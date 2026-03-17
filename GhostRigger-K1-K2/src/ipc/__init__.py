"""
GhostRigger IPC module — Ghostworks Pipeline communication.

Per GHOSTWORKS_BLUEPRINT.md Section 3:
  GhostRigger runs an IPC server on port 7001.
  GhostScripter is on port 7002.
  GModular is on port 7003.
"""

from .server import GhostRiggerIPCServer, PORT_GHOSTRIGGER
from .client import (
    ipc_call, ipc_call_async,
    notify_blueprint_saved,
    refresh_gmodular_viewport,
    open_script_in_scripter,
    open_dlg_in_scripter,
    ping_program, ping_all,
    PORT_GHOSTSCRIPTER, PORT_GMODULAR,
)

__all__ = [
    "GhostRiggerIPCServer",
    "PORT_GHOSTRIGGER", "PORT_GHOSTSCRIPTER", "PORT_GMODULAR",
    "ipc_call", "ipc_call_async",
    "notify_blueprint_saved", "refresh_gmodular_viewport",
    "open_script_in_scripter", "open_dlg_in_scripter",
    "ping_program", "ping_all",
]
