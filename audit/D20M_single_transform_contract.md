# D20-M Single Transform Contract

## Decision: Keep Vertices Local, Apply Node Transform in Renderer

**Date**: 2026-04-18
**Phase**: D20-M (Vertex-Space Contract Reset)

---

## Chosen Transform Path

**Vertices stay in node-local space** as stored in the MDL binary.
Every transform consumer reads `node.vertex_space` and applies exactly one
world transform when `vertex_space == NODE_LOCAL`:

```
world_pos, world_orient = node.world_transform()
v_world = quat_rotate(world_orient, v_local) + world_pos
```

When `vertex_space == WORLD` (imported OBJ/FBX), vertices are used as-is.
When `vertex_space == AABB_WALK` (walkmesh), the node is skipped entirely.

---

## Why Not CPU-Bake?

Pre-baking vertices into world space at load time would eliminate the need for
per-frame transforms, but it breaks:

1. **Animation**: Animated bone transforms require the original local vertices.
2. **Supermodel chain**: Head-attachment models need the skeleton's bind-pose
   transform, which isn't available until the composite model is assembled.
3. **Consistency**: Reference engines (xoreos, KotOR.js, reone) all store
   vertices local and apply the transform in the renderer.

---

## Transform Paths and Their `vertex_space` Reads

| Code Path                              | File                  | Action for NODE_LOCAL       | Action for WORLD |
|----------------------------------------|-----------------------|-----------------------------|-------------------|
| `model.compute_bounds()`               | model_data.py:1017    | rotate + translate          | use as-is         |
| `render_bounds._node_world_verts()`    | model_data.py:1127    | rotate + translate          | use as-is         |
| `_build_vbo_data()`                    | gpu_renderer.py:1441  | rotate + translate (batch)  | pass (no-op)      |
| `_compute_model_bounds()`              | gpu_renderer.py:3514  | rotate + translate (numpy)  | pass (no-op)      |

All four paths produce identical world-space vertex positions for the same node.

---

## Deleted Heuristics

| Heuristic                           | Location (old)            | Replacement          |
|-------------------------------------|---------------------------|----------------------|
| `_WORLDSPACE_VERT_THRESHOLD = 1.5`  | gpu_renderer.py:1453      | `vertex_space == 0`  |
| `centroid_mag > threshold`           | gpu_renderer.py:1496-1507 | `vertex_space == 0`  |
| `_is_accessory_skin` + centering    | gpu_renderer.py:1466-1565 | `vertex_space == 0`  |
| `_nonskin_worldspace` flag           | gpu_renderer.py:1502-1508 | `vertex_space == 0`  |
| `_WORLDSPACE_THRESHOLD = 1.5`       | gpu_renderer.py:3593      | `vertex_space == 0`  |
| Strategy B outlier exclusion (1.5u) | model_data.py:1179-1206   | removed entirely     |
| Skin-only local rotation            | gpu_renderer.py:1534-1545 | `vertex_space == 0`  |

---

## `vertex_space` Assignment

Set once at load time by `compute_vertex_space()` in `src/core/vertex_space.py`.

Rules:
1. `flags & 0x0200` (AABB) → `AABB_WALK` (2)
2. `_imported == True`      → `WORLD` (1)
3. Everything else          → `NODE_LOCAL` (0)

No centroid checks, no name-suffix checks, no skeleton/supermodel checks.

---

## Reference Engine Corroboration

| Engine       | Source File                    | Vertex Storage | Transform Applied By        |
|--------------|-------------------------------|----------------|-----------------------------|
| xoreos       | model_kotor.cpp readMesh      | Node-local     | Model matrix (GPU)          |
| KotOR.js     | OdysseyModelNodeMesh.ts       | Node-local     | THREE.js matrixWorld (GPU)  |
| KotOR.js     | OdysseyModel3D.ts (static)    | Pre-baked       | applyMatrix4 (CPU one-shot) |
| reone        | mdlreader.cpp                 | Node-local     | Scenegraph node (GPU)       |
| KotorBlender | parser.py readMesh            | Node-local     | Blender object hierarchy    |
| PyKotor      | mdl_auto.py                   | Node-local     | Blender import post-process |

None use centroid-magnitude heuristics. None distinguish skin vs non-skin for
the purpose of deciding whether to apply the world transform.

---

## Expected Outcome

For model `101perzc`, the bounding radius should match the "old working"
screenshot value (R ≈ 109.7) rather than the doubled value (R ≈ 182.0 or 132.0).

For character models (p_bastilabb, c_bantha, etc.), the transform path is
identical to the old code's non-skin branch (rotate + translate), which was
always correct for trimesh nodes. The change affects skin nodes that were
previously exempted from the world transform — these now also receive it, but
in practice their `world_transform()` is typically identity (bone pivot at
origin), so the result is unchanged.
