"""Tool registry: collect tool definitions and dispatch handle_tool by name.

Architecture note (Khononov, "Balancing Coupling in Software Design"):
  This module is the single integration point between the MCP server and all
  tool sub-modules.  Its only coupling to each tool module is the module's
  public API — get_tools() and handle_*() functions — which constitutes
  Contract Coupling (the lowest acceptable strength for components at this
  distance).

  Tool modules should never import from each other; all shared state flows
  through the service container (adapters.py / state.py), not through this
  registry.

Architecture note (Constantine, "Structured Design"):
  New composite tools (get_resource, get_quest) follow Transform Analysis:
  each is a single-purpose transform with data-coupling only.  Tool names
  are context-free — the same tool works in a Discord bot, VS Code extension,
  CI pipeline, or any other consumer without modification.

Tool manifest (v3.4 — 43 total):
  Installation   (3): detectInstallations, loadInstallation, kotor_installation_info
  Discovery      (4): listResources, describeResource, kotor_find_resource, kotor_search_resources
  Game data      (3): journalOverview, kotor_lookup_2da, kotor_lookup_tlk
  GhostRigger    (5): ghostrigger_open_model, ghostrigger_render_model, ghostrigger_model_info,
                      ghostrigger_list_game_models, ghostrigger_audit
  Modules        (3): kotor_list_modules, kotor_describe_module, kotor_module_resources
  GFF data       (3): kotor_read_gff, kotor_read_2da, kotor_read_tlk
  AgentDecompile (11): kotor_binary_ping, kotor_binary_info, kotor_list_engine_funcs,
                       kotor_decompile_function, kotor_search_symbols,
                       kotor_search_engine_strings, kotor_get_references,
                       kotor_call_graph, kotor_data_flow, kotor_inspect_memory,
                       kotor_engine_script
  Composite      (2): get_resource, get_quest
  Refs           (6): kotor_list_references, kotor_find_referrers,
                      kotor_find_strref_referrers, kotor_describe_dlg,
                      kotor_describe_jrl, kotor_describe_resource_refs
  Walkmesh       (1): kotor_walkmesh_validation_diagram
  Archives       (2): kotor_list_archive, kotor_extract_resource
"""

from __future__ import annotations

from typing import Any, Dict, List

from kotormcp.tools import (
    installation, discovery, gamedata, ghostrigger,
    modules, gffdata, decompile, resource, quest,
    refs, walkmesh, archives,
)


def get_all_tools() -> List[Dict[str, Any]]:
    """Return all tool definitions from all tool modules.

    Tool count: 43 (v3.4)
      3  installation  +  4 discovery  +  3 gamedata  +  5 ghostrigger
    + 3  modules       +  3 gffdata    + 11 decompile  +  2 composite
    + 6  refs          +  1 walkmesh   +  2 archives
    = 43
    """
    return (
        installation.get_tools()          # 3  installation management
        + discovery.get_tools()           # 4  resource discovery
        + gamedata.get_tools()            # 3  game data (2da, tlk, journal)
        + ghostrigger.get_tools()         # 5  3D model pipeline
        + modules.get_tools()             # 3  module enumeration
        + gffdata.get_tools()             # 3  deep GFF/2DA/TLK reads
        + decompile.get_tools()           # 11 AgentDecompile / Ghidra bridge
        + resource.get_tools()            # 1  get_resource: universal accessor
        + quest.get_tools()               # 1  get_quest: composite quest inspector
        + refs.get_tools()                # 6  reference tracing (ported from upstream)
        + walkmesh.get_tools()            # 1  walkmesh validation diagram
        + archives.get_tools()            # 2  archive listing + extraction
    )


async def handle_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch tool invocation to the correct handler."""
    # ── Installation tools ────────────────────────────────────────────────────
    if name == "detectInstallations":
        return await installation.handle_detect_installations(arguments)
    if name == "loadInstallation":
        return await installation.handle_load_installation(arguments)
    if name == "kotor_installation_info":
        return await installation.handle_installation_info(arguments)

    # ── Discovery tools ───────────────────────────────────────────────────────
    if name == "listResources":
        return await discovery.handle_list_resources(arguments)
    if name == "describeResource":
        return await discovery.handle_describe_resource(arguments)
    if name == "kotor_find_resource":
        return await discovery.handle_find_resource(arguments)
    if name == "kotor_search_resources":
        return await discovery.handle_search_resources(arguments)

    # ── Game data tools ───────────────────────────────────────────────────────
    if name == "journalOverview":
        return await gamedata.handle_journal_overview(arguments)
    if name == "kotor_lookup_2da":
        return await gamedata.handle_lookup_2da(arguments)
    if name == "kotor_lookup_tlk":
        return await gamedata.handle_lookup_tlk(arguments)

    # ── GhostRigger-specific tools ────────────────────────────────────────────
    if name == "ghostrigger_open_model":
        return await ghostrigger.handle_open_model(arguments)
    if name == "ghostrigger_render_model":
        return await ghostrigger.handle_render_model(arguments)
    if name == "ghostrigger_model_info":
        return await ghostrigger.handle_model_info(arguments)
    if name == "ghostrigger_list_game_models":
        return await ghostrigger.handle_list_game_models(arguments)
    if name == "ghostrigger_audit":
        return await ghostrigger.handle_audit(arguments)

    # ── Module tools ──────────────────────────────────────────────────────────
    if name == "kotor_list_modules":
        return await modules.handle_list_modules(arguments)
    if name == "kotor_describe_module":
        return await modules.handle_describe_module(arguments)
    if name == "kotor_module_resources":
        return await modules.handle_module_resources(arguments)

    # ── Deep read tools ───────────────────────────────────────────────────────
    if name == "kotor_read_gff":
        return await gffdata.handle_read_gff(arguments)
    if name == "kotor_read_2da":
        return await gffdata.handle_read_2da(arguments)
    if name == "kotor_read_tlk":
        return await gffdata.handle_read_tlk(arguments)

    # ── AgentDecompile / Ghidra bridge tools ─────────────────────────────────
    if name == "kotor_binary_ping":
        return await decompile.handle_ping(arguments)
    if name == "kotor_binary_info":
        return await decompile.handle_binary_info(arguments)
    if name == "kotor_list_engine_funcs":
        return await decompile.handle_list_engine_funcs(arguments)
    if name == "kotor_decompile_function":
        return await decompile.handle_decompile_function(arguments)
    if name == "kotor_search_symbols":
        return await decompile.handle_search_symbols(arguments)
    if name == "kotor_search_engine_strings":
        return await decompile.handle_search_engine_strings(arguments)
    if name == "kotor_get_references":
        return await decompile.handle_get_references(arguments)
    if name == "kotor_call_graph":
        return await decompile.handle_call_graph(arguments)
    if name == "kotor_data_flow":
        return await decompile.handle_data_flow(arguments)
    if name == "kotor_inspect_memory":
        return await decompile.handle_inspect_memory(arguments)
    if name == "kotor_engine_script":
        return await decompile.handle_engine_script(arguments)

    # ── Composite / high-level tools (v3.3) ───────────────────────────────────
    if name == "get_resource":
        return await resource.handle_get_resource(arguments)
    if name == "get_quest":
        return await quest.handle_get_quest(arguments)

    # ── Reference and plot tools (v3.4 — ported from upstream KotorMCP) ───────
    if name == "kotor_list_references":
        return await refs.handle_list_references(arguments)
    if name == "kotor_find_referrers":
        return await refs.handle_find_referrers(arguments)
    if name == "kotor_find_strref_referrers":
        return await refs.handle_find_strref_referrers(arguments)
    if name == "kotor_describe_dlg":
        return await refs.handle_describe_dlg(arguments)
    if name == "kotor_describe_jrl":
        return await refs.handle_describe_jrl(arguments)
    if name == "kotor_describe_resource_refs":
        return await refs.handle_describe_resource_refs(arguments)

    # ── Walkmesh tools (v3.4 — ported from upstream KotorMCP) ────────────────
    if name == "kotor_walkmesh_validation_diagram":
        return await walkmesh.handle_walkmesh_validation_diagram(arguments)

    # ── Archive tools (v3.4 — ported from upstream KotorMCP) ─────────────────
    if name == "kotor_list_archive":
        return await archives.handle_list_archive(arguments)
    if name == "kotor_extract_resource":
        return await archives.handle_extract_resource(arguments)

    raise ValueError(f"Unknown tool: '{name}'")
