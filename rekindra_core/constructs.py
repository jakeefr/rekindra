"""Construction fields: parametric part builders compiled to original shader math.

Each optional surface field supplies coordinates to the position expressions, the way loft does:
feathers -> feather_x/y/z, drape -> drape_x/y/z, ring -> ring_x/y/z. Absent by default.
"""
import math
from .scenes import SceneError, _number
from .expressions import compile_expression

CONSTRUCTS = ('feathers', 'drape', 'ring')


def _fields(value, required, optional, label):
    if not isinstance(value, dict) or not set(required) <= set(value) <= set(required) | set(optional):
        raise SceneError(f'Invalid {label} fields. Required: {", ".join(required)}. Optional: {", ".join(optional)}')


def _f(n):
    return format(float(n), '.9f')


def _feathers(spec, segments):
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


def _drape(spec, segments):
    _fields(spec, ('height', 'top_radius', 'hem_radius'), ('pool', 'folds', 'fold_depth'), 'drape')
    _number(spec['height'], .1, 40, 'drape height')
    _number(spec['top_radius'], .02, 20, 'drape top_radius')
    _number(spec['hem_radius'], .05, 40, 'drape hem_radius')
    pool = spec.get('pool', 0); _number(pool, 0, 10, 'drape pool')
    folds = spec.get('folds', 8); _number(folds, 0, 24, 'drape folds', True)
    depth = spec.get('fold_depth', .12); _number(depth, 0, .5, 'drape fold_depth')
    hang = '.85' if pool else '1.'
    code = [
        'float rk_dv=clamp(v,0.,1.);',
        f'float rk_dh=clamp(rk_dv/{hang},0.,1.);',
        'float rk_da=u*6.2831853;',
        # Radius widens down the cloth, then runs out flat along the ground past the hang line.
        f'float rk_dr=mix({_f(spec["top_radius"])},{_f(spec["hem_radius"])},rk_dh*rk_dh*(3.-2.*rk_dh))'
        f'+{_f(pool)}*clamp((rk_dv-.85)/.15,0.,1.);',
        f'rk_dr*=1.+{_f(depth)}*rk_dv*cos({folds}.*rk_da);',
        f'vec3 rk_drape_p=vec3(rk_dr*cos(rk_da),{_f(spec["height"])}*(1.-rk_dh),rk_dr*sin(rk_da));',
    ]
    return {'definitions': '\n'.join(code), 'cost': 70,
            'names': {'drape_x': 'rk_drape_p.x', 'drape_y': 'rk_drape_p.y', 'drape_z': 'rk_drape_p.z'}}


def _ring(spec, segments):
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


_BUILD = {'feathers': _feathers, 'drape': _drape, 'ring': _ring}


def compile_constructs(obj):
    """Compiled parts for whichever construction fields the surface carries, in a fixed order."""
    present = [name for name in CONSTRUCTS if name in obj]
    if len(present) > 1 or (present and 'loft' in obj):
        raise SceneError('A surface takes one construction field: feathers, drape, ring or loft')
    return [_BUILD[name](obj[name], obj.get('segments')) for name in present]
