"""Small structural identification registry; extension alone is not evidence."""
import struct


def identify(header: bytes, name: str) -> str:
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if header.startswith(b'\xff\xd8\xff'):
        return 'jpeg'
    if header.startswith((b'GIF87a', b'GIF89a')):
        return 'gif'
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
