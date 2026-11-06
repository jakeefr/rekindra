# Explicit shot cuts: checked editing capability

Optional camera `cut:true` holds the previous pose until the destination timestamp, jumps at that instant, and resets parallel-transport orientation. Object equations keep global time. Omitted/false keys retain interpolation; first-key cuts and nonbooleans reject. Only an actual cut skips nonexistent interpolation-path crossing checks. Fixed inspection replaces all presentation keys.

RED: Python rejected the new field; runtime interpolated instead of holding and carried previous orientation into new shots. First implementation passed contract and normal/nongrid/closely-spaced cut tests. A later endpoint assertion distinguished negative zero from zero; corrected that test to numerical orientation equality, while pixel repeat stayed exact.

Fresh read-only review found one blocker: for t immediately below23/30, floating-point multiplication rounded t*30 to23, selecting future orientation. Added adjacent-value regression, observed RED, then constrained the cached sample timestamp to be no later than requested t. Single review fix pass; no remaining reviewer findings or deferred minors.

Final89Python+15Node tests pass. GPU frames at10before/exact/after/end/boundary sample times equal independent fixed-camera controls byte-for-byte, including a reflected moving object. Global-time motion and0→4→0 exact repeat pass. Final default-browser export6s1280x720,806,060bytes passes unchanged intrinsic-motion/repeat/export checks;24decoded frames reviewed. Original fixture export before boundary fix is preserved separately. This is an editing mechanism test, not artistic acceptance or continuous collision proof. Evidence `.local/camera-cuts/`.

Private installation/native schema invocation pending until active rain candidate2 finishes, to avoid changing its registered tool contract mid-run. No new cross-platform GPU evidence; current CI cannot start due account billing/spending gate.
