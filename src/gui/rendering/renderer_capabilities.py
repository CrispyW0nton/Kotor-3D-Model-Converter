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
    skeleton_overlay_supported: bool = False
    joint_dot_overlay_supported: bool = False
    bone_selection_supported: bool = False
    skinned_mesh_supported: bool = False
    gpu_skinning_supported: bool = False
    cpu_skinning_fallback_supported: bool = False
    animation_preview_supported: bool = False
    skin_weight_heatmap_supported: bool = False
    max_supported_bones: int = 0
    bone_matrix_buffer_type: str = ""
    skinned_shader_status: str = ""
    supports_marquee_selection: bool = False
    supports_subobject_selection: bool = False
    supports_batching: bool = False
    supports_instancing: bool = False
    supports_texture_streaming: bool = False
    supports_texture_arrays: bool = False
    supports_atlas: bool = False
    supports_frustum_culling: bool = False
    supports_gpu_timing: bool = False
    supports_dynamic_quality: bool = False
    details: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "backend_id": self.backend_id,
            "name": self.name,
            "available": self.available,
            "reason": self.reason,
            "api": self.api,
            "supports_scene_meshes": self.supports_scene_meshes,
            "supports_textures": self.supports_textures,
            "supports_grid": self.supports_grid,
            "supports_overlays": self.supports_overlays,
            "supports_hot_switch": self.supports_hot_switch,
            "requires_restart": self.requires_restart,
            "diagnostic_only": self.diagnostic_only,
            "supported_display_modes": tuple(self.supported_display_modes),
            "supported_display_options": tuple(self.supported_display_options),
            "fallback_display_modes": dict(self.fallback_display_modes),
            "supports_object_picking": self.supports_object_picking,
            "supports_cpu_ray_picking": self.supports_cpu_ray_picking,
            "supports_gpu_id_picking": self.supports_gpu_id_picking,
            "supports_selection_highlight": self.supports_selection_highlight,
            "supports_gizmo_drawing": self.supports_gizmo_drawing,
            "supports_gizmo_interaction": self.supports_gizmo_interaction,
            "skeleton_overlay_supported": self.skeleton_overlay_supported,
            "joint_dot_overlay_supported": self.joint_dot_overlay_supported,
            "bone_selection_supported": self.bone_selection_supported,
            "skinned_mesh_supported": self.skinned_mesh_supported,
            "gpu_skinning_supported": self.gpu_skinning_supported,
            "cpu_skinning_fallback_supported": self.cpu_skinning_fallback_supported,
            "animation_preview_supported": self.animation_preview_supported,
            "skin_weight_heatmap_supported": self.skin_weight_heatmap_supported,
            "max_supported_bones": self.max_supported_bones,
            "bone_matrix_buffer_type": self.bone_matrix_buffer_type,
            "skinned_shader_status": self.skinned_shader_status,
            "supports_marquee_selection": self.supports_marquee_selection,
            "supports_subobject_selection": self.supports_subobject_selection,
            "supports_batching": self.supports_batching,
            "supports_instancing": self.supports_instancing,
            "supports_texture_streaming": self.supports_texture_streaming,
            "supports_texture_arrays": self.supports_texture_arrays,
            "supports_atlas": self.supports_atlas,
            "supports_frustum_culling": self.supports_frustum_culling,
            "supports_gpu_timing": self.supports_gpu_timing,
            "supports_dynamic_quality": self.supports_dynamic_quality,
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, values: dict) -> "RendererCapabilities":
        payload = dict(values or {})
        return cls(
            backend_id=str(payload.get("backend_id") or ""),
            name=str(payload.get("name") or ""),
            available=bool(payload.get("available", False)),
            reason=str(payload.get("reason") or ""),
            api=str(payload.get("api") or ""),
            supports_scene_meshes=bool(payload.get("supports_scene_meshes", False)),
            supports_textures=bool(payload.get("supports_textures", False)),
            supports_grid=bool(payload.get("supports_grid", False)),
            supports_overlays=bool(payload.get("supports_overlays", True)),
            supports_hot_switch=bool(payload.get("supports_hot_switch", False)),
            requires_restart=bool(payload.get("requires_restart", False)),
            diagnostic_only=bool(payload.get("diagnostic_only", False)),
            supported_display_modes=tuple(payload.get("supported_display_modes") or ()),
            supported_display_options=tuple(payload.get("supported_display_options") or ()),
            fallback_display_modes=dict(payload.get("fallback_display_modes") or {}),
            supports_object_picking=bool(payload.get("supports_object_picking", False)),
            supports_cpu_ray_picking=bool(payload.get("supports_cpu_ray_picking", False)),
            supports_gpu_id_picking=bool(payload.get("supports_gpu_id_picking", False)),
            supports_selection_highlight=bool(payload.get("supports_selection_highlight", False)),
            supports_gizmo_drawing=bool(payload.get("supports_gizmo_drawing", False)),
            supports_gizmo_interaction=bool(payload.get("supports_gizmo_interaction", False)),
            skeleton_overlay_supported=bool(payload.get("skeleton_overlay_supported", False)),
            joint_dot_overlay_supported=bool(payload.get("joint_dot_overlay_supported", False)),
            bone_selection_supported=bool(payload.get("bone_selection_supported", False)),
            skinned_mesh_supported=bool(payload.get("skinned_mesh_supported", False)),
            gpu_skinning_supported=bool(payload.get("gpu_skinning_supported", False)),
            cpu_skinning_fallback_supported=bool(payload.get("cpu_skinning_fallback_supported", False)),
            animation_preview_supported=bool(payload.get("animation_preview_supported", False)),
            skin_weight_heatmap_supported=bool(payload.get("skin_weight_heatmap_supported", False)),
            max_supported_bones=int(payload.get("max_supported_bones") or 0),
            bone_matrix_buffer_type=str(payload.get("bone_matrix_buffer_type") or ""),
            skinned_shader_status=str(payload.get("skinned_shader_status") or ""),
            supports_marquee_selection=bool(payload.get("supports_marquee_selection", False)),
            supports_subobject_selection=bool(payload.get("supports_subobject_selection", False)),
            supports_batching=bool(payload.get("supports_batching", False)),
            supports_instancing=bool(payload.get("supports_instancing", False)),
            supports_texture_streaming=bool(payload.get("supports_texture_streaming", False)),
            supports_texture_arrays=bool(payload.get("supports_texture_arrays", False)),
            supports_atlas=bool(payload.get("supports_atlas", False)),
            supports_frustum_culling=bool(payload.get("supports_frustum_culling", False)),
            supports_gpu_timing=bool(payload.get("supports_gpu_timing", False)),
            supports_dynamic_quality=bool(payload.get("supports_dynamic_quality", False)),
            details=dict(payload.get("details") or {}),
        )

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
