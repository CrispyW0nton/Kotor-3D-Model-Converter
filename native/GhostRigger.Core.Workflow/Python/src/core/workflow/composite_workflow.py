"""
src/core/workflow/composite_workflow.py - Mode 3 (Supermodel Composite) service
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
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

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
        from src.core.geometry import model_data as _md             # type: ignore
    except ImportError:
        from core.geometry import model_data as _md                 # type: ignore
    return _md


def _import_body_workflow():                                # pragma: no cover - import shim
    try:
        from src.core.characters import headless_body_workflow as _wf  # type: ignore
    except ImportError:
        from core.characters import headless_body_workflow as _wf      # type: ignore
    return _wf


def _import_head_workflow():                                # pragma: no cover - import shim
    try:
        from src.core.characters import head_workflow as _wf           # type: ignore
    except ImportError:
        from core.characters import head_workflow as _wf               # type: ignore
    return _wf


def _import_character_builder():                            # pragma: no cover - import shim
    try:
        from src.core.characters import character_builder as _cb       # type: ignore
    except ImportError:
        from core.characters import character_builder as _cb           # type: ignore
    return _cb


def _import_validation_service():                           # pragma: no cover - import shim
    try:
        from src.core.diagnostics import validation_service as _vs      # type: ignore
    except ImportError:
        from core.diagnostics import validation_service as _vs          # type: ignore
    return _vs


def _import_workflow_base():                                # pragma: no cover - import shim
    try:
        from src.core.workflow import _workflow_base as _wb          # type: ignore
    except ImportError:
        from core.workflow import _workflow_base as _wb              # type: ignore
    return _wb


def _import_creature_appearance():                          # pragma: no cover - import shim
    try:
        from src.core.characters import creature_appearance as _ca     # type: ignore
    except ImportError:
        from core.characters import creature_appearance as _ca         # type: ignore
    return _ca


def _import_scene_io():                                     # pragma: no cover - import shim
    try:
        from src.core.geometry.model_data import SceneIO             # type: ignore
    except ImportError:
        from core.geometry.model_data import SceneIO                 # type: ignore
    return SceneIO


def _import_mesh_exporters():                               # pragma: no cover - import shim
    try:
        from src.converters.mesh_converter import (         # type: ignore
            FBXExporter,
            GLTFExporter,
            OBJExporter,
        )
    except ImportError:
        from converters.mesh_converter import (             # type: ignore
            FBXExporter,
            GLTFExporter,
            OBJExporter,
        )
    return FBXExporter, GLTFExporter, OBJExporter


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


@dataclass
class CompositeCheckResult:
    """Step-2 validation result for Supermodel composite mode."""

    ok: bool = True
    issues: List[Any] = field(default_factory=list)
    banner_key: str = "clean"
    summary: str = "CLEAN"
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    codes: set = field(default_factory=set)
    snap: HeadhookSnapResult = field(default_factory=HeadhookSnapResult)
    message: str = "Composite check clean."
    code: str = "clean"


@dataclass
class CompositeExportFormatResult:
    """Per-format row for Supermodel composite export."""

    key: str = ""
    label: str = ""
    ok: bool = False
    path: str = ""
    message: str = ""
    code: str = "exported"


@dataclass
class CompositeExportResult:
    """Result of writing a merged body/head interchange export."""

    ok: bool = False
    formats: List[CompositeExportFormatResult] = field(default_factory=list)
    sidecar_path: str = ""
    out_dir: str = ""
    message: str = ""
    code: str = "exported"


def _slot_models(scene: Any) -> Tuple[Optional[Any], Optional[Any]]:
    md = _import_model_data()
    body = scene.get_model(md.PartSlot.HEADLESS_BODY)
    head = scene.get_model(md.PartSlot.HEAD_SHELL)
    return body, head


def _make_issue(severity: str, code: str, message: str, slot=None, node: str = ""):
    vs = _import_validation_service()
    sev = {
        "error": vs.Severity.ERROR,
        "warning": vs.Severity.WARNING,
        "info": vs.Severity.INFO,
    }[severity]
    return vs.ValidationIssue(
        severity=sev,
        code=code,
        message=message,
        slot=slot,
        node=node,
    )


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


def _supermodel_value(model: Any) -> str:
    return (getattr(model, "supermodel", "") or "").strip().upper()


def _bounds(model: Any):
    if model is None:
        return None
    try:
        if hasattr(model, "compute_bounds"):
            model.compute_bounds()
    except Exception:
        pass
    bb_min = getattr(model, "bb_min", None)
    bb_max = getattr(model, "bb_max", None)
    if not bb_min or not bb_max:
        return None
    try:
        mn = (float(bb_min[0]), float(bb_min[1]), float(bb_min[2]))
        mx = (float(bb_max[0]), float(bb_max[1]), float(bb_max[2]))
    except Exception:
        return None
    if mn == (0.0, 0.0, 0.0) and mx == (0.0, 0.0, 0.0):
        return None
    return mn, mx


def _append_supermodel_issues(scene: Any, issues: List[Any], *, strict: bool) -> None:
    md = _import_model_data()
    body, head = _slot_models(scene)
    if body is None or head is None:
        return

    body_sm = _supermodel_value(body)
    head_sm = _supermodel_value(head)
    nulls = {"", "NULL", "NONE"}
    severity = "error" if strict else "warning"

    if body_sm in nulls:
        issues.append(_make_issue(
            severity,
            "SUPERMODEL_MISMATCH",
            "Body has no supermodel set. KOTOR body/head composites need a "
            "shared PC supermodel such as S_Female02 or S_Male02.",
            slot=md.PartSlot.HEADLESS_BODY,
        ))
    elif body_sm not in KOTOR_PC_SUPERMODELS:
        issues.append(_make_issue(
            severity,
            "SUPERMODEL_MISMATCH",
            f"Body supermodel '{body_sm}' is not a known PC base rig. "
            "Pick a KOTOR player/NPC body or retarget both models to "
            "S_Female02/S_Female03/S_Male02/S_Male03 before export.",
            slot=md.PartSlot.HEADLESS_BODY,
        ))

    if body_sm not in nulls and head_sm not in nulls and body_sm != head_sm:
        issues.append(_make_issue(
            severity,
            "SUPERMODEL_MISMATCH",
            f"Body and head supermodels differ: body={body_sm}, head={head_sm}. "
            "They must share the same supermodel or the face/body animations "
            "will not stay in sync in game.",
            slot=md.PartSlot.HEAD_SHELL,
        ))


def _append_seam_issue(scene: Any, snap: HeadhookSnapResult, issues: List[Any]) -> None:
    md = _import_model_data()
    if not snap.ok or snap.headhook is None or snap.head_model is None:
        return
    b = _bounds(snap.head_model)
    if b is None:
        return

    head_min, head_max = b
    hook_z = float(snap.headhook[0][2])
    root_z = float(snap.head_local_offset[2][3])
    lower_world_z = root_z + head_min[2]
    upper_world_z = root_z + head_max[2]

    tolerance_m = 0.02
    if (lower_world_z - tolerance_m) <= hook_z <= (upper_world_z + tolerance_m):
        return

    if hook_z < lower_world_z:
        gap = lower_world_z - hook_z
        direction = "above"
    else:
        gap = hook_z - upper_world_z
        direction = "below"

    issues.append(_make_issue(
        "warning",
        "SEAM_GAP",
        f"Head bounds sit {gap * 100.0:.1f} cm {direction} the body headhook "
        "plane. The preview may show a neck gap or clipping; check the head "
        "root/origin before exporting.",
        slot=md.PartSlot.HEAD_SHELL,
        node="headhook",
    ))


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


def check_composite(scene: Any, *, strict: bool = False) -> CompositeCheckResult:
    """Run Step 2 checks that matter for a body/head KOTOR composite."""

    body, head = _slot_models(scene)
    issues: List[Any] = []
    md = _import_model_data()

    if body is None:
        issues.append(_make_issue(
            "error",
            "COMPOSITE_BODY_MISSING",
            "Load a headless body first. KOTOR needs a body MDL with a headhook.",
            slot=md.PartSlot.HEADLESS_BODY,
        ))
    if head is None:
        issues.append(_make_issue(
            "error",
            "COMPOSITE_HEAD_MISSING",
            "Load a head model next. The composite preview needs both body and head.",
            slot=md.PartSlot.HEAD_SHELL,
        ))

    snap = update_snap_after_scene_mutation(scene, build_preview=False)
    if body is not None and head is not None and not snap.ok:
        issues.append(_make_issue(
            "error",
            "HEADHOOK_MISSING",
            snap.message or "Body model has no usable headhook attachment.",
            slot=md.PartSlot.HEADLESS_BODY,
            node="headhook",
        ))

    _append_supermodel_issues(scene, issues, strict=strict)
    _append_seam_issue(scene, snap, issues)

    wb = _import_workflow_base()
    banner, summary, errors, warnings, infos, codes = wb.summarize_issues(issues)
    if errors:
        message = f"Composite check blocked: {summary}."
        code = "blocked"
    elif warnings:
        message = f"Composite check found warnings: {summary}."
        code = "warnings_only"
    else:
        message = "Composite check clean: body/head snap and supermodel look usable."
        code = "clean"

    return CompositeCheckResult(
        ok=(errors == 0),
        issues=issues,
        banner_key=banner,
        summary=summary,
        error_count=errors,
        warning_count=warnings,
        info_count=infos,
        codes=codes,
        snap=snap,
        message=message,
        code=code,
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


def _scene_resref(scene: Any, body: Any, head: Any) -> str:
    md = _import_model_data()
    wb = _import_workflow_base()
    body_entry = scene.get(md.PartSlot.HEADLESS_BODY)
    head_entry = scene.get(md.PartSlot.HEAD_SHELL)
    body_ref = (
        getattr(body_entry, "resref", "")
        or getattr(body, "name", "")
        or "body"
    )
    head_ref = (
        getattr(head_entry, "resref", "")
        or getattr(head, "name", "")
        or "head"
    )
    return wb.safe_resref(f"{body_ref}_{head_ref}_composite", fallback="composite")


def _composite_export_model(scene: Any) -> Tuple[Optional[Any], List[str], str]:
    """Build the merged interchange model used by FBX/glTF export."""
    body, head = _slot_models(scene)
    if body is None or head is None:
        return None, [], "Composite export needs both body and head models."

    snap = snap_head_to_body(scene, build_preview=False, update_metadata=True)
    if not snap.ok:
        return None, list(snap.warnings), snap.message

    ca = _import_creature_appearance()
    merged = ca.snap_head_onto_body(
        body,
        head,
        scale_head=False,
        merge_animations=False,
    )
    warnings = list(merged.get("warnings", []) or [])
    model = merged.get("model") if merged.get("ok") else None
    if model is None:
        return None, warnings, str(merged.get("message", "Composite merge failed."))

    setattr(model, "name", _scene_resref(scene, body, head))
    return model, warnings, "Composite export model ready."


def _export_composite_single_format(
    model: Any,
    fmt_key: str,
    label: str,
    out_dir: str,
    resref: str,
    fbx_compatibility_profile: str = "standard",
    base_skeleton_model: Any = None,
    tex_cache: Any = None,
    fbx_animation_names: Optional[Sequence[str]] = None,
    animation_resource_manager: Any = None,
    animation_game: str = "",
    supplemental_animation_models: Sequence[Any] = (),
    primary_animation_model: Any = None,
) -> CompositeExportFormatResult:
    primary_ext = {
        "fbx": ".fbx",
        "gltf": ".glb",
    }.get(fmt_key, "")
    if not primary_ext:
        return CompositeExportFormatResult(
            key=fmt_key,
            label=label,
            ok=False,
            message=(
                f"Supermodel composite export supports FBX/glTF only; "
                f"'{fmt_key}' is not available for merged output."
            ),
            code="failed",
        )

    out_path = os.path.join(out_dir, f"{resref}{primary_ext}")
    try:
        fbx_cls, gltf_cls, _obj_cls = _import_mesh_exporters()
        if fmt_key == "fbx":
            fbx_model = model
            if fbx_animation_names is not None:
                try:
                    from src.core.animation.fbx_animation_selection import (
                        prepare_fbx_animation_export_model,
                    )
                except ImportError:  # pragma: no cover - package-relative fallback
                    from core.animation.fbx_animation_selection import (  # type: ignore
                        prepare_fbx_animation_export_model,
                    )
                fbx_model = prepare_fbx_animation_export_model(
                    model,
                    tuple(fbx_animation_names),
                    game=animation_game,
                    resource_manager=animation_resource_manager,
                    base_skeleton_model=base_skeleton_model,
                    supplemental_models=tuple(supplemental_animation_models or ()),
                    primary_model=primary_animation_model,
                    require_all=True,
                )
            ok = fbx_cls().export(
                fbx_model,
                out_path,
                tex_cache=tex_cache,
                base_skeleton_model=base_skeleton_model,
                compatibility_profile=fbx_compatibility_profile,
            )
            if ok is False:
                raise RuntimeError("FBX exporter returned False")
        elif fmt_key == "gltf":
            ok = gltf_cls().export(model, out_path, binary=True)
            if ok is False:
                raise RuntimeError("glTF exporter returned False")
    except Exception as exc:
        log.exception("export_composite_scene: %s writer failed", fmt_key)
        return CompositeExportFormatResult(
            key=fmt_key,
            label=label,
            ok=False,
            path=out_path,
            message=f"{label} composite export failed: {exc}",
            code="failed",
        )

    return CompositeExportFormatResult(
        key=fmt_key,
        label=label,
        ok=True,
        path=out_path,
        message=f"{label} composite exported to {out_path}.",
        code="exported",
    )


def export_composite_scene(
    scene: Any,
    *,
    formats: Optional[List[str]] = None,
    out_dir: str = "",
    write_sidecar: bool = True,
    skip_validation: bool = False,
    fbx_compatibility_profile: str = "standard",
    tex_cache: Any = None,
    fbx_animation_names: Optional[Sequence[str]] = None,
    animation_resource_manager: Any = None,
) -> CompositeExportResult:
    """M10/T1003: export a snapped Supermodel body/head as FBX/glTF."""
    body, head = _slot_models(scene)
    if body is None:
        return CompositeExportResult(
            message="No body model loaded — nothing to export.",
            code="no_body",
        )
    if head is None:
        return CompositeExportResult(
            message="No head model loaded — nothing to export.",
            code="no_head",
        )
    if not out_dir:
        return CompositeExportResult(
            message="No output directory supplied.",
            code="no_out_dir",
        )

    requested = list(formats or [])
    if not requested and not write_sidecar:
        return CompositeExportResult(
            out_dir=out_dir,
            message="Nothing requested — pick FBX/glTF or enable the sidecar JSON.",
            code="no_formats",
        )

    if not skip_validation:
        body_wf = _import_body_workflow()
        gate = body_wf.validate_for_export(scene, strict=True)
        if not getattr(gate, "ok", False):
            return CompositeExportResult(
                out_dir=out_dir,
                message=("Export blocked by validation: "
                         f"{getattr(gate, 'error_count', 0)} error(s). "
                         f"Codes: {', '.join(getattr(gate, 'blocking_codes', []))}"),
                code="blocked",
            )

    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as exc:
        return CompositeExportResult(
            out_dir=out_dir,
            message=f"Cannot create output directory: {exc}",
            code="no_out_dir",
        )

    model, warnings, merge_message = _composite_export_model(scene)
    if model is None:
        return CompositeExportResult(
            out_dir=out_dir,
            message=f"Composite export model could not be built: {merge_message}",
            code="merge_failed",
        )

    resref = _scene_resref(scene, body, head)
    label_by_key = {
        "fbx": "FBX (Autodesk)",
        "gltf": "glTF / GLB",
    }
    rows: List[CompositeExportFormatResult] = []
    for fmt_key in requested:
        label = label_by_key.get(fmt_key, fmt_key)
        rows.append(_export_composite_single_format(
            model,
            fmt_key,
            label,
            out_dir,
            resref,
            fbx_compatibility_profile,
            getattr(body, "_gr_fbx_base_skeleton_model", None),
            tex_cache,
            fbx_animation_names,
            animation_resource_manager,
            str(getattr(scene, "game_version", "") or "K1").upper(),
            (head,),
            body,
        ))

    sidecar_path = ""
    if write_sidecar:
        try:
            scene.metadata["composite_export"] = {
                "resref": resref,
                "warnings": warnings,
                "fbx_compatibility_profile": str(
                    fbx_compatibility_profile or "standard"
                ),
                "fbx_animation_names": (
                    None if fbx_animation_names is None else list(fbx_animation_names)
                ),
                "formats": [
                    {
                        "format": row.key,
                        "ok": bool(row.ok),
                        "path": row.path,
                        "code": row.code,
                        "message": row.message,
                    }
                    for row in rows
                ],
            }
            sio = _import_scene_io()
            anchor = os.path.join(out_dir, f"{resref}.fbx")
            sidecar_path = sio.write_sidecar(scene, anchor)
        except Exception as exc:                            # pragma: no cover
            log.exception("export_composite_scene: write_sidecar raised")
            rows.append(CompositeExportFormatResult(
                key="sidecar",
                label="Scene JSON sidecar",
                ok=False,
                message=f"Sidecar write failed: {exc}",
                code="failed",
            ))

    any_ok = any(row.ok for row in rows) or bool(sidecar_path)
    if rows and not any_ok and not sidecar_path:
        return CompositeExportResult(
            formats=rows,
            out_dir=out_dir,
            message="Every requested composite format failed.",
            code="all_failed",
        )

    ok_count = sum(1 for row in rows if row.ok)
    fail_count = sum(1 for row in rows if not row.ok)
    parts: List[str] = []
    if ok_count:
        parts.append(f"{ok_count} written")
    if fail_count:
        parts.append(f"{fail_count} failed")
    if sidecar_path:
        parts.append("sidecar written")
    if warnings:
        parts.append(f"{len(warnings)} warning(s)")

    return CompositeExportResult(
        ok=any_ok and fail_count == 0,
        formats=rows,
        sidecar_path=sidecar_path,
        out_dir=out_dir,
        message="Composite export complete — " + ", ".join(parts or ["nothing requested"]),
        code="exported" if any_ok and fail_count == 0 else "partial",
    )


__all__ = [
    "CompositeResult",
    "CompositeCheckResult",
    "CompositeExportFormatResult",
    "CompositeExportResult",
    "HeadhookSnapResult",
    "IDENTITY_MATRIX",
    "KOTOR_PC_SUPERMODELS",
    "check_composite",
    "export_composite_scene",
    "load_composite",
    "snap_head_to_body",
    "update_snap_after_scene_mutation",
]
