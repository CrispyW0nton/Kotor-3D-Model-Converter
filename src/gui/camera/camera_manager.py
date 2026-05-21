"""Coordinator for editable scene cameras."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Iterable

from .camera_model import GhostRiggerCamera
from .camera_selection import CameraSelection


class CameraManager:
    def __init__(self) -> None:
        self.model: object | None = None
        self.cameras: list[GhostRiggerCamera] = []
        self.selection = CameraSelection()
        self.active_camera_id: str = ""

    def set_model(self, model: object | None) -> None:
        self.model = model
        self.deserialize(getattr(model, "_gr_camera_state", None) if model is not None else None)
        if not self.cameras and model is not None:
            self.cameras = self._discover_cameras(model)
        self.selection.clear()
        self._sync_selection_flags()
        self._store_on_model()

    def create_camera(self, name: str | None = None, camera_type: str = "Cinematic Camera") -> GhostRiggerCamera:
        camera = GhostRiggerCamera(name=name or self._next_name(), camera_type=camera_type)
        if camera_type == "Target Camera":
            camera.target_enabled = True
        return self.add_camera(camera)

    def add_camera(self, camera: GhostRiggerCamera) -> GhostRiggerCamera:
        if camera.original_ref is None:
            camera.original_ref = self._make_camera_node(camera)
        camera.apply_to_original()
        self.cameras.append(camera)
        self._sync_generated_nodes()
        self._store_on_model()
        return camera

    def delete_camera(self, camera_id: str) -> bool:
        camera = self.get_camera(camera_id)
        if camera is None:
            return False
        camera.deleted = True
        camera.enabled = False
        camera.visible = False
        camera.selected = False
        camera.apply_to_original()
        if self.active_camera_id == camera.id:
            self.clear_active_camera()
        self.cameras = [item for item in self.cameras if item.id != camera.id]
        self.selection.selected_ids = [item for item in self.selection.selected_ids if item != camera.id]
        if self.selection.active_id == camera.id:
            self.selection.active_id = self.selection.selected_ids[-1] if self.selection.selected_ids else ""
        self._sync_generated_nodes()
        self._store_on_model()
        return True

    def delete_selected(self) -> list[str]:
        ids = list(self.selection.selected_ids)
        deleted: list[str] = []
        for camera_id in ids:
            if self.delete_camera(camera_id):
                deleted.append(camera_id)
        self.clear_camera_selection()
        return deleted

    def duplicate_camera(self, camera_id: str) -> GhostRiggerCamera | None:
        source = self.get_camera(camera_id)
        if source is None:
            return None
        dup = source.copy_generated(name=self._next_name(source.name))
        self.add_camera(dup)
        self.select_camera(dup.id)
        return dup

    def rename_camera(self, camera_id: str, new_name: str) -> bool:
        camera = self.get_camera(camera_id)
        name = str(new_name or "").strip()
        if camera is None or not name:
            return False
        camera.name = name
        camera.apply_to_original()
        self._store_on_model()
        return True

    def get_camera(self, camera_id: str) -> GhostRiggerCamera | None:
        return next((camera for camera in self.cameras if camera.id == camera_id and not camera.deleted), None)

    def find_by_name(self, name: str) -> GhostRiggerCamera | None:
        needle = str(name or "").strip().lower()
        return next((camera for camera in self.cameras if camera.name.lower() == needle and not camera.deleted), None)

    def find_by_original(self, obj: object | None) -> GhostRiggerCamera | None:
        if obj is None:
            return None
        return next((camera for camera in self.cameras if camera.original_ref is obj and not camera.deleted), None)

    def get_all_cameras(self) -> list[GhostRiggerCamera]:
        return [camera for camera in self.cameras if not camera.deleted]

    def set_active_camera(self, camera_id: str) -> GhostRiggerCamera | None:
        camera = self.get_camera(camera_id)
        if camera is None:
            self.clear_active_camera()
            return None
        self.active_camera_id = camera.id
        self._store_on_model()
        return camera

    def clear_active_camera(self) -> None:
        self.active_camera_id = ""
        self._store_on_model()

    def get_active_camera(self) -> GhostRiggerCamera | None:
        return self.get_camera(self.active_camera_id)

    def select_camera(self, camera_id: str, additive: bool = False) -> GhostRiggerCamera | None:
        camera = self.get_camera(camera_id)
        if camera is None:
            if not additive:
                self.clear_camera_selection()
            return None
        if additive:
            self.selection.toggle(camera.id)
        else:
            self.selection.set_single(camera.id)
        self._sync_selection_flags()
        self._store_on_model()
        return camera

    def select_many(self, cameras: Iterable[GhostRiggerCamera], *, active: GhostRiggerCamera | None = None) -> None:
        clean = [camera for camera in cameras if camera is not None]
        self.selection.set_many([camera.id for camera in clean], active_id=active.id if active else "")
        self._sync_selection_flags()
        self._store_on_model()

    def clear_camera_selection(self) -> None:
        self.selection.clear()
        self._sync_selection_flags()
        self._store_on_model()

    def selected_cameras(self) -> list[GhostRiggerCamera]:
        by_id = {camera.id: camera for camera in self.get_all_cameras()}
        return [by_id[camera_id] for camera_id in self.selection.selected_ids if camera_id in by_id]

    def serialize(self) -> dict:
        return {
            "version": 1,
            "active_camera_id": self.active_camera_id if self.get_camera(self.active_camera_id) else "",
            "cameras": [camera.serialize() for camera in self.get_all_cameras()],
        }

    def deserialize(self, data) -> None:
        payload = dict(data or {})
        self.cameras = []
        for entry in payload.get("cameras", []) or []:
            try:
                camera = GhostRiggerCamera.from_dict(entry)
            except Exception:
                continue
            camera.original_ref = self._find_existing_node(camera.id) if self.model is not None else None
            if camera.original_ref is None and self.model is not None:
                camera.original_ref = self._make_camera_node(camera)
            camera.apply_to_original()
            self.cameras.append(camera)
        active = str(payload.get("active_camera_id", "") or "")
        self.active_camera_id = active if any(camera.id == active for camera in self.cameras) else ""
        self._sync_generated_nodes()

    def _sync_selection_flags(self) -> None:
        selected = set(self.selection.selected_ids)
        active = self.selection.active_id
        for camera in self.cameras:
            camera.selected = camera.id in selected
            camera.metadata["active_selection"] = camera.id == active
            camera.apply_to_original()

    def _store_on_model(self) -> None:
        if self.model is None:
            return
        try:
            setattr(self.model, "_gr_camera_state", self.serialize())
        except Exception:
            pass

    def _discover_cameras(self, model: object) -> list[GhostRiggerCamera]:
        try:
            nodes = model.all_nodes() if hasattr(model, "all_nodes") else []
        except Exception:
            nodes = []
        cameras: list[GhostRiggerCamera] = []
        for node in nodes:
            if bool(getattr(node, "is_camera", False)) or bool(getattr(node, "_gr_camera_id", "")):
                camera = GhostRiggerCamera.from_object(node)
                cameras.append(camera)
        return cameras

    def _find_existing_node(self, camera_id: str):
        if self.model is None:
            return None
        try:
            nodes = self.model.all_nodes() if hasattr(self.model, "all_nodes") else []
        except Exception:
            nodes = []
        return next((node for node in nodes if str(getattr(node, "_gr_camera_id", "") or "") == camera_id), None)

    def _make_camera_node(self, camera: GhostRiggerCamera) -> object:
        node = SimpleNamespace(
            name=camera.name,
            is_camera=True,
            position=tuple(camera.position),
            rotation=tuple(camera.rotation),
            children=[],
        )
        if self.model is not None:
            existing = list(getattr(self.model, "_gr_generated_cameras", []) or [])
            existing.append(node)
            try:
                setattr(self.model, "_gr_generated_cameras", existing)
                self._install_all_nodes_wrapper()
            except Exception:
                pass
        return node

    def _sync_generated_nodes(self) -> None:
        if self.model is None:
            return
        nodes = [camera.original_ref for camera in self.cameras if camera.original_ref is not None and not camera.deleted]
        try:
            setattr(self.model, "_gr_generated_cameras", nodes)
            self._install_all_nodes_wrapper()
        except Exception:
            pass

    def _install_all_nodes_wrapper(self) -> None:
        model = self.model
        if model is None or not hasattr(model, "all_nodes"):
            return
        if not hasattr(model, "_gr_original_all_nodes"):
            setattr(model, "_gr_original_all_nodes", getattr(model, "all_nodes"))

        def _all_nodes_with_generated(_model=model):
            base = list(_model._gr_original_all_nodes())
            lights = list(getattr(_model, "_gr_generated_lights", []) or [])
            cameras = list(getattr(_model, "_gr_generated_cameras", []) or [])
            extras = [node for node in lights + cameras if node not in base]
            return base + extras

        setattr(model, "all_nodes", _all_nodes_with_generated)

    def _next_name(self, base: str = "Camera") -> str:
        prefix = str(base or "Camera").strip()
        if prefix.lower().endswith(" copy"):
            prefix = prefix[:-5]
        existing = {camera.name for camera in self.get_all_cameras()}
        if prefix == "Camera":
            for index in range(1, 10000):
                candidate = f"Camera{index:03d}"
                if candidate not in existing:
                    return candidate
        for index in range(1, 10000):
            candidate = f"{prefix} Copy" if index == 1 else f"{prefix} Copy {index}"
            if candidate not in existing:
                return candidate
        return f"{prefix} Copy"
