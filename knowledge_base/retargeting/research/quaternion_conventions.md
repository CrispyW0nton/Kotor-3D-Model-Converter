# Quaternion Conventions

Date: 2026-05-20

## Current GhostRigger Runtime Convention

Most `ModelNode.rotation`, animation `NodePose.rotation`, and current
retargeting helpers use XYZW ordering:

```text
x, y, z, w
```

The active retargeting code in `src/core/animation_retargeting/retargeter.py`
and `src/unreal/animation_retargeting.py` expects this order and normalizes
inputs defensively.

## KOTOR MDL Caution

KOTOR skin bind tables and qBone/tBone logic have their own binary layout and
import semantics. Do not assume a newly decoded MDL quaternion can be passed
directly into retargeting until it has gone through GhostRigger's model loader
normalization.

## Rule for New Retargeting Work

All public retargeting APIs should state the order in the field name:

- `rotation_xyzw` for GhostRigger runtime objects.
- `rotation_wxyz` only when a raw binary or external source truly uses W-first.

The MCP skeleton info tool exposes `rotation_xyzw` to avoid ambiguity.
