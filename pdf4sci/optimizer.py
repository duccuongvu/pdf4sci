"""Rewrite oversized raster images in place.

Downsamples each image the analyzer flagged to the configured max DPI and
re-encodes it, leaving everything else in the PDF -- text, fonts, vector
content, links/annotations, and images already within budget -- untouched.

The encoding choice is: images with transparency always stay lossless
(never convert a transparent image to JPEG); otherwise, classifier.py's
content-based heuristic decides -- photographic/continuous-tone content
gets JPEG, everything else (plots, diagrams, screenshots, icons) stays
lossless, regardless of how the image happened to be encoded originally.

Every candidate replacement is encoded and measured *before* it is written
into the PDF; if downsampling plus re-encoding would not actually shrink
the image (can happen on small, already-near-optimal images, where resize
artifacts fight the encoder), the original is kept untouched instead --
matching the project's primary principle of only optimizing what is
actually wasteful.
"""

from __future__ import annotations

from dataclasses import dataclass

import pikepdf
import pymupdf

from .analyzer import PDFAnalysis, analyze_pdf
from .classifier import classify_image
from .config import AnalyzerConfig
from .images import (
    apply_jpeg,
    apply_lossless,
    apply_with_alpha,
    decode_for_edit,
    encode_jpeg,
    encode_lossless_for_pdf,
    resize_by_scale,
)


@dataclass
class OptimizationResult:
    xref: int
    page: int
    action: str  # "optimized" | "kept" | "skipped"
    reason: str
    before_bytes: int
    after_bytes: int = 0
    before_dims: tuple[int, int] = (0, 0)
    after_dims: tuple[int, int] = (0, 0)
    category: str = ""


def _plan_replacement(decoded, scale: float, jpeg_quality: int):
    """Encode a candidate replacement without touching the PDF yet, so its
    size can be compared against the original before committing to it.
    Returns (kind, payload, total_encoded_bytes, (width, height), category)."""
    resized = resize_by_scale(decoded.image, scale)

    if decoded.had_alpha:
        # Never convert a transparent image to JPEG, regardless of content.
        rgba = resized.convert("RGBA")
        rgb_encoded = encode_lossless_for_pdf(rgba.convert("RGB"))
        alpha_encoded = encode_lossless_for_pdf(rgba.getchannel("A"))
        total = len(rgb_encoded["data"]) + len(alpha_encoded["data"])
        return "alpha", (rgb_encoded, alpha_encoded), total, resized.size, "transparent"

    classification = classify_image(decoded.image, decoded.image.width, decoded.image.height)

    if classification.prefer_jpeg:
        rgb = resized.convert("RGB")
        data = encode_jpeg(rgb, jpeg_quality)
        return "jpeg", (data, rgb.size), len(data), resized.size, classification.category

    normalized = resized if resized.mode == "L" else resized.convert("RGB")
    encoded = encode_lossless_for_pdf(normalized)
    return "lossless", encoded, len(encoded["data"]), resized.size, classification.category


def _commit_replacement(pdf: pikepdf.Pdf, xref: int, kind: str, payload) -> None:
    obj = pdf.get_object((xref, 0))
    if kind == "alpha":
        rgb_encoded, alpha_encoded = payload
        apply_with_alpha(pdf, obj, rgb_encoded, alpha_encoded)
    elif kind == "jpeg":
        data, (width, height) = payload
        apply_jpeg(obj, data, width, height)
    else:
        apply_lossless(obj, payload)


def optimize_pdf(
    input_path: str,
    output_path: str,
    config: AnalyzerConfig | None = None,
    jpeg_quality: int = 92,
    analysis: PDFAnalysis | None = None,
    on_progress=None,
) -> list[OptimizationResult]:
    """Downsample every image `analyze_pdf` flagged as oversized and write
    the result to `output_path`. Returns a per-image list of what happened,
    in the same order as the analysis.

    `on_progress`, if given, is called as `on_progress(done, total, image)`
    before each image is considered (`image` is the analyzer's ImageInfo) --
    real progress for a caller that wants to report it (e.g. a GUI), never
    required and never a stand-in for a fake percentage."""
    config = config or AnalyzerConfig()
    analysis = analysis or analyze_pdf(input_path, config)

    mudoc = pymupdf.open(input_path)
    pdf = pikepdf.open(input_path)

    total = len(analysis.images)
    results: list[OptimizationResult] = []
    for done, img in enumerate(analysis.images):
        if on_progress is not None:
            on_progress(done, total, img)
        if img.recommendation != "downsample":
            results.append(
                OptimizationResult(img.xref, img.page, "kept", img.reason, img.compressed_size)
            )
            continue

        decoded, skip_reason = decode_for_edit(mudoc, img.xref)
        if decoded is None:
            results.append(
                OptimizationResult(img.xref, img.page, "skipped", skip_reason, img.compressed_size)
            )
            continue

        before_total = img.compressed_size
        if decoded.smask_xref:
            before_total += len(mudoc.xref_stream_raw(decoded.smask_xref))

        scale = config.max_dpi / img.effective_dpi
        try:
            kind, payload, after_total, new_dims, category = _plan_replacement(
                decoded, scale, jpeg_quality
            )
        except Exception as exc:
            results.append(
                OptimizationResult(
                    img.xref, img.page, "skipped", f"encode failed: {exc}", img.compressed_size
                )
            )
            continue

        if after_total >= before_total:
            results.append(
                OptimizationResult(
                    img.xref,
                    img.page,
                    "kept",
                    "re-encoding would not shrink this image",
                    before_total,
                )
            )
            continue

        try:
            _commit_replacement(pdf, img.xref, kind, payload)
        except Exception as exc:
            results.append(
                OptimizationResult(
                    img.xref, img.page, "skipped", f"replace failed: {exc}", before_total
                )
            )
            continue

        results.append(
            OptimizationResult(
                xref=img.xref,
                page=img.page,
                action="optimized",
                reason="downsampled",
                before_bytes=before_total,
                after_bytes=after_total,
                before_dims=(img.width, img.height),
                after_dims=new_dims,
                category=category,
            )
        )

    pdf.save(output_path)
    pdf.close()
    mudoc.close()
    return results
