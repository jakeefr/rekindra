"""Bounded Truevision TGA true-color decoder, implemented from the format spec.

Supported: image types 2/10, 24/32-bit pixels, four origins, no interleaving.
No source execution, external converters, or inferred replacement pixels.
"""
from dataclasses import dataclass
import struct


class RecoveryError(ValueError):
    """The supplied file cannot be recovered by this supported decoder."""


@dataclass(frozen=True)
class Raster:
    width: int
    height: int
    rgba: bytes
    warnings: tuple[str, ...] = ()


def decode_tga(data: bytes, max_pixels: int = 20_000_000) -> Raster:
    if len(data) < 18:
        raise RecoveryError('Truncated TGA header')
    id_size, cmap, kind, _, _, _, _, _, width, height, depth, desc = struct.unpack_from('<BBBHHBHHHHBB', data)
    if cmap != 0 or kind not in (2, 10) or depth not in (24, 32):
        raise RecoveryError('Unsupported TGA: requires true-color type 2/10, 24/32-bit, no palette')
    attributes = desc & 15
    if desc & 192 or attributes not in ((0,) if depth == 24 else (0, 8)):
        raise RecoveryError('Unsupported TGA interleaving or attribute depth')
    pixels = width * height
    if not width or not height or pixels > max_pixels:
        raise RecoveryError('Invalid dimensions or decoded pixel limit exceeded')
    stride, cursor = depth // 8, 18 + id_size
    pixel_end = len(data)
    if len(data) >= 26 and data[-18:] == b'TRUEVISION-XFILE.\0':
        pixel_end = len(data) - 26
        extension, developer = struct.unpack_from('<II', data, pixel_end)
        for offset in (extension, developer):
            if offset:
                if not cursor <= offset < len(data) - 26:
                    raise RecoveryError('Invalid TGA metadata offset')
                pixel_end = min(pixel_end, offset)
    if cursor > pixel_end:
        raise RecoveryError('Truncated TGA image ID')
    required = pixels * stride
    if kind == 2:
        if pixel_end - cursor < required:
            raise RecoveryError('Truncated TGA pixel data; missing pixels are not invented')
        raw = data[cursor:cursor + required]
        cursor += required
    else:
        raw = bytearray()
        while len(raw) < required:
            if cursor >= pixel_end:
                raise RecoveryError('Truncated TGA RLE packet')
            packet = data[cursor]
            cursor += 1
            count = (packet & 127) + 1
            if len(raw) + count * stride > required:
                raise RecoveryError('TGA RLE packet exceeds image bounds')
            amount = stride if packet & 128 else count * stride
            if cursor + amount > pixel_end:
                raise RecoveryError('Truncated TGA RLE payload')
            payload = data[cursor:cursor + amount]
            raw.extend(payload * count if packet & 128 else payload)
            cursor += amount
    rgba = bytearray(pixels * 4)
    rgba[0::4] = raw[2::stride]
    rgba[1::4] = raw[1::stride]
    rgba[2::4] = raw[0::stride]
    rgba[3::4] = raw[3::stride] if attributes == 8 else b'\xff' * pixels
    if not desc & 32:
        row_bytes = width * 4
        for y in range(height // 2):
            a, b = y * row_bytes, (height - y - 1) * row_bytes
            rgba[a:a+row_bytes], rgba[b:b+row_bytes] = rgba[b:b+row_bytes], rgba[a:a+row_bytes]
    if desc & 16:
        for y in range(height):
            for x in range(width // 2):
                a, b = (y * width + x) * 4, (y * width + width - x - 1) * 4
                rgba[a:a+4], rgba[b:b+4] = rgba[b:b+4], rgba[a:a+4]
    warnings = ('Trailing metadata preserved in original; not interpreted.',) if cursor < len(data) else ()
    return Raster(width, height, bytes(rgba), warnings)
