# Surface relief study — November 5

This is a developer-controlled material comparison, **not a new autonomous Hermes authoring trial or showcase acceptance**. Audio remains deferred.

Implemented original optional `bump_detail`: restricted per-pixel height math, world-space surface-gradient lighting normals, +/-0.1 height and 0.6 slope limits, existing shared 128-node fragment budget. Geometry, silhouettes and geometric shadow bias stay unchanged. No borrowed rendering engine or production dependency.

## Evidence

- Failing tests first: validator rejected the new field; actual GPU test showed zero changed pixels because the renderer ignored it.
- After implementation: 50 Python tests and 6 Node tests passed. Existing material GPU regression unchanged (60,202 changed samples, maximum delta7); shadow regression unchanged (clear255, occluded48).
- New GPU regression: 327,271 changed pixels on a 4x4 mesh, maximum channel delta42; animated relief changed329,642 pixels. Zero and constant extreme height produced identical pixels to the baseline. No pixels outside the surface changed.
- Two controlled scene comparisons, then two revisions. Harbor initially used overly regular crossed waves; revised to phase-modulated ripples and roughness0.34. Ruins initially used height0.012 and looked carved; reduced to0.002. These are developer-authored changes to prior native plans, not evidence that the native agent chose the new capability.
- Export/decode checks succeeded for both revised 12-second 1280x720 WebMs: harbor6,962,927 bytes, ruins5,488,248 bytes. Reviewed all24 decoded sample thumbnails per video plus full-size representative stills. This is sampled review, not continuous playback or collision proof.

## Strict verification failure retained

The harbor full browser check failed same-time equality:12 color channels differed by1. Do not label these exports fully verified. A subsequent10-trial comparison found the unchanged harbor baseline failed2/10 (11 channels, delta1); the revised scene passed10/10 in that run. This does **not** establish a fix: a separate raw-WebGL diagnostic reproduced12 changed channels at delta1 in1/10 revised-scene trials. The same difference survived the2D copy. Thus at least one source is upstream of canvas transfer; disabling comparisons or adding tolerance would hide it. Existing M01 reproducibility concerns remain open.

`scripts/trace_world_seek.cjs HTML OUTPUT` now preserves raw versus copied pixel diagnostics. It deliberately synchronizes via readPixels; compare with `check_seek_repeat.cjs`, which tests the real player without that instrumentation.

Local artifacts: `.local/relief-study/`; `first-artifacts.json` preserves first-pass IDs, `artifacts.json` the revised IDs, `*-diagnostic/decoded/decoded-overview.png` the decoded reviews. Final study plans: harbor `9bdec168e0cc4ebf9b184981a7744308`, ruins `03e61cf383df43729ff6dd65289d26e8`.

## Visual judgment and next priorities

Water now has light-responsive moving detail, but distant repetitions remain visible. The harbor still reads as a model: solid-color sail triangles, hollow-ended piers, basic building, broad barren shore, and no object reflections or wakes. The ruins still lack masonry organization; pigment streaks and UV stretching dominate grain. Its tree is sparse and angular, and its opening is too quiet. Neither is accepted as impressive.

1. Diagnose strict frame repeatability at the WebGL stage. Keep exact checks and distinguish real renderer state from graphics-driver numerical variation.
2. Improve authorable object construction: closed ends, connected parts, intentional proportions, grouped motion and controllable detail allocation. Do not simply increase the geometry limit. Validate with boats/architecture and an unrelated subject.
3. Add bounded reflected-object/contact cues. A single explicitly horizontal reflection plane is a candidate to investigate; it costs an extra render pass and needs clipping, roughness treatment and fallback tests. It is not implemented here.
4. Re-run native Hermes on fresh source folders with the new tools and stricter visual selection. Agent-generated results, not hand-polished examples, are the acceptance target. Give the opening a clear action and the ending a visible consequence.
5. Real Mac/Linux browser runs, then audio reuse and audio-inspired creation after visual and export reliability improve.
