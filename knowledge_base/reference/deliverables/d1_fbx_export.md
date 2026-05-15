# Deliverable 1: FBX Export Fix
# ==============================
# File: src/converters/mesh_converter.py (~3,535 lines)
# Priority: HIGH | Effort: ~38 hours | Risk: HIGH

## Problem Statement
The FBX exporter falls back to handwritten ASCII when SDK/pyassimp are missing.
This fallback:
- Skips bones entirely (no skeleton hierarchy)
- Missing skin clusters / deformers
- Incorrect bind-pose matrices
- No weight normalization
- Unreal Engine import fails completely

## Root Cause Analysis
The ASCII FBX fallback was written as a quick hack that only outputs geometry tokens.
It does not understand the FBX object model for skeletal meshes.

## Required Fix (from dev brief)
Formula: **Jk = Lk x Fk** where:
- Jk = global bind-pose transform for bone k
- Lk = local transform of bone k (position + orientation from MDL node)
- Fk = offset matrix (transforms from mesh space to bone's local space)

## Tasks (from roadmap spreadsheet)
| Task | Description | Hours | Files | Acceptance |
|------|------------|-------|-------|------------|
| T101 | Fix bone hierarchy export | 6 | mesh_converter.py | All bones in output, parent-child correct |
| T102 | Implement FBX skin deformers | 8 | mesh_converter.py | Deformer + SubDeformer per bone |
| T103 | Fix bind-pose matrix computation | 8 | mesh_converter.py | TransformLink = inverse offset = global bind |
| T104 | Add synthetic bone stubs | 4 | mesh_converter.py | Non-skinned bones present in FBX |
| T105 | Weight normalization | 4 | mesh_converter.py | Per-vertex weights sum to 1.0, max 4 influences |
| T106 | Animation export | 4 | mesh_converter.py | AnimCurveNode for each bone's channels |
| T107 | Regression tests + Unreal validation | 4 | new test file | Round-trip: export -> ufbx parse -> verify |

## Cross-Reference Repos to Study BEFORE Coding
1. **ufbx** (`ufbx.h`): Study `ufbx_skin_cluster`, `ufbx_skin_deformer` structures
   - `ufbx_skin_cluster.bind_to_world` = our TransformLink
   - `ufbx_skin_cluster.geometry_to_bone` = our offset matrix
2. **KotorBlender** (`io_scene_kotor/scene/modelnode/skin.py`): How skin weights are read from MDL
3. **FBX2glTF** (`src/fbx/`): How FBX SDK objects map to export code

## Book Principles (MUST follow)
- **Mukundan 7.5.1 (Offset Matrix)**: F = Translation(-Jx, -Jy, -Jz) for simple case
- **Mukundan 7.6 (Vertex Blending)**: v' = sum(wi * Ji * v); weights must sum to 1.0
- **Gregory 5.3 (Matrices)**: Column-major (OpenGL) vs row-major (FBX); MUST transpose
- **Gregory 5.4 (Quaternions)**: KOTOR uses quaternions; FBX ASCII uses Euler angles; convert via matrix

## FBX ASCII Structure Required
```
; Objects section must contain:
Model: <id>, "Model::<bone_name>", "LimbNode"     ; For each bone
Model: <id>, "Model::<mesh_name>", "Mesh"          ; For each mesh
Geometry: <id>, "Geometry::", "Mesh"                ; Vertex/face data
Deformer: <id>, "Deformer::", "Skin"                ; One per skinned mesh
Deformer: <id>, "Deformer::<bone>", "Cluster"       ; One per bone
  Transform: <16 floats>                            ; Geometry-to-bone (offset)
  TransformLink: <16 floats>                        ; Bone's global bind pose

; Connections section must contain:
C: "OO", <cluster_id>, <skin_id>                    ; Cluster -> Skin
C: "OO", <skin_id>, <geometry_id>                   ; Skin -> Geometry
C: "OO", <bone_model_id>, <cluster_id>              ; Bone -> Cluster
C: "OO", <child_bone_id>, <parent_bone_id>          ; Bone hierarchy
```

## Acceptance Criteria
1. FBX file imports into Unreal Engine 5 without errors
2. Skeleton hierarchy matches KOTOR MDL node tree
3. Mesh is properly skinned (vertices deform with bones)
4. Bind pose is correct (mesh doesn't explode on import)
5. Weights are normalized (sum to 1.0 per vertex)
6. ufbx can parse the output FBX without errors
7. All existing functionality preserved
