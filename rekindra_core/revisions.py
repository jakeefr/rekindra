"""Bounded field revisions of immutable worlds; no executable patch language."""
import copy
from .scenes import SceneError
from .worlds import validate_world, WORLD_SCHEMA

SCENE_FIELDS = frozenset(('title', 'mood', 'reason', 'camera', 'environment', 'assemblies', 'text_references'))
OPTIONAL_SCENE_FIELDS = frozenset(('assemblies', 'text_references'))
OPTIONAL_FIELDS = frozenset(('bindings', 'caps', 'instances', 'color_detail', 'bump_detail', 'color_pattern','assembly','shading','loft','reflection'))
OBJECT_FIELDS = frozenset(WORLD_SCHEMA['properties']['objects']['items']['properties']) - {'id'}


def revise_world(scene, edits, asset_ids):
    # Validation and copying precede every edit. Nothing mutates a saved record.
    candidate = validate_world(scene, asset_ids)
    if not isinstance(edits, list) or not 1 <= len(edits) <= 24:
        raise SceneError('Provide one to 24 field edits')
    objects = {obj['id']: obj for obj in candidate['objects']}
    seen, changed = set(), []
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) not in (
                {'field', 'value'}, {'object_id', 'field', 'value'}):
            raise SceneError('Each edit requires field/value and optional object_id')
        field = edit['field']
        if not isinstance(field, str):
            raise SceneError('Edit field must be a string')
        if 'object_id' in edit:
            identifier = edit['object_id']
            if not isinstance(identifier, str) or identifier not in objects:
                raise SceneError('Edit object_id must identify an existing surface')
            if field not in OBJECT_FIELDS:
                raise SceneError('Unsupported surface edit field; IDs cannot change')
            target, path = objects[identifier], f'objects/{identifier}/{field}'
        else:
            if field not in SCENE_FIELDS:
                raise SceneError('Scene edits allow title, mood, reason, camera, environment, assemblies or text_references only')
            target, path = candidate, field
        if path in seen:
            raise SceneError('Duplicate edit target: ' + path)
        seen.add(path)
        value = edit['value']
        if value is None:
            if field not in (OPTIONAL_FIELDS if 'object_id' in edit else OPTIONAL_SCENE_FIELDS):
                raise SceneError('Only optional fields may be removed')
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
