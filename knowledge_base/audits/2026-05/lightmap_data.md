# Lightmap Data-Path Audit: 101peras

Date: 2026-05-06
Build: `d0fa269`

## Goal

Classify the `101peras` lightmap symptom into exactly one domain:

- A: UV1 / lightmap UV data on the model node
- B: GPU VBO packing or UV1 attribute binding
- C: lightmap role / dispatch
- D: lightmap composite math or lightmap texture content

This audit follows the previous GL-state and debug-visualization audits. Those ruled out alpha collapse, blend/depth/cull/OIT state, texture-slot misbinding, and the UV0/UV1 shader typo.

## Instrumentation

Added `GHOSTRIGGER_LM_DATA_DUMP=<path>` in `src/gui/gpu_renderer.py`.

The dump is independent from `GHOSTRIGGER_GL_STATE_TRACE`, inert when unset, and appends crash-safe JSONL records once per unique lightmapped node per renderer session. Each record captures model-side UV arrays and the VBO-uploaded UV columns so model data and packing bugs can be separated.

Captured fields include:

- `pass`, `node`, `program_id`
- `vertex_count`, `uploaded_vertex_count`
- `len_uvs`, `len_uvs_lm`
- `first8_uv0_model`, `first8_uv1_model`
- `first8_uv0_uploaded`, `first8_uv1_uploaded`
- `has_lightmap`, `lightmap_role_inferred`, `effective_lightmap`
- `dispatch_path`, `slot1_role`
- `lightmap_texture_name`, `lightmap_bound`
- `uv1_attribute_bound`, `uv1_vbo_id`
- `lightmap_uniforms.u_has_lm`, `u_lm_shade`, `u_lm_tex`, `u_debug_visualize`

## Captures

Captured with `GHOSTRIGGER_LM_DATA_DUMP` set and `GHOSTRIGGER_DEBUG_VIZ=0`.

- `diagnostics/lm_data/2026_05/lm_data_m03aa_05a_d0fa269.jsonl`
- `diagnostics/lm_data/2026_05/lm_data_101peras_d0fa269.jsonl`
- `c_brith` negative control produced no dump file, confirming no lightmap path was engaged.

Capture counts:

- `m03aa_05a`: 14 lightmapped records
- `101peras`: 32 lightmapped records
- `c_brith`: 0 lightmapped records

## Reductions

### 1. UV1 Length Parity

For every draw with `effective_lightmap=true`, `len_uvs_lm == vertex_count`.

Result:

- `m03aa_05a`: 0 mismatches
- `101peras`: 0 mismatches

Conclusion: no evidence for A.

### 2. UV1 Sanity

Checked sampled `first8_uv1_model` and `first8_uv1_uploaded` pairs for NaN/inf, values outside `[-8, 8]`, and exact `(0, 0)` pairs.

Result:

- `m03aa_05a` model UV1: 112 sampled pairs, 0 NaN/inf, 0 outside range, 0 exact zero pairs
- `m03aa_05a` uploaded UV1: 112 sampled pairs, 0 NaN/inf, 0 outside range, 0 exact zero pairs
- `101peras` model UV1: 252 sampled pairs, 0 NaN/inf, 0 outside range, 0 exact zero pairs
- `101peras` uploaded UV1: 252 sampled pairs, 0 NaN/inf, 0 outside range, 0 exact zero pairs

Conclusion: no evidence for A or B.

### 3. Dispatch Parity

Grouped by `dispatch_path` and `slot1_role`.

Result:

- `m03aa_05a`: all 14 records are `Case A`, `slot1_role=lightmap`
- `101peras`: all 32 records are `Case A`, `slot1_role=lightmap`

Every lightmapped draw had `lightmap_bound=true`.

Conclusion: no evidence for C.

### 4. Attribute Binding Sanity

Checked every lightmapped draw for `uv1_attribute_bound=true`.

Result:

- `m03aa_05a`: 0 unbound UV1 attributes
- `101peras`: 0 unbound UV1 attributes

Conclusion: no evidence for B.

### 5. CPU/GPU UV1 Parity

Compared `first8_uv1_model` against `first8_uv1_uploaded` for each lightmapped draw.

Result:

- `m03aa_05a`: 0 divergent nodes
- `101peras`: 0 divergent nodes

Conclusion: no evidence for B. Model UV1 and uploaded VBO UV1 agree for sampled data.

## Classification

Classification: D.

The audit found no UV1 length/data issue, no VBO UV1 packing or attribute-binding issue, and no lightmap role/dispatch issue. `101peras` enters the expected lightmap draw path with valid UV1 data, a bound lightmap texture, and `u_has_lm=1`, `u_lm_shade=1`, matching the K1 control pattern.

The remaining domain is lightmap composite math or lightmap texture content.

## Follow-Up Scope

Open Work item 2h: investigate lightmap composite math or lightmap texture content.

Recommended next checks:

- Dump per-lightmap texture stats for `101peras_lm0` and `101peras_lm1`: dimensions, mean RGB, min/max RGB, alpha range, and sample hashes.
- Capture debug-viz mode 4 with per-node isolation for the first visually bad `101peras` mesh.
- Compare the current shader composite formula against KotOR.js / reone for area lightmap overbright and ambient floor behavior.
- If texture content is clean, test a temporary shader toggle that renders `diffuse * lightmap * 2.0` with no ambient floor or extra clamp behavior to isolate composite math.

## Pre-Staged Reduction Script

```powershell
$script = @'
import json, math
from collections import Counter
from pathlib import Path

base = Path("diagnostics/lm_data/2026_05")
files = [
    base / "lm_data_m03aa_05a_d0fa269.jsonl",
    base / "lm_data_101peras_d0fa269.jsonl",
]

def bad_count(pairs):
    nan_inf = outside = zeros = total = 0
    for uv in pairs:
        if len(uv) < 2:
            continue
        total += 1
        vals = [float(uv[0]), float(uv[1])]
        if any(not math.isfinite(v) for v in vals):
            nan_inf += 1
        if any(abs(v) > 8 for v in vals):
            outside += 1
        if vals[0] == 0.0 and vals[1] == 0.0:
            zeros += 1
    return {"sampled_pairs": total, "nan_inf": nan_inf, "outside_abs8": outside, "exact_zero_pairs": zeros}

for path in files:
    recs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    lm = [r for r in recs if r.get("effective_lightmap")]
    print(f"FILE {path}")
    print("records", len(recs), "effective_lightmap", len(lm))
    print("uv1_length_mismatch", [r["node"] for r in lm if r.get("len_uvs_lm") != r.get("vertex_count")])
    print("uv1_attr_unbound", [r["node"] for r in lm if not r.get("uv1_attribute_bound")])
    print("lm_not_bound", [r["node"] for r in lm if not r.get("lightmap_bound")])
    print("bad_slot_role", [(r["node"], r.get("slot1_role"), r.get("dispatch_path")) for r in lm if r.get("slot1_role") not in ("lightmap", "N/A")])
    print("dispatch_counts", dict(Counter((r.get("dispatch_path"), r.get("slot1_role")) for r in recs)))
    print("uv1_model_sanity", bad_count([uv for r in lm for uv in r.get("first8_uv1_model", [])]))
    print("uv1_uploaded_sanity", bad_count([uv for r in lm for uv in r.get("first8_uv1_uploaded", [])]))
    parity = []
    for r in lm:
        m = r.get("first8_uv1_model", [])
        u = r.get("first8_uv1_uploaded", [])
        diffs = [
            max(abs(float(m[i][0]) - float(u[i][0])), abs(float(m[i][1]) - float(u[i][1])))
            for i in range(min(len(m), len(u)))
        ]
        maxdiff = max(diffs) if diffs else 0.0
        if maxdiff > 1e-6:
            parity.append((r["node"], maxdiff))
    print("model_uploaded_uv1_divergence", parity, "count", len(parity))
    print()
'@
python -c $script
```
