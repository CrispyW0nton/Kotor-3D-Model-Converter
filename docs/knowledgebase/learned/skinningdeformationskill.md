# Skinning And Deformation Skill

Use this skill for Character Builder bugs where a skeleton builds successfully
but deformation is wrong: bad Bendak-style FBX skin remap, donor weight transfer
artifacts, nearest-surface weight mistakes, joint collapse, twist artifacts,
mirrored-side drift, or animation ROM failures after export.

## Book Grounding

- `Inspired 3D Advanced Rigging and Deformations`: smooth binding, skin
  cluster influence behavior, clean-slate weighting, reverse/paint weighting,
  mirroring weights, weight storage, bind pose nodes, deformer ordering,
  blend-shape/corrective deformation, cluster-relative behavior, and iterative
  deformation testing.
- `Rig it Right`: local rotation axes, zeroed controls, joint orientation,
  controller hierarchy, naming, and skinning workflow discipline.
- `Digital Creature Rigging`: layered creature rigs, source geometry cleanup,
  deformation rig pass, and final cleanup.
- `Automatic skinning and weight retargeting`: LBS artifacts, weight transfer,
  joint-area refinement, distance fields, smoothing, and retarget assumptions.

## GhostRigger Workflow

0. For Character Builder design or workflow changes, load
   `learned/characterbuilderprinciples.md` first so the implementation preserves
   bind/export pose authority, fit evidence, ROM proof, and in-game validation.
1. Name the spaces before debugging: source object, imported FBX armature,
   bind, native KOTOR skeleton, pose, scene/world, and renderer palette space.
2. Freeze the asset contract before weighting. Record vertex count, face order,
   UV identity, mesh bounds, bone names, bone order, bind pose matrices, and
   source-to-native bone map before any transfer.
3. Prefer imported source skin weights when the FBX has a coherent armature and
   bone names can be remapped to the selected KOTOR base. Treat donor transfer
   as second-best evidence and nearest-bone fallback as exportable but not
   launch-quality.
4. If transfer is required, prove the fit first. The source and target need
   explicit scale/orientation evidence, matched side/center landmarks, and a
   non-reflected transform before weights can be trusted.
5. Normalize and cap influences after every remap, interpolation, mirror, or
   topology operation. KOTOR export should reject negative, missing, NaN, or
   over-limit weights rather than silently fixing them late.
6. Test deformation with ROM poses before export: neutral, root motion, spine
   bend, shoulder/hip bends, wrist/ankle bends, mirrored limbs, twist-heavy
   joints, and any creature-specific tail/wing/jaw/appendage chains.
7. Only add corrective shapes, helper clusters, or scripted deformation fixes
   after the base skeleton, bind pose, bone palette, and primary weights pass
   ROM checks.

## Bendak-Style Debug Checklist

- Confirm the FBX importer preserves the source armature guides and skin rows:
  vertex count equals skin row count, each row has at least one influence, and
  each row sums to 1 within tolerance.
- Compare source bone names to the native KOTOR bone palette. Every remapped
  influence must point to the intended native bone index after aliasing.
- Verify bind-pose equivalence. A visually correct skeleton in rest pose can
  still deform badly if the inverse bind matrices or local axes were taken from
  the wrong space.
- Check whether the mesh was already in KOTOR space. Do not run a humanoid
  height/axis fallback on a creature or replacement mesh that already matches
  native bounds.
- For donor weight transfer, inspect nearest-donor selection at seams, hands,
  shoulders, hips, and mirrored sides. A close vertex in object space may still
  belong to the wrong anatomical region if surfaces overlap.
- If deformation explodes only during animation, compare pose matrix order:
  parent-to-child composition, bind inverse multiplication, coordinate
  handedness, and whether renderer/object transforms are applied twice.

## Weighting Rules

- Weight totals are conservation rules. Editing one influence must redistribute
  the remainder deliberately; hidden or distant influences can steal weight if
  they remain eligible.
- Start from a known baseline when repairing a broken bind. A clean all-root or
  all-main influence pass is often easier to audit than partially inherited
  weights with unknown leftovers.
- Mirror only after naming, axes, and topology symmetry are proven. After
  mirroring, run animation tests on both sides because center bones and missing
  mirror partners need manual review.
- Preserve point identity when saving, restoring, or transferring weight maps.
  Vertex deletion, added spans, triangulation changes, or reordered geometry
  can invalidate stored weights even when the model looks visually similar.
- Smooth weights as a polish pass, not as a substitute for correct bone
  ownership. Smoothing can hide a bad assignment until high-bend animation.

## Corrective Deformation Rules

- Deformation order matters. Skinning, blend shapes, clusters, and helper
  deformers must have a documented evaluation order so fixes do not fight each
  other.
- Corrective shapes should name their driver pose and the failure they solve,
  such as shoulder raise collapse or elbow twist volume loss.
- Cluster/helper systems should avoid double transforms. If a helper follows a
  joint, document whether it is relative, world-space, parented, constrained, or
  evaluated outside the export skeleton.
- Correctives are review evidence, not export authority. The native KOTOR DAG,
  skin payload, and animation compatibility still own the final MDL behavior.

## Verification Gates

- Backend: MCP or direct loader proof for original native MDL node count,
  skeleton hierarchy, animations, skin nodes, bone maps, and texture references.
- Binding: targeted test proving imported source skin remap or donor transfer
  records weighting method, weighted vertex count, normalized influence totals,
  and native bone-map targets.
- Deformation: ROM preview in the Debug app, with at least one inherited walk
  or named animation looped on the generated model.
- Export: reload the produced MDL/MDX and compare hooks, mesh count, skin node
  count, supermodel/motion source, animation availability, and texture names.

## Failure Patterns

- Mesh follows the wrong limb: bone index remap or donor nearest-surface choice
  is wrong.
- Mesh collapses at a joint: missing bind-pose inverse, unnormalized weights,
  too few influences, or source weights assigned to a parent instead of the
  bend joint.
- One side behaves differently after mirror: side aliases, local axes, or
  topology symmetry assumptions are false.
- Mesh looks correct in rest pose but breaks during playback: pose-space matrix
  composition or renderer palette order is wrong.
- Creature replacement scales or rotates unexpectedly: humanoid auto-fit logic
  was applied to a non-humanoid or already-KOTOR-space mesh.
