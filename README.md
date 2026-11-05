# Rekindra

An original Hermes Agent plugin for recovering, reconstructing, and reimagining forgotten files.

Status: working recovery foundation. This is not yet the complete creative product or a released plugin.

## Product boundary

The core recovery logic, project model, creative scene representation, renderer, and export pipeline are our own implementation. HyperFrames, Remotion, Blender, GSAP, Three.js, REA, FFmpeg, and similar products are reference material, not runtime engines.

Python standard-library facilities, Hermes public APIs, and browser platform APIs are foundations. No model credentials are stored by this project.

## Development

All project code, dependencies, fixtures, temporary files, and development caches belong on D: on the current Windows development machine. Never commit private source collections or credentials.

Five-day target: November 5-9, 2026. The implementation plan and evidence log live in `docs/`.

Run the dependency-free core tests:

```text
python -m unittest discover -s tests -v
```

On Jake's Windows development machine, use `scripts/Start-Rekindra.ps1` to launch Hermes with all development storage and caches directed to `<local path>`. To configure a model, run `scripts/Start-Rekindra.ps1 setup` and complete the provider's own sign-in. Never put a credential in this repository.

## Working now

- `rekindra_inspect`: bounded folder inventory, source snapshots, hashes and explicit skips.
- `rekindra_recover`: original TGA type 2/10 true-color decoding to PNG, with provenance.
- `rekindra_status`: saved inventory and recovered artifacts.

Supported TGA subset: 24/32-bit, no color map or interleaving; all four image origins; 8-bit declared alpha or opaque output. Known footer/metadata boundaries are excluded from pixel recovery. Unknown trailing metadata stays in the original snapshot and is reported as uninterpreted. This is not universal damaged-image repair.

Limits: 500 files, 100 MB per file, 500 MB total snapshots, 2,000 visited directory entries, depth 32, and 20 million decoded pixels. Limits, excluded credential/development paths, unreadable inputs, and links appear in the skipped report. Do not supply a store and source that overlap. One Hermes process may write a given store in this milestone; this is not a hostile multi-user filesystem sandbox.

## Verification

Local Windows: 25 unit/integration tests passed; real Hermes Plugin Doctor and catalog validation passed; actual Hermes registry dispatch completed inspect/recover/status with unchanged originals. Hermes research/development pin: `7ab170ea6d36fb6ac7a4e7c6607293759df38480`, Python 3.14.9. `scripts/smoke.py` reproduces the installed-registry flow with the Hermes interpreter and `HERMES_HOME` set.

The native browser probe encoded 120 frames at 640x360/30 fps in Windows Chrome using VP8, VP9 and H.264. It emits raw encoded chunks, not a playable container. Playwright is used only by the developer's probe runner; it is not a production creative engine.

Cross-platform CI passed all six Windows/Linux/macOS + Python 3.11/3.14 jobs, with 25 tests per job and no symlink-test skips: [foundation CI run](https://github.com/jakeefr/rekindra/actions/runs/41980181028). A green core test is not a real Hermes desktop/browser acceptance pass. Mac/Linux host integration and live model conversation remain unverified.

Next: scene schema and renderer, semantic mood planning, safe reconstruction, correct downloadable video container, job progress/cancellation, and full cross-platform acceptance. Hermes itself may install its own standard tools, including FFmpeg; Rekindra does not import or invoke them.

