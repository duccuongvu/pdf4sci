"""Phase 1: read a PDF and report, per raster image, what it is, how big it
is, and how much resolution it actually needs on the page.

This module only inspects the document; it never modifies it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import pymupdf

from .config import AnalyzerConfig
from .pdf_utils import colorspace_components, format_name


@dataclass
class ImageInfo:
    page: int  # 1-indexed
    xref: int
    width: int
    height: int
    colorspace: str
    bpc: int
    has_alpha: bool
    is_stencil_mask: bool
    format: str
    filters: list[str]
    compressed_size: int
    decoded_size: int
    display_width_in: float
    display_height_in: float
    effective_dpi: float
    placements_on_page: int
    total_occurrences: int
    recommendation: str
    reason: str

    @property
    def is_reused(self) -> bool:
        return self.total_occurrences > 1


@dataclass
class PDFAnalysis:
    path: str
    file_size: int
    num_pages: int
    images: list[ImageInfo] = field(default_factory=list)
    image_bytes_total: int = 0
    other_bytes_total: int = 0


def _filters_of(doc: pymupdf.Document, xref: int) -> list[str]:
    kind, value = doc.xref_get_key(xref, "Filter")
    if kind == "null" or not value:
        return []
    if kind == "name":
        return [value.lstrip("/")]
    if kind == "array":
        return [tok.lstrip("/") for tok in value.strip("[]").split() if tok]
    return [str(value)]


def _has_smask_or_mask(doc: pymupdf.Document, xref: int) -> bool:
    for key in ("SMask", "Mask"):
        kind, _ = doc.xref_get_key(xref, key)
        if kind != "null":
            return True
    return False


def _is_image_mask(doc: pymupdf.Document, xref: int) -> bool:
    kind, value = doc.xref_get_key(xref, "ImageMask")
    return kind != "null" and value == "true"


def _classify_dpi(effective_dpi: float, config: AnalyzerConfig) -> tuple[str, str]:
    if effective_dpi <= config.max_dpi:
        return "keep", f"already {effective_dpi:.0f} DPI"
    return "downsample", f"{effective_dpi:.0f} DPI exceeds {config.max_dpi} DPI threshold"


def analyze_pdf(path: str, config: AnalyzerConfig | None = None) -> PDFAnalysis:
    """Inspect every raster image in `path` and return a structured report.

    Each *placement* of an image on a page is analyzed separately (a shared
    xref can be displayed at different sizes on different pages), but a
    single ImageInfo per (page, xref) is emitted, using the placement with
    the highest effective DPI on that page -- so a recommendation never
    under-estimates the resolution actually required.
    """
    config = config or AnalyzerConfig()
    doc = pymupdf.open(path)

    # First pass: how many times does each xref get placed anywhere in the
    # document, so we can flag reused images.
    occurrences_by_xref: dict[int, int] = {}
    for page in doc:
        # get_images() can list the same xref more than once per page (it
        # enumerates resource names, and one xref may be bound to several),
        # so dedupe before asking for its rects -- get_image_rects already
        # returns every placement of that xref on the page in one call.
        xrefs_on_page = {img[0] for img in page.get_images(full=True)}
        for xref in xrefs_on_page:
            occurrences_by_xref[xref] = occurrences_by_xref.get(xref, 0) + len(
                page.get_image_rects(xref)
            )

    stream_size_cache: dict[int, int] = {}

    def stream_size(xref: int) -> int:
        if xref not in stream_size_cache:
            stream_size_cache[xref] = len(doc.xref_stream_raw(xref))
        return stream_size_cache[xref]

    images: list[ImageInfo] = []
    seen_on_page: set[tuple[int, int]] = set()

    for page_index in range(doc.page_count):
        page = doc[page_index]
        for img in page.get_images(full=True):
            xref = img[0]
            key = (page_index, xref)
            if key in seen_on_page:
                continue
            seen_on_page.add(key)

            width, height, bpc, colorspace = img[2], img[3], img[4], img[5]
            rects = page.get_image_rects(xref)
            if not rects:
                # Referenced in the page's resources but not actually
                # painted anywhere on the page (e.g. an unused XObject) --
                # nothing to size against, so skip it.
                continue

            # Worst case (highest DPI) placement decides the recommendation.
            best_dpi = -1.0
            best_disp = (0.0, 0.0)
            for rect in rects:
                disp_w_in = rect.width / 72.0
                disp_h_in = rect.height / 72.0
                if disp_w_in <= 0 or disp_h_in <= 0:
                    continue
                dpi = max(width / disp_w_in, height / disp_h_in)
                if dpi > best_dpi:
                    best_dpi = dpi
                    best_disp = (disp_w_in, disp_h_in)

            if best_dpi < 0:
                continue

            filters = _filters_of(doc, xref)
            is_stencil = _is_image_mask(doc, xref)
            n_components = 1 if is_stencil else colorspace_components(colorspace)
            decoded_size = width * height * n_components * max(bpc, 1) // 8

            recommendation, reason = _classify_dpi(best_dpi, config)
            if is_stencil:
                recommendation, reason = "keep", "stencil mask, not a content image"

            images.append(
                ImageInfo(
                    page=page_index + 1,
                    xref=xref,
                    width=width,
                    height=height,
                    colorspace=colorspace,
                    bpc=bpc,
                    has_alpha=_has_smask_or_mask(doc, xref),
                    is_stencil_mask=is_stencil,
                    format=format_name(filters),
                    filters=filters,
                    compressed_size=stream_size(xref),
                    decoded_size=decoded_size,
                    display_width_in=best_disp[0],
                    display_height_in=best_disp[1],
                    effective_dpi=best_dpi,
                    placements_on_page=len(rects),
                    total_occurrences=occurrences_by_xref.get(xref, len(rects)),
                    recommendation=recommendation,
                    reason=reason,
                )
            )

    image_bytes_total = sum(stream_size_cache[x] for x in occurrences_by_xref)
    file_size = os.path.getsize(path)

    analysis = PDFAnalysis(
        path=path,
        file_size=file_size,
        num_pages=doc.page_count,
        images=images,
        image_bytes_total=image_bytes_total,
        other_bytes_total=max(file_size - image_bytes_total, 0),
    )
    doc.close()
    return analysis
