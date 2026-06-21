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

from src.adapters.qt_ipc.threading import marshal_to_gui_thread

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
    Schedule ``cb(*args)`` through the Qt IPC adapter when an event loop is
    active, otherwise invoke it directly for headless runs and tests.
    """
    if marshal_to_gui_thread(cb, *args):
        return

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
    thread via :func:`_marshal_to_gui_thread`.
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

def show_ghostrigger_panel(panel: str) -> None:
    """Ask a running GhostRigger instance to show a named dock/panel."""
    ipc_call_async(
        PORT_GHOSTRIGGER,
        "show_panel",
        payload={"panel": panel},
        on_result=_log_result("show_panel -> GhostRigger"),
    )


def open_ghostrigger_tool(tool: str) -> None:
    """Ask a running GhostRigger instance to open a workbench/tool surface."""
    ipc_call_async(
        PORT_GHOSTRIGGER,
        "open_tool",
        payload={"tool": tool},
        on_result=_log_result("open_tool -> GhostRigger"),
    )


def run_ghostrigger_viewport_command(command: str, **options: Any) -> None:
    """Ask a running GhostRigger instance to run a whitelisted viewport command."""
    payload = {"command": command}
    payload.update(options)
    ipc_call_async(
        PORT_GHOSTRIGGER,
        "viewport_command",
        payload=payload,
        on_result=_log_result("viewport_command -> GhostRigger"),
    )


def get_ghostrigger_state() -> Tuple[bool, Dict[str, Any]]:
    """Return the synchronous state snapshot from a running GhostRigger instance."""
    return ipc_call(PORT_GHOSTRIGGER, "state", payload={}, timeout=_IPC_TIMEOUT)


def set_ghostrigger_appearance(theme: str = "", layout: str = "", *, persist: bool = True) -> None:
    """Ask a running GhostRigger instance to apply a theme and/or layout."""
    ipc_call_async(
        PORT_GHOSTRIGGER,
        "appearance",
        payload={"theme": theme, "layout": layout, "persist": bool(persist)},
        on_result=_log_result("appearance -> GhostRigger"),
    )


def run_ghostrigger_animation_command(
    command: str,
    animation: str = "",
    *,
    loop: bool | None = None,
    seek: int | float | None = None,
    source: str = "",
    target: str = "",
    object_id: str = "",
) -> None:
    """Ask a running GhostRigger instance to select/play/stop/seek an animation."""
    payload: Dict[str, Any] = {"command": command, "animation": animation, "source": source}
    target_id = str(target or object_id or "")
    if target_id:
        payload["target"] = target_id
    if loop is not None:
        payload["loop"] = bool(loop)
    if seek is not None:
        payload["seek"] = seek
    ipc_call_async(
        PORT_GHOSTRIGGER,
        "animation_command",
        payload=payload,
        on_result=_log_result("animation_command -> GhostRigger"),
    )


def search_ghostrigger_library(
    query: str = "",
    *,
    limit: int = 50,
    game: str = "",
    category: str = "",
    source: str = "",
) -> Tuple[bool, Dict[str, Any]]:
    """Return Content Browser library rows from a running GhostRigger instance."""
    payload: Dict[str, Any] = {"query": query, "limit": int(limit)}
    if game:
        payload["game"] = game
    if category:
        payload["category"] = category
    if source:
        payload["source"] = source
    return ipc_call(PORT_GHOSTRIGGER, "library_search", payload=payload, timeout=_IPC_TIMEOUT)


def select_ghostrigger_library_asset(
    query: str = "",
    *,
    resref: str = "",
    game: str = "",
    load: bool = False,
    import_action: str = "clear",
) -> Tuple[bool, Dict[str, Any]]:
    """Select a Content Browser library asset, optionally loading it into the scene."""
    payload: Dict[str, Any] = {
        "query": query or resref,
        "load": bool(load),
        "import_action": import_action,
    }
    if resref:
        payload["resref"] = resref
    if game:
        payload["game"] = game
    return ipc_call(PORT_GHOSTRIGGER, "library_select", payload=payload, timeout=_IPC_TIMEOUT)


def search_ghostrigger_resources(
    query: str = "",
    *,
    limit: int = 50,
    game: str = "",
    resource_type: str = "",
) -> Tuple[bool, Dict[str, Any]]:
    """Return Resource Browser rows from a running GhostRigger instance."""
    payload: Dict[str, Any] = {"query": query, "limit": int(limit)}
    if game:
        payload["game"] = game
    if resource_type:
        payload["type"] = resource_type
    return ipc_call(PORT_GHOSTRIGGER, "resource_search", payload=payload, timeout=_IPC_TIMEOUT)


def select_ghostrigger_resource(
    query: str = "",
    *,
    resref: str = "",
    game: str = "",
    resource_type: str = "",
    activate: bool = False,
) -> Tuple[bool, Dict[str, Any]]:
    """Select a Resource Browser row, optionally activating its normal UI handler."""
    payload: Dict[str, Any] = {"query": query or resref, "activate": bool(activate)}
    if resref:
        payload["resref"] = resref
    if game:
        payload["game"] = game
    if resource_type:
        payload["type"] = resource_type
    return ipc_call(PORT_GHOSTRIGGER, "resource_select", payload=payload, timeout=_IPC_TIMEOUT)


def new_ghostrigger_scene(game: str = "", *, force: bool = False) -> None:
    """Ask a running GhostRigger instance to create a new KMAX scene."""
    ipc_call_async(
        PORT_GHOSTRIGGER,
        "new_scene",
        payload={"game": game, "force": bool(force)},
        on_result=_log_result("new_scene -> GhostRigger"),
    )


def open_ghostrigger_scene(path: str, *, force: bool = False) -> None:
    """Ask a running GhostRigger instance to open a KMAX scene path."""
    ipc_call_async(
        PORT_GHOSTRIGGER,
        "open_scene",
        payload={"path": path, "force": bool(force)},
        on_result=_log_result("open_scene -> GhostRigger"),
    )


def save_ghostrigger_scene(path: str = "") -> None:
    """Ask a running GhostRigger instance to save the active KMAX scene."""
    ipc_call_async(
        PORT_GHOSTRIGGER,
        "save_scene",
        payload={"path": path},
        on_result=_log_result("save_scene -> GhostRigger"),
    )


def create_ghostrigger_scene_camera(camera_type: str = "Cinematic Camera", name: str = "", *, make_active: bool = False) -> None:
    """Ask a running GhostRigger instance to create a scene camera."""
    ipc_call_async(
        PORT_GHOSTRIGGER,
        "create_scene_camera",
        payload={"type": camera_type, "name": name, "make_active": bool(make_active)},
        on_result=_log_result("create_scene_camera -> GhostRigger"),
    )


def create_ghostrigger_scene_light(light_type: str = "point", name: str = "") -> None:
    """Ask a running GhostRigger instance to create a scene light."""
    ipc_call_async(
        PORT_GHOSTRIGGER,
        "create_scene_light",
        payload={"type": light_type, "name": name},
        on_result=_log_result("create_scene_light -> GhostRigger"),
    )


def select_ghostrigger_scene_object(object_id: str = "", name: str = "") -> None:
    """Ask a running GhostRigger instance to select a scene object."""
    ipc_call_async(
        PORT_GHOSTRIGGER,
        "select_scene_object",
        payload={"id": object_id, "name": name},
        on_result=_log_result("select_scene_object -> GhostRigger"),
    )


def set_ghostrigger_scene_object_visibility(
    object_id: str = "",
    name: str = "",
    *,
    visible: bool = True,
) -> None:
    """Ask a running GhostRigger instance to show or hide a scene object."""
    ipc_call_async(
        PORT_GHOSTRIGGER,
        "set_scene_object_visibility",
        payload={"id": object_id, "name": name, "visible": bool(visible)},
        on_result=_log_result("set_scene_object_visibility -> GhostRigger"),
    )


def run_ghostrigger_scene_object_command(
    command: str,
    *,
    object_id: str = "",
    name: str = "",
    value: Any = None,
) -> Tuple[bool, Dict[str, Any]]:
    """Run an outliner-style command against a KMAX scene object."""
    payload: Dict[str, Any] = {"command": command, "id": object_id, "name": name}
    if value is not None:
        payload["value"] = value
    return ipc_call(PORT_GHOSTRIGGER, "scene_object_command", payload=payload, timeout=30.0)


def set_ghostrigger_scene_object_properties(
    *,
    object_id: str = "",
    name: str = "",
    properties: Optional[Dict[str, Any]] = None,
    **changes: Any,
) -> Tuple[bool, Dict[str, Any]]:
    """Update transform or camera/light properties for a KMAX scene object."""
    payload: Dict[str, Any] = {"id": object_id, "name": name, "properties": dict(properties or {})}
    payload["properties"].update(changes)
    return ipc_call(PORT_GHOSTRIGGER, "scene_object_properties", payload=payload, timeout=30.0)


def select_ghostrigger_module_mesh(mesh: str) -> None:
    """Ask a running GhostRigger instance to select a module mesh by label."""
    ipc_call_async(
        PORT_GHOSTRIGGER,
        "select_module_mesh",
        payload={"mesh": mesh},
        on_result=_log_result("select_module_mesh -> GhostRigger"),
    )


def set_ghostrigger_renderer_backend(backend: str, allow_fallback: bool | None = None) -> None:
    """Ask a running GhostRigger instance to switch viewport renderer backend."""
    payload = {"backend": backend}
    if allow_fallback is not None:
        payload["allow_fallback"] = bool(allow_fallback)
    ipc_call_async(
        PORT_GHOSTRIGGER,
        "set_renderer_backend",
        payload=payload,
        on_result=_log_result("set_renderer_backend -> GhostRigger"),
    )


def set_ghostrigger_dummy_helpers(visible: bool) -> None:
    """Ask a running GhostRigger instance to show or hide dummy/helper markers."""
    ipc_call_async(
        PORT_GHOSTRIGGER,
        "set_dummy_helpers",
        payload={"visible": bool(visible)},
        on_result=_log_result("set_dummy_helpers -> GhostRigger"),
    )


def set_ghostrigger_light_helpers(helpers: bool, volumes: bool | None = None) -> None:
    """Ask a running GhostRigger instance to show or hide light helpers."""
    payload = {"helpers": bool(helpers)}
    if volumes is not None:
        payload["volumes"] = bool(volumes)
    ipc_call_async(
        PORT_GHOSTRIGGER,
        "set_light_helpers",
        payload=payload,
        on_result=_log_result("set_light_helpers -> GhostRigger"),
    )


def select_ghostrigger_helper(name: str = "") -> None:
    """Ask a running GhostRigger instance to select a dummy/helper node."""
    ipc_call_async(
        PORT_GHOSTRIGGER,
        "select_helper",
        payload={"name": name},
        on_result=_log_result("select_helper -> GhostRigger"),
    )


def capture_ghostrigger_viewport(path: str) -> None:
    """Ask a running GhostRigger instance to capture the viewport canvas."""
    ipc_call_async(
        PORT_GHOSTRIGGER,
        "capture_viewport",
        payload={"path": path},
        on_result=_log_result("capture_viewport -> GhostRigger"),
    )


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
