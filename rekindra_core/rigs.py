"""Poseable figure rigs: a small skeleton solved once, for people, statues and creatures.

A rig is an optional scene entry. It draws nothing by itself: the figure construction field puts soft
body masses on its bones, and mount places any other surface on one of its attachment points.
"""
import math
from .scenes import SceneError, _number, _LAYER_ID

MAX_RIGS = 4
JOINTS = ('spine', 'neck', 'shoulder_left', 'shoulder_right', 'elbow_left', 'elbow_right',
          'hip_left', 'hip_right', 'knee_left', 'knee_right')
ANCHORS = ('head_top', 'neck', 'shoulders', 'shoulder_left', 'shoulder_right', 'chest', 'back', 'hips',
           'hand_left', 'hand_right')
PARTS = ('head', 'torso', 'arms', 'legs')
PROPORTIONS = ('head', 'neck', 'torso', 'arms', 'legs', 'build')
# Each preset sets [forward, outward, twist] radians on some joints; later presets and joints override earlier ones.
POSES = {
    'standing': {'shoulder': (0, .12, 0)},
    'kneeling': {'hip': (.55, .06, 0), 'knee': (2.1, 0, 0), 'spine': (.08, 0, 0), 'shoulder': (0, .12, 0)},
    'sitting': {'hip': (1.5, .08, 0), 'knee': (1.5, 0, 0), 'shoulder': (0, .12, 0)},
    'arms_raised': {'shoulder': (.15, 2.5, 0), 'elbow': (.35, 0, 0)},
    'arms_at_chest': {'shoulder': (.75, .05, 1.15), 'elbow': (2., 0, 0)},
    'arms_out': {'shoulder': (0, 1.45, 0)},
}
SEATED = ('kneeling', 'sitting')
BONES = {'head': 2, 'torso': 2, 'arms': 6, 'legs': 6}


def _rx(a):
    c, s = math.cos(a), math.sin(a)
    return ((1, 0, 0), (0, c, -s), (0, s, c))


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return ((c, 0, s), (0, 1, 0), (-s, 0, c))


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return ((c, -s, 0), (s, c, 0), (0, 0, 1))


def _mul(a, *rest):
    for b in rest:
        a = tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))
    return a


def _apply(m, v):
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))


def _add(a, b, scale=1.):
    return tuple(x + scale * y for x, y in zip(a, b))


def _unit(v, fallback=(1., 0., 0.)):
    n = math.sqrt(sum(x * x for x in v))
    return tuple(x / n for x in v) if n > 1e-9 else fallback


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _pose(spec):
    pose = spec.get('pose', 'standing')
    names = [pose] if isinstance(pose, str) else pose
    if not isinstance(names, list) or not 1 <= len(names) <= 4 or any(not isinstance(n, str) or n not in POSES for n in names):
        raise SceneError(f'Rig pose is one preset or a list of up to four, applied in order: {", ".join(POSES)}; got {str(pose)[:60]}')
    angles = {joint: [0., 0., 0.] for joint in JOINTS}
    for name in names:
        for joint, value in POSES[name].items():
            for target in ([joint] if joint in angles else [joint + '_left', joint + '_right']):
                angles[target] = list(value)
    joints = spec.get('joints', {})
    if not isinstance(joints, dict) or any(j not in JOINTS for j in joints):
        raise SceneError(f'Rig joints is an object of joint name to [forward, outward, twist] radians. Joints: {", ".join(JOINTS)}')
    for joint, value in joints.items():
        if not isinstance(value, list) or len(value) != 3:
            raise SceneError(f'Rig joint {joint} needs [forward, outward, twist] in radians; elbows and knees use only the first')
        for x in value:
            _number(x, -math.pi, math.pi, 'rig joint angle')
        angles[joint] = [float(x) for x in value]
    return names, angles


def solve_rig(spec, eye=None):
    """Joint positions, bones and attachment points of one rig in world coordinates."""
    if not isinstance(spec, dict) or not {'id', 'position', 'height'} <= set(spec) <= {'id', 'position', 'height', 'facing', 'pose', 'joints', 'proportions'}:
        raise SceneError('Invalid rig fields. Required: id, position, height. Optional: facing, pose, joints, proportions')
    if not isinstance(spec['id'], str) or not _LAYER_ID.fullmatch(spec['id']):
        raise SceneError('Rig id must be 1-40 letters, digits, underscore or hyphen')
    origin = spec['position']
    if not isinstance(origin, list) or len(origin) != 3:
        raise SceneError('Rig position is the ground point under the figure: [x, y, z]')
    for x in origin:
        _number(x, -80, 80, 'rig position')
    height = spec['height']; _number(height, .2, 20, 'rig height')
    facing = spec.get('facing', 0); _number(facing, -2 * math.pi, 2 * math.pi, 'rig facing')
    scale = dict.fromkeys(PROPORTIONS, 1.)
    given = spec.get('proportions', {})
    if not isinstance(given, dict) or any(k not in PROPORTIONS for k in given):
        raise SceneError(f'Rig proportions is an object of multipliers (0.4-2.5, default 1) for: {", ".join(PROPORTIONS)}')
    for key, value in given.items():
        _number(value, .4, 2.5, 'rig proportion ' + key); scale[key] = float(value)
    names, angle = _pose(spec)
    h, build = float(height), scale['build']
    up, down = (0., 1., 0.), (0., -1., 0.)
    spine = _mul(_rz(angle['spine'][1]), _rx(angle['spine'][0]), _ry(angle['spine'][2]))
    head_turn = _mul(spine, _rz(angle['neck'][1]), _rx(angle['neck'][0]), _ry(angle['neck'][2]))
    pelvis = (0., 0., 0.)
    torso = .29 * scale['torso'] * h
    neck_base = _apply(spine, (0, torso, 0))
    head_radius = .058 * scale['head'] * h
    head_centre = _add(neck_base, _apply(head_turn, up), .05 * scale['neck'] * h + head_radius + .008 * h)
    bones = []

    def bone(group, a, b, ra, rb, wide=None, flat=1.):
        bones.append({'group': group, 'a': a, 'b': b, 'ra': ra * h, 'rb': rb * h, 'wide': wide, 'flat': flat})

    right = _apply(spine, (1, 0, 0))
    bone('head', neck_base, head_centre, .03 * build, .028 * build)
    bone('head', _add(head_centre, _apply(head_turn, up), -.012 * scale['head'] * h),
         _add(head_centre, _apply(head_turn, up), .012 * scale['head'] * h), .058 * scale['head'], .058 * scale['head'])
    bone('torso', pelvis, _apply(spine, (0, .21 * scale['torso'] * h, 0)), .082 * build, .1 * build, right, .62)
    joints = {'pelvis': pelvis, 'neck': neck_base, 'head': head_centre}
    for side, sign in (('left', -1.), ('right', 1.)):
        shoulder = _apply(spine, (sign * .115 * build * h, .27 * scale['torso'] * h, 0))
        s = angle['shoulder_' + side]
        arm = _mul(spine, _rz(sign * s[1]), _rx(-s[0]), _ry(-sign * s[2]))
        elbow = _add(shoulder, _apply(arm, down), .16 * scale['arms'] * h)
        fore = _mul(arm, _rx(-angle['elbow_' + side][0]))
        wrist = _add(elbow, _apply(fore, down), .15 * scale['arms'] * h)
        hand = _add(wrist, _apply(fore, down), .05 * scale['arms'] * h)
        joints.update({'shoulder_' + side: shoulder, 'elbow_' + side: elbow, 'hand_' + side: hand})
        bone('arms', shoulder, elbow, .034 * build, .029 * build)
        bone('arms', elbow, wrist, .028 * build, .021 * build)
        bone('arms', wrist, hand, .021 * build, .017 * build)
        hip = (sign * .055 * build * h, -.01 * h, 0.)
        g = angle['hip_' + side]
        thigh = _mul(_rz(sign * g[1]), _rx(-g[0]), _ry(-sign * g[2]))
        knee = _add(hip, _apply(thigh, down), .245 * scale['legs'] * h)
        shin = _mul(thigh, _rx(angle['knee_' + side][0]))
        ankle = _add(knee, _apply(shin, down), .245 * scale['legs'] * h)
        # The foot runs forward from an upright shin and continues a shin that lies along the ground.
        along, ahead = _apply(shin, down), _apply(shin, (0, 0, 1))
        toe = _add(ankle, _unit(tuple(abs(along[1]) * f + (1 - abs(along[1])) * d for f, d in zip(ahead, along))),
                   .07 * scale['legs'] * h)
        joints.update({'hip_' + side: hip, 'knee_' + side: knee, 'ankle_' + side: ankle})
        bone('legs', hip, knee, .056 * build, .042 * build)
        bone('legs', knee, ankle, .04 * build, .027 * build)
        bone('legs', ankle, toe, .027 * build, .02 * build)
    bones.insert(3, {'group': 'torso', 'a': joints['shoulder_left'], 'b': joints['shoulder_right'],
                     'ra': .046 * build * h, 'rb': .046 * build * h, 'wide': None, 'flat': 1.})
    # The lowest body mass rests on the rig's ground point, whatever the pose.
    low = min(min(b['a'][1] - b['ra'], b['b'][1] - b['rb']) for b in bones)
    turn = _ry(facing)

    def world(p):
        q = _apply(turn, (p[0], p[1] - low, p[2]))
        return (q[0] + origin[0], q[1] + origin[1], q[2] + origin[2])

    local = {
        'head_top': _add(head_centre, _apply(head_turn, up), head_radius + .012 * scale['head'] * h),
        'neck': neck_base, 'hips': pelvis,
        'shoulders': _apply(spine, (0, .27 * scale['torso'] * h, 0)),
        'shoulder_left': joints['shoulder_left'], 'shoulder_right': joints['shoulder_right'],
        'chest': _apply(spine, (0, .2 * scale['torso'] * h, .066 * build * h)),
        'back': _apply(spine, (0, .22 * scale['torso'] * h, -.07 * build * h)),
        'hand_left': joints['hand_left'], 'hand_right': joints['hand_right'],
    }
    solved = []
    for b in bones:
        a, c = world(b['a']), world(b['b'])
        axis = _unit(tuple(y - x for x, y in zip(a, c)), (0., 1., 0.))
        if b['wide'] is not None:
            # A flattened mass keeps its wide axis; its seam sits on the side.
            wide = _apply(turn, b['wide'])
            along = sum(x * y for x, y in zip(wide, axis))
            x_axis = _unit(tuple(x - along * y for x, y in zip(wide, axis)))
            y_axis, sx, sy = _cross(axis, x_axis), 1., b['flat']
        else:
            # A round mass turns its seam away from the first camera position.
            middle = tuple((x + y) / 2 for x, y in zip(a, c))
            away = tuple(m - e for m, e in zip(middle, eye)) if eye else (0., 0., -1.)
            along = sum(x * y for x, y in zip(away, axis))
            x_axis = _unit(tuple(x - along * y for x, y in zip(away, axis)), _unit(_cross(axis, (.3, .5, .8))))
            y_axis, sx, sy = _cross(axis, x_axis), 1., 1.
        solved.append({'group': b['group'], 'a': a, 'd': tuple(y - x for x, y in zip(a, c)), 'axis': axis,
                       'x': tuple(v * sx for v in x_axis), 'y': tuple(v * sy for v in y_axis), 'ra': b['ra'], 'rb': b['rb']})
    return {'id': spec['id'], 'bones': solved, 'anchors': {k: world(v) for k, v in local.items()},
            'turn': turn, 'ground': float(origin[1]), 'seated': any(n in SEATED for n in names), 'height': h}


def solve_rigs(specs, eye=None):
    if not isinstance(specs, list) or not 1 <= len(specs) <= MAX_RIGS:
        raise SceneError(f'rigs is a list of 1-{MAX_RIGS} figure rigs; omit it when the scene has no posed figure')
    rigs = {}
    for spec in specs:
        rig = solve_rig(spec, eye)
        if rig['id'] in rigs:
            raise SceneError(f'Rig ids must be unique: {rig["id"]} appears twice')
        rigs[rig['id']] = rig
    return rigs


def rig_context(scene):
    """What rig-aware fields need: the solved rigs and the first camera position."""
    if 'rigs' not in scene:
        return None
    eye = scene['camera'][0]['eye']
    return {'rigs': solve_rigs(scene['rigs'], eye), 'eye': eye}


def resolve_mount(obj, context):
    """Where a mounted surface sits: an origin on the rig and the turn applied to its own coordinates."""
    spec = obj['mount']
    if not isinstance(spec, dict) or not {'rig', 'anchor'} <= set(spec) <= {'rig', 'anchor', 'face_camera'}:
        raise SceneError('Invalid mount fields. Required: rig, anchor. Optional: face_camera')
    rigs = (context or {}).get('rigs') or {}
    if not isinstance(spec['rig'], str) or spec['rig'] not in rigs:
        raise SceneError(f'mount rig must name a rig in scene.rigs: got {str(spec["rig"])[:40]!r}; scene.rigs defines '
                         + (', '.join(sorted(rigs)) if rigs else 'none, so add a rig there first'))
    if any(k in obj for k in ('figure', 'reflection')):
        raise SceneError('mount places a separate part on a rig: it cannot be combined with figure or reflection')
    rig = rigs[spec['rig']]
    if not isinstance(spec['anchor'], str) or spec['anchor'] not in rig['anchors']:
        raise SceneError(f'mount anchor must be one of: {", ".join(ANCHORS)}; got {str(spec["anchor"])[:40]!r}')
    anchor = rig['anchors'][spec['anchor']]
    face = spec.get('face_camera', .6 if 'ring' in obj else 0)
    _number(face, 0, 1, 'mount face_camera')
    matrix, origin = rig['turn'], anchor
    if 'drape' in obj:
        # Cloth hangs from the anchor: its own origin is the ground point below.
        origin = (anchor[0], rig['ground'], anchor[2])
    elif face and context.get('eye'):
        to_eye = _unit(tuple(e - a for e, a in zip(context['eye'], anchor)), (0., 0., 1.))
        k = _unit((to_eye[2], 0., -to_eye[0]), (1., 0., 0.))
        angle = face * math.acos(max(-1., min(1., to_eye[1])))
        c, s = math.cos(angle), math.sin(angle)
        cross = ((0, -k[2], k[1]), (k[2], 0, -k[0]), (-k[1], k[0], 0))
        tilt = tuple(tuple(c * (i == j) + s * cross[i][j] + (1 - c) * k[i] * k[j] for j in range(3)) for i in range(3))
        matrix = _mul(tilt, matrix)
    return {'origin': origin, 'matrix': matrix, 'drop': anchor[1] - rig['ground'], 'seated': rig['seated']}
