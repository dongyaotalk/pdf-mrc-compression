# pdf-mrc-compression

[简体中文](README.md) · [Skill instructions](SKILL.md) · [Releases](https://github.com/dongyaotalk/pdf-mrc-compression/releases)

Current version: **[v0.3.0](https://github.com/dongyaotalk/pdf-mrc-compression/releases/tag/v0.3.0)** · [Download ZIP](https://github.com/dongyaotalk/pdf-mrc-compression/releases/download/v0.3.0/pdf-mrc-compression-0.3.0.zip) · [SHA256SUMS](https://github.com/dongyaotalk/pdf-mrc-compression/releases/download/v0.3.0/SHA256SUMS)

**New in v0.3.0: scanned-book workflows.** Explicit JSON plans now support page geometry, native-grid G4/generic JBIG2 with sparse-gray protection, bookmarks/page labels, and bounded cleanup. Validation follows the operation; continuous edits can reuse a verified visible baseline backup. See the [book workflow](references/book-workflow.md) and [changelog](CHANGELOG.md).

A Codex skill for scanned-PDF MRC compression, image repairs, and measured tradeoffs between size, fidelity, and rendering speed. Instructions and detailed references are in Chinese; Python CLIs provide English help and diagnostics.

The native scan path has deliberate support limits and preserves unsupported pages. Complex color segmentation and illustration protection still need plans based on actual samples. This is not a general-purpose automatic MRC segmenter. Native text/vector PDFs are not rasterized just to use this skill.

## Install

Clone this repository into your Codex personal skills directory. The default is
`~/.codex/skills`; if `CODEX_HOME` is set, use its `skills` subdirectory. Check an
existing installation before replacing it.

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/dongyaotalk/pdf-mrc-compression.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/pdf-mrc-compression"
```

Alternatively, download the [v0.3.0 ZIP](https://github.com/dongyaotalk/pdf-mrc-compression/releases/download/v0.3.0/pdf-mrc-compression-0.3.0.zip), verify it
against [SHA256SUMS](https://github.com/dongyaotalk/pdf-mrc-compression/releases/download/v0.3.0/SHA256SUMS), and extract its `pdf-mrc-compression` directory into your
skills directory. Reopen Codex and invoke it in a new chat:

```text
Use $pdf-mrc-compression to assess this scanned PDF, preserve color illustrations,
and compare representative samples for size, fidelity, and rendering speed.
```

See the [Chinese README](README.md) for PowerShell installation commands.

## Update an existing installation

- **Git installation:** run `git status --short` in the actual skill directory.
  After preserving any local changes, update a clean checkout with `git pull --ff-only`.
- **ZIP installation:** download the ZIP above, verify `SHA256SUMS`, preserve your
  customizations, and replace the old `pdf-mrc-compression` folder with the new one.
  Existing Python and native dependencies do not need to be downloaded again.
- Reopen Codex and use the skill in a new chat. Existing PDFs, historical backups,
  and encoding caches are not automatically moved or deleted.

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

### 8. Continue a multi-volume book using earlier volumes

```text
Use $pdf-mrc-compression to optimize this scanned series. Volumes 1–3 already have compressed editions; extract their actual strategy and apply it to volumes 4–7.
Audit normal body sizes, unusual rotation, gray/color content and shared resources. Use native bilevel encoding only where appropriate; protect continuous tones and illustrations.
After compression, restore the printed contents hierarchy and actual cover, title, copyright, division-title and back-cover bookmarks. Use the exact auxiliary names “书名” and “版权”; do not invent copyright bookmarks for blank pages.
Propose physical-page mappings and labels based on each volume's printed numbering before applying them. Processing notes should describe operations without machine paths or a full contents listing.
```

### 9. Change labels only, keeping manual bookmarks

```text
Use $pdf-mrc-compression to change only the page labels in ready.pdf. Keep all my manually edited bookmarks.
Physical pages 1–3 use A, B, C; pages 4–19 use uppercase Roman I–XVI; page 20 starts Arabic 1, continuing through end matter and the back cover.
The page order is already confirmed. Skip extra validation, apply the change directly and record it as unvalidated. Do not recompress or render the entire book.
```

### 10. Clean the delivery directory

```text
Use $pdf-mrc-compression to clean this book's specified directory. Keep all final PDFs and the processing notes; remove the remaining files belonging to this task.
Keep only completed operations in the notes, without storage locations, caches, logs or a complete chapter listing.
I also authorize removing this task's backups and recovery archives. Do not create hidden replacement backups or touch other books.
```

## Dependencies and CLI use

Before modifying an existing PDF (for example, its bookmarks or page labels),
save the backup in a **visible `pdf-mrc-backups/` directory beside the input PDF**.
Do not put persistent PDF backups in hidden work directories or the skill installation.
`backup_pdf.py` preserves the filename, creates a unique stage directory for each call,
independently verifies the copy's size and SHA-256, and reports its actual path with a
`backup.json` recovery record. Stop the PDF edit if backup fails; do not fall back to
another location. No extra original copy is needed when writing a new output without
changing the input. Existing backups are not automatically moved or deleted.
See [backup and work-file locations](references/backups-and-work-files.md).

Use Python 3.10+ and install the Python packages in `requirements.txt`. Native tools
are installed separately. See [environment and dependency guidance](references/environment-and-dependencies.md)
for Windows, Linux, and macOS.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/audit_pdf.py input.pdf --output audit.json
.venv/bin/python scripts/backup_pdf.py input.pdf --stage before-bookmarks
.venv/bin/python scripts/verify_lossless.py before.pdf after.pdf --dpi 96 --native-images --report verify.json
.venv/bin/python scripts/encode_jbig2_region.py binary.png mask.jb2
```

On Windows, use `py -3 -m venv .venv` and `.venv\Scripts\python.exe`.
All scripts support `--help`. Auditing and comparison require PyMuPDF; encoding
requires Pillow and the `jbig2` executable from jbig2enc.
The backup helper needs only Python's standard library and never modifies the PDF.

Additional plan-based tools (all physical page numbers are **1-based**):

| Tool | Scope |
|---|---|
| `normalize_pages.py` | Aspect-fit page size, explicit single-scan placement repair; no image resampling |
| `compress_scans.py` | Selected native scans, G4/generic JBIG2, bounded sparse-gray protection |
| `set_navigation.py` | Explicit bookmarks and/or label segments; omitted structures stay intact |
| `cleanup_outputs.py` | Keep PDFs and named notes; preview by default, `--apply` to delete; backups need explicit selection |

```bash
python scripts/normalize_pages.py input.pdf sized.pdf --plan geometry.json
python scripts/compress_scans.py sized.pdf compact.pdf --plan compression.json --cache work/encoding
python scripts/set_navigation.py compact.pdf ready.pdf --plan navigation.json
python scripts/cleanup_outputs.py books --plan cleanup.json
```

For example, `compression.json` can contain `{"pages": [4, 5], "codec": "g4", "max_gray_pixels": 8}`: it preserves binary pixels and at most eight gray pixels per selected image, keeping continuous-tone images unchanged. Binarization requires an explicit `threshold` and changes the baseline. Default checks compare installed native target pixels; `--skip-validation` explicitly records that checks were skipped. Structure and representative independent rendering remain separate delivery checks.

A labels-only plan might be `{"labels": [{"page": 1, "style": "A"}, {"page": 4, "style": "D", "first": 773}]}`. It keeps existing bookmarks. A provided `bookmarks` array replaces the tree, so omit it when preserving manual edits. See [geometry](references/page-geometry.md), [scan encoding](references/segmentation-and-repairs.md), [navigation](references/navigation-and-labels.md), and [cleanup](references/backups-and-work-files.md) for complete examples and limits.

The three PDF editing tools accept `--session work/session.json` to reuse a verified visible backup within one continuous task; external changes invalidate reuse. Metadata-only work does not require whole-book raster validation. Processing notes describe completed operations, without directory paths or log dumps.

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
[book workflows](references/book-workflow.md),
[page geometry](references/page-geometry.md),
[navigation and labels](references/navigation-and-labels.md),
[backups and work files](references/backups-and-work-files.md),
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
