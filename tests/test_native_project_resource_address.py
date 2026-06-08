from __future__ import annotations

import ctypes
import json
from pathlib import Path

from src.core.project.resource_address import ResourceAddress, SUPPORTED_RESOURCE_ADDRESS_SCHEMES


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "native" / "GhostRigger.Project"
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Project.dll"


def _bytes(value: str | None) -> bytes | None:
    if value is None:
        return None
    return value.encode("utf-8")


def _load_project_dll() -> ctypes.CDLL:
    dll = ctypes.CDLL(str(DLL_PATH))
    dll.gr_project_resource_address_supported_schemes_json.restype = ctypes.c_char_p
    dll.gr_project_resource_address_contracts_schema_json.restype = ctypes.c_char_p
    dll.gr_project_resource_address_is_supported_scheme.argtypes = [ctypes.c_char_p]
    dll.gr_project_resource_address_is_supported_scheme.restype = ctypes.c_int
    for name in (
        "gr_project_resource_address_stable_key",
        "gr_project_resource_address_display_name",
        "gr_project_resource_address_to_json",
    ):
        function = getattr(dll, name)
        function.argtypes = [ctypes.c_char_p] * 9
        function.restype = ctypes.c_char_p
    return dll


def test_project_declares_native_resource_address_files() -> None:
    project = (PROJECT_DIR / "GhostRigger.Project.vcxproj").read_text(encoding="utf-8")
    filters = (PROJECT_DIR / "GhostRigger.Project.vcxproj.filters").read_text(encoding="utf-8")
    header = (PROJECT_DIR / "Public" / "ResourceAddress.h").read_text(encoding="utf-8")
    implementation = (PROJECT_DIR / "Private" / "ResourceAddress.cpp").read_text(encoding="utf-8")

    assert '<ClInclude Include="Public\\ResourceAddress.h" />' in project
    assert '<ClCompile Include="Private\\ResourceAddress.cpp" />' in project
    assert '<Filter>Public</Filter>' in filters
    assert '<Filter>Private</Filter>' in filters
    assert "namespace ghostrigger::project::core::project::resource_address" in header
    assert "namespace ghostrigger::project::core::project::resource_address" in implementation
    assert "using namespace" not in implementation
    assert "phase15" not in implementation
    assert "pyfn_" not in implementation


def test_project_resource_address_exports_are_declared() -> None:
    header = (PROJECT_DIR / "Public" / "GhostRiggerProject.h").read_text(encoding="utf-8")
    implementation = (PROJECT_DIR / "Private" / "GhostRiggerProject.cpp").read_text(encoding="utf-8")

    assert "gr_project_resource_address_supported_schemes_json" in header
    assert "gr_project_resource_address_stable_key" in header
    assert "resource_address_contracts" in implementation
    assert "native_implementation_enabled\":true" in implementation


def test_project_resource_address_release_dll_matches_python_behavior() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_project_dll()

    schemes = json.loads(dll.gr_project_resource_address_supported_schemes_json().decode("utf-8"))
    assert set(schemes) == SUPPORTED_RESOURCE_ADDRESS_SCHEMES
    assert dll.gr_project_resource_address_is_supported_scheme(b" MODULE_RESOURCE ") == 1
    assert dll.gr_project_resource_address_is_supported_scheme(b"bogus") == 0

    address = ResourceAddress(
        scheme=" MODULE_RESOURCE ",
        game=" K1 ",
        module_id=" tar_m09aa ",
        resref=" gr_beklead ",
        restype=".utc",
        layer=" Project ",
    )
    args = (
        _bytes(" MODULE_RESOURCE "),
        _bytes(" K1 "),
        _bytes(" tar_m09aa "),
        _bytes(" gr_beklead "),
        _bytes(".utc"),
        _bytes(" Project "),
        None,
        None,
        None,
    )

    assert dll.gr_project_resource_address_stable_key(*args).decode("utf-8") == address.stable_key()
    assert dll.gr_project_resource_address_display_name(*args).decode("utf-8") == address.display_name()
    assert json.loads(dll.gr_project_resource_address_to_json(*args).decode("utf-8")) == address.to_dict()


def test_project_resource_address_display_name_uses_file_basename_like_python() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_project_dll()

    address = ResourceAddress(scheme="local_file", path="C:/mods/kotor/example.utc")
    args = (_bytes("local_file"), None, None, None, None, None, _bytes("C:/mods/kotor/example.utc"), None, None)

    assert dll.gr_project_resource_address_stable_key(*args).decode("utf-8") == address.stable_key()
    assert dll.gr_project_resource_address_display_name(*args).decode("utf-8") == address.display_name()


def test_project_resource_address_documents_python_fallback_scope() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_project_dll()

    schema = json.loads(dll.gr_project_resource_address_contracts_schema_json().decode("utf-8"))
    assert schema["schema"] == "project_resource_address_native.v1"
    assert "stable key formatting" in schema["native_scope"]
    assert "project model graph serialization" in schema["python_fallback"]
