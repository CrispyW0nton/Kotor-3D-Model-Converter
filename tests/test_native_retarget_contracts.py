from __future__ import annotations

import ctypes
import json
from pathlib import Path

import pytest

from src.core.retargeting import retarget_modes, retarget_output_naming


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "native" / "GhostRigger.Domain.Core.Retargeting"
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Domain.Core.Retargeting.dll"


def _load_retargeting_dll() -> ctypes.CDLL:
    dll = ctypes.CDLL(str(DLL_PATH))
    dll.gr_retargeting_coerce_mode.argtypes = [ctypes.c_char_p]
    dll.gr_retargeting_coerce_mode.restype = ctypes.c_char_p
    dll.gr_retargeting_is_kotor_output_mode.argtypes = [ctypes.c_char_p]
    dll.gr_retargeting_is_kotor_output_mode.restype = ctypes.c_int
    dll.gr_retargeting_mode_specs_json.argtypes = []
    dll.gr_retargeting_mode_specs_json.restype = ctypes.c_char_p
    dll.gr_retargeting_coerce_kotor_output_name_mode.argtypes = [ctypes.c_char_p]
    dll.gr_retargeting_coerce_kotor_output_name_mode.restype = ctypes.c_char_p
    dll.gr_retargeting_validate_custom_kotor_animation_name.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_ulonglong,
    ]
    dll.gr_retargeting_validate_custom_kotor_animation_name.restype = ctypes.c_int
    dll.gr_retargeting_validate_unreal_clip_name.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulonglong]
    dll.gr_retargeting_validate_unreal_clip_name.restype = ctypes.c_int
    dll.gr_retargeting_capabilities_json.argtypes = []
    dll.gr_retargeting_capabilities_json.restype = ctypes.c_char_p
    dll.gr_retargeting_contracts_schema_json.argtypes = []
    dll.gr_retargeting_contracts_schema_json.restype = ctypes.c_char_p
    return dll


def _call_string(function, value: str) -> str:
    output = ctypes.create_string_buffer(256)
    required = function(value.encode("utf-8"), output, ctypes.sizeof(output))
    assert required > 0
    assert required <= ctypes.sizeof(output)
    return output.value.decode("utf-8")


def test_retargeting_project_declares_contract_files_and_exports() -> None:
    project = (PROJECT_DIR / "GhostRigger.Domain.Core.Retargeting.vcxproj").read_text(encoding="utf-8")
    filters = (PROJECT_DIR / "GhostRigger.Domain.Core.Retargeting.vcxproj.filters").read_text(encoding="utf-8")
    package_header = (PROJECT_DIR / "Public" / "GhostRiggerRetargeting.h").read_text(encoding="utf-8")
    public_header = (PROJECT_DIR / "Public" / "RetargetContracts.h").read_text(encoding="utf-8")
    implementation = (PROJECT_DIR / "Private" / "RetargetContracts.cpp").read_text(encoding="utf-8")

    assert '<ClInclude Include="Public\\RetargetContracts.h" />' in project
    assert '<ClCompile Include="Private\\RetargetContracts.cpp" />' in project
    assert '<Filter>Public</Filter>' in filters
    assert '<Filter>Private</Filter>' in filters
    assert "gr_retargeting_coerce_mode" in package_header
    assert "namespace ghostrigger::domain::core::retargeting::core::retargeting::retarget_contracts" in public_header
    assert "namespace ghostrigger::domain::core::retargeting::core::retargeting::retarget_contracts" in implementation
    assert "phase15" not in public_header
    assert "pyfn_" not in implementation
    assert "using namespace" not in implementation


def test_native_retarget_modes_match_python_contracts() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_retargeting_dll()

    for mode in retarget_modes.RetargetMode:
        assert dll.gr_retargeting_coerce_mode(mode.value.encode("utf-8")).decode("utf-8") == mode.value
        assert dll.gr_retargeting_coerce_mode(mode.name.encode("utf-8")).decode("utf-8") == mode.value
        assert (
            dll.gr_retargeting_is_kotor_output_mode(mode.value.encode("utf-8"))
            == int(retarget_output_naming.is_kotor_output_mode(mode))
        )

    assert dll.gr_retargeting_coerce_mode(b"not-a-mode").decode("utf-8") == ""
    assert dll.gr_retargeting_is_kotor_output_mode(b"not-a-mode") == 0


def test_native_retarget_mode_specs_match_python_dropdown_order() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_retargeting_dll()

    native_specs = json.loads(dll.gr_retargeting_mode_specs_json().decode("utf-8"))
    python_specs = retarget_modes.list_retarget_mode_specs()

    assert [item["mode"] for item in native_specs] == [spec.mode.value for spec in python_specs]
    assert [item["label"] for item in native_specs] == [spec.label for spec in python_specs]
    assert [item["source_kind"] for item in native_specs] == [spec.source_kind for spec in python_specs]
    assert [item["target_kind"] for item in native_specs] == [spec.target_kind for spec in python_specs]
    assert [item["output_kind"] for item in native_specs] == [spec.output_kind for spec in python_specs]
    assert [tuple(item["required_inputs"]) for item in native_specs] == [spec.required_inputs for spec in python_specs]


def test_native_output_name_modes_and_validation_match_python_contracts() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_retargeting_dll()

    for alias, expected in {
        None: retarget_output_naming.KotorOutputAnimationNameMode.VANILLA_SLOT.value,
        "vanilla": retarget_output_naming.KotorOutputAnimationNameMode.VANILLA_SLOT.value,
        "slot": retarget_output_naming.KotorOutputAnimationNameMode.VANILLA_SLOT.value,
        "custom": retarget_output_naming.KotorOutputAnimationNameMode.CUSTOM_PATCH.value,
        "patch": retarget_output_naming.KotorOutputAnimationNameMode.CUSTOM_PATCH.value,
    }.items():
        value = b"" if alias is None else alias.encode("utf-8")
        assert dll.gr_retargeting_coerce_kotor_output_name_mode(value).decode("utf-8") == expected

    assert dll.gr_retargeting_coerce_kotor_output_name_mode(b"bad").decode("utf-8") == ""

    for name in ["walk_custom", " Combat Idle ", "a" * 64]:
        assert _call_string(dll.gr_retargeting_validate_custom_kotor_animation_name, name) == (
            retarget_output_naming.validate_custom_kotor_animation_name(name)
        )

    for invalid in ["", ".", "..", "bad/name", "a" * 65]:
        with pytest.raises(retarget_output_naming.RetargetOutputNamingError):
            retarget_output_naming.validate_custom_kotor_animation_name(invalid)
        assert _call_string(dll.gr_retargeting_validate_custom_kotor_animation_name, invalid) == ""


def test_native_unreal_clip_validation_matches_python_contracts_for_ascii_inputs() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_retargeting_dll()

    for name in ["Walk Forward", " UE-Clip_01 ", "__trim_me--"]:
        assert _call_string(dll.gr_retargeting_validate_unreal_clip_name, name) == (
            retarget_output_naming.validate_unreal_clip_name(name)
        )

    for invalid in ["", "bad/name", "a" * 129]:
        with pytest.raises(retarget_output_naming.RetargetOutputNamingError):
            retarget_output_naming.validate_unreal_clip_name(invalid)
        assert _call_string(dll.gr_retargeting_validate_unreal_clip_name, invalid) == ""


def test_native_retargeting_capabilities_document_python_fallback_scope() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_retargeting_dll()

    capabilities = json.loads(dll.gr_retargeting_capabilities_json().decode("utf-8"))
    schema = json.loads(dll.gr_retargeting_contracts_schema_json().decode("utf-8"))

    assert capabilities["native_implementation_enabled"] is True
    assert capabilities["python_fallback_required"] is True
    assert "retarget_mode_contracts" in capabilities["capabilities"]
    assert "KotorOutputAnimationNameMode coercion" in schema["native_scope"]
    assert "animation slot lookup" in schema["python_fallback"]
