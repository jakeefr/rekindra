# Concept and material quality follow-up

This follows the 16-folder matrix. Audio reuse/audio-inspired creation is deferred
per the user; see `docs/deferred-audio.md`.

## Changed authoring guidance

The native agent now compares three source-led premises before authoring and
briefly records its selection in the scene rationale. It assesses source
specificity, supporting space, material contrast and progression separately.
This is general guidance, not a supplied geometry/camera recipe. Initial follow-up
runs received the same guidance explicitly in their query because an already
running host may cache tool descriptions. Production tool descriptions contain
the same guidance.

## Fresh native runs before evaluator direction

### C02: ruins photograph and painting

Project `ed9342a042564a7d9a4c715979f94dae`; first plan
`ce2ed32a1c554020b7127c7713fa1770`, retained autonomous revision
`51d5c86853e5433092bb0b17e8c19d91`.

Two worlds and two native previews/vision critiques. Both previews and 24 decoded
samples of the revision were inspected by the evaluator. Browser checks passed.
Compared with the earlier floating-arch sculpture, the new scene has a receding
arcade, banks, trees, water and travelling cloth. It depends more on the sources
and establishes a landscape. Native revision reduced fog and water-edge gaps,
changed trees, enlarged cloth and adjusted the camera.

Still rejected as showcase work: smooth bent-pipe stone, candy-like tree lobes,
striped canal, small cloth and weak final payoff. A populated environment is an
improvement in scope, not proof of polish.

### D02: rain paving and marina photographs

Project `87b7964420934511beb25b476ae71441`; retained autonomous plan
`ae85f25a5c5c48f3b7182c37ef99e6ab` after three authored worlds/previews.
Final native preview and 24 decoded samples inspected; browser checks passed.
Rain crowns become small sailboats departing between piers, with a shoreline.
This connects the two sources more specifically than the earlier purple opening
bowl. However, hulls resemble open rolled shells with holes, sails are thin fins,
the shore structure is billboard-like and the environment/materials are flat.
Still rejected as showcase quality.

## Per-pixel color detail capability

Renderer inspection exposed a constraint: existing color_mix runs per vertex,
so finer patterns cannot resolve on coarse geometry. Optional `color_detail`
now evaluates bounded math per pixel. It modulates linear albedo by 0.65..1.35,
with 128 characters/32 nodes per expression and 128 nodes across the world.
Geometry bindings are excluded. Existing shader path remains when absent.
This is color variation only, not normal mapping or displacement.

Python tests first failed on the unsupported field and detail limits, then passed.
Real-browser coarse 4×4-plane test first measured zero changed pixels (failure),
then 60,202 changed red-channel samples with max difference 7. Extreme ±1000
expressions produced bounded differences of 8 rather than blowing out or
blackening the material. Evaluator viewed the actual detailed render. This proves
the capability resolves detail; it does not establish impressive artistic use.

49 Python and six Node tests passed. Independent read-only review found no
important issues. Commit `fb57527` passed the existing six-job CI matrix:
https://github.com/jakeefr/rekindra/actions/runs/42133571154
Real-browser visual verification remains Windows-only.

## Directed continuations

Evaluator supplied the visible defects above and the new material capability,
without scene equations or a camera recipe. These continuations are separate
from the autonomous first runs. First C02 continuation failed to connect during
gateway restart; its failed transcript is retained, then it was retried after
the gateway became ready. Existing Codex main-agent sign-in continued to work;
auxiliary title/client auth warnings are not a request for a second login.

### Ruins continuation

Three new worlds and exact native preview/vision reviews:
`8d1297283cdc45b59e0f3dcc21983d5a`,
`6d9c6ef619714fa6a163fbb4ba7c3fa0`, and retained
`f9a79ed75bf449c78f7e38da31b42526`.
Evaluator inspected all three preview sheets plus 24 decoded samples of the final
12-second 1280×720 export (5,049,198 bytes; SHA-256
`28a68a12dcdcf8814f73493bf9c3fb0aee2e898afbbcf4df4969de0eb6166a1f`).
Full browser checks passed, including exact seeking on this artifact.

Thick broken wall masses replace pipe arches; an irregular pool replaces the
striped channel; cloth now approaches at readable scale and clears the doorway.
After previewing lumpy foliage and excessive mottling, the native agent removed
the foliage blobs and reduced stone detail. It successfully authored the new
material field through the installed plugin. Still below showcase quality:
stone reads as carved plaster with wavy color rather than masonry, bare branches
are sparse, the pool lacks convincing reflections, and the opening is too quiet.
This is improved structure and readability, not a claim of impressive realism.

### Harbor continuation

Three new worlds/previews:
`133c4644acaa49c58f8af06947ec912e`,
`bcaa931d90a14853b9d6657a27595e7e`, and
`33ee2bdd4cd546e884272479964c0319`. All three preview sheets were inspected by
the evaluator, plus 24 decoded samples of the third. Browser checks passed.
Native preview contention returned explicit busy errors during concurrent work;
the agent retried successfully. One over-budget candidate was simplified rather
than increasing renderer limits.

Closed decked hulls, properly oriented sails, a connected quay and volumetric
boathouse improve the earlier shell/fins/billboard shapes. However, the third
revision's low opposing light produces broad white glare and conspicuous long
shadows. The evaluator rejected that optical tradeoff and requested a focused
continuation preserving the improved geometry.

The focused revision `8dde81456a4a4acab478bed06290f691` raised/turned the key,
changed key/fill balance and light size, and increased hull roughness while
preserving geometry, timing and exposure. Native vision and evaluator inspection
of its preview plus 24 decoded samples confirm the broad white glare is gone and
shadows are shorter. Full browser checks passed, including exact seeking.
The final 12-second 1280×720 WebM is 4,771,617 bytes, SHA-256
`c1c5d4b4ac0f1f266b377a4c5a64b6de5c20eaaa365f8a5dd4b0b6634e507426`.

This is the retained harbor draft. It is much more readable than the initial
rolled shells/fins and corrects the rejected lighting, but remains a sparse toy-like
marina. Water lacks wakes and convincing reflected surroundings, shore vegetation
is unresolved and the building is simplistic. It is not accepted as showcase quality.

The optical continuation initially rejected an incompatible max-turn override
on a resumed session. It was retried without that override; no scene was authored
by the rejected command.

## Saved evaluated scenes

`docs/acceptance/scenes/` preserves selected authored scene documents for code
review and reproduction. Source IDs are replaced with `a`/`b` placeholders to be
mapped to the corresponding corpus case's two actual project image IDs. These
are evaluated drafts, **not** recommended aesthetic templates or accepted demos.

The retained ruins and harbor JSON both validate after placeholder substitution.
Temporary native run budget was restored to 120 after the sessions finished.
No delegated intake paths were modified. The real-browser shadow regression also
passed on the updated renderer (isolated receiver255; real blocker48), confirming
that the material addition did not disable the existing shadow behavior.

Next quality work should improve environmental richness, water/foliage expression
and deliberate visual style rather than repeating cosmetic revisions to these
two scenes. The per-pixel control provides additional capability; scene quality
still depends on authored shapes, lighting and temporal design.

## Exact-seek issue

Further isolated experiments disabling WebGL dithering or multisample
antialiasing did not fix M01 repeat-frame differences (both failed eight of ten
trials). Neither candidate entered production. The strict regression remains
unresolved; no tolerance was introduced.
