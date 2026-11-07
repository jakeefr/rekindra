"""Result envelope and untrusted-filename handling shared by both inspectors."""
import posixpath
import re
import unicodedata

SCHEMA_VERSION = 1
MAX_NAME_CHARS = 255
_NAME_TAIL_CHARS = 4096
_PLACEHOLDER = 'unnamed'
_SEPARATOR = re.compile(r'[\\/]')
_DRIVE_PREFIX = re.compile(r'^[A-Za-z]:')
_UNSAFE_CATEGORIES = {'Cc', 'Cf', 'Cs', 'Zl', 'Zp'}


class Warnings:
    """Ordered warnings holding one entry per stable code."""

    def __init__(self):
        self._items = {}

    def add(self, code, message):
        self._items.setdefault(code, message)

    def as_list(self):
        return [{'code': code, 'message': message} for code, message in self._items.items()]


def require_inputs(data, filename):
    """Wrong Python types are caller bugs; malformed content never raises."""
    if not isinstance(data, bytes):
        raise TypeError('data must be bytes')
    if not isinstance(filename, str):
        raise TypeError('filename must be str')


def display_name(filename, warnings):
    """Return (bounded display name, full basename). The name is never opened."""
    base = _SEPARATOR.split(filename[-_NAME_TAIL_CHARS:])[-1]
    base = _DRIVE_PREFIX.sub('', base)
    cleaned = ''.join('_' if unicodedata.category(c) in _UNSAFE_CATEGORIES else c for c in base)
    if cleaned != base:
        warnings.add('filename_sanitized', 'Unsafe characters in the display name were replaced with underscores.')
    if cleaned.strip(' .') == '':
        cleaned = _PLACEHOLDER
    return cleaned[:MAX_NAME_CHARS], cleaned


def extension(basename):
    """Lower-case extension; trailing dots and spaces are ignored as on Windows."""
    return posixpath.splitext(basename.rstrip(' .'))[1].lower()


def envelope(fmt, status, name, size, sha256, facts, warnings):
    return {
        'schema_version': SCHEMA_VERSION,
        'format': fmt,
        'status': status,
        'source': {'name': name, 'size_bytes': size, 'sha256': sha256},
        'facts': facts,
        'warnings': warnings.as_list(),
    }
