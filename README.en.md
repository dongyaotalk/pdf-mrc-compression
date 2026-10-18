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
