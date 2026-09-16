"""Synthetic PDF builders used across the test suite."""

from __future__ import annotations

import pymupdf
import pytest
from PIL import Image


def _png_bytes(width: int, height: int, mode: str = "RGB", color=(200, 50, 50)) -> bytes:
    import io

    img = Image.new(mode, (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def png_bytes():
    return _png_bytes


@pytest.fixture
def make_pdf(tmp_path):
    """Factory fixture: make_pdf(name, builder) writes a PDF built by
    `builder(doc)` to tmp_path/name and returns its path as a string."""

    def _make(name: str, builder) -> str:
        doc = pymupdf.open()
        builder(doc)
        path = tmp_path / name
        doc.save(str(path))
        doc.close()
        return str(path)

    return _make
