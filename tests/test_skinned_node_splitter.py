"""Tests for the PR E (T2512) anatomical skinned-node splitter in
native/GhostRigger.Core.Workflow/Python/src/core/characters/headless_body_workflow.py:

- split_skinned_mesh_nodes_with_weight_remap: donor-driven BIAGP split of
  over-palette skinned nodes into per-region nodes with <=16-bone local
  palettes; weights byte-identical (D-5); hard-fail on missing donor (D-4).
- validate_skin_node_palettes: hard export gate counting EVERY palette entry
  (including bones the correspondence fit classifies as degenerate — the
  T2509b collar finding: two lists, same source data).
- split_imported_mesh_nodes(respect_skinned=...): "skip" is byte-for-byte the
  pre-T2512 behavior; "split_with_weight_remap" reaches the new path.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("trimesh")
pytest.importorskip("scipy")

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_module(mod_name: str, rel_path: str):
    path = _ROOT.joinpath(*rel_path.split("/"))
    spec = importlib.util.spec_from_file_location(mod_name, str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


wf = _load_module(
    "gr_headless_body_workflow_split",
    "native/GhostRigger.Core.Workflow/Python/src/core/characters/"
    "headless_body_workflow.py",
)


# ---------------------------------------------------------------------------
# Fake node/model helpers
# ---------------------------------------------------------------------------


class _FakeSkinNode:
    def __init__(self, name, vertices, faces, skin_rows, bone_map):
        self.name = name
        self.parent = None
        self.children: list = []
        self.is_skin = True
        self.is_mesh = True
        self.render = True
        self.vertices = [tuple(float(x) for x in v) for v in vertices]
        self.faces = [tuple(int(i) for i in f) for f in faces]
        self.normals: list = []
        self.tangents: list = []
        self.uvs: list = []
        self.face_uvs: list = []
        self.face_mats: list = []
        self.skin_data = skin_rows
        self.bone_map = list(bone_map)


class _FakeModel:
    def __init__(self, node):
        self.name = "fake_model"
        self.root_node = node
        self.metadata: dict = {}

    def all_nodes(self):
        out = []
        stack = [self.root_node]
        while stack:
            n = stack.pop()
            out.append(n)
            stack.extend(getattr(n, "children", []) or [])
        return out


def _skin_rows_from_arrays(bone_indices, bone_weights):
    rows = []
    for bi_row, bw_row in zip(bone_indices, bone_weights):
        influences = []
        for bi, bw in zip(bi_row, bw_row):
            if int(bi) >= 0 and float(bw) > 0.0:
                influences.append(
                    SimpleNamespace(bone_index=int(bi), weight=float(bw))
                )
        rows.append(SimpleNamespace(influences=influences))
    return rows


def _source_weight_multiset(node, vertex_index):
    """{(bone_NAME, weight)} multiset for one vertex — name-keyed so it is
    invariant under local-index remapping."""
    row = node.skin_data[vertex_index]
    out = []
    for infl in row.influences:
        bi = int(infl.bone_index)
        if 0 <= bi < len(node.bone_map) and float(infl.weight) > 1e-9:
            out.append((str(node.bone_map[bi]), float(infl.weight)))
    return sorted(out)


def _drexl_skinned_fixture():
    """The Drexl donor itself as an over-palette skinned import (55-bone map)."""
    from tests.test_anatomical_partition import _load_drexl_model

    try:
        from src.core.game.kotor_loader import build_donor_skin_data_from_model
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"donor builder unavailable: {exc}")

    reference = _load_drexl_model()
    donor = build_donor_skin_data_from_model(reference)
    rows = _skin_rows_from_arrays(donor.bone_indices, donor.bone_weights)
    node = _FakeSkinNode(
        "imported_skinned",
        np.asarray(donor.vertices).tolist(),
        np.asarray(donor.faces).tolist(),
        rows,
        list(donor.bone_names),
    )
    return _FakeModel(node), reference, node


# ---------------------------------------------------------------------------
# Palette validator
# ---------------------------------------------------------------------------


def test_palette_validator_counts_every_entry_including_degenerates() -> None:
    """17-entry palette fails even when two entries are duplicate-position
    (correspondence-degenerate) bones — the validator counts palette slots,
    never positions.  Two lists, same source data (T2509b collar finding)."""
    verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    faces = [(0, 1, 2)]
    rows = _skin_rows_from_arrays([[0, -1, -1, -1]] * 3, [[1.0, 0, 0, 0]] * 3)
    bone_map = [f"bone_{i}" for i in range(15)] + ["lcollar_g", "rcollar_g"]
    assert len(bone_map) == 17
    model = _FakeModel(_FakeSkinNode("over", verts, faces, rows, bone_map))

    report = wf.validate_skin_node_palettes(model)
    assert not report["ok"]
    assert report["violations"][0]["palette_size"] == 17
    assert report["violations"][0]["limit"] == 16


def test_palette_validator_passes_at_limit() -> None:
    verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    faces = [(0, 1, 2)]
    rows = _skin_rows_from_arrays([[0, -1, -1, -1]] * 3, [[1.0, 0, 0, 0]] * 3)
    model = _FakeModel(
        _FakeSkinNode("ok16", verts, faces, rows, [f"b{i}" for i in range(16)])
    )
    assert wf.validate_skin_node_palettes(model)["ok"]


# ---------------------------------------------------------------------------
# Hard-fail guards (D-4)
# ---------------------------------------------------------------------------


def test_missing_donor_hard_fails() -> None:
    verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    faces = [(0, 1, 2)]
    rows = _skin_rows_from_arrays([[0, -1, -1, -1]] * 3, [[1.0, 0, 0, 0]] * 3)
    model = _FakeModel(
        _FakeSkinNode("skinned", verts, faces, rows, [f"b{i}" for i in range(20)])
    )
    result = wf.split_skinned_mesh_nodes_with_weight_remap(model, None)
    assert not result["ok"]
    assert result["code"] == "missing_donor"


def test_default_mode_skips_skinned_nodes_unchanged() -> None:
    """respect_skinned='skip' (default) must be byte-for-byte the pre-T2512
    behavior: skinned nodes counted, never split."""
    verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    faces = [(0, 1, 2)]
    rows = _skin_rows_from_arrays([[0, -1, -1, -1]] * 3, [[1.0, 0, 0, 0]] * 3)
    node = _FakeSkinNode("skinned", verts, faces, rows, [f"b{i}" for i in range(20)])
    model = _FakeModel(node)

    md = wf._import_model_data()
    scene = SimpleNamespace(
        get=lambda slot: SimpleNamespace(model=model)
        if slot == md.PartSlot.HEADLESS_BODY
        else None
    )
    result = wf.split_imported_mesh_nodes(scene)
    assert result["ok"]
    assert result["split_nodes"] == 0
    assert result["skipped_skinned_nodes"] == 1
    assert node.bone_map  # untouched
    assert "skinned_split" not in result


# ---------------------------------------------------------------------------
# Drexl end-to-end split (K2-gated)
# ---------------------------------------------------------------------------


def test_split_with_weight_remap_drexl(capsys) -> None:
    """Load-bearing PR E acceptance: the 55-bone Drexl skinned mesh splits into
    anatomical region nodes, every palette <=16, weights byte-identical (D-5),
    and the duplicate-position collar pair survives as two distinct palette
    entries wherever it appears."""
    model, reference, source_node = _drexl_skinned_fixture()
    source_weights = [
        _source_weight_multiset(source_node, i)
        for i in range(len(source_node.vertices))
    ]
    source_vertex_count = len(source_node.vertices)

    result = wf.split_skinned_mesh_nodes_with_weight_remap(model, reference)
    assert result["ok"], result
    assert result["split_nodes"] >= 4

    parts = [
        n
        for n in model.all_nodes()
        if getattr(n, "_gr_weight_remap_split", False)
    ]
    assert len(parts) == result["split_nodes"]

    with capsys.disabled():
        print("\n=== PR E Drexl anatomical split ===")
        for p in parts:
            print(
                f"  {p.name:<28} verts={len(p.vertices):>5} "
                f"faces={len(p.faces):>5} palette={len(p.bone_map):>3}"
            )

    total_faces = 0
    collar_regions = 0
    for part in parts:
        # Palette limit (hard invariant).
        assert len(part.bone_map) <= 16, (part.name, len(part.bone_map))
        # Palette entries are unique names (collar pair stays distinct).
        assert len(set(part.bone_map)) == len(part.bone_map), part.name
        if "lcollar_g" in part.bone_map and "rcollar_g" in part.bone_map:
            collar_regions += 1
            assert part.bone_map.index("lcollar_g") != part.bone_map.index(
                "rcollar_g"
            )
        total_faces += len(part.faces)

        # D-5 byte-identity: every vertex's (bone_name, weight) multiset is
        # exactly the source vertex's multiset — weights never dropped,
        # renormalised, or reordered; only indices remapped.
        src_idx = getattr(part, "_gr_source_vertex_indices")
        assert len(src_idx) == len(part.vertices)
        for new_i, old_i in enumerate(src_idx):
            assert 0 <= old_i < source_vertex_count
            assert (
                _source_weight_multiset(part, new_i) == source_weights[old_i]
            ), f"{part.name} vertex {new_i} (source {old_i}) weights diverged"

    # No faces lost across the split.
    assert total_faces == 1526

    # The collar pair is real skinning data on Drexl; it must survive in at
    # least one region as two distinct palette entries.
    assert collar_regions >= 1

    # Post-split model-wide palette gate.
    palettes = wf.validate_skin_node_palettes(model)
    assert palettes["ok"], palettes["violations"]

    # Wrapper metadata recorded.
    meta = model.metadata["character_builder_skinned_node_splitter"]
    assert meta["method"] == "anatomical_partition_weight_remap"
    assert meta["palette_validation"]["ok"]


def test_split_wiring_through_split_imported_mesh_nodes() -> None:
    """respect_skinned='split_with_weight_remap' reaches the skinned splitter
    through the public entry point and reports its result additively."""
    model, reference, _ = _drexl_skinned_fixture()
    md = wf._import_model_data()
    scene = SimpleNamespace(
        get=lambda slot: SimpleNamespace(model=model)
        if slot == md.PartSlot.HEADLESS_BODY
        else None
    )
    result = wf.split_imported_mesh_nodes(
        scene,
        respect_skinned="split_with_weight_remap",
        reference_model=reference,
    )
    assert result["ok"], result
    assert result["skinned_split"]["ok"]
    assert result["split_nodes"] >= 4
    assert result["skinned_split"]["palette_validation"]["ok"]
