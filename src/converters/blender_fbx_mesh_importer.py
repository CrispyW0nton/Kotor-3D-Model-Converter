"""Blender-backed FBX mesh preview importer.

This importer is for viewport/model preview. It does not replace the Retarget
Workbench animation importer, which produces ``SourceSkeletonClip`` data.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any

from src.core.geometry.model_data import (
    BoneWeight,
    GameVersion,
    KotorModel,
    ModelNode,
    NodeFlags,
    VertexSkinData,
)
from src.core.retargeting.fbx_exporter import FBXExportFailure, find_blender_executable


REPO_ROOT = Path(__file__).resolve().parents[2]
BLENDER_MESH_SCRIPT = REPO_ROOT / "scripts" / "blender_extract_fbx_mesh.py"


class BlenderFbxMeshImportError(RuntimeError):
    """Raised when Blender cannot produce preview mesh data from an FBX file."""


def import_fbx_mesh_with_blender(
    path: str | Path,
    *,
    model_name: str = "",
    game_version: GameVersion = GameVersion.K1,
    supermodel: str = "NULL",
    classification: str = "character",
    blender_executable: str | Path | None = None,
    timeout: int = 300,
) -> KotorModel:
    """Import FBX renderable mesh geometry through Blender's FBX importer."""

    source = Path(path)
    if not source.exists():
        raise BlenderFbxMeshImportError(f"FBX source file not found: {source}")
    if not BLENDER_MESH_SCRIPT.exists():
        raise BlenderFbxMeshImportError(f"Blender mesh extraction script not found: {BLENDER_MESH_SCRIPT}")

    try:
        blender = find_blender_executable(blender_executable)
    except FBXExportFailure as exc:
        raise BlenderFbxMeshImportError(str(exc)) from exc

    output_json = _output_json_path(source)
    cmd = [
        str(blender),
        "--background",
        "--python",
        str(BLENDER_MESH_SCRIPT),
        "--",
        "--fbx",
        str(source),
        "--json",
        str(output_json),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    log_path = output_json.with_suffix(".blender.log")
    log_path.write_text(
        f"COMMAND:\n{' '.join(cmd)}\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}\n",
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise BlenderFbxMeshImportError(
            f"Blender FBX mesh import failed with code {proc.returncode}: {proc.stderr[-1600:]}"
        )
    if not output_json.exists():
        raise BlenderFbxMeshImportError("Blender completed but did not write FBX mesh JSON.")

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    if not payload.get("success"):
        errors = "; ".join(str(error) for error in payload.get("errors", []) if str(error).strip())
        raise BlenderFbxMeshImportError(errors or "Blender FBX mesh extraction failed.")
    return model_from_blender_fbx_mesh_payload(
        payload,
        model_name=model_name or source.stem[:32],
        game_version=game_version,
        supermodel=supermodel,
        classification=classification,
    )


def model_from_blender_fbx_mesh_payload(
    payload: dict[str, Any],
    *,
    model_name: str,
    game_version: GameVersion,
    supermodel: str = "NULL",
    classification: str = "character",
) -> KotorModel:
    """Convert Blender mesh JSON into a viewport-friendly ``KotorModel``."""

    meshes = list(payload.get("meshes") or [])
    if not meshes:
        raise BlenderFbxMeshImportError("FBX file imported through Blender but contains no mesh geometry.")

    model = KotorModel(
        name=(model_name or "fbx_mesh")[:32],
        supermodel=supermodel,
        game_version=game_version,
        classification=classification,
    )
    root = ModelNode(name=model.name, flags=int(NodeFlags.HEADER))
    model.root_node = root
    setattr(model, "_gr_blender_fbx_mesh_preview", True)
    setattr(model, "_gr_fbx_mesh_count", len(meshes))
    setattr(model, "_gr_fbx_armatures", list(payload.get("armatures") or []))
    setattr(model, "_gr_fbx_actions", list(payload.get("actions") or []))

    for index, mesh in enumerate(meshes):
        is_skin = bool(mesh.get("is_skin") and mesh.get("bone_map") and mesh.get("skin_data"))
        node = ModelNode(
            name=str(mesh.get("name") or f"mesh_{index}")[:32],
            flags=int(NodeFlags.HEADER | (NodeFlags.SKIN if is_skin else NodeFlags.MESH)),
            parent=root,
        )
        node.vertices = [_triple(vertex) for vertex in mesh.get("vertices") or []]
        node.normals = [_triple(normal) for normal in mesh.get("normals") or []]
        node.uvs = [_pair(uv) for uv in mesh.get("uvs") or []]
        node.faces = [_face(face) for face in mesh.get("faces") or []]
        materials = list(mesh.get("materials") or [])
        material = materials[0] if materials else {}
        node.texture = str(material.get("texture") or material.get("name") or "")[:32]
        diffuse = material.get("diffuse")
        if isinstance(diffuse, (list, tuple)) and len(diffuse) >= 3:
            node.diffuse = (float(diffuse[0]), float(diffuse[1]), float(diffuse[2]))
        node.render = True
        node._imported = True
        node.vertex_space = 1
        if is_skin:
            node.bone_map = [str(name) for name in (mesh.get("bone_map") or [])]
            node.skin_data = [_skin_vertex(row) for row in (mesh.get("skin_data") or [])]
            if len(node.skin_data) < len(node.vertices):
                node.skin_data.extend(VertexSkinData() for _ in range(len(node.vertices) - len(node.skin_data)))
            elif len(node.skin_data) > len(node.vertices):
                node.skin_data = node.skin_data[: len(node.vertices)]
        node.compute_bounds()
        root.children.append(node)

    model.compute_bounds()
    setattr(model, "_gr_bounds_prepared", True)
    setattr(model, "_gr_render_bounds", (model.bb_min, model.bb_max))
    return model


def _output_json_path(source: Path) -> Path:
    env_root = os.environ.get("GHOSTRIGGER_FBX_IMPORT_CACHE")
    root = Path(env_root) if env_root else Path(tempfile.gettempdir()) / "ghostrigger_fbx_import"
    root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(
        f"{source.resolve()}|{source.stat().st_mtime_ns}|{source.stat().st_size}|mesh".encode("utf-8")
    ).hexdigest()[:12]
    return root / f"{source.stem}_{digest}_mesh.json"


def _triple(values: Any) -> tuple[float, float, float]:
    raw = list(values or (0.0, 0.0, 0.0))
    return (float(raw[0]), float(raw[1]), float(raw[2]))


def _pair(values: Any) -> tuple[float, float]:
    raw = list(values or (0.0, 0.0))
    return (float(raw[0]), float(raw[1]))


def _face(values: Any) -> tuple[int, int, int]:
    raw = list(values or (0, 0, 0))
    return (int(raw[0]), int(raw[1]), int(raw[2]))


def _skin_vertex(values: Any) -> VertexSkinData:
    influences: list[BoneWeight] = []
    for entry in list(values or [])[:4]:
        if not isinstance(entry, dict):
            continue
        try:
            bone_index = int(entry.get("bone_index", 0))
            weight = float(entry.get("weight", 0.0))
        except (TypeError, ValueError):
            continue
        if bone_index < 0 or weight <= 0.0:
            continue
        influences.append(BoneWeight(bone_index=bone_index, weight=weight))
    skin = VertexSkinData(influences=influences)
    skin.normalize()
    return skin
