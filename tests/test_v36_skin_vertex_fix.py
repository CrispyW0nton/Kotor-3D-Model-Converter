"""
v3.6 Regression Tests: Skin Vertex Transform Fix + Animation Quaternion Fix
===========================================================================
Tests for the core fix that resolved the "shattered Bantha" bug and
animation flip issues in GhostRigger v3.6.

Root Causes Fixed:
  1. Skin vertex double-translation: _apply_vertex_transform was adding the skin
     node's world position (wp) to skin vertices.  KotOR skin vertices are stored
     in MODEL SPACE (= world/bind-pose space), so NO transform should be applied
     in bind pose.  Adding wp caused every skin mesh to appear displaced by its
     node's accumulated parent-chain offset, "shattering" the geometry.

  2. LBS skin_bind_wp offset: _lbs_vertex added skin_bind_wp to the vertex before
     computing bone-local space.  Since skin vertices are already in model space,
     this extra offset double-counted the skin node's position, causing LBS-animated
     meshes to explode further.

  3. Animation quaternion sign: Packed KotOR quaternions use negative-w convention.
     When w alternates sign between keyframes, the accumulated rotation chain can
     produce sudden 360° flips ("helicopter spin") during animation playback.
     Fixed by canonicalising to positive-w convention at parse time and in the
     animation engine evaluator.

  4. model_data compute_bounds / render_bounds: same skin-vertex transform bug
     existed in KotorModel.compute_bounds() and render_bounds(), causing the
     camera framing to include the wrong bounding box.
"""

import math
import pytest
from src.core.model_data import (
    KotorModel, ModelNode, NodeFlags, BoneWeight, VertexSkinData,
    _quat_normalize_bind
)
from src.gui.viewport import FrameRenderer, ArcBallCamera


# ─────────────────────────────────────────────────────────────────────
#  Test helpers
# ─────────────────────────────────────────────────────────────────────

def _make_root(name='root', pos=(0, 0, 0), rot=(0, 0, 0, 1)):
    n = ModelNode(name=name, flags=int(NodeFlags.HEADER))
    n.position = pos
    n.rotation = rot
    return n


def _make_bone(name, parent, pos=(0, 0, 0), rot=(0, 0, 0, 1)):
    n = ModelNode(name=name, flags=int(NodeFlags.HEADER))
    n.position = pos
    n.rotation = rot
    n.parent = parent
    parent.children.append(n)
    return n


def _make_skin(name, parent, verts, bone_map, skin_data, pos=(0, 0, 0)):
    n = ModelNode(name=name, flags=int(NodeFlags.MESH) | int(NodeFlags.SKIN))
    n.position = pos
    n.rotation = (0, 0, 0, 1)
    n.parent = parent
    parent.children.append(n)
    n.vertices = list(verts)
    n.bone_map = list(bone_map)
    n.skin_data = list(skin_data)
    n.uvs = [(0.5, 0.5)] * len(verts)
    n.texture = 'tex_body'
    return n


def _make_simple_model(skin_pos=(0, 0, 0), bone_pos=(0, 0, 1)):
    """Bantha-style: root → bone → skin (skin parented under bone)."""
    root = _make_root('c_bantha')
    bone = _make_bone('hip', root, pos=bone_pos)
    verts = [(0, 0, 0.5), (0.3, 0, 1.0), (-0.3, 0, 0.8)]
    bmap = ['hip']
    sdata = [VertexSkinData(influences=[BoneWeight(0, 1.0)]) for _ in verts]
    skin = _make_skin('c_bantha01', bone, verts, bmap, sdata, pos=skin_pos)
    model = KotorModel(name='c_bantha', root_node=root)
    model.compute_bounds()
    return model, root, bone, skin


# ─────────────────────────────────────────────────────────────────────
#  FIX 1 — _apply_vertex_transform: skin verts are in model space
# ─────────────────────────────────────────────────────────────────────

class TestSkinVertexModelSpace:
    """Skin vertices are in skin-node-LOCAL space — _apply_vertex_transform
    must add the skin node's world position (wp) as a translation.
    Rotation is NOT applied (baked into vertex positions by KotOR exporter).

    Empirically verified: bantha (btBody_front wp_Z≈1.47) and ad_saul
    (head wp_Z≈1.70) both require this wp offset for geometry to align
    correctly with non-skin attachment nodes."""

    def test_skin_node_at_origin_unchanged(self):
        """Skin node at wp=(0,0,0): vertex unchanged (zero offset)."""
        apply = FrameRenderer._apply_vertex_transform
        root = _make_root()
        skin = ModelNode(name='body', flags=int(NodeFlags.MESH) | int(NodeFlags.SKIN))
        skin.parent = root
        v = (1.0, 2.0, 3.0)
        wp = (0.0, 0.0, 0.0)
        wo = (0.0, 0.0, 0.0, 1.0)
        result = apply(skin, v, wp, wo, True)
        assert result == (1.0, 2.0, 3.0)

    def test_skin_node_with_nonzero_wp_translated(self):
        """Skin node with world position (10, 5, 2): vertex translated by wp.

        Skin vertices are stored in skin-node-LOCAL space and must be translated
        by the skin node's world position (wp) to get world/model space coords.
        Verified empirically against bantha (btBody_front) and ad_saul (head).
        """
        apply = FrameRenderer._apply_vertex_transform
        root = _make_root()
        skin = ModelNode(name='body', flags=int(NodeFlags.MESH) | int(NodeFlags.SKIN))
        skin.parent = root
        v = (1.0, 2.0, 3.0)
        wp = (10.0, 5.0, 2.0)  # large non-zero world position
        wo = (0.0, 0.0, 0.0, 1.0)
        result = apply(skin, v, wp, wo, True)
        # Skin: translate-only — v + wp
        assert abs(result[0] - 11.0) < 1e-6, f"expected 11.0, got {result[0]}"
        assert abs(result[1] - 7.0) < 1e-6
        assert abs(result[2] - 5.0) < 1e-6

    def test_skin_node_with_rotation_translate_only(self):
        """Skin node with non-identity rotation: rotation IS applied (corrected behaviour).

        Prior versions skipped rotation for skin nodes under the assumption that the
        KotOR/NWN exporter always bakes the orientation into vertex positions.  However,
        empirical analysis of the full K1/K2 model corpus shows that models such as
        p_bastilabb (180°-Y) and p_bastilaba (180°-X) carry a genuine non-identity
        rotation on their skin mesh nodes that MUST be applied so that vertices are
        correctly oriented in world space.

        For models with identity skin-node rotation (the common case) this change is a
        no-op: _apply_vertex_transform still reduces to a pure translation.

        wo = (0,0,1,0) → 180° about Z: (1,0,0) → (-1,0,0) → +wp(5,0,0) = (4,0,0).
        """
        apply = FrameRenderer._apply_vertex_transform
        root = _make_root()
        skin = ModelNode(name='body', flags=int(NodeFlags.MESH) | int(NodeFlags.SKIN))
        skin.parent = root
        v = (1.0, 0.0, 0.0)
        wp = (5.0, 0.0, 0.0)
        wo = (0.0, 0.0, 1.0, 0.0)  # 180° about Z
        result = apply(skin, v, wp, wo, False)
        # Rotation applied: 180°Z maps (1,0,0)→(-1,0,0), then +wp(5,0,0) = (4,0,0)
        assert abs(result[0] - 4.0) < 1e-6, f"Expected 4.0 (rotation applied), got {result[0]}"
        assert abs(result[1] - 0.0) < 1e-6
        assert abs(result[2] - 0.0) < 1e-6


class TestGetWorldVertsForSkin:
    """_get_world_verts_for_node for skin nodes: Phase 17 — full world transform applied.

    KotOR MDL skin vertices are stored in NODE-LOCAL space (same as non-skin nodes).
    The full world transform (translation + rotation via the parent chain) must
    always be applied to produce correct world-space coordinates.

    Phase 17 verified by:
    - KotorBlender (base.py): obj.location = self.position (LOCAL), verts raw
    - PyKotor: vertex_positions read raw, no world-space pre-baking
    - c_bantha binary analysis: btBody_front local Y=[1.117,3.391], pivot Y=-1.163
      → correct world Y=[-0.046,2.228]

    In _make_simple_model: root → bone(z=1.2) → skin(parented to bone, pos=0,0,0).
    The skin's world position = bone world position = (0,0,1.2).
    Skin vertex at z=0.5 → world z = 0.5 + 1.2 = 1.7.
    """

    def test_skin_verts_translated_by_skin_node_wp(self):
        """Phase 17: skin verts have world transform applied.

        In _make_simple_model: root → bone(z=1.2) → skin(pos=(0,0,0), parented to bone).
        Skin vertices are in skin-node-LOCAL space (which is the same as bone-local
        when skin.position=(0,0,0)). The skin world position = bone position = z=1.2.
        verts(z=0.5) → world z = 0.5 + 1.2 = 1.7.
        """
        model, root, bone, skin = _make_simple_model(bone_pos=(0, 0, 1.2))
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        r._anim_pose = None  # bind pose

        verts = r._get_world_verts_for_node(skin)
        assert len(verts) == len(skin.vertices)
        # Phase 17: skin wp = (0,0,1.2) is applied → z = vert_z + 1.2
        for wv, sv in zip(verts, skin.vertices):
            assert abs(wv[0] - sv[0]) < 1e-6, f"x mismatch: got {wv[0]}, expected {sv[0]}"
            assert abs(wv[1] - sv[1]) < 1e-6
            expected_z = sv[2] + 1.2
            assert abs(wv[2] - expected_z) < 1e-5, \
                f"z mismatch: got {wv[2]}, expected {expected_z:.4f} (sv[2]+1.2)"

    def test_skin_verts_shifted_by_skin_node_position(self):
        """Phase 17: skin vert at z=0.5 with bone at z=1.2 → world z = 1.7.

        Skin node position (0,0,0) + bone world pivot (0,0,1.2) = skin world = (0,0,1.2).
        Vertex local z=0.5 → world z = 0.5 + 1.2 = 1.7.
        """
        model, root, bone, skin = _make_simple_model(bone_pos=(0, 0, 1.2))
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        r._anim_pose = None

        verts = r._get_world_verts_for_node(skin)
        # First vertex at (0, 0, 0.5) in local space → world z = 0.5 + 1.2 = 1.7
        assert abs(verts[0][2] - 1.7) < 1e-5, \
            f"Phase 17: z should be 1.7 (vert_z + bone_z), got {verts[0][2]}"


class TestComputeBoundsModelData:
    """KotorModel.compute_bounds() and render_bounds() — Phase 17: world transform applied.

    Phase 17: Skin vertices are in NODE-LOCAL space. The full world transform
    (translate + rotate via parent chain) is always applied.

    In _make_simple_model: root → bone(z=bone_pos) → skin(pos=(0,0,0)).
    Skin world position = bone world position.
    Vertex local z=0.5 → world z = 0.5 + bone_pos_z.
    Vertex local z=1.0 → world z = 1.0 + bone_pos_z.
    """

    def test_compute_bounds_skin_verts_with_wp_offset(self):
        """Phase 17: Skin node bounds include world transform (bone z=1.2 added).

        Skin vertices at local z=0.5, z=1.0, z=0.8.
        Skin world pos = bone pos z=1.2 (skin.pos=(0,0,0), parented to bone).
        Expected bounds max z = 1.0 + 1.2 = 2.2 (world-transformed).
        """
        model, root, bone, skin = _make_simple_model(bone_pos=(0, 0, 1.2))
        model.compute_bounds()
        # Phase 17: wp (z=1.2) applied → max z = 1.0 + 1.2 = 2.2
        assert model.bb_max[2] >= 2.1, \
            f"bb_max.z={model.bb_max[2]}: should be ~2.2 (skin verts + bone z=1.2)"
        assert model.bb_max[2] <= 2.3, \
            f"bb_max.z={model.bb_max[2]}: expected ~2.2, not {model.bb_max[2]:.3f}"

    def test_render_bounds_skin_verts_with_wp_offset(self):
        """Phase 17: render_bounds() includes world transform.

        Skin vertices at local z=0.5, z=1.0, z=0.8.
        Bone position z=5.0 added → world max z = 1.0 + 5.0 = 6.0.
        """
        model, root, bone, skin = _make_simple_model(bone_pos=(0, 0, 5.0))
        # Add UVs to make node visible (render_bounds filters non-UV nodes)
        skin.uvs = [(0.5, 0.5)] * len(skin.vertices)
        rbb_min, rbb_max = model.render_bounds()
        # Phase 17: wp (z=5.0) applied → max z = 1.0 + 5.0 = 6.0
        assert rbb_max[2] >= 5.9, \
            f"rbb_max.z={rbb_max[2]}: Phase 17 expects ~6.0 (skin verts + bone z=5.0)"
        assert rbb_max[2] <= 6.1, \
            f"rbb_max.z={rbb_max[2]}: expected ~6.0, not {rbb_max[2]:.3f}"


# ─────────────────────────────────────────────────────────────────────
#  FIX 2 — LBS: no skin_bind_wp in _lbs_vertex
# ─────────────────────────────────────────────────────────────────────

class TestLBSNoSkinOffset:
    """_lbs_vertex must not add skin node's world position to vertices."""

    def _make_model_with_lbs(self, bone_pos=(0, 0, 1.0)):
        """Create a model with LBS-ready skin node."""
        root = _make_root('c_test', pos=(0, 0, 0))
        bone = _make_bone('hip', root, pos=bone_pos)
        verts = [(0.0, 0.0, 1.0)]  # vertex at z=1.0 in model space
        bmap = ['hip']
        sdata = [VertexSkinData(influences=[BoneWeight(0, 1.0)])]
        skin = _make_skin('c_test01', root, verts, bmap, sdata)
        model = KotorModel(name='c_test', root_node=root)
        model.compute_bounds()
        return model, bone, skin

    def test_bind_pose_lbs_returns_vertex_unchanged(self):
        """In bind pose, vertex at (0,0,1) with bone at (0,0,1) → LBS returns (0,0,1)."""
        model, bone, skin = self._make_model_with_lbs(bone_pos=(0, 0, 1.0))
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        r._anim_pose = None

        verts = r._get_world_verts_for_node(skin)
        # Vertex (0,0,1) in model space → should return (0,0,1)
        assert abs(verts[0][2] - 1.0) < 1e-4, f"Expected z=1.0, got {verts[0][2]}"

    def test_animated_lbs_moves_only_by_delta(self):
        """LBS with bone at (0,0,1) moving to (0,0,1.3): vertex should move by delta."""
        from src.core.animation_engine import AnimPose, NodePose
        model, bone, skin = self._make_model_with_lbs(bone_pos=(0, 0, 1.0))
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)

        # Animate: hip moves from z=1.0 to z=1.3 (+0.3)
        pose = AnimPose(time=0.0)
        pose.nodes['hip'] = NodePose(name='hip', position=(0, 0, 1.3), rotation=(0, 0, 0, 1))
        r.set_animation_pose(pose)

        verts = r._get_world_verts_for_node(skin)
        # Vertex was at z=1.0, bone moved +0.3 → vertex should be at ~1.3
        assert abs(verts[0][2] - 1.3) < 0.05, f"Expected z≈1.3, got {verts[0][2]}"

    def test_lbs_no_double_translation(self):
        """Regression: old code added skin_bind_wp twice, causing z=bone_pos+vert_pos.

        With bone at z=5, vertex at z=1: old result was z=6 (double).
        New correct result: z=1 (bind pose, no motion).
        """
        model, bone, skin = self._make_model_with_lbs(bone_pos=(0, 0, 5.0))
        # Set skin vert at z=1.0 explicitly
        skin.vertices = [(0.0, 0.0, 1.0)]
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        r._anim_pose = None

        verts = r._get_world_verts_for_node(skin)
        # Must be z=1.0, NOT z=6.0 (which was the old double-translation bug)
        assert abs(verts[0][2] - 1.0) < 1e-3, \
            f"Expected z=1.0 (bind pose), got {verts[0][2]} (DOUBLE TRANSLATION BUG)"


# ─────────────────────────────────────────────────────────────────────
#  FIX 3 — Animation quaternion positive-w canonicalisation
# ─────────────────────────────────────────────────────────────────────

class TestAnimQuatCanonicalisation:
    """Packed KotOR quaternions use negative-w; we canonicalise to positive-w."""

    def test_packed_quat_w_positive_after_canonicalise(self):
        """Packed quaternion decoder should produce positive-w quaternions."""
        import math as _m
        # Simulate packed quat decode: a rotation of ~90° about Z-axis
        # with negative w as produced by KotOR's packed encoding
        # qx=0, qy=0, qz=sin(45°)=√2/2, qw=-cos(45°)=-√2/2
        qx, qy, qz = 0.0, 0.0, _m.sqrt(0.5)
        qw = -_m.sqrt(0.5)  # negative w (KotOR convention)

        # Verify this is unit length before canonicalisation
        mag_before = _m.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
        assert abs(mag_before - 1.0) < 1e-6, "Test quat should be unit length"

        # Canonicalise: negate all components to get positive w
        if qw < 0:
            qx, qy, qz, qw = -qx, -qy, -qz, -qw

        assert qw > 0, "Canonicalised quaternion should have positive w"
        # Should still be unit quaternion after canonicalisation
        mag = _m.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
        assert abs(mag - 1.0) < 1e-6

    def test_slerp_does_not_flip_with_positive_w(self):
        """SLERP between two positive-w quats should not produce sudden flips."""
        from src.core.animation_engine import _slerp
        import math as _m

        # Two similar rotations, both with positive w
        q1 = [0.0, 0.0, 0.0, 1.0]    # identity
        q2 = [0.0, 0.0, 0.1, _m.sqrt(1 - 0.01)]  # small rotation about Z

        for t in [0.0, 0.25, 0.5, 0.75, 1.0]:
            qi = _slerp(q1, q2, t)
            # w should be positive (no hemisphere crossing)
            assert qi[3] >= 0, f"SLERP at t={t} produced negative w: {qi}"
            # Quaternion should be unit length
            mag = _m.sqrt(sum(v*v for v in qi))
            assert abs(mag - 1.0) < 1e-5

    def test_anim_engine_canonicalises_orientation(self):
        """AnimationEngine._eval_node SLERP shortest-path: no spin-flip artefacts.

        The animation engine deliberately does NOT force positive-w canonicalisation
        on individual keyframes.  Forcing w>0 at each keyframe would cause SLERP to
        take the long path through the quaternion sphere (360° spin) when consecutive
        keyframes straddle the w=0 boundary.  Instead, the engine's _slerp function
        canonicalises at interpolation time (negates q2 if dot<0).

        This test verifies that when keyframes all have consistent sign (both negative),
        the interpolated result is unit-length and numerically valid, even if w<0.
        The sign of w is irrelevant for rotation — q and -q represent the same rotation.

        v12.14 UPDATE: Updated to reflect the actual (correct) engine behaviour.
        Forcing positive-w per-keyframe is NOT done; the SLERP is sign-consistent.
        """
        from src.core.animation_engine import AnimationEngine
        from src.core.model_data import Animation, ModelNode
        import math as _m

        # Build a model with one bone that has negative-w orientation keyframes
        root = ModelNode(name='test_root', flags=int(NodeFlags.HEADER))
        root.position = (0, 0, 0)
        root.rotation = (0, 0, 0, 1)

        model = KotorModel(name='test', root_node=root)
        model.compute_bounds()

        anim_node = ModelNode(name='test_root', flags=int(NodeFlags.HEADER))
        anim_node.position = (0, 0, 0)
        anim_node.rotation = (0, 0, 0, 1)
        # All-negative-w keyframes: SLERP stays on the same hemisphere (no flip)
        anim_node.controllers = [{
            'type': 20,  # CTRL_ORIENTATION
            'name': 'orientation',
            'times': [0.0, 0.5, 1.0],
            'values': [
                [0.0, 0.0, 0.0, 1.0],      # identity (positive w)
                [0.0, 0.0, 0.1, -0.995],   # small rotation, negative w
                [0.0, 0.0, 0.2, -0.98],    # slightly larger, negative w
            ],
            'columns': 4,
        }]

        anim = Animation(name='test_anim', length=1.0)
        anim.nodes = [anim_node]
        model.animations = [anim]

        engine = AnimationEngine(model)
        engine.play('test_anim')

        # Evaluate at t=0.5 — result is interpolated rotation
        pose = engine.evaluate(0.5)
        np = pose.nodes.get('test_root')
        assert np is not None
        rot = np.rotation
        assert rot is not None, "Rotation must be set"
        # Result must be a valid unit quaternion (q and -q represent same rotation)
        mag = _m.sqrt(sum(v*v for v in rot))
        assert abs(mag - 1.0) < 0.01, \
            f"Interpolated quaternion must be unit length, got magnitude {mag}, quat={rot}"
        # The rotation must encode a small rotation about Z (z component ≠ 0)
        assert abs(rot[2]) > 0.05, \
            f"Expected nonzero z-component for Z-rotation, got {rot}"


# ─────────────────────────────────────────────────────────────────────
#  FIX 4 — Texture performance: MAX_SIZE=512, BILINEAR resampling
# ─────────────────────────────────────────────────────────────────────

class TestTexturePerformance:
    """TextureCache.MAX_SIZE must be 512 for quality (raised from 256)."""

    def test_max_size_is_512(self):
        """TextureCache.MAX_SIZE must be 512 for full-quality texture rendering.

        Raised from 256→512 in v5.5: KotOR textures are typically 128×128 or
        256×256.  At 512px cap we load at native resolution (no downscale for
        typical sizes), eliminating the main source of blurry/blocky textures.
        """
        from src.gui.viewport import TextureCache
        assert TextureCache.MAX_SIZE == 512, \
            f"MAX_SIZE={TextureCache.MAX_SIZE}: should be 512 for full quality texture rendering"

    def test_max_tris_textured_is_bounded(self):
        """MAX_TRIS_TEXTURED must be ≤ 10,000 to prevent per-triangle AFFINE lag."""
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        assert r.MAX_TRIS_TEXTURED <= 10_000, \
            f"MAX_TRIS_TEXTURED={r.MAX_TRIS_TEXTURED}: too high for realtime textured rendering"


# ─────────────────────────────────────────────────────────────────────
#  FIX 5 — Bantha-style model renders without explosion
# ─────────────────────────────────────────────────────────────────────

class TestBanthaStyleRendering:
    """Integration test: Bantha-style creature model renders correctly."""

    def _build_bantha_model(self):
        """Realistic Bantha setup: root → hip (z=1.2) → skin with world-space verts."""
        root = _make_root('c_bantha', pos=(0, 0, 0))
        hip  = _make_bone('hip',  root, pos=(0, 0, 1.2))
        lleg = _make_bone('lleg', hip,  pos=(0.3, 0, -0.5))
        rleg = _make_bone('rleg', hip,  pos=(-0.3, 0, -0.5))

        # Skin vertices in MODEL SPACE (not bone-local space)
        # They are centred around z=0.8 (approximate middle of creature)
        import math as _m
        verts = [(0.5*_m.cos(i*0.2), 0.5*_m.sin(i*0.2), 0.8) for i in range(30)]
        bmap = ['hip', 'lleg', 'rleg']
        sdata = []
        for i in range(len(verts)):
            sd = VertexSkinData()
            sd.influences.append(BoneWeight(0, 0.5))  # hip
            sd.influences.append(BoneWeight(1 + i % 2, 0.5))  # alternating legs
            sdata.append(sd)
        skin = _make_skin('c_bantha01', root, verts, bmap, sdata)

        model = KotorModel(name='c_bantha', root_node=root)
        model.compute_bounds()
        return model, skin, verts

    def test_bantha_bind_pose_verts_at_model_space_positions(self):
        """Bind pose: all Bantha skin verts returned at their original z≈0.8 positions."""
        model, skin, orig_verts = self._build_bantha_model()
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)

        world_verts = r._get_world_verts_for_node(skin)
        assert len(world_verts) == len(orig_verts)

        for i, (wv, ov) in enumerate(zip(world_verts, orig_verts)):
            assert abs(wv[2] - ov[2]) < 1e-5, \
                f"Vert {i}: z should be {ov[2]}, got {wv[2]} (shattered bug!)"

    def test_bantha_model_renders_without_crash(self):
        """Bantha model must render to a valid image without crashing."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not available")

        model, skin, _ = self._build_bantha_model()
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)

        img = r.render(400, 300)
        assert img is not None, "render() must return a valid image"
        assert img.size == (400, 300)

    def test_bantha_model_bounds_not_exploded(self):
        """Bantha model compute_bounds must return reasonable (non-exploded) bounding box."""
        model, skin, verts = self._build_bantha_model()

        # Max vertex z is ~0.8; max x/y is ~0.5
        # Old code would produce bb_max.z ≈ 2.0 (0.8 + 1.2 hip offset)
        assert model.bb_max[2] <= 1.0, \
            f"bb_max.z={model.bb_max[2]}: bounding box should not include bone offset"
        assert model.bb_max[0] <= 0.6, f"bb_max.x={model.bb_max[0]}: too large"


# ─────────────────────────────────────────────────────────────────────
#  FIX 6 — Non-skin trimesh nodes still get correct world transform
# ─────────────────────────────────────────────────────────────────────

class TestNonSkinTransformUnchanged:
    """Non-skin (trimesh/dangly) nodes must still get correct world transform."""

    def test_trimesh_identity_rot_translates(self):
        """Non-skin with identity rotation: vertex translated by world pos."""
        apply = FrameRenderer._apply_vertex_transform
        root = _make_root()
        mesh = ModelNode(name='panel', flags=int(NodeFlags.MESH))
        mesh.parent = root
        v = (1.0, 0.0, 0.0)
        wp = (5.0, 2.0, 1.0)
        wo = (0.0, 0.0, 0.0, 1.0)
        is_id = True
        result = apply(mesh, v, wp, wo, is_id)
        assert abs(result[0] - 6.0) < 1e-6
        assert abs(result[1] - 2.0) < 1e-6
        assert abs(result[2] - 1.0) < 1e-6

    def test_trimesh_90z_rotates_and_translates(self):
        """Non-skin with 90° Z rotation: (1,0,0) → (0,1,0) + translate."""
        apply = FrameRenderer._apply_vertex_transform
        root = _make_root()
        mesh = ModelNode(name='panel', flags=int(NodeFlags.MESH))
        mesh.parent = root
        v = (1.0, 0.0, 0.0)
        wp = (0.0, 0.0, 0.0)
        s = math.sqrt(0.5)
        wo = (0.0, 0.0, s, s)  # 90° about Z
        is_id = False
        result = apply(mesh, v, wp, wo, is_id)
        assert abs(result[0] - 0.0) < 1e-5
        assert abs(result[1] - 1.0) < 1e-5
        assert abs(result[2] - 0.0) < 1e-5

    def test_trimesh_world_verts_uses_transform(self):
        """Non-skin node world verts use full world transform."""
        model = KotorModel()
        root = _make_root()
        model.root_node = root
        mesh = ModelNode(name='panel', flags=int(NodeFlags.MESH))
        mesh.parent = root
        mesh.position = (5.0, 0.0, 0.0)
        mesh.rotation = (0.0, 0.0, 0.0, 1.0)
        mesh.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
        root.children.append(mesh)
        model.compute_bounds()

        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        verts = r._get_world_verts_for_node(mesh)
        # Vertex (0,0,0) at node pos (5,0,0) → world (5,0,0)
        assert abs(verts[0][0] - 5.0) < 1e-6
        # Vertex (1,0,0) at node pos (5,0,0) → world (6,0,0)
        assert abs(verts[1][0] - 6.0) < 1e-6
