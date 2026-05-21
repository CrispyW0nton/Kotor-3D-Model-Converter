import numpy as np

from src.core.retargeting.coordinate_normalizer import CoordinateNormalizer
from src.core.retargeting.fbx_exporter import _registry_to_aurora_payload, validate_ground_truth
from src.core.retargeting.sampler import load_fixture_model
from src.core.retargeting.skeleton_renamer import load_rename_spec


def _pmbam_payload():
    model = load_fixture_model("pmbam")
    registry = CoordinateNormalizer().normalize_aurora_bind(model, "kotor_pmbam")
    return _registry_to_aurora_payload(registry, load_rename_spec())


def test_all_bones_have_bind_world_matrix_4x4():
    payload = _pmbam_payload()
    assert all("bind_world_matrix_4x4" in bone for bone in payload["bones"].values())


def test_matrices_are_4x4():
    payload = _pmbam_payload()
    assert all(np.asarray(bone["bind_world_matrix_4x4"]).shape == (4, 4) for bone in payload["bones"].values())


def test_matrices_non_degenerate():
    payload = _pmbam_payload()
    for bone in payload["bones"].values():
        matrix = np.asarray(bone["bind_world_matrix_4x4"], dtype=float)
        assert abs(float(np.linalg.det(matrix[:3, :3]))) > 1e-6


def test_parent_chain_resolves_no_cycles():
    payload = _pmbam_payload()
    assert validate_ground_truth(payload) == []
