# Contrasting-source creative acceptance — November 5, 2026

This is a development study, not a product-completion claim. Production rendering uses Rekindra's own expression compiler, WebGL renderer and WebM exporter. No external creative engine was added.

## Method

Run `scripts/make_variety_sources.py` to generate two original 640x480 PNG design references under `.local/variety-study`: leafy stems and rust seed shapes on cream; four colorful horizontal-bar towers on a dark grid. These are deliberately synthetic, not user memories or recovered damaged files. This script is renderer-side acceptance tooling; it does not overlap the delegated intake package.

Two independent native Hermes sessions used provider `openai-codex`, model `gpt-6.1-sol`, low reasoning, max seven turns. Each was authorized to view its reference through native vision, inspect the folder and author a 12-second world with `rekindra_create_world`. Neither could read earlier benchmarks or the other session. The request asked for source-grounded invention, independent geometry movement, readable depth, no text and no source pixels drawn. The agent chose all geometry formulas and scene parameters.

We rendered each returned HTML with `scripts/browser_scene_test.cjs`, `REKINDRA_WORLD_STUDY=1`, and a distinct `REKINDRA_BROWSER_OUTPUT`. Inspected six decoded frames from each exported video. This is sampled visual inspection plus native playback/decode tests, not continuous human-like viewing.

## First drafts

| Source | Project / plan | Export | Assessment |
| --- | --- | --- | --- |
| Botanical | `9909255e0dbc4384893cd616f2af47f8` / `2481acbe64e6441ea4c14501ec1b7118` | 1,672,434 bytes | Source cues recognized, but small literal stems, muted greens and weak temporal change. Creative rejection. |
| Geometric | `881164d5a45b49c586deab5da0b50718` / `996b272de9b54219860a17429fe6e25c` | 3,298,350 bytes | Distinct from botanical output, but small rounded stacks and repetitive motion. Creative rejection. |

Both exports: 12 seconds, 1280x720; independent motion with fixed camera, zero source HTML image drawing, deterministic seek, ASCII, native decode/duration/seek, cancellation, integrity rejection and no external network requests all passed. Passing those checks did not override creative rejection.

## Render-based revisions

Each revision request supplied its actual decoded filmstrip, described observed defects, authorized reading its own prior plan, and requested a substantial staged transformation while retaining source cues. We provided art direction, not replacement formulas. This review loop is currently external development tooling, not an autonomous plugin capability.

Geometric revision `67b64d9e03ec44e69826a2ca33ed6fc6` in the same project produced compact pleats that extend and then bend/fan into an architectural arrangement. Export `.local/geometric-revised-browser/verified-scene.webm`: 3,991,457 bytes, 12 seconds, 1280x720. All browser checks passed again. Decoded frames show clearer staging, stronger scale and preserved four-color identity. Materials and lighting remain basic; this is an improvement, not final showcase quality.

The first botanical revision session stopped making visible progress after its vision result. After more than five minutes without a returned artifact, its CLI was interrupted and a fresh session was started with explicit project/source IDs and authorized prior-plan context. Logs do not establish the root cause. The configured 120-second run budget did not produce a timely result in this case; do not present it as a guaranteed wall-clock timeout.

The fresh botanical session produced revision `37914e2eb67e44fba81e9f9fcab502b6` in the original project. Export `.local/botanical-revised-browser/verified-scene.webm`: 2,970,806 bytes, 12 seconds, 1280x720; all browser checks passed. Decoded frames show a closed layered bud opening outward into a radial leaf sculpture, exposing three rust-colored seed forms. This is a substantial silhouette change and a distinct concept from the geometric installation. Green lighting remains somewhat dull and intersecting leaves need refinement; it is not final showcase quality.

The retry initially failed because `mood` exceeded 100 characters, then the agent corrected its request successfully. Investigation found the public world schema omitted runtime text limits. Added `maxLength` for title/mood/reason/observed/created and a boundary regression that failed before the fix. All 47 Python and 6 Node tests pass. This contract fix was made after the live sessions; their successful correction is not evidence of live testing the updated schema yet.

## Product implications

- Recognition and visual variety work on these two references, but first-pass creative quality is inconsistent.
- Model instructions now call for concrete source cues, an invented concept and readable temporal states, and distinguish artifact creation from visual inspection.
- Authoring guidance explains bounded time progress for staged geometry, camera-independent movement, color review after shading and explicit creative acceptance.
- Further work: integrate a bounded render/review workflow through supported host capabilities, test varied real multi-image inputs, improve visual quality, and verify live Mac/Linux host/browser behavior. Two synthetic references cannot establish broad generalization.

Raw session events, prompts, source images and exported media remain local under `.local`; project plans/artifacts remain under `<local path>/home/plugin-data/rekindra/projects`. No private media or credentials are committed.
