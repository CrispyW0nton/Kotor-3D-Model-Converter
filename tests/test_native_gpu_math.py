from __future__ import annotations

import ctypes
import json
import math
from pathlib import Path

from src.math import gpu_math


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "native" / "GhostRigger.Native.Core.Math"
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Native.Core.Math.dll"


Double3 = ctypes.c_double * 3
Double4 = ctypes.c_double * 4
Double9 = ctypes.c_double * 9
Double16 = ctypes.c_double * 16


def _vec3(values: tuple[float, float, float]) -> Double3:
    return Double3(*values)


def _vec4(values: tuple[float, float, float, float]) -> Double4:
    return Double4(*values)


def _mat4(values) -> Double16:
    return Double16(*tuple(float(v) for v in values))


def _tuple16(values: Double16) -> tuple[float, ...]:
    return tuple(values)


def _tuple9(values: Double9) -> tuple[float, ...]:
    return tuple(values)


def _assert_close_tuple(actual: tuple[float, ...], expected: tuple[float, ...], *, abs_tol: float = 1.0e-9) -> None:
    assert len(actual) == len(expected)
    for actual_value, expected_value in zip(actual, expected):
        assert math.isclose(actual_value, expected_value, rel_tol=1.0e-9, abs_tol=abs_tol)


def _load_math_dll() -> ctypes.CDLL:
    dll = ctypes.CDLL(str(DLL_PATH))
    vec3_ptr = ctypes.POINTER(ctypes.c_double)
    vec4_ptr = ctypes.POINTER(ctypes.c_double)
    mat4_ptr = ctypes.POINTER(ctypes.c_double)
    mat9_ptr = ctypes.POINTER(ctypes.c_double)

    dll.gr_native_core_math_matrix_from_pos_quat_np.argtypes = [vec3_ptr, vec4_ptr, mat4_ptr]
    dll.gr_native_core_math_matrix_from_pos_quat_np.restype = ctypes.c_int
    dll.gr_native_core_math_mat4_perspective.argtypes = [
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        mat4_ptr,
    ]
    dll.gr_native_core_math_mat4_perspective.restype = ctypes.c_int
    dll.gr_native_core_math_mat4_lookat.argtypes = [vec3_ptr, vec3_ptr, vec3_ptr, mat4_ptr]
    dll.gr_native_core_math_mat4_lookat.restype = ctypes.c_int
    dll.gr_native_core_math_mat4_identity.argtypes = [mat4_ptr]
    dll.gr_native_core_math_mat4_identity.restype = ctypes.c_int
    dll.gr_native_core_math_mat4_mul.argtypes = [mat4_ptr, mat4_ptr, mat4_ptr]
    dll.gr_native_core_math_mat4_mul.restype = ctypes.c_int
    dll.gr_native_core_math_mat3_normal.argtypes = [mat4_ptr, mat9_ptr]
    dll.gr_native_core_math_mat3_normal.restype = ctypes.c_int
    dll.gr_native_core_math_capabilities_json.argtypes = []
    dll.gr_native_core_math_capabilities_json.restype = ctypes.c_char_p
    return dll


def test_native_core_math_project_declares_gpu_math_files_and_exports() -> None:
    project = (PROJECT_DIR / "GhostRigger.Native.Core.Math.vcxproj").read_text(encoding="utf-8")
    filters = (PROJECT_DIR / "GhostRigger.Native.Core.Math.vcxproj.filters").read_text(encoding="utf-8")
    public_gpu = (PROJECT_DIR / "Public" / "GpuMath.h").read_text(encoding="utf-8")
    package_header = (PROJECT_DIR / "Public" / "GhostRiggerNativeCoreMath.h").read_text(encoding="utf-8")
    implementation = (PROJECT_DIR / "Private" / "GpuMath.cpp").read_text(encoding="utf-8")

    assert '<ClCompile Include="Private\\GpuMath.cpp" />' in project
    assert '<ClInclude Include="Public\\GpuMath.h" />' in project
    assert '<Filter>Public</Filter>' in filters
    assert '<Filter>Private</Filter>' in filters
    assert "namespace ghostrigger::native::nativecore::math::gpu_math" in public_gpu
    assert "matrix_from_pos_quat_np" in public_gpu
    assert "gr_native_core_math_mat4_perspective" in package_header
    assert "using namespace" not in implementation
    assert "pyfn_" not in implementation
    assert "phase15" not in implementation


def test_native_gpu_math_matches_python_gpu_math() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_math_dll()

    mat4 = Double16()
    mat3 = Double9()

    pos = (10.0, -6.0, 2.5)
    quat = (0.2, 0.5, 0.1, 0.84)
    assert dll.gr_native_core_math_matrix_from_pos_quat_np(_vec3(pos), _vec4(quat), mat4) == 1
    expected_matrix = gpu_math._matrix_from_pos_quat_np(pos, quat)
    _assert_close_tuple(_tuple16(mat4), tuple(float(v) for v in expected_matrix.flatten()))

    assert dll.gr_native_core_math_mat4_perspective(1.15, 1.7, 0.1, 1250.0, mat4) == 1
    expected_perspective = gpu_math._mat4_perspective(1.15, 1.7, 0.1, 1250.0)
    _assert_close_tuple(_tuple16(mat4), tuple(float(v) for v in expected_perspective.flatten()))

    assert dll.gr_native_core_math_mat4_lookat(_vec3((2.0, 4.0, 6.0)), _vec3((5.0, 7.0, 10.0)), _vec3((0.0, 0.0, 1.0)), mat4) == 1
    expected_lookat = gpu_math._mat4_lookat((2.0, 4.0, 6.0), (5.0, 7.0, 10.0), (0.0, 0.0, 1.0))
    _assert_close_tuple(_tuple16(mat4), tuple(float(v) for v in expected_lookat.flatten()))

    assert dll.gr_native_core_math_mat4_identity(mat4) == 1
    _assert_close_tuple(_tuple16(mat4), tuple(float(v) for v in gpu_math._mat4_identity().flatten()))

    identity = _mat4(gpu_math._mat4_identity().flatten())
    lookat_matrix = _mat4(expected_lookat.flatten())
    assert dll.gr_native_core_math_mat4_mul(identity, lookat_matrix, mat4) == 1
    expected_mul = gpu_math._mat4_identity() @ expected_lookat
    _assert_close_tuple(_tuple16(mat4), tuple(float(v) for v in expected_mul.flatten()))

    assert dll.gr_native_core_math_mat3_normal(lookat_matrix, mat3) == 1
    expected_normal = gpu_math._mat3_normal(expected_lookat)
    _assert_close_tuple(_tuple9(mat3), tuple(float(v) for v in expected_normal.flatten()))


def test_native_math_capabilities_json_documents_gpu_math_scope() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_math_dll()
    capabilities = json.loads(dll.gr_native_core_math_capabilities_json().decode("utf-8"))
    assert capabilities["gpu_math_native"] is True
    assert capabilities["gpu_math_schema"] == "gpu_math.v1"
