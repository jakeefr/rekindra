"""Recover common image formats to normalized PNG in a killable child process under hard caps.

Pillow parses untrusted bytes in ``_image_worker.py``, never in the gateway. Damaged files
keep only the pixels that were really decoded and are marked partial; nothing is invented.
The original TGA decoder stays separate and does not need Pillow.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

from .pdf_text import ReaderBusy, _WORKER_SLOTS, _python

IMAGE_FORMATS = frozenset({'png', 'jpeg', 'bmp', 'gif', 'tiff', 'pcx', 'ico', 'webp', 'ppm', 'qoi', 'sgi', 'dds'})
MAX_IMAGE_BYTES = 64 * 1024 * 1024
MAX_PIXELS = 20_000_000
TIMEOUT_SECONDS = 30.0
SCENE_BYTES = 1_900_000
WORKER = Path(__file__).with_name('_image_worker.py')
_PNG = b'\x89PNG\r\n\x1a\n'
_HEX = re.compile(r'#[0-9A-F]{6}')
_LOCATIONS = frozenset({'top band', 'middle', 'bottom band', 'top band and middle', 'middle and bottom band',
                        'top band and bottom band', 'throughout'})

_REFUSALS = {
    'too_large': ('image_too_large', f'The image is over the {MAX_PIXELS}-pixel limit, so it was not decoded.'),
    'damaged': ('damaged_image', 'The image is damaged and no pixels could be proved to have decoded.'),
    'no_pixels': ('damaged_image', 'The image is damaged and none of its pixels decoded.'),
    'unsupported_mode': ('unsupported_image_mode', 'This image uses a pixel format that cannot be stored as PNG without changing its values.'),
    'memory_limit': ('image_memory_limit', 'Decoding this image hit the memory limit, so its contents are unknown.'),
    'reader_unavailable': ('image_reader_unavailable', 'The image reader (Pillow) is not installed or could not be loaded in this Hermes environment.'),
}


class ImageRefused(Exception):
    """A decided outcome for this asset, with a stable code for the agent."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def clean_palette(palette) -> list | None:
    """The child's palette if it has exactly the promised shape, since the child reads untrusted bytes."""
    if not isinstance(palette, list) or len(palette) > 6:
        return None
    for entry in palette:
        if (not isinstance(entry, dict) or set(entry) != {'hex', 'location', 'coverage'}
                or not isinstance(entry['hex'], str) or not _HEX.fullmatch(entry['hex'])
                or not isinstance(entry['location'], str) or entry['location'] not in _LOCATIONS
                or type(entry['coverage']) is not float or not 0 <= entry['coverage'] <= 100):
            return None
    return palette


def _clean_regions(regions) -> list | None:
    """The measured preview bands if they have exactly the promised shape."""
    if not isinstance(regions, list) or [item.get('region') if isinstance(item, dict) else None for item in regions] != ['top band', 'middle', 'bottom band']:
        return None
    for item in regions:
        colors = item.get('colors')
        if not isinstance(colors, list) or not 1 <= len(colors) <= 4:
            return None
        for color in colors:
            if (not isinstance(color, dict) or not isinstance(color.get('hex'), str) or not _HEX.fullmatch(color['hex'])
                    or type(color.get('coverage')) is not float):
                return None
    return regions


def _reader_dir() -> str | None:
    """The directory holding Pillow, found without importing it into the gateway."""
    try:
        spec = importlib.util.find_spec('PIL')
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.origin:
        return None
    return str(Path(spec.origin).resolve().parent.parent)


def _run_worker(python: str, reader_dir: str, data: bytes, tag: str) -> tuple[bytes, bool]:
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'PATH') if key in os.environ}
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    process = subprocess.Popen([python, '-I', '-S', '-B', str(WORKER), reader_dir, tag, str(MAX_PIXELS), str(SCENE_BYTES)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               env=env, creationflags=flags)
    try:
        output, _ = process.communicate(data, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        return b'', True
    return output, False


def _stopped() -> ImageRefused:
    # No verdict from the reader, so this says nothing about whether the file is damaged.
    return ImageRefused('image_reader_stopped', 'The image reader stopped before finishing, so the contents of this file are unknown.')


def measure_review_sheet(png: bytes) -> list | None:
    """Rendered colors per band of a preview sheet, or None when they could not be measured."""
    reader_dir, python = _reader_dir(), _python()
    if reader_dir is None or python is None or not _WORKER_SLOTS.acquire(timeout=TIMEOUT_SECONDS):
        return None
    try:
        output, timed_out = _run_worker(python, reader_dir, png, 'review-sheet')
    except OSError:
        return None
    finally:
        _WORKER_SLOTS.release()
    line, newline, _ = output.partition(b'\n')
    if timed_out or not newline:
        return None
    try:
        header = json.loads(line)
    except ValueError:
        return None
    return _clean_regions(header.get('regions')) if isinstance(header, dict) and header.get('kind') == 'ok' else None


def read_image(data: bytes, tag: str) -> dict:
    """Return {'header': metadata, 'full': PNG bytes, 'scene': smaller PNG bytes or None}."""
    if tag not in IMAGE_FORMATS:
        raise ImageRefused('unsupported_image_format', f'{tag} is not an image format this reader handles.')
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageRefused('image_too_large', f'The image is larger than the {MAX_IMAGE_BYTES}-byte limit.')
    reader_dir, python = _reader_dir(), _python()
    if reader_dir is None or python is None:
        raise ImageRefused(*_REFUSALS['reader_unavailable'])
    # Long enough for two hung workers to reach their deadlines and free a slot.
    if not _WORKER_SLOTS.acquire(timeout=TIMEOUT_SECONDS * 3):
        raise ReaderBusy('Other files were being read for too long; recover this one again.')
    try:
        output, timed_out = _run_worker(python, reader_dir, data, tag)
    except OSError as exc:
        raise ImageRefused('image_reader_unavailable', 'The image reader process could not be started.') from exc
    finally:
        _WORKER_SLOTS.release()
    if timed_out:
        raise ImageRefused('image_timeout', f'Decoding stopped after {TIMEOUT_SECONDS:g} seconds, so the contents of this file are unknown.')
    line, newline, rest = output.partition(b'\n')
    try:
        header = json.loads(line) if newline else None
    except ValueError:
        header = None
    if not isinstance(header, dict):
        raise _stopped()
    if header.get('kind') == 'refused':
        code, message = _REFUSALS.get(header.get('code'), _REFUSALS['damaged'])
        raise ImageRefused(code, message)
    full_size, scene_size = header.get('full_bytes'), header.get('scene_bytes')
    if (header.get('kind') != 'ok' or type(full_size) is not int or type(scene_size) is not int
            or full_size <= 0 or scene_size < 0 or full_size + scene_size != len(rest)):
        raise _stopped()
    full, scene = rest[:full_size], rest[full_size:]
    if not full.startswith(_PNG) or (scene and not scene.startswith(_PNG)):
        raise _stopped()
    return {'header': header, 'full': full, 'scene': scene or None}
