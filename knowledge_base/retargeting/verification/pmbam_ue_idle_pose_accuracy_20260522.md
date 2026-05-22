# PMBAM UE Idle Pose Accuracy Verification - 2026-05-22

## Purpose

This note preserves the useful findings from the local PMBAM idle-retarget experiment so the generated scratch exports do not need to be committed. The working output was produced from `M_Neutral_Stand_Idle_Loop_export.fbx` and installed as a local K1 Override candidate for `pmbam`.

## Final Candidate

- Target model: `pmbam`
- Game: KOTOR 1
- Animation slot used for test: `victory`
- Source FBX: `C:\Users\NewAdmin\Documents\KaiGenInteractive\AnimationLibrary\Exports\M_Neutral_Stand_Idle_Loop_export.fbx`
- Local scratch output: `exports/manual_override_test_20260522_limb_exact_calibrated_basis_v1`
- Installed Override path: `C:\Program Files (x86)\Steam\steamapps\common\swkotor\Override\pmbam.mdl`
- Backup timestamp before install: `20260521_222800`
- MDL SHA-256: `BC5E3EC954349EC15E8774C7899F5E9E71DBA5377AB4E88BE21993DEB3C87545`
- MDX SHA-256: `84DC9B42FAA0B2004C0E10EEF6AB0BC65E02EE7BFFACA027B829574832A58154`

The user confirmed this candidate as the first visually correct PMBAM UE idle retarget after the earlier arm and leg pose mismatches.

## Key Findings

1. Frame-zero source reference keeps the target stable, but it erases the authored UE idle pose. It is useful as a safety baseline, not an accuracy solution.
2. Full source-rest transfer restores the authored limb intent, but it can over-rotate torso and shoulder-helper chains if applied uniformly.
3. PMBAM forearms must target `Lforearm_g` and `Rforearm_g`; mapping UE lower arms to the intermediate bicep links leaves the hands in an A-pose.
4. The observed PMBAM/UE rest-pose conversion for this pipeline is `(-X, -Y, Z)`, with quaternion conversion `(w, -x, -y, z)` from UE-style internal order into Aurora-facing orientation.
5. Direction-only segment matching is not sufficient for a production solver because it leaves twist under-constrained. The successful candidate used calibrated segment frames, then exact segment pose correction for arms, hands, fingers, thighs, shins, feet, and toes.
6. Collar/clavicle helper nodes should be treated carefully. They stabilize the shoulder region, but exact correction on collar helpers can worsen the visible body pose.

## Segment Accuracy Gate

The final local report sampled frames `0, 75, 150, 225, 300` and checked 14 source-to-target limb segments:

- `upperarm_l -> lowerarm_l` mapped to `lbicep_g -> Lforearm_g`
- `lowerarm_l -> hand_l` mapped to `Lforearm_g -> Lhand_g`
- `hand_l -> middle_01_l` mapped to `Lhand_g -> LbFngrB_g`
- `middle_01_l -> middle_03_l` mapped to `LbFngrB_g -> LbFngrT_g`
- `upperarm_r -> lowerarm_r` mapped to `rbicep_g -> Rforearm_g`
- `lowerarm_r -> hand_r` mapped to `Rforearm_g -> Rhand_g`
- `hand_r -> middle_01_r` mapped to `Rhand_g -> RbFngrB_g`
- `middle_01_r -> middle_03_r` mapped to `RbFngrB_g -> RbFngrT_g`
- `thigh_l -> calf_l` mapped to `lthigh_g -> lshin_g`
- `calf_l -> foot_l` mapped to `lshin_g -> lfoot_g`
- `foot_l -> ball_l` mapped to `lfoot_g -> lfootT_g`
- `thigh_r -> calf_r` mapped to `rthigh_g -> rshin_g`
- `calf_r -> foot_r` mapped to `rshin_g -> rfoot_g`
- `foot_r -> ball_r` mapped to `rfoot_g -> rfootT_g`

Maximum measured direction error: `0.0000012074` degrees.

This is the current numeric acceptance gate for "100% pose accuracy" on the PMBAM idle candidate. It measures segment direction, not twist or full surface deformation, so viewport confirmation remains required.

## Scratch Artifact Policy

The generated directories under `exports/manual_override_test_*` are local diagnostics only. Keep their findings here in the knowledge base and regenerate binaries from source code when needed. Do not commit generated MDL/MDX override candidates.

## Next Engineering Step

Promote the exact limb segment correction used for this candidate into the reusable retarget solver path, instead of leaving it as a one-off calibration/export experiment. The core solver already contains the book-backed calibrated frame layer; the remaining polish is to expose the final exact segment pose correction as a repeatable, tested mode for Preview Retarget and verified export.
