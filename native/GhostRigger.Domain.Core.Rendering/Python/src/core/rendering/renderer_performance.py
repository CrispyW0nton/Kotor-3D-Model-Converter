"""Renderer performance helpers shared by tests and WGPU diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import time
from typing import Callable, Iterable, Sequence


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
class RenderQueueCache:
    """Small revision-key cache for persistent WGPU draw-item queues."""

    revision_key: tuple | None = None
    draw_items: list = field(default_factory=list)
    edge_items: list = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
    rebuild_count: int = 0
    hit_count: int = 0
    last_rebuild_reason: str = ""

    def invalidate(self, reason: str = "") -> None:
        self.revision_key = None
        self.draw_items = []
        self.edge_items = []
        self.metadata = {}
        self.last_rebuild_reason = str(reason or "invalidated")

    def get_or_build(
        self,
        revision_key: tuple,
        builder: Callable[[], tuple[list, list, dict[str, object]]],
        *,
        reason: str = "",
    ) -> tuple[list, list, dict[str, object], bool]:
        key = tuple(revision_key or ())
        if self.revision_key == key:
            self.hit_count += 1
            return self.draw_items, self.edge_items, self.metadata, False
        draw_items, edge_items, metadata = builder()
        self.revision_key = key
        self.draw_items = list(draw_items or [])
        self.edge_items = list(edge_items or [])
        self.metadata = dict(metadata or {})
        self.rebuild_count += 1
        self.last_rebuild_reason = str(reason or "revision changed")
        return self.draw_items, self.edge_items, self.metadata, True

    def diagnostics(self) -> dict[str, object]:
        return {
            "revision_key_active": self.revision_key is not None,
            "draw_item_count": len(self.draw_items),
            "edge_item_count": len(self.edge_items),
            "rebuild_count": int(self.rebuild_count),
            "hit_count": int(self.hit_count),
            "last_rebuild_reason": self.last_rebuild_reason,
        }


class ViewportFrameGovernor:
    """Dirty-state frame pacing for the Qt viewport render loop."""

    DIRTY_FLAGS = (
        "scene",
        "camera",
        "transform",
        "geometry",
        "material",
        "style",
        "visibility",
        "overlay",
        "resources",
        "selection",
        "lighting",
        "animation",
        "gizmo",
        "diagnostics",
        "hud",
    )

    def __init__(self, target_fps: int = 60, *, idle_mode: str = "dirty_only") -> None:
        self.target_fps = max(1, int(target_fps or 60))
        self.idle_mode = str(idle_mode or "dirty_only")
        self.active_interaction = False
        self.animation_playing = False
        self.dirty_flags = {name: False for name in self.DIRTY_FLAGS}
        self.last_frame_time = 0.0
        self.last_render_reason = ""
        self.pending_reason = ""
        self.active_reason = ""
        self.frames_skipped = 0
        self.frames_rendered = 0

    @property
    def frame_interval_s(self) -> float:
        return 1.0 / max(1, int(self.target_fps))

    @property
    def dirty(self) -> bool:
        return any(self.dirty_flags.values())

    def set_target_fps(self, fps: int) -> None:
        self.target_fps = max(1, int(fps or 60))

    def set_idle_mode(self, mode: str | bool = "dirty_only") -> None:
        if isinstance(mode, bool):
            self.idle_mode = "dirty_only" if mode else "continuous"
        else:
            self.idle_mode = str(mode or "dirty_only")

    def request_redraw(self, reason: str = "", **dirty_flags: bool) -> None:
        reason = str(reason or "redraw requested")
        self.pending_reason = reason
        matched = False
        for name, value in dirty_flags.items():
            if name in self.dirty_flags and bool(value):
                self.dirty_flags[name] = True
                matched = True
        if not matched:
            self.dirty_flags["scene"] = True

    def begin_interaction(self, reason: str = "") -> None:
        self.active_interaction = True
        self.active_reason = str(reason or "interaction")
        self.request_redraw(self.active_reason, camera=True, overlay=True)

    def end_interaction(self, reason: str = "") -> None:
        self.active_interaction = False
        self.active_reason = ""
        self.request_redraw(str(reason or "interaction ended"), camera=True, overlay=True)

    def set_animation_playing(self, playing: bool, reason: str = "animation") -> None:
        self.animation_playing = bool(playing)
        if playing:
            self.request_redraw(reason, scene=True)

    def should_render_now(self, now: float | None = None) -> bool:
        now = time.perf_counter() if now is None else float(now)
        active = bool(self.active_interaction or self.animation_playing)
        if not self.dirty and self.idle_mode == "dirty_only" and not active:
            self.frames_skipped += 1
            return False
        elapsed = now - float(self.last_frame_time or 0.0)
        if self.last_frame_time and elapsed < self.frame_interval_s:
            self.frames_skipped += 1
            return False
        return True

    def delay_until_next_frame_ms(self, now: float | None = None) -> int:
        now = time.perf_counter() if now is None else float(now)
        if not self.last_frame_time:
            return 0
        remaining = self.frame_interval_s - (now - self.last_frame_time)
        return max(1, int(math.ceil(max(0.0, remaining) * 1000.0)))

    def mark_clean_after_render(self, reason: str = "", now: float | None = None) -> None:
        self.frames_rendered += 1
        self.last_frame_time = time.perf_counter() if now is None else float(now)
        self.last_render_reason = str(reason or self.pending_reason or self.active_reason or "render")
        self.pending_reason = ""
        for name in self.dirty_flags:
            self.dirty_flags[name] = False

    def diagnostics(self) -> dict[str, object]:
        return {
            "target_fps": int(self.target_fps),
            "idle_mode": self.idle_mode,
            "active_interaction": bool(self.active_interaction),
            "animation_playing": bool(self.animation_playing),
            "dirty": bool(self.dirty),
            "dirty_flags": dict(self.dirty_flags),
            "last_render_reason": self.last_render_reason,
            "pending_reason": self.pending_reason,
            "frames_rendered": int(self.frames_rendered),
            "frames_skipped": int(self.frames_skipped),
        }


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
        if len(item) >= 5:
            mesh_data = item[3]
            material_data = item[4]
        elif len(item) >= 4:
            mesh_data = item[2]
            material_data = item[3]
        else:
            mesh_data = item[0]
            material_data = getattr(mesh_data, "material", None)
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
        if len(item) >= 5:
            mesh_data = item[3]
            material_data = item[4]
        elif len(item) >= 4:
            mesh_data = item[2]
            material_data = item[3]
        else:
            mesh_data = item[0]
            material_data = getattr(mesh_data, "material", None)
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
