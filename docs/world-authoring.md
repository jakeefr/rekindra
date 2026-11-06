# Generated world authoring

## Repeated parts

A surface may specify `instances: [{"offset":[-2,0,0],"scale":[1,1,1]},
{"offset":[2,0,0],"scale":[0.7,1.4,1]}]`. These place the same animated local
geometry/material after scaling about its origin, then translating. Caps, normals
and shadows follow each placement. Omit the field for a single unchanged surface.

Limits:1–16 placements per surface,64 placements across the world; offsets -80..80,
positive scales .05..8. Every copy consumes the unchanged geometry, expression-work
and fragment-detail budgets. Optional static Euler rotation follows scale and precedes
offset (see Per-copy orientation). There is no per-copy parenting, independent
animation or per-copy material. Final coordinates still clamp to +/-100.

Use low-resolution local meshes for repeated windows, supports, roof clusters or
foliage. Place parts deliberately and vary scale where meaningful; repetition is
not a substitute for composition. Keep small instances free of expensive fine
material expressions. Prefer source-specific assemblies over generic rows of boxes.

## Solid ends and connected construction

Optional `caps: ["v0", "v1"]` closes the selected v boundaries with triangle fans
around their boundary average, evaluated at the same time as the side surface.
Use it only when u wraps a closed, planar convex or star-shaped ring (with its
average inside the kernel). The fan does not repair arbitrary concave holes,
nonplanar ends, open u seams, or self intersections. Caps have flat triangle
normals, interpolate the surface's vertex colors, and omit fine color/bump detail.
They cast shadows and share the existing cell/work budgets. Omit for sheets,
cloth, terrain and water. Existing scenes without caps retain the old topology.

For assemblies, establish attachment points and share the same time-dependent
translation/bend definitions between adjoining surfaces. Inspect a side or
reverse view when joins are hidden. Decide thickness and proportions before
material noise; reserve surfaces for the focal construction. Automatic caps
remove endpoint bookkeeping, not the need for visual judgment.

This is the current primary-side scene system. The second developer's isolated source-intake assignment must not modify it.

## Workflow

1. Inspect a user-selected folder and recover supported image formats as needed.
2. Obtain consent for the chosen agent's image input and view selected references using Hermes's native vision route.
3. Describe concrete observed features: palette, silhouette, repeated forms, depth relationships, texture, mood cues. Separate invented scene elements from observations.
4. Author `rekindra_create_world` scene v2. Choose geometry and motion that express those features; do not default every source to ocean/torus imagery.
5. Call `rekindra_preview(project_id, plan_id)` and inspect its returned PNG with native vision under the user image-sharing consent. Use the HTML video exporter and decoded-video review when export-specific inspection is needed. A valid schema and successful export are not creative acceptance. Check silhouette, framing, foreground obstruction, lighting, independent movement, and temporal progression.
6. Critique actual rendered frames and submit a revised world if needed. Revisions are new immutable plans. Keep the returned plan ID and artifact path: the current project status inventory still lists original/recovered artifacts, not generated plans.

The active-agent route does not require a second model login or plugin-owned credentials. The separate `ctx.llm` route remains optional and has an unresolved native-chat/Python-client auth mismatch on this development installation.

## Creative acceptance: source recognition is only the first step

Contrasting botanical and geometric live-agent trials both recognized the sources but initially produced small, nearly literal sculptures with subtle periodic movement. Neither first draft was accepted creatively, despite passing all browser checks. Do not equate a new mesh with a compelling new creation.

Before authoring, choose three concrete visual cues from the source, an invented spatial concept, and visibly different opening/transformation/resolution states. Keep observed evidence separate from inventions. For a transformation, use bounded time progress such as `clamp((t-2)/6,0,1)` inside formulas; sinusoidal motion can add life but need not carry the whole story. This is guidance, not a required visual template: a user-requested ambient loop may deliberately stay cyclical.

Frame the important forms at useful scale, preserve their silhouettes, and check depth from the actual camera. Review color identity after shading; source hex values alone do not guarantee a matching rendered palette. Do not solve every empty frame with extra objects or every weak composition with camera movement.

### Art direction before surface detail

Write a one-sentence visual premise before choosing equations: what recognizable source relationship becomes what new moving form? Pick a dominant subject and a deliberate supporting environment. A collection of equally weighted objects on a rectangular slab is not automatically a composition. A source's colors and repetition can survive a substantial change in spatial form; an interpretation need not be a literal extrusion.

Use the first preview to evaluate large shapes before polishing small details. In a showcase composition, the subject should have useful screen presence from the opening, not spend several seconds growing from an insignificant speck. Preserve intentional negative space and silhouette gaps. A dramatic close-up can be appropriate, but cropping must be deliberate. Do not treat a fixed screen-coverage percentage as a universal rule.

Keep a short revision ledger: observed defect, proposed cause, changed controls, result in the next preview. Prioritize framing and silhouette, then temporal progression and spatial conflicts, then lighting/materials and fine detail. If a corrugated tower still looks like a corrugated tower after changing roughness, change its geometry rather than repeatedly polishing it. Avoid adding high-frequency ribs to every surface; subtle detail should reinforce the large form. Moderate roughness often reveals shape more clearly than an intense highlight.

Assess geometry clearance and projected overlap separately. Separate world-space lanes can still obscure each other in an oblique view. Inspect the chosen camera's opening, transformation and resolution. Strong motion should change a readable relationship or silhouette, not merely produce a nonzero frame difference. A final hold should resolve the motion intentionally. These are review questions, not a prescribed ribbon, sculpture, studio or color style for all sources.

After two or three revisions, compare with the baseline explicitly and retain the strongest version. If the premise remains weak, reauthor it rather than endlessly tuning exposure. Report remaining shortcomings. The renderer's limited geometry/material model can constrain an ambitious concept; do not disguise those limits as successful reconstruction.

Inspect decoded frames from the exported video at the beginning, middle and end. Ask separately: are source cues recognizable, is the invention substantial, is the transformation legible with a fixed camera, is framing readable, and does the final state feel intentional? Automated motion and integrity checks cannot answer these aesthetic questions. Feed observed defects and the actual contact sheet back to the authoring agent, then render the revision. The plugin now supplies rendered contact sheets through `rekindra_preview`; the active agent must still view and critique them. A contact sheet does not establish encoded-video correctness or make aesthetic acceptance automatic.

### Continue from diagnosis, not from a passing test

Before equations, record a compact visual brief: dominant subject, supporting place, material contrast, motivated light sources, and opening/transformation/resolution. A camera move needs a purpose such as revealing thickness or disclosing the destination; endless drift is not a substitute for design. Compare light-facing and shadow-facing surfaces before adding texture. If material variants merely trade matte slabs for noisy slabs, preserve the cleanest version and change construction or composition in a new, explicitly scoped unit. Do not reset the failed unit's attempt counter or describe a new hypothesis as a successful fix.

Passing a bounded unit does not end a broader user-authorized quality task. Preserve its evidence, identify the next failing visual criterion and continue independent work. Stop for actual completion, an external blocker, or an applicable explicit budget—not because another contact sheet was generated. Reference research in `docs/research/ansphare-cinetic-quality.md` informs this workflow; no external creative engine is required.

### Optional contact depth

`environment.occlusion_strength` (0..1, default0) enables bounded screen-space attenuation of indirect ambient/environment lighting. `occlusion_radius` (.05..4, default1) sets its world-space reach. Use it subtly to distinguish nearby contacts and recesses; it does not affect direct lights or emission. It adds one camera-depth geometry pass and 16 fixed hemisphere samples, with no random temporal state. Missing/offscreen geometry cannot occlude, so review moving silhouettes for halos or changes at frame boundaries. It is not global illumination, local-light shadowing, or a substitute for connected construction. Existing scenes remain on the original path unless enabled.

`scripts/make_variety_sources.py` reproduces the original synthetic visual references on D: in `.local/variety-study`. These test rendering and creative interpretation only; they are unrelated to the second developer's intake fixtures and do not establish performance on real damaged archives.

## Geometry, clock and camera

Each object is a parametric surface defined by x/y/z expressions in `u`, `v` (both 0..1) and `t` (seconds). Y is up; positions are world units. The agent can construct planes, folded sheets, spheres, arches, loops, terrain and other surfaces by combining mathematics. These are not canned visual templates. There are no arbitrary-code, file, network or shell operations in the expression language.

Allowed arithmetic: addition, subtraction, multiplication, division, unary signs. Functions: sin, cos, abs, sqrt, exp, min, max, pow, clamp, mix. `pi` is available. Multiplication must be explicit. Use `pow(a,b)`, not `a**b`. Formulas are parsed as an expression tree, whitelisted and emitted as bounded shader arithmetic; they are never evaluated as Python/JavaScript code.

Objects may include optional ordered `bindings` (maximum 16), each `{ "name": "opening", "expression": "clamp((t-1)/6,0,1)" }`. A binding can use u/v/t/pi and earlier bindings. Position and color expressions can use all bindings. Names are unique lowercase identifiers, up to 24 characters, and cannot replace built-in variables or functions. Unknown names, cycles and forward references fail. This supports reusable timing, hinge angles, local coordinate frames and compound forms without repeating long formulas. Bindings are recalculated for each sampled surface coordinate, including finite-difference normals and shadows; they are not shared mutable state. Their expression cost counts toward the work budget.

For example, define `opening=clamp((t-1)/6,0,1)`, `angle=.1+1.2*(opening*opening*(3-2*opening))`, `length=3.2*u`, and then use `length*sin(angle)` and `length*cos(angle)` for a coordinated hinge. These are expressions in binding records, not executable assignment statements. Keep local radial, tangential and normal directions orthogonal when rotating width/thickness with a shell.

For spatial accuracy, reserve separate regions for moving parts and think through swept motion, not only endpoint positions. In a radial arrangement, tangential half-width must remain inside each angular sector even in the closed state; seeds or other central objects need a clear corridor until outer shells open. Intentional contact and camera occlusion are different from surface penetration. The renderer does not perform collision detection or prove a scene intersection-free. Review intermediate rendered states and distinguish supported observations from claims about unseen states. In source references, `observed` describes the actual source file; render-review observations belong in the revision rationale.

Numerical semantics deliberately avoid undefined GPU results: arithmetic intermediates clamp to +/-10000; division denominators have minimum absolute magnitude .0001; sqrt uses max(input,0); exp clamps its input to +/-16; pow clamps the base to .0001..10000 and exponent to +/-8; mix clamps its factor to 0..1; output positions clamp to +/-100. For predictable results, author well inside these bounds rather than depending on the clamps.

In particular, `pow(sin(a),2)` does not square the negative half-cycle under these bounded semantics. Bind `wave=sin(a)` and use `wave*wave` for a signed quantity's square, or use `pow(abs(sin(a)),2)` when that is the intended shape. This matters for symmetric ribs, thickness and color patterns.

The camera takes explicit eye/target/FOV states over the full duration. Geometry, shading and camera all evaluate from the same time. Camera orientation uses deterministic parallel transport over a fixed time table, so viewing almost straight up does not trigger a sudden reference-axis roll. Projection uses near .1 and far400, covering the validated position domain. Camera keys must not cross their target between states.

## Rendering and limits

Optional `environment.point_lights` accepts up to four static world-space lights:
`[{"position":[0,2,0],"color":"#FFB060","intensity":12,"range":8}]`.
Coordinates are -80..80, intensity 0..200 and range .1..80. These illuminate nearby
surfaces with the same GGX material response, inverse-square distance falloff
(softened inside .5 units) and smooth cutoff at range. They do not follow assemblies
or emissive meshes automatically. Place a light near the intended visible emitter
and check moving surfaces across the whole timeline. Material emission alone does
not cast light. These local lights are **unshadowed**: they can shine through walls;
keep range tight and avoid arrangements that require occlusion. The directional key
still owns the existing shadow map. This is direct illumination, not bounce lighting,
bloom, ray tracing or global illumination. Omitted/empty lists preserve legacy behavior.

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


## Native preview workflow

`rekindra_preview` regenerates a validated plan, copies the exact hash-checked HTML into an isolated work directory, and launches installed Chrome/Chromium/Edge headlessly. The original player draws six samples at `(i + .5) * duration / 6` into a 1280x1128 PNG with timestamps outside the frames. A completed JSON marker is required; waiting alone is never accepted as success. The returned result includes plan/project IDs, times, PNG hash and reviewed HTML hash.

This local tool does not call a model or send the image externally. The active agent can then use native vision under the user's image-sharing consent, name concrete defects, create an immutable revision and preview again. It must not claim to have watched or decoded video from this sheet. Do not iterate indefinitely: report remaining defects candidly if revisions do not improve them.

The browser uses an isolated profile/cache/temp under the project and is limited to45 seconds with a40MB DOM-output read cap and8MB PNG cap. No caller URL/browser flags, credential reuse, browser download, disabled sandbox or production Playwright dependency. A user may configure `REKINDRA_BROWSER` as an absolute executable path. Common Windows/macOS/Linux browser locations are supported; only Windows live behavior has been verified so far. Interrupted browser processes are terminated/reaped, temporary paths are containment-checked before cleanup, and the preview lock is always released. A locked temporary directory may remain if OS cleanup fails; no broad filesystem cleanup is attempted.

CLI background operation is based on [Chrome's official headless interface](https://developer.chrome.com/docs/automation-and-testing/headless-cli). Scene rendering and PNG assembly are Rekindra's own implementation. Headless native-browser requirements and graphics failures are surfaced to the agent rather than replaced with a fake preview.

### Shadow-filter depth correction

Filtered shadow taps now compare against the receiver plane's depth at each sampled texel center. Comparing all neighboring samples with only the center pixel depth caused false self-shadow on sloping surfaces. Screen-space derivatives determine the light-space depth gradient before any divergent coverage return. Degenerate gradients fall back to zero and finite gradient bounds limit unstable extrapolation; out-of-map taps are treated as lit. The blocker search uses the same correction as the final filter. This does not remove genuine self-cast shadows, solve arbitrary thin-geometry artifacts or replace geometric clearance checks.

Conceptual reference: [Microsoft's per-texel depth-bias explanation](https://learn.microsoft.com/en-us/windows/desktop/DxTechArts/cascaded-shadow-maps). The GLSL is original. `scripts/browser_shadow_test.cjs` is a development-only installed-browser regression that isolates the actual production shadow visibility calculation, checks a lone sloped receiver and preserves a separate occluder's shadow. It is not a production dependency or a complete curved-surface acceptance suite.

For a clean authored ribbon tip, avoid relying on a sparse mesh to approximate an infinite-slope square-root taper. Review the terminal centerline as well as width: narrowing a curled end alone leaves the hook. A short tangent continuation with controlled taper is one option, not a universal shape template.

## Source-specific concept selection

Before geometry, compare three materially different premises based on visible evidence: change the action and spatial relationships, not merely palette or object names. Record a brief selected premise and why the alternatives are weaker in `scene.reason`; this is a design summary, not a reasoning transcript. An unfolding ornament and rising sphere are not defaults for unrelated folders.

Design the supporting space to communicate scale, depth or meaning across the full sequence. An empty stage and decorative clutter are both weak substitutes for that decision. Allocate the limited object budget deliberately. Check whether replacing the source files would leave the same concept; if so, source specificity is probably weak.

Define material contrast through shape, color variation, roughness and lighting together. Wet surfaces, cloth, stone, foliage and metal should not all become glossy ribbed sheets. The current color expression is evaluated at mesh vertices and interpolated: sub-grid patterns do not become fine texture. Actual transparency and physical water remain unavailable. Treat a constrained interpretation honestly.

Review four separate questions in each preview: is the invention specific to these sources, is spatial depth convincing, are materials distinguishable, and does the sequence develop? Reconsider a weak premise before another cosmetic revision. This guidance is not a requirement that every result be realistic or densely populated.

### Per-pixel material detail

Optional surface `color_detail` supplies an original bounded math expression evaluated per pixel in interpolated surface coordinates `u,v`, with `t` in seconds and `pi`. It uses the same allowed arithmetic/functions but cannot reference geometry bindings. The result clamps to -0.35..0.35 and multiplies linear albedo by 1+detail; it does not add displacement, normal mapping, transparency, roughness variation or physical simulation.

Use it for restrained surface color grain or weave, with `color_mix` retaining broad mesh-interpolated color variation. For example `.12*sin(u*80)*sin(v*85)` resolves on a coarse mesh; this simple pattern is an illustration, not a universal material preset. Choose frequencies that remain visible at the intended view; subpixel patterns can alias. Detail does not rescue balloon-like stone geometry or a weak composition.

Limits are 128 characters and 32 compiled expression nodes per detail expression, plus 128 detail nodes across the world, separate from geometry budgets. This bounds added per-pixel work even when tessellation is low; it is not a frame-rate guarantee. Omit the optional field for the prior shader path. `scripts/browser_material_test.cjs` verifies resolved detail on a 4×4 mesh and bounded brightness under extreme inputs using an installed real browser.
# Fine surface relief

Optional surface `bump_detail` evaluates a bounded height expression per pixel.
It uses the same restricted math as `color_detail` (u/v/t/pi, no local bindings,
128 characters and 32 nodes per expression). Both fields **share** the existing
128-node fragment budget across the world. It adds no production dependency.

Height is in world units, clamped to +/-0.1. Its surface gradient perturbs the
lighting normal, limited to magnitude 0.6. Geometric normals still determine
shadow bias. The mesh, silhouette, cast shadow and collision geometry are
unchanged. Constant height has no effect. The absent field preserves the old
shader path. Example starting point: `.002*sin(u*83)*sin(v*71)` for subtle grain.

Scale frequency to surface dimensions and projected size. Check multiple times
and camera angles: short wavelengths can shimmer, UV seams can become visible,
and strong periodic relief reads as carved ribs. This is not displacement,
transparency, reflected objects, fluid simulation, or automatically good material
design. Diagnose those separately instead of adding stronger noise.

## Shared assembly frames and ambient controls

Optional `assemblies` contains up to eight named frames. Each has `translation` and `rotation` x/y/z expressions using t/pi only, a fixed pivot, and positive xyz scale. Parent must appear earlier; depth is limited to four. Assign a surface with `assembly`. The order is surface → instance scale/rotation/offset → child frame → parent frames → final world clamp. Each frame subtracts pivot, scales, rotates X/Y/Z in radians, restores pivot and translates. Share frames across connected surfaces; this avoids duplicated joint motion but does not prevent collisions or fix inaccurate local attachment points. Transform work consumes existing budgets.

Use `rekindra_revise_world` to replace the complete assemblies array and attach surfaces within one validated batch. Unchanged fields and original plan remain intact. Camera-only revision plans support alternate views. Optional surface `assembly` can be removed with null; removing a referenced group without detaching its surfaces is invalid.

`ambient_strength` (0..2, default1) changes diffuse ambient only. `ground_color` (default #342A20) with `ground_strength` (0..1, default0) supplies an approximate lower hemisphere tint. Defaults preserve the old shader behavior. These are art-direction controls, not contact occlusion, sampled scene reflections or physical light bounce. Compare neutral and revised previews; darker is not automatically better.

## Inspection-only cameras

`rekindra_preview` accepts optional `review_camera: {eye:[x,y,z], target:[x,y,z], fov:57}` for a saved world. This uses one stationary pose for all six animation samples. It creates a separately labeled inspection HTML and PNG, leaving the saved plan and normal presentation HTML unchanged. The inspection HTML blocks video export through UI and API; use the normal saved scene for final export. Omit the override to review presentation framing. Use this for side, reverse and close attachment views rather than appending diagnostic travel to the final camera timeline.

## Per-copy orientation

An instance may include `rotation:[rx,ry,rz]`, static radians bounded to +/-2pi per axis. The order is local surface, instance scale, X/Y/Z rotation, instance offset, then its assembly chain. Scale is therefore along the original local axes. Omitted rotation preserves the earlier shader path. Caps, normals and cast shadows use the same transformed geometry. When any copy uses rotation, the fixed transform cost is charged to all copies, including capped boundary vertices, within existing work budgets.

Use varied orientations for repeated leaves, branches or stones when the sources justify them. This does not automatically attach copies to terrain or resolve intersections; inspect their bases and silhouettes from stationary review views.

## Compact bounded assembly easing

Expanded polynomials can exceed the assembly's32-node expression limit before geometry is even considered. For a smooth held opening from second3 to8, `0.5-0.5*cos(pi*clamp((t-3)/5,0,1))` compiles to15nodes and stays0before the interval and1after it, with zero endpoint velocity. Multiply by the desired displacement or angle within the same budget. This is a timing example, not a scene template. It was checked through both expression and assembly compilers; fixed assembly work and all attached copies still count toward the world's total.

## Deliberate faceted surfaces

Optional surface `shading:"flat"` uses the actual rendered triangle normal. Omitted or `"smooth"` keeps the previous derivative-of-surface normal behavior; caps retain their flat normals in either mode. Flat mode is useful for cut planes, fractured stone and intentionally low-poly solids. It changes lighting only, not vertices, silhouette or shadow geometry. Planar triangles have constant geometric normals; bump detail can still perturb them. Avoid strong bump when the purpose is a clean plane.

Choose geometry and segment layout deliberately: flat shading exposes every triangle and cannot create fractures or repair intersections. Inspect silhouettes and attachment points before material polish. Use `rekindra_revise_world` to set shading on an existing surface, or null to remove the optional field and return to default.

## Shared attachment coordinates

For a branch or leaf, define its base at its local origin. Evaluate the parent stem centerline at the chosen attachment parameter, apply the parent's instance scale, X/Y/Z rotation and offset, then use that position for the child's instance offset. Both parts should share the assembly that moves their joint. This makes the connection persist under common assembly motion without independently approximated trajectories. A leaf's v=0 edge can collapse to that base; a tube's root ring can overlap the parent tube radius.

Check computed coordinates and inspect rendered joins. In the cleft construction trial,20declared branch/leaf connections agreed within0.000001local units; this did not establish rock contact, hidden intersections or convincing growth. If the parent itself deforms over time, a static offset will not follow its deformation: share the same time-dependent attachment formula or use a rigid shared frame.

## Numeric cross-section lofts

Optional surface `loft` defines2–8 ordered sections. Each is `{height:0,points:[[-1,-1],[1,-1],[1,1],[-1,1]]}`: points are local x,z, height is local y. Heights increase by at least0.0001; all coordinates stay within+/-80. Every ring has the same3–16point count, must be strictly convex, and must use the same winding. The last point connects to the first automatically; do not repeat the first point. Corresponding indices connect adjacent sections, so choose consistent landmarks around the shape.

The loft supplies `loft_x`, `loft_y`, `loft_z` to ordinary position expressions and local bindings. Start with `position:{x:"loft_x",y:"loft_y",z:"loft_z"}`. Existing bounded equations can then deform or animate it; instances and shared assemblies still apply afterwards. These names cannot be redefined by bindings when a loft is present, and cannot be used in fragment detail. All ordinary required surface fields remain required. Removing loft requires also removing expressions that depend on it in the same revision.

The u segment count must be a multiple of ring point count; v segments must be a multiple of section count minus1. For4points and3sections, `[8,8]` is valid. Mesh minimums and all existing budgets still apply. Section breaks are equally spaced in v, while explicit heights set their actual y positions. Budget a compact segment layout before repeating the shape; loft calculations count toward every copy and cap. Extra subdivisions do not invent shape detail.

Use varied section sizes, centers and corresponding corners to construct deliberate taper and edge transitions, instead of repeating identical polygon faces. `shading:"flat"` reveals the actual triangles; smooth is still available. Planar convex end rings can use existing caps, but arbitrary position deformation can invalidate that assumption. Convex input rings do not guarantee interpolation or later deformation is intersection-free. Always inspect the complete silhouette and joins. This original compiler does not import a modeling engine or execute supplied code.
