# PDFShrink Web UI — Focused MVP

The PDFShrink backend and current web application already work.

For this task, **do not modify or redesign the compression engine** and **do not build the native PySide6 GUI yet**.

I only want to improve the existing web application into a polished, usable PDF compression interface.

## Goal

The primary workflow must be extremely simple:

> Drop PDF → set target size → Compress → download result.

Do not expand the scope beyond this workflow.

## Main UI

Create a clean single-page interface approximately structured as:

```text
┌──────────────────────────────────────────────────────┐
│ PDFShrink                                            │
│ Scientific PDF Optimizer                            │
├──────────────────────────────────────────────────────┤
│                                                      │
│       ┌──────────────────────────────────────┐       │
│       │                                      │       │
│       │          Drop PDF here               │       │
│       │                                      │       │
│       │       or click to browse             │       │
│       │                                      │       │
│       └──────────────────────────────────────┘       │
│                                                      │
│ paper.pdf                               12.43 MB     │
│                                                      │
│ Target size       [ 6.0 ] MB                         │
│ Preset            [ Scientific ▼ ]                   │
│                                                      │
│ Advanced ▸                                           │
│                                                      │
│                   [ Compress ]                       │
│                                                      │
└──────────────────────────────────────────────────────┘
```

## Required features

Implement only:

1. PDF drag and drop.
2. File picker.
3. Show filename and original size.
4. Target-size input in MB.
5. Existing compression presets.
6. Advanced settings using existing backend options.
7. Compress button.
8. Real progress/status where supported by the backend.
9. Compression result.
10. Download compressed PDF.
11. Clear error messages.

Result example:

```text
Compression complete

12.43 MB  →  5.87 MB
Reduction: 52.8%

✓ PDF valid
✓ 8 / 8 pages
✓ Text preserved
✓ Vector content preserved

3 images optimized
14 images unchanged

[ Download compressed PDF ]
[ Compress another ]
```

## Analysis

If the backend already exposes PDF analysis, show a small optional section:

```text
17 raster images
3 oversized
14 already optimized
```

Detailed image information may be placed inside an expandable section.

Do not make analysis mandatory before compression.

## UI direction

The interface should feel like a small modern desktop utility.

Use:

* clean typography
* generous whitespace
* restrained borders
* clear hierarchy
* one obvious primary action
* responsive layout

Avoid:

* dashboard layouts
* excessive cards
* gradients everywhere
* excessive animation
* unnecessary icons
* technical PDF terminology on the main screen

## Architecture

Reuse the existing web stack.

Do not migrate frameworks unless absolutely necessary.

Do not rewrite the backend.

Do not duplicate compression logic in JavaScript.

The frontend should only collect user parameters, send them to the existing backend, and display the result.

## Important constraints

Do NOT:

* build PySide6
* build AppImage
* build `.deb`
* implement Electron
* redesign the compression backend
* break the existing CLI
* add authentication
* add accounts
* add cloud storage
* add a database unless the current application genuinely requires one
* add unrelated features

Keep this task small.

## Development process

First inspect the existing web application and identify the smallest changes required.

Then:

1. implement the new single-page UI
2. connect it to the existing backend
3. test PDF upload
4. test target-size compression
5. test download
6. test error handling
7. test with at least one real scientific PDF
8. verify existing backend tests still pass

Do not spend time on native desktop packaging in this task.

## Definition of Done

This task is complete when I can open the existing PDFShrink web application, drag in a scientific PDF, enter a target such as 6 MB, compress it, see the actual before/after size, and download the resulting PDF through a clean and polished interface.

Stop after this is working reliably.

Do not continue into native GUI or packaging without explicit instruction.
