"""Read the text of a PDF, page by page, in a killable child process under hard caps.

pypdf parses untrusted bytes in ``_pdf_worker.py``, never in the gateway. Nothing
in a PDF runs. Each page with text becomes one member of the envelope, the same
shape a ZIP's text members have, so every evidence item keeps its page number.
Encrypted, image-only and damaged files get an honest status; OCR is not offered.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unicodedata

from .zip_text import _REPORT_SKIPS, _refuse

MAX_PDF_BYTES = 32 * 1024 * 1024
MAX_PDF_PAGES = 32
MAX_PAGE_CHARS = 60000       # at most 240 KB of UTF-8, inside inspect_text's input budget
TIMEOUT_SECONDS = 20.0
WORKER = Path(__file__).with_name('_pdf_worker.py')
_WORKER_SLOTS = threading.BoundedSemaphore(2)   # each worker may use its full memory cap

_REFUSALS = {
    'encrypted': ('rejected', 'encrypted_pdf',
                  'The PDF is encrypted and no password is available, so its contents are unknown.'),
    'malformed': ('rejected', 'malformed_pdf', 'The file is damaged or is not a readable PDF.'),
    'reader_unavailable': ('unsupported', 'pdf_reader_unavailable',
                           'The PDF reader (pypdf) is not installed or could not be loaded in this Hermes environment.'),
    'memory_limit': ('unsupported', 'pdf_memory_limit',
                     'Reading this PDF hit the memory limit, so its contents are unknown.'),
}


class ReaderBusy(Exception):
    """No reader process could be started in time; says nothing about the file."""


def _reader_dir() -> str | None:
    """The directory holding pypdf, found without importing it into the gateway."""
    try:
        spec = importlib.util.find_spec('pypdf')
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.origin:
        return None
    return str(Path(spec.origin).resolve().parent.parent)


def _python() -> str | None:
    """A real Python interpreter; a host launcher such as hermes.exe cannot run the worker."""
    prefix = Path(sys.prefix)
    candidates = (sys.executable, getattr(sys, '_base_executable', None), prefix / 'python.exe',
                  prefix / 'Scripts' / 'python.exe', prefix / 'bin' / 'python3')
    for candidate in candidates:
        if candidate and Path(candidate).name.lower().startswith('python') and Path(candidate).is_file():
            return str(candidate)
    return None


def _run_worker(python: str, reader_dir: str, data: bytes) -> tuple[list, bool]:
    """Return (records from every complete output line, whether the deadline was hit)."""
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'PATH') if key in os.environ}
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    process = subprocess.Popen([python, '-I', '-S', '-B', str(WORKER), reader_dir,
                                str(MAX_PDF_PAGES), str(MAX_PAGE_CHARS)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               env=env, creationflags=flags)
    timed_out = False
    try:
        output, _ = process.communicate(data, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        output, _ = process.communicate()
    records = []
    for line in output.split(b'\n')[:-1]:   # the part after the last newline is incomplete
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records, timed_out


def _envelope(data: bytes, name: str) -> dict:
    shown = ''.join('_' if unicodedata.category(c) in ('Cc', 'Cf', 'Cs', 'Zl', 'Zp') else c for c in name)[:255]
    return {'schema_version': 1, 'format': 'unknown', 'document_format': 'pdf', 'status': 'ok',
            'source': {'name': shown, 'size_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()},
            'facts': {'document_format': 'pdf'}, 'warnings': []}


def _stop(envelope: dict, status: str, code: str, reason: str, skipped=()) -> dict:
    return dict(_refuse(envelope, code, reason, list(skipped)), status=status)


def _member(page: int, text: str, inspect_text) -> dict | None:
    name = f'page-{page:04d}.txt'
    intake = inspect_text(text.encode('utf-8', 'replace'), name)
    if intake.get('status') not in ('ok', 'partial'):
        return None
    # Set here, never read from the page's text, so a document cannot claim a page.
    return {'member_id': f'm{page:04d}', 'name': name, 'intake': dict(intake, pdf_page=page)}


def read_pdf_text(data: bytes, name: str, inspect_text) -> dict:
    """Return an intake envelope with one text member per page that has text."""
    envelope = _envelope(data, name)
    if len(data) > MAX_PDF_BYTES:
        return _stop(envelope, 'rejected', 'pdf_too_large', f'The PDF is larger than the {MAX_PDF_BYTES}-byte limit.')
    reader_dir, python = _reader_dir(), _python()
    if reader_dir is None or python is None:
        return _stop(envelope, 'unsupported', *_REFUSALS['reader_unavailable'][1:])
    # Long enough for two hung workers to reach their deadlines and free a slot.
    if not _WORKER_SLOTS.acquire(timeout=TIMEOUT_SECONDS * 3):
        raise ReaderBusy('Other PDFs were being read for too long; recover this one again.')
    try:
        records, timed_out = _run_worker(python, reader_dir, data)
    except OSError:
        return _stop(envelope, 'unsupported', 'pdf_reader_unavailable', 'The PDF reader process could not be started.')
    finally:
        _WORKER_SLOTS.release()

    refused = next((r for r in records if r.get('kind') == 'refused'), None)
    if refused:
        status, code, reason = _REFUSALS.get(refused.get('code'), _REFUSALS['malformed'])
        return _stop(envelope, status, code, reason)
    start = next((r for r in records if r.get('kind') == 'start'), None)
    if start is None:
        if timed_out:
            return _stop(envelope, 'rejected', 'pdf_timeout', f'Reading stopped after {TIMEOUT_SECONDS:g} seconds.')
        # No verdict from the reader, so this says nothing about whether the file is damaged.
        return _stop(envelope, 'unsupported', 'pdf_reader_stopped',
                     'The PDF reader stopped before opening this file, so its contents are unknown.')

    members, skipped, failed, out_of_memory = [], [], 0, 0
    seen = set()
    for record in records:
        page = record.get('page')
        if type(page) is not int or page in seen:
            continue
        seen.add(page)
        name_on_report = f'page-{page:04d}.txt'
        if record.get('kind') == 'page_failed' and record.get('code') == 'memory_limit':
            failed += 1
            out_of_memory += 1
            skipped.append({'name': name_on_report, 'code': 'page_memory_limit',
                            'reason': 'Reading this page hit the memory limit; its contents are unknown.'})
        elif record.get('kind') == 'page_failed':
            failed += 1
            skipped.append({'name': name_on_report, 'code': 'page_failed', 'reason': 'This page could not be decoded.'})
        elif record.get('kind') == 'page':
            text = record.get('text')
            member = _member(page, text, inspect_text) if isinstance(text, str) and text.strip() else None
            if member is not None:
                members.append(member)
                continue
            skipped.append({'name': name_on_report, 'code': 'page_no_text',
                            'reason': 'No extractable text on this page; it may be a scan or an image.'})

    page_count = start.get('page_count') if type(start.get('page_count')) is int else 0
    readable_limit = min(page_count, MAX_PDF_PAGES)
    finished = any(r.get('kind') == 'done' for r in records)
    # How many pages became evidence is text_member_report.read, which stays true after fitting.
    envelope['facts'].update(page_count=page_count,
                             encrypted_readable_without_password=bool(start.get('encrypted')))
    if not members and finished and not failed:
        return _stop(envelope, 'rejected', 'no_extractable_text',
                     'No page has extractable text, so this is probably a scan or image-only PDF. '
                     'OCR is not available.', skipped)
    if not members and out_of_memory:
        return _stop(envelope, *_REFUSALS['memory_limit'], skipped)
    if not members and not finished and not timed_out:
        return _stop(envelope, 'unsupported', 'pdf_reader_stopped',
                     'The PDF reader stopped before any page gave text, so its contents are unknown.', skipped)
    if not members:
        code, reason = (('pdf_timeout', f'Reading stopped after {TIMEOUT_SECONDS:g} seconds before any page gave text.')
                        if timed_out else ('malformed_pdf', 'No page of this PDF could be decoded.'))
        return _stop(envelope, 'rejected', code, reason, skipped)

    warnings = []
    if not finished:
        code, reason = (('pdf_timeout', f'Reading stopped after {TIMEOUT_SECONDS:g} seconds; later pages were not read.')
                        if timed_out else ('pdf_reader_stopped', 'The PDF reader stopped early; later pages were not read.'))
        warnings.append({'code': code, 'message': reason})
        unread = readable_limit - len(seen)
        if unread > 0:
            skipped.append({'name': f'{unread} page(s) after the last one read', 'code': code, 'reason': reason})
    if page_count > MAX_PDF_PAGES:
        reason = f'Only the first {MAX_PDF_PAGES} of {page_count} pages were read.'
        warnings.append({'code': 'page_limit', 'message': reason})
        skipped.append({'name': f'pages {MAX_PDF_PAGES + 1}-{page_count}', 'code': 'page_limit', 'reason': reason})
    if out_of_memory:
        warnings.append({'code': 'pdf_memory_limit',
                         'message': f'{out_of_memory} page(s) hit the memory limit; see text_member_report.'})
    no_text = sum(s['code'] in ('page_no_text', 'page_failed') for s in skipped)
    if no_text:
        warnings.append({'code': 'pages_without_text',
                         'message': f'{no_text} page(s) gave no text; see text_member_report.'})
    # The worker's cap, or the shorter excerpt inspect_text keeps of a dense page.
    clipped = ({r['page'] for r in records if r.get('kind') == 'page' and r.get('truncated') is True}
               | {m['intake']['pdf_page'] for m in members if (m['intake'].get('facts') or {}).get('excerpt_truncated')})
    if clipped:
        warnings.append({'code': 'page_text_clipped',
                         'message': f'{len(clipped)} long page(s) were clipped; only the beginning of each became evidence.'})
    report = {'read': len(members), 'skipped': skipped[:_REPORT_SKIPS],
              'skipped_omitted': max(0, len(skipped) - _REPORT_SKIPS)}
    return dict(envelope, status='partial' if warnings else 'ok', warnings=warnings,
                text_members=members, text_member_report=report)


def mark_pdf_pages(dossier: dict, records: list) -> dict:
    """Put each page number on the dossier rows and evidence items that came from that page."""
    if not isinstance(dossier, dict):
        return dossier
    pages = {r['source_id']: r['intake']['pdf_page'] for r in records
             if isinstance(r.get('intake'), dict) and type(r['intake'].get('pdf_page')) is int}
    for key in ('sources', 'evidence'):
        for row in dossier.get(key) or []:
            if isinstance(row, dict) and row.get('source_id') in pages:
                row['page_number'] = pages[row['source_id']]
    return dossier
