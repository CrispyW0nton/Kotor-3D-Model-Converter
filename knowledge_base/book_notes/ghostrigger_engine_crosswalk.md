# GhostRigger Engine Book Crosswalk

This crosswalk turns the book notes into practical guidance for any GhostRigger
subsystem, not only retargeting.

## Subsystem Crosswalk

| GhostRigger Area | Primary Book Concepts | Use These Notes |
|------------------|-----------------------|-----------------|
| MDL/MDX loader and writer | Resource identity, binary/resource dependencies, transforms, quaternions, readback validation | Gregory resources; Vince matrices/quaternions; Dunn coordinate spaces |
| KOTOR resource browser | Resource manager, archives, file formats, dependency lookup | Gregory resources and file system |
| Viewport rendering | Coordinate spaces, matrices, camera transforms, normals/tangents, debug drawing, capture | Dunn graphics/math; Vince transforms; Gregory debugging |
| Skinning | Binding pose, matrix palettes, rigid transforms, normal handling, determinant/orthogonality | Dunn skeletal/skinned mesh; Vince matrices; Gregory runtime animation overview |
| Animation playback | Timelines, interpolation, quaternions, controller semantics, debug capture | Gregory time/debugging; Vince interpolation/quaternions; Dunn rotation |
| UE/FBX import/export | Asset conditioning, coordinate/handedness conversion, source conditioning | Gregory asset pipeline; Dunn coordinate conventions; Vince homogeneous transforms |
| Retargeting | Nested spaces, reference poses, quaternion difference, calibrated frames, plane/twist audits | Dunn chapters 3/8/10; Vince vectors/matrices/quaternions; Gregory pipeline gates |
| Character Builder | Asset pipeline, resource identity, hook validation, preview/capture tooling | Gregory tools/resources/debugging; Dunn transforms/primitives |
| Module and walkmesh tools | Geometric primitives, barycentric coordinates, plane tests, picking rays | Dunn primitives/appendix; Vince analytic geometry/barycentric coordinates |
| Texture/TXI/TPC rendering | Resource dependencies, texture asset pipeline, tangent space | Gregory resources; Dunn tangent-space/graphics |
| Qt UI controllers | Tool architecture, worker boundaries, logs/status/debug surfaces | Gregory tools, concurrency, debugging |
| Performance and full scans | Profiling, resource loading, concurrency, deterministic tests | Gregory profiling/concurrency/resources |
| Validation and QA | Numeric tolerances, structured logs, screenshots/capture packs, semantic readback | All three: Vince math, Dunn geometry tests, Gregory debug/capture |

## Development Rules Derived From The Books

### 1. Name Spaces, Not Just Values

Any transform-heavy code should prefer names such as:

```text
mdl_local
mdl_parent_world
source_fbx_global
viewport_world
skin_bind
export_readback
```

Generic `matrix`, `rot`, or `pose` variables should be local and short-lived.

### 2. Validate Before Visual Trust

Visual output can look plausible while math is wrong. Before accepting a result,
check:

- finite transforms;
- unit quaternions;
- determinant and orthogonality;
- expected handedness;
- semantic readback;
- viewport/capture evidence.

### 3. Treat Exports As Built Resources

Every generated file should have a provenance trail:

- source asset path/hash;
- profile/settings hash;
- game variant;
- target resref;
- dependency list;
- validation status;
- preview/capture status.

### 4. Keep Tool UI Thin

Qt widgets should select inputs, launch work, show progress, and display reports.
Importer, solver, writer, renderer, and validator logic should stay in core
modules with headless tests.

### 5. Make Debugging First-Class

For every visual workflow, plan the debug surface with the feature:

- overlay lines/axes/labels;
- numeric audit JSON;
- screenshot/capture pack;
- status/log messages;
- minimal reproduction fixture.

## Current Priority Derived From The Crosswalk

For the retargeting work specifically, the next high-value engineering slice is:

```text
pole-plane + twist audits
-> viewport overlay/capture pack
-> retarget build manifest
-> only then another PMBAM export candidate
```

For broader GhostRigger, the same pattern applies: build a measured tool surface
before trusting manual visual inspection or game-only feedback.

## Maintenance Checklist

When adding a feature:

1. Identify which subsystem row applies.
2. Read the listed book notes.
3. Add a small audit/test inspired by the relevant math or engine principle.
4. Update the subsystem knowledgebase note if the implementation teaches a new
   durable rule.
