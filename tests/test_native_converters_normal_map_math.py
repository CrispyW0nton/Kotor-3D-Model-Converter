from __future__ import annotations

import ctypes
import json
import math
from pathlib import Path

from src.converters import normal_map


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "native" / "GhostRigger.Core.IO"
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Core.IO.dll"
DOUBLE_PTR = ctypes.POINTER(ctypes.c_double)


def _load_converters_dll() -> ctypes.CDLL:
    dll = ctypes.CDLL(str(DLL_PATH))
    dll.gr_converters_normal_map_normalize3.argtypes = [
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        DOUBLE_PTR,
        DOUBLE_PTR,
        DOUBLE_PTR,
    ]
    dll.gr_converters_normal_map_dot3.argtypes = [ctypes.c_double] * 6
    dll.gr_converters_normal_map_dot3.restype = ctypes.c_double
    dll.gr_converters_normal_map_barycentric_uv.argtypes = [ctypes.c_double] * 8 + [DOUBLE_PTR] * 3
    dll.gr_converters_normal_map_barycentric_uv.restype = ctypes.c_int
    dll.gr_converters_normal_map_compute_tangent.argtypes = [ctypes.c_double] * 15 + [DOUBLE_PTR] * 6
    dll.gr_converters_normal_map_world_to_tangent.argtypes = [ctypes.c_double] * 12 + [DOUBLE_PTR] * 3
    dll.gr_converters_normal_map_ray_triangle_intersect.argtypes = [ctypes.c_double] * 15 + [DOUBLE_PTR] * 4
    dll.gr_converters_normal_map_ray_triangle_intersect.restype = ctypes.c_int
    dll.gr_converters_normal_map_math_contracts_schema_json.restype = ctypes.c_char_p
    return dll


def _triple() -> tuple[ctypes.c_double, ctypes.c_double, ctypes.c_double]:
    return ctypes.c_double(), ctypes.c_double(), ctypes.c_double()


def _assert_tuple_close(actual: tuple[float, ...], expected: tuple[float, ...]) -> None:
    assert len(actual) == len(expected)
    for lhs, rhs in zip(actual, expected):
        assert math.isclose(lhs, rhs, rel_tol=1.0e-9, abs_tol=1.0e-9)


def test_converters_declares_native_normal_map_math_files() -> None:
    project = (PROJECT_DIR / "GhostRigger.Core.IO.vcxproj").read_text(encoding="utf-8")
    filters = (PROJECT_DIR / "GhostRigger.Core.IO.vcxproj.filters").read_text(encoding="utf-8")
    header = (PROJECT_DIR / "Public" / "NormalMapMath.h").read_text(encoding="utf-8")
    implementation = (PROJECT_DIR / "Private" / "NormalMapMath.cpp").read_text(encoding="utf-8")

    assert '<ClInclude Include="Public\\NormalMapMath.h" />' in project
    assert '<ClCompile Include="Private\\NormalMapMath.cpp" />' in project
    assert '<Filter>Public</Filter>' in filters
    assert '<Filter>Private</Filter>' in filters
    assert "namespace ghostrigger::core::converters::normal_map::math" in header
    assert "namespace ghostrigger::core::converters::normal_map::math" in implementation
    assert "using namespace" not in implementation
    assert "phase15" not in implementation
    assert "pyfn_" not in implementation


def test_native_normal_map_vector_helpers_match_python() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_converters_dll()

    out_x, out_y, out_z = _triple()
    dll.gr_converters_normal_map_normalize3(3.0, 4.0, 0.0, out_x, out_y, out_z)
    _assert_tuple_close((out_x.value, out_y.value, out_z.value), normal_map._normalize3((3.0, 4.0, 0.0)))

    out_x, out_y, out_z = _triple()
    dll.gr_converters_normal_map_normalize3(0.0, 0.0, 0.0, out_x, out_y, out_z)
    _assert_tuple_close((out_x.value, out_y.value, out_z.value), normal_map._normalize3((0.0, 0.0, 0.0)))

    assert math.isclose(
        dll.gr_converters_normal_map_dot3(1.0, 2.0, 3.0, 4.0, -5.0, 6.0),
        normal_map._dot3((1.0, 2.0, 3.0), (4.0, -5.0, 6.0)),
        rel_tol=1.0e-9,
        abs_tol=1.0e-9,
    )


def test_native_normal_map_barycentric_and_tangent_match_python() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_converters_dll()

    b0, b1, b2 = _triple()
    valid = dll.gr_converters_normal_map_barycentric_uv(0.25, 0.25, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, b0, b1, b2)
    assert valid == 1
    _assert_tuple_close((b0.value, b1.value, b2.value), normal_map._barycentric_uv(0.25, 0.25, (0, 0), (1, 0), (0, 1)))

    b0, b1, b2 = _triple()
    valid = dll.gr_converters_normal_map_barycentric_uv(2.0, 2.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, b0, b1, b2)
    assert valid == 0
    assert normal_map._barycentric_uv(2.0, 2.0, (0, 0), (1, 0), (0, 1)) is None

    tx, ty, tz = _triple()
    bx, by, bz = _triple()
    dll.gr_converters_normal_map_compute_tangent(
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        1.0,
        tx,
        ty,
        tz,
        bx,
        by,
        bz,
    )
    expected_tangent, expected_bitangent = normal_map._compute_tangent(
        (0, 0, 0),
        (1, 0, 0),
        (0, 1, 0),
        (0, 0),
        (1, 0),
        (0, 1),
    )
    _assert_tuple_close((tx.value, ty.value, tz.value), expected_tangent)
    _assert_tuple_close((bx.value, by.value, bz.value), expected_bitangent)


def test_native_normal_map_world_to_tangent_and_ray_match_python() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_converters_dll()

    out_x, out_y, out_z = _triple()
    dll.gr_converters_normal_map_world_to_tangent(
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        out_x,
        out_y,
        out_z,
    )
    _assert_tuple_close(
        (out_x.value, out_y.value, out_z.value),
        normal_map._world_to_tangent((0, 1, 0), (0, 0, 1), (1, 0, 0), (0, 1, 0)),
    )

    t, b0, b1, b2 = ctypes.c_double(), ctypes.c_double(), ctypes.c_double(), ctypes.c_double()
    hit = dll.gr_converters_normal_map_ray_triangle_intersect(
        0.25,
        0.25,
        1.0,
        0.0,
        0.0,
        -1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        t,
        b0,
        b1,
        b2,
    )
    expected_t, expected_bary = normal_map._ray_triangle_intersect(
        (0.25, 0.25, 1.0),
        (0.0, 0.0, -1.0),
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    )
    assert hit == 1
    assert math.isclose(t.value, expected_t, rel_tol=1.0e-9, abs_tol=1.0e-9)
    _assert_tuple_close((b0.value, b1.value, b2.value), expected_bary)


def test_native_normal_map_math_documents_python_fallback_scope() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_converters_dll()

    schema = json.loads(dll.gr_converters_normal_map_math_contracts_schema_json().decode("utf-8"))
    assert schema["schema"] == "converters_normal_map_math_native.v1"
    assert "barycentric UV solve" in schema["native_scope"]
    assert "SoftwareNormalBaker image writes" in schema["python_fallback"]
