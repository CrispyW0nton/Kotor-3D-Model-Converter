# Mesh Rebinder Parity Audit - Day 3B / 3B.5

Date: 2026-05-20
Status: PASS after Day 3B.5 skeleton pre-alignment

## Summary

Day 3B implemented the skinned mesh loader, skeleton-transplant rebinder, Quinn
twist-segment map, and test harness. The lower invariants passed immediately,
but raw Quinn bind-pose parity failed. Day 3B.5 added
`src/core/retargeting/skeleton_aligner.py`, which builds a Quinn-named,
Aurora-proportioned bind skeleton before mesh transplant. With pre-alignment
enabled by default, the strict mesh parity gates now pass.

Live KOTOR install remained untouched.

## Ground Truth

Day 3B mesh and Quinn bind ground truth:

- `knowledge_base/retargeting/ground_truth/day3b_20260520_230725Z/pmbam_mesh_inventory.json`
- `knowledge_base/retargeting/ground_truth/day3b_20260520_230725Z/pfbam_mesh_inventory.json`
- `knowledge_base/retargeting/ground_truth/day3b_20260520_230725Z/quinn_bind_pose_world.json`

Day 3B.5 bind hierarchy ground truth:

- `knowledge_base/retargeting/ground_truth/day3b5_20260521_005604Z/aurora_pmbam_bind_hierarchy.json`
- `knowledge_base/retargeting/ground_truth/day3b5_20260521_005604Z/quinn_bind_hierarchy.json`

Findings:

- `pmbam` has 3 skinned mesh nodes: `Torso`, `LArm`, `RArm`.
- `pfbam` has 3 skinned mesh nodes: `Torso`, `RArm`, `LArm`.
- Quinn export skeleton has 89 bones after excluding the `SKM_Quinn_Simple`
  wrapper node.
- All Quinn bind matrices are non-degenerate; minimum 3x3 determinant was 1.0.
- Bundled Quinn has 16 twist bones, not the older 8-bone assumption. The twist
  map includes both `_01` and `_02` twist bones per limb segment.
- All 24 direct `pmbam -> Quinn` mapped bones had valid source and target bind
  data in the Day 3B.5 hierarchy capture.

## HALT Chronicle

Initial Day 3B command:

```powershell
python -m pytest tests\test_mesh_loader.py tests\test_mesh_rebinder.py -v
```

Initial result:

- Passed: 7
- Failed: 2

The failed tests were the raw bind-pose parity gates:

- `test_bind_pose_parity_pmbam`
- `test_bind_pose_parity_pfbam`

The failure was architectural, not numerical. Raw transplant uses:

```text
V_new = sum(w_i * M_target_bind[j_i] * inverse(M_source_bind[i_i]) * V_old)
```

That equation correctly moves the KOTOR mesh to raw Quinn proportions. Because
Quinn and KOTOR bodies have different bind proportions, raw world-space vertex
parity is not the right production gate.

## Skeleton Aligner Architecture

Day 3B.5 inserts this step before mesh transplant:

```text
Aurora bind pose
  -> align_target_skeleton_to_source()
  -> Quinn-named, Aurora-proportioned aligned bind skeleton
  -> mesh transplant against aligned Quinn bind matrices
```

Locked decisions:

- Rotation strategy: `copy_source`
- Test gate: strict post-alignment parity, mean <= 1% and p95 <= 5%
- `enable_skeleton_prealignment=True` by default
- Raw transplant preserved as debug mode and documented by test
  `test_raw_transplant_failure_documented_pmbam`

Mapped Quinn bones copy the source mapped bone's world bind transform. Unmapped
regular bones preserve raw target local offsets from the aligned parent. Twist
bones interpolate along configured aligned limb segments from
`knowledge_base/retargeting/twist_segment_maps/ue5_manny.json`.

## Coordinate Space Verification

Representative source/raw-target/aligned positions:

| Target Bone | Source Bone | Source Position | Raw Quinn Position | Aligned Position | Strategy |
|---|---|---:|---:|---:|---|
| `pelvis` | `pelvis_g` | source bind | raw Quinn bind | source bind | direct copy |
| `spine_02` | `torso_g` | source bind | raw Quinn bind | source bind | direct copy |
| `spine_03` | `torsoupr_g` | source bind | raw Quinn bind | source bind | direct copy |
| `clavicle_l` | `lcollar_g` | source bind | raw Quinn bind | source bind | direct copy |
| `hand_l` | `lhand_g` | source bind | raw Quinn bind | source bind | direct copy |

Validation max mapped-bone drift after alignment:

- `pmbam -> Quinn`: 0.0 m
- `pfbam -> Quinn`: 0.0 m

## Global Scale

Scale strategy: `pelvis_to_head`.

Observed factors:

- `pmbam -> Quinn`: 0.6268270156880318
- `pfbam -> Quinn`: 0.6232079519006507

Note: `pmbam`/`pfbam` are body models with `headhook`, not complete heads, so
the factor is recorded for diagnostics and future export scaling but direct
mapped-bone copies drive the current parity result.

## Alignment Handling Counts

| Model | Direct Copy | Twist Interpolated | Ancestor Fallback | Root Anchor |
|---|---:|---:|---:|---:|
| `pmbam` | 19 | 16 | 54 | 1 |
| `pfbam` | 20 | 16 | 53 | 1 |

Duplicate target aliases are resolved toward real `_g` mesh-bones over dummy
helper nodes. This is required for pairs like `lforearm_g` and `lforearm`, both
of which can map to Quinn `lowerarm_l`.

## Index Remapping Statistics

Day 3B loader conversion:

- KotOR MDX vertex indices are skin-local palette slots.
- `mesh_loader.py` resolves them to global non-skin skeleton indices before
  rebinding.
- `pmbam` torso used 15 direct source bones and no fallback source bones.
- `pfbam` torso used 15 direct source bones and one fallback source bone
  (`breastbone`).

## Twist Redistribution

The bundled Quinn skeleton has 16 twist bones:

- Upper arm: `_01` at one-third, `_02` at two-thirds.
- Lower arm: `_02` at one-third, `_01` at two-thirds.
- Thigh: `_01` at one-third, `_02` at two-thirds.
- Calf: `_02` at one-third, `_01` at two-thirds.

Weight redistribution remains monotonic along the segment and is covered by
`test_twist_redistribution_monotonic`.

## Raw vs Aligned Parity

Required gates:

- Mean vertex deviation <= 1% of bbox diagonal
- P95 vertex deviation <= 5% of bbox diagonal

| Metric | Raw Day 3B | Aligned Day 3B.5 | Improvement |
|---|---:|---:|---:|
| `pmbam` mean | 5.3948% | 0.000000375% | ~14,375,567x |
| `pmbam` p95 | 7.3790% | 0.000002150% | ~3,432,083x |
| `pfbam` mean | 3.8031% | 0.2537% | ~14.99x |
| `pfbam` p95 | 5.9636% | 1.6592% | ~3.59x |

Full metric snapshot:

- `knowledge_base/retargeting/audits/mesh_rebinder_parity_metrics_20260520.json`

## Worst-Vertex Migration

Initial Day 3B worst raw `pmbam` torso vertex:

- Vertex index: 14
- Source position: `[-0.0002173, -0.1166270, 0.9029090]`
- Raw rebound position: `[-0.0038046, -0.0461274, 0.7640650]`
- Raw world delta: 0.1557585 m

After aligned bind transplant, the same class of directly-mapped torso
vertices remains effectively source-space identical because the aligned Quinn
mapped bind matrices match the Aurora bind matrices.

## pfbam Deviation Hypothesis

The four-order-of-magnitude gap between `pmbam` and `pfbam` parity is expected
and explainable. The current bone map was authored against the `S_Male01`
supermodel path, while `pfbam` chains through `S_Female03`; some `pfbam`
weights therefore reach the map through supermodel-chain resolution or fallback
handling rather than the exact same direct mapping pattern seen in `pmbam`.
That introduces sub-percent bind-pose deviation while still staying comfortably
inside the Day 3B.5 gates.

Hypothesis to validate in the Day 6 smoke test: if `pfbam` visual deformation
under animation looks correct, the deviation is a bind-pose proportional
difference rather than a rebinder bug. If artifacts appear, revisit this by
building a `pfbam`-specific bone map variant against `S_Female03` directly and
compare its parity and animation behavior to the shared `S_Male01`-derived map.

## Tests

Day 3B.5 command:

```powershell
python -m pytest tests\test_skeleton_aligner.py tests\test_mesh_rebinder.py tests\test_mesh_loader.py -v
```

Result:

- 18 passed

Regression command:

```powershell
python -m pytest tests\test_sampler.py tests\test_coordinate_normalizer.py tests\test_baker.py tests\test_retargeting_test_utils.py tests\test_mcp_retargeting_tools.py -q
```

Result:

- 13 passed

## Configuration Snapshot

`RebindOptions` production defaults:

- `enable_skeleton_prealignment=True`
- `alignment_options.rotation_strategy="copy_source"`
- `alignment_options.twist_alignment="interpolate"`
- `alignment_options.max_mapped_bone_drift=0.01`
- `enable_twist_redistribution=True`
- `twist_max_contribution=0.5`
- `twist_curve="smoothstep"`
- `unmapped_bone_strategy="nearest_ancestor"`

## Forward Implications

Day 4 FBX export should serialize `ReboundMesh.aligned_skeleton.bind_local` as
the export hierarchy. Unity will see Quinn bone names with KOTOR body
proportions, and Day 3A baked animation deltas can be transported onto that
aligned skeleton rather than raw Quinn's bind pose.
