"""Shared helpers for exporting KotOR models into Unity asset folders."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..geometry.model_data import CharacterMode, detect_character_mode


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
    nodes = list(model.all_nodes())
    mesh_nodes = [node for node in nodes if getattr(node, "is_mesh", False)]
    animations = list(getattr(model, "animations", []) or [])
    try:
        mode = detect_character_mode(model)
    except Exception:
        mode = CharacterMode.AMBIGUOUS

    return {
        "schema_version": 1,
        "tool": "ghostrigger.export_model_for_unity",
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "game": game,
            "resref": resref,
            "path": source_path,
            "supermodel": getattr(model, "supermodel", "") or "",
            "classification": int(getattr(model, "model_type", 0) or 0),
            "character_mode": mode.value,
        },
        "counts": {
            "nodes": len(nodes),
            "mesh_nodes": len(mesh_nodes),
            "vertices": sum(len(getattr(node, "vertices", []) or []) for node in mesh_nodes),
            "faces": sum(len(getattr(node, "faces", []) or []) for node in mesh_nodes),
            "animations": len(animations),
        },
        "animations": [getattr(anim, "name", "") for anim in animations],
        "unity": {
            "asset_path": asset_relative(asset_path, unity_project),
        },
    }


def inspect_fbx_skin_objects(asset_path: Path) -> dict[str, Any]:
    """Return lightweight ASCII FBX diagnostics for Unity import contracts."""
    if asset_path.suffix.lower() != ".fbx" or not asset_path.exists():
        return {"checked": False, "reason": "not_fbx"}
    text = asset_path.read_text(encoding="utf-8", errors="ignore")
    skin_ids = re.findall(r'\bDeformer:\s+(\d+),\s+"[^"]*",\s+"Skin"', text)
    cluster_ids = re.findall(r'\bDeformer:\s+(\d+),\s+"[^"]*",\s+"Cluster"', text)
    legacy_cluster_ids = re.findall(r'\bSubDeformer:\s+(\d+),\s+"[^"]*",\s+"Cluster"', text)
    texture_ids = re.findall(r'\bTexture:\s+(\d+),', text)
    skeleton_attrs = re.findall(r'\bNodeAttribute:\s+\d+,\s+"[^"]*",\s+"Skeleton"', text)
    limb_models = re.findall(r'\bModel:\s+\d+,\s+"[^"]*",\s+"LimbNode"', text)
    bind_poses = re.findall(r'\bPose:\s+\d+,\s+"[^"]*",\s+"BindPose"', text)
    pose_nodes = re.findall(r'\bPoseNode:\s+{', text)
    transform_count = len(re.findall(r'\bTransform:\s+\*16\s+{', text))
    transform_link_count = len(re.findall(r'\bTransformLink:\s+\*16\s+{', text))
    wrap_u_count = len(re.findall(r'\bP:\s+"WrapModeU"', text))
    wrap_v_count = len(re.findall(r'\bP:\s+"WrapModeV"', text))
    animation_stacks = re.findall(r'\bAnimationStack:\s+\d+,', text)
    animation_layers = re.findall(r'\bAnimationLayer:\s+\d+,', text)
    animation_curves = re.findall(r'\bAnimationCurve:\s+\d+,', text)

    object_counts = Counter(skin_ids + cluster_ids)
    duplicate_ids = {
        object_id: count
        for object_id, count in object_counts.items()
        if count > 1
    }
    skin_contract_ok = (
        not skin_ids
        or (
            bool(cluster_ids)
            and bool(skeleton_attrs)
            and bool(bind_poses)
            and transform_count >= len(cluster_ids)
            and transform_link_count >= len(cluster_ids)
        )
    )
    texture_contract_ok = (
        not texture_ids
        or (
            wrap_u_count >= len(texture_ids)
            and wrap_v_count >= len(texture_ids)
        )
    )

    return {
        "checked": True,
        "skin_deformers": len(skin_ids),
        "clusters": len(cluster_ids),
        "legacy_subdeformer_clusters": len(legacy_cluster_ids),
        "skeleton_node_attributes": len(skeleton_attrs),
        "limb_node_models": len(limb_models),
        "bind_poses": len(bind_poses),
        "pose_nodes": len(pose_nodes),
        "cluster_transforms": transform_count,
        "cluster_transform_links": transform_link_count,
        "textures": len(texture_ids),
        "texture_wrap_u": wrap_u_count,
        "texture_wrap_v": wrap_v_count,
        "animation_stacks": len(animation_stacks),
        "animation_layers": len(animation_layers),
        "animation_curves": len(animation_curves),
        "skin_contract_ok": skin_contract_ok,
        "texture_contract_ok": texture_contract_ok,
        "duplicate_object_ids": duplicate_ids,
        "ok": (
            not duplicate_ids
            and not legacy_cluster_ids
            and skin_contract_ok
            and texture_contract_ok
        ),
    }


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
        metadata["fbx"] = inspect_fbx_skin_objects(asset_path)
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
