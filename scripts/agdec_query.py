"""Query the OpenKotOR AgentDecompile Ghidra MCP server (Odyssey engine).

Usage:
  py -3.14 scripts/agdec_query.py tools
  py -3.14 scripts/agdec_query.py call <tool_name> '<json_args>'

Raw MCP-over-HTTP JSON-RPC; used to validate Map Studio output against the
real engine (K1/K2 GFF field semantics, script events, module loading).
"""
from __future__ import annotations

import json
import sys
import urllib.request

URL = "http://170.9.241.140:8080/mcp/"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "User-Agent": "PyKotorAgent/1.0",
    "X-Agent-Version": "1.0",
    "X-Agent-Server-Username": "OpenKotOR",
    "X-Agent-Server-Password": "revanlives",
    "X-Ghidra-Repository": "Odyssey",
    "X-Agent-Server-Repository": "Odyssey",
    "X-Ghidra-Server-Host": "170.9.241.140",
    "X-Ghidra-Server-Port": "13100",
}


def _post(payload: dict, session: str | None = None, timeout: float = 60.0):
    headers = dict(HEADERS)
    if session:
        headers["Mcp-Session-Id"] = session
    request = urllib.request.Request(URL, data=json.dumps(payload).encode("utf-8"), headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        session_id = response.headers.get("Mcp-Session-Id", session)
        body = response.read().decode("utf-8", errors="replace")
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
