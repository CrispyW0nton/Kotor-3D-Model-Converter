"""Maya-style Map Studio component marking-menu action registry.

Headless registry describing the context-sensitive radial marking menu:
which actions appear for each hovered component type, which targets each
action supports, and what the Shift/Ctrl/Alt modifiers mean.  The radial
widget renders this data; it must not own it.

Vocabulary is based on the clean-room modeling interaction audit
study (action + target + modifier trees re-expressed for KOTOR authoring).
This is a KOTOR-relevant subset, not the full 800-combination import: every
entry states the module resources it will eventually touch so export/proof
staleness stays honest.

This slice is read-only scaffolding: entries with ``implemented=False`` must
render disabled and must not mutate geometry when activated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .map_studio_hover_context import (
    HOVER_COMPONENT_EDGE,
    HOVER_COMPONENT_FACE,
    HOVER_COMPONENT_VERTEX,
    HOVER_COMPONENT_WALKMESH_FACE,
    MapStudioHoverContext,
)

#: Radial menu center entry key.  Selecting it must never run an operation.
DO_NOTHING_KEY = "do_nothing"


@dataclass(frozen=True)
class MapStudioMarkingMenuAction:
    """One radial-menu action available for a hover component type."""

    key: str
    label: str
    hover_context: str
    targets: tuple[str, ...]
    default_target: str
    shift_modifier: str = ""
    ctrl_modifier: str = ""
    alt_modifier: str = ""
    kotor_guardrail: str = ""
    resource_impacts: tuple[str, ...] = ()
    tool_belt_key: str = ""
    implemented: bool = False


@dataclass(frozen=True)
class MapStudioMarkingMenuTree:
    """The full radial tree for one hover context."""

    hover_context: str
    title: str
    actions: tuple[MapStudioMarkingMenuAction, ...] = field(default_factory=tuple)

    @property
    def action_keys(self) -> tuple[str, ...]:
        return tuple(action.key for action in self.actions)


_FACE_ACTIONS: tuple[MapStudioMarkingMenuAction, ...] = (
    MapStudioMarkingMenuAction(
        key="face_extrude",
        label="Extrude",
        hover_context=HOVER_COMPONENT_FACE,
        targets=("Single Face", "Material Region", "Room Island", "All Faces"),
        default_target="Single Face",
        shift_modifier="Point Normal",
        ctrl_modifier="Switch to Move",
        alt_modifier="New Material Region",
        kotor_guardrail="Extrusion must keep visible MDL geometry and generated WOK surface ids in sync.",
        resource_impacts=("MDL", "MDX", "WOK"),
        tool_belt_key="extrude",
        implemented=True,
    ),
    MapStudioMarkingMenuAction(
        key="face_move",
        label="Move",
        hover_context=HOVER_COMPONENT_FACE,
        targets=("Single Face", "Room Island", "All Mesh"),
        default_target="Single Face",
        shift_modifier="Not Aligned",
        alt_modifier="New Material Region",
        kotor_guardrail="Face moves must not open room seams or desync WOK floors under visible geometry.",
        resource_impacts=("MDL", "MDX", "WOK"),
        tool_belt_key="move",
        implemented=True,
    ),
    MapStudioMarkingMenuAction(
        key="face_inset",
        label="Inset",
        hover_context=HOVER_COMPONENT_FACE,
        targets=("Each Face",),
        default_target="Each Face",
        shift_modifier="Square",
        alt_modifier="New Material Region",
        kotor_guardrail="Inset topology must define material, UV, and WOK surface behavior for new faces.",
        resource_impacts=("MDL", "MDX", "WOK"),
        tool_belt_key="bevel",
        implemented=True,
    ),
    MapStudioMarkingMenuAction(
        key="face_bevel",
        label="Bevel",
        hover_context=HOVER_COMPONENT_FACE,
        targets=("Face Corners", "Region Border"),
        default_target="Face Corners",
        shift_modifier="Proportional",
        kotor_guardrail="Bevels must not create sliver triangles that degenerate in WOK output.",
        resource_impacts=("MDL", "MDX", "WOK"),
        tool_belt_key="bevel",
    ),
    MapStudioMarkingMenuAction(
        key="face_delete",
        label="Delete",
        hover_context=HOVER_COMPONENT_FACE,
        targets=("Single Face", "Room Island", "Material Region"),
        default_target="Single Face",
        kotor_guardrail="Deleting faces must flag walkmesh and room-seam validation stale before export.",
        resource_impacts=("MDL", "MDX", "WOK"),
        tool_belt_key="delete_component",
        implemented=True,
    ),
    MapStudioMarkingMenuAction(
        key="face_set_texture",
        label="Set Texture",
        hover_context=HOVER_COMPONENT_FACE,
        targets=("Single Face", "Same Texture Faces"),
        default_target="Single Face",
        shift_modifier="Whole Surface",
        kotor_guardrail="Texture resrefs must exist in the game directory; imported UVs are reused so faces stay mapped.",
        resource_impacts=("MDL", "TPC/TGA refs"),
        implemented=True,
    ),
    MapStudioMarkingMenuAction(
        key="face_split",
        label="Split",
        hover_context=HOVER_COMPONENT_FACE,
        targets=("Single Face",),
        default_target="Single Face",
        kotor_guardrail="Splitting inserts a centroid vertex; keep triangle quality WOK-safe.",
        resource_impacts=("MDL", "MDX", "WOK"),
        implemented=True,
    ),
    MapStudioMarkingMenuAction(
        key="face_inflate",
        label="Inflate",
        hover_context=HOVER_COMPONENT_FACE,
        targets=("Single Face", "Material Region"),
        default_target="Single Face",
        kotor_guardrail="Inflation moves vertices along their normals; re-audit seams and WOK afterward.",
        resource_impacts=("MDL", "MDX", "WOK"),
    ),
    MapStudioMarkingMenuAction(
        key="face_equalize",
        label="Equalize",
        hover_context=HOVER_COMPONENT_FACE,
        targets=("Single Face", "Material Region"),
        default_target="Single Face",
        kotor_guardrail="Equalize redistributes vertices evenly; verify UV stretch and WOK slopes.",
        resource_impacts=("MDL", "MDX", "WOK"),
    ),
    MapStudioMarkingMenuAction(
        key="face_flat",
        label="Flat",
        hover_context=HOVER_COMPONENT_FACE,
        targets=("Single Face", "Material Region"),
        default_target="Single Face",
        kotor_guardrail="Flattening must not fold walkable floors; re-audit WOK slopes after commit.",
        resource_impacts=("MDL", "MDX", "WOK"),
        implemented=True,
    ),
    MapStudioMarkingMenuAction(
        key="face_flip",
        label="Flip",
        hover_context=HOVER_COMPONENT_FACE,
        targets=("Single Face", "Material Region"),
        default_target="Single Face",
        kotor_guardrail="Flipped winding changes lighting and backface culling in the engine; verify in-game.",
        resource_impacts=("MDL", "MDX"),
        implemented=True,
    ),
    MapStudioMarkingMenuAction(
        key="face_material_region",
        label="Material Region",
        hover_context=HOVER_COMPONENT_FACE,
        targets=("Assign", "New Region", "Pick From Face"),
        default_target="Assign",
        shift_modifier="Pick",
        alt_modifier="New Region",
        kotor_guardrail="Material regions map to KOTOR texture/material slots; keep resref-safe names.",
        resource_impacts=("MDL", "TPC/TGA refs"),
        tool_belt_key="paint_material",
    ),
    MapStudioMarkingMenuAction(
        key="face_mask",
        label="Mask",
        hover_context=HOVER_COMPONENT_FACE,
        targets=("Single Face", "Room Island", "Brush Radius"),
        default_target="Single Face",
        alt_modifier="Unmask",
        kotor_guardrail="Masking is editor-only lock state; it must never serialize into module output.",
        resource_impacts=(),
    ),
)

_EDGE_ACTIONS: tuple[MapStudioMarkingMenuAction, ...] = (
    MapStudioMarkingMenuAction(
        key="edge_move",
        label="Move",
        hover_context=HOVER_COMPONENT_EDGE,
        targets=("Single Edge",),
        default_target="Single Edge",
        shift_modifier="Slide",
        alt_modifier="Inflate",
        kotor_guardrail="Edge moves must preserve clean portal/door seams and walkable face boundaries.",
        resource_impacts=("MDL", "MDX", "WOK"),
        tool_belt_key="move",
        implemented=True,
    ),
    MapStudioMarkingMenuAction(
        key="edge_extrude",
        label="Extrude",
        hover_context=HOVER_COMPONENT_EDGE,
        targets=("Single Edge",),
        default_target="Single Edge",
        kotor_guardrail="Edge extrusion appends an unwelded quad; Ctrl+E drags it interactively along the surface plane.",
        resource_impacts=("MDL", "MDX"),
        tool_belt_key="extrude",
        implemented=True,
    ),
    MapStudioMarkingMenuAction(
        key="edge_bevel",
        label="Bevel",
        hover_context=HOVER_COMPONENT_EDGE,
        targets=("Single Edge",),
        default_target="Single Edge",
        shift_modifier="Proportional",
        kotor_guardrail="Edge bevels feed ramp/stair profiles; verify WOK slope walkability after commit.",
        resource_impacts=("MDL", "MDX", "WOK"),
        tool_belt_key="bevel",
        implemented=True,
    ),
    MapStudioMarkingMenuAction(
        key="edge_split",
        label="Split",
        hover_context=HOVER_COMPONENT_EDGE,
        targets=("Single Edge",),
        default_target="Single Edge",
        alt_modifier="Split Edge",
        kotor_guardrail="Edge splits insert vertices; reject degenerate WOK triangles early.",
        resource_impacts=("MDL", "MDX", "WOK"),
        tool_belt_key="cut",
        implemented=True,
    ),
    MapStudioMarkingMenuAction(
        key="edge_collapse",
        label="Collapse",
        hover_context=HOVER_COMPONENT_EDGE,
        targets=("Single Edge",),
        default_target="Single Edge",
        kotor_guardrail="Collapsing merges endpoints and drops degenerate faces; verify seams and WOK afterward.",
        resource_impacts=("MDL", "MDX", "WOK"),
        implemented=True,
    ),
    MapStudioMarkingMenuAction(
        key="edge_delete",
        label="Delete",
        hover_context=HOVER_COMPONENT_EDGE,
        targets=("Single Edge",),
        default_target="Single Edge",
        kotor_guardrail="Deleting an edge removes its adjacent faces; flag walkmesh validation stale.",
        resource_impacts=("MDL", "MDX", "WOK"),
        tool_belt_key="delete_component",
        implemented=True,
    ),
    MapStudioMarkingMenuAction(
        key="edge_bridge",
        label="Bridge",
        hover_context=HOVER_COMPONENT_EDGE,
        targets=("Two Edges", "Two Holes"),
        default_target="Two Edges",
        kotor_guardrail="Bridging is a two-click sequence; generated faces need material and WOK intent.",
        resource_impacts=("MDL", "MDX", "WOK"),
        tool_belt_key="bridge",
    ),
    MapStudioMarkingMenuAction(
        key="edge_slide",
        label="Slide",
        hover_context=HOVER_COMPONENT_EDGE,
        targets=("Single Edge", "Edge Loop"),
        default_target="Single Edge",
        kotor_guardrail="Edge slides must keep UV intent stable for KOTOR texture mapping.",
        resource_impacts=("MDL", "MDX"),
    ),
    MapStudioMarkingMenuAction(
        key="edge_align",
        label="Align",
        hover_context=HOVER_COMPONENT_EDGE,
        targets=("Single Edge", "Edge Loop"),
        default_target="Single Edge",
        kotor_guardrail="Aligning edges must keep portal/door seams straight for VIS and WOK adjacency.",
        resource_impacts=("MDL", "MDX", "WOK"),
    ),
    MapStudioMarkingMenuAction(
        key="edge_close",
        label="Close",
        hover_context=HOVER_COMPONENT_EDGE,
        targets=("Border Loop",),
        default_target="Border Loop",
        kotor_guardrail="Closing a border hole caps it with faces that need material and WOK intent.",
        resource_impacts=("MDL", "MDX", "WOK"),
    ),
    MapStudioMarkingMenuAction(
        key="edge_unweld",
        label="Unweld",
        hover_context=HOVER_COMPONENT_EDGE,
        targets=("Single Edge", "Edge Loop"),
        default_target="Single Edge",
        kotor_guardrail="Unwelding duplicates vertices along the edge; watch UV seams and lighting splits.",
        resource_impacts=("MDL", "MDX"),
    ),
    MapStudioMarkingMenuAction(
        key="edge_crease",
        label="Crease",
        hover_context=HOVER_COMPONENT_EDGE,
        targets=("Single Edge", "Edge Loop"),
        default_target="Single Edge",
        alt_modifier="Uncrease",
        kotor_guardrail="Crease is authoring intent for normal hardness; KOTOR export bakes normals.",
        resource_impacts=("MDL",),
        tool_belt_key="harden_edges",
    ),
)

_VERTEX_ACTIONS: tuple[MapStudioMarkingMenuAction, ...] = (
    MapStudioMarkingMenuAction(
        key="vertex_move",
        label="Move",
        hover_context=HOVER_COMPONENT_VERTEX,
        targets=("Single Vertex",),
        default_target="Single Vertex",
        shift_modifier="Aligned",
        kotor_guardrail="Vertex moves must not create degenerate WOK triangles or cracked room seams.",
        resource_impacts=("MDL", "MDX", "WOK"),
        tool_belt_key="move",
        implemented=True,
    ),
    MapStudioMarkingMenuAction(
        key="vertex_weld",
        label="Weld / Stitch",
        hover_context=HOVER_COMPONENT_VERTEX,
        targets=("To Nearest",),
        default_target="To Nearest",
        kotor_guardrail="Weld changes topology and must repair face indices, WOK references, and undo metadata.",
        resource_impacts=("MDL", "MDX", "WOK"),
        tool_belt_key="weld",
        implemented=True,
    ),
    MapStudioMarkingMenuAction(
        key="vertex_split",
        label="Split",
        hover_context=HOVER_COMPONENT_VERTEX,
        targets=("Single Vertex",),
        default_target="Single Vertex",
        kotor_guardrail="Vertex splits must keep stable subobject ids for KMAP contracts.",
        resource_impacts=("MDL", "MDX", "WOK"),
    ),
    MapStudioMarkingMenuAction(
        key="vertex_extrude",
        label="Extrude",
        hover_context=HOVER_COMPONENT_VERTEX,
        targets=("Single Vertex",),
        default_target="Single Vertex",
        kotor_guardrail="Point extrusion pulls a spike; new faces need material and WOK intent.",
        resource_impacts=("MDL", "MDX", "WOK"),
    ),
    MapStudioMarkingMenuAction(
        key="vertex_slide",
        label="Slide",
        hover_context=HOVER_COMPONENT_VERTEX,
        targets=("Single Vertex",),
        default_target="Single Vertex",
        kotor_guardrail="Vertex slides must keep UV intent stable along the surface.",
        resource_impacts=("MDL", "MDX"),
    ),
    MapStudioMarkingMenuAction(
        key="vertex_delete",
        label="Delete",
        hover_context=HOVER_COMPONENT_VERTEX,
        targets=("Single Vertex",),
        default_target="Single Vertex",
        kotor_guardrail="Deleting a vertex retriangulates its fan; validate winding and WOK output.",
        resource_impacts=("MDL", "MDX", "WOK"),
        tool_belt_key="delete_component",
        implemented=True,
    ),
)

_WALKMESH_ACTIONS: tuple[MapStudioMarkingMenuAction, ...] = (
    MapStudioMarkingMenuAction(
        key="walkmesh_toggle_walkable",
        label="Toggle Walkable",
        hover_context=HOVER_COMPONENT_WALKMESH_FACE,
        targets=("This Face", "Region", "By Slope Threshold"),
        default_target="This Face",
        alt_modifier="Toggle Region",
        kotor_guardrail="Walkable flags define player traversal; mark walkmesh validation and game proof stale.",
        resource_impacts=("WOK",),
        tool_belt_key="paint_wok",
    ),
    MapStudioMarkingMenuAction(
        key="walkmesh_set_surface",
        label="Set Surface",
        hover_context=HOVER_COMPONENT_WALKMESH_FACE,
        targets=("Walkable", "Non-walkable", "Door Transition", "Water"),
        default_target="Walkable",
        kotor_guardrail="Surface materials use KOTOR WOK surface ids; transitions need linked destinations.",
        resource_impacts=("WOK", "GIT/IFO links"),
        tool_belt_key="paint_wok",
    ),
    MapStudioMarkingMenuAction(
        key="walkmesh_split",
        label="Split",
        hover_context=HOVER_COMPONENT_WALKMESH_FACE,
        targets=("By Edge", "By Slope"),
        default_target="By Edge",
        kotor_guardrail="WOK splits must stay seam-consistent with visible floors, ramps, and stairs.",
        resource_impacts=("WOK",),
    ),
    MapStudioMarkingMenuAction(
        key="walkmesh_validate",
        label="Validate",
        hover_context=HOVER_COMPONENT_WALKMESH_FACE,
        targets=("Reachability", "Seam Integrity", "Slope Walkability"),
        default_target="Reachability",
        kotor_guardrail="Validation is read-only and reports against entry point, PTH, and transitions.",
        resource_impacts=(),
        tool_belt_key="validate",
    ),
)

_TREES: dict[str, MapStudioMarkingMenuTree] = {
    HOVER_COMPONENT_FACE: MapStudioMarkingMenuTree(
        hover_context=HOVER_COMPONENT_FACE,
        title="Face",
        actions=_FACE_ACTIONS,
    ),
    HOVER_COMPONENT_EDGE: MapStudioMarkingMenuTree(
        hover_context=HOVER_COMPONENT_EDGE,
        title="Edge",
        actions=_EDGE_ACTIONS,
    ),
    HOVER_COMPONENT_VERTEX: MapStudioMarkingMenuTree(
        hover_context=HOVER_COMPONENT_VERTEX,
        title="Vertex",
        actions=_VERTEX_ACTIONS,
    ),
    HOVER_COMPONENT_WALKMESH_FACE: MapStudioMarkingMenuTree(
        hover_context=HOVER_COMPONENT_WALKMESH_FACE,
        title="Walkmesh",
        actions=_WALKMESH_ACTIONS,
    ),
}


def available_map_studio_marking_menu_trees() -> tuple[MapStudioMarkingMenuTree, ...]:
    """Return every registered hover-context tree in stable order."""

    return tuple(_TREES[key] for key in sorted(_TREES))


def map_studio_marking_menu_tree_for_hover(
    context: MapStudioHoverContext | str | None,
) -> MapStudioMarkingMenuTree | None:
    """Return the radial tree for a hover context (or its component-type key)."""

    if context is None:
        return None
    key = context if isinstance(context, str) else str(getattr(context, "component_type", "") or "")
    return _TREES.get(key)


def map_studio_marking_menu_action(key: str) -> MapStudioMarkingMenuAction | None:
    """Look up one registered action by its stable key."""

    wanted = str(key or "").strip()
    if not wanted:
        return None
    for tree in _TREES.values():
        for action in tree.actions:
            if action.key == wanted:
                return action
    return None
