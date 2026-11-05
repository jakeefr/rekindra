"""Public tool contracts for the foundation milestone."""

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
