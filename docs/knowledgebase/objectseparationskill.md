# Object Separation Skill

Use this before changing Map Studio object separate/combine, export boundaries,
room ownership, DCC/UV handoff, generated resource grouping, or KMAP object
identity.

Sources: Mukundan mesh topology and character mesh processing, de Berg
computational geometry, graphics pipeline/data-flow guidance from
Marschner/Shirley and Hayes, and GhostRigger's KOTOR module export constraints.

## Working Rules

- Separate and combine are resource-ownership operations, not just viewport
  visibility changes.
- Preserve stable IDs and provenance. A separated object should remember source
  room resrefs, source primitive IDs, material names, WOK ownership, and the
  operation that created it.
- Combining objects must not silently merge KOTOR runtime responsibilities.
  Visual mesh, walkmesh, light/visibility, pathing, and gameplay placements can
  share a workspace but still need clear export boundaries.
- Keep render mesh and WOK mesh related but independently auditable. A decorative
  object can be visual-only; a floor/ramp/stair object must state walkability.
- DCC handoff requires clean object names, material slots, UV intent, transform
  pivots, and round-trip metadata.
- Topology-changing separate/combine operations stale MDL, MDX, WOK, LYT, VIS,
  PTH, and packaged `.mod` proof unless a narrower validation proves otherwise.
- Do not bake arbitrary viewport transforms into vertices unless the user chose
  a bake/freeze/export operation and the readiness report records it.

## GhostRigger Applications

- A modder separating a building, terrain patch, cave wall, or prop cluster
  should see which KOTOR resources that object will produce or affect.
- Combining rooms should produce a readable export-boundary summary before any
  package is staged.
- In the current Map Studio implementation, Combine means compatible
  rectangular floor-plan room union. Do not imply arbitrary mesh-object combine
  until a later mesh-editing pass owns that topology operation.
- Separate currently means splitting a named authored composition primitive into
  its own exportable room/object boundary for UV and texturing handoff.
- UV/texturing workflows should allow export to Blender/Maya without losing
  KMAP identity or KOTOR resource intent.
- Object names shown to users should map to resrefs/export labels where
  possible, while internal IDs remain stable even after renaming.
- The readiness panel should explain stale output by KOTOR resource type, not
  only say "export stale."

## Preflight Checklist

- Is this operation changing visual grouping, topology, transform, or resource
  ownership?
- Which MDL/MDX/WOK output owns each resulting object?
- Are LYT/VIS/PTH impacts explicit?
- Are material and texture names preserved?
- Are pivots/transforms preserved or intentionally frozen?
- Can the modder tell whether the result is previewable, export-candidate, or
  game-tested?
- Does undo restore object identity and readiness metadata?

## Tests To Prefer

- Separate a primitive room into two export objects and assert stable IDs.
- Combine two compatible objects and assert provenance is retained.
- Export-boundary tests that list expected MDL/MDX/WOK resources.
- Readiness tests that explain stale resource impacts after combine/separate.
- DCC handoff metadata tests for object labels, material slots, pivots, and UV
  intent.
