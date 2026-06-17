"""Animation source selection, playback, baking, export, and library scan behavior."""

from __future__ import annotations

import copy
import logging
import math
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

try:
    from PySide6 import QtCore, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.gui.qt_lib.panels.qt_animation_panel import animation_row_label
from src.gui.windows.application_core.application_core_lib.shared.workers import AnimationLibraryScanWorker

log = logging.getLogger(__name__)


class AnimationWorkflowMixin:
    """Animation source selection, playback, baking, export, and library scan behavior."""

    def _tag_animation_pose_source(self, pose, model, anim_name: str = "", game: str = ""):
        if pose is None:
            return pose
        try:
            setattr(pose, "_gr_animation_source_model_id", id(model) if model is not None else 0)
            setattr(pose, "_gr_animation_source_model_name", str(getattr(model, "name", "") or ""))
            scene_object = self._animation_scene_object_for_model(model)
            if scene_object is not None:
                metadata = getattr(scene_object, "metadata", {}) or {}
                setattr(pose, "_gr_animation_scene_object_id", str(getattr(scene_object, "id", "") or ""))
                setattr(pose, "_gr_animation_scene_import_id", str(metadata.get("scene_import_id") or getattr(scene_object, "id", "") or ""))
            if anim_name:
                setattr(pose, "_gr_animation_name", str(anim_name))
            if game:
                setattr(pose, "_gr_animation_game", str(game))
        except Exception:
            pass
        return pose

    def _animation_scene_object_for_model(self, model):
        if model is None:
            return None
        scene_manager = getattr(self, "scene_manager", None)
        if scene_manager is None:
            return None
        try:
            selected = list(scene_manager.get_selected_objects() or [])
        except Exception:
            selected = []
        for obj in reversed(selected):
            metadata = getattr(obj, "metadata", {}) or {}
            if metadata.get("_runtime_model") is model:
                return obj
            if metadata.get("_runtime_bas_body_model") is model:
                return obj
        try:
            objects = list(getattr(scene_manager.active_scene, "objects", []) or [])
        except Exception:
            objects = []
        matches = [
            obj
            for obj in objects
            if (getattr(obj, "metadata", {}) or {}).get("_runtime_model") is model
        ]
        return matches[0] if len(matches) == 1 else None

    def _handle_animation_selected(self, anim_name: str):
        model = self._animation_source_model()
        if not model or not anim_name:
            return
        model_game = self._animation_model_game(model)
        inheritance_game = self._animation_inheritance_game(model)
        inheritance_supermodel = self._animation_inheritance_supermodel(model)
        try:
            from src.core.animation.animation_engine import AnimationEngine, SuperModelResolver

            mgr = self._get_resource_manager()
            if mgr is not None:
                SuperModelResolver.configure(mgr)
            with self._animation_resolution_context(model, inheritance_game, inheritance_supermodel):
                engine = AnimationEngine(model)
                entries = engine.list_all_animations()
            for entry in entries:
                if str(entry.get("name", "") or "") != anim_name:
                    continue
                inherited = bool(entry.get("inherited"))
                source = str(entry.get("source") or getattr(model, "name", ""))
                source_type = str(entry.get("source_type") or ("inherited" if inherited else "local"))
                source_text = f"\nSource: {source_type} ({source})"
                display_name = animation_row_label(
                    anim_name,
                    inherited=inherited,
                    source=source if inherited else "",
                    game=inheritance_game if inherited else model_game,
                )
                self.animations_panel.info.setPlainText(
                    f"{display_name}\n"
                    f"Length: {float(entry.get('length') or 0.0):.3f} s\n"
                    f"Keys: {int(entry.get('key_count') or 0)}  "
                    f"Nodes: {int(entry.get('node_count') or 0)}  "
                    f"Events: {int(entry.get('event_count') or 0)}"
                    f"{source_text}"
                )
                self.animations_panel.seek.blockSignals(True)
                self.animations_panel.seek.setValue(0)
                self.animations_panel.seek.blockSignals(False)
                self._preview_selected_animation_first_frame(model, anim_name)
                return
        except Exception:
            log.debug("Inherited animation metadata lookup failed", exc_info=True)
        for anim in getattr(model, "animations", []) or []:
            if getattr(anim, "name", "") != anim_name:
                continue
            length = float(getattr(anim, "length", 0.0) or 0.0)
            events = getattr(anim, "events", []) or []
            node_anims = getattr(anim, "node_anims", {}) or {}
            key_count = 0
            for node_anim in node_anims.values() if hasattr(node_anims, "values") else []:
                for attr in ("position_keys", "rotation_keys", "scale_keys"):
                    key_count += len(getattr(node_anim, attr, []) or [])
            display_name = animation_row_label(anim_name, game=model_game)
            self.animations_panel.info.setPlainText(
                f"{display_name}\nLength: {length:.3f} s\nKeys: {key_count}  Nodes: {len(node_anims)}  Events: {len(events)}"
            )
            self.animations_panel.seek.blockSignals(True)
            self.animations_panel.seek.setValue(0)
            self.animations_panel.seek.blockSignals(False)
            self._preview_selected_animation_first_frame(model, anim_name)
            return
    def _preview_selected_animation_first_frame(self, model, anim_name: str) -> bool:
        if model is None or not anim_name:
            return False
        inheritance_game = self._animation_inheritance_game(model)
        inheritance_supermodel = self._animation_inheritance_supermodel(model)
        try:
            from src.core.animation.animation_engine import AnimationEngine, SuperModelResolver

            mgr = self._get_resource_manager()
            if mgr is not None:
                SuperModelResolver.configure(mgr)
            with self._animation_resolution_context(model, inheritance_game, inheritance_supermodel):
                if self._animation_engine is None or getattr(self._animation_engine, "model", None) is not model:
                    self._animation_engine = AnimationEngine(model)
                if not self._animation_engine.play(anim_name, loop=False, blend=False):
                    return False
                pose = self._tag_animation_pose_source(self._animation_engine.evaluate(0.0), model, anim_name, inheritance_game)
                current = self._animation_engine.current_animation
            length = float(getattr(current, "length", 0.0) or 0.0) if current is not None else 0.0
            self._animation_engine.seek(0.0)
            self._animation_engine.stop()
            self._animation_timer.stop()
            self._animation_last_tick = None
            self._animation_status_last_update = 0.0
            if hasattr(self, "viewport"):
                self.viewport.set_animation_pose(pose, name=anim_name, time=0.0, length=length)
                if hasattr(self.viewport, "set_animation_playback_active"):
                    self.viewport.set_animation_playback_active(False)
            return True
        except Exception as exc:
            self._log(f"Animation first-frame preview error: {exc}", "error")
            return False
    def _handle_animation_action(self, action: str, anim_name: str):
        if action == "Stop":
            self._animation_timer.stop()
            self._animation_last_tick = None
            self._animation_status_last_update = 0.0
            engine = getattr(self, "_animation_engine", None)
            if engine is not None:
                engine.stop()
            if hasattr(self, "viewport") and hasattr(self.viewport, "set_animation_playback_active"):
                self.viewport.set_animation_playback_active(False)
            if hasattr(self, "viewport") and hasattr(self.viewport, "clear_animation_pose"):
                self.viewport.clear_animation_pose()
            if hasattr(self, "animations_panel"):
                self.animations_panel.info.setPlainText("Animation stopped.")
            return
        body_model = self._require_model("Animations")
        if body_model is None:
            return
        model = self._animation_source_model(body_model)
        if model is None:
            QtWidgets.QMessageBox.information(self, "Animations", "No animation source is loaded for this part.")
            return
        model_game = self._animation_model_game(model)
        inheritance_game = self._animation_inheritance_game(model)
        inheritance_supermodel = self._animation_inheritance_supermodel(model)
        if action == "Export Binary MDL":
            self._export_mdl_binary()
            return
        try:
            from src.core.animation.animation_engine import AnimationEngine, SuperModelResolver

            mgr = self._get_resource_manager()
            if mgr is not None:
                SuperModelResolver.configure(mgr)
            with self._animation_resolution_context(model, inheritance_game, inheritance_supermodel):
                if self._animation_engine is None or getattr(self._animation_engine, "model", None) is not model:
                    self._animation_engine = AnimationEngine(model)
                animation_entries = self._animation_engine.list_all_animations()
        except Exception:
            animation_entries = []
        if not animation_entries and not (getattr(model, "animations", []) or []):
            QtWidgets.QMessageBox.information(self, "Animations", "No animations available on this model.")
            return
        if not anim_name and action not in {"Stop", "Loop"}:
            QtWidgets.QMessageBox.information(self, "Animations", "Select an animation first.")
            return
        try:
            if action == "Play":
                with self._animation_resolution_context(model, inheritance_game, inheritance_supermodel):
                    ok = self._animation_engine.play(anim_name, loop=self._animation_loop, blend=False)
                if ok:
                    self._animation_active_model = model
                    self._animation_active_game = inheritance_game
                    self._animation_active_supermodel = inheritance_supermodel
                    try:
                        self.viewport.set_anim_base_pose(self._tag_animation_pose_source(self._animation_engine.evaluate(0.0), model, anim_name, inheritance_game))
                    except Exception:
                        pass
                    if hasattr(self.viewport, "set_animation_playback_active"):
                        self.viewport.set_animation_playback_active(True, "animation playback")
                    self._animation_last_tick = None
                    self._animation_status_last_update = 0.0
                    self._animation_timer.start()
                self.animations_panel.info.setPlainText(
                    f"Playing {animation_row_label(anim_name, game=model_game)}" if ok else f"Animation not found: {anim_name}"
                )
                self._log(f"Animation play: {anim_name}", "success" if ok else "warning")
            elif action == "Loop":
                self._animation_loop = not self._animation_loop
                if self._animation_engine is not None:
                    self._animation_engine._loop = self._animation_loop
                self.animations_panel.info.setPlainText(f"Loop {'on' if self._animation_loop else 'off'}.")
            elif action == "Export":
                self._export_selected_animation(anim_name)
            elif action == "Bake Animation":
                self._bake_selected_animation(anim_name)
        except Exception as exc:
            self._log(f"Animation action error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Animations", str(exc))
    def _load_animation_panel_model(self, model, select_name: str = "") -> None:
        source_model = self._animation_source_model(model)
        if source_model is None:
            self._animation_engine = None
            self.animations_panel.load_model(None)
            source = self._animation_source_label()
            self.animations_panel.info.setPlainText(f"No suitable {source.lower()} model selected.")
            if hasattr(self, "viewport") and hasattr(self.viewport, "clear_animation_pose"):
                self.viewport.clear_animation_pose()
            return
        model = source_model
        model_game = self._animation_model_game(model)
        inheritance_game = self._animation_inheritance_game(model)
        inheritance_supermodel = self._animation_inheritance_supermodel(model)
        self.animations_panel.load_model(None)
        self.animations_panel.set_inheritance_game(model_game, emit=False)
        if model is None:
            return
        try:
            from src.core.animation.animation_engine import AnimationEngine, SuperModelResolver

            mgr = self._get_resource_manager()
            if mgr is not None:
                SuperModelResolver.configure(mgr)
            with self._animation_resolution_context(model, inheritance_game, inheritance_supermodel):
                engine = AnimationEngine(model)
                entries = self._filter_animation_browser_entries(model, engine.list_all_animations())
        except Exception:
            log.debug("Inherited animation panel load failed", exc_info=True)
            self.animations_panel.load_model(model, select_name=select_name, game=model_game)
            return
        existing = set()
        inherited_count = 0
        local_count = 0
        for entry in entries:
            name = str(entry.get("name") or "")
            if not name or name.lower() in existing:
                continue
            entry_game = inheritance_game if bool(entry.get("inherited")) else model_game
            if entry_game:
                entry = {**entry, "game": entry_game}
            self.animations_panel.add_effective_animation(entry)
            existing.add(name.lower())
            if bool(entry.get("inherited")):
                inherited_count += 1
            else:
                local_count += 1
        total = self.animations_panel.listbox.count()
        if inherited_count:
            self.animations_panel.info.setPlainText(
                f"{total} animation(s) for {getattr(model, 'name', 'selected model')}\n"
                f"Mode: {self._animation_source_label()}  Local: {local_count}  Inherited: {inherited_count}"
            )
        else:
            self.animations_panel.info.setPlainText(
                f"{total} animation(s) for {getattr(model, 'name', 'selected model')}\n"
                f"Mode: {self._animation_source_label()}  Local: {local_count}"
            )
        if select_name:
            self.animations_panel.select_animation(select_name)
    def _handle_animation_inheritance_game_changed(self, _game: str) -> None:
        model = getattr(self, "_current_model", None)
        if model is None:
            return
        selected = self.animations_panel.selected_animation() if hasattr(self, "animations_panel") else ""
        self._animation_engine = None
        self._load_animation_panel_model(model, select_name=selected)
    def _handle_animation_source_changed(self, _source: str) -> None:
        model = getattr(self, "_current_model", None)
        self._animation_engine = None
        self._load_animation_panel_model(model)
    def _animation_source_key(self) -> str:
        if hasattr(self, "animations_panel") and hasattr(self.animations_panel, "selected_animation_source"):
            return str(self.animations_panel.selected_animation_source() or "body").lower()
        return "body"
    def _animation_source_label(self) -> str:
        return {
            "head": "Head",
            "attachment": "Attachment / Weapon",
        }.get(self._animation_source_key(), "Body")
    @staticmethod
    def _is_head_animation_slot(anim_name: str) -> bool:
        key = str(anim_name or "").strip().lower()
        return key.startswith(("talk", "tlk", "listen", "look"))
    def _model_is_head_animation_source(self, model) -> bool:
        if model is None:
            return False
        try:
            from src.core.geometry.model_data import CharacterMode, detect_character_mode

            return detect_character_mode(model) == CharacterMode.HEAD
        except Exception:
            name = str(getattr(model, "name", "") or "").lower()
            return name.startswith(("pmh", "pfh")) or name.endswith("head")
    def _animation_source_model(self, fallback_model=None):
        source = self._animation_source_key()
        if source == "body":
            body_model = getattr(self, "_bas_body_model", None)
            if self._model_is_animation_browser_source(body_model):
                return body_model

            selected_objects = []
            scene_manager = getattr(self, "scene_manager", None)
            if scene_manager is not None:
                try:
                    selected_objects = list(scene_manager.get_selected_objects() or [])
                except Exception:
                    selected_objects = []
            if selected_objects:
                selected_object = self._selected_scene_model_object() if hasattr(self, "_selected_scene_model_object") else None
                selected_model = None
                if selected_object is not None and hasattr(self, "_runtime_model_for_scene_object"):
                    selected_model = self._runtime_model_for_scene_object(selected_object)
                return selected_model if self._model_is_animation_browser_source(selected_model) else None

            for candidate in (getattr(self, "_current_model", None), fallback_model):
                if self._model_is_animation_browser_source(candidate):
                    return candidate
            return None
        if source == "head":
            for attr in ("_current_head_model", "_attached_head_model", "_head_model"):
                model = getattr(self, attr, None)
                if self._model_is_animation_browser_source(model):
                    return model
            for model in (fallback_model, getattr(self, "_current_model", None)):
                if self._model_is_head_animation_source(model) and self._model_is_animation_browser_source(model):
                    return model
            return None
        for attr in ("_current_attachment_model", "_current_weapon_model", "_attached_weapon_model", "_attachment_model"):
            model = getattr(self, attr, None)
            if self._model_is_animation_browser_source(model):
                return model
        return None
    def _model_is_animation_browser_source(self, model) -> bool:
        if model is None:
            return False
        if getattr(model, "animations", None):
            return True
        supermodel = str(getattr(model, "supermodel", "") or "").strip().upper()
        if supermodel and supermodel not in {"NULL", "NONE"}:
            return True
        try:
            from src.core.geometry.model_data import CharacterMode, detect_character_mode, is_animation_supermodel

            if is_animation_supermodel(model):
                return True
            return detect_character_mode(model) in {
                CharacterMode.HEADLESS_BODY,
                CharacterMode.HEAD,
                CharacterMode.HUMANOID,
                CharacterMode.SUPERMODEL,
                CharacterMode.CREATURE,
            }
        except Exception:
            name = str(getattr(model, "name", "") or "").lower()
            return name.startswith(("pm", "pf", "n_", "c_", "s_"))
    def _filter_animation_browser_entries(self, model, entries: list[dict]) -> list[dict]:
        if self._animation_source_key() != "head" or not self._model_is_head_animation_source(model):
            return entries
        filtered: list[dict] = []
        for entry in entries:
            inherited = bool(entry.get("inherited"))
            source_scope = str(entry.get("source_scope") or "").lower()
            source_type = str(entry.get("source_type") or "").lower()
            if inherited or source_scope == "inherited" or source_type == "inherited":
                if not self._is_head_animation_slot(str(entry.get("name") or "")):
                    continue
            filtered.append(entry)
        return filtered
    def _animation_model_game(self, model) -> str:
        return str(getattr(self, "_current_game", "") or self._infer_game_from_model(model) or "").upper()
    def _animation_inheritance_game(self, model) -> str:
        selected = ""
        if hasattr(self, "animations_panel") and hasattr(self.animations_panel, "selected_inheritance_game"):
            selected = self.animations_panel.selected_inheritance_game()
        return str(selected or self._animation_model_game(model) or "K1").upper()
    def _animation_inheritance_supermodel(self, model) -> str:
        selected = ""
        if hasattr(self, "animations_panel") and hasattr(self.animations_panel, "selected_inheritance_supermodel"):
            selected = self.animations_panel.selected_inheritance_supermodel()
        return str(selected or getattr(model, "supermodel", "") or "").strip()
    @contextmanager
    def _animation_resolution_context(self, model, game: str, supermodel: str = ""):
        if model is None:
            yield
            return
        had_game_version = hasattr(model, "game_version")
        original_game_version = getattr(model, "game_version", None)
        original_supermodel = getattr(model, "supermodel", None)
        try:
            self._apply_animation_resolution_game(model, game)
            if supermodel:
                model.supermodel = supermodel
            yield
        finally:
            if original_supermodel is not None or hasattr(model, "supermodel"):
                model.supermodel = original_supermodel
            if had_game_version:
                model.game_version = original_game_version
    def _apply_animation_resolution_game(self, model, game: str) -> None:
        if model is None:
            return
        game = str(game or "").upper()
        if game not in {"K1", "K2"}:
            return
        try:
            from src.core.geometry.model_data import GameVersion

            model.game_version = GameVersion.K2 if game == "K2" else GameVersion.K1
        except Exception:
            pass
    def _request_bake_animation_options(self, anim_name: str) -> Optional[dict]:
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Bake Animation")
        layout = QtWidgets.QVBoxLayout(dialog)
        form = QtWidgets.QFormLayout()
        name_edit = QtWidgets.QLineEdit(anim_name)
        fps_spin = QtWidgets.QSpinBox()
        fps_spin.setRange(1, 120)
        fps_spin.setValue(30)
        replace_box = QtWidgets.QCheckBox("Replace animation with same name")
        replace_box.setChecked(True)
        form.addRow("Name:", name_edit)
        form.addRow("FPS:", fps_spin)
        layout.addLayout(form)
        layout.addWidget(replace_box)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return None
        name = name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.information(self, "Bake Animation", "Enter an animation name.")
            return None
        return {"name": name, "fps": int(fps_spin.value()), "replace": replace_box.isChecked()}
    def _bake_selected_animation(self, anim_name: str):
        model = self._require_model("Bake Animation")
        if model is None:
            return
        options = self._request_bake_animation_options(anim_name)
        if options is None:
            return
        baked = self._build_baked_animation(
            model,
            anim_name,
            str(options["name"]),
            fps=int(options["fps"]),
        )
        animations = getattr(model, "animations", None)
        if animations is None:
            model.animations = []
            animations = model.animations
        replaced = False
        if options.get("replace"):
            needle = baked.name.lower()
            for index, existing in enumerate(list(animations)):
                if str(getattr(existing, "name", "") or "").lower() == needle:
                    animations[index] = baked
                    replaced = True
                    break
        if not replaced:
            animations.append(baked)
        self._animation_engine = None
        if hasattr(self, "animations_panel"):
            self._load_animation_panel_model(model, select_name=baked.name)
            self.animations_panel.info.setPlainText(
                f"Baked {anim_name} -> {baked.name}\n"
                f"{len(getattr(baked, 'nodes', []) or [])} nodes @ {int(options['fps'])} fps"
            )
        self._populate_animation_library_from_current_model()
        self.statusBar().showMessage(f"Baked animation {baked.name}")
        self._log(
            f"{'Replaced' if replaced else 'Added'} baked animation {baked.name} "
            f"from {anim_name}",
            "success",
        )
    def _build_baked_animation(self, model, anim_name: str, output_name: str, fps: int = 30):
        from src.core.animation.animation_engine import AnimationEngine
        from src.core.geometry.model_data import Animation

        fps = max(1, int(fps or 30))
        engine = AnimationEngine(model)
        if not engine.play(anim_name, loop=False, blend=False):
            raise ValueError(f"Animation not found: {anim_name}")
        source_anim = engine.current_animation
        if source_anim is None:
            raise ValueError(f"Animation not found: {anim_name}")
        length = max(0.0, float(getattr(source_anim, "length", 0.0) or 0.0))
        frame_count = max(1, int(math.ceil(length * fps))) if length > 0.0 else 1
        times = [min(length, i / float(fps)) for i in range(frame_count + 1)]
        if not times:
            times = [0.0]

        base_nodes = {
            str(getattr(node, "name", "") or "").lower(): node
            for node in (list(model.all_nodes()) if hasattr(model, "all_nodes") else [])
            if getattr(node, "name", "")
        }
        sampled_poses = [(t, engine.evaluate(t)) for t in times]
        baked = Animation(
            name=output_name,
            length=length,
            transition_time=float(getattr(source_anim, "transition_time", 0.25) or 0.25),
            anim_root=str(getattr(source_anim, "anim_root", "") or ""),
            events=copy.deepcopy(getattr(source_anim, "events", []) or []),
            nodes=[],
        )
        ctrl_names = {
            8: "position",
            20: "orientation",
            36: "scale",
            100: "selfillumcolor",
            128: "alpha",
            132: "alpha",
        }

        for source_node in getattr(source_anim, "nodes", []) or []:
            key = str(getattr(source_node, "name", "") or "").lower()
            if not key:
                continue
            source_types = {
                int(ctrl.get("type", -1))
                for ctrl in (getattr(source_node, "controllers", []) or [])
                if isinstance(ctrl, dict)
            }
            if not source_types:
                continue
            base_node = base_nodes.get(key)
            if base_node is not None and hasattr(base_node, "clone_shallow"):
                baked_node = base_node.clone_shallow()
            elif hasattr(source_node, "clone_shallow"):
                baked_node = source_node.clone_shallow()
            else:
                baked_node = copy.copy(source_node)
            baked_node.name = str(getattr(base_node or source_node, "name", key) or key)
            baked_node.children = []
            baked_node.parent = None
            baked_node.controllers = []
            base_pos = tuple(getattr(base_node, "position", (0.0, 0.0, 0.0)) if base_node else (0.0, 0.0, 0.0))

            def _samples_for_node():
                for sample_time, pose in sampled_poses:
                    node_pose = getattr(pose, "nodes", {}).get(key)
                    if node_pose is not None:
                        yield sample_time, node_pose

            node_samples = list(_samples_for_node())
            if not node_samples:
                continue
            node_times = [sample_time for sample_time, _node_pose in node_samples]
            poses = [node_pose for _sample_time, node_pose in node_samples]
            if 8 in source_types:
                baked_node.controllers.append({
                    "type": 8,
                    "name": ctrl_names[8],
                    "columns": 3,
                    "times": node_times,
                    "values": [
                        [
                            float(node_pose.position[0]) - float(base_pos[0]),
                            float(node_pose.position[1]) - float(base_pos[1]),
                            float(node_pose.position[2]) - float(base_pos[2]),
                        ]
                        for node_pose in poses
                    ],
                })
            if 20 in source_types:
                baked_node.controllers.append({
                    "type": 20,
                    "name": ctrl_names[20],
                    "columns": 4,
                    "times": node_times,
                    "values": [[float(v) for v in node_pose.rotation[:4]] for node_pose in poses],
                })
            if 36 in source_types:
                baked_node.controllers.append({
                    "type": 36,
                    "name": ctrl_names[36],
                    "columns": 1,
                    "times": node_times,
                    "values": [[float(node_pose.scale)] for node_pose in poses],
                })
            alpha_type = 132 if 132 in source_types else 128 if 128 in source_types else None
            if alpha_type is not None:
                baked_node.controllers.append({
                    "type": alpha_type,
                    "name": ctrl_names[alpha_type],
                    "columns": 1,
                    "times": node_times,
                    "values": [[float(node_pose.alpha if node_pose.alpha is not None else 1.0)] for node_pose in poses],
                })
            if 100 in source_types:
                baked_node.controllers.append({
                    "type": 100,
                    "name": ctrl_names[100],
                    "columns": 3,
                    "times": node_times,
                    "values": [
                        [float(v) for v in (node_pose.selfillum or (0.0, 0.0, 0.0))[:3]]
                        for node_pose in poses
                    ],
                })
            if baked_node.controllers:
                baked.nodes.append(baked_node)
        return baked
    def _handle_animation_seek(self, percent: int):
        model = self._animation_source_model()
        anim_name = self.animations_panel.selected_animation() if hasattr(self, "animations_panel") else ""
        if model is None or not anim_name:
            return
        inheritance_game = self._animation_inheritance_game(model)
        inheritance_supermodel = self._animation_inheritance_supermodel(model)
        try:
            from src.core.animation.animation_engine import AnimationEngine, SuperModelResolver

            mgr = self._get_resource_manager()
            if mgr is not None:
                SuperModelResolver.configure(mgr)

            with self._animation_resolution_context(model, inheritance_game, inheritance_supermodel):
                if self._animation_engine is None or getattr(self._animation_engine, "model", None) is not model:
                    self._animation_engine = AnimationEngine(model)
                current = self._animation_engine.current_animation
                if current is None or getattr(current, "name", "") != anim_name:
                    if not self._animation_engine.play(anim_name, loop=self._animation_loop, blend=False):
                        return
                    self._animation_engine.stop()
                    current = self._animation_engine.current_animation
            length = float(getattr(current, "length", 0.0) or 0.0) if current else 0.0
            if length <= 0.0:
                return
            t = max(0.0, min(100.0, float(percent))) / 100.0 * length
            was_playing = self._animation_engine.is_playing
            self._animation_engine.seek(t)
            pose = self._tag_animation_pose_source(self._animation_engine.evaluate(), model, anim_name, inheritance_game)
            if hasattr(self, "viewport"):
                self.viewport.set_animation_pose(pose, name=anim_name, time=t, length=length)
            self.animations_panel.info.setPlainText(f"{anim_name}\n{t:.3f} / {length:.3f} s")
            if not was_playing:
                self._animation_engine.stop()
        except Exception as exc:
            self._log(f"Animation seek error: {exc}", "error")
    def _apply_animation_command_from_ipc(self, command: str, anim_name: str = "", *, loop: object = None, seek: object = None, source: str = "") -> bool:
        key = str(command or "").strip().lower().replace("-", "_").replace(" ", "_")
        panel = getattr(self, "animations_panel", None)
        if panel is None:
            self._log("IPC animation_command: animations panel unavailable.", "warning")
            return False
        if source and hasattr(panel, "set_animation_source"):
            panel.set_animation_source(str(source or "body"))
        if loop is not None:
            self._animation_loop = bool(loop)
        selected = str(anim_name or "").strip() or panel.selected_animation()
        if selected and key in {"select", "play", "preview", "seek"}:
            if not panel.select_animation(selected):
                self._log(f"IPC animation_command: animation not found {selected}", "warning")
                return False
            selected = panel.selected_animation()
        if key in {"select", "preview_first_frame"}:
            self._handle_animation_selected(selected)
            self._log(f"IPC animation_command select: {selected}", "info")
            return True
        if key in {"play", "preview"}:
            self._handle_animation_action("Play", selected)
            return True
        if key in {"stop", "clear"}:
            self._handle_animation_action("Stop", "")
            self._log("IPC animation_command stop", "info")
            return True
        if key == "loop":
            self._animation_loop = bool(loop) if loop is not None else not bool(getattr(self, "_animation_loop", False))
            engine = getattr(self, "_animation_engine", None)
            if engine is not None:
                try:
                    engine._loop = self._animation_loop
                except Exception:
                    pass
            panel.info.setPlainText(f"Loop {'on' if self._animation_loop else 'off'}.")
            self._log(f"IPC animation_command loop: {'on' if self._animation_loop else 'off'}", "info")
            return True
        if key == "seek":
            value = seek if seek is not None else 0
            try:
                percent = int(float(value))
            except (TypeError, ValueError):
                percent = 0
            self._handle_animation_seek(max(0, min(100, percent)))
            self._log(f"IPC animation_command seek: {percent}", "info")
            return True
        self._log(f"IPC animation_command: unknown command {command}", "warning")
        return False

    def _animation_state_snapshot(self) -> dict:
        panel = getattr(self, "animations_panel", None)
        engine = getattr(self, "_animation_engine", None)
        current = getattr(engine, "current_animation", None) if engine is not None else None
        return {
            "selected": panel.selected_animation() if panel is not None and hasattr(panel, "selected_animation") else "",
            "source": panel.selected_animation_source() if panel is not None and hasattr(panel, "selected_animation_source") else "body",
            "loop": bool(getattr(self, "_animation_loop", False)),
            "playing": bool(getattr(engine, "is_playing", False)) if engine is not None else False,
            "current": str(getattr(current, "name", "") or ""),
            "time": float(getattr(engine, "current_time", 0.0) or 0.0) if engine is not None else 0.0,
            "available_count": int(panel.listbox.count()) if panel is not None and hasattr(panel, "listbox") else 0,
        }
    def _tick_animation(self):
        engine = self._animation_engine
        if engine is None or not engine.is_playing:
            self._animation_timer.stop()
            self._animation_last_tick = None
            self._animation_status_last_update = 0.0
            return
        now = time.perf_counter()
        if self._animation_last_tick is None:
            dt = 1.0 / 30.0
        else:
            dt = max(1.0 / 60.0, min(now - self._animation_last_tick, 0.25))
        self._animation_last_tick = now
        still_playing = engine.advance(dt)
        anim = engine.current_animation
        anim_name = getattr(anim, "name", "") if anim else ""
        anim_length = float(getattr(anim, "length", 0.0) or 0.0) if anim else 0.0
        active_model = getattr(self, "_animation_active_model", None) or getattr(engine, "model", None)
        active_game = str(getattr(self, "_animation_active_game", "") or "")
        active_supermodel = str(getattr(self, "_animation_active_supermodel", "") or "")
        with self._animation_resolution_context(active_model, active_game, active_supermodel):
            pose = self._tag_animation_pose_source(
                pose=engine.evaluate(),
                model=active_model,
                anim_name=anim_name,
                game=active_game,
            )
        if hasattr(self, "viewport"):
            self.viewport.set_animation_pose(
                pose,
                name=anim_name,
                time=engine.current_time,
                length=anim_length,
            )
        should_update_status = (
            anim_length > 0
            and hasattr(self, "animations_panel")
            and (now - float(getattr(self, "_animation_status_last_update", 0.0) or 0.0)) >= 0.20
        )
        if should_update_status:
            self._animation_status_last_update = now
            pct = max(0, min(100, int((engine.current_time / anim_length) * 100.0)))
            self.animations_panel.seek.blockSignals(True)
            self.animations_panel.seek.setValue(pct)
            self.animations_panel.seek.blockSignals(False)
            self.animations_panel.info.setPlainText(
                f"Playing {anim_name}\n{engine.current_time:.3f} / {anim_length:.3f} s"
            )
        if not still_playing:
            self._animation_timer.stop()
            self._animation_last_tick = None
            self._animation_status_last_update = 0.0
            if hasattr(self.viewport, "set_animation_playback_active"):
                self.viewport.set_animation_playback_active(False)
    def _export_selected_animation(self, anim_name: str):
        model = self._require_model("Export Animation")
        if model is None:
            return
        path, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Animation",
            f"{anim_name}.json",
            "Animation JSON (*.json);;BVH (*.bvh)",
        )
        if not path:
            return
        from src.core.animation.animation_engine import AnimationEngine

        engine = AnimationEngine(model)
        if selected_filter.startswith("BVH") or path.lower().endswith(".bvh"):
            ok = engine.export_animation_bvh(anim_name, path)
        else:
            ok = engine.export_animation_json(anim_name, path)
        self._log(
            f"Exported animation {anim_name} -> {Path(path).name}" if ok else f"Animation export failed: {anim_name}",
            "success" if ok else "error",
        )
    def _populate_animation_library_from_current_model(self):
        if not hasattr(self, "animation_library_panel"):
            return
        model = self._current_model
        entries = self._collect_scene_animation_entries()
        scene_models = {
            id((getattr(obj, "metadata", {}) or {}).get("_runtime_model"))
            for obj in self.scene_manager.active_scene.objects
            if (getattr(obj, "metadata", {}) or {}).get("_runtime_model") is not None
        }
        if model is not None:
            include_current = not scene_models or id(model) not in scene_models
            if include_current:
                for anim in getattr(model, "animations", []) or []:
                    length = float(getattr(anim, "length", 0.0) or 0.0)
                    entries.append(
                        {
                            "model": getattr(model, "name", ""),
                            "animation": getattr(anim, "name", ""),
                            "frames": int(round(length * 30.0)) if length else "",
                            "source": "Current model",
                        }
                    )
        panel = getattr(self, "content_browser_panel", getattr(self, "animation_library_panel", None))
        if panel is not None and hasattr(panel, "set_scene_animation_entries"):
            panel.set_scene_animation_entries(entries)
        elif panel is not None and hasattr(panel, "set_animation_entries"):
            panel.set_animation_entries(entries)
        elif panel is not None and hasattr(panel, "set_entries"):
            panel.set_entries(entries)
    def _handle_animation_library_action(self, action: str):
        if action == "Scan Animations":
            self._scan_animation_library()
            return
        if action == "Refresh":
            self._populate_animation_library_from_current_model()
            count = len(self._collect_scene_animation_entries())
            model = self._current_model
            if model is not None and not count:
                count = len(getattr(model, "animations", []) or [])
            self._log(f"Animation library refreshed: {count} scene/current animation rows", "info")
            return
        panel = getattr(self, "content_browser_panel", getattr(self, "animation_library_panel", None))
        if action == "Stop":
            self._handle_animation_action("Stop", "")
            return
        entry = panel.selected_entry() if panel is not None and hasattr(panel, "selected_entry") else None
        if not entry:
            QtWidgets.QMessageBox.information(self, "Animation Library", "Select an animation entry first.")
            return
        anim_name = str(entry.get("animation") or "")
        if action in {"Load", "Preview"}:
            self._activate_animation_entry_model(entry)
            self._show_right_tab("Animations")
            matches = self.animations_panel.listbox.findItems(anim_name, QtCore.Qt.MatchExactly)
            if matches:
                self.animations_panel.listbox.setCurrentItem(matches[0])
            if action == "Preview":
                self._handle_animation_action("Play", anim_name)
        elif action == "Export":
            self._activate_animation_entry_model(entry)
            self._export_selected_animation(anim_name)
    def _scan_animation_library(self) -> None:
        if self._animation_scan_worker_is_running():
            self._log("Animation library scan is already running.", "warning")
            return
        rows = list(getattr(self, "_library_rows", []) or [])
        if not rows:
            QtWidgets.QMessageBox.information(self, "Animation Library", "Scan the Content Browser library first.")
            return
        k1_dir, k2_dir = self._configured_game_dirs()
        self._show_progress_toast("Scanning animations", "Reading animation headers from library models...")
        panel = getattr(self, "content_browser_panel", None)
        for name in ("scan_anims_button", "refresh_anims_button"):
            button = getattr(panel, name, None) if panel is not None else None
            if button is not None:
                button.setEnabled(False)
        worker = AnimationLibraryScanWorker(rows, k1_dir, k2_dir)
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_animation_library_scan_progress)
        worker.finished.connect(self._on_animation_library_scanned)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: setattr(self, "_animation_scan_thread", None))
        thread.finished.connect(lambda: setattr(self, "_animation_scan_worker", None))
        self._animation_scan_thread = thread
        self._animation_scan_worker = worker
        thread.start()
    @QtCore.Slot(str, int, int)
    def _on_animation_library_scan_progress(self, detail: str, value: int, total: int) -> None:
        self._update_progress_toast("Scanning animations", detail, value, total)
        self.statusBar().showMessage(detail)
    @QtCore.Slot(list, str)
    def _on_animation_library_scanned(self, entries: list, error: str) -> None:
        panel = getattr(self, "content_browser_panel", None)
        for name in ("scan_anims_button", "refresh_anims_button"):
            button = getattr(panel, name, None) if panel is not None else None
            if button is not None:
                button.setEnabled(True)
        if error:
            self._finish_progress_toast("Animation scan failed", "Check the output log for details.")
            self._log(f"Animation library scan failed:\n{error}", "error")
            return
        if panel is not None and hasattr(panel, "set_scanned_animation_entries"):
            panel.set_scanned_animation_entries(entries)
            panel.select_asset_type("Animation")
        self._finish_progress_toast("Animation library ready", f"{len(entries)} animation clips indexed.")
        self._log(f"Animation library scan complete: {len(entries)} clips", "success")
    def _activate_animation_entry_model(self, entry: dict) -> None:
        object_id = str(entry.get("object_id") or "")
        if object_id:
            obj = next((item for item in self.scene_manager.active_scene.objects if item.id == object_id), None)
            if obj is not None:
                self._activate_scene_object_model(obj)
                return
        resref = str(entry.get("resref") or "").strip()
        game = str(entry.get("game") or self._current_game or "K1").upper()
        if not resref:
            return
        mgr = self._get_resource_manager()
        if mgr is None:
            return
        model = mgr.load_model(resref, game)
        if model is None:
            return
        self._current_model = model
        if hasattr(self, "animations_panel"):
            self._load_animation_panel_model(model)
