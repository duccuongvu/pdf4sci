"""Compression policy configuration.

Kept separate from PDF manipulation code (analyzer.py, optimizer.py) so
presets and CLI flags only ever have to change values here.
"""

from dataclasses import dataclass


@dataclass
class AnalyzerConfig:
    """Thresholds used to decide whether an image is a compression candidate."""

    # Images whose effective DPI is at or below this are left untouched.
    max_dpi: int = 300


@dataclass(frozen=True)
class Preset:
    name: str
    max_dpi: int
    jpeg_quality: int
    description: str


# Ordered roughly from gentlest to most aggressive; also doubles as the
# rung order for the --target-size search ladder (see quality.py).
PRESETS: dict[str, Preset] = {
    "maximum-quality": Preset(
        "maximum-quality", max_dpi=400, jpeg_quality=95,
        description="Only touch clearly excessive images; highest fidelity.",
    ),
    "scientific": Preset(
        "scientific", max_dpi=300, jpeg_quality=92,
        description="Default. Preserves figure/text readability, targets print-quality DPI.",
    ),
    "balanced": Preset(
        "balanced", max_dpi=200, jpeg_quality=88,
        description="Noticeably smaller files; figures remain clear on screen.",
    ),
    "aggressive": Preset(
        "aggressive", max_dpi=150, jpeg_quality=80,
        description="Smallest files; visible quality loss on photos is expected.",
    ),
}

DEFAULT_PRESET = "scientific"
