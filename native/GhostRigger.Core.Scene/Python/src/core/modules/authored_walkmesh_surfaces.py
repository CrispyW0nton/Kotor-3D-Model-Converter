"""Map Studio walkmesh surface policy.

KOTOR WOK files store surface/material behavior as numeric IDs.  Map Studio
should expose stable authoring names instead of requiring modders to remember
that, for example, ``10`` means ``METAL`` and ``7`` means a blocking surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .module_format import NON_WALK_ID, WALKABLE_IDS, WOK_SURFACE_NAMES


@dataclass(frozen=True)
class AuthoredWalkmeshSurface:
    """One surface material available to authored room/walkmesh tools."""

    surface_id: int
    name: str
    authoring_name: str
    walkable: bool
    description: str = ""


SURFACE_DESCRIPTIONS: dict[int, str] = {
    0: "Invalid or unset surface. Do not use for authored playable floors.",
    1: "Walkable dirt floor.",
    3: "Walkable grass floor.",
    4: "Walkable stone or generic hard floor.",
    5: "Walkable wood floor.",
    6: "Walkable water surface.",
    7: "Blocking/non-walk surface for walls, pits, or barriers.",
    8: "Transparent/visual-only surface. Use for faces that should carry visual intent without normal walkable-floor meaning.",
    10: "Walkable metal floor.",
    15: "Hazard lava surface; not treated as normal walkable floor.",
    16: "Bottomless pit surface; not walkable.",
    17: "Deep water surface; not normal walkable floor.",
    18: "Door transition surface. Use only for authored doorway/transition WOK faces.",
    19: "Non-walk grass blocker surface.",
    20: "Reserved non-walk Odyssey surface material 20.",
    21: "Reserved non-walk Odyssey surface material 21.",
    22: "Reserved non-walk Odyssey surface material 22.",
}

SURFACE_AUTHORING_NAMES: dict[int, str] = {
    6: "water",
    NON_WALK_ID: "non_walk",
    8: "visual_only",
    18: "door_transition",
}

SURFACE_ALIASES: dict[str, int] = {
    "invalid": 0,
    "dirt": 1,
    "obscuring": 2,
    "grass": 3,
    "stone": 4,
    "default": 4,
    "walkable": 4,
    "wood": 5,
    "water": 6,
    "non_walk": NON_WALK_ID,
    "nonwalk": NON_WALK_ID,
    "blocked": NON_WALK_ID,
    "blocker": NON_WALK_ID,
    "wall": NON_WALK_ID,
    "transparent": 8,
    "visual": 8,
    "visual_only": 8,
    "visualonly": 8,
    "render_only": 8,
    "decorative": 8,
    "carpet": 9,
    "metal": 10,
    "puddles": 11,
    "swamp": 12,
    "mud": 13,
    "leaves": 14,
    "lava": 15,
    "bottomless_pit": 16,
    "pit": 16,
    "deep_water": 17,
    "door": 18,
    "transition": 18,
    "door_transition": 18,
    "non_walk_grass": 19,
    "nonwalk_grass": 19,
    "surface_material_20": 20,
    "surface_material_21": 21,
    "surface_material_22": 22,
}


def _key(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def authored_walkmesh_surface_palette() -> tuple[AuthoredWalkmeshSurface, ...]:
    """Return the stable Map Studio WOK surface palette."""

    surfaces: list[AuthoredWalkmeshSurface] = []
    for surface_id, name in sorted(WOK_SURFACE_NAMES.items()):
        authoring_name = SURFACE_AUTHORING_NAMES.get(int(surface_id), str(name).lower())
        surfaces.append(
            AuthoredWalkmeshSurface(
                surface_id=int(surface_id),
                name=str(name),
                authoring_name=authoring_name,
                walkable=int(surface_id) in WALKABLE_IDS,
                description=SURFACE_DESCRIPTIONS.get(int(surface_id), ""),
            )
        )
    return tuple(surfaces)


def known_walkmesh_surface_ids() -> set[int]:
    return {int(surface_id) for surface_id in WOK_SURFACE_NAMES}


def walkable_walkmesh_surface_ids() -> set[int]:
    return {int(surface_id) for surface_id in WALKABLE_IDS}


def walkmesh_surface_name(surface_id: int) -> str:
    return str(WOK_SURFACE_NAMES.get(int(surface_id), f"SURFACE_{int(surface_id)}"))


def is_known_walkmesh_surface(value: Any) -> bool:
    try:
        return resolve_walkmesh_surface_id(value) in known_walkmesh_surface_ids()
    except ValueError:
        return False


def is_walkable_walkmesh_surface(value: Any) -> bool:
    return int(resolve_walkmesh_surface_id(value)) in WALKABLE_IDS


def resolve_walkmesh_surface_id(value: Any) -> int:
    """Resolve a numeric ID or authoring alias such as ``metal`` to a WOK ID."""

    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid walkmesh surface IDs.")
    if isinstance(value, int):
        surface_id = int(value)
    else:
        text = str(value or "").strip()
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            surface_id = int(text)
        else:
            alias = _key(text)
            if alias not in SURFACE_ALIASES:
                raise ValueError(f"Unknown KOTOR walkmesh surface '{value}'.")
            surface_id = int(SURFACE_ALIASES[alias])
    if surface_id not in WOK_SURFACE_NAMES:
        raise ValueError(f"Unknown KOTOR walkmesh surface ID {surface_id}.")
    return surface_id


def require_walkable_walkmesh_surface(value: Any, *, context: str = "floor") -> int:
    """Resolve and require a normal walkable WOK material."""

    surface_id = resolve_walkmesh_surface_id(value)
    if surface_id not in WALKABLE_IDS:
        name = walkmesh_surface_name(surface_id)
        raise ValueError(f"{context} surface {surface_id} ({name}) is not walkable.")
    return surface_id


__all__ = [
    "AuthoredWalkmeshSurface",
    "authored_walkmesh_surface_palette",
    "is_known_walkmesh_surface",
    "is_walkable_walkmesh_surface",
    "known_walkmesh_surface_ids",
    "require_walkable_walkmesh_surface",
    "resolve_walkmesh_surface_id",
    "walkable_walkmesh_surface_ids",
    "walkmesh_surface_name",
]
