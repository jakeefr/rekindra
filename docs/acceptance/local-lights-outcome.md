# Local lights and structural trial outcome

Original implementation adds up to four static world-space point lights with bounded position, color, intensity and range. Receivers use the existing GGX material response with softened inverse-square attenuation and smooth range cutoff. No external engine was introduced. These lights are unshadowed and can leak through walls; they do not follow assemblies or turn emissive meshes into automatic lights. Omitted/empty light lists retain the legacy path.

Checks: observed Python RED for unsupported field, browser RED for dark receiver; then 75 Python and 10 Node tests passed. Actual browser receiver samples: near red238/green43, distant red45/green6, outside range black. Zero intensity equals omitted. Four intensity1 lights equal one intensity4 light; the fourth alone equals the first; a metallic receiver has a nonzero specular response. Root inspected the lit receiver image. Independent code review found no concrete defect; finite coincident-source math was inspected, while the browser's alpha check only establishes coverage. CI run42169441520 never started any of its six job steps; no new macOS/Linux pass is claimed.

## Native structural unit: closed after three submissions

The agent proposed a split rib vault revealing a lantern court, replacing the earlier paired slabs. Its local prevalidation included four lights. Root incorrectly updated installed files without restarting the existing gateway. That gateway retained old registered schemas/Python modules, while renderer JavaScript was read fresh from disk.

1. Gateway rejected create input containing `point_lights` before a stream tool event was emitted.
2. Agent omitted lights and saved `e05635ff854644648a773df599ba21e1`. Root reviewed both native preview sheets. A more dimensional structure, but small, cage-like, broad-lit, and approached by a floating-looking plank. Full browser export passed at 18 seconds/4,550,086 bytes; this is not evidence of local lights.
3. A structural revision restoring the lights was rejected by the loaded validator. No saved revised plan existed. The native ledger also notes differences between its rejected submission and local draft; no exact-payload claim applies to that failed call.

The unit is closed, not silently reset. The direct stream summary undercounts gateway rejections; the native `review-ledger.json` records all three. The integration plan was wrong: fresh files and a fresh CLI did not imply a fresh gateway. The internal development notes now document live-runtime verification.

## One bounded integration recovery

After native work ended, root identified/restarted the stale gateway (old PID29504). A separate one-submission integration check applied the already-authored `revision.json` exactly; no new creative retry was authorized in that check. Native saved plan `92b963de3e114ff6ae6bdbac4e292974`. Native and root independently verified full scene equality with `revised-scene.json`, four saved point lights and original source hashes. Both normal and stationary previews were inspected by the native agent and root.

Root's same-frame light on/off diagnostic found56,797 pixels with summed RGB difference greater than3; maximum summed difference459. This is aggregate illumination evidence, not a visual-quality score or proof that four individual sources are perceptually distinct. Root's full default-browser check passed: 18 seconds,1280x720,6,628,700 bytes, exact repeat-seek, fixed-camera visual motion, offline behavior, cancellation, corruption rejection and export/decode. Root inspected24 decoded samples. Earlier intermittent GPU repeat failures remain a separate unresolved issue.

The recovered scene has stronger faceted ribs, a taller destination and visible warm/cool illumination on surfaces. It is an improved checkpoint, **not showcase acceptance**. Right-hand ribs overlap almost edge-on late in the presentation; the plain approach and empty hillside still read as a model; pivot interfaces remain visually weak. Sampling does not prove collision freedom. Next work should address projected separation, grounded approach detail and material hierarchy before adding decorative geometry.

All artifacts remain local and the repository remains private. Audio, intake ownership and public catalog integration were untouched. The temporary native run budget was restored to120 seconds. Evidence: `.local/local-lights/`, `.local/structural-lights/`, and `<local path>/home/cache/scratch/vesper-vault/{review-ledger.json,recovery-review.json}`.
