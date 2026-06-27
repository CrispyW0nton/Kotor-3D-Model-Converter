"""Read-only GIT object inventories for stock KotOR module archives."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
from src.core.stock_modules.stock_module_archive import ModuleArchiveResource, read_module_resource_bytes


SUPPORTED_GIT_EDIT_FIELDS = {
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
}


@dataclass(frozen=True)
class ModuleGitObjectCount:
    object_type: str
    count: int
    template_type: str = ""


@dataclass(frozen=True)
class ModuleGitObjectEditableField:
    key: str
    label: str
    value: str
    value_type: str


@dataclass(frozen=True)
class ModuleGitObjectRow:
    object_type: str
    index: int
    template_resref: str
    tag: str = ""
    template_type: str = ""
    list_label: str = ""
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    bearing: float = 0.0
    field_count: int = 0
    editable_fields: tuple[ModuleGitObjectEditableField, ...] = ()


@dataclass(frozen=True)
class ModuleGitInventory:
    resref: str
    parse_status: str
    counts: tuple[ModuleGitObjectCount, ...] = ()
    objects: tuple[ModuleGitObjectRow, ...] = ()
    warning: str = ""
    editable_scope: str = "git_object_forms"

    @property
    def ok(self) -> bool:
        return self.parse_status == "ok"

    @property
    def total_objects(self) -> int:
        return sum(item.count for item in self.counts)

    @property
    def summary(self) -> str:
        if not self.counts:
            return "0 placed objects"
        parts = [f"{item.object_type}:{item.count}" for item in self.counts if item.count]
        return f"{self.total_objects} placed object forms ({', '.join(parts)})"


@dataclass(frozen=True)
class ModuleGitObjectEditDraft:
    git_resref: str
    object_type: str
    index: int
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
        return f"{self.git_resref}.git {self.object_type}.{self.index}.{self.field_key}: {self.old_value} -> {self.new_value}"


@dataclass(frozen=True)
class ModuleGitObjectPatchExportResult:
    output_module: str
    manifest_path: str
    source_sha256: str
    output_sha256: str
    patched_resources: tuple[str, ...]
    copied_bytes: int
    draft: ModuleGitObjectEditDraft

    @property
    def ok(self) -> bool:
        return self.source_sha256 != self.output_sha256 and bool(self.patched_resources)


def inspect_module_git(
    module_path: str | Path,
    resource: ModuleArchiveResource,
) -> ModuleGitInventory:
    """Parse a module-local GIT and return editor-facing placed-object facts."""

    if resource.restype != "git":
        return ModuleGitInventory(resource.resref, "skipped", warning="Resource is not a GIT game instance table.")
    try:
        raw = read_module_resource_bytes(module_path, resource)
        from src.core.modules.module_format import GITData
        from src.core.modules.module_object_inspector import OBJECT_SPECS, build_module_object_inspector

        git = GITData.from_bytes(raw)

        class _Module:
            pass

        module = _Module()
        module.git = git
        module.templates = {}
        result = build_module_object_inspector(module)
    except Exception as exc:
        return ModuleGitInventory(resource.resref, "parse_failed", warning=str(exc))

    counts = tuple(
        ModuleGitObjectCount(
            object_type=object_type,
            count=int(count),
            template_type=OBJECT_SPECS.get(object_type).template_type if object_type in OBJECT_SPECS else "",
        )
        for object_type, count in sorted(result.counts.items())
        if int(count) > 0
    )
    objects: list[ModuleGitObjectRow] = []
    for object_type, forms in sorted(result.forms.items()):
        for form in forms:
            objects.append(
                ModuleGitObjectRow(
                    object_type=object_type,
                    index=int(form.index),
                    template_resref=str(form.template_resref or ""),
                    tag=str(form.tag or ""),
                    template_type=str(form.template_type or ""),
                    list_label=str(form.list_label or ""),
                    position=tuple(float(value) for value in form.position),
                    bearing=float(form.bearing),
                    field_count=len(form.fields),
                    editable_fields=tuple(
                        ModuleGitObjectEditableField(
                            key=str(field.key),
                            label=str(field.label),
                            value=_display_gff_value(field.value),
                            value_type=str(field.value_type),
                        )
                        for field in form.fields
                        if field.editable and field.key in SUPPORTED_GIT_EDIT_FIELDS
                    ),
                )
            )
    return ModuleGitInventory(
        resref=resource.resref,
        parse_status="ok" if result.ok else result.code or "empty",
        counts=counts,
        objects=tuple(objects),
        warning="; ".join(result.warnings),
    )


def create_git_object_edit_draft(
    module_path: str | Path,
    resource: ModuleArchiveResource,
    *,
    object_type: str,
    index: int,
    field_key: str,
    value: str,
) -> ModuleGitObjectEditDraft:
    """Build a validated, non-destructive GIT object form edit preview."""

    object_type = str(object_type or "").strip().lower()
    field_key = str(field_key or "").strip()
    new_text = _clean_text_value(value)
    if resource.restype != "git":
        return _git_edit_error(resource.resref, object_type, index, field_key, "", new_text, "not_git", "Resource is not a GIT.")
    if field_key not in SUPPORTED_GIT_EDIT_FIELDS:
        return _git_edit_error(
            resource.resref,
            object_type,
            index,
            field_key,
            "",
            new_text,
            "unsupported_field",
            f"Field {field_key!r} is not enabled for safe GIT object edits.",
        )
    if field_key == "TemplateResRef":
        issue = _resref_issue(new_text)
        if issue:
            return _git_edit_error(resource.resref, object_type, index, field_key, "", new_text, "invalid_resref", issue)
    try:
        raw = read_module_resource_bytes(module_path, resource)
        gff = _read_gff(raw)
        row = _git_object_struct(gff, object_type, int(index))
        if row is None:
            return _git_edit_error(resource.resref, object_type, index, field_key, "", new_text, "form_missing", f"No {object_type} object form exists at index {index}.")
        field = row.fields.get(field_key)
        if field is None:
            return _git_edit_error(resource.resref, object_type, index, field_key, "", new_text, "field_missing", f"Field {field_key!r} is not present on {object_type}.{index}.")
        old_text = _display_gff_value(field.value)
        try:
            field.value = _coerce_gff_edit_value(field.type, new_text)
        except Exception as exc:
            return _git_edit_error(resource.resref, object_type, index, field_key, old_text, new_text, "coerce_failed", f"Could not convert {field_key!r}: {exc}")
        output = _write_gff(gff)
        reparsed = _read_gff(output)
        check_row = _git_object_struct(reparsed, object_type, int(index))
        check_field = check_row.fields.get(field_key) if check_row is not None else None
        actual_text = _display_gff_value(check_field.value) if check_field is not None else ""
        if check_field is None or not _gff_value_matches(check_field.type, actual_text, new_text):
            return _git_edit_error(resource.resref, object_type, index, field_key, old_text, new_text, "roundtrip_failed", "GIT edit did not survive GFF write/read round-trip.")
        return ModuleGitObjectEditDraft(
            git_resref=resource.resref,
            object_type=object_type,
            index=int(index),
            field_key=field_key,
            old_value=old_text,
            new_value=_display_gff_value(check_field.value),
            output_payload=output,
            validation_status="valid",
        )
    except Exception as exc:
        return _git_edit_error(resource.resref, object_type, index, field_key, "", new_text, "parse_failed", str(exc))


def write_git_object_patch_export_copy(
    source_module: str | Path,
    output_module: str | Path,
    draft: ModuleGitObjectEditDraft,
    *,
    manifest_path: str | Path | None = None,
) -> ModuleGitObjectPatchExportResult:
    """Export a rebuilt module archive with one validated GIT object edit."""

    source = Path(source_module)
    output = Path(output_module)
    if source.resolve() == output.resolve():
        raise ValueError("Export target must be a new file; the source module will not be overwritten.")
    if not source.exists():
        raise FileNotFoundError(f"Source module does not exist: {source}")
    if not draft.ready:
        message = "; ".join(draft.issues) or f"GIT object edit draft is not exportable: {draft.validation_status}"
        raise ValueError(message)

    from src.core.stock_modules.stock_module_archive import read_module_archive_resources, read_module_resource_bytes

    resources = read_module_archive_resources(source)
    patched_label = f"{draft.git_resref.lower()}.git"
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
                source="patched_git_object_form" if changed else "preserved_source_resource",
                changed=changed,
                serializer="validated_gff_binary" if changed else "preserved_binary",
            )
        )
    if not found_target:
        raise ValueError(f"Target GIT resource {draft.git_resref}.git is not in the source archive.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(build_erf_v1_archive(entries, archive_type=_source_archive_type(source)))
    source_bytes = source.read_bytes()
    output_bytes = output.read_bytes()
    resolved_manifest = Path(manifest_path) if manifest_path is not None else _default_git_manifest_path(output)
    manifest = {
        "schema": "ghostrigger.stock_module_git_object_patch_plan.v1",
        "generated_at": _utc_now(),
        "status": "patched_module_export",
        "archive_bytes_modified": True,
        "source_module": str(source),
        "output_module": str(output),
        "patched_resources": [patched_label],
        "draft": {
            "git_resref": draft.git_resref,
            "object_type": draft.object_type,
            "index": draft.index,
            "field_key": draft.field_key,
            "old_value": draft.old_value,
            "new_value": draft.new_value,
            "validation_status": draft.validation_status,
            "issues": list(draft.issues),
            "status": draft.status,
            "summary": draft.summary,
        },
        "note": "Exported module archive was rebuilt from the source archive with only the listed GIT payload patched.",
    }
    resolved_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ModuleGitObjectPatchExportResult(
        output_module=str(output),
        manifest_path=str(resolved_manifest),
        source_sha256=_sha256(source_bytes),
        output_sha256=_sha256(output_bytes),
        patched_resources=(patched_label,),
        copied_bytes=len(output_bytes),
        draft=draft,
    )


def _read_gff(data: bytes) -> Any:
    from src.formats.gff_reader import GffReader

    return GffReader(data).parse()


def _write_gff(gff: Any) -> bytes:
    from src.formats.gff_writer import GffWriter

    return GffWriter(gff).serialize()


def _git_object_struct(gff: Any, object_type: str, index: int) -> Any | None:
    from src.core.modules.module_object_inspector import OBJECT_SPECS

    spec = OBJECT_SPECS.get(object_type)
    if spec is None:
        return None
    for label in spec.labels:
        field = gff.root.fields.get(label)
        rows = getattr(field, "value", None) if field is not None else None
        if isinstance(rows, list):
            return rows[index] if 0 <= index < len(rows) else None
    return None


def _coerce_gff_edit_value(field_type: Any, value: str) -> Any:
    from src.formats.gff_types import GffFieldType, ResRef

    if field_type == GffFieldType.RESREF:
        return ResRef(value)
    if field_type == GffFieldType.CEXOSTRING:
        return str(value)
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


def _display_gff_value(value: Any) -> str:
    return "" if value is None else str(value).strip().strip("\x00")


def _clean_text_value(value: object) -> str:
    return str(value or "").strip().strip("\x00")


def _resref_issue(value: str) -> str:
    if not value:
        return "TemplateResRef cannot be empty."
    if len(value) > 16:
        return "TemplateResRef exceeds the 16-character KotOR resref limit."
    try:
        value.encode("ascii")
    except UnicodeEncodeError:
        return "TemplateResRef must be ASCII."
    if not all(character.isalnum() or character == "_" for character in value):
        return "TemplateResRef may only contain letters, numbers, and underscores."
    return ""


def _git_edit_error(
    git_resref: str,
    object_type: str,
    index: int,
    field_key: str,
    old_value: str,
    new_value: str,
    status: str,
    issue: str,
) -> ModuleGitObjectEditDraft:
    return ModuleGitObjectEditDraft(
        git_resref=git_resref,
        object_type=object_type,
        index=int(index),
        field_key=field_key,
        old_value=old_value,
        new_value=new_value,
        validation_status=status,
        issues=(issue,),
    )


def _default_git_manifest_path(output: Path) -> Path:
    return output.with_name(output.name + ".ghostrigger_git_patch_plan.json")


def _source_archive_type(source: Path) -> str:
    signature = source.read_bytes()[:3].decode("ascii", errors="replace").upper()
    if signature in {"MOD", "RIM", "ERF", "SAV"}:
        return signature
    return "MOD"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "ModuleGitObjectEditDraft",
    "ModuleGitInventory",
    "ModuleGitObjectCount",
    "ModuleGitObjectEditableField",
    "ModuleGitObjectPatchExportResult",
    "ModuleGitObjectRow",
    "SUPPORTED_GIT_EDIT_FIELDS",
    "create_git_object_edit_draft",
    "inspect_module_git",
    "write_git_object_patch_export_copy",
]
