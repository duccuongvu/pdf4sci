"""Low-level, per-image decode / resize / encode / replace operations.

Kept separate from optimizer.py so PDF image-stream mechanics (PNG
predictors, soft masks, DCTDecode) never leak into compression policy.

A PDF image XObject is not a container for a JPEG or PNG *file* -- except
for DCTDecode streams, which really are literal JPEG file bytes. A
FlateDecode image stream holds raw scanline data, optionally run through
one of PNG's five per-row predictors (PDF's Predictor 15, "PNG optimum",
is bit-for-bit the same scheme PNG itself uses). That means a PNG file's
concatenated IDAT payload can be reused directly as a Flate-encoded PDF
image stream, with matching /DecodeParms -- so lossless re-encoding here
goes through Pillow/oxipng (for their better compression) and then strips
the PNG container down to just that payload, rather than reimplementing
PNG filtering from scratch. Encoding falls back to a plain, unfiltered
Flate stream (Predictor 1) whenever the produced PNG doesn't match the
one shape (8-bit, non-interlaced, gray or RGB) this trick expects.
"""

from __future__ import annotations

import io
import os
import shutil
import struct
import subprocess
import tempfile
import zlib
from dataclasses import dataclass

import pikepdf
import pymupdf
from PIL import Image

_OXIPNG = shutil.which("oxipng")


@dataclass
class DecodedImage:
    image: Image.Image  # mode "L" or "RGBA" (alpha already merged in if present)
    had_alpha: bool
    source_ext: str  # "jpeg", "png", ... as reported by PyMuPDF's extract_image
    smask_xref: int = 0  # original soft-mask object, if had_alpha (for size comparisons)


def decode_for_edit(doc: pymupdf.Document, xref: int) -> tuple[DecodedImage | None, str | None]:
    """Decode an image xref (plus its soft mask, if any) into a single
    Pillow image ready to resize/re-encode.

    Returns (decoded, None) on success, or (None, reason) when the image
    can't be safely round-tripped this way -- the caller should leave the
    original object untouched and report `reason`.
    """
    kind, value = doc.xref_get_key(xref, "ImageMask")
    if kind != "null" and value == "true":
        return None, "stencil mask, not a content image"

    # /Mask (color-key ranges, or a reference to a separate stencil image)
    # has transparency semantics tied to the exact original pixel values;
    # resampling would silently break it, so leave these alone.
    kind, _ = doc.xref_get_key(xref, "Mask")
    if kind != "null":
        return None, "explicit /Mask transparency, unsafe to resample"

    try:
        info = doc.extract_image(xref)
    except Exception as exc:
        return None, f"could not decode image: {exc}"

    n_components = info.get("colorspace", 0)
    if n_components not in (1, 3):
        # CMYK or an unresolved colorspace -- Pillow/PNG can't round-trip
        # CMYK without a color shift, so leave it untouched rather than
        # guess at a conversion.
        return None, f"unsupported colorspace ({info.get('cs-name', n_components)})"

    try:
        base = Image.open(io.BytesIO(info["image"]))
        base.load()
    except Exception as exc:
        return None, f"could not open decoded image: {exc}"

    if base.mode == "P":
        base = base.convert("RGB")  # lossless: just expands the palette

    smask_xref = info.get("smask", 0)
    had_alpha = False
    if smask_xref:
        try:
            smask_info = doc.extract_image(smask_xref)
            alpha = Image.open(io.BytesIO(smask_info["image"])).convert("L")
            if alpha.size != base.size:
                alpha = alpha.resize(base.size, Image.LANCZOS)
            base = base.convert("RGBA")
            base.putalpha(alpha)
            had_alpha = True
        except Exception as exc:
            return None, f"could not decode soft mask: {exc}"

    return DecodedImage(
        image=base, had_alpha=had_alpha, source_ext=info["ext"], smask_xref=smask_xref
    ), None


def resize_by_scale(img: Image.Image, scale: float) -> Image.Image:
    """Scale `img` by `scale` (< 1 to downsample), preserving aspect ratio.
    A scale >= 1 is a no-op: this tool never upscales."""
    if scale >= 1:
        return img
    new_w = max(1, round(img.width * scale))
    new_h = max(1, round(img.height * scale))
    if (new_w, new_h) == img.size:
        return img
    return img.resize((new_w, new_h), Image.LANCZOS)


def _oxipng_optimize(png_bytes: bytes) -> bytes:
    if not _OXIPNG:
        return png_bytes
    fd, path = tempfile.mkstemp(suffix=".png")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(png_bytes)
        subprocess.run(
            [_OXIPNG, "-o", "4", "--quiet", path],
            check=True,
            timeout=60,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with open(path, "rb") as f:
            return f.read()
    except Exception:
        return png_bytes
    finally:
        os.unlink(path)


def _split_png_idat(png_bytes: bytes):
    """Return (idat_bytes, colors, width, height) reusable as a Predictor-15
    Flate stream, or None if this PNG doesn't match that one shape (8-bit,
    non-interlaced, grayscale or RGB -- exactly what encode_lossless_for_pdf
    produces before calling this, but oxipng's output is re-verified rather
    than assumed)."""
    if png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos = 8
    width = height = bit_depth = color_type = interlace = None
    idat = bytearray()
    while pos + 8 <= len(png_bytes):
        length = struct.unpack(">I", png_bytes[pos : pos + 4])[0]
        ctype = png_bytes[pos + 4 : pos + 8]
        data = png_bytes[pos + 8 : pos + 8 + length]
        if ctype == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", data)
        elif ctype == b"IDAT":
            idat.extend(data)
        elif ctype == b"IEND":
            break
        pos += 12 + length

    if bit_depth != 8 or interlace != 0:
        return None
    colors = {0: 1, 2: 3}.get(color_type)
    if colors is None:
        return None
    return bytes(idat), colors, width, height


def encode_lossless_for_pdf(img: Image.Image) -> dict:
    """Encode a "L" or "RGB" Pillow image for direct use as a PDF Flate
    image stream. Returns a dict with data/colors/width/height/predictor."""
    assert img.mode in ("L", "RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    png_bytes = _oxipng_optimize(buf.getvalue())

    parsed = _split_png_idat(png_bytes)
    if parsed is not None:
        data, colors, width, height = parsed
        return {"data": data, "colors": colors, "width": width, "height": height, "predictor": 15}

    colors = 1 if img.mode == "L" else 3
    data = zlib.compress(img.tobytes(), level=9)
    width, height = img.size
    return {"data": data, "colors": colors, "width": width, "height": height, "predictor": 1}


def encode_jpeg(img: Image.Image, quality: int) -> bytes:
    rgb = img.convert("RGB") if img.mode not in ("RGB", "L") else img
    buf = io.BytesIO()
    rgb.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buf.getvalue()


def _write_flate_stream(obj: pikepdf.Object, encoded: dict, colorspace_name: str) -> None:
    decode_parms = None
    if encoded["predictor"] != 1:
        decode_parms = pikepdf.Dictionary(
            Predictor=encoded["predictor"],
            Colors=encoded["colors"],
            BitsPerComponent=8,
            Columns=encoded["width"],
        )
    obj.write(encoded["data"], filter=pikepdf.Name("/FlateDecode"), decode_parms=decode_parms)
    obj.Width = encoded["width"]
    obj.Height = encoded["height"]
    obj.BitsPerComponent = 8
    obj.ColorSpace = pikepdf.Name(colorspace_name)


def _clear_stale_keys(obj: pikepdf.Object) -> None:
    # /Decode remaps component ranges for the *previous* encoding (e.g. an
    # inverted or indexed image); it no longer applies to freshly-encoded,
    # standard-range data.
    if "/Decode" in obj:
        del obj.Decode


def apply_lossless(obj: pikepdf.Object, encoded: dict) -> None:
    _write_flate_stream(obj, encoded, "/DeviceGray" if encoded["colors"] == 1 else "/DeviceRGB")
    _clear_stale_keys(obj)
    if "/SMask" in obj:
        del obj.SMask


def apply_jpeg(obj: pikepdf.Object, data: bytes, width: int, height: int) -> None:
    obj.write(data, filter=pikepdf.Name("/DCTDecode"))
    obj.Width = width
    obj.Height = height
    obj.BitsPerComponent = 8
    obj.ColorSpace = pikepdf.Name("/DeviceRGB")
    _clear_stale_keys(obj)
    if "/SMask" in obj:
        del obj.SMask


def apply_with_alpha(pdf: pikepdf.Pdf, obj: pikepdf.Object, rgb_encoded: dict, alpha_encoded: dict) -> None:
    smask_obj = pdf.make_indirect(pikepdf.Stream(pdf, b""))
    smask_obj.Type = pikepdf.Name("/XObject")
    smask_obj.Subtype = pikepdf.Name("/Image")
    _write_flate_stream(smask_obj, alpha_encoded, "/DeviceGray")

    _write_flate_stream(obj, rgb_encoded, "/DeviceRGB")
    _clear_stale_keys(obj)
    obj.SMask = smask_obj
