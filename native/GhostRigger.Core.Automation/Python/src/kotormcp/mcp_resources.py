"""MCP resources: kotor:// URI scheme for passive context injection.

URIs supported:
  kotor://k1/resource/{resref}.{ext}   — Resolved binary resource (base64)
  kotor://k2/resource/{resref}.{ext}
  kotor://k1/2da/{table_name}          — 2DA table as JSON
  kotor://k2/2da/{table_name}
  kotor://k1/tlk/{strref}              — TLK string by reference
  kotor://k2/tlk/{strref}
  kotor://docs/capabilities            — Agent onboarding markdown
  kotor://ghostrigger/model/{resref}   — GhostRigger model info JSON
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, List
from urllib.parse import unquote

from kotormcp.state import load_installation, resolve_game


def _game_from_authority(authority: str):
    return resolve_game("k1" if authority == "k1" else "k2" if authority == "k2" else None)


def parse_kotor_uri(uri: str) -> Dict[str, Any]:
    """Parse kotor:// URI into components. Returns empty dict if invalid."""
    if not uri.startswith("kotor://"):
        return {}
    parts = uri[8:].split("/", 2)
    if len(parts) < 2:
        return {}
    authority = parts[0].lower()
    resource_type = parts[1].lower()
    path = unquote(parts[2]) if len(parts) > 2 else ""
    game = _game_from_authority(authority)
    return {"game": game, "type": resource_type, "path": path, "uri": uri, "authority": authority}


async def list_resource_templates() -> List[Dict[str, Any]]:
    """Return parameterized MCP resource templates."""
    return [
        {"uriTemplate": "kotor://k1/resource/{resref}.{ext}", "name": "K1 Resource",
         "description": "Resolve resource by resref.ext", "mimeType": "application/octet-stream"},
        {"uriTemplate": "kotor://k2/resource/{resref}.{ext}", "name": "K2 Resource",
         "description": "Resolve resource by resref.ext", "mimeType": "application/octet-stream"},
        {"uriTemplate": "kotor://k1/2da/{table_name}", "name": "K1 2DA Table",
         "description": "2DA table as JSON", "mimeType": "application/json"},
        {"uriTemplate": "kotor://k2/2da/{table_name}", "name": "K2 2DA Table",
         "description": "2DA table as JSON", "mimeType": "application/json"},
        {"uriTemplate": "kotor://k1/tlk/{strref}", "name": "K1 TLK String",
         "description": "TLK string by strref", "mimeType": "text/plain"},
        {"uriTemplate": "kotor://k2/tlk/{strref}", "name": "K2 TLK String",
         "description": "TLK string by strref", "mimeType": "text/plain"},
        {"uriTemplate": "kotor://ghostrigger/model/{resref}", "name": "GhostRigger Model Info",
         "description": "JSON metadata for a KotOR MDL model", "mimeType": "application/json"},
    ]


async def list_resources() -> List[Dict[str, Any]]:
    """Return concrete MCP resources.

    Parameterized resources must be exposed through ``list_resource_templates``.
    Returning templated URIs from ``resources/list`` makes some MCP clients
    percent-encode the braces and hide the entries entirely.
    """
    return [
        {"uri": "kotor://docs/capabilities", "name": "KotorMCP capabilities",
         "description": "Tool index and resolution order for agent onboarding", "mimeType": "text/markdown"},
        {"uri": "kotor://k1/2da/appearance", "name": "K1 appearance.2da",
         "description": "Common character/body/head appearance table", "mimeType": "application/json"},
        {"uri": "kotor://k2/2da/appearance", "name": "K2 appearance.2da",
         "description": "Common character/body/head appearance table", "mimeType": "application/json"},
    ]


def _capabilities_doc() -> str:
    return """# GhostRigger KotorMCP Capabilities

## Resource resolution order

1. **OVERRIDE** — Game override directory (user/mod content)
2. **MODULES** — Module ERFs in load order
3. **CHITIN** — Base game KEY/BIF data

## Tool index

| Tool | Use when |
|------|----------|
| detectInstallations | Discover K1/K2 installation paths |
| loadInstallation | Activate an installation for subsequent calls |
| kotor_installation_info | Check game path, validity, module/override counts |
| listResources | List resources with location/type/name filters |
| describeResource | Summarize a single resource (GFF, TLK, 2DA) |
| kotor_find_resource | Find files by resref/glob |
| kotor_search_resources | Search by regex with pagination |
| journalOverview | Summarize global.jrl plot categories |
| kotor_lookup_2da | Query 2DA table rows/columns |
| kotor_lookup_tlk | Resolve strref to dialog.tlk text |
| ghostrigger_open_model | Open MDL in the 3D viewport |
| ghostrigger_render_model | Render MDL to PNG image |
| ghostrigger_model_info | Get node/mesh/bone/bbox info for an MDL |
| ghostrigger_list_game_models | List available MDL models in an installation |
| ghostrigger_audit | Quick integrity check on an MDL |

## GhostRigger integration

GhostRigger listens on port **7001** for IPC calls. When `ghostrigger_open_model` is called,
the MCP server will POST to the IPC endpoint to trigger the viewport to load the model.
If GhostRigger is not running, the tool returns the model path and metadata instead.
"""


async def read_resource(uri: str) -> Dict[str, Any]:
    """Read kotor:// resource and return content."""
    parsed = parse_kotor_uri(uri)
    if not parsed:
        return {"error": f"Invalid kotor:// URI: {uri}"}

    authority = parsed.get("authority", "")
    resource_type = parsed["type"]
    path = parsed["path"]

    if authority == "docs" and resource_type == "capabilities":
        return {"uri": uri, "mimeType": "text/markdown", "text": _capabilities_doc()}

    if authority == "ghostrigger" and resource_type == "model":
        from kotormcp.tools.ghostrigger import handle_model_info  # noqa: PLC0415
        result = await handle_model_info({"resref": path})
        text = result.get("text", json.dumps({"error": "no data"}))
        return {"uri": uri, "mimeType": "application/json", "text": text}

    game = parsed["game"]
    if game is None:
        return {"error": f"Unknown game in URI: {uri}"}

    try:
        installation = load_installation(game)
    except Exception as exc:
        return {"error": str(exc)}

    if resource_type == "resource":
        try:
            from pykotor.resource.type import ResourceType  # noqa: PLC0415
            from pykotor.extract.file import ResourceIdentifier  # noqa: PLC0415
            from pykotor.extract.installation import SearchLocation  # noqa: PLC0415
            ident = ResourceIdentifier.from_path(path)
            if ident.restype == ResourceType.INVALID:
                return {"error": f"Unknown resource type in URI: {path}"}
            order = [SearchLocation.OVERRIDE, SearchLocation.MODULES, SearchLocation.CHITIN]
            result = installation.resource(ident.resname, ident.restype, order=order)
            if result is None:
                return {"error": f"Resource not found: {path}"}
            return {"uri": uri, "mimeType": "application/octet-stream",
                    "blob": base64.b64encode(result.data).decode("ascii")}
        except Exception as exc:
            return {"error": str(exc)}

    if resource_type == "2da":
        try:
            from io import BytesIO  # noqa: PLC0415
            from pykotor.resource.formats.twoda.twoda_auto import read_2da  # noqa: PLC0415
            from pykotor.resource.type import ResourceType  # noqa: PLC0415
            from pykotor.extract.installation import SearchLocation  # noqa: PLC0415
            order = [SearchLocation.OVERRIDE, SearchLocation.MODULES, SearchLocation.CHITIN]
            result = installation.resource(path or "appearance", ResourceType.TwoDA, order=order)
            if result is None:
                return {"error": f"2DA not found: {path}"}
            table = read_2da(result.data)
            headers = table.get_headers()
            rows = [{h: table.get_cell_safe(i, h, "") for h in headers}
                    for i in range(min(table.get_height(), 500))]
            return {"uri": uri, "mimeType": "application/json",
                    "text": json.dumps({"columns": headers, "rows": rows}, indent=2)}
        except Exception as exc:
            return {"error": str(exc)}

    if resource_type == "tlk":
        try:
            strref = int(path.strip()) if path.strip().isdigit() else -1
            text = installation.talktable().string(strref)
            return {"uri": uri, "mimeType": "text/plain", "text": text}
        except Exception as exc:
            return {"error": str(exc)}

    return {"error": f"Unsupported resource type in URI: {resource_type}"}
