"""Optional wgpu-py renderer backend probes.

The first GhostRigger WGPU integration is deliberately diagnostic-only.  It
does not claim scene parity until the Qt surface, mesh upload, material, and
readback paths are implemented for the existing viewport contract.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass

from src.gui.rendering.null_renderer import NullDiagnosticRenderer
from src.gui.rendering.renderer_backend import RendererBackend
from src.gui.rendering.renderer_capabilities import RendererCapabilities


_WGPU_BACKEND_ENV = "WGPU_BACKEND_TYPE"


@dataclass(frozen=True)
class _WgpuBackendSpec:
    backend: RendererBackend
    name: str
    wgpu_backend_type: str


class WgpuRenderer(NullDiagnosticRenderer):
    """Diagnostic-only WGPU adapter with lazy import and clear availability."""

    def __init__(self, backend: RendererBackend = RendererBackend.WGPU_AUTO):
        super().__init__()
        self._spec = _WgpuBackendSpec(
            backend=backend,
            name={
                RendererBackend.WGPU_D3D12: "WGPU Direct3D 12",
                RendererBackend.WGPU_VULKAN: "WGPU Vulkan",
                RendererBackend.WGPU_OPENGL: "WGPU OpenGL",
            }.get(backend, "WGPU Auto"),
            wgpu_backend_type={
                RendererBackend.WGPU_D3D12: "D3D12",
                RendererBackend.WGPU_VULKAN: "Vulkan",
                RendererBackend.WGPU_OPENGL: "OpenGL",
            }.get(backend, ""),
        )
        self.name = self._spec.name
        self.backend_id = self._spec.backend.value

    def _import_reason(self) -> str:
        if importlib.util.find_spec("wgpu") is None:
            return "wgpu is not installed"
        return "WGPU viewport surface and scene pipeline are diagnostic-only in this build"

    def is_available(self) -> bool:
        return False

    def get_capabilities(self) -> RendererCapabilities:
        has_wgpu = importlib.util.find_spec("wgpu") is not None
        return RendererCapabilities(
            backend_id=self.backend_id,
            name=self.name,
            available=False,
            reason=self._import_reason(),
            api="WGPU",
            supports_scene_meshes=False,
            supports_textures=False,
            supports_grid=False,
            supports_overlays=True,
            diagnostic_only=True,
            requires_restart=True,
            details={
                "wgpu_installed": has_wgpu,
                "requested_backend_type": self._spec.wgpu_backend_type or "auto",
                "env_var": _WGPU_BACKEND_ENV,
            },
        )

    def initialize(self, viewport_widget=None, scene_context=None) -> None:
        # If GhostRigger later creates a real wgpu device here, WGPU_BACKEND_TYPE
        # must be set before this point.  Do not mutate it after device creation.
        if self._spec.wgpu_backend_type and not os.environ.get(_WGPU_BACKEND_ENV):
            self._diagnostics["requested_env"] = f"{_WGPU_BACKEND_ENV}={self._spec.wgpu_backend_type}"

    def get_diagnostics(self) -> dict:
        caps = self.get_capabilities()
        return {
            "name": self.name,
            "backend_id": self.backend_id,
            "available": False,
            "api": "WGPU",
            "backend": self._spec.wgpu_backend_type or "auto",
            "reason": caps.reason,
            "wgpu_installed": caps.details.get("wgpu_installed"),
        }

