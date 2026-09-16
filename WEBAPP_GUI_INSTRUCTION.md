# pdf4sci Web UI — Integrated PDF Viewer

The pdf4sci backend and current web application already work.

For this task, **do not modify the compression engine**.

Only improve the existing web application by reorganizing the interface and adding an integrated PDF viewer.

The UI should use a simple **two-column desktop layout**:

* **Left column:** all information, settings, actions, progress, and results.
* **Right column:** PDF viewer only.

Do not create two PDF viewers.

Do not create separate Original/Compressed panels.

---

# 1. Main Layout

Use approximately:

```text
┌─────────────────────────┬────────────────────────────────────────────┐
│                         │                                            │
│ pdf4sci               │                                            │
│ Scientific PDF Optimizer│                                            │
│                         │                                            │
│ File                    │                                            │
│ paper.pdf               │                                            │
│ 12.43 MB · 8 pages      │                                            │
│                         │                                            │
│ Target size             │                                            │
│ [ 6.0            ] MB   │                PDF VIEWER                  │
│                         │                                            │
│ Preset                  │                                            │
│ [ Scientific       ▼ ]  │                                            │
│                         │                                            │
│ Advanced ▸              │                                            │
│                         │                                            │
│ [      Compress      ]  │                                            │
│                         │                                            │
│ Status / analysis       │                                            │
│                         │                                            │
│ Results                 │                                            │
│ 12.43 MB → 5.87 MB      │                                            │
│                         │                                            │
│ [ Download ]            │                                            │
│                         │                                            │
└─────────────────────────┴────────────────────────────────────────────┘
```

The left column contains **all application UI except the PDF itself**.

The right column should be dedicated almost entirely to PDF viewing.

Suggested width:

```text
Left:   ~300–380 px
Right:  remaining width
```

or approximately:

```text
30% | 70%
```

Do not use a 50/50 split unless required by the existing design.

The PDF viewer should receive substantially more screen space.

---

# 2. Left Sidebar

Put all information and controls in the left sidebar.

This includes:

* application name
* file selection
* filename
* original file size
* page count
* PDF analysis
* target size
* preset
* advanced options
* Compress button
* progress
* compression status
* result size
* reduction percentage
* validation result
* Download button
* Compress Another / Load Another action

Nothing except the PDF viewer itself should need to appear on the right side.

---

# 3. Initial State

Before a PDF is loaded, the left sidebar should provide the upload/drop area.

Example:

```text
pdf4sci
Scientific PDF Optimizer

┌───────────────────────┐
│                       │
│    Drop PDF here      │
│                       │
│  or click to browse   │
│                       │
└───────────────────────┘
```

The right viewer should remain empty or show a subtle placeholder.

Do not create a large decorative empty state.

---

# 4. After Loading a PDF

Once a PDF is selected:

Left sidebar:

```text
paper.pdf

12.43 MB
8 pages

Target size
[ 6.0 ] MB

Preset
[ Scientific ▼ ]

Advanced ▸

[ Compress ]
```

Right side:

```text
┌────────────────────────────────────────────┐
│                                            │
│                                            │
│                                            │
│                 PDF                        │
│                                            │
│                                            │
│                                            │
├────────────────────────────────────────────┤
│ ‹    Page 3 / 8    ›   Fit Width   − 125% +│
└────────────────────────────────────────────┘
```

The uploaded PDF should appear automatically.

Do not require a separate Preview button.

---

# 5. PDF Viewer

Use **PDF.js** unless the current application already has an appropriate viewer.

The PDF viewer should be the dominant visual element.

Support:

* page rendering
* previous page
* next page
* current page / total pages
* direct page selection if simple
* zoom in
* zoom out
* fit width
* fit page
* mouse wheel
* trackpad scrolling
* high zoom for scientific figures

Support at least approximately:

```text
100%
125%
150%
200%
300%
400%
```

The user should be able to inspect:

* plots
* diagrams
* equations
* labels
* raster images
* small scientific figures

Do not implement:

* annotations
* PDF editing
* signing
* OCR

---

# 6. Viewer State Before and After Compression

There is only **one PDF viewer**.

Before compression:

```text
Viewer → uploaded/original PDF
```

After compression:

```text
Viewer → compressed PDF
```

Do not keep both PDFs visible simultaneously.

The purpose of this iteration is simply to let the user inspect the document inside pdf4sci.

---

# 7. Original / Compressed Toggle

After compression finishes, provide a small toggle in the left sidebar:

```text
Preview

[ Original | Compressed ]
```

Default after successful compression:

```text
Compressed
```

Selecting:

```text
Original
```

loads the original PDF into the same right-side viewer.

Selecting:

```text
Compressed
```

loads the compressed PDF.

Preserve the current page and zoom level when switching whenever possible.

Example:

```text
Page 5
Zoom 300%

Original
   ↓ click Compressed

Page 5
Zoom 300%
```

This makes visual comparison possible without needing two viewers.

---

# 8. Compression Controls

Keep compression controls entirely in the left sidebar.

Example:

```text
Target size

[ 6.0 ] MB


Preset

[ Scientific ▼ ]


Advanced ▸


[       Compress       ]
```

The Compress button should be visually prominent.

Do not place compression controls over the PDF viewer.

---

# 9. Analysis

If the backend already provides PDF analysis, show it in the left sidebar.

Keep the summary compact:

```text
Analysis

17 raster images
3 oversized
14 already optimized
```

Detailed analysis can live inside:

```text
View details ▸
```

Do not display technical image information unless the user expands it.

---

# 10. Compression Progress

During compression, keep the PDF viewer usable.

Do not replace the PDF viewer with a loading screen.

Show progress in the left sidebar:

```text
Compressing

████████████████░░░░  72%

Optimizing image 7 / 11
Page 4
```

The right side may continue showing the original PDF while compression is running.

If exact percentage is unavailable, use an indeterminate progress indicator.

Do not invent fake percentages.

---

# 11. Compression Result

After compression finishes, update the left sidebar:

```text
Complete

12.43 MB
    ↓
5.87 MB

52.8% smaller

✓ PDF valid
✓ 8 pages
```

Then show:

```text
Preview

[ Original | Compressed ]
```

and:

```text
[ Download compressed PDF ]
```

The right viewer should automatically switch to the compressed PDF.

---

# 12. Visual Comparison Workflow

The intended comparison workflow is:

```text
Compress
   ↓
viewer shows compressed PDF
   ↓
zoom into a figure
   ↓
toggle Original / Compressed
   ↓
same page + same zoom
   ↓
visually compare
```

This is simpler than maintaining two synchronized PDF viewers.

Preserve:

* current page
* zoom level
* preferably scroll position

when switching between Original and Compressed.

---

# 13. Loading Another PDF

Provide a clear action such as:

```text
Load another PDF
```

When another PDF is loaded:

1. dispose the current PDF.js document
2. clear the compressed result
3. revoke old object URLs
4. clear previous analysis
5. clear previous result
6. load the new original PDF
7. reset preview state to Original

Do not accidentally retain compressed output from the previous document.

---

# 14. Performance

Do not render every page at maximum resolution immediately.

Use PDF.js efficiently.

Prefer:

* lazy page rendering
* appropriate canvas resolution
* cancel obsolete render tasks
* reuse viewer component
* clean up old PDF documents
* revoke unused object URLs

Switching between Original and Compressed should feel fast.

---

# 15. Responsive Behavior

Desktop is the priority.

Use:

```text
┌─────────────┬───────────────────────────┐
│ Controls    │                           │
│ Info        │        PDF Viewer         │
│ Results     │                           │
└─────────────┴───────────────────────────┘
```

The left sidebar may have a fixed/minimum width.

The PDF viewer should expand with the browser window.

For narrow screens only, stacking is acceptable.

Do not spend excessive time on mobile optimization.

---

# 16. UI Direction

The application should feel like a small desktop utility.

Prioritize:

* PDF viewing area
* simple sidebar
* clear hierarchy
* compact controls
* minimal clutter

Avoid:

* dashboard design
* excessive cards
* excessive icons
* gradients everywhere
* large decorative headers
* large result screens
* modal dialogs for normal workflow

The user should be able to work almost entirely from one screen.

---

# 17. Scope

Implement only:

> Load → Inspect → Configure → Compress → Inspect result → Toggle before/after → Download

Do NOT:

* modify the compression algorithm
* implement vector compression
* build native GUI
* build AppImage
* build `.deb`
* implement Electron
* add PDF editing
* add annotations
* add OCR
* add authentication
* add accounts
* add cloud storage
* add unrelated features

---

# 18. Implementation Order

1. Inspect the existing web application.
2. Preserve the current backend and compression API.
3. Reorganize the UI into left sidebar + right viewer.
4. Integrate PDF.js.
5. Display the uploaded PDF automatically.
6. Implement page navigation.
7. Implement zoom / fit controls.
8. Keep all existing compression controls in the sidebar.
9. Keep progress/status in the sidebar.
10. Load compressed PDF into the same viewer after completion.
11. Add Original / Compressed toggle.
12. Preserve page and zoom while toggling.
13. Add compact compression results.
14. Preserve the existing download workflow.
15. Test loading another PDF.
16. Test with real scientific papers.
17. Verify existing backend/CLI tests still pass.

---

# 19. Definition of Done

The task is complete when:

1. All information and controls are contained in the left sidebar.
2. The right side is dedicated to one large PDF viewer.
3. Loading a PDF automatically displays it in the viewer.
4. I can navigate pages and zoom into scientific figures.
5. I can configure target size and compression from the left sidebar.
6. Compression progress appears in the sidebar without replacing the PDF viewer.
7. After compression, the viewer automatically displays the compressed PDF.
8. I can toggle between Original and Compressed.
9. Page and zoom remain unchanged when toggling whenever possible.
10. Before/after file sizes and reduction are shown in the sidebar.
11. I can download the compressed PDF.
12. Loading another PDF correctly clears the previous state.
13. The compression backend and CLI continue working unchanged.

Stop after this workflow works reliably.

Do not continue into native GUI, packaging, or compression-algorithm changes without explicit instruction.
