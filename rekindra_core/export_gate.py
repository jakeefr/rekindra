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
EMPTY_SPREAD = 8        # brightness range (0-255) below which a frame is one flat color
STILL_CHANGE = 0.25     # mean per-channel change (0-255) between sampled frames below which nothing moved
# Percent of a sampled frame that may be near-white (every channel at 190 of 255 or more, which takes in a
# bloom core and the washed halo round it). Previews that read well measure 0.4 or less; a frame that reads
# as one white bloom measured 4.0. Three sits well clear of the first and under the second.
BLOWN_SHARE = 3.0
# A sky or fog authored this pale fills the frame with near-white on purpose, so the share says nothing there.
PALE_BACKDROP = 170


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
        isinstance(row, dict) and isinstance(row.get('region'), str) and isinstance(row.get('over_threshold'), bool)
        and (not row['over_threshold'] or isinstance(row.get('flag'), str)) for row in rows)


def _read_record(store, project_id, plan_id):
    """The latest presentation preview's record, or None when there is no usable one."""
    path = _record_path(store, project_id, plan_id)
    try:
        if path.stat().st_size > MAX_RECORD_BYTES:
            return None
        record = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or record.get('plan_id') != plan_id or not _well_formed(record.get('palette_drift')):
        return None
    return record


def _read_drift(store, project_id, plan_id):
    record = _read_record(store, project_id, plan_id)
    return None if record is None else record['palette_drift']


def frame_warnings(frames):
    """A preview whose frames show nothing, or never change, is not a video worth saving."""
    try:
        spread, change = max(frames['spread']), max(frames['change'])
    except (TypeError, KeyError, ValueError):
        return []       # not measured: an older record, or the image reader was unavailable
    if not isinstance(spread, (int, float)) or not isinstance(change, (int, float)):
        return []
    found = []
    if spread < EMPTY_SPREAD:
        found.append({'warning_id': 'frames:empty', 'kind': 'empty_frames',
                      'message': 'Every sampled frame is close to one flat color, so the video would show nothing. '
                                 'Check that the camera faces the objects, that they are lit, and that fog or '
                                 'exposure is not hiding them.'})
    elif change < STILL_CHANGE:
        found.append({'warning_id': 'frames:motionless', 'kind': 'motionless_frames',
                      'message': 'The six sampled frames are almost identical, so the video would look like a '
                                 'still image. Move the camera along its path or animate something visible.'})
    return found + blown_out_warnings(frames)


def blown_out_warnings(frames):
    """A frame mostly washed to near-white by one light shows the light and nothing else."""
    white = frames.get('white') if isinstance(frames, dict) else None
    if (not isinstance(white, list) or not white
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in white)):
        return []       # not measured: a record written before this check existed
    worst = max(white)
    if worst <= BLOWN_SHARE:
        return []
    frame = white.index(worst) + 1
    return [{'warning_id': 'frames:blown_out', 'kind': 'blown_out_frames',
             'message': f'Sampled frame {frame} is {worst:g}% near-white (limit {BLOWN_SHARE:g}%): a light has '
                        'bloomed over the picture and hides the scene behind it. Lower the glow strength of the '
                        'emitter or the atmosphere bloom and halo, pull the camera back from it, or shrink the '
                        'emitter, then preview again. If the source image itself is this bright, acknowledge '
                        'the warning with that reason.'}]


def _pale_backdrop(scene):
    """True when the scene's own sky or fog is authored near-white: daylight, overcast, snow light."""
    environment = scene.get('environment') if isinstance(scene, dict) else None
    if not isinstance(environment, dict):
        return False
    for key in ('sky_top', 'sky_bottom', 'fog_color'):
        value = environment.get(key)
        if isinstance(value, str) and len(value) == 7 and value[0] == '#':
            try:
                if min(int(value[i:i + 2], 16) for i in (1, 3, 5)) >= PALE_BACKDROP:
                    return True
            except ValueError:
                pass
    return False


def current_warnings(plan, drift, frames=None):
    found = frame_warnings(frames)
    if _pale_backdrop(plan.get('scene')):
        found = [w for w in found if w['warning_id'] != 'frames:blown_out']
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
        record = _read_record(compositions.projects, project_id, current['plan_id'])
        if record is not None and current_warnings(current, record['palette_drift'], record.get('frames')):
            count += 1
        try:
            current = compositions.load_plan(project_id, model.get('parent_plan_id'))
        except (SceneError, ProjectError):
            break
    return count


def preview_gate(store, project_id, plan, drift, review_camera, frames=None):
    """Remember a presentation preview of a world and say what export will ask of it."""
    if plan['scene']['schema_version'] != 2 or review_camera is not None:
        return None
    record = {'plan_id': plan['plan_id'], 'palette_drift': drift}
    if frames is not None:
        record['frames'] = frames
    payload = json.dumps(record, ensure_ascii=False, allow_nan=False)
    _atomic(_record_path(store, project_id, plan['plan_id']), payload.encode('utf-8'))
    cycles = flagged_cycles(CompositionStore(store), project_id, plan)
    return {'warnings': current_warnings(plan, drift, frames), 'revise_preview_cycles': cycles,
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


def _brief(text):
    text = ''.join(c if c.isprintable() else '?' for c in text)
    return repr(text[:64] + ('...' if len(text) > 64 else ''))


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
        # One line per kind of fault, the current ids listed once: the refusal must stay well inside the host's result budget.
        malformed, stale, repeated = 0, [], []
        for item in acknowledgments:
            parsed = _parsed(item)
            if parsed is None:
                malformed += 1
            elif parsed['warning_id'] not in wanted:
                stale.append(_brief(parsed['warning_id']))
            elif parsed['warning_id'] in answered:
                repeated.append(parsed['warning_id'])
            else:
                answered[parsed['warning_id']] = parsed
        if malformed:
            problems.append(f'{malformed} item(s) malformed: each item needs exactly warning_id and a reason of '
                            f'{MIN_REASON} to {MAX_REASON} characters, shaped {{"warning_id": "...", "reason": "..."}} '
                            f'with warning_id copied from: {", ".join(wanted)}')
        if stale:
            problems.append(f"{', '.join(dict.fromkeys(stale))} {'is' if len(set(stale)) == 1 else 'are'} not a current warning "
                            f"for this plan (current: {', '.join(wanted)})")
        if repeated:
            problems.append(f"{', '.join(dict.fromkeys(repeated))} acknowledged more than once; send one item per warning")
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
    saved = _read_record(store, project_id, plan_id)
    if saved is None:
        raise ExportBlocked(f'Plan {plan_id} has no preview on record. Call rekindra_preview with this plan_id and '
                            'no review_camera, inspect it, then call rekindra_export. Only rekindra_preview can '
                            'make that record, never write one another way; if its error says to stop, stop '
                            'and tell the user.')
    drift = saved['palette_drift']
    warnings = current_warnings(plan, drift, saved.get('frames'))
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
