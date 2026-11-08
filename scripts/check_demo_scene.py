"""Program-checkable pass conditions for the five demo weak-spot units.

Reads a saved world plan plus rendered frames and reports each unit as PASS/FAIL
with the measured numbers. It judges nothing aesthetic; frame review stays manual.

Frames are single-frame PNGs, or a decoded review grid with --grid COLSxROWS
(each tile's bottom label strip is cropped with --label-px).

Usage:
  py -3 scripts/check_demo_scene.py PLAN.json SOURCE.png FRAME.png [FRAME.png ...]
      [--grid 3x2 --label-px 30] [--boat-id ID] [--beam-id ID] [--water-id ID]
"""
import argparse
import colorsys
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rekindra_core.expressions import sampler  # noqa: E402

LUMA = np.array([.2126, .7152, .0722])


def load_frames(paths, grid, label_px):
    frames = []
    for p in paths:
        im = np.asarray(Image.open(p).convert('RGB')).astype(float) / 255
        if not grid:
            frames.append(im)
            continue
        cols, rows = grid
        th, tw = im.shape[0] // rows, im.shape[1] // cols
        for r in range(rows):
            for c in range(cols):
                frames.append(im[r * th:(r + 1) * th - label_px, c * tw:(c + 1) * tw])
    return frames


def hue_deg(px):
    hsv = np.array([colorsys.rgb_to_hsv(*p) for p in px])
    keep = hsv[:, 1] > .12
    return (float(np.median(hsv[keep, 0])) * 360) if keep.any() else -1.0


# Recalibrated 2026-11-07: the first threshold (0.7x the source's luma std) was unreachable.
# The source is a 160x120 pixel-art TGA with hard flat tones. The original live plan
# (d42b979, fog .012) measured 0.073, so the bar is now ~1.25x that.
FOG_MIN_STD = .09


def check_fog(env, frames, source):
    density = float(env.get('fog_density', 0))
    src_std = float((source @ LUMA).std())
    std = float(np.mean([(f @ LUMA).std() for f in frames]))
    ok = density <= .006 and std >= FOG_MIN_STD
    return ok, (f'fog_density={density:.4f} (<=0.006), luma_std={std:.3f} (>={FOG_MIN_STD}; '
                f'original plan 0.073, source {src_std:.3f} for reference)')


def check_sea(frames):
    hues, blue = [], []
    for f in frames:
        h = f.shape[0]
        band = f[int(h * .70):int(h * .95)].reshape(-1, 3)[::5]
        hues.append(hue_deg(band))
        blue.append(float((band[:, 2] > band[:, 0]).mean()))
    hue, frac = float(np.median(hues)), float(np.mean(blue))
    ok = 185 <= hue <= 235 and frac >= .6
    return ok, f'sea_band hue={hue:.0f} (185-235), blue>red frac={frac:.2f} (>=0.60)'


def rgb(hexcolor):
    return np.array([int(hexcolor[i:i + 2], 16) for i in (1, 3, 5)], float)


def check_horizon(scene, water_id):
    """The water's far edge must sit near the true horizon and fade into the sky.

    Edge distance: min horizontal distance from every camera eye to the sampled
    water boundary (u or v at 0/1, skipping wrap seams and collapsed sides).
    Level: per eye, (max-min)/mean rim distance <= 0.08.
    Fade: fog_color within 48 RGB of sky_bottom with fog opacity >= 0.95 at the
    nearest rim, or a color_pattern >= 0.9 along
    the boundary blending to a color_high within 48 RGB of sky_bottom."""
    env = scene.get('environment', {})
    gap = float(np.linalg.norm(rgb(env.get('fog_color', '#000000')) - rgb(env.get('sky_bottom', '#ffffff'))))
    o = find(scene, water_id) if water_id else None
    if not o:
        return False, f'water object {water_id!r} not found'
    try:
        fx, fz = sampler(o['position']['x']), sampler(o['position']['z'])
    except Exception as exc:
        return False, f'water={water_id} unsampled ({exc.__class__.__name__})'
    g = np.linspace(0, 1, 49)
    offs = [i.get('offset', [0, 0, 0]) for i in o.get('instances') or [{}]]
    sides = {'u0': [(0.0, v) for v in g], 'u1': [(1.0, v) for v in g],
             'v0': [(u, 0.0) for u in g], 'v1': [(u, 1.0) for u in g]}
    xz = {k: np.array([(fx(u, v, 0.0), fz(u, v, 0.0)) for u, v in uv]) for k, uv in sides.items()}
    boundary = []
    for a, b in (('u0', 'u1'), ('v0', 'v1')):
        if np.abs(xz[a] - xz[b]).max() < 1e-3:
            continue  # wrap seam (e.g. a disc's u=0/u=1), interior not boundary
        for k in (a, b):
            if np.ptp(xz[k], axis=0).max() < 1.0:
                continue  # collapsed side (e.g. a disc centre), not an edge
            boundary.append(k)
    if not boundary:
        return False, f'water={water_id} has no open boundary edge'
    pts = np.array([(x + d[0], z + d[2]) for k in boundary for x, z in xz[k] for d in offs])
    eyes = np.array([[c['eye'][0], c['eye'][2]] for c in scene['camera']])
    dist = np.hypot(pts[:, None, 0] - eyes[None, :, 0], pts[:, None, 1] - eyes[None, :, 1])
    near = float(dist.min())
    # A finite rim at uneven distance from the eye projects as a slanted line, not a level horizon.
    spread = float(max((d.max() - d.min()) / d.mean() for d in dist.T))
    density = float(env.get('fog_density', 0))
    fog_fade = gap <= 48 and 1 - np.exp(-near * density) >= .95
    sky = rgb(env.get('sky_bottom', '#ffffff'))
    # The far edge also fades if the water's own color_pattern reaches a sky-matching color_high there.
    pattern_fade = False
    if o.get('color_pattern') and float(np.linalg.norm(rgb(o.get('color_high', '#000000')) - sky)) <= 48:
        try:
            fp = sampler(o['color_pattern'])
            pattern_fade = min(min(1.0, max(0.0, fp(u, v, 0.0))) for k in boundary for u, v in sides[k]) >= .9
        except Exception:
            pattern_fade = False
    ok = near >= 250 and spread <= .08 and (fog_fade or pattern_fade)
    return ok, (f'water={water_id} nearest far edge={near:.0f} (>=250, sides={boundary}), rim spread={spread:.2f} (<=0.08), '
                f'fog_fade={fog_fade} (gap={gap:.0f}<=48, opacity at edge>=0.95) or pattern_fade={pattern_fade}')


def find(scene, oid):
    for o in scene['objects']:
        if o['id'] == oid:
            return o
    return None


def assembly(scene, aid):
    for a in scene.get('assemblies', []):
        if a['id'] == aid:
            return a
    return None


def check_beam(scene, frames, beam_id):
    o = find(scene, beam_id) if beam_id else None
    a = assembly(scene, o.get('assembly')) if o else None
    sweeps = bool(a) and any('t' in str(a['rotation'][k]).replace('sqrt', '') for k in 'xyz')
    centroids, areas = [], []
    for f in frames:
        r, g, b = f[..., 0], f[..., 1], f[..., 2]
        warm = (r > .80) & (g > .62) & (r - b > .12)
        areas.append(float(warm.mean()))
        yy, xx = np.nonzero(warm)
        centroids.append((float(xx.mean()), float(yy.mean())) if len(xx) else None)
    pts = [c for c in centroids if c]
    travel = max((np.hypot(p[0] - q[0], p[1] - q[1]) for p in pts for q in pts), default=0.0)
    w = frames[0].shape[1]
    area = float(np.median(areas))
    ok = sweeps and area >= .002 and travel >= .05 * w
    return ok, (f'beam={beam_id} assembly_rotation_has_t={sweeps}, warm_area={area * 100:.2f}% (>=0.20%), '
                f'warm_centroid_travel={travel:.0f}px (>={.05 * w:.0f})')


def surface_extent(o):
    if o.get('loft'):
        pts = np.array([p for s in o['loft'] for p in s['points']], float)
        return float(np.ptp(pts[:, 0])), float(np.ptp(pts[:, 1])), 'loft'
    try:
        fx, fy, fz = (sampler(o['position'][k]) for k in 'xyz')
    except Exception as exc:  # bindings or unsupported names
        return None, None, f'unsampled ({exc.__class__.__name__})'
    g = np.linspace(0, 1, 25)
    pts = [(fx(u, v, 0.0), fy(u, v, 0.0), fz(u, v, 0.0)) for u in g for v in g]
    pts = np.array(pts)
    return float(np.ptp(pts[:, 0])), float(np.ptp(pts[:, 2])), 'sampled'


def check_boats(scene, boat_id):
    o = find(scene, boat_id) if boat_id else None
    if not o:
        return False, f'boat object {boat_id!r} not found'
    ex, ez, how = surface_extent(o)
    if ex is None:
        return False, f'boat={boat_id} extent {how}'
    ratio = max(ex, ez) / max(min(ex, ez), 1e-6)
    peers = [p['id'] for p in scene['objects']
             if p['id'] != boat_id and o.get('assembly') and p.get('assembly') == o.get('assembly')]
    ok = ratio >= 2.5 and bool(peers)
    return ok, f'boat={boat_id} hull L/W={ratio:.2f} (>=2.5, {how}), parts sharing assembly={peers or "none"}'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('plan')
    ap.add_argument('source')
    ap.add_argument('frames', nargs='+')
    ap.add_argument('--grid')
    ap.add_argument('--label-px', type=int, default=30)
    ap.add_argument('--boat-id')
    ap.add_argument('--beam-id')
    ap.add_argument('--water-id')
    a = ap.parse_args(argv)
    grid = tuple(int(n) for n in a.grid.split('x')) if a.grid else None
    plan = json.loads(Path(a.plan).read_text(encoding='utf-8'))
    scene = plan.get('scene', plan)
    frames = load_frames(a.frames, grid, a.label_px)
    source = np.asarray(Image.open(a.source).convert('RGB')).astype(float) / 255
    results = {
        'fog': check_fog(scene.get('environment', {}), frames, source),
        'sea': check_sea(frames),
        'horizon': check_horizon(scene, a.water_id),
        'beam': check_beam(scene, frames, a.beam_id),
        'boats': check_boats(scene, a.boat_id),
    }
    for name, (ok, detail) in results.items():
        print(f'{"PASS" if ok else "FAIL"} {name}: {detail}')
    return 0 if all(ok for ok, _ in results.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
