"""Map Builder custom module pack/export service.

T1605 turns authored Map Builder state into an install-safe package: a playable
``install/Modules/<module>.mod`` plus loose source resources and a manifest a
modder can inspect before copying anything into Override or Modules.
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, Iterable, Optional


CORE_PACKAGE_RESTYPES = {"are", "git", "ifo", "lyt", "vis", "wok"}
ROOM_MODEL_RESTYPES = {"mdl", "mdx"}
# Global engine tables are loaded before a module archive is opened.  Keep
# these out of the MOD and stage them in install/Override instead.
GLOBAL_OVERRIDE_RESOURCE_KEYS = {("placeables", "2da")}


@dataclass(frozen=True)
class PackagedModuleResource:
    """Explicit resource bytes to include in a custom module package."""

    resref: str
    restype: str
    data: bytes = b""
    source_path: str = ""
    source: str = "map_builder"
    required: bool = True

    @property
    def key(self) -> tuple[str, str]:
        return (_normalise_resref(self.resref), _normalise_restype(self.restype))


@dataclass(frozen=True)
class CustomModulePackRequest:
    """Options for exporting a custom Map Builder module pack."""

    module_root: str
    game: str = "K1"
    output_dir: str = ""
    archive_mode: str = "mod"
    create_backups: bool = True
    write_loose_resources: bool = True
    include_reference_check: bool = True
    include_wok_check: bool = True
    strict: bool = True


@dataclass(frozen=True)
class StagedResourceResult:
    """One loose resource staged beside the installable module package."""

    resref: str
    restype: str
    path: str
    size: int
    sha256: str
    source: str = ""


@dataclass
class CustomModulePackResult:
    """Result from a custom module pack/export operation."""

    ok: bool = False
    save_result: Any = None
    module_path: str = ""
    modules_dir: str = ""
    override_dir: str = ""
    resources_dir: str = ""
    manifest_path: str = ""
    staged_resources: list[StagedResourceResult] = field(default_factory=list)
    staged_override_resources: list[StagedResourceResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    reference_report: Any = None
    wok_report: Any = None
    message: str = ""
    code: str = "not_packaged"


def _import_module_save_pipeline():
    for name in (
        "src.core.modules.module_save_pipeline",
        "core.modules.module_save_pipeline",
        "core.module_save_pipeline",
        "src.core.module_save_pipeline",
    ):
        try:
            return import_module(name)
        except ImportError:
            continue
    return import_module(".module_save_pipeline", __package__)


def _import_reference_safety():
    for name in (
        "src.core.modules.module_reference_safety",
        "core.modules.module_reference_safety",
        "core.module_reference_safety",
        "src.core.module_reference_safety",
    ):
        try:
            return import_module(name)
        except ImportError:
            continue
    return import_module(".module_reference_safety", __package__)


def _import_area_wok_integration():
    for name in (
        "src.core.modules.area_wok_integration",
        "core.modules.area_wok_integration",
        "core.area_wok_integration",
        "src.core.area_wok_integration",
    ):
        try:
            return import_module(name)
        except ImportError:
            continue
    return import_module(".area_wok_integration", __package__)


def _import_export_job():
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "native").is_dir():
            for rel in (
                "native/GhostRigger.Core.Project/Python",
                "native/GhostRigger.Core.Validation/Python",
                "native/GhostRigger.Core.IO/Python",
            ):
                path = str((parent / rel).resolve())
                if path not in sys.path:
                    sys.path.insert(0, path)
            importlib.invalidate_caches()
            break
    for name in (
        "src.core.export.export_job",
        "core.export.export_job",
    ):
        try:
            return import_module(name)
        except ImportError:
            continue
    return import_module("src.core.export.export_job")


def _normalise_resref(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "." in text:
        text = text.rsplit(".", 1)[0]
    return text[:16]


def _normalise_restype(value: Any) -> str:
    return str(value or "").strip().lower().lstrip(".")


def _module_from_input(value: Any) -> Any:
    return getattr(value, "module", value)


def _resources_from_input(module_like: Any) -> dict[tuple[str, str], Any]:
    resources = getattr(module_like, "resources", {}) or {}
    if not isinstance(resources, dict):
        return {}
    out: dict[tuple[str, str], Any] = {}
    for key, value in resources.items():
        if isinstance(key, tuple) and len(key) >= 2:
            out[(_normalise_resref(key[0]), _normalise_restype(key[1]))] = value
            continue
        if isinstance(key, str):
            stem, _, ext = key.rpartition(".")
            out[(_normalise_resref(stem), _normalise_restype(ext))] = value
            continue
        record = getattr(key, "record", key)
        out[
            (
                _normalise_resref(getattr(record, "resref", "")),
                _normalise_restype(getattr(record, "restype", getattr(record, "type", ""))),
            )
        ] = value
    return {key: value for key, value in out.items() if key != ("", "")}


def _resource_data(resource: Any) -> bytes:
    if isinstance(resource, (bytes, bytearray, memoryview)):
        return bytes(resource)
    return bytes(getattr(resource, "data", b"") or b"")


def _read_packaged_resource(resource: PackagedModuleResource) -> bytes:
    if resource.data:
        return bytes(resource.data)
    if resource.source_path:
        return Path(resource.source_path).read_bytes()
    return b""


def _text_bytes(value: Any) -> bytes:
    if value is None or not hasattr(value, "to_text"):
        return b""
    return str(value.to_text()).encode("latin-1", errors="replace")


def _binary_bytes(value: Any) -> bytes:
    if value is None or not hasattr(value, "to_bytes"):
        return b""
    return bytes(value.to_bytes())


def _replacement(sp: Any, resref: str, restype: str, data: bytes, source: str) -> Any:
    return sp.ModuleReplacementResource(
        _normalise_resref(resref),
        _normalise_restype(restype),
        bytes(data),
        source=source,
    )


def _generated_layout_replacements(module_like: Any, request: CustomModulePackRequest, sp: Any) -> list[Any]:
    module = _module_from_input(module_like)
    replacements: list[Any] = []
    lyt_data = _text_bytes(getattr(module, "lyt", None))
    if lyt_data:
        replacements.append(_replacement(sp, request.module_root, "lyt", lyt_data, "map_builder:lyt"))
    vis_data = _text_bytes(getattr(module, "vis", None))
    if vis_data:
        replacements.append(_replacement(sp, request.module_root, "vis", vis_data, "map_builder:vis"))
    for room_id, wok in sorted((getattr(module, "room_woks", {}) or {}).items()):
        data = _binary_bytes(wok)
        if data:
            replacements.append(_replacement(sp, str(room_id), "wok", data, "map_builder:wok"))
    return replacements


def _explicit_replacements(resources: Iterable[PackagedModuleResource], sp: Any) -> tuple[list[Any], list[str]]:
    replacements: list[Any] = []
    blocking: list[str] = []
    for resource in list(resources or []):
        resref, restype = resource.key
        if not resref or not restype:
            blocking.append("A packaged resource is missing a resref or type.")
            continue
        try:
            data = _read_packaged_resource(resource)
        except OSError as exc:
            blocking.append(f"{resref}.{restype} could not be read: {exc}")
            continue
        if not data and resource.required:
            blocking.append(f"{resref}.{restype} has no bytes to package.")
            continue
        if data:
            source = resource.source or resource.source_path or "map_builder"
            replacements.append(_replacement(sp, resref, restype, data, source))
    return replacements, blocking


def _keys_for_replacements(replacements: Iterable[Any]) -> set[tuple[str, str]]:
    return {(_normalise_resref(item.resref), _normalise_restype(item.restype)) for item in replacements}


def _has_restype(keys: set[tuple[str, str]], restype: str) -> bool:
    target = _normalise_restype(restype)
    return any(key_restype == target for _resref, key_restype in keys)


def _preflight_required_resources(
    module_like: Any,
    replacements: Iterable[Any],
    request: CustomModulePackRequest,
) -> tuple[list[str], list[str]]:
    keys = set(_resources_from_input(module_like)) | _keys_for_replacements(replacements)
    blocking: list[str] = []
    warnings: list[str] = []
    for restype in ("are", "git", "ifo", "lyt", "vis"):
        if not _has_restype(keys, restype):
            blocking.append(f"Custom module package is missing a {restype.upper()} resource.")
    if not _has_restype(keys, "wok"):
        blocking.append("Custom module package is missing room WOK walkmesh resources.")
    if not _has_restype(keys, "mdl"):
        warnings.append("No room MDL resources are staged; the package may rely on base-game room models.")
    if _has_restype(keys, "mdl") and not _has_restype(keys, "mdx"):
        warnings.append("Room MDL resources are staged without matching MDX resources.")
    if request.archive_mode.lower() != "mod":
        warnings.append("Install-safe custom modules should normally export as a single .mod package.")
    return warnings, blocking


def _issue_message(issue: Any) -> str:
    code = str(getattr(issue, "code", "") or "").strip()
    message = str(getattr(issue, "message", issue) or "").strip()
    return f"{code}: {message}" if code and code not in message else message


def _validation_messages(reference_report: Any, wok_report: Any) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    blocking: list[str] = []
    if reference_report is not None:
        for issue in list(getattr(reference_report, "issues", []) or []):
            target = blocking if str(getattr(issue, "severity", "")).lower() == "error" else warnings
            target.append(_issue_message(issue))
    if wok_report is not None:
        for issue in list(getattr(wok_report, "issues", []) or []):
            target = blocking if str(getattr(issue, "severity", "")).lower() == "error" else warnings
            target.append(_issue_message(issue))
    return warnings, blocking


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _next_backup_path(path: Path) -> Path:
    candidate = path.with_suffix(path.suffix + ".bak")
    if not candidate.exists():
        return candidate
    for index in range(1, 1000):
        candidate = path.with_suffix(path.suffix + f".bak{index}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find an available backup path for {path}.")


def _promote_staged_file(staged_path: Path, final_path: Path, *, create_backup: bool) -> str:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = ""
    if final_path.exists():
        if final_path.is_dir():
            raise IsADirectoryError(f"Cannot promote staged file over directory: {final_path}")
        if create_backup:
            backup = _next_backup_path(final_path)
            shutil.copy2(final_path, backup)
            backup_path = str(backup)
        final_path.unlink()
    shutil.move(str(staged_path), str(final_path))
    return backup_path


def _relocated_staged_resource(resource: StagedResourceResult, final_resources_dir: Path) -> StagedResourceResult:
    final_path = final_resources_dir / Path(resource.path).name
    return StagedResourceResult(
        resref=resource.resref,
        restype=resource.restype,
        path=str(final_path),
        size=resource.size,
        sha256=resource.sha256,
        source=resource.source,
    )


def _stage_loose_resources(entries: Iterable[Any], resources_dir: Path) -> list[StagedResourceResult]:
    resources_dir.mkdir(parents=True, exist_ok=True)
    staged: list[StagedResourceResult] = []
    for entry in sorted(entries, key=lambda item: (item.resref, item.restype)):
        path = resources_dir / f"{entry.resref}.{entry.restype}"
        path.write_bytes(entry.data)
        staged.append(
            StagedResourceResult(
                resref=entry.resref,
                restype=entry.restype,
                path=str(path),
                size=len(entry.data),
                sha256=_sha256(entry.data),
                source=str(getattr(entry, "source", "") or ""),
            )
        )
    return staged


def _manifest_dict(
    request: CustomModulePackRequest,
    result: CustomModulePackResult,
    generated_at: str,
    transaction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    save_result = result.save_result
    archives = []
    if save_result is not None:
        archives = [
            {
                "path": archive.path,
                "archive_type": archive.archive_type,
                "resource_count": archive.resource_count,
                "size": archive.size,
            }
            for archive in list(getattr(save_result, "archives", []) or [])
        ]
    return {
        "module_root": _normalise_resref(request.module_root),
        "game": request.game.upper(),
        "generated_at": generated_at,
        "install": {
            "modules_dir": result.modules_dir,
            "module_path": result.module_path,
            "archives": archives,
            "override_dir": result.override_dir,
            "override_resources": [resource.__dict__ for resource in result.staged_override_resources],
        },
        "source": {
            "resources_dir": result.resources_dir,
            "resources": [resource.__dict__ for resource in result.staged_resources],
        },
        "validation": {
            "warnings": result.warnings,
            "blocking_issues": result.blocking_issues,
            "reference_code": str(getattr(result.reference_report, "code", "") or ""),
            "wok_code": str(getattr(result.wok_report, "code", "") or ""),
        },
        "save_manifest_path": str(getattr(save_result, "manifest_path", "") or "") if save_result is not None else "",
        "transaction": dict(transaction or {}),
    }


def package_custom_module(
    module_like: Any,
    request: CustomModulePackRequest,
    *,
    resources: Iterable[PackagedModuleResource] | None = None,
    now: Optional[datetime] = None,
) -> CustomModulePackResult:
    """Build a playable custom module package and author-facing source layout."""

    sp = _import_module_save_pipeline()
    generated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    root = _normalise_resref(request.module_root)
    if not root:
        return CustomModulePackResult(
            blocking_issues=["Custom module export requires a module root."],
            message="Custom module export requires a module root.",
            code="invalid_request",
        )

    all_resources = list(resources or [])
    global_resources = [resource for resource in all_resources if resource.key in GLOBAL_OVERRIDE_RESOURCE_KEYS]
    resource_list = [resource for resource in all_resources if resource.key not in GLOBAL_OVERRIDE_RESOURCE_KEYS]
    archive_module_like = module_like
    module_resources = getattr(module_like, "resources", None)
    if isinstance(module_resources, dict) and any(key in module_resources for key in GLOBAL_OVERRIDE_RESOURCE_KEYS):
        archive_module_like = copy.copy(module_like)
        archive_module_like.resources = {
            key: value for key, value in module_resources.items() if key not in GLOBAL_OVERRIDE_RESOURCE_KEYS
        }
    generated_replacements = _generated_layout_replacements(module_like, request, sp)
    explicit_replacements, explicit_blocking = _explicit_replacements(resource_list, sp)
    replacements = [*generated_replacements, *explicit_replacements]
    warnings, blocking = _preflight_required_resources(module_like, replacements, request)
    blocking.extend(explicit_blocking)

    reference_report = None
    wok_report = None
    if request.include_reference_check:
        reference_report = _import_reference_safety().validate_module_references(
            module_like,
            extra_available=resource_list,
        )
    if request.include_wok_check:
        try:
            wok_report = _import_area_wok_integration().validate_area_woks(module_like)
        except Exception as exc:
            warnings.append(f"Area WOK validation could not run: {exc}")
    validation_warnings, validation_blocking = _validation_messages(reference_report, wok_report)
    warnings.extend(validation_warnings)
    blocking.extend(validation_blocking)

    output_root = Path(request.output_dir or ".")
    output_root.mkdir(parents=True, exist_ok=True)
    install_modules_dir = output_root / "install" / "Modules"
    install_override_dir = output_root / "install" / "Override"
    resources_dir = output_root / "source" / "resources"
    manifest_path = output_root / f"{root}_pack_manifest.json"

    if blocking and request.strict:
        result = CustomModulePackResult(
            modules_dir=str(install_modules_dir),
            override_dir=str(install_override_dir),
            resources_dir=str(resources_dir),
            manifest_path=str(manifest_path),
            warnings=warnings,
            blocking_issues=blocking,
            reference_report=reference_report,
            wok_report=wok_report,
            message=f"Custom module package preflight found {len(blocking)} blocking issue(s).",
            code="preflight_failed",
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                _manifest_dict(
                    request,
                    result,
                    generated_at,
                    {
                        "staged": False,
                        "status": "preflight_failed",
                        "staging_model": "preflight_manifest_only",
                        "blocking_issue_count": len(blocking),
                    },
                ),
                indent=2,
            ),
            encoding="utf-8",
        )
        return result

    staging_root = Path(tempfile.mkdtemp(prefix=f".ghostrigger_pack_{root}_", dir=str(output_root)))
    staging_install_modules_dir = staging_root / "install" / "Modules"
    staging_install_override_dir = staging_root / "install" / "Override"
    staging_resources_dir = staging_root / "source" / "resources"
    staging_manifest_path = staging_root / f"{root}_pack_manifest.json"
    promoted_outputs: list[dict[str, Any]] = []
    export_job_result = None
    transaction: dict[str, Any] = {
        "staged": True,
        "status": "writing",
        "staging_model": "save_pipeline_temp_root_then_export_job_promote",
        "staging_root": str(staging_root),
        "promoted_outputs": promoted_outputs,
    }
    save_request = sp.ModuleSaveRequest(
        module_root=root,
        game=request.game,
        output_dir=str(staging_install_modules_dir),
        archive_mode=request.archive_mode,
        create_backups=False,
        write_manifest=True,
    )
    try:
        save_result = sp.save_module_package(archive_module_like, save_request, replacements=replacements, now=now)
        save_blocking = list(getattr(save_result, "blocking_issues", []) or [])
        save_warnings = list(getattr(save_result, "warnings", []) or [])
        warnings.extend(item for item in save_warnings if item not in warnings)
        blocking.extend(item for item in save_blocking if item not in blocking)
        archives = list(getattr(save_result, "archives", []) or [])

        staged: list[StagedResourceResult] = []
        staged_override: list[StagedResourceResult] = []
        if request.write_loose_resources:
            entries, entry_warnings, entry_blocking = sp.collect_module_archive_entries(
                archive_module_like,
                save_request,
                replacements=replacements,
            )
            warnings.extend(item for item in entry_warnings if item not in warnings)
            blocking.extend(item for item in entry_blocking if item not in blocking)
            staged = _stage_loose_resources(entries, staging_resources_dir)
            if global_resources:
                staged.extend(_stage_loose_resources(global_resources, staging_resources_dir))
        if global_resources:
            staged_override = _stage_loose_resources(global_resources, staging_install_override_dir)

        ok = bool(getattr(save_result, "ok", False)) and (not blocking or not request.strict)
        if not ok:
            transaction["status"] = "failed"
            result = CustomModulePackResult(
                ok=False,
                save_result=save_result,
                module_path=str(archives[0].path) if archives else "",
                modules_dir=str(install_modules_dir),
                override_dir=str(install_override_dir),
                resources_dir=str(resources_dir),
                manifest_path=str(manifest_path),
                staged_resources=staged,
                staged_override_resources=staged_override,
                warnings=warnings,
                blocking_issues=blocking,
                reference_report=reference_report,
                wok_report=wok_report,
                message=f"Custom module package completed with {len(blocking)} blocking issue(s).",
                code="packaged_with_blockers",
            )
            manifest_path.write_text(json.dumps(_manifest_dict(request, result, generated_at, transaction), indent=2), encoding="utf-8")
            return result

        export_artifacts: list[dict[str, Any]] = []
        for archive in archives:
            staged_archive_path = Path(archive.path)
            final_archive_path = install_modules_dir / staged_archive_path.name
            archive.path = str(final_archive_path)
            export_artifacts.append(
                {
                    "artifact_kind": "module_package",
                    "staged_path": str(staged_archive_path),
                    "final_path": str(final_archive_path),
                    "backup_path": "",
                }
            )
        module_path = str(Path(archives[0].path)) if archives else ""

        save_manifest_path = str(getattr(save_result, "manifest_path", "") or "")
        if save_manifest_path:
            staged_save_manifest = Path(save_manifest_path)
            final_save_manifest = install_modules_dir / staged_save_manifest.name
            save_result.manifest_path = str(final_save_manifest)
            export_artifacts.append(
                {
                    "artifact_kind": "save_manifest",
                    "staged_path": str(staged_save_manifest),
                    "final_path": str(final_save_manifest),
                    "backup_path": "",
                }
            )

        final_staged: list[StagedResourceResult] = []
        for resource in staged:
            staged_resource_path = Path(resource.path)
            final_resource = _relocated_staged_resource(resource, resources_dir)
            final_staged.append(final_resource)
            export_artifacts.append(
                {
                    "artifact_kind": "loose_resource",
                    "resref": resource.resref,
                    "restype": resource.restype,
                    "staged_path": str(staged_resource_path),
                    "final_path": final_resource.path,
                    "backup_path": "",
                }
            )

        final_staged_override: list[StagedResourceResult] = []
        for resource in staged_override:
            staged_resource_path = Path(resource.path)
            final_resource = _relocated_staged_resource(resource, install_override_dir)
            final_staged_override.append(final_resource)
            export_artifacts.append(
                {
                    "artifact_kind": "override_resource",
                    "resref": resource.resref,
                    "restype": resource.restype,
                    "staged_path": str(staged_resource_path),
                    "final_path": final_resource.path,
                    "backup_path": "",
                }
            )

        transaction["status"] = "succeeded"
        result = CustomModulePackResult(
            ok=True,
            save_result=save_result,
            module_path=module_path,
            modules_dir=str(install_modules_dir),
            override_dir=str(install_override_dir),
            resources_dir=str(resources_dir),
            manifest_path=str(manifest_path),
            staged_resources=final_staged,
            staged_override_resources=final_staged_override,
            warnings=warnings,
            blocking_issues=blocking,
            reference_report=reference_report,
            wok_report=wok_report,
            message=f"Custom module package exported to {module_path}.",
            code="packaged",
        )
        export_artifacts.append(
            {
                "artifact_kind": "pack_manifest",
                "staged_path": str(staging_manifest_path),
                "final_path": str(manifest_path),
                "backup_path": "",
            }
        )

        for artifact in export_artifacts:
            final_path = Path(artifact["final_path"])
            if final_path.exists() and request.create_backups:
                backup = _next_backup_path(final_path)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(final_path, backup)
                artifact["backup_path"] = str(backup)
            promoted_outputs.append(dict(artifact))
        for archive in archives:
            for artifact in promoted_outputs:
                if artifact["artifact_kind"] == "module_package" and Path(artifact["final_path"]) == Path(archive.path):
                    archive.backup_path = artifact["backup_path"]

        ej = _import_export_job()
        output_specs = [
            ej.ExportOutputSpec(
                Path(artifact["final_path"]),
                "manifest" if artifact["artifact_kind"] == "pack_manifest" else artifact["artifact_kind"],
            )
            for artifact in promoted_outputs
        ]
        export_job_request = ej.ExportJobRequest(
            job_id=f"map_studio.custom_module_package.{root}",
            kind="map_studio.custom_module_package",
            outputs=output_specs,
            overwrite=True,
            staging_root=output_root,
            metadata={
                "module_root": root,
                "game": request.game.upper(),
                "archive_mode": request.archive_mode,
                "artifact_count": len(output_specs),
            },
            validation_bus_source="map_studio.custom_module_packager",
        )
        transaction["export_job"] = {
            "job_id": export_job_request.job_id,
            "kind": export_job_request.kind,
            "status": "succeeded",
            "staged_paths": {},
            "final_paths": [str(spec.final_path) for spec in output_specs],
            "manifest_path": str(manifest_path),
        }

        def _write_export_job_outputs(context: Any) -> None:
            transaction["export_job"]["staged_paths"] = {
                str(final): str(staged_path)
                for final, staged_path in context.output_map.items()
            }
            for artifact in promoted_outputs:
                if artifact["artifact_kind"] == "pack_manifest":
                    continue
                staged_source = Path(artifact["staged_path"])
                staged_target = context.staged_path_for(Path(artifact["final_path"]))
                staged_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(staged_source, staged_target)
            context.write_text(
                manifest_path,
                json.dumps(_manifest_dict(request, result, generated_at, transaction), indent=2),
                encoding="utf-8",
            )

        export_job_result = ej.run_export_job(export_job_request, writer=_write_export_job_outputs)
        if not bool(getattr(export_job_result, "succeeded", False)):
            issues = [
                _issue_message(issue)
                for issue in list(getattr(getattr(export_job_result, "validation_report", None), "issues", []) or [])
            ]
            blocking.extend(issue for issue in issues if issue not in blocking)
            transaction["status"] = "failed"
            transaction["export_job"] = {
                "job_id": getattr(export_job_result, "job_id", export_job_request.job_id),
                "kind": getattr(export_job_result, "kind", export_job_request.kind),
                "status": str(getattr(getattr(export_job_result, "status", ""), "value", getattr(export_job_result, "status", ""))),
                "staged_paths": dict(getattr(export_job_result, "staged_paths", {}) or {}),
                "final_paths": [str(path) for path in list(getattr(export_job_result, "final_paths", []) or [])],
                "manifest_path": str(getattr(export_job_result, "manifest_path", "") or ""),
            }
            result.ok = False
            result.module_path = ""
            result.blocking_issues = blocking
            result.message = "Custom module package ExportJob promotion failed."
            result.code = "export_job_failed"
            manifest_path.write_text(
                json.dumps(_manifest_dict(request, result, generated_at, transaction), indent=2),
                encoding="utf-8",
            )
            return result

        return result
    except Exception as exc:
        blocking.append(f"Custom module package promotion failed: {exc}")
        transaction["status"] = "failed"
        if export_job_result is not None:
            transaction["export_job"] = {
                "job_id": getattr(export_job_result, "job_id", ""),
                "kind": getattr(export_job_result, "kind", ""),
                "status": str(getattr(getattr(export_job_result, "status", ""), "value", getattr(export_job_result, "status", ""))),
                "staged_paths": dict(getattr(export_job_result, "staged_paths", {}) or {}),
                "final_paths": [str(path) for path in list(getattr(export_job_result, "final_paths", []) or [])],
                "manifest_path": str(getattr(export_job_result, "manifest_path", "") or ""),
            }
        result = CustomModulePackResult(
            ok=False,
            save_result=locals().get("save_result"),
            module_path="",
            modules_dir=str(install_modules_dir),
            override_dir=str(install_override_dir),
            resources_dir=str(resources_dir),
            manifest_path=str(manifest_path),
            staged_resources=[],
            warnings=warnings,
            blocking_issues=blocking,
            reference_report=reference_report,
            wok_report=wok_report,
            message=f"Custom module package promotion failed: {exc}",
            code="promotion_failed",
        )
        manifest_path.write_text(json.dumps(_manifest_dict(request, result, generated_at, transaction), indent=2), encoding="utf-8")
        return result
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


__all__ = [
    "CustomModulePackRequest",
    "CustomModulePackResult",
    "PackagedModuleResource",
    "StagedResourceResult",
    "package_custom_module",
]
