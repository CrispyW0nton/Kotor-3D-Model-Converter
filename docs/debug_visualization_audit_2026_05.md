# Debug Visualization Audit - 2026-05-06

This is the Work item 2c-prep shader discriminator following `docs/gl_state_recorder_audit_2026_05.md`.

## Scope

Targets:

- `k2:c_brith`
- `k2:101peras`

Capture set:

- `GHOSTRIGGER_DEBUG_VIZ=0` - normal render.
- `GHOSTRIGGER_DEBUG_VIZ=1` - solid red for every rasterized fragment.
- `GHOSTRIGGER_DEBUG_VIZ=2` - final alpha as grayscale.
- `GHOSTRIGGER_DEBUG_VIZ=3` - diffuse sample only.
- `GHOSTRIGGER_DEBUG_VIZ=4` - lightmap sample only.

Artifacts:

- `diagnostics/debug_viz/2026_05/c_brith_debugviz_contact_d0fa269.png`
- `diagnostics/debug_viz/2026_05/101peras_debugviz_contact_d0fa269.png`
- Per-mode PNGs and matching JSONL traces are in `diagnostics/debug_viz/2026_05/` and `diagnostics/traces/2026_05/`.

## Screenshots

`c_brith`:

![c_brith debug visualization](../diagnostics/debug_viz/2026_05/c_brith_debugviz_contact_d0fa269.png)

`101peras`:

![101peras debug visualization](../diagnostics/debug_viz/2026_05/101peras_debugviz_contact_d0fa269.png)

## Image Statistics

```text
c_brith
mode 0 normal        non_bg 5764, redish 0,    whiteish 0,    blackish 62
mode 1 solid_red     non_bg 5788, redish 5455, whiteish 0,    blackish 0
mode 2 alpha_gray    non_bg 5788, redish 0,    whiteish 5334, blackish 0
mode 3 diffuse_only  non_bg 5780, redish 0,    whiteish 3,    blackish 52
mode 4 lightmap_only non_bg 5674, redish 0,    whiteish 0,    blackish 5455

101peras
mode 0 normal        non_bg 18404, redish 1,     whiteish 1484,  blackish 364
mode 1 solid_red     non_bg 18491, redish 17894, whiteish 0,     blackish 0
mode 2 alpha_gray    non_bg 18491, redish 0,     whiteish 17465, blackish 0
mode 3 diffuse_only  non_bg 18465, redish 0,     whiteish 0,     blackish 5
mode 4 lightmap_only non_bg 18404, redish 4,     whiteish 144,   blackish 211
```

## Findings

`c_brith`:

- Mode 1 renders a solid red silhouette, so `Brith_mesh` reaches the rasterizer and is not being lost before fragment color output.
- Mode 2 is fully white over the mesh, so final shader alpha is not collapsing.
- Mode 3 closely matches mode 0, so the normal color path is essentially diffuse-only for this model.
- Mode 4 is black, as expected, because `c_brith` has no lightmap binding.

Conclusion: the captured `c_brith` issue is not a GL state, alpha, texture-slot, or fragment-shader composite problem. If the GUI screenshot still looks see-through, the remaining likely causes are animation/skinning pose, skeleton/debug overlay, or vertex/palette data in the animated path rather than the static material path captured here.

`101peras`:

- Mode 1 renders the room as solid red wherever geometry exists, so the missing-wall symptom is not caused by fragments failing to reach the shader.
- Mode 2 is fully white over rendered geometry, so alpha is not collapsing.
- Mode 3 shows the diffuse-only room without the bright/mottled lightmap contribution.
- Mode 4 shows the baked lightmap contribution directly and carries the strongest visible high-contrast/color variation.

Conclusion: the `101peras` symptom is not caused by GL pass state, alpha, texture-slot routing, or vertex data failing to rasterize. The next suspect is the lightmap content/composite path: either decoded lightmap content, lightmap UVs, or the single-pass `diffuse * (lightmap * 2.5 + 0.03)` composite is producing the visual artifact.

## Next Work Item

Work item 2c should split by target:

- `101peras`: inspect lightmap texture content and lightmap UVs for the wall nodes identified in the trace, then compare the current shader composite against the expected KotOR lightmap formula.
- `c_brith`: move out of the transparency/lightmap track and into animation/skinning or overlay diagnostics. Static rendering is opaque, diffuse-driven, and alpha-correct.
