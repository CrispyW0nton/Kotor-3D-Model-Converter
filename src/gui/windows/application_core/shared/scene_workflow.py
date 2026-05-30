"""KMAX scene and scene-object workflows for the main window."""

from __future__ import annotations

import copy
import json
import logging
import traceback
from pathlib import Path

try:
    from PySide6 import QtCore, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.core.scene.axis_mode import AxisMode
from src.core.scene.scene_resource_ref import SceneResourceRef
from src.gui.qt_lib.dialogs.qt_settings_dialog import save_settings

log = logging.getLogger(__name__)


class SceneWorkflowMixin:
    """KMAX scene file, object selection, sprite-material, and pivot behavior."""

    def _scene_path_filter(self) -> str:
        return "GhostRigger Scene (*.kmax);;All files (*.*)"

    def _new_scene(self):
        if not self._prompt_save_dirty_scene():
            return
        game = str(self.settings_data.get("default_game") or "K1").upper()
        self.scene_manager.create_new_scene(game=game)
        self._scene_texture_dirs.clear()
        self._set_model_internal(None)
        self._refresh_scene_view()
        self.scene_manager.active_scene.mark_clean()
        self._update_scene_chrome()
        bus = getattr(self, "integration_event_bus", None)
        if bus is not None:
            bus.record_scene_update("scene_cleared")
        self._invalidate_renderer_resources("new empty scene")
        self._log("New empty scene created.", "success")

    def _close_scene(self):
        self._new_scene()

    def _open_scene(self):
        if not self._prompt_save_dirty_scene():
            return
        start_dir = str(self.settings_data.get("last_kmax_dir") or self.app_root)
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Scene", start_dir, self._scene_path_filter())
        if path:
            self._load_scene_from_path(path)

    def _load_scene_from_path(self, path: str) -> bool:
        try:
            scene = self.scene_manager.load_kmax(path)
            self.settings_data["last_kmax_dir"] = str(Path(path).parent)
            self._add_recent_scene(path)
            self._load_runtime_models_for_scene()
            selected = self.scene_manager.get_selected_objects()
            if selected:
                self._current_model = selected[-1].metadata.get("_runtime_model")
            self._refresh_scene_view()
            self.scene_manager.active_scene.mark_clean()
            self._update_scene_chrome()
            bus = getattr(self, "integration_event_bus", None)
            if bus is not None:
                bus.record_scene_update("scene_loaded", scene)
            self._invalidate_renderer_resources("scene loaded")
            self._log(f"Scene loaded: {path}", "success")
            return True
        except Exception:
            self._log(f"Scene load failed:\n{traceback.format_exc()}", "error")
            QtWidgets.QMessageBox.warning(self, "Open Scene", "Could not open the selected .kmax scene.")
            return False

    def _save_scene(self) -> bool:
        scene = self.scene_manager.active_scene
        if not scene.path:
            return self._save_scene_as()
        try:
            self.scene_manager.save_kmax(scene.path)
            self._add_recent_scene(scene.path)
            self._update_scene_chrome()
            self._log(f"Scene saved: {scene.path}", "success")
            return True
        except Exception:
            self._log(f"Scene save failed:\n{traceback.format_exc()}", "error")
            QtWidgets.QMessageBox.warning(self, "Save Scene", "Could not save the current scene.")
            return False

    def _save_scene_as(self) -> bool:
        scene = self.scene_manager.active_scene
        start_dir = str(self.settings_data.get("last_kmax_dir") or self.app_root)
        default_name = Path(scene.path).name if scene.path else "untitled_scene.kmax"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Scene As",
            str(Path(start_dir) / default_name),
            self._scene_path_filter(),
        )
        if not path:
            return False
        if not path.lower().endswith(".kmax"):
            path = f"{path}.kmax"
        try:
            self.scene_manager.save_kmax_as(path)
            self.settings_data["last_kmax_dir"] = str(Path(path).parent)
            self._add_recent_scene(path)
            self._update_scene_chrome()
            self._log(f"Scene saved: {path}", "success")
            return True
        except Exception:
            self._log(f"Scene save-as failed:\n{traceback.format_exc()}", "error")
            QtWidgets.QMessageBox.warning(self, "Save Scene As", "Could not save the current scene.")
            return False

    def _export_scene(self):
        scene = self.scene_manager.active_scene
        if not scene.objects:
            QtWidgets.QMessageBox.information(self, "Export Scene", "The current scene is empty.")
            return
        QtWidgets.QMessageBox.information(
            self,
            "Export Scene",
            "Scene export will use the existing model exporters for the active model in this first KMAX bridge.",
        )

    def _prompt_save_dirty_scene(self) -> bool:
        if not self.scene_manager.is_dirty():
            return True
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("Save Scene")
        box.setText("Save changes to current scene?")
        save_button = box.addButton("Save", QtWidgets.QMessageBox.AcceptRole)
        discard_button = box.addButton("Don't Save", QtWidgets.QMessageBox.DestructiveRole)
        cancel_button = box.addButton("Cancel", QtWidgets.QMessageBox.RejectRole)
        box.setDefaultButton(save_button)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save_button:
            return self._save_scene()
        if clicked is discard_button:
            return True
        return clicked is not cancel_button and False

    def _add_recent_scene(self, path: str) -> None:
        scene_path = str(Path(path))
        recent = [item for item in self.settings_data.get("recent_scenes", []) if item != scene_path]
        recent.insert(0, scene_path)
        self.settings_data["recent_scenes"] = recent[:10]
        try:
            save_settings(self.settings_path, self.settings_data)
        except Exception:
            log.debug("Could not persist recent scenes", exc_info=True)
        self._rebuild_recent_scenes_menu()

    def _rebuild_recent_scenes_menu(self) -> None:
        menu = getattr(self, "recent_scenes_menu", None)
        if menu is None:
            return
        menu.clear()
        recent = [str(path) for path in self.settings_data.get("recent_scenes", []) if path]
        if not recent:
            action = menu.addAction("No Recent Scenes")
            action.setEnabled(False)
            return
        for path in recent[:10]:
            action = menu.addAction(Path(path).name)
            action.setToolTip(path)
            action.triggered.connect(lambda _checked=False, p=path: self._open_recent_scene(p))

    def _open_recent_scene(self, path: str) -> None:
        if not Path(path).exists():
            QtWidgets.QMessageBox.information(self, "Recent Scene", "That scene file no longer exists.")
            return
        if self._prompt_save_dirty_scene():
            self._load_scene_from_path(path)

    def _load_runtime_models_for_scene(self) -> None:
        self._scene_texture_dirs.clear()
        for obj in self.scene_manager.active_scene.objects:
            if obj.object_type != "model":
                continue
            try:
                model, texture_dir = self._load_model_for_resource_ref(obj.source_ref)
                if model is not None:
                    obj.metadata["_runtime_model"] = model
                    if texture_dir and texture_dir not in self._scene_texture_dirs:
                        self._scene_texture_dirs.append(texture_dir)
                else:
                    obj.metadata["unresolved"] = True
            except Exception as exc:
                obj.metadata["unresolved"] = True
                obj.metadata["load_error"] = str(exc)
                self._log(f"Scene object unresolved: {obj.name} ({exc})", "warning")

    def _load_model_for_resource_ref(self, ref: SceneResourceRef):
        if ref.source_path:
            path = Path(ref.source_path)
            if not path.exists():
                return None, ""
            model = self._load_model_from_path_sync(path, ref.game)
            return model, str(path.parent)
        if ref.resref:
            mgr = self._get_resource_manager()
            if mgr is None:
                return None, ""
            from src.core.qt_core.game.kotor_loader import load_model_from_bytes
            from src.core.qt_core.geometry.model_data import GameVersion

            game = (ref.game or "K1").upper()
            mdl = mgr.get_mdl(ref.resref, game)
            if not mdl:
                return None, ""
            mdx = mgr.get_mdx(ref.resref, game) or b""
            model = load_model_from_bytes(mdl, mdx, game_version=GameVersion.K2 if game == "K2" else GameVersion.K1)
            if model is not None:
                model.game_version = GameVersion.K2 if game == "K2" else GameVersion.K1
            return model, ""
        return None, ""

    def _load_model_from_path_sync(self, path: Path, game: str = ""):
        raw = path.read_bytes()
        first16 = raw[:16]
        printable_count = sum(1 for byte in first16 if 0x20 <= byte <= 0x7E or byte in (0x09, 0x0A, 0x0D))
        is_ascii_mdl = printable_count >= 10 or raw[:8].lstrip(b"\x00").startswith(b"newmodel") or raw[:2] in (b"#\x20", b"# ")
        if is_ascii_mdl:
            from src.core.qt_core.mdl.mdl_parser import MDLAsciiParser

            model = MDLAsciiParser().parse(raw.decode("utf-8", errors="replace").splitlines())
            model.mdl_path = str(path)
            model.mdx_path = ""
            return model
        from src.core.qt_core.game.kotor_loader import load_model_from_bytes
        from src.core.qt_core.geometry.model_data import GameVersion

        mdx_path = path.with_suffix(".mdx")
        mdx = mdx_path.read_bytes() if mdx_path.exists() else b""
        game_version = GameVersion.K2 if str(game).upper() == "K2" else GameVersion.K1
        model = load_model_from_bytes(raw, mdx, game_version=game_version)
        if model is not None:
            model.mdl_path = str(path)
            model.mdx_path = str(mdx_path) if mdx else ""
            model.game_version = game_version
        return model

    def _refresh_scene_view(self) -> None:
        scene = self.scene_manager.active_scene
        for obj in getattr(scene, "objects", []) or []:
            model = (getattr(obj, "metadata", {}) or {}).get("_runtime_model")
            if model is not None:
                self._apply_sprite_material_overrides(model)
        if hasattr(self, "viewport"):
            self._configure_viewport_resources()
            self.viewport.load_scene_instances(
                scene.objects,
                scene_name=scene.display_name,
                texture_dirs=self._scene_texture_dirs,
            )
        if hasattr(self, "scene_outliner_panel"):
            self.scene_outliner_panel.set_scene(scene)
        self._refresh_scene_animation_entries()
        self._update_scene_chrome()
        self._refresh_adjust_pivot_panel()

    def _active_viewport_model(self):
        viewport = getattr(self, "viewport", None)
        model = getattr(viewport, "model", None) if viewport is not None else None
        return model or getattr(self, "_current_model", None)

    def _sprite_persistence_path(self) -> Path:
        return self.app_root / "config" / "sprite_material_overrides.json"

    def _load_sprite_material_overrides(self) -> dict:
        cached = getattr(self, "_sprite_material_overrides", None)
        if isinstance(cached, dict):
            return cached
        path = self._sprite_persistence_path()
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except Exception:
            log.warning("Could not read sprite material override file: %s", path, exc_info=True)
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("version", 1)
        data.setdefault("models", {})
        self._sprite_material_overrides = data
        return data

    def _save_sprite_material_overrides(self) -> None:
        data = self._load_sprite_material_overrides()
        path = self._sprite_persistence_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except Exception:
            log.warning("Could not save sprite material override file: %s", path, exc_info=True)

    def _sprite_model_key(self, model=None) -> str:
        model = model or self._active_viewport_model()
        game = str(getattr(self, "_current_game", "") or self._infer_game_from_model(model) or "").upper()
        name = str(getattr(model, "name", "") or getattr(model, "resref", "") or getattr(model, "resource_name", "") or "").strip()
        path = str(getattr(self, "_model_path", "") or "").strip()
        if ":" in path and not name:
            name = path.split(":", 1)[-1]
        return f"{game}:{name or path or 'model'}".lower()

    @staticmethod
    def _sprite_node_key(node) -> str:
        texture = str(getattr(node, "texture", "") or "")
        if not texture:
            names = getattr(node, "texture_names", None) or []
            texture = str(names[0]) if names else ""
        return f"{getattr(node, 'name', '')}|{texture}".lower()

    @staticmethod
    def _sprite_material_payload(node) -> dict:
        return {
            "mesh": str(getattr(node, "name", "") or ""),
            "texture": str(getattr(node, "texture", "") or ""),
            "category": str(getattr(node, "_gr_sprite_category", "") or ""),
            "hidden": bool(getattr(node, "_gr_hidden", False)),
            "render_mode": str(getattr(node, "_gr_sprite_render_mode", "") or ""),
            "txi_blending": int(getattr(node, "txi_blending", 0) or 0),
            "txi_alpha_test": float(getattr(node, "txi_alpha_test", 0.0) or 0.0),
            "txi_wateralpha": float(getattr(node, "txi_wateralpha", 1.0) or 1.0),
            "txi_decal": bool(getattr(node, "txi_decal", False)),
            "transparency_hint": int(getattr(node, "transparency_hint", 0) or 0),
            "alpha": float(getattr(node, "alpha", 1.0) or 1.0),
            "sprite_alpha_source": str(getattr(node, "_gr_sprite_alpha_source", "") or ""),
            "sprite_glow": float(getattr(node, "_gr_sprite_glow", 0.0) or 0.0),
        }

    @staticmethod
    def _sprite_node_has_explicit_override(node) -> bool:
        if bool(getattr(node, "_gr_hidden", False)):
            return True
        if str(getattr(node, "_gr_sprite_category", "") or ""):
            return True
        if str(getattr(node, "_gr_sprite_render_mode", "") or ""):
            return True
        if str(getattr(node, "_gr_sprite_alpha_source", "") or ""):
            return True
        try:
            if abs(float(getattr(node, "_gr_sprite_glow", 0.0) or 0.0)) > 0.001:
                return True
        except Exception:
            pass
        original = getattr(node, "_gr_sprite_original_material", None)
        if isinstance(original, dict):
            for attr in ("txi_blending", "txi_alpha_test", "txi_wateralpha", "txi_decal", "transparency_hint", "alpha"):
                if getattr(node, attr, None) != original.get(attr):
                    return True
        return False

    def _iter_sprite_mesh_nodes(self, model) -> list:
        if model is None:
            return []
        sources = []
        if hasattr(model, "mesh_nodes"):
            sources.append(model.mesh_nodes() or [])
        if hasattr(model, "all_nodes"):
            sources.append(model.all_nodes() or [])
        sources.append(getattr(model, "_gr_extra_module_mesh_nodes", []) or [])
        result = []
        seen: set[int] = set()
        for source in sources:
            for node in source:
                if node is None or id(node) in seen or not getattr(node, "is_mesh", False):
                    continue
                seen.add(id(node))
                result.append(node)
        return result

    def _apply_sprite_material_overrides(self, model) -> int:
        data = self._load_sprite_material_overrides()
        model_overrides = (data.get("models") or {}).get(self._sprite_model_key(model), {})
        if not isinstance(model_overrides, dict):
            return 0
        applied = 0
        for node in self._iter_sprite_mesh_nodes(model):
            payload = model_overrides.get(self._sprite_node_key(node))
            if not isinstance(payload, dict):
                continue
            if not hasattr(node, "_gr_sprite_original_material"):
                setattr(node, "_gr_sprite_original_material", {
                    name: getattr(node, name, None)
                    for name in ("txi_blending", "txi_alpha_test", "txi_wateralpha", "txi_decal", "transparency_hint", "alpha", "_gr_sprite_render_mode", "_gr_sprite_alpha_source", "_gr_sprite_glow")
                })
            setattr(node, "_gr_sprite_category", str(payload.get("category") or ""))
            setattr(node, "_gr_hidden", bool(payload.get("hidden", False)))
            setattr(node, "_gr_sprite_render_mode", str(payload.get("render_mode") or ""))
            setattr(node, "txi_blending", int(payload.get("txi_blending", getattr(node, "txi_blending", 0)) or 0))
            setattr(node, "txi_alpha_test", float(payload.get("txi_alpha_test", getattr(node, "txi_alpha_test", 0.0)) or 0.0))
            setattr(node, "txi_wateralpha", float(payload.get("txi_wateralpha", getattr(node, "txi_wateralpha", 1.0)) or 1.0))
            setattr(node, "txi_decal", bool(payload.get("txi_decal", getattr(node, "txi_decal", False))))
            setattr(node, "transparency_hint", int(payload.get("transparency_hint", getattr(node, "transparency_hint", 0)) or 0))
            setattr(node, "alpha", float(payload.get("alpha", getattr(node, "alpha", 1.0)) or 1.0))
            setattr(node, "_gr_sprite_alpha_source", str(payload.get("sprite_alpha_source") or ""))
            setattr(node, "_gr_sprite_glow", float(payload.get("sprite_glow", 0.0) or 0.0))
            setattr(node, "_gr_revision", int(getattr(node, "_gr_revision", 0) or 0) + 1)
            applied += 1
        return applied

    def _sync_lighting_helper_visibility_to_viewport(self) -> None:
        panel = getattr(self, "lighting_panel", None)
        viewport = getattr(self, "viewport", None)
        if panel is None or viewport is None or not hasattr(viewport, "set_light_helper_visibility"):
            return
        helpers = bool(getattr(getattr(panel, "show_helpers_check", None), "isChecked", lambda: True)())
        volumes = bool(getattr(getattr(panel, "show_volumes_check", None), "isChecked", lambda: False)())
        viewport.set_light_helper_visibility(helpers, volumes)

    def _refresh_scene_animation_entries(self) -> None:
        panel = getattr(self, "content_browser_panel", getattr(self, "animation_library_panel", None))
        if panel is None or not hasattr(panel, "set_scene_animation_entries"):
            return
        panel.set_scene_animation_entries(self._collect_scene_animation_entries())

    def _collect_scene_animation_entries(self) -> list[dict]:
        entries: list[dict] = []
        for obj in self.scene_manager.active_scene.objects:
            model = (getattr(obj, "metadata", {}) or {}).get("_runtime_model")
            if model is None:
                continue
            model_name = str(getattr(model, "name", "") or getattr(obj, "name", "") or "model")
            game = str(getattr(getattr(obj, "source_ref", None), "game", "") or self._infer_game_from_model(model) or "").upper()
            resref = str(getattr(getattr(obj, "source_ref", None), "resref", "") or "")
            for anim in getattr(model, "animations", []) or []:
                anim_name = str(getattr(anim, "name", "") or "").strip()
                if not anim_name:
                    continue
                length = float(getattr(anim, "length", 0.0) or 0.0)
                entries.append(
                    {
                        "game": game,
                        "model": model_name,
                        "resref": resref,
                        "object_id": obj.id,
                        "object_name": obj.name,
                        "animation": anim_name,
                        "frames": int(round(length * 30.0)) if length else "",
                        "length": f"{length:.3f}" if length else "",
                        "source": f"Scene: {obj.name}",
                    }
                )
        return entries

    def _activate_scene_object_model(self, obj) -> None:
        metadata = getattr(obj, "metadata", {}) or {}
        model = metadata.get("_runtime_model")
        if model is None:
            return
        bas_preview = metadata.get("_runtime_bas_preview_model")
        bas_body = metadata.get("_runtime_bas_body_model") or getattr(self, "_bas_body_model", None)
        is_bas_preview = bool(
            (bas_preview is not None and model is bas_preview)
            or (metadata.get("body_attachment_system") or {}).get("active")
        )
        body_source_active = self._animation_source_key() == "body" if hasattr(self, "_animation_source_key") else True
        preserve_bas_body_animation = bool(is_bas_preview and body_source_active and bas_body is not None)
        self._current_model = bas_body if preserve_bas_body_animation else model
        if hasattr(self, "animations_panel"):
            if not preserve_bas_body_animation:
                self._load_animation_panel_model(model)
        if hasattr(self, "animation_retarget_panel"):
            if preserve_bas_body_animation:
                return
            game = str(getattr(getattr(obj, "source_ref", None), "game", "") or self._infer_game_from_model(model)).upper()
            self.animation_retarget_panel.set_texture_dir(self._texture_dir)
            if self._supports_animation_retarget_target(model):
                mgr = self._get_resource_manager()
                if mgr is not None:
                    self.animation_retarget_panel.set_target_resource_context(mgr, game)
                self._retarget_target_model = model
                self.animation_retarget_panel.set_target_model(model, game)

    def _update_scene_chrome(self) -> None:
        scene = self.scene_manager.active_scene
        dirty = " *" if scene.dirty else ""
        self.setWindowTitle(f"GhostRigger - {scene.display_name}{dirty}")
        objects = len(scene.objects)
        selected = len(self.scene_manager.get_selected_objects())
        models = len(scene.model_instances)
        if hasattr(self, "model_pill"):
            self.model_pill.setText(f"// {scene.display_name}{dirty}")
            status = "Empty Scene" if objects == 0 else f"Objects: {objects} | Selected: {selected}"
            self.model_pill.setToolTip(f"{status} | Models: {models}")
        try:
            self.statusBar().showMessage("Empty Scene" if objects == 0 else f"Objects: {objects} | Selected: {selected} | Models: {models}")
        except Exception:
            pass

    def _select_scene_object(self, object_id: str) -> None:
        if getattr(self, "_syncing_scene_skeleton_selection", False):
            return
        self._syncing_scene_skeleton_selection = True
        try:
            self._select_scene_object_impl(object_id)
        finally:
            self._syncing_scene_skeleton_selection = False

    def _select_scene_object_impl(self, object_id: str) -> None:
        for obj in self.scene_manager.active_scene.objects:
            obj.selected = obj.id == object_id
        if hasattr(self, "viewport"):
            self.viewport.select_scene_object(object_id)
        obj = next((item for item in self.scene_manager.active_scene.objects if item.id == object_id), None)
        if obj is not None:
            self._activate_scene_object_model(obj)
            self._sync_skeleton_root_for_scene_object(obj)
            if hasattr(self, "properties_panel"):
                show_scene_object = getattr(self.properties_panel, "show_scene_object", None)
                if callable(show_scene_object):
                    show_scene_object(obj)
        self._update_scene_chrome()
        self._refresh_adjust_pivot_panel()
        bus = getattr(self, "integration_event_bus", None)
        if bus is not None:
            bus.selectionChanged.emit(obj)
            bus.record_tool_action("scene_information", f"selected scene object: {object_id}")
        if hasattr(self, "scene_outliner_panel"):
            self.scene_outliner_panel.set_scene(self.scene_manager.active_scene)

    def _runtime_model_for_scene_object(self, obj):
        return (getattr(obj, "metadata", {}) or {}).get("_runtime_model")

    def _scene_object_for_runtime_node(self, node):
        if node is None:
            return None
        for obj in self.scene_manager.active_scene.objects:
            if getattr(obj, "object_type", "") != "model":
                continue
            model = self._runtime_model_for_scene_object(obj)
            if model is None:
                continue
            if node is getattr(model, "root_node", None):
                return obj
            try:
                nodes = list(model.all_nodes()) if hasattr(model, "all_nodes") else []
            except Exception:
                nodes = []
            if any(candidate is node for candidate in nodes):
                return obj
        return None

    def _sync_skeleton_root_for_scene_object(self, obj) -> None:
        panel = getattr(self, "skeleton_panel", None)
        if panel is None or obj is None:
            return
        model = self._runtime_model_for_scene_object(obj)
        root = getattr(model, "root_node", None)
        if model is None or root is None:
            return
        try:
            if getattr(panel, "_current_model", None) is not model:
                panel.load_model(model)
            panel.select_node(root, emit=False)
        except Exception:
            log.debug("Could not sync scene object root into skeleton panel", exc_info=True)

    def _on_skeleton_node_selected(self, node) -> None:
        if hasattr(self, "viewport"):
            self.viewport.set_selected_node(node, source="nodes panel")

    def _on_scene_outliner_helper_node_selected(self, node) -> None:
        if node is None:
            return
        obj = self._scene_object_for_runtime_node(node)
        if obj is not None:
            self._activate_scene_object_model(obj)
        if hasattr(self, "viewport"):
            self.viewport.set_selected_node(node, source="scene outliner helper")
        if hasattr(self, "properties_panel"):
            self.properties_panel.show_node(node)
        if hasattr(self, "skeleton_panel") and obj is not None:
            model = self._runtime_model_for_scene_object(obj)
            try:
                if model is not None and getattr(self.skeleton_panel, "_current_model", None) is not model:
                    self.skeleton_panel.load_model(model)
                self.skeleton_panel.select_node(node, emit=False)
            except Exception:
                log.debug("Could not sync scene outliner helper into skeleton panel", exc_info=True)

    def _on_scene_outliner_light_node_selected(self, node) -> None:
        if node is None:
            return
        obj = self._scene_object_for_runtime_node(node)
        if obj is not None:
            self._activate_scene_object_model(obj)
        if hasattr(self, "viewport"):
            self.viewport.set_selected_node(node, source="scene outliner light")
        if hasattr(self, "lighting_panel"):
            self.lighting_panel.select_light(node)
        if hasattr(self, "properties_panel"):
            self.properties_panel.show_node(node)

    def _delete_scene_object(self, object_id: str) -> None:
        self.scene_manager.remove_object(object_id)
        self._refresh_scene_view()

    def _duplicate_scene_object(self, object_id: str) -> None:
        duplicate = self.scene_manager.duplicate_object(object_id)
        if duplicate is not None:
            source = next((obj for obj in self.scene_manager.active_scene.objects if obj.id == object_id), None)
            if source is not None and "_runtime_model" in source.metadata:
                duplicate.metadata["_runtime_model"] = copy.deepcopy(source.metadata["_runtime_model"])
            duplicate.transform.position = (
                duplicate.transform.position[0] + 2.0,
                duplicate.transform.position[1],
                duplicate.transform.position[2],
            )
        self._refresh_scene_view()

    def _focus_scene_object(self, object_id: str) -> None:
        self._select_scene_object(object_id)
        self._call_viewport("frame_all")

    def _set_scene_object_visible(self, object_id: str, visible: bool) -> None:
        obj = next((item for item in self.scene_manager.active_scene.objects if item.id == object_id), None)
        if obj is not None:
            obj.visible = bool(visible)
            self.scene_manager.mark_dirty()
            self._refresh_scene_view()
            self._invalidate_renderer_resources("scene object visibility changed")

    def _set_scene_object_locked(self, object_id: str, locked: bool) -> None:
        obj = next((item for item in self.scene_manager.active_scene.objects if item.id == object_id), None)
        if obj is not None:
            obj.locked = bool(locked)
            self.scene_manager.mark_dirty()
            self._refresh_scene_view()
            self._refresh_adjust_pivot_panel()

    def _rename_scene_object(self, object_id: str, name: str) -> None:
        obj = next((item for item in self.scene_manager.active_scene.objects if item.id == object_id), None)
        if obj is not None and name.strip():
            obj.name = name.strip()
            self.scene_manager.mark_dirty()
            self._refresh_scene_view()

    def _on_viewport_scene_node_selected(self, node) -> None:
        object_id = str(getattr(node, "_gr_scene_object_id", "") or "")
        if object_id:
            for obj in self.scene_manager.active_scene.objects:
                obj.selected = obj.id == object_id
            if hasattr(self, "scene_outliner_panel"):
                self.scene_outliner_panel.set_scene(self.scene_manager.active_scene)
            obj = next((item for item in self.scene_manager.active_scene.objects if item.id == object_id), None)
            if obj is not None:
                self._activate_scene_object_model(obj)
                self._sync_skeleton_root_for_scene_object(obj)
                show_scene_object = getattr(self.properties_panel, "show_scene_object", None)
                if callable(show_scene_object):
                    show_scene_object(obj)
        else:
            for obj in self.scene_manager.active_scene.objects:
                obj.selected = False
        self._update_scene_chrome()
        self._refresh_adjust_pivot_panel()
        bus = getattr(self, "integration_event_bus", None)
        if bus is not None:
            bus.selectionChanged.emit(obj if object_id else node)
            bus.record_tool_action("viewport", "viewport selection changed")

    def _on_viewport_scene_node_moved(self, node) -> None:
        object_id = str(getattr(node, "_gr_scene_object_id", "") or "")
        if not object_id:
            return
        rotation = None
        scale = None
        try:
            rotation = self.viewport._quat_to_euler_degrees(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0)))
        except Exception:
            rotation = None
        try:
            scale = tuple(float(v) for v in getattr(node, "_gr_scale", (1.0, 1.0, 1.0))[:3])
        except Exception:
            scale = None
        self.scene_manager.update_object_transform(
            object_id,
            position=tuple(float(v) for v in getattr(node, "position", (0.0, 0.0, 0.0))[:3]),
            rotation=rotation,
            scale=scale,
        )
        try:
            pivot_local = self.viewport._pivot_local_from_node(node)
            pivot_rotation = self.viewport._quat_to_euler_degrees(getattr(node, "_gr_pivot_rotation", (0.0, 0.0, 0.0, 1.0)))
            self.scene_manager.update_object_pivot(
                object_id,
                position_local=pivot_local,
                rotation_local=pivot_rotation,
            )
        except Exception:
            log.debug("Could not persist scene pivot edit", exc_info=True)
        self._update_scene_chrome()
        self._refresh_adjust_pivot_panel()
        self._record_transform_event(node)
        self._record_pivot_event(node)
        if hasattr(self, "scene_outliner_panel"):
            self.scene_outliner_panel.set_scene(self.scene_manager.active_scene)

    def _selected_scene_objects(self):
        return list(self.scene_manager.get_selected_objects())

    def _refresh_adjust_pivot_panel(self) -> None:
        panel = getattr(self, "adjust_pivot_panel", None)
        if panel is None:
            return
        selected = self._selected_scene_objects()
        locked = any(bool(getattr(obj, "locked", False)) for obj in selected)
        hierarchy_available = any(bool(getattr(obj, "group_id", "")) for obj in selected)
        panel.set_selection_state(len(selected), locked=locked, hierarchy_available=hierarchy_available)
        viewport = getattr(self, "viewport", None)
        if viewport is not None and hasattr(viewport, "pivot_edit_mode"):
            panel.set_pivot_mode(viewport.pivot_edit_mode())

    def _set_pivot_edit_mode(self, mode: str) -> None:
        if mode == "affect_hierarchy_only":
            selected = self._selected_scene_objects()
            if not any(bool(getattr(obj, "group_id", "")) for obj in selected):
                self.statusBar().showMessage("Hierarchy mode is not available for this selection.")
                self._refresh_adjust_pivot_panel()
                return
        if hasattr(self, "viewport"):
            self.viewport.set_pivot_edit_mode(mode)
        self._record_renderer_tool_action("adjust_pivot", f"pivot edit mode: {mode}")
        self._refresh_adjust_pivot_panel()

    def _persist_axis_mode(self, mode) -> None:
        resolved = AxisMode.from_value(mode)
        self.settings_data["last_axis_mode"] = resolved.value
        if resolved is not AxisMode.PICK:
            self.settings_data.pop("picked_reference_object_id", None)
        try:
            save_settings(self.settings_path, self.settings_data)
        except Exception:
            log.debug("Could not persist axis mode", exc_info=True)

    def _runtime_bounds_center_local(self, obj) -> tuple[float, float, float] | None:
        model = (getattr(obj, "metadata", {}) or {}).get("_runtime_model")
        if model is None:
            return None
        try:
            if hasattr(model, "compute_bounds"):
                model.compute_bounds()
            bb_min = tuple(float(v) for v in getattr(model, "bb_min")[:3])
            bb_max = tuple(float(v) for v in getattr(model, "bb_max")[:3])
            return (
                (bb_min[0] + bb_max[0]) * 0.5,
                (bb_min[1] + bb_max[1]) * 0.5,
                (bb_min[2] + bb_max[2]) * 0.5,
            )
        except Exception:
            return None

    def _apply_pivot_action(self, action: str) -> None:
        selected = self._selected_scene_objects()
        if not selected:
            self.statusBar().showMessage("No object selected.")
            self._refresh_adjust_pivot_panel()
            return
        changed = False
        for obj in selected:
            if bool(getattr(obj, "locked", False)):
                continue
            if action == "center_to_object":
                center = self._runtime_bounds_center_local(obj)
                if center is None:
                    self.statusBar().showMessage("Center to Object is unavailable: selected object has no bounds.")
                    continue
                changed = self.scene_manager.update_object_pivot(obj.id, position_local=center) or changed
            elif action == "align_to_object":
                changed = self.scene_manager.update_object_pivot(obj.id, rotation_local=obj.transform.rotation) or changed
            elif action == "align_to_world":
                changed = self.scene_manager.update_object_pivot(obj.id, rotation_local=(0.0, 0.0, 0.0)) or changed
            elif action == "reset_pivot":
                changed = self.scene_manager.update_object_pivot(
                    obj.id,
                    position_local=(0.0, 0.0, 0.0),
                    rotation_local=(0.0, 0.0, 0.0),
                ) or changed
        if changed:
            self._refresh_scene_view()
            self._refresh_adjust_pivot_panel()
            self._update_scene_chrome()
            self._record_pivot_event(selected[0] if selected else None)
            self._invalidate_renderer_resources(f"pivot changed: {action}")
