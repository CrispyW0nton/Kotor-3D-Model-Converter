"""Environment preparation for the optional pygfx/WGPU renderer."""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass

_WGPU_BACKEND_ENV = "WGPU_BACKEND_TYPE"
_WGPU_POWER_ENV = "WGPU_POWER_PREF"
_GPU_IMPORTS = ("wgpu", "pygfx", "rendercanvas")


@dataclass(frozen=True)
class PygfxBackendEnvStatus:
    requested_backend: str
    selected_backend: str
    power_preference: str
    d3d12_requested: bool
    restart_required: bool
    fallback_allowed: bool
    reason: str = ""


def gpu_runtime_imported() -> bool:
    """Return whether a WGPU/pygfx runtime module has already been imported."""

    return any(name in sys.modules for name in _GPU_IMPORTS)


def prepare_pygfx_wgpu_environment(
    *,
    device_created: bool = False,
    runtime_imported: bool | None = None,
) -> PygfxBackendEnvStatus:
    """Request D3D12/high-performance before pygfx imports WGPU on Windows."""

    is_windows = platform.system().lower() == "windows"
    requested = "D3D12" if is_windows else ""
    current = os.environ.get(_WGPU_BACKEND_ENV, "")
    power = os.environ.get(_WGPU_POWER_ENV, "")
    restart_required = False
    reason = ""
    runtime_imported = gpu_runtime_imported() if runtime_imported is None else bool(runtime_imported)

    if not power:
        os.environ[_WGPU_POWER_ENV] = "high-performance"
        power = "high-performance"

    if requested:
        if current and current.upper() != requested:
            restart_required = bool(device_created or runtime_imported)
            reason = (
                f"{_WGPU_BACKEND_ENV} is already {current}; restart GhostRigger to switch pygfx to {requested}"
                if restart_required
                else ""
            )
            if not device_created:
                os.environ[_WGPU_BACKEND_ENV] = requested
                current = requested
        elif not current:
            if device_created or runtime_imported:
                restart_required = True
                reason = (
                    f"{_WGPU_BACKEND_ENV} must be set before importing WGPU/pygfx/rendercanvas; "
                    "restart GhostRigger"
                )
            else:
                os.environ[_WGPU_BACKEND_ENV] = requested
                current = requested

    return PygfxBackendEnvStatus(
        requested_backend=requested or current or "auto",
        selected_backend=current or "auto",
        power_preference=power or "high-performance",
        d3d12_requested=bool(requested),
        restart_required=restart_required,
        fallback_allowed=True,
        reason=reason,
    )
