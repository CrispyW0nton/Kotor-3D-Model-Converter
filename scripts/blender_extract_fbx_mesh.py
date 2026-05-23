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


def _extract_mesh_object(obj, depsgraph):
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        uv_layer = mesh.uv_layers.active.data if mesh.uv_layers.active is not None else None
        world = evaluated.matrix_world
        normal_matrix = world.to_3x3().inverted_safe().transposed()
        materials = [_material_info(material) for material in obj.data.materials]
        if not materials:
            materials = [_material_info(None)]

        vertices = []
        normals = []
        uvs = []
        faces = []
        face_mats = []
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
                face.append(len(vertices) - 1)
            faces.append(face)
            face_mats.append(int(tri.material_index))
        return {
            "name": obj.name,
            "matrix_world": _matrix_rows(world),
            "vertices": vertices,
            "normals": normals,
            "uvs": uvs,
            "faces": faces,
            "face_mats": face_mats,
            "materials": materials,
        }
    finally:
        evaluated.to_mesh_clear()


def main():
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(args.fbx))
    bpy.context.view_layer.update()

    depsgraph = bpy.context.evaluated_depsgraph_get()
    meshes = [_extract_mesh_object(obj, depsgraph) for obj in bpy.data.objects if obj.type == "MESH"]
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
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
        "actions": actions,
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[FBX_MESH_EXTRACT] {args.json}")


if __name__ == "__main__":
    main()
