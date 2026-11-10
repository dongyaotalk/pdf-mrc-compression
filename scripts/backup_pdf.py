#!/usr/bin/env python3
"""Back up a PDF in a visible pdf-mrc-backups directory beside the input."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile


def _signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _copy_and_hash(source, target):
    digest = hashlib.sha256()
    with source.open('rb') as incoming, target.open('xb') as outgoing:
        before = os.fstat(incoming.fileno())
        for block in iter(lambda: incoming.read(1024 * 1024), b''):
            outgoing.write(block)
            digest.update(block)
        outgoing.flush()
        os.fsync(outgoing.fileno())
        if _signature(before) != _signature(os.fstat(incoming.fileno())):
            raise ValueError('Input changed while making the backup')
    return before, digest.hexdigest()


def _sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def backup_pdf(source, stage='before-edit'):
    """Return a manifest only after a complete, independently hashed copy exists.

    Call this before editing an existing PDF. A failed backup raises instead of
    falling back to a different location. This function never edits the input.
    """
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,39}', stage):
        raise ValueError('Stage must be 1–40 ASCII letters, digits, hyphens or underscores')
    source = Path(source).expanduser().absolute()
    # Resolve the parent, not a file symlink: the backup belongs beside the
    # input path the user selected, even when that PDF points elsewhere.
    source = source.parent.resolve(strict=True) / source.name
    if source.suffix.lower() != '.pdf' or not source.is_file():
        raise ValueError(f'Input must be an existing PDF file: {source}')
    root = source.parent / 'pdf-mrc-backups'
    root.mkdir(exist_ok=True)
    if root.is_symlink() or root.resolve() != root:
        raise ValueError(f'Backup directory must not redirect elsewhere: {root}')
    now = datetime.now(timezone.utc)
    prefix = f'{now:%Y%m%dT%H%M%S.%fZ}-{stage}-'
    directory = Path(tempfile.mkdtemp(prefix=prefix, dir=root))
    target = directory / source.name
    try:
        before, digest = _copy_and_hash(source, target)
        shutil.copystat(source, target)
        if target.stat().st_size != before.st_size or _sha256(target) != digest:
            raise ValueError('Backup size or SHA-256 does not match the copied input')
        if _signature(source.stat()) != _signature(before):
            raise ValueError('Input changed before backup verification completed')
        manifest = {
            'source': str(source), 'backup': str(target), 'stage': stage,
            'created_at': now.isoformat(), 'bytes': before.st_size,
            'sha256': digest, 'verified': True,
        }
        with (directory / 'backup.json').open('x', encoding='utf-8') as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='PDF to copy; the input is never modified')
    parser.add_argument('--stage', default='before-edit', help='Stage name, e.g. before-bookmarks')
    args = parser.parse_args()
    try:
        result = backup_pdf(args.input, args.stage)
    except (OSError, ValueError) as error:
        print(f'Backup failed; do not modify the PDF: {error}', file=sys.stderr)
        return 1
    # ASCII JSON also works when Windows redirects stdout with a legacy codec.
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
