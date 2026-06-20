from __future__ import annotations

import ctypes
import math
from pathlib import Path

from src.math import camera_math


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "native" / "GhostRigger.Native.Core.Foundation"
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Native.Core.Foundation.dll"


Double3 = ctypes.c_double * 3
Double4 = ctypes.c_double * 4


def _vec3(values: tuple[float, float, float]) -> Double3:
    return Double3(*values)


def _quat(values: tuple[float, float, float, float]) -> Double4:
    return Double4(*values)


def _tuple3(values: Double3) -> tuple[float, float, float]:
    return (values[0], values[1], values[2])


def _tuple4(values: Double4) -> tuple[float, float, float, float]:
    return (values[0], values[1], values[2], values[3])


def _assert_close_tuple(actual, expected, *, abs_tol: float = 1.0e-9) -> None:
    assert len(actual) == len(expected)
    for actual_value, expected_value in zip(actual, expected):
        assert math.isclose(actual_value, expected_value, rel_tol=1.0e-9, abs_tol=abs_tol)


def _load_math_dll() -> ctypes.CDLL:
    dll = ctypes.CDLL(str(DLL_PATH))
    vec3_ptr = ctypes.POINTER(ctypes.c_double)

    dll.gr_native_core_math_camera_normalize_vec3.argtypes = [vec3_ptr, vec3_ptr]
    dll.gr_native_core_math_camera_normalize_vec3.restype = ctypes.c_int

    for name in (
        "gr_native_core_math_camera_cross",
        "gr_native_core_math_camera_add",
        "gr_native_core_math_camera_sub",
    ):
        function = getattr(dll, name)
        function.argtypes = [vec3_ptr, vec3_ptr, vec3_ptr]
        function.restype = ctypes.c_int

    dll.gr_native_core_math_camera_mul.argtypes = [vec3_ptr, ctypes.c_double, vec3_ptr]
    dll.gr_native_core_math_camera_mul.restype = ctypes.c_int
    dll.gr_native_core_math_camera_dot.argtypes = [vec3_ptr, vec3_ptr]
    dll.gr_native_core_math_camera_dot.restype = ctypes.c_double
    dll.gr_native_core_math_camera_length.argtypes = [vec3_ptr]
    dll.gr_native_core_math_camera_length.restype = ctypes.c_double

    quat_ptr = ctypes.POINTER(ctypes.c_double)
    dll.gr_native_core_math_camera_normalize_quat.argtypes = [quat_ptr, quat_ptr]
    dll.gr_native_core_math_camera_normalize_quat.restype = ctypes.c_int
    dll.gr_native_core_math_camera_multiply_quat.argtypes = [quat_ptr, quat_ptr, quat_ptr]
    dll.gr_native_core_math_camera_multiply_quat.restype = ctypes.c_int
    dll.gr_native_core_math_camera_quat_to_euler_degrees.argtypes = [quat_ptr, vec3_ptr]
    dll.gr_native_core_math_camera_quat_to_euler_degrees.restype = ctypes.c_int
    dll.gr_native_core_math_camera_euler_degrees_to_quat.argtypes = [vec3_ptr, quat_ptr]
    dll.gr_native_core_math_camera_euler_degrees_to_quat.restype = ctypes.c_int
    dll.gr_native_core_math_camera_rotate_vector.argtypes = [quat_ptr, vec3_ptr, vec3_ptr]
    dll.gr_native_core_math_camera_rotate_vector.restype = ctypes.c_int
    dll.gr_native_core_math_camera_look_at_quaternion.argtypes = [vec3_ptr, vec3_ptr, quat_ptr]
    dll.gr_native_core_math_camera_look_at_quaternion.restype = ctypes.c_int
    dll.gr_native_core_math_camera_forward.argtypes = [quat_ptr, vec3_ptr]
    dll.gr_native_core_math_camera_forward.restype = ctypes.c_int
    dll.gr_native_core_math_camera_focal_length_to_fov.argtypes = [ctypes.c_double, ctypes.c_double]
    dll.gr_native_core_math_camera_focal_length_to_fov.restype = ctypes.c_double
    dll.gr_native_core_math_camera_fov_to_focal_length.argtypes = [ctypes.c_double, ctypes.c_double]
    dll.gr_native_core_math_camera_fov_to_focal_length.restype = ctypes.c_double
    return dll


def test_native_core_math_project_declares_camera_math_files_and_exports() -> None:
    project = (PROJECT_DIR / "GhostRigger.Native.Core.Foundation.vcxproj").read_text(encoding="utf-8")
    filters = (PROJECT_DIR / "GhostRigger.Native.Core.Foundation.vcxproj.filters").read_text(encoding="utf-8")
    public_header = (PROJECT_DIR / "Public" / "CameraMath.h").read_text(encoding="utf-8")
    package_header = (PROJECT_DIR / "Public" / "GhostRiggerNativeCoreMath.h").read_text(encoding="utf-8")
    implementation = (PROJECT_DIR / "Private" / "CameraMath.cpp").read_text(encoding="utf-8")

    assert '<ClInclude Include="Public\\CameraMath.h" />' in project
    assert '<ClCompile Include="Private\\CameraMath.cpp" />' in project
    assert '<Filter>Public</Filter>' in filters
    assert '<Filter>Private</Filter>' in filters
    assert "namespace ghostrigger::native::nativecore::math::camera_math" in public_header
    assert "namespace ghostrigger::native::nativecore::math::camera_math" in implementation
    assert "gr_native_core_math_camera_look_at_quaternion" in package_header
    assert "phase15" not in public_header
    assert "pyfn_" not in implementation
    assert "using namespace" not in implementation


def test_native_camera_vec3_math_matches_python_camera_math() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_math_dll()
    a = (3.5, -2.0, 7.25)
    b = (-4.0, 5.0, 0.5)

    out = Double3()
    assert dll.gr_native_core_math_camera_normalize_vec3(_vec3(a), out) == 1
    _assert_close_tuple(_tuple3(out), camera_math.normalize(a))

    assert dll.gr_native_core_math_camera_cross(_vec3(a), _vec3(b), out) == 1
    _assert_close_tuple(_tuple3(out), camera_math.cross(a, b))

    assert dll.gr_native_core_math_camera_add(_vec3(a), _vec3(b), out) == 1
    _assert_close_tuple(_tuple3(out), camera_math.add(a, b))

    assert dll.gr_native_core_math_camera_sub(_vec3(a), _vec3(b), out) == 1
    _assert_close_tuple(_tuple3(out), camera_math.sub(a, b))

    assert dll.gr_native_core_math_camera_mul(_vec3(a), 2.75, out) == 1
    _assert_close_tuple(_tuple3(out), camera_math.mul(a, 2.75))
    assert math.isclose(dll.gr_native_core_math_camera_dot(_vec3(a), _vec3(b)), camera_math.dot(a, b))
    assert math.isclose(dll.gr_native_core_math_camera_length(_vec3(a)), camera_math.length(a))


def test_native_camera_quaternion_math_matches_python_camera_math() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_math_dll()
    q1 = camera_math.euler_degrees_to_quat((10.0, 20.0, 30.0))
    q2 = camera_math.euler_degrees_to_quat((-15.0, 5.0, 90.0))

    out_quat = Double4()
    assert dll.gr_native_core_math_camera_normalize_quat(_quat((0.5, 0.25, -0.75, 2.0)), out_quat) == 1
    _assert_close_tuple(_tuple4(out_quat), camera_math.normalize_quat((0.5, 0.25, -0.75, 2.0)))

    assert dll.gr_native_core_math_camera_multiply_quat(_quat(q1), _quat(q2), out_quat) == 1
    _assert_close_tuple(_tuple4(out_quat), camera_math.multiply_quat(q1, q2))

    out_vec = Double3()
    assert dll.gr_native_core_math_camera_euler_degrees_to_quat(_vec3((10.0, 20.0, 30.0)), out_quat) == 1
    _assert_close_tuple(_tuple4(out_quat), q1)

    assert dll.gr_native_core_math_camera_quat_to_euler_degrees(_quat(q1), out_vec) == 1
    _assert_close_tuple(_tuple3(out_vec), camera_math.quat_to_euler_degrees(q1), abs_tol=1.0e-8)

    vector = (4.0, -2.0, 1.5)
    assert dll.gr_native_core_math_camera_rotate_vector(_quat(q1), _vec3(vector), out_vec) == 1
    _assert_close_tuple(_tuple3(out_vec), camera_math.rotate_vector(q1, vector))


def test_native_camera_look_at_and_lens_math_match_python_camera_math() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_math_dll()
    position = (10.0, -5.0, 3.0)
    target = (-2.0, 8.0, 4.5)

    out_quat = Double4()
    assert dll.gr_native_core_math_camera_look_at_quaternion(_vec3(position), _vec3(target), out_quat) == 1
    _assert_close_tuple(_tuple4(out_quat), camera_math.look_at_quaternion(position, target), abs_tol=1.0e-8)

    out_vec = Double3()
    assert dll.gr_native_core_math_camera_forward(out_quat, out_vec) == 1
    _assert_close_tuple(_tuple3(out_vec), camera_math.camera_forward(_tuple4(out_quat)), abs_tol=1.0e-8)

    assert math.isclose(
        dll.gr_native_core_math_camera_focal_length_to_fov(36.0, 50.0),
        camera_math.focal_length_to_fov(36.0, 50.0),
        rel_tol=1.0e-9,
        abs_tol=1.0e-9,
    )
    assert math.isclose(
        dll.gr_native_core_math_camera_fov_to_focal_length(36.0, 39.597752709049864),
        camera_math.fov_to_focal_length(36.0, 39.597752709049864),
        rel_tol=1.0e-9,
        abs_tol=1.0e-9,
    )
