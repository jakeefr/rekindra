# Evidence result schemas

This is the contract for `rekindra_evidence`, written before the code. All results use `schema_version: 1`. Codes are stable; message text may be reworded, so branch on `code`.

## Limits

| Limit | Value |
|---|---|
| Source records | 128 |
| Canonical input | 1 MiB |
| Nesting depth | 32 (the `records` list is depth 1) |
| Evidence items | 256 |
| Characters per evidence item | 1,000 |
| Retained evidence characters | 32,000 |
| Serialized dossier | 256 KiB |
| Query | 256 characters |
| Search results | 20 |

These smaller limits are added by this package:

| Limit | Value |
|---|---|
| `source_id` | 1 to 128 characters of `A-Z a-z 0-9 . _ : -` |
| `relative_path` | 1 to 512 characters |
| Validation errors returned | 32 |
| Warnings kept per source | 16, messages clipped to 160 characters |
| Evidence candidates read per source | 256 |
| Search snippet | 240 characters |

**Canonical input** means `json.dumps(records, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')`. Its size is computed by an iterative walk, so oversized or deep input is refused without serializing it.

**Serialized dossier** size means `len(json.dumps(result, allow_nan=False))`. That is the largest common encoding, so the limit holds for the others too.

## `build_dossier(records: list[dict]) -> dict`

`TypeError` is raised only when `records` is not a `list`. Everything inside it gets a structured result.

### Input record

```json
{
  "source_id": "note-1",
  "relative_path": "notes/project.md",
  "intake": {"schema_version": 1, "format": "markdown", "status": "ok",
             "source": {"name": "project.md", "size_bytes": 14, "sha256": "64 lowercase hex characters or null"},
             "facts": {}, "warnings": [{"code": "stable_code", "message": "text"}]}
}
```

Exactly these three keys are allowed. Values must be plain JSON types: exact `dict`, `list`, `str`, `int`, `float`, `bool` or `None`, with `str` keys, finite floats and valid Unicode.

`relative_path` is display text and is never opened. It must be relative: no absolute, drive, UNC or `..` paths, no empty paths and no control characters.

The envelope must have `schema_version` exactly `1` (`True` is not `1`), a known `format` and `status`, a `source` object, a `facts` object, and a `warnings` list of `{code, message}` strings.

An invalid `sha256` or `size_bytes` does not reject the collection. That source keeps its row, gets a warning, and is excluded from duplicate groups.

### Rejected dossier

```json
{
  "schema_version": 1,
  "kind": "rekindra.evidence_dossier",
  "status": "rejected",
  "errors": [{"code": "duplicate_source_id", "message": "text", "record_index": 3, "field": "source_id"}],
  "errors_truncated": false
}
```

`record_index` and `field` are `null` for collection-level errors. Errors never echo caller values.

| Code | Meaning |
|---|---|
| `too_many_records` | More than 128 records |
| `input_too_large` | Canonical input over 1 MiB |
| `input_too_deep` | Nesting over 32 |
| `invalid_json_value` | A value is not JSON-compatible |
| `invalid_record` | Record is not an object, or has missing or extra keys |
| `invalid_source_id` | `source_id` is missing or breaks its format |
| `duplicate_source_id` | `source_id` repeats |
| `invalid_relative_path` | `relative_path` is not a safe relative path |
| `invalid_intake` | The intake envelope is malformed |
| `output_too_large` | Identity data alone exceeds 256 KiB |

### Built dossier

```json
{
  "schema_version": 1,
  "kind": "rekindra.evidence_dossier",
  "status": "ok",
  "limits": {},
  "counts": {"sources": 1, "by_format": {"markdown": 1}, "by_status": {"ok": 1}},
  "sources": [],
  "duplicate_groups": [],
  "evidence": [],
  "coverage": {},
  "warnings": [],
  "notices": []
}
```

- `status` is `ok` when every available evidence candidate was retained whole, otherwise `partial`. It says nothing about the sources' own condition. Read `coverage` for that.
- `sources` is sorted by `source_id`. The result does not depend on input order.
- `limits` lists the limits above.
- `notices` holds fixed `{code, message}` statements about what the dossier does not establish.

### Source row

```json
{
  "source_id": "note-1",
  "relative_path": "notes/project.md",
  "display_name": "project.md",
  "format": "markdown",
  "inspection_status": "ok",
  "size_bytes": 14,
  "sha256": "... or null",
  "duplicate_group": "dup-0123456789abcdef-14",
  "warnings": [{"code": "stable_code", "message": "text"}],
  "warnings_omitted": 0,
  "coverage": {
    "content_inspected": true,
    "member_contents_inspected": null,
    "intake_truncated": ["excerpt_truncated"],
    "undecoded_bytes": 0,
    "evidence_available": 4,
    "evidence_retained": 4,
    "characters_available": 120,
    "characters_retained": 120,
    "candidates_capped": false,
    "source_text_fully_retained": false
  }
}
```

- `content_inspected` is `true` only for text formats with status `ok` or `partial`. Sources with status `rejected` or `unsupported` produce no evidence in any format, so their `evidence_available` is `0`; the row is still listed.
- `member_contents_inspected`, as `build_dossier` returns it, is `false` for ZIP sources and `null` otherwise. The package alone never sets it to `true`. The plugin's live wiring does: after `build_dossier`, `mark_member_coverage` in `rekindra_core/zip_text.py` sets it to `true` on any row that has member sources (`<source_id>:mNNNN`). That covers a ZIP whose text members were read, and also a PDF whose pages gave text, which `build_dossier` alone reports as `null`. A ZIP with no member read keeps `false`.
- `intake_truncated` lists the truncation flags the intake result set, sorted.
- `source_text_fully_retained` is `true` only when intake status is `ok`, its excerpt was complete, and all of that excerpt was retained. It is always `false` for ZIP.

An invalid `size_bytes` or `sha256` appears here as `null`.

### Duplicate group

```json
{
  "group_id": "dup-0123456789abcdef-14",
  "sha256": "64 hex characters",
  "size_bytes": 14,
  "source_ids": ["copy-a", "copy-b"],
  "basis": "sha256_and_size"
}
```

A group needs at least two sources with a valid, non-null SHA-256 and the same valid size. `group_id` comes from that content, not from `source_ids`. Groups are sorted by `group_id`. This covers identical bytes only.

### Evidence item

```json
{
  "evidence_id": "ev-0123456789abcdef01234567",
  "source_id": "note-1",
  "kind": "excerpt",
  "provenance": "observed_source_text",
  "locator": {"pointer": "/facts/excerpt", "char_start": 0, "char_end": 14},
  "text": "# Title\n\nBody\n",
  "clipped": false,
  "untrusted_content": true
}
```

`evidence` is sorted by `source_id`, then by the source's candidate order. `evidence_id` is a hash of the source ID, locator and text.

**Locators** are relative to that source's supplied `intake` object. `pointer` is an RFC 6901 JSON Pointer.

- With `char_start` and `char_end`, `text` is exactly that slice of the pointed string, in Python characters.
- `transform: "cells_joined"` means `text` joins the pointed list's strings with ` | `, and `clipped` says whether it was cut.

| `kind` | From | `provenance` | Extra fields |
|---|---|---|---|
| `excerpt` | text formats, `/facts/excerpt` | `observed_source_text` | |
| `heading` | `/facts/headings/N/text` | `observed_structure` | `source_line`, `heading_level` as supplied by intake |
| `json_keys` | `/facts/top_level_keys` | `observed_structure` | |
| `csv_row` | `/facts/first_row`, `/facts/next_rows/N` | `observed_structure` | |
| `archive_entry_name` | `/facts/entries/N/name` | `unverified_archive_metadata` | `archive_metadata` |

`source_line` is copied from intake and is omitted when intake gives no valid integer. No line numbers are calculated.

`archive_metadata` holds `claimed_uncompressed_size_bytes`, `compressed_size_bytes`, `is_directory`, `encrypted` and `safety_warnings`, each copied from intake when valid and `null` otherwise. These are claims. They do not show that member contents were inspected or recovered.

**Item size** is a fair share: the smaller of 1,000 characters and 32,000 divided by the number of sources offering any evidence. With 32 or fewer such sources it is 1,000; with 128 it is 250. Longer excerpts become several `excerpt` items of that size, each cut preferring whitespace in its last 100 characters. Longer structure items are clipped to it.

**Selection** is round-robin over sources in `source_id` order. Each source offers its first excerpt chunk, then structure, then its remaining chunks, so every source gets a turn before the character limit runs out, and characters that short sources leave unused go to longer ones in later rounds. The item that crosses the 32,000-character limit is clipped to fit, and later ones are omitted. If the serialized dossier would exceed 256 KiB, later items are dropped.

Above 32 evidence-offering sources, item size depends on the collection, so `evidence_id` values for chunked or clipped text can change when sources are added.

### Coverage

```json
{
  "sources_total": 1,
  "sources_with_evidence": 1,
  "sources_without_evidence": 0,
  "sources_not_content_inspected": 0,
  "sources_text_fully_retained": 1,
  "evidence_available": 4,
  "evidence_retained": 4,
  "evidence_omitted": {"item_limit": 0, "character_limit": 0, "output_limit": 0},
  "evidence_items_clipped": 0,
  "characters_available": 120,
  "characters_retained": 120,
  "complete": true
}
```

`complete` is `true` only if there is at least one source and every source has `source_text_fully_retained`.

### Dossier warnings

These are sorted by code.

| Code | Meaning |
|---|---|
| `empty_collection` | No records were supplied |
| `evidence_item_limit_reached` | Items omitted at 256 |
| `evidence_character_limit_reached` | Items clipped or omitted at 32,000 characters |
| `output_limit_reached` | Items omitted at 256 KiB |
| `evidence_clipped` | At least one item was cut |
| `candidates_capped` | A source offered more than 256 candidates |
| `invalid_sha256` | A source hash is invalid and was not grouped |
| `invalid_size_bytes` | A source size is invalid and was not grouped |
| `sha256_size_conflict` | Equal hashes with different sizes; not grouped together |
| `malformed_fact_skipped` | A fact had the wrong shape and yielded no evidence |

## `search_dossier(dossier: dict, query: str, *, limit: int = 10) -> dict`

`TypeError` is raised when `dossier` is not a `dict`, `query` is not a `str`, or `limit` is not an `int` (`bool` included). Other problems return a rejection.

### Matching

Search covers only each retained item's `text`, not archive metadata or warning codes.

1. Text and query are normalized the same way: each character is NFKD-decomposed and case-folded, and whitespace runs become one space. Accents still matter, but composed and decomposed forms match.
2. The query's space-separated pieces are its `terms`, with repeats removed.
3. Terms are matched as plain substrings, so `bell` also matches `rebellion`. Nothing is stemmed, fuzzy or semantic.

| `match_type` | Rule |
|---|---|
| `exact_phrase` | The whole normalized query occurs |
| `all_terms` | Every term occurs |
| `some_terms` | At least one term occurs |

### Ordering

Matches sort by: `match_type` in the table's order, then more matched terms, then more occurrences, then dossier evidence order. This order is total, because evidence order is unique.

### Result

```json
{
  "schema_version": 1,
  "kind": "rekindra.evidence_search",
  "status": "ok",
  "query": {"text": "lantern tide", "normalized": "lantern tide", "terms": ["lantern", "tide"]},
  "limit": 10,
  "total_matches": 1,
  "returned": 1,
  "results_truncated": false,
  "matches": [{
    "rank": 1,
    "evidence_id": "ev-0123456789abcdef01234567",
    "source_id": "note-1",
    "relative_path": "notes/project.md",
    "kind": "excerpt",
    "provenance": "observed_source_text",
    "inspection_status": "ok",
    "locator": {"pointer": "/facts/excerpt", "char_start": 0, "char_end": 14},
    "snippet": "text",
    "snippet_start": 0,
    "snippet_end": 4,
    "snippet_truncated_start": false,
    "snippet_truncated_end": false,
    "explanation": {"match_type": "exact_phrase", "matched_terms": ["lantern", "tide"],
                    "unmatched_terms": [], "occurrences": 2, "rule": "fixed sentence"},
    "untrusted_content": true
  }],
  "scope": {
    "coverage": "retained_evidence_only",
    "dossier_status": "ok",
    "evidence_items_searched": 4,
    "characters_searched": 120,
    "evidence_items_not_retained": 0,
    "sources_not_content_inspected": 0,
    "sources_text_not_fully_retained": 0
  },
  "notice": "fixed sentence"
}
```

`status` is `ok` or `no_match`. `snippet_start` and `snippet_end` are offsets into that evidence item's `text`. On `no_match`, `notice` states that uninspected or truncated source content may still contain the query.

### Rejected search

```json
{
  "schema_version": 1,
  "kind": "rekindra.evidence_search",
  "status": "rejected",
  "errors": [{"code": "query_too_long", "message": "text"}]
}
```

| Code | Meaning |
|---|---|
| `empty_query` | Nothing remains after normalization |
| `query_too_long` | Query over 256 characters |
| `invalid_query` | Query is not valid Unicode text |
| `limit_out_of_range` | `limit` is not 1 to 20 |
| `invalid_dossier` | The object is not a usable dossier |
| `dossier_rejected` | The dossier's own status is `rejected` |
