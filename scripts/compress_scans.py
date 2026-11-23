#!/usr/bin/env python3
"""Bounded native-grid scan compression; preserve unsupported resources unchanged.

A plan explicitly selects pages and permits optional binarization. This is not
an automatic segmentation engine for arbitrary color or continuous-tone pages.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tempfile
import shutil

import pymupdf as fitz
from PIL import Image, ImageChops, TiffImagePlugin, features
from book_utils import check_edit_paths, page_number, read_plan, save_pdf
from encode_jbig2_region import encode_region

ALGORITHM = 'native-scans-v1'


def sha256_executable(command):
    executable = shutil.which(command)
    if not executable:
        raise ValueError(f'Encoder not found: {command}')
    digest = hashlib.sha256()
    with open(executable, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def g4_encode(image):
    binary = image.convert('1', dither=Image.Dither.NONE)
    with tempfile.TemporaryDirectory(prefix='mrc-g4-') as directory:
        path = Path(directory) / 'one-strip.tiff'
        # Pillow's TIFF writer respects this strip size before delegating to
        # libtiff. Verify the actual tags rather than concatenate unknown strips.
        tags = TiffImagePlugin.ImageFileDirectory_v2()
        tags[278] = binary.height
        binary.save(path, compression='group4', tiffinfo=tags,
                    strip_size=max(65536, ((binary.width + 7) // 8) * binary.height + 1))
        with Image.open(path) as decoded:
            if decoded.convert('L').tobytes() != image.convert('L').tobytes():
                raise ValueError('TIFF roundtrip changed binary pixels')
            offsets, counts = decoded.tag_v2[273], decoded.tag_v2[279]
            if len(offsets) != 1 or len(counts) != 1:
                raise ValueError('TIFF encoder emitted multiple strips; cannot concatenate')
            if decoded.tag_v2[262] != 1:
                raise ValueError('Unexpected TIFF photometric polarity')
            raw = path.read_bytes()
            return raw[offsets[0]:offsets[0] + counts[0]]


def write_stream(doc, xref, data, compress=False):
    codec = doc.xref_get_key(xref, 'Filter')[1]
    params = doc.xref_get_key(xref, 'DecodeParms')[1]
    doc.update_stream(xref, data, compress=compress)
    if not compress:
        doc.xref_set_key(xref, 'Filter', codec)
        doc.xref_set_key(xref, 'DecodeParms', params)


def add_stream(doc, dictionary, data, compress=False):
    xref = doc.get_new_xref()
    doc.update_object(xref, dictionary)
    write_stream(doc, xref, data, compress)
    return xref


def image_dict(width, height, codec):
    base = f'/Type /XObject /Subtype /Image /Width {width} /Height {height} /ColorSpace /DeviceGray /BitsPerComponent 1 /Decode [0 1]'
    if codec == 'g4':
        return f'<<{base} /Filter /CCITTFaxDecode /DecodeParms << /K -1 /Columns {width} /Rows {height} /BlackIs1 true >> >>'
    return f'<<{base} /Filter /JBIG2Decode >>'


def prepare_gray(doc, xref):
    for key in ('Mask', 'SMaskInData', 'Alternates', 'OC', 'ImageMask'):
        if doc.xref_get_key(xref, key)[0] != 'null':
            raise ValueError(f'Unsupported image attribute {key}')
    color_kind, color_value = doc.xref_get_key(xref, 'ColorSpace')
    if color_kind == 'xref':
        color_value = doc.xref_object(int(color_value.split()[0]))
    color_value = ''.join(color_value.split()).strip('[]')
    if color_value not in ('/DeviceGray', '/DeviceRGB'):
        raise ValueError('Only explicit DeviceGray/DeviceRGB color spaces are supported')
    if doc.xref_get_key(xref, 'Decode')[0] != 'null':
        raise ValueError('Explicit Decode needs a tailored adapter')
    pix = fitz.Pixmap(doc, xref)
    if pix.alpha or pix.n not in (1, 3):
        raise ValueError('Unsupported pixel layout')
    image = Image.frombytes('L' if pix.n == 1 else 'RGB', (pix.width, pix.height), pix.samples)
    if image.mode == 'RGB':
        red, green, blue = image.split()
        if ImageChops.difference(red, green).getbbox() or ImageChops.difference(red, blue).getbbox():
            raise ValueError('Color content is preserved')
        image = red
    kind, value = doc.xref_get_key(xref, 'SMask')
    if kind != 'null':
        if kind != 'xref':
            raise ValueError('Unknown soft mask')
        mask_xref = int(value.split()[0])
        mask = fitz.Pixmap(doc, mask_xref)
        if (mask.n != 1 or mask.alpha or (mask.width, mask.height) != image.size
                or any(v != 255 for v in mask.samples)):
            raise ValueError('Nonopaque soft mask is preserved')
    return image


def target_pixels(gray, options):
    histogram = gray.histogram()
    middle = sum(histogram[1:255])
    threshold = options.get('threshold')
    if threshold is None:
        if middle > options.get('max_gray_pixels', 0):
            raise ValueError('Continuous gray exceeds explicit protection budget')
        binary = gray.point(lambda value: 0 if value == 0 else 255)
        corrections = gray if middle else None
        return binary, corrections, gray, middle
    if type(threshold) is not int or not 1 <= threshold <= 255:
        raise ValueError('threshold must be an integer in 1..255')
    protect = options.get('protect_gray')
    binary = gray.point(lambda value: 0 if value < threshold else 255)
    if protect is None:
        return binary, None, binary, 0
    if (not isinstance(protect, list) or len(protect) != 2
            or any(type(v) is not int for v in protect) or not 1 <= protect[0] <= protect[1] <= 254):
        raise ValueError('protect_gray must be a closed integer range inside 1..254')
    low, high = protect
    count = sum(histogram[low:high + 1])
    if count > options.get('max_gray_pixels', 0):
        raise ValueError('Gray protection budget exceeded; preserve continuous-tone page')
    mask = gray.point(lambda value: 255 if low <= value <= high else 0)
    target = Image.composite(gray, binary, mask)
    return binary, (target if count else None), target, count


def embed(doc, xref, binary, corrections, data, codec, interpolate):
    width, height = binary.size
    dictionary = image_dict(width, height, codec)
    if corrections is None:
        doc.update_object(xref, dictionary)
        write_stream(doc, xref, data, compress=False)
        doc.xref_set_key(xref, 'Interpolate', interpolate)
        return
    base = add_stream(doc, dictionary, data)
    # Each gray value uses a constant color and a full native-grid alpha mask.
    # Interpolating a gray-on-white image AND its mask would attenuate gray
    # twice, giving pale dots in independent renderers.
    objects = [base]
    resources = [f'/Base {base} 0 R']
    commands = [b'q /Base Do']
    for value, count in enumerate(corrections.histogram()):
        if value in (0, 255) or not count:
            continue
        mask = corrections.point(lambda v: 255 if v == value else 0).convert('1', dither=Image.Dither.NONE)
        mask_ref = add_stream(doc, f'<< /Type /XObject /Subtype /Image /Width {width} /Height {height} /ColorSpace /DeviceGray /BitsPerComponent 1 >>', mask.tobytes(), True)
        color_ref = add_stream(doc, f'<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceGray /BitsPerComponent 8 /SMask {mask_ref} 0 R >>', bytes([value]), True)
        resources.append(f'/G{value} {color_ref} 0 R')
        commands.append(f'/G{value} Do'.encode())
        objects.extend((mask_ref, color_ref))
    doc.update_object(xref, f'<< /Type /XObject /Subtype /Form /BBox [0 0 1 1] /Resources << /XObject << {" ".join(resources)} >> >> >>')
    doc.update_stream(xref, b' '.join(commands) + b' Q\n', compress=True)
    for item in objects:
        doc.xref_set_key(item, 'Interpolate', interpolate)


def validate_native(doc, xref, expected):
    # Decode the actual installed object at its native grid. Form paths are
    # rendered at exactly one device pixel per source pixel.
    if doc.xref_get_key(xref, 'Subtype')[1] == '/Image':
        pix = fitz.Pixmap(doc, xref)
        if pix.samples != expected.tobytes():
            raise ValueError('Native codec roundtrip differs (including polarity)')
    else:
        wrapper = doc.new_page(width=expected.width, height=expected.height)
        try:
            doc.xref_set_key(wrapper.xref, 'Resources', f'<< /XObject << /Proof {xref} 0 R >> >>')
            stream = add_stream(doc, '<<>>', f'q {expected.width} 0 0 {expected.height} 0 0 cm /Proof Do Q'.encode())
            wrapper.set_contents(stream)
            pix = wrapper.get_pixmap(colorspace=fitz.csGRAY, alpha=False)
            if pix.samples != expected.tobytes():
                raise ValueError('Installed sparse-gray Form differs at native resolution')
        finally:
            doc.delete_page(len(doc) - 1)


def direct_scan_supported(doc, page, xref):
    resources = page.get_images(full=True)
    if not any(item[0] == xref and item[9] == 0 for item in resources):
        return False
    owner = page.xref
    seen = set()
    while owner and owner not in seen:
        seen.add(owner)
        kind, value = doc.xref_get_key(owner, 'Resources')
        if kind != 'null':
            return all(doc.xref_get_key(owner, f'Resources/ColorSpace/{name}')[0] == 'null'
                       for name in ('DefaultGray', 'DefaultRGB', 'DefaultCMYK'))
        kind, value = doc.xref_get_key(owner, 'Parent')
        owner = int(value.split()[0]) if kind == 'xref' else 0
    return True


def compress(doc, plan, cache=None, jbig2='jbig2', validate=True):
    allowed = {'pages', 'codec', 'threshold', 'protect_gray', 'max_gray_pixels'}
    if set(plan) - allowed or not {'pages', 'codec'} <= set(plan):
        raise ValueError('Expected pages and codec; only documented options supported')
    if plan['codec'] not in ('g4', 'jbig2'):
        raise ValueError('codec must be g4 or jbig2')
    if type(plan.get('max_gray_pixels', 0)) is not int or plan.get('max_gray_pixels', 0) < 0:
        raise ValueError('max_gray_pixels must be a nonnegative integer')
    if 'protect_gray' in plan and 'threshold' not in plan:
        raise ValueError('protect_gray requires an explicit threshold')
    # Validate options even when all selected pages are unsupported.
    target_pixels(Image.new('L', (1, 1), 255), plan)
    selected = {page_number(value, len(doc)) for value in plan['pages']}
    uses, candidates, mask_uses = {}, {}, set()
    for index, page in enumerate(doc):
        for resource in page.get_images(full=True):
            uses.setdefault(resource[0], set()).add(index)
            if resource[1]:
                mask_uses.add(resource[1])
        info = page.get_image_info(xrefs=True)
        if (index in selected and len(info) == 1 and info[0]['xref']
                and direct_scan_supported(doc, page, info[0]['xref'])):
            candidates.setdefault(info[0]['xref'], set()).add(index)
    report = {'changed': [], 'preserved': [], 'codec': plan['codec'],
              'baseline': 'explicit threshold/protection target' if 'threshold' in plan else 'native grayscale pixels',
              'validation': 'native decoded object pixels' if validate else 'skipped at user request'}
    handled = set()
    for xref, pages in candidates.items():
        handled |= pages
        if xref in mask_uses or not uses.get(xref, set()) <= pages:
            report['preserved'].append({'pages': sorted(p + 1 for p in pages), 'reason': 'shared resource has unselected or complex uses'})
            continue
        try:
            gray = prepare_gray(doc, xref)
            binary, corrections, target, count = target_pixels(gray, plan)
        except ValueError as error:
            report['preserved'].append({'pages': sorted(p + 1 for p in pages), 'reason': str(error)})
            continue
        # The encoder sees only a native binary target. Cache identities include
        # pixels, effective resource dictionary and encoding options/versions.
        import PIL
        identity = json.dumps({'algorithm': ALGORITHM, 'options': plan, 'size': gray.size,
                               'attributes': doc.xref_object(xref), 'pillow': PIL.__version__,
                               'pymupdf': fitz.VersionBind, 'encoder': (sha256_executable(jbig2) if plan['codec'] == 'jbig2' else features.version_codec('libtiff'))}, sort_keys=True).encode()
        key = hashlib.sha256(identity + gray.tobytes()).hexdigest()
        cache_path = Path(cache) / key if cache else None
        data = None
        if cache_path and cache_path.with_suffix('.json').exists() and cache_path.with_suffix('.bin').exists():
            try:
                stored = json.loads(cache_path.with_suffix('.json').read_text())
                raw = cache_path.with_suffix('.bin').read_bytes()
                if isinstance(stored, dict) and stored.get('sha256') == hashlib.sha256(raw).hexdigest():
                    data = raw
            except (ValueError, OSError):
                pass  # An incomplete cache is a miss, never validation evidence.
        if data is None:
            data = g4_encode(binary) if plan['codec'] == 'g4' else encode_region(binary, jbig2)[0]
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.with_suffix('.bin').write_bytes(data)
                cache_path.with_suffix('.json').write_text(json.dumps({'sha256': hashlib.sha256(data).hexdigest()}))
        interpolate = doc.xref_get_key(xref, 'Interpolate')[1]
        if interpolate == 'null':
            interpolate = 'false'
        embed(doc, xref, binary, corrections, data, plan['codec'], interpolate)
        if validate:
            validate_native(doc, xref, target)
        report['changed'].append({'pages': sorted(p + 1 for p in pages), 'gray_pixels_preserved': count,
                                  'binary_stream_bytes': len(data), 'cache_key': key})
    for index in sorted(selected - handled):
        report['preserved'].append({'pages': [index + 1], 'reason': 'not a direct single scan with supported page color resources'})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--jbig2', default='jbig2')
    parser.add_argument('--session', type=Path)
    parser.add_argument('--skip-validation', action='store_true', help='Explicitly skip native output checks; report as unvalidated')
    args = parser.parse_args()
    try:
        check_edit_paths(args.input, args.output, args.plan, args.session)
        plan = read_plan(args.plan, ('pages', 'codec', 'threshold', 'protect_gray', 'max_gray_pixels'))
        with fitz.open(args.input) as doc:
            report = compress(doc, plan, args.cache, args.jbig2, not args.skip_validation)
            report['write'] = save_pdf(doc, args.input, args.output, args.session)
        print(json.dumps(report, ensure_ascii=True, indent=2))
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f'Compression failed: {error}\n')


if __name__ == '__main__':
    main()
