"""Light grouping model and operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class LightGroup:
    id: str = field(default_factory=lambda: f"group-{uuid4().hex}")
    name: str = "Light Group"
    enabled: bool = True
    visible: bool = True
    locked: bool = False
    color: tuple[float, float, float] = (0.4, 0.8, 0.6)
    member_light_ids: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class LightGrouping:
    def __init__(self) -> None:
        self.groups: dict[str, LightGroup] = {}

    def create_group(self, light_ids: list[str], name: str | None = None) -> LightGroup:
        group = LightGroup(name=name or f"Group {len(self.groups) + 1}")
        group.member_light_ids = list(dict.fromkeys(light_ids))
        self.groups[group.id] = group
        return group

    def ungroup(self, light_ids: list[str]) -> None:
        ids = set(light_ids)
        for group in self.groups.values():
            group.member_light_ids = [light_id for light_id in group.member_light_ids if light_id not in ids]

    def group_for(self, light_id: str) -> LightGroup | None:
        for group in self.groups.values():
            if light_id in group.member_light_ids:
                return group
        return None
