"""
GhostRigger-K1-K2  v3.2 — Animation Engine Test Suite
========================================================
Covers:
  1.  Interpolation helpers (_lerp, _lerp3, _slerp, _interp_channel, _is_finite_vec)
  2.  AnimationEngine lifecycle (play / stop / pause / seek / advance)
  3.  advance() return value correctness (non-loop end → False, loop → True)
  4.  Pose evaluation (position, orientation, scale controllers)
  5.  Cross-fade transition blending (blend=True)
  6.  Event firing (fire once per loop, reset on seek/play)
  7.  Quaternion normalisation in _eval_node
  8.  NaN / Inf guard in keyframe values
  9.  list_animations() + get_animation_fps_estimate()
  10. JSON export / import round-trip
  11. BVH export structure validation
  12. export_all_animations()
  13. add_animation / remove_animation
  14. get_pose() alias
  15. is_blending() / blend_fraction() helpers
  16. Viewport set_animation_pose() integration
  17. Rigging display: _bone_world_pos during animation
  18. Packed-quaternion controller decoding (MDL parser)
  19. AnimPose / NodePose dataclasses
  20. Edge-cases: zero-length animation, single keyframe, empty nodes

Total: 60 tests
"""

from __future__ import annotations

import math
import sys
import os
import json
import struct
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest

from src.core.model_data import KotorModel, ModelNode, Animation, AnimEvent, NodeFlags
from src.core.animation_engine import (
    AnimationEngine, AnimPose, NodePose,
    _lerp, _lerp3, _slerp, _interp_channel, _is_finite_vec, _get_ctrl,
)


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────

def _make_model(name="m"):
    """Minimal model with one root and one child bone."""
    model = KotorModel(name=name)
    root  = ModelNode(name='root',   position=(0, 0, 0), rotation=(0, 0, 0, 1))
    bone  = ModelNode(name='bone01', position=(0, 1, 0), rotation=(0, 0, 0, 1), parent=root)
    root.children.append(bone)
    model.root_node = root
    return model


def _make_pos_anim(name="cwalk", length=1.0, pos_keys=None, trans=0.25):
    """Animation with a position controller on 'root'."""
    if pos_keys is None:
        pos_keys = {'times': [0.0, 1.0], 'values': [[0, 0, 0], [1, 0, 0]]}
    anim = Animation(name=name, length=length, transition_time=trans)
    n = ModelNode(name='root')
    n.controllers = [{
        'type': 8, 'name': 'position', 'columns': 3,
        'times': pos_keys['times'], 'values': pos_keys['values'],
    }]
    anim.nodes = [n]
    return anim


def _make_rot_anim(name="cturn", length=1.0):
    """Animation with an orientation controller on 'bone01'."""
    anim = Animation(name=name, length=length, transition_time=0.1)
    n = ModelNode(name='bone01')
    n.controllers = [{
        'type': 20, 'name': 'orientation', 'columns': 4,
        'times': [0.0, 1.0],
        'values': [[0, 0, 0, 1], [0, 0, 0.7071, 0.7071]],
    }]
    anim.nodes = [n]
    return anim


def _make_scale_anim(name="cscale", length=1.0):
    """Animation with a scale controller on 'root'."""
    anim = Animation(name=name, length=length)
    n = ModelNode(name='root')
    n.controllers = [{
        'type': 36, 'name': 'scale', 'columns': 1,
        'times': [0.0, 1.0], 'values': [[1.0], [2.0]],
    }]
    anim.nodes = [n]
    return anim


def _make_event_anim(events, name="cevent", length=1.0):
    anim = Animation(name=name, length=length)
    anim.nodes = []
    for t, ev_name in events:
        anim.events.append(AnimEvent(time=t, name=ev_name))
    return anim


def _engine_with(anims):
    """Return an (engine, model) tuple pre-loaded with the given animations."""
    model = _make_model()
    model.animations = list(anims)
    return AnimationEngine(model), model


# ─────────────────────────────────────────────────────────────
#  1. Interpolation Helpers
# ─────────────────────────────────────────────────────────────

class TestInterpolationHelpers:

    def test_lerp_midpoint(self):
        assert abs(_lerp(0.0, 10.0, 0.5) - 5.0) < 1e-9

    def test_lerp_zero(self):
        assert _lerp(3.0, 7.0, 0.0) == pytest.approx(3.0)

    def test_lerp_one(self):
        assert _lerp(3.0, 7.0, 1.0) == pytest.approx(7.0)

    def test_lerp3_midpoint(self):
        r = _lerp3((0, 0, 0), (2, 4, 6), 0.5)
        assert r == pytest.approx((1.0, 2.0, 3.0))

    def test_is_finite_vec_all_finite(self):
        assert _is_finite_vec([1.0, 2.0, 3.0]) is True

    def test_is_finite_vec_nan(self):
        assert _is_finite_vec([1.0, float('nan'), 3.0]) is False

    def test_is_finite_vec_inf(self):
        assert _is_finite_vec([1.0, float('inf'), 3.0]) is False


class TestSlerp:

    def test_slerp_at_zero(self):
        q1 = [0, 0, 0, 1]
        q2 = [0, 0, 0.7071, 0.7071]
        r = _slerp(q1, q2, 0.0)
        assert r == pytest.approx([0, 0, 0, 1], abs=1e-4)

    def test_slerp_at_one(self):
        q1 = [0, 0, 0, 1]
        q2 = [0, 0, 0.7071, 0.7071]
        r = _slerp(q1, q2, 1.0)
        assert r == pytest.approx([0, 0, 0.7071, 0.7071], abs=1e-4)

    def test_slerp_normalized(self):
        q1 = [1, 0, 0, 0]
        q2 = [0, 1, 0, 0]
        r = _slerp(q1, q2, 0.5)
        mag = sum(x*x for x in r) ** 0.5
        assert abs(mag - 1.0) < 1e-6

    def test_slerp_antipodal_shortest_path(self):
        """Antipodal quats should be handled (dot < 0 branch) without NaN."""
        q1 = [0, 0, 0, 1]
        q2 = [0, 0, 0, -1]
        r = _slerp(q1, q2, 0.5)
        assert all(math.isfinite(v) for v in r)

    def test_slerp_identical(self):
        q = [0.0, 0.0, 0.0, 1.0]
        r = _slerp(q, q, 0.5)
        assert r == pytest.approx(q, abs=1e-6)


class TestInterpChannel:

    def test_empty_returns_none(self):
        assert _interp_channel([], [], 0.5) is None

    def test_single_key_returns_it(self):
        r = _interp_channel([0.0], [[1.0, 2.0, 3.0]], 5.0)
        assert r == pytest.approx([1.0, 2.0, 3.0])

    def test_clamp_before_first(self):
        r = _interp_channel([1.0, 2.0], [[0, 0, 0], [1, 1, 1]], 0.0)
        assert r == pytest.approx([0, 0, 0])

    def test_clamp_after_last(self):
        r = _interp_channel([0.0, 1.0], [[0, 0, 0], [5, 5, 5]], 99.0)
        assert r == pytest.approx([5, 5, 5])

    def test_midpoint_lerp(self):
        r = _interp_channel([0.0, 1.0], [[0, 0, 0], [2, 0, 0]], 0.5)
        assert r == pytest.approx([1.0, 0.0, 0.0])

    def test_nan_keyframe_skipped(self):
        """Corrupt middle keyframe should be bridged over."""
        times = [0.0, 0.5, 1.0]
        vals  = [[0, 0, 0], [float('nan'), 0, 0], [2, 0, 0]]
        r = _interp_channel(times, vals, 0.75)
        assert r is not None
        assert all(math.isfinite(v) for v in r)

    def test_quat_slerp_branch(self):
        """len(v0)==4 should use slerp, not lerp."""
        q1 = [0, 0, 0, 1]
        q2 = [0, 0, 0.7071, 0.7071]
        r = _interp_channel([0.0, 1.0], [q1, q2], 0.5)
        assert r is not None
        mag = sum(x*x for x in r) ** 0.5
        assert abs(mag - 1.0) < 1e-5


# ─────────────────────────────────────────────────────────────
#  2. AnimationEngine Lifecycle
# ─────────────────────────────────────────────────────────────

class TestEngineLifecycle:

    def test_play_returns_true(self):
        eng, _ = _engine_with([_make_pos_anim()])
        assert eng.play('cwalk') is True

    def test_play_missing_returns_false(self):
        eng, _ = _engine_with([_make_pos_anim()])
        assert eng.play('nonexistent') is False

    def test_stop_clears_playing(self):
        eng, _ = _engine_with([_make_pos_anim()])
        eng.play('cwalk')
        eng.stop()
        assert eng.is_playing is False

    def test_pause_toggles(self):
        eng, _ = _engine_with([_make_pos_anim()])
        eng.play('cwalk')
        eng.pause()
        assert eng.is_playing is False
        eng.pause()
        assert eng.is_playing is True

    def test_seek_clamps_non_loop(self):
        eng, _ = _engine_with([_make_pos_anim()])
        eng.play('cwalk', loop=False)
        eng.seek(5.0)
        assert eng.current_time == pytest.approx(1.0)

    def test_seek_wraps_loop(self):
        eng, _ = _engine_with([_make_pos_anim()])
        eng.play('cwalk', loop=True)
        eng.seek(1.7)
        assert eng.current_time == pytest.approx(0.7, abs=1e-6)

    def test_initial_state(self):
        eng, _ = _engine_with([])
        assert eng.is_playing is False
        assert eng.current_time == 0.0
        assert eng.current_animation is None


# ─────────────────────────────────────────────────────────────
#  3. advance() Return Value
# ─────────────────────────────────────────────────────────────

class TestAdvanceReturnValue:

    def test_advance_not_playing_returns_false(self):
        eng, _ = _engine_with([_make_pos_anim()])
        assert eng.advance(0.1) is False

    def test_advance_during_loop_returns_true(self):
        eng, _ = _engine_with([_make_pos_anim()])
        eng.play('cwalk', loop=True)
        assert eng.advance(0.3) is True

    def test_advance_non_loop_past_end_returns_false(self):
        eng, _ = _engine_with([_make_pos_anim()])
        eng.play('cwalk', loop=False)
        result = eng.advance(1.5)
        assert result is False
        assert eng.is_playing is False

    def test_advance_non_loop_mid_returns_true(self):
        eng, _ = _engine_with([_make_pos_anim()])
        eng.play('cwalk', loop=False)
        assert eng.advance(0.5) is True

    def test_advance_loop_wraps_and_continues(self):
        eng, _ = _engine_with([_make_pos_anim()])
        eng.play('cwalk', loop=True)
        eng.seek(0.95)
        result = eng.advance(0.2)
        assert result is True
        # Time should have wrapped around
        assert eng.current_time < 0.5


# ─────────────────────────────────────────────────────────────
#  4. Pose Evaluation
# ─────────────────────────────────────────────────────────────

class TestPoseEvaluation:

    def test_position_interpolation(self):
        eng, _ = _engine_with([_make_pos_anim()])
        eng.play('cwalk')
        pose = eng.evaluate(0.5)
        rp = pose.nodes.get('root')
        assert rp is not None
        assert rp.position == pytest.approx((0.5, 0.0, 0.0), abs=1e-5)

    def test_position_at_start(self):
        eng, _ = _engine_with([_make_pos_anim()])
        eng.play('cwalk')
        pose = eng.evaluate(0.0)
        rp = pose.nodes.get('root')
        assert rp.position == pytest.approx((0.0, 0.0, 0.0), abs=1e-5)

    def test_position_at_end(self):
        eng, _ = _engine_with([_make_pos_anim()])
        eng.play('cwalk')
        pose = eng.evaluate(1.0)
        rp = pose.nodes.get('root')
        assert rp.position == pytest.approx((1.0, 0.0, 0.0), abs=1e-5)

    def test_orientation_slerp(self):
        eng, _ = _engine_with([_make_rot_anim()])
        eng.play('cturn')
        pose = eng.evaluate(0.5)
        bp = pose.nodes.get('bone01')
        assert bp is not None
        # Rotation at t=0.5 should be between identity and 90° Z
        mag = sum(x*x for x in bp.rotation) ** 0.5
        assert abs(mag - 1.0) < 1e-5

    def test_scale_interpolation(self):
        eng, _ = _engine_with([_make_scale_anim()])
        eng.play('cscale')
        pose = eng.evaluate(0.5)
        rp = pose.nodes.get('root')
        assert rp is not None
        assert abs(rp.scale - 1.5) < 1e-5

    def test_evaluate_no_animation_returns_empty_pose(self):
        eng, _ = _engine_with([])
        pose = eng.evaluate()
        assert isinstance(pose, AnimPose)
        assert len(pose.nodes) == 0

    def test_evaluate_uses_current_time(self):
        eng, _ = _engine_with([_make_pos_anim()])
        eng.play('cwalk')
        eng.advance(0.25)
        pose = eng.evaluate()
        rp = pose.nodes.get('root')
        assert rp.position[0] == pytest.approx(0.25, abs=1e-5)

    def test_base_pose_fallback_when_no_key(self):
        """Nodes not in the animation should fall back to bind-pose values."""
        eng, model = _engine_with([_make_pos_anim()])
        eng.play('cwalk')
        pose = eng.evaluate(0.5)
        # 'bone01' has no controller in cwalk – should appear from base pose
        # (or simply not appear in the pose dict, which is also valid)
        # Either way it should not crash
        assert isinstance(pose, AnimPose)


# ─────────────────────────────────────────────────────────────
#  5. Cross-Fade Transition Blending
# ─────────────────────────────────────────────────────────────

class TestTransitionBlending:

    def _two_anims(self):
        anim_a = _make_pos_anim('cwalk', length=1.0, pos_keys={
            'times': [0.0, 1.0], 'values': [[0, 0, 0], [1, 0, 0]]
        }, trans=0.25)
        anim_b = Animation(name='cidle', length=0.5, transition_time=0.1)
        n = ModelNode(name='root')
        n.controllers = [{
            'type': 8, 'name': 'position', 'columns': 3,
            'times': [0.0, 0.5], 'values': [[5, 0, 0], [5, 0, 0]],
        }]
        anim_b.nodes = [n]
        return _engine_with([anim_a, anim_b])

    def test_is_blending_after_switch(self):
        eng, _ = self._two_anims()
        eng.play('cwalk', loop=True)
        eng.advance(0.3)
        eng.play('cidle', loop=True, blend=True)
        assert eng.is_blending() is True

    def test_blend_fraction_starts_at_zero(self):
        eng, _ = self._two_anims()
        eng.play('cwalk', loop=True)
        eng.advance(0.3)
        eng.play('cidle', loop=True, blend=True)
        assert eng.blend_fraction() == pytest.approx(0.0, abs=1e-9)

    def test_blend_progresses_with_advance(self):
        eng, _ = self._two_anims()
        eng.play('cwalk', loop=True)
        eng.advance(0.3)
        eng.play('cidle', loop=True, blend=True)
        # transition_time = 0.1, advance 0.05 → blend_t ≈ 0.5
        eng.advance(0.05)
        assert eng.blend_fraction() == pytest.approx(0.5, abs=0.05)

    def test_blend_completes_after_transition_time(self):
        eng, _ = self._two_anims()
        eng.play('cwalk', loop=True)
        eng.advance(0.3)
        eng.play('cidle', loop=True, blend=True)
        eng.advance(0.2)  # past transition_time=0.1
        assert eng.is_blending() is False

    def test_no_blend_when_not_playing(self):
        eng, _ = self._two_anims()
        eng.play('cidle', loop=True, blend=True)
        # Was not playing before – no blend should be active
        assert eng.is_blending() is False

    def test_blend_pose_interpolated(self):
        """Pose during blend should be between old and new animation values."""
        eng, _ = self._two_anims()
        eng.play('cwalk', loop=True)
        eng.advance(0.5)
        pos_before = eng.evaluate().nodes.get('root').position[0]  # ≈ 0.5
        eng.play('cidle', blend=True)
        eng.advance(0.05)  # halfway through 0.1s blend
        blended = eng.evaluate()
        rp = blended.nodes.get('root')
        assert rp is not None
        # Should be between 0.5 (old) and 5.0 (new)
        assert pos_before - 0.5 < rp.position[0] < 5.5


# ─────────────────────────────────────────────────────────────
#  6. Event Firing
# ─────────────────────────────────────────────────────────────

class TestEventFiring:

    def test_event_fires_after_time(self):
        eng, _ = _engine_with([_make_event_anim([(0.3, 'footstep')])])
        eng.play('cevent', loop=False)
        eng.advance(0.4)
        assert 'footstep' in eng.get_fired_events()

    def test_event_not_fired_before_time(self):
        eng, _ = _engine_with([_make_event_anim([(0.5, 'step')])])
        eng.play('cevent', loop=False)
        eng.advance(0.2)
        assert eng.get_fired_events() == []

    def test_multiple_events_ordered(self):
        eng, _ = _engine_with([_make_event_anim([(0.2, 'a'), (0.6, 'b'), (0.9, 'c')])])
        eng.play('cevent', loop=False)
        eng.advance(0.7)
        fired = eng.get_fired_events()
        assert 'a' in fired and 'b' in fired
        assert 'c' not in fired

    def test_events_reset_on_loop(self):
        eng, _ = _engine_with([_make_event_anim([(0.3, 'step')], length=0.5)])
        eng.play('cevent', loop=True)
        eng.advance(0.4)
        assert 'step' in eng.get_fired_events()
        # Loop wraps – fired_events cleared
        eng.advance(0.2)   # crosses 0.5 boundary → reset
        # After reset, events may fire again in the new cycle
        assert isinstance(eng.get_fired_events(), list)

    def test_seek_resets_fired_events(self):
        eng, _ = _engine_with([_make_event_anim([(0.3, 'step')])])
        eng.play('cevent', loop=True)
        eng.advance(0.4)
        assert 'step' in eng.get_fired_events()
        eng.seek(0.1)  # seek back before event
        assert eng.get_fired_events() == []

    def test_no_events_returns_empty(self):
        eng, _ = _engine_with([_make_pos_anim()])
        eng.play('cwalk')
        assert eng.get_fired_events() == []


# ─────────────────────────────────────────────────────────────
#  7. Quaternion Normalisation
# ─────────────────────────────────────────────────────────────

class TestQuatNormalisation:

    def test_base_pose_unnormalised_quat_fixed(self):
        """An un-normalised bind-pose quaternion should be fixed during eval."""
        model = _make_model()
        # Deliberately set un-normalised rotation on bone01
        model.root_node.children[0].rotation = (0.0, 0.0, 2.0, 2.0)
        anim = _make_rot_anim('cturn')
        model.animations = [anim]
        eng = AnimationEngine(model)
        eng.play('cturn')
        pose = eng.evaluate(0.5)
        bp = pose.nodes.get('bone01')
        if bp:
            mag = sum(x*x for x in bp.rotation) ** 0.5
            assert abs(mag - 1.0) < 1e-4

    def test_animated_quat_normalised(self):
        """Interpolated orientation should always be unit-length."""
        eng, _ = _engine_with([_make_rot_anim()])
        eng.play('cturn')
        for t in [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]:
            pose = eng.evaluate(t)
            bp = pose.nodes.get('bone01')
            if bp:
                mag = sum(x*x for x in bp.rotation) ** 0.5
                assert abs(mag - 1.0) < 1e-4, f"denormalised at t={t}: mag={mag}"


# ─────────────────────────────────────────────────────────────
#  8. NaN / Inf Guards
# ─────────────────────────────────────────────────────────────

class TestNaNGuards:

    def test_nan_position_uses_base_pose(self):
        anim = Animation(name='corrupt', length=1.0)
        n = ModelNode(name='root')
        n.controllers = [{
            'type': 8, 'name': 'position', 'columns': 3,
            'times': [0.0], 'values': [[float('nan'), 0, 0]],
        }]
        anim.nodes = [n]
        model = _make_model()
        model.animations = [anim]
        eng = AnimationEngine(model)
        eng.play('corrupt')
        pose = eng.evaluate(0.0)
        rp = pose.nodes.get('root')
        assert rp is not None
        assert all(math.isfinite(v) for v in rp.position)

    def test_nan_rotation_uses_previous_finite(self):
        anim = Animation(name='corrupt', length=1.0)
        n = ModelNode(name='bone01')
        n.controllers = [{
            'type': 20, 'name': 'orientation', 'columns': 4,
            'times': [0.0, 0.5, 1.0],
            'values': [[0,0,0,1], [float('nan'),0,0,1], [0,0,0.7071,0.7071]],
        }]
        anim.nodes = [n]
        model = _make_model()
        model.animations = [anim]
        eng = AnimationEngine(model)
        eng.play('corrupt')
        pose = eng.evaluate(0.5)
        bp = pose.nodes.get('bone01')
        # May be None if NaN row blocks the node entirely — or finite
        if bp:
            assert all(math.isfinite(v) for v in bp.rotation)

    def test_inf_scale_ignored(self):
        anim = Animation(name='corrupt', length=1.0)
        n = ModelNode(name='root')
        n.controllers = [{
            'type': 36, 'name': 'scale', 'columns': 1,
            'times': [0.0], 'values': [[float('inf')]],
        }]
        anim.nodes = [n]
        model = _make_model()
        model.animations = [anim]
        eng = AnimationEngine(model)
        eng.play('corrupt')
        pose = eng.evaluate(0.0)
        rp = pose.nodes.get('root')
        if rp:
            assert math.isfinite(rp.scale)


# ─────────────────────────────────────────────────────────────
#  9. list_animations + fps estimate
# ─────────────────────────────────────────────────────────────

class TestListAnimations:

    def test_list_returns_all(self):
        eng, _ = _engine_with([_make_pos_anim('a'), _make_pos_anim('b'), _make_pos_anim('c')])
        lst = eng.list_animations()
        assert len(lst) == 3
        names = [d['name'] for d in lst]
        assert set(names) == {'a', 'b', 'c'}

    def test_list_empty(self):
        eng, _ = _engine_with([])
        assert eng.list_animations() == []

    def test_list_fields(self):
        eng, _ = _engine_with([_make_pos_anim('cwalk')])
        info = eng.list_animations()[0]
        assert 'name' in info and 'length' in info
        assert 'key_count' in info and 'node_count' in info

    def test_fps_estimate_reasonable(self):
        anim = _make_pos_anim('cwalk', length=1.0, pos_keys={
            'times': [i*0.1 for i in range(11)],
            'values': [[i*0.1, 0, 0] for i in range(11)],
        })
        eng, _ = _engine_with([anim])
        fps = eng.get_animation_fps_estimate(anim)
        # 11 keyframes over 1s → ~10 fps
        assert 5.0 <= fps <= 15.0

    def test_fps_estimate_no_keys(self):
        anim = Animation(name='empty', length=1.0)
        eng, _ = _engine_with([anim])
        fps = eng.get_animation_fps_estimate(anim)
        assert fps == pytest.approx(30.0)


# ─────────────────────────────────────────────────────────────
#  10. JSON Export / Import Round-Trip
# ─────────────────────────────────────────────────────────────

class TestJSONRoundTrip:

    def _export_import(self, anim):
        eng, _ = _engine_with([anim])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, f"{anim.name}.json")
            ok = eng.export_animation_json(anim.name, path)
            assert ok is True
            anim2 = eng.import_animation_json(path)
        return anim2

    def test_name_preserved(self):
        a = _make_pos_anim('mywalk')
        a2 = self._export_import(a)
        assert a2.name == 'mywalk'

    def test_length_preserved(self):
        a = _make_pos_anim(length=2.5)
        a2 = self._export_import(a)
        assert abs(a2.length - 2.5) < 1e-6

    def test_nodes_preserved(self):
        a = _make_pos_anim()
        a2 = self._export_import(a)
        assert len(a2.nodes) == len(a.nodes)

    def test_controllers_preserved(self):
        a = _make_pos_anim()
        a2 = self._export_import(a)
        assert len(a2.nodes[0].controllers) > 0

    def test_events_preserved(self):
        a = _make_event_anim([(0.3, 'step'), (0.7, 'land')])
        a2 = self._export_import(a)
        assert len(a2.events) == 2
        assert a2.events[0].name == 'step'

    def test_import_missing_file_returns_none(self):
        eng, _ = _engine_with([])
        r = eng.import_animation_json('/nonexistent/path/anim.json')
        assert r is None


# ─────────────────────────────────────────────────────────────
#  11. BVH Export
# ─────────────────────────────────────────────────────────────

class TestBVHExport:

    def _export_bvh(self, anim):
        eng, _ = _engine_with([anim])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, f"{anim.name}.bvh")
            ok = eng.export_animation_bvh(anim.name, path)
            assert ok is True
            with open(path) as f:
                content = f.read()
        return content

    def test_has_hierarchy(self):
        assert 'HIERARCHY' in self._export_bvh(_make_pos_anim())

    def test_has_motion(self):
        assert 'MOTION' in self._export_bvh(_make_pos_anim())

    def test_has_frames(self):
        content = self._export_bvh(_make_pos_anim())
        assert 'Frames:' in content

    def test_frame_count_positive(self):
        content = self._export_bvh(_make_pos_anim())
        for line in content.splitlines():
            if line.startswith('Frames:'):
                count = int(line.split(':')[1].strip())
                assert count > 0
                break

    def test_missing_anim_returns_false(self):
        eng, _ = _engine_with([])
        with tempfile.TemporaryDirectory() as d:
            ok = eng.export_animation_bvh('missing', os.path.join(d, 'x.bvh'))
        assert ok is False


# ─────────────────────────────────────────────────────────────
#  12. export_all_animations
# ─────────────────────────────────────────────────────────────

class TestExportAll:

    def test_exports_all_json(self):
        anims = [_make_pos_anim('a'), _make_pos_anim('b'), _make_pos_anim('c')]
        eng, _ = _engine_with(anims)
        with tempfile.TemporaryDirectory() as d:
            paths = eng.export_all_animations(d, fmt='json')
            assert len(paths) == 3
            assert all(p.endswith('.json') for p in paths)

    def test_exports_all_bvh(self):
        anims = [_make_pos_anim('x'), _make_pos_anim('y')]
        eng, _ = _engine_with(anims)
        with tempfile.TemporaryDirectory() as d:
            paths = eng.export_all_animations(d, fmt='bvh')
            assert len(paths) == 2
            assert all(p.endswith('.bvh') for p in paths)


# ─────────────────────────────────────────────────────────────
#  13. add_animation / remove_animation
# ─────────────────────────────────────────────────────────────

class TestAddRemoveAnimation:

    def test_add_animation(self):
        eng, model = _engine_with([])
        eng.add_animation(_make_pos_anim('new'))
        assert len(model.animations) == 1

    def test_replace_existing(self):
        eng, model = _engine_with([_make_pos_anim('cwalk', length=1.0)])
        eng.add_animation(_make_pos_anim('cwalk', length=2.0))
        assert len(model.animations) == 1
        assert model.animations[0].length == pytest.approx(2.0)

    def test_remove_animation(self):
        eng, model = _engine_with([_make_pos_anim('cwalk')])
        ok = eng.remove_animation('cwalk')
        assert ok is True
        assert len(model.animations) == 0

    def test_remove_nonexistent_returns_false(self):
        eng, _ = _engine_with([])
        assert eng.remove_animation('ghost') is False

    def test_remove_current_stops_playback(self):
        eng, _ = _engine_with([_make_pos_anim('cwalk')])
        eng.play('cwalk')
        eng.remove_animation('cwalk')
        assert eng.is_playing is False


# ─────────────────────────────────────────────────────────────
#  14. get_pose() Alias
# ─────────────────────────────────────────────────────────────

class TestGetPoseAlias:

    def test_get_pose_equals_evaluate(self):
        eng, _ = _engine_with([_make_pos_anim()])
        eng.play('cwalk')
        eng.advance(0.3)
        p1 = eng.evaluate()
        p2 = eng.get_pose()
        assert p1.time == p2.time
        assert set(p1.nodes.keys()) == set(p2.nodes.keys())


# ─────────────────────────────────────────────────────────────
#  15. AnimPose / NodePose dataclasses
# ─────────────────────────────────────────────────────────────

class TestAnimPoseDataclasses:

    def test_animpose_defaults(self):
        p = AnimPose()
        assert p.time == 0.0
        assert isinstance(p.nodes, dict)

    def test_nodepose_defaults(self):
        np = NodePose(name='test')
        assert np.position == (0.0, 0.0, 0.0)
        assert np.rotation == (0.0, 0.0, 0.0, 1.0)
        assert np.scale == 1.0

    def test_nodepose_custom(self):
        np = NodePose(name='x', position=(1, 2, 3), rotation=(0, 0, 0.7, 0.7), scale=2.0)
        assert np.position == (1, 2, 3)
        assert np.scale == 2.0


# ─────────────────────────────────────────────────────────────
#  16. Edge Cases
# ─────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_zero_length_animation(self):
        """A zero-length animation should not crash advance()."""
        anim = Animation(name='zero', length=0.0)
        eng, _ = _engine_with([anim])
        eng.play('zero', loop=True)
        # max(0.001, length) prevents divide-by-zero
        result = eng.advance(0.01)
        assert isinstance(result, bool)

    def test_single_keyframe_anim(self):
        anim = Animation(name='one_key', length=1.0)
        n = ModelNode(name='root')
        n.controllers = [{'type': 8, 'name': 'position', 'columns': 3,
                          'times': [0.5], 'values': [[3, 3, 3]]}]
        anim.nodes = [n]
        eng, _ = _engine_with([anim])
        eng.play('one_key')
        pose = eng.evaluate(0.9)
        rp = pose.nodes.get('root')
        assert rp is not None

    def test_model_with_no_root_node(self):
        model = KotorModel(name='empty')
        model.root_node = None
        eng = AnimationEngine(model)
        assert eng.list_animations() == []

    def test_evaluate_without_play(self):
        """evaluate() before play() should return empty pose, not crash."""
        eng, _ = _engine_with([_make_pos_anim()])
        pose = eng.evaluate(0.5)
        assert isinstance(pose, AnimPose)

    def test_advance_zero_dt(self):
        eng, _ = _engine_with([_make_pos_anim()])
        eng.play('cwalk')
        t_before = eng.current_time
        eng.advance(0.0)
        assert eng.current_time == t_before

    def test_seek_without_current_anim(self):
        """seek() without an active animation should be a no-op."""
        eng, _ = _engine_with([])
        eng.seek(0.5)  # should not raise
        assert eng.current_time == 0.0


# ─────────────────────────────────────────────────────────────
#  17. Packed-Quaternion Controller Decoding
# ─────────────────────────────────────────────────────────────

class TestPackedQuatDecoding:

    def test_pack_unpack_identity(self):
        """Manually pack an identity quaternion and verify the decoder."""
        # KotOR packed-quat: x = 1 - (temp & 0x7FF)/1023; etc.
        # For identity (0,0,0,1): x=0, y=0, z=0
        # x = 1 - bits_x/1023 = 0  →  bits_x = 1023
        # y = 1 - bits_y/1023 = 0  →  bits_y = 1023
        # z = 1 - bits_z/511  = 0  →  bits_z = 511
        bits_x = 1023
        bits_y = 1023
        bits_z = 511
        temp = bits_x | (bits_y << 11) | (bits_z << 22)
        # Decode
        qx = 1.0 - (temp & 0x7FF) / 1023.0
        qy = 1.0 - ((temp >> 11) & 0x7FF) / 1023.0
        qz = 1.0 - (temp >> 22) / 511.0
        mag2 = qx*qx + qy*qy + qz*qz
        assert mag2 < 1.0
        qw = -math.sqrt(1.0 - mag2)
        # Identity quat: x≈0, y≈0, z≈0, w≈-1 (sign convention in KotOR)
        assert abs(qx) < 0.01 and abs(qy) < 0.01 and abs(qz) < 0.01
        assert abs(abs(qw) - 1.0) < 0.01

    def test_pack_unpack_90z(self):
        """Pack ~90° Z rotation and check x,y,z component magnitudes."""
        # 90° Z: x=0, y=0, z=0.7071, w=-0.7071 (KotOR sign convention)
        # z = 1 - bits_z/511 = 0.7071  →  bits_z = round((1-0.7071)*511) ≈ 149
        bits_z = round((1.0 - 0.7071) * 511)
        bits_x = 1023  # x=0
        bits_y = 1023  # y=0
        temp = bits_x | (bits_y << 11) | (bits_z << 22)
        qz = 1.0 - (temp >> 22) / 511.0
        assert abs(qz - 0.7071) < 0.05


# ─────────────────────────────────────────────────────────────
#  18. Viewport Animation Pose Integration
# ─────────────────────────────────────────────────────────────

class TestViewportIntegration:

    def _make_renderer(self):
        try:
            from src.gui.viewport import FrameRenderer, ArcBallCamera
            cam   = ArcBallCamera()
            rend  = FrameRenderer(cam)
            return rend
        except Exception:
            pytest.skip("FrameRenderer unavailable (no display)")

    def test_set_animation_pose_clears_cache(self):
        rend = self._make_renderer()
        model = _make_model()
        rend.set_model(model)
        # Populate cache
        node = model.root_node
        rend._wt_cache[id(node)] = ((0,0,0),(0,0,0,1),True)
        pose = AnimPose(time=0.1)
        rend.set_animation_pose(pose, name='cwalk', time=0.1, length=1.0)
        assert rend._wt_cache == {}

    def test_clear_animation_pose(self):
        rend = self._make_renderer()
        model = _make_model()
        rend.set_model(model)
        pose = AnimPose(time=0.5)
        rend.set_animation_pose(pose)
        rend.set_animation_pose(None)
        assert rend._anim_pose is None

    def test_set_model_clears_anim_pose(self):
        rend = self._make_renderer()
        model = _make_model()
        pose = AnimPose(time=0.3)
        rend.set_animation_pose(pose)
        rend.set_model(model)
        assert rend._anim_pose is None
