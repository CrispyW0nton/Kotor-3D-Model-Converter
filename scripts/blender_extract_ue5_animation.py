"""Blender-side UE5 FBX animation extraction for Sprint 3 R3.A."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--fbx", required=True, type=Path)
    parser.add_argument("--json", required=True, type=Path)
    parser.add_argument("--action", default="")
    parser.add_argument("--frame-step", type=int, default=1)
    return parser.parse_args(argv)


def quat_wxyz(quat):
    return [float(quat.w), float(quat.x), float(quat.y), float(quat.z)]


def matrix_rows(matrix):
    return [[float(matrix[row][col]) for col in range(4)] for row in range(4)]


def capture_rest_pose_bases(armature):
    """Capture source-bone rest bases before animated frame sampling."""

    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    try:
        bpy.ops.object.mode_set(mode="POSE")
        for pose_bone in armature.pose.bones:
            pose_bone.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
    finally:
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass

    bases = {}
    for bone in armature.data.bones:
        world = armature.matrix_world @ bone.matrix_local
        bases[bone.name] = {
            "world_matrix_at_rest": matrix_rows(world),
            "data_bone_matrix": matrix_rows(bone.matrix_local),
            "head": [float(v) for v in bone.head_local],
            "tail": [float(v) for v in bone.tail_local],
            "rotation_wxyz": quat_wxyz(world.to_quaternion()),
            "location_xyz": [float(v) for v in world.translation],
        }
    return bases


def pick_action(armature, action_name: str):
    if action_name:
        action = bpy.data.actions.get(action_name)
        if action is None:
            raise RuntimeError(f"Action not found: {action_name}")
        return action
    if armature.animation_data and armature.animation_data.action:
        return armature.animation_data.action
    if bpy.data.actions:
        return bpy.data.actions[0]
    raise RuntimeError("No action found in FBX")


def action_entries():
    entries = []
    for action in bpy.data.actions:
        entries.append(
            {
                "name": action.name,
                "frame_start": float(action.frame_range[0]),
                "frame_end": float(action.frame_range[1]),
                "frame_count": int(round(action.frame_range[1] - action.frame_range[0] + 1)),
            }
        )
    return entries


def main():
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(args.fbx))
    bpy.context.view_layer.update()

    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("FBX import produced no armature")
    armature = armatures[0]
    action = pick_action(armature, args.action)
    armature.animation_data_create()
    armature.animation_data.action = action

    frame_start = int(round(action.frame_range[0]))
    frame_end = int(round(action.frame_range[1]))
    step = max(1, int(args.frame_step))
    fps = float(bpy.context.scene.render.fps) / max(1.0, float(bpy.context.scene.render.fps_base))

    source_bones = [bone.name for bone in armature.data.bones]
    parents = {bone.name: bone.parent.name if bone.parent else None for bone in armature.data.bones}
    rest_pose_bases = capture_rest_pose_bases(armature)
    rest_world = {}
    for bone in armature.data.bones:
        world = armature.matrix_world @ bone.matrix_local
        rest_world[bone.name] = {
            "matrix": matrix_rows(world),
            "rotation_wxyz": quat_wxyz(world.to_quaternion()),
            "location_xyz": [float(v) for v in world.translation],
        }

    frames = []
    curves = {name: [] for name in source_bones}
    for frame in range(frame_start, frame_end + 1, step):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        frames.append(frame)
        for pose_bone in armature.pose.bones:
            world = armature.matrix_world @ pose_bone.matrix
            loc, rot, _scale = world.decompose()
            curves[pose_bone.name].append(
                {
                    "frame": int(frame),
                    "time_seconds": float((frame - frame_start) / fps) if fps else 0.0,
                    "rotation_wxyz": quat_wxyz(rot),
                    "location_xyz": [float(loc.x), float(loc.y), float(loc.z)],
                    "matrix": matrix_rows(world),
                }
            )

    meshes = [obj.name for obj in bpy.data.objects if obj.type == "MESH"]
    payload = {
        "success": True,
        "source_fbx": str(args.fbx),
        "armature_name": armature.name,
        "action_name": action.name,
        "actions": action_entries(),
        "source_bone_count": len(source_bones),
        "source_bones": source_bones,
        "bone_parents": parents,
        "rest_world": rest_world,
        "rest_pose_bases": rest_pose_bases,
        "frame_start": frame_start,
        "frame_end": frame_end,
        "frame_count": max(0, len(frames)),
        "frames": frames,
        "fps": fps,
        "mesh_count": len(meshes),
        "meshes": meshes,
        "curves": curves,
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[UE5_ANIM_EXTRACT] {args.json}")


if __name__ == "__main__":
    main()
