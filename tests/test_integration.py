"""End-to-end coverage using one PDF that combines the content types listed
in the project spec: vector graphics, text, a high-resolution photo, a
PNG-like plot, transparency, a repeated image, a grayscale image, and a
rotated/scaled image."""

import pymupdf

from pdfshrink.config import AnalyzerConfig
from pdfshrink.optimizer import optimize_pdf
from pdfshrink.validation import validate


def _build_kitchen_sink_pdf(make_pdf, png_bytes):
    def build(doc):
        page = doc.new_page()

        # Vector graphics + text.
        page.draw_rect(pymupdf.Rect(20, 20, 200, 120))
        page.draw_line((20, 20), (200, 120))
        page.insert_text((30, 150), "Scientific paper body text with equations")

        # High-resolution "photo" (noisy, continuous-tone).
        import random

        random.seed(1)
        photo = png_bytes(1, 1)  # placeholder, replaced below
        from PIL import Image

        img = Image.new("RGB", (1200, 1200))
        img.putdata(
            [
                (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
                for _ in range(1200 * 1200)
            ]
        )
        import io

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        page.insert_image(pymupdf.Rect(210, 20, 310, 120), stream=buf.getvalue())  # ~864 DPI

        # A repeated image (same xref placed twice).
        icon_data = png_bytes(2000, 2000)
        xref = page.insert_image(pymupdf.Rect(210, 130, 230, 150), stream=icon_data)  # very high DPI
        page.insert_image(pymupdf.Rect(240, 130, 260, 150), xref=xref)

        # Transparent image.
        alpha_data = png_bytes(1500, 1500, mode="RGBA", color=(5, 10, 15, 100))
        page.insert_image(pymupdf.Rect(20, 160, 60, 200), stream=alpha_data)  # high DPI

        # Grayscale image.
        gray = Image.new("L", (1000, 1000), 128)
        buf2 = io.BytesIO()
        gray.save(buf2, format="PNG")
        page.insert_image(pymupdf.Rect(70, 160, 110, 200), stream=buf2.getvalue())  # high DPI

        # Rotated/scaled image (placed via a rotated rect).
        scaled_data = png_bytes(1800, 900)
        page.insert_image(pymupdf.Rect(120, 160, 300, 250), stream=scaled_data, rotate=90)

    return make_pdf("kitchen_sink.pdf", build)


def test_kitchen_sink_pdf_compresses_safely(make_pdf, png_bytes, tmp_path):
    path = _build_kitchen_sink_pdf(make_pdf, png_bytes)
    out = str(tmp_path / "out.pdf")

    results = optimize_pdf(path, out, AnalyzerConfig(max_dpi=300))
    assert any(r.action == "optimized" for r in results)

    report = validate(path, out)
    assert report.passed, report.issues

    # Vector content (the rect + line) must not have been rasterized.
    orig = pymupdf.open(path)
    new = pymupdf.open(out)
    assert len(new[0].get_drawings()) == len(orig[0].get_drawings()) > 0
    orig.close()
    new.close()
