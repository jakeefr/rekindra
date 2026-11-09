"""Decode one untrusted image with Pillow under hard caps. Runs only as a child process.

stdin carries the image. argv is: reader_dir, format tag, pixel cap, scene byte budget.
stdout carries one JSON line, then the full PNG, then an optional smaller PNG for scenes.

A damaged image keeps only the pixels its decoder really produced. Each pixel is proved
by decoding twice onto opposite backgrounds: a pixel that differs between the two runs
was never written by the decoder, so it is dropped rather than shown.
"""
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import warnings

PILLOW_FORMATS = {'png': 'PNG', 'jpeg': 'JPEG', 'bmp': 'BMP', 'gif': 'GIF', 'tiff': 'TIFF', 'pcx': 'PCX',
                  'ico': 'ICO', 'webp': 'WEBP', 'ppm': 'PPM', 'qoi': 'QOI', 'sgi': 'SGI', 'dds': 'DDS'}
# Only decoders that write onto the prepared canvas; the others replace it, so nothing can be proved.
PARTIAL_FORMATS = frozenset({'png', 'jpeg', 'bmp', 'gif', 'pcx', 'ppm', 'tiff'})
SCENE_EDGES = (2048, 1600, 1280, 1024, 800, 640)
_EXIF_DATE = re.compile(r'^\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}$')


class Refuse(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _limit_resources() -> None:
    # Loaded by path: with -I this directory is not importable, and it should not be.
    spec = importlib.util.spec_from_file_location('rekindra_pdf_limits', Path(__file__).with_name('_pdf_worker.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._limit_resources()


def _opener(Image, data: bytes, tag: str, max_pixels: int):
    def open_image():
        try:
            image = Image.open(io.BytesIO(data), formats=[PILLOW_FORMATS[tag]])
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise Refuse('too_large') from exc
        if image.size[0] * image.size[1] > max_pixels:
            raise Refuse('too_large')
        return image
    return open_image


def _on_background(Image, open_image, fill: int):
    """Decode onto a canvas of one value, kept by load_prepare, without Pillow's fake end marker."""
    image = open_image()
    image._ended = True     # otherwise a truncated JPEG is padded with gray rows nothing wrote
    if getattr(image, '_frame_transparency', None) is not None:
        image._frame_transparency = None    # or GIF swaps the canvas for its own, and nothing can be proved
    bands = len(image.getbands())
    size = getattr(image, '_tile_size', image.size)     # TIFF decodes unrotated, then turns during load
    image.im = Image.new(image.mode, size, fill if bands == 1 else (fill,) * bands).im
    image.load()
    return image


def _written_mask(Image, ImageChops, low, high):
    """255 where both runs agree, so the decoder wrote that pixel."""
    if low.mode == '1':
        low, high = low.convert('L'), high.convert('L')
    width, height = low.size
    low_bytes, high_bytes = low.tobytes(), high.tobytes()
    per_pixel = len(low_bytes) // (width * height)
    nonzero = [0] + [255] * 255
    differs = ImageChops.difference(Image.frombytes('L', (width * per_pixel, height), low_bytes),
                                    Image.frombytes('L', (width * per_pixel, height), high_bytes)).point(nonzero)
    if per_pixel > 1:
        differs = differs.reduce((per_pixel, 1)).point(nonzero)
    return ImageChops.invert(differs)


def _high_bytes(Image, image):
    """An 8-bit view of I;16 from its high bytes, with no conversion rule to depend on."""
    return Image.frombytes('L', image.size, image.tobytes('raw', 'I;16')[1::2])


def _normalize(Image, image):
    mode, transparent = image.mode, 'transparency' in image.info
    try:
        if mode in ('RGBA', 'LA', 'I;16') or (mode in ('RGB', 'L') and not transparent):
            out = image
        elif mode in ('RGB', 'L', 'P', 'PA') and (transparent or mode == 'PA'):
            out = image.convert('RGBA')
        elif mode == 'P':
            out = image.convert('RGB')
        elif mode == '1':
            out = image.convert('L')
        elif mode.startswith('I;16'):
            out = image.convert('I').convert('I;16')
        elif mode == 'I':
            low, high = image.getextrema()
            if low < 0 or high > 65535:
                raise Refuse('unsupported_mode')
            out = image.convert('I;16')
        elif mode in ('CMYK', 'YCbCr', 'HSV', 'LAB'):
            out = image.convert('RGB')
        else:
            raise Refuse('unsupported_mode')
    except ValueError as exc:
        raise Refuse('unsupported_mode') from exc
    out = out.copy()
    out.info = {}
    return out


def _png(image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, 'PNG', compress_level=6)
    return buffer.getvalue()


def _complete(Image, ImageFile, open_image):
    """The fully decoded image, or None if the file is short or damaged."""
    ImageFile.LOAD_TRUNCATED_IMAGES = False
    try:
        image = open_image()
        image.load()
        return image
    except (Refuse, MemoryError):
        raise
    except Exception:
        return None


def _partial(Image, ImageChops, ImageFile, open_image, tag: str) -> tuple:
    """(cropped image with undecoded holes transparent, original size, decoded fraction)."""
    if tag not in PARTIAL_FORMATS:
        raise Refuse('damaged')
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    try:
        low = _on_background(Image, open_image, 0)
        high = _on_background(Image, open_image, 255)
    except (Refuse, MemoryError):
        raise
    except Exception as exc:
        raise Refuse('damaged') from exc
    written = _written_mask(Image, ImageChops, low, high)
    box = written.getbbox()
    if box is None:
        raise Refuse('no_pixels')
    width, height = low.size
    fraction = written.histogram()[255] / (width * height)
    cropped = low.crop(box)
    mask = written.crop(box)
    if mask.getextrema()[0] == 255:
        return cropped, (width, height), fraction
    if cropped.mode == 'I;16':
        cropped = _high_bytes(Image, cropped)
    normal = _normalize(Image, cropped).convert('RGBA')
    normal.putalpha(ImageChops.darker(normal.getchannel('A'), mask))
    return normal, (width, height), fraction


def _facts(open_image) -> dict:
    """Facts the file states about itself. Bad metadata never costs the pixels."""
    facts = {'exif_date': None, 'exif_date_tag': None, 'orientation': None, 'multi_frame': False}
    try:
        image = open_image()
        exif = image.getexif()
        for value, tag in ((exif.get_ifd(0x8769).get(36867), 'DateTimeOriginal'), (exif.get(306), 'DateTime')):
            if isinstance(value, str) and _EXIF_DATE.match(value):
                facts.update(exif_date=value, exif_date_tag=tag)
                break
        orientation = exif.get(0x0112)
        if type(orientation) is int and 2 <= orientation <= 8:
            facts['orientation'] = orientation
    except Exception:   # MemoryError included: these facts are optional
        pass
    try:
        facts['multi_frame'] = bool(getattr(open_image(), 'is_animated', False))
    except Exception:
        pass
    return facts


def _scene_copy(Image, image, png: bytes, budget: int):
    """A smaller PNG for a model when the full one is over budget; never used as the recovery."""
    if len(png) <= budget:
        return None, None
    source = _high_bytes(Image, image) if image.mode == 'I;16' else image
    for edge in SCENE_EDGES:
        if edge >= max(image.size):
            continue
        small = source.copy()
        small.thumbnail((edge, edge), Image.Resampling.LANCZOS)
        data = _png(small)
        if len(data) <= budget:
            return small, data
    return None, None


def recover(data: bytes, tag: str, max_pixels: int, scene_budget: int) -> tuple:
    import PIL
    from PIL import Image, ImageChops, ImageFile
    Image.MAX_IMAGE_PIXELS = max_pixels
    warnings.simplefilter('error', Image.DecompressionBombWarning)
    open_image = _opener(Image, data, tag, max_pixels)
    notes = []
    image = _complete(Image, ImageFile, open_image)
    partial = image is None
    fraction = 1.0
    if partial:
        image, original, fraction = _partial(Image, ImageChops, ImageFile, open_image, tag)
        notes.append(f'The file is damaged or short. Only the {round(fraction * 100, 1)}% of pixels the decoder '
                     'produced were kept; nothing was filled in.')
    else:
        original = image.size
    facts = _facts(open_image)
    if facts['multi_frame']:
        notes.append('The file holds several frames; only the first was recovered.')
    if tag == 'ico' and len(image.info.get('sizes') or ()) > 1:
        notes.append('The icon holds several sizes; only the largest was recovered.')
    out = _normalize(Image, image)
    if facts['orientation']:
        if tag != 'tiff':   # Pillow's TIFF reader already turned it during load
            out = out.transpose({2: Image.Transpose.FLIP_LEFT_RIGHT, 3: Image.Transpose.ROTATE_180,
                                 4: Image.Transpose.FLIP_TOP_BOTTOM, 5: Image.Transpose.TRANSPOSE,
                                 6: Image.Transpose.ROTATE_270, 7: Image.Transpose.TRANSVERSE,
                                 8: Image.Transpose.ROTATE_90}[facts['orientation']])
        notes.append(f"EXIF orientation {facts['orientation']} was applied.")
    full = _png(out)
    small, scene = _scene_copy(Image, out, full, scene_budget)
    if small is not None:
        notes.append(f'A {small.size[0]}x{small.size[1]} copy was made for scene models; the full recovery is unchanged.')
    header = {'kind': 'ok', 'pillow': PIL.__version__, 'source_format': tag,
              'width': out.size[0], 'height': out.size[1], 'partial': partial,
              'original_width': original[0], 'original_height': original[1],
              'decoded_fraction': round(fraction, 6), 'exif_date': facts['exif_date'],
              'exif_date_tag': facts['exif_date_tag'], 'exif_orientation': facts['orientation'],
              'multi_frame': facts['multi_frame'], 'warnings': notes, 'full_bytes': len(full),
              'scene_bytes': len(scene or b''), 'scene_width': small.size[0] if small is not None else None,
              'scene_height': small.size[1] if small is not None else None}
    return header, full, scene or b''


def main() -> None:
    reader_dir, tag, max_pixels, scene_budget = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    _limit_resources()
    sys.path.append(reader_dir)     # after the standard library, so nothing there can shadow it
    data = sys.stdin.buffer.read()
    full = scene = b''
    try:
        header, full, scene = recover(data, tag, max_pixels, scene_budget)
    except Refuse as exc:
        header = {'kind': 'refused', 'code': exc.code}
    except MemoryError:
        header = {'kind': 'refused', 'code': 'memory_limit'}
    except ImportError:
        header = {'kind': 'refused', 'code': 'reader_unavailable'}
    except Exception:
        header = {'kind': 'refused', 'code': 'damaged'}
    out = sys.stdout.buffer
    out.write(json.dumps(header).encode('ascii') + b'\n' + full + scene)
    out.flush()


if __name__ == '__main__':
    main()
