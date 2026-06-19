"""Controller coordinating KMAP project state and module-editor services."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.core.level import KMapProject, KMapSerializer, KMapValidator, LevelExportBridge, LevelExportOptions, LevelScene, LevelTransform, new_kmap_project
from src.core.scene.module_scene_import import resolve_module_room_placement

from .module_blueprint_service import ModuleBlueprintService
from .module_builder_service import ModuleBuilderService
from .module_editor_model import ModuleEditorModel
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
    update_authored_gameplay_camera_properties,
    update_authored_gameplay_placement_transform,
    update_authored_gameplay_transition,
)
from .authored_room_operations import (
    add_authored_room_composition_primitive,
    apply_authored_terrain_operation,
    apply_authored_floor_plan_rectangular_union,
    apply_authored_floor_plan_operation,
    available_authored_composition_primitive_kinds,
    authored_floor_plan_room_choices,
    authored_terrain_room_choices,
    authored_room_composition_primitives,
    move_authored_floor_plan_point,
    move_authored_room_composition_primitive,
    remove_authored_room_composition_primitive,
    set_authored_room_composition_primitive_dimensions,
    set_authored_room_composition_primitive_style,
    set_authored_room_composition_primitive_transform,
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
from .authored_walkmesh_surfaces import authored_walkmesh_surface_palette
from .dev_module_smoke import DevModuleGameProofRequest, DevModuleInstallPrepRequest, DevModuleSmokeRequest, prepare_dev_test_module_install, record_dev_module_game_proof
from .module_layout_service import ModuleLayoutService
from .module_porter_service import ModulePorterService
from .module_walkmesh_service import ModuleWalkmeshService


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
        self.undo_stack: list[tuple[str, Any]] = []
        self.redo_stack: list[tuple[str, Any]] = []

    @property
    def project(self) -> KMapProject:
        return self.model.project

    def new_project(self, name: str = "new_level", game: str = "K1", author: str = "") -> KMapProject:
        game_key = str(game or "K1").strip().upper()
        if game_key not in {"K1", "K2"}:
            raise ValueError("Map Studio projects must target K1 or K2.")
        issue = authored_resref_blocking_issue("Map Studio module root", name)
        if issue:
            raise ValueError(issue)
        project_name = normalise_resref(name) or "new_level"
        self.model.set_project(new_kmap_project(name=project_name, game=game_key, author=str(author or "").strip()))
        self.model.project.dirty = True
        self.model.log(f"Created new Map Studio KMAP project {project_name} for {game_key}.")
        return self.model.project

    def open_project(self, path: str | Path) -> KMapProject:
        project = KMapSerializer.load(path)
        self.model.set_project(project)
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

    def create_authored_room_preset_module(self, *, preset_id: str, module_root: str = "grdev01"):
        """Store an authored module created from a named primitive room preset."""

        root = str(module_root or "grdev01").strip() or "grdev01"
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
        return self.authored_module_readiness()

    def apply_authored_room_operation(self, *, operation: str, **kwargs: Any):
        """Apply a floor-plan shaping operation to the current authored KMAP module."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
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
        return self.authored_module_readiness()

    def apply_authored_terrain_operation(self, *, operation: str, **kwargs: Any):
        """Apply a terrain heightfield operation to the current authored KMAP module."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
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
        return self.authored_module_readiness()

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
        return self.authored_module_readiness()

    def move_authored_room_outline_point(self, *, room_resref: str, point_index: int, world_position: Any):
        """Move one authored room outline vertex through the headless floor-plan operation."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
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
        return self.authored_module_readiness()

    def move_authored_room_primitive(self, *, room_resref: str, primitive_name: str, world_delta: Any):
        """Move one authored composition primitive by a viewport-authored world delta."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
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
        return self.authored_module_readiness()

    def remove_authored_room_primitive(self, *, room_resref: str, primitive_name: str):
        """Remove one authored composition primitive from the current KMAP module."""

        extra = getattr(self.project, "extra_sections", {}) or {}
        payload = extra.get("authored_module")
        if payload is None:
            raise ValueError("No authored Map Studio module is stored in this KMAP. Create or load an authored module first.")
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
        return self.authored_module_readiness()

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
            self.project.extra_sections["authored_module"] = payload
            self.project.dirty = True
        self.model.log(result.message)
        return result

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
                    for key in ("manual_proof_required", "game_test"):
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
