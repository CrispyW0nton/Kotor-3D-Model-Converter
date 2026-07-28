"""Repository hygiene checks for local-only tool credentials."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
import sys

import pytest


FORBIDDEN_TRACKED_SUBSTRINGS = (
    "170." "9." "241." "140",
    "http://" + "170." "9." "241." "140" + ":8080/mcp/",
    "revan" "lives",
    '"X-Agent-Server-' "Password" '":',
)


def test_tracked_files_do_not_expose_local_ghidra_endpoint_or_passwords() -> None:
    root = Path(__file__).resolve().parents[1]
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.splitlines()

    offenders: list[str] = []
    for rel in tracked:
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for forbidden in FORBIDDEN_TRACKED_SUBSTRINGS:
            if forbidden in text:
                offenders.append(f"{rel}: contains {forbidden!r}")

    assert not offenders, "Local Ghidra/AgentDecompile secrets leaked into tracked files:\n" + "\n".join(offenders)


def _agdec_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "agdec_query.py"
    name = "ghoststudio_agdec_query_hygiene_test"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_agentdecompile_connection_requires_private_local_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _agdec_module()
    monkeypatch.setenv(
        "AGENTDECOMPILE_MCP_HEADERS_JSON",
        '{"Authorization":"local-secret"}',
    )
    monkeypatch.setenv(
        "AGENTDECOMPILE_MCP_SERVER_URL",
        "http://127.0.0.1:8080/mcp/",
    )

    url, headers = module._connection()

    assert url == "http://127.0.0.1:8080/mcp/"
    assert headers["Authorization"] == "local-secret"

    monkeypatch.setenv(
        "AGENTDECOMPILE_MCP_SERVER_URL",
        "https://example.com/mcp/",
    )
    with pytest.raises(RuntimeError, match="reviewed local MCP endpoint"):
        module._connection()
