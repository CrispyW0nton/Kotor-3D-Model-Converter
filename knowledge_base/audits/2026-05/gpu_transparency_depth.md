# GPU Transparency And Depth Audit - 2026-05-06

This is a findings-first audit for Work item 2 from `knowledge_base/audits/2026-05/visual_performance.md`. No production renderer code was changed.

## Targets

- `k2:101peras` - Peragus room target from the transparency/missing-wall screenshot family
- `k2:c_brith` - creature target from the semi-transparent-body screenshot family

Both resrefs exist in the local K2 install and load successfully.

## Method

The audit used two sources:

- Static inspection of `src/gui/gpu_renderer.py` pass setup, depth/blend state, and shader uniforms.
- A diagnostic-only Python trace that mirrors the current GPU node classification logic for each target model and records each intended draw pass, depth-write state, blend mode, OIT flag, texture alpha range, and material alpha fields.

Attempting to run the real headless `GpuRenderer` on this machine fell back to CPU because `glcontext` could not provide EGL:

`cannot import name 'egl' from 'glcontext'`

Because of that, this document does not claim live driver GL-state capture. It does, however, capture the renderer's intended pass state from the current source and loaded model data.

## Renderer State From Source

The current GPU path sets frame-level state as:

- `DEPTH_TEST` enabled.
- `depth_func = '<='`.
- `depth_mask = True` after clear.
- `front_face = 'cw'`.
- `CULL_FACE` enabled.
- `u_oit_enabled = 0` during per-frame uniform initialization.

Pass state:

- Opaque pass: `depth_mask = True`, `BLEND` disabled before drawing.
- Cutout pass: `depth_mask` remains `True`; blending is not enabled by the pass itself. Per-node shader discard only happens when `_draw_node()` sets `u_blend_mode = 2`.
- Transparent pass: entered only if `transparent_nodes` is non-empty; it sorts back-to-front, sets `depth_mask = False`, draws, then restores `depth_mask = True` and disables blending.

No code path currently enables `u_oit_enabled = 1` for these draws. OIT is present in the shader but effectively dormant in the current renderer path.

## Diagnostic Trace Results

`101peras`:

- Model classification: `effect`, `model_type = 0`, treated as module geometry.
- Node count: 49.
- Drawn mesh counts: 34 opaque, 0 cutout, 0 transparent.
- Skipped render-false meshes: 1.
- All drawn diffuse texture alpha ranges were `[255, 255]`.
- No draw had `transparency_hint > 0`.
- No draw had `txi_blending != 0`.
- No draw had `alpha < 1.0`, `wateralpha < 1.0`, or decal enabled.
- No classification-vs-draw blend mismatch was found.

`c_brith`:

- Model classification: `flyer`, `model_type = 64`, not module geometry.
- Node count: 21.
- Drawn mesh counts: 1 opaque, 0 cutout, 0 transparent.
- Skipped render-false meshes: 17.
- The only drawn mesh is `Brith_mesh`.
- `Brith_mesh` state: `transparency_hint = 0`, `alpha = 1.0`, `txi_blending = 0`, `txi_alpha_test = 0.5`, `wateralpha = 1.0`, blend disabled, depth writes on.
- `c_brith01` alpha range after decode is `[255, 255]`.
- No classification-vs-draw blend mismatch was found.

## Findings

The originally suspected broad causes are not supported by current data for these targets:

- Opaque geometry is not being routed into the transparent pass.
- `u_oit_enabled` is not globally active.
- The target draw calls do not request GL blending.
- The target texture alpha channels decode as fully opaque.
- `c_brith`'s visible body draw is a single opaque draw with depth writes enabled.

For `101peras`, the trace says every drawn surface is opaque. If the GUI screenshot shows missing/transparent walls, the next likely causes are outside pass classification:

- Actual live GL state differs from the source-intended state in the GUI context.
- Culling/winding or camera clipping is removing faces, but the visual symptom is being read as transparency.
- The visible issue comes from a room/visibility/scene selection layer rather than this model's draw-pass routing.
- A texture/lightmap decode or upload artifact is making opaque surfaces look absent, even though pass state is opaque.

For `c_brith`, the semi-transparent-body hypothesis is not supported. The only drawn body mesh is fully opaque in loaded material state and decoded texture alpha. If the screenshot appears see-through, the more likely explanations are:

- Debug/proxy/skeleton overlay is visually confusing the body silhouette.
- Skinning/palette deformation moves opaque body geometry away from expected position, exposing internal bone/proxy geometry.
- The screenshot came from a different render path or UI state than the traced GPU path.

## Root-Cause Status

This audit did not find a production-code bug in alpha classification or OIT gating for `101peras` or `c_brith`.

It did find a diagnostic limitation: live GL-state capture cannot run in this headless environment until the local GPU context dependency issue is fixed. To finish the original "per draw live state" request, the next diagnostic should run inside the GUI/active ModernGL context or add a temporary debug hook that records state in the live viewport path.

## Recommended Next Step

Do not change alpha/depth production logic based on this pass.

The next transparency/depth diagnostic should be one of:

1. Add a temporary GUI-only draw-state recorder behind an environment flag, then capture actual state for `101peras` in the live viewport.
2. If the screenshot issue reproduces in CPU fallback too, pivot away from GPU pass state and inspect room visibility, face culling, and texture/lightmap decode/upload for `101peras`.
3. For `c_brith`, move this symptom into the animation/skinning audit, because current material and pass state are fully opaque.

## Artifacts

- Diagnostic trace target output was generated for `101peras` and `c_brith`.
- Headless GPU smoke render attempted both targets but used CPU fallback due missing EGL support.
