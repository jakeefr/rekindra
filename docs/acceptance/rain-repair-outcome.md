# Rain construction repair outcome

User explicitly authorized a revised plan after the prior study's failed visual verdict. Scope: repair diagnosed edge artifacts and support overhang, retain prior artifacts and review the resulting video. No renderer code or test tolerances changed; shadows remain enabled.

## Controls and causal evidence

Identical10.8second camera controls removed outlet liner, rails, shell, main support and shoe independently. Removing the main support removed the brown projection; removing only the shoe did not. Disabling contact occlusion did not resolve the dashes. Disabling shadows diagnostically removed dark dashes, but left a thin line. Single-layer32segment control is clean, while double-layer64segment outlet control retains dark edge marks: extra tessellation alone is not the solution. The line was separately traced to the inactive streak's constant .002radius.

Diagnostic correction: first no-contact/no-shadow controls used nonexistent environment fields and were invalid; do not count them as evidence. Replaced contact field with occlusion_strength and used an explicit diagnostic-only shadow function override. A proposed all-shell64segment control exceeded4M work and was rejected; isolated outlet64 control passed. These are controls, not accepted creative versions, and no budget was relaxed.

## Three repair attempts

1. Smooth thick cross-section plus shortened support: projection improved, layered edge artifacts remained; not selected.
2. Single coated solid, denser cross-section and smaller bracket: edge dashes disappeared but bracket shifted too far forward and penetrated the channel; rejected.
3. Retained single solid, restored bracket depth with inward lateral fit, removed dormant streak radius: selected. Previous attempts and controls preserved in .local/rain-repair.

Fixed-camera support ROI[690,280,742,340] at1214x684: warm support pixels262before,0after. This confirms that specific projected overhang only, not all-angle collision freedom. Original payload hash unchanged. Camera and assembly exactly unchanged; original channel centerline and width bindings preserved. Dormant whole-length radius reduced .002to0. Original schema and work budgets pass.

## Native and encoded checks

Actual exposed Hermes create once, plan5419e28867164a33b25bd685506ad5b0 in projectb666b25007704a3abf24309c1f1aaf15. Root verified exact saved/intended scene equality. Native normal and fixed inspection previews completed and were viewed. Root reviewed fixed inspection and24decoded samples of the actual native HTML's export.

Full16second1280x720WebM,8,125,070bytes. Default browser motion, exact repeated pixels, playback/seek, cancellation, integrity and no-network checks pass. Root viewed full-size transfer comparison and decoded ending sheet. The diagnosed dark dashes, premature wire and brown projection are removed in the inspected transfer view. Export preserves coherent gathering, pivot, docking, descent and reveal.

Remaining limits: the deliberate docking seam is visible; narrow outlet termination still deserves a more finished design. No claim of continuous collision proof, watertight geometry, physical fluid simulation, cross-platform GPU verification or impeccable overall artistic quality. This repair addresses the named construction defects; it does not establish that arbitrary folders produce showcase-level results. All work remains private.

Reusable example: examples/worlds/rain-switch-repaired.json (portable placeholder reference IDs). General construction diagnosis and recipe added to world-authoring.md and RULES.md. No intake files or external rendering engines changed.
