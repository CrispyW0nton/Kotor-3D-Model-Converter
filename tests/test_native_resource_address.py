from __future__ import annotations

import ctypes
import json
from pathlib import Path

from src.core.project.resource_address import ResourceAddress, SUPPORTED_RESOURCE_ADDRESS_SCHEMES


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "native" / "GhostRigger.Runtime.Shared"
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Runtime.Shared.dll"


def _bytes(value: str | None) -> bytes | None:
    if value is None:
        return None
    return value.encode("utf-8")


def _load_descriptors_dll() -> ctypes.CDLL:
    dll = ctypes.CDLL(str(DLL_PATH))
    dll.gr_runtime_shared_descriptors_resource_address_supported_schemes_json.restype = ctypes.c_char_p
    dll.gr_runtime_shared_descriptors_resource_address_is_supported_scheme.argtypes = [ctypes.c_char_p]
    dll.gr_runtime_shared_descriptors_resource_address_is_supported_scheme.restype = ctypes.c_int
    for name in (
        "gr_runtime_shared_descriptors_resource_address_stable_key",
        "gr_runtime_shared_descriptors_resource_address_display_name",
        "gr_runtime_shared_descriptors_resource_address_to_json",
    ):
        function = getattr(dll, name)
        function.argtypes = [ctypes.c_char_p] * 9
        function.restype = ctypes.c_char_p
    return dll


def test_runtime_shared_descriptors_project_declares_native_resource_address_files() -> None:
    project = (PROJECT_DIR / "GhostRigger.Runtime.Shared.vcxproj").read_text(encoding="utf-8")
    filters = (PROJECT_DIR / "GhostRigger.Runtime.Shared.vcxproj.filters").read_text(encoding="utf-8")
    header = (PROJECT_DIR / "Public" / "ResourceAddress.h").read_text(encoding="utf-8")
    implementation = (PROJECT_DIR / "Private" / "ResourceAddress.cpp").read_text(encoding="utf-8")

    assert '<ClInclude Include="Public\\ResourceAddress.h" />' in project
    assert '<ClCompile Include="Private\\ResourceAddress.cpp" />' in project
    assert '<Filter>Public</Filter>' in filters
    assert '<Filter>Private</Filter>' in filters
    assert "namespace ghostrigger::runtime::shared::descriptors::resource_address" in header
    assert "namespace ghostrigger::runtime::shared::descriptors::resource_address" in implementation
    assert "phase15" not in header
    assert "phase15" not in implementation


def test_native_resource_address_exports_are_declared_on_shared_descriptor_boundary() -> None:
    header = (PROJECT_DIR / "Public" / "GhostRiggerRuntimeSharedDescriptors.h").read_text(encoding="utf-8")
    implementation = (PROJECT_DIR / "Private" / "GhostRiggerRuntimeSharedDescriptors.cpp").read_text(encoding="utf-8")

    assert "gr_runtime_shared_descriptors_resource_address_supported_schemes_json" in header
    assert "gr_runtime_shared_descriptors_resource_address_stable_key" in header
    assert "native_resource_address" in implementation
    assert "python_fallback_secondary" in implementation


def test_native_resource_address_release_dll_matches_python_resource_address_behavior() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_descriptors_dll()

    schemes = json.loads(dll.gr_runtime_shared_descriptors_resource_address_supported_schemes_json().decode("utf-8"))
    assert set(schemes) == SUPPORTED_RESOURCE_ADDRESS_SCHEMES
    assert dll.gr_runtime_shared_descriptors_resource_address_is_supported_scheme(b" MODULE_RESOURCE ") == 1
    assert dll.gr_runtime_shared_descriptors_resource_address_is_supported_scheme(b"bogus") == 0

    address = ResourceAddress(
        scheme=" MODULE_RESOURCE ",
        game=" K2 ",
        module_id=" 001EBO ",
        resref=" n_darthmalak ",
        restype=".mdl",
        layer=" RIM ",
    )

    args = (
        _bytes(" MODULE_RESOURCE "),
        _bytes(" K2 "),
        _bytes(" 001EBO "),
        _bytes(" n_darthmalak "),
        _bytes(".mdl"),
        _bytes(" RIM "),
        None,
        None,
        None,
    )
    assert dll.gr_runtime_shared_descriptors_resource_address_stable_key(*args).decode("utf-8") == address.stable_key()
    assert (
        dll.gr_runtime_shared_descriptors_resource_address_display_name(*args).decode("utf-8")
        == address.display_name()
    )

    payload = json.loads(dll.gr_runtime_shared_descriptors_resource_address_to_json(*args).decode("utf-8"))
    assert payload == address.to_dict()


def test_native_resource_address_display_name_uses_file_basename_like_python() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_descriptors_dll()

    address = ResourceAddress(scheme="local_file", path="C:/mods/kotor/example.utc")
    args = (_bytes("local_file"), None, None, None, None, None, _bytes("C:/mods/kotor/example.utc"), None, None)

    assert dll.gr_runtime_shared_descriptors_resource_address_stable_key(*args).decode("utf-8") == address.stable_key()
    assert (
        dll.gr_runtime_shared_descriptors_resource_address_display_name(*args).decode("utf-8")
        == address.display_name()
    )
