from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "exports" / "scan_manifest.json"
MCP_CONFIG_PATH = ROOT / ".cursor" / "mcp.json"

DEFAULT_K1_PATH = r"h:\steam\steamapps\common\swkotor"
DEFAULT_K2_PATH = (
    r"h:\steam\steamapps\common\Knights of the Old Republic II"
)


def _configure_mcp_pythonpath() -> None:
    """Mirror the KotorMCP PYTHONPATH from .cursor/mcp.json for pytest runs."""
    configured = []
    try:
        from scripts.mcp.start_kotormcp_stdio import _python_roots

        configured.extend(_python_roots(ROOT))
    except Exception:
        configured.extend([ROOT / "src", ROOT])

    if MCP_CONFIG_PATH.exists():
        data = json.loads(MCP_CONFIG_PATH.read_text(encoding="utf-8"))
        env = data.get("mcpServers", {}).get("kotormcp", {}).get("env", {})
        for key in ("K1_PATH", "K2_PATH"):
            if env.get(key):
                os.environ.setdefault(key, env[key])
        configured.extend(p for p in str(env.get("PYTHONPATH", "")).split(";") if p)

    os.environ.setdefault("K1_PATH", DEFAULT_K1_PATH)
    os.environ.setdefault("K2_PATH", DEFAULT_K2_PATH)

    workspaces = ROOT.parent
    configured.extend(
        [
            workspaces / "KotorMCP" / "src",
            workspaces / "PyKotor" / "Libraries" / "PyKotor" / "src",
            workspaces / "PyKotor" / "Libraries" / "PyKotorGL" / "src",
            workspaces / "PyKotor" / "Libraries" / "Utility" / "src",
        ]
    )

    for item in reversed(configured):
        path = Path(item)
        text = str(path)
        if path.exists() and text not in sys.path:
            sys.path.insert(0, text)


def _load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {"k1": {"models": []}, "k2": {"models": []}, "total": 0}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


_configure_mcp_pythonpath()


@pytest.fixture(scope="session")
def game_k1_available() -> bool:
    return Path(os.environ.get("K1_PATH", DEFAULT_K1_PATH)).exists()


@pytest.fixture(scope="session")
def game_k2_available() -> bool:
    return Path(os.environ.get("K2_PATH", DEFAULT_K2_PATH)).exists()


@pytest.fixture(scope="session")
def k1_models() -> list[str]:
    return _load_manifest()["k1"]["models"]


@pytest.fixture(scope="session")
def k2_models() -> list[str]:
    return _load_manifest()["k2"]["models"]


@pytest.fixture(scope="session")
def manifest() -> dict[str, Any]:
    return _load_manifest()


@pytest.fixture(scope="session")
def ghostrigger_tools():
    return pytest.importorskip("kotormcp.tools.ghostrigger_tools")
