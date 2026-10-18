"""Check archive reproducibility and isolation from local documents."""
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_release
import validate_skill


class ReleaseTests(unittest.TestCase):
    def test_repository_skill_metadata_and_links(self):
        self.assertEqual(validate_skill.validate(), [])

    def test_archive_is_reproducible_and_excludes_unlisted_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'source'
            for name in build_release.FILES:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            (root / 'private.pdf').write_bytes(b'must not ship')
            (root / '.env').write_text('SECRET=must-not-ship', encoding='utf-8')
            first, digest = build_release.build(root, Path(temporary) / 'first')
            second, second_digest = build_release.build(root, Path(temporary) / 'second')
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(digest, second_digest)
            self.assertEqual(digest, hashlib.sha256(first.read_bytes()).hexdigest())
            self.assertEqual((first.parent / 'SHA256SUMS').read_text().strip(), f'{digest}  {first.name}')
            with zipfile.ZipFile(first) as package:
                self.assertIsNone(package.testzip())
                names = package.namelist()
                self.assertEqual(set(names), {f'pdf-mrc-compression/{name}' for name in build_release.FILES})
                self.assertFalse(any('..' in Path(name).parts or name.startswith('/') for name in names))
                package.extractall(Path(temporary) / 'installed')
            installed = Path(temporary) / 'installed/pdf-mrc-compression'
            self.assertEqual(validate_skill.validate(installed), [])


if __name__ == '__main__':
    unittest.main()
