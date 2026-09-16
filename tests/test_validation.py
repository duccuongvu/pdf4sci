import pymupdf

from pdfshrink.config import AnalyzerConfig
from pdfshrink.optimizer import optimize_pdf
from pdfshrink.validation import validate


def test_valid_compression_passes_all_checks(make_pdf, png_bytes, tmp_path):
    data = png_bytes(3000, 3000)

    def build(doc):
        page = doc.new_page()
        page.insert_image(pymupdf.Rect(0, 0, 72, 72), stream=data)
        page.insert_text((50, 300), "Some scientific text")

    path = make_pdf("valid.pdf", build)
    out = str(tmp_path / "out.pdf")
    optimize_pdf(path, out, AnalyzerConfig(max_dpi=300))

    report = validate(path, out)
    assert report.passed, report.issues


def test_missing_output_file_fails_reopen_gracefully(tmp_path):
    report = validate(str(tmp_path / "nope.pdf"), str(tmp_path / "also_nope.pdf"))
    assert report.reopened_ok is False
    assert report.passed is False
    assert report.issues


def test_detects_text_loss(make_pdf, tmp_path):
    def build_in(doc):
        page = doc.new_page()
        page.insert_text((50, 50), "Original text content")

    def build_out(doc):
        doc.new_page()  # same page count/size, but text is gone

    in_path = make_pdf("in.pdf", build_in)
    out_path = make_pdf("out.pdf", build_out)

    report = validate(in_path, out_path)
    assert report.text_match is False
    assert report.passed is False


def test_diagnostics_identical_pdfs_score_perfectly(make_pdf, png_bytes, tmp_path):
    data = png_bytes(200, 200)

    def build(doc):
        page = doc.new_page()
        page.insert_image(pymupdf.Rect(0, 0, 100, 100), stream=data)

    path = make_pdf("same.pdf", build)

    report = validate(path, path, with_diagnostics=True)
    assert report.diagnostics
    for d in report.diagnostics:
        assert d.psnr == float("inf")
        assert d.ssim == 1.0
