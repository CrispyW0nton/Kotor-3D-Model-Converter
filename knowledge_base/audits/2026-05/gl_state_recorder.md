# GL State Recorder Audit - 2026-05-06

This is the Work item 2b follow-up to `knowledge_base/audits/2026-05/gpu_transparency_depth.md`.

## Scope

Targets:

- `k2:101peras` - Peragus wall / missing-surface symptom.
- `k2:c_brith` - semi-transparent-body symptom.

Goal:

- Capture per-draw GL state from `src/gui/gpu_renderer.py` using `GHOSTRIGGER_GL_STATE_TRACE`.
- Identify the first draw whose depth, cull, blend, lightmap, or substring-classification state differs from expected opaque-pass behavior.

## Recorder Status

The recorder is now available behind `GHOSTRIGGER_GL_STATE_TRACE`.

Trace path behavior:

- Unset, `0`, `false`, `no`, or `off`: tracing disabled.
- `1`, `true`, `yes`, or `on`: writes `exports/gl_state_trace.jsonl`.
- Any other value: treated as a custom JSONL output path.

Each draw record includes:

- Node name, render pass, program id, triangle count, texture names.
- Depth, cull, front-face, blend function, and blend equation state as observed by the renderer.
- `transparency_hint`, `txi_blending`, alpha-test, wateralpha, decal, skin, and dangly flags.
- `u_alpha`, `u_node_alpha`, `u_blend_mode`, `u_oit_enabled`, lightmap/env/spec flags, and feature mask.
- `is_face_mesh_name` and `is_inner_geometry_name`.

## Capture Attempt

The local headless capture attempted both targets with custom trace paths:

- `exports/gl_state_trace_101peras.jsonl`
- `exports/gl_state_trace_c_brith.jsonl`

Both models loaded, texture resolution completed, and CPU fallback renders succeeded. No JSONL traces were produced because the renderer never entered `_render_gpu()`.

Observed backend status:

- `101peras`: `image=True`, `backend=cpu`, `gpu_available=False`, `trace_exists=False`.
- `c_brith`: `image=True`, `backend=cpu`, `gpu_available=False`, `trace_exists=False`.

The blocking error remains:

```text
GpuRenderer: GPU init failed (cannot import name 'egl' from 'glcontext')
```

Because the trace hook records actual GPU draw calls, CPU fallback is not a valid substitute for Work item 2b's live GL-state question.

An interactive GUI capture was then attempted with:

```powershell
$env:GHOSTRIGGER_GL_STATE_TRACE="diagnostics\traces\2026_05\gl_state_trace_m03aa_05a_d0fa269.jsonl"
python main.py
```

This launched the real application, but toggling GPU mode hit the same backend failure before any GL draw calls:

```text
GpuRenderer: GPU init failed (cannot import name 'egl' from 'glcontext') - using CPU fallback
```

No `m03aa_05a` JSONL trace was produced. This means the blocker is not limited to the standalone headless script; the current `GpuRenderer` path on this Windows environment also requires the unavailable `glcontext` EGL backend.

Follow-up diagnosis showed the local install was healthy:

```text
glcontext 2.3.7 exposes _wgl and _egl
moderngl 5.12.0
moderngl.create_standalone_context() -> NVIDIA GeForce RTX 3090/PCIe/SSE2
```

The failure was caused by `GpuRenderer._ensure_context()` forcing `backend='egl'`. The renderer now selects platform-appropriate standalone backends: default/WGL first on Windows, EGL first on POSIX/headless systems. A smoke test confirmed `GpuRenderer._ensure_context()` succeeds on this Windows machine.

After that fix, scripted standalone GPU captures succeeded for:

- `diagnostics/traces/2026_05/gl_state_trace_m03aa_05a_d0fa269.jsonl`
- `diagnostics/traces/2026_05/gl_state_trace_101peras_d0fa269.jsonl`
- `diagnostics/traces/2026_05/gl_state_trace_c_brith_d0fa269.jsonl`
- `diagnostics/traces/2026_05/gl_state_trace_c_drexlf_d0fa269.jsonl`

The first `m03aa_05a` control attempt exposed a ResourceManager memory issue: Override indexing eagerly loaded every loose file into RAM. ResourceManager now indexes Override file paths and reads only the requested resource bytes, preserving Override priority without the startup memory spike. After that fix, the intended K1 control trace captured successfully.

## Captured Trace Results

Each trace contains a static frame plus four orbit frames.

Reduction summary:

```text
gl_state_trace_m03aa_05a_d0fa269.jsonl
rows 75, passes {'opaque': 75}, unique_nodes 15, bad 0, lightmap 70, env 0

gl_state_trace_c_drexlf_d0fa269.jsonl
rows 35, passes {'opaque': 35}, unique_nodes 7, bad 0, lightmap 0, env 0

gl_state_trace_101peras_d0fa269.jsonl
rows 170, passes {'opaque': 170}, unique_nodes 34, bad 0, lightmap 160, env 0

gl_state_trace_c_brith_d0fa269.jsonl
rows 5, passes {'opaque': 5}, unique_nodes 1, bad 0, lightmap 0, env 0
```

The `bad` reduction flags draws where any of these were true:

- Non-opaque pass.
- Depth writes disabled.
- Culling disabled.
- Blending enabled.
- `u_oit_enabled` non-zero.

No target draw matched those suspicious-state predicates.

Representative records:

```text
m03aa_05a control Rectangle23:
pass=opaque depth_writemask=True cull_face=True front_face=cw blend=False
u_node_alpha=1.0 u_oit_enabled=0 u_has_lm=1

c_drexlf control headGeo:
pass=opaque depth_writemask=True cull_face=True front_face=cw blend=False
u_node_alpha=1.0 u_oit_enabled=0 texture=c_drex01 u_has_lm=0
is_face_mesh_name=True is_inner_geometry_name=False

101peras mesh640:
pass=opaque depth_writemask=True cull_face=True front_face=cw blend=False
u_node_alpha=1.0 u_oit_enabled=0 texture=per_cpan lightmap=101peras_lm0 u_has_lm=1
is_face_mesh_name=False is_inner_geometry_name=False

c_brith Brith_mesh:
pass=opaque depth_writemask=True cull_face=True front_face=cw blend=False
u_node_alpha=1.0 u_oit_enabled=0 texture=c_brith01 u_has_lm=0
is_face_mesh_name=False is_inner_geometry_name=False
```

Notable caveat: ModernGL exposes some state getters incompletely on this backend. `depth_func`, `blend_func`, and `blend_equation` may appear as `None` in the trace because their property getters raise `NotImplementedError`; the recorder now tolerates that instead of aborting a draw.

## Texture Slot Audit

A 2c-prep reduction checked whether the diffuse slot is accidentally receiving lightmap or env-map resources.

Flagged conditions:

- Diffuse texture name looks like a lightmap (`_lm`, `_lm0`, `_lm1`, `lightmap`, etc.).
- Diffuse texture name looks like an env/cube-map convention.
- Diffuse texture name equals the lightmap texture name on the same draw.
- `u_has_tex != 1`.

Results:

```text
gl_state_trace_m03aa_05a_d0fa269.jsonl
draws 75, unique_diffuse 14, unique_lightmap 2, unique_env 0
flags diffuse_looks_lightmap 0, diffuse_looks_env 0, same_diffuse_lightmap 0, missing_tex 0

gl_state_trace_c_drexlf_d0fa269.jsonl
draws 35, unique_diffuse 1, unique_lightmap 0, unique_env 0
flags diffuse_looks_lightmap 0, diffuse_looks_env 0, same_diffuse_lightmap 0, missing_tex 0

gl_state_trace_101peras_d0fa269.jsonl
draws 170, unique_diffuse 16, unique_lightmap 7, unique_env 0
flags diffuse_looks_lightmap 0, diffuse_looks_env 0, same_diffuse_lightmap 0, missing_tex 0

gl_state_trace_c_brith_d0fa269.jsonl
draws 5, unique_diffuse 1, unique_lightmap 0, unique_env 0
flags diffuse_looks_lightmap 0, diffuse_looks_env 0, same_diffuse_lightmap 0, missing_tex 0
```

The texture-slot hypothesis is not supported by the captured traces. `101peras` binds expected Peragus diffuse textures such as `per_wl02`, `per_cpan`, and `per_fl05` in the diffuse slot while binding `101peras_lm*` resources in the lightmap slot. `c_brith` binds only `c_brith01` as diffuse and has no lightmap or env-map binding.

## Static Eliminations

The `c_brith` substring-classification hypothesis is now ruled out.

Static check across the loaded `c_brith` tree found only two renderable nodes matched the shared render constants:

```text
c_brith classified renderable mesh nodes: 2
L_Tooth_bone: face=False inner=True verts=96 faces=32
R_Tooth_bone: face=False inner=True verts=96 faces=32
```

`Brith_mesh`, the visible body mesh, does not match `is_face_mesh_name()` or `is_inner_geometry_name()`. The see-through-body symptom is therefore not caused by face/head substring overreach or accidental two-sided body routing.

The previous pass-classification audit still holds:

- `101peras`: all drawn surfaces classify as opaque, with fully opaque diffuse alpha.
- `c_brith`: the visible body draw is `Brith_mesh`, classified opaque, with fully opaque `c_brith01` alpha.
- `u_oit_enabled` remains `0` in the current renderer path.

## Remaining Hypotheses

For `101peras`, the unresolved candidates are:

- Live depth-write state differs from source-intended opaque pass state.
- Live cull/front-face state differs from the expected `front_face = 'cw'` and cull-face-enabled setup.
- Winding or one-sided wall geometry is being culled in the live view and visually reads as missing wall transparency.
- Lightmap composite state is wrong for one or more wall draws.

For `c_brith`, the unresolved candidates are narrower:

- Live depth or cull state differs for `Brith_mesh`.
- Lightmap/env/spec composite state on `Brith_mesh` is washing out the diffuse, though the model currently resolves only one diffuse texture in this headless path.
- The screenshot symptom belongs to animation/skinning or overlay state rather than alpha/depth pass routing.

## Live Trace Reduction

Once captured from a GUI/live ModernGL context, include:

- `101peras`, the missing-wall target.
- `c_brith`, the see-through-body target.
- A known-good control such as `m03aa_05a`.

Use the current build SHA in the trace filename, or write it to a sibling `.meta` file:

```powershell
$sha = git rev-parse --short HEAD
$env:GHOSTRIGGER_GL_STATE_TRACE="diagnostics\traces\2026_05\gl_state_trace_c_brith_$sha.jsonl"
python -m src.gui.main_window
```

For each target, capture one static frame and then a short 2-3 second camera orbit before closing. The static frame gives the cleanest state snapshot; the orbit catches state that only changes after camera or dirty-flag updates.

The first reduction should be:

```powershell
$env:GHOSTRIGGER_GL_STATE_TRACE="exports\gl_state_trace_c_brith.jsonl"
python -m src.gui.main_window
```

Then load `c_brith`, reproduce the view, and inspect:

```powershell
python -c "import json; from pathlib import Path; p=Path('exports/gl_state_trace_c_brith.jsonl'); rows=[json.loads(x) for x in p.read_text().splitlines() if x.strip()]; print(len(rows)); [print(r) for r in rows if r.get('node')=='Brith_mesh']"
```

Expected `Brith_mesh` state:

- `pass = "opaque"`
- `gl_depth_test = True`
- `gl_depth_writemask = True`
- `gl_cull_face = True`
- `gl_front_face = "cw"`
- `gl_blend_enabled = False`
- `transparency_hint = 0`
- `txi_blending = 0`
- `u_node_alpha = 1.0`
- `u_oit_enabled = 0`
- `is_face_mesh_name = False`
- `is_inner_geometry_name = False`

For `101peras`, reduce every non-opaque-looking draw with:

```powershell
python -c "import json; from pathlib import Path; rows=[json.loads(x) for x in Path('exports/gl_state_trace_101peras.jsonl').read_text().splitlines() if x.strip()]; bad=[r for r in rows if r.get('pass')!='opaque' or not r.get('gl_depth_writemask') or not r.get('gl_cull_face') or r.get('gl_blend_enabled') or r.get('u_oit_enabled')]; print(len(bad)); [print(r) for r in bad[:20]]"
```

Expected `101peras` opaque wall state:

- `pass = "opaque"`
- `gl_depth_writemask = True`
- `gl_cull_face = True`
- `gl_blend_enabled = False`
- `u_oit_enabled = 0`

The first draw that violates those expectations should become Work item 2c.

## Result

Work item 2b is now captured for the target models. The recorder is ready, the `c_brith` substring classifier hypothesis is eliminated, and the captured traces do not show a depth-write, blend, OIT, or substring-classification divergence for either target.

Work item 2c should not be an alpha/depth-pass fix based on these traces. The likely next scopes are narrower:

- For `101peras`, inspect lightmap composite/content for the wall nodes, because 160/170 draws bind lightmaps and the opaque GL state plus texture slot routing are otherwise normal.
- For `c_brith`, pivot to vertex data, shader output, animation/skinning, or overlay state, because `Brith_mesh` is a single opaque draw with normal material state, correct diffuse-slot routing, and no face/inner substring collision.
