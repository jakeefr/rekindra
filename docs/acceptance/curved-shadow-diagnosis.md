# Curved-surface shadow diagnosis

Question from actual forest previews: are dark curved-surface seams a new lighting regression or coarse geometry/shadow interaction? No production change made.

Isolated original-renderer test removes all other objects, fog, contact depth, reflection, material detail and fill complexity. Convex sphere with analytic smooth normals, fixed key/camera; diagnostic pixels encode occlusion in red, normal/light dot product in green and surface mask in blue. Tessellation alone varies12x6,24x12,48x24. Test condition for the directly lit region: mask255 and normal/light dot>.2; count occlusion>.1.

Observed433/66,604 affected samples at12x6,3/70,970 at24x12,0/71,804 at48x24. Root viewed diagnostic images: stepped self-shadowing is concentrated at the smooth-normal/triangulated-geometry light boundary. Increasing actual mesh resolution removes the measured directly lit artifacts. This does not demonstrate a general absence of shadow artifacts, nor establish an acceptable artistic density for every shape.

Ruling: do not disable shadows or add a global bias merely to hide the forest scene's authored shape/lighting weaknesses. Reserve sufficient sampling for the silhouette and curvature actually authored; complex lobes need more angular samples than a sphere. Keep existing cast-shadow regression and exact repeat gates unchanged. The scene's concave foliage also legitimately self-shadows, so it cannot be used as an unoccluded-sphere oracle. Evidence `.local/forest-reflection/shadow-diagnostic/`. One diagnostic round; no attempted renderer fix.
