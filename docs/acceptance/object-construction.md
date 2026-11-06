# Object construction studies — November 5

## Implementation and verification

Original runtime additions: optional animated end caps, then repeated mesh parts with offset/nonuniform positive scale. Caps use the same moving boundary positions as the side mesh and flat face normals; they cast shadows. Repeated parts share a mesh/material, with up to16 placements per definition and64 across the world. Every placement consumes the unchanged cell, expression-work and material-detail budgets. No outside creative engine, audio work, or intake-owned changes.

Caps are for closed planar convex/star-shaped rings with the boundary average inside the kernel. They are not arbitrary solid repair. Instances do not yet support parenting, rotation, independent time or per-copy materials.

Tests failed before implementation: new fields rejected; cap test still saw the sky through the tube; instance test still drew an object at the origin. After implementation, GPU checks show closure and animation, fine side detail leaves caps unchanged, an offset capped tube shadows the floor (212 open versus105 closed), and differently scaled copies occupy11,593 and33,534 colored pixels with an empty origin. Existing relief/shadow regressions remain unchanged. Python tests and7 Node tests pass in cross-platform CI. Actual browser/GPU checks here are Windows-only.

Live authoring also exposed an unadvertised40-character surface-ID limit. The schema now advertises its length/pattern and the error explains the permitted characters. Geometry budget violations continue to be rejected with rescaling guidance.

## Harbor: controlled closure, then native revision

Starting project `87b7964420934511beb25b476ae71441`. Controlled plan `ad3feae555f84fa6ad818066179d2841` adds caps to the two piers and connecting quay in the prior relief study. Review confirmed solid ends without changing the fleet.

The old resumed native session had accumulated roughly106,000 tokens and repeated provider errors. It was interrupted through the per-session gateway control, without stopping the independent city trial. It authored no new saved plan. Logs are preserved as `harbor-events.jsonl`. A clean session resumed from the saved scene instead of inheriting that conversation. Native main-provider authentication worked; auxiliary compression authentication remains unavailable.

Clean session `local-3f123f3d69e70cce6096470eb1d967b0a7faf3af42b707651322c76df14144f0` authored:

- `e15b2e7ca2e64226b5990935002b2da9`: longer/narrower hulls, continuous cockpit depressions, curved sails and articulated boathouse. Better focal construction than the starting draft.
- `733e1b8ced3e4a6981499da7e226a9a5`: opposite elevated construction view, discarded as presentation.
- `87f3d2183aea4fefaf90b480fa6cb6b5`: native-retained final, with stronger sail camber, reduced building scale and revised shore/woodland.

Evaluator viewed all three native review sheets and24 decoded final samples. Final browser checks and WebM export/decode passed in this run. This does not resolve the intermittent repeat-render defect found in other trials. The hull/sail construction improved; the final woodland introduced pointed/repetitive geometry and is a visual regression relative to the first revision. Cockpit fittings and rigging remain simplified, water repetition remains visible, and the environment is still schematic. No showcase acceptance.

## Fresh night-city folder B01: no scene-specific direction

Fresh session `local-19c86d9dda5fdbb2a222a1652bd48752ba0a3a0271d0cd39f940ceb1654d9daa`; project `5317c09f2da140e5ad7f4cd522483bf3`. The agent viewed two sourced photographs and read the constructed collection notes/index. No equations, palette, object list or camera plan was supplied. This run used caps before repeated placements were installed.

It independently chose a magenta-edged crossing that arches between unequal towers. Four saved worlds and four native previews:

- `0b47cde7d4af4e98b40b2bc54ff656fb`: first draft; water/land overlap, jagged backdrop.
- `076339a89d274a74a5c4bec8a19150ce`: separated banks and closer framing; added wall erroneously crossed the canal.
- `8ff18a458927475aaa76154e9193ddff`: removed that wall and replaced wavy backdrop with capped hall/roof; reverse-angle inspection.
- `0b298faf362f429eba810c1c78078c8b`: retained main camera around corrected geometry.

The agent independently identified and fixed actual construction defects. Evaluator viewed all four sheets and24 decoded final samples. It still looks sparse and toy-like: soft window dots, simple towers, repetitive hall and an unexplained stretching bridge. All12 distinct surfaces were used. This motivated repeated parts, not a blanket budget increase.

The full browser check failed strict repeatability by **one channel at delta1**. The separate diagnostic WebM exported/decoded (3,571,387 bytes;12 seconds;1280x720). Do not label it fully verified. This is evidence of source-specific invention and some autonomous correction, **not** evidence of reliable autonomous high-end visual quality.

Local evidence: `.local/construction-study/` holds exact queries/events, native summaries, controlled studies, browser failures and decoded outputs. Portable draft JSONs replace machine-local source IDs with placeholders; they are review records, not templates the native trials may copy.

## Fresh botanical folder A02: repeated parts used independently

Fresh session `local-247c7dad35ef268ac652621d1a34f5d43b9741f9012c96ba716c5bbfcb5de60e`; project `e2ab465a08264c4e9a0eb39ee9f00070`. Generic authoring/review instructions only: no supplied composition, geometry, palette, camera or prior example scenes. Installed code included repeated parts. The agent viewed both sunflower photographs and read collection notes/index, distinguishing the curated collection from recovered personal history.

It chose a passage through rooted sunflower gates, independently using instances for stems, corollas, disks, leaves and shrubs:

- `4af490f7e4354c0885a002dd19610792`:32 placed surfaces from12 definitions, six flowers. It identified sparse bare ground, drifting right-leaf joins and cropped foreground heads.
- `23a54677b6bd42b3a6f4887e3c23335b`:39 placed surfaces, eight flowers, mirrored leaf attachments and green beds. Temporary side/rear view exposed joins and head thickness.
- `25ebbe51e3b74bf4864766ba72511813`: final approach camera preserves the front flowers; eased bending/turning, subtle disk relief, larger shrub patches. All39 placements remain inside the unchanged budgets.

The evaluator viewed all three native review sheets and24 decoded final samples, including a larger late-sequence sheet. Final browser checks, independent geometry motion, source-image exclusion, export/decode, offline behavior and cancellation checks passed in this run. The12-second1280x720 WebM is10,777,346 bytes. Harbor's final WebM is7,163,494 bytes. These passing trials do not erase B01's strict equality failure.

One native provider call timed out after300 seconds without substantive progress and automatically retried successfully. This also occurred with a much smaller context than the old harbor session; long history is not established as the sole cause of provider failures. No new login or fallback provider was used.

The botanical assembly and final framing are visibly stronger than its first draft. The tool transferred beyond boats/buildings without evaluator-supplied geometry. However, the planting remains sparse, repeated one-leaf proportions look schematic, rear heads overlap in projection, shrubs resemble painted buttons, and the lighting/background remain plain. **Not accepted as showcase-ready.** Source-grounded invention and useful autonomous correction are demonstrated in these cases; arbitrary-folder quality and collision freedom are not.

## Recommended next work

1. Targeted scene-edit and alternate-view tools: revise one component or camera without resubmitting every surface. This should reduce expensive context growth and accidental changes; measure it rather than assuming it fixes provider timeouts.
2. Shared assembly transforms/attachments, so related parts can follow one motion definition. Current independent surfaces still require the agent to duplicate consistent formulas.
3. Improve lighting, environmental depth and reflected/contact cues using these richer assemblies. Compare against retained drafts; reject detail that makes silhouettes or materials worse.
4. Keep the exact repeat-render defect open and obtain real Mac/Linux browser checks. Audio remains deferred.
