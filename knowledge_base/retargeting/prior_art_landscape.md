# Prior Art Landscape: KOTOR/Aurora to Game Engine Conversion

## Purpose

This note records the external tools and community workflows that informed the
Day 4.5 v6 export design. GhostRigger does not vendor GPL code from these
projects; they are treated as clean-room specification references and prior-art
validation.

## Tier 1: Reference Implementations

| Project | License | Relevance |
| --- | --- | --- |
| [KotorBlender](https://github.com/seedhartha/kotorblender) | GPL-3.0 | Blender addon for binary MDL import/export. Validates the `bone.matrix = world_matrix` armature construction pattern, name-keyed vertex groups, and delta-from-rest animation baking. |
| [KotOR-Unity](https://github.com/rwc4301/KotOR-Unity) | GPL-3.0 | Unity reimplementation with Aurora-to-Unity model, skin, animation, and axis conversion behavior. |
| [reone](https://github.com/seedhartha/reone) | GPL-3.0 | C++ engine/toolkit reference for Odyssey resource extraction and model parsing behavior. |
| [xoreos](https://github.com/xoreos/xoreos) | GPL-3.0 | Aurora-family engine reimplementation; confirms KOTOR’s weighted skeletal animation category and supermodel inheritance behavior. |
| [KotOR.js](https://github.com/KobaltBlu/KotOR.js) | GPL-3.0 | TypeScript/Three.js KOTOR runtime reference for skeletal evaluation behavior. |

## Community Tools

MDLEdit, MDLOps, KOTORMax, reone toolkit, and Kotor Tool remain the practical
modding ecosystem around MDL/MDX extraction, ASCII conversion, and DCC import.
The dominant manual FBX workflow has historically used 3ds Max/KOTORMax, while
KotorBlender provides the closest Blender-native reference workflow.

## Critical Technical Facts

1. KOTOR character "bones" are Aurora nodes, often trimeshes acting as bones and shadowcasters.
2. Character mesh weights bind by bone name once represented in Blender vertex groups.
3. The fidelity-preserving Blender armature primitive is assigning the edit bone matrix from the node world bind matrix.
4. KOTOR animation controllers are absolute local object transforms; Blender pose curves need deltas from rest.
5. The delta rotation relationship is `rest_rotation.inverted() @ animated_rotation`.
6. KOTOR quaternions may be stored compressed in binary MDL; GhostRigger consumes decompressed WXYZ values at the retargeting boundary.
7. Bind world matrices come from parent-chain accumulation of local TRS.
8. Runtime animations may resolve through the supermodel chain.
9. Export-time pose forcing is not required for Unity Mecanim or UE5 IK Retargeter workflows.
10. Sprint 1 keeps a single clean clip; supermodel library batching is Sprint 2 scope.

## GhostRigger Differentiation

GhostRigger’s value is not inventing KOTOR-to-FBX from scratch. It packages the
known-good ingredients into an automated, free, batchable, UE5/Unity-targeted
pipeline with ground-truth capture, validation gates, and future supermodel-aware
animation bundling.

## Reverse Retargeting Landscape

Sprint 3.5 research did not identify a documented prior UE5/Manny or Mixamo-style
animation to KOTOR Aurora character retargeting pipeline. Known community work
covers KOTOR animation authoring in DCC tools, KOTOR MDL import/export, and
KOTOR-to-modern-engine asset conversion. The reverse direction introduces new
failure modes: KOTOR's objects-as-bones hierarchy, absolute parent-relative
animation controllers, per-node transform conventions, and source twist-bone
data that does not have a direct PMBAM equivalent.

This makes ground-truth verification mandatory. GhostRigger now treats stock
MDL round-trip, synthetic transform preservation, KotorBlender cross-validation,
and viewport playback as separate correctness oracles rather than relying on a
single visual inspection loop.

## License Posture

The referenced implementations are GPL-family projects. GhostRigger may cite
their public behavior and re-implement algorithms independently, but it must not
copy source text or vendor their modules into this repository unless the whole
distribution license is intentionally changed.
