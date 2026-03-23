"""
get_resource — universal KotOR resource accessor.

Constantine/Khononov design notes
──────────────────────────────────
• Functional cohesion: this module does exactly one thing — return the content
  of a named resource, decoded to the most useful human/LLM-readable form.
• Data coupling only: callers pass (game, resref, restype) and receive content.
  No flags, no control parameters that change the function's behaviour.
• Context-free naming: the tool is called "get_resource", not
  "discord_get_resource" or "vscode_get_resource".  The same atomic operation
  is valid in every consumer context.
• Black-box principle: callers need not know whether the resource lives in
  chitin.key, override/, or a .mod — that decision is hidden in the adapter.
• Generality by exclusion: specialised decoders (GFF→JSON, 2DA→TSV, TLK→text,
  MDL→info, NCS→hex summary, plain bytes→base64) are selected at runtime based
  on restype, not baked into the tool name or description.

Scope of effect ⊆ scope of control (Constantine §7):
  All decisions about how to decode a resource live inside this module's
  handlers, not in the callers — so the scope-of-effect rule is satisfied.
"""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Any, Dict, List, Optional

from kotormcp.state import load_installation, resolve_game
from kotormcp.utils import json_content


# ── Tool definitions ──────────────────────────────────────────────────────────

def get_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": "get_resource",
            "description": (
                "Return the content of any KotOR resource identified by resref and type. "
                "GFF-based resources (utc, utp, utd, uti, utm, uts, utt, utp, dlg, are, "
                "git, ifo, jrl, fac, gic, mod, nfo, bic) are decoded to a JSON field tree. "
                "2DA tables are returned as TSV rows. "
                "TLK entries are returned as numbered text lines. "
                "MDL models return a structural summary (node count, meshes, animations). "
                "NCS scripts return a hex+size summary. "
                "All other binary resources return base64-encoded bytes with a size header. "
                "Resolution order: override → modules → chitin (highest priority wins). "
                "Read-only."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {
                        "type": "string",
                        "description": "Game alias: k1 or k2",
                    },
                    "resref": {
                        "type": "string",
                        "description": "Resource reference name without extension, e.g. 'global', 'n_sithpraet', 'appearance'",
                    },
                    "restype": {
                        "type": "string",
                        "description": (
                            "Resource type / file extension, e.g. "
                            "'jrl', 'utc', 'dlg', '2da', 'tlk', 'mdl', 'ncs', 'tpc', 'wav'"
                        ),
                    },
                    "field_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "For GFF resources only: dot-separated field paths to extract "
                            "(e.g. ['FirstName', 'SkillList.0.Rank']). "
                            "Omit to return the full tree."
                        ),
                    },
                },
                "required": ["game", "resref", "restype"],
            },
        }
    ]


# ── Handler ───────────────────────────────────────────────────────────────────

async def handle_get_resource(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Universal resource reader.

    Dispatches to a type-specific decoder; callers see only plain content.
    Adding support for a new restype requires adding one decoder function —
    no changes to callers, registry, or tool name/description (open/closed).
    """
    game_alias: str = arguments.get("game", "")
    resref: str = arguments.get("resref", "").strip()
    restype: str = arguments.get("restype", "").strip().lower().lstrip(".")
    field_paths: Optional[List[str]] = arguments.get("field_paths")

    game = resolve_game(game_alias)
    if game is None:
        return json_content({"error": "game must be 'k1' or 'k2'."})
    if not resref:
        return json_content({"error": "resref is required."})
    if not restype:
        return json_content({"error": "restype is required."})

    try:
        installation = load_installation(game)
    except Exception as exc:
        return json_content({"error": f"Could not load installation: {exc}"})

    entry = installation.get_resource(resref, restype)
    if entry is None:
        return json_content({"error": f"Resource '{resref}.{restype}' not found in {game_alias} installation."})

    data: bytes = entry.data

    # ── Decode based on restype ──────────────────────────────────────────────
    decoder = _DECODERS.get(restype, _decode_binary)
    try:
        content = decoder(resref, restype, data, field_paths=field_paths, installation=installation)
    except Exception as exc:
        content = {"error": f"Decode error for {resref}.{restype}: {exc}"}

    return json_content({
        "resref": resref,
        "restype": restype,
        "source": entry.source,
        "size_bytes": len(data),
        "content": content,
    })


# ── Type-specific decoders ────────────────────────────────────────────────────
# Each decoder: (resref, restype, bytes, *, field_paths, installation) → Any
# Adding a new format = adding one function + one entry in _DECODERS.
# No other code changes required (open/closed principle, Constantine §12).

_GFF_TYPES = {
    "utc", "utp", "utd", "uti", "utm", "uts", "utt", "ute", "utw",
    "dlg", "are", "git", "ifo", "jrl", "fac", "gic", "nfo", "bic",
    "gff", "pth", "res",
}


def _decode_gff(
    resref: str,
    restype: str,
    data: bytes,
    *,
    field_paths: Optional[List[str]] = None,
    **_kw,
) -> Any:
    from pykotor.resource.formats.gff.gff_auto import read_gff  # noqa: PLC0415
    from kotormcp.tools.gffdata import _gff_struct_to_dict  # noqa: PLC0415
    gff = read_gff(BytesIO(data))
    tree = _gff_struct_to_dict(gff.root, max_depth=6, max_fields=300)
    if field_paths:
        return {fp: _extract_path(tree, fp) for fp in field_paths}
    return tree


def _decode_2da(
    resref: str,
    restype: str,
    data: bytes,
    **_kw,
) -> Any:
    from pykotor.resource.formats.twoda.twoda_auto import read_2da  # noqa: PLC0415
    table = read_2da(BytesIO(data))
    headers = table.get_headers()
    rows = []
    for i in range(table.get_height()):
        row = {"_row": i}
        for h in headers:
            try:
                row[h] = table.get_cell(i, h)
            except Exception:
                row[h] = ""
        rows.append(row)
    return {"columns": headers, "row_count": len(rows), "rows": rows}


def _decode_tlk(
    resref: str,
    restype: str,
    data: bytes,
    *,
    installation=None,
    **_kw,
) -> Any:
    """
    TLK decode: if this IS the dialog.tlk (resref == 'dialog'), parse directly.
    The installation port's talktable_string handles strref resolution for
    callers who already have the installation loaded.
    """
    try:
        from pykotor.resource.formats.tlk.tlk_auto import read_tlk  # noqa: PLC0415
        tlk = read_tlk(BytesIO(data))
        entries = []
        # Surface first 200 entries to keep response manageable
        limit = min(tlk.get_size(), 200)
        for i in range(limit):
            try:
                entry = tlk.get(i)
                entries.append({"strref": i, "text": entry.text, "sound": entry.sound_resref})
            except Exception:
                entries.append({"strref": i, "text": "", "sound": ""})
        return {
            "total_entries": tlk.get_size(),
            "returned": len(entries),
            "entries": entries,
        }
    except Exception as exc:
        return {"error": str(exc)}


def _decode_mdl(
    resref: str,
    restype: str,
    data: bytes,
    *,
    installation=None,
    **_kw,
) -> Any:
    """MDL: return structural summary via GhostRigger ModelAnalyzer."""
    try:
        from src.core.mdl_parser import MDLBinaryParser  # noqa: PLC0415
        # Try to find .mdx alongside
        mdx = b""
        if installation is not None:
            mdx_entry = installation.get_resource(resref, "mdx")
            if mdx_entry:
                mdx = mdx_entry.data
        parser = MDLBinaryParser(data, mdx)
        model = parser.parse()
        nodes = [n.name for n in model.nodes] if hasattr(model, "nodes") else []
        anims = [a.name for a in model.animations] if hasattr(model, "animations") else []
        return {
            "classification": getattr(model, "classification", "unknown"),
            "supermodel": getattr(model, "supermodel", None),
            "node_count": len(nodes),
            "nodes": nodes[:50],
            "animation_count": len(anims),
            "animations": anims[:50],
        }
    except Exception as exc:
        return {"summary": "MDL binary", "size_bytes": len(data), "parse_error": str(exc)}


def _decode_ncs(
    resref: str,
    restype: str,
    data: bytes,
    **_kw,
) -> Any:
    """NCS (compiled NWScript): return hex dump of header + size."""
    header_hex = data[:32].hex() if len(data) >= 32 else data.hex()
    return {
        "format": "NCS compiled NWScript bytecode",
        "size_bytes": len(data),
        "header_hex": header_hex,
        "note": "Use kotor_decompile_function or a NWScript decompiler to read source.",
    }


def _decode_nss(
    resref: str,
    restype: str,
    data: bytes,
    **_kw,
) -> Any:
    """NSS (NWScript source): return as plain text."""
    try:
        return {"source": data.decode("utf-8", errors="replace")}
    except Exception:
        return {"source": data.decode("latin-1", errors="replace")}


def _decode_text(
    resref: str,
    restype: str,
    data: bytes,
    **_kw,
) -> Any:
    try:
        return {"text": data.decode("utf-8", errors="replace")}
    except Exception:
        return {"text": data.decode("latin-1", errors="replace")}


def _decode_binary(
    resref: str,
    restype: str,
    data: bytes,
    **_kw,
) -> Any:
    return {
        "encoding": "base64",
        "size_bytes": len(data),
        "data": base64.b64encode(data[:4096]).decode(),
        "truncated": len(data) > 4096,
    }


# Register all decoders (restype → decoder fn)
_DECODERS: Dict[str, Any] = {}

# GFF family
for _t in _GFF_TYPES:
    _DECODERS[_t] = _decode_gff

# 2DA
_DECODERS["2da"] = _decode_2da

# TLK
_DECODERS["tlk"] = _decode_tlk

# MDL / MDX
_DECODERS["mdl"] = _decode_mdl
_DECODERS["mdx"] = _decode_binary  # raw geometry, not useful as text

# Scripts
_DECODERS["ncs"] = _decode_ncs
_DECODERS["nss"] = _decode_nss

# Text-ish formats
for _t in ("txt", "ini", "set", "cfg", "wav_info"):
    _DECODERS[_t] = _decode_text


# ── Path extraction helper ────────────────────────────────────────────────────

def _extract_path(tree: Any, path: str) -> Any:
    """
    Walk a decoded GFF tree by dot-separated path.
    e.g. 'SkillList.0.Rank' → tree['SkillList'][0]['Rank']
    """
    parts = path.split(".")
    cur = tree
    for part in parts:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur
