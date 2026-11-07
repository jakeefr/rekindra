"""Verified source selection, immutable plans, and portable artifact packaging."""
import base64
import hashlib
import html
import json
import re
from pathlib import Path
import struct
import uuid

from .projects import ProjectStore, ProjectError, _no_links, _atomic, _ID, _MAX_INTAKE_BYTES
from .scenes import validate_scene, SceneError

RUNTIME = Path(__file__).resolve().parents[1] / 'runtime'
MAX_PLAN_BYTES = 512_000


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    """Bounded baseline/progressive JPEG header walk; never decompress pixels."""
    if data[:2] != b'\xff\xd8': raise SceneError('Invalid JPEG header')
    pos = 2
    while pos < len(data):
        if data[pos] != 255: raise SceneError('Malformed JPEG marker')
        while pos < len(data) and data[pos] == 255: pos += 1
        if pos >= len(data): break
        marker = data[pos]; pos += 1
        if marker in (0, 0xd8, 0xd9, 0xda) or 0xd0 <= marker <= 0xd7: break
        if marker == 1: continue
        if pos+2 > len(data): break
        size = int.from_bytes(data[pos:pos+2], 'big')
        if size < 2 or pos+size > len(data): break
        if marker in (0xc0, 0xc2):
            if size < 8: break
            precision, height, width, count = struct.unpack_from('>BHHB', data, pos+2)
            if precision != 8 or count not in (1, 3, 4) or size != 8+3*count:
                raise SceneError('Unsupported JPEG frame header')
            if not width or not height or width*height > 20_000_000:
                raise SceneError('Image exceeds decoded pixel budget')
            return width, height
        if marker in (0xc1,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf):
            raise SceneError('Only baseline and progressive JPEG frames are supported')
        pos += size
    raise SceneError('Missing or truncated JPEG frame header')


_RECOVERED_KEYS = frozenset(('asset_id', 'source_path', 'evidence_id', 'kind', 'locator', 'text',
                             'clipped', 'content', 'untrusted'))


def _interpretation(ref: dict) -> dict:
    return {'asset_id': ref['asset_id'], 'evidence_ids': list(ref['evidence_ids']),
            'interpretation': ref['interpretation'],
            'content': 'interpretation', 'origin': 'agent', 'recovered': False}


def _evidence_id(source_id: str, locator, text: str) -> str:
    # Same derivation as rekindra_evidence._dossier._evidence: the ID commits to
    # the source, the locator and the exact quoted text.
    digest = hashlib.sha256(json.dumps([source_id, locator, text], sort_keys=True).encode('utf-8')).hexdigest()
    return f'ev-{digest[:24]}'


class CompositionStore:
    def __init__(self, projects: ProjectStore):
        self.projects = projects

    def sources(self, project_id: str, selected_ids: list[str]) -> list[dict]:
        if (not isinstance(selected_ids, list) or not 1 <= len(selected_ids) <= 6
                or any(not isinstance(x, str) or not _ID.fullmatch(x) for x in selected_ids)
                or len(set(selected_ids)) != len(selected_ids)):
            raise SceneError('Select one to six unique image asset IDs')
        project = self.projects.status(project_id)
        directory = self.projects._project(project_id)
        by_id = {a['asset_id']: a for a in project['assets']}
        result, total = [], 0
        for aid in selected_ids:
            if aid not in by_id: raise SceneError('Selected source is not in this project')
            asset = by_id[aid]
            path = directory / 'originals' / aid
            _no_links(path)
            with path.open('rb') as inp: original = inp.read(self.projects.limits.max_file_bytes+1)
            if len(original) > self.projects.limits.max_file_bytes or hashlib.sha256(original).hexdigest() != asset['sha256']:
                raise ProjectError('Source integrity check failed before creative processing')
            if asset['format'] in ('tga', 'tga_candidate'):
                recovered = self.projects.recover(project_id, aid)
                path = Path(recovered['path']); _no_links(path)
                with path.open('rb') as inp: data = inp.read(2_000_001)
                if hashlib.sha256(data).hexdigest() != recovered['sha256']:
                    raise ProjectError('Recovered image integrity check failed')
                mime = 'image/png'
            elif asset['format'] in ('png', 'jpeg'):
                data, mime = original, 'image/' + asset['format']
            else:
                raise SceneError('Creative scenes currently accept PNG, JPEG, or recovered TGA images')
            total += len(data)
            if len(data) > 2_000_000 or total > 8_000_000:
                raise SceneError('Image budget exceeded: 2 MB per image, 8 MB total')
            if mime == 'image/png':
                if len(data) < 33 or data[:8] != b'\x89PNG\r\n\x1a\n' or data[12:16] != b'IHDR':
                    raise SceneError('Invalid PNG source header')
                width, height = struct.unpack_from('>II', data, 16)
                if not width or not height or width*height > 20_000_000:
                    raise SceneError('Image exceeds decoded pixel budget')
            else:
                jpeg_dimensions(data)
            result.append({'asset_id': aid, 'name': asset['source_path'], 'mime_type': mime,
                           'data': data, 'source_sha256': asset['sha256'], 'image_sha256': hashlib.sha256(data).hexdigest(),
                           'kind': 'recovered' if asset['format'].startswith('tga') else 'original'})
        return result

    def text_provenance(self, project_id: str, refs) -> dict | None:
        """Resolve text_references against the saved dossier.

        Recovered evidence text and the agent's interpretation are kept in separate
        lists: the interpretation is never labeled or stored as recovered content.
        """
        if refs is None:
            return None
        project = self.projects.status(project_id)
        manifest = project.get('evidence')
        if not isinstance(manifest, dict):
            raise SceneError('text_references need recovered evidence; run rekindra_recover on the text or ZIP asset first')
        path = self.projects._project(project_id) / 'artifacts' / 'evidence.json'
        _no_links(path)
        try:
            with path.open('rb') as inp:
                raw = inp.read(_MAX_INTAKE_BYTES + 1)
        except OSError as exc:
            raise SceneError('Saved evidence is missing; re-run rekindra_recover') from exc
        if len(raw) > _MAX_INTAKE_BYTES or hashlib.sha256(raw).hexdigest() != manifest.get('sha256'):
            raise SceneError('Saved evidence changed; re-run rekindra_recover')
        try:
            dossier = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError) as exc:
            raise SceneError('Saved evidence is not readable; re-run rekindra_recover') from exc
        if not isinstance(dossier, dict):
            raise SceneError('Saved evidence is not readable; re-run rekindra_recover')
        artifacts = {a.get('asset_id'): a for a in project['artifacts'] if a.get('kind') == 'evidence'}
        paths = {a['asset_id']: a['source_path'] for a in project['assets']}
        items = {e.get('evidence_id'): e for e in dossier.get('evidence') or [] if isinstance(e, dict)}
        cited = set(manifest.get('source_ids') or [])
        recovered, interpretations = [], []
        for ref in refs:
            aid = ref['asset_id']
            artifact = artifacts.get(aid)
            if artifact is None or aid not in cited or aid not in paths:
                raise SceneError(f'text_references asset {aid} has no recovered evidence; run rekindra_recover on it first')
            if artifact.get('status') in ('rejected', 'unsupported'):
                raise SceneError(f'text_references asset {aid} was {artifact.get("status")} by intake and cannot be cited')
            for eid in ref['evidence_ids']:
                item = items.get(eid)
                if item is None or item.get('source_id') != aid:
                    raise SceneError(f'Evidence {eid} was not recovered from asset {aid}')
                recovered.append({'asset_id': aid, 'source_path': paths[aid], 'evidence_id': eid,
                                  'kind': item.get('kind'), 'locator': item.get('locator'), 'text': item.get('text'),
                                  'clipped': bool(item.get('clipped')),
                                  'content': 'recovered', 'untrusted': True})
            interpretations.append(_interpretation(ref))
        return {'recovered_evidence': recovered, 'interpretations': interpretations}

    def check_text_provenance(self, project_id: str, refs, stored) -> None:
        """Check a saved plan's text provenance without the live dossier.

        Recovering another source rebuilds evidence.json and may reshape or evict
        items, so a saved plan keeps its own quoted copy. Each copy must still hash
        to its cited evidence_id, and the interpretations must match the scene.
        """
        if refs is None:
            if stored is not None:
                raise SceneError('Plan text evidence provenance has changed')
            return
        paths = {a['asset_id']: a['source_path'] for a in self.projects.status(project_id)['assets']}
        wanted = [(ref['asset_id'], eid) for ref in refs for eid in ref['evidence_ids']]
        if (not isinstance(stored, dict) or set(stored) != {'recovered_evidence', 'interpretations'}
                or stored['interpretations'] != [_interpretation(ref) for ref in refs]
                or not isinstance(stored['recovered_evidence'], list)
                or len(stored['recovered_evidence']) != len(wanted)):
            raise SceneError('Plan text evidence provenance has changed')
        for item, (aid, eid) in zip(stored['recovered_evidence'], wanted):
            if (not isinstance(item, dict) or set(item) != _RECOVERED_KEYS
                    or item['asset_id'] != aid or item['evidence_id'] != eid
                    or item['source_path'] != paths.get(aid) or item['content'] != 'recovered'
                    or item['untrusted'] is not True or not isinstance(item['text'], str)
                    or _evidence_id(aid, item['locator'], item['text']) != eid):
                raise SceneError('Plan text evidence provenance has changed')

    def save_plan(self, project_id: str, scene: dict, selected_ids: list[str], attribution: dict) -> dict:
        sources = self.sources(project_id, selected_ids)
        normalized = validate_scene(scene, set(selected_ids))
        plan_id = uuid.uuid4().hex
        directory = self.projects._project(project_id) / 'plans'
        _no_links(directory); directory.mkdir(exist_ok=True)
        record = {'plan_id': plan_id, 'project_id': project_id, 'kind': 'generated',
                  'scene': normalized, 'source_ids': selected_ids,
                  'sources': [{k: v for k, v in s.items() if k != 'data'} for s in sources],
                  'model': attribution}
        text = self.text_provenance(project_id, normalized.get('text_references'))
        if text is not None:
            record['text_provenance'] = text
        encoded=json.dumps(record, ensure_ascii=False, allow_nan=False, indent=2).encode()
        if len(encoded)>MAX_PLAN_BYTES:raise SceneError('Plan exceeds size limit')
        _atomic(directory / (plan_id + '.json'), encoded)
        return record

    def load_plan(self, project_id: str, plan_id: str) -> dict:
        if not isinstance(plan_id, str) or not _ID.fullmatch(plan_id): raise SceneError('Invalid plan identifier')
        path = self.projects._project(project_id) / 'plans' / (plan_id + '.json')
        _no_links(path)
        try:
            if path.stat().st_size > MAX_PLAN_BYTES: raise SceneError('Plan exceeds size limit')
            record = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(record, dict) or record.get('project_id') != project_id or record.get('plan_id') != plan_id:
                raise SceneError('Malformed plan identity')
            sources = self.sources(project_id, record.get('source_ids'))
            record['scene'] = validate_scene(record.get('scene'), {s['asset_id'] for s in sources})
            expected = record.get('sources')
            actual = [{k: v for k, v in s.items() if k != 'data'} for s in sources]
            if expected != actual: raise SceneError('Plan source provenance has changed')
            self.check_text_provenance(project_id, record['scene'].get('text_references'), record.get('text_provenance'))
            return record
        except (OSError, json.JSONDecodeError) as exc:
            raise SceneError('Cannot load this scene plan') from exc

    def build(self, project_id: str, plan_id: str, review_camera=None) -> dict:
        plan = self.load_plan(project_id, plan_id)
        inspection=review_camera is not None
        if inspection:
            if (plan['scene']['schema_version']!=2 or not isinstance(review_camera,dict)
                    or set(review_camera)!={'eye','target','fov'}):
                raise SceneError('Inspection camera requires world v2 and exactly eye, target, fov')
            # load_plan returns an independent record. Validate a stationary view
            # without saving a revision or touching the presentation trajectory.
            plan['scene']['camera']=[dict(review_camera,at=0),dict(review_camera,at=plan['scene']['duration'])]
            plan['scene']=validate_scene(plan['scene'],set(plan['source_ids']))
        sources = self.sources(project_id, plan['source_ids'])
        embedded = [{**{k: v for k, v in s.items() if k != 'data'},
                     'url': f"data:{s['mime_type']};base64," + base64.b64encode(s['data']).decode('ascii')} for s in sources]
        content={'scene': plan['scene'], 'sources': embedded, 'model': plan.get('model', {})}
        if inspection:content.update(inspection_only=True,inspection_of=plan_id)
        if plan['scene']['schema_version']==2:
            from .worlds import compile_world
            content['programs']=compile_world(plan['scene'])
        payload = json.dumps(content, ensure_ascii=True, allow_nan=False)
        payload = payload.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
        template = (RUNTIME / 'player.html').read_text(encoding='utf-8')
        replacements = {'<!--TITLE-->': html.escape(plan['scene']['title']), '/*PAYLOAD*/': payload,
                        '/*SCENE_RUNTIME*/': (RUNTIME / 'scene.js').read_text(encoding='utf-8'),
                        '/*WORLD_RUNTIME*/': (RUNTIME / 'world.js').read_text(encoding='utf-8'),
                        '/*WEBM_RUNTIME*/': (RUNTIME / 'webm.js').read_text(encoding='utf-8'),
                        '/*PLAYER_RUNTIME*/': (RUNTIME / 'player.js').read_text(encoding='utf-8')}
        # One substitution pass: input can never become another template directive.
        document = re.sub('|'.join(map(re.escape, replacements)), lambda m: replacements[m[0]], template)
        filename=plan_id+('-inspection-'+uuid.uuid4().hex if inspection else '')+'.html'
        target = self.projects._project(project_id) / 'artifacts' / filename
        _no_links(target); _atomic(target, document.encode('utf-8'))
        return {'kind': 'generated', 'plan_id': plan_id, 'project_id': project_id,
                'plan_path': str(self.projects._project(project_id) / 'plans' / (plan_id + '.json')),
                'path': str(target), 'format': 'html', 'source_ids': plan['source_ids'],
                'sha256': hashlib.sha256(document.encode('utf-8')).hexdigest(),
                'inspection_only': inspection}
