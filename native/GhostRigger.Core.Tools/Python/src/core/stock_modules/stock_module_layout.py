"""LYT/VIS inventories and safe edits for stock KotOR module archives."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
from src.core.stock_modules.stock_module_archive import ModuleArchiveResource, read_module_resource_bytes


@dataclass(frozen=True)
class ModuleLayoutRoomRow:
    room_resref: str
    position: tuple[float, float, float]


@dataclass(frozen=True)
class ModuleLayoutDoorHookRow:
    hook_name: str
    position: tuple[float, float, float]
    rotation: tuple[float, float, float, float]


@dataclass(frozen=True)
class ModuleVisibilityRow:
    room_resref: str
    visible_rooms: tuple[str, ...]

    @property
    def link_count(self) -> int:
        return len(self.visible_rooms)


@dataclass(frozen=True)
class ModuleLayoutInventory:
    resref: str
    restype: str
    parse_status: str
    rooms: tuple[ModuleLayoutRoomRow, ...] = ()
    doorhooks: tuple[ModuleLayoutDoorHookRow, ...] = ()
    visibility: tuple[ModuleVisibilityRow, ...] = ()
    missing_visibility_targets: tuple[str, ...] = ()
    unlisted_layout_rooms: tuple[str, ...] = ()
    other_line_count: int = 0
    warning: str = ""
    editable_scope: str = "layout_visibility"

    @property
    def ok(self) -> bool:
        return self.parse_status == "ok"

    @property
    def room_count(self) -> int:
        return len(self.rooms)

    @property
    def visibility_entry_count(self) -> int:
        return len(self.visibility)

    @property
    def visibility_link_count(self) -> int:
        return sum(row.link_count for row in self.visibility)

    @property
    def summary(self) -> str:
        if self.restype == "lyt":
            return f"LYT layout: {self.room_count} rooms, {len(self.doorhooks)} doorhooks"
        if self.restype == "vis":
            return f"VIS graph: {self.visibility_entry_count} rooms, {self.visibility_link_count} links"
        return f"{self.restype.upper()} layout resource"


@dataclass(frozen=True)
class ModuleLayoutEditDraft:
    resref: str
    restype: str
    edit_kind: str
    target_key: str
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
        return f"{self.resref}.{self.restype} {self.edit_kind} {self.target_key}.{self.field_key}: {self.old_value} -> {self.new_value}"


@dataclass(frozen=True)
class ModuleLayoutPatchExportResult:
    output_module: str
    manifest_path: str
    source_sha256: str
    output_sha256: str
    patched_resources: tuple[str, ...]
    copied_bytes: int
    draft: ModuleLayoutEditDraft

    @property
    def ok(self) -> bool:
        return self.source_sha256 != self.output_sha256 and bool(self.patched_resources)


def inspect_module_layout(
    module_path: str | Path,
    resources: list[ModuleArchiveResource],
    resource: ModuleArchiveResource,
) -> ModuleLayoutInventory:
    """Parse module-local LYT/VIS data and return editor-facing room graph facts."""

    if resource.restype not in {"lyt", "vis"}:
        return ModuleLayoutInventory(
            resource.resref,
            resource.restype,
            "skipped",
            warning="Resource is not a LYT/VIS layout or visibility file.",
        )
    try:
        raw = read_module_resource_bytes(module_path, resource)
        text = raw.decode("latin-1", errors="replace")
        if resource.restype == "lyt":
            return _inspect_lyt(resource, text)
        return _inspect_vis(module_path, resources, resource, text)
    except Exception as exc:
        return ModuleLayoutInventory(resource.resref, resource.restype, "parse_failed", warning=str(exc))


def create_layout_edit_draft(
    module_path: str | Path,
    resources: list[ModuleArchiveResource],
    resource: ModuleArchiveResource,
    *,
    target_key: str,
    field_key: str,
    value: str,
) -> ModuleLayoutEditDraft:
    """Build a validated, non-destructive LYT room or VIS link edit preview."""

    if resource.restype == "lyt":
        return _create_lyt_room_edit_draft(module_path, resource, target_key=target_key, field_key=field_key, value=value)
    if resource.restype == "vis":
        return _create_vis_link_edit_draft(module_path, resources, resource, target_key=target_key, field_key=field_key, value=value)
    return _layout_edit_error(
        resource,
        "layout",
        target_key,
        field_key,
        "",
        str(value or ""),
        "not_layout",
        "Resource is not a LYT/VIS layout or visibility file.",
    )


def write_layout_patch_export_copy(
    source_module: str | Path,
    output_module: str | Path,
    draft: ModuleLayoutEditDraft,
    *,
    manifest_path: str | Path | None = None,
) -> ModuleLayoutPatchExportResult:
    """Export a rebuilt module archive with one validated LYT/VIS edit."""

    source = Path(source_module)
    output = Path(output_module)
    if source.resolve() == output.resolve():
        raise ValueError("Export target must be a new file; the source module will not be overwritten.")
    if not source.exists():
        raise FileNotFoundError(f"Source module does not exist: {source}")
    if not draft.ready:
        message = "; ".join(draft.issues) or f"Layout edit draft is not exportable: {draft.validation_status}"
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
                source="patched_layout_visibility" if changed else "preserved_source_resource",
                changed=changed,
                serializer="validated_lyt_vis_text" if changed else "preserved_binary",
            )
        )
    if not found_target:
        raise ValueError(f"Target layout resource {draft.resref}.{draft.restype} is not in the source archive.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(build_erf_v1_archive(entries, archive_type=_source_archive_type(source)))
    source_bytes = source.read_bytes()
    output_bytes = output.read_bytes()
    resolved_manifest = Path(manifest_path) if manifest_path is not None else _default_layout_manifest_path(output)
    manifest = {
        "schema": "ghostrigger.stock_module_layout_patch_plan.v1",
        "generated_at": _utc_now(),
        "status": "patched_module_export",
        "archive_bytes_modified": True,
        "source_module": str(source),
        "output_module": str(output),
        "patched_resources": [patched_label],
        "draft": {
            "resref": draft.resref,
            "restype": draft.restype,
            "edit_kind": draft.edit_kind,
            "target_key": draft.target_key,
            "field_key": draft.field_key,
            "old_value": draft.old_value,
            "new_value": draft.new_value,
            "validation_status": draft.validation_status,
            "issues": list(draft.issues),
            "status": draft.status,
            "summary": draft.summary,
        },
        "note": "Exported module archive was rebuilt from the source archive with only the listed LYT/VIS payload patched.",
    }
    resolved_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ModuleLayoutPatchExportResult(
        output_module=str(output),
        manifest_path=str(resolved_manifest),
        source_sha256=_sha256(source_bytes),
        output_sha256=_sha256(output_bytes),
        patched_resources=(patched_label,),
        copied_bytes=len(output_bytes),
        draft=draft,
    )


def _create_lyt_room_edit_draft(
    module_path: str | Path,
    resource: ModuleArchiveResource,
    *,
    target_key: str,
    field_key: str,
    value: str,
) -> ModuleLayoutEditDraft:
    from src.core.modules.module_format import LYTLayout

    room_key = _clean_resref(target_key)
    axis = str(field_key or "").strip().lower()
    new_text = _clean_text_value(value)
    if axis not in {"x", "y", "z"}:
        return _layout_edit_error(resource, "room", room_key, axis, "", new_text, "unsupported_field", "LYT room edits support only X, Y, and Z coordinates.")
    try:
        new_value = float(new_text)
    except ValueError:
        return _layout_edit_error(resource, "room", room_key, axis, "", new_text, "invalid_value", "Room coordinate must be a number.")
    try:
        text = read_module_resource_bytes(module_path, resource).decode("latin-1", errors="replace")
        layout = LYTLayout.from_text(text)
        unsafe_lines = _unsafe_lyt_other_lines(layout.others)
        if unsafe_lines:
            return _layout_edit_error(resource, "room", room_key, axis, "", new_text, "unsupported_layout", "LYT contains unparsed layout lines; edit is blocked to avoid data loss.")
        room = next((item for item in layout.rooms if _clean_resref(item.model) == room_key), None)
        if room is None:
            return _layout_edit_error(resource, "room", room_key, axis, "", new_text, "room_missing", f"Room {room_key!r} is not present in {resource.label}.")
        old_value = float(getattr(room, axis))
        setattr(room, axis, new_value)
        output_text = layout.to_text()
        reparsed = LYTLayout.from_text(output_text)
        check = next((item for item in reparsed.rooms if _clean_resref(item.model) == room_key), None)
        actual = float(getattr(check, axis)) if check is not None else None
        if actual is None or abs(actual - new_value) > 0.0001:
            return _layout_edit_error(resource, "room", room_key, axis, _float_text(old_value), _float_text(new_value), "roundtrip_failed", "LYT room edit did not survive text write/read round-trip.")
        return ModuleLayoutEditDraft(
            resref=resource.resref,
            restype=resource.restype,
            edit_kind="room",
            target_key=room_key,
            field_key=axis.upper(),
            old_value=_float_text(old_value),
            new_value=_float_text(actual),
            output_payload=output_text.encode("latin-1"),
            validation_status="valid",
        )
    except Exception as exc:
        return _layout_edit_error(resource, "room", room_key, axis, "", new_text, "parse_failed", str(exc))


def _create_vis_link_edit_draft(
    module_path: str | Path,
    resources: list[ModuleArchiveResource],
    resource: ModuleArchiveResource,
    *,
    target_key: str,
    field_key: str,
    value: str,
) -> ModuleLayoutEditDraft:
    from src.core.modules.module_format import LYTLayout, VISData

    source_room = _clean_resref(target_key)
    target_room = _clean_resref(field_key)
    enabled = _truthy(value)
    if not source_room or not target_room:
        return _layout_edit_error(resource, "visibility", source_room, target_room, "", str(enabled), "invalid_room", "VIS source and target rooms must be non-empty resrefs.")
    try:
        text = read_module_resource_bytes(module_path, resource).decode("latin-1", errors="replace")
        vis = VISData.from_text(text)
        layout_rooms = _layout_room_names(module_path, resources, resource.resref)
        known_rooms = layout_rooms or {str(room or "").lower() for room in vis.visibility}
        if known_rooms and source_room not in known_rooms:
            return _layout_edit_error(resource, "visibility", source_room, target_room, "", str(enabled), "source_missing", f"Source room {source_room!r} is not listed in the matching LYT/VIS data.")
        if known_rooms and target_room not in known_rooms:
            return _layout_edit_error(resource, "visibility", source_room, target_room, "", str(enabled), "target_missing", f"Target room {target_room!r} is not listed in the matching LYT/VIS data.")
        links = list(dict.fromkeys(_clean_resref(room) for room in vis.visibility.get(source_room, []) if _clean_resref(room)))
        old_enabled = target_room in links
        if enabled and not old_enabled:
            links.append(target_room)
        elif not enabled and old_enabled:
            links = [room for room in links if room != target_room]
        vis.visibility[source_room] = links
        output_text = vis.to_text()
        reparsed = VISData.from_text(output_text)
        actual_enabled = target_room in {_clean_resref(room) for room in reparsed.visibility.get(source_room, [])}
        if actual_enabled != enabled:
            return _layout_edit_error(resource, "visibility", source_room, target_room, str(old_enabled), str(enabled), "roundtrip_failed", "VIS link edit did not survive text write/read round-trip.")
        return ModuleLayoutEditDraft(
            resref=resource.resref,
            restype=resource.restype,
            edit_kind="visibility",
            target_key=source_room,
            field_key=target_room,
            old_value=str(old_enabled),
            new_value=str(actual_enabled),
            output_payload=output_text.encode("latin-1"),
            validation_status="valid",
        )
    except Exception as exc:
        return _layout_edit_error(resource, "visibility", source_room, target_room, "", str(enabled), "parse_failed", str(exc))


def _inspect_lyt(resource: ModuleArchiveResource, text: str) -> ModuleLayoutInventory:
    from src.core.modules.module_format import LYTLayout

    layout = LYTLayout.from_text(text)
    rooms = tuple(
        ModuleLayoutRoomRow(
            room_resref=str(room.model or "").lower(),
            position=(float(room.x), float(room.y), float(room.z)),
        )
        for room in layout.rooms
    )
    doorhooks = tuple(
        ModuleLayoutDoorHookRow(
            hook_name=str(hook.name or "").lower(),
            position=(float(hook.x), float(hook.y), float(hook.z)),
            rotation=(float(hook.qx), float(hook.qy), float(hook.qz), float(hook.qw)),
        )
        for hook in layout.doorhooks
    )
    return ModuleLayoutInventory(
        resref=resource.resref,
        restype=resource.restype,
        parse_status="ok",
        rooms=rooms,
        doorhooks=doorhooks,
        other_line_count=len(layout.others),
        editable_scope="room_layout",
    )


def _inspect_vis(
    module_path: str | Path,
    resources: list[ModuleArchiveResource],
    resource: ModuleArchiveResource,
    text: str,
) -> ModuleLayoutInventory:
    from src.core.modules.module_format import LYTLayout, VISData

    vis = VISData.from_text(text)
    rows = tuple(
        ModuleVisibilityRow(
            room_resref=str(room or "").lower(),
            visible_rooms=tuple(str(target or "").lower() for target in targets),
        )
        for room, targets in sorted(vis.visibility.items())
    )
    layout_rooms: set[str] = set()
    lyt = _matching_resource(resources, resource.resref, "lyt")
    if lyt is not None:
        lyt_text = read_module_resource_bytes(module_path, lyt).decode("latin-1", errors="replace")
        layout = LYTLayout.from_text(lyt_text)
        layout_rooms = {str(room.model or "").lower() for room in layout.rooms}
    vis_rooms = {row.room_resref for row in rows}
    vis_targets = {target for row in rows for target in row.visible_rooms}
    known = layout_rooms or vis_rooms
    missing_targets = tuple(sorted(target for target in vis_targets if target and target not in known))
    unlisted_rooms = tuple(sorted(room for room in layout_rooms if room and room not in vis_rooms))
    warning_parts = []
    if missing_targets:
        warning_parts.append(f"{len(missing_targets)} visibility target(s) are not listed in the matching layout.")
    if unlisted_rooms:
        warning_parts.append(f"{len(unlisted_rooms)} layout room(s) have no VIS entry.")
    return ModuleLayoutInventory(
        resref=resource.resref,
        restype=resource.restype,
        parse_status="ok",
        visibility=rows,
        missing_visibility_targets=missing_targets,
        unlisted_layout_rooms=unlisted_rooms,
        warning="; ".join(warning_parts),
        editable_scope="room_visibility",
    )


def _matching_resource(
    resources: list[ModuleArchiveResource],
    resref: str,
    restype: str,
) -> ModuleArchiveResource | None:
    wanted = (str(resref or "").lower(), str(restype or "").lower())
    for resource in resources:
        if (resource.resref.lower(), resource.restype.lower()) == wanted:
            return resource
    return None


def _layout_room_names(
    module_path: str | Path,
    resources: list[ModuleArchiveResource],
    resref: str,
) -> set[str]:
    from src.core.modules.module_format import LYTLayout

    lyt = _matching_resource(resources, resref, "lyt")
    if lyt is None:
        return set()
    text = read_module_resource_bytes(module_path, lyt).decode("latin-1", errors="replace")
    layout = LYTLayout.from_text(text)
    return {_clean_resref(room.model) for room in layout.rooms if _clean_resref(room.model)}


def _unsafe_lyt_other_lines(lines: list[str]) -> tuple[str, ...]:
    safe_prefixes = (
        "filedependancy ",
        "filedependency ",
        "beginlayout",
        "trackcount 0",
        "obstaclecount 0",
        "articulatedmeshcount 0",
        "othercounttype 0",
    )
    unsafe: list[str] = []
    for line in lines:
        lowered = str(line or "").strip().lower()
        if not lowered:
            continue
        if any(lowered == prefix.rstrip() or lowered.startswith(prefix) for prefix in safe_prefixes):
            continue
        unsafe.append(str(line))
    return tuple(unsafe)


def _layout_edit_error(
    resource: ModuleArchiveResource,
    edit_kind: str,
    target_key: str,
    field_key: str,
    old_value: str,
    new_value: str,
    status: str,
    issue: str,
) -> ModuleLayoutEditDraft:
    return ModuleLayoutEditDraft(
        resref=resource.resref,
        restype=resource.restype,
        edit_kind=edit_kind,
        target_key=target_key,
        field_key=field_key,
        old_value=old_value,
        new_value=new_value,
        validation_status=status,
        issues=(issue,),
    )


def _clean_resref(value: object) -> str:
    return str(value or "").strip().strip("\x00").lower()[:16]


def _clean_text_value(value: object) -> str:
    return str(value or "").strip().strip("\x00")


def _truthy(value: object) -> bool:
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "on", "add", "visible", "enabled"}


def _float_text(value: float) -> str:
    return f"{float(value):.6g}"


def _default_layout_manifest_path(output: Path) -> Path:
    return output.with_name(output.name + ".ghostrigger_layout_patch_plan.json")


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
    "ModuleLayoutDoorHookRow",
    "ModuleLayoutEditDraft",
    "ModuleLayoutInventory",
    "ModuleLayoutPatchExportResult",
    "ModuleLayoutRoomRow",
    "ModuleVisibilityRow",
    "create_layout_edit_draft",
    "inspect_module_layout",
    "write_layout_patch_export_copy",
]
