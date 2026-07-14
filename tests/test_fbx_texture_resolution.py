"""T2521: FBX embedded-texture (.fbm) folder discovery and name reconciliation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.core.characters.character_builder as cb
import src.core.characters.headless_body_workflow as wf


class _FakeTexturedSkinModel:
    def __init__(self, texture: str = "BendakStarkiller_basecolor"):
        self.name = "payload"
        skin = SimpleNamespace(
            name="Mesh",
            is_skin=True,
            is_mesh=False,
            texture=texture,
            texture_names=[],
            vertices=[(0.0, 0.0, 0.0)],
            lightmap="",
            txi_envmaptexture="",
            txi_specularcolour="",
            txi_bumpmaptexture="",
        )
        self._nodes = [skin]

    def all_nodes(self):
        return list(self._nodes)


class _FakeNode(SimpleNamespace):
    def world_transform(self):
        return (
            tuple(getattr(self, "position", (0.0, 0.0, 0.0))),
            tuple(getattr(self, "rotation", (0.0, 0.0, 0.0, 1.0))),
        )

    def compute_bounds(self):
        return None


class _FakeTreeModel:
    def __init__(self, children):
        self.name = "fake"
        self.metadata = {}
        self.root_node = _FakeNode(
            name="root",
            children=list(children),
            parent=None,
            vertices=[],
            faces=[],
            is_skin=False,
            bone_map=[],
        )
        for child in self.root_node.children:
            child.parent = self.root_node

    def all_nodes(self):
        out = []
        stack = [self.root_node]
        while stack:
            node = stack.pop()
            out.append(node)
            stack.extend(reversed(list(getattr(node, "children", []) or [])))
        return out


def _skin_row(*bone_indices):
    weight = 1.0 / max(1, len(bone_indices))
    return SimpleNamespace(
        influences=[
            SimpleNamespace(bone_index=int(index), weight=weight)
            for index in bone_indices
        ]
    )


def _weighted_skin_row(*pairs):
    return SimpleNamespace(
        influences=[
            SimpleNamespace(bone_index=int(index), weight=float(weight))
            for index, weight in pairs
        ]
    )


def test_split_weight_smoothing_blends_edge_discontinuous_rows():
    node = _FakeNode(
        name="region",
        vertices=[(0.0, 0.0, 0.0), (0.05, 0.0, 0.0), (0.0, 0.05, 0.0)],
        faces=[(0, 1, 2)],
        skin_data=[
            _skin_row(0),
            _skin_row(1),
            _skin_row(1),
        ],
        bone_map=["root", "hand"],
    )

    report = wf._smooth_skin_weights_across_edges(node)

    assert report["applied"] is True
    assert report["iterations"] == 4
    assert report["changed_rows"] > 0
    first = {
        int(getattr(influence, "bone_index", -1)):
            float(getattr(influence, "weight", 0.0) or 0.0)
        for influence in node.skin_data[0].influences
    }
    assert first[0] > 0.0
    assert first[1] > 0.0
    assert abs(sum(first.values()) - 1.0) < 1.0e-6


def test_split_weight_smoothing_reports_but_does_not_lock_position_duplicates():
    node = _FakeNode(
        name="triangle_soup_region",
        vertices=[
            (0.0, 0.0, 0.0),
            (0.05, 0.0, 0.0),
            (0.0, 0.05, 0.0),
            (0.0, 0.0, 0.0),
            (-0.05, 0.0, 0.0),
            (0.0, -0.05, 0.0),
        ],
        faces=[(0, 1, 2), (3, 4, 5)],
        skin_data=[
            _skin_row(0),
            _skin_row(0),
            _skin_row(0),
            _skin_row(1),
            _skin_row(1),
            _skin_row(1),
        ],
        bone_map=["left_patch", "right_patch"],
    )

    report = wf._smooth_skin_weights_across_edges(node)

    assert report["applied"] is True
    assert report["position_duplicate_groups"] == 1
    assert report["position_duplicate_vertices"] == 2
    first = {
        int(getattr(influence, "bone_index", -1)):
            float(getattr(influence, "weight", 0.0) or 0.0)
        for influence in node.skin_data[0].influences
    }
    duplicate = {
        int(getattr(influence, "bone_index", -1)):
            float(getattr(influence, "weight", 0.0) or 0.0)
        for influence in node.skin_data[3].influences
    }
    assert first == {0: 1.0}
    assert duplicate == {1: 1.0}


def test_payload_triangle_soup_repair_welds_vertices_without_collapsing_uvs(monkeypatch):
    monkeypatch.setattr(cb, "_PAYLOAD_TOPOLOGY_WELD_MIN_REMOVED", 1)
    monkeypatch.setattr(cb, "_PAYLOAD_TOPOLOGY_WELD_MIN_RATIO", 1.1)
    node = _FakeNode(
        name="triangle_soup_payload",
        vertices=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        ],
        faces=[(0, 1, 2), (3, 4, 5)],
        uvs=[
            (0.0, 0.0),
            (1.0, 0.0),
            (0.0, 1.0),
            (0.1, 0.1),
            (0.9, 0.1),
            (0.1, 0.9),
        ],
        face_uvs=[],
        face_mats=[2, 3],
        normals=[
            (0.0, 0.0, 1.0),
            (0.0, 0.0, 1.0),
            (0.0, 0.0, 1.0),
            (0.0, 0.0, 1.0),
            (0.0, 0.0, 1.0),
            (0.0, 0.0, 1.0),
        ],
    )

    _rows, report = cb._repair_payload_triangle_soup_topology(node, [])

    assert report is not None
    assert report["applied"] is True
    assert report["original_vertices"] == 6
    assert report["welded_vertices"] == 3
    assert report["promoted_implicit_uvs"] is True
    assert node.vertices == [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    assert node.faces == [(0, 1, 2), (0, 1, 2)]
    assert node.face_uvs == [(0, 1, 2), (3, 4, 5)]
    assert node.face_mats == [2, 3]


def test_topology_welded_split_weights_smooth_even_below_density_gate():
    node = _FakeNode(
        name="welded_region",
        vertices=[(0.0, 0.0, 0.0), (0.05, 0.0, 0.0), (0.0, 0.05, 0.0)],
        faces=[(0, 1, 2)],
        skin_data=[
            _skin_row(0),
            _skin_row(1),
            _skin_row(1),
        ],
        bone_map=["root", "hand"],
        _gr_topology_weld_report={
            "applied": True,
            "original_vertices": 14349,
            "welded_vertices": 2595,
            "removed_vertices": 11754,
        },
    )

    report = wf._maybe_smooth_high_density_split_weights(
        node,
        {"vertex_count": 2048},
    )

    assert report is not None
    assert report["applied"] is True
    assert report["topology_weld_smoothing"] is True
    assert report["density_ratio"] < 1.0
    assert report["topology_weld"]["removed_vertices"] == 11754


def test_rancor_hand_stabilizer_collapses_finger_rows_to_hand_forearm():
    node = _FakeNode(
        name="LArm",
        vertices=[
            (-0.5, 0.0, 0.0),
            (-1.5, 0.0, 0.0),
            (-2.5, 0.0, 0.0),
            (-3.0, 0.0, 0.0),
        ],
        faces=[(0, 1, 2), (1, 2, 3)],
        bone_map=[
            "Ran_BicepL",
            "Ran_ForearmL",
            "Ran_handL",
            "Ran_Index_01_L",
            "Ran_Mid_03_L",
        ],
        skin_data=[
            _weighted_skin_row((1, 0.60), (2, 0.10), (3, 0.30)),
            _weighted_skin_row((1, 0.30), (2, 0.20), (4, 0.50)),
            _weighted_skin_row((1, 0.10), (2, 0.40), (3, 0.50)),
            _weighted_skin_row((2, 0.35), (3, 0.65)),
        ],
    )

    report = wf._stabilize_rancor_hand_split_weights(node)

    assert report is not None
    assert report["applied"] is True
    assert report["side"] == "l"
    assert report["finger_rows"] == 4
    assert report["changed_rows"] == 4
    assert report["hand_slot"] == "Ran_handL"
    assert report["forearm_slot"] == "Ran_ForearmL"
    for row in node.skin_data:
        weights = {
            int(getattr(influence, "bone_index", -1)):
                float(getattr(influence, "weight", 0.0) or 0.0)
            for influence in row.influences
        }
        assert 3 not in weights
        assert 4 not in weights
        assert weights[1] > 0.0
        assert weights[2] > 0.0
        assert abs(sum(weights.values()) - 1.0) < 1.0e-6


def test_rancor_hand_stabilizer_ignores_non_rancor_palettes():
    node = _FakeNode(
        name="LArm",
        vertices=[(0.0, 0.0, 0.0)],
        faces=[],
        bone_map=["lforearm_g", "lhand_g", "LaFngrB_g"],
        skin_data=[_skin_row(0, 1, 2)],
    )
    before = [
        (
            int(getattr(influence, "bone_index", -1)),
            float(getattr(influence, "weight", 0.0) or 0.0),
        )
        for influence in node.skin_data[0].influences
    ]

    report = wf._stabilize_rancor_hand_split_weights(node)

    after = [
        (
            int(getattr(influence, "bone_index", -1)),
            float(getattr(influence, "weight", 0.0) or 0.0),
        )
        for influence in node.skin_data[0].influences
    ]
    assert report is None
    assert after == before


def test_candidate_texture_dirs_includes_fbx_fbm_folder(tmp_path):
    fbx = tmp_path / "RancorTamedConceptFinal.fbx"
    fbx.write_bytes(b"fbx")
    fbm = tmp_path / "RancorTamedConceptFinal.fbm"
    fbm.mkdir()
    (fbm / "body.png").write_bytes(b"stub")

    dirs = wf.candidate_texture_dirs(str(fbx))

    assert str(fbm) in dirs


def test_reconcile_external_texture_names_rewrites_material_name_to_fbm_file(tmp_path):
    model = _FakeTexturedSkinModel(texture="Material")
    fbm = tmp_path / "RancorTamedConceptFinal.fbm"
    fbm.mkdir()
    tex = fbm / "RancorBody_BaseColor.png"
    tex.write_bytes(b"stub")
    dirs = [str(fbm)]

    rewrites = wf.reconcile_external_texture_names(model, dirs)
    report = wf.texture_resolution_report(model, dirs)

    assert rewrites == {"Material": "RancorBody_BaseColor"}
    assert report["found_count"] == 1
    assert report["missing"] == []


def test_truncated_fbx_texture_stem_resolves_to_full_sidecar_name(tmp_path):
    model = _FakeTexturedSkinModel(texture="RancorTamedConceptFinal_basecolo")
    fbm = tmp_path / "RancorTamedConceptFinal.fbm"
    fbm.mkdir()
    tex = fbm / "RancorTamedConceptFinal_basecolor.jpg"
    tex.write_bytes(b"stub")
    dirs = [str(fbm)]

    rewrites = wf.reconcile_external_texture_names(model, dirs)
    report = wf.texture_resolution_report(model, dirs)

    assert rewrites == {
        "RancorTamedConceptFinal_basecolo": "RancorTamedConceptFinal_basecolor"
    }
    assert model.all_nodes()[0].texture == "RancorTamedConceptFinal_basecolor"
    assert report["found"] == {"RancorTamedConceptFinal_basecolor": str(tex)}
    assert report["missing"] == []


def test_texture_cache_loads_unique_long_sidecar_for_truncated_stem(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    from src.core.rendering.frame_core.texture_cache import TextureCache

    fbm = tmp_path / "RancorTamedConceptFinal.fbm"
    fbm.mkdir()
    Image.new("RGB", (4, 4), (80, 40, 20)).save(
        fbm / "RancorTamedConceptFinal_basecolor.jpg"
    )

    cache = TextureCache()
    cache.set_search_dirs([str(fbm)])

    assert cache.get("RancorTamedConceptFinal_basecolo") is not None


def test_node_splitter_prefers_authored_donor_skin_regions():
    bones = [f"Bone{i:02d}" for i in range(17)]
    source = _FakeNode(
        name="RancorPayload",
        is_skin=True,
        vertices=[
            (-1.0, 0.0, 0.0),
            (-1.0, 1.0, 0.0),
            (-1.0, 0.0, 1.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (1.0, 0.0, 1.0),
        ],
        faces=[(0, 1, 2), (3, 4, 5)],
        skin_data=[
            _skin_row(0, 1),
            _skin_row(1, 2),
            _skin_row(2, 3),
            _skin_row(12, 13),
            _skin_row(13, 14),
            _skin_row(15, 16),
        ],
        bone_map=bones,
        children=[],
        parent=None,
        texture="RancorTamedConceptFinal_basecolor",
        normals=[],
        tangents=[],
        uvs=[],
        face_uvs=[],
        face_mats=[],
    )
    donor_left = _FakeNode(
        name="LArm",
        is_skin=True,
        vertices=[(-1.0, 0.0, 0.0), (-1.0, 1.0, 0.0), (-1.0, 0.0, 1.0)],
        faces=[(0, 1, 2)],
        bone_map=bones[:8],
        skin_data=[_skin_row(0), _skin_row(1), _skin_row(2)],
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        children=[],
        parent=None,
    )
    donor_right = _FakeNode(
        name="RArm",
        is_skin=True,
        vertices=[(1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (1.0, 0.0, 1.0)],
        faces=[(0, 1, 2)],
        bone_map=bones[8:],
        skin_data=[_skin_row(0), _skin_row(1), _skin_row(2)],
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        children=[],
        parent=None,
    )

    model = _FakeTreeModel([source])
    donor = _FakeTreeModel([donor_left, donor_right])

    result = wf.split_skinned_mesh_nodes_with_weight_remap(model, donor)
    parts = [
        node
        for node in model.all_nodes()
        if getattr(node, "_gr_weight_remap_split", False)
    ]

    assert result["ok"] is True, result
    assert result["split_nodes"] == 2
    assert {getattr(part, "_gr_anatomical_region_name", "") for part in parts} == {
        "LArm",
        "RArm",
    }
    assert all(len(part.bone_map) <= 16 for part in parts)
    assert model.metadata["character_builder_skinned_node_splitter"]["method"] == (
        "authored_donor_skin_node_weight_remap"
    )


def test_node_splitter_keeps_imported_world_space_regions_in_place(monkeypatch):
    bones = [f"Bone{i:02d}" for i in range(17)]
    source = _FakeNode(
        name="RancorPayload",
        is_skin=True,
        vertices=[
            (-1.0, 0.0, 0.0),
            (-1.0, 1.0, 0.0),
            (-1.0, 0.0, 1.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (1.0, 0.0, 1.0),
        ],
        faces=[(0, 1, 2), (3, 4, 5)],
        skin_data=[
            _skin_row(0, 1),
            _skin_row(1, 2),
            _skin_row(2, 3),
            _skin_row(12, 13),
            _skin_row(13, 14),
            _skin_row(15, 16),
        ],
        bone_map=bones,
        children=[],
        parent=None,
        texture="RancorTamedConceptFinal_basecolor",
        normals=[],
        tangents=[],
        uvs=[],
        face_uvs=[],
        face_mats=[],
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        vertex_space=1,
        _gr_vertices_in_kotor_world=True,
        _gr_bound_to_kotor_skeleton=True,
        _gr_kotor_skeleton_root="c_rancorS",
        _gr_kotor_bone_map_source="character_builder_template_rig",
        _gr_use_animation_base_bind_for_preview=True,
    )
    donor_left = _FakeNode(
        name="LArm",
        is_skin=True,
        vertices=[(-1.0, 0.0, 0.0), (-1.0, 1.0, 0.0), (-1.0, 0.0, 1.0)],
        faces=[(0, 1, 2)],
        bone_map=bones[:8],
        skin_data=[_skin_row(0), _skin_row(1), _skin_row(2)],
        position=(25.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        children=[],
        parent=None,
    )
    donor_right = _FakeNode(
        name="RArm",
        is_skin=True,
        vertices=[(1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (1.0, 0.0, 1.0)],
        faces=[(0, 1, 2)],
        bone_map=bones[8:],
        skin_data=[_skin_row(0), _skin_row(1), _skin_row(2)],
        position=(-25.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        children=[],
        parent=None,
    )
    model = _FakeTreeModel([source])
    donor = _FakeTreeModel([donor_left, donor_right])

    monkeypatch.setattr(
        wf,
        "_authored_donor_skin_node_regions",
        lambda *_args, **_kwargs: {
            "face_to_region": [0, 1],
            "region_names": {0: "LArm", 1: "RArm"},
            "region_palettes": {0: bones[:8], 1: bones[8:]},
            "mean_transfer_confidence": 1.0,
            "per_region_confidence": {0: 1.0, 1: 1.0},
            "method": "authored_donor_skin_nodes",
        },
    )

    result = wf.split_skinned_mesh_nodes_with_weight_remap(model, donor)
    parts = {
        node.name: node
        for node in model.all_nodes()
        if getattr(node, "_gr_weight_remap_split", False)
    }

    assert result["ok"] is True, result
    assert set(parts) == {"LArm", "RArm"}
    assert parts["LArm"].vertices == source.vertices[:3]
    assert parts["RArm"].vertices == source.vertices[3:]
    assert parts["LArm"].position == source.position
    assert parts["RArm"].position == source.position
    assert getattr(parts["LArm"], "_gr_vertices_in_kotor_world", False) is True
    assert getattr(parts["RArm"], "_gr_vertices_in_kotor_world", False) is True
    assert parts["LArm"].vertex_space == 1
    assert parts["RArm"].vertex_space == 1
    assert getattr(parts["LArm"], "_gr_bound_to_kotor_skeleton", False) is True
    assert getattr(parts["RArm"], "_gr_bound_to_kotor_skeleton", False) is True
    assert getattr(parts["LArm"], "_gr_use_animation_base_bind_for_preview", False) is True
    assert getattr(parts["RArm"], "_gr_use_animation_base_bind_for_preview", False) is True
    assert getattr(parts["LArm"], "_gr_authored_donor_skin_node_localized") is False
    assert getattr(parts["RArm"], "_gr_authored_donor_skin_node_localized") is False
