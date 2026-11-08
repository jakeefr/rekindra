"""Immutable input snapshots and evidence-bearing recovery projects.

This is bounded local processing, not a hostile multi-user filesystem sandbox.
Only one Hermes process may write a particular store in this first milestone.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
import sys
from pathlib import Path
import re
import stat
import threading
import time
import uuid

from .identify import identify
from .tga import decode_tga, RecoveryError
from .png import encode_png
from .zip_text import MAX_DOSSIER_SOURCES, fit_members, member_byte_room, member_records

_STORE_LOCK = threading.RLock()
_ID = re.compile(r'^[0-9a-f]{32}$')
_HASH = re.compile(r'^[0-9a-f]{64}$')
_ARTIFACT_KINDS = {('recovered', 'png'), ('evidence', 'intake-json')}
_EVIDENCE_FORMATS = ('text', 'zip')
_MAX_INTAKE_BYTES = 16 * 1024 * 1024
_STAGED_GRACE_SECONDS = 300
_STAGED = re.compile(r'^(?:[0-9a-f]{32}\.intake|evidence)\.json\.[0-9a-f]{32}\.(?:new|old)$')
_EXCLUDED = {'.git', '.ssh', '.aws', '.azure', '.gnupg', '.venv', 'node_modules', '__pycache__'}


class ProjectError(ValueError):
    """Actionable input or project-integrity failure."""


@dataclass(frozen=True)
class Limits:
    max_files: int = 500
    max_file_bytes: int = 100_000_000
    max_total_bytes: int = 500_000_000
    max_entries: int = 2000
    max_depth: int = 32


def _linked(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def _no_links(path: Path) -> None:
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            if _linked(part):
                raise ProjectError('Linked paths and Windows reparse points are not supported')


def _atomic(path: Path, data: bytes) -> None:
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('xb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


class ProjectStore:
    def __init__(self, root: Path, limits: Limits | None = None):
        self.root = Path(os.path.abspath(root))
        self.limits = limits or Limits()

    def _project(self, project_id: str) -> Path:
        if not isinstance(project_id, str) or not _ID.fullmatch(project_id):
            raise ProjectError('Invalid project identifier')
        path = self.root / project_id
        _no_links(path)
        if not path.is_dir():
            raise ProjectError('Project not found')
        return path

    def _save(self, path: Path, project: dict) -> None:
        _atomic(path / 'project.json', json.dumps(project, ensure_ascii=False, indent=2).encode('utf-8'))

    def status(self, project_id: str) -> dict:
        with _STORE_LOCK:
            try:
                path = self._project(project_id) / 'project.json'
                _no_links(path)
                if path.stat().st_size > 2_000_000:
                    raise ProjectError('Project manifest exceeds limit')
                project = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(project, dict) or project.get('project_id') != project_id or project.get('schema_version') != 1:
                    raise ProjectError('Unsupported or malformed project manifest')
                if not isinstance(project.get('assets'), list) or not isinstance(project.get('artifacts'), list):
                    raise ProjectError('Malformed project collections')
                asset_ids = set()
                for asset in project['assets']:
                    if (not isinstance(asset, dict)
                            or not isinstance(asset.get('asset_id'), str) or not _ID.fullmatch(asset['asset_id'])
                            or asset['asset_id'] in asset_ids
                            or not isinstance(asset.get('sha256'), str) or not _HASH.fullmatch(asset['sha256'])
                            or type(asset.get('size')) is not int or asset['size'] < 0
                            or not isinstance(asset.get('source_path'), str)
                            or not isinstance(asset.get('format'), str) or asset.get('kind') != 'original'):
                        raise ProjectError('Malformed asset record: project manifest integrity failure')
                    asset_ids.add(asset['asset_id'])
                artifact_ids = set()
                for artifact in project['artifacts']:
                    if (not isinstance(artifact, dict)
                            or not isinstance(artifact.get('asset_id'), str)
                            or artifact['asset_id'] not in asset_ids or artifact['asset_id'] in artifact_ids
                            or (artifact.get('kind'), artifact.get('format')) not in _ARTIFACT_KINDS
                            or not isinstance(artifact.get('sha256'), str) or not _HASH.fullmatch(artifact['sha256'])
                            or not isinstance(artifact.get('source_sha256'), str) or not _HASH.fullmatch(artifact['source_sha256'])
                            or not isinstance(artifact.get('path'), str)):
                        raise ProjectError('Malformed artifact record: project manifest integrity failure')
                    artifact_ids.add(artifact['asset_id'])
                return project
            except (OSError, json.JSONDecodeError, UnicodeError) as exc:
                raise ProjectError('Cannot read project manifest; preserve the project for diagnosis') from exc

    def inspect(self, folder: Path) -> dict:
        with _STORE_LOCK:
            source = Path(os.path.abspath(folder))
            _no_links(source)
            _no_links(self.root)
            if not source.is_dir():
                raise ProjectError('Select an existing local folder')
            source, root = source.resolve(), self.root.resolve()
            if source.is_relative_to(root) or root.is_relative_to(source):
                raise ProjectError('Source folder and project storage must not overlap')
            project_id = uuid.uuid4().hex
            directory = self.root / project_id
            (directory / 'originals').mkdir(parents=True)
            (directory / 'artifacts').mkdir()
            project = {'schema_version': 1, 'project_id': project_id,
                       'created_at': datetime.now(timezone.utc).isoformat(),
                       'source_name': source.name, 'assets': [], 'artifacts': [],
                       'skipped': [], 'truncated': False, 'stage': 'inspected'}
            stack, visited, total = [(source, 0)], 0, 0
            while stack:
                current, depth = stack.pop()
                _no_links(current)
                try:
                    with os.scandir(current) as listing:
                        entries = []
                        for entry in listing:
                            visited += 1
                            if visited > self.limits.max_entries:
                                project['truncated'] = True
                                break
                            entries.append(entry)
                except OSError:
                    project['skipped'].append({'source_path': str(current.relative_to(source)), 'reason': 'unreadable directory'})
                    continue
                for entry in sorted(entries, key=lambda e: e.name):
                    path = Path(entry.path)
                    relative = path.relative_to(source).as_posix()
                    reason = None
                    try:
                        _no_links(path)
                        if entry.name.lower() in _EXCLUDED or entry.name.lower() == '.env' or entry.name.lower().startswith('.env.'):
                            reason = 'excluded private or development directory/file'
                        elif entry.is_dir(follow_symlinks=False):
                            if depth < self.limits.max_depth:
                                stack.append((path, depth+1))
                            else:
                                reason = 'directory depth limit'
                            if reason is None:
                                continue
                        elif not entry.is_file(follow_symlinks=False):
                            reason = 'not a regular file'
                        elif len(project['assets']) >= self.limits.max_files:
                            project['truncated'] = True
                            reason = 'file count limit'
                        else:
                            size = path.stat().st_size
                            if size > self.limits.max_file_bytes or size + total > self.limits.max_total_bytes:
                                reason = 'input byte limit'
                            else:
                                asset = self._snapshot(path, directory, relative, self.limits.max_total_bytes-total)
                                total += asset['size']
                                project['assets'].append(asset)
                    except (OSError, ProjectError) as exc:
                        reason = str(exc) if isinstance(exc, ProjectError) else 'unreadable or changed file'
                    if reason:
                        project['skipped'].append({'source_path': relative, 'reason': reason})
                if project['truncated']:
                    break
            self._save(directory, project)
            return project

    def _snapshot(self, source: Path, directory: Path, relative: str, remaining: int) -> dict:
        asset_id = uuid.uuid4().hex
        destination = directory / 'originals' / asset_id
        digest, size, header = hashlib.sha256(), 0, b''
        before = source.lstat()
        try:
            flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
            with os.fdopen(os.open(source, flags), 'rb') as inp, destination.open('xb') as out:
                opened = os.fstat(inp.fileno())
                if not stat.S_ISREG(opened.st_mode) or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                    raise ProjectError('Source changed during inspection')
                _no_links(source)
                while chunk := inp.read(1024 * 1024):
                    size += len(chunk)
                    if size > min(self.limits.max_file_bytes, remaining):
                        raise ProjectError('Input byte limit exceeded during copy')
                    if len(header) < 65536:
                        header += chunk[:65536-len(header)]
                    digest.update(chunk)
                    out.write(chunk)
                after = os.fstat(inp.fileno())
                if (opened.st_size, opened.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or size != opened.st_size:
                    raise ProjectError('Source changed during inspection')
            return {'asset_id': asset_id, 'source_path': relative, 'size': size,
                    'sha256': digest.hexdigest(), 'format': identify(header, relative), 'kind': 'original'}
        except Exception:
            destination.unlink(missing_ok=True)
            raise

    def recover(self, project_id: str, asset_id: str, evidence_reader=None) -> dict:
        """Recover one saved asset.

        TGA decodes to PNG. Text and ZIP go through ``evidence_reader`` (a dict with
        ``intake(format, data, name)`` and ``dossier(records)``) when the caller
        supplies one; their result is quoted observation, never interpretation.
        """
        with _STORE_LOCK:
            if not isinstance(asset_id, str) or not _ID.fullmatch(asset_id):
                raise ProjectError('Invalid asset identifier')
            project = self.status(project_id)
            directory = self._project(project_id)
            asset = next((a for a in project['assets'] if isinstance(a, dict) and a.get('asset_id') == asset_id), None)
            if not asset:
                raise ProjectError('Asset not found in this project')
            source = directory / 'originals' / asset_id
            _no_links(source)
            if source.stat().st_size > self.limits.max_file_bytes:
                raise ProjectError('Snapshot byte limit exceeded')
            with source.open('rb') as inp:
                data = inp.read(self.limits.max_file_bytes+1)
            if len(data) > self.limits.max_file_bytes or hashlib.sha256(data).hexdigest() != asset.get('sha256'):
                raise ProjectError('Snapshot integrity check failed; original copy changed')
            if asset.get('format') in _EVIDENCE_FORMATS and evidence_reader is not None:
                return self._recover_evidence(project, directory, asset, data, evidence_reader)
            if asset.get('format') not in ('tga', 'tga_candidate'):
                raise ProjectError('Recovery supports the documented TGA subset, plus text and ZIP inventory')
            try:
                raster = decode_tga(data)
                png = encode_png(raster)
            except RecoveryError as exc:
                raise ProjectError(str(exc)) from exc
            target = directory / 'artifacts' / (asset_id + '.png')
            _no_links(target)
            _atomic(target, png)
            artifact = {'asset_id': asset_id, 'kind': 'recovered', 'format': 'png',
                        'path': str(target), 'source_sha256': asset['sha256'],
                        'sha256': hashlib.sha256(png).hexdigest(), 'decoder': 'rekindra-tga-v1',
                        'width': raster.width, 'height': raster.height, 'warnings': list(raster.warnings)}
            project['artifacts'] = [a for a in project['artifacts'] if a.get('asset_id') != asset_id] + [artifact]
            project['stage'] = 'recovered'
            self._save(directory, project)
            return artifact

    def _recover_evidence(self, project: dict, directory: Path, asset: dict, data: bytes, reader) -> dict:
        # Everything is built and checked in memory first; nothing is written unless the
        # combined dossier is valid, so one bad source cannot replace a good evidence.json.
        asset_id = asset['asset_id']
        artifacts_dir = directory / 'artifacts'
        envelope = reader['intake'](asset['format'], data, asset['source_path'].rsplit('/', 1)[-1])
        if not isinstance(envelope, dict):
            raise ProjectError('Evidence intake returned no result')
        # Every evidence asset keeps its own slot; members share what is left.
        slots = MAX_DOSSIER_SOURCES - sum(a.get('format') in _EVIDENCE_FORMATS for a in project['assets'])
        others = [a for a in project['artifacts'] if a.get('kind') == 'evidence' and a.get('asset_id') != asset_id]
        used = sum((a.get('text_members') or {}).get('read', 0) for a in others)
        byte_room = member_byte_room(envelope, sum(a.get('intake_bytes', 0) for a in others),
                                     sum((a.get('text_members') or {}).get('member_bytes', 0) for a in others))
        envelope = fit_members(envelope, asset['source_path'], max(0, slots - used), byte_room)
        blob = json.dumps(envelope, ensure_ascii=False, sort_keys=True).encode('utf-8')
        warnings = [w.get('code') for w in envelope.get('warnings') or [] if isinstance(w, dict)]
        artifact = {'asset_id': asset_id, 'kind': 'evidence', 'format': 'intake-json',
                    'path': str(artifacts_dir / (asset_id + '.intake.json')), 'source_sha256': asset['sha256'],
                    'sha256': hashlib.sha256(blob).hexdigest(), 'intake_bytes': len(blob),
                    'decoder': 'rekindra-intake-v1',
                    'intake_format': envelope.get('format'), 'status': envelope.get('status'),
                    'warnings': warnings}
        report = envelope.get('text_member_report')
        if isinstance(report, dict):
            artifact['text_members'] = report
        artifacts = [a for a in project['artifacts'] if a.get('asset_id') != asset_id] + [artifact]
        paths = {a['asset_id']: a['source_path'] for a in project['assets']}
        records = []
        for item in artifacts:
            if item.get('kind') != 'evidence':
                continue
            sid = item.get('asset_id')
            if not isinstance(sid, str) or not _ID.fullmatch(sid) or sid not in paths:
                raise ProjectError('Saved evidence refers to an unknown asset')
            if sid == asset_id:
                raw = blob
            else:
                # Never trust the stored path string: derive it from the asset id.
                raw = self._read_intake(artifacts_dir / (sid + '.intake.json'))
                if hashlib.sha256(raw).hexdigest() != item.get('sha256'):
                    raise ProjectError('Saved intake changed; re-run recovery for that asset')
            try:
                intake = json.loads(raw.decode('utf-8'))
            except (UnicodeDecodeError, ValueError) as exc:
                raise ProjectError('Saved intake is not readable; re-run recovery for that asset') from exc
            try:
                intake, members = member_records(sid, paths[sid], intake)
            except ValueError as exc:
                raise ProjectError('Saved intake is not readable; re-run recovery for that asset') from exc
            if isinstance(intake, dict) and intake.get('status') == 'rejected':
                # Intake refused this source, so nothing from it may surface as recovered
                # evidence. Its row and rejection stay; its facts are dropped.
                intake, members = dict(intake, facts={}), []
            records.append({'source_id': sid, 'relative_path': paths[sid], 'intake': intake})
            records.extend(members)
        dossier = reader['dossier'](records)
        if not isinstance(dossier, dict) or dossier.get('status') == 'rejected':
            errors = dossier.get('errors') if isinstance(dossier, dict) else None
            codes = [e.get('code') for e in errors or [] if isinstance(e, dict)]
            raise ProjectError('Evidence dossier refused this source; earlier evidence is unchanged'
                               + (' (' + ', '.join(c for c in codes if c) + ')' if codes else ''))
        dossier_blob = json.dumps(dossier, ensure_ascii=False, sort_keys=True).encode('utf-8')
        target = artifacts_dir / (asset_id + '.intake.json')
        dossier_path = artifacts_dir / 'evidence.json'
        _no_links(target)
        _no_links(dossier_path)
        # Stage new bytes first, then swap by rename only. Rename needs no free space, so
        # the rollback cannot fail the way the write did; after the manifest is saved,
        # nothing is rolled back.
        # The stamp leads with its staging time: a rename keeps the source file's mtime, so
        # an aside's age can only be read from its name.
        stamp = f'{time.time_ns():016x}{uuid.uuid4().hex[:16]}'
        swaps = [(path, path.with_name(f'{path.name}.{stamp}.new'), path.with_name(f'{path.name}.{stamp}.old'), data)
                 for path, data in ((target, blob), (dossier_path, dossier_blob))]
        updated = dict(project, artifacts=artifacts, stage='recovered',
                       evidence={'path': str(dossier_path), 'sha256': hashlib.sha256(dossier_blob).hexdigest(),
                                 'status': dossier.get('status'),
                                 # Asset IDs only: ZIP members are cited through their archive.
                                 'source_ids': [r['source_id'] for r in records if ':' not in r['source_id']]})
        moved, promoted, committed = [], [], False
        try:
            for _, staged, _, data in swaps:
                with staged.open('xb') as out:
                    out.write(data)
                    out.flush()
                    os.fsync(out.fileno())
            for path, staged, aside, _ in swaps:
                if path.exists():
                    os.replace(path, aside)
                    moved.append((path, aside))
                os.replace(staged, path)
                promoted.append(path)
            self._save(directory, updated)
            committed = True
        finally:
            if not committed:
                kept = []
                for path in promoted:
                    if not any(path == m for m, _ in moved):
                        try:
                            path.unlink(missing_ok=True)
                        except OSError:
                            pass
                for path, aside in moved:
                    try:
                        os.replace(aside, path)
                    except OSError:
                        kept.append(aside.name)
                for _, staged, _, _ in swaps:
                    try:
                        staged.unlink(missing_ok=True)
                    except OSError:
                        pass
                if kept:
                    # The set-aside files are now the only copy of the previous bytes: keep them.
                    detail = ('Evidence files could not be restored after a failed write; previous bytes '
                              'are kept in artifacts as ' + ', '.join(kept)
                              + '. Re-run recovery for this asset to rebuild them.')
                    pending = sys.exc_info()[1]
                    if pending is None or isinstance(pending, Exception):
                        raise ProjectError(detail)
                    pending.add_note(detail)  # an interrupt keeps propagating, with the detail attached
        project.clear()
        project.update(updated)
        # Committed: best-effort removal of this attempt's aside copies and any left by an
        # earlier failed attempt. It never fails a recovery that is already saved. recover()
        # holds _STORE_LOCK for in-process callers; another process sharing the store could
        # have an aside in flight, so other attempts' files are only removed once their stamp
        # is more than _STAGED_GRACE_SECONDS from now in either direction. That protects
        # processes whose clocks agree within the grace period and whose staging (including
        # fsync) plus commit finish inside it; anything beyond needs a cross-process lock.
        now = time.time_ns()
        try:
            leftovers = [path for path in artifacts_dir.iterdir() if _STAGED.fullmatch(path.name)]
        except OSError:
            leftovers = []
        for leftover in leftovers:
            try:
                staged = int(leftover.name.rsplit('.', 2)[1][:16], 16)
                if (f'.{stamp}.' not in leftover.name
                        and abs(now - staged) < _STAGED_GRACE_SECONDS * 1_000_000_000):
                    continue
                leftover.unlink(missing_ok=True)
            except OSError:
                continue
        return {'artifact': artifact, 'dossier': dossier, 'dossier_path': str(dossier_path)}

    @staticmethod
    def _read_intake(path: Path) -> bytes:
        _no_links(path)
        try:
            with path.open('rb') as inp:
                raw = inp.read(_MAX_INTAKE_BYTES + 1)
        except OSError as exc:
            raise ProjectError('Saved intake is missing; re-run recovery for that asset') from exc
        if len(raw) > _MAX_INTAKE_BYTES:
            raise ProjectError('Saved intake is too large')
        return raw
