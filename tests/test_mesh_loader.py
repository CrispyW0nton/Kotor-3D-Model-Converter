from pathlib import Path

import numpy as np

from src.core.retargeting.mesh_loader import load_kotor_skinned_mesh
from src.core.retargeting.sampler import DEFAULT_CORPUS_ROOT


def _fixture_path(resref: str) -> Path:
    return DEFAULT_CORPUS_ROOT / "k1" / f"{resref}.mdl"


def test_pmbam_mesh_loads_with_valid_skin_data():
    mesh = load_kotor_skinned_mesh(_fixture_path("pmbam"))

    assert mesh.positions.shape[0] > 0
    assert mesh.positions.shape[1] == 3
    assert mesh.bone_indices.shape == mesh.bone_weights.shape
    assert mesh.bone_indices.shape[1] == 4
    np.testing.assert_allclose(mesh.bone_weights.sum(axis=1), 1.0, atol=1e-5)
    assert int(mesh.bone_indices.max()) < len(mesh.source_bone_names)
    assert not np.any(np.isnan(mesh.positions))
    assert mesh.local_bone_map
    assert mesh.metadata["local_palette_to_global_indices"]
