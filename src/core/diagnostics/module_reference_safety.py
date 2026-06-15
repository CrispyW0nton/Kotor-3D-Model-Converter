"""Module Editor script/dialog/template reference safety checks.

T1505 catches common "works in the editor, breaks in game" module mistakes
before save/export.  The checker is intentionally headless and conservative:
placed object templates missing from the hydrated module are blocking errors,
while scripts/dialogs unresolved from the module inventory are warnings because
some valid references can live in global game resources.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional


TEMPLATE_LIST_SPECS: dict[str, tuple[tuple[str, ...], str]] = {
    "creature": (("Creature List", "CreatureList"), "utc"),
    "door": (("Door List", "DoorList"), "utd"),
    "placeable": (("Placeable List", "PlaceableList"), "utp"),
    "trigger": (("TriggerList", "Trigger List"), "utt"),
    "encounter": (("Encounter List", "EncounterList"), "ute"),
    "waypoint": (("WaypointList", "Waypoint List"), "utw"),
    "sound": (("SoundList", "Sound List"), "uts"),
    "store": (("StoreList", "Store List"), "utm"),
}

SCRIPT_FIELD_NAMES = {
    "onacquireitem",
    "onactivateitem",
    "onattacked",
    "onblocked",
    "onclosed",
    "ondamaged",
    "ondeath",
    "ondialog",
    "ondisarm",
    "onenddialog",
    "onenter",
    "onexit",
    "onfailtoopen",
    "onheartbeat",
    "onmeleeattacked",
    "onnotice",
    "onopen",
    "onperception",
    "onphysicalattacked",
    "onrest",
    "onrested",
    "onspawn",
    "onspellcastat",
    "ontraptriggered",
    "onunaquireitem",
    "onunacquireitem",
    "onused",
    "onuserdefined",
    "mod_onacquiritem",
    "mod_onactivateit",
    "mod_oncliententr",
    "mod_onclientlev",
    "mod_onheartbeat",
    "mod_onmodload",
    "mod_onmodstart",
    "mod_onplayerdye",
    "mod_onplrdth",
    "mod_onplrrest",
    "mod_onspawnbtndn",
    "mod_onunacquir",
}

DIALOG_FIELD_NAMES = {
    "conversation",
    "conversationresref",
    "dialog",
    "dialogresref",
}


@dataclass(frozen=True)
class ModuleReference:
    """One reference discovered in module data."""

    kind: str
    resref: str
    restype: str
    owner_type: str
    owner_index: int = -1
    field: str = ""
    source_label: str = ""


@dataclass(frozen=True)
class ModuleReferenceIssue:
    """Actionable missing-reference finding."""

    severity: str
    code: str
    message: str
    reference: ModuleReference
    action: str = ""


@dataclass
class ModuleReferenceSafetyReport:
    """Pre-save reference report for a hydrated module."""

    ok: bool = False
    references: list[ModuleReference] = field(default_factory=list)
    issues: list[ModuleReferenceIssue] = field(default_factory=list)
    available: dict[str, list[str]] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    message: str = ""
    code: str = "not_checked"

    @property
    def blocking_issues(self) -> list[ModuleReferenceIssue]:
        return [issue for issue in self.issues if issue.severity.lower() == "error"]


def _module_from_input(value: Any) -> Any:
    return getattr(value, "module", value)


def _normalise_resref(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if "." in text:
        text = text.rsplit(".", 1)[0]
    return text[:16]


def _normalise_restype(value: Any) -> str:
    return str(value or "").strip().lower().lstrip(".")


def _record_key(value: Any) -> tuple[str, str]:
    record = getattr(value, "record", value)
    if isinstance(record, tuple) and len(record) >= 2:
        return (_normalise_resref(record[0]), _normalise_restype(record[1]))
    if isinstance(record, str):
        stem, _, ext = record.rpartition(".")
        return (_normalise_resref(stem), _normalise_restype(ext))
    return (
        _normalise_resref(getattr(record, "resref", "")),
        _normalise_restype(getattr(record, "restype", getattr(record, "type", ""))),
    )


def _resources_from_input(module_like: Any) -> Iterable[Any]:
    resources = getattr(module_like, "resources", {}) or {}
    if isinstance(resources, dict):
        for key, value in resources.items():
            if hasattr(value, "record"):
                yield value
            else:
                resref, restype = _record_key(key)
                yield type("_ResourceRecordAdapter", (), {"resref": resref, "restype": restype})()
    elif isinstance(resources, list):
        yield from resources


def _available_index(module_like: Any, extra_available: Iterable[Any] | None = None) -> dict[str, set[str]]:
    available: dict[str, set[str]] = {}

    def _add(resref: str, restype: str) -> None:
        resref = _normalise_resref(resref)
        restype = _normalise_restype(restype)
        if resref and restype:
            available.setdefault(restype, set()).add(resref)

    for resource in _resources_from_input(module_like):
        resref, restype = _record_key(resource)
        _add(resref, restype)

    templates = getattr(module_like, "templates", {}) or {}
    if isinstance(templates, dict):
        for restype, entries in templates.items():
            for entry in list(entries or []):
                resref, detected_type = _record_key(entry)
                _add(resref, detected_type or str(restype))

    for entry in list(getattr(module_like, "scripts", []) or []):
        resref, restype = _record_key(entry)
        _add(resref, restype or "ncs")
    for entry in list(getattr(module_like, "dialogs", []) or []):
        resref, restype = _record_key(entry)
        _add(resref, restype or "dlg")

    for entry in list(extra_available or []):
        resref, restype = _record_key(entry)
        _add(resref, restype)

    return available


def _git_raw(module_like: Any) -> dict[str, Any]:
    module = _module_from_input(module_like)
    git = getattr(module, "git", None)
    raw = getattr(git, "_raw", None)
    return raw if isinstance(raw, dict) else {}


def _core_raw(module_like: Any) -> list[tuple[str, dict[str, Any]]]:
    module = _module_from_input(module_like)
    out: list[tuple[str, dict[str, Any]]] = []
    for label, attr in (("are", "are"), ("ifo", "ifo")):
        raw = getattr(getattr(module, attr, None), "_raw", None)
        if isinstance(raw, dict):
            out.append((label, raw))
    return out


def _raw_list(raw: dict[str, Any], labels: tuple[str, ...]) -> tuple[str, list[Any]]:
    for label in labels:
        value = raw.get(label)
        if isinstance(value, list):
            return label, value
    return labels[0], []


def _script_field(key: str) -> bool:
    lower = key.lower()
    return lower in SCRIPT_FIELD_NAMES or lower.startswith("script") or lower.startswith("mod_on")


def _dialog_field(key: str) -> bool:
    return key.lower() in DIALOG_FIELD_NAMES


def _iter_script_dialog_refs(raw: dict[str, Any], *, owner_type: str, owner_index: int = -1) -> Iterable[ModuleReference]:
    for key, value in raw.items():
        if isinstance(value, str):
            resref = _normalise_resref(value)
            if not resref:
                continue
            if _dialog_field(key):
                yield ModuleReference(
                    kind="dialog",
                    resref=resref,
                    restype="dlg",
                    owner_type=owner_type,
                    owner_index=owner_index,
                    field=key,
                    source_label=f"{owner_type}.{owner_index}.{key}" if owner_index >= 0 else f"{owner_type}.{key}",
                )
            elif _script_field(key):
                yield ModuleReference(
                    kind="script",
                    resref=resref,
                    restype="ncs",
                    owner_type=owner_type,
                    owner_index=owner_index,
                    field=key,
                    source_label=f"{owner_type}.{owner_index}.{key}" if owner_index >= 0 else f"{owner_type}.{key}",
                )
        elif isinstance(value, dict):
            yield from _iter_script_dialog_refs(value, owner_type=owner_type, owner_index=owner_index)


def collect_module_references(module_like: Any) -> list[ModuleReference]:
    """Collect template, script, and dialog references from hydrated module data."""

    references: list[ModuleReference] = []
    git_raw = _git_raw(module_like)
    for object_type, (labels, template_type) in TEMPLATE_LIST_SPECS.items():
        list_label, rows = _raw_list(git_raw, labels)
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            template = _normalise_resref(row.get("TemplateResRef") or row.get("ResRef") or "")
            if template:
                references.append(
                    ModuleReference(
                        kind="template",
                        resref=template,
                        restype=template_type,
                        owner_type=object_type,
                        owner_index=index,
                        field="TemplateResRef",
                        source_label=f"{list_label}.{index}.TemplateResRef",
                    )
                )
            references.extend(_iter_script_dialog_refs(row, owner_type=object_type, owner_index=index))

    for owner_type, raw in _core_raw(module_like):
        references.extend(_iter_script_dialog_refs(raw, owner_type=owner_type))

    return references


def _has_reference(
    available: dict[str, set[str]],
    reference: ModuleReference,
    resolver: Optional[Callable[[str, str], bool]],
) -> bool:
    if reference.restype in available and reference.resref in available[reference.restype]:
        return True
    if reference.kind == "script":
        if reference.resref in available.get("ncs", set()) or reference.resref in available.get("nss", set()):
            return True
    if resolver is not None:
        try:
            return bool(resolver(reference.resref, reference.restype))
        except TypeError:
            return bool(resolver(f"{reference.resref}.{reference.restype}"))
    return False


def _issue_for_missing(reference: ModuleReference) -> ModuleReferenceIssue:
    if reference.kind == "template":
        return ModuleReferenceIssue(
            severity="error",
            code="MISSING_TEMPLATE",
            message=(
                f"{reference.owner_type} {reference.owner_index} references missing "
                f"{reference.restype.upper()} template '{reference.resref}'."
            ),
            reference=reference,
            action="Add the template to the module static archive or choose an existing template.",
        )
    if reference.kind == "dialog":
        return ModuleReferenceIssue(
            severity="warning",
            code="UNRESOLVED_DIALOG",
            message=(
                f"{reference.source_label} references dialog '{reference.resref}.dlg', "
                "but it was not found in the hydrated module resources."
            ),
            reference=reference,
            action="Verify the DLG exists in the module, Override, or base game resources before save.",
        )
    return ModuleReferenceIssue(
        severity="warning",
        code="UNRESOLVED_SCRIPT",
        message=(
            f"{reference.source_label} references script '{reference.resref}', "
            "but no matching NCS/NSS was found in the hydrated module resources."
        ),
        reference=reference,
        action="Compile or include the script, or verify it exists in global game resources.",
    )


def validate_module_references(
    module_like: Any,
    *,
    extra_available: Iterable[Any] | None = None,
    resolver: Optional[Callable[[str, str], bool]] = None,
) -> ModuleReferenceSafetyReport:
    """Return a pre-save report of broken template/script/dialog references."""

    references = collect_module_references(module_like)
    available = _available_index(module_like, extra_available)
    issues = [
        _issue_for_missing(reference)
        for reference in references
        if not _has_reference(available, reference, resolver)
    ]
    counts: dict[str, int] = {}
    for reference in references:
        counts[reference.kind] = counts.get(reference.kind, 0) + 1
    for issue in issues:
        counts[f"{issue.severity.lower()}_issues"] = counts.get(f"{issue.severity.lower()}_issues", 0) + 1

    blocking = [issue for issue in issues if issue.severity.lower() == "error"]
    return ModuleReferenceSafetyReport(
        ok=not blocking,
        references=references,
        issues=issues,
        available={key: sorted(values) for key, values in sorted(available.items())},
        counts=counts,
        message=(
            "Module references passed blocking safety checks."
            if not blocking else
            f"Module reference safety found {len(blocking)} blocking issue(s)."
        ),
        code="valid" if not blocking else "invalid",
    )


__all__ = [
    "ModuleReference",
    "ModuleReferenceIssue",
    "ModuleReferenceSafetyReport",
    "collect_module_references",
    "validate_module_references",
]
