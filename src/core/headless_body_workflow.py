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


# ──────────────────────────────────────────────────────────────────────
#  Supported input formats
# ──────────────────────────────────────────────────────────────────────

#: Extensions accepted by :func:`load_body`.  The detector keys off the
#: lower-cased suffix.
_MDL_EXTS  = (".mdl",)
_GLTF_EXTS = (".gltf", ".glb")
_FBX_EXTS  = (".fbx", ".obj", ".ply", ".stl")
_UTC_EXTS  = (".utc",)


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


def _get_body_model(scene: Any) -> Optional[Any]:
    md = _import_model_data()
    return scene.get_model(md.PartSlot.HEADLESS_BODY)


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


# ─────────────────────────────────────────────────────────────────────────────
#  T506 ▸ Validate + Export step
# ─────────────────────────────────────────────────────────────────────────────
#
# The final workflow step lets the user (a) run the full validation
# service with ``strict=True`` to surface every blocker, and (b) write
# the scene out to one or more of KOTOR (MDL/MDX) / FBX / glTF / OBJ
# next to a ``.ghostrig.json`` sidecar (via :class:`SceneIO`).
#
# The actual binary writers are still partly stubs (KOTOR MDL writer
# lives in a future M, the FBX/glTF/OBJ exporters are scattered across
# helper modules) — so :func:`export_scene` returns a stable
# ``not_implemented`` code per format that the UI can present as a
# friendly skip rather than a crash.  The ``.ghostrig.json`` sidecar
# *is* fully implemented via :func:`SceneIO.write_sidecar`, so the
# workflow always has at least one deliverable.

EXPORT_FORMATS: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    # (key,    display label,         extensions for the output file)
    ("kotor", "KOTOR (MDL/MDX)",      (".mdl",  ".mdx")),
    ("fbx",   "FBX (Autodesk)",       (".fbx",)),
    ("gltf",  "glTF / GLB",           (".gltf", ".glb")),
    ("obj",   "OBJ (Wavefront)",      (".obj",)),
)


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


def _import_scene_io():                                     # pragma: no cover - import shim
    """Defer the SceneIO import to keep the module pykotor-free at import time."""
    from src.core.model_data import SceneIO  # type: ignore[import-untyped]
    return SceneIO


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

    The KOTOR / FBX / glTF / OBJ writers are still being assembled
    across the codebase (M10 work), so this function deliberately
    returns ``not_implemented`` with a friendly message rather than
    raising — the UI can grey out / inform per format.
    """
    # Resolve output path candidate (caller is responsible for the dir).
    primary_ext = {
        "kotor": ".mdl",
        "fbx":   ".fbx",
        "gltf":  ".gltf",
        "obj":   ".obj",
    }.get(fmt_key, "")
    if not primary_ext:
        return ExportFormatResult(
            key=fmt_key, label=label, ok=False,
            message=f"Unknown format key '{fmt_key}'.",
            code="failed",
        )

    out_path = os.path.join(out_dir, f"{resref}{primary_ext}")

    # ── Per-format writer dispatch (M5: all are still not_implemented). ──
    # When the real writers land (M10), each branch becomes a call into
    # the dedicated module — the surrounding scaffolding stays the same.
    return ExportFormatResult(
        key=fmt_key, label=label, ok=False,
        path=out_path,
        message=(f"{label} writer not yet implemented — would have "
                 f"written to {out_path}.  Use the .ghostrig.json "
                 "sidecar for the scene definition until M10."),
        code="not_implemented",
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
    The KOTOR / FBX / glTF / OBJ binary writers are M10 work — every
    selected format currently returns the ``not_implemented`` code
    with a friendly message pointing the user at the sidecar JSON.
    The sidecar itself *is* fully written.
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
    ni_count = sum(1 for r in rows if r.code == "not_implemented")
    fail_count = sum(1 for r in rows
                     if not r.ok and r.code != "not_implemented")
    parts = []
    if ok_count:
        parts.append(f"{ok_count} written")
    if ni_count:
        parts.append(f"{ni_count} pending (M10)")
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
    "BodyRigGenerateResult",
    "BodyRigGuidesResult",
    "CheckActorResult",
    "CheckModelResult",
    "EXPORT_FORMATS",
    "ExportFormatResult",
    "ExportResult",
    "HAND_BONES",
    "HandRigResult",
    "LoadResult",
    "PREVIEW_ANIMATIONS",
    "ValidateForExportResult",
    "apply_hand_masks",
    "available_preview_animations",
    "check_model",
    "export_scene",
    "generate_skeleton",
    "load_body",
    "load_file_filter",
    "place_body_guides",
    "place_hand_guides",
    "play_preview_animation",
    "stop_preview_animation",
    "supported_load_extensions",
    "validate_for_export",
]
