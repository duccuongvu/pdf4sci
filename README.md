# pdfshrink

A PDF compressor for scientific papers that targets a **user-defined file
size** while preserving text, embedded fonts, equations, vector graphics,
and line-art plots as vector content. It does not rasterize pages, and it
does not apply one global lossy preset to everything in the file.

Generic tools (Ghostscript's `-dPDFSETTINGS`, most "compress PDF" web tools)
either rasterize whole pages or apply the same JPEG quality to every image
regardless of whether that image is a 6000×4000 photo displayed at 3 inches
or a small icon that's already efficient. `pdfshrink` instead looks at each
embedded raster image individually — its pixel dimensions, how large it's
actually displayed on the page (its *effective DPI*), and its content type —
and only touches images that are actually oversized for how they're used.

## Project status

This project is being built in phases (see `instruction.md`). Currently
implemented:

- **Phase 1 — analyzer**: `pdfshrink <file> --analyze` reports, per image,
  its pixel dimensions, displayed size, effective DPI, embedded size,
  format, transparency, reuse across the document, and a keep/downsample
  recommendation. It also reports what fraction of the file's bytes are
  raster images vs. everything else (text, fonts, vector content,
  structure).

Compression itself (actually rewriting the PDF) is not implemented yet —
that's Phase 2 onward.

## Installation (Ubuntu 22.04+)

No root privileges are required for the Python side. A conda environment is
used here because `python3-venv` requires `sudo apt install` on a fresh
system; if your system's `python3-venv` is already installed, a plain `venv`
works identically.

```bash
# Using conda (recommended if python3-venv isn't installed / you can't sudo)
conda create -n pdfshrink python=3.10 -y
conda activate pdfshrink

# Or, if python3-venv is available:
# python3 -m venv .venv && source .venv/bin/activate

pip install -e ".[dev]"
```

### Optional native backends

These are optional, used later (Phase 2+) as backends for lossless PNG
optimization and PDF structure cleanup. They are not required for the
analyzer.

```bash
conda install -c conda-forge qpdf oxipng
```

(`gs`/Ghostscript, if you want it available too, is usually already present
on Ubuntu or installable via `sudo apt install ghostscript`.)

## Usage

```bash
# Analyze a PDF: report every raster image, its effective DPI, and whether
# it's a compression candidate. Makes no changes to the file.
pdfshrink paper.pdf --analyze

# Change the DPI threshold used for the keep/downsample recommendation
# (default: 300, appropriate for print-quality scientific figures).
pdfshrink paper.pdf --analyze --max-dpi 250
```

Example output:

```text
Input: paper.pdf
Size: 12.2 MB
Pages: 8

Page 5:
  Image #295
  6150 x 1638 px
  Display size: 3.5 x 0.9 in
  Effective resolution: ~1771 DPI
  Embedded size: 1.7 MB
  Format: Flate
  Recommendation: downsample (1771 DPI exceeds 300 DPI threshold)

...

Summary:
  Raster images: 10.4 MB (85.3% of file)
  Other content (text/fonts/vectors/structure): 1.8 MB
  Images to keep: 1
  Images flagged for downsampling: 26
```

## Architecture

```text
pdfshrink/
    __init__.py
    cli.py        — Typer CLI, report formatting
    analyzer.py   — reads a PDF, computes per-image effective DPI and a
                    keep/downsample recommendation (no writes)
    config.py     — compression policy thresholds, kept separate from
                    the PDF-manipulation code
    pdf_utils.py  — stateless helpers: size formatting, colorspace/filter
                    name normalization

tests/
    conftest.py       — synthetic PDF builders (in-memory, via PyMuPDF)
    test_analyzer.py
```

Future phases add `optimizer.py` (image replacement / downsampling),
`classifier.py` (photo vs. plot vs. icon heuristics), `quality.py`
(target-size search), and `validation.py` (post-compression checks),
without changing this layout.

## Limitations (current phase)

- Analysis only — no PDF is written yet.
- Effective DPI is computed from each image's axis-aligned placement
  rectangle on the page; extreme rotations/skews are an approximation.
- Image classification (photo vs. plot vs. icon) is not implemented yet;
  the current recommendation is DPI-threshold-only.
