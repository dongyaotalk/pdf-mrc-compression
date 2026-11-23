"""Shared bounded-plan and atomic-output mechanics (Python 3.10+)."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile

from backup_pdf import backup_pdf


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_plan(path, allowed):
    plan = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(plan, dict) or set(plan) - set(allowed):
        raise ValueError('Plan must be an object with only documented keys')
    return plan


def page_number(value, count):
    if type(value) is not int or not 1 <= value <= count:
        raise ValueError(f'Physical page must be an integer in 1..{count}: {value}')
    return value - 1


def check_edit_paths(source, output, plan, session=None):
    protected = {Path(source).resolve(), Path(output).resolve(), Path(plan).resolve()}
    if Path(output).resolve() == Path(plan).resolve():
        raise ValueError('Output must not overwrite the plan')
    if session and (Path(session).resolve() in protected or Path(session).is_symlink()):
        raise ValueError('Session must be separate from inputs, output and plan')


@contextmanager
def open_pdf(path):
    # Lazy import keeps standard-library backup/cleanup tools independent.
    import pymupdf
    doc = pymupdf.open(path)
    try:
        yield doc
    finally:
        if not doc.is_closed:
            doc.close()


def save_pdf(doc, source, output, session=None):
    """Consume/close doc and save atomically with visible backup reuse.

    A session is local task state, never a substitute for the independently
    verified backup. An external edit invalidates reuse.
    """
    source, output = Path(source).resolve(), Path(output).absolute()
    if output.suffix.lower() != '.pdf' or output.is_symlink():
        raise ValueError('Output must be a regular .pdf path, not a symlink')
    output.parent.mkdir(parents=True, exist_ok=True)
    output = output.parent.resolve() / output.name
    state = {}
    if session:
        session = Path(session).absolute()
        if session.resolve() in (source, output.resolve()) or session.suffix.lower() == '.pdf':
            raise ValueError('Session must be a separate non-PDF task state file')
        if session.is_symlink():
            raise ValueError('Session must not be a symlink')
        if session.exists():
            state = json.loads(session.read_text(encoding='utf-8'))
            if not isinstance(state, dict):
                raise ValueError('Session must contain a task-state object')
    key = str(output)
    if output.exists():
        current = sha256(output)
        previous = state.get(key, {})
        manifest = previous.get('baseline') or {}
        backup = Path(manifest.get('backup', ''))
        reuse = (previous.get('current_sha256') == current and manifest.get('verified') is True
                 and backup.is_file() and sha256(backup) == manifest.get('sha256')
                 and backup.parent.parent == output.parent / 'pdf-mrc-backups')
        if not reuse:
            manifest = backup_pdf(output, 'before-book-edit')
    else:
        manifest = None
    fd, temp = tempfile.mkstemp(prefix='.mrc-save-', suffix='.pdf', dir=output.parent)
    os.close(fd)
    try:
        # PDF_ENCRYPT_KEEP == 0; preserve source encryption rather than remove it.
        doc.save(temp, garbage=0, deflate=False, encryption=0)
        # Windows cannot replace an input PDF while MuPDF holds it open.
        doc.close()
        os.replace(temp, output)
    finally:
        Path(temp).unlink(missing_ok=True)
    if session:
        state[key] = {'baseline': manifest, 'current_sha256': sha256(output)}
        session.parent.mkdir(parents=True, exist_ok=True)
        session.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'output': str(output), 'backup': manifest, 'validation': 'not run by save helper'}
