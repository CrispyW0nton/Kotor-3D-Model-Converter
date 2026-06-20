# Map Studio Skill

Use this before changing the Level Editor / Map Studio modeling workspace,
tool belt, terrain sculpting, authored room geometry, walkmesh generation,
placement authoring, or module packaging UX.

Sources inspected: Mukundan mesh processing, de Berg computational geometry,
Hayes OpenGL, Marschner/Shirley computer graphics fundamentals, Dunn/Parberry
3D math, Vince graphics math, Qt 6 GUI cookbook, Fitzpatrick/Summerfield Qt,
O'Hailey rigging workflows, and automatic skinning/weight retargeting notes.

## Product Rule

Map Studio should feel familiar to Maya/ZBrush users, but every tool must have a
KOTOR module purpose. A primitive, bevel, terrain brush, snap, or placement is
not done until it can be represented in KMAP, validated against KOTOR module
rules, and routed toward MDL/MDX/WOK/LYT/VIS/PTH/GIT/ARE/IFO export.

## Workspace Model

- Keep tool modes explicit: Object, Vertex, Edge, Face, Terrain, Walkmesh,
  Placement, Lighting, Validation, Export.
- Keep the modeling belt customizable, but back every button with a stable
  action key and an owning service/API. Do not bury behavior in the window.
- Separate visual authoring from export ownership. Room mesh, terrain mesh,
  walkmesh, gameplay markers, and module metadata can be edited together, but
  they are distinct authored resources.
- Treat the viewport as an editor surface, not the source of truth. The source
  of truth is the KMAP/authored module state plus command history.
- Make destructive edits undoable. Component edits, welds, booleans, terrain
  strokes, object combine/separate, placement moves, and transition edits must
  leave command-level evidence.

## Geometry Authoring Rules

- Use structured topology for editable geometry: vertices, edges, faces,
  material slots, UV intent, object boundaries, normals, and WOK surface intent.
- Triangulate deterministically before export-facing validation.
- Reject degenerate room and walkmesh output early: zero-area faces,
  zero-length edges, sliver triangles, inverted winding, NaN transforms, and
  unlinked transition markers.
- Snap is not weld. Snap moves components; weld changes topology and must
  repair face indices, WOK references, selection state, and undo metadata.
- Combine/separate should preserve stable object IDs and material names so a
  modder can export UV/texturing work to another DCC and re-import safely.

## Terrain Sculpting Rules

- Terrain sculpting must be low latency: preview strokes should update only
  dirty regions, coalesce pointer samples, and defer full validation until
  commit or idle.
- Store brush parameters as authored operations: brush type, radius, strength,
  falloff, locked axes, material/walkability intent, and affected room/terrain.
- Every terrain change must have a walkmesh consequence: walkable, blocked,
  ramp, transition, water, grass, metal, or explicit "visual only."
- Provide smoothing, flatten, raise/lower, terrace, ramp, noise, and erosion-like
  workflows as focused KOTOR map-building tools, not generic sculpt toys.

## Placement And Transition Rules

- Use KOTOR words in UI: resref, module, GIT, waypoint, trigger, door,
  TransitionDestin, LinkedTo, LinkedToModule, Override, `.mod`.
- Placement rows should show readiness, transition status, and summary text so a
  modder can tell whether a doorway is only visual or actually linked.
- Doorways, triggers, waypoints, and player starts must become visible viewport
  markers plus authored GIT/IFO data.
- Export readiness must distinguish previewable, export candidate,
  installed-ready-for-game-test, and game-tested.

## Performance Rules

- Active sculpting, component dragging, and gizmo moves must stay interactive.
  Cache draw data, batch updates, and avoid full rebuilds per mouse move.
- Use Qt model/view for resource lists, validation rows, object trees, and
  placement tables; do not rebuild entire widgets for one value change.
- Long operations such as module builds, scans, validation sweeps, and exports
  must run as jobs/progress tasks rather than blocking the UI thread.
- Prefer small core tests for geometry math and command results, then visible UI
  testing for workflows that depend on user gestures or viewport rendering.

## Implementation Checklist

Before coding a Map Studio feature, fill this in:

```text
Roadmap task:
User-facing modder story:
Owning UI surface: existing Level Editor / Map Studio
Owning core/system/adapter package:
Edited authored resource(s):
KOTOR validation gate:
Export/proof state affected:
Undo/redo behavior:
Performance budget:
Tests:
```

If any line is unclear, stop and audit ownership before adding code.
