"""Map Studio tool-belt action routing.

This module keeps Map Studio shelf/tool-belt action semantics out of the Qt
window.  The UI can arrange buttons and collect selection context, but the
meaning of an action key lives here so menus, hotkeys, context menus, command
search, and the customizable tool belt can share one policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .map_studio_modeling_tools import MapStudioToolBeltAction, available_map_studio_tool_belt_actions


MAP_STUDIO_TOOL_ACTION_STALE_OUTPUTS: tuple[str, ...] = ("MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod")
MAP_STUDIO_TOOL_ACTION_READINESS_IMPACT = (
    "Map Studio validation, export, install handoff, and game proof are stale."
)


@dataclass(frozen=True)
class MapStudioToolActionContext:
    """Current selection/context facts needed to resolve one tool-belt action."""

    module_root: str = ""
    room_resref: str = ""
    first_room_resref: str = ""
    second_room_resref: str = ""
    result_room_resref: str = ""
    primitive_name: str = ""
    primitive_kind: str = ""
    placement_kind: str = ""
    placement_template_resref: str = ""
    placement_tag: str = ""
    placement_position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    placement_bearing: float = 0.0
    entry_area_resref: str = ""
    entry_position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    entry_facing: float = 0.0
    wall_opening_name: str = ""
    wall_opening_edge_index: int = 0
    wall_opening_center_fraction: float = 0.5
    wall_opening_width: float = 1.5
    wall_opening_height: float = 2.1
    wall_opening_bottom: float = 0.0
    opening_name: str = ""
    opening_marker_kind: str = "door"
    opening_marker_template_resref: str = ""
    opening_marker_tag: str = ""
    opening_marker_linked_to: str = ""
    opening_marker_linked_to_module: str = ""
    opening_marker_transition_destination: int = 0
    opening_marker_edge_index: int | None = None
    point_index: int | None = None
    point_indices: tuple[int, ...] = ()
    target_point_index: int | None = None
    target_room_resref: str = ""
    first_edge_index: int | None = None
    second_edge_index: int | None = None
    axis: str = "x"
    positive_z: bool = True
    operation_distance: float = 0.25
    operation_edge_index: int = 0
    terrain_row_index: int = 0
    terrain_column_index: int = 0
    terrain_points: tuple[tuple[int, int, float], ...] = ()
    terrain_delta: float = 0.1
    terrain_radius: int = 0
    terrain_height: float = 0.0
    terrain_iterations: int = 1
    terrain_strength: float = 0.5
    terrain_preserve_boundary: bool = True
    terrain_symmetry_axis: str = ""
    cut_center: tuple[float, float] = (0.0, 0.0)
    cut_size: tuple[float, float] = (1.0, 1.0)
    duplicate_count: int = 1
    duplicate_translation_offset: tuple[float, float, float] = (1.0, 0.0, 0.0)
    duplicate_rotation_offset_degrees_z: float = 0.0
    duplicate_scale_multiplier: tuple[float, float, float] = (1.0, 1.0, 1.0)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MapStudioToolActionRoute:
    """Resolved behavior for one Map Studio action key."""

    action_key: str
    label: str
    workspace_key: str
    tool_key: str
    enabled: bool
    disabled_reason: str = ""
    focus_component_mode: str = ""
    focus_snap_mode: str = ""
    terrain_brush: str = ""
    primitive_kind: str = ""
    placement_kind: str = ""
    command_method: str = ""
    command_kwargs: dict[str, Any] = field(default_factory=dict)
    mutates_kmap: bool = False
    stale_outputs: tuple[str, ...] = ()
    readiness_impact: str = ""
    status_message: str = ""
    authoring_context: str = ""


_PRIMITIVE_ACTIONS: dict[str, str] = {
    "primitive": "cube",
    "plane": "plane",
    "cube": "cube",
    "wall": "wall",
    "ramp": "ramp",
    "stairs": "stairs",
    "cylinder": "cylinder",
    "door_frame": "door_frame",
    "arch": "arch",
}

_ROOM_PRESET_ACTIONS: dict[str, tuple[str, str]] = {
    "create_room": ("rectangular_dev_room", "grdev01"),
    "corridor": ("wide_hall", "grhall"),
    "terrain_patch": ("terrain_heightfield", "grterrain"),
}

_PLACEMENT_ACTIONS: dict[str, str] = {
    "place": "placeable",
    "placeable": "placeable",
    "creature": "creature",
    "door": "door",
    "waypoint": "waypoint",
    "trigger": "trigger",
    "encounter": "encounter",
    "sound": "sound",
    "camera": "camera",
    "store": "store",
}

_PLACEMENT_DEFAULT_TEMPLATES: dict[str, str] = {
    "placeable": "plc_bench",
    "creature": "c_drdmkone",
    "door": "door_t01",
    "waypoint": "wp_mapstudio",
    "trigger": "trg_mapstudio",
    "encounter": "enc_mapstudio",
    "sound": "snd_mapstudio",
    "store": "store_map",
    "camera": "",
}

_TERRAIN_BRUSH_ACTIONS: dict[str, str] = {
    "sculpt_raise": "raise",
    "sculpt_lower": "lower",
    "sculpt_smooth": "smooth",
    "sculpt_flatten": "flatten",
    "sculpt_erase": "erase",
    "sculpt_plateau": "plateau",
    "sculpt_ramp": "ramp",
    "sculpt_slope": "slope",
    "sculpt_terrace": "terrace",
    "sculpt_pinch": "pinch",
    "sculpt_erode": "erode",
    "sculpt_noise": "noise",
}

_VERTEX_FOCUS: dict[str, tuple[str, str, str]] = {
    "vertex_snap": ("vertex", "snap_vertices", "vertex"),
    "weld": ("vertex", "weld_vertices", "vertex"),
    "merge_components": ("vertex", "weld_vertices", "vertex"),
    "flatten": ("vertex", "flatten_vertices", "grid"),
    "transform_snap_level": ("vertex", "transform_snap_level", "level"),
    "mirror": ("vertex", "mirror_footprint", "grid"),
    "mirror_x": ("vertex", "mirror_x", "grid"),
    "mirror_y": ("vertex", "mirror_y", "grid"),
    "mirror_z": ("vertex", "mirror_z", "grid"),
    "cleanup": ("vertex", "cleanup_footprint", "grid"),
}


def _action_by_key() -> dict[str, MapStudioToolBeltAction]:
    return {item.key: item for item in available_map_studio_tool_belt_actions()}


def _clean_axis(axis: str) -> str:
    value = str(axis or "x").strip().lower()
    return value if value in {"x", "y", "z"} else "x"


def _clean_indices(values: tuple[int, ...] | list[int] | Any) -> tuple[int, ...]:
    return tuple(int(index) for index in tuple(values or ()))


def _placement_template_for_action(ctx: MapStudioToolActionContext, placement_kind: str, requested_kind: str) -> str:
    selected_kind = str(ctx.placement_kind or "").strip().lower()
    if (not selected_kind or selected_kind == placement_kind or requested_kind == "place") and str(ctx.placement_template_resref or "").strip():
        return str(ctx.placement_template_resref or "").strip()
    return _PLACEMENT_DEFAULT_TEMPLATES.get(placement_kind, "")


def _placement_tag_for_action(ctx: MapStudioToolActionContext, placement_kind: str) -> str:
    tag = str(ctx.placement_tag or "").strip()
    if tag:
        return tag
    return f"map_{placement_kind}"[:32]


def _disabled(action: MapStudioToolBeltAction | None, action_key: str, reason: str) -> MapStudioToolActionRoute:
    return MapStudioToolActionRoute(
        action_key=action_key,
        label=str(getattr(action, "label", action_key) or action_key),
        workspace_key=str(getattr(action, "workspace_key", "") or ""),
        tool_key=str(getattr(action, "tool_key", "") or ""),
        enabled=False,
        disabled_reason=reason,
        status_message=reason,
    )


def _route(
    action: MapStudioToolBeltAction,
    *,
    enabled: bool = True,
    disabled_reason: str = "",
    focus_component_mode: str = "",
    focus_snap_mode: str = "",
    terrain_brush: str = "",
    primitive_kind: str = "",
    placement_kind: str = "",
    command_method: str = "",
    command_kwargs: dict[str, Any] | None = None,
    mutates_kmap: bool = False,
    status_message: str = "",
    authoring_context: str = "",
) -> MapStudioToolActionRoute:
    return MapStudioToolActionRoute(
        action_key=action.key,
        label=action.label,
        workspace_key=action.workspace_key,
        tool_key=action.tool_key,
        enabled=enabled,
        disabled_reason=disabled_reason,
        focus_component_mode=focus_component_mode,
        focus_snap_mode=focus_snap_mode,
        terrain_brush=terrain_brush,
        primitive_kind=primitive_kind,
        placement_kind=placement_kind,
        command_method=command_method if enabled else "",
        command_kwargs=dict(command_kwargs or {}) if enabled else {},
        mutates_kmap=bool(mutates_kmap and enabled),
        stale_outputs=MAP_STUDIO_TOOL_ACTION_STALE_OUTPUTS if mutates_kmap and enabled else (),
        readiness_impact=MAP_STUDIO_TOOL_ACTION_READINESS_IMPACT if mutates_kmap and enabled else "",
        status_message=status_message or action.description,
        authoring_context=authoring_context,
    )


def resolve_map_studio_tool_belt_action(
    action_key: str,
    context: MapStudioToolActionContext | None = None,
) -> MapStudioToolActionRoute:
    """Resolve a Map Studio tool-belt action into command/focus semantics."""

    key = str(action_key or "").strip()
    actions = _action_by_key()
    action = actions.get(key)
    if action is None:
        return _disabled(None, key, f"Unknown Map Studio tool-belt action '{key}'.")
    ctx = context or MapStudioToolActionContext()
    if not bool(action.implemented):
        return _disabled(action, key, f"{action.label} is planned and not implemented for command execution yet.")

    if key == "terrain":
        return _route(
            action,
            focus_component_mode="terrain",
            focus_snap_mode="surface",
            command_method="authored_terrain_status",
            mutates_kmap=False,
            status_message="Terrain status refreshed; choose a brush or create a terrain patch before sculpting.",
            authoring_context=(
                "Terrain: query authored terrain room choices, walkability overlay counts, slope risk, and next actions "
                "without mutating KMAP state. Brush actions commit dirty-region heightfield edits."
            ),
        )

    if key == "walkmesh":
        return _route(
            action,
            focus_component_mode="walkmesh",
            focus_snap_mode="face",
            command_method="authored_walkmesh_status",
            mutates_kmap=False,
            status_message="Walkmesh status refreshed; paint WOK surfaces or fix traversal blockers before export.",
            authoring_context=(
                "Walkmesh: query generated WOK walkability, disconnected islands, invalid/degenerate faces, "
                "and gameplay-anchor readiness without mutating KMAP state."
            ),
        )

    preset = _ROOM_PRESET_ACTIONS.get(key)
    if preset is not None:
        preset_id, fallback_root = preset
        module_root = str(ctx.module_root or fallback_root).strip() or fallback_root
        return _route(
            action,
            focus_component_mode="object" if key != "terrain_patch" else "terrain",
            focus_snap_mode="grid" if key != "terrain_patch" else "surface",
            command_method="create_authored_room_preset_module",
            command_kwargs={"preset_id": preset_id, "module_root": module_root},
            mutates_kmap=True,
            authoring_context=(
                f"{action.label}: create a KMAP-authored module from the {preset_id} preset; "
                "room geometry, placements, walkmesh intent, validation, export, and game proof become stale."
            ),
        )

    if key in _PRIMITIVE_ACTIONS:
        primitive_kind = ctx.primitive_kind or _PRIMITIVE_ACTIONS[key]
        return _route(
            action,
            primitive_kind=primitive_kind,
            command_method="add_authored_room_primitive",
            command_kwargs={
                "primitive_kind": primitive_kind,
                "room_resref": ctx.room_resref,
                "primitive_name": ctx.primitive_name,
            },
            mutates_kmap=True,
            authoring_context=(
                f"Primitive: add a {primitive_kind} to an editable authored room; "
                "KMAP state, validation, export, and game proof become stale."
            ),
        )

    terrain_brush = _TERRAIN_BRUSH_ACTIONS.get(key)
    if terrain_brush:
        if not str(ctx.room_resref or "").strip():
            return _route(
                action,
                focus_component_mode="terrain",
                terrain_brush=terrain_brush,
                enabled=False,
                disabled_reason="Terrain brush needs a selected authored terrain room.",
            )
        terrain_points = tuple(ctx.terrain_points or ((int(ctx.terrain_row_index), int(ctx.terrain_column_index), 1.0),))
        kwargs: dict[str, Any] = {
            "operation": f"brush_stroke:{terrain_brush}",
            "room_resref": str(ctx.room_resref or "").strip(),
            "row_index": int(ctx.terrain_row_index),
            "column_index": int(ctx.terrain_column_index),
            "points": terrain_points,
            "delta": float(ctx.terrain_delta),
            "radius": int(ctx.terrain_radius),
            "height": float(ctx.terrain_height),
            "iterations": int(ctx.terrain_iterations),
            "strength": float(ctx.terrain_strength),
            "preserve_boundary": bool(ctx.terrain_preserve_boundary),
        }
        if str(ctx.terrain_symmetry_axis or "").strip():
            kwargs["symmetry_axis"] = str(ctx.terrain_symmetry_axis or "").strip().lower()
        return _route(
            action,
            focus_component_mode="terrain",
            focus_snap_mode="surface",
            terrain_brush=terrain_brush,
            command_method="apply_authored_terrain_operation",
            command_kwargs=kwargs,
            mutates_kmap=True,
            status_message=(
                f"Applied terrain brush {terrain_brush}; dirty terrain samples changed and "
                "MDL/WOK/export/game proof are stale."
            ),
            authoring_context=(
                f"Terrain brush: {terrain_brush}. Commit one dirty-region scoped heightfield stroke "
                "to authored KMAP terrain; live frames remain viewport-coalesced, while full MDL/WOK "
                "rebuild waits for validation or staged export."
            ),
        )

    if key == "universal_transform":
        if not ctx.primitive_name:
            return _route(
                action,
                focus_component_mode="object",
                focus_snap_mode="grid",
                enabled=False,
                disabled_reason="Universal Manipulator needs a selected authored room primitive.",
            )
        return _route(
            action,
            focus_component_mode="object",
            focus_snap_mode="grid",
            command_method="map_studio_universal_transform_overlay",
            command_kwargs={
                "room_resref": ctx.room_resref,
                "primitive_name": ctx.primitive_name,
            },
            mutates_kmap=False,
            authoring_context=(
                "Universal Manipulator: query exact KMAP-world selected primitive bounds, center, "
                "width/depth/height, transform handles, dimension labels, and export-stale impact before committing any edit."
            ),
        )

    if key == "shrink_wrap":
        return _route(
            action,
            focus_component_mode="walkmesh",
            focus_snap_mode="surface",
            command_method="apply_authored_terrain_operation",
            command_kwargs={
                "operation": "shrink_wrap",
                "room_resref": ctx.room_resref,
            },
            mutates_kmap=True,
            authoring_context=(
                "Shrink Wrap: project authored entry points, waypoints, and gameplay placements onto the selected "
                "terrain heightfield; arbitrary mesh/walkmesh shrink-wrap remains planned."
            ),
        )

    if key == "entry_point":
        return _route(
            action,
            focus_component_mode="placement",
            focus_snap_mode="face",
            command_method="set_authored_module_entry_point",
            command_kwargs={
                "area_resref": str(ctx.entry_area_resref or "").strip(),
                "position": tuple(ctx.entry_position),
                "facing": float(ctx.entry_facing),
            },
            mutates_kmap=True,
            authoring_context=(
                "Entry Point: write the authored module IFO player start from the selected KMAP-world position; "
                "validate that it lands on a reachable WOK before export/game proof."
            ),
        )

    if key == "opening":
        room_resref = str(ctx.room_resref or "").strip()
        if not room_resref:
            return _route(
                action,
                focus_component_mode="edge",
                focus_snap_mode="edge",
                enabled=False,
                disabled_reason="Wall Opening needs a selected authored floor-plan room before it can cut KOTOR-safe doorway geometry.",
            )
        return _route(
            action,
            focus_component_mode="edge",
            focus_snap_mode="edge",
            command_method="apply_authored_room_operation",
            command_kwargs={
                "operation": "wall_opening",
                "room_resref": room_resref,
                "name": str(ctx.wall_opening_name or "doorway_opening").strip() or "doorway_opening",
                "edge_index": int(ctx.wall_opening_edge_index),
                "center_fraction": float(ctx.wall_opening_center_fraction),
                "width": float(ctx.wall_opening_width),
                "height": float(ctx.wall_opening_height),
                "bottom": float(ctx.wall_opening_bottom),
            },
            mutates_kmap=True,
            authoring_context=(
                "Wall Opening: cut a named doorway/window opening into one authored floor-plan wall edge; "
                "use Opening Marker next to turn it into KOTOR door, trigger, or waypoint transition data."
            ),
        )

    if key == "opening_marker":
        opening_name = str(ctx.opening_name or "").strip()
        if not str(ctx.room_resref or "").strip() or not opening_name:
            return _route(
                action,
                focus_component_mode="placement",
                focus_snap_mode="doorhook",
                enabled=False,
                disabled_reason="Opening Marker needs an authored wall opening selected before it can create KOTOR transition data.",
            )
        kwargs: dict[str, Any] = {
            "operation": "opening_transition_marker",
            "room_resref": str(ctx.room_resref or "").strip(),
            "opening_name": opening_name,
            "marker_kind": str(ctx.opening_marker_kind or "door").strip().lower() or "door",
            "template_resref": str(ctx.opening_marker_template_resref or "").strip(),
            "tag": str(ctx.opening_marker_tag or "").strip(),
            "linked_to": str(ctx.opening_marker_linked_to or "").strip(),
            "linked_to_module": str(ctx.opening_marker_linked_to_module or "").strip(),
            "transition_destination": int(ctx.opening_marker_transition_destination),
        }
        if ctx.opening_marker_edge_index is not None:
            kwargs["edge_index"] = int(ctx.opening_marker_edge_index)
        return _route(
            action,
            focus_component_mode="placement",
            focus_snap_mode="doorhook",
            command_method="apply_authored_room_operation",
            command_kwargs=kwargs,
            mutates_kmap=True,
            authoring_context=(
                "Opening Marker: convert a visual floor-plan wall opening into authored KOTOR door, trigger, "
                "or waypoint transition data with LinkedTo/LinkedToModule/TransitionDestin readiness checks."
            ),
        )

    placement_kind = _PLACEMENT_ACTIONS.get(key)
    if placement_kind:
        template_resref = _placement_template_for_action(ctx, placement_kind, key)
        return _route(
            action,
            placement_kind=placement_kind,
            command_method="add_authored_gameplay_placement",
            command_kwargs={
                "kind": placement_kind,
                "template_resref": template_resref,
                "tag": _placement_tag_for_action(ctx, placement_kind),
                "position": tuple(ctx.placement_position),
                "bearing": float(ctx.placement_bearing),
            },
            mutates_kmap=True,
            authoring_context=(
                f"Placement: add a {placement_kind} blueprint/resref to authored GIT/IFO state at the current placement position; "
                "validate template availability and walkable WOK before export/game proof."
            ),
        )

    if key == "vertex_snap":
        if ctx.point_index is None or ctx.target_point_index is None:
            return _route(
                action,
                focus_component_mode="vertex",
                focus_snap_mode="vertex",
                enabled=False,
                disabled_reason="Vertex snap needs a source point and a target point; hold V or choose points first.",
            )
        return _route(
            action,
            focus_component_mode="vertex",
            focus_snap_mode="vertex",
            command_method="snap_authored_floor_plan_vertex",
            command_kwargs={
                "room_resref": ctx.room_resref,
                "point_index": int(ctx.point_index),
                "target_point_index": int(ctx.target_point_index),
                "target_room_resref": ctx.target_room_resref,
            },
            mutates_kmap=True,
        )

    if key in {"weld", "merge_components"}:
        indices = _clean_indices(ctx.point_indices)
        if len(indices) < 2:
            return _route(
                action,
                focus_component_mode="vertex",
                focus_snap_mode="vertex",
                enabled=False,
                disabled_reason="Weld/Merge needs at least two selected floor-plan vertices.",
            )
        return _route(
            action,
            focus_component_mode="vertex",
            focus_snap_mode="vertex",
            command_method="weld_authored_floor_plan_vertices",
            command_kwargs={
                "room_resref": ctx.room_resref,
                "point_indices": indices,
                "target_point_index": ctx.target_point_index,
                "position_policy": str(ctx.metadata.get("position_policy") or "target"),
            },
            mutates_kmap=True,
        )

    if key in {"flatten", "transform_snap_level"}:
        indices = _clean_indices(ctx.point_indices)
        if len(indices) < 2:
            return _route(
                action,
                focus_component_mode="vertex",
                focus_snap_mode="level" if key == "transform_snap_level" else "grid",
                enabled=False,
                disabled_reason="Level/flatten snap needs two or more selected floor-plan vertices.",
            )
        return _route(
            action,
            focus_component_mode="vertex",
            focus_snap_mode="level" if key == "transform_snap_level" else "grid",
            command_method="flatten_authored_floor_plan_vertices",
            command_kwargs={
                "room_resref": ctx.room_resref,
                "point_indices": indices,
                "axis": _clean_axis(ctx.axis),
                "value": ctx.metadata.get("value"),
            },
            mutates_kmap=True,
        )

    if key == "cleanup":
        return _route(
            action,
            focus_component_mode="vertex",
            focus_snap_mode="grid",
            command_method="cleanup_authored_floor_plan_vertices",
            command_kwargs={
                "room_resref": ctx.room_resref,
                "tolerance": float(ctx.metadata.get("tolerance") or 0.001),
            },
            mutates_kmap=True,
        )

    if key == "mirror_z":
        kwargs: dict[str, Any] = {
            "operation": "mirror_z",
            "room_resref": ctx.room_resref,
        }
        if "center_height" in ctx.metadata:
            kwargs["center_height"] = float(ctx.metadata["center_height"])
        return _route(
            action,
            focus_component_mode="terrain",
            focus_snap_mode="surface",
            command_method="apply_authored_terrain_operation",
            command_kwargs=kwargs,
            mutates_kmap=True,
            authoring_context=(
                "Mirror Z: reflect a terrain heightfield around a horizontal Z plane, then revalidate WOK slope, "
                "placements, and export readiness. Arbitrary mesh/component Z mirroring remains planned."
            ),
        )

    if key == "bend_tool":
        kwargs = {
            "operation": "bend",
            "room_resref": ctx.room_resref,
            "axis": _clean_axis(ctx.axis),
            "amplitude": float(ctx.metadata.get("amplitude", ctx.operation_distance)),
        }
        if "center" in ctx.metadata:
            kwargs["center"] = float(ctx.metadata["center"])
        if "span" in ctx.metadata:
            kwargs["span"] = float(ctx.metadata["span"])
        return _route(
            action,
            focus_component_mode="terrain",
            focus_snap_mode="surface",
            command_method="apply_authored_terrain_operation",
            command_kwargs=kwargs,
            mutates_kmap=True,
            authoring_context=(
                "Bend: bake a parabolic X/Y height profile into the selected terrain heightfield, "
                "then revalidate WOK slope, placements, and export readiness. Arbitrary mesh/component bending remains planned."
            ),
        )

    if key == "lattice":
        kwargs: dict[str, Any] = {
            "operation": "lattice",
            "room_resref": ctx.room_resref,
            "strength": float(ctx.metadata.get("strength", 1.0)),
        }
        if "control_deltas" in ctx.metadata:
            kwargs["control_deltas"] = ctx.metadata["control_deltas"]
        else:
            kwargs["amplitude"] = float(ctx.metadata.get("amplitude", ctx.operation_distance))
        return _route(
            action,
            focus_component_mode="terrain",
            focus_snap_mode="surface",
            command_method="apply_authored_terrain_operation",
            command_kwargs=kwargs,
            mutates_kmap=True,
            authoring_context=(
                "Lattice: bake a heightfield control cage into the selected terrain, then revalidate WOK slope, "
                "placements, and export readiness. Arbitrary mesh/object lattice deformation remains planned."
            ),
        )

    if key == "curve_tool":
        points = ctx.metadata.get("points")
        if points is None:
            distance = max(1.0, abs(float(ctx.operation_distance)) * 4.0)
            points = ((0.0, 0.0, 0.0), (distance, 0.0, 0.0), (distance, distance * 0.5, 0.0))
        return _route(
            action,
            focus_component_mode="vertex",
            focus_snap_mode="grid",
            command_method="add_authored_curve_guide",
            command_kwargs={
                "name": str(ctx.metadata.get("curve_name") or ""),
                "points": tuple(points),
                "purpose": str(ctx.metadata.get("curve_purpose") or "path_guide"),
                "room_resref": ctx.room_resref,
                "coordinate_space": str(ctx.metadata.get("coordinate_space") or "kmap_world"),
                "metadata": {"source_action": "curve_tool"},
            },
            mutates_kmap=True,
            authoring_context=(
                "Curve: add a durable KMAP construction guide for roads, terrain ridges, placement paths, "
                "or later sweep/PTH tools. This is previewable guide data, not baked KOTOR runtime geometry yet."
            ),
        )

    if key in {"mirror", "mirror_x", "mirror_y"}:
        axis = {"mirror_y": "y", "mirror_x": "x"}.get(key, _clean_axis(ctx.axis))
        return _route(
            action,
            focus_component_mode="vertex",
            focus_snap_mode="grid",
            command_method="mirror_authored_floor_plan_vertices",
            command_kwargs={"room_resref": ctx.room_resref, "axis": axis},
            mutates_kmap=True,
        )

    if key in {"normals", "reverse_normals"}:
        return _route(
            action,
            focus_component_mode="face",
            focus_snap_mode="grid",
            command_method="cleanup_authored_floor_plan_normals",
            command_kwargs={"room_resref": ctx.room_resref, "positive_z": key != "reverse_normals" and bool(ctx.positive_z)},
            mutates_kmap=True,
        )

    if key in {"soften_edges", "harden_edges"}:
        policy = "soft" if key == "soften_edges" else "hard"
        return _route(
            action,
            focus_component_mode="edge",
            focus_snap_mode="grid",
            command_method="set_authored_room_edge_normal_policy",
            command_kwargs={
                "room_resref": ctx.room_resref,
                "policy": policy,
                "primitive_name": ctx.primitive_name,
                "edge_indices": tuple(ctx.metadata.get("edge_indices") or ()),
            },
            mutates_kmap=True,
            authoring_context=(
                "Edge normals: record visual soft/hard edge intent in authored KMAP state; "
                "WOK traversal remains validated separately."
            ),
        )

    if key == "extrude":
        return _route(
            action,
            focus_component_mode="edge",
            focus_snap_mode="grid",
            command_method="apply_authored_room_operation",
            command_kwargs={
                "operation": "edge_extrude",
                "room_resref": ctx.room_resref,
                "distance": float(ctx.operation_distance),
                "edge_index": int(ctx.operation_edge_index),
            },
            mutates_kmap=True,
            authoring_context=(
                "Extrude: pull the selected floor-plan edge into a KOTOR-authored room footprint; "
                "MDL/WOK generation must be revalidated."
            ),
        )

    if key == "bevel":
        return _route(
            action,
            focus_component_mode="edge",
            focus_snap_mode="grid",
            command_method="apply_authored_room_operation",
            command_kwargs={
                "operation": "bevel",
                "room_resref": ctx.room_resref,
                "distance": float(ctx.operation_distance),
            },
            mutates_kmap=True,
            authoring_context=(
                "Bevel: chamfer convex room footprint corners while preserving deterministic WOK output."
            ),
        )

    if key in {"boolean", "cut", "cut_slice_insert_edges", "insert_edge_loop"}:
        operation = "rectangular_cut" if key == "boolean" else "axis_split"
        kwargs: dict[str, Any] = {"operation": operation, "room_resref": ctx.room_resref}
        if operation == "rectangular_cut":
            kwargs.update({"center": tuple(ctx.cut_center), "size": tuple(ctx.cut_size)})
        else:
            axis = _clean_axis(ctx.axis)
            coordinate = float(ctx.cut_center[1] if axis == "y" else ctx.cut_center[0])
            kwargs.update({"axis": axis, "coordinate": coordinate})
        return _route(
            action,
            focus_component_mode="face",
            focus_snap_mode="grid",
            command_method="apply_authored_room_operation",
            command_kwargs=kwargs,
            mutates_kmap=True,
            authoring_context=(
                "Cut/Slice/Edge Loop: split simple floor-plan geometry into explicit KOTOR room/export boundaries, "
                "then cleanup and validate before export."
                if operation == "axis_split"
                else "Cut/boolean: split or subtract simple floor-plan geometry, then cleanup and validate before export."
            ),
        )

    if key in {"boolean_a_minus_b", "boolean_b_minus_a"}:
        first = ctx.first_room_resref
        second = ctx.second_room_resref
        if not first or not second:
            return _route(
                action,
                focus_component_mode="object",
                focus_snap_mode="grid",
                enabled=False,
                disabled_reason="Boolean Difference needs two selected rectangular floor-plan rooms.",
            )
        minuend = first if key == "boolean_a_minus_b" else second
        cutter = second if key == "boolean_a_minus_b" else first
        return _route(
            action,
            focus_component_mode="object",
            focus_snap_mode="grid",
            command_method="apply_authored_room_operation",
            command_kwargs={
                "operation": "boolean_difference",
                "first_room_resref": minuend,
                "second_room_resref": cutter,
                "result_room_resref": ctx.result_room_resref,
            },
            mutates_kmap=True,
            authoring_context=(
                "Boolean Difference: subtract one compatible rectangular floor-plan room from another, "
                "consume the cutter operand, and emit KOTOR-safe room/export pieces."
            ),
        )

    if key == "triangulate":
        return _route(
            action,
            focus_component_mode="face",
            focus_snap_mode="grid",
            command_method="triangulate_authored_floor_plan_face",
            command_kwargs={"room_resref": ctx.room_resref},
            mutates_kmap=True,
        )

    if key in {"fill", "fill_hole"}:
        indices = _clean_indices(ctx.point_indices)
        if len(indices) < 3:
            return _route(
                action,
                focus_component_mode="face",
                focus_snap_mode="grid",
                enabled=False,
                disabled_reason="Fill needs a selected loop of at least three floor-plan points.",
            )
        return _route(
            action,
            focus_component_mode="face",
            focus_snap_mode="grid",
            command_method="fill_authored_floor_plan_face",
            command_kwargs={"room_resref": ctx.room_resref, "point_indices": indices},
            mutates_kmap=True,
        )

    if key == "bridge":
        if not ctx.first_room_resref or not ctx.second_room_resref or ctx.first_edge_index is None or ctx.second_edge_index is None:
            return _route(
                action,
                focus_component_mode="edge",
                focus_snap_mode="grid",
                enabled=False,
                disabled_reason="Bridge needs two selected room edges before it can create a connector room.",
            )
        return _route(
            action,
            focus_component_mode="edge",
            focus_snap_mode="grid",
            command_method="bridge_authored_floor_plan_edges",
            command_kwargs={
                "first_room_resref": ctx.first_room_resref,
                "first_edge_index": int(ctx.first_edge_index),
                "second_room_resref": ctx.second_room_resref,
                "second_edge_index": int(ctx.second_edge_index),
                "result_room_resref": ctx.result_room_resref,
            },
            mutates_kmap=True,
        )

    if key == "combine":
        if not ctx.first_room_resref or not ctx.second_room_resref:
            return _route(
                action,
                focus_component_mode="object",
                focus_snap_mode="grid",
                enabled=False,
                disabled_reason="Combine needs two compatible floor-plan rooms before it can merge export boundaries.",
            )
        return _route(
            action,
            focus_component_mode="object",
            focus_snap_mode="grid",
            command_method="merge_authored_floor_plan_rooms",
            command_kwargs={
                "first_room_resref": ctx.first_room_resref,
                "second_room_resref": ctx.second_room_resref,
                "result_room_resref": ctx.result_room_resref,
            },
            mutates_kmap=True,
        )

    if key == "separate":
        if not ctx.primitive_name:
            return _route(
                action,
                focus_component_mode="object",
                focus_snap_mode="grid",
                enabled=False,
                disabled_reason="Separate needs an authored composition primitive selection first.",
            )
        return _route(
            action,
            focus_component_mode="object",
            focus_snap_mode="grid",
            command_method="separate_authored_room_primitive",
            command_kwargs={
                "room_resref": ctx.room_resref,
                "primitive_name": ctx.primitive_name,
                "result_room_resref": ctx.result_room_resref,
            },
            mutates_kmap=True,
        )

    if key == "duplicate_special":
        if not ctx.primitive_name:
            return _route(
                action,
                focus_component_mode="object",
                focus_snap_mode="grid",
                enabled=False,
                disabled_reason="Duplicate Special needs an authored composition primitive selection first.",
            )
        return _route(
            action,
            focus_component_mode="object",
            focus_snap_mode="grid",
            command_method="duplicate_authored_room_primitive",
            command_kwargs={
                "room_resref": ctx.room_resref,
                "primitive_name": ctx.primitive_name,
                "duplicate_count": int(ctx.duplicate_count),
                "translation_offset": tuple(ctx.duplicate_translation_offset),
                "rotation_offset_degrees_z": float(ctx.duplicate_rotation_offset_degrees_z),
                "scale_multiplier": tuple(ctx.duplicate_scale_multiplier),
            },
            mutates_kmap=True,
            authoring_context=(
                "Duplicate Special: repeat the selected modular primitive with a deterministic transform offset; "
                "MDL/MDX/WOK/LYT/VIS/PTH/.mod proof becomes stale."
            ),
        )

    focus = _VERTEX_FOCUS.get(key)
    if focus is not None:
        mode, tool, snap = focus
        return _route(action, focus_component_mode=mode, focus_snap_mode=snap, command_method="", command_kwargs={}, mutates_kmap=False)

    return _route(action)


def execute_map_studio_tool_belt_action(controller: Any, action_key: str, context: MapStudioToolActionContext | None = None) -> Any:
    """Execute an already implemented headless Map Studio action."""

    route = resolve_map_studio_tool_belt_action(action_key, context)
    if not route.enabled:
        raise ValueError(route.disabled_reason or f"Map Studio action '{action_key}' is not ready.")
    if not route.command_method:
        raise ValueError(f"Map Studio action '{action_key}' selects a workflow but has no headless command to execute.")
    method = getattr(controller, route.command_method)
    return method(**route.command_kwargs)
