"""Regression tests for binary-FBX import fallback through Blender."""

from __future__ import annotations

import json
import pathlib
import base64
import sys
import struct
from types import SimpleNamespace

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.core import gltf_importer as gi  # noqa: E402


def test_fbx_importer_uses_blender_fallback_when_trimesh_rejects_fbx(
    tmp_path,
    monkeypatch,
):
    fake_model = object()
    fbx = tmp_path / "Bendak.fbx"
    fbx.write_bytes(b"Kaydara FBX Binary  \x00\x1a\x00")

    import trimesh

    def reject_fbx(*_args, **_kwargs):
        raise ValueError("file_type 'fbx' not supported")

    monkeypatch.setattr(trimesh, "load", reject_fbx)
    monkeypatch.setattr(
        gi.FBXFallbackImporter,
        "_load_via_blender",
        lambda self, path, **kwargs: fake_model,
    )

    model = gi.FBXFallbackImporter().import_file(str(fbx), model_name="Bendak")

    assert model is fake_model


def test_blender_fallback_converts_then_imports_glb(tmp_path, monkeypatch):
    fbx = tmp_path / "Bendak.fbx"
    fbx.write_bytes(b"fbx")
    blender = tmp_path / "blender.exe"
    blender.write_text("fake", encoding="utf-8")
    fake_model = SimpleNamespace(name="Bendak")
    converted: list[tuple[str, pathlib.Path, pathlib.Path]] = []
    imported: list[pathlib.Path] = []

    def fake_convert(blender_exe, fbx_path, glb_path):
        converted.append((blender_exe, fbx_path, glb_path))
        glb_path.write_bytes(b"glb")

    class _FakeGLTFImporter:
        def import_file(self, path, **_kwargs):
            imported.append(pathlib.Path(path))
            return fake_model

    monkeypatch.setattr(gi, "_candidate_blender_executables", lambda: [str(blender)])
    monkeypatch.setattr(gi, "_convert_fbx_to_glb_with_blender", fake_convert)
    monkeypatch.setattr(gi, "GLTFImporter", _FakeGLTFImporter)

    result = gi.FBXFallbackImporter()._load_via_blender(
        str(fbx),
        model_name="Bendak",
        game_version=gi.GameVersion.K1,
        supermodel="NULL",
        classification="character",
    )

    assert result is fake_model
    assert converted[0][0] == str(blender)
    assert converted[0][1] == fbx
    assert converted[0][2].suffix == ".glb"
    assert imported[0].suffix == ".glb"


def test_candidate_blender_executables_honors_env_path(tmp_path, monkeypatch):
    blender = tmp_path / "blender.exe"
    blender.write_text("fake", encoding="utf-8")
    monkeypatch.setenv("GHOSTRIGGER_BLENDER_PATH", str(blender))
    monkeypatch.setattr(gi.shutil, "which", lambda _name: None)

    candidates = gi._candidate_blender_executables()

    assert candidates[0] == str(blender)


def test_gltf_import_preserves_bone_hierarchy_for_external_skeletons():
    """UE/Blender skeletons must not flatten every joint under the model root."""
    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [
            {"name": "Armature", "translation": [0.0, 0.0, 1.0], "children": [1]},
            {"name": "Pelvis", "translation": [0.0, 0.0, 2.0], "children": [2]},
            {"name": "Head", "translation": [0.0, 0.0, 3.0]},
        ],
    }

    model = gi.GLTFImporter().import_bytes(
        json.dumps(gltf).encode("utf-8"),
        model_name="hierarchy",
    )

    assert model is not None
    armature = model.find_node("Armature")
    pelvis = model.find_node("Pelvis")
    head = model.find_node("Head")
    assert armature is not None
    assert pelvis is not None
    assert head is not None
    assert armature.parent is model.root_node
    assert pelvis.parent is armature
    assert head.parent is pelvis
    assert head.bone_world_position() == (0.0, 0.0, 6.0)


def test_gltf_import_uses_parentless_nodes_when_scene_roots_are_absent():
    gltf = {
        "asset": {"version": "2.0"},
        "nodes": [
            {"name": "Root", "children": [1]},
            {"name": "Child", "translation": [1.0, 2.0, 3.0]},
        ],
    }

    model = gi.GLTFImporter().import_bytes(
        json.dumps(gltf).encode("utf-8"),
        model_name="fallback_roots",
    )

    assert model is not None
    root = model.find_node("Root")
    child = model.find_node("Child")
    assert root is not None
    assert child is not None
    assert root.parent is model.root_node
    assert child.parent is root


def test_gltf_import_bakes_parent_scale_into_bone_offsets():
    """Blender FBX->GLB keeps UE armature scale on the parent node."""
    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [
            {
                "name": "Armature",
                "scale": [10.0, 10.0, 10.0],
                "children": [1],
            },
            {"name": "Head", "translation": [0.0, 0.0, 0.8]},
        ],
    }

    model = gi.GLTFImporter().import_bytes(
        json.dumps(gltf).encode("utf-8"),
        model_name="scaled_armature",
    )

    assert model is not None
    head = model.find_node("Head")
    assert head is not None
    assert head.parent is model.find_node("Armature")
    assert head.bone_world_position() == (0.0, 0.0, 8.0)
    assert head.external_world_position == (0.0, 0.0, 8.0)


def test_gltf_import_flips_texture_coordinates_to_viewport_convention():
    """glTF UVs are upper-left-origin; GhostRigger stores bottom-left V."""
    positions = struct.pack(
        "<9f",
        0.0, 0.0, 0.0,
        1.0, 0.0, 0.0,
        0.0, 1.0, 0.0,
    )
    uvs = struct.pack(
        "<6f",
        0.125, 0.25,
        0.875, 0.5,
        0.25, 0.75,
    )
    indices = struct.pack("<3H", 0, 1, 2)
    blob = positions + uvs + indices
    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "buffers": [{
            "byteLength": len(blob),
            "uri": "data:application/octet-stream;base64,"
            + base64.b64encode(blob).decode("ascii"),
        }],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(positions)},
            {"buffer": 0, "byteOffset": len(positions), "byteLength": len(uvs)},
            {
                "buffer": 0,
                "byteOffset": len(positions) + len(uvs),
                "byteLength": len(indices),
            },
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
            },
            {
                "bufferView": 1,
                "componentType": 5126,
                "count": 3,
                "type": "VEC2",
            },
            {
                "bufferView": 2,
                "componentType": 5123,
                "count": 3,
                "type": "SCALAR",
            },
        ],
        "meshes": [{
            "name": "uv_mesh",
            "primitives": [{
                "attributes": {"POSITION": 0, "TEXCOORD_0": 1},
                "indices": 2,
            }],
        }],
        "nodes": [{"name": "Root", "mesh": 0}],
    }

    model = gi.GLTFImporter()._import_builtin_bytes(
        json.dumps(gltf).encode("utf-8"),
        name="uv_test",
        gv=gi.GameVersion.K1,
        sm="NULL",
        cl="character",
    )

    mesh = model.find_node("uv_mesh")
    assert mesh is not None
    assert mesh.uvs == pytest.approx([
        (0.125, 0.75),
        (0.875, 0.5),
        (0.25, 0.25),
    ])
