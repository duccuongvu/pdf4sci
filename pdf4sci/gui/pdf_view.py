"""PDF viewer panel: Qt's own QPdfDocument/QPdfView (continuous multi-page
scrolling is built in), plus a toolbar matching the web UI's -- page nav,
fit width/page, zoom presets, and Ctrl+scroll/pinch to zoom. Rendering
here never modifies the underlying file.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QWheelEvent
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget

ZOOM_STEPS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0]


class _ZoomableView(QPdfView):
    """QPdfView with Ctrl+wheel (and trackpad pinch, reported as Ctrl+wheel)
    zoom; a plain wheel scrolls normally via the base class."""

    ctrlWheelZoom = Signal(float)  # multiplicative factor

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.0015**delta
            self.ctrlWheelZoom.emit(factor)
            event.accept()
            return
        super().wheelEvent(event)


class PdfViewPanel(QWidget):
    """Emits pageChanged(current, total) whenever the visible page or
    document changes, so the host window can keep a page indicator in
    sync without polling."""

    pageChanged = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.document = QPdfDocument(self)
        self.view = _ZoomableView(self)
        self.view.setDocument(self.document)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self._fit_mode = "width"
        self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.view.ctrlWheelZoom.connect(self._on_ctrl_wheel_zoom)
        self.view.pageNavigator().currentPageChanged.connect(self._on_page_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.view, 1)
        layout.addWidget(self._build_toolbar())

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(8, 6, 8, 6)

        self.prev_btn = QPushButton("‹")
        self.next_btn = QPushButton("›")
        self.prev_btn.setFixedWidth(30)
        self.next_btn.setFixedWidth(30)
        self.prev_btn.clicked.connect(self.previous_page)
        self.next_btn.clicked.connect(self.next_page)

        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(1)
        self.page_spin.valueChanged.connect(self._on_page_spin_changed)
        self.page_count_label = QLabel("/ 1")

        self.fit_width_btn = QPushButton("Fit Width")
        self.fit_page_btn = QPushButton("Fit Page")
        self.fit_width_btn.clicked.connect(lambda: self.set_fit_mode("width"))
        self.fit_page_btn.clicked.connect(lambda: self.set_fit_mode("page"))

        self.zoom_out_btn = QPushButton("−")
        self.zoom_in_btn = QPushButton("+")
        self.zoom_out_btn.setFixedWidth(28)
        self.zoom_in_btn.setFixedWidth(28)
        self.zoom_out_btn.clicked.connect(lambda: self._zoom_step(-1))
        self.zoom_in_btn.clicked.connect(lambda: self._zoom_step(1))
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(42)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for w in (
            self.prev_btn, QLabel("Page"), self.page_spin, self.page_count_label, self.next_btn,
        ):
            row.addWidget(w)
        row.addSpacing(12)
        row.addWidget(self.fit_width_btn)
        row.addWidget(self.fit_page_btn)
        row.addSpacing(12)
        row.addWidget(self.zoom_out_btn)
        row.addWidget(self.zoom_label)
        row.addWidget(self.zoom_in_btn)
        row.addStretch(1)
        return bar

    def load(self, path: str, page: int = 0, zoom_factor: float | None = None, fit_mode: str | None = None) -> None:
        self.document.load(path)
        count = max(self.document.pageCount(), 1)
        self.page_spin.blockSignals(True)
        self.page_spin.setMaximum(count)
        self.page_spin.blockSignals(False)
        self.page_count_label.setText(f"/ {count}")

        if fit_mode is not None:
            self.set_fit_mode(fit_mode, _render=False)
        if zoom_factor is not None and fit_mode is None:
            self.view.setZoomMode(QPdfView.ZoomMode.Custom)
            self.view.setZoomFactor(zoom_factor)
            self._fit_mode = None

        target_page = max(0, min(page, count - 1))
        self.view.pageNavigator().jump(target_page, QPointF(0, 0))
        self._update_zoom_label()
        self.pageChanged.emit(target_page + 1, count)

    def current_state(self) -> dict:
        return {
            "page": self.view.pageNavigator().currentPage(),
            "zoom_factor": self.view.zoomFactor(),
            "fit_mode": self._fit_mode,
        }

    def clear(self) -> None:
        self.document.close()
        self.page_spin.blockSignals(True)
        self.page_spin.setMaximum(1)
        self.page_spin.blockSignals(False)
        self.page_count_label.setText("/ 1")

    def previous_page(self) -> None:
        nav = self.view.pageNavigator()
        if nav.currentPage() > 0:
            nav.jump(nav.currentPage() - 1, QPointF(0, 0))

    def next_page(self) -> None:
        nav = self.view.pageNavigator()
        if nav.currentPage() < self.document.pageCount() - 1:
            nav.jump(nav.currentPage() + 1, QPointF(0, 0))

    def set_fit_mode(self, mode: str, _render: bool = True) -> None:
        self._fit_mode = mode
        if mode == "width":
            self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        elif mode == "page":
            self.view.setZoomMode(QPdfView.ZoomMode.FitInView)
        if _render:
            self._update_zoom_label()

    def _zoom_step(self, direction: int) -> None:
        current = self.view.zoomFactor()
        idx = next((i for i, z in enumerate(ZOOM_STEPS) if z >= current - 0.001), len(ZOOM_STEPS) - 1)
        idx = max(0, min(len(ZOOM_STEPS) - 1, idx + direction))
        self._set_zoom(ZOOM_STEPS[idx])

    def _set_zoom(self, factor: float) -> None:
        factor = max(0.1, min(10.0, factor))
        self._fit_mode = None
        self.view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.view.setZoomFactor(factor)
        self._update_zoom_label()

    def _on_ctrl_wheel_zoom(self, factor: float) -> None:
        self._set_zoom(self.view.zoomFactor() * factor)

    def _on_page_spin_changed(self, value: int) -> None:
        nav = self.view.pageNavigator()
        if value - 1 != nav.currentPage():
            nav.jump(value - 1, QPointF(0, 0))

    def _on_page_changed(self, page: int) -> None:
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(page + 1)
        self.page_spin.blockSignals(False)
        self.pageChanged.emit(page + 1, self.document.pageCount())

    def _update_zoom_label(self) -> None:
        self.zoom_label.setText(f"{round(self.view.zoomFactor() * 100)}%")
