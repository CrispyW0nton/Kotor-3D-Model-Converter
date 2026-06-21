"""Export Maya polygon primitive reference fixtures for Map Studio.

Run this with Autodesk Maya's Python, for example:

    "C:\\Program Files\\Autodesk\\Maya2025\\bin\\mayapy.exe" ^
        tools\\maya\\export_maya_polygon_primitives.py ^
        --output docs\\knowledgebase\\maya_primitives\\maya2025

The generated FBX/MA/OBJ files and JSON metadata are reference fixtures. They
document Maya's default polygon primitive topology so GhostRigger's Map Studio
primitive builders can intentionally match or deliberately diverge from them.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import maya.standalone


PrimitiveFactory = Callable[[Any], tuple[str, str]]


def _factory_options(options: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in options.items() if key != "name"}


def _primitive_factories(cmds: Any) -> dict[str, tuple[str, dict[str, Any], Callable[[], str]]]:
    return {
        "cube": (
            "polyCube",
            {"w": 1.0, "h": 1.0, "d": 1.0, "sx": 1, "sy": 1, "sz": 1, "name": "maya_cube"},
            lambda: cmds.polyCube(w=1.0, h=1.0, d=1.0, sx=1, sy=1, sz=1, name="maya_cube")[0],
        ),
        "sphere": (
            "polySphere",
            {"r": 0.5, "sx": 16, "sy": 8, "name": "maya_sphere"},
            lambda: cmds.polySphere(r=0.5, sx=16, sy=8, name="maya_sphere")[0],
        ),
        "cylinder": (
            "polyCylinder",
            {"r": 0.5, "h": 1.0, "sx": 16, "sy": 1, "sz": 1, "name": "maya_cylinder"},
            lambda: cmds.polyCylinder(r=0.5, h=1.0, sx=16, sy=1, sz=1, name="maya_cylinder")[0],
        ),
        "cone": (
            "polyCone",
            {"r": 0.5, "h": 1.0, "sx": 16, "sy": 1, "name": "maya_cone"},
            lambda: cmds.polyCone(r=0.5, h=1.0, sx=16, sy=1, name="maya_cone")[0],
        ),
        "torus": (
            "polyTorus",
            {"r": 0.35, "sr": 0.12, "sx": 16, "sy": 8, "name": "maya_torus"},
            lambda: cmds.polyTorus(r=0.35, sr=0.12, sx=16, sy=8, name="maya_torus")[0],
        ),
        "plane": (
            "polyPlane",
            {"w": 1.0, "h": 1.0, "sx": 1, "sy": 1, "name": "maya_plane"},
            lambda: cmds.polyPlane(w=1.0, h=1.0, sx=1, sy=1, name="maya_plane")[0],
        ),
        "platonic_solid": (
            "polyPlatonicSolid",
            {"r": 0.5, "name": "maya_platonic_solid"},
            lambda: cmds.polyPlatonicSolid(r=0.5, name="maya_platonic_solid")[0],
        ),
        "pyramid": (
            "polyPyramid",
            {"w": 1.0, "ns": 4, "name": "maya_pyramid"},
            lambda: cmds.polyPyramid(w=1.0, ns=4, name="maya_pyramid")[0],
        ),
        "prism": (
            "polyPrism",
            {"w": 1.0, "l": 1.0, "sc": 4, "name": "maya_prism"},
            lambda: cmds.polyPrism(w=1.0, l=1.0, sc=4, name="maya_prism")[0],
        ),
        "pipe": (
            "polyPipe",
            {"r": 0.5, "h": 1.0, "t": 0.1, "sa": 16, "sh": 1, "name": "maya_pipe"},
            lambda: cmds.polyPipe(r=0.5, h=1.0, t=0.1, sa=16, sh=1, name="maya_pipe")[0],
        ),
        "helix": (
            "polyHelix",
            {"c": 2, "h": 1.0, "w": 0.1, "r": 0.35, "sa": 16, "sco": 8, "name": "maya_helix"},
            lambda: cmds.polyHelix(c=2, h=1.0, w=0.1, r=0.35, sa=16, sco=8, name="maya_helix")[0],
        ),
    }


def _path_for_mel(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def _face_degree_histogram(cmds: Any, mesh: str) -> dict[str, int]:
    histogram: Counter[int] = Counter()
    for line in cmds.polyInfo(mesh, faceToVertex=True) or []:
        tokens = line.replace(":", " ").split()
        if len(tokens) >= 3:
            histogram[len(tokens) - 2] += 1
    return {str(key): histogram[key] for key in sorted(histogram)}


def _mesh_metadata(cmds: Any, mesh: str, primitive_id: str, command: str, options: dict[str, Any]) -> dict[str, Any]:
    shape = (cmds.listRelatives(mesh, shapes=True, fullPath=False) or [""])[0]
    bbox = cmds.exactWorldBoundingBox(mesh)
    min_xyz = [float(bbox[0]), float(bbox[1]), float(bbox[2])]
    max_xyz = [float(bbox[3]), float(bbox[4]), float(bbox[5])]
    return {
        "primitive_id": primitive_id,
        "maya_transform": mesh,
        "maya_shape": shape,
        "maya_command": command,
        "maya_options": _factory_options(options),
        "vertices": int(cmds.polyEvaluate(mesh, vertex=True)),
        "edges": int(cmds.polyEvaluate(mesh, edge=True)),
        "faces": int(cmds.polyEvaluate(mesh, face=True)),
        "triangles": int(cmds.polyEvaluate(mesh, triangle=True)),
        "uvs": int(cmds.polyEvaluate(mesh, uvcoord=True)),
        "shells": int(cmds.polyEvaluate(mesh, shell=True)),
        "bounds": {
            "min": min_xyz,
            "max": max_xyz,
            "size": [max_xyz[index] - min_xyz[index] for index in range(3)],
        },
        "face_degree_histogram": _face_degree_histogram(cmds, mesh),
    }


def _load_export_plugins(cmds: Any) -> dict[str, bool]:
    result = {"fbxmaya": False, "objExport": False}
    for plugin in tuple(result):
        try:
            cmds.loadPlugin(plugin, quiet=True)
            result[plugin] = True
        except Exception:
            result[plugin] = False
    return result


def _export_selected_fbx(cmds: Any, mel: Any, path: Path) -> bool:
    try:
        mel.eval("FBXExportSmoothingGroups -v true")
        mel.eval("FBXExportTangents -v true")
        mel.eval("FBXExportTriangulate -v false")
        mel.eval(f'FBXExport -f "{_path_for_mel(path)}" -s')
        return True
    except Exception as exc:
        print(f"FBX export skipped for {path.name}: {exc}")
        return False


def _export_selected_obj(cmds: Any, path: Path) -> bool:
    try:
        cmds.file(
            str(path.resolve()),
            force=True,
            options="groups=1;ptgroups=1;materials=0;smoothing=1;normals=1",
            typ="OBJexport",
            exportSelected=True,
        )
        return True
    except Exception as exc:
        print(f"OBJ export skipped for {path.name}: {exc}")
        return False


def _export_selected_ma(cmds: Any, path: Path) -> bool:
    cmds.file(str(path.resolve()), force=True, typ="mayaAscii", exportSelected=True)
    return True


def _arrange_reference_scene(cmds: Any, meshes: list[str]) -> None:
    spacing = 2.0
    columns = 4
    for index, mesh in enumerate(meshes):
        x = (index % columns) * spacing
        z = (index // columns) * spacing
        cmds.xform(mesh, translation=(x, 0.0, z), worldSpace=True)


def export_primitives(output: Path) -> dict[str, Any]:
    maya.standalone.initialize(name="python")
    import maya.cmds as cmds
    import maya.mel as mel

    output.mkdir(parents=True, exist_ok=True)
    exports_dir = output / "exports"
    metadata_dir = output / "metadata"
    exports_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    plugins = _load_export_plugins(cmds)
    factories = _primitive_factories(cmds)
    primitive_records: list[dict[str, Any]] = []

    for primitive_id, (command, options, factory) in factories.items():
        cmds.file(new=True, force=True)
        mesh = factory()
        cmds.select(mesh, replace=True)
        metadata = _mesh_metadata(cmds, mesh, primitive_id, command, options)
        metadata["exports"] = {}
        metadata["exports"]["maya_ascii"] = _export_selected_ma(cmds, exports_dir / f"{primitive_id}.ma")
        if plugins["fbxmaya"]:
            metadata["exports"]["fbx"] = _export_selected_fbx(cmds, mel, exports_dir / f"{primitive_id}.fbx")
        else:
            metadata["exports"]["fbx"] = False
        if plugins["objExport"]:
            metadata["exports"]["obj"] = _export_selected_obj(cmds, exports_dir / f"{primitive_id}.obj")
        else:
            metadata["exports"]["obj"] = False
        (metadata_dir / f"{primitive_id}.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        primitive_records.append(metadata)

    cmds.file(new=True, force=True)
    meshes = []
    for primitive_id, (_command, _options, factory) in factories.items():
        mesh = factory()
        cmds.rename(mesh, f"ref_{primitive_id}")
        meshes.append(f"ref_{primitive_id}")
    _arrange_reference_scene(cmds, meshes)
    cmds.select(meshes, replace=True)
    scene_exports = {
        "maya_ascii": _export_selected_ma(cmds, output / "maya_polygon_primitives_reference_scene.ma"),
        "fbx": _export_selected_fbx(cmds, mel, output / "maya_polygon_primitives_reference_scene.fbx") if plugins["fbxmaya"] else False,
        "obj": _export_selected_obj(cmds, output / "maya_polygon_primitives_reference_scene.obj") if plugins["objExport"] else False,
    }

    summary = {
        "fixture": "maya_polygon_primitives",
        "maya_version": str(cmds.about(version=True)),
        "maya_api_version": int(cmds.about(apiVersion=True)),
        "axis_system": "maya_y_up",
        "unit": "centimeter",
        "output": str(output.resolve()),
        "plugins": plugins,
        "scene_exports": scene_exports,
        "primitive_count": len(primitive_records),
        "primitives": primitive_records,
        "excluded": {
            "polyPrimitive": "Maya internal/generic constructor, not a distinct polygon menu primitive.",
            "polyDisc": "Not available in this Maya 2025 command set.",
            "polySoccerBall": "Not available in this Maya 2025 command set.",
            "polySuperShape": "Not available in this Maya 2025 command set.",
            "polyGear": "Not available in this Maya 2025 command set.",
        },
    }
    (output / "maya_polygon_primitives_manifest.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    maya.standalone.uninitialize()
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/knowledgebase/maya_primitives/maya2025"),
        help="Directory for generated primitive fixtures and metadata.",
    )
    args = parser.parse_args()
    summary = export_primitives(args.output)
    print(f"Exported {summary['primitive_count']} Maya polygon primitive fixtures to {summary['output']}")
    for primitive in summary["primitives"]:
        bounds = primitive["bounds"]["size"]
        print(
            f"- {primitive['primitive_id']}: "
            f"v={primitive['vertices']} e={primitive['edges']} f={primitive['faces']} "
            f"tri={primitive['triangles']} size=({bounds[0]:.3f}, {bounds[1]:.3f}, {bounds[2]:.3f})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
