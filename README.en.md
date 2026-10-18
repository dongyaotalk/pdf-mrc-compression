# pdf-mrc-compression

[简体中文](README.md) · [Skill instructions](SKILL.md) · [Releases](https://github.com/dongyaotalk/pdf-mrc-compression/releases)

A Codex skill for scanned-PDF Mixed Raster Content (MRC) compression, image repairs,
and measured tradeoffs between size, fidelity, and rendering speed. The skill
instructions and detailed references are written in Chinese; the Python CLIs
provide English help and diagnostics.

Includes three standalone helpers: PDF resource auditing, pixel comparison, and
lossless generic JBIG2 region encoding. **This is not a turnkey whole-book MRC
segmenter.** Segmentation and protected illustration regions must be tailored to
the actual pages.

## Install

Clone this repository into your Codex personal skills directory. The default is
`~/.codex/skills`; if `CODEX_HOME` is set, use its `skills` subdirectory. Check an
existing installation before replacing it.

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/dongyaotalk/pdf-mrc-compression.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/pdf-mrc-compression"
```

Alternatively, download the versioned ZIP from
[Releases](https://github.com/dongyaotalk/pdf-mrc-compression/releases), verify it
against `SHA256SUMS`, and extract its `pdf-mrc-compression` directory into your
skills directory. Reopen Codex and invoke it in a new chat:

```text
Use $pdf-mrc-compression to assess this scanned PDF, preserve color illustrations,
and compare representative samples for size, fidelity, and rendering speed.
```

See the [Chinese README](README.md) for PowerShell installation commands.

## Example prompts

After installing the skill, send one of these prompts directly to Codex. Replace
file names, output directories, and page numbers with your own, and provide input
files Codex can access. Page numbers below are 1-based PDF page numbers. The agent
should choose the processing strategy based on the audit and representative samples.

### 1. Assess whether MRC is appropriate

```text
Use $pdf-mrc-compression to audit input.pdf without generating a compressed copy yet.
Inspect scans, native text/vectors, OCR, image and mask encodings, shared resources, and the largest storage costs.
Identify pages suitable for MRC and pages best preserved as-is. Suggest representative test pages and optimization options.
Save the audit report to output/audit.json.
```

### 2. First compression, prioritizing glyphs and illustrations

```text
Use $pdf-mrc-compression to compress scanned input.pdf into output/input-mrc.pdf.
Prioritize small text, mathematical formulas, superscripts, subscripts, and fine lines. Preserve the colors of illustrations, gray lettering, and covers.
Check representative samples of small text, dense formulas, illustrations, gray title bars, and covers before processing the whole document.
Keep the source file and existing OCR, bookmarks, and links. Do not use lossy symbol substitution.
Report before/after sizes, visual changes, validation scope, and rendering times measured with identical settings.
```

### 3. Further lossless optimization of an existing MRC PDF

```text
Use $pdf-mrc-compression to optimize current-mrc.pdf into output/compact.pdf.
Use current-mrc.pdf as the pixel-equivalence baseline. Only attempt verified lossless encoding, structural optimization, and resource reuse.
Preserve page geometry, text, bookmarks, links, and colors. Do not re-binarize, downsample, or standardize textures.
Compare native decoded pixels of changed images and masks, render every page at the same DPI, check structure, and sample with an independent renderer.
Report bytes saved, rendering performance, and validation limitations. Keep the baseline if no safe improvement is available.
```

### 4. Repair merged strokes, missing illustration regions, and black patches

```text
Use $pdf-mrc-compression to repair compressed.pdf against original.pdf, saving output/repaired.pdf.
The small caption on PDF page 11 has merged strokes; pale parts of the color illustration on page 18 were missed and show black patches.
Adjust only those regions. Protect minus signs, decimal points, superscripts, subscripts, fine illustration lines, and original colors.
Check for duplicate text overlays and verify that content outside the repair regions remains equivalent.
Provide before/after comparisons of the affected regions and validation results.
```

### 5. Reuse gray-bar textures with explicit permission

```text
Use $pdf-mrc-compression to optimize gray title bars in input-mrc.pdf into output/shared-texture.pdf.
I authorize replacing their scanned backgrounds with a visually similar shared texture. Preserve each title's original scanned glyphs and grayscale edges.
Validate representative bars for missing characters, duplicate overlays, seams, and color changes before processing the remaining pages.
Report storage saved by resource reuse, label texture replacement as a visual approximation, and verify content outside the bars.
```

### 6. Diagnose a small PDF that renders slowly

```text
Use $pdf-mrc-compression to investigate rendering performance in small-but-slow.pdf.
Inspect high-resolution masks, redundant transparency layers, repeated drawing, and oversized images. Measure representative page decode costs.
Prioritize fidelity and compare suitable G4, generic JBIG2, constant-foreground, and resource-reuse options.
If size and speed conflict, produce fast-reading and compact versions and compare sizes and rendering times with identical settings.
Describe the scope of offline rendering measurements rather than equating them with actual reader page-turn latency.
```

### 7. Split a scanned jacket and replace the front cover

```text
Use $pdf-mrc-compression to process the jacket in book.pdf and use cover.jpg as the high-resolution front cover.
Identify the actual front-cover, inside-front, inside-back, and back-cover boundaries; do not assume four equal panels.
Order them as front cover, inside front, body, inside back, back cover. Match the body page boxes, preserve aspect ratios, and use whitespace to show each panel fully.
Align the inside front to the left and the inside back to the right. Reuse the original scan image object where possible, except for the replaced cover.
Save output/book-covers.pdf, update bookmarks and links affected by inserted pages, and verify that body content is unchanged.
```

## Dependencies and CLI use

Use Python 3.10+ and install the Python packages in `requirements.txt`. Native tools
are installed separately. See [environment and dependency guidance](references/environment-and-dependencies.md)
for Windows, Linux, and macOS.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/audit_pdf.py input.pdf --output audit.json
.venv/bin/python scripts/verify_lossless.py before.pdf after.pdf --dpi 96 --native-images --report verify.json
.venv/bin/python scripts/encode_jbig2_region.py binary.png mask.jb2
```

On Windows, use `py -3 -m venv .venv` and `.venv\Scripts\python.exe`.
All scripts support `--help`. Auditing and comparison require PyMuPDF; encoding
requires Pillow and the `jbig2` executable from jbig2enc.

The encoder accepts black ink (0) on white paper (255). It never thresholds gray
pixels or substitutes symbols. Its output is a PDF-ready stream, not a PDF or
standalone JBIG2 file. Validate polarity and rendering after embedding.

The verifier exits `0` for a successful comparison, `1` for differences/failures,
and `2` for invalid arguments. Native-image comparison requires stable,
unambiguous image resource names. `--pages` only compares the selected pages.

Initial segmentation, binarization, downsampling, and texture replacement change
pixels. Lossless claims must identify the baseline and validation scope. A match
at one DPI in one renderer does not prove full PDF equivalence. Use qpdf for
structure checks and Poppler for independent rendering; the helpers do not run
these tools automatically. Preserve native vector/text PDFs rather than
rasterizing them just to apply MRC.

## References and development

Start with [SKILL.md](SKILL.md), then read the relevant references on
[segmentation](references/segmentation-and-repairs.md),
[lossless optimization and speed](references/lossless-and-speed.md), or
[covers](references/covers.md). The [case study](references/case-study.md) contains
historical measurements, not guaranteed compression ratios. No book scans are
distributed.

```bash
python -m pip install -r requirements-dev.txt
python tools/validate_skill.py
python -m unittest discover -s tests -v
python tools/build_release.py
```

Tests generate synthetic documents in temporary directories. Optional native
tests require jbig2enc, qpdf, and Poppler; missing tools produce explicit skips.
The Linux integration CI job requires all three.

See [CONTRIBUTING.md](CONTRIBUTING.md) for testing and release instructions and
[CHANGELOG.md](CHANGELOG.md) for version history.

Original project code and documentation: [MIT](LICENSE).
Third-party dependencies retain their own licenses; see [NOTICE.md](NOTICE.md).
