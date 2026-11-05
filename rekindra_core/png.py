"""Small RGBA PNG writer using only the standard-library DEFLATE primitive."""
import struct
import zlib
from .tga import Raster, RecoveryError


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff)


def encode_png(raster: Raster) -> bytes:
    if raster.width <= 0 or raster.height <= 0 or len(raster.rgba) != raster.width * raster.height * 4:
        raise RecoveryError('Invalid raster size')
    compressor = zlib.compressobj()
    chunks = []
    stride = raster.width * 4
    for y in range(raster.height):
        chunks.append(compressor.compress(b'\0' + raster.rgba[y*stride:(y+1)*stride]))
    chunks.append(compressor.flush())
    header = struct.pack('>IIBBBBB', raster.width, raster.height, 8, 6, 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', header) + _chunk(b'IDAT', b''.join(chunks)) + _chunk(b'IEND', b'')
