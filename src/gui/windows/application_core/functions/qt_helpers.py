"""Qt helper functions for application-core windows."""

from __future__ import annotations

from typing import Optional

try:
    from PySide6 import QtCore, QtGui
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

try:
    import shiboken6
except Exception:  # pragma: no cover - defensive fallback for unusual PySide installs
    shiboken6 = None

from src.core.rendering.renderer_backend import RendererBackend
from src.core.rendering.renderer_settings import RendererSettings

_WGPU_BACKEND_TYPES = {
    RendererBackend.WGPU_D3D12.value: "D3D12",
    RendererBackend.WGPU_VULKAN.value: "Vulkan",
    RendererBackend.WGPU_OPENGL.value: "OpenGL",
    RendererBackend.PYGFX_WGPU.value: "D3D12",
}

def _wgpu_backend_type(backend_id: object) -> str:
    return _WGPU_BACKEND_TYPES.get(str(backend_id or ""), "")

def _wgpu_backend_restart_required(
    old_settings: RendererSettings,
    new_settings: RendererSettings,
) -> bool:
    old_type = _wgpu_backend_type(old_settings.backend.value)
    new_type = _wgpu_backend_type(new_settings.backend.value)
    return bool(old_type and new_type and old_type != new_type)

def _primary_screen_available_geometry() -> Optional[QtCore.QRect]:
    screen = QtGui.QGuiApplication.primaryScreen()
    if screen is None:
        screens = QtGui.QGuiApplication.screens()
        screen = screens[0] if screens else None
    if screen is None:
        return None
    return QtCore.QRect(screen.availableGeometry())

def _qt_object_alive(obj) -> bool:
    if obj is None:
        return False
    if shiboken6 is not None:
        try:
            return bool(shiboken6.isValid(obj))
        except Exception:
            return False
    try:
        obj.objectName()
    except RuntimeError:
        return False
    except Exception:
        return True
    return True
