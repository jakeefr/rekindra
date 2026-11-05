# Broad source acceptance

This is a development evaluation, not a claim that Rekindra can recover arbitrary
files or autonomously produce polished work from every folder.

The local corpus contains 16 folders and 65 files. Ten folders contain two sourced
images each (photographs, plus a digitized painting in C02), with constructed notes
and CSV indexes. L01/L02 contain manufactured legacy exports with exact pixel
ground truth. X01/X02 contain deliberate truncation, misleading extensions and
unsupported data. M01/M02 combine sourced images with fictional narrative/game
notes and archive/legacy fragments. No supplied fragment is executed.

| IDs | Intended coverage |
| --- | --- |
| A01, A02 | Sunny coast; sunflower garden |
| B01, B02 | Illuminated night city; cave entrances |
| C01, C02 | Cloud forest; architectural ruins |
| D01, D02 | Rain on glass; rain on roof and marina |
| E01, E02 | Overcast sea; fog and winter trees |
| L01, L02 | Truecolor TGA, raw/RLE, opposite origins, extensionless copies |
| X01, X02 | Damaged pixels/packets, false JPEG, empty image, partial PNG/ZIP, unknown binary, untrusted instructions |
| M01, M02 | Fictional travel journal/archive; abandoned-game design/map/source fragment |

Mood labels are evaluator metadata, not instructions to the native agent. They
describe intended coverage rather than an objective image classification. The
actual photos contain mixed cues: the garden has clouds; the ruined arch photo
has sunlight. No images were recolored to force a mood.

`corpus-provenance.json` records Commons media-page URLs, creator/license metadata,
the downloaded server derivative, sizes and SHA-256 hashes. Each downloaded image
was individually marked CC0 in its media metadata; the license on Commons page
text was not used as evidence for the media license. Re-running search acquisition
can select different images if Commons search changes; this manifest identifies
the specific evaluated corpus. Large source media and raw native logs remain in
`.local`, not Git.

## Reproduction

Run from the repository with the development environment loaded so temporary and
cache writes remain on D: on this Windows host:

```powershell
. ./scripts/dev-environment.ps1
python scripts/build_acceptance_corpus.py --root .local/acceptance-corpus
python scripts/check_acceptance_recovery.py .local/acceptance-corpus
python scripts/summarize_acceptance_runs.py .local/acceptance-runs --compact
```

Recovery evaluation independently decodes the exported PNG scanlines and checks
the expected RGBA hash. It also checks that all eight damaged/unsupported inputs
are rejected as creative image sources. Identification alone is not recovery.
Current recovery result: 16 folders inspected, 65 files, 12 ground-truth recovery
checks, zero failures (four exact recoveries and eight honest rejections).

## Native creative protocol

Fresh Hermes sessions receive `autonomy-brief.txt`, substituting only the selected
folder path. They inspect actual images using native vision, optionally read
bounded text using host tools, author generated worlds, and inspect/critique their
own native previews. No evaluator geometry, palette, camera recipe or previous
scene implementation is supplied. Native vision and text reading are host
assistance; Rekindra does not thereby gain general document/archive parsing.

Keep initial and revised plans. The evaluator reviews returned previews and
decoded exports separately. Successful build, visible motion and artistic quality
are separate outcomes. Source-inspired scenes are new interpretations, not
recovered historic footage or reconstructed original games.

## Discovered loading defect

The first A01 run authored a chair/canvas coastal world, but native previews
failed before returning an image. The agent then attempted a photographic
composition and honestly reported that neither output was visually verified.
This fallback does not satisfy the generated-world goal.

The same unchanged world reproduced the failure outside Hermes: the headless
browser dumped its DOM with only one source loaded, while the second awaited
`Image.decode()`. A load/error event promise, with handlers installed before
assigning `src`, completed in the same browser invocation. The saved regression
command failed before repair and passed three consecutive times after repair.
The fix is commit `cf77c83`; six Node and 47 Python checks passed, with an
independent read-only review finding no important issues. The native agent was
then resumed with a technical repair notice and no scene-specific art direction.

```powershell
python scripts/check_native_preview.py <local path>/home/plugin-data/rekindra/projects 0ffb58025c944f57aff99fe2349d2ca9 b2b35b1b4a034ec88d9f75ad89a63c15
```

The developer session temporarily used `agent.run_budget_seconds: 600` rather
than 120 so the native agent can complete its preview cycle. The installed
gateway rejects the CLI `--run-budget` flag, so the documented config setting was
used. It was restored to 120 after the matrix. This is a model wrap-up budget,
not a proven wall-clock timeout.

All 16 native folder runs finished. See `visual-review.md` and `outcomes.json` for
reviewed results, retries and the unresolved M01 exact-pixel seeking defect.
The matrix is completed evidence collection, not artistic acceptance.
No cross-platform browser success is claimed from this Windows-only live run.
