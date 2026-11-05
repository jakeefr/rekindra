"""Verified source selection, immutable plans, and portable artifact packaging."""
import base64
import hashlib
import html
import json
import re
from pathlib import Path
import struct
import uuid

from .projects import ProjectStore, ProjectError, _no_links, _atomic, _ID
from .scenes import validate_scene, SceneError

RUNTIME = Path(__file__).resolve().parents[1] / 'runtime'


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
        _atomic(directory / (plan_id + '.json'), json.dumps(record, ensure_ascii=False, allow_nan=False, indent=2).encode())
        return record

    def load_plan(self, project_id: str, plan_id: str) -> dict:
        if not isinstance(plan_id, str) or not _ID.fullmatch(plan_id): raise SceneError('Invalid plan identifier')
        path = self.projects._project(project_id) / 'plans' / (plan_id + '.json')
        _no_links(path)
        try:
            if path.stat().st_size > 100_000: raise SceneError('Plan exceeds size limit')
            record = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(record, dict) or record.get('project_id') != project_id or record.get('plan_id') != plan_id:
                raise SceneError('Malformed plan identity')
            sources = self.sources(project_id, record.get('source_ids'))
            record['scene'] = validate_scene(record.get('scene'), {s['asset_id'] for s in sources})
            expected = record.get('sources')
            actual = [{k: v for k, v in s.items() if k != 'data'} for s in sources]
            if expected != actual: raise SceneError('Plan source provenance has changed')
            return record
        except (OSError, json.JSONDecodeError) as exc:
            raise SceneError('Cannot load this scene plan') from exc

    def build(self, project_id: str, plan_id: str) -> dict:
        plan = self.load_plan(project_id, plan_id)
        sources = self.sources(project_id, plan['source_ids'])
        embedded = [{**{k: v for k, v in s.items() if k != 'data'},
                     'url': f"data:{s['mime_type']};base64," + base64.b64encode(s['data']).decode('ascii')} for s in sources]
        payload = json.dumps({'scene': plan['scene'], 'sources': embedded, 'model': plan.get('model', {})}, ensure_ascii=True, allow_nan=False)
        payload = payload.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
        template = (RUNTIME / 'player.html').read_text(encoding='utf-8')
        replacements = {'<!--TITLE-->': html.escape(plan['scene']['title']), '/*PAYLOAD*/': payload,
                        '/*SCENE_RUNTIME*/': (RUNTIME / 'scene.js').read_text(encoding='utf-8'),
                        '/*WEBM_RUNTIME*/': (RUNTIME / 'webm.js').read_text(encoding='utf-8'),
                        '/*PLAYER_RUNTIME*/': (RUNTIME / 'player.js').read_text(encoding='utf-8')}
        # One substitution pass: input can never become another template directive.
        document = re.sub('|'.join(map(re.escape, replacements)), lambda m: replacements[m[0]], template)
        target = self.projects._project(project_id) / 'artifacts' / (plan_id + '.html')
        _no_links(target); _atomic(target, document.encode('utf-8'))
        return {'kind': 'generated', 'plan_id': plan_id, 'project_id': project_id,
                'path': str(target), 'format': 'html', 'source_ids': plan['source_ids'],
                'sha256': hashlib.sha256(document.encode('utf-8')).hexdigest()}
