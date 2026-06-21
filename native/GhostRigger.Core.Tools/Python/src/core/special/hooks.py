"""Canonical KotOR character attachment hook names.

These constants mirror the runtime attachment points used by Odyssey-style
character models: weapons and equipment are parented to named nodes, not
skinned to the body mesh.
"""

from __future__ import annotations

BODY_HOOKS = frozenset({
    "headhook",
    "rhand",
    "lhand",
    "impact",
    "impact_bolt",
    "belt_g",
})

HEAD_HOOKS = frozenset({
    "gogglehook",
    "maskhook",
})

WEAPON_HOOKS = frozenset({
    "rhand",
    "lhand",
    "impact_bolt",
    "lightsaberhook",
})

ALL_CHARACTER_HOOKS = BODY_HOOKS | HEAD_HOOKS | WEAPON_HOOKS | frozenset({
    "camerahook",
    "freelookhook",
    "deflecthook",
    "handconjure",
    "headconjure",
    "revmask1hook",
    "revmask2hook",
})


def is_attachment_hook(name: str) -> bool:
    return str(name or "").strip().lower() in ALL_CHARACTER_HOOKS

