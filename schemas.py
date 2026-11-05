"""Public tool contracts for the foundation milestone."""
from .rekindra_core.scenes import SCENE_SCHEMA

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
