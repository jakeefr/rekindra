"""Warn when a wide piece of scenery shows its end on camera.

Geometry is clamped to +/-100 per axis, so a backdrop can look finished in the plan and still stop
inside the frame. This walks the camera path and projects each wide surface's end edges exactly as
the runtime does. It is advice, never a rejection. Limits: nothing tests whether another object
hides the end, and lofted, assembled, rotated or multi-instance surfaces are not checked.
"""
import math

from .expressions import surface_sampler
from .scenes import SceneError

_LIMIT = 100.0
_WIDE = 40.0                # world units across before a surface counts as scenery
_GRID = 9
_EDGE_POINTS = 17
_PATH_SAMPLES = 12
_NEAR = .1
_FOG_FLOOR = .05            # below this much transmission the end has faded out
_ASPECT = 1280 / 720
_HORIZON_LIKE = 3.0         # an edge lying this flat on screen reads as a horizon, not an end
_MIN_ON_SCREEN = .02
_WORK_BUDGET = 4_000_000    # expression nodes, so the check stays cheap on any valid scene
_EDGES = (('u=0', lambda s: (0.0, s)), ('u=1', lambda s: (1.0, s)), ('v=0', lambda s: (s, 0.0)), ('v=1', lambda s: (s, 1.0)))


def _clamp(value):
    return max(min(value, _LIMIT), -_LIMIT)


def _unit(vector):
    length = math.sqrt(sum(part * part for part in vector))
    return [part / length for part in vector]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _dot(a, b):
    return sum(p * q for p, q in zip(a, b))


def _camera_at(keys, time):
    """Mirrors cameraAt in runtime/world.js."""
    if time <= keys[0]['at']:
        return keys[0]
    for before, key in zip(keys, keys[1:]):
        if time <= key['at']:
            if key.get('cut'):
                return before if time < key['at'] else key
            q = (time - before['at']) / (key['at'] - before['at'])
            s = q * q * (3 - 2 * q)
            mix = lambda a, b: a + (b - a) * s
            return {'eye': [mix(a, b) for a, b in zip(before['eye'], key['eye'])],
                    'target': [mix(a, b) for a, b in zip(before['target'], key['target'])],
                    'fov': mix(before['fov'], key['fov'])}
    return keys[-1]


def _view(camera):
    forward = _unit([a - b for a, b in zip(camera['target'], camera['eye'])])
    right = _unit(_cross(forward, [0, 0, 1] if abs(forward[1]) > .99 else [0, 1, 0]))
    return {'eye': camera['eye'], 'forward': forward, 'right': right, 'up': _unit(_cross(right, forward)),
            'tan': math.tan(camera['fov'] * math.pi / 360)}


def _in_frame(view, point, fog_density):
    """Screen position of a world point the camera can see through the fog, else None."""
    delta = [a - b for a, b in zip(point, view['eye'])]
    depth = _dot(delta, view['forward'])
    if depth <= _NEAR or math.exp(-math.sqrt(_dot(delta, delta)) * fog_density) <= _FOG_FLOOR:
        return None
    x = _dot(delta, view['right']) / (depth * view['tan'] * _ASPECT)
    y = _dot(delta, view['up']) / (depth * view['tan'])
    return (x, y) if abs(x) <= 1 and abs(y) <= 1 else None


def _placed(item):
    """f(u,v,t) giving world position after the runtime's clamps, or None for a surface not modeled here."""
    instances = item.get('instances')
    if 'loft' in item or 'feathers' in item or 'drape' in item or 'ring' in item or 'assembly' in item or (instances and (len(instances) > 1 or 'rotation' in instances[0])):
        return None
    place = instances[0] if instances else None
    position = item['position']
    sample = surface_sampler((position['x'], position['y'], position['z']), item.get('bindings', ()))

    def world(u, v, t):
        local = [_clamp(part) for part in sample(u, v, t)]
        return [_clamp(part * scale + offset) for part, scale, offset in zip(local, place['scale'], place['offset'])] if place else local
    world.cost = sample.cost
    return world


def _across(first, second):
    return math.hypot(first[0] - second[0], first[2] - second[2])


def _end_edges(world):
    """The edges that are ends of a wide surface. A surface that closes on itself has none along that axis."""
    grid = [world(i / (_GRID - 1), j / (_GRID - 1), 0.0) for i in range(_GRID) for j in range(_GRID)]
    width = max(max(p[axis] for p in grid) - min(p[axis] for p in grid) for axis in (0, 2))
    if width < _WIDE:
        return []
    along_u = max(_across(world(0.0, s, 0.0), world(1.0, s, 0.0)) for s in (0.0, .5, 1.0))
    along_v = max(_across(world(s, 0.0, 0.0), world(s, 1.0, 0.0)) for s in (0.0, .5, 1.0))
    return [edge for edge in _EDGES if (along_u if edge[0][0] == 'u' else along_v) >= _WIDE]


def _shows_end(edge, world, views, fog_density):
    """(time, world point) where the first camera sees this end, or None."""
    _, at = edge
    for time, view in views:
        points = [world(*at(index / (_EDGE_POINTS - 1)), time) for index in range(_EDGE_POINTS)]
        seen = [(point, screen) for point, screen in ((point, _in_frame(view, point, fog_density)) for point in points) if screen]
        if len(seen) < 2:
            continue
        across = (max(s[0] for _, s in seen) - min(s[0] for _, s in seen)) * _ASPECT
        high = max(s[1] for _, s in seen) - min(s[1] for _, s in seen)
        if max(across, high) >= _MIN_ON_SCREEN and across <= _HORIZON_LIKE * high:
            return time, seen[len(seen) // 2][0]
    return None


def backdrop_warnings(scene: dict) -> list:
    """One plain warning per wide surface whose end the camera path can see. Same scene, same warnings."""
    if scene.get('schema_version') != 2:
        return []
    keys = scene['camera']
    duration = scene['duration']
    times = sorted({round(index * duration / (_PATH_SAMPLES - 1), 6) for index in range(_PATH_SAMPLES)} | {key['at'] for key in keys})
    views = [(time, _view(_camera_at(keys, time))) for time in times]
    fog_density = scene['environment']['fog_density']
    warnings, spent = [], 0
    for item in scene['objects']:
        try:
            world = _placed(item)
            if world is None:
                continue
            spent += world.cost * (_GRID * _GRID + 4 * _EDGE_POINTS * len(views))
            if spent > _WORK_BUDGET:
                break
            ends = [(edge[0], found) for edge in _end_edges(world)
                    if (found := _shows_end(edge, world, views, fog_density))]
        except (SceneError, ArithmeticError, ValueError):
            continue
        if ends:
            name, (time, point) = min(ends, key=lambda end: (end[1][0], end[0]))
            where = ', '.join(f'{axis}={value:.0f}' for axis, value in zip('xyz', point))
            warnings.append(f"{item['id']}: its {name} end is in frame at t={time:.1f}s (near {where}), so the edge of the "
                            f'scenery shows. Geometry stops at +/-100 on each axis. Fix one: move it closer to the camera, '
                            f'widen it (up to +/-100), or aim the camera more head-on.')
    return warnings
