# FBX Exporter Day 4 Audit

Date: 2026-05-20
Status: PASS

## Scope

Day 4 implemented the first self-contained Unity-facing FBX export:

- Source mesh: `pmbam` torso from the isolated stock corpus
- Source clip: `g1a1`, resolved through the supermodel chain to `S_Male02`
- Target skeleton: Quinn, pre-aligned to `pmbam` by Day 3B.5
- Output shape: single FBX containing mesh, aligned skeleton, and one baked clip

Unity import verification is still Day 6. Day 4 only proves that GhostRigger can
create an internally consistent FBX that roundtrips through Blender.

## Documentation References

- Blender FBX exporter operator: https://docs.blender.org/api/current/bpy.ops.export_scene.html
- Blender background command-line execution: https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html
- Blender armature/edit-bone API notes: https://docs.blender.org/api/current/info_gotchas_armatures_and_bones.html
- Autodesk FBX axis-system reference: https://help.autodesk.com/cloudhelp/2020/ENU/FBX-API-Reference/cpp_ref/class_fbx_axis_system.html
- Unity FBX importer model/rig/animation overview: https://docs.unity.cn/Manual/class-FBXImporter.html

## Ground Truth

Day 4 ground-truth metadata:

- `knowledge_base/retargeting/ground_truth/day4_20260521_000000Z/g1a1_metadata.json`

Sanity gates:

- `g1a1` is available through `pmbam -> S_Female02 -> S_Female01 -> S_Male02 -> S_Male01`
- Resolved clip source: `S_Male02`
- Duration: 1.466670036315918 seconds
- Sample rate: 60 FPS
- Frame count: 89
- Controller bone count: 72
- The clip references mapped body bones

The requested `ghostrigger_get_animation_metadata` MCP tool is not exposed in
the current server surface. The metadata JSON records this and combines the
available MCP animation inventory with the Day 2 stock-corpus sampler metadata.

## Blender Invocation Contract

GhostRigger writes a deterministic intermediate JSON and invokes Blender 4.2 LTS
with:

```powershell
blender.exe --background --factory-startup --python scripts/blender_fbx_export.py -- --intermediate <json> --output <fbx> --options <json>
```

`--factory-startup` keeps user preferences out of the export. The Blender script
does not import GhostRigger modules; it only reads the intermediate JSON,
constructs an armature, mesh, and action, then calls `bpy.ops.export_scene.fbx`.

Detected Blender version:

- `Blender 4.2.0`

## Axis System Decision

Canonical retargeting space remains Z-up, right-handed, WXYZ quaternion space.
The FBX export uses:

- `axis_up="Z"`
- `axis_forward="-Y"`
- `primary_bone_axis="Y"`
- `secondary_bone_axis="X"`

Autodesk documents the MayaZUp/Max-style FBX system as +Z up, -Y forward,
right-handed. Blender 4.2 writes this into `GlobalSettings` as:

- `UpAxis=2`, `UpAxisSign=1`
- `FrontAxis=1`, `FrontAxisSign=1`
- `CoordAxis=0`, `CoordAxisSign=-1`

The Day 4 parser treats this full tuple as the exported `-Y` forward system.
Reading only `FrontAxisSign` would falsely report `+Y`.

## Artifact Paths

- FBX: `exports/retargets/day4/pmbam__g1a1__to__quinn_aligned.fbx`
- Manifest: `exports/retargets/day4/pmbam__g1a1__to__quinn_aligned.manifest.json`
- Intermediate JSON: `exports/retargets/day4/pmbam__g1a1__to__quinn_aligned_intermediate.json`
- Roundtrip JSON: `exports/retargets/day4/pmbam__g1a1__to__quinn_aligned.roundtrip.json`

FBX SHA-256:

- `bdd560848ac20bd8f1ac3718b8a28d274d2df13d36fa29dcf82f00a0f307bd67`

## Roundtrip Metrics

| Metric | Expected | Observed | Status |
|---|---:|---:|---|
| Bone count | 89 | 89 | PASS |
| Vertex count | 661 | 661 | PASS |
| Animation frames | 89 | 89 | PASS |
| Leaf bones | 0 | 0 | PASS |
| Axis up | `Z` | `Z` | PASS |
| Axis forward | `-Y` | `-Y` | PASS |
| Frame 0 rotation max delta | <= 1e-4 | 1.3700886175582738e-07 | PASS |

Bind-pose validation copied into the manifest:

- Alignment max drift: 0.0 m
- Weight conservation max drift: 3.3527612686157227e-08
- Normal unit max drift: 2.220446049250313e-16

## Manifest Schema Example

The sidecar manifest uses `schema_version="1.0"` and records:

- FBX path, hash, version, and Blender version
- Source mesh and aligned skeleton IDs
- Bone-map hash
- Clip inventory with frame count, FPS, duration, and source supermodel
- Bind-pose validation metrics
- Axis-system declaration and roundtrip metrics

This schema is intentionally multi-clip capable even though Day 4 exports only
`g1a1`.

## Blender 4.2 Quirks Observed

- Blender can print Python exceptions but still exit with code 0 in background
  mode; the wrapper therefore verifies the FBX path exists after subprocess
  completion.
- The FBX axis tuple needs `CoordAxisSign` to interpret the `-Y` forward
  declaration correctly.
- `add_leaf_bones=False` successfully prevents Blender from creating `_end`
  bones in the roundtripped file.
- The test suite writes temporary FBXs under `.pytest_tmp_fbx_exporter/` because
  this Windows user temp directory denied pytest access during the first run.

## Tests

Dedicated Day 4 suite:

```powershell
python -m pytest tests\test_fbx_exporter.py -v
```

Result:

- 10 passed

Regression suite:

```powershell
python -m pytest tests\test_sampler.py tests\test_coordinate_normalizer.py tests\test_baker.py tests\test_mesh_loader.py tests\test_mesh_rebinder.py tests\test_skeleton_aligner.py tests\test_retargeting_test_utils.py tests\test_mcp_retargeting_tools.py tests\test_fbx_exporter.py -q
```

Result:

- 42 passed

MCP dispatch smoke:

```powershell
$env:PYTHONPATH='src;.'; python - <<'PY'
from src.kotormcp.tools import handle_tool
# handle_tool("ghostrigger_export_unity_fbx", ...)
PY
```

Result:

- `ok: true`
- Payload size: 1309 bytes
- Validation status: `PASS`
- Smoke artifact: `exports/retargets/day4_mcp_smoke/pmbam__g1a1__to__quinn_aligned.fbx`

## Live Install Boundary

Day 4 used the isolated stock corpus and wrote only inside the GhostRigger
workspace. No commands wrote to
`C:\Program Files (x86)\Steam\steamapps\common\swkotor`.
