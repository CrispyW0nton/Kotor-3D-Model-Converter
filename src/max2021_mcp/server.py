"""3ds Max MCP server (2021 compatible bridge layer).

This module exposes a small MCP tool surface for experimenting with 3ds Max
modeling workflows and scripting behavior. It is designed for research and
comparison work before porting ideas into GhostRigger.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import socket
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


_MCP_AVAILABLE = False
try:
    import mcp.server.lowlevel  # noqa: F401
    import mcp.server.stdio
    import mcp.server.sse
    from mcp.server.lowlevel import NotificationOptions, Server as MCPServer
    from mcp.server.models import InitializationOptions
    from mcp import types as mcp_types
    _MCP_AVAILABLE = True
except ImportError:
    MCPServer = None  # type: ignore[assignment]
    mcp_types = None  # type: ignore[assignment]

try:
    from uvicorn import Config as UvConfig, Server as UvServer  # type: ignore
    _UVICORN_AVAILABLE = True
except ImportError:
    UvConfig = None  # type: ignore[assignment]
    UvServer = None  # type: ignore[assignment]
    _UVICORN_AVAILABLE = False


MAX_TOOL_TEXT_LIMIT = 200_000
DEFAULT_SOCKET_PORT = 19001
DEFAULT_HOST = "127.0.0.1"


@dataclass
class MaxRunResult:
    text: str
    structured: Optional[Any] = None
    is_error: bool = False


class MaxScriptRuntimeError(RuntimeError):
    """Raised when 3ds Max execution cannot be performed."""


class Max2021Runtime:
    """Abstraction over 3ds Max transport.

    Auto-detection order:
    1. In-process `pymxs` runtime (most useful when run inside 3ds Max)
    2. Socket transport to a separate MaxScript bridge process
    """

    def __init__(
        self,
        mode: str = "auto",
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_SOCKET_PORT,
        timeout_seconds: float = 3.0,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds
        self._mode = mode
        self._pymxs_runtime = None

        if self._mode == "auto":
            self._mode = self._detect_mode()
        elif self._mode not in {"pymxs", "socket"}:
            raise ValueError(f"Unknown runtime mode: {self._mode}")

        if self._mode == "pymxs":
            self._pymxs_runtime = self._load_pymxs()
        elif self._mode == "socket":
            self._verify_socket()

    @property
    def mode(self) -> str:
        return self._mode

    def _load_pymxs(self):
        try:
            from pymxs import runtime as rt
            _ = rt.execute("format \"ok\\n\"")
            return rt
        except Exception as exc:
            raise MaxScriptRuntimeError(
                "Could not initialize pymxs in-process runtime. "
                "Run this server from 3ds Max Python or set mode=socket."
            ) from exc

    def _detect_mode(self) -> str:
        try:
            from pymxs import runtime  # noqa: F401
        except Exception:
            pass
        else:
            return "pymxs"

        return "socket"

    def _verify_socket(self) -> None:
        if not self.host or not self.port:
            raise MaxScriptRuntimeError(
                "Socket mode requested but MAX2021_MCP_HOST/MAX2021_MCP_PORT are not set."
            )

    async def execute(self, script: str) -> MaxRunResult:
        if self._mode == "pymxs":
            return await self._execute_via_pymxs(script)
        if self._mode == "socket":
            return await self._execute_via_socket(script)
        raise MaxScriptRuntimeError("No runtime configured.")

    async def _execute_via_pymxs(self, script: str) -> MaxRunResult:
        if self._pymxs_runtime is None:
            raise MaxScriptRuntimeError("pymxs runtime is not initialized.")
        try:
            raw = self._pymxs_runtime.execute(script)
        except Exception as exc:
            raise MaxScriptRuntimeError(f"pymxs execute failed: {exc}") from exc

        if raw is None:
            return MaxRunResult(text="")
        if isinstance(raw, (dict, list, int, float, bool)):
            return MaxRunResult(
                text=json.dumps(raw, ensure_ascii=False),
                structured=raw,
            )
        if isinstance(raw, str):
            return MaxRunResult(text=raw)
        return MaxRunResult(text=str(raw))

    async def _execute_via_socket(self, script: str) -> MaxRunResult:
        payload = {
            "id": self._socket_request_id(),
            "script": script,
        }
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")

        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout_seconds) as sock:
                sock.sendall(data)
                sock.shutdown(socket.SHUT_WR)
                chunks: List[bytes] = []
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    chunks.append(chunk)
        except Exception as exc:
            raise MaxScriptRuntimeError(f"Socket runtime failed: {exc}") from exc

        if not chunks:
            return MaxRunResult(text="", is_error=True)
        raw = b"".join(chunks).decode("utf-8", errors="replace")
        line = raw.strip().splitlines()[0].strip() if raw.strip() else ""
        if not line:
            return MaxRunResult(text="")

        try:
            parsed = json.loads(line)
        except Exception:
            return MaxRunResult(text=line)

        if isinstance(parsed, dict):
            if isinstance(parsed.get("text"), str):
                return MaxRunResult(text=parsed["text"], structured=parsed.get("structured"))
            return MaxRunResult(text=json.dumps(parsed, ensure_ascii=False), structured=parsed)

        if isinstance(parsed, str):
            return MaxRunResult(text=parsed)
        return MaxRunResult(text=str(parsed), structured=parsed)

    def _socket_request_id(self) -> str:
        return f"max2021-{id(self)}"


def _make_text(payload: Any, *, max_chars: int = MAX_TOOL_TEXT_LIMIT) -> Dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[truncated]"
    return {"text": text}


def _lines_to_list(value: str) -> List[str]:
    normalized = value.replace("\r", "")
    return [line.strip() for line in normalized.split("\n") if line.strip()]


def get_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": "max2021_health",
            "description": "Check whether the 3ds Max 2021 MCP runtime is connected.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "max2021_execute",
            "description": "Execute arbitrary MaxScript and return raw text (or parse JSON when expected).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": "MaxScript code to execute.",
                    },
                    "expect_json": {
                        "type": "boolean",
                        "description": "Parse and validate JSON output from the script.",
                        "default": False,
                    },
                },
                "required": ["script"],
            },
        },
        {
            "name": "max2021_list_selected_nodes",
            "description": "List the currently selected scene nodes.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "max2021_list_all_nodes",
            "description": "List all scene nodes (top-level object names).",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]


async def handle_tool(name: str, arguments: Dict[str, Any], runtime: Max2021Runtime) -> Dict[str, Any]:
    if name == "max2021_health":
        return _make_text(
            {
                "connected": True,
                "transport": runtime.mode,
                "host": runtime.host,
                "port": runtime.port,
            }
        )

    if name == "max2021_list_selected_nodes":
        script = (
            "(\n"
            "    local out = \"\"\n"
            "    for node in selection do (\n"
            "        if out != \"\" do out += \"\\n\"\n"
            "        out += node.name\n"
            "    )\n"
            "    out\n"
            ")"
        )
        result = await runtime.execute(script)
        nodes = _lines_to_list(result.text)
        return _make_text({"count": len(nodes), "nodes": nodes})

    if name == "max2021_list_all_nodes":
        script = (
            "(\n"
            "    local out = \"\"\n"
            "    for node in objects do (\n"
            "        if out != \"\" do out += \"\\n\"\n"
            "        out += node.name\n"
            "    )\n"
            "    out\n"
            ")"
        )
        result = await runtime.execute(script)
        nodes = _lines_to_list(result.text)
        return _make_text({"count": len(nodes), "nodes": nodes})

    if name == "max2021_execute":
        script = str(arguments["script"])
        expect_json = bool(arguments.get("expect_json", False))
        result = await runtime.execute(script)
        if expect_json:
            try:
                return _make_text(json.loads(result.text))
            except Exception:
                return _make_text(
                    {
                        "error": "Result could not be parsed as JSON.",
                        "text": result.text,
                    }
                )
        return {"text": result.text}

    raise ValueError(f"Unknown tool: {name!r}")


class _FallbackHTTPServer:
    """Minimal HTTP compatibility endpoint if MCP SDK is unavailable."""

    def __init__(self, runtime: Max2021Runtime, host: str = DEFAULT_HOST, port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.runtime = runtime

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            raw = await reader.read(65536)
            request = raw.decode("utf-8", errors="replace")
            if "\r\n" not in request:
                writer.close()
                return
            request_line = request.split("\r\n", 1)[0]
            parts = request_line.split(" ")
            if len(parts) < 2:
                writer.close()
                return
            method, path = parts[0], parts[1].split("?")[0]

            body_text = ""
            body_start = request.find("\r\n\r\n")
            if body_start != -1:
                body_text = request[body_start + 4 :]
            try:
                body = json.loads(body_text) if body_text.strip() else {}
            except Exception:
                body = {}

            status = "200 OK"
            if method != "POST":
                status = "405 Method Not Allowed"
                response_body = {"error": "Only POST is supported."}
            elif path == "/tools/list":
                response_body = {"tools": get_tools()}
            elif path == "/tools/call":
                try:
                    response_body = {
                        "result": await handle_tool(
                            body.get("name", ""), body.get("arguments", {}), self.runtime
                        )
                    }
                except Exception as exc:
                    status = "500 Internal Server Error"
                    response_body = {"error": str(exc)}
            elif path == "/health":
                response_body = {"status": "ok", "server": "GhostRigger-Max2021MCP"}
            else:
                status = "404 Not Found"
                response_body = {"error": f"Unknown endpoint: {path}"}

            body_bytes = json.dumps(response_body, ensure_ascii=False, indent=2).encode("utf-8")
            headers = (
                f"HTTP/1.1 {status}\r\n"
                "Content-Type: application/json; charset=utf-8\r\n"
                f"Content-Length: {len(body_bytes)}\r\n"
                "Access-Control-Allow-Origin: *\r\n"
                "\r\n"
            )
            writer.write(headers.encode("ascii"))
            writer.write(body_bytes)
            await writer.drain()
        finally:
            writer.close()

    async def serve(self) -> None:
        server = await asyncio.start_server(self.handle, self.host, self.port)
        addr = server.sockets[0].getsockname()
        print(
            f"GhostRigger Max2021 MCP HTTP fallback server on http://{addr[0]}:{addr[1]}",
            flush=True,
        )
        async with server:
            await server.serve_forever()


def _build_mcp_server(runtime: Max2021Runtime):
    if MCPServer is None:
        raise RuntimeError("MCP SDK unavailable")

    server = MCPServer("GhostRigger-Max2021MCP")

    @server.list_tools()
    async def list_tools() -> list:
        return [
            mcp_types.Tool(
                name=entry["name"],
                description=entry["description"],
                inputSchema=entry["inputSchema"],
            )
            for entry in get_tools()
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]):
        payload = await handle_tool(name, arguments, runtime)
        text = payload.get("text", json.dumps(payload))
        return [mcp_types.TextContent(type="text", text=text)]

    return server


async def _run_stdio(runtime: Max2021Runtime) -> None:
    server = _build_mcp_server(runtime)
    async with mcp.server.stdio.stdio_server() as (reader, writer):
        await server.run(
            reader,
            writer,
            InitializationOptions(
                server_name="GhostRigger-Max2021MCP",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
                notification_options=NotificationOptions(),
            ),
        )


async def _run_sse(runtime: Max2021Runtime, host: str, port: int) -> None:
    if not _UVICORN_AVAILABLE:
        raise ImportError("uvicorn is required for SSE mode: pip install uvicorn[standard]")
    server = _build_mcp_server(runtime)
    transport = mcp.server.sse.SseServerTransport("/mcp")

    async def app(scope, receive, send):
        if scope["type"] != "http":
            return
        path = scope.get("path", "")
        method = scope.get("method", "")
        if path == "/mcp" and method == "GET":
            await transport.connect_sse(scope, receive, send)
        elif path == "/mcp" and method == "POST":
            await transport.handle_post_message(scope, receive, send)
        else:
            await send({
                "type": "http.response.start",
                "status": 404,
                "headers": [],
            })
            await send({"type": "http.response.body", "body": b"Not Found"})

    uv = UvServer(UvConfig(app=app, host=host, port=port, log_level="info"))  # type: ignore[arg-type]
    await uv.serve()


async def _run_http_fallback(runtime: Max2021Runtime, host: str, port: int) -> None:
    srv = _FallbackHTTPServer(runtime=runtime, host=host, port=port)
    await srv.serve()


def _build_runtime_from_args(argv: Optional[Any] = None) -> Max2021Runtime:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--adapter", default=os.getenv("MAX2021_MCP_MODE", "auto"))
    parser.add_argument("--host", default=os.getenv("MAX2021_MCP_HOST", DEFAULT_HOST))
    parser.add_argument(
        "--port",
        default=int(os.getenv("MAX2021_MCP_PORT", str(DEFAULT_SOCKET_PORT))),
        type=int,
    )
    parser.add_argument(
        "--timeout",
        default=float(os.getenv("MAX2021_MCP_TIMEOUT_SECONDS", "3.0")),
        type=float,
    )
    parsed, _ = parser.parse_known_args(argv)
    mode = parsed.adapter
    if mode == "auto":
        mode = "auto"
    if mode not in {"auto", "pymxs", "socket"}:
        raise ValueError(f"Unsupported adapter mode: {mode}")
    return Max2021Runtime(
        mode=mode,
        host=parsed.host,
        port=parsed.port,
        timeout_seconds=parsed.timeout,
    )


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m max2021_mcp",
        description="3ds Max 2021 research MCP server",
    )
    parser.add_argument(
        "--mode",
        default="stdio",
        choices=["stdio", "sse", "http"],
        help="Transport mode.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host for HTTP/SSE fallback")
    parser.add_argument("--port", default=8765, type=int, help="Port for HTTP/SSE fallback")
    parser.add_argument(
        "--adapter",
        default=os.getenv("MAX2021_MCP_MODE", "auto"),
        choices=["auto", "pymxs", "socket"],
        help="Runtime transport to 3ds Max.",
    )
    parser.add_argument("--maxscript-host", default=os.getenv("MAX2021_MCP_HOST", DEFAULT_HOST))
    parser.add_argument(
        "--maxscript-port",
        default=int(os.getenv("MAX2021_MCP_PORT", str(DEFAULT_SOCKET_PORT))),
        type=int,
    )
    parser.add_argument(
        "--maxscript-timeout",
        default=float(os.getenv("MAX2021_MCP_TIMEOUT_SECONDS", "3.0")),
        type=float,
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    runtime = Max2021Runtime(
        mode=args.adapter,
        host=args.maxscript_host,
        port=args.maxscript_port,
        timeout_seconds=args.maxscript_timeout,
    )

    if args.mode == "stdio":
        if not _MCP_AVAILABLE:
            print(
                "ERROR: mcp package not installed. "
                "Use http mode for no-MCP transport: python -m max2021_mcp --mode http",
                file=sys.stderr,
            )
            sys.exit(1)
        asyncio.run(_run_stdio(runtime))
        return

    if args.mode == "sse":
        if not _MCP_AVAILABLE:
            print("ERROR: mcp package required for SSE mode.", file=sys.stderr)
            sys.exit(1)
        asyncio.run(_run_sse(runtime, host=args.host, port=args.port))
        return

    if args.mode == "http":
        asyncio.run(_run_http_fallback(runtime=runtime, host=args.host, port=args.port))


if __name__ == "__main__":
    main()
