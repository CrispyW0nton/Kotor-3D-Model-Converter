# Computational Geometry Skill

Use this before changing booleans, snapping, intersection tests, polygon
splits, triangulation, walkmesh generation, terrain sampling, or spatial lookup
systems in Map Studio.

Sources: de Berg computational geometry, Mukundan mesh processing,
Marschner/Shirley graphics fundamentals, Dunn/Parberry and Vince graphics math,
and Kneusel numerical-programming notes.

## Working Rules

- Prefer explicit predicates over visual guesses: orientation, sidedness,
  segment intersection, point-in-polygon, point-in-triangle, and ray/plane tests.
- Store tolerances near the operation that uses them. A viewport-picking epsilon
  is not automatically safe for export geometry.
- Classify degenerate cases first: duplicate points, collinear edges, zero-area
  faces, self-intersections, inverted winding, and near-parallel planes.
- Use spatial indexes for repeated queries. BVH/grid/k-d style acceleration is
  required for large terrain picks, snap targets, and validation sweeps.
- Triangulate deterministically and record the input polygon, tolerance, and
  cleanup decisions so KOTOR export bugs can be reproduced.
- Treat booleans as pipelines: classify, split, rebuild topology, repair
  normals/winding, remap materials, validate, then mark export/proof stale.

## GhostRigger Applications

- Hold-V snapping should query a bounded set of nearby valid vertices/bones
  instead of scanning the whole scene on every mouse move.
- Map Studio floor plans and room outlines should reject self-intersections
  before generating MDL/MDX/WOK candidates.
- WOK and PTH readiness should use triangle-plane and barycentric tests for
  entry points, doors, triggers, waypoints, and gameplay anchors.
- Terrain brush dirty regions should be spatial rectangles/tiles, not a full
  module rebuild trigger.

## Preflight Checklist

- What geometric predicate decides success?
- What tolerance is used, and why is it safe for this operation?
- Are coordinates in local, room, module, or viewport space?
- Does the result change topology, WOK walkability, or export ownership?
- Is there a deterministic cleanup/triangulation step?
- Does the operation invalidate preview, export, or game-proof state?

## Tests To Prefer

- Segment intersection and polygon split edge cases.
- Point-in-WOK triangle with entry point near edges and vertices.
- Self-intersecting floor-plan rejection.
- Deterministic triangulation for repeated runs.
- Snap target selection with a bounded spatial index.
