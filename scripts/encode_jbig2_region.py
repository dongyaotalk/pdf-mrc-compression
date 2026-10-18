#!/usr/bin/env python3
"""Encode a bilevel black-on-white image as a lossless full-canvas JBIG2 region.

Produces a PDF-ready generic JBIG2 stream, not a standalone JBIG2 file or PDF.
No symbol dictionary, thresholding, or resampling is used.
"""
import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

try:
    from PIL import Image, ImageOps
except ImportError:
    raise SystemExit('Pillow is required; use a Python environment with Pillow installed.')


def encode_region(image, executable='jbig2', crop=True):
    command = shutil.which(executable)
    if not command:
        raise ValueError(f'jbig2enc executable not found: {executable}')
    if image.mode not in ('1', 'L'):
        raise ValueError('Input must be mode 1 or L; convert color/alpha images explicitly first.')
    gray = image.convert('L')
    colors = gray.getcolors(maxcolors=3)
    if colors is None or any(value not in (0, 255) for count, value in colors):
        raise ValueError('Input is not binary 0/255. This encoder will not threshold it.')
    width, height = gray.size
    if not width or not height:
        raise ValueError('Input must have a nonempty canvas.')
    box = ImageOps.invert(gray).getbbox() if crop else (0, 0, width, height)
    if box is None:
        box = (0, 0, 1, 1)
    x0, y0, x1, y1 = box
    with tempfile.TemporaryDirectory(prefix='mrc-jbig2-') as temp:
        path = Path(temp) / 'region.png'
        gray.crop(box).convert('1', dither=Image.Dither.NONE).save(path, compress_level=1)
        result = subprocess.run([command, '-p', '-d', str(path)], capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f'jbig2 failed ({result.returncode}): {result.stderr.decode(errors="replace")}')
    raw = result.stdout
    # Recognize the exact two-segment, one-page, unreferenced layout before
    # changing any offsets. Never apply these byte offsets to unknown streams.
    if (len(raw) < 59 or raw[4:7] != b'\x30\x00\x01'
            or struct.unpack_from('>I', raw, 7)[0] != 19
            or raw[34:37] != b'\x26\x00\x01'
            or struct.unpack_from('>I', raw, 37)[0] != len(raw) - 41
            or raw[57] != 0):
        raise ValueError('Unsupported jbig2 output structure; refusing to patch segment offsets.')
    expected_size = (x1 - x0, y1 - y0)
    if (struct.unpack_from('>II', raw, 11) != expected_size
            or struct.unpack_from('>II', raw, 41) != expected_size
            or struct.unpack_from('>II', raw, 49) != (0, 0)):
        raise ValueError('Unexpected page/region geometry from encoder.')
    encoded = bytearray(raw)
    struct.pack_into('>I', encoded, 0, 0)
    struct.pack_into('>II', encoded, 11, width, height)
    struct.pack_into('>I', encoded, 30, 1)
    struct.pack_into('>II', encoded, 49, x0, y0)
    return bytes(encoded), {'width': width, 'height': height, 'ink_bbox': list(box),
        'encoded_area_fraction': ((x1 - x0) * (y1 - y0)) / (width * height),
        'encoded_bytes': len(encoded), 'codec': 'JBIG2 generic, no symbol substitution'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='Black ink=0, paper=255; bilevel PNG/TIFF/PBM')
    parser.add_argument('output', type=Path, help='PDF-ready .jb2 stream')
    parser.add_argument('--jbig2', default='jbig2', help='jbig2enc executable name or path')
    parser.add_argument('--no-crop', action='store_true', help='Encode the whole image as one region')
    parser.add_argument('--overwrite', action='store_true', help='Allow replacing the output stream')
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error('Input and output must be different files.')
    if args.output.exists() and not args.overwrite:
        parser.error('Output already exists; choose another path or use --overwrite.')
    try:
        with Image.open(args.input) as image:
            data, stats = encode_region(image, args.jbig2, not args.no_crop)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('wb' if args.overwrite else 'xb') as stream:
            stream.write(data)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError) as error:
        print(f'Encoding failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
