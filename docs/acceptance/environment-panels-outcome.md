# Environment-panel capability outcome

UNIT: bounded original environment lighting. VERDICT: technical pass; artistic impact requires scene review and is not implied by these checks. Scope: renderer, validation/schema, documentation and controlled fixtures only; intake untouched.

- A: schema RED rejected the new environment field. First implementation passed both focused tests, including malformed arrays, booleans/nonfinite values, zero direction and all size/count/intensity limits.
- B: old renderer GPU RED ignored panels and failed the bright-reflection assertion. First implementation passed: glossy center231, rough149 with broader horizontal variance1479→20269; rotated panel changes highlight orientation; diffuse center80 with key/fill/ambient disabled; reverse-facing panel equals black control. Exact0→3→0 repeat passed, including a moving-camera control that changes its intermediate frame.
- Compatibility: six omitted/empty/off PNGs, including illuminated nonblack controls, are byte-identical between pre-change HEAD renderer and updated renderer. Four panels with polar directions, rotated frames, caps, bump, color patterns and contact depth render together. All13 fixtures validate.
- Full suites:82 Python tests and10 Node tests passed. Independent read-only review found no blocking issues. Minor suggestion to validate fixture scenes was incorporated; all13 validated fixtures regenerated successfully.
- Full default-browser export on developer lighting diagnostic plan06044113b67e43f3bbaac0f469a37c15 exited0 with unchanged integrity, exact-repeat and motion checks.10seconds1280x720,1,285,167bytes. Decoded review exited0; root viewed24decoded frames. This diagnostic derives from the native first skiff but changes camera/environment; it is not a live native authoring success or artistic candidate2.

Evidence: private `.local/environment-panels/` (RED/GREEN controls, suites, baseline byte comparison, export and decoded review) and `.local/focal-construction/root-diagnostic/` (geometry-held lighting comparisons). All new artifacts stayed local. Installed locally at ee21d2f after gateway restart. Windows Chrome/WebGL2 tested; no new macOS/Linux GPU evidence.

Optical limits: original analytic broad reflection with roughness peak compensation and approximate center-direction diffuse solid angle. Distant radiance, not physical area integration; no local falloff, panel shadows, sky-background panel image or scene-object reflections. No external renderer or reference code imported. Geometry/material work budgets unchanged; up to4 separately bounded panels.

The retained construction diagnostic is still not an impressive showcase: seat/hull intersections, excess floor and hidden cargo remain. Its failure is preserved and is being addressed by a separate native construction revision, not concealed by this capability pass.

Live integration follow-up: native candidate2, plan271b8020a4b84395b8bea4ec430451dd, includes three environment panels through the actual exposed revision tool and restarted installed gateway. Normal/reverse previews rendered and were viewed by native vision and root. Root independently checked exact saved/intended equality and unchanged source hashes. This establishes native schema/render integration, not artistic acceptance.
