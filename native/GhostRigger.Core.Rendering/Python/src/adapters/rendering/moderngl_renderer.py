"""ModernGL/OpenGL 3.3 renderer adapter."""

from __future__ import annotations

import ctypes
import json
import os
import platform
from pathlib import Path

from src.adapters.rendering.moderngl_legacy_bridge import GpuRenderer, moderngl_runtime_available
from src.core.rendering.renderer_backend import RendererBackend
from src.core.rendering.renderer_capabilities import MODERNGL_DISPLAY_MODES, RendererCapabilities


_NATIVE_MODERNGL_ENV = "GHOSTRIGGER_RENDERER_MODERNGL"
_NATIVE_MODERNGL_DLLS = (
    "GhostRigger.Core.Rendering.dll",
    "GhostRigger.Core.Rendering.dll",
    "GhostRigger.Core.Rendering.dll",
    "GhostRigger.Core.Rendering.dll",
)
_native_moderngl_dll: ctypes.CDLL | None = None
_native_moderngl_attempted = False


class ModernGLRenderer(GpuRenderer):
    """Adapter that keeps the existing ModernGL renderer behavior intact."""

    name = "ModernGL"
    backend_id = RendererBackend.MODERNGL_GL330.value

    def is_available(self) -> bool:
        try:
            return moderngl_runtime_available()
        except Exception:
            return False

    def get_capabilities(self) -> RendererCapabilities:
        available = self.is_available()
        return RendererCapabilities(
            backend_id=self.backend_id,
            name=self.name,
            available=available,
            reason="" if available else "moderngl or numpy is not installed",
            api="OpenGL 3.3",
            supports_scene_meshes=True,
            supports_textures=True,
            supports_grid=True,
            supports_overlays=True,
            supports_hot_switch=True,
            supports_object_picking=True,
            supports_cpu_ray_picking=True,
            supports_gpu_id_picking=False,
            supports_selection_highlight=True,
            supports_gizmo_drawing=True,
            supports_gizmo_interaction=True,
            supports_marquee_selection=True,
            supports_subobject_selection=True,
            supported_display_modes=MODERNGL_DISPLAY_MODES,
            supported_display_options=(
                "show_grid",
                "show_wire_overlay",
                "show_edged_faces",
                "show_textures",
                "show_lightmaps",
                "show_material_colour",
                "show_alpha",
                "two_sided",
                "force_unlit",
                "force_flat_colour",
            ),
        )

    def create_surface_widget(self, parent=None):
        from PySide6 import QtCore, QtWidgets

        widget = QtWidgets.QLabel("Empty Scene", parent)
        widget.setObjectName("ModernGLViewportSurface")
        widget.setAlignment(QtCore.Qt.AlignCenter)
        widget.setMinimumSize(120, 100)
        widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        widget.setFocusPolicy(QtCore.Qt.StrongFocus)
        widget.setMouseTracking(True)
        widget.setScaledContents(False)
        return widget

    def shutdown(self) -> None:
        self.release()

    def get_diagnostics(self) -> dict:
        global _native_moderngl_attempted, _native_moderngl_dll
        ctx = getattr(self, "_ctx", None)
        perf = dict(getattr(self, "perf", {}) or {})
        info = getattr(ctx, "info", {}) if ctx is not None else {}
        version_code = getattr(ctx, "version_code", None)
        gpu = info.get("GL_RENDERER") if ctx is not None else None
        vendor = info.get("GL_VENDOR") if ctx is not None else None
        mesh_cache_size = len(getattr(self, "_mesh_cache", {}) or {})
        texture_cache_size = len(getattr(getattr(self, "_tex_cache", None), "_cache", {}) or {})
        viewport_display = getattr(getattr(self, "display_options", None), "diagnostics", lambda: {})()
        try:
            frame_time_ms = float(perf.get("last_frame_ms") or 0.0)
        except (TypeError, ValueError):
            frame_time_ms = 0.0
        try:
            upload_ms = float(perf.get("gpu_upload_ms") or 0.0)
        except (TypeError, ValueError):
            upload_ms = 0.0
        try:
            draw_ms = float(perf.get("draw_ms") or 0.0)
        except (TypeError, ValueError):
            draw_ms = 0.0
        try:
            readback_ms = float(perf.get("readback_ms") or 0.0)
        except (TypeError, ValueError):
            readback_ms = 0.0
        try:
            triangle_count = int(perf.get("tri_count") or 0)
        except (TypeError, ValueError):
            triangle_count = 0
        try:
            version_number = int(version_code or 0) if version_code is not None else -1
        except (TypeError, ValueError):
            version_number = -1

        if not _native_moderngl_attempted and platform.system().lower() == "windows":
            _native_moderngl_attempted = True
            candidates: list[Path] = []
            override = os.environ.get(_NATIVE_MODERNGL_ENV)
            if override:
                candidates.append(Path(override))
            root = Path(__file__).resolve().parents[3]
            for dll_name in _NATIVE_MODERNGL_DLLS:
                candidates.extend(
                    [
                        root / "build" / "vs" / "x64" / "Release" / dll_name,
                        root / "build" / "vs" / "x64" / "Debug" / dll_name,
                    ]
                )
            for candidate in candidates:
                if not candidate.exists():
                    continue
                try:
                    dll = ctypes.CDLL(str(candidate))
                    dll.gr_renderer_moderngl_frame_diagnostics_json.argtypes = [
                        ctypes.c_int,
                        ctypes.c_int,
                        ctypes.c_char_p,
                        ctypes.c_char_p,
                        ctypes.c_double,
                        ctypes.c_double,
                        ctypes.c_double,
                        ctypes.c_double,
                        ctypes.c_int,
                        ctypes.c_int,
                        ctypes.c_int,
                    ]
                    dll.gr_renderer_moderngl_frame_diagnostics_json.restype = ctypes.c_char_p
                except (AttributeError, OSError):
                    continue
                _native_moderngl_dll = dll
                break

        if _native_moderngl_dll is not None:
            try:
                raw = _native_moderngl_dll.gr_renderer_moderngl_frame_diagnostics_json(
                    int(bool(getattr(self, "_gpu_available", False))),
                    version_number,
                    str(gpu or "").encode("utf-8", errors="replace"),
                    str(vendor or "").encode("utf-8", errors="replace"),
                    frame_time_ms,
                    upload_ms,
                    draw_ms,
                    readback_ms,
                    triangle_count,
                    mesh_cache_size,
                    texture_cache_size,
                )
                diagnostics = json.loads((raw or b"{}").decode("utf-8", errors="replace"))
                diagnostics["name"] = self.name
                diagnostics["backend_id"] = self.backend_id
                diagnostics["viewport_display"] = viewport_display
                return diagnostics
            except Exception:
                pass

        return {
            "name": self.name,
            "backend_id": self.backend_id,
            "available": bool(getattr(self, "_gpu_available", False)),
            "api": "OpenGL",
            "backend": "ModernGL",
            "viewport_display": viewport_display,
            "mature_material_path": True,
            "version_code": version_code,
            "gpu": gpu,
            "vendor": vendor,
            "performance": {
                "frame_time_ms": round(frame_time_ms, 3),
                "upload_ms": round(upload_ms, 3),
                "draw_ms": round(draw_ms, 3),
                "readback_ms": round(readback_ms, 3),
            },
            "triangle_count": triangle_count,
            "mesh_cache_size": mesh_cache_size,
            "texture_cache_size": texture_cache_size,
        }
