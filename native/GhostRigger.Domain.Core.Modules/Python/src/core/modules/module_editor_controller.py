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
from .authored_gameplay_palette import authored_gameplay_palette_from_library_rows
from .authored_gameplay_marker_geometry import (
    AuthoredGameplayMarkerGeometry,
    authored_gameplay_marker_geometry_for_project,
)
from .authored_gameplay_preview import authored_gameplay_preview_markers
from .authored_module_placements import (
    SUPPORTED_AUTHORED_GAMEPLAY_PLACEMENTS,
    add_authored_gameplay_placement,
    authored_gameplay_placement_rows,
    parse_authored_gameplay_placement_id,
    update_authored_gameplay_placement_transform,
)
from .authored_room_operations import apply_authored_floor_plan_operation, move_authored_floor_plan_point
from .authored_room_outline_geometry import AuthoredRoomOutlineGeometry, authored_room_outline_geometry_for_project
from .authored_room_presets import available_authored_room_primitive_presets, create_authored_module_from_room_preset
from .authored_room_style import update_authored_room_style
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
        self.model.set_project(new_kmap_project(name=name, game=game, author=author))
        self.model.project.dirty = True
        self.model.log("Created new KMAP project.")
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
        scene = LevelScene(self.project)
        changed = scene.remove_room(item_id) or scene.remove_module(item_id)
        if changed:
            self.model.select("")
            self.model.log(f"Deleted {item_id}.")
        return changed

    def duplicate_selected(self):
        item_id = self.model.selected_ids[0] if self.model.selected_ids else ""
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
        return self.validator.validate(self.project)

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

    def available_authored_walkmesh_surfaces(self):
        """Return named WOK surface choices for authored room floors."""

        return authored_walkmesh_surface_palette()

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

    def stage_authored_module(self, output_dir: str | Path, *, dry_run: bool = False, overwrite: bool = False):
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
                dry_run=dry_run,
                overwrite=overwrite,
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
                    payload["game_tested"] = True
                    payload["proof_manifest_path"] = str(getattr(result, "proof_manifest_path", "") or proof_path)
                    payload["pack_manifest_path"] = str(getattr(result, "pack_manifest_path", "") or "")
                    payload["in_game_proof_evidence_path"] = str(getattr(result, "evidence_path", "") or evidence_path)
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
