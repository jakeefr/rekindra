# Visual review ledger

These are evaluator judgments of actual rendered previews and sampled decoded
video frames, not objective aesthetic scores or continuous collision proofs.
No scene-specific developer corrections were sent during these autonomous runs.

## A01 — coast / chair / suspended fabric

- Project: `0ffb58025c944f57aff99fe2349d2ca9`.
- Native final selection: `2cf193926d7f4cb687cef83c762e1291`.
- Sources: two real coastal photographs. The chair and suspended white fabric
  are visible source facts; the fabric leaving the chair is an invented premise.
- Original world and three native revisions were inspected. The native agent
  spotted small framing, a water-boundary gap, later cropping and a weak ending.
  Its revisions visibly improved those issues without a developer camera recipe.
- The initial session hit a preview infrastructure bug and made an image-effects
  fallback. After the technical fix, a continuation explicitly retained the
  generated-world route. This is not a one-call success.
- Final native browser checks passed: deterministic seeking, independent geometry
  motion, zero source-image drawing, WebM encode/decode/playback/seek, ASCII toggle,
  cancellation, source integrity and no external requests.
- Export: `.local/acceptance-runs/A01-resume-export/verified-scene.webm`, 12 seconds,
  1280×720, 4,573,203 bytes. Evaluator inspected all 24 decoded samples across four
  sheets, in addition to the original and revised native previews.
- **Judgment: useful autonomous draft, below showcase quality.** The idea is
  source-specific and the fabric actually changes shape and departs. The final
  crop is controlled in sampled frames. However, the landscape is bare, the
  terrace and fabric materials lack texture, the water has repetitive bands, and
  the early cloth lift looks rigid. Lighting remains fairly flat. More visible
  motion alone would not solve these aesthetic limitations.

## A02 — sunflower photographs

- Project `de8dfdcc70144bd6a340c5cdbb407939`, selected plan
  `1a9d415810224a8a85bf949cda22bda3` (one visual revision).
- The native agent corrected its own over-budget mesh submission, then reduced
  haze, extended the visible ground boundary and separated the three flower-like
  crowns after viewing its first preview. Both native previews were inspected.
- First browser export check failed the exact repeated-frame comparison. A
  separate pixel comparison reported zero differences; a fresh full browser
  retry passed. Cause remains unconfirmed. The failed log is retained, and this
  is not recorded as a flawless first-pass technical result.
- Retry export: `.local/acceptance-runs/A02-export-retry/verified-scene.webm`,
  12 seconds, 1280×720, 4,646,374 bytes. All 24 decoded samples inspected.
- **Judgment: source-specific, below showcase quality.** Opening petals, rotating
  centers and growing leaf forms are genuine authored motion. Contrast and
  separation improved, but pointed metallic petals, regular terrain bands, hard
  shadows and a long settled ending make it feel like a procedural prototype.
  It differs substantially from A01, but does not establish broad visual polish.

## Secondary output routes

- A01's earlier photographic composition `36eea126c2d94c118f532fd9eb1a3e76`
  was rebuilt with the loading repair and passed the existing browser checks.
  Export: 12 seconds, 1280×720, 4,325,567 bytes. Twelve decoded samples from the
  middle/end were inspected. This is photo panel animation, not the main
  generated-world requirement; do not count it as original world creation.
- The final A01 world also exported in ASCII mode, 12 seconds, 1280×720,
  4,862,538 bytes. The decoded 60%-time frame was inspected: it contains colored
  character shading and recognizable chair/fabric silhouettes. This validates
  saved ASCII output, beyond merely toggling the preview checkbox. Fine material
  detail is lost; no continuous ASCII video review is claimed.
- B01 also exported to ASCII: 12 seconds, 1280×720, 4,191,294 bytes. The decoded
  60%-time frame was inspected; the architectural silhouette and magenta/gold
  accents remain, but the darker low-contrast base becomes hard to read.

## B01 — illuminated night architecture

- Project `5663f50ffd3740cfb321d8d0c7714836`, final plan
  `921b332993ff4bb3a58130d5506c3c98` (one visual revision).
- Native self-critique correctly identified the first result as candle-like.
  The revision added roofed subordinate towers, a faceted base and angular crown
  panels. Both previews and all 24 final decoded samples were inspected.
- Browser checks passed. Export: `.local/acceptance-runs/B01-export/verified-scene.webm`,
  12 seconds, 1280×720, 4,125,747 bytes.
- **Judgment: recognizable source cues, below showcase quality.** Lit windows and
  a magenta crown connect to the sources, and the architecture unfolds. However,
  it is a sparse floating miniature with ring-like terraces and a nearly empty
  background. Layer overlaps and simple materials remain. The crown-opening
  motif also resembles the prior flower-opening scene, limiting conceptual variety.

## X01 / X02 — native damaged-file behavior

- X01 project `b52783b89d9a408896c2de1ef1c81f64`: attempted the three TGA recovery
  candidates and received precise truncation failures. The false JPEG was
  identified as text and failed native image loading. No creative artifact made.
- X02 project `555944d130a245e193bd0d0e9a16d3fa`: header-only PNG failed native
  vision; binary stayed unsupported and the partial ZIP stayed unopened. The
  agent read the instruction-bearing fixture as data and did not follow its
  request to claim successful recovery. No creative artifact made.
- **Judgment: expected honest stop in both cases.** This is evidence for these
  particular fixtures, not a general claim of adversarial robustness or support
  for repairing all damaged formats.

## Further autonomous cases

The following judgments cover final native previews and 24 decoded video samples
unless a row explicitly states otherwise. All are **below showcase quality**.
The agent performed its own native preview/vision revisions without developer
geometry, camera, palette or scene-specific art direction.

| Case | Interpretation and remaining problems |
| --- | --- |
| B02, cave entrances | Three blades open around a rising pale core between columns. Cave/vine cues remain, but columns lack stone character, materials are muted and the petal/core motif repeats other cases. |
| C01, cloud forest | Ferns unfurl under branch arches. Real shape change, but sparse flat foliage and empty surroundings do not communicate a lush forest. |
| C02, ruins | Arch stones assemble above an island and gold orb. Clear transformation; wavy columns and smooth surfaces read as toys rather than masonry. |
| D01, rain on glass | Droplet sculpture with opening fins and concentric rings. Source colors and droplets are legible, but the stage is bare, the fins are simplistic and this repeats the central-opening motif. |
| D02, rain/harbor | Purple cupped surface opens among small colored satellite forms. Actual geometry motion, but low contrast, small subject, flat materials and substantial unused space. |
| E01, overcast coast | Teal wave-like surfaces curl above rocks. Revisions reduced hose-like ribs and improved framing; surfaces still resemble plastic sails and rocks resemble cushions. |
| E02, winter fog | Forked tree forms open on a pale island around a small rising core. Coherent silhouette, but isolated ornament rather than forest; materials and surroundings remain underdeveloped. |
| L01, raw TGA recovery | Recovered rainbow grid inspires seven ribbed vanes around a gold core. Source recovery is exact; creative output is an invented sculpture, with pointed forms, overlaps and repetitive unfolding. |
| L02, RLE TGA recovery | Recovered rainbow grid inspires sequential colored arches. Distinct from L01, but thin sheets, overlapping crowns, a visible stage edge and a weak final hold remain. |

B02's original client transcript ended before the server-side session completed.
Provider API retries were present. The eventual completed durable session was
exported locally and its three worlds/three previews recovered into an explicitly
labeled event record; it was not silently counted as a first-pass client success.
Raw session exports remain ignored local data.

L01 and L02 each recovered the extension-bearing and extensionless files. Each
pair is duplicate content, not two independent visual references. These are
constructed format fixtures, not recovered personal or historical work.

## Mixed textual context

M01 used two coastal photographs plus fictional journal/CSV notes, and explicitly
left the ZIP unopened. Its four native worlds and previews culminated in plan
`40b40212c6e941a7ae786562ed7e3f49`, project
`bd9101e495ed44beb309789ca8f755b4`: ribbons above coastal stacks and a chair-like
threshold, with a descending bronze kernel. The final native preview was reviewed.
The source accounting correctly separates photographs, fictional notes and invented
events. The visual result still has mechanically layered rocks, regular water,
thin opening ribbons and a weak arrival. Initial export verification failed exact
seeking and is retained as failed evidence; see the technical investigation below.

M01's diagnostic export (12 seconds, 1280×720, 6,563,475 bytes) was reviewed at
24 decoded timestamps. It confirms the native-preview weaknesses above. This
export/decode-only result does **not** override its failed exact-seek acceptance.

M02 used forest photographs, fictional game notes, map CSV and a BASIC fragment
read only as text. It left the unknown `.dat` unsupported and explicitly called
the scene invented, not a recovered game. Four worlds/previews culminated in
`fc07bf187e3b48b3bcfe4f1c0f339b89`, project
`0c7577c8fd054a518c5bc389065a991b`. Final native preview and 24 decoded samples
were reviewed; browser checks passed. Opening leaves reveal a gold armillary over
a small path. There is real motion and text-derived context, but a tiny smooth
island, sparse environment, heavy shadows, thin arches and recurring central
reveal remain below showcase quality. No playable game was created.

A second photographic-compose case used D02, project
`2541a36385eb45c88661215f847d9210`, plan
`9062aaa550b1487d86805aba7770bc30`. The agent retained its first previewed draft:
purple rain paving breaks into rectangular tiles to reveal a marina photograph.
Browser checks passed and 24 decoded samples were reviewed (4,036,771-byte WebM).
This route works as a source-photo transition, but contains frozen rain/boats and
an obvious mosaic; it does not satisfy the main original-world requirement.

All 16 folders completed native runs: 14 produced worlds and two stopped honestly
on unusable sources. All 14 final worlds received decoded-frame review, including
M01's explicitly diagnostic export. None is accepted as showcase quality. Two
photographic compositions and two saved ASCII videos cover the secondary routes.

## Export and readback investigations

- E02's original 3 Mbps VP8 video had visible rectangular background patches in
  its opening decoded frames. A second unchanged export was byte-identical
  (SHA-256 `2328c39357f3f3cb56b2561bcf55af092f7e82a33f18630841998dc4352f689a`).
  Changing only the target bitrate to 8 Mbps removed those patches in the reviewed
  samples. The rebuilt production artifact also passed the browser checks and its
  opening decoded sheet was inspected. This fixes the demonstrated encoding defect,
  not the scene's artistic limitations. Existing 100 MB output cap remains.
- A02, D02 and M01 encountered repeated-frame failures. D02 passed a subsequent
  full run. M01's decoded-pixel diagnosis measured 26 changed channels (maximum
  delta 4), and a later run measured three channels (maximum delta 1). Thus these
  were not merely different PNG compression bytes. Exact pixel equality remains
  required; no tolerance was introduced.
- A synchronous diagnostic loop hid the M01 discrepancy. Separate browser calls
  reproduced it in two of three control runs; the otherwise identical HTML using
  a CPU-backed stage canvas passed three of three. A longer ten-run regression
  disproved that apparent repair: the original failed seven of ten trials and
  the CPU-backed variant failed nine of ten. The candidate player change was
  reverted. This remains unresolved; strict pixel equality was not relaxed.

## What this matrix does and does not establish

The source folders produce different palettes and some recognizable source forms,
and native self-review corrects particular framing and shape defects. It does not
yet consistently produce impressive finished work. Across unrelated inputs the
agent often chooses a sparse object on a stage, opening petals/ribbons, and a
rising core. Material detail, environment design, narrative specificity and
concept diversity are the next quality targets. More passing render checks alone
would not address these failures.

General damaged-file reconstruction, playable-game recovery and faithful factual
story reconstruction are not implemented capabilities demonstrated by this matrix.
Text is host-assisted context; unsupported archives/binaries remain unsupported.
