# ASCII mode: pass condition and outcome

## Pass condition (written before implementation)

The ASCII view passes when every item below is checked against evidence.

1. **Detail.** The character grid is at least 180 columns for a 1280x720 frame, with the row count chosen so each cell covers the same picture area it is drawn into (no stretch). The glyph ramp has at least 24 levels ordered by ink coverage.
2. **Two modes.** `color`: each character is drawn in the scene colour at that cell. `mono`: light characters on black, no scene colour. The player has a control that switches between them and redraws immediately.
3. **Player and export.** The mode chosen in the player is the mode of the saved video. `scripts/export_ascii.cjs` can save an ASCII video in either mode (`--mono` selects black-and-white).
4. **Deterministic.** Character and colour selection is a pure function of the frame pixels: no random numbers, no clock. Rendering the same time twice gives identical canvas pixels.
5. **Tests.** `node --test tests/test_ascii.cjs` passes and covers determinism, ramp ordering, grid size, colour versus mono, and edge glyphs. The existing Node tests still pass.
6. **No captions.** Nothing is drawn over the scene except the character grid itself.
7. **Recognisable lighthouse.** Frames decoded from exported video of the lighthouse scene, in both modes and at two or more times, are viewed by the reviewer. In each, the lighthouse tower must be identifiable as a lighthouse without the normal render beside it. A normal render of the same moment is saved for comparison.

Item 7 is a human-style visual judgement by the implementing reviewer, not an automated measure. It is not artistic acceptance of the scene itself.

## Outcome

Checked 2026-11-09 against the working tree on `feat/post-freeze-2`. Scene used: the lighthouse scene "North Point Light at First Beam" (schema 2, 16 s), rebuilt into a player with the working-tree runtime. Evidence files are under `<local path>\logs\pf2-ascii\`.

### What the earlier view did

110 x 34 characters, a 10-glyph ramp (`' .:-=+*#%@'`), one bilinear downscale of the frame by about 11x (thin shapes dropped out), linear luminance with no contrast handling, no outlines, colour only, and a new sampling canvas on every frame.

### Final design

| Setting | Value |
| --- | --- |
| Grid | 200 x 60 on 1280x720 (cell 6.4 x 12 px, aspect 1.875) |
| Sampling | 2x supersample (400 x 120), then block average per cell |
| Ramp (32 levels) | `' .:~;=+*cvstxneoakhSAm#H8WMB0N&@'` |
| Luminance | Rec. 709, gamma 0.8 |
| Frame contrast | stretch between the 2nd and 98th percentile, gain capped at 3, flat frame unchanged |
| Outlines | Sobel on the toned luminance, threshold 0.6, one glyph per crossing on the darker side: `\|` `/` `-` `\` |
| `color` | glyph takes the cell colour, hue kept, dark cells lifted (exponent 0.45, floor 0.32), background `#05080a` |
| `mono` | uniform `rgb(236,240,236)` glyphs on `#000` |
| Font | bold, Consolas-first monospace stack |

Ordered dithering was tried and removed: it added texture noise without making shapes clearer.

### Items

1. **Detail: pass.** 200 columns x 60 rows; 32-level ramp. Checked by `tests/test_ascii.cjs`.
2. **Two modes: pass.** `asciiCells(..., 'color' | 'mono')`; the player has an "ASCII color" checkbox next to "ASCII" (unchecked means black-and-white) and redraws on change.
3. **Player and export: pass.** The player export captures the mode when the export starts. `scripts/export_ascii.cjs` saved `export\ascii-scene.webm` (colour, 19,306,281 bytes) and, with `--mono`, `export\ascii-mono-scene.webm` (20,675,262 bytes); both 1280x720, 16 s. `--standard` saved `export\diagnostic-scene.webm` for comparison.
4. **Deterministic: pass.** No random or clock calls in the ASCII source section (asserted by test). Canvas stills at t = 3.2, 7.2, 11.2 and 14.72 s were each rendered twice per mode and were pixel-identical (`stills.json`).
5. **Tests: pass.** `node --test` over the four existing files plus `tests/test_ascii.cjs`: 22 pass, 0 fail (15 existing, 7 new).
6. **No captions: pass.** Only the character grid is drawn.
7. **Recognisable lighthouse: pass in both modes.** Viewed: `export\decoded-ascii-scene-early.png` and `export\decoded-ascii-scene.png` (colour, 25% and 60% of the video), `export\decoded-ascii-mono-scene-early.png` and `export\decoded-ascii-mono-scene.png` (mono), with `export\decoded-diagnostic-scene-early.png` and `export\decoded-diagnostic-scene.png` as the normal render. In all four ASCII frames the tapered tower, its alternating bands, the lit lamp room, the pointed cap and the island base read as a lighthouse on their own; the beam and the second island are also visible in the early frames. Colour mode is the clearer of the two because the warm sky separates from the tower. Mono relies on glyph density and outlines alone and is a little busier in the sky, but the tower is still plain.

Second review of the 60% frames in both modes against the normal render: the tower, bands, lamp room, cap and island read as a lighthouse in each. The bright sky is a dense, busy glyph field in both modes, the far headland on the left is lost in mono, and colour mode is muted because the scene itself is a narrow warm palette.

### Limits

- `scripts/browser_scene_test.cjs` stops at its "Seeking changed rendered pixels" check before it reaches ASCII. It fails the same way, with the same pixel count, on a player built on 2026-11-05 with the earlier runtime, so it is not caused by this change; it is open and was not investigated here.

- The red and grey tower bands differ mainly in hue, so in mono they separate less strongly than in the normal render.
- ASCII video files are about five times larger than the normal export at the same bitrate setting, because dense glyph texture compresses poorly.
- Glyph shapes come from the viewer's installed monospace font; the character grid is deterministic, exact pixels can differ between machines with different fonts.
