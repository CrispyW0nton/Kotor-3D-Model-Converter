"""Start the narrow authenticated Ghost Studio spatial MCP over stdio."""

from __future__ import annotations

import os
from pathlib import Path
import sys


def _prepend_path(path: Path) -> None:
    text = str(path)
    if path.is_dir() and text not in sys.path:
        sys.path.insert(0, text)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    automation_src = (
        root
        / "native"
        / "GhostRigger.Core.Automation"
        / "Python"
        / "src"
    )
    _prepend_path(automation_src)
    os.environ.setdefault("GHOSTRIGGER_ROOT", str(root))

    from ghoststudio_spatial_mcp.server import main as server_main

    server_main()


if __name__ == "__main__":
    main()
