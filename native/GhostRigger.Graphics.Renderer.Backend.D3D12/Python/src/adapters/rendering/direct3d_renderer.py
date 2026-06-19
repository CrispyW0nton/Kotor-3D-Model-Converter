"""Windows Direct3D renderer adapter."""

from __future__ import annotations

import platform

from src.adapters.rendering.null_renderer import NullDiagnosticRenderer
from src.core.rendering.renderer_backend import RendererBackend
from src.core.rendering.renderer_capabilities import RendererCapabilities


class Direct3DRenderer(NullDiagnosticRenderer):
    """Retired compatibility stub; Direct3D rendering is provided by WGPU D3D12."""

    def __init__(self, backend: RendererBackend = RendererBackend.DIRECT3D_HARDWARE):
        super().__init__()
        self._backend = backend
        self.name = "Retired Direct3D placeholder"
        self.backend_id = backend.value

    def is_available(self) -> bool:
        return False

    def _reason(self) -> str:
        if platform.system().lower() != "windows":
            return "Direct3D is only available on Windows"
        return "Retired renderer placeholder; use Direct3D (WGPU)"

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
