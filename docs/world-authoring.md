# Generated world authoring

This is the current primary-side scene system. The second developer's isolated source-intake assignment must not modify it.

## Workflow

1. Inspect a user-selected folder and recover supported image formats as needed.
2. Obtain consent for the chosen agent's image input and view selected references using Hermes's native vision route.
3. Describe concrete observed features: palette, silhouette, repeated forms, depth relationships, texture, mood cues. Separate invented scene elements from observations.
4. Author `rekindra_create_world` scene v2. Choose geometry and motion that express those features; do not default every source to ocean/torus imagery.
5. Open the HTML, export and inspect the actual rendered sequence. A valid schema and successful export are not creative acceptance. Check silhouette, framing, foreground obstruction, lighting, independent movement, and temporal progression.
6. Critique actual rendered frames and submit a revised world if needed. Revisions are new immutable plans. Keep the returned plan ID and artifact path: the current project status inventory still lists original/recovered artifacts, not generated plans.

The active-agent route does not require a second model login or plugin-owned credentials. The separate `ctx.llm` route remains optional and has an unresolved native-chat/Python-client auth mismatch on this development installation.

## Creative acceptance: source recognition is only the first step

Contrasting botanical and geometric live-agent trials both recognized the sources but initially produced small, nearly literal sculptures with subtle periodic movement. Neither first draft was accepted creatively, despite passing all browser checks. Do not equate a new mesh with a compelling new creation.

Before authoring, choose three concrete visual cues from the source, an invented spatial concept, and visibly different opening/transformation/resolution states. Keep observed evidence separate from inventions. For a transformation, use bounded time progress such as `clamp((t-2)/6,0,1)` inside formulas; sinusoidal motion can add life but need not carry the whole story. This is guidance, not a required visual template: a user-requested ambient loop may deliberately stay cyclical.

Frame the important forms at useful scale, preserve their silhouettes, and check depth from the actual camera. Review color identity after shading; source hex values alone do not guarantee a matching rendered palette. Do not solve every empty frame with extra objects or every weak composition with camera movement.

Inspect decoded frames from the exported video at the beginning, middle and end. Ask separately: are source cues recognizable, is the invention substantial, is the transformation legible with a fixed camera, is framing readable, and does the final state feel intentional? Automated motion and integrity checks cannot answer these aesthetic questions. Feed observed defects and the actual contact sheet back to the authoring agent, then render the revision. This development review loop is currently external tooling, not an autonomous plugin feature.

`scripts/make_variety_sources.py` reproduces the original synthetic visual references on D: in `.local/variety-study`. These test rendering and creative interpretation only; they are unrelated to the second developer's intake fixtures and do not establish performance on real damaged archives.

## Geometry, clock and camera

Each object is a parametric surface defined by x/y/z expressions in `u`, `v` (both 0..1) and `t` (seconds). Y is up; positions are world units. The agent can construct planes, folded sheets, spheres, arches, loops, terrain and other surfaces by combining mathematics. These are not canned visual templates. There are no arbitrary-code, file, network or shell operations in the expression language.

Allowed arithmetic: addition, subtraction, multiplication, division, unary signs. Functions: sin, cos, abs, sqrt, exp, min, max, pow, clamp, mix. `pi` is available. Multiplication must be explicit. Use `pow(a,b)`, not `a**b`. Formulas are parsed as an expression tree, whitelisted and emitted as bounded shader arithmetic; they are never evaluated as Python/JavaScript code.

Objects may include optional ordered `bindings` (maximum 16), each `{ "name": "opening", "expression": "clamp((t-1)/6,0,1)" }`. A binding can use u/v/t/pi and earlier bindings. Position and color expressions can use all bindings. Names are unique lowercase identifiers, up to 24 characters, and cannot replace built-in variables or functions. Unknown names, cycles and forward references fail. This supports reusable timing, hinge angles, local coordinate frames and compound forms without repeating long formulas. Bindings are recalculated for each sampled surface coordinate, including finite-difference normals and shadows; they are not shared mutable state. Their expression cost counts toward the work budget.

For example, define `opening=clamp((t-1)/6,0,1)`, `angle=.1+1.2*(opening*opening*(3-2*opening))`, `length=3.2*u`, and then use `length*sin(angle)` and `length*cos(angle)` for a coordinated hinge. These are expressions in binding records, not executable assignment statements. Keep local radial, tangential and normal directions orthogonal when rotating width/thickness with a shell.

For spatial accuracy, reserve separate regions for moving parts and think through swept motion, not only endpoint positions. In a radial arrangement, tangential half-width must remain inside each angular sector even in the closed state; seeds or other central objects need a clear corridor until outer shells open. Intentional contact and camera occlusion are different from surface penetration. The renderer does not perform collision detection or prove a scene intersection-free. Review intermediate rendered states and distinguish supported observations from claims about unseen states. In source references, `observed` describes the actual source file; render-review observations belong in the revision rationale.

Numerical semantics deliberately avoid undefined GPU results: arithmetic intermediates clamp to +/-10000; division denominators have minimum absolute magnitude .0001; sqrt uses max(input,0); exp clamps its input to +/-16; pow clamps the base to .0001..10000 and exponent to +/-8; mix clamps its factor to 0..1; output positions clamp to +/-100. For predictable results, author well inside these bounds rather than depending on the clamps.

The camera takes explicit eye/target/FOV states over the full duration. Geometry, shading and camera all evaluate from the same time. Camera orientation uses deterministic parallel transport over a fixed time table, so viewing almost straight up does not trigger a sudden reference-axis roll. Projection uses near .1 and far400, covering the validated position domain. Camera keys must not cross their target between states.

## Rendering and limits

Original WebGL2 renders into an offscreen canvas, which the shared player/exporter consumes. Surface normals come from local derivatives. Materials expose two colors and a blend expression, roughness, metalness, and emission. Direct lighting uses a GGX microfacet distribution, Smith masking and Schlick Fresnel with colored metal reflectance. The sky reflection remains an analytic approximation, not a prefiltered HDR environment. This is original implementation of established shading mathematics, not an imported engine; conceptual reference: [Filament material model](https://google.github.io/filament/main/filament.html).

Directional light now honors `sun_strength` on surfaces and casts approximate soft shadows. A fixed 2048-square depth map uses a camera-derived lateral region and enough depth to include all clamped legal geometry along the light ray. Receivers outside the lateral region are unshadowed. A bounded 16-sample blocker search and 32-sample disk filter estimate penumbra from `sun_size`; this is not ray tracing or exact area-light integration. Very thin features and near contacts can still show shadow-map artifacts. The map evaluates from the same time as geometry and export; no frame-history accumulation occurs.

Optional environment controls: `fill_color` defaults to #B8D1FF, `fill_direction` defaults opposite the normalized key light horizontally with positive elevation, `fill_strength` is 0..2 (default .25), and `exposure` is .25..4 (default 1). Fill is deliberately unshadowed studio fill, not global illumination. Set fill strength to zero to remove it. Dark scenes need sufficient fill to show material shape; exposure cannot restore absent lighting. Tune roughness and illumination together instead of brightening material colors indiscriminately.

There are no object-to-object ray-traced reflections, physical fluid simulation, translucent leaf materials or full global illumination. Do not promise those or arbitrary-complexity exact reconstruction.

Up to12 objects, each grid4..128 by4..96, <=32000 cells combined, and expression-weighted work <=4000000. Each expression <=512 characters,128 nodes,24 levels; literals <=1000 magnitude. Camera2..12 states. Duration4..30 seconds at1280x720. Source selection remains1..6 images and existing source byte/pixel bounds. No text primitives in v2; v1 text remains opt-in.

WebGL2 is required for worlds; native VP8 WebCodecs encoding is required for export. Rendering/context errors must fail visibly. Original source hashes and embedded image integrity are retained even though world pixels are generated. Source descriptions are agent-authored interpretations, not verified forensic findings.

## Development verification

`scripts/make_world_fixture.py` generates an authored benchmark, explicitly not model output. `scripts/browser_scene_test.cjs` accepts an HTML path and `REKINDRA_WORLD_STUDY=1` to additionally check that source image pixels are not drawn, geometry still moves with a fixed camera, and decoded exported video frames can be inspected. `REKINDRA_BROWSER_OUTPUT` selects its output directory. All task data on Jake's Windows development machine stays on D:.

The filmstrip is sampled decoded video, not proof of human-like continuous viewing. Review multiple times and full playback behavior; do not equate a frame-difference statistic with beauty or usefulness.

`scripts/review_video.cjs VIDEO OUTPUT_DIRECTORY` creates four sheets containing 24 decoded video samples with timestamps outside the image frames. It is development tooling with Playwright, not a production dependency or text added to the video. Use it to inspect transitions and spatial conflicts missed by a six-frame overview.
