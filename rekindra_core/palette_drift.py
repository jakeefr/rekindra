"""Tell the agent when a preview's large regions rendered away from the colors the sources call for.

The rendered side is measured from the review sheet by the Pillow child. The intended side is the
source image's measured palette or, with no palette, colors that text evidence names for a large
surface. Regions are the same thirds as the source palette, so a shot framed very differently
from its source can be flagged for framing rather than for color; the flag is advice to look.
"""
import re

from .image_recovery import clean_palette, measure_review_sheet
from .projects import ProjectError

SOURCE_THRESHOLD = 20.0     # CIE76. On four lighthouse takes the water that read right was 11-17, the brown water 25
TEXT_THRESHOLD = 30.0       # a named color is a loose target, so it needs a wider margin
MIDDLE_THRESHOLD = 35.0     # the middle band holds the subject, not one surface; those same takes were 26-33
_SAME_COLOR = 10.0          # median cut splits one surface into near-identical clusters
_SCENE_MATCH = 10.0
_WARMTH = 8.0
_MAX_NAMED = 3
_MAX_TEXT = 20_000
_MAX_COLORS = 6

_COLOR_NAMES = {'black': '#141414', 'white': '#F2F2F2', 'grey': '#808080', 'gray': '#808080', 'silver': '#C0C0C0',
                'red': '#B03A2E', 'crimson': '#A61C3C', 'orange': '#E07B39', 'amber': '#D99A2B', 'gold': '#D4AF37',
                'golden': '#D4AF37', 'yellow': '#E6C84A', 'green': '#4C8C4A', 'teal': '#2A7F7F', 'blue': '#3A6EA5',
                'navy': '#1F2F55', 'purple': '#6C3F8F', 'violet': '#7A52A8', 'pink': '#D98CA6', 'brown': '#6B4A2F',
                'tan': '#C2A27A', 'rust': '#9C4A24', 'cream': '#EDE3C8', 'ivory': '#EFE9D6'}
_SURFACES = {'sky': 'top band', 'skies': 'top band', 'clouds': 'top band',
             'hill': 'middle', 'hills': 'middle', 'mountain': 'middle', 'mountains': 'middle', 'cliff': 'middle',
             'cliffs': 'middle', 'wall': 'middle', 'walls': 'middle', 'forest': 'middle', 'trees': 'middle',
             'water': 'bottom band', 'sea': 'bottom band', 'ocean': 'bottom band', 'lake': 'bottom band',
             'river': 'bottom band', 'harbor': 'bottom band', 'harbour': 'bottom band', 'bay': 'bottom band',
             'ground': 'bottom band', 'floor': 'bottom band', 'sand': 'bottom band', 'beach': 'bottom band',
             'snow': 'bottom band', 'grass': 'bottom band', 'field': 'bottom band', 'fields': 'bottom band'}
_SHADE = r'(?:(dark|deep|pale|light)\s+)?'
_COLOR = r'(' + '|'.join(sorted(_COLOR_NAMES, key=lambda name: (-len(name), name))) + r'|#[0-9a-f]{6})'
_SURFACE = r'(' + '|'.join(sorted(_SURFACES, key=lambda name: (-len(name), name))) + r')'
_COLOR_FIRST = re.compile(r'\b' + _SHADE + r'(?<![\w#])' + _COLOR + r'\s+' + _SURFACE + r'\b', re.IGNORECASE)
_SURFACE_FIRST = re.compile(r'\b' + _SURFACE + r'\s+(?:was|is|were|are|looked|looks|turned|glowed)\s+(?:an?\s+)?'
                            + _SHADE + _COLOR + r'\b', re.IGNORECASE)


def _channels(color: str) -> tuple:
    return tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))


def _lab(color: str) -> tuple:
    def linear(value):
        value /= 255
        return value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4

    def curve(value):
        return value ** (1 / 3) if value > .008856 else 7.787 * value + 16 / 116
    red, green, blue = (linear(value) for value in _channels(color))
    x = curve((.4124 * red + .3576 * green + .1805 * blue) / .95047)
    y = curve(.2126 * red + .7152 * green + .0722 * blue)
    z = curve((.0193 * red + .1192 * green + .9505 * blue) / 1.08883)
    return 116 * y - 16, 500 * (x - y), 200 * (y - z)


def delta_e(first: str, second: str) -> float:
    a, b = _lab(first), _lab(second)
    return sum((p - q) ** 2 for p, q in zip(a, b)) ** .5


def _shaded(color: str, shade: str | None) -> str:
    red, green, blue = _channels(color)
    if shade in ('dark', 'deep'):
        red, green, blue = (round(value * .55) for value in (red, green, blue))
    elif shade in ('pale', 'light'):
        red, green, blue = (round(value + (255 - value) * .5) for value in (red, green, blue))
    return '#%02X%02X%02X' % (red, green, blue)


def text_colors(evidence) -> list:
    """Colors text evidence names for a large surface, in evidence order. English only, and conservative."""
    found = []
    for record in evidence if isinstance(evidence, list) else []:
        text = record.get('text') if isinstance(record, dict) else None
        if not isinstance(text, str):
            continue
        spans = []
        for pattern, shade_at, color_at, surface_at in ((_COLOR_FIRST, 1, 2, 3), (_SURFACE_FIRST, 2, 3, 1)):
            for match in pattern.finditer(text[:_MAX_TEXT]):
                spans.append((match.start(), match.group(shade_at), match.group(color_at), match.group(surface_at)))
        for _, shade, color, surface in sorted(spans, key=lambda span: span[0]):
            name = color.lower()
            value = name.upper() if name.startswith('#') else _COLOR_NAMES[name]
            entry = {'region': _SURFACES[surface.lower()], 'surface': surface.lower(),
                     'hex': _shaded(value, shade.lower() if shade else None)}
            if len(found) < _MAX_COLORS and entry not in found:
                found.append(entry)
    return found


def _palette_intended(palette: list, region: str) -> list:
    matching = [entry for entry in palette if entry['location'] == 'throughout' or region in entry['location'].split(' and ')]
    if not matching:
        return []
    floor = max(entry['coverage'] for entry in matching) / 2    # an accent there is not what the region should read as
    return [entry['hex'] for entry in matching if entry['coverage'] >= floor]


def _scene_colors(scene: dict) -> list:
    named = []
    for item in scene.get('objects') or []:
        named += [(item.get('id'), item.get(key)) for key in ('color', 'color_high')]
    environment = scene.get('environment') or {}
    named += [(key, environment.get(key)) for key in ('sky_top', 'sky_bottom', 'ground_color')]
    return [(name, color) for name, color in named if isinstance(name, str) and isinstance(color, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', color)]


def _near_intended(scene: dict, intended: str) -> list:
    names = []
    for name, color in _scene_colors(scene):
        if name not in names and delta_e(color, intended) <= _SCENE_MATCH:
            names.append(name)
    return names[:_MAX_NAMED]


def _cause(rendered: str, intended: str, has_material: bool) -> str:
    if not has_material:
        return 'no scene color is near the intended one; set the material of the large surface here from it'
    now, wanted = _lab(rendered), _lab(intended)
    warmth = (now[2] - wanted[2]) + .5 * (now[1] - wanted[1])
    if warmth > _WARMTH:
        return 'lighting is shifting it warm; reduce warm sun/fill/ambient or adjust the material'
    if warmth < -_WARMTH:
        return 'lighting is shifting it cool; reduce cool sun/fill/ambient or adjust the material'
    if now[0] > wanted[0]:
        return 'it renders lighter than intended; reduce light strength, exposure or emission, or darken the material'
    return 'it renders darker than intended; raise light strength or ambient, or lighten the material'


def _dominant(colors: list) -> dict:
    """The largest group of near-identical measured colors, named by its largest member."""
    groups = []
    for color in sorted(colors, key=lambda item: (-item['coverage'], item['hex'])):
        group = next((item for item in groups if delta_e(item['hex'], color['hex']) <= _SAME_COLOR), None)
        if group:
            group['coverage'] += color['coverage']
        else:
            groups.append(dict(color))
    return max(groups, key=lambda item: item['coverage'])


def drift_report(regions: list, reference: dict, scene: dict) -> dict:
    """Compare measured bands with the reference. Same inputs, same report."""
    from_palette = reference['kind'] == 'source-palette'
    rows = []
    for measured in regions:
        region = measured['region']
        intended = ([color for palette in reference['palettes'] for color in _palette_intended(palette, region)] if from_palette
                    else [entry['hex'] for entry in reference['colors'] if entry['region'] == region])
        if not intended:
            continue
        threshold = max(SOURCE_THRESHOLD if from_palette else TEXT_THRESHOLD, MIDDLE_THRESHOLD if region == 'middle' else 0)
        rendered = _dominant(measured['colors'])
        best = min(intended, key=lambda color: (delta_e(rendered['hex'], color), color))
        distance = delta_e(rendered['hex'], best)
        objects = _near_intended(scene, best)
        over = distance > threshold
        rows.append({'region': region, 'intended': best, 'rendered': rendered['hex'],
                     'rendered_coverage': round(rendered['coverage'], 1), 'delta_e': round(distance, 1), 'threshold': threshold,
                     'over_threshold': over, 'objects': objects,
                     'flag': (f"{', '.join(objects) or region} rendered {rendered['hex']} vs intended {best}: "
                              f"{_cause(rendered['hex'], best, bool(objects))}") if over else None})
    report = {'status': 'drift' if any(row['over_threshold'] for row in rows) else 'ok',
              'reference': reference['kind'], 'regions': rows}
    if reference.get('asset_ids'):
        report['source_asset_ids'] = reference['asset_ids']
    if not rows:
        report.update(status='not_measured', reason='The reference names no color for any measured region.')
    return report


def _skipped(status: str, reason: str) -> dict:
    return {'status': status, 'reference': None, 'regions': [], 'reason': reason}


def _reference(store, project_id: str, plan: dict) -> dict | None:
    artifacts = store.status(project_id)['artifacts']
    palettes, asset_ids = [], []
    for asset_id in plan.get('source_ids') or []:
        saved = next((item for item in artifacts if item.get('asset_id') == asset_id and item.get('kind') == 'recovered'), None)
        if saved is None:
            continue
        if 'palette' in saved:      # None or [] is a settled answer: previewing must not decode the source again
            palette = clean_palette(saved['palette'])
        else:                       # no measurement has finished for this source yet
            try:
                palette = clean_palette(store.recover(project_id, asset_id).get('palette'))
            except (ProjectError, OSError):
                palette = None
        if palette:
            palettes.append(palette)
            asset_ids.append(asset_id)
    if palettes:    # a scene may take its sky from one source and its water from another
        return {'kind': 'source-palette', 'asset_ids': asset_ids, 'palettes': palettes}
    colors = text_colors(((plan.get('text_provenance') or {}).get('recovered_evidence')))
    return {'kind': 'text-evidence', 'colors': colors} if colors else None


def measure_drift(store, project_id: str, plan: dict, png: bytes, review_camera=None) -> dict:
    """The preview's drift report. A measurement that cannot be made costs the report, never the preview."""
    if review_camera is not None:
        return _skipped('not_measured', 'An inspection camera does not frame the scene like the source.')
    try:
        reference = _reference(store, project_id, plan)
    except (ProjectError, OSError):
        return _skipped('unavailable', 'The source palette could not be read.')
    if reference is None:
        return _skipped('not_measured', 'No source palette and no color named for a large surface in text evidence.')
    regions = measure_review_sheet(png)
    if regions is None:
        return _skipped('unavailable', 'The rendered colors could not be measured (the image reader is unavailable or was stopped).')
    return drift_report(regions, reference, plan['scene'])
