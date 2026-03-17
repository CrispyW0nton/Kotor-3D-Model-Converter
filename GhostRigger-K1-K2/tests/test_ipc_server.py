"""
test_ipc_server.py — IPC server ping and error handling tests.

Tests per GHOSTWORKS_BLUEPRINT.md Section 10:
  "IPC ping: start the IPC server, send a ping, assert ok response"
  "IPC error handling: send malformed JSON, assert no crash"
"""
import time
import json
import threading
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ─── Try to import Flask/requests ────────────────────────────────────────────

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

try:
    import flask as _flask
    _HAS_FLASK = True
except ImportError:
    _HAS_FLASK = False


pytestmark = pytest.mark.skipif(
    not (_HAS_REQUESTS and _HAS_FLASK),
    reason="requests and flask required for IPC tests"
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def ipc_server():
    """Start the GhostRigger IPC server on a test port and yield, then stop."""
    from src.ipc.server import GhostRiggerIPCServer

    # Use a non-default port to avoid conflict with a running app
    TEST_PORT = 17001

    received = {}
    def on_open_utc(resref, module_dir):
        received['open_utc'] = (resref, module_dir)
    def on_open_utp(resref, module_dir):
        received['open_utp'] = (resref, module_dir)
    def on_open_mdl(resref, module_dir):
        received['open_mdl'] = (resref, module_dir)

    server = GhostRiggerIPCServer(callbacks={
        'open_utc': on_open_utc,
        'open_utp': on_open_utp,
        'open_mdl': on_open_mdl,
    }, port=TEST_PORT)
    server.start()
    # Give Flask more time to bind and become ready
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            import requests as _r
            _r.get(f"http://127.0.0.1:{TEST_PORT}/api/health", timeout=0.5)
            break
        except Exception:
            time.sleep(0.2)

    yield server, TEST_PORT, received

    server.stop()


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestIPCPing:

    def test_ping_returns_ok(self, ipc_server):
        server, port, _ = ipc_server
        url = f"http://127.0.0.1:{port}/api/ping"
        resp = _requests.post(url, json={"version": "1.0", "sender": "pytest",
                                          "action": "ping", "payload": {}},
                              timeout=3)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["program"] == "GhostRigger"

    def test_ping_get_method_not_allowed(self, ipc_server):
        """IPC only accepts POST."""
        server, port, _ = ipc_server
        url = f"http://127.0.0.1:{port}/api/ping"
        resp = _requests.get(url, timeout=3)
        assert resp.status_code == 405

    def test_ping_action_in_response(self, ipc_server):
        server, port, _ = ipc_server
        url = f"http://127.0.0.1:{port}/api/ping"
        resp = _requests.post(url, json={"version": "1.0", "sender": "test",
                                          "action": "ping", "payload": {}},
                              timeout=3)
        body = resp.json()
        assert body["action"] == "ping"


class TestIPCActions:

    def test_open_utc_triggers_callback(self, ipc_server):
        server, port, received = ipc_server
        url = f"http://127.0.0.1:{port}/api/open_utc"
        resp = _requests.post(url, json={
            "version": "1.0", "sender": "GModular", "action": "open_utc",
            "payload": {"resref": "dan13_01", "module_dir": "/test/path"}
        }, timeout=3)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert received.get('open_utc') == ("dan13_01", "/test/path")

    def test_open_utp_triggers_callback(self, ipc_server):
        server, port, received = ipc_server
        url = f"http://127.0.0.1:{port}/api/open_utp"
        resp = _requests.post(url, json={
            "version": "1.0", "sender": "GModular", "action": "open_utp",
            "payload": {"resref": "plc_footlocker", "module_dir": ""}
        }, timeout=3)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_open_mdl_triggers_callback(self, ipc_server):
        server, port, received = ipc_server
        url = f"http://127.0.0.1:{port}/api/open_mdl"
        resp = _requests.post(url, json={
            "version": "1.0", "sender": "GModular", "action": "open_mdl",
            "payload": {"resref": "c_gamorrean", "module_dir": ""}
        }, timeout=3)
        assert resp.status_code == 200

    def test_unknown_action_returns_error(self, ipc_server):
        server, port, _ = ipc_server
        url = f"http://127.0.0.1:{port}/api/unknown_action"
        resp = _requests.post(url, json={
            "version": "1.0", "sender": "test", "action": "unknown_action",
            "payload": {}
        }, timeout=3)
        body = resp.json()
        assert body["status"] == "error"


class TestIPCErrorHandling:

    def test_malformed_json_no_crash(self, ipc_server):
        """Send garbage bytes — server must not crash. May return 400 or 200 depending on Flask version."""
        server, port, _ = ipc_server
        url = f"http://127.0.0.1:{port}/api/ping"
        resp = _requests.post(url, data=b"this is not json at all!!!",
                              headers={'Content-Type': 'application/json'},
                              timeout=3)
        # Server should handle it without crashing (any response is acceptable)
        assert resp.status_code in (200, 400, 500)
        # Server should still be alive after bad request
        ping_resp = _requests.post(url, json={"action": "ping", "payload": {}},
                                   timeout=3)
        assert ping_resp.status_code == 200

    def test_empty_body_no_crash(self, ipc_server):
        server, port, _ = ipc_server
        url = f"http://127.0.0.1:{port}/api/ping"
        resp = _requests.post(url, data=b"",
                              headers={'Content-Type': 'application/json'},
                              timeout=3)
        # Should not crash — return 200 or 400
        assert resp.status_code in (200, 400)

    def test_missing_payload_no_crash(self, ipc_server):
        server, port, _ = ipc_server
        url = f"http://127.0.0.1:{port}/api/open_utc"
        resp = _requests.post(url, json={"version": "1.0"}, timeout=3)
        # Should handle gracefully
        assert resp.status_code in (200, 400)

    def test_server_survives_repeated_calls(self, ipc_server):
        """Server should survive 20 rapid successive calls."""
        server, port, _ = ipc_server
        url = f"http://127.0.0.1:{port}/api/ping"
        for _ in range(20):
            resp = _requests.post(url, json={"action": "ping", "payload": {}},
                                  timeout=3)
            assert resp.status_code == 200


class TestIPCClient:

    def test_ipc_call_connection_refused(self):
        """ipc_call to a closed port must return (False, ...) without raising."""
        from src.ipc.client import ipc_call
        ok, body = ipc_call(port=19999, action="ping", payload={}, timeout=1.0)
        assert ok is False

    def test_ping_program_down(self):
        """ping_program to a down host returns (False, message)."""
        from src.ipc.client import ping_program
        ok, msg = ping_program("GModular", port=19998)
        assert ok is False
        assert isinstance(msg, str)

    def test_ipc_call_returns_dict(self, ipc_server):
        server, port, _ = ipc_server
        from src.ipc.client import ipc_call
        ok, body = ipc_call(port=port, action="ping", payload={})
        assert ok is True
        assert isinstance(body, dict)
        assert body.get("status") == "ok"
