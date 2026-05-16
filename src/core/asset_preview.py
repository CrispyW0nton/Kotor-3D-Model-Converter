"""Asset Viewer character preview assembly.

M14 starts with the modder QA path: load a headless body/outfit plus a
head, snap the head at ``headhook``, and expose enough structured state
for the Asset Viewer UI to render and validate the preview without
booting KOTOR.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

Matrix4 = tuple[
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
]

IDENTITY_MATRIX: Matrix4 = (
    (1.0, 0.0, 0.0, 0.0),
    (0.0, 1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0),
    (0.0, 0.0, 0.0, 1.0),
)

SOCKET_ALIASES: dict[str, tuple[str, ...]] = {
    "right_hand": ("rhand", "rhand_g", "r_hand", "hand_r", "lightsaberhook"),
    "left_hand": ("lhand", "lhand_g", "l_hand", "hand_l"),
    "lightsaber": ("lightsaberhook", "rhand", "rhand_g"),
    "back": ("backhook", "back_hook", "backpackhook", "spinehook", "torsoUpr_g"),
    "utility": ("deflecthook", "handconjure", "impact_bolt", "camerahook"),
}


def _import_model_data():  # pragma: no cover - import shim
    try:
        from src.core import model_data as _md  # type: ignore
    except ImportError:
        from core import model_data as _md  # type: ignore
    return _md


def _import_composite_workflow():  # pragma: no cover - import shim
    try:
        from src.core import composite_workflow as _cw  # type: ignore
    except ImportError:
        from core import composite_workflow as _cw  # type: ignore
    return _cw


@dataclass(frozen=True)
class CharacterPreviewSpec:
    """Input contract for an Asset Viewer character preview."""

    body_path: str
    head_path: str
    outfit_path: str = ""
    game_version: str = "K1"
    body_resref: str = ""
    head_resref: str = ""
    outfit_resref: str = ""


@dataclass
class CharacterPreviewResult:
    """Assembled character preview state for the Asset Viewer."""

    ok: bool = False
    scene: Optional[Any] = None
    spec: Optional[CharacterPreviewSpec] = None
    composite_result: Optional[Any] = None
    snap: Optional[Any] = None
    preview_model: Optional[Any] = None
    visible_body_model: Optional[Any] = None
    head_model: Optional[Any] = None
    warnings: list[str] = field(default_factory=list)
    message: str = ""
    code: str = "not_loaded"


@dataclass(frozen=True)
class AttachmentSpec:
    """Input contract for attaching an item/weapon to a preview socket."""

    item_model: Any
    item_path: str = ""
    item_resref: str = ""
    socket: str = "right_hand"
    socket_name: str = ""
    attachment_type: str = "weapon"
    side: str = "right"


@dataclass
class AttachmentResult:
    """Result of attaching an item/weapon model to a preview socket."""

    ok: bool = False
    item_model: Any = None
    body_model: Any = None
    socket_name: str = ""
    socket_alias: str = ""
    socket_world_transform: Any = None
    item_local_offset: Matrix4 = IDENTITY_MATRIX
    available_sockets: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    message: str = ""
    code: str = "not_attached"


def _scene_metadata(scene: Any) -> dict[str, Any]:
    metadata = getattr(scene, "metadata", None)
    if metadata is None:
        scene.metadata = {}
        metadata = scene.metadata
    return metadata


def _slot_model(scene: Any, slot: Any) -> Any:
    getter = getattr(scene, "get_model", None)
    if callable(getter):
        return getter(slot)
    return None


def _all_nodes(model: Any) -> list[Any]:
    if model is None:
        return []
    try:
        nodes = model.all_nodes()
        return list(nodes or [])
    except Exception:
        return []


def _node_name(node: Any) -> str:
    return str(getattr(node, "name", "") or "")


def _node_world_transform(node: Any) -> tuple[tuple[float, float, float], tuple[float, float, float, float]]:
    world_transform = getattr(node, "world_transform", None)
    if callable(world_transform):
        value = world_transform()
        if value and len(value) >= 2:
            return value[0], value[1]
    position = getattr(node, "position", (0.0, 0.0, 0.0))
    rotation = getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))
    return position, rotation


def _normalise_quat(q: Any) -> tuple[float, float, float, float]:
    x, y, z, w = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
    mag = (x * x + y * y + z * z + w * w) ** 0.5
    if mag <= 0.0:
        return (0.0, 0.0, 0.0, 1.0)
    return (x / mag, y / mag, z / mag, w / mag)


def _matrix_from_transform(position: Any, rotation: Any) -> Matrix4:
    x, y, z, w = _normalise_quat(rotation)
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    tx, ty, tz = (float(position[0]), float(position[1]), float(position[2]))
    return (
        (1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy), tx),
        (2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx), ty),
        (2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy), tz),
        (0.0, 0.0, 0.0, 1.0),
    )


def _socket_names(model: Any) -> list[str]:
    names: list[str] = []
    for node in _all_nodes(model):
        name = _node_name(node)
        lower = name.lower()
        if "hook" in lower or lower in {"rhand", "lhand", "rhand_g", "lhand_g", "handconjure", "impact_bolt"}:
            names.append(name)
    return sorted(dict.fromkeys(names), key=str.lower)


def _resolve_socket(body_model: Any, socket: str, socket_name: str = "") -> tuple[Any, str, str]:
    nodes = _all_nodes(body_model)
    by_lower = {_node_name(node).lower(): node for node in nodes if _node_name(node)}
    if socket_name:
        node = by_lower.get(socket_name.lower())
        return node, socket_name, "explicit"
    alias = (socket or "right_hand").lower()
    for candidate in SOCKET_ALIASES.get(alias, (alias,)):
        node = by_lower.get(candidate.lower())
        if node is not None:
            return node, _node_name(node), alias
    return None, "", alias


def _write_preview_metadata(
    scene: Any,
    spec: CharacterPreviewSpec,
    result: CharacterPreviewResult,
) -> None:
    md = _import_model_data()
    snap = result.snap
    _scene_metadata(scene)["asset_preview"] = {
        "kind": "character",
        "ok": result.ok,
        "code": result.code,
        "game_version": spec.game_version,
        "body_path": spec.body_path,
        "head_path": spec.head_path,
        "outfit_path": spec.outfit_path,
        "active_body_path": spec.outfit_path or spec.body_path,
        "body_resref": spec.body_resref,
        "head_resref": spec.head_resref,
        "outfit_resref": spec.outfit_resref,
        "visible_slots": [
            md.PartSlot.HEADLESS_BODY.value,
            md.PartSlot.HEAD_SHELL.value,
        ],
        "snap": {
            "ok": bool(getattr(snap, "ok", False)) if snap is not None else False,
            "code": str(getattr(snap, "code", "not_snapped")) if snap is not None else "not_snapped",
            "headhook_name": str(getattr(snap, "headhook_name", "headhook")) if snap is not None else "headhook",
            "head_local_offset": getattr(snap, "head_local_offset", None),
        },
        "warnings": list(result.warnings),
    }


def load_character_preview(
    spec: CharacterPreviewSpec,
    *,
    scene: Any | None = None,
    build_preview: bool = True,
    allow_mode_correction: bool = True,
) -> CharacterPreviewResult:
    """Load and snap a character preview using the M7 composite backend.

    ``outfit_path`` is treated as the visible headless-body variant when
    supplied.  This matches KOTOR's armor/robe preview behavior: the head
    attaches to the currently displayed body variant's ``headhook``.
    """

    if not spec.body_path and not spec.outfit_path:
        return CharacterPreviewResult(
            spec=spec,
            message="Load a headless body or outfit variant before previewing a character.",
            code="body_required",
        )
    if not spec.head_path:
        return CharacterPreviewResult(
            spec=spec,
            message="Load a head model before previewing a character.",
            code="head_required",
        )

    md = _import_model_data()
    cw = _import_composite_workflow()
    preview_scene = scene or md.CharacterScene(game_version=spec.game_version)
    visible_body_path = spec.outfit_path or spec.body_path

    composite = cw.load_composite(
        preview_scene,
        body_path=visible_body_path,
        head_path=spec.head_path,
        game_version=spec.game_version,
        build_preview=build_preview,
        allow_mode_correction=allow_mode_correction,
    )
    snap = getattr(composite, "snap", None)
    warnings = list(getattr(snap, "warnings", []) or [])
    result = CharacterPreviewResult(
        ok=bool(getattr(composite, "ok", False)),
        scene=preview_scene,
        spec=spec,
        composite_result=composite,
        snap=snap,
        preview_model=getattr(snap, "preview_model", None),
        visible_body_model=_slot_model(preview_scene, md.PartSlot.HEADLESS_BODY),
        head_model=_slot_model(preview_scene, md.PartSlot.HEAD_SHELL),
        warnings=warnings,
        message=str(getattr(composite, "message", "") or ""),
        code=str(getattr(composite, "code", "") or "loaded"),
    )

    if spec.outfit_path:
        slot = getattr(preview_scene, "get", lambda _slot: None)(md.PartSlot.HEADLESS_BODY)
        model = _slot_model(preview_scene, md.PartSlot.HEADLESS_BODY)
        assign = getattr(preview_scene, "assign", None)
        if callable(assign) and model is not None:
            assign(
                md.PartSlot.BODY_VARIANT,
                model,
                resref=spec.outfit_resref or getattr(slot, "resref", ""),
                source_path=spec.outfit_path,
            )

    _write_preview_metadata(preview_scene, spec, result)
    return result


def refresh_character_preview(
    scene: Any,
    spec: CharacterPreviewSpec,
    *,
    build_preview: bool = True,
) -> CharacterPreviewResult:
    """Recompute preview snap after a scene/body/head mutation."""

    cw = _import_composite_workflow()
    snap = cw.update_snap_after_scene_mutation(scene, build_preview=build_preview)
    md = _import_model_data()
    result = CharacterPreviewResult(
        ok=bool(getattr(snap, "ok", False)),
        scene=scene,
        spec=spec,
        snap=snap,
        preview_model=getattr(snap, "preview_model", None),
        visible_body_model=_slot_model(scene, md.PartSlot.HEADLESS_BODY),
        head_model=_slot_model(scene, md.PartSlot.HEAD_SHELL),
        warnings=list(getattr(snap, "warnings", []) or []),
        message=str(getattr(snap, "message", "") or ""),
        code=str(getattr(snap, "code", "") or "not_snapped"),
    )
    _write_preview_metadata(scene, spec, result)
    return result


def available_attachment_sockets(scene: Any) -> list[str]:
    """Return socket/hook names available on the visible preview body."""

    md = _import_model_data()
    return _socket_names(_slot_model(scene, md.PartSlot.HEADLESS_BODY))


def attach_item_to_preview(scene: Any, spec: AttachmentSpec) -> AttachmentResult:
    """Attach a weapon/item model to a preview body's socket metadata.

    This does not rewrite vertex data.  It annotates the item model and scene
    metadata so the Asset Viewer viewport can parent/render the attachment at
    the resolved KOTOR hook.
    """

    md = _import_model_data()
    body = _slot_model(scene, md.PartSlot.HEADLESS_BODY)
    available = _socket_names(body)
    if body is None:
        return AttachmentResult(
            item_model=spec.item_model,
            available_sockets=available,
            message="Load a character preview before attaching weapons or items.",
            code="preview_body_missing",
        )
    if spec.item_model is None:
        return AttachmentResult(
            body_model=body,
            available_sockets=available,
            message="Load a weapon or item model before attaching it.",
            code="item_missing",
        )

    socket_node, socket_name, socket_alias = _resolve_socket(body, spec.socket, spec.socket_name)
    if socket_node is None:
        requested = spec.socket_name or spec.socket
        return AttachmentResult(
            item_model=spec.item_model,
            body_model=body,
            socket_alias=socket_alias,
            available_sockets=available,
            warnings=[f"Available sockets: {', '.join(available) or 'none'}"],
            message=f"Preview body has no socket matching '{requested}'.",
            code="socket_missing",
        )

    position, rotation = _node_world_transform(socket_node)
    matrix = _matrix_from_transform(position, rotation)
    item = spec.item_model
    setattr(item, "preview_parent_socket", socket_name)
    setattr(item, "preview_socket_alias", socket_alias)
    setattr(item, "socket_world_transform", (position, rotation))
    setattr(item, "item_local_offset", matrix)
    setattr(item, "preview_attachment_type", spec.attachment_type)
    setattr(item, "preview_attachment_side", spec.side)

    assign = getattr(scene, "assign", None)
    if callable(assign):
        assign(
            md.PartSlot.ACCESSORY,
            item,
            resref=spec.item_resref,
            source_path=spec.item_path,
        )

    result = AttachmentResult(
        ok=True,
        item_model=item,
        body_model=body,
        socket_name=socket_name,
        socket_alias=socket_alias,
        socket_world_transform=(position, rotation),
        item_local_offset=matrix,
        available_sockets=available,
        message=f"Attached {spec.item_resref or getattr(item, 'name', 'item')} to {socket_name}.",
        code="attached",
    )

    metadata = _scene_metadata(scene)
    preview = metadata.setdefault("asset_preview", {})
    attachments = preview.setdefault("attachments", [])
    attachment_payload = {
        "ok": True,
        "code": result.code,
        "type": spec.attachment_type,
        "side": spec.side,
        "socket": socket_name,
        "socket_alias": socket_alias,
        "item_path": spec.item_path,
        "item_resref": spec.item_resref,
        "item_local_offset": matrix,
    }
    attachments.append(attachment_payload)
    metadata["active_attachment"] = attachment_payload
    return result
