"""KOTOR-aware modeling tool palette for Map Studio.

This module is deliberately headless.  It describes the manual modeling modes,
snap modes, and tool intent that the Level Editor exposes while the actual mesh
editing services mature.  Keeping these labels and guardrails in core prevents
the GUI from becoming the owner of Map Studio workflow policy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MapStudioComponentMode:
    """One editable component scope in the Map Studio modeling workspace."""

    key: str
    label: str
    description: str
    kotor_guardrail: str


@dataclass(frozen=True)
class MapStudioModelingTool:
    """One visible modeling tool and its KOTOR-specific safety intent."""

    key: str
    label: str
    category: str
    component_modes: tuple[str, ...]
    description: str
    kotor_guardrail: str
    implemented: bool = False


@dataclass(frozen=True)
class MapStudioSnapMode:
    """One snapping mode that Map Studio can expose in the Level Editor."""

    key: str
    label: str
    description: str
    hotkey: str = ""


@dataclass(frozen=True)
class MapStudioEditModeContext:
    """One top-level Map Studio edit mode shown in the Level Editor shell."""

    key: str
    label: str
    editing_target: str
    description: str
    kotor_guardrail: str
    next_action: str


@dataclass(frozen=True)
class MapStudioTerrainBrush:
    """One terrain sculpt brush and its performance/export contract."""

    key: str
    label: str
    operation: str
    description: str
    kotor_guardrail: str
    implemented: bool = False
    continuous_preview: bool = True
    hotkey: str = ""


@dataclass(frozen=True)
class MapStudioViewportPerformancePolicy:
    """Interactive performance expectations for Map Studio tools."""

    target_frame_ms: float
    terrain_brush_budget_ms: float
    input_event_policy: str
    dirty_region_policy: str
    rebuild_policy: str
    validation_policy: str


@dataclass(frozen=True)
class MapStudioToolBeltAction:
    """One action that can appear in the modder-customizable Map Studio belt."""

    key: str
    label: str
    workspace_key: str
    tool_key: str
    description: str
    kotor_guardrail: str
    implemented: bool = False
    hotkey: str = ""


@dataclass(frozen=True)
class MapStudioToolBeltPreset:
    """A named tool-belt arrangement for a common KOTOR map-building task."""

    key: str
    label: str
    description: str
    action_keys: tuple[str, ...]


@dataclass(frozen=True)
class MapStudioToolCommandSearchResult:
    """One searchable Map Studio command entry for command palettes and pickers."""

    key: str
    label: str
    workspace_key: str
    tool_key: str
    description: str
    kotor_guardrail: str
    hotkey: str
    implemented: bool
    score: int
    display_label: str
    match_text: str


_COMPONENT_MODES: tuple[MapStudioComponentMode, ...] = (
    MapStudioComponentMode(
        "object",
        "Object",
        "Select, move, duplicate, rename, and delete rooms, primitives, lights, and KOTOR placements.",
        "Object edits must keep stable KMAP ids and mark staged exports/game proof stale.",
    ),
    MapStudioComponentMode(
        "vertex",
        "Vertex",
        "Move individual room or walkmesh vertices with grid, vertex, and KOTOR doorway snap targets.",
        "Vertex edits must not create degenerate WOK triangles, gaps at room seams, or invalid transition edges.",
    ),
    MapStudioComponentMode(
        "edge",
        "Edge",
        "Select borders and room seams for bridge, bevel, split, flatten, or doorway alignment.",
        "Edge edits should preserve clean portal/door seams and walkable/non-walkable face boundaries.",
    ),
    MapStudioComponentMode(
        "face",
        "Face",
        "Paint material and WOK surface intent, extrude faces, inset floors, and assign terrain/walkmesh behavior.",
        "Face edits must keep visible geometry and generated WOK surface ids in sync.",
    ),
    MapStudioComponentMode(
        "walkmesh",
        "Walkmesh",
        "Inspect and paint WOK faces separately from render geometry before export/game proof.",
        "Walkmesh edits define player traversal and must be validated before the module is called playable.",
    ),
)


_EDIT_MODE_CONTEXTS: tuple[MapStudioEditModeContext, ...] = (
    MapStudioEditModeContext(
        key="object",
        label="Object",
        editing_target="rooms, primitives, lights, placements, and module objects",
        description="Select, move, duplicate, rename, and organize authored map objects.",
        kotor_guardrail="Object edits must preserve stable KMAP ids and mark staged exports/game proof stale.",
        next_action="Select an object, then transform, duplicate, focus, validate, or open its owning tools.",
    ),
    MapStudioEditModeContext(
        key="vertex",
        label="Vertex",
        editing_target="room mesh vertices and WOK vertices",
        description="Edit room and walkmesh vertices with snap, weld, flatten, mirror, and cleanup tools.",
        kotor_guardrail="Vertex edits must avoid degenerate WOK triangles, cracked room seams, and invalid transition edges.",
        next_action="Use snap/weld/flatten on selected vertices, then validate geometry and pathing.",
    ),
    MapStudioEditModeContext(
        key="edge",
        label="Edge",
        editing_target="room seams, doorway borders, corridor joins, and walkmesh edges",
        description="Edit seams, door or corridor borders, bridge edges, bevels, and rectangular cuts.",
        kotor_guardrail="Edge edits must keep doorway/portal seams and walkmesh face boundaries clean.",
        next_action="Bridge, bevel, cut, or align selected edges, then check LYT/VIS/WOK readiness.",
    ),
    MapStudioEditModeContext(
        key="face",
        label="Face",
        editing_target="room faces, material faces, and WOK surface faces",
        description="Edit room faces, material intent, WOK surface intent, triangulation, and cleanup.",
        kotor_guardrail="Face edits must keep visible MDL geometry and generated WOK surface ids in sync.",
        next_action="Assign surface/material intent, fill or triangulate, then validate normals and WOK output.",
    ),
    MapStudioEditModeContext(
        key="walkmesh",
        label="Walkmesh",
        editing_target="WOK walkable, non-walkable, door, water, and transition faces",
        description="Inspect and paint KOTOR walkmesh surfaces and traversal readiness.",
        kotor_guardrail="Walkmesh edits must keep entry points and gameplay anchors on reachable walkable faces.",
        next_action="Paint WOK surface types, validate PTH pathing, then fix any off-walkmesh anchors.",
    ),
    MapStudioEditModeContext(
        key="placement",
        label="Placement",
        editing_target="GIT creatures, placeables, doors, triggers, cameras, sounds, and waypoints",
        description="Place and transform KOTOR runtime resources in the authored module.",
        kotor_guardrail="Placement edits must preserve valid template resrefs and sit on generated walkable WOK when required.",
        next_action="Choose a resource template, place it, then validate GIT/ARE/IFO references.",
    ),
    MapStudioEditModeContext(
        key="terrain",
        label="Terrain",
        editing_target="terrain heightfields, ramps, plateaus, slopes, and walkability",
        description="Sculpt terrain heightfields and terrain-derived room geometry.",
        kotor_guardrail="Terrain edits must stay performant during brush strokes and regenerate WOK before export.",
        next_action="Choose a terrain brush, sculpt, commit, then validate slope and walkmesh output.",
    ),
    MapStudioEditModeContext(
        key="export",
        label="Export",
        editing_target="ARE/GIT/IFO/LYT/VIS/PTH/WOK/MDL/MDX and staged .mod proof",
        description="Validate, stage, install, hand off, warp-test, and record game proof.",
        kotor_guardrail="Export is only a candidate until staged/install-safe packaging and live KOTOR warp proof are recorded.",
        next_action="Resolve blockers, stage or install safely, run the warp test, then record proof.",
    ),
)


_MODE_KEYS = tuple(mode.key for mode in _COMPONENT_MODES)


_MODELING_TOOLS: tuple[MapStudioModelingTool, ...] = (
    MapStudioModelingTool(
        "primitive_room",
        "Create Primitive Room",
        "Primitives",
        ("object",),
        "Seed a KMAP with a flat room, doorway blockout, corridor, or terrain patch.",
        "Generated rooms must produce MDL/MDX, WOK, LYT, VIS, PTH, ARE, GIT, and IFO intent before packaging.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "add_primitive",
        "Add Primitive",
        "Primitives",
        ("object", "face"),
        "Add plane, cube, wall, ramp, stair, cylinder, door frame, arch, or terrain patch primitives to the current authored room.",
        "Primitives that affect traversal must declare whether they create walkmesh faces.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "universal_transform",
        "Universal Manipulator",
        "Transform",
        ("object", "vertex", "edge", "face"),
        "Display a selected component bounding box, interactive transform handles, and exact width/depth/height dimensions for modular-kit scaling.",
        "Transform overlays must use the selected KMAP component bounds and mark MDL/MDX/WOK/export proof stale when committed.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "extrude",
        "Extrude",
        "Component Modeling",
        ("edge", "face"),
        "Pull selected faces or border edges into walls, ledges, corridors, or terrain lips.",
        "Extrusions must be checked for non-manifold geometry and valid WOK face generation.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "bevel_inset",
        "Bevel / Inset",
        "Component Modeling",
        ("vertex", "edge", "face"),
        "Round blockout corners or inset floor plans to create cleaner authored room shapes.",
        "Bevels and insets must not collapse doorway seams or create tiny walkmesh triangles.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "bridge",
        "Bridge",
        "Component Modeling",
        ("edge",),
        "Create faces between compatible border edge loops for corridors, door frames, or terrain seams.",
        "Bridged loops need matching orientation and WOK continuity checks before export.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "snap_vertices",
        "Snap Vertex / Grid",
        "Cleanup",
        ("vertex",),
        "Move one floor-plan vertex to another vertex or snap selected vertices to the active grid without merging topology.",
        "Snapping is not welding; it moves geometry and marks MDL/WOK/LYT/VIS/PTH proof stale while preserving point identity.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "weld_vertices",
        "Weld Vertices",
        "Cleanup",
        ("vertex",),
        "Merge selected vertices or snap a source vertex to a target vertex like Maya-style point snapping.",
        "Welds must update render geometry and generated WOK vertices together.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "flatten_vertices",
        "Flatten / Align Vertices",
        "Cleanup",
        ("vertex", "edge"),
        "Flatten selected floor-plan vertices onto a shared local X or Y line for clean wall and doorway alignment.",
        "Flattening must keep the footprint convex and valid before MDL/WOK generation.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "transform_snap_level",
        "Transform Snap Level",
        "Transform",
        ("vertex", "edge"),
        "While transforming vertices or expanded edge vertices, align them onto one shared X, Y, or Z level.",
        "Level snapping is a geometry edit; validate seams, walkmesh triangles, and doorway alignment before export.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "cleanup_footprint",
        "Cleanup Footprint",
        "Cleanup",
        ("vertex", "edge", "face"),
        "Remove duplicate and collinear floor-plan points before MDL/WOK generation.",
        "Cleanup must preserve at least three valid footprint points and keep the room exportable.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "mirror_footprint",
        "Mirror Footprint",
        "Component Modeling",
        ("object", "vertex", "edge", "face"),
        "Mirror an authored room footprint across its local X or Y centerline for symmetrical rooms and corridors.",
        "Mirroring must preserve a valid convex footprint and keep generated MDL/WOK room output exportable.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "knife_split",
        "Cut / Split",
        "Component Modeling",
        ("edge", "face"),
        "Add room or terrain cuts for door openings, floor details, and walkmesh control loops.",
        "Cuts should preserve triangulation validity and avoid isolated walkmesh slivers.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "wall_opening",
        "Wall Opening",
        "Component Modeling",
        ("edge", "face"),
        "Author a KOTOR-safe doorway or window opening in a generated floor-plan wall.",
        "Wall openings must stay inside one wall panel and leave enough side/lintel geometry for deterministic MDL/WOK export.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "fill_face",
        "Fill Face",
        "Component Modeling",
        ("vertex", "edge", "face", "walkmesh"),
        "Fill a selected vertex loop into a room, terrain, or walkmesh face.",
        "Filled faces must remain planar enough for deterministic triangulation and WOK generation.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "boolean",
        "Boolean",
        "Component Modeling",
        ("object", "face"),
        "Union, subtract, or intersect simple room primitives during blockout.",
        "Boolean results must be cleaned before MDL/WOK export; non-manifold output is not game-ready.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "mirror_x",
        "Mirror X",
        "Component Modeling",
        ("object", "vertex", "edge", "face"),
        "Mirror authored room components across the local X axis for symmetrical blockouts.",
        "Axis-specific mirror output must preserve convex room footprints and valid generated WOK boundaries.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "mirror_y",
        "Mirror Y",
        "Component Modeling",
        ("object", "vertex", "edge", "face"),
        "Mirror authored room components across the local Y axis for symmetrical blockouts.",
        "Axis-specific mirror output must preserve convex room footprints and valid generated WOK boundaries.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "mirror_z",
        "Mirror Z",
        "Component Modeling",
        ("object", "vertex", "edge", "face"),
        "Mirror authored components vertically for ceilings, overhangs, and layered terrain planning.",
        "Vertical mirroring needs explicit MDL/WOK rebuild validation before it can be promoted beyond planning.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "boolean_a_minus_b",
        "Boolean A - B",
        "Component Modeling",
        ("object", "face"),
        "Subtract the second selected authored object/primitive from the first selected object.",
        "Subtraction must be cleaned for manifold geometry before KOTOR MDL/WOK export.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "boolean_b_minus_a",
        "Boolean B - A",
        "Component Modeling",
        ("object", "face"),
        "Subtract the first selected authored object/primitive from the second selected object.",
        "Subtraction must be cleaned for manifold geometry before KOTOR MDL/WOK export.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "insert_edge_loop",
        "Insert Edge Loop",
        "Component Modeling",
        ("edge", "face"),
        "Insert a loop through compatible room or primitive faces for cleaner cuts and bevel support.",
        "Inserted loops must not create sliver WOK faces or broken room seams.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "cut_slice_insert_edges",
        "Cut / Slice + Insert Edges",
        "Component Modeling",
        ("edge", "face"),
        "Cut polygons and insert new edges for doorway, wall-panel, and terrain topology control.",
        "Cuts must preserve triangulation validity and KOTOR surface/material intent.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "fill_hole",
        "Fill Hole",
        "Cleanup",
        ("edge", "face", "walkmesh"),
        "Fill a border or polygon hole in authored room/WOK candidate geometry.",
        "Filled holes need deterministic triangulation and surface assignment before export.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "merge_components",
        "Merge Components",
        "Cleanup",
        ("vertex", "edge"),
        "Merge two selected edges or vertices into one component while repairing references.",
        "Merged components must update visible geometry and WOK topology together.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "lattice",
        "Lattice",
        "Deformation",
        ("object", "vertex", "face"),
        "Apply a baked heightfield control cage to selected terrain for broad terrain shaping.",
        "Current Lattice targets terrain heightfields; arbitrary mesh/object lattice deformation remains planned and must be baked before KOTOR export.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "shrink_wrap",
        "Shrink Wrap",
        "Walkmesh",
        ("vertex", "face", "walkmesh"),
        "Project authored gameplay placements onto the selected terrain heightfield.",
        "Current shrink wrap snaps entry points, waypoints, and placements to terrain; arbitrary mesh/walkmesh shrink-wrap is planned.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "reverse_normals",
        "Reverse Normals",
        "Cleanup",
        ("face", "walkmesh"),
        "Reverse selected face winding for room geometry or WOK candidates.",
        "Reversed normals must be validated so collision and backface culling do not break in-game.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "soften_edges",
        "Soften Edges",
        "Normals",
        ("edge", "face"),
        "Soften selected visual mesh edges for smoother lighting across authored geometry.",
        "Softened edges affect viewport/export normals only; WOK geometry still needs hard traversal validation.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "harden_edges",
        "Harden Edges",
        "Normals",
        ("edge", "face"),
        "Harden selected visual mesh edges for crisp KOTOR hard-surface room silhouettes.",
        "Hardened edges should preserve explicit material and lightmap seams.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "duplicate_special",
        "Duplicate Special",
        "Object Modeling",
        ("object",),
        "Duplicate selected objects with repeatable transform offsets for columns, walls, stairs, or trim kits.",
        "Duplicated outputs must keep stable KMAP ids and export-object ownership.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "curve_tool",
        "Curve Tool",
        "Curves",
        ("object", "vertex"),
        "Author durable KMAP guide curves for paths, rails, terrain ridges, road edges, or later extrusion sweeps.",
        "Curves are construction guides until another command bakes them into KOTOR geometry, WOK, or PTH/path data.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "bend_tool",
        "Bend Tool",
        "Deformation",
        ("object", "vertex", "face"),
        "Bend selected authored terrain heightfields for curved grades, pads, or terrain forms.",
        "Current Bend bakes a terrain heightfield profile; arbitrary mesh/component bending remains planned.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "combine_objects",
        "Combine Objects",
        "Object Modeling",
        ("object",),
        "Combine compatible rectangular floor-plan rooms through the supported room-union workflow; broader primitive/object combine is a future mesh-editing pass.",
        "Combined output must keep stable KMAP ids, clean room/WOK resource boundaries, explicit export-object names, and a readiness note for stale MDL/MDX/WOK/LYT/VIS/PTH outputs.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "separate_objects",
        "Separate Objects",
        "Object Modeling",
        ("object", "face"),
        "Split selected authored composition primitives into independent KMAP room/object boundaries for outside UV/texturing workflows.",
        "Current implementation separates named authored primitives; arbitrary mesh-island separation still needs a later mesh-editing pass.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "triangulate",
        "Triangulate",
        "Cleanup",
        ("face", "walkmesh"),
        "Convert n-gon faces into deterministic triangles before MDL/WOK export.",
        "Triangulation must preserve walkable surface intent and avoid sliver triangles.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "cleanup_normals",
        "Cleanup Normals",
        "Cleanup",
        ("face", "walkmesh"),
        "Orient face winding consistently for predictable culling and walkmesh-facing checks.",
        "Normal cleanup must not hide inverted WOK faces; validation still decides export readiness.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "terrain_sculpt",
        "Terrain Sculpt",
        "Terrain",
        ("vertex", "face", "walkmesh"),
        "Raise, lower, smooth, flatten, and shape terrain heightfield samples.",
        "Terrain slopes and surface ids must be validated against player traversal before export.",
        implemented=True,
    ),
    MapStudioModelingTool(
        "paint_wok",
        "Paint WOK Surface",
        "Walkmesh",
        ("face", "walkmesh"),
        "Assign walkable, non-walkable, door, water, dirt, stone, or other KOTOR WOK surface intent.",
        "Player starts, doors, triggers, and waypoints should sit on valid walkable faces.",
        implemented=True,
    ),
)


_SNAP_MODES: tuple[MapStudioSnapMode, ...] = (
    MapStudioSnapMode("grid", "Grid", "Snap moved resources or components to the current Map Studio grid."),
    MapStudioSnapMode("vertex", "Vertex", "Snap a selected vertex, primitive, or placement to another vertex/handle.", "Hold V"),
    MapStudioSnapMode("level", "Transform Level", "Align selected vertices or edges to one shared X/Y/Z transform level.", "Hold J"),
    MapStudioSnapMode("edge", "Edge", "Snap along an edge or room seam for corridor and doorway alignment."),
    MapStudioSnapMode("face", "Face", "Snap placements or geometry handles to a room or walkmesh face."),
    MapStudioSnapMode("doorhook", "Door / Transition", "Snap rooms to doorway hooks or transition handles for KOTOR module layout."),
)


_TERRAIN_BRUSHES: tuple[MapStudioTerrainBrush, ...] = (
    MapStudioTerrainBrush(
        "raise",
        "Raise",
        "raise",
        "Paint height upward with the selected radius and delta.",
        "Raised terrain must stay under the slope limits that the generated WOK can validate as walkable.",
        implemented=True,
        hotkey="LMB",
    ),
    MapStudioTerrainBrush(
        "lower",
        "Lower",
        "lower",
        "Paint height downward with the selected radius and delta.",
        "Lowered terrain must not strand the module entry point, doors, triggers, or placeables outside walkable WOK.",
        implemented=True,
        hotkey="Shift+LMB",
    ),
    MapStudioTerrainBrush(
        "smooth",
        "Smooth",
        "smooth",
        "Relax neighboring heightfield samples to remove sharp spikes and traversal artifacts.",
        "Smoothing is still export-candidate until slope, WOK surface, and gameplay placement validation passes.",
        implemented=True,
    ),
    MapStudioTerrainBrush(
        "flatten",
        "Flatten",
        "flatten",
        "Level the terrain patch to the chosen sample height for plazas, interiors, and clean encounter spaces.",
        "Flattening should be used around starts, doors, triggers, and combat areas before in-game proof.",
        implemented=True,
    ),
    MapStudioTerrainBrush(
        "erase",
        "Erase / Reset",
        "erase",
        "Brush samples back toward the base terrain height without clearing the whole patch.",
        "Erase/reset is local and dirty-region scoped; validate WOK slopes again before calling the terrain playable.",
        implemented=True,
    ),
    MapStudioTerrainBrush(
        "plateau",
        "Plateau",
        "plateau",
        "Pull the brush area toward the sampled center height for combat pads, doorway landings, and flat ledges.",
        "Plateau painting is local and fast, but door/start pads still need WOK validation before game proof.",
        implemented=True,
    ),
    MapStudioTerrainBrush(
        "ramp",
        "Ramp",
        "ramp",
        "Paint a directional grade between stroke samples for paths, ramps, and sloped approaches.",
        "Ramp output must keep slopes within KOTOR walkmesh limits before export is considered playable.",
        implemented=True,
    ),
    MapStudioTerrainBrush(
        "terrace",
        "Terrace",
        "terrace",
        "Create stepped terrain bands for cliffs, stairs, and layered platforms.",
        "Terrace painting keeps deterministic height bands, but WOK slope/surface review still decides export readiness.",
        implemented=True,
    ),
    MapStudioTerrainBrush(
        "pinch",
        "Pinch",
        "pinch",
        "Tighten ridges or channels by pulling affected samples toward the brush center height.",
        "Pinched terrain can create traversal artifacts; keep walkability overlay visible and validate after sculpting.",
        implemented=True,
    ),
    MapStudioTerrainBrush(
        "erode",
        "Erode",
        "erode",
        "Soften unstable spikes and noisy slopes with a cheap thermal-erosion style relaxation pass.",
        "Erosion is a visual shaping pass; final WOK slope and surface validation still controls game-readiness.",
        implemented=True,
    ),
    MapStudioTerrainBrush(
        "noise",
        "Noise",
        "noise",
        "Add controlled variation for natural ground after the main layout is blocked out.",
        "Noise is deterministic and records post-stroke slope facts so it never silently hides walkability risk.",
        implemented=True,
    ),
)


_VIEWPORT_PERFORMANCE_POLICY = MapStudioViewportPerformancePolicy(
    target_frame_ms=8.33,
    terrain_brush_budget_ms=4.0,
    input_event_policy="Coalesce high-frequency mouse/tablet samples, drop stale stroke frames, and apply only the newest brush state per viewport frame.",
    dirty_region_policy="Update dirty terrain tiles, affected WOK preview triangles, and local bounding boxes only; never rebuild the whole module during pointer movement.",
    rebuild_policy="Defer MDL/WOK/export rebuilds until stroke end, explicit validation, or staged export.",
    validation_policy="Run lightweight slope/walkability feedback during strokes and full ValidationBus/export checks after the edit is committed.",
)


_TOOL_BELT_ACTIONS: tuple[MapStudioToolBeltAction, ...] = (
    MapStudioToolBeltAction(
        "create_room",
        "Room",
        "geometry",
        "primitive_room",
        "Create or focus the room primitive workflow for a new indoor module space.",
        "Rooms must keep stable resrefs and generate matching MDL/MDX/WOK resources.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "corridor",
        "Corridor",
        "geometry",
        "primitive_room",
        "Create a wide hallway starter room for connecting authored module spaces.",
        "Corridors must generate their own clean MDL/WOK resources and remain aligned to doorway/transition seams.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "primitive",
        "Primitive",
        "geometry",
        "add_primitive",
        "Add planes, cubes, walls, ramps, stairs, cylinders, door frames, arches, and blockout parts to the active room.",
        "Traversal-affecting primitives must declare walkmesh intent before export.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "universal_transform",
        "Ctrl+T",
        "geometry",
        "universal_transform",
        "Activate the Universal Manipulator around the selected mesh or component and show exact width/depth/height dimensions.",
        "Use selected component bounds as the source of truth for modular-kit scale; committed edits make runtime exports stale.",
        implemented=True,
        hotkey="Ctrl+T",
    ),
    MapStudioToolBeltAction(
        "plane",
        "Plane",
        "geometry",
        "add_primitive",
        "Add a flat walkable plane/platform primitive to the active authored room.",
        "Planes create WOK faces, so their surface type must remain valid before export.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "cube",
        "Cube",
        "geometry",
        "add_primitive",
        "Add a box primitive for room massing, trim, platforms, or blockout props.",
        "Cubes are visual blockout geometry unless converted into explicit WOK surfaces later.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "wall",
        "Wall",
        "geometry",
        "add_primitive",
        "Add a rectangular wall/slab primitive to the active room.",
        "Walls should align to floor-plan and doorway seams so exported room geometry stays clean.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "ramp",
        "Ramp",
        "geometry",
        "add_primitive",
        "Add a sloped ramp primitive with generated walkmesh faces.",
        "Ramp slope and WOK surface intent must remain valid before export/game proof.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "stairs",
        "Stairs",
        "geometry",
        "add_primitive",
        "Add a visual stair primitive with a continuous walkable WOK proxy.",
        "Stairs use a ramp-style WOK proxy until detailed stair walkmesh authoring is promoted.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "cylinder",
        "Cylinder",
        "geometry",
        "add_primitive",
        "Add a column/pedestal cylinder primitive for room structure or dressing.",
        "Cylinders are visual geometry and must not be mistaken for walkable surfaces.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "door_frame",
        "Door Frame",
        "geometry",
        "add_primitive",
        "Add a doorway frame primitive for KOTOR transition and portal blockout.",
        "Door frames should be aligned with transition triggers, doors, and room visibility boundaries.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "arch",
        "Arch",
        "geometry",
        "add_primitive",
        "Add a curved arch primitive for room entrances, alcoves, and visual portal silhouettes.",
        "Arches are visual geometry; pair them with explicit door/trigger/waypoint transition setup when they mark an exit.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "extrude",
        "Extrude",
        "geometry",
        "extrude",
        "Pull an authored floor-plan edge outward to extend a wall, room, or corridor footprint.",
        "Edge extrusion stays convex in this first pass so generated MDL/WOK remains deterministic.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "bridge",
        "Bridge",
        "geometry",
        "bridge",
        "Create a connector/corridor floor-plan room between compatible room edges.",
        "Bridge creates a separate exportable MDL/WOK room and requires matching elevation, material, WOK surface, and wall settings.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "cut",
        "Cut",
        "geometry",
        "knife_split",
        "Split a floor-plan room into separate exportable KOTOR room pieces, or use rectangular cuts for openings/detail.",
        "Split pieces remain separate exportable rooms and must still pass WOK/visibility validation.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "opening",
        "Opening",
        "geometry",
        "wall_opening",
        "Add or replace a doorway/window opening on a generated floor-plan wall.",
        "Openings must remain KOTOR-safe wall panels and be validated before staged module export.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "opening_marker",
        "Opening Marker",
        "placements",
        "opening_transition_marker",
        "Create a KOTOR door, trigger, or waypoint marker from an authored wall opening.",
        "Opening markers bridge visual doorway geometry to GIT transition data such as LinkedTo, LinkedToModule, and TransitionDestin.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "fill",
        "Fill",
        "geometry",
        "fill_face",
        "Fill a selected component loop into a face for room, terrain, or WOK repair.",
        "Filled faces need cleanup and triangulation before they are considered export-ready.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "vertex_snap",
        "Snap Vtx",
        "geometry",
        "snap_vertices",
        "Move a floor-plan vertex to another room or vertex handle without merging topology.",
        "Snapping is not welding; it must preserve point identity and avoid degenerate footprints or invalid WOK boundaries.",
        implemented=True,
        hotkey="Hold V",
    ),
    MapStudioToolBeltAction(
        "grid_snap",
        "Grid Snap",
        "geometry",
        "snap_vertices",
        "Snap selected floor-plan vertices to the authored Map Studio grid without welding topology.",
        "Grid snapping is a geometry edit; validate seams, WOK, staged export, and game proof after snapping.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "weld",
        "Weld",
        "geometry",
        "weld_vertices",
        "Merge selected floor-plan vertices into one clean footprint point.",
        "Welds update room geometry and generated WOK together.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "flatten",
        "Flatten",
        "geometry",
        "flatten_vertices",
        "Align selected vertices to a shared local X or Y line for walls and door seams.",
        "Flattening is blocked when it would make the room footprint invalid.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "transform_snap_level",
        "Level Snap",
        "geometry",
        "transform_snap_level",
        "Hold J with transform active to align selected vertices or edges onto one shared transform level.",
        "Level snapping should be followed by seam, WOK, and geometry validation before export.",
        implemented=True,
        hotkey="Hold J",
    ),
    MapStudioToolBeltAction(
        "cleanup",
        "Cleanup",
        "geometry",
        "cleanup_footprint",
        "Remove duplicate and collinear footprint points that can create sliver walls or fragile WOK triangles.",
        "Cleanup stays footprint-scoped and must keep the generated MDL/WOK room exportable.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "triangulate",
        "Triangulate",
        "geometry",
        "triangulate",
        "Triangulate selected faces for deterministic MDL/WOK output.",
        "Triangulated faces must preserve material and WOK surface intent.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "normals",
        "Normals",
        "geometry",
        "cleanup_normals",
        "Clean up face winding/normal direction for authored room and WOK candidates.",
        "Normal cleanup is a repair step; validation still needs to catch inverted or non-walkable output.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "triangulate_face",
        "Triangulate Face",
        "geometry",
        "triangulate_face",
        "Triangulate the active floor-plan face deterministically before MDL/WOK validation.",
        "Triangulation is an export-facing cleanup step; WOK and room validation must still run afterward.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "mirror",
        "Mirror",
        "geometry",
        "mirror_footprint",
        "Mirror the active floor-plan footprint across local X or Y for symmetrical blockout.",
        "Mirror remains room-footprint scoped in this first pass and reuses KOTOR floor-plan validation.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "bevel",
        "Bevel",
        "geometry",
        "bevel_inset",
        "Round or chamfer authored room corners during blockout.",
        "Tiny bevels that collapse walkmesh triangles must be rejected before export.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "inset",
        "Inset",
        "geometry",
        "bevel_inset",
        "Inset the selected authored floor plan for inner walls, trim, pits, or raised platforms.",
        "Insets must preserve room boundaries and reject collapsed or self-intersecting WOK candidates.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "boolean",
        "Boolean",
        "geometry",
        "boolean",
        "Union or subtract simple authored room primitives for blockout.",
        "Boolean results stay export-candidate only after cleanup and validation.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "boolean_a_minus_b",
        "A - B",
        "geometry",
        "boolean_a_minus_b",
        "Subtract selected object B from selected object A.",
        "Boolean subtraction needs manifold cleanup before MDL/WOK export.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "boolean_b_minus_a",
        "B - A",
        "geometry",
        "boolean_b_minus_a",
        "Subtract selected object A from selected object B.",
        "Boolean subtraction needs manifold cleanup before MDL/WOK export.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "mirror_x",
        "Mirror X",
        "geometry",
        "mirror_x",
        "Mirror authored components across local X.",
        "Mirrored footprints must remain valid for room and WOK export.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "mirror_y",
        "Mirror Y",
        "geometry",
        "mirror_y",
        "Mirror authored components across local Y.",
        "Mirrored footprints must remain valid for room and WOK export.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "mirror_z",
        "Mirror Z",
        "geometry",
        "mirror_z",
        "Mirror authored components vertically.",
        "Mirror Z reflects terrain heightfields around a horizontal plane; arbitrary mesh mirroring remains planned.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "insert_edge_loop",
        "Edge Loop",
        "geometry",
        "insert_edge_loop",
        "Insert an edge loop through compatible room or primitive faces.",
        "Loop insertion must avoid sliver WOK faces and broken seams.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "cut_slice_insert_edges",
        "Slice",
        "geometry",
        "cut_slice_insert_edges",
        "Cut/slice polygons and insert edges for topology control.",
        "Cuts must preserve KOTOR material and surface intent.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "fill_hole",
        "Fill Hole",
        "geometry",
        "fill_hole",
        "Fill a border or polygon hole.",
        "Filled holes need deterministic triangulation before export.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "merge_components",
        "Merge",
        "geometry",
        "merge_components",
        "Merge two selected edges or vertices into one component.",
        "Merged topology must update render geometry and WOK candidates together.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "lattice",
        "Lattice",
        "geometry",
        "lattice",
        "Apply a baked terrain heightfield control cage to selected authored terrain.",
        "Lattice currently targets terrain heightfields; arbitrary mesh/object cages remain planned because KOTOR has no runtime lattice primitive.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "shrink_wrap",
        "Shrink Wrap",
        "walkmesh",
        "shrink_wrap",
        "Project authored gameplay placements onto terrain.",
        "Current shrink wrap targets entry points, waypoints, and placed objects; arbitrary mesh shrink-wrap remains planned.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "reverse_normals",
        "Reverse",
        "geometry",
        "reverse_normals",
        "Reverse selected face winding.",
        "Reversed normals must pass collision/culling validation.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "soften_edges",
        "Soften",
        "geometry",
        "soften_edges",
        "Soften selected visual edges.",
        "Softened normals are planned for visual export, not WOK traversal.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "harden_edges",
        "Harden",
        "geometry",
        "harden_edges",
        "Harden selected visual edges.",
        "Hardened normals are planned for visual export and lightmap seams.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "duplicate_special",
        "Duplicate Special",
        "geometry",
        "duplicate_special",
        "Duplicate selected objects with repeatable transform offsets.",
        "Duplicate Special must preserve stable KMAP ids and export ownership.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "curve_tool",
        "Curve",
        "geometry",
        "curve_tool",
        "Create an authored KMAP guide curve for paths, rails, terrain shaping, or later sweep tools.",
        "Curve guides are previewable authoring data; they are not KOTOR runtime geometry until baked by another tool.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "bend_tool",
        "Bend",
        "geometry",
        "bend_tool",
        "Bend the selected terrain heightfield with a baked height profile.",
        "Bend currently targets terrain heightfields; arbitrary mesh/component bending remains planned.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "combine",
        "Combine",
        "geometry",
        "combine_objects",
        "Focus object-combine tools for merging compatible rooms/primitives into an exportable object.",
        "Combining must preserve KMAP ids, room resource boundaries, and generated WOK ownership.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "separate",
        "Separate",
        "geometry",
        "separate_objects",
        "Split a selected authored primitive into its own exportable KMAP room/object boundary.",
        "Select an authored composition primitive first; arbitrary raw mesh-face separation is a future mesh-editing slice.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "terrain",
        "Terrain",
        "terrain",
        "terrain_sculpt",
        "Create or focus terrain patches for sculpting outdoor or uneven spaces.",
        "Terrain slopes and WOK surface ids must be validated before gameplay proof.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "terrain_patch",
        "Terrain Patch",
        "terrain",
        "terrain_sculpt",
        "Create a starter terrain heightfield patch for outdoor module blockout.",
        "Terrain patches need slope, surface, and walkmesh validation before they are safe to package.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "sculpt_raise",
        "Raise",
        "terrain",
        "terrain_sculpt",
        "Select the raise terrain brush for continuous heightfield sculpting with optional X/Y symmetry.",
        "Brush strokes must stay responsive and defer heavy rebuilds until the stroke is committed.",
        implemented=True,
        hotkey="LMB",
    ),
    MapStudioToolBeltAction(
        "sculpt_lower",
        "Lower",
        "terrain",
        "terrain_sculpt",
        "Select the lower terrain brush for continuous heightfield sculpting with optional X/Y symmetry.",
        "Brush strokes must keep gameplay starts and placements on reachable WOK after validation.",
        implemented=True,
        hotkey="Shift+LMB",
    ),
    MapStudioToolBeltAction(
        "sculpt_smooth",
        "Smooth",
        "terrain",
        "terrain_sculpt",
        "Select the smooth brush to relax spikes and uneven walkmesh transitions.",
        "Smoothing should reduce slope issues but does not replace WOK validation.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "sculpt_flatten",
        "Flatten",
        "terrain",
        "terrain_sculpt",
        "Select the flatten brush for plazas, combat arenas, and door/start pads.",
        "Flattened areas still need surface-id and gameplay placement validation before export.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "sculpt_erase",
        "Erase",
        "terrain",
        "terrain_sculpt",
        "Select the erase/reset brush to return terrain samples toward the base height.",
        "Erase is local and safe for live sculpting, but the resulting WOK still needs validation before game proof.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "sculpt_plateau",
        "Plateau",
        "terrain",
        "terrain_sculpt",
        "Select the plateau brush for local flat pads, ledges, and doorway landings.",
        "Plateau brush frames stay dirty-region scoped; full WOK/MDL rebuilds wait for commit/export.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "sculpt_ramp",
        "Ramp",
        "terrain",
        "terrain_sculpt",
        "Select the ramp brush for directional path grades and sloped approaches.",
        "Ramp strokes need slope validation before the map can be called playable.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "sculpt_slope",
        "Slope",
        "terrain",
        "terrain_sculpt",
        "Select the slope brush for controlled terrain grades between two stroke points, with optional mirrored grading.",
        "Slope strokes keep dirty-region scope and immediately report whether the generated WOK triangles remain walkable.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "sculpt_terrace",
        "Terrace",
        "terrain",
        "terrain_sculpt",
        "Select the terrace brush for stepped cliffs, tiers, and layered outdoor platforms.",
        "Terrace bands still need WOK slope and traversal validation before game proof.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "sculpt_pinch",
        "Pinch",
        "terrain",
        "terrain_sculpt",
        "Select the pinch brush for sharper ridges, banks, and channels.",
        "Pinch strokes can create steep WOK triangles and must remain validation-visible.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "sculpt_erode",
        "Erode",
        "terrain",
        "terrain_sculpt",
        "Select the erode brush to reduce noisy spikes and unstable slopes.",
        "Erosion is live-preview safe and defers heavy export rebuilds until the stroke is committed.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "sculpt_noise",
        "Noise",
        "terrain",
        "terrain_sculpt",
        "Select the deterministic noise brush for subtle natural terrain variation.",
        "Noise records post-stroke slope facts so traversal issues remain visible before export.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "walkmesh",
        "WOK Paint",
        "walkmesh",
        "paint_wok",
        "Paint walkable, blocked, door, water, and material surface intent.",
        "The player start, transitions, and placeables should sit on valid WOK faces.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "place",
        "Place",
        "placements",
        "",
        "Focus the KOTOR resource placement workspace.",
        "Placed resources keep source resrefs and are validated against GIT/ARE export rules.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "entry_point",
        "Entry Point",
        "placements",
        "entry_point",
        "Focus the module entry point/player start controls that compile into IFO.",
        "The entry point must use a valid area resref and sit on walkable WOK before the module is game-tested.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "placeable",
        "Placeable",
        "placements",
        "placeable",
        "Select placeable placement so a UTP/resref can be searched, positioned, and exported into the GIT.",
        "Placeables should sit on valid walkmesh faces and keep their source template references explicit.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "creature",
        "Creature",
        "placements",
        "creature",
        "Select creature placement so a UTC/resref can be searched, positioned, and exported into the GIT.",
        "Creatures need valid spawn positions and should not be placed outside walkable/navigation space.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "door",
        "Door",
        "placements",
        "door",
        "Select door placement for UTD templates and transition-facing doorway work.",
        "Doors should align with doorway geometry, transition triggers, and valid walkmesh door surfaces.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "waypoint",
        "Waypoint",
        "placements",
        "waypoint",
        "Select waypoint placement for starts, navigation anchors, transition destinations, and scripting markers.",
        "Waypoints used as starts or transitions should sit on reachable walkmesh.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "trigger",
        "Trigger",
        "placements",
        "trigger",
        "Select trigger placement for UTT templates and transition/script volumes.",
        "Triggers should be sized and placed intentionally around doors, cutscenes, and gameplay boundaries.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "encounter",
        "Encounter",
        "placements",
        "encounter",
        "Select encounter placement for UTE templates and encounter-region layout.",
        "Encounters need reachable placement and should be validated against spawn/navigation expectations.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "sound",
        "Sound",
        "placements",
        "sound",
        "Select sound placement for UTS ambient/audio emitters.",
        "Sounds export as gameplay resources; radius and placement should be checked in-game.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "camera",
        "Camera",
        "placements",
        "camera",
        "Select authored camera marker placement for cutscene and preview planning.",
        "Camera markers must be validated separately from gameplay placement and are not visual proof by themselves.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "store",
        "Store",
        "placements",
        "store",
        "Select store/merchant placement for UTM module-level resources.",
        "Stores are module-level GIT resources without viewport markers; template references must resolve at runtime.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "light",
        "Light",
        "lighting",
        "",
        "Add authored room lights and plan later lightmap coverage.",
        "Lighting preview is not game proof; staged in-game checks remain required.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "script",
        "Scripts",
        "scripts",
        "",
        "Assign KOTOR module script hooks and transition metadata.",
        "Script resrefs are stored as references; the tool should not silently create behavior.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "validate",
        "Validate",
        "export",
        "",
        "Run Map Studio validation and show actionable blocking issues.",
        "Only staged install plus recorded warp proof can upgrade a map beyond export candidate.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "stage_module",
        "Stage .mod",
        "export",
        "",
        "Stage the authored KMAP module package, checklist, proof manifest, and launch handoff files.",
        "Staging creates an export candidate for testing; it is not a live KOTOR proof.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "install_module",
        "Install Test",
        "export",
        "",
        "Install the authored module into a selected KOTOR Modules folder with backup protection.",
        "Install only prepares a live test; the module is not game-tested until warp proof is recorded.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "launch_handoff",
        "Launch Handoff",
        "export",
        "",
        "Open the exact warp-test handoff, launch helper, proof manifest, and proof recorder paths.",
        "Launching KOTOR is not proof; run the warp command and capture evidence before marking game-tested.",
        implemented=True,
    ),
    MapStudioToolBeltAction(
        "record_proof",
        "Record Proof",
        "export",
        "",
        "Record screenshot/video-backed KOTOR warp-test proof into the staged proof manifest.",
        "Only real in-game evidence should promote the module from export candidate to game-tested.",
        implemented=True,
    ),
)


_TOOL_BELT_PRESETS: tuple[MapStudioToolBeltPreset, ...] = (
    MapStudioToolBeltPreset(
        "blockout",
        "Blockout",
        "Primitives, snapping, welding, and validation for fast room/corridor layout.",
        (
            "create_room",
            "corridor",
            "plane",
            "wall",
            "cube",
            "cylinder",
            "ramp",
            "stairs",
            "door_frame",
            "arch",
            "primitive",
            "universal_transform",
            "extrude",
            "bridge",
            "cut",
            "opening",
            "opening_marker",
            "fill",
            "vertex_snap",
            "grid_snap",
            "transform_snap_level",
            "weld",
            "flatten",
            "mirror",
            "combine",
            "separate",
            "cleanup",
            "triangulate",
            "triangulate_face",
            "normals",
            "bevel",
            "inset",
            "boolean",
            "boolean_a_minus_b",
            "boolean_b_minus_a",
            "mirror_x",
            "mirror_y",
            "mirror_z",
            "insert_edge_loop",
            "cut_slice_insert_edges",
            "fill_hole",
            "merge_components",
            "shrink_wrap",
            "reverse_normals",
            "soften_edges",
            "harden_edges",
            "duplicate_special",
            "validate",
        ),
    ),
    MapStudioToolBeltPreset(
        "component",
        "Component Modeling",
        "Vertex/edge/face cleanup tools for refining authored module geometry.",
        (
            "plane",
            "wall",
            "cube",
            "door_frame",
            "arch",
            "universal_transform",
            "extrude",
            "bridge",
            "cut",
            "cut_slice_insert_edges",
            "insert_edge_loop",
            "opening",
            "opening_marker",
            "fill",
            "fill_hole",
            "vertex_snap",
            "grid_snap",
            "transform_snap_level",
            "weld",
            "merge_components",
            "flatten",
            "mirror",
            "mirror_x",
            "mirror_y",
            "mirror_z",
            "combine",
            "separate",
            "cleanup",
            "triangulate",
            "triangulate_face",
            "normals",
            "reverse_normals",
            "soften_edges",
            "harden_edges",
            "bevel",
            "inset",
            "boolean",
            "boolean_a_minus_b",
            "boolean_b_minus_a",
            "lattice",
            "shrink_wrap",
            "duplicate_special",
            "curve_tool",
            "bend_tool",
            "walkmesh",
            "validate",
        ),
    ),
    MapStudioToolBeltPreset(
        "terrain",
        "Terrain",
        "Terrain patch creation, continuous sculpt brushes, WOK painting, placement, lighting, and validation.",
        (
            "terrain_patch",
            "terrain",
            "sculpt_raise",
            "sculpt_lower",
            "sculpt_smooth",
            "sculpt_flatten",
            "sculpt_erase",
            "sculpt_plateau",
            "sculpt_ramp",
            "sculpt_slope",
            "sculpt_terrace",
            "sculpt_pinch",
            "sculpt_erode",
            "sculpt_noise",
            "walkmesh",
            "entry_point",
            "place",
            "placeable",
            "creature",
            "waypoint",
            "light",
            "validate",
        ),
    ),
    MapStudioToolBeltPreset(
        "gameplay",
        "Gameplay Layout",
        "Placement, transition/script, lighting, walkmesh, and validation for making the map usable.",
        (
            "place",
            "entry_point",
            "placeable",
            "creature",
            "door",
            "opening_marker",
            "waypoint",
            "trigger",
            "encounter",
            "sound",
            "camera",
            "store",
            "script",
            "light",
            "walkmesh",
            "validate",
        ),
    ),
    MapStudioToolBeltPreset(
        "export",
        "Export Proof",
        "Final validation-focused belt for staged install and KOTOR warp proof workflow.",
        (
            "validate",
            "stage_module",
            "install_module",
            "launch_handoff",
            "record_proof",
            "walkmesh",
            "entry_point",
            "place",
            "placeable",
            "door",
            "opening_marker",
            "trigger",
            "waypoint",
            "script",
            "light",
        ),
    ),
    MapStudioToolBeltPreset(
        "custom",
        "Custom",
        "Session-customized belt chosen by the modder.",
        (),
    ),
)


def _action_by_key() -> dict[str, MapStudioToolBeltAction]:
    return {action.key: action for action in _TOOL_BELT_ACTIONS}


def available_map_studio_component_modes() -> tuple[MapStudioComponentMode, ...]:
    """Return component scopes exposed by the Map Studio modeling workspace."""

    return _COMPONENT_MODES


def available_map_studio_edit_mode_contexts() -> tuple[MapStudioEditModeContext, ...]:
    """Return top-level Map Studio edit modes with KOTOR-specific UX context."""

    return _EDIT_MODE_CONTEXTS


def map_studio_edit_mode_context(mode_label: str = "Object") -> MapStudioEditModeContext:
    """Return context for a visible toolbar edit-mode label or key."""

    wanted = str(mode_label or "Object").strip().lower().replace(" ", "_")
    for context in _EDIT_MODE_CONTEXTS:
        if wanted in {context.key.lower(), context.label.lower().replace(" ", "_")}:
            return context
    return _EDIT_MODE_CONTEXTS[0]


def available_map_studio_modeling_tools() -> tuple[MapStudioModelingTool, ...]:
    """Return visible modeling tools and their capability-honest status."""

    return _MODELING_TOOLS


def available_map_studio_snap_modes() -> tuple[MapStudioSnapMode, ...]:
    """Return snap modes that should be visible in Map Studio controls."""

    return _SNAP_MODES


def available_map_studio_terrain_brushes() -> tuple[MapStudioTerrainBrush, ...]:
    """Return terrain sculpt brushes and their capability-honest status."""

    return _TERRAIN_BRUSHES


def map_studio_viewport_performance_policy() -> MapStudioViewportPerformancePolicy:
    """Return the no-lag interaction contract for Map Studio viewport tools."""

    return _VIEWPORT_PERFORMANCE_POLICY


def available_map_studio_tool_belt_actions() -> tuple[MapStudioToolBeltAction, ...]:
    """Return actions that can be placed in the Map Studio modeling belt."""

    return _TOOL_BELT_ACTIONS


def available_map_studio_tool_belt_presets() -> tuple[MapStudioToolBeltPreset, ...]:
    """Return built-in Maya-like tool-belt presets for common modder workflows."""

    return _TOOL_BELT_PRESETS


def map_studio_tool_belt_actions_for_preset(
    preset_key: str = "blockout",
    *,
    custom_action_keys: tuple[str, ...] | list[str] = (),
) -> tuple[MapStudioToolBeltAction, ...]:
    """Resolve a preset or custom action list into tool-belt actions."""

    action_map = _action_by_key()
    preset = next((item for item in _TOOL_BELT_PRESETS if item.key == str(preset_key or "blockout")), None)
    if preset is None:
        preset = _TOOL_BELT_PRESETS[0]
    keys = tuple(custom_action_keys or ()) if preset.key == "custom" else preset.action_keys
    actions: list[MapStudioToolBeltAction] = []
    for key in keys:
        action = action_map.get(str(key))
        if action is not None and action not in actions:
            actions.append(action)
    return tuple(actions)


def map_studio_tool_command_search(
    query: str = "",
    *,
    limit: int = 50,
    include_planned: bool = False,
) -> tuple[MapStudioToolCommandSearchResult, ...]:
    """Return a deterministic searchable command index for Map Studio tools."""

    raw_query = str(query or "").strip().lower()
    tokens = tuple(token for token in raw_query.replace("_", " ").split() if token)
    results: list[MapStudioToolCommandSearchResult] = []
    for action in _TOOL_BELT_ACTIONS:
        if not include_planned and not action.implemented:
            continue
        workspace = str(action.workspace_key or "map").replace("_", " ")
        searchable = " ".join(
            (
                action.key,
                action.label,
                workspace,
                action.tool_key,
                action.description,
                action.kotor_guardrail,
                action.hotkey,
            )
        ).lower()
        if tokens and not all(token in searchable for token in tokens):
            continue
        score = 1
        label_lower = action.label.lower()
        key_lower = action.key.lower()
        if raw_query:
            if raw_query == key_lower or raw_query == label_lower:
                score += 100
            if key_lower.startswith(raw_query) or label_lower.startswith(raw_query):
                score += 50
            if raw_query in key_lower or raw_query in label_lower:
                score += 25
            for token in tokens:
                if key_lower.startswith(token) or label_lower.startswith(token):
                    score += 10
                elif token in searchable:
                    score += 3
        if action.implemented:
            score += 5
        display_label = f"{action.label} [{workspace}]"
        if action.hotkey:
            display_label = f"{display_label} - {action.hotkey}"
        results.append(
            MapStudioToolCommandSearchResult(
                key=action.key,
                label=action.label,
                workspace_key=action.workspace_key,
                tool_key=action.tool_key,
                description=action.description,
                kotor_guardrail=action.kotor_guardrail,
                hotkey=action.hotkey,
                implemented=action.implemented,
                score=score,
                display_label=display_label,
                match_text=searchable,
            )
        )
    ordered = sorted(results, key=lambda item: (-item.score, item.label.lower(), item.key))
    if limit <= 0:
        return tuple(ordered)
    return tuple(ordered[: int(limit)])


def map_studio_modeling_tool_summary(
    *,
    mode_key: str = "object",
    tool_key: str = "",
    snap_key: str = "grid",
) -> str:
    """Return a concise modder-facing status line for the selected modeling tool."""

    mode = next((item for item in _COMPONENT_MODES if item.key == mode_key), _COMPONENT_MODES[0])
    tool = next((item for item in _MODELING_TOOLS if item.key == tool_key), None)
    snap = next((item for item in _SNAP_MODES if item.key == snap_key), _SNAP_MODES[0])
    if tool is None:
        return f"{mode.label} mode. Snap: {snap.label}. {mode.kotor_guardrail}"
    state = "usable now" if tool.implemented else "planned; validation-first"
    return (
        f"{mode.label} mode / {tool.label} ({state}). Snap: {snap.label}. "
        f"{tool.kotor_guardrail}"
    )
