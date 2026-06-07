from __future__ import annotations

import ctypes
import math
from pathlib import Path

from src.math import frame_math


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "native" / "GhostRigger.Native.NativeCore.Math"
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Native.NativeCore.Math.dll"


Double3 = ctypes.c_double * 3


def _vec3(values: tuple[float, float, float]) -> Double3:
    return Double3(*values)


def _tuple3(values: Double3) -> tuple[float, float, float]:
    return (values[0], values[1], values[2])


def _assert_close_tuple(actual, expected, *, abs_tol: float = 1.0e-9) -> None:
    assert len(actual) == len(expected)
    for actual_value, expected_value in zip(actual, expected):
        assert math.isclose(actual_value, expected_value, rel_tol=1.0e-9, abs_tol=abs_tol)


def _load_math_dll() -> ctypes.CDLL:
    dll = ctypes.CDLL(str(DLL_PATH))
    vec3_ptr = ctypes.POINTER(ctypes.c_double)
    dll.gr_native_core_math_frame_normalize_vec3.argtypes = [vec3_ptr, vec3_ptr]
    dll.gr_native_core_math_frame_normalize_vec3.restype = ctypes.c_int
    dll.gr_native_core_math_frame_clean_texture_name.argtypes = [ctypes.c_char_p]
    dll.gr_native_core_math_frame_clean_texture_name.restype = ctypes.c_char_p
    for name in (
        "gr_native_core_math_frame_cross",
        "gr_native_core_math_frame_sub",
        "gr_native_core_math_frame_add",
    ):
        function = getattr(dll, name)
        function.argtypes = [vec3_ptr, vec3_ptr, vec3_ptr]
        function.restype = ctypes.c_int
    dll.gr_native_core_math_frame_dot.argtypes = [vec3_ptr, vec3_ptr]
    dll.gr_native_core_math_frame_dot.restype = ctypes.c_double
    dll.gr_native_core_math_frame_clamp.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double]
    dll.gr_native_core_math_frame_clamp.restype = ctypes.c_double
    dll.gr_native_core_math_frame_lerp.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double]
    dll.gr_native_core_math_frame_lerp.restype = ctypes.c_double
    dll.gr_native_core_math_frame_unwrap_uv.argtypes = [ctypes.c_double, ctypes.c_double]
    dll.gr_native_core_math_frame_unwrap_uv.restype = ctypes.c_double
    dll.gr_native_core_math_frame_edge_has_seam.argtypes = [ctypes.c_double, ctypes.c_double]
    dll.gr_native_core_math_frame_edge_has_seam.restype = ctypes.c_int
    dll.gr_native_core_math_frame_vflip_nontiled.argtypes = [ctypes.c_double, ctypes.c_double]
    dll.gr_native_core_math_frame_vflip_nontiled.restype = ctypes.c_double
    dll.gr_native_core_math_frame_vflip_tiled.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double]
    dll.gr_native_core_math_frame_vflip_tiled.restype = ctypes.c_double
    dll.gr_native_core_math_frame_float_to_sort_key.argtypes = [ctypes.c_double]
    dll.gr_native_core_math_frame_float_to_sort_key.restype = ctypes.c_uint32
    dll.gr_native_core_math_frame_compute_screen_size_ratio.argtypes = [
        vec3_ptr,
        vec3_ptr,
        vec3_ptr,
        ctypes.c_double,
        ctypes.c_int,
    ]
    dll.gr_native_core_math_frame_compute_screen_size_ratio.restype = ctypes.c_double
    return dll


def test_native_core_math_project_declares_frame_math_files_and_exports() -> None:
    project = (PROJECT_DIR / "GhostRigger.Native.NativeCore.Math.vcxproj").read_text(encoding="utf-8")
    filters = (PROJECT_DIR / "GhostRigger.Native.NativeCore.Math.vcxproj.filters").read_text(encoding="utf-8")
    public_header = (PROJECT_DIR / "Public" / "FrameMath.h").read_text(encoding="utf-8")
    package_header = (PROJECT_DIR / "Public" / "GhostRiggerNativeCoreMath.h").read_text(encoding="utf-8")
    implementation = (PROJECT_DIR / "Private" / "FrameMath.cpp").read_text(encoding="utf-8")

    assert '<ClInclude Include="Public\\FrameMath.h" />' in project
    assert '<ClCompile Include="Private\\FrameMath.cpp" />' in project
    assert '<Filter>Public</Filter>' in filters
    assert '<Filter>Private</Filter>' in filters
    assert "namespace ghostrigger::native::nativecore::math::frame_math" in public_header
    assert "namespace ghostrigger::native::nativecore::math::frame_math" in implementation
    assert "gr_native_core_math_frame_compute_screen_size_ratio" in package_header
    assert "phase15" not in public_header
    assert "pyfn_" not in implementation
    assert "using namespace" not in implementation


def test_native_frame_vector_and_scalar_helpers_match_python_frame_math() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_math_dll()
    a = (3.5, -2.0, 7.25)
    b = (-4.0, 5.0, 0.5)

    out = Double3()
    assert dll.gr_native_core_math_frame_normalize_vec3(_vec3(a), out) == 1
    _assert_close_tuple(_tuple3(out), frame_math._normalize(a))
    assert dll.gr_native_core_math_frame_cross(_vec3(a), _vec3(b), out) == 1
    _assert_close_tuple(_tuple3(out), frame_math._cross(a, b))
    assert dll.gr_native_core_math_frame_sub(_vec3(a), _vec3(b), out) == 1
    _assert_close_tuple(_tuple3(out), frame_math._sub(a, b))
    assert dll.gr_native_core_math_frame_add(_vec3(a), _vec3(b), out) == 1
    _assert_close_tuple(_tuple3(out), frame_math._add(a, b))
    assert math.isclose(dll.gr_native_core_math_frame_dot(_vec3(a), _vec3(b)), frame_math._dot(a, b))
    assert math.isclose(dll.gr_native_core_math_frame_clamp(8.0, -2.0, 5.0), frame_math._clamp(8.0, -2.0, 5.0))
    assert math.isclose(dll.gr_native_core_math_frame_lerp(10.0, 20.0, 0.25), frame_math._lerp(10.0, 20.0, 0.25))


def test_native_frame_texture_uv_and_sort_helpers_match_python_frame_math() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_math_dll()

    assert dll.gr_native_core_math_frame_clean_texture_name(b"  PLC_Floor01\x00junk  ").decode("utf-8") == frame_math._clean_tex_name("  PLC_Floor01\x00junk  ")
    assert math.isclose(dll.gr_native_core_math_frame_unwrap_uv(0.1, 1.2), frame_math._uwrap_global(0.1, 1.2))
    assert dll.gr_native_core_math_frame_edge_has_seam(0.1, 1.2) == int(frame_math._edge_has_seam_global(0.1, 1.2))
    assert math.isclose(dll.gr_native_core_math_frame_vflip_nontiled(0.25, 256.0), frame_math._vflip_nontiled(0.25, 256.0))
    assert math.isclose(dll.gr_native_core_math_frame_vflip_tiled(2.25, 4.0, 128.0), frame_math._vflip_tiled(2.25, 4.0, 128.0))
    for value in (-100.5, -0.0, 0.0, 0.25, 50.0, 1000.125):
        assert dll.gr_native_core_math_frame_float_to_sort_key(value) == frame_math._float_to_sort_key(value)


def test_native_frame_screen_size_ratio_matches_python_frame_math() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_math_dll()
    bounds_min = (-1.0, -2.0, -3.0)
    bounds_max = (4.0, 5.0, 6.0)
    view_origin = (10.0, -3.0, 2.0)
    fov = 1.0471975512
    viewport_height = 1080

    assert math.isclose(
        dll.gr_native_core_math_frame_compute_screen_size_ratio(
            _vec3(bounds_min),
            _vec3(bounds_max),
            _vec3(view_origin),
            fov,
            viewport_height,
        ),
        frame_math._compute_screen_size_ratio(bounds_min, bounds_max, view_origin, fov, viewport_height),
        rel_tol=1.0e-9,
        abs_tol=1.0e-9,
    )
