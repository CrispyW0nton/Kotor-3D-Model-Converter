"""Validated patch plans for non-destructive stock module texture edits."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
from src.core.stock_modules.stock_module_archive import read_module_archive_resources, read_module_resource_bytes
from src.core.stock_modules.stock_module_materials import ModuleTextureReplacementDraft
from src.core.stock_modules.stock_module_mdl_patch import ModuleMDLTexturePatchResult, patch_room_mdl_texture_reference


@dataclass(frozen=True)
class ModuleTexturePatchIssue:
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class ModuleTexturePatchPlan:
    source_module: str
    output_module: str
    drafts: tuple[ModuleTextureReplacementDraft, ...]
    issues: tuple[ModuleTexturePatchIssue, ...] = ()
    status: str = "patched_module_export"
    archive_bytes_modified: bool = True
    patched_resources: tuple[str, ...] = ()
    bundled_resources: tuple[str, ...] = ()

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    @property
    def ready(self) -> bool:
        return bool(self.drafts) and not self.has_errors

    def to_manifest(self, *, generated_at: str | None = None) -> dict[str, Any]:
        return {
            "schema": "ghostrigger.stock_module_texture_patch_plan.v1",
            "generated_at": generated_at or _utc_now(),
            "status": self.status,
            "archive_bytes_modified": self.archive_bytes_modified,
            "source_module": self.source_module,
            "output_module": self.output_module,
            "note": (
                "Exported module archive was rebuilt from the source archive with only the listed MDL "
                "texture-reference fields patched; untouched resource payloads were preserved."
            ),
            "patched_resources": list(self.patched_resources),
            "bundled_resources": list(self.bundled_resources),
            "drafts": [_draft_to_manifest(draft) for draft in self.drafts],
            "issues": [
                {"severity": issue.severity, "code": issue.code, "message": issue.message}
                for issue in self.issues
            ],
        }


@dataclass(frozen=True)
class ModuleTexturePatchPreflight:
    draft_count: int
    patched_resources: tuple[str, ...] = ()
    bundled_resources: tuple[str, ...] = ()
    archive_action: str = "copied_module_export"
    source_preserved: bool = True

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
    def source_summary(self) -> str:
        return "source module preserved; copied export receives changes"


@dataclass(frozen=True)
class ModuleTexturePatchExportResult:
    plan: ModuleTexturePatchPlan
    output_module: str
    manifest_path: str
    source_sha256: str
    output_sha256: str
    copied_bytes: int
    patch_results: tuple[ModuleMDLTexturePatchResult, ...] = ()

    @property
    def ok(self) -> bool:
        return bool(self.patch_results) and self.source_sha256 != self.output_sha256 and not self.plan.has_errors


def build_texture_patch_plan(
    source_module: str | Path,
    output_module: str | Path,
    drafts: Iterable[ModuleTextureReplacementDraft],
) -> ModuleTexturePatchPlan:
    """Validate pending material-slot replacements before any export action."""

    source = Path(source_module)
    output = Path(output_module)
    draft_tuple = tuple(drafts)
    issues: list[ModuleTexturePatchIssue] = []
    if not draft_tuple:
        issues.append(ModuleTexturePatchIssue("error", "no_drafts", "No texture replacements are pending."))
    if source.resolve() == output.resolve():
        issues.append(
            ModuleTexturePatchIssue(
                "error",
                "source_overwrite_refused",
                "Export target must be a new file; the source module will not be overwritten.",
            )
        )
    for index, draft in enumerate(draft_tuple, start=1):
        issues.extend(_validate_draft(draft, index))
    existing_resources = None
    if source.exists():
        try:
            existing_resources = read_module_archive_resources(source)
        except Exception:
            existing_resources = None
    issues.extend(_validate_source_patch_targets(source, draft_tuple, existing_resources))
    preflight = summarize_texture_patch_preflight(draft_tuple, existing_resources=existing_resources)
    return ModuleTexturePatchPlan(
        source_module=str(source),
        output_module=str(output),
        drafts=draft_tuple,
        issues=tuple(issues),
        patched_resources=preflight.patched_resources,
        bundled_resources=preflight.bundled_resources,
    )


def summarize_texture_patch_preflight(
    drafts: Iterable[ModuleTextureReplacementDraft],
    *,
    existing_resources: Iterable[ModuleArchiveResource] | None = None,
) -> ModuleTexturePatchPreflight:
    """Describe what a copied module export would patch or bundle."""

    draft_tuple = tuple(drafts)
    existing_keys = {
        (resource.resref.lower(), resource.restype.lower())
        for resource in (existing_resources or ())
    }
    patched_resource_labels: list[str] = []
    bundled_resource_labels: list[str] = []
    seen_keys = set(existing_keys)
    for draft in draft_tuple:
        patched_label = f"{draft.target.room_resref.lower()}.mdl"
        if patched_label not in patched_resource_labels:
            patched_resource_labels.append(patched_label)
        replacement_key = (draft.replacement_texture_resref.lower(), draft.replacement_format.lower())
        if draft.replacement_payload and replacement_key not in seen_keys:
            seen_keys.add(replacement_key)
            bundled_resource_labels.append(f"{replacement_key[0]}.{replacement_key[1]}")
        for sidecar in draft.replacement_sidecars:
            sidecar_key = (sidecar.resref.lower(), sidecar.restype.lower())
            if sidecar.payload and sidecar_key not in seen_keys:
                seen_keys.add(sidecar_key)
                bundled_resource_labels.append(f"{sidecar_key[0]}.{sidecar_key[1]}")
    return ModuleTexturePatchPreflight(
        draft_count=len(draft_tuple),
        patched_resources=tuple(patched_resource_labels),
        bundled_resources=tuple(bundled_resource_labels),
    )


def write_texture_patch_export_copy(
    source_module: str | Path,
    output_module: str | Path,
    drafts: Iterable[ModuleTextureReplacementDraft],
    *,
    manifest_path: str | Path | None = None,
) -> ModuleTexturePatchExportResult:
    """Export a rebuilt module archive with surgical MDL texture patches."""

    source = Path(source_module)
    output = Path(output_module)
    plan = build_texture_patch_plan(source, output, drafts)
    if plan.has_errors:
        messages = "; ".join(issue.message for issue in plan.issues if issue.severity == "error")
        raise ValueError(messages or "Texture patch plan is not exportable.")
    if not source.exists():
        raise FileNotFoundError(f"Source module does not exist: {source}")

    resources = read_module_archive_resources(source)
    payload_by_key = {
        (resource.resref.lower(), resource.restype.lower()): read_module_resource_bytes(source, resource)
        for resource in resources
    }
    patch_results: list[ModuleMDLTexturePatchResult] = []
    patched_resource_labels: list[str] = []
    bundled_resource_labels: list[str] = []
    for draft in plan.drafts:
        key = (draft.target.room_resref.lower(), "mdl")
        mdl_bytes = payload_by_key.get(key)
        if mdl_bytes is None:
            raise ValueError(f"Target room model {draft.target.room_resref}.mdl is not in the source archive.")
        patched_bytes, patch_result = patch_room_mdl_texture_reference(mdl_bytes, draft)
        payload_by_key[key] = patched_bytes
        patch_results.append(patch_result)
        label = f"{key[0]}.{key[1]}"
        if label not in patched_resource_labels:
            patched_resource_labels.append(label)
        bundled_key = (draft.replacement_texture_resref.lower(), draft.replacement_format.lower())
        if bundled_key not in payload_by_key and draft.replacement_payload:
            payload_by_key[bundled_key] = draft.replacement_payload
            bundled_label = f"{bundled_key[0]}.{bundled_key[1]}"
            if bundled_label not in bundled_resource_labels:
                bundled_resource_labels.append(bundled_label)
        for sidecar in draft.replacement_sidecars:
            sidecar_key = (sidecar.resref.lower(), sidecar.restype.lower())
            if sidecar_key in payload_by_key or not sidecar.payload:
                continue
            payload_by_key[sidecar_key] = sidecar.payload
            sidecar_label = f"{sidecar_key[0]}.{sidecar_key[1]}"
            if sidecar_label not in bundled_resource_labels:
                bundled_resource_labels.append(sidecar_label)

    patched_plan = ModuleTexturePatchPlan(
        source_module=plan.source_module,
        output_module=plan.output_module,
        drafts=plan.drafts,
        issues=plan.issues,
        status=plan.status,
        archive_bytes_modified=True,
        patched_resources=tuple(patched_resource_labels),
        bundled_resources=tuple(bundled_resource_labels),
    )
    archive_type = _source_archive_type(source)
    entries = [
        ModuleArchiveEntry(
            resref=resource.resref,
            restype=resource.restype,
            data=payload_by_key[(resource.resref.lower(), resource.restype.lower())],
            source="patched_mdl_texture_reference"
            if f"{resource.resref.lower()}.{resource.restype.lower()}" in patched_resource_labels
            else "preserved_source_resource",
            changed=f"{resource.resref.lower()}.{resource.restype.lower()}" in patched_resource_labels,
            serializer="fixed_mdl_texture_field"
            if f"{resource.resref.lower()}.{resource.restype.lower()}" in patched_resource_labels
            else "preserved_binary",
        )
        for resource in resources
    ]
    for label in bundled_resource_labels:
        resref, restype = label.rsplit(".", 1)
        entries.append(
            ModuleArchiveEntry(
                resref=resref,
                restype=restype,
                data=payload_by_key[(resref, restype)],
                source="bundled_replacement_texture",
                changed=True,
                serializer="copied_texture_payload",
            )
        )
    archive_bytes = build_erf_v1_archive(entries, archive_type=archive_type)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(archive_bytes)
    source_bytes = source.read_bytes()
    output_bytes = output.read_bytes()
    resolved_manifest = Path(manifest_path) if manifest_path is not None else _default_manifest_path(output)
    resolved_manifest.write_text(
        json.dumps(patched_plan.to_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return ModuleTexturePatchExportResult(
        plan=patched_plan,
        output_module=str(output),
        manifest_path=str(resolved_manifest),
        source_sha256=_sha256(source_bytes),
        output_sha256=_sha256(output_bytes),
        copied_bytes=len(output_bytes),
        patch_results=tuple(patch_results),
    )


def _validate_draft(draft: ModuleTextureReplacementDraft, index: int) -> tuple[ModuleTexturePatchIssue, ...]:
    issues: list[ModuleTexturePatchIssue] = []
    replacement = str(draft.replacement_texture_resref or "").strip()
    original = str(draft.original_texture_resref or "").strip()
    if draft.status != "preview_only":
        issues.append(_draft_error(index, "unsupported_status", f"Unsupported draft status {draft.status!r}."))
    if draft.target.slot_kind != "diffuse":
        issues.append(_draft_error(index, "unsupported_slot", "Only diffuse material-slot replacements are exportable."))
    if draft.replacement_format not in {"tga", "tpc"}:
        issues.append(_draft_error(index, "unsupported_texture_format", "Replacement texture must be TGA or TPC."))
    if not replacement:
        issues.append(_draft_error(index, "missing_replacement", "Replacement texture resref is empty."))
    elif len(replacement) > 16:
        issues.append(_draft_error(index, "replacement_resref_too_long", "Replacement texture resref exceeds 16 characters."))
    elif not _is_ascii_resource_name(replacement):
        issues.append(_draft_error(index, "replacement_resref_not_ascii", "Replacement texture resref must be ASCII."))
    if not original:
        issues.append(_draft_error(index, "missing_original", "Target material slot has no original texture resref."))
    elif original == replacement:
        issues.append(_draft_error(index, "same_texture", "Replacement texture is already assigned to this slot."))
    if not str(draft.target.room_resref or "").strip():
        issues.append(_draft_error(index, "missing_room", "Target room model resref is empty."))
    if not str(draft.target.node_name or "").strip():
        issues.append(_draft_error(index, "missing_node", "Target mesh node name is empty."))
    return tuple(issues)


def _validate_source_patch_targets(
    source: Path,
    drafts: tuple[ModuleTextureReplacementDraft, ...],
    existing_resources: Iterable[ModuleArchiveResource] | None,
) -> tuple[ModuleTexturePatchIssue, ...]:
    if not drafts or existing_resources is None:
        return ()
    resources = tuple(existing_resources)
    payload_cache: dict[tuple[str, str], bytes] = {}
    resource_by_key = {
        (resource.resref.lower(), resource.restype.lower()): resource
        for resource in resources
    }
    issues: list[ModuleTexturePatchIssue] = []
    for index, draft in enumerate(drafts, start=1):
        key = (draft.target.room_resref.lower(), "mdl")
        resource = resource_by_key.get(key)
        if resource is None:
            issues.append(_draft_error(index, "target_room_missing", f"Target room model {draft.target.room_resref}.mdl is not in the source archive."))
            continue
        try:
            mdl_bytes = payload_cache.setdefault(key, read_module_resource_bytes(source, resource))
            patch_room_mdl_texture_reference(mdl_bytes, draft)
        except Exception as exc:
            issues.append(_draft_error(index, "target_texture_field_unpatchable", str(exc)))
    return tuple(issues)


def _draft_error(index: int, code: str, message: str) -> ModuleTexturePatchIssue:
    return ModuleTexturePatchIssue("error", code, f"Draft {index}: {message}")


def _is_ascii_resource_name(value: str) -> bool:
    try:
        value.encode("ascii")
    except UnicodeEncodeError:
        return False
    return all(character.isalnum() or character == "_" for character in value)


def _draft_to_manifest(draft: ModuleTextureReplacementDraft) -> dict[str, Any]:
    target = draft.target
    return {
        "room_resref": target.room_resref,
        "node_name": target.node_name,
        "slot_kind": target.slot_kind,
        "editable_scope": target.editable_scope,
        "face_count": target.face_count,
        "vertex_count": target.vertex_count,
        "original_texture_resref": draft.original_texture_resref,
        "replacement_texture_resref": draft.replacement_texture_resref,
        "replacement_source_label": draft.replacement_source_label,
        "replacement_format": draft.replacement_format,
        "replacement_payload_bundled": bool(draft.replacement_payload),
        "replacement_payload_size": len(draft.replacement_payload),
        "replacement_sidecars": [
            {
                "resource": sidecar.label,
                "source_label": sidecar.source_label,
                "payload_bundled": bool(sidecar.payload),
                "payload_size": len(sidecar.payload),
            }
            for sidecar in draft.replacement_sidecars
        ],
        "status": draft.status,
        "summary": draft.summary,
    }


def _default_manifest_path(output: Path) -> Path:
    return output.with_name(output.name + ".ghostrigger_texture_patch_plan.json")


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
    "ModuleTexturePatchExportResult",
    "ModuleTexturePatchIssue",
    "ModuleTexturePatchPlan",
    "ModuleTexturePatchPreflight",
    "build_texture_patch_plan",
    "summarize_texture_patch_preflight",
    "write_texture_patch_export_copy",
]
