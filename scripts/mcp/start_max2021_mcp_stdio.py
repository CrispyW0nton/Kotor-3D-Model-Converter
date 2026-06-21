"""Start the 3ds Max MCP server over stdio.

`Codex` and other MCP clients should call this entry-point.
Keep stdout reserved for MCP frames; diagnostics remain on stderr.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _prepend_path(path: Path) -> None:
    text = str(path)
    if path.exists() and text not in sys.path:
        sys.path.insert(0, text)


def _python_roots(root: Path) -> list[Path]:
    roots: list[Path] = []
    root_src = root / "src"
    if root_src.exists():
        roots.append(root_src)
    roots.append(root)
    return roots


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    wanted = _python_roots(root)
    for path in reversed(wanted):
        _prepend_path(path)

    os.environ.setdefault("PYTHONPATH", "")
    os.environ["GHOSTRIGGER_ROOT"] = str(root)

    from max2021_mcp.server import main as server_main

    server_main(["--mode", "stdio"])


if __name__ == "__main__":
    main()
