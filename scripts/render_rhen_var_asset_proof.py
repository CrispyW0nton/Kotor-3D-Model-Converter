"""Render an isometric proof sheet for the optional Rhen Var OBJ asset pack.

Run with Blender, not the system Python:
    blender --background --python scripts/render_rhen_var_asset_proof.py -- \
        --output artifacts/rhen_var_proof/assets
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "assets" / "map_studio" / "terrain_kits" / "rhen_var"


def _arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "artifacts" / "rhen_var_proof" / "assets"))
    parser.add_argument("--size", type=int, default=512)
    return parser.parse_args(values)


def _clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.images):
        for datablock in tuple(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def _look_at(camera: bpy.types.Object, target: Vector) -> None:
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def _bounds(objects: tuple[bpy.types.Object, ...]) -> tuple[Vector, Vector]:
    points = tuple(obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box)
    return (
        Vector(tuple(min(point[axis] for point in points) for axis in range(3))),
        Vector(tuple(max(point[axis] for point in points) for axis in range(3))),
    )


def _material(name: str, color: tuple[float, float, float, float], roughness: float) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    if shader is not None:
        shader.inputs["Base Color"].default_value = color
        shader.inputs["Roughness"].default_value = roughness
    return material


def _configure_scene(size: int) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 1.15
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs["Color"].default_value = (0.08, 0.11, 0.17, 1.0)
        background.inputs["Strength"].default_value = 0.55
    scene.render.filepath = ""


def _render_asset(obj_path: Path, output_path: Path, size: int) -> None:
    _clear_scene()
    _configure_scene(size)
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=str(obj_path), forward_axis="NEGATIVE_Y", up_axis="Z")
    imported = tuple(obj for obj in bpy.data.objects if obj not in before and obj.type == "MESH")
    if not imported:
        raise RuntimeError(f"No mesh objects imported from {obj_path}")

    minimum, maximum = _bounds(imported)
    center = (minimum + maximum) * 0.5
    extent = maximum - minimum
    radius = max(1.0, extent.length * 0.5)

    floor_material = _material("Proof floor", (0.08, 0.10, 0.14, 1.0), 0.85)
    bpy.ops.mesh.primitive_plane_add(
        size=max(16.0, max(extent.x, extent.y) * 1.8),
        location=(center.x, center.y, minimum.z - 0.035),
    )
    floor = bpy.context.object
    floor.data.materials.append(floor_material)

    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = max(4.0, max(extent.x, extent.y, extent.z * 1.25) * 1.38)
    camera.location = center + Vector((radius * 1.35, -radius * 1.55, radius * 1.05))
    _look_at(camera, center + Vector((0.0, 0.0, extent.z * 0.04)))
    bpy.context.scene.camera = camera

    for energy, size_value, direction in (
        (2200.0, 8.0, Vector((radius * 0.9, -radius * 0.7, radius * 1.8))),
        (1350.0, 6.0, Vector((-radius * 1.2, radius * 0.8, radius * 0.9))),
    ):
        bpy.ops.object.light_add(type="AREA", location=center + direction)
        light = bpy.context.object
        light.data.energy = energy
        light.data.shape = "DISK"
        light.data.size = size_value
        _look_at(light, center)

    bpy.context.scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)


def main() -> int:
    args = _arguments()
    output_root = Path(args.output).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    obj_paths = tuple(sorted(ASSET_ROOT.glob("rv_*.obj")))
    if not obj_paths:
        raise FileNotFoundError(f"No Rhen Var assets were found in {ASSET_ROOT}")
    for index, obj_path in enumerate(obj_paths, 1):
        print(f"[{index:02d}/{len(obj_paths):02d}] {obj_path.name}", flush=True)
        _render_asset(obj_path, output_root / f"{obj_path.stem}.png", max(256, int(args.size)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
