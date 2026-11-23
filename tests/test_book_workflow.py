"""Observable regression coverage for book plans; synthetic PDFs only."""
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import pymupdf as fitz
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import book_utils
import cleanup_outputs
import compress_scans
import normalize_pages
import set_navigation


def png(image):
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    return stream.getvalue()


def scan_doc(image, pages=1):
    doc = fitz.open()
    xref = None
    for _ in range(pages):
        page = doc.new_page(width=image.width, height=image.height)
        if xref:
            page.insert_image(page.rect, xref=xref)
        else:
            xref = page.insert_image(page.rect, stream=png(image))
            # Synthetic fixture intentionally uses uncalibrated device colors.
            # Production ICC-based inputs must stay outside this bounded path.
            doc.xref_set_key(xref, 'ColorSpace', '/DeviceGray' if image.mode == 'L' else '/DeviceRGB')
    return doc


class BookPlans(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mrc book plans ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_labels_only_preserves_manual_navigation_and_raw_image(self):
        with scan_doc(Image.new('L', (40, 50), 0), 9) as doc:
            doc.set_toc([[1, '手改书名', 2], [1, '卷一', 7]])
            before = doc.get_toc(False)
            raw = doc.xref_stream_raw(doc[0].get_images()[0][0])
            set_navigation.apply_navigation(doc, {'labels': [
                {'page': 1, 'style': 'A'}, {'page': 4, 'style': 'R'},
                {'page': 7, 'style': 'D', 'first': 773}]})
            self.assertEqual(doc.get_toc(False), before)
            self.assertEqual([p.get_label() for p in doc], ['A', 'B', 'C', 'I', 'II', 'III', '773', '774', '775'])
            self.assertEqual(doc.xref_stream_raw(doc[0].get_images()[0][0]), raw)
            set_navigation.apply_navigation(doc, {'bookmarks': [
                {'level': 1, 'title': '封面', 'page': 1},
                {'level': 1, 'title': '书名页', 'page': 2},
                {'level': 1, 'title': '版权页', 'page': 3}]})
            self.assertEqual([row[1] for row in doc.get_toc()], ['封面', '书名', '版权'])
            set_navigation.apply_navigation(doc, {'labels': [
                {'page': 1, 'style': 'A'}, {'page': 4, 'style': 'D', 'first': 773}]})
            self.assertEqual(doc[3].get_label(), '773')

    def test_navigation_preflights_entire_plan_and_does_not_invent_copyright(self):
        with scan_doc(Image.new('L', (10, 10), 255), 4) as doc:
            doc.set_toc([[1, '封面', 1], [1, '书名', 2]])
            before = doc.get_toc()
            with self.assertRaises(ValueError):
                set_navigation.apply_navigation(doc, {'bookmarks': [], 'labels': [{'page': 2, 'style': 'R'}]})
            self.assertEqual(doc.get_toc(), before)
            set_navigation.apply_navigation(doc, {'labels': [{'page': 1, 'style': 'A'}, {'page': 4, 'style': 'D'}]})
            self.assertNotIn('版权', [entry[1] for entry in doc.get_toc()])

    def test_geometry_preserves_native_shared_stream_ocr_and_navigation(self):
        with scan_doc(Image.new('L', (40, 60), 127), 2) as doc:
            first = doc[0]
            first.set_mediabox(fitz.Rect(0, 0, 400, 600))
            first.insert_text((20, 100), 'OCR evidence', render_mode=3)
            doc[1].set_rotation(90)
            first = doc[0]
            first.insert_link({'kind': fitz.LINK_GOTO, 'from': fitz.Rect(10, 10, 30, 30), 'page': 1, 'to': fitz.Point(10, 20)})
            doc.set_toc([[1, 'Book', 1], [1, 'Landscape', 2]])
            # Reload is required by PyMuPDF to expose newly inserted links.
            data = doc.tobytes()
        with fitz.open(stream=data, filetype='pdf') as doc:
            xref = doc[0].get_images()[0][0]
            before = doc.xref_stream_raw(xref)
            old_to = doc[0].get_links()[0]['to']
            normalize_pages.normalize(doc, {'size': [200, 300]})
            self.assertEqual(doc.xref_stream_raw(xref), before)
            self.assertIn('OCR evidence', doc[0].get_text())
            self.assertEqual(doc[1].rotation, 90)
            self.assertEqual(tuple(doc[0].mediabox), (0, 0, 200, 300))
            self.assertEqual(doc.get_toc()[1][1], 'Landscape')
            saved = doc.tobytes()
        with fitz.open(stream=saved, filetype='pdf') as doc:
            self.assertAlmostEqual(doc[0].get_links()[0]['from'].x0, 5)
            self.assertAlmostEqual(doc[0].get_links()[0]['to'].x, old_to.x * 5)

    def test_explicit_scan_rotation_repair_and_complex_page_rejection(self):
        image = Image.new('L', (40, 60), 255)
        ImageDraw.Draw(image).rectangle((1, 2, 10, 20), fill=0)
        with scan_doc(image) as doc:
            xref = doc[0].get_images()[0][0]
            raw = doc.xref_stream_raw(xref)
            doc[0].set_rotation(90)
            normalize_pages.normalize(doc, {'size': [200, 300], 'scan_repairs': [{'page': 1, 'rect': [0, 0, 200, 300]}]})
            self.assertEqual(doc[0].rotation, 0)
            self.assertEqual(doc.xref_stream_raw(xref), raw)
            pix = doc[0].get_pixmap(matrix=fitz.Matrix(.2, .2), colorspace=fitz.csGRAY)
            self.assertEqual(pix.samples, image.tobytes())
            doc[0].add_text_annot((5, 5), 'retain appearance')
            with self.assertRaisesRegex(ValueError, 'Annotated'):
                normalize_pages.normalize(doc, {'size': [100, 150]})

    def test_atomic_save_session_reuse_external_edit_and_separate_output(self):
        source, output, session = self.root / 'book.pdf', self.root / 'copy.pdf', self.root / 'session.json'
        with scan_doc(Image.new('L', (10, 10), 255)) as doc:
            doc.save(source)
        original = source.read_bytes()
        with fitz.open(source) as doc:
            book_utils.save_pdf(doc, source, output, session)
        self.assertFalse((self.root / 'pdf-mrc-backups').exists())
        for value in ('one', 'two'):
            with fitz.open(output) as doc:
                doc.set_metadata({'title': value})
                book_utils.save_pdf(doc, output, output, session)
        self.assertEqual(len(list((self.root / 'pdf-mrc-backups').iterdir())), 1)
        with fitz.open(output) as doc:
            doc.set_metadata({'title': 'external'})
            changed = doc.tobytes()
        output.write_bytes(changed)
        with fitz.open(output) as doc:
            book_utils.save_pdf(doc, output, output, session)
        self.assertEqual(len(list((self.root / 'pdf-mrc-backups').iterdir())), 2)
        self.assertEqual(source.read_bytes(), original)

    def test_cleanup_scope_keeps_pdfs_description_and_backups_until_requested(self):
        root = self.root / 'book'
        backup = root / 'pdf-mrc-backups' / 'task'
        backup.mkdir(parents=True)
        for path in (root / 'book.PDF', root / '说明.md', root / 'log.json', backup / 'original.pdf', backup / 'backup.json'):
            path.write_text('synthetic')
        other = self.root / 'other.txt'
        other.write_text('unrelated')
        preview = cleanup_outputs.cleanup(root, {'keep': ['说明.md']})
        self.assertEqual(preview['would_remove'], ['log.json'])
        self.assertTrue((root / 'log.json').exists())
        cleanup_outputs.cleanup(root, {'keep': ['说明.md']}, apply=True)
        self.assertTrue((backup / 'backup.json').exists())
        cleanup_outputs.cleanup(root, {'keep': ['说明.md'], 'delete_backups': ['pdf-mrc-backups']}, apply=True)
        self.assertEqual(sorted(p.name for p in root.iterdir()), ['book.PDF', '说明.md'])
        self.assertTrue(other.exists())
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['book', 'other.txt'])
        with self.assertRaises(ValueError):
            cleanup_outputs.cleanup(root, {'keep': [], 'delete_backups': ['../other.txt']}, True)

    def test_partial_backup_cleanup_preserves_other_tasks_manifests(self):
        root = self.root / 'deliver'
        for name in ('this-task', 'other-task'):
            backup = root / 'pdf-mrc-backups' / name
            backup.mkdir(parents=True)
            (backup / 'original.pdf').write_bytes(b'original')
            (backup / 'backup.json').write_text('{}')
        cleanup_outputs.cleanup(root, {'keep': [], 'delete_backups': ['pdf-mrc-backups/this-task']}, True)
        self.assertFalse((root / 'pdf-mrc-backups/this-task').exists())
        self.assertTrue((root / 'pdf-mrc-backups/other-task/backup.json').exists())
        with self.assertRaises(ValueError):
            cleanup_outputs.cleanup(root, {'keep': ['missing-notes.md']}, True)
        self.assertTrue((root / 'pdf-mrc-backups/other-task/original.pdf').exists())

    def test_cli_plans_work_with_space_paths_and_no_render_for_labels(self):
        source = self.root / 'source scan.pdf'
        with scan_doc(Image.new('L', (40, 60), 255), 4) as doc:
            doc.set_toc([[1, 'Manual title', 2]])
            doc.save(source)
        for script, plan in (
            ('normalize_pages', {'size': [80, 120]}),
            ('compress_scans', {'pages': [1, 2, 3, 4], 'codec': 'g4'}),
            ('set_navigation', {'labels': [{'page': 1, 'style': 'A'}, {'page': 4, 'style': 'D', 'first': 773}]}),
        ):
            output = self.root / (script + '.pdf')
            plan_file = self.root / (script + '.json')
            plan_file.write_text(json.dumps(plan))
            result = subprocess.run([sys.executable, str(ROOT / 'scripts' / (script + '.py')), str(source),
                                     str(output), '--plan', str(plan_file)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with fitz.open(output) as final:
                self.assertEqual(len(final), 4)
                self.assertEqual(final.get_toc()[0][1], 'Manual title')
                if script == 'set_navigation':
                    self.assertEqual(final[3].get_label(), '773')
                    self.assertIn('not independently validated', json.loads(result.stdout)['validation'])
            source = output



class NativeScanCompression(unittest.TestCase):
    def sample(self):
        image = Image.new('L', (257, 197), 255)
        ImageDraw.Draw(image).rectangle((19, 20, 57, 160), fill=0)
        return image

    def test_g4_native_and_sparse_gray_target_actual_pdf(self):
        for gray in (None, 67, 127, 191, 254):
            image = self.sample()
            if gray:
                image.putpixel((100, 120), gray)
            with self.subTest(gray=gray), scan_doc(image) as doc:
                doc.set_toc([[1, '书名', 1]])
                report = compress_scans.compress(doc, {'pages': [1], 'codec': 'g4', 'max_gray_pixels': 1})
                self.assertEqual(len(report['changed']), 1)
                self.assertEqual(doc.get_toc(), [[1, '书名', 1]])
                data = doc.tobytes(garbage=4, deflate=True)
            with fitz.open(stream=data, filetype='pdf') as final:
                pix = final[0].get_pixmap(colorspace=fitz.csGRAY)
                self.assertEqual(pix.samples, image.tobytes())

    def test_large_scan_is_one_g4_strip_and_keeps_native_pixels(self):
        image = Image.new('L', (1025, 1100), 255)
        draw = ImageDraw.Draw(image)
        for y in range(10, 1090, 40):
            draw.line((20, y, 1000, y), fill=0, width=2)
        with scan_doc(image) as doc:
            report = compress_scans.compress(doc, {'pages': [1], 'codec': 'g4'})
            self.assertEqual(len(report['changed']), 1)
            self.assertLess(report['changed'][0]['binary_stream_bytes'], 20000)

    def test_threshold_explicit_target_gray_protection_and_shared_uses(self):
        image = self.sample()
        image.putpixel((100, 120), 127)
        image.putpixel((105, 120), 250)
        with scan_doc(image, 2) as doc:
            report = compress_scans.compress(doc, {'pages': [1], 'codec': 'g4', 'threshold': 128})
            self.assertEqual(report['changed'], [])
            report = compress_scans.compress(doc, {'pages': [1, 2], 'codec': 'g4', 'threshold': 128,
                                                   'protect_gray': [64, 191], 'max_gray_pixels': 1})
            self.assertEqual(len(report['changed']), 1)
            target = image.point(lambda v: 0 if v < 128 else 255)
            target.putpixel((100, 120), 127)
            self.assertEqual(doc[0].get_pixmap(colorspace=fitz.csGRAY).samples, target.tobytes())

    def test_continuous_gray_color_and_nonopaque_mask_preserved(self):
        for image in (Image.new('L', (20, 30), 100), Image.new('RGB', (20, 30), 'red'),
                      Image.new('RGBA', (20, 30), (0, 0, 0, 150))):
            with self.subTest(mode=image.mode), scan_doc(image) as doc:
                before = doc[0].get_pixmap().samples
                report = compress_scans.compress(doc, {'pages': [1], 'codec': 'g4'})
                self.assertEqual(report['changed'], [])
                self.assertEqual(doc[0].get_pixmap().samples, before)

    def test_icc_color_management_is_not_discarded(self):
        with fitz.open() as doc:
            page = doc.new_page(width=20, height=30)
            xref = page.insert_image(page.rect, stream=png(Image.new('L', (20, 30), 255)))
            # Pin an explicit calibrated color space on all supported versions.
            doc.xref_set_key(xref, 'ColorSpace', '[/CalGray << /WhitePoint [1 1 1] >>]')
            before = doc.xref_object(xref)
            result = compress_scans.compress(doc, {'pages': [1], 'codec': 'g4'})
            self.assertEqual(result['changed'], [])
            self.assertEqual(doc.xref_object(xref), before)

    def test_cache_corruption_and_changed_target_do_not_reuse_bad_stream(self):
        with tempfile.TemporaryDirectory() as folder:
            keys = []
            for threshold in (100, 150, 100):
                with scan_doc(self.sample()) as doc:
                    result = compress_scans.compress(doc, {'pages': [1], 'codec': 'g4', 'threshold': threshold}, folder)
                    keys.append(result['changed'][0]['cache_key'])
                if len(keys) == 1:
                    (Path(folder) / (keys[-1] + '.bin')).write_bytes(b'corrupt')
            self.assertEqual(keys[0], keys[2])
            self.assertNotEqual(keys[0], keys[1])

    def test_jbig2_g4_independent_render_and_qpdf(self):
        missing = [name for name in ('jbig2', 'qpdf', 'pdftoppm') if not shutil.which(name)]
        if missing:
            if os.environ.get('MRC_REQUIRE_NATIVE') == '1':
                self.fail('Missing native tools: ' + ', '.join(missing))
            self.skipTest('Missing native tools: ' + ', '.join(missing))
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            for gray in (None, 127):
                image = self.sample()
                if gray:
                    image.putpixel((100, 120), gray)
                renders = []
                reference = folder / 'reference.pdf'
                with scan_doc(image) as reference_doc:
                    reference_doc.save(reference)
                for codec in ('reference', 'g4', 'jbig2'):
                    pdf = folder / f'{codec}.pdf'
                    if codec != 'reference':
                        with scan_doc(image) as doc:
                            report = compress_scans.compress(doc, {'pages': [1], 'codec': codec, 'max_gray_pixels': 1})
                            self.assertEqual(len(report['changed']), 1)
                            doc.save(pdf, garbage=4, deflate=True)
                    result = subprocess.run(['qpdf', '--check', str(pdf)], capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    prefix = folder / codec
                    result = subprocess.run(['pdftoppm', '-singlefile', '-r', '72', '-gray', str(pdf), str(prefix)], capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    with Image.open(prefix.with_suffix('.pgm')) as rendered:
                        renders.append(rendered.tobytes())
                # Separate alpha compositing can round differently by one
                # gray level in Poppler, even when native target pixels agree.
                for rendered in renders[1:]:
                    self.assertLessEqual(max(abs(a-b) for a, b in zip(renders[0], rendered)), 1 if gray else 0)
                self.assertEqual(renders[1], renders[2])


if __name__ == '__main__':
    unittest.main()
