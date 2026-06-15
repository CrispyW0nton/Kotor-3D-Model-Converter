"""Validation manifest for GhostRigger assets imported into Unity."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _clip_name(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("name", "") or item.get("clip", "") or "")
    return str(getattr(item, "name", "") or "")


def _renderer_type(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("type", "") or item.get("rendererType", "") or "")
    return str(getattr(item, "type", "") or getattr(item, "rendererType", "") or "")


def _renderer_int(item: Any, key: str) -> int:
    if isinstance(item, dict):
        try:
            return int(item.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0
    try:
        return int(getattr(item, key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _material_count(unity_summary: dict[str, Any], renderers: list[Any]) -> int:
    explicit = unity_summary.get("material_count", unity_summary.get("materialCount"))
    if explicit is not None:
        try:
            return int(explicit)
        except (TypeError, ValueError):
            return 0
    materials = unity_summary.get("materials")
    if materials is not None:
        return len(_as_list(materials))
    return sum(_renderer_int(renderer, "materialCount") for renderer in renderers)


def build_unity_import_manifest(
    transfer_metadata: dict[str, Any],
    unity_summary: dict[str, Any],
) -> dict[str, Any]:
    """Compare GhostRigger transfer metadata with Unity import facts."""
    source = dict(transfer_metadata.get("source", {}) or {})
    expected = dict(transfer_metadata.get("unity", {}) or {})
    expected_asset_path = str(expected.get("asset_path", "") or "")
    actual_asset_path = str(
        unity_summary.get("asset_path")
        or unity_summary.get("assetPath")
        or expected_asset_path
        or ""
    )

    expected_clips = [_clip_name(item) for item in _as_list(transfer_metadata.get("animations"))]
    expected_clip_set = {name.lower() for name in expected_clips if name}
    clips = [_clip_name(item) for item in _as_list(unity_summary.get("clips"))]
    clip_set = {name.lower().lstrip("|") for name in clips if name}
    missing_clips = sorted(name for name in expected_clip_set if name and name not in clip_set)

    renderers = _as_list(unity_summary.get("renderers"))
    renderer_types = [_renderer_type(item) for item in renderers if _renderer_type(item)]
    renderer_counts = Counter(renderer_types)
    material_count = _material_count(unity_summary, renderers)
    skinned_count = renderer_counts.get("SkinnedMeshRenderer", 0) + renderer_counts.get(
        "UnityEngine.SkinnedMeshRenderer",
        0,
    )
    mesh_count = renderer_counts.get("MeshRenderer", 0) + renderer_counts.get(
        "UnityEngine.MeshRenderer",
        0,
    )
    bindpose_count = sum(_renderer_int(renderer, "bindposeCount") for renderer in renderers)
    bone_count = sum(_renderer_int(renderer, "boneCount") for renderer in renderers)

    warnings: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    for message in _as_list(unity_summary.get("importer_warnings") or unity_summary.get("warnings")):
        if message:
            warnings.append({"code": "unity_import_warning", "message": str(message)})
    for message in _as_list(unity_summary.get("importer_errors") or unity_summary.get("errors")):
        if message:
            errors.append({"code": "unity_import_error", "message": str(message)})

    if expected_asset_path and actual_asset_path and expected_asset_path != actual_asset_path:
        warnings.append({
            "code": "asset_path_mismatch",
            "message": f"Unity asset path is {actual_asset_path}, expected {expected_asset_path}.",
        })
    if not renderer_types:
        errors.append({"code": "no_renderers", "message": "Unity import produced no renderers."})
    if expected_clip_set and not clip_set:
        warnings.append({"code": "no_animation_clips", "message": "Unity import produced no animation clips."})
    elif missing_clips:
        warnings.append({
            "code": "missing_animation_clips",
            "message": f"Unity import is missing {len(missing_clips)} expected GhostRigger clips.",
        })
    if material_count <= 0 and renderer_types:
        warnings.append({"code": "no_materials", "message": "Unity renderers have no material assignments."})

    fbx_diag = transfer_metadata.get("fbx") or {}
    if isinstance(fbx_diag, dict) and fbx_diag.get("checked") and not fbx_diag.get("ok", True):
        errors.append({
            "code": "fbx_skin_object_error",
            "message": "GhostRigger FBX skin diagnostics found duplicate or invalid deformer object IDs.",
        })

    character_mode = str(source.get("character_mode", "") or "").lower()
    expected_animation_count = int((transfer_metadata.get("counts", {}) or {}).get("animations", 0) or 0)
    if character_mode in {"headless_body", "head", "supermodel", "creature"} and expected_animation_count > 0:
        if skinned_count == 0:
            warnings.append({
                "code": "missing_skinned_renderer",
                "message": "Animated character import has no SkinnedMeshRenderer; deformation may be transform-only or broken.",
            })
        elif bindpose_count == 0:
            warnings.append({
                "code": "missing_bindposes",
                "message": "Skinned renderers exist but report no bindposes.",
            })
        if skinned_count > 0 and bone_count == 0:
            warnings.append({
                "code": "missing_skin_bones",
                "message": "Skinned renderers exist but report no bones.",
            })

    status = "error" if errors else ("warning" if warnings else "ok")
    return {
        "schema_version": 1,
        "tool": "ghostrigger.validate_unity_import",
        "status": status,
        "ok": not errors,
        "source": source,
        "unity": {
            "asset_path": actual_asset_path,
            "expected_asset_path": expected_asset_path,
        },
        "counts": {
            "clips": len(clips),
            "expected_clips": len(expected_clip_set),
            "missing_clips": len(missing_clips),
            "renderers": len(renderer_types),
            "mesh_renderers": mesh_count,
            "skinned_mesh_renderers": skinned_count,
            "materials": material_count,
            "skin_bones": bone_count,
            "bindposes": bindpose_count,
        },
        "clips": clips,
        "missing_clips": missing_clips,
        "renderer_types": dict(renderer_counts),
        "warnings": warnings,
        "errors": errors,
    }


def validate_unity_import_file(
    transfer_metadata_path: Path,
    unity_summary: dict[str, Any],
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Read a GhostRigger transfer sidecar and optionally write a manifest."""
    import json

    transfer_metadata = json.loads(transfer_metadata_path.read_text(encoding="utf-8"))
    manifest = build_unity_import_manifest(transfer_metadata, unity_summary)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
