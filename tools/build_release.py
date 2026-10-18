#!/usr/bin/env python3
"""Build an allowlisted skill ZIP and SHA256SUMS using only the standard library."""
import argparse
import hashlib
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'SKILL.md', 'agents/openai.yaml', 'requirements.txt', 'VERSION',
    'LICENSE', 'NOTICE.md', 'README.md', 'README.en.md', 'CHANGELOG.md',
    'CONTRIBUTING.md', 'requirements-dev.txt',
    'tools/validate_skill.py', 'tools/build_release.py',
    '.github/workflows/ci.yml',
    'scripts/audit_pdf.py', 'scripts/verify_lossless.py', 'scripts/encode_jbig2_region.py',
    'references/environment-and-dependencies.md', 'references/segmentation-and-repairs.md',
    'references/lossless-and-speed.md', 'references/covers.md', 'references/case-study.md',
    'tests/test_helpers.py', 'tests/test_release.py',
)


def build(root=ROOT, output=None):
    version = (root / 'VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('VERSION must contain MAJOR.MINOR.PATCH')
    for name in FILES:
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Missing or symlinked release input: {name}')
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f'Release input escapes repository: {name}')
    output = output if output is not None else root / 'dist'
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'pdf-mrc-compression-{version}.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for name in sorted(FILES):
            info = zipfile.ZipInfo(f'pdf-mrc-compression/{name}', date_time=(2020, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            # Normalize checkout line endings for Windows and Unix builds.
            data = (root / name).read_bytes().replace(b'\r\n', b'\n')
            package.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / 'SHA256SUMS').write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    return archive, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Output directory; defaults to dist/')
    args = parser.parse_args()
    archive, digest = build(output=args.output)
    print(f'{archive}\nSHA256: {digest}')


if __name__ == '__main__':
    main()
