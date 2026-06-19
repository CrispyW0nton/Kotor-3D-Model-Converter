from __future__ import annotations

import ctypes
import json
from pathlib import Path

from src.core.validation import validation_bus
from src.core.validation.validation_bus import ValidationSeverity, ValidationSubsystem, severity_rank


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "native" / "GhostRigger.Core.Validation"
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Core.Validation.dll"


def _load_validation_dll() -> ctypes.CDLL:
    dll = ctypes.CDLL(str(DLL_PATH))
    dll.gr_validation_capabilities_json.argtypes = []
    dll.gr_validation_capabilities_json.restype = ctypes.c_char_p
    dll.gr_validation_severity_rank.argtypes = [ctypes.c_char_p]
    dll.gr_validation_severity_rank.restype = ctypes.c_int
    dll.gr_validation_is_valid_severity.argtypes = [ctypes.c_char_p]
    dll.gr_validation_is_valid_severity.restype = ctypes.c_int
    dll.gr_validation_is_valid_subsystem.argtypes = [ctypes.c_char_p]
    dll.gr_validation_is_valid_subsystem.restype = ctypes.c_int
    dll.gr_validation_severity_values_json.argtypes = []
    dll.gr_validation_severity_values_json.restype = ctypes.c_char_p
    dll.gr_validation_subsystem_values_json.argtypes = []
    dll.gr_validation_subsystem_values_json.restype = ctypes.c_char_p
    dll.gr_validation_validation_bus_schema_json.argtypes = []
    dll.gr_validation_validation_bus_schema_json.restype = ctypes.c_char_p
    return dll


def _json_from_bytes(value: bytes) -> object:
    return json.loads(value.decode("utf-8"))


def test_validation_project_declares_validation_bus_files_and_exports() -> None:
    project = (PROJECT_DIR / "GhostRigger.Core.Validation.vcxproj").read_text(encoding="utf-8")
    filters = (PROJECT_DIR / "GhostRigger.Core.Validation.vcxproj.filters").read_text(encoding="utf-8")
    package_header = (PROJECT_DIR / "Public" / "GhostRiggerValidation.h").read_text(encoding="utf-8")
    public_header = (PROJECT_DIR / "Public" / "ValidationBus.h").read_text(encoding="utf-8")
    implementation = (PROJECT_DIR / "Private" / "ValidationBus.cpp").read_text(encoding="utf-8")

    assert '<ClInclude Include="Public\\ValidationBus.h" />' in project
    assert '<ClCompile Include="Private\\ValidationBus.cpp" />' in project
    assert '<Filter>Public</Filter>' in filters
    assert '<Filter>Private</Filter>' in filters
    assert "gr_validation_severity_rank" in package_header
    assert "namespace ghostrigger::core::validation::core::validation::validation_bus" in public_header
    assert "namespace ghostrigger::core::validation::core::validation::validation_bus" in implementation
    assert "phase15" not in public_header
    assert "pyfn_" not in implementation
    assert "using namespace" not in implementation


def test_native_validation_severity_rank_matches_python_validation_bus() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_validation_dll()

    for severity in ValidationSeverity:
        assert dll.gr_validation_severity_rank(severity.value.encode("utf-8")) == validation_bus._python_severity_rank(severity)
        assert dll.gr_validation_is_valid_severity(severity.value.encode("utf-8")) == 1
        assert dll.gr_validation_is_valid_severity(severity.value.upper().encode("utf-8")) == 1

    assert dll.gr_validation_severity_rank(b"not-a-severity") == -1
    assert dll.gr_validation_is_valid_severity(b" warning ") == 0


def test_native_validation_subsystem_values_match_python_validation_bus() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_validation_dll()

    native_severities = _json_from_bytes(dll.gr_validation_severity_values_json())
    native_subsystems = _json_from_bytes(dll.gr_validation_subsystem_values_json())

    assert native_severities == [severity.value for severity in ValidationSeverity]
    assert native_subsystems == [subsystem.value for subsystem in ValidationSubsystem]
    for subsystem in ValidationSubsystem:
        assert dll.gr_validation_is_valid_subsystem(subsystem.value.encode("utf-8")) == 1
        assert dll.gr_validation_is_valid_subsystem(subsystem.value.upper().encode("utf-8")) == 1
    assert dll.gr_validation_is_valid_subsystem(b"module-editor") == 0


def test_native_validation_capabilities_document_python_fallback_scope() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_validation_dll()

    capabilities = _json_from_bytes(dll.gr_validation_capabilities_json())
    schema = _json_from_bytes(dll.gr_validation_validation_bus_schema_json())

    assert capabilities["native_implementation_enabled"] is True
    assert capabilities["python_fallback_required"] is True
    assert "validation_bus_severity_rank" in capabilities["capabilities"]
    assert schema["native_scope"] == [
        "ValidationSeverity",
        "ValidationSubsystem",
        "severity_rank",
        "severity_subsystem_coercion",
    ]
    assert "ValidationReport object graph" in schema["python_fallback"]


def test_python_validation_helpers_prefer_native_contract(monkeypatch) -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_validation_dll()
    monkeypatch.setattr(validation_bus, "native_validation", lambda: dll)

    assert validation_bus.severity_rank("blocking") == 3
    assert validation_bus._coerce_severity("WARNING") is ValidationSeverity.WARNING
    assert validation_bus._coerce_subsystem("VIEWPORT") is ValidationSubsystem.VIEWPORT


def test_python_validation_helpers_fall_back_when_native_missing(monkeypatch) -> None:
    monkeypatch.setattr(validation_bus, "native_validation", lambda: None)

    assert validation_bus.severity_rank("blocking") == 3
    assert validation_bus._coerce_severity("WARNING") is ValidationSeverity.WARNING
    assert validation_bus._coerce_subsystem("VIEWPORT") is ValidationSubsystem.VIEWPORT
