"""Read supported text members of a ZIP, in memory only, under hard caps.

``rekindra_intake.inspect_archive`` lists a ZIP without reading any member. This
module runs after it: it refuses bomb-shaped archives from the claimed sizes, then
reads the plain-text members with bounded reads and hands each one to
``inspect_text``. Nothing is ever written to disk and nothing inside the ZIP runs.
"""
import io
import lzma
import re
import time
import zipfile
import zlib

MAX_TEXT_MEMBERS = 32
MAX_MEMBER_BYTES = 256 * 1024      # inspect_text's own input budget
MAX_TOTAL_CLAIMED_BYTES = 64 * 1024 * 1024
MAX_RATIO = 100
RATIO_FLOOR_BYTES = 64 * 1024      # small members may compress well without being suspicious
MAX_NAME_CHARS = 200
TIME_BUDGET_SECONDS = 5.0
_CHUNK_BYTES = 64 * 1024
_REPORT_SKIPS = 32

_TEXT_SUFFIXES = ('.txt', '.text', '.log', '.md', '.markdown', '.json', '.csv')
_NESTED_SUFFIXES = ('.zip', '.jar', '.war', '.apk', '.7z', '.rar', '.tar', '.gz', '.tgz', '.bz2', '.xz',
                    '.cab', '.iso')
_METHODS = (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
_DECODE_ERRORS = (zipfile.BadZipFile, zlib.error, lzma.LZMAError, EOFError, NotImplementedError,
                  RuntimeError, OSError, ValueError)
_TOLERATED = {'encrypted', 'nested_archive_not_inspected'}
_FAILED = ('encrypted_member', 'corrupt_member', 'text_intake_rejected')
_MEMBER_ID = re.compile(r'm\d{4}')

_REASONS = {
    'nested_archive_not_read': 'Nested archive; archives inside archives are not opened.',
    'encrypted_member': 'Encrypted member; no password is available, so its contents are unknown.',
    'unsafe_member': 'The name or layout of this member is unsafe, so it was not read.',
    'unsupported_member_type': 'Not a supported text member (txt, md, json, csv, log).',
    'unsupported_compression': 'Compression method other than stored or deflate.',
    'member_limit': f'More than {MAX_TEXT_MEMBERS} text members; the rest were not read.',
    'member_too_large': f'Larger than the {MAX_MEMBER_BYTES}-byte member limit.',
    'corrupt_member': 'The member failed to decompress or failed its checksum.',
    'text_intake_rejected': 'The member was read but is not usable text.',
    'time_budget_exhausted': 'The read time budget ran out before this member.',
}


class _TooLarge(Exception):
    pass


class _OutOfTime(Exception):
    pass


def _bomb_reason(entries: list, facts: dict) -> str | None:
    claimed_total = 0
    for entry in entries:
        claimed = entry.get('claimed_uncompressed_size_bytes') or 0
        compressed = entry.get('compressed_size_bytes') or 0
        claimed_total += claimed
        if claimed >= RATIO_FLOOR_BYTES and claimed > MAX_RATIO * max(compressed, 1):
            return f'A member expands more than {MAX_RATIO}:1, so the archive was not opened.'
        if 'overlapping_entries' in (entry.get('safety_warnings') or []):
            return 'Members overlap each other, a zip-bomb construction, so the archive was not opened.'
    if max(claimed_total, facts.get('total_claimed_uncompressed_bytes') or 0) > MAX_TOTAL_CLAIMED_BYTES:
        return f'Members claim more than {MAX_TOTAL_CLAIMED_BYTES} bytes in total, so the archive was not opened.'
    return None


def _refuse(envelope: dict, code: str, reason: str, skipped: list) -> dict:
    report = {'read': 0, 'skipped': skipped[:_REPORT_SKIPS], 'skipped_omitted': max(0, len(skipped) - _REPORT_SKIPS),
              'refused': {'code': code, 'reason': reason}}
    return dict(envelope, status='rejected', warnings=list(envelope.get('warnings') or [])
                + [{'code': code, 'message': reason}], text_members=[], text_member_report=report)


def _bounded_read(archive, info, deadline: float, clock) -> bytes:
    chunks, total = [], 0
    with archive.open(info) as member:
        while True:
            if clock() > deadline:
                raise _OutOfTime
            chunk = member.read(_CHUNK_BYTES)
            if not chunk:
                return b''.join(chunks)
            total += len(chunk)
            if total > MAX_MEMBER_BYTES:
                raise _TooLarge
            chunks.append(chunk)


def _precheck(entry: dict, info) -> str | None:
    """The skip code decided from metadata alone, or None when the member may be read."""
    name = entry.get('name') or ''
    lowered = name.lower()
    warnings = set(entry.get('safety_warnings') or [])
    if 'nested_archive_not_inspected' in warnings or lowered.endswith(_NESTED_SUFFIXES):
        return 'nested_archive_not_read'
    if entry.get('encrypted') or info.flag_bits & 1:
        return 'encrypted_member'
    if (warnings - _TOLERATED or entry.get('name_truncated') or len(name) > MAX_NAME_CHARS
            or info.filename != name):
        return 'unsafe_member'
    if not lowered.endswith(_TEXT_SUFFIXES):
        return 'unsupported_member_type'
    if info.compress_type not in _METHODS:
        return 'unsupported_compression'
    if (entry.get('claimed_uncompressed_size_bytes') or 0) > MAX_MEMBER_BYTES:
        return 'member_too_large'
    return None


def read_archive_text(envelope: dict, data: bytes, inspect_text, clock=time.monotonic) -> dict:
    """Return the ``inspect_archive`` envelope plus ``text_members`` and a read report."""
    if envelope.get('format') != 'zip' or envelope.get('status') in ('rejected', 'unsupported'):
        return envelope
    facts = envelope.get('facts') or {}
    entries = facts.get('entries') or []
    bomb = _bomb_reason(entries, facts)
    if bomb:
        return _refuse(envelope, 'zip_bomb_guard', bomb, [])
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except _DECODE_ERRORS:
        return _refuse(envelope, 'corrupt_archive', 'The archive directory could not be read.', [])

    members, skipped, attempted = [], [], 0
    deadline = clock() + TIME_BUDGET_SECONDS
    with archive:
        for index, (entry, info) in enumerate(zip(entries, archive.infolist()), 1):
            if entry.get('is_directory'):
                continue
            name = str(entry.get('name') or '')
            code = _precheck(entry, info)
            is_text = name.lower().endswith(_TEXT_SUFFIXES)
            attempted += is_text
            if code is None and len(members) >= MAX_TEXT_MEMBERS:
                code = 'member_limit'
            if code is None and clock() > deadline:
                code = 'time_budget_exhausted'
            if code is None:
                try:
                    raw = _bounded_read(archive, info, deadline, clock)
                except _TooLarge:
                    code = 'member_too_large'
                except _OutOfTime:
                    code = 'time_budget_exhausted'
                except _DECODE_ERRORS:
                    code = 'corrupt_member'
            if code is None:
                intake = inspect_text(raw, name.rsplit('/', 1)[-1])
                if intake.get('status') in ('ok', 'partial'):
                    members.append({'member_id': f'm{index:04d}', 'name': name, 'intake': intake})
                    continue
                code = 'text_intake_rejected'
            skipped.append({'name': name[:MAX_NAME_CHARS], 'code': code, 'reason': _REASONS[code],
                            'text_candidate': is_text})

    unread = [s for s in skipped if s.pop('text_candidate')]
    # Candidates are skipped entries that named a text type; every reader failure is one of them.
    failed = [s for s in unread if s['code'] in _FAILED]
    if attempted and not members and len(failed) == attempted:
        codes = {s['code'] for s in failed}
        code, reason = ('encrypted_archive', 'Every text member is encrypted, so none could be read.') \
            if codes == {'encrypted_member'} else \
            ('corrupt_archive', 'Every text member is corrupt or unusable, so none could be read.')
        return _refuse(envelope, code, reason, skipped)

    warnings = list(envelope.get('warnings') or [])
    status = envelope.get('status')
    if unread:
        status = 'partial'
        warnings.append({'code': 'text_members_skipped',
                         'message': f'{len(unread)} text member(s) could not be read; see text_member_report.'})
    if skipped and len(skipped) > len(unread):
        warnings.append({'code': 'other_members_not_read',
                         'message': f'{len(skipped) - len(unread)} non-text member(s) were not read.'})
    report = {'read': len(members), 'skipped': skipped[:_REPORT_SKIPS],
              'skipped_omitted': max(0, len(skipped) - _REPORT_SKIPS)}
    return dict(envelope, status=status, warnings=warnings, text_members=members, text_member_report=report)


def member_records(source_id: str, relative_path: str, intake: dict) -> tuple[dict, list]:
    """Split a stored envelope into the plain ZIP intake and one record per text member.

    Members are separate dossier sources, so the ZIP's inventory stays exactly what
    ``build_dossier`` expects and each member carries its own provenance path.
    """
    if not isinstance(intake, dict) or 'text_members' not in intake:
        return intake, []
    members = intake['text_members']
    parent = {k: v for k, v in intake.items() if k not in ('text_members', 'text_member_report')}
    if not isinstance(members, list):
        raise ValueError('text_members is malformed')
    records = []
    for member in members:
        if (not isinstance(member, dict) or set(member) != {'member_id', 'name', 'intake'}
                or not isinstance(member['member_id'], str) or not _MEMBER_ID.fullmatch(member['member_id'])
                or not isinstance(member['name'], str)):
            raise ValueError('text_members is malformed')
        path = f"{relative_path}!{member['name']}"
        if len(path) <= 512:  # the dossier's path limit; one over-long name must not refuse the rest
            records.append({'source_id': f"{source_id}:{member['member_id']}", 'relative_path': path,
                            'intake': member['intake']})
    return parent, records


def mark_member_coverage(dossier: dict) -> dict:
    """A ZIP whose text members became sources did have member contents inspected."""
    if not isinstance(dossier, dict):
        return dossier
    rows = dossier.get('sources') or []
    parents = {row.get('source_id', '').rsplit(':', 1)[0] for row in rows
               if isinstance(row, dict) and ':' in row.get('source_id', '')}
    for row in rows:
        if isinstance(row, dict) and row.get('source_id') in parents and isinstance(row.get('coverage'), dict):
            row['coverage']['member_contents_inspected'] = True
    return dossier
