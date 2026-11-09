# Integration notes

For the primary developer. Nothing below has been implemented. `rekindra_intake` has no callers and no outside file was changed.

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
3. **Never treat `status: ok` as safe to extract.** It means the inventory finished. No extraction feature exists. If one is ever added, it needs its own design and must refuse flagged entries and any `partial` archive, since entries past 256 are unexamined.
4. **Never reuse an entry name as a path.** Names are returned unmodified so that danger stays visible.
5. **Do not put CSV cells in a spreadsheet export** without neutralizing `formula_like_cell_count` cells. A cell is counted when it starts with `=`, `@`, a tab or a carriage return, or when it starts with `+` or `-` and the whole cell is not a plain number (optional sign, ASCII digits, optional decimal part, optional exponent, as in `-12`, `+3.5` or `-1E+10`). Cells are matched exactly as parsed, with no trimming, so a cell starting with a space is not counted. Apply the same rule when neutralizing, rather than recounting with a different one.
6. **Claimed sizes are not measurements.** `claimed_sizes_verified` is `false` for a reason.
7. **Strings are safe for UTF-8.** Results survive `json.dumps(..., allow_nan=False, ensure_ascii=False).encode('utf-8')`, which `ProjectStore._save` relies on. They may still contain control characters, so escape them for terminals and HTML.

## Proposed future wiring

These touch files outside this assignment, so they are proposals only.

| Where | Proposal |
|---|---|
| `handlers.py`, `schemas.py` | A read-only tool, for example `rekindra_read_clues(project_id, asset_id)`, returning the envelope for one snapshotted asset. Asking per asset keeps responses small. |
| `rekindra_core/projects.py` | Store the envelope beside the asset, keyed by `sha256`, so repeat calls need no re-read. Bump nothing in `project.json` until a field is agreed. |
| `rekindra_core/identify.py` | No change required. Its `zip` and `text` results are enough to route. Note that it inspects a header only, so text routing must still accept a `rejected` envelope. |
| `plugin.yaml` | Declare the tool. |
| `.github/workflows/test.yml` | No change required. `discover -s tests` already finds `tests/intake`. |
| `tests/` | Add a Hermes-level registry test, since current tests stop at the pure functions. |

Add `format`, `status` and warning codes to tool output for the agent to reason over. Avoid rendering `message` as if it were source content.

## Compatibility promises

`schema_version` stays `1` unless the envelope changes. Warning codes and the fields documented in `docs/intake/README.md` are stable. Message text may be reworded, so branch on `code`.

## Unsupported cases to expect

`unsupported` is a normal result. Show the user that the file was kept but not read.

- ZIP64, multi-disk, strong encryption and self-extracting archives.
- Tar, gzip, 7z, RAR.
- UTF-32, unmarked UTF-16 and legacy encodings. Unmarked UTF-16 is `rejected`; legacy text gives a `partial` prefix.
- Text-like formats outside the extension list, such as `.html`, `.py`, `.tsv` and `.jsonl`.

If real forgotten folders commonly hit one of these, the first candidates to add are legacy-encoding labelling chosen by the user and ZIP64. Each is a separate decision, because guessing an encoding would present invented text as recovered text.
