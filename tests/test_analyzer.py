import pymupdf

from pdfshrink.analyzer import analyze_pdf
from pdfshrink.config import AnalyzerConfig


def test_high_dpi_image_flagged_for_downsample(make_pdf, png_bytes):
    # 3000x3000 px image placed in a 1x1 inch box -> 3000 DPI, way over 300.
    data = png_bytes(3000, 3000)

    def build(doc):
        page = doc.new_page()
        page.insert_image(pymupdf.Rect(0, 0, 72, 72), stream=data)

    path = make_pdf("high_dpi.pdf", build)
    analysis = analyze_pdf(path, AnalyzerConfig(max_dpi=300))

    assert len(analysis.images) == 1
    img = analysis.images[0]
    assert img.width == 3000 and img.height == 3000
    assert 2900 < img.effective_dpi < 3100
    assert img.recommendation == "downsample"


def test_low_dpi_image_kept(make_pdf, png_bytes):
    # 250x250 px in a 1x1 inch box -> 250 DPI, under the 300 threshold.
    data = png_bytes(250, 250)

    def build(doc):
        page = doc.new_page()
        page.insert_image(pymupdf.Rect(0, 0, 72, 72), stream=data)

    path = make_pdf("low_dpi.pdf", build)
    analysis = analyze_pdf(path, AnalyzerConfig(max_dpi=300))

    assert len(analysis.images) == 1
    assert analysis.images[0].recommendation == "keep"


def test_vector_only_pdf_has_no_images(make_pdf):
    def build(doc):
        page = doc.new_page()
        page.draw_line((10, 10), (100, 100))
        page.insert_text((50, 50), "Hello scientific paper")

    path = make_pdf("vector_only.pdf", build)
    analysis = analyze_pdf(path)

    assert analysis.images == []
    assert analysis.image_bytes_total == 0
    assert analysis.other_bytes_total == analysis.file_size


def test_transparency_detected(make_pdf, png_bytes):
    data = png_bytes(200, 200, mode="RGBA", color=(10, 20, 30, 128))

    def build(doc):
        page = doc.new_page()
        page.insert_image(pymupdf.Rect(0, 0, 200, 200), stream=data)

    path = make_pdf("alpha.pdf", build)
    analysis = analyze_pdf(path)

    assert len(analysis.images) == 1
    assert analysis.images[0].has_alpha is True


def test_reused_image_flagged(make_pdf, png_bytes):
    data = png_bytes(100, 100)

    def build(doc):
        page = doc.new_page()
        xref = page.insert_image(pymupdf.Rect(0, 0, 100, 100), stream=data)
        page.insert_image(pymupdf.Rect(200, 200, 300, 300), xref=xref)

    path = make_pdf("reused.pdf", build)
    analysis = analyze_pdf(path)

    assert len(analysis.images) == 1
    img = analysis.images[0]
    assert img.is_reused is True
    assert img.total_occurrences == 2
    assert img.placements_on_page == 2


def test_image_bytes_and_file_size_are_consistent(make_pdf, png_bytes):
    data = png_bytes(500, 500)

    def build(doc):
        page = doc.new_page()
        page.insert_image(pymupdf.Rect(0, 0, 200, 200), stream=data)

    path = make_pdf("sizes.pdf", build)
    analysis = analyze_pdf(path)

    assert analysis.image_bytes_total <= analysis.file_size
    assert analysis.image_bytes_total + analysis.other_bytes_total == analysis.file_size


def test_never_upscales_recommendation_reason(make_pdf, png_bytes):
    # An image already below the threshold should never be touched, and the
    # reason string should say so explicitly (useful in --verbose output).
    data = png_bytes(100, 100)

    def build(doc):
        page = doc.new_page()
        page.insert_image(pymupdf.Rect(0, 0, 72, 72), stream=data)  # 100 DPI

    path = make_pdf("keep_reason.pdf", build)
    analysis = analyze_pdf(path, AnalyzerConfig(max_dpi=300))

    img = analysis.images[0]
    assert img.recommendation == "keep"
    assert "DPI" in img.reason
