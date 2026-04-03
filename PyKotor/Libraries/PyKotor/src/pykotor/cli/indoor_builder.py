"""Shared helpers for indoor map building and extraction in Pykotorcli.

This module provides CLI-friendly wrappers around the HolocronToolset indoor map functionality.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykotor.common.misc import Game
from pykotor.extract.installation import Installation
from utility.string_util import normalize_string

if TYPE_CHECKING:
    from pathlib import Path


K1_ALIASES = ("k1", "kotor1", "kotor 1")
K2_ALIASES = ("k2", "kotor2", "kotor 2", "tsl")


def parse_game_argument(game_arg: str | None) -> Game | None:
    """Parse game argument string to Game enum.

    Args:
    ----
        game_arg: Game argument string (k1, k2, kotor1, kotor2, etc.)

    Returns:
    -------
        Game enum or None if invalid/not provided
    """
    if not game_arg:
        return None

    game_lower = normalize_string(game_arg)
    if game_lower in K1_ALIASES:
        return Game.K1
    if game_lower in K2_ALIASES:
        return Game.K2

    return None


def determine_game_from_installation(installation_path: Path) -> Game | None:
    """Determine game type from installation path.

    Args:
    ----
        installation_path: Path to installation directory

    Returns:
    -------
        Game enum or None if cannot determine
    """
    try:
        installation = Installation(installation_path)
        return installation.game()
    except Exception:
        return None


def resolve_game_argument(game_arg: str | None, installation_path: Path) -> Game | None:
    """Resolve game from explicit argument first, then by probing installation."""
    explicit = parse_game_argument(game_arg)
    if explicit is not None:
        return explicit
    return determine_game_from_installation(installation_path)
