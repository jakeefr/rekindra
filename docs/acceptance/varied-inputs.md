# Varied-input reliability set

First pass 2026-11-08; latest results are under Rerun (2026-11-09) below.

## First pass (2026-11-08)

Seven small synthetic folders under `<local path>\samples\varied\` (generated for this test; no personal files).
Each ran as one live Hermes create (gateway, gpt-6.1-sol, same prompt shape as the demo), then
`scripts/export_acceptance_case.py`. Source SHA-256 manifests (`<folder>.sha256`, outside the repo) were re-checked
after every run. Not polished visually; this logs what each input produces.

Pass = no crash, every file accounted for (recovered, rejected with a reason, or unsupported), source hashes
unchanged, and a world plus export where the evidence supports one.

| Folder | Inputs | Per-file outcome | Crash? | Hashes | World / export | Result |
|---|---|---|---|---|---|---|
| v1-jpeg-cabin | photo-style JPEG, note | note recovered; JPEG unsupported for recovery, used as visual reference | no | unchanged | world built; export ok | PASS |
| v2-notes-only | .txt letter, .md journal | both recovered | no | unchanged | create_world refused: "Creative scenes currently accept PNG, JPEG, or recovered TGA images"; agent reported it, no world | PASS (limitation) |
| v3-zip-notes | ZIP of 3 notes | ZIP recovered as inventory (member names only, contents not read) | no | unchanged | no world; agent declined to build from filenames | PASS (limitation) |
| v4-pdf | PDF, readme | readme recovered; PDF `unsupported_extension`, contents not read | no | unchanged | no world (only a pointer to the PDF) | PASS |
| v5-broken-mix | PNG, notes.md, bad JSON, empty file, truncated TGA, 101 MiB .bin | notes recovered; JSON partial (not repaired); empty recovered as empty; TGA rejected "Truncated TGA pixel data; missing pixels are not invented"; .bin skipped at inspect "input byte limit"; PNG unsupported, used as reference | no | unchanged | world built; export ok | PASS |
| v6-nothing-usable | Thumbs.db, random blob, empty .md, 72-byte fake PNG | Thumbs.db and blob: format unknown, unsupported; empty .md recovered as empty; fake PNG unsupported | no | unchanged | no world (nothing recovered); agent said so | PASS |
| v7-png-garden | illustration PNG, note | note recovered; PNG unsupported, used as reference | no | unchanged | world built; both agent previews hit "Scene preview exceeded 45 seconds"; export browser check timed out twice, passed on the third try with the machine idle (`export3`) | PASS on retry (flaky, see below) |

## Notes

- **Gateway flake, first pass.** v4 got "Gateway disconnected; turn outcome is unknown" and v5/v6 "Gateway
  connection failed; no local fallback" while an earlier session was still running server-side. Transport, not
  input handling. Logs kept in each folder's `failed1/`; the rerun above is clean.
- **v7 timeout is not reproducible standalone.** Same artifact in a fresh headless Chrome: frame render 1-5 ms,
  `exportVideo` 3.2 s, decode and 7 seeks 0.25 s; the full export check passed once nothing else was running.
  v5 used the same PNG and its preview and export passed. The failed attempts overlapped other live runs, so
  likely browser/GPU contention; not diagnosed further. The agent-side preview timeouts are still a real risk
  for the recording: run one take at a time.
- **Limitations worth a decision:** notes-only folders cannot produce a world (an image is required); ZIP member
  text is not recovered; JPEG/PNG are references, not recovered assets; PDF is unsupported. Each is reported
  honestly by the agent, none crashes.
- **Minor:** inspect labels the synthetic PDF `format: text` (it is ASCII), while recover reports
  `unsupported_extension`. Consistent outcome, inconsistent label.
- Logs: `<local path>\logs\varied-<folder>\` (events.jsonl, stderr.txt, export/).

## Rerun (2026-11-09)

Same seven folders and manifests, one live Hermes create at a time, plugin at `8ec6b86`. The prompt gained one
sentence asking for an export once the agent was happy with the world. Not judged visually; this logs behavior.
"Gate" is the `rekindra_export` outcome: clear, or acknowledged with a reason stored in provenance.

| Folder | Per-file outcome | Crash? | Hashes | World / export | Result |
|---|---|---|---|---|---|
| v1-jpeg-cabin | JPEG recovered as 1024x683 PNG; note recovered | no | unchanged | world built; revised once on its own (snow too dark); gate clear | PASS |
| v2-notes-only | both notes recovered | no | unchanged | world built with no image; first create rejected (color pattern aliasing), retry ok; gate clear | PASS |
| v3-zip-notes | ZIP recovered; all 3 member texts read | no | unchanged | world built; first create rejected (repeated text reference), retry ok; gate clear | PASS |
| v4-pdf | PDF text recovered (page 1); readme recovered | no | unchanged | world built; revised once on its own (roof shape); gate clear | PASS |
| v5-broken-mix | PNG recovered 800x600; notes recovered; JSON partial, not repaired; empty recovered as empty; TGA rejected "Truncated TGA pixel data; missing pixels are not invented"; .bin rejected at intake (input byte limit) | no | unchanged | world built; gate acknowledged (one palette warning, reason stored) | PASS |
| v6-nothing-usable | Thumbs.db and blob (both random bytes): no known file signature; empty .md recovered as empty; fake PNG rejected "damaged" | no | unchanged | no world (nothing usable); agent said so | PASS |
| v7-png-garden | PNG recovered 800x600; note recovered | no | unchanged | world built; first create rejected (material expression limit), retry ok; revised once on its own (flower and stem gap); gate acknowledged (one palette warning, reason stored) | PASS |

Every export passed the browser check and decoded on the first try. No preview timed out, and v7 did not repeat
its first-pass timeouts with one run at a time.

Rerun notes:

- The first-pass limitations on notes-only worlds, ZIP text, JPEG/PNG recovery and PDF text are closed.
- Both acknowledged palette warnings (v5, v7) were the same case: a 3D view puts green ground where the flat source
  has sky. The band comparison can flag intended changes.
- v3: the agent also tried `terminal` and `execute_code` once each; Hermes blocked both.
- v4: the evidence dossier counted 3 sources (text 2, unknown 1) from 2 files. Not investigated.
- Logs: `<local path>\logs\varied2-<folder>\`.

## Integration build `4524c04` (2026-11-09): live rerun skipped

The live rerun of the seven folders on `4524c04` (tag `freeze-2-2026-11-09`) was not completed. All seven attempts
ended before any tool call: v1 on a gateway start timeout, v2 to v7 on the gpt-6.1-sol provider's quota (HTTP 429).
Source hashes were unchanged. Jake accepted a model-free comparison in its place, so no live agent run backs this
build for these folders.

What was compared: `rekindra_inspect` and `rekindra_recover` on every asset in all seven folders, called through the
real handlers with no model, once on the freeze build `64a6507` and once on `4524c04`.

- Same ok or error outcome for every asset in every folder (v5: one `invalid_input`; v6: two `invalid_input` and one
  `damaged_image`; everything else ok).
- Same evidence items returned. v3 returns 6 of 7 on both builds; `4524c04` now says so with
  `evidence_truncated: "truncated, 1 more; the full dossier is at dossier_path"`.
- Reply differences are the intended ones: a `notice` line on recover replies, and in `text_members` the fields
  `skipped_counts` and `skipped_uncounted` replace `member_bytes` and `skipped_omitted`. Text replies grew by about
  240 characters; the largest seen was 3,193.

Not covered: what a live agent authors from these replies, preview, and export on this build for these folders. The
lighthouse flow was run live on `4524c04` with glm-5.3 and exported.
