"""Bounded stdio MCP server for Ghost Studio's private spatial IPC surface.

The adapter deliberately exposes only four fixed tools.  It does not import
KotorMCP, accept arbitrary URLs or paths, inherit proxy configuration, or
write protocol diagnostics to stdout.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable, Mapping, TextIO
import urllib.error
import urllib.request


def _load_spatial_auth_module():
    """Load the shared contract without executing legacy ``ipc.__init__``.

    That package initializer intentionally imports the broad historical IPC
    surface.  The narrow adapter must remain independently launchable.
    """

    module_name = "_ghoststudio_spatial_auth_contract"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    module_path = Path(__file__).resolve().parents[1] / "ipc" / "spatial_auth.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Ghost Studio spatial authentication contract is unavailable.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_SPATIAL_AUTH = _load_spatial_auth_module()
SpatialAuthenticationError = _SPATIAL_AUTH.SpatialAuthenticationError
SpatialRequestSigner = _SPATIAL_AUTH.SpatialRequestSigner
SpatialSessionDescriptor = _SPATIAL_AUTH.SpatialSessionDescriptor
default_spatial_session_path = _SPATIAL_AUTH.default_spatial_session_path
load_spatial_session_descriptor = _SPATIAL_AUTH.load_spatial_session_descriptor


SERVER_NAME = "ghoststudio-spatial"
SERVER_VERSION = "0.1.0"
LATEST_PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = frozenset(
    {
        LATEST_PROTOCOL_VERSION,
        "2025-06-18",
        "2025-03-26",
        "2024-11-05",
        "2024-10-07",
    }
)
MAX_STDIN_FRAME_BYTES = 1024 * 1024
MAX_HTTP_RESPONSE_BYTES = (4 * 1024 * 1024) - (64 * 1024)
HTTP_TIMEOUT_SECONDS = 8.0
CAPTURE_ID_PATTERN = r"^[A-Za-z0-9_-]{16,128}$"
_CAPTURE_ID_RE = re.compile(CAPTURE_ID_PATTERN)
_SESSION_PATH_ENV = "GHOSTSTUDIO_SPATIAL_SESSION_PATH"


class SpatialAdapterError(RuntimeError):
    """A stable non-secret error safe to return through MCP."""

    _MESSAGES = {
        "ghoststudio-unavailable": (
            "Ghost Studio's authenticated spatial session is unavailable."
        ),
        "invalid-response": "Ghost Studio returned an invalid spatial response.",
        "response-too-large": (
            "Ghost Studio's spatial response exceeds the bounded MCP frame."
        ),
        "spatial-request-failed": (
            "Ghost Studio could not complete the authenticated spatial request."
        ),
    }

    def __init__(self, code: str):
        self.code = code
        super().__init__(self._MESSAGES.get(code, "Ghost Studio spatial request failed."))


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        del request, file_pointer, code, message, headers, new_url
        raise SpatialAdapterError("invalid-response")


@dataclass(frozen=True)
class _ToolRoute:
    method: str
    path: str


TOOL_ROUTES: Mapping[str, _ToolRoute] = {
    "ghoststudio_health": _ToolRoute("GET", "/api/mcpstudio/health"),
    "ghoststudio_spatial_snapshot": _ToolRoute(
        "POST",
        "/api/mcpstudio/spatial-snapshot",
    ),
    "ghoststudio_capture": _ToolRoute("POST", "/api/mcpstudio/capture"),
    "ghoststudio_evidence_gaps": _ToolRoute(
        "POST",
        "/api/mcpstudio/evidence-gaps",
    ),
}


TOOLS: tuple[dict[str, Any], ...] = (
    {
        "name": "ghoststudio_health",
        "title": "Ghost Studio Spatial Health",
        "description": (
            "Verify the live authenticated Ghost Studio spatial session and "
            "report its narrow capability set."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "ghoststudio_spatial_snapshot",
        "title": "Ghost Studio Spatial Snapshot",
        "description": (
            "Read a revisioned scene, hierarchy, selection, camera, viewport, "
            "and grid snapshot from the live Ghost Studio process."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "includeBounds": {"type": "boolean", "default": True},
                "includeHierarchy": {"type": "boolean", "default": True},
                "includeSelection": {"type": "boolean", "default": True},
            },
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "ghoststudio_capture",
        "title": "Capture Ghost Studio Spatial Evidence",
        "description": (
            "Capture a viewport PNG bound to exact scene and viewport revisions. "
            "A screenshot is visual evidence and does not by itself prove a GUI action."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "captureId": {
                    "type": "string",
                    "pattern": CAPTURE_ID_PATTERN,
                    "minLength": 16,
                    "maxLength": 128,
                }
            },
            "required": ["captureId"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    },
    {
        "name": "ghoststudio_evidence_gaps",
        "title": "Ghost Studio Spatial Evidence Gaps",
        "description": (
            "Report which spatial claims remain unavailable, inferred, or "
            "unproven by the current semantic and visual evidence."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
)


def _strict_object(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError("Tool arguments must be a JSON object.")
    return dict(value)


def _validate_arguments(name: str, arguments: Any) -> dict[str, Any]:
    payload = _strict_object(arguments)
    if name in {"ghoststudio_health", "ghoststudio_evidence_gaps"}:
        if payload:
            raise ValueError(f"{name} does not accept arguments.")
        return payload
    if name == "ghoststudio_spatial_snapshot":
        allowed = {"includeBounds", "includeHierarchy", "includeSelection"}
        if set(payload) - allowed:
            raise ValueError("Spatial snapshot arguments contain unknown fields.")
        if any(not isinstance(value, bool) for value in payload.values()):
            raise ValueError("Spatial snapshot flags must be booleans.")
        return payload
    if name == "ghoststudio_capture":
        if set(payload) != {"captureId"}:
            raise ValueError("Capture requires exactly one captureId.")
        capture_id = payload["captureId"]
        if not isinstance(capture_id, str) or not _CAPTURE_ID_RE.fullmatch(capture_id):
            raise ValueError("captureId must be a 16-128 character safe token.")
        return payload
    raise KeyError(name)


def _descriptor_path(environ: Mapping[str, str] | None = None) -> Path:
    values = os.environ if environ is None else environ
    configured = str(values.get(_SESSION_PATH_ENV) or "").strip()
    if not configured:
        return default_spatial_session_path(values)
    path = Path(configured).expanduser()
    if not path.is_absolute():
        raise SpatialAdapterError("ghoststudio-unavailable")
    return path


class GhostStudioSpatialClient:
    """Signed, proxy-free client for the loopback-only GUI bridge."""

    def __init__(
        self,
        *,
        session_path: Path | None = None,
        descriptor_loader: Callable[[str | os.PathLike[str]], SpatialSessionDescriptor] = (
            load_spatial_session_descriptor
        ),
        opener: Any | None = None,
        timeout_seconds: float = HTTP_TIMEOUT_SECONDS,
    ):
        self._session_path = session_path or _descriptor_path()
        self._descriptor_loader = descriptor_loader
        self._opener = opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            _NoRedirectHandler(),
        )
        self._timeout_seconds = float(timeout_seconds)

    def call(self, name: str, arguments: Any) -> dict[str, Any]:
        route = TOOL_ROUTES.get(name)
        if route is None:
            raise KeyError(name)
        payload = _validate_arguments(name, arguments)
        body = (
            b""
            if route.method == "GET"
            else json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        try:
            descriptor = self._descriptor_loader(self._session_path)
            signer = SpatialRequestSigner(descriptor.credentials)
            headers = signer.sign(
                method=route.method,
                path=route.path,
                body=body,
            )
        except (OSError, SpatialAuthenticationError, ValueError) as exc:
            raise SpatialAdapterError("ghoststudio-unavailable") from exc
        if route.method != "GET":
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"http://127.0.0.1:{descriptor.port}{route.path}",
            data=None if route.method == "GET" else body,
            headers=headers,
            method=route.method,
        )
        return self._open_json(request)

    def _open_json(self, request: urllib.request.Request) -> dict[str, Any]:
        try:
            with self._opener.open(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                status = int(getattr(response, "status", 0) or response.getcode())
                content_type = str(response.headers.get("Content-Type") or "")
                length_text = str(response.headers.get("Content-Length") or "").strip()
                if length_text:
                    try:
                        content_length = int(length_text, 10)
                        if content_length < 0:
                            raise SpatialAdapterError("invalid-response")
                        if content_length > MAX_HTTP_RESPONSE_BYTES:
                            raise SpatialAdapterError("response-too-large")
                    except ValueError as exc:
                        raise SpatialAdapterError("invalid-response") from exc
                raw = response.read(MAX_HTTP_RESPONSE_BYTES + 1)
        except SpatialAdapterError:
            raise
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            OSError,
        ) as exc:
            raise SpatialAdapterError("spatial-request-failed") from exc
        if status != 200:
            raise SpatialAdapterError("spatial-request-failed")
        if not content_type.lower().split(";", 1)[0].strip() == "application/json":
            raise SpatialAdapterError("invalid-response")
        if len(raw) > MAX_HTTP_RESPONSE_BYTES:
            raise SpatialAdapterError("response-too-large")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SpatialAdapterError("invalid-response") from exc
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            raise SpatialAdapterError("invalid-response")
        return payload


class GhostStudioSpatialMcpServer:
    """Small JSON-RPC dispatcher compatible with MCP stdio framing."""

    def __init__(
        self,
        *,
        client_factory: Callable[[], GhostStudioSpatialClient] = (
            GhostStudioSpatialClient
        ),
    ):
        self._client_factory = client_factory

    def dispatch(self, message: Any) -> dict[str, Any] | None:
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return self._error(None, -32600, "Invalid Request")
        method = message.get("method")
        request_id = message.get("id")
        if not isinstance(method, str):
            return self._error(request_id, -32600, "Invalid Request")
        if "id" not in message:
            return None
        if (
            request_id is not None
            and (
                isinstance(request_id, bool)
                or not isinstance(request_id, (str, int))
            )
        ):
            return self._error(None, -32600, "Invalid Request")
        params = message.get("params", {})
        if method == "initialize":
            if not isinstance(params, dict):
                return self._error(request_id, -32602, "Invalid params")
            requested = str(params.get("protocolVersion") or "")
            negotiated = (
                requested
                if requested in SUPPORTED_PROTOCOL_VERSIONS
                else LATEST_PROTOCOL_VERSION
            )
            return self._result(
                request_id,
                {
                    "protocolVersion": negotiated,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {
                        "name": SERVER_NAME,
                        "version": SERVER_VERSION,
                    },
                    "instructions": (
                        "Use only the four authenticated Ghost Studio spatial "
                        "tools. Visual captures do not prove unobserved GUI actions."
                    ),
                },
            )
        if method == "ping":
            return self._result(request_id, {})
        if method == "tools/list":
            if not isinstance(params, dict) or set(params) - {"cursor"}:
                return self._error(request_id, -32602, "Invalid params")
            if params.get("cursor") not in (None, ""):
                return self._error(request_id, -32602, "Invalid cursor")
            return self._result(
                request_id,
                {"tools": [dict(tool) for tool in TOOLS]},
            )
        if method == "tools/call":
            return self._call_tool(request_id, params)
        return self._error(request_id, -32601, "Method not found")

    def _call_tool(self, request_id: Any, params: Any) -> dict[str, Any]:
        if not isinstance(params, dict) or set(params) - {"name", "arguments"}:
            return self._error(request_id, -32602, "Invalid params")
        name = params.get("name")
        if not isinstance(name, str) or name not in TOOL_ROUTES:
            return self._error(request_id, -32602, "Unknown tool")
        try:
            arguments = _validate_arguments(name, params.get("arguments"))
            payload = self._client_factory().call(name, arguments)
        except ValueError as exc:
            return self._tool_error(request_id, "invalid-arguments", str(exc))
        except SpatialAdapterError as exc:
            return self._tool_error(request_id, exc.code, str(exc))
        except Exception:
            return self._tool_error(
                request_id,
                "spatial-request-failed",
                "Ghost Studio spatial request failed.",
            )
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if len(text.encode("utf-8")) > MAX_HTTP_RESPONSE_BYTES:
            return self._tool_error(
                request_id,
                "response-too-large",
                "Ghost Studio spatial response exceeds the bounded MCP frame.",
            )
        return self._result(
            request_id,
            {
                "content": [{"type": "text", "text": text}],
                "structuredContent": payload,
            },
        )

    @staticmethod
    def _result(request_id: Any, result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(
        request_id: Any,
        code: int,
        message: str,
    ) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }

    @classmethod
    def _tool_error(
        cls,
        request_id: Any,
        code: str,
        message: str,
    ) -> dict[str, Any]:
        return cls._result(
            request_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"status": "error", "code": code, "message": message},
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    }
                ],
                "isError": True,
            },
        )

    def run(
        self,
        input_stream: TextIO = sys.stdin,
        output_stream: TextIO = sys.stdout,
    ) -> None:
        for raw_line in input_stream:
            if len(raw_line.encode("utf-8")) > MAX_STDIN_FRAME_BYTES:
                self._write(
                    output_stream,
                    self._error(None, -32700, "Parse error"),
                )
                continue
            try:
                message = json.loads(raw_line)
            except json.JSONDecodeError:
                self._write(
                    output_stream,
                    self._error(None, -32700, "Parse error"),
                )
                continue
            response = self.dispatch(message)
            if response is not None:
                self._write(output_stream, response)

    @staticmethod
    def _write(output_stream: TextIO, payload: dict[str, Any]) -> None:
        serialized = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        encoded_size = len(serialized.encode("utf-8"))
        if encoded_size > MAX_STDIN_FRAME_BYTES * 4:
            payload = GhostStudioSpatialMcpServer._tool_error(
                payload.get("id"),
                "response-too-large",
                "Ghost Studio spatial response exceeds the bounded MCP frame.",
            )
            serialized = json.dumps(payload, separators=(",", ":"))
        output_stream.write(serialized + "\n")
        output_stream.flush()


def main() -> None:
    GhostStudioSpatialMcpServer().run()


if __name__ == "__main__":
    main()
