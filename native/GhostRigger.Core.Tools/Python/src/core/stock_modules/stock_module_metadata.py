"""ARE/IFO metadata inventories and safe field edits for stock KotOR modules."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
from src.core.stock_modules.stock_module_archive import ModuleArchiveResource, read_module_resource_bytes


METADATA_TYPES = {"are", "ifo"}

FIELD_LABELS = {
    "Name": "Area name",
    "Tag": "Area tag",
    "Comments": "Comments",
    "SunFog": "Sun fog enabled",
    "SunFogOn": "Sun fog enabled",
    "FogNearDist": "Fog near",
    "FogFarDist": "Fog far",
    "SunFogNear": "Sun fog near",
    "SunFogFar": "Sun fog far",
    "SunAmbientColor": "Sun ambient raw",
    "SunDiffuseColor": "Sun diffuse raw",
    "FogColor": "Fog color raw",
    "SunFogColor": "Sun fog color raw",
    "DynAmbientColor": "Dynamic ambient raw",
    "MoonAmbientColor": "Moon ambient raw",
    "MoonDiffuseColor": "Moon diffuse raw",
    "MoonFogColor": "Moon fog color raw",
    "Mod_Tag": "Module tag",
    "Mod_Name": "Module name",
    "Mod_Entry_Area": "Entry area",
    "Mod_Entry_X": "Entry X",
    "Mod_Entry_Y": "Entry Y",
    "Mod_Entry_Z": "Entry Z",
    "Mod_Entry_Dir_X": "Entry dir X",
    "Mod_Entry_Dir_Y": "Entry dir Y",
    "Mod_DawnHour": "Dawn hour",
    "Mod_DuskHour": "Dusk hour",
    "Mod_MinPerHour": "Minutes per hour",
    "Mod_StartHour": "Start hour",
    "Mod_StartDay": "Start day",
    "Mod_StartMonth": "Start month",
    "Mod_StartYear": "Start year",
    "Mod_StartMovie": "Start movie",
}

ARE_EDIT_FIELDS = (
    "Name",
    "Tag",
    "Comments",
    "SunFog",
    "SunFogOn",
    "FogNearDist",
    "FogFarDist",
    "SunFogNear",
    "SunFogFar",
    "SunAmbientColor",
    "SunDiffuseColor",
    "FogColor",
    "SunFogColor",
    "DynAmbientColor",
    "MoonAmbientColor",
    "MoonDiffuseColor",
    "MoonFogColor",
    "ChanceRain",
    "ChanceSnow",
    "ChanceLightning",
    "WindPower",
    "LoadScreenID",
)

IFO_EDIT_FIELDS = (
    "Mod_Tag",
    "Mod_Name",
    "Mod_Entry_Area",
    "Mod_Entry_X",
    "Mod_Entry_Y",
    "Mod_Entry_Z",
    "Mod_Entry_Dir_X",
    "Mod_Entry_Dir_Y",
    "Mod_DawnHour",
    "Mod_DuskHour",
    "Mod_MinPerHour",
    "Mod_StartHour",
    "Mod_StartDay",
    "Mod_StartMonth",
    "Mod_StartYear",
    "Mod_StartMovie",
)

REQUIRED_RESREF_FIELDS = {"Mod_Entry_Area"}


@dataclass(frozen=True)
class ModuleMetadataField:
    key: str
    label: str
    value: str
    editable_scope: str
    value_type: str = "string"
    editable: bool = False


@dataclass(frozen=True)
class ModuleMetadataInventory:
    resref: str
    restype: str
    parse_status: str
    fields: tuple[ModuleMetadataField, ...] = ()
    warning: str = ""
    editable_scope: str = "module_metadata"

    @property
    def ok(self) -> bool:
        return self.parse_status == "ok"

    @property
    def summary(self) -> str:
        if not self.fields:
            return f"{self.restype.upper()} metadata: 0 fields"
        return f"{self.restype.upper()} metadata: {len(self.fields)} editor-facing fields"


@dataclass(frozen=True)
class ModuleMetadataFieldEditDraft:
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
class ModuleMetadataPatchExportResult:
    output_module: str
    manifest_path: str
    source_sha256: str
    output_sha256: str
    patched_resources: tuple[str, ...]
    copied_bytes: int
    draft: ModuleMetadataFieldEditDraft

    @property
    def ok(self) -> bool:
        return self.source_sha256 != self.output_sha256 and bool(self.patched_resources)


def inspect_module_metadata(
    module_path: str | Path,
    resource: ModuleArchiveResource,
) -> ModuleMetadataInventory:
    """Parse module-local ARE/IFO data and return editor-facing metadata facts."""

    if resource.restype not in METADATA_TYPES:
        return ModuleMetadataInventory(
            resource.resref,
            resource.restype,
            "skipped",
            warning="Resource is not an ARE/IFO module metadata file.",
        )
    try:
        raw = read_module_resource_bytes(module_path, resource)
        if resource.restype == "are":
            return _inspect_are(resource, raw)
        return _inspect_ifo(resource, raw)
    except Exception as exc:
        return ModuleMetadataInventory(resource.resref, resource.restype, "parse_failed", warning=str(exc))


def create_metadata_field_edit_draft(
    module_path: str | Path,
    resource: ModuleArchiveResource,
    *,
    field_key: str,
    value: str,
) -> ModuleMetadataFieldEditDraft:
    """Build a validated, non-destructive ARE/IFO field edit preview."""

    field_key = str(field_key or "").strip()
    new_text = _clean_text_value(value)
    if resource.restype not in METADATA_TYPES:
        return _metadata_edit_error(resource, field_key, "", new_text, "not_metadata", "Resource is not ARE/IFO metadata.")
    allowed_fields = set(ARE_EDIT_FIELDS if resource.restype == "are" else IFO_EDIT_FIELDS)
    if field_key not in allowed_fields:
        return _metadata_edit_error(
            resource,
            field_key,
            "",
            new_text,
            "unsupported_field",
            f"Field {field_key!r} is not enabled for safe ARE/IFO edits.",
        )
    try:
        raw = read_module_resource_bytes(module_path, resource)
        gff = _read_gff(raw)
        field = gff.root.fields.get(field_key)
        if field is None:
            return _metadata_edit_error(resource, field_key, "", new_text, "field_missing", f"Field {field_key!r} is not present on {resource.label}.")
        if not _is_editable_gff_type(field.type):
            return _metadata_edit_error(resource, field_key, _display_typed_value(field.value), new_text, "unsupported_field", f"Field {field_key!r} is not a primitive editable field.")
        issue = _field_value_issue(field_key, field.type, new_text)
        if issue:
            return _metadata_edit_error(resource, field_key, _display_typed_value(field.value), new_text, "invalid_value", issue)
        old_text = _display_typed_value(field.value)
        try:
            field.value = _coerce_gff_edit_value(field.type, new_text)
        except Exception as exc:
            return _metadata_edit_error(resource, field_key, old_text, new_text, "coerce_failed", f"Could not convert {field_key!r}: {exc}")
        output = _write_gff(gff)
        reparsed = _read_gff(output)
        check_field = reparsed.root.fields.get(field_key)
        actual_text = _display_typed_value(check_field.value) if check_field is not None else ""
        if check_field is None or not _gff_value_matches(check_field.type, actual_text, new_text):
            return _metadata_edit_error(resource, field_key, old_text, new_text, "roundtrip_failed", "Metadata edit did not survive GFF write/read round-trip.")
        return ModuleMetadataFieldEditDraft(
            resref=resource.resref,
            restype=resource.restype,
            field_key=field_key,
            old_value=old_text,
            new_value=actual_text,
            output_payload=output,
            validation_status="valid",
        )
    except Exception as exc:
        return _metadata_edit_error(resource, field_key, "", new_text, "parse_failed", str(exc))


def write_metadata_field_patch_export_copy(
    source_module: str | Path,
    output_module: str | Path,
    draft: ModuleMetadataFieldEditDraft,
    *,
    manifest_path: str | Path | None = None,
) -> ModuleMetadataPatchExportResult:
    """Export a rebuilt module archive with one validated ARE/IFO metadata edit."""

    source = Path(source_module)
    output = Path(output_module)
    if source.resolve() == output.resolve():
        raise ValueError("Export target must be a new file; the source module will not be overwritten.")
    if not source.exists():
        raise FileNotFoundError(f"Source module does not exist: {source}")
    if not draft.ready:
        message = "; ".join(draft.issues) or f"Metadata edit draft is not exportable: {draft.validation_status}"
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
                source="patched_module_metadata" if changed else "preserved_source_resource",
                changed=changed,
                serializer="validated_gff_binary" if changed else "preserved_binary",
            )
        )
    if not found_target:
        raise ValueError(f"Target metadata resource {draft.resref}.{draft.restype} is not in the source archive.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(build_erf_v1_archive(entries, archive_type=_source_archive_type(source)))
    source_bytes = source.read_bytes()
    output_bytes = output.read_bytes()
    resolved_manifest = Path(manifest_path) if manifest_path is not None else _default_metadata_manifest_path(output)
    manifest = {
        "schema": "ghostrigger.stock_module_metadata_patch_plan.v1",
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
        "note": "Exported module archive was rebuilt from the source archive with only the listed ARE/IFO metadata payload patched.",
    }
    resolved_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ModuleMetadataPatchExportResult(
        output_module=str(output),
        manifest_path=str(resolved_manifest),
        source_sha256=_sha256(source_bytes),
        output_sha256=_sha256(output_bytes),
        patched_resources=(patched_label,),
        copied_bytes=len(output_bytes),
        draft=draft,
    )


def _inspect_are(resource: ModuleArchiveResource, raw: bytes) -> ModuleMetadataInventory:
    from src.core.modules.module_format import AREData

    area = AREData.from_bytes(raw)
    raw_field_count = len(area._raw or {})
    fields = [
        _field("Name", "Area name", area.name, "area_metadata", raw=raw),
        _field("Tag", "Area tag", area.tag, "area_metadata", raw=raw),
        _field("SunAmbientColorDisplay", "Sun ambient", _rgb(area.sun_ambient), "area_lighting"),
        _field("SunDiffuseColorDisplay", "Sun diffuse", _rgb(area.sun_diffuse), "area_lighting"),
        _field("SunFog", "Sun fog enabled", str(bool(area.sun_fog)), "area_lighting", raw=raw),
        _field("FogColorDisplay", "Fog color", _rgb(area.fog_color), "area_lighting"),
        _field("FogNearDist", "Fog near", f"{area.fog_near:.2f}", "area_lighting", raw=raw),
        _field("FogFarDist", "Fog far", f"{area.fog_far:.2f}", "area_lighting", raw=raw),
        _field("MapPt1", "Minimap point 1", _point2(area.map_pt1_x, area.map_pt1_y), "area_minimap"),
        _field("MapPt2", "Minimap point 2", _point2(area.map_pt2_x, area.map_pt2_y), "area_minimap"),
        _field("WorldPt1", "World point 1", _point2(area.world_pt1_x, area.world_pt1_y), "area_minimap"),
        _field("WorldPt2", "World point 2", _point2(area.world_pt2_x, area.world_pt2_y), "area_minimap"),
        _field("raw", "Raw GFF fields", str(raw_field_count), "gff_unknown_metadata"),
    ]
    fields.extend(_extra_edit_fields(raw, ARE_EDIT_FIELDS, "area_metadata", used_keys={field.key for field in fields}))
    return ModuleMetadataInventory(
        resref=resource.resref,
        restype=resource.restype,
        parse_status="ok",
        fields=tuple(fields),
        editable_scope="area_metadata",
    )


def _inspect_ifo(resource: ModuleArchiveResource, raw: bytes) -> ModuleMetadataInventory:
    from src.core.modules.module_format import IFOData

    module = IFOData.from_bytes(raw)
    raw_field_count = len(module._raw or {})
    fields = [
        _field("Mod_Tag", "Module tag", module.tag, "module_metadata", raw=raw),
        _field("Mod_Name", "Module name", module.mod_name, "module_metadata", raw=raw),
        _field("Mod_Entry_Area", "Entry area", module.entry_area, "module_entry", raw=raw),
        _field("Mod_Entry_Position", "Entry position", _point3(module.entry_x, module.entry_y, module.entry_z), "module_entry"),
        _field("Mod_Entry_Direction", "Entry direction", _point2(module.entry_dir_x, module.entry_dir_y), "module_entry"),
        _field("Mod_DawnHour", "Dawn hour", str(module.dawn_hour), "module_time", raw=raw),
        _field("Mod_DuskHour", "Dusk hour", str(module.dusk_hour), "module_time", raw=raw),
        _field("raw", "Raw GFF fields", str(raw_field_count), "gff_unknown_metadata"),
    ]
    fields.extend(_extra_edit_fields(raw, IFO_EDIT_FIELDS, "module_metadata", used_keys={field.key for field in fields}))
    return ModuleMetadataInventory(
        resref=resource.resref,
        restype=resource.restype,
        parse_status="ok",
        fields=tuple(fields),
        editable_scope="module_metadata",
    )


def _field(
    key: str,
    label: str,
    value: object,
    editable_scope: str,
    *,
    raw: bytes | None = None,
) -> ModuleMetadataField:
    text = str(value) if value not in (None, "") else "(empty)"
    gff_field = _typed_root_field(raw, key) if raw is not None else None
    return ModuleMetadataField(
        key=key,
        label=label,
        value=text,
        value_type=_value_type_from_gff_field(gff_field),
        editable_scope=editable_scope,
        editable=gff_field is not None and _is_editable_gff_type(gff_field.type),
    )


def _extra_edit_fields(
    raw: bytes,
    keys: tuple[str, ...],
    editable_scope: str,
    *,
    used_keys: set[str],
) -> tuple[ModuleMetadataField, ...]:
    try:
        gff = _read_gff(raw)
    except Exception:
        return ()
    rows: list[ModuleMetadataField] = []
    for key in keys:
        field = gff.root.fields.get(key)
        if field is None or not _is_editable_gff_type(field.type):
            continue
        if key in used_keys:
            continue
        rows.append(
            ModuleMetadataField(
                key=key,
                label=FIELD_LABELS.get(key, _label_from_key(key)),
                value=_display_typed_value(field.value),
                value_type=_value_type_from_gff_field(field),
                editable_scope=editable_scope,
                editable=True,
            )
        )
    return tuple(rows)


def _typed_root_field(raw: bytes | None, key: str) -> Any | None:
    if raw is None:
        return None
    try:
        return _read_gff(raw).root.fields.get(key)
    except Exception:
        return None


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
        return _resref_issue(value, required=field_key in REQUIRED_RESREF_FIELDS)
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


def _value_type_from_gff_field(field: Any | None) -> str:
    if field is None:
        return "display"
    text = getattr(field.type, "name", str(field.type))
    return str(text).lower()


def _clean_text_value(value: object) -> str:
    return str(value or "").strip().strip("\x00")


def _metadata_edit_error(
    resource: ModuleArchiveResource,
    field_key: str,
    old_value: str,
    new_value: str,
    status: str,
    issue: str,
) -> ModuleMetadataFieldEditDraft:
    return ModuleMetadataFieldEditDraft(
        resref=resource.resref,
        restype=resource.restype,
        field_key=field_key,
        old_value=old_value,
        new_value=new_value,
        validation_status=status,
        issues=(issue,),
    )


def _default_metadata_manifest_path(output: Path) -> Path:
    return output.with_name(output.name + ".ghostrigger_metadata_patch_plan.json")


def _source_archive_type(source: Path) -> str:
    signature = source.read_bytes()[:3].decode("ascii", errors="replace").upper()
    if signature in {"MOD", "RIM", "ERF", "SAV"}:
        return signature
    return "MOD"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _rgb(value: tuple[int, int, int]) -> str:
    return f"{int(value[0])}, {int(value[1])}, {int(value[2])}"


def _point2(x: float, y: float) -> str:
    return f"{float(x):.2f}, {float(y):.2f}"


def _point3(x: float, y: float, z: float) -> str:
    return f"{float(x):.2f}, {float(y):.2f}, {float(z):.2f}"


def _label_from_key(key: str) -> str:
    out: list[str] = []
    for index, char in enumerate(key):
        if index and char.isupper() and not key[index - 1].isupper():
            out.append(" ")
        out.append(char)
    return "".join(out).replace("_", " ").strip().title()


__all__ = [
    "METADATA_TYPES",
    "ModuleMetadataFieldEditDraft",
    "ModuleMetadataField",
    "ModuleMetadataInventory",
    "ModuleMetadataPatchExportResult",
    "create_metadata_field_edit_draft",
    "inspect_module_metadata",
    "write_metadata_field_patch_export_copy",
]
