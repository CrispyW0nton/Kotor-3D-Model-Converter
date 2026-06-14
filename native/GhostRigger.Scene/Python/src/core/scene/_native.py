"""Native C ABI bridge for scene contracts."""

from __future__ import annotations

import ctypes
import os
import platform
from pathlib import Path


_NATIVE_SCENE_ENV = "GHOSTRIGGER_SCENE"
_NATIVE_SCENE_DLL = "GhostRigger.Scene.dll"
_native_scene_dll: ctypes.CDLL | None = None
_native_scene_attempted = False


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _native_scene_candidates() -> tuple[Path, ...]:
    override = os.environ.get(_NATIVE_SCENE_ENV)
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override))
    if platform.system().lower() == "windows":
        root = _repo_root()
        candidates.extend(
            [
                root / "build" / "vs" / "x64" / "Debug" / _NATIVE_SCENE_DLL,
                root / "build" / "vs" / "x64" / "Release" / _NATIVE_SCENE_DLL,
                root / "build" / "vs" / "Win32" / "Debug" / _NATIVE_SCENE_DLL,
                root / "build" / "vs" / "Win32" / "Release" / _NATIVE_SCENE_DLL,
            ]
        )
    return tuple(candidates)


def native_scene() -> ctypes.CDLL | None:
    global _native_scene_attempted, _native_scene_dll
    if _native_scene_attempted:
        return _native_scene_dll
    _native_scene_attempted = True
    for candidate in _native_scene_candidates():
        if not candidate.exists():
            continue
        try:
            dll = ctypes.CDLL(str(candidate))
            dll.gr_scene_sanitize_vec3.argtypes = [
                ctypes.POINTER(ctypes.c_double),
                ctypes.POINTER(ctypes.c_double),
                ctypes.POINTER(ctypes.c_double),
            ]
            dll.gr_scene_sanitize_vec3.restype = ctypes.c_int
            dll.gr_scene_transform_defaults.argtypes = [
                ctypes.POINTER(ctypes.c_double),
                ctypes.POINTER(ctypes.c_double),
                ctypes.POINTER(ctypes.c_double),
            ]
            dll.gr_scene_transform_defaults.restype = ctypes.c_int
            dll.gr_scene_pivot_defaults.argtypes = [
                ctypes.POINTER(ctypes.c_double),
                ctypes.POINTER(ctypes.c_double),
                ctypes.POINTER(ctypes.c_int),
            ]
            dll.gr_scene_pivot_defaults.restype = ctypes.c_int
            dll.gr_scene_pivot_values_are_valid.argtypes = [
                ctypes.POINTER(ctypes.c_double),
                ctypes.POINTER(ctypes.c_double),
            ]
            dll.gr_scene_pivot_values_are_valid.restype = ctypes.c_int
            dll.gr_scene_sanitize_resource_game.argtypes = [ctypes.c_char_p]
            dll.gr_scene_sanitize_resource_game.restype = ctypes.c_char_p
            dll.gr_scene_metadata_key_is_persisted.argtypes = [ctypes.c_char_p]
            dll.gr_scene_metadata_key_is_persisted.restype = ctypes.c_int
        except (AttributeError, OSError):
            continue
        _native_scene_dll = dll
        return dll
    return None

