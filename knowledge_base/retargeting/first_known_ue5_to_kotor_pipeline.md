# First Known UE5-to-KOTOR Retargeting Pipeline Claim

Date: 2026-05-21

Status: Working claim, pending community review

## Claim

Based on the Sprint 3.5 research snapshot, GhostRigger appears to be building
the first documented UE5/Manny-style animation to KOTOR Aurora character MDL
retargeting pipeline.

This is not a priority claim for marketing. It is an engineering note explaining
why the project must rely on ground-truth verification rather than assuming
there is a known community recipe to follow.

## Known Prior Art

| Work | Direction | Notes |
| --- | --- | --- |
| KotorBlender | KOTOR MDL <-> Blender | Authoritative DCC bridge and writer reference, not a documented UE5-to-KOTOR retargeting pipeline. |
| KOTORMax / 3ds Max workflows | KOTOR MDL <-> 3ds Max | Supports custom animation authoring in DCC, not an automated UE5 source retarget. |
| KotOR-Unity / Apeiron-style work | KOTOR -> Unity/UE-style runtime | Primarily asset/runtime conversion in the opposite direction. |
| Community custom animations | DCC-authored KOTOR animation | Existing examples are hand-authored or facial/dummy workflows, not external UE5 skeletal retargeting. |

## Engineering Consequence

The pipeline must create its own oracles:

- Stock MDL reader/writer round-trip verification
- Synthetic single-bone transform tests
- KotorBlender cross-validation
- Manual or industry-tool retarget comparisons when available

This is now locked as Principle #13: production-quality animation output
requires ground-truth verification, not visual heuristics.
