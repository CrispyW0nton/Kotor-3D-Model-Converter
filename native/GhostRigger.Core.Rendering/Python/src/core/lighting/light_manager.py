"""Coordinator for editable lights, groups, generated rigs, and source sync."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Iterable

from src.core.lighting.aurora_light_adapter import AuroraLightAdapter
from src.core.lighting.light_grouping import LightGroup, LightGrouping
from src.core.lighting.light_model import GhostRiggerLight, _quat, _vec3
from src.core.lighting.light_selection import LightSelection


class LightManager:
    def __init__(self, adapter: AuroraLightAdapter | None = None) -> None:
        self.adapter = adapter or AuroraLightAdapter()
        self.model: object | None = None
        self.lights: list[GhostRiggerLight] = []
        self.selection = LightSelection()
        self.grouping = LightGrouping()

    def set_model(self, model: object | None) -> None:
        self.model = model
        self.lights = self.adapter.from_model(model)
        self.selection.clear()
        self._sync_selection_flags()

    def all_lights(self, *, include_deleted: bool = False) -> list[GhostRiggerLight]:
        return [light for light in self.lights if include_deleted or not light.deleted]

    def get(self, light_id: str) -> GhostRiggerLight | None:
        return next((light for light in self.lights if light.id == light_id), None)

    def find_by_original(self, obj: object | None) -> GhostRiggerLight | None:
        if obj is None:
            return None
        return next((light for light in self.lights if light.original_ref is obj), None)

    def selected_lights(self) -> list[GhostRiggerLight]:
        by_id = {light.id: light for light in self.lights}
        return [by_id[light_id] for light_id in self.selection.selected_ids if light_id in by_id]

    def active_light(self) -> GhostRiggerLight | None:
        return self.get(self.selection.active_id)

    def select_single(self, light_or_ref: GhostRiggerLight | object | None) -> None:
        light = light_or_ref if isinstance(light_or_ref, GhostRiggerLight) else self.find_by_original(light_or_ref)
        self.selection.set_single(light.id if light is not None else "")
        self._sync_selection_flags()

    def select_many(self, lights: Iterable[GhostRiggerLight], *, active: GhostRiggerLight | None = None) -> None:
        ids = [light.id for light in lights]
        self.selection.set_many(ids, active_id=(active.id if active else ""))
        self._sync_selection_flags()

    def apply_to_selected(self, **changes: Any) -> None:
        for light in self.selected_lights():
            if light.locked:
                continue
            self._sync_live_transform(light, changes)
            for key, value in changes.items():
                if hasattr(light, key):
                    setattr(light, key, value)
            light.apply_to_original()

    def apply_to_light(self, light: GhostRiggerLight, **changes: Any) -> None:
        if light.locked:
            return
        self._sync_live_transform(light, changes)
        for key, value in changes.items():
            if hasattr(light, key):
                setattr(light, key, value)
        light.apply_to_original()

    def _sync_live_transform(self, light: GhostRiggerLight, changes: dict[str, Any]) -> None:
        obj = light.original_ref
        if obj is None:
            return
        if "position" not in changes:
            light.position = _vec3(getattr(obj, "position", light.position), light.position)
        if "rotation" not in changes:
            light.rotation = _quat(getattr(obj, "rotation", light.rotation), light.rotation)

    def group_selected(self, name: str | None = None) -> LightGroup | None:
        ids = list(self.selection.selected_ids)
        if not ids:
            return None
        group = self.grouping.create_group(ids, name)
        for light in self.selected_lights():
            light.group_id = group.id
            light.apply_to_original()
        return group

    def ungroup_selected(self) -> None:
        ids = list(self.selection.selected_ids)
        self.grouping.ungroup(ids)
        for light in self.selected_lights():
            light.group_id = ""
            light.apply_to_original()

    def set_group_state(self, group_id: str, *, enabled: bool | None = None, visible: bool | None = None, locked: bool | None = None) -> None:
        group = self.grouping.groups.get(group_id)
        if group is None:
            return
        if enabled is not None:
            group.enabled = bool(enabled)
        if visible is not None:
            group.visible = bool(visible)
        if locked is not None:
            group.locked = bool(locked)
        members = [light for light in self.lights if light.id in group.member_light_ids]
        for light in members:
            if enabled is not None:
                light.enabled = bool(enabled)
            if visible is not None:
                light.visible = bool(visible)
            if locked is not None:
                light.locked = bool(locked)
            light.apply_to_original()

    def add_light(self, light: GhostRiggerLight) -> GhostRiggerLight:
        if light.original_ref is None:
            light.original_ref = self._make_light_node(light)
        light.apply_to_original()
        self.lights.append(light)
        return light

    def duplicate_selected(self) -> list[GhostRiggerLight]:
        created: list[GhostRiggerLight] = []
        for source in self.selected_lights():
            dup = source.copy_generated(name=f"{source.name} Copy")
            dup.position = (source.position[0] + 0.35, source.position[1] + 0.35, source.position[2])
            created.append(self.add_light(dup))
        return created

    def soft_delete_selected(self) -> None:
        for light in self.selected_lights():
            light.deleted = True
            light.enabled = False
            light.visible = False
            light.apply_to_original()
        self.selection.clear()
        self._sync_selection_flags()

    def remove_generated_rig(self) -> None:
        keep: list[GhostRiggerLight] = []
        for light in self.lights:
            if light.source_type == "GeneratedRig":
                light.deleted = True
                light.enabled = False
                light.visible = False
                light.apply_to_original()
            else:
                keep.append(light)
        self.lights = keep
        self.selection.clear()
        self._sync_selection_flags()

    def _sync_selection_flags(self) -> None:
        selected = set(self.selection.selected_ids)
        active = self.selection.active_id
        for light in self.lights:
            light.selected = light.id in selected
            light.metadata["active_selection"] = light.id == active
            light.apply_to_original()

    def _make_light_node(self, light: GhostRiggerLight) -> object:
        node = SimpleNamespace(
            name=light.name,
            is_light=True,
            is_mesh=False,
            type_label="light",
            position=light.position,
            rotation=light.rotation,
            children=[],
        )
        existing = []
        if self.model is not None and hasattr(self.model, "_gr_generated_lights"):
            existing = list(getattr(self.model, "_gr_generated_lights", []) or [])
        existing.append(node)
        try:
            setattr(self.model, "_gr_generated_lights", existing)
            if hasattr(self.model, "all_nodes"):
                original_all_nodes = getattr(self.model, "all_nodes")
                if not hasattr(self.model, "_gr_original_all_nodes"):
                    setattr(self.model, "_gr_original_all_nodes", original_all_nodes)

                    def _all_nodes_with_generated(_orig=original_all_nodes, _model=self.model):
                        return list(_orig()) + list(getattr(_model, "_gr_generated_lights", []) or [])

                    setattr(self.model, "all_nodes", _all_nodes_with_generated)
        except Exception:
            pass
        return node
