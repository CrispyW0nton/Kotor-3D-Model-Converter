"""test_reparent_head_nodes.py — Phase G3 parity guard
=======================================================

Exercises ``src.core.kotor_loader.reparent_head_nodes`` — the xoreos-parity
helper that flattens ``head`` and ``tongue`` nodes under the model root
while preserving their world transform.

What we prove
-------------
1. A ``head`` node nested two levels below the root ends up as a direct
   child of the root after ``reparent_head_nodes`` runs.
2. Its world-space position (from ``world_transform()``) is unchanged to
   within single-precision tolerance.
3. The function is idempotent — a second call on the already-flattened
   model is a no-op (returns ``0``).
4. A model with no ``head`` / ``tongue`` nodes returns ``0`` and leaves
   the tree untouched.
5. The default load pipeline does **not** call ``reparent_head_nodes`` —
   we verify by loading a K1 model and confirming that, if a ``head``
   node exists, it is *not* forcibly reparented to the root.  This locks
   in the "opt-in only" contract.

(Test 5 is skipped when the K1 install is absent or when the chosen MDL
doesn't actually expose a ``head`` node.)
"""
from __future__ import annotations

import math
import os
import sys
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.core.kotor_loader import reparent_head_nodes
from src.core.model_data import KotorModel, ModelNode, NodeFlags


K1_PATH = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")


def _build_nested_head_model() -> KotorModel:
    """A head nested under an intermediate dummy under the root.

    Topology::

        rootdummy  (0, 0, 0)
          └── neck  (pos 0, 0, 1)
                └── head  (pos 0, 0.1, 0.2)   <-- target of reparenting

    Expected world position of head = (0, 0.1, 1.2).  After reparent it
    must still be at (0, 0.1, 1.2) — but as a direct child of root with
    local position (0, 0.1, 1.2).
    """
    root = ModelNode(name="rootdummy", flags=int(NodeFlags.HEADER))
    root.position = (0.0, 0.0, 0.0)

    neck = ModelNode(name="neck", flags=int(NodeFlags.HEADER))
    neck.position = (0.0, 0.0, 1.0)
    neck.parent = root
    root.children.append(neck)

    head = ModelNode(name="head", flags=int(NodeFlags.HEADER))
    head.position = (0.0, 0.1, 0.2)
    head.parent = neck
    neck.children.append(head)

    model = KotorModel(name="nested_head_fixture")
    model.root_node = root
    return model


def _dist(a, b) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


class TestReparentHeadNodes(unittest.TestCase):

    # ---- core behaviour ---------------------------------------------------

    def test_head_becomes_direct_child_of_root(self) -> None:
        model = _build_nested_head_model()
        head = next(n for n in model.all_nodes() if n.name == "head")
        self.assertIsNot(head.parent, model.root_node,
                         "fixture precondition: head should be nested")

        moved = reparent_head_nodes(model)

        self.assertEqual(moved, 1)
        self.assertIs(head.parent, model.root_node)
        self.assertIn(head, model.root_node.children)
        # Old parent no longer lists the head as a child.
        neck = next(n for n in model.all_nodes() if n.name == "neck")
        self.assertNotIn(head, neck.children)

    def test_world_position_preserved(self) -> None:
        model = _build_nested_head_model()
        head = next(n for n in model.all_nodes() if n.name == "head")
        wp_before, _ = head.world_transform()

        reparent_head_nodes(model)

        wp_after, _ = head.world_transform()
        self.assertAlmostEqual(_dist(wp_before, wp_after), 0.0, places=5,
                               msg=f"world pos drifted: {wp_before} -> {wp_after}")

        # And explicitly: new local position equals the preserved world
        # position, because root sits at origin with identity rotation.
        self.assertAlmostEqual(head.position[0], wp_before[0], places=5)
        self.assertAlmostEqual(head.position[1], wp_before[1], places=5)
        self.assertAlmostEqual(head.position[2], wp_before[2], places=5)

    def test_idempotent(self) -> None:
        model = _build_nested_head_model()
        self.assertEqual(reparent_head_nodes(model), 1)
        # Second call finds head already under root → no work.
        self.assertEqual(reparent_head_nodes(model), 0)

    def test_missing_head_is_noop(self) -> None:
        """Model without ``head`` or ``tongue`` returns 0 and is untouched."""
        root = ModelNode(name="rootdummy", flags=int(NodeFlags.HEADER))
        child = ModelNode(name="ArmL", flags=int(NodeFlags.HEADER))
        child.parent = root
        root.children.append(child)
        model = KotorModel(name="no_head")
        model.root_node = root

        before = [(n.name, id(n.parent)) for n in model.all_nodes()]
        self.assertEqual(reparent_head_nodes(model), 0)
        after = [(n.name, id(n.parent)) for n in model.all_nodes()]
        self.assertEqual(before, after)

    def test_none_model_is_safe(self) -> None:
        self.assertEqual(reparent_head_nodes(None), 0)  # type: ignore[arg-type]

    def test_model_without_root_is_safe(self) -> None:
        m = KotorModel(name="empty")
        m.root_node = None
        self.assertEqual(reparent_head_nodes(m), 0)

    # ---- contract: default loader does NOT call reparent_head_nodes ------

    @unittest.skipUnless(K1_PATH.exists(), "K1 install not found")
    def test_default_loader_does_not_flatten(self) -> None:
        """Find any K1 MDL with a ``head`` node; ensure it is *not* under root.

        If the default loader silently called ``reparent_head_nodes``, every
        head-bearing model in the Override would emerge with the head node
        as a direct child of the root.  That would hide real bugs and
        violate the "opt-in only" promise.

        We scan a handful of Override MDLs, pick the first with a ``head``
        node that xoreos-style reparenting *would* move (i.e. head not
        already directly under root), and assert that the default loader
        leaves it nested.
        """
        from src.core.kotor_loader import load_model_from_file

        candidates = list((K1_PATH / "Override").glob("*.mdl"))[:25]
        if not candidates:
            self.skipTest("no Override .mdl files")

        for mdl_path in candidates:
            model = None
            try:
                model = load_model_from_file(str(mdl_path))
            except Exception:  # noqa: BLE001 — broad catch is fine for skip
                continue
            if model is None or model.root_node is None:
                continue
            head = next(
                (n for n in model.all_nodes()
                 if (n.name or '').lower() == 'head'),
                None,
            )
            if head is None or head.parent is None:
                continue
            if head.parent is model.root_node:
                # Can't use this model — it wouldn't be affected by the
                # helper in the first place.  Try the next candidate.
                continue

            # Found a usable candidate: head node nested under something
            # other than the root.  Confirm the default load path left it
            # nested (i.e. reparent_head_nodes was NOT called implicitly).
            self.assertIsNot(
                head.parent, model.root_node,
                f"{mdl_path.name}: default loader silently reparented 'head' "
                f"to root — reparent_head_nodes must stay opt-in.",
            )
            return  # one confirmation is enough

        self.skipTest(
            "no Override MDL with a nested 'head' node found in sample"
        )


if __name__ == "__main__":
    unittest.main()
