"""Portable Custom Head packages and reversible retail-test installation.

This module owns filesystem mutation only.  It stages a read-only preview from
the live game tables, requires confirmation of that exact preview, refuses to
run while the game/launcher is active, writes Override files atomically, and
keeps verified backups for a conflict-aware restore.
"""

from __future__ import annotations

import configparser
import hashlib
import io
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Callable, Iterable, Mapping

from src.io.head_binary_export import HeadBinaryExportResult
from src.io.head_game_records import (
    HEAD_GAME_RECORD_PATCH_SCHEMA,
    HeadGameRecordMergeResult,
    HeadGameRecordPatch,
    load_live_twoda,
    merge_head_game_records,
)
from src.io.head_texture_asset import (
    HeadTextureAsset,
    HeadTextureOutputPolicy,
)


HEAD_PACKAGE_SCHEMA = "ghostrigger.head_builder_package.v1"
HEAD_INSTALL_PLAN_SCHEMA = "ghostrigger.head_builder_install_plan.v1"
HEAD_INSTALL_SESSION_SCHEMA = (
    "ghostrigger.head_builder_install_session.v1"
)
_RUNTIME_SUFFIXES = frozenset(
    {".mdl", ".mdx", ".tga", ".tpc", ".txi", ".utc"}
)


class HeadPackageError(RuntimeError):
    """Raised when package/install work cannot remain source-preserving."""


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_json(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _write_atomic(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as stream:
            temporary = stream.name
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            Path(temporary).unlink(missing_ok=True)


def _safe_package_file(name: str) -> str:
    path = Path(str(name or ""))
    if (
        not path.name
        or path.name != str(name)
        or path.is_absolute()
        or ".." in path.parts
    ):
        raise HeadPackageError(f"Unsafe package filename: {name!r}")
    return path.name


def _write_package_file(
    root: Path,
    relative: str,
    value: bytes,
    written: dict[str, Path],
) -> Path:
    clean = Path(relative)
    if clean.is_absolute() or ".." in clean.parts:
        raise HeadPackageError(f"Unsafe package path: {relative!r}")
    target = (root / clean).resolve()
    if root.resolve() not in target.parents:
        raise HeadPackageError(f"Package path escapes its root: {relative!r}")
    if target.exists() and target.read_bytes() != value:
        raise HeadPackageError(
            f"Package output would overwrite an unrelated file: {relative}"
        )
    _write_atomic(target, value)
    written[clean.as_posix()] = target
    return target


def _read_source_txi(asset: HeadTextureAsset) -> str:
    if not asset.txi_path:
        return ""
    path = Path(asset.txi_path)
    if not path.is_file() or _sha256_file(path) != asset.txi_sha256:
        raise HeadPackageError(
            "Texture TXI source changed after the material contract"
        )
    return path.read_text(encoding="ascii", errors="strict")


def _merge_txi_text(
    source_text: str,
    policy: HeadTextureOutputPolicy,
) -> str:
    """Preserve unknown source lines while explicit UI policy wins by key."""

    explicit = [
        line.strip()
        for line in policy.txi_text().splitlines()
        if line.strip()
    ]
    explicit_keys = {
        line.split(None, 1)[0].casefold()
        for line in explicit
    }
    preserved: list[str] = []
    if policy.preserve_source_txi:
        for raw_line in str(source_text or "").splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("#", ";")):
                continue
            key = line.split(None, 1)[0].casefold()
            if key not in explicit_keys:
                preserved.append(line)
    rows = preserved + explicit
    return ("\n".join(rows) + "\n") if rows else ""


def _texture_outputs(
    asset: HeadTextureAsset,
    policy: HeadTextureOutputPolicy,
) -> dict[str, bytes]:
    source = Path(asset.source_path)
    if not source.is_file() or _sha256_file(source) != asset.source_sha256:
        raise HeadPackageError(
            "Texture source changed after the material contract"
        )
    if not policy.accepted or policy.source_sha256 != asset.source_sha256:
        raise HeadPackageError(
            "Texture package policy does not belong to the verified source"
        )
    source_txi = _read_source_txi(asset)
    txi_text = _merge_txi_text(source_txi, policy)
    try:
        from pykotor.resource.formats.tpc import (
            bytes_tpc,
            read_tpc,
        )
        from pykotor.resource.type import ResourceType

        source_bytes = source.read_bytes()
        retail_tga_bytes: bytes | None = None
        if asset.source_format in {"PNG", "TGA"}:
            from PIL import Image

            converted = io.BytesIO()
            with Image.open(io.BytesIO(source_bytes)) as image:
                image.convert("RGBA").save(converted, format="TGA")
            retail_tga_bytes = converted.getvalue()
        if policy.output_format == "TGA" and retail_tga_bytes is not None:
            # Pillow writes the lower-left TGA origin used by Odyssey. Passing
            # these bytes through PyKotor's generic TGA writer changes the
            # descriptor to top-origin, which KOTOR's creature renderer does
            # not compensate for and therefore inverts the atlas against UVs.
            texture_bytes = retail_tga_bytes
        else:
            if asset.source_format == "PNG" and retail_tga_bytes is not None:
                source_bytes = retail_tga_bytes
            texture = read_tpc(
                source_bytes,
                txi_source=(
                    source_txi.encode("ascii")
                    if source_txi
                    else None
                ),
            )
            if policy.txi_delivery == "embedded":
                texture.txi = txi_text
            output_type = (
                ResourceType.TPC
                if policy.output_format == "TPC"
                else ResourceType.TGA
            )
            texture_bytes = bytes_tpc(texture, output_type)
    except Exception as exc:
        raise HeadPackageError(
            f"Could not create the selected KOTOR texture output: {exc}"
        ) from exc
    outputs = {
        f"{policy.output_resref}.{policy.output_format.lower()}": (
            texture_bytes
        )
    }
    if policy.txi_delivery == "sidecar":
        outputs[f"{policy.output_resref}.txi"] = txi_text.encode(
            "ascii",
            "strict",
        )
    if set(outputs) != set(policy.packaged_files):
        raise HeadPackageError(
            "Texture output files differ from the saved material policy"
        )
    return outputs


def _patch_utc_appearance(
    value: bytes,
    appearance_row: int,
) -> bytes:
    from src.formats.gff_reader import read_gff
    from src.formats.gff_types import GffFieldType
    from src.formats.gff_writer import write_gff

    utc = read_gff(value)
    if str(utc.file_type).strip().upper() != "UTC":
        raise HeadPackageError("Optional test actor is not a UTC resource")
    if "Appearance_Type" in utc.root.fields:
        field = utc.root.fields["Appearance_Type"]
        field.value = type(field.value)(appearance_row)
    else:
        utc.root.set(
            "Appearance_Type",
            GffFieldType.UINT16,
            int(appearance_row),
        )
    result = write_gff(utc)
    check = read_gff(result)
    if int(check.root.get("Appearance_Type", -1)) != int(
        appearance_row
    ):
        raise HeadPackageError(
            "UTC appearance row did not survive GFF readback"
        )
    return result


def _tslpatcher_changes_ini(
    patch: HeadGameRecordPatch,
    reference: HeadGameRecordMergeResult,
    runtime_names: Iterable[str],
) -> str:
    """Emit an additive TSLPatcher alternative using 2DAMEMORY links."""

    parser = configparser.ConfigParser(
        interpolation=None,
        strict=True,
    )
    parser.optionxform = str
    parser["Settings"] = {
        "WindowCaption": "Ghost Studio Custom Head",
        "ConfirmMessage": (
            "Install the Ghost Studio custom modular head?"
        ),
        "LogLevel": "3",
        "InstallerMode": "1",
        "BackupFiles": "1",
        "PlaintextLog": "0",
        "LookupGameFolder": "1",
        "LookupGameNumber": "2" if patch.game == "K2" else "1",
        "SaveProcessedScripts": "0",
    }
    parser["TLKList"] = {}
    parser["InstallList"] = {"install_folder0": "Override"}
    parser["install_folder0"] = {
        f"File{index}": name
        for index, name in enumerate(
            sorted(set(runtime_names), key=str.casefold)
        )
    }
    table_names = ["heads.2da", "appearance.2da"]
    if patch.portrait_resref:
        table_names.append("portraits.2da")
    parser["2DAList"] = {
        f"Table{index}": name
        for index, name in enumerate(table_names)
    }

    heads_section = "ghoststudio_head_row"
    parser["heads.2da"] = {"AddRow0": heads_section}
    heads_values = dict(
        reference.report["rows"]["heads"]["after"]
    )
    parser[heads_section] = {
        "RowLabel": str(reference.heads_row),
        "ExclusiveColumn": "head",
        **{str(key): str(value) for key, value in heads_values.items()},
        "2DAMEMORY0": "RowIndex",
    }

    appearance_section = "ghoststudio_appearance_row"
    parser["appearance.2da"] = {
        "AddRow0": appearance_section,
    }
    appearance_values = dict(
        reference.report["rows"]["appearance"]["after"]
    )
    appearance_values["normalhead"] = "2DAMEMORY0"
    parser[appearance_section] = {
        "RowLabel": str(reference.appearance_row),
        "ExclusiveColumn": "label",
        **{
            str(key): str(value)
            for key, value in appearance_values.items()
        },
        "2DAMEMORY1": "RowIndex",
    }

    if patch.portrait_resref:
        portrait_section = "ghoststudio_portrait_row"
        parser["portraits.2da"] = {
            "AddRow0": portrait_section,
        }
        portrait_values = dict(
            reference.report["rows"]["portraits"]["after"]
        )
        for column in (
            "appearancenumber",
            "appearance_s",
            "appearance_l",
        ):
            if column in portrait_values:
                portrait_values[column] = "2DAMEMORY1"
        parser[portrait_section] = {
            "RowLabel": str(reference.portraits_row),
            "ExclusiveColumn": "baseresref",
            **{
                str(key): str(value)
                for key, value in portrait_values.items()
            },
            "2DAMEMORY2": "RowIndex",
        }
    output = io.StringIO()
    parser.write(output, space_around_delimiters=False)
    return output.getvalue()


@dataclass(frozen=True, slots=True)
class HeadPackageBuildResult:
    ok: bool
    package_directory: str = ""
    report_path: str = ""
    install_plan_path: str = ""
    patch_path: str = ""
    files: Mapping[str, str] = field(default_factory=dict)
    hashes: Mapping[str, str] = field(default_factory=dict)
    reference_merge: HeadGameRecordMergeResult | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "package_directory": self.package_directory,
            "report_path": self.report_path,
            "install_plan_path": self.install_plan_path,
            "patch_path": self.patch_path,
            "files": dict(sorted(self.files.items())),
            "hashes": dict(sorted(self.hashes.items())),
            "reference_merge": (
                dict(self.reference_merge.report)
                if self.reference_merge is not None
                else {}
            ),
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class HeadInstallPreview:
    ok: bool
    preview_id: str = ""
    package_directory: str = ""
    game_directory: str = ""
    executable_path: str = ""
    executable_sha256: str = ""
    candidate_directory: str = ""
    heads_row: int = -1
    appearance_row: int = -1
    portraits_row: int = -1
    files: tuple[Mapping[str, Any], ...] = ()
    before_after: Mapping[str, Any] = field(default_factory=dict)
    process_names: tuple[str, ...] = ()
    messages: tuple[str, ...] = ()
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "preview_id": self.preview_id,
            "package_directory": self.package_directory,
            "game_directory": self.game_directory,
            "executable_path": self.executable_path,
            "executable_sha256": self.executable_sha256,
            "candidate_directory": self.candidate_directory,
            "heads_row": self.heads_row,
            "appearance_row": self.appearance_row,
            "portraits_row": self.portraits_row,
            "files": [dict(value) for value in self.files],
            "before_after": dict(self.before_after),
            "process_names": list(self.process_names),
            "messages": list(self.messages),
            "error": self.error,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
    ) -> "HeadInstallPreview":
        return cls(
            ok=bool(payload.get("ok", False)),
            preview_id=str(payload.get("preview_id") or ""),
            package_directory=str(
                payload.get("package_directory") or ""
            ),
            game_directory=str(payload.get("game_directory") or ""),
            executable_path=str(
                payload.get("executable_path") or ""
            ),
            executable_sha256=str(
                payload.get("executable_sha256") or ""
            ),
            candidate_directory=str(
                payload.get("candidate_directory") or ""
            ),
            heads_row=int(payload.get("heads_row", -1)),
            appearance_row=int(payload.get("appearance_row", -1)),
            portraits_row=int(payload.get("portraits_row", -1)),
            files=tuple(
                dict(value)
                for value in payload.get("files") or ()
            ),
            before_after=dict(payload.get("before_after") or {}),
            process_names=tuple(
                str(value)
                for value in payload.get("process_names") or ()
            ),
            messages=tuple(
                str(value)
                for value in payload.get("messages") or ()
            ),
            error=str(payload.get("error") or ""),
        )


@dataclass(frozen=True, slots=True)
class HeadInstallResult:
    ok: bool
    session_manifest: str = ""
    installed_files: tuple[str, ...] = ()
    restored_files: tuple[str, ...] = ()
    messages: tuple[str, ...] = ()
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "session_manifest": self.session_manifest,
            "installed_files": list(self.installed_files),
            "restored_files": list(self.restored_files),
            "messages": list(self.messages),
            "error": self.error,
        }


def _prepare_owned_rebuild(
    root: Path,
    *,
    project_id: str,
    allow_overwrite: bool,
) -> None:
    if not root.exists() or not any(root.iterdir()):
        return
    if not allow_overwrite:
        raise HeadPackageError(
            "Package folder is not empty; choose an empty folder or "
            "explicitly rebuild this project's verified package"
        )
    reports = list(root.glob("*.head-package-report.json"))
    if len(reports) != 1:
        raise HeadPackageError(
            "Existing package ownership report is missing or ambiguous"
        )
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    if (
        report.get("schema") != HEAD_PACKAGE_SCHEMA
        or str(report.get("project_id") or "") != str(project_id)
    ):
        raise HeadPackageError(
            "Existing package belongs to another project"
        )
    for relative, wanted in dict(
        report.get("output_hashes") or {}
    ).items():
        target = (root / str(relative)).resolve()
        if root.resolve() not in target.parents:
            raise HeadPackageError(
                "Existing ownership report contains an unsafe path"
            )
        if (
            not target.is_file()
            or _sha256_file(target) != str(wanted)
        ):
            raise HeadPackageError(
                f"Owned package file changed after build: {relative}"
            )
    for relative in dict(report.get("output_hashes") or {}):
        (root / str(relative)).unlink(missing_ok=True)
    reports[0].unlink(missing_ok=True)


def build_head_package(
    *,
    project_id: str,
    display_name: str,
    binary_export: HeadBinaryExportResult,
    texture_asset: HeadTextureAsset,
    texture_policy: HeadTextureOutputPolicy,
    game_record_patch: HeadGameRecordPatch,
    reference_heads_bytes: bytes,
    reference_appearance_bytes: bytes,
    destination: str | Path,
    reference_portraits_bytes: bytes | None = None,
    utc_template_path: str | Path | None = None,
    portrait_files: Iterable[str | Path] = (),
    launcher_process_names: Iterable[str] = (),
    allow_overwrite: bool = False,
) -> HeadPackageBuildResult:
    """Build a portable additive package plus direct/TSLPatcher metadata."""

    root = Path(destination).expanduser().resolve()
    try:
        _prepare_owned_rebuild(
            root,
            project_id=project_id,
            allow_overwrite=allow_overwrite,
        )
        root.mkdir(parents=True, exist_ok=True)
        written: dict[str, Path] = {}
        additional = root / "additional"
        additional.mkdir(parents=True, exist_ok=True)

        mdl = Path(binary_export.mdl_path)
        mdx = Path(binary_export.mdx_path)
        if (
            not mdl.is_file()
            or not mdx.is_file()
            or _sha256_file(mdl)
            != binary_export.inspection.mdl_sha256
            or _sha256_file(mdx)
            != binary_export.inspection.mdx_sha256
        ):
            raise HeadPackageError(
                "Verified MDL/MDX outputs changed before packaging"
            )
        resref = game_record_patch.output_head_resref
        runtime: dict[str, bytes] = {
            f"{resref}.mdl": mdl.read_bytes(),
            f"{resref}.mdx": mdx.read_bytes(),
            **_texture_outputs(texture_asset, texture_policy),
        }
        for source_value in portrait_files:
            source = Path(source_value).expanduser().resolve()
            if not source.is_file():
                raise HeadPackageError(
                    f"Portrait package file does not exist: {source}"
                )
            name = _safe_package_file(source.name)
            if source.suffix.casefold() not in {".tga", ".tpc", ".txi"}:
                raise HeadPackageError(
                    f"Unsupported portrait package file: {name}"
                )
            value = source.read_bytes()
            if name in runtime and runtime[name] != value:
                raise HeadPackageError(
                    f"Portrait file collides with another output: {name}"
                )
            runtime[name] = value

        utc_name = ""
        if utc_template_path is not None:
            utc_source = Path(utc_template_path).expanduser().resolve()
            if not utc_source.is_file():
                raise HeadPackageError(
                    f"Optional UTC template was not found: {utc_source}"
                )
            utc_name = f"{resref[:16]}.utc.template"
            _write_package_file(
                root,
                f"additional/{utc_name}",
                utc_source.read_bytes(),
                written,
            )

        for name, value in sorted(
            runtime.items(),
            key=lambda item: item[0].casefold(),
        ):
            if Path(name).suffix.casefold() not in _RUNTIME_SUFFIXES:
                raise HeadPackageError(
                    f"Unsupported runtime output: {name}"
                )
            _write_package_file(
                root,
                f"additional/{_safe_package_file(name)}",
                value,
                written,
            )

        reference = merge_head_game_records(
            game_record_patch,
            heads_bytes=reference_heads_bytes,
            appearance_bytes=reference_appearance_bytes,
            portraits_bytes=reference_portraits_bytes,
        )
        if not reference.accepted:
            raise HeadPackageError(
                "Reference game-record merge was not accepted"
            )
        patch_path = _write_package_file(
            root,
            "additional/head-game-records.patch.json",
            _stable_json(game_record_patch.to_dict()),
            written,
        )
        merge_report_path = _write_package_file(
            root,
            "additional/reference-merge-report.json",
            _stable_json(dict(reference.report)),
            written,
        )
        exe_name = (
            "swkotor2.exe"
            if game_record_patch.game == "K2"
            else "swkotor.exe"
        )
        process_names = {
            exe_name.casefold(),
            "launcher.exe",
            *(
                str(value).strip().casefold()
                for value in launcher_process_names
                if str(value).strip()
            ),
        }
        plan = {
            "schema": HEAD_INSTALL_PLAN_SCHEMA,
            "package_schema": HEAD_PACKAGE_SCHEMA,
            "project_id": project_id,
            "target_game": game_record_patch.game,
            "output_head_resref": resref,
            "game_executable": exe_name,
            "process_names": sorted(process_names),
            "runtime_files": sorted(runtime, key=str.casefold),
            "utc_template": utc_name,
            "utc_runtime_name": (
                f"{resref[:16]}.utc" if utc_name else ""
            ),
            "game_record_patch": patch_path.name,
            "reference_merge_report": merge_report_path.name,
            "target_directory": "Override",
            "executable_edits": False,
            "cache_actions": [],
            "requires_patch_launcher": False,
        }
        install_plan_path = _write_package_file(
            root,
            "additional/install-plan.json",
            _stable_json(plan),
            written,
        )
        tsl_root = root / "tslpatchdata"
        for name, value in sorted(
            runtime.items(),
            key=lambda item: item[0].casefold(),
        ):
            _write_package_file(
                root,
                f"tslpatchdata/{name}",
                value,
                written,
            )
        changes = _tslpatcher_changes_ini(
            game_record_patch,
            reference,
            runtime,
        )
        _write_package_file(
            root,
            "tslpatchdata/changes.ini",
            changes.encode("utf-8"),
            written,
        )
        manifest = (
            "[package]\n"
            f'id = "ghoststudio-head-{resref.lower()}"\n'
            f'name = "{str(display_name).replace(chr(34), chr(39))}"\n'
            f'game = "{game_record_patch.game}"\n'
            'type = "custom-modular-head"\n'
            'install = "merge-safe-override"\n'
        )
        _write_package_file(
            root,
            "manifest.toml",
            manifest.encode("utf-8"),
            written,
        )
        readme = (
            f"# {display_name}\n\n"
            "This Ghost Studio package installs one modular KOTOR head. "
            "Use **Prepare Test Install** in Head Builder for a live-table "
            "preview, timestamped backups, atomic installation, and Restore "
            "Previous Test. No executable is modified.\n\n"
            "The `tslpatchdata` folder is an additive TSLPatcher-compatible "
            "alternative. Ghost Studio's installer is preferred because it "
            "re-finds stable row values and refuses conflicts before writing.\n"
        )
        _write_package_file(
            root,
            "README.md",
            readme.encode("utf-8"),
            written,
        )

        hashes = {
            relative: _sha256_file(path)
            for relative, path in sorted(written.items())
        }
        report = {
            "schema": HEAD_PACKAGE_SCHEMA,
            "project_id": project_id,
            "display_name": display_name,
            "target_game": game_record_patch.game,
            "output_head_resref": resref,
            "generated_at": _utc_now(),
            "binary_inspection": (
                binary_export.inspection.to_dict()
            ),
            "texture_policy": texture_policy.to_dict(),
            "game_record_patch": game_record_patch.to_dict(),
            "reference_merge": dict(reference.report),
            "install_plan": plan,
            "output_hashes": hashes,
            "absolute_developer_paths_in_package": False,
            "source_files_modified": False,
        }
        report_path = root / f"{resref}.head-package-report.json"
        _write_atomic(report_path, _stable_json(report))
        return HeadPackageBuildResult(
            ok=True,
            package_directory=str(root),
            report_path=str(report_path),
            install_plan_path=str(install_plan_path),
            patch_path=str(patch_path),
            files={
                relative: str(path)
                for relative, path in sorted(written.items())
            },
            hashes=hashes,
            reference_merge=reference,
        )
    except Exception as exc:
        return HeadPackageBuildResult(
            ok=False,
            package_directory=str(root),
            error=str(exc),
        )


def _load_package(
    package_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], HeadGameRecordPatch]:
    plan_path = package_root / "additional" / "install-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("schema") != HEAD_INSTALL_PLAN_SCHEMA:
        raise HeadPackageError("Head install plan schema is not supported")
    reports = list(package_root.glob("*.head-package-report.json"))
    if len(reports) != 1:
        raise HeadPackageError(
            "Head package ownership report is missing or ambiguous"
        )
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    if (
        report.get("schema") != HEAD_PACKAGE_SCHEMA
        or report.get("project_id") != plan.get("project_id")
    ):
        raise HeadPackageError(
            "Head package report does not belong to its install plan"
        )
    for relative, wanted in dict(
        report.get("output_hashes") or {}
    ).items():
        path = (package_root / str(relative)).resolve()
        if package_root.resolve() not in path.parents:
            raise HeadPackageError("Package report contains an unsafe path")
        if not path.is_file() or _sha256_file(path) != str(wanted):
            raise HeadPackageError(
                f"Package file changed after build: {relative}"
            )
    patch_name = _safe_package_file(
        str(plan.get("game_record_patch") or "")
    )
    patch_payload = json.loads(
        (
            package_root / "additional" / patch_name
        ).read_text(encoding="utf-8")
    )
    if (
        patch_payload.get("schema")
        != HEAD_GAME_RECORD_PATCH_SCHEMA
    ):
        raise HeadPackageError(
            "Head game-record patch schema is not supported"
        )
    return report, plan, HeadGameRecordPatch.from_dict(patch_payload)


class HeadPackageInstaller:
    """Preview, install, and restore one exact Custom Head package."""

    def __init__(
        self,
        *,
        process_is_running: Callable[[str], bool] | None = None,
    ) -> None:
        self._process_is_running = (
            process_is_running or _default_process_is_running
        )

    def preview(
        self,
        package_directory: str | Path,
        game_directory: str | Path,
    ) -> HeadInstallPreview:
        package_root = Path(package_directory).expanduser().resolve()
        game_root = Path(game_directory).expanduser().resolve()
        try:
            report, plan, patch = _load_package(package_root)
            exe_path = game_root / str(plan["game_executable"])
            if not exe_path.is_file():
                raise HeadPackageError(
                    f"Expected game executable was not found: {exe_path}"
                )
            exe_hash = _sha256_file(exe_path)
            heads_source = load_live_twoda(game_root, "heads")
            appearance_source = load_live_twoda(
                game_root,
                "appearance",
            )
            portraits_source = (
                load_live_twoda(game_root, "portraits")
                if patch.portrait_resref
                else None
            )
            merge = merge_head_game_records(
                patch,
                heads_bytes=heads_source,
                appearance_bytes=appearance_source,
                portraits_bytes=portraits_source,
            )
            identity_seed = {
                "package_report_sha256": _sha256(
                    _stable_json(report)
                ),
                "game_directory": str(game_root),
                "executable_sha256": exe_hash,
                "heads_before_sha256": _sha256(heads_source),
                "appearance_before_sha256": _sha256(
                    appearance_source
                ),
                "portraits_before_sha256": (
                    _sha256(portraits_source)
                    if portraits_source is not None
                    else ""
                ),
            }
            seed_hash = _sha256(_stable_json(identity_seed))
            candidate_root = (
                package_root / ".install-preview" / seed_hash[:16]
            )
            candidates: dict[str, bytes] = {
                "heads.2da": merge.heads_bytes,
                "appearance.2da": merge.appearance_bytes,
            }
            if (
                patch.portrait_resref
                and merge.portraits_bytes is not None
            ):
                candidates["portraits.2da"] = (
                    merge.portraits_bytes
                )
            for raw_name in plan.get("runtime_files") or ():
                name = _safe_package_file(str(raw_name))
                source = package_root / "additional" / name
                if (
                    not source.is_file()
                    or source.suffix.casefold()
                    not in _RUNTIME_SUFFIXES
                ):
                    raise HeadPackageError(
                        f"Package runtime file is missing: {name}"
                    )
                candidates[name] = source.read_bytes()
            utc_template = str(plan.get("utc_template") or "")
            if utc_template:
                source = (
                    package_root
                    / "additional"
                    / _safe_package_file(utc_template)
                )
                runtime_name = _safe_package_file(
                    str(plan.get("utc_runtime_name") or "")
                )
                candidates[runtime_name] = _patch_utc_appearance(
                    source.read_bytes(),
                    merge.appearance_row,
                )
            for name, value in candidates.items():
                _write_atomic(candidate_root / name, value)

            override = (game_root / "Override").resolve()
            files: list[dict[str, Any]] = []
            for name in sorted(candidates, key=str.casefold):
                candidate = (candidate_root / name).resolve()
                target = (override / name).resolve()
                if target.parent != override:
                    raise HeadPackageError(
                        f"Install target escapes Override: {name}"
                    )
                current_hash = (
                    _sha256_file(target) if target.is_file() else ""
                )
                candidate_hash = _sha256_file(candidate)
                files.append(
                    {
                        "name": name,
                        "target": str(target),
                        "candidate": str(candidate),
                        "status": (
                            "new"
                            if not current_hash
                            else (
                                "unchanged"
                                if current_hash == candidate_hash
                                else "replace_with_backup"
                            )
                        ),
                        "current_sha256": current_hash,
                        "candidate_sha256": candidate_hash,
                        "size": candidate.stat().st_size,
                    }
                )
            preview_payload = {
                **identity_seed,
                "rows": {
                    "heads": merge.heads_row,
                    "appearance": merge.appearance_row,
                    "portraits": merge.portraits_row,
                },
                "files": files,
            }
            preview_id = _sha256(_stable_json(preview_payload))
            return HeadInstallPreview(
                ok=True,
                preview_id=preview_id,
                package_directory=str(package_root),
                game_directory=str(game_root),
                executable_path=str(exe_path),
                executable_sha256=exe_hash,
                candidate_directory=str(candidate_root),
                heads_row=merge.heads_row,
                appearance_row=merge.appearance_row,
                portraits_row=merge.portraits_row,
                files=tuple(files),
                before_after=dict(merge.report),
                process_names=tuple(plan.get("process_names") or ()),
                messages=(
                    "No game files have been changed.",
                    "Confirm this exact destination/hash preview to install.",
                    "No executable edit or unproven cache deletion is planned.",
                ),
            )
        except Exception as exc:
            return HeadInstallPreview(
                ok=False,
                package_directory=str(package_root),
                game_directory=str(game_root),
                error=str(exc),
            )

    def install(
        self,
        preview: HeadInstallPreview,
        *,
        confirmed_preview_id: str,
    ) -> HeadInstallResult:
        if (
            not preview.ok
            or not preview.preview_id
            or confirmed_preview_id != preview.preview_id
        ):
            return HeadInstallResult(
                ok=False,
                error="The exact prepared install preview was not confirmed",
            )
        game_root = Path(preview.game_directory).resolve()
        exe_path = Path(preview.executable_path).resolve()
        try:
            if (
                not exe_path.is_file()
                or _sha256_file(exe_path)
                != preview.executable_sha256
            ):
                raise HeadPackageError(
                    "The game executable changed after preview"
                )
            for process_name in preview.process_names:
                if self._process_is_running(process_name):
                    raise HeadPackageError(
                        f"Close {process_name} before installing the test"
                    )
            override = (game_root / "Override").resolve()
            for item in preview.files:
                candidate = Path(str(item["candidate"])).resolve()
                target = Path(str(item["target"])).resolve()
                if target.parent != override:
                    raise HeadPackageError(
                        f"Install target is outside Override: {target}"
                    )
                if target == exe_path:
                    raise HeadPackageError(
                        "Custom Head installation can never target the EXE"
                    )
                if (
                    not candidate.is_file()
                    or _sha256_file(candidate)
                    != str(item["candidate_sha256"])
                ):
                    raise HeadPackageError(
                        f"Install candidate changed after preview: "
                        f"{item['name']}"
                    )
                current = (
                    _sha256_file(target) if target.is_file() else ""
                )
                if current != str(item["current_sha256"]):
                    raise HeadPackageError(
                        f"Target changed after preview: {item['name']}"
                    )

            timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
            session = (
                Path(preview.package_directory)
                / ".install-sessions"
                / f"{timestamp}-{preview.preview_id[:8]}"
            )
            before_root = session / "before" / "Override"
            before_root.mkdir(parents=True, exist_ok=False)
            records: list[dict[str, Any]] = []
            for item in preview.files:
                target = Path(str(item["target"]))
                existed = target.is_file()
                backup = before_root / str(item["name"])
                before_mtime_ns = (
                    target.stat().st_mtime_ns if existed else 0
                )
                backup_sha = ""
                if existed:
                    _write_atomic(backup, target.read_bytes())
                    os.utime(
                        backup,
                        ns=(
                            before_mtime_ns,
                            before_mtime_ns,
                        ),
                    )
                    backup_sha = _sha256_file(backup)
                    if backup_sha != str(item["current_sha256"]):
                        raise HeadPackageError(
                            f"Backup verification failed: {item['name']}"
                        )
                records.append(
                    {
                        "name": str(item["name"]),
                        "target": str(target),
                        "candidate": str(item["candidate"]),
                        "existed": existed,
                        "before_sha256": str(
                            item["current_sha256"]
                        ),
                        "before_mtime_ns": before_mtime_ns,
                        "backup": str(backup) if existed else "",
                        "backup_sha256": backup_sha,
                        "installed_sha256": str(
                            item["candidate_sha256"]
                        ),
                    }
                )
            manifest_path = session / "install-session.json"
            manifest: dict[str, Any] = {
                "schema": HEAD_INSTALL_SESSION_SCHEMA,
                "status": "prepared",
                "prepared_at": _utc_now(),
                "installed_at": "",
                "game_directory": str(game_root),
                "executable_path": str(exe_path),
                "executable_sha256": preview.executable_sha256,
                "preview_id": preview.preview_id,
                "process_names": list(preview.process_names),
                "heads_row": preview.heads_row,
                "appearance_row": preview.appearance_row,
                "portraits_row": preview.portraits_row,
                "cache_actions": [],
                "files": records,
            }
            _write_atomic(manifest_path, _stable_json(manifest))
            installed: list[str] = []
            try:
                for record in records:
                    candidate = Path(record["candidate"])
                    target = Path(record["target"])
                    _write_atomic(target, candidate.read_bytes())
                    if (
                        _sha256_file(target)
                        != record["installed_sha256"]
                    ):
                        raise HeadPackageError(
                            f"Installed hash mismatch: {record['name']}"
                        )
                    installed.append(str(target))
                manifest["status"] = "installed"
                manifest["installed_at"] = _utc_now()
                _write_atomic(manifest_path, _stable_json(manifest))
                return HeadInstallResult(
                    ok=True,
                    session_manifest=str(manifest_path),
                    installed_files=tuple(installed),
                    messages=(
                        "The exact preview was installed atomically.",
                        "Verified backups are ready for Restore Previous Test.",
                    ),
                )
            except Exception:
                for record in reversed(records):
                    target = Path(record["target"])
                    if record["existed"]:
                        backup = Path(record["backup"])
                        if (
                            backup.is_file()
                            and _sha256_file(backup)
                            == record["before_sha256"]
                        ):
                            _write_atomic(target, backup.read_bytes())
                            os.utime(
                                target,
                                ns=(
                                    int(record["before_mtime_ns"]),
                                    int(record["before_mtime_ns"]),
                                ),
                            )
                    else:
                        target.unlink(missing_ok=True)
                manifest["status"] = "rolled_back"
                _write_atomic(manifest_path, _stable_json(manifest))
                raise
        except Exception as exc:
            return HeadInstallResult(
                ok=False,
                error=f"Install stopped or rolled back: {exc}",
            )

    def restore(
        self,
        session_manifest: str | Path,
    ) -> HeadInstallResult:
        manifest_path = Path(session_manifest).expanduser().resolve()
        try:
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            if (
                manifest.get("schema")
                != HEAD_INSTALL_SESSION_SCHEMA
                or manifest.get("status") != "installed"
            ):
                raise HeadPackageError(
                    "Install session is not an active installed test"
                )
            exe_path = Path(manifest["executable_path"]).resolve()
            for process_name in tuple(
                manifest.get("process_names")
                or (
                    "swkotor.exe",
                    "swkotor2.exe",
                    "launcher.exe",
                )
            ):
                if self._process_is_running(process_name):
                    raise HeadPackageError(
                        f"Close {process_name} before restoring the test"
                    )
            if (
                not exe_path.is_file()
                or _sha256_file(exe_path)
                != manifest["executable_sha256"]
            ):
                raise HeadPackageError(
                    "The game executable changed after installation"
                )
            records = [dict(value) for value in manifest["files"]]
            for record in records:
                target = Path(record["target"])
                current = (
                    _sha256_file(target) if target.is_file() else ""
                )
                if current != record["installed_sha256"]:
                    raise HeadPackageError(
                        f"{target.name} changed after this test install; "
                        "restore stopped instead of overwriting newer work"
                    )
                if record["existed"]:
                    backup = Path(record["backup"])
                    if (
                        not backup.is_file()
                        or _sha256_file(backup)
                        != record["backup_sha256"]
                        or record["backup_sha256"]
                        != record["before_sha256"]
                    ):
                        raise HeadPackageError(
                            f"Backup is missing or damaged: {backup}"
                        )
            restored: list[str] = []
            changed: list[dict[str, Any]] = []
            try:
                for record in reversed(records):
                    target = Path(record["target"])
                    if record["existed"]:
                        backup = Path(record["backup"])
                        _write_atomic(target, backup.read_bytes())
                        os.utime(
                            target,
                            ns=(
                                int(record["before_mtime_ns"]),
                                int(record["before_mtime_ns"]),
                            ),
                        )
                        if (
                            _sha256_file(target)
                            != record["before_sha256"]
                        ):
                            raise HeadPackageError(
                                f"Restored hash mismatch: "
                                f"{record['name']}"
                            )
                    else:
                        target.unlink(missing_ok=True)
                        if target.exists():
                            raise HeadPackageError(
                                f"Could not remove new test file: "
                                f"{record['name']}"
                            )
                    changed.append(record)
                    restored.append(str(target))
            except Exception:
                for record in changed:
                    candidate = Path(record["candidate"])
                    target = Path(record["target"])
                    if candidate.is_file():
                        _write_atomic(target, candidate.read_bytes())
                raise
            manifest["status"] = "restored"
            manifest["restored_at"] = _utc_now()
            _write_atomic(manifest_path, _stable_json(manifest))
            _write_atomic(
                manifest_path.with_name("restore-report.json"),
                _stable_json(
                    {
                        "schema": HEAD_INSTALL_SESSION_SCHEMA,
                        "restored_at": manifest["restored_at"],
                        "files": restored,
                    }
                ),
            )
            return HeadInstallResult(
                ok=True,
                session_manifest=str(manifest_path),
                restored_files=tuple(restored),
                messages=(
                    "Restore Previous Test completed from verified backups.",
                ),
            )
        except Exception as exc:
            return HeadInstallResult(
                ok=False,
                session_manifest=str(manifest_path),
                error=str(exc),
            )


def _default_process_is_running(executable_name: str) -> bool:
    wanted = str(executable_name or "").strip().casefold()
    if not wanted:
        return False
    try:
        import psutil

        return any(
            str(process.info.get("name") or "").casefold() == wanted
            for process in psutil.process_iter(["name"])
        )
    except ImportError:
        pass
    except Exception as exc:
        raise HeadPackageError(
            f"Could not verify running processes: {exc}"
        ) from exc
    if os.name != "nt":
        raise HeadPackageError(
            "A running-process verifier is unavailable; install is blocked"
        )
    try:
        completed = subprocess.run(
            ["tasklist.exe", "/FO", "CSV", "/NH"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0,
            ),
        )
    except Exception as exc:
        raise HeadPackageError(
            f"Could not verify running Windows processes: {exc}"
        ) from exc
    for line in completed.stdout.splitlines():
        first = line.strip().split(",", 1)[0].strip().strip('"')
        if first.casefold() == wanted:
            return True
    return False


__all__ = [
    "HEAD_INSTALL_PLAN_SCHEMA",
    "HEAD_INSTALL_SESSION_SCHEMA",
    "HEAD_PACKAGE_SCHEMA",
    "HeadInstallPreview",
    "HeadInstallResult",
    "HeadPackageBuildResult",
    "HeadPackageError",
    "HeadPackageInstaller",
    "build_head_package",
]
