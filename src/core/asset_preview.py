"""Asset Viewer character preview assembly.

M14 starts with the modder QA path: load a headless body/outfit plus a
head, snap the head at ``headhook``, and expose enough structured state
for the Asset Viewer UI to render and validate the preview without
booting KOTOR.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


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
