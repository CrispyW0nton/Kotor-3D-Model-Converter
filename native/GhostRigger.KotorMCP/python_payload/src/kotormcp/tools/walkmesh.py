"""Walkmesh (BWM/WOK) tools: validation diagram for LLM context.

Ported from OldRepublicDevs/KotorMCP (Tools/KotorMCP/src/kotormcp/tools/walkmesh.py)
and adapted to GhostRigger's port-contract layer (ports.py / adapters.py).

Design note (Constantine, Transform Analysis):
  Single-input single-output transform: (game + resref) → plain-text diagram.
  No UI context embedded in the tool name or description.

Improvements over upstream (from PyKotor test_bwm.py review, v3.4.1):
  - read_bwm() receives raw bytes (its actual accepted type), not BytesIO
  - resref sanitisation strips both .wok AND .bwm suffixes
  - Stats header (face_count, walkable_count, edge_count) prepended to diagram
  - JSON-safe error serialisation for all error paths

Tools exposed:
  kotor_walkmesh_validation_diagram — text validation diagram for a BWM/WOK file
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from kotormcp.state import load_installation, resolve_game


def _err(msg: str) -> Dict[str, Any]:
    """Return a canonical error result in {"type":"text","text":"<json>"} format."""
    return {"type": "text", "text": json.dumps({"error": msg})}


def get_tools() -> List[Dict[str, Any]]:
    """Return tool definitions for walkmesh validation (read-only)."""
    return [
        {
            "name": "kotor_walkmesh_validation_diagram",
            "description": (
                "Get a text validation diagram for a walkmesh (BWM/WOK): perimeter, "
                "transitions, outer boundary. Use when you need to understand an area's "
                "walkable layout, door links, or boundary for modding or debugging. "
                "Read-only; returns plain text (no ANSI by default)."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "description": "Game alias: k1 or k2"},
                    "resref": {
                        "type": "string",
                        "description": "Walkmesh resref (e.g. 203tell for 203tell.wok)",
                    },
                    "use_color": {
                        "type": "boolean",
                        "default": False,
                        "description": "If true, include ANSI color codes (terminal only); default false for plain MCP text.",
                    },
                },
                "required": ["game", "resref"],
            },
        },
    ]


# ── Handler ───────────────────────────────────────────────────────────────────

async def handle_walkmesh_validation_diagram(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Load BWM from installation and return validation diagram lines as plain text."""
    game_str = arguments.get("game")
    resref = arguments.get("resref")
    if not game_str or not resref:
        return _err("game and resref are required")

    game = resolve_game(game_str)
    if game is None:
        return _err("Unknown game alias. Use k1 or k2.")

    try:
        from pykotor.resource.formats.bwm import read_bwm  # type: ignore[import]
        from pykotor.tools.walkmesh_render_diagram import render_bwm_validation_diagram_lines  # type: ignore[import]
    except ImportError as e:
        return _err(f"pykotor not available: {e}")

    try:
        installation = load_installation(game)
        # Strip both .wok and .bwm suffixes (PyKotor supports both extensions)
        resref_clean = resref.strip().lower().removesuffix(".wok").removesuffix(".bwm")
        entry = installation.get_resource(resref_clean, "WOK")
        if entry is None:
            # Fallback to BWM (interior / door walkmesh)
            entry = installation.get_resource(resref_clean, "BWM")
        if entry is None:
            return _err(f"Walkmesh {resref_clean}.wok/.bwm not found.")

        # Pass raw bytes directly — read_bwm(source) accepts bytes/bytearray/str/Path
        bwm = read_bwm(entry.data)
        use_color = bool(arguments.get("use_color", False))
        lines = render_bwm_validation_diagram_lines(bwm, use_color=use_color)

        # Prepend a stats header so LLM has quick numeric context without parsing ASCII
        try:
            face_count = len(bwm.faces)
            walkable_count = len(bwm.walkable_faces())
            edge_count = len(bwm.edges())
            stats_line = (
                f"# stats: {face_count} faces, "
                f"{walkable_count} walkable, "
                f"{edge_count} perimeter edges"
            )
            lines = [stats_line] + lines
        except Exception:
            pass  # stats are best-effort; don't let them break the output

        return {"type": "text", "text": "\n".join(lines)}
    except Exception as e:
        return _err(str(e))
