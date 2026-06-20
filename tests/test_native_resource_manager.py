from __future__ import annotations

import ctypes
import json
from pathlib import Path

from src.core.assets import resource_manager


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "native" / "GhostRigger.Core.Resources"
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Core.Resources.dll"


def _load_assets_dll() -> ctypes.CDLL:
    dll = ctypes.CDLL(str(DLL_PATH))
    dll.gr_assets_resource_key.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_ulonglong]
    dll.gr_assets_resource_key.restype = ctypes.c_int
    dll.gr_assets_texture_name_candidates_json.argtypes = [ctypes.c_char_p]
    dll.gr_assets_texture_name_candidates_json.restype = ctypes.c_char_p
    dll.gr_assets_extension_to_resource_type.argtypes = [ctypes.c_char_p]
    dll.gr_assets_extension_to_resource_type.restype = ctypes.c_int
    dll.gr_assets_resource_type_to_extension.argtypes = [ctypes.c_int]
    dll.gr_assets_resource_type_to_extension.restype = ctypes.c_char_p
    dll.gr_assets_capabilities_json.argtypes = []
    dll.gr_assets_capabilities_json.restype = ctypes.c_char_p
    dll.gr_assets_resource_manager_schema_json.argtypes = []
    dll.gr_assets_resource_manager_schema_json.restype = ctypes.c_char_p
    return dll


def _call_resource_key(dll: ctypes.CDLL, name: str, resource_type: int) -> str:
    output = ctypes.create_string_buffer(256)
    required = dll.gr_assets_resource_key(name.encode("utf-8"), resource_type, output, ctypes.sizeof(output))
    assert required > 0
    assert required <= ctypes.sizeof(output)
    return output.value.decode("utf-8")


def test_assets_project_declares_resource_manager_files_and_exports() -> None:
    project = (PROJECT_DIR / "GhostRigger.Core.Resources.vcxproj").read_text(encoding="utf-8")
    filters = (PROJECT_DIR / "GhostRigger.Core.Resources.vcxproj.filters").read_text(encoding="utf-8")
    package_header = (PROJECT_DIR / "Public" / "GhostRiggerAssets.h").read_text(encoding="utf-8")
    public_header = (PROJECT_DIR / "Public" / "ResourceManager.h").read_text(encoding="utf-8")
    implementation = (PROJECT_DIR / "Private" / "ResourceManager.cpp").read_text(encoding="utf-8")

    assert '<ClInclude Include="Public\\ResourceManager.h" />' in project
    assert '<ClCompile Include="Private\\ResourceManager.cpp" />' in project
    assert '<Filter>Public</Filter>' in filters
    assert '<Filter>Private</Filter>' in filters
    assert "gr_assets_resource_key" in package_header
    assert "namespace ghostrigger::core::assets::core::assets::resource_manager" in public_header
    assert "namespace ghostrigger::core::assets::core::assets::resource_manager" in implementation
    assert "phase15" not in public_header
    assert "pyfn_" not in implementation
    assert "using namespace" not in implementation


def test_native_resource_key_matches_python_resource_manager() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_assets_dll()

    for name, resource_type in [
        ("N_DarthMalak", resource_manager.RES_MDL),
        ("C_DREX01", resource_manager.RES_TPC),
        ("001EBO", resource_manager.RES_MOD),
        ("with space", resource_manager.RES_TXI),
    ]:
        assert _call_resource_key(dll, name, resource_type) == resource_manager._key(name, resource_type)


def test_native_texture_candidates_match_python_resource_manager() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_assets_dll()

    for name in ["", "  C_DREX01  ", "regular_texture", "c_drexl01"]:
        actual = json.loads(dll.gr_assets_texture_name_candidates_json(name.encode("utf-8")).decode("utf-8"))
        assert tuple(actual) == resource_manager._texture_name_candidates(name)


def test_native_resource_type_tables_match_python_resource_manager() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_assets_dll()

    for extension, resource_type in resource_manager.EXT_TO_TYPE.items():
        assert dll.gr_assets_extension_to_resource_type(extension.encode("utf-8")) == resource_type
        assert dll.gr_assets_extension_to_resource_type(f".{extension.upper()}".encode("utf-8")) == resource_type

    for resource_type, extension in resource_manager.TYPE_TO_EXT.items():
        assert dll.gr_assets_resource_type_to_extension(resource_type).decode("utf-8") == extension

    assert dll.gr_assets_extension_to_resource_type(b"notreal") == -1
    assert dll.gr_assets_resource_type_to_extension(999999).decode("utf-8") == ""


def test_native_resource_manager_capabilities_document_python_fallback_scope() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_assets_dll()

    capabilities = json.loads(dll.gr_assets_capabilities_json().decode("utf-8"))
    schema = json.loads(dll.gr_assets_resource_manager_schema_json().decode("utf-8"))

    assert capabilities["native_implementation_enabled"] is True
    assert capabilities["python_fallback_required"] is True
    assert "resource_manager_keys" in capabilities["capabilities"]
    assert schema["native_scope"] == ["_key", "_texture_name_candidates", "EXT_TO_TYPE", "TYPE_TO_EXT"]
    assert "BIF/ERF archive indexing" in schema["python_fallback"]
