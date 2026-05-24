"""Renderer capability and availability records."""

from __future__ import annotations

from dataclasses import dataclass, field


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
    details: dict[str, object] = field(default_factory=dict)

    def status_text(self) -> str:
        if self.available:
            suffix = " (diagnostic only)" if self.diagnostic_only else ""
            return f"Available{suffix}"
        return f"Unavailable: {self.reason or 'not supported'}"

