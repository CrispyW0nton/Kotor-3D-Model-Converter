# GhostRigger Book-Derived Working Skills

Purpose: provide concise, reusable development skills distilled from the local
books in `knowledge_base/books` and prior notes in `knowledge_base/book_notes`.
These notes are not copies of the books. They are GhostRigger-specific working
rules to consult before changing architecture, Map Studio tools, viewport
behavior, Character Builder rigging, or KOTOR export logic.

## Source Set

Local book/PDF sources inspected on 2026-06-20:

- Mukundan, *3D Mesh Processing and Character Animation*
- de Berg et al., *Computational Geometry*
- Hayes, *Computer Graphics Development with OpenGL*
- Fitzpatrick, *Create GUI Applications with Python and Qt6*
- Marschner/Shirley et al., *Fundamentals of Computer Graphics*
- Kneusel, *Math for Programming*
- Vince, *Mathematics for Computer Graphics*
- Lee, *Qt 6 C++ GUI Programming Cookbook*
- O'Hailey, *Rig it Right! Maya Animation Rigging Concepts*
- Pan et al., *Automatic skinning and weight retargeting of articulated characters*
- Dunn/Parberry, *3D Math Primer for Graphics and Game Development*
- Summerfield, *Rapid GUI Programming with Python and Qt*
- Xu, *System Design Interview*

Also consult existing derived notes in `knowledge_base/book_notes`, especially:

- `qt_python_ui_architecture_for_ghostrigger.md`
- `python_clean_architecture_for_ghostrigger.md`
- `ghostrigger_programming_crosswalk.md`
- `character_builder_rigging_skinning_sources_2026_06_04.md`
- `dunn_parberry_3d_math_primer_2e.md`
- `vince_mathematics_for_computer_graphics_7e.md`

## Skill Index

Use these files before making related code or roadmap decisions:

- `meshskill.md`: mesh representation, topology, object boundaries, exportable
  KOTOR room/object geometry, UV/DCC handoff.
- `vertexskill.md`: vertex/edge/face component editing, snapping, welding,
  selection, validation, and undo expectations.
- `extrusionskill.md`: extrusion, bevel, inset, bridge, boolean, split/fill,
  and cleanup tools for Map Studio.
- `computationalgeometryskill.md`: robust predicates, polygon operations,
  spatial queries, triangulation, tolerances, and degeneracy handling.
- `terrainsculptskill.md`: low-latency terrain sculpting, heightfields,
  brush coalescing, dirty regions, walkability/WOK validation.
- `uvtextureskill.md`: UV preservation, material slots, texture references,
  lightmap/secondary UV policy, and DCC round-trip constraints.
- `riggingskill.md`: Character Builder skeleton fitting, binding, skinning,
  deformation preview, donor weights, and export preflight.
- `qtuiskill.md`: Qt actions, model/view, threading, undo, theming, and
  studio/window boundaries.
- `mathskill.md`: coordinate spaces, matrices, quaternions, transforms,
  geometry tests, and determinant/handedness checks.
- `performanceskill.md`: no-lag interaction design, coalescing, caching,
  async jobs, bounded budgets, and validation cadence.
- `mapstudioskill.md`: Maya/ZBrush-inspired Map Studio workspace rules tied to
  KOTOR authored resources, validation, export readiness, and game proof.

## 2026-06-20 Book Pass Method

This pass inspected the local PDF metadata, outlines, and targeted topic hits
with `pypdf` for mesh, vertex, edge, face, extrusion, bevel, boolean, terrain,
heightfield, sculpt, snapping, undo, model/view, OpenGL, quaternion, matrix,
rigging, skinning, weight, BVH, triangulation, and Delaunay. The resulting docs
are paraphrased GhostRigger working rules, not copied book excerpts.

Practical source-to-skill mapping:

- Mukundan and de Berg drive topology, adjacency, triangulation, degeneracy,
  and mesh-operation validation.
- Marschner/Shirley, Hayes, Vince, Dunn/Parberry, and Kneusel drive transforms,
  robust math, coordinate conventions, rendering data flow, and performance
  budgets.
- O'Hailey plus the automatic skinning/weight-retargeting paper drive
  Character Builder guide-joint, donor-weight, bind-pose, and deformation
  preview rules.
- Fitzpatrick, Summerfield, Lee, and official Qt docs drive actions,
  model/view lists, undo stacks, workers, theme/layout, and tool-belt UI.
- Xu is used only for scale/performance discipline: caching, bounded work,
  background jobs, and explicit degraded states.

## Program-Wide Rule

Before implementing a feature, name the owning skill and owning code layer:

```text
User task:
Owning studio/window:
Owning core/system/adapter package:
Book-derived skill(s):
KOTOR validation/export gate:
Capability honesty: planned / previewable / export candidate / game-tested
```

If a change cannot name its owning skill and KOTOR gate, pause and audit the
architecture before coding.

## How To Use These Skills

1. Read the specific skill file before editing.
2. Keep Qt as presentation; put reusable math, modeling, export, and validation
   behavior in the owning core/system/adapter layer.
3. Treat Maya/ZBrush terminology as UX language, not as permission to ignore
   KOTOR constraints.
4. Preserve stable KMAP/KMAX IDs and source KOTOR resrefs.
5. Use ValidationBus/ExportJob/readback/game proof for claims of readiness.
6. Keep previews and live edits fast; defer full rebuild/export work until
   commit, validation, or staged export.
