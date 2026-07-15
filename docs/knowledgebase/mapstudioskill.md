# Map Studio Skill

Use this before changing the Level Editor / Map Studio modeling workspace,
tool belt, terrain sculpting, authored room geometry, walkmesh generation,
placement authoring, or module packaging UX.

Also read `toolbeltskill.md` before changing action belts, command search,
shortcuts, or customization; read `objectseparationskill.md` before changing
separate/combine, DCC handoff, or export-object ownership.

Sources inspected: Mukundan mesh processing, de Berg computational geometry,
Hayes OpenGL, Marschner/Shirley computer graphics fundamentals, Dunn/Parberry
3D math, Vince graphics math, Qt 6 GUI cookbook, Fitzpatrick/Summerfield Qt,
O'Hailey rigging workflows, and automatic skinning/weight retargeting notes.

## Product Rule

Map Studio should feel familiar to Maya/ZBrush users, but every tool must have a
KOTOR module purpose. A primitive, bevel, terrain brush, snap, or placement is
not done until it can be represented in KMAP, validated against KOTOR module
rules, and routed toward MDL/MDX/WOK/LYT/VIS/PTH/GIT/ARE/IFO export.

The Level Editor / Map Studio window is the product surface. Do not put these
workflows in the main model viewer, Character Builder, or Retarget Workbench.

## Lighting Export Rules

- Fullbright authored modules must be fullbright in both ARE metadata and room
  MDL behavior. Set ARE ambient/diffuse/dynamic ambient to white, disable fog
  and shadows, and export room mesh ambient/diffuse as white with mesh shadows
  off.
- Do not leave dynamic/shadow Aurora light nodes active in a fullbright room
  MDL. The `tst_light` KOTOR2 proof showed that duplicate zero-radius
  `colorlight1` nodes with dynamic influence/shadows could trigger an NVIDIA
  OpenGL out-of-memory crash during warp even when ARE lighting was already
  fullbright. Fullbright export should neutralize light-node `dynamic_type`,
  `affect_dynamic`, `shadow`, `flare`, and `fading_light` fields.
- Treat authored room lights as editor intent until a real lightmap or game
  proof exists. For graybox fullbright proof, prefer ARE/material lighting and
  inert MDL light nodes over runtime dynamic lights.

## Workspace Model

- Keep tool modes explicit: Object, Vertex, Edge, Face, Terrain, Walkmesh,
  Placement, Lighting, Validation, Export.
- Keep the modeling belt customizable, but back every button with a stable
  action key and an owning service/API. Do not bury behavior in the window.
- Search, filters, presets, and favorites belong in the belt UI; operation
  semantics belong in core modules or systems.
- Separate visual authoring from export ownership. Room mesh, terrain mesh,
  walkmesh, gameplay markers, and module metadata can be edited together, but
  they are distinct authored resources.
- Treat the viewport as an editor surface, not the source of truth. The source
  of truth is the KMAP/authored module state plus command history.
- Make destructive edits undoable. Component edits, welds, booleans, terrain
  strokes, object combine/separate, placement moves, and transition edits must
  leave command-level evidence.

## Maya Modeling Shelf And Construction History

- The canonical manual-modeling surface is the Map Studio Maya Modeling shelf,
  using original Ghost Studio icon art and stable Ghost action keys. Do not copy
  Autodesk icon files, private code, or proprietary assets. The retired
  `gmodeler_marking_menu.py` path is compatibility state only; do not add new
  product behavior to it.
- A routed shelf button is not proof of Maya parity. Each command must prove
  frontmost hover, live non-accumulating preview, complete advertised options,
  cancel, one commit/undo/redo transaction, selection retention, attribute
  preservation, practical frame time, KMAP reload, and the relevant KOTOR
  export/game gate before it is labeled equivalent.
- Polygon primitives are retained construction recipes, not one-shot mesh
  replacements. Persist a versioned construction-node ID and typed parameters;
  property scrubbing evaluates only that primitive and patches only its
  resident renderer node. Do not decode/serialize the full authored KMAP during
  a preview frame.
- The initial retained primitive set is Plane, Cube, Cylinder, Sphere, Cone,
  and Torus. Preserve dimensions/radii, independent subdivisions, normalized
  KOTOR Z-up axis, height baseline, UV policy, cap policy, and twist where the
  primitive supports them. Render subdivision density must not automatically
  inflate a floor WOK.
- `Freeze Transformations` and `Delete History` are separate contracts. Freeze
  resets transform channels while preserving the primitive recipe through a
  downstream transform stage. Delete History explicitly evaluates and bakes
  the construction stack; it must be undoable. Never silently destroy every
  primitive recipe in a room because one object enters component editing.
- Editable topology needs stable logical vertex/edge/face/shell identity
  separate from renderer triangles and UV/hard-normal seam duplication.
  Extrude, Bevel, Bridge, Connect, Multi-Cut, Insert Edge Loop, Target Weld,
  Combine, and Separate must consume that shared topology/remap contract rather
  than infer polygons repeatedly from export triangles.
- Picking is depth-correct and frontmost. A face, edge, or vertex hidden behind
  nearer geometry must not become the active modeling target unless the user
  explicitly enables through/backface selection.

## Imported Stock Geometry (map editing)

- Stock game rooms become editable through `authored_imported_mesh.py`:
  `ImportedMeshRoomPrimitive` stores per-texture surfaces (baked transforms,
  original UVs/normals, stock WOK when available). It is a first-class room
  primitive: `compile_authored_room_spec`, validation, the KMAP bridge
  (`type: imported_mesh`), preview, undo, and export all dispatch on it.
- Hover identity contract: stock preview mesh roles are `stock_room_<i>` and
  imported surfaces map by the same index (`render` for 0,
  `imported_srf_<i>` after) because `_flattened_mesh_nodes` and
  `build_imported_mesh_primitive_from_stock_model` share traversal order and
  skip rules (non-render, AABB). Changing either traversal breaks face edits.
- GModeler `face_delete` / `face_set_texture` auto-convert a hovered stock
  room (one undoable command) and retire the stock KMAP room row so only the
  editable copy renders.
- KMAP payloads for imported meshes pack vertex data as base64 little-endian
  float32/int32 (`vertices_b64` etc.); everything else stays readable JSON.
- UVs: imported geometry keeps its original UVs — retexture without
  re-unwrap. NEW architecture geometry uses world-space tiled projection
  (`tiled_uvs_for_vertices`): one texture repeat per tile-size meters, with
  the tile size sampled from an existing surface of the same texture
  (`matched_uv_tile_size`) so new pieces tile at the same density as the
  vanilla room they extend. That is how vanilla KOTOR architecture is
  mapped; never ship normalized 0..1 planar UVs on level geometry
  (`planar_uvs_for_vertices` is preview-only). Unique unwrap + packing
  (sculpted props, future lightmap UVs) goes through the RizomUVMCP
  pipeline (`Workspaces/RizomUVMCP`, `run_full_pipeline`: seam planning →
  RizomUV or xatlas+Blender fallback → packed OBJ/FBX) — bridge by
  exporting surfaces to OBJ and re-importing the UVs.
- Polycount guardrails: `MDL_MAX_VERTICES_PER_SURFACE` (65535, u16 MDL
  index limit — blocking) and `ROOM_TRIANGLE_WARNING_BUDGET` (15000 —
  warning; vanilla rooms run low thousands). Terrain sculpting and any
  ZBrush-style workflows must decimate to game resolution before export.

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
- Center pivot and freeze transforms are authoring commands. They must update
  KMAP object transforms/pivots without silently baking mesh vertices unless the
  user selects a bake/export operation.

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
- PTH pathing, WOK walkability, entry point placement, and transition markers
  are load/playability gates. Treat them as first-class readiness signals, not
  afterthought warnings hidden in export logs.

### Placement Visualization Contract

- A placed UTP-backed placeable should render its resolved MDL/MDX geometry in
  Map Studio whenever `UTP Appearance -> placeables.2da modelname` resolves.
  The abstract marker is only an explicit unresolved-resource fallback. Mesh
  picking must return the stable authored placement ID so staging and bearing
  edits apply to the GIT instance, not to a room.
- Present animated doors in the same modder-facing **Placeables** authoring
  family because they are spatial interactive props. Do not collapse the game
  format: doors remain UTD-backed objects serialized into the GIT Door List,
  with door animation, transition, and GenericType/model rules preserved.
- Spatial sounds use a recognizable speaker billboard/icon, like a level
  editor sound actor. Do not pretend that a sound has a physical mesh or
  footprint; the icon remains selectable and carries the sound placement ID.
- Walkmesh overlay color is validation state, not decoration. A WOK whose raw
  structure, walkable faces, adjacency, and serialized perimeter loops pass is
  translucent green. Missing/invalid/non-working WOK data is translucent red.
  Unknown or not-yet-validated state must be visibly distinct and must never be
  mislabeled as working merely because a parser accepted it.

## Environment Authoring Rules

- Keep world lighting, placed lights/lightmaps, sky, and sky traffic in a
  Map Studio-only Environment workspace. Do not expose this authoring belt in
  Character Studio or the general model viewer.
- Imported ARE values are the round-trip baseline. Preserve and compare
  `SunAmbientColor`, `SunDiffuseColor`, `DynAmbientColor`, `SunShadows`,
  `ShadowOpacity`, and the game-specific fog fields before adding presets or
  renderer-only controls.
- A viewport light is editor intent, not an exported KOTOR light. Call a room
  lightmapped only after UV2, the room MDL lightmap slot, final resref, texture
  sidecars, staged resource inventory, and manual game proof all agree.
  Malformed active MDL light nodes can crash K2, so dynamic-light export stays
  opt-in and vanilla-compared.
- Use K2 `001ebo1` as the applied-lightmap structural oracle: lightmapped
  surfaces have two texture channels, `has_lightmap=1`, an MDX vertex stream
  with UV0 and UV2, and packaged TPC/TXI lightmap resources. Key assignments by
  stable room+surface identity, not node name. If an unwrap has per-corner UV2
  seams, split/remap export vertices; the current writer consumes one UV2 per
  vertex and cannot infer `face_uvs_lm`.
- Backdrop is a surface role, not a filename heuristic. K2 rooms such as
  `231telSB` and `151harSB` mix sky panels with ordinary or walkable geometry;
  hiding or excluding an entire `*SB` room can remove gameplay geometry and
  pathing. A whole room may be `backdrop_only` only when every render surface
  is backdrop and its WOK is empty/non-walkable or explicitly visual-only.
- Scope empty-WOK/no-AABB exceptions to a vanilla-compared pure backdrop.
  Playable rooms retain the normal AABB, walkable-floor, perimeter, and
  adjacency gates.
- Panorama/HDR/EXR files are authoring sources stored by project-relative path
  plus hash. Convert them offline in linear color, expose exposure/white
  balance/tone mapping/yaw controls, and package power-of-two sRGB TGA/TPC
  faces. Start with the vanilla-style four sides plus top; verify orientation,
  mirroring, and seams with an asymmetrically labeled panorama.
- Preserve imported room animations, emitters, dummy/reference nodes, and
  controller graphs before offering editable sky traffic. Flattening a stock
  room to render surfaces alone silently deletes this behavior.
- Taris ships and Dantooine Brith are room-MDL animation graphs. KOTOR starts
  named `animloop1`, `animloop2`, and `animloop3` slots automatically. The UI
  may present an Unreal-like actor, direction arrow, spline, speed, banking,
  offset, and loop controls, but export must compile deterministic room-local
  MDL/MDX controllers. Do not serialize the visual actor as a GIT placeable.
- Do not apply static MDL header fixes blindly to those animation graphs.
  Vanilla traffic animation-node `+8` points at the owning animation geometry;
  observed type-8 position and type-20 orientation controllers use
  `binary_unknown0` values `16` and `28`, not `0xFFFF`. Preserve compressed
  quaternion columns, Bezier flags/tangents, zero transitions, and sparse
  animation trees with full declared geometry-node counts.
- Treat any linked traffic sound separately as a real UTS/GIT spatial sound
  placement so its resource, radius, and looping rules remain inspectable.

## Holocron Toolset Layout Lessons (2026-07 audit)

- Treat every passable floor-plan opening as a stable room connection hook.
  Connecting two hooks should align the rooms, persist both counterparts, and
  author symmetric VIS intent in one undoable operation.
- Keep hook health visible while editing: connected, unconnected, stale, size-
  incompatible, window/backdrop, or intentional external exit. Do not wait for
  export logs to reveal a disconnected room graph.
- Separate three claims that Holocron's workflow can visually blur: 3D opening
  alignment, KOTOR WOK transition/room-link correctness, and live in-game
  traversal. GhostRigger may report the first as ready while the latter two
  remain blocking proof gates.
- Prefer module-derived room content over a small fixed kit library, while
  retaining authored primitives as the path beyond rearranging vanilla rooms.
- Preserve fast grid/hook/rotation snapping, walkmesh surface painting, a
  draggable player start, marquee selection, and a single build action as the
  baseline usability model; route each through KMAP state and command history.
- Avoid inheriting Holocron's documented weak points: synchronous heavy module
  work, crash-prone repeated opens, and build success without vanilla-structural
  or live-game proof.

### Holocron Placement Lessons

- The primary placement loop is asset → viewport click → immediate selection.
  Manual XYZ entry is a precision fallback, not the front door.
- Keep asset search, sticky placement, walkmesh snap, selected-instance
  transform fields, duplicate/delete/focus, and readiness feedback in one
  compact placement workspace. Do not bury placement below geometry controls.
- Selection must stay synchronized between viewport markers, the outliner, and
  the placement inspector. A newly placed or duplicated instance becomes the
  active selection immediately.
- W/E mean move/rotate for authored GIT markers. KOTOR GIT instances do not
  have arbitrary scale; explain that constraint instead of presenting a fake
  scale tool.
- Position correction must use the combined module-coordinate WOK, preserve
  ramps and room offsets, and choose the vertically nearest face when floors
  overlap in XY. Trigger moves must translate their polygon with the marker.
- Store bearing in KOTOR radians while presenting degrees to users. Rotation
  snapping is a UI gesture; serialized GIT orientation remains engine-native.
- Holocron's align/distribute, fine/coarse nudge, visibility filters, 2D/3D
  shared selection, and drag-from-resource-tree flows remain useful follow-up
  parity work after the direct placement loop is visibly proven in GhostRigger.

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
