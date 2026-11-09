"""Small structural identification registry; extension alone is not evidence."""
import re
import struct

_BMP_DIB_SIZES = (12, 16, 40, 52, 56, 64, 108, 124)
_PNM = re.compile(rb'P[56]\s+(?:#[^\n]*\n\s*)*\d+\s+\d+\s')


def _image_signature(header: bytes, name: str) -> str | None:
    """Structure beyond the magic bytes, so short magics do not claim unrelated files."""
    if header.startswith(b'BM') and len(header) >= 18 and struct.unpack_from('<I', header, 14)[0] in _BMP_DIB_SIZES:
        return 'bmp'
    if header.startswith((b'II*\0', b'MM\0*', b'II+\0', b'MM\0+')):
        return 'tiff'
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return 'webp'
    if header.startswith(b'\0\0\1\0') and len(header) >= 22 and header[4:6] != b'\0\0' and header[9] == 0:
        return 'ico'
    if len(header) >= 128 and header[0] == 0x0a and header[1] in (0, 2, 3, 4, 5) and header[2] == 1 and header[3] in (1, 2, 4, 8):
        return 'pcx'
    if header.startswith(b'\x01\xda') and len(header) >= 4 and header[2] in (0, 1) and header[3] in (1, 2):
        return 'sgi'
    if header.startswith(b'qoif') and len(header) >= 14 and header[12] in (3, 4) and header[13] in (0, 1):
        return 'qoi'
    if header.startswith(b'DDS ') and len(header) >= 8 and struct.unpack_from('<I', header, 4)[0] == 124:
        return 'dds'
    # The P5/P6 opening is plain text, so a text file needs the extension to count as an image.
    if _PNM.match(header) and (name.lower().endswith(('.ppm', '.pgm', '.pnm')) or any(b < 9 or b > 126 for b in header[:4096])):
        return 'ppm'
    return None


def identify(header: bytes, name: str) -> str:
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if header.startswith(b'\xff\xd8\xff'):
        return 'jpeg'
    if header.startswith((b'GIF87a', b'GIF89a')):
        return 'gif'
    image = _image_signature(header, name)
    if image:
        return image
    if header.startswith((b'PK\x03\x04', b'PK\x05\x06')):
        return 'zip'
    if header.startswith(b'%PDF-') or name.lower().endswith('.pdf'):
        return 'pdf'
    if len(header) >= 18:
        width, height = struct.unpack_from('<HH', header, 12)
        if header[1] == 0 and header[2] in (2, 10) and header[16] in (24, 32) and width and height:
            return 'tga'
    if name.lower().endswith('.tga'):
        return 'tga_candidate'
    try:
        text = header.decode('utf-8-sig')
        if all(c >= ' ' or c in '\t\r\n' for c in text):
            return 'text'
    except UnicodeDecodeError:
        pass
    return 'unknown'
