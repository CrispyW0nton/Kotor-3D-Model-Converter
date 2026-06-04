"""
GhostRigger IPC Server — port 7001
Implements the Ghostworks Pipeline IPC contract from GHOSTWORKS_BLUEPRINT.md.

Listens on http://localhost:7001/api/<action> for JSON POST requests from
GhostScripter (port 7002) and GModular (port 7003).

Actions received:
  open_utc     — open a creature blueprint for editing
  open_utp     — open a placeable blueprint for editing
  open_utd     — open a door blueprint for editing
  open_mdl     — open a 3D model for viewing/editing
  ping         — health-check, returns {"status":"ok","program":"GhostRigger"}

Actions sent (client calls):
  blueprint_saved → GModular port 7003 when a blueprint is saved
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Callable, Optional, Dict, Any

from src.adapters.qt_ipc.threading import marshal_to_gui_thread

log = logging.getLogger(__name__)

# ── IPC Port Assignment (per GHOSTWORKS_BLUEPRINT.md Section 3.1) ──────────
PORT_GHOSTRIGGER  = 7001
PORT_GHOSTSCRIPTER = 7002
PORT_GMODULAR     = 7003

_PROGRAM_NAME = "GhostRigger"


# ─────────────────────────────────────────────────────────────────────────────
#  GhostRigger IPC Server  (Flask, runs in background thread)
# ─────────────────────────────────────────────────────────────────────────────

class GhostRiggerIPCServer:
    """
    Flask-based IPC server running on port 7001.

    Usage:
        server = GhostRiggerIPCServer(callbacks)
        server.start()   # non-blocking, starts background thread
        ...
        server.stop()

    callbacks dict keys (all optional, set to callable or None):
        'open_utc'  : Callable[[str, str], None]   (resref, module_dir)
        'open_utp'  : Callable[[str, str], None]
        'open_utd'  : Callable[[str, str], None]
        'open_mdl'  : Callable[[str, str], None]
    """

    def __init__(self, callbacks: Optional[Dict[str, Callable]] = None, port: int = 7001):
        self.callbacks: Dict[str, Callable] = callbacks or {}
        self._thread: Optional[threading.Thread] = None
        self._app = None
        self._running = False
        self._port = port   # allow test to override port

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self):
        """Start the IPC server in a daemon background thread."""
        if self._running:
            return
        self._thread = threading.Thread(
            target=self._run_server,
            name="GhostRigger-IPC-Server",
            daemon=True,
        )
        self._thread.start()
        log.info("GhostRigger IPC server starting on port %d", PORT_GHOSTRIGGER)

    def stop(self):
        """Stop the server (best-effort — Flask dev server can't be stopped cleanly)."""
        self._running = False
        log.info("GhostRigger IPC server stopping")

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Server thread ─────────────────────────────────────────────────────

    def _run_server(self):
        try:
            from flask import Flask, request, jsonify
        except ImportError:
            log.warning(
                "Flask not installed — GhostRigger IPC server unavailable. "
                "Install with: pip install flask"
            )
            return

        app = Flask(__name__)
        self._app = app
        self._running = True

        # Suppress Flask startup banner
        import os as _os
        _os.environ.setdefault("WERKZEUG_RUN_MAIN", "true")

        # Disable Flask request logging to keep the console clean
        logging.getLogger("werkzeug").setLevel(logging.ERROR)

        # ── Endpoint factory ───────────────────────────────────────────────

        def _ok(action: str, extra: dict = None):
            resp = {"status": "ok", "action": action}
            if extra:
                resp.update(extra)
            return jsonify(resp)

        def _err(action: str, message: str):
            return jsonify({"status": "error", "action": action, "message": message}), 400

        def _payload(body: dict) -> dict:
            payload = body.get("payload", body)
            return payload if isinstance(payload, dict) else {}

        def _handle(action: str):
            """Generic IPC endpoint handler."""
            try:
                body = request.get_json(force=True, silent=True) or {}
            except Exception:
                body = {}

            log.debug("IPC received: %s %s", action, body)

            cb = self.callbacks.get(action)
            if cb is not None:
                try:
                    if action in ("open_utc", "open_utp", "open_utd", "open_mdl"):
                        # Payload can be top-level OR nested under "payload" key.
                        payload = _payload(body)
                        resref = payload.get("resref", body.get("resref", ""))
                        module_dir = payload.get("module_dir", body.get("module_dir", ""))
                        # Schedule callback on the main thread when Qt is active.
                        self._schedule_callback(cb, resref, module_dir)
                    else:
                        self._schedule_callback(cb)
                except Exception as exc:
                    log.error("IPC callback error for %s: %s", action, exc)
                    return _err(action, str(exc))

            if action == "ping":
                return _ok(action, {"program": _PROGRAM_NAME, "port": self._port})
            return _ok(action)

        # ── Routes ────────────────────────────────────────────────────────

        @app.route("/api/open_utc", methods=["POST"])
        def route_open_utc():
            return _handle("open_utc")

        @app.route("/api/open_utp", methods=["POST"])
        def route_open_utp():
            return _handle("open_utp")

        @app.route("/api/open_utd", methods=["POST"])
        def route_open_utd():
            return _handle("open_utd")

        @app.route("/api/open_mdl", methods=["POST"])
        def route_open_mdl():
            return _handle("open_mdl")

        @app.route("/api/ping", methods=["POST"])
        def route_ping():
            return _handle("ping")

        @app.route("/api/reload", methods=["POST"])
        def route_reload():
            """Hot-reload selected Python modules and refresh the viewport."""
            import importlib
            import sys

            try:
                body = request.get_json(force=True, silent=True) or {}
            except Exception:
                body = {}

            targets = body.get("modules", [
                "src.core.rendering.frame_core.renderer",
                "src.adapters.rendering.moderngl_legacy_bridge",
                "src.adapters.rendering.moderngl_scene_helpers",
                "src.core.kotor_loader",
            ])
            reloaded: list[str] = []
            errors: list[str] = []

            for mod_name in targets:
                if mod_name not in sys.modules:
                    continue
                try:
                    importlib.reload(sys.modules[mod_name])
                    reloaded.append(mod_name)
                except Exception as exc:
                    errors.append(f"{mod_name}: {exc}")

            cb = self.callbacks.get("refresh_viewport")
            if cb is not None:
                try:
                    self._schedule_callback(cb)
                except Exception as exc:
                    errors.append(f"refresh_viewport: {exc}")

            return jsonify({"status": "ok", "action": "reload",
                            "reloaded": reloaded, "errors": errors})

        @app.route("/api/load_model", methods=["POST"])
        def route_load_model():
            """Load a game model into the running viewport for visual QA."""
            body = request.get_json(force=True, silent=True) or {}
            game = str(body.get("game", "k2") or "k2").lower()
            resref = str(body.get("resref", "") or "").strip()
            if not resref:
                return jsonify({"error": "missing resref"}), 400
            if game not in {"k1", "k2"}:
                return jsonify({"error": "game must be 'k1' or 'k2'"}), 400

            cb = self.callbacks.get("load_model_by_resref")
            if cb is not None:
                self._schedule_callback(cb, game, resref)
            return jsonify({"status": "ok", "loading": resref, "game": game})

        @app.route("/api/show_panel", methods=["POST"])
        def route_show_panel():
            """Show a GhostRigger dock/panel in the running UI for visual QA."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            panel = str(payload.get("panel", body.get("panel", "")) or "").strip()
            if not panel:
                return jsonify({"error": "missing panel"}), 400

            cb = self.callbacks.get("show_panel")
            if cb is not None:
                self._schedule_callback(cb, panel)
            return jsonify({"status": "ok", "showing": panel})

        @app.route("/api/select_module_mesh", methods=["POST"])
        def route_select_module_mesh():
            """Select a module mesh by display name in the running viewport/list."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            mesh = str(payload.get("mesh", body.get("mesh", "")) or "").strip()
            if not mesh:
                return jsonify({"error": "missing mesh"}), 400

            cb = self.callbacks.get("select_module_mesh")
            if cb is not None:
                self._schedule_callback(cb, mesh)
            return jsonify({"status": "ok", "selecting": mesh})

        @app.route("/api/set_renderer_backend", methods=["POST"])
        def route_set_renderer_backend():
            """Switch the running viewport renderer for visual QA."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            backend = str(payload.get("backend", body.get("backend", "")) or "").strip()
            if not backend:
                return jsonify({"error": "missing backend"}), 400
            allow_fallback = payload.get("allow_fallback", body.get("allow_fallback", None))

            cb = self.callbacks.get("set_renderer_backend")
            if cb is not None:
                self._schedule_callback(cb, backend, allow_fallback)
            return jsonify({"status": "ok", "renderer_backend": backend})

        @app.route("/api/set_dummy_helpers", methods=["POST"])
        def route_set_dummy_helpers():
            """Show or hide dummy/helper markers in the running viewport."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            visible = payload.get("visible", body.get("visible", True))

            cb = self.callbacks.get("set_dummy_helpers")
            if cb is not None:
                self._schedule_callback(cb, visible)
            return jsonify({"status": "ok", "visible": bool(visible)})

        @app.route("/api/set_light_helpers", methods=["POST"])
        def route_set_light_helpers():
            """Show or hide light helper markers/volumes in the running viewport."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            helpers = payload.get("helpers", body.get("helpers", True))
            volumes = payload.get("volumes", body.get("volumes", helpers))

            cb = self.callbacks.get("set_light_helpers")
            if cb is not None:
                self._schedule_callback(cb, helpers, volumes)
            return jsonify({"status": "ok", "helpers": bool(helpers), "volumes": bool(volumes)})

        @app.route("/api/select_helper", methods=["POST"])
        def route_select_helper():
            """Select a dummy/helper node by name, or the first visible helper."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            name = str(payload.get("name", body.get("name", "")) or "").strip()

            cb = self.callbacks.get("select_helper")
            if cb is not None:
                self._schedule_callback(cb, name)
            return jsonify({"status": "ok", "selecting": name or "<first-helper>"})

        @app.route("/api/capture_viewport", methods=["POST"])
        def route_capture_viewport():
            """Capture the running viewport canvas to a PNG path for visual QA."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            path = str(payload.get("path", body.get("path", "")) or "").strip()
            if not path:
                return jsonify({"error": "missing path"}), 400

            cb = self.callbacks.get("capture_viewport")
            if cb is not None:
                self._schedule_callback(cb, path)
            return jsonify({"status": "ok", "path": path})

        @app.route("/api/health", methods=["GET"])
        def route_health():
            return jsonify({"status": "ok", "program": _PROGRAM_NAME,
                            "port": self._port, "version": "2.8",
                            "mcp": True})

        # ── KotorMCP tool endpoints ────────────────────────────────────────
        # These mirror the KotorMCP JSON API so Claude and other agents can
        # call KotOR resource tools directly via the IPC server.

        @app.route("/mcp/tools/list", methods=["GET", "POST"])
        def route_mcp_tools_list():
            """Return all available MCP tool definitions."""
            try:
                from kotormcp.tools import get_all_tools  # noqa: PLC0415
                return jsonify({"tools": get_all_tools()})
            except Exception as exc:
                return jsonify({"error": str(exc)}), 500

        @app.route("/mcp/tools/call", methods=["POST"])
        def route_mcp_tools_call():
            """
            Call an MCP tool by name.
            Body: {"name": "toolName", "arguments": {...}}
            """
            import asyncio  # noqa: PLC0415
            try:
                body = request.get_json(force=True, silent=True) or {}
                tool_name = body.get("name", "")
                arguments = body.get("arguments", {})
                if not tool_name:
                    return jsonify({"error": "Missing 'name' in request body"}), 400
                from kotormcp.tools import handle_tool  # noqa: PLC0415
                result = asyncio.run(handle_tool(tool_name, arguments))
                return jsonify({"result": result})
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 404
            except Exception as exc:
                log.error("MCP tool call error: %s", exc)
                return jsonify({"error": str(exc)}), 500

        @app.route("/mcp/resources/list", methods=["GET", "POST"])
        def route_mcp_resources_list():
            """Return the kotor:// URI resource template list."""
            import asyncio  # noqa: PLC0415
            try:
                from kotormcp import mcp_resources  # noqa: PLC0415
                resources = asyncio.run(mcp_resources.list_resources())
                return jsonify({"resources": resources})
            except Exception as exc:
                return jsonify({"error": str(exc)}), 500

        @app.route("/mcp/resources/read", methods=["POST"])
        def route_mcp_resources_read():
            """
            Read a kotor:// resource URI.
            Body: {"uri": "kotor://k1/2da/appearance"}
            """
            import asyncio  # noqa: PLC0415
            try:
                body = request.get_json(force=True, silent=True) or {}
                uri = body.get("uri", "")
                if not uri:
                    return jsonify({"error": "Missing 'uri' in request body"}), 400
                from kotormcp import mcp_resources  # noqa: PLC0415
                content = asyncio.run(mcp_resources.read_resource(uri))
                return jsonify({"content": content})
            except Exception as exc:
                return jsonify({"error": str(exc)}), 500

        @app.route("/api/<path:action_name>", methods=["POST"])
        def route_catch_all(action_name):
            """Catch-all for unknown POST actions — returns JSON error."""
            return jsonify({"status": "error", "action": action_name,
                            "message": f"unknown action: {action_name}"}), 404

        @app.errorhandler(404)
        def not_found(e):
            return jsonify({"status": "error", "message": "unknown action"}), 404

        @app.errorhandler(405)
        def method_not_allowed(e):
            return jsonify({"status": "error", "message": "method not allowed"}), 405

        # ── Start ─────────────────────────────────────────────────────────
        # Use werkzeug make_server directly to avoid the WERKZEUG_SERVER_FD
        # environment variable issue present in newer werkzeug versions when
        # running inside a daemon thread (no reloader needed).
        try:
            from werkzeug.serving import make_server
            srv = make_server("127.0.0.1", self._port, app, threaded=True)
            self._running = True
            log.info("GhostRigger IPC server bound on port %d", self._port)
            srv.serve_forever()
        except OSError as exc:
            if "Address already in use" in str(exc) or "10048" in str(exc):
                log.warning(
                    "GhostRigger IPC port %d already in use — "
                    "another instance may be running.",
                    self._port,
                )
            else:
                log.error("GhostRigger IPC server error: %s", exc)
        finally:
            self._running = False

    def _schedule_callback(self, cb: Callable, *args):
        """Execute a callback through Qt when active, otherwise directly."""
        if marshal_to_gui_thread(cb, *args):
            return

        try:
            cb(*args)
        except Exception as exc:
            log.error("IPC callback direct error: %s", exc)

    def set_callback(self, action: str, cb: Callable):
        """Register or replace a callback for the given IPC action."""
        self.callbacks[action] = cb

    def remove_callback(self, action: str):
        self.callbacks.pop(action, None)
