# Extrusion Skill

Use this before changing extrusion, bridge, bevel, inset, cut/split, fill, or
boolean modeling tools in Map Studio.

Sources: Maya-style rig/modeling workflow concepts from O'Hailey, mesh
processing from Mukundan, computational geometry from de Berg, graphics math
from Dunn/Parberry and Vince.

## Working Rules

- Extrusion is topology generation plus validation, not just moving a face.
- Keep first-pass operations conservative: convex floor-plan edge extrusion,
  rectangular cuts, deterministic bridge corridors, and simple primitive
  booleans are safer than arbitrary mesh surgery.
- Record the operation source: selected face/edge loop, normal/reference axis,
  distance/offset, material inheritance, UV policy, and WOK intent.
- Bevel/inset must reject tiny or self-intersecting results that create sliver
  triangles or broken doorway seams.
- Bridge operations need compatible edge orientation, elevation, material, WOK
  surface, and room/visibility ownership.
- Boolean output is only export-candidate after cleanup, triangulation, normal
  repair, WOK review, and validation.
- Fill operations must record face intent: visual-only, walkable WOK, blocked
  WOK, door/transition, water, or other KOTOR surface type.

## GhostRigger Applications

- Tool belt buttons may use Maya words, but the domain layer must output KOTOR
  room/resource facts.
- Cut, bridge, and separate should create explicit exportable room/object
  boundaries when that is safer than editing one huge mesh.
- New faces need predictable material and UV defaults so external DCC texturing
  can happen without guessing which faces were generated.
- Any operation that changes traversal must update WOK preview/readiness.
- Exterior/terrain transitions should stay visible as planned/export-candidate
  until in-game proof exists.

## Preflight Checklist

- Is the input selection valid for the operation?
- Will the result stay manifold enough for deterministic triangulation?
- Does the result preserve room resrefs and KMAP stable IDs?
- Does the operation affect WOK traversal?
- Does VIS/LYT membership need updating?
- Did the UI clearly explain whether the result is game-tested?

## Tests To Prefer

- Edge extrude a rectangular room and assert MDL/MDX/WOK remain generated.
- Bridge two compatible edges and assert a connector room is created.
- Rectangular cut splits a room into valid resource outputs.
- Bevel/inset rejects too-large distances.
- Boolean/separate reports export object boundaries.
