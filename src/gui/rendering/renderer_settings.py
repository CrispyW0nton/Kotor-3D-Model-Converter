"""Renderer settings read from GhostRigger settings.json."""

from __future__ import annotations

from dataclasses import dataclass

from src.gui.rendering.renderer_backend import RendererBackend, normalize_renderer_backend


def _safe_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _safe_int(value: object, default: int, minimum: int = 1) -> int:
    try:
        return max(int(minimum), int(value))
    except Exception:
        return max(int(minimum), int(default))


def _safe_float(value: object, default: float, minimum: float = 0.0) -> float:
    try:
        return max(float(minimum), float(value))
    except Exception:
        return max(float(minimum), float(default))


@dataclass(frozen=True)
class RendererSettings:
    backend: RendererBackend = RendererBackend.AUTOMATIC
    preferred_windows_backend: RendererBackend = RendererBackend.MODERNGL_GL330
    allow_fallback: bool = True
    show_renderer_diagnostics: bool = True
    force_safe_mode: bool = False
    target_fps: int = 60
    idle_render_mode: str = "dirty_only"
    throttle_diagnostics: bool = True
    diagnostics_hz: float = 2.0
    overlay_dirty_rendering: bool = True
    wgpu_enable_batching: bool = True
    wgpu_enable_instancing: bool = True
    wgpu_enable_frustum_culling: bool = True
    wgpu_enable_lazy_upload: bool = True
    wgpu_enable_texture_arrays: bool = False
    wgpu_enable_texture_atlas: bool = False
    wgpu_pick_on_demand_only: bool = True
    wgpu_cache_render_queue: bool = True
    wgpu_cache_draw_items: bool = True
    wgpu_profile_frames: bool = False
    wgpu_profile_gpu_frames: bool = False
    wgpu_dynamic_quality: bool = True
    wgpu_max_texture_memory_mb: int = 512
    wgpu_max_uploads_per_frame: int = 16
    dynamic_quality_large_scene_threshold: int = 5000
    dynamic_quality_simplify_while_navigating: bool = True

    @classmethod
    def from_settings(cls, settings: dict | None) -> "RendererSettings":
        values = dict((settings or {}).get("renderer") or {})
        wgpu_values = dict(values.get("wgpu") or {})
        dynamic_quality = dict(values.get("dynamic_quality") or {})
        return cls(
            backend=normalize_renderer_backend(values.get("backend", RendererBackend.AUTOMATIC.value)),
            preferred_windows_backend=normalize_renderer_backend(
                values.get("preferred_windows_backend", RendererBackend.MODERNGL_GL330.value)
            ),
            allow_fallback=_safe_bool(values.get("allow_fallback", True), True),
            show_renderer_diagnostics=_safe_bool(values.get("show_renderer_diagnostics", True), True),
            force_safe_mode=_safe_bool(values.get("force_safe_mode", False), False),
            target_fps=_safe_int(values.get("target_fps", 60), 60),
            idle_render_mode=str(values.get("idle_render_mode", "dirty_only") or "dirty_only"),
            throttle_diagnostics=_safe_bool(values.get("throttle_diagnostics", True), True),
            diagnostics_hz=_safe_float(values.get("diagnostics_hz", 2.0), 2.0, minimum=0.1),
            overlay_dirty_rendering=_safe_bool(values.get("overlay_dirty_rendering", True), True),
            wgpu_enable_batching=_safe_bool(wgpu_values.get("enable_batching", values.get("wgpu_enable_batching", True)), True),
            wgpu_enable_instancing=_safe_bool(wgpu_values.get("enable_instancing", values.get("wgpu_enable_instancing", True)), True),
            wgpu_enable_frustum_culling=_safe_bool(wgpu_values.get("enable_frustum_culling", values.get("wgpu_enable_frustum_culling", True)), True),
            wgpu_enable_lazy_upload=_safe_bool(wgpu_values.get("enable_lazy_upload", values.get("wgpu_enable_lazy_upload", True)), True),
            wgpu_enable_texture_arrays=_safe_bool(wgpu_values.get("enable_texture_arrays", values.get("wgpu_enable_texture_arrays", False)), False),
            wgpu_enable_texture_atlas=_safe_bool(wgpu_values.get("enable_texture_atlas", values.get("wgpu_enable_texture_atlas", False)), False),
            wgpu_pick_on_demand_only=_safe_bool(wgpu_values.get("pick_on_demand_only", values.get("wgpu_pick_on_demand_only", True)), True),
            wgpu_cache_render_queue=_safe_bool(wgpu_values.get("cache_render_queue", values.get("wgpu_cache_render_queue", True)), True),
            wgpu_cache_draw_items=_safe_bool(wgpu_values.get("cache_draw_items", values.get("wgpu_cache_draw_items", True)), True),
            wgpu_profile_frames=_safe_bool(
                wgpu_values.get(
                    "profile_cpu_frames",
                    wgpu_values.get("profile_frames", values.get("wgpu_profile_frames", False)),
                ),
                False,
            ),
            wgpu_profile_gpu_frames=_safe_bool(wgpu_values.get("profile_gpu_frames", values.get("wgpu_profile_gpu_frames", False)), False),
            wgpu_dynamic_quality=_safe_bool(wgpu_values.get("dynamic_quality", values.get("wgpu_dynamic_quality", True)), True),
            wgpu_max_texture_memory_mb=_safe_int(wgpu_values.get("max_texture_memory_mb", values.get("wgpu_max_texture_memory_mb", 512)), 512),
            wgpu_max_uploads_per_frame=_safe_int(wgpu_values.get("max_uploads_per_frame", values.get("wgpu_max_uploads_per_frame", 16)), 16),
            dynamic_quality_large_scene_threshold=_safe_int(
                dynamic_quality.get("large_scene_threshold", values.get("dynamic_quality_large_scene_threshold", 5000)),
                5000,
            ),
            dynamic_quality_simplify_while_navigating=_safe_bool(
                dynamic_quality.get("simplify_while_navigating", values.get("dynamic_quality_simplify_while_navigating", True)),
                True,
            ),
        )

    def to_settings_dict(self) -> dict[str, object]:
        return {
            "backend": self.backend.value,
            "preferred_windows_backend": self.preferred_windows_backend.value,
            "allow_fallback": self.allow_fallback,
            "show_renderer_diagnostics": self.show_renderer_diagnostics,
            "force_safe_mode": self.force_safe_mode,
            "target_fps": self.target_fps,
            "idle_render_mode": self.idle_render_mode,
            "throttle_diagnostics": self.throttle_diagnostics,
            "diagnostics_hz": self.diagnostics_hz,
            "overlay_dirty_rendering": self.overlay_dirty_rendering,
            "wgpu": {
                "enable_batching": self.wgpu_enable_batching,
                "enable_instancing": self.wgpu_enable_instancing,
                "enable_frustum_culling": self.wgpu_enable_frustum_culling,
                "enable_lazy_upload": self.wgpu_enable_lazy_upload,
                "enable_texture_arrays": self.wgpu_enable_texture_arrays,
                "enable_texture_atlas": self.wgpu_enable_texture_atlas,
                "pick_on_demand_only": self.wgpu_pick_on_demand_only,
                "cache_render_queue": self.wgpu_cache_render_queue,
                "cache_draw_items": self.wgpu_cache_draw_items,
                "profile_frames": self.wgpu_profile_frames,
                "profile_cpu_frames": self.wgpu_profile_frames,
                "profile_gpu_frames": self.wgpu_profile_gpu_frames,
                "dynamic_quality": self.wgpu_dynamic_quality,
                "max_texture_memory_mb": self.wgpu_max_texture_memory_mb,
                "max_uploads_per_frame": self.wgpu_max_uploads_per_frame,
            },
            "dynamic_quality": {
                "enabled": self.wgpu_dynamic_quality,
                "large_scene_threshold": self.dynamic_quality_large_scene_threshold,
                "simplify_while_navigating": self.dynamic_quality_simplify_while_navigating,
            },
        }

    @staticmethod
    def apply_defaults(settings: dict) -> dict:
        renderer = settings.setdefault("renderer", {})
        defaults = RendererSettings().to_settings_dict()
        for key, value in defaults.items():
            renderer.setdefault(key, value)
        renderer["backend"] = normalize_renderer_backend(renderer.get("backend")).value
        renderer["preferred_windows_backend"] = normalize_renderer_backend(
            renderer.get("preferred_windows_backend")
        ).value
        wgpu = renderer.setdefault("wgpu", {})
        for key, value in defaults["wgpu"].items():
            wgpu.setdefault(key, value)
        dynamic_quality = renderer.setdefault("dynamic_quality", {})
        for key, value in defaults["dynamic_quality"].items():
            dynamic_quality.setdefault(key, value)
        return settings
