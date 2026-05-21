# Day 4.5 v6 Skeleton Renamer Audit

## Executive Summary

Day 4.5 v6 exports PMBAM + g1a1 as a self-contained FBX using the native Aurora
bind pose. The exporter builds Blender bones from Aurora `bind_world_matrix_4x4`,
binds mesh weights by bone-name vertex groups, bakes animation curves as deltas
from rest, applies a UE5 naming layer, and adds zero-weight helper leaves.

Output:
- FBX: `exports/retargets/day4_5/pmbam__g1a1__day4_5_v6.fbx`
- Manifest: `exports/retargets/day4_5/pmbam__g1a1__day4_5_v6.manifest.json`
- Intermediate: `exports/retargets/day4_5/pmbam__g1a1__day4_5_v6_intermediate.json`
- SHA-256: `b05743b68c955b0eadaee13fc2d396f89e4b02fa8bb442473520942ca158f634`

## Five-Layer Architectural Lessons

1. Day 4 failed because skeleton transplant produced a mesh/skeleton bind-pose
   mismatch even though structural roundtrip checks passed.
2. Day 4.5 v1-v3 failed because export-time rest-pose forcing double-transformed
   an Aurora-bound mesh.
3. Day 4.5 v4 corrected the separation of concerns: the exporter preserves
   source semantics, while Unity/UE5 handles target pose alignment.
4. Day 4.5 v5 over-specified manual roll/orientation math.
5. Day 4.5 v6 uses the proven Blender primitive instead: assign each edit
   bone's matrix directly from the Aurora world-bind matrix and let Blender
   derive head, tail, and roll.

## Prior Art Validation

KotorBlender validates the armature construction, name-keyed vertex groups, and
delta-from-rest animation baking patterns. KotOR-Unity, reone, xoreos, and
KotOR.js corroborate the broader Aurora/Odyssey model and animation landscape.
See `knowledge_base/retargeting/prior_art_landscape.md`.

No GPL source was vendored or copied.

## Phase 0 Contract

Ground-truth capture:
`knowledge_base/retargeting/ground_truth/day4_5_v6_20260521T032834Z/`

Validation summary:
- Aurora bones: 58
- Mesh vertices: 1,184
- Clip: `g1a1`
- FPS: 30.0
- Frames: 45
- Ground-truth contract errors: 0

Every exported Aurora bone carries:
- `local_translation`
- `local_rotation_quat_wxyz`
- `bind_world_matrix_4x4`
- parent name
- deform/helper flags

## Rename And Helper Coverage

Rename map:
`knowledge_base/retargeting/aurora_to_ue5_rename_map.json`

Coverage:
- Explicit Aurora to UE-style rename pairs: 20
- Twist helper leaves: 8
- Humanoid helper leaves: 2 (`neck_01`, `head`)
- Scope: `BONE_NAMING_ONLY`
- Explicit non-scope: rest pose modification, rotation application, vertex transformation, vertex weight remapping

The PMBAM body model lacks a deforming head/neck chain because heads are
swappable in KOTOR. The v6 map adds non-deforming `neck_01` and `head` helper
leaves so Unity/UE humanoid pre-checks can find those slots without changing
Aurora skin weights.

## Export Notes

The v6 exporter sets `use_armature_deform_only=False` for this path. Blender 4.2
drops zero-weight helper leaves when the flag is enabled, which removes the
synthetic humanoid `neck_01` and `head` slots. The helper bones remain
non-deforming and zero-weight; the export flag only controls whether they are
serialized.

## Roundtrip Metrics

| Metric | Result |
| --- | --- |
| Bone count | 68 / 68 |
| Vertex count | 1,184 / 1,184 |
| Frame count | 45 / 45 |
| Axis | Z up, -Y forward |
| Added `_end` leaf bones | 0 |
| Frame 0 rotation delta | 0.0 |

## Evaluated Skinning Gate

Validation file:
`exports/retargets/day4_5/pmbam__g1a1__day4_5_v6.visual.json`

The visual gate clears pose transforms before evaluation and compares in the
armature/deformation space rather than the FBX importer's scene-level axis
wrapper.

| Metric | Result | Gate |
| --- | ---: | ---: |
| Height ratio | 0.9999999658 | >= 0.99 |
| Width ratio | 1.0000000000 | >= 0.99 |
| Silhouette proxy | 0.9994565217 | >= 0.95 |
| Left arm vertex ratio | 1.0 | >= 0.99 |
| Right arm vertex ratio | 1.0 | >= 0.99 |
| Required humanoid bones missing | 0 | 0 |
| Bind-pose influencing bones present | true | true |
| Bind-pose parent bones present | true | true |

## Sprint Boundary

Sprint 1 remains single-character, single-clip, clean-path export. Sprint 2 owns
full supermodel animation library resolution, batch export, stress models, and
reverse UE/Unity to KOTOR workflows.

## Verification

Commands:
- `python -m pytest tests/test_skeleton_renamer.py tests/test_ground_truth_contract.py tests/test_blender_fbx_export_script.py tests/test_fbx_exporter_visual.py -q`
- `python -m pytest tests/test_sampler.py tests/test_coordinate_normalizer.py tests/test_baker.py -q`
- `python -m pytest tests/test_fbx_exporter.py -q`

Results:
- Day 4.5 v6 focused suite: 22 passed
- Day 2/3A regression subset: 9 passed
- Day 4 legacy FBX exporter regression: 10 passed
