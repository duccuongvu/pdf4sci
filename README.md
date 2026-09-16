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
- **Phase 2 — safe optimization**: `pdfshrink <file>` downsamples every
  image the analyzer flagged as exceeding `--max-dpi` and re-encodes it
  (lossless for anything with transparency or already lossless, JPEG for
  already-JPEG photos), leaving everything else in the PDF untouched. On
  the provided real-world test papers this gets 65–80% size reduction with
  identical text extraction, page count, and page dimensions. An image is
  only ever replaced if the re-encoded version is actually smaller; images
  that can't be safely round-tripped (CMYK, color-key/stencil masks) are
  left untouched and reported as skipped rather than risking corruption.
- **Phase 3 — classification, target size, presets**: a cheap heuristic
  classifier (entropy, color count, edge density, dimensions — no ML)
  distinguishes photos from plots/diagrams/screenshots/icons and drives the
  JPEG-vs-lossless choice by actual content instead of original format —
  on the test papers this alone took reduction from ~66-81% to ~74-84% by
  correctly routing genuine photos to JPEG. `--target-size` searches a
  gentlest-first ladder of (DPI, JPEG quality) settings and stops at the
  first one that actually fits the requested size, so a modest target
  doesn't trigger maximum-aggressiveness compression. `--preset
  {maximum-quality,scientific,balanced,aggressive}` selects a starting
  point on that same ladder; `scientific` is the default.
- **Phase 4 — validation & benchmarking**: every compress run now reopens
  the output and checks page count/dimensions, text extraction, link
  counts, image counts, transparency, and vector-content preservation
  (each pass/fail), reported right after the size summary — pass
  `--no-validate` to skip it, or `--diagnostics` to also render each page
  and report PSNR/SSIM (informational only; this tool does not optimize
  for them). `pdfshrink benchmark paper.pdf` runs all four presets and
  prints a size/reduction table without permanently writing the
  intermediate PDFs (add `--output-dir` to keep them).

All four backend phases from `instruction.md` are now implemented end to
end. A web UI (`pdfshrink-web`) has also been added on top, per
`WEBAPP_GUI_INSTRUCTION.md` — see below. (`GUI_INSTRUCTION.md`, a separate
native-desktop/PySide6 spec, has not been started.)

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

pip install -e ".[dev]"   # installs Flask too, for the web UI and its tests
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

# Compress: downsample oversized images, write paper_compressed.pdf.
# The original is never overwritten unless -o points at it AND --overwrite
# is also passed.
pdfshrink paper.pdf

# See exactly what would change, without writing anything.
pdfshrink paper.pdf --dry-run --verbose

# Change the DPI threshold used for the keep/downsample decision
# (default: 300, appropriate for print-quality scientific figures).
pdfshrink paper.pdf --max-dpi 250

# Custom output path, and the JPEG quality floor for photographic images.
pdfshrink paper.pdf -o out.pdf --min-jpeg-quality 90

# Fit a size budget: tries settings gentlest-first, stops at the first
# that fits. Warns (without crashing or destroying quality) if the ladder
# is exhausted before reaching the target.
pdfshrink paper.pdf --target-size 6MB

# Presets bundle a --max-dpi/--min-jpeg-quality pair. Explicit flags
# override whatever the preset sets.
pdfshrink paper.pdf --preset aggressive

# Skip the post-compression validation checks (they run by default), or
# add slower per-page PSNR/SSIM diagnostics on top of them.
pdfshrink paper.pdf --no-validate
pdfshrink paper.pdf --diagnostics

# Compare all four presets' size/reduction without keeping the outputs.
pdfshrink benchmark paper.pdf
# ...or keep them:
pdfshrink benchmark paper.pdf --output-dir ./benchmark-out
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

A compress run's output ends with the validation block:

```text
PDF reopen test: PASS
Page count/dimensions: PASS
Text extraction: PASS
Links/annotations: PASS
Images present: PASS
Transparency preserved: PASS
Vector content untouched: PASS
```

## Web UI

A two-column web interface: a left sidebar with everything (file info,
analysis, target size/preset, advanced settings, progress, results), and
a right-hand pane dominated by an in-browser PDF viewer (PDF.js, vendored
locally under `static/pdfjs/` — no CDN dependency at runtime). It calls
the same `analyzer`/`optimizer`/`quality`/`validation` functions the CLI
uses — no subprocess, no separate compression logic.

```bash
pdfshrink-web
# then open http://127.0.0.1:5000
```

Workflow: drop a PDF and it renders immediately in the viewer (page
navigation, zoom presets, fit-width/fit-page) → set a target size or
preset → Compress → the viewer automatically switches to the compressed
result, with a small Original/Compressed toggle in the sidebar that
preserves the current page and zoom when you switch — so you can zoom
into a figure and flip back and forth to check it stayed sharp. There is
only one viewer instance; toggling swaps which PDF it's showing rather
than maintaining two side-by-side panels. The result also shows
before/after size, reduction %, and the same pass/fail validation
checklist as the CLI.

This runs Flask's built-in development server, which is fine for local
use on your own machine; it is not hardened for exposing to a network.

## Architecture

```text
pdfshrink/
    __init__.py
    cli.py        — Typer CLI, report formatting
    analyzer.py   — reads a PDF, computes per-image effective DPI and a
                    keep/downsample recommendation (no writes)
    optimizer.py  — orchestrates replacing flagged images: plan a
                    candidate re-encode, only commit it if smaller
    images.py     — per-image codec mechanics: decode (incl. soft masks),
                    resize, encode (JPEG / Flate with the PNG-predictor
                    trick), and write the result into a pikepdf object
    classifier.py — cheap heuristic content classification (photo /
                    screenshot / plot / icon), no ML
    quality.py    — --target-size search: try (DPI, JPEG quality) rungs
                    gentlest-first, stop at the first that fits
    validation.py — post-compression checks (reopen, text, links, vector
                    content, transparency) plus optional PSNR/SSIM
    config.py     — compression policy thresholds and presets, kept
                    separate from the PDF-manipulation code
    pdf_utils.py  — stateless helpers: size formatting, colorspace/filter
                    name normalization, size string parsing

    web/
        app.py        — Flask routes: upload / compress / download,
                        calling the backend functions above directly
        storage.py    — per-job temp-file handling, keyed by an opaque
                        uuid4 token (no path-traversal surface)
        templates/index.html
        static/style.css
        static/app.js        — sidebar workflow: upload, settings,
                                compress, results, Original/Compressed
                                toggle
        static/pdf-viewer.js — thin wrapper around PDF.js: one canvas,
                                page nav, zoom/fit; owns no object URLs
                                (app.js keeps both Original and
                                Compressed alive for instant toggling)
        static/pdfjs/         — vendored PDF.js (pdf.min.js +
                                pdf.worker.min.js), no CDN at runtime

tests/
    conftest.py       — synthetic PDF builders (in-memory, via PyMuPDF)
    test_analyzer.py
    test_optimizer.py
    test_classifier.py
    test_quality.py
    test_validation.py
    test_integration.py — one PDF combining vector graphics, text, a
                           photo, transparency, a repeated image, a
                           grayscale image, and a rotated/scaled image
    test_web.py          — Flask test-client coverage of upload/compress/
                            download and their error paths
```

The `benchmark` command lives in `cli.py` as a second Typer app; `entry()`
dispatches to it or to the default compress command based on argv, so
`pdfshrink paper.pdf` and `pdfshrink benchmark paper.pdf` both work
without one shadowing the other.

## Limitations (current phase)

- Effective DPI, and therefore the downsampling decision, is computed from
  each image's axis-aligned placement rectangle on the page; extreme
  rotations/skews are an approximation.
- CMYK images and images using a color-key or stencil `/Mask` (as opposed
  to a soft mask, `/SMask`, which is handled) are left untouched rather
  than risk a color or transparency error — reported as "skipped".
- Re-encoding drops any embedded ICC profile (images are decoded to
  DeviceGray/DeviceRGB); for typical scientific-paper figures this has no
  visible effect, but wide-gamut photographic color accuracy isn't
  preserved.
- The photo/plot/screenshot/icon classifier is a heuristic (entropy, color
  count, edge density, dimensions) calibrated against the project's real
  test PDFs, not a learned model — it can misclassify unusual content
  (e.g. a very low-contrast photo), in which case the fallback is the
  lossless path, which never destroys quality, just doesn't compress as
  hard as JPEG would have.
- `--target-size` re-runs the full analyzer + optimizer per rung tried, so
  it can take several times as long as a single-preset run on a
  many-image PDF; it always uses the real output file size to decide
  whether a rung fits, never an estimate. `benchmark` similarly runs all
  four presets in full.
- SSIM here is a lightweight, unwindowed global approximation (mean/
  variance/covariance over the whole page render), not a proper windowed
  SSIM -- good enough to flag a page that changed a lot, not precise
  enough to compare small local differences. It's diagnostic-only either
  way: nothing in the compression policy reads it.
- Validation's "vector content untouched" check compares the count of
  vector drawing paths per page; it would catch a page being rasterized
  wholesale, but wouldn't catch a single path being subtly altered.
- The web UI runs compression synchronously in the request handler (a
  single scientific paper takes seconds to tens of seconds); there's no
  granular progress bar, just a status spinner, and only one job runs at
  a time in Flask's default dev-server threading model. Uploaded and
  compressed files live under a per-job temp directory keyed by a random
  token and are not automatically cleaned up on a timer — fine for local,
  single-user use, not for a long-running public deployment.
- The PDF viewer renders one page at a time (matching the sidebar spec's
  paginated toolbar) rather than continuous scroll; very large pages at
  high zoom are re-rendered to a single canvas sized for that zoom level,
  not tiled, so extreme zoom on a very large page is the slow path.
