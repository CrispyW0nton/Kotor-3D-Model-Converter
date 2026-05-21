# Sprint 3 R3 Animation Injection Report

Date: 2026-05-21
Status: PASS for R3.A extraction/adaptation and R3.B binary MDL injection; R3.C viewport playback renders successfully

## Scope

R3.A extracts a UE5 Manny/UEFN FBX animation through Blender, adapts source bone channels through the reverse UE5-to-Aurora rename policy, validates PMBAM target-bone coverage, and writes a retarget-ready JSON payload.

It does not yet write or compile a modified MDL. That is R3.B.

## Inputs

- Source FBX: `C:\Users\NewAdmin\Documents\KaiGenInteractive\AnimationLibrary\Exports\M_Neutral_Stand_Idle_Loop_export.fbx`
- Source FBX SHA-256: `20d4f1fe351aab873fbea54d66e38063665eceaeb4ca519004981c289b01a211`
- Target MDL: `tests/fixtures/kotor_stock/k1/pmbam.mdl`
- Target MDL SHA-256: `f439fbdbf9e50ef994d14c333d0829017ad72bcfc1bf6f922420943e37ebf3f1`
- Reverse rename map: `knowledge_base/retargeting/ue5_to_aurora_rename_map.json`
- Target slot: `victory`
- Output directory: `exports/r3_idle_test/`

## Tool Discovery

- Native Ghost Rigger MDL writer exists: `src/core/mdl_writer.py`
- Writer supports animation blocks through `MDLBinaryWriter._write_animation`
- KotorBlender is installed in Blender 4.2 under user extensions: `io_scene_kotor`
- Blender 4.2 executable found: `C:\Program Files\Blender Foundation\Blender 4.2\blender.exe`
- Blender 4.5 executable also found, but Sprint 3 extraction uses the validated 4.2 path
- MDLEdit CLI was not found under `C:\Users\NewAdmin` during discovery

## Outputs

- Raw Blender extraction: `exports/r3_idle_test/M_Neutral_Stand_Idle_Loop_export_r3a_extraction.json`
- Blender log: `exports/r3_idle_test/M_Neutral_Stand_Idle_Loop_export_r3a_extraction.blender.log`
- Retarget-ready payload: `exports/r3_idle_test/pmbam__victory__r3a_animation.json`
- Manifest: `exports/r3_idle_test/pmbam__victory__r3a_manifest.json`

## Metrics

- Source bones: 87
- Target PMBAM nodes: 61
- Mapped channels: 20
- Dropped channels: 64
- Collapsed channels: 3
- Unmapped channels: 0
- Frames: 302
- FPS: 30.0
- Duration: 10.0667 seconds

## Adapter Notes

- `attach` is accepted as a source-root alias for Aurora `rootdummy`
- UE5 fingers, IK helpers, twist bones, weapons, and known extras are dropped for PMBAM
- `spine_02`, `spine_04`, and `spine_05` are marked as collapse candidates for R3.B
- `neck_02` is treated as a known UE5 extra because PMBAM has no second neck segment

## R3.B Boundary

R3.B must consume `pmbam__victory__r3a_animation.json`, convert raw UE5 world-space source transforms into Aurora local animation controllers, inject or replace the `victory` animation on a PMBAM model object, and write the output through `MDLBinaryWriter`.

The likely implementation path is native Ghost Rigger binary write, not MDLEdit-first, because the repository already has an animation-capable binary writer.

## Verification

```powershell
python -m py_compile src\core\retargeting\ue5_source_adapter.py src\core\retargeting\blender_animation_injection.py src\core\retargeting\animation_injector.py scripts\blender_extract_ue5_animation.py scripts\inject_animation.py tests\test_animation_injector.py
python -m pytest tests\test_animation_injector.py -q --basetemp .pytest_tmp_anim_injector
python scripts\inject_animation.py --source-fbx "C:\Users\NewAdmin\Documents\KaiGenInteractive\AnimationLibrary\Exports\M_Neutral_Stand_Idle_Loop_export.fbx" --target-mdl tests\fixtures\kotor_stock\k1\pmbam.mdl --slot victory --rename-map knowledge_base\retargeting\ue5_to_aurora_rename_map.json --output exports\r3_idle_test --game K1
```

Result: R3.A PASS.

## R3.B Injection

R3.B now consumes the R3.A payload, computes source-local rotation deltas from UE5 parent/rest transforms, applies those deltas onto Aurora bind-local rotations, appends a local `victory` animation override to PMBAM, and writes binary MDL/MDX through `MDLBinaryWriter.write_files()`.

Key implementation details:

- `src/core/retargeting/coordinate_converter.py` implements the involutive UE5/Unity-style to Aurora quaternion/position conversion.
- `src/core/retargeting/aurora_animation_writer.py` builds Aurora animation controllers and writes binary MDL/MDX natively.
- `scripts/inspect_pmbam_animation.py` confirmed PMBAM has 0 local animations, 267 inherited animations, and inherited `victory`.
- `scripts/inject_animation.py --write-mdl` runs R3.A followed by R3.B.
- Position controllers are omitted in the first pass to preserve PMBAM bind proportions and keep binary size below the 2x stop condition; rotation controllers are written for 20 mapped Aurora bones.

R3.B artifacts:

- Output MDL: `exports/r3_idle_test/pmbam__victory__r3b.mdl`
- Output MDX: `exports/r3_idle_test/pmbam__victory__r3b.mdx`
- Manifest: `exports/r3_idle_test/pmbam__victory__r3b_manifest.json`
- Output MDL SHA-256: `bfcd3468838050d25159afa3c90d963fec1a06fcbfc64b6ea9982adc4a8be8df`
- Output MDX SHA-256: `84dc9b42faa0b2004c0e10eef6ab0bc65e02ee7bffaca027b829574832a58154`
- Output MDL size: 293,360 bytes vs. 188,736-byte vanilla input (1.55x; below 2x stop condition)
- Operation: `appended_local_override`
- Animated bones: 20
- Frames: 302 at 30 FPS

R3.B verification:

```powershell
python -m pytest tests\test_coordinate_converter.py tests\test_aurora_animation_writer.py tests\test_animation_injector.py -q --basetemp .pytest_tmp_r3b
python scripts\inject_animation.py --source-fbx "C:\Users\NewAdmin\Documents\KaiGenInteractive\AnimationLibrary\Exports\M_Neutral_Stand_Idle_Loop_export.fbx" --target-mdl tests\fixtures\kotor_stock\k1\pmbam.mdl --slot victory --rename-map knowledge_base\retargeting\ue5_to_aurora_rename_map.json --output exports\r3_idle_test --game K1 --write-mdl
```

Result: R3.B PASS.

## R3.C Viewport Gate

The modified binary MDL loads in the Ghost Rigger viewport and the injected local `victory` animation renders at five sampled frames.

Viewport artifacts:

- Validation JSON: `exports/r3_idle_test/viewport_captures/pmbam__victory__r3b_validation.json`
- Captures:
  - `exports/r3_idle_test/viewport_captures/pmbam__victory__r3b_victory_frame_0000.png`
  - `exports/r3_idle_test/viewport_captures/pmbam__victory__r3b_victory_frame_0075.png`
  - `exports/r3_idle_test/viewport_captures/pmbam__victory__r3b_victory_frame_0150.png`
  - `exports/r3_idle_test/viewport_captures/pmbam__victory__r3b_victory_frame_0225.png`
  - `exports/r3_idle_test/viewport_captures/pmbam__victory__r3b_victory_frame_0300.png`

Viewport metrics:

- Success: true
- Nodes: 61
- Meshes: 44
- Local animations: 1 (`victory`)
- Captures: 5
- Render time: 437.8 ms

R3.C verification:

```powershell
python scripts\validate_mdl.py --mdl exports\r3_idle_test\pmbam__victory__r3b.mdl --animation victory --frames 0,75,150,225,300 --output exports\r3_idle_test\viewport_captures --camera front_ortho
```

Result: R3.C STRUCTURAL PASS. Visual review confirms the catastrophic direct-world-rotation deformation was removed after switching to source-local rest-relative deltas. Remaining first-pass limitation: this is a 20-bone core-body transfer with no finger, head, twist, or translation controllers, so pose quality is proof-of-pipeline rather than final animation polish.
