"""test_supermodel_chain.py
==========================
Phase 5 unit tests for the super-model animation chain resolver.

Scenarios covered:

1. ``test_resolve_local_animation``       — own animation returned, scale = 1.0.
2. ``test_resolve_inherited_animation``   — animation fetched from supermodel,
                                             scale equals model.anim_scale.
3. ``test_chain_override``                — local name wins over supermodel's.
4. ``test_cycle_detection``               — A→B→A does not recurse forever.
5. ``test_cumulative_scale``              — chain scales multiply.
6. ``test_position_delta_scaled``         — AnimationEngine applies
                                             _current_anim_scale to POSITION deltas.
7. ``test_list_all_animations``           — full chain listing with override
                                             precedence and source attribution.

Plus a bonus regression that verifies the resolver caches repeated
supermodel lookups so we do not hit disk twice for the same chain.

Run from the repo root:
    python -m unittest test_supermodel_chain.py -v
"""

from __future__ import annotations

import sys
import os
import math
import unittest
from typing import Dict, List, Optional

# Keep the import path self-sufficient so the test runs both from the repo
# root (``python -m unittest test_supermodel_chain.py``) and from Cursor /
# IDE runners that may invoke it with a different CWD.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from src.core.model_data import Animation, KotorModel, ModelNode, NodeFlags
from src.core.animation_engine import AnimationEngine, SuperModelResolver


# ────────────────────────────────────────────────────────────────────────
#  Test fixtures
# ────────────────────────────────────────────────────────────────────────

def _make_anim(name: str,
               length: float = 1.0,
               pos_delta: Optional[List[float]] = None,
               node_name: str = "root") -> Animation:
    """Build a minimal animation with one POSITION keyframe on ``node_name``.

    Controllers are dicts matching the engine's expected shape:
        {'type': int, 'times': [floats], 'values': [ [floats], ... ]}
    """
    node = ModelNode(name=node_name, flags=int(NodeFlags.HEADER))
    if pos_delta is not None:
        node.controllers.append({
            'type':   AnimationEngine.CTRL_POSITION,
            'times':  [0.0],
            'values': [list(pos_delta)],
        })
    return Animation(name=name, length=length, nodes=[node])


def _make_model(name: str,
                supermodel: str = "NULL",
                anim_scale: float = 1.0,
                animations: Optional[List[Animation]] = None,
                bind_pos: tuple = (0.0, 0.0, 0.0),
                root_name: str = "root") -> KotorModel:
    """Build a minimal KotorModel with a single root node at ``bind_pos``."""
    root = ModelNode(name=root_name, flags=int(NodeFlags.HEADER),
                     position=bind_pos)
    model = KotorModel(
        name=name,
        supermodel=supermodel,
        anim_scale=anim_scale,
        root_node=root,
        animations=list(animations or []),
    )
    return model


class _StubResourceManager:
    """Stand-in ``ResourceManager`` that serves in-memory models.

    Tracks how many times ``load_model`` was called per resref so the cache
    behaviour test can assert the resolver is not hitting us twice.
    """

    def __init__(self, models: Dict[str, KotorModel]):
        self._models = {k.lower(): v for k, v in models.items()}
        self.calls: Dict[str, int] = {}

    def load_model(self, name: str, game: str = 'K1') -> Optional[KotorModel]:
        key = name.lower()
        self.calls[key] = self.calls.get(key, 0) + 1
        return self._models.get(key)


# ────────────────────────────────────────────────────────────────────────
#  Resolver unit tests
# ────────────────────────────────────────────────────────────────────────

class SuperModelResolverTests(unittest.TestCase):

    def setUp(self):
        # Each test starts from a clean cache and no installed RM.
        SuperModelResolver.clear_cache()
        SuperModelResolver.configure(None)

    def tearDown(self):
        SuperModelResolver.clear_cache()
        SuperModelResolver.configure(None)

    # 1. Local animation ─────────────────────────────────────────────
    def test_resolve_local_animation(self):
        walk = _make_anim("walk")
        model = _make_model("hero", supermodel="NULL", anim_scale=0.9,
                            animations=[walk])

        anim, scale = SuperModelResolver.resolve_animation(model, "walk")
        self.assertIs(anim, walk,
                      "Local animation must be returned unchanged")
        self.assertEqual(
            scale, 1.0,
            "Own animations always play at scale 1.0, even when "
            "model.anim_scale != 1.0 (xoreos rule).",
        )

    # 2. Inherited animation ─────────────────────────────────────────
    def test_resolve_inherited_animation(self):
        walk_in_b = _make_anim("walk")
        model_b = _make_model("B", supermodel="NULL", animations=[walk_in_b])
        model_a = _make_model("A", supermodel="B", anim_scale=0.9,
                              animations=[])

        SuperModelResolver.configure(_StubResourceManager({"B": model_b}))

        anim, scale = SuperModelResolver.resolve_animation(model_a, "walk")
        self.assertIs(anim, walk_in_b)
        self.assertAlmostEqual(
            scale, 0.9, places=6,
            msg="Inherited animation must be scaled by A.anim_scale",
        )

    # 3. Override precedence ────────────────────────────────────────
    def test_chain_override(self):
        walk_a = _make_anim("walk")
        walk_b = _make_anim("walk")       # same name — should be shadowed
        run_b  = _make_anim("run")
        model_b = _make_model("B", supermodel="NULL",
                              animations=[walk_b, run_b])
        model_a = _make_model("A", supermodel="B", anim_scale=0.7,
                              animations=[walk_a])

        SuperModelResolver.configure(_StubResourceManager({"B": model_b}))

        anim_walk, scale_walk = SuperModelResolver.resolve_animation(
            model_a, "walk")
        self.assertIs(anim_walk, walk_a,
                      "Model A's own 'walk' must win over supermodel B's")
        self.assertEqual(scale_walk, 1.0,
                         "Own animation never receives anim_scale")

        anim_run, scale_run = SuperModelResolver.resolve_animation(
            model_a, "run")
        self.assertIs(anim_run, run_b)
        self.assertAlmostEqual(scale_run, 0.7, places=6,
                               msg="Inherited 'run' must use A.anim_scale")

    # 4. Cycle detection ────────────────────────────────────────────
    def test_cycle_detection(self):
        model_a = _make_model("A", supermodel="B", anim_scale=0.9,
                              animations=[])
        model_b = _make_model("B", supermodel="A", anim_scale=0.8,
                              animations=[])
        SuperModelResolver.configure(_StubResourceManager({
            "A": model_a, "B": model_b,
        }))

        anim, scale = SuperModelResolver.resolve_animation(model_a, "walk")
        self.assertIsNone(anim, "Cyclic chain must not raise or infinite-loop")
        self.assertEqual(scale, 1.0)

    # 5. Cumulative scale across chain ──────────────────────────────
    def test_cumulative_scale(self):
        walk_in_c = _make_anim("walk")
        model_c = _make_model("C", supermodel="NULL", anim_scale=0.5,
                              animations=[walk_in_c])
        model_b = _make_model("B", supermodel="C", anim_scale=0.8,
                              animations=[])
        model_a = _make_model("A", supermodel="B", anim_scale=0.9,
                              animations=[])
        SuperModelResolver.configure(_StubResourceManager({
            "B": model_b, "C": model_c,
        }))

        anim, scale = SuperModelResolver.resolve_animation(model_a, "walk")
        self.assertIs(anim, walk_in_c)
        # A (0.9) contributes first step, then B (0.8), owner C is not
        # multiplied in (own animations play at natural rate).
        expected = 0.9 * 0.8
        self.assertAlmostEqual(
            scale, expected, places=6,
            msg=f"Cumulative scale must equal 0.9 * 0.8 = {expected}",
        )

    # 6. Position delta scaling through the engine ──────────────────
    def test_position_delta_scaled(self):
        # Supermodel B holds the animation; A inherits it with anim_scale=0.5.
        bind = (2.0, 3.0, 4.0)
        anim = _make_anim("walk", length=1.0, pos_delta=[1.0, 0.0, 0.0],
                          node_name="root")
        model_b = _make_model("B", supermodel="NULL",
                              animations=[anim], bind_pos=bind)
        model_a = _make_model("A", supermodel="B", anim_scale=0.5,
                              animations=[], bind_pos=bind)

        SuperModelResolver.configure(_StubResourceManager({"B": model_b}))

        engine = AnimationEngine(model_a)
        self.assertTrue(engine.play("walk", loop=False, blend=False))
        pose = engine.evaluate(0.0)

        self.assertIsNotNone(pose)
        # AnimPose.nodes is ``Dict[str, NodePose]`` keyed by lower-case name.
        root_pose = pose.nodes.get("root") or pose.nodes.get("Root")
        self.assertIsNotNone(root_pose, f"pose keys: {list(pose.nodes)}")
        # Expected: bind + anim_scale * delta  = (2+0.5, 3, 4)
        self.assertAlmostEqual(root_pose.position[0], 2.5, places=5)
        self.assertAlmostEqual(root_pose.position[1], 3.0, places=5)
        self.assertAlmostEqual(root_pose.position[2], 4.0, places=5)

        # And for comparison: when the animation is local we must NOT scale.
        model_local = _make_model(
            "Solo", supermodel="NULL", anim_scale=0.5,
            animations=[_make_anim("walk", 1.0, [1.0, 0.0, 0.0], "root")],
            bind_pos=bind,
        )
        local_engine = AnimationEngine(model_local)
        self.assertTrue(local_engine.play("walk", loop=False, blend=False))
        local_pose = local_engine.evaluate(0.0)
        root_local = local_pose.nodes.get("root") or local_pose.nodes.get("Root")
        self.assertIsNotNone(root_local)
        self.assertAlmostEqual(
            root_local.position[0], 3.0, places=5,
            msg="Own animation must apply full delta (no scale)",
        )

    # 7. list_all_animations enumeration ────────────────────────────
    def test_list_all_animations(self):
        walk_a = _make_anim("walk")
        walk_b = _make_anim("walk")   # shadowed
        run_b  = _make_anim("run")
        idle_c = _make_anim("idle")

        model_c = _make_model("C", supermodel="NULL", anim_scale=0.5,
                              animations=[idle_c])
        model_b = _make_model("B", supermodel="C", anim_scale=0.8,
                              animations=[walk_b, run_b])
        model_a = _make_model("A", supermodel="B", anim_scale=0.9,
                              animations=[walk_a])

        SuperModelResolver.configure(_StubResourceManager({
            "B": model_b, "C": model_c,
        }))

        entries = SuperModelResolver.list_all_animations(model_a)
        names = [name for name, _src, _scale in entries]
        self.assertEqual(names, ["idle", "run", "walk"],
                         "Must be sorted and de-duplicated by lower-case name")

        by_name = {name: (src, scale) for name, src, scale in entries}

        # own 'walk' — source is A, scale 1.0
        src, scale = by_name["walk"]
        self.assertEqual(src, "A")
        self.assertEqual(scale, 1.0)

        # inherited 'run' from B — scale = A.anim_scale
        src, scale = by_name["run"]
        self.assertEqual(src, "B")
        self.assertAlmostEqual(scale, 0.9, places=6)

        # inherited 'idle' from C — scale = A.anim_scale * B.anim_scale
        src, scale = by_name["idle"]
        self.assertEqual(src, "C")
        self.assertAlmostEqual(scale, 0.9 * 0.8, places=6)


# ────────────────────────────────────────────────────────────────────────
#  Cache regression
# ────────────────────────────────────────────────────────────────────────

class SuperModelResolverCacheTests(unittest.TestCase):

    def setUp(self):
        SuperModelResolver.clear_cache()

    def tearDown(self):
        SuperModelResolver.clear_cache()
        SuperModelResolver.configure(None)

    def test_cache_prevents_duplicate_loads(self):
        walk = _make_anim("walk")
        model_b = _make_model("B", supermodel="NULL", animations=[walk])
        model_a = _make_model("A", supermodel="B", anim_scale=0.9)

        rm = _StubResourceManager({"B": model_b})
        SuperModelResolver.configure(rm)

        # Three identical resolutions should only cause ONE underlying load.
        for _ in range(3):
            SuperModelResolver.resolve_animation(model_a, "walk")
        self.assertEqual(
            rm.calls.get("b", 0), 1,
            "Resolver cache must collapse repeated chain loads "
            "(matches xoreos ModelCache behaviour).",
        )


# ────────────────────────────────────────────────────────────────────────
#  AnimationEngine integration
# ────────────────────────────────────────────────────────────────────────

class AnimationEngineChainTests(unittest.TestCase):

    def setUp(self):
        SuperModelResolver.clear_cache()

    def tearDown(self):
        SuperModelResolver.clear_cache()
        SuperModelResolver.configure(None)

    def test_engine_find_anim_walks_chain(self):
        walk = _make_anim("walk")
        model_b = _make_model("B", supermodel="NULL", animations=[walk])
        model_a = _make_model("A", supermodel="B", anim_scale=0.9)

        SuperModelResolver.configure(_StubResourceManager({"B": model_b}))

        engine = AnimationEngine(model_a)
        self.assertTrue(engine.play("walk", blend=False, loop=False))
        self.assertIs(engine.current_animation, walk)
        self.assertAlmostEqual(engine._current_anim_scale, 0.9, places=6)

    def test_engine_list_all_includes_supermodel(self):
        walk = _make_anim("walk")
        model_b = _make_model("B", supermodel="NULL", animations=[walk])
        model_a = _make_model("A", supermodel="B", anim_scale=0.9)

        SuperModelResolver.configure(_StubResourceManager({"B": model_b}))

        engine = AnimationEngine(model_a)
        entries = engine.list_all_animations()
        names = sorted(e['name'] for e in entries)
        self.assertEqual(names, ["walk"])
        row = entries[0]
        self.assertTrue(row['inherited'])
        self.assertEqual(row['source'], "B")
        self.assertAlmostEqual(row['anim_scale'], 0.9, places=6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
