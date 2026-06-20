# Transform Skill

Use this skill for matrices, coordinate spaces, quaternions, pivots, gizmos,
camera transforms, animation transforms, and object/world/local conversion bugs.

## Book Grounding

- `3D Math Primer`: coordinate handedness, multiple coordinate spaces, matrices, homogeneous transforms, rotations, quaternions, cameras, and geometric primitives.
- `Mathematics for Computer Graphics`: 3D transforms, homogeneous coordinates, change of axes, arbitrary-axis rotation, vector transforms, quaternions, interpolation, and analytic geometry.
- `Game Engine Architecture`: points/vectors, matrices, quaternions, rotational representations, debug cameras, and runtime loops.
- Rigging books: pivot points, hierarchy, local rotation axes, zeroed controls, and controller inheritance.

## Workflow

1. Write down spaces at every boundary: source file, bind, object, parent, world, camera, clip, screen, and UI/gizmo space.
2. Keep points, vectors, normals, and pivots distinct. Pivots are points with transform semantics; normals are directions with special transform rules.
3. For hierarchy bugs, inspect parent-to-child composition order and whether code assumes row-major/column-major or pre/post multiplication.
4. For rotations, prefer quaternions for interpolation and stable animation blending; use Euler angles mainly for UI input/output.
5. For pivot-only edits, keep visible geometry stable by compensating object transforms as required by the scene contract.
6. For mirrored or imported rigs, verify local axes and handedness before blaming animation clips.

## GhostRigger Checks

- Shared math belongs in `src/math` or the corresponding native math package.
- Pivot tools must integrate with `SceneObjectInstance.transform` and `SceneObjectInstance.pivot`.
- Axis/reference modes must use `TransformReferenceController`.
- Visible geometry must not jump during pivot-only edits.

## Failure Patterns

- Object moves when pivot changes: missing compensation transform.
- Animation works on one object but not another: pose source/object ID or bind-space mismatch.
- Camera picking drifts: ray was built in the wrong space or used stale projection/view matrices.
- Quaternion interpolation flips: check sign continuity and normalize after blend.
- Normals look wrong under scale: transform normals separately from positions.
