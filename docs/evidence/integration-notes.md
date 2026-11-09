# Integration notes

For the primary developer. `rekindra_evidence` neither imports nor requires `rekindra_intake`, but the plugin now calls it, in a different way from the original proposal. [Current wiring](#current-wiring) describes what runs, checked against `af67b55`. The original proposals are kept at the end, marked as not adopted.

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
2. **Keep evidence and interpretation apart.** World authoring records what was observed and what was invented. A dossier belongs on the observed side. Inside the plugin, an observation cites its origin by `asset_id` plus `evidence_id` through `text_references`. Outside it, use `source_id` plus locator.
3. **Do not treat duplicates as relationships.** Identical bytes do not show shared authorship, chronology or ownership.
4. **Do not treat ZIP entries as contents.** Keep the `unverified_archive_metadata` provenance visible, and do not reuse entry names as paths.
5. **Do not report "not found" as "not there".** Pass the search `notice` and `scope` along, especially on `no_match`.
6. **Escape before display.** Evidence can contain HTML, scripts, formulas and control characters.

## Locators

`pointer` is resolved against the intake result supplied for that source, so that result must be kept if a citation needs checking later. The plugin stores it beside the dossier as `artifacts/<asset_id>.intake.json`, with its hash in the project manifest.

`evidence_id` is stable for the same source, locator and text. Do not treat it as permanent across collections above 32 evidence-offering sources, where chunk size changes. `source_id` plus locator with the source hash is the durable citation.

## Current wiring

Checked against `af67b55`. No dossier or search tool was added. The dossier is built inside the existing `rekindra_recover`.

| Where | What happens |
|---|---|
| `handlers.py` | `evidence_reader` runs `build_dossier` and then two plugin-side markers, `mark_member_coverage` and `mark_pdf_pages`. `evidence_summary` returns a first view of the recovered asset: up to 6 evidence items of 240 characters, coverage, warning codes and notices. The full dossier stays on disk. |
| `rekindra_core/projects.py` | Each recover rebuilds one dossier for the whole project from every recovered text, ZIP and PDF asset. It is saved as `artifacts/evidence.json`, with its hash in the project manifest. Each ZIP text member and PDF page becomes a source of its own, `<asset_id>:mNNNN`, with a path such as `notes.zip!a.txt`. A dossier that comes back `rejected` is not saved, and the earlier one is kept. |
| `rekindra_core/zip_text.py`, `rekindra_core/pdf_text.py` | Supply the member and page sources. `mark_member_coverage` sets `member_contents_inspected` on the parent row (see [schemas.md](schemas.md)), and `mark_pdf_pages` adds `page_number`. |
| `docs/world-authoring.md` | World authoring cites recovered text by `asset_id` plus `evidence_id` values through `text_references`, not by `source_id` and locator. Members are cited through their archive's or PDF's `asset_id`. |
| `search_dossier` | Not called by the plugin. Only `examples/evidence/synthetic_collection.py` uses it. |
| `tests/` | `tests/test_recover_evidence.py`, `tests/test_zip_text.py` and `tests/test_pdf_text.py` cover the wiring through the store and handlers. No test here drives a real Hermes install. |

Testing: no workflow change was made. GitHub Actions results are not used as evidence for this repository. The evidence is a local run of `PYTHONDONTWRITEBYTECODE=1 py -3 -m unittest discover -s tests`, which also finds `tests/evidence`. Tests use a saved intake snapshot, so regenerate `tests/evidence/intake_output_snapshot.json` if the intake envelope changes.

### Original proposals, not adopted

The first version of these notes proposed `rekindra_evidence_dossier(project_id)` and `rekindra_evidence_search(project_id, query)` tools declared in `plugin.yaml`, and world authoring citing `source_id` plus locator. None was built. As proposed, the dossier is a derived file rebuilt when the evidence changes, and it holds excerpts, so treat it like source data.

## Compatibility

`schema_version` stays `1` unless a documented field changes. Codes are stable; message text may be reworded, so branch on `code`.

The input check is deliberately strict: exact JSON types, exactly three record keys, and intake schema version 1. If intake changes its envelope, update `valid_intake` in `rekindra_evidence/_validate.py` and the schema document together.
