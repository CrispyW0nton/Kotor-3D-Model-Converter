from __future__ import annotations

import ctypes
import json
import math
from pathlib import Path

from src.core.scene import axis_mode


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "native" / "GhostRigger.Scene"
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Scene.dll"


Double9 = ctypes.c_double * 9
Double4 = ctypes.c_double * 4


def _load_scene_dll() -> ctypes.CDLL:
    dll = ctypes.CDLL(str(DLL_PATH))
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
    dll.gr_scene_capabilities_json.argtypes = []
    dll.gr_scene_capabilities_json.restype = ctypes.c_char_p
    dll.gr_scene_axis_mode_contracts_schema_json.argtypes = []
    dll.gr_scene_axis_mode_contracts_schema_json.restype = ctypes.c_char_p
    return dll


def _matrix_from_flat(values: Double9) -> axis_mode.Matrix3:
    return (
        (values[0], values[1], values[2]),
        (values[3], values[4], values[5]),
        (values[6], values[7], values[8]),
    )


def _assert_matrix_close(actual: axis_mode.Matrix3, expected: axis_mode.Matrix3) -> None:
    for actual_row, expected_row in zip(actual, expected):
        for actual_value, expected_value in zip(actual_row, expected_row):
            assert math.isclose(actual_value, expected_value, rel_tol=1.0e-9, abs_tol=1.0e-9)


def test_scene_project_declares_axis_mode_files_and_exports() -> None:
    project = (PROJECT_DIR / "GhostRigger.Scene.vcxproj").read_text(encoding="utf-8")
    filters = (PROJECT_DIR / "GhostRigger.Scene.vcxproj.filters").read_text(encoding="utf-8")
    package_header = (PROJECT_DIR / "Public" / "GhostRiggerScene.h").read_text(encoding="utf-8")
    public_header = (PROJECT_DIR / "Public" / "AxisMode.h").read_text(encoding="utf-8")
    implementation = (PROJECT_DIR / "Private" / "AxisMode.cpp").read_text(encoding="utf-8")

    assert '<ClInclude Include="Public\\AxisMode.h" />' in project
    assert '<ClCompile Include="Private\\AxisMode.cpp" />' in project
    assert '<Filter>Public</Filter>' in filters
    assert '<Filter>Private</Filter>' in filters
    assert "gr_scene_normalize_axis_mode" in package_header
    assert "namespace ghostrigger::scene::core::scene::axis_mode" in public_header
    assert "namespace ghostrigger::scene::core::scene::axis_mode" in implementation
    assert "phase15" not in public_header
    assert "pyfn_" not in implementation
    assert "using namespace" not in implementation


def test_native_axis_mode_values_labels_and_fallback_match_python() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_scene_dll()

    for value in ["view", "SCREEN", "world", "parent", "local", "gimbal", "grid", "working", "pick", "", "bogus"]:
        expected = axis_mode._python_axis_mode_from_value(value)
        actual = dll.gr_scene_normalize_axis_mode(value.encode("utf-8")).decode("utf-8")
        label = dll.gr_scene_axis_mode_label(value.encode("utf-8")).decode("utf-8")
        assert actual == expected.value
        assert label == axis_mode._python_axis_mode_label(expected)

    native_values = json.loads(dll.gr_scene_axis_mode_values_json().decode("utf-8"))
    assert tuple(native_values) == tuple(mode.value for mode in axis_mode.AxisMode)


def test_native_axis_basis_math_matches_python() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_scene_dll()

    identity_out = Double9()
    assert dll.gr_scene_identity_basis(identity_out) == 1
    _assert_matrix_close(_matrix_from_flat(identity_out), axis_mode.IDENTITY_BASIS)

    valid = Double9(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0)
    finite_out = Double9()
    assert dll.gr_scene_finite_basis(valid, finite_out) == 1
    assert _matrix_from_flat(finite_out) == ((1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0))

    invalid = Double9(1.0, 2.0, 3.0, math.inf, 5.0, 6.0, 7.0, 8.0, 9.0)
    invalid_out = Double9()
    assert dll.gr_scene_finite_basis(invalid, invalid_out) == 1
    _assert_matrix_close(_matrix_from_flat(invalid_out), axis_mode.IDENTITY_BASIS)


def test_native_quat_to_basis_matches_python_transform_controller_local_basis() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_scene_dll()

    for quat in [
        (0.0, 0.0, 0.70710678, 0.70710678),
        (0.0, 0.70710678, 0.0, 0.70710678),
        (0.0, 0.0, 0.0, 0.0),
    ]:
        selected = type("Selected", (), {"rotation": quat})()
        controller = axis_mode.TransformReferenceController(axis_mode.AxisMode.LOCAL)
        expected = axis_mode._python_quat_to_basis(quat)

        out = Double9()
        assert dll.gr_scene_quat_to_basis(Double4(*quat), out) == 1
        _assert_matrix_close(_matrix_from_flat(out), expected)


def test_native_axis_mode_capabilities_document_python_fallback_scope() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_scene_dll()

    capabilities = json.loads(dll.gr_scene_capabilities_json().decode("utf-8"))
    schema = json.loads(dll.gr_scene_axis_mode_contracts_schema_json().decode("utf-8"))

    assert capabilities["native_implementation_enabled"] is True
    assert capabilities["python_fallback_required"] is True
    assert "axis_mode_contracts" in capabilities["capabilities"]
    assert "AxisMode normalization" in schema["native_scope"]
    assert "TransformReferenceController object ownership" in schema["python_fallback"]


def test_python_axis_mode_helpers_prefer_native_scene_contract(monkeypatch) -> None:
    class _NativeSceneProbe:
        def gr_scene_normalize_axis_mode(self, value: bytes) -> bytes:
            return b"local"

        def gr_scene_axis_mode_label(self, value: bytes) -> bytes:
            return b"Native Local"

        def gr_scene_axis_mode_values_json(self) -> bytes:
            return b'["native-world","native-local"]'

    monkeypatch.setattr(axis_mode, "_native_scene", lambda: _NativeSceneProbe())

    assert axis_mode.AxisMode.from_value("anything") is axis_mode.AxisMode.LOCAL
    assert axis_mode.AxisMode.LOCAL.label == "Native Local"
    assert axis_mode.axis_mode_values() == ("native-world", "native-local")


def test_python_axis_mode_helpers_fall_back_when_native_scene_missing(monkeypatch) -> None:
    monkeypatch.setattr(axis_mode, "_native_scene", lambda: None)

    assert axis_mode.AxisMode.from_value("bogus") is axis_mode.AxisMode.WORLD
    assert axis_mode.AxisMode.LOCAL.label == "Local"
    assert axis_mode.axis_mode_values() == tuple(mode.value for mode in axis_mode.AxisMode)
