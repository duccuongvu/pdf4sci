"""Cheap, heuristic content classification for raster images.

No machine learning: just entropy, unique-color count, and edge density on
a small thumbnail, plus pixel dimensions. Good enough to separate "this is
a continuous-tone photo, JPEG is fine" from "this is a plot/diagram/icon,
keep it lossless" -- which is all the compression policy actually needs.

Thresholds were calibrated against the two real scientific-paper PDFs used
during development (mostly vector-rendered plots and equation snippets,
plus a handful of genuine photos and many tiny UI icons) and are
deliberately conservative: when in doubt, classify toward the category
that keeps lossless encoding, since that's the safe failure mode for a
tool whose priority is preserving figure quality.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageFilter

ICON_MAX_DIM = 48
PHOTO_ENTROPY_THRESHOLD = 5.5
SCREENSHOT_ENTROPY_RANGE = (3.5, 5.5)
SCREENSHOT_EDGE_RATIO_THRESHOLD = 0.15

CATEGORIES = ("icon", "photo", "screenshot", "plot")


@dataclass
class ImageClass:
    category: str  # one of CATEGORIES
    prefer_jpeg: bool  # False means "keep lossless regardless of format"
    reason: str


def _thumbnail_stats(img: Image.Image) -> tuple[float, int | None, float]:
    thumb = img.convert("RGB") if img.mode not in ("L", "RGB") else img
    thumb = thumb.copy()
    thumb.thumbnail((256, 256))
    gray = thumb.convert("L")
    entropy = gray.entropy()
    colors = thumb.convert("RGB").getcolors(maxcolors=1_000_000)
    n_colors = len(colors) if colors is not None else None
    edges = gray.filter(ImageFilter.FIND_EDGES)
    bw = edges.point(lambda p: 255 if p > 24 else 0)
    total = bw.width * bw.height
    edge_ratio = (bw.histogram()[255] / total) if total else 0.0
    return entropy, n_colors, edge_ratio


def classify_image(img: Image.Image, width: int, height: int) -> ImageClass:
    """Classify a decoded image (pre-resize) by its original pixel content.

    `width`/`height` are the image's own pixel dimensions -- used for the
    icon check, since a photo thumbnail is judged by its content, but a
    16x16 logo is judged by simply being 16x16.
    """
    if max(width, height) <= ICON_MAX_DIM:
        return ImageClass("icon", prefer_jpeg=False, reason=f"{width}x{height}, tiny UI/icon asset")

    entropy, n_colors, edge_ratio = _thumbnail_stats(img)

    if entropy >= PHOTO_ENTROPY_THRESHOLD:
        return ImageClass(
            "photo", prefer_jpeg=True, reason=f"entropy={entropy:.1f} -> continuous-tone content"
        )

    lo, hi = SCREENSHOT_ENTROPY_RANGE
    if lo <= entropy < hi and edge_ratio > SCREENSHOT_EDGE_RATIO_THRESHOLD:
        return ImageClass(
            "screenshot",
            prefer_jpeg=False,
            reason=f"entropy={entropy:.1f}, edge_ratio={edge_ratio:.2f} -> UI/mixed content",
        )

    return ImageClass(
        "plot",
        prefer_jpeg=False,
        reason=f"entropy={entropy:.1f}, colors={n_colors} -> line art/diagram, prefer lossless",
    )
