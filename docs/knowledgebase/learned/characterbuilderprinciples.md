# Character Builder Development Principles

Use this file when changing Character Builder behavior: base selection, custom
mesh import, skeleton fitting, skin binding, weight transfer, deformation
preview, animation proof, and MDL export. Character Builder is a rigging and
deformation tool first, not a generic model converter.

## Source Grounding

- `Inspired 3d advanced rigging and deformations (Clark, Brad)`: production
  rigging discipline, real joint pivots, local axes, bind/rest pose preservation,
  separate model/texture/skin/rig poses, bind skeleton versus rig skeleton,
  skin cluster weighting, deformer ordering, corrective passes, and export pose
  safety.
- `2017-tvc-automatic-skinning-weight-retargeting`: automatic skinning and
  weight retargeting for articulated characters, linear blend skinning limits,
  joint-area refinement, surface smoothing, bi-harmonic/surface-matching
  transfer ideas, and the warning that retargeted or automatic weights still
  need a basically correct skeleton/topology/weight setup before high-bend
  animation will look good.
- `learned/riggingskill.md` and `learned/skinningdeformationskill.md` remain
  the operational checklists. This file defines the product-level development
  principles that should guide new Character Builder features.

## Product North Star

- Treat every import as an animation candidate. A mesh is not successfully
  loaded until its scale, axes, UV identity, bind pose, skeleton authority, and
  deformation proof can be explained.
- Preserve the final game export pose. The native KOTOR bind/export skeleton
  must remain recoverable even when the viewport offers rigging conveniences,
  manual fit overrides, or temporary imported armatures.
- Separate source, bind, rig, and export states. Store evidence for each state
  instead of assuming the visible pose is the pose animations were authored
  against.
- Make the selected KOTOR base skeleton authoritative for game export. Imported
  OBJ/FBX/glTF geometry is payload; donor or imported skeletons are guides unless
  a workflow explicitly promotes them with proof.
- Prefer reusable rigging workflows over one-off fixes. Skeleton fitting,
  weight remap, ROM preview, and export validation belong in Workflow/Core
  layers; the Qt panel should orchestrate and display evidence.

## Import And Fit Rules

- Identify the intended character mode before fitting. Humanoid landmark logic
  must not drive creature, winged, tail, beast, or already-KOTOR-space
  replacements.
- Record source axis, target axis, scale basis, translation basis, reference
  bounds, and confidence for every auto-fit. The Inspector should show why the
  tool moved the mesh.
- Use the selected base model as the reference whenever available. Generic
  humanoid height is a fallback, not a launch-quality creature or replacement
  fitting method.
- Preserve authored UV convention for external DCC meshes. Do not repair KOTOR
  seams, flip UVs, or collapse per-corner UV identity unless the import path
  records why that transformation is safe.
- Keep manual fit overrides as explicit deltas. They should be reportable,
  repeatable, and reversible before binding or export.

## Skeleton And Bind Rules

- Validate pivots and local rotation axes before diagnosing animation or
  skinning. Bad axes can look harmless in rest pose and fail during playback.
- Bind pose is production-critical state. Store enough bind evidence to restore
  or compare it after controls, guide bones, imported armatures, or native
  template swaps are introduced.
- Keep bind skeleton and rig/guide skeleton roles separate. Temporary imported
  armatures may guide fit or weight transfer, but the native KOTOR DAG owns the
  MDL unless the workflow says otherwise.
- Check hierarchy inheritance deliberately. Root, pelvis, wings, tail, jaw,
  hand/weapon hooks, and helper nodes must not accidentally double-transform.
- Naming and side conventions are validation rules. Weight mirroring,
  retargeting, and donor transfer should stop or warn when side aliases or
  symmetry assumptions are uncertain.

## Skinning And Weight Rules

- Weight transfer starts with a proven fit. Surface matching or nearest-donor
  selection is unsafe when scale, orientation, side landmarks, or topology
  assumptions are weak.
- Automatic weights are a baseline, not proof. Joint areas, high twists,
  overlap zones, and creature appendages need range-of-motion checks.
- Normalize, cap, and audit influences after every remap or smoothing pass.
  KOTOR export should not silently accept missing, NaN, negative, or over-limit
  influence data.
- Smooth weights only after ownership is correct. Smoothing can hide a wrong
  anatomical assignment until animation bends the joint.
- Preserve vertex and UV identity through cleanup. Reordered vertices,
  triangulation changes, UV seam collapse, or changed face order can invalidate
  stored weights even when the mesh looks similar.

## Deformation Proof

- A successful build needs ROM evidence, not just a rest-pose screenshot.
  Preview neutral, root motion, twist-heavy bends, mirrored sides, and
  creature-specific chains such as wings, tail, jaw, claws, or tentacles.
- Prefer base weight repair before corrective deformation. Correctives should
  document their driver pose and failure mode.
- Validate exported behavior after reload. Compare native hierarchy, hook nodes,
  mesh/skin counts, bone maps, texture names, animations/supermodel, and at
  least one visible animated playback path.
- When the result is intended for the game, finish with in-game proof. The
  viewport proves setup; KOTOR runtime proves the final asset contract.
