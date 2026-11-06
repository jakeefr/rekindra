# Horizontal reflection capability evidence

Original bounded renderer implementation; no external graphics engine or copied source. Windows Chrome development evidence only. Artistic acceptance remains separate.

- Contract RED: optional reflection rejected before implementation. First schema implementation passed its two focused tests.
- GPU RED: reflected red object absent. First renderer implementation passed isolated position/handedness, raised plane, below-plane clipping, bounded blur, moving objects/camera, exact0→3→0, below-camera fallback and resource disposal controls.
- Expanded to13 fixtures including contact depth with omitted/off reflection and a capped reflected object. All passed. Four previous/current omitted/off PNGs, including contact-depth cases, are byte-identical.
- Independent read-only review found Python numeric-underscore syntax accepted while JavaScript produced NaN. Added `1_0` rejection, observed regression RED, constrained decimal syntax. No other production blocker found; requested combined caps/contact and full export evidence added.
- First black diagnostic export reached saved-video readback but failed the existing harness's nonblack center-pixel assumption. Preserved the failure. Ruling: keep isolated black controls unchanged; use a separate integration fixture with a nonblack sky and capped object for the existing full-video harness. No renderer, pixel-repeat threshold, backend or harness change.
- Integration default-browser export passed unchanged strict pixel repeat, intrinsic motion and offline/no-source-pixel checks:12s1280x720 WebM,1,106,924bytes. Preview stayed within the existing45second deadline. Evidence under `.local/planar-reflection/`.
- Additional24-definition stress scene (23 capped animated parts plus reflector, four environment panels and contact depth) previewed in24.83s. Unchanged full browser export passed:6s1280x720,2,585,624bytes. This is a measured Windows workload, not a universal worst-case timing guarantee. Full suites after the height fix:86Python and10Node pass. Root viewed the24-frame decoded integration overview.

Limitations: one horizontal plane, fixed pixel blur, display-encoded offscreen color with inverse transfer before blend, no HDR precision guarantee, recursion, refraction, transparency or curved/vertical mirrors. Cross-platform GPU acceptance remains pending. GitHub Actions jobs currently cannot start because the account billing/spending-limit check fails; no billing settings changed.
