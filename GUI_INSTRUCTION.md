# pdf4sci Native GUI & Linux Packaging

The pdf4sci compression backend, CLI, and web application are already functional and should be treated as stable.

The current web application has reached a satisfactory workflow and should be used as the **behavioral and visual reference** for the native application.

The goal of this task is to build a polished native Linux desktop application and produce distributable:

* `.AppImage`
* `.deb`

packages.

The final application must run on a normal Ubuntu machine **without requiring Conda, a manually installed Python environment, or running the web server manually**.

Do not redesign or rewrite the compression engine during this task.

---

# 1. Primary Goal

Turn the existing pdf4sci project into an installable Linux desktop application.

The expected user experience is:

```text
Install / launch pdf4sci
        ↓
Open or drop PDF
        ↓
Preview PDF
        ↓
Configure compression
        ↓
Compress
        ↓
Preview compressed PDF
        ↓
Compare Original / Compressed
        ↓
Download / Save result
```

The native GUI should preserve the workflow and visual hierarchy already established in the current web application.

---

# 2. First: Inspect the Existing Project

Before writing GUI or packaging code, inspect the repository.

Determine:

* project structure
* Python version
* compression-core entry points
* CLI entry point
* current web application architecture
* existing tests
* dependency files
* native external tools used
* optional external tools
* how compression progress is exposed
* how PDF analysis is exposed
* how temporary files are managed
* how compressed output is generated
* current preset definitions
* current advanced settings

Do not guess these APIs.

Reuse the existing implementation.

Run the current test suite before modifying anything.

Record the baseline result.

---

# 3. Freeze the Compression Core

Treat the existing compression engine as stable.

Do NOT:

* redesign compression algorithms
* change target-size behavior
* change DPI logic
* change JPEG quality logic
* introduce vector compression
* change presets unless required to fix an actual bug
* duplicate compression logic inside the GUI
* break CLI behavior

The GUI must call the same compression core used by the CLI/web application.

Architecture should remain conceptually:

```text
                 ┌───────────────┐
                 │ pdf4sci Core│
                 └───────┬───────┘
                         │
            ┌────────────┼────────────┐
            │            │            │
           CLI         Web UI      Native GUI
```

There must be only one source of truth for compression behavior.

---

# 4. Native GUI Technology

Use:

> **PySide6 / Qt 6**

Do not use:

* Electron
* embedded Chromium merely to display the existing website
* WebView as the main application
* another local web server as the native GUI
* Tkinter

Build a real Qt desktop interface.

The native application should invoke the Python compression core directly.

---

# 5. GUI Layout

Use the current web application as the primary UX reference.

The desktop application should use:

```text
┌──────────────────────────┬───────────────────────────────────────────┐
│                          │                                           │
│ pdf4sci                │                                           │
│                          │                                           │
│ File information         │                                           │
│                          │                                           │
│ Compression settings     │                                           │
│                          │                PDF VIEWER                 │
│ Advanced settings        │                                           │
│                          │                                           │
│ Compress                 │                                           │
│                          │                                           │
│ Progress                 │                                           │
│ Results                  │                                           │
│                          │                                           │
│ Save / Export            │                                           │
│                          │                                           │
└──────────────────────────┴───────────────────────────────────────────┘
```

Use:

* left sidebar for information and controls
* large PDF viewer on the right

Suggested sidebar width:

```text
300–380 px
```

The PDF viewer should receive most of the available window.

Do not turn the GUI into a dashboard.

---

# 6. File Loading

Support:

* Open PDF button
* drag-and-drop PDF
* optionally opening a PDF passed as a command-line argument

Example:

```bash
pdf4sci paper.pdf
```

If practical, support Linux file-manager integration later through the `.desktop` file.

After loading a PDF:

* validate it
* show filename
* show original file size
* show page count
* run existing analysis where appropriate
* immediately display it in the PDF viewer

Do not require a separate Preview button.

---

# 7. Compression Controls

Expose the same important controls as the current web application.

At minimum:

```text
Target size
[ 6.0 ] MB

Preset
[ Scientific ▼ ]

Advanced ▸

[ Compress ]
```

Advanced settings should expose existing backend options, including where applicable:

```text
Maximum image DPI
Minimum JPEG quality
```

Do not invent GUI-only compression parameters.

GUI values must map directly to existing backend configuration.

Use the same default values and preset definitions as the existing application.

---

# 8. PDF Viewer

Implement an integrated native PDF viewer.

Prefer Qt's supported PDF functionality where suitable, such as Qt PDF / `QPdfDocument`, rather than introducing an entire browser engine.

Requirements:

* render PDF pages
* previous/next page
* current page / total pages
* zoom in/out
* fit width
* fit page
* scrolling
* mouse wheel
* trackpad
* high zoom suitable for scientific figures

Target useful zoom range should include approximately:

```text
100%
125%
150%
200%
300%
400%
```

The user must be able to inspect:

* equations
* plot lines
* labels
* diagrams
* raster images
* scientific figures

Rendering must not modify the actual PDF.

---

# 9. Original / Compressed Preview

Use one main PDF viewer.

Before compression:

```text
viewer = original PDF
```

After compression:

```text
viewer = compressed PDF
```

Then expose:

```text
Preview

[ Original | Compressed ]
```

Default to `Compressed` after successful compression.

When switching between Original and Compressed, preserve whenever possible:

* page number
* zoom
* scroll position

This should allow rapid visual comparison.

Do not build two simultaneous viewers unless there is a compelling technical reason.

---

# 10. Compression Must Run in Background

This is mandatory.

Compression must never block the Qt UI thread.

Use an appropriate Qt worker architecture such as:

* `QThread`
* worker `QObject`
* Qt signals/slots

The UI must remain responsive while compression runs.

The user should still be able to:

* move the window
* inspect the current PDF
* scroll the PDF
* see progress
* cancel where backend cancellation safely supports it

Never call the full compression process synchronously from the GUI thread.

---

# 11. Progress

Use real backend progress if available.

Display information such as:

```text
Compressing...

████████████████░░░░ 72%

Optimizing images...
```

If exact progress cannot be determined, use an indeterminate progress indicator.

Do not fake percentages.

Worker → GUI communication must be thread-safe using Qt signals.

---

# 12. Compression Result

After successful compression show compact information in the sidebar:

```text
Complete

12.43 MB
    ↓
5.87 MB

52.8% smaller

✓ PDF valid
✓ 8 pages
```

If available, also show compact analysis such as:

```text
3 images optimized
14 images unchanged
```

Do not create a separate result window.

Keep the PDF viewer visible.

Automatically switch the viewer to the compressed PDF.

---

# 13. Saving Output

Provide a clear action:

```text
Save compressed PDF
```

Use a native Qt save-file dialog.

Suggest an output filename such as:

```text
paper_compressed.pdf
```

Never overwrite the original PDF without explicit confirmation.

Prefer preventing accidental overwrite entirely.

The user should always retain the source PDF.

---

# 14. Temporary Files

Manage temporary output carefully.

During compression:

* use an application-specific temporary directory
* do not overwrite input
* clean temporary files after they are no longer needed
* preserve compressed result until the user saves it or closes/replaces the job

On application exit, clean stale temporary resources where safe.

Do not delete user-created output files.

---

# 15. Loading Another PDF

When another PDF is opened:

* cancel/finish current safe operations as appropriate
* dispose current viewer document
* clear previous compressed output
* clear previous analysis
* clear previous result
* reset Original/Compressed preview
* load the new document

Never display results belonging to the previous PDF.

---

# 16. Error Handling

Handle at least:

* invalid PDF
* encrypted/password-protected PDF
* corrupted PDF
* unreadable file
* unsupported PDF feature
* compression failure
* insufficient disk space
* missing optional dependency
* backend exception
* output write failure

Show concise user-facing errors.

Do not dump Python tracebacks into the normal GUI.

Detailed diagnostics may be written to logs.

---

# 17. Logging

Add appropriate application logging if not already available.

Prefer a location consistent with Linux desktop applications.

Logs should help diagnose:

* startup failures
* dependency failures
* compression exceptions
* PDF rendering problems
* packaging-specific failures

Do not log PDF contents or unnecessary user data.

---

# 18. Development Environment

Development may continue using the existing Conda environment.

Prefer the existing environment:

```bash
conda activate pdf4sci
```

Do not install Python packages globally.

Update the reproducible environment specification if GUI dependencies are added.

For example:

```yaml
PySide6
```

or the exact package dependencies actually required.

Development environment and release runtime are different concerns.

---

# 19. Release Requirement

The final user must NOT need:

* Conda
* Miniconda
* Anaconda
* Python installed separately
* pip
* virtualenv
* manually running a backend
* manually installing Python packages

The release should behave like a normal Linux application.

---

# 20. Audit External Native Dependencies

Before packaging, identify every external executable used by pdf4sci.

Possible examples may include:

* qpdf
* Ghostscript
* oxipng
* pngquant
* MozJPEG / cjpeg
* MuPDF-related utilities

Do not assume all of these are actually required.

Classify each dependency as:

```text
Required
Optional
Development only
```

For each required dependency decide whether to:

1. bundle it with the application, or
2. declare it as a system dependency where appropriate.

The AppImage should be as self-contained as reasonably possible.

The `.deb` package may use appropriate Ubuntu package dependencies where this is cleaner and reliable.

Do not silently rely on executables that happen to exist on the development machine.

---

# 21. Python Application Bundling

Use **PyInstaller** unless repository inspection reveals a strong technical reason to use another approach.

Create a reproducible build configuration.

Prefer a `.spec` file committed to the project.

Ensure PyInstaller includes:

* Python runtime
* pdf4sci modules
* PySide6
* required Qt plugins
* Qt PDF components
* icons
* application resources
* required Python dependencies
* required non-Python resources

Check carefully for Qt plugin issues.

Test from the generated bundle, not only from source.

---

# 22. Build Stages

Do not attempt AppImage and `.deb` packaging before the standalone bundled application works.

Use this sequence:

```text
Source
   ↓
PyInstaller bundle
   ↓
Test bundle
   ↓
AppImage
   ↓
Test AppImage
   ↓
.deb
   ↓
Test .deb
```

Debug each layer independently.

---

# 23. AppImage

Produce an artifact such as:

```text
pdf4sci-x86_64.AppImage
```

The AppImage should:

* launch directly
* contain the application runtime
* contain required Qt libraries/plugins
* contain required application resources
* not require Conda
* not require separate Python
* work from arbitrary user directories

Make it executable:

```bash
chmod +x pdf4sci-x86_64.AppImage
```

Then it should launch with:

```bash
./pdf4sci-x86_64.AppImage
```

Test the actual generated AppImage.

Do not assume successful packaging means successful execution.

---

# 24. Debian Package

Produce an installable package such as:

```text
pdf4sci_<version>_amd64.deb
```

Installation should work using:

```bash
sudo apt install ./pdf4sci_<version>_amd64.deb
```

After installation the user should be able to launch:

```bash
pdf4sci
```

or:

```bash
pdf4sci-gui
```

Choose naming consistently with the existing CLI.

The desktop application must also appear in the Ubuntu application launcher.

---

# 25. Desktop Integration

Create a `.desktop` entry.

Conceptually:

```ini
[Desktop Entry]
Name=pdf4sci
Comment=Compress scientific PDF files
Exec=pdf4sci-gui %f
Icon=pdf4sci
Terminal=false
Type=Application
Categories=Office;Utility;
MimeType=application/pdf;
```

Adjust `Exec` to the actual packaged executable.

Install icons in appropriate Linux icon locations and sizes.

The application should have:

* launcher icon
* window icon
* taskbar/dock icon

---

# 26. Open With pdf4sci

Where practical, support:

```text
Right click PDF
→ Open With
→ pdf4sci
```

The application should accept a PDF path passed through the `.desktop` entry.

Do not make pdf4sci the default PDF application automatically.

---

# 27. Application Identity

Use consistent naming:

```text
pdf4sci
```

Provide application metadata including:

* application name
* version
* description
* icon
* license information

Do not display development/Conda terminology to end users.

---

# 28. Linux Compatibility

Primary target:

```text
Ubuntu 22.04+
x86_64
```

Also test on a newer Ubuntu release if practical.

Be careful about:

* glibc compatibility
* Qt platform plugins
* X11
* Wayland
* font rendering
* Qt PDF dependencies
* bundled shared libraries

Prefer building on the oldest supported Ubuntu environment so the resulting binaries are not accidentally linked against a newer glibc than Ubuntu 22.04 provides.

A container or clean VM may be used for reproducible release builds.

---

# 29. Clean-Machine Testing

This is critical.

Do not validate releases only on the development machine.

Test on a clean Ubuntu environment with:

* no Conda
* no project virtualenv
* no repository checkout
* no development Python packages
* no accidentally inherited native dependencies

Test both:

```text
.AppImage
```

and:

```text
.deb
```

At minimum test:

1. application launches
2. PDF opens
3. drag-and-drop works
4. PDF preview works
5. page navigation works
6. zoom works
7. target size can be entered
8. presets work
9. advanced settings work
10. compression runs
11. GUI remains responsive
12. progress works
13. compressed PDF loads
14. Original/Compressed toggle works
15. output can be saved
16. saved PDF opens normally
17. loading another PDF resets state
18. application exits cleanly

Use at least one real scientific PDF containing:

* text
* equations
* vector plots
* raster figures
* multiple pages

---

# 30. Regression Testing

Packaging work must not break the existing project.

After implementation run:

* existing unit tests
* compression tests
* CLI tests
* target-size tests
* validation tests

Then add GUI-focused tests where practical.

Do not rewrite existing tests merely to make failures disappear.

---

# 31. Packaging Scripts

Make release generation reproducible.

Prefer scripts such as:

```text
scripts/
    build_bundle.sh
    build_appimage.sh
    build_deb.sh
    build_release.sh
```

or an equivalent clean structure.

Ideally:

```bash
./scripts/build_release.sh
```

should generate the release artifacts.

Avoid undocumented manual packaging steps.

---

# 32. Release Output

Collect final artifacts in a clear directory such as:

```text
dist/release/
```

Expected output:

```text
pdf4sci-x86_64.AppImage
pdf4sci_<version>_amd64.deb
SHA256SUMS
```

Generate SHA-256 checksums.

Do not include development environments or unnecessary intermediate build files in release artifacts.

---

# 33. Documentation

Update the README with a concise installation section.

Document:

### AppImage

```bash
chmod +x pdf4sci-x86_64.AppImage
./pdf4sci-x86_64.AppImage
```

### Debian/Ubuntu

```bash
sudo apt install ./pdf4sci_<version>_amd64.deb
```

Also document:

* supported Ubuntu versions
* how to launch
* drag-and-drop/open-file behavior
* where output is saved
* known packaging limitations, if any

Keep development instructions separate from end-user installation.

---

# 34. Do Not Overengineer

Do not add:

* automatic updater
* user accounts
* telemetry
* cloud storage
* plugin systems
* database
* online services
* Electron
* embedded web application
* installer wizard
* Windows packaging
* macOS packaging

Those are outside this task.

Focus on a high-quality Ubuntu release.

---

# 35. Implementation Milestones

Work incrementally.

## Milestone 1 — Repository Audit

Inspect:

* backend
* CLI
* webapp
* tests
* dependencies
* external executables

Confirm existing behavior before modification.

## Milestone 2 — Native GUI Skeleton

Create PySide6 application with:

* main window
* sidebar
* viewer area
* file opening
* drag/drop

## Milestone 3 — PDF Viewer

Implement:

* PDF loading
* rendering
* page navigation
* zoom
* fit width/page

## Milestone 4 — Compression Integration

Connect GUI directly to existing core.

Implement:

* target size
* presets
* advanced settings
* background worker

## Milestone 5 — Results

Implement:

* progress
* before/after size
* validation
* compressed preview
* Original/Compressed toggle
* save output

## Milestone 6 — GUI Testing

Test from source inside the development environment.

Fix GUI lifecycle/thread/resource issues.

## Milestone 7 — Standalone Bundle

Create and test PyInstaller bundle.

Do not continue until this runs independently from the source environment.

## Milestone 8 — AppImage

Build and test:

```text
pdf4sci-x86_64.AppImage
```

## Milestone 9 — Debian Package

Build and test:

```text
pdf4sci_<version>_amd64.deb
```

## Milestone 10 — Clean Ubuntu Test

Test both artifacts on a clean supported Ubuntu environment.

## Milestone 11 — Release

Generate:

* AppImage
* `.deb`
* SHA256SUMS
* release documentation

---

# 36. Definition of Done

This task is complete only when all of the following are true:

### GUI

* pdf4sci launches as a native Qt application.
* Left sidebar contains file information and all compression controls.
* Right side contains a large integrated PDF viewer.
* Drag-and-drop works.
* File picker works.
* PDF preview works.
* Page navigation works.
* Zoom works.
* Compression runs outside the UI thread.
* Progress/status is displayed.
* Compressed PDF is previewed after completion.
* Original/Compressed switching works.
* Output can be saved safely.
* Loading another PDF correctly resets application state.

### Core

* Existing compression behavior remains unchanged.
* Existing CLI still works.
* Existing tests pass.
* GUI uses the existing compression core rather than duplicating it.

### AppImage

* A working `.AppImage` is produced.
* It runs without Conda.
* It runs without separately installed Python.
* It has been tested outside the development environment.

### Debian Package

* A working `.deb` is produced.
* It installs with `apt`.
* pdf4sci appears in the Ubuntu application launcher.
* Desktop icon works.
* Application launches after installation.
* File-path argument/open-with behavior works where implemented.

### Release

The final release directory contains at minimum:

```text
pdf4sci-x86_64.AppImage
pdf4sci_<version>_amd64.deb
SHA256SUMS
```

Provide a short final report containing:

* files created
* GUI architecture used
* packaging approach
* required/bundled native dependencies
* tests performed
* clean-machine test results
* known limitations

Do not claim packaging success unless the actual generated artifacts were launched and tested.

---

# Final Principle

> **The existing compressor is the product core. The native GUI is only a clean interface to it.**

and:

> **The development environment may use Conda; the released application must not depend on Conda or a separately installed Python runtime.**

Prioritize reliability, scientific-PDF quality preservation, and a simple Ubuntu desktop experience over adding new features.
