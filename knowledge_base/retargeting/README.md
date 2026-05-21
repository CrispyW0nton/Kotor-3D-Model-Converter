# GhostRigger Animation Retargeting

Date: 2026-05-20
Branch: `qt-ghostrigger`

This folder tracks the production retargeting work for bidirectional animation
transfer between KOTOR's Aurora/Odyssey node hierarchy and external skeletons
such as Unreal Engine Quinn/Manny.

## Current Repo Baseline

GhostRigger already has a useful retargeting foundation:

- `src/core/animation_retargeting/retargeter.py`: KotOR-to-KotOR bind-relative
  pose and animation transfer.
- `src/unreal/animation_retargeting.py`: KotOR-to-Unreal target mapping,
  bridge-bone interpolation, twist-bone approximation, and baked animation
  sampling.
- `src/unreal/quinn.py`: bundled `SKM_Quinn_Simple` FBX and bone-map loader.
- `src/gui/windows/qt_retarget_window.py`: detachable retargeting workbench.
- `src/gui/windows/qt_unreal_animator.py`: Quinn/Unreal animator workflow.

The next work should extend this foundation instead of adding a parallel
retargeting stack.

## Dependency Rule

Do not add runtime dependencies for the first retargeting milestones. The plan
examples mentioned `scipy`, `python-Levenshtein`, and `reportlab`; those stay
out of runtime code unless a later dev-only QA package is explicitly accepted.
Existing code already provides quaternion SLERP and deterministic alias matching
without those packages.

## Ground Truth Notes

MCP model inspection on 2026-05-20 confirmed that KOTOR supermodel names do not
match the clean `spine1/l_bicep` planning vocabulary. Real mappings must account
for Odyssey node names such as `torso_g`, `torsoUpr_g`, `neck_g`, `rCollar_g`,
`rbicep_g`, `rbicepl_g`, `lforearm`, `rhand`, `lhand`, `Hturn_g`, and hook
nodes.

## Initial MCP Surface

The first read-only MCP retargeting tools are:

- `ghostrigger_get_retarget_skeleton_info`
- `ghostrigger_build_retarget_map`
- `ghostrigger_list_retarget_animations`

These tools expose skeleton inspection, mapping coverage, and supermodel-chain
animation lists before any destructive bake/export workflow is exposed.

## Next Implementation Phases

1. Lock the skeleton/node summary contracts against real KOTOR and Quinn data.
2. Add MCP animation bake/export only after mapping reports are stable.
3. Add Character Builder integration once the native KOTOR Build Skeleton work
   preserves node names, hooks, and parent chains.
4. Add visual QA only after deterministic retargeted clips can be generated.
