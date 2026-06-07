"""Body Attachment System preview and recipe helpers."""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from types import MethodType

try:
    from PySide6 import QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.systems.bas.attachment_alignment import default_bas_attachment_transform
from src.systems.bas.head_resolution import normalize_bas_model_resref, resolve_bas_head_resref
from src.systems.bas.model_recipe import (
    BAS_SLOT_ORDER,
    BAS_SOCKET_BY_SLOT,
    build_bas_model_recipe,
    save_bas_model_recipe,
)

log = logging.getLogger(__name__)


class BasWorkflowMixin:
    """Body Attachment System preview and recipe helpers."""

    def _handle_bas_mode_changed(self, mode: str) -> None:
        mode_key = str(mode or "headless_body").strip().lower()
        if mode_key not in {"headless_body", "full_body"}:
            mode_key = "headless_body"
        self._bas_mode = mode_key
        if mode_key == "full_body" and "head" in getattr(self, "_bas_attachments", {}):
            self._bas_attachments.pop("head", None)
            self._bas_attachment_resrefs.pop("head", None)
            self._bas_attachment_transforms.pop("head", None)
            self._current_head_model = None
            if hasattr(self, "body_attachment_panel"):
                self.body_attachment_panel.clear_slot_model("head")
        result = self._rebuild_bas_preview()
        if hasattr(self, "body_attachment_panel"):
            self.body_attachment_panel.set_status(result or f"BAS mode: {mode_key.replace('_', ' ')}.")
    def _bas_mode_for_model(self, model) -> str:
        try:
            from src.core.geometry.model_data import CharacterMode, detect_character_mode

            return "headless_body" if detect_character_mode(model) == CharacterMode.HEADLESS_BODY else "full_body"
        except Exception:
            return "headless_body"
    def _handle_bas_attach_requested(self, slot: str, resref: str) -> None:
        slot = str(slot or "").strip().lower()
        resref = str(resref or "").strip()
        if slot == "body":
            self._show_workspace_dock("content_browser")
            return
        if slot in {"left_hand", "right_hand"}:
            if hasattr(self, "body_attachment_panel"):
                self.body_attachment_panel.set_status("Hand slots are sockets; attach items through L. Weapon or R. Weapon.")
            return
        if slot == "head" and getattr(self, "_bas_mode", "headless_body") == "full_body":
            if hasattr(self, "body_attachment_panel"):
                self.body_attachment_panel.set_status("Full Body BAS mode uses the existing head hooks; attach masks or goggles instead.")
            return
        body = getattr(self, "_bas_body_model", None) or getattr(self, "_current_model", None)
        if body is None:
            self.body_attachment_panel.set_status("No body model loaded.")
            return
        if not resref and slot != "head":
            self.body_attachment_panel.set_status("No attachment model selected.")
            return
        load_resref = normalize_bas_model_resref(resref)
        resolution = None
        if slot == "head":
            manager = self._get_resource_manager()
            game = (getattr(self, "_current_game", "") or self._infer_game_from_model(body) or "K1").upper()
            resolution = resolve_bas_head_resref(
                requested=resref,
                body_model=body,
                manager=manager,
                game=game,
            )
            load_resref = resolution.resolved_resref or load_resref
        if not load_resref:
            self.body_attachment_panel.set_status("No attachment model selected.")
            return
        model = self._load_bas_attachment_model(load_resref)
        if model is None:
            details = ""
            if resolution is not None and resolution.candidates:
                details = f" Tried: {', '.join(resolution.candidates)}."
            self.body_attachment_panel.set_status(f"Could not load {load_resref}.{details}")
            return
        previous_resref = str(self._bas_attachment_resrefs.get(slot, "") or "").strip().lower()
        self._bas_body_model = body
        self._bas_attachments[slot] = model
        self._bas_attachment_resrefs[slot] = load_resref
        if slot not in self._bas_attachment_transforms or previous_resref != load_resref.lower():
            self._bas_attachment_transforms[slot] = default_bas_attachment_transform(slot, load_resref)
        if slot == "head":
            self._current_head_model = model
        else:
            self._current_attachment_model = model
        result = self._rebuild_bas_preview()
        if result:
            self.body_attachment_panel.set_slot_model(slot, model, resref=load_resref)
            suffix = ""
            if resolution is not None and resolution.source and resolution.source != "requested":
                suffix = f" Head resolved from {resolution.source}: {load_resref}."
            self.body_attachment_panel.set_status(f"{result}{suffix}")
            self._refresh_bas_animation_panel_after_layer_change(slot)
    def _handle_bas_clear_requested(self, slot: str) -> None:
        slot = str(slot or "").strip().lower()
        if slot in {"body", "left_hand", "right_hand"}:
            return
        self._bas_attachments.pop(slot, None)
        self._bas_attachment_resrefs.pop(slot, None)
        self._bas_attachment_transforms.pop(slot, None)
        self.body_attachment_panel.clear_slot_model(slot)
        if slot == "head":
            self._current_head_model = None
        elif not any(key != "head" for key in self._bas_attachments):
            self._current_attachment_model = None
        result = self._rebuild_bas_preview()
        self.body_attachment_panel.set_status(result or f"Cleared {slot}.")
        self._refresh_bas_animation_panel_after_layer_change(slot)
    def _refresh_bas_animation_panel_after_layer_change(self, slot: str) -> None:
        if not hasattr(self, "animations_panel"):
            return
        selected = ""
        if hasattr(self.animations_panel, "selected_animation"):
            try:
                selected = str(self.animations_panel.selected_animation() or "")
            except Exception:
                selected = ""
        source = self._animation_source_key() if hasattr(self, "_animation_source_key") else "body"
        if source == "body":
            return
        if (source == "head" and slot == "head") or (source == "attachment" and slot != "head"):
            model = getattr(self, "_bas_body_model", None) or getattr(self, "_current_model", None)
            self._load_animation_panel_model(model, select_name=selected)
    def _load_bas_attachment_model(self, resref: str):
        resref = normalize_bas_model_resref(resref)
        if not resref:
            return None
        game = (getattr(self, "_current_game", "") or self._infer_game_from_model(self._bas_body_model or self._current_model) or "K1").upper()
        manager = self._get_resource_manager()
        if manager is None:
            return None
        try:
            return manager.load_model(resref, game)
        except Exception:
            log.debug("BAS attachment load failed for %s:%s", game, resref, exc_info=True)
            return None
    def _rebuild_bas_preview(self) -> str:
        body = getattr(self, "_bas_body_model", None) or getattr(self, "_current_model", None)
        if body is None:
            return "No body model loaded."
        try:
            previous_preview = getattr(self, "_bas_preview_model", None)
            preview = copy.deepcopy(body)
            self._reset_bas_model_node_traversal(preview)
            head = self._bas_attachments.get("head")
            if head is not None:
                if not self._attach_bas_item_to_preview(preview, head, "headhook", slot="head", transform=self._bas_attachment_transforms.get("head")):
                    return "Head attachment failed: body has no headhook socket."
            for slot in ("mask", "goggles", "left_weapon", "belt", "right_weapon"):
                item = self._bas_attachments.get(slot)
                if item is None:
                    continue
                socket_name = self._bas_socket_for_slot(slot)
                if not self._attach_bas_item_to_preview(
                    preview,
                    item,
                    socket_name,
                    slot=slot,
                    transform=self._bas_attachment_transforms.get(slot),
                ):
                    label = slot.replace("_", " ")
                    return f"{label.title()} attachment failed: model has no {socket_name} socket."
            preview.name = str(getattr(self, "_bas_active_build_name", "") or f"{getattr(body, 'name', 'body')}_bas")
            self._apply_bas_preview_to_viewport(preview, previous_preview=previous_preview)
            attached = ", ".join(self._bas_attachment_resrefs.get(key, key) for key in self._bas_attachments)
            return f"BAS preview updated: {attached or 'body only'}."
        except Exception as exc:
            log.exception("BAS preview rebuild failed")
            return f"BAS preview failed: {exc}"
    def _handle_bas_save_build_requested(self) -> None:
        body = getattr(self, "_bas_body_model", None) or getattr(self, "_current_model", None)
        if body is None:
            if hasattr(self, "body_attachment_panel"):
                self.body_attachment_panel.set_status("No body model loaded.")
            return
        default_name = str(getattr(self, "_bas_active_build_name", "") or f"{getattr(body, 'name', 'body')}_bas")
        name, accepted = QtWidgets.QInputDialog.getText(self, "Save BAS Build", "Model name", text=default_name)
        if not accepted:
            return
        build_name = str(name or "").strip()
        if not build_name:
            if hasattr(self, "body_attachment_panel"):
                self.body_attachment_panel.set_status("Save cancelled: model name is required.")
            return
        self._bas_active_build_name = build_name
        rebuild_status = self._rebuild_bas_preview()
        if str(rebuild_status or "").lower().startswith("bas preview failed"):
            if hasattr(self, "body_attachment_panel"):
                self.body_attachment_panel.set_status(rebuild_status)
            return
        path = self._save_bas_model_recipe(body, build_name=build_name)
        if hasattr(self, "body_attachment_panel"):
            if path is not None:
                self.body_attachment_panel.set_status(f"Saved BAS build: {path.name}")
            else:
                self.body_attachment_panel.set_status("Could not save BAS build.")
    def _save_bas_model_recipe(self, body, *, build_name: str = "") -> Path | None:
        try:
            game = (getattr(self, "_current_game", "") or self._infer_game_from_model(body) or "").upper()
            recipe = build_bas_model_recipe(
                body_model=body,
                attachment_models=dict(getattr(self, "_bas_attachments", {}) or {}),
                attachment_resrefs=dict(getattr(self, "_bas_attachment_resrefs", {}) or {}),
                attachment_transforms=dict(getattr(self, "_bas_attachment_transforms", {}) or {}),
                game=game,
                build_name=build_name or getattr(self, "_bas_active_build_name", ""),
                mode=getattr(self, "_bas_mode", "headless_body"),
            )
            path = save_bas_model_recipe(recipe, self.app_root / "src" / "systems" / "bas" / "models")
            self._last_bas_model_recipe_path = path
            log.info("Saved BAS model recipe: %s", path)
            return path
        except Exception:
            log.debug("Could not save BAS model recipe", exc_info=True)
            self._last_bas_model_recipe_path = None
            return None
    def _reset_bas_model_node_traversal(self, model) -> None:
        if model is None:
            return
        base_all_nodes = getattr(type(model), "all_nodes", None)
        if callable(base_all_nodes):
            try:
                setattr(model, "all_nodes", MethodType(base_all_nodes, model))
            except Exception:
                pass
        for attr in ("_gr_original_all_nodes", "_gr_generated_cameras", "_gr_generated_lights"):
            try:
                if hasattr(model, attr):
                    delattr(model, attr)
            except Exception:
                pass
    def _attach_bas_item_to_preview(self, preview, item, socket_name: str, slot: str = "", transform: dict | None = None) -> bool:
        socket = self._find_model_node(preview, socket_name)
        item_copy = copy.deepcopy(item)
        self._reset_bas_model_node_traversal(item_copy)
        item_root = getattr(item_copy, "root_node", None)
        if socket is None or item_root is None:
            return False
        try:
            setattr(item_root, "_gr_bas_attachment_source_model_id", id(item))
            setattr(item_root, "_gr_bas_attachment_source_model_name", str(getattr(item, "name", "") or ""))
            setattr(item_root, "_gr_bas_attachment_source_model_ref", item)
        except Exception:
            pass
        self._prepare_bas_layer_root(item_root, socket, slot or socket_name)
        if not transform:
            item_root.rotation = (0.0, 0.0, 0.0, 1.0)
        if transform:
            self._apply_bas_layer_transform(item_root, transform)
        if slot:
            try:
                self._bas_attachment_transforms[slot] = self._bas_layer_transform_from_model(item_copy)
            except Exception:
                pass
        item_root.parent = socket
        children = getattr(socket, "children", None)
        if children is None:
            socket.children = []
            children = socket.children
        children.append(item_root)
        return True
    def _bas_layer_transform_from_model(self, model) -> dict[str, list[float]]:
        root = getattr(model, "root_node", model)
        position = getattr(root, "position", (0.0, 0.0, 0.0))
        rotation = getattr(root, "rotation", (0.0, 0.0, 0.0, 1.0))
        scale = getattr(root, "scale", (1.0, 1.0, 1.0))
        try:
            scale_values = list(scale)[:3]
        except Exception:
            scale_values = [float(scale or 1.0)] * 3
        return {
            "position": [float(value) for value in list(position)[:3]],
            "rotation": [float(value) for value in list(rotation)[:4]],
            "scale": [float(value) for value in scale_values[:3]],
        }
    def _apply_bas_layer_transform(self, root, transform: dict) -> None:
        if root is None:
            return
        for attr, fallback, count in (
            ("position", (0.0, 0.0, 0.0), 3),
            ("rotation", (0.0, 0.0, 0.0, 1.0), 4),
            ("scale", (1.0, 1.0, 1.0), 3),
        ):
            values = transform.get(attr, fallback) if isinstance(transform, dict) else fallback
            try:
                coerced = [float(value) for value in list(values)[:count]]
            except Exception:
                coerced = []
            while len(coerced) < count:
                coerced.append(float(fallback[len(coerced)]))
            try:
                setattr(root, attr, tuple(coerced))
            except Exception:
                pass
    def _prepare_bas_layer_root(self, item_root, socket, slot: str) -> None:
        socket_name = str(getattr(socket, "name", "") or "").strip()
        if str(slot or "").lower() == "head":
            pos = tuple(float(v) for v in getattr(item_root, "position", (0.0, 0.0, 0.0))[:3])
            try:
                socket_world = socket.world_position()
            except Exception:
                socket_world = (0.0, 0.0, 0.0)
            if abs(float(pos[2]) + float(socket_world[2])) < 0.25 and abs(float(pos[2])) > 0.5:
                item_root.position = (pos[0], pos[1], 0.0)
        setattr(item_root, "_gr_bas_attachment_root", True)
        setattr(item_root, "_gr_bas_attachment_slot", str(slot or "attachment"))
        setattr(item_root, "_gr_bas_socket_name", socket_name)
        self._tag_bas_attachment_subtree(item_root, item_root)
    def _tag_bas_attachment_subtree(self, node, root) -> None:
        stack = [node]
        visited = set()
        while stack:
            current = stack.pop()
            if current is None or id(current) in visited:
                continue
            visited.add(id(current))
            setattr(current, "_gr_bas_attachment_layer", True)
            setattr(current, "_gr_bas_attachment_root_ref", root)
            try:
                setattr(current, "_gr_bas_attachment_source_model_id", int(getattr(root, "_gr_bas_attachment_source_model_id", 0) or 0))
                setattr(current, "_gr_bas_attachment_source_model_name", str(getattr(root, "_gr_bas_attachment_source_model_name", "") or ""))
            except Exception:
                pass
            stack.extend(getattr(current, "children", []) or [])
    def _find_model_node(self, model, name: str):
        target = str(name or "").lower()
        try:
            nodes = model.all_nodes()
        except Exception:
            nodes = []
        by_lower = {str(getattr(node, "name", "") or "").lower(): node for node in nodes}
        for candidate in (target, "rhand_g" if target == "rhand" else "", "lhand_g" if target == "lhand" else ""):
            if candidate and candidate in by_lower:
                return by_lower[candidate]
        return None
    def _bas_socket_for_slot(self, slot: str) -> str:
        slot_key = str(slot or "").strip().lower()
        return BAS_SOCKET_BY_SLOT.get(slot_key, "lhand" if slot_key.startswith("left") else "rhand")
    def _bas_target_scene_object(self, previous_preview=None):
        scene_manager = getattr(self, "scene_manager", None)
        scene = getattr(scene_manager, "active_scene", None)
        if scene is None:
            return None
        body = getattr(self, "_bas_body_model", None) or getattr(self, "_current_model", None)
        current_preview = getattr(self, "_bas_preview_model", None)
        candidate_models = [model for model in (body, getattr(self, "_current_model", None), previous_preview, current_preview) if model is not None]
        body_marker = str(id(body)) if body is not None else ""

        for obj in getattr(scene, "objects", []) or []:
            metadata = getattr(obj, "metadata", {}) or {}
            if body_marker and str(metadata.get("_runtime_bas_body_model_id") or "") == body_marker:
                return obj

        selected = scene_manager.get_selected_objects() if hasattr(scene_manager, "get_selected_objects") else []
        for obj in selected:
            runtime = (getattr(obj, "metadata", {}) or {}).get("_runtime_model")
            if any(runtime is model for model in candidate_models):
                return obj

        for obj in getattr(scene, "objects", []) or []:
            runtime = (getattr(obj, "metadata", {}) or {}).get("_runtime_model")
            if any(runtime is model for model in candidate_models):
                return obj
        return None
    def _apply_bas_preview_to_viewport(self, preview, previous_preview=None) -> None:
        target_object = None
        if hasattr(self, "scene_manager"):
            target_object = self._bas_target_scene_object(previous_preview=previous_preview)
        if target_object is not None:
            target_object.metadata["_runtime_model"] = preview
            target_object.metadata["_runtime_bas_body_model"] = getattr(self, "_bas_body_model", None) or getattr(self, "_current_model", None)
            target_object.metadata["_runtime_bas_body_model_id"] = str(
                id(getattr(self, "_bas_body_model", None) or getattr(self, "_current_model", None))
            )
            target_object.metadata["_runtime_bas_preview_model"] = preview
            target_object.metadata.setdefault("body_attachment_system", {})
            target_object.metadata["body_attachment_system"].update({
                "active": True,
                "mode": getattr(self, "_bas_mode", "headless_body"),
                "attachments": dict(self._bas_attachment_resrefs),
                "layers": [
                    {
                        "slot": slot,
                        "resref": self._bas_attachment_resrefs.get(slot, ""),
                        "enabled": True,
                    }
                    for slot in BAS_SLOT_ORDER
                    if slot in self._bas_attachments
                ],
            })
            self._bas_preview_model = preview
            self.scene_manager.mark_dirty()
            self._refresh_scene_view()
        elif hasattr(self, "viewport"):
            self._bas_preview_model = preview
            self.viewport.load_model(preview)
        else:
            self._bas_preview_model = preview
        self._sync_bas_body_animation_engine()
        self._restore_bas_animation_pose_after_viewport_refresh()
        self._request_bas_viewport_refresh()
        if hasattr(self, "skeleton_panel"):
            self.skeleton_panel.load_model(preview)
        if hasattr(self, "module_geometry_panel"):
            self.module_geometry_panel.show_model(preview)
        if hasattr(self, "sprite_materials_panel"):
            self.sprite_materials_panel.set_model(preview)
    def _sync_bas_body_animation_engine(self, preview=None) -> None:
        try:
            source_key = self._animation_source_key() if hasattr(self, "_animation_source_key") else "body"
        except Exception:
            source_key = "body"
        if source_key != "body":
            return
        body = getattr(self, "_bas_body_model", None) or getattr(self, "_current_model", None)
        if body is None:
            return
        engine = getattr(self, "_animation_engine", None)
        current = getattr(engine, "current_animation", None) if engine is not None else None
        if engine is None or current is None or not hasattr(engine, "model") or getattr(engine, "model", None) is body:
            return
        anim_name = str(getattr(current, "name", "") or "")
        if not anim_name:
            return
        try:
            from src.core.animation.animation_engine import AnimationEngine, SuperModelResolver

            mgr = self._get_resource_manager()
            if mgr is not None:
                SuperModelResolver.configure(mgr)
            t = float(getattr(engine, "current_time", 0.0) or 0.0)
            was_playing = bool(getattr(engine, "is_playing", False))
            loop = bool(getattr(engine, "_loop", getattr(self, "_animation_loop", False)))
            inheritance_game = self._animation_inheritance_game(body)
            inheritance_supermodel = self._animation_inheritance_supermodel(body)
            with self._animation_resolution_context(body, inheritance_game, inheritance_supermodel):
                replacement = AnimationEngine(body)
                if not replacement.play(anim_name, loop=loop, blend=False):
                    return
                replacement.seek(t)
                if not was_playing:
                    replacement.stop()
            self._animation_engine = replacement
        except Exception:
            log.debug("Could not restore BAS animation engine to body model", exc_info=True)
    def _restore_bas_animation_pose_after_viewport_refresh(self) -> None:
        engine = getattr(self, "_animation_engine", None)
        current = getattr(engine, "current_animation", None) if engine is not None else None
        if engine is None or current is None or not hasattr(self, "viewport"):
            return
        try:
            t = float(getattr(engine, "current_time", 0.0) or 0.0)
            pose = engine.evaluate(t)
            if hasattr(self, "_tag_animation_pose_source"):
                pose = self._tag_animation_pose_source(pose, getattr(engine, "model", None))
            self.viewport.set_animation_pose(
                pose,
                name=str(getattr(current, "name", "") or ""),
                time=t,
                length=float(getattr(current, "length", 0.0) or 0.0),
            )
            if hasattr(self.viewport, "set_animation_playback_active"):
                self.viewport.set_animation_playback_active(bool(getattr(engine, "is_playing", False)))
        except Exception:
            log.debug("Could not restore BAS animation pose after viewport refresh", exc_info=True)
    def _request_bas_viewport_refresh(self) -> None:
        viewport = getattr(self, "viewport", None)
        if viewport is None:
            return
        try:
            if hasattr(viewport, "refresh_view"):
                viewport.refresh_view()
            elif hasattr(viewport, "_request_render"):
                viewport._request_render(fast=True, reason="body attachment updated", scene=True, overlay=True, hud=True)
        except Exception:
            log.debug("Could not request BAS viewport refresh", exc_info=True)
