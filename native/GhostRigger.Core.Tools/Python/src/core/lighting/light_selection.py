"""Selection state for single and multi-light editing."""

from __future__ import annotations


class LightSelection:
    def __init__(self) -> None:
        self.selected_ids: list[str] = []
        self.active_id: str = ""

    def clear(self) -> None:
        self.selected_ids.clear()
        self.active_id = ""

    def set_single(self, light_id: str) -> None:
        self.selected_ids = [light_id] if light_id else []
        self.active_id = light_id or ""

    def set_many(self, light_ids: list[str], *, active_id: str = "") -> None:
        seen: set[str] = set()
        self.selected_ids = []
        for light_id in light_ids:
            if light_id and light_id not in seen:
                self.selected_ids.append(light_id)
                seen.add(light_id)
        self.active_id = active_id or (self.selected_ids[-1] if self.selected_ids else "")

    def toggle(self, light_id: str) -> None:
        if not light_id:
            return
        if light_id in self.selected_ids:
            self.selected_ids = [item for item in self.selected_ids if item != light_id]
            if self.active_id == light_id:
                self.active_id = self.selected_ids[-1] if self.selected_ids else ""
        else:
            self.selected_ids.append(light_id)
            self.active_id = light_id
