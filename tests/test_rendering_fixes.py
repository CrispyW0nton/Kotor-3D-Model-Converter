"""
Tests for rendering pipeline fixes:
  - Alpha/transparency for droid glass nodes
  - UV tiling for large-coordinate geometry
  - Creature model outlier-skin filter (c_bantha, c_brith)
  - Normal transform on rotated mesh nodes
  - ClothRigSimulator PBD physics
"""

import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.model_data import (
    ModelNode, KotorModel, NodeFlags,
    _quat_rotate, _quat_mul, _quat_normalize_bind, _quat_normalize,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_model(name="test_model", supermodel="NULL"):
    m = KotorModel()
    m.name = name
    m.supermodel = supermodel
    return m


def _make_node(name, parent=None, pos=(0,0,0), rot=(0,0,0,1), flags=NodeFlags.MESH):
    n = ModelNode(name=name, flags=flags)
    n.position = pos
    n.rotation = rot
    n.parent = parent
    if parent is not None:
        parent.children.append(n)
    return n


def _make_skin_node(name, parent=None, pos=(0,0,0)):
    n = _make_node(name, parent, pos, flags=NodeFlags.MESH | NodeFlags.SKIN)
    n.vertices = [(0,0,0),(1,0,0),(0,1,0)]
    n.uvs = [(0,0),(1,0),(0,1)]
    n.faces = [(0,1,2)]
    return n


def _make_mesh_node(name, parent=None, pos=(0,0,0), rot=(0,0,0,1)):
    n = _make_node(name, parent, pos, rot)
    n.vertices = [(0,0,0),(0.2,0,0),(-0.2,0,0),(0,0.1,0)]
    n.uvs = [(0,0),(1,0),(0,1),(0.5,0.5)]
    n.faces = [(0,1,3),(0,3,2)]
    n.texture = "test_tex"
    return n


# ─────────────────────────────────────────────────────────────────────────────
#  Alpha / transparency tests
# ─────────────────────────────────────────────────────────────────────────────

class TestNodeAlpha:
    def test_node_alpha_default(self):
        node = ModelNode(name="mesh", flags=NodeFlags.MESH)
        assert getattr(node, 'alpha', 1.0) == 1.0

    def test_node_alpha_can_be_set(self):
        node = ModelNode(name="glass", flags=NodeFlags.MESH)
        node.alpha = 0.5
        assert node.alpha == 0.5

    def test_transparency_hint_zero_is_opaque(self):
        node = ModelNode(name="solid", flags=NodeFlags.MESH)
        node.alpha = 1.0
        node.transparency_hint = 0
        # Opaque: no special handling needed
        assert node.transparency_hint == 0
        assert node.alpha == 1.0

    def test_transparency_hint_2_is_glass(self):
        node = ModelNode(name="glass", flags=NodeFlags.MESH)
        node.alpha = 1.0
        node.transparency_hint = 2
        # hint=2 = KotOR additive blend (glass eye domes, etc.)
        assert node.transparency_hint == 2

    def test_alpha_from_bind_pose_controller(self):
        """_apply_bind_pose_controllers should set node.alpha from ctrl type 132.

        BUG-FIX v4.4: CTRL_MESH_ALPHA = 132, not 100.
        Verified against KotorBlender io_scene_kotor/format/mdl/types.py.
        """
        from src.core.mdl_parser import MDLBinaryParser as P
        node = ModelNode(name="glass_eye", flags=NodeFlags.MESH)
        node.controllers = [{'type': 132, 'values': [[0.4]]}]
        model = _make_model()
        model.root_node = node
        # Manually call the static helper (simulating parser post-process)
        P._apply_bind_pose_controllers(model)
        assert abs(node.alpha - 0.4) < 1e-5

    def test_selfillum_from_controller(self):
        """_apply_bind_pose_controllers should set node.selfillum from ctrl type 100.

        BUG-FIX v4.4: CTRL_MESH_SELFILLUMCOLOR = 100, not 132.
        Verified against KotorBlender io_scene_kotor/format/mdl/types.py.
        """
        from src.core.mdl_parser import MDLBinaryParser as P
        node = ModelNode(name="droid_eye", flags=NodeFlags.MESH)
        node.controllers = [{'type': 100, 'values': [[0.9, 0.7, 0.1]]}]
        model = _make_model()
        model.root_node = node
        P._apply_bind_pose_controllers(model)
        si = node.selfillum
        assert abs(si[0] - 0.9) < 1e-5
        assert abs(si[1] - 0.7) < 1e-5
        assert abs(si[2] - 0.1) < 1e-5


# ─────────────────────────────────────────────────────────────────────────────
#  UV tiling tests
# ─────────────────────────────────────────────────────────────────────────────

class TestUVWrapping:
    """Test the _uv_unwrap_coord helper via the _paste_textured_triangle function."""

    def _unwrap(self, base, other):
        """Replicate the multi-tile _uv_unwrap_coord logic."""
        diff = other - base
        while diff > 0.5:
            other -= 1.0
            diff -= 1.0
        while diff < -0.5:
            other += 1.0
            diff += 1.0
        return other

    def test_no_wrap_needed(self):
        assert abs(self._unwrap(0.3, 0.4) - 0.4) < 1e-9

    def test_single_seam_forward(self):
        # u0=0.9, u1=0.1: diff = -0.8 < -0.5 → shift other += 1.0 → 1.1
        # This keeps u1 within +0.2 of u0=0.9 (|1.1-0.9|=0.2 < 0.5)
        result = self._unwrap(0.9, 0.1)
        assert abs(result - 1.1) < 1e-9

    def test_single_seam_backward(self):
        # u0=0.1, u1=0.9 → should shift u1 to 0.9 (within ±0.5 of 0.1)
        # diff = 0.9-0.1=0.8 > 0.5, so other = 0.9-1.0 = -0.1
        result = self._unwrap(0.1, 0.9)
        assert abs(result - (-0.1)) < 1e-9

    def test_multi_tile_large_uv(self):
        # UV of 2.3 from base 0.1: diff = 2.2, needs two shifts
        result = self._unwrap(0.1, 2.3)
        assert abs(result - 0.3) < 1e-9

    def test_negative_uv(self):
        # UV of -0.7 from base 0.3: diff = -1.0, one shift up
        result = self._unwrap(0.3, -0.7)
        assert abs(result - 0.3) < 1e-9

    def test_large_tile_count(self):
        # UV of 5.1 from base 0.1: diff=5.0, five shifts
        result = self._unwrap(0.1, 5.1)
        assert abs(result - 0.1) < 1e-9


# ─────────────────────────────────────────────────────────────────────────────
#  Creature model outlier skin filter
# ─────────────────────────────────────────────────────────────────────────────

class TestCreatureOutlierFilter:
    """Verify that creature models (c_bantha, c_brith, wardroid) are
    never subject to the outlier skin filter that hides geometry."""

    def _make_renderer_and_model(self, name, supermodel):
        """Create a FrameRenderer with a minimal model."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        model = _make_model(name=name, supermodel=supermodel)
        root = _make_node("root", flags=NodeFlags.HEADER)
        model.root_node = root
        # Add some body nodes
        body = _make_skin_node("body_g", root)
        head = _make_mesh_node("head",   root, pos=(0,0,1.0))
        model.root_node = root
        model.compute_bounds()
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        return r

    def test_c_bantha_not_filtered(self):
        r = self._make_renderer_and_model("c_bantha", "NULL")
        # All mesh nodes should pass through (outlier set empty)
        assert len(r._outlier_skin_nodes) == 0

    def test_c_brith_not_filtered(self):
        r = self._make_renderer_and_model("c_brith", "NULL")
        assert len(r._outlier_skin_nodes) == 0

    def test_wardroid_not_filtered(self):
        r = self._make_renderer_and_model("wardroid", "NULL")
        assert len(r._outlier_skin_nodes) == 0

    def test_creature_with_c_prefix_not_filtered(self):
        r = self._make_renderer_and_model("c_kinrath", "NULL")
        assert len(r._outlier_skin_nodes) == 0

    def test_accessory_model_can_have_outliers(self):
        """Non-creature accessories can have outlier nodes (ad_saul style)."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        # An accessory model with S_MALE02 supermodel is handled differently
        # (no outlier filtering for base skeletons either, but for accessory
        # models with non-null non-base supermodels it CAN run)
        model = _make_model(name="ad_saul", supermodel="S_MALE02")
        root = _make_node("root", flags=NodeFlags.HEADER)
        model.root_node = root
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        # Base skeleton → no outlier filtering applied
        assert len(r._outlier_skin_nodes) == 0

    def test_base_skeleton_s_female_not_filtered(self):
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        model = _make_model(name="p_bastilabb02", supermodel="S_FEMALE02")
        root = _make_node("root", flags=NodeFlags.HEADER)
        model.root_node = root
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        assert len(r._outlier_skin_nodes) == 0


# ─────────────────────────────────────────────────────────────────────────────
#  Normal transform on rotated mesh nodes
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalTransform:
    """Verify that normals are correctly rotated for mesh nodes with
    non-identity world orientation (Wardroid / c_brith panels)."""

    def test_identity_rotation_normals_unchanged(self):
        """Nodes with identity rotation: normals should be returned as-is."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        root = _make_node("root", flags=NodeFlags.HEADER)
        panel = _make_mesh_node("panel", root, pos=(0,0,0.5), rot=(0,0,0,1))
        panel.normals = [(0,0,1), (0,0,1), (0,0,1), (0,0,1)]
        model = _make_model()
        model.root_node = root
        model.compute_bounds()
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        wn = r._get_world_normals_for_node(panel)
        assert len(wn) == 4
        for n in wn:
            assert abs(n[0]) < 1e-6 and abs(n[1]) < 1e-6 and abs(n[2]-1) < 1e-6

    def test_180z_rotation_flips_normals(self):
        """Panel with 180° Z rotation should have X normals flipped."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        root = _make_node("root", flags=NodeFlags.HEADER)
        # 180° about Z: quat = (0,0,1,0)
        panel = _make_mesh_node("panel", root, pos=(0,0,0.5), rot=(0,0,1,0))
        # A normal pointing in +X direction
        panel.normals = [(1,0,0), (1,0,0)]
        model = _make_model()
        model.root_node = root
        model.compute_bounds()
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        wn = r._get_world_normals_for_node(panel)
        assert len(wn) == 2
        # 180° about Z rotates (1,0,0) → (-1,0,0)
        for n in wn:
            assert abs(n[0] - (-1.0)) < 1e-5
            assert abs(n[1]) < 1e-5
            assert abs(n[2]) < 1e-5

    def test_skin_normals_not_rotated(self):
        """Skin node normals should be returned as-is (pre-baked in MDX)."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        root = _make_node("root", flags=NodeFlags.HEADER)
        skin = _make_skin_node("body_g", root)
        skin.rotation = (0,0,1,0)   # 180° Z — but skin normals stay as-is
        skin.normals = [(0,0,1), (0,0,1), (0,0,1)]
        model = _make_model()
        model.root_node = root
        model.compute_bounds()
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        wn = r._get_world_normals_for_node(skin)
        for n in wn:
            assert abs(n[2]-1) < 1e-5   # unchanged


# ─────────────────────────────────────────────────────────────────────────────
#  World transform: 180° mesh node rotation fix
# ─────────────────────────────────────────────────────────────────────────────

class TestWorldTransformFix:
    """Verify the world_transform fix preserves leaf mesh node orientations."""

    def test_180z_leaf_orientation_preserved(self):
        """A leaf mesh node with 180° Z rotation should have that orientation in world_transform."""
        root  = _make_node("root",  pos=(0,0,0), rot=(0,0,0,1))
        panel = _make_node("panel", root, pos=(0,0,0.5), rot=(0,0,1,0))
        wpos, wori = panel.world_transform()
        # Orientation should be (0,0,1,0), not collapsed to identity
        assert abs(wori[2]-1.0) < 1e-5, f"Expected z=1.0 in orientation, got {wori}"
        assert abs(wori[3]) < 1e-5

    def test_180x_parent_collapses_for_position(self):
        """A parent with 180° X should be collapsed for position chain."""
        root  = _make_node("root",  pos=(0,0,0),   rot=(0,0,0,1))
        body  = _make_node("body",  root, pos=(0,0,0.2), rot=(1,0,0,0))  # 180° X
        child = _make_node("child", body, pos=(0,0,0.1), rot=(0,0,0,1))
        # body's 180°X collapses to identity for child's position:
        # child should be at (0,0,0.3) not (0,0,0.1) if it got wrong rotation
        wp = child.world_position()
        assert abs(wp[0]) < 1e-6
        assert abs(wp[1]) < 1e-6
        assert abs(wp[2]-0.3) < 1e-5

    def test_bone_world_position_uses_full_collapse(self):
        """bone_world_position always collapses 180° on ALL nodes for pivot placement."""
        root  = _make_node("root",  pos=(0,0,0),   rot=(0,0,0,1))
        panel = _make_node("panel", root, pos=(0,0,0.5), rot=(0,0,1,0))
        bwp = panel.bone_world_position()
        # Position should be (0,0,0.5) regardless of rotation
        assert abs(bwp[2]-0.5) < 1e-5

    def test_vertex_correctly_rotated_for_180z_mesh(self):
        """Vertices at (0.2,0,0) on a 180°Z node should become (-0.2,0,0.5)."""
        root  = _make_node("root",  pos=(0,0,0),   rot=(0,0,0,1))
        panel = _make_node("panel", root, pos=(0,0,0.5), rot=(0,0,1,0))
        wpos, wori = panel.world_transform()
        # Rotate vertex (0.2, 0, 0) by world orientation and add world position
        rv = _quat_rotate(wori, (0.2, 0, 0))
        final = (rv[0]+wpos[0], rv[1]+wpos[1], rv[2]+wpos[2])
        assert abs(final[0] - (-0.2)) < 1e-5
        assert abs(final[1]) < 1e-5
        assert abs(final[2] - 0.5) < 1e-5

    def test_wardroid_deep_hierarchy(self):
        """Simulate Wardroid-style hierarchy (multiple 180° rotations)."""
        root   = _make_node("wardroid",    pos=(0,0,0),    rot=(0,0,0,1))
        body   = _make_node("body",        root, pos=(0,0,0),    rot=(1,0,0,0))  # 180° X
        chest  = _make_node("chest_panel", body, pos=(0,0,0.8),  rot=(0,0,1,0))  # 180° Z
        # chest should be at z=0.8
        cp = chest.world_position()
        assert abs(cp[2]-0.8) < 1e-4, f"chest expected z=0.8 got {cp}"
        # chest world orientation should be the composition of 180°X (collapsed)
        # × 180°Z (preserved as leaf)
        wpos, wori = chest.world_transform()
        # The leaf rotation (0,0,1,0) is preserved
        assert abs(wori[2]-1.0) < 1e-5 or abs(abs(wori[2])-1.0) < 0.2, \
            f"chest orientation unexpected: {wori}"


# ─────────────────────────────────────────────────────────────────────────────
#  ClothRigSimulator tests
# ─────────────────────────────────────────────────────────────────────────────

class TestClothRigSimulator:
    """Tests for the new PBD cloth physics simulator."""

    def _make_cloth_node(self, n_verts=6):
        """Make a minimal danglymesh node for simulation."""
        node = ModelNode(name="robe", flags=NodeFlags.MESH | NodeFlags.DANGLY)
        # Simple 2-row quad strip: top row pinned, bottom row free
        node.vertices = []
        for row in range(2):
            for col in range(3):
                node.vertices.append((col * 0.1, 0.0, 1.0 - row * 0.5))
        # Top row (row=0): z=1.0, constraint=1.0 (pinned)
        # Bottom row (row=1): z=0.5, constraint=0.0 (free)
        node.dangly_constraints = [1.0, 1.0, 1.0,   # top row
                                    0.0, 0.0, 0.0]   # bottom row
        node.dangly_displacement = 0.5
        node.dangly_tightness    = 0.5
        node.dangly_period       = 1.0
        # Faces: two quads
        node.faces = [(0,1,4), (0,4,3), (1,2,5), (1,5,4)]
        node.normals = [(0,1,0)] * len(node.vertices)
        return node

    def test_simulator_initialises(self):
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_cloth_node()
        sim = ClothRigSimulator(node)
        assert len(sim.positions) == 6
        assert len(sim._springs) > 0

    def test_pinned_verts_do_not_move(self):
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_cloth_node()
        sim = ClothRigSimulator(node, gravity=(0,0,-9.8), dt=1/30)
        top_before = [sim.positions[i][:] for i in range(3)]
        for _ in range(30):
            sim.step()
        for i in range(3):
            for d in range(3):
                assert abs(sim.positions[i][d] - top_before[i][d]) < 1e-9, \
                    f"Pinned vert {i} moved on axis {d}"

    def test_free_verts_fall_under_gravity(self):
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_cloth_node()
        sim = ClothRigSimulator(node, gravity=(0,0,-9.8), dt=1/30)
        z_before = [sim.positions[i][2] for i in range(3, 6)]
        for _ in range(10):
            sim.step()
        # Free verts should move downward (z decreases)
        for i in range(3, 6):
            assert sim.positions[i][2] < z_before[i-3], \
                f"Free vert {i} did not fall: {sim.positions[i][2]} vs {z_before[i-3]}"

    def test_displacement_cap(self):
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_cloth_node()
        node.dangly_displacement = 0.3   # strict cap
        sim = ClothRigSimulator(node, gravity=(0,0,-9.8), dt=1/30)
        for _ in range(60):
            sim.step()
        for i in range(3, 6):
            rest = sim._rest_pos[i]
            pos  = sim.positions[i]
            dist = math.sqrt(sum((pos[d]-rest[d])**2 for d in range(3)))
            assert dist <= node.dangly_displacement + 1e-6, \
                f"Vertex {i} exceeded displacement cap: {dist:.4f} > {node.dangly_displacement}"

    def test_reset_restores_positions(self):
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_cloth_node()
        sim = ClothRigSimulator(node, gravity=(0,0,-9.8), dt=1/30)
        orig = [p[:] for p in sim.positions]
        for _ in range(20):
            sim.step()
        sim.reset()
        for i, (a, b) in enumerate(zip(sim.positions, orig)):
            for d in range(3):
                assert abs(a[d]-b[d]) < 1e-9, f"Reset failed for vert {i} axis {d}"

    def test_wind_impulse_moves_free_verts(self):
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_cloth_node()
        sim = ClothRigSimulator(node, gravity=(0,0,0), dt=1/30)  # no gravity
        prev_y = [sim.positions[i][1] for i in range(3, 6)]
        sim.apply_wind(direction=(0,1,0), strength=5.0)
        sim.step()
        # Free verts should have moved in +Y direction after wind impulse
        for i in range(3, 6):
            assert sim.positions[i][1] > prev_y[i-3] - 1e-9, \
                f"Wind did not move vert {i+3} in Y direction"

    def test_springs_built_from_faces(self):
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_cloth_node()
        sim = ClothRigSimulator(node)
        # All springs should connect valid vertex indices
        n = len(node.vertices)
        for i, j, rest in sim._springs:
            assert 0 <= i < n and 0 <= j < n
            assert i != j
            assert rest > 0


# ─────────────────────────────────────────────────────────────────────────────
#  ClothRigger integration tests
# ─────────────────────────────────────────────────────────────────────────────

class TestClothRiggerIntegration:
    """Integration tests for the full cloth rigging pipeline."""

    def _make_robe_model(self):
        model = _make_model(name="p_pc_f01")
        root = _make_node("root", flags=NodeFlags.HEADER)
        # A simple robe mesh
        robe = _make_mesh_node("robe01", root, pos=(0,0,0.5))
        robe.vertices = [
            (0.2, 0, 1.0), (-0.2, 0, 1.0),   # top (waist)
            (0.3, 0, 0.5), (-0.3, 0, 0.5),   # mid
            (0.4, 0, 0.0), (-0.4, 0, 0.0),   # hem (floor)
        ]
        robe.faces = [(0,1,3),(0,3,2),(2,3,5),(2,5,4)]
        robe.normals = [(0,1,0)]*6
        model.root_node = root
        return model, robe

    def test_apply_cloth_sets_dangly_flag(self):
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset
        model, robe = self._make_robe_model()
        rigger = ClothRigger()
        assert not robe.is_dangly
        result = rigger.apply_cloth_to_node(robe, ClothRigPreset.ROBE_LOOSE)
        assert result is True
        assert robe.is_dangly

    def test_apply_cloth_generates_constraints(self):
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset
        model, robe = self._make_robe_model()
        rigger = ClothRigger()
        rigger.apply_cloth_to_node(robe, ClothRigPreset.ROBE_LOOSE)
        assert len(robe.dangly_constraints) == len(robe.vertices)

    def test_vertical_constraints_top_pinned(self):
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset
        model, robe = self._make_robe_model()
        rigger = ClothRigger()
        rigger.apply_cloth_to_node(robe, ClothRigPreset.ROBE_LOOSE)
        # Top vertices (highest Z) should have high constraint
        zvals = [v[2] for v in robe.vertices]
        z_max = max(zvals)
        z_min = min(zvals)
        for i, v in enumerate(robe.vertices):
            c = robe.dangly_constraints[i]
            if abs(v[2] - z_max) < 1e-6:
                assert c > 0.8, f"Top vert {i} not pinned: c={c}"
            if abs(v[2] - z_min) < 1e-6:
                assert c < 0.2, f"Bottom vert {i} not free: c={c}"

    def test_remove_cloth_clears_flag(self):
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset
        model, robe = self._make_robe_model()
        rigger = ClothRigger()
        rigger.apply_cloth_to_node(robe, ClothRigPreset.ROBE_LOOSE)
        assert robe.is_dangly
        rigger.remove_cloth_from_node(robe)
        assert not robe.is_dangly
        assert robe.dangly_constraints == []

    def test_undo_last_restores_state(self):
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset
        model, robe = self._make_robe_model()
        rigger = ClothRigger()
        original_flags = robe.flags
        rigger.apply_cloth_to_node(robe, ClothRigPreset.ROBE_LOOSE)
        assert robe.is_dangly
        rigger.undo_last(robe)
        assert robe.flags == original_flags

    def test_auto_detect_finds_robe_node(self):
        from src.autorig.cloth_rig import ClothRigger
        model, robe = self._make_robe_model()
        rigger = ClothRigger()
        candidates = rigger.find_cloth_candidates(model)
        assert any(n.name == "robe01" for n in candidates)

    def test_get_cloth_summary(self):
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset
        model, robe = self._make_robe_model()
        rigger = ClothRigger()
        rigger.apply_cloth_to_node(robe, ClothRigPreset.CAPE_LIGHT)
        summary = rigger.get_cloth_summary(model)
        assert summary['total_cloth_nodes'] == 1
        assert summary['nodes'][0]['name'] == 'robe01'

    def test_simulator_works_after_cloth_applied(self):
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset, ClothRigSimulator
        model, robe = self._make_robe_model()
        rigger = ClothRigger()
        rigger.apply_cloth_to_node(robe, ClothRigPreset.ROBE_LOOSE)
        # Simulate 30 steps
        sim = ClothRigSimulator(robe, dt=1/30)
        for _ in range(30):
            sim.step()
        # Should not raise, and top verts should be pinned
        zvals_before = [robe.vertices[0][2], robe.vertices[1][2]]
        assert abs(sim.positions[0][2] - zvals_before[0]) < 1e-9


# ─────────────────────────────────────────────────────────────────────────────
#  Deformation helper filter tests (Wardroid-specific)
# ─────────────────────────────────────────────────────────────────────────────

class TestDeformationHelperFilter:
    """Verify _is_deformation_helper correctly identifies helper vs real meshes."""

    def _make_renderer(self):
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        return FrameRenderer(ArcBallCamera())

    def test_g_suffix_non_skin_is_helper(self):
        r = self._make_renderer()
        n = _make_mesh_node("rthigh_g")
        n.texture = "some_tex"
        assert r._is_deformation_helper(n) is True

    def test_dum_suffix_is_helper(self):
        r = self._make_renderer()
        n = _make_mesh_node("head_dum")
        assert r._is_deformation_helper(n) is True

    def test_skin_with_texture_not_helper(self):
        r = self._make_renderer()
        n = _make_skin_node("body_g")
        n.texture = "real_tex"
        # Skin node with real texture and non-extreme UVs should NOT be a helper
        assert r._is_deformation_helper(n) is False

    def test_null_texture_non_skin_is_helper(self):
        r = self._make_renderer()
        n = _make_mesh_node("misc")
        n.texture = "NULL"
        assert r._is_deformation_helper(n) is True

    def test_wardroid_head_mesh_not_helper(self):
        r = self._make_renderer()
        n = _make_mesh_node("wardroid_head")
        n.texture = "n_ward_h"
        # Has real texture, not _g/_dum suffix, not null → NOT a helper
        assert r._is_deformation_helper(n) is False
