"""Command-line interface."""

from __future__ import annotations

import os
import sys
import tempfile
from itertools import groupby

import typer

from .analyzer import PDFAnalysis, analyze_pdf
from .config import PRESETS, AnalyzerConfig, DEFAULT_PRESET
from .optimizer import OptimizationResult, optimize_pdf
from .pdf_utils import human_size, parse_size
from .quality import TargetSizeResult, optimize_to_target_size
from .validation import ValidationReport, validate

app = typer.Typer(add_completion=False, help="Target-size-aware PDF compressor for scientific papers.")
benchmark_app = typer.Typer(add_completion=False, help="Run several presets and compare sizes.")


def _render_report(analysis: PDFAnalysis) -> str:
    lines: list[str] = []
    lines.append(f"Input: {analysis.path}")
    lines.append(f"Size: {human_size(analysis.file_size)}")
    lines.append(f"Pages: {analysis.num_pages}")
    lines.append("")

    for page, group in groupby(analysis.images, key=lambda i: i.page):
        lines.append(f"Page {page}:")
        for img in group:
            lines.append(f"  Image #{img.xref}")
            lines.append(f"  {img.width} x {img.height} px")
            lines.append(
                f"  Display size: {img.display_width_in:.1f} x {img.display_height_in:.1f} in"
            )
            lines.append(f"  Effective resolution: ~{img.effective_dpi:.0f} DPI")
            lines.append(f"  Embedded size: {human_size(img.compressed_size)}")
            lines.append(f"  Format: {img.format}")
            if img.has_alpha:
                lines.append("  Transparency: yes")
            if img.is_reused:
                lines.append(f"  Reused: {img.total_occurrences} placements")
            lines.append(f"  Recommendation: {img.recommendation} ({img.reason})")
            lines.append("")

    if not analysis.images:
        lines.append("No raster images found.")
        lines.append("")

    pct_images = (
        analysis.image_bytes_total / analysis.file_size * 100 if analysis.file_size else 0
    )
    lines.append("Summary:")
    lines.append(
        f"  Raster images: {human_size(analysis.image_bytes_total)} ({pct_images:.1f}% of file)"
    )
    lines.append(f"  Other content (text/fonts/vectors/structure): {human_size(analysis.other_bytes_total)}")
    n_downsample = sum(1 for i in analysis.images if i.recommendation == "downsample")
    n_keep = len(analysis.images) - n_downsample
    lines.append(f"  Images to keep: {n_keep}")
    lines.append(f"  Images flagged for downsampling: {n_downsample}")

    return "\n".join(lines)


def _default_output_path(input_pdf: str) -> str:
    stem, ext = os.path.splitext(input_pdf)
    return f"{stem}_compressed{ext or '.pdf'}"


def _render_verbose_log(results: list[OptimizationResult]) -> str:
    lines = []
    for r in results:
        if r.action == "kept":
            lines.append(f"[KEEP] p{r.page}/xref{r.xref} {r.reason}")
        elif r.action == "skipped":
            lines.append(f"[SKIP] p{r.page}/xref{r.xref} {r.reason}")
        else:
            bw, bh = r.before_dims
            aw, ah = r.after_dims
            lines.append(
                f"[OPT ] p{r.page}/xref{r.xref} {bw}x{bh} -> {aw}x{ah}  ({r.category})\n"
                f"        {human_size(r.before_bytes)} -> {human_size(r.after_bytes)}"
            )
    return "\n".join(lines)


def _render_summary(results: list[OptimizationResult], before_size: int, after_size: int) -> str:
    n_optimized = sum(1 for r in results if r.action == "optimized")
    n_kept = sum(1 for r in results if r.action == "kept")
    n_skipped = sum(1 for r in results if r.action == "skipped")
    reduction = (1 - after_size / before_size) * 100 if before_size else 0
    lines = [
        f"Original: {human_size(before_size)}",
        f"Output:   {human_size(after_size)}",
        f"Reduction: {reduction:.1f}%",
        "",
        f"Raster images optimized: {n_optimized}",
        f"Raster images preserved: {n_kept}",
        f"Raster images skipped (unsafe to modify): {n_skipped}",
    ]
    return "\n".join(lines)


def _render_target_size_summary(result: TargetSizeResult) -> str:
    lines = [
        f"Original: {human_size(result.original_size)}",
        f"Output:   {human_size(result.final_size)}",
    ]
    if result.original_size:
        reduction = (1 - result.final_size / result.original_size) * 100
        lines.append(f"Reduction: {reduction:.1f}%")
    status = "reached" if result.achieved and not result.warning else "NOT reached"
    lines.append(f"Target:   {human_size(result.target_size)} ({status})")
    if result.steps_tried:
        lines.append(
            f"Settings used: max-dpi={result.max_dpi}, jpeg-quality={result.jpeg_quality} "
            f"(search step {result.steps_tried})"
        )
    if result.results:
        n_optimized = sum(1 for r in result.results if r.action == "optimized")
        n_kept = sum(1 for r in result.results if r.action == "kept")
        n_skipped = sum(1 for r in result.results if r.action == "skipped")
        lines += [
            "",
            f"Raster images optimized: {n_optimized}",
            f"Raster images preserved: {n_kept}",
            f"Raster images skipped (unsafe to modify): {n_skipped}",
        ]
    if result.warning:
        lines += ["", f"WARNING: {result.warning}"]
    return "\n".join(lines)


def _render_validation(report: ValidationReport) -> str:
    def status(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    lines = [
        "",
        f"PDF reopen test: {status(report.reopened_ok)}",
    ]
    if report.reopened_ok:
        lines += [
            f"Page count/dimensions: {status(report.page_count_match and report.page_dims_match)}",
            f"Text extraction: {status(report.text_match)}",
            f"Links/annotations: {status(report.links_match)}",
            f"Images present: {status(report.image_count_match)}",
            f"Transparency preserved: {status(report.alpha_count_match)}",
            f"Vector content untouched: {status(report.vector_count_match)}",
        ]
    if report.issues:
        lines.append("")
        lines.append("Validation issues:")
        for issue in report.issues:
            lines.append(f"  - {issue}")
    if report.diagnostics:
        lines.append("")
        lines.append("Diagnostics (informational only, not optimized for):")
        for d in report.diagnostics:
            psnr_s = f"{d.psnr:.1f} dB" if d.psnr is not None else "n/a"
            ssim_s = f"{d.ssim:.3f}" if d.ssim is not None else "n/a"
            lines.append(f"  page {d.page}: PSNR={psnr_s}  SSIM={ssim_s}")
    return "\n".join(lines)


@app.command()
def main(
    input_pdf: str = typer.Argument(..., help="Path to the input PDF."),
    output: str = typer.Option(None, "-o", "--output", help="Output PDF path. Default: <input>_compressed.pdf"),
    analyze: bool = typer.Option(False, "--analyze", help="Print an analysis report and exit."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would change, without writing the output PDF."),
    target_size: str = typer.Option(
        None, "--target-size", help="Target output size, e.g. 6MB. Tries presets gentlest-first until one fits."
    ),
    preset: str = typer.Option(
        DEFAULT_PRESET, "--preset", help=f"One of: {', '.join(PRESETS)}. Default: {DEFAULT_PRESET}."
    ),
    max_dpi: int = typer.Option(None, "--max-dpi", help="Override the preset's DPI threshold."),
    min_jpeg_quality: int = typer.Option(
        None, "--min-jpeg-quality", help="Override the preset's JPEG quality (also the floor for --target-size search)."
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Allow -o to point at the input file."),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed per-image decisions."),
    validate_output: bool = typer.Option(
        True, "--validate/--no-validate", help="Verify the output PDF (reopen, text, links, vectors, transparency)."
    ),
    diagnostics: bool = typer.Option(
        False, "--diagnostics", help="Also compute per-page PSNR/SSIM (slower; informational only)."
    ),
) -> None:
    if preset not in PRESETS:
        typer.echo(f"Unknown preset {preset!r}. Choose from: {', '.join(PRESETS)}.", err=True)
        raise typer.Exit(code=1)
    preset_cfg = PRESETS[preset]
    effective_max_dpi = max_dpi if max_dpi is not None else preset_cfg.max_dpi
    effective_jpeg_quality = min_jpeg_quality if min_jpeg_quality is not None else preset_cfg.jpeg_quality
    config = AnalyzerConfig(max_dpi=effective_max_dpi)

    if analyze:
        analysis = analyze_pdf(input_pdf, config)
        typer.echo(_render_report(analysis))
        raise typer.Exit(code=0)

    output_path = output or _default_output_path(input_pdf)
    if os.path.abspath(output_path) == os.path.abspath(input_pdf) and not overwrite:
        typer.echo(
            f"Refusing to overwrite {input_pdf!r}. Pass --overwrite if you really "
            "want -o to point at the input file.",
            err=True,
        )
        raise typer.Exit(code=1)

    if target_size is not None:
        target_bytes = parse_size(target_size)
        with tempfile.TemporaryDirectory() as tmp:
            write_path = os.path.join(tmp, "preview.pdf") if dry_run else output_path
            result = optimize_to_target_size(
                input_pdf, write_path, target_bytes, min_jpeg_quality=effective_jpeg_quality
            )
            if dry_run:
                typer.echo("Planned changes (dry run, nothing written):\n")
            if verbose:
                typer.echo(_render_verbose_log(result.results))
                typer.echo("")
            typer.echo(_render_target_size_summary(result))
            if not dry_run and validate_output:
                report = validate(input_pdf, output_path, with_diagnostics=diagnostics)
                typer.echo(_render_validation(report))
        if not dry_run:
            typer.echo(f"\nWrote {output_path}")
        raise typer.Exit(code=0)

    analysis = analyze_pdf(input_pdf, config)

    if dry_run:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_out = os.path.join(tmp, "preview.pdf")
            results = optimize_pdf(input_pdf, tmp_out, config, effective_jpeg_quality, analysis=analysis)
            after_size = os.path.getsize(tmp_out)
        typer.echo("Planned changes (dry run, nothing written):\n")
        if verbose:
            typer.echo(_render_verbose_log(results))
            typer.echo("")
        typer.echo(_render_summary(results, analysis.file_size, after_size))
        raise typer.Exit(code=0)

    results = optimize_pdf(input_pdf, output_path, config, effective_jpeg_quality, analysis=analysis)
    after_size = os.path.getsize(output_path)

    if verbose:
        typer.echo(_render_verbose_log(results))
        typer.echo("")
    typer.echo(_render_summary(results, analysis.file_size, after_size))
    if validate_output:
        report = validate(input_pdf, output_path, with_diagnostics=diagnostics)
        typer.echo(_render_validation(report))
    typer.echo(f"\nWrote {output_path}")


@benchmark_app.command()
def benchmark(
    input_pdf: str = typer.Argument(..., help="Path to the input PDF."),
    output_dir: str = typer.Option(
        None, "--output-dir", help="Persist each preset's compressed PDF here. Default: discard after measuring."
    ),
) -> None:
    """Run every preset and report size/reduction, without necessarily
    keeping the intermediate PDFs."""
    original_size = os.path.getsize(input_pdf)
    rows = [("Original", original_size, None)]

    for name, preset_cfg in PRESETS.items():
        cfg = AnalyzerConfig(max_dpi=preset_cfg.max_dpi)
        with tempfile.TemporaryDirectory() as tmp:
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                stem = os.path.splitext(os.path.basename(input_pdf))[0]
                out_path = os.path.join(output_dir, f"{stem}_{name}.pdf")
            else:
                out_path = os.path.join(tmp, f"{name}.pdf")
            optimize_pdf(input_pdf, out_path, cfg, jpeg_quality=preset_cfg.jpeg_quality)
            size = os.path.getsize(out_path)
        reduction = (1 - size / original_size) * 100 if original_size else 0
        rows.append((name, size, reduction))

    header = f"{'Configuration':<20}{'Size':>12}{'Reduction':>12}"
    typer.echo(header)
    typer.echo("-" * len(header))
    for name, size, reduction in rows:
        red_str = "-" if reduction is None else f"{reduction:.0f}%"
        typer.echo(f"{name:<20}{human_size(size):>12}{red_str:>12}")


def entry() -> None:
    """Dispatches to the `benchmark` subcommand or the default compress
    command, so `pdf4sci paper.pdf` works without naming a subcommand
    while `pdf4sci benchmark paper.pdf` still does."""
    if len(sys.argv) > 1 and sys.argv[1] == "benchmark":
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        benchmark_app()
    else:
        app()


if __name__ == "__main__":
    entry()
