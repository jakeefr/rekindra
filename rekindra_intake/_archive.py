"""ZIP inventory from central-directory metadata alone.

Local headers are read only to compare offsets and names against the central
directory. Entry payloads are never read, decompressed or extracted, and nested
archives are never opened. Every size and checksum is a claim, not a measurement.
"""
import hashlib
import re
import struct
import unicodedata

from ._common import Warnings, display_name, envelope, extension, require_inputs

MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_ENTRIES = 256
MAX_NAME_CHARS = 512
EXPANSION_RATIO = 100
EXPANSION_MIN_BYTES = 1024 * 1024
EXPANSION_LARGE_BYTES = 1024 ** 3

_EOCD_SIGNATURE = b'PK\x05\x06'
_EOCD_RECORD = struct.Struct('<4sHHHHIIH')
_MAX_COMMENT = 0xFFFF
_ZIP64_LOCATOR_SIGNATURE = b'PK\x06\x07'
_ZIP64_LOCATOR_SIZE = 20
_CENTRAL_SIGNATURE = b'PK\x01\x02'
_CENTRAL_RECORD = struct.Struct('<4sHHHHHHIIIHHHHHII')
_LOCAL_SIGNATURE = b'PK\x03\x04'
_LOCAL_RECORD = struct.Struct('<4s22xHH')
_U16 = 0xFFFF
_U32 = 0xFFFFFFFF

_FLAG_ENCRYPTED = 0x0001
_FLAG_STRONG_ENCRYPTION = 0x0040
_FLAG_UTF8 = 0x0800
_FLAG_MASKED_HEADERS = 0x2000
_METHOD_AES = 99
_METHODS = {0: 'stored', 1: 'shrink', 6: 'implode', 8: 'deflate', 9: 'deflate64', 12: 'bzip2', 14: 'lzma',
            93: 'zstd', 95: 'xz', 98: 'ppmd', _METHOD_AES: 'aes'}
_SYSTEM_FAT = 0
_SYSTEM_UNIX = 3
_DOS_DIRECTORY = 0x10
_MODE_MASK = 0o170000
_MODE_DIRECTORY = 0o040000
_MODE_SYMLINK = 0o120000
_MODES_SPECIAL = {0o010000, 0o020000, 0o060000, 0o140000}
_UNICODE_PATH_EXTRA = 0x7075

_SEPARATORS = re.compile(r'[\\/]')
_DRIVE = re.compile(r'[A-Za-z]:')
_CONTROL = re.compile('[\x00-\x1f\x7f-\x9f\u200e\u200f\u202a-\u202e\u2066-\u2069]')
_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
_NESTED_SUFFIXES = ('.zip', '.jar', '.war', '.apk', '.7z', '.rar', '.tar', '.gz', '.tgz', '.bz2', '.xz', '.cab', '.iso')

# These mean the metadata contradicts itself, so the inventory itself is doubtful.
_INTEGRITY_FLAGS = {'entry_out_of_bounds', 'local_header_missing', 'local_name_mismatch', 'overlapping_entries',
                    'size_inconsistent'}
_MESSAGES = {
    'absolute_path': 'An entry name is an absolute path.',
    'backslash_separator': 'An entry name uses backslashes, which act as separators on Windows.',
    'case_fold_collision': 'Entry names differ only by case, Unicode form or path spelling.',
    'colon_in_name': 'An entry name contains a colon, which can address an NTFS stream.',
    'control_character_in_name': 'An entry name contains control or text-direction characters.',
    'directory_with_data': 'A directory entry claims to contain data.',
    'drive_path': 'An entry name begins with a Windows drive.',
    'duplicate_name': 'Several entries share one name.',
    'empty_name': 'An entry has an empty name.',
    'encrypted': 'An entry is marked encrypted. Its payload cannot be read without a password.',
    'entry_out_of_bounds': 'An entry claims data outside the area before the central directory.',
    'local_header_missing': 'No local header exists at the offset an entry claims.',
    'local_name_mismatch': 'An entry has different names in its local and central headers.',
    'name_not_decodable': 'An entry name is not valid UTF-8; undecodable bytes are shown as escapes.',
    'nested_archive_not_inspected': 'An entry looks like an archive. It was not opened.',
    'overlapping_entries': 'Entries claim overlapping byte ranges, a known decompression-bomb construction.',
    'path_traversal': 'An entry name climbs out of its directory with parent-directory segments.',
    'size_inconsistent': 'A stored entry claims different compressed and uncompressed sizes.',
    'special_file': 'An entry claims to be a device, FIFO or socket.',
    'suspicious_expansion': 'An entry claims an extreme expansion. This is metadata; nothing was decompressed.',
    'symlink': 'An entry claims to be a symbolic link.',
    'unc_path': 'An entry name is a UNC network or device path.',
    'unicode_lookalike_path': 'An entry name becomes a dangerous path after Unicode normalization.',
    'unicode_path_extra': 'An entry carries an alternate Unicode path in an extra field. It was not decoded.',
    'unknown_compression_method': 'An entry uses an unrecognized compression method id.',
    'windows_reserved_name': 'An entry name uses a Windows reserved device name.',
}


def _find_eocd(data):
    """Return (offset, has trailing bytes, ambiguous).

    A comment can hold a forged end record, and both then reach end of file
    exactly. Prefer the one whose directory really ends where it begins.
    """
    floor = max(0, len(data) - _EOCD_RECORD.size - _MAX_COMMENT)
    exact, consistent, fallback = [], [], None
    position = data.rfind(_EOCD_SIGNATURE, floor)
    while position >= 0:
        if position + _EOCD_RECORD.size <= len(data):
            fields = _EOCD_RECORD.unpack_from(data, position)
            end = position + _EOCD_RECORD.size + fields[7]
            if end == len(data):
                exact.append(position)
                if fields[5] + fields[6] == position:
                    consistent.append(position)
            elif end < len(data) and fallback is None:
                fallback = position
        position = data.rfind(_EOCD_SIGNATURE, floor, position + len(_EOCD_SIGNATURE) - 1)
    if exact:
        return (consistent or exact)[0], False, len(exact) > 1
    return fallback, fallback is not None, False


def _decode_name(raw, flags):
    if not flags & _FLAG_UTF8:
        return raw.decode('cp437'), 'cp437', True
    try:
        return raw.decode('utf-8'), 'utf-8', True
    except UnicodeDecodeError:
        return raw.decode('utf-8', 'backslashreplace'), 'utf-8', False


def _path_flags(name):
    found = set()
    if not name:
        return {'empty_name'}
    if '\\' in name:
        found.add('backslash_separator')
    if name.startswith(('\\\\', '//')):
        found.add('unc_path')
    elif name.startswith(('/', '\\')):
        found.add('absolute_path')
    rest = name
    if _DRIVE.match(name):
        found.add('drive_path')
        rest = name[2:]
    if ':' in rest:
        found.add('colon_in_name')
    if _CONTROL.search(name):
        found.add('control_character_in_name')
    for part in _SEPARATORS.split(name):
        if len(part) >= 2 and not part.strip('. '):
            found.add('path_traversal')
        if part.split('.')[0].rstrip(' ').upper() in _RESERVED:
            found.add('windows_reserved_name')
    return found


def _has_unicode_path(extra):
    position = 0
    while position + 4 <= len(extra):
        tag, size = struct.unpack_from('<HH', extra, position)
        if tag == _UNICODE_PATH_EXTRA:
            return True
        position += 4 + size
    return False


def _collision_key(name):
    parts = [part for part in _SEPARATORS.split(name) if part not in ('', '.')]
    return unicodedata.normalize('NFC', unicodedata.normalize('NFC', '/'.join(parts)).casefold())


def _flag_collisions(entries, names):
    groups = {}
    for index, name in enumerate(names):
        groups.setdefault(_collision_key(name), []).append(index)
    for indexes in groups.values():
        spellings = {names[index] for index in indexes}
        for index in indexes:
            if sum(names[other] == names[index] for other in indexes) > 1:
                entries[index]['safety_warnings'].append('duplicate_name')
            if len(spellings) > 1:
                entries[index]['safety_warnings'].append('case_fold_collision')


def _flag_overlaps(entries, spans):
    deepest_end, holder = -1, None
    for start, end, index in sorted(spans):
        if start < deepest_end:
            entries[index]['safety_warnings'].append('overlapping_entries')
            entries[holder]['safety_warnings'].append('overlapping_entries')
        if end > deepest_end:
            deepest_end, holder = end, index


def _check_local(data, offset, compressed, raw_name, limit, flags):
    """Compare the local header with the central record. Return the entry's span."""
    if offset + _LOCAL_RECORD.size > limit:
        flags.add('entry_out_of_bounds')
        return None
    signature, name_length, extra_length = _LOCAL_RECORD.unpack_from(data, offset)
    if signature != _LOCAL_SIGNATURE:
        flags.add('local_header_missing')
        return None
    payload_start = offset + _LOCAL_RECORD.size + name_length + extra_length
    if data[offset + _LOCAL_RECORD.size:offset + _LOCAL_RECORD.size + name_length] != raw_name:
        flags.add('local_name_mismatch')
    if payload_start + compressed > limit:
        flags.add('entry_out_of_bounds')
        return None
    return offset, payload_start + compressed


def _describe(data, fields, position, cd_offset):
    """Turn one central record into (entry, span, decoded full name)."""
    _, made_by, _, flags, method, _, _, crc, compressed, uncompressed, name_length, extra_length, _, _, _, \
        external, local_offset = fields
    name_start = position + _CENTRAL_RECORD.size
    raw_name = data[name_start:name_start + name_length]
    name, name_encoding, decodable = _decode_name(raw_name, flags)
    found = _path_flags(name)
    if not name.isascii():
        lookalike = _path_flags(unicodedata.normalize('NFKC', name))
        if lookalike - found - {'colon_in_name', 'windows_reserved_name'}:
            found.add('unicode_lookalike_path')
    if not decodable:
        found.add('name_not_decodable')
    # Windows drops trailing dots and spaces on extraction, so 'a.zip. ' lands as 'a.zip'.
    if name.rstrip(' .').lower().endswith(_NESTED_SUFFIXES):
        found.add('nested_archive_not_inspected')
    if _has_unicode_path(data[name_start + name_length:name_start + name_length + extra_length]):
        found.add('unicode_path_extra')

    system, mode = made_by >> 8, (external >> 16) & _MODE_MASK
    is_directory = (name.endswith(('/', '\\')) or mode == _MODE_DIRECTORY
                    or (system == _SYSTEM_FAT and bool(external & _DOS_DIRECTORY)))
    if mode == _MODE_SYMLINK:
        found.add('symlink')
    elif mode in _MODES_SPECIAL:
        found.add('special_file')
    if is_directory and uncompressed:
        found.add('directory_with_data')

    encrypted = bool(flags & _FLAG_ENCRYPTED) or method == _METHOD_AES
    if encrypted:
        found.add('encrypted')
    if method not in _METHODS:
        found.add('unknown_compression_method')
    if method == 0 and compressed != uncompressed and not encrypted:
        found.add('size_inconsistent')
    if (uncompressed >= EXPANSION_LARGE_BYTES
            or (uncompressed and not compressed)
            or (uncompressed >= EXPANSION_MIN_BYTES and uncompressed >= compressed * EXPANSION_RATIO)):
        found.add('suspicious_expansion')

    span = _check_local(data, local_offset, compressed, raw_name, cd_offset, found)
    entry = {'name': name[:MAX_NAME_CHARS], 'name_encoding': name_encoding, 'name_bytes': name_length,
             'name_truncated': len(name) > MAX_NAME_CHARS, 'is_directory': is_directory,
             'compressed_size_bytes': compressed, 'claimed_uncompressed_size_bytes': uncompressed,
             'compression_method': method, 'compression_method_name': _METHODS.get(method, 'unknown'),
             'claimed_crc32': f'{crc:08x}', 'encrypted': encrypted, 'safety_warnings': sorted(found)}
    return entry, span, name


def _walk(data, cd_offset, cd_end):
    """Walk records up to MAX_ENTRIES. Returns (entries, names, spans, stop reason)."""
    entries, names, spans = [], [], []
    position = cd_offset
    while position < cd_end:
        if len(entries) == MAX_ENTRIES:
            return entries, names, spans, 'limit'
        if position + _CENTRAL_RECORD.size > cd_end:
            return entries, names, spans, 'malformed'
        fields = _CENTRAL_RECORD.unpack_from(data, position)
        record_end = position + _CENTRAL_RECORD.size + sum(fields[10:13])
        if fields[0] != _CENTRAL_SIGNATURE or record_end > cd_end:
            return entries, names, spans, 'malformed'
        if _U32 in (fields[8], fields[9], fields[16]) or fields[13] == _U16:
            return entries, names, spans, 'zip64_unsupported'
        if fields[13]:
            return entries, names, spans, 'multidisk_unsupported'
        if fields[3] & (_FLAG_STRONG_ENCRYPTION | _FLAG_MASKED_HEADERS):
            return entries, names, spans, 'strong_encryption_unsupported'
        entry, span, name = _describe(data, fields, position, cd_offset)
        if span:
            spans.append((*span, len(entries)))
        entries.append(entry)
        names.append(name)
        position = record_end
    return entries, names, spans, None


def inspect_archive(data: bytes, filename: str) -> dict:
    """Inventory a ZIP from metadata. Raises TypeError only for wrong argument types."""
    require_inputs(data, filename)
    warnings = Warnings()
    name, basename = display_name(filename, warnings)
    size = len(data)

    def result(fmt, status, sha256, facts):
        return envelope(fmt, status, name, size, sha256, facts, warnings)

    if size > MAX_INPUT_BYTES:
        warnings.add('input_too_large', f'Input exceeds the {MAX_INPUT_BYTES} byte archive budget and was not read.')
        return result('unknown', 'rejected', None, {'limit_bytes': MAX_INPUT_BYTES})
    digest = hashlib.sha256(data).hexdigest()

    def stop(status, code, message, facts=None):
        warnings.add(code, message)
        return result('zip', status, digest, facts or {})

    eocd, trailing, ambiguous = _find_eocd(data)
    if eocd is None:
        if data.startswith((_LOCAL_SIGNATURE, _EOCD_SIGNATURE)):
            return stop('rejected', 'eocd_missing', 'The end-of-central-directory record is missing, so the file is truncated.')
        warnings.add('not_a_zip', 'No ZIP end-of-central-directory record was found.')
        return result('unknown', 'rejected', digest, {})
    zip64_message = 'ZIP64 archives are recognized but not inventoried.'
    multidisk_message = 'Multi-disk archives are recognized but not inventoried.'
    _, disk, cd_disk, on_disk, declared, cd_size, cd_offset, comment = _EOCD_RECORD.unpack_from(data, eocd)
    locator = eocd - _ZIP64_LOCATOR_SIZE
    if (_U16 in (disk, cd_disk, on_disk, declared) or _U32 in (cd_size, cd_offset)
            or (locator >= 0 and data.startswith(_ZIP64_LOCATOR_SIGNATURE, locator))):
        return stop('unsupported', 'zip64_unsupported', zip64_message)
    if disk or cd_disk or on_disk != declared:
        return stop('unsupported', 'multidisk_unsupported', multidisk_message)
    cd_end = cd_offset + cd_size
    if cd_end > eocd:
        return stop('rejected', 'central_directory_out_of_bounds', 'The central directory claims bytes beyond its end record.')
    if cd_end < eocd:
        return stop('unsupported', 'prepended_data_unsupported',
                    'Bytes separate the central directory from its end record, as in self-extracting archives.')

    entries, names, spans, stopped = _walk(data, cd_offset, cd_end)
    if stopped == 'zip64_unsupported':
        return stop('unsupported', stopped, zip64_message)
    if stopped == 'multidisk_unsupported':
        return stop('unsupported', stopped, multidisk_message)
    if stopped == 'strong_encryption_unsupported':
        return stop('unsupported', stopped, 'Strong or header-masking encryption is recognized but not inventoried.')
    _flag_collisions(entries, names)
    _flag_overlaps(entries, spans)
    for entry in entries:
        entry['safety_warnings'] = sorted(set(entry['safety_warnings']))

    status = 'ok'
    if stopped == 'malformed':
        warnings.add('central_directory_malformed', 'A central-directory record is damaged; walking stopped there.')
        status = 'partial'
    elif stopped == 'limit':
        warnings.add('entry_limit_exceeded', f'Only the first {MAX_ENTRIES} entries were read. '
                                             'Later entries were not examined and may be dangerous.')
        status = 'partial'
    elif len(entries) != declared:
        warnings.add('entry_count_mismatch', 'The declared entry count differs from the records found.')
        status = 'partial'
    if trailing:
        warnings.add('trailing_data', 'Bytes follow the end-of-central-directory record.')
        status = 'partial'
    if ambiguous:
        warnings.add('multiple_eocd_candidates', 'Several end records fit this file; other readers may choose another.')
        status = 'partial'
    if extension(basename) not in ('', '.zip'):
        warnings.add('extension_mismatch', 'The bytes are a ZIP although the file name suggests otherwise.')

    if any(entry['name_truncated'] for entry in entries):
        warnings.add('entry_name_truncated', f'At least one entry name is longer than the {MAX_NAME_CHARS} characters returned.')

    flagged = sum(1 for entry in entries if entry['safety_warnings'])
    found = sorted({code for entry in entries for code in entry['safety_warnings']})
    for code in found:
        warnings.add(code, _MESSAGES[code])
    if _INTEGRITY_FLAGS.intersection(found):
        status = 'partial'
    total_claimed = sum(entry['claimed_uncompressed_size_bytes'] for entry in entries)
    if total_claimed >= EXPANSION_LARGE_BYTES:
        warnings.add('suspicious_total_expansion', 'Entries together claim an extreme size. Nothing was decompressed.')
    if not entries and (stopped == 'malformed' or declared):
        status = 'rejected'
    return result('zip', status, digest, {
        'archive_type': 'zip', 'entry_count_declared': declared, 'entries_inspected': len(entries),
        'entries_truncated': stopped == 'limit', 'flagged_entry_count': flagged,
        'total_compressed_bytes': sum(entry['compressed_size_bytes'] for entry in entries),
        'total_claimed_uncompressed_bytes': total_claimed, 'comment_bytes': comment,
        'payloads_read': False, 'extraction_performed': False, 'claimed_sizes_verified': False,
        'untrusted_content': True, 'entries': entries})
