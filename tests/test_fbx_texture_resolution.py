"""T2521: FBX embedded-texture (.fbm) folder discovery and name reconciliation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

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
