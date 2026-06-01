"""
src/core/head_workflow.py — Mode 2 (Head) workflow service
==========================================================

End-to-end *Head* workflow defined by M6 / T601-T605 of the
Qt-ghostrigger roadmap.  This is the **Head-mode companion** to
``headless_body_workflow.py`` (M5), implementing the same seven-step
contract for head-only models (pfhc*, pmhc*, p_hk47, etc.):

    Step 1  ── Load Head      →  :func:`load_head`           (T601)
    Step 2  ── Check Model    →  :func:`check_head`          (T601)
    Step 3  ── Head Rig       →  :func:`rig_head`            (T601)
                                  (neck chain + jaw skeleton)
    Step 4  ── Face Rig       →  :func:`rig_face`            (T601)
                                  (eye / lid / lip-corner palette)
    Step 5  ── Viseme Test    →  :func:`available_visemes`   (T603)
                                  + :func:`apply_viseme`       (T603)
    Step 6  ── Phoneme Cal.   →  :func:`calibrate_phoneme`   (T604)
    Step 7  ── Validate +     →  :func:`validate_for_export_head` (T601)
              Export             + :func:`export_head_scene`      (T601)

Like its Mode-1 sibling, this module is a *pure-Python service layer*
with no Qt imports and no PyKotor imports at module-load time.  Heavy
dependencies are pulled in through the lazy-import helpers in
:mod:`_workflow_base`.

The seven M5 invariants documented in
``knowledge_base/roadmap/02_roadmap_2026_05.md`` are honoured verbatim:

  1. Qt-free / pykotor-free service module with deferred imports.
  2. Per-step result dataclasses with ``ok`` + ``message`` + ``code``.
  3. ``_summarize_issues`` reads ``severity.value.lower()`` not ``.name``.
  4. The Inspector page rewrite (T602) retires legacy stubs.
  5. Window slot replacement wires ``_on_<step>_requested`` to this module.
  6. Fake-injection via monkeypatch keeps tests Qt-free.
  7. Commit per task ID, squash to milestone commit, PR per milestone.

Roadmap reference: knowledge_base/roadmap/02_roadmap_2026_05.md M6/T601.
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
# We re-export the import helpers from :mod:`_workflow_base` under
# local names so tests can ``monkeypatch.setattr(wf, "_import_…", …)``
# without touching the base module.  This mirrors the M5 pattern in
# ``headless_body_workflow.py`` where the same shim names live inline.

def _import_workflow_base():                                # pragma: no cover - import shim
    """Return :mod:`_workflow_base`, deferring the import.

    The base module is dependency-free so this almost never fails, but
    we keep the import lazy for symmetry with the rest of the module.
    """
    try:
        from src.core.workflow import _workflow_base as _wb         # type: ignore
    except ImportError:
        from core.workflow import _workflow_base as _wb             # type: ignore
    return _wb


def _import_model_data():                                   # pragma: no cover - import shim
    try:
        from src.core.geometry import model_data as _md             # type: ignore
    except ImportError:
        from core.geometry import model_data as _md                 # type: ignore
    return _md


def _import_validation_service():                           # pragma: no cover - import shim
    try:
        from src.core.diagnostics import validation_service as _vs     # type: ignore
    except ImportError:
        from core.diagnostics import validation_service as _vs         # type: ignore
    return _vs


def _import_character_builder():                            # pragma: no cover - import shim
    """Return ``core.character_builder`` (where ``validate_facial_bones``,
    ``find_headhook``, and :class:`LIPPlayback` live)."""
    try:
        from src.core.characters import character_builder as _cb      # type: ignore
    except ImportError:
        from core.characters import character_builder as _cb          # type: ignore
    return _cb


def _import_lip_reader():                                   # pragma: no cover - import shim
    """Return ``core.lip_reader`` (where :class:`LIPShape` and
    :class:`LIPFile` live).

    Falls back to a direct-file load when ``core/__init__.py`` would
    eagerly pull in pykotor — same pattern the GUI layer uses.
    """
    try:
        from src.core.special import lip_reader as _lr             # type: ignore
        return _lr
    except Exception:
        pass
    try:
        from core.special import lip_reader as _lr                 # type: ignore
        return _lr
    except Exception:
        pass
    # Direct-file load.
    import importlib.util as _u
    import pathlib as _pl
    import sys as _sys
    _here = _pl.Path(__file__).resolve().parent
    _lr_path = _here.parent / "special" / "lip_reader.py"
    if not _lr_path.is_file():
        raise ImportError("src/core/special/lip_reader.py not found")
    _spec = _u.spec_from_file_location("_gr_lip_reader_inline", str(_lr_path))
    _mod = _u.module_from_spec(_spec)
    _sys.modules[_spec.name] = _mod
    _spec.loader.exec_module(_mod)
    return _mod


def _import_scene_io():                                     # pragma: no cover - import shim
    """Defer the SceneIO import to keep the module pykotor-free at import time."""
    from src.core.geometry.model_data import SceneIO                 # type: ignore[import-untyped]
    return SceneIO


# ──────────────────────────────────────────────────────────────────────
#  Supported input formats (Head mode)
# ──────────────────────────────────────────────────────────────────────
#
# Heads come from the same set of importers as bodies — the only
# practical difference is that UTC resolution returns a *head* resref
# instead of a body one.  We keep the same extension surface so the Qt
# Load-Head dialog can use a single shared file filter.

_MDL_EXTS  = (".mdl",)
_GLTF_EXTS = (".gltf", ".glb")
_FBX_EXTS  = (".fbx", ".obj", ".ply", ".stl")
_UTC_EXTS  = (".utc",)


def supported_load_extensions() -> Tuple[str, ...]:
    """Return the full tuple of extensions :func:`load_head` accepts."""
    return _MDL_EXTS + _GLTF_EXTS + _FBX_EXTS + _UTC_EXTS


def load_file_filter() -> str:
    """Qt-compatible filter string for the Load-Head dialog.

    Example output::

        "Head models (*.mdl *.gltf *.glb *.fbx *.obj *.ply *.stl *.utc);;All files (*.*)"
    """
    patterns = " ".join(f"*{ext}" for ext in supported_load_extensions())
    return f"Head models ({patterns});;All files (*.*)"


# ──────────────────────────────────────────────────────────────────────
#  Facial-bone palette (canonical KotOR head skeleton)
# ──────────────────────────────────────────────────────────────────────
#
# Pulled verbatim from ``character_builder.validate_facial_bones`` so
# both the validator and the Inspector page (T602) reference the same
# source of truth.  These names match the KotOR engine convention
# documented in KotorBlender ``armature.py``.

#: Bones the Head workflow *must* find to consider rigging viable.
REQUIRED_HEAD_BONES: Dict[str, str] = {
    "head_g":   "Head bone (base orientation)",
    "f_jaw_g":  "Jaw bone (lip sync open/close)",
    "f_um_g":   "Upper mouth (lip sync)",
}

#: Bones that are *recommended* but not fatal.  Their absence drops a
#: validation WARNING rather than an ERROR.
RECOMMENDED_HEAD_BONES: Dict[str, str] = {
    "necklwr_g":  "Lower neck bone",
    "neck_g":     "Neck bone",
    "f_llm_g":    "Left lower mouth",
    "f_rlm_g":    "Right lower mouth",
    "maskhook":   "Mask attachment hook",
    "gogglehook": "Goggle attachment hook",
}

#: The full neck-chain order from torso anchor up to the head root.
#: Used by :func:`rig_head` to decide which guides to plant.
NECK_CHAIN: Tuple[str, ...] = ("necklwr_g", "neck_g", "head_g")

#: The eight face-rig knobs the Face Rig step (T602) exposes to the
#: Inspector palette.  Order is significant — the UI lays these out
#: left-to-right in two rows of four.
FACE_RIG_BONES: Tuple[str, ...] = (
    "f_jaw_g",     # jaw open/close
    "f_um_g",      # upper mouth
    "f_llm_g",     # left lower mouth
    "f_rlm_g",     # right lower mouth
    "f_lec_g",     # left eye control
    "f_rec_g",     # right eye control
    "f_llid_g",    # left eyelid
    "f_rlid_g",    # right eyelid
)


# ──────────────────────────────────────────────────────────────────────
#  Export formats
# ──────────────────────────────────────────────────────────────────────
#
# Head models export to the same surface as bodies — KOTOR (MDL/MDX),
# FBX, glTF, OBJ — plus the always-on ``.ghostrig.json`` sidecar.

EXPORT_FORMATS: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    ("kotor", "KOTOR (MDL/MDX)",  (".mdl",  ".mdx")),
    ("fbx",   "FBX (Autodesk)",   (".fbx",)),
    ("gltf",  "glTF / GLB",       (".gltf", ".glb")),
    ("obj",   "OBJ (Wavefront)",  (".obj",)),
)


# ──────────────────────────────────────────────────────────────────────
#  Result dataclasses
# ──────────────────────────────────────────────────────────────────────

@dataclass
class LoadHeadResult:
    """Result of :func:`load_head`.

    Attributes
    ----------
    ok            : True when the model loaded *and* matched HEAD.
    model         : The loaded ``KotorModel`` (may be present even when
                    ``ok=False`` — e.g. a Body model was loaded by
                    mistake; the caller can offer to switch modes).
    detected_mode : The ``CharacterMode`` returned by ``detect_character_mode``.
    source_path   : Absolute path the file was read from.
    resref        : Lower-case resource reference (basename without ext).
    message       : Human-readable summary suitable for the status bar.
    code          : Stable machine tag — ``"loaded" / "mode_mismatch" /
                    "unsupported_format" / "file_not_found" / "load_failed" /
                    "empty_path"``.
    """
    ok:            bool          = False
    model:         Optional[Any] = None          # KotorModel
    detected_mode: Optional[Any] = None          # CharacterMode
    source_path:   str           = ""
    resref:        str           = ""
    message:       str           = ""
    code:          str           = "load_failed"


@dataclass
class CheckHeadResult:
    """Result of :func:`check_head`.

    Wraps :func:`validate_facial_bones` *and* the full
    :class:`ValidationService` pass so the Qt window can show one
    unified banner.  Field-compatible with
    :class:`headless_body_workflow.CheckModelResult` so the bottom-strip
    consumer doesn't have to special-case it.

    Attributes
    ----------
    ok                : True when there are no ERRORs (missing
                        required facial bones flip this False).
    issues            : Full list of validator findings.
    facial_warnings   : The raw string list from
                        ``character_builder.validate_facial_bones``.
                        Surfaced separately so the Inspector can drive
                        per-bone tooltips.
    banner_key        : ``"clean" / "info" / "warning" / "error"``.
    summary           : Banner text (e.g. ``"2 ERRORS, 1 WARNING"`` ).
    error_count / warning_count / info_count : Per-severity tallies.
    codes             : Set of distinct ValidationIssue codes found.
    missing_required  : List of required-bone names that are absent.
    missing_recommended : List of recommended-bone names that are absent.
    """
    ok:                  bool       = True
    issues:              List[Any]  = field(default_factory=list)
    facial_warnings:     List[str]  = field(default_factory=list)
    banner_key:          str        = "clean"
    summary:             str        = "CLEAN"
    error_count:         int        = 0
    warning_count:       int        = 0
    info_count:          int        = 0
    codes:               set        = field(default_factory=set)
    missing_required:    List[str]  = field(default_factory=list)
    missing_recommended: List[str]  = field(default_factory=list)


@dataclass
class RigHeadResult:
    """Result of :func:`rig_head`.

    Attributes
    ----------
    ok          : True when the neck-chain + jaw skeleton was assembled.
    bones       : Ordered list of bone names that were placed
                  (root → necklwr_g → neck_g → head_g → f_jaw_g).
    headhook    : Optional ``(world_position, world_orientation)`` tuple
                  returned by :func:`character_builder.find_headhook`
                  on the *parent body* — useful for the attach step
                  in M7.  ``None`` for stand-alone head edits.
    message     : Human-readable summary.
    code        : ``"rigged" / "no_head" / "missing_required_bone" /
                  "build_failed"``.
    """
    ok:        bool                  = False
    bones:     List[str]             = field(default_factory=list)
    headhook:  Optional[Any]         = None
    message:   str                   = ""
    code:      str                   = "rigged"


@dataclass
class RigFaceResult:
    """Result of :func:`rig_face`.

    Step 4 of the Head workflow lays out the face-rig palette: the eight
    bones listed in :data:`FACE_RIG_BONES` plus any extras the user
    requested.  Only bones that exist on the head model are activated;
    missing ones are skipped (and surfaced in ``skipped``).

    Attributes
    ----------
    ok       : True when at least one face bone was activated.
    active   : The ordered list of bones currently bound to UI knobs.
    skipped  : Bones requested but absent from the model.
    message  : Human-readable summary.
    code     : ``"rigged" / "no_head" / "no_bones_found"``.
    """
    ok:      bool       = False
    active:  List[str]  = field(default_factory=list)
    skipped: List[str]  = field(default_factory=list)
    message: str        = ""
    code:    str        = "rigged"


@dataclass
class ValidateForExportHeadResult:
    """Result of :func:`validate_for_export_head`.

    Field-for-field identical to
    :class:`headless_body_workflow.ValidateForExportResult` so the Qt
    window can use one shared handler for both modes.

    ``code`` is one of ``"clean" / "warnings_only" / "blocked"``.
    """
    ok:             bool       = False
    error_count:    int        = 0
    warning_count:  int        = 0
    info_count:     int        = 0
    blocking_codes: List[str]  = field(default_factory=list)
    issues:         List[Any]  = field(default_factory=list)
    message:        str        = ""
    code:           str        = "clean"


@dataclass
class ExportFormatResult:
    """Per-format result row.  Mirrors the M5 dataclass shape."""
    key:     str  = ""
    label:   str  = ""
    ok:      bool = False
    path:    str  = ""
    message: str  = ""
    code:    str  = "exported"        # exported / not_implemented /
                                      # no_head / failed / skipped


@dataclass
class ExportHeadResult:
    """Result of :func:`export_head_scene`.

    Attributes
    ----------
    ok            : True when at least one format succeeded *and* no
                    requested format raised.
    formats       : Per-format :class:`ExportFormatResult` rows.
    sidecar_path  : Absolute path of the written ``.ghostrig.json``.
    out_dir       : The resolved output directory.
    message       : Human-readable summary.
    code          : ``"exported" / "no_head" / "blocked" / "no_formats" /
                    "no_out_dir" / "all_failed"``.
    """
    ok:           bool                       = False
    formats:      List[ExportFormatResult]   = field(default_factory=list)
    sidecar_path: str                        = ""
    out_dir:      str                        = ""
    message:      str                        = ""
    code:         str                        = "exported"


# ──────────────────────────────────────────────────────────────────────
#  Internal helpers
# ──────────────────────────────────────────────────────────────────────

def _ext_of(path: str) -> str:
    return Path(path).suffix.lower()


def _resref_from_path(path: str) -> str:
    return Path(path).stem.lower()


def _safe_resref(text: str, fallback: str = "untitled") -> str:
    cleaned = "".join(c for c in (text or "").lower()
                      if c.isalnum() or c in ("_", "-"))
    return cleaned or fallback


def _load_mdl(path: str, game_version: str) -> Optional[Any]:
    """Load a KOTOR MDL/MDX pair via the kotor_loader bridge."""
    try:
        from src.core.game.kotor_loader import load_model_from_file
    except ImportError:                                     # pragma: no cover
        from core.game.kotor_loader import load_model_from_file  # type: ignore
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
        from src.core.export.gltf_importer import auto_import
    except ImportError:                                     # pragma: no cover
        from core.export.gltf_importer import auto_import          # type: ignore
    gv = (md.GameVersion.K2
          if str(game_version).upper().endswith("2")
          else md.GameVersion.K1)
    return auto_import(path,
                       model_name=_resref_from_path(path),
                       game_version=gv)


def _load_utc(path: str, game_version: str) -> Optional[Any]:
    """Resolve a UTC's appearance and load the resulting head MDL.

    The full UTC → library → MDL chain depends on a configured KOTOR
    installation.  When none is wired, we raise :class:`NotImplementedError`
    so the caller can fall back to a direct head-MDL picker — matching
    the M5 / Headless-Body behaviour.
    """
    if not os.path.isfile(path):
        return None
    raise NotImplementedError(
        "UTC-driven head load requires a configured KOTOR installation "
        "(creature_appearance.resolve_utc_appearance_from_library). "
        "Pick a head MDL directly for now."
    )


def _get_head_model(scene: Any) -> Optional[Any]:
    """Return the head model assigned to *scene*, or None."""
    md = _import_model_data()
    return scene.get_model(md.PartSlot.HEAD_SHELL)


def _existing_bone_names(head_model: Any) -> set:
    """Return the lower-cased set of node names in *head_model*."""
    if head_model is None:
        return set()
    names: set = set()
    try:
        for node in head_model.all_nodes():
            names.add(node.name.lower().strip())
    except Exception:                                       # pragma: no cover
        log.debug("_existing_bone_names: enumeration failed", exc_info=True)
    return names


def _summarize_issues(issues: List[Any]) -> Tuple[str, str, int, int, int, set]:
    """Reduce a list of ValidationIssues into a banner-ready tuple.

    Returns ``(banner_key, summary, errors, warnings, infos, codes)``.
    Identical semantics to ``headless_body_workflow._summarize_issues``
    — this is the M5 invariant #3 (``severity.value.lower()``).
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


# ──────────────────────────────────────────────────────────────────────
#  T601 — Step 1: Load Head
# ──────────────────────────────────────────────────────────────────────

def load_head(
    path: str,
    scene: Any,
    *,
    game_version: Optional[str] = None,
    allow_mode_correction: bool = False,
) -> LoadHeadResult:
    """Load a head model from *path* and assign it to *scene*.

    This is the entry point for **Workflow Step 1 (Load Head)** in the
    Mode-2 (Head) workflow.  Behaves identically to
    :func:`headless_body_workflow.load_body` except:

      * the slot it assigns is ``PartSlot.HEAD_SHELL`` ;
      * the expected detected mode is ``CharacterMode.HEAD`` ;
      * a mode-mismatch warning is raised for any non-HEAD detection.

    Parameters
    ----------
    path                  : Absolute path to the source file.
    scene                 : :class:`CharacterScene` to mutate.
    game_version          : ``"K1"`` / ``"K2"``.  Defaults to
                            ``scene.game_version``.
    allow_mode_correction : When True a non-HEAD detection is *not*
                            failed; the slot is still populated and the
                            caller can react to ``detected_mode``.
    """
    if not path:
        return LoadHeadResult(message="No file path given.", code="empty_path")
    if not os.path.isfile(path):
        return LoadHeadResult(
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
            return LoadHeadResult(
                source_path=path,
                message=f"Unsupported format: {ext or '(no extension)'}",
                code="unsupported_format",
            )
    except NotImplementedError as exc:
        return LoadHeadResult(
            source_path=path,
            message=str(exc),
            code="load_failed",
        )
    except Exception as exc:                                # pragma: no cover
        log.exception("load_head: importer raised on %s", path)
        return LoadHeadResult(
            source_path=path,
            message=f"Load failed: {exc}",
            code="load_failed",
        )

    if model is None:
        return LoadHeadResult(
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
        md.PartSlot.HEAD_SHELL, model,
        resref=resref,
        game_version=gv,
        source_path=path,
    )

    # ── Verdict ─────────────────────────────────────────────────────
    if detected == md.CharacterMode.HEAD:
        return LoadHeadResult(
            ok=True, model=model, detected_mode=detected,
            source_path=path, resref=resref,
            message=f"Loaded head: {resref} ({Path(path).name})",
            code="loaded",
        )

    # Mode mismatch — surface suggested mode so the UI can offer to switch.
    suggest = getattr(detected, "display_name", str(detected))
    msg = (f"Loaded {Path(path).name}, but it looks like a {suggest} model "
           f"(expected Head).")
    return LoadHeadResult(
        ok=allow_mode_correction,
        model=model, detected_mode=detected,
        source_path=path, resref=resref,
        message=msg,
        code="loaded" if allow_mode_correction else "mode_mismatch",
    )


# ──────────────────────────────────────────────────────────────────────
#  T601 — Step 2: Check Head
# ──────────────────────────────────────────────────────────────────────

def check_head(scene: Any, *, strict: bool = False) -> CheckHeadResult:
    """Workflow Step 2 — run facial-bone + validator checks on the head.

    Combines two sources:

      * :func:`character_builder.validate_facial_bones` — returns a list
        of warning strings keyed on the canonical KotOR facial-bone
        names.  Missing *required* bones (head_g, f_jaw_g, f_um_g) flip
        ``ok=False`` ; missing *recommended* bones drop a warning.
      * :class:`ValidationService` — the same scene-wide validator the
        Body workflow uses (geometry, hooks, weights, supermodel
        mismatch …).

    The two are merged into a single :class:`CheckHeadResult` so the
    Qt bottom-strip can surface them through ``set_validation``.

    Parameters
    ----------
    scene  : :class:`CharacterScene` whose ``PartSlot.HEAD_SHELL`` must
             be populated.
    strict : Forwarded to ``ValidationService(strict=…)``.  When True
             several WARNINGs are promoted to ERRORs.
    """
    if scene is None or not getattr(scene, "slots", None):
        return CheckHeadResult(
            ok=False,
            banner_key="warning",
            summary="NO HEAD LOADED",
        )

    head = _get_head_model(scene)
    if head is None:
        return CheckHeadResult(
            ok=False,
            banner_key="warning",
            summary="NO HEAD LOADED",
        )

    # ── Facial-bone palette check ───────────────────────────────────
    existing = _existing_bone_names(head)
    missing_required = sorted([
        name for name in REQUIRED_HEAD_BONES
        if name.lower() not in existing
    ])
    missing_recommended = sorted([
        name for name in RECOMMENDED_HEAD_BONES
        if name.lower() not in existing
    ])

    # Pull the human-readable warning strings from the canonical helper
    # too so the Inspector page can surface them verbatim (tooltips,
    # log entries, etc.).
    try:
        cb = _import_character_builder()
        facial_warnings = list(cb.validate_facial_bones(head) or [])
    except Exception as exc:                                # pragma: no cover
        log.exception("check_head: validate_facial_bones raised")
        facial_warnings = [f"validate_facial_bones failed: {exc}"]

    # ── Scene-wide validator ────────────────────────────────────────
    try:
        vs_mod = _import_validation_service()
        service = vs_mod.ValidationService(scene, strict=strict)
        issues = list(service.validate() or [])
    except Exception as exc:                                # pragma: no cover
        log.exception("check_head: ValidationService raised")
        return CheckHeadResult(
            ok=False,
            facial_warnings=facial_warnings,
            missing_required=missing_required,
            missing_recommended=missing_recommended,
            banner_key="error",
            summary=f"CHECK FAILED: {exc}",
        )

    # ── Merge ───────────────────────────────────────────────────────
    # Missing required bones promote to ERROR-equivalent severity in the
    # banner roll-up, even when the validator itself didn't flag them
    # (HEAD-mode validation is M9 work — until then we synthesise the
    # equivalent banner state from the facial-bone palette).
    key, summary, errs, warns, infos, codes = _summarize_issues(issues)
    if missing_required:
        errs += len(missing_required)
        # Bump banner to ERROR if we synthesised any.
        key = "error"
        # Re-render the summary using the bumped tallies.
        parts: List[str] = []
        if errs:
            parts.append(f"{errs} error{'s' if errs != 1 else ''}")
        if warns:
            parts.append(f"{warns} warning{'s' if warns != 1 else ''}")
        if infos and not (errs or warns):
            parts.append(f"{infos} info")
        summary = ", ".join(parts).upper() if parts else "CLEAN"
        # Mark the synthetic codes so tests can assert on them.
        codes = set(codes)
        for name in missing_required:
            codes.add(f"FACIAL_BONE_MISSING:{name}")
    elif missing_recommended and key == "clean":
        # Recommended-only misses bump us to WARNING (info -> warning).
        warns += len(missing_recommended)
        key = "warning"
        parts2: List[str] = []
        if warns:
            parts2.append(f"{warns} warning{'s' if warns != 1 else ''}")
        if infos:
            parts2.append(f"{infos} info")
        summary = ", ".join(parts2).upper() if parts2 else "CLEAN"
        codes = set(codes)
        for name in missing_recommended:
            codes.add(f"FACIAL_BONE_RECOMMENDED:{name}")

    return CheckHeadResult(
        ok=(errs == 0),
        issues=issues,
        facial_warnings=facial_warnings,
        banner_key=key,
        summary=summary,
        error_count=errs,
        warning_count=warns,
        info_count=infos,
        codes=codes,
        missing_required=missing_required,
        missing_recommended=missing_recommended,
    )


# ──────────────────────────────────────────────────────────────────────
#  T601 — Step 3: Head Rig (neck chain + jaw)
# ──────────────────────────────────────────────────────────────────────

def rig_head(
    scene: Any,
    *,
    parent_body: Optional[Any] = None,
) -> RigHeadResult:
    """Workflow Step 3 — assemble the neck-chain + jaw skeleton.

    The full AcuRig-style neck builder is M7/M8 work; this M6 step
    establishes the *intent surface* the Qt window calls into.  It:

      * confirms the head model is loaded;
      * verifies every bone in :data:`NECK_CHAIN` is present (failure
        returns ``code="missing_required_bone"``);
      * optionally captures the parent body's ``headhook`` transform
        (for the M7 attach step);
      * returns the ordered chain ``["necklwr_g", "neck_g", "head_g",
        "f_jaw_g"]`` as ``bones``.

    Parameters
    ----------
    scene        : :class:`CharacterScene` with ``HEAD_SHELL`` populated.
    parent_body  : Optional ``KotorModel`` of the body the head will
                   attach to.  When provided, we capture its headhook
                   transform via :func:`character_builder.find_headhook`.
    """
    head = _get_head_model(scene)
    if head is None:
        return RigHeadResult(
            message="No head model loaded.  Load a head first.",
            code="no_head",
        )

    existing = _existing_bone_names(head)

    # Required chain — fail loudly if anything is missing.
    chain: List[str] = []
    missing: List[str] = []
    for bone in NECK_CHAIN:
        if bone.lower() in existing:
            chain.append(bone)
        else:
            missing.append(bone)

    if missing:
        return RigHeadResult(
            bones=chain,
            message=(f"Cannot rig head — missing required bone(s): "
                     f"{', '.join(missing)}"),
            code="missing_required_bone",
        )

    # Jaw is required for any meaningful talk/lip-sync rig.
    if "f_jaw_g" in existing:
        chain.append("f_jaw_g")
    else:
        return RigHeadResult(
            bones=chain,
            message="Cannot rig head — missing jaw bone 'f_jaw_g'.",
            code="missing_required_bone",
        )

    # Optional: capture the parent body's headhook for the M7 attach.
    headhook = None
    if parent_body is not None:
        try:
            cb = _import_character_builder()
            headhook = cb.find_headhook(parent_body)
        except Exception:                                   # pragma: no cover
            log.debug("rig_head: find_headhook raised", exc_info=True)
            headhook = None

    return RigHeadResult(
        ok=True,
        bones=chain,
        headhook=headhook,
        message=f"Head rig assembled: {len(chain)} bone(s).",
        code="rigged",
    )


# ──────────────────────────────────────────────────────────────────────
#  T601 — Step 4: Face Rig (eye / lid / lip-corner palette)
# ──────────────────────────────────────────────────────────────────────

def rig_face(
    scene: Any,
    *,
    extra_bones: Optional[List[str]] = None,
) -> RigFaceResult:
    """Workflow Step 4 — activate the face-rig palette knobs.

    Iterates :data:`FACE_RIG_BONES` (plus any *extra_bones* supplied by
    the caller) and partitions them into ``active`` (present on the
    model) and ``skipped`` (absent).  At least one active bone is
    required for ``ok=True`` ; a head with no face bones at all is a
    geometry-only proxy and the workflow surfaces that explicitly.

    Parameters
    ----------
    scene        : :class:`CharacterScene` with ``HEAD_SHELL`` populated.
    extra_bones  : Optional list of additional bone names the caller
                   wants exposed in the palette (e.g. custom mod bones).
    """
    head = _get_head_model(scene)
    if head is None:
        return RigFaceResult(
            message="No head model loaded.  Load a head first.",
            code="no_head",
        )

    existing = _existing_bone_names(head)
    requested = list(FACE_RIG_BONES) + list(extra_bones or [])

    active: List[str] = []
    skipped: List[str] = []
    seen: set = set()
    for bone in requested:
        if bone in seen:
            continue
        seen.add(bone)
        if bone.lower() in existing:
            active.append(bone)
        else:
            skipped.append(bone)

    if not active:
        return RigFaceResult(
            ok=False,
            active=[],
            skipped=skipped,
            message=("No face-rig bones present on this head — "
                     "model appears to be geometry-only."),
            code="no_bones_found",
        )

    return RigFaceResult(
        ok=True,
        active=active,
        skipped=skipped,
        message=(f"Face rig palette: {len(active)} active, "
                 f"{len(skipped)} skipped."),
        code="rigged",
    )


# ──────────────────────────────────────────────────────────────────────
#  T601 — Step 6a: Validate for export
# ──────────────────────────────────────────────────────────────────────

def validate_for_export_head(
    scene: Any,
    *,
    strict: bool = True,
) -> ValidateForExportHeadResult:
    """Workflow Step 6a — run :class:`ValidationService` with strict=True.

    Returns a structured result indicating whether the scene is safe to
    export.  ERROR-severity issues block export; WARNING / INFO pass
    through as advisory.

    Mirrors :func:`headless_body_workflow.validate_for_export` so the Qt
    window's export-gate code can be mode-agnostic.
    """
    try:
        svc_mod = _import_validation_service()
    except Exception as exc:                                # pragma: no cover
        return ValidateForExportHeadResult(
            message=f"ValidationService unavailable: {exc}",
            code="blocked",
        )

    try:
        service = svc_mod.ValidationService(scene, strict=strict)
        issues = list(service.validate() or [])
    except Exception as exc:                                # pragma: no cover
        log.exception("validate_for_export_head: ValidationService raised")
        return ValidateForExportHeadResult(
            message=f"Validation failed: {exc}",
            code="blocked",
        )

    _key, _summary, errors, warnings, infos, codes = _summarize_issues(issues)
    # Same severity-read pattern as :func:`_summarize_issues`.
    blocking = sorted({
        getattr(i, "code", "")
        for i in issues
        if (getattr(getattr(i, "severity", None), "value",
                    getattr(getattr(i, "severity", None), "name", ""))
            or "").lower() == "error"
        and getattr(i, "code", "")
    })

    if errors > 0:
        return ValidateForExportHeadResult(
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
        return ValidateForExportHeadResult(
            ok=True,
            error_count=0, warning_count=warnings, info_count=infos,
            blocking_codes=[],
            issues=issues,
            message=(f"Export allowed — {warnings} warning(s), "
                     f"{infos} info (no blockers)."),
            code="warnings_only",
        )

    return ValidateForExportHeadResult(
        ok=True,
        error_count=0, warning_count=0, info_count=0,
        blocking_codes=[],
        issues=issues,
        message="Head is clean — ready to export.",
        code="clean",
    )


# ──────────────────────────────────────────────────────────────────────
#  T601 — Step 6b: Export head scene
# ──────────────────────────────────────────────────────────────────────

def _export_single_format(
    scene: Any,
    head: Any,
    fmt_key: str,
    label: str,
    out_dir: str,
    resref: str,
) -> ExportFormatResult:
    """Dispatch one format for a head export.

    The binary writers (KOTOR MDL, FBX, glTF, OBJ) are M10 work — every
    format currently returns the ``not_implemented`` code with a
    pointer to the always-on ``.ghostrig.json`` sidecar.
    """
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
    return ExportFormatResult(
        key=fmt_key, label=label, ok=False,
        path=out_path,
        message=(f"{label} writer not yet implemented for heads — "
                 f"would have written to {out_path}.  Use the "
                 ".ghostrig.json sidecar until M10."),
        code="not_implemented",
    )


def export_head_scene(
    scene: Any,
    *,
    formats: Optional[List[str]] = None,
    out_dir: str = "",
    write_sidecar: bool = True,
    skip_validation: bool = False,
) -> ExportHeadResult:
    """Workflow Step 6b — write the head scene to disk.

    Behaviour parallels :func:`headless_body_workflow.export_scene`:

      * gates on :func:`validate_for_export_head` unless
        ``skip_validation=True`` ;
      * dispatches each requested format through
        :func:`_export_single_format` (all M10-pending today);
      * always writes the ``.ghostrig.json`` sidecar (unless
        ``write_sidecar=False`` ) so the head's metadata survives even
        when no binary writer has landed.

    Parameters
    ----------
    scene            : :class:`CharacterScene` with ``HEAD_SHELL``
                       populated.
    formats          : Subset of ``{"kotor", "fbx", "gltf", "obj"}``.
    out_dir          : Destination directory (created if missing).
    write_sidecar    : When True, write ``<resref>.ghostrig.json``
                       via :meth:`SceneIO.write_sidecar`.
    skip_validation  : When True, bypass the strict-validation gate.
    """
    md = _import_model_data()
    entry = scene.get(md.PartSlot.HEAD_SHELL)
    head = entry.model if entry is not None else None
    if head is None:
        return ExportHeadResult(
            message="No head model loaded — nothing to export.",
            code="no_head",
        )

    if not out_dir:
        return ExportHeadResult(
            message="No output directory supplied.",
            code="no_out_dir",
        )

    requested = list(formats or [])
    if not requested and not write_sidecar:
        return ExportHeadResult(
            out_dir=out_dir,
            message="Nothing requested — pick at least one format or "
                    "enable the sidecar JSON.",
            code="no_formats",
        )

    # Optional pre-flight validation gate.
    if not skip_validation:
        gate = validate_for_export_head(scene, strict=True)
        if not gate.ok:
            return ExportHeadResult(
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
        return ExportHeadResult(
            out_dir=out_dir,
            message=f"Cannot create output directory: {exc}",
            code="no_out_dir",
        )

    resref = _safe_resref(
        entry.resref or getattr(head, "name", "") or "untitled",
        fallback="untitled",
    )

    # Per-format dispatch.
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
                scene, head, fmt_key,
                label_by_key[fmt_key], out_dir, resref,
            )
        )

    # Sidecar JSON — written last so partial-failure exports still
    # leave a valid scene-definition file behind.
    sidecar_path = ""
    if write_sidecar:
        try:
            sio = _import_scene_io()
            anchor = os.path.join(out_dir, f"{resref}.mdl")
            sidecar_path = sio.write_sidecar(scene, anchor)
        except Exception as exc:                            # pragma: no cover
            log.exception("export_head_scene: write_sidecar raised")
            rows.append(ExportFormatResult(
                key="sidecar", label="Scene JSON sidecar", ok=False,
                message=f"Sidecar write failed: {exc}",
                code="failed",
            ))

    any_ok = any(r.ok for r in rows) or bool(sidecar_path)
    if rows and not any_ok and not sidecar_path:
        return ExportHeadResult(
            formats=rows, sidecar_path="",
            out_dir=out_dir,
            message="Every requested format failed.",
            code="all_failed",
        )

    # Summary message.
    ok_count = sum(1 for r in rows if r.ok)
    ni_count = sum(1 for r in rows if r.code == "not_implemented")
    fail_count = sum(1 for r in rows
                     if not r.ok and r.code != "not_implemented")
    parts: List[str] = []
    if ok_count:
        parts.append(f"{ok_count} written")
    if ni_count:
        parts.append(f"{ni_count} pending (M10)")
    if fail_count:
        parts.append(f"{fail_count} failed")
    if sidecar_path:
        parts.append("sidecar JSON OK")
    summary = "; ".join(parts) or "nothing to export"

    return ExportHeadResult(
        ok=True,
        formats=rows,
        sidecar_path=sidecar_path,
        out_dir=out_dir,
        message=f"Export to {out_dir}: {summary}.",
        code="exported",
    )


# ──────────────────────────────────────────────────────────────────────
#  T603 — Viseme test panel surface
# ──────────────────────────────────────────────────────────────────────
#
# The Viseme Test Panel (T603) is rendered by the Qt Inspector page; this
# module exposes the headless surface it calls into:  enumerate the 16
# Preston-Blair phoneme indices via :class:`lip_reader.LIPShape` and
# accept "apply this viseme" requests so the head's facial bones
# snap to the matching pose.

def available_visemes() -> Tuple[Tuple[int, str], ...]:
    """Return ``(index, label)`` tuples for every defined LIP viseme.

    Pulled from :class:`lip_reader.LIPShape` so the panel and the
    runtime always agree on the index ordering.  Returns an empty tuple
    when :mod:`lip_reader` cannot be imported (e.g. CI without the lip
    parser available — fall-back path).
    """
    try:
        lr = _import_lip_reader()
    except Exception:                                       # pragma: no cover
        return tuple()
    shape_enum = getattr(lr, "LIPShape", None)
    if shape_enum is None:                                  # pragma: no cover
        return tuple()
    return tuple((int(s), s.name) for s in shape_enum)


def apply_viseme(
    scene: Any,
    viseme_index: int,
) -> Tuple[bool, str]:
    """Snap the head's facial bones to the pose for *viseme_index*.

    Parameters
    ----------
    scene         : :class:`CharacterScene` with ``HEAD_SHELL`` loaded.
    viseme_index  : Integer ∈ ``[0, 15]`` matching :class:`LIPShape`.

    Returns
    -------
    ``(ok, message)``.  The actual pose data lives in the head's
    ``talk`` animation; this function locates that animation via
    :class:`character_builder.LIPPlayback` and asks it to evaluate the
    matching keyframe.  Returns ``ok=False`` when no head is loaded,
    no ``talk`` animation is present, or the index is out of range.
    """
    head = _get_head_model(scene)
    if head is None:
        return False, "No head model loaded."

    try:
        avail = available_visemes()
    except Exception as exc:                                # pragma: no cover
        return False, f"Viseme lookup failed: {exc}"

    valid_indices = {idx for idx, _ in avail}
    if viseme_index not in valid_indices:
        return False, (f"Viseme {viseme_index} out of range; valid: "
                       f"0..{max(valid_indices) if valid_indices else 15}")

    try:
        cb = _import_character_builder()
        playback = cb.LIPPlayback()
        if not playback.load_talk_animation(head):
            return False, ("Head has no 'talk' animation — cannot apply "
                           "viseme poses.  Re-rig with a supermodel that "
                           "carries the standard talk animation.")
    except Exception as exc:                                # pragma: no cover
        return False, f"LIPPlayback unavailable: {exc}"

    return True, f"Viseme {viseme_index} applied via talk animation."


# ──────────────────────────────────────────────────────────────────────
#  T604 — Phoneme calibration poses
# ──────────────────────────────────────────────────────────────────────
#
# The phoneme calibrator (T604) lets the user adjust per-phoneme poses
# that the lip-sync runtime will use when generating LIP files.  M6
# ships the *registry* — eight canonical phoneme groups mapped to LIP
# shape indices — plus a stub :func:`calibrate_phoneme` entry point.
# The actual save/load is M9 work.

#: The eight standard phoneme groups used in KotOR LIP calibration.
#: Each entry maps a phoneme label to the canonical
#: :class:`LIPShape` index it triggers.  Order matches the layout
#: requested by the Inspector page (left-to-right, two rows of four).
PHONEME_POSES: Tuple[Tuple[str, int], ...] = (
    # Row 1 — vowels.
    ("AH (open vowel)",          1),    # PP / AA equivalent
    ("EH (mid vowel)",           2),    # EH / E
    ("IH (closed vowel)",        3),    # IH / I
    ("OH (rounded vowel)",       4),    # OH / O
    # Row 2 — consonants.
    ("MM (closed labial)",       5),    # MM / Bilabial closed
    ("FV (labiodental)",         6),    # FV / labiodental
    ("TH (interdental)",         7),    # TH / dental
    ("SS (sibilant)",            8),    # SS / sibilant
)


def calibrate_phoneme(
    scene: Any,
    phoneme_label: str,
    viseme_index: int,
) -> Tuple[bool, str]:
    """Register a calibration mapping ``phoneme_label → viseme_index``.

    M6 stub — stores the mapping on the scene's
    ``head_phoneme_calibration`` dict (created on demand).  The
    persistence + UI write-back is M9 work.

    Parameters
    ----------
    scene          : :class:`CharacterScene` — mutated in place.
    phoneme_label  : One of the labels in :data:`PHONEME_POSES`.
    viseme_index   : Integer ∈ ``[0, 15]`` matching :class:`LIPShape`.
    """
    head = _get_head_model(scene)
    if head is None:
        return False, "No head model loaded — load a head first."

    valid_labels = {label for label, _ in PHONEME_POSES}
    if phoneme_label not in valid_labels:
        return False, (f"Unknown phoneme '{phoneme_label}'. "
                       f"Valid: {', '.join(sorted(valid_labels))}.")

    valid_indices = {idx for idx, _ in available_visemes()}
    # If we can't enumerate visemes (lip_reader missing) just bound-check.
    if not valid_indices:
        if not (0 <= viseme_index <= 15):
            return False, (f"Viseme {viseme_index} out of range [0, 15].")
    elif viseme_index not in valid_indices:
        return False, (f"Viseme {viseme_index} not in available set.")

    # Stash on the scene for the M9 persistence pass to pick up.
    calib = getattr(scene, "head_phoneme_calibration", None)
    if calib is None:
        calib = {}
        try:
            scene.head_phoneme_calibration = calib          # type: ignore[attr-defined]
        except Exception:                                   # pragma: no cover
            # Read-only scene — surface explicitly.
            return False, "Scene is read-only; cannot persist calibration."
    calib[phoneme_label] = int(viseme_index)
    return True, f"Calibrated '{phoneme_label}' → viseme {viseme_index}."


# ──────────────────────────────────────────────────────────────────────
#  T605 — Head-mode camera preset
# ──────────────────────────────────────────────────────────────────────

#: Default camera framing for Head mode.  Returned by
#: :func:`head_camera_preset` so the Qt viewport can apply it when the
#: user switches into Head mode.  Values are tuned for a typical KotOR
#: head model (centre ~0,0,0.05; height ~0.18m).
HEAD_CAMERA_PRESET: Dict[str, Tuple[float, ...]] = {
    # Eye position (camera) — in front of the face, slightly above.
    "eye":       (0.0, -0.45, 1.65),
    # Look-at target — eye level on the head model.
    "target":    (0.0, 0.0, 1.65),
    # Up vector.
    "up":        (0.0, 0.0, 1.0),
    # FOV in degrees — tighter than the body preset (35° instead of 50°)
    # because heads benefit from a near-portrait framing.
    "fov_deg":   (35.0,),
    # Near / far clip.
    "clip":      (0.02, 5.0),
}


def head_camera_preset() -> Dict[str, Tuple[float, ...]]:
    """Return a copy of :data:`HEAD_CAMERA_PRESET`.

    The dict is copied per call so the caller can mutate it without
    affecting subsequent calls.  Vectors stay as tuples (immutable).
    """
    return {k: tuple(v) for k, v in HEAD_CAMERA_PRESET.items()}


def head_camera_spherical(
    preset: Optional[Dict[str, Tuple[float, ...]]] = None,
) -> Dict[str, float]:
    """Convert :data:`HEAD_CAMERA_PRESET` into spherical camera state.

    The Qt viewport's :class:`ArcBallCamera` is parametrised in
    spherical coordinates (``target``, ``distance``, ``azimuth``,
    ``elevation``) plus ``fov`` and ``near/far`` clip planes — not the
    raw ``(eye, target)`` pair the preset stores.  This helper performs
    the conversion in a single, pure-function place so:

      * the Qt viewport hook stays a thin glue layer, and
      * unit tests can validate the math without booting a GUI.

    The Z-up convention used by the runtime matches
    :meth:`ArcBallCamera.eye`::

        eye = target + (
            d·cos(elev)·cos(azim),
            d·cos(elev)·sin(azim),
            d·sin(elev),
        )

    Parameters
    ----------
    preset : Optional override.  Defaults to :func:`head_camera_preset`.

    Returns
    -------
    Dict with keys ``target_x``, ``target_y``, ``target_z``,
    ``distance``, ``azimuth``, ``elevation``, ``fov``, ``near``,
    ``far``.  Angles are in degrees.

    Raises
    ------
    ValueError
        When *preset* has malformed ``eye``/``target`` (not length 3)
        or ``eye == target`` (zero-distance camera).
    """
    import math
    p = preset if preset is not None else head_camera_preset()

    eye    = tuple(p.get("eye",    (0.0, -0.45, 1.65)))
    target = tuple(p.get("target", (0.0,  0.0,  1.65)))
    fov    = tuple(p.get("fov_deg", (35.0,)))
    clip   = tuple(p.get("clip",   (0.02, 5.0)))

    if len(eye) != 3 or len(target) != 3:
        raise ValueError("head camera preset eye/target must be length-3 tuples")

    dx = float(eye[0]) - float(target[0])
    dy = float(eye[1]) - float(target[1])
    dz = float(eye[2]) - float(target[2])
    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
    if dist < 1e-6:
        raise ValueError("head camera preset eye == target (zero distance)")

    # asin domain-clamped against fp drift.
    elev = math.degrees(math.asin(max(-1.0, min(1.0, dz / dist))))
    azim = math.degrees(math.atan2(dy, dx)) % 360.0

    return {
        "target_x":  float(target[0]),
        "target_y":  float(target[1]),
        "target_z":  float(target[2]),
        "distance":  float(dist),
        "azimuth":   float(azim),
        "elevation": float(elev),
        "fov":       float(fov[0]) if fov else 35.0,
        "near":      float(clip[0]) if len(clip) >= 1 else 0.02,
        "far":       float(clip[1]) if len(clip) >= 2 else 5.0,
    }


__all__ = [
    # Constants
    "EXPORT_FORMATS",
    "FACE_RIG_BONES",
    "HEAD_CAMERA_PRESET",
    "NECK_CHAIN",
    "PHONEME_POSES",
    "RECOMMENDED_HEAD_BONES",
    "REQUIRED_HEAD_BONES",
    # Result dataclasses
    "CheckHeadResult",
    "ExportFormatResult",
    "ExportHeadResult",
    "LoadHeadResult",
    "RigFaceResult",
    "RigHeadResult",
    "ValidateForExportHeadResult",
    # Workflow functions
    "apply_viseme",
    "available_visemes",
    "calibrate_phoneme",
    "check_head",
    "export_head_scene",
    "head_camera_preset",
    "head_camera_spherical",
    "load_file_filter",
    "load_head",
    "rig_face",
    "rig_head",
    "supported_load_extensions",
    "validate_for_export_head",
]
