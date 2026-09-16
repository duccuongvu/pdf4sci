"""Bundled icon assets, generated from the project logo."""

import os

_ICONS_DIR = os.path.join(os.path.dirname(__file__), "icons")

ICON_SIZES = (16, 32, 48, 64, 128, 256, 512)


def icon_path(size: int = 256) -> str:
    """Path to the bundled PNG icon closest to `size` pixels square."""
    closest = min(ICON_SIZES, key=lambda s: abs(s - size))
    return os.path.join(_ICONS_DIR, f"{closest}.png")
