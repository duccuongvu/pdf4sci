import os

import pymupdf

from pdf4sci.quality import optimize_to_target_size


def _build_multi_image_pdf(make_pdf, png_bytes):
    def build(doc):
        for _ in range(3):
            page = doc.new_page()
            data = png_bytes(2000, 2000)
            page.insert_image(pymupdf.Rect(0, 0, 100, 100), stream=data)  # ~1440 DPI

    return make_pdf("multi.pdf", build)


def test_target_already_met_copies_unmodified(make_pdf, png_bytes, tmp_path):
    path = _build_multi_image_pdf(make_pdf, png_bytes)
    out = str(tmp_path / "out.pdf")
    original_size = os.path.getsize(path)

    result = optimize_to_target_size(path, out, target_bytes=original_size * 2)

    assert result.achieved is True
    assert result.steps_tried == 0
    assert os.path.getsize(out) == original_size


def test_target_size_is_respected(make_pdf, png_bytes, tmp_path):
    path = _build_multi_image_pdf(make_pdf, png_bytes)
    out = str(tmp_path / "out.pdf")
    original_size = os.path.getsize(path)
    target = original_size // 2

    result = optimize_to_target_size(path, out, target_bytes=target)

    assert os.path.getsize(out) <= target or result.warning is not None
    if result.achieved:
        assert result.final_size <= target


def test_unreachable_target_warns_instead_of_failing(make_pdf, png_bytes, tmp_path):
    path = _build_multi_image_pdf(make_pdf, png_bytes)
    out = str(tmp_path / "out.pdf")

    # 1 byte is unreachable for any real PDF -- must warn, not crash or lie.
    result = optimize_to_target_size(path, out, target_bytes=1, min_jpeg_quality=75)

    assert result.final_size > 1
    assert result.warning is not None
    assert os.path.exists(out)  # still produced a usable, valid PDF


def test_ladder_never_exceeds_min_jpeg_quality_floor():
    from pdf4sci.quality import _ladder

    steps = _ladder(min_jpeg_quality=88)
    assert all(q >= 88 for _, q in steps)
    assert steps[-1][1] == 88  # the floor itself is always tried
