"""PTH, DLG, NSS, and NCS inventories for stock KotOR modules."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
from src.core.stock_modules.stock_module_archive import ModuleArchiveResource, read_module_resource_bytes


LOGIC_TYPES = {"pth", "dlg", "nss", "ncs"}

RESOURCE_KIND_LABELS = {
    "pth": "Path data",
    "dlg": "Dialogue tree",
    "nss": "NWScript source",
    "ncs": "Compiled NWScript",
}


@dataclass(frozen=True)
class ModuleLogicField:
    key: str
    label: str
    value: str
    value_type: str
    editable_scope: str = "logic_resource"
    editable: bool = False


@dataclass(frozen=True)
class ModuleLogicListSummary:
    key: str
    label: str
    count: int


@dataclass(frozen=True)
class ModuleLogicReference:
    source: str
    resref: str
    expected_types: tuple[str, ...]
    status: str

    @property
    def label(self) -> str:
        types = "/".join(self.expected_types) if self.expected_types else "resource"
        return f"{self.source}: {self.resref} ({types})"


@dataclass(frozen=True)
class ModuleLogicInventory:
    resref: str
    restype: str
    parse_status: str
    resource_kind: str = ""
    fields: tuple[ModuleLogicField, ...] = ()
    list_summaries: tuple[ModuleLogicListSummary, ...] = ()
    references: tuple[ModuleLogicReference, ...] = ()
    raw_field_count: int = 0
    line_count: int = 0
    byte_size: int = 0
    text_preview: str = ""
    warning: str = ""
    editable_scope: str = "list_only_logic_resource"

    @property
    def ok(self) -> bool:
        return self.parse_status in {"ok", "text", "compiled_binary", "binary_list_only"}

    @property
    def summary(self) -> str:
        kind = self.resource_kind or self.restype.upper()
        if self.restype == "nss":
            return f"{kind}: {self.line_count} source line(s)"
        if self.restype == "ncs":
            return f"{kind}: {self.byte_size} compiled byte(s)"
        if self.raw_field_count:
            return f"{kind}: {self.raw_field_count} GFF field(s), {len(self.list_summaries)} list(s)"
        return f"{kind}: {self.byte_size} byte(s)"

    @property
    def missing_reference_count(self) -> int:
        return sum(1 for reference in self.references if reference.status == "missing")


@dataclass(frozen=True)
class ModuleLogicFieldEditDraft:
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
class ModuleLogicPatchExportResult:
    output_module: str
    manifest_path: str
    source_sha256: str
    output_sha256: str
    patched_resources: tuple[str, ...]
    copied_bytes: int
    draft: ModuleLogicFieldEditDraft

    @property
    def ok(self) -> bool:
        return self.source_sha256 != self.output_sha256 and bool(self.patched_resources)


def inspect_module_logic(
    module_path: str | Path,
    resource: ModuleArchiveResource,
    resources: list[ModuleArchiveResource] | None = None,
) -> ModuleLogicInventory:
    """Parse or classify a module-local logic/path resource for safe inspection."""

    if resource.restype not in LOGIC_TYPES:
        return ModuleLogicInventory(
            resource.resref,
            resource.restype,
            "skipped",
            warning="Resource is not a PTH/DLG/NSS/NCS logic resource.",
        )
    try:
        data = read_module_resource_bytes(module_path, resource)
        available = _available_resources(resources)
        if resource.restype == "nss":
            return _inspect_nss(resource, data, available)
        if resource.restype == "ncs":
            return _inspect_ncs(resource, data, available)
        return _inspect_gff_or_binary(resource, data, available)
    except Exception as exc:
        return ModuleLogicInventory(resource.resref, resource.restype, "parse_failed", warning=str(exc))


def create_logic_field_edit_draft(
    module_path: str | Path,
    resource: ModuleArchiveResource,
    *,
    field_key: str,
    value: str,
) -> ModuleLogicFieldEditDraft:
    """Build a validated, non-destructive DLG top-level field edit preview."""

    field_key = str(field_key or "").strip()
    new_text = _clean_text_value(value)
    if resource.restype != "dlg":
        return _logic_edit_error(resource, field_key, "", new_text, "not_dialogue", "Only DLG top-level fields are editable in this gate.")
    try:
        raw = read_module_resource_bytes(module_path, resource)
        gff = _read_gff(raw)
        field = gff.root.fields.get(field_key)
        if field is None:
            return _logic_edit_error(resource, field_key, "", new_text, "field_missing", f"Field {field_key!r} is not present on {resource.label}.")
        if not _is_safe_dlg_edit_field(field_key, field.type):
            return _logic_edit_error(resource, field_key, _display_typed_value(field.value), new_text, "unsupported_field", f"Field {field_key!r} is not a safe top-level DLG primitive field.")
        issue = _field_value_issue(field_key, field.type, new_text)
        if issue:
            return _logic_edit_error(resource, field_key, _display_typed_value(field.value), new_text, "invalid_value", issue)
        old_text = _display_typed_value(field.value)
        try:
            field.value = _coerce_gff_edit_value(field.type, new_text)
        except Exception as exc:
            return _logic_edit_error(resource, field_key, old_text, new_text, "coerce_failed", f"Could not convert {field_key!r}: {exc}")
        output = _write_gff(gff)
        reparsed = _read_gff(output)
        check_field = reparsed.root.fields.get(field_key)
        actual_text = _display_typed_value(check_field.value) if check_field is not None else ""
        if check_field is None or not _gff_value_matches(check_field.type, actual_text, new_text):
            return _logic_edit_error(resource, field_key, old_text, new_text, "roundtrip_failed", "Dialogue edit did not survive GFF write/read round-trip.")
        return ModuleLogicFieldEditDraft(
            resref=resource.resref,
            restype=resource.restype,
            field_key=field_key,
            old_value=old_text,
            new_value=actual_text,
            output_payload=output,
            validation_status="valid",
        )
    except Exception as exc:
        return _logic_edit_error(resource, field_key, "", new_text, "parse_failed", str(exc))


def write_logic_field_patch_export_copy(
    source_module: str | Path,
    output_module: str | Path,
    draft: ModuleLogicFieldEditDraft,
    *,
    manifest_path: str | Path | None = None,
) -> ModuleLogicPatchExportResult:
    """Export a rebuilt module archive with one validated DLG field edit."""

    source = Path(source_module)
    output = Path(output_module)
    if source.resolve() == output.resolve():
        raise ValueError("Export target must be a new file; the source module will not be overwritten.")
    if not source.exists():
        raise FileNotFoundError(f"Source module does not exist: {source}")
    if not draft.ready:
        message = "; ".join(draft.issues) or f"Logic edit draft is not exportable: {draft.validation_status}"
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
                source="patched_logic_field" if changed else "preserved_source_resource",
                changed=changed,
                serializer="validated_gff_binary" if changed else "preserved_binary",
            )
        )
    if not found_target:
        raise ValueError(f"Target logic resource {draft.resref}.{draft.restype} is not in the source archive.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(build_erf_v1_archive(entries, archive_type=_source_archive_type(source)))
    source_bytes = source.read_bytes()
    output_bytes = output.read_bytes()
    resolved_manifest = Path(manifest_path) if manifest_path is not None else _default_logic_manifest_path(output)
    manifest = {
        "schema": "ghostrigger.stock_module_logic_patch_plan.v1",
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
        "note": "Exported module archive was rebuilt from the source archive with only the listed DLG top-level field patched.",
    }
    resolved_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ModuleLogicPatchExportResult(
        output_module=str(output),
        manifest_path=str(resolved_manifest),
        source_sha256=_sha256(source_bytes),
        output_sha256=_sha256(output_bytes),
        patched_resources=(patched_label,),
        copied_bytes=len(output_bytes),
        draft=draft,
    )


def _inspect_nss(
    resource: ModuleArchiveResource,
    data: bytes,
    available: set[tuple[str, str]],
) -> ModuleLogicInventory:
    text = data.decode("latin-1", errors="replace")
    lines = text.splitlines()
    preview = "\n".join(lines[:16]).strip()
    references = _nss_references(text, available)
    warning = "Script editing/compile support is a later gate; source bytes are preserved."
    if any(reference.status == "missing" for reference in references):
        warning = f"{warning} {sum(1 for reference in references if reference.status == 'missing')} referenced resource(s) are missing."
    return ModuleLogicInventory(
        resref=resource.resref,
        restype=resource.restype,
        parse_status="text",
        resource_kind=RESOURCE_KIND_LABELS[resource.restype],
        fields=(
            ModuleLogicField("source_name", "Source script", resource.resref, "resref"),
            ModuleLogicField("line_count", "Source lines", str(len(lines)), "int"),
        ),
        references=references,
        line_count=len(lines),
        byte_size=len(data),
        text_preview=preview,
        editable_scope="script_source_list_only",
        warning=warning,
    )


def _inspect_ncs(
    resource: ModuleArchiveResource,
    data: bytes,
    available: set[tuple[str, str]],
) -> ModuleLogicInventory:
    signature = data[:4].decode("ascii", errors="replace") if data else ""
    references = ()
    source_status = "resolved" if (resource.resref.lower(), "nss") in available else "missing"
    references = (
        ModuleLogicReference("matching source", resource.resref, ("nss",), source_status),
    )
    fields = (
        ModuleLogicField("compiled_name", "Compiled script", resource.resref, "resref"),
        ModuleLogicField("signature", "Signature", signature or "(empty)", "string"),
    )
    warning = "Compiled NCS bytecode is list-only until decompile/compile validation exists."
    if source_status == "missing":
        warning = f"{warning} Matching NSS source is not present in this module archive."
    return ModuleLogicInventory(
        resref=resource.resref,
        restype=resource.restype,
        parse_status="compiled_binary",
        resource_kind=RESOURCE_KIND_LABELS[resource.restype],
        fields=fields,
        references=references,
        byte_size=len(data),
        editable_scope="compiled_script_list_only",
        warning=warning,
    )


def _inspect_gff_or_binary(
    resource: ModuleArchiveResource,
    data: bytes,
    available: set[tuple[str, str]],
) -> ModuleLogicInventory:
    from src.core.game.game_library_ext import GFFReader

    raw = GFFReader.from_bytes(data)
    if isinstance(raw, dict):
        return _inventory_from_gff(resource, data, raw, available)
    text = data.decode("latin-1", errors="replace")
    lines = text.splitlines()
    is_text = _looks_textual(data)
    preview = "\n".join(lines[:16]).strip() if is_text else ""
    status = "text" if is_text else "binary_list_only"
    warning = (
        "No safe PTH serializer is available yet; path data is preserved byte-for-byte."
        if resource.restype == "pth"
        else "Resource did not parse as GFF; bytes are preserved."
    )
    return ModuleLogicInventory(
        resref=resource.resref,
        restype=resource.restype,
        parse_status=status,
        resource_kind=RESOURCE_KIND_LABELS.get(resource.restype, resource.restype.upper()),
        fields=(
            ModuleLogicField("resource", "Resource", resource.label, "resource"),
            ModuleLogicField("format", "Detected format", "text" if is_text else "binary", "string"),
        ),
        line_count=len(lines) if is_text else 0,
        byte_size=len(data),
        text_preview=preview,
        editable_scope=f"{resource.restype}_list_only",
        warning=warning,
    )


def _inventory_from_gff(
    resource: ModuleArchiveResource,
    data: bytes,
    raw: dict[str, Any],
    available: set[tuple[str, str]],
) -> ModuleLogicInventory:
    fields: list[ModuleLogicField] = []
    for key in _preferred_keys(resource.restype):
        if key in raw:
            fields.append(_field(resource.restype, key, raw.get(key)))
    if not fields:
        for key, value in sorted(raw.items()):
            if key.startswith("_") or isinstance(value, (list, dict, bytes)):
                continue
            fields.append(_field(resource.restype, key, value))
            if len(fields) >= 12:
                break
    list_summaries = tuple(
        ModuleLogicListSummary(key=key, label=_label(key), count=len(value))
        for key, value in sorted(raw.items())
        if isinstance(value, list)
    )
    references = _gff_references(resource.restype, raw, available)
    warning = (
        "Top-level primitive DLG fields can be preview-edited; nested dialogue lists are preserved."
        if resource.restype == "dlg"
        else "GFF data is inspectable; editing waits for a byte-preserving serializer gate."
    )
    if any(reference.status == "missing" for reference in references):
        warning = f"{warning} {sum(1 for reference in references if reference.status == 'missing')} referenced resource(s) are missing."
    return ModuleLogicInventory(
        resref=resource.resref,
        restype=resource.restype,
        parse_status="ok",
        resource_kind=RESOURCE_KIND_LABELS.get(resource.restype, resource.restype.upper()),
        fields=tuple(fields[:18]),
        list_summaries=list_summaries,
        references=references,
        raw_field_count=len(raw),
        byte_size=len(data),
        editable_scope="dlg_top_level_fields" if resource.restype == "dlg" else f"{resource.restype}_gff_list_only",
        warning=warning,
    )


def _available_resources(resources: list[ModuleArchiveResource] | None) -> set[tuple[str, str]]:
    return {
        (str(resource.resref or "").lower(), str(resource.restype or "").lower())
        for resource in resources or ()
    }


def _nss_references(text: str, available: set[tuple[str, str]]) -> tuple[ModuleLogicReference, ...]:
    patterns = (
        ("dialogue", re.compile(r"\b(?:ActionStartConversation|StartConversation)\s*\([^;]*?\"([A-Za-z0-9_]{1,16})\"", re.IGNORECASE), ("dlg",)),
        ("script", re.compile(r"\bExecuteScript\s*\(\s*\"([A-Za-z0-9_]{1,16})\"", re.IGNORECASE), ("ncs", "nss")),
        ("module", re.compile(r"\bStartNewModule\s*\(\s*\"([A-Za-z0-9_]{1,16})\"", re.IGNORECASE), ("mod", "rim")),
    )
    references: list[ModuleLogicReference] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for source, pattern, expected in patterns:
        for match in pattern.finditer(text or ""):
            resref = match.group(1).lower()
            key = (source, resref, expected)
            if key in seen:
                continue
            seen.add(key)
            references.append(ModuleLogicReference(source, resref, expected, _reference_status(resref, expected, available)))
    return tuple(references)


def _gff_references(
    restype: str,
    raw: dict[str, Any],
    available: set[tuple[str, str]],
) -> tuple[ModuleLogicReference, ...]:
    if restype != "dlg":
        return ()
    references: list[ModuleLogicReference] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for source, resref, expected in _walk_dlg_references(raw):
        key = (source, resref, expected)
        if not resref or key in seen:
            continue
        seen.add(key)
        references.append(ModuleLogicReference(source, resref, expected, _reference_status(resref, expected, available)))
    return tuple(references)


def _walk_dlg_references(value: Any, prefix: str = "") -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    rows: list[tuple[str, str, tuple[str, ...]]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            expected = _dlg_expected_types(str(key))
            if expected and _is_resref_like(child):
                rows.append((child_prefix, _clean_resref(child), expected))
            rows.extend(_walk_dlg_references(child, child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(_walk_dlg_references(child, f"{prefix}[{index}]"))
    return tuple(rows)


def _dlg_expected_types(key: str) -> tuple[str, ...]:
    lowered = key.lower()
    if lowered in {"endconversation", "conversation"}:
        return ("dlg",)
    if "script" in lowered or lowered in {"active", "action", "conditional"}:
        return ("ncs", "nss")
    if "sound" in lowered or "vo" in lowered:
        return ("wav", "mp3", "ssf")
    return ()


def _is_resref_like(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip().lower()
    return bool(text) and len(text) <= 16 and all(character.isalnum() or character == "_" for character in text)


def _clean_resref(value: Any) -> str:
    return str(value or "").strip().strip("\x00").lower()[:16]


def _reference_status(
    resref: str,
    expected_types: tuple[str, ...],
    available: set[tuple[str, str]],
) -> str:
    if not available:
        return "unknown"
    if any((resref.lower(), restype.lower()) in available for restype in expected_types):
        return "resolved"
    return "missing"


def _preferred_keys(restype: str) -> tuple[str, ...]:
    if restype == "dlg":
        return (
            "DelayEntry",
            "DelayReply",
            "EndConverAbort",
            "EndConversation",
            "ConversationType",
            "NumWords",
            "PreventZoomIn",
            "Skippable",
            "UnequipHItem",
        )
    if restype == "pth":
        return ("Path_Conections", "Path_Points", "PathConnections", "PathPoints")
    return ()


def _field(restype: str, key: str, value: Any) -> ModuleLogicField:
    is_editable_dlg_field = restype == "dlg" and key in _preferred_keys("dlg") and _is_editable_value(value)
    return ModuleLogicField(
        key=key,
        label=_label(key),
        value=_display_value(value),
        value_type=_value_type(value),
        editable_scope="dlg_top_level_fields" if restype == "dlg" else f"{restype}_list_only",
        editable=is_editable_dlg_field,
    )


def _display_value(value: Any) -> str:
    if isinstance(value, dict) and "strings" in value:
        strings = value.get("strings") or {}
        if strings:
            return str(strings.get(sorted(strings)[0]) or "")
        return f"strref:{value.get('strref', -1)}"
    if isinstance(value, bytes):
        return f"bytes:{len(value)}"
    if isinstance(value, list):
        return f"list:{len(value)}"
    if isinstance(value, dict):
        return f"struct:{len(value)}"
    return str(value) if value not in (None, "") else "(empty)"


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


def _is_safe_dlg_edit_field(field_key: str, field_type: Any) -> bool:
    return field_key in _preferred_keys("dlg") and _is_editable_gff_type(field_type)


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
        return _resref_issue(value, required=False)
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


def _logic_edit_error(
    resource: ModuleArchiveResource,
    field_key: str,
    old_value: str,
    new_value: str,
    status: str,
    issue: str,
) -> ModuleLogicFieldEditDraft:
    return ModuleLogicFieldEditDraft(
        resref=resource.resref,
        restype=resource.restype,
        field_key=field_key,
        old_value=old_value,
        new_value=new_value,
        validation_status=status,
        issues=(issue,),
    )


def _default_logic_manifest_path(output: Path) -> Path:
    return output.with_name(output.name + ".ghostrigger_logic_patch_plan.json")


def _source_archive_type(source: Path) -> str:
    signature = source.read_bytes()[:3].decode("ascii", errors="replace").upper()
    if signature in {"MOD", "RIM", "ERF", "SAV"}:
        return signature
    return "MOD"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _label(key: str) -> str:
    out: list[str] = []
    for index, char in enumerate(key):
        if index and char.isupper() and not key[index - 1].isupper():
            out.append(" ")
        out.append(char)
    return "".join(out).replace("_", " ").strip().title()


def _looks_textual(data: bytes) -> bool:
    if not data:
        return True
    sample = data[:512]
    printable = sum(1 for byte in sample if byte in (9, 10, 13) or 32 <= byte <= 126)
    return printable / max(1, len(sample)) > 0.85


__all__ = [
    "LOGIC_TYPES",
    "ModuleLogicField",
    "ModuleLogicFieldEditDraft",
    "ModuleLogicInventory",
    "ModuleLogicListSummary",
    "ModuleLogicPatchExportResult",
    "inspect_module_logic",
    "create_logic_field_edit_draft",
    "write_logic_field_patch_export_copy",
]
