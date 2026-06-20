"""Transform gizmo mode declarations."""

from __future__ import annotations

import ctypes
import json
import os
import platform
from enum import Enum
from pathlib import Path


_Double3 = ctypes.c_double * 3


class GizmoMode(Enum):
    """Viewport transform modes."""

    TRANSLATE = "translate"
    ROTATE = "rotate"
    SCALE = "scale"


TransformGizmoMode = GizmoMode


class TransformSpace(Enum):
    """Coordinate space for gizmo axes."""

    WORLD = "world"
    LOCAL = "local"


_NATIVE_GIZMO_ENV = "GHOSTRIGGER_GIZMO"
_NATIVE_GIZMO_DLL = "GhostRigger.Core.GUI.Helpers.Gizmo.dll"
_native_gizmo_dll = None
_native_gizmo_attempted = False


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _native_gizmo_candidates() -> tuple[Path, ...]:
    override = os.environ.get(_NATIVE_GIZMO_ENV, "").strip()
    if override:
        return (Path(override),)
    root = _repo_root()
    return (
        root / "build" / "vs" / "x64" / "Debug" / _NATIVE_GIZMO_DLL,
        root / "build" / "vs" / "x64" / "Release" / _NATIVE_GIZMO_DLL,
        root / "build" / "vs" / "Win32" / "Debug" / _NATIVE_GIZMO_DLL,
        root / "build" / "vs" / "Win32" / "Release" / _NATIVE_GIZMO_DLL,
        root / "native" / "GhostRigger.Core.GUI.Helpers.Gizmo" / "build" / "vs" / "x64" / "Debug" / _NATIVE_GIZMO_DLL,
        root / "native" / "GhostRigger.Core.GUI.Helpers.Gizmo" / "build" / "vs" / "x64" / "Release" / _NATIVE_GIZMO_DLL,
    )


def _native_gizmo():
    global _native_gizmo_attempted, _native_gizmo_dll
    if platform.system() != "Windows":
        return None
    if _native_gizmo_attempted:
        return _native_gizmo_dll
    _native_gizmo_attempted = True
    existing = [path for path in _native_gizmo_candidates() if path.exists()]
    if not existing:
        return None
    try:
        dll = ctypes.CDLL(str(existing[0]))
        dll.gr_gizmo_normalize_mode.argtypes = [ctypes.c_char_p]
        dll.gr_gizmo_normalize_mode.restype = ctypes.c_char_p
        dll.gr_gizmo_cycle_mode.argtypes = [ctypes.c_char_p]
        dll.gr_gizmo_cycle_mode.restype = ctypes.c_char_p
        dll.gr_gizmo_mode_values_json.argtypes = []
        dll.gr_gizmo_mode_values_json.restype = ctypes.c_char_p
        dll.gr_gizmo_normalize_transform_space.argtypes = [ctypes.c_char_p]
        dll.gr_gizmo_normalize_transform_space.restype = ctypes.c_char_p
        dll.gr_gizmo_transform_space_values_json.argtypes = []
        dll.gr_gizmo_transform_space_values_json.restype = ctypes.c_char_p
        dll.gr_gizmo_resolve_origin.argtypes = [
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_double),
        ]
        dll.gr_gizmo_resolve_origin.restype = ctypes.c_int
    except Exception:
        return None
    _native_gizmo_dll = dll
    return _native_gizmo_dll


def _python_normalize_gizmo_mode(mode: GizmoMode | str | None) -> GizmoMode:
    if isinstance(mode, GizmoMode):
        return mode
    try:
        return GizmoMode(str(mode or "").lower())
    except ValueError:
        return GizmoMode.TRANSLATE


def normalize_gizmo_mode(mode: GizmoMode | str | None) -> GizmoMode:
    dll = _native_gizmo()
    if dll is not None:
        try:
            raw = dll.gr_gizmo_normalize_mode(str(mode.value if isinstance(mode, GizmoMode) else mode or "").encode("utf-8"))
            return GizmoMode((raw or b"translate").decode("utf-8", errors="replace"))
        except Exception:
            pass
    return _python_normalize_gizmo_mode(mode)


def _python_cycle_gizmo_mode(mode: GizmoMode | str | None) -> GizmoMode:
    order = (GizmoMode.TRANSLATE, GizmoMode.ROTATE, GizmoMode.SCALE)
    current = _python_normalize_gizmo_mode(mode)
    return order[(order.index(current) + 1) % len(order)]


def cycle_gizmo_mode(mode: GizmoMode | str | None) -> GizmoMode:
    dll = _native_gizmo()
    if dll is not None:
        try:
            raw = dll.gr_gizmo_cycle_mode(str(mode.value if isinstance(mode, GizmoMode) else mode or "").encode("utf-8"))
            return GizmoMode((raw or b"translate").decode("utf-8", errors="replace"))
        except Exception:
            pass
    return _python_cycle_gizmo_mode(mode)


def gizmo_mode_values() -> tuple[str, ...]:
    dll = _native_gizmo()
    if dll is not None:
        try:
            values = json.loads((dll.gr_gizmo_mode_values_json() or b"[]").decode("utf-8", errors="replace"))
            if isinstance(values, list) and all(isinstance(value, str) for value in values):
                return tuple(values)
        except Exception:
            pass
    return tuple(mode.value for mode in GizmoMode)


def _python_normalize_transform_space(space: TransformSpace | str | None) -> TransformSpace:
    if isinstance(space, TransformSpace):
        return space
    try:
        return TransformSpace(str(space or "").lower())
    except ValueError:
        return TransformSpace.WORLD


def normalize_transform_space(space: TransformSpace | str | None) -> TransformSpace:
    dll = _native_gizmo()
    if dll is not None:
        try:
            raw = dll.gr_gizmo_normalize_transform_space(
                str(space.value if isinstance(space, TransformSpace) else space or "").encode("utf-8")
            )
            return TransformSpace((raw or b"world").decode("utf-8", errors="replace"))
        except Exception:
            pass
    return _python_normalize_transform_space(space)


def transform_space_values() -> tuple[str, ...]:
    dll = _native_gizmo()
    if dll is not None:
        try:
            values = json.loads((dll.gr_gizmo_transform_space_values_json() or b"[]").decode("utf-8", errors="replace"))
            if isinstance(values, list) and all(isinstance(value, str) for value in values):
                return tuple(values)
        except Exception:
            pass
    return tuple(space.value for space in TransformSpace)


def _tuple3_or_none(value) -> tuple[float, float, float] | None:
    if value is None:
        return None
    try:
        values = tuple(float(v) for v in tuple(value)[:3])
    except Exception:
        return None
    if len(values) != 3 or any(v != v or v in (float("inf"), float("-inf")) for v in values):
        return None
    return values


def _double3(value: tuple[float, float, float] | None) -> _Double3:
    safe = value or (0.0, 0.0, 0.0)
    return _Double3(float(safe[0]), float(safe[1]), float(safe[2]))


def _python_resolve_gizmo_origin(
    position,
    pivot_world=None,
    gizmo_world=None,
    *,
    is_helper_object: bool = False,
    affect_pivot_only: bool = False,
) -> tuple[float, float, float]:
    position_value = _tuple3_or_none(position) or (0.0, 0.0, 0.0)
    pivot_value = _tuple3_or_none(pivot_world)
    gizmo_value = _tuple3_or_none(gizmo_world)
    if bool(is_helper_object) and not bool(affect_pivot_only):
        return gizmo_value or position_value
    return pivot_value or gizmo_value or position_value


def resolve_gizmo_origin(
    position,
    pivot_world=None,
    gizmo_world=None,
    *,
    is_helper_object: bool = False,
    affect_pivot_only: bool = False,
) -> tuple[float, float, float]:
    """Resolve the world-space gizmo origin from object, pivot, and helper candidates."""
    position_value = _tuple3_or_none(position) or (0.0, 0.0, 0.0)
    pivot_value = _tuple3_or_none(pivot_world)
    gizmo_value = _tuple3_or_none(gizmo_world)
    dll = _native_gizmo()
    if dll is not None:
        try:
            out = _Double3()
            ok = dll.gr_gizmo_resolve_origin(
                _double3(position_value),
                _double3(pivot_value),
                _double3(gizmo_value),
                int(pivot_value is not None),
                int(gizmo_value is not None),
                int(bool(is_helper_object)),
                int(bool(affect_pivot_only)),
                out,
            )
            if ok:
                return (float(out[0]), float(out[1]), float(out[2]))
        except Exception:
            pass
    return _python_resolve_gizmo_origin(
        position_value,
        pivot_value,
        gizmo_value,
        is_helper_object=is_helper_object,
        affect_pivot_only=affect_pivot_only,
    )
