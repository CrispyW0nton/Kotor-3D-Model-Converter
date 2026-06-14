from __future__ import annotations

import ctypes
import json
from pathlib import Path

from src.ipc import client


ROOT = Path(__file__).resolve().parents[1]
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Domain.Core.IPC.dll"


def _load_dll() -> ctypes.CDLL:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = ctypes.CDLL(str(DLL_PATH))
    dll.gr_ipc_capabilities_json.argtypes = []
    dll.gr_ipc_capabilities_json.restype = ctypes.c_char_p
    dll.gr_ipc_port_for_program.argtypes = [ctypes.c_char_p]
    dll.gr_ipc_port_for_program.restype = ctypes.c_int
    dll.gr_ipc_default_timeout_seconds.argtypes = []
    dll.gr_ipc_default_timeout_seconds.restype = ctypes.c_double
    dll.gr_ipc_endpoint_url.argtypes = [ctypes.c_int, ctypes.c_char_p]
    dll.gr_ipc_endpoint_url.restype = ctypes.c_char_p
    dll.gr_ipc_request_body_json.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
    dll.gr_ipc_request_body_json.restype = ctypes.c_char_p
    dll.gr_ipc_response_is_ok.argtypes = [ctypes.c_char_p]
    dll.gr_ipc_response_is_ok.restype = ctypes.c_int
    dll.gr_ipc_ping_status_message.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p]
    dll.gr_ipc_ping_status_message.restype = ctypes.c_char_p
    return dll


def _text(value: bytes) -> str:
    return value.decode("utf-8")


def test_native_ipc_program_ports_match_python_constants() -> None:
    dll = _load_dll()

    assert dll.gr_ipc_port_for_program(b"GhostRigger") == client.PORT_GHOSTRIGGER
    assert dll.gr_ipc_port_for_program(b" ghostscripter ") == client.PORT_GHOSTSCRIPTER
    assert dll.gr_ipc_port_for_program(b"GModular") == client.PORT_GMODULAR
    assert dll.gr_ipc_port_for_program(b"unknown") == 0
    assert dll.gr_ipc_default_timeout_seconds() == 2.0


def test_native_ipc_endpoint_and_request_envelope_match_python_shape() -> None:
    dll = _load_dll()

    assert _text(dll.gr_ipc_endpoint_url(client.PORT_GHOSTRIGGER, b"state")) == (
        f"http://127.0.0.1:{client.PORT_GHOSTRIGGER}/api/state"
    )
    body = json.loads(
        dll.gr_ipc_request_body_json(
            b"GhostRigger",
            b"show_panel",
            b'{"panel":"content_browser"}',
        ).decode("utf-8")
    )
    assert body == {
        "version": "1.0",
        "sender": "GhostRigger",
        "action": "show_panel",
        "payload": {"panel": "content_browser"},
    }
    empty_payload_body = json.loads(dll.gr_ipc_request_body_json(b"GhostRigger", b"ping", b"").decode("utf-8"))
    assert empty_payload_body["payload"] == {}


def test_native_ipc_response_and_ping_status_contracts() -> None:
    dll = _load_dll()

    assert dll.gr_ipc_response_is_ok(b"ok") == 1
    assert dll.gr_ipc_response_is_ok(b"error") == 0
    assert _text(dll.gr_ipc_ping_status_message(b"GhostScripter", client.PORT_GHOSTSCRIPTER, b"ok")) == (
        f"GhostScripter is running on port {client.PORT_GHOSTSCRIPTER}"
    )
    assert "not running" in _text(
        dll.gr_ipc_ping_status_message(b"GModular", client.PORT_GMODULAR, b"unavailable")
    )
    assert _text(dll.gr_ipc_ping_status_message(b"GModular", client.PORT_GMODULAR, b"timeout")) == (
        f"GModular on port {client.PORT_GMODULAR}: timeout"
    )


def test_native_ipc_capabilities_document_contract_scope() -> None:
    dll = _load_dll()
    capabilities = json.loads(dll.gr_ipc_capabilities_json().decode("utf-8"))
    assert capabilities["ipc_contracts_native"] is True
    assert capabilities["ipc_runtime_python_fallback"] is True
    assert capabilities["python_fallback_required"] is True
