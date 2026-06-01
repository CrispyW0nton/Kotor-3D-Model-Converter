"""Game-library scans, model loads, scene import choices, resources, and walkmesh co-load behavior."""

from __future__ import annotations

import logging
import re
import traceback
from pathlib import Path
from typing import Optional

try:
    from PySide6 import QtCore, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.core.scene.scene_object import PivotData, Transform
from src.core.scene.module_scene_import import ModuleRoomPlacement, resolve_module_room_placement
from src.core.scene.scene_resource_ref import SceneResourceRef
from src.gui.qt_lib.dialogs.add_model_to_scene_dialog import AddModelToSceneChoice, AddModelToSceneDialog
from src.gui.windows.application_core.application_core_lib.functions.geometry import (
    _walkmesh_overlay_node_from_wok,
    _walkmesh_overlay_offset_for_model,
)
from src.gui.windows.application_core.application_core_lib.shared.workers import (
    LibraryScanWorker,
    ModelListItem,
    ModelLoadWorker,
    ResourceModelLoadWorker,
    load_resource_model_from_game_resources,
)
from src.systems.bas.attachment_alignment import default_bas_attachment_transform, normalize_bas_transform
from src.systems.bas.model_recipe import BAS_SLOT_ORDER, load_bas_model_recipe

log = logging.getLogger(__name__)


class ResourceLoadingMixin:
    """Game-library scans, model loads, scene import choices, resources, and walkmesh co-load behavior."""

    def _populate_saved_dirs(self):
        self.library_list.clear()
        for key, label in (("k1_dir", "KotOR 1"), ("k2_dir", "KotOR 2")):
            value = str(self.settings_data.get(key) or "").strip()
            if value:
                self.library_list.addItem(f"{label}: {value}")
        if self.library_list.count() == 0:
            self.library_list.addItem("No saved game directories yet")
    def _scan_library(self):
        if self._scan_worker_is_running():
            return
        k1_dir = self.k1_dir_edit.text().strip()
        k2_dir = self.k2_dir_edit.text().strip()
        self._show_progress_toast(
            "Scanning game library",
            "Indexing model resources from detected game directories...",
        )
        self.scan_button.setEnabled(False)
        self._set_library_scan_buttons_enabled(False)
        self.library_list.clear()
        self.library_list.addItem("Scanning...")
        self._log("Scanning game library...")
        self.statusBar().showMessage("Scanning library...")

        worker = LibraryScanWorker(k1_dir, k2_dir)
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_library_scanned)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: setattr(self, "_scan_thread", None))
        thread.finished.connect(lambda: setattr(self, "_scan_worker", None))
        self._scan_thread = thread
        self._scan_worker = worker
        thread.start()
    @QtCore.Slot(list, str)
    def _on_library_scanned(self, rows: list, error: str):
        self.scan_button.setEnabled(True)
        self._set_library_scan_buttons_enabled(True)
        if error:
            self._finish_progress_toast("Library scan failed", "Check the output log for details.")
            self.library_list.clear()
            self.library_list.addItem("Scan failed")
            if hasattr(self, "library_panel"):
                self.library_panel.set_rows([])
                self.library_panel.set_status("Scan failed")
            self._log(f"Library scan failed:\n{error}", "error")
            self.statusBar().showMessage("Library scan failed")
            return
        self._library_rows = rows
        self._rebuild_library_list()
        if hasattr(self, "animation_retarget_window"):
            self.animation_retarget_window.set_library_rows(rows)
        if hasattr(self, "library_panel"):
            self.library_panel.set_rows(rows)
            self.library_panel.set_status(f"{len(rows)} models")
        module_editor_window = getattr(self, "module_editor_window", None)
        if module_editor_window is not None:
            module_editor_window.set_library_rows(rows)
        self._unreal_refresh_supermodel_library()
        self._populate_resource_panel()
        self._populate_animation_library_from_current_model()
        self._finish_progress_toast("Library ready", f"{len(rows)} models indexed.")
        self._log(f"Library scan complete: {len(rows)} models", "success")
        self.statusBar().showMessage(f"{len(rows)} models")
    def _set_library_scan_buttons_enabled(self, enabled: bool) -> None:
        panel = getattr(self, "library_panel", None)
        if panel is None:
            return
        for name in ("scan_button", "deep_button"):
            button = getattr(panel, name, None)
            if button is not None:
                button.setEnabled(enabled)
    def _rebuild_library_list(self):
        self.library_list.clear()
        needle = self.library_filter.text().lower().strip()
        for row in self._library_rows:
            text = f"[{row.get('game', '?')}] {row.get('resref', '')}"
            if needle and needle not in text.lower():
                continue
            self.library_list.addItem(ModelListItem(row))
        if self.library_list.count() == 0:
            self.library_list.addItem("No matching models")
    def _filter_library(self, text: str):
        if self._library_rows:
            self._rebuild_library_list()
            return
        needle = text.lower().strip()
        for row in range(self.library_list.count()):
            item = self.library_list.item(row)
            item.setHidden(bool(needle and needle not in item.text().lower()))
    def _load_library_item(self, item: QtWidgets.QListWidgetItem):
        row = getattr(item, "row", None)
        if not row:
            return
        self._start_resource_load(row["resref"], row["game"])
    def _load_content_browser_primary_scene_model(self, row: dict) -> None:
        resref = str(row.get("resref") or "")
        game = str(row.get("game") or "")
        if resref:
            self._start_resource_load(resref, game, import_action="clear")
    def _add_content_browser_model_to_current_scene(self, row: dict) -> None:
        resref = str(row.get("resref") or "")
        game = str(row.get("game") or "")
        if resref:
            self._start_resource_load(resref, game, import_action="add")
    def _start_resource_load(self, resref: str, game: str, import_action: str = ""):
        if self._model_worker_is_running():
            self._log("A model is already loading.", "warning")
            return
        action = str(import_action or "").strip().lower()
        if action in {"clear", "clear_and_load", "clear scene and load"}:
            if not self._prompt_save_dirty_scene():
                return
            action = "clear"
            self._pending_scene_import_placement = "origin"
        elif action in {"add", "add_to_scene", "add to existing scene"}:
            action = "add"
            self._pending_scene_import_placement = str(self.settings_data.get("default_import_placement") or "auto_offset")
        else:
            action = self._choose_model_import_action(f"{game}:{resref}")
        if action == "cancel":
            return
        self._pending_scene_import_action = action
        if str(resref).lower().startswith("gr_humanoid"):
            try:
                from src.core.templates.template_builder import build_humanoid_template

                self._show_progress_toast("Loading model", f"Building template {game}:{resref}...")
                game_tag = game.upper() if game else "K1"
                model = build_humanoid_template(game_version=game_tag, name=resref)
                self._current_game = game_tag
                self._on_model_loaded(model, f"{game_tag}:{resref}", "")
            except Exception:
                self._log(f"Template load failed:\n{traceback.format_exc()}", "error")
            return
        self._log(f"Loading {game}:{resref} ...")
        self.statusBar().showMessage(f"Loading {game}:{resref}...")
        self._show_progress_toast("Loading model", f"Loading {game}:{resref} from game resources...")
        self._current_game = game.upper()
        QtCore.QTimer.singleShot(0, lambda: self._load_resource_model_on_ui_thread(resref, game))

    def _load_resource_model_on_ui_thread(self, resref: str, game: str) -> None:
        def progress(message: str, step: int, total: int) -> None:
            self._on_model_load_progress(message, step, total)
            app = QtWidgets.QApplication.instance()
            if app is not None:
                app.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)

        try:
            model, label = load_resource_model_from_game_resources(
                resref,
                game,
                self.k1_dir_edit.text().strip(),
                self.k2_dir_edit.text().strip(),
                progress=progress,
            )
            self._on_model_loaded(model, label, "")
        except Exception:
            self._on_model_loaded(None, f"{str(game or '').upper()}:{resref}", traceback.format_exc())
    def _open_model(self, _checked: bool = False, *, ascii_only: bool = False):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open ASCII MDL" if ascii_only else "Open KotOR MDL",
            str(Path(self.settings_data.get("last_import") or self.app_root)),
            "ASCII MDL (*.mdl);;All files (*.*)" if ascii_only else "KotOR MDL or BAS Build (*.mdl *.json);;KotOR MDL (*.mdl);;BAS Build JSON (*.json);;All files (*.*)",
        )
        if not path:
            return
        self._start_model_load(path)
    def _open_startup_inputs(self):
        mdl_path = str(self.startup_input.get("mdl") or "").strip()
        if not mdl_path:
            return
        texture_dir = str(self.startup_input.get("texture_dir") or "").strip()
        textures = [str(path) for path in (self.startup_input.get("tga") or []) if path]
        if not texture_dir and textures:
            texture_dir = str(Path(textures[0]).resolve().parent)
        mdx_path = str(self.startup_input.get("mdx") or "").strip()
        game = str(self.startup_input.get("game") or "").upper()
        self._start_model_load(mdl_path, mdx_path=mdx_path, texture_dir=texture_dir, game=game)
        if textures:
            self._log(f"Startup texture context: {len(textures)} file(s)", "info")
    def _load_bas_model_recipe_from_path(self, path: Path):
        recipe = load_bas_model_recipe(path)
        game = str(recipe.get("game") or (recipe.get("body") or {}).get("game") or "K1").upper()
        body_info = recipe.get("body") or {}
        body_resref = str(body_info.get("resref") or "").strip()
        if not body_resref:
            raise ValueError("BAS build is missing its body resref.")
        manager = self._get_resource_manager()
        if manager is None:
            raise RuntimeError("No resource manager is available for BAS build import.")

        body = manager.load_model(body_resref, game)
        if body is None:
            raise FileNotFoundError(f"{game}:{body_resref}.mdl")
        self._animation_timer.stop()
        self._animation_engine = None
        self._animation_last_tick = None
        self._retarget_timer.stop()
        self._retarget_engine = None
        self._retarget_last_tick = None
        self._model_path = str(path)
        self._current_game = game
        self._current_model = body
        self._bas_body_model = body
        self._bas_preview_model = None
        self._bas_attachments.clear()
        self._bas_attachment_resrefs.clear()
        self._bas_attachment_transforms.clear()
        self._bas_active_build_name = str(recipe.get("display_name") or recipe.get("build_name") or path.stem).strip()
        self._bas_mode = str(recipe.get("mode") or (recipe.get("runtime") or {}).get("body_mode") or "headless_body").strip().lower()
        if self._bas_mode not in {"headless_body", "full_body"}:
            self._bas_mode = "headless_body"
        self._current_head_model = None
        self._current_attachment_model = None

        for layer in recipe.get("layers") or []:
            slot = str((layer or {}).get("slot") or "").strip().lower()
            if slot in {"", "body", "left_hand", "right_hand"}:
                continue
            resref = str((layer or {}).get("resref") or "").strip()
            if not resref or str((layer or {}).get("state") or "").lower() != "attached":
                continue
            layer_game = str((layer or {}).get("game") or game).upper()
            model = manager.load_model(resref, layer_game)
            if model is None:
                raise FileNotFoundError(f"{layer_game}:{resref}.mdl")
            self._bas_attachments[slot] = model
            self._bas_attachment_resrefs[slot] = resref
            self._bas_attachment_transforms[slot] = normalize_bas_transform(
                (layer or {}).get("transform") or default_bas_attachment_transform(slot, resref)
            )
            if slot == "head":
                self._current_head_model = model
            else:
                self._current_attachment_model = model

        if hasattr(self, "_add_loaded_model_to_scene"):
            self._add_loaded_model_to_scene(body, f"{game}:{body_resref}")
        result = self._rebuild_bas_preview()
        preview = getattr(self, "_bas_preview_model", None)
        if hasattr(self, "body_attachment_panel"):
            if hasattr(self.body_attachment_panel, "set_mode"):
                self.body_attachment_panel.set_mode(self._bas_mode)
            self.body_attachment_panel.set_body_model(body)
            for slot in BAS_SLOT_ORDER:
                if slot == "body":
                    continue
                if slot in self._bas_attachments:
                    self.body_attachment_panel.set_slot_model(slot, self._bas_attachments[slot], resref=self._bas_attachment_resrefs.get(slot, ""))
                else:
                    self.body_attachment_panel.clear_slot_model(slot)
            self.body_attachment_panel.set_status(f"Loaded BAS build: {self._bas_active_build_name}")
        if hasattr(self, "skeleton_panel") and preview is not None:
            self.skeleton_panel.load_model(preview)
        if hasattr(self, "properties_panel"):
            self.properties_panel.show_model(body)
        if hasattr(self, "animations_panel"):
            self._load_animation_panel_model(body)
        if hasattr(self, "sprite_materials_panel") and preview is not None:
            self.sprite_materials_panel.set_model(preview)
        if hasattr(self, "_populate_animation_library_from_current_model"):
            self._populate_animation_library_from_current_model()
        if hasattr(self, "statusBar"):
            self.statusBar().showMessage(result or f"Loaded BAS build: {self._bas_active_build_name}")
        self._log(f"Loaded BAS build {path.name}", "success")
        return preview
    def _start_model_load(
        self,
        path: str,
        *,
        mdx_path: str = "",
        texture_dir: str = "",
        game: str = "",
    ):
        if self._model_worker_is_running():
            self._log("A model is already loading.", "warning")
            return
        action = self._choose_model_import_action(Path(path).name)
        if action == "cancel":
            return
        self._pending_scene_import_action = action
        mdl = Path(path)
        if not mdl.exists():
            self._log(f"Startup model not found: {path}", "error")
            self.statusBar().showMessage("Model file not found")
            return
        if mdl.suffix.lower() == ".json":
            try:
                self._load_bas_model_recipe_from_path(mdl)
            except Exception:
                self._log(f"BAS build load failed:\n{traceback.format_exc()}", "error")
                self.statusBar().showMessage("BAS build load failed")
            return
        if mdx_path and not Path(mdx_path).exists():
            self._log(f"MDX file not found, using sibling lookup: {mdx_path}", "warning")
            mdx_path = ""
        self._texture_dir = texture_dir or str(mdl.parent)
        self._log(f"Loading {mdl} ...")
        self.statusBar().showMessage("Loading model...")
        self._show_progress_toast("Loading model", f"Loading {mdl.name}...")
        self._current_game = game.upper()

        worker = ModelLoadWorker(str(mdl), mdx_path, self._current_game)
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_model_load_progress)
        worker.finished.connect(self._on_model_loaded)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: setattr(self, "_worker_thread", None))
        thread.finished.connect(lambda: setattr(self, "_model_worker", None))
        self._worker_thread = thread
        self._model_worker = worker
        thread.start()
    def _choose_model_import_action(self, model_label: str) -> str:
        objects = self.scene_manager.get_scene_objects()
        if not objects:
            self._pending_scene_import_placement = "origin"
            return "add"
        preference = str(self._session_model_double_click_choice or self.settings_data.get("model_double_click_behaviour") or "always ask").lower()
        if preference in {"add", "add to existing scene", "add_to_scene"}:
            self._pending_scene_import_placement = str(self.settings_data.get("default_import_placement") or "auto_offset")
            return "add"
        if preference in {"clear", "clear scene and load", "clear_and_load"}:
            if not self._prompt_save_dirty_scene():
                return "cancel"
            self._pending_scene_import_placement = "origin"
            return "clear"
        dialog = AddModelToSceneDialog(model_label, self)
        try:
            self.theme_manager.register_theme_aware_widget(dialog)
            active_theme = self.theme_manager.current_theme or self.theme_manager.get_theme()
            if active_theme.is_native():
                dialog.setStyleSheet("")
            else:
                dialog.apply_ghost_theme(active_theme)
            active_layout = self.layout_manager.current_layout or self.layout_manager.get_layout()
            dialog.apply_ghost_layout(active_layout)
        except Exception:
            pass
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return "cancel"
        if dialog.remember_choice:
            self._session_model_double_click_choice = dialog.choice.value
        self._pending_scene_import_placement = dialog.placement_mode
        if dialog.choice is AddModelToSceneChoice.CLEAR_AND_LOAD:
            if not self._prompt_save_dirty_scene():
                return "cancel"
            return "clear"
        if dialog.choice is AddModelToSceneChoice.ADD_TO_SCENE:
            return "add"
        return "cancel"
    def _resource_ref_from_loaded_model(self, model, path: str) -> SceneResourceRef:
        label = str(path or "")
        if ":" in label and label.split(":", 1)[0].upper() in {"K1", "K2"}:
            game, resref = label.split(":", 1)
            return SceneResourceRef(
                resource_type="model",
                game=game.upper(),
                resref=resref,
                original_name=getattr(model, "name", resref),
            )
        return SceneResourceRef(
            resource_type="model",
            game=(self._current_game or self._infer_game_from_model(model)).upper(),
            source_path=label,
            original_name=getattr(model, "name", Path(label).stem if label else "model"),
        )
    def _module_room_placement_for_ref(self, ref: SceneResourceRef) -> ModuleRoomPlacement | None:
        game = str(getattr(ref, "game", "") or self._current_game or self.settings_data.get("default_game") or "K1").upper()
        resref = str(getattr(ref, "resref", "") or getattr(ref, "original_name", "") or "").strip()
        if not resref:
            return None
        try:
            return resolve_module_room_placement(
                game=game,
                resref=resref,
                resource_manager=self._resource_manager or self._get_resource_manager(),
            )
        except Exception as exc:
            log.debug("module room placement lookup failed for %s:%s: %s", game, resref, exc)
            return None

    def _placement_transform_for_new_model(self, module_placement: ModuleRoomPlacement | None = None) -> Transform:
        if module_placement is not None:
            return Transform(position=module_placement.position)
        placement = str(self._pending_scene_import_placement or "auto_offset")
        if placement == "origin":
            return Transform()
        occupied = {
            tuple(round(float(v), 3) for v in obj.transform.position[:3])
            for obj in self.scene_manager.active_scene.objects
        }
        position = (0.0, 0.0, 0.0)
        if position in occupied:
            index = 1
            while (round(index * 2.0, 3), 0.0, 0.0) in occupied:
                index += 1
            position = (index * 2.0, 0.0, 0.0)
        return Transform(position=position)
    def _add_loaded_model_to_scene(self, model, path: str):
        action = str(self._pending_scene_import_action or "add")
        if action == "clear":
            self.scene_manager.clear_scene()
        ref = self._resource_ref_from_loaded_model(model, path)
        texture_dir = ""
        if path and not str(path).startswith(("K1:", "K2:")):
            try:
                texture_dir = str(Path(path).parent)
            except Exception:
                texture_dir = ""
        if texture_dir and texture_dir not in self._scene_texture_dirs:
            self._scene_texture_dirs.append(texture_dir)
        module_placement = self._module_room_placement_for_ref(ref)
        instance = self.scene_manager.add_model_instance(
            ref,
            transform=self._placement_transform_for_new_model(module_placement),
            runtime_model=model,
            select=True,
        )
        if module_placement is not None:
            self._apply_module_group_metadata(instance, model, module_placement)
        self.scene_manager.active_scene.game = ref.game or self.scene_manager.active_scene.game
        return instance

    def _apply_module_group_metadata(self, instance, model, placement: ModuleRoomPlacement) -> None:
        instance.group_id = placement.group_id
        instance.metadata["module_group"] = placement.to_metadata()
        instance.metadata["child_count"] = self._runtime_model_child_count(model)
        center = self._model_bounds_center(model)
        instance.pivot = PivotData(
            position_local=center,
            rotation_local=(0.0, 0.0, 0.0),
            enabled=True,
            metadata={"source": "model_bounds_center", "scope": "module_group"},
        )
        self.scene_manager.mark_dirty()

    @staticmethod
    def _runtime_model_child_count(model) -> int:
        if model is None:
            return 0
        try:
            nodes = list(model.all_nodes() or []) if hasattr(model, "all_nodes") else []
        except Exception:
            nodes = []
        root = getattr(model, "root_node", None)
        return len([node for node in nodes if node is not None and node is not root])

    @staticmethod
    def _model_bounds_center(model) -> tuple[float, float, float]:
        if model is None:
            return (0.0, 0.0, 0.0)
        try:
            compute = getattr(model, "compute_bounds", None)
            if callable(compute):
                compute()
            bb_min = tuple(float(v) for v in getattr(model, "bb_min", (0.0, 0.0, 0.0))[:3])
            bb_max = tuple(float(v) for v in getattr(model, "bb_max", (0.0, 0.0, 0.0))[:3])
            return (
                (bb_min[0] + bb_max[0]) * 0.5,
                (bb_min[1] + bb_max[1]) * 0.5,
                (bb_min[2] + bb_max[2]) * 0.5,
            )
        except Exception:
            return (0.0, 0.0, 0.0)
    @QtCore.Slot(object, str, str)
    def _on_model_loaded(self, model, path: str, error: str):
        if error:
            self._log(f"Model load failed:\n{error}", "error")
            self.statusBar().showMessage("Model load failed")
            self._pending_gpu_upload_model_id = 0
            self._pending_gpu_upload_total = 0
            self._finish_progress_toast("Model load failed", "Check the output log for details.")
            return
        self._update_progress_toast("Loading model", "Updating viewport and panels...", 5, 6)
        self._animation_timer.stop()
        self._animation_engine = None
        self._animation_last_tick = None
        self._retarget_timer.stop()
        self._retarget_engine = None
        self._retarget_last_tick = None
        self._current_model = model
        self._bas_body_model = model
        self._bas_preview_model = None
        self._bas_attachments.clear()
        self._bas_attachment_resrefs.clear()
        self._bas_attachment_transforms.clear()
        self._bas_active_build_name = ""
        self._bas_mode = self._bas_mode_for_model(model)
        self._current_head_model = None
        self._current_attachment_model = None
        self._retarget_target_model = model
        self._retarget_mapping_report = None
        if path:
            self._model_path = path
            if str(path).startswith(("K1:", "K2:")):
                self._current_game = str(path).split(":", 1)[0].upper()
            else:
                self._texture_dir = self._texture_dir or str(Path(path).parent)
                self._current_game = self._infer_game_from_model(model)
        mesh_count = len(model.mesh_nodes()) if hasattr(model, "mesh_nodes") else 0
        node_count = model.node_count() if hasattr(model, "node_count") else 0
        anim_count = len(getattr(model, "animations", []) or [])
        name = getattr(model, "name", Path(path).stem)
        scene_instance = self._add_loaded_model_to_scene(model, path)
        if hasattr(self, "viewport"):
            self._configure_viewport_resources()
            self._refresh_scene_view()
            self._try_coload_walkmesh()
        else:
            self.viewport_label.setText(f"{name}\n\nQt viewport host\n{mesh_count} mesh | {node_count} nodes")
        self._update_scene_chrome()
        if hasattr(self, "skeleton_panel"):
            self.skeleton_panel.load_model(model)
        if hasattr(self, "lighting_panel"):
            self.lighting_panel.set_model(self._active_viewport_model())
            self._sync_lighting_helper_visibility_to_viewport()
        if hasattr(self, "camera_panel"):
            self.camera_panel.set_model(self._active_viewport_model())
            self.camera_panel.manager = self.viewport.camera_manager
            self.camera_panel.refresh()
        if hasattr(self, "properties_panel"):
            self.properties_panel.show_model(model)
        if hasattr(self, "module_geometry_panel"):
            self.module_geometry_panel.show_model(self._active_viewport_model())
        if hasattr(self, "sprite_materials_panel"):
            self.sprite_materials_panel.set_model(self._active_viewport_model())
        if hasattr(self, "body_attachment_panel"):
            if hasattr(self.body_attachment_panel, "set_mode"):
                self.body_attachment_panel.set_mode(self._bas_mode)
            self.body_attachment_panel.set_body_model(model)
            for slot in BAS_SLOT_ORDER:
                if slot == "body":
                    continue
                self.body_attachment_panel.clear_slot_model(slot)
            self.body_attachment_panel.set_status(f"Body: {name}")
        if hasattr(self, "animations_panel"):
            self._load_animation_panel_model(model)
        if hasattr(self, "animation_retarget_panel"):
            self.animation_retarget_panel.set_texture_dir(self._texture_dir)
            game = (self._current_game or self._infer_game_from_model(model)).upper()
            if self._supports_animation_retarget_target(model):
                mgr = self._get_resource_manager()
                if mgr is not None:
                    self.animation_retarget_panel.set_target_resource_context(mgr, game)
                self.animation_retarget_panel.set_target_model(model, game)
            else:
                self._retarget_target_model = None
                self._retarget_mapping_report = None
                self.animation_retarget_panel.set_target_model(None, game)
        if hasattr(self, "retarget_preview_controller"):
            self._sync_retarget_preview_target()
        if hasattr(self, "diagnostics_panel"):
            self.diagnostics_panel.run_diagnostics(model)
        self.props_text.setPlainText(
            "\n".join(
                [
                    f"Name: {name}",
                    f"Path: {path}",
                    f"Meshes: {mesh_count}",
                    f"Nodes: {node_count}",
                    f"Animations: {anim_count}",
                    f"Supermodel: {getattr(model, 'supermodel', '')}",
                ]
            )
        )
        prebuilt_meshes = int(getattr(model, "_gr_gpu_prebuilt_mesh_count", 0) or 0)
        if prebuilt_meshes:
            self._pending_gpu_upload_model_id = id(model)
            self._pending_gpu_upload_total = prebuilt_meshes
            self._update_progress_toast(
                "Uploading mesh buffers",
                f"Moving mesh buffers into GPU memory (0/{prebuilt_meshes})...",
                0,
                prebuilt_meshes,
            )
            QtCore.QTimer.singleShot(
                5000,
                lambda model_id=id(model): self._finish_model_load_toast_if_pending(model_id),
            )
        else:
            self._pending_gpu_upload_model_id = 0
            self._pending_gpu_upload_total = 0
            self._finish_progress_toast("Model ready", f"{name} loaded.")
        if prebuilt_meshes:
            self._log(
                f"Loaded {name} ({mesh_count} mesh, {node_count} nodes; {prebuilt_meshes} GPU buffers prepared in RAM)",
                "success",
            )
        else:
            self._log(f"Loaded {name} ({mesh_count} mesh, {node_count} nodes)", "success")
        self.statusBar().showMessage(f"Loaded {name}")
        bus = getattr(self, "integration_event_bus", None)
        if bus is not None:
            bus.record_scene_update("model_imported", model)
            bus.animationChanged.emit(model)
        self._invalidate_renderer_resources(f"model loaded: {name}")
        if scene_instance is not None:
            self._log(f"Scene object added: {scene_instance.name}", "success")
    def _infer_game_from_model(self, model) -> str:
        try:
            game_name = getattr(getattr(model, "game_version", ""), "name", "")
            if str(game_name).upper() == "K2":
                return "K2"
        except Exception:
            pass
        return str(self.settings_data.get("default_game") or "K1").upper()
    def _configured_game_dirs(self) -> tuple[str, str]:
        k1_dir = self.k1_dir_edit.text().strip() if hasattr(self, "k1_dir_edit") else ""
        k2_dir = self.k2_dir_edit.text().strip() if hasattr(self, "k2_dir_edit") else ""
        return k1_dir, k2_dir
    def _get_resource_manager(self):
        k1_dir, k2_dir = self._configured_game_dirs()
        if not (k1_dir or k2_dir):
            return None
        existing = getattr(self, "_resource_manager", None)
        if existing is not None and getattr(self, "_resource_manager_dirs", ("", "")) == (k1_dir, k2_dir):
            return existing
        try:
            from src.core.assets.resource_manager import ResourceManager

            mgr = ResourceManager()
            if k1_dir:
                mgr.set_k1_dir(k1_dir)
            if k2_dir:
                mgr.set_k2_dir(k2_dir)
            self._resource_manager = mgr
            self._resource_manager_dirs = (k1_dir, k2_dir)
            return mgr
        except Exception as exc:
            self._log(f"Resource manager unavailable: {exc}", "warning")
            return None
    @staticmethod
    def _supports_animation_retarget_target(model) -> bool:
        if model is None:
            return True
        try:
            return int(getattr(model, "model_type", 0)) == 4
        except Exception:
            pass
        return str(getattr(model, "classification", "") or "").lower() in {
            "character",
            "creature",
            "headless_body",
            "head",
        }
    def _configure_viewport_resources(self):
        viewport = getattr(self, "viewport", None)
        if viewport is None:
            return
        game = (self._current_game or self._infer_game_from_model(self._current_model)).upper()
        mgr = self._get_resource_manager()
        if mgr is not None:
            try:
                viewport.set_resource_manager(mgr, game)
            except Exception as exc:
                self._log(f"Viewport texture resource setup failed: {exc}", "warning")
    @staticmethod
    def _derive_wok_resrefs(stem: str) -> list[str]:
        candidates = [stem]
        match = re.match(r"^(.+?)_[0-9a-z]+$", stem)
        if match:
            base = match.group(1)
            if base and base != stem:
                candidates.append(base)
                if base[:3].isdigit() and len(base) > 3:
                    candidates.append(base[:3])
        return candidates
    def _try_coload_walkmesh(self, mdl_path: Optional[Path] = None):
        try:
            if mdl_path is None:
                path = str(self._model_path or "")
                if path and not path.startswith(("K1:", "K2:")):
                    mdl_path = Path(path)
            self._do_coload_walkmesh(mdl_path)
        except Exception as exc:
            log.debug("_try_coload_walkmesh: %s", exc)
    def _do_coload_walkmesh(self, mdl_path: Optional[Path]):
        viewport = getattr(self, "viewport", None)
        if viewport is None:
            return
        model = self._current_model
        if model is None:
            viewport.clear_walkmesh()
            return

        path_label = str(self._model_path or "")
        if mdl_path is not None and mdl_path.name:
            stem = mdl_path.stem.lower()
            folder = mdl_path.parent
        elif ":" in path_label:
            stem = path_label.split(":", 1)[1].lower()
            folder = None
        else:
            stem = str(getattr(model, "name", "") or "").lower()
            folder = None
        if not stem:
            return

        viewport.clear_walkmesh()
        candidates = self._derive_wok_resrefs(stem)
        for base in candidates:
            if folder is not None:
                for ext in (".wok", ".pwk", ".dwk", ".bwm"):
                    path = folder / f"{base}{ext}"
                    if path.exists() and self._load_walkmesh_source(str(path), path.name):
                        return

        mgr = self._resource_manager or self._get_resource_manager()
        game = (self._current_game or self._infer_game_from_model(model)).upper()
        if mgr is not None:
            try:
                from src.core.assets.resource_manager import RES_WOK

                for base in candidates:
                    data = mgr.get(base, RES_WOK, game)
                    if data and self._load_walkmesh_source(data, f"{game}:{base}.wok"):
                        return
            except Exception as exc:
                log.debug("resource walkmesh lookup failed: %s", exc)
    def _load_walkmesh_source(self, source, label: str) -> bool:
        try:
            from src.core.modules.module_format import WOKData

            if isinstance(source, (bytes, bytearray)):
                source = WOKData.from_bytes(bytes(source))
            elif isinstance(source, str):
                source = WOKData.from_file(source)
            offset = _walkmesh_overlay_offset_for_model(
                self._current_model,
                source,
                getattr(self.viewport, "_renderer", None),
            )
            proxy_node = _walkmesh_overlay_node_from_wok(source, label, offset)
            target_models = []
            for model in (self._current_model, self._active_viewport_model()):
                if model is not None and id(model) not in {id(existing) for existing in target_models}:
                    target_models.append(model)
            for model in target_models:
                extra_nodes = [
                    node
                    for node in (getattr(model, "_gr_extra_module_mesh_nodes", []) or [])
                    if not getattr(node, "_gr_walkmesh_overlay_proxy", False)
                ]
                extra_nodes.append(proxy_node)
                setattr(model, "_gr_extra_module_mesh_nodes", extra_nodes)
            self.viewport.load_walkmesh(source, world_offset=offset)
            overlay = getattr(getattr(self.viewport, "_renderer", None), "_walkmesh_overlay", None)
            if overlay is not None:
                setattr(overlay, "_gr_module_node", proxy_node)
            self._sync_walkmesh_overlay_visibility()
            self.viewport._request_render()
            if hasattr(self, "module_geometry_panel"):
                self.module_geometry_panel.show_model(self._active_viewport_model())
            if hasattr(self, "sprite_materials_panel"):
                self.sprite_materials_panel.set_model(self._active_viewport_model())
            self._log(f"Walkmesh loaded: {label}", "success")
            return True
        except Exception as exc:
            log.debug("walkmesh load failed for %s: %s", label, exc)
            return False
    def _on_module_meshes_selected_from_panel(self, nodes: list) -> None:
        selected = [node for node in (nodes or []) if node is not None]
        if selected and any(bool(getattr(node, "_gr_hidden", False)) for node in selected):
            return
        if hasattr(self, "viewport"):
            try:
                self.viewport.set_selected_meshes(selected, source="module mesh panel")
            except TypeError:
                self.viewport.set_selected_meshes(selected)

    def _refresh_mesh_visibility_render_state(self, reason: str) -> None:
        viewport = getattr(self, "viewport", None)
        if viewport is None:
            return
        refresh_scene_transforms = getattr(viewport, "refresh_scene_transforms", None)
        if callable(refresh_scene_transforms):
            refresh_scene_transforms(reason=reason)
            return
        gpu_renderer = getattr(viewport, "_gpu_renderer", None)
        invalidate_transform_cache = getattr(gpu_renderer, "invalidate_transform_cache", None)
        if callable(invalidate_transform_cache):
            invalidate_transform_cache(reason)
        refresh = getattr(viewport, "refresh_view", None)
        if callable(refresh):
            refresh()

    def _on_viewport_mesh_visibility_changed(self) -> None:
        if hasattr(self, "module_geometry_panel"):
            self.module_geometry_panel.refresh_module_mesh_rows()
        self._refresh_mesh_visibility_render_state("mesh visibility changed")

    def _on_module_mesh_visibility_changed(self) -> None:
        self._sync_walkmesh_overlay_visibility()
        self._refresh_mesh_visibility_render_state("module mesh visibility changed")

    def _on_sprite_material_selected(self, node) -> None:
        if node is None or bool(getattr(node, "_gr_hidden", False)):
            return
        if hasattr(self, "viewport"):
            self.viewport.set_selected_node(node, source="sprite materials panel")
        if hasattr(self, "module_geometry_panel"):
            self.module_geometry_panel.select_module_meshes([node])
        if hasattr(self, "properties_panel"):
            self.properties_panel.show_node(node)
    def _on_sprite_materials_changed(self, nodes: list) -> None:
        changed = [node for node in (nodes or []) if node is not None]
        if changed:
            data = self._load_sprite_material_overrides()
            model_key = self._sprite_model_key()
            models = data.setdefault("models", {})
            model_overrides = models.setdefault(model_key, {})
            for node in changed:
                node_key = self._sprite_node_key(node)
                if self._sprite_node_has_explicit_override(node):
                    model_overrides[node_key] = self._sprite_material_payload(node)
                else:
                    model_overrides.pop(node_key, None)
            if not model_overrides:
                models.pop(model_key, None)
            self._save_sprite_material_overrides()
        if hasattr(self, "viewport"):
            renderer = getattr(self.viewport, "_renderer", None)
            if renderer is not None and hasattr(renderer, "invalidate_node_cache"):
                renderer.invalidate_node_cache()
            gpu_renderer = getattr(self.viewport, "_gpu_renderer", None)
            if gpu_renderer is not None:
                for node in changed:
                    invalidate_node = getattr(gpu_renderer, "invalidate_node", None)
                    if callable(invalidate_node):
                        invalidate_node(node)
                invalidate_cache = getattr(gpu_renderer, "invalidate_node_cache", None)
                if callable(invalidate_cache):
                    invalidate_cache()
            self.viewport.refresh_view()
        if hasattr(self, "module_geometry_panel"):
            self.module_geometry_panel.refresh_module_mesh_rows()
        self._invalidate_renderer_resources("sprite material render settings changed")
    def _sync_walkmesh_overlay_visibility(self) -> None:
        renderer = getattr(getattr(self, "viewport", None), "_renderer", None)
        overlay = getattr(renderer, "_walkmesh_overlay", None)
        proxy_node = getattr(overlay, "_gr_module_node", None)
        if renderer is None or overlay is None or proxy_node is None:
            return
        visible = not bool(getattr(proxy_node, "_gr_hidden", False))
        try:
            renderer.show_walkmesh = visible
        except Exception:
            pass
        button = getattr(getattr(self, "viewport", None), "walkmesh_button", None)
        if button is not None:
            try:
                button.setChecked(visible)
            except Exception:
                pass
