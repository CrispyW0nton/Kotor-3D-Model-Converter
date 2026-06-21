"""Native C ABI bridge for renderer-neutral core rendering contracts."""

from __future__ import annotations

import ctypes
import os
import platform
from pathlib import Path


_NATIVE_RENDERING_ENV = "GHOSTRIGGER_RENDERING"
_NATIVE_RENDERING_DLL = "GhostRigger.Core.Rendering.dll"
_native_rendering_dll: ctypes.CDLL | None = None
_native_rendering_attempted = False


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _native_rendering_candidates() -> tuple[Path, ...]:
    override = os.environ.get(_NATIVE_RENDERING_ENV)
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override))
    if platform.system().lower() == "windows":
        root = _repo_root()
        candidates.extend(
            [
                root / "build" / "vs" / "x64" / "Release" / _NATIVE_RENDERING_DLL,
                root / "build" / "vs" / "x64" / "Debug" / _NATIVE_RENDERING_DLL,
                root / "native" / "GhostRigger.Core.Rendering.dll" / "bin" / "x64" / "Release" / _NATIVE_RENDERING_DLL,
                root / "native" / "GhostRigger.Core.Rendering.dll" / "bin" / "x64" / "Debug" / _NATIVE_RENDERING_DLL,
            ]
        )
    return tuple(candidates)


def native_rendering() -> ctypes.CDLL | None:
    global _native_rendering_attempted, _native_rendering_dll
    if _native_rendering_attempted:
        return _native_rendering_dll
    _native_rendering_attempted = True
    for candidate in _native_rendering_candidates():
        if not candidate.exists():
            continue
        try:
            dll = ctypes.CDLL(str(candidate))
            dll.gr_rendering_normalize_renderer_backend.argtypes = [ctypes.c_char_p]
            dll.gr_rendering_normalize_renderer_backend.restype = ctypes.c_char_p
            dll.gr_rendering_renderer_backend_label.argtypes = [ctypes.c_char_p]
            dll.gr_rendering_renderer_backend_label.restype = ctypes.c_char_p
            dll.gr_rendering_normalize_display_mode.argtypes = [ctypes.c_char_p]
            dll.gr_rendering_normalize_display_mode.restype = ctypes.c_char_p
            dll.gr_rendering_display_mode_values_json.argtypes = []
            dll.gr_rendering_display_mode_values_json.restype = ctypes.c_char_p
            dll.gr_rendering_normalize_viewport_navigation_profile.argtypes = [ctypes.c_char_p]
            dll.gr_rendering_normalize_viewport_navigation_profile.restype = ctypes.c_char_p
            dll.gr_rendering_viewport_navigation_profile_label.argtypes = [ctypes.c_char_p]
            dll.gr_rendering_viewport_navigation_profile_label.restype = ctypes.c_char_p
            dll.gr_rendering_viewport_navigation_profile_summary.argtypes = [ctypes.c_char_p]
            dll.gr_rendering_viewport_navigation_profile_summary.restype = ctypes.c_char_p
            dll.gr_rendering_hex_to_rgb_float.argtypes = [
                ctypes.c_char_p,
                ctypes.POINTER(ctypes.c_double),
                ctypes.POINTER(ctypes.c_double),
            ]
            dll.gr_rendering_hex_to_rgb_float.restype = ctypes.c_int
        except (AttributeError, OSError):
            continue
        _native_rendering_dll = dll
        return dll
    return None

