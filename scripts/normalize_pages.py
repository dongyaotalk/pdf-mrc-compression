#!/usr/bin/env python3
"""Fit page content to an explicit paper size without resampling scan images."""
import argparse
import json
import math
import re
from pathlib import Path

import pymupdf as fitz
from book_utils import check_edit_paths, page_number, read_plan, save_pdf


def size_pair(value):
    if (not isinstance(value, list) or len(value) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in value)):
        raise ValueError('size must be two positive finite point values')
    return value


def normalize(doc, plan):
    if set(plan) - {'size', 'pages', 'scan_repairs'} or 'size' not in plan:
        raise ValueError('Expected size; optional pages and scan_repairs')
    width, height = size_pair(plan['size'])
    selected = plan.get('pages', list(range(1, len(doc) + 1)))
    selected = [page_number(number, len(doc)) for number in selected]
    if len(selected) != len(set(selected)):
        raise ValueError('Duplicate page selection')
    repairs = {}
    for item in plan.get('scan_repairs', []):
        if set(item) != {'page', 'rect'}:
            raise ValueError('scan_repairs need page and explicit unrotated rect')
        number = page_number(item['page'], len(doc))
        rect = fitz.Rect(item['rect'])
        if number in repairs or number not in selected or rect.is_empty or rect.is_infinite:
            raise ValueError('Invalid or duplicate scan repair')
        if not fitz.Rect(0, 0, width, height).contains(rect):
            raise ValueError('Repair rect must be inside target paper')
        repairs[number] = rect
    links = [page.get_links() for page in doc]
    toc = doc.get_toc(simple=False)
    transforms = {}
    # Preflight before mutations. Arbitrary clipped pages, named destinations,
    # forms and annotations with complex appearances require a tailored tool.
    for index in selected:
        page = doc[index]
        if doc.xref_get_key(page.xref, 'UserUnit')[1] not in ('null', '1'):
            raise ValueError('Non-default UserUnit requires a geometry adapter')
        if page.cropbox != page.mediabox or page.mediabox.x0 or page.mediabox.y0:
            raise ValueError('Nontrivial page boxes require an explicit geometry adapter')
        if page.first_widget or page.first_annot:
            raise ValueError('Annotated/form pages require appearance-aware geometry handling')
        if any(link['kind'] not in (fitz.LINK_GOTO, fitz.LINK_URI, fitz.LINK_GOTOR)
               for link in links[index]):
            raise ValueError('Unsupported link type on changed page')
        if index in repairs:
            image_info = page.get_image_info(xrefs=True)
            direct = [item for item in page.get_images(full=True) if item[9] == 0]
            if (page.get_text().strip() or page.get_fonts() or page.get_drawings()
                    or len(image_info) != 1 or not image_info[0]['xref']
                    or not any(item[0] == image_info[0]['xref'] and re.fullmatch(r'[A-Za-z0-9_.-]+', item[7]) for item in direct)):
                raise ValueError('Scan repair is restricted to one scan with no text or vectors')
        old_width, old_height = page.mediabox.width, page.mediabox.height
        scale = min(width / old_width, height / old_height)
        dx, dy = (width - old_width * scale) / 2, (height - old_height * scale) / 2
        transforms[index] = (fitz.Matrix(scale, 0, 0, scale, dx, dy),
                             page.derotation_matrix, page.rotation)
    # Named internal destinations cannot be safely relocated by this helper.
    if transforms and any(link['kind'] == fitz.LINK_NAMED for group in links for link in group):
        raise ValueError('Named destinations require an explicit geometry adapter')
    for index in selected:
        page = doc[index]
        transform, _, _ = transforms[index]
        if index in repairs:
            placement = page.get_image_info(xrefs=True)[0]
            xref = placement['xref']
            if not xref:
                raise ValueError('Inline scan repair is unsupported')
            # A fresh content stream refers to the same scan object. No decoded
            # pixel data is written; only its placement and rotation change.
            name = next(item[7] for item in page.get_images(full=True) if item[0] == xref and item[9] == 0)
            rect = repairs[index]
            raw = (f'q {rect.width} 0 0 {rect.height} {rect.x0} {height-rect.y1} cm /{name} Do Q\n').encode()
            page.set_rotation(0)
        else:
            scale, dx, dy = transform.a, transform.e, transform.f
            raw = (f'q {scale} 0 0 {scale} {dx} {dy} cm\n').encode() + page.read_contents() + b'\nQ\n'
        page.set_mediabox(fitz.Rect(0, 0, width, height))
        for setter in (page.set_cropbox, page.set_trimbox, page.set_bleedbox, page.set_artbox):
            setter(fitz.Rect(0, 0, width, height))
        content = doc.get_new_xref()
        doc.update_object(content, '<<>>')
        doc.update_stream(content, raw)
        page.set_contents(content)
    def destination(number, point, rotated=True):
        if number not in transforms:
            return point
        matrix, derotate, _ = transforms[number]
        mapped = fitz.Point(point) * derotate * matrix
        return mapped * doc[number].rotation_matrix if rotated else mapped
    for index, group in enumerate(links):
        for link in group:
            changed = False
            if index in transforms:
                # get_links source rectangles use the page's rotated space.
                link['from'] = (link['from'] * transforms[index][1] * transforms[index][0])
                changed = True
            if link['kind'] == fitz.LINK_GOTO and link.get('page') in transforms:
                link['to'] = destination(link['page'], link.get('to', fitz.Point()), rotated=False)
                changed = True
            if changed:
                doc[index].update_link(link)
    if toc:
        for entry in toc:
            detail = entry[3]
            if detail.get('kind') == fitz.LINK_GOTO and detail.get('page') in transforms:
                detail['to'] = destination(detail['page'], detail.get('to', fitz.Point()))
        doc.set_toc(toc)
    return {'changed_physical_pages': [p + 1 for p in selected], 'size_points': [width, height],
            'validation': 'plan preflight only; inspect geometry and rendering separately'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--session', type=Path)
    args = parser.parse_args()
    try:
        check_edit_paths(args.input, args.output, args.plan, args.session)
        plan = read_plan(args.plan, ('size', 'pages', 'scan_repairs'))
        with fitz.open(args.input) as doc:
            result = normalize(doc, plan)
            result['write'] = save_pdf(doc, args.input, args.output, args.session)
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f'Geometry failed: {error}\n')


if __name__ == '__main__':
    main()
