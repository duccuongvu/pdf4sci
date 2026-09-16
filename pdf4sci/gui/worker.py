"""Background compression worker.

Runs on a QThread so the UI thread never blocks on compression. Calls the
same analyzer/optimizer/quality/validation functions the CLI and web UI
use; the only GUI-specific addition is wiring their optional progress
callbacks to Qt signals.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from ..analyzer import analyze_pdf
from ..config import AnalyzerConfig
from ..optimizer import optimize_pdf
from ..quality import optimize_to_target_size
from ..validation import validate


@dataclass
class CompressJob:
    input_path: str
    output_path: str
    max_dpi: int
    jpeg_quality: int
    target_size_mb: float | None  # None or <= 0 means "no target, use preset settings"


class CompressWorker(QObject):
    # Real progress only: a status string, and either a 0-100 percent or -1
    # for "can't compute a percentage, but here's what's happening."
    progress = Signal(str, int)
    finished = Signal(object)  # CompressWorkerResult
    failed = Signal(str, str)  # user-facing message, full traceback for "Show Details"

    def __init__(self, job: CompressJob):
        super().__init__()
        self.job = job

    def run(self) -> None:
        job = self.job
        try:
            self.progress.emit("Analyzing…", -1)
            original_size_before = _file_size(job.input_path)

            if job.target_size_mb and job.target_size_mb > 0:
                target_bytes = int(job.target_size_mb * 1024 * 1024)

                def on_step(step_index, total_steps, dpi, quality):
                    self.progress.emit(
                        f"Trying max-dpi={dpi}, jpeg-quality={quality} "
                        f"(attempt {step_index}/{total_steps})…",
                        -1,
                    )

                def on_progress(done, total, img):
                    pct = int(done / total * 100) if total else -1
                    self.progress.emit(f"Optimizing image {done + 1} / {total}…", pct)

                result = optimize_to_target_size(
                    job.input_path,
                    job.output_path,
                    target_bytes,
                    min_jpeg_quality=job.jpeg_quality,
                    on_step=on_step,
                    on_progress=on_progress,
                )
                opt_results = result.results
                warning = result.warning
            else:
                config = AnalyzerConfig(max_dpi=job.max_dpi)
                analysis = analyze_pdf(job.input_path, config)

                def on_progress(done, total, img):
                    pct = int(done / total * 100) if total else -1
                    self.progress.emit(f"Optimizing image {done + 1} / {total}…", pct)

                opt_results = optimize_pdf(
                    job.input_path,
                    job.output_path,
                    config,
                    jpeg_quality=job.jpeg_quality,
                    analysis=analysis,
                    on_progress=on_progress,
                )
                warning = None

            self.progress.emit("Validating…", -1)
            report = validate(job.input_path, job.output_path)
            output_size = _file_size(job.output_path)

            self.finished.emit(
                CompressWorkerResult(
                    original_size=original_size_before,
                    output_size=output_size,
                    warning=warning,
                    images_optimized=sum(1 for r in opt_results if r.action == "optimized"),
                    images_kept=sum(1 for r in opt_results if r.action != "optimized"),
                    validation=report,
                    output_path=job.output_path,
                )
            )
        except Exception as exc:
            self.failed.emit(
                "Could not compress this PDF. It may use an image format this tool "
                "cannot safely optimize. The original file was not modified.",
                f"{exc}\n\n{traceback.format_exc()}",
            )


@dataclass
class CompressWorkerResult:
    original_size: int
    output_size: int
    warning: str | None
    images_optimized: int
    images_kept: int
    validation: object  # validation.ValidationReport
    output_path: str


def _file_size(path: str) -> int:
    import os

    return os.path.getsize(path)
