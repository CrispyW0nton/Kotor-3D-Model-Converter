"""Start the in-repo KotorMCP server over stdio for Codex.

Codex launches this file from ``~/.codex/config.toml``.  Keep stdout reserved
for MCP protocol frames; diagnostics belong on stderr inside ``kotormcp.server``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _prepend_path(path: Path) -> None:
    text = str(path)
    if path.exists() and text not in sys.path:
        sys.path.insert(0, text)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    _prepend_path(root / "src")
    _prepend_path(root)

    current = os.environ.get("PYTHONPATH", "")
    wanted = [str(root / "src"), str(root)]
    os.environ["PYTHONPATH"] = os.pathsep.join(
        item for item in wanted + ([current] if current else []) if item
    )

    from kotormcp.server import main as server_main

    server_main(["--mode", "stdio"])


if __name__ == "__main__":
    main()
