# Live end-to-end: recover → text_references → preview → export

Date: 2026-11-07. Branch `feat/recover-text-zip`. Hermes v0.22.7 (local install), gateway on.
Model: `openai-codex` / `gpt-6.1-sol`, reasoning medium, `--max-turns 28`, one-shot.

## Pass condition

1. The chat reaches the model with the gateway on, and the agent recovers the TGA and both loose notes.
2. The saved plan's `scene.text_references` evidence ids resolve to the project's dossier, with source paths `keeper_notes.txt` / `stairs.md` and text that matches the source files byte for byte.
3. Interpretations are stored apart from recovered text (`content: interpretation`, `recovered: false`). Recovered quotes carry `content: recovered`, `untrusted: true`.
4. Preview and export complete, and the motion probe changes over time.
5. The source hashes are unchanged.

## Sample

`<local path>\samples\e2e-lighthouse\` contains `harbor_dusk.tga` (160x120, 24-bit), `keeper_notes.txt` and `stairs.md`.
The notes are loose files, not in a ZIP. Hashes are in `<local path>\samples\e2e-lighthouse.sha256`.

## Attempts

| # | Result | Cause |
|---|--------|-------|
| 1 | `Gateway starting: deadline` | The gateway was started in a background shell with output redirected, and hung after plugin discovery. It was restarted minimized with `--quiet`. |
| 2 | `Gateway connection failed; no local fallback` | The chat ran during the gateway's 105 s turn-machinery warmup. |
| 3 | Same as 2 | `session.create` took about 40 s against the client's 30 s RPC timeout. A stray recursive `grep -rn` over hermes-agent and its venv (left from a stopped task) was saturating the development drive. |
| 4 | **Pass** | The grep had exited. The chat completed in 251 s with exit 0. |

Attempts 1–3 never reached the model. They were infrastructure failures, not plugin failures.
Logs: `<local path>\logs\e2e-text-refs\`. Session: `local-26200ba7…`.

## Attempt 4 result

Tool sequence: `rekindra_inspect` → `rekindra_recover` ×3 (TGA→PNG, text, markdown; intake ok, dossier ok) → `read_file evidence.json` → `vision_analyze` → `rekindra_create_world` (with `text_references`) → `rekindra_preview` → `vision_analyze`.

Project `b54ad42d55864d9baa9e1ed7ca47b8a6`, plan `d42b97997b5541ac99841a632e1aa79d`:

- `ev-f3282e0f5e3f3764bac3a07b` resolves to `keeper_notes.txt`, chars 0–235, and its text equals the file.
- `ev-b5300ef86366e3e67f2ebf52` resolves to `stairs.md`, chars 0–142, and its text equals the file.
- Both interpretations are stored under `text_provenance.interpretations` with `origin: agent`, `recovered: false`. The agent flagged its own inventions in them, for example moving the brass rail outside and not claiming the 112 steps.

Export (`scripts/export_acceptance_case.py`): browser exit 0, decode exit 0. The motion probe shows both `motion` and `independent` changed.
Source check: `sha256sum -c` reports all three files OK.

## Frame review (honest)

Matches the source:
- dusk pink-orange sky
- red/white banded tower with lit lantern and gallery
- rock base
- a dark harbor-facing window
- a rotating amber beam

No on-screen text in the scene. The labels on the review sheets come from the review tool.

Weak points:
- The sea is a hazy gray-mauve, not the deep blue of the source.
- Fog flattens the whole frame.
- The water plane's far edge shows as a slanted hard line against the sky.
- The beam is a thin stick, not a light cone.
- The two boats read as flat brown discs.

This is a functional pass for the pipeline, not a best-scene quality acceptance.
