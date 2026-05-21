"""Unreal Python script for Sprint 3 Gate 2 sample animation export.

Run inside UnrealEditor-Cmd with ``-ExecutePythonScript``. This file is kept in
the repo so the Gate 2 export is reproducible instead of a one-off UI click.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import unreal


ANIM_PATH = "/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop"
MESH_PATH = "/Game/Characters/UEFN_Mannequin/Meshes/SKM_UEFN_Mannequin"
EXPORT_ROOT = Path(r"C:\Users\NewAdmin\Documents\KaiGenInteractive\AnimationLibrary\Exports")
FBX_PATH = EXPORT_ROOT / "M_Neutral_Stand_Idle_Loop_export.fbx"
META_PATH = EXPORT_ROOT / "M_Neutral_Stand_Idle_Loop_export_metadata.json"


def _set_option(options, name: str, value) -> None:
    try:
        options.set_editor_property(name, value)
    except Exception:
        unreal.log_warning(f"FBX export option not available: {name}")


def _asset_name(asset) -> str:
    try:
        return str(asset.get_name())
    except Exception:
        return str(asset)


def _class_name(asset) -> str:
    try:
        return str(asset.get_class().get_name())
    except Exception:
        return type(asset).__name__


def _animation_metadata(asset, mesh) -> dict:
    data = {
        "animation_asset_path": ANIM_PATH,
        "animation_name": _asset_name(asset),
        "animation_class": _class_name(asset),
        "preview_mesh_path": MESH_PATH,
        "preview_mesh_name": _asset_name(mesh) if mesh else "",
        "preview_mesh_class": _class_name(mesh) if mesh else "",
        "unreal_version": str(unreal.SystemLibrary.get_engine_version()),
    }
    for field, method_name in (
        ("number_of_frames", "get_number_of_frames"),
        ("play_length_seconds", "get_play_length"),
        ("sampling_frame_rate", "get_sampling_frame_rate"),
    ):
        method = getattr(asset, method_name, None)
        if callable(method):
            try:
                data[field] = str(method())
            except Exception as exc:
                data[f"{field}_error"] = str(exc)
    try:
        skeleton = asset.get_editor_property("skeleton")
        data["skeleton_name"] = _asset_name(skeleton)
        data["skeleton_class"] = _class_name(skeleton)
        data["skeleton_path"] = str(skeleton.get_path_name())
    except Exception as exc:
        data["skeleton_error"] = str(exc)
    return data


def main() -> None:
    EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
    asset = unreal.EditorAssetLibrary.load_asset(ANIM_PATH)
    if asset is None:
        raise RuntimeError(f"Could not load animation asset: {ANIM_PATH}")
    mesh = unreal.EditorAssetLibrary.load_asset(MESH_PATH)
    if mesh is None:
        unreal.log_warning(f"Could not load preview mesh: {MESH_PATH}")

    options = unreal.FbxExportOption()
    _set_option(options, "ascii", False)
    _set_option(options, "collision", False)
    _set_option(options, "export_local_time", True)
    _set_option(options, "export_morph_targets", False)
    _set_option(options, "export_preview_mesh", True)
    _set_option(options, "force_front_x_axis", False)
    _set_option(options, "level_of_detail", False)
    _set_option(options, "map_skeletal_motion_to_root", False)

    task = unreal.AssetExportTask()
    task.set_editor_property("object", asset)
    task.set_editor_property("filename", str(FBX_PATH))
    task.set_editor_property("automated", True)
    task.set_editor_property("prompt", False)
    task.set_editor_property("replace_identical", True)
    task.set_editor_property("options", options)

    ok = unreal.Exporter.run_asset_export_task(task)
    metadata = _animation_metadata(asset, mesh)
    metadata.update(
        {
            "export_ok": bool(ok),
            "fbx_path": str(FBX_PATH),
            "fbx_exists": FBX_PATH.exists(),
            "fbx_size_bytes": FBX_PATH.stat().st_size if FBX_PATH.exists() else 0,
            "export_options": {
                "format": "FBX",
                "export_preview_mesh": True,
                "export_skeleton": True,
                "export_morph_targets": False,
                "export_local_time": True,
                "export_in_world_space": False,
            },
        }
    )
    META_PATH.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    unreal.log(f"[GATE2_EXPORT_METADATA] {META_PATH}")
    if not ok or not FBX_PATH.exists() or os.path.getsize(FBX_PATH) <= 0:
        raise RuntimeError(f"FBX export failed: {FBX_PATH}")
    unreal.log(f"[GATE2_EXPORT_SUCCESS] {FBX_PATH}")


main()
