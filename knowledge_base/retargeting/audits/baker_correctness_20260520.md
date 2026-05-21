# Sprint 1 Day 3A Baker Correctness Audit

Date: 2026-05-20

## Scope

Day 3A implemented the canonical coordinate normalizer and pure animation bake
core only. Mesh rebinding, FBX export, Unity validation, and Aurora hand-off
artifacts remain out of scope until later sprint days.

## MCP Ground Truth

Captured after live MCP queries and before code changes:

- `knowledge_base/retargeting/ground_truth/day3a_20260520_224749Z/aurora_pmbam_skeleton.json`
- `knowledge_base/retargeting/ground_truth/day3a_20260520_224749Z/aurora_smale01_skeleton.json`
- `knowledge_base/retargeting/ground_truth/day3a_20260520_224749Z/ue5_quinn_skeleton.json`
- `knowledge_base/retargeting/ground_truth/day3a_20260520_224749Z/bone_map_smale01_to_quinn.json`
- `knowledge_base/retargeting/ground_truth/day3a_20260520_224749Z/animation_inventory.json`
- `knowledge_base/retargeting/ground_truth/day3a_20260520_224749Z/sanity_summary.json`

Sanity gates:

| Gate | Result |
|---|---:|
| Direct S_Male01 -> Quinn mappings | 27 |
| Derived Quinn mappings | 20 |
| PMBAM chain includes S_Male02/S_Male01 | PASS |
| `g1a1`, `walk`, `run` available through chain | PASS |
| Quinn asset bone count | 89 |
| Quinn twist bones observed | 16 |
| Live `custom_mixamo_a1` noise still observed | Expected |

## Coordinate Space Verification

`src/core/retargeting/coordinate_normalizer.py` is now the single conversion
point for Day 3A retargeting math:

- Canonical transform space: world-space, Z-up, right-handed.
- Canonical quaternion order: WXYZ.
- Aurora/KotOR input rotations are converted from GhostRigger `ModelNode`
  XYZW into WXYZ at the boundary.
- The normalizer cross-checks its world inverse-bind matrices against
  `MatrixPaletteUploader.build_inverse_bind_pose()`.
- Quinn is normalized from the existing GhostRigger Quinn `KotorModel`; raw FBX
  axis conversion is intentionally deferred to Day 4's import/export boundary.

G5 parity:

| Model | G5 inverse-bind max abs delta | Gate |
|---|---:|---:|
| `S_Male01` fixture | `6.661338147750939e-16` | `<= 5.4e-7` |

## Baker Verification

Implemented `src/core/retargeting/baker.py`:

- `compute_bind_offsets(source, target, bone_map)`.
- `bake_retargeted_clip(sampled, source, target, bone_map, offsets)`.
- Identity no-op path for same-skeleton retargets.
- World-space source pose lift and target local-space drop.
- Target-shaped output as `SampledClip`.
- First-pass derived twist rotation for unmapped Quinn twist bones.

Identity retarget metrics are written to:

- `diagnostics/retargeting/day3a_baker_metrics.json`

| Metric | Value | Gate |
|---|---:|---:|
| Identity position max abs delta | `0.0` | Informational |
| Identity scale max abs delta | `0.0` | Informational |
| Identity rotation max WXYZ component delta | `0.0` | `<= 1e-5` |
| Identity frame count | `45` | Informational |
| Identity bone count | `82` | Informational |

## Tests

Command:

```powershell
python -m pytest tests\test_coordinate_normalizer.py tests\test_baker.py -v
```

Result:

```text
6 passed in 13.16s
```

Regression command:

```powershell
python -m pytest tests\test_sampler.py tests\test_retargeting_test_utils.py tests\test_mcp_retargeting_tools.py -q
```

Result:

```text
7 passed in 15.59s
```

## Live Install Boundary

Day 3A did not write to `C:\Program Files (x86)\Steam\steamapps\common\swkotor`.
The latest observed live KOTOR write timestamps after Day 3A remained earlier
than the Day 3A implementation window; the newest entries were user/runtime or
Patch Manager-owned files such as `swkotor.ini`, `patch_config.toml`, and the
known Patch Manager DLL/Override artifacts.

## Stop-Condition Status

PASS.

- Normalizer/G5 parity: `6.661338147750939e-16`, below `5.4e-7`.
- Identity retarget deviation: `0.0`, below `1e-5`.
- No live KOTOR install mutation was performed.

## Known Limits

- The current bake core is coherent enough for Day 3A tests, but it is not yet
  the final export path. Day 3B must add mesh rebinding before FBX output can be
  considered production-meaningful.
- Quinn raw FBX axis conversion is documented but not exercised here because
  the bundled Quinn loader already returns a GhostRigger `KotorModel`.
- Twist handling is a first-pass derived rotation path for animation bake tests;
  mesh-weight twist redistribution belongs to Day 3B.
