"""Scene v2: source-grounded procedural geometry with bounded GPU work."""
import copy
import re
from .scenes import SceneError, _number, _text, _COLOR, _LAYER_ID
from .expressions import compile_expression, FUNCTIONS


def fields(value,names,label):
    if not isinstance(value,dict) or set(value)!=set(names.split()):raise SceneError(f'Invalid {label} fields')


def vector(value,label):
    if not isinstance(value,list) or len(value)!=3:raise SceneError(f'{label} requires three coordinates')
    for x in value:_number(x,-80,80,label)
    return value


def color(value):
    if not isinstance(value,str) or not _COLOR.fullmatch(value):raise SceneError('World colors must be #RRGGBB')


def compile_surface(obj):
    bindings=obj.get('bindings',[])
    if not isinstance(bindings,list) or len(bindings)>16:raise SceneError('Surface allows at most 16 local bindings')
    names={};definitions=[];cost=0
    for binding in bindings:
        fields(binding,'name expression','local binding')
        name=binding['name']
        if not isinstance(name,str) or not re.fullmatch('[a-z][a-z0-9_]{0,23}',name) or name in names or name in FUNCTIONS or name in ('u','v','t','pi'):
            raise SceneError('Binding names must be unique lowercase identifiers, not reserved math names')
        # Only prior names are in scope. No recursion, cycles, forward references,
        # caller-supplied shader identifiers, or executable code are accepted.
        value=compile_expression(binding['expression'],names)
        shader_name=f'rk_local_{len(names)}';names[name]=shader_name
        definitions.append(f'float {shader_name}={value["glsl"]};');cost+=value['cost']
    pos=[compile_expression(obj['position'][k],names) for k in ('x','y','z')]
    blend=compile_expression(obj['color_mix'],names)
    result={'position':[p['glsl'] for p in pos],'color_mix':blend['glsl'],
            'definitions':'\n'.join(definitions),'cost':cost+sum(p['cost'] for p in pos)+blend['cost']}
    for field in ('color_detail','bump_detail'):
        if field not in obj:continue
        detail=obj[field]
        if not isinstance(detail,str) or not 1<=len(detail)<=128:
            raise SceneError('Material detail requires 1-128 characters')
        # Per-pixel work is independent of tessellation. Geometry bindings are
        # deliberately unavailable here; their cost can be much larger.
        compiled=compile_expression(detail)
        if compiled['cost']>32:raise SceneError('Material detail exceeds 32 expression nodes')
        result[field]=compiled['glsl']
        result['detail_cost']=result.get('detail_cost',0)+compiled['cost']
    return result


def validate_world(value,asset_ids):
    fields(value,'schema_version title mood reason duration width height seed references environment camera objects','world')
    s=copy.deepcopy(value)
    if type(s['schema_version']) is not int or s['schema_version']!=2:raise SceneError('Unsupported world version')
    for name,limit in (('title',100),('mood',100),('reason',600)):_text(s[name],limit,name)
    _number(s['duration'],4,30,'duration');_number(s['width'],1280,1280,'width',True);_number(s['height'],720,720,'height',True)
    _number(s['seed'],0,2**31-1,'seed',True)
    if not isinstance(s['references'],list) or not 1<=len(s['references'])<=6:raise SceneError('World needs 1-6 source interpretations')
    used=set()
    for ref in s['references']:
        fields(ref,'asset_id observed created','source interpretation')
        if not isinstance(ref['asset_id'],str) or ref['asset_id'] not in asset_ids or ref['asset_id'] in used:raise SceneError('Invalid or repeated world source')
        used.add(ref['asset_id'])
        for key in ('observed','created'):
            _text(ref[key],500,key)
            if not ref[key].strip():raise SceneError('Explain observed and created features')
    env=s['environment']
    optional={'fill_color','fill_direction','fill_strength','exposure'}
    if not isinstance(env,dict):raise SceneError('Invalid environment fields')
    fields({k:v for k,v in env.items() if k not in optional},'sky_top sky_bottom fog_color fog_density light_color light_direction sun_size sun_strength','environment')
    for key in ('sky_top','sky_bottom','fog_color','light_color'):color(env[key])
    _number(env['fog_density'],0,.15,'fog density');_number(env['sun_size'],.003,.15,'sun size');_number(env['sun_strength'],0,4,'sun strength')
    if sum(x*x for x in vector(env['light_direction'],'light direction'))<.0001:raise SceneError('Light direction cannot be zero')
    if 'fill_color' in env:color(env['fill_color'])
    if 'fill_strength' in env:_number(env['fill_strength'],0,2,'fill strength')
    if 'exposure' in env:_number(env['exposure'],.25,4,'exposure')
    if 'fill_direction' in env and sum(x*x for x in vector(env['fill_direction'],'fill direction'))<.0001:
        raise SceneError('Fill direction cannot be zero')
    camera=s['camera']
    if not isinstance(camera,list) or not 2<=len(camera)<=12:raise SceneError('Camera requires 2-12 states')
    last=-1;previous=None
    for key in camera:
        fields(key,'at eye target fov','camera state')
        _number(key['at'],0,s['duration'],'camera time');_number(key['fov'],15,100,'field of view')
        if key['at']<=last:raise SceneError('Camera times must increase')
        last=key['at'];eye=vector(key['eye'],'camera eye');target=vector(key['target'],'camera target')
        delta=[a-b for a,b in zip(eye,target)]
        if sum(x*x for x in delta)<.01:raise SceneError('Camera eye and target must be distinct')
        if previous is not None:
            step=[a-b for a,b in zip(delta,previous)];length=sum(x*x for x in step)
            u=max(0,min(1,-sum(a*b for a,b in zip(previous,step))/length)) if length else 0
            if sum((a+u*b)**2 for a,b in zip(previous,step))<.01:raise SceneError('Camera crosses its target between states')
        previous=delta
    if camera[0]['at']!=0 or camera[-1]['at']!=s['duration']:raise SceneError('Camera must span the full duration')
    if not isinstance(s['objects'],list) or not 1<=len(s['objects'])<=12:raise SceneError('World requires 1-12 surfaces')
    ids=set();cells=work=detail_work=0
    for obj in s['objects']:
        if not isinstance(obj,dict):raise SceneError('Invalid surface fields')
        fields({k:v for k,v in obj.items() if k not in ('bindings','color_detail','bump_detail','caps')},'id position segments color color_high color_mix roughness metalness emission','surface')
        caps=obj.get('caps',[])
        if not isinstance(caps,list) or len(caps)>2 or any(not isinstance(c,str) or c not in ('v0','v1') for c in caps) or len(set(caps))!=len(caps):
            raise SceneError('Caps must be a unique list containing v0 and/or v1')
        if not isinstance(obj['id'],str) or not _LAYER_ID.fullmatch(obj['id']) or obj['id'] in ids:raise SceneError('Surface IDs must be unique simple names')
        ids.add(obj['id']);fields(obj['position'],'x y z','surface position')
        compiled=compile_surface(obj)
        detail_work+=compiled.get('detail_cost',0)
        segments=obj['segments']
        if not isinstance(segments,list) or len(segments)!=2:raise SceneError('Surface segments require two integers')
        _number(segments[0],4,128,'u segments',True);_number(segments[1],4,96,'v segments',True)
        count=segments[0]*segments[1];cells+=count;work+=count*compiled['cost']
        # Fan triangles and bounded boundary-average sampling consume the same
        # budgets as the side mesh. Do not make closure free or raise limits.
        cells+=len(caps)*((segments[0]+1)//2)
        work+=len(caps)*6*(segments[0]+1)*compiled['cost']
        color(obj['color']);color(obj['color_high'])
        _number(obj['roughness'],.04,1,'roughness');_number(obj['metalness'],0,1,'metalness');_number(obj['emission'],0,3,'emission')
    if detail_work>128:raise SceneError('World material detail exceeds 128 total expression nodes; simplify detail expressions or use them on fewer surfaces')
    if cells>32000 or work>4_000_000:
        # Actionable authoring feedback: reducing each segment axis by this
        # factor reduces the cell/work total approximately quadratically.
        scale=min((32000/max(cells,1))**.5,(4_000_000/max(work,1))**.5,1)
        raise SceneError(f'World exceeds geometry or shader work budget: {cells} cells (max 32000), '
                         f'{work} expression-weighted work (max 4000000). '
                         f'Reduce both segment counts per object to about {scale*.95:.2f} times their current values '
                         '(round down, minimum 4), or simplify repeated position/color expressions. '
                         'Preserve the intended shapes and timing; resubmit the full scene.')
    return s


def compile_world(scene):
    return [{k:v for k,v in compile_surface(o).items() if k not in ('cost','detail_cost')} for o in scene['objects']]


def obj_schema(properties):return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
NUM={'type':'number'}
TEXT={'type':'string'}
VEC={'type':'array','items':NUM,'minItems':3,'maxItems':3}
WORLD_SCHEMA=obj_schema({
    'schema_version':{'type':'integer','const':2},'title':{'type':'string','maxLength':100},
    'mood':{'type':'string','maxLength':100},'reason':{'type':'string','maxLength':600},
    'duration':{'type':'number','minimum':4,'maximum':30},'width':{'type':'integer','const':1280},'height':{'type':'integer','const':720},'seed':{'type':'integer'},
    'references':{'type':'array','minItems':1,'maxItems':6,'items':obj_schema({'asset_id':TEXT,
        'observed':{'type':'string','maxLength':500},'created':{'type':'string','maxLength':500}})},
    'environment':obj_schema({'sky_top':TEXT,'sky_bottom':TEXT,'fog_color':TEXT,'fog_density':NUM,'light_color':TEXT,'light_direction':VEC,'sun_size':NUM,'sun_strength':NUM}),
    'camera':{'type':'array','minItems':2,'maxItems':12,'items':obj_schema({'at':NUM,'eye':VEC,'target':VEC,'fov':NUM})},
    'objects':{'type':'array','minItems':1,'maxItems':12,'items':obj_schema({'id':TEXT,'position':obj_schema({'x':TEXT,'y':TEXT,'z':TEXT}),
        'segments':{'type':'array','items':{'type':'integer'},'minItems':2,'maxItems':2},'color':TEXT,'color_high':TEXT,'color_mix':TEXT,
        'roughness':NUM,'metalness':NUM,'emission':NUM})}})
# Optional studio-light controls preserve all existing v2 plans.
WORLD_SCHEMA['properties']['environment']['properties'].update({
    'fill_color':{'type':'string','description':'Optional unshadowed fill light color; default #B8D1FF.'},
    'fill_direction':VEC,
    'fill_strength':{'type':'number','minimum':0,'maximum':2,'description':'Optional fill intensity, default 0.25. Set 0 for no fill.'},
    'exposure':{'type':'number','minimum':.25,'maximum':4,'description':'Optional scene exposure multiplier, default 1.'}})
WORLD_SCHEMA['properties']['objects']['items']['properties']['bindings']={
    'type':'array','maxItems':16,
    'description':'Optional ordered local math definitions shared by position and color expressions. Each can reference u/v/t/pi and earlier bindings. Use for opening progress, local frames and reusable geometric terms; no cycles or code.',
    'items':obj_schema({'name':{'type':'string','pattern':'^[a-z][a-z0-9_]{0,23}$'},
                        'expression':{'type':'string','minLength':1,'maxLength':512}})}
WORLD_SCHEMA['properties']['objects']['items']['properties']['color_detail']={
    'type':'string','minLength':1,'maxLength':128,
    'description':'Optional per-pixel albedo detail expression using only u/v/t/pi and supported math, no local bindings. At most32 nodes per expression; color_detail and bump_detail share128 nodes across the world. Result clamps to -0.35..0.35 and multiplies base color by 1+detail. Use subtle grain/weave/material variation; does not change geometry, normals or roughness. Default absent preserves existing rendering. Avoid subpixel frequencies and animated noise unless intentional.'}
WORLD_SCHEMA['properties']['objects']['items']['properties']['bump_detail']={
    'type':'string','minLength':1,'maxLength':128,
    'description':'Optional per-pixel relief HEIGHT in world units, using u/v/t/pi and math, no bindings. <=32 expression nodes; color_detail and bump_detail together share128 nodes across the world. Height clamps to +/-0.1, slope magnitude to0.6. Changes lighting normals only, not silhouettes, shadow geometry, or roughness. Start .002-.02 amplitude for stone/cloth or .01-.04 for water ripples; scale frequency to surface size. Avoid subpixel frequencies, seams and sharp masks; inspect motion for shimmer. Not physical water, transparency or scene reflections.'}
WORLD_SCHEMA['properties']['objects']['items']['properties']['caps']={
    'type':'array','maxItems':2,'uniqueItems':True,'items':{'type':'string','enum':['v0','v1']},
    'description':'Optional solid end caps at v=0 and/or v=1. Use only when u wraps a closed planar convex or star-shaped ring, e.g. a beam or trunk cross-section. Generates a triangle fan to the average boundary position at current t, moving with the surface. Flat face normals; no bump/color_detail on caps. Counts toward existing geometry/work budgets. Not arbitrary concave hole repair or a guarantee against self-intersection. Omit on open cloth, terrain and water.'}
