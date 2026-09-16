"""Phase 3: target-size search.

`--target-size` asks for the highest-quality PDF that fits a size budget.
Rather than guessing one aggressive setting, this tries a ladder of
increasingly aggressive (max_dpi, jpeg_quality) configurations, gentlest
first, and stops at the first one that actually fits -- so a target that's
only slightly below the input size gets only a light touch, matching the
project's "optimize only what is wasteful" principle instead of always
reaching for the most aggressive preset.

Each rung re-runs the full analyzer + optimizer and checks the *real*
output file size (not an estimate), since target-size accuracy matters
more here than search speed.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

from .analyzer import analyze_pdf
from .config import AnalyzerConfig
from .optimizer import OptimizationResult, optimize_pdf

# Gentlest to most aggressive. Mirrors the example search space in the
# project spec: hold DPI while tightening JPEG quality first, then step
# DPI down and repeat.
DEFAULT_LADDER: list[tuple[int, int]] = [
    (400, 95),
    (300, 92),
    (300, 88),
    (250, 88),
    (200, 85),
    (150, 80),
    (100, 75),
]


def _ladder(min_jpeg_quality: int) -> list[tuple[int, int]]:
    steps = [s for s in DEFAULT_LADDER if s[1] >= min_jpeg_quality]
    if not steps:
        steps = [DEFAULT_LADDER[-1]]
    if steps[-1][1] != min_jpeg_quality:
        lowest_dpi = min(dpi for dpi, _ in DEFAULT_LADDER)
        steps.append((lowest_dpi, min_jpeg_quality))
    return steps


@dataclass
class TargetSizeResult:
    achieved: bool
    original_size: int
    final_size: int
    target_size: int
    max_dpi: int
    jpeg_quality: int
    steps_tried: int
    results: list[OptimizationResult]
    warning: str | None = None


def optimize_to_target_size(
    input_path: str,
    output_path: str,
    target_bytes: int,
    min_jpeg_quality: int = 75,
    on_step=None,
    on_progress=None,
) -> TargetSizeResult:
    """`on_step`, if given, is called as `on_step(step_index, total_steps,
    max_dpi, jpeg_quality)` before each search rung runs; `on_progress` is
    passed straight through to `optimize_pdf` for per-image progress within
    that rung. Both are for reporting real progress (e.g. a GUI), never
    required."""
    original_size = os.path.getsize(input_path)

    if target_bytes >= original_size:
        shutil.copy(input_path, output_path)
        return TargetSizeResult(
            achieved=True,
            original_size=original_size,
            final_size=original_size,
            target_size=target_bytes,
            max_dpi=0,
            jpeg_quality=0,
            steps_tried=0,
            results=[],
            warning="Input already fits the requested target size; left unmodified.",
        )

    steps = _ladder(min_jpeg_quality)
    last: TargetSizeResult | None = None
    for step_index, (dpi, quality) in enumerate(steps, start=1):
        if on_step is not None:
            on_step(step_index, len(steps), dpi, quality)
        config = AnalyzerConfig(max_dpi=dpi)
        analysis = analyze_pdf(input_path, config)
        results = optimize_pdf(
            input_path, output_path, config, jpeg_quality=quality, analysis=analysis, on_progress=on_progress
        )
        size = os.path.getsize(output_path)
        last = TargetSizeResult(
            achieved=size <= target_bytes,
            original_size=original_size,
            final_size=size,
            target_size=target_bytes,
            max_dpi=dpi,
            jpeg_quality=quality,
            steps_tried=step_index,
            results=results,
        )
        if last.achieved:
            return last

    last.warning = (
        f"Could not reach the requested {target_bytes / (1024*1024):.1f} MB target "
        f"without going below --min-jpeg-quality {min_jpeg_quality}. Closest achieved: "
        f"{last.final_size / (1024*1024):.2f} MB at max-dpi={last.max_dpi}, "
        f"jpeg-quality={last.jpeg_quality}."
    )
    return last
