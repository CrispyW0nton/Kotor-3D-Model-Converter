# Sprint 3 Reverse Direction Audit

## Scope

Sprint 3 starts the UE5 Manny/Quinn -> Aurora direction. The first committed
slice is intentionally conservative:

- derive `ue5_to_aurora_rename_map.json` from the Day 4.5 v6 forward map;
- validate that every source animation channel is either mapped or explicitly
  dropped;
- preserve Aurora target helpers instead of importing UE5 IK/twist/helper bones;
- add a pure data-level A-pose compatibility report for rest-pose rotations.

## Source Basis

Epic's Game Animation Sample remains the preferred source corpus. Epic describes
it as a free sample project with over 500 AAA-quality animations, compatible with
UE Mannequins and usable with or without its animation Blueprints. The official
documentation also states that Animation Sequence assets live under
`Content/Characters/UEFN_Mannequin/Animations` and can be exported from Unreal.

References:

- https://www.unrealengine.com/blog/game-animation-sample?lang=en-US
- https://dev.epicgames.com/documentation/en-us/unreal-engine/game-animation-sample-project-in-unreal-engine

## Important Correction From The Planning Draft

The actual Day 4.5 v6 forward map is narrower than the illustrative reverse map.
It maps PMBAM body bones to UE5-compatible names, but `neck_01` and `head` were
synthetic helper leaves added for UE/Unity humanoid checks. They are not native
PMBAM deform bones. The generated reverse map therefore drops those synthetic
helper channels unless a later target-specific map opts into a full-head target.

## Deliverables Added

- `knowledge_base/retargeting/ue5_to_aurora_rename_map.json`
- `src/core/retargeting/reverse_renamer.py`
- `src/core/retargeting/apose_compatibility.py`
- `tests/test_reverse_renamer.py`
- `tests/test_apose_compatibility.py`

## Verification

Command:

```powershell
python -m pytest tests/test_reverse_renamer.py tests/test_apose_compatibility.py tests/test_skeleton_renamer.py -q
```

Result:

```text
19 passed
```

## Next Gate

Before animation injection, obtain/export one Game Animation Sample FBX and
capture its rest pose. The A-pose validator should then compare that source
capture against the target Aurora model through the reverse rename map. If any
mapped deform bone exceeds the tolerance, halt and document the pose delta
instead of baking curves into an Aurora animation block.
