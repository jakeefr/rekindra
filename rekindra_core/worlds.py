"""Scene v2: source-grounded procedural geometry with bounded GPU work."""
import copy
from .scenes import SceneError, _number, _text, _COLOR, _LAYER_ID
from .expressions import compile_expression


def fields(value,names,label):
    if not isinstance(value,dict) or set(value)!=set(names.split()):raise SceneError(f'Invalid {label} fields')


def vector(value,label):
    if not isinstance(value,list) or len(value)!=3:raise SceneError(f'{label} requires three coordinates')
    for x in value:_number(x,-80,80,label)
    return value


def color(value):
    if not isinstance(value,str) or not _COLOR.fullmatch(value):raise SceneError('World colors must be #RRGGBB')


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
    env=s['environment'];fields(env,'sky_top sky_bottom fog_color fog_density light_color light_direction sun_size sun_strength','environment')
    for key in ('sky_top','sky_bottom','fog_color','light_color'):color(env[key])
    _number(env['fog_density'],0,.15,'fog density');_number(env['sun_size'],.003,.15,'sun size');_number(env['sun_strength'],0,4,'sun strength')
    if sum(x*x for x in vector(env['light_direction'],'light direction'))<.0001:raise SceneError('Light direction cannot be zero')
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
    ids=set();cells=work=0
    for obj in s['objects']:
        fields(obj,'id position segments color color_high color_mix roughness metalness emission','surface')
        if not isinstance(obj['id'],str) or not _LAYER_ID.fullmatch(obj['id']) or obj['id'] in ids:raise SceneError('Surface IDs must be unique simple names')
        ids.add(obj['id']);fields(obj['position'],'x y z','surface position')
        expressions=[compile_expression(obj['position'][k]) for k in ('x','y','z')]+[compile_expression(obj['color_mix'])]
        segments=obj['segments']
        if not isinstance(segments,list) or len(segments)!=2:raise SceneError('Surface segments require two integers')
        _number(segments[0],4,128,'u segments',True);_number(segments[1],4,96,'v segments',True)
        count=segments[0]*segments[1];cells+=count;work+=count*sum(e['cost'] for e in expressions)
        color(obj['color']);color(obj['color_high'])
        _number(obj['roughness'],.04,1,'roughness');_number(obj['metalness'],0,1,'metalness');_number(obj['emission'],0,3,'emission')
    if cells>32000 or work>4_000_000:raise SceneError('World exceeds geometry or shader work budget')
    return s


def compile_world(scene):
    return [{'position':[compile_expression(o['position'][k])['glsl'] for k in ('x','y','z')],
             'color_mix':compile_expression(o['color_mix'])['glsl']} for o in scene['objects']]


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
