"""Controller coordinating KMAP project state and module-editor services."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.level import KMapProject, KMapSerializer, KMapValidator, LevelExportBridge, LevelExportOptions, LevelScene, LevelTransform, new_kmap_project
from src.core.scene.module_scene_import import resolve_module_room_placement

from .module_blueprint_service import ModuleBlueprintService
from .module_builder_service import ModuleBuilderService
from .module_editor_model import MapStudioWorkspaceMode, ModuleEditorModel
from .authored_module_export import (
    AuthoredModuleExportRequest,
    AuthoredModuleGameProofRequest,
    AuthoredModuleInstallPrepRequest,
    export_authored_module_project,
    prepare_authored_module_install,
    record_authored_module_game_proof,
)
from .authored_module_kmap_bridge import (
    authored_project_from_kmap_payload,
    authored_project_to_kmap_payload,
    build_kmap_authored_module_readiness,
    create_dev_test_authored_module_payload,
)
from .authored_module_project import authored_resref_blocking_issue, normalise_resref
from .authored_module_validation_projection import authored_module_readiness_validation_issues
from .authored_gameplay_palette import authored_gameplay_palette_from_library_rows
from .map_studio_modeling_tools import (
    available_map_studio_component_modes,
    available_map_studio_edit_mode_contexts,
    available_map_studio_modeling_tools,
    available_map_studio_snap_modes,
    available_map_studio_terrain_brushes,
    available_map_studio_tool_belt_actions,
    available_map_studio_tool_belt_presets,
    map_studio_edit_mode_context,
    map_studio_modeling_tool_summary,
    map_studio_tool_command_search,
    map_studio_tool_belt_actions_for_preset,
    map_studio_viewport_performance_policy,
)
from .map_studio_export_objects import map_studio_export_object_boundaries
from .map_studio_terrain_sculpt_session import (
    MapStudioTerrainSculptApplyResult,
    prepare_terrain_sculpt_frame_for_project,
)
from .map_studio_tool_belt_preferences import (
    MAP_STUDIO_TOOL_BELT_SECTION,
    normalise_map_studio_tool_belt_preferences,
)
from .map_studio_tool_contract_audit import audit_map_studio_tool_belt_contract
from .map_studio_command_history import MapStudioCommandHistory, MapStudioCommandRestoreResult
from .map_studio_curve_guides import add_authored_curve_guide as add_curve_guide_to_project
from .map_studio_curve_guides import authored_curve_guides
from .map_studio_universal_transform_overlay import build_map_studio_universal_transform_overlay
from .authored_gameplay_marker_geometry import (
    AuthoredGameplayMarkerGeometry,
    authored_gameplay_marker_geometry_for_project,
)
from .authored_gameplay_preview import authored_gameplay_preview_markers
from .authored_module_lighting import (
    add_authored_room_light as add_authored_room_light_to_project,
    authored_room_light_rows,
    duplicate_authored_room_light,
    parse_authored_room_light_id,
    remove_authored_room_light,
    rename_authored_room_light,
    update_authored_room_light_properties,
    update_authored_room_light_transform,
)
from .authored_module_scripts import (
    authored_script_hook_field_choices,
    authored_script_hooks,
    remove_authored_script_hook,
    set_authored_script_hook,
)
from .authored_module_placements import (
    SUPPORTED_AUTHORED_GAMEPLAY_PLACEMENTS,
    add_authored_gameplay_placement,
    authored_gameplay_placement_rows,
    duplicate_authored_gameplay_placement,
    parse_authored_gameplay_placement_id,
    remove_authored_gameplay_placement,
    rename_authored_gameplay_placement,
    update_authored_module_entry_point,
    update_authored_gameplay_camera_properties,
    update_authored_gameplay_placement_transform,
    update_authored_gameplay_transition,
)
from .authored_room_operations import (
    add_authored_room_composition_primitive,
    apply_authored_floor_plan_axis_split,
    apply_authored_floor_plan_boolean_difference,
    apply_authored_floor_plan_rectangular_cut,
    apply_authored_terrain_operation,
    apply_authored_floor_plan_rectangular_union,
    apply_authored_floor_plan_operation,
    available_authored_composition_primitive_kinds,
    authored_floor_plan_room_choices,
    authored_floor_plan_vertex_snap_candidates,
    authored_room_composition_primitive_universal_transform,
    authored_terrain_room_choices,
    authored_room_composition_primitives,
    bridge_authored_floor_plan_edges,
    cleanup_authored_floor_plan_normals,
    cleanup_authored_floor_plan_vertices,
    duplicate_authored_room_composition_primitive,
    fill_authored_floor_plan_face,
    flatten_authored_floor_plan_vertices,
    grid_snap_authored_floor_plan_vertices,
    mirror_authored_floor_plan_vertices,
    move_authored_floor_plan_point,
    move_authored_room_composition_primitive,
    remove_authored_room_composition_primitive,
    separate_authored_room_composition_primitive,
    set_authored_floor_plan_extrusion_settings,
    set_authored_floor_plan_wall_opening,
    set_authored_room_edge_normal_policy,
    set_authored_room_composition_primitive_dimensions,
    set_authored_room_composition_primitive_style,
    set_authored_room_composition_primitive_transform,
    split_authored_floor_plan_face,
    snap_authored_floor_plan_vertex_to_vertex,
    transform_snap_authored_floor_plan_vertices,
    triangulate_authored_floor_plan_face,
    weld_authored_floor_plan_vertices,
)
from .authored_room_outline_geometry import AuthoredRoomOutlineGeometry, authored_room_outline_geometry_for_project
from .authored_room_presets import available_authored_room_primitive_presets, create_authored_module_from_room_preset
from .authored_room_style import update_authored_room_style
from .authored_terrain_builder import available_terrain_shape_presets
from .authored_terrain_walkability_overlay import (
    AuthoredTerrainWalkabilityOverlay,
    authored_terrain_walkability_overlay_for_project,
)
from .authored_walkmesh_status import AuthoredWalkmeshStatus, authored_walkmesh_status_for_project
from .authored_walkmesh_status import authored_walkmesh_room_surface_choices
from .authored_walkmesh_surfaces import authored_walkmesh_surface_palette
from .dev_module_smoke import DevModuleGameProofRequest, DevModuleInstallPrepRequest, DevModuleSmokeRequest, prepare_dev_test_module_install, record_dev_module_game_proof
from .module_layout_service import ModuleLayoutService
from .module_porter_service import ModulePorterService
from .module_walkmesh_service import ModuleWalkmeshService


def _read_json_object(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


MAP_STUDIO_MODELING_STALE_OUTPUTS = ("MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod")
MAP_STUDIO_MODELING_READINESS_IMPACT = "Map Studio validation, export, install handoff, and game proof are stale."


@dataclass(frozen=True)
class MapStudioLaunchHandoffSummary:
    """Non-mutating summary of the current Map Studio in-game launch handoff."""

    ready: bool
    module_root: str
    game: str
    warp_command: str
    launcher_path: str = ""
    proof_manifest_path: str = ""
    proof_recording_script_path: str = ""
    launch_helper_command: str = ""
    elevated_launch_script_path: str = ""
    installed_module_path: str = ""
    checklist_path: str = ""
    resolved_modules_dir: str = ""
    resolved_game_root_dir: str = ""
    warnings: tuple[str, ...] = ()
    blocking_messages: tuple[str, ...] = ()
    summary: str = ""
    next_action: str = ""
    capability_stage: str = "installed_for_game_test_handoff"


@dataclass(frozen=True)
class MapStudioGameProofRecordingSummary:
    """Non-mutating defaults for recording Map Studio in-game proof."""

    ready: bool
    module_root: str
    game: str
    warp_command: str
    proof_manifest_path: str = ""
    default_evidence_path: str = ""
    required_checks: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    blocking_messages: tuple[str, ...] = ()
    summary: str = ""
    next_action: str = ""
    capability_stage: str = "installed_for_game_test_recording_handoff"


class ModuleEditorController:
    def __init__(self, model: ModuleEditorModel | None = None) -> None:
        self.model = model or ModuleEditorModel()
        self.layout_service = ModuleLayoutService()
        self.walkmesh_service = ModuleWalkmeshService()
        self.blueprint_service = ModuleBlueprintService()
        self.builder_service = ModuleBuilderService()
        self.porter_service = ModulePorterService()
        self.validator = KMapValidator()
        self.export_bridge = LevelExportBridge(self.validator)
        self.command_history = MapStudioCommandHistory()
        self._terrain_sculpt_command_before = None

    @property
    def project(self) -> KMapProject:
        return self.model.project

    def _capture_map_studio_command_state(self):
        return self.command_history.capture(
            self.project,
            selected_ids=tuple(self.model.selected_ids),
            active_module_id=self.model.active_module_id,
            active_room_id=self.model.active_room_id,
        )

    def _record_map_studio_command(
        self,
        *,
        action_key: str,
        label: str,
        before,
        stale_outputs: tuple[str, ...] = MAP_STUDIO_MODELING_STALE_OUTPUTS,
        readiness_impact: str = MAP_STUDIO_MODELING_READINESS_IMPACT,
        summary: str = "",
        metadata: dict[str, Any] | None = None,
    ):
        record = self.command_history.record(
            action_key=action_key,
            label=label,
            before=before,
            after=self._capture_map_studio_command_state(),
            stale_outputs=stale_outputs,
            readiness_impact=readiness_impact,
            summary=summary,
            metadata=metadata,
        )
        if record is not None:
            self.model.log(f"Undo checkpoint recorded: {record.label}.")
        return record

    def can_undo_map_studio_command(self) -> bool:
        return self.command_history.can_undo

    def can_redo_map_studio_command(self) -> bool:
        return self.command_history.can_redo

    def undo_map_studio_command(self) -> MapStudioCommandRestoreResult | None:
        result = self.command_history.undo()
        if result is None:
            return None
        self.model.set_project(result.project)
        self.model.selected_ids = list(result.selected_ids)
        self.model.active_module_id = result.active_module_id
        self.model.active_room_id = result.active_room_id
        self._terrain_sculpt_command_before = None
        self.model.log(result.message)
        return result

    def redo_map_studio_command(self) -> MapStudioCommandRestoreResult | None:
        result = self.command_history.redo()
        if result is None:
            return None
        self.model.set_project(result.project)
        self.model.selected_ids = list(result.selected_ids)
        self.model.active_module_id = result.active_module_id
        self.model.active_room_id = result.active_room_id
        self._terrain_sculpt_command_before = None
        self.model.log(result.message)
        return result

    def new_project(self, name: str = "new_level", game: str = "K1", author: str = "") -> KMapProject:
        game_key = str(game or "K1").strip().upper()
        if game_key not in {"K1", "K2"}:
            raise ValueError("Map Studio projects must target K1 or K2.")
        issue = authored_resref_blocking_issue("Map Studio module root", name)
        if issue:
            raise ValueError(issue)
        project_name = normalise_resref(name) or "new_level"
        self.model.set_project(new_kmap_project(name=project_name, game=game_key, author=str(author or "").strip()))
        self.command_history.clear()
        self._terrain_sculpt_command_before = None
        self.model.project.dirty = True
        self.model.log(f"Created new Map Studio KMAP project {project_name} for {game_key}.")
        return self.model.project

    def open_project(self, path: str | Path) -> KMapProject:
        project = KMapSerializer.load(path)
        self.model.set_project(project)
        self.command_history.clear()
        self._terrain_sculpt_command_before = None
        self.model.log(f"Opened KMAP {Path(path).name}.")
        return project

    def save_project(self, path: str | Path | None = None) -> None:
        KMapSerializer.save(self.project, path)
        self.model.log(f"Saved KMAP {Path(self.project.path).name}.")

    def add_module(self, name: str, *, source_path: str = "", game: str | None = None):
        module = LevelScene(self.project).add_module(name, source_path=source_path, game=game)
        self.model.active_module_id = module.module_id
        self.model.select(module.module_id)
        self.model.log(f"Added module {module.module_name}.")
        return module

    def remove_selected(self) -> bool:
        item_id = self.model.selected_ids[0] if self.model.selected_ids else ""
        if not item_id:
            return False
        if item_id.startswith("authored:"):
            update = self.remove_authored_gameplay_placement(item_id)
            self.model.select("")
            self.model.log(f"Deleted Map Studio {update.kind} placement {update.tag}.")
            return True
        if item_id.startswith("authored_light:"):
            update = self.remove_authored_room_light(item_id)
            self.model.select("")
            self.model.log(f"Deleted Map Studio room light {update.light.name}.")
            return True
        scene = LevelScene(self.project)
        changed = scene.remove_room(item_id) or scene.remove_module(item_id)
        if changed:
            self.model.select("")
            self.model.log(f"Deleted {item_id}.")
        return changed

    def duplicate_selected(self):
        item_id = self.model.selected_ids[0] if self.model.selected_ids else ""
        if item_id.startswith("authored:"):
            update = self.duplicate_authored_gameplay_placement(item_id)
            self.model.select(update.placement_id)
            self.model.log(f"Duplicated Map Studio {update.kind} placement {update.tag}.")
            return update
        if item_id.startswith("authored_light:"):
            update = self.duplicate_authored_room_light(item_id)
            self.model.select(update.light_id)
            self.model.log(f"Duplicated Map Studio room light {update.light.name}.")
            return update
        clone = LevelScene(self.project).duplicate_room(item_id)
        if clone is not None:
            self.model.select(clone.room_id)
            self.model.log(f"Duplicated room {clone.name}.")
        return clone

    def load_lyt(self, path: str | Path):
        return self.layout_service.load_lyt_file(self.project, path, module_id=self.model.active_module_id)

    def load_wok(self, path: str | Path, room_id: str = ""):
        target_room = room_id or self.model.active_room_id
        result = self.walkmesh_service.load_wok_file(self.project, path, room_id=target_room)
        if result.ok and target_room:
            self.model.loaded_walkmeshes[target_room] = result.wok
        return result

    def validate(self):
        issues = list(self.validator.validate(self.project))
        readiness_result = self.authored_module_readiness()
        issues.extend(
            authored_module_readiness_validation_issues(
                readiness_result.readiness,
                bridge_warnings=readiness_result.warnings,
                bridge_blocking_messages=readiness_result.blocking_messages,
            )
        )
        return issues

    def authored_module_readiness(self):
        """Return Map Studio authored-module readiness for the current KMAP."""

        return build_kmap_authored_module_readiness(self.project)

    def map_studio_workspace_modes(self) -> tuple[MapStudioWorkspaceMode, ...]:
        """Return the modder-facing Map Studio workspaces exposed by the Level Editor."""

        return (
            MapStudioWorkspaceMode(
                key="project",
                label="Project",
                summary="KMAP identity, target game, outliner, asset browser, and save/open state.",
                next_action="Create or open a KMAP, then choose the workspace for the current map task.",
            ),
            MapStudioWorkspaceMode(
                key="geometry",
                label="Room Geometry",
                summary="Build floors, walls, corridors, doorway blockouts, primitives, and component-mode edits: Object, Vertex, Edge, Face, and Walkmesh.",
                next_action="Choose a modeling mode/tool, then create primitives, snap vertices, bevel/inset, cut, bridge, boolean, or shape the authored layout.",
            ),
            MapStudioWorkspaceMode(
                key="terrain",
                label="Terrain Builder",
                summary="Create terrain patches, sculpt heightfield samples, and check slope/walkability intent.",
                next_action="Create a terrain patch, choose a heightfield room, then raise/lower/smooth terrain samples.",
            ),
            MapStudioWorkspaceMode(
                key="walkmesh",
                label="Walkmesh",
                summary="Inspect WOK surfaces, walkable faces, non-walkable barriers, and traversal readiness.",
                next_action="Generate or inspect WOK faces before staging a playable module.",
            ),
            MapStudioWorkspaceMode(
                key="placements",
                label="Placements",
                summary="Place KOTOR creatures, placeables, doors, triggers, encounters, cameras, sounds, waypoints, and stores.",
                next_action="Search the game library or type a template resref, then place the resource in the viewport.",
            ),
            MapStudioWorkspaceMode(
                key="lighting",
                label="Lighting",
                summary="Author room lights and plan future lightmap coverage before export/game testing.",
                next_action="Add key/fill/ambient lights per room and validate lighting coverage in readiness.",
            ),
            MapStudioWorkspaceMode(
                key="scripts",
                label="Scripts + Transitions",
                summary="Assign ARE/IFO script hooks and configure door, trigger, or waypoint transition targets.",
                next_action="Set script resrefs or transition destination tags/modules when the map needs behavior or exits.",
            ),
            MapStudioWorkspaceMode(
                key="export",
                label="Export + Game Proof",
                summary="Validate, stage, install, open warp-test handoff, and record live KOTOR proof.",
                next_action="Validate first; only call the module game-ready after a staged install and recorded warp proof.",
            ),
        )

    def create_dev_test_authored_module(self, *, module_root: str = "grdev01"):
        """Store the editable first Map Studio dev-test module in the KMAP."""

        root = str(module_root or "grdev01").strip() or "grdev01"
        payload = create_dev_test_authored_module_payload(module_root=root, game=str(self.project.game or "K1").upper())
        self.project.extra_sections["authored_module"] = payload
        self.project.name = str(payload.get("module_root") or root)
        self.project.game = str(payload.get("game") or self.project.game or "K1").upper()
        self.project.dirty = True
        self.model.log(f"Created authored Map Studio module {self.project.name}.")
        return self.authored_module_readiness()

    def available_authored_room_presets(self):
        """Return named primitive room presets for the Map Studio Builder tab."""

        return available_authored_room_primitive_presets()

    def available_authored_terrain_shape_presets(self):
        """Return named terrain shape presets for the Map Studio Builder tab."""

        return available_terrain_shape_presets()

    def available_authored_walkmesh_surfaces(self):
        """Return named WOK surface choices for authored room floors."""

        return authored_walkmesh_surface_palette()

    def available_authored_composition_primitive_kinds(self):
        """Return primitive kinds that can be added to authored composition rooms."""

        return available_authored_composition_primitive_kinds()

    def available_authored_gameplay_placement_kinds(self):
        """Return supported authored gameplay placement kinds for Map Studio UI."""

        return SUPPORTED_AUTHORED_GAMEPLAY_PLACEMENTS

    def available_map_studio_component_modes(self):
        """Return visible object/component edit modes for Map Studio modeling."""

        return available_map_studio_component_modes()

    def available_map_studio_edit_mode_contexts(self):
        """Return visible top-level edit-mode context for Map Studio UX."""

        return available_map_studio_edit_mode_contexts()

    def map_studio_edit_mode_context(self, mode_label: str = "Object"):
        """Return the KOTOR-specific UX context for a visible edit mode."""

        return map_studio_edit_mode_context(mode_label)

    def available_map_studio_modeling_tools(self):
        """Return visible Maya-like, KOTOR-aware modeling tools."""

        return available_map_studio_modeling_tools()

    def available_map_studio_snap_modes(self):
        """Return visible snap modes for Map Studio modeling tools."""

        return available_map_studio_snap_modes()

    def available_map_studio_terrain_brushes(self):
        """Return visible terrain sculpt brushes for Map Studio."""

        return available_map_studio_terrain_brushes()

    def map_studio_viewport_performance_policy(self):
        """Return the interaction budget for smooth Map Studio viewport edits."""

        return map_studio_viewport_performance_policy()

    def available_map_studio_tool_belt_actions(self):
        """Return actions that can be shown in the Map Studio tool belt."""

        return available_map_studio_tool_belt_actions()

    def available_map_studio_tool_belt_presets(self):
        """Return built-in tool-belt presets for common map-building tasks."""

        return available_map_studio_tool_belt_presets()

    def map_studio_tool_belt_actions_for_preset(
        self,
        preset_key: str = "blockout",
        *,
        custom_action_keys: tuple[str, ...] | list[str] = (),
    ):
        """Resolve a preset or custom session action list into visible belt buttons."""

        return map_studio_tool_belt_actions_for_preset(
            preset_key,
            custom_action_keys=custom_action_keys,
        )

    def map_studio_tool_command_search(
        self,
        query: str = "",
        *,
        limit: int = 50,
        include_planned: bool = False,
    ):
        """Return searchable Map Studio command entries for command palettes and custom belts."""

        return map_studio_tool_command_search(
            query,
            limit=limit,
            include_planned=include_planned,
        )

    def map_studio_tool_belt_contract_audit(self):
        """Return a headless audit of visible Map Studio tool-belt action contracts."""

        return audit_map_studio_tool_belt_contract()

    def map_studio_tool_belt_preferences(self):
        """Return KMAP-persisted Map Studio tool-belt preferences."""

        payload = dict((getattr(self.project, "extra_sections", {}) or {}).get(MAP_STUDIO_TOOL_BELT_SECTION) or {})
        return normalise_map_studio_tool_belt_preferences(payload)

    def set_map_studio_tool_belt_preferences(
        self,
        *,
        preset_key: str = "blockout",
        custom_action_keys: tuple[str, ...] | list[str] = (),
    ):
        """Persist Map Studio tool-belt preferences into the current KMAP."""

        preferences = normalise_map_studio_tool_belt_preferences(
            preset_key=preset_key,
            custom_action_keys=custom_action_keys,
        )
        self.project.extra_sections[MAP_STUDIO_TOOL_BELT_SECTION] = preferences.to_kmap_section()
        self.project.dirty = True
        self.model.log(f"Updated Map Studio tool belt preference: {preferences.preset_key}.")
        return preferences

    def map_studio_modeling_tool_summary(
        self,
        *,
        mode_key: str = "object",
        tool_key: str = "",
        snap_key: str = "grid",
    ) -> str:
        """Return UI-ready active modeling context text."""

        return map_studio_modeling_tool_summary(
            mode_key=mode_key,
            tool_key=tool_key,
            snap_key=snap_key,
        )

    def authored_curve_guides(self):
        """Return KMAP-authored curve guides for road, path, terrain, and PTH planning."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            return ()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        return authored_curve_guides(authored)

    def authored_gameplay_palette_entries(self, rows, *, query: str = "", kind: str = ""):
        """Return game-library-backed resources that can seed gameplay placements."""

        return authored_gameplay_palette_from_library_rows(
            rows,
            game=str(getattr(self.project, "game", "") or ""),
            query=query,
            kind=kind,
        )

    def authored_gameplay_placements(self):
        """Return selectable authored gameplay placements for the current KMAP."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            return ()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        return authored_gameplay_placement_rows(authored)

    def authored_module_entry_point(self):
        """Return the authored IFO player start for the current KMAP."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            return None
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        return authored.placements.entry_point

    def authored_room_lights(self):
        """Return selectable authored room lights for the current KMAP."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            return ()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        return authored_room_light_rows(authored)

    def authored_script_hook_field_choices(self):
        """Return editable ARE/IFO script hook fields for Map Studio controls."""

        return authored_script_hook_field_choices()

    def authored_script_hooks(self):
        """Return current authored script hooks for the current KMAP."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            return {"area": {}, "module": {}}
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        return authored_script_hooks(authored)

    def authored_gameplay_preview_markers(self):
        """Return UI-ready preview markers for authored gameplay placements."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            return ()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        return authored_gameplay_preview_markers(authored)

    def authored_gameplay_marker_geometry(self):
        """Return renderer-ready geometry for authored gameplay placement markers."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            return AuthoredGameplayMarkerGeometry()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        return authored_gameplay_marker_geometry_for_project(authored)

    def authored_room_outline_geometry(self):
        """Return renderer-ready outlines for authored Map Studio rooms."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            return AuthoredRoomOutlineGeometry()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        return authored_room_outline_geometry_for_project(authored)

    def authored_room_primitive_transforms(self):
        """Return editable composition primitive transform rows for the current KMAP."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            return ()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        return authored_room_composition_primitives(authored)

    def authored_room_primitive_universal_transform(self, *, room_resref: str, primitive_name: str):
        """Return exact selected primitive bounds for the Universal Manipulator."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        return authored_room_composition_primitive_universal_transform(
            authored,
            room_resref=room_resref,
            primitive_name=primitive_name,
        )

    def map_studio_universal_transform_overlay(self, *, room_resref: str, primitive_name: str):
        """Return viewport-ready Universal Manipulator overlay geometry."""

        selection = self.authored_room_primitive_universal_transform(
            room_resref=room_resref,
            primitive_name=primitive_name,
        )
        return build_map_studio_universal_transform_overlay(selection)

    def map_studio_export_object_boundaries(self):
        """Return exportable authored room/object boundaries for the current KMAP."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            return ()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        return map_studio_export_object_boundaries(authored)

    def authored_floor_plan_room_choices(self):
        """Return floor-plan rooms that can participate in Builder boolean operations."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            return ()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        return authored_floor_plan_room_choices(authored)

    def authored_terrain_room_choices(self):
        """Return terrain rooms that can participate in Builder heightfield operations."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            return ()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        return authored_terrain_room_choices(authored)

    def authored_terrain_walkability_overlay(self):
        """Return renderer-ready terrain WOK walkability feedback."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            return AuthoredTerrainWalkabilityOverlay()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        return authored_terrain_walkability_overlay_for_project(authored)

    def authored_terrain_status(self):
        """Return modder-facing terrain authoring status for the current KMAP."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            return {
                "ready": False,
                "terrain_room_count": 0,
                "walkable_triangle_count": 0,
                "non_walk_triangle_count": 0,
                "max_slope_degrees": 0.0,
                "summary": "Terrain: no authored Map Studio module is loaded.",
                "next_action": "Create a Terrain Patch, then choose a brush before sculpting.",
                "warnings": (),
                "capability_stage": "previewable_status_query",
            }
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        choices = tuple(authored_terrain_room_choices(authored))
        overlay = authored_terrain_walkability_overlay_for_project(authored)
        ready = bool(choices)
        summary = (
            f"Terrain: {len(choices)} terrain room(s), {int(overlay.walkable_triangle_count)} walkable triangle(s), "
            f"{int(overlay.non_walk_triangle_count)} blocked triangle(s), max slope {float(overlay.max_slope_degrees):.1f} deg."
            if ready
            else "Terrain: no terrain heightfield rooms exist in this authored module."
        )
        return {
            "ready": ready,
            "terrain_room_count": len(choices),
            "walkable_triangle_count": int(overlay.walkable_triangle_count),
            "non_walk_triangle_count": int(overlay.non_walk_triangle_count),
            "max_slope_degrees": float(overlay.max_slope_degrees),
            "summary": summary,
            "next_action": (
                "Select a terrain room, apply a brush stroke, then validate WOK slope/walkability before staging."
                if ready
                else "Create a Terrain Patch or convert a room to terrain before sculpting."
            ),
            "warnings": tuple(overlay.warnings),
            "capability_stage": "previewable_status_query",
        }

    def authored_walkmesh_status(self):
        """Return modder-facing walkmesh status for the current KMAP."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            return AuthoredWalkmeshStatus(
                ready=False,
                summary="Walkmesh: no authored Map Studio module is loaded.",
                next_action="Create or open a KMAP with authored rooms before inspecting walkmesh.",
            )
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        return authored_walkmesh_status_for_project(authored)

    def authored_walkmesh_room_surface_choices(self):
        """Return authored rooms whose WOK floor surface can be edited in Walkmesh tools."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            return ()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        return authored_walkmesh_room_surface_choices(authored)

    def create_authored_room_preset_module(self, *, preset_id: str, module_root: str = "grdev01"):
        """Store an authored module created from a named primitive room preset."""

        root = str(module_root or "grdev01").strip() or "grdev01"
        before = self._capture_map_studio_command_state()
        authored = create_authored_module_from_room_preset(
            preset_id=preset_id,
            module_root=root,
            game=str(self.project.game or "K1").upper(),
        )
        payload = authored_project_to_kmap_payload(authored)
        self.project.extra_sections["authored_module"] = payload
        self.project.name = authored.metadata.module_root
        self.project.game = authored.game
        self.project.dirty = True
        self.model.log(f"Created authored Map Studio module {self.project.name} from primitive preset {preset_id}.")
        self._record_map_studio_command(
            action_key="map_studio.room_preset.create",
            label=f"Create authored module {authored.metadata.module_root}",
            before=before,
            metadata={"preset_id": preset_id, "module_root": root},
        )
        return self.authored_module_readiness()

    def apply_authored_room_operation(self, *, operation: str, **kwargs: Any):
        """Apply a floor-plan shaping operation to the current authored KMAP module."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        updated = apply_authored_floor_plan_operation(authored, operation, **kwargs)
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(f"Applied Map Studio room operation {operation}.")
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.operation",
            label=f"Apply room operation {operation}",
            before=before,
            metadata={"operation": operation, "kwargs": dict(kwargs)},
        )
        return self.authored_module_readiness()

    def rectangular_cut_authored_floor_plan_room(
        self,
        *,
        room_resref: str = "",
        center: Any,
        size: Any,
        room_resref_prefix: str | None = None,
    ):
        """Cut one authored floor-plan room with a rectangular cutter and record explicit command metadata."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        cut_center = tuple(float(value) for value in tuple(center or (0.0, 0.0))[:2])
        cut_size = tuple(float(value) for value in tuple(size or (1.0, 1.0))[:2])
        if len(cut_center) != 2 or len(cut_size) != 2:
            raise ValueError("Rectangular cut requires a 2D center and size in floor-plan local space.")
        updated = apply_authored_floor_plan_rectangular_cut(
            authored,
            room_resref=room_resref,
            center=(cut_center[0], cut_center[1]),
            size=(cut_size[0], cut_size[1]),
            room_resref_prefix=room_resref_prefix,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Rectangular-cut Map Studio room {room_resref or '(first room)'} at {cut_center} size {cut_size}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.rectangular_cut",
            label=f"Rectangular cut {room_resref or 'room'}",
            before=before,
            metadata={
                "room_resref": room_resref,
                "center": cut_center,
                "size": cut_size,
                "room_resref_prefix": room_resref_prefix or "",
            },
        )
        return self.authored_module_readiness()

    def boolean_difference_authored_floor_plan_rooms(
        self,
        *,
        first_room_resref: str,
        second_room_resref: str,
        result_room_resref: str = "",
    ):
        """Subtract one authored floor-plan room from another with explicit KMAP metadata."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        updated = apply_authored_floor_plan_boolean_difference(
            authored,
            first_room_resref=first_room_resref,
            second_room_resref=second_room_resref,
            result_room_resref=result_room_resref,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Applied Map Studio boolean difference {first_room_resref} - {second_room_resref}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.boolean_difference",
            label=f"Boolean difference {first_room_resref} - {second_room_resref}",
            before=before,
            metadata={
                "first_room_resref": first_room_resref,
                "second_room_resref": second_room_resref,
                "result_room_resref": result_room_resref,
            },
        )
        return self.authored_module_readiness()

    def axis_split_authored_floor_plan_room(
        self,
        *,
        room_resref: str = "",
        axis: str,
        coordinate: float,
        room_resref_prefix: str | None = None,
    ):
        """Split one floor-plan room along a local X/Y axis with explicit KMAP metadata."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        split_axis = str(axis or "x").strip().lower()
        split_coordinate = float(coordinate)
        updated = apply_authored_floor_plan_axis_split(
            authored,
            room_resref=room_resref,
            axis=split_axis,
            coordinate=split_coordinate,
            room_resref_prefix=room_resref_prefix,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Axis-split Map Studio room {room_resref or '(first room)'} on {split_axis}={split_coordinate:g}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.axis_split",
            label=f"Axis split {room_resref or 'room'} on {split_axis}",
            before=before,
            metadata={
                "room_resref": room_resref,
                "axis": split_axis,
                "coordinate": split_coordinate,
                "room_resref_prefix": room_resref_prefix or "",
            },
        )
        return self.authored_module_readiness()

    def set_authored_floor_plan_wall_opening(
        self,
        *,
        room_resref: str = "",
        name: str = "",
        edge_index: int = 0,
        center_fraction: float = 0.5,
        width: float = 1.5,
        height: float = 2.1,
        bottom: float = 0.0,
    ):
        """Add or replace one named wall opening on an authored floor-plan room edge."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        opening_name = str(name or "").strip() or f"opening_edge_{int(edge_index)}"
        updated = set_authored_floor_plan_wall_opening(
            authored,
            room_resref=room_resref,
            name=opening_name,
            edge_index=int(edge_index),
            center_fraction=float(center_fraction),
            width=float(width),
            height=float(height),
            bottom=float(bottom),
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Set Map Studio wall opening {opening_name} on {room_resref or '(first room)'} edge {int(edge_index)}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.wall_opening",
            label=f"Set wall opening {opening_name}",
            before=before,
            metadata={
                "room_resref": room_resref,
                "name": opening_name,
                "edge_index": int(edge_index),
                "center_fraction": float(center_fraction),
                "width": float(width),
                "height": float(height),
                "bottom": float(bottom),
            },
        )
        return self.authored_module_readiness()

    def apply_authored_terrain_operation(self, *, operation: str, **kwargs: Any):
        """Apply a terrain heightfield operation to the current authored KMAP module."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        updated = apply_authored_terrain_operation(authored, operation, **kwargs)
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(f"Applied Map Studio terrain operation {operation}.")
        self._record_map_studio_command(
            action_key="map_studio.terrain.operation",
            label=f"Apply terrain operation {operation}",
            before=before,
            metadata={"operation": operation, "kwargs": dict(kwargs)},
        )
        return self.authored_module_readiness()

    def add_authored_curve_guide(
        self,
        *,
        name: str = "",
        points: Any = (),
        purpose: str = "path_guide",
        room_resref: str = "",
        coordinate_space: str = "kmap_world",
        metadata: dict[str, Any] | None = None,
    ):
        """Add a Map Studio authoring curve guide to the current KMAP module."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        updated = add_curve_guide_to_project(
            authored,
            name=name,
            points=points,
            purpose=purpose,
            room_resref=room_resref,
            coordinate_space=coordinate_space,
            metadata=metadata,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        guide_name = str(updated.extra.get("last_curve_guide") or name or "curve")
        self.model.log(
            f"Added Map Studio curve guide {guide_name}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.curve_guide.add",
            label=f"Add curve guide {guide_name}",
            before=before,
            metadata={
                "name": name,
                "purpose": purpose,
                "room_resref": room_resref,
                "coordinate_space": coordinate_space,
            },
        )
        return self.authored_module_readiness()

    def prepare_map_studio_terrain_sculpt_frame(
        self,
        *,
        room_resref: str,
        brush: str,
        points: tuple[Any, ...] | list[Any],
        delta: float = 0.1,
        radius: int = 0,
        height: float = 0.0,
        iterations: int = 1,
        strength: float = 0.5,
        preserve_boundary: bool = True,
        max_points_per_frame: int = 8,
        budget_ms: float = 8.0,
    ):
        """Prepare a live terrain sculpt frame without mutating the KMAP project."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        return prepare_terrain_sculpt_frame_for_project(
            authored,
            room_resref=room_resref,
            brush=brush,
            points=points,
            delta=delta,
            radius=radius,
            height=height,
            iterations=iterations,
            strength=strength,
            preserve_boundary=preserve_boundary,
            max_points_per_frame=max_points_per_frame,
            budget_ms=budget_ms,
        )

    def commit_map_studio_terrain_sculpt_stroke(self, *, brush: str, room_resref: str):
        """Record one undo command for all terrain frames applied during a released stroke."""

        before = self._terrain_sculpt_command_before
        self._terrain_sculpt_command_before = None
        if before is not None:
            self._record_map_studio_command(
                action_key="map_studio.terrain.sculpt_stroke",
                label=f"Sculpt terrain {brush} on {room_resref}",
                before=before,
                metadata={"brush": brush, "room_resref": room_resref},
            )
        return self.authored_module_readiness()

    def apply_map_studio_terrain_sculpt_frame(
        self,
        *,
        room_resref: str,
        brush: str,
        points: tuple[Any, ...] | list[Any],
        delta: float = 0.1,
        radius: int = 0,
        height: float = 0.0,
        iterations: int = 1,
        strength: float = 0.5,
        preserve_boundary: bool = True,
        max_points_per_frame: int = 8,
        budget_ms: float = 8.0,
        force: bool = False,
    ) -> MapStudioTerrainSculptApplyResult:
        """Apply a coalesced live terrain sculpt frame while deferring full rebuild/validation."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        frame = prepare_terrain_sculpt_frame_for_project(
            authored,
            room_resref=room_resref,
            brush=brush,
            points=points,
            delta=delta,
            radius=radius,
            height=height,
            iterations=iterations,
            strength=strength,
            preserve_boundary=preserve_boundary,
            max_points_per_frame=max_points_per_frame,
            budget_ms=budget_ms,
        )
        if not frame.should_apply_live and not force:
            message = (
                f"Skipped live terrain sculpt frame for {frame.room_resref}: estimated "
                f"{frame.performance.estimated_apply_ms:.3f} ms exceeds {frame.performance.budget_ms:.3f} ms budget."
            )
            self.model.log(message)
            return MapStudioTerrainSculptApplyResult(applied=False, frame=frame, message=message)
        if self._terrain_sculpt_command_before is None:
            self._terrain_sculpt_command_before = self._capture_map_studio_command_state()
        updated = apply_authored_terrain_operation(authored, frame.operation, **frame.operation_kwargs)
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        message = (
            f"Applied live terrain sculpt frame to {frame.room_resref}: "
            f"{frame.applied_sample_count} point(s), dirty region only; full MDL/WOK rebuild deferred."
        )
        self.model.log(message)
        return MapStudioTerrainSculptApplyResult(applied=True, frame=frame, message=message)

    def merge_authored_floor_plan_rooms(
        self,
        *,
        first_room_resref: str,
        second_room_resref: str,
        result_room_resref: str = "",
    ):
        """Union two compatible floor-plan rooms in the current authored KMAP module."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        before = self._capture_map_studio_command_state()
        updated = apply_authored_floor_plan_rectangular_union(
            authored,
            first_room_resref=first_room_resref,
            second_room_resref=second_room_resref,
            result_room_resref=result_room_resref,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Merged Map Studio floor-plan rooms {first_room_resref} and {second_room_resref}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.merge_rooms",
            label=f"Merge {first_room_resref} and {second_room_resref}",
            before=before,
            metadata={
                "first_room_resref": first_room_resref,
                "second_room_resref": second_room_resref,
                "result_room_resref": result_room_resref,
            },
        )
        return self.authored_module_readiness()

    def bridge_authored_floor_plan_edges(
        self,
        *,
        first_room_resref: str,
        first_edge_index: int,
        second_room_resref: str,
        second_edge_index: int,
        result_room_resref: str = "",
    ):
        """Create a connector room between two compatible floor-plan room edges."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        before = self._capture_map_studio_command_state()
        updated = bridge_authored_floor_plan_edges(
            authored,
            first_room_resref=first_room_resref,
            first_edge_index=int(first_edge_index),
            second_room_resref=second_room_resref,
            second_edge_index=int(second_edge_index),
            result_room_resref=result_room_resref,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Bridged Map Studio floor-plan edge {first_edge_index} in {first_room_resref} "
            f"to edge {second_edge_index} in {second_room_resref}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.bridge_edges",
            label=f"Bridge {first_room_resref}:{int(first_edge_index)} to {second_room_resref}:{int(second_edge_index)}",
            before=before,
            metadata={
                "first_room_resref": first_room_resref,
                "first_edge_index": int(first_edge_index),
                "second_room_resref": second_room_resref,
                "second_edge_index": int(second_edge_index),
                "result_room_resref": result_room_resref,
            },
        )
        return self.authored_module_readiness()

    def set_authored_floor_plan_extrusion(
        self,
        *,
        room_resref: str = "",
        z: float | None = None,
        wall_height: float | None = None,
        include_walls: bool | None = None,
        floor_surface_id: int | str | None = None,
    ):
        """Set explicit room extrusion parameters for the current authored KMAP module."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        before = self._capture_map_studio_command_state()
        updated = set_authored_floor_plan_extrusion_settings(
            authored,
            room_resref=room_resref,
            z=z,
            wall_height=wall_height,
            include_walls=include_walls,
            floor_surface_id=floor_surface_id,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Updated Map Studio floor-plan extrusion settings for {room_resref or 'the selected room'}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.set_extrusion",
            label=f"Set {room_resref or 'room'} extrusion",
            before=before,
            metadata={
                "room_resref": room_resref,
                "z": z,
                "wall_height": wall_height,
                "include_walls": include_walls,
                "floor_surface_id": floor_surface_id,
            },
        )
        return self.authored_module_readiness()

    def move_authored_room_outline_point(self, *, room_resref: str, point_index: int, world_position: Any):
        """Move one authored room outline vertex through the headless floor-plan operation."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        updated = move_authored_floor_plan_point(
            authored,
            room_resref=room_resref,
            point_index=int(point_index),
            world_position=tuple(world_position),
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Moved Map Studio room {room_resref or '(first room)'} outline point {int(point_index)}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.move_vertex",
            label=f"Move {room_resref or 'room'} outline point {int(point_index)}",
            before=before,
            metadata={"room_resref": room_resref, "point_index": int(point_index), "world_position": tuple(world_position)},
        )
        return self.authored_module_readiness()

    def authored_floor_plan_vertex_snap_candidates(
        self,
        *,
        room_resref: str,
        point_index: int,
        max_distance: float | None = None,
        include_same_room: bool = True,
        include_cross_room: bool = True,
        limit: int = 8,
    ):
        """Return nearest floor-plan vertex snap targets without mutating project state."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        return authored_floor_plan_vertex_snap_candidates(
            authored,
            room_resref=room_resref,
            point_index=int(point_index),
            max_distance=max_distance,
            include_same_room=bool(include_same_room),
            include_cross_room=bool(include_cross_room),
            limit=int(limit),
        )

    def snap_authored_floor_plan_vertex(
        self,
        *,
        room_resref: str,
        point_index: int,
        target_point_index: int,
        target_room_resref: str = "",
    ):
        """Snap one authored floor-plan vertex to another through the domain operation."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        updated = snap_authored_floor_plan_vertex_to_vertex(
            authored,
            room_resref=room_resref,
            point_index=int(point_index),
            target_point_index=int(target_point_index),
            target_room_resref=target_room_resref,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Snapped Map Studio room {room_resref or '(first room)'} point {int(point_index)} to point {int(target_point_index)}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.snap_vertex",
            label=f"Snap {room_resref or 'room'} point {int(point_index)}",
            before=before,
            metadata={
                "room_resref": room_resref,
                "point_index": int(point_index),
                "target_point_index": int(target_point_index),
                "target_room_resref": target_room_resref,
            },
        )
        return self.authored_module_readiness()

    def grid_snap_authored_floor_plan_vertices(
        self,
        *,
        room_resref: str,
        point_indices: Any,
        grid_size: float = 0.1,
        axes: Any = ("x", "y"),
    ):
        """Snap authored floor-plan vertices to grid through the domain operation."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        indices = tuple(int(index) for index in tuple(point_indices or ()))
        axes_tuple = tuple(str(axis or "").strip().lower() for axis in tuple(axes or ("x", "y")))
        updated = grid_snap_authored_floor_plan_vertices(
            authored,
            room_resref=room_resref,
            point_indices=indices,
            grid_size=float(grid_size),
            axes=axes_tuple,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Grid-snapped Map Studio room {room_resref or '(first room)'} floor-plan vertices {indices} to {float(grid_size):g}m; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.grid_snap_vertices",
            label=f"Grid snap {room_resref or 'room'} vertices",
            before=before,
            metadata={"room_resref": room_resref, "point_indices": indices, "grid_size": float(grid_size), "axes": axes_tuple},
        )
        return self.authored_module_readiness()

    def weld_authored_floor_plan_vertices(
        self,
        *,
        room_resref: str,
        point_indices: Any,
        target_point_index: int | None = None,
        position_policy: str = "target",
    ):
        """Weld authored floor-plan vertices through the domain operation."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        indices = tuple(int(index) for index in tuple(point_indices or ()))
        updated = weld_authored_floor_plan_vertices(
            authored,
            room_resref=room_resref,
            point_indices=indices,
            target_point_index=target_point_index,
            position_policy=position_policy,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Welded Map Studio room {room_resref or '(first room)'} floor-plan vertices {indices}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.weld_vertices",
            label=f"Weld {room_resref or 'room'} vertices",
            before=before,
            metadata={
                "room_resref": room_resref,
                "point_indices": indices,
                "target_point_index": target_point_index,
                "position_policy": position_policy,
            },
        )
        return self.authored_module_readiness()

    def flatten_authored_floor_plan_vertices(
        self,
        *,
        room_resref: str,
        point_indices: Any,
        axis: str = "x",
        value: float | None = None,
    ):
        """Flatten authored floor-plan vertices through the domain operation."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        indices = tuple(int(index) for index in tuple(point_indices or ()))
        updated = flatten_authored_floor_plan_vertices(
            authored,
            room_resref=room_resref,
            point_indices=indices,
            axis=axis,
            value=value,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Flattened Map Studio room {room_resref or '(first room)'} floor-plan vertices {indices} on {axis}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.flatten_vertices",
            label=f"Flatten {room_resref or 'room'} vertices on {axis}",
            before=before,
            metadata={"room_resref": room_resref, "point_indices": indices, "axis": axis, "value": value},
        )
        return self.authored_module_readiness()

    def transform_snap_authored_floor_plan_vertices(
        self,
        *,
        room_resref: str,
        point_indices: Any,
        axis: str = "x",
        target_point_index: int | None = None,
        value: float | None = None,
        level_policy: str = "average",
    ):
        """Apply hold-J transform level snapping through the domain operation."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        indices = tuple(int(index) for index in tuple(point_indices or ()))
        updated = transform_snap_authored_floor_plan_vertices(
            authored,
            room_resref=room_resref,
            point_indices=indices,
            axis=axis,
            target_point_index=target_point_index,
            value=value,
            level_policy=level_policy,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Transform-snapped Map Studio room {room_resref or '(first room)'} floor-plan vertices {indices} on {axis}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.transform_snap_level",
            label=f"Transform snap {room_resref or 'room'} vertices on {axis}",
            before=before,
            metadata={
                "room_resref": room_resref,
                "point_indices": indices,
                "axis": axis,
                "target_point_index": target_point_index,
                "value": value,
                "level_policy": level_policy,
            },
        )
        return self.authored_module_readiness()

    def cleanup_authored_floor_plan_vertices(
        self,
        *,
        room_resref: str,
        tolerance: float = 0.001,
    ):
        """Cleanup redundant authored floor-plan vertices through the domain operation."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        updated = cleanup_authored_floor_plan_vertices(
            authored,
            room_resref=room_resref,
            tolerance=float(tolerance),
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Cleaned Map Studio room {room_resref or '(first room)'} floor-plan vertices; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.cleanup_vertices",
            label=f"Clean {room_resref or 'room'} floor-plan vertices",
            before=before,
            metadata={"room_resref": room_resref, "tolerance": float(tolerance)},
        )
        return self.authored_module_readiness()

    def fill_authored_floor_plan_face(
        self,
        *,
        room_resref: str,
        point_indices: Any,
    ):
        """Fill a floor-plan point loop through the domain operation."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        indices = tuple(int(index) for index in tuple(point_indices or ()))
        updated = fill_authored_floor_plan_face(
            authored,
            room_resref=room_resref,
            point_indices=indices,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Filled Map Studio room {room_resref or '(first room)'} floor-plan face loop {indices}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.fill_face",
            label=f"Fill {room_resref or 'room'} floor-plan face",
            before=before,
            metadata={"room_resref": room_resref, "point_indices": indices},
        )
        return self.authored_module_readiness()

    def triangulate_authored_floor_plan_face(
        self,
        *,
        room_resref: str,
    ):
        """Triangulate a floor-plan footprint through the domain operation."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        updated = triangulate_authored_floor_plan_face(
            authored,
            room_resref=room_resref,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Triangulated Map Studio room {room_resref or '(first room)'} floor-plan face; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.triangulate_face",
            label=f"Triangulate {room_resref or 'room'} floor-plan face",
            before=before,
            metadata={"room_resref": room_resref},
        )
        return self.authored_module_readiness()

    def split_authored_floor_plan_face(
        self,
        *,
        room_resref: str,
        point_indices: Any,
    ):
        """Record a selected-vertex face split through the domain operation."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        indices = tuple(int(index) for index in tuple(point_indices or ()))
        updated = split_authored_floor_plan_face(
            authored,
            room_resref=room_resref,
            point_indices=indices,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Split Map Studio room {room_resref or '(first room)'} floor-plan face between points {indices}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.split_face",
            label=f"Split {room_resref or 'room'} floor-plan face",
            before=before,
            metadata={"room_resref": room_resref, "point_indices": indices},
        )
        return self.authored_module_readiness()

    def cleanup_authored_floor_plan_normals(
        self,
        *,
        room_resref: str,
        positive_z: bool = True,
    ):
        """Clean floor-plan face winding through the domain operation."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        updated = cleanup_authored_floor_plan_normals(
            authored,
            room_resref=room_resref,
            positive_z=bool(positive_z),
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Cleaned Map Studio room {room_resref or '(first room)'} floor-plan normals; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.cleanup_normals",
            label=f"Clean {room_resref or 'room'} floor-plan normals",
            before=before,
            metadata={"room_resref": room_resref, "positive_z": bool(positive_z)},
        )
        return self.authored_module_readiness()

    def mirror_authored_floor_plan_vertices(
        self,
        *,
        room_resref: str,
        axis: str = "x",
    ):
        """Mirror an authored floor-plan footprint through the domain operation."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        updated = mirror_authored_floor_plan_vertices(
            authored,
            room_resref=room_resref,
            axis=axis,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Mirrored Map Studio room {room_resref or '(first room)'} floor-plan across local {axis}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.floor_plan.mirror_vertices",
            label=f"Mirror {room_resref or 'room'} floor-plan on {axis}",
            before=before,
            metadata={"room_resref": room_resref, "axis": axis},
        )
        return self.authored_module_readiness()

    def set_authored_room_primitive_transform(
        self,
        *,
        room_resref: str,
        primitive_name: str,
        translation: Any = None,
        rotation_degrees_z: float | None = None,
        scale: Any = None,
        pivot: Any = None,
    ):
        """Set one authored composition primitive transform in the current KMAP module."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        updated = set_authored_room_composition_primitive_transform(
            authored,
            room_resref=room_resref,
            primitive_name=primitive_name,
            translation=translation,
            rotation_degrees_z=rotation_degrees_z,
            scale=scale,
            pivot=pivot,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Transformed Map Studio room primitive {primitive_name} in {room_resref or '(first room)'}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.primitive.transform",
            label=f"Transform primitive {primitive_name}",
            before=before,
            metadata={
                "room_resref": room_resref,
                "primitive_name": primitive_name,
                "translation": translation,
                "rotation_degrees_z": rotation_degrees_z,
                "scale": scale,
                "pivot": pivot,
            },
        )
        return self.authored_module_readiness()

    def move_authored_room_primitive(self, *, room_resref: str, primitive_name: str, world_delta: Any):
        """Move one authored composition primitive by a viewport-authored world delta."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        updated = move_authored_room_composition_primitive(
            authored,
            room_resref=room_resref,
            primitive_name=primitive_name,
            world_delta=world_delta,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Moved Map Studio room primitive {primitive_name}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.primitive.move",
            label=f"Move primitive {primitive_name}",
            before=before,
            metadata={"room_resref": room_resref, "primitive_name": primitive_name, "world_delta": world_delta},
        )
        return self.authored_module_readiness()

    def duplicate_authored_room_primitive(
        self,
        *,
        room_resref: str,
        primitive_name: str,
        duplicate_count: int = 1,
        translation_offset: Any = (1.0, 0.0, 0.0),
        rotation_offset_degrees_z: float = 0.0,
        scale_multiplier: Any = (1.0, 1.0, 1.0),
    ):
        """Duplicate one authored composition primitive with repeatable transform offsets."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        updated = duplicate_authored_room_composition_primitive(
            authored,
            room_resref=room_resref,
            primitive_name=primitive_name,
            duplicate_count=duplicate_count,
            translation_offset=translation_offset,
            rotation_offset_degrees_z=rotation_offset_degrees_z,
            scale_multiplier=scale_multiplier,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Duplicated Map Studio room primitive {primitive_name} {int(duplicate_count)} time(s); previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.primitive.duplicate_special",
            label=f"Duplicate primitive {primitive_name}",
            before=before,
            metadata={
                "room_resref": room_resref,
                "primitive_name": primitive_name,
                "duplicate_count": int(duplicate_count),
                "translation_offset": translation_offset,
                "rotation_offset_degrees_z": rotation_offset_degrees_z,
                "scale_multiplier": scale_multiplier,
            },
        )
        return self.authored_module_readiness()

    def add_authored_room_primitive(
        self,
        *,
        primitive_kind: str,
        room_resref: str = "",
        primitive_name: str = "",
        translation: Any = None,
        rotation_degrees_z: float | None = None,
        scale: Any = None,
        pivot: Any = None,
        texture: str = "",
        floor_surface: Any = None,
    ):
        """Append a primitive instance to an authored composition room."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        updated = add_authored_room_composition_primitive(
            authored,
            primitive_kind=primitive_kind,
            room_resref=room_resref,
            primitive_name=primitive_name,
            translation=translation,
            rotation_degrees_z=rotation_degrees_z,
            scale=scale,
            pivot=pivot,
            texture=texture,
            floor_surface=floor_surface,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Added Map Studio room primitive {primitive_kind} {primitive_name or '(auto-named)'}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.primitive.add",
            label=f"Add {primitive_kind} primitive",
            before=before,
            metadata={
                "primitive_kind": primitive_kind,
                "room_resref": room_resref,
                "primitive_name": primitive_name,
                "translation": translation,
                "rotation_degrees_z": rotation_degrees_z,
                "scale": scale,
                "pivot": pivot,
                "texture": texture,
                "floor_surface": floor_surface,
            },
        )
        return self.authored_module_readiness()

    def set_authored_room_primitive_dimensions(
        self,
        *,
        room_resref: str,
        primitive_name: str,
        dimensions: Any,
    ):
        """Set editable dimensions for one authored composition primitive."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        updated = set_authored_room_composition_primitive_dimensions(
            authored,
            room_resref=room_resref,
            primitive_name=primitive_name,
            dimensions=dimensions,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Edited Map Studio room primitive dimensions for {primitive_name}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.primitive.set_dimensions",
            label=f"Set dimensions for primitive {primitive_name}",
            before=before,
            metadata={"room_resref": room_resref, "primitive_name": primitive_name, "dimensions": dimensions},
        )
        return self.authored_module_readiness()

    def set_authored_room_primitive_style(
        self,
        *,
        room_resref: str,
        primitive_name: str,
        texture: str = "",
        surface_id: Any = None,
    ):
        """Set material and optional WOK surface intent for one composition primitive."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        updated = set_authored_room_composition_primitive_style(
            authored,
            room_resref=room_resref,
            primitive_name=primitive_name,
            texture=texture,
            surface_id=surface_id,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Styled Map Studio room primitive {primitive_name}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.primitive.set_style",
            label=f"Style primitive {primitive_name}",
            before=before,
            metadata={"room_resref": room_resref, "primitive_name": primitive_name, "texture": texture, "surface_id": surface_id},
        )
        return self.authored_module_readiness()

    def set_authored_room_edge_normal_policy(
        self,
        *,
        room_resref: str = "",
        policy: str,
        primitive_name: str = "",
        edge_indices: Any = None,
    ):
        """Record soft/hard edge-normal intent for authored Map Studio geometry."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        updated = set_authored_room_edge_normal_policy(
            authored,
            room_resref=room_resref,
            policy=policy,
            primitive_name=primitive_name,
            edge_indices=edge_indices,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        normal_policy = str(policy or "").strip().lower()
        label_word = "Soften" if normal_policy.startswith("soft") else "Harden"
        self.model.log(
            f"{label_word}ed Map Studio visual edge-normal policy for {room_resref or '(first room)'}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.edge_normals.set_policy",
            label=f"{label_word} edges",
            before=before,
            metadata={
                "room_resref": room_resref,
                "policy": policy,
                "primitive_name": primitive_name,
                "edge_indices": tuple(edge_indices or ()),
            },
        )
        return self.authored_module_readiness()

    def remove_authored_room_primitive(self, *, room_resref: str, primitive_name: str):
        """Remove one authored composition primitive from the current KMAP module."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        updated = remove_authored_room_composition_primitive(
            authored,
            room_resref=room_resref,
            primitive_name=primitive_name,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        self.model.log(
            f"Removed Map Studio room primitive {primitive_name}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.primitive.remove",
            label=f"Remove primitive {primitive_name}",
            before=before,
            metadata={"room_resref": room_resref, "primitive_name": primitive_name},
        )
        return self.authored_module_readiness()

    def separate_authored_room_primitive(
        self,
        *,
        room_resref: str,
        primitive_name: str,
        result_room_resref: str = "",
    ):
        """Separate one authored composition primitive into a new room/object boundary."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        updated = separate_authored_room_composition_primitive(
            authored,
            room_resref=room_resref,
            primitive_name=primitive_name,
            result_room_resref=result_room_resref,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(updated)
        self.project.name = updated.metadata.module_root
        self.project.game = updated.game
        self.project.dirty = True
        separated_room = str(updated.extra.get("last_room_operation", "")).rsplit(":", 1)[-1]
        self.model.log(
            f"Separated Map Studio room primitive {primitive_name} into {separated_room}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.primitive.separate",
            label=f"Separate primitive {primitive_name}",
            before=before,
            metadata={
                "room_resref": room_resref,
                "primitive_name": primitive_name,
                "result_room_resref": result_room_resref,
                "separated_room": separated_room,
            },
        )
        return self.authored_module_readiness()

    def apply_authored_room_style(self, *, texture: str = "", floor_surface: Any = 4, room_resref: str = ""):
        """Apply room texture and WOK surface intent to the current authored KMAP module."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        before = self._capture_map_studio_command_state()
        update = update_authored_room_style(
            authored,
            texture=texture,
            floor_surface=floor_surface,
            room_resref=room_resref,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(update.project)
        self.project.name = update.project.metadata.module_root
        self.project.game = update.project.game
        self.project.dirty = True
        self.model.log(
            f"Applied Map Studio room style texture {update.texture}, surface {update.floor_surface_id} ({update.floor_surface_name})."
        )
        for warning in update.warnings:
            self.model.log(f"Warning: {warning}")
        self._record_map_studio_command(
            action_key="map_studio.room.set_style",
            label=f"Style {room_resref or 'room'}",
            before=before,
            metadata={"texture": texture, "floor_surface": floor_surface, "room_resref": room_resref},
        )
        return self.authored_module_readiness()

    def set_authored_room_walkmesh_surface(self, *, room_resref: str, floor_surface: Any = 4):
        """Apply only the room WOK surface from Walkmesh tools, preserving texture intent."""

        target = normalise_resref(room_resref)
        texture = ""
        for choice in self.authored_walkmesh_room_surface_choices():
            if normalise_resref(getattr(choice, "room_resref", "")) == target:
                texture = str(getattr(choice, "texture", "") or "")
                break
        return self.apply_authored_room_style(texture=texture, floor_surface=floor_surface, room_resref=room_resref)

    def add_authored_gameplay_placement(
        self,
        *,
        kind: str,
        template_resref: str = "",
        tag: str = "",
        position: Any = (0.0, 0.0, 0.0),
        bearing: float = 0.0,
    ):
        """Append a gameplay object placement to the current authored KMAP module."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        before = self._capture_map_studio_command_state()
        update = add_authored_gameplay_placement(
            authored,
            kind=kind,
            template_resref=template_resref,
            tag=tag,
            position=position,
            bearing=bearing,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(update.project)
        self.project.name = update.project.metadata.module_root
        self.project.game = update.project.game
        self.project.dirty = True
        self.model.log(
            f"Added Map Studio {update.kind} placement {update.tag} at {update.position}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.gameplay.add_placement",
            label=f"Add {update.kind} placement {update.tag}",
            before=before,
            metadata={
                "kind": update.kind,
                "template_resref": update.template_resref,
                "tag": update.tag,
                "position": update.position,
                "placement_id": update.placement_id,
            },
        )
        return self.authored_module_readiness()

    def set_authored_module_entry_point(
        self,
        *,
        area_resref: str = "",
        position: Any = (0.0, 0.0, 0.0),
        facing: float = 0.0,
    ):
        """Edit the module IFO entry point/player start for the authored KMAP."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        before = self._capture_map_studio_command_state()
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        update = update_authored_module_entry_point(
            authored,
            area_resref=area_resref,
            position=position,
            facing=facing,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(update.project)
        self.project.name = update.project.metadata.module_root
        self.project.game = update.project.game
        self.project.dirty = True
        self.model.log(
            f"Updated Map Studio module entry point {update.area_resref} at {update.position}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.gameplay.set_entry_point",
            label=f"Set entry point {update.area_resref}",
            before=before,
            metadata={
                "area_resref": update.area_resref,
                "position": update.position,
                "facing": update.facing,
            },
        )
        return self.authored_module_readiness()

    def add_authored_room_light(
        self,
        *,
        room_resref: str = "",
        name: str = "",
        position: Any = (0.0, 0.0, 2.25),
        color: Any = (1.0, 0.92, 0.78),
        radius: float = 8.0,
        intensity: float = 1.0,
        light_type: str = "point",
    ):
        """Append room-light authoring intent to the current authored KMAP module."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        before = self._capture_map_studio_command_state()
        update = add_authored_room_light_to_project(
            authored,
            room_resref=room_resref,
            name=name,
            position=position,
            color=color,
            radius=radius,
            intensity=intensity,
            light_type=light_type,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(update.project)
        self.project.name = update.project.metadata.module_root
        self.project.game = update.project.game
        self.project.dirty = True
        self.model.log(
            f"Added Map Studio {update.light.light_type} room light {update.light.name} in {update.light.room_resref}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.lighting.add_room_light",
            label=f"Add room light {update.light.name}",
            before=before,
            metadata={
                "light_id": update.light_id,
                "room_resref": update.light.room_resref,
                "name": update.light.name,
                "position": update.light.position,
                "color": update.light.color,
                "radius": update.light.radius,
                "intensity": update.light.intensity,
                "light_type": update.light.light_type,
            },
        )
        return self.authored_module_readiness()

    def set_authored_gameplay_placement_transform(self, placement_id: str, *, position: Any, bearing: float | None = None):
        """Move one authored gameplay placement by virtual id."""

        parse_authored_gameplay_placement_id(placement_id)
        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        update = update_authored_gameplay_placement_transform(
            authored,
            placement_id,
            position=position,
            bearing=bearing,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(update.project)
        self.project.name = update.project.metadata.module_root
        self.project.game = update.project.game
        self.project.dirty = True
        self.model.log(
            f"Moved Map Studio {update.kind} placement {update.tag} to {update.position}; previous exports/proofs are now stale."
        )
        return self.authored_module_readiness()

    def rename_authored_gameplay_placement(self, placement_id: str, *, tag: Any):
        """Rename one authored gameplay placement by virtual id."""

        parse_authored_gameplay_placement_id(placement_id)
        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        update = rename_authored_gameplay_placement(authored, placement_id, tag=tag)
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(update.project)
        self.project.name = update.project.metadata.module_root
        self.project.game = update.project.game
        self.project.dirty = True
        self.model.log(
            f"Renamed Map Studio {update.kind} placement to {update.tag}; previous exports/proofs are now stale."
        )
        return update

    def duplicate_authored_gameplay_placement(self, placement_id: str):
        """Duplicate one authored gameplay placement by virtual id."""

        parse_authored_gameplay_placement_id(placement_id)
        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        update = duplicate_authored_gameplay_placement(authored, placement_id)
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(update.project)
        self.project.name = update.project.metadata.module_root
        self.project.game = update.project.game
        self.project.dirty = True
        self.model.log(
            f"Duplicated Map Studio {update.kind} placement {update.tag}; previous exports/proofs are now stale."
        )
        return update

    def remove_authored_gameplay_placement(self, placement_id: str):
        """Remove one authored gameplay placement by virtual id."""

        parse_authored_gameplay_placement_id(placement_id)
        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        update = remove_authored_gameplay_placement(authored, placement_id)
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(update.project)
        self.project.name = update.project.metadata.module_root
        self.project.game = update.project.game
        self.project.dirty = True
        self.model.log(
            f"Removed Map Studio {update.kind} placement {update.tag}; previous exports/proofs are now stale."
        )
        return update

    def set_authored_gameplay_camera_properties(
        self,
        placement_id: str,
        *,
        camera_id: Any | None = None,
        field_of_view: Any | None = None,
        height: Any | None = None,
        mic_range: Any | None = None,
        pitch: Any | None = None,
    ):
        """Edit selected authored camera GIT CameraList fields from Properties."""

        parse_authored_gameplay_placement_id(placement_id)
        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        update = update_authored_gameplay_camera_properties(
            authored,
            placement_id,
            camera_id=camera_id,
            field_of_view=field_of_view,
            height=height,
            mic_range=mic_range,
            pitch=pitch,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(update.project)
        self.project.name = update.project.metadata.module_root
        self.project.game = update.project.game
        self.project.dirty = True
        self.model.log(
            f"Edited Map Studio camera {update.tag}; previous exports/proofs are now stale."
        )
        return self.authored_module_readiness()

    def set_authored_gameplay_transition(
        self,
        placement_id: str,
        *,
        linked_to: Any = "",
        linked_to_module: Any = "",
        transition_destination: Any = 0,
    ):
        """Set transition destination fields on a selected authored door/trigger/waypoint."""

        parse_authored_gameplay_placement_id(placement_id)
        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        update = update_authored_gameplay_transition(
            authored,
            placement_id,
            linked_to=linked_to,
            linked_to_module=linked_to_module,
            transition_destination=transition_destination,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(update.project)
        self.project.name = update.project.metadata.module_root
        self.project.game = update.project.game
        self.project.dirty = True
        self.model.log(
            f"Updated Map Studio {update.kind} transition for {update.tag}; previous exports/proofs are now stale."
        )
        return self.authored_module_readiness()

    def set_authored_room_light_transform(self, light_id: str, *, position: Any):
        """Move one authored room light by virtual id."""

        parse_authored_room_light_id(light_id)
        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        update = update_authored_room_light_transform(authored, light_id, position=position)
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(update.project)
        self.project.name = update.project.metadata.module_root
        self.project.game = update.project.game
        self.project.dirty = True
        self.model.log(
            f"Moved Map Studio room light {update.light.name} to {update.light.position}; previous exports/proofs are now stale."
        )
        return self.authored_module_readiness()

    def set_authored_room_light_properties(
        self,
        light_id: str,
        *,
        color: Any | None = None,
        radius: float | None = None,
        intensity: float | None = None,
        light_type: Any | None = None,
    ):
        """Edit selected authored room-light settings from the properties panel."""

        parse_authored_room_light_id(light_id)
        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        update = update_authored_room_light_properties(
            authored,
            light_id,
            color=color,
            radius=radius,
            intensity=intensity,
            light_type=light_type,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(update.project)
        self.project.name = update.project.metadata.module_root
        self.project.game = update.project.game
        self.project.dirty = True
        self.model.log(
            f"Edited Map Studio room light {update.light.name}; previous exports/proofs are now stale."
        )
        return self.authored_module_readiness()

    def rename_authored_room_light(self, light_id: str, *, name: Any):
        """Rename one authored room light by virtual id."""

        parse_authored_room_light_id(light_id)
        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        update = rename_authored_room_light(authored, light_id, name=name)
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(update.project)
        self.project.name = update.project.metadata.module_root
        self.project.game = update.project.game
        self.project.dirty = True
        self.model.log(
            f"Renamed Map Studio room light to {update.light.name}; previous exports/proofs are now stale."
        )
        return update

    def duplicate_authored_room_light(self, light_id: str):
        """Duplicate one authored room light by virtual id."""

        parse_authored_room_light_id(light_id)
        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        update = duplicate_authored_room_light(authored, light_id)
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(update.project)
        self.project.name = update.project.metadata.module_root
        self.project.game = update.project.game
        self.project.dirty = True
        self.model.log(
            f"Duplicated Map Studio room light {update.light.name}; previous exports/proofs are now stale."
        )
        return update

    def remove_authored_room_light(self, light_id: str):
        """Remove one authored room light by virtual id."""

        parse_authored_room_light_id(light_id)
        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        update = remove_authored_room_light(authored, light_id)
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(update.project)
        self.project.name = update.project.metadata.module_root
        self.project.game = update.project.game
        self.project.dirty = True
        self.model.log(
            f"Removed Map Studio room light {update.light.name}; previous exports/proofs are now stale."
        )
        return update

    def set_authored_script_hook(self, *, scope: Any, field_name: Any, script_resref: Any):
        """Assign one authored module/area script hook in the current KMAP payload."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        before = self._capture_map_studio_command_state()
        update = set_authored_script_hook(
            authored,
            scope=scope,
            field_name=field_name,
            script_resref=script_resref,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(update.project)
        self.project.name = update.project.metadata.module_root
        self.project.game = update.project.game
        self.project.dirty = True
        self.model.log(
            f"Assigned Map Studio {update.scope} script hook {update.field_name} -> {update.script_resref}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.script.set_hook",
            label=f"Set {update.scope} script {update.field_name}",
            before=before,
            metadata={
                "scope": update.scope,
                "field_name": update.field_name,
                "script_resref": update.script_resref,
            },
        )
        return update

    def remove_authored_script_hook(self, *, scope: Any, field_name: Any):
        """Clear one authored module/area script hook in the current KMAP payload."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        before = self._capture_map_studio_command_state()
        update = remove_authored_script_hook(
            authored,
            scope=scope,
            field_name=field_name,
        )
        self.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(update.project)
        self.project.name = update.project.metadata.module_root
        self.project.game = update.project.game
        self.project.dirty = True
        self.model.log(
            f"Cleared Map Studio {update.scope} script hook {update.field_name}; previous exports/proofs are now stale."
        )
        self._record_map_studio_command(
            action_key="map_studio.script.remove_hook",
            label=f"Clear {update.scope} script {update.field_name}",
            before=before,
            metadata={
                "scope": update.scope,
                "field_name": update.field_name,
                "script_resref": update.script_resref,
            },
        )
        return update

    def build_preview(self, output_dir: str | Path):
        return self.builder_service.build_preview(self.project, output_dir)

    def stage_dev_test_module(self, output_dir: str | Path, *, dry_run: bool = False, overwrite: bool = False):
        """Stage the first from-scratch Map Studio smoke module package."""

        output_path = Path(output_dir)
        game = str(self.project.game or "K1").upper()
        return prepare_dev_test_module_install(
            DevModuleInstallPrepRequest(
                output_dir=str(output_path),
                game=game,
                dry_run=dry_run,
                overwrite=overwrite,
                smoke_request=DevModuleSmokeRequest(
                    output_dir=str(output_path),
                    game=game,
                ),
            )
        )

    def export_authored_module(self, output_dir: str | Path, *, dry_run: bool = False, overwrite: bool = False):
        """Export the authored module currently stored in the KMAP project."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        output_path = Path(output_dir)
        result = export_authored_module_project(
            AuthoredModuleExportRequest(
                project=authored,
                output_dir=str(output_path),
                dry_run=dry_run,
                strict=not dry_run,
            )
        )
        if not dry_run and result.resources:
            runtime_resources = [f"{item.resref}.{item.restype}" for item in result.resources]
            payload = dict(payload)
            payload["runtime_resources"] = runtime_resources
            payload["game_tested"] = False
            payload["pack_manifest_path"] = result.manifest_path
            manifest = _read_json_object(result.manifest_path)
            authored_manifest = manifest.get("map_studio_authored_module")
            if isinstance(authored_manifest, dict):
                test_plan = authored_manifest.get("modder_test_plan")
                if isinstance(test_plan, dict):
                    payload["modder_test_plan"] = test_plan
            self.project.extra_sections["authored_module"] = payload
            self.project.dirty = True
        self.model.log(result.message)
        return result

    def stage_authored_module(
        self,
        output_dir: str | Path,
        *,
        dry_run: bool = False,
        overwrite: bool = False,
        game_modules_dir: str | Path = "",
        auto_detect_game_modules_dir: bool = False,
    ):
        """Stage the current authored KMAP module with a manual game-test checklist."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(self.project, "name", "") or "new_level"),
            fallback_game=str(getattr(self.project, "game", "") or "K1"),
        )
        output_path = Path(output_dir)
        result = prepare_authored_module_install(
            AuthoredModuleInstallPrepRequest(
                project=authored,
                output_dir=str(output_path),
                game_modules_dir=str(game_modules_dir or ""),
                dry_run=dry_run,
                overwrite=overwrite,
                auto_detect_game_modules_dir=bool(auto_detect_game_modules_dir),
            )
        )
        export_result = result.export_result
        if export_result is not None and export_result.resources:
            runtime_resources = [f"{item.resref}.{item.restype}" for item in export_result.resources]
            payload = dict(payload)
            payload["runtime_resources"] = runtime_resources
            payload["game_tested"] = False
            payload["proof_manifest_path"] = result.proof_manifest_path
            payload["checklist_path"] = result.checklist_path
            payload["resolved_modules_dir"] = result.resolved_modules_dir
            payload["resolved_game_root_dir"] = result.resolved_game_root_dir
            payload["launch_helper_command"] = result.launch_helper_command
            payload["elevated_launch_script_path"] = result.elevated_launch_script_path
            payload["proof_recording_script_path"] = result.proof_recording_script_path
            payload["installed_module_path"] = result.installed_module_path
            payload["backup_module_path"] = result.backup_module_path
            payload["pack_manifest_path"] = export_result.manifest_path
            proof_manifest = _read_json_object(result.proof_manifest_path)
            test_plan = proof_manifest.get("modder_test_plan")
            if isinstance(test_plan, dict):
                payload["modder_test_plan"] = test_plan
            self.project.extra_sections["authored_module"] = payload
            self.project.dirty = True
        self.model.log(result.message)
        return result

    def map_studio_launch_handoff(self) -> MapStudioLaunchHandoffSummary:
        """Describe the current manual KOTOR launch/proof handoff without mutating project state."""

        payload = dict((getattr(self.project, "extra_sections", {}) or {}).get("authored_module") or {})
        module_root = str(payload.get("module_root") or getattr(self.project, "name", "") or "").strip()
        game = str(payload.get("game") or getattr(self.project, "game", "") or "K1").strip().upper()
        warp_command = str(payload.get("warp_command") or (f"warp {module_root}" if module_root else "warp <module>")).strip()
        proof_manifest_path = str(payload.get("proof_manifest_path") or "").strip()
        proof_recording_script_path = str(payload.get("proof_recording_script_path") or "").strip()
        launch_helper_command = str(payload.get("launch_helper_command") or "").strip()
        elevated_launch_script_path = str(payload.get("elevated_launch_script_path") or "").strip()
        installed_module_path = str(payload.get("installed_module_path") or "").strip()
        checklist_path = str(payload.get("checklist_path") or "").strip()
        resolved_modules_dir = str(payload.get("resolved_modules_dir") or "").strip()
        resolved_game_root_dir = str(payload.get("resolved_game_root_dir") or "").strip()

        blocking: list[str] = []
        warnings: list[str] = []
        if not payload:
            blocking.append("No authored Map Studio module has been staged for a launch handoff.")
        if proof_manifest_path:
            if not Path(proof_manifest_path).is_file():
                blocking.append(f"Proof manifest does not exist: {proof_manifest_path}")
        elif not elevated_launch_script_path:
            blocking.append("Stage or install the authored module before opening the launch handoff.")
        if elevated_launch_script_path and not Path(elevated_launch_script_path).is_file():
            warnings.append(f"Launch script is not available on disk: {elevated_launch_script_path}")
        if proof_recording_script_path and not Path(proof_recording_script_path).is_file():
            warnings.append(f"Proof recorder is not available on disk: {proof_recording_script_path}")
        if checklist_path and not Path(checklist_path).is_file():
            warnings.append(f"Game-test checklist is not available on disk: {checklist_path}")
        if installed_module_path and not Path(installed_module_path).exists():
            warnings.append(f"Installed module candidate is not present on disk: {installed_module_path}")
        if not module_root:
            warnings.append("Module root is unknown; the warp command must be checked before launch.")
        if not launch_helper_command:
            warnings.append("No CLI launch helper command was recorded; use the proof manifest and warp command manually.")

        ready = len(blocking) == 0
        summary = (
            f"Launch handoff ready for {game}:{module_root or '<module>'}; run {warp_command} and record proof."
            if ready
            else "Launch handoff is not ready; stage or install an authored module package first."
        )
        next_action = (
            "Open the launcher/proof folder, run the exact KOTOR warp command, then record screenshot or video proof."
            if ready
            else "Stage .mod or Install Test from Map Studio export tools before launching."
        )
        return MapStudioLaunchHandoffSummary(
            ready=ready,
            module_root=module_root,
            game=game,
            warp_command=warp_command,
            launcher_path=elevated_launch_script_path,
            proof_manifest_path=proof_manifest_path,
            proof_recording_script_path=proof_recording_script_path,
            launch_helper_command=launch_helper_command,
            elevated_launch_script_path=elevated_launch_script_path,
            installed_module_path=installed_module_path,
            checklist_path=checklist_path,
            resolved_modules_dir=resolved_modules_dir,
            resolved_game_root_dir=resolved_game_root_dir,
            warnings=tuple(warnings),
            blocking_messages=tuple(blocking),
            summary=summary,
            next_action=next_action,
        )

    def map_studio_game_proof_recording_handoff(self) -> MapStudioGameProofRecordingSummary:
        """Return default proof-recording inputs without mutating project state."""

        launch = self.map_studio_launch_handoff()
        proof_manifest_path = str(getattr(launch, "proof_manifest_path", "") or "").strip()
        warnings = list(getattr(launch, "warnings", ()) or ())
        blocking = list(getattr(launch, "blocking_messages", ()) or ())
        if proof_manifest_path and not Path(proof_manifest_path).is_file():
            if not any(proof_manifest_path in item for item in blocking):
                blocking.append(f"Proof manifest does not exist: {proof_manifest_path}")
        if not proof_manifest_path:
            blocking.append("Choose the proof manifest written by Stage .mod or Install Test before recording game proof.")
        required_checks = (
            "`warp` loads the generated module in KOTOR",
            "Player appears on the generated floor, not in void",
            "Authored/test placeable appears where expected",
            "Player can walk across the generated floor",
            "Screenshot or video evidence is attached",
        )
        ready = len(blocking) == 0
        summary = (
            f"Proof recording ready for {launch.game}:{launch.module_root or '<module>'}; attach screenshot or video evidence."
            if ready
            else "Proof recording needs a staged Map Studio proof manifest before it can mark the module game-tested."
        )
        next_action = (
            "Select the KOTOR screenshot/video evidence, confirm the in-game checks, then record proof."
            if ready
            else "Use Stage .mod or Install Test first, or browse to an existing proof manifest in the Record Proof dialog."
        )
        return MapStudioGameProofRecordingSummary(
            ready=ready,
            module_root=launch.module_root,
            game=launch.game,
            warp_command=launch.warp_command,
            proof_manifest_path=proof_manifest_path,
            required_checks=required_checks,
            warnings=tuple(warnings),
            blocking_messages=tuple(blocking),
            summary=summary,
            next_action=next_action,
        )

    def record_map_studio_game_proof(
        self,
        *,
        proof_manifest_path: str | Path,
        evidence_path: str | Path,
        tester: str = "",
        notes: str = "",
        module_loads_in_game: bool = False,
        player_spawns_on_floor: bool = False,
        test_placeable_visible: bool = False,
        player_can_walk_on_floor: bool = False,
        allow_missing_evidence: bool = False,
    ):
        """Record in-game proof for a staged Map Studio module proof manifest."""

        proof_path = Path(proof_manifest_path)
        try:
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
        except Exception:
            proof = {}
        task = str(proof.get("task") or "").strip().upper()
        proof_filename = proof_path.name.lower()
        common = {
            "proof_manifest_path": str(proof_path),
            "evidence_path": str(evidence_path),
            "tester": tester,
            "notes": notes,
            "module_loads_in_game": bool(module_loads_in_game),
            "player_spawns_on_floor": bool(player_spawns_on_floor),
            "test_placeable_visible": bool(test_placeable_visible),
            "player_can_walk_on_floor": bool(player_can_walk_on_floor),
            "allow_missing_evidence": bool(allow_missing_evidence),
        }
        if task == "T2601" or proof_filename.endswith("_in_game_smoke_manifest.json"):
            result = record_dev_module_game_proof(DevModuleGameProofRequest(**common))
        else:
            result = record_authored_module_game_proof(AuthoredModuleGameProofRequest(**common))
            if getattr(result, "ok", False):
                payload = dict((getattr(self.project, "extra_sections", {}) or {}).get("authored_module") or {})
                if payload:
                    try:
                        recorded_proof = json.loads(Path(getattr(result, "proof_manifest_path", "") or proof_path).read_text(encoding="utf-8"))
                    except Exception:
                        recorded_proof = {}
                    payload["game_tested"] = True
                    payload["proof_manifest_path"] = str(getattr(result, "proof_manifest_path", "") or proof_path)
                    payload["pack_manifest_path"] = str(getattr(result, "pack_manifest_path", "") or "")
                    payload["in_game_proof_evidence_path"] = str(getattr(result, "evidence_path", "") or evidence_path)
                    for key in ("manual_proof_required", "game_test", "modder_test_plan"):
                        if key in recorded_proof:
                            payload[key] = recorded_proof[key]
                    self.project.extra_sections["authored_module"] = payload
                    self.project.dirty = True
        self.model.log(getattr(result, "message", "Recorded Map Studio game proof."))
        return result

    def export_fbx(self, output_path: str | Path, *, dry_run: bool = False):
        return self.export_bridge.export_fbx(self.project, output_path, LevelExportOptions(dry_run=dry_run))

    def add_blueprint(self, name: str = "Blueprint", blueprint_type: str = "Custom", template_resref: str = ""):
        blueprint = self.blueprint_service.add_blueprint(self.project, name, blueprint_type=blueprint_type, template_resref=template_resref)
        self.model.select(blueprint.blueprint_id)
        return blueprint

    def import_library_asset(self, row: dict[str, Any], *, resource_manager: Any = None):
        """Add a game-library asset row to the editable KMAP scene."""
        asset = dict(row or {})
        resref = str(asset.get("resref") or "").strip()
        if not resref:
            raise ValueError("Library asset is missing a resref.")
        game = str(asset.get("game") or self.project.game or "K1").upper()
        category = str(asset.get("category") or "").strip()
        model_class = str(asset.get("model_class") or "").strip()
        source = str(asset.get("source") or "")
        metadata = {
            "library_asset": {
                "resref": resref,
                "game": game,
                "category": category,
                "model_class": model_class,
                "source": source,
                "area_label": asset.get("area_label", ""),
                "module_code": asset.get("module_code", ""),
                "location": asset.get("location", ""),
            }
        }
        scene = LevelScene(self.project)
        if category == "Module" or model_class.lower() == "tile":
            placement = resolve_module_room_placement(game=game, resref=resref, resource_manager=resource_manager)
            transform = LevelTransform(position=placement.position) if placement is not None else None
            lyt_entry = {"model": resref, "source": "library", "game": game}
            if placement is not None:
                lyt_entry.update(placement.to_metadata())
            room = scene.add_room(
                str(asset.get("area_label") or resref),
                model_resref=resref,
                source_module=str(
                    (placement.module_code if placement is not None else "")
                    or asset.get("module_code")
                    or asset.get("location")
                    or ""
                ),
                module_id=self.model.active_module_id,
                transform=transform,
                lyt_entry=lyt_entry,
            )
            if placement is not None:
                metadata.setdefault("module_group", placement.to_metadata())
            room.metadata.update(metadata)
            self.model.select(room.room_id)
            self.model.log(f"Imported library room {game}:{resref}.")
            return room

        blueprint_type = self._blueprint_type_for_library_asset(category, resref)
        blueprint = self.blueprint_service.add_blueprint(
            self.project,
            str(asset.get("area_label") or resref),
            blueprint_type=blueprint_type,
            template_resref=resref,
        )
        blueprint.properties.update({"game": game, "source": source, "category": category, "model_class": model_class})
        blueprint.metadata.update(metadata)
        self.model.select(blueprint.blueprint_id)
        self.model.log(f"Imported library {blueprint_type.lower()} {game}:{resref}.")
        return blueprint

    @staticmethod
    def _blueprint_type_for_library_asset(category: str, resref: str) -> str:
        value = (category or "").lower()
        lower_resref = (resref or "").lower()
        if value == "creature" or lower_resref.startswith("c_"):
            return "Creature"
        if "item" in value:
            return "Placeable"
        if value == "character":
            return "Creature"
        if lower_resref.startswith(("plc_", "utp_")):
            return "Placeable"
        if lower_resref.startswith(("door_", "utd_")):
            return "Door"
        return "Custom"

    def record_port(self, source_game: str, target_game: str):
        return self.porter_service.record_port_decision(self.project, source_game, target_game)
