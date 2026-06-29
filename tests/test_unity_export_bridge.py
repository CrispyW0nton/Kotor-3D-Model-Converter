import asyncio
import json
import re
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
LOCAL_SRC = ROOT / "src"
if str(LOCAL_SRC) not in sys.path:
    sys.path.insert(0, str(LOCAL_SRC))

from src.core.export.unity_export_bridge import (
    build_output_paths,
    export_model_for_unity,
    inspect_fbx_skin_objects,
    summarize_model,
)
from src.core.export.unity_import_validator import build_unity_import_manifest
from src.core.geometry.model_data import Animation, BoneWeight, KotorModel, ModelNode, NodeFlags, VertexSkinData
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
                'NodeAttribute: 11, "NodeAttribute::pelvis_g", "LimbNode" {',
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
            'NodeAttribute: 11, "NodeAttribute::pelvis_g", "LimbNode" {',
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


def test_fbx_export_uses_skeleton_alias_when_mesh_node_is_bone(tmp_path):
    root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
    renderable_bone = ModelNode(
        name="RArm",
        flags=int(NodeFlags.MESH),
        parent=root,
        vertices=[(0.0, 0.0, 0.0), (0.2, 0.0, 0.0), (0.0, 0.2, 0.0)],
        faces=[(0, 1, 2)],
        texture="arm",
    )
    skin = ModelNode(
        name="Legs",
        flags=int(NodeFlags.MESH | NodeFlags.SKIN),
        parent=root,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[(0, 1, 2)],
        texture="legs",
        bone_map=["RArm"],
        skin_data=[
            VertexSkinData([BoneWeight(0, 1.0)]),
            VertexSkinData([BoneWeight(0, 1.0)]),
            VertexSkinData([BoneWeight(0, 1.0)]),
        ],
    )
    root.children.extend([renderable_bone, skin])
    model = KotorModel(name="mesh_bone_alias_case", root_node=root)
    out_path = tmp_path / "mesh_bone_alias_case.fbx"

    assert FBXExporter()._export_fbx_ascii(model, str(out_path))
    text = out_path.read_text(encoding="utf-8")

    mesh_model_id = re.search(r'Model: (\d+), "Model::RArm", "Mesh"', text).group(1)
    alias_model_id = re.search(r'Model: (\d+), "Model::RArm_bone", "LimbNode"', text).group(1)
    cluster_id = re.search(r'Deformer: (\d+), "SubDeformer::RArm", "Cluster"', text).group(1)
    assert f'C: "OO",{alias_model_id},{cluster_id}' in text
    assert f'C: "OO",{mesh_model_id},{cluster_id}' not in text
    assert '"NodeAttribute::RArm_bone", "LimbNode"' in text


def test_fbx_export_animates_skeleton_alias_when_mesh_node_is_bone(tmp_path):
    root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
    renderable_bone = ModelNode(
        name="RArm",
        flags=int(NodeFlags.MESH),
        parent=root,
        vertices=[(0.0, 0.0, 0.0), (0.2, 0.0, 0.0), (0.0, 0.2, 0.0)],
        faces=[(0, 1, 2)],
        texture="arm",
    )
    skin = ModelNode(
        name="Legs",
        flags=int(NodeFlags.MESH | NodeFlags.SKIN),
        parent=root,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[(0, 1, 2)],
        texture="legs",
        bone_map=["RArm"],
        skin_data=[
            VertexSkinData([BoneWeight(0, 1.0)]),
            VertexSkinData([BoneWeight(0, 1.0)]),
            VertexSkinData([BoneWeight(0, 1.0)]),
        ],
    )
    root.children.extend([renderable_bone, skin])
    anim_node = ModelNode(
        name="RArm",
        controllers=[
            {
                "type": 20,
                "times": [0.0, 1.0],
                "values": [(0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.7071068, 0.7071068)],
            }
        ],
    )
    model = KotorModel(
        name="mesh_bone_animation_alias_case",
        root_node=root,
        animations=[Animation(name="turn", length=1.0, anim_root="root", nodes=[anim_node])],
    )
    out_path = tmp_path / "mesh_bone_animation_alias_case.fbx"

    assert FBXExporter()._export_fbx_ascii(model, str(out_path))
    text = out_path.read_text(encoding="utf-8")

    mesh_model_id = re.search(r'Model: (\d+), "Model::RArm", "Mesh"', text).group(1)
    alias_model_id = re.search(r'Model: (\d+), "Model::RArm_bone", "LimbNode"', text).group(1)
    assert re.search(rf'C: "OP",\d+,{alias_model_id},"Lcl Rotation"', text)
    assert not re.search(rf'C: "OP",\d+,{mesh_model_id},"Lcl Rotation"', text)


def test_fbx_export_aliases_animated_rigid_mesh_without_skin_reference(tmp_path):
    root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
    eye = ModelNode(
        name="Rancor_eyeL",
        flags=int(NodeFlags.MESH),
        parent=root,
        position=(0.1, 0.2, 0.3),
        vertices=[(0.0, 0.0, 0.0), (0.2, 0.0, 0.0), (0.0, 0.2, 0.0)],
        uvs=[(0.25, 0.10), (0.75, 0.20), (0.50, 0.90)],
        faces=[(0, 1, 2)],
        texture="eye",
    )
    root.children.append(eye)
    anim_node = ModelNode(
        name="Rancor_eyeL",
        controllers=[
            {
                "type": 8,
                "times": [0.0, 1.0],
                "values": [(0.0, 0.0, 0.0), (0.0, 0.0, 0.1)],
            }
        ],
    )
    model = KotorModel(
        name="animated_rigid_mesh_alias_case",
        root_node=root,
        animations=[Animation(name="blink", length=1.0, anim_root="root", nodes=[anim_node])],
    )
    out_path = tmp_path / "animated_rigid_mesh_alias_case.fbx"

    assert FBXExporter()._export_fbx_ascii(model, str(out_path))
    text = out_path.read_text(encoding="utf-8")

    mesh_model_id = re.search(r'Model: (\d+), "Model::Rancor_eyeL", "Mesh"', text).group(1)
    alias_model_id = re.search(r'Model: (\d+), "Model::Rancor_eyeL_bone", "LimbNode"', text).group(1)
    mesh_block = re.search(
        r'Model: \d+, "Model::Rancor_eyeL", "Mesh" \{(.*?)\n\t\}',
        text,
        re.S,
    ).group(1)

    assert f'C: "OO",{mesh_model_id},{alias_model_id}' in text
    assert re.search(rf'C: "OP",\d+,{alias_model_id},"Lcl Translation"', text)
    assert not re.search(rf'C: "OP",\d+,{mesh_model_id},"Lcl Translation"', text)
    assert 'P: "Lcl Translation","Lcl Translation","","A",0.000000,0.000000,0.000000' in mesh_block
    assert "a: 0.250000,0.900000,0.750000,0.800000,0.500000,0.100000" in text


def test_fbx_export_rotation_curves_are_absolute_local_values(tmp_path):
    root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
    bone = ModelNode(
        name="jaw",
        flags=0,
        parent=root,
        rotation=(0.0, 0.0, 0.3826834, 0.9238795),
    )
    root.children.append(bone)
    anim_node = ModelNode(
        name="jaw",
        controllers=[
            {
                "type": 20,
                "times": [0.0, 1.0],
                "values": [
                    (0.0, 0.0, 0.3826834, 0.9238795),
                    (0.0, 0.0, 0.3826834, 0.9238795),
                ],
            }
        ],
    )
    model = KotorModel(
        name="absolute_rotation_curve_case",
        root_node=root,
        animations=[Animation(name="hold", length=1.0, anim_root="root", nodes=[anim_node])],
    )
    out_path = tmp_path / "absolute_rotation_curve_case.fbx"

    assert FBXExporter()._export_fbx_ascii(model, str(out_path))
    text = out_path.read_text(encoding="utf-8")

    bone_model_id = re.search(r'Model: (\d+), "Model::jaw", "LimbNode"', text).group(1)

    assert re.search(rf'C: "OP",\d+,{bone_model_id},"Lcl Rotation"', text)
    assert "a: 44.999998,44.999998" in text or "a: 45.000000,45.000000" in text


def test_fbx_export_root_skin_influence_is_limb_node(tmp_path):
    root = ModelNode(name="c_rancorS", flags=int(NodeFlags.HEADER))
    skin = ModelNode(
        name="Legs",
        flags=int(NodeFlags.MESH | NodeFlags.SKIN),
        parent=root,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[(0, 1, 2)],
        texture="legs",
        bone_map=["c_rancorS"],
        skin_data=[
            VertexSkinData([BoneWeight(0, 1.0)]),
            VertexSkinData([BoneWeight(0, 1.0)]),
            VertexSkinData([BoneWeight(0, 1.0)]),
        ],
    )
    root.children.append(skin)
    model = KotorModel(name="root_influence_case", root_node=root)
    out_path = tmp_path / "root_influence_case.fbx"

    assert FBXExporter()._export_fbx_ascii(model, str(out_path))
    text = out_path.read_text(encoding="utf-8")

    root_model_id = re.search(r'Model: (\d+), "Model::c_rancorS", "LimbNode"', text).group(1)
    cluster_id = re.search(r'Deformer: (\d+), "SubDeformer::c_rancorS", "Cluster"', text).group(1)
    assert f'C: "OO",{root_model_id},{cluster_id}' in text
    assert '"NodeAttribute::c_rancorS", "LimbNode"' in text


def test_fbx_export_scales_tiny_finger_bone_display_size(tmp_path):
    root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
    hand = ModelNode(name="Ran_handR", flags=int(NodeFlags.HEADER), parent=root, position=(1.0, 0.0, 0.0))
    finger_1 = ModelNode(
        name="Ran_Index_01_R",
        flags=int(NodeFlags.HEADER),
        parent=hand,
        position=(0.09, -0.46, 0.02),
    )
    finger_2 = ModelNode(
        name="Ran_Index_02_R",
        flags=int(NodeFlags.HEADER),
        parent=finger_1,
        position=(0.0, -0.25, 0.0),
    )
    skin = ModelNode(
        name="RArm",
        flags=int(NodeFlags.MESH | NodeFlags.SKIN),
        parent=root,
        vertices=[(0.0, 0.0, 0.0), (0.2, 0.0, 0.0), (0.0, 0.2, 0.0)],
        faces=[(0, 1, 2)],
        texture="arm",
        bone_map=["Ran_Index_01_R"],
        skin_data=[
            VertexSkinData([BoneWeight(0, 1.0)]),
            VertexSkinData([BoneWeight(0, 1.0)]),
            VertexSkinData([BoneWeight(0, 1.0)]),
        ],
    )
    root.children.extend([hand, skin])
    hand.children.append(finger_1)
    finger_1.children.append(finger_2)
    model = KotorModel(name="finger_display_size_case", root_node=root)
    out_path = tmp_path / "finger_display_size_case.fbx"

    assert FBXExporter()._export_fbx_ascii(model, str(out_path))
    text = out_path.read_text(encoding="utf-8")

    finger_attr = re.search(
        r'NodeAttribute: \d+, "NodeAttribute::Ran_Index_01_R", "LimbNode" \{(.*?)\n\t\}',
        text,
        re.S,
    ).group(1)
    size_match = re.search(r'P: "Size", "double", "Number", "",([0-9.]+)', finger_attr)
    limb_match = re.search(r'P: "LimbLength", "double", "Number", "",([0-9.]+)', finger_attr)

    assert size_match is not None
    assert limb_match is not None
    assert float(size_match.group(1)) < 0.35
    assert float(limb_match.group(1)) == float(size_match.group(1))


def test_fbx_export_parents_rigid_mesh_bone_under_alias_at_identity(tmp_path):
    root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
    jaw = ModelNode(
        name="Ran_Jaw",
        flags=int(NodeFlags.MESH),
        parent=root,
        position=(1.0, 2.0, 3.0),
        vertices=[(0.0, 0.0, 0.0), (0.2, 0.0, 0.0), (0.0, 0.2, 0.0)],
        faces=[(0, 1, 2)],
        texture="jaw",
    )
    skin = ModelNode(
        name="torso",
        flags=int(NodeFlags.MESH | NodeFlags.SKIN),
        parent=root,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[(0, 1, 2)],
        texture="torso",
        bone_map=["Ran_Jaw"],
        skin_data=[
            VertexSkinData([BoneWeight(0, 1.0)]),
            VertexSkinData([BoneWeight(0, 1.0)]),
            VertexSkinData([BoneWeight(0, 1.0)]),
        ],
    )
    root.children.extend([jaw, skin])
    model = KotorModel(name="rigid_mesh_bone_parent_case", root_node=root)
    out_path = tmp_path / "rigid_mesh_bone_parent_case.fbx"

    assert FBXExporter()._export_fbx_ascii(model, str(out_path))
    text = out_path.read_text(encoding="utf-8")

    mesh_model_id = re.search(r'Model: (\d+), "Model::Ran_Jaw", "Mesh"', text).group(1)
    alias_model_id = re.search(r'Model: (\d+), "Model::Ran_Jaw_bone", "LimbNode"', text).group(1)
    mesh_block = re.search(
        r'Model: \d+, "Model::Ran_Jaw", "Mesh" \{(.*?)\n\t\}',
        text,
        re.S,
    ).group(1)
    alias_block = re.search(
        r'Model: \d+, "Model::Ran_Jaw_bone", "LimbNode" \{(.*?)\n\t\}',
        text,
        re.S,
    ).group(1)

    assert f'C: "OO",{mesh_model_id},{alias_model_id}' in text
    assert 'P: "Lcl Translation","Lcl Translation","","A",0.000000,0.000000,0.000000' in mesh_block
    assert 'P: "Lcl Rotation","Lcl Rotation","","A",0.0000,0.0000,0.0000' in mesh_block
    assert 'P: "Lcl Translation","Lcl Translation","","A",1.000000,2.000000,3.000000' in alias_block


def test_fbx_export_references_texture_sidecar_paths(tmp_path):
    root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
    mesh = ModelNode(
        name="torso",
        flags=int(NodeFlags.MESH),
        parent=root,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[(0, 1, 2)],
        texture="c_rancor01",
    )
    root.children.append(mesh)
    model = KotorModel(name="texture_sidecar_case", root_node=root)
    out_path = tmp_path / "texture_sidecar_case.fbx"

    assert FBXExporter()._export_fbx_ascii(
        model,
        str(out_path),
        texture_paths={"c_rancor01": "textures/c_rancor01.png"},
    )
    text = out_path.read_text(encoding="utf-8")

    assert 'Filename: "textures/c_rancor01.png"' in text
    assert 'RelativeFilename: "textures/c_rancor01.png"' in text


def test_fbx_export_writes_texture_sidecar_files(tmp_path):
    class _FakeImage:
        mode = "RGBA"

        def save(self, path):
            Path(path).write_bytes(b"fake-png")

    class _FakeTextureCache:
        def get(self, name):
            return _FakeImage() if name == "c_rancor01" else None

    root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
    mesh = ModelNode(
        name="torso",
        flags=int(NodeFlags.MESH),
        parent=root,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[(0, 1, 2)],
        texture="c_rancor01",
    )
    root.children.append(mesh)
    model = KotorModel(name="texture_write_case", root_node=root)

    paths = FBXExporter._export_fbx_textures_to_dir(
        model,
        tmp_path / "textures",
        _FakeTextureCache(),
        tmp_path,
    )

    assert paths == {"c_rancor01": "textures/c_rancor01.png"}
    assert (tmp_path / "textures" / "c_rancor01.png").read_bytes() == b"fake-png"


def test_fbx_export_aliases_mesh_bones_case_insensitively(tmp_path):
    root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
    eye = ModelNode(
        name="Rancor_eyeL",
        flags=int(NodeFlags.MESH),
        parent=root,
        position=(0.1, 0.2, 0.3),
        vertices=[(0.0, 0.0, 0.0), (0.2, 0.0, 0.0), (0.0, 0.2, 0.0)],
        faces=[(0, 1, 2)],
        texture="eye",
    )
    skin = ModelNode(
        name="torso",
        flags=int(NodeFlags.MESH | NodeFlags.SKIN),
        parent=root,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[(0, 1, 2)],
        texture="torso",
        bone_map=["Rancor_EyeL"],
        skin_data=[
            VertexSkinData([BoneWeight(0, 1.0)]),
            VertexSkinData([BoneWeight(0, 1.0)]),
            VertexSkinData([BoneWeight(0, 1.0)]),
        ],
    )
    root.children.extend([eye, skin])
    anim_node = ModelNode(
        name="Rancor_eyeL",
        controllers=[
            {
                "type": 8,
                "times": [0.0, 1.0],
                "values": [(0.0, 0.0, 0.0), (0.0, 0.0, 0.1)],
            }
        ],
    )
    model = KotorModel(
        name="case_insensitive_mesh_bone_alias_case",
        root_node=root,
        animations=[Animation(name="blink", length=1.0, anim_root="root", nodes=[anim_node])],
    )
    out_path = tmp_path / "case_insensitive_mesh_bone_alias_case.fbx"

    assert FBXExporter()._export_fbx_ascii(model, str(out_path))
    text = out_path.read_text(encoding="utf-8")

    mesh_model_id = re.search(r'Model: (\d+), "Model::Rancor_eyeL", "Mesh"', text).group(1)
    alias_model_id = re.search(r'Model: (\d+), "Model::Rancor_eyeL_bone", "LimbNode"', text).group(1)
    cluster_id = re.search(r'Deformer: (\d+), "SubDeformer::Rancor_EyeL", "Cluster"', text).group(1)
    assert f'C: "OO",{alias_model_id},{cluster_id}' in text
    assert f'C: "OO",{mesh_model_id},{cluster_id}' not in text
    assert re.search(rf'C: "OP",\d+,{alias_model_id},"Lcl Translation"', text)
    assert not re.search(rf'C: "OP",\d+,{mesh_model_id},"Lcl Translation"', text)


def test_fbx_export_writes_kotor_unreal_sidecar_manifest(tmp_path):
    root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
    head_hook = ModelNode(name="head_g", flags=int(NodeFlags.HEADER), parent=root)
    skin = ModelNode(
        name="torso",
        flags=int(NodeFlags.MESH | NodeFlags.SKIN),
        parent=root,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        tangents=[(1.0, 0.0, 0.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        uvs_lm=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        faces=[(0, 1, 2)],
        texture="torso_diff",
        lightmap="torso_lm",
        bump_map="torso_n",
        texture_names=["torso_diff", "torso_lm"],
        bone_map=["root", "head_g"],
        qbone_list=[(0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 1.0)],
        tbone_list=[(0.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        skin_data=[
            VertexSkinData([BoneWeight(0, 1.0)]),
            VertexSkinData([BoneWeight(0, 0.5), BoneWeight(1, 0.5)]),
            VertexSkinData([BoneWeight(1, 1.0)]),
        ],
    )
    root.children.extend([head_hook, skin])
    model = KotorModel(name="manifest_case", root_node=root, supermodel="S_MALE02")
    out_path = tmp_path / "manifest_case.fbx"

    assert FBXExporter().export(model, str(out_path), export_rigging=False)
    manifest_path = out_path.with_suffix(".ghostrigger.json")
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["schema"] == "ghostrigger.kotor_fbx_manifest.v1"
    assert manifest["source"]["supermodel"] == "S_MALE02"
    assert manifest["coordinate_system"]["fbx_axis"] == "Z-up, -Y forward, +X right"
    assert manifest["counts"]["exported_mesh_nodes"] == 1
    assert manifest["hooks"] == [{"name": "head_g", "role": "head_attachment_geometry", "parent": "root"}]
    assert manifest["materials"][0]["diffuse"] == "torso_diff"
    assert manifest["materials"][0]["lightmap"] == "torso_lm"
    assert manifest["materials"][0]["bump_map"] == "torso_n"
    assert manifest["meshes"][0]["skin"]["qbone_count"] == 2
    assert manifest["meshes"][0]["skin"]["tbone_count"] == 2
    assert manifest["skeleton"]["skin"]["missing_bones"] == []
    assert manifest["validation"]["ok"] is True
    assert manifest["fbx"]["checked"] is True
    assert manifest["fbx"]["exporter_backend"] == "builtin_ascii"
    assert manifest["unreal"]["recommended_import"]["skeletal_mesh"] is True
