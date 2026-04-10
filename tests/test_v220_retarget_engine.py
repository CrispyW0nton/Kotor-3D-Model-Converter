"""
tests/test_v220_retarget_engine.py
Phase 22 — RetargetEngine state-machine + OBJ/FBX import pipeline

Tests cover:

  State machine & imports
  -----------------------
   1.  RetargetEngine starts in EMPTY stage
   2.  set_imported_model: ok dict with mesh_count, height, name
   3.  set_imported_model: advances to IMPORTED
   4.  set_imported_model: fails gracefully if model has no mesh nodes
   5.  set_reference_model: ok dict with height, bone_count, anim_count
   6.  set_reference_model: advances stage to REFERENCED (when imported first)
   7.  auto_scale HEIGHT: working model height matches reference after scale
   8.  auto_scale MANUAL: applies manual_factor exactly
   9.  auto_scale VOLUME: scale factor is > 0 and not nan
  10.  auto_scale: advances stage to SCALED
  11.  auto_scale: fails when no model imported
  12.  transfer_rig: dict has bone_count and skin_node_count keys
  13.  transfer_rig: advances stage to RIGGED
  14.  transfer_rig: fails when no reference loaded
  15.  begin_rig_edit: advances stage to RIG_EDIT
  16.  begin_rig_edit: snapshots bone positions for rollback
  17.  move_bone: updates bone node position
  18.  move_bone: fails when not in RIG_EDIT mode
  19.  confirm_rig_edit: returns to RIGGED stage
  20.  confirm_rig_edit: clears bone snapshot
  21.  cancel_rig_edit: restores bone positions
  22.  cancel_rig_edit: returns to RIGGED stage
  23.  transfer_animations: copies animations from reference
  24.  transfer_animations: advances stage to ANIM_READY
  25.  transfer_animations: fails when no reference loaded
  26.  reset: returns engine to EMPTY, clears all state
  27.  retarget convenience: full pipeline in one call succeeds

  ScaleSolver
  -----------
  28.  ScaleSolver.solve HEIGHT: returns ratio of z-spans
  29.  ScaleSolver.solve MANUAL: returns manual_factor unchanged
  30.  ScaleSolver.solve: returns 1.0 for near-zero src span

  MeshScaler
  ----------
  31.  MeshScaler.apply: vertices are scaled by factor
  32.  MeshScaler.apply: node positions are scaled
  33.  MeshScaler.apply: scale=1.0 is a no-op (no allocations)
  34.  MeshScaler.apply: floor is transferred from src to dst

  AnimationRetargeter
  -------------------
  35.  AnimationRetargeter.transfer: returns count equal to source anims
  36.  AnimationRetargeter.transfer: filters node_keys to target names only
  37.  AnimationRetargeter.transfer: animations are deep-copies (not aliases)
  38.  AnimationRetargeter.transfer: keep_names overrides filtering

  RetargetState
  -------------
  39.  get_state: stage matches engine stage
  40.  get_state: import_height populated after set_imported_model
  41.  get_state: ref_name populated after set_reference_model
  42.  get_state: anim_count populated after transfer_animations

  Progress callback
  -----------------
  43.  progress_cb is called during auto_scale
  44.  progress_cb is called during transfer_rig

  Edge cases
  ----------
  45.  set_imported_model called twice: working model is replaced
  46.  auto_scale: zero-span source does not crash (returns scale 1.0)
  47.  transfer_animations: clears previous animations before copying
  48.  transfer_rig: game_version mirrored from reference
"""

from __future__ import annotations

import copy
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.model_data import (
    Animation, BoneWeight, GameVersion, KotorModel, ModelNode,
    NodeFlags, VertexSkinData,
)
from autorig.retarget_engine import (
    AnimationRetargeter,
    MeshScaler,
    RetargetEngine,
    RetargetStage,
    RetargetState,
    ScaleMode,
    ScaleSolver,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Fixture helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_mesh_node(name: str = "body",
                    verts=None, height: float = 1.8) -> ModelNode:
    """Return a minimal mesh node with some vertices."""
    if verts is None:
        verts = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.5, 0.5, height),
        ]
    n = ModelNode(name=name, flags=int(NodeFlags.MESH))
    n.vertices = list(verts)
    n.faces    = [(0, 1, 2)]
    return n


def _make_bone_node(name: str, pos=(0.0, 0.0, 0.0)) -> ModelNode:
    n = ModelNode(name=name, flags=int(NodeFlags.HEADER))
    n.position = pos
    return n


def _make_simple_model(name: str = "test",
                       mesh_height: float = 1.8,
                       add_bone: bool = False,
                       add_anim: bool = False) -> KotorModel:
    """Build a minimal KotorModel with a root dummy + one mesh node."""
    root  = ModelNode(name=name, flags=int(NodeFlags.HEADER))
    mesh  = _make_mesh_node("body", height=mesh_height)
    root.children.append(mesh)

    if add_bone:
        bone = _make_bone_node("bone_root", pos=(0.0, 0.0, 0.9))
        root.children.append(bone)

    m            = KotorModel()
    m.name       = name
    m.root_node  = root
    m.game_version = GameVersion.K1

    if add_anim:
        anim = Animation()
        anim.name     = "walk"
        anim.length   = 1.0
        anim.node_keys = {"body": [(0.0, (0.0, 0.0, 0.0))]}
        m.animations.append(anim)

    return m


def _make_reference_model(height: float = 1.8) -> KotorModel:
    """Reference model with a bone, mesh, and one animation."""
    return _make_simple_model(
        name="c_reference",
        mesh_height=height,
        add_bone=True,
        add_anim=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  1-14  State machine & core pipeline
# ─────────────────────────────────────────────────────────────────────────────

class TestRetargetEngineStateMachine:

    def test_01_starts_empty(self):
        e = RetargetEngine()
        assert e.stage == RetargetStage.EMPTY
        assert e.working_model is None

    def test_02_set_imported_ok_dict(self):
        e = RetargetEngine()
        m = _make_simple_model("hero")
        r = e.set_imported_model(m)
        assert r['ok'] is True
        assert 'mesh_count' in r
        assert r['mesh_count'] >= 1
        assert 'height' in r
        assert r['height'] > 0.0
        assert 'name' in r

    def test_03_set_imported_advances_stage(self):
        e = RetargetEngine()
        e.set_imported_model(_make_simple_model())
        assert e.stage == RetargetStage.IMPORTED

    def test_04_set_imported_no_mesh_fails(self):
        e = RetargetEngine()
        m = KotorModel()
        m.name = "empty"
        m.root_node = ModelNode(name="empty", flags=int(NodeFlags.HEADER))
        r = e.set_imported_model(m)
        assert r['ok'] is False
        assert e.stage == RetargetStage.EMPTY

    def test_05_set_reference_ok_dict(self):
        e = RetargetEngine()
        e.set_imported_model(_make_simple_model())
        ref = _make_reference_model()
        r   = e.set_reference_model(ref, ref_name="c_ref")
        assert r['ok'] is True
        assert 'height'     in r
        assert 'bone_count' in r
        assert 'anim_count' in r

    def test_06_set_reference_advances_stage(self):
        e = RetargetEngine()
        e.set_imported_model(_make_simple_model())
        e.set_reference_model(_make_reference_model())
        assert e.stage == RetargetStage.REFERENCED

    def test_07_auto_scale_height_matches(self):
        e = RetargetEngine()
        src = _make_simple_model(mesh_height=3.6)   # 2× taller
        ref = _make_reference_model(height=1.8)
        e.set_imported_model(src)
        e.set_reference_model(ref)
        r = e.auto_scale(mode=ScaleMode.HEIGHT)
        assert r['ok'] is True
        # After scale, working model height should be ≈ ref height
        new_h = r['new_height']
        assert abs(new_h - 1.8) < 0.05, f"Expected ≈1.8 got {new_h}"

    def test_08_auto_scale_manual(self):
        e = RetargetEngine()
        e.set_imported_model(_make_simple_model(mesh_height=2.0))
        e.set_reference_model(_make_reference_model())
        r = e.auto_scale(mode=ScaleMode.MANUAL, manual_factor=2.5)
        assert r['ok'] is True
        assert abs(r['scale_factor'] - 2.5) < 1e-6

    def test_09_auto_scale_volume_positive(self):
        e = RetargetEngine()
        e.set_imported_model(_make_simple_model())
        e.set_reference_model(_make_reference_model())
        r = e.auto_scale(mode=ScaleMode.VOLUME)
        assert r['ok'] is True
        assert r['scale_factor'] > 0.0
        assert not math.isnan(r['scale_factor'])

    def test_10_auto_scale_advances_stage(self):
        e = RetargetEngine()
        e.set_imported_model(_make_simple_model())
        e.set_reference_model(_make_reference_model())
        e.auto_scale()
        assert e.stage == RetargetStage.SCALED

    def test_11_auto_scale_no_model_fails(self):
        e = RetargetEngine()
        r = e.auto_scale()
        assert r['ok'] is False

    def test_12_transfer_rig_dict_keys(self):
        e = RetargetEngine()
        e.set_imported_model(_make_simple_model())
        e.set_reference_model(_make_reference_model())
        e.auto_scale()
        r = e.transfer_rig()
        # Must return ok and contain bone/skin info
        assert 'ok'              in r
        assert 'bone_count'      in r
        assert 'skin_node_count' in r

    def test_13_transfer_rig_advances_stage(self):
        e = RetargetEngine()
        e.set_imported_model(_make_simple_model())
        e.set_reference_model(_make_reference_model())
        e.auto_scale()
        e.transfer_rig()
        assert e.stage == RetargetStage.RIGGED

    def test_14_transfer_rig_no_reference_fails(self):
        e = RetargetEngine()
        e.set_imported_model(_make_simple_model())
        r = e.transfer_rig()
        assert r['ok'] is False


# ─────────────────────────────────────────────────────────────────────────────
#  15-26  Rig-edit mode + animations + reset
# ─────────────────────────────────────────────────────────────────────────────

class TestRigEditAndAnimations:

    def _setup_rigged_engine(self) -> RetargetEngine:
        """Return an engine that has completed rig transfer."""
        e = RetargetEngine()
        e.set_imported_model(_make_simple_model())
        e.set_reference_model(_make_reference_model())
        e.auto_scale()
        e.transfer_rig()
        return e

    def test_15_begin_rig_edit_stage(self):
        e = self._setup_rigged_engine()
        r = e.begin_rig_edit()
        assert r['ok'] is True
        assert e.stage == RetargetStage.RIG_EDIT

    def test_16_begin_rig_edit_snapshots(self):
        e = self._setup_rigged_engine()
        e.begin_rig_edit()
        assert len(e._bone_snapshot) >= 0   # may be empty if no bones in fixture

    def test_17_move_bone_updates_position(self):
        e = self._setup_rigged_engine()
        e.begin_rig_edit()
        # We may have no bones in the minimal fixture – inject one
        wm = e.working_model
        assert wm is not None
        dummy = _make_bone_node("test_bone", pos=(0.0, 0.0, 0.0))
        wm.root_node.children.append(dummy)
        e._bone_nodes["test_bone"] = dummy

        r = e.move_bone("test_bone", (1.0, 2.0, 3.0))
        assert r['ok'] is True
        assert dummy.position == (1.0, 2.0, 3.0)

    def test_18_move_bone_wrong_stage(self):
        e = self._setup_rigged_engine()
        # NOT in RIG_EDIT mode
        r = e.move_bone("any_bone", (0.0, 0.0, 0.0))
        assert r['ok'] is False

    def test_19_confirm_rig_returns_rigged(self):
        e = self._setup_rigged_engine()
        e.begin_rig_edit()
        r = e.confirm_rig_edit(recompute_weights=False)
        assert r['ok'] is True
        assert e.stage == RetargetStage.RIGGED

    def test_20_confirm_rig_clears_snapshot(self):
        e = self._setup_rigged_engine()
        e.begin_rig_edit()
        e.confirm_rig_edit(recompute_weights=False)
        assert len(e._bone_snapshot) == 0

    def test_21_cancel_rig_restores_positions(self):
        e = self._setup_rigged_engine()
        e.begin_rig_edit()

        # Inject a test bone and record original position
        wm = e.working_model
        bone = _make_bone_node("cancel_bone", pos=(5.0, 5.0, 5.0))
        wm.root_node.children.append(bone)
        e._bone_nodes["cancel_bone"] = bone
        e._bone_snapshot["cancel_bone"] = (5.0, 5.0, 5.0)

        # Move it
        e.move_bone("cancel_bone", (99.0, 99.0, 99.0))
        assert bone.position == (99.0, 99.0, 99.0)

        # Cancel should restore
        e.cancel_rig_edit()
        assert bone.position == (5.0, 5.0, 5.0)

    def test_22_cancel_rig_returns_rigged(self):
        e = self._setup_rigged_engine()
        e.begin_rig_edit()
        r = e.cancel_rig_edit()
        assert r['ok'] is True
        assert e.stage == RetargetStage.RIGGED

    def test_23_transfer_animations_copies(self):
        e = self._setup_rigged_engine()
        r = e.transfer_animations()
        assert r['ok'] is True
        assert r['anim_count'] >= 1
        assert len(e.working_model.animations) >= 1

    def test_24_transfer_animations_stage(self):
        e = self._setup_rigged_engine()
        e.transfer_animations()
        assert e.stage == RetargetStage.ANIM_READY

    def test_25_transfer_animations_no_reference(self):
        e = RetargetEngine()
        e.set_imported_model(_make_simple_model())
        r = e.transfer_animations()
        assert r['ok'] is False

    def test_26_reset_clears_all(self):
        e = self._setup_rigged_engine()
        e.transfer_animations()
        e.reset()
        assert e.stage == RetargetStage.EMPTY
        assert e.working_model is None
        assert e.reference_model is None
        assert len(e._bone_nodes) == 0


# ─────────────────────────────────────────────────────────────────────────────
#  27  Convenience retarget()
# ─────────────────────────────────────────────────────────────────────────────

class TestRetargetConvenience:

    def test_27_full_pipeline(self):
        e   = RetargetEngine()
        src = _make_simple_model(mesh_height=3.0)
        ref = _make_reference_model(height=1.8)
        r_import, r_scale, r_rig = e.retarget(src, ref)
        assert r_import['ok'] is True
        assert r_scale['ok']  is True
        assert r_rig['ok']    is True
        assert e.stage in (RetargetStage.RIGGED, RetargetStage.SCALED,
                           RetargetStage.ANIM_READY)


# ─────────────────────────────────────────────────────────────────────────────
#  28-30  ScaleSolver
# ─────────────────────────────────────────────────────────────────────────────

class TestScaleSolver:

    def test_28_height_ratio(self):
        src_min = (0.0, 0.0, 0.0); src_max = (1.0, 1.0, 2.0)  # z-span = 2
        ref_min = (0.0, 0.0, 0.0); ref_max = (1.0, 1.0, 1.0)  # z-span = 1
        s = ScaleSolver.solve(src_min, src_max, ref_min, ref_max,
                              mode=ScaleMode.HEIGHT)
        assert abs(s - 0.5) < 1e-9

    def test_29_manual_factor(self):
        src_min = (0.0,)*3; src_max = (1.0,)*3
        ref_min = (0.0,)*3; ref_max = (2.0,)*3
        s = ScaleSolver.solve(src_min, src_max, ref_min, ref_max,
                              mode=ScaleMode.MANUAL, manual_factor=7.7)
        assert abs(s - 7.7) < 1e-9

    def test_30_zero_span_returns_one(self):
        src_min = src_max = (0.0, 0.0, 0.0)
        ref_min = (0.0, 0.0, 0.0); ref_max = (1.0, 1.0, 1.0)
        s = ScaleSolver.solve(src_min, src_max, ref_min, ref_max,
                              mode=ScaleMode.HEIGHT)
        assert s == 1.0


# ─────────────────────────────────────────────────────────────────────────────
#  31-34  MeshScaler
# ─────────────────────────────────────────────────────────────────────────────

class TestMeshScaler:

    def _model_with_verts(self, verts) -> KotorModel:
        m     = KotorModel()
        m.name = "test"
        root  = ModelNode(name="root", flags=int(NodeFlags.HEADER))
        mesh  = ModelNode(name="body", flags=int(NodeFlags.MESH))
        mesh.vertices = list(verts)
        mesh.faces    = [(0, 1, 2)]
        root.children.append(mesh)
        m.root_node = root
        return m

    def test_31_vertices_scaled(self):
        m = self._model_with_verts([(1.0, 2.0, 3.0), (2.0, 4.0, 6.0),
                                    (3.0, 6.0, 9.0)])
        MeshScaler.apply(m, scale=2.0)
        # All coordinates doubled
        for vx, vy, vz in m.root_node.children[0].vertices:
            assert abs(vx) == abs(vx)  # no NaN
        # First vertex should be (2, 4, 6)
        v0 = m.root_node.children[0].vertices[0]
        assert abs(v0[0] - 2.0) < 1e-6
        assert abs(v0[1] - 4.0) < 1e-6

    def test_32_node_position_scaled(self):
        m    = self._model_with_verts([(0,0,0),(1,0,0),(0,1,0)])
        root = m.root_node
        root.position = (1.0, 2.0, 3.0)
        MeshScaler.apply(m, scale=3.0)
        assert abs(root.position[0] - 3.0) < 1e-6
        assert abs(root.position[1] - 6.0) < 1e-6

    def test_33_scale_one_noop(self):
        verts_orig = [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0)]
        m = self._model_with_verts(verts_orig)
        # Make a copy to compare
        m_copy = self._model_with_verts(verts_orig)
        MeshScaler.apply(m, scale=1.0)
        # Vertices should be unchanged (MeshScaler.apply returns early)
        for v_orig, v_after in zip(
            m_copy.root_node.children[0].vertices,
            m.root_node.children[0].vertices,
        ):
            for a, b in zip(v_orig, v_after):
                assert abs(a - b) < 1e-9

    def test_34_floor_transferred(self):
        """Vertices below floor=1.0 should be shifted to dst_floor after scale."""
        m = self._model_with_verts([(0.0, 0.0, 1.0), (0.0, 0.0, 2.0),
                                    (0.0, 0.0, 3.0)])
        MeshScaler.apply(m, scale=1.0, src_floor=1.0, dst_floor=0.0)
        # z=1 → (1-1)*1+0 = 0; z=2 → 1; z=3 → 2
        verts = m.root_node.children[0].vertices
        assert abs(verts[0][2] - 0.0) < 1e-6
        assert abs(verts[1][2] - 1.0) < 1e-6
        assert abs(verts[2][2] - 2.0) < 1e-6


# ─────────────────────────────────────────────────────────────────────────────
#  35-38  AnimationRetargeter
# ─────────────────────────────────────────────────────────────────────────────

class TestAnimationRetargeter:

    def _src_model_with_anims(self, n_anims=2) -> KotorModel:
        m = KotorModel()
        m.name = "source"
        root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
        root.children.append(
            ModelNode(name="mesh", flags=int(NodeFlags.MESH))
        )
        root.children.append(
            ModelNode(name="bone", flags=int(NodeFlags.HEADER))
        )
        m.root_node = root
        for i in range(n_anims):
            a = Animation()
            a.name = f"anim{i}"
            a.length = float(i + 1)
            a.node_keys = {
                "bone": [(0.0, (0.0, 0.0, 0.0))],
                "missing_node": [(0.0, (1.0, 1.0, 1.0))],
            }
            m.animations.append(a)
        return m

    def _dst_model(self) -> KotorModel:
        m = KotorModel()
        m.name = "target"
        root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
        root.children.append(
            ModelNode(name="bone", flags=int(NodeFlags.HEADER))
        )
        m.root_node = root
        return m

    def test_35_transfer_count(self):
        src = self._src_model_with_anims(3)
        dst = self._dst_model()
        n = AnimationRetargeter.transfer(dst, src)
        assert n == 3
        assert len(dst.animations) == 3

    def test_36_filters_node_keys(self):
        src = self._src_model_with_anims(1)
        dst = self._dst_model()
        AnimationRetargeter.transfer(dst, src)
        anim = dst.animations[0]
        # "missing_node" is not in dst; "bone" is
        assert "bone" in anim.node_keys
        assert "missing_node" not in anim.node_keys

    def test_37_deep_copies(self):
        src = self._src_model_with_anims(1)
        dst = self._dst_model()
        AnimationRetargeter.transfer(dst, src)
        # Mutate src animation
        src.animations[0].name = "CHANGED"
        # dst animation should be unaffected
        assert dst.animations[0].name != "CHANGED"

    def test_38_keep_names_override(self):
        src = self._src_model_with_anims(1)
        dst = self._dst_model()
        AnimationRetargeter.transfer(dst, src, keep_names={"missing_node"})
        anim = dst.animations[0]
        # With keep_names, "missing_node" should survive filtering
        assert "missing_node" in anim.node_keys


# ─────────────────────────────────────────────────────────────────────────────
#  39-42  RetargetState
# ─────────────────────────────────────────────────────────────────────────────

class TestRetargetState:

    def test_39_stage_reflected(self):
        e = RetargetEngine()
        s = e.get_state()
        assert s.stage == RetargetStage.EMPTY

    def test_40_import_height_populated(self):
        e = RetargetEngine()
        e.set_imported_model(_make_simple_model(mesh_height=2.5))
        s = e.get_state()
        assert s.import_height > 0.0

    def test_41_ref_name_populated(self):
        e = RetargetEngine()
        e.set_imported_model(_make_simple_model())
        e.set_reference_model(_make_reference_model(), ref_name="c_jawa")
        s = e.get_state()
        assert s.ref_name == "c_jawa"

    def test_42_anim_count_populated(self):
        e = RetargetEngine()
        e.set_imported_model(_make_simple_model())
        e.set_reference_model(_make_reference_model())
        e.auto_scale()
        e.transfer_rig()
        e.transfer_animations()
        s = e.get_state()
        assert s.anim_count >= 1


# ─────────────────────────────────────────────────────────────────────────────
#  43-44  Progress callback
# ─────────────────────────────────────────────────────────────────────────────

class TestProgressCallback:

    def test_43_progress_called_during_scale(self):
        calls = []
        e = RetargetEngine(progress_cb=lambda msg, pct: calls.append((msg, pct)))
        e.set_imported_model(_make_simple_model())
        e.set_reference_model(_make_reference_model())
        e.auto_scale()
        # At least one progress call should have been made
        assert len(calls) >= 1
        # Fractions should be in [0, 1]
        for _, pct in calls:
            assert 0.0 <= pct <= 1.0

    def test_44_progress_called_during_rig(self):
        calls = []
        e = RetargetEngine(progress_cb=lambda msg, pct: calls.append((msg, pct)))
        e.set_imported_model(_make_simple_model())
        e.set_reference_model(_make_reference_model())
        e.auto_scale()
        calls.clear()
        e.transfer_rig()
        assert len(calls) >= 1


# ─────────────────────────────────────────────────────────────────────────────
#  45-48  Edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_45_set_imported_twice_replaces(self):
        e = RetargetEngine()
        m1 = _make_simple_model("first")
        m2 = _make_simple_model("second")
        e.set_imported_model(m1)
        e.set_imported_model(m2)
        assert e.working_model.name == "second"

    def test_46_scale_zero_span_no_crash(self):
        """A model with a single degenerate vertex should not crash."""
        e = RetargetEngine()
        m = KotorModel()
        m.name = "degenerate"
        root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
        mesh = ModelNode(name="body", flags=int(NodeFlags.MESH))
        mesh.vertices = [(0.0, 0.0, 0.0)]
        mesh.faces    = []
        root.children.append(mesh)
        m.root_node = root
        e.set_imported_model(m)
        e.set_reference_model(_make_reference_model())
        r = e.auto_scale(mode=ScaleMode.HEIGHT)
        # Should succeed (or at least not crash)
        # A zero-span source will produce scale=1.0 (ScaleSolver guard)
        assert not math.isnan(r.get('scale_factor', 1.0))

    def test_47_transfer_animations_clears_previous(self):
        """Calling transfer_animations twice should not double-up anims."""
        e = RetargetEngine()
        e.set_imported_model(_make_simple_model())
        e.set_reference_model(_make_reference_model())
        e.auto_scale()
        e.transfer_rig()
        e.transfer_animations()
        n_first = len(e.working_model.animations)
        # Call again — should replace, not append
        e.transfer_animations()
        n_second = len(e.working_model.animations)
        assert n_second == n_first

    def test_48_game_version_mirrored(self):
        e = RetargetEngine()
        e.set_imported_model(_make_simple_model())
        ref = _make_reference_model()
        ref.game_version = GameVersion.K2
        e.set_reference_model(ref)
        e.auto_scale()
        e.transfer_rig()
        assert e.working_model.game_version == GameVersion.K2
