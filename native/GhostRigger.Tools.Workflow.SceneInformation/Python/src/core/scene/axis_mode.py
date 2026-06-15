"""Transform reference coordinate-system support for GhostRigger scenes."""

from __future__ import annotations

import ctypes
from enum import Enum
import json
import math
import os
import platform
from pathlib import Path
from typing import Any, Iterable

Matrix3 = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
Vec3 = tuple[float, float, float]
_Double9 = ctypes.c_double * 9
_Double4 = ctypes.c_double * 4
_NATIVE_SCENE_ENV = "GHOSTRIGGER_SCENE"
_NATIVE_SCENE_DLL = "GhostRigger.Domain.Core.Scene.dll"
_native_scene_dll = None
_native_scene_attempted = False


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _native_scene_candidates() -> tuple[Path, ...]:
    override = os.environ.get(_NATIVE_SCENE_ENV, "").strip()
    if override:
        return (Path(override),)
    root = _repo_root()
    return (
        root / "build" / "vs" / "x64" / "Debug" / _NATIVE_SCENE_DLL,
        root / "build" / "vs" / "x64" / "Release" / _NATIVE_SCENE_DLL,
        root / "build" / "vs" / "Win32" / "Debug" / _NATIVE_SCENE_DLL,
        root / "build" / "vs" / "Win32" / "Release" / _NATIVE_SCENE_DLL,
        root / "native" / "GhostRigger.Domain.Core.Scene" / "build" / "vs" / "x64" / "Debug" / _NATIVE_SCENE_DLL,
        root / "native" / "GhostRigger.Domain.Core.Scene" / "build" / "vs" / "x64" / "Release" / _NATIVE_SCENE_DLL,
    )


def _native_scene():
    global _native_scene_attempted, _native_scene_dll
    if platform.system() != "Windows":
        return None
    if _native_scene_attempted:
        return _native_scene_dll
    _native_scene_attempted = True
    existing = [path for path in _native_scene_candidates() if path.exists()]
    if not existing:
        return None
    try:
        dll = ctypes.CDLL(str(existing[0]))
        dll.gr_scene_normalize_axis_mode.argtypes = [ctypes.c_char_p]
        dll.gr_scene_normalize_axis_mode.restype = ctypes.c_char_p
        dll.gr_scene_axis_mode_label.argtypes = [ctypes.c_char_p]
        dll.gr_scene_axis_mode_label.restype = ctypes.c_char_p
        dll.gr_scene_axis_mode_values_json.argtypes = []
        dll.gr_scene_axis_mode_values_json.restype = ctypes.c_char_p
        dll.gr_scene_identity_basis.argtypes = [ctypes.POINTER(ctypes.c_double)]
        dll.gr_scene_identity_basis.restype = ctypes.c_int
        dll.gr_scene_finite_basis.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]
        dll.gr_scene_finite_basis.restype = ctypes.c_int
        dll.gr_scene_quat_to_basis.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]
        dll.gr_scene_quat_to_basis.restype = ctypes.c_int
    except Exception:
        return None
    _native_scene_dll = dll
    return _native_scene_dll


def _basis_from_flat(values: _Double9) -> Matrix3:
    return (
        (values[0], values[1], values[2]),
        (values[3], values[4], values[5]),
        (values[6], values[7], values[8]),
    )


class AxisMode(Enum):
    VIEW = "view"
    SCREEN = "screen"
    WORLD = "world"
    PARENT = "parent"
    LOCAL = "local"
    GIMBAL = "gimbal"
    GRID = "grid"
    WORKING = "working"
    PICK = "pick"

    @property
    def label(self) -> str:
        dll = _native_scene()
        if dll is not None:
            try:
                raw = dll.gr_scene_axis_mode_label(self.value.encode("utf-8"))
                return (raw or self.value.title().encode("utf-8")).decode("utf-8", errors="replace")
            except Exception:
                pass
        return self.value.title()

    @classmethod
    def from_value(cls, value: Any) -> "AxisMode":
        if isinstance(value, AxisMode):
            return value
        dll = _native_scene()
        if dll is not None:
            try:
                raw = dll.gr_scene_normalize_axis_mode(str(value or "").encode("utf-8"))
                return cls((raw or cls.WORLD.value.encode("utf-8")).decode("utf-8", errors="replace"))
            except Exception:
                pass
        text = str(value or "").strip().lower()
        for mode in cls:
            if mode.value == text or mode.name.lower() == text:
                return mode
        return cls.WORLD


def _python_axis_mode_label(mode: AxisMode) -> str:
    return mode.value.title()


def _python_axis_mode_from_value(value: Any) -> AxisMode:
    if isinstance(value, AxisMode):
        return value
    text = str(value or "").strip().lower()
    for mode in AxisMode:
        if mode.value == text or mode.name.lower() == text:
            return mode
    return AxisMode.WORLD


def axis_mode_values() -> tuple[str, ...]:
    dll = _native_scene()
    if dll is not None:
        try:
            values = json.loads((dll.gr_scene_axis_mode_values_json() or b"[]").decode("utf-8", errors="replace"))
            if isinstance(values, list) and all(isinstance(value, str) for value in values):
                return tuple(values)
        except Exception:
            pass
    return tuple(mode.value for mode in AxisMode)


IDENTITY_BASIS: Matrix3 = (
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
)


def _finite_basis(basis: Iterable[Iterable[float]] | None) -> Matrix3:
    dll = _native_scene()
    if dll is not None:
        try:
            rows = [tuple(float(v) for v in row[:3]) for row in basis]  # type: ignore[index]
            flat = _Double9(*(value for row in rows[:3] for value in row))
            out = _Double9()
            if dll.gr_scene_finite_basis(flat, out) == 1:
                return _basis_from_flat(out)
        except Exception:
            pass
    try:
        rows = [tuple(float(v) for v in row[:3]) for row in basis]  # type: ignore[index]
        if len(rows) >= 3 and all(len(row) == 3 and all(math.isfinite(v) for v in row) for row in rows[:3]):
            return (rows[0], rows[1], rows[2])
    except Exception:
        pass
    return IDENTITY_BASIS


def _python_finite_basis(basis: Iterable[Iterable[float]] | None) -> Matrix3:
    try:
        rows = [tuple(float(v) for v in row[:3]) for row in basis]  # type: ignore[index]
        if len(rows) >= 3 and all(len(row) == 3 and all(math.isfinite(v) for v in row) for row in rows[:3]):
            return (rows[0], rows[1], rows[2])
    except Exception:
        pass
    return IDENTITY_BASIS


def _normalize(vec: Iterable[float], fallback: Vec3) -> Vec3:
    try:
        x, y, z = (float(v) for v in tuple(vec)[:3])
        length = math.sqrt(x * x + y * y + z * z)
        if length > 1e-9 and math.isfinite(length):
            return (x / length, y / length, z / length)
    except Exception:
        pass
    return fallback


def _quat_to_basis(quat: Iterable[float] | None) -> Matrix3:
    dll = _native_scene()
    if dll is not None:
        try:
            values = tuple(float(v) for v in tuple(quat or (0.0, 0.0, 0.0, 1.0))[:4])
            out = _Double9()
            if dll.gr_scene_quat_to_basis(_Double4(*values), out) == 1:
                return _basis_from_flat(out)
        except Exception:
            pass
    try:
        x, y, z, w = (float(v) for v in tuple(quat or (0.0, 0.0, 0.0, 1.0))[:4])
    except Exception:
        return IDENTITY_BASIS
    length = math.sqrt(x * x + y * y + z * z + w * w)
    if length <= 1e-9 or not math.isfinite(length):
        return IDENTITY_BASIS
    x, y, z, w = x / length, y / length, z / length, w / length
    return (
        (1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y + z * w), 2.0 * (x * z - y * w)),
        (2.0 * (x * y - z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z + x * w)),
        (2.0 * (x * z + y * w), 2.0 * (y * z - x * w), 1.0 - 2.0 * (x * x + y * y)),
    )


def _python_quat_to_basis(quat: Iterable[float] | None) -> Matrix3:
    try:
        x, y, z, w = (float(v) for v in tuple(quat or (0.0, 0.0, 0.0, 1.0))[:4])
    except Exception:
        return IDENTITY_BASIS
    length = math.sqrt(x * x + y * y + z * z + w * w)
    if length <= 1e-9 or not math.isfinite(length):
        return IDENTITY_BASIS
    x, y, z, w = x / length, y / length, z / length, w / length
    return (
        (1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y + z * w), 2.0 * (x * z - y * w)),
        (2.0 * (x * y - z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z + x * w)),
        (2.0 * (x * z + y * w), 2.0 * (y * z - x * w), 1.0 - 2.0 * (x * x + y * y)),
    )


def _camera_basis(camera: Any) -> Matrix3:
    try:
        right, up, fwd, _eye = camera._view_matrix()
        return (
            _normalize(right, (1.0, 0.0, 0.0)),
            _normalize(up, (0.0, 1.0, 0.0)),
            _normalize(fwd, (0.0, 0.0, 1.0)),
        )
    except Exception:
        return IDENTITY_BASIS


class TransformReferenceController:
    """Central state and fallback policy for viewport transform reference axes."""

    def __init__(self, axis_mode: AxisMode | str = AxisMode.WORLD) -> None:
        self._axis_mode = AxisMode.from_value(axis_mode)
        self._pick_reference: Any = None
        self._working_basis: Matrix3 | None = None

    def set_axis_mode(self, mode: AxisMode | str) -> AxisMode:
        self._axis_mode = AxisMode.from_value(mode)
        if self._axis_mode is not AxisMode.PICK:
            self.clear_pick_reference()
        return self._axis_mode

    def get_axis_mode(self) -> AxisMode:
        return self._axis_mode

    def get_transform_basis(self, selected_object: Any = None, camera: Any = None, scene: Any = None) -> Matrix3:
        mode = self._axis_mode
        if mode in {AxisMode.VIEW, AxisMode.SCREEN}:
            return _camera_basis(camera)
        if mode in {AxisMode.LOCAL, AxisMode.GIMBAL}:
            return self._object_basis(selected_object)
        if mode is AxisMode.PARENT:
            parent = getattr(selected_object, "parent", None)
            if parent is not None:
                return self._object_basis(parent)
            return IDENTITY_BASIS
        if mode is AxisMode.PICK:
            if self._reference_is_deleted(scene):
                self.clear_pick_reference()
                return IDENTITY_BASIS
            return self._object_basis(self._pick_reference)
        if mode is AxisMode.WORKING:
            return _finite_basis(self._working_basis)
        return IDENTITY_BASIS

    def get_gizmo_orientation(self, selected_object: Any = None, camera: Any = None, scene: Any = None) -> Matrix3:
        return self.get_transform_basis(selected_object, camera, scene)

    def resolve_pick_reference(self, target_object: Any) -> None:
        self._pick_reference = target_object
        self._axis_mode = AxisMode.PICK

    def clear_pick_reference(self) -> None:
        self._pick_reference = None

    def picked_reference(self) -> Any:
        return self._pick_reference

    def set_working_basis(self, basis: Iterable[Iterable[float]] | None) -> None:
        self._working_basis = _finite_basis(basis) if basis is not None else None

    def _object_basis(self, obj: Any) -> Matrix3:
        if obj is None:
            return IDENTITY_BASIS
        reference_rotation = getattr(obj, "_gr_reference_rotation", None)
        if reference_rotation is not None:
            return _quat_to_basis(reference_rotation)
        basis = getattr(obj, "_gr_axis_basis", None)
        if basis is not None:
            return _finite_basis(basis)
        return _quat_to_basis(getattr(obj, "rotation", None))

    def _reference_is_deleted(self, scene: Any) -> bool:
        if self._pick_reference is None or scene is None:
            return False
        target_id = getattr(self._pick_reference, "_gr_scene_object_id", None)
        if not target_id:
            return False
        try:
            objects = scene.get_scene_objects() if hasattr(scene, "get_scene_objects") else scene.objects
            return not any(getattr(obj, "id", None) == target_id for obj in objects)
        except Exception:
            return False
