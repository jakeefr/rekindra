# color_pattern stripe rejection

Unit: refuse authored color_pattern expressions that render as hard albedo stripes, the B01 failure recorded in `architecture-study.md:21` (`.35+.25*cos(u*80*pi)`). Budget: at most 3 attempts.

Pass condition (program-checkable): `tests/test_color_pattern.py::test_refuses_high_frequency_stripes` rejects the B01 payload and two other high-frequency payloads with a "stripes" SceneError. It still accepts the four low-frequency or low-swing patterns already in use (including `.48+.035*sin(u*170+v*45-t*.85)`), and the full suite stays green.

Attempt 1 (kept): `expressions.sampler` evaluates the compiled AST in Python, using mirrors of the shader's clamped helpers and no eval. `worlds._refuse_stripes` samples 2048 points along u and along v, at v/u = .25, .5 and .75 with t=0. It clamps each sample to ±.35, the same as the shader. An axis whose swing is below .08 is skipped. Otherwise it counts midpoint crossings, and more than 16 cycles is refused. Targeted test: 4 pass. Full suite: 438 pass.

Limitations: the check samples t=0 only and three lines per axis. It does not prove that a pattern stays stripe-free at every time or position. Nyquist means a pattern repeating more than ~1024 times per axis can alias below the threshold, but at those frequencies the renderer averages it out as well. Sharp-edged low-frequency patterns, such as `clamp(.5+2*sin(2*pi*u),0,1)`, are allowed by design.
