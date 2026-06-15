from __future__ import annotations

import ctypes
import json
from pathlib import Path

from src.io.fbx import fbx_sdk_paths, fbx_sdk_setup


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "native" / "GhostRigger.Domain.Core.IO"
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Domain.Core.IO.dll"


def _load_io_dll() -> ctypes.CDLL:
    dll = ctypes.CDLL(str(DLL_PATH))
    dll.gr_io_fbx_sdk_download_url.restype = ctypes.c_char_p
    dll.gr_io_fbx_sdk_licence_notice.restype = ctypes.c_char_p
    dll.gr_io_fbx_sdk_recommended_fix.argtypes = [ctypes.c_char_p]
    dll.gr_io_fbx_sdk_recommended_fix.restype = ctypes.c_char_p
    dll.gr_io_fbx_sdk_settings_contracts_schema_json.restype = ctypes.c_char_p
    return dll


def test_io_declares_native_fbx_sdk_settings_files() -> None:
    project = (PROJECT_DIR / "GhostRigger.Domain.Core.IO.vcxproj").read_text(encoding="utf-8")
    filters = (PROJECT_DIR / "GhostRigger.Domain.Core.IO.vcxproj.filters").read_text(encoding="utf-8")
    header = (PROJECT_DIR / "Public" / "FbxSdkSettings.h").read_text(encoding="utf-8")
    implementation = (PROJECT_DIR / "Private" / "FbxSdkSettings.cpp").read_text(encoding="utf-8")

    assert '<ClInclude Include="Public\\FbxSdkSettings.h" />' in project
    assert '<ClCompile Include="Private\\FbxSdkSettings.cpp" />' in project
    assert '<Filter>Public</Filter>' in filters
    assert '<Filter>Private</Filter>' in filters
    assert "namespace ghostrigger::domain::core::io::fbx::sdk_settings" in header
    assert "namespace ghostrigger::domain::core::io::fbx::sdk_settings" in implementation
    assert "using namespace" not in implementation
    assert "phase15" not in implementation
    assert "pyfn_" not in implementation


def test_native_fbx_sdk_static_contracts_match_python() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_io_dll()

    assert dll.gr_io_fbx_sdk_download_url().decode("utf-8") == fbx_sdk_paths.FBX_DOWNLOAD_URL
    assert dll.gr_io_fbx_sdk_licence_notice().decode("utf-8") == fbx_sdk_setup.LICENCE_NOTICE


def test_native_fbx_sdk_recommended_fix_matches_python_classifier() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_io_dll()

    samples = [
        "ImportError: DLL load failed while importing fbx",
        "OSError: wrong architecture",
        "ModuleNotFoundError: No module named 'fbx'",
        "some unrelated validation failure",
    ]
    for sample in samples:
        assert dll.gr_io_fbx_sdk_recommended_fix(sample.encode("utf-8")).decode("utf-8") == fbx_sdk_paths._recommended_fix(sample)


def test_native_fbx_sdk_settings_documents_python_fallback_scope() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_io_dll()

    schema = json.loads(dll.gr_io_fbx_sdk_settings_contracts_schema_json().decode("utf-8"))
    assert schema["schema"] == "io_fbx_sdk_settings_native.v1"
    assert "FBX SDK recommended-fix classification" in schema["native_scope"]
    assert "importlib FBX probing" in schema["python_fallback"]
