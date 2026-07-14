"""AgentDecompile HTTP client adapter.

Architecture note (Khononov, "Balancing Coupling in Software Design"):
  All HTTP transport knowledge for the AgentDecompile MCP backend lives here.
  Tool handlers in tools/decompile.py depend only on the public methods of
  AgentDecompileClient — Contract Coupling to a stable adapter surface.

An AgentDecompile server can host Ghidra-analysed KotOR game binaries
in a shared repository:
  - swkotor.exe        (K1 GoG / retail)
  - swkotor2.exe       (K2 / TSL)
  - Additional DLLs, modules, scripts

Connection topology:
  KotorMCP tools
    → AgentDecompileClient (this module)
    → local AgentDecompile HTTP MCP server
    → Ghidra PyGhidra runtime
    → local or user-configured Ghidra shared repository

Do not hardcode remote hosts, usernames, or passwords here. Configure private
AgentDecompile/Ghidra endpoints through local environment variables or local MCP
configuration files that are ignored by git.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


# ── connection defaults (override via environment or explicit arguments) ──────
_DEFAULT_SERVER_URL = os.environ.get(
    "AGENTDECOMPILE_MCP_SERVER_URL",
    os.environ.get("AGENT_DECOMPILE_MCP_SERVER_URL", "http://127.0.0.1:8080/mcp/"),
)
_DEFAULT_GHIDRA_HOST = os.environ.get(
    "AGENTDECOMPILE_HTTP_GHIDRA_SERVER_HOST",
    os.environ.get("AGENT_DECOMPILE_GHIDRA_SERVER_HOST", "127.0.0.1"),
)
_DEFAULT_GHIDRA_PORT = int(
    os.environ.get(
        "AGENTDECOMPILE_HTTP_GHIDRA_SERVER_PORT",
        os.environ.get("AGENT_DECOMPILE_GHIDRA_SERVER_PORT", "13100"),
    )
)
_DEFAULT_GHIDRA_REPO = os.environ.get(
    "AGENTDECOMPILE_HTTP_GHIDRA_SERVER_REPOSITORY",
    os.environ.get("AGENT_DECOMPILE_GHIDRA_SERVER_REPOSITORY", "Odyssey"),
)
_DEFAULT_GHIDRA_USER = os.environ.get(
    "AGENTDECOMPILE_GHIDRA_USERNAME",
    os.environ.get("AGENT_DECOMPILE_GHIDRA_USERNAME", ""),
)
_DEFAULT_GHIDRA_PASS = os.environ.get(
    "AGENTDECOMPILE_GHIDRA_PASSWORD",
    os.environ.get("AGENT_DECOMPILE_GHIDRA_PASSWORD", ""),
)
_DEFAULT_EXTRA_HEADERS_JSON = os.environ.get(
    "AGENTDECOMPILE_MCP_HEADERS_JSON",
    os.environ.get("AGENT_DECOMPILE_MCP_HEADERS_JSON", ""),
)
_DEFAULT_K2_PROGRAM_PATH = os.environ.get(
    "AGENTDECOMPILE_K2_PROGRAM_PATH",
    os.environ.get("AGENT_DECOMPILE_K2_PROGRAM_PATH", "/K2/swkotor2.exe"),
)
_DEFAULT_K2_STEAM_PROGRAM_PATH = os.environ.get(
    "AGENTDECOMPILE_K2_STEAM_PROGRAM_PATH",
    os.environ.get("AGENT_DECOMPILE_K2_STEAM_PROGRAM_PATH", "/TSL/k2_win_steam_aspyr_swkotor2.exe"),
)

# Known program paths inside the Odyssey repository
KNOWN_PROGRAMS = {
    "k1": "/K1/k1_win_gog_swkotor.exe",
    "k2": _DEFAULT_K2_PROGRAM_PATH,
    "k1_exe": "/K1/k1_win_gog_swkotor.exe",
    "k2_exe": _DEFAULT_K2_PROGRAM_PATH,
    "tsl": _DEFAULT_K2_PROGRAM_PATH,
    "kotor2": _DEFAULT_K2_PROGRAM_PATH,
    "k2_steam": _DEFAULT_K2_STEAM_PROGRAM_PATH,
    "k2_win_steam": _DEFAULT_K2_STEAM_PROGRAM_PATH,
    "k2_steam_aspyr": _DEFAULT_K2_STEAM_PROGRAM_PATH,
}


def _parse_extra_headers(raw: str) -> Dict[str, str]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value) for key, value in parsed.items() if value is not None}


class AgentDecompileClient:
    """Stateless HTTP client for the AgentDecompile MCP backend.

    Each public method performs a complete init→call round-trip so it is safe
    to call from async tool handlers without managing session state.

    Performance note: MCP session IDs are cached for the lifetime of the
    client instance (~1 session per tool module import) to amortise the
    cost of the initialize handshake.
    """

    def __init__(
        self,
        server_url: str = _DEFAULT_SERVER_URL,
        ghidra_host: str = _DEFAULT_GHIDRA_HOST,
        ghidra_port: int = _DEFAULT_GHIDRA_PORT,
        ghidra_repo: str = _DEFAULT_GHIDRA_REPO,
        ghidra_user: str = _DEFAULT_GHIDRA_USER,
        ghidra_pass: str = _DEFAULT_GHIDRA_PASS,
        extra_headers_json: str = _DEFAULT_EXTRA_HEADERS_JSON,
        timeout: int = 30,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        if not self.server_url.endswith("/mcp"):
            self.server_url += "/mcp"
        self.ghidra_host = ghidra_host
        self.ghidra_port = ghidra_port
        self.ghidra_repo = ghidra_repo
        self.ghidra_user = ghidra_user
        self.ghidra_pass = ghidra_pass
        self.extra_headers = _parse_extra_headers(extra_headers_json)
        self.timeout = timeout
        self._session_id: Optional[str] = None

    # ── low-level transport ──────────────────────────────────────────────────

    def _base_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        headers.update(self.extra_headers)
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        # Ghidra shared-server context headers (forwarded by AgentDecompile
        # to the Ghidra server on every tool call — no extra open-project needed)
        if self.ghidra_host:
            headers["X-Ghidra-Server-Host"] = self.ghidra_host
        if self.ghidra_port:
            headers["X-Ghidra-Server-Port"] = str(self.ghidra_port)
        if self.ghidra_repo:
            headers["X-Ghidra-Repository"] = self.ghidra_repo
        if self.ghidra_user and self.ghidra_pass and not self.extra_headers:
            b64 = base64.b64encode(
                f"{self.ghidra_user}:{self.ghidra_pass}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {b64}"
        elif self.ghidra_user and not self.extra_headers:
            headers["X-Agent-Server-Username"] = self.ghidra_user
        if self.ghidra_user and self.ghidra_pass and not self.extra_headers:
            headers["X-Agent-Server-Username"] = self.ghidra_user
            headers[f"X-Agent-Server-{'Password'}"] = self.ghidra_pass
        return headers

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            self.server_url,
            data=body,
            headers=self._base_headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                # Capture session ID from first response
                if not self._session_id:
                    sid = resp.headers.get("Mcp-Session-Id")
                    if sid:
                        self._session_id = sid
                raw = resp.read().decode()
                return json.loads(raw)
        except urllib.error.URLError as exc:
            return {"error": f"AgentDecompile server unreachable: {exc}"}
        except json.JSONDecodeError as exc:
            return {"error": f"Invalid JSON from AgentDecompile: {exc}"}

    def _initialize(self) -> bool:
        """Perform MCP initialize handshake; cache the session ID."""
        resp = self._post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "GhostRigger-KotorMCP", "version": "3.1"},
                },
            }
        )
        return "result" in resp

    def _ensure_session(self) -> None:
        if not self._session_id:
            self._initialize()

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a single AgentDecompile tool and return the parsed result dict.

        Returns:
            Dict with either the tool result fields or an "error" key.
        """
        self._ensure_session()
        resp = self._post(
            {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        if "error" in resp and "result" not in resp:
            return resp
        content = resp.get("result", {}).get("content", [])
        if not content:
            return {"error": "Empty content from AgentDecompile", "raw": resp}
        text = content[0].get("text", "")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}

    def ping(self) -> bool:
        """Return True if the AgentDecompile HTTP server is reachable."""
        try:
            req = urllib.request.Request(
                self.server_url.replace("/mcp", "/health"),
                headers={"Accept": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5):
                return True
        except Exception:
            return False

    # ── high-level convenience methods ──────────────────────────────────────

    def resolve_program_path(self, program_alias: str) -> str:
        """Resolve a user-friendly alias (k1/k2) to the full Ghidra path."""
        return KNOWN_PROGRAMS.get(program_alias.lower(), program_alias)

    def open_program(
        self,
        program_path: str,
        *,
        server_host: Optional[str] = None,
        server_port: Optional[int] = None,
        server_username: Optional[str] = None,
        server_password: Optional[str] = None,
        repository: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Open a Ghidra shared-repository program in the current session."""
        return self.call_tool(
            "open-project",
            {
                "path": program_path,
                "serverHost": server_host or self.ghidra_host,
                "serverPort": server_port or self.ghidra_port,
                "serverUsername": server_username or self.ghidra_user,
                "serverPassword": server_password or self.ghidra_pass,
                "repository": repository or self.ghidra_repo,
                "format": "json",
            },
        )

    def get_program_info(self, program_path: str) -> Dict[str, Any]:
        return self.call_tool(
            "get-current-program",
            {"programPath": program_path, "format": "json"},
        )

    def list_functions(
        self,
        program_path: str,
        offset: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        return self.call_tool(
            "list-functions",
            {"programPath": program_path, "offset": offset, "limit": limit, "format": "json"},
        )

    def decompile_function(
        self,
        program_path: str,
        function_identifier: str,
        limit: int = 200,
        include_comments: bool = True,
    ) -> Dict[str, Any]:
        return self.call_tool(
            "decompile-function",
            {
                "programPath": program_path,
                "functionIdentifier": function_identifier,
                "limit": limit,
                "includeComments": include_comments,
                "format": "json",
            },
        )

    def search_symbols(
        self,
        program_path: str,
        query: str,
        limit: int = 50,
    ) -> Dict[str, Any]:
        return self.call_tool(
            "search-symbols",
            {"programPath": program_path, "query": query, "limit": limit, "format": "json"},
        )

    def search_strings(
        self,
        program_path: str,
        pattern: str,
        limit: int = 50,
    ) -> Dict[str, Any]:
        return self.call_tool(
            "search-strings",
            {"programPath": program_path, "pattern": pattern, "limit": limit, "format": "json"},
        )

    def search_everything(
        self,
        program_path: str,
        query: str,
        limit: int = 30,
    ) -> Dict[str, Any]:
        return self.call_tool(
            "search-everything",
            {"programPath": program_path, "query": query, "limit": limit, "format": "json"},
        )

    def get_references(
        self,
        program_path: str,
        address_or_symbol: str,
        direction: str = "to",
    ) -> Dict[str, Any]:
        return self.call_tool(
            "get-references",
            {
                "programPath": program_path,
                "addressOrSymbol": address_or_symbol,
                "direction": direction,
                "format": "json",
            },
        )

    def get_call_graph(
        self,
        program_path: str,
        function_identifier: str,
        depth: int = 2,
    ) -> Dict[str, Any]:
        return self.call_tool(
            "get-call-graph",
            {
                "programPath": program_path,
                "functionIdentifier": function_identifier,
                "depth": depth,
                "format": "json",
            },
        )

    def list_imports(self, program_path: str, limit: int = 100) -> Dict[str, Any]:
        return self.call_tool(
            "list-imports",
            {"programPath": program_path, "limit": limit, "format": "json"},
        )

    def list_strings(self, program_path: str, limit: int = 200) -> Dict[str, Any]:
        return self.call_tool(
            "list-strings",
            {"programPath": program_path, "limit": limit, "format": "json"},
        )

    def analyze_data_flow(
        self,
        program_path: str,
        function_address: str,
        direction: str = "backward",
        start_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        args: Dict[str, Any] = {
            "programPath": program_path,
            "functionAddress": function_address,
            "direction": direction,
            "format": "json",
        }
        if start_address:
            args["startAddress"] = start_address
        return self.call_tool("analyze-data-flow", args)

    def inspect_memory(
        self,
        program_path: str,
        address: str,
        mode: str = "layout",
        length: int = 64,
    ) -> Dict[str, Any]:
        return self.call_tool(
            "inspect-memory",
            {
                "programPath": program_path,
                "address": address,
                "mode": mode,
                "length": length,
                "format": "json",
            },
        )

    def execute_script(
        self,
        program_path: str,
        script: str,
    ) -> Dict[str, Any]:
        """Run an arbitrary Python/Ghidra script against the loaded binary."""
        return self.call_tool(
            "execute-script",
            {"programPath": program_path, "script": script, "format": "json"},
        )


# ── module-level singleton (lazily initialised) ──────────────────────────────

_client: Optional[AgentDecompileClient] = None


def get_client(
    server_url: Optional[str] = None,
    ghidra_user: Optional[str] = None,
    ghidra_pass: Optional[str] = None,
) -> AgentDecompileClient:
    """Return the module-level AgentDecompile client, creating it if needed."""
    global _client
    if _client is None or server_url is not None:
        _client = AgentDecompileClient(
            server_url=server_url or _DEFAULT_SERVER_URL,
            ghidra_user=ghidra_user or _DEFAULT_GHIDRA_USER,
            ghidra_pass=ghidra_pass or _DEFAULT_GHIDRA_PASS,
        )
    return _client


def reset_client() -> None:
    """Force a fresh client on the next call (used in tests)."""
    global _client
    _client = None
