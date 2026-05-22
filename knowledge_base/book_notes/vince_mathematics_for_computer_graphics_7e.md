# John Vince — Mathematics for Computer Graphics, 7th Ed.

Local source: `C:/Users/NewAdmin/Downloads/_OceanofPDF.com_Mathematics_for_Computer_Graphics_7E_-_John_Vince.pdf`  
Pages scanned: 614  
Purpose: foundational math reference for GhostRigger geometry, rendering,
animation, retargeting, validation, and analysis code.

## Chapter Map

| PDF Page | Chapter / Topic | GhostRigger Use |
|----------|-----------------|-----------------|
| 24 | Introduction | Shared notation and why graphics math needs careful definitions. |
| 28 | Numbers | Numeric robustness, tolerances, finite-value checks. |
| 56 | Algebra | Function notation, series, identities used by geometry algorithms. |
| 78 | Trigonometry | Rotation angles, sine/cosine relationships, angular diagnostics. |
| 93 | Coordinate Systems | Cartesian, polar, spherical, cylindrical, homogeneous coordinates. |
| 106 | Determinants | Matrix validity, handedness, degeneracy checks. |
| 124 | Vectors | Basis vectors, dot/cross products, normals, vector manipulation. |
| 148 | Matrices | Transform representation, multiplication, inverse, orthogonality. |
| 185 | Complex Numbers | Bridge concept toward quaternion algebra. |
| 212 | Geometric Transforms | 2D/3D translation, rotation, scale, yaw/pitch/roll, arbitrary-axis rotation. |
| 262 | Quaternion Algebra | Unit quaternions, norm, inverse, multiplication. |
| 289 | Quaternions in Space | Quaternion rotation, matrix conversion, multiple rotations. |
| 312 | Interpolation | Lerp, spline ideas, quaternion interpolation. |
| 327 | Curves and Patches | Future curve editors, animation tangents, path previews. |
| 351 | Analytic Geometry | Lines, planes, intersections, distance tests. |
| 395 | Statistics | Metrics, QA aggregation, thresholds and outlier reports. |
| 423 | Barycentric Coordinates | Mesh editing, hit testing, interpolation over triangles. |
| 450 | Geometric Algebra | Advanced orientation/transform context; optional future research. |
| 484 | Calculus: Derivatives | Motion rate, tangent/velocity, smoothness audits. |
| 536 | Calculus: Integration | Accumulated motion, area/volume, future physics-style tools. |
| 574 | Fourier Series | Cyclic motion and signal analysis; future animation curve diagnostics. |
| 584 | Worked Examples | Check math implementations against small hand-solvable examples. |

## Core Principles To Reuse

### Coordinate Systems Are Contracts

Every vector or rotation is meaningful only inside a coordinate frame. GhostRigger
should name spaces explicitly:

```text
source_global
source_reference
aurora_local
aurora_parent_world
viewport_world
mdl_controller_space
```

Do not move values across those spaces without a named conversion helper.

### Rotation Frames Must Be Orthogonal

Rigid character animation needs transforms that preserve distances and angles.
Whenever GhostRigger constructs a frame from noisy or external data, verify:

- axes are unit length;
- axes are mutually perpendicular;
- determinant has expected sign;
- matrix can be safely converted back to quaternion.

### Quaternions Need Strict Boundary Handling

Use quaternions for orientation keys and interpolation, but keep conversions
localized:

- internal convention: explicit XYZW or WXYZ, never implied;
- MDL boundary convention: verified and documented;
- normalize every generated key;
- hemisphere-fix adjacent keys;
- compare quaternions by angular distance, not raw components.

### Interpolation Is A Validation Topic

Animation preview is not just evaluating stored keys. The evaluator must prove
that interpolation is stable:

- no quaternion sign flips;
- no angular spikes;
- no non-finite transforms;
- no unintended root drift;
- no non-root translation changes unless policy allows them.

## GhostRigger Applications

### MDL/MDX Loading and Writing

Use determinant and inverse-matrix checks when validating loaded transforms.
Readback validators should compare semantic transforms, not just bytes, because
equivalent quaternions may differ by sign or writer layout.

### Rendering

Use matrix and vector sections for:

- camera/view/projection sanity checks;
- normal/tangent validation;
- bounding boxes and transformed points;
- lightmap and texture coordinate debugging.

### Skinning

Skinning depends on a stable relation between bind pose, current pose, and mesh
space. The matrix and quaternion chapters support the current policy: preserve
node order, bind transforms, and rest translations unless an explicit tool is
performing geometry rebinding.

### Retargeting

Use coordinate systems, basis vectors, matrix inverse/order, quaternion inverse,
and interpolation chapters as the math basis for:

```text
source reference pose
-> source motion delta
-> target calibrated frame
-> parent-local Aurora controller
-> evaluator/viewport audit
```

### Module / Walkmesh / Geometry Tools

Analytic geometry and barycentric coordinates are the useful sections for:

- triangle picking;
- walkmesh validation;
- room/door transition checks;
- point-in-face or ray-hit tools;
- interpolating surface data.

## Future Knowledgebase Follow-Ups

- Add a small formula note for quaternion angular distance and sign-equivalence.
- Add a matrix-validity checklist shared by rendering, retargeting, and export.
- Add a barycentric coordinate note for mesh/walkmesh selection tools.
- Add interpolation examples for animation curve diagnostics.
