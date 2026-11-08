# Demo weak-spot fixes: outcome (2026-11-07)

Scope: five authoring-guidance fixes for the lighthouse demo (fog, horizon, sea colour, beam, boats) plus the
beat-5 revise. Engine untouched; only `schemas.py` create_world text, `docs/world-authoring.md` and `RULES.md`
changed. Checker: `scripts/check_demo_scene.py` (exit 0 pass, 1 fail, 3 unmeasured only).

This is not an artistic acceptance. Frame reviews below are honest notes, not sign-off.

## Offline probes (hand-authored plans, same engine)

- Baseline plan (d42b979): horizon FAIL (square sea, far edge 25 units, slanted hard line), boats FAIL (L/W 2.12).
- Beam `cone`: emissive tapered cone read as a solid wedge in decoded frames. Rejected per the fallback rule.
- `shaft2`-`shaft6`: flat soft strip on the water, widening away from the lamp, edge/far fade via
  `color_pattern`, on the sweeping assembly. shaft2/3 tuned water colour; shaft4-6 tuned exposure and fill.
  **shaft5 passed all five checker units** (boats L/W 3.02). The RULES.md lines for the five units came from
  these offline passes.
- Fog calibration: `fog_density` .012 flattened the frame (luma std .073); guidance now caps it at .006.

## Live runs (Hermes gateway, gpt-6.1-sol, demo-lighthouse folder)

Folder: `<local path>\samples\demo-lighthouse` (prepared sample: copy of e2e-lighthouse plus a deliberately
corrupt `corrupt.json`). Originals untouched; hashes in `<local path>\samples\demo-lighthouse.sha256` (outside the repo) verify.

### Create, attempt 1 (logs `e2e-fixes`)

- `corrupt.json` got intake_status `rejected`: the demo's rejection beat works live.
- Agent followed the guidance: disc sea `320*v*v`, colour #1F5888 with rim fade, soft shaft (emission .45) on
  the sweeping assembly, pointed-loft hulls with mast and lamps, fog .002.
- Checker: fog PASS (std .148), sea PASS (hue 232), horizon FAIL (edge 282 but rim spread .24: disc centred at
  the origin, eye ~35 units off-centre), beam FAIL on metric (warm area .08%, travel 11 px), boats UNMEASURED
  (hand-computed L/W 3.09).
- Frames: shaft sweep reads clearly across the water; boats small but legible hulls and masts; horizon shows as a
  wavy hard line against the sky; lamp-room glow weak.

### Revise, beat 5 (logs `e2e-fixes-revise`)

Request: lamp-room glass fogs at dusk, soften the beam, bring the two boats in along it.

- **Pass on the riskiest beat.** One `rekindra_revise_world` call, preview rendered.
- Sweep rotation `-.8+.15*t` kept; both assemblies copied; lantern 1.8 -> 1.35; shaft emission .45 -> .12;
  boats translate inward along the beam angle.
- Frames: softer beam, boats ride in along the shaft through the whole sweep. Reads as intended.
- Checker: horizon/beam same as create; sea hue 235 at the band edge (FAIL by <1 degree).

### Horizon, attempt 2 (logs `e2e-fixes2`)

Guidance change: give an explicit eye-centred formula (centre of all camera eyes added as constants).
Review fix in e378932: centre on the midpoint of all eyes, keep scale 1 with no offset, or put the centre in the offset.

- Agent centred the disc at (19,27); eyes x 17..21, z 26..28. corrupt.json rejected again.
- Checker: fog PASS (.144), sea PASS (hue 225), **horizon PASS** (edge 318, rim spread .24 -> .01), beam FAIL on the
  warm-pixel metric only (warm area .02%; travel now 110 px, passes), boats UNMEASURED (assembly x/z bob).
- Frames: horizon level; a faint kinked rim line remains, consistent with disc mesh segments (engine resolution,
  out of scope). Beam sweeps clearly. Boats small and partly behind the headland in this take, weaker than
  attempt 1. Best-of-N recording covers take-to-take variance.
- Horizon unit closed at attempt 2 of 3.

## Beam metric note

The checker's beam unit counts warm (lamp-coloured) pixels. The live shaft is pale against the water, so it fails
that metric while the sweep reads plainly in frames. Per the approved plan ("pick whichever looks better in decoded
frames"), the shaft is kept; the metric mismatch is recorded, not tuned. With this design the
checker's overall exit code will not be 0; read the beam line as advisory.

## Beam from the lamp: engine glow mode (2026-11-07, approved by Jake)

Jake's review of the live take: the light sat on the water instead of coming from the lighthouse. Guidance alone
could not fix it: every surface was opaque and cast shadows, so any beam in the air read as a solid wedge. This unit
changes the engine (the "engine untouched" scope above covers only the five earlier fixes).

- `glow` object field (.05..3): additive, see-through, no shadow or contact depth, ignores scene lighting, fades at its
  silhouette and with fog, depth-tested so opaque matter hides it, drawn in the mirrored reflection pass, cannot be
  the reflector. Optional and revisable; omitting it keeps the old render path.
- Pass conditions (`scripts/browser_glow_test.cjs`): no pixel darker than the scene without it, visible added light,
  opaque control does shadow, a wall in front hides it exactly (same pixel shows it with the wall removed), a planar
  reflector mirrors it without darkening anything, centre brighter than silhouette. The original conditions passed at
  attempt 1; after review the occlusion point was corrected (the first one missed the tube) and the wall-removed and
  reflector cases (each with a control) were added; the re-run passed.
  `tests/test_glow.py` covers validation, the reflector rule and revise set/remove.
- Offline probe (`glow1`-`glow3`, same base plan): attempt 1 at glow .9-1.3 saturated to a white wedge; attempt 2 at
  .12 reads as a soft beam leaving the lamp in all six frames and hidden by the tower when it points away. Guidance and
  RULES.md now say: apex at the lamp, on the sweeping assembly, glow ~.12, plus a glow halo on the lamp room.

- Live run `e2e-glow` built the beam from the lamp, but export failed the seek check: hardware MSAA resolve of
  overlapping additive layers drifted between identical draws (about half of runs; SwiftShader bit-exact). Attempt 1
  (front faces only, x2 gain) and attempt 2 (mirror-pass facing fix) reduced it but broke glow seen from inside or on
  open meshes (review 5379). Attempt 3 (2eca0c9, 85fbc71): scenes with glow render without MSAA, double-sided x1
  glow restored, strict bit-exact seek check restored; 8/8 strict on the live artifact. Scenes without glow keep MSAA.
- Live run `e2e-glow2` (85fbc71): corrupt.json rejected; export passed first try; beam leaves the lamp and sweeps
  in all six decoded frames. Open polish: far sea edge shows as a corner line this take, beam far end reads slightly
  flat, boats have no masts this take.

## Sunday checks and polish (2026-11-08)

- Live revise, beat 5, on `e2e-glow2` ("the lamp-room glass fogs at dusk — soften the beam and bring the boats in
  along it"): two `rekindra_revise_world` calls and two previews, all ok; export passed. Decoded frames: beam angled
  down to the water, slightly softer; boats with mast and lamp ride in along it in all six frames. Pass.
- MSAA change vs non-glow scenes (rain-finish plan, no glow): rendered with world.js from before the MSAA change
  (2eca0c9^), before glow (83cf642^) and current. Live canvas: at most 33 bytes per frame differ, max delta 1, the
  same as current vs current (MSAA noise between page loads). Decoded exports before-MSAA vs current: bit-identical.
  Against the older stored rain export the difference (mean |d| .28, 0.22% of pixels over 8) is the same for both
  builds; it comes from the earlier supersample commit 168e571, not MSAA. Pass.
- Polish, offline probes on a scratch copy of the glow2 project (`polish.py`, one change per variant):
  - Far sea edge, 3 attempts, not adopted. The plan check failed (fog .001 is only ~27% at the 320 rim). Attempt 1
    (fog .006, rim radius 520, ~96% fog) and attempts 2-3 (fog color set to the engine horizon sky,
    mix(sky_bottom, sky_top, .31), first in sRGB then linear) shrank the rim step from ~40 to ~8 levels, but the
    line stays visible and the fog turns the blue sea grey-purple, undoing the sea-color fix. Cause found: the engine
    sky at the horizon is 31% toward sky_top and fog is one flat color, so no fog color matches the horizon along the
    whole rim while the near sea keeps its color. The fix would be an engine change (fog toward the sky color along
    the view ray); left for Jake to decide.
  - Beam end, attempt 1 pass: color_pattern/color_mix `u*u*(3-2*u)` fades the cone to nothing; no flat cap.
  - Boats, attempt 1 pass: hull already a pointed loft; mast radius .035 -> .07 and #695041 -> #B89A78 makes the mast
    readable so the lamp no longer floats.
  Guidance (schemas.py, docs/world-authoring.md) and RULES.md updated for the beam and mast.
- New live take `e2e-glow3` with the updated guidance (first launch hit "Gateway starting: deadline" before warmup,
  kept in `e2e-glow3/failed1`; relaunch ok). Kept as the best lighthouse take. Plan:
  `projects/35bb301718e240d79eb65796088e9bd7/plans/6a70c3c2a8d14108936f1c3b8ac199e2.json`, export in
  `logs/e2e-glow3/export`. Decoded frames reviewed: beam eases out with no flat cap, masts #B89A78 read as wood,
  sea stays blue, no fog washout.
- `scripts/check_demo_scene.py` on the takes:

  | Take | Fog / sea / horizon | Beam | Boats | Exit |
  |---|---|---|---|---|
  | glow2 | PASS | FAIL (fade slope .05) | UNMEASURED | 1 |
  | glow3 | PASS | PASS | UNMEASURED (assembly parent / tilt / instance rotation) | 3 |

  Still open on glow3: the far rim / corner line (needs the engine fog change above) and sea hue 231, near the top
  of the band.

## Opt-in `fog_sky_blend`: 3 attempts, all failed, reverted (2026-11-08, approved by Jake)

Pass condition, fixed before measuring (`scripts/check_rim.py`): rim step median <= 10 RGB levels, every frame <= 14,
and the existing sea-hue and luma checks. Baseline on the glow3 plan: 47.6 median, 56.8 worst; sea hue 231, luma pass.
Offline probes on a scratch copy of glow3, decoded export frames, the option implemented in the shader:

| Attempt | Change | Rim median / worst | Sea hue | Luma | Result |
|---|---|---|---|---|---|
| 1 | `fog_sky_blend` 1, density .002 | 45.8 / 55.9 | 231 pass | pass | FAIL |
| 2 | attempt 1 + density .006 | 25.8 / 33.7 | 261 FAIL | pass | FAIL |
| 3 | attempt 1 + rim `color_high` #FFB9D1 | 46.2 / 56.0 | 231 pass | pass | FAIL |

- Attempt 2 reaches about 85% fog at the rim. The remaining 15% still shows about 26 levels after display gamma, and the
  haze covers the near sea and turns it violet.
- A larger disc cannot raise rim fog at low density: the far plane is fixed at 400 (`runtime/world.js`), so a wider rim
  clips into a new hard edge. Moving the far plane was outside the approved change.
- Attempt 3 came from inferring the albedo that would equal the sky; red needed 1.44 linear, so it was clipped. It also
  failed the existing horizon check, and made no measurable difference to the rim.
- Engine reverted: `runtime/world.js` is byte-identical to 36c3cf9. Because nothing shipped, the bit-identity proof on
  the rain scene and the Violet Hour Gate was not needed and was not run post-change; only the pre-change controls exist
  (decoded frames 8/8 identical, WebM bytes equal between repeat exports). No RULES.md line, no new take.
- Fallback per the approved plan: guidance for a low headland or island silhouette in front of the rim (`schemas.py`,
  `docs/world-authoring.md`). Not rendered or tested in a live take.

## Recording

Best-of-N recording on Monday (approved): several takes of each beat, the best one used, disclosed in the post.
