# pdf4sci

A PDF compressor built for scientific papers: targets a **user-defined
file size** while keeping text, fonts, equations, and vector
graphics/plots untouched. It never rasterizes pages — only oversized
raster images are analyzed and re-encoded, and only when doing so
actually helps.

Ships three front ends (CLI, web, native desktop) over one shared
backend, so compression behavior is identical everywhere.

## Install

```bash
conda create -n pdf4sci python=3.10 -y && conda activate pdf4sci
pip install -e ".[dev]"          # core + web + GUI + tests
```

(No conda? A plain `python3 -m venv` works too — conda is only used here
because it doesn't need `sudo apt install python3-venv`.)

## CLI

```bash
pdf4sci paper.pdf --analyze              # report only, no changes
pdf4sci paper.pdf                        # writes paper_compressed.pdf
pdf4sci paper.pdf --target-size 6MB      # fit a size budget
pdf4sci paper.pdf --preset aggressive    # maximum-quality | scientific | balanced | aggressive
pdf4sci benchmark paper.pdf              # compare all presets
```

Run `pdf4sci --help` for the full flag list.

## Web UI

```bash
pdf4sci-web   # open http://127.0.0.1:5000
```

Drop a PDF, set a target size or preset, compress, and compare
Original/Compressed side by side in an in-browser PDF.js viewer.

## Native desktop GUI

```bash
pdf4sci-gui [paper.pdf]
```

A PySide6/Qt app with the same sidebar + PDF-viewer workflow as the web
UI; compression runs on a background thread so the window never freezes.

## Architecture

```text
pdf4sci/
    analyzer.py, optimizer.py, images.py, classifier.py,
    quality.py, validation.py, config.py, pdf_utils.py  — core engine
    cli.py       — Typer CLI
    web/         — Flask app (templates/, static/)
    gui/         — PySide6 desktop app
    assets/      — bundled app icons

tests/          — pytest, ~40 tests across engine, web, and GUI
```

Every front end calls the same `analyzer` / `optimizer` / `quality` /
`validation` functions directly — no duplicated compression logic.

## Testing

```bash
pytest
```

## Known limitations

- CMYK images and color-key/stencil `/Mask` transparency are left
  untouched rather than risk a color/transparency error.
- Re-encoding drops embedded ICC profiles.
- `.deb`/AppImage packaging isn't built yet.

---

© 2026 Duc Cuong Vu
