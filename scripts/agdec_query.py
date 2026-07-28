"""Query the OpenKotOR AgentDecompile Ghidra MCP server (Odyssey engine).

Usage:
  py -3.14 scripts/agdec_query.py tools
  py -3.14 scripts/agdec_query.py call <tool_name> '<json_args>'

Raw MCP-over-HTTP JSON-RPC; used to validate Map Studio output against the
real engine (K1/K2 GFF field semantics, script events, module loading).
"""
from __future__ import annotations

import ipaddress
import json
import os
import sys
import urllib.parse
import urllib.request

BASE_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "User-Agent": "PyKotorAgent/1.0",
    "X-Agent-Version": "1.0",
}
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        del request, file_pointer, code, message, headers, new_url
        raise RuntimeError("AgentDecompile MCP redirects are not allowed.")


OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    _NoRedirectHandler(),
)


def _is_local_host(hostname: str) -> bool:
    normalized = hostname.strip().casefold().rstrip(".")
    if (
        normalized in {"localhost", "ip6-localhost"}
        or normalized.endswith(".localhost")
        or normalized.endswith(".local")
        or "." not in normalized
    ):
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return bool(
        address.is_loopback
        or address.is_private
        or address.is_link_local
    )


def _connection() -> tuple[str, dict[str, str]]:
    url = os.environ.get("AGENTDECOMPILE_MCP_SERVER_URL", "").strip()
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not _is_local_host(parsed.hostname)
    ):
        raise RuntimeError(
            "Set AGENTDECOMPILE_MCP_SERVER_URL to the reviewed local MCP endpoint."
        )
    raw_headers = os.environ.get("AGENTDECOMPILE_MCP_HEADERS_JSON", "").strip()
    if not raw_headers:
        raise RuntimeError(
            "Set AGENTDECOMPILE_MCP_HEADERS_JSON from a private local secret store."
        )
    try:
        configured = json.loads(raw_headers)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "AGENTDECOMPILE_MCP_HEADERS_JSON must be valid JSON."
        ) from exc
    if (
        not isinstance(configured, dict)
        or any(
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(value, str)
            or "\r" in key
            or "\n" in key
            or "\r" in value
            or "\n" in value
            for key, value in configured.items()
        )
    ):
        raise RuntimeError(
            "AGENTDECOMPILE_MCP_HEADERS_JSON must contain only safe string headers."
        )
    return url, {**BASE_HEADERS, **configured}


def _post(payload: dict, session: str | None = None, timeout: float = 60.0):
    url, headers = _connection()
    if session:
        headers["Mcp-Session-Id"] = session
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )
    with OPENER.open(request, timeout=timeout) as response:
        session_id = response.headers.get("Mcp-Session-Id", session)
        encoded = response.read(MAX_RESPONSE_BYTES + 1)
    if len(encoded) > MAX_RESPONSE_BYTES:
        raise RuntimeError("AgentDecompile MCP response exceeded the local bound.")
    body = encoded.decode("utf-8", errors="replace")
    # Streamable HTTP may wrap JSON in SSE ("data: {...}").
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            body = line[5:].strip()
            break
    return (json.loads(body) if body else {}), session_id


def connect() -> str | None:
    result, session = _post(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ghost-studio", "version": "1.0"},
            },
        }
    )
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, session)
    return session


def list_tools(session: str | None):
    result, _ = _post({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, session)
    return result


def call_tool(session: str | None, name: str, arguments: dict, timeout: float = 120.0):
    result, _ = _post(
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
        session,
        timeout=timeout,
    )
    return result


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "tools"
    session = connect()
    if mode == "chain":
        # Run multiple tool calls in ONE session so active-program state
        # persists: chain 'name={json};name2={json2};...'
        spec = sys.argv[2] if len(sys.argv) > 2 else ""
        for part in spec.split(";;"):
            part = part.strip()
            if not part:
                continue
            name, _, arg = part.partition("=")
            arguments = json.loads(arg) if arg.strip() else {}
            result = call_tool(session, name.strip(), arguments)
            content = result.get("result", {}).get("content", [])
            print(f"### CALL {name.strip()}")
            for block in content:
                if block.get("type") == "text":
                    print(block.get("text", ""))
            if not content:
                print(json.dumps(result)[:1500])
        return 0
    if mode == "tools":
        result = list_tools(session)
        tools = result.get("result", {}).get("tools", [])
        for tool in tools:
            print(f"{tool['name']}: {str(tool.get('description', ''))[:120]}")
        if not tools:
            print(json.dumps(result)[:800])
        return 0
    if mode == "call":
        name = sys.argv[2]
        arguments = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        result = call_tool(session, name, arguments)
        content = result.get("result", {}).get("content", [])
        for block in content:
            if block.get("type") == "text":
                print(block.get("text", ""))
        if not content:
            print(json.dumps(result)[:2000])
        return 0
    print("unknown mode")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
