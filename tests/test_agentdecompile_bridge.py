"""Tests for AgentDecompile bridge tools and client adapter.

Tests cover:
  - AgentDecompileClient (adapter) — constructor, path resolution, session logic
  - Tool schema validation — all 11 tools have required fields
  - Tool handler logic — input validation, error returns, client delegation
  - Tool registry — all decompile tools registered and dispatchable

These tests are fully offline (no network calls). The client is replaced by
a mock that returns configurable fixture responses.
"""
from __future__ import annotations

import asyncio
import json
import sys
import os
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

# ── path setup ───────────────────────────────────────────────────────────────
_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from kotormcp.adapters_decompile import (
    AgentDecompileClient,
    KNOWN_PROGRAMS,
    get_client,
    reset_client,
)
from kotormcp.tools import decompile as decompile_module
from kotormcp.tools import get_all_tools, handle_tool


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

class MockClient:
    """Minimal mock for AgentDecompileClient used in handler tests."""

    def __init__(self, responses: Optional[Dict[str, Any]] = None):
        self.responses = responses or {}
        self.calls: list = []
        self.server_url = "http://mock-agentdecompile:8080/mcp"
        self.ghidra_host = "mock-host"
        self.ghidra_port = 13100
        self.ghidra_repo = "Odyssey"
        self.ghidra_user = "user"
        self.ghidra_pass = "pass"
        self._session_id = "mock-session"

    def ping(self) -> bool:
        return self.responses.get("_ping", True)

    def _ensure_session(self) -> None:
        pass

    def resolve_program_path(self, alias: str) -> str:
        return KNOWN_PROGRAMS.get(alias.lower(), alias)

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append((name, arguments))
        return self.responses.get(name, {"status": "ok", "name": name})

    def get_program_info(self, path: str) -> Dict[str, Any]:
        return self.responses.get("get-current-program", {"loaded": True, "name": "swkotor.exe", "functionCount": 24591})

    def list_functions(self, path: str, offset: int = 0, limit: int = 50) -> Dict[str, Any]:
        return self.responses.get("list-functions", {"functions": [], "count": 0})

    def decompile_function(self, path: str, fn: str, limit: int = 200, include_comments: bool = True) -> Dict[str, Any]:
        return self.responses.get("decompile-function", {"decompilation": "void main() {}"})

    def search_symbols(self, path: str, query: str, limit: int = 50) -> Dict[str, Any]:
        return self.responses.get("search-symbols", {"symbols": [], "count": 0, "query": query})

    def search_strings(self, path: str, pattern: str, limit: int = 50) -> Dict[str, Any]:
        return self.responses.get("search-strings", {"strings": [], "count": 0})

    def get_references(self, path: str, sym: str, direction: str = "to") -> Dict[str, Any]:
        return self.responses.get("get-references", {"references": [], "count": 0})

    def get_call_graph(self, path: str, fn: str, depth: int = 2) -> Dict[str, Any]:
        return self.responses.get("get-call-graph", {"nodes": [], "edges": []})

    def analyze_data_flow(self, path: str, fn_addr: str, direction: str = "backward", start_address=None) -> Dict[str, Any]:
        return self.responses.get("analyze-data-flow", {"flow": []})

    def inspect_memory(self, path: str, addr: str, mode: str = "layout", length: int = 64) -> Dict[str, Any]:
        return self.responses.get("inspect-memory", {"segments": []})

    def execute_script(self, path: str, script: str) -> Dict[str, Any]:
        return self.responses.get("execute-script", {"output": "script executed"})


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _parse(result) -> dict:
    """Parse the tool handler result (a dict or list-of-dicts) into a Python dict."""
    if isinstance(result, list):
        text = result[0]["text"]
    elif isinstance(result, dict):
        text = result.get("text", "{}")
    else:
        raise TypeError(f"Unexpected result type: {type(result)}")
    return json.loads(text)


def _patch_client(mock: MockClient):
    """Context manager: replace decompile_module.get_client with one returning mock."""
    return patch.object(decompile_module, "get_client", return_value=mock)


# ══════════════════════════════════════════════════════════════════════════════
# AgentDecompileClient unit tests
# ══════════════════════════════════════════════════════════════════════════════

class TestAgentDecompileClient:
    def test_server_url_normalised_to_mcp(self):
        c = AgentDecompileClient(server_url="http://host:8080")
        assert c.server_url.endswith("/mcp")

    def test_server_url_with_trailing_slash_normalised(self):
        c = AgentDecompileClient(server_url="http://host:8080/mcp/")
        assert c.server_url == "http://host:8080/mcp"

    def test_server_url_already_ending_mcp(self):
        c = AgentDecompileClient(server_url="http://host:8080/mcp")
        assert c.server_url == "http://host:8080/mcp"

    def test_resolve_k1_alias(self):
        c = AgentDecompileClient()
        assert c.resolve_program_path("k1") == "/K1/k1_win_gog_swkotor.exe"

    def test_resolve_k2_alias(self):
        c = AgentDecompileClient()
        assert c.resolve_program_path("k2") == "/K2/swkotor2.exe"

    def test_resolve_unknown_alias_passthrough(self):
        c = AgentDecompileClient()
        assert c.resolve_program_path("/Custom/binary.exe") == "/Custom/binary.exe"

    def test_base_headers_include_ghidra_host(self):
        c = AgentDecompileClient(
            ghidra_host="myhost",
            ghidra_port=13100,
            ghidra_repo="Odyssey",
            ghidra_user="user",
            ghidra_pass="pass",
        )
        headers = c._base_headers()
        assert headers["X-Ghidra-Server-Host"] == "myhost"
        assert headers["X-Ghidra-Server-Port"] == "13100"
        assert headers["X-Ghidra-Repository"] == "Odyssey"
        assert "Authorization" in headers

    def test_base_headers_auth_basic_format(self):
        import base64
        c = AgentDecompileClient(ghidra_user="user", ghidra_pass="secret")
        headers = c._base_headers()
        b64 = base64.b64encode(b"user:secret").decode()
        assert headers["Authorization"] == f"Basic {b64}"

    def test_session_id_added_to_headers_when_set(self):
        c = AgentDecompileClient()
        c._session_id = "abc123"
        headers = c._base_headers()
        assert headers["Mcp-Session-Id"] == "abc123"

    def test_session_id_absent_before_init(self):
        c = AgentDecompileClient()
        headers = c._base_headers()
        assert "Mcp-Session-Id" not in headers

    def test_known_programs_has_k1_and_k2(self):
        assert "k1" in KNOWN_PROGRAMS
        assert "k2" in KNOWN_PROGRAMS

    def test_get_client_returns_singleton(self):
        reset_client()
        c1 = get_client()
        c2 = get_client()
        assert c1 is c2

    def test_reset_client_forces_new_instance(self):
        reset_client()
        c1 = get_client()
        reset_client()
        c2 = get_client()
        assert c1 is not c2


# ══════════════════════════════════════════════════════════════════════════════
# Tool schema tests
# ══════════════════════════════════════════════════════════════════════════════

class TestDecompileToolSchemas:
    def test_all_tools_have_name(self):
        for tool in decompile_module.get_tools():
            assert "name" in tool, f"Tool missing 'name': {tool}"

    def test_all_tools_have_description(self):
        for tool in decompile_module.get_tools():
            assert "description" in tool
            assert len(tool["description"]) > 20, f"Description too short for {tool['name']}"

    def test_all_tools_have_input_schema(self):
        for tool in decompile_module.get_tools():
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    def test_tool_count_is_eleven(self):
        assert len(decompile_module.get_tools()) == 11

    def test_tool_names_are_unique(self):
        names = [t["name"] for t in decompile_module.get_tools()]
        assert len(names) == len(set(names))

    def test_ping_has_no_required_fields(self):
        ping = next(t for t in decompile_module.get_tools() if t["name"] == "kotor_binary_ping")
        assert "required" not in ping["inputSchema"] or ping["inputSchema"].get("required") == []

    def test_decompile_function_requires_game_and_function(self):
        tool = next(t for t in decompile_module.get_tools() if t["name"] == "kotor_decompile_function")
        assert "game" in tool["inputSchema"]["required"]
        assert "function" in tool["inputSchema"]["required"]

    def test_search_symbols_requires_game_and_query(self):
        tool = next(t for t in decompile_module.get_tools() if t["name"] == "kotor_search_symbols")
        assert "query" in tool["inputSchema"]["required"]

    def test_direction_enum_in_get_references(self):
        tool = next(t for t in decompile_module.get_tools() if t["name"] == "kotor_get_references")
        direction_prop = tool["inputSchema"]["properties"]["direction"]
        assert "to" in direction_prop["enum"]
        assert "from" in direction_prop["enum"]


# ══════════════════════════════════════════════════════════════════════════════
# Tool handler tests
# ══════════════════════════════════════════════════════════════════════════════

class TestHandlePing:
    def test_ping_ok_when_reachable(self):
        mock = MockClient({"_ping": True})
        with _patch_client(mock):
            result = _run(decompile_module.handle_ping({}))
        data = _parse(result)
        assert data["status"] == "ok"

    def test_ping_unreachable_returns_error(self):
        mock = MockClient({"_ping": False})
        with _patch_client(mock):
            result = _run(decompile_module.handle_ping({}))
        data = _parse(result)
        assert data["status"] == "unreachable"
        assert "error" in data

    def test_ping_response_includes_server_url(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(decompile_module.handle_ping({}))
        data = _parse(result)
        assert "server_url" in data

    def test_ping_response_includes_known_programs(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(decompile_module.handle_ping({}))
        data = _parse(result)
        assert "known_programs" in data
        assert "k1" in data["known_programs"]


class TestHandleBinaryInfo:
    def test_returns_program_info_for_k1(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(decompile_module.handle_binary_info({"game": "k1"}))
        data = _parse(result)
        assert data["game"] == "k1"
        assert "program_path" in data

    def test_program_path_resolved_from_alias(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(decompile_module.handle_binary_info({"game": "k2"}))
        data = _parse(result)
        assert data["program_path"] == "/K2/swkotor2.exe"

    def test_error_propagated_from_client(self):
        mock = MockClient()
        mock.get_program_info = lambda path: {"error": "not loaded"}
        with _patch_client(mock):
            result = _run(decompile_module.handle_binary_info({"game": "k1"}))
        data = _parse(result)
        assert "error" in data


class TestHandleDecompileFunction:
    def test_requires_function_argument(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(decompile_module.handle_decompile_function({"game": "k1"}))
        data = _parse(result)
        assert "error" in data

    def test_returns_decompilation(self):
        mock = MockClient({"decompile-function": {"decompilation": "void MDLLoad() {}"}})
        mock.decompile_function = lambda p, f, **kw: {"decompilation": "void MDLLoad() {}"}
        with _patch_client(mock):
            result = _run(decompile_module.handle_decompile_function(
                {"game": "k1", "function": "MDLLoad"}
            ))
        data = _parse(result)
        assert "decompilation" in data

    def test_response_includes_function_name(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(decompile_module.handle_decompile_function(
                {"game": "k1", "function": "WinMain"}
            ))
        data = _parse(result)
        assert data["function"] == "WinMain"


class TestHandleSearchSymbols:
    def test_requires_query(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(decompile_module.handle_search_symbols({"game": "k1"}))
        data = _parse(result)
        assert "error" in data

    def test_returns_query_in_response(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(decompile_module.handle_search_symbols(
                {"game": "k1", "query": "MDL"}
            ))
        data = _parse(result)
        assert data["query"] == "MDL"


class TestHandleGetReferences:
    def test_requires_address_or_symbol(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(decompile_module.handle_get_references({"game": "k1"}))
        data = _parse(result)
        assert "error" in data

    def test_default_direction_is_to(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(decompile_module.handle_get_references(
                {"game": "k1", "address_or_symbol": "WinMain"}
            ))
        data = _parse(result)
        assert data["direction"] == "to"

    def test_explicit_from_direction(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(decompile_module.handle_get_references(
                {"game": "k1", "address_or_symbol": "WinMain", "direction": "from"}
            ))
        data = _parse(result)
        assert data["direction"] == "from"


class TestHandleDataFlow:
    def test_requires_function_address(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(decompile_module.handle_data_flow({"game": "k1"}))
        data = _parse(result)
        assert "error" in data

    def test_default_direction_is_backward(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(decompile_module.handle_data_flow(
                {"game": "k1", "function_address": "0x401000"}
            ))
        data = _parse(result)
        assert data["direction"] == "backward"


class TestHandleEngineScript:
    def test_requires_script(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(decompile_module.handle_engine_script({"game": "k1"}))
        data = _parse(result)
        assert "error" in data

    def test_returns_script_output(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(decompile_module.handle_engine_script(
                {"game": "k1", "script": "print('hello')"}
            ))
        data = _parse(result)
        assert "output" in data or "error" not in data


# ══════════════════════════════════════════════════════════════════════════════
# Tool registry integration tests
# ══════════════════════════════════════════════════════════════════════════════

class TestDecompileToolRegistry:
    def test_all_decompile_tools_in_registry(self):
        all_names = {t["name"] for t in get_all_tools()}
        decompile_names = {t["name"] for t in decompile_module.get_tools()}
        assert decompile_names.issubset(all_names)

    def test_total_tool_count_is_43(self):
        assert len(get_all_tools()) == 43

    def test_dispatch_ping(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(handle_tool("kotor_binary_ping", {}))
        assert isinstance(result, (list, dict))

    def test_dispatch_binary_info(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(handle_tool("kotor_binary_info", {"game": "k1"}))
        assert isinstance(result, (list, dict))

    def test_dispatch_search_symbols(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(handle_tool("kotor_search_symbols", {"game": "k1", "query": "MDL"}))
        assert isinstance(result, (list, dict))

    def test_dispatch_decompile_function(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(handle_tool("kotor_decompile_function", {"game": "k1", "function": "WinMain"}))
        assert isinstance(result, (list, dict))

    def test_dispatch_get_references(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(handle_tool("kotor_get_references", {"game": "k1", "address_or_symbol": "main"}))
        assert isinstance(result, (list, dict))

    def test_dispatch_call_graph(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(handle_tool("kotor_call_graph", {"game": "k1", "function": "main"}))
        assert isinstance(result, (list, dict))

    def test_dispatch_data_flow(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(handle_tool("kotor_data_flow", {"game": "k1", "function_address": "0x401000"}))
        assert isinstance(result, (list, dict))

    def test_dispatch_inspect_memory(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(handle_tool("kotor_inspect_memory", {"game": "k1", "address": "0x401000"}))
        assert isinstance(result, (list, dict))

    def test_dispatch_engine_script(self):
        mock = MockClient()
        with _patch_client(mock):
            result = _run(handle_tool("kotor_engine_script", {"game": "k1", "script": "print(1)"}))
        assert isinstance(result, (list, dict))

    def test_unknown_tool_raises(self):
        with pytest.raises(ValueError, match="Unknown tool"):
            _run(handle_tool("kotor_nonexistent_tool", {}))
