# Math Skill

Use this before changing coordinate conversions, transforms, cameras, viewport
picking, retargeting, rig fitting, terrain sampling, or geometry validation.

Sources: Dunn/Parberry 3D math, Vince graphics math, Kneusel programming math,
Marschner/Shirley graphics fundamentals.

## Working Rules

- Name coordinate spaces explicitly. Avoid helpers that accept "a transform"
  without saying source and destination spaces.
- Matrices and quaternions are convention-sensitive. Record row/column,
  pre/post multiply, handedness, units, and axis system.
- Convert handedness and basis with matrices, not ad hoc quaternion component
  shuffling.
- Rebuild orthonormal bases carefully: normalize primary axis, project secondary
  hint, cross product, normalize, determinant check.
- Treat `q` and `-q` as equivalent quaternion orientations.
- Direction is not orientation. Segment direction checks do not catch twist.
- Use barycentric/triangle-plane tests for WOK and terrain height sampling, not
  vertex-average shortcuts.
- Use robust comparison policies. Exact equality is useful for byte/fixture
  audits, but viewport picking, fitting, snapping, and geometry predicates need
  named tolerances and degeneracy handling.
- Bounding boxes are not anatomy. Use them for coarse scale/framing, then use
  landmarks, axes, and joint chains for character fitting or retargeting.

## GhostRigger Applications

- Retargeting quality gates need direction, plane, twist, endpoint, and root
  policy checks.
- Character Builder auto-fit needs landmark transforms plus scale/orientation
  evidence, not only bounding boxes.
- Map Studio placement validation must sample actual WOK triangle planes.
- Viewport gizmos and snapping need clear world/local/object/reference modes.
- Terrain and floor-plan tools need deterministic rounding/snap grids so saved
  KMAP files do not drift across repeated edits.

## Preflight Checklist

- What are the input/output spaces?
- Are units meters, centimeters, KOTOR units, or pixels?
- Are axes/right-handedness documented?
- Is the transform rigid, affine, or possibly sheared?
- Is the determinant sane?
- Are quaternions normalized and hemisphere-consistent?
- Is the calculation stable near degenerate cases?

## Tests To Prefer

- Identity and round-trip transform tests.
- Known-axis rotations and determinant checks.
- Barycentric inside/outside and triangle height tests.
- Quaternion angular-distance tests.
- Coordinate conversion tests with explicit named spaces.
