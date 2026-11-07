"""Scene v2: source-grounded procedural geometry with bounded GPU work."""
import copy
import math
import re
from .scenes import SceneError, _number, _text, _COLOR, _LAYER_ID
from .expressions import compile_expression, sampler, FUNCTIONS
from .assemblies import compile_assemblies
from .lofts import compile_loft

MAX_SURFACES = 24

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
    if 'loft' in obj:
        loft=compile_loft(obj['loft']);names.update(loft['names']);definitions.append(loft['definitions']);cost+=loft['cost']
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
    for field in ('color_detail','bump_detail','color_pattern'):
        if field not in obj:continue
        detail=obj[field]
        if not isinstance(detail,str) or not 1<=len(detail)<=128:
            raise SceneError('Material detail requires 1-128 characters')
        # Per-pixel work is independent of tessellation. Geometry bindings are
        # deliberately unavailable here; their cost can be much larger.
        compiled=compile_expression(detail)
        if compiled['cost']>32:raise SceneError('Material detail exceeds 32 expression nodes')
        if field=='color_pattern':_refuse_stripes(detail)
        result[field]=compiled['glsl']
        result['detail_cost']=result.get('detail_cost',0)+compiled['cost']
    return result


# A color_pattern repeating more than this many times across a surface's u or v
# range, with a visible swing after the renderer's 0..1 blend clamp, reads as hard
# stripes rather than material grain (B01 terrace: .35+.25*cos(u*80*pi)).
_STRIPE_CYCLES=16
_STRIPE_SWING=.08


def _refuse_stripes(source):
    f=sampler(source);n=2048
    for t in (0.0,1.0,7.3):
        for fixed in (.25,.5,.75):
            for axis in ('u','v'):
                xs=[min(max(f(i/(n-1),fixed,t) if axis=='u' else f(fixed,i/(n-1),t),0.),1.) for i in range(n)]
                lo,hi=min(xs),max(xs)
                if hi-lo<_STRIPE_SWING:continue
                mid=(lo+hi)/2;crossings=sum((a<mid)!=(b<mid) for a,b in zip(xs,xs[1:]))
                if crossings>2*_STRIPE_CYCLES:
                    raise SceneError(f'color_pattern repeats about {crossings/2:g} times across {axis} with a visible swing; '
                                     f'this renders as hard stripes. Keep repeats at or below {_STRIPE_CYCLES} or the swing under {_STRIPE_SWING}')


_EVIDENCE_ID=re.compile(r'ev-[0-9a-f]{24}')


def _text_references(refs):
    # Shape only. Whether each cited asset and evidence_id really exists in the
    # project's recovered dossier is checked where the project is known
    # (CompositionStore), because world validation sees image IDs only.
    if not isinstance(refs,list) or not 1<=len(refs)<=4:raise SceneError('text_references needs 1-4 entries')
    seen=set()
    for ref in refs:
        fields(ref,'asset_id evidence_ids interpretation','text reference')
        aid=ref['asset_id']
        if not isinstance(aid,str) or not 1<=len(aid)<=64 or aid in seen:raise SceneError('Invalid or repeated text reference asset_id')
        seen.add(aid)
        ids=ref['evidence_ids']
        if (not isinstance(ids,list) or not 1<=len(ids)<=4
                or any(not isinstance(e,str) or not _EVIDENCE_ID.fullmatch(e) for e in ids) or len(set(ids))!=len(ids)):
            raise SceneError('Each text reference needs 1-4 unique evidence_id values from rekindra_recover')
        _text(ref['interpretation'],300,'text reference interpretation')
        if not ref['interpretation'].strip():raise SceneError('Text reference interpretation cannot be blank')


def validate_world(value,asset_ids):
    if not isinstance(value,dict):raise SceneError('Invalid world fields')
    fields({k:v for k,v in value.items() if k not in ('assemblies','text_references')},'schema_version title mood reason duration width height seed references environment camera objects','world')
    s=copy.deepcopy(value)
    assemblies=compile_assemblies(s.get('assemblies',[]))
    if 'text_references' in s:_text_references(s['text_references'])
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
    optional={'fill_color','fill_direction','fill_strength','exposure','ambient_strength','ground_color','ground_strength','point_lights','occlusion_strength','occlusion_radius','environment_panels'}
    if not isinstance(env,dict):raise SceneError('Invalid environment fields')
    fields({k:v for k,v in env.items() if k not in optional},'sky_top sky_bottom fog_color fog_density light_color light_direction sun_size sun_strength','environment')
    for key in ('sky_top','sky_bottom','fog_color','light_color'):color(env[key])
    _number(env['fog_density'],0,.15,'fog density');_number(env['sun_size'],.003,.15,'sun size');_number(env['sun_strength'],0,4,'sun strength')
    if sum(x*x for x in vector(env['light_direction'],'light direction'))<.0001:raise SceneError('Light direction cannot be zero')
    if 'fill_color' in env:color(env['fill_color'])
    if 'fill_strength' in env:_number(env['fill_strength'],0,2,'fill strength')
    if 'exposure' in env:_number(env['exposure'],.25,4,'exposure')
    if 'ambient_strength' in env:_number(env['ambient_strength'],0,2,'ambient strength')
    if 'ground_strength' in env:_number(env['ground_strength'],0,1,'ground strength')
    if 'ground_color' in env:color(env['ground_color'])
    if 'occlusion_strength' in env:_number(env['occlusion_strength'],0,1,'occlusion strength')
    if 'occlusion_radius' in env:_number(env['occlusion_radius'],.05,4,'occlusion radius')
    if 'environment_panels' in env:
        panels=env['environment_panels']
        if not isinstance(panels,list) or len(panels)>4:raise SceneError('At most four environment panels are allowed')
        for panel in panels:
            fields(panel,'direction color intensity size rotation','environment panel')
            if sum(x*x for x in vector(panel['direction'],'environment panel direction'))<.0001:
                raise SceneError('Environment panel direction cannot be zero')
            color(panel['color'])
            _number(panel['intensity'],0,16,'environment panel intensity')
            _number(panel['rotation'],-2*math.pi,2*math.pi,'environment panel rotation')
            if not isinstance(panel['size'],list) or len(panel['size'])!=2:
                raise SceneError('Environment panel size requires two tangent half-widths')
            for size in panel['size']:_number(size,.03,1,'environment panel size')
    if 'point_lights' in env:
        lights=env['point_lights']
        if not isinstance(lights,list) or len(lights)>4:raise SceneError('At most four point lights are allowed')
        for light in lights:
            fields(light,'position color intensity range','point light')
            vector(light['position'],'point light position');color(light['color'])
            _number(light['intensity'],0,200,'point light intensity')
            _number(light['range'],.1,80,'point light range')
    if 'fill_direction' in env and sum(x*x for x in vector(env['fill_direction'],'fill direction'))<.0001:
        raise SceneError('Fill direction cannot be zero')
    camera=s['camera']
    if not isinstance(camera,list) or not 2<=len(camera)<=12:raise SceneError('Camera requires 2-12 states')
    last=-1;previous=None
    for key in camera:
        if not isinstance(key,dict):raise SceneError('Invalid camera state fields')
        fields({k:v for k,v in key.items() if k!='cut'},'at eye target fov','camera state')
        if 'cut' in key and type(key['cut']) is not bool:raise SceneError('Camera cut must be a boolean')
        if previous is None and key.get('cut',False):raise SceneError('The first camera state cannot be a cut')
        _number(key['at'],0,s['duration'],'camera time');_number(key['fov'],15,100,'field of view')
        if key['at']<=last:raise SceneError('Camera times must increase')
        last=key['at'];eye=vector(key['eye'],'camera eye');target=vector(key['target'],'camera target')
        delta=[a-b for a,b in zip(eye,target)]
        if sum(x*x for x in delta)<.01:raise SceneError('Camera eye and target must be distinct')
        if previous is not None and not key.get('cut',False):
            step=[a-b for a,b in zip(delta,previous)];length=sum(x*x for x in step)
            u=max(0,min(1,-sum(a*b for a,b in zip(previous,step))/length)) if length else 0
            if sum((a+u*b)**2 for a,b in zip(previous,step))<.01:raise SceneError('Camera crosses its target between states')
        previous=delta
    if camera[0]['at']!=0 or camera[-1]['at']!=s['duration']:raise SceneError('Camera must span the full duration')
    if not isinstance(s['objects'],list) or not 1<=len(s['objects'])<=MAX_SURFACES:
        raise SceneError(f'World requires 1-{MAX_SURFACES} surfaces')
    ids=set();cells=work=detail_work=placements=active_reflectors=0
    for obj in s['objects']:
        if not isinstance(obj,dict):raise SceneError('Invalid surface fields')
        fields({k:v for k,v in obj.items() if k not in ('bindings','color_detail','bump_detail','color_pattern','caps','instances','assembly','shading','loft','reflection')},'id position segments color color_high color_mix roughness metalness emission','surface')
        if 'reflection' in obj:
            reflection=obj['reflection'];fields(reflection,'strength blur','planar reflection')
            _number(reflection['strength'],0,1,'reflection strength');_number(reflection['blur'],0,8,'reflection blur')
            if any(k in obj for k in ('assembly','instances','caps','loft')):
                raise SceneError('Reflection requires an unassembled horizontal surface without instances, caps or loft')
            try:
                y=obj['position']['y']
                if not isinstance(y,str) or not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',y.strip(),flags=re.ASCII):raise ValueError()
                height=float(y)
            except (ValueError,TypeError,KeyError):
                raise SceneError('Reflection surface y must be a numeric constant string')
            _number(height,-80,80,'reflection plane height')
            active_reflectors+=reflection['strength']>0
            if active_reflectors>1:raise SceneError('World allows only one active planar reflection')
        if 'shading' in obj and (not isinstance(obj['shading'],str) or obj['shading'] not in ('smooth','flat')):
            raise SceneError('Surface shading must be smooth or flat')
        caps=obj.get('caps',[])
        if not isinstance(caps,list) or len(caps)>2 or any(not isinstance(c,str) or c not in ('v0','v1') for c in caps) or len(set(caps))!=len(caps):
            raise SceneError('Caps must be a unique list containing v0 and/or v1')
        instances=obj.get('instances',[{'offset':[0,0,0],'scale':[1,1,1]}])
        if not isinstance(instances,list) or not 1<=len(instances)<=16:raise SceneError('A surface requires 1-16 instances when specified')
        for instance in instances:
            if not isinstance(instance,dict):raise SceneError('Invalid instance fields')
            fields({k:v for k,v in instance.items() if k!='rotation'},'offset scale','instance')
            vector(instance['offset'],'instance offset')
            if 'rotation' in instance:
                angles=instance['rotation']
                if not isinstance(angles,list) or len(angles)!=3:raise SceneError('Instance rotation needs three radian angles')
                for angle in angles:_number(angle,-2*math.pi,2*math.pi,'instance rotation')
            scale=instance['scale']
            if not isinstance(scale,list) or len(scale)!=3:raise SceneError('Instance scale needs three positive values')
            for x in scale:_number(x,.05,8,'instance scale')
        copies=len(instances);placements+=copies
        if not isinstance(obj['id'],str) or not _LAYER_ID.fullmatch(obj['id']) or obj['id'] in ids:raise SceneError('Surface IDs must be unique, 1-40 characters, using only letters, digits, underscore or hyphen')
        ids.add(obj['id']);fields(obj['position'],'x y z','surface position')
        compiled=compile_surface(obj)
        if any('rotation' in p for p in instances):compiled['cost']+=60
        if 'assembly' in obj:
            if not isinstance(obj['assembly'],str) or obj['assembly'] not in assemblies:
                raise SceneError('Surface assembly must identify an existing assembly')
            compiled['cost']+=assemblies[obj['assembly']]['cost']
        detail_work+=compiled.get('detail_cost',0)*copies
        segments=obj['segments']
        if not isinstance(segments,list) or len(segments)!=2:raise SceneError('Surface segments require two integers')
        _number(segments[0],4,128,'u segments',True);_number(segments[1],4,96,'v segments',True)
        if 'loft' in obj and (segments[0]%len(obj['loft'][0]['points']) or segments[1]%(len(obj['loft'])-1)):
            raise SceneError('Loft segments must align: u multiple of ring point count, v multiple of section intervals')
        count=segments[0]*segments[1];cells+=count*copies;work+=count*compiled['cost']*copies
        # Fan triangles and bounded boundary-average sampling consume the same
        # budgets as the side mesh. Do not make closure free or raise limits.
        cells+=copies*len(caps)*((segments[0]+1)//2)
        work+=copies*len(caps)*6*(segments[0]+1)*compiled['cost']
        color(obj['color']);color(obj['color_high'])
        _number(obj['roughness'],.04,1,'roughness');_number(obj['metalness'],0,1,'metalness');_number(obj['emission'],0,3,'emission')
    if placements>64:raise SceneError('World exceeds 64 total surface instances')
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
    assemblies=compile_assemblies(scene.get('assemblies',[]))
    result=[]
    for obj in scene['objects']:
        compiled={k:v for k,v in compile_surface(obj).items() if k not in ('cost','detail_cost')}
        if 'assembly' in obj:compiled['assembly']=assemblies[obj['assembly']]['glsl']
        result.append(compiled)
    return result


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
    'objects':{'type':'array','minItems':1,'maxItems':MAX_SURFACES,'items':obj_schema({'id':{'type':'string','minLength':1,'maxLength':40,'pattern':_LAYER_ID.pattern},'position':obj_schema({'x':TEXT,'y':TEXT,'z':TEXT}),
        'segments':{'type':'array','items':{'type':'integer'},'minItems':2,'maxItems':2},'color':TEXT,'color_high':TEXT,'color_mix':TEXT,
        'roughness':NUM,'metalness':NUM,'emission':NUM})}})
# Optional: absent in older plans, so it stays out of the required list.
WORLD_SCHEMA['properties']['text_references']={'type':'array','minItems':1,'maxItems':4,
    'description':'Optional. Cite recovered text evidence that shaped this world. asset_id is a text/ZIP asset you ran rekindra_recover on; evidence_ids are its evidence_id values; interpretation is YOUR reading of that evidence (stored as agent interpretation, never as recovered content).',
    'items':obj_schema({'asset_id':TEXT,
        'evidence_ids':{'type':'array','minItems':1,'maxItems':4,'uniqueItems':True,'items':{'type':'string','pattern':_EVIDENCE_ID.pattern}},
        'interpretation':{'type':'string','minLength':1,'maxLength':300}})}
# Optional studio-light controls preserve all existing v2 plans.
WORLD_SCHEMA['properties']['camera']['items']['properties']['cut']={'type':'boolean','description':'Optional shot cut at this exact key time. Hold previous pose until this instant, then jump without resetting object time. First key cannot cut; absent/false interpolates normally.'}
WORLD_SCHEMA['properties']['environment']['properties'].update({
    'occlusion_strength':{'type':'number','minimum':0,'maximum':1,'description':'Optional screen-space indirect-light occlusion, default0. Does not shadow direct lights or emission; offscreen geometry is unavailable.'},
    'occlusion_radius':{'type':'number','minimum':.05,'maximum':4,'description':'Indirect occlusion radius in world units, default1. Only used when strength>0.'},
    'point_lights':{'type':'array','maxItems':4,'description':'Optional static unshadowed local lights. Finite-range inverse-square illumination; not attached to emissive meshes.',
        'items':obj_schema({'position':VEC,'color':TEXT,'intensity':{'type':'number','minimum':0,'maximum':200},'range':{'type':'number','minimum':.1,'maximum':80}})},
    'fill_color':{'type':'string','description':'Optional unshadowed fill light color; default #B8D1FF.'},
    'fill_direction':VEC,
    'fill_strength':{'type':'number','minimum':0,'maximum':2,'description':'Optional fill intensity, default 0.25. Set 0 for no fill.'},
    'exposure':{'type':'number','minimum':.25,'maximum':4,'description':'Optional scene exposure multiplier, default 1.'},
    'ambient_strength':{'type':'number','minimum':0,'maximum':2,'description':'Diffuse ambient intensity only, default1. Lower for stronger form contrast; does not change key/fill/emission or sky specular.'},
    'ground_color':{'type':'string','description':'Approximate lower hemisphere diffuse color, default #342A20. Does not sample geometry or provide occlusion.'},
    'ground_strength':{'type':'number','minimum':0,'maximum':1,'description':'Blend lower-facing diffuse illumination toward ground_color, default0 (legacy sky-only ambient). Not raytraced bounce or ambient occlusion.'}})
WORLD_SCHEMA['properties']['environment']['properties']['environment_panels']={
    'type':'array','maxItems':4,
    'description':'Optional distant rectangular environment radiance lobes for broad reflections and approximate diffuse illumination. No local falloff, scene reflections, or panel shadows; sky background unchanged. Empty/omitted/off preserves legacy lighting. Size is tangent angular half-width/height (.03..1), rotation is radians about direction. Original bounded analytic approximation, not physical area-light integration.',
    'items':obj_schema({'direction':VEC,'color':TEXT,'intensity':{'type':'number','minimum':0,'maximum':16},
        'size':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'number','minimum':.03,'maximum':1}},
        'rotation':{'type':'number','minimum':-2*math.pi,'maximum':2*math.pi}})}
WORLD_SCHEMA['properties']['objects']['items']['properties']['reflection']=obj_schema({
    'strength':{'type':'number','minimum':0,'maximum':1},
    'blur':{'type':'number','minimum':0,'maximum':8}})
WORLD_SCHEMA['properties']['objects']['items']['properties']['reflection']['description']='Optional one horizontal scene reflection: y position must be a numeric constant string within +/-80, no assembly/instances/caps/loft on reflector. At most one active reflector. Strength blends reflected radiance; blur is bounded fixed pixel filtering, not physical roughness. No recursion, refraction or curved/vertical mirrors. Omit or strength0 preserves old path. Adds bounded offscreen passes; preview deadlines unchanged.'
WORLD_SCHEMA['properties']['objects']['items']['properties']['bindings']={
    'type':'array','maxItems':16,
    'description':'Optional ordered local math definitions shared by position and color expressions. Each can reference u/v/t/pi and earlier bindings. Use for opening progress, local frames and reusable geometric terms; no cycles or code.',
    'items':obj_schema({'name':{'type':'string','pattern':'^[a-z][a-z0-9_]{0,23}$'},
                        'expression':{'type':'string','minLength':1,'maxLength':512}})}
WORLD_SCHEMA['properties']['objects']['items']['properties']['color_pattern']={
    'type':'string','minLength':1,'maxLength':128,
    'description':'Optional per-pixel color blend expression using u/v/t/pi and supported math, no geometry bindings. Result clamps to0..1 and replaces vertex color_mix on side surfaces, mixing color and color_high. Solid caps retain color_mix. At most32 expression nodes; shares128 total world nodes with color_detail and bump_detail. Omit for unchanged rendering. Use for resolved pane/tile/material color patterns independent of mesh density; does not change geometry, transparency or emission strength. Avoid subpixel frequencies and inspect motion for shimmer.'}
WORLD_SCHEMA['properties']['objects']['items']['properties']['color_detail']={
    'type':'string','minLength':1,'maxLength':128,
    'description':'Optional per-pixel albedo detail expression using only u/v/t/pi and supported math, no local bindings. At most32 nodes per expression; color_pattern, color_detail and bump_detail share128 nodes across the world. Result clamps to -0.35..0.35 and multiplies base color by 1+detail. Use subtle grain/weave/material variation; does not change geometry, normals or roughness. Default absent preserves existing rendering. Avoid subpixel frequencies and animated noise unless intentional.'}
WORLD_SCHEMA['properties']['objects']['items']['properties']['bump_detail']={
    'type':'string','minLength':1,'maxLength':128,
    'description':'Optional per-pixel relief HEIGHT in world units, using u/v/t/pi and math, no bindings. <=32 expression nodes; color_pattern, color_detail and bump_detail together share128 nodes across the world. Height clamps to +/-0.1, slope magnitude to0.6. Changes lighting normals only, not silhouettes, shadow geometry, or roughness. Start .002-.02 amplitude for stone/cloth or .01-.04 for water ripples; scale frequency to surface size. Avoid subpixel frequencies, seams and sharp masks; inspect motion for shimmer. Not physical water, transparency or scene reflections.'}
WORLD_SCHEMA['properties']['objects']['items']['properties']['caps']={
    'type':'array','maxItems':2,'uniqueItems':True,'items':{'type':'string','enum':['v0','v1']},
    'description':'Optional solid end caps at v=0 and/or v=1. Use only when u wraps a closed planar convex or star-shaped ring, e.g. a beam or trunk cross-section. Generates a triangle fan to the average boundary position at current t, moving with the surface. Flat face normals; no bump/color_detail on caps. Counts toward existing geometry/work budgets. Not arbitrary concave hole repair or a guarantee against self-intersection. Omit on open cloth, terrain and water.'}
WORLD_SCHEMA['properties']['objects']['items']['properties']['instances']={
    'type':'array','minItems':1,'maxItems':16,
    'items':obj_schema({'offset':VEC,'scale':{'type':'array','minItems':3,'maxItems':3,'items':{'type':'number','minimum':.05,'maximum':8}}}),
    'description':'Optional placements of this same animated surface/material: each offset is a world vector -80..80 and scale is positive xyz .05..8. Scale local geometry about its origin, then offset. Caps/normals/shadows follow. 1-16 placements per surface, <=64 total; EVERY copy consumes the existing geometry/work budgets. Omitted means one identity placement. Use low-resolution local parts for repeated windows, supports, roof clusters or foliage. Optional static rotation follows scale and precedes offset; no per-copy hierarchy, independent animation or color. Final world coordinates clamp to +/-100; avoid clipping. Fine material math is shared, not duplicated shader source.'}
WORLD_SCHEMA['properties']['objects']['items']['properties']['instances']['items']['properties']['rotation']={
    'type':'array','minItems':3,'maxItems':3,'items':{'type':'number','minimum':-2*math.pi,'maximum':2*math.pi},
    'description':'Optional static Euler X,Y,Z radians: scale local geometry, rotate X then Y then Z about origin, add offset, then assembly chain. Omitted means no rotation. Vary leaf/branch orientations without new surface definitions; all transformed copies consume work budgets.'}
WORLD_SCHEMA['properties']['objects']['items']['properties']['instances']['description']=WORLD_SCHEMA['properties']['objects']['items']['properties']['instances']['description'].replace('then offset.','optionally rotate Euler X/Y/Z, then offset.').replace('No rotation, hierarchy,','No per-instance hierarchy,')

_ASSEMBLY_EXPR={'type':'string','minLength':1,'maxLength':128}
_ASSEMBLY=obj_schema({'id':{'type':'string','pattern':_LAYER_ID.pattern},
    'translation':obj_schema({axis:_ASSEMBLY_EXPR for axis in ('x','y','z')}),
    'rotation':obj_schema({axis:_ASSEMBLY_EXPR for axis in ('x','y','z')}),
    'pivot':VEC,'scale':{'type':'array','minItems':3,'maxItems':3,'items':{'type':'number','minimum':.05,'maximum':8}}})
_ASSEMBLY['properties']['parent']={'type':'string','description':'Optional earlier assembly ID; max4 hierarchy levels.'}
WORLD_SCHEMA['properties']['assemblies']={'type':'array','maxItems':8,'items':_ASSEMBLY,
    'description':'Shared animated frames. Each transform uses t/pi only, <=32 nodes per expression. Subtract pivot, scale, rotate Euler X then Y then Z (radians), add pivot and translation; then apply parent chain. Surface instance transforms run first. Share one frame across connected parts to preserve joints. No u/v or geometry bindings. All referenced chain work counts toward shader budgets. Optional and absent by default.'}
WORLD_SCHEMA['properties']['objects']['items']['properties']['assembly']={'type':'string','description':'Optional existing assembly ID. Geometry, cap positions, normals and shadows follow its complete transform chain.'}

WORLD_SCHEMA['properties']['objects']['items']['properties']['shading']={'type':'string','enum':['smooth','flat'],'description':'Optional normal mode, smooth by default. Flat uses each rendered triangle normal for faceted rock, cut crystal or deliberately low-poly construction. Geometry and shadow silhouettes unchanged; caps remain flat. Bump detail may still perturb lighting normals. Choose segments to represent intentional planes; flat shading cannot create cracks or repair bad geometry.'}

WORLD_SCHEMA['properties']['objects']['items']['properties']['loft']={'type':'array','minItems':2,'maxItems':8,'description':'Optional ordered convex cross-sections. Supplies loft_x/loft_y/loft_z to position and bindings. Equal3-16point counts, same winding, heights increasing >=0.0001. Points are x,z, no repeated closing vertex. Rings close automatically. u segments must be a multiple of point count; v segments a multiple of sections-1. Use position x:loft_x,y:loft_y,z:loft_z then optional bounded deformation. Static sections interpolate linearly in v; instance/assembly transforms still apply. Work charged per copy/cap. Convex source rings do not guarantee deformed geometry is collision-free.','items':obj_schema({'height':{'type':'number','minimum':-80,'maximum':80},'points':{'type':'array','minItems':3,'maxItems':16,'items':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'number','minimum':-80,'maximum':80}}}})}
