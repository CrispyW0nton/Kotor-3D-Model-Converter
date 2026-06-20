from __future__ import annotations

import ctypes
import json
from pathlib import Path

from src.adapters.scripts.unavailable_compiler import UnavailableScriptCompiler


ROOT = Path(__file__).resolve().parents[1]
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Core.Automation.dll"


def _load_dll() -> ctypes.CDLL:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = ctypes.CDLL(str(DLL_PATH))
    dll.gr_core_automation_scripting_capabilities_json.argtypes = []
    dll.gr_core_automation_scripting_capabilities_json.restype = ctypes.c_char_p
    dll.gr_core_automation_scripting_unavailable_default_reason.argtypes = []
    dll.gr_core_automation_scripting_unavailable_default_reason.restype = ctypes.c_char_p
    dll.gr_core_automation_scripting_unavailable_issue_json.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
    dll.gr_core_automation_scripting_unavailable_issue_json.restype = ctypes.c_char_p
    dll.gr_core_automation_scripting_unavailable_compile_result_json.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
    dll.gr_core_automation_scripting_unavailable_compile_result_json.restype = ctypes.c_char_p
    return dll


def test_native_unavailable_script_compiler_default_reason_matches_python() -> None:
    dll = _load_dll()
    compiler = UnavailableScriptCompiler()

    assert dll.gr_core_automation_scripting_unavailable_default_reason().decode("utf-8") == compiler.reason


def test_native_unavailable_script_compiler_issue_matches_python_result() -> None:
    dll = _load_dll()
    source = "scripts/k_inc_debug.nss"
    game = "k2"
    compiler = UnavailableScriptCompiler()
    py_result = compiler.compile_script(source, game=game)
    py_issue = py_result.report.issues[0]

    native_issue = json.loads(
        dll.gr_core_automation_scripting_unavailable_issue_json(
            source.encode("utf-8"),
            game.encode("utf-8"),
            None,
        ).decode("utf-8")
    )

    assert native_issue["severity"] == py_issue.severity.value
    assert native_issue["subsystem"] == py_issue.subsystem.value
    assert native_issue["code"] == py_issue.code
    assert native_issue["message"] == py_issue.message
    assert native_issue["target"] is None
    assert native_issue["details"] == py_issue.details


def test_native_unavailable_script_compiler_result_matches_python_contract() -> None:
    dll = _load_dll()
    source = "module/on_enter.nss"
    game = "k1"
    reason = "Compiler path is missing."

    native_result = json.loads(
        dll.gr_core_automation_scripting_unavailable_compile_result_json(
            source.encode("utf-8"),
            game.encode("utf-8"),
            reason.encode("utf-8"),
        ).decode("utf-8")
    )

    assert native_result["source"] == source
    assert native_result["output_hex"] == ""
    assert native_result["report"]["source"] == "script.compiler"
    assert native_result["report"]["issues"][0]["message"] == reason
    assert native_result["metadata"] == {
        "available": False,
        "reason": reason,
        "game": game,
    }


def test_native_core_automation_scripting_capabilities_document_contract_scope() -> None:
    dll = _load_dll()
    capabilities = json.loads(dll.gr_core_automation_scripting_capabilities_json().decode("utf-8"))
    assert capabilities["unavailable_compiler_native"] is True
    assert capabilities["script_compiler_runtime_python_fallback"] is True
    assert capabilities["python_fallback_required"] is True
