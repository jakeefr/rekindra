# Rekindra

An original Hermes Agent plugin for recovering, reconstructing, and reimagining forgotten files.

Status: working plugin, version 0.2.0. It recovers images and text from a folder you name and builds source-backed animated worlds that can be saved as video. Tested end to end on Windows only. See Limitations and Verification below.

## Product boundary

The core recovery logic, project model, creative scene representation, renderer, and export pipeline are our own implementation. HyperFrames, Remotion, Blender, GSAP, Three.js, REA, FFmpeg, and similar products are reference material, not runtime engines.

Python standard-library facilities, Hermes public APIs, and browser platform APIs are foundations. No model credentials are stored by this project.

## Development

All project code, dependencies, fixtures, temporary files, and development caches belong on D: on the current Windows development machine. Never commit private source collections or credentials.

The implementation plan and evidence log live in `docs/`.

Run the core tests:

```text
python -m unittest discover -s tests -v
```

Two runtime dependencies, ranged in `plugin.yaml`: `pypdf>=6.21.4,<7` (BSD-3-Clause) reads PDF text and `Pillow>=13.0.0,<14` (MIT-CMU) decodes images, each in a separate, killable process. They are decoders, not creative engines. The ranges include the versions Hermes itself installs, because a plugin cannot move a Hermes pin and a conflicting one gets the plugin disabled; `tests/test_dependency_ranges.py` checks them against the recorded Hermes pins on every run, and against the versions actually installed when `HERMES_HOME` points at a Hermes install. Hermes asks before installing them (`hermes plugins install`, then restart). `hermes pm repair` does not add them. Without pypdf, PDFs are reported as unsupported; without Pillow, images other than the original TGA decoder's are. Everything else works, and those reader tests skip with a reason.

`scripts/Start-Rekindra.ps1` is a Windows development helper that launches Hermes with all development storage and caches directed to `<local path>`. To configure a model, run `scripts/Start-Rekindra.ps1 setup` and complete the provider's own sign-in. Never put a credential in this repository.

## Working now

- `rekindra_inspect`: bounded folder inventory, source snapshots, hashes and explicit skips. Files no recovery route accepts are named from their leading bytes ("identified as RAR archive, not supported yet") without being opened or run.
- `rekindra_recover`: original TGA type 2/10 true-color decoding to PNG, and JPEG, PNG, BMP, GIF, TIFF, PCX, ICO, WebP, PPM, QOI, SGI and DDS through Pillow to normalized PNG copies with dimensions, format and EXIF date. A damaged JPEG, PNG, BMP, GIF, PCX, PPM or TIFF keeps only the pixels that really decoded and is marked partial; other damaged images are refused. Text, Markdown, JSON and CSV become quoted evidence with citable IDs. ZIP archives have their text members read in memory under size, ratio and time caps; nothing is extracted. PDFs have their text read page by page in a separate process, with no OCR. All of it carries provenance.
- `rekindra_status`: saved inventory and recovered artifacts.
- `rekindra_reconstruct`: the agent proposes an order for the recovered material (sections, titles, an optional timeline, short bridging notes) and the plugin checks every piece against real recovered evidence before writing one self-contained offline HTML page. Recovered images and quoted passages appear in place, labelled recovered. Titles, notes and timeline labels are the agent's and are labelled inferred. Files that were skipped, rejected, unreadable or left out are listed as gaps. A partially decoded image shows only the pixels that decoded, inside a frame of its original size with the rest marked missing; nothing is filled in. A timeline date must be backed by a recovered capture date or by a year that appears in the cited passage. Untrusted text is escaped, the page carries no script and loads nothing from the network, and a provenance JSON file is written beside it. `rekindra_create_world` can cite a reconstruction by id. Out of scope: Rekindra does not repair, complete or run games or software projects; nothing in a folder is compiled, executed or rebuilt.
- `rekindra_compose`: validate an agent-authored scene and build a portable, offline HTML player with a high-detail ASCII mode (full color or black-and-white) and silent WebM export.
- `rekindra_plan`: optional separate host-owned structured model call to infer mood and save a scene plan.
- `rekindra_build`: rebuild a saved plan after verifying source integrity.
- `rekindra_preview`: render a saved scene into a timed PNG contact sheet in an isolated local browser so the active agent can inspect and revise it. World previews also report palette drift against the source and any backdrop edge in frame. Requires installed Chrome/Chromium/Edge; no production Playwright dependency.
- `rekindra_export`: clear a previewed world for video. Refuses unresolved palette drift or a backdrop edge until they are revised or acknowledged with a reason, allows export with the warnings recorded after three flagged revise and preview cycles, and writes the only world HTML that can save WebM.
- `rekindra_create_world`: create generated geometry, animated surfaces, atmosphere, materials and a moving perspective camera from the agent's interpretation of recovered images, recovered text, or both. A folder of notes or PDFs with no image can still make a world, citing the evidence it used through `text_references`. No source-image textures or text are drawn in this mode.
- `rekindra_revise_world`: apply bounded field edits to a new immutable world plan, then review its rendered output.

Recommended flow: inspect the selected folder, recover its images and text, let the active Hermes agent view selected images with consent and read the recovered evidence, then have it call `rekindra_compose` or `rekindra_create_world`. A world then goes through `rekindra_preview`, any revisions, and `rekindra_export`. Creative output is labelled generated. `rekindra_plan` is an optional route; on the tested native Hermes build, its Python auxiliary model client could not access the working Codex chat sign-in. Do not copy credentials or add a second provider to work around this. Use the active agent route.

For a new environment rather than picture effects, prefer `rekindra_create_world` after source inspection. The agent records what it observed and what it invented, then authors parametric geometry in scene v2. The original WebGL2 renderer calculates moving geometry and shading at the requested time. The source image remains in the provenance gallery; it is not a texture on a rectangle. Camera and object motion are independent. This is generated interpretation, not recovery of a photograph's true 3D scene. See `docs/world-authoring.md`.

Scenes currently support 1-6 image sources in any format above, 4-30 seconds at 1280x720, images, source fragments, optional requested text, and deterministic particles. On-screen text is off by default: new creation calls require allow_text=true only when the user asks for it. Explicit per-layer transform tracks support 2-16 complete states; fragments can separate, turn through generated depth, and resolve. These are creative transformations, not recovered 3D geometry. PNG/JPEG headers are bounded before upload; baseline/progressive 8-bit JPEG only. Image bytes are capped at 2 MB each / 8 MB total. Saved HTML embeds its assets and checks their hashes before playback. Hashes detect corruption; they are not signatures proving authenticity.

Open the saved HTML in a current Chromium browser, play or scrub it, optionally select **ASCII** (leave **ASCII color** checked for full color, uncheck it for black-and-white), and choose **Save video**; the saved video uses the view and mode selected. Export uses native WebCodecs VP8 packets and our original WebM writer. No audio or MP4 yet. A browser without VP8 WebCodecs encoding can still play the scene but cannot export video.

Supported TGA subset: 24/32-bit, no color map or interleaving; all four image origins; 8-bit declared alpha or opaque output. Known footer/metadata boundaries are excluded from pixel recovery. Unknown trailing metadata stays in the original snapshot and is reported as uninterpreted. This is not universal damaged-image repair. A damaged JPEG, PNG, BMP, GIF, PCX, PPM or TIFF keeps only the pixels its decoder really wrote, proved by decoding it twice on opposite backgrounds; it is marked partial, and undecoded areas are cropped or left transparent. Other damaged formats, and truncated progressive JPEGs with no complete pixels, are refused. Multi-frame files recover the first frame and say so.

Limits: 500 files, 100 MB per file, 500 MB total snapshots, 2,000 visited directory entries, depth 32, and 20 million decoded pixels. Limits, excluded credential/development paths, unreadable inputs, and links appear in the skipped report. Do not supply a store and source that overlap. One Hermes process may write a given store in this milestone; this is not a hostile multi-user filesystem sandbox.

## Limitations

Known limits. Input limits are reported by the agent; none crashes.

- PDF text is read page by page, up to 32 pages. There is no OCR: a scanned or image-only PDF is reported as having no extractable text, and an encrypted one as encrypted.
- A file Rekindra cannot read is named from its file signature ("identified as X, not supported yet") when the signature is known, and otherwise reported as having no known file signature. Its contents are not used.
- Worlds built only from notes have no tamper check yet. The player's integrity check hashes embedded images, so a world with no image has nothing for it to verify.
- A world that selects images is refused only when `references` is empty. If some selected images have a reference and others do not, the world still builds; the unreferenced image ships with no observed or created record and still counts toward palette drift.
- Palette drift compares the rendered frame with the source in horizontal bands. A 3D view of flat art can flag a band that changed on purpose, such as ground where the source had sky. The agent must give a reason per warning to export past a flag, and the reason is stored in provenance. After three revise and preview cycles that still flag, export is allowed without reasons and the warnings are recorded as unresolved.

## What this plugin does on your machine

**Network.** Rekindra makes no network calls of its own and has no telemetry. Tool results, including recovered text and file names, go to your active Hermes model like any other tool result, so they reach whichever provider you use. `rekindra_plan` sends selected image bytes to that model only when called with `send_images=true`. If the agent opens a recovered image or preview with Hermes' own vision tools, that image goes to the model too.

**Files it reads.** Only the folder you name, read-only, working from snapshots. In that folder it skips files and directories named `.git`, `.ssh`, `.aws`, `.azure`, `.gnupg`, `.venv`, `node_modules`, `__pycache__`, `.env` and `.env.*`. That filter applies to names on disk only: text files inside a ZIP are not filtered by name, so do not point Rekindra at an archive that holds secrets. Your source files are never modified.

**Files it writes.** Only under `$HERMES_HOME/plugin-data/rekindra`.

**Child processes, never through a shell.**
- An isolated Python reader (`-I -S -B`) decodes images and PDFs. It gets only `SYSTEMROOT` and `PATH`, runs with a time limit, and is killed if it overruns.
- Rendering a preview starts a headless copy of your installed Chrome, Edge or Chromium, or the browser named by the optional `REKINDRA_BROWSER` variable. It uses a temporary profile inside the project and background networking is turned off. It runs one at a time with a 45 second limit. It inherits Hermes' environment variables, with temp and cache paths redirected, and loads only a local generated page.
- On Windows, `taskkill` ends a preview browser that overruns.

**Background processes.** None remain once a tool call returns.

**Credentials.** Rekindra stores none and declares no required environment variables. Model access is through Hermes.

**Dependencies.** `pypdf>=6.21.4,<7` and `Pillow>=13.0.0,<14`. Hermes asks before installing them.

**Untrusted content.** Recovered text is labelled as untrusted quoted data for the agent, which is told not to follow instructions inside it. That is guidance to the model, not a guarantee.

## Verification

Latest local core verification: 736 Python tests pass, and 22 Node tests pass. The current plugin declares eleven tools including reconstruction, native preview, immutable revision and gated export; see docs/progress.md and docs/acceptance/ for live verification and remaining gaps. Hermes research/development pin: `7ab170ea6d36fb6ac7a4e7c6607293759df38480`, Python 3.14.9. The registry smoke harnesses that drive an installed Hermes directly use private Hermes internals, so they are kept outside this repository and do not ship with the plugin.

Tested models: end-to-end runs (inspect, recover, create world, preview, revise, export) were verified with gpt-6.1-sol and glm-5.3 (z.ai, high reasoning). Model choice affects visual quality: both models completed the flow, but the rendered worlds differed in how closely they matched the source. The export gate records acknowledged drift, so a world exported past a palette warning carries that warning in its provenance, along with the agent's reason when one was given. After three flagged revise and preview cycles a reason is not required.

Real Windows Chrome acceptance now verifies original 1280x720 WebM output: native decoding, finite duration, seeking and playback, ASCII frame differences in color and black-and-white (`scripts/export_ascii.cjs`, add `--mono` for black-and-white), cancellation, no external network requests, and rejection of corrupted embedded image hashes. Playwright is development-only. Reproduce with `scripts/make_scene_fixture.py`, then `scripts/browser_scene_test.cjs` (requires a development Playwright installation and Chrome).

The CI matrix covers Windows, Linux and macOS on Python 3.11 and 3.14. An earlier build passed all six jobs; the current build has been verified locally on Windows only. A green core test is not a real Hermes desktop/browser acceptance pass. Mac/Linux host and browser integration remain unverified.

Future work: general render checks beyond palette drift and backdrop edges, covering object readability, washout, aliasing, intersections, motion and horizon. Also stronger creative variety, interactive story/game reconstruction, background jobs and full cross-platform acceptance. Hermes itself may install its own standard tools, including FFmpeg; Rekindra does not import or invoke them.


