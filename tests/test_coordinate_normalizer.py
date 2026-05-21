import numpy as np

from src.core.animation.gpu_skinning import MatrixPaletteUploader
from src.core.retargeting.coordinate_normalizer import CoordinateNormalizer
from src.core.retargeting.sampler import load_fixture_model


def test_normalizer_round_trip_pmbam_pelvis_matches_g5():
    model = load_fixture_model("pmbam")
    registry = CoordinateNormalizer().normalize_aurora_bind(model, "kotor_pmbam")

    uploader = MatrixPaletteUploader()
    uploader.build_inverse_bind_pose(model)
    g5_world = np.linalg.inv(np.asarray(uploader._inv_bind["pelvis_g"], dtype=np.float64))

    np.testing.assert_allclose(
        registry.world_position("pelvis_g"),
        g5_world[:3, 3],
        atol=1e-6,
    )
    assert registry.g5_inverse_bind_delta_max <= 5.4e-7


def test_normalizer_uses_wxyz_and_world_space():
    model = load_fixture_model("S_Male01")
    registry = CoordinateNormalizer().normalize_aurora_bind(model, "kotor_s_male01")

    rootdummy = registry.world_matrix("rootdummy")
    pelvis = registry.world_matrix("pelvis_g")

    # pelvis_g is parented under rootdummy, so the world Z is the root height
    # plus the local pelvis offset in KOTOR's Z-up coordinate system.
    assert pelvis[2, 3] > rootdummy[2, 3]
    rotation = registry.world_rotation("pelvis_g")
    assert abs(float(np.linalg.norm(rotation)) - 1.0) <= 1e-6
    assert abs(float(rotation[0])) > 0.999
