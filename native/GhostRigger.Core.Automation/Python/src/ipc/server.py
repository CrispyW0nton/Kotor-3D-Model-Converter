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

    def _invoke_callback_sync(self, cb: Callable, *args: Any, timeout: float = 2.0) -> tuple[bool, Any]:
        """Invoke a callback on the GUI thread and wait briefly for its result."""
        done = threading.Event()
        result: dict[str, Any] = {}

        def _runner() -> None:
            try:
                result["value"] = cb(*args)
                result["ok"] = True
            except Exception as exc:
                result["value"] = str(exc)
                result["ok"] = False
                log.exception("IPC synchronous callback failed")
            finally:
                done.set()

        if not marshal_to_gui_thread(_runner):
            _runner()
        if not done.wait(max(0.1, float(timeout))):
            return False, "callback timeout"
        return bool(result.get("ok", False)), result.get("value")

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

        @app.route("/api/new_scene", methods=["POST"])
        def route_new_scene():
            """Create a new KMAX scene in the running application."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            game = str(payload.get("game", body.get("game", "")) or "").strip()
            force = bool(payload.get("force", body.get("force", False)))

            cb = self.callbacks.get("new_scene")
            if cb is not None:
                self._schedule_callback(cb, game, force)
            return jsonify({"status": "ok", "game": game, "force": force})

        @app.route("/api/open_scene", methods=["POST"])
        def route_open_scene():
            """Open a KMAX scene by path in the running application."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            path = str(payload.get("path", body.get("path", "")) or "").strip()
            if not path:
                return jsonify({"error": "missing path"}), 400
            force = bool(payload.get("force", body.get("force", False)))

            cb = self.callbacks.get("open_scene")
            if cb is not None:
                self._schedule_callback(cb, path, force)
            return jsonify({"status": "ok", "opening": path, "force": force})

        @app.route("/api/save_scene", methods=["POST"])
        def route_save_scene():
            """Save the active KMAX scene, optionally to a supplied path."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            path = str(payload.get("path", body.get("path", "")) or "").strip()

            cb = self.callbacks.get("save_scene")
            if cb is not None:
                self._schedule_callback(cb, path)
            return jsonify({"status": "ok", "path": path})

        @app.route("/api/create_scene_camera", methods=["POST"])
        def route_create_scene_camera():
            """Create a KMAX scene camera in the running application."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            camera_type = str(payload.get("type", payload.get("camera_type", body.get("type", "Cinematic Camera"))) or "Cinematic Camera").strip()
            name = str(payload.get("name", body.get("name", "")) or "").strip()
            make_active = bool(payload.get("make_active", body.get("make_active", False)))

            cb = self.callbacks.get("create_scene_camera")
            if cb is not None:
                self._schedule_callback(cb, camera_type, name, make_active)
            return jsonify({"status": "ok", "camera_type": camera_type, "name": name, "make_active": make_active})

        @app.route("/api/create_scene_light", methods=["POST"])
        def route_create_scene_light():
            """Create a KMAX scene light in the running application."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            light_type = str(payload.get("type", payload.get("light_type", body.get("type", "point"))) or "point").strip()
            name = str(payload.get("name", body.get("name", "")) or "").strip()

            cb = self.callbacks.get("create_scene_light")
            if cb is not None:
                self._schedule_callback(cb, light_type, name)
            return jsonify({"status": "ok", "light_type": light_type, "name": name})

        @app.route("/api/select_scene_object", methods=["POST"])
        def route_select_scene_object():
            """Select a KMAX scene object by id or name."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            object_id = str(payload.get("id", payload.get("object_id", body.get("id", ""))) or "").strip()
            name = str(payload.get("name", body.get("name", "")) or "").strip()
            if not (object_id or name):
                return jsonify({"error": "missing id or name"}), 400

            cb = self.callbacks.get("select_scene_object")
            if cb is not None:
                self._schedule_callback(cb, object_id, name)
            return jsonify({"status": "ok", "object_id": object_id, "name": name})

        @app.route("/api/set_scene_object_visibility", methods=["POST"])
        def route_set_scene_object_visibility():
            """Show or hide a KMAX scene object by id or name."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            object_id = str(payload.get("id", payload.get("object_id", body.get("id", ""))) or "").strip()
            name = str(payload.get("name", body.get("name", "")) or "").strip()
            if not (object_id or name):
                return jsonify({"error": "missing id or name"}), 400
            visible = bool(payload.get("visible", body.get("visible", True)))

            cb = self.callbacks.get("set_scene_object_visibility")
            if cb is not None:
                self._schedule_callback(cb, object_id, name, visible)
            return jsonify({"status": "ok", "object_id": object_id, "name": name, "visible": visible})

        @app.route("/api/scene_object_command", methods=["POST"])
        def route_scene_object_command():
            """Run an outliner-style command against a KMAX scene object."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            command = str(payload.get("command", payload.get("cmd", body.get("command", ""))) or "").strip()
            if not command:
                return jsonify({"error": "missing command"}), 400
            object_id = str(payload.get("id", payload.get("object_id", body.get("id", ""))) or "").strip()
            name = str(payload.get("name", body.get("name", "")) or "").strip()
            if not (object_id or name):
                return jsonify({"error": "missing id or name"}), 400
            value = payload.get("value", body.get("value", None))

            cb = self.callbacks.get("scene_object_command")
            if cb is None:
                return jsonify({"status": "error", "message": "scene_object_command callback unavailable"}), 503
            ok, result = self._invoke_callback_sync(cb, command, object_id, name, value, timeout=30.0)
            if not ok:
                return jsonify({"status": "error", "message": str(result)}), 504
            payload_result = result if isinstance(result, dict) else {"value": result}
            return jsonify({"status": "ok", "program": _PROGRAM_NAME, "result": payload_result})

        @app.route("/api/scene_object_properties", methods=["POST"])
        def route_scene_object_properties():
            """Update transform or type-specific properties for a KMAX scene object."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            object_id = str(payload.get("id", payload.get("object_id", body.get("id", ""))) or "").strip()
            name = str(payload.get("name", body.get("name", "")) or "").strip()
            if not (object_id or name):
                return jsonify({"error": "missing id or name"}), 400
            properties = payload.get("properties", body.get("properties", {}))
            if not isinstance(properties, dict):
                properties = {}
            for key, value in payload.items():
                if key not in {"id", "object_id", "name", "properties"}:
                    properties.setdefault(key, value)

            cb = self.callbacks.get("scene_object_properties")
            if cb is None:
                return jsonify({"status": "error", "message": "scene_object_properties callback unavailable"}), 503
            ok, result = self._invoke_callback_sync(cb, object_id, name, properties, timeout=30.0)
            if not ok:
                return jsonify({"status": "error", "message": str(result)}), 504
            payload_result = result if isinstance(result, dict) else {"value": result}
            return jsonify({"status": "ok", "program": _PROGRAM_NAME, "result": payload_result})

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

        @app.route("/api/show_window", methods=["POST"])
        def route_show_window():
            """Raise the main GhostRigger window in the running UI for visual QA."""
            cb = self.callbacks.get("show_window")
            if cb is not None:
                self._schedule_callback(cb)
            return jsonify({"status": "ok", "showing": "main_window"})

        @app.route("/api/open_tool", methods=["POST"])
        def route_open_tool():
            """Open a GhostRigger workbench, standalone tool window, or dock."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            tool = str(payload.get("tool", body.get("tool", "")) or "").strip()
            if not tool:
                return jsonify({"error": "missing tool"}), 400

            cb = self.callbacks.get("open_tool")
            if cb is not None:
                self._schedule_callback(cb, tool)
            return jsonify({"status": "ok", "opening": tool})

        @app.route("/api/viewport_command", methods=["POST"])
        def route_viewport_command():
            """Run a whitelisted viewport workflow command in the running UI."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            command = str(payload.get("command", payload.get("cmd", body.get("command", ""))) or "").strip()
            if not command:
                return jsonify({"error": "missing command"}), 400
            options = dict(payload)
            options.pop("command", None)
            options.pop("cmd", None)

            cb = self.callbacks.get("viewport_command")
            if cb is not None:
                self._schedule_callback(cb, command, options)
            return jsonify({"status": "ok", "command": command, "options": options})

        @app.route("/api/appearance", methods=["POST"])
        def route_appearance():
            """Apply a GhostRigger theme and/or layout in the running UI."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            theme = str(payload.get("theme", payload.get("theme_id", body.get("theme", ""))) or "").strip()
            layout = str(payload.get("layout", payload.get("layout_id", body.get("layout", ""))) or "").strip()
            persist = bool(payload.get("persist", body.get("persist", True)))
            if not (theme or layout):
                return jsonify({"error": "missing theme or layout"}), 400

            cb = self.callbacks.get("appearance")
            if cb is not None:
                self._schedule_callback(cb, theme, layout, persist)
            return jsonify({"status": "ok", "theme": theme, "layout": layout, "persist": persist})

        @app.route("/api/animation_command", methods=["POST"])
        def route_animation_command():
            """Select, play, stop, loop, or seek a current-model animation."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            command = str(payload.get("command", payload.get("cmd", body.get("command", ""))) or "").strip()
            if not command:
                return jsonify({"error": "missing command"}), 400
            animation = str(payload.get("animation", payload.get("anim", body.get("animation", ""))) or "").strip()
            source = str(payload.get("source", body.get("source", "")) or "").strip()
            target = str(
                payload.get(
                    "target",
                    payload.get("object_id", body.get("target", body.get("object_id", ""))),
                )
                or ""
            ).strip()
            loop = payload.get("loop", body.get("loop", None))
            seek = payload.get("seek", payload.get("percent", body.get("seek", None)))

            cb = self.callbacks.get("animation_command")
            if cb is not None:
                self._schedule_callback(cb, command, animation, loop, seek, source, target)
            return jsonify({
                "status": "ok",
                "command": command,
                "animation": animation,
                "source": source,
                "target": target,
                "loop": None if loop is None else bool(loop),
                "seek": seek,
            })

        @app.route("/api/sequence_command", methods=["POST"])
        def route_sequence_command():
            """Run a focused Sequence Editor workflow command in the running UI."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            command = str(payload.get("command", payload.get("cmd", body.get("command", ""))) or "").strip()
            if not command:
                return jsonify({"error": "missing command"}), 400

            cb = self.callbacks.get("sequence_command")
            if cb is None:
                return jsonify({"status": "error", "message": "sequence_command callback unavailable"}), 503
            ok, result = self._invoke_callback_sync(cb, command, payload, timeout=30.0)
            if not ok:
                return jsonify({"status": "error", "message": str(result)}), 504
            payload_result = result if isinstance(result, dict) else {"value": result}
            return jsonify({"status": "ok", "program": _PROGRAM_NAME, "result": payload_result})

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

        @app.route("/api/capture_window", methods=["POST"])
        def route_capture_window():
            """Capture the running main window to a PNG path for visual QA."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            path = str(payload.get("path", body.get("path", "")) or "").strip()
            if not path:
                return jsonify({"error": "missing path"}), 400

            cb = self.callbacks.get("capture_window")
            if cb is not None:
                self._schedule_callback(cb, path)
            return jsonify({"status": "ok", "path": path})

        @app.route("/api/library_search", methods=["GET", "POST"])
        def route_library_search():
            """Return searchable rows from the running app's indexed Content Browser library."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            query = str(payload.get("query", payload.get("q", body.get("query", ""))) or "").strip()
            limit = payload.get("limit", body.get("limit", 50))
            filters = dict(payload)
            for key in ("query", "q", "limit"):
                filters.pop(key, None)

            cb = self.callbacks.get("library_search")
            if cb is None:
                return jsonify({"status": "error", "message": "library_search callback unavailable"}), 503
            ok, result = self._invoke_callback_sync(cb, query, limit, filters, timeout=3.0)
            if not ok:
                return jsonify({"status": "error", "message": str(result)}), 504
            payload_result = result if isinstance(result, dict) else {"value": result}
            return jsonify({"status": "ok", "program": _PROGRAM_NAME, "library": payload_result})

        @app.route("/api/library_select", methods=["POST"])
        def route_library_select():
            """Select a Content Browser library row, optionally loading it into the scene."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            query = str(payload.get("query", payload.get("q", payload.get("resref", body.get("query", "")))) or "").strip()
            if not query:
                return jsonify({"error": "missing query or resref"}), 400
            load = bool(payload.get("load", body.get("load", False)))
            import_action = str(payload.get("import_action", payload.get("action", body.get("import_action", "clear"))) or "clear")
            filters = dict(payload)
            for key in ("query", "q", "resref", "load", "import_action", "action"):
                filters.pop(key, None)

            cb = self.callbacks.get("library_select")
            if cb is None:
                return jsonify({"status": "error", "message": "library_select callback unavailable"}), 503
            ok, result = self._invoke_callback_sync(cb, query, filters, load, import_action, timeout=3.0)
            if not ok:
                return jsonify({"status": "error", "message": str(result)}), 504
            payload_result = result if isinstance(result, dict) else {"value": result}
            return jsonify({"status": "ok", "program": _PROGRAM_NAME, "selection": payload_result})

        @app.route("/api/resource_search", methods=["GET", "POST"])
        def route_resource_search():
            """Return searchable rows from the running app's Resource Browser index."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            query = str(payload.get("query", payload.get("q", body.get("query", ""))) or "").strip()
            limit = payload.get("limit", body.get("limit", 50))
            filters = dict(payload)
            for key in ("query", "q", "limit"):
                filters.pop(key, None)

            cb = self.callbacks.get("resource_search")
            if cb is None:
                return jsonify({"status": "error", "message": "resource_search callback unavailable"}), 503
            ok, result = self._invoke_callback_sync(cb, query, limit, filters, timeout=4.0)
            if not ok:
                return jsonify({"status": "error", "message": str(result)}), 504
            payload_result = result if isinstance(result, dict) else {"value": result}
            return jsonify({"status": "ok", "program": _PROGRAM_NAME, "resources": payload_result})

        @app.route("/api/resource_select", methods=["POST"])
        def route_resource_select():
            """Select a Resource Browser row, optionally activating its normal UI handler."""
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            query = str(payload.get("query", payload.get("q", payload.get("resref", body.get("query", "")))) or "").strip()
            if not query:
                return jsonify({"error": "missing query or resref"}), 400
            activate = bool(payload.get("activate", payload.get("open", body.get("activate", False))))
            filters = dict(payload)
            for key in ("query", "q", "resref", "activate", "open"):
                filters.pop(key, None)

            cb = self.callbacks.get("resource_select")
            if cb is None:
                return jsonify({"status": "error", "message": "resource_select callback unavailable"}), 503
            ok, result = self._invoke_callback_sync(cb, query, filters, activate, timeout=4.0)
            if not ok:
                return jsonify({"status": "error", "message": str(result)}), 504
            payload_result = result if isinstance(result, dict) else {"value": result}
            return jsonify({"status": "ok", "program": _PROGRAM_NAME, "selection": payload_result})

        @app.route("/api/state", methods=["GET", "POST"])
        def route_state():
            """Return a synchronous snapshot of the running GhostRigger UI state."""
            cb = self.callbacks.get("get_state")
            if cb is None:
                return jsonify({"status": "error", "message": "state callback unavailable"}), 503
            ok, state = self._invoke_callback_sync(cb)
            if not ok:
                return jsonify({"status": "error", "message": str(state)}), 504
            payload = state if isinstance(state, dict) else {"value": state}
            return jsonify({"status": "ok", "program": _PROGRAM_NAME, "state": payload})

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
