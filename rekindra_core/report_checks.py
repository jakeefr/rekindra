"""Preview checks that read the plan and its measurements: object motion, haze against the sources, and
small surfaces the camera path runs into. Same inputs, same report; nothing here renders.
"""
import ast
import math

from .backdrop import _ASPECT, _camera_at, _clamp, _dot, _view
from .expressions import surface_sampler
from .palette_drift import _lab

# Mean per-channel change (0-255) between a frozen-camera frame and the same view at another time,
# below which no object visibly moved. The renderer is deterministic with grain off, so a scene with
# nothing animated measures 0; one gently swaying leaf in view measures well above this.
OBJECT_STILL = 0.1
# Source mist: 0 for a crisp, contrasty or colourful photo, 1 for one flat pale grey veil.
MISTY_SOURCE = 0.45
# Scene haze: share of the light from the camera's subject distance that fog and haze replace.
THIN_HAZE = 0.3
_HAZE_DISTANCE = (5.0, 60.0)
# A surface counts as small up to this bounding-box diagonal (metres); smaller than this floor is a speck.
SMALL_OBJECT = 1.5
_SPECK = 0.02
# The camera runs into a small surface when its eye comes nearer than this share of the surface's size:
# the surface then fills more than the frame and shows as a detached shard rather than as itself.
_GRAZE_SHARE = 0.5
_SAMPLES_PER_SECOND = 4
_GRID = 7
_WORK_BUDGET = 4_000_000
_MAX_INSTANCE_CHECKS = 400_000
PREVIEW_FRAMES = 6
# Share of the frame height a posed figure should reach in the last third of the preview frames. 0.3 is a
# medium-wide shot: a kneeling figure with raised wings still fits the 16:9 frame. The demo-1 rehearsal, whose
# ending read as a small figure in a large room, measured 0.126 and 0.151 in its last two frames.
FOCAL_SHARE = 0.3
_EXPRESSION_FIELDS = ('color_mix', 'color_detail', 'bump_detail', 'color_pattern')
_UNMODELED = ('loft', 'feathers', 'drape', 'ring', 'assembly')


def _mentions_time(source):
    try:
        tree = ast.parse(source, mode='eval')
    except (SyntaxError, ValueError):
        return False
    return any(isinstance(node, ast.Name) and node.id == 't' for node in ast.walk(tree))


def uses_time(scene):
    """True when any surface expression depends on time, so something is meant to move or change."""
    for item in scene.get('objects') or []:
        if not isinstance(item, dict):
            continue
        sources = list((item.get('position') or {}).values()) if isinstance(item.get('position'), dict) else []
        sources += [b.get('expression') for b in item.get('bindings') or [] if isinstance(b, dict)]
        sources += [item.get(field) for field in _EXPRESSION_FIELDS]
        if any(isinstance(source, str) and _mentions_time(source) for source in sources):
            return True
    return False


def _measured(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def object_motion_report(value):
    """What the frozen-camera measurement says, in plain words. None when it was not measured."""
    if not _measured(value):
        return None
    moves = value >= OBJECT_STILL
    return {'value': round(value, 3), 'threshold': OBJECT_STILL, 'objects_move': moves,
            'statement': ('objects move or change on their own between frames' if moves
                          else 'objects do not move on their own; only the camera moves')}


def object_motion_warnings(scene, value):
    """The plan animates with t, yet with the camera held still nothing in view changes."""
    if not _measured(value) or value >= OBJECT_STILL or not uses_time(scene):
        return []
    return [{'warning_id': 'frames:objects_still', 'kind': 'objects_still',
             'message': f'The plan uses time (t) in surface expressions, but with the camera held still the '
                        f'frames change by only {value:g} (limit {OBJECT_STILL:g}): objects do not move on their '
                        'own; only the camera moves. Make the animated term large enough to see from the camera, '
                        'or put the animated surface in view. This is reported, not an export warning.'}]


def source_mist(palettes):
    """0..1, how much the misty-est source reads as one pale, low-contrast, colourless veil. None without palettes."""
    best = None
    for palette in palettes or []:
        entries = [e for e in palette if isinstance(e, dict) and isinstance(e.get('hex'), str)
                   and _measured(e.get('coverage')) and e['coverage'] > 0]
        if not entries:
            continue
        total = sum(e['coverage'] for e in entries)
        labs = [(_lab(e['hex']), e['coverage'] / total) for e in entries]
        chroma = sum(math.hypot(lab[1], lab[2]) * w for lab, w in labs)
        lightness = sum(lab[0] * w for lab, w in labs)
        spread = max(lab[0] for lab, _ in labs) - min(lab[0] for lab, _ in labs)
        grey = 1 - min(1.0, chroma / 40)
        flat = 1 - min(1.0, spread / 100)
        pale = max(0.0, min(1.0, (lightness - 35) / 40))
        mist = grey * flat * pale
        best = mist if best is None else max(best, mist)
    return None if best is None else round(best, 2)


def scene_haze(scene):
    """0..1, the share of light from the camera's subject distance that the scene's fog and haze replace."""
    environment = scene.get('environment') if isinstance(scene.get('environment'), dict) else {}
    atmosphere = environment.get('atmosphere') if isinstance(environment.get('atmosphere'), dict) else {}
    density = sum(v for v in (environment.get('fog_density'), atmosphere.get('haze_density')) if _measured(v))
    keys = scene.get('camera') or []
    distances = [math.dist(k['eye'], k['target']) for k in keys if isinstance(k, dict) and 'eye' in k and 'target' in k]
    distance = sum(distances) / len(distances) if distances else _HAZE_DISTANCE[0]
    distance = max(_HAZE_DISTANCE[0], min(_HAZE_DISTANCE[1], distance))
    return round(1 - math.exp(-max(0.0, density) * distance), 2)


def haze_report(scene, mist):
    if not _measured(mist):
        return None
    haze = scene_haze(scene)
    return {'source_mist': mist, 'scene_haze': haze,
            'verdict': 'too_thin' if mist >= MISTY_SOURCE and haze < THIN_HAZE else 'ok'}


def haze_warnings(scene, mist):
    report = haze_report(scene, mist)
    if report is None or report['verdict'] != 'too_thin':
        return []
    return [{'warning_id': 'frames:haze_thin', 'kind': 'haze_thin',
             'message': f"The sources read as misty (source mist {report['source_mist']:g} of 1) but the scene's "
                        f"fog and haze veil only {report['scene_haze']:g} of the light from the subject distance "
                        f'(want {THIN_HAZE:g} or more). Raise environment.fog_density or atmosphere.haze_density '
                        'with a haze_color taken from the source, or acknowledge that the scene is meant to be clearer.'}]


def _frame_height(view, points):
    """Share of the frame height spanned by the points inside the frame's width, clipped to its height.

    0 when none is in front of the camera and between the left and right edges: a figure the camera looks
    past is not framed."""
    rows = []
    for point in points:
        delta = [p - e for p, e in zip(point, view['eye'])]
        depth = _dot(delta, view['forward'])
        if depth > 1e-6 and abs(_dot(delta, view['right']) / (depth * view['tan'] * _ASPECT)) <= 1:
            rows.append(max(-1.0, min(1.0, _dot(delta, view['up']) / (depth * view['tan']))))
    return (max(rows) - min(rows)) / 2 if rows else 0.0


def _rig_points(rig):
    points = []
    for bone in rig['bones']:
        end = [a + d for a, d in zip(bone['a'], bone['d'])]
        for centre, radius in ((bone['a'], bone['ra']), (end, bone['rb'])):
            points += [[c + s * radius * (i == axis) for i, c in enumerate(centre)]
                       for axis in range(3) for s in (-1, 1)]
    return points


def focal_framing(scene):
    """How tall the posed figure stands in the last third of the preview frames. None without a rig or camera."""
    keys = scene.get('camera') or []
    duration = scene.get('duration')
    if not keys or not _measured(duration) or duration <= 0 or not scene.get('rigs'):
        return None
    try:
        from .rigs import rig_context
        rigs = (rig_context(scene) or {}).get('rigs') or {}
    except Exception:       # a rig this check cannot solve is refused by validation, not here
        return None
    if not rigs:
        return None
    times = [(i + .5) * duration / PREVIEW_FRAMES for i in range(PREVIEW_FRAMES - PREVIEW_FRAMES // 3, PREVIEW_FRAMES)]
    views = [_view(_camera_at(keys, time)) for time in times]
    # The figure the ending looks at: the one that stands tallest in those frames.
    name, shares = max(((name, [_frame_height(view, _rig_points(rig)) for view in views]) for name, rig in sorted(rigs.items())),
                       key=lambda row: max(row[1]))
    return {'subject': name, 'times_seconds': [round(t, 3) for t in times],
            'frame_height_share': [round(s, 3) for s in shares], 'threshold': FOCAL_SHARE,
            'verdict': 'small' if max(shares) < FOCAL_SHARE else 'ok'}


def focal_framing_warnings(scene, report=None):
    """The figure the scene is about ends up small in frame. Reported, not an export warning."""
    report = focal_framing(scene) if report is None else report
    if report is None or report['verdict'] != 'small':
        return []
    best = max(report['frame_height_share'])
    closer = f' (about {FOCAL_SHARE / best:.1f} times closer at the same fov)' if best > 0 else ''
    return [{'warning_id': 'frames:subject_small', 'kind': 'subject_small',
             'message': f"Figure {report['subject']} stands at most {best:.0%} of the frame height in the last third of "
                        f'the preview frames (want {FOCAL_SHARE:.0%} or more), so the ending shows mostly setting. Move '
                        f'the final camera keys closer to the figure{closer}, lower their fov, and aim their target '
                        'at mid-body. This is reported, not an export warning.'}]


def _rotate(point, angles):
    """Mirrors the runtime instance rotation: about X, then Y, then Z."""
    cx, cy, cz = (math.cos(a) for a in angles)
    sx, sy, sz = (math.sin(a) for a in angles)
    x, y, z = point
    y, z = cx * y - sx * z, sx * y + cx * z
    x, z = cy * x + sy * z, -sy * x + cy * z
    x, y = cz * x - sz * y, sz * x + cz * y
    return x, y, z


def _box(points):
    return [min(p[i] for p in points) for i in range(3)], [max(p[i] for p in points) for i in range(3)]


def _placed_box(local, place):
    lo, hi = local
    corners = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    scale, offset = place.get('scale', [1, 1, 1]), place.get('offset', [0, 0, 0])
    angles = place.get('rotation') or [0, 0, 0]
    moved = [[_clamp(a + b) for a, b in zip(_rotate([c * s for c, s in zip(corner, scale)], angles), offset)]
             for corner in corners]
    return _box(moved)


def _gap(eye, box):
    lo, hi = box
    return math.sqrt(sum(max(0.0, lo[i] - eye[i], eye[i] - hi[i]) ** 2 for i in range(3)))


def _times(scene):
    duration = scene.get('duration') if _measured(scene.get('duration')) else 0
    count = max(1, int(duration * _SAMPLES_PER_SECOND))
    times = {round(duration * i / count, 4) for i in range(count + 1)}
    times |= {k['at'] for k in scene.get('camera') or [] if isinstance(k, dict) and _measured(k.get('at'))}
    return sorted(t for t in times if 0 <= t <= duration)


def camera_graze_warnings(scene):
    """One warning per small surface the camera path flies into, named by object id. Same scene, same warnings."""
    keys = scene.get('camera') or []
    if not keys:
        return []
    times = _times(scene)
    views = [(t, _view(_camera_at(keys, t))) for t in times]
    found, work, checks = [], 0, 0
    for item in scene.get('objects') or []:
        if not isinstance(item, dict) or any(k in item for k in _UNMODELED) or not isinstance(item.get('position'), dict):
            continue
        try:
            position = item['position']
            sample = surface_sampler((position['x'], position['y'], position['z']), item.get('bindings', ()))
        except Exception:       # a surface this check cannot model is left to the other checks
            continue
        work += sample.cost * _GRID * _GRID * len(times)
        places = item.get('instances') or [{}]
        checks += len(places) * len(times)
        if work > _WORK_BUDGET or checks > _MAX_INSTANCE_CHECKS:
            break
        hit = None
        for time, view in views:
            try:
                local = _box([[_clamp(p) for p in sample(i / (_GRID - 1), j / (_GRID - 1), time)]
                              for i in range(_GRID) for j in range(_GRID)])
            except (ArithmeticError, ValueError, TypeError):
                break
            for index, place in enumerate(places):
                box = _placed_box(local, place)
                size = math.dist(box[0], box[1])
                if not _SPECK <= size <= SMALL_OBJECT:
                    continue
                gap = _gap(view['eye'], box)
                centre = [(a + b) / 2 for a, b in zip(*box)]
                ahead = _dot([c - e for c, e in zip(centre, view['eye'])], view['forward']) > 0
                if gap < _GRAZE_SHARE * size and (ahead or gap == 0) and (hit is None or gap < hit[2]):
                    hit = (time, index, gap, size)
            if hit is not None and hit[2] == 0:
                break
        if hit is not None:
            time, index, gap, size = hit
            which = f' instance {index}' if len(places) > 1 else ''
            found.append({'warning_id': f"fragment:{item.get('id')}", 'kind': 'camera_graze',
                          'message': f"Surface {item.get('id')}{which} ({size:.2f} m across) comes within "
                                     f'{gap:.2f} m of the camera eye at {time:g} s, so it fills the frame as a '
                                     'detached shard instead of reading as itself. Move it off the camera path, '
                                     'move the camera keys away from it, or shrink its animated sway.'})
    return found
