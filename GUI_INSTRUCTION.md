# PDFShrink Native Ubuntu GUI — Implementation Instructions

## Objective

The PDFShrink compression backend and web application are already implemented and working.

Your task is **NOT to redesign or rewrite the PDF compression backend or the existing web application**.

Your task is to build a polished **native desktop GUI for Ubuntu/Linux** on top of the existing PDFShrink core, and then package it so an end user can install or run it **without Conda, Python, pip, or a terminal-based development setup**.

The final user experience should be:

1. Install PDFShrink from a `.deb`, or run a portable AppImage.
2. Open PDFShrink from the Ubuntu application launcher.
3. Drag and drop a PDF.
4. Select a target size or compression preset.
5. Click **Compress**.
6. See real progress without the UI freezing.
7. Review the compression result and validation status.
8. Open the compressed PDF or its containing folder.
9. Optionally inspect original/compressed previews.

The existing backend remains the source of truth for all PDF processing.

---

# 1. First: Inspect the Existing Project

Before writing GUI code:

1. Inspect the entire existing repository.
2. Identify:
   - compression core
   - PDF analyzer
   - optimizer
   - validator
   - configuration and presets
   - CLI
   - web application
   - data models
   - progress/reporting mechanisms
   - temporary-file handling
   - external native binaries, if any
3. Run all existing tests.
4. Run the existing CLI and/or web application where useful.
5. Understand the public API that should be reused by the GUI.
6. Identify every runtime dependency required by the compression backend.

Do not duplicate existing functionality.

Do not change working backend behavior merely to make GUI implementation easier.

If a small backend refactor is genuinely necessary to expose a clean reusable API, keep it minimal, test it, and preserve backward compatibility with both the CLI and web application.

---

# 2. Development Environment

Use the existing project Conda environment if one already exists.

For example:

```bash
conda activate pdfshrink
```

Do not create a second unnecessary environment.

Install GUI development dependencies inside the existing Conda environment.

Prefer:

```bash
python -m pip install PySide6
```

or Conda/conda-forge if more appropriate for the existing repository.

Do not install Python packages globally.

Do not modify the system Python.

Before development, verify:

```bash
which python
python --version
```

Keep development dependencies and runtime dependencies clearly separated where practical.

The Conda environment is for **development only**. The final application must not require Conda.

---

# 3. GUI Framework

Use:

**PySide6 / Qt 6**

This must be a real native desktop application.

Do NOT:

- implement another browser UI
- wrap the existing web app in a WebView
- use Electron
- launch a local web server just to display the desktop GUI

During development, the application should be runnable with something similar to:

```bash
pdfshrink-gui
```

or:

```bash
python -m pdfshrink.gui
```

Later it must be launchable directly from Ubuntu's application menu.

---

# 4. Architecture

Keep the GUI separate from the core.

A reasonable structure is:

```text
pdfshrink/
├── core/
│   ├── ...
│   └── existing backend
│
├── cli/
│   └── existing CLI
│
├── web/
│   └── existing web application
│
└── gui/
    ├── __init__.py
    ├── app.py
    ├── main_window.py
    │
    ├── widgets/
    │   ├── drop_zone.py
    │   ├── settings_panel.py
    │   ├── analysis_panel.py
    │   ├── progress_panel.py
    │   ├── result_panel.py
    │   └── pdf_preview.py
    │
    ├── workers/
    │   ├── analyze_worker.py
    │   └── compress_worker.py
    │
    └── resources/
        ├── icons/
        └── style.qss

packaging/
├── pyinstaller/
├── appimage/
└── deb/
```

Adapt this structure to the existing repository where appropriate.

The GUI should call the core directly through Python APIs.

Avoid:

```python
subprocess.run(["pdfshrink", ...])
```

when the compression engine can be imported directly.

Prefer:

```python
result = compressor.compress(...)
```

The CLI, web app, and GUI should all ultimately use the same compression engine.

The GUI must not contain its own PDF compression policy.

---

# 5. MVP User Interface

The initial screen should be intentionally simple.

The primary workflow should require almost no technical knowledge:

> **Drop PDF → choose target size → Compress**

Conceptually:

```text
┌──────────────────────────────────────────────────────┐
│ PDFShrink                                       ─ □ ×│
│ Scientific PDF Optimizer                            │
├──────────────────────────────────────────────────────┤
│                                                      │
│    ┌────────────────────────────────────────────┐    │
│    │                                            │    │
│    │              Drop PDF here                 │    │
│    │                                            │    │
│    │           or click to browse               │    │
│    │                                            │    │
│    └────────────────────────────────────────────┘    │
│                                                      │
│ paper.pdf                               12.43 MB     │
│                                                      │
│ Target size       [ 6.0 ] MB                         │
│ Preset            [ Scientific ▼ ]                   │
│                                                      │
│ Advanced ▸                                           │
│                                                      │
│                    [ Compress ]                      │
│                                                      │
└──────────────────────────────────────────────────────┘
```

Do not expose DPI, JPEG quality, PDF object IDs, or other technical concepts on the main screen.

---

# 6. Drag and Drop

Implement a proper PDF drag-and-drop zone.

Requirements:

- accept `.pdf`
- reject unsupported files cleanly
- visually react when a valid PDF is dragged over the window
- allow clicking the drop zone to open a file picker
- display:
  - filename
  - original file size
  - page count if quickly available
- allow dropping a new PDF after a previous job has completed

Also support:

```bash
pdfshrink-gui paper.pdf
```

so the application can later integrate naturally with Ubuntu's **Open With** menu.

---

# 7. Compression Settings

Expose existing backend presets.

At minimum, if already supported by the backend:

```text
Scientific
Maximum Quality
Balanced
Aggressive
```

Default:

```text
Scientific
```

Target size should be prominent:

```text
Target size: [ 6.0 ] MB
```

Use an appropriate numeric Qt control such as `QDoubleSpinBox`.

Reject invalid values.

If the requested target is equal to or larger than the input file size, communicate this clearly rather than performing unnecessary destructive compression.

---

# 8. Advanced Settings

Hide technical controls behind:

```text
Advanced ▸
```

Potential controls should map directly to existing backend options, for example:

```text
Maximum image DPI       [300]
Minimum JPEG quality    [88]
Line-art DPI            [450]
Preserve transparency   [✓]
Prefer lossless plots   [✓]
```

Do not invent settings unsupported by the backend.

Do not reproduce backend compression logic in GUI code.

The GUI collects parameters; the backend makes compression decisions.

---

# 9. Analysis

If the existing backend provides PDF analysis, expose it visually.

Show a concise summary:

```text
17 raster images
3 oversized
14 already optimized
```

Optionally provide an expandable table:

```text
Page   Resolution     DPI     Size      Type       Action
2      5120×2880      1340    3.1 MB    Render     Optimize
3      1200×900       286     240 KB    Plot       Keep
6      4000×3000      920     2.4 MB    Photo      Optimize
```

Analysis is secondary to the primary compression workflow.

Do not make users inspect the analysis before they can compress a PDF.

---

# 10. Background Processing

This is mandatory.

PDF analysis and compression must **NOT run on the Qt main thread**.

The GUI must remain responsive.

Use an appropriate Qt architecture such as:

```text
GUI thread
    │
    │ Qt signals
    ▼
QThread / QThreadPool worker
    │
    ▼
PDFShrink core
```

Never update GUI widgets directly from a worker thread.

Use Qt signals/slots for:

- progress
- status text
- success
- failure
- cancellation state

---

# 11. Progress Reporting

Connect existing backend progress events/callbacks to the GUI where available.

Display meaningful information, for example:

```text
Optimizing paper.pdf

████████████████░░░░░░░░░░  63%

Optimizing image 7 / 11
Page 4
4200 × 2800
300 DPI · JPEG Q92

Current estimated size: 7.1 MB
```

If the backend cannot provide an accurate percentage, use an indeterminate progress indicator.

Never invent fake progress percentages.

---

# 12. Cancellation

Provide a **Cancel** action during long operations if the backend can safely support cancellation.

Cancellation must not:

- modify the original PDF
- leave a corrupt partial output presented as valid
- crash the application
- leave unnecessary temporary files

If safe cancellation is not currently supported by the backend, document that limitation rather than implementing unsafe termination.

---

# 13. Result Screen

After successful compression, prominently display:

```text
12.43 MB  →  5.87 MB

Reduction: 52.8%
```

Also display validation information returned by the backend, for example:

```text
✓ PDF valid
✓ 8 / 8 pages
✓ Text preserved
✓ Vector content preserved

3 images optimized
14 images unchanged
```

Provide actions:

```text
Open PDF
Open Folder
Compress Another
```

Later, if preview functionality is implemented:

```text
Compare
```

---

# 14. Output Handling

Never overwrite the original PDF by default.

Use a sensible default:

```text
paper.pdf
    ↓
paper_compressed.pdf
```

Allow the user to choose another destination.

Handle filename collisions safely.

Do not silently overwrite an existing output.

Temporary files should use a safe temporary directory and be cleaned after completion or failure.

---

# 15. PDF Preview

Implement preview only after the basic GUI workflow is stable.

Use MuPDF/PyMuPDF or another renderer already available in the repository.

Rendering pages for GUI preview is allowed and does not imply rasterizing the actual output PDF.

Support:

- page navigation
- zoom
- fit page
- fit width

Thumbnail navigation is desirable but not required for the first release.

Avoid rendering every page at high resolution at startup.

Render lazily and cache previews sensibly.

---

# 16. Before/After Comparison

After compression, provide a useful visual comparison.

At minimum:

```text
Original | Compressed
```

Maintain synchronized page and zoom state where practical.

A later version may provide:

```text
┌──────────────────┬──────────────────┐
│ Original         │ Compressed       │
│                  │                  │
│    PDF page      │    PDF page      │
│                  │                  │
└──────────────────┴──────────────────┘

Zoom: 100%  200%  400%
Synchronize zoom: ✓
```

This feature is especially useful for scientific papers because users care about whether plots, diagrams, equations, and figures remain sharp.

Do not block the MVP release on before/after comparison.

---

# 17. Error Handling

Present errors cleanly.

Examples:

- invalid PDF
- encrypted PDF
- unsupported PDF feature
- permission denied
- disk full
- output path unavailable
- backend compression failure
- validation failure

Do not show a raw Python traceback to normal users.

Example:

```text
Could not compress this PDF.

The document contains an image format that PDFShrink
cannot safely optimize.

The original PDF was not modified.

[Show Details] [Close]
```

`Show Details` may expose technical diagnostics.

Log full exceptions for development/debugging.

---

# 18. UI/UX Direction

The application should feel like a focused Ubuntu utility, not an enterprise dashboard.

Design goals:

- minimal
- clean
- modern
- spacious
- responsive
- obvious primary action
- minimal visual clutter

Avoid:

- excessive cards
- gradients everywhere
- dashboard-style layouts
- unnecessary animation
- excessive icons
- technical PDF terminology on the main screen

Use Qt's native capabilities where practical.

Support light and dark desktop environments if reasonably possible.

Functionality and clarity are more important than creating a custom design system.

---

# 19. Keyboard and Desktop Behavior

Support basic desktop conventions.

Suggested shortcuts:

```text
Ctrl+O       Open PDF
Ctrl+Enter   Compress
Ctrl+Q       Quit
```

Optional:

```text
Ctrl+,       Settings
```

Support opening a PDF directly:

```bash
pdfshrink-gui paper.pdf
```

This should later allow:

```text
Right click paper.pdf
    ↓
Open With
    ↓
PDFShrink
```

---

# 20. Persistent Preferences

Use `QSettings` for lightweight preferences.

Potentially remember:

- last preset
- last target size
- last output directory
- advanced settings
- window size/state

Do not store document contents.

Do not unnecessarily store recent PDF paths if there is no product need.

---

# 21. Tests

Keep all existing backend, CLI, and web tests passing.

Add practical GUI/integration tests for:

- GUI/backend parameter mapping
- invalid input
- output naming
- settings persistence
- worker success
- worker failure
- worker signals
- target-size validation

Do not overinvest in pixel-perfect GUI testing.

Core PDF correctness remains the responsibility of the existing backend test suite.

---

# 22. Release Goal

The final release must work on a normal supported Ubuntu machine **without requiring the user to install**:

- Conda
- Python
- pip
- PySide6
- the project's development environment

The user should receive either:

```text
PDFShrink-1.0.0-x86_64.AppImage
```

or:

```text
pdfshrink_1.0.0_amd64.deb
```

and be able to use PDFShrink as a normal desktop application.

---

# 23. Packaging Strategy

Do not start packaging until the GUI works reliably from the development environment.

Recommended pipeline:

```text
Source repository
      ↓
PyInstaller
      ↓
Standalone Linux application bundle
      ↓
 ┌───────────────┬───────────────┐
 │               │               │
AppImage        .deb        development build
```

Use PyInstaller or another justified Python application bundler to include the Python interpreter and Python runtime dependencies.

The packaged application must not rely on the user's Conda environment.

---

# 24. External Native Dependencies

Before packaging, audit the backend for external executables such as:

```text
qpdf
Ghostscript
oxipng
pngquant
mozjpeg
```

For every external binary, explicitly decide whether to:

1. bundle a compatible binary with PDFShrink, or
2. declare it as a package dependency, or
3. make it an optional backend with graceful fallback

Do not accidentally build an application that works only because the development machine already has these tools installed.

The packaging test must be performed in a clean environment.

---

# 25. AppImage Release

Produce a portable AppImage as the first release format if practical.

Target:

```text
PDFShrink-1.0.0-x86_64.AppImage
```

Expected user workflow:

```bash
chmod +x PDFShrink-1.0.0-x86_64.AppImage
./PDFShrink-1.0.0-x86_64.AppImage
```

The AppImage must contain or correctly provide access to everything needed at runtime.

It should not require Conda.

It should not require the source repository.

Test:

- startup
- drag and drop
- analysis
- compression
- output creation
- PDF opening
- failure handling

on a clean Ubuntu environment.

---

# 26. Debian `.deb` Installer

After the standalone build is stable, produce:

```text
pdfshrink_1.0.0_amd64.deb
```

The package should install PDFShrink as a normal Ubuntu application.

Expected installation:

```bash
sudo apt install ./pdfshrink_1.0.0_amd64.deb
```

It should install appropriate files under locations such as:

```text
/opt/pdfshrink/
/usr/bin/pdfshrink-gui
/usr/share/applications/pdfshrink.desktop
/usr/share/icons/hicolor/.../apps/pdfshrink.png
```

Use appropriate Linux filesystem conventions rather than blindly copying these exact paths if a better packaging structure is warranted.

After installation:

- PDFShrink appears in Ubuntu Applications.
- Clicking the icon launches the GUI.
- No terminal window is required.
- The application works without activating Conda.
- Uninstallation removes installed application files cleanly.

---

# 27. Desktop Integration

Create a `.desktop` entry with appropriate final paths.

Conceptually:

```ini
[Desktop Entry]
Name=PDFShrink
Comment=Scientific PDF Optimizer
Exec=pdfshrink-gui %f
Icon=pdfshrink
Terminal=false
Type=Application
Categories=Office;Utility;
MimeType=application/pdf;
```

Register PDF MIME support appropriately.

The intended result is:

```text
Right click paper.pdf
    ↓
Open With
    ↓
PDFShrink
```

Do not force PDFShrink to become the system default PDF viewer.

---

# 28. Application Icon and Metadata

Provide a proper application icon.

Include standard Linux icon sizes where appropriate.

Also provide:

- application name: `PDFShrink`
- short description: `Scientific PDF Optimizer`
- version information
- About dialog
- license information if already defined by the repository

Do not use third-party copyrighted branding.

---

# 29. Clean-Machine Acceptance Test

This is mandatory before considering packaging complete.

Test the final release in a clean Ubuntu VM/container/environment that does **not** have the development Conda environment.

Ideally the test environment should not already have the project's Python dependencies.

For AppImage, verify:

```text
Fresh Ubuntu
    ↓
Copy AppImage
    ↓
Make executable
    ↓
Launch
    ↓
Compress real scientific PDF
    ↓
Open output
```

For `.deb`, verify:

```text
Fresh Ubuntu
    ↓
Install .deb
    ↓
Launch from Applications
    ↓
Compress real scientific PDF
    ↓
Open output
    ↓
Uninstall package
```

Do not consider a package successful merely because it runs on the development machine.

---

# 30. Release Artifacts

At the end of the packaging phase, produce a release directory similar to:

```text
dist/
├── PDFShrink-1.0.0-x86_64.AppImage
├── pdfshrink_1.0.0_amd64.deb
├── SHA256SUMS
└── RELEASE_NOTES.md
```

Generate SHA-256 checksums for distributed binaries.

Document:

- supported Ubuntu versions
- architecture
- known limitations
- external dependencies, if any

---

# 31. Development Milestones

Implement incrementally.

## Milestone 1 — Integration audit

- inspect existing backend/web project
- run existing tests
- identify reusable API
- identify native dependencies
- document GUI integration points

Do not implement substantial UI until this is understood.

## Milestone 2 — Minimal PySide6 application

- application startup
- main window
- drag and drop
- file picker
- target size
- presets
- Compress button

## Milestone 3 — Backend integration

- connect GUI to existing core
- background worker
- progress
- success/failure handling
- output file

At this point the application must already be usable.

## Milestone 4 — Analysis and results

- PDF analysis summary
- detailed image table
- compression summary
- validation status
- Open PDF
- Open Folder

## Milestone 5 — Preview

- page renderer
- navigation
- zoom
- fit page / fit width
- thumbnails if practical

## Milestone 6 — Before/after comparison

- original/compressed toggle
- synchronized page
- synchronized zoom

## Milestone 7 — UX polish

- advanced settings
- keyboard shortcuts
- QSettings
- dark/light compatibility
- icon
- error dialogs
- logging

## Milestone 8 — Standalone build

- dependency audit
- PyInstaller configuration
- standalone application
- test outside Conda

## Milestone 9 — AppImage

- AppImage packaging
- clean Ubuntu test
- portable release artifact

## Milestone 10 — Debian package

- `.deb`
- `.desktop`
- icon installation
- MIME integration
- clean install/uninstall test

## Milestone 11 — Release validation

- test real scientific PDFs
- verify original files remain untouched
- verify CLI still works
- verify web app still works
- verify GUI package on clean Ubuntu
- generate checksums
- write release notes

---

# 32. Development Discipline

At the end of every milestone:

1. run existing backend tests
2. run CLI tests
3. run web tests
4. run new relevant GUI tests
5. manually launch the GUI where applicable
6. test with at least one real scientific PDF
7. verify the original PDF remains untouched
8. document known limitations
9. make a Git commit with a meaningful commit message

Examples:

```text
feat(gui): add PySide6 application shell and PDF drop zone
feat(gui): integrate compression worker and progress reporting
feat(gui): add PDF analysis and compression results
feat(gui): add PDF preview and zoom controls
build(linux): add PyInstaller standalone bundle
build(appimage): add portable Ubuntu release
build(deb): add Ubuntu desktop installer
```

Do not combine the entire GUI and packaging implementation into one giant commit.

---

# 33. Important Constraints

Do **NOT**:

- rewrite the working compression engine unnecessarily
- duplicate compression algorithms inside the GUI
- remove or break the existing web application
- remove or break the existing CLI
- rasterize PDFs for compression
- run compression on the GUI thread
- overwrite original PDFs by default
- require Conda for end users
- require users to manually install Python packages
- use Electron merely to obtain a desktop window
- hide backend errors during development
- claim progress percentages that are not actually known
- assume native binaries installed on the development machine will exist on user machines
- declare packaging successful without clean-machine testing

The existing backend is the source of truth for PDF processing.

The GUI is a native presentation and interaction layer around that backend.

---

# 34. Definition of Done

The desktop project is considered complete when all of the following are true:

1. I can launch PDFShrink as a native Ubuntu application.
2. I can drag a scientific PDF into the window.
3. I can specify a target such as `6 MB`.
4. Compression runs without freezing the GUI.
5. The original PDF is not overwritten.
6. The result screen shows actual output size and validation status.
7. I can open the output PDF or its containing folder.
8. The existing CLI still works.
9. The existing web application still works.
10. An AppImage works on a clean supported Ubuntu installation without Conda.
11. A `.deb` can be installed on a clean supported Ubuntu installation.
12. The installed `.deb` appears in Ubuntu Applications.
13. The installed application does not require the user to activate a Python environment.
14. External native dependencies are either bundled, explicitly packaged, or handled gracefully.
15. Release binaries and checksums are produced in `dist/`.

The guiding principles are:

> **Keep the compression engine stable. Make the desktop experience simple.**

and:

> **The development environment may use Conda; the released application must not depend on it.**
