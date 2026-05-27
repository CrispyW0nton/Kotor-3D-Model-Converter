"""Lightweight renderer profiling primitives.

The profiler is intentionally opt-in.  Disabled instances keep only the latest
counter snapshot and avoid nested timing work in the render loop.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import time
from typing import Iterator


@dataclass
class RendererFrameMetrics:
    frame_time_ms: float = 0.0
    cpu_prepare_ms: float = 0.0
    gpu_submit_ms: float = 0.0
    pick_pass_ms: float = 0.0
    overlay_ms: float = 0.0
    gizmo_ms: float = 0.0
    skeleton_ms: float = 0.0
    animation_pose_upload_ms: float = 0.0
    alpha_sort_ms: float = 0.0
    draw_calls: int = 0
    mesh_count: int = 0
    visible_mesh_count: int = 0
    culled_mesh_count: int = 0
    material_group_count: int = 0
    texture_bind_count: int = 0
    buffer_upload_count: int = 0
    texture_upload_count: int = 0
    bind_group_creation_count: int = 0
    pipeline_switch_count: int = 0
    batch_count: int = 0
    instance_group_count: int = 0
    instance_count: int = 0
    alpha_object_count: int = 0
    skeleton_pose_upload_count: int = 0
    pending_uploads: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    estimated_gpu_memory_bytes: int = 0
    estimated_texture_memory_bytes: int = 0
    estimated_vertex_index_memory_bytes: int = 0
    extra: dict[str, object] = field(default_factory=dict)

    @property
    def fps_estimate(self) -> float:
        if self.frame_time_ms <= 1e-6:
            return 0.0
        return 1000.0 / self.frame_time_ms

    def to_dict(self) -> dict[str, object]:
        data = {
            "frame_time_ms": round(float(self.frame_time_ms), 3),
            "fps_estimate": round(float(self.fps_estimate), 2),
            "cpu_prepare_ms": round(float(self.cpu_prepare_ms), 3),
            "gpu_submit_ms": round(float(self.gpu_submit_ms), 3),
            "pick_pass_ms": round(float(self.pick_pass_ms), 3),
            "overlay_ms": round(float(self.overlay_ms), 3),
            "gizmo_ms": round(float(self.gizmo_ms), 3),
            "skeleton_ms": round(float(self.skeleton_ms), 3),
            "animation_pose_upload_ms": round(float(self.animation_pose_upload_ms), 3),
            "alpha_sort_ms": round(float(self.alpha_sort_ms), 3),
            "draw_calls": int(self.draw_calls),
            "mesh_count": int(self.mesh_count),
            "visible_mesh_count": int(self.visible_mesh_count),
            "culled_mesh_count": int(self.culled_mesh_count),
            "material_group_count": int(self.material_group_count),
            "texture_bind_count": int(self.texture_bind_count),
            "buffer_upload_count": int(self.buffer_upload_count),
            "texture_upload_count": int(self.texture_upload_count),
            "bind_group_creation_count": int(self.bind_group_creation_count),
            "pipeline_switch_count": int(self.pipeline_switch_count),
            "batch_count": int(self.batch_count),
            "instance_group_count": int(self.instance_group_count),
            "instance_count": int(self.instance_count),
            "alpha_object_count": int(self.alpha_object_count),
            "skeleton_pose_upload_count": int(self.skeleton_pose_upload_count),
            "pending_uploads": int(self.pending_uploads),
            "cache_hits": int(self.cache_hits),
            "cache_misses": int(self.cache_misses),
            "estimated_gpu_memory_bytes": int(self.estimated_gpu_memory_bytes),
            "estimated_texture_memory_bytes": int(self.estimated_texture_memory_bytes),
            "estimated_vertex_index_memory_bytes": int(self.estimated_vertex_index_memory_bytes),
        }
        data.update(dict(self.extra or {}))
        return data


class RendererProfiler:
    """Optional per-frame profiler with near-zero disabled overhead."""

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = bool(enabled)
        self.current = RendererFrameMetrics()
        self.last = RendererFrameMetrics()
        self._frame_started = 0.0

    def begin_frame(self) -> None:
        self.current = RendererFrameMetrics()
        self._frame_started = time.perf_counter() if self.enabled else 0.0

    def end_frame(self, *, fallback_frame_ms: float | None = None) -> None:
        if self.enabled and self._frame_started:
            self.current.frame_time_ms = (time.perf_counter() - self._frame_started) * 1000.0
        elif fallback_frame_ms is not None:
            self.current.frame_time_ms = float(fallback_frame_ms)
        self.last = self.current

    @contextmanager
    def section(self, name: str) -> Iterator[None]:
        if not self.enabled:
            yield
            return
        started = time.perf_counter()
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - started) * 1000.0
            attr = f"{name}_ms"
            if hasattr(self.current, attr):
                setattr(self.current, attr, float(getattr(self.current, attr)) + elapsed)
            else:
                self.current.extra[attr] = round(float(self.current.extra.get(attr, 0.0)) + elapsed, 3)

    def add(self, key: str, amount: int = 1) -> None:
        if hasattr(self.current, key):
            setattr(self.current, key, int(getattr(self.current, key)) + int(amount))
        else:
            self.current.extra[key] = int(self.current.extra.get(key, 0)) + int(amount)

    def set(self, key: str, value: object) -> None:
        if hasattr(self.current, key):
            setattr(self.current, key, value)
        else:
            self.current.extra[key] = value

    def diagnostics(self) -> dict[str, object]:
        return self.last.to_dict()
