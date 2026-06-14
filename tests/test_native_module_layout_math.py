from __future__ import annotations

import ctypes
import math
from pathlib import Path

from src.math.module_layout_math import module_anchor_relative_position


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "native" / "GhostRigger.Native.Core.Math"
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Native.Core.Math.dll"


Double3 = ctypes.c_double * 3


def _vec3(values: tuple[float, float, float]) -> Double3:
    return Double3(*values)


def _tuple3(values: Double3) -> tuple[float, float, float]:
    return (values[0], values[1], values[2])


def _load_math_dll() -> ctypes.CDLL:
    dll = ctypes.CDLL(str(DLL_PATH))
    vec3_ptr = ctypes.POINTER(ctypes.c_double)
    dll.gr_native_core_math_module_anchor_relative_position.argtypes = [
        vec3_ptr,
        vec3_ptr,
        vec3_ptr,
        vec3_ptr,
    ]
    dll.gr_native_core_math_module_anchor_relative_position.restype = ctypes.c_int
    return dll


def test_native_core_math_project_declares_module_layout_math_files_and_exports() -> None:
    project = (PROJECT_DIR / "GhostRigger.Native.Core.Math.vcxproj").read_text(encoding="utf-8")
    filters = (PROJECT_DIR / "GhostRigger.Native.Core.Math.vcxproj.filters").read_text(encoding="utf-8")
    public_header = (PROJECT_DIR / "Public" / "ModuleLayoutMath.h").read_text(encoding="utf-8")
    package_header = (PROJECT_DIR / "Public" / "GhostRiggerNativeCoreMath.h").read_text(encoding="utf-8")
    implementation = (PROJECT_DIR / "Private" / "ModuleLayoutMath.cpp").read_text(encoding="utf-8")

    assert '<ClInclude Include="Public\\ModuleLayoutMath.h" />' in project
    assert '<ClCompile Include="Private\\ModuleLayoutMath.cpp" />' in project
    assert '<Filter>Public</Filter>' in filters
    assert '<Filter>Private</Filter>' in filters
    assert "namespace ghostrigger::native::nativecore::math::module_layout_math" in public_header
    assert "namespace ghostrigger::native::nativecore::math::module_layout_math" in implementation
    assert "gr_native_core_math_module_anchor_relative_position" in package_header
    assert "phase15" not in public_header
    assert "pyfn_" not in implementation
    assert "using namespace" not in implementation


def test_native_module_anchor_relative_position_matches_python_module_layout_math() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_math_dll()
    room = (32.0, -8.5, 4.0)
    anchor_lyt = (10.0, -2.5, 1.0)
    anchor_scene = (100.0, 50.0, -3.0)
    out = Double3()

    assert dll.gr_native_core_math_module_anchor_relative_position(
        _vec3(room),
        _vec3(anchor_lyt),
        _vec3(anchor_scene),
        out,
    ) == 1
    expected = module_anchor_relative_position(room, anchor_lyt, anchor_scene)
    for actual_value, expected_value in zip(_tuple3(out), expected):
        assert math.isclose(actual_value, expected_value, rel_tol=1.0e-9, abs_tol=1.0e-9)
