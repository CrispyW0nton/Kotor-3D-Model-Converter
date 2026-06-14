"""Native C ABI bridge for core template utility contracts."""

from __future__ import annotations

import ctypes
import os
import platform
from pathlib import Path


_NATIVE_TEMPLATES_ENV = "GHOSTRIGGER_TEMPLATES"
_NATIVE_TEMPLATES_DLL = "GhostRigger.Templates.dll"
_native_templates_dll: ctypes.CDLL | None = None
_native_templates_attempted = False


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _native_templates_candidates() -> tuple[Path, ...]:
    override = os.environ.get(_NATIVE_TEMPLATES_ENV)
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override))
    if platform.system().lower() == "windows":
        root = _repo_root()
        candidates.extend(
            [
                root / "build" / "vs" / "x64" / "Release" / _NATIVE_TEMPLATES_DLL,
                root / "build" / "vs" / "x64" / "Debug" / _NATIVE_TEMPLATES_DLL,
                root / "native" / "GhostRigger.Templates" / "bin" / "x64" / "Release" / _NATIVE_TEMPLATES_DLL,
                root / "native" / "GhostRigger.Templates" / "bin" / "x64" / "Debug" / _NATIVE_TEMPLATES_DLL,
            ]
        )
    return tuple(candidates)


def native_templates() -> ctypes.CDLL | None:
    global _native_templates_attempted, _native_templates_dll
    if _native_templates_attempted:
        return _native_templates_dll
    _native_templates_attempted = True
    for candidate in _native_templates_candidates():
        if not candidate.exists():
            continue
        try:
            dll = ctypes.CDLL(str(candidate))
            dll.gr_templates_normalize_game_version.argtypes = [ctypes.c_char_p]
            dll.gr_templates_normalize_game_version.restype = ctypes.c_char_p
            dll.gr_templates_humanoid_bone_count.argtypes = [ctypes.c_char_p]
            dll.gr_templates_humanoid_bone_count.restype = ctypes.c_int
            dll.gr_templates_humanoid_animation_slot_count.argtypes = [ctypes.c_char_p]
            dll.gr_templates_humanoid_animation_slot_count.restype = ctypes.c_int
            dll.gr_templates_humanoid_rig_source.argtypes = [ctypes.c_char_p]
            dll.gr_templates_humanoid_rig_source.restype = ctypes.c_char_p
            dll.gr_templates_detect_twoda_format.argtypes = [ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint]
            dll.gr_templates_detect_twoda_format.restype = ctypes.c_char_p
            dll.gr_templates_twoda_cell_or_default.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
            dll.gr_templates_twoda_cell_or_default.restype = ctypes.c_char_p
            dll.gr_templates_split_twoda_line_json.argtypes = [ctypes.c_char_p]
            dll.gr_templates_split_twoda_line_json.restype = ctypes.c_char_p
        except (AttributeError, OSError):
            continue
        _native_templates_dll = dll
        return dll
    return None

