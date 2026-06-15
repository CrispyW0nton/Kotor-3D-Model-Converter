from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path

from src.adapters.gpu import moderngl_context


ROOT = Path(__file__).resolve().parents[1]
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Adapters.Hardware.GPU.dll"


def _load_dll() -> ctypes.CDLL:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = ctypes.CDLL(str(DLL_PATH))
    dll.gr_adapters_gpu_capabilities_json.argtypes = []
    dll.gr_adapters_gpu_capabilities_json.restype = ctypes.c_char_p
    dll.gr_adapters_gpu_gl_backend_candidates_json.argtypes = [ctypes.c_char_p]
    dll.gr_adapters_gpu_gl_backend_candidates_json.restype = ctypes.c_char_p
    dll.gr_adapters_gpu_light_kind_code.argtypes = [ctypes.c_char_p, ctypes.c_int]
    dll.gr_adapters_gpu_light_kind_code.restype = ctypes.c_int
    return dll


def _candidates(dll: ctypes.CDLL, os_name: str) -> list[str]:
    return json.loads(dll.gr_adapters_gpu_gl_backend_candidates_json(os_name.encode("utf-8")))


def test_native_gl_backend_candidates_match_python_for_platform_names(monkeypatch) -> None:
    monkeypatch.delenv("GHOSTRIGGER_GL_BACKEND", raising=False)
    dll = _load_dll()

    assert _candidates(dll, "nt") == list(moderngl_context._python_gl_context_backend_candidates("nt"))
    assert _candidates(dll, "posix") == list(moderngl_context._python_gl_context_backend_candidates("posix"))
    assert _candidates(dll, "java") == list(moderngl_context._python_gl_context_backend_candidates("java"))


def test_native_gl_backend_candidates_honor_env_override(monkeypatch) -> None:
    monkeypatch.setenv("GHOSTRIGGER_GL_BACKEND", " EGL ")
    dll = _load_dll()

    assert _candidates(dll, "nt") == ["egl"]


def test_native_light_kind_code_matches_python_contract() -> None:
    dll = _load_dll()

    assert dll.gr_adapters_gpu_light_kind_code(b"ambient", 0) == 4
    assert dll.gr_adapters_gpu_light_kind_code(b"point", 1) == 4
    assert dll.gr_adapters_gpu_light_kind_code(b"directional", 0) == 2
    assert dll.gr_adapters_gpu_light_kind_code(b"area", 0) == 3
    assert dll.gr_adapters_gpu_light_kind_code(b"spot", 0) == 1
    assert dll.gr_adapters_gpu_light_kind_code(b"point", 0) == 0
    assert dll.gr_adapters_gpu_light_kind_code(None, 0) == 0


def test_native_gpu_capabilities_document_contract_scope() -> None:
    dll = _load_dll()
    capabilities = json.loads(dll.gr_adapters_gpu_capabilities_json().decode("utf-8"))
    assert capabilities["gpu_adapter_contracts_native"] is True
    assert capabilities["gpu_runtime_python_fallback"] is True
    assert capabilities["python_fallback_required"] is True
