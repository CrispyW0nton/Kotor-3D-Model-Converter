"""Viewport-level model, diagnostics, terminal, camera, lightmap, and rig helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

try:
    from PySide6 import QtCore, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.gui.qt_lib.dialogs.qt_lightmap_baker_dialog import QtLightmapBakerDialog
from src.gui.qt_lib.dialogs.qt_render_frame_dialog import QtRenderFrameDialog
from src.gui.viewports.viewport_core.widget_scaffold import create_custom_viewport_widget
from src.core.rendering.viewport_navigation import DEFAULT_VIEWPORT_NAVIGATION_PROFILE
from src.systems.bas.model_recipe import BAS_SLOT_ORDER

log = logging.getLogger(__name__)


class ViewportToolsMixin:
    """Viewport-level model, diagnostics, terminal, camera, lightmap, and rig helpers."""

    def _require_model(self, action: str):
        model = self._current_model or self._active_viewport_model()
        if model is not None and self._current_model is None:
            self._current_model = model
        if model is None:
            QtWidgets.QMessageBox.information(self, action, "Load or import a model first.")
            return None
        return model
    def _model_worker_is_running(self) -> bool:
        thread = self._worker_thread
        if thread is None:
            return False
        try:
            return thread.isRunning()
        except RuntimeError:
            self._worker_thread = None
            self._model_worker = None
            return False
    def _scan_worker_is_running(self) -> bool:
        thread = self._scan_thread
        if thread is None:
            return False
        try:
            return thread.isRunning()
        except RuntimeError:
            self._scan_thread = None
            self._scan_worker = None
            return False
    def _auto_detect_worker_is_running(self) -> bool:
        thread = self._auto_detect_thread
        if thread is None:
            return False
        try:
            return thread.isRunning()
        except RuntimeError:
            self._auto_detect_thread = None
            self._auto_detect_worker = None
            return False
    def _animation_scan_worker_is_running(self) -> bool:
        thread = self._animation_scan_thread
        if thread is None:
            return False
        try:
            return thread.isRunning()
        except RuntimeError:
            self._animation_scan_thread = None
            self._animation_scan_worker = None
            return False
    def _set_model_internal(self, model, path: str = ""):
        if model is None:
            old_model = self._current_model
            if old_model is not None:
                try:
                    from src.adapters.rendering.moderngl_resources import clear_prebuilt_static_gpu_model_data

                    clear_prebuilt_static_gpu_model_data(old_model)
                except Exception:
                    log.debug("Model RAM buffer cleanup failed", exc_info=True)
            self._pending_gpu_upload_model_id = 0
            self._pending_gpu_upload_total = 0
            self._animation_timer.stop()
            self._retarget_timer.stop()
            self._animation_engine = None
            self._animation_last_tick = None
            self._retarget_engine = None
            self._retarget_target_model = None
            self._retarget_last_tick = None
            self._current_model = None
            self._bas_body_model = None
            self._bas_preview_model = None
            self._bas_attachments.clear()
            self._bas_attachment_resrefs.clear()
            self._bas_attachment_transforms.clear()
            self._bas_active_build_name = ""
            self._bas_mode = "headless_body"
            self._current_head_model = None
            self._current_attachment_model = None
            self._model_path = ""
            self.model_pill.setText(f"// {self.scene_manager.active_scene.display_name}")
            self.model_pill.setToolTip("Active KMAX scene.")
            self.statusBar().showMessage("Ready")
            if hasattr(self, "viewport"):
                self.viewport.set_model(None)
            if hasattr(self, "skeleton_panel"):
                self.skeleton_panel.load_model(None)
            if hasattr(self, "lighting_panel"):
                self.lighting_panel.set_model(None)
            if hasattr(self, "camera_panel"):
                self.camera_panel.set_model(None)
                self.camera_panel.manager = self.viewport.camera_manager
            if hasattr(self, "properties_panel"):
                self.properties_panel.show_model(None)
            if hasattr(self, "module_geometry_panel"):
                self.module_geometry_panel.show_model(None)
            if hasattr(self, "sprite_materials_panel"):
                self.sprite_materials_panel.set_model(None)
            if hasattr(self, "body_attachment_panel"):
                if hasattr(self.body_attachment_panel, "set_mode"):
                    self.body_attachment_panel.set_mode("headless_body")
                self.body_attachment_panel.set_body_model(None)
                for slot in BAS_SLOT_ORDER:
                    if slot == "body":
                        continue
                    self.body_attachment_panel.clear_slot_model(slot)
                self.body_attachment_panel.set_status("")
            if hasattr(self, "animations_panel"):
                self.animations_panel.load_model(None)
            if hasattr(self, "animation_retarget_panel"):
                self.animation_retarget_panel.set_target_model(None)
            if hasattr(self, "retarget_preview_controller"):
                self._sync_retarget_preview_target()
            if hasattr(self, "diagnostics_panel"):
                self.diagnostics_panel.run_diagnostics(None)
            bus = getattr(self, "integration_event_bus", None)
            if bus is not None:
                bus.record_scene_update("model_removed", None)
            self._invalidate_renderer_resources("model cleared")
            self.props_text.clear()
            return
        self._on_model_loaded(model, path or getattr(model, "name", "model"), "")
    def _pick_export_game_version(self) -> Optional[str]:
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("Export Target Game")
        box.setText("Choose the target game version for this export.")
        k1_button = box.addButton("K1", QtWidgets.QMessageBox.AcceptRole)
        k2_button = box.addButton("K2", QtWidgets.QMessageBox.AcceptRole)
        box.addButton(QtWidgets.QMessageBox.Cancel)
        box.setDefaultButton(k1_button)
        box.exec()
        clicked = box.clickedButton()
        if clicked is k1_button:
            return "K1"
        if clicked is k2_button:
            return "K2"
        return None
    def _game_version(self):
        from src.core.geometry.model_data import GameVersion

        default_game = str(self.settings_data.get("default_game") or "K1").upper()
        return GameVersion.K2 if default_game == "K2" else GameVersion.K1
    def _get_tex_cache_for_export(self):
        viewport = getattr(self, "viewport", None)
        if viewport is None:
            return None
        tex_cache = getattr(viewport, "tex_cache", None)
        return tex_cache() if callable(tex_cache) else tex_cache
    def _open_lightmap_baker(self) -> None:
        if self._current_model is None:
            QtWidgets.QMessageBox.information(self, "Lightmap Baker", "Load a model or module before baking lightmaps.")
            return
        dialog = QtLightmapBakerDialog(
            self,
            model=self._current_model,
            lights=list(self.lighting_panel.manager.all_lights()) if hasattr(self, "lighting_panel") else [],
            selected_meshes=self.viewport.get_selected_meshes() if hasattr(self.viewport, "get_selected_meshes") else [],
            visible_meshes=self.viewport.get_visible_meshes() if hasattr(self.viewport, "get_visible_meshes") else [],
            texture_cache=self._get_tex_cache_for_export(),
            default_output_dir=str((Path.cwd() / "exports" / "lightmaps").resolve()),
        )
        dialog.previewRequested.connect(self._preview_baked_lightmaps)
        dialog.applyRequested.connect(self._apply_baked_lightmaps)
        dialog.revertRequested.connect(self._revert_baked_lightmaps)
        self._lightmap_baker_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
    def _preview_baked_lightmaps(self, result) -> None:
        assignments = result.preview_assignments() if result is not None and hasattr(result, "preview_assignments") else {}
        self.viewport.set_baked_lightmap_assignments(assignments, preview=True)
        self._log(f"Previewing {len(assignments)} baked lightmap(s).", "success")
    def _apply_baked_lightmaps(self, result) -> None:
        assignments = result.preview_assignments() if result is not None and hasattr(result, "preview_assignments") else {}
        self.viewport.set_baked_lightmap_assignments(assignments, preview=False)
        self._log(f"Applied {len(assignments)} baked lightmap assignment(s) to the current scene state.", "success")
    def _revert_baked_lightmaps(self) -> None:
        self.viewport.revert_baked_lightmaps()
        self._log("Reverted baked lightmap preview/apply overrides.", "info")
    def _on_camera_panel_changed(self) -> None:
        self._sync_scene_cameras_from_viewport_manager()
        self.viewport.refresh_cameras()
        self.camera_panel.refresh()
        if hasattr(self, "scene_outliner_panel"):
            self.scene_outliner_panel.set_scene(self.scene_manager.active_scene)
    def _sync_camera_panel_from_viewport(self) -> None:
        self._sync_scene_cameras_from_viewport_manager()
        self.camera_panel.manager = self.viewport.camera_manager
        self.camera_panel.refresh()
        if hasattr(self, "scene_outliner_panel"):
            self.scene_outliner_panel.set_scene(self.scene_manager.active_scene)
    def _on_lighting_panel_changed(self) -> None:
        self._sync_scene_lights_from_panel_manager()
        self.viewport.refresh_lighting()
        if hasattr(self, "scene_outliner_panel"):
            self.scene_outliner_panel.set_scene(self.scene_manager.active_scene)
    def _create_scene_camera_object(self, camera_type: str = "Cinematic Camera", *, make_active: bool = False, name: str = ""):
        from src.core.camera.camera_model import GhostRiggerCamera
        from src.core.scene.scene_object import Transform

        camera = GhostRiggerCamera(camera_type=camera_type)
        if camera_type == "Target Camera":
            camera.target_enabled = True
        adapter = getattr(getattr(self, "viewport", None), "_camera_adapter", None)
        if adapter is not None:
            adapter.update_camera_from_view(camera)
        rotation = (0.0, 0.0, 0.0)
        try:
            rotation = self.viewport._quat_to_euler_degrees(camera.rotation)
        except Exception:
            pass
        obj = self.scene_manager.add_camera_object(
            camera_type,
            Transform(position=camera.position, rotation=rotation),
            name=str(name or ""),
            properties=camera,
            select=True,
        )
        self._refresh_scene_view()
        self._select_scene_object(obj.id)
        if make_active and hasattr(self, "viewport"):
            self.viewport.switch_to_camera(obj.id)
        return obj
    def _create_scene_camera_from_view(self):
        return self._create_scene_camera_object("Cinematic Camera", make_active=True)
    def _duplicate_scene_camera_object(self, camera_id: str):
        duplicate = self.scene_manager.duplicate_camera_object(camera_id) or self.scene_manager.duplicate_object(camera_id)
        if duplicate is not None:
            position = (
                duplicate.transform.position[0] + 0.35,
                duplicate.transform.position[1] + 0.35,
                duplicate.transform.position[2],
            )
            self.scene_manager.update_object_transform(duplicate.id, position=position)
        self._refresh_scene_view()
        return duplicate
    def _delete_scene_camera_object(self, camera_id: str) -> bool:
        if hasattr(self, "viewport") and getattr(self.viewport.camera_manager, "active_camera_id", "") == camera_id:
            self.viewport.switch_to_perspective()
        ok = self.scene_manager.remove_camera_object(camera_id) or self.scene_manager.remove_object(camera_id)
        if ok:
            self._refresh_scene_view()
        return ok
    def _create_scene_light_object(self, light_type: str = "point", *, name: str = ""):
        from src.core.scene.scene_object import Transform

        position = (0.0, 0.0, 0.0)
        camera = getattr(getattr(self, "viewport", None), "camera", None)
        target = getattr(camera, "target", None)
        if target is not None:
            try:
                position = tuple(float(v) for v in target[:3])
            except Exception:
                position = (0.0, 0.0, 0.0)
        obj = self.scene_manager.add_light_object(
            light_type,
            Transform(position=position),
            name=str(name or ""),
            select=True,
        )
        self._refresh_scene_view()
        self._select_scene_object(obj.id)
        return obj
    def _sync_scene_cameras_from_viewport_manager(self) -> None:
        manager = getattr(getattr(self, "viewport", None), "camera_manager", None)
        scene_manager = getattr(self, "scene_manager", None)
        if manager is None or scene_manager is None:
            return
        for camera in manager.get_all_cameras():
            object_id = str(getattr(camera, "id", "") or "")
            node = getattr(camera, "original_ref", None)
            if not object_id:
                continue
            try:
                rotation = self.viewport._quat_to_euler_degrees(getattr(node, "rotation", camera.rotation))
            except Exception:
                rotation = None
            scene_manager.update_object_transform(
                object_id,
                position=tuple(float(v) for v in camera.position[:3]),
                rotation=rotation,
            )
            existing = next((obj for obj in scene_manager.active_scene.objects if obj.id == object_id), None)
            if existing is not None:
                scene_manager.update_camera_properties(object_id, **camera.serialize())
                continue
            from src.core.scene.scene_object import Transform

            scene_manager.add_camera_object(
                getattr(camera, "camera_type", "Cinematic Camera"),
                Transform(position=tuple(float(v) for v in camera.position[:3]), rotation=rotation or (0.0, 0.0, 0.0)),
                name=str(getattr(camera, "name", "") or "Camera"),
                properties=camera,
                object_id=object_id,
                select=bool(getattr(camera, "selected", False)),
            )
    def _sync_scene_lights_from_panel_manager(self) -> None:
        panel = getattr(self, "lighting_panel", None)
        scene_manager = getattr(self, "scene_manager", None)
        if panel is None or scene_manager is None:
            return
        for light in panel.manager.all_lights(include_deleted=True):
            object_id = str(getattr(light, "id", "") or "")
            if not object_id:
                continue
            if bool(getattr(light, "deleted", False)):
                scene_obj = next((obj for obj in scene_manager.active_scene.objects if obj.id == object_id), None)
                if scene_obj is not None and getattr(scene_obj, "object_type", "") == "light":
                    scene_manager.remove_light_object(object_id)
                continue
            changed = scene_manager.update_object_transform(
                object_id,
                position=tuple(float(v) for v in light.position[:3]),
            )
            payload = {
                key: value
                for key, value in light.__dict__.items()
                if key != "original_ref" and not str(key).startswith("_")
            }
            if changed:
                scene_manager.update_light_properties(object_id, **payload)
                continue
            if str(getattr(light, "source_type", "") or "") == "Aurora":
                continue
            from src.core.scene.scene_object import Transform

            scene_manager.add_light_object(
                str(getattr(light, "type", "point") or "point"),
                Transform(position=tuple(float(v) for v in light.position[:3])),
                name=str(getattr(light, "name", "") or "Light"),
                properties=payload,
                object_id=object_id,
                select=bool(getattr(light, "selected", False)),
            )
    def _open_render_frame_dialog(self) -> None:
        cameras = self.viewport.camera_manager.get_all_cameras()
        active_id = self.viewport.camera_manager.active_camera_id
        dialog = QtRenderFrameDialog(cameras, active_id, self)
        dialog.renderRequested.connect(lambda settings, camera_id: self._render_camera_still(dialog, settings, camera_id))
        dialog.previewRequested.connect(lambda settings, camera_id: self._preview_camera_still(dialog, settings, camera_id))
        dialog.exec()
    def _preview_camera_still(self, dialog: QtRenderFrameDialog, settings, camera_id: str) -> None:
        try:
            path = self.viewport.render_still_frame(settings, camera_id)
            dialog.report_status(f"Preview saved: {path}")
            self._log(f"Preview rendered camera still: {path}", "success")
        except Exception as exc:
            dialog.report_status(f"Preview failed: {exc}")
            self._log(f"Camera preview render failed: {exc}", "error")
    def _render_camera_still(self, dialog: QtRenderFrameDialog, settings, camera_id: str) -> None:
        try:
            path = self.viewport.render_still_frame(settings, camera_id)
            dialog.report_status(f"Saved: {path}")
            self._log(f"Rendered camera still: {path}", "success")
        except Exception as exc:
            dialog.report_status(f"Render failed: {exc}")
            self._log(f"Camera render failed: {exc}", "error")
    def _call_viewport(self, method_name: str):
        viewport = getattr(self, "viewport", None)
        method = getattr(viewport, method_name, None)
        if method is None:
            self._not_migrated(method_name)
            return
        method()
    def _click_viewport_button(self, button_name: str):
        viewport = getattr(self, "viewport", None)
        button = getattr(viewport, button_name, None)
        if button is None:
            self._not_migrated(button_name)
            return
        button.click()
    def _apply_viewport_command_from_ipc(self, command: str, options: dict | None = None) -> bool:
        viewport = getattr(self, "viewport", None)
        if viewport is None:
            self._log("IPC viewport_command: viewport unavailable.", "warning")
            return False
        payload = dict(options or {})
        key = str(command or "").strip().lower().replace("-", "_").replace(" ", "_")
        simple_methods = {
            "frame": "frame_all",
            "frame_all": "frame_all",
            "reset": "reset_camera",
            "reset_camera": "reset_camera",
            "undo": "undo",
            "redo": "redo",
        }
        method_name = simple_methods.get(key)
        if method_name:
            method = getattr(viewport, method_name, None)
            if callable(method):
                method()
                self._log(f"IPC viewport_command: {key}", "info")
                return True
            self._log(f"IPC viewport_command unavailable: {key}", "warning")
            return False
        if key in {"refresh", "refresh_all"}:
            self._refresh_all()
            self._log("IPC viewport_command: refresh", "info")
            return True
        if key in {"shade", "shade_mode", "display", "display_mode", "wire", "wireframe", "solid", "solid_wire"}:
            mode = str(payload.get("mode", payload.get("value", command)) or command)
            if key in {"wire", "wireframe"}:
                mode = "wire"
            elif key == "solid":
                mode = "solid"
            elif key == "solid_wire":
                mode = "both"
            setter = getattr(viewport, "set_shade_mode", None)
            if callable(setter):
                setter(mode)
                self._log(f"IPC viewport_command shade: {mode}", "info")
                return True
        if key in {"render", "render_mode", "lighting_render_mode"}:
            mode = str(payload.get("mode", payload.get("value", "realistic")) or "realistic")
            setter = getattr(viewport, "set_render_mode", None)
            if callable(setter):
                setter(mode)
                self._log(f"IPC viewport_command render_mode: {mode}", "info")
                return True
        toggles = {
            "grid": "toggle_grid",
            "texture": "toggle_texture",
            "textures": "toggle_texture",
            "bones": "toggle_bones",
            "locomotion": "toggle_locomotion_discs",
            "locomotion_disc": "toggle_locomotion_discs",
            "locomotion_discs": "toggle_locomotion_discs",
        }
        toggle = toggles.get(key)
        if toggle:
            value = payload.get("enabled", payload.get("visible", payload.get("value", None)))
            method = getattr(viewport, toggle, None)
            if callable(method):
                method(None if value is None else bool(value))
                state = "toggle" if value is None else ("on" if bool(value) else "off")
                self._log(f"IPC viewport_command {key}: {state}", "info")
                return True
        if key in {"locomotion_size", "locomotion_disc_size", "disc_size"}:
            size = payload.get("size", payload.get("value", None))
            setter = getattr(viewport, "set_locomotion_disc_size", None)
            if callable(setter) and size is not None:
                setter(int(size))
                self._log(f"IPC viewport_command locomotion_disc_size: {int(size)}", "info")
                return True
        if key in {"lighting", "lighting_mode"}:
            mode = str(payload.get("mode", payload.get("value", "scene")) or "scene")
            setter = getattr(viewport, "set_lighting_mode", None)
            if callable(setter):
                setter(mode)
                self._log(f"IPC viewport_command lighting_mode: {mode}", "info")
                return True
        if key in {"shader_complexity", "complexity"}:
            mode = str(payload.get("mode", payload.get("value", "off")) or "off")
            setter = getattr(viewport, "set_shader_complexity_mode", None)
            if callable(setter):
                setter(mode)
                self._log(f"IPC viewport_command shader_complexity: {mode}", "info")
                return True
        self._log(f"IPC viewport_command: unknown command {command}", "warning")
        return False
    def _ipc_application_state_snapshot(self) -> dict:
        scene_manager = getattr(self, "scene_manager", None)
        scene = getattr(scene_manager, "active_scene", None)
        objects = list(getattr(scene, "objects", []) or [])
        selected = [obj for obj in objects if bool(getattr(obj, "selected", False))]
        counts = {"model": 0, "light": 0, "camera": 0, "helper": 0}
        for obj in objects:
            kind = str(getattr(obj, "object_type", "") or "helper")
            counts[kind if kind in counts else "helper"] += 1
        viewport = getattr(self, "viewport", None)
        renderer_text = ""
        display_options = {}
        if viewport is not None:
            render_state = getattr(viewport, "render_state_status_text", None)
            if callable(render_state):
                try:
                    renderer_text = str(render_state() or "")
                except Exception:
                    renderer_text = ""
            options = getattr(viewport, "display_options", None)
            if options is not None:
                display_options = {
                    "mode": str(getattr(getattr(options, "display_mode", ""), "value", getattr(options, "display_mode", "")) or ""),
                    "show_grid": bool(getattr(options, "show_grid", False)),
                    "show_textures": bool(getattr(options, "show_textures", False)),
                    "show_lightmaps": bool(getattr(options, "show_lightmaps", False)),
                    "show_wire_overlay": bool(getattr(options, "show_wire_overlay", False)),
                    "xray": bool(getattr(options, "xray", False)),
                }
        model = self._active_viewport_model() if hasattr(self, "_active_viewport_model") else getattr(self, "_current_model", None)
        dock_visibility = {}
        for key, dock in getattr(self, "_dock_widgets", {}).items() if isinstance(getattr(self, "_dock_widgets", {}), dict) else []:
            try:
                dock_visibility[str(key)] = bool(dock.isVisible())
            except Exception:
                pass
        theme_manager = getattr(self, "theme_manager", None)
        layout_manager = getattr(self, "layout_manager", None)
        current_theme = getattr(theme_manager, "current_theme", None) or (theme_manager.get_theme() if theme_manager is not None else None)
        current_layout = getattr(layout_manager, "current_layout", None) or (layout_manager.get_layout() if layout_manager is not None else None)
        return {
            "window": {
                "visible": bool(self.isVisible()),
                "active": bool(self.isActiveWindow()),
                "minimized": bool(self.isMinimized()),
                "width": int(self.width()),
                "height": int(self.height()),
            },
            "scene": {
                "name": str(getattr(scene, "display_name", getattr(scene, "name", "")) or ""),
                "path": str(getattr(scene, "path", "") or ""),
                "game": str(getattr(scene, "game", "") or ""),
                "dirty": bool(getattr(scene, "dirty", False)),
                "object_count": len(objects),
                "counts": counts,
            },
            "selection": [
                {
                    "id": str(getattr(obj, "id", "") or ""),
                    "name": str(getattr(obj, "name", "") or ""),
                    "type": str(getattr(obj, "object_type", "") or ""),
                    "visible": bool(getattr(obj, "visible", True)),
                }
                for obj in selected
            ],
            "viewport": {
                "renderer": renderer_text,
                "display": display_options,
                "model": str(getattr(model, "name", "") or getattr(model, "resref", "") or ""),
            },
            "appearance": {
                "theme": str(getattr(current_theme, "id", "") or ""),
                "theme_name": str(getattr(current_theme, "name", "") or ""),
                "layout": str(getattr(current_layout, "id", "") or ""),
                "layout_name": str(getattr(current_layout, "name", "") or ""),
            },
            "animation": self._animation_state_snapshot() if hasattr(self, "_animation_state_snapshot") else {},
            "sequence": self._sequence_state_snapshot() if hasattr(self, "_sequence_state_snapshot") else {},
            "library": self._ipc_library_state_snapshot() if hasattr(self, "_ipc_library_state_snapshot") else {},
            "resources": self._ipc_resource_state_snapshot() if hasattr(self, "_ipc_resource_state_snapshot") else {},
            "docks": dock_visibility,
        }
    def _clear_model(self):
        if not self._prompt_save_dirty_scene():
            return
        self.scene_manager.clear_scene()
        self._set_model_internal(None)
        self._refresh_scene_view()
        self._finish_progress_toast("Scene cleared", "Scene objects were removed.")
        self._log("Scene cleared.", "info")
    def _set_texture_dir(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Texture Directory",
            self._texture_dir or str(self.app_root),
        )
        if not directory:
            return
        self._texture_dir = directory
        self._log(f"Texture dir -> {Path(directory).name}", "success")
        self._refresh_all()
    def _refresh_all(self):
        model = self._current_model
        if hasattr(self, "viewport"):
            self._configure_viewport_resources()
            self._refresh_scene_view()
        if hasattr(self, "skeleton_panel"):
            self.skeleton_panel.load_model(model)
        if hasattr(self, "lighting_panel"):
            self.lighting_panel.set_model(self._active_viewport_model())
            self._sync_lighting_helper_visibility_to_viewport()
        if hasattr(self, "camera_panel"):
            self.camera_panel.set_model(self._active_viewport_model())
            self.camera_panel.manager = self.viewport.camera_manager
            self.camera_panel.refresh()
        if getattr(self, "sequence_editor_window", None) is not None:
            try:
                self.sequence_editor_window.viewport_panel.sync_from_source()
                self.sequence_editor_window.set_docked_preview(False, self.viewport)
            except Exception:
                pass
        if getattr(self, "sequence_editor_docked_window", None) is not None:
            try:
                self.sequence_editor_docked_window.set_docked_preview(True, self.viewport)
            except Exception:
                pass
        if hasattr(self, "properties_panel"):
            self.properties_panel.show_model(model)
        if hasattr(self, "module_geometry_panel"):
            self.module_geometry_panel.show_model(self._active_viewport_model())
        if hasattr(self, "sprite_materials_panel"):
            self._refresh_sprite_materials_panel_context()
        if hasattr(self, "body_attachment_panel"):
            self.body_attachment_panel.set_body_model(getattr(self, "_bas_body_model", None) or model)
        if hasattr(self, "animations_panel"):
            self._load_animation_panel_model(model)
        if hasattr(self, "animation_retarget_panel"):
            self.animation_retarget_panel.set_texture_dir(self._texture_dir)
            game = (self._current_game or self._infer_game_from_model(model)).upper()
            self._retarget_mapping_report = None
            if self._supports_animation_retarget_target(model):
                mgr = self._get_resource_manager()
                if mgr is not None:
                    self.animation_retarget_panel.set_target_resource_context(mgr, game)
                self._retarget_target_model = model
                self.animation_retarget_panel.set_target_model(model, game)
            else:
                self._retarget_target_model = None
                self.animation_retarget_panel.set_target_model(None, game)
        if hasattr(self, "retarget_preview_controller"):
            self._sync_retarget_preview_target()
        self._animation_engine = None
        self._animation_timer.stop()
        self._animation_last_tick = None
        self._retarget_timer.stop()
        self._retarget_engine = None
        self._retarget_last_tick = None
        if hasattr(self, "diagnostics_panel"):
            self.diagnostics_panel.run_diagnostics(model)
        self.statusBar().showMessage("Refreshed")
        self._log("Panels refreshed.", "info")
    def _show_model_info(self):
        model = self._require_model("Model Info")
        if model is None:
            return
        mesh_nodes = model.mesh_nodes() if hasattr(model, "mesh_nodes") else []
        bone_nodes = model.bone_nodes() if hasattr(model, "bone_nodes") else []
        textures = model.texture_list() if hasattr(model, "texture_list") else []
        info = "\n".join(
            [
                f"Name:       {getattr(model, 'name', '')}",
                f"Game:       {getattr(getattr(model, 'game_version', ''), 'name', getattr(model, 'game_version', ''))}",
                f"Supermodel: {getattr(model, 'supermodel', '')}",
                f"Class:      {getattr(model, 'classification', '')}",
                f"Nodes:      {model.node_count() if hasattr(model, 'node_count') else 0}",
                f"Mesh nodes: {len(mesh_nodes)}",
                f"Bone nodes: {len(bone_nodes)}",
                f"Animations: {len(getattr(model, 'animations', []) or [])}",
                f"Textures:   {', '.join(textures) or '(none)'}",
                f"BB min:     {getattr(model, 'bb_min', '')}",
                f"BB max:     {getattr(model, 'bb_max', '')}",
                f"Radius:     {getattr(model, 'radius', '')}",
            ]
        )
        QtWidgets.QMessageBox.information(self, "Model Info", info)
    def _run_diagnostics_popup(self):
        if hasattr(self, "diagnostics_panel"):
            self.diagnostics_panel.run_diagnostics(self._current_model)
            content = self.diagnostics_panel.text.toPlainText()
        else:
            content = "No diagnostics panel available."
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Diagnostics")
        dialog.resize(720, 520)
        layout = QtWidgets.QVBoxLayout(dialog)
        text = QtWidgets.QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(content or "No diagnostics available.")
        layout.addWidget(text, 1)
        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button, 0, QtCore.Qt.AlignRight)
        dialog.exec()
    def _show_diagnostics_panel(self):
        panel = getattr(self, "diagnostics_panel", None)
        if panel is None:
            self._not_migrated("Diagnostics")
            return
        panel.run_diagnostics(self._current_model)
        self._show_workspace_dock("diagnostics")
    def _configure_python_terminal_context(self) -> None:
        terminal = getattr(self, "python_terminal_panel", None)
        if terminal is None:
            terminal = getattr(getattr(self, "log_panel", None), "terminal", None)
        if terminal is None:
            return
        terminal.set_context(
            window=self,
            main_window=self,
            log_panel=getattr(self, "log_panel", None),
            viewport=lambda: getattr(self, "viewport", None),
            model=self._terminal_model,
            selected_model=self._terminal_model,
            animation_names=self._terminal_animation_names,
            select_animation=self._terminal_select_animation,
            play_animation=self._terminal_play_animation,
            stop_animation=self._terminal_stop_animation,
            seek_animation=self._terminal_seek_animation,
            override_animation=self._terminal_override_animation,
            create_viewport_widget=self._terminal_create_viewport_widget,
        )
    def _terminal_model(self):
        return getattr(self, "_current_model", None)
    def _terminal_animation_names(self) -> list[str]:
        model = self._terminal_model()
        return [
            str(getattr(anim, "name", anim))
            for anim in (getattr(model, "animations", []) or [])
        ] if model is not None else []
    def _terminal_select_animation(self, anim_name: str) -> bool:
        anim_name = str(anim_name or "")
        if not anim_name or not hasattr(self, "animations_panel"):
            return False
        ok = self.animations_panel.select_animation(anim_name)
        if ok:
            self._show_right_tab("Animations")
        return ok
    def _terminal_play_animation(self, anim_name: str = "", loop: Optional[bool] = None) -> str:
        if loop is not None:
            self._animation_loop = bool(loop)
        anim_name = str(anim_name or "")
        if not anim_name and hasattr(self, "animations_panel"):
            anim_name = self.animations_panel.selected_animation()
        if anim_name:
            self._terminal_select_animation(anim_name)
        self._handle_animation_action("Play", anim_name)
        return anim_name
    def _terminal_stop_animation(self) -> None:
        self._handle_animation_action("Stop", "")
    def _terminal_seek_animation(self, percent: int | float) -> None:
        self._handle_animation_seek(int(percent))
    def _terminal_override_animation(
        self,
        target_name: str,
        source_name: str = "",
        source_model=None,
    ) -> str:
        import copy

        model = self._terminal_model()
        if model is None:
            raise RuntimeError("No selected model is loaded.")
        target_name = str(target_name or "").strip()
        if not target_name:
            raise ValueError("target_name is required.")
        source_model = source_model or model
        if not source_name and hasattr(self, "animations_panel"):
            source_name = self.animations_panel.selected_animation()
        source_name = str(source_name or target_name).strip()
        source_anim = next(
            (
                anim for anim in (getattr(source_model, "animations", []) or [])
                if str(getattr(anim, "name", "")).lower() == source_name.lower()
            ),
            None,
        )
        if source_anim is None:
            raise ValueError(f"Source animation not found: {source_name}")
        replacement = copy.deepcopy(source_anim)
        replacement.name = target_name
        animations = list(getattr(model, "animations", []) or [])
        for index, anim in enumerate(animations):
            if str(getattr(anim, "name", "")).lower() == target_name.lower():
                animations[index] = replacement
                break
        else:
            animations.append(replacement)
        model.animations = animations
        if hasattr(self, "animations_panel"):
            self._load_animation_panel_model(model, select_name=target_name)
        self._populate_animation_library_from_current_model()
        self._show_content_browser("Animation")
        self._log(f"Animation override: {source_name} -> {target_name}", "success")
        return target_name
    def _terminal_create_viewport_widget(
        self,
        name: str,
        *,
        kind: str = "widget",
        overwrite: bool = False,
        public_export: bool = False,
    ) -> dict[str, object]:
        result = create_custom_viewport_widget(
            name,
            kind=kind,
            overwrite=overwrite,
            public_export=public_export,
        )
        self._log(f"Created viewport {result['kind']} scaffold: {result['path']}", "success")
        return result
    def _open_texture_tool_window(self):
        window = getattr(self, "texture_tool_window", None)
        if window is None:
            self._not_migrated("Texture Tool")
            return
        window.show()
        window.raise_()
        window.activateWindow()
    def _open_blueprint_editor_window(self):
        window = getattr(self, "blueprint_window", None)
        if window is None:
            self._not_migrated("Blueprint Editor")
            return
        window.show()
        window.raise_()
        window.activateWindow()
    def _open_placeable_builder_window(self):
        """Lazily open the dedicated reusable-placeable authoring workbench."""

        window = getattr(self, "placeable_builder_window", None)
        app_root = Path(getattr(self, "app_root", Path.cwd()))
        library_root = app_root / "Saved" / "PlaceableLibrary"
        manager = getattr(self, "_resource_manager", None)
        if manager is None:
            get_manager = getattr(self, "_get_resource_manager", None)
            if callable(get_manager):
                try:
                    manager = get_manager()
                except Exception:
                    manager = None
        provider = None
        if manager is not None:
            try:
                from src.core.resources.game_resource_provider import ResourceManagerGameResourceProvider

                provider = ResourceManagerGameResourceProvider(manager)
            except Exception:
                provider = None
        if window is None:
            from src.gui.qt_lib.windows.qt_placeable_builder import QtPlaceableBuilderWindow
            from src.gui.qt_lib.windows.qt_placeable_builder_controller import QtPlaceableBuilderController

            window = QtPlaceableBuilderWindow(self)
            self.placeable_builder_window = window
            controller = QtPlaceableBuilderController(
                window,
                library_root=library_root,
                provider=provider,
                resource_manager=manager,
                parent=window,
            )
            self.placeable_builder_controller = controller
            window.libraryChanged.connect(self._on_placeable_library_changed)
        else:
            controller = getattr(self, "placeable_builder_controller", None)
            if controller is not None:
                controller.set_library_root(library_root)
                controller.set_provider(provider, resource_manager=manager)
            else:
                window.set_library_root(library_root)
        set_renderer_settings = getattr(window, "set_renderer_settings", None)
        if callable(set_renderer_settings):
            set_renderer_settings(getattr(self, "settings_data", {}) or {})
        set_navigation_profile = getattr(window, "set_navigation_profile", None)
        if callable(set_navigation_profile):
            profile = (getattr(self, "settings_data", {}) or {}).get(
                "viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE
            )
            set_navigation_profile(profile)
        window.show()
        window.raise_()
        window.activateWindow()

    def _open_particle_editor_window(self):
        """Lazily open the emitter particle editing workspace."""

        window = getattr(self, "particle_editor_window", None)
        manager = getattr(self, "_resource_manager", None)
        if manager is None:
            get_manager = getattr(self, "_get_resource_manager", None)
            if callable(get_manager):
                try:
                    manager = get_manager()
                except Exception:
                    manager = None
        if window is None:
            from src.gui.qt_lib.windows.qt_particle_editor import QtParticleEditorWindow

            window = QtParticleEditorWindow(
                self,
                resource_manager=manager,
                settings_data=getattr(self, "settings_data", {}) or {},
                app_root=Path(getattr(self, "app_root", Path.cwd())),
            )
            self.particle_editor_window = window
            theme_manager = getattr(self, "theme_manager", None)
            current_theme = getattr(theme_manager, "current_theme", None)
            if current_theme is not None:
                try:
                    window.apply_ghost_theme(current_theme)
                except Exception:
                    pass
        elif manager is not None:
            window.set_resource_manager(manager)
        set_renderer_settings = getattr(window, "set_renderer_settings", None)
        if callable(set_renderer_settings):
            set_renderer_settings(getattr(self, "settings_data", {}) or {})
        window.show()
        window.raise_()
        window.activateWindow()

    def _on_placeable_library_changed(self, root: str) -> None:
        """Refresh both the workbench and any open Map Studio after a save."""

        controller = getattr(self, "placeable_builder_controller", None)
        if controller is not None:
            controller.refresh_library()
        map_window = getattr(self, "module_editor_window", None)
        if map_window is not None:
            set_root = getattr(map_window, "set_placeable_library_root", None)
            if callable(set_root):
                set_root(root)
            refresh = getattr(map_window, "refresh_placeable_library", None)
            if callable(refresh):
                refresh()
        log = getattr(self, "_log", None)
        if callable(log):
            log("Placeable Library refreshed in Placeable Builder and Map Studio.", "success")
    def _quick_autorig(self):
        model = self._require_model("Auto-Rig")
        if model is None:
            return
        try:
            from src.autorig.auto_rigger import AutoRigger

            rigged = AutoRigger().rig_model(model, template="humanoid")
            self._set_model_internal(rigged, self._model_path)
            self._log("Auto-rig applied.", "success")
            if hasattr(self, "rig_panel"):
                self.rig_panel.status_label.setText("Auto-rig applied.")
        except Exception as exc:
            self._log(f"Auto-rig error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Auto-Rig Error", str(exc))
    def _remove_rig(self):
        model = self._require_model("Remove Rigging")
        if model is None:
            return
        try:
            from src.core.geometry.model_data import NodeFlags

            for node in model.mesh_nodes() if hasattr(model, "mesh_nodes") else []:
                node.flags &= ~int(NodeFlags.SKIN)
                node.skin_data = []
                node.bone_map = []
            if getattr(model, "root_node", None):
                model.root_node.children = [
                    child for child in model.root_node.children if getattr(child, "is_mesh", False)
                ]
            self._set_model_internal(model, self._model_path)
            self._log("Rigging removed.", "success")
            if hasattr(self, "rig_panel"):
                self.rig_panel.status_label.setText("Rigging removed.")
        except Exception as exc:
            self._log(f"Remove rigging error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Remove Rigging Error", str(exc))
    def _clear_skeleton(self):
        model = self._require_model("Clear Skeleton")
        if model is None:
            return
        if not getattr(model, "root_node", None):
            QtWidgets.QMessageBox.warning(self, "Clear Skeleton", "No root node found.")
            return
        if QtWidgets.QMessageBox.question(
            self,
            "Clear Skeleton",
            "Remove all bone/dummy nodes and skin weights from this model?\n\nMesh nodes will be re-parented to the root.",
        ) != QtWidgets.QMessageBox.Yes:
            return
        try:
            from src.core.geometry.model_data import NodeFlags

            root = model.root_node
            mesh_nodes = [node for node in model.all_nodes() if getattr(node, "is_mesh", False)]
            for node in mesh_nodes:
                node.flags &= ~int(NodeFlags.SKIN)
                node.skin_data = []
                node.bone_map = []
                if hasattr(node, "bone_map_floats"):
                    node.bone_map_floats = []
                node.parent = root
                node.position = (0.0, 0.0, 0.0)
            root.children = mesh_nodes
            self._set_model_internal(model, self._model_path)
            self._log(f"Skeleton cleared: {len(mesh_nodes)} mesh nodes remain at root.", "success")
            if hasattr(self, "rig_panel"):
                self.rig_panel.status_label.setText(f"Skeleton cleared: {len(mesh_nodes)} mesh nodes")
        except Exception as exc:
            self._log(f"Clear skeleton error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Clear Skeleton Error", str(exc))
    def _show_weight_stats(self):
        model = self._require_model("Weight Stats")
        if model is None:
            return
        try:
            from src.autorig.auto_rigger import AutoRigger

            stats = AutoRigger().get_weight_stats(model)
            if not stats:
                QtWidgets.QMessageBox.information(self, "Weight Stats", "No rigged nodes found. Run Auto-Rig first.")
                return
            lines = []
            for node_name, data in stats.items():
                lines.append(f"-- {node_name} --")
                lines.append(
                    f"  verts={data['total_verts']}  avg_infl={data['avg_influences']:.2f}  "
                    f"max_infl={data['max_influences']}  zero={data['zero_weight_verts']}"
                )
                lines.append("  Top bones:")
                for bone_name, total_w in sorted(data["bone_usage"].items(), key=lambda item: -item[1])[:8]:
                    bar = "#" * int(total_w / max(data["total_verts"], 1) * 20)
                    lines.append(f"    {bone_name:<16} {bar}")
                lines.append("")
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("Weight Statistics")
            dialog.resize(560, 420)
            layout = QtWidgets.QVBoxLayout(dialog)
            text = QtWidgets.QPlainTextEdit()
            text.setReadOnly(True)
            text.setPlainText("\n".join(lines))
            layout.addWidget(text, 1)
            close_button = QtWidgets.QPushButton("Close")
            close_button.clicked.connect(dialog.accept)
            layout.addWidget(close_button, 0, QtCore.Qt.AlignRight)
            dialog.exec()
        except Exception as exc:
            self._log(f"Weight stats error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Weight Stats", str(exc))
    def _handle_rig_action(self, action: str):
        if action == "Auto-Rig Model":
            self._quick_autorig()
        elif action == "Remove Rigging":
            self._remove_rig()
        elif action == "Clear Skeleton":
            self._clear_skeleton()
        elif action == "Weight Stats":
            self._show_weight_stats()
        else:
            self._log(f"{action} is waiting for its Qt behavior migration.", "warning")
