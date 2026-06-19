from __future__ import annotations

import ctypes
import json
import math
from pathlib import Path

from src.core.animation_retargeting import retargeter


ROOT = Path(__file__).resolve().parents[1]
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Core.AnimationRetargeting.dll"


Double3 = ctypes.c_double * 3
Double4 = ctypes.c_double * 4


def _vec3(values: tuple[float, float, float]) -> Double3:
    return Double3(*values)


def _vec4(values: tuple[float, float, float, float]) -> Double4:
    return Double4(*values)


def _tuple3(values: Double3) -> tuple[float, float, float]:
    return (values[0], values[1], values[2])


def _tuple4(values: Double4) -> tuple[float, float, float, float]:
    return (values[0], values[1], values[2], values[3])


def _assert_close_tuple(actual, expected, *, abs_tol: float = 1.0e-9) -> None:
    assert len(actual) == len(expected)
    for actual_value, expected_value in zip(actual, expected):
        assert math.isclose(actual_value, expected_value, rel_tol=1.0e-9, abs_tol=abs_tol)


def _load_dll() -> ctypes.CDLL:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = ctypes.CDLL(str(DLL_PATH))

    vec3_ptr = ctypes.POINTER(ctypes.c_double)
    vec4_ptr = ctypes.POINTER(ctypes.c_double)

    dll.gr_animation_retargeting_capabilities_json.argtypes = []
    dll.gr_animation_retargeting_capabilities_json.restype = ctypes.c_char_p
    dll.gr_animation_retargeting_candidate_names_json.argtypes = [ctypes.c_char_p]
    dll.gr_animation_retargeting_candidate_names_json.restype = ctypes.c_char_p
    dll.gr_animation_retargeting_sub3.argtypes = [vec3_ptr, vec3_ptr, vec3_ptr]
    dll.gr_animation_retargeting_sub3.restype = ctypes.c_int
    dll.gr_animation_retargeting_add3.argtypes = [vec3_ptr, vec3_ptr, ctypes.c_double, vec3_ptr]
    dll.gr_animation_retargeting_add3.restype = ctypes.c_int
    dll.gr_animation_retargeting_mul3.argtypes = [vec3_ptr, ctypes.c_double, vec3_ptr]
    dll.gr_animation_retargeting_mul3.restype = ctypes.c_int
    dll.gr_animation_retargeting_normal_quat.argtypes = [vec4_ptr, vec4_ptr]
    dll.gr_animation_retargeting_normal_quat.restype = ctypes.c_int
    dll.gr_animation_retargeting_quat_conjugate.argtypes = [vec4_ptr, vec4_ptr]
    dll.gr_animation_retargeting_quat_conjugate.restype = ctypes.c_int
    dll.gr_animation_retargeting_quat_mul.argtypes = [vec4_ptr, vec4_ptr, vec4_ptr]
    dll.gr_animation_retargeting_quat_mul.restype = ctypes.c_int
    dll.gr_animation_retargeting_retarget_rotation.argtypes = [vec4_ptr, vec4_ptr, vec4_ptr, vec4_ptr]
    dll.gr_animation_retargeting_retarget_rotation.restype = ctypes.c_int
    dll.gr_animation_retargeting_height_from_positions.argtypes = [vec3_ptr, ctypes.c_size_t]
    dll.gr_animation_retargeting_height_from_positions.restype = ctypes.c_double
    return dll


def test_native_candidate_names_match_python_alias_order() -> None:
    dll = _load_dll()
    for source_name in ("pelvis_g", "pelvis", "RHand", "unknown_node"):
        actual = json.loads(dll.gr_animation_retargeting_candidate_names_json(source_name.encode("utf-8")))
        expected = list(retargeter._candidate_names(source_name))
        assert actual == expected


def test_native_vector_helpers_match_python_retargeter() -> None:
    dll = _load_dll()
    a = (8.0, -2.0, 4.5)
    b = (-1.0, 3.0, 0.25)
    out = Double3()

    assert dll.gr_animation_retargeting_sub3(_vec3(a), _vec3(b), out) == 1
    _assert_close_tuple(_tuple3(out), retargeter._sub3(a, b))

    assert dll.gr_animation_retargeting_add3(_vec3(a), _vec3(b), 2.5, out) == 1
    _assert_close_tuple(_tuple3(out), retargeter._add3(a, b, 2.5))

    assert dll.gr_animation_retargeting_mul3(_vec3(a), -0.5, out) == 1
    _assert_close_tuple(_tuple3(out), retargeter._mul3(a, -0.5))

    flat_positions = Double3 * 4
    positions = ((1.0, 2.0, -3.0), (4.0, 5.0, 12.0), (6.0, 7.0, 4.0), (8.0, 9.0, 0.0))
    native_positions = flat_positions(*(_vec3(pos) for pos in positions))
    actual_height = dll.gr_animation_retargeting_height_from_positions(
        ctypes.cast(native_positions, ctypes.POINTER(ctypes.c_double)),
        len(positions),
    )
    assert math.isclose(actual_height, retargeter._height_from_positions(positions), rel_tol=1.0e-9, abs_tol=1.0e-9)


def test_native_quaternion_helpers_match_python_retargeter() -> None:
    dll = _load_dll()
    a = (0.2, -0.3, 0.5, 0.7)
    b = (-0.4, 0.1, 0.6, 0.65)
    c = (0.05, 0.2, -0.1, 0.97)
    out = Double4()

    assert dll.gr_animation_retargeting_normal_quat(_vec4(a), out) == 1
    _assert_close_tuple(_tuple4(out), retargeter._normal_quat(a))

    assert dll.gr_animation_retargeting_quat_conjugate(_vec4(a), out) == 1
    _assert_close_tuple(_tuple4(out), retargeter._quat_conjugate(a))

    assert dll.gr_animation_retargeting_quat_mul(_vec4(a), _vec4(b), out) == 1
    _assert_close_tuple(_tuple4(out), retargeter._quat_mul(a, b))

    assert dll.gr_animation_retargeting_retarget_rotation(_vec4(a), _vec4(b), _vec4(c), out) == 1
    _assert_close_tuple(_tuple4(out), retargeter._retarget_rotation(a, b, c))

    assert dll.gr_animation_retargeting_normal_quat(_vec4((0.0, 0.0, 0.0, 0.0)), out) == 1
    _assert_close_tuple(_tuple4(out), retargeter._normal_quat((0.0, 0.0, 0.0, 0.0)))


def test_native_animation_retargeting_capabilities_document_native_slice() -> None:
    dll = _load_dll()
    capabilities = json.loads(dll.gr_animation_retargeting_capabilities_json().decode("utf-8"))
    assert capabilities["retargeting_alias_native"] is True
    assert capabilities["retargeting_math_native"] is True
    assert capabilities["retargeting_runtime_python_fallback"] is True
