"""Map Builder custom module pack/export service.

T1605 turns authored Map Builder state into an install-safe package: a playable
``install/Modules/<module>.mod`` plus loose source resources and a manifest a
modder can inspect before copying anything into Override or Modules.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, Iterable, Optional


CORE_PACKAGE_RESTYPES = {"are", "git", "ifo", "lyt", "vis", "wok"}
ROOM_MODEL_RESTYPES = {"mdl", "mdx"}


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
    resources_dir: str = ""
    manifest_path: str = ""
    staged_resources: list[StagedResourceResult] = field(default_factory=list)
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

    resource_list = list(resources or [])
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
    install_modules_dir = output_root / "install" / "Modules"
    resources_dir = output_root / "source" / "resources"
    manifest_path = output_root / f"{root}_pack_manifest.json"

    if blocking and request.strict:
        result = CustomModulePackResult(
            modules_dir=str(install_modules_dir),
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
        manifest_path.write_text(json.dumps(_manifest_dict(request, result, generated_at), indent=2), encoding="utf-8")
        return result

    save_request = sp.ModuleSaveRequest(
        module_root=root,
        game=request.game,
        output_dir=str(install_modules_dir),
        archive_mode=request.archive_mode,
        create_backups=request.create_backups,
        write_manifest=True,
    )
    save_result = sp.save_module_package(module_like, save_request, replacements=replacements, now=now)
    save_blocking = list(getattr(save_result, "blocking_issues", []) or [])
    save_warnings = list(getattr(save_result, "warnings", []) or [])
    warnings.extend(item for item in save_warnings if item not in warnings)
    blocking.extend(item for item in save_blocking if item not in blocking)
    archives = list(getattr(save_result, "archives", []) or [])
    module_path = str(archives[0].path) if archives else ""

    staged: list[StagedResourceResult] = []
    if request.write_loose_resources:
        entries, entry_warnings, entry_blocking = sp.collect_module_archive_entries(
            module_like,
            save_request,
            replacements=replacements,
        )
        warnings.extend(item for item in entry_warnings if item not in warnings)
        blocking.extend(item for item in entry_blocking if item not in blocking)
        staged = _stage_loose_resources(entries, resources_dir)

    ok = bool(getattr(save_result, "ok", False)) and (not blocking or not request.strict)
    result = CustomModulePackResult(
        ok=ok,
        save_result=save_result,
        module_path=module_path,
        modules_dir=str(install_modules_dir),
        resources_dir=str(resources_dir),
        manifest_path=str(manifest_path),
        staged_resources=staged,
        warnings=warnings,
        blocking_issues=blocking,
        reference_report=reference_report,
        wok_report=wok_report,
        message=(
            f"Custom module package exported to {module_path}."
            if ok else
            f"Custom module package completed with {len(blocking)} blocking issue(s)."
        ),
        code="packaged" if ok else "packaged_with_blockers",
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(_manifest_dict(request, result, generated_at), indent=2), encoding="utf-8")
    return result


__all__ = [
    "CustomModulePackRequest",
    "CustomModulePackResult",
    "PackagedModuleResource",
    "StagedResourceResult",
    "package_custom_module",
]
