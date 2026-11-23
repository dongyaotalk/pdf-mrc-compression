#!/usr/bin/env python3
"""Preview/apply bounded non-PDF cleanup; backups need explicit deletion scope."""
import argparse
import json
from pathlib import Path
import shutil

from book_utils import read_plan


def cleanup(root, plan, apply=False):
    root = Path(root).absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Cleanup root must be an existing real directory')
    root = root.resolve()
    if set(plan) - {'keep', 'delete_backups'} or 'keep' not in plan:
        raise ValueError('Expected keep; optional delete_backups')
    keep = plan['keep']
    delete_backups = plan.get('delete_backups', [])
    if not isinstance(keep, list) or not isinstance(delete_backups, list):
        raise ValueError('keep and delete_backups must be lists')
    def relative(value):
        if not isinstance(value, str):
            raise ValueError('Cleanup entries must be relative paths')
        name = Path(value)
        if name.is_absolute() or '..' in name.parts or not name.parts:
            raise ValueError('Cleanup entry escapes target directory')
        path = root / name
        for part in [path, *path.parents]:
            if part == root:
                break
            if part.is_symlink():
                raise ValueError('Cleanup entries must not follow symlinks')
        return path
    protected = {relative(value) for value in keep}
    backups = {relative(value) for value in delete_backups}
    if any(not path.exists() for path in protected):
        raise ValueError('Retained entry does not exist; check keep paths before deletion')
    for item in backups:
        # These are explicit selected recovery entries, never an implicit glob
        # across other books or the entire machine.
        if item == root or any(p == item or item in p.parents or p in item.parents for p in protected):
            raise ValueError('Backup deletion overlaps a retained entry')
    removed, retained, candidates = [], [], []
    def walk(directory, backup_zone=False):
        for path in sorted(directory.iterdir()):
            if path in protected or any(p in path.parents for p in protected):
                retained.append(str(path.relative_to(root)))
                continue
            if path in backups:
                candidates.append(path)
                continue
            if backup_zone:
                if path.is_dir() and not path.is_symlink() and any(path in p.parents for p in backups):
                    walk(path, True)
                else:
                    retained.append(str(path.relative_to(root)))
                continue
            if path.is_symlink():
                # Never traverse links. Keep them for a task-specific decision.
                retained.append(str(path.relative_to(root)))
            elif path.is_dir():
                if path.name == 'pdf-mrc-backups':
                    if any(path in p.parents for p in backups):
                        walk(path, True)
                    else:
                        retained.append(str(path.relative_to(root)))
                else:
                    walk(path)
            elif path.suffix.lower() == '.pdf':
                retained.append(str(path.relative_to(root)))
            elif path.is_file():
                candidates.append(path)
    walk(root)
    for path in candidates:
        removed.append(str(path.relative_to(root)))
        if apply:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    # Remove only empty directories, leaving every surviving PDF and keep item.
    if apply:
        directories = sorted((p for p in root.rglob('*') if p.is_dir() and not p.is_symlink()),
                             key=lambda p: len(p.parts), reverse=True)
        for directory in directories:
            if (directory in protected or any(p in directory.parents for p in protected)
                    or ('pdf-mrc-backups' in directory.relative_to(root).parts
                        and not any(p == directory or p in directory.parents or directory in p.parents for p in backups))):
                continue
            try:
                directory.rmdir()
            except OSError:
                pass  # Nonempty directories retain protected files.
    return {'applied': apply, 'removed' if apply else 'would_remove': removed,
            'retained': retained, 'recovery_copy_created': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--apply', action='store_true', help='Delete the previewed entries within this directory')
    args = parser.parse_args()
    try:
        result = cleanup(args.directory, read_plan(args.plan, ('keep', 'delete_backups')), args.apply)
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f'Cleanup failed: {error}\n')


if __name__ == '__main__':
    main()
