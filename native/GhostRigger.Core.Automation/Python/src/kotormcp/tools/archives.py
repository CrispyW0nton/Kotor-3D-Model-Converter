"""Archive operations: list_archive, extract_resource.

Ported from OldRepublicDevs/KotorMCP (Tools/KotorMCP/src/kotormcp/tools/archives.py)
and adapted to GhostRigger's port-contract layer (ports.py / adapters.py).

Design note (Constantine, §11 — coupling):
  Both tools use data coupling only: each receives a plain dict and returns
  a JSON payload.  The extract tool is the FIRST write-capable tool in
  GhostRigger KotorMCP; it writes to a path-validated location on disk.

Tools exposed:
  kotor_list_archive      — list KEY/BIF/RIM/ERF/MOD contents (read-only)
  kotor_extract_resource  — extract a resource to disk (write: disk output)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from kotormcp.schemas import ListArchiveInput, ExtractResourceInput
from kotormcp.state import load_installation, resolve_game
from kotormcp.utils.formatting import json_content


def _parse_restype(restype_str: str):
    """Parse restype string to ResourceType."""
    try:
        from pykotor.resource.type import ResourceType  # type: ignore[import]
        ext = restype_str.strip().lstrip(".").lower()
        return ResourceType.from_extension(ext)
    except ImportError:
        return None


def get_tools() -> List[Dict[str, Any]]:
    """Return tool definitions for archive operations."""
    return [
        {
            "name": "kotor_list_archive",
            "description": (
                "Use when you need to list contents of a KEY/BIF/RIM/ERF/MOD file "
                "with pagination. Read-only."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to archive file"},
                    "key_file": {"type": "string", "description": "Path to KEY file (for BIF listing)"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
                    "offset": {"type": "integer", "minimum": 0, "default": 0},
                },
                "required": ["file_path"],
            },
        },
        {
            "name": "kotor_extract_resource",
            "description": (
                "Use when you need to write a resolved resource to disk. "
                "Optional 'source' restricts to one location (OVERRIDE, CHITIN, MODULES). "
                "[destructiveHint: writes to disk]"
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "description": "Game alias: k1 or k2"},
                    "resref": {"type": "string", "description": "Resource reference name"},
                    "restype": {"type": "string", "description": "Resource type (extension or name)"},
                    "output_path": {"type": "string", "description": "Output file or directory path (validated)"},
                    "source": {
                        "type": "string",
                        "description": "Optional: extract only from this location (OVERRIDE, CHITIN, MODULES, etc.)",
                    },
                },
                "required": ["game", "resref", "restype", "output_path"],
            },
        },
    ]


# ── Handlers ──────────────────────────────────────────────────────────────────

async def handle_list_archive(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """List archive contents with pagination."""
    inp = ListArchiveInput.model_validate(arguments)

    try:
        from pykotor.tools.archives import list_bif, list_erf, list_key, list_rim  # type: ignore[import]
    except ImportError as e:
        return {"type": "text", "text": f'{{"error": "pykotor not available: {e}"}}'}

    path = Path(inp.file_path)
    if not path.exists():
        return {"type": "text", "text": f'{{"error": "Archive file not found: {path}"}}'}

    suffix = path.suffix.lower()
    items: List[Dict[str, Any]] = []
    try:
        if suffix == ".key":
            bif_files, resources = list_key(path)
            for resref, restype_ext, bif_index, res_index in resources:
                items.append({
                    "resref": resref,
                    "type": restype_ext,
                    "bif_index": bif_index,
                    "res_index": res_index,
                    "bif_file": bif_files[bif_index] if bif_index < len(bif_files) else None,
                })
        elif suffix == ".bif":
            key_path = Path(inp.key_file) if inp.key_file else path.parent / "chitin.key"
            for ar in list_bif(path, key_path=key_path if key_path.exists() else None):
                items.append({"resref": str(ar.resref), "type": ar.restype.extension, "size": ar.size})
        elif suffix == ".rim":
            for ar in list_rim(path):
                items.append({"resref": str(ar.resref), "type": ar.restype.extension, "size": ar.size})
        elif suffix in (".erf", ".mod", ".sav", ".hak"):
            for ar in list_erf(path):
                items.append({"resref": str(ar.resref), "type": ar.restype.extension, "size": ar.size})
        else:
            return {"type": "text", "text": f'{{"error": "Unsupported archive type: {suffix}. Use .key, .bif, .rim, .erf, .mod, .sav, .hak"}}'}
    except Exception as e:
        return {"type": "text", "text": f'{{"error": "{e}"}}'}

    limit = getattr(inp, "limit", 50) or 50
    offset = getattr(inp, "offset", 0) or 0
    total = len(items)
    page = items[offset: offset + limit]
    has_more = total > offset + limit
    next_offset = offset + len(page) if has_more else None
    return json_content({
        "total": total,
        "count": len(page),
        "offset": offset,
        "items": page,
        "has_more": has_more,
        "next_offset": next_offset,
    })


async def handle_extract_resource(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Extract resource from installation to output path."""
    inp = ExtractResourceInput.model_validate(arguments)
    game = resolve_game(inp.game)
    if game is None:
        return {"type": "text", "text": '{"error": "Unknown game alias. Use k1 or k2."}'}

    try:
        from pykotor.tools.path_safety import get_extract_base, resolve_and_validate_under_base  # type: ignore[import]
    except ImportError as e:
        return {"type": "text", "text": f'{{"error": "pykotor not available: {e}"}}'}

    try:
        installation = load_installation(game)
        source = getattr(inp, "source", None)
        restype = _parse_restype(inp.restype)
        if restype is None:
            return {"type": "text", "text": f'{{"error": "Unknown resource type: {inp.restype}"}}'}

        order_override = None
        if source and source.strip():
            try:
                from pykotor.extract.installation import SearchLocation  # type: ignore[import]
                name_to_loc = {e.name: e for e in SearchLocation}
                loc = name_to_loc.get(source.strip().upper())
                if loc is not None:
                    order_override = [loc.name]
            except ImportError:
                pass

        entry = installation.get_resource(inp.resref, restype.name, order=order_override)
        if entry is None:
            return {"type": "text", "text": f'{{"error": "Resource {inp.resref}.{restype.name} not found."}}'}

        out_path = Path(inp.output_path)
        ext = f".{restype.extension}"
        if out_path.suffix.lower() != ext:
            if out_path.is_dir():
                out_path = out_path / f"{inp.resref}{ext}"
            else:
                out_path = out_path.with_suffix(ext)

        try:
            out_path = resolve_and_validate_under_base(out_path, get_extract_base(), allow_nonexistent=True)
        except ValueError as e:
            return {"type": "text", "text": f'{{"error": "Output path rejected: {e}"}}'}

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(entry.data)
        return json_content({"status": "ok", "path": str(out_path), "bytes": len(entry.data)})
    except Exception as e:
        return {"type": "text", "text": f'{{"error": "{e}"}}'}
