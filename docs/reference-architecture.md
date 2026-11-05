# Reference architecture investigation — 2026-11-05

This is source inspection, not a claim that every linked project has been reverse engineered. No external engine implementation was copied into Rekindra. Source paths below refer to pinned reference checkouts outside the product repository.

## Remotion

Inspected commit `682cad29c569d7c36c2445e27ec07cb433f06b32`, especially `packages/core/src/interpolate.ts`, `packages/core/src/Sequence.tsx`, and `packages/core/src/spring/spring-utils.ts`.

- Interpolation exposes ranges, easing, and explicit extrapolation policies, with validation rather than assuming arbitrary inputs are safe.
- Sequences maintain local and parent timing, enabling coordinated overlapping elements rather than a single global animation preset.
- Spring evaluation includes physical parameters, finite/frame handling and cached calculations. This is an actual timing primitive; sprinkling sine waves on a still does not provide equivalent creative control.
- Implication for our implementation: expose authored transform states over time, evaluate deterministically, and test random-access rendering. We do not need to reproduce React or import Remotion to do that.

Sources: [interpolation](https://github.com/remotion-dev/remotion/blob/682cad29c569d7c36c2445e27ec07cb433f06b32/packages/core/src/interpolate.ts), [sequences](https://github.com/remotion-dev/remotion/blob/682cad29c569d7c36c2445e27ec07cb433f06b32/packages/core/src/Sequence.tsx), [springs](https://github.com/remotion-dev/remotion/blob/682cad29c569d7c36c2445e27ec07cb433f06b32/packages/core/src/spring/spring-utils.ts).

## HyperFrames

Inspected commit `898d0fb00b3d8a9dbe637c8a5df2423c9556ace1`, especially `packages/core/src/runtime/player.ts`, `packages/core/scripts/test-hyperframe-runtime-seek.ts`, and `packages/engine/src/services/riskFrameCapture.test.ts`.

- The player distinguishes canonical frame-quantized seeking from exact seeking and coordinates sibling timelines.
- Seek tests check adapter behavior and same-time re-rendering, not just whether the UI playhead moves.
- The risk-frame test refuses a capture path before touching the page when a frame is known unsuitable, avoiding silently shipping damaged frames.
- Implication: preview and export must share one clock/evaluator. Random-order frame checks and actual video decoding belong in acceptance. Capture success alone does not establish visual quality.

Sources: [runtime player](https://github.com/heygen-com/hyperframes/blob/898d0fb00b3d8a9dbe637c8a5df2423c9556ace1/packages/core/src/runtime/player.ts), [seek tests](https://github.com/heygen-com/hyperframes/blob/898d0fb00b3d8a9dbe637c8a5df2423c9556ace1/packages/core/scripts/test-hyperframe-runtime-seek.ts), [capture tests](https://github.com/heygen-com/hyperframes/blob/898d0fb00b3d8a9dbe637c8a5df2423c9556ace1/packages/engine/src/services/riskFrameCapture.test.ts).

## REA

Inspected commit `71f680d7c1aa7a45ba0325fe87b104744b0c105f`, README, `src/application/WorkflowEvidence.ts`, and `src/cli/javascriptApplicationAnalysis.ts`.

REA is an analysis toolkit, not a video renderer. Its evidence workflow retains source links, limitations, and partial results. JavaScript analysis owns and closes worker resources explicitly. For open-source animation engines, direct source inspection is the simpler initial method; no binary decompiler is needed. We have not installed or run REA, and have not decompiled a proprietary application.

Implication for recovery: keep observed facts and generated interpretations separate; retain what failed and what remains unknown. For our present visual problem, REA is not the missing animation engine.

Sources: [REA](https://github.com/morluto/rea), [evidence workflow](https://github.com/morluto/rea/blob/71f680d7c1aa7a45ba0325fe87b104744b0c105f/src/application/WorkflowEvidence.ts), [JavaScript analysis lifecycle](https://github.com/morluto/rea/blob/71f680d7c1aa7a45ba0325fe87b104744b0c105f/src/cli/javascriptApplicationAnalysis.ts).

## Where the first Rekindra demo failed

Our original schema allowed only image, text and particles plus five small preset motions. The prompt explicitly encouraged sparse poetic text and subtle effects. The test image was crude synthetic material. Automated checks only established that frames differed and the video decoded. None of that established a compelling visual transformation.

Immediate response: enforce text opt-in, introduce explicit transform tracks and independent source fragments, and inspect a complete motion study. Next research should cover scene transitions, image masks/segmentation, camera composition, temporal visual critique, and the remaining user-provided projects (GSAP, Three.js, Blender, ComfyUI, Hallmark, Impeccable and others). Those have NOT received the same source-level inspection in this pass.

The five-day target remains a scope constraint. Rebuilding all of Remotion, Blender, or a generative video model is outside it. A distinctive, bounded creation workflow with convincing outputs is the achievable target; breadth must follow evidence.
