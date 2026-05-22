# Dunn & Parberry — 3D Math Primer for Graphics and Game Development, 2nd Ed.

Local source: `C:/Users/NewAdmin/Downloads/3D Math Primer for Graphics and Game Development 2nd Edition.pdf`  
Pages scanned: 846  
Purpose: practical 3D math guide for coordinate spaces, rotations, geometric
tests, rendering, skeletal animation, motion, and curves in GhostRigger.

## Chapter Map

| PDF Page | Chapter / Topic | GhostRigger Use |
|----------|-----------------|-----------------|
| 23 | Cartesian Coordinate Systems | Handedness, axis conventions, angle direction. |
| 53 | Vectors | Points vs vectors, dot/cross product, unit vectors, distances. |
| 101 | Multiple Coordinate Spaces | World/object/upright spaces, basis transforms, nested spaces. |
| 135 | Introduction to Matrices | Matrix notation, row/column vector hazards, geometric meaning. |
| 159 | Matrices and Linear Transformations | Rotation, scale, shear, combining transforms, rigid transforms. |
| 183 | More on Matrices | Determinants, inverse, orthogonal matrices, orthogonalization, homogeneous matrices. |
| 213 | Polar Coordinate Systems | Useful for cameras, spherical controls, angular UI and diagnostics. |
| 239 | Rotation in Three Dimensions | Orientation vs direction, matrices, Euler, axis-angle, quaternions, conversions. |
| 317 | Geometric Primitives | Lines, rays, boxes, planes, triangles, barycentric space, polygons. |
| 365 | Mathematical Topics from 3D Graphics | Rendering pipeline, coordinate spaces, meshes, skeletal animation, tangent space, skinned mesh shaders. |
| 501 | Mechanics 1 | Velocity, acceleration, derivatives/integrals, circular motion. |
| 575 | Mechanics 2 | Forces, springs, rotational dynamics; future simulation/guide tools. |
| 667 | Curves in 3D | Future animation/path/guide editing and smooth camera/pose curves. |
| 737 | Afterword | General practice context. |
| 739 | Appendix A Geometric Tests | Reusable hit tests and geometry validation. |
| 767 | Appendix B Answers | Sanity checks for math exercises. |

## Core Principles To Reuse

### Orientation Is Not Direction

A direction vector does not contain twist. This is critical for animation and
retargeting. A hand can be in the wrong orientation even if the forearm points
in roughly the correct direction. Any pose-quality gate should measure:

```text
segment direction
anatomical plane / pole direction
twist about the segment
endpoint position
controller stability
```

### Multiple Coordinate Spaces Are Normal

GhostRigger has many spaces:

- KOTOR MDL node local;
- KOTOR parent/world;
- skin bind space;
- source FBX global/local;
- viewport world/camera;
- export/readback semantic space.

Use named conversions and tests. Avoid generic helpers whose names do not state
which spaces are involved.

### Row/Column And Handedness Conventions Are Hazards

The book explicitly warns that equations transpose across conventions. For
GhostRigger:

- never paste a matrix formula without checking row/column convention;
- record whether a helper post-multiplies or pre-multiplies;
- convert handedness through matrices;
- check determinant signs before and after conversion.

### Orthonormal Bases Are The Practical Foundation

Rigid transforms, tangent spaces, retarget frames, and camera frames all require
orthonormal axes. When axes are reconstructed:

- normalize primary axis;
- project secondary hint onto the perpendicular plane;
- cross to build the third axis;
- re-orthonormalize;
- check determinant.

### Quaternion Difference Expresses Pose Motion

Retargeting, animation blending, and pose comparison all need "rotation from A
to B." Use named quaternion-difference helpers with the project convention
encoded once. Compare rotations by angular distance and treat `q` and `-q` as
equivalent.

## GhostRigger Applications

### Retargeting And Animation

Use chapters 3 and 8 constantly:

- reference pose = named coordinate-space baseline;
- motion delta = angular displacement from reference to current;
- KOTOR controller = absolute parent-local result;
- quality gate = direction + plane + twist + endpoint.

The PMBAM arm problem is exactly an orientation-vs-direction failure.

### Viewport And Camera

Use coordinate-space and polar-coordinate chapters for:

- arcball/orbit camera stability;
- front/back/side/top presets;
- camera debug overlays;
- consistent axis widget behavior.

### Rendering And Skinning

Use the graphics chapter for:

- skinned mesh matrix-palette thinking;
- normal/tangent-space validation;
- avoiding nonuniform scale/shear in skinning transforms;
- transformed AABB checks.

### Mesh, Walkmesh, And Selection Tools

Use geometric primitives and appendix tests for:

- ray picking;
- plane tests;
- point-to-plane distances;
- triangle barycentric interpolation;
- AABB transforms;
- walkmesh edge/transition validation.

### Motion And Curves

Use mechanics and curve chapters for:

- animation speed/velocity diagnostics;
- camera flythroughs;
- guide-handle smoothing;
- cyclic motion and root drift analysis;
- future curve/tangent UI.

## Required Future Tests Inspired By This Book

- A coordinate-convention unit test for every matrix helper that crosses
  source/KOTOR/viewport spaces.
- A determinant/orthogonality audit for every constructed retarget frame.
- A pole-plane test for arm and leg chains.
- A twist-axis test for forearm/hand and foot/toe chains.
- A ray/triangle/barycentric test suite for mesh and walkmesh editing.
- A camera preset test that verifies expected axes and handedness.

## Maintenance Note

When an implementation uses dot, cross, matrix inverse, quaternion difference,
orthogonalization, or geometric primitive tests, link back here or add a
subsystem-specific note in the relevant knowledgebase folder.
