"""AgentDecompile bridge tools — KotorMCP ↔ Ghidra/AgentDecompile integration.

Architecture note (Khononov, "Balancing Coupling in Software Design"):
  Handlers here depend only on AgentDecompileClient (Contract Coupling).
  All HTTP transport knowledge lives in adapters_decompile.py.
  No tool handler imports from another tool module.

What these tools give a KotOR modder:
  The KotOR Odyssey Engine binaries (swkotor.exe, swkotor2.exe) have been
  fully analysed by Ghidra on a shared server.  These tools let you ask
  plain-English questions about the game engine itself — decompile any
  function, trace data flow, search for strings, understand save-game
  formats, find where the MDL loader lives, etc. — all without needing
  a local Ghidra installation.

Tool groups exposed here (11 tools):
  kotor_binary_ping          — health-check the AgentDecompile backend
  kotor_binary_info          — metadata for a KotOR binary (language, functions)
  kotor_list_engine_funcs    — list functions in swkotor.exe / swkotor2.exe
  kotor_decompile_function   — decompile a named or addressed engine function to C
  kotor_search_symbols       — search symbol names in the KotOR binary
  kotor_search_engine_strings— search string literals baked into the binary
  kotor_get_references       — find all callers/callees of an engine function
  kotor_call_graph           — visualise the call graph around a function
  kotor_data_flow            — trace data flow backward/forward from an address
  kotor_inspect_memory       — view memory layout at a given address
  kotor_engine_script        — run arbitrary PyGhidra/Python against the binary
"""
from __future__ import annotations

from typing import Any, Dict, List

from kotormcp.adapters_decompile import get_client, KNOWN_PROGRAMS, reset_client
from kotormcp.utils import json_content


# ── Tool schema definitions ──────────────────────────────────────────────────

def get_tools() -> List[Dict[str, Any]]:
    """Return MCP tool definitions for all AgentDecompile bridge tools."""
    _prog_desc = (
        "KotOR binary to target. Use 'k1' for swkotor.exe or 'k2' for swkotor2.exe. "
        "Also accepts a full Ghidra project path like '/K1/k1_win_gog_swkotor.exe'."
    )
    return [
        {
            "name": "kotor_binary_ping",
            "description": (
                "Check whether the AgentDecompile / Ghidra backend is reachable. "
                "Returns server version and health status. Call this first to verify "
                "connectivity before using the other kotor_binary_* tools."
            ),
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "kotor_binary_info",
            "description": (
                "Get metadata for a KotOR engine binary from Ghidra: language, "
                "compiler, total function count, and the full Ghidra project path. "
                "Useful to confirm the binary is loaded before deeper analysis."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "description": _prog_desc},
                },
                "required": ["game"],
            },
        },
        {
            "name": "kotor_list_engine_funcs",
            "description": (
                "List functions defined in swkotor.exe or swkotor2.exe. "
                "Returns function name, entry address, and size. "
                "Supports pagination via offset/limit for the 24 000+ function table."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "description": _prog_desc},
                    "offset": {"type": "integer", "description": "Start index (default 0)."},
                    "limit": {"type": "integer", "description": "Max results (default 50)."},
                },
                "required": ["game"],
            },
        },
        {
            "name": "kotor_decompile_function",
            "description": (
                "Decompile a KotOR engine function to C-like pseudocode using Ghidra's "
                "decompiler.  Pass a function name (e.g. 'CResMan::LoadResource') or "
                "hex address (e.g. '0x00541230').  "
                "Returns the full decompiled C source. "
                "Invaluable for understanding the MDL loader, script VM, save-game "
                "serialisation, AI routines, and other engine internals."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "description": _prog_desc},
                    "function": {
                        "type": "string",
                        "description": "Function name or hex address to decompile.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max lines of C output (default 200).",
                    },
                    "include_comments": {
                        "type": "boolean",
                        "description": "Include Ghidra inline comments (default true).",
                    },
                },
                "required": ["game", "function"],
            },
        },
        {
            "name": "kotor_search_symbols",
            "description": (
                "Search symbol names inside a KotOR binary. "
                "Finds functions, globals, and labels matching the query substring. "
                "Example: search 'MDL' to find all MDL-related engine functions; "
                "search 'ResMan' to map the resource manager class."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "description": _prog_desc},
                    "query": {"type": "string", "description": "Substring to search for in symbol names."},
                    "limit": {"type": "integer", "description": "Max results (default 50)."},
                },
                "required": ["game", "query"],
            },
        },
        {
            "name": "kotor_search_engine_strings",
            "description": (
                "Search string literals embedded in the KotOR binary. "
                "Finds hardcoded file paths, format strings, error messages, "
                "resource type names, and debug output. "
                "Useful for discovering how the engine references MDL/MDX, "
                "TPC textures, GFF files, 2DA tables, and NWScript."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "description": _prog_desc},
                    "pattern": {
                        "type": "string",
                        "description": "Text pattern to search for in string literals.",
                    },
                    "limit": {"type": "integer", "description": "Max results (default 50)."},
                },
                "required": ["game", "pattern"],
            },
        },
        {
            "name": "kotor_get_references",
            "description": (
                "Find all call sites (callers) or call targets (callees) of a KotOR "
                "engine function or address. "
                "direction='to'  → who calls this function "
                "direction='from' → what does this function call "
                "Essential for tracing execution paths through the engine."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "description": _prog_desc},
                    "address_or_symbol": {
                        "type": "string",
                        "description": "Function name or hex address.",
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["to", "from"],
                        "description": "'to' = find callers; 'from' = find callees.",
                    },
                },
                "required": ["game", "address_or_symbol"],
            },
        },
        {
            "name": "kotor_call_graph",
            "description": (
                "Generate a call graph around a KotOR engine function showing "
                "callers and callees up to a configurable depth. "
                "Returns a structured graph suitable for visualisation or analysis. "
                "Useful for mapping subsystems like the resource manager, "
                "MDL renderer, script engine, or combat system."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "description": _prog_desc},
                    "function": {
                        "type": "string",
                        "description": "Function name or hex address.",
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Call graph traversal depth (default 2).",
                    },
                },
                "required": ["game", "function"],
            },
        },
        {
            "name": "kotor_data_flow",
            "description": (
                "Trace data flow backward or forward from an instruction address "
                "inside a KotOR engine function using Ghidra P-code analysis. "
                "Backward tracing reveals where a value came from; "
                "forward tracing reveals where it is used. "
                "Useful for understanding parameter passing to MDL/resource "
                "loaders and save-game serialisation paths."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "description": _prog_desc},
                    "function_address": {
                        "type": "string",
                        "description": "Hex address of the containing function.",
                    },
                    "start_address": {
                        "type": "string",
                        "description": "Hex address of the instruction to trace from (optional).",
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["backward", "forward", "variable_accesses"],
                        "description": "Analysis direction (default 'backward').",
                    },
                },
                "required": ["game", "function_address"],
            },
        },
        {
            "name": "kotor_inspect_memory",
            "description": (
                "Inspect the memory layout of the KotOR binary at a given address. "
                "Modes: 'layout' = segment overview, 'read' = raw bytes, "
                "'defined' = typed data. "
                "Useful for inspecting static tables, vtables, and hardcoded "
                "resource type arrays."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "description": _prog_desc},
                    "address": {
                        "type": "string",
                        "description": "Hex address to inspect.",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["layout", "read", "defined"],
                        "description": "Inspection mode (default 'layout').",
                    },
                    "length": {
                        "type": "integer",
                        "description": "Bytes to read in 'read' mode (default 64).",
                    },
                },
                "required": ["game", "address"],
            },
        },
        {
            "name": "kotor_engine_script",
            "description": (
                "Execute an arbitrary Python/PyGhidra script against the loaded KotOR "
                "binary inside the Ghidra runtime. "
                "POWERFUL: can rename functions, apply data types, export analysis "
                "results, bulk-annotate the binary, run custom analysis passes, etc. "
                "Script runs as a trusted Ghidra headless script with full API access."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "description": _prog_desc},
                    "script": {
                        "type": "string",
                        "description": "Python source code to execute in the Ghidra environment.",
                    },
                },
                "required": ["game", "script"],
            },
        },
    ]


# ── Tool handlers ────────────────────────────────────────────────────────────

async def handle_ping(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Health-check the AgentDecompile backend."""
    client = get_client()
    reachable = client.ping()
    if not reachable:
        return json_content({
            "status": "unreachable",
            "server_url": client.server_url,
            "error": (
                "AgentDecompile MCP server not reachable. "
                "Set AGENTDECOMPILE_MCP_SERVER_URL or ensure the server is running."
            ),
        })
    # Do a quick tools/list probe to confirm MCP is responding
    client._ensure_session()
    return json_content({
        "status": "ok",
        "server_url": client.server_url,
        "ghidra_host": client.ghidra_host,
        "ghidra_port": client.ghidra_port,
        "ghidra_repo": client.ghidra_repo,
        "known_programs": KNOWN_PROGRAMS,
        "message": "AgentDecompile backend is reachable. Use kotor_binary_info to load a program.",
    })


async def handle_binary_info(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Return metadata for a KotOR binary."""
    game = arguments.get("game", "k1")
    client = get_client()
    program_path = client.resolve_program_path(game)
    result = client.get_program_info(program_path)
    if "error" in result:
        return json_content(result)
    return json_content({
        "game": game,
        "program_path": program_path,
        **result,
    })


async def handle_list_engine_funcs(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """List functions in a KotOR binary."""
    game = arguments.get("game", "k1")
    offset = int(arguments.get("offset", 0))
    limit = int(arguments.get("limit", 50))
    client = get_client()
    program_path = client.resolve_program_path(game)
    result = client.list_functions(program_path, offset=offset, limit=limit)
    if "error" in result:
        return json_content(result)
    return json_content({
        "game": game,
        "program_path": program_path,
        "offset": offset,
        "limit": limit,
        **result,
    })


async def handle_decompile_function(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Decompile a KotOR engine function to C pseudocode."""
    game = arguments.get("game", "k1")
    function = arguments.get("function", "")
    if not function:
        return json_content({"error": "Provide 'function' (name or hex address)."})
    limit = int(arguments.get("limit", 200))
    include_comments = bool(arguments.get("include_comments", True))
    client = get_client()
    program_path = client.resolve_program_path(game)
    result = client.decompile_function(
        program_path, function, limit=limit, include_comments=include_comments
    )
    if "error" in result:
        return json_content(result)
    return json_content({
        "game": game,
        "program_path": program_path,
        "function": function,
        **result,
    })


async def handle_search_symbols(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Search symbol names in a KotOR binary."""
    game = arguments.get("game", "k1")
    query = arguments.get("query", "")
    if not query:
        return json_content({"error": "Provide 'query' string."})
    limit = int(arguments.get("limit", 50))
    client = get_client()
    program_path = client.resolve_program_path(game)
    result = client.search_symbols(program_path, query, limit=limit)
    if "error" in result:
        return json_content(result)
    return json_content({
        "game": game,
        "program_path": program_path,
        "query": query,
        **result,
    })


async def handle_search_engine_strings(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Search string literals in a KotOR binary."""
    game = arguments.get("game", "k1")
    pattern = arguments.get("pattern", "")
    if not pattern:
        return json_content({"error": "Provide 'pattern' string."})
    limit = int(arguments.get("limit", 50))
    client = get_client()
    program_path = client.resolve_program_path(game)
    result = client.search_strings(program_path, pattern, limit=limit)
    if "error" in result:
        return json_content(result)
    return json_content({
        "game": game,
        "program_path": program_path,
        "pattern": pattern,
        **result,
    })


async def handle_get_references(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Find callers/callees of an engine function."""
    game = arguments.get("game", "k1")
    address_or_symbol = arguments.get("address_or_symbol", "")
    if not address_or_symbol:
        return json_content({"error": "Provide 'address_or_symbol'."})
    direction = arguments.get("direction", "to")
    client = get_client()
    program_path = client.resolve_program_path(game)
    result = client.get_references(program_path, address_or_symbol, direction=direction)
    if "error" in result:
        return json_content(result)
    return json_content({
        "game": game,
        "program_path": program_path,
        "target": address_or_symbol,
        "direction": direction,
        **result,
    })


async def handle_call_graph(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Return the call graph around an engine function."""
    game = arguments.get("game", "k1")
    function = arguments.get("function", "")
    if not function:
        return json_content({"error": "Provide 'function'."})
    depth = int(arguments.get("depth", 2))
    client = get_client()
    program_path = client.resolve_program_path(game)
    result = client.get_call_graph(program_path, function, depth=depth)
    if "error" in result:
        return json_content(result)
    return json_content({
        "game": game,
        "program_path": program_path,
        "function": function,
        "depth": depth,
        **result,
    })


async def handle_data_flow(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Trace data flow from an address inside an engine function."""
    game = arguments.get("game", "k1")
    function_address = arguments.get("function_address", "")
    if not function_address:
        return json_content({"error": "Provide 'function_address'."})
    direction = arguments.get("direction", "backward")
    start_address = arguments.get("start_address")
    client = get_client()
    program_path = client.resolve_program_path(game)
    result = client.analyze_data_flow(
        program_path, function_address, direction=direction, start_address=start_address
    )
    if "error" in result:
        return json_content(result)
    return json_content({
        "game": game,
        "program_path": program_path,
        "function_address": function_address,
        "direction": direction,
        **result,
    })


async def handle_inspect_memory(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Inspect memory at an address in a KotOR binary."""
    game = arguments.get("game", "k1")
    address = arguments.get("address", "")
    if not address:
        return json_content({"error": "Provide 'address'."})
    mode = arguments.get("mode", "layout")
    length = int(arguments.get("length", 64))
    client = get_client()
    program_path = client.resolve_program_path(game)
    result = client.inspect_memory(program_path, address, mode=mode, length=length)
    if "error" in result:
        return json_content(result)
    return json_content({
        "game": game,
        "program_path": program_path,
        "address": address,
        "mode": mode,
        **result,
    })


async def handle_engine_script(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a PyGhidra script against the KotOR binary."""
    game = arguments.get("game", "k1")
    script = arguments.get("script", "")
    if not script:
        return json_content({"error": "Provide 'script' (Python source code)."})
    client = get_client()
    program_path = client.resolve_program_path(game)
    result = client.execute_script(program_path, script)
    if "error" in result:
        return json_content(result)
    return json_content({
        "game": game,
        "program_path": program_path,
        **result,
    })
