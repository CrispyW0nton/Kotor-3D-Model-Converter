"""Combined safe export for queued stock Module Editor edits."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
from src.core.stock_modules.stock_module_archive import read_module_archive_resources, read_module_resource_bytes
from src.core.stock_modules.stock_module_git import ModuleGitObjectEditDraft
from src.core.stock_modules.stock_module_layout import ModuleLayoutEditDraft
from src.core.stock_modules.stock_module_logic import ModuleLogicFieldEditDraft
from src.core.stock_modules.stock_module_materials import ModuleTextureReplacementDraft
from src.core.stock_modules.stock_module_mdl_patch import ModuleMDLTexturePatchResult, patch_room_mdl_texture_reference
from src.core.stock_modules.stock_module_metadata import ModuleMetadataFieldEditDraft
from src.core.stock_modules.stock_module_templates import ModuleTemplateFieldEditDraft
from src.core.stock_modules.stock_module_walkmesh import ModuleWokSurfacePaintDraft


QueuedModuleEditDraft = (
    ModuleTextureReplacementDraft
    | ModuleWokSurfacePaintDraft
    | ModuleGitObjectEditDraft
    | ModuleTemplateFieldEditDraft
    | ModuleMetadataFieldEditDraft
    | ModuleLayoutEditDraft
    | ModuleLogicFieldEditDraft
)


# ── Draft-type dispatch table (#15) ────────────────────────────────────
# Each queued draft type is registered exactly once with its cohesive export
# metadata (kind, changed-source label, serializer id, payload key). Adding an
# 8th draft type is a ONE-line edit to ``_DRAFT_DISPATCH`` (plus the
# ``QueuedModuleEditDraft`` union above) instead of touching four parallel
# isinstance ladders. The public helpers below are thin lookups over this table.


def _payload_key_resref_restype(draft: QueuedModuleEditDraft) -> tuple[str, str]:
    """Payload key for drafts that carry a generic ``resref``/``restype`` pair."""
    return (draft.resref.lower(), draft.restype.lower())


@dataclass(frozen=True)
class _DraftDispatch:
    """Cohesive export metadata for one queued-module-edit draft type."""

    kind: str
    changed_source: str
    serializer: str
    payload_key: Callable[[QueuedModuleEditDraft], tuple[str, str]]


_DRAFT_DISPATCH: dict[type, _DraftDispatch] = {
    ModuleTextureReplacementDraft: _DraftDispatch(
        kind="texture",
        changed_source="patched_module_resource",
        serializer="validated_payload",
        payload_key=lambda draft: (draft.target.room_resref.lower(), "mdl"),
    ),
    ModuleWokSurfacePaintDraft: _DraftDispatch(
        kind="wok",
        changed_source="patched_wok_surface",
        serializer="validated_bwm_binary",
        payload_key=lambda draft: (draft.room_resref.lower(), "wok"),
    ),
    ModuleGitObjectEditDraft: _DraftDispatch(
        kind="git",
        changed_source="patched_git_object_form",
        serializer="validated_gff_binary",
        payload_key=lambda draft: (draft.git_resref.lower(), "git"),
    ),
    ModuleTemplateFieldEditDraft: _DraftDispatch(
        kind="template",
        changed_source="patched_gameplay_template_form",
        serializer="validated_gff_binary",
        payload_key=_payload_key_resref_restype,
    ),
    ModuleMetadataFieldEditDraft: _DraftDispatch(
        kind="metadata",
        changed_source="patched_module_metadata",
        serializer="validated_gff_binary",
        payload_key=_payload_key_resref_restype,
    ),
    ModuleLayoutEditDraft: _DraftDispatch(
        kind="layout",
        changed_source="patched_layout_visibility",
        serializer="validated_lyt_vis_text",
        payload_key=_payload_key_resref_restype,
    ),
    ModuleLogicFieldEditDraft: _DraftDispatch(
        kind="logic",
        changed_source="patched_logic_field",
        serializer="validated_gff_binary",
        payload_key=_payload_key_resref_restype,
    ),
}


def _draft_dispatch(draft: QueuedModuleEditDraft) -> _DraftDispatch:
    """Look up the cohesive export metadata for a queued draft."""
    try:
        return _DRAFT_DISPATCH[type(draft)]
    except KeyError:
        raise TypeError(
            f"Unsupported queued draft type: {draft.__class__.__name__}"
        ) from None



@dataclass(frozen=True)
class ModuleQueuedExportIssue:
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class ModuleQueuedPatchExportResult:
    output_module: str
    manifest_path: str
    source_sha256: str
    output_sha256: str
    patched_resources: tuple[str, ...]
    bundled_resources: tuple[str, ...]
    copied_bytes: int
    edit_count: int
    issues: tuple[ModuleQueuedExportIssue, ...] = ()
    texture_patch_results: tuple[ModuleMDLTexturePatchResult, ...] = ()

    @property
    def ok(self) -> bool:
        return self.source_sha256 != self.output_sha256 and bool(self.patched_resources or self.bundled_resources) and not self.issues


@dataclass(frozen=True)
class ModuleQueuedPatchPreflight:
    edit_count: int
    patched_resources: tuple[str, ...] = ()
    bundled_resources: tuple[str, ...] = ()
    preserved_resources: tuple[str, ...] = ()
    preserved_resources_enumerated: bool = False
    issues: tuple[ModuleQueuedExportIssue, ...] = ()
    source_preserved: bool = True

    @property
    def ready(self) -> bool:
        return self.edit_count > 0 and not any(issue.severity == "error" for issue in self.issues)

    @property
    def patch_summary(self) -> str:
        if not self.patched_resources:
            return "(none)"
        return ", ".join(self.patched_resources)

    @property
    def bundle_summary(self) -> str:
        if not self.bundled_resources:
            return "(none)"
        return ", ".join(self.bundled_resources)

    @property
    def preserve_summary(self) -> str:
        if not self.preserved_resources:
            return "(none)" if self.preserved_resources_enumerated else "(not enumerated)"
        return ", ".join(self.preserved_resources)

    @property
    def source_summary(self) -> str:
        return "source module preserved; copied export receives staged edits"

    @property
    def summary(self) -> str:
        return (
            f"{self.edit_count} edit(s); patches {self.patch_summary}; "
            f"bundles {self.bundle_summary}; source preserved"
        )


def describe_module_edit_draft(draft: QueuedModuleEditDraft) -> str:
    """Return a compact, user-facing summary for a queued edit draft."""

    return str(getattr(draft, "summary", draft.__class__.__name__))


def summarize_queued_module_patch_preflight(
    drafts: Iterable[QueuedModuleEditDraft],
    *,
    existing_resources: Iterable[object] | None = None,
) -> ModuleQueuedPatchPreflight:
    """Describe the resources a queued copied-module export would touch."""

    draft_tuple = tuple(drafts)
    existing_key_list = [
        (str(getattr(resource, "resref", "")).lower(), str(getattr(resource, "restype", "")).lower())
        for resource in (existing_resources or ())
    ]
    existing_keys = set(existing_key_list)
    known_resources = bool(existing_resources is not None)
    issues = list(_validate_queued_drafts(draft_tuple))
    patched_keys: list[tuple[str, str]] = []
    bundled_keys: list[tuple[str, str]] = []
    seen_changed_payload_keys: set[tuple[str, str]] = set()
    seen_resource_keys = set(existing_keys)

    if not draft_tuple:
        issues.append(ModuleQueuedExportIssue("error", "no_drafts", "No staged Module Editor edits are queued for export."))

    for index, draft in enumerate(draft_tuple, start=1):
        if isinstance(draft, ModuleTextureReplacementDraft):
            key = (draft.target.room_resref.lower(), "mdl")
            _append_unique_key(patched_keys, key)
            if known_resources and key not in existing_keys:
                issues.append(
                    ModuleQueuedExportIssue(
                        "error",
                        "missing_target_resource",
                        f"Draft {index}: target room model {key[0]}.{key[1]} is not in the source archive.",
                    )
                )
            _append_texture_bundle_preflight(bundled_keys, seen_resource_keys, draft)
            continue

        key = _payload_draft_key(draft)
        if key in seen_changed_payload_keys:
            issues.append(
                ModuleQueuedExportIssue(
                    "error",
                    "duplicate_target_resource",
                    f"Draft {index}: queued edits both replace {key[0]}.{key[1]}; batch composition for the same resource is not enabled yet.",
                )
            )
        seen_changed_payload_keys.add(key)
        _append_unique_key(patched_keys, key)
        if known_resources and key not in existing_keys:
            issues.append(
                ModuleQueuedExportIssue(
                    "error",
                    "missing_target_resource",
                    f"Draft {index}: target resource {key[0]}.{key[1]} is not in the source archive.",
                )
            )

    return ModuleQueuedPatchPreflight(
        edit_count=len(draft_tuple),
        patched_resources=tuple(f"{key[0]}.{key[1]}" for key in patched_keys),
        bundled_resources=tuple(f"{key[0]}.{key[1]}" for key in bundled_keys),
        preserved_resources=tuple(
            f"{key[0]}.{key[1]}"
            for key in existing_key_list
            if key not in set(patched_keys)
        ) if known_resources else (),
        preserved_resources_enumerated=known_resources,
        issues=tuple(issues),
    )


def write_queued_module_patch_export_copy(
    source_module: str | Path,
    output_module: str | Path,
    drafts: Iterable[QueuedModuleEditDraft],
    *,
    manifest_path: str | Path | None = None,
) -> ModuleQueuedPatchExportResult:
    """Export one rebuilt module archive with all queued validated edits applied."""

    source = Path(source_module)
    output = Path(output_module)
    draft_tuple = tuple(drafts)
    if source.resolve() == output.resolve():
        raise ValueError("Export target must be a new file; the source module will not be overwritten.")
    if not source.exists():
        raise FileNotFoundError(f"Source module does not exist: {source}")
    if not draft_tuple:
        raise ValueError("No staged Module Editor edits are queued for export.")

    issues = _validate_queued_drafts(draft_tuple)
    if issues:
        raise ValueError("; ".join(issue.message for issue in issues if issue.severity == "error"))

    resources = read_module_archive_resources(source)
    payload_by_key = {
        (resource.resref.lower(), resource.restype.lower()): read_module_resource_bytes(source, resource)
        for resource in resources
    }
    changed_source_by_key: dict[tuple[str, str], str] = {}
    serializer_by_key: dict[tuple[str, str], str] = {}
    bundled_keys: list[tuple[str, str]] = []
    texture_patch_results: list[ModuleMDLTexturePatchResult] = []

    for draft in draft_tuple:
        if isinstance(draft, ModuleTextureReplacementDraft):
            key = (draft.target.room_resref.lower(), "mdl")
            mdl_bytes = payload_by_key.get(key)
            if mdl_bytes is None:
                raise ValueError(f"Target room model {draft.target.room_resref}.mdl is not in the source archive.")
            patched_bytes, patch_result = patch_room_mdl_texture_reference(mdl_bytes, draft)
            payload_by_key[key] = patched_bytes
            changed_source_by_key[key] = "patched_mdl_texture_reference"
            serializer_by_key[key] = "fixed_mdl_texture_field"
            texture_patch_results.append(patch_result)
            _bundle_texture_payload(payload_by_key, bundled_keys, draft)
            continue
        key = _payload_draft_key(draft)
        if key in changed_source_by_key:
            raise ValueError(f"Queued edits both replace {key[0]}.{key[1]}; batch composition for the same resource is not enabled yet.")
        if key not in payload_by_key:
            raise ValueError(f"Target resource {key[0]}.{key[1]} is not in the source archive.")
        payload_by_key[key] = draft.output_payload  # type: ignore[union-attr]
        changed_source_by_key[key] = _draft_changed_source(draft)
        serializer_by_key[key] = _draft_serializer(draft)

    entries: list[ModuleArchiveEntry] = []
    for resource in resources:
        key = (resource.resref.lower(), resource.restype.lower())
        changed = key in changed_source_by_key
        entries.append(
            ModuleArchiveEntry(
                resref=resource.resref,
                restype=resource.restype,
                data=payload_by_key[key],
                source=changed_source_by_key.get(key, "preserved_source_resource"),
                changed=changed,
                serializer=serializer_by_key.get(key, "preserved_binary"),
            )
        )
    for key in bundled_keys:
        entries.append(
            ModuleArchiveEntry(
                resref=key[0],
                restype=key[1],
                data=payload_by_key[key],
                source="bundled_replacement_texture",
                changed=True,
                serializer="copied_texture_payload",
            )
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(build_erf_v1_archive(entries, archive_type=_source_archive_type(source)))
    source_bytes = source.read_bytes()
    output_bytes = output.read_bytes()
    patched_resources = tuple(f"{key[0]}.{key[1]}" for key in changed_source_by_key)
    bundled_resources = tuple(f"{key[0]}.{key[1]}" for key in bundled_keys)
    resolved_manifest = Path(manifest_path) if manifest_path is not None else _default_queue_manifest_path(output)
    manifest = {
        "schema": "ghostrigger.stock_module_queued_patch_plan.v1",
        "generated_at": _utc_now(),
        "status": "patched_module_export",
        "archive_bytes_modified": True,
        "source_module": str(source),
        "output_module": str(output),
        "edit_count": len(draft_tuple),
        "patched_resources": list(patched_resources),
        "bundled_resources": list(bundled_resources),
        "preserved_resources": [
            f"{resource.resref.lower()}.{resource.restype.lower()}"
            for resource in resources
            if (resource.resref.lower(), resource.restype.lower()) not in changed_source_by_key
        ],
        "edits": [_draft_manifest(draft) for draft in draft_tuple],
        "note": "Exported module archive was rebuilt once from the source archive with all queued Module Editor edits applied.",
    }
    resolved_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ModuleQueuedPatchExportResult(
        output_module=str(output),
        manifest_path=str(resolved_manifest),
        source_sha256=_sha256(source_bytes),
        output_sha256=_sha256(output_bytes),
        patched_resources=patched_resources,
        bundled_resources=bundled_resources,
        copied_bytes=len(output_bytes),
        edit_count=len(draft_tuple),
        texture_patch_results=tuple(texture_patch_results),
    )


def _validate_queued_drafts(drafts: tuple[QueuedModuleEditDraft, ...]) -> tuple[ModuleQueuedExportIssue, ...]:
    issues: list[ModuleQueuedExportIssue] = []
    for index, draft in enumerate(drafts, start=1):
        ready = _draft_ready(draft)
        if not ready:
            issues.append(
                ModuleQueuedExportIssue(
                    "error",
                    "draft_not_ready",
                    f"Draft {index} is not ready for export: {describe_module_edit_draft(draft)}",
                )
            )
    return tuple(issues)


def _draft_ready(draft: QueuedModuleEditDraft) -> bool:
    if isinstance(draft, ModuleTextureReplacementDraft):
        return (
            draft.status == "preview_only"
            and bool(draft.replacement_texture_resref)
            and draft.replacement_format in {"tga", "tpc"}
            and bool(draft.target.room_resref)
            and bool(draft.target.node_name)
            and draft.original_texture_resref != draft.replacement_texture_resref
        )
    return bool(getattr(draft, "ready", False))


def _payload_draft_key(draft: QueuedModuleEditDraft) -> tuple[str, str]:
    return _draft_dispatch(draft).payload_key(draft)


def _draft_changed_source(draft: QueuedModuleEditDraft) -> str:
    return _draft_dispatch(draft).changed_source


def _draft_serializer(draft: QueuedModuleEditDraft) -> str:
    return _draft_dispatch(draft).serializer


def _bundle_texture_payload(
    payload_by_key: dict[tuple[str, str], bytes],
    bundled_keys: list[tuple[str, str]],
    draft: ModuleTextureReplacementDraft,
) -> None:
    texture_key = (draft.replacement_texture_resref.lower(), draft.replacement_format.lower())
    if texture_key not in payload_by_key and draft.replacement_payload:
        payload_by_key[texture_key] = draft.replacement_payload
        bundled_keys.append(texture_key)
    for sidecar in draft.replacement_sidecars:
        sidecar_key = (sidecar.resref.lower(), sidecar.restype.lower())
        if sidecar_key in payload_by_key or not sidecar.payload:
            continue
        payload_by_key[sidecar_key] = sidecar.payload
        bundled_keys.append(sidecar_key)


def _append_texture_bundle_preflight(
    bundled_keys: list[tuple[str, str]],
    seen_resource_keys: set[tuple[str, str]],
    draft: ModuleTextureReplacementDraft,
) -> None:
    texture_key = (draft.replacement_texture_resref.lower(), draft.replacement_format.lower())
    if texture_key not in seen_resource_keys and draft.replacement_payload:
        seen_resource_keys.add(texture_key)
        bundled_keys.append(texture_key)
    for sidecar in draft.replacement_sidecars:
        sidecar_key = (sidecar.resref.lower(), sidecar.restype.lower())
        if sidecar_key in seen_resource_keys or not sidecar.payload:
            continue
        seen_resource_keys.add(sidecar_key)
        bundled_keys.append(sidecar_key)


def _append_unique_key(keys: list[tuple[str, str]], key: tuple[str, str]) -> None:
    if key not in keys:
        keys.append(key)


def _draft_manifest(draft: QueuedModuleEditDraft) -> dict[str, Any]:
    data = {
        "kind": _draft_kind(draft),
        "summary": describe_module_edit_draft(draft),
        "status": str(getattr(draft, "status", "")),
    }
    if isinstance(draft, ModuleTextureReplacementDraft):
        data.update(
            {
                "resource": f"{draft.target.room_resref}.mdl",
                "target": f"{draft.target.node_name}.{draft.target.slot_kind}",
                "original_texture_resref": draft.original_texture_resref,
                "replacement_texture_resref": draft.replacement_texture_resref,
                "replacement_format": draft.replacement_format,
                "replacement_payload_bundled": bool(draft.replacement_payload),
                "replacement_sidecars": [sidecar.label for sidecar in draft.replacement_sidecars],
            }
        )
    elif isinstance(draft, ModuleWokSurfacePaintDraft):
        data.update({"resource": f"{draft.room_resref}.wok", "faces": list(draft.face_indices), "new_surface_id": draft.new_surface_id})
    elif isinstance(draft, ModuleGitObjectEditDraft):
        data.update({"resource": f"{draft.git_resref}.git", "object": f"{draft.object_type}.{draft.index}", "field_key": draft.field_key, "old_value": draft.old_value, "new_value": draft.new_value})
    elif isinstance(draft, (ModuleTemplateFieldEditDraft, ModuleMetadataFieldEditDraft, ModuleLogicFieldEditDraft)):
        data.update({"resource": f"{draft.resref}.{draft.restype}", "field_key": draft.field_key, "old_value": draft.old_value, "new_value": draft.new_value})
    elif isinstance(draft, ModuleLayoutEditDraft):
        data.update({"resource": f"{draft.resref}.{draft.restype}", "edit_kind": draft.edit_kind, "target_key": draft.target_key, "field_key": draft.field_key, "old_value": draft.old_value, "new_value": draft.new_value})
    return data


def _draft_kind(draft: QueuedModuleEditDraft) -> str:
    return _draft_dispatch(draft).kind


def _default_queue_manifest_path(output: Path) -> Path:
    return output.with_name(output.name + ".ghostrigger_queued_patch_plan.json")


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
    "ModuleQueuedExportIssue",
    "ModuleQueuedPatchExportResult",
    "ModuleQueuedPatchPreflight",
    "QueuedModuleEditDraft",
    "describe_module_edit_draft",
    "summarize_queued_module_patch_preflight",
    "write_queued_module_patch_export_copy",
]
