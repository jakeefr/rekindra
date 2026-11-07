"""Synthetic intake results modelled on docs/intake output. No real files."""
import hashlib
import json

HASH_A = hashlib.sha256(b'synthetic-a').hexdigest()
HASH_B = hashlib.sha256(b'synthetic-b').hexdigest()


def envelope(fmt='text', status='ok', facts=None, sha=HASH_A, size=10, name='a.txt', warnings=None):
    return {'schema_version': 1, 'format': fmt, 'status': status,
            'source': {'name': name, 'size_bytes': size, 'sha256': sha},
            'facts': {} if facts is None else facts, 'warnings': [] if warnings is None else warnings}


def text_facts(excerpt='', **extra):
    return {'excerpt': excerpt, 'excerpt_truncated': False, 'headings': [], 'untrusted_content': True, **extra}


def record(source_id='s1', path='notes/a.txt', intake=None):
    return {'source_id': source_id, 'relative_path': path, 'intake': envelope(facts=text_facts('x')) if intake is None else intake}


def text_record(source_id, excerpt, path=None, sha=None, size=None, fmt='text', **facts):
    digest = hashlib.sha256(source_id.encode()).hexdigest() if sha is None else sha
    return record(source_id, path or f'notes/{source_id}.txt',
                  envelope(fmt, facts=text_facts(excerpt, **facts), sha=digest, size=len(excerpt) if size is None else size))


def zip_entry(name, **overrides):
    entry = {'name': name, 'is_directory': False, 'compressed_size_bytes': 4, 'claimed_uncompressed_size_bytes': 4,
             'encrypted': False, 'safety_warnings': []}
    entry.update(overrides)
    return entry


def zip_record(source_id='zip1', entries=(), status='ok', **facts):
    return record(source_id, f'archive/{source_id}.zip', envelope('zip', status, {
        'entries': list(entries), 'entries_truncated': False, 'payloads_read': False, **facts}, sha=hashlib.sha256(source_id.encode()).hexdigest()))


def resolve(document, pointer):
    """RFC 6901 lookup, used to prove locators really point into the intake."""
    value = document
    for token in pointer.split('/')[1:]:
        token = token.replace('~1', '/').replace('~0', '~')
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def assert_located(case, item, records):
    """Prove an evidence item's locator resolves to its text in the supplied intake."""
    intake = next(entry['intake'] for entry in records if entry['source_id'] == item['source_id'])
    target = resolve(intake, item['locator']['pointer'])
    if 'char_start' in item['locator']:
        case.assertEqual(item['text'], target[item['locator']['char_start']:item['locator']['char_end']])
    elif item['locator'].get('transform') == 'cells_joined':
        case.assertTrue(' | '.join(target).startswith(item['text']))
    else:
        case.assertEqual(item['text'], target)


def assert_matches_retained(case, result, dossier):
    """Prove every search match resolves to one retained evidence item, unchanged."""
    retained = {item['evidence_id']: item for item in dossier['evidence']}
    for match in result['matches']:
        item = retained[match['evidence_id']]
        for key in ('source_id', 'kind', 'provenance', 'locator'):
            case.assertEqual(match[key], item[key])
        case.assertEqual(match['snippet'], item['text'][match['snippet_start']:match['snippet_end']])


def serialized(result):
    return len(json.dumps(result, allow_nan=False))
