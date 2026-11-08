# Varied-input reliability set (2026-11-08)

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
