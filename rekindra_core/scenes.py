"""Rekindra Scene Document v1: bounded creative data, never executable source."""
import copy
import math
import re


class SceneError(ValueError):
    pass


_COLOR = re.compile(r'^#[0-9a-fA-F]{6}$')
_LAYER_ID = re.compile(r'^[a-zA-Z0-9_-]{1,40}$')
MOTIONS = ('still', 'drift', 'rise', 'pulse', 'pan')


def _number(value, low, high, label, integer=False):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high or (integer and type(value) is not int):
        raise SceneError(f'{label} must be a finite number between {low} and {high}')
    return value


def _text(value, limit, label):
    if not isinstance(value, str) or len(value) > limit:
        raise SceneError(f'{label} must be text of at most {limit} characters')
    return value


def validate_scene(value: dict, asset_ids: set[str]) -> dict:
    if not isinstance(value, dict):
        raise SceneError('Scene must be an object')
    required = {'schema_version', 'title', 'mood', 'reason', 'duration', 'width', 'height', 'background', 'palette', 'seed', 'layers'}
    if set(value) != required or type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise SceneError('Unsupported scene version or fields')
    scene = copy.deepcopy(value)
    for key, limit in (('title', 100), ('mood', 100), ('reason', 600)):
        _text(scene[key], limit, key)
    _number(scene['duration'], 4, 30, 'duration')
    _number(scene['width'], 1280, 1280, 'width', True)
    _number(scene['height'], 720, 720, 'height', True)
    _number(scene['seed'], 0, 2**31-1, 'seed', True)
    if not isinstance(scene['background'], str) or not _COLOR.fullmatch(scene['background']):
        raise SceneError('background must be a six-digit hex color')
    if not isinstance(scene['palette'], list) or not 2 <= len(scene['palette']) <= 5 or any(not isinstance(c, str) or not _COLOR.fullmatch(c) for c in scene['palette']):
        raise SceneError('palette requires two to five six-digit hex colors')
    if not isinstance(scene['layers'], list) or not 1 <= len(scene['layers']) <= 24:
        raise SceneError('Scene requires 1-24 layers')
    defaults = {'opacity': 1, 'rotation': 0, 'motion': 'still', 'color': scene['palette'][0],
                'width': .8, 'height': .6, 'font_size': 48, 'font': 'serif', 'count': 50, 'text': '', 'asset_id': ''}
    allowed = {'id', 'kind', 'start', 'end', 'x', 'y', *defaults}
    ids, image_count = set(), 0
    for layer in scene['layers']:
        if not isinstance(layer, dict) or set(layer) - allowed or not {'id', 'kind', 'start', 'end', 'x', 'y'} <= set(layer):
            raise SceneError('Invalid or unknown layer fields')
        if not isinstance(layer['id'], str) or not _LAYER_ID.fullmatch(layer['id']) or layer['id'] in ids:
            raise SceneError('Layer IDs must be unique simple identifiers')
        ids.add(layer['id'])
        if layer['kind'] not in ('image', 'text', 'particles'):
            raise SceneError('Unsupported layer operation')
        for key, default in defaults.items(): layer.setdefault(key, default)
        for key, low, high in (('start', 0, scene['duration']), ('end', 0, scene['duration']),
                               ('x', 0, 1), ('y', 0, 1), ('width', .02, 1.5), ('height', .02, 1.5),
                               ('opacity', 0, 1), ('rotation', -45, 45), ('font_size', 16, 120)):
            _number(layer[key], low, high, key)
        _number(layer['count'], 1, 160, 'count', True)
        if layer['end'] <= layer['start']:
            raise SceneError('Layer end must follow start')
        if layer['motion'] not in MOTIONS or layer['font'] not in ('serif', 'sans-serif', 'monospace'):
            raise SceneError('Unsupported motion or font')
        if not isinstance(layer['color'], str) or not _COLOR.fullmatch(layer['color']):
            raise SceneError('Layer color must be a six-digit hex color')
        _text(layer['text'], 180, 'layer text')
        _text(layer['asset_id'], 32, 'asset ID')
        if layer['kind'] == 'image':
            if layer['asset_id'] not in asset_ids:
                raise SceneError('Image layer refers to an unselected source')
            image_count += 1
    if not image_count:
        raise SceneError('A composition must visibly use at least one selected image')
    return scene


_NUM = {'type': 'number'}
SCENE_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'schema_version': {'type': 'integer', 'const': 1},
        'title': {'type': 'string'}, 'mood': {'type': 'string'}, 'reason': {'type': 'string'},
        'duration': {'type': 'number', 'minimum': 4, 'maximum': 30},
        'width': {'type': 'integer', 'const': 1280}, 'height': {'type': 'integer', 'const': 720},
        'background': {'type': 'string'}, 'palette': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 2, 'maxItems': 5},
        'seed': {'type': 'integer', 'minimum': 0, 'maximum': 2147483647},
        'layers': {'type': 'array', 'minItems': 1, 'maxItems': 24, 'items': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'id': {'type': 'string'}, 'kind': {'type': 'string', 'enum': ['image', 'text', 'particles']},
                           'start': _NUM, 'end': _NUM, 'x': _NUM, 'y': _NUM, 'width': _NUM, 'height': _NUM,
                           'opacity': _NUM, 'rotation': _NUM, 'font_size': _NUM, 'count': {'type': 'integer'},
                           'text': {'type': 'string'}, 'asset_id': {'type': 'string'}, 'color': {'type': 'string'},
                           'font': {'type': 'string', 'enum': ['serif', 'sans-serif', 'monospace']},
                           'motion': {'type': 'string', 'enum': list(MOTIONS)}},
            'required': ['id', 'kind', 'start', 'end', 'x', 'y']}}
    },
    'required': ['schema_version', 'title', 'mood', 'reason', 'duration', 'width', 'height', 'background', 'palette', 'seed', 'layers']
}
