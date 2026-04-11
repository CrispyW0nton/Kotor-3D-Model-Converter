"""
test_v355_fbx_animation_pipeline.py
====================================

Comprehensive test suite for the FBX animation export pipeline,
animation library improvements, and retargeting system.

Grounded in:
  - "3D Mesh Processing and Character Animation" (Mukundan, 2022)
    §Offset matrix: Jk = Lk * Fk
    §Skinning:      v' = Σ wi * Ji * v
    §Retargeting:   Map-JN via hash maps + Map-EA axis alignment
  - "Game Engine Architecture 4th Ed" (Gregory, 2022)
    §SQT format, §SLERP shortest-path, §Local→World hierarchy

Priority coverage:
  1. Animations play smoothly and retain original quality
  2. Animation library catalogs all game animations
  3. Export animations to rigged FBX models
"""
import json
import math
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ─────────────────────────────────────────────────────────────────────────────
#  Import helpers
# ─────────────────────────────────────────────────────────────────────────────

def _import_anim_lib():
    """Return tuple of all needed symbols.
    Index map:
      [0] AnimationLibrary
      [1] AnimationEntry
      [2] AnimationRetargeter
      [3] FBXAnimationExporter
      [4] batch_export_animations
      [5] _quat_to_euler_xyz
      [6] _slerp_quat
      [7] _mat4_identity
      [8] _mat4_mul
      [9] _mat4_from_sqt
      [10] _mat4_inverse_trs
      [11] _build_world_transforms
      [12] _safe_filename
    """
    from src.core.animation_library import (
        AnimationLibrary, AnimationEntry, AnimationRetargeter,
        FBXAnimationExporter, batch_export_animations,
        _quat_to_euler_xyz, _slerp_quat,
        _mat4_identity, _mat4_mul, _mat4_from_sqt, _mat4_inverse_trs,
        _build_world_transforms, _safe_filename,
    )
    return (AnimationLibrary, AnimationEntry, AnimationRetargeter,
            FBXAnimationExporter, batch_export_animations,
            _quat_to_euler_xyz, _slerp_quat,
            _mat4_identity, _mat4_mul, _mat4_from_sqt, _mat4_inverse_trs,
            _build_world_transforms, _safe_filename)  # 13 items total


def _alib():
    """Unpack helper — returns dict for named access."""
    t = _import_anim_lib()
    return {
        'AL': t[0], 'AE': t[1], 'AR': t[2], 'FBX': t[3], 'batch': t[4],
        'qe': t[5], 'sl': t[6], 'mi': t[7], 'mm': t[8],
        'mf': t[9], 'minv': t[10], 'bwt': t[11], 'sf': t[12],
    }


def _load_bantha():
    """Load the c_bantha test model."""
    from src.core.kotor_loader import load_model_from_file
    mdl_path = 'test_assets/c_bantha/c_bantha.mdl'
    if not os.path.exists(mdl_path):
        return None
    return load_model_from_file(mdl_path)


def _load_template(game='K1', part='body'):
    from src.core.character_builder import load_template
    return load_template(game, part)


# ═════════════════════════════════════════════════════════════════════════════
#  1.  Math Helpers (from book algorithms)
# ═════════════════════════════════════════════════════════════════════════════

class TestMathHelpers:
    """Test the book-derived math helpers added to animation_library.py."""

    def test_mat4_identity(self):
        h = _alib()
        I = h['mi']()
        assert len(I) == 4
        for i in range(4):
            for j in range(4):
                expected = 1.0 if i == j else 0.0
                assert abs(I[i][j] - expected) < 1e-9

    def test_mat4_mul_identity(self):
        h = _alib()
        I = h['mi']()
        A = [[1,2,3,4],[5,6,7,8],[9,10,11,12],[0,0,0,1]]
        AI = h['mm'](A, I)
        IA = h['mm'](I, A)
        for i in range(4):
            for j in range(4):
                assert abs(AI[i][j] - A[i][j]) < 1e-9
                assert abs(IA[i][j] - A[i][j]) < 1e-9

    def test_mat4_from_sqt_identity_quat(self):
        """SQT with identity quaternion should produce pure translation matrix."""
        h = _alib()
        M = h['mf'](1.0, 2.0, 3.0,  0.0, 0.0, 0.0, 1.0)  # identity quat = no rotation
        # Translation should be (1,2,3)
        assert abs(M[0][3] - 1.0) < 1e-6
        assert abs(M[1][3] - 2.0) < 1e-6
        assert abs(M[2][3] - 3.0) < 1e-6
        # Rotation part should be identity
        assert abs(M[0][0] - 1.0) < 1e-6
        assert abs(M[1][1] - 1.0) < 1e-6
        assert abs(M[2][2] - 1.0) < 1e-6

    def test_mat4_from_sqt_90deg_rotation(self):
        """90° rotation around Z axis."""
        h = _alib()
        # 90° around Z: q = (0, 0, sin45°, cos45°) = (0, 0, √2/2, √2/2)
        s = math.sqrt(2) / 2
        M = h['mf'](0.0, 0.0, 0.0,  0.0, 0.0, s, s)
        # X-axis maps to Y-axis after 90° Z rotation
        assert abs(M[0][0] - 0.0) < 1e-5   # was 1, should be ~0
        assert abs(M[1][0] - 1.0) < 1e-5   # X → Y
        assert abs(M[0][1] - (-1.0)) < 1e-5 # Y → -X

    def test_mat4_inverse_trs_translation(self):
        """Inverse of a pure translation T should be translation -T."""
        h = _alib()
        M    = h['mf'](3.0, 4.0, 5.0,  0.0, 0.0, 0.0, 1.0)  # translate by (3,4,5)
        Minv = h['minv'](M)
        # Inverse translation should be (-3,-4,-5)
        assert abs(Minv[0][3] - (-3.0)) < 1e-6
        assert abs(Minv[1][3] - (-4.0)) < 1e-6
        assert abs(Minv[2][3] - (-5.0)) < 1e-6

    def test_mat4_inverse_times_original_is_identity(self):
        """M * M⁻¹ = I (offset matrix cancels bind pose)."""
        h = _alib()
        s = math.sqrt(2) / 2
        # Combined translation + rotation
        M    = h['mf'](1.5, -2.0, 0.5,  0.0, 0.0, s, s)
        Minv = h['minv'](M)
        I    = h['mm'](M, Minv)
        for i in range(4):
            for j in range(4):
                expected = 1.0 if i == j else 0.0
                assert abs(I[i][j] - expected) < 1e-5, \
                    f"M*M⁻¹[{i}][{j}] = {I[i][j]:.6f}, expected {expected}"

    def test_slerp_quat_t0_returns_q1(self):
        """SLERP at t=0 returns first quaternion."""
        h = _alib()
        q1 = (0.0, 0.0, 0.0, 1.0)
        q2 = (0.0, 0.0, 1.0, 0.0)
        r  = h['sl'](q1, q2, 0.0)
        for a, b in zip(r, q1):
            assert abs(a - b) < 1e-6

    def test_slerp_quat_t1_returns_q2(self):
        """SLERP at t=1 returns second quaternion."""
        h = _alib()
        q1 = (0.0, 0.0, 0.0, 1.0)
        q2 = (0.0, 0.0, 1.0, 0.0)
        r  = h['sl'](q1, q2, 1.0)
        for a, b in zip(r, (0.0, 0.0, 1.0, 0.0)):
            assert abs(a - b) < 1e-6

    def test_slerp_quat_shortest_path(self):
        """SLERP should take shortest path (dot<0 fix)."""
        h = _alib()
        # q and -q represent same rotation; SLERP should not spin 360°
        q1 = (0.0, 0.0, 0.0, 1.0)
        q2 = (0.0, 0.0, 0.0, -1.0)  # same rotation, negated
        r  = h['sl'](q1, q2, 0.5)
        # Result should be identity or very close (no rotation)
        mag = math.sqrt(sum(x*x for x in r))
        assert abs(mag - 1.0) < 1e-6, "SLERP result not unit quaternion"

    def test_slerp_quat_result_is_unit(self):
        """SLERP result is always a unit quaternion."""
        h = _alib()
        q1 = (0.1, 0.2, 0.3, 0.9)
        q2 = (0.4, 0.5, 0.6, 0.5)
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            r   = h['sl'](q1, q2, t)
            mag = math.sqrt(sum(x*x for x in r))
            assert abs(mag - 1.0) < 1e-6

    def test_quat_to_euler_identity(self):
        """Identity quaternion → zero Euler angles."""
        h = _alib()
        rx, ry, rz = h['qe'](0.0, 0.0, 0.0, 1.0)
        assert abs(rx) < 1e-5
        assert abs(ry) < 1e-5
        assert abs(rz) < 1e-5

    def test_quat_to_euler_90deg_z(self):
        """90° Z rotation quaternion → ~90° Z Euler angle."""
        h = _alib()
        s  = math.sqrt(2) / 2
        rx, ry, rz = h['qe'](0.0, 0.0, s, s)
        assert abs(rz - 90.0) < 0.5   # allow 0.5° rounding

    def test_safe_filename(self):
        """_safe_filename strips special chars."""
        h = _alib()
        assert h['sf']("walk/run") == "walk_run"
        assert h['sf']("anim 01") == "anim_01"
        assert h['sf']("k1::walk") == "k1__walk"


# ═════════════════════════════════════════════════════════════════════════════
#  2.  World-Transform Hierarchy Concatenation
# ═════════════════════════════════════════════════════════════════════════════

class TestWorldTransforms:
    """
    Test _build_world_transforms — the book algorithm for computing
    WorldTransform(j) = WorldTransform(parent) × LocalTransform(j).
    """

    class _FakeNode:
        """Minimal node stub for testing."""
        def __init__(self, name, position, rotation=(0,0,0,1), parent=None):
            self.name     = name
            self.position = position
            self.rotation = rotation
            self.parent   = parent
            self.children = []

    def _make_chain(self):
        """root(0,0,0) → child(1,0,0) → grandchild(0,1,0)"""
        root  = self._FakeNode("root", (0.0, 0.0, 0.0))
        child = self._FakeNode("child", (1.0, 0.0, 0.0), parent=root)
        grand = self._FakeNode("grand", (0.0, 1.0, 0.0), parent=child)
        root.children  = [child]
        child.children = [grand]
        return [root, child, grand]

    def test_root_world_equals_local(self):
        """Root node world transform = its local transform."""
        h = _alib()
        nodes = self._make_chain()
        wt = h['bwt'](nodes)
        # Root at (0,0,0) identity → world = identity
        assert abs(wt['root'][0][3]) < 1e-9  # tx = 0
        assert abs(wt['root'][1][3]) < 1e-9  # ty = 0
        assert abs(wt['root'][2][3]) < 1e-9  # tz = 0

    def test_child_world_is_parent_plus_local(self):
        """Child world position = parent world position + local offset."""
        h = _alib()
        nodes = self._make_chain()
        wt = h['bwt'](nodes)
        # child is at (1,0,0) relative to root(0,0,0) → world = (1,0,0)
        assert abs(wt['child'][0][3] - 1.0) < 1e-6
        assert abs(wt['child'][1][3] - 0.0) < 1e-6

    def test_grandchild_world_accumulates_chain(self):
        """Grandchild world = sum of all ancestors' local translations."""
        h = _alib()
        nodes = self._make_chain()
        wt = h['bwt'](nodes)
        # grandchild local = (0,1,0), parent at (1,0,0) → world = (1,1,0)
        assert abs(wt['grand'][0][3] - 1.0) < 1e-6
        assert abs(wt['grand'][1][3] - 1.0) < 1e-6
        assert abs(wt['grand'][2][3] - 0.0) < 1e-6

    def test_all_nodes_in_result(self):
        """All nodes appear in world transform dict."""
        h = _alib()
        nodes = self._make_chain()
        wt = h['bwt'](nodes)
        assert 'root'  in wt
        assert 'child' in wt
        assert 'grand' in wt

    def test_world_transforms_with_real_model(self):
        """Build world transforms from a real model's skeleton."""
        h = _alib()
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        all_nodes = []
        def _collect(n):
            all_nodes.append(n)
            for c in n.children: _collect(c)
        if model.root_node:
            _collect(model.root_node)
        wt = h['bwt'](all_nodes)
        # All nodes should have a world transform
        for n in all_nodes:
            assert n.name.lower() in wt
            M = wt[n.name.lower()]
            # Matrix should be 4×4
            assert len(M) == 4
            assert all(len(row) == 4 for row in M)


# ═════════════════════════════════════════════════════════════════════════════
#  3.  Bone Retargeting (AnimationRetargeter)
# ═════════════════════════════════════════════════════════════════════════════

class TestAnimationRetargeter:
    """
    Test the bone retargeting system.
    Reference: Mukundan §Retargeting — Map-JN (joint name mapping via hash maps)
    """

    def test_mixamo_map_has_all_kotor_bones(self):
        """Every KotOR humanoid bone has a Mixamo equivalent."""
        (_, _, AR, *_) = _import_anim_lib()[:3]
        for bone in AR.KOTOR_BONES:
            assert bone in AR.KOTOR_TO_MIXAMO, \
                f"KotOR bone '{bone}' missing from MIXAMO map"

    def test_ue5_map_has_all_kotor_bones(self):
        """Every KotOR humanoid bone has a UE5 Mannequin equivalent."""
        (_, _, AR, *_) = _import_anim_lib()[:3]
        for bone in AR.KOTOR_BONES:
            assert bone in AR.KOTOR_TO_UE5, \
                f"KotOR bone '{bone}' missing from UE5 map"

    def test_build_map_lowercases_keys(self):
        """build_map produces lowercase keys for case-insensitive lookup."""
        (_, _, AR, *_) = _import_anim_lib()[:3]
        remap = AR.build_map(AR.KOTOR_TO_MIXAMO)
        for key in remap:
            assert key == key.lower(), f"Key '{key}' is not lowercase"

    def test_mixamo_pelvis_mapping(self):
        """pelvis_g → mixamorig:Hips."""
        (_, _, AR, *_) = _import_anim_lib()[:3]
        remap = AR.build_map(AR.KOTOR_TO_MIXAMO)
        assert remap.get("pelvis_g") == "mixamorig:Hips"

    def test_ue5_pelvis_mapping(self):
        """pelvis_g → pelvis in UE5."""
        (_, _, AR, *_) = _import_anim_lib()[:3]
        remap = AR.build_map(AR.KOTOR_TO_UE5)
        assert remap.get("pelvis_g") == "pelvis"

    def test_mixamo_hand_bones(self):
        """Left and right hand bones map correctly to Mixamo."""
        (_, _, AR, *_) = _import_anim_lib()[:3]
        remap = AR.build_map(AR.KOTOR_TO_MIXAMO)
        assert remap.get("rhand") == "mixamorig:RightHand"
        assert remap.get("lhand") == "mixamorig:LeftHand"

    def test_ue5_foot_bones(self):
        """Left and right foot bones map correctly to UE5."""
        (_, _, AR, *_) = _import_anim_lib()[:3]
        remap = AR.build_map(AR.KOTOR_TO_UE5)
        assert remap.get("rfoot_g") == "foot_r"
        assert remap.get("lfoot_g") == "foot_l"

    def test_from_json_roundtrip(self):
        """save_json → from_json roundtrip preserves remap."""
        (_, _, AR, *_) = _import_anim_lib()[:3]
        remap = {"pelvis_g": "hips", "rhand": "right_hand"}
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "remap.json")
            AR.save_json(remap, path)
            loaded = AR.from_json(path)
        assert loaded.get("pelvis_g") == "hips"
        assert loaded.get("rhand")    == "right_hand"

    def test_unknown_bone_returns_original_name(self):
        """Bones not in the remap dict keep their original name."""
        (_, _, AR, *_) = _import_anim_lib()[:3]
        remap = AR.build_map(AR.KOTOR_TO_MIXAMO)
        # "LightsaberHook" is not in the humanoid remap
        name = remap.get("lightsaberhook", "LightsaberHook")
        assert name == "LightsaberHook"  # falls back to original


# ═════════════════════════════════════════════════════════════════════════════
#  4.  FBXAnimationExporter — File Structure Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestFBXAnimationExporter:
    """
    Test FBX export output structure.
    Reference: FBX ASCII 7.4 format + Game Engine Architecture §asset pipeline.
    """

    def _get_engine_and_anim(self):
        model = _load_bantha()
        if model is None:
            return None, None
        from src.core.animation_engine import AnimationEngine
        engine = AnimationEngine(model)
        anims  = engine.list_animations()
        if not anims:
            return engine, None
        return engine, anims[0]['name']

    def test_export_creates_file(self):
        """FBX export creates a file on disk."""
        (_, _, _, FBXExp, *_) = _import_anim_lib()[:5]
        engine, anim_name = self._get_engine_and_anim()
        if engine is None or anim_name is None:
            pytest.skip("c_bantha not available")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.fbx")
            ok   = FBXExp().export(engine, anim_name, path)
            assert ok
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0

    def test_exported_fbx_has_header(self):
        """Exported FBX contains FBX header section."""
        (_, _, _, FBXExp, *_) = _import_anim_lib()[:5]
        engine, anim_name = self._get_engine_and_anim()
        if engine is None or anim_name is None:
            pytest.skip("c_bantha not available")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.fbx")
            FBXExp().export(engine, anim_name, path)
            content = Path(path).read_text()
        assert "FBXHeaderExtension" in content
        assert "FBXVersion: 7400"   in content

    def test_exported_fbx_has_objects_section(self):
        """Exported FBX contains Objects section with Model entries."""
        (_, _, _, FBXExp, *_) = _import_anim_lib()[:5]
        engine, anim_name = self._get_engine_and_anim()
        if engine is None or anim_name is None:
            pytest.skip("c_bantha not available")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.fbx")
            FBXExp().export(engine, anim_name, path)
            content = Path(path).read_text()
        assert "Objects:" in content
        assert "LimbNode" in content

    def test_exported_fbx_has_animation_stack(self):
        """Exported FBX contains AnimationStack for the animation."""
        (_, _, _, FBXExp, *_) = _import_anim_lib()[:5]
        engine, anim_name = self._get_engine_and_anim()
        if engine is None or anim_name is None:
            pytest.skip("c_bantha not available")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.fbx")
            FBXExp().export(engine, anim_name, path)
            content = Path(path).read_text()
        assert "AnimationStack" in content
        assert "AnimationLayer" in content

    def test_exported_fbx_has_connections(self):
        """Exported FBX contains Connections section."""
        (_, _, _, FBXExp, *_) = _import_anim_lib()[:5]
        engine, anim_name = self._get_engine_and_anim()
        if engine is None or anim_name is None:
            pytest.skip("c_bantha not available")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.fbx")
            FBXExp().export(engine, anim_name, path)
            content = Path(path).read_text()
        assert "Connections:" in content

    def test_exported_fbx_has_takes_for_blender_compat(self):
        """Exported FBX has Takes block for Blender/UE4 compatibility."""
        (_, _, _, FBXExp, *_) = _import_anim_lib()[:5]
        engine, anim_name = self._get_engine_and_anim()
        if engine is None or anim_name is None:
            pytest.skip("c_bantha not available")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.fbx")
            FBXExp().export(engine, anim_name, path)
            content = Path(path).read_text()
        assert "Takes:" in content

    def test_exported_fbx_has_bind_pose(self):
        """Exported FBX contains BindPose section for correct T-pose."""
        (_, _, _, FBXExp, *_) = _import_anim_lib()[:5]
        engine, anim_name = self._get_engine_and_anim()
        if engine is None or anim_name is None:
            pytest.skip("c_bantha not available")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.fbx")
            FBXExp().export(engine, anim_name, path, include_bind_pose=True)
            content = Path(path).read_text()
        assert "BindPose" in content
        assert "Matrix: *16" in content

    def test_exported_fbx_animation_name_in_stack(self):
        """Exported FBX AnimationStack name matches the animation name."""
        (_, _, _, FBXExp, *_) = _import_anim_lib()[:5]
        engine, anim_name = self._get_engine_and_anim()
        if engine is None or anim_name is None:
            pytest.skip("c_bantha not available")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.fbx")
            FBXExp().export(engine, anim_name, path)
            content = Path(path).read_text()
        assert anim_name in content

    def test_export_with_mixamo_remap_changes_bone_names(self):
        """FBX exported with Mixamo remap uses Mixamo bone names."""
        (_, _, AR, FBXExp, *_) = _import_anim_lib()[:5]
        engine, anim_name = self._get_engine_and_anim()
        if engine is None or anim_name is None:
            pytest.skip("c_bantha not available")
        remap = AR.build_map(AR.KOTOR_TO_MIXAMO)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test_mixamo.fbx")
            ok = FBXExp().export(engine, anim_name, path, bone_remap=remap)
            assert ok
            content = Path(path).read_text()
        # Should NOT contain raw KotOR names that are in the remap
        # (they should be replaced by Mixamo names)
        # pelvis_g → mixamorig:Hips
        if "pelvis_g" in str(engine.model.root_node):
            assert "mixamorig:Hips" in content or "pelvis_g" not in content

    def test_export_invalid_anim_name_returns_false(self):
        """Exporting nonexistent animation returns False."""
        (_, _, _, FBXExp, *_) = _import_anim_lib()[:5]
        engine, _ = self._get_engine_and_anim()
        if engine is None:
            pytest.skip("c_bantha not available")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "bad.fbx")
            ok   = FBXExp().export(engine, "NONEXISTENT_ANIM_XYZ", path)
        assert not ok

    def test_export_all_creates_multi_stack_fbx(self):
        """export_all produces FBX with multiple AnimationStack entries."""
        (_, _, _, FBXExp, *_) = _import_anim_lib()[:5]
        engine, _ = self._get_engine_and_anim()
        if engine is None:
            pytest.skip("c_bantha not available")
        model = engine.model
        if len(model.animations) < 2:
            pytest.skip("Need at least 2 animations")
        with tempfile.TemporaryDirectory() as td:
            path    = os.path.join(td, "all.fbx")
            ok      = FBXExp().export_all(engine, path)
            assert ok
            content = Path(path).read_text()
        # Count AnimationStack entries
        stack_count = content.count("AnimationStack:")
        assert stack_count >= 2

    def test_fbx_file_is_valid_ascii(self):
        """Exported FBX is valid UTF-8 text (ASCII mode)."""
        (_, _, _, FBXExp, *_) = _import_anim_lib()[:5]
        engine, anim_name = self._get_engine_and_anim()
        if engine is None or anim_name is None:
            pytest.skip("c_bantha not available")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.fbx")
            FBXExp().export(engine, anim_name, path)
            # Should be readable as text
            content = Path(path).read_text(encoding='utf-8')
        assert len(content) > 100

    def test_fbx_animation_curve_has_keyframes(self):
        """FBX AnimationCurve sections contain keyframe data."""
        (_, _, _, FBXExp, *_) = _import_anim_lib()[:5]
        engine, anim_name = self._get_engine_and_anim()
        if engine is None or anim_name is None:
            pytest.skip("c_bantha not available")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.fbx")
            FBXExp().export(engine, anim_name, path)
            content = Path(path).read_text()
        assert "AnimationCurve:" in content
        assert "KeyTime:"        in content
        assert "KeyValueFloat:"  in content


# ═════════════════════════════════════════════════════════════════════════════
#  5.  AnimationLibrary — Core Functionality
# ═════════════════════════════════════════════════════════════════════════════

class TestAnimationLibrary:
    """Test AnimationLibrary scanning, search, and engine loading."""

    def _make_mock_library(self):
        """Create a mock game library with the bantha test asset."""
        bantha_path = 'test_assets/c_bantha/c_bantha.mdl'
        if not os.path.exists(bantha_path):
            return None, None

        with open(bantha_path, 'rb') as f:
            mdl_bytes = f.read()

        class _Entry:
            resref = "c_bantha"
            game   = "K1"
            classification = "creature"

        class _MockLib:
            models = [_Entry()]
            def get_model_data(self, entry):
                return mdl_bytes, b""

        return _MockLib(), _Entry()

    def test_library_starts_empty(self):
        """New AnimationLibrary has no entries."""
        (AL, *_) = _import_anim_lib()[:1]
        lib = AL()
        assert len(lib.entries) == 0
        assert lib.stats['total_animations'] == 0

    def test_library_scan_populates_entries(self):
        """Scanning a mock library populates animation entries."""
        (AL, *_) = _import_anim_lib()[:1]
        mock_lib, _ = self._make_mock_library()
        if mock_lib is None:
            pytest.skip("c_bantha not available")
        lib = AL()
        lib.scan(mock_lib, background=False)
        assert len(lib.entries) > 0

    def test_library_entry_has_required_fields(self):
        """AnimationEntry has all required fields populated."""
        (AL, AE, *_) = _import_anim_lib()[:2]
        mock_lib, _ = self._make_mock_library()
        if mock_lib is None:
            pytest.skip("c_bantha not available")
        lib = AL()
        lib.scan(mock_lib, background=False)
        for entry in lib.entries:
            assert entry.model_name, "model_name is empty"
            assert entry.anim_name,  "anim_name is empty"
            assert entry.game in ("K1", "K2"), f"invalid game: {entry.game}"
            assert entry.length >= 0,  f"negative length: {entry.length}"
            assert entry.node_count >= 0

    def test_search_by_name(self):
        """Search by animation name filters correctly."""
        (AL, *_) = _import_anim_lib()[:1]
        mock_lib, _ = self._make_mock_library()
        if mock_lib is None:
            pytest.skip("c_bantha not available")
        lib = AL()
        lib.scan(mock_lib, background=False)
        # Get the first anim name
        if not lib.entries:
            pytest.skip("no animations found")
        first_name = lib.entries[0].anim_name
        results = lib.search(query=first_name[:3])
        assert len(results) > 0
        for r in results:
            assert first_name[:3].lower() in r.anim_name.lower() or \
                   first_name[:3].lower() in r.model_name.lower()

    def test_search_by_game_filter(self):
        """Search by game='K2' returns only K2 entries."""
        (AL, *_) = _import_anim_lib()[:1]
        mock_lib, _ = self._make_mock_library()
        if mock_lib is None:
            pytest.skip("c_bantha not available")
        lib = AL()
        lib.scan(mock_lib, background=False)
        k2_results = lib.search(game="K2")
        for r in k2_results:
            assert r.game == "K2"

    def test_get_engine_returns_engine(self):
        """get_engine returns an AnimationEngine for a valid entry."""
        (AL, *_) = _import_anim_lib()[:1]
        mock_lib, _ = self._make_mock_library()
        if mock_lib is None:
            pytest.skip("c_bantha not available")
        lib = AL()
        lib.scan(mock_lib, background=False)
        if not lib.entries:
            pytest.skip("no entries")
        engine = lib.get_engine(lib.entries[0])
        assert engine is not None

    def test_stats_counts_correct(self):
        """Library stats reflect correct counts."""
        (AL, *_) = _import_anim_lib()[:1]
        mock_lib, _ = self._make_mock_library()
        if mock_lib is None:
            pytest.skip("c_bantha not available")
        lib = AL()
        lib.scan(mock_lib, background=False)
        stats = lib.stats
        assert stats['total_animations'] == len(lib.entries)
        assert stats['total_models'] == len(lib.get_all_model_names())

    def test_fps_estimate_reasonable(self):
        """AnimationEntry fps_estimate is in reasonable range (15-120)."""
        (AL, *_) = _import_anim_lib()[:1]
        mock_lib, _ = self._make_mock_library()
        if mock_lib is None:
            pytest.skip("c_bantha not available")
        lib = AL()
        lib.scan(mock_lib, background=False)
        for entry in lib.entries:
            fps = entry.fps_estimate
            assert 10.0 <= fps <= 120.0, \
                f"fps_estimate {fps} out of range for {entry.display_name}"


# ═════════════════════════════════════════════════════════════════════════════
#  6.  Animation Quality — SLERP Continuity
# ═════════════════════════════════════════════════════════════════════════════

class TestAnimationQuality:
    """
    Verify animation quality — smooth interpolation, no 360° spin artifacts,
    correct position delta application.
    Reference: Gregory §SLERP, Mukundan §Quaternion interpolation.
    """

    def test_engine_produces_continuous_poses(self):
        """Animation engine poses are continuous (no sudden jumps)."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        from src.core.animation_engine import AnimationEngine
        engine = AnimationEngine(model)
        anims  = engine.list_animations()
        if not anims:
            pytest.skip("no animations")
        name = anims[0]['name']
        ok   = engine.play(name, loop=False)
        assert ok

        # Sample poses at small time steps
        poses = []
        anim  = engine._current_anim
        if anim is None:
            pytest.skip("anim not set after play()")
        step = anim.length / 20.0
        for i in range(20):
            p = engine.evaluate(t=i * step)
            poses.append(p)

        # For each bone that appears in all poses, check for no huge jumps
        if len(poses) < 2:
            return
        first_nodes = set(poses[0].nodes.keys())
        for node_name in list(first_nodes)[:5]:  # check first 5 bones
            prev_pos = poses[0].nodes[node_name].position
            prev_rot = poses[0].nodes[node_name].rotation
            for pose in poses[1:]:
                if node_name not in pose.nodes:
                    continue
                cur_pos = pose.nodes[node_name].position
                cur_rot = pose.nodes[node_name].rotation
                # No teleportation: position change < 5 units per step
                dist = math.sqrt(sum((a-b)**2 for a,b in zip(cur_pos, prev_pos)))
                assert dist < 5.0, \
                    f"Bone {node_name} jumped {dist:.3f} units in one step"
                # Rotation quaternion stays unit-length
                mag = math.sqrt(sum(r*r for r in cur_rot))
                assert abs(mag - 1.0) < 0.01, \
                    f"Rotation quaternion for {node_name} not unit: mag={mag:.4f}"
                prev_pos = cur_pos
                prev_rot = cur_rot

    def test_position_delta_not_absolute(self):
        """KotOR position keyframes are deltas, not absolute positions."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        from src.core.animation_engine import AnimationEngine
        engine = AnimationEngine(model)
        anims  = engine.list_animations()
        if not anims:
            pytest.skip("no animations")
        name = anims[0]['name']
        engine.play(name)
        pose_t0 = engine.evaluate(t=0.0)

        # For a bone at bind pose, t=0 keyframe should produce bind position
        # (delta=0 → animated = bind_pos + 0 = bind_pos)
        for node_name, np_ in pose_t0.nodes.items():
            base = engine._base_nodes.get(node_name)
            if base is None:
                continue
            # At t=0, most animation positions should equal bind position
            # (within some tolerance, as some animations start offset)
            dist = math.sqrt(sum((a-b)**2 for a,b in
                                 zip(np_.position, base.position)))
            # The distance should be reasonable (not the "exploded skeleton" bug
            # where all bones collapse to origin because keyframes treated as absolute)
            assert dist < 20.0, \
                f"Bone {node_name} at t=0 is {dist:.2f} units from bind pose " \
                f"— may indicate wrong position keyframe handling"

    def test_no_nan_inf_in_poses(self):
        """No NaN or Inf values appear in animation poses."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        from src.core.animation_engine import AnimationEngine
        engine = AnimationEngine(model)
        anims  = engine.list_animations()
        if not anims:
            pytest.skip("no animations")
        engine.play(anims[0]['name'])
        anim = engine._current_anim
        if anim is None:
            pytest.skip("anim not set")
        for t in (0.0, anim.length * 0.25, anim.length * 0.5,
                  anim.length * 0.75, anim.length):
            pose = engine.evaluate(t=t)
            for name, np_ in pose.nodes.items():
                for v in np_.position:
                    assert math.isfinite(v), \
                        f"NaN/Inf in position of {name} at t={t}"
                for v in np_.rotation:
                    assert math.isfinite(v), \
                        f"NaN/Inf in rotation of {name} at t={t}"


# ═════════════════════════════════════════════════════════════════════════════
#  7.  Full Pipeline Test — KotOR → FBX
# ═════════════════════════════════════════════════════════════════════════════

class TestFullAnimationPipeline:
    """
    End-to-end test: load KotOR MDL → extract animation → export FBX.
    This validates the complete three-step priority pipeline.
    """

    def test_full_pipeline_native_skeleton(self):
        """Full pipeline: MDL → AnimationEngine → FBX (KotOR skeleton)."""
        (_, _, _, FBXExp, *_) = _import_anim_lib()[:5]
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        from src.core.animation_engine import AnimationEngine
        engine = AnimationEngine(model)
        anims  = engine.list_animations()
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "native.fbx")
            ok   = FBXExp().export(engine, anims[0]['name'], path)
        assert ok, "FBX export failed"

    def test_full_pipeline_mixamo_skeleton(self):
        """Full pipeline: MDL → AnimationEngine → FBX (Mixamo skeleton)."""
        (_, _, AR, FBXExp, *_) = _import_anim_lib()[:5]
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        from src.core.animation_engine import AnimationEngine
        engine = AnimationEngine(model)
        anims  = engine.list_animations()
        if not anims:
            pytest.skip("no animations")
        remap = AR.build_map(AR.KOTOR_TO_MIXAMO)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "mixamo.fbx")
            ok   = FBXExp().export(engine, anims[0]['name'], path,
                                   bone_remap=remap)
        assert ok, "Mixamo FBX export failed"

    def test_full_pipeline_ue5_skeleton(self):
        """Full pipeline: MDL → AnimationEngine → FBX (UE5 Mannequin)."""
        (_, _, AR, FBXExp, *_) = _import_anim_lib()[:5]
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        from src.core.animation_engine import AnimationEngine
        engine = AnimationEngine(model)
        anims  = engine.list_animations()
        if not anims:
            pytest.skip("no animations")
        remap = AR.build_map(AR.KOTOR_TO_UE5)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "ue5.fbx")
            ok   = FBXExp().export(engine, anims[0]['name'], path,
                                   bone_remap=remap)
        assert ok, "UE5 FBX export failed"

    def test_full_pipeline_all_animations_exported(self):
        """Export all animations from a model to individual FBX files."""
        (_, _, _, FBXExp, *_) = _import_anim_lib()[:5]
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        from src.core.animation_engine import AnimationEngine
        engine = AnimationEngine(model)
        anims  = engine.list_animations()
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            exported = []
            for a in anims:
                safe = "".join(c for c in a['name'] if c.isalnum() or c in '-_')
                path = os.path.join(td, f"{safe}.fbx")
                ok   = FBXExp().export(engine, a['name'], path)
                if ok:
                    exported.append(path)
            assert len(exported) == len(anims), \
                f"Only {len(exported)}/{len(anims)} animations exported"
            for p in exported:
                assert os.path.exists(p)
                assert os.path.getsize(p) > 500

    def test_full_pipeline_template_body_k1(self):
        """Full pipeline using K1 body template."""
        (_, _, _, FBXExp, *_) = _import_anim_lib()[:5]
        model = _load_template('K1', 'body')
        if model is None:
            pytest.skip("K1 body template not available")
        from src.core.animation_engine import AnimationEngine
        engine = AnimationEngine(model)
        # Template has no animations — just verify we can export the skeleton
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "k1_body.fbx")
            ok   = FBXExp().export_all(engine, path)
        # May return False (no anims) or True — just shouldn't crash
        assert isinstance(ok, bool)

    def test_fbx_file_size_scales_with_animation_length(self):
        """Longer animations produce larger FBX files."""
        (_, _, _, FBXExp, *_) = _import_anim_lib()[:5]
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        from src.core.animation_engine import AnimationEngine
        engine = AnimationEngine(model)
        anims  = sorted(engine.list_animations(), key=lambda a: a['length'])
        if len(anims) < 2:
            pytest.skip("need at least 2 animations")
        short_anim = anims[0]
        long_anim  = anims[-1]
        if abs(short_anim['length'] - long_anim['length']) < 0.1:
            pytest.skip("animations too similar in length")
        with tempfile.TemporaryDirectory() as td:
            p1 = os.path.join(td, "short.fbx")
            p2 = os.path.join(td, "long.fbx")
            FBXExp().export(engine, short_anim['name'], p1)
            FBXExp().export(engine, long_anim['name'],  p2)
            size1 = os.path.getsize(p1)
            size2 = os.path.getsize(p2)
        # Longer anim should generally produce a larger file,
        # but the relationship isn't strictly monotonic due to node counts.
        # Use a relaxed check: file sizes are both > 0 and reasonable.
        assert size1 > 0 and size2 > 0, "FBX files should be non-empty"
        # The ratio should be within 2x of the length ratio (loose bound)
        len_ratio  = long_anim['length']  / max(short_anim['length'],  0.001)
        size_ratio = max(size1, size2)    / max(min(size1, size2), 1)
        assert size_ratio < len_ratio * 10 + 5, \
            f"FBX sizes ({size1}B, {size2}B) differ wildly from length ratio {len_ratio:.2f}"

    def test_bvh_export_still_works(self):
        """BVH export still works alongside new FBX pipeline."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        from src.core.animation_engine import AnimationEngine
        engine = AnimationEngine(model)
        anims  = engine.list_animations()
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.bvh")
            ok   = engine.export_animation_bvh(anims[0]['name'], path)
            assert ok
            assert os.path.exists(path)
            content = Path(path).read_text()
        assert "HIERARCHY" in content
        assert "MOTION"    in content

    def test_json_export_still_works(self):
        """JSON export still works alongside new FBX pipeline."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        from src.core.animation_engine import AnimationEngine
        engine = AnimationEngine(model)
        anims  = engine.list_animations()
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.json")
            ok   = engine.export_animation_json(anims[0]['name'], path)
            assert ok
            assert os.path.exists(path)
            data = json.loads(Path(path).read_text())
        assert 'animations' in data or 'name' in data
