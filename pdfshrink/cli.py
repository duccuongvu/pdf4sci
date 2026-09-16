"""Command-line interface."""

from __future__ import annotations

import os
import tempfile
from itertools import groupby

import typer

from .analyzer import PDFAnalysis, analyze_pdf
from .config import AnalyzerConfig
from .optimizer import OptimizationResult, optimize_pdf
from .pdf_utils import human_size

app = typer.Typer(add_completion=False, help="Target-size-aware PDF compressor for scientific papers.")


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
                f"[OPT ] p{r.page}/xref{r.xref} {bw}x{bh} -> {aw}x{ah}\n"
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


@app.command()
def main(
    input_pdf: str = typer.Argument(..., help="Path to the input PDF."),
    output: str = typer.Option(None, "-o", "--output", help="Output PDF path. Default: <input>_compressed.pdf"),
    analyze: bool = typer.Option(False, "--analyze", help="Print an analysis report and exit."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would change, without writing the output PDF."),
    max_dpi: int = typer.Option(300, "--max-dpi", help="Images at or below this effective DPI are kept untouched."),
    min_jpeg_quality: int = typer.Option(92, "--min-jpeg-quality", help="JPEG quality used when re-encoding photographic images."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Allow -o to point at the input file."),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed per-image decisions."),
) -> None:
    config = AnalyzerConfig(max_dpi=max_dpi)

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

    analysis = analyze_pdf(input_pdf, config)

    if dry_run:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_out = os.path.join(tmp, "preview.pdf")
            results = optimize_pdf(input_pdf, tmp_out, config, min_jpeg_quality, analysis=analysis)
            after_size = os.path.getsize(tmp_out)
        typer.echo("Planned changes (dry run, nothing written):\n")
        if verbose:
            typer.echo(_render_verbose_log(results))
            typer.echo("")
        typer.echo(_render_summary(results, analysis.file_size, after_size))
        raise typer.Exit(code=0)

    results = optimize_pdf(input_pdf, output_path, config, min_jpeg_quality, analysis=analysis)
    after_size = os.path.getsize(output_path)

    if verbose:
        typer.echo(_render_verbose_log(results))
        typer.echo("")
    typer.echo(_render_summary(results, analysis.file_size, after_size))
    typer.echo(f"\nWrote {output_path}")


if __name__ == "__main__":
    app()
