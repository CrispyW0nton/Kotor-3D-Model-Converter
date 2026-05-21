# Sprint 3.5 Phase 1 Quality Audit - R3.B PMBAM Victory

Date: 2026-05-21

Status: R4 BLOCKED. Current R3.B output is structurally valid but does not meet Tier 3 viewport quality.

## Locked Decisions

- R4 live testing is blocked until Tier 3 quality is reached in Ghost Rigger viewport.
- Locked Principle #12 is active: live in-game testing is reserved for engine fidelity; animation quality must be achieved in viewport first.
- Tier 3 is the R4 gate: stable mesh, anatomically plausible idle pose, smooth motion, and no visible deformation.

## Inputs

- MDL under audit: `exports/r3_idle_test/pmbam__victory__r3b.mdl`
- MDL SHA-256: `bfcd3468838050d25159afa3c90d963fec1a06fcbfc64b6ea9982adc4a8be8df`
- Animation: `victory`
- Source UE5 clip: `M_Neutral_Stand_Idle_Loop_export.fbx`
- Baseline rest render: `exports/calibration/baselines/pmbam_validation.json`
- Vanilla comparison: `tests/fixtures/kotor_stock/k1/pmbam.mdl`, animation `g1a1`

## Captures Generated

- Front, 11 frames: `exports/r3_idle_test/quality_audit/front/`
- Three-quarter, 5 frames: `exports/r3_idle_test/quality_audit/three_quarter/`
- Side-left, 5 frames: `exports/r3_idle_test/quality_audit/side_left/`
- Back, 5 frames: `exports/r3_idle_test/quality_audit/back/`
- Full-motion 64x64 renderer pass, 302 frames: `exports/r3_idle_test/quality_audit/full_motion_64/`
- Vanilla `g1a1` comparison, 6 frames: `exports/r3_idle_test/quality_audit/vanilla_g1a1/`
- Bone-position audit JSON: `exports/r3_idle_test/quality_audit/bone_position_audit.json`

## Diagnostic Tooling Note

The first multi-angle pass revealed a viewport-validator bug: `FrameRenderer.render_still()` set legacy `cam.az` / `cam.el`, but `ArcBallCamera` uses `azimuth` / `elevation`. That made front, side, back, and three-quarter captures byte-identical. The renderer was fixed to set and restore both property sets. The regenerated frame-150 hashes now differ by camera:

- front: `0061e6c07c462afef569ff9204287037b4381890d3fb0e0d5f40225a83bf1c2a`
- side-left: `7f95e3cb32cb330d7842a4a4a10163f8d70a3af3dc0e6755a89966c67cdb6d90`
- three-quarter: `cb514e03da799267227c13ee258b2a2cbfab2be5d31de9a5306d51bab93e0a9c`
- back: `305a4dc1a252c68a9137e615781200cff26baa96898e4b6da5968b33ed398518`

## Programmatic Audit Results

Renderer-derived full-motion audit across all 302 frames:

- Parent-child length issues at 5% tolerance: 0
- Frame-to-frame motion jumps over 10 mm: 0
- Render/load failures: 0

Interpretation: the current output is stable and smooth from the renderer's transform perspective. The failure is pose correctness, not binary validity, animation playback, length stretch, or frame popping.

## Issue Catalog

### I001 - Full-body pose is not an idle stance

- Frames: all sampled frames, visible from frame 0 onward
- Body part: pelvis, torso, upper torso, legs
- Type: wrong orientation / wrong pose
- Severity: 5
- Description: PMBAM is crouched and twisted instead of standing in a relaxed idle. The torso is pitched and the lower body is folded.
- Evidence: `front/pmbam__victory__r3b_victory_frame_0000.png`, `side_left/pmbam__victory__r3b_victory_frame_0150.png`
- Likely cause: source-local UE5 deltas are being applied directly in Aurora local bone axes without a per-bone basis conversion between UE5 rest local axes and Aurora rest local axes.

### I002 - Shoulders and arms are anatomically wrong

- Frames: all sampled frames
- Body part: clavicles, biceps, forearms, hands
- Type: wrong orientation / limb placement
- Severity: 4
- Description: arms do not hang naturally; the right arm and hand are held in an unnatural shape, and the left side is pulled across/near the body depending on view.
- Evidence: `three_quarter/pmbam__victory__r3b_victory_frame_0150.png`, `back/pmbam__victory__r3b_victory_frame_0150.png`
- Likely cause: same per-bone basis mismatch as I001, amplified by shoulder local-axis differences. Missing twist/finger channels are secondary.

### I003 - Lower body is folded rather than balanced

- Frames: all sampled frames
- Body part: pelvis, thighs, shins, feet
- Type: wrong pose
- Severity: 4
- Description: the character does not keep a balanced standing idle. Legs are visibly crouched/folded.
- Evidence: `side_left/pmbam__victory__r3b_victory_frame_0150.png`
- Likely cause: UE5 thigh/pelvis local deltas need basis remapping before being multiplied onto Aurora bind rotations.

### I004 - Fine bones are static or underdriven

- Frames: all sampled frames
- Body part: fingers, head/neck extras, twist regions
- Type: missing channel coverage
- Severity: 2
- Description: R3.B maps 20 core bones and drops UE5 fingers/twists/extras. This is expected to make hands and twist regions stiff.
- Likely cause: intentionally deferred H4 work.
- Blocking: not the first blocker; solve I001-I003 before expanding mapping.

### I005 - Vanilla comparison quality gap

- Frames: compared against vanilla `g1a1`
- Body part: full body
- Type: visual quality gap
- Severity: 5
- Description: vanilla KOTOR animation shows coherent authored poses in the same renderer. R3.B playback is smooth but not anatomically plausible.
- Evidence: `vanilla_g1a1/pmbam_g1a1_frame_0000.png` versus R3.B frame captures.

## Root Cause Ranking

1. H2 revised: missing per-bone basis conversion between source UE5 local delta axes and Aurora local axes. Highest likelihood; explains full-body wrong pose with zero length/popping issues.
2. H3: first-pass spine collapse policy may worsen torso posture after basis conversion is fixed.
3. H4: missing fingers/twists/head extras will affect polish but is unlikely to be the main cause of the crouched full-body pose.
4. H5: no translation transfer is not the main blocker for an idle pose.
5. H1 original: parent-animation cascade was a good suspicion, but source-local parent/rest deltas are already in the current R3.B path. Remaining issue is more likely local basis mapping than parent cascade.

## Phase 1 Gate Answers

1. Distinct issues: five documented, with I001-I003 sharing one likely root cause.
2. Shared root cause: per-bone source-to-target local-axis basis mismatch.
3. Retargeting math status: structurally stable but incomplete. Binary writing, animation slot override, playback, and smoothness are working; pose mapping is not Tier 3.
4. Distance to Tier 3: not close visually. This is not a live-test candidate. It is a targeted math refinement sprint, not a full rewrite.

## Recommended Fix Order

1. Implement per-bone basis remapping:
   - derive source local rest orientation per mapped UE5 bone,
   - derive target Aurora local rest orientation,
   - convert source local animation delta into target local basis before applying to target bind rotation.
2. Add quaternion hemisphere continuity before writing controller rows.
3. Re-render the exact same quality-audit capture set.
4. If torso remains wrong, refine spine collapse policy.
5. Only after body pose is plausible, expand H4 bone coverage for hands/head/twist polish.

## R4 Decision

R4 remains blocked. The current MDL is proof of binary injection and viewport playback only; it does not satisfy Tier 3 quality.

---

# Sprint 3.5 Phase 2 Update - Basis Remap + Clip Reference

Date: 2026-05-21

Status: Tier 2+ candidate only. Phase 2 improved stability and motion, but it is not promoted to Tier 3 until Phase 3 ground-truth verification completes.

## Phase 2 Inputs

- Source FBX: `C:/Users/NewAdmin/Documents/KaiGenInteractive/AnimationLibrary/Exports/M_Neutral_Stand_Idle_Loop_export.fbx`
- Target MDL: `tests/fixtures/kotor_stock/k1/pmbam.mdl`
- Output MDL: `exports/r3_idle_test_v2/pmbam__victory__r3b_v2.mdl`
- Output MDX: `exports/r3_idle_test_v2/pmbam__victory__r3b_v2.mdx`
- Output MDL SHA-256: `903bd5214080d69762a962a234c56fc5b19de2ba5043eabdf251d58b0a39454c`
- Animation slot: `victory`
- Frame count: 302 at 30 FPS
- Animated bones: 20

## What Changed

Phase 2 implemented the planned per-bone basis remapping and uncovered one additional, decisive retargeting requirement:

1. R3.A now emits UE5 rest-pose basis metadata per source bone:
   - `world_matrix_at_rest`
   - `data_bone_matrix`
   - `head`
   - `tail`
   - `rotation_wxyz`
   - `location_xyz`
2. R3.B computes a per-target-bone basis bridge where `M` sends Aurora local coordinates into UE5 local coordinates:
   - `M = inverse(B_ue5) @ B_aurora`
   - `R_aurora_delta = inverse(M) @ R_source_delta @ M`
3. R3.B now uses source clip frame 0 as the retarget reference pose before applying motion deltas.

The third item was the quality unlock. The UE5 idle clip's frame 0 is already an idle pose, not the Manny bind pose. Applying that full frame-0 offset onto PMBAM folded the body. Treating frame 0 as the source retarget pose preserves PMBAM's clean target pose and transfers only the idle motion deltas.

## Probe Results

Two negative probes were useful:

- Basis remapping against UE5 bind pose alone made the pose worse: it conjugated the wrong absolute idle offset.
- A signed-axis permutation sweep did not produce a Tier 3 candidate, confirming the remaining issue was not a simple global axis flip.

The successful probe was:

- Source reference = clip frame 0
- Target reference = PMBAM bind/rest pose
- Motion = frame-local delta from source clip frame 0
- Orientation controllers = target bind rotation multiplied by remapped motion delta

## Phase 2 Captures

- Front, 11 frames: `exports/r3_idle_test_v2/quality_audit/front/`
- Three-quarter, 5 frames: `exports/r3_idle_test_v2/quality_audit/three_quarter/`
- Side-left, 5 frames: `exports/r3_idle_test_v2/quality_audit/side_left/`
- Back, 5 frames: `exports/r3_idle_test_v2/quality_audit/back/`
- Full-motion 64x64 viewport pass, 302 frames: `exports/r3_idle_test_v2/quality_audit/full_motion_64/`
- Bone-position audit JSON: `exports/r3_idle_test_v2/quality_audit/bone_position_audit.json`

Representative v2 frame:

- `exports/r3_idle_test_v2/quality_audit/three_quarter/pmbam__victory__r3b_v2_victory_frame_0150.png`

## Programmatic Gate Results

Viewport validation:

- Front capture: PASS, 11 frames
- Three-quarter capture: PASS, 5 frames
- Side-left capture: PASS, 5 frames
- Back capture: PASS, 5 frames
- Full-motion 64x64 pass: PASS, 302 frames

Viewport-derived bone audit:

- Parent-child length issues at 5% tolerance: 0
- Frame-to-frame motion jumps over 10 mm: 0
- Render/load failures: 0

Note: the optional secondary `AnimationEngine` audit path produced noisy helper-bone false positives and is not used as the canonical Phase 2 gate. The canonical result is the viewport-capture-derived audit in `bone_position_audit.json`.

## Tier Decision

Tier reached: Tier 2+ candidate, pending ground-truth verification.

The v2 output is upright, stable, and smooth across viewport captures, but visual
heuristics are not sufficient for a production-quality animation gate. Phase 3
must verify writer round-trip, synthetic transform preservation, and external
writer parity before the candidate can be promoted.

## R4 Decision

R4 remains blocked pending Phase 3 and the final Tier 3 quality gate:

1. complete Phase 3.A reader/writer round-trip verification,
2. complete Phase 3.B synthetic single-bone transform tests,
3. run KotorBlender cross-validation when available,
4. only update the R4 hand-off package after Tier 3 is reached through verified data.
