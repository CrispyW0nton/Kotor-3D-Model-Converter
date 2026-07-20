"""Shared helpers for exporting KotOR models into Unity asset folders."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .kotor_fbx_manifest import build_kotor_fbx_manifest, inspect_fbx_skin_objects


Exporter = Callable[[Any, Path, bool], bool]


def asset_relative(path: Path, unity_project: Path) -> str:
    """Return a Unity-project-relative asset path using forward slashes."""
    try:
        relative = path.resolve().relative_to(unity_project.resolve())
    except ValueError as exc:
        raise ValueError(f"output path must be inside Unity project: {path}") from exc
    return relative.as_posix()


def build_output_paths(
    unity_project: Path,
    asset_subdir: str,
    resref: str,
    extension: str,
) -> tuple[Path, Path]:
    """Return output asset and metadata paths inside a Unity project."""
    clean_subdir = asset_subdir.strip().strip("/\\")
    out_dir = unity_project / clean_subdir
    asset_path = out_dir / f"{resref}.{extension.lstrip('.')}"
    metadata_path = out_dir / f"{resref}.ghostrigger.json"
    return asset_path, metadata_path


def summarize_model(
    model: Any,
    game: str,
    resref: str,
    asset_path: Path,
    unity_project: Path,
    *,
    source_path: str = "",
) -> dict[str, Any]:
    """Build the JSON metadata written beside a Unity transfer."""
    metadata = build_kotor_fbx_manifest(
        model,
        asset_path,
        source_path=source_path,
        game=game,
        resref=resref,
        target_engine="unity",
        compatibility_profile="unity",
    )
    metadata["tool"] = "ghostrigger.export_model_for_unity"
    unity_metadata = dict(metadata.get("unity") or {})
    unity_metadata["asset_path"] = asset_relative(asset_path, unity_project)
    metadata["unity"] = unity_metadata
    metadata["animations"] = [getattr(anim, "name", "") for anim in (getattr(model, "animations", []) or [])]
    return metadata


def export_model_for_unity(
    model: Any,
    *,
    game: str,
    resref: str,
    asset_name: str | None = None,
    unity_project: Path,
    asset_subdir: str,
    extension: str,
    export_rigging: bool,
    exporter: Exporter,
    source_path: str = "",
) -> dict[str, Any]:
    """Export a parsed model to Unity and write GhostRigger metadata."""
    output_name = asset_name or resref
    asset_path, metadata_path = build_output_paths(unity_project, asset_subdir, output_name, extension)
    asset_relative(asset_path, unity_project)
    asset_path.parent.mkdir(parents=True, exist_ok=True)

    if not exporter(model, asset_path, export_rigging):
        raise RuntimeError(f"exporter returned False for {asset_path}")
    if not asset_path.exists():
        raise RuntimeError(f"exporter did not create {asset_path}")

    metadata = summarize_model(
        model,
        game,
        resref,
        asset_path,
        unity_project,
        source_path=source_path,
    )
    if extension.lower().lstrip(".") == "fbx":
        diagnostics = inspect_fbx_skin_objects(asset_path)
        fbx_metadata = dict(metadata.get("fbx") or {})
        fbx_metadata["diagnostics"] = diagnostics
        fbx_metadata.update(diagnostics)
        metadata["fbx"] = fbx_metadata
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "status": "ok",
        "asset": str(asset_path),
        "metadata": str(metadata_path),
        "unity_asset_path": metadata["unity"]["asset_path"],
        "counts": metadata["counts"],
        "animations": metadata["animations"],
        "source": metadata["source"],
    }
