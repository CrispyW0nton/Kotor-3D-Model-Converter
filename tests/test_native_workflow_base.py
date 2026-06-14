from __future__ import annotations

import ctypes
import json
from pathlib import Path
from types import SimpleNamespace

from src.core.workflow import _workflow_base as workflow_base


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "native" / "GhostRigger.Domain.Core.Workflow"
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Domain.Core.Workflow.dll"


def _load_workflow_dll() -> ctypes.CDLL:
    dll = ctypes.CDLL(str(DLL_PATH))
    for name in (
        "gr_workflow_base_ext_of",
        "gr_workflow_base_resref_from_path",
        "gr_workflow_base_safe_resref",
        "gr_workflow_base_banner_key_for_counts",
        "gr_workflow_base_summary_for_counts",
    ):
        function = getattr(dll, name)
        if name == "gr_workflow_base_safe_resref":
            function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulonglong]
        elif name in {"gr_workflow_base_banner_key_for_counts", "gr_workflow_base_summary_for_counts"}:
            function.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_ulonglong]
        else:
            function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulonglong]
        function.restype = ctypes.c_int
    dll.gr_workflow_capabilities_json.argtypes = []
    dll.gr_workflow_capabilities_json.restype = ctypes.c_char_p
    dll.gr_workflow_base_schema_json.argtypes = []
    dll.gr_workflow_base_schema_json.restype = ctypes.c_char_p
    return dll


def _call_string(function, *args) -> str:
    output = ctypes.create_string_buffer(256)
    required = function(*args, output, ctypes.sizeof(output))
    assert required > 0
    assert required <= ctypes.sizeof(output)
    return output.value.decode("utf-8")


def _issue(severity: str, code: str) -> SimpleNamespace:
    return SimpleNamespace(severity=SimpleNamespace(value=severity), code=code)


def test_workflow_project_declares_workflow_base_files_and_exports() -> None:
    project = (PROJECT_DIR / "GhostRigger.Domain.Core.Workflow.vcxproj").read_text(encoding="utf-8")
    filters = (PROJECT_DIR / "GhostRigger.Domain.Core.Workflow.vcxproj.filters").read_text(encoding="utf-8")
    package_header = (PROJECT_DIR / "Public" / "GhostRiggerWorkflow.h").read_text(encoding="utf-8")
    public_header = (PROJECT_DIR / "Public" / "WorkflowBase.h").read_text(encoding="utf-8")
    implementation = (PROJECT_DIR / "Private" / "WorkflowBase.cpp").read_text(encoding="utf-8")

    assert '<ClInclude Include="Public\\WorkflowBase.h" />' in project
    assert '<ClCompile Include="Private\\WorkflowBase.cpp" />' in project
    assert '<Filter>Public</Filter>' in filters
    assert '<Filter>Private</Filter>' in filters
    assert "gr_workflow_base_safe_resref" in package_header
    assert "namespace ghostrigger::domain::core::workflow::core::workflow::workflow_base" in public_header
    assert "namespace ghostrigger::domain::core::workflow::core::workflow::workflow_base" in implementation
    assert "phase15" not in public_header
    assert "pyfn_" not in implementation
    assert "using namespace" not in implementation


def test_native_workflow_path_helpers_match_python_workflow_base() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_workflow_dll()

    paths = [
        r"C:\Games\Override\N_DarthMalak.MDL",
        "modules/001ebo1.rim",
        "README",
        r"C:\tmp.with.dots\Foo-Bar.UTC",
    ]
    for path in paths:
        encoded = path.encode("utf-8")
        assert _call_string(dll.gr_workflow_base_ext_of, encoded) == workflow_base.ext_of(path)
        assert _call_string(dll.gr_workflow_base_resref_from_path, encoded) == workflow_base.resref_from_path(path)


def test_native_workflow_safe_resref_matches_python_workflow_base_for_ascii_inputs() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_workflow_dll()

    cases = [
        ("N Darth Malak!", "untitled"),
        ("pmhc01_head-Variant", "untitled"),
        ("###", "fallback_id"),
        ("A_B-C.01", "untitled"),
    ]
    for text, fallback in cases:
        actual = _call_string(dll.gr_workflow_base_safe_resref, text.encode("utf-8"), fallback.encode("utf-8"))
        assert actual == workflow_base.safe_resref(text, fallback)


def test_native_workflow_summary_helpers_match_python_summarize_issues_counts() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_workflow_dll()

    cases = [
        [],
        [_issue("info", "I001")],
        [_issue("warning", "W001"), _issue("warning", "W002")],
        [_issue("error", "E001"), _issue("warning", "W001"), _issue("info", "I001")],
    ]
    for issues in cases:
        key, summary, errors, warnings, infos, _codes = workflow_base.summarize_issues(issues)
        assert _call_string(dll.gr_workflow_base_banner_key_for_counts, errors, warnings, infos) == key
        assert _call_string(dll.gr_workflow_base_summary_for_counts, errors, warnings, infos) == summary


def test_native_workflow_capabilities_document_python_fallback_scope() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_workflow_dll()

    capabilities = json.loads(dll.gr_workflow_capabilities_json().decode("utf-8"))
    schema = json.loads(dll.gr_workflow_base_schema_json().decode("utf-8"))

    assert capabilities["native_implementation_enabled"] is True
    assert capabilities["python_fallback_required"] is True
    assert "workflow_base_path_helpers" in capabilities["capabilities"]
    assert schema["native_scope"] == [
        "ext_of",
        "resref_from_path",
        "safe_resref",
        "banner_key_for_counts",
        "summary_for_counts",
    ]
    assert "workflow dataclasses" in schema["python_fallback"]
