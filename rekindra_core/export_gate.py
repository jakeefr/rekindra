"""Binding review: only a clean or answered preview unlocks a video-capable world export."""
import json

from .backdrop import backdrop_warnings
from .compositions import CompositionStore
from .projects import ProjectError, _atomic, _no_links
from .scenes import SceneError

MAX_FLAGGED_CYCLES = 3
MIN_REASON = 10
MAX_REASON = 200
MAX_ACKNOWLEDGMENTS = 16
MAX_LINEAGE = 64
MAX_RECORD_BYTES = 512_000
_DRIFT_STATUSES = ('drift', 'ok', 'not_measured', 'unavailable')


class ExportBlocked(SceneError):
    """A refusal the agent can act on: it carries what must be answered."""

    def __init__(self, message, warnings=(), cycles=0):
        super().__init__(message)
        self.warnings = list(warnings)
        self.cycles = cycles


def _record_path(store, project_id, plan_id):
    path = store._project(project_id) / 'artifacts' / f'{plan_id}-preview-record.json'
    _no_links(path)
    return path


def _well_formed(drift):
    if not isinstance(drift, dict) or drift.get('status') not in _DRIFT_STATUSES:
        return False
    if drift['status'] != 'drift':
        return True
    rows = drift.get('regions')
    return isinstance(rows, list) and all(
        isinstance(row, dict) and isinstance(row.get('region'), str) and isinstance(row.get('flag'), str)
        and isinstance(row.get('over_threshold'), bool) for row in rows)


def _read_drift(store, project_id, plan_id):
    """The latest presentation preview's drift report, or None when there is no usable record."""
    path = _record_path(store, project_id, plan_id)
    try:
        if path.stat().st_size > MAX_RECORD_BYTES:
            return None
        record = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or record.get('plan_id') != plan_id or not _well_formed(record.get('palette_drift')):
        return None
    return record['palette_drift']


def current_warnings(plan, drift):
    found = []
    if drift['status'] == 'drift':
        found += [{'warning_id': 'palette:' + row['region'].replace(' ', '-'), 'kind': 'palette_drift',
                   'message': row['flag']} for row in drift['regions'] if row['over_threshold']]
    found += [{'warning_id': 'backdrop:' + text.split(':', 1)[0], 'kind': 'backdrop_edge', 'message': text}
              for text in backdrop_warnings(plan['scene'])]
    return found


def flagged_cycles(compositions, project_id, plan):
    """Revised plans in this plan's ancestry whose own preview still flagged; one count per plan."""
    count, seen, current = 0, set(), plan
    for _ in range(MAX_LINEAGE):
        model = current.get('model')
        if current['plan_id'] in seen or not isinstance(model, dict) or model.get('origin') != 'caller-revised':
            break
        seen.add(current['plan_id'])
        drift = _read_drift(compositions.projects, project_id, current['plan_id'])
        if drift is not None and current_warnings(current, drift):
            count += 1
        try:
            current = compositions.load_plan(project_id, model.get('parent_plan_id'))
        except (SceneError, ProjectError):
            break
    return count


def preview_gate(store, project_id, plan, drift, review_camera):
    """Remember a presentation preview of a world and say what export will ask of it."""
    if plan['scene']['schema_version'] != 2 or review_camera is not None:
        return None
    payload = json.dumps({'plan_id': plan['plan_id'], 'palette_drift': drift}, ensure_ascii=False, allow_nan=False)
    _atomic(_record_path(store, project_id, plan['plan_id']), payload.encode('utf-8'))
    cycles = flagged_cycles(CompositionStore(store), project_id, plan)
    return {'warnings': current_warnings(plan, drift), 'revise_preview_cycles': cycles,
            'cycle_cap': MAX_FLAGGED_CYCLES}


def _parsed(item):
    if not isinstance(item, dict) or set(item) != {'warning_id', 'reason'}:
        return None
    if not isinstance(item['warning_id'], str) or not isinstance(item['reason'], str):
        return None
    reason = ' '.join(item['reason'].split())
    return None if not MIN_REASON <= len(reason) <= MAX_REASON else {'warning_id': item['warning_id'], 'reason': reason}


def _refusal(warnings, cycles, problems=()):
    named = '; '.join(f"{w['warning_id']}: {w['message']}" for w in warnings)
    parts = [f'Export blocked by {len(warnings)} unresolved warning(s): {named}.']
    parts += [f'Override not accepted: {problem}.' for problem in problems]
    parts.append('Fix it: revise with rekindra_revise_world following each warning, run rekindra_preview on the new '
                 'plan, then rekindra_export that plan. If a warning is deliberate, call rekindra_export again with '
                 'acknowledgments [{warning_id, reason}] covering every warning, each reason '
                 f'{MIN_REASON} to {MAX_REASON} characters saying why.')
    parts.append(f'Flagged revise and preview cycles so far: {cycles} of {MAX_FLAGGED_CYCLES}; '
                 f'at {MAX_FLAGGED_CYCLES} export is allowed with the warnings recorded.')
    return ' '.join(parts)


def _matched(acknowledgments, warnings, cycles):
    """Every warning answered by exactly one well-formed reason, or a refusal naming what is wrong."""
    wanted = [w['warning_id'] for w in warnings]
    problems, answered = [], {}
    if acknowledgments is None:
        acknowledgments = []
    if not isinstance(acknowledgments, list) or len(acknowledgments) > MAX_ACKNOWLEDGMENTS:
        problems.append(f'acknowledgments must be a list of at most {MAX_ACKNOWLEDGMENTS} items')
        acknowledgments = []
    elif acknowledgments:
        for item in acknowledgments:
            parsed = _parsed(item)
            if parsed is None:
                problems.append('each item needs exactly warning_id and a reason of '
                                f'{MIN_REASON} to {MAX_REASON} characters')
            elif parsed['warning_id'] not in wanted:
                problems.append(f"{parsed['warning_id']} is not a current warning for this plan")
            elif parsed['warning_id'] in answered:
                problems.append(f"{parsed['warning_id']} was acknowledged twice")
            else:
                answered[parsed['warning_id']] = parsed
        if not problems and len(answered) < len(wanted):
            problems.append('not acknowledged: ' + ', '.join(i for i in wanted if i not in answered))
    if problems or len(answered) < len(wanted):
        raise ExportBlocked(_refusal(warnings, cycles, problems), warnings, cycles)
    return [answered[i] for i in wanted]


def _kept_on_cap(acknowledgments, wanted):
    """At the cap nothing can refuse; keep only reasons that actually answer a current warning."""
    kept = {}
    for item in acknowledgments if isinstance(acknowledgments, list) else []:
        parsed = _parsed(item)
        if parsed is not None and parsed['warning_id'] in wanted:
            kept.setdefault(parsed['warning_id'], parsed)
    return list(kept.values())[:MAX_ACKNOWLEDGMENTS]


_NEXT_STEP = {
    'clear': 'This HTML can save video. The preview raised no warnings; that is not visual acceptance.',
    'acknowledged': 'This HTML can save video. Tell the user which warnings you acknowledged and why.',
    'cycle_cap': 'Export is allowed because three revise and preview cycles still flagged. The warnings are '
                 'unresolved and recorded; tell the user what is still wrong.'}


def export_world(store, project_id, plan_id, acknowledgments=None):
    compositions = CompositionStore(store)
    plan = compositions.load_plan(project_id, plan_id)
    if plan['scene']['schema_version'] != 2:
        raise SceneError('rekindra_export is for worlds; a composition saves video from its own HTML.')
    drift = _read_drift(store, project_id, plan_id)
    if drift is None:
        raise ExportBlocked(f'Plan {plan_id} has no preview on record. Call rekindra_preview with this plan_id and '
                            'no review_camera, inspect it, then call rekindra_export.')
    warnings = current_warnings(plan, drift)
    cycles = flagged_cycles(compositions, project_id, plan)
    if not warnings:
        status, answered = 'clear', []
    elif cycles >= MAX_FLAGGED_CYCLES:
        status, answered = 'cycle_cap', _kept_on_cap(acknowledgments, {w['warning_id'] for w in warnings})
    else:
        status, answered = 'acknowledged', _matched(acknowledgments, warnings, cycles)
    provenance = {'status': status, 'warnings': warnings, 'acknowledgments': answered,
                  'revise_preview_cycles': cycles, 'cycle_cap': MAX_FLAGGED_CYCLES}
    artifact = compositions.build(project_id, plan_id, export_provenance=provenance)
    record = {**provenance, 'plan_id': plan_id, 'palette_drift': drift, 'html_sha256': artifact['sha256']}
    target = store._project(project_id) / 'artifacts' / f'{plan_id}-export.json'
    _no_links(target)
    _atomic(target, json.dumps(record, ensure_ascii=False, allow_nan=False, indent=2).encode('utf-8'))
    return {'kind': 'cleared-export', 'project_id': project_id, 'plan_id': plan_id, 'path': artifact['path'],
            'format': 'html', 'sha256': artifact['sha256'], 'provenance_path': str(target), 'status': status,
            'warnings': warnings, 'acknowledgments': answered, 'revise_preview_cycles': cycles,
            'next_step': _NEXT_STEP[status]}
