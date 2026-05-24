"""Renderer capability and availability records."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.gui.rendering.viewport_display import ViewportDisplayMode, display_mode_values


@dataclass(frozen=True)
class RendererCapabilities:
    backend_id: str
    name: str
    available: bool
    reason: str = ""
    api: str = ""
    supports_scene_meshes: bool = False
    supports_textures: bool = False
    supports_grid: bool = False
    supports_overlays: bool = True
    supports_hot_switch: bool = False
    requires_restart: bool = False
    diagnostic_only: bool = False
    supported_display_modes: tuple[str, ...] = field(default_factory=tuple)
    supported_display_options: tuple[str, ...] = field(default_factory=tuple)
    fallback_display_modes: dict[str, str] = field(default_factory=dict)
    supports_object_picking: bool = False
    supports_cpu_ray_picking: bool = False
    supports_gpu_id_picking: bool = False
    supports_selection_highlight: bool = False
    supports_gizmo_drawing: bool = False
    supports_gizmo_interaction: bool = False
    supports_marquee_selection: bool = False
    supports_subobject_selection: bool = False
    details: dict[str, object] = field(default_factory=dict)

    def status_text(self) -> str:
        if self.available:
            suffix = " (diagnostic only)" if self.diagnostic_only else ""
            return f"Available{suffix}"
        return f"Unavailable: {self.reason or 'not supported'}"

    def supports_display_mode(self, mode: object) -> bool:
        if not self.available:
            return False
        if not self.supported_display_modes:
            return not self.diagnostic_only
        if isinstance(mode, ViewportDisplayMode):
            key = mode.value
        else:
            key = str(mode or "").strip().lower()
        return key in set(self.supported_display_modes)


MODERNGL_DISPLAY_MODES = display_mode_values(
    (
        ViewportDisplayMode.WIREFRAME,
        ViewportDisplayMode.HIDDEN_LINE,
        ViewportDisplayMode.SOLID,
        ViewportDisplayMode.SHADED,
        ViewportDisplayMode.SMOOTH_SHADED,
        ViewportDisplayMode.TEXTURED,
        ViewportDisplayMode.TEXTURED_LIGHTMAPPED,
        ViewportDisplayMode.FULL_MATERIAL,
        ViewportDisplayMode.BOUNDING_BOX,
    )
)

WGPU_DISPLAY_MODES = display_mode_values(
    (
        ViewportDisplayMode.WIREFRAME,
        ViewportDisplayMode.HIDDEN_LINE,
        ViewportDisplayMode.SOLID,
        ViewportDisplayMode.SHADED,
        ViewportDisplayMode.SMOOTH_SHADED,
        ViewportDisplayMode.TEXTURED,
        ViewportDisplayMode.TEXTURED_LIGHTMAPPED,
    )
)

WGPU_FALLBACK_DISPLAY_MODES = {
    ViewportDisplayMode.FULL_MATERIAL.value: ViewportDisplayMode.TEXTURED_LIGHTMAPPED.value,
    ViewportDisplayMode.BOUNDING_BOX.value: ViewportDisplayMode.SOLID.value,
    ViewportDisplayMode.NORMALS_DEBUG.value: ViewportDisplayMode.SHADED.value,
    ViewportDisplayMode.UV_DEBUG.value: ViewportDisplayMode.TEXTURED.value,
}

DIAGNOSTIC_DISPLAY_MODES = (ViewportDisplayMode.SOLID.value,)
