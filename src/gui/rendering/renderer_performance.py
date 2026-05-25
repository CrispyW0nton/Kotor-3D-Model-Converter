"""Renderer performance helpers shared by tests and WGPU diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Iterable, Sequence


@dataclass(frozen=True)
class ResourceCacheKey:
    """Stable renderer-cache key that carries source revision information."""

    kind: str
    identifier: object
    revision: tuple = field(default_factory=tuple)
    variant: tuple = field(default_factory=tuple)


@dataclass(frozen=True)
class RenderBatchKey:
    pipeline_key: str
    material_key: str
    texture_key: str
    alpha_mode: str
    culling_mode: str
    category: str
    skinned: bool = False


@dataclass
class RenderBatch:
    key: RenderBatchKey
    items: list = field(default_factory=list)

    @property
    def draw_count(self) -> int:
        return len(self.items)

    @property
    def visible_count(self) -> int:
        return len(self.items)


@dataclass
class TextureResidencyInfo:
    texture_id: str
    width: int
    height: int
    format: str
    byte_size: int
    resident: bool = False
    lightmap: bool = False
    alpha: bool = False

    @property
    def array_group_key(self) -> tuple[int, int, str, bool]:
        return (int(self.width), int(self.height), str(self.format), bool(self.lightmap))

    @property
    def array_eligible(self) -> bool:
        return self.width > 0 and self.height > 0 and self.format in {"rgba8unorm", "rgba8unorm-srgb"}


class LazyUploadQueue:
    """Small priority queue for staged renderer-resource uploads."""

    def __init__(self) -> None:
        self._items: list[tuple[int, int, object]] = []
        self._serial = 0

    def push(self, item: object, *, visible: bool = False, selected: bool = False) -> None:
        priority = 0 if selected else 1 if visible else 2
        self._items.append((priority, self._serial, item))
        self._serial += 1

    def pop_many(self, limit: int) -> list[object]:
        if limit <= 0 or not self._items:
            return []
        self._items.sort(key=lambda row: (row[0], row[1]))
        selected = self._items[:limit]
        self._items = self._items[limit:]
        return [item for _priority, _serial, item in selected]

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)


def material_texture_key(material_data) -> str:
    diffuse = str(getattr(material_data, "diffuse_texture_id", "") or getattr(material_data, "diffuse_texture_path", "") or "")
    lightmap = str(getattr(material_data, "lightmap_texture_id", "") or getattr(material_data, "lightmap_texture_path", "") or "")
    return f"{diffuse}|{lightmap}"


def batch_key_for_mesh(mesh_data, material_data, *, pipeline_key: str, category: str, culling_mode: str = "default") -> RenderBatchKey:
    material_key = str(getattr(material_data, "material_id", "") or id(material_data))
    alpha_mode = str(getattr(material_data, "alpha_mode", "OPAQUE") or "OPAQUE").upper()
    return RenderBatchKey(
        pipeline_key=str(pipeline_key),
        material_key=material_key,
        texture_key=material_texture_key(material_data),
        alpha_mode=alpha_mode,
        culling_mode=str(culling_mode),
        category=str(category),
        skinned=bool(getattr(mesh_data, "is_skinned", False)),
    )


def group_render_batches(items: Iterable[tuple], *, pipeline_key: str, category: str) -> list[RenderBatch]:
    batches: dict[RenderBatchKey, RenderBatch] = {}
    order: list[RenderBatchKey] = []
    for item in items:
        mesh_data = item[2] if len(item) >= 4 else item[0]
        material_data = item[3] if len(item) >= 4 else getattr(mesh_data, "material", None)
        if material_data is None:
            continue
        key = batch_key_for_mesh(mesh_data, material_data, pipeline_key=pipeline_key, category=category)
        batch = batches.get(key)
        if batch is None:
            batch = RenderBatch(key)
            batches[key] = batch
            order.append(key)
        batch.items.append(item)
    return [batches[key] for key in order]


def instancing_summary(items: Iterable[tuple]) -> dict[str, int]:
    groups: dict[tuple, int] = {}
    for item in items:
        mesh_data = item[2] if len(item) >= 4 else item[0]
        material_data = item[3] if len(item) >= 4 else getattr(mesh_data, "material", None)
        positions = getattr(mesh_data, "positions", ())
        indices = getattr(mesh_data, "indices", ())
        geometry_key = (
            tuple(getattr(mesh_data, "source_revision", ()) or ()),
            _array_len(positions),
            _array_len(indices),
            str(getattr(material_data, "material_id", "") or ""),
        )
        groups[geometry_key] = groups.get(geometry_key, 0) + 1
    repeated = [count for count in groups.values() if count > 1]
    return {
        "instance_group_count": len(repeated),
        "instance_count": sum(repeated),
    }


def extract_frustum_planes(mvp: Sequence[Sequence[float]]) -> tuple[tuple[float, float, float, float], ...]:
    rows = [[float(v) for v in row[:4]] for row in mvp[:4]]
    planes = (
        _normalize_plane(_row_add(rows[3], rows[0])),
        _normalize_plane(_row_sub(rows[3], rows[0])),
        _normalize_plane(_row_add(rows[3], rows[1])),
        _normalize_plane(_row_sub(rows[3], rows[1])),
        _normalize_plane(_row_add(rows[3], rows[2])),
        _normalize_plane(_row_sub(rows[3], rows[2])),
    )
    return planes


def bounds_intersects_frustum(
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]],
    planes: Sequence[tuple[float, float, float, float]],
) -> bool:
    mins, maxs = bounds
    for a, b, c, d in planes:
        px = maxs[0] if a >= 0 else mins[0]
        py = maxs[1] if b >= 0 else mins[1]
        pz = maxs[2] if c >= 0 else mins[2]
        if a * px + b * py + c * pz + d < 0.0:
            return False
    return True


def texture_array_groups(textures: Iterable[TextureResidencyInfo]) -> dict[tuple[int, int, str, bool], list[TextureResidencyInfo]]:
    groups: dict[tuple[int, int, str, bool], list[TextureResidencyInfo]] = {}
    for texture in textures:
        if not texture.array_eligible:
            continue
        groups.setdefault(texture.array_group_key, []).append(texture)
    return groups


def _array_len(value: object) -> int:
    if value is None:
        return 0
    shape = getattr(value, "shape", None)
    if shape:
        try:
            return int(shape[0])
        except Exception:
            return 0
    size = getattr(value, "size", None)
    if size is not None:
        try:
            return int(size)
        except Exception:
            return 0
    try:
        return len(value)  # type: ignore[arg-type]
    except Exception:
        return 0


def _row_add(a: Sequence[float], b: Sequence[float]) -> tuple[float, float, float, float]:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2], a[3] + b[3])


def _row_sub(a: Sequence[float], b: Sequence[float]) -> tuple[float, float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2], a[3] - b[3])


def _normalize_plane(plane: Sequence[float]) -> tuple[float, float, float, float]:
    a, b, c, d = (float(v) for v in plane[:4])
    length = math.sqrt(a * a + b * b + c * c)
    if length <= 1e-8:
        return (a, b, c, d)
    return (a / length, b / length, c / length, d / length)
