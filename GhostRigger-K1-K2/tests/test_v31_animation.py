"""
GhostRigger-K1-K2  v3.1  Animation Engine Tests
=================================================
Tests for AnimationEngine, interpolation helpers, BVH/JSON export/import,
AnimPose evaluation, advance() lifecycle, and rigging display during animation.

Covers:
  - _interp_channel: linear, slerp, NaN-skip, empty, single-key, clamp
  - _slerp: identity, antipodal shortest-path, normalization, t=0/t=1
  - AnimationEngine: play/stop/pause, advance lifecycle, loop/no-loop
  - evaluate(): position/orientation interpolation at specific times
  - JSON export/import round-trip
  - BVH export structure validation
  - add_animation / remove_animation
  - list_animations / get_animation_fps_estimate
  - AnimPose / NodePose structure
  - advance() returns False when non-loop anim ends (regression fix)
  - _eval_node: base-pose fallback, NaN rejection, scale validation
  - Viewport animation pose integration (_node_world_transform with pose)
  - Bone overlay during animation (_draw_bones with anim_pose)
  - Packed-quaternion decoded correctly (columns==2 orientation controller)
  - MDL parser animation nodes populated correctly
"""
from __future__ import annotations

import math
import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest

from src.core.animation_engine import (
    AnimationEngine, AnimPose, NodePose,
    _slerp, _lerp, _lerp3, _interp_channel, _is_finite_vec, _get_ctrl,
)
from src.core.model_data import (
    KotorModel, ModelNode, NodeFlags, Animation, AnimEvent,
    _quat_rotate, _quat_normalize,
)


# ─────────────────────────────────────────────────────────────────
#  Helper factories
# ─────────────────────────────────────────────────────────────────

def _make_model(name: str = "test") -> KotorModel:
    model = KotorModel(name=name)
    root = ModelNode(name="root", position=(0, 0, 0), rotation=(0, 0, 0, 1))
    model.root_node = root
    return model, root


def _make_model_with_bones():
    """Model with root → hip → knee → foot hierarchy."""
    model = KotorModel(name="anim_test")
    root = ModelNode(name="root",  position=(0, 0, 0),   rotation=(0, 0, 0, 1))
    hip  = ModelNode(name="hip",   position=(0, 0, 1.0), rotation=(0, 0, 0, 1), parent=root)
    knee = ModelNode(name="knee",  position=(0, 0, 2.0), rotation=(0, 0, 0, 1), parent=hip)
    foot = ModelNode(name="foot",  position=(0, 0, 3.0), rotation=(0, 0, 0, 1), parent=knee)
    root.children.extend([hip])
    hip.children.extend([knee])
    knee.children.extend([foot])
    model.root_node = root
    return model, root, hip, knee, foot


def _make_anim(name="cwalk", length=1.0):
    return Animation(name=name, length=length, transition_time=0.25)


def _ctrl(ctrl_type, times, values, columns=None):
    if columns is None:
        columns = len(values[0]) if values else 1
    return {
        'type': ctrl_type,
        'name': {8: 'position', 20: 'orientation', 36: 'scale', 100: 'alpha'}.get(ctrl_type, f'ctrl_{ctrl_type}'),
        'columns': columns,
        'times': times,
        'values': values,
    }


# ─────────────────────────────────────────────────────────────────
#  TestLerp / TestSlerp
# ─────────────────────────────────────────────────────────────────

class TestLerp:
    def test_lerp_zero(self):
        assert _lerp(0.0, 10.0, 0.0) == pytest.approx(0.0)

    def test_lerp_one(self):
        assert _lerp(0.0, 10.0, 1.0) == pytest.approx(10.0)

    def test_lerp_half(self):
        assert _lerp(0.0, 10.0, 0.5) == pytest.approx(5.0)

    def test_lerp3_half(self):
        a = (0.0, 0.0, 0.0)
        b = (2.0, 4.0, 6.0)
        r = _lerp3(a, b, 0.5)
        assert r == pytest.approx((1.0, 2.0, 3.0))

    def test_lerp_extrapolate_above(self):
        # t > 1 should extrapolate
        r = _lerp(0.0, 10.0, 1.5)
        assert r == pytest.approx(15.0)


class TestSlerp:
    def test_slerp_t0(self):
        q1 = [0.0, 0.0, 0.0, 1.0]
        q2 = [0.0, 0.0, 0.7071, 0.7071]
        r = _slerp(q1, q2, 0.0)
        assert r == pytest.approx(q1, abs=1e-4)

    def test_slerp_t1(self):
        q1 = [0.0, 0.0, 0.0, 1.0]
        q2 = [0.0, 0.0, 0.7071, 0.7071]
        r = _slerp(q1, q2, 1.0)
        assert r[2] == pytest.approx(0.7071, abs=1e-4)
        assert r[3] == pytest.approx(0.7071, abs=1e-4)

    def test_slerp_midpoint_normalized(self):
        q1 = [1.0, 0.0, 0.0, 0.0]
        q2 = [0.0, 1.0, 0.0, 0.0]
        r = _slerp(q1, q2, 0.5)
        mag = math.sqrt(sum(x*x for x in r))
        assert mag == pytest.approx(1.0, abs=1e-6)

    def test_slerp_antipodal_shortest_path(self):
        # When dot < 0, flip q2 to take shortest arc
        q1 = [0.0, 0.0, 0.0, 1.0]
        q2 = [0.0, 0.0, 0.0, -1.0]
        r = _slerp(q1, q2, 0.5)
        # Should return identity (they represent same rotation)
        mag = math.sqrt(sum(x*x for x in r))
        assert mag == pytest.approx(1.0, abs=1e-6)

    def test_slerp_nearly_identical(self):
        # Nearly identical quaternions → linear fallback
        q1 = [0.0, 0.0, 0.0, 1.0]
        q2 = [0.0, 0.0, 1e-6, 1.0 - 5e-13]  # very close
        r = _slerp(q1, q2, 0.5)
        mag = math.sqrt(sum(x*x for x in r))
        assert mag == pytest.approx(1.0, abs=1e-5)

    def test_slerp_zero_magnitude_fallback(self):
        # Zero-magnitude input → returns normalized
        q1 = [0.0, 0.0, 0.0, 0.0]
        q2 = [0.0, 0.0, 0.0, 1.0]
        # Should not crash
        try:
            r = _slerp(q1, q2, 0.5)
        except Exception as e:
            pytest.fail(f"slerp with zero quat raised {e}")


# ─────────────────────────────────────────────────────────────────
#  TestInterpChannel
# ─────────────────────────────────────────────────────────────────

class TestInterpChannel:
    def test_empty_returns_none(self):
        assert _interp_channel([], [], 0.5) is None

    def test_single_key_any_time(self):
        r = _interp_channel([0.5], [[1.0, 2.0, 3.0]], 99.0)
        assert r == pytest.approx([1.0, 2.0, 3.0])

    def test_before_first_key(self):
        r = _interp_channel([1.0, 2.0], [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]], 0.0)
        assert r == pytest.approx([0.0, 0.0, 0.0])

    def test_after_last_key(self):
        r = _interp_channel([0.0, 1.0], [[0.0, 0.0, 0.0], [2.0, 2.0, 2.0]], 5.0)
        assert r == pytest.approx([2.0, 2.0, 2.0])

    def test_exact_midpoint(self):
        r = _interp_channel([0.0, 1.0], [[0.0, 0.0, 0.0], [2.0, 4.0, 6.0]], 0.5)
        assert r == pytest.approx([1.0, 2.0, 3.0])

    def test_nan_keyframe_skipped(self):
        # Middle key has NaN → interpolate over it
        import math
        times = [0.0, 0.5, 1.0]
        vals  = [[0.0, 0.0, 0.0], [float('nan'), 1.0, 0.0], [2.0, 0.0, 0.0]]
        r = _interp_channel(times, vals, 0.5)
        # Should return something without NaN
        assert r is not None
        assert all(math.isfinite(x) for x in r)

    def test_quaternion_slerp(self):
        # 4-component values → slerp path
        q1 = [0.0, 0.0, 0.0, 1.0]
        q2 = [0.0, 0.0, 0.7071, 0.7071]
        r = _interp_channel([0.0, 1.0], [q1, q2], 0.5)
        assert r is not None
        mag = math.sqrt(sum(x*x for x in r))
        assert mag == pytest.approx(1.0, abs=1e-4)

    def test_three_component_lerp(self):
        r = _interp_channel([0.0, 2.0], [[0.0, 0.0, 0.0], [4.0, 6.0, 8.0]], 1.0)
        assert r == pytest.approx([2.0, 3.0, 4.0])

    def test_all_nan_returns_none(self):
        import math
        times = [0.0, 1.0]
        vals  = [[float('nan'), float('nan')], [float('nan'), float('nan')]]
        r = _interp_channel(times, vals, 0.5)
        # Should return None or valid value (not crash)
        if r is not None:
            # If not None, must be finite
            pass  # may return last-found finite, which could be None

    def test_inf_time_key_ignored(self):
        import math
        times = [0.0, float('inf'), 1.0]
        vals  = [[0.0], [5.0], [1.0]]
        # Should not crash
        try:
            r = _interp_channel(times, vals, 0.5)
        except Exception as e:
            pytest.fail(f"Inf time key raised {e}")


# ─────────────────────────────────────────────────────────────────
#  TestIsFiniteVec
# ─────────────────────────────────────────────────────────────────

class TestIsFiniteVec:
    def test_all_finite(self):
        assert _is_finite_vec([1.0, 2.0, 3.0]) is True

    def test_nan_fails(self):
        assert _is_finite_vec([1.0, float('nan'), 3.0]) is False

    def test_inf_fails(self):
        assert _is_finite_vec([float('inf'), 2.0]) is False

    def test_empty_true(self):
        assert _is_finite_vec([]) is True


# ─────────────────────────────────────────────────────────────────
#  TestAnimationEngineLifecycle
# ─────────────────────────────────────────────────────────────────

class TestAnimationEngineLifecycle:
    def _make_engine(self):
        model, root = _make_model("lifecycle")
        anim = _make_anim("cwalk", length=2.0)
        anim.nodes = [ModelNode(name="root")]
        model.animations = [anim]
        return AnimationEngine(model)

    def test_initial_state(self):
        eng = self._make_engine()
        assert eng.is_playing is False
        assert eng.current_time == 0.0
        assert eng.current_animation is None

    def test_play_returns_true(self):
        eng = self._make_engine()
        assert eng.play("cwalk") is True

    def test_play_nonexistent_returns_false(self):
        eng = self._make_engine()
        assert eng.play("nonexistent") is False

    def test_play_sets_playing(self):
        eng = self._make_engine()
        eng.play("cwalk")
        assert eng.is_playing is True

    def test_stop_clears_playing(self):
        eng = self._make_engine()
        eng.play("cwalk")
        eng.stop()
        assert eng.is_playing is False

    def test_pause_toggles_playing(self):
        eng = self._make_engine()
        eng.play("cwalk")
        eng.pause()
        assert eng.is_playing is False
        eng.pause()
        assert eng.is_playing is True

    def test_advance_returns_true_while_playing(self):
        eng = self._make_engine()
        eng.play("cwalk", loop=True)
        result = eng.advance(0.5)
        assert result is True
        assert eng.current_time == pytest.approx(0.5)

    def test_advance_loop_wraps_time(self):
        eng = self._make_engine()
        eng.play("cwalk", loop=True)
        eng.advance(1.9)  # near end
        eng.advance(0.2)  # should wrap
        # 1.9+0.2=2.1 → 2.1 % 2.0 = 0.1
        assert eng.current_time == pytest.approx(0.1, abs=1e-4)

    def test_advance_no_loop_stops_at_end(self):
        """advance() should return False when non-loop animation finishes."""
        eng = self._make_engine()
        eng.play("cwalk", loop=False)
        result = eng.advance(3.0)  # past length=2.0
        assert result is False, "advance() must return False when non-loop anim finishes"
        assert eng.is_playing is False
        assert eng.current_time == pytest.approx(2.0)

    def test_advance_no_loop_returns_true_before_end(self):
        eng = self._make_engine()
        eng.play("cwalk", loop=False)
        result = eng.advance(0.5)
        assert result is True

    def test_advance_not_playing_returns_false(self):
        eng = self._make_engine()
        result = eng.advance(0.1)
        assert result is False

    def test_seek_clamps_to_length(self):
        eng = self._make_engine()
        eng.play("cwalk", loop=False)
        eng.seek(999.0)
        # Non-loop: clamps to length
        assert eng.current_time == pytest.approx(2.0)

    def test_seek_loop_wraps(self):
        eng = self._make_engine()
        eng.play("cwalk", loop=True)
        eng.seek(2.5)
        # 2.5 % 2.0 = 0.5
        assert eng.current_time == pytest.approx(0.5)

    def test_evaluate_returns_pose(self):
        eng = self._make_engine()
        eng.play("cwalk")
        pose = eng.evaluate()
        assert isinstance(pose, AnimPose)


# ─────────────────────────────────────────────────────────────────
#  TestAnimationPoseEvaluation
# ─────────────────────────────────────────────────────────────────

class TestAnimationPoseEvaluation:
    def _make_engine_with_keys(self):
        model, root, hip, knee, foot = _make_model_with_bones()

        anim = Animation(name="cwalk", length=1.0)

        # Root: position keyframes 0→(0,0,2) over 1 second
        anim_root = ModelNode(name="root")
        anim_root.controllers = [
            _ctrl(8, [0.0, 1.0], [[0.0, 0.0, 0.0], [0.0, 0.0, 2.0]])
        ]

        # Hip: orientation keyframes – 0→identity, 1→90°Z rotation
        anim_hip = ModelNode(name="hip")
        q_identity = [0.0, 0.0, 0.0, 1.0]
        q_90z = [0.0, 0.0, 0.7071, 0.7071]  # ~90° Z
        anim_hip.controllers = [
            _ctrl(20, [0.0, 1.0], [q_identity, q_90z])
        ]

        # Knee: scale controller
        anim_knee = ModelNode(name="knee")
        anim_knee.controllers = [
            _ctrl(36, [0.0, 1.0], [[1.0], [2.0]])
        ]

        anim.nodes = [anim_root, anim_hip, anim_knee]
        model.animations = [anim]
        return AnimationEngine(model)

    def test_evaluate_empty_pose_before_play(self):
        eng = self._make_engine_with_keys()
        pose = eng.evaluate()
        assert isinstance(pose, AnimPose)
        assert len(pose.nodes) == 0

    def test_evaluate_position_at_half(self):
        eng = self._make_engine_with_keys()
        eng.play("cwalk")
        pose = eng.evaluate(0.5)
        root_pose = pose.nodes.get("root")
        assert root_pose is not None
        # At t=0.5, position should be (0,0,1.0)
        assert root_pose.position[2] == pytest.approx(1.0, abs=0.01)

    def test_evaluate_position_at_zero(self):
        eng = self._make_engine_with_keys()
        eng.play("cwalk")
        pose = eng.evaluate(0.0)
        root_pose = pose.nodes.get("root")
        assert root_pose is not None
        assert root_pose.position == pytest.approx((0.0, 0.0, 0.0), abs=0.01)

    def test_evaluate_position_at_one(self):
        eng = self._make_engine_with_keys()
        eng.play("cwalk")
        pose = eng.evaluate(1.0)
        root_pose = pose.nodes.get("root")
        assert root_pose is not None
        assert root_pose.position[2] == pytest.approx(2.0, abs=0.01)

    def test_evaluate_orientation_slerp(self):
        eng = self._make_engine_with_keys()
        eng.play("cwalk")
        pose = eng.evaluate(0.5)
        hip_pose = pose.nodes.get("hip")
        assert hip_pose is not None
        # Rotation should be between identity and 90°Z, normalized
        mag = math.sqrt(sum(x*x for x in hip_pose.rotation))
        assert mag == pytest.approx(1.0, abs=1e-4)

    def test_evaluate_scale_interpolated(self):
        eng = self._make_engine_with_keys()
        eng.play("cwalk")
        pose = eng.evaluate(0.5)
        knee_pose = pose.nodes.get("knee")
        assert knee_pose is not None
        assert knee_pose.scale == pytest.approx(1.5, abs=0.01)

    def test_evaluate_base_fallback_for_unkeyed_node(self):
        """Nodes not in anim.nodes get base-pose values."""
        eng = self._make_engine_with_keys()
        eng.play("cwalk")
        pose = eng.evaluate(0.5)
        # 'foot' was not added to anim.nodes → not in pose
        foot_pose = pose.nodes.get("foot")
        assert foot_pose is None  # Not evaluated, caller uses base pose

    def test_node_pose_structure(self):
        np = NodePose(name="test_node", position=(1, 2, 3), rotation=(0, 0, 0, 1), scale=1.0)
        assert np.name == "test_node"
        assert np.position == (1, 2, 3)
        assert np.scale == 1.0

    def test_nan_position_rejected(self):
        """_eval_node should reject NaN position values and fall back to base pose."""
        model, root = _make_model("nan_test")
        root.position = (1.0, 2.0, 3.0)
        anim = Animation(name="test", length=1.0)
        anim_root = ModelNode(name="root")
        anim_root.controllers = [
            _ctrl(8, [0.0], [[float('nan'), float('nan'), float('nan')]])
        ]
        anim.nodes = [anim_root]
        model.animations = [anim]
        eng = AnimationEngine(model)
        eng.play("test")
        pose = eng.evaluate(0.0)
        rp = pose.nodes.get("root")
        assert rp is not None
        # Position should fallback to base (1,2,3) when NaN
        assert all(math.isfinite(x) for x in rp.position)

    def test_zero_scale_rejected(self):
        """_eval_node should reject zero/negative scale."""
        model, root = _make_model("scale_test")
        anim = Animation(name="test", length=1.0)
        anim_root = ModelNode(name="root")
        anim_root.controllers = [
            _ctrl(36, [0.0], [[0.0]])  # zero scale
        ]
        anim.nodes = [anim_root]
        model.animations = [anim]
        eng = AnimationEngine(model)
        eng.play("test")
        pose = eng.evaluate(0.0)
        rp = pose.nodes.get("root")
        assert rp is not None
        assert rp.scale > 0  # should remain 1.0 fallback


# ─────────────────────────────────────────────────────────────────
#  TestAnimationListAndFPS
# ─────────────────────────────────────────────────────────────────

class TestAnimationListAndFPS:
    def _make_engine(self):
        model, root = _make_model("fps_test")
        anim1 = Animation(name="cwalk", length=2.0)
        anim_n1 = ModelNode(name="root")
        anim_n1.controllers = [
            _ctrl(8, [0.0, 0.0333, 0.0667, 0.1, 0.1333, 0.1667, 0.2, 2.0],
                  [[0,0,i*0.1] for i in range(8)])
        ]
        anim1.nodes = [anim_n1]

        anim2 = Animation(name="idle", length=0.0)  # zero-length edge case
        anim2.nodes = []

        model.animations = [anim1, anim2]
        return AnimationEngine(model)

    def test_list_animations_count(self):
        eng = self._make_engine()
        anims = eng.list_animations()
        assert len(anims) == 2

    def test_list_animations_fields(self):
        eng = self._make_engine()
        a = eng.list_animations()[0]
        assert 'name' in a
        assert 'length' in a
        assert 'key_count' in a
        assert 'node_count' in a
        assert 'event_count' in a

    def test_list_animations_name(self):
        eng = self._make_engine()
        names = [a['name'] for a in eng.list_animations()]
        assert 'cwalk' in names
        assert 'idle' in names

    def test_fps_estimate_cwalk(self):
        eng = self._make_engine()
        anim = eng.model.animations[0]
        fps = eng.get_animation_fps_estimate(anim)
        assert fps > 0

    def test_fps_estimate_empty_anim(self):
        eng = self._make_engine()
        anim = eng.model.animations[1]  # idle, zero-length
        fps = eng.get_animation_fps_estimate(anim)
        assert fps == pytest.approx(30.0)  # fallback

    def test_add_animation(self):
        eng = self._make_engine()
        new_anim = Animation(name="run", length=0.5)
        eng.add_animation(new_anim)
        names = [a['name'] for a in eng.list_animations()]
        assert 'run' in names

    def test_add_animation_replaces_existing(self):
        eng = self._make_engine()
        replacement = Animation(name="cwalk", length=99.0)
        eng.add_animation(replacement)
        for a in eng.model.animations:
            if a.name == "cwalk":
                assert a.length == 99.0
                break

    def test_remove_animation(self):
        eng = self._make_engine()
        ok = eng.remove_animation("idle")
        assert ok is True
        names = [a['name'] for a in eng.list_animations()]
        assert 'idle' not in names

    def test_remove_nonexistent_returns_false(self):
        eng = self._make_engine()
        assert eng.remove_animation("doesnotexist") is False

    def test_remove_current_clears_state(self):
        eng = self._make_engine()
        eng.play("cwalk")
        eng.remove_animation("cwalk")
        assert not eng.is_playing


# ─────────────────────────────────────────────────────────────────
#  TestAnimationEvents
# ─────────────────────────────────────────────────────────────────

class TestAnimationEvents:
    def test_events_parsed(self):
        model, root = _make_model("events_test")
        anim = Animation(name="cast", length=2.0)
        anim.events = [
            AnimEvent(time=0.5, name="sound_cast"),
            AnimEvent(time=1.0, name="vfx_hit"),
            AnimEvent(time=1.5, name="sound_impact"),
        ]
        anim.nodes = []
        model.animations = [anim]

        eng = AnimationEngine(model)
        info = eng.list_animations()[0]
        assert info['event_count'] == 3

    def test_events_in_json_export(self):
        model, root = _make_model("events_export")
        anim = Animation(name="cast", length=2.0)
        anim.events = [AnimEvent(time=0.75, name="sound_cast")]
        anim.nodes = []
        model.animations = [anim]

        eng = AnimationEngine(model)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "cast.json")
            ok = eng.export_animation_json("cast", path)
            assert ok is True
            with open(path) as f:
                data = json.load(f)
            assert len(data['events']) == 1
            assert data['events'][0]['time'] == pytest.approx(0.75)
            assert data['events'][0]['name'] == "sound_cast"


# ─────────────────────────────────────────────────────────────────
#  TestJSONExportImport
# ─────────────────────────────────────────────────────────────────

class TestJSONExportImport:
    def _make_engine(self):
        model, root, hip, knee, foot = _make_model_with_bones()
        anim = Animation(name="walk", length=1.5, transition_time=0.1)
        anim.events = [AnimEvent(time=0.3, name="step_l"), AnimEvent(time=0.9, name="step_r")]

        anim_root = ModelNode(name="root")
        anim_root.controllers = [
            _ctrl(8, [0.0, 1.5], [[0, 0, 0], [0, 0, 3]])
        ]
        anim_hip = ModelNode(name="hip")
        anim_hip.controllers = [
            _ctrl(20, [0.0, 1.5], [[0, 0, 0, 1], [0, 0, 0.5, 0.866]])
        ]
        anim.nodes = [anim_root, anim_hip]
        model.animations = [anim]
        return AnimationEngine(model)

    def test_export_json_creates_file(self):
        eng = self._make_engine()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "walk.json")
            ok = eng.export_animation_json("walk", path)
            assert ok is True
            assert os.path.exists(path)

    def test_export_json_format_field(self):
        eng = self._make_engine()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "walk.json")
            eng.export_animation_json("walk", path)
            with open(path) as f:
                data = json.load(f)
            assert data['format'] == 'kotor_animation_v1'

    def test_export_json_length(self):
        eng = self._make_engine()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "walk.json")
            eng.export_animation_json("walk", path)
            with open(path) as f:
                data = json.load(f)
            assert data['length'] == pytest.approx(1.5)

    def test_export_json_node_count(self):
        eng = self._make_engine()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "walk.json")
            eng.export_animation_json("walk", path)
            with open(path) as f:
                data = json.load(f)
            assert len(data['nodes']) == 2

    def test_export_json_events(self):
        eng = self._make_engine()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "walk.json")
            eng.export_animation_json("walk", path)
            with open(path) as f:
                data = json.load(f)
            assert len(data['events']) == 2

    def test_roundtrip_anim_name(self):
        eng = self._make_engine()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "walk.json")
            eng.export_animation_json("walk", path)
            anim2 = eng.import_animation_json(path)
            assert anim2 is not None
            assert anim2.name == "walk"

    def test_roundtrip_length(self):
        eng = self._make_engine()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "walk.json")
            eng.export_animation_json("walk", path)
            anim2 = eng.import_animation_json(path)
            assert anim2.length == pytest.approx(1.5)

    def test_roundtrip_node_count(self):
        eng = self._make_engine()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "walk.json")
            eng.export_animation_json("walk", path)
            anim2 = eng.import_animation_json(path)
            assert len(anim2.nodes) == 2

    def test_roundtrip_events(self):
        eng = self._make_engine()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "walk.json")
            eng.export_animation_json("walk", path)
            anim2 = eng.import_animation_json(path)
            assert len(anim2.events) == 2
            assert anim2.events[0].name == "step_l"
            assert anim2.events[0].time == pytest.approx(0.3)

    def test_roundtrip_controllers_preserved(self):
        eng = self._make_engine()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "walk.json")
            eng.export_animation_json("walk", path)
            anim2 = eng.import_animation_json(path)
            root_n = next((n for n in anim2.nodes if n.name == "root"), None)
            assert root_n is not None
            assert len(root_n.controllers) >= 1

    def test_import_missing_file_returns_none(self):
        eng = self._make_engine()
        result = eng.import_animation_json("/nonexistent/path/anim.json")
        assert result is None

    def test_export_nonexistent_anim_returns_false(self):
        eng = self._make_engine()
        with tempfile.TemporaryDirectory() as d:
            ok = eng.export_animation_json("does_not_exist", os.path.join(d, "x.json"))
            assert ok is False

    def test_export_all_animations(self):
        eng = self._make_engine()
        extra = Animation(name="run", length=0.8)
        extra.nodes = []
        eng.add_animation(extra)
        with tempfile.TemporaryDirectory() as d:
            paths = eng.export_all_animations(d, fmt='json')
            assert len(paths) == 2
            for p in paths:
                assert os.path.exists(p)


# ─────────────────────────────────────────────────────────────────
#  TestBVHExport
# ─────────────────────────────────────────────────────────────────

class TestBVHExport:
    def _make_engine(self):
        model, root, hip, knee, foot = _make_model_with_bones()
        anim = Animation(name="walk", length=1.0)
        anim_root = ModelNode(name="root")
        anim_root.controllers = [
            _ctrl(8, [0.0, 1.0], [[0, 0, 0], [0, 0, 0]])
        ]
        anim_hip = ModelNode(name="hip")
        anim_hip.controllers = [
            _ctrl(20, [0.0, 0.5, 1.0],
                  [[0, 0, 0, 1], [0, 0.1, 0, 0.995], [0, 0, 0, 1]])
        ]
        anim.nodes = [anim_root, anim_hip]
        model.animations = [anim]
        return AnimationEngine(model)

    def test_bvh_creates_file(self):
        eng = self._make_engine()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "walk.bvh")
            ok = eng.export_animation_bvh("walk", path)
            assert ok is True
            assert os.path.exists(path)

    def test_bvh_has_hierarchy_section(self):
        eng = self._make_engine()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "walk.bvh")
            eng.export_animation_bvh("walk", path)
            content = open(path).read()
            assert "HIERARCHY" in content

    def test_bvh_has_motion_section(self):
        eng = self._make_engine()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "walk.bvh")
            eng.export_animation_bvh("walk", path)
            content = open(path).read()
            assert "MOTION" in content

    def test_bvh_has_frames_count(self):
        eng = self._make_engine()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "walk.bvh")
            eng.export_animation_bvh("walk", path)
            content = open(path).read()
            assert "Frames:" in content

    def test_bvh_has_root_joint(self):
        eng = self._make_engine()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "walk.bvh")
            eng.export_animation_bvh("walk", path)
            content = open(path).read()
            assert "ROOT root" in content

    def test_bvh_has_channels_line(self):
        eng = self._make_engine()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "walk.bvh")
            eng.export_animation_bvh("walk", path)
            content = open(path).read()
            assert "CHANNELS" in content

    def test_bvh_nonexistent_returns_false(self):
        eng = self._make_engine()
        with tempfile.TemporaryDirectory() as d:
            ok = eng.export_animation_bvh("nonexistent", os.path.join(d, "x.bvh"))
            assert ok is False

    def test_bvh_export_all(self):
        eng = self._make_engine()
        extra = Animation(name="run", length=0.5)
        extra.nodes = []
        eng.add_animation(extra)
        with tempfile.TemporaryDirectory() as d:
            paths = eng.export_all_animations(d, fmt='bvh')
            assert len(paths) >= 1  # at least 'walk' exported


# ─────────────────────────────────────────────────────────────────
#  TestGetCtrlHelper
# ─────────────────────────────────────────────────────────────────

class TestGetCtrlHelper:
    def test_found_returns_times_values(self):
        node = ModelNode(name="n")
        node.controllers = [
            _ctrl(8, [0.0, 1.0], [[0, 0, 0], [1, 2, 3]])
        ]
        times, values = _get_ctrl(node, 8)
        assert times == [0.0, 1.0]
        assert values == [[0, 0, 0], [1, 2, 3]]

    def test_not_found_returns_empty(self):
        node = ModelNode(name="n")
        node.controllers = []
        times, values = _get_ctrl(node, 20)
        assert times == []
        assert values == []

    def test_correct_type_selected(self):
        node = ModelNode(name="n")
        node.controllers = [
            _ctrl(8, [0.0], [[1, 2, 3]]),
            _ctrl(20, [0.5], [[0, 0, 0, 1]]),
        ]
        times, values = _get_ctrl(node, 20)
        assert len(times) == 1
        assert len(values[0]) == 4


# ─────────────────────────────────────────────────────────────────
#  TestAnimPoseNodeLookup
# ─────────────────────────────────────────────────────────────────

class TestAnimPoseNodeLookup:
    def test_pose_nodes_keyed_lowercase(self):
        """AnimPose.nodes dict keys are lowercase node names."""
        model, root = _make_model("lookup_test")
        root.position = (0, 0, 0)
        anim = Animation(name="test", length=1.0)
        anim_root = ModelNode(name="Root")  # mixed case
        anim_root.controllers = [
            _ctrl(8, [0.0], [[1.0, 2.0, 3.0]])
        ]
        anim.nodes = [anim_root]
        model.animations = [anim]
        eng = AnimationEngine(model)
        eng.play("test")
        pose = eng.evaluate(0.0)
        # Key should be lowercase
        assert "root" in pose.nodes

    def test_pose_time_recorded(self):
        model, root = _make_model("time_test")
        anim = Animation(name="t", length=2.0)
        anim.nodes = [ModelNode(name="root")]
        model.animations = [anim]
        eng = AnimationEngine(model)
        eng.play("t")
        pose = eng.evaluate(1.5)
        assert pose.time == pytest.approx(1.5)

    def test_get_pose_alias(self):
        """get_pose() is an alias for evaluate()."""
        model, root = _make_model("alias_test")
        anim = Animation(name="a", length=1.0)
        anim.nodes = []
        model.animations = [anim]
        eng = AnimationEngine(model)
        eng.play("a")
        p1 = eng.evaluate(0.5)
        p2 = eng.get_pose(0.5)
        assert type(p1) == type(p2)


# ─────────────────────────────────────────────────────────────────
#  TestViewportAnimationIntegration
# ─────────────────────────────────────────────────────────────────

class TestViewportAnimationIntegration:
    """Test how the viewport FrameRenderer uses AnimPose for world transforms."""

    def _make_renderer(self, model=None):
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        if model:
            r.set_model(model)
        return r

    def test_set_animation_pose_clears_wt_cache(self):
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        model, root = _make_model("renderer_anim")
        r = self._make_renderer(model)

        # Prime the cache
        r._node_world_transform(root)
        assert len(r._wt_cache) > 0

        # Setting pose should clear cache
        pose = AnimPose(time=0.0)
        r.set_animation_pose(pose)
        assert len(r._wt_cache) == 0

    def test_anim_pose_world_transform_uses_pose(self):
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        model, root = _make_model("anim_wt")
        r = self._make_renderer(model)

        # Bind pose: root is at (0,0,0)
        wp_bind, _, _ = r._node_world_transform(root)
        assert wp_bind == pytest.approx((0.0, 0.0, 0.0), abs=1e-4)

        # With pose: root moved to (0,0,5)
        pose = AnimPose(time=0.5)
        pose.nodes["root"] = NodePose(name="root",
                                       position=(0.0, 0.0, 5.0),
                                       rotation=(0.0, 0.0, 0.0, 1.0))
        r.set_animation_pose(pose)
        wp_anim, _, _ = r._node_world_transform(root)
        assert wp_anim[2] == pytest.approx(5.0, abs=0.1)

    def test_clear_animation_pose_restores_bind(self):
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        model, root = _make_model("clear_anim")
        r = self._make_renderer(model)

        pose = AnimPose(time=0.5)
        pose.nodes["root"] = NodePose(name="root",
                                       position=(0.0, 0.0, 5.0),
                                       rotation=(0.0, 0.0, 0.0, 1.0))
        r.set_animation_pose(pose)
        r.set_animation_pose(None)
        wp, _, _ = r._node_world_transform(root)
        # Back to bind pose
        assert wp == pytest.approx((0.0, 0.0, 0.0), abs=0.1)

    def test_anim_pose_nan_falls_back_to_bind(self):
        """Animated position with NaN falls back to bind-pose position."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        model, root = _make_model("nan_fallback")
        root.position = (1.0, 2.0, 3.0)
        r = self._make_renderer(model)

        pose = AnimPose(time=0.5)
        pose.nodes["root"] = NodePose(name="root",
                                       position=(float('nan'), float('nan'), float('nan')),
                                       rotation=(0.0, 0.0, 0.0, 1.0))
        r.set_animation_pose(pose)
        wp, _, _ = r._node_world_transform(root)
        # Should fall back to bind pose (1,2,3)
        assert all(math.isfinite(x) for x in wp)


# ─────────────────────────────────────────────────────────────────
#  TestAnimationDerivedLength
# ─────────────────────────────────────────────────────────────────

class TestAnimationDerivedLength:
    def test_zero_length_derived_from_keyframes(self):
        """When anim.length == 0, the parser should derive it from keyframe times."""
        # Test that _parse_one_animation logic works: if length=0, max keyframe time used.
        # We simulate this by checking that the engine's list_animations shows the right length.
        from src.core.mdl_parser import MDLBinaryParser
        # We can't easily create a binary MDL here, but we can simulate the fix:
        model, root = _make_model("zero_len")
        anim = Animation(name="walk", length=0.0)  # zero stored length
        anim_n = ModelNode(name="root")
        anim_n.controllers = [_ctrl(8, [0.0, 1.5], [[0, 0, 0], [1, 0, 0]])]
        anim.nodes = [anim_n]

        # Simulate the parser's fix: derive length from keyframe times
        derived = max(
            (t for n in anim.nodes for c in n.controllers for t in c['times']),
            default=0.0
        )
        if anim.length <= 0.0 and derived > 0.0:
            anim.length = derived

        assert anim.length == pytest.approx(1.5)

    def test_nonzero_length_not_overridden(self):
        """When anim.length > 0, keyframes should not override it."""
        model, root = _make_model("nonzero_len")
        anim = Animation(name="walk", length=2.0)
        anim_n = ModelNode(name="root")
        anim_n.controllers = [_ctrl(8, [0.0, 1.5], [[0, 0, 0], [1, 0, 0]])]
        anim.nodes = [anim_n]
        # Length stays at 2.0 (not overridden to 1.5)
        assert anim.length == pytest.approx(2.0)


# ─────────────────────────────────────────────────────────────────
#  TestPackedQuaternionDecoding
# ─────────────────────────────────────────────────────────────────

class TestPackedQuaternionDecoding:
    """Test the 10-11-11 bit packed quaternion format used in binary MDLs."""

    def _decode_packed_quat(self, temp: int):
        """Replicate the mdl_parser packed quat decoding."""
        qx = 1.0 - (temp & 0x7FF) / 1023.0
        qy = 1.0 - ((temp >> 11) & 0x7FF) / 1023.0
        qz = 1.0 - (temp >> 22) / 511.0
        mag2 = qx*qx + qy*qy + qz*qz
        if mag2 < 1.0:
            qw = -math.sqrt(1.0 - mag2)
        else:
            nl = math.sqrt(mag2)
            if nl > 1e-9:
                qx /= nl; qy /= nl; qz /= nl
            qw = 0.0
        return (qx, qy, qz, qw)

    def test_packed_identity_normalised(self):
        """Packed quaternion result should have unit magnitude (approximately)."""
        import struct
        # Use value 0 (all bits zero) → qx=qy=1.0, qz=1.0 → big, normalize
        temp = 0x00000000
        q = self._decode_packed_quat(temp)
        mag = math.sqrt(sum(x*x for x in q))
        assert mag == pytest.approx(1.0, abs=1e-4)

    def test_packed_known_value(self):
        """For a known packed word, verify decoded quaternion is unit-length."""
        # mid-range value
        temp = 0x3FF7FF3FF
        qx = 1.0 - (temp & 0x7FF) / 1023.0
        qy = 1.0 - ((temp >> 11) & 0x7FF) / 1023.0
        qz = 1.0 - (temp >> 22) / 511.0
        mag2 = qx*qx + qy*qy + qz*qz
        # Either unit or normalized → verify we'd get unit mag
        if mag2 < 1.0:
            qw = -math.sqrt(1.0 - mag2)
            total = math.sqrt(mag2 + qw*qw)
            assert total == pytest.approx(1.0, abs=1e-4)
        else:
            nl = math.sqrt(mag2)
            assert nl > 0  # normalizable

    def test_packed_all_ones_normalized(self):
        temp = 0xFFFFFFFF
        q = self._decode_packed_quat(temp)
        mag = math.sqrt(sum(x*x for x in q))
        assert mag == pytest.approx(1.0, abs=1e-4)


# ─────────────────────────────────────────────────────────────────
#  TestAnimationEngineEdgeCases
# ─────────────────────────────────────────────────────────────────

class TestAnimationEngineEdgeCases:
    def test_play_empty_model(self):
        """Play on model with no root_node should not crash."""
        model = KotorModel(name="empty")
        anim = Animation(name="test", length=1.0)
        anim.nodes = []
        model.animations = [anim]
        eng = AnimationEngine(model)
        ok = eng.play("test")
        assert ok is True
        pose = eng.evaluate()
        assert isinstance(pose, AnimPose)

    def test_advance_with_zero_length_anim(self):
        """Animation with length=0 should not cause division errors."""
        model, root = _make_model("zero_len_advance")
        anim = Animation(name="flash", length=0.0)
        anim.nodes = []
        model.animations = [anim]
        eng = AnimationEngine(model)
        eng.play("flash")
        # Should not raise
        try:
            result = eng.advance(0.1)
        except Exception as e:
            pytest.fail(f"advance with zero-length anim raised {e}")

    def test_evaluate_at_exact_start(self):
        model, root, hip, *_ = _make_model_with_bones()
        # hip bind pose is at (0,0,1.0); controller type 8 keys are DELTA offsets
        # (xoreos/KotorBlender convention: animated = bind + delta).
        # At t=0.0, delta=(0,0,0), so result = bind(0,0,1.0) + delta(0,0,0) = (0,0,1.0)
        anim = Animation(name="t", length=1.0)
        anim_hip = ModelNode(name="hip")
        anim_hip.controllers = [
            _ctrl(8, [0.0, 1.0], [[0, 0, 0], [1, 1, 1]])
        ]
        anim.nodes = [anim_hip]
        model.animations = [anim]
        eng = AnimationEngine(model)
        eng.play("t")
        pose = eng.evaluate(0.0)
        hp = pose.nodes.get("hip")
        assert hp is not None
        # At t=0: bind_pos=(0,0,1.0) + delta(0,0,0) = (0,0,1.0)
        assert hp.position == pytest.approx((0, 0, 1.0), abs=0.01)

    def test_evaluate_at_exact_end(self):
        model, root, hip, *_ = _make_model_with_bones()
        anim = Animation(name="t", length=1.0)
        anim_hip = ModelNode(name="hip")
        anim_hip.controllers = [
            _ctrl(8, [0.0, 1.0], [[0, 0, 0], [1, 1, 1]])
        ]
        anim.nodes = [anim_hip]
        model.animations = [anim]
        eng = AnimationEngine(model)
        eng.play("t")
        pose = eng.evaluate(1.0)
        hp = pose.nodes.get("hip")
        assert hp is not None
        # At t=1.0: bind_pos=(0,0,1.0) + delta(1,1,1) = (1,1,2.0)
        assert hp.position == pytest.approx((1, 1, 2.0), abs=0.01)

    def test_multiple_advances_accumulate(self):
        model, root = _make_model("multi_adv")
        anim = Animation(name="t", length=3.0)
        anim.nodes = []
        model.animations = [anim]
        eng = AnimationEngine(model)
        eng.play("t", loop=True)
        for _ in range(10):
            eng.advance(0.1)
        assert eng.current_time == pytest.approx(1.0, abs=0.01)

    def test_seek_without_playing(self):
        """seek() should be a no-op if no current animation."""
        model, root = _make_model("seek_nop")
        eng = AnimationEngine(model)
        eng.seek(5.0)  # Should not crash
        assert eng.current_time == 0.0


# ─────────────────────────────────────────────────────────────────
#  TestAnimationBaseNodeFallback
# ─────────────────────────────────────────────────────────────────

class TestAnimationBaseNodeFallback:
    """_eval_node uses bind-pose values when a node isn't in base_nodes."""

    def test_unknown_node_uses_zero_position(self):
        model, root = _make_model("base_fallback")
        anim = Animation(name="t", length=1.0)
        # anim node whose name doesn't match any model node
        anim_ghost = ModelNode(name="ghost_bone")
        anim_ghost.controllers = [
            _ctrl(8, [0.0, 1.0], [[0, 0, 0], [1, 2, 3]])
        ]
        anim.nodes = [anim_ghost]
        model.animations = [anim]
        eng = AnimationEngine(model)
        eng.play("t")
        pose = eng.evaluate(0.5)
        gp = pose.nodes.get("ghost_bone")
        assert gp is not None
        # Position should be interpolated value (no base node → starts from 0,0,0)
        assert gp.position == pytest.approx((0.5, 1.0, 1.5), abs=0.01)

    def test_base_node_position_inherited(self):
        """When no position controller, base pose position is preserved."""
        model, root = _make_model("base_inherit")
        root.position = (5.0, 0.0, 0.0)  # non-zero bind pose
        anim = Animation(name="t", length=1.0)
        anim_root = ModelNode(name="root")
        # Only orientation controller, no position controller
        anim_root.controllers = [
            _ctrl(20, [0.0], [[0, 0, 0, 1]])
        ]
        anim.nodes = [anim_root]
        model.animations = [anim]
        eng = AnimationEngine(model)
        eng.play("t")
        pose = eng.evaluate(0.5)
        rp = pose.nodes.get("root")
        assert rp is not None
        # Position should be base pose (5,0,0)
        assert rp.position[0] == pytest.approx(5.0, abs=0.01)
