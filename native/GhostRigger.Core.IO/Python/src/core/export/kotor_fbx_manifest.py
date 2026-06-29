"""GhostRigger FBX sidecar metadata for KOTOR/DCC handoff."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from src.core.geometry.model_data import CharacterMode, detect_character_mode


SCHEMA_VERSION = 1

KOTOR_HOOK_ROLES: dict[str, str] = {
    "head_g": "head_attachment_geometry",
    "headhook": "head_attachment_socket",
    "maskhook": "mask_attachment_socket",
    "gogglehook": "goggle_attachment_socket",
    "lhand_g": "left_hand_attachment",
    "rhand_g": "right_hand_attachment",
    "lhand": "left_hand_bone",
    "rhand": "right_hand_bone",
    "camerahook": "camera_anchor",
    "foot_l": "left_foot_alignment",
    "foot_r": "right_foot_alignment",
    "talkdummy": "facial_talk_anchor",
}


def sidecar_path_for_fbx(fbx_path: str | Path) -> Path:
    """Return the canonical GhostRigger metadata path for an FBX file."""
    target = Path(fbx_path)
    return target.with_suffix(".ghostrigger.json")


def inspect_fbx_skin_objects(asset_path: Path) -> dict[str, Any]:
    """Return lightweight ASCII FBX diagnostics for engine import contracts."""
    if asset_path.suffix.lower() != ".fbx" or not asset_path.exists():
        return {"checked": False, "reason": "not_fbx"}
    text = asset_path.read_text(encoding="utf-8", errors="ignore")
    skin_ids = re.findall(r'\bDeformer:\s+(\d+),\s+"[^"]*",\s+"Skin"', text)
    cluster_ids = re.findall(r'\bDeformer:\s+(\d+),\s+"[^"]*",\s+"Cluster"', text)
    legacy_cluster_ids = re.findall(r'\bSubDeformer:\s+(\d+),\s+"[^"]*",\s+"Cluster"', text)
    texture_ids = re.findall(r'\bTexture:\s+(\d+),', text)
    skeleton_attrs = re.findall(
        r'\bNodeAttribute:\s+\d+,\s+"[^"]*",\s+"(?:LimbNode|Limb|Skeleton)"',
        text,
    )
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
    duplicate_ids = {object_id: count for object_id, count in object_counts.items() if count > 1}
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
        "ok": not duplicate_ids and not legacy_cluster_ids and skin_contract_ok and texture_contract_ok,
    }


def build_kotor_fbx_manifest(
    model: Any,
    fbx_path: str | Path,
    *,
    source_path: str = "",
    game: str = "",
    resref: str = "",
    exported_mesh_names: list[str] | None = None,
    fbx_diagnostics: dict[str, Any] | None = None,
    exporter_backend: str = "",
    fbx_format: str = "",
    target_engine: str = "unreal",
) -> dict[str, Any]:
    """Build the sidecar preserving KOTOR semantics that FBX cannot represent."""
    target = Path(fbx_path)
    nodes = _all_nodes(model)
    node_names = {str(getattr(node, "name", "") or "") for node in nodes}
    mesh_nodes = [node for node in nodes if _is_mesh_like(node)]
    exported_set = set(exported_mesh_names or [])
    exported_meshes = [
        node
        for node in mesh_nodes
        if not exported_set or str(getattr(node, "name", "") or "") in exported_set
    ]
    animations = list(getattr(model, "animations", []) or [])
    mode = _detect_mode(model)
    skin_summary = _skin_summary(mesh_nodes, node_names)
    diagnostics = fbx_diagnostics or inspect_fbx_skin_objects(target)
    manifest = {
        "schema": "ghostrigger.kotor_fbx_manifest.v1",
        "schema_version": SCHEMA_VERSION,
        "tool": "ghostrigger.fbx_exporter",
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "game": game or _game_name(model),
            "resref": resref or str(getattr(model, "name", "") or ""),
            "path": source_path,
            "model_name": str(getattr(model, "name", "") or ""),
            "supermodel": str(getattr(model, "supermodel", "") or ""),
            "classification": _safe_int(getattr(model, "model_type", 0), 0),
            "character_mode": mode.value if hasattr(mode, "value") else str(mode),
        },
        "fbx": {
            "path": str(target),
            "sidecar_path": str(sidecar_path_for_fbx(target)),
            "format": fbx_format or ("FBX 7.4 ASCII" if target.exists() else ""),
            "exporter_backend": exporter_backend,
            "diagnostics": diagnostics,
            **diagnostics,
        },
        "coordinate_system": {
            "source": "KOTOR object/bind space",
            "fbx_axis": "Z-up, -Y forward, +X right",
            "unit_scale": "1 KOTOR unit exported as 1 centimeter",
            "uv_v_flipped_for_dcc": True,
            "notes": [
                "KOTOR-specific node semantics are stored in this manifest, not inferred from FBX node type alone.",
                "Use qbone/tbone metadata when rebuilding exact Odyssey skin bind data.",
            ],
        },
        "counts": {
            "nodes": len(nodes),
            "mesh_nodes": len(mesh_nodes),
            "exported_mesh_nodes": len(exported_meshes),
            "skin_mesh_nodes": len([node for node in mesh_nodes if bool(getattr(node, "is_skin", False))]),
            "vertices": sum(len(getattr(node, "vertices", []) or []) for node in exported_meshes),
            "faces": sum(len(getattr(node, "faces", []) or []) for node in exported_meshes),
            "animations": len(animations),
            "hooks": len(_hook_nodes(nodes)),
            "missing_skin_bones": len(skin_summary["missing_bones"]),
        },
        "nodes": [_node_entry(node) for node in nodes],
        "hooks": _hook_nodes(nodes),
        "materials": [_material_entry(node) for node in exported_meshes],
        "meshes": [_mesh_entry(node) for node in exported_meshes],
        "skeleton": {
            "supermodel": str(getattr(model, "supermodel", "") or ""),
            "bone_nodes": [_node_entry(node) for node in nodes if _is_skeleton_node(node)],
            "bone_count": len([node for node in nodes if _is_skeleton_node(node)]),
            "skin": skin_summary,
        },
        "animations": [_animation_entry(anim) for anim in animations],
        "kotor_semantics": {
            "node_flags_preserved": True,
            "texture_slots": ["diffuse", "lightmap", "bump_map", "texture_names"],
            "hook_roles": KOTOR_HOOK_ROLES,
            "supermodel_required_for_animation_inheritance": bool(str(getattr(model, "supermodel", "") or "").strip()),
            "roundtrip_notes": [
                "Do not reorder KOTOR skeleton nodes when reimporting into GhostRigger.",
                "Preserve bone_map order, qbone_list, and tbone_list for MDL/MDX export.",
                "FBX can be consumed by Unreal, while this manifest preserves Odyssey-only authoring state.",
            ],
        },
        "unreal": _unreal_handoff(target_engine),
    }
    manifest["validation"] = _validation_summary(manifest)
    return manifest


def write_kotor_fbx_manifest(
    model: Any,
    fbx_path: str | Path,
    *,
    source_path: str = "",
    game: str = "",
    resref: str = "",
    exported_mesh_names: list[str] | None = None,
    fbx_diagnostics: dict[str, Any] | None = None,
    exporter_backend: str = "",
    fbx_format: str = "",
    target_engine: str = "unreal",
) -> Path:
    """Write and return the canonical FBX sidecar path."""
    manifest = build_kotor_fbx_manifest(
        model,
        fbx_path,
        source_path=source_path,
        game=game,
        resref=resref,
        exported_mesh_names=exported_mesh_names,
        fbx_diagnostics=fbx_diagnostics,
        exporter_backend=exporter_backend,
        fbx_format=fbx_format,
        target_engine=target_engine,
    )
    path = sidecar_path_for_fbx(fbx_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _all_nodes(model: Any) -> list[Any]:
    try:
        return list(model.all_nodes())
    except Exception:
        return []


def _game_name(model: Any) -> str:
    game = getattr(model, "game_version", "")
    return str(getattr(game, "name", game) or "")


def _detect_mode(model: Any) -> CharacterMode:
    try:
        return detect_character_mode(model)
    except Exception:
        return CharacterMode.AMBIGUOUS


def _node_entry(node: Any) -> dict[str, Any]:
    name = str(getattr(node, "name", "") or "")
    parent = getattr(node, "parent", None)
    return {
        "name": name,
        "parent": str(getattr(parent, "name", "") or "") if parent is not None else "",
        "flags": _safe_int(getattr(node, "flags", 0), 0),
        "type": str(getattr(node, "type_label", "") or _node_type(node)),
        "position": _float_list(getattr(node, "position", (0.0, 0.0, 0.0)), 3),
        "rotation_xyzw": _float_list(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0)), 4),
        "render": bool(getattr(node, "render", True)),
        "is_mesh": bool(getattr(node, "is_mesh", False)),
        "is_skin": bool(getattr(node, "is_skin", False)),
        "is_hook": name.lower() in KOTOR_HOOK_ROLES,
        "hook_role": KOTOR_HOOK_ROLES.get(name.lower(), ""),
    }


def _mesh_entry(node: Any) -> dict[str, Any]:
    skin_data = list(getattr(node, "skin_data", []) or [])
    influence_counts = [len(getattr(row, "influences", []) or []) for row in skin_data]
    return {
        "name": str(getattr(node, "name", "") or ""),
        "type": str(getattr(node, "type_label", "") or _node_type(node)),
        "vertices": len(getattr(node, "vertices", []) or []),
        "faces": len(getattr(node, "faces", []) or []),
        "normals": len(getattr(node, "normals", []) or []),
        "tangents": len(getattr(node, "tangents", []) or []),
        "uv_sets": {
            "diffuse": len(getattr(node, "uvs", []) or []),
            "lightmap": len(getattr(node, "uvs_lm", []) or []),
            "uv2": len(getattr(node, "uvs_2", []) or []),
            "uv3": len(getattr(node, "uvs_3", []) or []),
        },
        "skin": {
            "is_skin": bool(getattr(node, "is_skin", False)),
            "bone_map": [str(item or "") for item in (getattr(node, "bone_map", []) or [])],
            "qbone_count": len(getattr(node, "qbone_list", []) or []),
            "tbone_count": len(getattr(node, "tbone_list", []) or []),
            "weighted_vertices": len([count for count in influence_counts if count > 0]),
            "max_influences_per_vertex": max(influence_counts) if influence_counts else 0,
        },
    }


def _material_entry(node: Any) -> dict[str, Any]:
    texture_names = [str(item or "") for item in (getattr(node, "texture_names", []) or [])]
    return {
        "mesh": str(getattr(node, "name", "") or ""),
        "diffuse": str(getattr(node, "texture_clean", "") or getattr(node, "texture", "") or ""),
        "lightmap": str(getattr(node, "lightmap", "") or ""),
        "bump_map": str(getattr(node, "bump_map", "") or getattr(node, "txi_bumpmaptexture", "") or ""),
        "texture_names": texture_names,
        "tex_count": _safe_int(getattr(node, "tex_count", len(texture_names) or 1), 1),
        "face_material_slots": sorted({_safe_int(item, 0) for item in (getattr(node, "face_mats", []) or [])}),
        "txi": {
            "blending": _safe_int(getattr(node, "txi_blending", 0), 0),
            "cube": bool(getattr(node, "txi_cube", False)),
            "proceduretype": str(getattr(node, "txi_proceduretype", "") or ""),
            "envmaptexture": str(getattr(node, "txi_envmaptexture", "") or ""),
            "bumpmaptexture": str(getattr(node, "txi_bumpmaptexture", "") or ""),
            "islightmap": bool(getattr(node, "txi_islightmap", False)),
            "isbumpmap": bool(getattr(node, "txi_isbumpmap", False)),
            "clamp_s": bool(getattr(node, "txi_clamp_s", False)),
            "clamp_t": bool(getattr(node, "txi_clamp_t", False)),
            "alpha_test": _safe_float(getattr(node, "txi_alpha_test", 0.5), 0.5),
        },
    }


def _skin_summary(mesh_nodes: list[Any], node_names: set[str]) -> dict[str, Any]:
    skin_meshes = []
    all_missing: set[str] = set()
    duplicate_maps: dict[str, dict[str, int]] = {}
    over_limit_vertices: dict[str, list[int]] = {}
    unnormalized_vertices: dict[str, list[int]] = {}
    for node in mesh_nodes:
        if not bool(getattr(node, "is_skin", False)):
            continue
        bone_map = [str(item or "") for item in (getattr(node, "bone_map", []) or [])]
        counts = Counter(item for item in bone_map if item)
        duplicates = {name: count for name, count in counts.items() if count > 1}
        if duplicates:
            duplicate_maps[str(getattr(node, "name", "") or "")] = duplicates
        missing = sorted(name for name in counts if name not in node_names)
        all_missing.update(missing)
        skin_rows = list(getattr(node, "skin_data", []) or [])
        over_limit = []
        unnormalized = []
        for index, row in enumerate(skin_rows):
            influences = list(getattr(row, "influences", []) or [])
            positive = [item for item in influences if _safe_float(getattr(item, "weight", 0.0), 0.0) > 0.0]
            if len(positive) > 4:
                over_limit.append(index)
            total = sum(_safe_float(getattr(item, "weight", 0.0), 0.0) for item in positive)
            if positive and abs(total - 1.0) > 0.01:
                unnormalized.append(index)
        if over_limit:
            over_limit_vertices[str(getattr(node, "name", "") or "")] = over_limit[:64]
        if unnormalized:
            unnormalized_vertices[str(getattr(node, "name", "") or "")] = unnormalized[:64]
        skin_meshes.append(
            {
                "mesh": str(getattr(node, "name", "") or ""),
                "bone_map": bone_map,
                "bone_map_unique": list(counts.keys()),
                "missing_bones": missing,
                "duplicate_bone_map_entries": duplicates,
                "qbone_count": len(getattr(node, "qbone_list", []) or []),
                "tbone_count": len(getattr(node, "tbone_list", []) or []),
                "vertex_rows": len(skin_rows),
            }
        )
    return {
        "skin_meshes": skin_meshes,
        "missing_bones": sorted(all_missing),
        "duplicate_bone_map_entries": duplicate_maps,
        "vertices_over_kotor_influence_limit": over_limit_vertices,
        "vertices_with_unnormalized_weights": unnormalized_vertices,
        "kotor_influence_limit": 4,
    }


def _animation_entry(anim: Any) -> dict[str, Any]:
    nodes = list(getattr(anim, "nodes", []) or [])
    controller_types: set[str] = set()
    keyed_nodes = []
    for node in nodes:
        controllers = list(getattr(node, "controllers", []) or [])
        for controller in controllers:
            controller_types.add(str(controller.get("type", "") if isinstance(controller, dict) else ""))
        keyed_nodes.append(
            {
                "name": str(getattr(node, "name", "") or ""),
                "controller_count": len(controllers),
                "controller_types": sorted(
                    str(controller.get("type", "") if isinstance(controller, dict) else "")
                    for controller in controllers
                ),
            }
        )
    return {
        "name": str(getattr(anim, "name", "") or ""),
        "length": _safe_float(getattr(anim, "length", 0.0), 0.0),
        "transition_time": _safe_float(getattr(anim, "transition_time", 0.0), 0.0),
        "anim_root": str(getattr(anim, "anim_root", "") or ""),
        "node_count": len(nodes),
        "controller_types": sorted(item for item in controller_types if item),
        "events": [
            {"time": _safe_float(getattr(event, "time", 0.0), 0.0), "name": str(getattr(event, "name", "") or "")}
            for event in (getattr(anim, "events", []) or [])
        ],
        "nodes": keyed_nodes,
    }


def _hook_nodes(nodes: list[Any]) -> list[dict[str, Any]]:
    hooks = []
    for node in nodes:
        name = str(getattr(node, "name", "") or "")
        role = KOTOR_HOOK_ROLES.get(name.lower())
        if role:
            hooks.append({"name": name, "role": role, "parent": str(getattr(getattr(node, "parent", None), "name", "") or "")})
    return hooks


def _validation_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    warnings = []
    errors = []
    skin = manifest.get("skeleton", {}).get("skin", {})
    if skin.get("missing_bones"):
        warnings.append({"code": "missing_skin_bones", "message": "Some skin bone_map entries do not exist as FBX/KOTOR nodes."})
    if skin.get("vertices_over_kotor_influence_limit"):
        errors.append({"code": "too_many_skin_influences", "message": "Some vertices exceed KOTOR's 4-influence skin limit."})
    fbx_diag = manifest.get("fbx", {}).get("diagnostics", {})
    if fbx_diag.get("checked") and not fbx_diag.get("ok", True):
        warnings.append({"code": "fbx_contract_warning", "message": "FBX text diagnostics reported import-contract issues."})
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def _unreal_handoff(target_engine: str) -> dict[str, Any]:
    return {
        "target": target_engine,
        "recommended_import": {
            "skeletal_mesh": True,
            "import_mesh": True,
            "import_animations": True,
            "import_materials": True,
            "import_textures": False,
            "normal_import_method": "Import Normals and Tangents when tangents are present; otherwise let Unreal compute tangents.",
        },
        "notes": [
            "Use the FBX for Unreal asset creation and the GhostRigger manifest for KOTOR-specific rebuild/round-trip metadata.",
            "If animation inheritance depends on a KOTOR supermodel, keep the manifest with the FBX so the supermodel chain is not lost.",
        ],
    }


def _is_mesh_like(node: Any) -> bool:
    return bool(getattr(node, "is_mesh", False) or getattr(node, "is_skin", False))


def _is_skeleton_node(node: Any) -> bool:
    return bool(getattr(node, "is_dummy", False) or not _is_mesh_like(node))


def _node_type(node: Any) -> str:
    if bool(getattr(node, "is_skin", False)):
        return "skin"
    if bool(getattr(node, "is_mesh", False)):
        return "trimesh"
    return "dummy"


def _float_list(values: Any, count: int) -> list[float]:
    result = [_safe_float(item, 0.0) for item in list(values or [])[:count]]
    while len(result) < count:
        result.append(1.0 if count == 4 and len(result) == 3 else 0.0)
    return result


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
