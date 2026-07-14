"""Optional KotorMCP HTTP server in a separate console on GhostRigger startup."""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

_DEFAULT_PORT = 8765


def maybe_autostart_kotormcp() -> None:
    """Spawn ``python -m kotormcp --mode http`` in a new terminal if port is free.

    Set ``GHOSTRIGGER_NO_MCP_AUTOSTART=1`` to disable.  Override port with
    ``GHOSTRIGGER_MCP_PORT``.
    """
    if getattr(sys, "frozen", False):
        # In a PyInstaller app sys.executable is GhostStudio.exe, not python.exe.
        # Launching it with "-m kotormcp" starts another GUI instance instead of
        # the MCP module, which can make the compiled app feel badly lagged.
        if os.environ.get("GHOSTRIGGER_ALLOW_FROZEN_MCP_AUTOSTART", "").strip().lower() not in (
            "1", "true", "yes", "on",
        ):
            log.info("maybe_autostart_kotormcp: skipped in frozen build")
            return

    flag = os.environ.get("GHOSTRIGGER_NO_MCP_AUTOSTART", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return

    src_dir = Path(__file__).resolve().parent.parent
    app_root = src_dir.parent
    if not (src_dir / "kotormcp" / "__main__.py").exists():
        return

    try:
        port = int(os.environ.get("GHOSTRIGGER_MCP_PORT", str(_DEFAULT_PORT)))
    except ValueError:
        port = _DEFAULT_PORT

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                log.debug("maybe_autostart_kotormcp: port %s busy, skip", port)
                return
    except OSError:
        pass

    env = os.environ.copy()
    env["GHOSTRIGGER_NO_MCP_AUTOSTART"] = "1"
    sep = os.pathsep
    pyp = str(src_dir)
    env["PYTHONPATH"] = f"{pyp}{sep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else pyp

    argv = [
        sys.executable,
        "-m",
        "kotormcp",
        "--mode",
        "http",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]

    try:
        subprocess.Popen(
            argv,
            cwd=str(app_root),
            env=env,
            creationflags=creationflags,
            stdin=subprocess.DEVNULL,
        )
        log.info(
            "KotorMCP HTTP started in a new console — http://127.0.0.1:%s/health",
            port,
        )
    except Exception as exc:
        log.warning("maybe_autostart_kotormcp: %s", exc)
