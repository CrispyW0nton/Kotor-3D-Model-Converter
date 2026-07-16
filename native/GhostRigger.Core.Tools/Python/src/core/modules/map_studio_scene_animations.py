"""Read authored scene animations from a module's OnEnter NCS script.

KOTOR ambient scenes (207TEL's seated cantina crowd) are not stored as GIT
data — the module's OnEnter script assigns each NPC an animation by tag:
``AssignCommand(GetObjectByTag("SittingBith"), ActionPlayAnimation(206))``.
PIE does not run NWScript, but it can read the compiled script's intent:
this module disassembles the OnEnter NCS, extracts every (tag ->
ActionPlayAnimation constant) pair, and resolves each constant to candidate
clip names so PIE can play the right animation on each creature.

This is intent extraction, not script execution: conditional logic, loops,
and computed tags are not followed — only the direct
``ActionPlayAnimation`` on a ``GetObjectByTag`` literal is recovered.
"""

from __future__ import annotations

import io
from typing import Any

# KOTOR nwscript ACTION routine numbers (K1 and K2 share these).
_ROUTINE_ACTION_PLAY_ANIMATION = 40
_ROUTINE_GET_OBJECT_BY_TAG = 200

# ActionPlayAnimation animation constant -> ordered candidate clip names. The
# first clip that resolves in a creature's model/supermodel is played, which
# absorbs per-model naming differences (S_Female02 has "sit", S_Male02 has
# "sitdown"). Only the ambient looping animations modules actually assign are
# mapped; unknown constants fall back to a safe idle.
SCENE_ANIMATION_CLIP_CANDIDATES: dict[int, tuple[str, ...]] = {
    0: ("pause1", "cpause1"),            # ANIMATION_LOOPING_PAUSE
    1: ("pause2", "pause1"),             # ANIMATION_LOOPING_PAUSE2
    2: ("listen", "pause1"),             # ANIMATION_LOOPING_LISTEN
    3: ("meditate", "meditatesit"),      # ANIMATION_LOOPING_MEDITATE
    4: ("worship", "pause1"),            # ANIMATION_LOOPING_WORSHIP
    5: ("talk", "tlknorm", "pause1"),    # ANIMATION_LOOPING_TALK_NORMAL
    6: ("talk", "tlkplead"),             # ANIMATION_LOOPING_TALK_PLEADING
    7: ("talk", "tlkforce"),             # ANIMATION_LOOPING_TALK_FORCEFUL
    8: ("talk", "tlklaugh"),             # ANIMATION_LOOPING_TALK_LAUGHING
    9: ("talk", "tlksad"),               # ANIMATION_LOOPING_TALK_SAD
    10: ("getlow", "pause1"),            # ANIMATION_LOOPING_GET_LOW
    11: ("getmid", "pause1"),            # ANIMATION_LOOPING_GET_MID
    12: ("pause3", "pause1"),            # ANIMATION_LOOPING_PAUSE_TIRED
    13: ("pausedrunk", "pause1"),        # ANIMATION_LOOPING_PAUSE_DRUNK
    14: ("deadbody", "dead"),            # ANIMATION_LOOPING_DEAD_FRONT
    28: ("choke", "pause1"),             # ANIMATION_LOOPING_CHOKE
    205: ("sit", "cesit", "sitcross", "sitchair", "meditatesit", "sitdown"),  # SIT_CHAIR
    206: ("sit", "sitdrink", "cesit", "sitcross", "sitdown"),                 # SIT_CHAIR (drink/talk)
}


def scene_animation_clip_candidates(constant: int) -> tuple[str, ...]:
    """Candidate clip names for one ActionPlayAnimation constant."""

    return SCENE_ANIMATION_CLIP_CANDIDATES.get(int(constant), ("pause1", "cpause1"))


def _instruction_type_name(instruction: Any) -> str:
    ins_type = getattr(instruction, "ins_type", None)
    return str(getattr(ins_type, "name", "") or "")


def _action_routine(instruction: Any) -> int | None:
    if _instruction_type_name(instruction) != "ACTION":
        return None
    args = tuple(getattr(instruction, "args", ()) or ())
    return int(args[0]) if args else None


def extract_scene_animation_intents(ncs_bytes: bytes) -> dict[str, int]:
    """Return ``{creature_tag_lower: animation_constant}`` from an OnEnter NCS.

    Matches the compiled shape of
    ``ActionPlayAnimation(GetObjectByTag("<tag>"), <const>, ...)``: an
    ``ACTION`` on routine 40 preceded by the animation ``CONSTI`` and, earlier,
    a ``GetObjectByTag`` (routine 200) whose tag is the nearest preceding
    ``CONSTS`` literal. Later assignments to the same tag win.
    """

    if not ncs_bytes:
        return {}
    try:
        from pykotor.resource.formats.ncs import NCSBinaryReader

        ncs = NCSBinaryReader(io.BytesIO(bytes(ncs_bytes))).load()
    except Exception:
        return {}
    instructions = list(getattr(ncs, "instructions", ()) or ())
    intents: dict[str, int] = {}
    for index, instruction in enumerate(instructions):
        if _action_routine(instruction) != _ROUTINE_ACTION_PLAY_ANIMATION:
            continue
        # Nearest preceding CONSTI is the animation constant.
        animation: int | None = None
        for j in range(index - 1, max(-1, index - 12), -1):
            if _action_routine(instructions[j]) == _ROUTINE_ACTION_PLAY_ANIMATION:
                break
            if _instruction_type_name(instructions[j]) == "CONSTI":
                args = tuple(getattr(instructions[j], "args", ()) or ())
                if args:
                    animation = int(args[0])
                break
        if animation is None:
            continue
        # Nearest preceding GetObjectByTag, then its tag CONSTS literal.
        tag: str | None = None
        for j in range(index - 1, max(-1, index - 20), -1):
            if _action_routine(instructions[j]) == _ROUTINE_GET_OBJECT_BY_TAG:
                for k in range(j - 1, max(-1, j - 6), -1):
                    if _instruction_type_name(instructions[k]) == "CONSTS":
                        args = tuple(getattr(instructions[k], "args", ()) or ())
                        if args:
                            tag = str(args[0])
                        break
                break
        if tag:
            intents[tag.strip().lower()] = animation
    return intents


def module_onenter_script_resref(ifo_gff_root: Any) -> str:
    """Return the OnEnter script resref from a module IFO (Mod_OnClientEntr)."""

    if ifo_gff_root is None:
        return ""
    for field in ("Mod_OnClientEntr", "Mod_OnModLoad", "Mod_OnModStart"):
        try:
            value = str(ifo_gff_root.acquire(field, "") or "").strip()
        except Exception:
            value = ""
        if value:
            return value
    return ""


def build_module_scene_animations(
    *,
    onenter_ncs_bytes: bytes,
) -> dict[str, tuple[str, ...]]:
    """Map creature tags to candidate animation clips from an OnEnter NCS."""

    intents = extract_scene_animation_intents(onenter_ncs_bytes)
    return {tag: scene_animation_clip_candidates(constant) for tag, constant in intents.items()}


__all__ = [
    "SCENE_ANIMATION_CLIP_CANDIDATES",
    "scene_animation_clip_candidates",
    "extract_scene_animation_intents",
    "module_onenter_script_resref",
    "build_module_scene_animations",
]
