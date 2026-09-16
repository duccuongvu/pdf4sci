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

## Linux release packages (.AppImage / .deb)

Pre-built, self-contained releases of the native GUI — no Python, Qt, or
conda needed on the target machine.

```bash
# AppImage (portable, no install)
chmod +x pdf4sci-x86_64.AppImage
./pdf4sci-x86_64.AppImage
# if your system has no libfuse2: ./pdf4sci-x86_64.AppImage --appimage-extract-and-run

# Debian/Ubuntu package
sudo apt install ./pdf4sci_0.1.0_amd64.deb
pdf4sci-gui
```

Building them yourself (needs the `gui` extra + `pyinstaller` in the dev
env):

```bash
pip install -e ".[gui]" pyinstaller
./scripts/build_release.sh
# -> dist/release/pdf4sci-x86_64.AppImage, pdf4sci_0.1.0_amd64.deb, SHA256SUMS
```

`build_bundle.sh` / `build_appimage.sh` / `build_deb.sh` also run
individually. **Known gap:** built and smoke-tested in this dev
environment (bundle launches correctly with conda stripped from `PATH`),
but not verified on an actual clean Ubuntu machine (no VM/Docker
available here) — do a real install test before distributing.

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

packaging/      — PyInstaller spec, AppImage AppDir, .deb tree
scripts/        — build_bundle.sh, build_appimage.sh, build_deb.sh,
                  build_release.sh
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
- `.deb`/AppImage packages aren't yet verified on a genuinely clean
  machine (see the packaging section above).

---

© 2026 Duc Cuong Vu
