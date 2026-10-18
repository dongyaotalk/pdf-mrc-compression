#!/usr/bin/env python3
"""Read-only inventory of page geometry and unique PDF image/mask streams."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

try:
    import pymupdf as fitz
except ImportError:
    raise SystemExit('PyMuPDF is required; use a Python environment with pymupdf installed.')


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def audit(path):
    resources = {}
    pages = []
    with fitz.open(path) as doc:
        if not doc.is_pdf or doc.needs_pass:
            raise ValueError('An unlocked PDF is required.')

        def register(xref, page_number, role):
            if xref <= 0:
                return
            if xref not in resources:
                raw = doc.xref_stream_raw(xref)
                keys = ['Width', 'Height', 'BitsPerComponent', 'ColorSpace',
                        'Filter', 'Decode', 'DecodeParms', 'ImageMask',
                        'Mask', 'SMask', 'Interpolate']
                resources[xref] = {'xref': xref, 'encoded_bytes': len(raw) if raw else 0,
                    'attributes': {key: doc.xref_get_key(xref, key)[1] for key in keys},
                    'pages': set(), 'roles': set(), 'resource_occurrences': 0}
            item = resources[xref]
            item['pages'].add(page_number)
            item['roles'].add(role)
            item['resource_occurrences'] += 1

        for number, page in enumerate(doc, 1):
            rows = page.get_images(full=True)
            for row in rows:
                register(row[0], number, 'image')
                if row[1]:
                    register(row[1], number, 'mask')
            placements = []
            for info in page.get_image_info(hashes=False, xrefs=False):
                a, b, c, d, e, f = info['transform']
                sx, sy = math.hypot(a, b), math.hypot(c, d)
                placements.append({'width': info['width'], 'height': info['height'],
                    'bbox': list(info['bbox']), 'transform': list(info['transform']),
                    'effective_dpi_xy': [round(info['width'] * 72 / sx, 2) if sx else None,
                                         round(info['height'] * 72 / sy, 2) if sy else None]})
            pages.append({'page': number, 'mediabox': list(page.mediabox),
                'cropbox': list(page.cropbox), 'rotation': page.rotation,
                'text_characters': len(page.get_text().strip()),
                'font_resources': len(page.get_fonts(full=True)),
                'drawing_paths': len(page.get_cdrawings()),
                'image_resource_occurrences': len(rows),
                'image_placements': placements,
                'images': [{'name': row[7], 'xref': row[0], 'mask_xref': row[1],
                            'parent_form_xref': row[9]} for row in rows]})
        metadata = doc.metadata
        toc_count = len(doc.get_toc())
        page_count = len(doc)
        pdf_version = doc.metadata.get('format')
    by_filter = Counter()
    mask_bytes = 0
    for item in resources.values():
        item['pages'] = sorted(item['pages'])
        item['page_use_count'] = len(item['pages'])
        item['roles'] = sorted(item['roles'])
        by_filter[item['attributes']['Filter']] += item['encoded_bytes']
        if 'mask' in item['roles'] or item['attributes']['ImageMask'] == 'true':
            mask_bytes += item['encoded_bytes']
    image_bytes = sum(item['encoded_bytes'] for item in resources.values())
    return {'input': str(path.resolve()), 'file_bytes': path.stat().st_size,
        'sha256': sha256_file(path), 'page_count': page_count, 'pdf_version': pdf_version,
        'metadata': metadata, 'toc_entries': toc_count, 'unique_image_and_mask_objects': len(resources),
        'unique_image_and_mask_encoded_bytes': image_bytes, 'mask_encoded_bytes': mask_bytes,
        'other_file_bytes': path.stat().st_size - image_bytes,
        'encoded_bytes_by_filter': dict(by_filter),
        'notes': ['Resource references may include unused resources; placements describe drawn images.',
                  'Encoded stream bytes are counted once per xref, including shared masks.',
                  'DPI is measured along image transform axes; clipping does not reduce decoded dimensions.'],
        'resources': sorted(resources.values(), key=lambda item: item['encoded_bytes'], reverse=True),
        'pages': pages}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, help='JSON report; otherwise write full report to stdout')
    args = parser.parse_args()
    if args.output and args.output.resolve() == args.input.resolve():
        parser.error('Report path must differ from the input PDF.')
    try:
        result = audit(args.input)
        data = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(data + '\n', encoding='utf-8')
            print(json.dumps({key: value for key, value in result.items()
                              if key not in ['pages', 'resources', 'metadata']}, ensure_ascii=False, indent=2))
        else:
            print(data)
    except (OSError, ValueError, RuntimeError) as error:
        print(f'Audit failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
