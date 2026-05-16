"""Asset Viewer character preview assembly.

M14 starts with the modder QA path: load a headless body/outfit plus a
head, snap the head at ``headhook``, and expose enough structured state
for the Asset Viewer UI to render and validate the preview without
booting KOTOR.
"""

from __future__ import annotations

import os
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


def _import_kotor_loader():  # pragma: no cover - import shim
    try:
        from src.core.kotor_loader import load_model_from_file  # type: ignore
    except ImportError:
        from core.kotor_loader import load_model_from_file  # type: ignore
    return load_model_from_file


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


@dataclass(frozen=True)
class PreviewAnimationClip:
    """Animation clip exposed by the Asset Viewer workbench."""

    name: str
    group: str
    source: str = "model"
    source_model: str = ""
    label: str = ""
    length: float = 0.0
    loop: bool = True
    inherited: bool = False


@dataclass
class AnimationWorkbenchResult:
    """Grouped preview-animation catalog for the Asset Viewer."""

    ok: bool = False
    clips: list[PreviewAnimationClip] = field(default_factory=list)
    groups: dict[str, list[PreviewAnimationClip]] = field(default_factory=dict)
    selected: Optional[PreviewAnimationClip] = None
    warnings: list[str] = field(default_factory=list)
    message: str = ""
    code: str = "not_listed"


@dataclass
class PreviewPlaybackState:
    """Current play/scrub state for a preview animation clip."""

    ok: bool = False
    clip: Optional[PreviewAnimationClip] = None
    clip_name: str = ""
    group: str = ""
    source: str = ""
    source_model: str = ""
    time: float = 0.0
    duration: float = 0.0
    loop: bool = True
    playing: bool = False
    message: str = ""
    code: str = "not_playing"


@dataclass(frozen=True)
class AttachmentValidationIssue:
    """Actionable Asset Viewer finding for an attached item or socket."""

    severity: str
    code: str
    message: str
    socket: str = ""
    item_resref: str = ""
    action: str = ""
    overlay_anchor: Optional[Matrix4] = None


@dataclass
class AttachmentValidationReport:
    """Validation overlay payload for preview attachments."""

    ok: bool = True
    issues: list[AttachmentValidationIssue] = field(default_factory=list)
    overlay: list[dict[str, Any]] = field(default_factory=list)
    available_sockets: list[str] = field(default_factory=list)
    message: str = ""
    code: str = "validated"


@dataclass(frozen=True)
class ExportPreviewDelta:
    """One difference between the preview model and exported/reloaded model."""

    severity: str
    kind: str
    name: str
    message: str
    source: Any = None
    exported: Any = None
    action: str = ""


@dataclass
class ExportPreviewParityReport:
    """Asset Viewer report comparing preview state to a reloaded export."""

    ok: bool = False
    deltas: list[ExportPreviewDelta] = field(default_factory=list)
    source_summary: dict[str, Any] = field(default_factory=dict)
    exported_summary: dict[str, Any] = field(default_factory=dict)
    exported_path: str = ""
    message: str = ""
    code: str = "not_compared"


ANIMATION_GROUP_ORDER: tuple[str, ...] = (
    "idle",
    "locomotion",
    "talk",
    "combat",
    "item",
    "rom",
    "other",
)

DEFAULT_PREVIEW_PRIORITY: tuple[str, ...] = (
    "pause1",
    "pause2",
    "listen",
    "walk",
    "run",
    "tlknorm",
)

_HAND_SOCKET_SIDES: dict[str, str] = {
    "rhand": "right",
    "rhand_g": "right",
    "lightsaberhook": "right",
    "lhand": "left",
    "lhand_g": "left",
}


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


def _model_identity(model: Any, fallback: str = "") -> str:
    for attr in ("name", "resref", "model_name"):
        value = str(getattr(model, attr, "") or "").strip()
        if value:
            return value
    return fallback


def _animation_name(anim: Any) -> str:
    if isinstance(anim, str):
        return anim.strip()
    if isinstance(anim, dict):
        for key in ("name", "anim_name", "clip", "animation"):
            value = str(anim.get(key, "") or "").strip()
            if value:
                return value
        return ""
    for attr in ("name", "anim_name", "clip", "animation"):
        value = str(getattr(anim, attr, "") or "").strip()
        if value:
            return value
    return ""


def _animation_length(anim: Any) -> float:
    if isinstance(anim, dict):
        values = (anim.get("length"), anim.get("duration"), anim.get("end_time"))
    else:
        values = (
            getattr(anim, "length", None),
            getattr(anim, "duration", None),
            getattr(anim, "end_time", None),
        )
    for value in values:
        try:
            length = float(value)
        except (TypeError, ValueError):
            continue
        if length > 0.0:
            return length
    return 0.0


def _model_animations(model: Any) -> list[Any]:
    for attr in ("animations", "anims", "animation_list"):
        value = getattr(model, attr, None)
        if value is None:
            continue
        try:
            return list(value)
        except Exception:
            return []
    return []


def _mesh_nodes(model: Any) -> list[Any]:
    meshes: list[Any] = []
    for node in _all_nodes(model):
        if (
            bool(getattr(node, "is_mesh", False))
            or bool(getattr(node, "is_skin", False))
            or bool(getattr(node, "vertices", None))
            or str(getattr(node, "type_label", "") or "").lower() in {"trimesh", "skin", "dangly", "saber"}
        ):
            meshes.append(node)
    return meshes


def _clean_token(value: Any) -> str:
    return str(value or "").strip().strip("\x00").lower()


def _node_textures(node: Any) -> tuple[str, ...]:
    values: list[str] = []
    texture_clean = getattr(node, "texture_clean", None)
    if isinstance(texture_clean, str):
        values.append(texture_clean)
    for attr in ("texture", "lightmap", "bump_map", "txi_envmaptexture", "txi_bumpmaptexture"):
        values.append(getattr(node, attr, ""))
    texture_names = getattr(node, "texture_names", None)
    if texture_names:
        try:
            values.extend(list(texture_names))
        except Exception:
            pass
    cleaned = [_clean_token(value) for value in values]
    return tuple(dict.fromkeys(value for value in cleaned if value))


def _preview_source_model(scene: Any) -> Any:
    md = _import_model_data()
    preview_model = getattr(scene, "preview_model", None)
    if _all_nodes(preview_model):
        return preview_model
    return _slot_model(scene, md.PartSlot.HEADLESS_BODY)


def _slot_entry(scene: Any, slot: Any) -> Any:
    getter = getattr(scene, "get", None)
    if callable(getter):
        return getter(slot)
    return None


def _slot_game_version(scene: Any, slot: Any) -> str:
    entry = _slot_entry(scene, slot)
    return str(getattr(entry, "game_version", "") or "").upper()


def _slot_resref(scene: Any, slot: Any) -> str:
    entry = _slot_entry(scene, slot)
    return str(getattr(entry, "resref", "") or "").lower()


def _animation_group(name: str, source: str = "") -> str:
    lower = (name or "").lower()
    if lower.startswith("pause") or lower in {"idle", "listen", "ready"}:
        return "idle"
    if lower in {"walk", "walkss", "run", "runss", "turnleft", "turnright"}:
        return "locomotion"
    if lower.startswith("tlk") or lower.startswith("kdtlk") or "talk" in lower:
        return "talk"
    if lower in {"powered", "off", "powerup", "powerdown", "throwout", "throwback"}:
        return "item"
    if lower in {"generated_rom", "rom"} or source == "generated_rom":
        return "rom"
    combat_prefixes = ("c", "f", "g", "kd", "nw", "pa", "ph", "ta", "sp")
    combat_names = {
        "cast",
        "damage",
        "dead",
        "die",
        "dodge",
        "parry",
        "taunt",
        "choke",
        "fear",
        "horror",
        "whirlwind",
    }
    if lower in combat_names or lower.startswith(combat_prefixes):
        return "combat"
    return "other"


def _clip_loop_default(group: str) -> bool:
    return group in {"idle", "locomotion", "talk", "item", "rom"}


def _motion_assignment(scene: Any) -> dict[str, Any]:
    state = getattr(scene, "motion_assignment", None)
    if isinstance(state, dict):
        return dict(state)
    return {}


def _add_clip(
    clips: list[PreviewAnimationClip],
    seen: set[tuple[str, str, str]],
    *,
    name: str,
    source: str,
    source_model: str = "",
    length: float = 0.0,
    inherited: bool = False,
) -> None:
    name = (name or "").strip()
    if not name:
        return
    group = _animation_group(name, source)
    key = (name.lower(), source, source_model.lower())
    if key in seen:
        return
    seen.add(key)
    clips.append(
        PreviewAnimationClip(
            name=name,
            group=group,
            source=source,
            source_model=source_model,
            label=name.replace("_", " ").title(),
            length=length,
            loop=_clip_loop_default(group),
            inherited=inherited,
        )
    )


def _group_clips(clips: list[PreviewAnimationClip]) -> dict[str, list[PreviewAnimationClip]]:
    grouped: dict[str, list[PreviewAnimationClip]] = {}
    order = {name: index for index, name in enumerate(ANIMATION_GROUP_ORDER)}
    for clip in sorted(
        clips,
        key=lambda c: (order.get(c.group, len(order)), c.name.lower(), c.source),
    ):
        grouped.setdefault(clip.group, []).append(clip)
    return grouped


def _default_clip(clips: list[PreviewAnimationClip]) -> Optional[PreviewAnimationClip]:
    by_name = {clip.name.lower(): clip for clip in clips}
    for name in DEFAULT_PREVIEW_PRIORITY:
        clip = by_name.get(name)
        if clip is not None:
            return clip
    return clips[0] if clips else None


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
    try:
        setattr(preview_scene, "preview_model", result.preview_model)
    except Exception:
        pass

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
    try:
        setattr(scene, "preview_model", result.preview_model)
    except Exception:
        pass
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


def _issue_payload(issue: AttachmentValidationIssue) -> dict[str, Any]:
    return {
        "severity": issue.severity,
        "code": issue.code,
        "message": issue.message,
        "socket": issue.socket,
        "item_resref": issue.item_resref,
        "action": issue.action,
        "overlay_anchor": issue.overlay_anchor,
    }


def _attachment_issue(
    severity: str,
    code: str,
    message: str,
    *,
    socket: str = "",
    item_resref: str = "",
    action: str = "",
    overlay_anchor: Optional[Matrix4] = None,
) -> AttachmentValidationIssue:
    return AttachmentValidationIssue(
        severity=severity,
        code=code,
        message=message,
        socket=socket,
        item_resref=item_resref,
        action=action,
        overlay_anchor=overlay_anchor,
    )


def _socket_side(socket_name: str) -> str:
    return _HAND_SOCKET_SIDES.get((socket_name or "").lower(), "")


def _expected_attachment_side(attachment: dict[str, Any]) -> str:
    side = str(attachment.get("side") or "").lower()
    if side in {"right", "left"}:
        return side
    alias = str(attachment.get("socket_alias") or "").lower()
    if alias in {"right_hand", "lightsaber"}:
        return "right"
    if alias == "left_hand":
        return "left"
    return ""


def _is_lightsaber_attachment(attachment: dict[str, Any]) -> bool:
    item_resref = str(attachment.get("item_resref") or "").lower()
    kind = str(attachment.get("type") or "").lower()
    socket_alias = str(attachment.get("socket_alias") or "").lower()
    return (
        "lghtsbr" in item_resref
        or "lightsaber" in kind
        or socket_alias == "lightsaber"
    )


def _requires_bullet_hook(attachment: dict[str, Any]) -> bool:
    item_resref = str(attachment.get("item_resref") or "").lower()
    kind = str(attachment.get("type") or "").lower()
    return (
        "blaster" in kind
        or item_resref.startswith("w_blstr")
        or item_resref.startswith("w_rfl")
        or item_resref.startswith("w_bow")
    )


def _matrix_close(a: Any, b: Any, tolerance: float = 0.001) -> bool:
    try:
        for row_a, row_b in zip(a, b):
            for value_a, value_b in zip(row_a, row_b):
                if abs(float(value_a) - float(value_b)) > tolerance:
                    return False
    except Exception:
        return False
    return True


def validate_attachment_overlay(scene: Any) -> AttachmentValidationReport:
    """Validate Asset Viewer attachments and write overlay-ready metadata."""

    md = _import_model_data()
    body = _slot_model(scene, md.PartSlot.HEADLESS_BODY)
    accessory = _slot_model(scene, md.PartSlot.ACCESSORY)
    available = _socket_names(body)
    metadata = _scene_metadata(scene)
    preview = metadata.setdefault("asset_preview", {})
    attachments = list(preview.get("attachments") or [])
    issues: list[AttachmentValidationIssue] = []

    if body is None:
        issues.append(
            _attachment_issue(
                "error",
                "PREVIEW_BODY_MISSING",
                "Load a character preview before validating weapon or item attachments.",
                action="Load a headless body/outfit and head, then attach the item again.",
            )
        )
    if body is not None and not attachments:
        issues.append(
            _attachment_issue(
                "info",
                "NO_ATTACHMENTS",
                "No preview attachments are active.",
                action="Attach a weapon or item to test its in-game socket placement.",
            )
        )

    scene_game = str(getattr(scene, "game_version", "") or "").upper()
    body_game = _slot_game_version(scene, md.PartSlot.HEADLESS_BODY)
    accessory_game = _slot_game_version(scene, md.PartSlot.ACCESSORY)
    if body is not None and scene_game and body_game and body_game != scene_game:
        issues.append(
            _attachment_issue(
                "warning",
                "BODY_GAME_MISMATCH",
                f"Preview body is {body_game}, but the scene is {scene_game}.",
                action="Use body/outfit assets from the same game target before final export.",
            )
        )
    if accessory is not None and scene_game and accessory_game and accessory_game != scene_game:
        issues.append(
            _attachment_issue(
                "warning",
                "ATTACHMENT_GAME_MISMATCH",
                f"Attached item is {accessory_game}, but the scene is {scene_game}.",
                item_resref=_slot_resref(scene, md.PartSlot.ACCESSORY),
                action="Swap the item for the matching K1/K2 version or change the preview target game.",
            )
        )

    body_nodes = {_node_name(node).lower(): node for node in _all_nodes(body) if _node_name(node)}
    item_nodes = {_node_name(node).lower(): node for node in _all_nodes(accessory) if _node_name(node)}
    for attachment in attachments:
        socket = str(attachment.get("socket") or "")
        socket_key = socket.lower()
        item_resref = str(attachment.get("item_resref") or _slot_resref(scene, md.PartSlot.ACCESSORY) or "")
        stored_matrix = attachment.get("item_local_offset")
        current_node = body_nodes.get(socket_key)
        current_matrix: Optional[Matrix4] = None
        if current_node is None:
            issues.append(
                _attachment_issue(
                    "error",
                    "ATTACHMENT_SOCKET_MISSING",
                    f"Attachment socket '{socket or 'unknown'}' is not present on the current preview body.",
                    socket=socket,
                    item_resref=item_resref,
                    action="Choose one of the body's available sockets or load a body that provides this hook.",
                )
            )
            continue

        position, rotation = _node_world_transform(current_node)
        current_matrix = _matrix_from_transform(position, rotation)
        expected_side = _expected_attachment_side(attachment)
        actual_side = _socket_side(socket)
        if expected_side and actual_side and expected_side != actual_side:
            issues.append(
                _attachment_issue(
                    "warning",
                    "WRONG_HAND_ATTACHMENT",
                    f"{item_resref or 'Attachment'} is assigned to the {expected_side} side but parented to {socket}.",
                    socket=socket,
                    item_resref=item_resref,
                    action=f"Reattach it to a {expected_side}-hand socket.",
                    overlay_anchor=current_matrix,
                )
            )
        if stored_matrix is not None and not _matrix_close(stored_matrix, current_matrix):
            issues.append(
                _attachment_issue(
                    "warning",
                    "ATTACHMENT_TRANSFORM_STALE",
                    f"{item_resref or 'Attachment'} was attached before the body socket moved.",
                    socket=socket,
                    item_resref=item_resref,
                    action="Refresh or reattach the item so its preview transform matches the current socket.",
                    overlay_anchor=current_matrix,
                )
            )
        if _is_lightsaber_attachment(attachment) and socket_key not in {"lightsaberhook", "rhand", "rhand_g"}:
            issues.append(
                _attachment_issue(
                    "warning",
                    "LIGHTSABER_SOCKET_UNUSUAL",
                    f"{item_resref or 'Lightsaber'} is not attached to LightsaberHook or the right hand.",
                    socket=socket,
                    item_resref=item_resref,
                    action="Use the lightsaber socket when present; otherwise use rhand.",
                    overlay_anchor=current_matrix,
                )
            )
        if _requires_bullet_hook(attachment) and accessory is not None and "bullethook" not in item_nodes:
            issues.append(
                _attachment_issue(
                    "warning",
                    "BULLET_HOOK_MISSING",
                    f"{item_resref or 'Blaster'} has no bullethook node for muzzle/VFX preview.",
                    socket=socket,
                    item_resref=item_resref,
                    action="Add or preserve bullethook on blaster-style weapon models.",
                    overlay_anchor=current_matrix,
                )
            )

    error_count = sum(1 for issue in issues if issue.severity == "error")
    actionable = [issue for issue in issues if issue.severity in {"error", "warning"}]
    overlay = [_issue_payload(issue) for issue in actionable]
    report_payload = {
        "ok": error_count == 0,
        "code": "validated" if error_count == 0 else "errors",
        "available_sockets": list(available),
        "issues": [_issue_payload(issue) for issue in issues],
        "overlay": overlay,
    }
    preview["attachment_validation"] = report_payload
    return AttachmentValidationReport(
        ok=error_count == 0,
        issues=issues,
        overlay=overlay,
        available_sockets=available,
        message=(
            "Attachment validation is clean."
            if not actionable
            else f"{len(actionable)} attachment issue(s) need attention."
        ),
        code=report_payload["code"],
    )


def _load_exported_preview_model(exported_path: str) -> Any:
    if not exported_path:
        return None
    loader = _import_kotor_loader()
    mdx_path = os.path.splitext(exported_path)[0] + ".mdx"
    return loader(exported_path, mdx_path if os.path.isfile(mdx_path) else "")


def _model_parity_summary(model: Any) -> dict[str, Any]:
    nodes = _all_nodes(model)
    meshes = _mesh_nodes(model)
    mesh_names = sorted(
        dict.fromkeys(_node_name(node) for node in meshes if _node_name(node)),
        key=str.lower,
    )
    hooks = _socket_names(model)
    animations = sorted(
        dict.fromkeys(_animation_name(anim) for anim in _model_animations(model) if _animation_name(anim)),
        key=str.lower,
    )
    materials = {
        _node_name(node): _node_textures(node)
        for node in meshes
        if _node_name(node)
    }
    return {
        "model": _model_identity(model, "model"),
        "node_count": len(nodes),
        "mesh_count": len(mesh_names),
        "hook_count": len(hooks),
        "animation_count": len(animations),
        "material_count": len([value for value in materials.values() if value]),
        "meshes": mesh_names,
        "hooks": hooks,
        "animations": animations,
        "materials": materials,
        "supermodel": str(getattr(model, "supermodel", "") or ""),
    }


def _delta(
    severity: str,
    kind: str,
    name: str,
    message: str,
    *,
    source: Any = None,
    exported: Any = None,
    action: str = "",
) -> ExportPreviewDelta:
    return ExportPreviewDelta(
        severity=severity,
        kind=kind,
        name=name,
        message=message,
        source=source,
        exported=exported,
        action=action,
    )


def _delta_payload(delta: ExportPreviewDelta) -> dict[str, Any]:
    return {
        "severity": delta.severity,
        "kind": delta.kind,
        "name": delta.name,
        "message": delta.message,
        "source": delta.source,
        "exported": delta.exported,
        "action": delta.action,
    }


def compare_export_preview_parity(
    scene: Any,
    *,
    exported_model: Any = None,
    exported_path: str = "",
) -> ExportPreviewParityReport:
    """Compare the current preview model against an exported/reloaded MDL.

    The report is intentionally structural and UI-ready: it lists mesh,
    material, animation, hook, and supermodel deltas that would make a KOTOR
    modder's in-game test differ from the Asset Viewer preview.
    """

    source_model = _preview_source_model(scene)
    if source_model is None:
        return ExportPreviewParityReport(
            message="Load a preview model before comparing export parity.",
            code="preview_missing",
            exported_path=exported_path,
        )

    if exported_model is None and exported_path:
        try:
            exported_model = _load_exported_preview_model(exported_path)
        except Exception as exc:
            report = ExportPreviewParityReport(
                ok=False,
                source_summary=_model_parity_summary(source_model),
                exported_path=exported_path,
                message=f"Exported MDL reload failed: {exc}",
                code="reload_failed",
            )
            _scene_metadata(scene).setdefault("asset_preview", {})["export_preview_parity"] = {
                "ok": False,
                "code": report.code,
                "exported_path": exported_path,
                "message": report.message,
            }
            return report

    if exported_model is None:
        return ExportPreviewParityReport(
            ok=False,
            source_summary=_model_parity_summary(source_model),
            exported_path=exported_path,
            message="Provide a reloaded exported model or an exported MDL path for parity comparison.",
            code="export_missing",
        )

    source = _model_parity_summary(source_model)
    exported = _model_parity_summary(exported_model)
    deltas: list[ExportPreviewDelta] = []

    source_meshes = set(source["meshes"])
    exported_meshes = set(exported["meshes"])
    for name in sorted(source_meshes - exported_meshes, key=str.lower):
        deltas.append(
            _delta(
                "error",
                "mesh_missing",
                name,
                f"Exported/reloaded model is missing preview mesh '{name}'.",
                source=True,
                exported=False,
                action="Check export slot selection and MDL writer mesh inclusion.",
            )
        )
    for name in sorted(exported_meshes - source_meshes, key=str.lower):
        deltas.append(
            _delta(
                "info",
                "mesh_added",
                name,
                f"Exported/reloaded model contains additional mesh '{name}'.",
                source=False,
                exported=True,
                action="Confirm this is an intentional generated helper or export artifact.",
            )
        )

    source_hooks = {name.lower(): name for name in source["hooks"]}
    exported_hooks = {name.lower(): name for name in exported["hooks"]}
    for key, name in sorted(source_hooks.items(), key=lambda item: item[0]):
        if key not in exported_hooks:
            deltas.append(
                _delta(
                    "error",
                    "hook_missing",
                    name,
                    f"Exported/reloaded model is missing hook '{name}'.",
                    source=True,
                    exported=False,
                    action="Preserve KOTOR hooks before shipping the MDL.",
                )
            )
    for key, name in sorted(exported_hooks.items(), key=lambda item: item[0]):
        if key not in source_hooks:
            deltas.append(
                _delta(
                    "info",
                    "hook_added",
                    name,
                    f"Exported/reloaded model contains additional hook '{name}'.",
                    source=False,
                    exported=True,
                    action="Verify the added hook is expected for the target game.",
                )
            )

    source_anims = {name.lower(): name for name in source["animations"]}
    exported_anims = {name.lower(): name for name in exported["animations"]}
    for key, name in sorted(source_anims.items(), key=lambda item: item[0]):
        if key not in exported_anims:
            deltas.append(
                _delta(
                    "warning",
                    "animation_missing",
                    name,
                    f"Exported/reloaded model is missing preview animation '{name}'.",
                    source=True,
                    exported=False,
                    action="Assign inherited or exported clips before testing this animation in game.",
                )
            )
    for key, name in sorted(exported_anims.items(), key=lambda item: item[0]):
        if key not in source_anims:
            deltas.append(
                _delta(
                    "info",
                    "animation_added",
                    name,
                    f"Exported/reloaded model contains additional animation '{name}'.",
                    source=False,
                    exported=True,
                    action="Confirm the additional clip is expected from inherited/generated motion handling.",
                )
            )

    source_materials = source["materials"]
    exported_materials = exported["materials"]
    for name in sorted(source_meshes & exported_meshes, key=str.lower):
        source_tex = tuple(source_materials.get(name, ()))
        exported_tex = tuple(exported_materials.get(name, ()))
        if source_tex != exported_tex:
            deltas.append(
                _delta(
                    "warning",
                    "material_changed",
                    name,
                    f"Material/texture assignment changed for mesh '{name}'.",
                    source=source_tex,
                    exported=exported_tex,
                    action="Check texture names, lightmaps, and TXI sidecars before packaging.",
                )
            )

    source_super = str(source.get("supermodel") or "")
    exported_super = str(exported.get("supermodel") or "")
    if source_super.lower() != exported_super.lower():
        deltas.append(
            _delta(
                "warning",
                "supermodel_changed",
                "supermodel",
                f"Supermodel changed from {source_super or 'NULL'} to {exported_super or 'NULL'}.",
                source=source_super,
                exported=exported_super,
                action="Confirm the exported MDL inherits the intended KOTOR animation set.",
            )
        )

    errors = [delta for delta in deltas if delta.severity == "error"]
    warnings = [delta for delta in deltas if delta.severity == "warning"]
    ok = not errors and not warnings
    report = ExportPreviewParityReport(
        ok=ok,
        deltas=deltas,
        source_summary=source,
        exported_summary=exported,
        exported_path=exported_path,
        message=(
            "Export preview parity is clean."
            if ok else
            f"{len(deltas)} export-preview delta(s) found."
        ),
        code="matched" if ok else ("errors" if errors else "warnings"),
    )

    _scene_metadata(scene).setdefault("asset_preview", {})["export_preview_parity"] = {
        "ok": report.ok,
        "code": report.code,
        "message": report.message,
        "exported_path": exported_path,
        "source_summary": source,
        "exported_summary": exported,
        "deltas": [_delta_payload(delta) for delta in deltas],
    }
    return report


def build_animation_workbench(scene: Any) -> AnimationWorkbenchResult:
    """Catalog Asset Viewer preview clips by practical modder workflow group.

    The workbench intentionally includes local model clips, attached item
    clips, imported/generated assignments, and inherited supermodel motions.
    That lets the UI explain why a clip is playable even when it lives on a
    KOTOR supermodel instead of the body MDL the user imported.
    """

    md = _import_model_data()
    body = _slot_model(scene, md.PartSlot.HEADLESS_BODY)
    head = _slot_model(scene, md.PartSlot.HEAD_SHELL)
    accessory = _slot_model(scene, md.PartSlot.ACCESSORY)
    metadata = _scene_metadata(scene)
    preview_metadata = metadata.setdefault("asset_preview", {})

    clips: list[PreviewAnimationClip] = []
    seen: set[tuple[str, str, str]] = set()
    warnings: list[str] = []

    sources = (
        (getattr(scene, "preview_model", None), "preview", "preview"),
        (body, "model", "body"),
        (head, "head", "head"),
        (accessory, "item", "accessory"),
    )
    for model, source, fallback in sources:
        if model is None:
            continue
        source_model = _model_identity(model, fallback)
        for anim in _model_animations(model):
            _add_clip(
                clips,
                seen,
                name=_animation_name(anim),
                source=source,
                source_model=source_model,
                length=_animation_length(anim),
            )

    motion = _motion_assignment(scene)
    motion_source = str(motion.get("source") or "").strip()
    supermodel = str(motion.get("supermodel") or getattr(body, "supermodel", "") or "").strip()
    if motion_source == "inherited_supermodel" and supermodel:
        for name in DEFAULT_PREVIEW_PRIORITY + ("tlkangry", "c2a1", "c2a2"):
            _add_clip(
                clips,
                seen,
                name=name,
                source="inherited_supermodel",
                source_model=supermodel,
                inherited=True,
            )
    imported = motion.get("imported_clips") or motion.get("clips") or []
    for anim in imported:
        _add_clip(
            clips,
            seen,
            name=_animation_name(anim),
            source="imported",
            source_model=str(motion.get("imported_source") or "imported"),
            length=_animation_length(anim),
        )
    if motion_source == "generated_rom" or motion.get("generated"):
        _add_clip(
            clips,
            seen,
            name="generated_rom",
            source="generated_rom",
            source_model="GhostRigger",
            length=float(motion.get("length") or 4.0),
        )

    if body is None:
        warnings.append("Load a character body before previewing animations.")
    if body is not None and not clips:
        warnings.append(
            "No preview animations found. Assign inherited, imported, or generated motions before export testing."
        )

    grouped = _group_clips(clips)
    selected = _default_clip(clips)
    payload = {
        "ok": bool(clips),
        "code": "listed" if clips else "no_animations",
        "selected": selected.name if selected is not None else "",
        "groups": {
            group: [
                {
                    "name": clip.name,
                    "source": clip.source,
                    "source_model": clip.source_model,
                    "length": clip.length,
                    "inherited": clip.inherited,
                }
                for clip in values
            ]
            for group, values in grouped.items()
        },
        "warnings": list(warnings),
    }
    preview_metadata["animation_workbench"] = payload

    return AnimationWorkbenchResult(
        ok=bool(clips),
        clips=clips,
        groups=grouped,
        selected=selected,
        warnings=warnings,
        message=(
            f"{len(clips)} preview animation clip(s) available."
            if clips
            else "No preview animation clips are available."
        ),
        code="listed" if clips else "no_animations",
    )


def _find_workbench_clip(
    workbench: AnimationWorkbenchResult,
    clip_name: str = "",
    *,
    group: str = "",
) -> Optional[PreviewAnimationClip]:
    target = (clip_name or "").strip().lower()
    if target:
        for clip in workbench.clips:
            if clip.name.lower() == target:
                return clip
        return None
    if group:
        values = workbench.groups.get(group, [])
        if values:
            return values[0]
    return workbench.selected


def play_preview_animation(
    scene: Any,
    clip_name: str = "",
    *,
    group: str = "",
    loop: Optional[bool] = None,
    time: float = 0.0,
) -> PreviewPlaybackState:
    """Select an Asset Viewer animation clip for playback."""

    workbench = build_animation_workbench(scene)
    clip = _find_workbench_clip(workbench, clip_name, group=group)
    if clip is None:
        requested = clip_name or group or "default"
        return PreviewPlaybackState(
            message=f"Preview animation '{requested}' is not available.",
            code="clip_missing",
        )

    duration = max(0.0, float(clip.length or 0.0))
    start = max(0.0, float(time or 0.0))
    should_loop = clip.loop if loop is None else bool(loop)
    if duration > 0.0:
        if should_loop:
            start = start % duration
        else:
            start = min(start, duration)

    state = PreviewPlaybackState(
        ok=True,
        clip=clip,
        clip_name=clip.name,
        group=clip.group,
        source=clip.source,
        source_model=clip.source_model,
        time=start,
        duration=duration,
        loop=should_loop,
        playing=True,
        message=f"Playing {clip.name} from {clip.source_model or clip.source}.",
        code="playing",
    )
    metadata = _scene_metadata(scene)
    preview = metadata.setdefault("asset_preview", {})
    preview["playback"] = {
        "ok": True,
        "code": state.code,
        "clip": state.clip_name,
        "group": state.group,
        "source": state.source,
        "source_model": state.source_model,
        "time": state.time,
        "duration": state.duration,
        "loop": state.loop,
        "playing": state.playing,
        "inherited": clip.inherited,
    }
    return state


def scrub_preview_animation(scene: Any, time: float) -> PreviewPlaybackState:
    """Move the active preview clip to a specific timestamp."""

    metadata = _scene_metadata(scene)
    current = metadata.get("asset_preview", {}).get("playback", {})
    clip_name = str(current.get("clip") or "")
    if not clip_name:
        return PreviewPlaybackState(
            message="No preview animation is selected for scrubbing.",
            code="not_playing",
        )
    state = play_preview_animation(
        scene,
        clip_name,
        loop=bool(current.get("loop", True)),
        time=time,
    )
    if state.ok:
        state.playing = bool(current.get("playing", True))
        state.code = "scrubbed"
        state.message = f"Scrubbed {state.clip_name} to {state.time:.3f}s."
        metadata["asset_preview"]["playback"]["code"] = "scrubbed"
        metadata["asset_preview"]["playback"]["time"] = state.time
        metadata["asset_preview"]["playback"]["playing"] = state.playing
    return state
