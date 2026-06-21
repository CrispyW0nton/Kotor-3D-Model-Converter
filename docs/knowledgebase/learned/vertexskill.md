# Vertex Skill

Use this skill for vertex transforms, normals, barycentric math, skin weights,
vertex selection, and per-vertex validation.

## Book Grounding

- `3D Math Primer`: points versus vectors, coordinate spaces, matrices, geometric primitives, triangle tests, and skeletal animation.
- `Mathematics for Computer Graphics`: deriving triangle normals, transforming vectors, barycentric coordinates, interpolation, and analytic geometry.
- `Automatic skinning and weight retargeting`: LBS, per-vertex weights, joint-area refinement, constraints, smoothing, and weight transfer.
- `3dsmax2020_ref_guide`: viewport statistics and checks for isolated vertices, T-vertices, UV problems, and flipped faces.

## Workflow

1. Name the vertex space before doing math: object, bind, pose, parent, world, camera, screen, or UV.
2. Treat points and direction vectors differently. Translations affect points; normals and tangents need vector transforms and usually inverse-transpose handling when non-uniform scale is present.
3. For per-vertex deformation, track this chain explicitly: bind position -> bone transforms -> weighted pose position -> object/world transform -> renderer/camera projection.
4. For barycentric or triangle selection, reject degenerate triangles first and keep epsilon handling local and named.
5. For skinning, validate weight count, normalization, bone indices, palette order, and whether the runtime supports more influences than the source model provides.
6. Preserve vertex ordering when external formats depend on it. If a tool must reorder vertices for cache locality or deduplication, emit a remap table.

## Per-Vertex Data Checklist

- Position: object/bind/pose/world space.
- Normal: normalized direction, transformed separately from position.
- Tangent/bitangent: handedness and UV orientation.
- UVs: channel count, per-face-corner vs per-vertex ownership, missing values.
- Color: format, color space, alpha policy.
- Skinning: bone indices, weights, influence count, normalization, palette
  mapping.
- Provenance: source vertex ID, generated vertex ID, remap table, and owning
  scene object.

## Interpolation And Picking

- Barycentric coordinates are useful for hit interpolation, height lookup,
  UV/material sampling, and weight transfer, but only after rejecting degenerate
  triangles.
- Ray tests must use the same coordinate space for ray and triangle.
- Edge hits need a tolerance policy distinct from face-inside tests.
- Interpolated normals/weights should be renormalized after interpolation.

## GhostRigger Checks

- Use MCP pipeline comparison before changing MDL loading, transforms, or skinning behavior.
- Add focused tests around the owning layer: math functions in `src/math`, mesh data contracts in rendering/core packages, and import/export rules in format/resource packages.
- For visible regressions, compare screenshots or frame deltas only after verifying the backend vertex data is correct.

## Failure Patterns

- Normals flip only after scale: check inverse-transpose normal handling and handedness.
- Vertex picking misses near edges: check triangle winding, ray space, barycentric epsilon, and viewport projection.
- Skin collapses near a joint: check missing/unnormalized weights and bone index remapping.
- Mirrored limbs twist: check local rotation axes, bind pose, and whether mirrored weights still point to the correct side.
