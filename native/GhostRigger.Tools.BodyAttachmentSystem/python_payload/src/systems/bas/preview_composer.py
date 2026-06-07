"""Runtime preview composition helpers for the Body Attachment System.

BAS preview models keep heads and equipment as socket-following layers. They
must not be merged into the body skin palette or grafted as ordinary body bones.
"""

from __future__ import annotations

import copy
from typing import Any

from src.systems.bas.attachment_alignment import normalize_bas_transform
from src.systems.bas.model_recipe import BAS_SOCKET_BY_SLOT


BAS_ATTACHMENT_SLOTS = ("head", "left_weapon", "right_weapon")


def reset_bas_model_node_traversal(model: Any) -> None:
    """Remove stale runtime traversal shims from a copied BAS preview model."""
    if model is None:
        return
    base_all_nodes = getattr(type(model), "all_nodes", None)
    if callable(base_all_nodes):
        try:
            setattr(model, "all_nodes", base_all_nodes.__get__(model, type(model)))
        except Exception:
            pass
    for attr in ("_gr_original_all_nodes", "_gr_generated_cameras", "_gr_generated_lights"):
        try:
            if hasattr(model, attr):
                delattr(model, attr)
        except Exception:
            pass


def find_model_node(model: Any, name: str):
    """Find a node by exact/case-insensitive KOTOR node name."""
    target = str(name or "").strip().lower()
    if not target or model is None:
        return None
    try:
        nodes = model.all_nodes()
    except Exception:
        nodes = []
    by_lower = {str(getattr(node, "name", "") or "").lower(): node for node in nodes}
    for candidate in (target, "rhand_g" if target == "rhand" else "", "lhand_g" if target == "lhand" else ""):
        if candidate and candidate in by_lower:
            return by_lower[candidate]
    return None


def bas_slot_for_preview_socket(socket: str, resref: str = "") -> str:
    """Map Character Builder preview socket choices onto BAS layer slots."""
    key = str(socket or "").strip().lower().replace(" ", "_")
    res = str(resref or "").strip().lower()
    if key in {"head", "headhook"} or res.startswith(("pmh", "pfh", "po_", "n_")) and "head" in key:
        return "head"
    if key in {"lhand", "left_hand", "left_weapon", "lhand_g"} or key.startswith("left"):
        return "left_weapon"
    if key in {"rhand", "right_hand", "right_weapon", "rhand_g", "lightsaberhook", "deflecthook"} or key.startswith("right"):
        return "right_weapon"
    return ""


def bas_socket_for_slot(slot: str) -> str:
    """Return the body dummy/socket name used by a BAS slot."""
    return BAS_SOCKET_BY_SLOT.get(str(slot or "").strip().lower(), "")


def tag_bas_attachment_subtree(node: Any, root: Any) -> None:
    """Tag every node in an attachment layer so renderers keep it out of body skinning."""
    stack = [node]
    visited: set[int] = set()
    while stack:
        current = stack.pop()
        if current is None or id(current) in visited:
            continue
        visited.add(id(current))
        setattr(current, "_gr_bas_attachment_layer", True)
        setattr(current, "_gr_bas_attachment_root_ref", root)
        try:
            setattr(current, "_gr_bas_attachment_source_model_id", int(getattr(root, "_gr_bas_attachment_source_model_id", 0) or 0))
            setattr(current, "_gr_bas_attachment_source_model_name", str(getattr(root, "_gr_bas_attachment_source_model_name", "") or ""))
        except Exception:
            pass
        stack.extend(getattr(current, "children", []) or [])


def _apply_bas_layer_transform(root: Any, transform: dict[str, Any] | None) -> None:
    values = normalize_bas_transform(transform)
    for attr in ("position", "rotation", "scale"):
        try:
            setattr(root, attr, tuple(values[attr]))
        except Exception:
            pass


def prepare_bas_layer_root(item_root: Any, socket: Any, slot: str) -> None:
    """Prepare an attachment root for socket-following BAS rendering."""
    socket_name = str(getattr(socket, "name", "") or "").strip()
    if str(slot or "").lower() == "head":
        pos = tuple(float(v) for v in getattr(item_root, "position", (0.0, 0.0, 0.0))[:3])
        try:
            socket_world = socket.world_position()
        except Exception:
            socket_world = (0.0, 0.0, 0.0)
        if abs(float(pos[2]) + float(socket_world[2])) < 0.25 and abs(float(pos[2])) > 0.5:
            item_root.position = (pos[0], pos[1], 0.0)
    setattr(item_root, "_gr_bas_attachment_root", True)
    setattr(item_root, "_gr_bas_attachment_slot", str(slot or "attachment"))
    setattr(item_root, "_gr_bas_socket_name", socket_name)
    tag_bas_attachment_subtree(item_root, item_root)


def attach_bas_item_to_preview(
    preview_model: Any,
    item_model: Any,
    socket_name: str,
    *,
    slot: str = "",
    transform: dict[str, Any] | None = None,
) -> bool:
    """Attach a model copy to a body preview as a BAS socket-following layer."""
    socket = find_model_node(preview_model, socket_name)
    item_copy = copy.deepcopy(item_model)
    reset_bas_model_node_traversal(item_copy)
    item_root = getattr(item_copy, "root_node", None)
    if socket is None or item_root is None:
        return False
    try:
        setattr(item_root, "_gr_bas_attachment_source_model_id", id(item_model))
        setattr(item_root, "_gr_bas_attachment_source_model_name", str(getattr(item_model, "name", "") or ""))
        setattr(item_root, "_gr_bas_attachment_source_model_ref", item_model)
    except Exception:
        pass
    prepare_bas_layer_root(item_root, socket, slot or socket_name)
    _apply_bas_layer_transform(item_root, transform)
    item_root.parent = socket
    children = getattr(socket, "children", None)
    if children is None:
        socket.children = []
        children = socket.children
    children.append(item_root)
    return True


def build_bas_preview_model(
    *,
    body_model: Any,
    attachment_models: dict[str, Any] | None = None,
    attachment_transforms: dict[str, dict[str, Any]] | None = None,
    name: str = "",
) -> Any:
    """Build a copied body preview with BAS attachment layers."""
    preview = copy.deepcopy(body_model)
    reset_bas_model_node_traversal(preview)
    attachment_models = attachment_models or {}
    attachment_transforms = attachment_transforms or {}
    for slot in BAS_ATTACHMENT_SLOTS:
        item = attachment_models.get(slot)
        if item is None:
            continue
        socket = bas_socket_for_slot(slot)
        if not attach_bas_item_to_preview(
            preview,
            item,
            socket,
            slot=slot,
            transform=attachment_transforms.get(slot),
        ):
            raise ValueError(f"{slot} attachment failed: body has no {socket} socket.")
    if name:
        try:
            preview.name = str(name)
        except Exception:
            pass
    return preview
