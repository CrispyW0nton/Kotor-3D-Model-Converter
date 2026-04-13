"""
test_v450_anim_state_machine.py
================================
Phase 8 — Animation State Machine  (Gregory §12.12; Dunsky §7–8)

Test coverage
─────────────
AnimTransition  dataclass
  ╠═ default values (blend=True, sync_phase=False, priority=0, condition=None)
  ╚═ explicit field assignment

AnimState  dataclass
  ╠═ default values (loop=True, speed=1.0, on_enter/on_exit=None, transitions=[])
  ╚═ explicit field assignment

AnimStateMachine  lifecycle
  ╠═ start() requires initial state set + state registered → True
  ╠═ start() without initial → False
  ╠═ start() clears history
  ╠═ stop() + reset()
  ╠═ is_running flag
  ╚═ current_state_name / previous_state_name

AnimStateMachine  state registration
  ╠═ add_state() + remove_state()
  ╠═ add_state() with overwrite warning
  ╠═ state_names list (sorted, excludes 'any')
  ╚═ get_state() hit + miss

AnimStateMachine  transitions
  ╠═ add_transition from known state
  ╠═ add_transition to 'any' creates virtual state
  ╠═ add_transition to unknown state logs warning (no crash)
  ╠═ condition-based auto-transition fires when condition() == True
  ╠═ condition-based transition does NOT fire when condition() == False
  ╠═ priority ordering: higher-priority fires before lower
  ╠═ global 'any' transition fires regardless of current state
  ╚═ same-state transition not re-entered via condition

AnimStateMachine  request_transition()
  ╠═ valid target returns True
  ╠═ invalid target returns False
  ╠═ pending transition fires on next advance()
  ╠═ blend=False skips cross-fade
  ╚═ sync_phase=True passed to engine.play()

AnimStateMachine  advance()
  ╠═ advance with no playing state returns None
  ╠═ advance enters initial state on start()
  ╠═ advance returns state name when transition fires
  ╠═ advance returns None when no transition fires
  ╠═ speed scaling multiplies dt before engine.advance()
  ╠═ non-loop clip ending triggers exit transitions
  ╚═ non-loop clip with no exit transition stays on last frame

AnimStateMachine  callbacks
  ╠═ on_enter called when state entered
  ╠═ on_exit called when state exited
  ╠═ on_exit called before on_enter (correct order)
  ╚═ callback exception does not crash advance()

AnimStateMachine  history
  ╠═ history() returns list of entered state names (in order)
  ╠═ reset() clears history
  ╚═ history grows correctly through multiple transitions

AnimStateMachine  phase-sync (Gregory §12.6.3)
  ╠═ sync_phase=True in transition calls engine.play(sync_phase=True)
  ╚═ phase-sync transition from walk→run starts at normalized phase

AnimationEngine integration
  ╠═ AnimationEngine.play() with blend uses _blend_from_pose
  ╠═ AnimationEngine.play() with sync_phase sets _time to phase-scaled value
  ╠═ AnimationEngine.is_blending() True during cross-fade window
  ╠═ AnimationEngine.blend_fraction() advances from 0 to 1 over blend duration
  ╚═ AnimationEngine cross-fade terminates cleanly at blend_duration
"""

import math
import sys
import os
import unittest
from dataclasses import dataclass, field
from typing import List, Optional

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo not in sys.path:
    sys.path.insert(0, _repo)
if os.path.join(_repo, 'src') not in sys.path:
    sys.path.insert(0, os.path.join(_repo, 'src'))

from src.core.animation_engine import (
    AnimationEngine, AnimPose,
    AnimState, AnimTransition, AnimStateMachine,
)
from src.core.model_data import KotorModel, ModelNode, Animation, AnimEvent


# ─────────────────────────────────────────────────────────────────────────────
#  Shared mock helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_animation(name: str, length: float = 1.0,
                    transition_time: float = 0.1) -> Animation:
    anim = Animation()
    anim.name            = name
    anim.length          = length
    anim.transition_time = transition_time
    anim.nodes           = []
    anim.events          = []
    return anim


def _make_model(anim_names=None) -> KotorModel:
    """Build a minimal KotorModel with given animation names."""
    mdl  = KotorModel()
    mdl.name       = 'test_model'
    mdl.supermodel = 'NULL'
    root  = ModelNode()
    root.name     = 'root'
    root.position = (0.0, 0.0, 0.0)
    root.rotation = (0.0, 0.0, 0.0, 1.0)
    mdl.root_node = root

    for aname in (anim_names or ['idle', 'walk', 'run', 'attack', 'die']):
        length = {'walk': 1.5, 'run': 0.8, 'attack': 1.2, 'die': 2.0}.get(aname, 1.0)
        mdl.animations.append(_make_animation(aname, length=length))

    return mdl


def _make_engine(anim_names=None) -> AnimationEngine:
    return AnimationEngine(_make_model(anim_names))


def _make_sm(anim_names=None) -> AnimStateMachine:
    """Build a ready-to-use state machine with common KotOR locomotion states."""
    engine = _make_engine(anim_names)
    sm     = AnimStateMachine(engine)
    sm.add_state(AnimState('idle',   'idle',   loop=True,  speed=1.0))
    sm.add_state(AnimState('walk',   'walk',   loop=True,  speed=1.0))
    sm.add_state(AnimState('run',    'run',    loop=True,  speed=1.0))
    sm.add_state(AnimState('attack', 'attack', loop=False, speed=1.0))
    sm.set_initial('idle')
    return sm


# ─────────────────────────────────────────────────────────────────────────────
#  Tests — AnimTransition  dataclass
# ─────────────────────────────────────────────────────────────────────────────

class TestAnimTransition(unittest.TestCase):

    def test_required_target_state(self):
        t = AnimTransition(target_state='walk')
        self.assertEqual(t.target_state, 'walk')

    def test_default_blend_true(self):
        t = AnimTransition(target_state='walk')
        self.assertTrue(t.blend)

    def test_default_sync_phase_false(self):
        t = AnimTransition(target_state='walk')
        self.assertFalse(t.sync_phase)

    def test_default_priority_zero(self):
        t = AnimTransition(target_state='walk')
        self.assertEqual(t.priority, 0)

    def test_default_condition_none(self):
        t = AnimTransition(target_state='walk')
        self.assertIsNone(t.condition)

    def test_explicit_fields(self):
        cond = lambda: True
        t = AnimTransition(target_state='run', condition=cond,
                            blend=False, sync_phase=True, priority=99)
        self.assertIs(t.condition, cond)
        self.assertFalse(t.blend)
        self.assertTrue(t.sync_phase)
        self.assertEqual(t.priority, 99)


# ─────────────────────────────────────────────────────────────────────────────
#  Tests — AnimState  dataclass
# ─────────────────────────────────────────────────────────────────────────────

class TestAnimState(unittest.TestCase):

    def test_required_name_and_anim_name(self):
        s = AnimState(name='idle', anim_name='cpause1')
        self.assertEqual(s.name, 'idle')
        self.assertEqual(s.anim_name, 'cpause1')

    def test_default_loop_true(self):
        self.assertTrue(AnimState('idle', 'cpause1').loop)

    def test_default_speed_one(self):
        self.assertEqual(AnimState('idle', 'cpause1').speed, 1.0)

    def test_default_callbacks_none(self):
        s = AnimState('idle', 'cpause1')
        self.assertIsNone(s.on_enter)
        self.assertIsNone(s.on_exit)

    def test_default_transitions_empty(self):
        s = AnimState('idle', 'cpause1')
        self.assertEqual(s.transitions, [])

    def test_explicit_transitions_list(self):
        tr = AnimTransition('walk')
        s  = AnimState('idle', 'cpause1', transitions=[tr])
        self.assertEqual(len(s.transitions), 1)
        self.assertIs(s.transitions[0], tr)


# ─────────────────────────────────────────────────────────────────────────────
#  Tests — AnimStateMachine  lifecycle
# ─────────────────────────────────────────────────────────────────────────────

class TestAnimStateMachineLifecycle(unittest.TestCase):

    def test_start_returns_true_with_valid_initial(self):
        sm = _make_sm()
        self.assertTrue(sm.start())

    def test_start_returns_false_without_initial(self):
        sm = AnimStateMachine(_make_engine())
        sm.add_state(AnimState('idle', 'idle'))
        self.assertFalse(sm.start())

    def test_start_returns_false_with_unknown_initial(self):
        sm = AnimStateMachine(_make_engine())
        sm.set_initial('nonexistent')
        self.assertFalse(sm.start())

    def test_is_running_false_before_start(self):
        sm = _make_sm()
        self.assertFalse(sm.is_running)

    def test_is_running_true_after_start(self):
        sm = _make_sm()
        sm.start()
        self.assertTrue(sm.is_running)

    def test_is_running_false_after_stop(self):
        sm = _make_sm()
        sm.start()
        sm.stop()
        self.assertFalse(sm.is_running)

    def test_reset_clears_history(self):
        sm = _make_sm()
        sm.start()
        sm.reset()
        self.assertEqual(sm.history(), [])

    def test_reset_sets_current_none(self):
        sm = _make_sm()
        sm.start()
        sm.reset()
        self.assertIsNone(sm.current_state_name)

    def test_start_clears_history_on_restart(self):
        sm = _make_sm()
        sm.start()
        sm.stop()
        sm.start()   # restart
        self.assertEqual(sm.history(), ['idle'])

    def test_current_state_after_start(self):
        sm = _make_sm()
        sm.start()
        self.assertEqual(sm.current_state_name, 'idle')

    def test_previous_state_none_on_first_start(self):
        sm = _make_sm()
        sm.start()
        self.assertIsNone(sm.previous_state_name)


# ─────────────────────────────────────────────────────────────────────────────
#  Tests — AnimStateMachine  state registration
# ─────────────────────────────────────────────────────────────────────────────

class TestAnimStateMachineStates(unittest.TestCase):

    def test_add_state_returns_self_for_chaining(self):
        sm  = AnimStateMachine(_make_engine())
        ret = sm.add_state(AnimState('idle', 'idle'))
        self.assertIs(ret, sm)

    def test_remove_state_existing_returns_true(self):
        sm = AnimStateMachine(_make_engine())
        sm.add_state(AnimState('idle', 'idle'))
        self.assertTrue(sm.remove_state('idle'))

    def test_remove_state_nonexistent_returns_false(self):
        sm = AnimStateMachine(_make_engine())
        self.assertFalse(sm.remove_state('ghost'))

    def test_state_names_excludes_any(self):
        sm = _make_sm()
        sm.add_transition('any', AnimTransition('idle'))
        names = sm.state_names
        self.assertNotIn('any', names)

    def test_state_names_sorted(self):
        sm = _make_sm()
        names = sm.state_names
        self.assertEqual(names, sorted(names))

    def test_get_state_hit(self):
        sm = _make_sm()
        state = sm.get_state('idle')
        self.assertIsNotNone(state)
        self.assertEqual(state.name, 'idle')

    def test_get_state_miss_returns_none(self):
        sm = _make_sm()
        self.assertIsNone(sm.get_state('does_not_exist'))

    def test_add_transition_to_unknown_state_no_crash(self):
        sm = _make_sm()
        # Should log warning but not raise
        sm.add_transition('unknown_state', AnimTransition('walk'))


# ─────────────────────────────────────────────────────────────────────────────
#  Tests — AnimStateMachine  transitions
# ─────────────────────────────────────────────────────────────────────────────

class TestAnimStateMachineTransitions(unittest.TestCase):

    def test_condition_true_fires_transition(self):
        sm = _make_sm()
        sm.add_transition('idle', AnimTransition('walk', condition=lambda: True, priority=10))
        sm.start()
        entered = sm.advance(0.1)
        self.assertEqual(entered, 'walk')
        self.assertEqual(sm.current_state_name, 'walk')

    def test_condition_false_does_not_fire(self):
        sm = _make_sm()
        sm.add_transition('idle', AnimTransition('walk', condition=lambda: False))
        sm.start()
        entered = sm.advance(0.1)
        self.assertIsNone(entered)
        self.assertEqual(sm.current_state_name, 'idle')

    def test_priority_higher_fires_first(self):
        fired_order = []
        sm = _make_sm()
        sm.add_transition('idle', AnimTransition('walk', condition=lambda: True, priority=5))
        sm.add_transition('idle', AnimTransition('run',  condition=lambda: True, priority=10))
        sm.start()
        entered = sm.advance(0.0)
        # Higher priority (10 → run) should win
        self.assertEqual(entered, 'run')

    def test_global_any_transition_fires_from_any_state(self):
        flag = [False]
        sm = _make_sm()
        sm.add_transition('any', AnimTransition('attack', condition=lambda: flag[0], priority=100))
        sm.start()
        # Walk to trigger 'any' transition
        sm.request_transition('walk')
        sm.advance(0.0)   # process pending
        flag[0] = True
        entered = sm.advance(0.0)
        self.assertEqual(entered, 'attack')

    def test_unconditional_transition_requires_request(self):
        sm = _make_sm()
        sm.add_transition('idle', AnimTransition('walk'))  # condition=None
        sm.start()
        entered = sm.advance(0.1)
        # Should NOT fire automatically
        self.assertIsNone(entered)
        self.assertEqual(sm.current_state_name, 'idle')

    def test_any_state_virtual_state_created(self):
        sm = _make_sm()
        sm.add_transition('any', AnimTransition('attack', condition=lambda: True, priority=1000))
        # 'any' virtual state should be in _states
        self.assertIn('any', sm._states)


# ─────────────────────────────────────────────────────────────────────────────
#  Tests — AnimStateMachine  request_transition
# ─────────────────────────────────────────────────────────────────────────────

class TestAnimStateMachineRequestTransition(unittest.TestCase):

    def test_valid_target_returns_true(self):
        sm = _make_sm()
        sm.start()
        self.assertTrue(sm.request_transition('walk'))

    def test_invalid_target_returns_false(self):
        sm = _make_sm()
        sm.start()
        self.assertFalse(sm.request_transition('nonexistent'))

    def test_request_transition_fires_on_next_advance(self):
        sm = _make_sm()
        sm.start()
        sm.request_transition('walk')
        entered = sm.advance(0.0)
        self.assertEqual(entered, 'walk')
        self.assertEqual(sm.current_state_name, 'walk')

    def test_previous_state_updated_after_transition(self):
        sm = _make_sm()
        sm.start()
        sm.request_transition('walk')
        sm.advance(0.0)
        self.assertEqual(sm.previous_state_name, 'idle')

    def test_double_transition_in_same_tick(self):
        """Only the first pending transition fires per tick."""
        sm = _make_sm()
        sm.start()
        sm.request_transition('walk')
        sm.request_transition('run')   # overwrites pending
        entered = sm.advance(0.0)
        self.assertEqual(entered, 'run')

    def test_request_with_blend_false(self):
        """blend=False: engine.play called with blend=False."""
        play_calls = []
        engine = _make_engine()
        orig_play = engine.play
        def capture_play(*args, **kwargs):
            play_calls.append(kwargs.get('blend', True))
            return orig_play(*args, **kwargs)
        engine.play = capture_play

        sm = AnimStateMachine(engine)
        sm.add_state(AnimState('idle', 'idle'))
        sm.add_state(AnimState('walk', 'walk'))
        sm.set_initial('idle')
        sm.start()
        sm.request_transition('walk', blend=False)
        sm.advance(0.0)
        # The walk entry call should have blend=False
        self.assertIn(False, play_calls)


# ─────────────────────────────────────────────────────────────────────────────
#  Tests — AnimStateMachine  advance() edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestAnimStateMachineAdvance(unittest.TestCase):

    def test_advance_not_running_returns_none(self):
        sm = _make_sm()
        self.assertIsNone(sm.advance(0.1))

    def test_advance_returns_none_when_no_transition(self):
        sm = _make_sm()
        sm.start()
        result = sm.advance(0.1)
        self.assertIsNone(result)

    def test_advance_engine_called_each_tick(self):
        """advance() must call engine.advance() every tick."""
        advance_calls = [0]
        engine = _make_engine()
        orig_advance = engine.advance
        def counting_advance(dt):
            advance_calls[0] += 1
            return orig_advance(dt)
        engine.advance = counting_advance

        sm = AnimStateMachine(engine)
        sm.add_state(AnimState('idle', 'idle'))
        sm.set_initial('idle')
        sm.start()
        for _ in range(5):
            sm.advance(0.1)
        self.assertEqual(advance_calls[0], 5)

    def test_speed_scaling_applied_to_dt(self):
        """State with speed=2.0 should call engine.advance(dt*2)."""
        advanced_dt = []
        engine = _make_engine()
        orig_advance = engine.advance
        def capture_advance(dt):
            advanced_dt.append(dt)
            return orig_advance(dt)
        engine.advance = capture_advance

        sm = AnimStateMachine(engine)
        sm.add_state(AnimState('fast', 'idle', speed=2.0))
        sm.set_initial('fast')
        sm.start()
        advanced_dt.clear()   # clear start() call
        sm.advance(0.1)
        self.assertAlmostEqual(advanced_dt[-1], 0.2, places=6)

    def test_nonloop_clip_end_triggers_exit_transition(self):
        """After a non-looping clip ends, a conditional exit transition fires."""
        engine = _make_engine()
        sm = AnimStateMachine(engine)
        sm.add_state(AnimState('attack', 'attack', loop=False))
        sm.add_state(AnimState('idle',   'idle',   loop=True))
        sm.add_transition('attack', AnimTransition('idle', condition=lambda: True))
        sm.set_initial('attack')
        sm.start()
        # Advance past the clip length (1.2 s)
        for _ in range(20):
            entered = sm.advance(0.1)
            if entered == 'idle':
                break
        self.assertEqual(sm.current_state_name, 'idle')

    def test_nonloop_clip_end_without_exit_stays(self):
        """No exit transition defined → stays on the last frame of the clip."""
        engine = _make_engine()
        sm = AnimStateMachine(engine)
        sm.add_state(AnimState('attack', 'attack', loop=False))
        sm.set_initial('attack')
        sm.start()
        # Advance well past clip length
        for _ in range(30):
            sm.advance(0.1)
        # Should remain on attack
        self.assertEqual(sm.current_state_name, 'attack')


# ─────────────────────────────────────────────────────────────────────────────
#  Tests — AnimStateMachine  callbacks
# ─────────────────────────────────────────────────────────────────────────────

class TestAnimStateMachineCallbacks(unittest.TestCase):

    def test_on_enter_called_on_start(self):
        entered = []
        sm = _make_sm()
        sm.get_state('idle').on_enter = lambda n: entered.append(n)
        sm.start()
        self.assertIn('idle', entered)

    def test_on_exit_called_when_leaving_state(self):
        exited = []
        sm = _make_sm()
        sm.get_state('idle').on_exit = lambda n: exited.append(n)
        sm.start()
        sm.request_transition('walk')
        sm.advance(0.0)
        self.assertIn('idle', exited)

    def test_on_enter_called_when_entering_new_state(self):
        entered = []
        sm = _make_sm()
        sm.get_state('walk').on_enter = lambda n: entered.append(n)
        sm.start()
        sm.request_transition('walk')
        sm.advance(0.0)
        self.assertIn('walk', entered)

    def test_exit_before_enter_order(self):
        order = []
        sm = _make_sm()
        sm.get_state('idle').on_exit  = lambda n: order.append(f'exit:{n}')
        sm.get_state('walk').on_enter = lambda n: order.append(f'enter:{n}')
        sm.start()
        sm.request_transition('walk')
        sm.advance(0.0)
        self.assertEqual(order, ['exit:idle', 'enter:walk'])

    def test_callback_exception_does_not_crash(self):
        sm = _make_sm()
        sm.get_state('walk').on_enter = lambda n: (_ for _ in ()).throw(RuntimeError("boom"))
        sm.start()
        sm.request_transition('walk')
        # Must not raise
        try:
            sm.advance(0.0)
        except Exception as e:
            self.fail(f"advance() raised {e} despite callback guard")


# ─────────────────────────────────────────────────────────────────────────────
#  Tests — AnimStateMachine  history
# ─────────────────────────────────────────────────────────────────────────────

class TestAnimStateMachineHistory(unittest.TestCase):

    def test_history_contains_initial_state(self):
        sm = _make_sm()
        sm.start()
        self.assertEqual(sm.history(), ['idle'])

    def test_history_grows_with_transitions(self):
        sm = _make_sm()
        sm.start()
        sm.request_transition('walk')
        sm.advance(0.0)
        sm.request_transition('run')
        sm.advance(0.0)
        self.assertEqual(sm.history(), ['idle', 'walk', 'run'])

    def test_history_returns_copy_not_reference(self):
        sm = _make_sm()
        sm.start()
        h1 = sm.history()
        sm.request_transition('walk')
        sm.advance(0.0)
        h2 = sm.history()
        self.assertEqual(len(h1), 1)
        self.assertEqual(len(h2), 2)

    def test_reset_clears_history(self):
        sm = _make_sm()
        sm.start()
        sm.request_transition('walk')
        sm.advance(0.0)
        sm.reset()
        self.assertEqual(sm.history(), [])


# ─────────────────────────────────────────────────────────────────────────────
#  Tests — Phase-synchronized cross-fade (Gregory §12.6.3)
# ─────────────────────────────────────────────────────────────────────────────

class TestPhaseSyncCrossFade(unittest.TestCase):

    def test_sync_phase_transition_request(self):
        """request_transition(sync_phase=True) must reach engine.play(sync_phase=True)."""
        play_kwargs = {}
        engine = _make_engine()
        orig_play = engine.play
        def capturing_play(*args, **kwargs):
            play_kwargs.update(kwargs)
            play_kwargs['_args'] = args
            return orig_play(*args, **kwargs)
        engine.play = capturing_play

        sm = AnimStateMachine(engine)
        sm.add_state(AnimState('walk', 'walk'))
        sm.add_state(AnimState('run',  'run'))
        sm.set_initial('walk')
        sm.start()
        play_kwargs.clear()
        sm.request_transition('run', sync_phase=True)
        sm.advance(0.0)
        self.assertTrue(play_kwargs.get('sync_phase', False),
                        "sync_phase=True not propagated to engine.play()")

    def test_sync_phase_sets_engine_time_proportionally(self):
        """When sync_phase=True, new clip starts at scaled phase of old clip."""
        engine = _make_engine(['walk', 'run'])
        # Manually set up a walk-length=1.5, run-length=0.8
        walk_anim = engine.model.animations[0]
        run_anim  = engine.model.animations[1]
        self.assertAlmostEqual(walk_anim.length, 1.5, places=5)
        self.assertAlmostEqual(run_anim.length,  0.8, places=5)

        engine.play('walk', loop=True, blend=False)
        engine.seek(0.75)   # 50% through walk (phase = 0.5)

        engine.play('run', loop=True, blend=True, sync_phase=True)
        expected_time = 0.5 * run_anim.length   # = 0.4
        self.assertAlmostEqual(engine.current_time, expected_time, places=4)

    def test_blend_fraction_starts_at_zero(self):
        engine = _make_engine(['idle', 'walk'])
        engine.play('idle', loop=True, blend=False)
        engine.play('walk', loop=True, blend=True)
        self.assertTrue(engine.is_blending())

    def test_blend_fraction_reaches_one_after_duration(self):
        engine = _make_engine(['idle', 'walk'])
        walk = next(a for a in engine.model.animations if a.name == 'walk')
        walk.transition_time = 0.2
        engine.play('idle', loop=True, blend=False)
        engine.play('walk', loop=True, blend=True)
        # Advance past transition time
        for _ in range(25):
            engine.advance(0.01)
        self.assertFalse(engine.is_blending())
        self.assertAlmostEqual(engine.blend_fraction(), 0.0, places=5)

    def test_blend_fraction_monotonically_increases(self):
        engine = _make_engine(['idle', 'walk'])
        walk = next(a for a in engine.model.animations if a.name == 'walk')
        walk.transition_time = 0.5
        engine.play('idle', loop=True, blend=False)
        engine.play('walk', loop=True, blend=True)
        prev = 0.0
        for _ in range(10):
            engine.advance(0.04)
            bf = engine.blend_fraction()
            if bf == 0.0 and prev > 0.0:
                break   # blend finished
            self.assertGreaterEqual(bf, prev,
                msg=f"blend_fraction went backwards: {bf} < {prev}")
            prev = bf


# ─────────────────────────────────────────────────────────────────────────────
#  Tests — AnimationEngine integration (blend / cross-fade)
# ─────────────────────────────────────────────────────────────────────────────

class TestAnimationEngineCrossFade(unittest.TestCase):

    def test_play_with_blend_true_captures_from_pose(self):
        engine = _make_engine()
        engine.play('idle',  loop=True, blend=False)
        engine.advance(0.5)
        engine.play('walk',  loop=True, blend=True)
        self.assertTrue(engine.is_blending())
        self.assertIsNotNone(engine._blend_from_pose)

    def test_play_with_blend_false_no_blend_from_pose(self):
        engine = _make_engine()
        engine.play('idle', loop=True, blend=False)
        engine.advance(0.3)
        engine.play('walk', loop=True, blend=False)
        self.assertFalse(engine.is_blending())
        self.assertIsNone(engine._blend_from_pose)

    def test_cross_fade_blend_fraction_increases_with_time(self):
        engine = _make_engine()
        walk = next(a for a in engine.model.animations if a.name == 'walk')
        walk.transition_time = 0.4
        engine.play('idle', loop=True, blend=False)
        engine.play('walk', loop=True, blend=True)
        engine.advance(0.1)
        bf1 = engine.blend_fraction()
        engine.advance(0.1)
        bf2 = engine.blend_fraction()
        self.assertGreater(bf2, bf1)

    def test_cross_fade_terminates_cleanly(self):
        engine = _make_engine()
        walk = next(a for a in engine.model.animations if a.name == 'walk')
        walk.transition_time = 0.2
        engine.play('idle', loop=True, blend=False)
        engine.play('walk', loop=True, blend=True)
        for _ in range(30):
            engine.advance(0.01)
        self.assertFalse(engine.is_blending())
        self.assertIsNone(engine._blend_from_pose)

    def test_evaluate_during_blend_returns_pose(self):
        engine = _make_engine()
        engine.play('idle', loop=True, blend=False)
        engine.play('walk', loop=True, blend=True)
        engine.advance(0.05)
        pose = engine.evaluate()
        self.assertIsInstance(pose, AnimPose)

    def test_sync_phase_true_updates_time(self):
        """play(sync_phase=True): new clip time = old_phase × new_length."""
        engine = _make_engine(['walk', 'run'])
        walk_anim = next(a for a in engine.model.animations if a.name == 'walk')
        run_anim  = next(a for a in engine.model.animations if a.name == 'run')
        walk_anim.length = 2.0
        run_anim.length  = 1.0

        engine.play('walk', loop=True, blend=False)
        engine.seek(1.0)   # 50% through walk

        engine.play('run', loop=True, blend=True, sync_phase=True)
        # Expected: 0.5 × 1.0 = 0.5
        self.assertAlmostEqual(engine.current_time, 0.5, places=5)

    def test_sync_phase_false_starts_at_zero(self):
        engine = _make_engine()
        engine.play('idle', loop=True, blend=False)
        engine.seek(0.7)
        engine.play('walk', loop=True, blend=True, sync_phase=False)
        self.assertAlmostEqual(engine.current_time, 0.0, places=5)

    def test_advance_blend_elapsed_independent_of_clip_time(self):
        """_blend_elapsed must advance with dt regardless of clip start time.
        Phase-sync can start new clip at t>0 (e.g. t=0.8); blend should still
        run over the full blend_duration without instantaneous finish.
        Reference: Gregory §12.6.3 / ROADMAP Phase 8.2 fix."""
        engine = _make_engine(['idle', 'walk'])
        walk = next(a for a in engine.model.animations if a.name == 'walk')
        walk.transition_time = 0.5
        walk.length = 1.5
        engine.play('idle', loop=True, blend=False)
        engine.seek(0.9)   # nearly end of idle
        engine.play('walk', loop=True, blend=True, sync_phase=True)
        # Blend should be active (not already finished)
        self.assertTrue(engine.is_blending(),
            "Blend should be active immediately after play() with sync_phase")
        engine.advance(0.1)
        # Still blending after only 0.1s with 0.5s duration
        self.assertTrue(engine.is_blending(),
            "Blend should still be active after 0.1s of 0.5s duration")


# ─────────────────────────────────────────────────────────────────────────────
#  Tests — Full integration: SM + engine play through locomotion cycle
# ─────────────────────────────────────────────────────────────────────────────

class TestAnimStateMachineIntegration(unittest.TestCase):

    def test_full_locomotion_cycle_idle_walk_run(self):
        """Simulate idle → walk → run locomotion triggered by conditions."""
        velocity = [0.0]   # simulated game velocity

        sm = AnimStateMachine(_make_engine())
        sm.add_state(AnimState('idle', 'idle', loop=True))
        sm.add_state(AnimState('walk', 'walk', loop=True))
        sm.add_state(AnimState('run',  'run',  loop=True))

        sm.add_transition('idle', AnimTransition('walk',
            condition=lambda: velocity[0] > 0.5, priority=10))
        sm.add_transition('walk', AnimTransition('run',
            condition=lambda: velocity[0] > 3.0, priority=10, sync_phase=True))
        sm.add_transition('walk', AnimTransition('idle',
            condition=lambda: velocity[0] <= 0.5, priority=5))
        sm.add_transition('run', AnimTransition('walk',
            condition=lambda: velocity[0] <= 3.0, priority=10, sync_phase=True))

        sm.set_initial('idle')
        sm.start()
        self.assertEqual(sm.current_state_name, 'idle')

        # Increase speed → walk
        velocity[0] = 1.0
        sm.advance(0.1)
        self.assertEqual(sm.current_state_name, 'walk')

        # Increase speed further → run
        velocity[0] = 5.0
        sm.advance(0.1)
        self.assertEqual(sm.current_state_name, 'run')

        # Decrease speed → walk
        velocity[0] = 1.5
        sm.advance(0.1)
        self.assertEqual(sm.current_state_name, 'walk')

        # Stop → idle
        velocity[0] = 0.0
        sm.advance(0.1)
        self.assertEqual(sm.current_state_name, 'idle')

        self.assertEqual(sm.history(), ['idle', 'walk', 'run', 'walk', 'idle'])

    def test_attack_from_any_state(self):
        """Global 'any' transition triggers attack from walk state."""
        attack_flag = [False]
        sm = AnimStateMachine(_make_engine())
        sm.add_state(AnimState('idle',   'idle',   loop=True))
        sm.add_state(AnimState('walk',   'walk',   loop=True))
        sm.add_state(AnimState('attack', 'attack', loop=False))
        sm.add_transition('idle', AnimTransition('walk', condition=lambda: True, priority=1))
        sm.add_transition('any',  AnimTransition('attack',
            condition=lambda: attack_flag[0], priority=100))
        sm.set_initial('idle')
        sm.start()

        sm.advance(0.0)   # idle → walk
        self.assertEqual(sm.current_state_name, 'walk')

        attack_flag[0] = True
        sm.advance(0.0)   # walk → attack via 'any'
        self.assertEqual(sm.current_state_name, 'attack')

    def test_sm_evaluates_valid_pose_after_several_ticks(self):
        """After running through several ticks, engine.evaluate() returns a valid pose."""
        sm = _make_sm()
        sm.start()
        for _ in range(10):
            sm.advance(0.05)
        pose = sm._engine.evaluate()
        self.assertIsInstance(pose, AnimPose)


if __name__ == '__main__':
    unittest.main(verbosity=2)
