#!/usr/bin/env python3
"""Compare PDF geometry, text, navigation, rendered pixels, and optional native images.

This is a pixel/behavior check, not proof of equivalence of every PDF feature.
Native image matching requires stable, unambiguous per-page resource names.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

try:
    import pymupdf as fitz
except ImportError:
    raise SystemExit('PyMuPDF is required; use a Python environment with pymupdf installed.')


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    if isinstance(value, dict):
        return {key: canonical(item) for key, item in value.items() if key != 'xref'}
    if isinstance(value, (list, tuple, fitz.Point, fitz.Rect)):
        return [canonical(item) for item in value]
    return value


def native_hash(doc, xref):
    pix = fitz.Pixmap(doc, xref)
    # Keep pix alive until the memoryview has been consumed.
    return (pix.width, pix.height, pix.n, pix.alpha), hashlib.sha256(pix.samples_mv).hexdigest()


def render_hash(page, dpi):
    fitz.TOOLS.store_shrink(100)
    started = time.perf_counter()
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
    duration = time.perf_counter() - started
    return (pix.width, pix.height, pix.n), hashlib.sha256(pix.samples_mv).hexdigest(), duration


def widget_values(page):
    return [{'name': item.field_name, 'type': item.field_type, 'value': item.field_value,
             'flags': item.field_flags, 'rect': list(item.rect)} for item in page.widgets() or []]


def annotation_values(page):
    return [{'type': item.type, 'rect': list(item.rect), 'info': item.info,
             'colors': item.colors, 'opacity': item.opacity} for item in page.annots() or []]


def verify(args, report):
    started = time.perf_counter()
    with fitz.open(args.before) as before, fitz.open(args.after) as after:
        require(before.is_pdf and after.is_pdf, 'Two PDF files are required.')
        require(not before.needs_pass and not after.needs_pass, 'Unlock both PDFs before comparing.')
        require(len(before) == len(after), 'Page count differs.')
        require(before.metadata == after.metadata, 'Metadata/PDF version differs; inspect deliberately.')
        require(canonical(before.get_toc(simple=False)) == canonical(after.get_toc(simple=False)), 'Bookmarks differ.')
        require(before.embfile_names() == after.embfile_names(), 'Embedded file names differ.')
        for name in before.embfile_names():
            require(before.embfile_get(name) == after.embfile_get(name), f'Embedded file differs: {name}')
        selected = sorted(set(args.pages)) if args.pages else list(range(1, len(before) + 1))
        require(bool(selected) and all(1 <= p <= len(before) for p in selected), 'Page selection is out of range.')
        report.update({'total_pages': len(before), 'selected_pages': selected, 'compared_page_count': len(selected),
                       'all_pages_compared': len(selected) == len(before), 'dpi': args.dpi,
                       'metadata_and_bookmarks_identical': True})
        seen = set()
        for count, number in enumerate(selected, 1):
            left, right = before[number - 1], after[number - 1]
            prefix = f'Page {number}: '
            require((list(left.mediabox), list(left.cropbox), left.rotation) ==
                    (list(right.mediabox), list(right.cropbox), right.rotation), prefix + 'geometry differs.')
            require(left.get_text() == right.get_text(), prefix + 'extracted text differs.')
            require(canonical(left.get_links()) == canonical(right.get_links()), prefix + 'links differ.')
            require(widget_values(left) == widget_values(right), prefix + 'form fields differ.')
            require(annotation_values(left) == annotation_values(right), prefix + 'annotations differ.')
            if args.native_images:
                ai, bi = left.get_images(full=True), right.get_images(full=True)
                am, bm = {item[7]: item for item in ai}, {item[7]: item for item in bi}
                require(len(ai) == len(am) and len(bi) == len(bm),
                        prefix + 'ambiguous image resource names; match by Form path instead.')
                require(set(am) == set(bm), prefix + 'image resource names differ.')
                for name, a in am.items():
                    b = bm[name]
                    require(a[2:7] == b[2:7] and bool(a[1]) == bool(b[1]),
                            prefix + f'{name}: native image geometry/color/mask differs.')
                    for kind, ax, bx in [('image', a[0], b[0]), ('mask', a[1], b[1])]:
                        if not ax or (ax, bx) in seen:
                            continue
                        ah, bh = native_hash(before, ax), native_hash(after, bx)
                        require(ah == bh, prefix + f'{name} {kind}: native pixels differ.')
                        seen.add((ax, bx))
                        report['native_images'].append({'page': number, 'name': name, 'kind': kind,
                            'before_xref': ax, 'after_xref': bx, 'shape': ah[0], 'pixel_sha256': ah[1]})
            rendered = {}
            for side in ([0, 1] if count % 2 else [1, 0]):
                rendered[side] = render_hash([left, right][side], args.dpi)
            require(rendered[0][:2] == rendered[1][:2], prefix + 'rendered pixels differ.')
            report['pages'].append({'page': number, 'identical': True,
                'pixel_sha256': rendered[0][1], 'before_render_seconds': rendered[0][2],
                'after_render_seconds': rendered[1][2]})
            if count % 25 == 0 or count == len(selected):
                print(f'Compared {count}/{len(selected)} pages', file=sys.stderr, flush=True)
        report.update({'passed': True, 'native_image_pairs_compared': len(seen),
            'native_images_checked': bool(args.native_images),
            'before_render_seconds': sum(p['before_render_seconds'] for p in report['pages']),
            'after_render_seconds': sum(p['after_render_seconds'] for p in report['pages']),
            'verification_seconds': time.perf_counter() - started,
            'limitations': ['Render equality applies to the stated DPI and PyMuPDF renderer.',
                'Native checks cover named image resources and explicit image masks, not inline images.',
                'Check another renderer and relevant PDF features before claiming full equivalence.']})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--dpi', type=int, default=96)
    parser.add_argument('--pages', nargs='+', type=int, help='1-based samples; omitted means all pages')
    parser.add_argument('--native-images', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.dpi <= 0:
        parser.error('--dpi must be positive.')
    if args.report and args.report.resolve() in (args.before.resolve(), args.after.resolve()):
        parser.error('Report path must differ from both PDF paths.')
    report = {'before': str(args.before.resolve()), 'after': str(args.after.resolve()),
              'passed': False, 'pages': [], 'native_images': []}
    try:
        report.update({'before_bytes': args.before.stat().st_size, 'after_bytes': args.after.stat().st_size,
                       'before_sha256': file_hash(args.before), 'after_sha256': file_hash(args.after)})
        verify(args, report)
    except (OSError, ValueError, RuntimeError) as error:
        report['error'] = str(error)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key not in ('pages', 'native_images', 'selected_pages')},
                     ensure_ascii=False, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
