"""Exact-byte vanilla texture staging for cross-game legacy module ports.

This workflow never edits either KOTOR installation.  It copies a texture only
when the target installation lacks it, validates the donor TPC, follows the
external TXI texture dependencies used by Odyssey materials, and records hashes
and provenance for later module packaging and retail-game proof.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any


_TXI_TEXTURE_KEYS = frozenset({"envmaptexture", "bumpmaptexture"})


@dataclass(frozen=True)
class LegacyTexturePortRequest:
    source_game_root: str
    target_game_root: str
    texture_resrefs: tuple[str, ...]
    output_dir: str
    overwrite: bool = False


@dataclass
class LegacyTexturePortResult:
    ok: bool = False
    requested: list[str] = field(default_factory=list)
    already_in_target: list[str] = field(default_factory=list)
    dependency_resrefs: list[str] = field(default_factory=list)
    extracted: list[dict[str, Any]] = field(default_factory=list)
    missing_from_source: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    manifest_path: str = ""
    code: str = "not_run"
    message: str = ""
    game_tested: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalise_texture_resref(value: Any) -> str:
    text = str(value or "").strip()
    if "." in text:
        text = text.rsplit(".", 1)[0]
    if not text or len(text) > 16 or any(ch in text for ch in ("/", "\\")):
        raise ValueError(f"Invalid Odyssey texture resref: {value!r}")
    return text


def _texture_result(installation: Any, resref: str) -> tuple[Any | None, str]:
    from pykotor.extract.installation import SearchLocation

    result, source_kind = installation.texture_resource_result(
        resref,
        order=[
            SearchLocation.TEXTURES_TPA,
            SearchLocation.TEXTURES_TPB,
            SearchLocation.TEXTURES_TPC,
            SearchLocation.TEXTURES_GUI,
            SearchLocation.CHITIN,
        ],
    )
    return result, str(source_kind or "")


def _txi_dependencies(txi: str) -> tuple[str, ...]:
    dependencies: list[str] = []
    for raw_line in str(txi or "").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = re.split(r"\s+", line, maxsplit=1)
        if len(parts) != 2 or parts[0].strip().lower() not in _TXI_TEXTURE_KEYS:
            continue
        value = parts[1].strip().strip('"\'')
        if not value or value.lower() in {"null", "none", "****"}:
            continue
        try:
            dependency = _normalise_texture_resref(value)
        except ValueError:
            continue
        if dependency.lower() not in {item.lower() for item in dependencies}:
            dependencies.append(dependency)
    return tuple(dependencies)


def stage_vanilla_texture_dependencies(request: LegacyTexturePortRequest) -> LegacyTexturePortResult:
    """Stage exact donor-game TPC bytes missing from the target game."""

    output_dir = Path(request.output_dir).expanduser().resolve()
    manifest_path = output_dir / "vanilla-texture-port.json"
    result = LegacyTexturePortResult(manifest_path=str(manifest_path))
    try:
        from pykotor.extract.installation import Installation
        from pykotor.resource.formats.tpc import read_tpc

        source_root = Path(request.source_game_root).expanduser().resolve()
        target_root = Path(request.target_game_root).expanduser().resolve()
        for label, root in (("source", source_root), ("target", target_root)):
            if not (root / "chitin.key").is_file():
                result.blocking_issues.append(f"The {label} KOTOR installation is invalid: {root}")
        requested: list[str] = []
        for raw_resref in request.texture_resrefs:
            resref = _normalise_texture_resref(raw_resref)
            if resref.lower() not in {item.lower() for item in requested}:
                requested.append(resref)
        result.requested = list(requested)
        if not requested:
            result.blocking_issues.append("No texture resrefs were requested.")
        if result.blocking_issues:
            raise ValueError("Texture-port input is incomplete.")

        source_install = Installation(source_root)
        target_install = Installation(target_root)
        output_dir.mkdir(parents=True, exist_ok=True)
        queue = list(requested)
        visited: set[str] = set()
        requested_keys = {item.lower() for item in requested}
        while queue:
            resref = queue.pop(0)
            key = resref.lower()
            if key in visited:
                continue
            visited.add(key)
            target_resource, _target_kind = _texture_result(target_install, resref)
            if target_resource is not None:
                result.already_in_target.append(resref)
                continue

            source_resource, source_kind = _texture_result(source_install, resref)
            if source_resource is None:
                result.missing_from_source.append(resref)
                result.blocking_issues.append(
                    f"Texture {resref} is absent from both the target and donor installations."
                )
                continue
            data = bytes(source_resource.data)
            try:
                texture = read_tpc(data)
            except Exception as exc:
                result.blocking_issues.append(f"Donor texture {resref}.tpc failed decode validation: {exc}")
                continue
            dependencies = _txi_dependencies(str(getattr(texture, "txi", "") or ""))
            for dependency in dependencies:
                if dependency.lower() not in requested_keys and dependency.lower() not in {
                    item.lower() for item in result.dependency_resrefs
                }:
                    result.dependency_resrefs.append(dependency)
                if dependency.lower() not in visited:
                    queue.append(dependency)

            output_path = output_dir / f"{resref.lower()}.tpc"
            if output_path.exists() and not request.overwrite:
                existing = output_path.read_bytes()
                if existing != data:
                    result.blocking_issues.append(
                        f"Texture output exists with conflicting bytes and overwrite is disabled: {output_path}"
                    )
                    continue
            output_path.write_bytes(data)
            result.extracted.append(
                {
                    "resref": resref,
                    "path": str(output_path),
                    "size": len(data),
                    "sha256": sha256(data).hexdigest(),
                    "source_path": str(getattr(source_resource, "filepath", "") or ""),
                    "source_kind": source_kind,
                    "txi": str(getattr(texture, "txi", "") or ""),
                    "dependencies": list(dependencies),
                }
            )

        result.ok = not result.blocking_issues
        result.code = "texture_port_ready" if result.ok else "texture_port_blocked"
        result.message = (
            f"Staged {len(result.extracted)} exact vanilla TPC texture(s); "
            f"{len(result.already_in_target)} already exist in the target game."
            if result.ok
            else "Vanilla texture staging has unresolved dependencies."
        )
    except Exception as exc:
        if not result.blocking_issues:
            result.blocking_issues.append(str(exc))
        result.ok = False
        result.code = "texture_port_failed"
        result.message = f"Vanilla texture staging failed: {exc}"
    finally:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


__all__ = [
    "LegacyTexturePortRequest",
    "LegacyTexturePortResult",
    "stage_vanilla_texture_dependencies",
]
