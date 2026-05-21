# Bone Mapping Rules

Date: 2026-05-20

## Rule 1: Real KOTOR Names Win

KOTOR animation binding is name-based. Retargeting logic must map from actual
Odyssey node names, not simplified planning names.

Representative KOTOR names:

- `rootdummy`
- `pelvis_g`
- `spine_g`
- `torso_g`
- `torsoUpr_g`
- `neck_g`
- `head_g`
- `rCollar_g`
- `rbicep_g`
- `rbicepl_g`
- `rforearm_g`
- `rhand`
- `lCollar_g`
- `lbicep_g`
- `lbicepl_g`
- `lforearm`
- `lhand`
- `rthigh_g`
- `rshin_g`
- `rfoot_g`
- `rfootT_g`

## Rule 2: Hooks Are Not Deform Bones

Attachment hooks should be visible and validated, but they should not become
normal retarget mapping targets unless a workflow explicitly requests socket
preview.

Common hook/helper names:

- `headhook`
- `rhand`
- `lhand`
- `impact`
- `impact_bolt`
- `DeflectHook`
- `LightsaberHook`
- `handconjure`
- `headconjure`
- `talkdummy`
- `cutscenedummy`

Note: `rhand` and `lhand` are both sockets and meaningful hand transform nodes.
The retargeting code should keep treating them as hand endpoints when mapping
humanoid animation, while validation/export should treat them as equipment
sockets.

## Rule 3: Unreal Bridge Bones Are Derived

Unreal/Quinn has denser chains and helper/twist nodes. These are not one-to-one
KOTOR failures. Missing target nodes may be expected if they can be derived by
interpolation.

Examples:

- KOTOR `torso_g`/`torsoUpr_g` can drive multiple Unreal spine nodes.
- Unreal twist bones should inherit a controlled fraction of parent rotation.
- Unreal IK/control bones are ignored for deformation retargeting.

## Rule 4: Mapping Reports Gate Automation

An MCP export/bake tool should not write files until the mapping report includes:

- source and target skeleton types,
- direct mapped count,
- derived target count,
- unmapped source nodes,
- unmapped target nodes,
- explicit manual override list when used.
