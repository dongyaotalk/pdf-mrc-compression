"""Exercise visible backup placement, independent copies and failure protection."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('backup_pdf', ROOT / 'scripts/backup_pdf.py')
backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup)


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='pdf backup test ')
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name).resolve()
        self.source = self.folder / '扫描 资料.PDF'
        self.original = b'%PDF-1.4\nsynthetic backup fixture\n%%EOF\n'
        self.source.write_bytes(self.original)

    def test_visible_sibling_backup_and_recoverable_manifest(self):
        result = backup.backup_pdf(self.source, 'before-bookmarks')
        target = Path(result['backup'])
        self.assertEqual(target.parent.parent, self.folder / 'pdf-mrc-backups')
        self.assertEqual(target.name, self.source.name)
        self.assertEqual(target.read_bytes(), self.original)
        self.assertEqual(result['sha256'], hashlib.sha256(self.original).hexdigest())
        self.assertEqual(result['bytes'], len(self.original))
        self.assertEqual(json.loads((target.parent / 'backup.json').read_text(encoding='utf-8')), result)
        self.assertTrue(result['verified'])
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_repeated_backups_do_not_overwrite_and_are_not_hardlinks(self):
        first = backup.backup_pdf(self.source)
        self.source.write_bytes(b'%PDF-1.4\nchanged\n%%EOF\n')
        second = backup.backup_pdf(self.source)
        self.assertNotEqual(first['backup'], second['backup'])
        self.assertEqual(Path(first['backup']).read_bytes(), self.original)
        self.assertEqual(Path(second['backup']).read_bytes(), self.source.read_bytes())

    def test_write_failure_leaves_input_unchanged_and_no_completed_backup(self):
        with patch.object(backup, '_copy_and_hash', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                backup.backup_pdf(self.source)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(list((self.folder / 'pdf-mrc-backups').iterdir()), [])

    def test_corrupt_backup_is_rejected(self):
        with patch.object(backup, '_sha256', return_value='wrong'):
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                backup.backup_pdf(self.source)
        self.assertEqual(list((self.folder / 'pdf-mrc-backups').iterdir()), [])

    def test_input_changed_during_verification_is_rejected(self):
        original_hash = backup._sha256
        def mutate_source(target):
            self.source.write_bytes(b'%PDF-1.4\nchanged during verification\n%%EOF\n')
            return original_hash(target)
        with patch.object(backup, '_sha256', side_effect=mutate_source):
            with self.assertRaisesRegex(ValueError, 'Input changed'):
                backup.backup_pdf(self.source)
        self.assertEqual(list((self.folder / 'pdf-mrc-backups').iterdir()), [])

    def test_blocked_backup_directory_does_not_fall_back_elsewhere(self):
        (self.folder / 'pdf-mrc-backups').write_text('not a directory', encoding='utf-8')
        with self.assertRaises(OSError):
            backup.backup_pdf(self.source)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(len(list(self.folder.iterdir())), 2)

    def test_rejects_invalid_stage_and_missing_input_without_creating_backups(self):
        for stage in ['../hidden', '.hidden', 'path/name', 'a' * 41]:
            with self.assertRaises(ValueError):
                backup.backup_pdf(self.source, stage)
        with self.assertRaises(ValueError):
            backup.backup_pdf(self.folder / 'missing.pdf')
        self.assertFalse((self.folder / 'pdf-mrc-backups').exists())

    def test_cli_prints_actual_backup_path(self):
        run = subprocess.run([sys.executable, str(ROOT / 'scripts/backup_pdf.py'),
                              str(self.source), '--stage', 'before-page-labels'],
                             capture_output=True, encoding='utf-8', check=False)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertEqual(Path(result['backup']).read_bytes(), self.original)
        self.assertEqual(result['stage'], 'before-page-labels')

    def test_cli_failure_reports_nonzero_without_modifying_input(self):
        (self.folder / 'pdf-mrc-backups').write_text('blocked', encoding='utf-8')
        run = subprocess.run([sys.executable, str(ROOT / 'scripts/backup_pdf.py'), str(self.source)],
                             capture_output=True, encoding='utf-8', check=False)
        self.assertEqual(run.returncode, 1)
        self.assertIn('do not modify the PDF', run.stderr)
        self.assertEqual(run.stdout, '')
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_file_symlink_backup_stays_beside_selected_input(self):
        selected = self.folder / 'selected'
        selected.mkdir()
        link = selected / 'selected.pdf'
        try:
            link.symlink_to(self.source)
        except (OSError, NotImplementedError):
            self.skipTest('File symlinks are unavailable for this user')
        result = backup.backup_pdf(link)
        self.assertEqual(Path(result['backup']).parent.parent, selected / 'pdf-mrc-backups')
        self.assertEqual(Path(result['backup']).name, link.name)
        self.assertEqual(Path(result['backup']).read_bytes(), self.original)

    def test_backup_directory_cannot_redirect_to_hidden_storage(self):
        hidden = self.folder / '.hidden'
        hidden.mkdir()
        link = self.folder / 'pdf-mrc-backups'
        try:
            link.symlink_to(hidden, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('Directory symlinks are unavailable for this user')
        with self.assertRaisesRegex(ValueError, 'redirect elsewhere'):
            backup.backup_pdf(self.source)
        self.assertEqual(list(hidden.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
