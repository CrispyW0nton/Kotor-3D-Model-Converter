# Mesh Skill

Use this before changing mesh import, room geometry, object separation,
combining, UV/DCC handoff, or Map Studio mesh export boundaries.

Sources: Mukundan mesh processing, de Berg computational geometry, Marschner/
Shirley fundamentals, Dunn/Parberry 3D math, Vince graphics math, prior
GhostRigger programming crosswalk.

## Working Rules

- Treat mesh data as structured topology, not just vertex lists. Track vertices,
  faces, material groups, normals, UVs, and object/export boundaries separately.
- For editable meshes, maintain adjacency explicitly enough to answer "what
  edges/faces touch this vertex?" without rebuilding the world. Half-edge or
  winged-edge style records are the preferred internal mental model even if the
  serialized KMAP shape remains simpler.
- Keep KMAP authoring state human-readable and stable. Do not store heavy mesh
  blobs in KMAP unless a future schema explicitly requires it.
- Preserve object identity. Separate/combine operations must keep stable IDs,
  source room resrefs, material intent, and generated MDL/MDX/WOK ownership.
- Use deterministic triangulation before KOTOR export. Non-deterministic face
  splitting makes WOK, collision, and proof bugs hard to reproduce.
- Treat topology cleanup as an explicit command: remove duplicates, collinear
  points, degenerate triangles, inverted faces, and sliver WOK triangles.
- Keep render geometry and WOK intent linked but not identical. Visual objects
  can be decorative; walkable surfaces must be deliberate.
- Bounds, normals, tangents, UVs, and adjacency are derived caches. Invalidate
  them with explicit reasons after topology edits; do not let the viewport own
  the only copy.

## GhostRigger Applications

- Map Studio object separation should produce independent export-object
  summaries, not just visual mesh islands.
- Combining rooms/primitives must not silently merge resource identity. KOTOR
  module output still needs clean MDL/MDX/WOK/LYT/VIS ownership.
- External UV/texturing handoff should export clear object boundaries and
  material texture names so a modder can round-trip through Blender/Maya.
- Imported FBX/OBJ meshes in Character Builder are payload geometry until bound
  to a native KOTOR skeleton and validated.

## Preflight Checklist

- Are vertex positions finite and in the expected coordinate space?
- Are face indices valid and non-degenerate?
- Are normals/winding consistent for renderer and export?
- Are material/texture references preserved by name and case?
- Is WOK surface intent explicit for player traversal?
- Are object boundaries visible to the modder before export?
- Did this operation change topology or only transform an existing object?

## Tests To Prefer

- Core tests for mesh/topology transformation without Qt.
- Golden small fixtures for plane, cube, cylinder, ramp, stair, door frame.
- Export-object boundary tests that assert independent MDL/MDX/WOK resources.
- Visible viewport smoke only after core behavior is locked.
