"""Project Map Studio readiness into KMAP validation-table issues.

The Level Editor already has a validation table with suggested fixes.  This
module keeps the authored-module readiness policy in core while giving the UI a
plain issue list it can display without knowing how readiness is derived.
"""

from __future__ import annotations

from typing import Any, Iterable

from src.core.level import KMapValidationIssue


def authored_module_readiness_validation_issues(
    readiness: Any | None,
    *,
    bridge_warnings: Iterable[str] = (),
    bridge_blocking_messages: Iterable[str] = (),
) -> list[KMapValidationIssue]:
    """Return validation rows for Map Studio readiness/status state."""

    issues: list[KMapValidationIssue] = []
    for index, message in enumerate(tuple(bridge_blocking_messages or ())):
        issues.append(
            KMapValidationIssue(
                "Error",
                "MAP_STUDIO_AUTHORED_SECTION_INVALID",
                str(message),
                f"authored_module:bridge:{index}",
                "Open the KMAP in Map Studio Builder and recreate or repair the authored module section.",
            )
        )
    for index, message in enumerate(tuple(bridge_warnings or ())):
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_AUTHORED_MODULE_MISSING",
                str(message),
                f"authored_module:bridge_warning:{index}",
                "Use Map Studio Builder to create terrain, a starter room, or a dev-test map before export.",
            )
        )
    if readiness is None:
        return _dedupe(issues)

    for item in tuple(getattr(readiness, "inputs", ()) or ()):
        if bool(getattr(item, "present", False)):
            continue
        name = str(getattr(item, "name", "") or "Map Studio input")
        value = str(getattr(item, "value_label", "") or "")
        fix = str(getattr(item, "fix_hint", "") or "Fill in this Map Studio input before preview/export.")
        issues.append(
            KMapValidationIssue(
                "Error",
                "MAP_STUDIO_INPUT_MISSING",
                f"{name} is not ready. {value}".strip(),
                f"authored_input:{_slug(name)}",
                fix,
            )
        )

    for index, message in enumerate(tuple(getattr(readiness, "blocking_messages", ()) or ())):
        issues.append(
            KMapValidationIssue(
                "Error",
                "MAP_STUDIO_READINESS_BLOCKER",
                str(message),
                f"authored_blocker:{index}",
                "Fix this authored module blocker before preview, staged export, or install.",
            )
        )

    for resource in tuple(getattr(readiness, "missing_runtime_resources", ()) or ()):
        resref, restype = _resource_label(resource)
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_RUNTIME_RESOURCE_MISSING",
                f"Runtime resource {resref}.{restype} has not been generated or staged.",
                f"authored_runtime:{resref}.{restype}",
                "Stage/build the authored module so ARE/GIT/IFO/PTH/LYT/VIS, room MDL/MDX, and WOK files are present.",
            )
        )

    for status in tuple(getattr(readiness, "toolchain", ()) or ()):
        if bool(getattr(status, "ready", False)):
            continue
        name = str(getattr(status, "name", "") or "Map Studio step")
        status_text = str(getattr(status, "status", "") or "Not ready")
        value = str(getattr(status, "value_label", "") or "")
        fix = str(getattr(status, "fix_hint", "") or "Complete this Map Studio step before export/install.")
        severity = "Error" if name in {"Geometry authoring", "Walkmesh", "Gameplay layout"} and not bool(getattr(readiness, "can_preview", False)) else "Warning"
        issues.append(
            KMapValidationIssue(
                severity,
                "MAP_STUDIO_TOOLCHAIN_NOT_READY",
                f"{name}: {status_text}. {value}".strip(),
                f"authored_toolchain:{_slug(name)}",
                fix,
            )
        )

    metadata = dict(getattr(readiness, "metadata", {}) or {})
    for ref in tuple(metadata.get("transition_references") or ()):
        if bool(ref.get("complete", False)):
            continue
        label = str(ref.get("tag") or ref.get("template_resref") or ref.get("kind") or "transition")
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_TRANSITION_DESTINATION_MISSING",
                str(ref.get("message") or f"Transition {label} is missing a destination."),
                f"authored_transition:{_slug(label)}",
                "Set LinkedTo plus LinkedToModule/TransitionDestin in the selected door, trigger, or waypoint properties.",
            )
        )

    for ref in tuple(metadata.get("script_references") or ()):
        if bool(ref.get("packaged", False)):
            continue
        script = str(ref.get("script_resref") or "script")
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_SCRIPT_EXTERNAL",
                str(ref.get("message") or f"Script hook {script}.ncs is external."),
                f"authored_script:{_slug(script)}",
                "Package the custom NCS script or confirm the base-game/Override script is installed for the test.",
            )
        )

    for ref in tuple(metadata.get("gameplay_template_references") or ()):
        if bool(ref.get("packaged", False)):
            continue
        template = str(ref.get("template_resref") or "template")
        restype = str(ref.get("restype") or "resource")
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_TEMPLATE_EXTERNAL",
                str(ref.get("message") or f"Template {template}.{restype} is external."),
                f"authored_template:{_slug(template)}.{restype}",
                "Package custom templates or verify the template exists in the base game, Override, or another installed mod.",
            )
        )

    if bool(getattr(readiness, "ready_for_game_test", False)) and not bool(getattr(readiness, "game_tested", False)):
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_GAME_PROOF_REQUIRED",
                "Module is exportable but not game-ready until a live KOTOR warp test is recorded.",
                "authored_module:proof",
                "Install the staged .mod, warp to the module in KOTOR, then record screenshot/video proof.",
            )
        )

    for index, message in enumerate(tuple(getattr(readiness, "warnings", ()) or ())):
        issues.append(
            KMapValidationIssue(
                "Warning",
                "MAP_STUDIO_READINESS_WARNING",
                str(message),
                f"authored_warning:{index}",
                "Review this Map Studio readiness warning before calling the module export-ready.",
            )
        )
    return _dedupe(issues)


def _resource_label(resource: Any) -> tuple[str, str]:
    if isinstance(resource, tuple) and len(resource) >= 2:
        return str(resource[0] or "").strip() or "module", str(resource[1] or "").strip().lower() or "resource"
    text = str(resource or "").strip()
    stem, dot, ext = text.rpartition(".")
    if dot:
        return stem or "module", ext.lower() or "resource"
    return text or "module", "resource"


def _slug(value: str) -> str:
    text = str(value or "").strip().lower()
    return "".join(ch if ch.isalnum() else "_" for ch in text).strip("_") or "item"


def _dedupe(issues: list[KMapValidationIssue]) -> list[KMapValidationIssue]:
    seen: set[tuple[str, str, str]] = set()
    result: list[KMapValidationIssue] = []
    for issue in issues:
        key = (issue.code, issue.message, issue.item_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result


__all__ = ["authored_module_readiness_validation_issues"]
