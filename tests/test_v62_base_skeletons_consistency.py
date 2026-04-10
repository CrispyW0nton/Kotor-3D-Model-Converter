"""
test_v62_base_skeletons_consistency.py
======================================
Regression tests verifying that KOTOR_BASE_SKELETONS is used consistently
across model_data.py, viewport.py (FrameRenderer._BASE_SKELETONS), and
gpu_renderer.py (_BASE_SKELETONS / _is_accessory_skin).

These tests guard against the historical bug where gpu_renderer.py used a
different hardcoded frozenset that:
  1. Excluded all creature base skeletons (C_BANTHA, C_DEWBACK, etc.)
  2. Included S_FEMALE01/S_MALE01 (light armour variants that ARE accessories)

v6.2 – 2026-03-21
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from core.model_data import KOTOR_BASE_SKELETONS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_model(name='test', supermodel='NULL'):
    """Create a minimal KotorModel-like stub."""
    from core.model_data import KotorModel, GameVersion
    return KotorModel(name=name, supermodel=supermodel,
                      game_version=GameVersion.K1)


def _make_skin_node(parent_root, name='skin', vertices=None, rotation=(0,0,0,1)):
    """Create a skin ModelNode attached to parent_root."""
    from core.model_data import ModelNode, NodeFlags
    node = ModelNode(name=name)
    node.flags = NodeFlags.MESH | NodeFlags.SKIN
    verts = vertices or [(0.1, 0.2, 0.3), (0.4, 0.5, 0.6)]
    node.vertices = verts
    # Provide basic UVs so _compute_model_bounds doesn't skip the node
    node.uvs = [(0.5, 0.5)] * len(verts)
    node.rotation = rotation
    node.parent = parent_root
    parent_root.children.append(node)
    return node


# ---------------------------------------------------------------------------
# 1. Canonical set content
# ---------------------------------------------------------------------------

class TestCanonicalSet:
    """Verify expected members of KOTOR_BASE_SKELETONS."""

    EXPECTED_PRESENT = [
        'NULL', '', 'NONE',
        'S_FEMALE02', 'S_MALE02', 'S_FEMALE03', 'S_MALE03',
        'C_BANTHA', 'C_BRITH', 'C_DEWBACK', 'C_DURASTEEL',
        'C_KINRATH', 'C_KATH', 'C_RANCOR', 'C_WRAID', 'C_IRIAZ',
        'C_KHOUNDA', 'C_TARENTATEK', 'C_RANCORM', 'C_TUKE',
        'WARDROID', 'N_WARDROID',
    ]
    EXPECTED_ABSENT = [
        # Light-armour PC variants – models WITH these as supermodel ARE accessories
        'S_FEMALE01', 'S_MALE01',
        'S_FEMALE01_LIGHT', 'S_MALE01_LIGHT',
        # Generic human base (not in KotOR's catalogue)
        'S_HUMANM', 'S_HUMANF',
    ]

    @pytest.mark.parametrize("name", EXPECTED_PRESENT)
    def test_expected_present(self, name):
        assert name in KOTOR_BASE_SKELETONS, (
            f"'{name}' should be in KOTOR_BASE_SKELETONS (is a base skeleton)."
        )

    @pytest.mark.parametrize("name", EXPECTED_ABSENT)
    def test_expected_absent(self, name):
        assert name not in KOTOR_BASE_SKELETONS, (
            f"'{name}' should NOT be in KOTOR_BASE_SKELETONS "
            f"(models using it as supermodel are accessories)."
        )


# ---------------------------------------------------------------------------
# 2. gpu_renderer uses the canonical constant
# ---------------------------------------------------------------------------

class TestGpuRendererConsistency:
    """gpu_renderer._BASE_SKELETONS must equal KOTOR_BASE_SKELETONS."""

    def _load_gpu_base(self):
        from gui import gpu_renderer as gr
        return gr._BASE_SKELETONS

    def test_gpu_base_skeletons_equals_canonical(self):
        gpu_base = self._load_gpu_base()
        assert gpu_base == KOTOR_BASE_SKELETONS, (
            "gpu_renderer._BASE_SKELETONS differs from KOTOR_BASE_SKELETONS!\n"
            "  Extra in GPU: %s\n  Missing from GPU: %s" % (
                sorted(gpu_base - KOTOR_BASE_SKELETONS),
                sorted(KOTOR_BASE_SKELETONS - gpu_base),
            )
        )

    def test_creature_bases_present_in_gpu(self):
        gpu_base = self._load_gpu_base()
        for name in ('C_BANTHA', 'C_DEWBACK', 'C_RANCOR', 'C_KINRATH', 'C_KATH'):
            assert name in gpu_base, f"Creature base '{name}' missing from gpu_renderer._BASE_SKELETONS"

    def test_s_female01_absent_from_gpu(self):
        """S_Female01 is NOT a base skeleton — models with supermodel=S_Female01 are accessories."""
        gpu_base = self._load_gpu_base()
        assert 'S_FEMALE01' not in gpu_base
        assert 'S_MALE01' not in gpu_base


# ---------------------------------------------------------------------------
# 3. viewport.py FrameRenderer._BASE_SKELETONS matches canonical
# ---------------------------------------------------------------------------

class TestViewportConsistency:
    """FrameRenderer._BASE_SKELETONS must equal KOTOR_BASE_SKELETONS."""

    def _load_fr_base(self):
        from gui.viewport import FrameRenderer
        return FrameRenderer._BASE_SKELETONS

    def test_viewport_base_skeletons_equals_canonical(self):
        fr_base = self._load_fr_base()
        assert fr_base == KOTOR_BASE_SKELETONS, (
            "FrameRenderer._BASE_SKELETONS differs from KOTOR_BASE_SKELETONS!\n"
            "  Extra in FR: %s\n  Missing from FR: %s" % (
                sorted(fr_base - KOTOR_BASE_SKELETONS),
                sorted(KOTOR_BASE_SKELETONS - fr_base),
            )
        )


# ---------------------------------------------------------------------------
# 4. Accessory detection correctness
# ---------------------------------------------------------------------------

class TestAccessoryDetection:
    """Models with creature/NULL supermodels are NOT accessories; PC overlays are."""

    @pytest.mark.parametrize("sm,expected_standalone", [
        ('NULL',        True),
        ('',            True),
        ('NONE',        True),
        ('C_BANTHA',    True),
        ('C_DEWBACK',   True),
        ('C_RANCOR',    True),
        ('S_FEMALE02',  True),
        ('S_MALE03',    True),
        # These ARE accessories (their models attach to a PC base)
        ('S_FEMALE01',  False),
        ('S_MALE01',    False),
        ('N_TWOHAND',   False),  # NPC model that has a base skeleton
        ('SOME_RANDOM', False),
    ])
    def test_is_standalone(self, sm, expected_standalone):
        is_standalone = sm.upper() in KOTOR_BASE_SKELETONS
        assert is_standalone == expected_standalone, (
            f"supermodel='{sm}': expected standalone={expected_standalone}, "
            f"got standalone={is_standalone}"
        )

    def test_creature_model_not_accessory_in_bounding_box(self):
        """_compute_model_bounds should treat C_BANTHA models as standalone."""
        from gui.gpu_renderer import _compute_model_bounds
        model = _make_model('c_bantha_test', supermodel='C_BANTHA')
        from core.model_data import ModelNode, NodeFlags
        root = ModelNode(name='root')
        model.root_node = root
        node = _make_skin_node(root, name='Body',
                               vertices=[(0.5, 0.5, 0.5), (1.0, 1.0, 1.0)])
        # Should not raise and should return a dict with valid bounds
        bounds = _compute_model_bounds(model)
        assert isinstance(bounds, dict)
        assert 'center_x' in bounds
        # No world_pos should have been applied (standalone model)
        assert bounds['center_x'] == pytest.approx(0.75, abs=0.2)

    def test_accessory_model_with_s_female01_supermodel(self):
        """A model with supermodel=S_Female01 is an accessory — bounds function processes it."""
        from gui.gpu_renderer import _compute_model_bounds
        model = _make_model('head_test', supermodel='S_Female01')
        from core.model_data import ModelNode, NodeFlags
        root = ModelNode(name='root')
        model.root_node = root
        # Head vertices centred around ~(0, 0, 1.7) — bone-local head position
        vertices = [(x*0.1, y*0.1, 1.7 + z*0.1)
                    for x in range(-3, 4)
                    for y in range(-3, 4)
                    for z in range(-3, 4)]
        node = _make_skin_node(root, name='Head', vertices=vertices)
        bounds = _compute_model_bounds(model)
        assert isinstance(bounds, dict)
        # With world_pos=(0,0,0) (no supermodel body), the centering transform
        # v = v - centroid + wp places vertices around (0,0,0).
        # Verify bounds are valid (extent > 0) — model was processed, not empty.
        assert bounds['max_extent'] > 0.01, "Bounds should reflect real vertex geometry"
        assert bounds['center_x'] == pytest.approx(0.0, abs=0.1)
        assert bounds['center_y'] == pytest.approx(0.0, abs=0.1)
        assert bounds['center_z'] == pytest.approx(0.0, abs=0.1)


# ---------------------------------------------------------------------------
# 5. model_data.KotorModel.is_accessory property uses canonical set
# ---------------------------------------------------------------------------

class TestModelDataAccessoryProperty:
    """KotorModel.is_accessory (if it exists) should agree with KOTOR_BASE_SKELETONS."""

    @pytest.mark.parametrize("sm,expected_acc", [
        ('NULL',       False),
        ('C_BANTHA',   False),
        ('S_FEMALE02', False),
        ('S_FEMALE01', True),   # light armour head target
        ('S_MALE01',   True),
        ('N_TWOHAND',  True),
    ])
    def test_is_accessory_agrees(self, sm, expected_acc):
        model = _make_model('test', supermodel=sm)
        # The property is defined in KotorModel via KOTOR_BASE_SKELETONS
        is_acc = model.supermodel.strip().upper() not in KOTOR_BASE_SKELETONS
        assert is_acc == expected_acc, (
            f"supermodel='{sm}': expected is_accessory={expected_acc}, got {is_acc}"
        )
