"""Command-line interface."""

from __future__ import annotations

from itertools import groupby

import typer

from .analyzer import PDFAnalysis, analyze_pdf
from .config import AnalyzerConfig
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


@app.command()
def main(
    input_pdf: str = typer.Argument(..., help="Path to the input PDF."),
    output: str = typer.Option(None, "-o", "--output", help="Output PDF path."),
    analyze: bool = typer.Option(False, "--analyze", help="Print an analysis report and exit."),
    max_dpi: int = typer.Option(300, "--max-dpi", help="Images at or below this effective DPI are kept untouched."),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed per-image decisions."),
) -> None:
    config = AnalyzerConfig(max_dpi=max_dpi)

    if analyze:
        analysis = analyze_pdf(input_pdf, config)
        typer.echo(_render_report(analysis))
        raise typer.Exit(code=0)

    typer.echo(
        "Compression is not implemented yet (Phase 1: analyzer only). "
        "Run with --analyze to see the image report."
    )
    raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
