# Live wiring audit at `af67b55`

Read-only audit of the three open items that the source-stack reconciliation (#17) raised. No code, test or other doc file was changed. Every result below was run locally against synthetic data.

- **Commit:** `af67b55` (Merge README Working now update), clean worktree
- **Host:** Windows 11 Home 10.0.26200
- **Python for the probes:** 3.12.3 in a virtual environment with pypdf 6.21.4 and Pillow 13.0.0. The unsupported-PDF case used system Python 3.12.3 without pypdf.
- **No model calls, no Hermes install and no project store other than throwaway ones.**

## Summary

| # | Item | Severity | Verdict |
|---|---|---|---|
| 1 | ZIP reader takes member text from a directory intake never inventoried | Medium | Gap: reproduced end to end through `rekindra_recover` |
| 2 | Intake rule 3 says to refuse any `partial` archive; `zip_text` reads them | Low | Gap between rule and code. Only the case in item 1 is dangerous |
| 3 | `evidence_summary` can reach 15,941 characters | Medium | Over Hermes's 8,000-character floor. When spilled, the 1,500-character preview has evidence text but no untrusted label |
| 4 | Flagged entries and each flag in `_TOLERATED` | None | Fine. Every flagged entry is skipped |
| 5 | `unsupported` sources keep their facts at `projects.py:483` | None | Fine. Nothing from an unsupported source reaches evidence |

## ZIP text against intake rule 3

Rule 3 in `docs/intake/integration-notes.md` says that any extraction must "refuse flagged entries and any `partial` archive, since entries past 256 are unexamined". `rekindra_core/zip_text.py` doesn't write to disk, but it does read member contents into evidence, so the rule applies.

The probe script builds each archive by hand, runs `inspect_archive`, then runs `read_archive_text` on the result.

### Flagged entries: met

`_precheck` skips any entry that has a safety warning outside `_TOLERATED`, giving the reason `unsafe_member`. It also skips any entry whose name differs from what `zipfile` reports, or whose name is truncated, too long or unsafe.

| Archive | Intake flag | Result |
|---|---|---|
| `notes\evil.txt` beside `notes/tide.txt` (raw bytes) | `backslash_separator` | `notes\evil.txt` skipped as `unsafe_member`; `tide.txt` read |
| Two entries named `notes/tide.txt` | `duplicate_name` on both | Both skipped as `unsafe_member` |

### Each tolerated flag: met

| Flag | What happens | Evidence |
|---|---|---|
| `encrypted` | `_precheck` checks `entry['encrypted']` and `info.flag_bits & 1` first, giving `encrypted_member` | Archive whose only member has the encryption bit set: `encrypted_member`, then refused as `encrypted_archive` |
| `nested_archive_not_inspected` | Checked before anything else, giving `nested_archive_not_read` | `inner.zip` beside a note: `inner.zip` skipped, note read |
| `suspicious_expansion` | Intake raises it in three cases, and none of them can be read | See below |

Intake raises `suspicious_expansion` when an entry:

- **claims 1 GiB or more:** over the 256 KiB member cap, so `member_too_large`, or the whole archive is refused as `zip_bomb_guard`.
- **claims 1 MiB or more at 100:1:** over the member cap, so `member_too_large`. Probe: a 2 MiB deflated note gave `member_too_large`.
- **claims a size from zero compressed bytes:**
  - With stored compression, intake also raises `size_inconsistent`, which isn't tolerated.
  - With deflate, the read fails. Probe: a member claiming 50 bytes from 0 compressed gave `corrupt_member`.

### Partial archives: not met

`read_archive_text` returns early only for `rejected` and `unsupported`. A `partial` archive is read.

| Why intake says `partial` | Probe result | Risk |
|---|---|---|
| `entry_limit_exceeded` (more than 256 entries) | A text member at position 281 was **not read**. Members are paired with `zip(entries, archive.infolist())`, which stops at intake's 256 | None. This is the reason the rule gives, and it holds |
| `trailing_data` | Member read | Low. Same directory as intake |
| `entry_count_mismatch` | Member read | Low. Same directory as intake |
| `multiple_eocd_candidates` | Member read **from a different central directory** | Finding 1 |

#### Finding 1: member text from a directory that intake never inventoried. Medium

The archive below has two end-of-central-directory records:

- Record A is ordinary. Its comment hides a second local header, directory B and record B.
- Record B is the last 22 bytes of the file. It declares its directory 100 bytes before where it really sits.
- `_find_eocd` prefers a record whose directory ends exactly where the record begins, so intake inventories A. Python's `zipfile` takes the record at the end of the file, B, and adds the 100-byte gap to every offset.
- Both directories list `notes/tide.txt`, so the name check in `_precheck` passes. The text read comes from B.

Through `rekindra_recover`, the ZIP is `partial` with `multiple_eocd_candidates`. The evidence item `pack.zip!notes/tide.txt` contains B's text. The size, CRC and flags shown for that entry come from A.

The member caps still apply, so this is not a size or execution problem. The problem is provenance: recovered evidence is quoted from bytes that the inventory beside it doesn't describe. Here, `partial` is the only sign of that.

Reproducer (`python -I repro.py <checkout>`):

```python
import struct, sys, zlib
sys.path.insert(0, sys.argv[1])  # checkout root
from rekindra_intake import inspect_archive, inspect_text
from rekindra_core.zip_text import read_archive_text


def local(name, body):
    return struct.pack('<4sHHHHHIIIHH', b'PK\x03\x04', 20, 0, 0, 0, 0, zlib.crc32(body),
                       len(body), len(body), len(name), 0) + name + body


def central(name, body, offset):
    return struct.pack('<4sHHHHHHIIIHHHHHII', b'PK\x01\x02', 20, 20, 0, 0, 0, 0, zlib.crc32(body),
                       len(body), len(body), len(name), 0, 0, 0, 0, 0, offset) + name


def end(cd_size, cd_offset, comment_len):
    return struct.pack('<4sHHHHIIH', b'PK\x05\x06', 0, 0, 1, 1, cd_size, cd_offset, comment_len)


name = b'notes/tide.txt'
seen, unseen = b'Text in the directory intake inventoried.\n', b'Text from a directory intake never walked.\n'
lh1, cd_a = local(name, seen), central(name, seen, 0)
lh2_at = len(lh1) + len(cd_a) + 22
lh2 = local(name, unseen)
cd_b = central(name, unseen, lh2_at - 100)        # directory B: declared 100 bytes early
tail = lh2 + cd_b + end(len(cd_b), lh2_at + len(lh2) - 100, 0)
data = lh1 + cd_a + end(len(cd_a), len(lh1), len(tail)) + tail   # B hides in A's comment

envelope = inspect_archive(data, 'pack.zip')
out = read_archive_text(envelope, data, inspect_text)
print(envelope['status'], [w['code'] for w in envelope['warnings']])
print([m['intake']['facts']['excerpt'] for m in out['text_members']])
```

Output on Python 3.12.3:

```text
partial ['multiple_eocd_candidates']
['Text from a directory intake never walked.\n']
```

**Proposed fix** (`rekindra_core/zip_text.py`, outside this audit's ownership):

1. Refuse to read members when the envelope warns `multiple_eocd_candidates`. Use a new `ambiguous_archive` refusal code and keep the inventory.
2. In `_precheck`, also compare each `ZipInfo` with its intake entry: `info.CRC` with `claimed_crc32`, `info.compress_size` with `compressed_size_bytes`, `info.file_size` with `claimed_uncompressed_size_bytes`, and `info.compress_type` with `compression_method`. Skip any member that disagrees as `unsafe_member`. This also covers future ways the two readers could diverge.
3. Add the archive above to `tests/test_zip_text.py`.

#### Finding 2: rule 3 is stricter than the code. Low

The rule says to refuse any `partial` archive. The code reads them, on purpose: one damaged note shouldn't cost the rest of the archive. Only `multiple_eocd_candidates` is dangerous (finding 1). `entry_limit_exceeded` is already safe.

**Proposed fix:** after finding 1 is fixed, reword rule 3 to say what is enforced. Flagged entries are skipped (`encrypted`, nested and `suspicious_expansion` entries can never be read), entries past 256 are never paired, and an archive with ambiguous end records is not read. The stale-doc sweep describes today's behavior and points here, but leaves the rule's wording alone, because the wording is a decision about the fix.

## `evidence_summary` size

`handlers.evidence_summary` caps evidence at 6 items of 240 characters. Two fields have no cap:

- **`warnings`** holds warning codes, not messages, and intake keeps one per code. It is bounded by the number of distinct codes: 13 in the worst case below, 279 characters.
- **`text_members`** is the full `text_member_report`: up to 32 `skipped` entries, each with a name of up to 200 characters, a code and a reason.

Measured through the real `rekindra_recover` handler. "Total" is the whole JSON string the tool returns:

| Case | Total | `text_members` | `evidence` | Evidence text starts at | `untrusted_content` at |
|---|---|---|---|---|---|
| Worst case: 40 text members, 40 unread members, flagged names, about 200-character names, a deep path | **15,941** | 9,967 | 4,038 | 981 | 5,129 |
| Reproducer below: the same members, no flagged names | **14,969** | 9,935 | not measured | 761 | 4,189 |
| Photo ZIP: 60 JPEGs and one note | 7,155 | 4,644 | 837 | 720 | 1,666 |
| One short text note | 1,753 | none | 130 | 102 | 926 |

These Hermes numbers come from #15's measurement on the pinned Hermes (`7ab170e`, `docs/response/preview-observations.md` at `e52fbda`). They were not measured again here:

- The per-result threshold drops to 8,000 characters on an 8,000-token context window.
- A longer result is spilled to disk, and the agent sees a preview of the first 1,500 characters.
- A turn budget as low as 16,000 characters can spill even a result under the threshold.

### Finding 3: the summary exceeds the floor, and its spilled preview has no untrusted label. Medium

The worst case is 15,941 characters, almost twice the 8,000 floor. At that floor it is spilled, and its 1,500-character preview starts quoting file text at character 981. `untrusted_content` (5,129) and `guidance` (5,156) both fall outside the preview.

#15 also found that Hermes gives plugin results no untrusted-data wrapper. So an agent on a small model sees quoted archive text with nothing marking it as untrusted. Even the ordinary photo ZIP puts `untrusted_content` at 1,666, so it is cut whenever the turn budget spills it.

Reproducer (`python -I repro.py <checkout>`, Pillow and pypdf not needed):

```python
import importlib.util, io, json, sys, tempfile, zipfile
from pathlib import Path

root = Path(sys.argv[1])  # checkout root
spec = importlib.util.spec_from_file_location('rk', root / '__init__.py', submodule_search_locations=[str(root)])
rk = importlib.util.module_from_spec(spec); sys.modules['rk'] = rk; spec.loader.exec_module(rk)
from rk import handlers
from rk.rekindra_core.projects import ProjectStore

note = 'The harbour bell rang twice at low tide while the ferry waited at the north quay. ' * 4
buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w') as z:
    for i in range(40):                                   # 32 read, 8 hit member_limit
        z.writestr(f'notes/{"long-folder-name-" * 10}{i:02d}/note{i:02d}.txt', note)
    for i in range(40):                                   # unread non-text members, 194-char names
        z.writestr(f'bin/{"x" * 186}{i:03d}.bin', b'\0' * 16)
work = Path(tempfile.mkdtemp())
(work / 'f').mkdir()
(work / 'f' / 'pack.zip').write_bytes(buf.getvalue())
tools = handlers.make_handlers(store_factory=lambda: ProjectStore(work / 's'))
p = json.loads(tools['rekindra_inspect']({'folder': str(work / 'f')}))['result']
raw = tools['rekindra_recover']({'project_id': p['project_id'], 'asset_id': p['assets'][0]['asset_id']})
result = json.loads(raw)['result']
print('reply chars:', len(raw), '| text_members chars:', len(json.dumps(result['text_members'])))
print('first evidence text at', raw.find('"text"'), '| untrusted_content at', raw.find('"untrusted_content"'))
```

Output:

```text
reply chars: 14969 | text_members chars: 9935
first evidence text at 761 | untrusted_content at 4189
```

**Proposed fix** (`handlers.py`, outside this audit's ownership):

1. **Order.** Put `untrusted_content` and a one-sentence form of the guidance before `evidence`, so that every preview carries the label. The full guidance can stay at the end.
2. **Cap `text_members`.** In the summary, replace the report with `read`, counts per skip code, and at most 5 skipped names clipped to 80 characters. The full report is already in the saved intake at `dossier_path`'s directory.
3. **Hard cap.** Keep the whole reply under 7,800 characters, the limit #15 used. Test it with the worst case above.

## `unsupported` handling

`rekindra_core/projects.py:483` drops `facts` and members only when intake status is `rejected`. For `unsupported`, the envelope is passed to the dossier as is. That is safe because:

- **No unsupported envelope carries file content.** All eight `unsupported` returns in `rekindra_intake` give facts that are empty, or only `extension`/`claimed_format`. `read_archive_text` returns an `unsupported` envelope unchanged, with no `text_members`. The PDF reader's `_stop` gives facts of `document_format` plus at most `page_count` and the encryption flag, and empty `text_members`.
- **The dossier quotes nothing for these formats.** Unsupported text and PDF envelopes have format `unknown`, which yields no evidence candidates. An unsupported ZIP has no `entries`.

Probe, through `rekindra_recover`. Each file holds a marker string, and the probe checked for it in every reply and in the saved `evidence.json`:

| File | Intake status | Warning | Evidence items | `content_inspected` | Marker present |
|---|---|---|---|---|---|
| `control.txt` | ok | none | 1 | true | n/a |
| `zip64.zip` (ZIP64 counts) | unsupported | `zip64_unsupported` | 0 | false | no |
| `sfx.zip` (gap before the end record) | unsupported | `prepended_data_unsupported` | 0 | false | no |
| `multi.zip` (disk number 1) | unsupported | `multidisk_unsupported` | 0 | false | no |
| `doc.pdf`, without pypdf | unsupported | `pdf_reader_unavailable` | 0 | false | no |
| `wide.txt` (UTF-32) | not reached | Inspect identifies it as `unknown`, so recover refuses it before intake | n/a | n/a | no |

The final dossier held one evidence item, all from `control.txt`, and the marker appeared nowhere in it.

**Verdict: fine.** Nothing from an unsupported source reaches evidence. This relies on intake never putting content in `unsupported` facts. PR #16's finding 3 adds a guard in `rekindra_evidence` itself: only `ok` and `partial` sources become evidence. That makes this behavior independent of what intake returns. No change to `projects.py` is needed.

## Not covered

- macOS and Linux. All probes ran on Windows.
- The Hermes preview behavior was taken from #15's measurement, not measured again.
- Python versions other than 3.12.3. The two-directory behavior depends on how `zipfile` chooses an end record. This audit checked it on 3.12.3 only; the Linux clean-machine run is the place to repeat it on 3.11 and the newest Python.
