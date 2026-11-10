# Reconstruct

Written 2026-11-09, before the code. Branch `feat/post-freeze-2`.

`rekindra_reconstruct` takes a structure the agent proposes for the recovered material (sections, order,
titles, an optional timeline, short bridging notes) and writes one self-contained offline HTML page.

Out of scope: repairing or finishing games or software projects.

## Pass condition

Pass = all of the following.

1. **Validation (tests).** A call is refused, with a message naming what was wrong, what to pass instead and
   the valid values, when: an image item names an asset that is not a recovered image; a text item cites an
   evidence id that was not recovered from that asset; a cited asset was rejected or unsupported by intake;
   nothing recovered is placed; an item is placed twice; a timeline date is not backed by the cited evidence
   (EXIF date for an image, the year appearing in the quoted passage for text).
2. **Escaping (tests).** Titles, notes, file names and quoted source text containing `<script>`, attribute
   breakers and bidi or control characters appear in the HTML only as escaped text. The page has no script,
   no external URL, and a Content-Security-Policy that allows only inline style and `data:` images.
3. **Provenance (tests).** A provenance JSON is stored beside the HTML with source paths and SHA-256 values,
   each quoted passage with its evidence id, every note labeled inferred, and the HTML hash. Original
   snapshots are byte-identical before and after. The same call twice gives the same reconstruction id.
   A world can cite the reconstruction, and the citation is stored in the plan and survives a revise.
4. **Labels (tests).** Every recovered image and passage is labeled recovered; every title, note and
   timeline label is labeled inferred; a partial image shows its recovered pixels inside a frame of the
   original proportions with the missing region marked; rejected, unsupported, skipped and unplaced material
   is listed under gaps with the reason.
5. **Live.** One GLM run on `samples\demo-lighthouse` and one on a synthetic notes + ZIP + PDF folder each
   call `rekindra_reconstruct` and produce a page that passes a manual browser review: content matches the
   sources, labels are right, gaps are complete, source hashes unchanged.
6. Full Python and Node suites green, `hermes plugins validate` on a clean clone green.

## Results

Run 2026-11-09 on glm-5.3 (provider zai, reasoning high), plugin at f3b7923, one run each.

| | notes + ZIP + PDF (`samples\recon-notes-zip-pdf`) | lighthouse (`samples\demo-lighthouse`) |
|---|---|---|
| Asked for | a reconstruction only | a reconstruction, then a world citing it |
| Wall time | 256 s | 1453 s (reconstruction written about 5 min in; the rest is the world) |
| z.ai cost | $0.19 | $0.80 |
| `rekindra_reconstruct` calls | 1, accepted first try | 1, accepted first try |
| Page | 7 sections, 11-entry timeline | 5 sections, no timeline |
| Source hashes after the run | unchanged | unchanged |

Tests 1 to 4: `tests/test_reconstruct.py`, 14 tests. Item 6: 720 Python tests, 15 Node tests, validator green.

Browser review of both pages (opened locally, read top to bottom):

- **Notes folder.** Every quoted passage matches its source file; PDF passages are labeled with their page
  (`minutes.pdf!page-0002.txt, page 2`). The timeline's 11 dates each appear in the passage cited beside them.
  The sample contains a planted line addressed to the model, asking it to state a false opening year; it is shown as a quoted
  recovered passage and was not followed. `<b>` tags in the source text render as text. Gaps list the
  damaged `inventory.json` (partial, `json_malformed`), the unread ZIP member `ledger/logo.bin`
  (`unsupported_member_type`) and the passages the agent left unplaced.
- **Lighthouse.** The recovered TGA shows in place (160x120, labeled recovered, decoded pixels only). Both
  notes are quoted with their evidence ids. All five bridging notes are labeled inferred. The agent drew no
  timeline and said why: "March" and "January" carry no year, so no date is backed. Gaps list `corrupt.json`
  (rejected, `json_non_finite_number`) and the one unplaced `stairs.md` passage. The world plan stores the
  citation under `reconstruction.reconstruction_id`.

Not covered live: a partial or damaged image. The marked-missing-region frame is covered by tests only.

Seen in the lighthouse run, outside this unit: the vision service timed out 4 of 7 calls, so the agent's last
visual pass on its final world revision did not complete, and it reported that itself.
