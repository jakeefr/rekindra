"""Flag renderer features the plan's own notes ask for but the scene leaves off.

Pure and deterministic: reads the saved plan only, renders nothing.
"""
import re

# Adjust names, keywords and hints here. Order is the output order.
# 'uses' names a detector in _USES; 'field' is how the hint names the scene field to add.
FEATURES = (
    {'feature': 'atmosphere', 'uses': 'atmosphere',
     'field': 'scene.environment.atmosphere is not set; add it (bloom, halo, haze_density...)',
     'words': ('glow', 'glowing', 'halo', 'halos', 'bloom', 'blooming', 'haze', 'hazy', 'mist', 'misty',
               'fog', 'foggy', 'soft light', 'luminous', 'radiant', 'lamplit')},
    {'feature': 'foliage', 'uses': 'foliage',
     'field': 'no object has foliage; add foliage to the tree, bush or hedge objects',
     'words': ('leaves', 'leaf', 'foliage', 'canopy', 'ivy', 'tree', 'trees', 'birch', 'bush', 'hedge')},
    {'feature': 'soft', 'uses': 'soft',
     'field': 'no object has soft; add soft to the feathered or glowing figure objects',
     'words': ('feather', 'feathered', 'soft-edged', 'soft edge', 'wispy', 'ethereal', 'figure of light',
               'luminous figure', 'aura')},
    {'feature': 'material_image', 'uses': 'material_image',
     'field': 'no object has material_image; add material_image to the textured objects',
     'words': ('texture', 'textured', 'bark', 'pavement', 'cobble', 'photo material')},
)
_BLACK = {'#000', '#000000'}


def _objects(scene):
    objects = scene.get('objects')
    return [o for o in objects if isinstance(o, dict)] if isinstance(objects, list) else []


def _object_has(key):
    return lambda scene: any(key in o for o in _objects(scene))


def _has_atmosphere(scene):
    env = scene.get('environment')
    return isinstance(env, dict) and bool(env.get('atmosphere'))


_USES = {'atmosphere': _has_atmosphere, 'foliage': _object_has('foliage'),
         'soft': _object_has('soft'), 'material_image': _object_has('material_image')}


def _notes(plan):
    """The agent's free-text statements of intent, in a fixed order."""
    scene = plan.get('scene') if isinstance(plan.get('scene'), dict) else {}
    notes = [scene.get(k) for k in ('title', 'mood', 'reason')]
    for ref in scene.get('references') or []:
        if isinstance(ref, dict):
            notes.append(ref.get('created'))
    provenance = plan.get('text_provenance')
    rows = provenance.get('interpretations') if isinstance(provenance, dict) else None
    if not isinstance(rows, list):
        rows = scene.get('text_references')
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict):
            notes.append(row.get('interpretation'))
    return [n for n in notes if isinstance(n, str) and n.strip()]


def _pattern(word):
    # Word boundaries on both ends; inner spaces/hyphens match any run of space or hyphen.
    parts = re.split(r'[\s-]+', word)
    return re.compile(r'(?<![\w])' + r'[\s-]+'.join(re.escape(p) for p in parts) + r'(?![\w])', re.IGNORECASE)


_PATTERNS = {f['feature']: [(w, _pattern(w)) for w in f['words']] for f in FEATURES}


def _constant(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _black(value):
    return isinstance(value, str) and value.strip().lower() in _BLACK


def _black_glow(scene):
    found = []
    for obj in _objects(scene):
        if 'glow' not in obj:
            continue
        mix = _constant(obj['color_mix']) if 'color_mix' in obj else 0.0
        if mix == 1.0:
            black = _black(obj.get('color_high'))
        elif mix == 0.0:
            black = _black(obj.get('color'))
        else:
            black = _black(obj.get('color')) and _black(obj.get('color_high'))
        if black:
            found.append(obj.get('id'))
    return found


def intent_check(plan):
    """List of {feature, stated, hint}; empty when nothing is flagged."""
    if not isinstance(plan, dict):
        return []
    scene = plan.get('scene') if isinstance(plan.get('scene'), dict) else {}
    notes = _notes(plan)
    flagged = []
    for feature in FEATURES:
        if not notes or _USES[feature['uses']](scene):
            continue
        stated = []
        for word, pattern in _PATTERNS[feature['feature']]:
            for note in notes:
                match = pattern.search(note)
                if match and match.group(0).lower() not in (s.lower() for s in stated):
                    stated.append(match.group(0))
                    break
        if stated:
            shown = ', '.join(f"'{s}'" for s in stated[:4])
            flagged.append({'feature': feature['feature'], 'stated': ', '.join(stated[:4]),
                            'hint': f"Your notes mention {shown} but {feature['field']} and preview again."})
    for oid in _black_glow(scene):
        flagged.append({'feature': 'glow_color', 'stated': str(oid),
                        'hint': f"glow surface '{oid}' renders black because its color resolves to #000000; "
                                'set color to the light color.'})
    return flagged
