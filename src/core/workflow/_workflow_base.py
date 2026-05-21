"""
src/core/workflow/_workflow_base.py — Shared scaffolding for per-mode workflow services
==============================================================================

The Qt-ghostrigger roadmap ships one *pure-Python service module* per
:class:`CharacterMode` ("Headless Body", "Head", "Supermodel", "Creature").
Each follows the same seven invariants documented in
``knowledge_base/roadmap/02_roadmap_2026_05.md``:

  1. Qt-free, pykotor-free service module via deferred-import helpers.
  2. Per-step result dataclasses with ``ok`` + ``message`` + structured ``code``.
  3. ``_summarize_issues`` uses ``severity.value.lower()`` not ``.name``.
  4. The Inspector page rewrite retires legacy "Open … Panel…" stubs.
  5. Window slot replacement wires ``_on_<step>_requested`` to the workflow.
  6. Fake-injection via monkeypatch for testing.
  7. Commit per task ID, squash to milestone commit, PR per milestone.

This module factors out the *deduplicable* pieces of (1) – (3) so each
per-mode module ( ``headless_body_workflow.py``, ``head_workflow.py`` ,
…) can re-use them instead of re-implementing them.  M5 shipped these
helpers inline inside ``headless_body_workflow.py`` ; M6 / T601 moves
them here.

Public surface
--------------

Lazy-import helpers (every per-mode service should re-export the ones
it actually uses so tests can ``monkeypatch.setattr(wf, name, …)``):

* :func:`import_model_data`             ──  ``core.model_data``
* :func:`import_validation_service`     ──  ``core.validation_service``
* :func:`import_accurig`                ──  ``autorig.accurig``
* :func:`import_scene_io`               ──  ``model_data.SceneIO``

Issue summariser:

* :func:`summarize_issues`              ──  reduces a list of
  :class:`ValidationIssue`-like objects into a banner-friendly tuple.

Base dataclasses:

* :class:`StepResult`                   ──  minimal ok/message/code carrier
* :class:`CheckResult`                  ──  Step-2 ``Check`` result shape
* :class:`ValidateForExportResult`      ──  Step-6 strict-validation result
* :class:`ExportFormatResult`           ──  per-format export row
* :class:`ExportResultBase`             ──  Step-6 export-wrapper result

Workflow modules *may* subclass any of these to add mode-specific fields
(e.g. ``LoadResult`` carries ``detected_mode``).  Subclassing is
optional — the M5 / Headless-Body service still uses its own
dataclasses verbatim, and this module is purely additive.

Roadmap reference: knowledge_base/roadmap/02_roadmap_2026_05.md M6/T601.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
#  Lazy-import shims
# ──────────────────────────────────────────────────────────────────────
#
# Each helper exists *both* in this module (for the new code paths) and
# (still) inline in ``headless_body_workflow.py`` so the M5 module
# continues to work unchanged.  M6 keeps the invariant "every workflow
# module owns its own re-export of the import helpers so tests can
# monkeypatch them locally" — this base module is the *implementation*,
# not the *test-injection point*.
#
# Pattern: every helper tries ``src.core.X`` first (the editable
# install path used by the repo) and falls back to ``core.X`` (the path
# used when the tests load ``src/`` directly into ``sys.path`` — see
# ``tests/test_headless_body_workflow.py``).


def import_model_data():                                    # pragma: no cover - import shim
    """Return the ``core.model_data`` module, deferring the import.

    The dual-try mirrors how ``headless_body_workflow._import_model_data``
    is wired and keeps the same fallback ordering ( ``src.core`` first ,
    then bare ``core`` ).
    """
    try:
        from src.core.qt_core.geometry import model_data as _md             # type: ignore
    except ImportError:
        from core.qt_core.geometry import model_data as _md                 # type: ignore
    return _md


def import_validation_service():                            # pragma: no cover - import shim
    """Return the ``core.validation_service`` module, deferred."""
    try:
        from src.core.qt_core.diagnostics import validation_service as _vs     # type: ignore
    except ImportError:
        from core.qt_core.diagnostics import validation_service as _vs         # type: ignore
    return _vs


def import_accurig():                                       # pragma: no cover - import shim
    """Return the ``autorig.accurig`` module, deferred.

    Used by per-mode workflow services that need AcuRig-style guide
    placement (M5 Body Rig, M6 Head Rig, M8 Creature Rig).
    """
    try:
        from src.autorig import accurig as _ar             # type: ignore
    except ImportError:
        from autorig import accurig as _ar                 # type: ignore
    return _ar


def import_scene_io():                                      # pragma: no cover - import shim
    """Return the ``model_data.SceneIO`` class, deferred.

    Kept separate from :func:`import_model_data` because tests
    sometimes want to fake the sidecar writer independently of the
    rest of ``model_data``.
    """
    md = import_model_data()
    return md.SceneIO


# ──────────────────────────────────────────────────────────────────────
#  Issue summariser
# ──────────────────────────────────────────────────────────────────────
#
# Reduces a list of :class:`ValidationIssue`-like objects into a tuple
# that the Qt bottom-strip can consume directly.  Two important
# invariants per the M5 pattern:
#
#  * Severity is read via ``getattr(severity, "value", str(severity)).lower()``
#    so duck-typed fakes used in tests work the same as the real enum.
#  * The summary string is the upper-cased human form
#    (e.g. ``"2 ERRORS, 3 WARNINGS"`` ) , matching the format that
#    ``qt_bottom_strip.set_validation`` expects.

#: Banner key emitted when a list of issues contains only warnings/info.
#: Used by per-mode services that want to look up a key without having
#: to re-implement the precedence rule.
BANNER_KEY_FOR_SEVERITY = {
    "error":   "error",
    "warning": "warning",
    "info":    "info",
}


def summarize_issues(
    issues: List[Any],
) -> Tuple[str, str, int, int, int, set]:
    """Reduce a list of ValidationIssues into a banner-ready tuple.

    Returns
    -------
    ``(banner_key, summary, errors, warnings, infos, codes)``

    * ``banner_key`` ∈ ``{"clean", "info", "warning", "error"}`` with
      ERROR > WARNING > INFO > CLEAN precedence.
    * ``summary`` is the upper-cased human form, e.g.
      ``"2 ERRORS, 3 WARNINGS"`` or ``"CLEAN"`` when empty.
    * ``errors`` / ``warnings`` / ``infos`` are the per-severity tallies.
    * ``codes`` is the set of distinct issue codes found (handy for
      tests asserting which checks fired).

    This is the canonical pattern documented in M5/T501 invariant #3.
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


def blocking_codes_from_issues(issues: List[Any]) -> List[str]:
    """Return the sorted unique list of ERROR-severity issue codes.

    Used by every ``validate_for_export*`` function so the export gate
    can surface "this is why I refused" to the UI without having to
    re-run the validator.
    """
    return sorted({
        getattr(i, "code", "")
        for i in issues
        if (getattr(getattr(i, "severity", None), "value",
                    getattr(getattr(i, "severity", None), "name", ""))
            or "").lower() == "error"
        and getattr(i, "code", "")
    })


# ──────────────────────────────────────────────────────────────────────
#  Base result dataclasses
# ──────────────────────────────────────────────────────────────────────

@dataclass
class StepResult:
    """Minimal carrier for any workflow step that doesn't need extra fields.

    Per the M5 invariant #2 every workflow result has:

    * ``ok``       ─ True when the step completed cleanly.
    * ``message``  ─ Human-readable summary for the status bar.
    * ``code``     ─ Stable machine tag for tests / branching.

    Per-mode services that need more fields (slot data, counts, etc.)
    should declare their own dataclasses; this one exists so trivial
    steps (e.g. ``rig_face``) can reuse a shared shape.
    """
    ok:      bool = False
    message: str  = ""
    code:    str  = ""


@dataclass
class CheckResult:
    """Result of any Step-2 *Check* function (Check Model / Check Head / …).

    Mirrors :class:`headless_body_workflow.CheckModelResult` field-for-field
    so the Qt bottom-strip can consume either shape interchangeably.

    Attributes
    ----------
    ok           : True when no ERROR-severity issues were found.  WARNINGs
                   do not flip this False (the export step gates on its own
                   re-validation).
    issues       : Full list of :class:`ValidationIssue` instances.
    banner_key   : One of ``"clean" / "info" / "warning" / "error"``.
    summary      : Short banner text, e.g. ``"3 errors, 2 warnings"``.
    error_count / warning_count / info_count : Per-severity tallies.
    codes        : ``set[str]`` of distinct issue codes found.
    """
    ok:            bool       = True
    issues:        List[Any]  = field(default_factory=list)
    banner_key:    str        = "clean"
    summary:       str        = "CLEAN"
    error_count:   int        = 0
    warning_count: int        = 0
    info_count:    int        = 0
    codes:         set        = field(default_factory=set)


@dataclass
class ValidateForExportResult:
    """Result of any Step-6 *Validate for export* function.

    Field-compatible with
    :class:`headless_body_workflow.ValidateForExportResult` so the Qt
    window can consume either shape with the same handler.

    The ``code`` field is one of ``"clean" / "warnings_only" / "blocked"``.
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
    """Per-format result inside an export result wrapper.

    ``code`` is one of:
      * ``"exported"``        — writer ran successfully.
      * ``"not_implemented"`` — writer is M10 work, sidecar still wrote.
      * ``"no_body"`` / ``"no_head"`` — required slot was empty.
      * ``"failed"``          — writer raised.
      * ``"skipped"``         — caller deselected this format.
    """
    key:     str  = ""
    label:   str  = ""
    ok:      bool = False
    path:    str  = ""
    message: str  = ""
    code:    str  = "exported"


@dataclass
class ExportResultBase:
    """Common shape for any export wrapper.

    Per-mode services may subclass to add fields (e.g. a "head export"
    might also surface the headhook transform used).  Field names are
    identical to :class:`headless_body_workflow.ExportResult`.
    """
    ok:           bool                       = False
    formats:      List[ExportFormatResult]   = field(default_factory=list)
    sidecar_path: str                        = ""
    out_dir:      str                        = ""
    message:      str                        = ""
    code:         str                        = "exported"


# ──────────────────────────────────────────────────────────────────────
#  Shared resref / extension helpers
# ──────────────────────────────────────────────────────────────────────
#
# These two helpers exist in every per-mode loader (``_ext_of`` /
# ``_resref_from_path`` in ``headless_body_workflow.py``) and are
# trivially shared.

def ext_of(path: str) -> str:
    """Return the lower-cased file extension (including the leading dot)."""
    import os
    return os.path.splitext(path)[1].lower()


def resref_from_path(path: str) -> str:
    """Return the lower-cased basename-without-extension of *path*.

    Mirrors the M5 ``_resref_from_path`` helper — kept here so per-mode
    services don't have to re-define it.
    """
    import os
    return os.path.splitext(os.path.basename(path))[0].lower()


def safe_resref(text: str, fallback: str = "untitled") -> str:
    """Sanitise a string to a filesystem-safe lower-case resref stem.

    Keeps alphanumerics plus ``_`` and ``-``; everything else is
    dropped.  Returns *fallback* if the result is empty.
    """
    cleaned = "".join(c for c in (text or "").lower()
                      if c.isalnum() or c in ("_", "-"))
    return cleaned or fallback


__all__ = [
    # imports
    "import_model_data",
    "import_validation_service",
    "import_accurig",
    "import_scene_io",
    # summariser
    "BANNER_KEY_FOR_SEVERITY",
    "summarize_issues",
    "blocking_codes_from_issues",
    # dataclasses
    "StepResult",
    "CheckResult",
    "ValidateForExportResult",
    "ExportFormatResult",
    "ExportResultBase",
    # path helpers
    "ext_of",
    "resref_from_path",
    "safe_resref",
]
