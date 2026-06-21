"""
Module-level tools: list, describe, and browse resources within KOTOR modules.

Ported from the upstream KotorMCP project (OldRepublicDevs/PyKotor) and
adapted to use the GhostRigger InstallationPort contract.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from kotormcp.schemas import DescribeModuleInput, ListModulesInput, ModuleResourcesInput
from kotormcp.state import load_installation, resolve_game
from kotormcp.utils import json_content


def get_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": "kotor_list_modules",
            "description": (
                "List all available module roots in a KotOR installation. "
                "Returns each unique module name with the associated area name where available."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "description": "k1 or k2"},
                },
                "required": ["game"],
            },
        },
        {
            "name": "kotor_describe_module",
            "description": (
                "Describe a specific module: area GFF struct, room count, "
                "per-type resource breakdown, and referenced scripts."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string"},
                    "module_root": {
                        "type": "string",
                        "description": "Module root name (e.g. 203tel, manm26ac)",
                    },
                },
                "required": ["game", "module_root"],
            },
        },
        {
            "name": "kotor_module_resources",
            "description": (
                "Paginated list of all resources in a specific module. "
                "Returns resref, type, extension, size, and source file."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string"},
                    "module_root": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                    "offset": {"type": "integer", "default": 0},
                },
                "required": ["game", "module_root"],
            },
        },
    ]


# ── Handlers ──────────────────────────────────────────────────────────────────

async def handle_list_modules(arguments: Dict[str, Any]) -> Dict[str, Any]:
    inp = ListModulesInput.model_validate(arguments)
    game = resolve_game(inp.game)
    if game is None:
        return json_content({"error": "Specify game (k1/k2)."})
    try:
        installation = load_installation(game)
        modules = installation.module_names()
        return json_content({"count": len(modules), "modules": modules})
    except Exception as exc:
        return json_content({"error": str(exc)})


async def handle_describe_module(arguments: Dict[str, Any]) -> Dict[str, Any]:
    inp = DescribeModuleInput.model_validate(arguments)
    game = resolve_game(inp.game)
    if game is None:
        return json_content({"error": "Specify game (k1/k2)."})
    try:
        from pykotor.resource.type import ResourceType  # noqa: PLC0415
        installation = load_installation(game)
        module_root = inp.module_root.lower()

        # Collect all resources from matching module(s)
        type_counts: Dict[str, int] = {}
        scripts: set = set()
        resource_count = 0
        are_info: Optional[Dict[str, Any]] = None

        for entry in installation.iter_resources(f"module:{module_root}"):
            resource_count += 1
            type_counts[entry.restype] = type_counts.get(entry.restype, 0) + 1

            # Parse the ARE (area descriptor) for a summary
            if entry.restype == "ARE" and entry.resref.lower() == module_root and are_info is None:
                try:
                    full_entry = installation.get_resource(entry.resref, "are")
                    if full_entry and full_entry.data:
                        are_info = _summarize_gff_bytes(full_entry.data)
                except Exception:
                    pass

            # Collect script references from NSS/NCS resources
            if entry.restype in {"NSS", "NCS"}:
                scripts.add(entry.resref)

        if resource_count == 0:
            return json_content({"error": f"Module '{module_root}' not found."})

        return json_content({
            "module_root": module_root,
            "resource_count": resource_count,
            "type_breakdown": type_counts,
            "area_info": are_info,
            "scripts": sorted(scripts)[:50],
        })
    except Exception as exc:
        return json_content({"error": str(exc)})


async def handle_module_resources(arguments: Dict[str, Any]) -> Dict[str, Any]:
    inp = ModuleResourcesInput.model_validate(arguments)
    game = resolve_game(inp.game)
    if game is None:
        return json_content({"error": "Specify game (k1/k2)."})
    try:
        installation = load_installation(game)
        module_root = inp.module_root.lower()
        limit = max(1, min(inp.limit, 500))
        offset = max(0, inp.offset)

        items = []
        skipped = 0
        total = 0
        for entry in installation.iter_resources(f"module:{module_root}"):
            total += 1
            if skipped < offset:
                skipped += 1
                continue
            if len(items) < limit:
                items.append({
                    "resref": entry.resref,
                    "type": entry.restype,
                    "extension": entry.extension,
                    "size": entry.size,
                    "source": entry.source,
                })

        has_more = (offset + len(items)) < total
        return json_content({
            "module_root": module_root,
            "count": len(items),
            "total": total,
            "offset": offset,
            "has_more": has_more,
            "next_offset": (offset + len(items)) if has_more else None,
            "items": items,
        })
    except Exception as exc:
        return json_content({"error": str(exc)})


# ── Internal helper ───────────────────────────────────────────────────────────

def _summarize_gff_bytes(data: bytes) -> Dict[str, Any]:
    try:
        from pykotor.resource.formats.gff.gff_auto import read_gff  # noqa: PLC0415
        gff = read_gff(data)
        root = gff.root
        fields = []
        for label, field_type, value in root:
            preview: Any = value
            if isinstance(value, bytes):
                preview = f"<bytes:{len(value)}>"
            elif hasattr(value, "__len__") and len(str(value)) > 80:
                preview = f"{str(value)[:77]}..."
            fields.append({"label": label, "type": field_type.name, "preview": str(preview)})
        return {"struct_id": root.struct_id, "field_count": len(root), "fields": fields[:20]}
    except Exception as exc:
        return {"error": str(exc)}
