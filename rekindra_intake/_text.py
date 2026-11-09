"""Bounded read-only dossier for text, Markdown, JSON and CSV bytes.

Facts are syntactic: nothing here summarizes, interprets or obeys the content.
"""
import csv
import hashlib
import io
import json
import math
import re

from ._common import Warnings, display_name, envelope, extension, require_inputs

MAX_INPUT_BYTES = 256 * 1024
MAX_SOURCE_CHARS = 4000
# Structure is served first so a long excerpt cannot crowd out keys and cells.
MAX_STRUCTURE_CHARS = 2000
MAX_ITEM_CHARS = 80
MAX_ITEMS = 64
MAX_JSON_DEPTH = 20
MAX_CSV_ROWS = 20
MAX_CSV_COLUMNS = 32
_BINARY_CONTROL_RATIO = 10  # more than 1 control character in 10 means binary

_FORMATS = {'': 'text', '.txt': 'text', '.text': 'text', '.log': 'text',
            '.md': 'markdown', '.markdown': 'markdown', '.json': 'json', '.csv': 'csv'}
_SIGNATURES = ((b'\x89PNG\r\n\x1a\n', 'png'), (b'\xff\xd8\xff', 'jpeg'), (b'GIF87a', 'gif'), (b'GIF89a', 'gif'),
               (b'PK\x03\x04', 'zip'), (b'PK\x05\x06', 'zip'), (b'\x1f\x8b', 'gzip'), (b'%PDF-', 'pdf'))
_UTF8_BOM = b'\xef\xbb\xbf'
_UTF16_LE_BOM = b'\xff\xfe'
_UTF16_BE_BOM = b'\xfe\xff'
_UTF32_LE_BOM = b'\xff\xfe\x00\x00'
_UTF32_BE_BOM = b'\x00\x00\xfe\xff'
_END_OF_DATA = {'unexpected end of data', 'truncated data'}

_LINE_END = re.compile(r'\r\n|\r|\n')
_CONTROL = re.compile('[\x00-\x08\x0b\x0e-\x1f\x7f]')
_ATX = re.compile(r' {0,3}(#{1,6})(?:[ \t](.*))?')
_FENCE = re.compile(r' {0,3}(`{3,}|~{3,})(.*)')
# A cell is formula-like when it starts with =, @, tab or carriage return, or when it
# starts with + or - and the whole cell is not a plain number. ASCII digits only.
_FORMULA_PREFIXES = ('=', '@', '\t', '\r')
_SIGN_PREFIXES = ('+', '-')
_PLAIN_NUMBER = re.compile(r'[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?')
_SURROGATE = re.compile('[\ud800-\udfff]')


_STRUCTURE_TRUNCATED = 'Some structural items were omitted or shortened.'


class _Budget:
    def __init__(self, chars):
        self.remaining = chars

    def clip(self, text):
        taken = text[:min(MAX_ITEM_CHARS, self.remaining)]
        self.remaining -= len(taken)
        return taken


class _NonFinite(ValueError):
    pass


def _reject_constant(_name):
    raise _NonFinite


def _checked_float(literal):
    if not math.isfinite(float(literal)):
        raise _NonFinite
    return 0.0


def _signature(data):
    return next((name for magic, name in _SIGNATURES if data.startswith(magic)), None)


def _decode(data):
    """Return (text, encoding, bom length, failure) or None for UTF-32."""
    if data.startswith((_UTF32_LE_BOM, _UTF32_BE_BOM)):
        return None
    if data.startswith(_UTF8_BOM):
        encoding, skip = 'utf-8', 3
    elif data.startswith(_UTF16_LE_BOM):
        encoding, skip = 'utf-16-le', 2
    elif data.startswith(_UTF16_BE_BOM):
        encoding, skip = 'utf-16-be', 2
    else:
        encoding, skip = 'utf-8', 0
    payload = data[skip:]
    try:
        return payload.decode(encoding), encoding, skip, None
    except UnicodeDecodeError as exc:
        code = 'encoding_truncated' if exc.reason in _END_OF_DATA else 'encoding_invalid'
        return payload[:exc.start].decode(encoding), encoding, skip, (code, exc.start, len(payload) - exc.start)


def _measure(text):
    """Return (lines, blank lines, longest line) using only CR, LF and CRLF."""
    lines = _LINE_END.split(text)
    if lines[-1] == '':
        lines.pop()
    return lines, sum(1 for line in lines if not line.strip()), max(map(len, lines), default=0)


def _analyze_headings(lines, budget, warnings):
    headings, count, blocks = [], 0, 0
    fence = None
    for number, line in enumerate(lines, 1):
        marker = _FENCE.fullmatch(line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            continue
        if marker and not (marker[1][0] == '`' and '`' in marker[2]):
            fence, blocks = marker[1], blocks + 1
            continue
        match = _ATX.fullmatch(line)
        if not match:
            continue
        count += 1
        if len(headings) < MAX_ITEMS and budget.remaining:
            text = (match[2] or '').strip()
            without_closing = text.rstrip('#')
            if not without_closing or without_closing[-1] in ' \t':
                text = without_closing.rstrip()
            clipped = budget.clip(text)
            if len(clipped) < len(text):
                warnings.add('structure_truncated', _STRUCTURE_TRUNCATED)
            headings.append({'level': len(match[1]), 'line': number, 'text': clipped})
    if fence:
        warnings.add('markdown_unclosed_fence', 'A fenced code block is never closed; it was treated as running to the end.')
    if count > len(headings):
        warnings.add('structure_truncated', _STRUCTURE_TRUNCATED)
    return {'headings': headings, 'heading_count': count, 'headings_truncated': count > len(headings),
            'fenced_code_block_count': blocks}


def _json_depth(text):
    """Linear bracket scan. Returns the deepest level seen, stopping past the limit."""
    depth = deepest = 0
    in_string = escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in '[{':
            depth += 1
            deepest = max(deepest, depth)
            if depth > MAX_JSON_DEPTH:
                return deepest
        elif char in ']}':
            depth = max(depth - 1, 0)
    return deepest


def _json_type(value):
    if isinstance(value, dict):
        return 'object'
    if isinstance(value, list):
        return 'array'
    if isinstance(value, str):
        return 'string'
    if isinstance(value, bool):
        return 'boolean'
    return 'null' if value is None else 'number'


def _analyze_json(text, decoded_fully, budget, warnings):
    """Return (status, facts). Numbers are discarded unparsed: they are never reported."""
    if not decoded_fully:
        warnings.add('json_not_parsed', 'The bytes did not fully decode, so JSON validity is unknown.')
        return 'partial', {'valid': None, 'root_type': None}
    deepest = _json_depth(text)
    if deepest > MAX_JSON_DEPTH:
        warnings.add('json_depth_exceeded', f'Nesting exceeds {MAX_JSON_DEPTH} levels, so the document was not parsed.')
        # Only the first non-whitespace character is known; anything else is not a container root.
        root = {'{': 'object', '[': 'array'}.get(text.lstrip()[:1])
        return 'partial', {'valid': None, 'root_type': root, 'depth_limit': MAX_JSON_DEPTH}
    duplicates = 0

    def pairs(items):
        nonlocal duplicates
        result = dict(items)
        duplicates += len(items) - len(result)
        return result

    try:
        value = json.loads(text, parse_constant=_reject_constant, parse_float=_checked_float,
                           parse_int=lambda _literal: 0, object_pairs_hook=pairs)
    except _NonFinite:
        warnings.add('json_non_finite_number', 'NaN, Infinity or an out-of-range number is not valid finite JSON.')
        return 'rejected', {'valid': False, 'root_type': None}
    except json.JSONDecodeError as exc:
        warnings.add('json_malformed', 'The document is not valid JSON.')
        return 'partial', {'valid': False, 'root_type': None, 'error': {'line': exc.lineno, 'column': exc.colno}}
    facts = {'valid': True, 'root_type': _json_type(value), 'max_depth': deepest}
    if isinstance(value, list):
        facts['array_length'] = len(value)
    elif isinstance(value, dict):
        keys = []
        for key in value:
            if len(keys) == MAX_ITEMS or not budget.remaining:
                break
            if _SURROGATE.search(key):
                warnings.add('json_lone_surrogate', 'A key escapes an unpaired surrogate; it is shown with U+FFFD.')
                key = _SURROGATE.sub('�', key)
            clipped = budget.clip(key)
            if len(clipped) < len(key):
                warnings.add('structure_truncated', _STRUCTURE_TRUNCATED)
            keys.append(clipped)
        facts['top_level_keys'] = keys
        facts['top_level_key_count'] = len(value)
        facts['top_level_keys_truncated'] = len(value) > len(keys)
        if len(value) > len(keys):
            warnings.add('structure_truncated', _STRUCTURE_TRUNCATED)
    if duplicates:
        facts['duplicate_key_count'] = duplicates
        warnings.add('json_duplicate_keys', 'An object repeats a key; readers may keep different values.')
    return 'ok', facts


def _formula_like(cell):
    """True for a cell starting with =, @, tab or carriage return, or with + or - unless
    the whole cell is a plain number: optional sign, ASCII digits, optional decimal part
    of one or more digits, optional exponent."""
    if cell.startswith(_FORMULA_PREFIXES):
        return True
    return cell.startswith(_SIGN_PREFIXES) and _PLAIN_NUMBER.fullmatch(cell) is None


def _analyze_csv(text, budget, warnings):
    """Comma-delimited, double-quoted rows. No header is inferred; no cell is evaluated.

    formula_like_cell_count counts every cell for which _formula_like is true.
    """
    reader = csv.reader(io.StringIO(text, newline=''), strict=True)
    preview, columns_cut, cells_cut = [], False, False
    rows = blank = formulas = 0
    widest, narrowest = 0, None
    failure = None
    try:
        for row in reader:
            if not row:
                blank += 1
                continue
            rows += 1
            widest = max(widest, len(row))
            narrowest = len(row) if narrowest is None else min(narrowest, len(row))
            formulas += sum(1 for cell in row if _formula_like(cell))
            if len(preview) < MAX_CSV_ROWS and budget.remaining:
                cells = []
                for cell in row[:MAX_CSV_COLUMNS]:
                    if not budget.remaining:
                        break
                    clipped = budget.clip(cell)
                    cells_cut = cells_cut or len(clipped) < len(cell)
                    cells.append(clipped)
                columns_cut = columns_cut or len(cells) < len(row)
                preview.append(cells)
    except csv.Error as exc:
        failure = 'csv_field_too_large' if 'field larger' in str(exc) else 'csv_malformed'
        warnings.add(failure, 'CSV parsing stopped at this row; later rows were not read.')
    facts = {'row_count': rows, 'column_count': widest, 'min_column_count': narrowest or 0,
             'blank_row_count': blank, 'first_row': preview[0] if preview else None, 'next_rows': preview[1:],
             'preview_rows_truncated': rows > len(preview), 'preview_columns_truncated': columns_cut,
             'preview_cells_truncated': cells_cut, 'formula_like_cell_count': formulas}
    if failure:
        facts['error_line'] = reader.line_num
    if rows > len(preview) or columns_cut or cells_cut:
        warnings.add('structure_truncated', _STRUCTURE_TRUNCATED)
    if formulas:
        warnings.add('csv_formula_like_cells', 'Some cells look like spreadsheet formulas. They are inert text here.')
    if widest != (narrowest or 0):
        warnings.add('csv_inconsistent_width', 'Rows have different numbers of columns.')
    return ('partial' if failure else 'ok'), facts


def inspect_text(data: bytes, filename: str) -> dict:
    """Describe text-like bytes. Raises TypeError only for wrong argument types."""
    require_inputs(data, filename)
    warnings = Warnings()
    name, basename = display_name(filename, warnings)
    size = len(data)
    claimed = _FORMATS.get(extension(basename))

    def result(fmt, status, sha256, facts):
        return envelope(fmt, status, name, size, sha256, facts, warnings)

    if size > MAX_INPUT_BYTES:
        warnings.add('input_too_large', f'Input exceeds the {MAX_INPUT_BYTES} byte text budget and was not read.')
        return result('unknown', 'rejected', None, {'claimed_format': claimed, 'limit_bytes': MAX_INPUT_BYTES})
    digest = hashlib.sha256(data).hexdigest()
    if claimed is None:
        warnings.add('unsupported_extension', 'This file extension is not handled by the text inspector.')
        return result('unknown', 'unsupported', digest, {'extension': extension(basename)[:32]})

    def refuse(code, message):
        warnings.add(code, message)
        return result('unknown', 'rejected', digest, {'claimed_format': claimed, 'detected_signature': _signature(data)})

    decoded = _decode(data)
    if decoded is None:
        warnings.add('utf32_unsupported', 'UTF-32 byte-order marks are recognized but not decoded.')
        return result('unknown', 'unsupported', digest, {'claimed_format': claimed})
    text, encoding, bom_length, failure = decoded
    binary_message = 'The bytes look binary, so no text was produced.'
    if encoding == 'utf-8' and b'\x00' in data:
        return refuse('binary_content', binary_message)
    if failure and not text:
        return refuse(failure[0], 'No text could be decoded from the start of this input.')
    if '\x00' in text:
        return refuse('binary_content', binary_message)
    controls = len(_CONTROL.findall(text))
    if controls * _BINARY_CONTROL_RATIO > len(text):
        return refuse('binary_content', binary_message)

    lines, blank, longest = _measure(text)
    budget = _Budget(MAX_STRUCTURE_CHARS)
    status = 'ok'
    if claimed in ('text', 'markdown'):
        structure = _analyze_headings(lines, budget, warnings)
    elif claimed == 'json':
        status, structure = _analyze_json(text, failure is None, budget, warnings)
    else:
        status, structure = _analyze_csv(text, budget, warnings)

    excerpt_limit = MAX_SOURCE_CHARS - (MAX_STRUCTURE_CHARS - budget.remaining)
    truncated = len(text) > excerpt_limit
    facts = {'encoding': encoding, 'bom': bom_length > 0, 'line_count': len(lines), 'blank_line_count': blank,
             'char_count': len(text), 'word_count': len(text.split()), 'longest_line_chars': longest,
             'control_character_count': controls, 'untrusted_content': True}
    if failure:
        code, decoded_bytes, undecoded_bytes = failure
        warnings.add(code, 'Decoding stopped at the first invalid byte; only the valid prefix is described.')
        facts.update(decoded_bytes=decoded_bytes, undecoded_bytes=undecoded_bytes,
                     first_invalid_offset=bom_length + decoded_bytes)
        status = 'rejected' if status == 'rejected' else 'partial'
    if controls:
        warnings.add('control_characters', 'The text contains control characters, kept as source data.')
    if longest > MAX_SOURCE_CHARS:
        warnings.add('long_line', f'At least one line is longer than {MAX_SOURCE_CHARS} characters.')
    if truncated:
        warnings.add('excerpt_truncated', 'Only the beginning of the text is included in the excerpt.')
    facts.update(structure)
    facts.update(excerpt=text[:excerpt_limit], excerpt_truncated=truncated)
    return result(claimed, status, digest, facts)
