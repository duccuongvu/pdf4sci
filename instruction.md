# Smart Scientific PDF Compressor — Implementation Instructions

I want you to build a production-quality open-source PDF compression tool for Ubuntu/Linux, primarily optimized for scientific papers.

The main goal is **NOT maximum compression**. The goal is:

> Reduce a PDF to a user-defined target file size while preserving the highest possible visual quality, especially text, equations, vector graphics, plots, and line art.

A typical use case is compressing a 12 MB scientific paper to approximately 6 MB rather than aggressively reducing it to 1 MB with visibly degraded figures.

## Conda environment and dependency isolation

The project must use a dedicated Conda environment so that all Python dependencies are isolated from the system Python and other projects.

Use the environment name:

```bash
pdf4sci

## 1. Core philosophy

Do **NOT** rasterize entire PDF pages.

The tool must preserve, whenever possible:

- text as text
- embedded fonts
- equations
- vector graphics
- vector plots
- paths
- annotations
- links
- PDF structure

Compression should primarily target oversized raster images embedded in the PDF.

The tool should intelligently determine what actually needs compression instead of applying one global destructive preset.

## 2. Platform and technology

Target platform:

- Ubuntu 22.04+
- Python 3.10+
- no root privileges should be required after installation if possible

Preferred libraries/tools to investigate:

- PyMuPDF / MuPDF
- pikepdf
- qpdf
- Pillow
- libjpeg-turbo or MozJPEG
- oxipng
- pngquant
- Ghostscript

Do not blindly use all of them.

First investigate their capabilities and limitations, then choose the simplest robust architecture.

Prefer Python for orchestration. Native open-source command-line utilities may be used as optional backends where they provide substantially better compression.

## 3. First milestone: PDF analyzer

Before implementing compression, build a reliable PDF analyzer.

For every raster image, determine as much as possible:

- page number
- PDF object/xref
- pixel dimensions
- image format
- color space
- bits per component
- alpha/transparency
- compressed size
- decoded size if useful
- displayed physical dimensions
- effective DPI in the document
- whether the same image object is reused multiple times

Generate a report such as:

```text
Input: paper.pdf
Size: 12.4 MB
Pages: 8

Page 2:
  Image #17
  5120 x 2880 px
  Display size: 3.4 x 1.9 in
  Effective resolution: ~1500 DPI
  Embedded size: 3.1 MB
  Recommendation: downsample

Page 4:
  Image #31
  1200 x 900 px
  Effective resolution: ~290 DPI
  Embedded size: 240 KB
  Recommendation: keep
```

Also report approximately how much of the PDF size is attributable to raster images versus other objects where practical.

## 4. Smart image classification

Do not treat all raster images as photographs.

Try to distinguish at least:

1. photographic/rendered images
2. screenshots
3. plots/diagrams/line art
4. images with transparency
5. very small UI/logo/icon assets

Use inexpensive heuristics where possible.

For example, edge density, number of unique colors, entropy, alpha channel, image dimensions, and compression format may help.

The classification does not need machine learning unless there is a compelling reason.

Scientific plots and diagrams should strongly prefer lossless or near-lossless compression.

Photographs and realistic renders can use high-quality JPEG.

Never convert an image with transparency to ordinary JPEG unless transparency is correctly preserved by another mechanism.

## 5. Effective-DPI-aware compression

Compression decisions must consider the image's displayed dimensions in the PDF.

For example, if a 5000-pixel-wide image is displayed at only 3.5 inches, its effective resolution is about 1400 DPI and is unnecessarily large for a normal scientific paper.

Default scientific-paper policy:

- <= 300 DPI: normally keep untouched
- > 300 DPI: candidate for downsampling
- photographs/renders: target around 250–300 DPI
- plots/line art: preserve losslessly whenever practical
- monochrome line art may use a higher DPI
- never upscale an image

Make these thresholds configurable.

## 6. Target-size mode

This is one of the most important features.

CLI example:

```bash
pdf4sci paper.pdf -o paper_compressed.pdf --target-size 6MB
```

The optimizer should attempt to produce the highest-quality PDF that fits within the requested size.

Do **NOT** immediately apply aggressive compression globally.

Use an iterative strategy.

Example:

```text
Original:             12.4 MB

Optimize oversized photo on page 4
                       8.8 MB

Downsample oversized render on page 6
                       6.7 MB

Slightly reduce JPEG quality on largest image
                       5.95 MB

Target reached. STOP.
```

Prefer modifying the images with the greatest estimated size savings and lowest expected perceptual impact first.

A possible quality search space could include:

- 300 DPI / JPEG quality 95
- 300 DPI / JPEG quality 92
- 300 DPI / JPEG quality 90
- 250 DPI / JPEG quality 92
- 250 DPI / JPEG quality 90
- 200 DPI / JPEG quality 90

But design a better search/optimization strategy if appropriate.

Do not unnecessarily degrade every image merely because a target size was specified.

If the requested target cannot reasonably be achieved without severe degradation, warn the user instead of silently destroying quality.

## 7. Presets

Implement at least:

```text
--preset scientific
--preset maximum-quality
--preset balanced
--preset aggressive
```

The default should be:

```text
scientific
```

Scientific should prioritize preservation of vector content and readable figures.

## 8. Dry-run mode

Support:

```bash
pdf4sci paper.pdf --analyze
pdf4sci paper.pdf --dry-run --target-size 6MB
```

Dry-run should explain exactly what would be modified without writing the final PDF.

Example:

```text
Planned changes:

p2 image #17
  5120x2880 -> 1600x900
  ~1500 DPI -> ~470 DPI
  PNG -> JPEG Q92
  estimated saving: 2.4 MB

p4 image #31
  unchanged

p6 image #52
  4000x3000 -> 1800x1350
  PNG optimized losslessly
  estimated saving: 1.1 MB
```

## 9. Quality validation

This is critical.

After producing the output PDF:

- verify that the PDF can be reopened successfully
- verify page count
- verify page dimensions
- verify text extraction still works
- verify links/annotations where feasible
- verify no obvious missing images
- verify no broken transparency
- verify vector content has not been rasterized

Optionally render input and output pages at a fixed DPI using MuPDF and calculate image-quality metrics.

Useful metrics may include:

- SSIM
- PSNR

However, do not optimize blindly for these metrics.

Provide them primarily as diagnostics.

It would be useful to report something like:

```text
Original: 12.41 MB
Output:    5.87 MB
Reduction: 52.7%

Pages: 8 -> 8
Raster images modified: 3
Raster images preserved: 14
Vector objects: untouched
Text extraction: PASS
PDF reopen test: PASS
```

## 10. Safety

Never overwrite the original PDF by default.

Use:

```text
input.pdf
input_compressed.pdf
```

unless `-o` is explicitly specified.

Before modifying PDF image objects, correctly handle:

- image masks
- soft masks
- transparency
- ICC profiles
- indexed colors
- grayscale images
- CMYK images
- shared image objects
- rotated/transformed images

If an image cannot safely be replaced, leave it untouched and report why.

Robustness is more important than squeezing out another few hundred KB.

## 11. CLI

Use argparse, Typer, or Click.

Desired commands:

```bash
pdf4sci paper.pdf

pdf4sci paper.pdf --analyze

pdf4sci paper.pdf --target-size 6MB

pdf4sci paper.pdf --preset scientific

pdf4sci paper.pdf --max-dpi 300

pdf4sci paper.pdf --min-jpeg-quality 88

pdf4sci paper.pdf --dry-run

pdf4sci paper.pdf --verbose
```

Provide a useful `--help`.

## 12. Logging

Normal output should be clean.

`--verbose` should show detailed decisions:

```text
[KEEP] p1/xref14 vector content
[KEEP] p2/xref22 image already 276 DPI
[OPT ] p3/xref35 4280x2840, 1260 DPI
        -> 1500x995 JPEG Q92
        2.81 MB -> 436 KB
[KEEP] p5/xref61 transparency unsafe to modify
```

At the end show a concise summary.

## 13. Architecture

Do not write everything in one giant Python file.

Use a maintainable structure, for example:

```text
pdf4sci/
    __init__.py
    cli.py
    analyzer.py
    optimizer.py
    images.py
    classifier.py
    quality.py
    validation.py
    config.py

tests/
    test_analyzer.py
    test_optimizer.py
    test_quality.py

pyproject.toml
README.md
```

You may change this architecture if you have a better design.

Keep compression policy separate from low-level PDF manipulation.

## 14. Testing

Create automated tests.

Also create synthetic test PDFs containing combinations of:

- vector graphics
- text
- high-resolution photographs
- PNG plots
- transparency
- repeated images
- grayscale images
- rotated/scaled images

Verify that compression does not accidentally rasterize or destroy unrelated PDF content.

## 15. Benchmark command

Add something like:

```bash
pdf4sci benchmark paper.pdf
```

It should run several reasonable compression configurations and report:

```text
Configuration       Size       Reduction
------------------------------------------------
Original            12.4 MB    -
Maximum quality      8.9 MB    28%
Scientific           5.8 MB    53%
Balanced             4.2 MB    66%
Aggressive           2.1 MB    83%
```

Do not permanently create every intermediate PDF unless requested.

## 16. Future GUI

Do **NOT** prioritize the GUI initially.

Build a reliable compression engine and CLI first.

Design the code so that a PySide6 GUI can later expose:

- drag and drop PDF
- target-size field
- quality slider
- preset selection
- before/after size
- page preview
- image-analysis report
- Compress button

## 17. README

Write a proper README containing:

- what the project does
- why it differs from generic PDF compressors
- installation on Ubuntu
- Python virtual environment setup
- optional native dependencies
- CLI examples
- explanation of presets
- limitations
- architecture overview

Provide commands that I can copy directly on Ubuntu.

## 18. Development approach

Do not attempt to implement every feature simultaneously.

### Phase 1

- project setup
- PDF analysis
- image extraction
- effective DPI calculation
- reporting

### Phase 2

- safe replacement of oversized raster images
- DPI-aware downsampling
- JPEG/lossless optimization

### Phase 3

- target-size optimizer
- image classification
- quality policy

### Phase 4

- validation
- benchmark
- tests

### Phase 5

- optional GUI

At the end of each phase:

1. run the tests
2. show me what works
3. show me known limitations
4. make a git commit with a meaningful commit message
5. continue to the next phase only when the current implementation is stable

Do not merely give me example code or an implementation plan. Actually create the project, implement it, run it, debug it, and test it in the current environment.

When you encounter a PDF feature that cannot safely be handled, preserve it instead of applying a destructive workaround.

## Primary design principle

> **Preserve what is already efficient; optimize only what is wasteful.**
