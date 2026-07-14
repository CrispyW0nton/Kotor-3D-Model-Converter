from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
AUTOMATION_ROOT = ROOT / "native/GhostRigger.Core.Automation/Python/src"


def _install_automation_payload() -> None:
    value = str(AUTOMATION_ROOT)
    if value not in sys.path:
        sys.path.insert(0, value)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def test_port_7002_compatible_server_dispatches_registered_payload_actions(monkeypatch) -> None:
    _install_automation_payload()
    import ipc.server as server_module

    # Other Qt-focused tests create a QApplication without entering exec().
    # This server-only contract has no widgets, so keep its callback direct;
    # the native app contract separately verifies GUI-thread marshaling.
    monkeypatch.setattr(server_module, "marshal_to_gui_thread", lambda *_args: False)
    GhostRiggerIPCServer = server_module.GhostRiggerIPCServer

    received: list[dict[str, object]] = []
    port = _free_port()
    server = GhostRiggerIPCServer(
        {"status": lambda payload: received.append(dict(payload)) or {"document_count": 3}},
        port=port,
        program_name="GhostStudio Scripting Suite",
    )
    server.start()
    try:
        deadline = time.monotonic() + 5.0
        ping = None
        while time.monotonic() < deadline:
            try:
                ping = requests.post(f"http://127.0.0.1:{port}/api/ping", json={}, timeout=0.25)
                if ping.ok:
                    break
            except requests.RequestException:
                time.sleep(0.025)
        assert ping is not None and ping.ok
        assert ping.json()["program"] == "GhostStudio Scripting Suite"

        response = requests.post(
            f"http://127.0.0.1:{port}/api/status",
            json={"version": "1.0", "payload": {"game": "K2"}},
            timeout=2.0,
        )
        assert response.ok
        assert response.json()["document_count"] == 3
        assert response.json()["program"] == "GhostStudio Scripting Suite"
        assert received == [{"game": "K2"}]
    finally:
        server.stop()
        if server._thread is not None:
            server._thread.join(timeout=3.0)
        assert not server.is_running


def test_script_compiled_event_keeps_legacy_port_and_versioned_payload(monkeypatch) -> None:
    _install_automation_payload()
    from ipc import client

    calls: list[tuple[int, str, dict[str, object], str]] = []

    def capture(port, action, payload=None, on_result=None, sender="GhostRigger"):
        calls.append((int(port), str(action), dict(payload or {}), str(sender)))
        return None

    monkeypatch.setattr(client, "ipc_call_async", capture)
    client.notify_script_compiled(
        "cantina_run",
        game="K2",
        success=True,
        sha256="a" * 64,
        output_path="Saved/cantina_run.ncs",
        diagnostics=[{"severity": "info", "message": "compiled"}],
    )

    assert calls[0][0:2] == (7003, "script_compiled")
    assert calls[0][2]["version"] == 1
    assert calls[0][2]["resref"] == "cantina_run"
    assert calls[0][2]["success"] is True
    assert calls[0][3] == "GhostStudio"
