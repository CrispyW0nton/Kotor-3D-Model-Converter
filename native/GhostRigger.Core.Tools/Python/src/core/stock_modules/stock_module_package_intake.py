"""Safe intake helpers for module archives wrapped in delivery packages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import zipfile


MODULE_ARCHIVE_SUFFIXES = frozenset({".mod", ".rim", ".erf"})
MODULE_PACKAGE_SUFFIXES = frozenset({".zip"})
_MODULE_ARCHIVE_PRIORITY = {".mod": 0, ".rim": 1, ".erf": 2}


@dataclass(frozen=True)
class ModulePackageCandidate:
    """A module archive that can be opened from a file or package."""

    source_path: Path
    display_name: str
    member_name: str | None
    suffix: str
    size: int
    source_kind: str


@dataclass(frozen=True)
class PreparedModuleOpenPath:
    """A concrete module path ready for archive reading."""

    source_path: Path
    module_path: Path
    display_name: str
    source_label: str
    member_name: str | None = None


def discover_module_package_candidates(path: str | Path) -> tuple[ModulePackageCandidate, ...]:
    """Find MOD/RIM/ERF archives in a direct file path or supported package."""

    source_path = Path(path)
    suffix = source_path.suffix.lower()
    if suffix in MODULE_ARCHIVE_SUFFIXES:
        return (
            ModulePackageCandidate(
                source_path=source_path,
                display_name=source_path.name,
                member_name=None,
                suffix=suffix,
                size=source_path.stat().st_size if source_path.exists() else 0,
                source_kind="module archive",
            ),
        )
    if suffix not in MODULE_PACKAGE_SUFFIXES:
        return ()

    candidates: list[ModulePackageCandidate] = []
    with zipfile.ZipFile(source_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            member_path = PurePosixPath(info.filename)
            member_suffix = member_path.suffix.lower()
            if member_suffix not in MODULE_ARCHIVE_SUFFIXES:
                continue
            candidates.append(
                ModulePackageCandidate(
                    source_path=source_path,
                    display_name=member_path.name,
                    member_name=info.filename,
                    suffix=member_suffix,
                    size=info.file_size,
                    source_kind="zip package",
                )
            )
    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                _MODULE_ARCHIVE_PRIORITY.get(item.suffix, 99),
                item.display_name.lower(),
                item.member_name or "",
            ),
        )
    )


def prepare_module_open_path(
    path: str | Path,
    extraction_dir: str | Path | None = None,
    *,
    member_name: str | None = None,
) -> PreparedModuleOpenPath:
    """Return an archive path that can be read without mutating the source package."""

    source_path = Path(path)
    suffix = source_path.suffix.lower()
    if suffix in MODULE_ARCHIVE_SUFFIXES:
        return PreparedModuleOpenPath(
            source_path=source_path,
            module_path=source_path,
            display_name=source_path.name,
            source_label=str(source_path),
        )
    if suffix not in MODULE_PACKAGE_SUFFIXES:
        raise ValueError(f"Unsupported module package type: {source_path.suffix or source_path.name}")
    if extraction_dir is None:
        raise ValueError("ZIP module packages require a temporary extraction directory.")

    candidates = discover_module_package_candidates(source_path)
    if not candidates:
        raise ValueError(f"No MOD/RIM/ERF archives were found inside {source_path.name}.")
    selected = _select_candidate(candidates, member_name)
    output_name = _safe_package_member_filename(selected.member_name or selected.display_name)
    output_path = Path(extraction_dir) / output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(source_path) as archive:
        with archive.open(selected.member_name or selected.display_name) as source:
            output_path.write_bytes(source.read())

    return PreparedModuleOpenPath(
        source_path=source_path,
        module_path=output_path,
        display_name=selected.display_name,
        source_label=f"{source_path.name}:{selected.member_name or selected.display_name}",
        member_name=selected.member_name,
    )


def _select_candidate(
    candidates: tuple[ModulePackageCandidate, ...],
    member_name: str | None,
) -> ModulePackageCandidate:
    if member_name is None:
        return candidates[0]
    for candidate in candidates:
        if candidate.member_name == member_name or candidate.display_name == member_name:
            return candidate
    raise ValueError(f"Module archive {member_name!r} was not found in the package.")


def _safe_package_member_filename(member_name: str) -> str:
    filename = PurePosixPath(member_name.replace("\\", "/")).name
    if not filename:
        raise ValueError(f"Invalid module archive member name: {member_name!r}")
    if Path(filename).suffix.lower() not in MODULE_ARCHIVE_SUFFIXES:
        raise ValueError(f"Unsupported module archive member type: {filename}")
    return filename
