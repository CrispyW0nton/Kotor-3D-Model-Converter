"""
Deep read tools: kotor_read_gff, kotor_read_2da, kotor_read_tlk.

Ported from the upstream KotorMCP project and adapted to use the
GhostRigger InstallationPort contract (Contract Coupling).

These tools provide full structured access to KotOR's binary formats,
complementing the lighter-weight summarization already in discovery.py.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Optional

from kotormcp.schemas import Read2daInput, ReadGffInput, ReadTlkInput
from kotormcp.state import load_installation, resolve_game
from kotormcp.utils import json_content


def get_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": "kotor_read_gff",
            "description": (
                "Read a GFF-format resource (UTC, UTP, DLG, ARE, etc.) and return "
                "its full field tree as JSON.  Supports field path filtering and "
                "depth / field-count limits to manage response size."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string"},
                    "resref": {"type": "string"},
                    "restype": {
                        "type": "string",
                        "description": "File extension, e.g. utc, utp, dlg, are, git, jrl",
                    },
                    "field_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of dot-separated field paths to extract",
                    },
                    "max_depth": {
                        "type": "integer",
                        "default": 4,
                        "description": "Maximum recursion depth (default 4)",
                    },
                    "max_fields": {
                        "type": "integer",
                        "default": 200,
                        "description": "Maximum fields returned per struct (default 200)",
                    },
                },
                "required": ["game", "resref", "restype"],
            },
        },
        {
            "name": "kotor_read_2da",
            "description": (
                "Read rows and columns from a 2DA table.  "
                "Supports row slicing and column selection."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string"},
                    "resref": {
                        "type": "string",
                        "description": "2DA table name, e.g. appearance, baseitems",
                    },
                    "row_start": {"type": "integer", "default": 0},
                    "row_end": {"type": "integer", "description": "Exclusive end row (default: 500)"},
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Column names to include (default: all)",
                    },
                },
                "required": ["game", "resref"],
            },
        },
        {
            "name": "kotor_read_tlk",
            "description": (
                "Read entries from dialog.tlk by strref range or text search. "
                "Supports batch resolution of multiple strrefs."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string"},
                    "strref_start": {
                        "type": "integer",
                        "description": "First strref (inclusive)",
                    },
                    "strref_end": {
                        "type": "integer",
                        "description": "Last strref (inclusive)",
                    },
                    "text_search": {
                        "type": "string",
                        "description": "Substring to search for in TLK entries",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 100,
                        "description": "Maximum entries to return",
                    },
                },
                "required": ["game"],
            },
        },
    ]


# ── Handlers ──────────────────────────────────────────────────────────────────

async def handle_read_gff(arguments: Dict[str, Any]) -> Dict[str, Any]:
    inp = ReadGffInput.model_validate(arguments)
    game = resolve_game(inp.game)
    if game is None:
        return json_content({"error": "Specify game (k1/k2)."})
    try:
        from pykotor.resource.formats.gff.gff_auto import read_gff  # noqa: PLC0415
        installation = load_installation(game)
        entry = installation.get_resource(inp.resref, inp.restype)
        if entry is None:
            return json_content({"error": f"{inp.resref}.{inp.restype} not found."})
        gff = read_gff(BytesIO(entry.data))
        max_depth = inp.max_depth if inp.max_depth is not None else 4
        max_fields = inp.max_fields if inp.max_fields is not None else 200
        tree = _gff_struct_to_dict(gff.root, max_depth=max_depth, max_fields=max_fields)
        return json_content({
            "resref": inp.resref,
            "restype": inp.restype,
            "root": tree,
        })
    except Exception as exc:
        return json_content({"error": str(exc)})


async def handle_read_2da(arguments: Dict[str, Any]) -> Dict[str, Any]:
    inp = Read2daInput.model_validate(arguments)
    game = resolve_game(inp.game)
    if game is None:
        return json_content({"error": "Specify game (k1/k2)."})
    try:
        from pykotor.resource.formats.twoda.twoda_auto import read_2da  # noqa: PLC0415
        installation = load_installation(game)
        entry = installation.get_resource(inp.resref, "2da")
        if entry is None:
            return json_content({"error": f"2DA '{inp.resref}' not found."})
        table = read_2da(entry.data)
        headers = table.get_headers()
        cols = [c for c in (inp.columns or headers) if c in headers] or headers
        row_start = inp.row_start or 0
        row_end = inp.row_end if inp.row_end is not None else min(row_start + 500, table.get_height())
        rows = []
        for i in range(row_start, min(row_end, table.get_height())):
            rows.append({"row": i, "values": {h: table.get_cell_safe(i, h, "") for h in cols}})
        return json_content({
            "resref": inp.resref,
            "columns": cols,
            "total_rows": table.get_height(),
            "row_start": row_start,
            "row_end": row_end,
            "rows": rows,
        })
    except Exception as exc:
        return json_content({"error": str(exc)})


async def handle_read_tlk(arguments: Dict[str, Any]) -> Dict[str, Any]:
    inp = ReadTlkInput.model_validate(arguments)
    game = resolve_game(inp.game)
    if game is None:
        return json_content({"error": "Specify game (k1/k2)."})
    try:
        installation = load_installation(game)
        limit = min(inp.limit or 100, 500)
        entries = []

        if inp.text_search:
            # Scan for text matches — use talktable_string via port for individual lookups
            # The upper bound is set conservatively to avoid very slow scans
            text_lower = inp.text_search.lower()
            scan_end = 50_000
            for i in range(scan_end):
                if len(entries) >= limit:
                    break
                try:
                    text = installation.talktable_string(i)
                    if text and text_lower in text.lower():
                        entries.append({"strref": i, "text": text})
                except Exception:
                    pass
        else:
            start = inp.strref_start or 0
            end = inp.strref_end if inp.strref_end is not None else start + limit - 1
            for i in range(start, min(end + 1, start + limit)):
                try:
                    text = installation.talktable_string(i)
                    entries.append({"strref": i, "text": text})
                except Exception:
                    break  # past end of talktable

        return json_content({"count": len(entries), "entries": entries})
    except Exception as exc:
        return json_content({"error": str(exc)})


# ── Internal helpers ──────────────────────────────────────────────────────────

def _gff_struct_to_dict(
    struct: Any,
    depth: int = 0,
    max_depth: int = 4,
    max_fields: int = 200,
) -> Dict[str, Any]:
    """Recursively convert a GFFStruct to a JSON-serializable dict."""
    if depth > max_depth:
        return {"_truncated": f"max depth {max_depth} reached"}
    result: Dict[str, Any] = {"_struct_id": getattr(struct, "struct_id", None)}
    count = 0
    try:
        for label, field_type, value in struct:
            if count >= max_fields:
                result["_truncated"] = f"limited to {max_fields} fields"
                break
            count += 1
            if isinstance(value, bytes):
                result[label] = f"<bytes:{len(value)}>"
            elif hasattr(value, "__iter__") and hasattr(value, "__len__"):
                # GFFList
                result[label] = [
                    _gff_struct_to_dict(item, depth + 1, max_depth, max_fields)
                    for item in list(value)[:50]
                ]
            elif hasattr(value, "struct_id"):
                # Nested GFFStruct
                result[label] = _gff_struct_to_dict(value, depth + 1, max_depth, max_fields)
            else:
                str_val = str(value)
                result[label] = str_val if len(str_val) <= 500 else str_val[:497] + "..."
    except Exception as exc:
        result["_error"] = str(exc)
    return result
