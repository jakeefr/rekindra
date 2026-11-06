# Evaluated drafts, not style templates

These native Hermes-authored worlds preserve evaluated drafts from
the concept/material and construction follow-ups. None is accepted as showcase quality. Do not
use them as mandatory templates for unrelated source folders.

- `ruins-evaluated-draft.json`: corpus C02, original plan
  `f9a79ed75bf449c78f7e38da31b42526`.
- `harbor-evaluated-draft.json`: corpus D02, original plan
  `8dde81456a4a4acab478bed06290f691`.
- `harbor-construction-draft.json`: D02 construction follow-up,
  `87f3d2183aea4fefaf90b480fa6cb6b5`; stronger boats, regressed woodland shape.
- `night-city-construction-draft.json`: independent B01 trial,
  `0b298faf362f429eba810c1c78078c8b`; strict repeat-render failure retained.
- `botanical-construction-draft.json`: independent A02 trial with repeated parts,
  `25ebbe51e3b74bf4864766ba72511813`.

To reproduce, build the acceptance corpus, inspect the corresponding folder with
Rekindra, and replace `a` repeated32 times with image_01's project asset ID and
`b` repeated32 times with image_02's ID. Then pass the scene to
rekindra_create_world and preview/export normally. No source photo bytes or model
credentials are included here. Source licensing and hashes are in the corpus
provenance manifest. Invented geometry and action remain explicitly distinguished
from observed source facts.

Review history and known defects: `../concept-quality.md` and `../object-construction.md`.
