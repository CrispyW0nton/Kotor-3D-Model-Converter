"""Module Editor object-inspector forms.

T1502 builds the headless form model for editing placed module objects.  The
service prefers the original GIT GFF dictionaries when present, so edits can be
written back without losing fields GhostRigger does not yet model directly.
It also falls back to the typed ``module_format.GITData`` lists for tests and
partially hydrated modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


PRIMITIVE_TYPES = (str, int, float, bool, type(None))


@dataclass(frozen=True)
class ObjectListSpec:
    object_type: str
    labels: tuple[str, ...]
    attr: str
    template_type: str = ""
    position_keys: tuple[str, str, str] = ("XPosition", "YPosition", "ZPosition")
    bearing_keys: tuple[str, ...] = ("Bearing", "XOrientation")


OBJECT_SPECS: dict[str, ObjectListSpec] = {
    "creature": ObjectListSpec("creature", ("Creature List", "CreatureList"), "creatures", "utc"),
    "door": ObjectListSpec("door", ("Door List", "DoorList"), "doors", "utd", ("X", "Y", "Z")),
    "placeable": ObjectListSpec("placeable", ("Placeable List", "PlaceableList"), "placeables", "utp", ("X", "Y", "Z")),
    "trigger": ObjectListSpec("trigger", ("TriggerList", "Trigger List"), "triggers", "utt"),
    "encounter": ObjectListSpec("encounter", ("Encounter List", "EncounterList"), "encounters", "ute"),
    "waypoint": ObjectListSpec("waypoint", ("WaypointList", "Waypoint List"), "waypoints", "utw"),
    "sound": ObjectListSpec("sound", ("SoundList", "Sound List"), "sounds", "uts"),
    "store": ObjectListSpec("store", ("StoreList", "Store List"), "stores", "utm"),
}


FIELD_LABELS: dict[str, str] = {
    "TemplateResRef": "Template",
    "Tag": "Tag",
    "XPosition": "X",
    "YPosition": "Y",
    "ZPosition": "Z",
    "X": "X",
    "Y": "Y",
    "Z": "Z",
    "Bearing": "Bearing",
    "XOrientation": "Orientation X",
    "YOrientation": "Orientation Y",
    "LinkedTo": "Linked To",
    "LinkedToModule": "Linked Module",
    "TransitionDestin": "Transition Destination",
    "LocalizedName": "Name",
    "Conversation": "Conversation",
    "OnEnter": "On Enter",
    "OnExit": "On Exit",
    "OnUsed": "On Used",
}


@dataclass(frozen=True)
class ModuleObjectField:
    """One editable/display field in an inspector form."""

    key: str
    label: str
    value: Any = None
    value_type: str = "string"
    editable: bool = True


@dataclass
class ModuleObjectForm:
    """Inspector form for one placed module object."""

    object_type: str
    index: int
    list_label: str = ""
    template_resref: str = ""
    template_type: str = ""
    template_available: bool = False
    template_source: str = ""
    tag: str = ""
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    bearing: float = 0.0
    fields: list[ModuleObjectField] = field(default_factory=list)
    raw: Optional[dict[str, Any]] = None
    parent_type: str = ""
    parent_index: int = -1


@dataclass
class ModuleObjectInspectorResult:
    """All object forms exposed by the Module Editor inspector."""

    ok: bool = False
    forms: dict[str, list[ModuleObjectForm]] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    message: str = ""
    code: str = "not_loaded"


@dataclass
class ModuleObjectEditResult:
    """Result of applying a form edit to the backing GIT data."""

    ok: bool = False
    form: Optional[ModuleObjectForm] = None
    old_value: Any = None
    new_value: Any = None
    message: str = ""
    code: str = "not_edited"


def _module_from_input(value: Any) -> Any:
    return getattr(value, "module", value)


def _git_from_input(value: Any) -> Any:
    module = _module_from_input(value)
    return getattr(module, "git", None)


def _git_raw(git: Any) -> dict[str, Any]:
    raw = getattr(git, "_raw", None)
    return raw if isinstance(raw, dict) else {}


def _field_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "struct"
    return "string"


def _coerce_value(value: Any, target_type: str) -> Any:
    if target_type == "bool":
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)
    if target_type == "int":
        return int(value)
    if target_type == "float":
        return float(value)
    return value


def _raw_list(raw: dict[str, Any], spec: ObjectListSpec) -> tuple[str, list[Any]]:
    for label in spec.labels:
        value = raw.get(label)
        if isinstance(value, list):
            return label, value
    return spec.labels[0], []


def _dataclass_items(git: Any, spec: ObjectListSpec) -> list[Any]:
    value = getattr(git, spec.attr, None)
    if isinstance(value, list):
        return value
    return []


def _get_value(raw: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in raw:
            return raw[key]
    return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _object_position(raw: dict[str, Any], spec: ObjectListSpec) -> tuple[float, float, float]:
    x_key, y_key, z_key = spec.position_keys
    return (
        _as_float(_get_value(raw, x_key, default=0.0)),
        _as_float(_get_value(raw, y_key, default=0.0)),
        _as_float(_get_value(raw, z_key, default=0.0)),
    )


def _object_bearing(raw: dict[str, Any], spec: ObjectListSpec) -> float:
    return _as_float(_get_value(raw, *spec.bearing_keys, default=0.0))


def _object_template(raw: dict[str, Any]) -> str:
    return str(_get_value(raw, "TemplateResRef", "ResRef", "Tag", default="") or "").lower()


def _object_tag(raw: dict[str, Any]) -> str:
    return str(_get_value(raw, "Tag", default="") or "")


def _dataclass_to_raw(item: Any, spec: ObjectListSpec) -> dict[str, Any]:
    raw = dict(getattr(item, "__dict__", {}) or {})
    if "TemplateResRef" not in raw:
        raw["TemplateResRef"] = raw.get("resref", getattr(item, "resref", ""))
    if "Tag" not in raw and "tag" in raw:
        raw["Tag"] = raw.get("tag", "")
    elif "Tag" not in raw:
        raw["Tag"] = getattr(item, "tag", "")
    x_key, y_key, z_key = spec.position_keys
    raw.setdefault(x_key, raw.get("x", getattr(item, "x", 0.0)))
    raw.setdefault(y_key, raw.get("y", getattr(item, "y", 0.0)))
    raw.setdefault(z_key, raw.get("z", getattr(item, "z", 0.0)))
    raw.setdefault(spec.bearing_keys[0], raw.get("bearing", getattr(item, "bearing", 0.0)))
    return raw


def _field_sort_key(item: tuple[str, Any]) -> tuple[int, str]:
    priority = [
        "TemplateResRef",
        "Tag",
        "XPosition",
        "YPosition",
        "ZPosition",
        "X",
        "Y",
        "Z",
        "Bearing",
        "XOrientation",
        "YOrientation",
        "LinkedTo",
        "LinkedToModule",
        "TransitionDestin",
    ]
    try:
        return (priority.index(item[0]), item[0])
    except ValueError:
        return (len(priority), item[0])


def _form_fields(raw: dict[str, Any]) -> list[ModuleObjectField]:
    fields: list[ModuleObjectField] = []
    for key, value in sorted(raw.items(), key=_field_sort_key):
        value_type = _field_type(value)
        editable = isinstance(value, PRIMITIVE_TYPES)
        display_value = value if editable else f"{value_type}:{len(value) if hasattr(value, '__len__') else ''}"
        fields.append(
            ModuleObjectField(
                key=key,
                label=FIELD_LABELS.get(key, key),
                value=display_value,
                value_type=value_type,
                editable=editable,
            )
        )
    return fields


def _template_index(module_like: Any) -> dict[tuple[str, str], Any]:
    templates = getattr(module_like, "templates", {}) or {}
    index: dict[tuple[str, str], Any] = {}
    if isinstance(templates, dict):
        for restype, entries in templates.items():
            for entry in list(entries or []):
                record = getattr(entry, "record", entry)
                resref = str(getattr(record, "resref", "") or "").lower()
                if resref:
                    index[(str(restype).lower(), resref)] = entry
    return index


def _template_source(entry: Any) -> str:
    record = getattr(entry, "record", entry)
    return str(getattr(record, "source", "") or "")


def _make_form(
    raw: dict[str, Any],
    *,
    spec: ObjectListSpec,
    index: int,
    list_label: str,
    templates: dict[tuple[str, str], Any],
) -> ModuleObjectForm:
    template_resref = _object_template(raw)
    template_entry = templates.get((spec.template_type, template_resref))
    return ModuleObjectForm(
        object_type=spec.object_type,
        index=index,
        list_label=list_label,
        template_resref=template_resref,
        template_type=spec.template_type,
        template_available=template_entry is not None,
        template_source=_template_source(template_entry) if template_entry is not None else "",
        tag=_object_tag(raw),
        position=_object_position(raw, spec),
        bearing=_object_bearing(raw, spec),
        fields=_form_fields(raw),
        raw=raw,
    )


def _transition_forms(raw: dict[str, Any], source_forms: dict[str, list[ModuleObjectForm]]) -> list[ModuleObjectForm]:
    forms: list[ModuleObjectForm] = []
    for parent_type in ("door", "trigger"):
        spec = OBJECT_SPECS[parent_type]
        list_label, rows = _raw_list(raw, spec)
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            if not any(key in row for key in ("LinkedTo", "LinkedToModule", "TransitionDestin")):
                continue
            transition_raw = {
                key: row.get(key, "")
                for key in ("TemplateResRef", "Tag", "LinkedTo", "LinkedToModule", "TransitionDestin")
                if key in row
            }
            form = ModuleObjectForm(
                object_type="transition",
                index=len(forms),
                list_label=f"{list_label}.{index}",
                template_resref=_object_template(row),
                tag=_object_tag(row),
                fields=_form_fields(transition_raw),
                raw=row,
                parent_type=parent_type,
                parent_index=index,
            )
            forms.append(form)
    if forms:
        source_forms["transition"] = forms
    return forms


def build_module_object_inspector(module_like: Any) -> ModuleObjectInspectorResult:
    """Build GFF-backed forms for placed module objects."""

    git = _git_from_input(module_like)
    if git is None:
        return ModuleObjectInspectorResult(
            warnings=["Hydrate a module with GIT data before opening the object inspector."],
            message="No GIT data is available.",
            code="no_git",
        )

    raw = _git_raw(git)
    templates = _template_index(module_like)
    forms: dict[str, list[ModuleObjectForm]] = {}
    warnings: list[str] = []

    for object_type, spec in OBJECT_SPECS.items():
        list_label, rows = _raw_list(raw, spec)
        object_forms: list[ModuleObjectForm] = []
        if rows:
            for index, row in enumerate(rows):
                if isinstance(row, dict):
                    object_forms.append(
                        _make_form(row, spec=spec, index=index, list_label=list_label, templates=templates)
                    )
        else:
            for index, item in enumerate(_dataclass_items(git, spec)):
                object_forms.append(
                    _make_form(
                        _dataclass_to_raw(item, spec),
                        spec=spec,
                        index=index,
                        list_label=list_label,
                        templates=templates,
                    )
                )
        if object_forms:
            forms[object_type] = object_forms

    _transition_forms(raw, forms)
    counts = {object_type: len(values) for object_type, values in forms.items()}
    if not counts:
        warnings.append("GIT data exists but no editable object lists were found.")
    return ModuleObjectInspectorResult(
        ok=bool(counts),
        forms=forms,
        counts=counts,
        warnings=warnings,
        message=(
            f"Built {sum(counts.values())} module object form(s)."
            if counts else
            "No module object forms were built."
        ),
        code="listed" if counts else "empty",
    )


def _find_form(result: ModuleObjectInspectorResult, object_type: str, index: int) -> Optional[ModuleObjectForm]:
    values = result.forms.get(object_type, [])
    if index < 0 or index >= len(values):
        return None
    return values[index]


def apply_object_form_edit(
    module_like: Any,
    object_type: str,
    index: int,
    field_key: str,
    value: Any,
) -> ModuleObjectEditResult:
    """Apply one inspector edit to the GIT-backed form data."""

    result = build_module_object_inspector(module_like)
    form = _find_form(result, object_type, index)
    if form is None or form.raw is None:
        return ModuleObjectEditResult(
            message=f"No {object_type} form at index {index}.",
            code="form_missing",
        )
    matching = [field for field in form.fields if field.key == field_key]
    if not matching:
        return ModuleObjectEditResult(
            form=form,
            message=f"Field '{field_key}' is not present on {object_type} form {index}.",
            code="field_missing",
        )
    field = matching[0]
    if not field.editable:
        return ModuleObjectEditResult(
            form=form,
            old_value=field.value,
            message=f"Field '{field_key}' is not directly editable.",
            code="field_readonly",
        )

    old_value = form.raw.get(field_key)
    try:
        new_value = _coerce_value(value, field.value_type)
    except Exception as exc:
        return ModuleObjectEditResult(
            form=form,
            old_value=old_value,
            new_value=value,
            message=f"Could not convert '{field_key}' to {field.value_type}: {exc}",
            code="coerce_failed",
        )
    form.raw[field_key] = new_value
    return ModuleObjectEditResult(
        ok=True,
        form=form,
        old_value=old_value,
        new_value=new_value,
        message=f"Updated {object_type}.{index}.{field_key}.",
        code="edited",
    )


__all__ = [
    "ModuleObjectField",
    "ModuleObjectForm",
    "ModuleObjectInspectorResult",
    "ModuleObjectEditResult",
    "build_module_object_inspector",
    "apply_object_form_edit",
]
