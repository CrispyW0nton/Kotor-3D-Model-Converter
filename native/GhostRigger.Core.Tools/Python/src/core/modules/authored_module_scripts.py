"""Qt-free authored Map Studio script hook editing helpers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .authored_module_metadata import AREA_SCRIPT_FIELDS, MODULE_SCRIPT_FIELDS
from .authored_module_project import AuthoredModuleProject, authored_resref_blocking_issue, normalise_resref


SCRIPT_HOOK_SCOPES: tuple[str, ...] = ("area", "module")


@dataclass(frozen=True)
class AuthoredScriptHookUpdate:
    """Result of editing one authored ARE/IFO script hook."""

    project: AuthoredModuleProject
    scope: str
    field_name: str
    script_resref: str
    removed: bool = False
    warnings: tuple[str, ...] = ()


def _normalise_scope(scope: Any) -> str:
    text = str(scope or "").strip().lower()
    if text in {"area", "are"}:
        return "area"
    if text in {"module", "ifo"}:
        return "module"
    raise ValueError("Script hook scope must be 'area' or 'module'.")


def _fields_for_scope(scope: str) -> tuple[str, ...]:
    return AREA_SCRIPT_FIELDS if scope == "area" else MODULE_SCRIPT_FIELDS


def _metadata_key_for_scope(scope: str) -> str:
    return "area_scripts" if scope == "area" else "module_scripts"


def _normalise_field_name(scope: str, field_name: Any) -> str:
    wanted = str(field_name or "").strip().lower()
    fields = _fields_for_scope(scope)
    for candidate in fields:
        if candidate.lower() == wanted:
            return candidate
    known = ", ".join(fields)
    raise ValueError(f"{scope.title()} script field '{field_name}' is not supported. Known fields: {known}.")


def authored_script_hook_field_choices() -> dict[str, tuple[str, ...]]:
    """Return UI-ready KOTOR script hook fields grouped by editable scope."""

    return {
        "area": AREA_SCRIPT_FIELDS,
        "module": MODULE_SCRIPT_FIELDS,
    }


def authored_script_hooks(project: AuthoredModuleProject) -> dict[str, dict[str, str]]:
    """Return normalized script hook metadata for display/edit controls."""

    metadata = dict(project.metadata.metadata)
    return {
        "area": {
            _normalise_field_name("area", field): normalise_resref(script)
            for field, script in dict(metadata.get("area_scripts") or metadata.get("are_scripts") or {}).items()
            if str(script or "").strip()
        },
        "module": {
            _normalise_field_name("module", field): normalise_resref(script)
            for field, script in dict(metadata.get("module_scripts") or metadata.get("ifo_scripts") or {}).items()
            if str(script or "").strip()
        },
    }


def set_authored_script_hook(
    project: AuthoredModuleProject,
    *,
    scope: Any,
    field_name: Any,
    script_resref: Any,
) -> AuthoredScriptHookUpdate:
    """Assign a script resref to one authored ARE/IFO hook."""

    normalized_scope = _normalise_scope(scope)
    normalized_field = _normalise_field_name(normalized_scope, field_name)
    script = normalise_resref(script_resref)
    issue = authored_resref_blocking_issue(f"{normalized_scope.title()} script {normalized_field}", script_resref)
    if issue:
        raise ValueError(issue)

    metadata = dict(project.metadata.metadata)
    key = _metadata_key_for_scope(normalized_scope)
    hooks = dict(metadata.get(key) or {})
    hooks[normalized_field] = script
    metadata[key] = hooks
    updated_metadata = replace(project.metadata, metadata=metadata)
    return AuthoredScriptHookUpdate(
        project=replace(project, metadata=updated_metadata),
        scope=normalized_scope,
        field_name=normalized_field,
        script_resref=script,
    )


def remove_authored_script_hook(
    project: AuthoredModuleProject,
    *,
    scope: Any,
    field_name: Any,
) -> AuthoredScriptHookUpdate:
    """Clear one authored ARE/IFO script hook."""

    normalized_scope = _normalise_scope(scope)
    normalized_field = _normalise_field_name(normalized_scope, field_name)
    metadata = dict(project.metadata.metadata)
    key = _metadata_key_for_scope(normalized_scope)
    hooks = dict(metadata.get(key) or {})
    removed_script = normalise_resref(hooks.pop(normalized_field, ""))
    if hooks:
        metadata[key] = hooks
    else:
        metadata.pop(key, None)
    updated_metadata = replace(project.metadata, metadata=metadata)
    return AuthoredScriptHookUpdate(
        project=replace(project, metadata=updated_metadata),
        scope=normalized_scope,
        field_name=normalized_field,
        script_resref=removed_script,
        removed=True,
    )


__all__ = [
    "AuthoredScriptHookUpdate",
    "SCRIPT_HOOK_SCOPES",
    "authored_script_hook_field_choices",
    "authored_script_hooks",
    "remove_authored_script_hook",
    "set_authored_script_hook",
]
