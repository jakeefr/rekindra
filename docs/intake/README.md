# Rekindra source intake

`rekindra_intake` describes forgotten files without changing them. It takes bytes, returns JSON-compatible data and has no knowledge of Hermes, the runtime or any model. It is standalone: nothing in the plugin calls it yet.

It reports what is structurally present. It does not summarize, interpret or recover content, and an archive inventory is not an extraction.

## API

```python
from rekindra_intake import inspect_archive, inspect_text

inspect_text(data: bytes, filename: str) -> dict
inspect_archive(data: bytes, filename: str) -> dict
```

```python
result = inspect_text(b'# Title\n\nBody\n', 'notes.md')
result['status']               # 'ok'
result['format']               # 'markdown'
result['facts']['headings']    # [{'level': 1, 'line': 1, 'text': 'Title'}]

result = inspect_archive(zip_bytes, 'old-drafts.zip')
for entry in result['facts']['entries']:
    print(entry['name'], entry['safety_warnings'])
```

Both functions:

- Are pure. They do not touch the filesystem, network, clock or randomness, so identical bytes and filename give identical output.
- Treat `filename` as display text and never open it.
- Raise `TypeError` only when `data` is not `bytes` or `filename` is not `str`. This includes `bytearray`. Malformed content always returns an envelope.

## Envelope

```json
{
  "schema_version": 1,
  "format": "markdown",
  "status": "ok",
  "source": {"name": "notes.md", "size_bytes": 14, "sha256": "6d94..."},
  "facts": {},
  "warnings": [{"code": "stable_machine_code", "message": "plain explanation"}]
}
```

`source.name` is a basename safe for both slash styles, at most 255 characters. Drive prefixes are removed, control, format and surrogate characters become `_` (reported as `filename_sanitized`), and an empty result becomes `unnamed`. `sha256` is `null` only when input was over budget. Each warning code appears at most once.

## What each status means

| Status | Meaning | Text examples | ZIP examples |
|---|---|---|---|
| `ok` | The analysis finished. Warnings can still apply. | Clean file; truncated excerpt; formula-like cells | Complete inventory, **including one with dangerous names** |
| `partial` | Some analysis was possible, but the content is damaged or was not fully examined. | Invalid bytes after a valid prefix; malformed JSON or CSV; JSON too deep to parse | Over 256 entries; damaged record after good ones; contradictory metadata; trailing bytes |
| `unsupported` | Recognized as out of scope. Nothing structural is reported. | Other extensions; UTF-32 | ZIP64; multi-disk; strong encryption; prepended data |
| `rejected` | Refused. No usable result. | Over budget; binary; nothing decodable; non-finite JSON | Over budget; not a ZIP; truncated; central directory unusable |

**`ok` never means safe to extract.** It only means the inventory finished. Check `safety_warnings` and `flagged_entry_count`. No field declares an entry safe.

`format` is `unknown` unless the bytes were validated as that format. Rejected text keeps the filename's guess in `facts.claimed_format`.

## Text inspector

| Limit | Value |
|---|---|
| Input | 256 KiB; larger input is rejected before hashing |
| Source text across all `facts` | 4,000 characters |
| Of which structure (headings, keys, cells) | at most 2,000, served first; the excerpt gets the rest |
| Each heading, key or cell | 80 characters; a shortened item adds the `structure_truncated` warning |
| Reported headings or keys | 64 |
| JSON depth | 20 (root container is depth 1) |
| CSV preview | 20 rows, 32 columns |

Filenames choose the format. Bytes still have to validate.

| Format | Extensions |
|---|---|
| `text` | `.txt`, `.text`, `.log`, or none |
| `markdown` | `.md`, `.markdown` |
| `json` | `.json` |
| `csv` | `.csv` |

Anything else, including `.html`, `.py`, `.tsv` and `.jsonl`, is `unsupported`, with a hash but no content.

**Encodings:** UTF-8, and UTF-8 or UTF-16 LE/BE with a byte-order mark. Nothing else is guessed. UTF-16 without a mark contains NUL bytes and is rejected as binary. Legacy encodings such as Latin-1 give a `partial` result up to the first invalid byte.

**Damaged text:** decoding stops at the first invalid byte. The valid prefix is described as `partial`, with `decoded_bytes`, `undecoded_bytes` and `first_invalid_offset`. Bytes are never replaced. If no text decodes at all, the result is `rejected`.

**Binary:** any NUL byte, or more than 1 control character in 10, is `rejected` as `binary_content`. Known signatures appear as `detected_signature`. Fewer control characters are kept and counted.

All text results include `encoding`, `bom`, `line_count`, `blank_line_count`, `char_count`, `word_count`, `longest_line_chars`, `control_character_count`, `excerpt`, `excerpt_truncated` and `untrusted_content`. Only CR, LF and CRLF end a line.

**Text and Markdown** add `headings`, `heading_count`, `headings_truncated` and `fenced_code_block_count`. Headings are ATX only (`# Title`), and fenced code is skipped. Setext headings are not detected. The same syntactic rule applies to `.txt`, so a `#` comment line there counts as a heading.

**JSON** adds `valid` (`true`, `false`, or `null` when not parsed), `root_type`, and `max_depth` when parsed. Objects add `top_level_keys`, `top_level_key_count` and `top_level_keys_truncated`. Arrays add `array_length`. Values are never reported outside the excerpt.

- Too deep: `partial`, `valid: null`, not parsed. A linear scan checks depth first, so the parser cannot recurse deeply.
- `NaN`, `Infinity` or numbers overflowing to infinity such as `1e999`: `rejected`, `valid: false`.
- Malformed: `partial`, `valid: false`, with `error.line` and `error.column`.
- Duplicate keys at any depth are counted.

**CSV** adds `row_count`, `column_count` (widest row), `min_column_count`, `blank_row_count`, `first_row`, `next_rows`, `formula_like_cell_count` and three `preview_*_truncated` flags. `error_line` is added when parsing stops.

- The delimiter is always a comma; no dialect is sniffed.
- `formula_like_cell_count` counts cells starting with `=`, `@`, tab or carriage return, and cells starting with `+` or `-` unless the whole cell is a plain number. See rule 5 in `integration-notes.md`.
- `first_row` is only the first row. No header is inferred.
- Cells beginning `=` or `@`, or `+`/`-` before a non-number, are counted and stay inert text. Do not paste them into a spreadsheet.
- Bad quoting is `partial` and parsing stops at that row. Uneven rows are `ok` with a warning.
- Fields over `csv.field_size_limit()` (default 131,072) give `partial` with `csv_field_too_large`. The limit is process-wide, so it is read, not changed.

## ZIP inspector

Parsed by hand from metadata. It never imports `zipfile` or a decompressor, never reads a payload, and never opens a nested archive.

| Limit | Value |
|---|---|
| Input | 8 MiB; larger input is rejected before hashing |
| Entries read | 256; the walk then stops, so work is bounded regardless of claims |
| Name returned | 512 characters; the full name is still checked, and a shortened name adds the `entry_name_truncated` warning |

**Supported subset:** single-disk, non-ZIP64 archives whose central directory ends exactly where the end record begins. Any compression method is listed, since nothing is decompressed. Traditional and AES entries are listed with `encrypted: true`.

**Unsupported, with a stable code:**

| Code | Case |
|---|---|
| `zip64_unsupported` | ZIP64 locator or any sentinel field |
| `multidisk_unsupported` | Any disk number or per-disk count mismatch |
| `strong_encryption_unsupported` | Strong encryption or masked headers (flag bits 6, 13) |
| `prepended_data_unsupported` | Bytes between directory and end record, as in self-extractors |

`facts` contains `entries`, `entry_count_declared`, `entries_inspected`, `entries_truncated`, `flagged_entry_count`, `total_compressed_bytes`, `total_claimed_uncompressed_bytes` and `comment_bytes`. It also states `payloads_read: false`, `extraction_performed: false`, `claimed_sizes_verified: false` and `untrusted_content: true`. Comments are measured but never returned.

Each entry has `name`, `name_encoding`, `name_bytes`, `name_truncated`, `is_directory`, `compressed_size_bytes`, `claimed_uncompressed_size_bytes`, `compression_method`, `compression_method_name`, `claimed_crc32`, `encrypted` and `safety_warnings`.

Names are returned exactly as stored and are never normalized, so a dangerous path stays visibly dangerous. Sizes and CRCs are claims. Local headers are read only to compare offsets and names; payload bytes cannot affect the facts.

### Entry warnings

| Group | Codes |
|---|---|
| Paths | `absolute_path`, `drive_path`, `unc_path`, `path_traversal`, `backslash_separator`, `colon_in_name`, `windows_reserved_name`, `control_character_in_name`, `empty_name`, `unicode_lookalike_path` |
| Links | `symlink`, `special_file` |
| Collisions | `duplicate_name`, `case_fold_collision` (also covers Unicode form and spellings such as `a//b`) |
| Expansion | `suspicious_expansion` |
| Encryption | `encrypted` |
| Names | `name_not_decodable`, `unicode_path_extra` |
| Other | `nested_archive_not_inspected`, `unknown_compression_method`, `directory_with_data` |
| Contradictions, which also make the result `partial` | `entry_out_of_bounds`, `local_header_missing`, `local_name_mismatch`, `overlapping_entries`, `size_inconsistent` |

`suspicious_expansion` applies when an entry claims at least 1 GiB, claims data with zero compressed bytes, or claims at least 1 MiB at a ratio of 100:1 or more. These are heuristics and legitimate files can trigger them. `suspicious_total_expansion` applies to at least 1 GiB across the inspected entries.

`nested_archive_not_inspected` applies when the name, after trailing dots and spaces are removed (Windows drops them on extraction), ends in an archive suffix such as `.zip`, `.7z` or `.tar`, ignoring case.

Archive-level codes: `input_too_large`, `not_a_zip`, `eocd_missing`, `central_directory_out_of_bounds`, `central_directory_malformed`, `entry_count_mismatch`, `entry_limit_exceeded`, `entry_name_truncated`, `multiple_eocd_candidates`, `trailing_data`, `extension_mismatch`.

## Limitations

- Entries past the 256th are not examined. The result is `partial` and later entries may be dangerous.
- ZIP entries have no timestamps in the output, and their content is never read.
- End records further than 64 KiB + 22 bytes from the end of the file are not found.
- `unicode_path_extra` flags an alternate name but does not decode it.
- Text direction controls in text excerpts are not counted. They are only flagged in ZIP names.
- No tar, gzip, 7z or RAR support. No PDF, DOCX or HTML parsing.
- `.tga` and images are out of scope here; `rekindra_core` handles recovery.

## Running tests

```bash
python -m unittest discover -s tests/intake -v
```

```bash
python -m unittest discover -s tests -v
```

Both forms work: `tests/intake` is a package, so the second also runs these tests.

## Synthetic source pack

```bash
python examples/intake/generate_source_pack.py OUTPUT_DIR
```

```bash
python examples/intake/generate_source_pack.py --print-expected
```

The first writes six invented files into an empty or new directory: Markdown notes, a UTF-16 log, JSON metadata, CSV cues, a stored ZIP and an optional 2x2 TGA. It refuses a non-empty directory, a file or a symbolic link, and downloads nothing.

The second prints expected results and hashes without writing. They are committed as [expected_intake.json](../../examples/intake/expected_intake.json), and a test compares them. If the inspectors' output changes on purpose, review the difference and regenerate that file.

The ZIP is written byte by byte with stored entries and fixed timestamps, because `zipfile` headers vary by platform and deflate output varies by zlib build.
