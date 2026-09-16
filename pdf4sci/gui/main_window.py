"""Main window: left sidebar (file info, settings, progress, results) and
a right-hand PDF viewer, mirroring the web UI's layout and workflow on top
of the same backend."""

from __future__ import annotations

import os
import shutil
import tempfile

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..analyzer import analyze_pdf
from ..config import DEFAULT_PRESET, PRESETS
from ..pdf_utils import human_size
from .pdf_view import PdfViewPanel
from .worker import CompressJob, CompressWorker


class DropArea(QFrame):
    """Click-to-browse + drag-and-drop target, styled like the web UI's."""

    def __init__(self, on_file, parent=None):
        super().__init__(parent)
        self._on_file = on_file
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("dropArea")
        self.setMinimumHeight(90)

        layout = QVBoxLayout(self)
        title = QLabel("Drop PDF here")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-weight: 600;")
        sub = QLabel("or click to browse")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: palette(placeholderText);")
        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addStretch(1)

    def mousePressEvent(self, event) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if path:
            self._on_file(path)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and any(
            u.toLocalFile().lower().endswith(".pdf") for u in event.mimeData().urls()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if local.lower().endswith(".pdf"):
                self._on_file(local)
                return


class QComboBoxNoWheel(QComboBox):
    """A QComboBox that ignores mouse-wheel events so scrolling the sidebar
    doesn't accidentally change the preset underneath the cursor."""

    def wheelEvent(self, event) -> None:
        event.ignore()


class MainWindow(QMainWindow):
    def __init__(self, initial_path: str | None = None):
        super().__init__()
        self.setWindowTitle("pdf4sci — Scientific PDF Optimizer")
        self.resize(1280, 850)
        self.setAcceptDrops(True)

        self._input_path: str | None = None
        self._compressed_path: str | None = None
        self._job_tmp_dir: str | None = None
        self._thread: QThread | None = None
        self._worker: CompressWorker | None = None

        self._build_ui()

        if initial_path:
            self.load_pdf(initial_path)

    # ---------------------------------------------------------------- UI

    def _build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar(), 0)

        self.viewer = PdfViewPanel()
        root.addWidget(self.viewer, 1)

        self.setCentralWidget(central)

    def _build_sidebar(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(340)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QLabel("pdf4sci")
        header.setStyleSheet("font-size: 18px; font-weight: 700;")
        subtitle = QLabel("Scientific PDF Optimizer")
        subtitle.setStyleSheet("color: palette(placeholderText);")
        layout.addWidget(header)
        layout.addWidget(subtitle)

        self.drop_area = DropArea(self.load_pdf)
        layout.addWidget(self.drop_area)

        self.file_name_label = QLabel()
        self.file_name_label.setStyleSheet("font-weight: 600;")
        self.file_meta_label = QLabel()
        self.file_meta_label.setStyleSheet("color: palette(placeholderText); font-size: 11px;")
        self.file_name_label.setVisible(False)
        self.file_meta_label.setVisible(False)
        layout.addWidget(self.file_name_label)
        layout.addWidget(self.file_meta_label)

        self.analysis_label = QLabel()
        self.analysis_label.setWordWrap(True)
        self.analysis_label.setStyleSheet(
            "background: palette(alternate-base); border-radius: 6px; padding: 8px; color: palette(placeholderText);"
        )
        self.analysis_label.setVisible(False)
        layout.addWidget(self.analysis_label)

        self.settings_widget = self._build_settings()
        self.settings_widget.setVisible(False)
        layout.addWidget(self.settings_widget)

        self.progress_label = QLabel()
        self.progress_bar = QProgressBar()
        self.progress_label.setVisible(False)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)

        self.result_widget = self._build_result()
        self.result_widget.setVisible(False)
        layout.addWidget(self.result_widget)

        self.load_another_btn = QPushButton("Load another PDF")
        self.load_another_btn.clicked.connect(self.reset_all)
        self.load_another_btn.setVisible(False)
        layout.addWidget(self.load_another_btn)

        layout.addStretch(1)
        scroll.setWidget(content)
        return scroll

    def _build_settings(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        form.setContentsMargins(0, 8, 0, 0)

        self.target_size_spin = QDoubleSpinBox()
        self.target_size_spin.setRange(0, 100000)
        self.target_size_spin.setDecimals(1)
        self.target_size_spin.setSingleStep(0.5)
        self.target_size_spin.setSpecialValueText("optional")
        self.target_size_spin.setSuffix(" MB")
        form.addRow("Target size", self.target_size_spin)

        self.preset_combo = QComboBoxNoWheel()
        self.preset_combo.addItems(list(PRESETS.keys()))
        self.preset_combo.setCurrentText(DEFAULT_PRESET)
        self.preset_combo.currentTextChanged.connect(self._apply_preset_defaults)
        form.addRow("Preset", self.preset_combo)

        self.advanced_toggle = QToolButton()
        self.advanced_toggle.setText("Advanced")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.advanced_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.advanced_toggle.toggled.connect(self._toggle_advanced)
        form.addRow(self.advanced_toggle)

        self.advanced_container = QWidget()
        self.advanced_container.setVisible(False)
        adv_form = QFormLayout(self.advanced_container)
        adv_form.setContentsMargins(0, 4, 0, 0)
        self.max_dpi_spin = QSpinBox()
        self.max_dpi_spin.setRange(50, 2000)
        self.max_dpi_spin.setSingleStep(10)
        self.jpeg_quality_spin = QSpinBox()
        self.jpeg_quality_spin.setRange(1, 100)
        adv_form.addRow("Maximum image DPI", self.max_dpi_spin)
        adv_form.addRow("Minimum JPEG quality", self.jpeg_quality_spin)
        form.addRow(self.advanced_container)

        self._apply_preset_defaults(DEFAULT_PRESET)

        self.compress_btn = QPushButton("Compress")
        self.compress_btn.setObjectName("primaryButton")
        self.compress_btn.clicked.connect(self._on_compress_clicked)
        form.addRow(self.compress_btn)

        return widget

    def _build_result(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)

        self.result_sizes_label = QLabel()
        self.result_sizes_label.setStyleSheet("font-size: 15px; font-weight: 700;")
        self.result_reduction_label = QLabel()
        self.result_reduction_label.setStyleSheet("color: #1a7f37; font-weight: 600;")
        layout.addWidget(self.result_sizes_label)
        layout.addWidget(self.result_reduction_label)

        self.result_warning_label = QLabel()
        self.result_warning_label.setStyleSheet("color: #b3261e;")
        self.result_warning_label.setWordWrap(True)
        self.result_warning_label.setVisible(False)
        layout.addWidget(self.result_warning_label)

        self.validation_label = QLabel()
        self.validation_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.validation_label)

        self.images_label = QLabel()
        self.images_label.setStyleSheet("color: palette(placeholderText); font-size: 12px;")
        layout.addWidget(self.images_label)

        toggle_row = QHBoxLayout()
        self.original_btn = QPushButton("Original")
        self.compressed_btn = QPushButton("Compressed")
        for b in (self.original_btn, self.compressed_btn):
            b.setCheckable(True)
        self.compressed_btn.setChecked(True)
        self.preview_group = QButtonGroup(self)
        self.preview_group.setExclusive(True)
        self.preview_group.addButton(self.original_btn)
        self.preview_group.addButton(self.compressed_btn)
        self.original_btn.clicked.connect(lambda: self._switch_preview("original"))
        self.compressed_btn.clicked.connect(lambda: self._switch_preview("compressed"))
        toggle_row.addWidget(self.original_btn)
        toggle_row.addWidget(self.compressed_btn)
        layout.addLayout(toggle_row)

        self.save_btn = QPushButton("Save compressed PDF")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._on_save_clicked)
        layout.addWidget(self.save_btn)

        return widget

    # ------------------------------------------------------------ actions

    def _apply_preset_defaults(self, name: str) -> None:
        preset = PRESETS.get(name)
        if preset is None:
            return
        self.max_dpi_spin.setValue(preset.max_dpi)
        self.jpeg_quality_spin.setValue(preset.jpeg_quality)

    def _toggle_advanced(self, checked: bool) -> None:
        self.advanced_container.setVisible(checked)
        self.advanced_toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and any(
            u.toLocalFile().lower().endswith(".pdf") for u in event.mimeData().urls()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if local.lower().endswith(".pdf"):
                self.load_pdf(local)
                return

    def load_pdf(self, path: str) -> None:
        if not path.lower().endswith(".pdf"):
            QMessageBox.warning(self, "Invalid file", "Please choose a PDF file.")
            return

        self.reset_all()

        try:
            analysis = analyze_pdf(path)
        except Exception:
            QMessageBox.critical(self, "Invalid PDF", "This does not look like a valid PDF file.")
            return

        self._input_path = path
        self._job_tmp_dir = tempfile.mkdtemp(prefix="pdf4sci-gui-")

        self.file_name_label.setText(os.path.basename(path))
        self.file_meta_label.setText(
            f"{human_size(analysis.file_size)} · {analysis.num_pages} page"
            f"{'s' if analysis.num_pages != 1 else ''}"
        )
        self.file_name_label.setVisible(True)
        self.file_meta_label.setVisible(True)

        n_downsample = sum(1 for i in analysis.images if i.recommendation == "downsample")
        n_keep = len(analysis.images) - n_downsample
        if analysis.images:
            self.analysis_label.setText(
                f"{len(analysis.images)} raster image{'s' if len(analysis.images) != 1 else ''} · "
                f"{n_downsample} oversized · {n_keep} already optimized"
            )
            self.analysis_label.setVisible(True)

        self.settings_widget.setVisible(True)
        self.load_another_btn.setVisible(True)

        self.viewer.load(path, fit_mode="width")

    def _on_compress_clicked(self) -> None:
        if not self._input_path or self._job_tmp_dir is None:
            return

        self.result_widget.setVisible(False)
        self.compress_btn.setEnabled(False)
        self.progress_label.setText("Starting…")
        self.progress_label.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)

        output_path = os.path.join(self._job_tmp_dir, "output.pdf")
        target_mb = self.target_size_spin.value()
        job = CompressJob(
            input_path=self._input_path,
            output_path=output_path,
            max_dpi=self.max_dpi_spin.value(),
            jpeg_quality=self.jpeg_quality_spin.value(),
            target_size_mb=target_mb if target_mb > 0 else None,
        )

        self._thread = QThread(self)
        self._worker = CompressWorker(job)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_compress_finished)
        self._worker.failed.connect(self._on_compress_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    def _on_progress(self, text: str, pct: int) -> None:
        self.progress_label.setText(text)
        if pct < 0:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(pct)

    def _on_thread_finished(self) -> None:
        self.compress_btn.setEnabled(True)
        self.progress_label.setVisible(False)
        self.progress_bar.setVisible(False)
        self._thread = None
        self._worker = None

    def _on_compress_finished(self, result) -> None:
        self._compressed_path = result.output_path

        self.result_sizes_label.setText(
            f"{human_size(result.original_size)} → {human_size(result.output_size)}"
        )
        reduction = (1 - result.output_size / result.original_size) * 100 if result.original_size else 0
        self.result_reduction_label.setText(f"{reduction:.1f}% smaller")

        if result.warning:
            self.result_warning_label.setText(result.warning)
            self.result_warning_label.setVisible(True)
        else:
            self.result_warning_label.setVisible(False)

        v = result.validation
        checks = [
            ("PDF valid", v.reopened_ok),
            ("Page count & dimensions preserved", v.page_count_match and v.page_dims_match),
            ("Text preserved", v.text_match),
            ("Links preserved", v.links_match),
            ("Images present", v.image_count_match),
            ("Transparency preserved", v.alpha_count_match),
            ("Vector content preserved", v.vector_count_match),
        ]
        def _row(label: str, ok: bool) -> str:
            color = "#1a7f37" if ok else "#b3261e"
            mark = "✓" if ok else "✗"
            return f"<span style='color:{color}'>{mark}</span> {label}"

        self.validation_label.setText("<br>".join(_row(label, ok) for label, ok in checks))

        self.images_label.setText(
            f"{result.images_optimized} image{'s' if result.images_optimized != 1 else ''} optimized, "
            f"{result.images_kept} unchanged"
        )

        self.compressed_btn.setChecked(True)
        self.result_widget.setVisible(True)

        state = self.viewer.current_state()
        self.viewer.load(
            self._compressed_path,
            page=state["page"],
            zoom_factor=state["zoom_factor"] if state["fit_mode"] is None else None,
            fit_mode=state["fit_mode"],
        )

    def _on_compress_failed(self, message: str, details: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("Compression failed")
        box.setText(message)
        box.setDetailedText(details)
        box.exec()

    def _switch_preview(self, variant: str) -> None:
        path = self._input_path if variant == "original" else self._compressed_path
        if not path:
            return
        state = self.viewer.current_state()
        self.viewer.load(
            path,
            page=state["page"],
            zoom_factor=state["zoom_factor"] if state["fit_mode"] is None else None,
            fit_mode=state["fit_mode"],
        )

    def _on_save_clicked(self) -> None:
        if not self._compressed_path or not self._input_path:
            return
        stem, ext = os.path.splitext(os.path.basename(self._input_path))
        suggested = f"{stem}_compressed{ext or '.pdf'}"
        chosen, _ = QFileDialog.getSaveFileName(self, "Save compressed PDF", suggested, "PDF Files (*.pdf)")
        if not chosen:
            return
        if os.path.abspath(chosen) == os.path.abspath(self._input_path):
            reply = QMessageBox.question(
                self,
                "Overwrite original?",
                "This will overwrite your original PDF. Are you sure?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        try:
            shutil.copy(self._compressed_path, chosen)
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", f"Could not save the file: {exc}")

    def reset_all(self) -> None:
        if self._job_tmp_dir and os.path.isdir(self._job_tmp_dir):
            shutil.rmtree(self._job_tmp_dir, ignore_errors=True)
        self._input_path = None
        self._compressed_path = None
        self._job_tmp_dir = None

        self.viewer.clear()
        self.file_name_label.setVisible(False)
        self.file_meta_label.setVisible(False)
        self.analysis_label.setVisible(False)
        self.settings_widget.setVisible(False)
        self.progress_label.setVisible(False)
        self.progress_bar.setVisible(False)
        self.result_widget.setVisible(False)
        self.load_another_btn.setVisible(False)
        self.target_size_spin.setValue(0)

    def closeEvent(self, event) -> None:
        if self._job_tmp_dir and os.path.isdir(self._job_tmp_dir):
            shutil.rmtree(self._job_tmp_dir, ignore_errors=True)
        super().closeEvent(event)
