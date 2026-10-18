"""Synthetic regression tests; no private PDFs or external downloads are used."""
import argparse
from contextlib import redirect_stderr
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import pymupdf as fitz
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit_pdf = load_script('audit_pdf')
verifier = load_script('verify_lossless')
encoder = load_script('encode_jbig2_region')


def compare(before, after, native=True, pages=None):
    args = argparse.Namespace(before=before, after=after, dpi=96, native_images=native, pages=pages)
    report = {'passed': False, 'pages': [], 'native_images': []}
    with redirect_stderr(io.StringIO()):
        verifier.verify(args, report)
    return report


def fixture(path):
    image = Image.new('RGBA', (32, 24), (40, 80, 120, 255))
    image.putpixel((0, 0), (40, 80, 120, 0))
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    with fitz.open() as doc:
        page = doc.new_page(width=180, height=240)
        xref = page.insert_image(fitz.Rect(10, 50, 138, 146), stream=stream.getvalue())
        page.insert_text((10, 25), 'MRC sample 1')
        page.insert_link({'kind': fitz.LINK_URI, 'from': fitz.Rect(10, 10, 70, 30),
                          'uri': 'https://example.org/'})
        page.add_text_annot((150, 200), 'Synthetic annotation')
        widget = fitz.Widget()
        widget.field_name = 'sample'
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.field_value = 'original'
        widget.rect = fitz.Rect(10, 160, 130, 180)
        page.add_widget(widget)
        page = doc.new_page(width=180, height=240)
        page.insert_image(fitz.Rect(10, 50, 138, 146), xref=xref)
        page.insert_text((10, 25), 'MRC sample 2')
        page.set_rotation(90)
        doc.set_metadata({'title': 'Synthetic MRC regression fixture'})
        doc.set_toc([[1, 'First page', 1], [1, 'Second page', 2]])
        doc.embfile_add('sample.txt', b'synthetic attachment')
        doc.save(path)


class PDFHelpers(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mrc test with spaces ')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.before = self.directory / 'before.pdf'
        self.after = self.directory / 'after.pdf'
        fixture(self.before)

    def mutate(self, operation):
        with fitz.open(self.before) as doc:
            operation(doc)
            doc.save(self.after, garbage=4, deflate=True)

    def cli(self, script, *args):
        return subprocess.run([sys.executable, str(ROOT / 'scripts' / script), *map(str, args)],
                              capture_output=True, text=True, check=False)

    def test_audit_counts_shared_image_and_mask_once(self):
        report = audit_pdf.audit(self.before)
        self.assertEqual(report['page_count'], 2)
        self.assertEqual(report['unique_image_and_mask_objects'], 2)
        self.assertTrue(all(item['page_use_count'] == 2 for item in report['resources']))
        with fitz.open(self.before) as doc:
            expected = sum(len(doc.xref_stream_raw(item['xref'])) for item in report['resources'])
        self.assertEqual(report['unique_image_and_mask_encoded_bytes'], expected)
        self.assertEqual(report['pages'][1]['rotation'], 90)
        self.assertEqual(report['pages'][0]['image_placements'][0]['effective_dpi_xy'], [18, 18])
        self.assertEqual(report['sha256'], hashlib.sha256(self.before.read_bytes()).hexdigest())

    def test_rewritten_pdf_preserves_pixels_and_features(self):
        self.mutate(lambda doc: None)
        report = compare(self.before, self.after)
        self.assertTrue(report['passed'])
        self.assertTrue(report['all_pages_compared'])
        self.assertEqual(report['native_image_pairs_compared'], 2)

    def test_native_check_detects_invisible_changed_image(self):
        # Occlude the image before changing its stored pixels, so rendered-only
        # comparison passes but a native check must reject the change.
        covered = self.directory / 'covered.pdf'
        with fitz.open(self.before) as doc:
            for page in doc:
                page.draw_rect(fitz.Rect(0, 40, 180, 150), color=None, fill=(1, 1, 1), overlay=True)
            doc.save(covered)
        self.before = covered
        def change(doc):
            xref = doc[0].get_images(full=True)[0][0]
            data = bytearray(doc.xref_stream(xref))
            data[0] ^= 255
            doc.update_stream(xref, bytes(data))
        self.mutate(change)
        self.assertTrue(compare(self.before, self.after, native=False)['passed'])
        with self.assertRaisesRegex(ValueError, 'native pixels differ'):
            compare(self.before, self.after)

    def test_verifier_rejects_feature_and_render_changes(self):
        def change_link(doc):
            page = doc[0]
            link = page.get_links()[0]
            link['uri'] = 'https://example.org/changed'
            page.update_link(link)
        def change_widget(doc):
            page = doc[0]
            widget = next(page.widgets())
            widget.field_value = 'changed'
            widget.update()
        def change_annotation(doc):
            page = doc[0]
            annotation = next(page.annots())
            annotation.set_info(content='changed')
            annotation.update()
        def change_attachment(doc):
            doc.embfile_del('sample.txt')
            doc.embfile_add('sample.txt', b'changed')
        changes = [
            (lambda doc: doc[0].draw_rect(fitz.Rect(5, 210, 30, 230), fill=(0, 0, 0)), 'rendered pixels'),
            (lambda doc: doc[0].set_rotation(180), 'geometry|Bookmarks'),
            (lambda doc: doc.delete_page(1), 'Page count'),
            (lambda doc: doc.set_metadata({'title': 'changed'}), 'Metadata'),
            (lambda doc: doc.set_toc([[1, 'changed', 1]]), 'Bookmarks'),
            (change_attachment, 'Embedded file'),
            (change_link, 'links'), (change_widget, 'form fields|extracted text'), (change_annotation, 'annotations'),
        ]
        for change, message in changes:
            with self.subTest(message=message):
                self.mutate(change)
                with self.assertRaisesRegex(ValueError, message):
                    compare(self.before, self.after)

    def test_page_sampling_reports_its_scope(self):
        shutil.copyfile(self.before, self.after)
        report = compare(self.before, self.after, pages=[2, 2])
        self.assertEqual(report['selected_pages'], [2])
        self.assertFalse(report['all_pages_compared'])
        with self.assertRaisesRegex(ValueError, 'out of range'):
            compare(self.before, self.after, pages=[0])

    def test_cli_json_and_exit_codes(self):
        report = self.directory / 'nested' / 'audit.json'
        result = self.cli('audit_pdf.py', self.before, '--output', report)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(report.read_text())['page_count'], 2)
        shutil.copyfile(self.before, self.after)
        result = self.cli('verify_lossless.py', self.before, self.after, '--native-images', '--report', report)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(report.read_text())['passed'])
        self.mutate(lambda doc: doc[0].set_rotation(180))
        result = self.cli('verify_lossless.py', self.before, self.after, '--report', report)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(report.read_text())['passed'])

    def test_cli_protects_pdf_from_report_overwrite(self):
        original = self.before.read_bytes()
        for script, arguments in [
            ('audit_pdf.py', [self.before, '--output', self.before]),
            ('verify_lossless.py', [self.before, self.before, '--report', self.before]),
            ('verify_lossless.py', [self.before, self.before, '--dpi', '0']),
        ]:
            with self.subTest(script=script, arguments=arguments):
                self.assertEqual(self.cli(script, *arguments).returncode, 2)
                self.assertEqual(self.before.read_bytes(), original)


class EncoderGuards(unittest.TestCase):
    def test_rejects_gray_and_color_instead_of_thresholding(self):
        with patch.object(encoder.shutil, 'which', return_value='jbig2'):
            for image in (Image.new('L', (5, 5), 127), Image.new('RGB', (5, 5), 'white')):
                with self.subTest(mode=image.mode), self.assertRaises(ValueError):
                    encoder.encode_region(image)

    def test_rejects_unknown_stream_layout(self):
        result = subprocess.CompletedProcess([], 0, stdout=b'unknown stream', stderr=b'')
        with patch.object(encoder.shutil, 'which', return_value='jbig2'), \
                patch.object(encoder.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(ValueError, 'Unsupported'):
                encoder.encode_region(Image.new('1', (4, 4), 1))

    def test_missing_encoder_has_clear_error(self):
        with patch.object(encoder.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(ValueError, 'not found'):
                encoder.encode_region(Image.new('1', (4, 4), 1))

    def test_cli_existing_output_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            image, output = Path(directory) / 'mask.png', Path(directory) / 'mask.jb2'
            Image.new('1', (4, 4), 1).save(image)
            output.write_bytes(b'preserve existing file')
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/encode_jbig2_region.py'),
                                     str(image), str(output)], capture_output=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(output.read_bytes(), b'preserve existing file')


class NativeIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [tool for tool in ('jbig2', 'qpdf', 'pdftoppm') if not shutil.which(tool)]
        if missing:
            message = 'Native tools missing: ' + ', '.join(missing)
            if os.environ.get('MRC_REQUIRE_NATIVE') == '1':
                raise RuntimeError(message)
            raise unittest.SkipTest(message)

    def test_generic_jbig2_roundtrip_and_independent_render(self):
        sparse = Image.new('L', (128, 97), 255)
        draw = ImageDraw.Draw(sparse)
        draw.rectangle((37, 25, 52, 71), fill=0)
        draw.line((15, 80, 110, 80), fill=0)
        rng = random.Random(42)
        noise = Image.frombytes('L', (128, 97), bytes(rng.choice((0, 255)) for _ in range(128 * 97)))
        tiny = Image.new('L', (6, 2), 255)
        tiny.putpixel((4, 1), 0)
        samples = [Image.new('L', (1, 1), 255), Image.new('L', (1, 1), 0),
                   Image.new('L', (128, 97), 255), Image.new('L', (64, 64), 0),
                   tiny, sparse, noise]
        with tempfile.TemporaryDirectory(prefix='mrc codec ') as directory:
            directory = Path(directory)
            for index, image in enumerate(samples):
                for crop in (True, False):
                    with self.subTest(index=index, crop=crop):
                        data, stats = encoder.encode_region(image, crop=crop)
                        reference = directory / 'reference.pdf'
                        encoded = directory / 'encoded.pdf'
                        stream = io.BytesIO()
                        image.save(stream, format='PNG')
                        with fitz.open() as doc:
                            page = doc.new_page(width=image.width, height=image.height)
                            xref = page.insert_image(page.rect, stream=stream.getvalue())
                            doc.save(reference)
                        with fitz.open(reference) as doc:
                            doc.update_stream(xref, data, compress=False)
                            doc.xref_set_key(xref, 'Filter', '/JBIG2Decode')
                            doc.xref_set_key(xref, 'BitsPerComponent', '1')
                            doc.xref_set_key(xref, 'DecodeParms', 'null')
                            doc.xref_set_key(xref, 'Decode', '[0 1]')
                            pix = fitz.Pixmap(doc, xref)
                            self.assertEqual(bytes(pix.samples), image.tobytes())
                            self.assertEqual((stats['width'], stats['height']), image.size)
                            doc.save(encoded)
                        self.assertTrue(compare(reference, encoded, native=False)['passed'])
                        checked = subprocess.run(['qpdf', '--check', str(encoded)], capture_output=True, check=False)
                        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
                        renders = []
                        for name, path in [('reference', reference), ('encoded', encoded)]:
                            prefix = directory / name
                            rendered = subprocess.run(['pdftoppm', '-singlefile', '-r', '144', '-png',
                                                       str(path), str(prefix)], capture_output=True, check=False)
                            self.assertEqual(rendered.returncode, 0, rendered.stderr)
                            with Image.open(prefix.with_suffix('.png')) as decoded:
                                renders.append((decoded.size, decoded.tobytes()))
                        self.assertEqual(renders[0], renders[1])


if __name__ == '__main__':
    unittest.main()
