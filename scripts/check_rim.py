"""Measure the sea/sky rim line on decoded frames.

Written as the pass condition for the fog_sky_blend experiment (failed and reverted, see
docs/acceptance/demo-fixes-outcome.md). Still usable on any take to measure the rim.

Rim step: each frame is cut into 64 px wide column bins (so the tower and hulls only spoil a
minority of bins). In each bin the row-median RGB (0-255) is taken, and the strongest step is the
largest Euclidean distance between the mean of 3 rows above and 3 rows below a 2-row gap, searched
over 10%-75% of the frame height. The frame's value is the median across bins.

Pass: median rim step across frames <= RIM_MAX_MEDIAN, every frame <= RIM_MAX_FRAME, and the
existing sea-hue and luma checks from check_demo_scene.py still pass.

Usage: py -3 scripts/check_rim.py PLAN.json SOURCE.png FRAME.png [FRAME.png ...]
Exit codes: 0 pass, 1 fail.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_demo_scene import check_fog, check_sea, load_frames  # noqa: E402

BIN_PX, GAP, SPAN = 64, 1, 3
RIM_MAX_MEDIAN = 10.0
RIM_MAX_FRAME = 14.0


def rim_step(frame):
    """Strongest horizontal line in a frame, in RGB levels (0-255); median across column bins."""
    img = frame * 255
    h, w = img.shape[:2]
    lo, hi = int(h * .10), int(h * .75)
    steps = []
    for x in range(0, w - BIN_PX + 1, BIN_PX):
        rows = np.median(img[:, x:x + BIN_PX], axis=1)
        best = 0.0
        for r in range(max(lo, GAP + SPAN), min(hi, h - GAP - SPAN)):
            above = rows[r - GAP - SPAN:r - GAP].mean(axis=0)
            below = rows[r + GAP:r + GAP + SPAN].mean(axis=0)
            best = max(best, float(np.linalg.norm(above - below)))
        steps.append(best)
    return float(np.median(steps))


def check_rim(frames):
    values = [rim_step(f) for f in frames]
    median, worst = float(np.median(values)), float(max(values))
    ok = bool(median <= RIM_MAX_MEDIAN and worst <= RIM_MAX_FRAME)
    return ok, f'rim_step median={median:.1f} (<={RIM_MAX_MEDIAN:g}), worst frame={worst:.1f} (<={RIM_MAX_FRAME:g})'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('plan')
    ap.add_argument('source')
    ap.add_argument('frames', nargs='+')
    a = ap.parse_args()
    data = json.loads(Path(a.plan).read_text(encoding='utf-8'))
    scene = data.get('scene', data)
    frames = load_frames(a.frames, None, 0)
    source = np.asarray(Image.open(a.source).convert('RGB')).astype(float) / 255
    results = {'rim': check_rim(frames), 'sea': check_sea(frames), 'luma': check_fog(scene['environment'], frames, source)}
    for unit, (ok, detail) in results.items():
        print(f'{unit}: {"PASS" if ok else "FAIL"}  {detail}')
    passed = all(ok for ok, _ in results.values())
    print('RESULT:', 'PASS' if passed else 'FAIL')
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
