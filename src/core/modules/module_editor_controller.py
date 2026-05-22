"""Controller coordinating KMAP project state and module-editor services."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.level import KMapProject, KMapSerializer, KMapValidator, LevelExportBridge, LevelExportOptions, LevelScene, new_kmap_project

from .module_blueprint_service import ModuleBlueprintService
from .module_builder_service import ModuleBuilderService
from .module_editor_model import ModuleEditorModel
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

    def build_preview(self, output_dir: str | Path):
        return self.builder_service.build_preview(self.project, output_dir)

    def export_fbx(self, output_path: str | Path, *, dry_run: bool = False):
        return self.export_bridge.export_fbx(self.project, output_path, LevelExportOptions(dry_run=dry_run))

    def add_blueprint(self, name: str = "Blueprint", blueprint_type: str = "Custom", template_resref: str = ""):
        blueprint = self.blueprint_service.add_blueprint(self.project, name, blueprint_type=blueprint_type, template_resref=template_resref)
        self.model.select(blueprint.blueprint_id)
        return blueprint

    def import_library_asset(self, row: dict[str, Any]):
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
            room = scene.add_room(
                str(asset.get("area_label") or resref),
                model_resref=resref,
                source_module=str(asset.get("module_code") or asset.get("location") or ""),
                module_id=self.model.active_module_id,
                lyt_entry={"model": resref, "source": "library", "game": game},
            )
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
