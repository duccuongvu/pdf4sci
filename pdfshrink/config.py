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
