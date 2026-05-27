"""Import-time normalisation rules for known shipped MDL anomalies.

These rules deliberately run before skin weights bind to GhostRigger's model
nodes. Keep renderer-specific fixes out of this module: the purpose here is to
make imported model data coherent once, then let OpenGL, D3D, export, and
diagnostics consume the same corrected representation.
"""

from __future__ import annotations

from typing import Any, Mapping


def _model_root_name(node: Any) -> str:
    current = node
    seen: set[int] = set()
    while getattr(current, "parent", None) is not None:
        marker = id(current)
        if marker in seen:
            break
        seen.add(marker)
        current = current.parent
    return str(getattr(current, "name", "") or "")


def apply_known_skin_bone_map_normalisations(
    node: Any,
    skin: Any,
    id_to_pknode: Mapping[int, object],
) -> None:
    """Correct known stock skin palette anomalies before vertex weights bind."""

    _normalise_bastila_headless_body_torso(node, skin, id_to_pknode)


def _normalise_bastila_headless_body_torso(
    node: Any,
    skin: Any,
    id_to_pknode: Mapping[int, object],
) -> None:
    """Protect the stock P_BastilaBB lower-limb torso palette correction.

    The shipped K1/K2 `P_BastilaBB` torso skin stores lower-limb vertex clusters
    that match `P_BastilaBB02`, Juhani, and other party bodies, but its compact
    `bone_indices` palette names for those slots are transposed to foot/flap
    helpers. The raw `bonemap` still references the missing leg-chain nodes.

    Normalising the compact palette here keeps the renderer on the normal G5
    qBone/tBone path and prevents export/diagnostic code from seeing a different
    skeleton mapping than the viewport.
    """

    root_name = _model_root_name(node).lower()
    skin_name = str(getattr(node, "name", "") or "").lower()
    if root_name != "p_bastilabb" or skin_name != "torso":
        return

    expected_transposed_slots = {
        6: "rfoot_g",
        7: "lfoot_g",
        10: "rfootT_g",
        11: "RLegFlap01",
        12: "Frntflap",
        13: "lfootT_g",
        14: "LLegFlap",
        15: "rthigh_g",
    }
    bone_map = list(getattr(node, "bone_map", []) or [])
    if len(bone_map) < 16:
        return
    for slot, name in expected_transposed_slots.items():
        if str(bone_map[slot] or "").lower() != name.lower():
            return

    bonemap_names = set()
    for raw in getattr(skin, "bonemap", None) or []:
        try:
            node_id = int(raw)
        except (TypeError, ValueError):
            continue
        if node_id < 0 or node_id == 0xFFFF:
            continue
        pk_node = id_to_pknode.get(node_id)
        if pk_node is not None:
            bonemap_names.add(str(getattr(pk_node, "name", "") or "").lower())

    # Require the anomaly's distinctive non-empty bonemap evidence so similarly
    # named custom models do not inherit this stock-model correction by accident.
    if not {
        "lthigh_g",
        "lshin_g",
        "rshin_g",
        "rfoot_g",
        "rfoott_g",
        "llegflap",
        "rthigh_g",
    }.issubset(bonemap_names):
        return

    protected_remap = {
        6: "lthigh_g",
        7: "rthigh_g",
        10: "lshin_g",
        11: "lfoot_g",
        12: "lfootT_g",
        13: "rshin_g",
        14: "rfoot_g",
        15: "rfootT_g",
    }
    for slot, bone_name in protected_remap.items():
        node.bone_map[slot] = bone_name
    setattr(node, "_gr_bone_map_override", "p_bastilabb_torso_lower_limb")


__all__ = ["apply_known_skin_bone_map_normalisations"]
