"""Windows Direct3D renderer adapter."""

from __future__ import annotations

import platform

from src.gui.rendering.null_renderer import NullDiagnosticRenderer
from src.gui.rendering.renderer_backend import RendererBackend
from src.gui.rendering.renderer_capabilities import RendererCapabilities


class Direct3DRenderer(NullDiagnosticRenderer):
    """Unavailable Direct3D adapter until a safe Qt/native binding is added."""

    def __init__(self, backend: RendererBackend = RendererBackend.DIRECT3D_HARDWARE):
        super().__init__()
        self._backend = backend
        self.name = (
            "Direct3D WARP Experimental"
            if backend == RendererBackend.DIRECT3D_WARP
            else "Direct3D Hardware Experimental"
        )
        self.backend_id = backend.value

    def is_available(self) -> bool:
        return False

    def _reason(self) -> str:
        if platform.system().lower() != "windows":
            return "Direct3D is only available on Windows"
        return "No safe Direct3D Qt surface/device binding is implemented yet; use WGPU_D3D12 for DirectX-backed routing"

    def get_capabilities(self) -> RendererCapabilities:
        return RendererCapabilities(
            backend_id=self.backend_id,
            name=self.name,
            available=False,
            reason=self._reason(),
            api="Direct3D",
            supports_scene_meshes=False,
            supports_textures=False,
            supports_grid=False,
            supports_overlays=True,
            diagnostic_only=True,
            requires_restart=True,
            details={"os": platform.system()},
        )

    def get_diagnostics(self) -> dict:
        return {
            "name": self.name,
            "backend_id": self.backend_id,
            "available": False,
            "api": "Direct3D",
            "backend": "hardware" if self._backend == RendererBackend.DIRECT3D_HARDWARE else "warp",
            "reason": self._reason(),
        }
