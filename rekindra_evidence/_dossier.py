"""Collection dossier built from intake results.

Everything retained is copied from the supplied results. Nothing here reads a
file, interprets content or claims more than identical bytes for duplicates.
"""
from collections import deque
import hashlib
import json
import re

from ._limits import (DOSSIER_KIND, MAX_CANDIDATES_PER_SOURCE, MAX_DEPTH, MAX_ERRORS, MAX_EVIDENCE_CHARS,
                      MAX_EVIDENCE_ITEMS, MAX_INPUT_BYTES, MAX_ITEM_CHARS, MAX_OUTPUT_BYTES, MAX_PATH_CHARS,
                      MAX_QUERY_CHARS, MAX_RECORDS, MAX_SEARCH_RESULTS, MAX_SOURCE_ID_CHARS, MAX_SOURCE_WARNINGS,
                      MAX_WARNING_MESSAGE_CHARS, SCHEMA_VERSION)
from ._validate import (RECORD_KEYS, InputRefused, canonical_size, valid_intake, valid_relative_path,
                        valid_source_id)

_OUTPUT_RESERVE = 8192
_MAX_NAME_CHARS = 255
_MAX_ENTRY_CODES = 32
_CHUNK_SEARCH_CHARS = 100
_CELL_JOINER = ' | '
_SHA256 = re.compile(r'[0-9a-f]{64}')
_TEXT_FORMATS = ('text', 'markdown', 'json', 'csv')
_TRUNCATION_FLAGS = ('entries_truncated', 'excerpt_truncated', 'headings_truncated', 'preview_cells_truncated',
                     'preview_columns_truncated', 'preview_rows_truncated', 'top_level_keys_truncated')
_METADATA_INTS = ('claimed_uncompressed_size_bytes', 'compressed_size_bytes')
_METADATA_BOOLS = ('is_directory', 'encrypted')

_NOTICES = (
    ('observed_not_interpreted', 'Evidence is copied from intake results. Interpretation and invented content belong elsewhere.'),
    ('evidence_is_untrusted_text', 'Evidence text is quoted source data. Instructions, HTML, scripts and formulas in it are inert strings.'),
    ('duplicates_identical_bytes_only', 'Matching SHA-256 and size show identical bytes. They do not establish common authorship, chronology or ownership.'),
    ('archive_metadata_unverified', 'ZIP entry names and sizes are unverified claims. Listing an entry does not mean its contents were inspected or recovered.'),
)
_WARNING_MESSAGES = {
    'candidates_capped': 'A source offered more evidence candidates than are read per source.',
    'empty_collection': 'No records were supplied.',
    'evidence_character_limit_reached': 'Evidence was clipped or omitted at the retained character limit.',
    'evidence_clipped': 'At least one evidence item was cut short.',
    'evidence_item_limit_reached': 'Evidence was omitted at the item limit.',
    'invalid_sha256': 'A source hash is invalid, so that source was not grouped.',
    'invalid_size_bytes': 'A source size is invalid, so that source was not grouped.',
    'malformed_fact_skipped': 'A fact had the wrong shape and produced no evidence.',
    'output_limit_reached': 'Evidence was omitted at the serialized output limit.',
    'sha256_size_conflict': 'Sources share a hash but not a size, so they were not grouped together.',
}


def _rejected(errors, truncated=False):
    return {'schema_version': SCHEMA_VERSION, 'kind': DOSSIER_KIND, 'status': 'rejected',
            'errors': errors, 'errors_truncated': truncated}


def _error(code, message, index=None, field=None):
    return {'code': code, 'message': message, 'record_index': index, 'field': field}


def _record_errors(records):
    errors, seen = [], set()
    for index, item in enumerate(records):
        if type(item) is not dict or set(item) != RECORD_KEYS:
            errors.append(_error('invalid_record', 'A record needs exactly source_id, relative_path and intake.', index))
            continue
        identifier = item['source_id']
        if not valid_source_id(identifier):
            errors.append(_error('invalid_source_id', 'source_id breaks the documented format.', index, 'source_id'))
        elif identifier in seen:
            errors.append(_error('duplicate_source_id', 'source_id repeats an earlier record.', index, 'source_id'))
        else:
            seen.add(identifier)
        if not valid_relative_path(item['relative_path']):
            errors.append(_error('invalid_relative_path', 'relative_path is not a safe relative path.', index, 'relative_path'))
        if not valid_intake(item['intake']):
            errors.append(_error('invalid_intake', 'intake is not a valid intake envelope.', index, 'intake'))
    return errors


def _natural_int(value):
    return value if type(value) is int and value >= 0 else None


def _chunks(text, size):
    """Yield (start, end) slices of at most size, cutting after whitespace if possible."""
    start = 0
    while start < len(text):
        end = start + size
        if end < len(text):
            for cut in range(end, end - _CHUNK_SEARCH_CHARS, -1):
                if text[cut - 1].isspace():
                    end = cut
                    break
        end = min(end, len(text))
        yield start, end
        start = end


def _direct(kind, provenance, pointer, text, **extra):
    return {'kind': kind, 'provenance': provenance, 'locator': {'pointer': pointer}, 'text': text, 'sliceable': True, **extra}


def _joined(pointer, kind, cells):
    return {'kind': kind, 'provenance': 'observed_structure', 'locator': {'pointer': pointer, 'transform': 'cells_joined'},
            'text': _CELL_JOINER.join(cells), 'sliceable': False}


class _Reader:
    """Pull candidates from known fact shapes, never trusting that they are well formed."""

    def __init__(self, facts):
        self.facts = facts
        self.malformed = False
        self.capped = False

    def listed(self, key):
        value = self.facts.get(key)
        if value is None:
            return []
        if type(value) is not list:
            self.malformed = True
            return []
        if len(value) > MAX_CANDIDATES_PER_SOURCE:
            self.capped = True
        return value[:MAX_CANDIDATES_PER_SOURCE]

    def strings(self, key):
        """A list of strings, or nothing: a partly valid row would misquote the source."""
        values = self.listed(key)
        if all(type(value) is str for value in values):
            return values
        self.malformed = True
        return []

    def excerpt(self, size):
        value = self.facts.get('excerpt')
        if value is None:
            return []
        if type(value) is not str:
            self.malformed = True
            return []
        spans = []
        for span in _chunks(value, size):
            if len(spans) == MAX_CANDIDATES_PER_SOURCE:
                self.capped = True
                break
            spans.append(span)
        return [{'kind': 'excerpt', 'provenance': 'observed_source_text', 'text': value[start:end],
                 'locator': {'pointer': '/facts/excerpt', 'char_start': start, 'char_end': end}, 'sliceable': False}
                for start, end in spans]

    def headings(self):
        found = []
        for index, heading in enumerate(self.listed('headings')):
            if type(heading) is not dict or type(heading.get('text')) is not str:
                self.malformed = True
                continue
            if not heading['text']:
                continue
            extra = {}
            if _natural_int(heading.get('line')) is not None:
                extra['source_line'] = heading['line']
            if _natural_int(heading.get('level')) is not None:
                extra['heading_level'] = heading['level']
            found.append(_direct('heading', 'observed_structure', f'/facts/headings/{index}/text', heading['text'], **extra))
        return found

    def keys(self):
        keys = self.strings('top_level_keys')
        return [_joined('/facts/top_level_keys', 'json_keys', keys)] if keys else []

    def rows(self):
        found = []
        first = self.strings('first_row')
        if first:
            found.append(_joined('/facts/first_row', 'csv_row', first))
        for index, row in enumerate(self.listed('next_rows')):
            if type(row) is list and all(type(cell) is str for cell in row):
                if row:
                    found.append(_joined(f'/facts/next_rows/{index}', 'csv_row', row[:MAX_CANDIDATES_PER_SOURCE]))
            else:
                self.malformed = True
        return found

    def entries(self):
        found = []
        for index, entry in enumerate(self.listed('entries')):
            if type(entry) is not dict or type(entry.get('name')) is not str:
                self.malformed = True
                continue
            metadata = {key: _natural_int(entry.get(key)) for key in _METADATA_INTS}
            metadata.update({key: entry[key] if type(entry.get(key)) is bool else None for key in _METADATA_BOOLS})
            codes = entry.get('safety_warnings')
            valid = type(codes) is list and len(codes) <= _MAX_ENTRY_CODES and all(type(code) is str for code in codes)
            metadata['safety_warnings'] = list(codes) if valid else None
            found.append(_direct('archive_entry_name', 'unverified_archive_metadata', f'/facts/entries/{index}/name',
                                 entry['name'], archive_metadata=metadata))
        return found


def _candidates(fmt, facts, item_chars):
    """Return (candidates, malformed, capped). The first excerpt chunk comes first."""
    reader = _Reader(facts)
    if fmt == 'zip':
        ordered = reader.entries()
    elif fmt in _TEXT_FORMATS:
        chunks = reader.excerpt(item_chars)
        structure = {'json': reader.keys, 'csv': reader.rows}.get(fmt, reader.headings)()
        ordered = chunks[:1] + structure + chunks[1:]
    else:
        ordered = []
    if len(ordered) > MAX_CANDIDATES_PER_SOURCE:
        reader.capped = True
    return ordered[:MAX_CANDIDATES_PER_SOURCE], reader.malformed, reader.capped


def _plan(item, item_chars=MAX_ITEM_CHARS):
    """Everything about one source that does not depend on other sources."""
    intake = item['intake']
    source, facts = intake['source'], intake['facts']
    digest = source.get('sha256')
    size = _natural_int(source.get('size_bytes'))
    valid_digest = type(digest) is str and _SHA256.fullmatch(digest) is not None
    name = source.get('name')
    candidates, malformed, capped = _candidates(intake['format'], facts, item_chars)
    kept = intake['warnings'][:MAX_SOURCE_WARNINGS]
    return {
        'source_id': item['source_id'], 'relative_path': item['relative_path'],
        'display_name': name[:_MAX_NAME_CHARS] if type(name) is str else None,
        'format': intake['format'], 'status': intake['status'], 'facts': facts,
        'sha256': digest if valid_digest else None, 'size_bytes': size,
        'bad_digest': digest is not None and not valid_digest, 'bad_size': size is None,
        'warnings': [{'code': w['code'], 'message': w['message'][:MAX_WARNING_MESSAGE_CHARS]} for w in kept],
        'warnings_omitted': len(intake['warnings']) - len(kept),
        'candidates': candidates, 'malformed': malformed, 'capped': capped,
    }


def _select(plans, item_chars):
    """Round-robin over sources so that one large source cannot crowd out the rest."""
    queues = [deque(enumerate(plan['candidates'])) for plan in plans]
    selected, omitted = [], {'item_limit': 0, 'character_limit': 0, 'output_limit': 0}
    characters_left = MAX_EVIDENCE_CHARS
    while any(queues):
        for source_index, queue in enumerate(queues):
            if not queue:
                continue
            order, candidate = queue.popleft()
            if len(selected) == MAX_EVIDENCE_ITEMS:
                omitted['item_limit'] += 1
            elif not characters_left:
                omitted['character_limit'] += 1
            else:
                item = _evidence(plans[source_index]['source_id'], candidate, min(item_chars, characters_left))
                characters_left -= len(item['text'])
                selected.append((source_index, order, item))
    return selected, omitted


def _evidence(source_id, candidate, limit):
    text = candidate['text'][:limit]
    clipped = len(text) < len(candidate['text'])
    locator = dict(candidate['locator'])
    if 'char_start' in locator:
        locator['char_end'] = locator['char_start'] + len(text)
    elif clipped and candidate['sliceable']:
        locator.update(char_start=0, char_end=len(text))
    digest = hashlib.sha256(json.dumps([source_id, locator, text], sort_keys=True).encode('utf-8')).hexdigest()
    item = {'evidence_id': f'ev-{digest[:24]}', 'source_id': source_id, 'kind': candidate['kind'],
            'provenance': candidate['provenance'], 'locator': locator, 'text': text, 'clipped': clipped,
            'untrusted_content': True}
    for key in ('source_line', 'heading_level', 'archive_metadata'):
        if key in candidate:
            item[key] = candidate[key]
    return item


def _duplicates(plans):
    groups, sizes_by_digest = {}, {}
    for plan in plans:
        if plan['sha256'] is None or plan['size_bytes'] is None:
            continue
        groups.setdefault((plan['sha256'], plan['size_bytes']), []).append(plan['source_id'])
        sizes_by_digest.setdefault(plan['sha256'], set()).add(plan['size_bytes'])
    built = [{'group_id': f'dup-{digest[:16]}-{size}', 'sha256': digest, 'size_bytes': size,
              'source_ids': sorted(members), 'basis': 'sha256_and_size'}
             for (digest, size), members in groups.items() if len(members) >= 2]
    built.sort(key=lambda group: group['group_id'])
    conflict = any(len(sizes) > 1 for sizes in sizes_by_digest.values())
    return built, conflict


def _row(plan, kept, group_id):
    facts = plan['facts']
    fmt, status = plan['format'], plan['status']
    available = plan['candidates']
    excerpt_available = sum(len(c['text']) for c in available if c['kind'] == 'excerpt')
    excerpt_retained = sum(len(item['text']) for item in kept if item['kind'] == 'excerpt')
    whole_excerpt = type(facts.get('excerpt')) is str and excerpt_retained == excerpt_available == len(facts['excerpt'])
    flags = [flag for flag in _TRUNCATION_FLAGS if facts.get(flag) is True]
    undecoded = _natural_int(facts.get('undecoded_bytes')) or 0
    return {
        'source_id': plan['source_id'], 'relative_path': plan['relative_path'], 'display_name': plan['display_name'],
        'format': fmt, 'inspection_status': status, 'size_bytes': plan['size_bytes'], 'sha256': plan['sha256'],
        'duplicate_group': group_id, 'warnings': [dict(warning) for warning in plan['warnings']],
        'warnings_omitted': plan['warnings_omitted'],
        'coverage': {
            'content_inspected': fmt in _TEXT_FORMATS and status in ('ok', 'partial'),
            'member_contents_inspected': False if fmt == 'zip' else None,
            'intake_truncated': flags, 'undecoded_bytes': undecoded,
            'evidence_available': len(available), 'evidence_retained': len(kept),
            'characters_available': sum(len(c['text']) for c in available),
            'characters_retained': sum(len(item['text']) for item in kept),
            'candidates_capped': plan['capped'],
            'source_text_fully_retained': (fmt in _TEXT_FORMATS and status == 'ok' and whole_excerpt
                                           and facts.get('excerpt_truncated') is not True),
        },
    }


def _limits():
    return {'max_records': MAX_RECORDS, 'max_input_bytes': MAX_INPUT_BYTES, 'max_depth': MAX_DEPTH,
            'max_evidence_items': MAX_EVIDENCE_ITEMS, 'max_item_chars': MAX_ITEM_CHARS,
            'max_evidence_chars': MAX_EVIDENCE_CHARS, 'max_output_bytes': MAX_OUTPUT_BYTES,
            'max_query_chars': MAX_QUERY_CHARS, 'max_search_results': MAX_SEARCH_RESULTS,
            'max_source_id_chars': MAX_SOURCE_ID_CHARS, 'max_path_chars': MAX_PATH_CHARS}


def _tally(values):
    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _assemble(plans, groups, conflict, selected, omitted):
    group_of = {member: group['group_id'] for group in groups for member in group['source_ids']}
    by_source = [[] for _ in plans]
    for source_index, _order, item in sorted(selected, key=lambda entry: entry[:2]):
        by_source[source_index].append(item)
    rows = [_row(plan, kept, group_of.get(plan['source_id'])) for plan, kept in zip(plans, by_source)]
    evidence = [json.loads(json.dumps(item)) for kept in by_source for item in kept]
    clipped = sum(1 for item in evidence if item['clipped'])
    fully = sum(1 for row in rows if row['coverage']['source_text_fully_retained'])
    with_evidence = sum(1 for kept in by_source if kept)
    capped = any(plan['capped'] for plan in plans)
    available = sum(len(plan['candidates']) for plan in plans)
    codes = {
        'candidates_capped': capped, 'empty_collection': not plans, 'evidence_character_limit_reached': False,
        'evidence_clipped': clipped > 0, 'evidence_item_limit_reached': omitted['item_limit'] > 0,
        'invalid_sha256': any(plan['bad_digest'] for plan in plans),
        'invalid_size_bytes': any(plan['bad_size'] for plan in plans),
        'malformed_fact_skipped': any(plan['malformed'] for plan in plans),
        'output_limit_reached': omitted['output_limit'] > 0, 'sha256_size_conflict': conflict,
    }
    total = sum(len(item['text']) for item in evidence)
    codes['evidence_character_limit_reached'] = omitted['character_limit'] > 0 or (clipped > 0 and total == MAX_EVIDENCE_CHARS)
    return {
        'schema_version': SCHEMA_VERSION, 'kind': DOSSIER_KIND,
        'status': 'partial' if capped or clipped or any(omitted.values()) else 'ok',
        'limits': _limits(),
        'counts': {'sources': len(plans), 'by_format': _tally(plan['format'] for plan in plans),
                   'by_status': _tally(plan['status'] for plan in plans)},
        'sources': rows,
        'duplicate_groups': groups,
        'evidence': evidence,
        'coverage': {
            'sources_total': len(plans), 'sources_with_evidence': with_evidence,
            'sources_without_evidence': len(plans) - with_evidence,
            'sources_not_content_inspected': sum(1 for row in rows if not row['coverage']['content_inspected']),
            'sources_text_fully_retained': fully, 'evidence_available': available, 'evidence_retained': len(evidence),
            'evidence_omitted': dict(omitted), 'evidence_items_clipped': clipped,
            'characters_available': sum(row['coverage']['characters_available'] for row in rows),
            'characters_retained': total, 'complete': bool(plans) and fully == len(plans),
        },
        'warnings': [{'code': code, 'message': _WARNING_MESSAGES[code]} for code in sorted(codes) if codes[code]],
        'notices': [{'code': code, 'message': message} for code, message in _NOTICES],
    }


def _size(result):
    return len(json.dumps(result, allow_nan=False))


def build_dossier(records: list[dict]) -> dict:
    """Index intake results. Raises TypeError only when records is not a list."""
    if not isinstance(records, list):
        raise TypeError('records must be a list')
    if len(records) > MAX_RECORDS:
        return _rejected([_error('too_many_records', 'More than 128 records were supplied.')])
    try:
        canonical_size(records)
    except InputRefused as refused:
        return _rejected([_error(refused.code, refused.message)])
    errors = _record_errors(records)
    if errors:
        return _rejected(errors[:MAX_ERRORS], len(errors) > MAX_ERRORS)

    ordered = sorted(records, key=lambda item: item['source_id'])
    plans = [_plan(item) for item in ordered]
    offering = sum(1 for plan in plans if plan['candidates'])
    # A fair share guarantees every source a turn before the character limit runs out.
    item_chars = min(MAX_ITEM_CHARS, MAX_EVIDENCE_CHARS // max(offering, 1))
    if item_chars < MAX_ITEM_CHARS:
        plans = [_plan(item, item_chars) for item in ordered]
    groups, conflict = _duplicates(plans)
    selected, omitted = _select(plans, item_chars)
    empty = _assemble(plans, groups, conflict, [], omitted)
    if _size(empty) + _OUTPUT_RESERVE > MAX_OUTPUT_BYTES:
        return _rejected([_error('output_too_large', 'Source identity data alone exceeds the output limit.')])

    used, kept = _size(empty) + _OUTPUT_RESERVE, []
    for position, entry in enumerate(selected):
        used += len(json.dumps(entry[2])) + 2
        if used > MAX_OUTPUT_BYTES:
            omitted['output_limit'] = len(selected) - position
            break
        kept.append(entry)
    result = _assemble(plans, groups, conflict, kept, omitted)
    while _size(result) > MAX_OUTPUT_BYTES:  # the reserve should make this unreachable
        kept.pop()
        omitted['output_limit'] += 1
        result = _assemble(plans, groups, conflict, kept, omitted)
    return result
