"""Name files Rekindra cannot recover, from their leading bytes only.

This reads the header bytes already captured at inspect time. It never opens,
parses, or runs the file, and it never changes what the recovery router accepts.
Very short magic numbers are checked against a second structural field so random
bytes are not given a confident name.
"""
import re
import struct

COMPOUND = 'Microsoft compound file (legacy Office document or Thumbs.db)'

_PREFIXES = (
    (b'Rar!\x1a\x07', 'RAR archive'),
    (b"7z\xbc\xaf'\x1c", '7-Zip archive'),
    (b'\x1f\x8b\x08', 'gzip archive'),
    (b'\xfd7zXZ\0', 'xz archive'),
    (b'\x28\xb5\x2f\xfd', 'Zstandard archive'),
    (b'MSCF\0\0\0\0', 'Windows cabinet archive'),
    (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1', COMPOUND),
    (b'SQLite format 3\0', 'SQLite database'),
    (b'\xffWPC', 'WordPerfect document'),
    (b'L\0\0\0\x01\x14\x02\0', 'Windows shortcut'),
    (b'\x7fELF', 'ELF executable'),
    (b'\xcf\xfa\xed\xfe', 'macOS executable'),
    (b'\xce\xfa\xed\xfe', 'macOS executable'),
    (b'\xfe\xed\xfa\xce', 'macOS executable'),
    (b'\xfe\xed\xfa\xcf', 'macOS executable'),
    (b'\xca\xfe\xba\xbe', 'Java class or macOS universal binary'),
    (b'\0asm\x01\0\0\0', 'WebAssembly module'),
    (b'8BPS\0\x01', 'Photoshop document'),
    (b'8BPS\0\x02', 'Photoshop document'),
    (b'\0\0\0\x0cjP  \r\n\x87\n', 'JPEG 2000 image'),
    (b'fLaC', 'FLAC audio'),
    (b'OggS\0', 'Ogg media'),
    (b'MThd\0\0\0\x06', 'MIDI audio'),
    (b'OTTO', 'OpenType font'),
    (b'wOFF', 'WOFF font'),
    (b'wOF2', 'WOFF2 font'),
)
_HEIF_BRANDS = (b'heic', b'heix', b'hevc', b'hevx', b'heim', b'heis')
_HEIF_CONTAINER_BRANDS = (b'mif1', b'msf1')
_MP4_BRANDS = (b'isom', b'iso2', b'iso3', b'iso4', b'iso5', b'iso6', b'mp41', b'mp42', b'avc1', b'M4V ', b'M4VH', b'M4VP', b'dash', b'f4v ')


def _is_pe(header):
    if len(header) < 64 or header[:2] != b'MZ':
        return False
    offset = struct.unpack_from('<I', header, 0x3c)[0]
    return offset + 4 <= len(header) and header[offset:offset + 4] == b'PE\0\0'


def _iso_media_kind(header):
    """Name an ISO base media file from the brands in its opening ftyp box."""
    if len(header) < 12 or header[4:8] != b'ftyp':
        return None
    size = struct.unpack_from('>I', header, 0)[0]
    if size < 16 or size > len(header):
        return None
    major = header[8:12]
    brands = [major] + [header[i:i + 4] for i in range(16, size - 3, 4)]
    if b'avif' in brands or b'avis' in brands:
        return 'AVIF image'
    if any(brand in _HEIF_BRANDS for brand in brands) or major in _HEIF_CONTAINER_BRANDS:
        return 'HEIC/HEIF image'
    if major == b'qt  ':
        return 'QuickTime video'
    if major in (b'M4A ', b'M4B ', b'M4P '):
        return 'M4A audio'
    if major == b'crx ':
        return 'Canon CR3 raw image'
    if major in _MP4_BRANDS or major[:3] in (b'3gp', b'3g2'):
        return 'MP4 video'
    return 'ISO media file'


def _matroska_kind(header):
    if header[:4] != b'\x1a\x45\xdf\xa3':
        return None
    opening = header[:64]
    if b'webm' in opening:
        return 'WebM video'
    if b'matroska' in opening:
        return 'Matroska video'
    return None


def file_kind(header: bytes):
    """Return a plain name for the file these bytes open, or None."""
    for prefix, name in _PREFIXES:
        if header.startswith(prefix):
            return name
    if re.match(rb'BZh[1-9]1AY&SY', header):
        return 'bzip2 archive'
    if _is_pe(header):
        return 'Windows executable'
    if header[:4] == b'RIFF' and header[8:12] == b'AVI ':
        return 'AVI video'
    if header[:4] == b'RIFF' and header[8:12] == b'WAVE':
        return 'WAV audio'
    if header[:3] == b'ID3' and len(header) >= 10 and header[3] in (2, 3, 4) and header[4] != 0xff:
        return 'MP3 audio'
    if header[257:262] == b'ustar':
        return 'TAR archive'
    if header[32769:32774] == b'CD001':
        return 'ISO disc image'
    return _iso_media_kind(header) or _matroska_kind(header)


def identification(header: bytes) -> str:
    """The sentence reported for a file that no recovery route accepts."""
    kind = file_kind(header)
    if kind is None:
        return 'no known file signature, not supported'
    return f'identified as {kind}, not supported yet'
