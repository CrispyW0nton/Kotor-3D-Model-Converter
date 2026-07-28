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

import importlib
import json
import logging
import os
from pathlib import Path
import re
import sys
import threading
from typing import Callable, Optional, Dict, Any

from src.adapters.qt_ipc.threading import marshal_to_gui_thread
from .spatial_auth import (
    HEADER_SIGNATURE,
    SpatialAuthenticationError,
    SpatialRequestAuthenticator,
    SpatialRequestSigner,
    SpatialSessionCredentials,
    publish_spatial_session_descriptor,
    remove_spatial_session_descriptor,
)

log = logging.getLogger(__name__)


def _ensure_kotormcp_importable() -> bool:
    """Make the standalone ``kotormcp`` package importable under its own name.

    The native payload importer registers this package as ``src.kotormcp``
    (it strips only the leading ``Python/`` from packaged paths), but
    ``kotormcp`` was ported in as a self-contained MCP server and imports
    itself with bare ``kotormcp.*`` names — including its submodules. Alias the
    payload-registered package to the top-level ``kotormcp`` name so those
    imports resolve, without adding ``src`` to ``sys.path`` (which would make
    every ``src`` subpackage importable twice under two identities).

    Returns True if ``kotormcp`` is importable afterwards.
    """
    if "kotormcp" in sys.modules:
        return True
    try:
        sys.modules["kotormcp"] = importlib.import_module("src.kotormcp")
        return True
    except Exception:  # noqa: BLE001 - fall back to a path-based import
        src_root = Path(__file__).resolve().parents[1]  # .../Python/src
        if (src_root / "kotormcp" / "__init__.py").exists():
            p = str(src_root)
            if p not in sys.path:
                sys.path.insert(0, p)
            return True
        log.exception("kotormcp package could not be made importable")
        return False

# ── IPC Port Assignment (per GHOSTWORKS_BLUEPRINT.md Section 3.1) ──────────
PORT_GHOSTRIGGER  = 7001
PORT_GHOSTSCRIPTER = 7002
PORT_GMODULAR     = 7003

_PROGRAM_NAME = "GhostStudio"
_RESREF_RE = re.compile(r"^[A-Za-z0-9_]{1,16}$")
_IPC_PORT_ENV = "GHOSTRIGGER_IPC_PORT"


def resolve_ghostrigger_ipc_port(raw_value: object | None = None) -> int:
    """Resolve the local IPC port without changing the normal 7001 contract.

    A per-process environment override lets a focus-safe validation instance
    coexist with the user's already-running GhostStudio process. Invalid
    values deliberately fall back to the documented product port.
    """

    value = os.environ.get(_IPC_PORT_ENV, "") if raw_value is None else raw_value
    text = str(value or "").strip()
    if not text:
        return PORT_GHOSTRIGGER
    try:
        port = int(text, 10)
    except (TypeError, ValueError):
        return PORT_GHOSTRIGGER
    return port if 1 <= port <= 65535 else PORT_GHOSTRIGGER


def _validate_map_studio_visual_proof_payload(payload: object) -> tuple[dict[str, Any] | None, str]:
    """Validate and normalise the focus-safe Map Studio proof request."""

    if not isinstance(payload, dict):
        return None, "payload must be a JSON object"

    game = str(payload.get("game") or "").strip().upper()
    if game not in {"K1", "K2"}:
        return None, "game must be 'K1' or 'K2'"

    module_resref = str(payload.get("module_resref") or payload.get("module") or "").strip().lower()
    if not _RESREF_RE.fullmatch(module_resref):
        return None, "module_resref must be a 1-16 character KOTOR resref"

    modules_dir_text = str(payload.get("modules_dir") or "").strip()
    modules_dir = Path(modules_dir_text).expanduser()
    if not modules_dir_text or not modules_dir.is_absolute():
        return None, "modules_dir must be an absolute path"
    if not modules_dir.is_dir():
        return None, f"modules_dir does not exist: {modules_dir}"

    capture_paths: dict[str, Path] = {}
    for key in ("before_path", "after_path"):
        text = str(payload.get(key) or "").strip()
        candidate = Path(text).expanduser()
        if not text or not candidate.is_absolute():
            return None, f"{key} must be an absolute path"
        if candidate.suffix.lower() != ".png":
            return None, f"{key} must end in .png"
        capture_paths[key] = candidate.resolve(strict=False)
    if capture_paths["before_path"] == capture_paths["after_path"]:
        return None, "before_path and after_path must be different files"

    activate = payload.get("activate", False)
    if not isinstance(activate, bool):
        return None, "activate must be a boolean"
    if activate:
        return None, "map_studio_visual_proof is focus-safe; activate must be false"

    settle_ms = payload.get("settle_ms", 5000)
    if isinstance(settle_ms, bool) or not isinstance(settle_ms, int) or not 0 <= settle_ms <= 5000:
        return None, "settle_ms must be an integer between 0 and 5000"
    # A positive visual-proof delay is a renderer-residency contract, not a
    # caller-selected performance knob.  Stock module textures can still be
    # decoding/uploading after the former 750 ms default, yielding a nearly
    # black capture that looked superficially different and falsely passed.
    # Preserve zero only for deterministic focused tests; real proofs always
    # receive the full measured residency window.
    settle_ms = 0 if settle_ms == 0 else 5000

    expected_room = str(payload.get("expected_room_resref") or "").strip().lower()
    if expected_room and not _RESREF_RE.fullmatch(expected_room):
        return None, "expected_room_resref must be a valid KOTOR resref"

    expected_count = payload.get("expected_backdrop_surface_count", None)
    if expected_count is not None:
        if isinstance(expected_count, bool) or not isinstance(expected_count, int) or not 0 <= expected_count <= 1024:
            return None, "expected_backdrop_surface_count must be an integer between 0 and 1024"

    raw_textures = payload.get("expected_textures", {})
    if raw_textures is None:
        raw_textures = {}
    if not isinstance(raw_textures, dict) or len(raw_textures) > 64:
        return None, "expected_textures must be an object with at most 64 entries"
    expected_textures: dict[str, list[int]] = {}
    for raw_name, raw_size in raw_textures.items():
        name = str(raw_name or "").strip().lower()
        if not _RESREF_RE.fullmatch(name):
            return None, f"invalid expected texture resref: {raw_name!r}"
        if (
            not isinstance(raw_size, (list, tuple))
            or len(raw_size) != 2
            or any(isinstance(value, bool) or not isinstance(value, int) for value in raw_size)
        ):
            return None, f"expected texture size for {name} must be [width, height]"
        width, height = int(raw_size[0]), int(raw_size[1])
        if not 1 <= width <= 8192 or not 1 <= height <= 8192:
            return None, f"expected texture size for {name} must be between 1 and 8192 pixels"
        expected_textures[name] = [width, height]

    return {
        "game": game,
        "module_resref": module_resref,
        "modules_dir": str(modules_dir.resolve()),
        "before_path": str(capture_paths["before_path"]),
        "after_path": str(capture_paths["after_path"]),
        "activate": activate,
        "settle_ms": settle_ms,
        "expected_room_resref": expected_room,
        "expected_backdrop_surface_count": expected_count,
        "expected_textures": expected_textures,
    }, ""


def _validate_map_studio_pie_visual_proof_payload(payload: object) -> tuple[dict[str, Any] | None, str]:
    """Validate one focus-safe, bounded PIE motion/capture request."""

    if not isinstance(payload, dict):
        return None, "payload must be a JSON object"

    kmap_text = str(payload.get("kmap_path") or "").strip()
    kmap_path = Path(kmap_text).expanduser()
    if not kmap_text or not kmap_path.is_absolute():
        return None, "kmap_path must be an absolute path"
    if kmap_path.suffix.lower() != ".kmap":
        return None, "kmap_path must end in .kmap"
    if not kmap_path.is_file():
        return None, f"kmap_path does not exist: {kmap_path}"

    capture_text = str(payload.get("capture_dir") or "").strip()
    capture_dir = Path(capture_text).expanduser()
    if not capture_text or not capture_dir.is_absolute():
        return None, "capture_dir must be an absolute path"

    activate = payload.get("activate", False)
    if not isinstance(activate, bool):
        return None, "activate must be a boolean"
    if activate:
        return None, "map_studio_pie_visual_proof is focus-safe; activate must be false"

    settle_ms = payload.get("settle_ms", 1500)
    if isinstance(settle_ms, bool) or not isinstance(settle_ms, int) or not 0 <= settle_ms <= 5000:
        return None, "settle_ms must be an integer between 0 and 5000"
    movement_ms = payload.get("movement_ms", 1200)
    if isinstance(movement_ms, bool) or not isinstance(movement_ms, int) or not 100 <= movement_ms <= 5000:
        return None, "movement_ms must be an integer between 100 and 5000"
    sample_count = payload.get("sample_count", 12)
    # Each proof also captures one post-movement frame.  Keep the stationary
    # sequence at the proven twelve-frame bound: an extended 24-frame request
    # exhausted the native ModernGL/QPixmap capture path on a real Debug run
    # while the default 12 + motion sequence completed continuously.
    if isinstance(sample_count, bool) or not isinstance(sample_count, int) or not 2 <= sample_count <= 12:
        return None, "sample_count must be an integer between 2 and 12"

    motion: dict[str, float] = {}
    for key, default in (("forward", 1.0), ("strafe", 0.0)):
        raw = payload.get(key, default)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return None, f"{key} must be a number between -1 and 1"
        value = float(raw)
        if not -1.0 <= value <= 1.0:
            return None, f"{key} must be a number between -1 and 1"
        motion[key] = value
    run = payload.get("run", False)
    if not isinstance(run, bool):
        return None, "run must be a boolean"
    expected_min_distance = payload.get("expected_min_distance", 0.05)
    if isinstance(expected_min_distance, bool) or not isinstance(expected_min_distance, (int, float)):
        return None, "expected_min_distance must be a number between 0 and 25"
    expected_min_distance = float(expected_min_distance)
    if not 0.0 <= expected_min_distance <= 25.0:
        return None, "expected_min_distance must be a number between 0 and 25"

    return {
        "kmap_path": str(kmap_path.resolve()),
        "capture_dir": str(capture_dir.resolve(strict=False)),
        "activate": False,
        "settle_ms": int(settle_ms),
        "movement_ms": int(movement_ms),
        "sample_count": int(sample_count),
        "forward": motion["forward"],
        "strafe": motion["strafe"],
        "run": run,
        "expected_min_distance": expected_min_distance,
    }, ""


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

    def __init__(
        self,
        callbacks: Optional[Dict[str, Callable]] = None,
        port: int | None = None,
        *,
        program_name: str = _PROGRAM_NAME,
        spatial_authenticator: SpatialRequestAuthenticator | None = None,
        spatial_session_path: str | os.PathLike[str] | None = None,
    ):
        if spatial_authenticator is not None and spatial_session_path is not None:
            raise ValueError(
                "spatial_authenticator and spatial_session_path are mutually exclusive"
            )
        self.callbacks: Dict[str, Callable] = callbacks or {}
        self._thread: Optional[threading.Thread] = None
        self._app = None
        self._http_server = None
        self._running = False
        self._port = resolve_ghostrigger_ipc_port() if port is None else int(port)
        self._program_name = str(program_name or _PROGRAM_NAME)
        self._spatial_authenticator = spatial_authenticator
        self._spatial_session_path = (
            Path(spatial_session_path).expanduser()
            if spatial_session_path is not None
            else None
        )
        if (
            self._spatial_session_path is not None
            and not self._spatial_session_path.is_absolute()
        ):
            raise ValueError("spatial_session_path must be absolute")
        self._spatial_session_id: str | None = None
        self._spatial_session_lock = threading.Lock()
        self._startup_complete = threading.Event()
        self._startup_error: BaseException | None = None
        self._stop_requested = threading.Event()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self):
        """Start the IPC server in a daemon background thread."""
        if self._running or (
            self._thread is not None and self._thread.is_alive()
        ):
            return
        self._startup_complete.clear()
        self._startup_error = None
        self._stop_requested.clear()
        self._thread = threading.Thread(
            target=self._run_server,
            name="GhostRigger-IPC-Server",
            daemon=True,
        )
        self._thread.start()
        log.info("GhostRigger IPC server starting on port %d", self._port)
        if self._spatial_session_path is None:
            return
        if not self._startup_complete.wait(15.0):
            self.stop()
            raise RuntimeError(
                "Ghost Studio spatial IPC session startup timed out"
            )
        if self._startup_error is not None:
            if self._thread is not None:
                self._thread.join(timeout=2.0)
            raise RuntimeError(
                "Ghost Studio spatial IPC session failed to start"
            ) from self._startup_error
        if not self._running:
            raise RuntimeError(
                "Ghost Studio spatial IPC session stopped during startup"
            )

    @property
    def port(self) -> int:
        """Return the actual per-process listening port."""

        return int(self._port)

    def stop(self):
        """Stop the background Werkzeug server without leaving a bound port."""
        self._stop_requested.set()
        self._running = False
        if self._spatial_session_path is not None:
            self._spatial_authenticator = None
        self._remove_owned_spatial_session_descriptor()
        server = self._http_server
        if server is not None:
            try:
                server.shutdown()
            except Exception:
                log.exception("GhostStudio IPC server shutdown failed")
        log.info("GhostRigger IPC server stopping")

    def _remove_owned_spatial_session_descriptor(self) -> None:
        path = self._spatial_session_path
        if path is None:
            return
        with self._spatial_session_lock:
            session_id = self._spatial_session_id
            if not session_id:
                return
            try:
                remove_spatial_session_descriptor(
                    path,
                    session_id=session_id,
                )
            except Exception:
                log.exception(
                    "Ghost Studio spatial session descriptor cleanup failed"
                )
            finally:
                self._spatial_session_id = None

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
            self._startup_error = RuntimeError("Flask is not installed")
            self._startup_complete.set()
            log.warning(
                "Flask not installed — GhostRigger IPC server unavailable. "
                "Install with: pip install flask"
            )
            return

        app = Flask(__name__)
        self._app = app

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

        def _authenticate_spatial_request():
            authenticator = self._spatial_authenticator
            if authenticator is None:
                return jsonify({
                    "status": "error",
                    "code": "spatial-auth-unconfigured",
                }), 503
            body_bytes = request.get_data(cache=True, as_text=False)
            try:
                authenticator.verify(
                    headers=request.headers,
                    method=request.method,
                    path=request.path,
                    body=body_bytes,
                )
            except SpatialAuthenticationError as exc:
                return jsonify({
                    "status": "error",
                    "code": exc.code,
                }), 401
            return None

        def _strict_spatial_payload(allowed_keys: set[str]):
            body = request.get_json(force=True, silent=True)
            if not isinstance(body, dict):
                return None, (
                    jsonify({
                        "status": "error",
                        "code": "invalid-spatial-payload",
                    }),
                    400,
                )
            if any(
                not isinstance(key, str) or key not in allowed_keys
                for key in body
            ):
                return None, (
                    jsonify({
                        "status": "error",
                        "code": "invalid-spatial-payload",
                    }),
                    400,
                )
            return body, None

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
                return _ok(action, {"program": self._program_name, "port": self._port})
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
            return jsonify({"status": "ok", "program": self._program_name, "result": payload_result})

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
            return jsonify({"status": "ok", "program": self._program_name, "result": payload_result})

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
            return jsonify({"status": "ok", "program": self._program_name, "result": payload_result})

        @app.route("/api/mesh_tool_command", methods=["POST"])
        def route_mesh_tool_command():
            """Run a Mesh Tools command through the shared command service.

            Payload shape:
            {
              "command": "create_cube",
              "target": {"id": "...", "name": "..."},
              "selection": {"mode": "face", "ids": [1, 2, 3]},
              "options": {"dimensions": [1, 1, 1], "grid_snap": true}
            }
            """
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            command = str(payload.get("command", payload.get("cmd", body.get("command", ""))) or "").strip()
            if not command:
                return jsonify({"status": "error", "message": "missing command"}), 400

            cb = self.callbacks.get("mesh_tool_command")
            if cb is None:
                return jsonify({"status": "error", "message": "mesh_tool_command callback unavailable"}), 503
            ok, result = self._invoke_callback_sync(cb, payload, timeout=30.0)
            if not ok:
                return jsonify({"status": "error", "command": command, "message": str(result)}), 504
            response = result if isinstance(result, dict) else {"status": "ok", "command": command, "result": result}
            response.setdefault("status", "ok")
            response.setdefault("command", command)
            response.setdefault("program", self._program_name)
            return jsonify(response)

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

        @app.route("/api/map_studio_visual_proof", methods=["POST"])
        def route_map_studio_visual_proof():
            """Run a focus-safe stock-skybox before/after proof in Map Studio."""

            body = request.get_json(force=True, silent=True) or {}
            payload, validation_error = _validate_map_studio_visual_proof_payload(_payload(body))
            if payload is None:
                return jsonify({"status": "error", "message": validation_error}), 400

            cb = self.callbacks.get("map_studio_visual_proof")
            if cb is None:
                return jsonify({"status": "error", "message": "map_studio_visual_proof callback unavailable"}), 503
            ok, result = self._invoke_callback_sync(cb, payload, timeout=180.0)
            if not ok:
                return jsonify({"status": "error", "message": str(result)}), 504
            proof = result if isinstance(result, dict) else {"status": "blocked", "value": result}
            return jsonify({"status": "ok", "program": self._program_name, "proof": proof})

        @app.route("/api/map_studio_pie_visual_proof", methods=["POST"])
        def route_map_studio_pie_visual_proof():
            """Run a focus-safe bounded PIE motion/capture proof."""

            body = request.get_json(force=True, silent=True) or {}
            payload, validation_error = _validate_map_studio_pie_visual_proof_payload(_payload(body))
            if payload is None:
                return jsonify({"status": "error", "message": validation_error}), 400

            cb = self.callbacks.get("map_studio_pie_visual_proof")
            if cb is None:
                return jsonify({"status": "error", "message": "map_studio_pie_visual_proof callback unavailable"}), 503
            # Cold-opening an editable stock module can legitimately cross the
            # 90-second mark while the UI remains responsive.  Match the
            # bounded Map Studio proof timeout so the synchronous IPC caller
            # can receive that completed proof instead of a false timeout.
            ok, result = self._invoke_callback_sync(cb, payload, timeout=180.0)
            if not ok:
                return jsonify({"status": "error", "message": str(result)}), 504
            proof = result if isinstance(result, dict) else {"status": "blocked", "value": result}
            return jsonify({"status": "ok", "program": self._program_name, "proof": proof})

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
            return jsonify({"status": "ok", "program": self._program_name, "library": payload_result})

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
            return jsonify({"status": "ok", "program": self._program_name, "selection": payload_result})

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
            return jsonify({"status": "ok", "program": self._program_name, "resources": payload_result})

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
            return jsonify({"status": "ok", "program": self._program_name, "selection": payload_result})

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
            return jsonify({"status": "ok", "program": self._program_name, "state": payload})

        # ── MCP Studio spatial endpoints ───────────────────────────────────
        # These are a separate, authenticated, read-focused surface. Legacy
        # Ghostworks/KotorMCP routes above and below are not implicitly trusted
        # merely because this narrow channel is configured.

        @app.route("/api/mcpstudio/health", methods=["GET"])
        def route_mcpstudio_health():
            auth_error = _authenticate_spatial_request()
            if auth_error is not None:
                return auth_error
            return jsonify({
                "status": "ok",
                "schema": "ghoststudio-spatial-health/v1",
                "program": self._program_name,
                "capabilities": [
                    "health",
                    "spatial-snapshot",
                    "capture",
                    "evidence-gaps",
                ],
            })

        @app.route("/api/mcpstudio/spatial-snapshot", methods=["POST"])
        def route_mcpstudio_spatial_snapshot():
            auth_error = _authenticate_spatial_request()
            if auth_error is not None:
                return auth_error
            payload, payload_error = _strict_spatial_payload({
                "includeBounds",
                "includeHierarchy",
                "includeSelection",
            })
            if payload_error is not None:
                return payload_error
            cb = self.callbacks.get("get_spatial_snapshot")
            if cb is None:
                return jsonify({
                    "status": "error",
                    "code": "spatial-snapshot-unavailable",
                }), 503
            ok, snapshot = self._invoke_callback_sync(cb, payload, timeout=3.0)
            if not ok or not isinstance(snapshot, dict):
                return jsonify({
                    "status": "error",
                    "code": "spatial-snapshot-failed",
                }), 504
            return jsonify({
                "status": "ok",
                "schema": "ghoststudio-spatial-response/v1",
                "snapshot": snapshot,
            })

        @app.route("/api/mcpstudio/capture", methods=["POST"])
        def route_mcpstudio_capture():
            auth_error = _authenticate_spatial_request()
            if auth_error is not None:
                return auth_error
            payload, payload_error = _strict_spatial_payload({"captureId"})
            if payload_error is not None:
                return payload_error
            capture_id = str(payload.get("captureId") or "")
            if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", capture_id):
                return jsonify({
                    "status": "error",
                    "code": "invalid-capture-id",
                }), 400
            cb = self.callbacks.get("capture_spatial_evidence")
            if cb is None:
                return jsonify({
                    "status": "error",
                    "code": "spatial-capture-unavailable",
                }), 503
            ok, capture = self._invoke_callback_sync(cb, payload, timeout=5.0)
            if not ok or not isinstance(capture, dict):
                return jsonify({
                    "status": "error",
                    "code": "spatial-capture-failed",
                }), 504
            return jsonify({
                "status": "ok",
                "schema": "ghoststudio-spatial-response/v1",
                "capture": capture,
            })

        @app.route("/api/mcpstudio/evidence-gaps", methods=["POST"])
        def route_mcpstudio_evidence_gaps():
            auth_error = _authenticate_spatial_request()
            if auth_error is not None:
                return auth_error
            payload, payload_error = _strict_spatial_payload(set())
            if payload_error is not None:
                return payload_error
            cb = self.callbacks.get("get_spatial_evidence_gaps")
            if cb is None:
                return jsonify({
                    "status": "error",
                    "code": "spatial-evidence-unavailable",
                }), 503
            ok, evidence = self._invoke_callback_sync(cb, payload, timeout=3.0)
            if not ok or not isinstance(evidence, dict):
                return jsonify({
                    "status": "error",
                    "code": "spatial-evidence-failed",
                }), 504
            return jsonify({
                "status": "ok",
                "schema": "ghoststudio-spatial-response/v1",
                "evidence": evidence,
            })

        @app.route("/api/health", methods=["GET"])
        def route_health():
            return jsonify({"status": "ok", "program": self._program_name,
                            "port": self._port, "version": "2.8",
                            "mcp": True})

        # ── KotorMCP tool endpoints ────────────────────────────────────────
        # These mirror the KotorMCP JSON API so Claude and other agents can
        # call KotOR resource tools directly via the IPC server.

        @app.route("/mcp/tools/list", methods=["GET", "POST"])
        def route_mcp_tools_list():
            """Return all available MCP tool definitions."""
            try:
                _ensure_kotormcp_importable()
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
                _ensure_kotormcp_importable()
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
                _ensure_kotormcp_importable()
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
                _ensure_kotormcp_importable()
                from kotormcp import mcp_resources  # noqa: PLC0415
                content = asyncio.run(mcp_resources.read_resource(uri))
                return jsonify({"content": content})
            except Exception as exc:
                return jsonify({"error": str(exc)}), 500

        @app.route("/api/<path:action_name>", methods=["POST"])
        def route_catch_all(action_name):
            """Dispatch registered compatibility actions with a bounded payload."""

            cb = self.callbacks.get(str(action_name))
            if cb is None:
                return jsonify({"status": "error", "action": action_name,
                                "message": f"unknown action: {action_name}"}), 404
            body = request.get_json(force=True, silent=True) or {}
            payload = _payload(body)
            ok, result = self._invoke_callback_sync(cb, payload, timeout=30.0)
            if not ok:
                return jsonify({
                    "status": "error",
                    "action": action_name,
                    "program": self._program_name,
                    "message": str(result),
                }), 500
            response = {
                "status": "ok",
                "action": action_name,
                "program": self._program_name,
            }
            if isinstance(result, dict):
                response.update(result)
            elif result is not None:
                response["result"] = result
            return jsonify(response)

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
        srv = None
        try:
            from werkzeug.serving import make_server
            srv = make_server("127.0.0.1", self._port, app, threaded=True)
            self._http_server = srv
            if self._port == 0:
                self._port = int(srv.server_port)
            if self._spatial_session_path is not None:
                credentials = SpatialSessionCredentials.create()
                self._spatial_authenticator = SpatialRequestAuthenticator(
                    credentials
                )
                with self._spatial_session_lock:
                    self._spatial_session_id = credentials.session_id
                    publish_spatial_session_descriptor(
                        self._spatial_session_path,
                        port=self._port,
                        credentials=credentials,
                    )
            if self._stop_requested.is_set():
                return
            self._running = True
            log.info("GhostRigger IPC server bound on port %d", self._port)
            self._startup_complete.set()
            srv.serve_forever()
        except Exception as exc:
            self._startup_error = exc
            if isinstance(exc, OSError) and (
                "Address already in use" in str(exc)
                or "10048" in str(exc)
            ):
                log.warning(
                    "GhostRigger IPC port %d already in use — "
                    "another instance may be running.",
                    self._port,
                )
            else:
                log.exception("GhostRigger IPC server failed")
        finally:
            self._running = False
            self._startup_complete.set()
            self._remove_owned_spatial_session_descriptor()
            if srv is not None:
                try:
                    close_server = getattr(srv, "server_close", None)
                    if callable(close_server):
                        close_server()
                except Exception:
                    log.exception("GhostRigger IPC server close failed")
            self._http_server = None
            if self._spatial_session_path is not None:
                self._spatial_authenticator = None

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
