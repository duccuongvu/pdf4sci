import pymupdf

from pdf4sci.analyzer import analyze_pdf
from pdf4sci.config import AnalyzerConfig
from pdf4sci.optimizer import optimize_pdf


def test_high_dpi_image_is_downsampled_and_shrinks(make_pdf, png_bytes, tmp_path):
    data = png_bytes(3000, 3000)

    def build(doc):
        page = doc.new_page()
        page.insert_image(pymupdf.Rect(0, 0, 72, 72), stream=data)  # 3000 DPI

    path = make_pdf("high_dpi.pdf", build)
    out = str(tmp_path / "out.pdf")

    results = optimize_pdf(path, out, AnalyzerConfig(max_dpi=300))

    assert len(results) == 1
    assert results[0].action == "optimized"
    assert results[0].after_bytes < results[0].before_bytes

    doc = pymupdf.open(out)
    img = doc[0].get_images(full=True)[0]
    assert img[2] <= 400 and img[3] <= 400  # downsampled, not left at 3000px
    doc.close()


def test_low_dpi_image_untouched_bytes(make_pdf, png_bytes, tmp_path):
    data = png_bytes(250, 250)

    def build(doc):
        page = doc.new_page()
        page.insert_image(pymupdf.Rect(0, 0, 72, 72), stream=data)  # 250 DPI

    path = make_pdf("low_dpi.pdf", build)
    out = str(tmp_path / "out.pdf")

    results = optimize_pdf(path, out, AnalyzerConfig(max_dpi=300))

    assert results[0].action == "kept"
    doc = pymupdf.open(out)
    img = doc[0].get_images(full=True)[0]
    assert (img[2], img[3]) == (250, 250)
    doc.close()


def test_transparency_preserved_after_downsample(make_pdf, png_bytes, tmp_path):
    data = png_bytes(2000, 2000, mode="RGBA", color=(10, 20, 30, 128))

    def build(doc):
        page = doc.new_page()
        page.insert_image(pymupdf.Rect(0, 0, 72, 72), stream=data)  # 2000 DPI

    path = make_pdf("alpha.pdf", build)
    out = str(tmp_path / "out.pdf")

    results = optimize_pdf(path, out, AnalyzerConfig(max_dpi=300))
    assert results[0].action == "optimized"

    doc = pymupdf.open(out)
    xref = doc[0].get_images(full=True)[0][0]
    info = doc.extract_image(xref)
    assert info["smask"] != 0, "soft mask must survive downsampling"
    doc.close()


def test_never_ships_a_larger_image(make_pdf, png_bytes, tmp_path):
    # A tiny image just barely over the DPI threshold: downsampling by a
    # small factor plus PNG/Flate overhead can end up no smaller than the
    # original. The optimizer must detect this and keep the original.
    data = png_bytes(40, 40)

    def build(doc):
        page = doc.new_page()
        page.insert_image(pymupdf.Rect(0, 0, 9, 9), stream=data)  # ~320 DPI

    path = make_pdf("tiny.pdf", build)
    out = str(tmp_path / "out.pdf")

    analysis = analyze_pdf(path, AnalyzerConfig(max_dpi=300))
    results = optimize_pdf(path, out, AnalyzerConfig(max_dpi=300), analysis=analysis)

    assert results[0].action in ("optimized", "kept")
    if results[0].action == "optimized":
        assert results[0].after_bytes < results[0].before_bytes
    else:
        assert "not shrink" in results[0].reason


def test_vector_content_and_page_count_survive(make_pdf, png_bytes, tmp_path):
    data = png_bytes(3000, 3000)

    def build(doc):
        page = doc.new_page()
        page.insert_image(pymupdf.Rect(0, 0, 72, 72), stream=data)
        page.draw_line((10, 10), (200, 200))
        page.insert_text((50, 300), "Scientific paper text")
        doc.new_page()  # second, image-free page

    path = make_pdf("mixed.pdf", build)
    out = str(tmp_path / "out.pdf")

    optimize_pdf(path, out, AnalyzerConfig(max_dpi=300))

    orig = pymupdf.open(path)
    new = pymupdf.open(out)
    assert new.page_count == orig.page_count == 2
    assert new[0].get_text() == orig[0].get_text()
    for i in range(orig.page_count):
        assert new[i].rect.width == orig[i].rect.width
        assert new[i].rect.height == orig[i].rect.height
    # the line is vector content -- must not have been rasterized into an
    # extra image on the page.
    assert len(new[0].get_images(full=True)) == 1
    orig.close()
    new.close()


def test_cmyk_image_is_skipped_not_corrupted(make_pdf, tmp_path):
    import io

    from PIL import Image

    def build(doc):
        page = doc.new_page()
        img = Image.new("CMYK", (2000, 2000), (10, 20, 30, 5))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        page.insert_image(pymupdf.Rect(0, 0, 72, 72), stream=buf.getvalue())

    path = make_pdf("cmyk.pdf", build)
    out = str(tmp_path / "out.pdf")

    results = optimize_pdf(path, out, AnalyzerConfig(max_dpi=300))

    assert results[0].action == "skipped"
    # Output must still be a valid, openable PDF with the image intact.
    doc = pymupdf.open(out)
    assert len(doc[0].get_images(full=True)) == 1
    doc.close()
