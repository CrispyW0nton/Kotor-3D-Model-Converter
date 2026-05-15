# K2 Skin Transform Audit

Generated during Phase 6 diagnosis to explain how reference renderers treat KotOR skin meshes.

## Sources Checked

- xoreos `src/graphics/aurora/model_kotor.cpp`
- xoreos `src/graphics/aurora/animation.cpp`
- KotOR.js `src/odyssey/OdysseyModelNodeMesh.ts`
- KotOR.js `src/odyssey/OdysseyModelNodeSkin.ts`
- KotOR.js `src/three/odyssey/OdysseyModel3D.ts`

## xoreos Findings

xoreos reads mesh vertex positions directly from MDX into `initialVertexCoords`; it does not pre-bake parent-node world transforms while reading geometry. For skins, `readSkin()` reads:

- per-vertex bone weights from MDX,
- per-vertex bone mapping IDs from MDX,
- `boneMapping` from the MDL skin header,
- qBone/tBone inverse bind-pose data.

During `Animation::updateSkinnedModel()`, xoreos computes a node-level bind transform and then applies skinning as:

1. initial vertex position,
2. skin node bind transform,
3. influencing bone inverse bind pose,
4. influencing bone absolute transform,
5. inverse of the skin node bind transform,
6. weighted sum across up to four influences.

Important xoreos note: there is a TODO for a KotOR 2 Handmaiden-style case where a skin node parented under a bone can receive transforms twice: once by the renderer and once by skinning. That is directly relevant to the K2 visual bug class.

## KotOR.js Findings

KotOR.js reads mesh positions into `OdysseyModelNodeMesh.vertices` without pre-transforming them. Skin nodes add:

- `skinIndex` from MDX bone indices,
- `skinWeight` from MDX weights,
- `bone_mapping` from the MDL skin header,
- qBone/tBone-derived `bone_inverse_matrix`.

When building the Three.js runtime model, `NodeMeshBuilder()` creates a `THREE.SkinnedMesh` for skin nodes, attaches the raw geometry to the node object, and sets `skinIndex` / `skinWeight` attributes. `buildSkeleton()` then binds the mesh to a `THREE.Skeleton` using bone nodes from the model hierarchy and the qBone/tBone inverse matrices.

This matches xoreos at a high level: raw skin vertices are retained, while skeletal deformation is handled by a skinning pipeline using inverse bind matrices and current bone transforms.

## Answer To The Key Question

Skin vertices should not be treated as generic static mesh vertices where the renderer permanently applies the skin node's world transform and stops there. The reference behavior keeps raw skin vertex positions and resolves final positions through skinning math.

The current GhostRigger invariant that skin nodes are `NODE_LOCAL` can still be true at the loader-contract level, but the renderer must avoid double-applying a parent-chain transform when the same transform is also represented in the skinning matrices. The suspicious case is not "K2 skin vertices are WORLD"; it is "K2 skin render path may be applying the skin node transform outside the LBS bind/inverse-bind calculation."

## Diagnostic Result So Far

`scripts/diagnose_k2_geometry.py` wrote `exports/k2_geometry_diagnosis.json` for 36 requested K2 starter models.

- 30 models loaded successfully.
- 6 requested head resrefs were not found in K2 (`PFHC08-10`, `PMHC08-10`).
- All loaded models had in-range bone indices and normalized weights within tolerance.
- The only parent-chain transform flags found were tongue skin nodes on `PFHC01`, `PMHC03`, and `PMHC04`.

A broader 180-model K2 creature/NPC/player sample was also written to `exports/k2_geometry_diagnosis_broad_sample.json`.

- 171 models classified as `OK` by diagnostic evidence.
- 8 models classified as `OFFSET` risk due to non-identity skin parent chains.
- 1 model (`n_darthmalak`) failed in raw parsing with a stream-boundary error.
- No model in the broad sample produced `SPIKES` evidence from out-of-range bone indices.
- No model in the broad sample produced `STRETCHED` evidence from weight normalization or zero-weight vertices.

This makes a broad K2 bonemap-index failure unlikely for the sampled character/creature set. The next diagnosis step is to compare GhostRigger's CPU/GPU skin render math against the xoreos/KotOR.js bind-pose flow, especially for skin nodes parented below other animated bones.
