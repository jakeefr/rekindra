"""Bounded field revisions of immutable worlds; no executable patch language."""
import copy
from .scenes import SceneError
from .worlds import validate_world, WORLD_SCHEMA, shown

SCENE_FIELDS = frozenset(('title', 'mood', 'reason', 'camera', 'environment', 'assemblies', 'text_references'))
OPTIONAL_SCENE_FIELDS = frozenset(('text_references',))
OPTIONAL_FIELDS = frozenset(('bindings', 'caps', 'instances', 'color_detail', 'bump_detail', 'color_pattern','assembly','shading','loft','reflection','glow'))
OBJECT_FIELDS = frozenset(WORLD_SCHEMA['properties']['objects']['items']['properties']) - {'id'}


def revise_world(scene, edits, asset_ids):
    # Validation and copying precede every edit. Nothing mutates a saved record.
    candidate = validate_world(scene, asset_ids)
    if not isinstance(edits, list) or not 1 <= len(edits) <= 24:
        raise SceneError('Provide one to 24 field edits: edits is a JSON array of {"field", "value"} objects '
                         '(add "object_id" for a surface field), not JSON-encoded text')
    objects = {obj['id']: obj for obj in candidate['objects']}
    seen, changed = set(), []
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) not in (
                {'field', 'value'}, {'object_id', 'field', 'value'}):
            raise SceneError('Each edit requires field/value and optional object_id: an edit is exactly '
                             '{"field": name, "value": new value} for a scene field, or '
                             '{"object_id": surface id, "field": name, "value": new value} for a surface field. '
                             'value is the whole new value of that field, or null to remove an optional one')
        field = edit['field']
        if not isinstance(field, str):
            raise SceneError('Edit field must be a string')
        if 'object_id' in edit:
            identifier = edit['object_id']
            if not isinstance(identifier, str) or identifier not in objects:
                raise SceneError(f'Edit object_id must identify an existing surface: got {shown(identifier)}; this plan has {sorted(objects)}. '
                                 'A revision cannot add or remove surfaces; for that, call rekindra_create_world with the full scene')
            if field not in OBJECT_FIELDS:
                raise SceneError(f'Unsupported surface edit field; IDs cannot change: got {shown(field)}; surface fields are {sorted(OBJECT_FIELDS)}. '
                                 f'Scene fields ({", ".join(sorted(SCENE_FIELDS))}) are edited without object_id')
            target, path = objects[identifier], f'objects/{identifier}/{field}'
        else:
            if field not in SCENE_FIELDS:
                hint = (f'; {field} is a surface field, so add object_id (one of {sorted(objects)})' if field in OBJECT_FIELDS
                        else '; duration, size, seed, references and the surface list are fixed by the parent plan' )
                raise SceneError('Scene edits allow title, mood, reason, camera, environment, assemblies or text_references only: '
                                 f'got {shown(field)}{hint}')
            target, path = candidate, field
        if path in seen:
            raise SceneError('Duplicate edit target: ' + path)
        seen.add(path)
        value = edit['value']
        if value is None:
            if field not in (OPTIONAL_FIELDS if 'object_id' in edit else OPTIONAL_SCENE_FIELDS):
                removable = sorted(OPTIONAL_FIELDS) if 'object_id' in edit else sorted(OPTIONAL_SCENE_FIELDS)
                raise SceneError(f'Only optional fields may be removed: {field} is required, so pass its new value instead of null. '
                                 f'Removable here: {removable}')
            if field in target:
                del target[field]; changed.append(path)
        else:
            if field not in target or target[field] != value:
                changed.append(path)
            # Never let Python's numeric equality (False == 0, 4.0 == 4)
            # skip validation of a submitted replacement, including nested data.
            target[field] = copy.deepcopy(value)
    # Check budgets, math, geometry, camera and material contracts as a whole.
    candidate = validate_world(candidate, asset_ids)
    if not changed:
        raise SceneError('Revision changes no fields')
    return candidate, sorted(changed)
