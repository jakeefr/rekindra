# Live revise test: rekindra_revise_world (demo beat 5)

Date: 2026-11-07 (Saturday). This was scheduled for Sunday; it ran a day early on Jake's go-ahead
("just whatever you think needs to be done").
Branch `feat/foundation` @ 74d0b80 (tag `checkpoint-recover-wired`). Hermes v0.22.7 (D: install), gateway on.
Model: `openai-codex` / `gpt-6.1-sol`, reasoning medium, `--max-turns 28`, one-shot, resuming session `local-26200ba7…`.

## Request (beat 5)

> The notes say the lamp-room glass fogs at dusk. Soften the beam and bring the two boats in along it.
> Revise the world you just made rather than starting over, keep the recovered notes cited, then preview
> the revision. No text on screen. Do not modify the source files.

## Pass condition

1. The chat exits 0 and calls `rekindra_revise_world` on the existing plan, not `rekindra_create_world`.
2. The new plan is a separate file with `model.origin: caller-revised` and `parent_plan_id` = the original plan.
3. The `text_references` evidence ids are unchanged and still resolve to the recovered notes.
4. Preview and export complete, and the motion probe changes over time.
5. The source hashes are unchanged.

## Result: mechanical PASS, visual WEAK

Attempt 1, exit 0, 151 s. Logs: `<local path>\logs\e2e-revise\`.

- New plan `747e21593f654412b82b97e957c16a6a` has parent `d42b97997b5541ac99841a632e1aa79d` and origin `caller-revised`.
  The original plan file is untouched.
- Changed fields: `assemblies`, beam (caps, color, color_high, color_mix, emission, position), `warm_lamp`,
  `returning_boats` instances, `reason`, `text_references`.
- Evidence ids are unchanged: `keeper_notes.txt` chars 0–235 and `stairs.md` chars 0–142, both `content: recovered`,
  `untrusted: true`, `clipped: false`. Only the keeper interpretation text changed ("stylized diffusion, not simulated
  glass or volumetric fog").
- Export: browser exit 0, decode exit 0, motion probe `motion` and `independent` both changed.
- `sha256sum -c` reports all three source files OK. The agent's own in-chat hash check was blocked by Hermes one-shot
  safety (no terminal); the check above was run outside the chat.

`scripts/export_acceptance_case.py` only picks up `rekindra_create_world` results, so it reported "no world authored"
for this revise-only run. The browser and decode scripts were run directly on `artifacts/747e….html` instead.

## Frame review (honest)

- **Beam:** worse. It became a thick tan spindle angled down to the water at a fixed bearing. It reads as a solid
  wedge, and the agent's own vision check called it "still visibly solid". It also **stopped sweeping**: the agent
  sent the `sweep` assembly with rotation `y: 0` (original `-0.7+t*0.35`). The engine applied what it was given.
- **Boats:** they do move in (homecoming translation grew from −3/−1.4 to −4.5/−2.25 over 18 s) and sit roughly along
  the beam line, but they are still flat discs.
- **Lamp:** slightly larger and warmer glow.
- **Unchanged weak spots:** gray-mauve sea, fog washout, hard horizon line.

## Consequences

- Beat 5 works as a pipeline step (revise → new plan with lineage → preview → export).
- The beam fix unit should go straight to the approved fallback (lamp-room glow + sweeping shaft), and authoring
  guidance must say a revise keeps an existing sweep rotation unless the request asks to stop it.
- The export script needs to select revised/previewed plans.
