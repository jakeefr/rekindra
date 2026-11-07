"""Input checks that run before any recursive or expensive processing."""
from json.encoder import encode_basestring
import math
import re

from ._limits import MAX_DEPTH, MAX_INPUT_BYTES, MAX_PATH_CHARS, MAX_SOURCE_ID_CHARS

FORMATS = ('text', 'markdown', 'json', 'csv', 'zip', 'unknown')
STATUSES = ('ok', 'partial', 'unsupported', 'rejected')
RECORD_KEYS = {'source_id', 'relative_path', 'intake'}
INTAKE_KEYS = {'schema_version', 'format', 'status', 'source', 'facts', 'warnings'}

_MAX_INT_BITS = 4096
_SOURCE_ID = re.compile(r'[A-Za-z0-9._:-]+')
_WARNING_CODE = re.compile(r'[a-z0-9_]{1,64}')
_CONTROL = re.compile('[\x00-\x1f\x7f-\x9f  ]')
_SEPARATOR = re.compile(r'[\\/]')
_DRIVE = re.compile(r'[A-Za-z]:')
_END = object()


class InputRefused(Exception):
    def __init__(self, code, message):
        super().__init__(code)
        self.code = code
        self.message = message


class _Meter:
    """Exact canonical JSON size, computed without building the serialization."""

    def __init__(self):
        self.size = 0

    def add(self, count):
        self.size += count
        if self.size > MAX_INPUT_BYTES:
            raise InputRefused('input_too_large', 'Canonical input exceeds 1 MiB.')

    def text(self, value):
        if len(value) > MAX_INPUT_BYTES:
            raise InputRefused('input_too_large', 'Canonical input exceeds 1 MiB.')
        try:
            self.add(len(encode_basestring(value).encode('utf-8')))
        except UnicodeEncodeError:
            raise InputRefused('invalid_json_value', 'A string is not valid Unicode text.') from None

    def scalar(self, value):
        kind = type(value)
        if kind is str:
            self.text(value)
        elif value is None or kind is bool:
            self.add(5 if value is False else 4)
        elif kind is int:
            if value.bit_length() > _MAX_INT_BITS:
                raise InputRefused('invalid_json_value', 'An integer is too large.')
            self.add(len(repr(value)))
        elif kind is float and math.isfinite(value):
            self.add(len(repr(value)))
        else:
            raise InputRefused('invalid_json_value', 'A value is not JSON-compatible.')

    def children(self, container):
        count = len(container)
        self.add(2 + max(count - 1, 0))
        if type(container) is dict:
            self.add(count)
            for key, value in container.items():
                if type(key) is not str:
                    raise InputRefused('invalid_json_value', 'An object key is not a string.')
                self.text(key)
                yield from self._visit(value)
        else:
            for value in container:
                yield from self._visit(value)

    def _visit(self, value):
        if type(value) in (dict, list):
            yield value
        else:
            self.scalar(value)


def canonical_size(records):
    """Walk iteratively. Shared references and cycles stop at the size or depth limit."""
    meter = _Meter()
    stack = [meter.children(records)]
    while stack:
        child = next(stack[-1], _END)
        if child is _END:
            stack.pop()
        elif len(stack) == MAX_DEPTH:
            raise InputRefused('input_too_deep', 'Nesting exceeds 32 levels.')
        else:
            stack.append(meter.children(child))
    return meter.size


def valid_source_id(value):
    return type(value) is str and 0 < len(value) <= MAX_SOURCE_ID_CHARS and _SOURCE_ID.fullmatch(value) is not None


def valid_relative_path(value):
    if type(value) is not str or not 0 < len(value) <= MAX_PATH_CHARS:
        return False
    if _CONTROL.search(value) or value[0] in '/\\' or _DRIVE.match(value):
        return False
    return not any(len(part) >= 2 and not part.strip('. ') for part in _SEPARATOR.split(value))


def _valid_warning(item):
    return (type(item) is dict and set(item) == {'code', 'message'} and type(item['code']) is str
            and _WARNING_CODE.fullmatch(item['code']) is not None and type(item['message']) is str)


def valid_intake(intake):
    return (type(intake) is dict and INTAKE_KEYS <= set(intake)
            and type(intake['schema_version']) is int and intake['schema_version'] == 1
            and type(intake['format']) is str and intake['format'] in FORMATS
            and type(intake['status']) is str and intake['status'] in STATUSES
            and type(intake['source']) is dict and type(intake['facts']) is dict
            and type(intake['warnings']) is list and all(_valid_warning(item) for item in intake['warnings']))
