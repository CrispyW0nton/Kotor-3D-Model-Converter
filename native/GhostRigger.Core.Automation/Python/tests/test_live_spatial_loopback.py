"""Real private-transport/stdio integration for the spatial boundary."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mcp.start_kotormcp_stdio import _python_roots  # noqa: E402

for root in reversed(_python_roots(ROOT)):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from src.ipc.server import GhostRiggerIPCServer  # noqa: E402
from src.ipc.spatial_auth import (  # noqa: E402
    SPATIAL_APP_CONTAINER_SID_ENV,
    SPATIAL_TRANSPORT_ENV,
    WINDOWS_SPATIAL_TRANSPORT,
)
from src.core.scene.spatial_snapshot import (  # noqa: E402
    build_scene_spatial_snapshot,
)


def _live_snapshot() -> dict:
    identity = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    snapshot = build_scene_spatial_snapshot(
        SimpleNamespace(
            id="live-scene",
            units={"system_unit": "cm", "display_unit": "cm"},
            objects=[],
            all_objects=lambda: [],
        ),
        application_version="2.8",
        captured_at="2026-07-28T00:00:00Z",
        viewport={
            "id": "ghoststudio-main-viewport",
            "rectangle": {
                "x": 0.0,
                "y": 0.0,
                "width": 1280.0,
                "height": 720.0,
            },
            "pixelOrigin": "top-left",
            "devicePixelRatio": 1.0,
            "cameraStableId": None,
            "projection": "perspective",
            "viewMatrix": identity,
            "projectionMatrix": identity,
            "nearClip": 0.01,
            "farClip": 1000.0,
        },
        grid={
            "origin": [0.0, 0.0, 0.0],
            "spacing": [10.0, 10.0, 10.0],
            "subdivisions": 10,
            "visible": True,
            "snapEnabled": False,
        },
    )
    snapshot["guiReadiness"] = {
        "ready": True,
        "mainThreadObserved": True,
        "windowVisible": True,
        "windowMinimized": False,
        "viewport": {
            "stateAvailable": True,
            "visible": True,
            "width": 1280,
            "height": 720,
        },
        "grid": {
            "stateAvailable": True,
            "visible": True,
        },
        "reason": None,
    }
    return snapshot


PACKAGE_SID = (
    "S-1-15-2-1229027098-1376173174-3902671414-3221589281-"
    "1354859120-752965424-969501979"
)


def _windows_full_trust_test_launcher(
    descriptor: Path,
    launcher: Path,
) -> str:
    """Route this protocol-only child to the AppContainer server namespace."""

    automation_src = (
        ROOT
        / "native"
        / "GhostRigger.Core.Automation"
        / "Python"
        / "src"
    )
    pipe_module = automation_src / "ipc" / "spatial_pipe.py"
    return "\n".join(
        (
            "import importlib.util, json, runpy, sys",
            "from pathlib import Path",
            f"automation_src = Path({str(automation_src)!r})",
            "sys.path.insert(0, str(automation_src))",
            "module_name = '_ghoststudio_spatial_pipe_contract'",
            f"spec = importlib.util.spec_from_file_location("
            f"module_name, Path({str(pipe_module)!r}))",
            "assert spec is not None and spec.loader is not None",
            "pipe = importlib.util.module_from_spec(spec)",
            "sys.modules[module_name] = pipe",
            "spec.loader.exec_module(pipe)",
            f"descriptor = Path({str(descriptor)!r})",
            "alias = json.loads(descriptor.read_text("
            "encoding='utf-8'))['pipeName']",
            "strict_alias = pipe.validate_windows_spatial_pipe_name",
            "qualified = pipe._windows_app_container_server_pipe_name("
            f"alias, {PACKAGE_SID!r}, "
            "session_id=pipe._current_windows_session_id())",
            "def resolve_test_pipe(value):",
            "    assert strict_alias(value) == alias",
            "    return qualified",
            "pipe.validate_windows_spatial_pipe_name = resolve_test_pipe",
            f"runpy.run_path({str(launcher)!r}, run_name='__main__')",
        )
    )


def test_real_private_descriptor_transport_and_stdio_tool_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.ipc.server as ipc_server

    def _marshal_inline_for_test(callback, *args) -> bool:
        callback(*args)
        return True

    monkeypatch.setattr(
        ipc_server,
        "marshal_to_gui_thread",
        _marshal_inline_for_test,
    )
    if os.name == "nt":
        original_pipe_server = ipc_server.WindowsSpatialNamedPipeServer

        class _IntegrationPipeServer(original_pipe_server):
            def __init__(self, **kwargs):
                kwargs["client_identity_verifier"] = lambda _handle: None
                super().__init__(**kwargs)

        monkeypatch.setattr(
            ipc_server,
            "WindowsSpatialNamedPipeServer",
            _IntegrationPipeServer,
        )
        monkeypatch.setenv(
            SPATIAL_TRANSPORT_ENV,
            WINDOWS_SPATIAL_TRANSPORT,
        )
        monkeypatch.setenv(SPATIAL_APP_CONTAINER_SID_ENV, PACKAGE_SID)
    descriptor = tmp_path / "private" / "ghoststudio-session.json"
    server = GhostRiggerIPCServer(
        {
            "get_spatial_snapshot": lambda _payload: _live_snapshot(),
            "get_spatial_evidence_gaps": lambda _payload: {
                "schema": "ghoststudio-spatial-evidence-gaps/v1",
                "sceneRevision": _live_snapshot()["sceneRevision"],
                "gaps": [],
                "screenshotProvesGuiAction": False,
            },
        },
        port=0,
        spatial_session_path=descriptor,
        spatial_session_ttl_seconds=60,
        spatial_session_renewal_margin_seconds=55,
    )
    try:
        server.start()
        assert server.is_running
        descriptor_payload = json.loads(
            descriptor.read_text(encoding="utf-8")
        )
        initial_session_id = descriptor_payload["sessionId"]
        if os.name == "nt":
            renewal_deadline = time.monotonic() + 8.0
            while time.monotonic() < renewal_deadline:
                descriptor_payload = json.loads(
                    descriptor.read_text(encoding="utf-8")
                )
                if descriptor_payload["sessionId"] != initial_session_id:
                    break
                time.sleep(0.05)
            assert descriptor_payload["sessionId"] != initial_session_id
        secret_text = descriptor_payload["secret"]
        if os.name == "nt":
            assert descriptor_payload["transport"] == WINDOWS_SPATIAL_TRANSPORT
            assert descriptor_payload["pipeName"].startswith(
                r"\\.\pipe\LOCAL\GhostStudioSpatial-"
            )
            assert "port" not in descriptor_payload
        else:
            assert descriptor_payload["port"] == server.port

        launcher = (
            ROOT / "scripts" / "mcp" / "start_ghoststudio_spatial_stdio.py"
        )
        messages = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "integration-test", "version": "1"},
                },
            },
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "ghoststudio_health",
                    "arguments": {},
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "ghoststudio_spatial_snapshot",
                    "arguments": {"includeSelection": True},
                },
            },
        ]
        child_environment = {
            "SYSTEMROOT": os.environ["SystemRoot"],
            "WINDIR": os.environ["SystemRoot"],
            "PATH": (
                f"{Path(os.environ['SystemRoot']) / 'System32'};"
                f"{os.environ['SystemRoot']}"
            ),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONUTF8": "1",
            "GHOSTSTUDIO_SPATIAL_SESSION_PATH": str(descriptor),
        }
        if os.name == "nt":
            child_environment.update(
                {
                    SPATIAL_TRANSPORT_ENV: WINDOWS_SPATIAL_TRANSPORT,
                    SPATIAL_APP_CONTAINER_SID_ENV: PACKAGE_SID,
                }
            )
        child_command = [
            sys.executable,
            "-I",
            "-B",
            "-u",
            "-X",
            "utf8",
        ]
        if os.name == "nt":
            # This is a full-trust protocol integration, not containment
            # evidence. Production clients reach the LOCAL alias only from
            # the exact zero-capability AppContainer.
            child_command.extend(
                [
                    "-c",
                    _windows_full_trust_test_launcher(
                        descriptor,
                        launcher,
                    ),
                ]
            )
        else:
            child_command.append(str(launcher))
        completed = subprocess.run(
            child_command,
            input="".join(
                json.dumps(message, separators=(",", ":")) + "\n"
                for message in messages
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=30,
            env=child_environment,
        )

        assert completed.returncode == 0, completed.stderr
        responses = [
            json.loads(line)
            for line in completed.stdout.splitlines()
            if line.strip()
        ]
        assert "structuredContent" in responses[1].get("result", {}), (
            responses,
            completed.stderr,
        )
        assert responses[1]["result"]["structuredContent"]["status"] == "ok"
        assert responses[1]["result"]["structuredContent"]["endpoint"][
            "transport"
        ] == (
            WINDOWS_SPATIAL_TRANSPORT
            if os.name == "nt"
            else "loopback-http"
        )
        snapshot = responses[2]["result"]["structuredContent"]["snapshot"]
        assert snapshot["sceneRevision"].startswith("sha256:")
        assert secret_text not in completed.stdout
        assert secret_text not in completed.stderr
    finally:
        server.stop()
        if server._thread is not None:
            server._thread.join(timeout=5)

    assert not descriptor.exists()
