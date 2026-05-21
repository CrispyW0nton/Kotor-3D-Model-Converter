# Retargeting Sampler G5 Parity Audit

Date: 2026-05-20

## Summary

Sprint 1 Day 2 added the first fixed-rate sampler for the bidirectional
retargeting pipeline. The sampler is intentionally a thin layer over existing
GhostRigger runtime math:

- Local animation pose evaluation is delegated to `AnimationEngine`.
- Supermodel resolution is delegated to `SuperModelResolver`.
- Skinning palette bake math is delegated to `MatrixPaletteUploader`.

No parallel controller interpolation or skinning formula was introduced.

## Implementation

New module:

- `src/core/retargeting/sampler.py`

Primary contracts:

- `SampledClip`: dense local-space TRS arrays with rotations stored as WXYZ.
- `resolve_supermodel_chain(model_resref, game)`: fixture-backed chain walk.
- `build_effective_controller_table(chain, clip_name)`: first-wins controller
  ownership report by node name.
- `sample_clip_to_fixed_rate(source_model, clip_name, fps)`: samples a clip into
  fixed-rate positions, rotations, and scales.

The sampler defaults to `tests/fixtures/kotor_stock`, so Sprint 1 tests no longer
depend on the live KOTOR install or its `Override/` state.

## G5 Bake Math Boundary

For every sampled frame, `sample_clip_to_fixed_rate` calls:

1. `AnimationEngine.evaluate(t)` to get the local node pose.
2. `MatrixPaletteUploader.compute_palette(pose, anim_base_pose=base_pose)`.

This keeps Day 2 on the existing G5 matrix palette path documented in
`knowledge_base/audits/2026-05/skinning_parity.md`. That audit is still the
numeric source of truth for the G5 gate:

- full vertex replay on audited creatures stayed within the established
  displacement bounds,
- renderer-vs-CPU palette decode stayed within the `5.345e-7` max-abs gate,
- G5 remains the production formula unless the environment switch explicitly
  requests a diagnostic fallback.

Day 2 did not rerun the expensive full creature capture set; it added a focused
contract test that proves the sampler invokes the G5 palette path once per
sampled frame.

## Frame-Zero Correction

The initial sprint text requested a stock test named
`test_frame_0_equals_bind_pose`. Local inspection showed that this assertion is
not valid for stock KOTOR clips. Many stock animation clips have frame-zero
controllers that differ from the static MDL bind pose.

The correct assertion for the sampler is:

`sampled frame 0 == AnimationEngine.evaluate(0.0)`

That is what `tests/test_sampler.py::test_frame_0_matches_animation_engine_pose`
pins. Static bind-pose equality remains a useful synthetic test later, but it is
not a stock-supermodel truth.

## Verification

Commands:

```powershell
python -m py_compile src\core\retargeting\sampler.py src\core\retargeting\__init__.py tests\test_sampler.py
python -m pytest tests\test_sampler.py tests\test_retargeting_test_utils.py tests\test_mcp_retargeting_tools.py -q
```

Result:

- `7 passed`

Sampler observations:

- `pmbam` resolves through `PMBAM -> S_Female02 -> S_Female01 -> S_Male02 -> S_Male01`.
- `pmbam:g1a1` is supplied by stock `S_Male02` in the isolated fixture corpus.
- `pmbam:walk` and `pmbam:run` also sample successfully from the fixture-backed chain.
- Each sampled frame records a successful G5 palette computation.

## Decision

Day 2 sampler foundation is ready for the Day 3 bake core. The retargeter should
continue to treat `AnimationEngine` plus `MatrixPaletteUploader` as the source of
truth until a later audit proves a specific divergence against xoreos/reone or
the retail engine.
