# Rekindra source evidence

`rekindra_evidence` turns intake results into one collection-level dossier. It helps answer three questions: what evidence do these files actually contain, which files are identical, and where did each clue come from?

It reports observations only. It does not generate stories, scenes, summaries or historical claims, and it never reads a file. Nothing in the plugin calls it yet.

The exact result shapes, status codes and warning codes are in [schemas.md](schemas.md), which is the contract.

The library accepts plain dictionaries and imports only the Python standard library. It does not import Hermes, `rekindra_core` or `rekindra_intake`.

## API

```python
from rekindra_evidence import build_dossier, search_dossier

dossier = build_dossier([
    {'source_id': 'note-1', 'relative_path': 'notes/project.md', 'intake': intake_result},
])

for group in dossier['duplicate_groups']:
    print(group['source_ids'])

result = search_dossier(dossier, 'harbour bell', limit=5)
for match in result['matches']:
    print(match['source_id'], match['locator'], match['snippet'])
print(result['notice'])
```

Both functions are pure. They use no filesystem, network, clock, randomness or model, and they never change their inputs. Identical input gives byte-identical output, and record order does not matter.

`TypeError` is raised only for wrong argument types: `records` not a `list`, `dossier` not a `dict`, `query` not a `str`, or `limit` not an `int`. Malformed data inside those arguments returns `status: rejected` with stable error codes.

## Limits

| Limit | Value | When exceeded |
|---|---|---|
| Source records | 128 | Rejected |
| Canonical UTF-8 JSON input | 1 MiB | Rejected |
| Nesting depth | 32 | Rejected |
| Evidence items | 256 | Omitted and reported |
| Characters per evidence item | 1,000 | Split or clipped and reported |
| Retained evidence characters | 32,000 | Clipped or omitted and reported |
| Serialized dossier | 256 KiB | Evidence omitted and reported; rejected if identity data alone is too large |
| Query | 256 characters | Rejected |
| Search results | 20 | `limit` above 20 is rejected; extra matches are counted |

Input limits are checked by an iterative walk before any recursive serialization.

## Example output

From the synthetic collection, searching `ferry storm` (shortened):

```json
{
  "rank": 1,
  "source_id": "note-letter",
  "relative_path": "notes/letter.txt",
  "provenance": "observed_source_text",
  "locator": {"pointer": "/facts/excerpt", "char_start": 0, "char_end": 71},
  "snippet": "The ferry stopped running after the storm.\nAsk about the harbour bell.\n",
  "explanation": {"match_type": "all_terms", "matched_terms": ["ferry", "storm"], "unmatched_terms": [], "occurrences": 2}
}
```

Duplicate group from the same collection:

```json
{"group_id": "dup-8956f38c4bfdbdd2-60", "size_bytes": 60, "source_ids": ["map-original", "map-renamed"], "basis": "sha256_and_size"}
```

## What a dossier means

| A dossier says | It does not say |
|---|---|
| This text appears in that intake result, at this locator | The text is true, or was written when it claims |
| These sources have identical bytes | They share an author, date or owner |
| This ZIP lists an entry with this name and claimed size | The entry exists as claimed, or its contents were inspected or recovered |
| A search found nothing in retained evidence | The sources do not contain the query |

Evidence is quoted source data. Instructions, HTML, JavaScript and spreadsheet formulas stay as inert strings and are returned verbatim. Escape them before displaying them, and present them to agents as quotations.

**Dossier status:** `ok` means every available evidence candidate was retained whole, and `partial` means something was clipped or omitted. Neither describes the sources themselves. Read `coverage`: an `ok` dossier can still have `complete: false`, for example when it contains a ZIP or an unsupported file.

**Duplicates** need a valid, non-null SHA-256 and a matching valid size. Missing or invalid hashes are never grouped. Different content with the same basename is never grouped.

**Fairness:** evidence is shared round-robin, with item size scaled to the collection, so every source offering evidence gets a turn before the character limit runs out. With 128 large sources, that means one item of 250 characters each.

## Search

Search looks only at each retained item's `text`. Filenames, archive sizes and warning codes are not searched.

Text and query are compared after Unicode decomposition, case-folding and whitespace collapsing. Accents still matter, so `cafe` does not match `café`. Terms match as plain substrings, so `bell` also matches `rebellion`. There is no stemming, fuzzy matching or embedding.

Matches rank by exact phrase, then all terms, then some terms, followed by more matched terms, more occurrences, and dossier order. Every result reports its scope and repeats that search covers retained evidence only.

## Limitations

- A phrase split across two excerpt chunks will not match as a phrase, though its terms can still match separately.
- Evidence only comes from the known intake fields documented in the schema. Other facts are ignored.
- CSV rows and JSON keys are joined with ` | `, which is marked `transform: cells_joined`. A cell containing ` | ` reads ambiguously, and the locator gives the original list.
- Above 32 evidence-offering sources, item size depends on the collection, so some `evidence_id` values can change when sources are added.
- If source paths and IDs alone exceed the output limit, the dossier is rejected rather than trimmed.
- It only understands intake schema version 1.

## Running tests and the example

```bash
python -m unittest discover -s tests/evidence -v
```

```bash
python -m unittest discover -s tests -v
```

```bash
python examples/evidence/synthetic_collection.py
```

```bash
python examples/evidence/synthetic_collection.py --print-expected
```

The example needs no intake package. Its data is invented and hand-written in the documented intake shape, and its hashes are real digests of the inline bytes. Expected results are committed as [expected_results.json](../../examples/evidence/expected_results.json), and a test compares them. If output changes on purpose, review the difference and regenerate that file.

`tests/evidence/intake_output_snapshot.json` is saved intake output from invented inputs. It lets tests check the real result shape without importing intake.
