"""Blender-side inspection for Sprint 3 Gate 2 exported UE5 FBX."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--fbx", required=True, type=Path)
    parser.add_argument("--json", required=True, type=Path)
    parser.add_argument("--screenshot", required=True, type=Path)
    return parser.parse_args(argv)


def quat_wxyz(quat):
    return [float(quat.w), float(quat.x), float(quat.y), float(quat.z)]


def matrix_to_wxyz(matrix):
    return quat_wxyz(matrix.to_quaternion())


def main():
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(args.fbx))
    bpy.context.view_layer.update()

    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("FBX import produced zero armatures")
    armature = armatures[0]
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)

    bpy.context.scene.frame_set(int(bpy.context.scene.frame_start))
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.select_all(action="SELECT")
    bpy.ops.pose.transforms_clear()
    bpy.context.view_layer.update()
    bpy.ops.object.mode_set(mode="OBJECT")

    bone_names = [bone.name for bone in armature.data.bones]
    rest_world_rotations = {}
    rest_world_positions = {}
    bone_parents = {}
    for bone in armature.data.bones:
        world = armature.matrix_world @ bone.matrix_local
        rest_world_rotations[bone.name] = matrix_to_wxyz(world)
        rest_world_positions[bone.name] = [float(v) for v in world.translation]
        bone_parents[bone.name] = bone.parent.name if bone.parent else None

    frame_start = int(bpy.context.scene.frame_start)
    frame_end = int(bpy.context.scene.frame_end)
    fps = float(bpy.context.scene.render.fps) / max(1.0, float(bpy.context.scene.render.fps_base))
    actions = [
        {
            "name": action.name,
            "frame_start": float(action.frame_range[0]),
            "frame_end": float(action.frame_range[1]),
            "frame_count": int(round(action.frame_range[1] - action.frame_range[0] + 1)),
        }
        for action in bpy.data.actions
    ]

    pose_bone_angles = {}
    for name in ("upperarm_l", "upperarm_r", "lowerarm_l", "lowerarm_r", "clavicle_l", "clavicle_r"):
        pbone = armature.pose.bones.get(name)
        if pbone is not None:
            euler = pbone.rotation_quaternion.to_euler()
            pose_bone_angles[name] = [float(euler.x), float(euler.y), float(euler.z)]

    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    bbox_points = []
    for obj in meshes:
        for corner in obj.bound_box:
            bbox_points.append(obj.matrix_world @ Vector(corner))
    if bbox_points:
        mn = [min(point[i] for point in bbox_points) for i in range(3)]
        mx = [max(point[i] for point in bbox_points) for i in range(3)]
    else:
        mn = mx = [0.0, 0.0, 0.0]

    bpy.ops.object.select_all(action="DESELECT")
    for obj in [*meshes, armature]:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="OBJECT")
    camera = bpy.data.objects.new("Gate2Camera", bpy.data.cameras.new("Gate2Camera"))
    bpy.context.collection.objects.link(camera)
    center = Vector(((mn[0] + mx[0]) * 0.5, (mn[1] + mx[1]) * 0.5, (mn[2] + mx[2]) * 0.5))
    height = max(0.1, mx[2] - mn[2])
    camera.location = (center.x, center.y - max(4.0, height * 2.6), center.z)
    camera.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = max(height * 1.2, 1.0)
    bpy.context.scene.camera = camera
    bpy.context.scene.render.resolution_x = 1280
    bpy.context.scene.render.resolution_y = 960
    try:
        bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        pass
    light_data = bpy.data.lights.new("Gate2KeyLight", "SUN")
    light = bpy.data.objects.new("Gate2KeyLight", light_data)
    bpy.context.collection.objects.link(light)
    light.rotation_euler = (math.radians(45.0), 0.0, math.radians(25.0))
    light_data.energy = 2.5
    args.screenshot.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.filepath = str(args.screenshot)
    bpy.ops.render.render(write_still=True)

    payload = {
        "fbx_path": str(args.fbx),
        "armature_name": armature.name,
        "bone_count": len(bone_names),
        "bone_names": bone_names,
        "bone_parents": bone_parents,
        "rest_world_rotations_wxyz": rest_world_rotations,
        "rest_world_positions": rest_world_positions,
        "frame_start": frame_start,
        "frame_end": frame_end,
        "frame_count": max(0, frame_end - frame_start + 1),
        "fps": fps,
        "actions": actions,
        "mesh_count": len(meshes),
        "bbox": {"min": mn, "max": mx},
        "pose_bone_euler_xyz": pose_bone_angles,
        "screenshot_path": str(args.screenshot),
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[GATE2_BLENDER_INSPECT] {args.json}")


if __name__ == "__main__":
    main()
