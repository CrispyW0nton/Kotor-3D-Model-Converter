"""
src/core/headless_body_workflow.py — Mode 1 (Headless Body) workflow service
============================================================================

This module implements the end-to-end *Headless Body* workflow defined by
M5 / T501-T506 of the Qt-ghostrigger roadmap.  It is a **pure-Python**
service layer that the Qt Character Builder window calls into; the layer
contains no Qt dependencies so it is fully unit-testable without a
display server.

The seven workflow steps mapped onto this module:

    Step 1  ── Load Body     →  :func:`load_body`
    Step 2  ── Check Model   →  :func:`check_model`        (T502)
    Step 3  ── Body Rig      →  :func:`place_body_guides`  (T503)
                              + :func:`generate_skeleton`   (T503)
    Step 4  ── Hand Rig      →  :func:`hand_rig`            (T504)
    Step 5  ── Check Actor   →  :func:`select_preview_animation`  (T505)
    Step 6  ── Add Motions   →  reuses :mod:`qt_animation_panel`
    Step 7  ── Validate +    →  :func:`validate_and_export` (T506)
              Export

Every public function returns a *result dataclass* carrying a structured
``ok`` flag plus a human-readable ``message``.  The Qt window converts
these into bottom-strip banner colours and status-bar messages without
needing to know how the underlying services are wired.

Roadmap reference: knowledge_base/roadmap/02_roadmap_2026_05.md M5/T501-T506.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
#  Lazy imports
# ──────────────────────────────────────────────────────────────────────
#
# We keep the *heavy* imports (model_data, validation_service, autorig)
# behind helper functions so this module can be imported in environments
# that lack PyKotor / OpenGL — the test suite uses this pattern to
# exercise the workflow logic in isolation.

def _import_model_data():                                   # pragma: no cover - import shim
    try:
        from src.core import model_data as _md             # type: ignore
    except ImportError:
        from core import model_data as _md                 # type: ignore
    return _md


def _import_validation_service():                           # pragma: no cover - import shim
    try:
        from src.core import validation_service as _vs    # type: ignore
    except ImportError:
        from core import validation_service as _vs         # type: ignore
    return _vs


def _import_character_builder():                            # pragma: no cover - import shim
    try:
        from src.core import character_builder as _cb      # type: ignore
    except ImportError:
        from core import character_builder as _cb          # type: ignore
    return _cb


# ──────────────────────────────────────────────────────────────────────
#  Supported input formats
# ──────────────────────────────────────────────────────────────────────

#: Extensions accepted by :func:`load_body`.  The detector keys off the
#: lower-cased suffix.
_MDL_EXTS  = (".mdl",)
_GLTF_EXTS = (".gltf", ".glb")
_FBX_EXTS  = (".fbx", ".obj", ".ply", ".stl")
_UTC_EXTS  = (".utc",)
_TEXTURE_EXTS = (".tga", ".tpc", ".png", ".dds", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")
_DEFAULT_KOTOR_HUMANOID_HEIGHT = 2.01345


def supported_load_extensions() -> Tuple[str, ...]:
    """Return the full tuple of file extensions :func:`load_body` accepts.

    The order is stable and used to build the Qt file-picker filter
    string ("Body models (*.mdl *.gltf *.glb *.fbx *.obj …)").
    """
    return _MDL_EXTS + _GLTF_EXTS + _FBX_EXTS + _UTC_EXTS


def load_file_filter() -> str:
    """Qt-compatible filter string for the Load-Body dialog.

    Example output::

        "Body models (*.mdl *.gltf *.glb *.fbx *.obj *.ply *.stl *.utc);;All files (*.*)"
    """
    patterns = " ".join(f"*{ext}" for ext in supported_load_extensions())
    return f"Body models ({patterns});;All files (*.*)"


# ──────────────────────────────────────────────────────────────────────
#  Result dataclasses
# ──────────────────────────────────────────────────────────────────────

@dataclass
class LoadResult:
    """Result of :func:`load_body`.

    Attributes
    ----------
    ok            : True when the model loaded *and* matched HEADLESS_BODY.
    model         : The loaded ``KotorModel`` (may be present even when
                    ``ok=False`` — e.g. a Head model was loaded by mistake;
                    the caller can offer to switch the active mode).
    detected_mode : The ``CharacterMode`` returned by ``detect_character_mode``.
    source_path   : Absolute path the file was read from.
    resref        : Lower-case resource reference (basename without ext).
    message       : Human-readable summary suitable for the status bar.
    code          : Stable machine tag: ``"loaded"``, ``"mode_mismatch"``,
                    ``"unsupported_format"``, ``"file_not_found"``,
                    ``"load_failed"``, ``"empty_path"``.
    """
    ok:            bool                        = False
    model:         Optional[Any]               = None         # KotorModel
    detected_mode: Optional[Any]               = None         # CharacterMode
    source_path:   str                         = ""
    resref:        str                         = ""
    message:       str                         = ""
    code:          str                         = "load_failed"


# ──────────────────────────────────────────────────────────────────────
#  Internal loader dispatch
# ──────────────────────────────────────────────────────────────────────

def _ext_of(path: str) -> str:
    return Path(path).suffix.lower()


def _resref_from_path(path: str) -> str:
    return Path(path).stem.lower()


def _load_mdl(path: str, game_version: str) -> Optional[Any]:
    """Load a KOTOR MDL/MDX pair via the kotor_loader bridge."""
    try:
        from src.core.kotor_loader import load_model_from_file
    except ImportError:                                     # pragma: no cover
        from core.kotor_loader import load_model_from_file  # type: ignore
    mdx = ""
    base, _ = os.path.splitext(path)
    cand = base + ".mdx"
    if os.path.isfile(cand):
        mdx = cand
    return load_model_from_file(path, mdx)


def _load_gltf_or_mesh(path: str, game_version: str) -> Optional[Any]:
    """Load a glTF/GLB/FBX/OBJ via the gltf_importer.auto_import dispatcher."""
    md = _import_model_data()
    try:
        from src.core.gltf_importer import auto_import
    except ImportError:                                     # pragma: no cover
        from core.gltf_importer import auto_import          # type: ignore
    gv = (md.GameVersion.K2
          if str(game_version).upper().endswith("2")
          else md.GameVersion.K1)
    return auto_import(path,
                       model_name=_resref_from_path(path),
                       game_version=gv)


def _iter_model_nodes(model: Any) -> List[Any]:
    try:
        return list(model.all_nodes())
    except Exception:
        root = getattr(model, "root_node", None)
        if root is None:
            return []
        out: List[Any] = []
        stack = [root]
        seen: set[int] = set()
        while stack:
            node = stack.pop()
            if node is None:
                continue
            nid = id(node)
            if nid in seen:
                continue
            seen.add(nid)
            out.append(node)
            stack.extend(reversed(list(getattr(node, "children", []) or [])))
        return out


def _vertex_bounds(model: Any) -> Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
    mins = [float("inf"), float("inf"), float("inf")]
    maxs = [float("-inf"), float("-inf"), float("-inf")]
    found = False
    for node in _iter_model_nodes(model):
        for vert in list(getattr(node, "vertices", []) or []):
            if len(vert) < 3:
                continue
            try:
                x, y, z = float(vert[0]), float(vert[1]), float(vert[2])
            except Exception:
                continue
            mins[0] = min(mins[0], x); mins[1] = min(mins[1], y); mins[2] = min(mins[2], z)
            maxs[0] = max(maxs[0], x); maxs[1] = max(maxs[1], y); maxs[2] = max(maxs[2], z)
            found = True
    if not found:
        return None
    return (tuple(mins), tuple(maxs))  # type: ignore[return-value]


def _model_bone_bounds(model: Any) -> Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
    mins = [float("inf"), float("inf"), float("inf")]
    maxs = [float("-inf"), float("-inf"), float("-inf")]
    found = False
    for node in _iter_model_nodes(model):
        try:
            if hasattr(node, "bone_world_position"):
                pos = node.bone_world_position()
            else:
                pos = getattr(node, "position", None)
            if pos is None or len(pos) < 3:
                continue
            x, y, z = float(pos[0]), float(pos[1]), float(pos[2])
        except Exception:
            continue
        mins[0] = min(mins[0], x); mins[1] = min(mins[1], y); mins[2] = min(mins[2], z)
        maxs[0] = max(maxs[0], x); maxs[1] = max(maxs[1], y); maxs[2] = max(maxs[2], z)
        found = True
    if not found:
        return None
    return (tuple(mins), tuple(maxs))  # type: ignore[return-value]


def _height_from_bounds(bounds: Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]) -> float:
    if bounds is None:
        return 0.0
    bb_min, bb_max = bounds
    try:
        return max(0.0, float(bb_max[2]) - float(bb_min[2]))
    except Exception:
        return 0.0


def reference_model_height(reference_model: Any) -> float:
    """Return the KOTOR-space height of a selected base skeleton/model."""
    mesh_height = _height_from_bounds(_vertex_bounds(reference_model))
    if mesh_height > 0.01:
        return mesh_height
    bone_height = _height_from_bounds(_model_bone_bounds(reference_model))
    if bone_height > 0.01:
        return bone_height
    return 0.0


def _kotor_template_humanoid_height(game_version: str) -> float:
    """Fallback KOTOR humanoid height when no selected base model is loaded."""
    try:
        gv = str(game_version).upper()
        if gv in {"K1", "KOTOR1", "1", "K2", "TSL", "KOTOR2", "2"}:
            return _DEFAULT_KOTOR_HUMANOID_HEIGHT
    except Exception:
        pass
    return _DEFAULT_KOTOR_HUMANOID_HEIGHT


def _axis_map_to_kotor_z(point: Tuple[float, float, float], vertical_axis: int) -> Tuple[float, float, float]:
    """Map the detected source up-axis to KOTOR Z-up while keeping handedness."""
    x, y, z = point
    if vertical_axis == 1:  # Y-up external model -> KOTOR Z-up
        return (x, z, y)
    if vertical_axis == 0:  # X-up external model -> KOTOR Z-up
        return (y, z, x)
    return (x, y, z)


def _transform_point_for_kotor(
    point: Tuple[float, float, float],
    *,
    vertical_axis: int,
    scale: float,
    offset: Tuple[float, float, float],
) -> Tuple[float, float, float]:
    mapped = _axis_map_to_kotor_z(point, vertical_axis)
    return (
        mapped[0] * scale + offset[0],
        mapped[1] * scale + offset[1],
        mapped[2] * scale + offset[2],
    )


def normalize_external_model_for_kotor(
    model: Any,
    *,
    game_version: str = "K1",
    target_height: Optional[float] = None,
    reference_model: Optional[Any] = None,
    reference_label: str = "",
) -> Dict[str, Any]:
    """Scale and orient an imported external mesh into KOTOR humanoid space.

    External FBX/glTF files often arrive in DCC/game-engine units, e.g. Unreal
    Manny at ~8.9 units tall.  The best fitting target is the user-selected
    KOTOR base model/supermodel; when one is unavailable we fall back to the
    canonical humanoid height so guide placement still lands in Odyssey space.
    """
    bounds = _vertex_bounds(model)
    if bounds is None:
        return {"ok": False, "code": "no_vertices", "message": "No vertex bounds."}

    bb_min, bb_max = bounds
    extents = tuple(max(0.0, bb_max[i] - bb_min[i]) for i in range(3))
    vertical_axis = max(range(3), key=lambda i: extents[i])
    source_height = max(extents[vertical_axis], 1e-6)
    reference_height = reference_model_height(reference_model) if reference_model is not None else 0.0
    target = float(target_height or reference_height or _kotor_template_humanoid_height(game_version))
    scale = target / source_height if source_height > 1e-6 else 1.0

    mapped_min = _axis_map_to_kotor_z(bb_min, vertical_axis)
    mapped_max = _axis_map_to_kotor_z(bb_max, vertical_axis)
    norm_min = tuple(min(mapped_min[i], mapped_max[i]) for i in range(3))
    norm_max = tuple(max(mapped_min[i], mapped_max[i]) for i in range(3))
    center_x = (norm_min[0] + norm_max[0]) * 0.5
    center_y = (norm_min[1] + norm_max[1]) * 0.5
    offset = (-center_x * scale, -center_y * scale, -norm_min[2] * scale)

    for node in _iter_model_nodes(model):
        pos = getattr(node, "position", None)
        if pos is not None and len(pos) >= 3:
            try:
                node.position = _transform_point_for_kotor(
                    (float(pos[0]), float(pos[1]), float(pos[2])),
                    vertical_axis=vertical_axis,
                    scale=scale,
                    offset=(0.0, 0.0, 0.0),
                )
            except Exception:
                pass

        external_wp = getattr(node, "external_world_position", None)
        if external_wp is not None and len(external_wp) >= 3:
            try:
                node.external_world_position = _transform_point_for_kotor(
                    (float(external_wp[0]), float(external_wp[1]), float(external_wp[2])),
                    vertical_axis=vertical_axis,
                    scale=scale,
                    offset=offset,
                )
            except Exception:
                pass

        verts = list(getattr(node, "vertices", []) or [])
        if verts:
            new_verts = []
            for vert in verts:
                try:
                    new_verts.append(_transform_point_for_kotor(
                        (float(vert[0]), float(vert[1]), float(vert[2])),
                        vertical_axis=vertical_axis,
                        scale=scale,
                        offset=offset,
                    ))
                except Exception:
                    new_verts.append(vert)
            node.vertices = new_verts
            try:
                node.compute_bounds()
            except Exception:
                pass

        normals = list(getattr(node, "normals", []) or [])
        if normals and vertical_axis != 2:
            new_normals = []
            for normal in normals:
                try:
                    new_normals.append(_axis_map_to_kotor_z(
                        (float(normal[0]), float(normal[1]), float(normal[2])),
                        vertical_axis,
                    ))
                except Exception:
                    new_normals.append(normal)
            node.normals = new_normals

    try:
        model.compute_bounds()
    except Exception:
        b = _vertex_bounds(model)
        if b is not None:
            model.bb_min, model.bb_max = b

    metadata = getattr(model, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
        setattr(model, "metadata", metadata)
    result = {
        "ok": True,
        "code": "normalized",
        "scale": scale,
        "source_height": source_height,
        "target_height": target,
        "reference": reference_label or getattr(reference_model, "name", "") or "",
        "vertical_axis": ("x", "y", "z")[vertical_axis],
        "offset": offset,
    }
    metadata["kotor_normalization"] = result
    return result


def _load_utc(path: str, game_version: str) -> Optional[Any]:
    """Resolve a UTC's appearance and load the resulting body MDL.

    This is the ``creature_appearance.resolve_utc_appearance_from_library``
    path called out in the T501 acceptance criteria.  When the UTC
    resolves to a body resref, we try to load it from the configured
    KOTOR installation; if no installation library is set, we raise
    :class:`NotImplementedError` so the caller can fall back to a
    direct MDL pick.

    The ``creature_appearance`` import is deferred to inside this
    helper so test environments without PyKotor can still exercise the
    "no library configured" failure path without dragging the loader
    chain into the import graph.
    """
    if not os.path.isfile(path):
        return None
    # The full UTC → library → MDL chain depends on a configured
    # installation library that must be wired by the host application
    # (see knowledge_base/qt_workflows.md for the contract).  Surface a
    # clear NotImplementedError so the Qt window can offer a direct
    # body-MDL file picker as the fallback.
    raise NotImplementedError(
        "UTC-driven load requires a configured KOTOR installation "
        "(creature_appearance.resolve_utc_appearance_from_library). "
        "Pick a body MDL directly for now."
    )


# ──────────────────────────────────────────────────────────────────────
#  T501 — Load Body
# ──────────────────────────────────────────────────────────────────────

def load_body(
    path: str,
    scene: Any,
    *,
    game_version: Optional[str] = None,
    allow_mode_correction: bool = False,
    fit_reference_model: Optional[Any] = None,
    fit_reference_label: str = "",
) -> LoadResult:
    """Load a body model from *path* and assign it to *scene*.

    This is the entry point for **Workflow Step 1 (Load Body)** in the
    Mode-1 (Headless Body) workflow.  Acceptance per T501:

      * MDL path uses ``pykotor_bridge.load_model_from_file`` (which
        re-exports ``kotor_loader.load_model_from_file``);
      * UTC path resolves through ``creature_appearance``; if no library
        is configured the caller falls back to a direct MDL load;
      * glTF / GLB / FBX / OBJ / PLY paths use
        ``gltf_importer.auto_import``;
      * the result is unconditionally assigned to
        ``PartSlot.HEADLESS_BODY`` so the scene reflects user intent;
      * when the auto-detected mode is *not* HEADLESS_BODY, the result
        is flagged ``ok=False`` (``code="mode_mismatch"``) so the UI
        can show a correction banner.  When
        ``allow_mode_correction=True`` the caller is responsible for
        switching the scene's mode; the slot is still populated either
        way so the user can see what they loaded.

    Parameters
    ----------
    path                  : Absolute path to the source file.
    scene                 : A :class:`CharacterScene` instance.  The
                            scene's slot dict is mutated in place.
    game_version          : ``"K1"`` or ``"K2"``.  Defaults to
                            ``scene.game_version``.
    allow_mode_correction : When True, a mode mismatch is *not* a
                            failure — the slot is assigned and the
                            caller can react to ``detected_mode``.
    fit_reference_model   : Optional real KOTOR model/skeleton chosen by
                            the user before import.  External meshes are
                            scaled/oriented to this reference instead of a
                            generic humanoid fallback.
    """
    if not path:
        return LoadResult(message="No file path given.", code="empty_path")
    if not os.path.isfile(path):
        return LoadResult(
            source_path=path,
            message=f"File not found: {path}",
            code="file_not_found",
        )

    md = _import_model_data()
    gv = (game_version or getattr(scene, "game_version", "K1") or "K1").upper()
    ext = _ext_of(path)

    # ── Dispatch ────────────────────────────────────────────────────
    try:
        if ext in _MDL_EXTS:
            model = _load_mdl(path, gv)
        elif ext in _GLTF_EXTS or ext in _FBX_EXTS:
            model = _load_gltf_or_mesh(path, gv)
        elif ext in _UTC_EXTS:
            model = _load_utc(path, gv)
        else:
            return LoadResult(
                source_path=path,
                message=f"Unsupported format: {ext or '(no extension)'}",
                code="unsupported_format",
            )
    except NotImplementedError as exc:
        return LoadResult(
            source_path=path,
            message=str(exc),
            code="load_failed",
        )
    except Exception as exc:                                # pragma: no cover - loader-specific
        log.exception("load_body: importer raised on %s", path)
        return LoadResult(
            source_path=path,
            message=f"Load failed: {exc}",
            code="load_failed",
        )

    if model is None:
        return LoadResult(
            source_path=path,
            message="Importer returned no model.",
            code="load_failed",
        )

    normalization: Dict[str, Any] = {}
    if ext in _GLTF_EXTS or ext in _FBX_EXTS:
        normalization = normalize_external_model_for_kotor(
            model,
            game_version=gv,
            reference_model=fit_reference_model,
            reference_label=fit_reference_label,
        )

    # ── Detect mode ─────────────────────────────────────────────────
    try:
        detected = md.detect_character_mode(model)
    except Exception:                                       # pragma: no cover
        detected = md.CharacterMode.AMBIGUOUS

    # ── Assign to scene ─────────────────────────────────────────────
    resref = _resref_from_path(path)
    scene.assign(
        md.PartSlot.HEADLESS_BODY, model,
        resref=resref,
        game_version=gv,
        source_path=path,
    )

    # ── Verdict ─────────────────────────────────────────────────────
    if detected == md.CharacterMode.HEADLESS_BODY:
        return LoadResult(
            ok=True, model=model, detected_mode=detected,
            source_path=path, resref=resref,
            message=f"Loaded headless body: {resref} ({Path(path).name})",
            code="loaded",
        )

    # Custom OBJ/FBX/glTF bodies often arrive from Blender without KOTOR hook
    # names yet.  That is exactly the M12 skeleton-template workflow: load the
    # external mesh first, then let the user apply a known-good KOTOR skeleton.
    if detected == md.CharacterMode.AMBIGUOUS and (ext in _GLTF_EXTS or ext in _FBX_EXTS):
        scale_msg = ""
        if normalization.get("ok"):
            scale_msg = (
                f" Fit to {normalization.get('reference') or 'KOTOR scale'} "
                f"({float(normalization.get('scale', 1.0)):.3f}x)."
            )
        return LoadResult(
            ok=True, model=model, detected_mode=detected,
            source_path=path, resref=resref,
            message=(
                f"Loaded external mesh: {resref} ({Path(path).name}). "
                "Choose a KOTOR base skeleton before rigging."
                f"{scale_msg}"
            ),
            code="loaded",
        )

    # Mode mismatch — surface the suggested mode so the UI can offer to
    # switch.  When the caller opted into mode correction, we treat the
    # load as successful (the scene already has the slot assigned).
    suggest = getattr(detected, "display_name", str(detected))
    msg = (f"Loaded {Path(path).name}, but it looks like a {suggest} model "
           f"(expected Headless Body).")
    return LoadResult(
        ok=allow_mode_correction,
        model=model, detected_mode=detected,
        source_path=path, resref=resref,
        message=msg,
        code="loaded" if allow_mode_correction else "mode_mismatch",
    )


# ──────────────────────────────────────────────────────────────────────
#  T502 — Check Model
# ──────────────────────────────────────────────────────────────────────
#
# Wraps the existing :class:`ValidationService` and projects its
# findings into a banner-ready ``CheckModelResult``.  The acceptance
# criterion is "all 10 issue codes surface correctly":
#
#   1.  NO_GEOMETRY             — model has no mesh nodes
#   2.  K1_K2_MISMATCH          — slots belong to different game versions
#   3.  SUPERMODEL_MISMATCH     — slot supermodels disagree
#   4.  SUPERMODEL_UNKNOWN      — supermodel string not in known list
#   5.  HOOK_MISSING            — headhook / rhand / talkdummy absent
#   6.  BONE_MISSING            — expected bone (e.g. lshoulder) absent
#   7.  SKIN_MESH_UNRIGGED      — mesh has no skin_data
#   8.  WEIGHT_OVERFLOW         — vertex has > 4 influences
#   9.  WEIGHT_ZERO_SUM         — vertex weights sum to 0
#  10.  WEIGHT_UNNORMALIZED     — weights don't sum to 1.0
#
# (WEIGHT_ERRORS_TRUNCATED is an INFO-severity summary, not a finding.)

# Severity → banner key mapping consumed by the Qt bottom-strip's
# ``set_validation(severity, summary, issues)`` API.
_BANNER_KEY_FOR_SEVERITY = {
    "error":   "error",
    "warning": "warning",
    "info":    "info",
}


@dataclass
class CheckModelResult:
    """Result of :func:`check_model`.

    Attributes
    ----------
    ok          : True when no ERROR-severity issues were found.  WARNINGs
                  do not flip this False (the export step gates on its own
                  re-validation).
    issues      : Full list of :class:`ValidationIssue` instances.
    banner_key  : Banner severity tag — one of ``"clean" / "info" /
                  "warning" / "error"``.
    summary     : Short banner text, e.g. ``"3 errors, 2 warnings"``.
    error_count / warning_count / info_count : Per-severity tallies.
    codes       : ``set[str]`` of distinct issue codes found
                  (handy for tests that assert which checks fired).
    """
    ok:            bool                                  = True
    issues:        List[Any]                             = field(default_factory=list)
    banner_key:    str                                   = "clean"
    summary:       str                                   = "CLEAN"
    error_count:   int                                   = 0
    warning_count: int                                   = 0
    info_count:    int                                   = 0
    codes:         set                                   = field(default_factory=set)


def _summarize_issues(issues: List[Any]) -> Tuple[str, str, int, int, int, set]:
    """Reduce a list of ValidationIssues into a banner-ready tuple.

    Returns ``(banner_key, summary, errors, warnings, infos, codes)``.
    """
    errs = warns = infos = 0
    codes: set = set()
    for issue in issues:
        sev = getattr(issue, "severity", None)
        sev_value = getattr(sev, "value", str(sev)).lower()
        if sev_value == "error":
            errs += 1
        elif sev_value == "warning":
            warns += 1
        elif sev_value == "info":
            infos += 1
        code = getattr(issue, "code", "")
        if code:
            codes.add(code)

    if errs:
        key = "error"
    elif warns:
        key = "warning"
    elif infos:
        key = "info"
    else:
        key = "clean"

    parts: List[str] = []
    if errs:
        parts.append(f"{errs} error{'s' if errs != 1 else ''}")
    if warns:
        parts.append(f"{warns} warning{'s' if warns != 1 else ''}")
    if infos and not (errs or warns):
        parts.append(f"{infos} info")
    summary = ", ".join(parts).upper() if parts else "CLEAN"

    return key, summary, errs, warns, infos, codes


def check_model(scene: Any, *, strict: bool = False) -> CheckModelResult:
    """Workflow Step 2 (Check Model) — M5 / T502.

    Runs :class:`ValidationService` over *scene* and reduces the
    resulting issue list to a banner-friendly summary.  The Qt window
    calls this from ``_on_check_model_requested`` and pushes the
    result straight into ``bottom_strip.set_validation(...)``.

    Parameters
    ----------
    scene  : :class:`CharacterScene` to validate.
    strict : When True, several WARNINGs are promoted to ERRORs (passed
             through to ``ValidationService(strict=...)``).
    """
    # Defensive: an empty scene yields no issues but isn't really
    # 'clean' from the user's perspective.  Surface that explicitly.
    if scene is None or not getattr(scene, "slots", None):
        return CheckModelResult(
            ok=False,
            issues=[],
            banner_key="warning",
            summary="NO MODEL LOADED",
        )

    try:
        vs_mod = _import_validation_service()
        service = vs_mod.ValidationService(scene, strict=strict)
        issues = service.validate()
    except Exception as exc:                                # pragma: no cover
        log.exception("check_model: ValidationService raised")
        return CheckModelResult(
            ok=False,
            issues=[],
            banner_key="error",
            summary=f"CHECK FAILED: {exc}",
        )

    key, summary, errs, warns, infos, codes = _summarize_issues(issues)
    return CheckModelResult(
        ok=(errs == 0),
        issues=issues,
        banner_key=key,
        summary=summary,
        error_count=errs,
        warning_count=warns,
        info_count=infos,
        codes=codes,
    )


# ──────────────────────────────────────────────────────────────────────
#  T503 — Body Rig
# ──────────────────────────────────────────────────────────────────────
#
# Step 3 of the Headless-Body workflow places AcuRig guide pins for
# the humanoid profile, lets the user nudge them via the joint-dot
# HUD (M4 / T402), then generates the skeleton + heat-map weights.
#
# The service module owns only the *headless* business logic.  The
# Qt window is responsible for binding the guide-drag UX to T402's
# hit-tester / mirror logic and forwarding the final guide dict back
# here for skeleton generation.

def _import_accurig():                                      # pragma: no cover - import shim
    try:
        from src.autorig import accurig as _ar             # type: ignore
    except ImportError:
        from autorig import accurig as _ar                 # type: ignore
    return _ar


@dataclass
class BodyRigGuidesResult:
    """Result of :func:`place_body_guides`.

    Attributes
    ----------
    ok          : True when guides were successfully placed.
    guides      : ``Dict[str, RigGuide]`` keyed by joint name
                  (root / hip / chest / lshoulder / rshoulder / …).
    profile     : The detected/used AcuRig profile (``"humanoid"``).
    acurig      : The :class:`AcuRig` instance — kept on the result so
                  the caller can forward it back to
                  :func:`generate_skeleton` (avoids re-running profile
                  detection a second time).
    message     : Human-readable summary for the status bar.
    """
    ok:       bool                                   = False
    guides:   Dict[str, Any]                         = field(default_factory=dict)
    profile:  str                                    = ""
    acurig:   Optional[Any]                          = None
    message:  str                                    = ""


@dataclass
class BodyRigGenerateResult:
    """Result of :func:`generate_skeleton`.

    Attributes
    ----------
    ok                : True when build + skin succeeded.
    bone_count        : Number of bones in the generated skeleton.
    vertices_skinned  : Total vertex count that received heat-map
                        weights.
    message           : Human-readable summary.
    code              : Stable tag — ``"generated" / "no_body" /
                        "no_guides" / "build_failed" / "skin_failed"``.
    """
    ok:                bool       = False
    bone_count:        int        = 0
    vertices_skinned:  int        = 0
    message:           str        = ""
    code:              str        = "generated"


@dataclass
class BodyGuideEditResult:
    """Result of persisting a manual HUD joint/guide edit (M12/T1203)."""

    ok:             bool           = False
    guide_name:     str            = ""
    position:       Tuple[float, float, float] = (0.0, 0.0, 0.0)
    guides:         Dict[str, Any] = field(default_factory=dict)
    acurig:         Optional[Any]  = None
    updated_guides: List[str]      = field(default_factory=list)
    before_positions: Dict[str, Tuple[float, float, float]] = field(default_factory=dict)
    after_positions:  Dict[str, Tuple[float, float, float]] = field(default_factory=dict)
    can_undo:      bool           = False
    can_redo:      bool           = False
    message:        str            = ""
    code:           str            = "updated"


@dataclass
class BodyGuideEditCommand:
    """One undoable body-guide edit command."""

    guide_name: str = ""
    before: Dict[str, Tuple[float, float, float]] = field(default_factory=dict)
    after:  Dict[str, Tuple[float, float, float]] = field(default_factory=dict)


@dataclass
class BodyGuideEditHistory:
    """Undo/redo stack for AccuRig guide edits."""

    undo_stack: List[BodyGuideEditCommand] = field(default_factory=list)
    redo_stack: List[BodyGuideEditCommand] = field(default_factory=list)
    limit: int = 50

    @property
    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self.redo_stack)


def _get_body_model(scene: Any) -> Optional[Any]:
    md = _import_model_data()
    return scene.get_model(md.PartSlot.HEADLESS_BODY)


def _get_head_model(scene: Any) -> Optional[Any]:
    md = _import_model_data()
    return scene.get_model(md.PartSlot.HEAD_SHELL)


def _coerce_position3(position: Any) -> Optional[Tuple[float, float, float]]:
    try:
        values = tuple(position)
    except Exception:
        return None
    if len(values) < 3:
        return None
    try:
        return (float(values[0]), float(values[1]), float(values[2]))
    except (TypeError, ValueError):
        return None


def _snapshot_guide_positions(guides: Dict[str, Any]) -> Dict[str, Tuple[float, float, float]]:
    positions: Dict[str, Tuple[float, float, float]] = {}
    for name, guide in (guides or {}).items():
        pos = _coerce_position3(getattr(guide, "position", None))
        if pos is not None:
            positions[str(name)] = pos
    return positions


def _history_flags(history: Optional[BodyGuideEditHistory]) -> Tuple[bool, bool]:
    if history is None:
        return False, False
    return bool(history.can_undo), bool(history.can_redo)


def update_body_guide(
    acurig: Any,
    guide_name: str,
    position: Any,
    *,
    auto_mirror: bool = False,
) -> BodyGuideEditResult:
    """Persist a manual body guide edit into the live AcuRig instance.

    T1203's UX rule is simple: when a user drags an AccuRig-style
    joint dot, the next :func:`generate_skeleton` call must use that
    position.  AcuRig already models this via ``move_guide`` +
    ``locked=True``; this adapter normalizes names/positions and
    returns a status object that the Qt layer can surface.
    """
    name = (guide_name or "").strip().lower()
    if acurig is None:
        return BodyGuideEditResult(
            guide_name=name,
            message="No AcuRig guide state yet. Click Place Body Guides first.",
            code="no_acurig",
        )
    if not name:
        return BodyGuideEditResult(
            acurig=acurig,
            message="No guide name supplied.",
            code="no_name",
        )

    pos = _coerce_position3(position)
    if pos is None:
        return BodyGuideEditResult(
            acurig=acurig,
            guide_name=name,
            message=f"Guide '{name}' has no valid 3D position.",
            code="bad_position",
        )

    before = {}
    if hasattr(acurig, "get_all_guides"):
        try:
            before = dict(acurig.get_all_guides() or {})
        except Exception:
            before = {}
    if before and name not in before:
        return BodyGuideEditResult(
            acurig=acurig,
            guide_name=name,
            position=pos,
            guides=before,
            message=f"'{name}' is not a body guide for the current AcuRig profile.",
            code="unknown_guide",
        )
    before_positions = {
        gname: getattr(guide, "position", None)
        for gname, guide in before.items()
    }
    before_snapshot = _snapshot_guide_positions(before)

    try:
        if hasattr(acurig, "move_guide"):
            acurig.move_guide(name, pos, auto_mirror=auto_mirror)
        elif before and name in before:                    # pragma: no cover
            guide = before[name]
            guide.position = pos
            guide.locked = True
        else:                                              # pragma: no cover
            return BodyGuideEditResult(
                acurig=acurig,
                guide_name=name,
                position=pos,
                message="AcuRig guide state does not support manual edits.",
                code="unsupported",
            )
    except Exception as exc:                               # pragma: no cover
        log.exception("update_body_guide: AcuRig guide update failed")
        return BodyGuideEditResult(
            acurig=acurig,
            guide_name=name,
            position=pos,
            message=f"Guide update failed: {exc}",
            code="failed",
        )

    after = {}
    if hasattr(acurig, "get_all_guides"):
        try:
            after = dict(acurig.get_all_guides() or {})
        except Exception:                                  # pragma: no cover
            after = {}

    changed: List[str] = []
    for gname, guide in after.items():
        old_pos = before_positions.get(gname)
        new_pos = getattr(guide, "position", None)
        if gname not in before_positions or old_pos != new_pos:
            changed.append(str(gname))
    if name not in changed:
        changed.insert(0, name)
    after_snapshot_all = _snapshot_guide_positions(after)
    before_changed = {
        gname: before_snapshot[gname]
        for gname in changed
        if gname in before_snapshot
    }
    after_changed = {
        gname: after_snapshot_all[gname]
        for gname in changed
        if gname in after_snapshot_all
    }

    return BodyGuideEditResult(
        ok=True,
        acurig=acurig,
        guide_name=name,
        position=pos,
        guides=after,
        updated_guides=changed,
        before_positions=before_changed,
        after_positions=after_changed,
        message=f"Guide '{name}' locked at ({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f}).",
        code="updated",
    )


def update_body_guide_from_node(
    acurig: Any,
    node: Any,
    *,
    auto_mirror: bool = False,
) -> BodyGuideEditResult:
    """Persist a moved viewport node as an AcuRig guide edit."""
    name = getattr(node, "name", "") or ""
    position = getattr(node, "position", None)
    return update_body_guide(
        acurig,
        str(name),
        position,
        auto_mirror=auto_mirror,
    )


def record_body_guide_edit(
    history: Optional[BodyGuideEditHistory],
    result: BodyGuideEditResult,
) -> BodyGuideEditHistory:
    """Record a successful guide edit as an undoable command."""
    if history is None:
        history = BodyGuideEditHistory()
    if not getattr(result, "ok", False):
        return history
    before = dict(getattr(result, "before_positions", {}) or {})
    after = dict(getattr(result, "after_positions", {}) or {})
    if not before or not after or before == after:
        return history
    history.undo_stack.append(BodyGuideEditCommand(
        guide_name=getattr(result, "guide_name", ""),
        before=before,
        after=after,
    ))
    history.redo_stack.clear()
    if history.limit > 0 and len(history.undo_stack) > history.limit:
        del history.undo_stack[0:len(history.undo_stack) - history.limit]
    return history


def apply_body_guide_positions(
    acurig: Any,
    positions: Dict[str, Any],
) -> BodyGuideEditResult:
    """Apply exact guide positions without auto-mirroring."""
    if acurig is None:
        return BodyGuideEditResult(
            message="No AcuRig guide state yet. Click Place Body Guides first.",
            code="no_acurig",
        )
    normalized: Dict[str, Tuple[float, float, float]] = {}
    for name, pos in (positions or {}).items():
        coerced = _coerce_position3(pos)
        if coerced is not None:
            normalized[str(name).lower()] = coerced
    if not normalized:
        return BodyGuideEditResult(
            acurig=acurig,
            message="No guide positions supplied.",
            code="no_positions",
        )

    before = {}
    if hasattr(acurig, "get_all_guides"):
        try:
            before = dict(acurig.get_all_guides() or {})
        except Exception:
            before = {}
    before_snapshot = _snapshot_guide_positions(before)

    try:
        for name, pos in normalized.items():
            if hasattr(acurig, "move_guide"):
                acurig.move_guide(name, pos, auto_mirror=False)
            elif before and name in before:                # pragma: no cover
                before[name].position = pos
                before[name].locked = True
            else:                                          # pragma: no cover
                return BodyGuideEditResult(
                    acurig=acurig,
                    guide_name=name,
                    position=pos,
                    message="AcuRig guide state does not support manual edits.",
                    code="unsupported",
                )
    except Exception as exc:                               # pragma: no cover
        log.exception("apply_body_guide_positions: AcuRig guide update failed")
        return BodyGuideEditResult(
            acurig=acurig,
            message=f"Guide position apply failed: {exc}",
            code="failed",
        )

    after = {}
    if hasattr(acurig, "get_all_guides"):
        try:
            after = dict(acurig.get_all_guides() or {})
        except Exception:
            after = {}
    after_snapshot = _snapshot_guide_positions(after)
    updated = [
        name for name, pos in normalized.items()
        if before_snapshot.get(name) != after_snapshot.get(name)
    ] or list(normalized.keys())
    return BodyGuideEditResult(
        ok=True,
        acurig=acurig,
        guide_name=updated[0] if updated else "",
        position=normalized.get(updated[0], (0.0, 0.0, 0.0)) if updated else (0.0, 0.0, 0.0),
        guides=after,
        updated_guides=updated,
        before_positions={k: before_snapshot[k] for k in updated if k in before_snapshot},
        after_positions={k: after_snapshot[k] for k in updated if k in after_snapshot},
        message=f"Applied {len(updated)} guide position(s).",
        code="applied",
    )


def undo_body_guide_edit(
    acurig: Any,
    history: Optional[BodyGuideEditHistory],
) -> BodyGuideEditResult:
    """Undo the latest recorded body guide edit."""
    can_undo, can_redo = _history_flags(history)
    if history is None or not can_undo:
        return BodyGuideEditResult(
            acurig=acurig,
            can_undo=False,
            can_redo=can_redo,
            message="No guide edit to undo.",
            code="no_undo",
        )
    command = history.undo_stack.pop()
    result = apply_body_guide_positions(acurig, command.before)
    if not result.ok:
        history.undo_stack.append(command)
        result.can_undo = history.can_undo
        result.can_redo = history.can_redo
        return result
    history.redo_stack.append(command)
    result.guide_name = command.guide_name
    result.can_undo = history.can_undo
    result.can_redo = history.can_redo
    result.message = f"Undid guide edit: {command.guide_name}."
    result.code = "undone"
    return result


def redo_body_guide_edit(
    acurig: Any,
    history: Optional[BodyGuideEditHistory],
) -> BodyGuideEditResult:
    """Redo the latest undone body guide edit."""
    can_undo, can_redo = _history_flags(history)
    if history is None or not can_redo:
        return BodyGuideEditResult(
            acurig=acurig,
            can_undo=can_undo,
            can_redo=False,
            message="No guide edit to redo.",
            code="no_redo",
        )
    command = history.redo_stack.pop()
    result = apply_body_guide_positions(acurig, command.after)
    if not result.ok:
        history.redo_stack.append(command)
        result.can_undo = history.can_undo
        result.can_redo = history.can_redo
        return result
    history.undo_stack.append(command)
    result.guide_name = command.guide_name
    result.can_undo = history.can_undo
    result.can_redo = history.can_redo
    result.message = f"Redid guide edit: {command.guide_name}."
    result.code = "redone"
    return result


def place_body_guides(
    scene: Any,
    *,
    snap_to_bones: bool = True,
    acurig: Optional[Any] = None,
) -> BodyRigGuidesResult:
    """Workflow Step 3a — place AcuRig humanoid guides on the body.

    Wraps ``AcuRig.place_guides(model, profile=PROFILE_HUMANOID)``.
    Acceptance per T503: "guides snap to existing bones when present;
    otherwise sit at canonical humanoid-template positions scaled to
    the model's height".

    Parameters
    ----------
    scene          : :class:`CharacterScene` that must already have a
                     ``PartSlot.HEADLESS_BODY`` slot assigned.
    snap_to_bones  : Forwarded to ``AcuRig.place_guides``.  When True,
                     each guide auto-snaps to the nearest existing bone
                     within the configured radius (improves accuracy
                     on models that already have a rough skeleton).
    acurig         : Optional existing :class:`AcuRig` instance.  Pass
                     this in on subsequent calls to keep user-locked
                     guide overrides between the *Place Guides* and
                     *Generate Skeleton* clicks.
    """
    body = _get_body_model(scene)
    if body is None:
        return BodyRigGuidesResult(
            message="No body model loaded.  Load a body first.",
        )

    try:
        ar_mod = _import_accurig()
    except Exception as exc:                                # pragma: no cover
        return BodyRigGuidesResult(
            message=f"AcuRig module unavailable: {exc}",
        )

    if acurig is None:
        acurig = ar_mod.AcuRig()

    profile = ar_mod.PROFILE_HUMANOID
    try:
        guides = acurig.place_guides(body, profile=profile,
                                     snap_to_bones=snap_to_bones)
    except Exception as exc:                                # pragma: no cover
        log.exception("place_body_guides: AcuRig.place_guides raised")
        return BodyRigGuidesResult(
            message=f"Guide placement failed: {exc}",
        )

    return BodyRigGuidesResult(
        ok=True,
        guides=guides,
        profile=profile,
        acurig=acurig,
        message=f"Placed {len(guides)} humanoid guide(s).",
    )


def generate_skeleton(
    scene: Any,
    *,
    acurig: Optional[Any] = None,
    guides: Optional[Dict[str, Any]] = None,
    smooth_iterations: int = 2,
) -> BodyRigGenerateResult:
    """Workflow Step 3b — Generate Skeleton button.

    Runs ``AcuRig.generate_rig`` (== ``accurig.build_skeleton`` in the
    roadmap wording) and then ``AcuRig.auto_skin`` (== ``heat_weights``)
    to produce a fully-rigged, heat-painted body model.

    Parameters
    ----------
    scene             : Scene with the body slot populated.
    acurig            : The :class:`AcuRig` instance from
                        :func:`place_body_guides` — passing it through
                        preserves user-locked guide positions.  When
                        ``None``, a fresh instance is created.
    guides            : Optional explicit guide dict (e.g. mutated by
                        the joint-dot HUD's drag-with-mirror UX).
                        When ``None``, the AcuRig instance uses its
                        internal state.
    smooth_iterations : Number of heat-map smoothing passes
                        (forwarded to ``WeightPainter.smooth_weights``).
    """
    body = _get_body_model(scene)
    if body is None:
        return BodyRigGenerateResult(
            message="No body model loaded.",
            code="no_body",
        )

    try:
        ar_mod = _import_accurig()
    except Exception as exc:                                # pragma: no cover
        return BodyRigGenerateResult(
            message=f"AcuRig module unavailable: {exc}",
            code="build_failed",
        )

    if acurig is None:
        acurig = ar_mod.AcuRig()
        # Without prior place_guides, we need *some* guides.
        if not guides:
            try:
                guides = acurig.place_guides(body,
                                             profile=ar_mod.PROFILE_HUMANOID,
                                             snap_to_bones=True)
            except Exception as exc:                        # pragma: no cover
                return BodyRigGenerateResult(
                    message=f"Guide placement failed: {exc}",
                    code="no_guides",
                )

    # ── Build skeleton ──────────────────────────────────────────────
    try:
        rigged = acurig.generate_rig(body, guides=guides)
    except Exception as exc:                                # pragma: no cover
        log.exception("generate_skeleton: generate_rig raised")
        return BodyRigGenerateResult(
            message=f"Skeleton build failed: {exc}",
            code="build_failed",
        )

    # Count bones in the active guide map (== the active mask).
    if guides is None:
        guides = acurig.get_all_guides() if hasattr(acurig, "get_all_guides") else {}
    bone_count = len(guides or {})

    # ── Heat-map skinning ───────────────────────────────────────────
    try:
        verts_skinned = acurig.auto_skin(
            rigged,
            guides=guides,
            smooth_iterations=smooth_iterations,
        )
    except Exception as exc:                                # pragma: no cover
        log.exception("generate_skeleton: auto_skin raised")
        return BodyRigGenerateResult(
            ok=False, bone_count=bone_count,
            message=f"Skin painting failed: {exc}",
            code="skin_failed",
        )

    # Update the scene's slot.model in case generate_rig replaced it.
    md = _import_model_data()
    entry = scene.get(md.PartSlot.HEADLESS_BODY)
    if entry is not None and rigged is not None:
        entry.model = rigged
        entry.dirty = True
        scene.dirty = True

    return BodyRigGenerateResult(
        ok=True,
        bone_count=bone_count,
        vertices_skinned=int(verts_skinned or 0),
        message=(f"Generated skeleton with {bone_count} bone(s); "
                 f"skinned {verts_skinned} vertices."),
        code="generated",
    )


# ─────────────────────────────────────────────────────────────────────────────
#  T504 ▸ Hand-Rig step
# ─────────────────────────────────────────────────────────────────────────────
#
# The KOTOR humanoid skeleton uses a single primary finger bone per hand
# (``lfinger01`` / ``rfinger01``), plus the wrist (``lhand`` / ``rhand``)
# and forearm (``lforearm`` / ``rforearm``).  T504's job is to expose
# those six bones in the inspector as per-bone mask checkboxes, so the
# user can mute weight-painting on any of them before kicking off the
# heat-map smoothing pass.
#
# Public surface:
#   • HAND_BONES                      — the six bones the UI shows.
#   • HandRigResult                   — structured result for both calls.
#   • place_hand_guides(scene, *)     — refresh the AcuRig hand guides.
#   • apply_hand_masks(scene, *)      — push the checkbox state into
#                                       ``AcuRig.mask`` (BoneMask).

HAND_BONES: Tuple[str, ...] = (
    "lforearm", "lhand", "lfinger01",
    "rforearm", "rhand", "rfinger01",
)


@dataclass
class HandRigResult:
    """Result of :func:`place_hand_guides` / :func:`apply_hand_masks`.

    Attributes
    ----------
    ok             : True when the operation completed cleanly.
    guides         : ``Dict[str, RigGuide]`` for the six hand bones —
                     empty when ``ok is False``.
    masked_bones   : Sorted list of bone names currently masked on the
                     AcuRig instance.  Mirrors the checkbox state.
    acurig         : The :class:`AcuRig` instance — preserved so the
                     window can pass it back on the next call without
                     re-running profile detection.
    message        : Human-readable summary for the status bar.
    code           : Stable tag — ``"placed" / "masked" / "no_body" /
                     "no_acurig" / "failed"``.
    """
    ok:           bool                                   = False
    guides:       Dict[str, Any]                         = field(default_factory=dict)
    masked_bones: List[str]                              = field(default_factory=list)
    acurig:       Optional[Any]                          = None
    message:      str                                    = ""
    code:         str                                    = "placed"


def place_hand_guides(
    scene: Any,
    *,
    acurig: Optional[Any] = None,
    snap_to_bones: bool = True,
) -> HandRigResult:
    """Workflow Step 4a — refresh AcuRig humanoid guides and isolate the hand subset.

    Re-runs ``AcuRig.place_guides`` so the wrist / finger pins re-snap
    to the latest bone positions (useful after the body skeleton has
    been generated and the user wants to fine-tune hands separately).
    Returns only the six hand-relevant guides for the inspector to
    drive.
    """
    body = _get_body_model(scene)
    if body is None:
        return HandRigResult(
            message="No body model loaded.  Load a body first.",
            code="no_body",
        )

    try:
        ar_mod = _import_accurig()
    except Exception as exc:                                # pragma: no cover
        return HandRigResult(
            message=f"AcuRig module unavailable: {exc}",
            code="no_acurig",
        )

    if acurig is None:
        acurig = ar_mod.AcuRig()

    try:
        all_guides = acurig.place_guides(
            body,
            profile=ar_mod.PROFILE_HUMANOID,
            snap_to_bones=snap_to_bones,
        )
    except Exception as exc:                                # pragma: no cover
        log.exception("place_hand_guides: AcuRig.place_guides raised")
        return HandRigResult(
            message=f"Hand-guide placement failed: {exc}",
            code="failed",
        )

    hand_guides = {
        name: guide for name, guide in (all_guides or {}).items()
        if name in HAND_BONES
    }
    # Surface whatever mask state the AcuRig already has — the UI uses
    # this to pre-populate its checkboxes on first paint.
    masked = _read_masked_bones(acurig)

    return HandRigResult(
        ok=True,
        guides=hand_guides,
        masked_bones=masked,
        acurig=acurig,
        message=(f"Placed {len(hand_guides)} hand-rig guide(s); "
                 f"{len(masked)} bone(s) currently masked."),
        code="placed",
    )


def apply_hand_masks(
    scene: Any,
    *,
    acurig: Optional[Any] = None,
    masked_bones: Optional[List[str]] = None,
) -> HandRigResult:
    """Workflow Step 4b — push the per-bone mask checkbox state into AcuRig.

    Clears the AcuRig's :class:`BoneMask` and re-applies exactly the
    bones listed in ``masked_bones``.  Only bones in :data:`HAND_BONES`
    are accepted (the body-level mask is owned by :func:`generate_skeleton`,
    not this step).

    Parameters
    ----------
    scene         : Scene whose body slot must be populated.
    acurig        : Required.  Reuse the instance from
                    :func:`place_hand_guides` so the mask survives
                    between checkbox toggles.
    masked_bones  : Iterable of bone names to mask.  Anything outside
                    :data:`HAND_BONES` is silently ignored.
    """
    body = _get_body_model(scene)
    if body is None:
        return HandRigResult(
            message="No body model loaded.",
            code="no_body",
        )

    if acurig is None:
        return HandRigResult(
            message="No AcuRig instance — click Place Hand Guides first.",
            code="no_acurig",
        )

    mask = getattr(acurig, "mask", None)
    if mask is None:                                        # pragma: no cover
        return HandRigResult(
            message="AcuRig has no BoneMask attribute.",
            code="failed",
        )

    requested = [b for b in (masked_bones or []) if b in HAND_BONES]

    try:
        # Non-hand bones (e.g. user previously masked the tail) must be
        # preserved — so only re-key the hand subset.
        for bone in HAND_BONES:
            if hasattr(mask, "is_masked") and mask.is_masked(bone) \
                    and bone not in requested:
                if hasattr(mask, "unmask"):
                    mask.unmask(bone)
                else:                                       # fallback for
                    # older BoneMask without ``unmask``: clear + re-apply
                    # the full intended set.
                    if hasattr(mask, "clear"):
                        mask.clear()
                    for b in requested:
                        mask.mask(b)
                    break
        for bone in requested:
            if not (hasattr(mask, "is_masked") and mask.is_masked(bone)):
                mask.mask(bone)
    except Exception as exc:                                # pragma: no cover
        log.exception("apply_hand_masks: mask manipulation raised")
        return HandRigResult(
            message=f"Failed to apply hand masks: {exc}",
            code="failed",
            acurig=acurig,
        )

    masked = _read_masked_bones(acurig)
    return HandRigResult(
        ok=True,
        guides={},                                          # caller still has them
        masked_bones=masked,
        acurig=acurig,
        message=(f"Hand masks updated — {len(masked)} bone(s) currently masked."),
        code="masked",
    )


def _read_masked_bones(acurig: Any) -> List[str]:
    """Best-effort accessor for ``AcuRig.mask.masked_bones``."""
    mask = getattr(acurig, "mask", None)
    if mask is None:                                        # pragma: no cover
        return []
    bones = getattr(mask, "masked_bones", None)
    if callable(bones):
        try:
            bones = bones()
        except Exception:                                   # pragma: no cover
            return []
    if bones is None:                                       # pragma: no cover
        return []
    return sorted(str(b) for b in bones)


# ─────────────────────────────────────────────────────────────────────────────
#  T505 ▸ Check-Actor step
# ─────────────────────────────────────────────────────────────────────────────
#
# The Check-Actor step lets the user preview a small, curated set of
# preview animations on the rigged body — walk / idle / talk — to
# verify the skeleton + heat-map weights look right under motion.
# These names come from the canonical KOTOR humanoid animation list
# (``template_builder._ANIM_SLOTS``).
#
# Public surface:
#   • PREVIEW_ANIMATIONS              — short tuple of (label, anim_name).
#   • CheckActorResult                — structured result for both calls.
#   • available_preview_animations()  — which previews exist on the model.
#   • play_preview_animation()        — look up the named anim + dispatch
#                                       it to the viewport if one is given.

# (Display label, actual animation name from _ANIM_SLOTS).
# The order is intentional — these are the most-used preview slots when
# QC-ing a freshly-rigged body.
PREVIEW_ANIMATIONS: Tuple[Tuple[str, str], ...] = (
    ("Idle",  "pause1"),
    ("Walk",  "walk"),
    ("Run",   "run"),
    ("Talk",  "tlknorm"),
    ("Dodge", "dodge"),
)

MOTION_SOURCE_MODEL = "model"
MOTION_SOURCE_INHERITED = "inherited_supermodel"
MOTION_SOURCE_IMPORTED = "imported"
MOTION_SOURCE_ROM = "generated_rom"

MOTION_SOURCE_LABELS: Dict[str, str] = {
    MOTION_SOURCE_INHERITED: "Inherit PC supermodel",
    MOTION_SOURCE_MODEL: "Use model clips",
    MOTION_SOURCE_IMPORTED: "Imported clips",
    MOTION_SOURCE_ROM: "Generated ROM",
}

PC_SUPERMODEL_OPTIONS: Tuple[Tuple[str, str, str], ...] = (
    ("K1 Female PC", "S_Female02", "K1"),
    ("K1 Female PC extended", "S_Female03", "K1"),
    ("K1 Male PC", "S_Male02", "K1"),
    ("K1 Male PC extended", "S_Male03", "K1"),
    ("K2 Female PC", "S_Female02", "K2"),
    ("K2 Female PC extended", "S_Female03", "K2"),
    ("K2 Male PC", "S_Male02", "K2"),
    ("K2 Male PC extended", "S_Male03", "K2"),
)


@dataclass
class MotionAssignmentResult:
    """Result of M12/T1204 motion assignment.

    The state is stored on ``scene.motion_assignment`` as a plain dict so
    older CharacterScene versions can participate without a schema bump.
    """
    ok:         bool                              = False
    source:     str                               = MOTION_SOURCE_MODEL
    supermodel: str                               = ""
    available:  List[Tuple[str, str]]             = field(default_factory=list)
    missing:    List[Tuple[str, str]]             = field(default_factory=list)
    message:    str                               = ""
    code:       str                               = "motion_assignment"


@dataclass
class CheckActorResult:
    """Result of :func:`available_preview_animations` /
    :func:`play_preview_animation`.

    Attributes
    ----------
    ok               : True when the operation succeeded.
    available        : List of ``(label, name)`` tuples present on the
                       body model — a subset of :data:`PREVIEW_ANIMATIONS`.
    missing          : Names from :data:`PREVIEW_ANIMATIONS` *not* found
                       on the model — useful for the UI to grey out.
    playing          : Name of the animation currently dispatched to
                       the viewport (or empty string).
    length           : Length in seconds of the playing animation (or 0).
    message          : Human-readable summary.
    code             : Stable tag — ``"listed" / "playing" / "stopped" /
                       "no_body" / "no_animations" / "anim_missing"``.
    """
    ok:         bool                              = False
    available:  List[Tuple[str, str]]             = field(default_factory=list)
    missing:    List[Tuple[str, str]]             = field(default_factory=list)
    playing:    str                               = ""
    length:     float                             = 0.0
    message:    str                               = ""
    code:       str                               = "listed"


def _motion_assignment_state(scene: Any) -> Dict[str, Any]:
    state = getattr(scene, "motion_assignment", None)
    if isinstance(state, dict):
        return dict(state)
    return {}


def _write_motion_assignment_state(scene: Any, state: Dict[str, Any]) -> None:
    try:
        setattr(scene, "motion_assignment", dict(state))
        setattr(scene, "dirty", True)
    except Exception:                                      # pragma: no cover
        log.debug("Could not persist motion assignment on scene", exc_info=True)


def _is_null_supermodel(value: str) -> bool:
    return (value or "").strip().upper() in {"", "NULL", "NONE"}


def _body_supermodel(body: Any) -> str:
    return str(getattr(body, "supermodel", "") or "").strip()


def motion_assignment_options(scene: Any) -> MotionAssignmentResult:
    """Return the currently selected motion source and preview split."""
    body = _get_body_model(scene)
    if body is None:
        return MotionAssignmentResult(
            message="No body model loaded. Load a body before assigning motions.",
            code="no_body",
        )

    state = _motion_assignment_state(scene)
    source = str(state.get("source") or MOTION_SOURCE_MODEL)
    supermodel = str(state.get("supermodel") or _body_supermodel(body))
    preview = available_preview_animations(scene)
    return MotionAssignmentResult(
        ok=True,
        source=source,
        supermodel=supermodel,
        available=list(preview.available),
        missing=list(preview.missing),
        message=preview.message,
        code="listed",
    )


def _normalise_imported_clips(imported_clips: Optional[Any]) -> List[str]:
    if imported_clips is None:
        return []
    names: List[str] = []
    for item in imported_clips:
        if isinstance(item, str):
            name = item
        else:
            name = str(getattr(item, "name", "") or getattr(item, "anim_name", ""))
        name = name.strip()
        if name:
            names.append(name)
    return names


def assign_motion_source(
    scene: Any,
    source: str,
    *,
    supermodel: str = "",
    imported_clips: Optional[Any] = None,
) -> MotionAssignmentResult:
    """M12/T1204: assign how this body obtains animation clips.

    ``inherited_supermodel`` mirrors normal KOTOR body behavior: the
    body MDL stores a supermodel string while the engine resolves clips
    from that parent at runtime.
    """
    body = _get_body_model(scene)
    if body is None:
        return MotionAssignmentResult(
            source=source or MOTION_SOURCE_MODEL,
            message="No body model loaded. Load a body before assigning motions.",
            code="no_body",
        )

    source = (source or MOTION_SOURCE_MODEL).strip()
    if source not in MOTION_SOURCE_LABELS:
        return MotionAssignmentResult(
            source=source,
            message=f"Unknown motion source '{source}'.",
            code="unknown_source",
        )

    clips = _normalise_imported_clips(imported_clips)
    state: Dict[str, Any] = {"source": source}

    if source == MOTION_SOURCE_INHERITED:
        selected = (supermodel or _body_supermodel(body) or "S_Female02").strip()
        if _is_null_supermodel(selected):
            selected = "S_Female02"
        setattr(body, "supermodel", selected)
        state["supermodel"] = selected
        message = (
            f"Motions will inherit from {selected}; KOTOR will resolve "
            "idle, walk, talk, and combat clips through the supermodel."
        )
        code = "inherited"
    elif source == MOTION_SOURCE_MODEL:
        state["supermodel"] = _body_supermodel(body)
        message = "Motions will use animation clips stored on this model."
        code = "model_clips"
    elif source == MOTION_SOURCE_IMPORTED:
        state["imported_clips"] = clips
        state["supermodel"] = _body_supermodel(body)
        message = (
            f"{len(clips)} imported clip(s) assigned."
            if clips else
            "Imported-clips source selected; import clips before export."
        )
        code = "imported_clips" if clips else "imported_empty"
    else:
        state["supermodel"] = _body_supermodel(body)
        state["generated"] = True
        message = "Generated ROM clip assigned for range-of-motion preview."
        code = "generated_rom"

    _write_motion_assignment_state(scene, state)
    preview = available_preview_animations(scene)
    return MotionAssignmentResult(
        ok=True,
        source=source,
        supermodel=str(state.get("supermodel") or ""),
        available=list(preview.available),
        missing=list(preview.missing),
        message=message,
        code=code,
    )


def _iter_model_animations(model: Any) -> List[Any]:
    """Best-effort accessor for ``KotorModel.animations`` — returns the
    list (possibly empty) of :class:`Animation` objects on the model.
    Survives ducks that name the attribute slightly differently.
    """
    for attr in ("animations", "anims", "animation_list"):
        anims = getattr(model, attr, None)
        if anims is not None:
            try:
                return list(anims)
            except Exception:                               # pragma: no cover
                return []
    return []


def available_preview_animations(scene: Any) -> CheckActorResult:
    """Workflow Step 5a — enumerate preview animations on the body model.

    Walks ``model.animations`` and splits :data:`PREVIEW_ANIMATIONS`
    into ``available`` (found) vs ``missing`` (not found).  Returns
    structured codes so the UI can grey-out missing previews and offer
    a helpful banner when none of the standard set are present.
    """
    body = _get_body_model(scene)
    if body is None:
        return CheckActorResult(
            message="No body model loaded.  Load a body first.",
            code="no_body",
        )

    motion_state = _motion_assignment_state(scene)
    motion_source = str(motion_state.get("source") or "")
    if motion_source == MOTION_SOURCE_INHERITED:
        supermodel = str(motion_state.get("supermodel") or _body_supermodel(body))
        if not _is_null_supermodel(supermodel):
            return CheckActorResult(
                ok=True,
                available=list(PREVIEW_ANIMATIONS),
                missing=[],
                message=(
                    f"Preview clips inherit from {supermodel}; "
                    f"{len(PREVIEW_ANIMATIONS)} standard KOTOR clips available."
                ),
                code="inherited",
            )
    if motion_source == MOTION_SOURCE_IMPORTED:
        imported = {
            name.lower()
            for name in _normalise_imported_clips(
                motion_state.get("imported_clips") or []
            )
        }
        available = [
            (label, anim_name)
            for label, anim_name in PREVIEW_ANIMATIONS
            if anim_name.lower() in imported
        ]
        missing = [
            (label, anim_name)
            for label, anim_name in PREVIEW_ANIMATIONS
            if anim_name.lower() not in imported
        ]
        return CheckActorResult(
            ok=True,
            available=available,
            missing=missing,
            message=(
                f"{len(available)} imported preview clip(s) assigned; "
                f"{len(missing)} standard clip(s) still missing."
            ),
            code=("listed" if available else "no_animations"),
        )
    if motion_source == MOTION_SOURCE_ROM:
        return CheckActorResult(
            ok=True,
            available=[("ROM Test", "generated_rom")],
            missing=list(PREVIEW_ANIMATIONS),
            message="Generated ROM is assigned; standard locomotion clips are still missing.",
            code="generated_rom",
        )

    anims = _iter_model_animations(body)
    names = {getattr(a, "name", "").lower() for a in anims if a is not None}

    available: List[Tuple[str, str]] = []
    missing:   List[Tuple[str, str]] = []
    for label, anim_name in PREVIEW_ANIMATIONS:
        if anim_name.lower() in names:
            available.append((label, anim_name))
        else:
            missing.append((label, anim_name))

    if not anims:
        return CheckActorResult(
            ok=True,
            available=[],
            missing=list(PREVIEW_ANIMATIONS),
            message=("Model has no animations — none of the standard "
                     "preview clips can be played."),
            code="no_animations",
        )

    if not available:
        return CheckActorResult(
            ok=True,
            available=[],
            missing=missing,
            message=(f"Model has {len(anims)} animation(s) but none of the "
                     f"standard preview clips "
                     f"({', '.join(n for _, n in PREVIEW_ANIMATIONS)}) "
                     "are present."),
            code="no_animations",
        )

    return CheckActorResult(
        ok=True,
        available=available,
        missing=missing,
        message=(f"{len(available)} preview clip(s) available; "
                 f"{len(missing)} missing."),
        code="listed",
    )


def play_preview_animation(
    scene: Any,
    anim_name: str,
    *,
    viewport: Optional[Any] = None,
) -> CheckActorResult:
    """Workflow Step 5b — dispatch a preview animation to the viewport.

    Looks up *anim_name* on the body model and calls
    ``viewport.set_animation_pose(animation, name=anim_name,
    time=0.0, length=animation.length)`` so the M4 renderer starts
    playing it.

    Parameters
    ----------
    scene      : Scene that must already have a body slot populated.
    anim_name  : Animation name, e.g. ``"walk"`` / ``"pause1"`` /
                 ``"tlknorm"`` — matched case-insensitively against
                 ``model.animations[i].name``.
    viewport   : The Qt viewport widget.  Optional — when ``None``,
                 the workflow just confirms the animation exists
                 (useful for headless tests).
    """
    body = _get_body_model(scene)
    if body is None:
        return CheckActorResult(
            message="No body model loaded.",
            code="no_body",
        )

    target = (anim_name or "").lower().strip()
    if not target:
        return CheckActorResult(
            message="No animation name supplied.",
            code="anim_missing",
        )

    chosen = None
    for a in _iter_model_animations(body):
        if getattr(a, "name", "").lower() == target:
            chosen = a
            break

    if chosen is None:
        motion_state = _motion_assignment_state(scene)
        motion_source = str(motion_state.get("source") or "")
        if motion_source == MOTION_SOURCE_INHERITED:
            requested = {name.lower(): label for label, name in PREVIEW_ANIMATIONS}
            if target in requested:
                supermodel = str(
                    motion_state.get("supermodel") or _body_supermodel(body)
                )
                return CheckActorResult(
                    ok=True,
                    available=list(PREVIEW_ANIMATIONS),
                    playing=anim_name,
                    length=0.0,
                    message=(
                        f"'{anim_name}' is inherited from {supermodel}. "
                        "Export will reference the supermodel; exact playback "
                        "requires loading the supermodel clip."
                    ),
                    code="inherited_preview",
                )
        if motion_source == MOTION_SOURCE_ROM and target == "generated_rom":
            return CheckActorResult(
                ok=True,
                available=[("ROM Test", "generated_rom")],
                playing="generated_rom",
                length=4.0,
                message="Generated ROM preview selected.",
                code="generated_rom",
            )
        return CheckActorResult(
            message=f"Animation '{anim_name}' is not present on this model.",
            code="anim_missing",
        )

    length = float(getattr(chosen, "length", 0.0) or 0.0)

    # Dispatch to the viewport when we have one.  Done last so we
    # always return a structured result even if the dispatch raises.
    if viewport is not None and hasattr(viewport, "set_animation_pose"):
        try:
            viewport.set_animation_pose(
                chosen,
                name=getattr(chosen, "name", anim_name),
                time=0.0,
                length=length,
            )
        except Exception as exc:                            # pragma: no cover
            log.exception("play_preview_animation: viewport dispatch raised")
            return CheckActorResult(
                playing="",
                length=length,
                message=(f"Animation '{anim_name}' found but viewport "
                         f"dispatch failed: {exc}"),
                code="anim_missing",
            )

    return CheckActorResult(
        ok=True,
        playing=getattr(chosen, "name", anim_name),
        length=length,
        message=f"Playing '{anim_name}' ({length:.2f}s).",
        code="playing",
    )


def run_rom_test(scene: Any, *, viewport: Optional[Any] = None) -> CheckActorResult:
    """M9/T903 — assign and start the generated ROM preview.

    This is the launch-path bridge until M8's full Stewart Jones ROM
    generator lands.  It records the generated-ROM motion source on the
    scene, exposes a ``generated_rom`` preview clip, and nudges the
    viewport/bottom strip into a four-second ROM playback state.
    """
    assigned = assign_motion_source(scene, MOTION_SOURCE_ROM)
    if not assigned.ok:
        return CheckActorResult(
            message=assigned.message,
            code=assigned.code,
        )

    result = play_preview_animation(scene, "generated_rom", viewport=None)
    if viewport is not None and hasattr(viewport, "set_animation_pose"):
        try:
            viewport.set_animation_pose(
                None,
                name="generated_rom",
                time=0.0,
                length=result.length or 4.0,
            )
        except Exception as exc:                            # pragma: no cover
            log.exception("run_rom_test: viewport dispatch raised")
            return CheckActorResult(
                available=result.available,
                playing="",
                length=result.length or 4.0,
                message=f"Generated ROM assigned but viewport dispatch failed: {exc}",
                code="anim_missing",
            )

    return CheckActorResult(
        ok=result.ok,
        available=[("ROM Test", "generated_rom")],
        missing=list(PREVIEW_ANIMATIONS),
        playing="generated_rom",
        length=result.length or 4.0,
        message="Running generated ROM test for range-of-motion validation.",
        code="generated_rom",
    )


def stop_preview_animation(viewport: Optional[Any] = None) -> CheckActorResult:
    """Workflow Step 5c — stop the currently-playing preview animation.

    Calls ``viewport.set_animation_pose(None)`` per the existing
    viewport contract (line 988 of qt_viewport.py).  Returns a
    structured ``stopped`` code so the UI can refresh.
    """
    if viewport is not None and hasattr(viewport, "set_animation_pose"):
        try:
            viewport.set_animation_pose(None)
        except Exception as exc:                            # pragma: no cover
            log.exception("stop_preview_animation: viewport dispatch raised")
            return CheckActorResult(
                message=f"Failed to stop animation: {exc}",
                code="anim_missing",
            )
    return CheckActorResult(
        ok=True,
        message="Stopped preview animation.",
        code="stopped",
    )


@dataclass
class _WorkflowSeverity:
    value: str


@dataclass
class _WorkflowIssue:
    severity: _WorkflowSeverity
    code: str
    message: str
    slot: Any = None
    node: str = ""


def _motion_assignment_issues(scene: Any) -> List[Any]:
    """Pre-export motion checks for the external-mesh launch path."""
    body = _get_body_model(scene)
    if body is None:
        return []

    state = _motion_assignment_state(scene)
    source = str(state.get("source") or "")
    supermodel = str(state.get("supermodel") or _body_supermodel(body))
    local_anims = _iter_model_animations(body)

    if source == MOTION_SOURCE_INHERITED:
        if not _is_null_supermodel(supermodel):
            return []
        return [_WorkflowIssue(
            _WorkflowSeverity("error"),
            "MOTIONS_MISSING",
            "Inherited motions selected, but no KOTOR supermodel is assigned.",
        )]

    if source == MOTION_SOURCE_IMPORTED:
        clips = _normalise_imported_clips(state.get("imported_clips") or [])
        if clips:
            return []
        return [_WorkflowIssue(
            _WorkflowSeverity("error"),
            "MOTIONS_MISSING",
            "Imported motion source selected, but no imported clips are assigned.",
        )]

    if local_anims:
        return []
    if not _is_null_supermodel(supermodel):
        return []

    return [_WorkflowIssue(
        _WorkflowSeverity("error"),
        "MOTIONS_MISSING",
        "No model clips or inherited KOTOR supermodel motions are assigned.",
    )]


def _scene_mode_value(scene: Any) -> str:
    mode = getattr(scene, "mode", "")
    return (
        getattr(mode, "value", None)
        or getattr(mode, "name", "")
        or str(mode or "")
    ).lower()


def _animation_names(model: Any) -> List[str]:
    return [
        str(getattr(anim, "name", "") or "").strip().lower()
        for anim in _iter_model_animations(model)
        if str(getattr(anim, "name", "") or "").strip()
    ]


def _per_mode_export_issues(scene: Any) -> List[Any]:
    """M10/T1005 mode-specific blockers that validation_service cannot infer."""
    mode = _scene_mode_value(scene)
    issues: List[Any] = []

    if mode == "head":
        head = _get_head_model(scene)
        names = _animation_names(head) if head is not None else []
        if not any(name == "talk" or name.startswith("tlk") for name in names):
            issues.append(_WorkflowIssue(
                _WorkflowSeverity("error"),
                "TALK_ANIMATION_MISSING",
                "Head export requires a talk animation for KOTOR LIP/viseme playback.",
                node="talkdummy",
            ))

    if mode == "supermodel":
        snap = getattr(scene, "metadata", {}).get("composite_snap", {})
        if not (
            isinstance(snap, dict)
            and bool(snap.get("ok"))
            and str(snap.get("code", "")).lower() == "snapped"
            and snap.get("head_local_offset") is not None
        ):
            issues.append(_WorkflowIssue(
                _WorkflowSeverity("error"),
                "COMPOSITE_SNAP_MISSING",
                "Supermodel export requires a completed headhook snap before export.",
                node="headhook",
            ))

    if mode == "creature":
        state = _motion_assignment_state(scene)
        if str(state.get("source") or "") != MOTION_SOURCE_ROM:
            issues.append(_WorkflowIssue(
                _WorkflowSeverity("error"),
                "ROM_CLIP_MISSING",
                "Creature export requires a generated ROM clip to prove the rig extremes.",
            ))

    return issues


# ─────────────────────────────────────────────────────────────────────────────
#  T506 ▸ Validate + Export step
# ─────────────────────────────────────────────────────────────────────────────
#
# The final workflow step lets the user (a) run the full validation
# service with ``strict=True`` to surface every blocker, and (b) write
# the scene out to one or more of KOTOR (MDL/MDX) / FBX / glTF / OBJ
# next to a ``.ghostrig.json`` sidecar (via :class:`SceneIO`).
#
# M10/T1001 wires the already-present MDL/MDX, FBX, glTF/GLB, and OBJ
# writers through this service so the Qt export dialog can produce real
# files.  The ``.ghostrig.json`` sidecar remains an optional recovery and
# round-trip artifact written beside the selected export formats.

EXPORT_FORMATS: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    # (key,    display label,         extensions for the output file)
    ("kotor", "KOTOR (MDL/MDX)",      (".mdl",  ".mdx")),
    ("fbx",   "FBX (Autodesk)",       (".fbx",)),
    ("gltf",  "glTF / GLB",           (".gltf", ".glb")),
    ("obj",   "OBJ (Wavefront)",      (".obj",)),
)


def default_export_formats_for_mode(scene_or_mode: Any) -> Tuple[str, ...]:
    """Return M10/T1004 export defaults for a Character Builder mode."""
    mode = getattr(scene_or_mode, "mode", scene_or_mode)
    value = (
        getattr(mode, "value", None)
        or getattr(mode, "name", "")
        or str(mode or "")
    ).lower()
    if value == "head":
        return ("kotor", "fbx", "gltf")
    if value == "supermodel":
        return ("fbx", "gltf")
    if value in ("headless_body", "creature"):
        return ("kotor", "fbx", "gltf", "obj")
    return ("kotor",)


@dataclass
class ValidateForExportResult:
    """Result of :func:`validate_for_export`.

    Attributes
    ----------
    ok               : True when no ERROR-severity issues were found
                       under ``strict=True``.  Warnings/info do *not*
                       block export.
    error_count      : Number of ERROR issues.
    warning_count    : Number of WARNING issues.
    info_count       : Number of INFO issues.
    blocking_codes   : Sorted list of unique error codes that would
                       block export.
    issues           : Full list of :class:`ValidationIssue`-like
                       objects from the service.
    message          : Human-readable summary.
    code             : Stable tag — ``"clean" / "warnings_only" /
                       "blocked"``.
    """
    ok:             bool                          = False
    error_count:    int                           = 0
    warning_count:  int                           = 0
    info_count:     int                           = 0
    blocking_codes: List[str]                     = field(default_factory=list)
    issues:         List[Any]                     = field(default_factory=list)
    message:        str                           = ""
    code:           str                           = "clean"


@dataclass
class ExportFormatResult:
    """Per-format result inside :class:`ExportResult`."""
    key:        str   = ""
    label:      str   = ""
    ok:         bool  = False
    path:       str   = ""
    message:    str   = ""
    code:       str   = "exported"        # exported / not_implemented /
                                          # no_body / failed / skipped


@dataclass
class ExportResult:
    """Result of :func:`export_scene`.

    Attributes
    ----------
    ok               : True when at least one format succeeded *and*
                       no requested format raised.  False when a hard
                       precondition fails (e.g. no body slot,
                       validation blocked) or every format failed.
    formats          : Per-format :class:`ExportFormatResult` rows in
                       the order they were requested.
    sidecar_path     : Absolute path of the written ``.ghostrig.json``
                       (empty when ``write_sidecar`` was False).
    out_dir          : The resolved output directory.
    message          : Human-readable summary.
    code             : Stable tag — ``"exported" / "no_body" / "blocked" /
                       "no_formats" / "no_out_dir" / "all_failed"``.
    """
    ok:           bool                            = False
    formats:      List[ExportFormatResult]        = field(default_factory=list)
    sidecar_path: str                             = ""
    out_dir:      str                             = ""
    message:      str                             = ""
    code:         str                             = "exported"


@dataclass
class LaunchWorkflowResult:
    """End-to-end external-mesh launch proof result (M12/T1205)."""

    ok:               bool                       = False
    load_result:      Optional[LoadResult]        = None
    apply_result:     Dict[str, Any]              = field(default_factory=dict)
    guide_result:     Optional[BodyRigGuidesResult] = None
    generate_result:  Optional[BodyRigGenerateResult] = None
    motion_result:    Optional[MotionAssignmentResult] = None
    export_result:    Optional[ExportResult]      = None
    reloaded_model:   Optional[Any]               = None
    mdl_path:         str                         = ""
    mdx_path:         str                         = ""
    hooks:            List[str]                   = field(default_factory=list)
    mesh_count:       int                         = 0
    skin_node_count:  int                         = 0
    supermodel:       str                         = ""
    message:          str                         = ""
    code:             str                         = "launch_workflow"


def _import_scene_io():                                     # pragma: no cover - import shim
    """Defer the SceneIO import to keep the module pykotor-free at import time."""
    try:
        from src.core.model_data import SceneIO  # type: ignore[import-untyped]
    except ImportError:
        from core.model_data import SceneIO      # type: ignore[import-untyped]
    return SceneIO


def _import_mdl_binary_writer():                            # pragma: no cover - import shim
    """Defer the KOTOR MDL/MDX writer until export time."""
    try:
        from src.core.mdl_writer import MDLBinaryWriter  # type: ignore
    except ImportError:
        from core.mdl_writer import MDLBinaryWriter      # type: ignore
    return MDLBinaryWriter


def _import_mesh_exporters():                                # pragma: no cover - import shim
    """Defer interchange exporters until export time."""
    try:
        from src.converters.mesh_converter import (       # type: ignore
            FBXExporter,
            GLTFExporter,
            OBJExporter,
        )
    except ImportError:
        from converters.mesh_converter import (           # type: ignore
            FBXExporter,
            GLTFExporter,
            OBJExporter,
        )
    return FBXExporter, GLTFExporter, OBJExporter


def _load_exported_kotor_model(mdl_path: str) -> Optional[Any]:
    """Reload an exported MDL/MDX pair through GhostRigger's KOTOR loader."""
    try:
        from src.core.kotor_loader import load_model_from_file
    except ImportError:                                     # pragma: no cover
        from core.kotor_loader import load_model_from_file  # type: ignore
    mdx_path = os.path.splitext(mdl_path)[0] + ".mdx"
    return load_model_from_file(mdl_path, mdx_path if os.path.isfile(mdx_path) else "")


def _model_nodes(model: Any) -> List[Any]:
    try:
        return list(model.all_nodes())
    except Exception:
        root = getattr(model, "root_node", None)
        if root is None:
            return []
        out: List[Any] = []

        def _walk(node: Any) -> None:
            out.append(node)
            for child in list(getattr(node, "children", []) or []):
                _walk(child)

        _walk(root)
        return out


def model_texture_names(model: Any) -> List[str]:
    """Return unique diffuse/aux texture names referenced by a model."""
    names: List[str] = []
    seen: set[str] = set()
    fields = (
        "texture",
        "lightmap",
        "txi_envmaptexture",
        "txi_specularcolour",
        "txi_bumpmaptexture",
    )
    for node in _model_nodes(model):
        if not (
            bool(getattr(node, "is_mesh", False))
            or bool(getattr(node, "is_skin", False))
            or bool(getattr(node, "vertices", None))
        ):
            continue
        raw_names: List[Any] = [getattr(node, field, "") for field in fields]
        raw_names.extend(list(getattr(node, "texture_names", []) or []))
        for raw in raw_names:
            clean = Path(str(raw or "").strip()).stem
            if not clean or clean.upper() in {"NULL", "NONE"}:
                continue
            key = clean.lower()
            if key not in seen:
                seen.add(key)
                names.append(clean[:32])
    return names


def candidate_texture_dirs(source_path: str) -> List[str]:
    """Likely folders beside an imported FBX/OBJ/glTF that hold textures."""
    if not source_path:
        return []
    base = Path(source_path).resolve().parent
    names = ("", "Texture", "Textures", "texture", "textures", "Materials", "materials")
    out: List[str] = []
    seen: set[str] = set()
    for name in names:
        path = base / name if name else base
        if path.is_dir():
            resolved = str(path)
            key = os.path.normcase(os.path.abspath(resolved))
            if key not in seen:
                seen.add(key)
                out.append(resolved)
    return out


def texture_file_for_name(name: str, dirs: List[str]) -> str:
    """Return the first matching on-disk texture path for *name*."""
    stem = Path(str(name or "").strip()).stem
    if not stem:
        return ""
    for directory in dirs:
        if not directory or not os.path.isdir(directory):
            continue
        for ext in _TEXTURE_EXTS:
            direct = Path(directory) / f"{stem}{ext}"
            if direct.is_file():
                return str(direct)
        try:
            for child in Path(directory).iterdir():
                if child.is_file() and child.stem.lower() == stem.lower():
                    return str(child)
        except OSError:
            continue
    return ""


def texture_resolution_report(
    model: Any,
    dirs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Report which referenced textures are found in the supplied folders."""
    dirs = list(dirs or [])
    found: Dict[str, str] = {}
    missing: List[str] = []
    for name in model_texture_names(model):
        path = texture_file_for_name(name, dirs)
        if path:
            found[name] = path
        else:
            missing.append(name)
    return {
        "expected": model_texture_names(model),
        "found": found,
        "missing": missing,
        "found_count": len(found),
        "missing_count": len(missing),
        "dirs": dirs,
    }


def export_external_textures(
    scene: Any,
    model: Any,
    out_dir: str,
) -> Dict[str, Any]:
    """Convert externally supplied texture images to game-side TGA files."""
    metadata = getattr(scene, "metadata", None)
    if not isinstance(metadata, dict):
        return {"ok": True, "written": [], "missing": [], "message": "No metadata."}
    dirs = [
        str(path)
        for path in list(metadata.get("external_texture_dirs", []) or [])
        if path and os.path.isdir(str(path))
    ]
    if not dirs:
        return {"ok": True, "written": [], "missing": [], "message": "No external texture dirs."}
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - Pillow is available in supported builds
        return {"ok": False, "written": [], "missing": [], "message": f"Pillow unavailable: {exc}"}

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    missing: List[str] = []
    for name in model_texture_names(model):
        src = texture_file_for_name(name, dirs)
        if not src:
            missing.append(name)
            continue
        target = out / f"{Path(name).stem[:32]}.tga"
        try:
            img = Image.open(src).convert("RGBA")
            img.save(target, format="TGA")
            written.append(str(target))
        except Exception as exc:
            log.warning("Could not export texture %s from %s: %s", name, src, exc)
            missing.append(name)
    result = {
        "ok": not missing,
        "written": written,
        "missing": missing,
        "message": f"{len(written)} texture(s) written; {len(missing)} missing.",
    }
    metadata["external_texture_exports"] = result
    return result


def _verify_launch_reloaded_model(
    model: Any,
    *,
    expected_supermodel: str = "",
) -> Tuple[bool, List[str], int, int, str, str]:
    """Check the KOTOR-critical facts after reloading an exported body."""
    if model is None:
        return False, [], 0, 0, "", "Reloaded model is empty."

    nodes = _model_nodes(model)
    names = [str(getattr(n, "name", "") or "") for n in nodes]
    names_lower = {n.lower() for n in names}
    hooks = [n for n in names if n.lower() in {"headhook", "rhand", "lhand_g"}]
    mesh_count = sum(
        1 for n in nodes
        if bool(getattr(n, "is_mesh", False))
        or bool(getattr(n, "vertices", None))
    )
    skin_count = sum(
        1 for n in nodes
        if bool(getattr(n, "is_skin", False))
        or bool(getattr(n, "skin_data", None))
    )
    supermodel = str(getattr(model, "supermodel", "") or "")
    problems: List[str] = []
    for required in ("headhook", "rhand"):
        if required not in names_lower:
            problems.append(f"Missing required hook/node: {required}")
    if mesh_count <= 0:
        problems.append("Reloaded export has no mesh nodes.")
    if skin_count <= 0:
        problems.append("Reloaded export has no skinned mesh data.")
    if expected_supermodel and supermodel.lower() != expected_supermodel.lower():
        problems.append(
            f"Supermodel mismatch: expected {expected_supermodel}, got {supermodel or 'NULL'}."
        )
    return (not problems), hooks, mesh_count, skin_count, supermodel, "; ".join(problems)


def run_external_mesh_launch_workflow(
    mesh_path: str,
    *,
    scene: Optional[Any] = None,
    game_version: str = "K1",
    out_dir: str = "",
    template_part: str = "body",
    motion_supermodel: str = "S_Female02",
    formats: Optional[List[str]] = None,
) -> LaunchWorkflowResult:
    """M12/T1205: one-shot external mesh to reloadable KOTOR export.

    This is the automation equivalent of the launch workflow a modder
    expects: load external mesh, apply a KOTOR template, generate/bind,
    inherit PC motions, export MDL/MDX, then reload the result and verify
    hooks, supermodel, mesh count, and skin data.
    """
    md = _import_model_data()
    if scene is None:
        scene = md.CharacterScene(game_version=game_version)
    if not out_dir:
        return LaunchWorkflowResult(
            message="No output directory supplied for launch workflow.",
            code="no_out_dir",
        )

    load = load_body(
        mesh_path,
        scene,
        game_version=game_version,
        allow_mode_correction=True,
    )
    if not load.ok or load.model is None:
        return LaunchWorkflowResult(
            load_result=load,
            message=f"Launch workflow stopped at load: {load.message}",
            code=load.code or "load_failed",
        )

    try:
        cb = _import_character_builder()
        template = cb.load_template(game=game_version, part=template_part)
        applied = cb.apply_template_rig(load.model, template, game=game_version)
    except Exception as exc:
        log.exception("run_external_mesh_launch_workflow: template apply failed")
        return LaunchWorkflowResult(
            load_result=load,
            message=f"Template rig apply failed: {exc}",
            code="template_failed",
        )
    if not bool(applied.get("ok")):
        return LaunchWorkflowResult(
            load_result=load,
            apply_result=applied,
            message=str(applied.get("message") or "Template rig apply failed."),
            code="template_failed",
        )

    rigged_model = applied.get("model")
    scene.assign(
        md.PartSlot.HEADLESS_BODY,
        rigged_model,
        resref=load.resref or _resref_from_path(mesh_path),
        game_version=game_version,
        source_path=mesh_path,
    )

    guides = place_body_guides(scene)
    if not guides.ok:
        return LaunchWorkflowResult(
            load_result=load,
            apply_result=applied,
            guide_result=guides,
            message=f"Launch workflow stopped at guide placement: {guides.message}",
            code=getattr(guides, "code", "") or "guides_failed",
        )

    generated = generate_skeleton(
        scene,
        acurig=guides.acurig,
        guides=guides.guides,
    )
    if not generated.ok:
        return LaunchWorkflowResult(
            load_result=load,
            apply_result=applied,
            guide_result=guides,
            generate_result=generated,
            message=f"Launch workflow stopped at skeleton generation: {generated.message}",
            code=generated.code or "generate_failed",
        )

    motion = assign_motion_source(
        scene,
        MOTION_SOURCE_INHERITED,
        supermodel=motion_supermodel,
    )
    if not motion.ok:
        return LaunchWorkflowResult(
            load_result=load,
            apply_result=applied,
            guide_result=guides,
            generate_result=generated,
            motion_result=motion,
            message=f"Launch workflow stopped at motion assignment: {motion.message}",
            code=motion.code or "motion_failed",
        )

    exported = export_scene(
        scene,
        formats=list(formats or ["kotor"]),
        out_dir=out_dir,
        write_sidecar=True,
    )
    if not exported.ok:
        return LaunchWorkflowResult(
            load_result=load,
            apply_result=applied,
            guide_result=guides,
            generate_result=generated,
            motion_result=motion,
            export_result=exported,
            message=f"Launch workflow stopped at export: {exported.message}",
            code=exported.code or "export_failed",
        )

    mdl_path = ""
    for row in exported.formats:
        if row.key == "kotor" and row.ok:
            mdl_path = row.path
            break
    if not mdl_path:
        return LaunchWorkflowResult(
            load_result=load,
            apply_result=applied,
            guide_result=guides,
            generate_result=generated,
            motion_result=motion,
            export_result=exported,
            message="KOTOR export did not produce an MDL path.",
            code="no_mdl_export",
        )

    try:
        reloaded = _load_exported_kotor_model(mdl_path)
    except Exception as exc:
        log.exception("run_external_mesh_launch_workflow: reload failed")
        return LaunchWorkflowResult(
            load_result=load,
            apply_result=applied,
            guide_result=guides,
            generate_result=generated,
            motion_result=motion,
            export_result=exported,
            mdl_path=mdl_path,
            mdx_path=os.path.splitext(mdl_path)[0] + ".mdx",
            message=f"Exported MDL reload failed: {exc}",
            code="reload_failed",
        )

    ok, hooks, mesh_count, skin_count, supermodel, problems = (
        _verify_launch_reloaded_model(
            reloaded,
            expected_supermodel=motion.supermodel or motion_supermodel,
        )
    )
    return LaunchWorkflowResult(
        ok=ok,
        load_result=load,
        apply_result=applied,
        guide_result=guides,
        generate_result=generated,
        motion_result=motion,
        export_result=exported,
        reloaded_model=reloaded,
        mdl_path=mdl_path,
        mdx_path=os.path.splitext(mdl_path)[0] + ".mdx",
        hooks=hooks,
        mesh_count=mesh_count,
        skin_node_count=skin_count,
        supermodel=supermodel,
        message=(
            "Launch workflow proof passed."
            if ok else
            f"Launch workflow reload verification failed: {problems}"
        ),
        code="launch_verified" if ok else "verification_failed",
    )


def validate_for_export(
    scene: Any,
    *,
    strict: bool = True,
) -> ValidateForExportResult:
    """Workflow Step 6a — run :class:`ValidationService` with strict=True.

    Returns a structured result indicating whether the scene is safe
    to export.  ERROR-severity issues block export; WARNING / INFO
    pass through as advisory.
    """
    try:
        svc_mod = _import_validation_service()
    except Exception as exc:                                # pragma: no cover
        return ValidateForExportResult(
            message=f"ValidationService unavailable: {exc}",
            code="blocked",
        )

    try:
        service = svc_mod.ValidationService(scene, strict=strict)
        issues = list(service.validate() or [])
        issues.extend(_motion_assignment_issues(scene))
        issues.extend(_per_mode_export_issues(scene))
    except Exception as exc:                                # pragma: no cover
        log.exception("validate_for_export: ValidationService raised")
        return ValidateForExportResult(
            message=f"Validation failed: {exc}",
            code="blocked",
        )

    _summary, _label, errors, warnings, infos, codes = _summarize_issues(issues)
    # Match the established severity-read pattern from
    # ``_summarize_issues`` (``severity.value.lower() == "error"``)
    # so duck-typed fakes used in tests work the same here.
    blocking = sorted({
        getattr(i, "code", "")
        for i in issues
        if (getattr(getattr(i, "severity", None), "value",
                    getattr(getattr(i, "severity", None), "name", ""))
            or "").lower() == "error"
        and getattr(i, "code", "")
    })

    if errors > 0:
        return ValidateForExportResult(
            ok=False,
            error_count=errors, warning_count=warnings, info_count=infos,
            blocking_codes=blocking,
            issues=issues,
            message=(f"Export blocked — {errors} error(s), "
                     f"{warnings} warning(s), {infos} info "
                     f"({len(codes)} unique code(s))."),
            code="blocked",
        )

    if warnings > 0 or infos > 0:
        return ValidateForExportResult(
            ok=True,
            error_count=0, warning_count=warnings, info_count=infos,
            blocking_codes=[],
            issues=issues,
            message=(f"Export allowed — {warnings} warning(s), "
                     f"{infos} info (no blockers)."),
            code="warnings_only",
        )

    return ValidateForExportResult(
        ok=True,
        error_count=0, warning_count=0, info_count=0,
        blocking_codes=[],
        issues=issues,
        message="Scene is clean — ready to export.",
        code="clean",
    )


def _export_single_format(
    scene: Any,
    body: Any,
    fmt_key: str,
    label: str,
    out_dir: str,
    resref: str,
) -> ExportFormatResult:
    """Dispatch one format.  Returns a structured per-format row.

    M10/T1001 wires the already-present writers into the workflow service
    so the export dialog can produce real files instead of sidecar-only
    placeholders.
    """
    # Resolve output path candidate (caller is responsible for the dir).
    primary_ext = {
        "kotor": ".mdl",
        "fbx":   ".fbx",
        "gltf":  ".glb",
        "obj":   ".obj",
    }.get(fmt_key, "")
    if not primary_ext:
        return ExportFormatResult(
            key=fmt_key, label=label, ok=False,
            message=f"Unknown format key '{fmt_key}'.",
            code="failed",
        )

    out_path = os.path.join(out_dir, f"{resref}{primary_ext}")

    try:
        if fmt_key == "kotor":
            writer_cls = _import_mdl_binary_writer()
            writer_cls().write_files(body, out_path)
        elif fmt_key == "fbx":
            fbx_cls, _gltf_cls, _obj_cls = _import_mesh_exporters()
            ok = fbx_cls().export(body, out_path)
            if ok is False:
                raise RuntimeError("FBX exporter returned False")
        elif fmt_key == "gltf":
            _fbx_cls, gltf_cls, _obj_cls = _import_mesh_exporters()
            ok = gltf_cls().export(body, out_path, binary=True)
            if ok is False:
                raise RuntimeError("glTF exporter returned False")
        elif fmt_key == "obj":
            _fbx_cls, _gltf_cls, obj_cls = _import_mesh_exporters()
            ok = obj_cls().export(body, out_path)
            if ok is False:
                raise RuntimeError("OBJ exporter returned False")
    except Exception as exc:
        log.exception("export_scene: %s writer failed", fmt_key)
        return ExportFormatResult(
            key=fmt_key, label=label, ok=False, path=out_path,
            message=f"{label} export failed: {exc}",
            code="failed",
        )

    return ExportFormatResult(
        key=fmt_key, label=label, ok=True, path=out_path,
        message=f"{label} exported to {out_path}.",
        code="exported",
    )


def export_scene(
    scene: Any,
    *,
    formats: Optional[List[str]] = None,
    out_dir: str = "",
    write_sidecar: bool = True,
    skip_validation: bool = False,
) -> ExportResult:
    """Workflow Step 6b — write the scene to disk in the requested formats.

    Parameters
    ----------
    scene            : Scene whose ``PartSlot.HEADLESS_BODY`` must be
                       populated.
    formats          : Subset of ``{"kotor", "fbx", "gltf", "obj"}`` —
                       per-format results are returned in order.
    out_dir          : Destination directory (created if missing).
    write_sidecar    : When True (default), write ``<resref>.ghostrig.json``
                       to the output directory via
                       :meth:`SceneIO.write_sidecar`.
    skip_validation  : When True, bypass the strict-validation gate.
                       Reserved for "Export anyway" UX after the user
                       has acknowledged warnings.

    Notes
    -----
    M10/T1001 routes the selected formats to the real in-tree writers.
    The sidecar is written last so a failed interchange export can still
    leave a recoverable GhostRigger scene definition behind.
    """
    md = _import_model_data()
    entry = scene.get(md.PartSlot.HEADLESS_BODY)
    body = entry.model if entry is not None else None
    if body is None:
        return ExportResult(
            message="No body model loaded — nothing to export.",
            code="no_body",
        )

    if not out_dir:
        return ExportResult(
            message="No output directory supplied.",
            code="no_out_dir",
        )

    requested = list(formats or [])
    if not requested and not write_sidecar:
        return ExportResult(
            out_dir=out_dir,
            message="Nothing requested — pick at least one format or "
                    "enable the sidecar JSON.",
            code="no_formats",
        )

    gate: Optional[ValidateForExportResult] = None
    # Optional pre-flight validation gate.
    if not skip_validation:
        gate = validate_for_export(scene, strict=True)
        if not gate.ok:
            return ExportResult(
                out_dir=out_dir,
                message=("Export blocked by validation: "
                         f"{gate.error_count} error(s). "
                         f"Codes: {', '.join(gate.blocking_codes)}"),
                code="blocked",
            )

    # Ensure output directory exists.
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as exc:
        return ExportResult(
            out_dir=out_dir,
            message=f"Cannot create output directory: {exc}",
            code="no_out_dir",
        )

    resref = (entry.resref or getattr(body, "name", "") or "untitled").lower()
    # Keep only filesystem-safe characters in the resref stem.
    resref = "".join(c for c in resref if c.isalnum() or c in ("_", "-")) \
        or "untitled"

    # Build the per-format dispatch list (preserving caller order).
    label_by_key = {key: label for key, label, _exts in EXPORT_FORMATS}
    rows: List[ExportFormatResult] = []
    for fmt_key in requested:
        if fmt_key not in label_by_key:
            rows.append(ExportFormatResult(
                key=fmt_key, label=fmt_key, ok=False,
                message=f"Unknown format '{fmt_key}'.",
                code="failed",
            ))
            continue
        rows.append(
            _export_single_format(
                scene, body, fmt_key,
                label_by_key[fmt_key], out_dir, resref,
            )
        )

    tex_export = export_external_textures(scene, body, out_dir)
    if tex_export.get("written") or tex_export.get("missing"):
        rows.append(ExportFormatResult(
            key="textures",
            label="External texture TGAs",
            ok=bool(tex_export.get("ok")),
            path=out_dir,
            message=str(tex_export.get("message", "")),
            code="exported" if tex_export.get("ok") else "failed",
        ))

    # Sidecar v2 metadata. Stored on the scene before SceneIO writes so the
    # .ghostrig.json records exactly what this export attempt produced.
    try:
        import datetime as _dt
        export_stamp = _dt.datetime.now(
            _dt.timezone.utc).isoformat().replace("+00:00", "Z")
        metadata = getattr(scene, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
            setattr(scene, "metadata", metadata)
        metadata["export_results"] = [
            {
                "format": row.key,
                "label": row.label,
                "ok": bool(row.ok),
                "path": row.path,
                "code": row.code,
                "message": row.message,
            }
            for row in rows
        ]
        metadata["export_timestamps"] = {
            **dict(metadata.get("export_timestamps", {}) or {}),
            "last_export_at": export_stamp,
        }
        if gate is not None:
            metadata["validation_report"] = {
                "ok": bool(gate.ok),
                "code": gate.code,
                "error_count": gate.error_count,
                "warning_count": gate.warning_count,
                "info_count": gate.info_count,
                "blocking_codes": list(gate.blocking_codes),
            }
    except Exception:                                      # pragma: no cover
        log.debug("export_scene: could not attach sidecar v2 metadata",
                  exc_info=True)

    # Sidecar JSON — written last so even partial-failure exports
    # leave a valid scene-definition file behind.
    sidecar_path = ""
    if write_sidecar:
        try:
            sio = _import_scene_io()
            anchor = os.path.join(out_dir, f"{resref}.mdl")
            sidecar_path = sio.write_sidecar(scene, anchor)
        except Exception as exc:                            # pragma: no cover
            log.exception("export_scene: write_sidecar raised")
            rows.append(ExportFormatResult(
                key="sidecar", label="Scene JSON sidecar", ok=False,
                message=f"Sidecar write failed: {exc}",
                code="failed",
            ))

    any_ok = any(r.ok for r in rows) or bool(sidecar_path)
    if rows and not any_ok and not sidecar_path:
        return ExportResult(
            formats=rows, sidecar_path="",
            out_dir=out_dir,
            message="Every requested format failed.",
            code="all_failed",
        )

    # Build summary message.
    ok_count = sum(1 for r in rows if r.ok)
    fail_count = sum(1 for r in rows if not r.ok)
    parts = []
    if ok_count:
        parts.append(f"{ok_count} written")
    if fail_count:
        parts.append(f"{fail_count} failed")
    if sidecar_path:
        parts.append("sidecar JSON OK")
    summary = "; ".join(parts) or "nothing to export"

    return ExportResult(
        ok=True,
        formats=rows,
        sidecar_path=sidecar_path,
        out_dir=out_dir,
        message=f"Export to {out_dir}: {summary}.",
        code="exported",
    )


__all__ = [
    "BodyGuideEditResult",
    "BodyGuideEditCommand",
    "BodyGuideEditHistory",
    "BodyRigGenerateResult",
    "BodyRigGuidesResult",
    "CheckActorResult",
    "CheckModelResult",
    "EXPORT_FORMATS",
    "ExportFormatResult",
    "ExportResult",
    "HAND_BONES",
    "HandRigResult",
    "LaunchWorkflowResult",
    "LoadResult",
    "MOTION_SOURCE_IMPORTED",
    "MOTION_SOURCE_INHERITED",
    "MOTION_SOURCE_LABELS",
    "MOTION_SOURCE_MODEL",
    "MOTION_SOURCE_ROM",
    "MotionAssignmentResult",
    "PC_SUPERMODEL_OPTIONS",
    "PREVIEW_ANIMATIONS",
    "ValidateForExportResult",
    "apply_body_guide_positions",
    "apply_hand_masks",
    "assign_motion_source",
    "available_preview_animations",
    "check_model",
    "default_export_formats_for_mode",
    "export_scene",
    "generate_skeleton",
    "load_body",
    "load_file_filter",
    "motion_assignment_options",
    "normalize_external_model_for_kotor",
    "place_body_guides",
    "place_hand_guides",
    "play_preview_animation",
    "reference_model_height",
    "record_body_guide_edit",
    "redo_body_guide_edit",
    "run_external_mesh_launch_workflow",
    "run_rom_test",
    "stop_preview_animation",
    "undo_body_guide_edit",
    "supported_load_extensions",
    "update_body_guide",
    "update_body_guide_from_node",
    "validate_for_export",
]
