#!/usr/bin/env python3
"""Set explicit bookmarks and/or page-label segments; never recompress images."""
import argparse
import json
from pathlib import Path

import pymupdf as fitz
from book_utils import check_edit_paths, page_number, read_plan, save_pdf


def apply_navigation(doc, plan):
    if set(plan) - {'bookmarks', 'labels'} or not plan:
        raise ValueError('Expected bookmarks and/or labels')
    bookmarks = plan.get('bookmarks')
    labels = plan.get('labels')
    toc = None
    if bookmarks is not None:
        toc = []
        previous = 0
        for item in bookmarks:
            if set(item) != {'level', 'title', 'page'}:
                raise ValueError('Bookmark needs level, title, page')
            level, title = item['level'], item['title']
            if type(level) is not int or level < 1 or level > previous + 1:
                raise ValueError('Invalid bookmark hierarchy')
            if not isinstance(title, str) or not title.strip():
                raise ValueError('Bookmark title must be nonempty')
            if title in ('书名页', '版权页'):
                title = title[:-1]
            toc.append([level, title, page_number(item['page'], len(doc)) + 1])
            previous = level
    rules = None
    if labels is not None:
        rules = []
        previous = -1
        for item in labels:
            if set(item) - {'page', 'style', 'first', 'prefix'} or not {'page', 'style'} <= set(item):
                raise ValueError('Label needs page, style; optional first, prefix')
            start = page_number(item['page'], len(doc))
            if start <= previous or (not rules and start != 0):
                raise ValueError('Labels must start at physical page 1 and increase')
            style, first, prefix = item['style'], item.get('first', 1), item.get('prefix', '')
            if style not in ('A', 'a', 'R', 'r', 'D', '') or type(first) is not int or first < 1:
                raise ValueError('Invalid label style or first number')
            if not isinstance(prefix, str):
                raise ValueError('Label prefix must be a string')
            rules.append({'startpage': start, 'style': style, 'firstpagenum': first, 'prefix': prefix})
            previous = start
    # Validate the entire plan before changing either structure.
    if toc is not None:
        doc.set_toc(toc)
    if rules is not None:
        doc.set_page_labels(rules)
    return {'bookmarks_changed': toc is not None, 'labels_changed': rules is not None,
            'validation': 'plan checked; no rendering or compression checks'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--session', type=Path)
    args = parser.parse_args()
    try:
        plan = read_plan(args.plan, ('bookmarks', 'labels'))
        check_edit_paths(args.input, args.output, args.plan, args.session)
        with fitz.open(args.input) as doc:
            result = apply_navigation(doc, plan)
            result.update(save_pdf(doc, args.input, args.output, args.session))
            result['validation'] = 'plan checked; output not independently validated'
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f'Navigation failed: {error}\n')


if __name__ == '__main__':
    main()
