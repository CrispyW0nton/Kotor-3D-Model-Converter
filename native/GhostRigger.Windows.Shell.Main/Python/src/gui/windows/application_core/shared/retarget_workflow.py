"""Animation retarget preview, apply, and workbench assignment behavior."""

from __future__ import annotations

import time

try:
    from PySide6 import QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.core.retargeting.retarget_output_naming import KotorOutputAnimationNameMode


class RetargetWorkflowMixin:
    """Animation retarget preview, apply, and workbench assignment behavior."""

    def _retarget_config(self):
        from src.core.animation_retargeting.retargeter import RetargetConfig

        kwargs = (
            self.animation_retarget_panel.config_kwargs()
            if hasattr(self, "animation_retarget_panel") else {}
        )
        return RetargetConfig(**kwargs)
    def _retarget_refresh_mapping(self):
        if self._retarget_source_model is None or self._retarget_target_model is None:
            return None
        from src.core.animation_retargeting.retargeter import build_bone_map

        manual_mapping = {}
        if hasattr(self.animation_retarget_panel, "panel"):
            manual_mapping = self.animation_retarget_panel.panel.manual_bone_mapping()
        self._retarget_mapping_report = build_bone_map(
            self._retarget_source_model,
            self._retarget_target_model,
            manual_mapping=manual_mapping,
        )
        self.animation_retarget_panel.set_mapping_report(self._retarget_mapping_report)
        return self._retarget_mapping_report
    def _retarget_set_source_current(self):
        model = self._require_model("Retarget Source")
        if model is None:
            return
        if not (getattr(model, "animations", []) or []):
            QtWidgets.QMessageBox.information(
                self, "Retarget Source",
                "The current model has no local animations to use as a source.",
            )
            return
        self._retarget_source_model = model
        self._retarget_engine = None
        controller = getattr(self, "retarget_workbench_controller", None)
        if controller is not None:
            controller.set_source_kotor_model(model)
            self._apply_retarget_workbench_mode_status()
        self.animation_retarget_panel.set_texture_dir(self._texture_dir)
        game = (self._current_game or self._infer_game_from_model(model)).upper()
        mgr = self._get_resource_manager()
        if mgr is not None:
            self.animation_retarget_panel.set_source_resource_context(mgr, game)
        self.animation_retarget_panel.set_source_model(model, game)
        self._retarget_refresh_mapping()
        self._log(f"Retarget source set: {getattr(model, 'name', '?')}", "success")
    def _retarget_set_target_current(self):
        model = self._require_model("Retarget Target")
        if model is None:
            return
        self._retarget_target_model = model
        self._retarget_engine = None
        self.animation_retarget_panel.set_texture_dir(self._texture_dir)
        game = (self._current_game or self._infer_game_from_model(model)).upper()
        mgr = self._get_resource_manager()
        if mgr is not None:
            self.animation_retarget_panel.set_target_resource_context(mgr, game)
        self.animation_retarget_panel.set_target_model(model, game)
        self._retarget_refresh_mapping()
        if hasattr(self, "retarget_preview_controller"):
            self._sync_retarget_preview_target()
        self._apply_retarget_workbench_mode_status()
        self._log(f"Retarget target set: {getattr(model, 'name', '?')}", "success")
    def _retarget_preview(self, anim_name: str):
        if not anim_name:
            QtWidgets.QMessageBox.information(self, "Retarget", "Select a source animation first.")
            return
        if self._retarget_source_model is None or self._retarget_target_model is None:
            QtWidgets.QMessageBox.information(self, "Retarget", "Set both a source and target model.")
            return
        controller = getattr(self, "retarget_workbench_controller", None)
        if controller is not None:
            controller.set_source_kotor_model(self._retarget_source_model)
            controller.set_source_kotor_animation_slot(anim_name)
            self._apply_retarget_workbench_mode_status()
        try:
            from src.core.animation.animation_engine import AnimationEngine

            self._animation_timer.stop()
            self._animation_engine = None
            self._retarget_engine = AnimationEngine(self._retarget_source_model)
            if not self._retarget_engine.play(anim_name, loop=True, blend=False):
                QtWidgets.QMessageBox.information(self, "Retarget", f"Animation not found: {anim_name}")
                return
            self._retarget_refresh_mapping()
            self._retarget_last_tick = None
            self._retarget_timer.start()
            self._log(
                f"Retarget preview: {getattr(self._retarget_source_model, 'name', '?')}:{anim_name} -> "
                f"{getattr(self._retarget_target_model, 'name', '?')}",
                "success",
            )
        except Exception as exc:
            self._log(f"Retarget preview error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Retarget", str(exc))
    def _retarget_workbench_preview_from_window(self, anim_name: str) -> None:
        controller = getattr(self, "retarget_workbench_controller", None)
        if controller is None:
            self._retarget_preview(anim_name)
            return
        self._ensure_retarget_workbench_target_viewport_adapter()
        self._apply_retarget_workbench_animation_assignment(anim_name)
        mode_name = str(getattr(getattr(controller.state, "mode", None), "name", "") or "")
        if anim_name and mode_name == "UNREAL_TO_KOTOR":
            clip = getattr(controller.state, "source_clip", None)
            current_name = str(getattr(clip, "clip_name", "") or "")
            source_path = str(getattr(clip, "source_path", "") or "")
            if clip is not None and source_path and anim_name != current_name:
                try:
                    clip = controller.load_source_clip(source_path, clip_name=anim_name)
                    window = getattr(self, "animation_retarget_window", None)
                    if window is not None and hasattr(window, "set_source_clip_preview"):
                        mesh_model = getattr(window, "_source_clip_mesh_model", None)
                        window.set_source_clip_preview(clip, mesh_model=mesh_model)
                except Exception as exc:
                    self._log(f"UE/FBX source clip reload failed: {exc}", "error")
                    QtWidgets.QMessageBox.critical(self, "Retarget Source Animation", str(exc))
                    return
            window = getattr(self, "animation_retarget_window", None)
            if window is not None and hasattr(window, "set_source_clip_animation_pose"):
                window.set_source_clip_animation_pose(anim_name, 0.0)
        if self._retarget_source_model is not None and mode_name in {"KOTOR_TO_KOTOR", "KOTOR_TO_UNREAL"}:
            controller.set_source_kotor_model(self._retarget_source_model)
        if self._retarget_target_model is not None and mode_name != "KOTOR_TO_UNREAL":
            controller.set_target_model(self._retarget_target_model)
        if anim_name and mode_name in {"KOTOR_TO_KOTOR", "KOTOR_TO_UNREAL"}:
            controller.set_source_kotor_animation_slot(anim_name)
        self._apply_retarget_workbench_mode_status()
        self._preview_retarget_animation()
    def _retarget_workbench_play_source_animation_from_window(self, anim_name: str) -> None:
        controller = getattr(self, "retarget_workbench_controller", None)
        window = getattr(self, "animation_retarget_window", None)
        if controller is None or window is None or not anim_name:
            return
        mode_name = str(getattr(getattr(controller.state, "mode", None), "name", "") or "")
        if mode_name != "UNREAL_TO_KOTOR":
            return
        clip = getattr(controller.state, "source_clip", None)
        source_path = str(getattr(clip, "source_path", "") or "")
        if not source_path:
            return
        try:
            loaded = controller.load_source_clip(source_path, clip_name=anim_name)
            if hasattr(window, "set_source_clip_preview"):
                mesh_model = getattr(window, "_source_clip_mesh_model", None)
                window.set_source_clip_preview(loaded, mesh_model=mesh_model)
            if hasattr(window, "play_source_clip_animation"):
                window.play_source_clip_animation(anim_name)
            self._ensure_retarget_workbench_target_viewport_adapter()
            self._apply_retarget_workbench_animation_assignment(anim_name)
            if self._retarget_target_model is not None:
                controller.set_target_model(self._retarget_target_model)
            self._refresh_target_kotor_animation_slots()
            if controller.can_preview():
                show_nodes = True
                if hasattr(window, "retarget_bones_visible"):
                    show_nodes = bool(window.retarget_bones_visible())
                preview = controller.preview(auto_play=False, show_node_overlay=show_nodes)
                if preview is not None:
                    self._log(f"Retargeted source animation to target preview: {anim_name}", "success")
            elif getattr(controller, "last_error", ""):
                self._log(f"Retarget preview not ready while playing source: {controller.last_error}", "warning")
            self._apply_retarget_workbench_mode_status()
        except Exception as exc:
            self._log(f"UE/FBX source animation playback load failed: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Play Source Animation", str(exc))
    def _retarget_workbench_sync_target_time_from_source(self, animation_name: str, time_seconds: float) -> None:
        controller = getattr(self, "retarget_workbench_controller", None)
        if controller is None:
            return
        mode_name = str(getattr(getattr(controller.state, "mode", None), "name", "") or "")
        if mode_name not in {"UNREAL_TO_KOTOR", "KOTOR_TO_KOTOR"}:
            return
        preview = getattr(controller.state, "last_preview_result", None)
        if preview is None:
            return
        adapter = self._ensure_retarget_workbench_target_viewport_adapter()
        if adapter is None or not hasattr(adapter, "set_time"):
            return
        try:
            adapter.set_time(float(time_seconds))
        except Exception as exc:
            self._log(f"Retarget target time sync failed: {exc}", "warning")
    def _retarget_workbench_apply_from_window(self, anim_name: str) -> None:
        controller = getattr(self, "retarget_workbench_controller", None)
        if controller is None:
            self._retarget_apply(anim_name)
            return
        self._ensure_retarget_workbench_target_viewport_adapter()
        self._apply_retarget_workbench_animation_assignment(anim_name)
        if not controller.can_export() and anim_name:
            self._retarget_workbench_preview_from_window(anim_name)
        self._export_retarget_preview()
    def _apply_retarget_workbench_animation_assignment(self, anim_name: str) -> None:
        controller = getattr(self, "retarget_workbench_controller", None)
        window = getattr(self, "animation_retarget_window", None)
        if controller is None or window is None or not anim_name:
            return
        if not hasattr(window, "current_animation_assignment"):
            return
        assignment = window.current_animation_assignment() or {}
        if str(assignment.get("source_animation") or anim_name) != str(anim_name):
            try:
                if hasattr(window.panel, "assignment_for_animation"):
                    assignment = window.panel.assignment_for_animation(anim_name)
            except Exception:
                assignment = {}
        output_name = str(assignment.get("output_name") or "").strip()
        output_mode = str(assignment.get("output_mode") or "").strip()
        if not output_name:
            return
        mode_name = str(getattr(getattr(controller.state, "mode", None), "name", "") or "")
        if mode_name in {"UNREAL_TO_KOTOR", "KOTOR_TO_KOTOR"}:
            if output_mode == KotorOutputAnimationNameMode.VANILLA_SLOT.value:
                controller.set_target_kotor_animation_slot(output_name)
            else:
                controller.set_custom_kotor_animation_name(output_name)
            self._sync_retarget_assignment_controls(output_name, output_mode)
        elif mode_name == "KOTOR_TO_UNREAL":
            controller.set_output_unreal_clip_name(output_name)
    def _sync_retarget_assignment_controls(self, output_name: str, output_mode: str) -> None:
        mode_combo = self._retarget_workbench_widget("kotor_output_name_mode_combo")
        slot_combo = self._retarget_workbench_widget("target_kotor_animation_slot_combo")
        custom_edit = self._retarget_workbench_widget("custom_kotor_animation_name_edit")
        if mode_combo is not None:
            mode_value = (
                KotorOutputAnimationNameMode.VANILLA_SLOT.value
                if output_mode == KotorOutputAnimationNameMode.VANILLA_SLOT.value
                else KotorOutputAnimationNameMode.CUSTOM_PATCH.value
            )
            index = mode_combo.findData(mode_value)
            if index >= 0:
                mode_combo.blockSignals(True)
                mode_combo.setCurrentIndex(index)
                mode_combo.blockSignals(False)
        if output_mode == KotorOutputAnimationNameMode.VANILLA_SLOT.value and slot_combo is not None:
            slot_combo.blockSignals(True)
            slot_combo.setCurrentText(output_name)
            slot_combo.blockSignals(False)
        elif custom_edit is not None:
            custom_edit.blockSignals(True)
            custom_edit.setText(output_name)
            custom_edit.blockSignals(False)
    def _retarget_target_label(self) -> str:
        model = self._retarget_target_model
        if model is None:
            return ""
        path = str(getattr(model, "mdl_path", "") or "").strip()
        if path:
            return path
        retarget_panel = getattr(self, "animation_retarget_panel", None)
        game = str(
            getattr(retarget_panel, "_target_game", "")
            or self._current_game
            or self._infer_game_from_model(model)
        ).upper()
        name = str(getattr(model, "name", "") or "target").strip() or "target"
        return f"{game}:{name}"
    def _activate_retarget_target_model(self, selected_anim: str) -> None:
        model = self._retarget_target_model
        if model is None:
            return
        if self._current_model is not model:
            self._set_model_internal(model, self._retarget_target_label())
        else:
            if hasattr(self, "animations_panel"):
                self._load_animation_panel_model(model)
        self._populate_animation_library_from_current_model()
        if hasattr(self, "animations_panel"):
            self.animations_panel.select_animation(selected_anim)
        self._show_right_tab("Animations")
    def _retarget_apply(self, anim_name: str):
        if not anim_name:
            QtWidgets.QMessageBox.information(self, "Retarget", "Select a source animation first.")
            return
        if self._retarget_source_model is None or self._retarget_target_model is None:
            QtWidgets.QMessageBox.information(self, "Retarget", "Set both a source and target model.")
            return
        try:
            from src.core.animation_retargeting.retargeter import retarget_animation

            source_anim = next(
                (
                    anim for anim in (getattr(self._retarget_source_model, "animations", []) or [])
                    if str(getattr(anim, "name", "")).lower() == anim_name.lower()
                ),
                None,
            )
            if source_anim is None:
                QtWidgets.QMessageBox.information(self, "Retarget", f"Animation not found: {anim_name}")
                return
            apply_options = self.animation_retarget_panel.request_apply_options(
                source_anim,
                self._retarget_target_model,
            )
            if apply_options is None:
                return
            report = self._retarget_refresh_mapping()
            new_anim, report = retarget_animation(
                source_anim,
                self._retarget_source_model,
                self._retarget_target_model,
                config=self._retarget_config(),
                mapping_report=report,
            )
            new_anim.name = str(apply_options["name"])
            target_anims = getattr(self._retarget_target_model, "animations", None)
            if target_anims is None:
                self._retarget_target_model.animations = []
                target_anims = self._retarget_target_model.animations
            replaced = False
            if apply_options.get("replace"):
                needle = new_anim.name.lower()
                for index, existing in enumerate(list(target_anims)):
                    if str(getattr(existing, "name", "") or "").lower() == needle:
                        target_anims[index] = new_anim
                        replaced = True
                        break
            if not replaced:
                target_anims.append(new_anim)
            self._activate_retarget_target_model(new_anim.name)
            if hasattr(self, "animation_retarget_panel") and hasattr(self.animation_retarget_panel, "panel"):
                self.animation_retarget_panel.panel.set_target_model(self._retarget_target_model)
            self.animation_retarget_panel.set_mapping_report(report)
            self.statusBar().showMessage(
                f"{'Replaced' if replaced else 'Added'} animation {new_anim.name} on "
                f"{getattr(self._retarget_target_model, 'name', 'target')}"
            )
            self._log(
                f"{'Replaced' if replaced else 'Added'} retargeted animation {new_anim.name} "
                f"from {anim_name} to target animation list ({report.matched_count} bones)",
                "success",
            )
        except Exception as exc:
            self._log(f"Retarget apply error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Retarget", str(exc))
    def _retarget_stop(self):
        self._retarget_timer.stop()
        self._retarget_last_tick = None
        if self._retarget_engine is not None:
            self._retarget_engine.stop()
        adapters = [getattr(self, "_retarget_preview_viewport", None)]
        window = getattr(self, "animation_retarget_window", None)
        if window is not None:
            adapters.append(getattr(window, "_retarget_target_viewport_adapter", None))
        for adapter in adapters:
            if adapter is not None and hasattr(adapter, "pause"):
                adapter.pause()
        if hasattr(self, "animation_retarget_panel"):
            self.animation_retarget_panel.clear_poses()
        self._log("Retarget preview stopped.", "info")
    def _retarget_pause(self):
        self._retarget_timer.stop()
        self._retarget_last_tick = None
        if self._retarget_engine is not None:
            self._retarget_engine.stop()
        adapters = [getattr(self, "_retarget_preview_viewport", None)]
        window = getattr(self, "animation_retarget_window", None)
        if window is not None:
            adapters.append(getattr(window, "_retarget_target_viewport_adapter", None))
        for adapter in adapters:
            if adapter is not None and hasattr(adapter, "pause"):
                adapter.pause()
        self._log("Retarget preview paused.", "info")
    def _tick_retarget_animation(self):
        engine = self._retarget_engine
        if engine is None or not engine.is_playing:
            self._retarget_timer.stop()
            self._retarget_last_tick = None
            return
        if self._retarget_source_model is None or self._retarget_target_model is None:
            self._retarget_stop()
            return
        now = time.perf_counter()
        if self._retarget_last_tick is None:
            dt = 1.0 / 30.0
        else:
            dt = max(1.0 / 60.0, min(now - self._retarget_last_tick, 0.25))
        self._retarget_last_tick = now
        still_playing = engine.advance(dt)
        source_pose = engine.evaluate()
        anim = engine.current_animation
        anim_name = getattr(anim, "name", "") if anim else ""
        anim_length = float(getattr(anim, "length", 0.0) or 0.0) if anim else 0.0
        try:
            from src.core.animation_retargeting.retargeter import retarget_pose

            result = retarget_pose(
                source_pose,
                self._retarget_source_model,
                self._retarget_target_model,
                config=self._retarget_config(),
                mapping_report=self._retarget_mapping_report,
            )
            self._retarget_mapping_report = result.report
            if hasattr(self, "animation_retarget_panel"):
                self.animation_retarget_panel.set_source_pose(
                    source_pose,
                    name=anim_name,
                    time=engine.current_time,
                    length=anim_length,
                )
                self.animation_retarget_panel.set_target_pose(
                    result.pose,
                    name=f"retarget:{anim_name}",
                    time=engine.current_time,
                    length=anim_length,
                )
        except Exception as exc:
            self._log(f"Retarget tick error: {exc}", "error")
            self._retarget_stop()
            return
        if not still_playing:
            self._retarget_stop()
