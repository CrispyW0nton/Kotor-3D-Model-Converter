"""Module Editor save/package pipeline.

T1504 turns hydrated module resources into deterministic output archives with a
changed-resource manifest and backup-before-overwrite behavior.  The pipeline is
deliberately conservative: resources with known writers (LYT/VIS/WOK and any
object exposing ``to_bytes``) are serialized, unchanged resources are preserved
byte-for-byte, and dirty GFF resources without replacement bytes are reported as
blocking issues instead of silently writing stale game data.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional


CORE_RESTYPES = {"are", "git", "ifo", "lyt", "vis", "wok", "dwk", "pwk", "pth"}
KOTOR_SAFE_ERF_BUILD_YEAR = 106
KOTOR_SAFE_ERF_BUILD_DAY = 364
STATIC_RESTYPES = {
    "utc",
    "utd",
    "utp",
    "uti",
    "utt",
    "uts",
    "ute",
    "utm",
    "utw",
    "ncs",
    "nss",
    "dlg",
}
GFF_RESTYPES = {
    "are",
    "git",
    "ifo",
    "utc",
    "utd",
    "utp",
    "uti",
    "utt",
    "uts",
    "ute",
    "utm",
    "utw",
    "dlg",
    "jrl",
}


RESTYPE_IDS: dict[str, int] = {
    "bmp": 1,
    "tga": 3,
    "tpc": 3007,
    "wav": 4,
    "plt": 6,
    "ini": 7,
    "txt": 10,
    "mdl": 2002,
    "thg": 2003,
    "nss": 2009,
    "ncs": 2010,
    "mod": 2011,
    "are": 2012,
    "set": 2013,
    "ifo": 2014,
    "bic": 2015,
    "wok": 2016,
    "2da": 2017,
    "tlk": 2018,
    "txi": 2022,
    "git": 2023,
    "uti": 2025,
    "utc": 2027,
    "dlg": 2029,
    "itp": 2030,
    "utt": 2032,
    "dds": 2033,
    "uts": 2035,
    "ltr": 2036,
    "gff": 2037,
    "fac": 2038,
    "ute": 2040,
    "utd": 2042,
    "utp": 2044,
    "dft": 2045,
    "gic": 2046,
    "gui": 2047,
    "utm": 2051,
    "dwk": 2052,
    "pwk": 2053,
    "jrl": 2056,
    "sav": 2057,
    "utw": 2058,
    "ssf": 2060,
    "hak": 2061,
    "nwm": 2062,
    "bik": 2063,
    "ndb": 2064,
    "ptm": 2065,
    "ptt": 2066,
    "lyt": 3000,
    "vis": 3001,
    "rim": 3001,
    "pth": 3003,
    "mdx": 3008,
}


@dataclass(frozen=True)
class ModuleSaveRequest:
    """Save/package options for a hydrated KOTOR module."""

    module_root: str
    game: str = "K1"
    output_dir: str = ""
    archive_mode: str = "auto"  # auto, k1_split, mod
    create_backups: bool = True
    write_manifest: bool = True
    dirty_resources: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ModuleReplacementResource:
    """Explicit replacement bytes for a resource without an in-tree writer."""

    resref: str
    restype: str
    data: bytes
    source: str = "replacement"

    @property
    def key(self) -> tuple[str, str]:
        return (self.resref.lower(), self.restype.lower().lstrip("."))


@dataclass(frozen=True)
class ModuleArchiveEntry:
    """One serialized resource destined for a MOD/RIM archive."""

    resref: str
    restype: str
    data: bytes
    archive_role: str = "core"
    source: str = ""
    changed: bool = False
    serializer: str = "preserved_binary"
    warning: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return (self.resref.lower(), self.restype.lower().lstrip("."))


@dataclass
class ModuleArchiveResult:
    """One generated module archive."""

    path: str = ""
    archive_type: str = ""
    resource_count: int = 0
    backup_path: str = ""
    size: int = 0
    resources: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class ModuleSaveManifest:
    """JSON-serializable save manifest for the Module Editor."""

    module_root: str
    game: str
    generated_at: str
    archive_mode: str
    archives: list[dict[str, Any]] = field(default_factory=list)
    resources: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_root": self.module_root,
            "game": self.game,
            "generated_at": self.generated_at,
            "archive_mode": self.archive_mode,
            "archives": self.archives,
            "resources": self.resources,
            "warnings": self.warnings,
            "blocking_issues": self.blocking_issues,
        }


@dataclass
class ModuleSaveResult:
    """Result of saving a hydrated module."""

    ok: bool = False
    archives: list[ModuleArchiveResult] = field(default_factory=list)
    manifest_path: str = ""
    manifest: Optional[ModuleSaveManifest] = None
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    message: str = ""
    code: str = "not_saved"


def _normalise_key(key: Any) -> tuple[str, str]:
    if isinstance(key, str):
        stem, _, ext = key.lower().rpartition(".")
        return (stem, ext.lstrip("."))
    if isinstance(key, tuple) and len(key) >= 2:
        return (str(key[0]).lower(), str(key[1]).lower().lstrip("."))
    record = getattr(key, "record", key)
    return (
        str(getattr(record, "resref", "") or "").lower(),
        str(getattr(record, "restype", getattr(record, "type", "")) or "").lower().lstrip("."),
    )


def _record_key(resource: Any) -> tuple[str, str]:
    record = getattr(resource, "record", resource)
    return (
        str(getattr(record, "resref", "") or "").lower(),
        str(getattr(record, "restype", getattr(record, "type", "")) or "").lower().lstrip("."),
    )


def _record_source(resource: Any) -> str:
    record = getattr(resource, "record", resource)
    return str(getattr(record, "source", "") or "")


def _resource_data(resource: Any) -> bytes:
    if isinstance(resource, (bytes, bytearray, memoryview)):
        return bytes(resource)
    return bytes(getattr(resource, "data", b"") or b"")


def _resource_parsed(resource: Any) -> Any:
    return getattr(resource, "parsed", None)


def _module_from_input(value: Any) -> Any:
    return getattr(value, "module", value)


def _resources_from_input(module_like: Any) -> dict[tuple[str, str], Any]:
    resources = getattr(module_like, "resources", {}) or {}
    if isinstance(resources, dict):
        out: dict[tuple[str, str], Any] = {}
        for key, value in resources.items():
            normalised = _normalise_key(key)
            if normalised != ("", ""):
                out[normalised] = value
        return out
    return {}


def _parsed_from_module(module_like: Any, key: tuple[str, str], resource: Any) -> Any:
    parsed = _resource_parsed(resource)
    if parsed is not None:
        return parsed

    module = _module_from_input(module_like)
    resref, restype = key
    if restype == "lyt":
        return getattr(module, "lyt", None)
    if restype == "vis":
        return getattr(module, "vis", None)
    if restype in {"wok", "dwk", "pwk"}:
        room_woks = getattr(module, "room_woks", {}) or {}
        if isinstance(room_woks, dict) and resref in room_woks:
            return room_woks[resref]
        return getattr(module, "wok", None)
    if restype == "are":
        return getattr(module, "are", None)
    if restype == "git":
        return getattr(module, "git", None)
    if restype == "ifo":
        return getattr(module, "ifo", None)
    return None


def _serialize_parsed(parsed: Any, restype: str) -> tuple[bytes, str]:
    if parsed is None:
        return b"", ""
    if restype in {"lyt", "vis"} and hasattr(parsed, "to_text"):
        return parsed.to_text().encode("latin-1", errors="replace"), f"{restype}.to_text"
    if restype in {"wok", "dwk", "pwk"} and hasattr(parsed, "to_bytes"):
        return bytes(parsed.to_bytes()), f"{restype}.to_bytes"
    if hasattr(parsed, "to_bytes"):
        return bytes(parsed.to_bytes()), f"{type(parsed).__name__}.to_bytes"
    return b"", ""


def _archive_role(restype: str) -> str:
    if restype in STATIC_RESTYPES:
        return "static"
    return "core"


def _target_archive_name(request: ModuleSaveRequest, role: str) -> tuple[str, str]:
    mode = request.archive_mode.lower()
    game = request.game.upper()
    root = request.module_root.lower()
    if mode == "mod" or game == "K2":
        return (f"{root}.mod", "MOD")
    if mode == "k1_split" or mode == "auto":
        if role == "static":
            return (f"{root}_s.rim", "RIM")
        return (f"{root}.rim", "RIM")
    raise ValueError(f"Unsupported module archive mode: {request.archive_mode}")


def _replacement_index(replacements: Iterable[ModuleReplacementResource] | None) -> dict[tuple[str, str], ModuleReplacementResource]:
    out: dict[tuple[str, str], ModuleReplacementResource] = {}
    for replacement in list(replacements or []):
        out[replacement.key] = replacement
    return out


def collect_module_archive_entries(
    module_like: Any,
    request: ModuleSaveRequest,
    *,
    replacements: Iterable[ModuleReplacementResource] | None = None,
) -> tuple[list[ModuleArchiveEntry], list[str], list[str]]:
    """Serialize all hydrated resources into archive entries and diagnostics."""

    resources = _resources_from_input(module_like)
    replacement_by_key = _replacement_index(replacements)
    dirty_keys = {_normalise_key(key) for key in request.dirty_resources}
    all_keys = sorted(set(resources) | set(replacement_by_key))
    entries: list[ModuleArchiveEntry] = []
    warnings: list[str] = []
    blocking: list[str] = []

    for key in all_keys:
        resref, restype = key
        if not resref or not restype:
            continue
        replacement = replacement_by_key.get(key)
        resource = resources.get(key)
        original = _resource_data(resource) if resource is not None else b""
        source = replacement.source if replacement is not None else _record_source(resource)

        if replacement is not None:
            data = bytes(replacement.data)
            serializer = "replacement_bytes"
            changed = data != original
            warning = ""
        else:
            parsed = _parsed_from_module(module_like, key, resource)
            data, serializer = _serialize_parsed(parsed, restype)
            warning = ""
            if not serializer:
                data = original
                serializer = "preserved_binary"
                if key in dirty_keys and restype in GFF_RESTYPES:
                    warning = (
                        f"{resref}.{restype} is marked dirty but no GFF writer/replacement bytes are available; "
                        "the original binary will be preserved."
                    )
                    blocking.append(warning)
                elif key in dirty_keys:
                    warning = (
                        f"{resref}.{restype} is marked dirty but no serializer is available; "
                        "the original binary will be preserved."
                    )
                    blocking.append(warning)
            changed = data != original

        if not data and original:
            data = original
            serializer = "preserved_binary"
            changed = False
        if not data:
            warning = warning or f"{resref}.{restype} has no bytes to write and will be skipped."
            warnings.append(warning)
            continue
        if warning and warning not in warnings:
            warnings.append(warning)

        entries.append(
            ModuleArchiveEntry(
                resref=resref,
                restype=restype,
                data=data,
                archive_role=_archive_role(restype),
                source=source,
                changed=changed,
                serializer=serializer,
                warning=warning,
            )
        )

    return entries, warnings, blocking


def _res_type_id(restype: str) -> int:
    return RESTYPE_IDS.get(restype.lower().lstrip("."), 0)


def _archive_signature(archive_type: str) -> bytes:
    sig = archive_type.upper().encode("ascii", errors="replace")[:3].ljust(4, b" ")
    if sig[:3] not in {b"ERF", b"MOD", b"RIM", b"SAV"}:
        raise ValueError(f"Unsupported archive type {archive_type!r}")
    return sig


def build_erf_v1_archive(entries: Iterable[ModuleArchiveEntry], archive_type: str = "MOD") -> bytes:
    """Build an ERF V1.0-compatible archive blob from serialized resources."""

    ordered = sorted(entries, key=lambda entry: (entry.resref, entry.restype))
    count = len(ordered)
    header_size = 160
    keylist_off = header_size
    reslist_off = keylist_off + count * 24
    data_off = reslist_off + count * 8

    key_table = bytearray()
    res_table = bytearray()
    payload = bytearray()
    for index, entry in enumerate(ordered):
        resref_raw = entry.resref.lower().encode("ascii", errors="replace")[:16]
        key_table.extend(resref_raw.ljust(16, b"\x00"))
        key_table.extend(struct.pack("<IHH", index, _res_type_id(entry.restype), 0))
        offset = data_off + len(payload)
        res_table.extend(struct.pack("<II", offset, len(entry.data)))
        payload.extend(entry.data)

    header = bytearray(header_size)
    header[0:4] = _archive_signature(archive_type)
    header[4:8] = b"V1.0"
    struct.pack_into("<I", header, 8, 0)  # language count
    struct.pack_into("<I", header, 12, 0)  # localized string size
    struct.pack_into("<I", header, 16, count)
    # Stock KotOR MOD archives set this to the end of the 160-byte header even
    # when the localized string table is empty.  PyKotor accepts 0 here, but the
    # game loader is stricter during module handoff.
    struct.pack_into("<I", header, 20, header_size)  # localized string offset
    struct.pack_into("<I", header, 24, keylist_off)
    struct.pack_into("<I", header, 28, reslist_off)
    # Keep these deterministic but nonzero.  The game accepts stock MOD files
    # with ERF build metadata populated, while zeroed fields are suspicious
    # during custom module handoff even though offline readers tolerate them.
    struct.pack_into("<I", header, 32, KOTOR_SAFE_ERF_BUILD_YEAR)
    struct.pack_into("<I", header, 36, KOTOR_SAFE_ERF_BUILD_DAY)
    struct.pack_into("<I", header, 40, 0xFFFFFFFF)  # description strref
    return bytes(header + key_table + res_table + payload)


def _next_backup_path(path: Path) -> Path:
    candidate = path.with_suffix(path.suffix + ".bak")
    if not candidate.exists():
        return candidate
    for index in range(1, 1000):
        candidate = path.with_suffix(path.suffix + f".bak{index}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find available backup name for {path}")


def _write_archive(path: Path, archive_type: str, entries: list[ModuleArchiveEntry], create_backup: bool) -> ModuleArchiveResult:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = ""
    if create_backup and path.exists():
        backup = _next_backup_path(path)
        shutil.copy2(path, backup)
        backup_path = str(backup)
    data = build_erf_v1_archive(entries, archive_type)
    path.write_bytes(data)
    return ModuleArchiveResult(
        path=str(path),
        archive_type=archive_type,
        resource_count=len(entries),
        backup_path=backup_path,
        size=len(data),
        resources=[entry.key for entry in sorted(entries, key=lambda item: item.key)],
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest_resource(entry: ModuleArchiveEntry, archive_name: str) -> dict[str, Any]:
    return {
        "resref": entry.resref,
        "restype": entry.restype,
        "archive": archive_name,
        "source": entry.source,
        "size": len(entry.data),
        "sha256": _sha256(entry.data),
        "changed": entry.changed,
        "serializer": entry.serializer,
        "warning": entry.warning,
    }


def _build_manifest(
    request: ModuleSaveRequest,
    entries_by_archive: dict[tuple[str, str], list[ModuleArchiveEntry]],
    archives: list[ModuleArchiveResult],
    warnings: list[str],
    blocking: list[str],
    generated_at: str,
) -> ModuleSaveManifest:
    archive_dicts = [
        {
            "path": archive.path,
            "archive_type": archive.archive_type,
            "resource_count": archive.resource_count,
            "backup_path": archive.backup_path,
            "size": archive.size,
        }
        for archive in archives
    ]
    resource_rows: list[dict[str, Any]] = []
    for (archive_name, _archive_type), entries in sorted(entries_by_archive.items()):
        for entry in sorted(entries, key=lambda item: item.key):
            resource_rows.append(_manifest_resource(entry, archive_name))
    return ModuleSaveManifest(
        module_root=request.module_root,
        game=request.game.upper(),
        generated_at=generated_at,
        archive_mode=request.archive_mode,
        archives=archive_dicts,
        resources=resource_rows,
        warnings=warnings,
        blocking_issues=blocking,
    )


def save_module_package(
    module_like: Any,
    request: ModuleSaveRequest,
    *,
    replacements: Iterable[ModuleReplacementResource] | None = None,
    now: Optional[datetime] = None,
) -> ModuleSaveResult:
    """Write module archives plus a changed-resource manifest."""

    out_dir = Path(request.output_dir or ".")
    generated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        entries, warnings, blocking = collect_module_archive_entries(module_like, request, replacements=replacements)
    except Exception as exc:
        return ModuleSaveResult(
            warnings=[str(exc)],
            blocking_issues=[str(exc)],
            message=f"Module save setup failed: {exc}",
            code="setup_failed",
        )

    if not entries:
        return ModuleSaveResult(
            warnings=warnings,
            blocking_issues=blocking,
            message="No module resources were available to save.",
            code="no_resources",
        )

    entries_by_archive: dict[tuple[str, str], list[ModuleArchiveEntry]] = {}
    try:
        for entry in entries:
            archive_name, archive_type = _target_archive_name(request, entry.archive_role)
            entries_by_archive.setdefault((archive_name, archive_type), []).append(entry)
    except Exception as exc:
        return ModuleSaveResult(
            warnings=warnings + [str(exc)],
            blocking_issues=blocking + [str(exc)],
            message=f"Module save target selection failed: {exc}",
            code="target_failed",
        )

    archives: list[ModuleArchiveResult] = []
    try:
        for (archive_name, archive_type), archive_entries in sorted(entries_by_archive.items()):
            archives.append(_write_archive(out_dir / archive_name, archive_type, archive_entries, request.create_backups))
    except Exception as exc:
        return ModuleSaveResult(
            archives=archives,
            warnings=warnings + [str(exc)],
            blocking_issues=blocking + [str(exc)],
            message=f"Module archive write failed: {exc}",
            code="write_failed",
        )

    manifest = _build_manifest(request, entries_by_archive, archives, warnings, blocking, generated_at)
    manifest_path = ""
    if request.write_manifest:
        manifest_file = out_dir / f"{request.module_root.lower()}_save_manifest.json"
        manifest_file.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest_path = str(manifest_file)

    ok = bool(archives) and not blocking
    return ModuleSaveResult(
        ok=ok,
        archives=archives,
        manifest_path=manifest_path,
        manifest=manifest,
        warnings=warnings,
        blocking_issues=blocking,
        message=(
            f"Saved {len(archives)} module archive(s)."
            if ok
            else f"Saved {len(archives)} archive(s), but blocking save issues remain."
        ),
        code="saved" if ok else "saved_with_blockers",
    )


__all__ = [
    "ModuleSaveRequest",
    "ModuleReplacementResource",
    "ModuleArchiveEntry",
    "ModuleArchiveResult",
    "ModuleSaveManifest",
    "ModuleSaveResult",
    "RESTYPE_IDS",
    "collect_module_archive_entries",
    "build_erf_v1_archive",
    "save_module_package",
]
