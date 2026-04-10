"""
Shared state for KotorMCP — backward-compatible bridge layer.

Design note (Khononov, "Balancing Coupling in Software Design"):
  This module previously held a module-level INSTALLATIONS dict (Common Coupling —
  multiple callers sharing mutable global state).  It has been refactored to a
  thin bridge that delegates to PyKotorRegistryAdapter (Contract Coupling).

  Existing callers (installation.py, discovery.py, gamedata.py) continue to
  import resolve_game / load_installation / iter_candidate_paths from here
  without modification — the coupling point is the function signatures, which
  are the stable public contract.

  New code should depend directly on InstallationRegistryPort via injection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, Optional

from kotormcp.adapters import (
    PyKotorRegistryAdapter,
    get_default_registry,
    _PYKOTOR_AVAILABLE,  # re-exported for compatibility
)

if TYPE_CHECKING:
    from kotormcp.ports import InstallationPort


# ── Backward-compatible surface ───────────────────────────────────────────────

# This dict-like view is kept for any code that reads INSTALLATIONS directly.
# It reads through to the default registry's cache, so it reflects reality
# without requiring callers to change.
class _InstallationsView:
    """Read-through view of the default registry's installation cache."""

    def __len__(self):
        return len(get_default_registry()._cache)

    def __contains__(self, item):
        return item in get_default_registry()._cache

    def __iter__(self):
        return iter(get_default_registry()._cache)

    def items(self):
        return get_default_registry()._cache.items()

    def get(self, key, default=None):
        return get_default_registry()._cache.get(key, default)

    def clear(self):
        get_default_registry().clear()


INSTALLATIONS = _InstallationsView()

# Re-export for callers that do: from kotormcp.state import DEFAULT_PATH_CACHE
from kotormcp.adapters import _DEFAULT_PATH_CACHE as DEFAULT_PATH_CACHE  # noqa: E402
from kotormcp.adapters import _ENV_HINTS as ENV_HINTS  # noqa: E402
from kotormcp.adapters import _GAME_ALIASES as GAME_ALIASES  # noqa: E402


# ── Public functions ──────────────────────────────────────────────────────────

def resolve_game(label: Optional[str]):
    """Resolve game alias (k1, k2, tsl, etc.) to Game enum. Returns None if unknown."""
    return get_default_registry().resolve(label)


def iter_candidate_paths(game, explicit: Optional[str]) -> Iterator:
    """Yield candidate installation paths: explicit, then env vars, then defaults."""
    return get_default_registry().iter_candidate_paths(game, explicit)


def load_installation(game, explicit_path: Optional[str] = None) -> "InstallationPort":
    """Load and cache an installation for the given game."""
    return get_default_registry().load(game, explicit_path)


def clear_cache() -> None:
    """Clear the installation cache (useful for testing)."""
    get_default_registry().clear()
