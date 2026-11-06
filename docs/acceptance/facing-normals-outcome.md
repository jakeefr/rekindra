# Grazing normal correction

Cause: flipping interpolated normals with dot(N,V) creates sign discontinuities inside grazing visible triangles. Horizon streaks persisted with shadows/contact disabled and disappeared with flat normals. Renderer-only diagnostic copies preserved all native scenes.

Three implementation attempts, including diagnostics:

1. Winding-only orientation: removed horizon streaks but inverted derivative cap normals. Rejected without installation.
2. Geometric derivative hemisphere: new above/below smooth-sheet test improved24,320/25,050 inverted pixels to zero; flat controls/repeat passed. Independent review found mirrored-camera handedness reverses derivative orientation. Existing reflection fixtures used emission and could not detect this.
3. Face geometric derivative toward the current pass eye, then orient the shading normal against it; retain view fallback for degenerate derivatives. New non-emissive smooth/flat/cap mirror regression went from black reflected samples to red203, matching direct203. All sheet orientation and exact-repeat checks pass. No further attempt needed.

One invocation omitted existing fixture arguments; one new mirror fixture omitted required raw position metadata. Both harness failures preserved and corrected before measuring production behavior. They are not passing renderer evidence.

Final integration: caps, flat, shadows, relief, planar reflection, contact depth and environment panels GPU controls pass.86Python+10Node tests pass. Unchanged selected forest scene rendered with new runtime in a separate regression HTML:14s1280x720,6,923,565byte export; exact repeat/intrinsic motion gates unchanged.24decoded frames reviewed. Source scene/old artifacts unchanged. This fixes a rendering artifact; it does not certify scene artistry or eliminate cusps/undersampling. Current GPU evidence Windows Chrome only; CI billing gate remains outside task scope.

Final review: fresh read-only reviewer found mirrored handedness; covered with failing test then fixed in the single review fix pass. No deferred reviewer minors. Ruling: do not reinterpret this renderer regression as another native creative submission.
