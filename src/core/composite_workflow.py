"""
src/core/composite_workflow.py - Mode 3 (Supermodel Composite) service
======================================================================

M7 wires the already-shipped body and head workflows into a single
head-on-body preview workflow.  This module deliberately stays Qt-free:
the GUI loads files, asks this service for the current composite snap,
then displays the two scene slots or an optional preview model.

Ground-truth note
-----------------

KotOR keeps body and head as separate MDL resources and attaches the
head at the body's ``headhook`` node.  GhostRigger already has that
engine-shaped behavior in ``creature_appearance.CreatureAssembly`` and
``snap_head_onto_body``; this module wraps those contracts rather than
re-implementing parser or vertex-transform logic.

Roadmap reference: M7 / T701-T702.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

Matrix4 = Tuple[
    Tuple[float, float, float, float],
    Tuple[float, float, float, float],
    Tuple[float, float, float, float],
    Tuple[float, float, float, float],
]

IDENTITY_MATRIX: Matrix4 = (
    (1.0, 0.0, 0.0, 0.0),
    (0.0, 1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0),
    (0.0, 0.0, 0.0, 1.0),
)

KOTOR_PC_SUPERMODELS = frozenset({
    "S_FEMALE02",
    "S_FEMALE03",
    "S_MALE02",
    "S_MALE03",
})


def _import_model_data():                                   # pragma: no cover - import shim
    try:
        from src.core import model_data as _md             # type: ignore
    except ImportError:
        from core import model_data as _md                 # type: ignore
    return _md


def _import_body_workflow():                                # pragma: no cover - import shim
    try:
        from src.core import headless_body_workflow as _wf  # type: ignore
    except ImportError:
        from core import headless_body_workflow as _wf      # type: ignore
    return _wf


def _import_head_workflow():                                # pragma: no cover - import shim
    try:
        from src.core import head_workflow as _wf           # type: ignore
    except ImportError:
        from core import head_workflow as _wf               # type: ignore
    return _wf


def _import_character_builder():                            # pragma: no cover - import shim
    try:
        from src.core import character_builder as _cb       # type: ignore
    except ImportError:
        from core import character_builder as _cb           # type: ignore
    return _cb


def _import_creature_appearance():                          # pragma: no cover - import shim
    try:
        from src.core import creature_appearance as _ca     # type: ignore
    except ImportError:
        from core import creature_appearance as _ca         # type: ignore
    return _ca


@dataclass
class HeadhookSnapResult:
    """Result of recomputing the body ``headhook`` attachment.

    ``head_local_offset`` is a 4x4 matrix built from the headhook world
    transform.  It is metadata for viewport/export consumers; this result
    does not rewrite mesh vertices.
    """

    ok: bool = False
    body_model: Optional[Any] = None
    head_model: Optional[Any] = None
    preview_model: Optional[Any] = None
    headhook: Optional[
        Tuple[Tuple[float, float, float], Tuple[float, float, float, float]]
    ] = None
    headhook_name: str = "headhook"
    head_local_offset: Matrix4 = IDENTITY_MATRIX
    warnings: List[str] = field(default_factory=list)
    message: str = ""
    code: str = "not_snapped"


@dataclass
class CompositeResult:
    """Result of loading and snapping a body/head pair."""

    ok: bool = False
    scene: Optional[Any] = None
    body_result: Optional[Any] = None
    head_result: Optional[Any] = None
    snap: HeadhookSnapResult = field(default_factory=HeadhookSnapResult)
    message: str = ""
    code: str = "load_failed"


def _slot_models(scene: Any) -> Tuple[Optional[Any], Optional[Any]]:
    md = _import_model_data()
    body = scene.get_model(md.PartSlot.HEADLESS_BODY)
    head = scene.get_model(md.PartSlot.HEAD_SHELL)
    return body, head


def _normalise_quat(q: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    x, y, z, w = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
    mag = (x * x + y * y + z * z + w * w) ** 0.5
    if mag <= 0.0:
        return (0.0, 0.0, 0.0, 1.0)
    return (x / mag, y / mag, z / mag, w / mag)


def _matrix_from_transform(
    position: Tuple[float, float, float],
    rotation: Tuple[float, float, float, float],
) -> Matrix4:
    """Build a row-major transform matrix from position + xyzw quaternion."""

    x, y, z, w = _normalise_quat(rotation)
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    tx, ty, tz = (float(position[0]), float(position[1]), float(position[2]))
    return (
        (1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz),       2.0 * (xz + wy),       tx),
        (2.0 * (xy + wz),       1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx),       ty),
        (2.0 * (xz - wy),       2.0 * (yz + wx),       1.0 - 2.0 * (xx + yy), tz),
        (0.0,                   0.0,                   0.0,                   1.0),
    )


def _first_root_name(model: Any) -> str:
    try:
        root = getattr(model, "root_node", None)
        if root is not None:
            return str(getattr(root, "name", "") or "")
        for node in model.all_nodes():
            if getattr(node, "parent", None) is None:
                return str(getattr(node, "name", "") or "")
    except Exception:
        return ""
    return ""


def _write_snap_metadata(scene: Any, snap: HeadhookSnapResult) -> None:
    payload: Dict[str, Any] = {
        "ok": snap.ok,
        "code": snap.code,
        "headhook": snap.headhook,
        "headhook_name": snap.headhook_name,
        "head_root": _first_root_name(snap.head_model),
        "head_local_offset": snap.head_local_offset,
        "warnings": list(snap.warnings),
    }
    metadata = getattr(scene, "metadata", None)
    if metadata is None:
        scene.metadata = {}
        metadata = scene.metadata
    metadata["composite_snap"] = payload

    head = snap.head_model
    if head is not None:
        # Non-invasive attachment hints for the viewport/export layers.
        setattr(head, "composite_parent_hook", snap.headhook_name)
        setattr(head, "head_local_offset", snap.head_local_offset)
        setattr(head, "headhook_world_transform", snap.headhook)


def snap_head_to_body(
    scene: Any,
    *,
    build_preview: bool = True,
    update_metadata: bool = True,
) -> HeadhookSnapResult:
    """Recompute the active head/body snap.

    The scene must already have ``HEADLESS_BODY`` and ``HEAD_SHELL`` slots.
    When ``build_preview`` is true, the existing
    ``creature_appearance.snap_head_onto_body`` backend is used to create a
    cloned preview model for viewport display.
    """

    body, head = _slot_models(scene)
    if body is None:
        snap = HeadhookSnapResult(
            head_model=head,
            message="No body model loaded. Load a body before snapping a head.",
            code="no_body",
        )
        if update_metadata:
            _write_snap_metadata(scene, snap)
        return snap
    if head is None:
        snap = HeadhookSnapResult(
            body_model=body,
            message="No head model loaded. Load a head before snapping.",
            code="no_head",
        )
        if update_metadata:
            _write_snap_metadata(scene, snap)
        return snap

    try:
        cb = _import_character_builder()
        headhook = cb.find_headhook(body)
    except Exception as exc:                                # pragma: no cover
        log.debug("snap_head_to_body: find_headhook failed: %s", exc)
        headhook = None

    if not headhook:
        snap = HeadhookSnapResult(
            body_model=body,
            head_model=head,
            message="Body model has no usable headhook attachment.",
            code="headhook_missing",
        )
        if update_metadata:
            _write_snap_metadata(scene, snap)
        return snap

    position, rotation = headhook
    offset = _matrix_from_transform(position, rotation)
    preview_model = None
    warnings: List[str] = []

    if build_preview:
        try:
            ca = _import_creature_appearance()
            preview = ca.snap_head_onto_body(
                body,
                head,
                scale_head=False,
                merge_animations=False,
            )
            warnings.extend(list(preview.get("warnings", []) or []))
            if preview.get("ok"):
                preview_model = preview.get("model")
            else:
                warnings.append(str(preview.get("message", "preview snap failed")))
        except Exception as exc:                            # pragma: no cover
            log.debug("snap_head_to_body: preview build failed", exc_info=True)
            warnings.append(f"Preview snap failed: {exc}")

    snap = HeadhookSnapResult(
        ok=True,
        body_model=body,
        head_model=head,
        preview_model=preview_model,
        headhook=headhook,
        head_local_offset=offset,
        warnings=warnings,
        message="Composite snap ready at body headhook.",
        code="snapped",
    )
    if update_metadata:
        _write_snap_metadata(scene, snap)
    return snap


def load_composite(
    scene: Any,
    *,
    body_path: str,
    head_path: str,
    game_version: Optional[str] = None,
    build_preview: bool = True,
    allow_mode_correction: bool = False,
) -> CompositeResult:
    """Load body + head into the scene, then compute the headhook snap."""

    body_wf = _import_body_workflow()
    head_wf = _import_head_workflow()
    md = _import_model_data()

    body_result = body_wf.load_body(
        body_path,
        scene,
        game_version=game_version,
        allow_mode_correction=allow_mode_correction,
    )
    if not getattr(body_result, "ok", False):
        return CompositeResult(
            scene=scene,
            body_result=body_result,
            message=f"Composite load stopped at body: {getattr(body_result, 'message', '')}",
            code=getattr(body_result, "code", "body_failed") or "body_failed",
        )

    head_result = head_wf.load_head(
        head_path,
        scene,
        game_version=game_version,
        allow_mode_correction=allow_mode_correction,
    )
    if not getattr(head_result, "ok", False):
        return CompositeResult(
            scene=scene,
            body_result=body_result,
            head_result=head_result,
            message=f"Composite load stopped at head: {getattr(head_result, 'message', '')}",
            code=getattr(head_result, "code", "head_failed") or "head_failed",
        )

    if hasattr(scene, "set_mode"):
        scene.set_mode(md.CharacterMode.SUPERMODEL, locked=False)

    snap = snap_head_to_body(scene, build_preview=build_preview, update_metadata=True)
    if not snap.ok:
        return CompositeResult(
            scene=scene,
            body_result=body_result,
            head_result=head_result,
            snap=snap,
            message=snap.message,
            code=snap.code,
        )

    return CompositeResult(
        ok=True,
        scene=scene,
        body_result=body_result,
        head_result=head_result,
        snap=snap,
        message="Composite loaded and snapped.",
        code="loaded",
    )


def update_snap_after_scene_mutation(
    scene: Any,
    *,
    build_preview: bool = True,
) -> HeadhookSnapResult:
    """M7/T702 hook for UI mutations: recompute attachment metadata."""

    return snap_head_to_body(
        scene,
        build_preview=build_preview,
        update_metadata=True,
    )


__all__ = [
    "CompositeResult",
    "HeadhookSnapResult",
    "IDENTITY_MATRIX",
    "KOTOR_PC_SUPERMODELS",
    "load_composite",
    "snap_head_to_body",
    "update_snap_after_scene_mutation",
]
