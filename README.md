# Rekindra

An original Hermes Agent plugin for recovering, reconstructing, and reimagining forgotten files.

Status: working recovery and original animated-scene milestone. This is not yet the complete creative product or a released plugin.

## Product boundary

The core recovery logic, project model, creative scene representation, renderer, and export pipeline are our own implementation. HyperFrames, Remotion, Blender, GSAP, Three.js, REA, FFmpeg, and similar products are reference material, not runtime engines.

Python standard-library facilities, Hermes public APIs, and browser platform APIs are foundations. No model credentials are stored by this project.

## Development

All project code, dependencies, fixtures, temporary files, and development caches belong on D: on the current Windows development machine. Never commit private source collections or credentials.

Five-day target: November 5-9, 2026. The implementation plan and evidence log live in `docs/`.

Run the core tests:

```text
python -m unittest discover -s tests -v
```

Two runtime dependencies, ranged in `plugin.yaml`: `pypdf>=6.21.4,<7` (BSD-3-Clause) reads PDF text and `Pillow>=13.0.0,<14` (MIT-CMU) decodes images, each in a separate, killable process. They are decoders, not creative engines. The ranges include the versions Hermes itself installs, because a plugin cannot move a Hermes pin and a conflicting one gets the plugin disabled; `tests/test_dependency_ranges.py` fails if they ever stop doing so. Hermes asks before installing them (`hermes plugins install`, then restart). `hermes pm repair` does not add them. Without pypdf, PDFs are reported as unsupported; without Pillow, images other than the original TGA decoder's are. Everything else works, and those reader tests skip with a reason.

On Jake's Windows development machine, use `scripts/Start-Rekindra.ps1` to launch Hermes with all development storage and caches directed to `<local path>`. To configure a model, run `scripts/Start-Rekindra.ps1 setup` and complete the provider's own sign-in. Never put a credential in this repository.

## Working now

- `rekindra_inspect`: bounded folder inventory, source snapshots, hashes and explicit skips.
- `rekindra_recover`: original TGA type 2/10 true-color decoding to PNG, and JPEG, PNG, BMP, GIF, TIFF, PCX, ICO, WebP, PPM, QOI, SGI and DDS through Pillow to normalized PNG copies with dimensions, format and EXIF date, all with provenance.
- `rekindra_status`: saved inventory and recovered artifacts.
- `rekindra_compose`: validate an agent-authored scene and build a portable, offline HTML player with ASCII mode and silent WebM export.
- `rekindra_plan`: optional separate host-owned structured model call to infer mood and save a scene plan.
- `rekindra_build`: rebuild a saved plan after verifying source integrity.
- `rekindra_preview`: render a saved scene into a timed PNG contact sheet in an isolated local browser so the active agent can inspect and revise it. Requires installed Chrome/Chromium/Edge; no production Playwright dependency.
- `rekindra_create_world`: create generated geometry, animated surfaces, atmosphere, materials and a moving perspective camera from source interpretation. No source-image textures or text are drawn in this mode.
- `rekindra_revise_world`: apply bounded field edits to a new immutable world plan, then review its rendered output.

Recommended flow: inspect the selected folder, recover its images, let the active Hermes agent view selected images with consent, then have it call `rekindra_compose`. Creative output is labelled generated. `rekindra_plan` is an optional route; on the tested native Hermes build, its Python auxiliary model client could not access the working Codex chat sign-in. Do not copy credentials or add a second provider to work around this. Use the active agent route.

For a new environment rather than picture effects, prefer `rekindra_create_world` after source inspection. The agent records what it observed and what it invented, then authors parametric geometry in scene v2. The original WebGL2 renderer calculates moving geometry and shading at the requested time. The source image remains in the provenance gallery; it is not a texture on a rectangle. Camera and object motion are independent. This is generated interpretation, not recovery of a photograph's true 3D scene. See `docs/world-authoring.md`.

Scenes currently support 1-6 image sources in any format above, 4-30 seconds at 1280x720, images, source fragments, optional requested text, and deterministic particles. On-screen text is off by default: new creation calls require allow_text=true only when the user asks for it. Explicit per-layer transform tracks support 2-16 complete states; fragments can separate, turn through generated depth, and resolve. These are creative transformations, not recovered 3D geometry. PNG/JPEG headers are bounded before upload; baseline/progressive 8-bit JPEG only. Image bytes are capped at 2 MB each / 8 MB total. Saved HTML embeds its assets and checks their hashes before playback. Hashes detect corruption; they are not signatures proving authenticity.

Open the saved HTML in a current Chromium browser, play or scrub it, optionally select ASCII, and choose **Save video**. Export uses native WebCodecs VP8 packets and our original WebM writer. No audio or MP4 yet. A browser without VP8 WebCodecs encoding can still play the scene but cannot export video.

Supported TGA subset: 24/32-bit, no color map or interleaving; all four image origins; 8-bit declared alpha or opaque output. Known footer/metadata boundaries are excluded from pixel recovery. Unknown trailing metadata stays in the original snapshot and is reported as uninterpreted. This is not universal damaged-image repair. A damaged JPEG, PNG, BMP, GIF, PCX, PPM or TIFF keeps only the pixels its decoder really wrote, proved by decoding it twice on opposite backgrounds; it is marked partial, and undecoded areas are cropped or left transparent. Other damaged formats, and truncated progressive JPEGs with no complete pixels, are refused. Multi-frame files recover the first frame and say so.

Limits: 500 files, 100 MB per file, 500 MB total snapshots, 2,000 visited directory entries, depth 32, and 20 million decoded pixels. Limits, excluded credential/development paths, unreadable inputs, and links appear in the skipped report. Do not supply a store and source that overlap. One Hermes process may write a given store in this milestone; this is not a hostile multi-user filesystem sandbox.

## Limitations

Four input limits to know up front. Each is reported by the agent; none crashes.

- A notes-only folder cannot produce a world. At least one image is required.
- Text inside ZIP archives is not read.
- JPEG and PNG files are visual references only. They are not recovered assets.
- PDF text is read page by page, up to 32 pages. There is no OCR: a scanned or image-only PDF is reported as having no extractable text, and an encrypted one as encrypted.

## Verification

Latest local core verification: 86 Python and 10 Node tests pass. The current plugin declares nine tools including native preview and immutable revision; see docs/progress.md and docs/acceptance/ for live verification and remaining gaps. Hermes research/development pin: `7ab170ea6d36fb6ac7a4e7c6607293759df38480`, Python 3.14.9. `scripts/smoke.py` reproduces the installed recovery-registry flow. `scripts/creative_smoke.py` specifically tests the optional auxiliary-model route; it currently exposes the host Codex-auth limitation above.

Real Windows Chrome acceptance now verifies original 1280x720 WebM output: native decoding, finite duration, seeking and playback, ASCII frame differences, cancellation, no external network requests, and rejection of corrupted embedded image hashes. Playwright is development-only. Reproduce with `scripts/make_scene_fixture.py`, then `scripts/browser_scene_test.cjs` (requires a development Playwright installation and Chrome).

Cross-platform CI passed all six Windows/Linux/macOS + Python 3.11/3.14 jobs, each running 46 Python and 6 Node tests: [scene CI run](https://github.com/jakeefr/rekindra/actions/runs/41989227727). A green core test is not a real Hermes desktop/browser acceptance pass. Mac/Linux host and browser integration remain unverified.

Next: stronger creative variety, interactive story/game reconstruction, background jobs and full cross-platform acceptance. Hermes itself may install its own standard tools, including FFmpeg; Rekindra does not import or invoke them.


