"""Real loopback/stdio integration for the authenticated spatial boundary."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mcp.start_kotormcp_stdio import _python_roots  # noqa: E402

for root in reversed(_python_roots(ROOT)):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from src.ipc.server import GhostRiggerIPCServer  # noqa: E402


def test_real_private_descriptor_loopback_and_stdio_tool_calls(
    tmp_path: Path,
) -> None:
    descriptor = tmp_path / "private" / "ghoststudio-session.json"
    server = GhostRiggerIPCServer(
        {
            "get_spatial_snapshot": lambda _payload: {
                "schemaVersion": "1.0",
                "sceneRevision": "sha256:live-scene",
                "entities": [],
            },
            "get_spatial_evidence_gaps": lambda _payload: {
                "schema": "ghoststudio-spatial-evidence-gaps/v1",
                "sceneRevision": "sha256:live-scene",
                "gaps": [],
                "screenshotProvesGuiAction": False,
            },
        },
        port=0,
        spatial_session_path=descriptor,
    )
    try:
        server.start()
        assert server.is_running
        descriptor_payload = json.loads(
            descriptor.read_text(encoding="utf-8")
        )
        secret_text = descriptor_payload["secret"]
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
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-u",
                "-X",
                "utf8",
                str(launcher),
            ],
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
        assert responses[1]["result"]["structuredContent"]["status"] == "ok"
        snapshot = responses[2]["result"]["structuredContent"]["snapshot"]
        assert snapshot["sceneRevision"] == "sha256:live-scene"
        assert secret_text not in completed.stdout
        assert secret_text not in completed.stderr
    finally:
        server.stop()
        if server._thread is not None:
            server._thread.join(timeout=5)

    assert not descriptor.exists()
