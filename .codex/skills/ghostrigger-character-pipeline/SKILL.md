---
name: ghostrigger-character-pipeline
description: >
  Work on GhostRigger's Character Studio pipeline: importing custom FBX/OBJ/glTF
  meshes, fitting them to native KOTOR Odyssey node hierarchies, binding/skinning,
  previewing inherited animations, and exporting reloadable MDL/MDX. Use for the
  native DAG lock (T2501-T2505), skin weight transfer, hook validation
  (head_g/Lhand_g/Rhand_g/camerahook), supermodel semantics, qbone/tbone data,
  and animation export. Covers joint orientation, bind pose, FK/IK switching,
  retargeting architecture, and the N_DarthMalak walk-cycle fixture.
---

# GhostRigger Character Pipeline

Character Studio's critical-path blocker is the native Odyssey DAG lock:
imported meshes must be bound to an exact clone of the KOTOR node hierarchy
preserving node names, parent chains, flags, hooks, and bind data.

## When to Use

- Character Studio import/fit/bind/skin/export workflow (T2501-T2705)
- Retarget Studio animation transfer (T2401-T2406)
- MDL/MDX export validation and reload testing
- Skin weight quality, bone palette, qbone/tbone data
- Hook validation for body/head/creature models
- Animation inheritance via supermodel chains
- Blender FBX axis conversion (world → KOTOR object space)

## The Native Odyssey DAG Lock (T2501-T2505)

KOTOR animation binding depends on **exact node names, parent chains, flags,
hooks, bind data, and supermodel semantics**. The workflow:

1. **Snapshot** (T2501): capture exact node names, parents, flags, transforms,
   hooks, mesh/skin metadata, and supermodel string from the selected base model.
2. **Separate hiding from export** (T2502): UI may hide helper/reference
   geometry, but export state must preserve exact base nodes unless a
   structural diff records the change.
3. **Clone DAG, then bind** (T2503): imported mesh attaches to the cloned
   hierarchy; external armature artifacts are removed from export output.
4. **Structural diff** (T2504): inspector lists preserved nodes, added meshes,
   changed transforms, missing hooks, and skin row counts.
5. **Golden tests** (T2505): K1/K2 body, head, full-body/disguise, and creature
   references pass snapshot/build-diff gates with MCP-backed ground truth.

## Joint Orientation Discipline

- A joint is a position + orientation; a bone adds length
- `Joint Orient` is a second rotation layer stacked on `Rotate XYZ`
- Pick **one store** — either `Rotate XYZ` **or** `Joint Orient XYZ`, never both
- Freeze transforms to move values into joint orient
- Re-parenting silently writes into `Joint Orient` — treat reparented nodes as
  suspect and re-zero
- A hinge mis-oriented across three axes serializes three rotation curves
  instead of one — bloats the file and invites gimbal singularities

## Hook Validation

KOTOR models must have named hooks for attachment points:

| Hook | Purpose | Models |
|------|---------|--------|
| `head_g` | Head attachment | Humanoid body |
| `Lhand_g` / `Rhand_g` | Weapon/hand attachment | Humanoid, creature |
| `camerahook` | Camera anchor | All player/creature |
| `foot_l` / `foot_r` | Footstep alignment | Bipedal |

Validate that the exported rig honors the donor snapshot's real hook names.
Creature hooks (e.g., Drexl's `Lhand_g`, `Rhand_g`, `camerahook`) must not be
blocked by humanoid-only hook expectations.

## Supermodel Semantics

A supermodel is KOTOR's equivalent of Unreal's Skeleton asset: it holds the
hierarchy structure and how animation data applies to it. Two skeletal meshes
share animation **only if the hierarchy matches** — joints may be absent on one
mesh, but the **order of the hierarchy cannot change** (if B is a child of A in
one model, A cannot become a child of C in another).

When exporting, set the supermodel reference correctly:
- Humanoid bodies: `NULL` or a body supermodel (e.g., `pmhb`)
- Creatures: typically `NULL` (self-contained rig)
- Heads: inherit from the body supermodel

## Validation Workflow

1. Run `compare_model_pipelines(game, resref)` to confirm baseline parity
2. Run `inspect_mdl(game, resref)` for PyKotor ground truth
3. Run `inspect_mdl_ghostrigger(game, resref)` for GhostRigger output
4. Identify divergence
5. Fix the owning code
6. Re-run `compare_model_pipelines` to confirm the fix
7. Run targeted regressions only

## Default Fixtures

- Animation: `N_DarthMalak` with `walk` animation looped
- Head/body: Carth body with Carth head attached
- Cloth/body: Bastila body and head
- Creature: `c_drexlf` (native-template replacement example)

## Deep Reference

- `docs/knowledgebase/learned/technicalanimationskill.md` — full pipeline,
  state machines, LOD, profiling, quaternion SLERP, vertex blending, CCD/FABRIK
- `docs/knowledgebase/learned/characterbuilderprinciples.md` — product-level
  rigging/deformation contract
- `docs/knowledgebase/learned/riggingskill.md` — joints, skeleton hierarchy,
  weight transfer
- `docs/knowledgebase/learned/skinningdeformationskill.md` — skinning failure
  troubleshooting, donor transfer, bind pose, bone palette
- `docs/knowledgebase/learned/unrealcharacterpipelineskill.md` — UE5 retarget
  lane details
