# Viewport Validator Specification

Date: 2026-05-21
Sprint: 3 R2.75

## Purpose

`src/core/validation/viewport_validator.py` provides the programmatic and CLI wrapper around Ghost Rigger's existing viewport renderer. It validates final MDL outputs through the same visual path users inspect in the application.

## Source APIs

- Loader: binary MDL/MDX uses `src.core.kotor_loader.load_model_from_bytes`; ASCII MDL uses `src.core.mdl_parser.MDLAsciiParser`.
- Renderer: `src.gui.qt_lib.rendering.viewport_core.FrameRenderer`.
- Camera: `src.gui.qt_lib.rendering.viewport_core.ArcBallCamera`.
- Animation: `src.core.animation_engine.AnimationEngine` and `SuperModelResolver`.
- Fixture supermodels: `src.core.retargeting.sampler.StockCorpusResourceManager` for `tests/fixtures/kotor_stock`.

## CLI

Run a bind-pose capture:

```powershell
python scripts\validate_mdl.py --mdl tests\fixtures\kotor_stock\k1\pmbam.mdl --frames 0 --output exports\calibration\baselines
```

Run an animation capture:

```powershell
python scripts\validate_mdl.py --mdl tests\fixtures\kotor_stock\k1\pmbam.mdl --animation g1a1 --frames 0,30,60,90,120 --output exports\calibration\baselines\g1a1
```

## Output Contract

The validator writes PNG captures and a JSON manifest containing:

- MDL path and SHA-256.
- Node, mesh, and available animation counts.
- Capture file paths.
- Per-frame node world positions and rotations.
- Optional SSIM scores against reference captures.
- Trust level when SSIM comparison is available.
- Errors and warnings.

## Current Baseline

Vanilla PMBAM from `tests/fixtures/kotor_stock/k1/pmbam.mdl` has:

- Nodes: 61
- Meshes: 44
- Inherited animations available through fixture supermodels: 267
- SHA-256: `f439fbdbf9e50ef994d14c333d0829017ad72bcfc1bf6f922420943e37ebf3f1`

## Known Limits

- The in-tree fixture currently contains no ASCII PMBAM fixture, so ASCII loading is covered by a conditional test.
- Camera names use historical `front_ortho` wording, but `FrameRenderer` still uses its perspective camera. The preset is canonical for validation framing, not an orthographic projection guarantee.
- Viewport-to-in-game calibration is a separate Gate 2.75 step and has not been completed by R2.75.
