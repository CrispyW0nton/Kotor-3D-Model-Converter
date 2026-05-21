import asyncio
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
LOCAL_SRC = ROOT / "src"
if str(LOCAL_SRC) not in sys.path:
    sys.path.insert(0, str(LOCAL_SRC))

from src.core.qt_core.export.unity_export_bridge import (
    build_output_paths,
    export_model_for_unity,
    inspect_fbx_skin_objects,
    summarize_model,
)
from src.core.qt_core.export.unity_import_validator import build_unity_import_manifest
from src.core.qt_core.geometry.model_data import BoneWeight, KotorModel, ModelNode, NodeFlags, VertexSkinData
from src.converters.mesh_converter import FBXExporter
from kotormcp.tools import get_all_tools, handle_tool
from kotormcp.tools import ghostrigger


class _Node:
    def __init__(self, name, is_mesh=False, vertices=None, faces=None):
        self.name = name
        self.is_mesh = is_mesh
        self.vertices = vertices or []
        self.faces = faces or []


class _Anim:
    def __init__(self, name):
        self.name = name


class _Model:
    name = "n_darthmalak"
    supermodel = "NULL"
    model_type = 4
    animations = [_Anim("pause1"), _Anim("tlknorm")]

    def all_nodes(self):
        return [
            _Node("n_darthmalak"),
            _Node("headhook"),
            _Node("torso", is_mesh=True, vertices=[1, 2, 3], faces=[1]),
        ]


def test_build_output_paths_stays_inside_unity_assets():
    unity_project = Path("C:/Unity/Kotor-Unity")

    asset_path, metadata_path = build_output_paths(
        unity_project,
        "Assets/KotorImported/MainMenu/Models/Malak",
        "n_darthmalak",
        "fbx",
    )

    assert asset_path == unity_project / "Assets/KotorImported/MainMenu/Models/Malak/n_darthmalak.fbx"
    assert metadata_path == unity_project / "Assets/KotorImported/MainMenu/Models/Malak/n_darthmalak.ghostrigger.json"


def test_summarize_model_records_counts_and_unity_asset_path():
    unity_project = Path("C:/Unity/Kotor-Unity")
    asset_path = unity_project / "Assets/KotorImported/Malak/n_darthmalak.fbx"

    metadata = summarize_model(_Model(), "K1", "n_darthmalak", asset_path, unity_project)

    assert metadata["source"]["game"] == "K1"
    assert metadata["source"]["resref"] == "n_darthmalak"
    assert metadata["counts"]["nodes"] == 3
    assert metadata["counts"]["mesh_nodes"] == 1
    assert metadata["counts"]["vertices"] == 3
    assert metadata["counts"]["faces"] == 1
    assert metadata["counts"]["animations"] == 2
    assert metadata["animations"] == ["pause1", "tlknorm"]
    assert metadata["unity"]["asset_path"] == "Assets/KotorImported/Malak/n_darthmalak.fbx"


def test_mcp_tool_manifest_exposes_unity_export_action():
    names = {tool["name"] for tool in get_all_tools()}

    assert "ghostrigger_export_model_for_unity" in names
    assert "ghostrigger_validate_unity_import" in names


def test_mcp_unity_export_action_writes_asset_and_metadata(monkeypatch):
    out_root = Path(".pytest_tmp_unity_bridge") / "UnityProject"

    class _Locator:
        def locate(self, resref, game, game_path):
            assert resref == "n_darthmalak"
            assert game == "k1"
            return "installation:n_darthmalak.mdl", b"mdl", b"mdx"

    class _Parser:
        def parse(self, mdl_bytes, mdx_bytes, path_label):
            assert mdl_bytes == b"mdl"
            assert mdx_bytes == b"mdx"
            return _Model()

    def _fake_exporter(model, out_path, export_rigging):
        assert export_rigging is True
        out_path.write_text("fbx", encoding="utf-8")
        return True

    services = SimpleNamespace(locator=_Locator(), parser=_Parser(), analyzer=None, registry=None)
    monkeypatch.setattr(ghostrigger, "_get_services", lambda: services)
    monkeypatch.setattr(ghostrigger, "_export_fbx_for_unity", _fake_exporter)

    try:
        result = asyncio.run(handle_tool(
            "ghostrigger_export_model_for_unity",
            {
                "game": "k1",
                "resref": "n_darthmalak",
                "unity_project": str(out_root),
                "asset_subdir": "Assets/KotorImported/Test",
            },
        ))
        payload = json.loads(result["text"])

        assert payload["status"] == "ok"
        assert payload["unity_asset_path"] == "Assets/KotorImported/Test/n_darthmalak.fbx"
        assert Path(payload["asset"]).exists()
        assert Path(payload["metadata"]).exists()
        sidecar = json.loads(Path(payload["metadata"]).read_text(encoding="utf-8"))
        assert sidecar["source"]["path"] == "installation:n_darthmalak.mdl"
        assert sidecar["counts"]["animations"] == 2
        assert sidecar["fbx"]["checked"] is True
    finally:
        shutil.rmtree(out_root, ignore_errors=True)


def test_unity_export_sidecar_records_fbx_skin_diagnostics():
    out_root = Path(".pytest_tmp_unity_bridge") / "UnityProject"

    def _fake_exporter(model, out_path, export_rigging):
        out_path.write_text(
            '\n'.join([
                'Model: 10, "Model::pelvis_g", "LimbNode" {',
                'NodeAttribute: 11, "NodeAttribute::pelvis_g", "Skeleton" {',
                'Deformer: 1, "Deformer::torso_Skin", "Skin" {',
                'Deformer: 2, "SubDeformer::root", "Cluster" {',
                'Transform: *16 {',
                'TransformLink: *16 {',
                'Pose: 3, "Pose::BIND_POSES", "BindPose" {',
                'PoseNode:  {',
                'Texture: 4, "Texture::torso_diff", "" {',
                'P: "WrapModeU","enum","","",0',
                'P: "WrapModeV","enum","","",0',
                'AnimationStack: 5, "AnimStack::pause1", "" {',
                'AnimationLayer: 6, "AnimLayer::pause1", "" {',
                'AnimationCurve: 7, "AnimCurve::pause1", "" {',
            ]),
            encoding="utf-8",
        )
        return True

    try:
        result = export_model_for_unity(
            _Model(),
            game="K1",
            resref="n_darthmalak",
            unity_project=out_root,
            asset_subdir="Assets/KotorImported/Test",
            extension="fbx",
            export_rigging=True,
            exporter=_fake_exporter,
        )
        sidecar = json.loads(Path(result["metadata"]).read_text(encoding="utf-8"))

        fbx = sidecar["fbx"]
        assert fbx["checked"] is True
        assert fbx["skin_deformers"] == 1
        assert fbx["clusters"] == 1
        assert fbx["legacy_subdeformer_clusters"] == 0
        assert fbx["skeleton_node_attributes"] == 1
        assert fbx["limb_node_models"] == 1
        assert fbx["bind_poses"] == 1
        assert fbx["pose_nodes"] == 1
        assert fbx["texture_wrap_u"] == 1
        assert fbx["texture_wrap_v"] == 1
        assert fbx["animation_stacks"] == 1
        assert fbx["animation_layers"] == 1
        assert fbx["animation_curves"] == 1
        assert fbx["skin_contract_ok"] is True
        assert fbx["texture_contract_ok"] is True
        assert fbx["duplicate_object_ids"] == {}
        assert fbx["ok"] is True
    finally:
        shutil.rmtree(out_root, ignore_errors=True)


def test_unity_export_can_use_custom_output_name():
    out_root = Path(".pytest_tmp_unity_bridge") / "UnityProject"

    def _fake_exporter(model, out_path, export_rigging):
        out_path.write_text("fbx", encoding="utf-8")
        return True

    try:
        result = export_model_for_unity(
            _Model(),
            game="K1",
            resref="n_darthmalak",
            asset_name="N_DarthMalak_GhostRiggerFresh",
            unity_project=out_root,
            asset_subdir="Assets/KotorImported/Test",
            extension="fbx",
            export_rigging=True,
            exporter=_fake_exporter,
        )

        assert result["unity_asset_path"] == (
            "Assets/KotorImported/Test/N_DarthMalak_GhostRiggerFresh.fbx"
        )
        sidecar = json.loads(Path(result["metadata"]).read_text(encoding="utf-8"))
        assert sidecar["source"]["resref"] == "n_darthmalak"
    finally:
        shutil.rmtree(out_root, ignore_errors=True)


def test_fbx_skin_diagnostics_flags_legacy_subdeformer_clusters(tmp_path):
    path = tmp_path / "bad.fbx"
    path.write_text(
        '\n'.join([
            'SubDeformer: 42, "SubDeformer::root", "Cluster" {',
            'SubDeformer: 42, "SubDeformer::root", "Cluster" {',
        ]),
        encoding="utf-8",
    )

    diagnostics = inspect_fbx_skin_objects(path)

    assert diagnostics["ok"] is False
    assert diagnostics["clusters"] == 0
    assert diagnostics["legacy_subdeformer_clusters"] == 2


def test_fbx_skin_diagnostics_counts_unity_compatible_cluster_records(tmp_path):
    path = tmp_path / "good.fbx"
    path.write_text(
        '\n'.join([
            'Model: 10, "Model::pelvis_g", "LimbNode" {',
            'NodeAttribute: 11, "NodeAttribute::pelvis_g", "Skeleton" {',
            'Deformer: 41, "Deformer::torso_Skin", "Skin" {',
            'Deformer: 42, "SubDeformer::root", "Cluster" {',
            'Transform: *16 {',
            'TransformLink: *16 {',
            'Pose: 43, "Pose::BIND_POSES", "BindPose" {',
            'PoseNode:  {',
        ]),
        encoding="utf-8",
    )

    diagnostics = inspect_fbx_skin_objects(path)

    assert diagnostics["ok"] is True
    assert diagnostics["skin_deformers"] == 1
    assert diagnostics["clusters"] == 1
    assert diagnostics["legacy_subdeformer_clusters"] == 0


def test_unity_import_manifest_reports_missing_skin_warning():
    transfer = {
        "source": {
            "game": "K1",
            "resref": "n_darthmalak",
            "character_mode": "creature",
        },
        "unity": {
            "asset_path": "Assets/KotorImported/Test/n_darthmalak.fbx",
        },
        "counts": {
            "animations": 2,
        },
        "animations": ["pause1", "tlknorm"],
    }
    unity_summary = {
        "asset_path": "Assets/KotorImported/Test/n_darthmalak.fbx",
        "clips": [{"name": "pause1", "length": 1.0}],
        "renderers": [{"type": "MeshRenderer", "materialCount": 1}],
    }

    manifest = build_unity_import_manifest(transfer, unity_summary)

    assert manifest["status"] == "warning"
    assert manifest["ok"] is True
    assert manifest["counts"]["mesh_renderers"] == 1
    assert manifest["counts"]["skinned_mesh_renderers"] == 0
    assert "tlknorm" in manifest["missing_clips"]
    assert {item["code"] for item in manifest["warnings"]} >= {
        "missing_skinned_renderer",
        "missing_animation_clips",
    }


def test_unity_import_manifest_errors_on_bad_fbx_skin_diagnostics():
    transfer = {
        "source": {"game": "K1", "resref": "n_darthmalak", "character_mode": "creature"},
        "unity": {"asset_path": "Assets/KotorImported/Test/n_darthmalak.fbx"},
        "counts": {"animations": 1},
        "animations": ["pause1"],
        "fbx": {
            "checked": True,
            "ok": False,
            "duplicate_object_ids": {"42": 2},
        },
    }
    unity_summary = {
        "asset_path": "Assets/KotorImported/Test/n_darthmalak.fbx",
        "clips": [{"name": "pause1"}],
        "renderers": [{"type": "SkinnedMeshRenderer", "materialCount": 1, "boneCount": 1, "bindposeCount": 1}],
    }

    manifest = build_unity_import_manifest(transfer, unity_summary)

    assert manifest["status"] == "error"
    assert manifest["ok"] is False
    assert {item["code"] for item in manifest["errors"]} == {"fbx_skin_object_error"}


def test_mcp_unity_import_validator_writes_manifest():
    out_root = Path(".pytest_tmp_unity_bridge") / "validator"
    sidecar = out_root / "n_darthmalak.ghostrigger.json"
    manifest_path = out_root / "validation.json"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(json.dumps({
        "source": {"game": "K1", "resref": "n_darthmalak", "character_mode": "creature"},
        "unity": {"asset_path": "Assets/KotorImported/Test/n_darthmalak.fbx"},
        "counts": {"animations": 1},
        "animations": ["pause1"],
    }), encoding="utf-8")

    try:
        result = asyncio.run(handle_tool(
            "ghostrigger_validate_unity_import",
            {
                "transfer_metadata_path": str(sidecar),
                "unity_summary": {
                    "asset_path": "Assets/KotorImported/Test/n_darthmalak.fbx",
                    "clips": [{"name": "pause1", "length": 1.0}],
                    "renderers": [{
                        "type": "SkinnedMeshRenderer",
                        "materialCount": 2,
                        "boneCount": 14,
                        "bindposeCount": 14,
                    }],
                },
                "output_path": str(manifest_path),
            },
        ))
        payload = json.loads(result["text"])

        assert payload["status"] == "ok"
        assert payload["counts"]["skinned_mesh_renderers"] == 1
        assert manifest_path.exists()
    finally:
        shutil.rmtree(out_root, ignore_errors=True)


def test_fbx_export_merges_duplicate_bone_map_clusters(tmp_path):
    root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
    skin = ModelNode(
        name="torso",
        flags=int(NodeFlags.MESH | NodeFlags.SKIN),
        parent=root,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        faces=[(0, 1, 2)],
        texture="torso",
        bone_map=["root", "root"],
        skin_data=[
            VertexSkinData([BoneWeight(0, 0.25), BoneWeight(1, 0.75)]),
            VertexSkinData([BoneWeight(1, 1.0)]),
            VertexSkinData([BoneWeight(0, 1.0)]),
        ],
    )
    root.children.append(skin)
    model = KotorModel(name="duplicate_cluster_case", root_node=root)
    out_path = tmp_path / "duplicate_cluster_case.fbx"

    assert FBXExporter()._export_fbx_ascii(model, str(out_path))
    text = out_path.read_text(encoding="utf-8")

    assert text.count('"SubDeformer::root", "Cluster"') == 1
    assert "Indexes: *3" in text
    assert "\ta: 0,1,2" in text
