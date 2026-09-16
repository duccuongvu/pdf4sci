"""Post-compression validation.

Checks that structurally matter -- the output reopens, page count and
dimensions are unchanged, text extraction and link counts match, no images
went missing, transparency wasn't lost, and vector content wasn't
rasterized -- are pass/fail. SSIM/PSNR are computed only if asked for and
are reported purely as diagnostics: this tool does not optimize for them
(see the project's primary design principle), so a low score is
informative, not a bug.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pymupdf


@dataclass
class PageDiagnostic:
    page: int
    psnr: float | None
    ssim: float | None


@dataclass
class ValidationReport:
    reopened_ok: bool
    page_count_match: bool = False
    page_dims_match: bool = False
    text_match: bool = False
    links_match: bool = False
    image_count_match: bool = False
    alpha_count_match: bool = False
    vector_count_match: bool = False
    issues: list[str] = field(default_factory=list)
    diagnostics: list[PageDiagnostic] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            self.reopened_ok
            and self.page_count_match
            and self.page_dims_match
            and self.text_match
            and self.links_match
            and self.image_count_match
            and self.alpha_count_match
            and self.vector_count_match
        )


def _psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))
    if mse == 0:
        return float("inf")
    return 20 * np.log10(255.0) - 10 * np.log10(mse)


def _ssim(a: np.ndarray, b: np.ndarray) -> float:
    """Global (unwindowed) SSIM -- a lightweight approximation adequate for
    a diagnostic number, not a substitute for a proper windowed SSIM."""
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    mu_a, mu_b = a.mean(), b.mean()
    var_a, var_b = a.var(), b.var()
    cov = float(((a - mu_a) * (b - mu_b)).mean())
    return ((2 * mu_a * mu_b + c1) * (2 * cov + c2)) / (
        (mu_a**2 + mu_b**2 + c1) * (var_a + var_b + c2)
    )


def _render_gray(page: pymupdf.Page, dpi: int) -> np.ndarray:
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


def compute_page_diagnostics(input_path: str, output_path: str, dpi: int = 100) -> list[PageDiagnostic]:
    in_doc = pymupdf.open(input_path)
    out_doc = pymupdf.open(output_path)
    diagnostics = []
    try:
        for i in range(min(in_doc.page_count, out_doc.page_count)):
            a = _render_gray(in_doc[i], dpi)
            b = _render_gray(out_doc[i], dpi)
            if a.shape != b.shape:
                diagnostics.append(PageDiagnostic(i + 1, None, None))
                continue
            diagnostics.append(PageDiagnostic(i + 1, _psnr(a, b), _ssim(a, b)))
    finally:
        in_doc.close()
        out_doc.close()
    return diagnostics


def validate(
    input_path: str,
    output_path: str,
    with_diagnostics: bool = False,
    diagnostic_dpi: int = 100,
) -> ValidationReport:
    try:
        out_doc = pymupdf.open(output_path)
    except Exception as exc:
        return ValidationReport(reopened_ok=False, issues=[f"output PDF failed to reopen: {exc}"])

    in_doc = pymupdf.open(input_path)
    issues: list[str] = []

    page_count_match = in_doc.page_count == out_doc.page_count
    if not page_count_match:
        issues.append(f"page count changed: {in_doc.page_count} -> {out_doc.page_count}")

    page_dims_match = text_match = links_match = True
    image_count_match = alpha_count_match = vector_count_match = True

    for i in range(min(in_doc.page_count, out_doc.page_count)):
        p_in, p_out = in_doc[i], out_doc[i]

        dims_in = (round(p_in.rect.width, 1), round(p_in.rect.height, 1))
        dims_out = (round(p_out.rect.width, 1), round(p_out.rect.height, 1))
        if dims_in != dims_out:
            page_dims_match = False
            issues.append(f"page {i + 1}: dimensions changed {dims_in} -> {dims_out}")

        if p_in.get_text() != p_out.get_text():
            text_match = False
            issues.append(f"page {i + 1}: text extraction differs")

        if len(p_in.get_links()) != len(p_out.get_links()):
            links_match = False
            issues.append(f"page {i + 1}: link count changed")

        xrefs_in = {im[0] for im in p_in.get_images(full=True)}
        xrefs_out = {im[0] for im in p_out.get_images(full=True)}
        if len(xrefs_in) != len(xrefs_out):
            image_count_match = False
            issues.append(f"page {i + 1}: image count changed ({len(xrefs_in)} -> {len(xrefs_out)})")

        alpha_in = sum(1 for x in xrefs_in if in_doc.xref_get_key(x, "SMask")[0] != "null")
        alpha_out = sum(1 for x in xrefs_out if out_doc.xref_get_key(x, "SMask")[0] != "null")
        if alpha_in != alpha_out:
            alpha_count_match = False
            issues.append(f"page {i + 1}: transparent-image count changed ({alpha_in} -> {alpha_out})")

        drawings_in = len(p_in.get_drawings())
        drawings_out = len(p_out.get_drawings())
        if drawings_in != drawings_out:
            vector_count_match = False
            issues.append(
                f"page {i + 1}: vector path count changed ({drawings_in} -> {drawings_out}), "
                "possible rasterization"
            )

    diagnostics = (
        compute_page_diagnostics(input_path, output_path, diagnostic_dpi) if with_diagnostics else []
    )

    in_doc.close()
    out_doc.close()

    return ValidationReport(
        reopened_ok=True,
        page_count_match=page_count_match,
        page_dims_match=page_dims_match,
        text_match=text_match,
        links_match=links_match,
        image_count_match=image_count_match,
        alpha_count_match=alpha_count_match,
        vector_count_match=vector_count_match,
        issues=issues,
        diagnostics=diagnostics,
    )
