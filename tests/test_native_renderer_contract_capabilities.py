from __future__ import annotations

import ctypes
import json
from pathlib import Path

from src.core.rendering.renderer_capabilities import (
    DIAGNOSTIC_DISPLAY_MODES,
    MODERNGL_DISPLAY_MODES,
    WGPU_DISPLAY_MODES,
    WGPU_FALLBACK_DISPLAY_MODES,
    RendererCapabilities,
)
from src.core.rendering.viewport_display import normalize_display_mode


ROOT = Path(__file__).resolve().parents[1]
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Graphics.Renderer.Shared.Contracts.dll"


def _load_dll() -> ctypes.CDLL:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = ctypes.CDLL(str(DLL_PATH))
    dll.gr_renderer_contracts_capabilities_json.argtypes = []
    dll.gr_renderer_contracts_capabilities_json.restype = ctypes.c_char_p
    dll.gr_renderer_contracts_normalize_display_mode.argtypes = [ctypes.c_char_p]
    dll.gr_renderer_contracts_normalize_display_mode.restype = ctypes.c_char_p
    dll.gr_renderer_contracts_moderngl_display_modes_json.argtypes = []
    dll.gr_renderer_contracts_moderngl_display_modes_json.restype = ctypes.c_char_p
    dll.gr_renderer_contracts_wgpu_display_modes_json.argtypes = []
    dll.gr_renderer_contracts_wgpu_display_modes_json.restype = ctypes.c_char_p
    dll.gr_renderer_contracts_wgpu_fallback_display_modes_json.argtypes = []
    dll.gr_renderer_contracts_wgpu_fallback_display_modes_json.restype = ctypes.c_char_p
    dll.gr_renderer_contracts_diagnostic_display_modes_json.argtypes = []
    dll.gr_renderer_contracts_diagnostic_display_modes_json.restype = ctypes.c_char_p
    dll.gr_renderer_contracts_status_text.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p]
    dll.gr_renderer_contracts_status_text.restype = ctypes.c_char_p
    dll.gr_renderer_contracts_supports_display_mode.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p]
    dll.gr_renderer_contracts_supports_display_mode.restype = ctypes.c_int
    return dll


def _text(value: bytes) -> str:
    return value.decode("utf-8")


def test_native_display_mode_normalization_matches_python_aliases() -> None:
    dll = _load_dll()

    for raw in ["wire", "hidden-line", "flat", "smooth", "texture", "lightmapped", "realistic", "bounds", "normals", "uv", ""]:
        assert _text(dll.gr_renderer_contracts_normalize_display_mode(raw.encode("utf-8"))) == normalize_display_mode(raw).value


def test_native_renderer_display_mode_lists_match_python_contracts() -> None:
    dll = _load_dll()

    assert tuple(json.loads(dll.gr_renderer_contracts_moderngl_display_modes_json().decode("utf-8"))) == MODERNGL_DISPLAY_MODES
    assert tuple(json.loads(dll.gr_renderer_contracts_wgpu_display_modes_json().decode("utf-8"))) == WGPU_DISPLAY_MODES
    assert json.loads(dll.gr_renderer_contracts_wgpu_fallback_display_modes_json().decode("utf-8")) == WGPU_FALLBACK_DISPLAY_MODES
    assert tuple(json.loads(dll.gr_renderer_contracts_diagnostic_display_modes_json().decode("utf-8"))) == DIAGNOSTIC_DISPLAY_MODES


def test_native_renderer_status_and_support_checks_match_python_contract() -> None:
    dll = _load_dll()
    caps = RendererCapabilities(
        backend_id="native_test",
        name="Native Test",
        available=True,
        diagnostic_only=False,
        supported_display_modes=("solid", "textured"),
    )

    assert _text(dll.gr_renderer_contracts_status_text(1, 0, b"")) == caps.status_text()
    assert _text(dll.gr_renderer_contracts_status_text(1, 1, b"")) == "Available (diagnostic only)"
    assert _text(dll.gr_renderer_contracts_status_text(0, 0, b"driver missing")) == "Unavailable: driver missing"
    assert _text(dll.gr_renderer_contracts_status_text(0, 0, b"")) == "Unavailable: not supported"
    assert dll.gr_renderer_contracts_supports_display_mode(1, 0, b"solid,textured", b"texture") == int(
        caps.supports_display_mode("texture")
    )
    assert dll.gr_renderer_contracts_supports_display_mode(1, 0, b"solid,textured", b"wireframe") == 0
    assert dll.gr_renderer_contracts_supports_display_mode(0, 0, b"solid,textured", b"solid") == 0
    assert dll.gr_renderer_contracts_supports_display_mode(1, 0, b"", b"uv") == 1
    assert dll.gr_renderer_contracts_supports_display_mode(1, 1, b"", b"uv") == 0


def test_native_renderer_contract_capabilities_document_scope() -> None:
    dll = _load_dll()
    capabilities = json.loads(dll.gr_renderer_contracts_capabilities_json().decode("utf-8"))
    assert capabilities["renderer_capability_contracts_native"] is True
    assert capabilities["renderer_runtime_python_fallback"] is True
    assert capabilities["python_fallback_required"] is True
