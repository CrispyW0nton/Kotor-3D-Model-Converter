"""Headless state container for the Map Studio Level Editor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.level import KMapProject, LevelScene, new_kmap_project


@dataclass
class ModuleEditorMessage:
    severity: str
    text: str
    code: str = ""


@dataclass(frozen=True)
class MapStudioWorkspaceMode:
    """One modder-facing workspace inside the Map Studio Level Editor."""

    key: str
    label: str
    summary: str
    next_action: str


@dataclass
class ModuleEditorModel:
    project: KMapProject = field(default_factory=new_kmap_project)
    selected_ids: list[str] = field(default_factory=list)
    active_module_id: str = ""
    active_room_id: str = ""
    loaded_modules: dict[str, Any] = field(default_factory=dict)
    loaded_walkmeshes: dict[str, Any] = field(default_factory=dict)
    messages: list[ModuleEditorMessage] = field(default_factory=list)

    @property
    def scene(self) -> LevelScene:
        return LevelScene(self.project, selection=list(self.selected_ids))

    def set_project(self, project: KMapProject) -> None:
        self.project = project
        self.selected_ids.clear()
        self.active_module_id = ""
        self.active_room_id = ""
        self.messages.clear()

    def select(self, item_id: str) -> None:
        self.selected_ids = [item_id] if item_id else []
        if self.project.find_room(item_id):
            self.active_room_id = item_id
        if self.project.find_module(item_id):
            self.active_module_id = item_id

    def select_many(self, item_ids: list[str] | tuple[str, ...]) -> None:
        """Replace the scene selection while preserving the user's order."""

        seen: set[str] = set()
        self.selected_ids = []
        for value in item_ids:
            item_id = str(value or "").strip()
            if not item_id or item_id in seen:
                continue
            seen.add(item_id)
            self.selected_ids.append(item_id)
        if self.selected_ids:
            active = self.selected_ids[-1]
            if self.project.find_room(active):
                self.active_room_id = active
            if self.project.find_module(active):
                self.active_module_id = active

    def toggle_selection(self, item_id: str) -> None:
        """Maya-style Shift toggle for one object in the current selection."""

        value = str(item_id or "").strip()
        if not value:
            return
        selected = list(self.selected_ids)
        if value in selected:
            selected.remove(value)
        else:
            selected.append(value)
        self.select_many(selected)

    def log(self, text: str, severity: str = "Info", code: str = "") -> None:
        self.messages.append(ModuleEditorMessage(severity=severity, text=text, code=code))
