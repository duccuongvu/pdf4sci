"""Entry point for the native desktop GUI: `pdf4sci-gui [file.pdf]`."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("pdf4sci")
    app.setOrganizationName("pdf4sci")

    initial_path = sys.argv[1] if len(sys.argv) > 1 else None
    window = MainWindow(initial_path=initial_path)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
