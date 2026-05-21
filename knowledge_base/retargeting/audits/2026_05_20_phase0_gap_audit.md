# Phase 0 Retargeting Gap Audit

Date: 2026-05-20

## Summary

The submitted retargeting plan is directionally right, but the codebase is not
starting from zero. LordVader's recent work already added a meaningful
retargeting spine: Quinn skeleton loading, Unreal workbench UI, bind-relative
pose transfer, bridge-bone interpolation, twist-bone approximation, and tests.

The safest path is to formalize and expose that existing work through MCP and
then evolve it toward bidirectional animation baking.

## MCP Ground Truth Checked

Models queried:

- `k1:s_male01`
- `k1:s_male02`
- `k1:s_female02`
- `k1:pmbam`

Important observations:

- `s_male02` has `S_Male01` as its supermodel and a large inherited animation
  library including locomotion, dialogue, combat, Force, and weapon clips.
- `s_female02` has `S_Female01` as its supermodel and contains combat/weapon
  clips with real Odyssey naming.
- `pmbam` contains no local animations and points to `S_Female02`.
- The planning sketch's `spine1`, `l_bicep`, and `l_shoulder` names are not
  the canonical KOTOR names in the loaded assets. Mapping logic must remain
  alias-driven.

## Existing Code to Keep

- `src/core/animation_retargeting/retargeter.py`
- `src/unreal/animation_retargeting.py`
- `src/unreal/quinn.py`
- `src/gui/windows/qt_retarget_window.py`
- `src/gui/windows/qt_unreal_animator.py`
- Quinn tests in `tests/test_core_contracts.py`

## Risks in the Original Plan

- Adding `scipy`, `python-Levenshtein`, or `reportlab` as runtime dependencies
  conflicts with the current low-dependency posture.
- Creating `src/core/retargeting/` alongside existing
  `src/core/animation_retargeting/` would split the implementation.
- Assuming clean modern bone names would break KOTOR's exact node-name binding.
- Exposing an MCP "retarget_animation" write/export tool too early would make
  bad mappings easy to automate.

## Phase 0 Change Made

Added read-only MCP retargeting tools:

- `ghostrigger_get_retarget_skeleton_info`
- `ghostrigger_build_retarget_map`
- `ghostrigger_list_retarget_animations`

These expose deterministic facts and mapping reports without changing model
files or exporting clips.

## Follow-up Fix: KOTOR Mesh-Bones in Mapping

The first real `k1:s_male02 -> SKM_Quinn_Simple` MCP mapping report exposed an
important bug in the existing Unreal mapper: it excluded all `is_mesh` nodes,
which is correct for modern render meshes but wrong for KOTOR source skeletons.
Odyssey uses mesh-objects-as-bones, so nodes such as `pelvis_g`, `torso_g`,
`torsoUpr_g`, `neck_g`, `rhand_g`, and `lhand_g` must be valid source bones.

The mapper now includes KOTOR mesh-bone names when they match the existing alias
vocabulary, while still excluding skin meshes and unrelated render meshes.

Smoke result after the fix:

- Source: `k1:s_male02`
- Target: bundled `SKM_Quinn_Simple`
- Direct matches: 27
- Derived target bones: 20
- Verified mappings:
  - `pelvis_g -> pelvis`
  - `torso_g -> spine_02`
  - `torsoUpr_g -> spine_03`
  - `neck_g -> neck_01`
  - `rhand_g -> hand_r`
  - `lhand_g -> hand_l`
  - `rthigh_g -> thigh_r`
  - `lfoot_g -> foot_l`

## Next Gate

Before enabling animation export through MCP:

1. Run mapping reports for KOTOR supermodels to Quinn.
2. Save representative reports under `knowledge_base/retargeting/audits/`.
3. Confirm bridge and twist bones are derived, not treated as missing failures.
4. Confirm local and inherited KOTOR animation names match the supermodel chain.
