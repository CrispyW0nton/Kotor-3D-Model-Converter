"""T2517 regression: donor weight transfer must preserve authored weights.

Root cause of the 2026-07-01 manual-test animation distortion: the creature
wing-refinement pass (`_refine_creature_wing_weights_with_native_wing_nodes`)
exists for donors whose stock skin carries NO wing-bone influence, but it fired
on Drexl — whose donor weights the wing membranes to Lwing/Rwing directly — and
blended up to 0.49 spurious wing weight onto 39.9% of vertices (arms/shoulders
sit outboard of the wing root, matching its spatial heuristic).  The T2517
guard makes the pass test its premise: it skips when the donor transfer already
delivered meaningful wing weights.

This test binds the real C_DrexlF_UV.obj against the real c_drexlf donor
(headless, same path the Character Builder uses) and asserts per-vertex
(bone_name, weight) fidelity is EXACT against the authored donor weights.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("trimesh")
pytest.importorskip("scipy")

from tests.test_anatomical_partition import _load_drexl_model, _load_imported_drexl
from tests.test_correspondence_fit import _FakeImportModel


def _weight_multiset(bone_map, skin_row):
    out = []
    for infl in getattr(skin_row, "influences", []) or []:
        bi = int(getattr(infl, "bone_index", -1))
        w = float(getattr(infl, "weight", 0.0) or 0.0)
        if 0 <= bi < len(bone_map) and w > 1e-6:
            out.append((str(bone_map[bi]).lower(), round(w, 4)))
    return sorted(out)


def test_drexl_donor_transfer_preserves_authored_weights() -> None:
    import src.core.characters.headless_body_workflow as wf
    from src.core.skeleton.skeleton_builder import bind_imported_meshes_to_skeleton
    from src.core.game.kotor_loader import build_donor_skin_data_from_model
    from scipy.spatial import cKDTree

    donor_model = _load_drexl_model()
    donor = build_donor_skin_data_from_model(donor_model)
    iv, if_ = _load_imported_drexl()

    fake = _FakeImportModel(iv, if_)
    norm = wf.normalize_external_model_for_kotor(
        fake,
        game_version="K2",
        reference_model=donor_model,
        reference_label="c_drexlf",
        expected_mode="creature",
    )
    assert norm["ok"], norm
    mesh_node = fake.root_node
    mesh_node._external_imported = True

    report = bind_imported_meshes_to_skeleton(
        donor_model, mesh_nodes=[mesh_node], donor_model=donor_model
    )
    assert report.ok, report.message

    # The wing-refinement pass must have skipped (donor supplies wing weights);
    # the binding method must be the pure donor transfer.
    assert report.weighting_method == "native_template_nearest_vertex_donor", (
        report.weighting_method
    )
    assert report.creature_wing_refinement is False

    # All donor deformation bones present in the generated bone map.
    assert report.bone_count == 53

    # Per-vertex fidelity: every bound vertex's (bone_name, weight) multiset is
    # exactly the authored multiset of its corresponding donor vertex.
    bone_map = list(mesh_node.bone_map)
    tree = cKDTree(np.asarray(donor.vertices))
    pos = np.asarray([tuple(map(float, v)) for v in mesh_node.vertices])
    _, nearest = tree.query(pos)

    bi = np.asarray(donor.bone_indices)
    bw = np.asarray(donor.bone_weights)
    donor_rows = []
    for v in range(len(donor.vertices)):
        row = []
        for k in range(bi.shape[1]):
            if bi[v, k] >= 0 and bw[v, k] > 1e-6:
                row.append(
                    (str(donor.bone_names[bi[v, k]]).lower(), round(float(bw[v, k]), 4))
                )
        donor_rows.append(sorted(row))

    mismatches = []
    for i in range(len(pos)):
        got = _weight_multiset(bone_map, mesh_node.skin_data[i])
        want = donor_rows[int(nearest[i])]
        if got != want:
            mismatches.append((i, want, got))
    assert not mismatches, (
        f"{len(mismatches)}/{len(pos)} vertices diverge from authored weights; "
        f"first: {mismatches[:3]}"
    )
