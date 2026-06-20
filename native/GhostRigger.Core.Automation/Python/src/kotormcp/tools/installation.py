"""Installation management tools: detect, load, info."""

from __future__ import annotations

from typing import Any, Dict, List

from kotormcp.state import load_installation, resolve_game
from kotormcp.utils import json_content
from kotormcp.schemas import LoadInstallationInput


def get_tools() -> List[Dict[str, Any]]:
    """Return tool definitions for installation management."""
    return [
        {
            "name": "detectInstallations",
            "description": (
                "Discover candidate K1/K2 installation paths (env vars and platform defaults). Read-only."
            ),
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "loadInstallation",
            "description": (
                "Activate a KOTOR installation in memory for subsequent tools. Read-only; does not modify disk."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "description": "Game alias: k1, k2, or tsl"},
                    "path": {"type": "string", "description": "Optional absolute path override"},
                },
                "required": ["game"],
            },
        },
        {
            "name": "kotor_installation_info",
            "description": (
                "Return installation summary: path, game, valid, errors, missing files, module/override counts."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "description": "Game alias: k1, k2, or tsl"},
                    "path": {"type": "string", "description": "Optional absolute path override"},
                },
                "required": ["game"],
            },
        },
    ]


async def handle_detect_installations(_arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Enumerate candidate paths for K1 and K2."""
    try:
        from pykotor.common.misc import Game  # noqa: PLC0415
    except ImportError:
        return json_content({"error": "pykotor not installed"})

    from kotormcp.adapters import get_default_registry  # noqa: PLC0415
    registry = get_default_registry()

    payload: Dict[str, Any] = {}
    for game in (Game.K1, Game.K2):
        default_keys = registry.default_path_keys(game)
        details = []
        for candidate in registry.iter_candidate_paths(game, None):
            key = str(candidate).lower()
            details.append({
                "path": str(candidate),
                "exists": candidate.is_dir(),
                "label": "default" if key in default_keys else "env",
            })
        payload[game.name] = details
    return json_content(payload)


async def handle_load_installation(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Load and cache an installation for the given game."""
    inp = LoadInstallationInput.model_validate(arguments)
    game = resolve_game(inp.game)
    if game is None:
        return json_content({"error": "Specify game as k1 or k2."})
    try:
        installation = load_installation(game, inp.path)
        return json_content({"game": installation.game_name(), "path": installation.path()})
    except Exception as exc:
        return json_content({"error": str(exc)})


async def handle_installation_info(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Return installation summary using the InstallationPort contract."""
    inp = LoadInstallationInput.model_validate(arguments)
    game = resolve_game(inp.game)
    if game is None:
        return json_content({"error": "Specify game as k1 or k2."})
    try:
        installation = load_installation(game, inp.path)
        summary: Dict[str, Any] = {
            "game": installation.game_name(),
            "path": installation.path(),
            "modules": installation.module_names(),
            "override_count": installation.override_count(),
        }
        return json_content(summary)
    except Exception as exc:
        return json_content({"error": str(exc)})
