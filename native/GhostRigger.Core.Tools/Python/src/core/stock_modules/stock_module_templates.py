"""Read-only gameplay template inventories for stock KotOR module archives."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
from src.core.stock_modules.stock_module_archive import ModuleArchiveResource, read_module_resource_bytes


TEMPLATE_TYPES = {"utc", "utd", "utp", "uti", "utt", "uts", "ute", "utm", "utw"}

TEMPLATE_KIND_LABELS = {
    "utc": "Creature/NPC",
    "utd": "Door",
    "utp": "Placeable",
    "uti": "Item",
    "utt": "Trigger",
    "uts": "Sound",
    "ute": "Encounter",
    "utm": "Store/Merchant",
    "utw": "Waypoint",
}

FIELD_LABELS = {
    "TemplateResRef": "Template resref",
    "Tag": "Tag",
    "LocalizedName": "Name",
    "FirstName": "First name",
    "LastName": "Last name",
    "Name": "Name",
    "Conversation": "Conversation",
    "Comment": "Comment",
    "ScriptHeartbeat": "On heartbeat",
    "ScriptOnNotice": "On notice",
    "ScriptSpawn": "On spawn",
    "ScriptDamaged": "On damaged",
    "ScriptDeath": "On death",
    "ScriptDialogue": "On dialogue",
    "ScriptDisturbed": "On disturbed",
    "ScriptEndDialogu": "On end dialogue",
    "ScriptUserDefine": "On user defined",
    "OnClosed": "On closed",
    "OnDamaged": "On damaged",
    "OnDeath": "On death",
    "OnDisarm": "On disarm",
    "OnFailToOpen": "On fail to open",
    "OnHeartbeat": "On heartbeat",
    "OnInvDisturbed": "On inventory disturbed",
    "OnLock": "On lock",
    "OnMeleeAttacked": "On melee attacked",
    "OnOpen": "On open",
    "OnSpellCastAt": "On spell cast at",
    "OnTrapTriggered": "On trap triggered",
    "OnUnlock": "On unlock",
    "OnUsed": "On used",
    "OnEnter": "On enter",
    "OnExit": "On exit",
    "OnClick": "On click",
    "OnStoreOpen": "On store open",
    "FactionID": "Faction",
    "Appearance_Type": "Appearance",
    "PaletteID": "Palette",
    "ChallengeRating": "Challenge rating",
    "Plot": "Plot",
    "Static": "Static",
    "Useable": "Usable",
    "OpenLockDC": "Open lock DC",
    "GenericType": "Generic type",
    "LinkedTo": "Linked to",
    "LinkedToModule": "Linked module",
    "StoreName": "Store name",
    "MarkDown": "Markdown",
    "MarkUp": "Markup",
    "BlackMarket": "Black market",
}

PREFERRED_FIELDS = (
    "TemplateResRef",
    "Tag",
    "LocalizedName",
    "FirstName",
    "LastName",
    "Name",
    "StoreName",
    "Conversation",
    "Comment",
    "FactionID",
    "Appearance_Type",
    "PaletteID",
    "ChallengeRating",
    "GenericType",
    "OpenLockDC",
    "LinkedTo",
    "LinkedToModule",
    "Plot",
    "Static",
    "Useable",
    "MarkDown",
    "MarkUp",
    "BlackMarket",
)


@dataclass(frozen=True)
class ModuleTemplateField:
    key: str
    label: str
    value: str
    value_type: str
    editable_scope: str
    editable: bool = False


@dataclass(frozen=True)
class ModuleTemplateListSummary:
    key: str
    label: str
    count: int


@dataclass(frozen=True)
class ModuleTemplateInventory:
    resref: str
    restype: str
    parse_status: str
    template_kind: str = ""
    fields: tuple[ModuleTemplateField, ...] = ()
    list_summaries: tuple[ModuleTemplateListSummary, ...] = ()
    raw_field_count: int = 0
    warning: str = ""
    editable_scope: str = "gameplay_template_form"

    @property
    def ok(self) -> bool:
        return self.parse_status == "ok"

    @property
    def summary(self) -> str:
        label = self.template_kind or self.restype.upper()
        return f"{label} template: {len(self.fields)} fields, {len(self.list_summaries)} lists"


@dataclass(frozen=True)
class ModuleTemplateFieldEditDraft:
    resref: str
    restype: str
    field_key: str
    old_value: str
    new_value: str
    output_payload: bytes = b""
    validation_status: str = "not_validated"
    issues: tuple[str, ...] = ()
    status: str = "preview_only"

    @property
    def ready(self) -> bool:
        return bool(self.output_payload) and self.validation_status == "valid"

    @property
    def summary(self) -> str:
        return f"{self.resref}.{self.restype} {self.field_key}: {self.old_value} -> {self.new_value}"


@dataclass(frozen=True)
class ModuleTemplatePatchExportResult:
    output_module: str
    manifest_path: str
    source_sha256: str
    output_sha256: str
    patched_resources: tuple[str, ...]
    copied_bytes: int
    draft: ModuleTemplateFieldEditDraft

    @property
    def ok(self) -> bool:
        return self.source_sha256 != self.output_sha256 and bool(self.patched_resources)


def inspect_module_template(
    module_path: str | Path,
    resource: ModuleArchiveResource,
) -> ModuleTemplateInventory:
    """Parse a module-local gameplay template and return editor-facing form facts."""

    if resource.restype not in TEMPLATE_TYPES:
        return ModuleTemplateInventory(
            resource.resref,
            resource.restype,
            "skipped",
            warning="Resource is not a gameplay template.",
        )
    try:
        raw_bytes = read_module_resource_bytes(module_path, resource)
        from src.core.game.game_library_ext import GFFReader

        raw = GFFReader.from_bytes(raw_bytes)
        if not isinstance(raw, dict):
            return ModuleTemplateInventory(resource.resref, resource.restype, "parse_failed", warning="GFF payload did not parse.")
        return _inventory_from_raw(resource, raw)
    except Exception as exc:
        return ModuleTemplateInventory(resource.resref, resource.restype, "parse_failed", warning=str(exc))


def create_template_field_edit_draft(
    module_path: str | Path,
    resource: ModuleArchiveResource,
    *,
    field_key: str,
    value: str,
) -> ModuleTemplateFieldEditDraft:
    """Build a validated, non-destructive gameplay template field edit preview."""

    field_key = str(field_key or "").strip()
    new_text = _clean_text_value(value)
    if resource.restype not in TEMPLATE_TYPES:
        return _template_edit_error(resource, field_key, "", new_text, "not_template", "Resource is not a gameplay template.")
    try:
        raw = read_module_resource_bytes(module_path, resource)
        gff = _read_gff(raw)
        field = gff.root.fields.get(field_key)
        if field is None:
            return _template_edit_error(resource, field_key, "", new_text, "field_missing", f"Field {field_key!r} is not present on {resource.label}.")
        if not _is_editable_gff_type(field.type):
            return _template_edit_error(resource, field_key, _display_typed_value(field.value), new_text, "unsupported_field", f"Field {field_key!r} is not a primitive editable field.")
        issue = _field_value_issue(field_key, field.type, new_text)
        if issue:
            return _template_edit_error(resource, field_key, _display_typed_value(field.value), new_text, "invalid_value", issue)
        old_text = _display_typed_value(field.value)
        try:
            field.value = _coerce_gff_edit_value(field.type, new_text)
        except Exception as exc:
            return _template_edit_error(resource, field_key, old_text, new_text, "coerce_failed", f"Could not convert {field_key!r}: {exc}")
        output = _write_gff(gff)
        reparsed = _read_gff(output)
        check_field = reparsed.root.fields.get(field_key)
        actual_text = _display_typed_value(check_field.value) if check_field is not None else ""
        if check_field is None or not _gff_value_matches(check_field.type, actual_text, new_text):
            return _template_edit_error(resource, field_key, old_text, new_text, "roundtrip_failed", "Template edit did not survive GFF write/read round-trip.")
        return ModuleTemplateFieldEditDraft(
            resref=resource.resref,
            restype=resource.restype,
            field_key=field_key,
            old_value=old_text,
            new_value=actual_text,
            output_payload=output,
            validation_status="valid",
        )
    except Exception as exc:
        return _template_edit_error(resource, field_key, "", new_text, "parse_failed", str(exc))


def write_template_field_patch_export_copy(
    source_module: str | Path,
    output_module: str | Path,
    draft: ModuleTemplateFieldEditDraft,
    *,
    manifest_path: str | Path | None = None,
) -> ModuleTemplatePatchExportResult:
    """Export a rebuilt module archive with one validated gameplay template edit."""

    source = Path(source_module)
    output = Path(output_module)
    if source.resolve() == output.resolve():
        raise ValueError("Export target must be a new file; the source module will not be overwritten.")
    if not source.exists():
        raise FileNotFoundError(f"Source module does not exist: {source}")
    if not draft.ready:
        message = "; ".join(draft.issues) or f"Template edit draft is not exportable: {draft.validation_status}"
        raise ValueError(message)

    from src.core.stock_modules.stock_module_archive import read_module_archive_resources, read_module_resource_bytes

    resources = read_module_archive_resources(source)
    patched_label = f"{draft.resref.lower()}.{draft.restype.lower()}"
    found_target = False
    entries: list[ModuleArchiveEntry] = []
    for archive_resource in resources:
        label = archive_resource.label.lower()
        changed = label == patched_label
        if changed:
            found_target = True
        entries.append(
            ModuleArchiveEntry(
                resref=archive_resource.resref,
                restype=archive_resource.restype,
                data=draft.output_payload if changed else read_module_resource_bytes(source, archive_resource),
                source="patched_gameplay_template_form" if changed else "preserved_source_resource",
                changed=changed,
                serializer="validated_gff_binary" if changed else "preserved_binary",
            )
        )
    if not found_target:
        raise ValueError(f"Target template resource {draft.resref}.{draft.restype} is not in the source archive.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(build_erf_v1_archive(entries, archive_type=_source_archive_type(source)))
    source_bytes = source.read_bytes()
    output_bytes = output.read_bytes()
    resolved_manifest = Path(manifest_path) if manifest_path is not None else _default_template_manifest_path(output)
    manifest = {
        "schema": "ghostrigger.stock_module_template_patch_plan.v1",
        "generated_at": _utc_now(),
        "status": "patched_module_export",
        "archive_bytes_modified": True,
        "source_module": str(source),
        "output_module": str(output),
        "patched_resources": [patched_label],
        "draft": {
            "resref": draft.resref,
            "restype": draft.restype,
            "field_key": draft.field_key,
            "old_value": draft.old_value,
            "new_value": draft.new_value,
            "validation_status": draft.validation_status,
            "issues": list(draft.issues),
            "status": draft.status,
            "summary": draft.summary,
        },
        "note": "Exported module archive was rebuilt from the source archive with only the listed gameplay template payload patched.",
    }
    resolved_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ModuleTemplatePatchExportResult(
        output_module=str(output),
        manifest_path=str(resolved_manifest),
        source_sha256=_sha256(source_bytes),
        output_sha256=_sha256(output_bytes),
        patched_resources=(patched_label,),
        copied_bytes=len(output_bytes),
        draft=draft,
    )


def _inventory_from_raw(resource: ModuleArchiveResource, raw: dict[str, Any]) -> ModuleTemplateInventory:
    editable_scope = f"{resource.restype}_template_form"
    fields: list[ModuleTemplateField] = []
    for key in PREFERRED_FIELDS:
        if key in raw:
            fields.append(_field(key, raw.get(key), editable_scope))
    script_keys = sorted(
        key for key, value in raw.items()
        if key not in PREFERRED_FIELDS and _is_script_field(key, value)
    )
    for key in script_keys:
        fields.append(_field(key, raw.get(key), editable_scope))
    if "TemplateResRef" not in raw:
        fields.insert(0, _field("TemplateResRef", resource.resref, editable_scope))
    if "Tag" not in raw:
        fields.insert(1, _field("Tag", raw.get("Tag", ""), editable_scope))

    list_summaries = tuple(
        ModuleTemplateListSummary(
            key=key,
            label=FIELD_LABELS.get(key, _label_from_key(key)),
            count=len(value),
        )
        for key, value in sorted(raw.items())
        if isinstance(value, list)
    )
    return ModuleTemplateInventory(
        resref=resource.resref,
        restype=resource.restype,
        parse_status="ok",
        template_kind=TEMPLATE_KIND_LABELS.get(resource.restype, resource.restype.upper()),
        fields=tuple(fields[:24]),
        list_summaries=list_summaries,
        raw_field_count=len(raw),
        editable_scope=editable_scope,
    )


def _field(key: str, value: Any, editable_scope: str) -> ModuleTemplateField:
    return ModuleTemplateField(
        key=key,
        label=FIELD_LABELS.get(key, _label_from_key(key)),
        value=_display_value(value),
        value_type=_value_type(value),
        editable_scope=editable_scope,
        editable=_is_editable_value(value),
    )


def _display_value(value: Any) -> str:
    if isinstance(value, dict) and "strings" in value:
        strings = value.get("strings") or {}
        if strings:
            first_key = sorted(strings)[0]
            return str(strings.get(first_key) or "")
        strref = value.get("strref", -1)
        return f"strref:{strref}" if strref not in (-1, 4294967295, None) else "(empty)"
    if isinstance(value, bytes):
        return f"bytes:{len(value)}"
    if isinstance(value, list):
        return f"list:{len(value)}"
    if isinstance(value, dict):
        return f"struct:{len(value)}"
    text = str(value) if value not in (None, "") else "(empty)"
    return text.strip("\x00")


def _value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "locstring" if "strings" in value else "struct"
    if isinstance(value, bytes):
        return "bytes"
    return "string"


def _is_editable_value(value: Any) -> bool:
    return _value_type(value) in {"bool", "int", "float", "locstring", "string"}


def _read_gff(data: bytes) -> Any:
    from src.formats.gff_reader import GffReader

    return GffReader(data).parse()


def _write_gff(gff: Any) -> bytes:
    from src.formats.gff_writer import GffWriter

    return GffWriter(gff).serialize()


def _is_editable_gff_type(field_type: Any) -> bool:
    from src.formats.gff_types import GffFieldType

    return field_type in {
        GffFieldType.BYTE,
        GffFieldType.CHAR,
        GffFieldType.UINT16,
        GffFieldType.INT16,
        GffFieldType.UINT32,
        GffFieldType.INT32,
        GffFieldType.UINT64,
        GffFieldType.INT64,
        GffFieldType.FLOAT,
        GffFieldType.DOUBLE,
        GffFieldType.CEXOSTRING,
        GffFieldType.RESREF,
        GffFieldType.CEXOLOCSTRING,
    }


def _coerce_gff_edit_value(field_type: Any, value: str) -> Any:
    from src.formats.gff_types import GffFieldType, LocString, ResRef

    if field_type == GffFieldType.RESREF:
        return ResRef(value)
    if field_type == GffFieldType.CEXOSTRING:
        return str(value)
    if field_type == GffFieldType.CEXOLOCSTRING:
        loc = LocString(strref=-1)
        loc.english = str(value)
        return loc
    if field_type in {GffFieldType.FLOAT, GffFieldType.DOUBLE}:
        return float(value)
    if field_type in {
        GffFieldType.BYTE,
        GffFieldType.CHAR,
        GffFieldType.UINT16,
        GffFieldType.INT16,
        GffFieldType.UINT32,
        GffFieldType.INT32,
        GffFieldType.UINT64,
        GffFieldType.INT64,
    }:
        return int(value)
    return str(value)


def _display_typed_value(value: Any) -> str:
    from src.formats.gff_types import LocString

    if isinstance(value, LocString):
        if value.strings:
            first_key = sorted(value.strings)[0]
            return str(value.strings.get(first_key) or "")
        return f"strref:{value.strref}" if value.strref not in (-1, 4294967295, None) else "(empty)"
    return "" if value is None else str(value).strip().strip("\x00")


def _gff_value_matches(field_type: Any, actual: str, expected: str) -> bool:
    from src.formats.gff_types import GffFieldType

    if field_type == GffFieldType.RESREF:
        return actual == expected.lower()
    if field_type in {GffFieldType.FLOAT, GffFieldType.DOUBLE}:
        try:
            return abs(float(actual) - float(expected)) < 0.0001
        except ValueError:
            return False
    if field_type in {
        GffFieldType.BYTE,
        GffFieldType.CHAR,
        GffFieldType.UINT16,
        GffFieldType.INT16,
        GffFieldType.UINT32,
        GffFieldType.INT32,
        GffFieldType.UINT64,
        GffFieldType.INT64,
    }:
        try:
            return int(actual) == int(expected)
        except ValueError:
            return False
    return actual == expected


def _field_value_issue(field_key: str, field_type: Any, value: str) -> str:
    from src.formats.gff_types import GffFieldType

    if field_type == GffFieldType.RESREF:
        required = field_key == "TemplateResRef"
        return _resref_issue(value, required=required)
    return ""


def _resref_issue(value: str, *, required: bool) -> str:
    if not value:
        return "ResRef cannot be empty." if required else ""
    if len(value) > 16:
        return "ResRef exceeds the 16-character KotOR limit."
    try:
        value.encode("ascii")
    except UnicodeEncodeError:
        return "ResRef must be ASCII."
    if not all(character.isalnum() or character == "_" for character in value):
        return "ResRef may only contain letters, numbers, and underscores."
    return ""


def _clean_text_value(value: object) -> str:
    return str(value or "").strip().strip("\x00")


def _template_edit_error(
    resource: ModuleArchiveResource,
    field_key: str,
    old_value: str,
    new_value: str,
    status: str,
    issue: str,
) -> ModuleTemplateFieldEditDraft:
    return ModuleTemplateFieldEditDraft(
        resref=resource.resref,
        restype=resource.restype,
        field_key=field_key,
        old_value=old_value,
        new_value=new_value,
        validation_status=status,
        issues=(issue,),
    )


def _default_template_manifest_path(output: Path) -> Path:
    return output.with_name(output.name + ".ghostrigger_template_patch_plan.json")


def _source_archive_type(source: Path) -> str:
    signature = source.read_bytes()[:3].decode("ascii", errors="replace").upper()
    if signature in {"MOD", "RIM", "ERF", "SAV"}:
        return signature
    return "MOD"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_script_field(key: str, value: Any) -> bool:
    if isinstance(value, (list, dict, bytes)):
        return False
    return key.startswith("On") or key.startswith("Script")


def _label_from_key(key: str) -> str:
    out: list[str] = []
    for index, char in enumerate(key):
        if index and char.isupper() and (not key[index - 1].isupper()):
            out.append(" ")
        out.append(char)
    return "".join(out).replace("_", " ").strip().title()


__all__ = [
    "ModuleTemplateFieldEditDraft",
    "ModuleTemplateField",
    "ModuleTemplateInventory",
    "ModuleTemplateListSummary",
    "ModuleTemplatePatchExportResult",
    "TEMPLATE_TYPES",
    "create_template_field_edit_draft",
    "inspect_module_template",
    "write_template_field_patch_export_copy",
]
