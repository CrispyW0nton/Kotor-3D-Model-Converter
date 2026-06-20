from __future__ import annotations

import ctypes
import json
from pathlib import Path

from src.core.diagnostics.module_reference_safety import (
    ModuleReference,
    _dialog_field,
    _issue_for_missing,
    _normalise_resref,
    _normalise_restype,
    _script_field,
)


ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Runtime.Core.dll"
PROJECT = ROOT / "native" / "GhostRigger.Runtime.Core" / "GhostRigger.Runtime.Core.vcxproj"
FILTERS = ROOT / "native" / "GhostRigger.Runtime.Core" / "GhostRigger.Runtime.Core.vcxproj.filters"
HEADER = ROOT / "native" / "GhostRigger.Runtime.Core" / "Public" / "DiagnosticsContracts.h"
SOURCE = ROOT / "native" / "GhostRigger.Runtime.Core" / "Private" / "DiagnosticsContracts.cpp"


def _dll() -> ctypes.CDLL:
    lib = ctypes.CDLL(str(DLL))
    lib.gr_diagnostics_capabilities_json.restype = ctypes.c_char_p
    lib.gr_diagnostics_normalize_resref.argtypes = [ctypes.c_char_p]
    lib.gr_diagnostics_normalize_resref.restype = ctypes.c_char_p
    lib.gr_diagnostics_normalize_restype.argtypes = [ctypes.c_char_p]
    lib.gr_diagnostics_normalize_restype.restype = ctypes.c_char_p
    lib.gr_diagnostics_is_script_field.argtypes = [ctypes.c_char_p]
    lib.gr_diagnostics_is_script_field.restype = ctypes.c_int
    lib.gr_diagnostics_is_dialog_field.argtypes = [ctypes.c_char_p]
    lib.gr_diagnostics_is_dialog_field.restype = ctypes.c_int
    lib.gr_diagnostics_missing_reference_issue_json.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p,
    ]
    lib.gr_diagnostics_missing_reference_issue_json.restype = ctypes.c_char_p
    lib.gr_diagnostics_contracts_schema_json.restype = ctypes.c_char_p
    return lib


def _b(text: str) -> bytes:
    return text.encode("utf-8")


def _text(value: bytes) -> str:
    return value.decode("utf-8")


def test_diagnostics_reference_normalization_matches_python() -> None:
    lib = _dll()

    for value in [" SomeResRef.UTC ", "verylongresrefname_that_clips.ncs", "", "A.B.C", "MixedCase"]:
        assert _text(lib.gr_diagnostics_normalize_resref(_b(value))) == _normalise_resref(value)

    for value in [".UTC", " ncs ", "..dlg", "", "TGA"]:
        assert _text(lib.gr_diagnostics_normalize_restype(_b(value))) == _normalise_restype(value)


def test_diagnostics_field_classification_matches_python() -> None:
    lib = _dll()

    for field in ["OnEnter", "ScriptHeartbeat", "mod_onplrrest", "mod_onanything", "Name", "TemplateResRef"]:
        assert lib.gr_diagnostics_is_script_field(_b(field)) == int(_script_field(field))

    for field in ["Conversation", "DialogResRef", "dialog", "OnDialog", "script_dialog"]:
        assert lib.gr_diagnostics_is_dialog_field(_b(field)) == int(_dialog_field(field))


def test_diagnostics_missing_reference_issues_match_python_contracts() -> None:
    lib = _dll()
    references = [
        ModuleReference(
            kind="template",
            resref="c_bastila",
            restype="utc",
            owner_type="creature",
            owner_index=2,
            field="TemplateResRef",
            source_label="Creature List.2.TemplateResRef",
        ),
        ModuleReference(
            kind="dialog",
            resref="introdlg",
            restype="dlg",
            owner_type="ifo",
            owner_index=-1,
            field="Conversation",
            source_label="ifo.Conversation",
        ),
        ModuleReference(
            kind="script",
            resref="k_mod_enter",
            restype="ncs",
            owner_type="are",
            owner_index=-1,
            field="OnEnter",
            source_label="are.OnEnter",
        ),
    ]

    for reference in references:
        expected = _issue_for_missing(reference)
        actual = json.loads(
            lib.gr_diagnostics_missing_reference_issue_json(
                _b(reference.kind),
                _b(reference.resref),
                _b(reference.restype),
                _b(reference.owner_type),
                reference.owner_index,
                _b(reference.field),
                _b(reference.source_label),
            ).decode("utf-8")
        )
        assert actual["severity"] == expected.severity
        assert actual["code"] == expected.code
        assert actual["message"] == expected.message
        assert actual["action"] == expected.action
        assert actual["reference"] == {
            "kind": reference.kind,
            "resref": reference.resref,
            "restype": reference.restype,
            "owner_type": reference.owner_type,
            "owner_index": reference.owner_index,
            "field": reference.field,
            "source_label": reference.source_label,
        }


def test_diagnostics_contracts_are_explicit_in_visual_studio_project() -> None:
    project_text = PROJECT.read_text(encoding="utf-8")
    filters_text = FILTERS.read_text(encoding="utf-8")
    source_text = SOURCE.read_text(encoding="utf-8")
    header_text = HEADER.read_text(encoding="utf-8")

    assert 'ClCompile Include="Private\\DiagnosticsContracts.cpp"' in project_text
    assert 'ClInclude Include="Public\\DiagnosticsContracts.h"' in project_text
    assert "<Filter>Private</Filter>" in filters_text
    assert "<Filter>Public</Filter>" in filters_text
    assert "namespace ghostrigger::core::diagnostics::core::diagnostics::contracts" in source_text
    assert "namespace ghostrigger::core::diagnostics::core::diagnostics::contracts" in header_text

    forbidden = ("*.cpp", "*.h", "using namespace", "phase15", "pyfn_")
    for token in forbidden:
        assert token not in project_text
        assert token not in source_text
        assert token not in header_text


def test_diagnostics_capabilities_document_native_and_python_boundaries() -> None:
    lib = _dll()
    capabilities = json.loads(lib.gr_diagnostics_capabilities_json().decode("utf-8"))
    schema = json.loads(lib.gr_diagnostics_contracts_schema_json().decode("utf-8"))

    assert capabilities["diagnostics_contracts_native"] is True
    assert capabilities["diagnostics_runtime_python_fallback"] is True
    assert schema["schema"] == "diagnostics_contracts_native.v1"
    assert "module reference resref normalization" in schema["native_scope"]
    assert "MDL header diagnostics" in schema["python_fallback"]
