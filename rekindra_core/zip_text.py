"""Read supported text members of a ZIP, in memory only, under hard caps.

``rekindra_intake.inspect_archive`` lists a ZIP without reading any member. This
module runs after it: it refuses bomb-shaped archives from the claimed sizes, then
reads the plain-text members with bounded reads and hands each one to
``inspect_text``. Nothing is ever written to disk and nothing inside the ZIP runs.
"""
import io
import json
import lzma
import re
import time
import zipfile
import zlib

MAX_TEXT_MEMBERS = 32
MAX_MEMBER_BYTES = 256 * 1024      # inspect_text's own input budget
MAX_TOTAL_READ_BYTES = 4 * 1024 * 1024    # what one archive may really decompress
MAX_TOTAL_CLAIMED_BYTES = 1024 * 1024 * 1024
MAX_RATIO = 100
RATIO_FLOOR_BYTES = 64 * 1024      # small members may compress well without being suspicious
BOMB_FLOOR_BYTES = 16 * 1024 * 1024     # over the ratio at this size, the whole archive is refused
MAX_NAME_CHARS = 200
TIME_BUDGET_SECONDS = 5.0
MAX_DOSSIER_SOURCES = 128          # the evidence dossier's record limit
MAX_DOSSIER_PATH = 512             # the evidence dossier's path limit
MAX_DOSSIER_INPUT_BYTES = 1024 * 1024    # the evidence dossier's input limit
MEMBER_BYTE_SHARE = 512 * 1024     # members may use half, so whole assets still fit
DOSSIER_BYTE_MARGIN = 32 * 1024    # record wrappers around the stored intake bytes
_CHUNK_BYTES = 64 * 1024
_REPORT_SKIPS = 32

_TEXT_SUFFIXES = ('.txt', '.text', '.log', '.md', '.markdown', '.json', '.csv')
_NESTED_SUFFIXES = ('.zip', '.jar', '.war', '.apk', '.7z', '.rar', '.tar', '.gz', '.tgz', '.bz2', '.xz',
                    '.cab', '.iso')
_METHODS = (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
_DECODE_ERRORS = (zipfile.BadZipFile, zlib.error, lzma.LZMAError, EOFError, NotImplementedError,
                  RuntimeError, OSError, ValueError)
_TOLERATED = {'encrypted', 'nested_archive_not_inspected', 'suspicious_expansion'}
_FAILED = ('encrypted_member', 'corrupt_member', 'text_intake_rejected')
_MEMBER_ID = re.compile(r'm\d{4}')
# A dossier source path may not carry these, so such a name must be skipped, not stored.
_BAD_NAME_CHARS = re.compile('[\x00-\x1f\x7f-\x9f\u2028\u2029]')

_REASONS = {
    'nested_archive_not_read': 'Nested archive; archives inside archives are not opened.',
    'encrypted_member': 'Encrypted member; no password is available, so its contents are unknown.',
    'unsafe_member': 'The name or layout of this member is unsafe, so it was not read.',
    'unsupported_member_type': 'Not a supported text member (txt, md, json, csv, log).',
    'unsupported_compression': 'Compression method other than stored or deflate.',
    'member_limit': f'More than {MAX_TEXT_MEMBERS} text members; the rest were not read.',
    'member_too_large': f'Larger than the {MAX_MEMBER_BYTES}-byte member limit.',
    'member_compresses_heavily': f'Expands more than {MAX_RATIO}:1, so it was not read.',
    'total_read_limit': f'The archive reached its {MAX_TOTAL_READ_BYTES}-byte read limit before this member.',
    'corrupt_member': 'The member failed to decompress or failed its checksum.',
    'text_intake_rejected': 'The member was read but is not usable text.',
    'time_budget_exhausted': 'The read time budget ran out before this member.',
    'member_path_too_long': f'The archive path plus this member name exceeds {MAX_DOSSIER_PATH} characters.',
    'project_source_limit': 'The project has no evidence source slots left for this member.',
    'project_evidence_size_limit': 'The project has no evidence size budget left for this member.',
}


class _TooLarge(Exception):
    pass


class _OutOfTime(Exception):
    pass


def _is_text_name(name: str) -> bool:
    return name.lower().endswith(_TEXT_SUFFIXES)


def _bomb_shaped(entry: dict) -> bool:
    claimed = entry.get('claimed_uncompressed_size_bytes') or 0
    return claimed >= RATIO_FLOOR_BYTES and claimed > MAX_RATIO * max(entry.get('compressed_size_bytes') or 0, 1)


def _bomb_reason(entries: list) -> str | None:
    """Refuse only at bomb scale; a smaller oversized note is skipped per member by ``_precheck``."""
    claimed_total = 0
    for entry in entries:
        if 'overlapping_entries' in (entry.get('safety_warnings') or []):
            return 'Members overlap each other, a zip-bomb construction, so the archive was not opened.'
        if not _is_text_name(str(entry.get('name') or '')):
            continue
        claimed = entry.get('claimed_uncompressed_size_bytes') or 0
        claimed_total += claimed
        if claimed >= BOMB_FLOOR_BYTES and _bomb_shaped(entry):
            return f'A text member claims {claimed} bytes at more than {MAX_RATIO}:1, so the archive was not opened.'
    if claimed_total > MAX_TOTAL_CLAIMED_BYTES:
        return f'Text members claim more than {MAX_TOTAL_CLAIMED_BYTES} bytes in total, so the archive was not opened.'
    return None


def _safe_name(name: str) -> bool:
    if _BAD_NAME_CHARS.search(name):
        return False
    return not any(len(part) >= 2 and not part.strip('. ') for part in re.split(r'[/\\]', name))


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
            or info.filename != name or not _safe_name(name)):
        return 'unsafe_member'
    if not _is_text_name(name):
        return 'unsupported_member_type'
    if info.compress_type not in _METHODS:
        return 'unsupported_compression'
    if (entry.get('claimed_uncompressed_size_bytes') or 0) > MAX_MEMBER_BYTES:
        return 'member_too_large'
    if _bomb_shaped(entry):
        return 'member_compresses_heavily'
    return None


def read_archive_text(envelope: dict, data: bytes, inspect_text, clock=time.monotonic) -> dict:
    """Return the ``inspect_archive`` envelope plus ``text_members`` and a read report."""
    if envelope.get('format') != 'zip' or envelope.get('status') in ('rejected', 'unsupported'):
        return envelope
    facts = envelope.get('facts') or {}
    entries = facts.get('entries') or []
    bomb = _bomb_reason(entries)
    if bomb:
        return _refuse(envelope, 'zip_bomb_guard', bomb, [])
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except _DECODE_ERRORS:
        return _refuse(envelope, 'corrupt_archive', 'The archive directory could not be read.', [])

    members, skipped, attempted, read_total = [], [], 0, 0
    deadline = clock() + TIME_BUDGET_SECONDS
    with archive:
        for index, (entry, info) in enumerate(zip(entries, archive.infolist()), 1):
            if entry.get('is_directory'):
                continue
            name = str(entry.get('name') or '')
            code = _precheck(entry, info)
            is_text = _is_text_name(name)
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
                else:
                    read_total += len(raw)
                    if read_total > MAX_TOTAL_READ_BYTES:
                        code = 'total_read_limit'
            if code is None:
                intake = inspect_text(raw, name.rsplit('/', 1)[-1])
                if intake.get('status') in ('ok', 'partial'):
                    members.append({'member_id': f'm{index:04d}', 'name': name, 'intake': intake})
                    continue
                code = 'text_intake_rejected'
            skipped.append({'name': name[:MAX_NAME_CHARS], 'code': code, 'reason': _REASONS[code],
                            'text_candidate': is_text})

    unread = [s for s in skipped if s.pop('text_candidate')]
    # Refuse only an archive with nothing else to offer: one bad note among healthy
    # entries is a partial result, and refusing would discard the inventory.
    if attempted and not members and all(s['code'] in _FAILED for s in skipped):
        codes = {s['code'] for s in skipped}
        code, reason = ('encrypted_archive', 'Every member is encrypted, so none could be read.') \
            if codes == {'encrypted_member'} else \
            ('corrupt_archive', 'Every member is corrupt or unusable, so none could be read.')
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
    bomb_shaped = sum(1 for e in entries if _bomb_shaped(e) and not _is_text_name(str(e.get('name') or '')))
    if bomb_shaped:
        warnings.append({'code': 'unread_members_compress_heavily',
                         'message': f'{bomb_shaped} unread member(s) expand more than {MAX_RATIO}:1.'})
    report = {'read': len(members), 'skipped': skipped[:_REPORT_SKIPS],
              'skipped_omitted': max(0, len(skipped) - _REPORT_SKIPS)}
    return dict(envelope, status=status, warnings=warnings, text_members=members, text_member_report=report)


def _member_bytes(member: dict) -> int:
    return len(json.dumps(member, ensure_ascii=False, sort_keys=True).encode('utf-8'))


def member_byte_room(envelope: dict, other_intake_bytes: int, other_member_bytes: int) -> int:
    """How many stored bytes this archive's members may use, given what the project already holds."""
    parent = {k: v for k, v in envelope.items() if k not in ('text_members', 'text_member_report')}
    parent_bytes = len(json.dumps(parent, ensure_ascii=False, sort_keys=True).encode('utf-8'))
    return max(0, min(MAX_DOSSIER_INPUT_BYTES - DOSSIER_BYTE_MARGIN - other_intake_bytes - parent_bytes,
                      MEMBER_BYTE_SHARE - other_member_bytes))


def fit_members(envelope: dict, relative_path: str, room: int, byte_room: int = MEMBER_BYTE_SHARE) -> dict:
    """Keep only the members the dossier can hold, reporting each one that is left out.

    ``room`` is how many member sources this archive may still add to the project and
    ``byte_room`` how many stored bytes, so a member-heavy archive can neither use up
    the slots other assets need nor push the dossier over its input limit.
    """
    members = envelope.get('text_members')
    if not isinstance(members, list) or not members:
        return envelope
    kept, dropped, used = [], [], 0
    for member in members:
        size = _member_bytes(member)
        code = ('member_path_too_long' if len(f"{relative_path}!{member['name']}") > MAX_DOSSIER_PATH
                else 'project_source_limit' if len(kept) >= room
                else 'project_evidence_size_limit' if used + size > byte_room else None)
        if code is None:
            kept.append(member)
            used += size
        else:
            dropped.append({'name': member['name'][:MAX_NAME_CHARS], 'code': code, 'reason': _REASONS[code]})
    old = dict(envelope['text_member_report'], member_bytes=used)
    if not dropped:
        return dict(envelope, text_member_report=old)
    skipped = dropped + old['skipped']
    report = dict(old, read=len(kept), skipped=skipped[:_REPORT_SKIPS],
                  skipped_omitted=old['skipped_omitted'] + max(0, len(skipped) - _REPORT_SKIPS))
    warnings = list(envelope.get('warnings') or []) + [
        {'code': 'text_members_skipped',
         'message': f'{len(dropped)} text member(s) did not fit in the project; see text_member_report.'}]
    return dict(envelope, status='partial', warnings=warnings, text_members=kept, text_member_report=report)


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
        records.append({'source_id': f"{source_id}:{member['member_id']}",
                        'relative_path': f"{relative_path}!{member['name']}", 'intake': member['intake']})
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
