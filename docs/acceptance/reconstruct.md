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

Filled in after the runs.
