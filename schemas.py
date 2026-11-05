"""Public tool contracts for the foundation milestone."""
from .rekindra_core.scenes import SCENE_SCHEMA
from .rekindra_core.worlds import WORLD_SCHEMA

SCHEMAS = {
    'rekindra_inspect': {
        'name': 'rekindra_inspect',
        'description': 'Inspect a user-selected local folder and save bounded copies in a Rekindra project. Does not execute input files, call a model, or modify originals. Excludes common credential/development paths. Ask the user to select a folder if none was provided.',
        'parameters': {'type': 'object', 'properties': {'folder': {'type': 'string', 'description': 'Absolute path to the folder the user selected.'}}, 'required': ['folder'], 'additionalProperties': False},
    },
    'rekindra_recover': {
        'name': 'rekindra_recover',
        'description': 'Recover a saved TGA image to PNG using Rekindra original decoding. Supports true-color type 2/10, 24/32-bit, no palette/interleaving. Rejects truncated pixels; never invents missing content. Use IDs from rekindra_inspect.',
        'parameters': {'type': 'object', 'properties': {'project_id': {'type': 'string'}, 'asset_id': {'type': 'string'}}, 'required': ['project_id', 'asset_id'], 'additionalProperties': False},
    },
    'rekindra_status': {
        'name': 'rekindra_status',
        'description': 'Read an existing Rekindra project inventory, warnings, and recovered artifacts. Does not revisit the original folder.',
        'parameters': {'type': 'object', 'properties': {'project_id': {'type': 'string'}}, 'required': ['project_id'], 'additionalProperties': False},
    },
}

SCHEMAS.update({
    'rekindra_preview':{
        'name':'rekindra_preview',
        'description':'Render six timed frames from a saved scene into a local PNG contact sheet so YOU can inspect and revise your creation. Rebuilds validated sources/plan with Rekindra renderer, uses installed Chrome/Chromium/Edge in an isolated temporary profile, and returns the image path and exact times. No model call, external creative engine or browser download. Then view the PNG using native vision under the user image-sharing consent; evaluate source faithfulness, lighting, framing, silhouettes and spatial conflicts. If needed author a revised immutable scene and preview again. Rendered samples are not decoded video or proof of collision-free motion. Local preview may take up to45 seconds and fails clearly if no compatible browser/graphics is available.',
        'parameters':{'type':'object','properties':{'project_id':{'type':'string'},'plan_id':{'type':'string'}},
                      'required':['project_id','plan_id'],'additionalProperties':False}},
    'rekindra_create_world':{
        'name':'rekindra_create_world',
        'description':'Create an original moving 3D environment from your interpretation of selected project images. View the sources with user consent first. Author geometry, not image effects: no images or text are drawn in this mode. Record observed features and invented elements in references. Surfaces are parametric functions of u,v in [0,1] and t in seconds, world units with Y up. Expressions allow numbers, u,v,t,pi, + - * /, sin cos abs sqrt exp min max pow clamp mix; <=512 characters, no code or imports. Position x/y/z are expressions. Optional bindings is an ordered array of up to16 {name,expression} records; names are lowercase identifiers, each expression can use earlier bindings. Reuse progress, local coordinates and hinge angles to keep complex geometry consistent and avoid duplicated math. Keep separate objects in deliberately separated spatial regions throughout motion; a successful build does not prove no intersections. color_mix is a 0-1 expression blending hex color and color_high. Material roughness .04-1, metalness 0-1, emission 0-3. Each grid segments=[4-128,4-96], <=32000 cells and12 objects total. Environment colors are #RRGGBB; fog_density 0-.15, light_direction points toward the sun (nonzero), sun_size .003-.15 radians, sun_strength 0-4 controls key illumination. Optional fill_color, fill_direction, fill_strength 0-2 (default .25), and exposure .25-4 (default1) control studio fill and brightness. Objects cast approximate soft directional shadows; no raytracing or translucent materials. Camera has 2-12 keys at seconds, starts0 endsduration, eye/target vectors, fov15-100; camera cannot cross its target. Choose concrete source cues, an invented spatial concept, and readable opening/transformation/resolution states. For staged changes use bounded progress such as clamp((t-2)/6,0,1); tiny periodic motion alone may be inadequate unless the user requests an ambient loop. Frame important forms at useful scale and preserve color identity after lighting. Make the source inspire a new scene with independent surface motion, interesting depth, and a considered camera path. Successful creation only validates/builds the artifact; call rekindra_preview with the returned project/plan IDs, view its PNG using native vision under user consent, then revise observed defects before judging quality. Do not claim visual inspection without it. Examples: a wave surface x=(u-.5)*30,z=(v-.5)*30,y=.2*sin(u*35+t)+.1*cos(v*40-t); a sphere x=2*cos(u*2*pi)*sin(v*pi),y=3+2*cos(v*pi),z=-5+2*sin(u*2*pi)*sin(v*pi). You choose forms, relationships, and motion; do not default to an ocean if the source suggests something else. Output is generated interpretation, not factual 3D recovery. Returns portable offline HTML with WebM export; no additional model call.',
        'parameters':{'type':'object','properties':{'project_id':{'type':'string'},'asset_ids':{'type':'array','items':{'type':'string'},'minItems':1,'maxItems':6},'scene':WORLD_SCHEMA},'required':['project_id','asset_ids','scene'],'additionalProperties':False}},
    'rekindra_compose': {
        'name': 'rekindra_compose',
        'description': 'Render an original scene YOU author from selected project images into portable offline HTML with animation, ASCII and WebM export. No second model call. View the selected image with user consent first (rekindra_recover provides PNG for TGA). Describe an inferred mood, never invent recovered history. Pass a scene: 1280x720, 4-30 seconds, 2-5 #RRGGBB palette colors, at least one image or fragments layer with an exact selected asset ID. For substantial motion use track: 2-16 complete states with at (local seconds), x/y [-1,2], scale [.1,3], rotation [-180,180], opacity [0,1], spread [0,1], turn [-150,150]. Times must increase within layer duration. Fragments use columns 2-32 and rows 2-18; max 1800 pieces total. Spread separates source tiles and turn rotates the field in generated depth. Track replaces preset motion. Plan a beginning, transformation and resolution. Layer x/y are normalized centers; width/height normalized sizes; font_size 16-120; motion still/drift/rise/pulse/pan; font serif/sans-serif/monospace. Do not add on-screen text unless the user explicitly requests it; only then set allow_text=true. Returns the saved artifact path.',
        'parameters': {'type':'object','properties':{'project_id':{'type':'string'},
            'allow_text':{'type':'boolean','description':'Default false. True only for user-requested on-screen text.'},'asset_ids':{'type':'array','items':{'type':'string'},'minItems':1,'maxItems':6},'scene':SCENE_SCHEMA},
            'required':['project_id','asset_ids','scene'],'additionalProperties':False}},
    'rekindra_plan': {
        'name': 'rekindra_plan',
        'description': 'Create and save an original animated scene plan from 1-6 selected project images using the active Hermes model. This sends selected image bytes to that model provider; obtain user consent first. Handles PNG/JPEG/recovered TGA. Result is generated interpretation, not recovered history. Return the creative direction and plan ID; use rekindra_build to make the portable artifact.',
        'parameters': {'type':'object','properties': {'project_id':{'type':'string'},
            'allow_text':{'type':'boolean','description':'Default false. True only for user-requested on-screen text.'},'asset_ids':{'type':'array','items':{'type':'string'},'minItems':1,'maxItems':6},
            'intent':{'type':'string','maxLength':1000},
            'send_images':{'type':'boolean','description':'True only when user consented to selected images being sent through the configured Hermes model.'}},
            'required':['project_id','asset_ids','intent','send_images'],'additionalProperties':False}},
    'rekindra_build': {
        'name':'rekindra_build',
        'description':'Build a validated saved scene plan into portable offline HTML, using Rekindra original Canvas runtime. The user can play, scrub, view ASCII, inspect source provenance, and save a silent WebM video in a supported browser. Does not call a model or modify original files.',
        'parameters':{'type':'object','properties':{'project_id':{'type':'string'},'plan_id':{'type':'string'}},
                      'required':['project_id','plan_id'],'additionalProperties':False}}
})
