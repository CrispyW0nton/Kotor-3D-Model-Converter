# 3D Math Primer Lessons for Aurora Retargeting

Date: 2026-05-22  
Reference: Dunn and Parberry, *3D Math Primer for Graphics and Game
Development*, 2nd ed., local PDF.  
Scope: math and graphics concepts that directly close gaps in GhostRigger's
UE/FBX -> KOTOR Aurora/Odyssey animation retargeter.

## Why This Book Matters

This book is the most directly useful of the three references for the current
pose-quality problem.  It explains the exact failure mode we saw in PMBAM:
orientation is not the same as direction.  A vector has direction but no twist,
so a solver that only aligns a parent-to-child segment can still leave the
elbow/hand plane or wrist orientation wrong.  KOTOR's object-node chains make
that problem sharper because a single UE limb role may correspond to several
Aurora nodes.

## High-Value Chapter Map

- Coordinate handedness: PDF pages 37-40.  Axis swaps and handedness changes
  affect rotation signs.  UE/KOTOR conversion must happen through matrices or
  named basis conversions, not component shuffles.
- Vectors, dot product, cross product: PDF pages 53-93.  Dot products measure
  projection/angle; cross products construct perpendicular axes and plane
  normals.  These are the tools for endpoint, pole-plane, and twist diagnostics.
- Multiple coordinate spaces: PDF pages 101-131.  Nested spaces are the correct
  mental model for source skeletons, Aurora object nodes, parent-local
  controllers, and viewport FK.
- Row/column vector conventions: PDF pages 145-146.  Matrix formulas from books,
  APIs, FBX, Blender, and GhostRigger may be transposed relative to each other.
  The code must use named transforms instead of visually copying equations.
- Combining transformations: PDF page 175.  Transform order is part of the
  meaning.  Parent/world/local order errors create believable-but-wrong poses.
- Orthogonal/rigid transforms and orthogonalization: PDF pages 180, 193-197.
  Rotation frames should preserve length and angles; imported or reconstructed
  frames must be re-orthonormalized.
- Rotation in 3D: PDF pages 239-313.  This chapter covers matrix, Euler,
  axis-angle, quaternion, conversion, and representation-choice pitfalls.
- Quaternion negation, inverse, multiplication, difference, and interpolation:
  PDF pages 271-285.  `q` and `-q` are equivalent, orientation keys must be
  hemisphere-continuous, and quaternion difference is the natural way to express
  angular displacement between poses.
- Planes and point-to-plane distance: PDF pages 335-338.  Elbow/knee pole
  validation should use plane normals and signed distances, not only segment
  angles.
- Skeletal animation and binding pose: PDF pages 446-451, 494-495.  Runtime
  skinning consumes matrices derived from pose and bind state.  For KOTOR, our
  equivalent is evaluating Aurora controller poses against the original node
  hierarchy and skin binding without moving rest translations.

## Gap Closed: Direction Is Not Orientation

The previous `segment_direction` experiment aligned a direction vector.  That
was under-constrained.  A limb pose needs a full frame:

```text
primary axis   = parent -> child segment direction
secondary axis = anatomical plane / pole / up hint
tertiary axis  = cross(primary, secondary)
```

The frame must be orthonormal, right/left-handed as intended, and stable under
small motion.  This is why the new `calibrated_frame_delta` path is a better
experimental direction than raw segment matching.

## Required Audits From This Book

### 1. Segment Direction Error

Use normalized dot product:

```text
angle = acos(clamp(dot(actual_dir, expected_dir), -1, 1))
```

This is necessary but not sufficient.

### 2. Plane / Pole Error

For arm and leg chains, use three points to define the anatomical plane:

```text
arm plane: shoulder, elbow, wrist
leg plane: hip, knee, ankle
```

Compute a plane normal with cross products.  Compare source and target plane
normals after calibration.  Also record signed point-to-plane distance for the
middle joint.  This catches "endpoint looks close, elbow bends wrong."

### 3. Twist Error

After primary segment alignment, compare the secondary axis around the primary
axis.  This catches "arm points at the right place, hand still rotated/cupped."

### 4. Hand / Finger Reference Error

Fingers are not solved by upperarm/forearm endpoint alignment.  If finger nodes
are unmapped, their KOTOR rest pose remains.  The current curled-hand symptom
should be reported as:

```text
hand role mapped, finger roles unmapped; KOTOR finger rest pose is preserved.
```

### 5. Matrix Convention Audit

Every coordinate conversion helper should record:

```text
source handedness
target handedness
row/column assumption
pre/post multiplication convention
determinant before/after conversion
```

This prevents a copied formula from silently transposing a transform.

## Solver Implications

### Keep Named Spaces Everywhere

Prefer names like:

```text
source_global
source_reference_global
source_semantic_frame
target_reference_global
target_parent_world
target_local_controller
```

over generic `M`, `R`, `q1`, `q2` when writing production code.

### Use Quaternion Difference For Pose Motion

Retargeting should treat motion as an angular displacement from reference to
current pose.  In project terms:

```text
source_delta = source_current * inverse(source_reference)
```

or the equivalent dictated by the project's multiplication convention.  This
must stay behind named helper functions so order mistakes do not spread.

### Use Matrices For Basis Conversion, Quaternions For Stored Rotations

Basis construction and handedness conversion are matrix problems.  Stored
animation orientation keys are quaternion problems.  Build/orthogonalize the
frame as a matrix, convert once to the internal XYZW quaternion convention, and
never component-shuffle a quaternion as a basis conversion.

### Treat Non-Uniform Scale And Shear As Invalid For Retarget Frames

Rotation frames should be rigid.  If a frame determinant is near zero, mirrored
unexpectedly, or contains scale/shear, warn and re-orthonormalize or reject.

## PMBAM-Specific Consequences

The PMBAM arm chain has intermediate Aurora nodes:

```text
lbicep_g -> LbicepL_g -> Lforearm_g -> Lhand_g
rbicep_g -> RbicepL_g -> Rforearm_g -> Rhand_g
```

Therefore:

- `upperarm` motion may need to distribute across `lbicep_g` and `LbicepL_g`.
- `forearm` motion should be calibrated against `Lforearm_g`, not a generic
  lowerarm name.
- hand orientation requires `Lhand_g/Rhand_g` and likely finger reference
  policy.
- KOTOR dummy hook nodes such as `lhand/rhand` may be attachment targets, not
  the same thing as skinned hand controllers.

## Next Engineering Tasks

1. Add a pole-plane audit for mapped arm/leg chains.
2. Add twist-axis audit for forearm/hand and calf/foot chains.
3. Add a hand/finger mapping report so the viewport can explain curled hands.
4. Add matrix convention metadata to `BasisConversion` and solver reports.
5. Extend the calibrated frame tests from single segment to three-point
   shoulder/elbow/wrist and hip/knee/ankle chains.
6. Only after those audits pass, try a new viewport export candidate.

## Rule To Carry Forward

Retargeting quality is not "does the mesh deform?" and not even "does the limb
point in the right direction?"  The quality gate must prove:

```text
direction + anatomical plane + twist + endpoint + stable parent-local keys
```

for every important chain across the full clip.
