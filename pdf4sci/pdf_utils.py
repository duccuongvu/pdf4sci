"""Small stateless helpers shared by analyzer/optimizer: size formatting and
PDF colorspace/filter name normalization."""

from __future__ import annotations

# Component counts for the colorspace names PyMuPDF reports on get_images().
# ICCBased spaces are already resolved by PyMuPDF to one of these generic
# names, so this covers the cases actually seen in practice.
_COLORSPACE_COMPONENTS = {
    "DeviceGray": 1,
    "CalGray": 1,
    "Indexed": 1,
    "Separation": 1,
    "DeviceRGB": 3,
    "CalRGB": 3,
    "Lab": 3,
    "DeviceCMYK": 4,
}

# Human-readable names for the PDF stream filters that matter for images.
_FILTER_NAMES = {
    "DCTDecode": "JPEG",
    "JPXDecode": "JPEG2000",
    "CCITTFaxDecode": "CCITT",
    "JBIG2Decode": "JBIG2",
    "FlateDecode": "Flate",
    "LZWDecode": "LZW",
    "RunLengthDecode": "RLE",
}


def colorspace_components(colorspace: str) -> int:
    """Number of color components for a colorspace name, defaulting to 3
    (RGB) for anything unrecognized rather than raising."""
    return _COLORSPACE_COMPONENTS.get(colorspace, 3)


def format_name(filters: list[str]) -> str:
    """Map a stream's filter chain to a human-readable image format label."""
    if not filters:
        return "raw"
    # The last filter in the chain is the one that determines the actual
    # pixel encoding (earlier filters, if any, are typically compression
    # wrappers PyMuPDF already strips out for images).
    return _FILTER_NAMES.get(filters[-1], filters[-1])


def human_size(num_bytes: float) -> str:
    """Format a byte count like '3.1 MB' / '240 KB', matching the style used
    throughout the CLI reports."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}" if size < 100 else f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def parse_size(text: str) -> int:
    """Parse a human size string like '6MB', '6 MB', '500KB', '2GB' into bytes."""
    text = text.strip().upper()
    units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
    for suffix, multiplier in sorted(units.items(), key=lambda kv: -len(kv[0])):
        if text.endswith(suffix):
            number_part = text[: -len(suffix)].strip()
            if number_part:
                return int(float(number_part) * multiplier)
    return int(float(text))
