"""Construction fields: parametric part builders compiled to original shader math.

Each optional surface field supplies coordinates to the position expressions, the way loft does:
feathers -> feather_x/y/z, drape -> drape_x/y/z, ring -> ring_x/y/z, figure -> figure_x/y/z,
wing -> wing_x/y/z. Absent by default.
"""
import math
from .scenes import SceneError, _number
from .expressions import compile_expression
from .rigs import PARTS

CONSTRUCTS = ('feathers', 'drape', 'ring', 'figure', 'wing')


def _fields(value, required, optional, label):
    if not isinstance(value, dict) or not set(required) <= set(value) <= set(required) | set(optional):
        raise SceneError(f'Invalid {label} fields. Required: {", ".join(required)}. Optional: {", ".join(optional)}')


def _f(n):
    return format(float(n), '.9f')


def _feathers(spec, segments, context=None):
    _fields(spec, ('count', 'spread', 'length'), ('curve', 'fan', 'taper', 'overlap', 'layer', 'open', 'mirror'), 'feathers')
    count = spec['count']
    _number(count, 2, 48, 'feathers count', True)
    _number(spec['spread'], .05, 40, 'feathers spread')
    _number(spec['length'], .02, 40, 'feathers length')
    curve = spec.get('curve', 0); _number(curve, -math.pi, math.pi, 'feathers curve')
    fan = spec.get('fan', 0); _number(fan, -2 * math.pi, 2 * math.pi, 'feathers fan')
    taper = spec.get('taper', 1); _number(taper, .1, 4, 'feathers taper')
    overlap = spec.get('overlap', .5); _number(overlap, 0, 1, 'feathers overlap')
    layer = spec.get('layer', .05); _number(layer, 0, 2, 'feathers layer')
    mirror = spec.get('mirror', False)
    if type(mirror) is not bool:
        raise SceneError('feathers mirror must be true or false')
    across = segments[0] // count if isinstance(segments, list) and segments and isinstance(segments[0], int) else 0
    if across < 2 or segments[0] % count:
        raise SceneError(f'feathers needs u segments to be a multiple of count with at least 2 per feather: with count {count} '
                         f'use u segments {count * 2}, {count * 3} or {count * 4} (u limit 128)')
    opened = compile_expression(spec.get('open', '1'), {})
    width = spec['spread'] / count * (1 + 2 * overlap)
    code = [
        f'float rk_fu=clamp(u,0.,.999999)*{count}.;',
        'float rk_fi=floor(rk_fu);',
        # The last cell of each feather bridges to the next one, so every card keeps its full width.
        f'float rk_ff=min((rk_fu-rk_fi)*{_f(across / (across - 1))},1.);',
        f'float rk_fs=rk_fi/{count - 1}.;',
        f'float rk_fo=clamp({opened["glsl"]},0.,1.);',
        f'float rk_fa={_f(curve)}*rk_fs*rk_fo;',
        f'vec2 rk_fp={_f(spec["spread"])}*(.3+.7*rk_fo)*rk_fs*vec2(cos(rk_fa*.5),sin(rk_fa*.5));',
        f'float rk_fd=-1.5707963+{_f(fan)}*rk_fs*rk_fo+rk_fa;',
        f'float rk_fl={_f(spec["length"])}*mix(1.,{_f(taper)},rk_fs)*clamp(v,0.,1.);',
        f'float rk_fw={_f(width)}*mix(1.,{_f(taper)},rk_fs*.5)*(.15+.85*sin(3.14159265*sqrt(clamp(v,0.,1.))))*(rk_ff-.5);',
        'vec2 rk_fq=rk_fp+rk_fl*vec2(cos(rk_fd),sin(rk_fd))+rk_fw*vec2(-sin(rk_fd),cos(rk_fd));',
        f'vec3 rk_feather_p=vec3({"-" if mirror else ""}rk_fq.x,rk_fq.y,'
        f'{_f(layer)}*(fract(rk_fi*.618034)-.5+(rk_ff-.5)*(rk_ff-.5)));',
    ]
    return {'definitions': '\n'.join(code), 'cost': 140 + opened['cost'],
            'names': {'feather_x': 'rk_feather_p.x', 'feather_y': 'rk_feather_p.y', 'feather_z': 'rk_feather_p.z'}}


def _drape(spec, segments, context=None):
    mount = (context or {}).get('mount')
    if mount and isinstance(spec, dict):
        # Mounted cloth hangs from the attachment point to the rig's ground, and pools under a seated pose.
        spec = dict(spec, height=max(mount['drop'], .1))
        if mount['seated'] and 'pool' not in spec and isinstance(spec.get('hem_radius'), (int, float)):
            spec['pool'] = min(.6 * spec['hem_radius'], 10)
            spec.setdefault('ripples', 3)
    _fields(spec, ('height', 'top_radius', 'hem_radius'), ('pool', 'folds', 'fold_depth', 'ripples'), 'drape')
    _number(spec['height'], .1, 40, 'drape height')
    _number(spec['top_radius'], .02, 20, 'drape top_radius')
    _number(spec['hem_radius'], .05, 40, 'drape hem_radius')
    pool = spec.get('pool', 0); _number(pool, 0, 10, 'drape pool')
    folds = spec.get('folds', 8); _number(folds, 0, 24, 'drape folds', True)
    depth = spec.get('fold_depth', .12); _number(depth, 0, .5, 'drape fold_depth')
    ripples = spec.get('ripples', 0); _number(ripples, 0, 8, 'drape ripples', True)
    if ripples and not pool:
        raise SceneError('drape ripples wrinkle the cloth lying on the ground: set pool above 0, or remove ripples')
    # Rippled cloth gives more of its length to the part on the ground, so the ripples have cells to bend.
    hang, rest = ('.6', '.4') if ripples else ('.85', '.15')
    lift = (f'+{_f(.14 * pool)}*rk_dq*(1.-.7*rk_dq)*(.5-.5*cos(6.2831853*{ripples}.*rk_dq+2.*sin({max(folds, 1)}.*rk_da)))'
            if ripples else '')
    code = [
        'float rk_dv=clamp(v,0.,1.);',
        f'float rk_dh=clamp(rk_dv/{hang if pool else "1."},0.,1.);',
        'float rk_da=u*6.2831853;',
        *([f'float rk_dq=clamp((rk_dv-{hang})/{rest},0.,1.);'] if ripples else []),
        # Radius widens down the cloth, then runs out flat along the ground past the hang line.
        f'float rk_dr=mix({_f(spec["top_radius"])},{_f(spec["hem_radius"])},rk_dh*rk_dh*(3.-2.*rk_dh))'
        f'+{_f(pool)}*clamp((rk_dv-{hang})/{rest},0.,1.);',
        f'rk_dr*=1.+{_f(depth)}*rk_dv*cos({folds}.*rk_da);',
        f'vec3 rk_drape_p=vec3(rk_dr*cos(rk_da),{_f(spec["height"])}*(1.-rk_dh){lift},rk_dr*sin(rk_da));',
    ]
    return {'definitions': '\n'.join(code), 'cost': 70 + (30 if ripples else 0),
            'names': {'drape_x': 'rk_drape_p.x', 'drape_y': 'rk_drape_p.y', 'drape_z': 'rk_drape_p.z'}}


def _ring(spec, segments, context=None):
    _fields(spec, ('radius', 'thickness'), ('tilt',), 'ring')
    _number(spec['radius'], .05, 40, 'ring radius')
    _number(spec['thickness'], .005, 10, 'ring thickness')
    tilt = spec.get('tilt', 0); _number(tilt, -math.pi, math.pi, 'ring tilt')
    if spec['thickness'] >= spec['radius']:
        raise SceneError('ring thickness must be smaller than its radius, or the hole closes')
    code = [
        'float rk_ra=u*6.2831853;', 'float rk_rb=v*6.2831853;',
        f'float rk_rr={_f(spec["radius"])}+{_f(spec["thickness"])}*cos(rk_rb);',
        f'vec3 rk_rq=vec3(rk_rr*cos(rk_ra),{_f(spec["thickness"])}*sin(rk_rb),rk_rr*sin(rk_ra));',
        f'vec3 rk_ring_p=vec3(rk_rq.x,rk_rq.y*{_f(math.cos(tilt))}-rk_rq.z*{_f(math.sin(tilt))},'
        f'rk_rq.y*{_f(math.sin(tilt))}+rk_rq.z*{_f(math.cos(tilt))});',
    ]
    return {'definitions': '\n'.join(code), 'cost': 50,
            'names': {'ring_x': 'rk_ring_p.x', 'ring_y': 'rk_ring_p.y', 'ring_z': 'rk_ring_p.z'}}


def _rig(name, context, label):
    rigs = (context or {}).get('rigs') or {}
    if not isinstance(name, str) or name not in rigs:
        raise SceneError(f'{label} rig must name a rig in scene.rigs: got {str(name)[:40]!r}; scene.rigs defines '
                         + (', '.join(sorted(rigs)) if rigs else 'none, so add a rig there first'))
    return rigs[name]


def _cards(segments, cards, least, label, unit):
    across = segments[0] // cards if isinstance(segments, list) and segments and isinstance(segments[0], int) else 0
    if across < least or segments[0] % cards:
        fit = [str(cards * k) for k in range(least, least + 6) if cards * k <= 128][:3]
        raise SceneError(f'{label} needs u segments to be a multiple of its {cards} {unit} with at least {least} each: '
                         + (f'use u segments {" or ".join(fit)}' if fit else 'use fewer, the u limit is 128'))
    return across


def _vec(v):
    return 'vec3(' + ','.join(_f(x) for x in v) + ')'


def _figure(spec, segments, context=None):
    _fields(spec, ('rig',), ('parts',), 'figure')
    rig = _rig(spec['rig'], context, 'figure')
    parts = spec.get('parts', list(PARTS))
    if (not isinstance(parts, list) or not parts or any(not isinstance(p, str) or p not in PARTS for p in parts)
            or len(set(parts)) != len(parts)):
        raise SceneError(f'figure parts is a list of the body masses to draw, each once: {", ".join(PARTS)}; omit it for the whole body')
    bones = [dict(b, radii=(b['ra'], b['rb'], 0.)) for b in rig['bones'] if b['group'] in parts]
    n = len(bones)
    across = _cards(segments, n, 6, 'figure', 'body masses')

    def table(name, key):
        return f'vec3 {name}[{n}]=vec3[{n}]({",".join(_vec(b[key]) for b in bones)});'

    code = [
        table('rk_ga', 'a'), table('rk_gd', 'd'), table('rk_gx', 'x'), table('rk_gy', 'y'), table('rk_gz', 'axis'),
        table('rk_gc', 'radii'),
        f'float rk_gu=clamp(u,0.,.999999)*{n}.;',
        # Each mass is a closed capsule; the bias keeps a normal sampled at its first column on the same mass.
        f'float rk_gi=min(floor(rk_gu+{_f(.00075 * n)}),{n - 1}.);',
        'int rk_gn=int(rk_gi);',
        f'float rk_gt=min((rk_gu-rk_gi)*{_f(across / (across - 1))},1.)*6.2831853;',
        'float rk_gv=clamp(v,0.,1.);',
        'float rk_gb=clamp(rk_gv*2.-.5,0.,1.);',
        'float rk_gp=1.5707963*(clamp(rk_gv*4.-3.,0.,1.)-clamp(1.-rk_gv*4.,0.,1.));',
        'vec3 rk_figure_p=rk_ga[rk_gn]+rk_gd[rk_gn]*rk_gb+mix(rk_gc[rk_gn].x,rk_gc[rk_gn].y,rk_gb)*'
        '(cos(rk_gp)*(cos(rk_gt)*rk_gx[rk_gn]+sin(rk_gt)*rk_gy[rk_gn])+sin(rk_gp)*rk_gz[rk_gn]);',
    ]
    return {'definitions': '\n'.join(code), 'cost': 220, 'cards': n,
            'names': {'figure_x': 'rk_figure_p.x', 'figure_y': 'rk_figure_p.y', 'figure_z': 'rk_figure_p.z'}}


def _wing(spec, segments, context=None):
    _fields(spec, ('span',), ('side', 'raise', 'open', 'count', 'rows', 'feather_length', 'width', 'overlap', 'layer'), 'wing')
    span = spec['span']; _number(span, .1, 40, 'wing span')
    side = spec.get('side', 'right')
    if side not in ('left', 'right'):
        raise SceneError('wing side must be "left" or "right"; build one surface for each wing')
    lift = spec.get('raise', .95); _number(lift, -.6, 1.5, 'wing raise')
    count = spec.get('count', 10); _number(count, 4, 24, 'wing count', True)
    rows = spec.get('rows', 3); _number(rows, 1, 3, 'wing rows', True)
    length = spec.get('feather_length', .6 * span); _number(length, .02, 40, 'wing feather_length')
    broad = spec.get('width', 1.5); _number(broad, .4, 3, 'wing width')
    overlap = spec.get('overlap', .5); _number(overlap, 0, 1, 'wing overlap')
    layer = spec.get('layer', .03 * span); _number(layer, 0, 2, 'wing layer')
    cards = count * rows
    across = _cards(segments, cards, 2, 'wing', f'feathers ({count} in each of {rows} rows)')
    opened = compile_expression(spec.get('open', '1'), {})
    code = [
        f'float rk_wu=clamp(u,0.,.999999)*{cards}.;',
        f'float rk_wi=min(floor(rk_wu+{_f(.00075 * cards)}),{cards - 1}.);',
        f'float rk_wf=min((rk_wu-rk_wi)*{_f(across / (across - 1))},1.);',
        # Rows share one arm: long primaries behind, shorter rows laid over their bases toward the front.
        f'float rk_wr=floor((rk_wi+.5)/{count}.);',
        f'float rk_ws=(rk_wi-rk_wr*{count}.)/{count - 1}.;',
        f'float rk_wo=clamp({opened["glsl"]},0.,1.);',
        f'float rk_wa=mix(-1.15,{_f(lift)},rk_wo);',
        'float rk_wv=clamp(v,0.,1.);',
        'vec2 rk_wd=vec2(cos(rk_wa),sin(rk_wa));',
        f'vec2 rk_wp={_f(span)}*((.06+mix(.4,1.,rk_wo)*rk_ws)*rk_wd+.07*rk_wo*sin(3.14159265*rk_ws)*vec2(-rk_wd.y,rk_wd.x));',
        # Feathers fan from hanging at the root to continuing the arm at the tip; folding closes the fan.
        'float rk_wh=rk_wa-mix(1.9,.12,rk_ws)*(.3+.7*rk_wo);',
        f'float rk_wl={_f(length)}*mix(1.,.36,rk_wr*.5)*mix(.62,1.,rk_ws)*rk_wv;',
        f'float rk_ww={_f(span / count * (1 + 2 * overlap) * broad)}*(.2+.8*sin(3.14159265*pow(rk_wv,.75)))*(rk_wf-.5);',
        'vec2 rk_wq=rk_wp+rk_wl*vec2(cos(rk_wh),sin(rk_wh))+rk_ww*vec2(-sin(rk_wh),cos(rk_wh));',
        f'vec3 rk_wing_p=vec3({"-" if side == "left" else ""}rk_wq.x,rk_wq.y,'
        f'{_f(layer)}*(rk_wr-{rows - 1}.+.35*fract(rk_wi*.618034)+(rk_wf-.5)*(rk_wf-.5)));',
    ]
    return {'definitions': '\n'.join(code), 'cost': 170 + opened['cost'], 'cards': cards,
            'names': {'wing_x': 'rk_wing_p.x', 'wing_y': 'rk_wing_p.y', 'wing_z': 'rk_wing_p.z'}}


_BUILD = {'feathers': _feathers, 'drape': _drape, 'ring': _ring, 'figure': _figure, 'wing': _wing}


def compile_constructs(obj, context=None):
    """Compiled parts for whichever construction fields the surface carries, in a fixed order."""
    present = [name for name in CONSTRUCTS if name in obj]
    if len(present) > 1 or (present and 'loft' in obj):
        raise SceneError('A surface takes one construction field: feathers, drape, ring, figure, wing or loft')
    return [_BUILD[name](obj[name], obj.get('segments'), context) for name in present]
