from __future__ import annotations

import ctypes
import json
import math
from pathlib import Path

from src.math import transform_math, viewcube_math


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "native" / "GhostRigger.Native.NativeCore.Math"
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Native.NativeCore.Math.dll"


Double3 = ctypes.c_double * 3
Double4 = ctypes.c_double * 4
Double16 = ctypes.c_double * 16


def _vec3(values: tuple[float, float, float]) -> Double3:
    return Double3(*values)


def _vec4(values: tuple[float, float, float, float]) -> Double4:
    return Double4(*values)


def _tuple3(values: Double3) -> tuple[float, float, float]:
    return (values[0], values[1], values[2])


def _tuple4(values: Double4) -> tuple[float, float, float, float]:
    return (values[0], values[1], values[2], values[3])


def _tuple16(values: Double16) -> tuple[float, ...]:
    return tuple(values)


def _assert_close_tuple(actual, expected, *, abs_tol: float = 1.0e-9) -> None:
    assert len(actual) == len(expected)
    for actual_value, expected_value in zip(actual, expected):
        assert math.isclose(actual_value, expected_value, rel_tol=1.0e-9, abs_tol=abs_tol)


def _matrix_to_tuple(values: Double16) -> tuple[float, ...]:
    return _tuple16(values)


def _load_math_dll() -> ctypes.CDLL:
    dll = ctypes.CDLL(str(DLL_PATH))

    vec3_ptr = ctypes.POINTER(ctypes.c_double)
    vec4_ptr = ctypes.POINTER(ctypes.c_double)

    dll.gr_native_core_math_capabilities_json.argtypes = []
    dll.gr_native_core_math_capabilities_json.restype = ctypes.c_char_p

    dll.gr_native_core_math_transform_as_vec3.argtypes = [vec3_ptr, vec3_ptr]
    dll.gr_native_core_math_transform_as_vec3.restype = ctypes.c_int
    dll.gr_native_core_math_transform_normalize.argtypes = [vec3_ptr, vec3_ptr]
    dll.gr_native_core_math_transform_normalize.restype = ctypes.c_int
    for name in (
        "gr_native_core_math_transform_closest_point_on_ray",
        "gr_native_core_math_transform_rotate_vector",
    ):
        function = getattr(dll, name)
        function.argtypes = [vec3_ptr, vec3_ptr, vec3_ptr]
        function.restype = ctypes.c_int
    dll.gr_native_core_math_transform_closest_point_between_rays.argtypes = [
        vec3_ptr,
        vec3_ptr,
        vec3_ptr,
        vec3_ptr,
        vec3_ptr,
        vec3_ptr,
    ]
    dll.gr_native_core_math_transform_closest_point_between_rays.restype = ctypes.c_int
    dll.gr_native_core_math_transform_screen_space_distance.argtypes = [
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
    ]
    dll.gr_native_core_math_transform_screen_space_distance.restype = ctypes.c_double
    dll.gr_native_core_math_transform_rotation_angle_from_mouse_delta.argtypes = [
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_int,
    ]
    dll.gr_native_core_math_transform_rotation_angle_from_mouse_delta.restype = ctypes.c_double
    dll.gr_native_core_math_transform_axis_quaternion.argtypes = [ctypes.c_char, ctypes.c_double, vec4_ptr]
    dll.gr_native_core_math_transform_axis_quaternion.restype = ctypes.c_int
    dll.gr_native_core_math_transform_multiply_quaternions.argtypes = [vec4_ptr, vec4_ptr, vec4_ptr]
    dll.gr_native_core_math_transform_multiply_quaternions.restype = ctypes.c_int
    dll.gr_native_core_math_transform_build_translation_matrix.argtypes = [vec3_ptr, ctypes.POINTER(ctypes.c_double)]
    dll.gr_native_core_math_transform_build_translation_matrix.restype = ctypes.c_int
    dll.gr_native_core_math_transform_build_rotation_matrix.argtypes = [ctypes.c_char, ctypes.c_double, ctypes.POINTER(ctypes.c_double)]
    dll.gr_native_core_math_transform_build_rotation_matrix.restype = ctypes.c_int
    dll.gr_native_core_math_transform_build_scale_matrix_scalar.argtypes = [ctypes.c_double, ctypes.POINTER(ctypes.c_double)]
    dll.gr_native_core_math_transform_build_scale_matrix_scalar.restype = ctypes.c_int
    dll.gr_native_core_math_transform_build_scale_matrix_vector.argtypes = [vec3_ptr, ctypes.POINTER(ctypes.c_double)]
    dll.gr_native_core_math_transform_build_scale_matrix_vector.restype = ctypes.c_int

    dll.gr_native_core_math_viewcube_normalize.argtypes = [vec3_ptr, vec3_ptr]
    dll.gr_native_core_math_viewcube_normalize.restype = ctypes.c_int
    dll.gr_native_core_math_viewcube_cross.argtypes = [vec3_ptr, vec3_ptr, vec3_ptr]
    dll.gr_native_core_math_viewcube_cross.restype = ctypes.c_int
    dll.gr_native_core_math_viewcube_view_direction_from_angles.argtypes = [ctypes.c_double, ctypes.c_double, vec3_ptr]
    dll.gr_native_core_math_viewcube_view_direction_from_angles.restype = ctypes.c_int
    dll.gr_native_core_math_viewcube_view_orientation_quaternion.argtypes = [ctypes.c_double, ctypes.c_double, vec4_ptr]
    dll.gr_native_core_math_viewcube_view_orientation_quaternion.restype = ctypes.c_int
    dll.gr_native_core_math_viewcube_dot.argtypes = [vec3_ptr, vec3_ptr]
    dll.gr_native_core_math_viewcube_dot.restype = ctypes.c_double
    dll.gr_native_core_math_viewcube_azimuth_elevation_from_direction.argtypes = [vec3_ptr, ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]
    dll.gr_native_core_math_viewcube_azimuth_elevation_from_direction.restype = ctypes.c_int
    dll.gr_native_core_math_viewcube_action_from_view_name.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
    dll.gr_native_core_math_viewcube_action_from_view_name.restype = ctypes.c_int
    dll.gr_native_core_math_viewcube_target_for_action.argtypes = [
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
    ]
    dll.gr_native_core_math_viewcube_target_for_action.restype = ctypes.c_int
    dll.gr_native_core_math_viewcube_camera_basis_from_angles.argtypes = [
        ctypes.c_double,
        ctypes.c_double,
        vec3_ptr,
        vec3_ptr,
        vec3_ptr,
    ]
    dll.gr_native_core_math_viewcube_camera_basis_from_angles.restype = ctypes.c_int

    return dll


def test_native_core_math_project_declares_transform_and_viewcube_math_files_and_exports() -> None:
    project = (PROJECT_DIR / "GhostRigger.Native.NativeCore.Math.vcxproj").read_text(encoding="utf-8")
    filters = (PROJECT_DIR / "GhostRigger.Native.NativeCore.Math.vcxproj.filters").read_text(encoding="utf-8")
    package_header = (PROJECT_DIR / "Public" / "GhostRiggerNativeCoreMath.h").read_text(encoding="utf-8")
    package_impl = (PROJECT_DIR / "Private" / "GhostRiggerNativeCoreMath.cpp").read_text(encoding="utf-8")
    public_transform = (PROJECT_DIR / "Public" / "TransformMath.h").read_text(encoding="utf-8")
    public_viewcube = (PROJECT_DIR / "Public" / "ViewcubeMath.h").read_text(encoding="utf-8")
    implementation_transform = (PROJECT_DIR / "Private" / "TransformMath.cpp").read_text(encoding="utf-8")
    implementation_viewcube = (PROJECT_DIR / "Private" / "ViewcubeMath.cpp").read_text(encoding="utf-8")

    for include in ("Private\\TransformMath.cpp", "Private\\ViewcubeMath.cpp"):
        assert f'<ClCompile Include="{include}" />' in project
    for include in ("Public\\TransformMath.h", "Public\\ViewcubeMath.h"):
        assert f'<ClInclude Include="{include}" />' in project
    assert '<Filter>Public</Filter>' in filters
    assert '<Filter>Private</Filter>' in filters
    assert "namespace ghostrigger::native::nativecore::math::transform_math" in public_transform
    assert "namespace ghostrigger::native::nativecore::math::viewcube_math" in public_viewcube
    assert "gr_native_core_math_transform_normalize" in package_header
    assert "gr_native_core_math_viewcube_normalize" in package_header
    assert "gr_native_core_math_transform_build_scale_matrix_vector" in package_header
    assert "transform_math_native" in package_impl
    assert "viewcube_math_native" in package_impl
    assert "using namespace" not in implementation_transform
    assert "using namespace" not in implementation_viewcube
    assert "phase15" not in implementation_transform
    assert "pyfn_" not in implementation_viewcube


def test_native_transform_math_matches_python_transform_math() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_math_dll()
    origin = (4.0, -1.0, 2.5)
    direction = (2.0, -2.0, 1.0)
    point = (5.0, 0.5, 7.5)
    second = (1.0, 2.0, 3.0)

    out_vec = Double3()
    out_vec_a = Double3()
    out_quat = Double4()
    out_mat = Double16()

    assert dll.gr_native_core_math_transform_as_vec3(_vec3(origin), out_vec) == 1
    _assert_close_tuple(_tuple3(out_vec), tuple(transform_math._as_vec3(origin)))

    assert dll.gr_native_core_math_transform_normalize(_vec3(second), out_vec) == 1
    _assert_close_tuple(_tuple3(out_vec), transform_math.normalize(second))

    assert dll.gr_native_core_math_transform_closest_point_on_ray(_vec3(origin), _vec3(direction), _vec3(point), out_vec) == 1
    _assert_close_tuple(_tuple3(out_vec), tuple(transform_math.closest_point_on_ray(origin, direction, point)))

    assert dll.gr_native_core_math_transform_closest_point_between_rays(
        _vec3(origin),
        _vec3(direction),
        _vec3(point),
        _vec3(second),
        out_vec,
        out_vec_a,
    ) == 1
    expected_a, expected_b = transform_math.closest_point_between_rays(origin, direction, point, second)
    out_a = _tuple3(out_vec)
    _assert_close_tuple((out_a), tuple(expected_a))
    _assert_close_tuple(_tuple3(out_vec_a), tuple(expected_b))

    expected_screen = transform_math.screen_space_distance((10.0, 15.0), (25.0, 35.0))
    assert math.isclose(dll.gr_native_core_math_transform_screen_space_distance(10.0, 15.0, 25.0, 35.0), expected_screen)

    expected_angle = transform_math.rotation_angle_from_mouse_delta((100, 120), (120, 160), (512.0, 380.0))
    assert math.isclose(
        dll.gr_native_core_math_transform_rotation_angle_from_mouse_delta(
            100.0,
            120.0,
            120.0,
            160.0,
            512.0,
            380.0,
            1,
        ),
        expected_angle,
        rel_tol=1.0e-9,
        abs_tol=1.0e-9,
    )
    expected_flat = transform_math.build_translation_matrix((1.0, 2.0, 3.0)).flatten()
    assert dll.gr_native_core_math_transform_build_translation_matrix(_vec3((1.0, 2.0, 3.0)), out_mat) == 1
    _assert_close_tuple(_matrix_to_tuple(out_mat), tuple(float(v) for v in expected_flat))

    expected_rot = transform_math.build_rotation_matrix("Y", 0.33).flatten()
    assert dll.gr_native_core_math_transform_build_rotation_matrix(ord("Y"), 0.33, out_mat) == 1
    _assert_close_tuple(_matrix_to_tuple(out_mat), tuple(float(v) for v in expected_rot))

    expected_scale_scalar = transform_math.build_scale_matrix(2.25).flatten()
    assert dll.gr_native_core_math_transform_build_scale_matrix_scalar(2.25, out_mat) == 1
    _assert_close_tuple(_matrix_to_tuple(out_mat), tuple(float(v) for v in expected_scale_scalar))

    expected_scale_vector = transform_math.build_scale_matrix((0.5, 2.0, -1.5)).flatten()
    assert dll.gr_native_core_math_transform_build_scale_matrix_vector(_vec3((0.5, 2.0, -1.5)), out_mat) == 1
    _assert_close_tuple(_matrix_to_tuple(out_mat), tuple(float(v) for v in expected_scale_vector))

    assert dll.gr_native_core_math_transform_axis_quaternion(ord("a"), 1.2, out_quat) == 1
    expected_unknown_axis = transform_math.axis_quaternion("a", 1.2)
    _assert_close_tuple(_tuple4(out_quat), tuple(float(v) for v in expected_unknown_axis))

    q1 = transform_math.axis_quaternion("Z", 0.7)
    q2 = transform_math.axis_quaternion("X", -1.1)
    assert dll.gr_native_core_math_transform_multiply_quaternions(_vec4(q1), _vec4(q2), out_quat) == 1
    _assert_close_tuple(_tuple4(out_quat), transform_math.multiply_quaternions(q1, q2))

    vector = (3.0, -1.0, 2.0)
    assert dll.gr_native_core_math_transform_rotate_vector(_vec4(q1), _vec3(vector), out_vec) == 1
    _assert_close_tuple(_tuple3(out_vec), transform_math.rotate_vector(q1, vector))


def test_native_viewcube_math_matches_python_viewcube_math() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_math_dll()

    out_vec = Double3()
    out_vec_a = Double3()
    out_vec_b = Double3()
    out_vec_c = Double3()
    out_quat = Double4()
    out_action = ctypes.c_int()
    out_az = ctypes.c_double()
    out_el = ctypes.c_double()

    assert dll.gr_native_core_math_viewcube_normalize(_vec3((1.0, 2.0, 3.0)), out_vec) == 1
    _assert_close_tuple(_tuple3(out_vec), viewcube_math._normalize((1.0, 2.0, 3.0)))

    assert dll.gr_native_core_math_viewcube_cross(_vec3((1.0, 0.0, 0.0)), _vec3((0.0, 1.0, 0.0)), out_vec) == 1
    _assert_close_tuple(_tuple3(out_vec), viewcube_math._cross((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))

    assert dll.gr_native_core_math_viewcube_dot(_vec3((1.0, 0.0, 0.0)), _vec3((0.0, 1.0, 0.0))) == 0.0
    assert math.isclose(dll.gr_native_core_math_viewcube_dot(_vec3((1.0, 0.0, 0.0)), _vec3((0.0, 1.0, 0.0))), viewcube_math._dot((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))

    for view_name in ("f", "front", "bo", "bottom", "persp", "home"):
        out_action = ctypes.c_int()
        status = dll.gr_native_core_math_viewcube_action_from_view_name(view_name.encode("utf-8"), ctypes.byref(out_action))
        if view_name in ("f", "front", "bo", "bottom"):
            assert status == 1
            assert out_action.value >= 0
            if view_name in ("f", "front"):
                assert out_action.value == 0
            if view_name in ("bo", "bottom"):
                assert out_action.value == 5
        elif view_name == "persp":
            assert status == 1
            assert out_action.value == 6
        else:
            assert status == 1
            assert out_action.value == 7

    assert dll.gr_native_core_math_viewcube_action_from_view_name(b"bad_view_name", ctypes.byref(out_action)) == 0

    azimuth_elevation = (60.0, 20.0)
    assert dll.gr_native_core_math_viewcube_target_for_action(0, ctypes.byref(out_az), ctypes.byref(out_el)) == 1
    _assert_close_tuple((out_az.value, out_el.value), (90.0, 0.0))
    assert dll.gr_native_core_math_viewcube_target_for_action(7, ctypes.byref(out_az), ctypes.byref(out_el)) == 0
    assert dll.gr_native_core_math_viewcube_target_for_action(6, ctypes.byref(out_az), ctypes.byref(out_el)) == 0

    assert dll.gr_native_core_math_viewcube_azimuth_elevation_from_direction(
        _vec3(viewcube_math.view_direction_from_angles(60.0, 20.0)),
        ctypes.byref(out_az),
        ctypes.byref(out_el),
    ) == 1
    _assert_close_tuple((out_az.value, out_el.value), azimuth_elevation, abs_tol=1.0e-7)

    assert dll.gr_native_core_math_viewcube_view_direction_from_angles(60.0, 20.0, out_vec) == 1
    _assert_close_tuple(_tuple3(out_vec), viewcube_math.view_direction_from_angles(60.0, 20.0))

    assert dll.gr_native_core_math_viewcube_camera_basis_from_angles(90.0, 10.0, out_vec, out_vec_a, out_vec_b) == 1
    py_right, py_up, py_forward = viewcube_math.camera_basis_from_angles(90.0, 10.0)
    _assert_close_tuple(_tuple3(out_vec), py_right)
    _assert_close_tuple(_tuple3(out_vec_a), py_up)
    _assert_close_tuple(_tuple3(out_vec_b), py_forward)

    assert dll.gr_native_core_math_viewcube_view_orientation_quaternion(90.0, 10.0, out_quat) == 1
    _assert_close_tuple(_tuple4(out_quat), viewcube_math.view_orientation_quaternion(90.0, 10.0))


def test_native_math_capabilities_json_documents_transform_and_viewcube_scope() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_math_dll()
    capabilities = json.loads(dll.gr_native_core_math_capabilities_json().decode("utf-8"))
    assert capabilities["transform_math_native"] is True
    assert capabilities["viewcube_math_native"] is True
    assert capabilities["transform_math_schema"] == "transform_math.v1"
    assert capabilities["viewcube_math_schema"] == "viewcube_math.v1"
