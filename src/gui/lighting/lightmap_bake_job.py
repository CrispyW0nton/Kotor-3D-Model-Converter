"""Lightmap bake job and result records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

from .lightmap_bake_settings import LightmapBakeSettings


ProgressCallback = Callable[[str, int, int, str], None]
CancelCallback = Callable[[], bool]


@dataclass
class LightmapBakeJob:
    model: object
    lights: Sequence[object] = field(default_factory=list)
    settings: LightmapBakeSettings = field(default_factory=LightmapBakeSettings)
    module_name: str = ""
    selected_meshes: Sequence[object] = field(default_factory=list)
    visible_meshes: Sequence[object] = field(default_factory=list)
    texture_cache: object | None = None
    progress: ProgressCallback | None = None
    should_cancel: CancelCallback | None = None

    def cancelled(self) -> bool:
        return bool(self.should_cancel and self.should_cancel())


@dataclass
class LightmapMeshBake:
    mesh_name: str
    material_name: str
    uv_channel: int
    output_path: str
    preview_name: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class LightmapBakeResult:
    module_name: str
    resolution: int
    output_format: str
    bakes: list[LightmapMeshBake] = field(default_factory=list)
    manifest_path: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    cancelled: bool = False

    @property
    def ok(self) -> bool:
        return not self.cancelled and not self.errors and bool(self.bakes)

    def preview_assignments(self) -> dict[str, str]:
        return {entry.mesh_name: entry.output_path for entry in self.bakes if entry.output_path}


@dataclass
class BakeableMesh:
    node: object
    name: str
    material_name: str
    uv_channel: int
    warnings: list[str] = field(default_factory=list)


def ordered_unique(items: Iterable[object]) -> list[object]:
    seen: set[int] = set()
    result: list[object] = []
    for item in items:
        key = id(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
