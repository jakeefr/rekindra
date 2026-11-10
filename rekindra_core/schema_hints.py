"""Argument hints shared by every tool schema: where an id comes from and what shape it has."""

ID_PATTERN = '^[0-9a-f]{32}$'
ID_HINTS = {
    'project_id': 'The project_id rekindra_inspect returned for the folder: 32 lowercase hex characters, not a path or a name.',
    'asset_id': 'One assets[].asset_id from rekindra_inspect or rekindra_status: 32 lowercase hex characters, not a file name.',
    'plan_id': 'The plan_id from the latest rekindra_create_world, rekindra_revise_world, rekindra_compose or rekindra_plan '
               'result for this project: 32 lowercase hex characters.',
}
FIELD_HINTS = {
    'asset_ids': 'One to six distinct image asset_id values from rekindra_inspect. Images only: a text, ZIP or PDF asset is '
                 'cited in scene.text_references instead, after rekindra_recover.',
    'edits': 'The changes to apply to the stored plan; fields you leave out keep their current value.',
    'acknowledgments': 'Only for warnings you keep on purpose: one {warning_id, reason} per current warning, warning_id copied '
                       'from the warnings rekindra_preview or a refused rekindra_export listed, reason 10 to 200 characters.',
    'timeline': 'Optional dated entries, only for dates that appear in the recovered material. Omit when it holds no dates.',
    'intent':'A short plain description of the scene to plan.',
    'folder':'Absolute path of the folder the user chose. It is read, never changed.',
}
WORDING = (('and12 objects', 'and 24 surfaces'), ('within12 distinct', 'within 24 distinct'),
           ('rekindra_create_world text_references', 'rekindra_create_world scene.text_references'))
KEYWORDS = {
    'rekindra_reconstruct': ' Keywords: reconstruct, reconstruction, restore, rebuild, reassemble, timeline, recovered archive.',
}


def tighten(schemas):
    """Give every id argument its source and shape, and fill descriptions a model would otherwise guess at."""
    for name, schema in schemas.items():
        for old, new in WORDING:
            schema['description'] = schema['description'].replace(old, new)
        schema['description'] += KEYWORDS.get(name, '')
        properties = schema['parameters']['properties']
        for key, hint in ID_HINTS.items():
            if key in properties:
                properties[key] = {**properties[key], 'pattern': ID_PATTERN,
                                   'description': properties[key].get('description') or hint}
        for key, hint in FIELD_HINTS.items():
            if key in properties and not properties[key].get('description'):
                properties[key] = {**properties[key], 'description': hint}
        ids = properties.get('asset_ids')
        if ids and isinstance(ids.get('items'), dict) and ids['items'].get('type') == 'string':
            ids['items'] = {**ids['items'], 'pattern': ID_PATTERN}
    return schemas
