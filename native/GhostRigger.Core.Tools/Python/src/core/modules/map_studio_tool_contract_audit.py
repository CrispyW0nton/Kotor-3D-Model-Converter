"""Headless Map Studio tool-belt contract audit.

The Level Editor can arrange tool buttons, presets, and customization UI, but
Map Studio needs a core-owned way to sanity-check whether visible tools still
resolve to a command, a query, or an honest workflow focus.  This audit keeps
the Maya-like shelf from becoming decorative UI that is disconnected from KMAP
authoring, readiness, and export impact.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .map_studio_modeling_tools import (
    available_map_studio_modeling_tools,
    available_map_studio_tool_belt_actions,
    available_map_studio_tool_belt_presets,
)
from .map_studio_tool_action_dispatch import MapStudioToolActionContext, resolve_map_studio_tool_belt_action


@dataclass(frozen=True)
class MapStudioToolContractStatus:
    """One visible Map Studio action and its executable/readiness contract."""

    action_key: str
    label: str
    workspace_key: str
    tool_key: str
    implemented: bool
    route_enabled: bool
    contract_kind: str
    command_method: str = ""
    mutates_kmap: bool = False
    readiness_impact: str = ""
    preset_keys: tuple[str, ...] = ()
    in_any_preset: bool = False
    has_modeling_tool: bool = False
    issues: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MapStudioToolContractAudit:
    """Complete audit result for the Map Studio tool-belt surface."""

    total_actions: int
    implemented_actions: int
    command_backed_actions: int
    mutating_command_actions: int
    query_command_actions: int
    workflow_focus_actions: int
    studio_workspace_actions: int
    planned_actions: int
    capability_stage: str
    statuses: tuple[MapStudioToolContractStatus, ...]
    warnings: tuple[str, ...] = ()
    blocking_messages: tuple[str, ...] = ()

    @property
    def has_blockers(self) -> bool:
        return bool(self.blocking_messages)


def _rich_context() -> MapStudioToolActionContext:
    """Return a representative context that unblocks context-sensitive routes."""

    return MapStudioToolActionContext(
        room_resref="audit_room_a",
        first_room_resref="audit_room_a",
        second_room_resref="audit_room_b",
        result_room_resref="audit_room_out",
        primitive_name="audit_room_a_cube",
        primitive_kind="cube",
        placement_kind="placeable",
        placement_template_resref="plc_bench",
        placement_tag="audit_placeable",
        placement_position=(1.0, 1.0, 0.0),
        placement_bearing=90.0,
        light_room_resref="audit_room_a",
        light_name="audit_key_light",
        light_position=(1.0, 1.0, 2.25),
        light_color=(1.0, 0.92, 0.78),
        light_radius=8.0,
        light_intensity=1.0,
        light_type="point",
        wall_opening_name="audit_south_door",
        wall_opening_edge_index=0,
        wall_opening_center_fraction=0.5,
        wall_opening_width=1.5,
        wall_opening_height=2.1,
        wall_opening_bottom=0.0,
        opening_name="audit_south_door",
        opening_marker_kind="trigger",
        opening_marker_template_resref="trg_audit",
        opening_marker_tag="audit_exit_trigger",
        opening_marker_linked_to="wp_audit_dest",
        opening_marker_linked_to_module="graudit02",
        opening_marker_transition_destination=2,
        point_index=0,
        point_indices=(0, 1, 2, 3),
        target_point_index=1,
        target_room_resref="audit_room_a",
        first_edge_index=0,
        second_edge_index=1,
        axis="x",
        cut_center=(0.5, 0.5),
        cut_size=(0.25, 0.25),
        duplicate_count=2,
        metadata={
            "edge_indices": (0, 1),
            "position_policy": "target",
            "curve_name": "audit_curve",
            "curve_purpose": "terrain_ridge",
            "points": ((0.0, 0.0, 0.0), (1.0, 0.5, 0.0), (2.0, 0.5, 0.0)),
            "control_deltas": ((0.0, 0.0), (0.0, 0.5)),
        },
    )


def _contract_kind(action, route) -> str:
    if not bool(getattr(action, "implemented", False)):
        return "planned"
    if not bool(getattr(route, "enabled", False)):
        return "blocked_context"
    if getattr(route, "command_method", ""):
        return "command_mutates_kmap" if bool(getattr(route, "mutates_kmap", False)) else "command_query"
    if (
        getattr(route, "focus_component_mode", "")
        or getattr(route, "terrain_brush", "")
        or getattr(route, "primitive_kind", "")
        or getattr(route, "placement_kind", "")
    ):
        return "workflow_focus"
    if str(getattr(action, "workspace_key", "") or "") in {"lighting", "scripts", "export"}:
        return "studio_workspace"
    if str(getattr(action, "workspace_key", "") or "") in {"geometry", "terrain", "walkmesh", "placements"}:
        return "workflow_focus"
    return "unrouted"


def audit_map_studio_tool_belt_contract() -> MapStudioToolContractAudit:
    """Audit every visible Map Studio tool-belt action against core routing.

    The result is capability-honest: an action can be acceptable as a mutating
    command, a non-mutating query, a workflow focus, or a studio workspace
    action.  It is a blocker only when an implemented visible action is disabled
    even with representative context, has no recognized route semantics, or
    points at a missing modeling-tool definition.
    """

    context = _rich_context()
    actions = available_map_studio_tool_belt_actions()
    modeling_tool_keys = {str(tool.key) for tool in available_map_studio_modeling_tools()}
    preset_map: dict[str, tuple[str, ...]] = {}
    for preset in available_map_studio_tool_belt_presets():
        for key in tuple(getattr(preset, "action_keys", ()) or ()):
            preset_map.setdefault(str(key), ())
            preset_map[str(key)] = (*preset_map[str(key)], str(getattr(preset, "key", "") or ""))

    statuses: list[MapStudioToolContractStatus] = []
    warnings: list[str] = []
    blockers: list[str] = []
    for action in actions:
        route = resolve_map_studio_tool_belt_action(str(action.key), context)
        kind = _contract_kind(action, route)
        tool_key = str(getattr(action, "tool_key", "") or "")
        workspace_key = str(getattr(action, "workspace_key", "") or "")
        has_modeling_tool = (
            (not tool_key)
            or tool_key in modeling_tool_keys
            or str(getattr(action, "key", "") or "") in modeling_tool_keys
            or bool(getattr(route, "command_method", ""))
            or workspace_key in {"placements", "lighting", "scripts", "export"}
        )
        action_presets = tuple(sorted(set(preset_map.get(str(action.key), ()))))
        issues: list[str] = []
        if bool(getattr(action, "implemented", False)) and kind in {"blocked_context", "unrouted"}:
            issues.append(f"Implemented action resolves as {kind}.")
        if not has_modeling_tool:
            issues.append(f"Action references missing modeling tool '{tool_key}'.")
        if bool(getattr(action, "implemented", False)) and not action_presets:
            warnings.append(f"{action.key}: implemented action is not included in any built-in preset.")
        if issues:
            blockers.append(f"{action.key}: {' '.join(issues)}")
        statuses.append(
            MapStudioToolContractStatus(
                action_key=str(action.key),
                label=str(action.label),
                workspace_key=str(action.workspace_key),
                tool_key=tool_key,
                implemented=bool(action.implemented),
                route_enabled=bool(route.enabled),
                contract_kind=kind,
                command_method=str(route.command_method or ""),
                mutates_kmap=bool(route.mutates_kmap),
                readiness_impact=str(route.readiness_impact or ""),
                preset_keys=action_presets,
                in_any_preset=bool(action_presets),
                has_modeling_tool=has_modeling_tool,
                issues=tuple(issues),
                metadata={
                    "source": "map_studio:tool_contract_audit",
                    "capability_honesty": "command_or_workflow_classification",
                    "default_context": "representative_non_mutating_route_resolution",
                },
            )
        )

    command_backed = tuple(item for item in statuses if item.contract_kind in {"command_mutates_kmap", "command_query"})
    mutating = tuple(item for item in statuses if item.contract_kind == "command_mutates_kmap")
    query = tuple(item for item in statuses if item.contract_kind == "command_query")
    workflow = tuple(item for item in statuses if item.contract_kind == "workflow_focus")
    studio = tuple(item for item in statuses if item.contract_kind == "studio_workspace")
    planned = tuple(item for item in statuses if item.contract_kind == "planned")
    stage = "previewable_tool_contract_audit" if not blockers else "tool_contract_gaps"
    return MapStudioToolContractAudit(
        total_actions=len(statuses),
        implemented_actions=sum(1 for item in statuses if item.implemented),
        command_backed_actions=len(command_backed),
        mutating_command_actions=len(mutating),
        query_command_actions=len(query),
        workflow_focus_actions=len(workflow),
        studio_workspace_actions=len(studio),
        planned_actions=len(planned),
        capability_stage=stage,
        statuses=tuple(statuses),
        warnings=tuple(warnings),
        blocking_messages=tuple(blockers),
    )


__all__ = [
    "MapStudioToolContractAudit",
    "MapStudioToolContractStatus",
    "audit_map_studio_tool_belt_contract",
]
