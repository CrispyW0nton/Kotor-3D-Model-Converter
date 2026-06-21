# Mesh Skill

Use this skill for mesh import, generated geometry, viewport rendering bugs,
topology validation, and mesh data contracts.

## Book Grounding

- `3D Math Primer`, chapter 10: polygon meshes, texture mapping, local lighting, skeletal animation, and real-time graphics pipeline.
- `Mathematics for Computer Graphics`, vector normals, transforms, analytic geometry, barycentric coordinates, and area tests.
- `3dsmax2020_ref_guide`, xView-style checks for flipped normals, overlapping faces, open edges, multiple edges, T-vertices, missing UVs, and statistics.
- `Game Engine Architecture`, tools and asset pipelines, resource/file systems, debug drawing, profiling, and runtime data layout.

## Workflow

1. Identify the mesh owner: source asset, imported runtime mesh, KMAX/KMAP scene object, renderer mesh data, or generated tool output.
2. Preserve stable object and subobject identity where GhostRigger already has IDs. Do not regenerate identities unless the operation is explicitly destructive.
3. Validate topology before debugging materials or lighting: face winding, normals, open boundaries, duplicate faces, isolated vertices, T-vertices, missing UVs, and degenerate triangles.
4. Keep mesh data headless. Put reusable checks and transforms in core/math/resource layers; GUI and viewport code should call the service.
5. For renderer bugs, separate geometry truth from display state: raw vertices/indices, transformed vertices, normals/tangents, UVs, material slots, texture bindings, and draw-call residency.
6. When imported modules are involved, use `K2:001ebo1` / `001EBO1` for visible renderer parity unless the user names another module.

## Topology Inspection Pass

- Count vertices, edges, triangles/polys, material slots, UV channels, bones,
  and draw groups before changing behavior.
- Classify boundaries: expected open border, accidental hole, seam, split UV,
  detached island, or nonmanifold edge.
- Check face winding and normal direction separately. A face can have valid
  topology and still render wrong because winding or normal transform is wrong.
- Find isolated vertices, duplicate vertices, duplicate faces, T-vertices,
  overlapping faces, missing UVs, flipped UV faces, and zero-area triangles.
- Build adjacency maps from indices rather than trusting spatial proximity.
  Spatial merges are destructive unless explicitly requested.
- Preserve material and smoothing/normal groups when converting or generating
  geometry.

## Mesh Operation Rules

- Selection operations should report whether they operate on objects, faces,
  edges, vertices, bones, or scene instances.
- Repair tools should produce a change report: removed vertices, merged edges,
  flipped faces, filled holes, regenerated normals, or skipped unsafe cases.
- Renderer mesh data should be immutable or versioned once queued for a frame;
  edits should create a new revision or dirty range.

## GhostRigger Checks

- For MDL mesh pipeline changes, follow AGENTS.md MCP order: `compare_model_pipelines`, `inspect_mdl`, `inspect_mdl_ghostrigger`, fix, then compare again.
- For viewport mesh behavior, use visible Debug app testing. Do not substitute headless widget construction for viewport proof.
- Prefer small fixtures: `PLC_bench` for static object mesh workflows and `N_DarthMalak` with `walk` for animated/skinned mesh workflows.

## Failure Patterns

- Geometry appears inside out: check winding and normal direction before lighting.
- Texture looks wrong but geometry is stable: check UV presence, UV face winding, material slot mapping, then texture decode.
- Selection or gizmo hits wrong part: compare object-space, world-space, and screen-space hit tests.
- Animation tears the mesh: inspect bind pose, bone palette order, skin weights, and per-object pose scoping.
