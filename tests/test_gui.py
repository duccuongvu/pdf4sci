"""GUI tests: parameter mapping, state lifecycle, worker signals. Run
against the offscreen Qt platform (no real display needed) -- pixel-level
rendering is verified manually/visually, not here.

Requires the `gui` extra (PySide6); skipped entirely if it's not
installed, since it's an optional part of the project.
"""

import os

import pymupdf
import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from pdf4sci.config import PRESETS  # noqa: E402
from pdf4sci.gui.main_window import MainWindow  # noqa: E402
from pdf4sci.gui.worker import CompressJob, CompressWorker  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp):
    w = MainWindow()
    yield w
    w.close()


def _make_pdf(tmp_path, png_bytes, name="paper.pdf"):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(pymupdf.Rect(0, 0, 72, 72), stream=png_bytes(3000, 3000))
    page.insert_text((50, 300), "Some scientific text")
    path = str(tmp_path / name)
    doc.save(path)
    doc.close()
    return path


def test_window_constructs_with_empty_state(window):
    assert window._input_path is None
    assert window._compressed_path is None
    assert window.settings_widget.isVisible() is False


def test_preset_defaults_map_to_advanced_fields(window):
    window.preset_combo.setCurrentText("scientific")
    assert window.max_dpi_spin.value() == PRESETS["scientific"].max_dpi
    assert window.jpeg_quality_spin.value() == PRESETS["scientific"].jpeg_quality

    window.preset_combo.setCurrentText("aggressive")
    assert window.max_dpi_spin.value() == PRESETS["aggressive"].max_dpi
    assert window.jpeg_quality_spin.value() == PRESETS["aggressive"].jpeg_quality


def test_load_pdf_populates_sidebar_and_viewer(window, tmp_path, png_bytes):
    path = _make_pdf(tmp_path, png_bytes)
    window.load_pdf(path)

    assert window._input_path == path
    # isVisible() would require the top-level window to be shown too; the
    # widget's own hidden flag is what load_pdf actually controls.
    assert window.settings_widget.isHidden() is False
    assert window.file_name_label.text() == os.path.basename(path)
    assert window.viewer.document.pageCount() == 1


def test_load_invalid_file_shows_no_state_change(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))

    bad = tmp_path / "fake.pdf"
    bad.write_text("not a pdf")
    window.load_pdf(str(bad))

    assert window._input_path is None
    assert window.settings_widget.isVisible() is False


def test_reset_all_clears_state_and_temp_dir(window, tmp_path, png_bytes):
    path = _make_pdf(tmp_path, png_bytes)
    window.load_pdf(path)
    job_dir = window._job_tmp_dir
    assert job_dir and os.path.isdir(job_dir)

    window.reset_all()

    assert window._input_path is None
    assert window._compressed_path is None
    assert not os.path.isdir(job_dir)
    assert window.viewer.document.pageCount() == 0


def test_load_another_pdf_clears_previous_compressed_result(window, tmp_path, png_bytes):
    first = _make_pdf(tmp_path, png_bytes, "first.pdf")
    window.load_pdf(first)
    window._compressed_path = "/tmp/pretend_compressed.pdf"  # simulate a finished compression
    window.result_widget.setVisible(True)

    second = _make_pdf(tmp_path, png_bytes, "second.pdf")
    window.load_pdf(second)

    assert window._input_path == second
    assert window._compressed_path is None
    assert window.result_widget.isVisible() is False


def test_compress_worker_emits_finished_with_smaller_output(tmp_path, png_bytes, qapp):
    from PySide6.QtCore import QEventLoop

    path = _make_pdf(tmp_path, png_bytes)
    out = str(tmp_path / "out.pdf")
    job = CompressJob(input_path=path, output_path=out, max_dpi=300, jpeg_quality=92, target_size_mb=None)
    worker = CompressWorker(job)

    results = {}
    loop = QEventLoop()
    worker.finished.connect(lambda r: (results.update(result=r), loop.quit()))
    worker.failed.connect(lambda msg, details: (results.update(error=(msg, details)), loop.quit()))

    worker.run()  # synchronous call is fine in a test -- no QThread needed
    if not results:
        loop.exec()

    assert "error" not in results, results.get("error")
    result = results["result"]
    assert result.output_size < result.original_size
    assert result.validation.passed


def test_compress_worker_reports_progress_not_fake_percentages(tmp_path, png_bytes):
    path = _make_pdf(tmp_path, png_bytes)
    out = str(tmp_path / "out.pdf")
    job = CompressJob(input_path=path, output_path=out, max_dpi=300, jpeg_quality=92, target_size_mb=None)
    worker = CompressWorker(job)

    progress_calls = []
    worker.progress.connect(lambda text, pct: progress_calls.append((text, pct)))
    worker.run()

    assert progress_calls  # something was reported
    # every percent value is either -1 (indeterminate) or a real 0-100 value
    assert all(pct == -1 or 0 <= pct <= 100 for _, pct in progress_calls)
