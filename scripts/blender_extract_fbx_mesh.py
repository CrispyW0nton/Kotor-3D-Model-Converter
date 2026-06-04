"""Blender-side FBX mesh extraction for GhostRigger preview imports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import bpy


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--fbx", required=True, type=Path)
    parser.add_argument("--json", required=True, type=Path)
    return parser.parse_args(argv)


def _matrix_rows(matrix):
    return [[float(matrix[row][col]) for col in range(4)] for row in range(4)]


def _vector3(vector):
    return [float(vector.x), float(vector.y), float(vector.z)]


def _material_info(material):
    if material is None:
        return {"name": "", "texture": "", "diffuse": [0.8, 0.8, 0.8]}
    texture = ""
    if material.use_nodes and material.node_tree is not None:
        for node in material.node_tree.nodes:
            if getattr(node, "type", "") == "TEX_IMAGE" and getattr(node, "image", None) is not None:
                texture = Path(str(node.image.name)).stem
                break
    diffuse = list(getattr(material, "diffuse_color", (0.8, 0.8, 0.8, 1.0))[:3])
    return {
        "name": material.name,
        "texture": texture or material.name,
        "diffuse": [float(value) for value in diffuse],
    }


def _mesh_skin_info(obj):
    """Return bone-map metadata for Blender vertex-group skin weights."""

    used_group_indices = set()
    for vertex in obj.data.vertices:
        for group_weight in vertex.groups:
            if float(group_weight.weight) > 1e-8:
                used_group_indices.add(int(group_weight.group))
    if not used_group_indices:
        return False, {}, []

    groups = list(obj.vertex_groups)
    bone_map = []
    group_to_bone = {}
    for group_index in sorted(used_group_indices):
        if group_index < 0 or group_index >= len(groups):
            continue
        local_index = len(bone_map)
        group_to_bone[group_index] = local_index
        bone_map.append(str(groups[group_index].name))
    return bool(bone_map), group_to_bone, bone_map


def _vertex_skin(vertex, group_to_bone):
    influences = []
    for group_weight in vertex.groups:
        bone_index = group_to_bone.get(int(group_weight.group))
        weight = float(group_weight.weight)
        if bone_index is None or weight <= 1e-8:
            continue
        influences.append({"bone_index": int(bone_index), "weight": weight})
    influences.sort(key=lambda item: float(item["weight"]), reverse=True)
    influences = influences[:4]
    total = sum(float(item["weight"]) for item in influences)
    if total > 1e-8:
        for item in influences:
            item["weight"] = float(item["weight"]) / total
    return influences


def _extract_mesh_object(obj, depsgraph):
    evaluated = obj.evaluated_get(depsgraph)
    is_skin, group_to_bone, bone_map = _mesh_skin_info(obj)
    mesh = obj.data if is_skin else evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        uv_layer = mesh.uv_layers.active.data if mesh.uv_layers.active is not None else None
        world = obj.matrix_world if is_skin else evaluated.matrix_world
        normal_matrix = world.to_3x3().inverted_safe().transposed()
        materials = [_material_info(material) for material in obj.data.materials]
        if not materials:
            materials = [_material_info(None)]

        vertices = []
        normals = []
        uvs = []
        faces = []
        face_mats = []
        skin_data = []
        for tri in mesh.loop_triangles:
            face = []
            for loop_index in tri.loops:
                loop = mesh.loops[loop_index]
                vertex = mesh.vertices[loop.vertex_index]
                point = world @ vertex.co
                normal = (normal_matrix @ loop.normal).normalized()
                vertices.append([float(point.x), float(point.y), float(point.z)])
                normals.append([float(normal.x), float(normal.y), float(normal.z)])
                if uv_layer is not None:
                    uv = uv_layer[loop_index].uv
                    uvs.append([float(uv.x), 1.0 - float(uv.y)])
                else:
                    uvs.append([0.0, 0.0])
                if is_skin:
                    skin_data.append(_vertex_skin(vertex, group_to_bone))
                face.append(len(vertices) - 1)
            faces.append(face)
            face_mats.append(int(tri.material_index))
        return {
            "name": obj.name,
            "matrix_world": _matrix_rows(world),
            "is_skin": bool(is_skin),
            "bone_map": bone_map,
            "skin_data": skin_data,
            "vertices": vertices,
            "normals": normals,
            "uvs": uvs,
            "faces": faces,
            "face_mats": face_mats,
            "materials": materials,
        }
    finally:
        if not is_skin:
            evaluated.to_mesh_clear()


def _extract_armature_object(obj):
    """Return rest-pose bone positions for Character Builder auto-fit.

    The importer consumes these as temporary guide joints only. The final KOTOR
    character hierarchy is still cloned from the selected native base model.
    """

    bones = []
    for bone in obj.data.bones:
        world = obj.matrix_world @ bone.matrix_local
        head_world = obj.matrix_world @ bone.head_local
        tail_world = obj.matrix_world @ bone.tail_local
        bones.append({
            "name": str(bone.name),
            "armature": str(obj.name),
            "parent": str(bone.parent.name) if bone.parent is not None else None,
            "world_position": _vector3(world.translation),
            "head_world_position": _vector3(head_world),
            "tail_world_position": _vector3(tail_world),
            "matrix_world": _matrix_rows(world),
            "use_deform": bool(getattr(bone, "use_deform", True)),
        })
    return {
        "name": str(obj.name),
        "matrix_world": _matrix_rows(obj.matrix_world),
        "bones": bones,
    }


def main():
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(args.fbx))
    bpy.context.view_layer.update()

    depsgraph = bpy.context.evaluated_depsgraph_get()
    meshes = [_extract_mesh_object(obj, depsgraph) for obj in bpy.data.objects if obj.type == "MESH"]
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    armature_payloads = [_extract_armature_object(obj) for obj in armatures]
    actions = [
        {
            "name": action.name,
            "frame_start": float(action.frame_range[0]),
            "frame_end": float(action.frame_range[1]),
            "frame_count": int(round(action.frame_range[1] - action.frame_range[0] + 1)),
        }
        for action in bpy.data.actions
    ]
    payload = {
        "success": True,
        "source_fbx": str(args.fbx),
        "mesh_count": len(meshes),
        "meshes": meshes,
        "armature_count": len(armatures),
        "armatures": [obj.name for obj in armatures],
        "armature_bones": [
            bone
            for armature in armature_payloads
            for bone in armature.get("bones", [])
        ],
        "armature_objects": armature_payloads,
        "actions": actions,
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[FBX_MESH_EXTRACT] {args.json}")


if __name__ == "__main__":
    main()
