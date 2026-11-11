# Local shared-assembly and lighting outcome

Private integration complete: revision tool commit0a5f470 and assembly/lighting commitbcfa502 pushed to the private jakeefr/rekindra repository and installed in <local path>/home/plugins/rekindra. GitHub visibility was verified PRIVATE. No marketplace/catalog submission, public fork, release or visibility change. All generated files/caches remained local. Intake-owned paths and deferred audio untouched.

## What changed and passed

Shared animated frames (up to8, depth4) now keep connected surfaces together through pivot rotations, scales, translations and parent chains. Visible geometry, finite-difference normals, cap centers and depth shadows use the same transformed positions. Existing scenes retain their legacy path. All transform work counts toward existing budgets. Review caught and fixed premature clipping before assembly scaling.

Optional diffuse ambient strength and ground hemisphere tint give the agent more lighting control. Explicit defaults produced0changedpixelchannels against legacy controls in the fixed GPU fixture. Ground tint affected lower-facing normals more strongly; zero ambient reduced the sampled value88to21. This is an approximation, not contact occlusion, scene reflections or physical bounce.

63 Python tests and7 Node tests passed. Six-job Windows/macOS/Linux Python CI passed: https://github.com/jakeefr/rekindra/actions/runs/42148271041. Actual browser/GPU coverage was Windows Chrome. GPU feedback matched known hierarchical joint coordinates; animated caps moved with assemblies, and their shadow darkened the expected floor sample212to105. Oversized local geometry scaled into world bounds remained intact. Reproduce fixtures with scripts/build_assembly_fixture.py then scripts/browser_assemblies_test.cjs .local/assembly-loop/gpu-input.json; lighting check is scripts/browser_ambient_test.cjs. These scripts require the existing development Playwright environment, not a production dependency.

Native Hermes smoke session local-3902cf362ccbc01ec6ea4545a000d5830c36361c7c3a4c10531e8694f258690d used revise_world, preview and native vision successfully. Its canal material edit was mostly offscreen; it correctly declined to claim a visible improvement.

## Independent folder trial and internal review

Native session local-e7d7a41136b8878a5b11a5d310618b6f87804db833d46d227703a2b68ddabdb9 completed in826041ms with exit0. C01 contains two sourced forest print photographs plus constructed notes/index, not a recovered personal archive. Agent received no scene geometry, palette, camera or premise recipe. It invented The Forest Mends Its Path, a hinged root bridge whose trunk, fork rails and moss share one frame. It used the new ambient controls itself.

Three candidate submissions total: first rejected for expression complexity; second saved5c04e8815b694862a8a19c372d27c282; third camera-only revision saved and retained0a19dfd8e085487f870c93567a32a61b. Project f2cd55de2c9c4074a04ab044646c1633. Native inspected both six-frame previews. Root independently inspected both previews and24decoded samples. The saved forest-assembly-draft.json replaces source IDs with placeholders; it is an evaluated draft, not a showcase or input template.

The closer framing makes the bridge and joined motion easier to read, but crops canopies. Rectangular terrain, visible seams, sparse umbrella-like crowns, thin fern sheets and muted materials remain. Landing lacks organic integration. No obvious separated moving parts in the sampled frames; no claim of collision-free continuous motion. The result still falls below showcase quality. Controlled botanical lighting comparison c00f98ed30dc4a6381a18920a93945ee modestly improved contrast; it did not repair weak geometry or sparse composition.

## Failed unit — acceptance remains blocked

UNIT: E, strict repeatable frame/export verification.
VERDICT: FAIL; whole-loop check exits1.
REASON: Returning to the same time changed6colorchannels by1level. This reproduces a prior issue on other scenes; assembly tests do not establish its cause. Focused state/code review found no new causal evidence. Stopped after two rounds without a new cause, preserving passed units.
EVIDENCE: .local/assembly-loop/forest-browser.log and forest-browser-exit.txt. No tolerance was relaxed and no passing rerun was substituted.
SCOPE: runtime/world.js investigation only; renderer cause remains unconfirmed. No failed experimental renderer fix was shipped.

Diagnostic-only export succeeded: .local/assembly-loop/forest-diagnostic/diagnostic-scene.webm,6546111bytes,12seconds,1280x720. Four decoded review sheets and an overview cover24samples. This is not the verified export artifact. scripts/check_assembly_loop.py intentionally refuses diagnostic substitution. Raw native events, GPU receipts and comparison frames stay under .local/assembly-loop. Gateway run budget restored from600to120; no authoring sessions remain active.

Next: isolate the strict renderer repeatability defect with a smaller reproducible scene, then improve branch/canopy/ground construction and material separation through the now-usable revision loop. No need to redo passing assembly/schema tests unless their implementation changes. No approval is needed for continued local work; public/store publication remains unauthorized.
