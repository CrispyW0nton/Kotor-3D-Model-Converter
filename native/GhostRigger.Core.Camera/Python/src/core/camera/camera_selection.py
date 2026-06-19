"""Selection state for editable cameras."""

from __future__ import annotations


class CameraSelection:
    def __init__(self) -> None:
        self.selected_ids: list[str] = []
        self.active_id: str = ""

    def clear(self) -> None:
        self.selected_ids = []
        self.active_id = ""

    def set_single(self, camera_id: str) -> None:
        self.selected_ids = [camera_id] if camera_id else []
        self.active_id = camera_id if camera_id else ""

    def set_many(self, camera_ids, *, active_id: str = "") -> None:
        clean: list[str] = []
        seen: set[str] = set()
        for camera_id in camera_ids or []:
            value = str(camera_id or "")
            if value and value not in seen:
                clean.append(value)
                seen.add(value)
        self.selected_ids = clean
        self.active_id = active_id if active_id in seen else (clean[-1] if clean else "")

    def toggle(self, camera_id: str) -> None:
        camera_id = str(camera_id or "")
        if not camera_id:
            return
        if camera_id in self.selected_ids:
            self.selected_ids = [item for item in self.selected_ids if item != camera_id]
            if self.active_id == camera_id:
                self.active_id = self.selected_ids[-1] if self.selected_ids else ""
            return
        self.selected_ids.append(camera_id)
        self.active_id = camera_id
