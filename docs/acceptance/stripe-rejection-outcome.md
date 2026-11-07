# color_pattern stripe rejection

Unit: refuse authored color_pattern expressions that render as hard albedo stripes, the B01 failure recorded in `architecture-study.md:21` (`.35+.25*cos(u*80*pi)`). Budget: at most 3 attempts.

Pass condition (program-checkable): `tests/test_color_pattern.py::test_refuses_high_frequency_stripes` rejects the B01 payload and two other high-frequency payloads with a "stripes" SceneError. It still accepts the four low-frequency or low-swing patterns already in use (including `.48+.035*sin(u*170+v*45-t*.85)`), and the full suite stays green.

Attempt 1 (superseded): `expressions.sampler` evaluates the compiled AST in Python, using mirrors of the shader's clamped helpers and no eval. `worlds._refuse_stripes` sampled 2048 points along u and along v, at v/u = .25, .5 and .75 with t=0, and counted midpoint crossings. Its pass condition held (4 targeted, 438 full). Review (roborev 5345) then found the samples were clamped to ±.35, which is the color_detail range. The renderer clamps color_pattern to 0..1 (`runtime/world.js:333`, patternBlend). So bands sitting above .35, such as `.5+.1*cos(u*80*pi)`, went unchecked, and patterns lying entirely below 0, which render flat, were refused. It also sampled t=0 only.

Attempt 2 (kept): samples are clamped to 0..1, matching patternBlend. t is sampled at 0, 1 and 7.3. An axis whose swing is below .08 is skipped. A pattern is refused when it has more than 32 midpoint crossings (16 cycles), and the message reports the same quantity. Added refusals for `.5+.1*cos(u*80*pi)`, `.7+.2*sin(u*200)` and `.5+.4*sin(u*200*t)`. Added acceptances for `-.4+.2*sin(u*200)` and `1.5+.3*sin(v*300)`, which render flat. Targeted test: 4 pass. Full suite: 438 pass.

Limitations: the check samples t at 0, 1 and 7.3 and three lines per axis. It does not prove that a pattern stays stripe-free at every time or position. Nyquist means a pattern repeating more than ~1024 times per axis can alias below the threshold, but at those frequencies the renderer averages it out as well. Sharp-edged low-frequency patterns, such as `clamp(.5+2*sin(2*pi*u),0,1)`, are allowed by design.
