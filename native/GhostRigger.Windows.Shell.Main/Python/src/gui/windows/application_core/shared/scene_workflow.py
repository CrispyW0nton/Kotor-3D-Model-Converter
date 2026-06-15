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
        self._create_new_scene_from_ipc()

    def _create_new_scene_from_ipc(self, game: str = "") -> bool:
        requested_game = str(game or "").strip().upper()
        game = str(self.settings_data.get("default_game") or "K1").upper()
        if requested_game in {"K1", "K2"}:
            game = requested_game
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
        return True

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

    def _open_scene_from_ipc(self, path: str, *, force: bool = False) -> bool:
        scene_path = Path(str(path or "")).expanduser()
        if not scene_path.is_absolute():
            scene_path = (Path.cwd() / scene_path).resolve()
        if not scene_path.exists():
            self._log(f"IPC open_scene: not found {scene_path}", "warning")
            return False
        if not force and not self._prompt_save_dirty_scene():
            self._log("IPC open_scene cancelled by dirty-scene prompt.", "warning")
            return False
        return self._load_scene_from_path(str(scene_path))

    def _save_scene(self) -> bool:
        scene = self.scene_manager.active_scene
        if not scene.path:
            return self._save_scene_as()
        try:
            self._sync_active_scene_sprite_material_overrides()
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
            self._sync_active_scene_sprite_material_overrides()
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

    def _save_scene_from_ipc(self, path: str = "") -> bool:
        scene = self.scene_manager.active_scene
        target = str(path or "").strip()
        if not target:
            if not scene.path:
                self._log("IPC save_scene: no scene path supplied.", "warning")
                return False
            return self._save_scene()
        scene_path = Path(target).expanduser()
        if not scene_path.is_absolute():
            scene_path = (Path.cwd() / scene_path).resolve()
        if scene_path.suffix.lower() != ".kmax":
            scene_path = scene_path.with_suffix(".kmax")
        try:
            self._sync_active_scene_sprite_material_overrides()
            self.scene_manager.save_kmax_as(scene_path)
            self.settings_data["last_kmax_dir"] = str(scene_path.parent)
            self._add_recent_scene(str(scene_path))
            self._update_scene_chrome()
            self._log(f"IPC save_scene: {scene_path}", "success")
            return True
        except Exception:
            self._log(f"IPC save_scene failed:\n{traceback.format_exc()}", "error")
            return False

    def _find_scene_object_for_ipc(self, object_id: str = "", name: str = ""):
        object_id = str(object_id or "").strip()
        name = str(name or "").strip()
        name_key = name.lower()
        for obj in self.scene_manager.active_scene.objects:
            if object_id and str(getattr(obj, "id", "") or "") == object_id:
                return obj
            if name_key and str(getattr(obj, "name", "") or "").lower() == name_key:
                return obj
        return None

    def _create_scene_camera_from_ipc(self, camera_type: str = "Cinematic Camera", name: str = "", *, make_active: bool = False) -> bool:
        obj = self._create_scene_camera_object(
            str(camera_type or "Cinematic Camera"),
            make_active=bool(make_active),
            name=str(name or ""),
        )
        if obj is None:
            self._log("IPC create_scene_camera failed.", "warning")
            return False
        self._log(f"IPC create_scene_camera: {obj.name}", "success")
        return True

    def _create_scene_light_from_ipc(self, light_type: str = "point", name: str = "") -> bool:
        obj = self._create_scene_light_object(str(light_type or "point"), name=str(name or ""))
        if obj is None:
            self._log("IPC create_scene_light failed.", "warning")
            return False
        self._log(f"IPC create_scene_light: {obj.name}", "success")
        return True

    def _select_scene_object_from_ipc(self, object_id: str = "", name: str = "") -> bool:
        obj = self._find_scene_object_for_ipc(object_id, name)
        if obj is None:
            self._log(f"IPC select_scene_object: not found {object_id or name or '<empty>'}", "warning")
            return False
        self._select_scene_object(str(obj.id))
        self._log(f"IPC select_scene_object: {obj.name}", "success")
        return True

    def _set_scene_object_visibility_from_ipc(self, object_id: str = "", name: str = "", *, visible: bool = True) -> bool:
        obj = self._find_scene_object_for_ipc(object_id, name)
        if obj is None:
            self._log(f"IPC set_scene_object_visibility: not found {object_id or name or '<empty>'}", "warning")
            return False
        self._set_scene_object_visible(str(obj.id), bool(visible))
        state = "visible" if bool(visible) else "hidden"
        self._log(f"IPC set_scene_object_visibility: {obj.name} {state}", "success")
        return True

    def _ipc_scene_object_summary(self, obj) -> dict:
        if obj is None:
            return {}
        transform = getattr(obj, "transform", None)
        metadata = dict(getattr(obj, "metadata", {}) or {})
        payload = dict(metadata.get(str(getattr(obj, "object_type", "") or "")) or {})
        extra = {}
        if getattr(obj, "object_type", "") == "camera":
            for key in ("camera_type", "focal_length_mm", "field_of_view_degrees", "resolution_width", "resolution_height", "near_clip", "far_clip"):
                if key in payload:
                    extra[key] = payload[key]
        elif getattr(obj, "object_type", "") == "light":
            for key in ("type", "color", "radius", "intensity", "cone_angle", "enabled", "cast_shadows"):
                if key in payload:
                    extra[key] = payload[key]
        return {
            "id": str(getattr(obj, "id", "") or ""),
            "name": str(getattr(obj, "name", "") or ""),
            "type": str(getattr(obj, "object_type", "") or ""),
            "visible": bool(getattr(obj, "visible", True)),
            "locked": bool(getattr(obj, "locked", False)),
            "selected": bool(getattr(obj, "selected", False)),
            "position": list(getattr(transform, "position", ()) or ()),
            "properties": extra,
        }

    def _ipc_vector3(self, value):
        if not isinstance(value, (list, tuple)) or len(value) < 3:
            return None
        try:
            return (float(value[0]), float(value[1]), float(value[2]))
        except (TypeError, ValueError):
            return None

    def _apply_scene_object_properties_from_ipc(
        self,
        object_id: str = "",
        name: str = "",
        properties: dict | None = None,
    ) -> dict:
        obj = self._find_scene_object_for_ipc(object_id, name)
        if obj is None:
            self._log(f"IPC scene_object_properties: not found {object_id or name or '<empty>'}", "warning")
            return {"ok": False, "object": {}}
        payload = dict(properties or {})
        transform_updates = {}
        for key in ("position", "rotation", "scale"):
            vector = self._ipc_vector3(payload.pop(key, None))
            if vector is not None:
                transform_updates[key] = vector
        if transform_updates:
            self.scene_manager.update_object_transform(str(obj.id), **transform_updates)
        common = {}
        for key in ("visible", "locked"):
            if key in payload:
                common[key] = bool(payload.pop(key))
        if "name" in payload:
            common["name"] = str(payload.pop("name") or "").strip()
        object_type = str(getattr(obj, "object_type", "") or "")
        changed = bool(transform_updates or common)
        if object_type == "camera":
            allowed = {
                "camera_type",
                "enabled",
                "focal_length_mm",
                "field_of_view_degrees",
                "sensor_width_mm",
                "sensor_height_mm",
                "aperture_f_stop",
                "near_clip",
                "far_clip",
                "resolution_width",
                "resolution_height",
                "aspect_ratio_width",
                "aspect_ratio_height",
                "show_safe_frame",
                "show_letterbox",
                "letterbox_ratio",
                "focus_distance",
                "target_enabled",
                "target_position",
            }
            camera_changes = {key: value for key, value in payload.items() if key in allowed}
            if common or camera_changes:
                changed = self.scene_manager.update_camera_properties(str(obj.id), **common, **camera_changes) or changed
        elif object_type == "light":
            allowed = {
                "type",
                "enabled",
                "color",
                "radius",
                "intensity",
                "cone_angle",
                "area_size",
                "ambient_only",
                "cast_shadows",
                "affects_diffuse",
                "affects_specular",
                "affects_lightmap",
                "affects_environment",
                "group_id",
            }
            light_changes = {key: value for key, value in payload.items() if key in allowed}
            if common or light_changes:
                changed = self.scene_manager.update_light_properties(str(obj.id), **common, **light_changes) or changed
        elif common:
            if "name" in common:
                self.scene_manager.rename_object(str(obj.id), common["name"])
            if "visible" in common:
                self.scene_manager.set_object_visibility(str(obj.id), common["visible"])
            if "locked" in common:
                self.scene_manager.set_object_locked(str(obj.id), common["locked"])
            changed = True
        self._refresh_scene_view()
        result_obj = self._find_scene_object_for_ipc(str(obj.id), "")
        if result_obj is not None:
            self._select_scene_object(str(result_obj.id))
        self._log(f"IPC scene_object_properties: {getattr(result_obj, 'name', getattr(obj, 'name', 'object'))}", "success" if changed else "info")
        return {"ok": bool(changed), "object": self._ipc_scene_object_summary(result_obj or obj)}

    def _apply_scene_object_command_from_ipc(
        self,
        command: str,
        object_id: str = "",
        name: str = "",
        value: object = None,
    ) -> dict:
        key = str(command or "").strip().lower().replace("-", "_").replace(" ", "_")
        obj = self._find_scene_object_for_ipc(object_id, name)
        if obj is None:
            self._log(f"IPC scene_object_command {key}: not found {object_id or name or '<empty>'}", "warning")
            return {"ok": False, "command": key, "object": {}}

        if key in {"select", "activate"}:
            self._select_scene_object(str(obj.id))
            result_obj = self._find_scene_object_for_ipc(str(obj.id), "")
        elif key in {"focus", "frame", "frame_all"}:
            self._focus_scene_object(str(obj.id))
            result_obj = self._find_scene_object_for_ipc(str(obj.id), "")
        elif key in {"rename", "set_name"}:
            new_name = str(value or "").strip()
            if not new_name:
                self._log("IPC scene_object_command rename: missing value", "warning")
                return {"ok": False, "command": key, "object": self._ipc_scene_object_summary(obj)}
            self._rename_scene_object(str(obj.id), new_name)
            result_obj = self._find_scene_object_for_ipc(str(obj.id), "")
        elif key in {"duplicate", "copy"}:
            before_ids = {str(item.id) for item in self.scene_manager.active_scene.objects}
            self._duplicate_scene_object(str(obj.id))
            created = next(
                (
                    item for item in self.scene_manager.active_scene.objects
                    if str(getattr(item, "id", "") or "") not in before_ids
                ),
                None,
            )
            result_obj = created or self._find_scene_object_for_ipc(str(obj.id), "")
        elif key in {"delete", "remove"}:
            summary = self._ipc_scene_object_summary(obj)
            self._delete_scene_object(str(obj.id))
            self._log(f"IPC scene_object_command delete: {summary.get('name', '')}", "success")
            return {"ok": True, "command": key, "object": summary, "deleted": True}
        elif key in {"lock", "unlock", "set_locked"}:
            locked = key == "lock" if key in {"lock", "unlock"} else bool(value)
            self._set_scene_object_locked(str(obj.id), locked)
            result_obj = self._find_scene_object_for_ipc(str(obj.id), "")
        elif key in {"show", "hide", "visible", "set_visible"}:
            visible = key == "show" if key in {"show", "hide"} else bool(value)
            self._set_scene_object_visible(str(obj.id), visible)
            result_obj = self._find_scene_object_for_ipc(str(obj.id), "")
        else:
            self._log(f"IPC scene_object_command: unknown command {command}", "warning")
            return {"ok": False, "command": key, "object": self._ipc_scene_object_summary(obj)}

        summary = self._ipc_scene_object_summary(result_obj)
        self._log(f"IPC scene_object_command {key}: {summary.get('name', '')}", "success")
        return {"ok": True, "command": key, "object": summary}

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
            from src.core.game.kotor_loader import load_model_from_bytes
            from src.core.geometry.model_data import GameVersion

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
            from src.core.mdl.mdl_parser import MDLAsciiParser

            model = MDLAsciiParser().parse(raw.decode("utf-8", errors="replace").splitlines())
            model.mdl_path = str(path)
            model.mdx_path = ""
            return model
        from src.core.game.kotor_loader import load_model_from_bytes
        from src.core.geometry.model_data import GameVersion

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
                self._apply_scene_object_sprite_material_overrides(obj)
        if hasattr(self, "viewport"):
            self._configure_viewport_resources()
            self.viewport.load_scene_instances(
                scene.objects,
                scene_name=scene.display_name,
                texture_dirs=self._scene_texture_dirs,
            )
        if hasattr(self, "scene_outliner_panel"):
            self.scene_outliner_panel.set_scene(scene)
        active_model = self._active_viewport_model()
        if hasattr(self, "lighting_panel"):
            self.lighting_panel.set_model(active_model)
            self._sync_lighting_helper_visibility_to_viewport()
        if hasattr(self, "camera_panel") and hasattr(self, "viewport"):
            self.camera_panel.manager = self.viewport.camera_manager
            self.camera_panel.refresh()
        self._refresh_scene_animation_entries()
        self._update_scene_chrome()
        self._refresh_adjust_pivot_panel()
        self._refresh_sprite_materials_panel_context()

    def _active_viewport_model(self):
        viewport = getattr(self, "viewport", None)
        model = getattr(viewport, "model", None) if viewport is not None else None
        return model or getattr(self, "_current_model", None)

    def _selected_scene_model_object(self):
        scene_manager = getattr(self, "scene_manager", None)
        if scene_manager is None:
            return None
        selected = []
        try:
            selected = list(scene_manager.get_selected_objects() or [])
        except Exception:
            selected = []
        for obj in reversed(selected):
            if getattr(obj, "object_type", "") != "model":
                continue
            if self._runtime_model_for_scene_object(obj) is not None:
                return obj
        return None

    def _refresh_sprite_materials_panel_context(self) -> None:
        panel = getattr(self, "sprite_materials_panel", None)
        if panel is None:
            return
        obj = self._selected_scene_model_object()
        model = self._runtime_model_for_scene_object(obj) if obj is not None else self._active_viewport_model()
        if model is not None:
            self._apply_sprite_material_overrides(model)
            if obj is not None:
                self._apply_scene_object_sprite_material_overrides(obj)
        panel.set_model(model)

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

    def _save_sprite_material_overrides(self, data: dict | None = None) -> None:
        if data is None:
            data = self._load_sprite_material_overrides()
        else:
            data.setdefault("version", 1)
            data.setdefault("models", {})
            self._sprite_material_overrides = data
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
    def _apply_sprite_material_payload(node, payload: dict) -> None:
        if not isinstance(payload, dict):
            return
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

    def _scene_object_for_sprite_node(self, node):
        object_id = str(getattr(node, "_gr_scene_object_id", "") or "")
        if not object_id:
            return None
        return next(
            (
                obj for obj in getattr(self.scene_manager.active_scene, "objects", [])
                if str(getattr(obj, "id", "") or "") == object_id
            ),
            None,
        )

    def _sync_sprite_material_nodes_to_scene(self, nodes: list) -> list:
        changed = []
        for node in nodes or []:
            obj = self._scene_object_for_sprite_node(node)
            if obj is None:
                continue
            overrides = dict(getattr(obj, "material_overrides", {}) or {})
            sprite_overrides = dict(overrides.get("sprite_materials") or {})
            node_key = self._sprite_node_key(node)
            if self._sprite_node_has_explicit_override(node):
                sprite_overrides[node_key] = self._sprite_material_payload(node)
            else:
                sprite_overrides.pop(node_key, None)
            if sprite_overrides:
                overrides["sprite_materials"] = sprite_overrides
            else:
                overrides.pop("sprite_materials", None)
            if overrides != getattr(obj, "material_overrides", {}):
                obj.material_overrides = overrides
                changed.append(obj)
        return changed

    def _sync_active_scene_sprite_material_overrides(self) -> None:
        viewport = getattr(self, "viewport", None)
        model = getattr(viewport, "model", None) if viewport is not None else None
        if model is None:
            return
        self._sync_sprite_material_nodes_to_scene(self._iter_sprite_mesh_nodes(model))

    def _apply_scene_object_sprite_material_overrides(self, obj) -> int:
        model = (getattr(obj, "metadata", {}) or {}).get("_runtime_model")
        overrides = dict(getattr(obj, "material_overrides", {}) or {})
        sprite_overrides = overrides.get("sprite_materials") or {}
        if model is None or not isinstance(sprite_overrides, dict):
            return 0
        applied = 0
        for node in self._iter_sprite_mesh_nodes(model):
            payload = sprite_overrides.get(self._sprite_node_key(node))
            if isinstance(payload, dict):
                self._apply_sprite_material_payload(node, payload)
                applied += 1
        return applied

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
            self._apply_sprite_material_payload(node, payload)
            applied += 1
        return applied

    def _sync_lighting_helper_visibility_to_viewport(self) -> None:
        viewport = getattr(self, "viewport", None)
        if viewport is None or not hasattr(viewport, "set_light_helper_visibility"):
            return
        button = getattr(viewport, "light_helpers_button", None)
        enabled = bool(getattr(button, "isChecked", lambda: True)())
        viewport.set_light_helper_visibility(enabled, enabled)

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
        selected_objects = self.scene_manager.get_selected_objects()
        selected = len(selected_objects)
        models = len(scene.model_instances)
        if hasattr(self, "model_pill"):
            active = selected_objects[-1] if selected_objects else None
            active_model = self._runtime_model_for_scene_object(active) if active is not None else None
            active_name = (
                str(getattr(active_model, "name", "") or "").strip()
                or str(getattr(active, "name", "") or "").strip()
                or scene.display_name
            )
            self.model_pill.setText(f"// {active_name}{dirty}")
            status = "Empty Scene" if objects == 0 else f"Objects: {objects} | Selected: {selected}"
            self.model_pill.setToolTip(f"{status} | Models: {models} | Scene: {scene.display_name}")
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
        self.scene_manager.select_object(object_id)
        if hasattr(self, "viewport"):
            self.viewport.select_scene_object(object_id)
        obj = next((item for item in self.scene_manager.active_scene.objects if item.id == object_id), None)
        if obj is not None:
            self._activate_scene_object_model(obj)
            self._sync_skeleton_root_for_scene_object(obj)
            self._refresh_sprite_materials_panel_context()
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
            self._refresh_sprite_materials_panel_context()
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
            self._refresh_sprite_materials_panel_context()
        if hasattr(self, "viewport"):
            self.viewport.set_selected_node(node, source="scene outliner light")
        if hasattr(self, "lighting_panel"):
            self.lighting_panel.select_light(node)
        if hasattr(self, "properties_panel"):
            self.properties_panel.show_node(node)

    def _delete_scene_object(self, object_id: str) -> None:
        obj = next((item for item in self.scene_manager.active_scene.objects if item.id == object_id), None)
        if obj is not None and obj.object_type == "camera":
            viewport = getattr(self, "viewport", None)
            if viewport is not None and getattr(getattr(viewport, "camera_manager", None), "active_camera_id", "") == object_id:
                viewport.switch_to_perspective()
        if self.scene_manager.remove_object(object_id):
            self._refresh_scene_view()

    def _duplicate_scene_object(self, object_id: str) -> None:
        duplicate = self.scene_manager.duplicate_object(object_id)
        if duplicate is not None:
            source = next((obj for obj in self.scene_manager.active_scene.objects if obj.id == object_id), None)
            if source is not None and "_runtime_model" in source.metadata:
                duplicate.metadata["_runtime_model"] = copy.deepcopy(source.metadata["_runtime_model"])
            self.scene_manager.update_object_transform(duplicate.id, position=(
                duplicate.transform.position[0] + 2.0,
                duplicate.transform.position[1],
                duplicate.transform.position[2],
            ))
        self._refresh_scene_view()

    def _focus_scene_object(self, object_id: str) -> None:
        self._select_scene_object(object_id)
        self._call_viewport("frame_all")

    def _add_scene_object_to_sequence(self, object_id: str) -> None:
        obj = next((item for item in self.scene_manager.active_scene.objects if item.id == object_id), None)
        if obj is None:
            return
        editor = getattr(self, "sequence_editor_docked_window", None)
        if editor is None:
            self._show_sequence_editor_dock()
            editor = getattr(self, "sequence_editor_docked_window", None)
        else:
            self._show_sequence_editor_dock()
        if editor is None or getattr(editor, "sequence", None) is None:
            return
        binding = editor.manager.add_object_binding(editor.sequence, obj)
        editor._sequence_changed()
        item = editor._find_binding_item(binding.binding_id)
        if item is not None:
            editor.outliner.track_list.setCurrentItem(item)
        editor._set_status(f"Bound {binding.display_name}")

    def _sequence_editor_for_ipc(self):
        editor = getattr(self, "sequence_editor_docked_window", None)
        if editor is None:
            self._show_sequence_editor_dock()
            editor = getattr(self, "sequence_editor_docked_window", None)
        else:
            self._show_sequence_editor_dock()
        return editor

    def _sequence_track_item_for_ipc(self, editor, track_id: str):
        tree = editor.outliner.track_list
        for top_index in range(tree.topLevelItemCount()):
            top = tree.topLevelItem(top_index)
            for child_index in range(top.childCount()):
                child = top.child(child_index)
                if child.data(0, QtCore.Qt.UserRole) == ("track", track_id):
                    return child
        return None

    def _sequence_binding_for_ipc(self, editor, payload: dict):
        sequence = getattr(editor, "sequence", None)
        if sequence is None:
            return None
        binding_id = str(payload.get("binding_id", "") or "")
        if binding_id:
            found = sequence.binding_by_id(binding_id)
            if found is not None:
                return found
        object_id = str(payload.get("object_id", payload.get("id", "")) or "")
        name = str(payload.get("name", "") or "")
        for binding in sequence.bindings:
            if object_id and binding.target_object_id == object_id:
                return binding
            if name and binding.display_name.lower() == name.lower():
                return binding
        return editor.outliner.track_list.selected_binding()

    def _sequence_state_snapshot(self) -> dict:
        editor = getattr(self, "sequence_editor_docked_window", None) or getattr(self, "sequence_editor_window", None)
        sequence = getattr(editor, "sequence", None) if editor is not None else None
        if editor is None or sequence is None:
            return {"available": False}
        bindings = []
        for binding in sequence.bindings:
            bindings.append(
                {
                    "id": binding.binding_id,
                    "display_name": binding.display_name,
                    "target_object_id": binding.target_object_id,
                    "target_type": binding.target_type.value if hasattr(binding.target_type, "value") else str(binding.target_type),
                    "tracks": [
                        {
                            "id": track.track_id,
                            "name": track.name,
                            "type": track.track_type,
                            "metadata": dict(getattr(track, "metadata", {}) or {}),
                            "keys": [
                                {
                                    "frame": int(key.frame),
                                    "value": key.value,
                                }
                                for key in track.keyframes
                            ],
                        }
                        for track in binding.tracks
                    ],
                }
            )
        return {
            "available": True,
            "name": sequence.name,
            "current_frame": int(sequence.current_frame),
            "frame_rate": float(sequence.frame_rate),
            "playing": bool(getattr(editor.playback, "playing", False)),
            "last_warning": str(getattr(editor.evaluator, "last_warning", "") or ""),
            "bindings": bindings,
        }

    def _apply_sequence_command_from_ipc(self, command: str, payload: dict | None = None) -> dict:
        payload = payload if isinstance(payload, dict) else {}
        key = str(command or "").strip().lower().replace("-", "_").replace(" ", "_")
        editor = self._sequence_editor_for_ipc()
        if editor is None or getattr(editor, "sequence", None) is None:
            return {"ok": False, "command": key, "error": "sequence editor unavailable", "sequence": self._sequence_state_snapshot()}

        if key in {"state", "snapshot"}:
            return {"ok": True, "command": key, "sequence": self._sequence_state_snapshot()}

        if key in {"bind_object", "add_object", "add_selected_object"}:
            obj = None
            object_id = str(payload.get("object_id", payload.get("id", "")) or "")
            name = str(payload.get("name", "") or "")
            if object_id or name:
                obj = self._find_scene_object_for_ipc(object_id, name)
            if obj is None:
                selected = self.scene_manager.get_selected_objects()
                obj = selected[0] if selected else None
            if obj is None:
                return {"ok": False, "command": key, "error": "scene object not found", "sequence": self._sequence_state_snapshot()}
            binding = editor.manager.add_object_binding(editor.sequence, obj)
            editor._sequence_changed()
            item = editor._find_binding_item(binding.binding_id)
            if item is not None:
                editor.outliner.track_list.setCurrentItem(item)
            editor._set_status(f"Bound {binding.display_name}")
            return {"ok": True, "command": key, "binding_id": binding.binding_id, "sequence": self._sequence_state_snapshot()}

        if key in {"add_animation_track", "animation_track"}:
            from src.sequence.tracks.character_track import CharacterTrack

            binding = self._sequence_binding_for_ipc(editor, payload)
            if binding is None:
                return {"ok": False, "command": key, "error": "binding not found", "sequence": self._sequence_state_snapshot()}
            track = editor._base_animation_track(binding) if hasattr(editor, "_base_animation_track") else next((item for item in binding.tracks if isinstance(item, CharacterTrack)), None)
            if track is None:
                track = CharacterTrack(parent_binding_id=binding.binding_id)
                binding.add_track(track)
            editor._sequence_changed(evaluate=False)
            item = self._sequence_track_item_for_ipc(editor, track.track_id)
            if item is not None:
                editor.outliner.track_list.setCurrentItem(item)
            return {"ok": True, "command": key, "binding_id": binding.binding_id, "track_id": track.track_id, "sequence": self._sequence_state_snapshot()}

        if key in {"add_transform_track", "transform_track"}:
            from src.sequence.tracks.transform_track import TransformTrack

            binding = self._sequence_binding_for_ipc(editor, payload)
            if binding is None:
                return {"ok": False, "command": key, "error": "binding not found", "sequence": self._sequence_state_snapshot()}
            track = next((item for item in binding.tracks if isinstance(item, TransformTrack)), None)
            if track is None:
                track = TransformTrack(parent_binding_id=binding.binding_id)
                binding.add_track(track)
            editor._sequence_changed(evaluate=False)
            item = self._sequence_track_item_for_ipc(editor, track.track_id)
            if item is not None:
                editor.outliner.track_list.setCurrentItem(item)
            return {"ok": True, "command": key, "binding_id": binding.binding_id, "track_id": track.track_id, "sequence": self._sequence_state_snapshot()}

        if key in {"set_transform_key", "key_transform", "set_key"}:
            from src.sequence.tracks.transform_track import TransformTrack

            binding = self._sequence_binding_for_ipc(editor, payload)
            if binding is None:
                return {"ok": False, "command": key, "error": "binding not found", "sequence": self._sequence_state_snapshot()}
            track = next((item for item in binding.tracks if isinstance(item, TransformTrack)), None)
            if track is None:
                track = TransformTrack(parent_binding_id=binding.binding_id)
                binding.add_track(track)
            item = self._sequence_track_item_for_ipc(editor, track.track_id)
            if item is not None:
                editor.outliner.track_list.setCurrentItem(item)
            obj = editor.evaluator.resolver.resolve(binding)
            if obj is None:
                return {"ok": False, "command": key, "error": "bound object not found", "sequence": self._sequence_state_snapshot()}
            editor._key_track(track, obj)
            editor._sequence_changed(evaluate=False)
            return {"ok": True, "command": key, "binding_id": binding.binding_id, "track_id": track.track_id, "sequence": self._sequence_state_snapshot()}

        if key in {"add_selected_animation_clip", "add_clip"}:
            animation_name = str(payload.get("animation", payload.get("name", "")) or "").strip()
            if animation_name:
                from src.sequence.tracks.character_track import CharacterTrack

                binding = self._sequence_binding_for_ipc(editor, payload)
                if binding is None:
                    return {"ok": False, "command": key, "error": "binding not found", "sequence": self._sequence_state_snapshot()}
                track = editor._base_animation_track(binding) if hasattr(editor, "_base_animation_track") else next((item for item in binding.tracks if isinstance(item, CharacterTrack)), None)
                if track is None:
                    track = CharacterTrack(parent_binding_id=binding.binding_id)
                    binding.add_track(track)
                entries = editor._character_animation_entries(binding)
                match = next(
                    (
                        entry for entry in entries
                        if str(entry.get("name", "") or "").lower() == animation_name.lower()
                        or str(entry.get("label", "") or "").lower().startswith(animation_name.lower())
                    ),
                    None,
                )
                if match is None:
                    return {"ok": False, "command": key, "error": f"animation not found: {animation_name}", "sequence": self._sequence_state_snapshot()}
                item = self._sequence_track_item_for_ipc(editor, track.track_id)
                if item is not None:
                    editor.outliner.track_list.setCurrentItem(item)
                ok = bool(editor._add_animation_entry_to_track(track, match))
                if ok:
                    editor._sequence_changed(evaluate=True)
                    if hasattr(editor, "_play_from_current_animation_clip"):
                        editor._play_from_current_animation_clip()
                return {"ok": ok, "command": key, "sequence": self._sequence_state_snapshot()}
            ok = bool(editor._add_animation_clip_to_selected_track())
            return {"ok": ok, "command": key, "sequence": self._sequence_state_snapshot()}

        if key in {"add_overlapping_animation", "add_overlap_clip", "overlap_clip"}:
            animation_name = str(payload.get("animation", payload.get("name", "")) or "").strip()
            from src.sequence.tracks.character_track import CharacterTrack

            binding = self._sequence_binding_for_ipc(editor, payload)
            if binding is None:
                return {"ok": False, "command": key, "error": "binding not found", "sequence": self._sequence_state_snapshot()}
            if not animation_name:
                item = editor._find_binding_item(binding.binding_id)
                if item is not None:
                    editor.outliner.track_list.setCurrentItem(item)
                ok = bool(editor._add_overlapping_animation_to_selected_track())
                return {"ok": ok, "command": key, "sequence": self._sequence_state_snapshot()}
            base_track = editor._base_animation_track(binding) if hasattr(editor, "_base_animation_track") else next((item for item in binding.tracks if isinstance(item, CharacterTrack)), None)
            if base_track is None:
                base_track = CharacterTrack(parent_binding_id=binding.binding_id)
                binding.add_track(base_track)
            entries = editor._character_animation_entries(binding)
            match = next(
                (
                    entry for entry in entries
                    if str(entry.get("name", "") or "").lower() == animation_name.lower()
                    or str(entry.get("label", "") or "").lower().startswith(animation_name.lower())
                ),
                None,
            )
            if match is None:
                return {"ok": False, "command": key, "error": f"animation not found: {animation_name}", "sequence": self._sequence_state_snapshot()}
            track = editor._create_overlapping_animation_track(binding, base_track)
            item = self._sequence_track_item_for_ipc(editor, track.track_id)
            if item is not None:
                editor.outliner.track_list.setCurrentItem(item)
            ok = bool(
                editor._add_animation_entry_to_track(
                    track,
                    match,
                    blend_mode="overlay",
                    mask="auto",
                    priority=1,
                    track_name_prefix="Overlap",
                )
            )
            if ok:
                editor._sequence_changed(evaluate=True)
                item = self._sequence_track_item_for_ipc(editor, track.track_id)
                if item is not None:
                    editor.outliner.track_list.setCurrentItem(item)
                if hasattr(editor, "_play_from_current_animation_clip"):
                    editor._play_from_current_animation_clip()
            else:
                binding.remove_track(track.track_id)
            return {"ok": ok, "command": key, "track_id": track.track_id, "sequence": self._sequence_state_snapshot()}

        if key in {"set_frame", "seek"}:
            frame = int(round(float(payload.get("frame", payload.get("value", 0)) or 0)))
            editor._set_frame(frame)
            return {"ok": True, "command": key, "sequence": self._sequence_state_snapshot()}

        if key == "play":
            if not bool(getattr(editor.playback, "playing", False)):
                editor._toggle_play()
            return {"ok": True, "command": key, "sequence": self._sequence_state_snapshot()}

        if key == "stop":
            if bool(getattr(editor.playback, "playing", False)):
                editor._toggle_play()
            return {"ok": True, "command": key, "sequence": self._sequence_state_snapshot()}

        self._log(f"IPC sequence_command: unknown command {command}", "warning")
        return {"ok": False, "command": key, "error": "unknown command", "sequence": self._sequence_state_snapshot()}

    def _set_scene_object_visible(self, object_id: str, visible: bool) -> None:
        if self.scene_manager.set_object_visibility(object_id, visible):
            self._refresh_scene_view()
            self._invalidate_renderer_resources("scene object visibility changed")

    def _set_scene_object_locked(self, object_id: str, locked: bool) -> None:
        if self.scene_manager.set_object_locked(object_id, locked):
            self._refresh_scene_view()
            self._refresh_adjust_pivot_panel()

    def _rename_scene_object(self, object_id: str, name: str) -> None:
        if self.scene_manager.rename_object(object_id, name):
            self._refresh_scene_view()

    def _on_viewport_scene_node_selected(self, node) -> None:
        object_id = str(getattr(node, "_gr_scene_object_id", "") or "")
        if object_id:
            self.scene_manager.select_object(object_id)
            if hasattr(self, "scene_outliner_panel"):
                self.scene_outliner_panel.set_scene(self.scene_manager.active_scene)
            obj = next((item for item in self.scene_manager.active_scene.objects if item.id == object_id), None)
            if obj is not None:
                self._activate_scene_object_model(obj)
                self._sync_skeleton_root_for_scene_object(obj)
                self._refresh_sprite_materials_panel_context()
                if obj.object_type == "camera" and hasattr(self, "camera_panel"):
                    self.camera_panel.select_camera_object(node)
                if obj.object_type == "light" and hasattr(self, "lighting_panel"):
                    self.lighting_panel.select_light(node)
                show_scene_object = getattr(self.properties_panel, "show_scene_object", None)
                if callable(show_scene_object):
                    show_scene_object(obj)
        else:
            self.scene_manager.clear_selection()
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
        live_preview = bool(getattr(node, "_gr_transform_previewing", False))
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
        obj = next((item for item in self.scene_manager.active_scene.objects if item.id == object_id), None)
        if obj is not None and obj.object_type == "camera":
            camera = getattr(getattr(self, "viewport", None), "camera_manager", None)
            camera = camera.find_by_original(node) if camera is not None else None
            payload = dict((getattr(obj, "metadata", {}) or {}).get("camera") or {})
            payload.update(
                {
                    "id": object_id,
                    "scene_object_id": object_id,
                    "name": str(getattr(node, "name", "") or obj.name),
                    "position": tuple(float(v) for v in getattr(node, "position", (0.0, 0.0, 0.0))[:3]),
                    "rotation": tuple(float(v) for v in getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))[:4]),
                    "visible": not bool(getattr(node, "_gr_camera_hidden", False)),
                    "locked": bool(getattr(node, "_gr_camera_locked", False)),
                    "selected": True,
                }
            )
            if camera is not None:
                payload["target_position"] = tuple(float(v) for v in tuple(camera.target_position)[:3])
                payload["target_enabled"] = bool(getattr(camera, "target_enabled", False))
                payload["target_object_id"] = str(getattr(camera, "target_object_id", "") or "")
                payload["target_follow_enabled"] = bool(getattr(camera, "target_follow_enabled", False))
            self.scene_manager.update_camera_properties(object_id, **payload)
        elif obj is not None and obj.object_type == "light":
            payload = dict((getattr(obj, "metadata", {}) or {}).get("light") or {})
            light_position = tuple(float(v) for v in getattr(node, "position", (0.0, 0.0, 0.0))[:3])
            payload.update(
                {
                    "id": object_id,
                    "scene_object_id": object_id,
                    "name": str(getattr(node, "name", "") or obj.name),
                    "position": light_position,
                    "rotation": tuple(float(v) for v in getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))[:4]),
                    "type": str(getattr(node, "light_kind", payload.get("type", "point")) or "point"),
                    "enabled": bool(getattr(node, "light_enabled", payload.get("enabled", True))),
                    "visible": not bool(getattr(node, "_gr_light_hidden", False)),
                    "locked": bool(getattr(node, "_gr_light_locked", False)),
                    "selected": True,
                }
            )
            self.scene_manager.update_light_properties(object_id, **payload)
            panel = getattr(self, "lighting_panel", None)
            light = panel.manager.get(object_id) if panel is not None else None
            if light is not None:
                light.position = light_position
                light.rotation = tuple(float(v) for v in getattr(node, "rotation", light.rotation)[:4])
                light.apply_to_original()
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
        self._refresh_adjust_pivot_panel()
        if live_preview:
            return
        self._update_scene_chrome()
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
