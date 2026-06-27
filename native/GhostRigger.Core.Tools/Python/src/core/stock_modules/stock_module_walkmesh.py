"""Read-only WOK walkmesh inventories for stock KotOR module archives."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.core.stock_modules.stock_module_archive import ModuleArchiveResource, read_module_resource_bytes
from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive


@dataclass(frozen=True)
class ModuleWokSurfaceOption:
    surface_id: int
    surface_name: str
    walkable: bool


@dataclass(frozen=True)
class ModuleWokSurfaceSummary:
    surface_id: int
    surface_name: str
    face_count: int
    walkable: bool
    face_indices: tuple[int, ...] = ()


@dataclass(frozen=True)
class ModuleWokInventory:
    room_resref: str
    parse_status: str
    vertex_count: int = 0
    face_count: int = 0
    walkable_face_count: int = 0
    non_walk_face_count: int = 0
    boundary_edge_count: int = 0
    transition_face_count: int = 0
    surfaces: tuple[ModuleWokSurfaceSummary, ...] = ()
    issue_summary: tuple[str, ...] = ()
    warning: str = ""
    editable_scope: str = "walkmesh_face_surface"

    @property
    def ok(self) -> bool:
        return self.parse_status == "ok"

    @property
    def summary(self) -> str:
        return (
            f"{self.vertex_count} verts, {self.face_count} faces, "
            f"{self.walkable_face_count} walkable, {self.non_walk_face_count} non-walk"
        )


@dataclass(frozen=True)
class ModuleWokSurfacePaintDraft:
    room_resref: str
    face_indices: tuple[int, ...]
    old_surfaces: dict[int, int]
    new_surface_id: int
    new_surface_name: str
    output_payload: bytes = b""
    validation_status: str = "not_validated"
    issues: tuple[str, ...] = ()
    status: str = "preview_only"

    @property
    def ready(self) -> bool:
        return bool(self.output_payload) and self.validation_status in {"valid", "roundtrip_ok"}

    @property
    def summary(self) -> str:
        faces = ", ".join(str(index) for index in self.face_indices) or "(none)"
        return f"{self.room_resref}.wok face(s) {faces} -> {self.new_surface_name} ({self.new_surface_id})"


@dataclass(frozen=True)
class ModuleWokSurfacePatchExportResult:
    output_module: str
    manifest_path: str
    source_sha256: str
    output_sha256: str
    patched_resources: tuple[str, ...]
    copied_bytes: int
    draft: ModuleWokSurfacePaintDraft

    @property
    def ok(self) -> bool:
        return self.source_sha256 != self.output_sha256 and bool(self.patched_resources)


def inspect_module_wok(
    module_path: str | Path,
    resource: ModuleArchiveResource,
) -> ModuleWokInventory:
    """Parse a module-local WOK and return editor-facing walkmesh facts."""

    if resource.restype != "wok":
        return ModuleWokInventory(resource.resref, "skipped", warning="Resource is not a WOK walkmesh.")
    try:
        raw = read_module_resource_bytes(module_path, resource)
        if raw[:4] not in {b"BWM ", b"BWM\x20"}:
            signature = raw[:8].decode("ascii", errors="replace")
            return ModuleWokInventory(
                resource.resref,
                "unsupported_format",
                warning=f"WOK payload does not use the supported BWM binary signature: {signature!r}.",
            )
        from src.core.modules.module_format import WOKData

        wok = WOKData.from_bytes(raw)
        wok.name = resource.resref
        from src.core.walkmesh.walkmesh_editor import build_walkmesh_workbench

        workbench = build_walkmesh_workbench(wok, room=resource.resref)
    except Exception as exc:
        return ModuleWokInventory(resource.resref, "parse_failed", warning=str(exc))

    validation = workbench.validation
    if not workbench.ok or validation is None:
        return ModuleWokInventory(
            resource.resref,
            workbench.code or "parse_failed",
            warning=workbench.message,
        )
    issue_summary = tuple(
        f"{issue.severity.upper()} {issue.code}: {issue.message}"
        for issue in validation.issues[:8]
    )
    face_indices_by_surface: dict[int, list[int]] = {}
    for face_index, face in enumerate(wok.faces):
        face_indices_by_surface.setdefault(int(face.surface), []).append(int(face_index))
    surfaces = tuple(
        ModuleWokSurfaceSummary(
            surface_id=int(surface_id),
            surface_name=_surface_name(workbench, int(surface_id)),
            face_count=int(count),
            walkable=_surface_walkable(workbench, int(surface_id)),
            face_indices=tuple(face_indices_by_surface.get(int(surface_id), ())),
        )
        for surface_id, count in sorted(validation.surface_distribution.items())
    )
    return ModuleWokInventory(
        room_resref=resource.resref,
        parse_status="ok" if validation.ok else "validation_failed",
        vertex_count=validation.vertex_count,
        face_count=validation.face_count,
        walkable_face_count=validation.walkable_face_count,
        non_walk_face_count=validation.non_walk_face_count,
        boundary_edge_count=validation.boundary_edge_count,
        transition_face_count=validation.transition_face_count,
        surfaces=surfaces,
        issue_summary=issue_summary,
        warning="" if validation.ok else validation.message,
    )


def walkmesh_surface_options() -> tuple[ModuleWokSurfaceOption, ...]:
    """Return KOTOR WOK surface materials for editor-facing paint controls."""

    from src.core.walkmesh.walkmesh_editor import walkmesh_surface_palette

    return tuple(
        ModuleWokSurfaceOption(
            surface_id=int(surface.surface_id),
            surface_name=str(surface.name),
            walkable=bool(surface.walkable),
        )
        for surface in walkmesh_surface_palette()
    )


def create_wok_surface_paint_draft(
    module_path: str | Path,
    resource: ModuleArchiveResource,
    face_indices: int | Iterable[int],
    surface_id: int,
) -> ModuleWokSurfacePaintDraft:
    """Build a validated, non-destructive WOK surface paint preview."""

    if resource.restype != "wok":
        return ModuleWokSurfacePaintDraft(
            room_resref=resource.resref,
            face_indices=(),
            old_surfaces={},
            new_surface_id=int(surface_id),
            new_surface_name=_surface_name_from_id(int(surface_id)),
            issues=("Resource is not a WOK walkmesh.",),
            validation_status="not_wok",
        )
    indices = (int(face_indices),) if isinstance(face_indices, int) else tuple(int(index) for index in face_indices)
    try:
        raw = read_module_resource_bytes(module_path, resource)
        if raw[:4] not in {b"BWM ", b"BWM\x20"}:
            return ModuleWokSurfacePaintDraft(
                room_resref=resource.resref,
                face_indices=indices,
                old_surfaces={},
                new_surface_id=int(surface_id),
                new_surface_name=_surface_name_from_id(int(surface_id)),
                issues=("WOK payload does not use the supported BWM binary signature.",),
                validation_status="unsupported_format",
            )
        from src.core.modules.module_format import WOKData
        from src.core.walkmesh.walkmesh_editor import roundtrip_walkmesh, set_walkmesh_face_surface

        wok = WOKData.from_bytes(raw)
        wok.name = resource.resref
        edit = set_walkmesh_face_surface(wok, indices, int(surface_id), room=resource.resref)
        if not edit.ok:
            return ModuleWokSurfacePaintDraft(
                room_resref=resource.resref,
                face_indices=indices,
                old_surfaces=dict(edit.old_surfaces),
                new_surface_id=int(surface_id),
                new_surface_name=edit.new_surface_name or _surface_name_from_id(int(surface_id)),
                issues=(edit.message,),
                validation_status=edit.code or "edit_failed",
            )
        validation = edit.workbench.validation if edit.workbench is not None else None
        issue_summary = tuple(
            f"{issue.severity.upper()} {issue.code}: {issue.message}"
            for issue in (validation.issues if validation is not None else ())[:8]
        )
        roundtrip = roundtrip_walkmesh(wok, room=resource.resref)
        if not roundtrip.ok:
            return ModuleWokSurfacePaintDraft(
                room_resref=resource.resref,
                face_indices=indices,
                old_surfaces=dict(edit.old_surfaces),
                new_surface_id=int(surface_id),
                new_surface_name=edit.new_surface_name,
                issues=issue_summary + (roundtrip.message,),
                validation_status=roundtrip.code or "roundtrip_failed",
            )
        return ModuleWokSurfacePaintDraft(
            room_resref=resource.resref,
            face_indices=indices,
            old_surfaces=dict(edit.old_surfaces),
            new_surface_id=int(surface_id),
            new_surface_name=edit.new_surface_name,
            output_payload=wok.to_bytes(),
            validation_status="valid" if validation is None or validation.ok else "validation_failed",
            issues=issue_summary,
        )
    except Exception as exc:
        return ModuleWokSurfacePaintDraft(
            room_resref=resource.resref,
            face_indices=indices,
            old_surfaces={},
            new_surface_id=int(surface_id),
            new_surface_name=_surface_name_from_id(int(surface_id)),
            issues=(str(exc),),
            validation_status="parse_failed",
        )


def write_wok_surface_patch_export_copy(
    source_module: str | Path,
    output_module: str | Path,
    draft: ModuleWokSurfacePaintDraft,
    *,
    manifest_path: str | Path | None = None,
) -> ModuleWokSurfacePatchExportResult:
    """Export a rebuilt module archive with one validated WOK surface patch."""

    source = Path(source_module)
    output = Path(output_module)
    if source.resolve() == output.resolve():
        raise ValueError("Export target must be a new file; the source module will not be overwritten.")
    if not source.exists():
        raise FileNotFoundError(f"Source module does not exist: {source}")
    if not draft.ready:
        message = "; ".join(draft.issues) or f"WOK surface draft is not exportable: {draft.validation_status}"
        raise ValueError(message)

    from src.core.stock_modules.stock_module_archive import read_module_archive_resources, read_module_resource_bytes

    resources = read_module_archive_resources(source)
    patched_label = f"{draft.room_resref.lower()}.wok"
    found_target = False
    entries: list[ModuleArchiveEntry] = []
    for resource in resources:
        label = resource.label.lower()
        changed = label == patched_label
        if changed:
            found_target = True
        entries.append(
            ModuleArchiveEntry(
                resref=resource.resref,
                restype=resource.restype,
                data=draft.output_payload if changed else read_module_resource_bytes(source, resource),
                source="patched_wok_surface_material" if changed else "preserved_source_resource",
                changed=changed,
                serializer="validated_wok_binary" if changed else "preserved_binary",
            )
        )
    if not found_target:
        raise ValueError(f"Target walkmesh {draft.room_resref}.wok is not in the source archive.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(build_erf_v1_archive(entries, archive_type=_source_archive_type(source)))
    source_bytes = source.read_bytes()
    output_bytes = output.read_bytes()
    resolved_manifest = Path(manifest_path) if manifest_path is not None else _default_wok_manifest_path(output)
    manifest = {
        "schema": "ghostrigger.stock_module_wok_surface_patch_plan.v1",
        "generated_at": _utc_now(),
        "status": "patched_module_export",
        "archive_bytes_modified": True,
        "source_module": str(source),
        "output_module": str(output),
        "patched_resources": (patched_label,),
        "draft": {
            "room_resref": draft.room_resref,
            "face_indices": list(draft.face_indices),
            "old_surfaces": {str(key): value for key, value in sorted(draft.old_surfaces.items())},
            "new_surface_id": draft.new_surface_id,
            "new_surface_name": draft.new_surface_name,
            "validation_status": draft.validation_status,
            "issues": list(draft.issues),
            "status": draft.status,
            "summary": draft.summary,
        },
        "note": "Exported module archive was rebuilt from the source archive with only the listed WOK payload patched.",
    }
    resolved_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ModuleWokSurfacePatchExportResult(
        output_module=str(output),
        manifest_path=str(resolved_manifest),
        source_sha256=_sha256(source_bytes),
        output_sha256=_sha256(output_bytes),
        patched_resources=(patched_label,),
        copied_bytes=len(output_bytes),
        draft=draft,
    )


def _surface_name(workbench: object, surface_id: int) -> str:
    for surface in getattr(workbench, "surfaces", []) or []:
        if int(getattr(surface, "surface_id", -1)) == surface_id:
            return str(getattr(surface, "name", "") or f"SURFACE_{surface_id}")
    return f"SURFACE_{surface_id}"


def _surface_walkable(workbench: object, surface_id: int) -> bool:
    for surface in getattr(workbench, "surfaces", []) or []:
        if int(getattr(surface, "surface_id", -1)) == surface_id:
            return bool(getattr(surface, "walkable", False))
    return False


def _surface_name_from_id(surface_id: int) -> str:
    for surface in walkmesh_surface_options():
        if surface.surface_id == surface_id:
            return surface.surface_name
    return f"SURFACE_{surface_id}"


def _default_wok_manifest_path(output: Path) -> Path:
    return output.with_name(output.name + ".ghostrigger_wok_patch_plan.json")


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
    "ModuleWokInventory",
    "ModuleWokSurfaceOption",
    "ModuleWokSurfacePaintDraft",
    "ModuleWokSurfacePatchExportResult",
    "ModuleWokSurfaceSummary",
    "create_wok_surface_paint_draft",
    "inspect_module_wok",
    "walkmesh_surface_options",
    "write_wok_surface_patch_export_copy",
]
