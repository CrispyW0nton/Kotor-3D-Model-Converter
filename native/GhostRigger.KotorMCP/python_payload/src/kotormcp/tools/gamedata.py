"""Game data tools: journal overview, lookup_2da, lookup_tlk.

Architecture note (Khononov, "Balancing Coupling in Software Design"):
  Handlers in this module depend on the InstallationPort contract
  (get_resource / talktable_string) rather than pykotor internals.
  All pykotor-specific handling is isolated inside InstallationAdapter.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Optional

from kotormcp.schemas import JournalOverviewInput, Lookup2daInput, LookupTlkInput
from kotormcp.state import load_installation, resolve_game
from kotormcp.utils import json_content


def get_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": "journalOverview",
            "description": "Summary of global.jrl plot categories and entries. Read-only.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string"},
                    "path": {"type": "string", "description": "Optional explicit install path"},
                },
                "required": ["game"],
            },
        },
        {
            "name": "kotor_lookup_2da",
            "description": "Query a 2DA table by row index, column name, or value search. Read-only.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string"},
                    "table_name": {"type": "string"},
                    "row_index": {"type": "integer"},
                    "column": {"type": "string"},
                    "value_search": {"type": "string"},
                    "path": {"type": "string", "description": "Optional explicit install path"},
                },
                "required": ["game", "table_name"],
            },
        },
        {
            "name": "kotor_lookup_tlk",
            "description": "Resolve a strref to display text from dialog.tlk. Read-only.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string"},
                    "strref": {"type": "integer"},
                    "path": {"type": "string", "description": "Optional explicit install path"},
                },
                "required": ["game", "strref"],
            },
        },
    ]


def _load_2da_bytes(installation, table_name: str) -> Optional[bytes]:
    """
    Retrieve raw 2DA bytes from an InstallationPort.

    Uses the port's get_resource() contract (preferred) with fallback
    to pykotor's installation.resource() for raw installs.
    """
    entry = installation.get_resource(table_name, "2da")
    if entry is not None:
        return entry.data

    # Fallback: try pykotor raw API (adapters that expose _inst)
    try:
        from pykotor.resource.type import ResourceType  # noqa: PLC0415
        from pykotor.extract.installation import SearchLocation  # noqa: PLC0415
        inner = getattr(installation, "_inst", None)
        if inner is None:
            return None
        order = [SearchLocation.OVERRIDE, SearchLocation.MODULES, SearchLocation.CHITIN]
        result = inner.resource(table_name, ResourceType.TwoDA, order=order)
        return result.data if result is not None else None
    except Exception:
        return None


def _load_gff_bytes(installation, resref: str, restype_str: str) -> Optional[bytes]:
    """Retrieve raw GFF bytes (JRL, UTC, UTP etc.) from an InstallationPort."""
    entry = installation.get_resource(resref, restype_str)
    if entry is not None:
        return entry.data

    # Fallback: try pykotor raw API
    try:
        from pykotor.resource.type import ResourceType  # noqa: PLC0415
        from pykotor.extract.installation import SearchLocation  # noqa: PLC0415
        inner = getattr(installation, "_inst", None)
        if inner is None:
            return None
        rt = ResourceType.from_extension(restype_str.lower())
        order = [SearchLocation.OVERRIDE, SearchLocation.MODULES, SearchLocation.CHITIN]
        result = inner.resource(resref, rt, order=order)
        return result.data if result is not None else None
    except Exception:
        return None


async def handle_journal_overview(arguments: Dict[str, Any]) -> Dict[str, Any]:
    inp = JournalOverviewInput.model_validate(arguments)
    game = resolve_game(inp.game)
    if game is None:
        return json_content({"error": "Specify game parameter (k1/k2)."})
    try:
        from pykotor.resource.formats.gff.gff_auto import read_gff  # noqa: PLC0415
    except ImportError:
        return json_content({"error": "pykotor is required for journalOverview."})
    try:
        explicit_path = arguments.get("path")
        installation = load_installation(game, explicit_path)
        data = _load_gff_bytes(installation, "global", "jrl")
        if data is None:
            return json_content({"error": "global.jrl not found in installation."})
        gff = read_gff(BytesIO(data))
        categories = []
        for entry in gff.root.get_list("Categories", default=[]):
            category: Dict[str, Any] = {
                "name": entry.get_string("Name", ""),
                "tag": entry.get_string("Tag", ""),
                "priority": entry.get_uint("Priority", 0),
                "entries": [],
            }
            for quest in entry.get_list("EntryList", default=[]):
                category["entries"].append({
                    "id": quest.get_uint("ID", 0),
                    "text": quest.get_string("Text", "")[:400],
                    "completes_plot": bool(quest.get_uint("End", 0)),
                })
            categories.append(category)
        return json_content({"count": len(categories), "categories": categories})
    except Exception as exc:
        return json_content({"error": str(exc)})


async def handle_lookup_2da(arguments: Dict[str, Any]) -> Dict[str, Any]:
    inp = Lookup2daInput.model_validate(arguments)
    game = resolve_game(inp.game)
    if game is None:
        return json_content({"error": "Specify game (k1/k2)."})
    try:
        from pykotor.resource.formats.twoda.twoda_auto import read_2da  # noqa: PLC0415
        explicit_path = arguments.get("path")
        installation = load_installation(game, explicit_path)
        data = _load_2da_bytes(installation, inp.table_name)
        if data is None:
            return json_content({"error": f"2DA table '{inp.table_name}' not found."})
        table = read_2da(BytesIO(data))
        row_index = getattr(inp, "row_index", None)
        column = getattr(inp, "column", None)
        value_search = getattr(inp, "value_search", None)
        if row_index is not None:
            headers = table.get_headers()
            out = {}
            for h in headers:
                try:
                    out[h] = table.get_cell(row_index, h)
                except Exception:
                    out[h] = ""
            return json_content({"table": inp.table_name, "row_index": row_index, "row": out})
        if value_search and column:
            matches = []
            for i in range(table.get_height()):
                try:
                    val = str(table.get_cell(i, column) or "")
                except Exception:
                    val = ""
                if value_search.lower() in val.lower():
                    matches.append({"row_index": i, column: val})
                    if len(matches) >= 50:
                        break
            return json_content({"table": inp.table_name, "column": column, "rows": matches})
        return json_content({
            "table": inp.table_name,
            "columns": table.get_headers(),
            "row_count": table.get_height(),
        })
    except Exception as exc:
        return json_content({"error": str(exc)})


async def handle_lookup_tlk(arguments: Dict[str, Any]) -> Dict[str, Any]:
    inp = LookupTlkInput.model_validate(arguments)
    game = resolve_game(inp.game)
    if game is None:
        return json_content({"error": "Specify game (k1/k2)."})
    try:
        explicit_path = arguments.get("path")
        installation = load_installation(game, explicit_path)
        # Use port contract: talktable_string(strref)
        text = installation.talktable_string(inp.strref)
        return json_content({"strref": inp.strref, "text": text})
    except Exception as exc:
        return json_content({"error": str(exc)})
