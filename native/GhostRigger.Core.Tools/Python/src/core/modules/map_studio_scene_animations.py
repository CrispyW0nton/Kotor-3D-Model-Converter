"""Read authored scene animations from a module's OnEnter NCS script.

KOTOR ambient scenes (207TEL's seated cantina crowd) are not stored as GIT
data — the module's OnEnter script assigns each NPC an animation by tag and
occurrence::

    AssignCommand(GetObjectByTag("SittingBith", 1), ActionPlayAnimation(37))

PIE does not run NWScript, but it can read the compiled script's intent. This
module extracts every ``((tag, nNth) -> ActionPlayAnimation constant)`` pair
and resolves supported creature constants to ordered clip candidates.

This is intent extraction, not script execution: conditional logic, loops,
computed tags, and non-creature targets are not followed.
"""

from __future__ import annotations

import io
from typing import Any, Mapping

SceneAnimationKey = tuple[str, int]


class MapStudioSceneAnimationMap(dict[SceneAnimationKey, tuple[str, ...]]):
    """Animation candidates plus auditable OnEnter source provenance.

    This remains a normal mapping so existing callers can pass it directly to
    the creature planner. ``intents`` deliberately retains constants whose
    creature clip mapping is unsupported; an empty candidate tuple therefore
    means "authored but unresolved", never "use the idle constant".
    """

    def __init__(
        self,
        animations: Mapping[SceneAnimationKey, tuple[str, ...]] | None = None,
        *,
        intents: Mapping[SceneAnimationKey, int] | None = None,
        script_resref: str = "",
        source: str = "",
        source_sha256: str = "",
    ) -> None:
        super().__init__(animations or {})
        self.intents = dict(intents or {})
        self.script_resref = str(script_resref or "")
        self.source = str(source or "")
        self.source_sha256 = str(source_sha256 or "")


# KOTOR nwscript ACTION routine numbers (K1 and K2 share these).
_ROUTINE_ACTION_PLAY_ANIMATION = 40
_ROUTINE_GET_OBJECT_BY_TAG = 200

# K2 nwscript animation constant -> ordered creature-model clip candidates.
# Specific inherited clips precede generic aliases. Placeable constants
# 205/206 intentionally remain unsupported for creature actors instead of
# being mislabeled as sit-chair animations.
SCENE_ANIMATION_CLIP_CANDIDATES: dict[int, tuple[str, ...]] = {
    0: ("pause1", "cpause1"),
    1: ("pause2", "pause1"),
    2: ("listen", "pause1"),
    3: ("meditate", "meditatesit"),
    4: ("worship", "pause1"),
    5: ("tlknorm", "talk", "pause1"),
    6: ("tlkplead", "talk", "tlknorm"),
    7: ("tlkforce", "talk", "tlknorm"),
    8: ("tlklaugh", "talk", "tlknorm"),
    9: ("tlksad", "talk", "tlknorm"),
    10: ("getlow", "pause1"),
    11: ("getmid", "pause1"),
    12: ("pausetrd", "pause3", "pause1"),
    13: ("pausedrunk", "pause1"),
    14: ("flirt", "tlkflirt", "pause1"),  # ANIMATION_LOOPING_FLIRT
    28: ("listeninj", "listen", "pause1"),  # ANIMATION_LOOPING_LISTEN_INJURED
    # K2 routes these constants to animations.2da rows 316-318. The actual
    # humanoid supermodel slots are persistent chair loops whose root pose
    # matches the endpoint of ``sitdown``; ``sit`` is a different transition
    # (Sit_To_Meditate) and visibly puts authored chair actors on the floor.
    36: ("animloop01",),  # ANIMATION_LOOPING_SIT_CHAIR -> row 316
    37: ("animloop02", "animloop01"),  # ..._SIT_CHAIR_DRINK -> row 317
    38: ("animloop03", "animloop01"),  # ..._SIT_CHAIR_PAZAK -> row 318
    39: ("animloop01",),  # ..._SIT_CHAIR_COMP1 -> row 316
    40: ("animloop01",),  # ..._SIT_CHAIR_COMP2 -> row 316
    205: (),  # ANIMATION_PLACEABLE_ANIMLOOP02
    206: (),  # ANIMATION_PLACEABLE_ANIMLOOP03
}

def scene_animation_clip_candidates(constant: int) -> tuple[str, ...]:
    """Candidate creature clips, or empty when the constant is unsupported."""

    return SCENE_ANIMATION_CLIP_CANDIDATES.get(int(constant), ())
def _instruction_type_name(instruction: Any) -> str:
    ins_type = getattr(instruction, "ins_type", None)
    return str(getattr(ins_type, "name", "") or "")


def _action_routine(instruction: Any) -> int | None:
    if _instruction_type_name(instruction) != "ACTION":
        return None
    args = tuple(getattr(instruction, "args", ()) or ())
    return int(args[0]) if args else None


def extract_scene_animation_intents_from_instructions(
    instructions: list[Any] | tuple[Any, ...],
) -> dict[SceneAnimationKey, int]:
    """Recover literal ``(tag, nNth)`` animation assignments from NCS ops."""

    rows = list(instructions or ())
    intents: dict[SceneAnimationKey, int] = {}
    for index, instruction in enumerate(rows):
        if _action_routine(instruction) != _ROUTINE_ACTION_PLAY_ANIMATION:
            continue

        animation: int | None = None
        for j in range(index - 1, max(-1, index - 12), -1):
            if _action_routine(rows[j]) == _ROUTINE_ACTION_PLAY_ANIMATION:
                break
            if _instruction_type_name(rows[j]) == "CONSTI":
                args = tuple(getattr(rows[j], "args", ()) or ())
                if args:
                    animation = int(args[0])
                break
        if animation is None:
            continue

        tag: str | None = None
        nth = 0
        for j in range(index - 1, max(-1, index - 20), -1):
            if _action_routine(rows[j]) != _ROUTINE_GET_OBJECT_BY_TAG:
                continue
            tag_index: int | None = None
            for k in range(j - 1, max(-1, j - 6), -1):
                if _instruction_type_name(rows[k]) == "CONSTS":
                    args = tuple(getattr(rows[k], "args", ()) or ())
                    if args:
                        tag = str(args[0])
                        tag_index = k
                    break
            if tag_index is not None:
                # Compiler shape: CONSTI(nNth), CONSTS(tag), ACTION(200, 2).
                for k in range(tag_index - 1, max(-1, tag_index - 4), -1):
                    if _instruction_type_name(rows[k]) == "CONSTI":
                        args = tuple(getattr(rows[k], "args", ()) or ())
                        if args:
                            nth = max(0, int(args[0]))
                        break
            break

        clean_tag = str(tag or "").strip().lower()
        if clean_tag:
            intents[(clean_tag, nth)] = animation
    return intents


def extract_scene_animation_intents(ncs_bytes: bytes) -> dict[SceneAnimationKey, int]:
    """Return ``{(tag_lower, nNth): constant}`` from an OnEnter NCS.

    Matches the compiled shape of a direct ``ActionPlayAnimation`` assignment
    to a literal ``GetObjectByTag`` target. Later assignments to the same exact
    tag occurrence win.
    """

    if not ncs_bytes:
        return {}
    try:
        from pykotor.resource.formats.ncs import NCSBinaryReader

        ncs = NCSBinaryReader(io.BytesIO(bytes(ncs_bytes))).load()
    except Exception:
        return {}
    return extract_scene_animation_intents_from_instructions(
        list(getattr(ncs, "instructions", ()) or ())
    )


def module_onenter_script_resref(ifo_gff_root: Any) -> str:
    """Return the OnEnter script resref from a module IFO."""

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
    script_resref: str = "",
    source: str = "",
    source_sha256: str = "",
) -> MapStudioSceneAnimationMap:
    """Map creature tag occurrences to clips and retain source provenance."""

    intents = extract_scene_animation_intents(onenter_ncs_bytes)
    return MapStudioSceneAnimationMap(
        {key: scene_animation_clip_candidates(constant) for key, constant in intents.items()},
        intents=intents,
        script_resref=script_resref,
        source=source,
        source_sha256=source_sha256,
    )


__all__ = [
    "MapStudioSceneAnimationMap",
    "SCENE_ANIMATION_CLIP_CANDIDATES",
    "SceneAnimationKey",
    "build_module_scene_animations",
    "extract_scene_animation_intents",
    "extract_scene_animation_intents_from_instructions",
    "module_onenter_script_resref",
    "scene_animation_clip_candidates",
]
