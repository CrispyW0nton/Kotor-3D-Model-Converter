from __future__ import annotations

import ctypes
import json
from pathlib import Path

from src.core.game import game_library_ext


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "native" / "GhostRigger.Domain.Core.Game"
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Domain.Core.Game.dll"


def _load_game_dll() -> ctypes.CDLL:
    dll = ctypes.CDLL(str(DLL_PATH))
    dll.gr_game_resource_type_name.argtypes = [ctypes.c_int]
    dll.gr_game_resource_type_name.restype = ctypes.c_char_p
    dll.gr_game_resource_type_extension.argtypes = [ctypes.c_int]
    dll.gr_game_resource_type_extension.restype = ctypes.c_char_p
    dll.gr_game_capabilities_json.argtypes = []
    dll.gr_game_capabilities_json.restype = ctypes.c_char_p
    dll.gr_game_resource_type_contracts_schema_json.argtypes = []
    dll.gr_game_resource_type_contracts_schema_json.restype = ctypes.c_char_p
    return dll


def test_game_project_declares_resource_type_files_and_exports() -> None:
    project = (PROJECT_DIR / "GhostRigger.Domain.Core.Game.vcxproj").read_text(encoding="utf-8")
    filters = (PROJECT_DIR / "GhostRigger.Domain.Core.Game.vcxproj.filters").read_text(encoding="utf-8")
    package_header = (PROJECT_DIR / "Public" / "GhostRiggerGame.h").read_text(encoding="utf-8")
    public_header = (PROJECT_DIR / "Public" / "ResourceTypes.h").read_text(encoding="utf-8")
    implementation = (PROJECT_DIR / "Private" / "ResourceTypes.cpp").read_text(encoding="utf-8")

    assert '<ClInclude Include="Public\\ResourceTypes.h" />' in project
    assert '<ClCompile Include="Private\\ResourceTypes.cpp" />' in project
    assert '<Filter>Public</Filter>' in filters
    assert '<Filter>Private</Filter>' in filters
    assert "gr_game_resource_type_name" in package_header
    assert "namespace ghostrigger::domain::core::game::core::game::resource_types" in public_header
    assert "namespace ghostrigger::domain::core::game::core::game::resource_types" in implementation
    assert "phase15" not in public_header
    assert "pyfn_" not in implementation
    assert "using namespace" not in implementation


def test_native_resource_type_names_and_extensions_match_python_registry() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_game_dll()

    resource_types = sorted(set(game_library_ext.RES_NAMES) | set(game_library_ext.RES_EXT) | {0x1234, 0xFFFF})
    for resource_type in resource_types:
        native_name = dll.gr_game_resource_type_name(resource_type).decode("utf-8")
        native_ext = dll.gr_game_resource_type_extension(resource_type).decode("utf-8")
        assert native_name == game_library_ext.res_type_name(resource_type)
        assert native_ext == game_library_ext.res_type_ext(resource_type)


def test_native_game_capabilities_document_python_fallback_scope() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_game_dll()

    capabilities = json.loads(dll.gr_game_capabilities_json().decode("utf-8"))
    schema = json.loads(dll.gr_game_resource_type_contracts_schema_json().decode("utf-8"))

    assert capabilities["native_implementation_enabled"] is True
    assert capabilities["python_fallback_required"] is True
    assert "resource_type_lookup_contracts" in capabilities["capabilities"]
    assert "resource type id to extension lookup" in schema["native_scope"]
    assert "GFFReader binary parsing" in schema["python_fallback"]
