"""Clean-room Maya-style modeling shelf contract for Map Studio.

The user's Maya 2025 ``Custom`` shelf is the interaction reference: compact,
icon-only, ordered, command-repeatable, and double-clickable for tool options.
This module intentionally records *semantic* Ghost Studio icon keys rather
than Autodesk resource names or artwork.

The shelf is a presentation-independent command map.  Mesh algorithms remain
owned by Scene/Math and the Qt shelf only renders these definitions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MapStudioModelingShelfCommand:
    """One button in the fixed Maya-style modeling shelf."""

    key: str
    label: str
    action_key: str
    description: str
    icon_key: str
    shortcut: str = ""
    options_key: str = ""
    repeatable: bool = True


_COMMANDS: tuple[MapStudioModelingShelfCommand, ...] = (
    MapStudioModelingShelfCommand("reset_transform", "Reset Transformations", "reset_transform", "Reset selected object translation, rotation, and scale channels.", "reset_transform"),
    MapStudioModelingShelfCommand("center_pivot", "Center Pivot", "center_pivot", "Center the selected object's pivot while keeping visible geometry in place.", "center_pivot"),
    MapStudioModelingShelfCommand("zero_pivot", "Zero Pivot", "zero_pivot", "Move the selected object's pivot to its local origin without moving visible geometry.", "zero_pivot"),
    MapStudioModelingShelfCommand("separate", "Separate", "separate", "Separate disconnected polygon shells into independently selectable objects.", "separate"),
    MapStudioModelingShelfCommand("combine", "Combine", "combine", "Combine selected polygon objects into one genuine polygon mesh.", "combine"),
    MapStudioModelingShelfCommand("fill_hole", "Fill Hole", "fill_hole", "Fill the selected closed border loop with triangulated faces.", "fill_hole", "Ctrl+/", "fill_hole"),
    MapStudioModelingShelfCommand("mirror", "Mirror", "mirror", "Mirror geometry across a chosen local axis with optional seam merge.", "mirror", options_key="mirror"),
    MapStudioModelingShelfCommand("bevel", "Bevel", "bevel", "Bevel selected edges with live width, segments, profile, miter, smoothing, and UV controls.", "bevel", "Ctrl+B", "bevel"),
    MapStudioModelingShelfCommand("bridge", "Bridge", "bridge", "Bridge exactly two border edges with baked divisions, taper, twist, smoothing, and preserved material channels.", "bridge", "Ctrl+/", "bridge"),
    MapStudioModelingShelfCommand("extrude", "Extrude", "extrude", "Extrude selected faces or border edges with a live manipulator.", "extrude", "Ctrl+E", "extrude"),
    MapStudioModelingShelfCommand("merge", "Merge", "merge_components", "Merge selected vertices by distance, or exactly two compatible border edges by nearest pairing.", "merge", options_key="merge_components"),
    MapStudioModelingShelfCommand("multi_cut", "Multi-Cut", "multi_cut", "Preview and commit one two-anchor cut across a connected coplanar triangle patch; Enter commits once and Esc cancels.", "multi_cut", "Ctrl+X", "multi_cut"),
    MapStudioModelingShelfCommand("insert_edge_loop", "Insert Edge Loop", "insert_edge_loop", "Insert one loop at the chosen position through a provenance-safe Quad Draw strip.", "edge_loop", options_key="insert_edge_loop"),
    MapStudioModelingShelfCommand("target_weld", "Target Weld", "target_weld", "Pick a source vertex and then the explicit target vertex to collapse onto.", "target_weld", options_key="target_weld"),
    MapStudioModelingShelfCommand("make_hole", "Make Hole", "make_hole", "Cut a selected face using the outline of another selected face.", "make_hole", options_key="make_hole"),
    MapStudioModelingShelfCommand("lattice", "Lattice", "lattice", "Bake a static 2x2x2 trilinear cage deformation into selected geometry.", "lattice", options_key="lattice"),
    MapStudioModelingShelfCommand("wrap", "Wrap", "wrap", "Capture a Make Live driver baseline and bake its inverse-distance vertex deltas into the target.", "wrap", options_key="wrap"),
    MapStudioModelingShelfCommand("shrink_wrap", "ShrinkWrap", "shrink_wrap", "Bake nearest-triangle or nearest-vertex projection onto the active Make Live surface.", "shrink_wrap", options_key="shrink_wrap"),
    MapStudioModelingShelfCommand("reverse_normals", "Reverse", "reverse_normals", "Reverse selected face winding and normals.", "reverse_normals", options_key="reverse_normals"),
    MapStudioModelingShelfCommand("soften_edges", "Soften Edge", "soften_edges", "Average normals across the explicitly selected edges.", "soften_edges", options_key="soften_edges"),
    MapStudioModelingShelfCommand("harden_edges", "Harden Edge", "harden_edges", "Split normals across selected edges for crisp shading.", "harden_edges", options_key="harden_edges"),
    MapStudioModelingShelfCommand("connect_components", "Connect", "connect_components", "Connect exactly two selected vertices by recovering one polygon edge.", "connect", options_key="connect_components"),
    MapStudioModelingShelfCommand("boolean_difference", "Difference A-B", "boolean_a_minus_b", "Subtract closed solid B from closed solid A with preserved materials; open architectural surfaces use planar subtraction.", "boolean_difference", options_key="boolean_a_minus_b"),
    MapStudioModelingShelfCommand("bend", "Bend", "bend_tool", "Bake a bounded circular bend into selected geometry; no live deformer handle is retained.", "bend", options_key="bend_tool"),
    MapStudioModelingShelfCommand("delete_history", "Delete History", "delete_history", "Bake supported construction history while preserving the current result.", "history"),
    MapStudioModelingShelfCommand("duplicate_special_options", "Duplicate Special Options", "duplicate_special_options", "Open repeatable duplicate offset, rotation, scale, and count settings.", "duplicate_special", "Ctrl+Shift+D", "duplicate_special"),
    MapStudioModelingShelfCommand("freeze_transform", "Freeze Transformations", "freeze_transform", "Bake supported transforms into geometry and reset transform channels.", "freeze_transform"),
    MapStudioModelingShelfCommand("select_triangles", "Select Triangle Faces", "select_triangles", "Select visible polygon faces that are true triangle regions.", "select_triangles"),
    MapStudioModelingShelfCommand("select_quads", "Select Quad Faces", "select_quads", "Select coplanar triangle pairs that form quad regions.", "select_quads"),
    MapStudioModelingShelfCommand("contained_faces", "Convert Selection to Contained Faces", "convert_contained_faces", "Convert the current vertex or edge selection to fully contained faces.", "contained_faces"),
    MapStudioModelingShelfCommand("make_live", "Make Live", "make_live", "Use the selected surface as the snapping and retopology target.", "make_live"),
    MapStudioModelingShelfCommand("quad_draw", "Quad Draw", "quad_draw", "Place four projected points on a live reference and auto-weld neighboring retopology quads.", "quad_draw", "Ctrl+Q", "quad_draw"),
)


def map_studio_modeling_shelf_commands() -> tuple[MapStudioModelingShelfCommand, ...]:
    """Return the stable, user-authored Maya shelf order."""

    return _COMMANDS


def map_studio_modeling_shelf_command(key: str) -> MapStudioModelingShelfCommand | None:
    wanted = str(key or "").strip()
    return next((command for command in _COMMANDS if command.key == wanted), None)


__all__ = [
    "MapStudioModelingShelfCommand",
    "map_studio_modeling_shelf_command",
    "map_studio_modeling_shelf_commands",
]
