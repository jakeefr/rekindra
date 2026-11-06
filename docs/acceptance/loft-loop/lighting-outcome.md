# Full-timeline motion checks and lighting isolation

Motion test fixed in `a3dec0d`: 24 decoded-pixel samples across the timeline replace the two early-frame motion assertion. A separate stationary-camera probe checks non-camera visual change. Unit regressions accept a delayed opening, reject frozen/camera-only fixtures and restore camera state after a capture exception. The exact same-time pixel repeatability assertion remains unchanged. A fresh reviewer found a stale-time ASCII comparison; rendering a presentation frame immediately before toggling ASCII fixes it. Finite sampling can miss brief/aliased movement, and visual change includes material animation, not only geometry.

Validation: 73 Python tests and 10 Node tests passed. Final full default-browser run on baseline `a2dead12c47c4420bd14ab7142271ad1` passed with an 18-second, 1280x720, 6,055,814-byte export. Offline requests, cancellation, corrupt-source rejection, repeat-seek and decode checks all ran. This single default pass does not establish that the previously intermittent hardware issue is fixed.

## Three lighting/composition attempts

Native Hermes revised the retained night study using only camera, environment and materials. Code compared all other scene data and original source hashes for every candidate. All three preserve geometry, assemblies and source observations. Each received normal and stationary native previews and vision review. No new geometry, third-party renderer or public action was introduced.

1. `d0644fc51c3d4a2781c893302a4820a6`: closer framing, deeper blue environment and warmer focal faces. Root retains this as the lighting checkpoint: it has the strongest subject/background separation and night mood. Dark supporting geometry remains a limitation.
2. `d0a82db5d63a4653853972c4b9399cbf`: cooler, more legible supporting planes; contrast is weaker. Useful comparison, not root's preferred presentation.
3. `260e11715f7348c58d6c7c14b2fa0cd9`: brighter, more evenly readable geometry. Root rejects it as the presentation checkpoint because it returns toward the washed-out maquette look. Newest is not automatically best.

Root inspected all three normal preview sheets, stationary sheets for candidates two and three, and 24 decoded samples of candidate one. Candidate one passed the full default-browser gate: 18 seconds, 1280x720, 7,138,398 bytes. Evidence is in `.local/night-lighting/{scope.json,motion-final/,candidate1/,candidate1/decoded/}`; all media stays private and untracked.

Visual verdict: better composition and light separation, still not showcase quality. The broad leaf slabs, proud strips, sparse backdrop and simple reveal remain schematic. Lighting alone cannot supply missing structural design. Close this bounded three-attempt unit rather than restart its counter. Next construction work should replace the slab-based focal design and improve the revealed destination, using the retained contrast as a baseline. Local illumination is also absent: emissive material currently brightens itself but does not illuminate adjacent surfaces; do not claim luminous strips cast light.

The native agent preferred candidate two for support legibility. Root also exported and reviewed its 24 decoded samples: the full default-browser gate passed at 6,995,192 bytes. Root still prefers candidate one's contrast for the presentation checkpoint; both remain preserved. This is an aesthetic judgment, not a numerical quality claim. One additional local prevalidation draft before submission three rejected `sun_size=.16` (maximum .15); corrected before its native submission and recorded in the attempt ledger. Native ended successfully; temporary run budget restored to 120 seconds.

No threshold relaxation, production shader change, intake edits or public publication occurred in this unit. Cross-platform CI remains subject to the previously recorded account billing block; these browser results are local Windows evidence.
