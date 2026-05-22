# Computer Graphics Math for Aurora Retargeting

Date: 2026-05-21  
Reference: John Vince, *Mathematics for Computer Graphics*, 7th ed.  
Scope: UE/FBX source animation -> KOTOR Aurora/Odyssey object-node hierarchy.

## Why This Exists

The PMBAM retarget tests proved that GhostRigger's writer and deformation safety
gates are working: the exported mesh does not explode, and MDL readback passes.
The visible failure is pose fidelity.  Arms and hands remain in the wrong place
because the solver is still treating parts of a KOTOR Aurora node hierarchy like
a simple game-engine skeleton.

This note is the living math reference for the retargeting work.  Update it
whenever a new solver, audit, or viewport result teaches us something durable.

## Book Map For This Problem

The useful sections are not isolated formulas; they form the required retarget
contract:

- Coordinate systems and basis vectors: PDF pages 93, 124-127.  A vector only
  has meaning relative to its basis.  Retargeting must therefore transfer motion
  between explicit source and target frames, not raw component triples.
- Inverse and orthogonal matrices: PDF pages 162-170.  Parent-local conversion,
  change of basis, and rigid transforms depend on inverse/order correctness.
  Rotation bases should be orthonormal and right-handed.
- Geometric transforms and homogeneous coordinates: PDF pages 212-260.  Source
  and target poses should be treated as full transforms, while translation
  transfer must remain policy-driven to protect KOTOR skin deformation.
- Unit, normalised, and inverse quaternions: PDF pages 273-280.  Every generated
  orientation key must be normalized, finite, and safely invertible.
- Multiple quaternion rotations: PDF page 304.  Rotation order is part of the
  meaning; parent/world/local composition cannot be swapped casually.
- Rotation matrix to quaternion and quaternion vector rotation: PDF pages
  307-309.  Matrix-based basis conversion should be converted back to the
  internal XYZW quaternion convention only at controlled boundaries.
- Quaternion interpolation: PDF page 324.  Adjacent keys must be hemisphere-fixed
  and evaluated by shortest-path interpolation to avoid animation flips.

## Aurora/Odyssey Constraint

KOTOR character animation is an object-node controller hierarchy:

- dummy/trimesh/skin/helper nodes form the hierarchy;
- skin meshes bind to named nodes;
- animation controllers store absolute parent-relative local transforms;
- supermodels supply inherited animation slots;
- a local animation block with the same slot name overrides an inherited slot.

This means the solver must output controllers on existing Aurora nodes.  It must
not import the UE skeleton as the target hierarchy, create new KOTOR nodes during
retargeting, or write UE helper/twist/IK names as KOTOR controller targets.

## PMBAM Ground Truth

PMBAM is a good failure case because its arms are not simple UE chains.

Left arm reference chain:

```text
lcollar_dum
  lcollar_g
    lbicep_g
      LbicepL_g
        Lforearm_g
          Lhand_g
            lhand/fingers
```

Right arm reference chain:

```text
rcollar_dum
  rcollar_g
    rbicep_g
      RbicepL_g
        Rforearm_g
          Rhand_g
            rhand/fingers
```

The visual regression after `segment_direction` happened because one direction
vector is under-constrained.  It can align an endpoint while losing the
anatomical plane or twist, and it ignores intermediate Aurora nodes such as
`LbicepL_g` / `Rforearm_g`.

## Current Solver Principle

The safe baseline is still `reference_frame_delta`:

```text
source sampled global motion
-> source reference-relative rotation delta
-> target reference frame
-> absolute parent-local Aurora orientation key
```

The next experimental path is `calibrated_frame_delta`:

```text
source parent/child reference segment
-> full orthonormal source frame
target parent/child reference segment
-> full orthonormal target frame
source current segment frame
-> calibrated semantic delta
-> target world rotation
-> absolute parent-local Aurora key
```

This comes directly from the basis/inverse/quaternion composition material in
the book: a pose transfer is a change-of-basis problem, not a component-copy
problem.

## Implementation Rules

1. Build a full frame for every mapped anatomical segment:
   primary axis = parent-to-child direction;
   secondary axis = projected plane/twist hint;
   tertiary axis = cross product;
   then re-orthonormalize.
2. Measure both endpoint direction and plane/twist quality.  A single segment
   direction error of zero is not a sufficient pass.
3. Treat PMBAM-style intermediate nodes as real transform stages.  Profiles must
   be able to map UE `upperarm/lowerarm/hand` roles onto composite Aurora chains.
4. Keep non-root translations fixed unless explicitly allowlisted.
5. Keep `calibrated_frame_delta` opt-in until viewport captures prove it beats
   the safer default across arms, legs, and torso.
6. Do not export a new candidate just because tests pass.  Use tests to prove
   math gates, then use GhostRigger viewport captures for visual approval.

## Next Knowledgebase Tasks

- Add a PMBAM chain profile document with left/right arm, leg, foot, hand, and
  finger controller candidates.
- Add a frame-quality report that records primary-axis, secondary-axis, twist,
  wrist/ankle endpoint, and elbow/knee pole errors per frame.
- Add before/after viewport captures for each solver mode so visual regressions
  are traceable to the exact math path.
- When twist redistribution starts, add a separate note for swing/twist
  decomposition and UE twist-helper policy.
