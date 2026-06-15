from __future__ import annotations

import ctypes
import json
import math
from pathlib import Path

from src.core.rendering import color_utils, renderer_backend, viewport_display, viewport_navigation


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "native" / "GhostRigger.Domain.Core.Rendering"
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Domain.Core.Rendering.dll"


Double3 = ctypes.c_double * 3


def _load_rendering_dll() -> ctypes.CDLL:
    dll = ctypes.CDLL(str(DLL_PATH))
    dll.gr_rendering_normalize_renderer_backend.argtypes = [ctypes.c_char_p]
    dll.gr_rendering_normalize_renderer_backend.restype = ctypes.c_char_p
    dll.gr_rendering_renderer_backend_label.argtypes = [ctypes.c_char_p]
    dll.gr_rendering_renderer_backend_label.restype = ctypes.c_char_p
    dll.gr_rendering_normalize_display_mode.argtypes = [ctypes.c_char_p]
    dll.gr_rendering_normalize_display_mode.restype = ctypes.c_char_p
    dll.gr_rendering_display_mode_values_json.argtypes = []
    dll.gr_rendering_display_mode_values_json.restype = ctypes.c_char_p
    dll.gr_rendering_normalize_viewport_navigation_profile.argtypes = [ctypes.c_char_p]
    dll.gr_rendering_normalize_viewport_navigation_profile.restype = ctypes.c_char_p
    dll.gr_rendering_viewport_navigation_profile_label.argtypes = [ctypes.c_char_p]
    dll.gr_rendering_viewport_navigation_profile_label.restype = ctypes.c_char_p
    dll.gr_rendering_viewport_navigation_profile_summary.argtypes = [ctypes.c_char_p]
    dll.gr_rendering_viewport_navigation_profile_summary.restype = ctypes.c_char_p
    dll.gr_rendering_viewport_navigation_profiles_json.argtypes = []
    dll.gr_rendering_viewport_navigation_profiles_json.restype = ctypes.c_char_p
    dll.gr_rendering_hex_to_rgb_float.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]
    dll.gr_rendering_hex_to_rgb_float.restype = ctypes.c_int
    dll.gr_rendering_capabilities_json.argtypes = []
    dll.gr_rendering_capabilities_json.restype = ctypes.c_char_p
    dll.gr_rendering_contracts_schema_json.argtypes = []
    dll.gr_rendering_contracts_schema_json.restype = ctypes.c_char_p
    return dll


def _tuple3(values: Double3) -> tuple[float, float, float]:
    return (values[0], values[1], values[2])


def _assert_close_tuple(actual: tuple[float, float, float], expected: tuple[float, float, float]) -> None:
    for actual_value, expected_value in zip(actual, expected):
        assert math.isclose(actual_value, expected_value, rel_tol=1.0e-9, abs_tol=1.0e-9)


def test_rendering_project_declares_contract_files_and_exports() -> None:
    project = (PROJECT_DIR / "GhostRigger.Domain.Core.Rendering.vcxproj").read_text(encoding="utf-8")
    filters = (PROJECT_DIR / "GhostRigger.Domain.Core.Rendering.vcxproj.filters").read_text(encoding="utf-8")
    package_header = (PROJECT_DIR / "Public" / "GhostRiggerRendering.h").read_text(encoding="utf-8")
    public_header = (PROJECT_DIR / "Public" / "RenderingContracts.h").read_text(encoding="utf-8")
    implementation = (PROJECT_DIR / "Private" / "RenderingContracts.cpp").read_text(encoding="utf-8")

    assert '<ClInclude Include="Public\\RenderingContracts.h" />' in project
    assert '<ClCompile Include="Private\\RenderingContracts.cpp" />' in project
    assert '<Filter>Public</Filter>' in filters
    assert '<Filter>Private</Filter>' in filters
    assert "gr_rendering_normalize_renderer_backend" in package_header
    assert "gr_rendering_normalize_viewport_navigation_profile" in package_header
    assert "namespace ghostrigger::domain::core::rendering::core::rendering::rendering_contracts" in public_header
    assert "namespace ghostrigger::domain::core::rendering::core::rendering::rendering_contracts" in implementation
    assert "phase15" not in public_header
    assert "pyfn_" not in implementation
    assert "using namespace" not in implementation


def test_native_renderer_backend_contracts_match_python() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_rendering_dll()

    for value in [
        "auto",
        "modern-gl",
        "OpenGL",
        "wgpu",
        "native/d3d12",
        "pygfx",
        "null",
        "not-real",
    ]:
        expected = renderer_backend._python_supported_renderer_backend(value)
        actual = dll.gr_rendering_normalize_renderer_backend(value.encode("utf-8")).decode("utf-8")
        label = dll.gr_rendering_renderer_backend_label(value.encode("utf-8")).decode("utf-8")
        assert actual == expected.value
        assert label == renderer_backend._python_renderer_backend_label(expected)


def test_native_viewport_display_contracts_match_python() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_rendering_dll()

    for value in [
        "wire",
        "hidden-line",
        "flat",
        "smooth",
        "texture",
        "lightmapped",
        "realistic",
        "bounds",
        "normals",
        "uv",
        "not-real",
    ]:
        actual = dll.gr_rendering_normalize_display_mode(value.encode("utf-8")).decode("utf-8")
        assert actual == viewport_display._python_normalize_display_mode(value).value

    native_values = json.loads(dll.gr_rendering_display_mode_values_json().decode("utf-8"))
    assert tuple(native_values) == viewport_display.display_mode_values(viewport_display.ViewportDisplayMode)


def test_native_viewport_navigation_contracts_match_python() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_rendering_dll()

    for value in [
        "",
        "3dmax",
        "3ds",
        "max",
        "3dsmax",
        "3ds max",
        "3ds_max",
        "3ds-max",
        "blender",
        "maya",
        "not-real",
    ]:
        expected = viewport_navigation._python_normalize_viewport_navigation_profile(value)
        actual = dll.gr_rendering_normalize_viewport_navigation_profile(value.encode("utf-8")).decode("utf-8")
        label = dll.gr_rendering_viewport_navigation_profile_label(value.encode("utf-8")).decode("utf-8")
        summary = dll.gr_rendering_viewport_navigation_profile_summary(value.encode("utf-8")).decode("utf-8")
        assert actual == expected
        assert label == viewport_navigation._python_viewport_profile_label(value)
        assert summary == viewport_navigation.VIEWPORT_NAVIGATION_PROFILES[expected].summary

    native_profiles = json.loads(dll.gr_rendering_viewport_navigation_profiles_json().decode("utf-8"))
    assert native_profiles["default"] == viewport_navigation.DEFAULT_VIEWPORT_NAVIGATION_PROFILE
    assert tuple(profile["key"] for profile in native_profiles["profiles"]) == tuple(
        viewport_navigation.VIEWPORT_NAVIGATION_PROFILES
    )


def test_native_hex_to_rgb_float_matches_python_color_utils() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_rendering_dll()
    fallback = (0.25, 0.5, 0.75)

    for value in ["#112233", "AABBCC", "bad", "#123", "#GGGGGG"]:
        out = Double3()
        assert dll.gr_rendering_hex_to_rgb_float(value.encode("utf-8"), Double3(*fallback), out) == 1
        _assert_close_tuple(_tuple3(out), color_utils._python_hex_to_rgb_float(value, fallback))


def test_python_rendering_helpers_prefer_native_contract(monkeypatch) -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_rendering_dll()
    monkeypatch.setattr(renderer_backend, "native_rendering", lambda: dll)
    monkeypatch.setattr(viewport_display, "native_rendering", lambda: dll)
    monkeypatch.setattr(viewport_navigation, "native_rendering", lambda: dll)
    monkeypatch.setattr(color_utils, "native_rendering", lambda: dll)

    assert renderer_backend.supported_renderer_backend("native/d3d12") is renderer_backend.RendererBackend.WGPU_D3D12
    assert renderer_backend.renderer_backend_label("pygfx") == "pygfx (WGPU)"
    assert viewport_display.normalize_display_mode("hidden-line") is viewport_display.ViewportDisplayMode.HIDDEN_LINE
    assert viewport_display.display_mode_values(viewport_display.ViewportDisplayMode)[0] == "wireframe"
    assert viewport_navigation.normalize_viewport_navigation_profile("3ds max") == "3dsmax"
    assert viewport_navigation.viewport_profile_label("blender") == "Blender"
    _assert_close_tuple(color_utils._hex_to_rgb_float("#112233", (0.0, 0.0, 0.0)), (17 / 255.0, 34 / 255.0, 51 / 255.0))


def test_python_rendering_helpers_fall_back_when_native_missing(monkeypatch) -> None:
    monkeypatch.setattr(renderer_backend, "native_rendering", lambda: None)
    monkeypatch.setattr(viewport_display, "native_rendering", lambda: None)
    monkeypatch.setattr(viewport_navigation, "native_rendering", lambda: None)
    monkeypatch.setattr(color_utils, "native_rendering", lambda: None)

    assert renderer_backend.supported_renderer_backend("native/d3d12") is renderer_backend.RendererBackend.WGPU_D3D12
    assert renderer_backend.renderer_backend_label("pygfx") == "pygfx (WGPU)"
    assert viewport_display.normalize_display_mode("hidden-line") is viewport_display.ViewportDisplayMode.HIDDEN_LINE
    assert viewport_display.display_mode_values(viewport_display.ViewportDisplayMode)[0] == "wireframe"
    assert viewport_navigation.normalize_viewport_navigation_profile("3ds max") == "3dsmax"
    assert viewport_navigation.viewport_profile_label("blender") == "Blender"
    _assert_close_tuple(color_utils._hex_to_rgb_float("#112233", (0.0, 0.0, 0.0)), (17 / 255.0, 34 / 255.0, 51 / 255.0))


def test_native_rendering_capabilities_document_python_fallback_scope() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_rendering_dll()

    capabilities = json.loads(dll.gr_rendering_capabilities_json().decode("utf-8"))
    schema = json.loads(dll.gr_rendering_contracts_schema_json().decode("utf-8"))

    assert capabilities["native_implementation_enabled"] is True
    assert capabilities["python_fallback_required"] is True
    assert "renderer_backend_contracts" in capabilities["capabilities"]
    assert "viewport_navigation_contracts" in capabilities["capabilities"]
    assert "viewport display mode normalization" in schema["native_scope"]
    assert "viewport navigation profile normalization" in schema["native_scope"]
    assert "GPU device/resource ownership" in schema["python_fallback"]
