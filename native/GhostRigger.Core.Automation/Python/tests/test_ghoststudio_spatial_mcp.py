"""Focused protocol and security tests for the narrow spatial MCP child."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[4]
AUTOMATION_SRC = (
    ROOT
    / "native"
    / "GhostRigger.Core.Automation"
    / "Python"
    / "src"
)
if str(AUTOMATION_SRC) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_SRC))

from ghoststudio_spatial_mcp import server as spatial_mcp  # noqa: E402


EXPECTED_TOOL_NAMES = [
    "ghoststudio_health",
    "ghoststudio_spatial_snapshot",
    "ghoststudio_capture",
    "ghoststudio_evidence_gaps",
]


def test_catalog_is_exact_and_does_not_require_a_live_session() -> None:
    response = spatial_mcp.GhostStudioSpatialMcpServer().dispatch(
        {
            "jsonrpc": "2.0",
            "id": "catalog",
            "method": "tools/list",
            "params": {},
        }
    )

    assert response is not None
    tools = response["result"]["tools"]
    assert [tool["name"] for tool in tools] == EXPECTED_TOOL_NAMES
    assert all(
        tool["inputSchema"]["additionalProperties"] is False
        for tool in tools
    )


def test_invalid_capture_id_is_rejected_before_client_construction() -> None:
    created: list[bool] = []

    def client_factory():
        created.append(True)
        raise AssertionError("invalid arguments must not reach the client")

    response = spatial_mcp.GhostStudioSpatialMcpServer(
        client_factory=client_factory
    ).dispatch(
        {
            "jsonrpc": "2.0",
            "id": "capture",
            "method": "tools/call",
            "params": {
                "name": "ghoststudio_capture",
                "arguments": {"captureId": "../outside"},
            },
        }
    )

    assert response is not None
    assert response["result"]["isError"] is True
    assert "invalid-arguments" in response["result"]["content"][0]["text"]
    assert created == []


def test_stdio_launcher_negotiates_and_lists_only_the_narrow_catalog() -> None:
    launcher = ROOT / "scripts" / "mcp" / "start_ghoststudio_spatial_stdio.py"
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        },
        {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
    ]
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
        timeout=15,
    )

    assert completed.returncode == 0, completed.stderr
    responses = [
        json.loads(line)
        for line in completed.stdout.splitlines()
        if line.strip()
    ]
    assert len(responses) == 2
    assert responses[0]["result"]["protocolVersion"] == "2025-11-25"
    assert [
        tool["name"] for tool in responses[1]["result"]["tools"]
    ] == EXPECTED_TOOL_NAMES
    assert completed.stderr == ""
