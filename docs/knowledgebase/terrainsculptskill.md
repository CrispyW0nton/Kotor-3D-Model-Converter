# Terrain Sculpt Skill

Use this before changing terrain creation, heightfield brushes, walkability
overlay, terrain performance, or WOK slope validation in Map Studio.

Sources: mesh/terrain topics in Mukundan and Marschner/Shirley, geometric tests
from Dunn/Parberry and de Berg, OpenGL/render-pipeline performance concepts,
System Design performance budgeting.

## Working Rules

- Terrain sculpting must feel immediate. Treat lag as a bug, not polish debt.
- Live strokes update dirty height samples, local preview triangles, local bounds,
  and walkability overlay only. They must not rebuild the whole module.
- Coalesce high-frequency pointer/tablet samples per viewport frame. Drop stale
  frames when newer input exists.
- Full MDL/WOK/export rebuilds happen on stroke commit, validation, or staged
  export, never during pointer movement.
- Every brush records metadata: brush name, dirty region, changed sample count,
  performance estimate, slope report, and rebuild deferral.
- WOK slope/walkability feedback is live guidance, not game proof.

## Brush Policy

Current executable brush family:

- Raise/Lower: local height offset.
- Smooth: neighbor relaxation.
- Flatten: blend toward explicit height.
- Plateau: blend local area toward center height for pads/landings.
- Ramp: directional grade between stroke samples.
- Terrace: deterministic stepped bands.
- Pinch: pull affected samples toward center height for ridges/channels.
- Erode: cheap thermal-style relaxation for noisy spikes.
- Noise: deterministic small variation with slope report.

## Performance Contract

- Target frame: 8.33 ms for responsive sculpt interaction.
- Brush budget: 4.0 ms per live terrain brush frame.
- If over budget: coalesce more input, reduce radius/iterations, or defer.
- UI should show readiness/performance state instead of freezing.

## GhostRigger Applications

- `map_studio_terrain_sculpt_session.py` owns live frame coalescing.
- `authored_terrain_builder.py` owns heightfield brush math and metadata.
- Builder/viewport panels only select brush context and display status.
- KOTOR playability still requires WOK, entry point, placement, package, and
  in-game warp proof.

## Tests To Prefer

- Brush operation changes expected local samples only.
- Dirty region metadata matches affected samples.
- Over-budget audit warns instead of applying expensive frames.
- Live frame coalescing reduces many raw samples deterministically.
- Viewport/tool belt source-contract tests keep brush controls exposed.
