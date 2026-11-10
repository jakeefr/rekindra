"""Scene v2: source-grounded procedural geometry with bounded GPU work."""
import copy
import functools
import math
import re
from .scenes import SceneError, _number, _text, _COLOR, _LAYER_ID
from .expressions import compile_expression, sampler, FUNCTIONS
from .assemblies import compile_assemblies
from .lofts import compile_loft
from .constructs import compile_constructs,_f
from .rigs import rig_context,resolve_mount,POSES,JOINTS,PROPORTIONS,ANCHORS,PARTS

MAX_SURFACES = 24
_CITED_ID_CHARS = 64


class UndeclaredWorldSource(SceneError):
    """A reference cites an image outside asset_ids. Advice only: the list is never filled in."""

    def __init__(self,cited):
        self.cited=[c[:_CITED_ID_CHARS] for c in dict.fromkeys(cited)]
        super().__init__(f'{self.subject()} but asset_ids does not list {"it" if len(self.cited)==1 else "them"}')

    def subject(self):
        return f'scene references asset{"" if len(self.cited)==1 else "s"} '+', '.join(f"'{c}'" for c in self.cited)


def shown(value):
    """A short, single-line echo of a rejected value for an error message."""
    text=value if isinstance(value,str) else f'{type(value).__name__} {value!r}'
    text=''.join(c if c.isprintable() else '?' for c in text)
    return repr(text[:40]+('...' if len(text)>40 else '')) if isinstance(value,str) else text[:48]


def fields(value,names,label,optional=''):
    wanted=names.split();allowed=optional.split()
    if not isinstance(value,dict):
        raise SceneError(f'Invalid {label} fields: pass a JSON object with {", ".join(wanted)}; got {shown(value)}')
    if set(wanted)<=set(value)<=set(wanted)|set(allowed):return
    missing=[k for k in wanted if k not in value]
    extra=sorted(shown(k) for k in value if k not in wanted and k not in allowed)[:8]
    raise SceneError(f'Invalid {label} fields.'+(f' Missing: {", ".join(missing)}.' if missing else '')
                     +(f' Not accepted here: {", ".join(extra)}.' if extra else '')
                     +f' Required {label} fields: {", ".join(wanted)}'
                     +(f'. Optional {label} fields: {", ".join(allowed)}' if allowed else ''))


def vector(value,label):
    if not isinstance(value,list) or len(value)!=3:raise SceneError(f'{label} requires three coordinates: pass an array of three numbers [x, y, z]; got {shown(value)}')
    for x in value:_number(x,-80,80,label)
    return value


def color(value):
    if not isinstance(value,str) or not _COLOR.fullmatch(value):raise SceneError(f'World colors must be #RRGGBB strings with six hex digits, like "#1A2B3C"; got {shown(value)}')


def compile_surface(obj,context=None):
    bindings=obj.get('bindings',[])
    if not isinstance(bindings,list) or len(bindings)>16:raise SceneError('Surface allows at most 16 local bindings: bindings is an array of 0-16 {name, expression} objects; got '
                         +(f'{len(bindings)} items' if isinstance(bindings,list) else shown(bindings)))
    names={};definitions=[];cost=0
    if 'loft' in obj:
        loft=compile_loft(obj['loft']);names.update(loft['names']);definitions.append(loft['definitions']);cost+=loft['cost']
    mount=resolve_mount(obj,context) if 'mount' in obj else None;cards=None
    for part in compile_constructs(obj,dict(context or {},mount=mount) if context or mount else None):
        names.update(part['names']);definitions.append(part['definitions']);cost+=part['cost'];cards=part.get('cards',cards)
    for binding in bindings:
        fields(binding,'name expression','local binding')
        name=binding['name']
        why=(None if isinstance(name,str) and re.fullmatch('[a-z][a-z0-9_]{0,23}',name) else
             f'has {len(name)} characters; the limit is 24' if isinstance(name,str) and re.fullmatch('[a-z][a-z0-9_]*',name)
             else 'is not a lowercase identifier')
        if why is None and name in names:
            why='is already defined on this surface'+('' if any(b is not binding and isinstance(b,dict) and b.get('name')==name for b in bindings)
                                                      else " by the surface's loft")
        if why is None and (name in FUNCTIONS or name in ('u','v','t','pi')):why='is a reserved math name'
        if why:
            raise SceneError(f'Binding names must be unique lowercase identifiers, not reserved math names: got {shown(name)}, which {why}. '
                             'Use a lowercase letter then up to 23 lowercase letters, digits or underscores, not u, v, t, pi or '
                             +', '.join(FUNCTIONS))
        # Only prior names are in scope. No recursion, cycles, forward references,
        # caller-supplied shader identifiers, or executable code are accepted.
        value=compile_expression(binding['expression'],names)
        shader_name=f'rk_local_{len(names)}';names[name]=shader_name
        definitions.append(f'float {shader_name}={value["glsl"]};');cost+=value['cost']
    pos=[compile_expression(obj['position'][k],names) for k in ('x','y','z')]
    blend=compile_expression(obj['color_mix'],names)
    position=[p['glsl'] for p in pos]
    if mount:
        # The surface's own coordinates are turned with the rig and moved to its attachment point.
        definitions.append('vec3 rk_ml=vec3('+','.join(position)+');');cost+=24
        position=[f'({_f(mount["origin"][i])}+dot(vec3({",".join(_f(x) for x in mount["matrix"][i])}),rk_ml))' for i in range(3)]
    result={'position':position,'color_mix':blend['glsl'],
            'definitions':'\n'.join(definitions),'cost':cost+sum(p['cost'] for p in pos)+blend['cost']}
    if cards:result['cards']=cards
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


@functools.lru_cache(maxsize=512)
def _refuse_stripes(source):
    # A pure function of the expression text, and one create/preview/export cycle validates the
    # same scene many times, so a pattern that passed is not sampled again. A refusal raises and
    # is therefore never cached.
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
        if isinstance(aid,str) and aid in seen:
            raise SceneError(f'Invalid or repeated text reference asset_id: {shown(aid)} already appears in text_references; '
                             'use one entry per source and put all of its evidence_ids in that entry')
        if not isinstance(aid,str) or not 1<=len(aid)<=64:raise SceneError('Invalid or repeated text reference asset_id: pass the asset_id of one recovered text source, '
                                                                                        f'1-64 characters, once per source; got {shown(aid)}')
        seen.add(aid)
        ids=ref['evidence_ids']
        if (not isinstance(ids,list) or not 1<=len(ids)<=4
                or any(not isinstance(e,str) or not _EVIDENCE_ID.fullmatch(e) for e in ids) or len(set(ids))!=len(ids)):
            raise SceneError('Each text reference needs 1-4 unique evidence_id values from rekindra_recover: evidence_ids is an array of '
                             'strings shaped ev- plus 24 lowercase hex digits, copied exactly from evidence[].evidence_id; '
                             f'got {shown(ids)}')
        _text(ref['interpretation'],300,'text reference interpretation')
        if not ref['interpretation'].strip():raise SceneError('Text reference interpretation cannot be blank')


# Optional screen-space finish applied after the 3D render. Every field is optional and absent by default.
HIGHLIGHT_MODES=('soft',)
ATMOSPHERE_RANGES=(('bloom',0,2),('halo',0,2),('haze_density',0,.3),('haze_height',.25,80),('haze_floor',-80,80),('vignette',0,1),('grain',0,.08))


def validate_world(value,asset_ids):
    if not isinstance(value,dict):raise SceneError(f'Invalid world fields: scene must be a JSON object, not JSON-encoded text; got {shown(value)}')
    fields(value,'schema_version title mood reason duration width height seed environment camera objects','world','references text_references assemblies rigs')
    s=copy.deepcopy(value)
    assemblies=compile_assemblies(s.get('assemblies',[]))
    if 'text_references' in s:_text_references(s['text_references'])
    if type(s['schema_version']) is not int or s['schema_version']!=2:raise SceneError(f'Unsupported world version: schema_version must be the integer 2; got {shown(s["schema_version"])}')
    for name,limit in (('title',100),('mood',100),('reason',600)):_text(s[name],limit,name)
    _number(s['duration'],4,30,'duration');_number(s['width'],1280,1280,'width',True);_number(s['height'],720,720,'height',True)
    _number(s['seed'],0,2**31-1,'seed',True)
    # A world built from text evidence alone has no image to interpret.
    s.setdefault('references',[])
    if not isinstance(s['references'],list) or len(s['references'])>6:raise SceneError('World needs 1-6 source interpretations')
    if not s['references'] and asset_ids:raise SceneError('Every selected image needs a source interpretation in references: add one {asset_id, observed, created} '
                                                           f'entry to scene.references for each of asset_ids {sorted(asset_ids)}')
    if not s['references'] and 'text_references' not in s:raise SceneError('World needs 1-6 image source interpretations, or text_references when it is built from text evidence alone')
    used=set()
    for ref in s['references']:
        fields(ref,'asset_id observed created','source interpretation')
        if not isinstance(ref['asset_id'],str):
            raise SceneError(f'Invalid or repeated world source: references[].asset_id must be a string from asset_ids {sorted(asset_ids)}; got {shown(ref["asset_id"])}')
        if ref['asset_id'] not in asset_ids:
            # Name every miss at once so one corrected call can fix them all.
            raise UndeclaredWorldSource([r['asset_id'] for r in s['references'] if isinstance(r,dict) and isinstance(r.get('asset_id'),str) and r['asset_id'] not in asset_ids])
        if ref['asset_id'] in used:
            raise SceneError(f'Invalid or repeated world source: {shown(ref["asset_id"])} appears twice in references; use one entry per image')
        used.add(ref['asset_id'])
        for key in ('observed','created'):
            _text(ref[key],500,key)
            if not ref[key].strip():raise SceneError('Explain observed and created features')
    env=s['environment']
    fields(env,'sky_top sky_bottom fog_color fog_density light_color light_direction sun_size sun_strength','environment',
           'fill_color fill_direction fill_strength exposure ambient_strength ground_color ground_strength point_lights occlusion_strength occlusion_radius environment_panels atmosphere')
    if 'atmosphere' in env:
        atmosphere=env['atmosphere']
        fields(atmosphere,'','atmosphere',' '.join(k for k,_,_ in ATMOSPHERE_RANGES)+' haze_color highlights')
        if not atmosphere:raise SceneError('Atmosphere needs at least one of bloom, halo, haze_density, vignette, grain or highlights; omit atmosphere for a plain render')
        if 'highlights' in atmosphere and atmosphere['highlights'] not in HIGHLIGHT_MODES:
            raise SceneError('Atmosphere highlights must be "soft"; omit it for the standard tone curve')
        for key,low,high in ATMOSPHERE_RANGES:
            if key in atmosphere:_number(atmosphere[key],low,high,'atmosphere '+key.replace('_',' '))
        if 'haze_color' in atmosphere:color(atmosphere['haze_color'])
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
        fields(key,'at eye target fov','camera state','cut')
        if 'cut' in key and type(key['cut']) is not bool:raise SceneError('Camera cut must be a boolean')
        if previous is None and key.get('cut',False):raise SceneError('The first camera state cannot be a cut')
        _number(key['at'],0,s['duration'],'camera time');_number(key['fov'],15,100,'field of view')
        if key['at']<=last:
            raise SceneError(f'Camera times must increase: a state at {key["at"]} follows one at {last}; order states by at, each later than the one before')
        last=key['at'];eye=vector(key['eye'],'camera eye');target=vector(key['target'],'camera target')
        delta=[a-b for a,b in zip(eye,target)]
        if sum(x*x for x in delta)<.01:raise SceneError('Camera eye and target must be distinct')
        if previous is not None and not key.get('cut',False):
            step=[a-b for a,b in zip(delta,previous)];length=sum(x*x for x in step)
            u=max(0,min(1,-sum(a*b for a,b in zip(previous,step))/length)) if length else 0
            if sum((a+u*b)**2 for a,b in zip(previous,step))<.01:raise SceneError(f'Camera crosses its target between states: the straight move into the state at {key["at"]} passes through its target. '
                                                                                         'Add an intermediate state that goes around the target, or set cut:true on this state')
        previous=delta
    if camera[0]['at']!=0 or camera[-1]['at']!=s['duration']:raise SceneError(f'Camera must span the full duration: the first state needs at 0 and the last needs at {s["duration"]}; got {camera[0]["at"]} and {camera[-1]["at"]}')
    context=rig_context(s)
    if not isinstance(s['objects'],list) or not 1<=len(s['objects'])<=MAX_SURFACES:
        raise SceneError(f'World requires 1-{MAX_SURFACES} surfaces')
    ids=set();cells=work=detail_work=placements=active_reflectors=image_materials=0
    for obj in s['objects']:
        fields(obj,'id position segments color color_high color_mix roughness metalness emission','surface',
               'bindings color_detail bump_detail color_pattern caps instances assembly shading loft reflection glow soft foliage material_image feathers drape ring figure wing mount')
        if 'soft' in obj:
            soft=obj['soft'];fields(soft,'u v','soft edge','breakup')
            if 'glow' not in obj:raise SceneError('soft feathers the edges of a glow surface: add glow to this surface, or remove soft')
            _number(soft['u'],0,1,'soft u');_number(soft['v'],0,1,'soft v');_number(soft.get('breakup',0),0,1,'soft breakup')
        if 'foliage' in obj:
            foliage=obj['foliage'];fields(foliage,'leaf_size density','foliage','variation rest_time')
            if 'glow' in obj or 'reflection' in obj:raise SceneError('foliage is a solid leaf mass: it cannot be combined with glow or reflection')
            _number(foliage['leaf_size'],.03,2,'foliage leaf_size');_number(foliage['density'],.2,1,'foliage density');_number(foliage.get('variation',.5),0,1,'foliage variation');_number(foliage.get('rest_time',0),0,s['duration'],'foliage rest_time')
        if 'material_image' in obj:
            material=obj['material_image'];fields(material,'asset_id crop','material image','repeat strength')
            if not isinstance(material['asset_id'],str) or material['asset_id'] not in used:
                raise SceneError(f'material_image asset_id must be one of the images in scene.references {sorted(used)}; got {shown(material["asset_id"])}')
            crop=material['crop']
            if not isinstance(crop,list) or len(crop)!=4:raise SceneError('material_image crop needs [left, top, width, height] as fractions of the image, each 0-1')
            _number(crop[0],0,.98,'material_image crop left');_number(crop[1],0,.98,'material_image crop top')
            _number(crop[2],.02,1,'material_image crop width');_number(crop[3],.02,1,'material_image crop height')
            if crop[0]+crop[2]>1.000001 or crop[1]+crop[3]>1.000001:raise SceneError('material_image crop must stay inside the image: left+width and top+height may not exceed 1')
            repeat=material.get('repeat',[1,1])
            if not isinstance(repeat,list) or len(repeat)!=2:raise SceneError('material_image repeat needs [across u, across v]')
            for x in repeat:_number(x,.1,32,'material_image repeat')
            _number(material.get('strength',1),0,1,'material_image strength')
            image_materials+=1
            if image_materials>4:raise SceneError('World allows at most 4 surfaces with material_image')
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
        if 'glow' in obj:
            _number(obj['glow'],.05,3,'glow')
            if 'reflection' in obj:raise SceneError('A glow surface cannot be the reflector')
        if 'shading' in obj and (not isinstance(obj['shading'],str) or obj['shading'] not in ('smooth','flat')):
            raise SceneError(f'Surface shading must be smooth or flat: pass "smooth" or "flat", or omit it; got {shown(obj["shading"])}')
        caps=obj.get('caps',[])
        if not isinstance(caps,list) or len(caps)>2 or any(not isinstance(c,str) or c not in ('v0','v1') for c in caps) or len(set(caps))!=len(caps):
            raise SceneError(f'Caps must be a unique list containing v0 and/or v1: pass ["v0"], ["v1"] or ["v0","v1"], or omit caps; got {shown(caps)}')
        instances=obj.get('instances',[{'offset':[0,0,0],'scale':[1,1,1]}])
        if not isinstance(instances,list) or not 1<=len(instances)<=16:raise SceneError('A surface requires 1-16 instances when specified')
        for instance in instances:
            fields(instance,'offset scale','instance','rotation')
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
        compiled=compile_surface(obj,context)
        if any('rotation' in p for p in instances):compiled['cost']+=60
        if 'assembly' in obj:
            if not isinstance(obj['assembly'],str) or obj['assembly'] not in assemblies:
                raise SceneError(f'Surface assembly must identify an existing assembly: got {shown(obj["assembly"])}; scene.assemblies defines '
                                 +(str(sorted(assemblies)) if assemblies else 'none, so add the assembly there or remove this field'))
            compiled['cost']+=assemblies[obj['assembly']]['cost']
        detail_work+=compiled.get('detail_cost',0)*copies
        segments=obj['segments']
        if not isinstance(segments,list) or len(segments)!=2:raise SceneError(f'Surface segments require two integers: pass [u, v] with u 4-128 and v 4-96; got {shown(segments)}')
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
    result=[];context=rig_context(scene)
    for obj in scene['objects']:
        compiled={k:v for k,v in compile_surface(obj,context).items() if k not in ('cost','detail_cost')}
        if 'assembly' in obj:compiled['assembly']=assemblies[obj['assembly']]['glsl']
        result.append(compiled)
    return result


def obj_schema(properties):return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
NUM={'type':'number'}
TEXT={'type':'string'}
VEC={'type':'array','items':{'type':'number','minimum':-80,'maximum':80},'minItems':3,'maxItems':3}
HEX={'type':'string','pattern':'^#[0-9a-fA-F]{6}$','description':'Color as #RRGGBB, six hex digits.'}
EXPR={'type':'string','minLength':1,'maxLength':512,'description':'One arithmetic expression as text (1-512 characters) over u, v, t, pi, bindings and the supported math functions; a constant is written as text too, like "0.5".'}
def ranged(low,high):return {'type':'number','minimum':low,'maximum':high}
WORLD_SCHEMA=obj_schema({
    'schema_version':{'type':'integer','const':2},'title':{'type':'string','maxLength':100},
    'mood':{'type':'string','maxLength':100},'reason':{'type':'string','maxLength':600},
    'duration':{'type':'number','minimum':4,'maximum':30},'width':{'type':'integer','const':1280},'height':{'type':'integer','const':720},'seed':{'type':'integer','minimum':0,'maximum':2**31-1},
    'references':{'type':'array','minItems':0,'maxItems':6,'items':obj_schema({'asset_id':{'type':'string','description':'One of the asset_ids passed beside scene.'},
        'observed':{'type':'string','maxLength':500},'created':{'type':'string','maxLength':500}})},
    'environment':obj_schema({'sky_top':HEX,'sky_bottom':HEX,'fog_color':HEX,'fog_density':ranged(0,.15),'light_color':HEX,'light_direction':VEC,'sun_size':ranged(.003,.15),'sun_strength':ranged(0,4)}),
    'camera':{'type':'array','minItems':2,'maxItems':12,'description':'Keys in strictly increasing at order, first at 0, last at duration.',
        'items':obj_schema({'at':{'type':'number','minimum':0,'description':'Seconds from 0 to duration.'},'eye':VEC,'target':VEC,'fov':ranged(15,100)})},
    'objects':{'type':'array','minItems':1,'maxItems':MAX_SURFACES,'items':obj_schema({'id':{'type':'string','minLength':1,'maxLength':40,'pattern':_LAYER_ID.pattern},'position':obj_schema({'x':EXPR,'y':EXPR,'z':EXPR}),
        'segments':{'type':'array','items':{'type':'integer','minimum':4,'maximum':128},'minItems':2,'maxItems':2,'description':'[u, v] whole numbers: u 4-128, v 4-96.'},'color':HEX,'color_high':HEX,'color_mix':EXPR,
        'roughness':ranged(.04,1),'metalness':ranged(0,1),'emission':ranged(0,3)})}})
# A world from text evidence alone has no image reference; validate_world then requires text_references.
WORLD_SCHEMA['required'].remove('references')
WORLD_SCHEMA['properties']['references']['description']='One entry per selected image: what you observed and what you created. Leave empty or omit only when the world is built from text evidence alone, and then cite that evidence in text_references.'
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
        'items':obj_schema({'position':VEC,'color':HEX,'intensity':{'type':'number','minimum':0,'maximum':200},'range':{'type':'number','minimum':.1,'maximum':80}})},
    'fill_color':{**HEX,'description':'Optional unshadowed fill light color as #RRGGBB; default #B8D1FF.'},
    'fill_direction':VEC,
    'fill_strength':{'type':'number','minimum':0,'maximum':2,'description':'Optional fill intensity, default 0.25. Set 0 for no fill.'},
    'exposure':{'type':'number','minimum':.25,'maximum':4,'description':'Optional scene exposure multiplier, default 1.'},
    'ambient_strength':{'type':'number','minimum':0,'maximum':2,'description':'Diffuse ambient intensity only, default1. Lower for stronger form contrast; does not change key/fill/emission or sky specular.'},
    'ground_color':{**HEX,'description':'#RRGGBB. Approximate lower hemisphere diffuse color, default #342A20. Does not sample geometry or provide occlusion.'},
    'ground_strength':{'type':'number','minimum':0,'maximum':1,'description':'Blend lower-facing diffuse illumination toward ground_color, default0 (legacy sky-only ambient). Not raytraced bounce or ambient occlusion.'}})
WORLD_SCHEMA['properties']['environment']['properties']['environment_panels']={
    'type':'array','maxItems':4,
    'description':'Optional distant rectangular environment radiance lobes for broad reflections and approximate diffuse illumination. No local falloff, scene reflections, or panel shadows; sky background unchanged. Empty/omitted/off preserves legacy lighting. Size is tangent angular half-width/height (.03..1), rotation is radians about direction. Original bounded analytic approximation, not physical area-light integration.',
    'items':obj_schema({'direction':VEC,'color':HEX,'intensity':{'type':'number','minimum':0,'maximum':16},
        'size':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'number','minimum':.03,'maximum':1}},
        'rotation':{'type':'number','minimum':-2*math.pi,'maximum':2*math.pi}})}
WORLD_SCHEMA['properties']['environment']['properties']['atmosphere']={
    'type':'object','additionalProperties':False,'minProperties':1,
    'description':'Optional finishing pass over the rendered 3D frame; omit for a plain render. USE IT when the sources show night, fog, mist, lamps, glow or soft light: without it emissive surfaces are hard-edged shapes on a flat background. bloom: soft glow spilling around emissive surfaces (emission>=1) and glow surfaces. halo: wide light halos that grow with fog/haze density and distance, plus a lit mist sphere around every point_lights entry reaching about a third of the range of that light, so put a point light at each lamp and keep its range to the pool that lamp really lights, so its colour stays local to it. haze_density with haze_color: mist that thickens with distance and tints far things toward haze_color; take haze_color from the dark unlit tones of the source, never from its lamps. haze_height makes the mist thin out above haze_floor (ground mist). vignette darkens the frame corners. grain adds fine film grain to exported video (review frames omit it). Typical foggy night: {"bloom":0.9,"halo":1.0,"haze_density":0.012,"haze_color":"<dark mist color from the source>","haze_height":5,"vignette":0.35,"grain":0.02}. Haze brightens the whole frame toward haze_color, so at night keep haze_color dark and haze_density at or below 0.02.',
    'properties':{
        'bloom':{'type':'number','minimum':0,'maximum':2,'description':'Glow around emissive and glow surfaces, default 0. Start 0.6-1.2.'},
        'halo':{'type':'number','minimum':0,'maximum':2,'description':'Wide halos around lights, default 0. Faint in clear air and much wider with fog_density or haze_density above 0; the mist sphere around a point light needs one of them. Start 0.8-1.4.'},
        'haze_color':{**HEX,'description':'#RRGGBB mist color, default fog_color. Sample it from the dark, unlit parts of the source image; lamp colour belongs on the lamps and their point lights, not in the haze.'},
        'haze_density':{'type':'number','minimum':0,'maximum':.3,'description':'Mist per world unit of distance, default 0. Light mist 0.01, dense fog 0.05.'},
        'haze_height':{'type':'number','minimum':.25,'maximum':80,'description':'Optional height in world units over which mist thins above haze_floor. Omit for mist that is equally thick at every height.'},
        'haze_floor':{'type':'number','minimum':-80,'maximum':80,'description':'World y where height mist is thickest, default 0.'},
        'vignette':{'type':'number','minimum':0,'maximum':1,'description':'Corner darkening, default 0. Start 0.3.'},
        'grain':{'type':'number','minimum':0,'maximum':.08,'description':'Film grain amplitude, default 0. Subtle 0.015-0.03. Fixed by seed and frame.'},
        'highlights':{'type':'string','enum':list(HIGHLIGHT_MODES),'description':'Optional "soft": the brightest tones roll off toward white instead of clipping, and glow layers combine without saturating. Omit for the standard tone curve. Use it when a bright lamp, flame or glowing core should keep its shape and colour rather than flatten into a white blob.'}}}
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

WORLD_SCHEMA['properties']['objects']['items']['properties']['soft']=obj_schema({'u':{'type':'number','minimum':0,'maximum':1},'v':{'type':'number','minimum':0,'maximum':1},'breakup':{'type':'number','minimum':0,'maximum':1}})
WORLD_SCHEMA['properties']['objects']['items']['properties']['soft']['required']=['u','v']
WORLD_SCHEMA['properties']['objects']['items']['properties']['soft']['description']=('Optional, glow surfaces only. Fades the light toward the surface edges so a figure of light, wing, aura or halo has no hard outline. '
    'u and v give the faded share of the surface from each pair of edges (0 none, 1 fades all the way to the middle). breakup 0-1 frays the fade into fine streaks that run along v, for feathers or wisps. '
    'Use it whenever a source shows light with soft or feathered edges; a glow sheet without soft has a hard cut edge.')
WORLD_SCHEMA['properties']['objects']['items']['properties']['foliage']=obj_schema({'leaf_size':{'type':'number','minimum':.03,'maximum':2},'density':{'type':'number','minimum':.2,'maximum':1},'variation':{'type':'number','minimum':0,'maximum':1},'rest_time':{'type':'number','minimum':0,'maximum':30}})
WORLD_SCHEMA['properties']['objects']['items']['properties']['foliage']['required']=['leaf_size','density']
WORLD_SCHEMA['properties']['objects']['items']['properties']['foliage']['description']=('Optional. Turns a closed surface into a leaf mass: leaf-sized patches vary between color and color_high and face different ways, and gaps are cut out so the outline is ragged and you see into the canopy. '
    'leaf_size is the patch size in world units (0.1-0.3 for a tree seen from the ground), density 0.2 sparse to 1 nearly solid, variation 0-1 colour spread. Take color and color_high from two leaf tones in the source. '
    'Build a canopy from several overlapping lumpy masses (instances) on a tapered trunk with a few branch surfaces, never one smooth ball on a pole. The leaf pattern is fixed to the surface as it stands at rest_time seconds (default 0) and moves with it; if the canopy grows in or unfolds, set rest_time to a time within the scene when it has its full shape. Not with glow or reflection. Shadows stay solid.')
WORLD_SCHEMA['properties']['objects']['items']['properties']['material_image']=obj_schema({'asset_id':{'type':'string'},'crop':{'type':'array','minItems':4,'maxItems':4,'items':{'type':'number','minimum':0,'maximum':1}},
    'repeat':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'number','minimum':.1,'maximum':32}},'strength':{'type':'number','minimum':0,'maximum':1}})
WORLD_SCHEMA['properties']['objects']['items']['properties']['material_image']['required']=['asset_id','crop']
WORLD_SCHEMA['properties']['objects']['items']['properties']['material_image']['description']=('Optional. Takes this surface colour from a crop of one of the recovered images in scene.references, so leaves, bark, paving, stone or mist carry the real texture of the source. '
    'crop is [left, top, width, height] as fractions of the image; at repeat 1 the top of the crop lands at v=1 and its left at u=0 (repeats mirror, so every second tile is flipped). For a material, pick a patch that is all one material. repeat [u,v] tiles it across the surface (mirrored between tiles; default 1,1. Use an even count across a direction that wraps around, or the two ends meet in a seam). strength 0-1 mixes it over color/color_high (default 1). '
    'Lighting, shadows and foliage still apply, and the page lists it as recovered material. Photo materials are for surface texture only: ground, bark, leaves, stone, fabric, sky detail. Never show the subject of a source image as a photo on a flat or camera-facing surface: build the subject from geometry (figure, wing, feathers, drape, ring, loft, soft glow forms) and keep photos for the surfaces around it. The preview report flags a photo used as the subject. At most 4 surfaces.')
WORLD_SCHEMA['properties']['objects']['items']['properties']['feathers']={'type':'object','additionalProperties':False,'required':['count','spread','length'],'properties':{
    'count':{'type':'integer','minimum':2,'maximum':48},'spread':{'type':'number','minimum':.05,'maximum':40},'length':{'type':'number','minimum':.02,'maximum':40},
    'curve':{'type':'number'},'fan':{'type':'number'},'taper':{'type':'number','minimum':.1,'maximum':4},'overlap':{'type':'number','minimum':0,'maximum':1},
    'layer':{'type':'number','minimum':0,'maximum':2},'open':{'type':'string'},'mirror':{'type':'boolean'}},
    'description':'Optional construction field: an array of many small tapered cards set along a curved spine, for wings, petals, leaves, scales and fins. Supplies feather_x/feather_y/feather_z to the position expressions (local, in the x-y plane, spine starting at the origin; add your own offset, scale or rotation in position). count 2-48 cards; spread is the spine length; curve bends the spine (radians over its length); fan turns each card further than the last (radians at the tip; 0 keeps them parallel, hanging down from the spine); length is the card length at the root and taper scales it toward the tip (below 1 shortens); overlap 0-1 widens cards over their neighbours; layer staggers them in depth. open is an expression over t from 0 (folded: short spine, cards parallel) to 1 (unfolded: full spread, curve and fan), so a wing or flower can open over time, like "clamp(t/8,0,1)". mirror flips x for the opposite side. u segments must be a multiple of count (2-4 per card). Layer two or three arrays of different length for depth. Works with glow and soft for a luminous, soft-edged result.'}
WORLD_SCHEMA['properties']['objects']['items']['properties']['drape']={'type':'object','additionalProperties':False,'required':['height','top_radius','hem_radius'],'properties':{
    'height':{'type':'number','minimum':.1,'maximum':40},'top_radius':{'type':'number','minimum':.02,'maximum':20},'hem_radius':{'type':'number','minimum':.05,'maximum':40},
    'pool':{'type':'number','minimum':0,'maximum':10},'folds':{'type':'integer','minimum':0,'maximum':24},'fold_depth':{'type':'number','minimum':0,'maximum':.5}},
    'description':'Optional construction field: draped cloth, a surface that hangs from a narrow top, ripples into folds and flares to a hem. Supplies drape_x/drape_y/drape_z to the position expressions (local: top at y=height over the origin, hem on y=0). top_radius and hem_radius set the flare; folds is the number of ripples around and fold_depth their depth, growing toward the hem; pool above 0 lays the last part of the cloth flat on the ground, running outward by that distance. Use for robes, skirts, curtains, tablecloths, tents. Give v at least 12 segments. Works with glow and soft.'}
WORLD_SCHEMA['properties']['objects']['items']['properties']['ring']={'type':'object','additionalProperties':False,'required':['radius','thickness'],'properties':{
    'radius':{'type':'number','minimum':.05,'maximum':40},'thickness':{'type':'number','minimum':.005,'maximum':10},'tilt':{'type':'number'}},
    'description':'Optional construction field: a ring (torus) for halos, rims, hoops and wheels. Supplies ring_x/ring_y/ring_z to the position expressions (local, centred on the origin). radius is the ring radius and thickness the tube radius. tilt turns it about the x axis in radians: 0 lies flat like a hoop on the ground, 1.5708 stands it upright facing the camera on z. A flat ring seen from a level camera reads as a bar, so tilt it toward the viewer. Works with glow and soft.'}
WORLD_SCHEMA['properties']['rigs']={'type':'array','minItems':1,'maxItems':4,'items':{'type':'object','additionalProperties':False,'required':['id','position','height'],'properties':{
    'id':{'type':'string'},'position':{'type':'array','items':{'type':'number'},'minItems':3,'maxItems':3},'height':{'type':'number','minimum':.2,'maximum':20},'facing':{'type':'number'},
    'pose':{'anyOf':[{'type':'string','enum':sorted(POSES)},{'type':'array','items':{'type':'string','enum':sorted(POSES)},'minItems':1,'maxItems':4}]},
    'joints':{'type':'object','additionalProperties':False,'properties':{name:{'type':'array','items':{'type':'number'},'minItems':3,'maxItems':3} for name in JOINTS}},
    'proportions':{'type':'object','additionalProperties':False,'properties':{name:{'type':'number','minimum':.4,'maximum':2.5} for name in PROPORTIONS}}}},
    'description':'Optional posed skeletons for anything with a body: a person, statue, puppet, robot or upright creature. A rig draws nothing itself; a surface with the figure field draws its body masses, and other surfaces attach to it with mount. position is the ground point under it, height its standing height, facing turns it about the vertical axis in radians (0 faces +z). pose is one preset or a list combined in order: '+', '.join(sorted(POSES))+'. joints fine-tunes after the pose, each [forward, outward, twist] in radians: '+', '.join(JOINTS)+'. proportions are multipliers (default 1) for '+', '.join(PROPORTIONS)+': a long neck, short legs or a heavy build make a creature or a stylised statue. The lowest body mass always rests on the ground point. Attachment points: '+', '.join(ANCHORS)+'. Revise a pose by replacing the scene field rigs.'}
WORLD_SCHEMA['properties']['objects']['items']['properties']['figure']={'type':'object','additionalProperties':False,'required':['rig'],'properties':{
    'rig':{'type':'string'},'parts':{'type':'array','items':{'type':'string','enum':list(PARTS)},'minItems':1,'maxItems':4}},
    'description':'Optional construction field: the body of a rig, as rounded masses on its bones (a real head, neck, torso with shoulders, upper and lower arms with hands, upper and lower legs with feet). Supplies figure_x/figure_y/figure_z to the position expressions, already in world coordinates and posed: use them as the position unchanged. parts limits it to some of head, torso, arms, legs (omit for the whole body), so two surfaces on one rig can have different materials, such as skin and clothing. With all parts u segments must be 96, 112 or 128 (16 masses, at least 6 each); v 12 or more. Works with soft and glow.'}
WORLD_SCHEMA['properties']['objects']['items']['properties']['wing']={'type':'object','additionalProperties':False,'required':['span'],'properties':{
    'span':{'type':'number','minimum':.1,'maximum':40},'side':{'type':'string','enum':['left','right']},'raise':{'type':'number','minimum':-.6,'maximum':1.5},'open':{'type':'string'},
    'count':{'type':'integer','minimum':4,'maximum':24},'rows':{'type':'integer','minimum':1,'maximum':3},'feather_length':{'type':'number','minimum':.02,'maximum':40},
    'width':{'type':'number','minimum':.4,'maximum':3},'overlap':{'type':'number','minimum':0,'maximum':1},'layer':{'type':'number','minimum':0,'maximum':2}},
    'description':'Optional construction field: one whole wing, built as layered rows of broad feathers on an arm: long flight feathers behind, shorter rows covering their bases. Supplies wing_x/wing_y/wing_z to the position expressions (local, in the x-y plane, root at the origin, reaching toward +x for side right and -x for side left). span is the arm length from root to tip; raise is the arm angle above horizontal in radians when open (about 1 is raised high in a V, 0.3 is spread wide, negative droops); open is an expression over t from 0 (folded down against the body) to 1 (fully raised and fanned), so the wing visibly opens over time, like "clamp((t-2)/8,0,1)". count feathers per row (default 10) and rows 1-3 (default 3); feather_length is the longest feather (default 0.6 of span); width broadens every feather (default 1.5); overlap and layer as in feathers. u segments must be a multiple of count*rows with 2-4 per feather (10 and 3 give 60, 90 or 120). Build a left and a right surface and attach both to a rig with mount at back.'}
WORLD_SCHEMA['properties']['objects']['items']['properties']['mount']={'type':'object','additionalProperties':False,'required':['rig','anchor'],'properties':{
    'rig':{'type':'string'},'anchor':{'type':'string','enum':list(ANCHORS)},'face_camera':{'type':'number','minimum':0,'maximum':1}},
    'description':'Optional: attaches this surface to a rig. Its position expressions become local to the attachment point, turned with the rig facing, so the part follows the body when the rig is moved or re-posed and never floats beside it. anchor is one of the rig attachment points. face_camera 0-1 tips the part toward the first camera position (a ring defaults to 0.6, so a flat ring over head_top reads as a ring, not a bar; others default to 0). A mounted drape hangs from the anchor to the ground under it: its height is set for you, and under a kneeling or sitting pose it pools on the ground with ripples unless you set pool yourself. Not for the figure surface itself.'}
WORLD_SCHEMA['properties']['objects']['items']['properties']['drape']['properties']['ripples']={'type':'integer','minimum':0,'maximum':8}
WORLD_SCHEMA['properties']['objects']['items']['properties']['drape']['description']+=' ripples 1-8 wrinkles the pooled cloth into rings of low folds on the ground (needs pool above 0).'
WORLD_SCHEMA['properties']['objects']['items']['properties']['glow']={'type':'number','minimum':.05,'maximum':3,
    'description':'Optional see-through light volume: the surface ADDS albedo*glow to whatever is behind it, casts no shadow, ignores scene lighting, fades at its silhouette and with fog. Use for a light beam, halo or shaft, never for solid matter. Black albedo adds nothing, so a color_pattern toward color_high #000000 fades it out along its length. Opaque surfaces in front still hide it.'}
