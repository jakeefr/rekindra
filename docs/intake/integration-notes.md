# Integration notes

For the primary developer. `rekindra_intake` is now called by the plugin, though not in the way first proposed. [Current wiring](#current-wiring) describes what runs, checked against `af67b55`. The original proposals are kept at the end, marked as not adopted.

## Calling it

Both functions are pure and take bytes already read by trusted code. Rekindra's existing `ProjectStore.inspect` limits, snapshots and hashes stay responsible for filesystem access.

```python
from rekindra_intake import inspect_archive, inspect_text

def describe(data: bytes, display_path: str, identified_format: str) -> dict:
    # identified_format comes from rekindra_core.identify, not the extension alone.
    inspector = inspect_archive if identified_format == 'zip' else inspect_text
    return inspector(data, display_path)
```

Read at most 8 MiB + 1 byte for archives and 256 KiB + 1 byte for text. The inspectors still report over-budget input correctly from that much, except that `size_bytes` would then be the truncated length. To report the true size, pass the whole file, or override `source.size_bytes` with the snapshot's size and treat `sha256: null` as "not inspected".

There are no imports from `rekindra_core`, Hermes or the runtime, so the package can be imported anywhere.

## Rules to keep at the boundary

1. **Facts are untrusted data.** Excerpts, headings, keys, cells and entry names come from the file. If they reach an agent, present them as quoted source material. A file can contain text addressed to the agent. `facts.untrusted_content` is `true` to make this explicit, but it is only a label; the prompt has to honor it.
2. **Keep recovery and interpretation separate.** Intake output is observation. Record it as such in world authoring, alongside invented forms, and never as recovered history.
3. **Never treat `status: ok` as safe to extract.** It means the inventory finished. Nothing extracts to disk, but `rekindra_core/zip_text.py` does read text members (txt, md, json, csv, log) in memory and passes each to `inspect_text`, so this rule applies to it. Any reader of member contents must refuse flagged entries and any `partial` archive, since entries past 256 are unexamined. What `zip_text` does now:
   - `zip_text` skips every flagged entry. Encrypted, nested and `suspicious_expansion` entries are tolerated in the inventory but are never read.
   - It never reads entries past 256.
   - It reads no member of an archive that intake left `partial`. The inventory is kept and the refusal is reported as `ambiguous_archive` (for `multiple_eocd_candidates`) or `partial_archive_not_read`. At `af67b55` it did read them; the live wiring audit (`docs/acceptance/live-wiring-audit-af67b55.md`, finding 1) showed that text could then come from a directory intake had not inventoried.
   - It reads no member of an `ok` archive either when the last end-record signature in the file is not the record that runs exactly to end of file, or when `zipfile` opens a different directory offset. `zipfile` takes the last signature without checking its comment length, so it could settle on a directory intake ignored. This is reported as `ambiguous_archive` and the result is marked `partial`.
   - It skips, as `unsafe_member`, any member whose CRC, sizes or compression method differ between `zipfile` and the intake entry.
4. **Never reuse an entry name as a path.** Names are returned unmodified so that danger stays visible.
5. **Do not put CSV cells in a spreadsheet export** without neutralizing `formula_like_cell_count` cells. A cell is counted when it starts with `=`, `@`, a tab or a carriage return, or when it starts with `+` or `-` and the whole cell is not a plain number (optional sign, ASCII digits, optional decimal part, optional exponent, as in `-12`, `+3.5` or `-1E+10`). Cells are matched exactly as parsed, with no trimming, so a cell starting with a space is not counted. Apply the same rule when neutralizing, rather than recounting with a different one.
6. **Claimed sizes are not measurements.** `claimed_sizes_verified` is `false` for a reason.
7. **Strings are safe for UTF-8.** Results survive `json.dumps(..., allow_nan=False, ensure_ascii=False).encode('utf-8')`, which `ProjectStore._save` relies on. They may still contain control characters, so escape them for terminals and HTML.

## Current wiring

Checked against `af67b55`. No tool was added for intake. It runs inside the existing `rekindra_recover`.

| Where | What happens |
|---|---|
| `handlers.py` | `evidence_reader` sends text assets to `inspect_text`. ZIP assets go to `inspect_archive`, then to `zip_text.read_archive_text`. PDF assets go to `pdf_text.read_pdf_text`. `evidence_summary` returns the intake `format`, `status` and warning codes, plus a short evidence view. |
| `rekindra_core/zip_text.py` | Reads up to 32 text members of a ZIP in memory, under size, ratio and time caps, and passes each to `inspect_text`. Nothing is written to disk. |
| `rekindra_core/pdf_text.py` | Reads PDF text page by page in a separate process, and passes each page to `inspect_text`. |
| `rekindra_core/projects.py` | Saves the envelope as `artifacts/<asset_id>.intake.json`, with its hash in the project manifest. A `rejected` envelope keeps its row and warnings, but its facts and members are dropped before the dossier is built. |
| `rekindra_core/identify.py` | Sets each asset's format at inspect time. Only `text`, `zip` and `pdf` assets reach intake. Images go to the image decoders, and anything else is refused by `rekindra_recover` before intake runs. |
| `plugin.yaml` | No change for intake. |
| `tests/` | `tests/test_recover_evidence.py`, `tests/test_zip_text.py` and `tests/test_pdf_text.py` cover the wiring through the store and handlers. `tests/test_plugin.py` registers the plugin with a stand-in context. No test here drives a real Hermes install. |

Testing: no workflow change was made. GitHub Actions results are not used as evidence for this repository. The evidence is a local run of `PYTHONDONTWRITEBYTECODE=1 py -3 -m unittest discover -s tests`, which also finds `tests/intake`.

### Original proposals, not adopted

The first version of these notes proposed a separate read-only `rekindra_read_clues(project_id, asset_id)` tool declared in `plugin.yaml`, and envelopes stored keyed by `sha256`. Neither was built. Its advice still holds: give the agent `format`, `status` and warning codes, and never present `message` as if it were source content.

## Compatibility promises

`schema_version` stays `1` unless the envelope changes. Warning codes and the fields documented in `docs/intake/README.md` are stable. Message text may be reworded, so branch on `code`.

## Unsupported cases to expect

`unsupported` is a normal result. Show the user that the file was kept but not read.

- ZIP64, multi-disk, strong encryption and self-extracting archives.
- Tar, gzip, 7z, RAR.
- UTF-32, unmarked UTF-16 and legacy encodings. Unmarked UTF-16 is `rejected`; legacy text gives a `partial` prefix.
- Text-like formats outside the extension list, such as `.html`, `.py`, `.tsv` and `.jsonl`.

If real forgotten folders commonly hit one of these, the first candidates to add are legacy-encoding labelling chosen by the user and ZIP64. Each is a separate decision, because guessing an encoding would present invented text as recovered text.
