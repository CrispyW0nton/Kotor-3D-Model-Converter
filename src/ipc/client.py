"""
GhostRigger IPC Client — calls GhostScripter (7002) and GModular (7003)
Implements the Ghostworks Pipeline IPC contract from GHOSTWORKS_BLUEPRINT.md.

Usage:
    from src.ipc.client import ipc_call, notify_blueprint_saved, ping_program

    # Tell GModular a blueprint was saved
    notify_blueprint_saved("dan13_01", "utc")

    # Open a script in GhostScripter
    open_script_in_scripter("c_rodian_sp", module_dir="C:/...")

    # Ping to check if a program is running
    ok, msg = ping_program("GModular", 7003)
"""

from __future__ import annotations

import logging
import threading
from typing import Optional, Tuple, Dict, Any

log = logging.getLogger(__name__)

# ── Port constants (per GHOSTWORKS_BLUEPRINT.md Section 3.1) ────────────────
PORT_GHOSTRIGGER   = 7001
PORT_GHOSTSCRIPTER = 7002
PORT_GMODULAR      = 7003

_IPC_TIMEOUT = 2.0   # seconds — per blueprint Section 3.4


# ─────────────────────────────────────────────────────────────────────────────
#  Low-level HTTP helper
# ─────────────────────────────────────────────────────────────────────────────

def ipc_call(
    port: int,
    action: str,
    payload: Optional[Dict[str, Any]] = None,
    sender: str = "GhostRigger",
    timeout: float = _IPC_TIMEOUT,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Send a JSON POST to http://localhost:<port>/api/<action>.

    Returns (success: bool, response_body: dict).

    On connection refused / timeout: returns (False, {"status": "unavailable"})
    WITHOUT raising an exception (per blueprint Section 3.4).
    """
    try:
        import requests
    except ImportError:
        log.warning("requests not installed — IPC calls unavailable. pip install requests")
        return False, {"status": "no_requests"}

    url = f"http://127.0.0.1:{port}/api/{action}"
    body = {
        "version": "1.0",
        "sender": sender,
        "action": action,
        "payload": payload or {},
    }

    try:
        resp = requests.post(url, json=body, timeout=timeout)
        data = resp.json() if resp.content else {}
        ok = data.get("status") == "ok"
        return ok, data
    except requests.exceptions.ConnectionError:
        log.debug("IPC: %s on port %d is not running (connection refused)", action, port)
        return False, {"status": "unavailable"}
    except requests.exceptions.Timeout:
        log.debug("IPC: %s on port %d timed out", action, port)
        return False, {"status": "timeout"}
    except Exception as exc:
        log.warning("IPC call %s:%d/%s error: %s", "localhost", port, action, exc)
        return False, {"status": "error", "message": str(exc)}


def _marshal_to_gui_thread(cb, *args) -> None:
    """
    T002 — Qt-first callback marshaling (M3/T304: Tk fallback removed).

    Schedule ``cb(*args)`` on the main GUI thread:

      1. If a Qt application is running (``QCoreApplication.instance()`` is
         not None) use ``QTimer.singleShot(0, ...)`` to defer onto the Qt
         event loop. This is the production path.
      2. Otherwise (headless / unit tests / no event loop) invoke the
         callback directly in the worker thread.

    The legacy Tk fallback (``tk._default_root.after(0, ...)``) was
    deleted in M3/T304 along with the rest of the Tk codepath.

    All marshaling exceptions are swallowed; the direct-call fallback runs
    so the callback never silently disappears.
    """
    # ── 1. Qt path ────────────────────────────────────────────────────
    try:
        from PySide6.QtCore import QCoreApplication, QTimer  # noqa: PLC0415
        app = QCoreApplication.instance()
        if app is not None:
            QTimer.singleShot(0, lambda: cb(*args))
            return
    except Exception:
        pass

    # ── 2. Headless fallback ──────────────────────────────────────────
    try:
        cb(*args)
    except Exception as exc:
        log.error("IPC async callback direct-call error: %s", exc)


def ipc_call_async(
    port: int,
    action: str,
    payload: Optional[Dict[str, Any]] = None,
    on_result: Optional[Any] = None,
    sender: str = "GhostRigger",
):
    """
    Non-blocking IPC call — runs in a daemon thread.
    ``on_result(success, response)`` is marshaled back to the GUI main
    thread via :func:`_marshal_to_gui_thread` (Qt → Tk → direct fallback).
    """
    def _worker():
        ok, resp = ipc_call(port, action, payload, sender)
        if on_result is not None:
            _marshal_to_gui_thread(on_result, ok, resp)

    t = threading.Thread(target=_worker, daemon=True,
                         name=f"IPC-{action}-{port}")
    t.start()
    return t


# ─────────────────────────────────────────────────────────────────────────────
#  High-level GhostRigger → GModular calls
# ─────────────────────────────────────────────────────────────────────────────

def notify_blueprint_saved(resref: str, bp_type: str) -> None:
    """
    Tell GModular (port 7003) that a blueprint was saved so it can
    refresh its viewport.  Called after writing a UTC/UTP/UTD file.

    bp_type: "utc", "utp", or "utd"
    """
    ipc_call_async(
        PORT_GMODULAR,
        "blueprint_saved",
        payload={"resref": resref, "type": bp_type},
        on_result=_log_result("blueprint_saved → GModular"),
    )


def refresh_gmodular_viewport() -> None:
    """Tell GModular to refresh its viewport (e.g. after a model export)."""
    ipc_call_async(
        PORT_GMODULAR,
        "refresh_viewport",
        payload={},
        on_result=_log_result("refresh_viewport → GModular"),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  High-level GhostRigger → GhostScripter calls
# ─────────────────────────────────────────────────────────────────────────────

def open_script_in_scripter(
    resref: str,
    module_dir: str = "",
    template: str = "",
) -> None:
    """Ask GhostScripter (port 7002) to open/create a script."""
    ipc_call_async(
        PORT_GHOSTSCRIPTER,
        "open_script",
        payload={"resref": resref, "module_dir": module_dir, "template": template},
        on_result=_log_result("open_script → GhostScripter"),
    )


def open_dlg_in_scripter(resref: str, module_dir: str = "") -> None:
    """Ask GhostScripter to open a dialogue tree."""
    ipc_call_async(
        PORT_GHOSTSCRIPTER,
        "open_dlg",
        payload={"resref": resref, "module_dir": module_dir},
        on_result=_log_result("open_dlg → GhostScripter"),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Ping helpers
# ─────────────────────────────────────────────────────────────────────────────

def ping_program(
    program_name: str,
    port: int,
    timeout: float = 1.5,
) -> Tuple[bool, str]:
    """
    Ping another Ghostworks program.

    Returns (running: bool, status_message: str).
    """
    ok, resp = ipc_call(port, "ping", payload={}, timeout=timeout)
    if ok:
        return True, f"{program_name} is running on port {port}"
    status = resp.get("status", "unavailable")
    if status == "unavailable":
        return False, f"{program_name} is not running — open it to use this feature"
    return False, f"{program_name} on port {port}: {status}"


def ping_all() -> Dict[str, Tuple[bool, str]]:
    """Ping GhostScripter and GModular, return dict of results."""
    return {
        "GhostScripter": ping_program("GhostScripter", PORT_GHOSTSCRIPTER),
        "GModular":       ping_program("GModular",      PORT_GMODULAR),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _log_result(label: str):
    def _cb(ok: bool, resp: dict):
        if ok:
            log.debug("IPC %s — OK", label)
        else:
            status = resp.get("status", "?")
            if status == "unavailable":
                # Non-intrusive: the other program simply isn't open
                log.debug("IPC %s — target not running", label)
            else:
                log.warning("IPC %s — %s", label, resp)
    return _cb
