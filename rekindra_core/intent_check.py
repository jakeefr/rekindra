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
     'words': ('texture', 'textured', 'bark', 'pavement', 'paving', 'paver', 'pavers', 'paved', 'cobble',
               'cobbles', 'cobblestone', 'cobblestones', 'brick', 'bricks', 'brickwork', 'leaf litter',
               'leaf-littered', 'photo material')},
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
        if 'color_pattern' in obj:
            mix = None  # the pattern picks the blend per pixel
        if mix == 1.0:
            field = 'color_high' if _black(obj.get('color_high')) else None
        elif mix == 0.0:
            field = 'color' if _black(obj.get('color')) else None
        else:
            both = _black(obj.get('color')) and _black(obj.get('color_high'))
            field = 'color and color_high' if both else None
        if field:
            found.append((obj.get('id'), field))
    return found


# What a recovered image could lend a surface, by words in what the agent observed in it.
# Order is the output order; the first matching word is quoted back.
PHOTO_USES = (
    ('ground', ('pavement', 'paving', 'paver', 'pavers', 'paved', 'path', 'road', 'street', 'sidewalk', 'brick',
                'bricks', 'cobble', 'cobbles', 'cobblestone', 'cobblestones', 'tile', 'tiles', 'floor', 'ground',
                'gravel', 'sand', 'grass', 'soil', 'rock', 'rocks', 'rocky', 'stone', 'stones'),
     'has ground detail: a crop of it could texture the ground, path or floor surfaces'),
    ('foliage', ('leaf', 'leaves', 'foliage', 'canopy', 'tree', 'trees', 'trunk', 'trunks', 'bark', 'hedge',
                 'bush', 'ivy', 'branch', 'branches'),
     'has leaf or bark detail: a crop of it could texture the canopy, hedge or trunk surfaces'),
)
_PHOTO_PATTERNS = [(use, [(w, _pattern(w)) for w in words], text) for use, words, text in PHOTO_USES]


def photo_material_candidates(plan):
    """None, or {status, message, candidates}: recovered images no surface uses, or a photo used as the subject."""
    if not isinstance(plan, dict):
        return None
    scene = plan.get('scene') if isinstance(plan.get('scene'), dict) else {}
    references = [r for r in scene.get('references') or []
                  if isinstance(r, dict) and isinstance(r.get('asset_id'), str) and r['asset_id']]
    if not references:
        return None
    if _USES['material_image'](scene):
        return _subject_photos(scene)
    candidates = []
    for ref in references:
        observed = ref.get('observed') if isinstance(ref.get('observed'), str) else ''
        found = False
        for use, patterns, text in _PHOTO_PATTERNS:
            match = next((m for m in (p.search(observed) for _, p in patterns) if m), None)
            if match:
                found = True
                candidates.append({'asset_id': ref['asset_id'], 'use': use,
                                   'hint': f"image {ref['asset_id'][:8]} (you observed '{match.group(0)}') {text}."})
        if not found:
            candidates.append({'asset_id': ref['asset_id'], 'use': 'surface',
                               'hint': f"image {ref['asset_id'][:8]} could texture any surface that shows its "
                                       'material: add material_image with a crop of it.'})
    count = len(references)
    return {'status': 'unused',
            'message': f"No surface uses a photo material, though {count} recovered image{'s' if count != 1 else ''} "
                       f"{'are' if count != 1 else 'is'} in scene.references. The shapes stay 3D and invented; "
                       'only their texture is recovered.',
            'candidates': candidates}


def _subject_photos(scene):
    """Photo materials that show a picture instead of texturing a surface: on a light form, or untiled on a flat upright sheet."""
    candidates = []
    for obj in scene.get('objects') or []:
        image = obj.get('material_image') if isinstance(obj, dict) else None
        if not isinstance(image, dict):
            continue
        position = obj.get('position')
        upright = False
        if isinstance(position, dict):
            x, y, z = (_constant(position.get(k)) for k in ('x', 'y', 'z'))
            upright = y is None and (x is not None or z is not None)
        repeat = image.get('repeat')
        tiled = isinstance(repeat, list) and any(isinstance(r, (int, float)) and not isinstance(r, bool) and r > 1 for r in repeat)
        if 'glow' in obj:
            why = 'is a glow form carrying a photo, so the picture itself is what glows'
        elif upright and not tiled:
            why = 'is a flat upright sheet carrying one untiled photo, so it reads as a picture pasted into the scene'
        else:
            continue
        name = obj.get('id') if isinstance(obj.get('id'), str) else '?'
        candidates.append({'surface': name, 'asset_id': image.get('asset_id') if isinstance(image.get('asset_id'), str) else '',
                           'use': 'construct',
                           'hint': f"surface '{name}' {why}. If it stands for the subject, remove material_image and "
                                   'construct the subject instead: decompose it into parts and build them with feathers, '
                                   'drape, ring, figure, wing, loft and soft glow forms. If it is a wall or backdrop material, tile it '
                                   'with repeat above 1.'})
    if not candidates:
        return None
    return {'status': 'subject_photo',
            'message': 'A photo material is standing in for a subject. Photos texture surfaces only (ground, bark, '
                       'leaves, stone, fabric, sky detail); subjects are built from geometry.',
            'candidates': candidates}


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
    for oid, field in _black_glow(scene):
        flagged.append({'feature': 'glow_color', 'stated': str(oid),
                        'hint': f"glow surface '{oid}' adds no light because its {field} is #000000; "
                                f'set {field} to the color of the light.'})
    return flagged
