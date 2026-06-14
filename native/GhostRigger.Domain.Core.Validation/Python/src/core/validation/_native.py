"""Native C ABI bridge for validation bus contracts."""

from __future__ import annotations

import ctypes
import os
import platform
from pathlib import Path


_NATIVE_VALIDATION_ENV = "GHOSTRIGGER_VALIDATION"
_NATIVE_VALIDATION_DLL = "GhostRigger.Domain.Core.Validation.dll"
_native_validation_dll: ctypes.CDLL | None = None
_native_validation_attempted = False


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _native_validation_candidates() -> tuple[Path, ...]:
    override = os.environ.get(_NATIVE_VALIDATION_ENV)
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override))
    if platform.system().lower() == "windows":
        root = _repo_root()
        candidates.extend(
            [
                root / "build" / "vs" / "x64" / "Release" / _NATIVE_VALIDATION_DLL,
                root / "build" / "vs" / "x64" / "Debug" / _NATIVE_VALIDATION_DLL,
                root / "native" / "GhostRigger.Domain.Core.Validation" / "bin" / "x64" / "Release" / _NATIVE_VALIDATION_DLL,
                root / "native" / "GhostRigger.Domain.Core.Validation" / "bin" / "x64" / "Debug" / _NATIVE_VALIDATION_DLL,
            ]
        )
    return tuple(candidates)


def native_validation() -> ctypes.CDLL | None:
    global _native_validation_attempted, _native_validation_dll
    if _native_validation_attempted:
        return _native_validation_dll
    _native_validation_attempted = True
    for candidate in _native_validation_candidates():
        if not candidate.exists():
            continue
        try:
            dll = ctypes.CDLL(str(candidate))
            dll.gr_validation_severity_rank.argtypes = [ctypes.c_char_p]
            dll.gr_validation_severity_rank.restype = ctypes.c_int
            dll.gr_validation_is_valid_severity.argtypes = [ctypes.c_char_p]
            dll.gr_validation_is_valid_severity.restype = ctypes.c_int
            dll.gr_validation_is_valid_subsystem.argtypes = [ctypes.c_char_p]
            dll.gr_validation_is_valid_subsystem.restype = ctypes.c_int
            dll.gr_validation_severity_values_json.argtypes = []
            dll.gr_validation_severity_values_json.restype = ctypes.c_char_p
            dll.gr_validation_subsystem_values_json.argtypes = []
            dll.gr_validation_subsystem_values_json.restype = ctypes.c_char_p
        except (AttributeError, OSError):
            continue
        _native_validation_dll = dll
        return dll
    return None

