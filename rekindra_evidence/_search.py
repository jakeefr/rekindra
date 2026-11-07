"""Deterministic lexical search over a dossier's retained evidence only."""
import unicodedata

from ._limits import (DOSSIER_KIND, MAX_EVIDENCE_CHARS, MAX_EVIDENCE_ITEMS, MAX_ITEM_CHARS, MAX_QUERY_CHARS, MAX_RECORDS,
                      MAX_SEARCH_RESULTS, MAX_SNIPPET_CHARS, SCHEMA_VERSION, SEARCH_KIND)

_SNIPPET_LEAD_CHARS = 60
_TYPE_ORDER = ('exact_phrase', 'all_terms', 'some_terms')
_RULES = {
    'exact_phrase': 'The whole normalized query occurs in this evidence text.',
    'all_terms': 'Every query term occurs in this evidence text, not necessarily together.',
    'some_terms': 'At least one query term occurs in this evidence text.',
}
_COVERAGE_INTS = ('sources_total', 'sources_not_content_inspected', 'sources_text_fully_retained',
                  'evidence_available', 'evidence_retained')
_NOTICE_MATCH = ('Search covers retained evidence only. Matches are quoted source data, not established facts, '
                 'and other sources may hold more.')
_NOTICE_NO_MATCH = ('Search covers retained evidence only. No match does not show that the query is absent from '
                    'the sources: uninspected, omitted or truncated content was not searched.')


def _refused(code, message):
    return {'schema_version': SCHEMA_VERSION, 'kind': SEARCH_KIND, 'status': 'rejected',
            'errors': [{'code': code, 'message': message}]}


def _fold(text):
    """Return (normalized text, original index of each normalized character)."""
    folded, origins = [], []
    pending_space = None
    for index, char in enumerate(text):
        if char.isspace():
            pending_space = index if pending_space is None else pending_space
            continue
        if pending_space is not None and folded:
            folded.append(' ')
            origins.append(pending_space)
        pending_space = None
        for part in unicodedata.normalize('NFKD', char).casefold():
            folded.append(part)
            origins.append(index)
    return ''.join(folded), origins


def _terms(normalized):
    return list(dict.fromkeys(piece for piece in normalized.split(' ') if piece))


def _valid_item(item, source_ids):
    return (type(item) is dict and type(item.get('text')) is str and len(item['text']) <= MAX_ITEM_CHARS
            and type(item.get('locator')) is dict
            and all(type(item.get(key)) is str for key in ('evidence_id', 'source_id', 'kind', 'provenance'))
            and item['source_id'] in source_ids)


def _usable(dossier):
    """Bounded shape check, so tampered input cannot make a search unbounded."""
    if type(dossier.get('schema_version')) is not int or dossier['schema_version'] != SCHEMA_VERSION:
        return None
    sources, evidence, coverage = dossier.get('sources'), dossier.get('evidence'), dossier.get('coverage')
    if (dossier.get('kind') != DOSSIER_KIND or dossier.get('status') not in ('ok', 'partial')
            or type(sources) is not list or type(evidence) is not list or type(coverage) is not dict
            or len(sources) > MAX_RECORDS or len(evidence) > MAX_EVIDENCE_ITEMS):
        return None
    if not all(type(coverage.get(key)) is int for key in _COVERAGE_INTS):
        return None
    rows = {}
    for row in sources:
        if (type(row) is not dict or type(row.get('source_id')) is not str
                or not all(type(row.get(key)) is str for key in ('relative_path', 'inspection_status'))):
            return None
        rows[row['source_id']] = row
    if not all(_valid_item(item, rows) for item in evidence):
        return None
    if sum(len(item['text']) for item in evidence) > MAX_EVIDENCE_CHARS:
        return None
    return rows


def _examine(text, phrase, terms):
    """Return the match description for one evidence text, or None."""
    folded, origins = _fold(text)
    matched = [term for term in terms if term in folded]
    if not matched:
        return None
    if phrase in folded:
        kind, position = 'exact_phrase', folded.index(phrase)
    else:
        kind = 'all_terms' if len(matched) == len(terms) else 'some_terms'
        position = min(folded.index(term) for term in matched)
    return {'type': kind, 'matched': matched, 'occurrences': sum(folded.count(term) for term in matched),
            'origin': origins[position]}


def _match_entry(rank, found, item, row, query_terms):
    text = item['text']
    start = max(found['origin'] - _SNIPPET_LEAD_CHARS, 0)
    end = min(start + MAX_SNIPPET_CHARS, len(text))
    return {
        'rank': rank, 'evidence_id': item['evidence_id'], 'source_id': item['source_id'],
        'relative_path': row['relative_path'], 'kind': item['kind'], 'provenance': item['provenance'],
        'inspection_status': row['inspection_status'], 'locator': dict(item['locator']),
        'snippet': text[start:end], 'snippet_start': start, 'snippet_end': end,
        'snippet_truncated_start': start > 0, 'snippet_truncated_end': end < len(text),
        'explanation': {'match_type': found['type'], 'matched_terms': found['matched'],
                        'unmatched_terms': [term for term in query_terms if term not in found['matched']],
                        'occurrences': found['occurrences'], 'rule': _RULES[found['type']]},
        'untrusted_content': True,
    }


def search_dossier(dossier: dict, query: str, *, limit: int = 10) -> dict:
    """Search retained evidence. Raises TypeError only for wrong argument types."""
    if not isinstance(dossier, dict):
        raise TypeError('dossier must be a dict')
    if not isinstance(query, str):
        raise TypeError('query must be a str')
    if type(limit) is not int:
        raise TypeError('limit must be an int')
    if not 1 <= limit <= MAX_SEARCH_RESULTS:
        return _refused('limit_out_of_range', 'limit must be from 1 to 20.')
    if len(query) > MAX_QUERY_CHARS:
        return _refused('query_too_long', 'query exceeds 256 characters.')
    try:
        query.encode('utf-8')
    except UnicodeEncodeError:
        return _refused('invalid_query', 'query is not valid Unicode text.')
    phrase = _fold(query)[0]
    if not phrase:
        return _refused('empty_query', 'query has no searchable characters.')
    if dossier.get('status') == 'rejected':
        return _refused('dossier_rejected', 'This dossier was rejected, so it holds no evidence.')
    rows = _usable(dossier)
    if rows is None:
        return _refused('invalid_dossier', 'This object is not a usable evidence dossier.')

    terms = _terms(phrase)
    evidence = dossier['evidence']
    found = []
    for order, item in enumerate(evidence):
        match = _examine(item['text'], phrase, terms)
        if match:
            found.append((_TYPE_ORDER.index(match['type']), -len(match['matched']), -match['occurrences'], order, match))
    found.sort(key=lambda entry: entry[:4])
    chosen = found[:limit]
    matches = [_match_entry(rank, entry[4], evidence[entry[3]], rows[evidence[entry[3]]['source_id']], terms)
               for rank, entry in enumerate(chosen, 1)]
    coverage = dossier['coverage']
    return {
        'schema_version': SCHEMA_VERSION, 'kind': SEARCH_KIND, 'status': 'ok' if found else 'no_match',
        'query': {'text': query, 'normalized': phrase, 'terms': terms},
        'limit': limit, 'total_matches': len(found), 'returned': len(matches), 'results_truncated': len(found) > len(matches),
        'matches': matches,
        'scope': {
            'coverage': 'retained_evidence_only', 'dossier_status': dossier['status'],
            'evidence_items_searched': len(evidence), 'characters_searched': sum(len(item['text']) for item in evidence),
            'evidence_items_not_retained': coverage['evidence_available'] - coverage['evidence_retained'],
            'sources_not_content_inspected': coverage['sources_not_content_inspected'],
            'sources_text_not_fully_retained': coverage['sources_total'] - coverage['sources_text_fully_retained'],
        },
        'notice': _NOTICE_MATCH if found else _NOTICE_NO_MATCH,
    }
