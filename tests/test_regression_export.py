"""M11/T1101 deterministic golden-file coverage for character exports."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = ROOT / "tests" / "golden" / "export_hashes.json"
K1_PATH = Path(os.environ.get(
    "K1_PATH",
    r"C:\Program Files (x86)\Steam\steamapps\common\swkotor",
))
K2_PATH = Path(os.environ.get(
    "K2_PATH",
    r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II",
))


def _golden_cases() -> list[dict[str, Any]]:
    data = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    return list(data.get("cases", []))


def _resource_manager():
    from src.core.qt_core.assets.resource_manager import ResourceManager

    manager = ResourceManager()
    if K1_PATH.exists():
        manager.set_k1_dir(str(K1_PATH))
    if K2_PATH.exists():
        manager.set_k2_dir(str(K2_PATH))
    return manager


def _load_game_model(game: str, resref: str, scratch: Path):
    from src.core.qt_core.game.kotor_loader import load_model_from_file

    manager = _resource_manager()
    game_key = game.upper()
    mdl = manager.get_mdl(resref, game_key)
    if mdl is None:
        pytest.skip(f"{game}:{resref} is not available in the configured KOTOR install")
    mdx = manager.get_mdx(resref, game_key) or b""
    scratch.mkdir(parents=True, exist_ok=True)
    mdl_path = scratch / f"{resref}.mdl"
    mdx_path = scratch / f"{resref}.mdx"
    mdl_path.write_bytes(mdl)
    mdx_path.write_bytes(mdx)
    return load_model_from_file(mdl_path, mdx_path)


def _model_for_case(case: dict[str, Any], tmp_path: Path):
    if case.get("kind") == "single":
        return _load_game_model(
            str(case["game"]),
            str(case["resref"]),
            tmp_path / "source" / str(case["resref"]),
        )

    if case.get("kind") == "composite":
        from src.core.qt_core.workflow import composite_workflow as cw
        from src.core.qt_core.geometry.model_data import CharacterMode, CharacterScene, PartSlot

        body_resref = str(case["body_resref"])
        head_resref = str(case["head_resref"])
        body = _load_game_model(str(case["game"]), body_resref, tmp_path / "source" / body_resref)
        head = _load_game_model(str(case["game"]), head_resref, tmp_path / "source" / head_resref)
        scene = CharacterScene(game_version=str(case["game"]))
        scene.assign(PartSlot.HEADLESS_BODY, body, resref=body_resref)
        scene.assign(PartSlot.HEAD_SHELL, head, resref=head_resref)
        scene.set_mode(CharacterMode.SUPERMODEL, locked=True)
        model, warnings, message = cw._composite_export_model(scene)
        assert model is not None, f"Composite model could not be built: {message}; {warnings}"
        return model

    raise AssertionError(f"Unknown golden export kind: {case.get('kind')!r}")


def _export_deterministic(model: Any, fmt: str, out_path: Path) -> None:
    if fmt == "fbx":
        from src.converters.mesh_converter import FBXExporter

        ok = FBXExporter()._export_fbx_ascii(model, str(out_path))
    elif fmt == "glb":
        from src.converters.mesh_converter import GLTFExporter

        ok = GLTFExporter()._export_manual(model, str(out_path), True, tex_cache=None)
    else:
        raise AssertionError(f"Unknown golden export format: {fmt!r}")
    assert ok is True
    assert out_path.exists()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fbx_skin_clusters_are_deformer_records(tmp_path: Path) -> None:
    """Unity only binds FBX skinning when Cluster objects are Deformer records."""
    from src.converters.mesh_converter import FBXExporter
    from src.core.geometry.model_data import (
        BoneWeight,
        KotorModel,
        ModelClassification,
        ModelNode,
        NodeFlags,
        VertexSkinData,
    )

    root = ModelNode(name="rootdummy", flags=int(NodeFlags.HEADER))
    bone = ModelNode(name="pelvis_g", flags=0, parent=root)
    root.children.append(bone)

    skin = ModelNode(
        name="torso",
        flags=int(NodeFlags.SKIN),
        parent=bone,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        faces=[(0, 1, 2)],
        texture="torso_diff",
        bone_map=["pelvis_g"],
        skin_data=[
            VertexSkinData([BoneWeight(0, 1.0)]),
            VertexSkinData([BoneWeight(0, 1.0)]),
            VertexSkinData([BoneWeight(0, 1.0)]),
        ],
    )
    bone.children.append(skin)

    model = KotorModel(
        name="unity_skin_cluster_regression",
        model_type=int(ModelClassification.CHARACTER),
        root_node=root,
    )
    out_path = tmp_path / "skin_cluster.fbx"

    assert FBXExporter()._export_fbx_ascii(model, str(out_path)) is True
    text = out_path.read_text(encoding="utf-8")

    assert '\tDeformer: ' in text
    assert '"SubDeformer::pelvis_g", "Cluster"' in text
    assert '\tSubDeformer: ' not in text


def test_fbx_export_flips_kotor_uvs_for_unity_import(tmp_path: Path) -> None:
    """FBX UVs must use the same V conversion as GhostRigger's OBJ/glTF exports."""
    from src.converters.mesh_converter import FBXExporter
    from src.core.geometry.model_data import KotorModel, ModelClassification, ModelNode, NodeFlags

    root = ModelNode(name="rootdummy", flags=int(NodeFlags.HEADER))
    mesh = ModelNode(
        name="uv_probe",
        flags=int(NodeFlags.MESH),
        parent=root,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.25, 0.10), (0.50, 0.25), (0.75, 0.90)],
        uvs_lm=[(0.10, 0.20), (0.30, 0.40), (0.50, 0.60)],
        faces=[(0, 1, 2)],
        texture="uv_probe_diff",
    )
    root.children.append(mesh)
    model = KotorModel(
        name="unity_uv_regression",
        model_type=int(ModelClassification.CHARACTER),
        root_node=root,
    )
    out_path = tmp_path / "uv_probe.fbx"

    assert FBXExporter()._export_fbx_ascii(model, str(out_path)) is True
    text = out_path.read_text(encoding="utf-8")

    assert "a: 0.250000,0.900000,0.500000,0.750000,0.750000,0.100000" in text
    assert "a: 0.100000,0.800000,0.300000,0.600000,0.500000,0.400000" in text


def test_fbx_export_preserves_txi_texture_wrap_modes(tmp_path: Path) -> None:
    """Unity/Unreal imports must receive KotOR TXI clamp-vs-repeat intent."""
    from src.converters.mesh_converter import FBXExporter
    from src.core.geometry.model_data import KotorModel, ModelClassification, ModelNode, NodeFlags

    root = ModelNode(name="rootdummy", flags=int(NodeFlags.HEADER))
    mesh = ModelNode(
        name="wrap_probe",
        flags=int(NodeFlags.MESH),
        parent=root,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (2.0, 0.0), (0.0, 2.0)],
        faces=[(0, 1, 2)],
        texture="wrap_probe_diff",
        txi_clamp_s=True,
        txi_clamp_t=False,
    )
    root.children.append(mesh)
    model = KotorModel(
        name="unity_wrap_regression",
        model_type=int(ModelClassification.CHARACTER),
        root_node=root,
    )
    out_path = tmp_path / "wrap_probe.fbx"

    assert FBXExporter()._export_fbx_ascii(model, str(out_path)) is True
    text = out_path.read_text(encoding="utf-8")

    assert 'P: "WrapModeU","enum","","",1' in text
    assert 'P: "WrapModeV","enum","","",0' in text


def test_fbx_skin_bind_matrices_use_unity_fbx_ascii_order(tmp_path: Path) -> None:
    """Unity bindposes use row-major FBX ASCII TransformLink rotation data."""
    from math import sqrt
    from src.converters.mesh_converter import FBXExporter
    from src.core.geometry.model_data import (
        BoneWeight,
        KotorModel,
        ModelClassification,
        ModelNode,
        NodeFlags,
        VertexSkinData,
    )

    root = ModelNode(name="rootdummy", flags=int(NodeFlags.HEADER))
    bone = ModelNode(
        name="pelvis_g",
        flags=0,
        parent=root,
        rotation=(0.0, 0.0, sqrt(0.5), sqrt(0.5)),
    )
    root.children.append(bone)
    skin = ModelNode(
        name="torso",
        flags=int(NodeFlags.SKIN),
        parent=bone,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        faces=[(0, 1, 2)],
        texture="torso_diff",
        bone_map=["pelvis_g"],
        skin_data=[
            VertexSkinData([BoneWeight(0, 1.0)]),
            VertexSkinData([BoneWeight(0, 1.0)]),
            VertexSkinData([BoneWeight(0, 1.0)]),
        ],
    )
    bone.children.append(skin)
    model = KotorModel(
        name="unity_bind_matrix_regression",
        model_type=int(ModelClassification.CHARACTER),
        root_node=root,
    )
    out_path = tmp_path / "bind_matrix.fbx"

    assert FBXExporter()._export_fbx_ascii(model, str(out_path)) is True
    text = out_path.read_text(encoding="utf-8")

    assert "a: -0.000000,-1.000000,0.000000,0.000000,1.000000,-0.000000,0.000000,0.000000,0.000000,0.000000,1.000000,0.000000,0.000000,0.000000,0.000000,1.000000" in text


def _export_stem(case: dict[str, Any]) -> str:
    if case.get("kind") == "composite":
        return f"{case['body_resref']}_{case['head_resref']}_composite"
    return str(case["resref"])


@pytest.mark.slow
@pytest.mark.parametrize(
    "case",
    _golden_cases(),
    ids=[str(case["id"]) for case in _golden_cases()],
)
def test_t1101_golden_export_hashes(case: dict[str, Any], tmp_path: Path) -> None:
    """Representative KOTOR character exports must stay byte-stable."""
    model = _model_for_case(case, tmp_path)
    for fmt, expected in case["formats"].items():
        suffix = ".fbx" if fmt == "fbx" else ".glb"
        out_path = tmp_path / "exports" / f"{_export_stem(case)}{suffix}"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        _export_deterministic(model, fmt, out_path)

        assert out_path.stat().st_size == int(expected["bytes"])
        assert _sha256(out_path) == expected["sha256"]


def test_t1101_golden_manifest_covers_launch_modes() -> None:
    cases = _golden_cases()
    modes = {str(case.get("mode")) for case in cases}
    assert {"HEADLESS_BODY", "HEAD", "CREATURE", "SUPERMODEL"}.issubset(modes)
    assert all({"fbx", "glb"}.issubset(case.get("formats", {})) for case in cases)
