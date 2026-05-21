# Day 4.5 v6 Audit Addendum - Validation Methodology Clarification

Date: 2026-05-21
Status: Approved
Locked Principle: #11 - Ghost Rigger viewport is the canonical visual validator

## Clarification, Not Retraction

The Day 4.5 v6 visual gate using Blender FBX import and SSIM comparison was correct for validating FBX authoring integrity: mesh, skeleton, bone hierarchy, animation frame count, and bind pose preservation inside the intermediate FBX format.

It was insufficient for final MDL visual correctness. Blender renders Blender's interpretation of the FBX. The Ghost Rigger viewport renders the final Aurora/Odyssey MDL path, using Ghost Rigger's KOTOR model loader, hierarchy evaluation, skinning, and viewport renderer.

## What Blender Validation Proved

- FBX file is well formed and importable into DCC tools.
- Bone count matches source: 68/68 roundtrip.
- Vertex count matches source: 1184/1184 roundtrip.
- Animation frames preserved: 45/45 roundtrip.
- Bind pose preserved within tolerance.
- Mesh topology intact.
- SSIM >= 0.95 between Blender renders confirmed authoring consistency.

## What Blender Validation Did Not Prove

- The final MDL renders correctly after Aurora compilation.
- Aurora-specific transform accumulation works on the produced artifact.
- KOTOR's engine will render the model as expected.
- Bone roll and axis conventions translate correctly after reverse-direction injection.
- Animation playback in Aurora's animation system matches the source.

## Three-Layer Validation Model

| Layer | Tool | Validates | Authority |
| --- | --- | --- | --- |
| 1 | Blender | FBX authoring integrity | Authoring gate |
| 2 | Ghost Rigger viewport | Final MDL visual correctness | Canonical |
| 3 | KOTOR in-game | Engine fidelity | Ultimate truth |

Each layer catches different bugs. None substitutes for the next.

## Impact on Day 4.5 v6

- v6 deliverables remain valid for their stated FBX export purpose.
- Future sprints add Ghost Rigger viewport validation as the canonical visual gate.
- No retroactive changes to v6 code are required.
- The Blender SSIM check is reclassified from "visual correctness gate" to "FBX authoring integrity gate."

## Why Blender Was a Reasonable Initial Choice

- Available, scriptable, and well documented.
- Allowed early forward-pipeline validation before viewport CLI support existed.
- Caught real bugs in FBX bind pose, vertex group naming, and hierarchy export.

## Why It Is No Longer Sufficient

- Blender's renderer is not Aurora's renderer.
- A correct FBX can produce an incorrect MDL.
- The reverse pipeline's purpose is to produce KOTOR-ready MDLs, so validation must happen at the MDL layer.

## References

- Locked Principle #11, Sprint 3 R2.75.
- `src/core/validation/viewport_validator.py`
- `scripts/validate_mdl.py`
- Gate 2.75 viewport-to-in-game calibration.
- `knowledge_base/validation/viewport_validator_spec.md`

## Sign-Off

This addendum clarifies methodology without invalidating prior work. The v6 audit remains the source of truth for forward-pipeline FBX completion. This addendum extends the validation framework for Sprint 3 reverse-direction work and all future MDL-output visual gates.
