# Integration notes

For the primary developer. Nothing below is implemented. `rekindra_evidence` has no callers, and it neither imports nor requires `rekindra_intake`.

## Calling it

Trusted code reads each file, runs intake, and passes the results in.

```python
records = [{'source_id': asset_id, 'relative_path': display_path, 'intake': inspect_text(data, name)}
           for asset_id, display_path, data, name in collection]
dossier = build_dossier(records)
if dossier['status'] == 'rejected':
    ...  # read dossier['errors']; each has a stable code, record_index and field
```

Snapshot asset IDs from `ProjectStore` already fit the `source_id` format. `relative_path` must stay relative, so pass the display path inside the collection, never an absolute path. Absolute, drive, UNC and `..` paths reject the whole collection, which also keeps machine-specific paths out of dossiers.

Check for `rejected` before reading other fields, since rejected results have a smaller shape.

## Rules to keep at the boundary

1. **Evidence is untrusted quotation.** If it reaches an agent, present it as quoted source material. A file can contain text addressed to the agent. `untrusted_content: true` is only a label; the prompt has to honor it.
2. **Keep evidence and interpretation apart.** World authoring records what was observed and what was invented. A dossier belongs on the observed side, and a `source_id` plus locator is how an observation should cite its origin.
3. **Do not treat duplicates as relationships.** Identical bytes do not show shared authorship, chronology or ownership.
4. **Do not treat ZIP entries as contents.** Keep the `unverified_archive_metadata` provenance visible, and do not reuse entry names as paths.
5. **Do not report "not found" as "not there".** Pass the search `notice` and `scope` along, especially on `no_match`.
6. **Escape before display.** Evidence can contain HTML, scripts, formulas and control characters.

## Locators

`pointer` is resolved against the intake result supplied for that source, so that result must be kept if a citation needs checking later. Storing it beside the dossier, keyed by source hash, is enough.

`evidence_id` is stable for the same source, locator and text. Do not treat it as permanent across collections above 32 evidence-offering sources, where chunk size changes. `source_id` plus locator with the source hash is the durable citation.

## Proposed future wiring

These touch files outside this assignment, so they are proposals only.

| Where | Proposal |
|---|---|
| `handlers.py`, `schemas.py`, `plugin.yaml` | Read-only tools such as `rekindra_evidence_dossier(project_id)` and `rekindra_evidence_search(project_id, query)` |
| `rekindra_core/projects.py` | Save the dossier as a derived file, rebuilt when the asset set changes. It holds excerpts, so treat it like source data |
| `docs/world-authoring.md` | Have source interpretation cite `source_id` and locator for observed clues |
| `tests/` | Add a registry-level test, since current tests stop at the pure functions |

No CI change is needed: `discover -s tests` already finds `tests/evidence`. Tests use a saved intake snapshot, so regenerate `tests/evidence/intake_output_snapshot.json` if the intake envelope changes.

## Compatibility

`schema_version` stays `1` unless a documented field changes. Codes are stable; message text may be reworded, so branch on `code`.

The input check is deliberately strict: exact JSON types, exactly three record keys, and intake schema version 1. If intake changes its envelope, update `valid_intake` in `rekindra_evidence/_validate.py` and the schema document together.
