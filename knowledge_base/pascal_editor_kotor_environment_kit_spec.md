# Pascal/editor construction model for Ghost Studio

Status: design gate for T2907 Map Studio environment-kit authoring
Research date: 2026-07-21
Pascal source revision: `cb6fadbc288f9daa627e866f31eb86a39b2d93e5`
Upstream: <https://github.com/pascalorg/editor> (MIT)

## Purpose

This document records the behavior and architecture Ghost Studio must preserve
when adapting Pascal's building interaction to KOTOR 1 and 2. It is based on
all three supplied forms of evidence:

- the current Pascal/editor source at the exact revision above;
- `How to Build Your First House in Pascal.txt`;
- `YTDown.com_YouTube_How-to-Build-Your-First-House-in-Pascal_Media_7_PAXkAp2ec_001_1080p.mp4`, inspected at the decisive interaction frames.

The target is not a visual imitation of Pascal. The target is the same
construction grammar and interaction quality, compiled to Odyssey resources
and styled with geometry/material provenance from the user's installed K1/K2
games. No Pascal runtime or KOTOR game geometry is embedded in Ghost Studio.

## Evidence-backed Pascal behavior

### The tutorial's complete user path

The 92.86-second tutorial demonstrates one continuous authoring loop:

1. Open Build and choose Wall from a compact type rail.
2. Click once to start a wall; move to preview length and direction; click to
   commit the segment.
3. The committed endpoint immediately becomes the next segment's start.
4. Close the loop. The editor recognizes a room and creates its floor and
   ceiling automatically.
5. Choose Door, then a thumbnail preset. Hovering a wall shows a hosted ghost;
   clicking inserts the door into that wall.
6. Choose Window, then a thumbnail preset. Reduce the grid step and place
   several wall-hosted windows.
7. Add a second level, then switch between exploded and stacked level views.
8. Choose a roof preset and define its footprint with two clicks.
9. Return to Select, select the roof/segment, and drag a contextual height
   handle while its inspector value updates live.

The visible interaction contract is therefore:

- tool type first, preset second, direct action in the viewport third;
- no modal property form before construction;
- live geometry, dimensions, validity, and snapping before commit;
- a single click continues repetitive construction;
- structural consequences appear automatically after topology changes;
- detailed properties remain editable after placement.

The recorded UI also shows source filters (`All`, `Pascal`, `Mine`, and
`Community`), responsive thumbnail grids, 3D/2D/Split view selection, a compact
active-level control with add-above/add-below actions, and Stack/Exploded view
controls. The open-source `apps/editor/components/build-tab.tsx` intentionally
describes itself as a preset-less replica, so its raw tool tiles do not replace
the richer catalog behavior demonstrated in the supplied tutorial.

### Scene and node ownership

Pascal separates four concerns across packages:

- `core`: schemas, flat node dictionary, hierarchy IDs, scene state,
  persistence, undo/redo, registry contracts, spatial queries, and events;
- `nodes`: built-in node definitions, parametric geometry, renderers, tools,
  handles, and systems;
- `viewer`: rendering and continuous systems such as wall/roof rebuilds and
  level presentation;
- `editor`: tool activation, direct manipulation, transient previews, 2D/3D
  interaction, catalogs, guides, inspectors, and keyboard policy.

The scene is a stable-ID node graph stored as a flat dictionary. Parent/child
relationships are IDs rather than nested geometry blobs. A level owns walls,
slabs, ceilings, roofs, openings/items, and other elements. Derived render
geometry is not the source of truth.

Ghost Studio implication: KMAP must store a small semantic construction graph
with stable IDs and source references. Render meshes and exported MDL/MDX/WOK
files are compiled outputs, never the editable source of truth.

### Tool interaction state machine

Pascal tools are driven by an explicit active interaction state, not by
independent widget flags. A drafting gesture has these phases:

1. **Armed** — a tool and optional preset are selected.
2. **Hover** — the cursor publishes a candidate support/snap result.
3. **Drafting** — the first click anchors a start point or creates a transient
   hosted draft.
4. **Previewing** — pointer movement changes only transient geometry and HUD.
5. **Valid/invalid** — collision, minimum size, host, and snap rules control
   visual validity and commit eligibility.
6. **Commit** — the complete gesture becomes one tracked scene mutation.
7. **Continue or select** — chain tools carry their endpoint; repeat-placement
   tools stay armed; single-placement tools select the new node.
8. **Cancel** — Escape/right-click cancellation clears every transient object,
   guide, and override without changing history.

This is the governing behavior for Ghost Studio's Wall, Doorway, Kit Piece,
Terrain Piece, and later Roof/Ceiling tools.

### Transient preview and undo

Pascal deliberately separates temporary visual state from committed scene
state. Its live-transform/live-node-override stores make pointer motion cheap
and prevent hundreds of undo records. A gesture either:

- never writes the scene until release; or
- pauses history, previews a draft, restores the baseline, resumes history,
  then performs one tracked commit.

Every completed placement or drag is one undo step. Cancel restores the exact
pre-gesture state. Tool unmount also clears transients, preventing stranded
ghost geometry.

Ghost Studio implication: live wall/kit ghosts and snap guides belong in
viewport transient state. They must be alpha-composited over a fresh scene
frame and must never become persistent renderer input until commit.

### Wall drafting and continuation

`packages/nodes/src/wall/tool.tsx` and
`packages/editor/src/components/tools/wall/wall-drafting.ts` implement a
click-to-click chain:

- first click captures a snapped start;
- movement previews actual wall thickness/height plus cursor, angle, and length;
- second click commits one valid segment;
- the endpoint becomes the next segment's start;
- closure to the chain start, a T-intersection with an existing wall, or a
  newly detected closed room terminates the chain;
- zero-length and duplicate segments are rejected;
- a segment landing inside an existing wall splits that wall and migrates its
  hosted attachments in the same history transaction;
- walls on the level below participate in alignment for multi-storey work.

The wall preset seeds thickness, height, and materials; the drawn endpoints
always control footprint and length.

### Snapping model

Pascal combines several distinct mechanisms:

- grid quantization;
- endpoint/corner/midpoint/crossing magnets;
- alignment guides that can remain visible even when another constraint owns
  the final point;
- angle/directional constraints where relevant;
- explicit force/free modifier behavior;
- a small mode-independent connection tolerance (0.05 m in the source) so a
  visibly closed room always becomes topologically closed.

The commit path and preview path use the same resolver. A placement cannot show
one result and commit another. Structural tools may consider the current level
and the level below. Movement raycasts must exclude the moving preview itself,
otherwise the ghost can steal pointer hits from the placement surface.

Ghost Studio implication: terrain and module-kit magnets use compatibility
classes and opposing socket orientations, but the cursor remains the user's
intent. A magnet wins only inside a visible threshold; otherwise the raw
surface/grid result wins. The exact snapped transform displayed by the ghost is
the transform committed on drop/click.

### Room detection and derived surfaces

`packages/core/src/lib/space-detection.ts` does not equate a room with “the last
four points.” It builds a planar wall graph:

- straight wall segments are split/planarized at T-junctions;
- directed half-edges are angle-sorted at vertices;
- face walking extracts closed cycles;
- repeated-vertex walks are split into simple cycles;
- curved walls are sampled into the same graph;
- tiny, invalid, and unbounded/outer cycles are rejected.

The same graph answers both `wallClosesRoom` and automatic slab/ceiling/zone
creation, so the UI cannot claim closure while the surface system disagrees.
When topology changes, auto surfaces are reconciled rather than recreated
blindly:

- exact boundary signatures preserve IDs first;
- overlap, centroid, and area matching preserve IDs through small edits;
- matched surfaces update;
- new faces create new surfaces;
- absorbed auto surfaces are removed;
- orphaned auto surfaces are demoted to manual rather than destroying user
  intent;
- a manual surface suppresses automatic duplication.

Ghost Studio implication: the next room-builder schema must store wall segments
and compute room faces from the wall graph. The current whole-polygon room
primitive remains a compile target and backward-compatible import, not the
long-term editing model.

### Wall junction geometry

Pascal's wall miter system considers endpoint junctions and T-junctions,
calculates plan footprints, and bounds pathological acute-angle miters. Dirty
wall processing includes adjacent walls because one edited endpoint changes
both sides of a joint.

Ghost Studio implication: semantic wall centerlines are edited; the compiler
produces bounded miter/bevel geometry. Kit-backed walls choose typed corner/end
pieces when a collection provides them, then use generated trim/fill geometry
only for small residual gaps.

### Doors and windows

Door and window tools use a common hosted-opening pattern:

- the chosen preset appears as real preview geometry;
- off-wall movement can keep a ghost visible but invalid;
- an actual wall-ray hit establishes the host, wall-local position, and
  orientation;
- placement is clamped inside wall extents;
- collisions with other openings are checked;
- guides show sill/center/equal spacing relationships;
- `R` flips facing while the preview remains live;
- an explicit force modifier may bypass overlap policy;
- commit creates one permanent child and marks its host wall dirty;
- the wall system rebuilds a true CSG cutout from node data;
- repeat and single placement modes are distinct.

Roof-segment wall faces can also host openings. Door and window tool behavior is
parallel rather than two unrelated implementations.

Ghost Studio implication: a KOTOR doorway is both authored geometry and
gameplay/module intent. The construction graph owns the opening and transition
socket; export resolves it to a wall cut/door frame plus the appropriate LYT,
VIS, WOK transition, and UTD/GIT placement when a door object is requested.

### Roofs and levels

The roof tool uses a two-click footprint. It previews an actual translucent
roof volume and outline, snaps to current/below-level wall anchors, and commits
a roof container with one or more editable roof-segment children. Segment
parameters own roof type, pitch, wall height, overhang, and materials; the
drawn footprint owns size and position. Contextual handles and the inspector
edit those values live.

Levels have integer order plus floor-to-floor height. Adding above/below or
inserting shifts level numbers predictably. Viewer presentation has three
separate modes:

- **Stacked**: true authored elevations;
- **Exploded**: true elevations plus a temporary visual gap, smoothly animated;
- **Solo**: only the selected level is colored, while appropriate hidden upper
  levels may remain shadow casters.

The visual exploded offset never changes authored coordinates.

Ghost Studio implication: levels belong in KMAP authoring state and compile to
room Z positions. Exploded/solo are viewport-only. KOTOR interiors usually need
ceiling/upper-room kit selection more than residential pitched roofs, so the
first production scope is levels, floors, ceilings, stairs/elevators, and
vertical transition sockets. Roof authoring is useful for exterior module kits
but must remain engine-budget aware.

### Dirty-node rendering and performance

Pascal does not rebuild the whole scene on each mouse move. Systems process a
dirty-node set and include dependent neighbors. Its wall pipeline:

- immediately rebuilds the actively dragged wall;
- throttles expensive CSG-sensitive hosted changes;
- defers neighboring miter reconciliation to a trailing-edge flush;
- uses progressive rebuild behavior when many walls are dirty;
- derives opening brushes directly from node data;
- keeps transient overrides out of persistent history.

Ghost Studio implication: semantic editing, preview, final room compilation,
lightmap invalidation, WOK regeneration, and module packaging must be separate
stages. Pointer motion may update lightweight preview geometry; MDL/MDX/WOK
compilation must occur on commit/debounce/export, never for every event.

### 2D/3D parity

Pascal treats 2D and 3D as two views of the same node graph. Tool rules,
selection, history, snapping, and commit semantics must agree in both. A feature
is incomplete if it works only on the ground grid or only in one renderer.

Ghost Studio implication: Map Studio starts with the existing 3D viewport, but
construction services must remain GUI-free so a future plan view can call the
same operations. Current tests should compare direct service calls with actual
viewport gestures.

## KOTOR environment-kit adaptation

### What “training on vanilla modules” means

For this feature, training is deterministic local asset analysis, not an opaque
generative model and not redistribution of BioWare/Obsidian data. Ghost Studio
scans the user's configured K1/K2 installations and derives a compact catalog
of:

- module and room provenance;
- indoor/exterior classification;
- room bounds and topology descriptors;
- door-hook/socket positions and orientations;
- terrain surface categories, dimensions, triangle counts, textures, and
  lightmaps;
- dominant floor/wall/ceiling material palettes;
- typed piece roles and compatibility classes;
- generated thumbnails stored as local cache artifacts.

The catalog stores source references and learned metadata only. Geometry and
textures are resolved from the user's game installation on demand.

### Two layers, one workflow

The authoring system needs two cooperating representations:

1. **Pascal-style semantic layer** — walls, closed spaces, openings, levels,
   surfaces, authored transforms, and stable IDs. This gives flexible direct
   construction and reliable undo/persistence.
2. **KOTOR kit realization layer** — module-style collections of vanilla room,
   corner, corridor, doorway, ceiling, trim, cliff, ridge, canyon, and terrain
   pieces with Kotor.NET-style typed magnets. This realizes the semantic design
   in a chosen game's visual language.

The semantic layer is authoritative. Changing the selected collection triggers
deterministic re-realization, not destructive redrawing of the floor plan.

### Collection and piece contract

Each `EnvironmentKitCollection` must provide:

- stable collection ID, K1/K2 game, module/style provenance, and indoor/exterior
  classification;
- representative thumbnail and material palette;
- typed pieces with source model/room/surface references;
- piece dimensions and orientation frame;
- typed magnets and compatibility classes;
- role tags such as straight, inner corner, outer corner, end, doorway,
  transition, floor, ceiling, stair, terrain shelf, cliff, ridge, canyon, or
  dressing;
- validation status and any engine/export restrictions.

Each magnet supplies local position, local orientation, socket kind, and
compatibility class. Snapping aligns compatible socket positions and rotates
the source so socket forward directions oppose. Preview and commit use the same
transform result.

### Interior and exterior realization

Interior collections use wall/door hooks and room topology to learn reusable
straight, turn, junction, doorway, floor, ceiling, and transition roles.
Exterior collections additionally expose cliffs, canyon walls, ridges,
hillocks, far silhouettes, drainage cuts, rocks, foliage, and walkable terrain
surfaces. A single exterior module may therefore feed both Terrain mode and
Building mode:

- Terrain mode shows sculpt-compatible terrain pieces and dressing;
- Building mode shows structural/module pieces and transitions;
- Object mode continues to show UTP/placeable content.

The mode controls browser contents; it does not create separate incompatible
asset stores.

### Odyssey compilation boundary

KOTOR cannot consume Pascal's live semantic graph. Ghost Studio compiles it to
retail formats:

- authored room geometry -> binary MDL/MDX;
- walkable surfaces and transitions -> WOK;
- room placement -> LYT;
- room visibility graph -> VIS;
- doors/placeables/creatures/waypoints/etc. -> GIT plus matching templates;
- packaged module -> RIM/MOD resources with 16-character resref rules.

Moving topology invalidates dependent WOK, LYT/VIS adjacency, and lightmap
state. The editor must show those as derived assets awaiting rebuild, not
silently preserve stale data. Export validation remains the final gate.

## Ghost Studio implementation contract

### Domain ownership

- `core/modules` / Core.Scene: semantic graph, kit metadata, snap math,
  topology, stable IDs, and KMAP serialization contracts.
- Core.Resources: discovery and on-demand resolution of installed-game assets.
- Core.Rendering: transient preview rendering, thumbnails, and resolved model
  presentation.
- GUI.Helpers / viewport interaction: picking, direct manipulation, snap
  feedback, and ghost lifetime.
- Core.Tools: Map Studio orchestration and user workflow.
- Core.IO/Workflow/Validation: MDL/MDX/WOK/LYT/VIS/module compilation,
  packaging, validation, and transactional save/export.

### Required construction graph

The next schema revision must add stable nodes for:

- building and level;
- wall segment (start/end, thickness, height, style/kit binding);
- detected space/room face with auto/manual surface state;
- floor and ceiling surface;
- hosted opening with wall-local distance/elevation/facing and chosen kit piece;
- placed kit piece with source reference and magnet binding;
- terrain piece with surface host and magnet binding.

Legacy closed `FloorPlanRoomPrimitive` records import as one detected room loop
and remain exportable. New edits should no longer require one polygon per room.

### First production interaction slice

1. Choose an interior/exterior collection from a visual catalog.
2. Choose Wall; click to start; move with live wall/piece preview and length;
   click to continue.
3. Snap to the start or a compatible existing endpoint to close/branch.
4. Generate/reconcile room floor and ceiling immediately after commit.
5. Choose Doorway or Window; choose a collection-compatible thumbnail; hover a
   wall; display real hosted ghost plus validity; click to commit.
6. Add/select a level and switch Stack/Exploded/Solo without changing authored
   transforms.
7. Save/reload KMAP with stable IDs and all source/magnet bindings intact.
8. Compile and validate a test module; stage and prove it in Ghost Studio and,
   for final game proof, in KOTOR.

### Acceptance gates

The feature is not complete until all of the following are true:

- wall preview and commit agree exactly;
- chained segments require no repeated tool selection;
- closing a loop creates/reconciles floor and ceiling;
- T-junctions and wall splitting preserve hosted openings;
- one gesture equals one undo record; cancel leaves no ghost or scene mutation;
- door/window preview shows host, facing, collision validity, and collection
  preset before commit;
- terrain and module-kit drag/drop work from the actual dockable content
  browser into the real staged viewport;
- surface/magnet snap feedback is visible and the committed transform matches;
- mode-specific browsers show correct terrain/building/object content;
- K1 and K2 collections retain real module/room/material provenance;
- KMAP save/reload retains semantic graph and kit bindings;
- compiled output produces MDL/MDX/WOK/LYT/VIS/GIT resources accepted by the
  current module export validator;
- user-facing verification is performed in the staged Debug application, not
  only by headless tests.

## Deliberate non-goals

- Copying Pascal's React/Three.js implementation into the Qt/ModernGL codebase.
- Shipping game geometry or textures in the repository.
- Treating dominant textures alone as a complete module kit.
- Rebuilding binary KOTOR resources on every pointer move.
- Allowing a visual snap cue to disagree with the committed transform.
- Claiming a generated room is game-ready before WOK, LYT/VIS, resource, and
  module-package validation succeeds.
