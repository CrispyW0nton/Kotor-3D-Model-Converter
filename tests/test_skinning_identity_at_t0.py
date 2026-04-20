"""test_skinning_identity_at_t0.py — Phase G3 guard-rail
========================================================

Purpose
-------
Proves that when the animation's first-frame pose equals the node-hierarchy
bind pose, the bone-matrix palette entries are all identity (within
floating-point tolerance).

Why this matters
----------------
The Phase G2.5 audit flagged "skinning transform space mismatch" as a critical
bug.  The claim was that our GPU pipeline produces double-transformed vertices
because we apply ``M_skin = world_pose × inv(world_bind)`` directly without
xoreos's ``inv_base × bone_transform × base`` chain.

That claim is a **false positive**.  The math is:

    _build_vbo_data  bakes world_transform() into VBO vertex positions
                     (NODE_LOCAL nodes only) →  v_in  =  world_bind · v_local

    palette          M_skin = world_pose × inv(world_bind)

    shader           v_out = M_skin · v_in
                           = world_pose × inv(world_bind) × world_bind · v_local
                           = world_pose · v_local                (world-space)

    u_model = I      (identity), so gl_Position = proj · view · v_out

Result: algebraically identical to xoreos's local→world→bone→local chain
followed by a per-node render transform.  Different factoring, same answer.

This test encodes the invariant so a future refactor that changes
``_build_vbo_data`` or ``compute_palette`` in isolation (without touching the
other half) will break the test instead of silently breaking rendering.

Specifically at t=0 with ``anim_base_pose == bind_pose``:
    world_pose = world_bind
    → M_skin = world_bind × inv(world_bind) = I

so every palette entry must be identity.
"""
from __future__ import annotations

import math
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.core.gpu_skinning import (
    MatrixPaletteUploader,
    _mat4_identity_py,
    _mat4_to_flat_col,
)
from src.core.model_data import KotorModel, ModelNode, NodeFlags


# ─────────────────────────────────────────────────────────────────────────────
#  Test fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _build_test_model() -> KotorModel:
    """Build a minimal 3-bone chain model with known non-trivial transforms.

    Topology:  rootdummy → bone_a (pos +X) → bone_b (pos +Y, 90deg Z-rot)

    We deliberately pick transforms that:
      * exercise a non-identity parent chain (so world_bind != local_bind)
      * include a rotation (so the inverse-bind math has to invert rotation
        properly, not just translation).
    """
    root = ModelNode(name="rootdummy", flags=int(NodeFlags.HEADER))
    root.position = (0.0, 0.0, 0.0)
    root.rotation = (0.0, 0.0, 0.0, 1.0)

    bone_a = ModelNode(name="bone_a", flags=int(NodeFlags.HEADER))
    bone_a.position = (1.0, 0.0, 0.0)
    bone_a.rotation = (0.0, 0.0, 0.0, 1.0)
    bone_a.parent = root
    root.children.append(bone_a)

    bone_b = ModelNode(name="bone_b", flags=int(NodeFlags.HEADER))
    bone_b.position = (0.0, 2.0, 0.0)
    # 90-degree rotation about Z: quat = (0, 0, sin(45deg), cos(45deg))
    s = math.sin(math.pi / 4.0)
    c = math.cos(math.pi / 4.0)
    bone_b.rotation = (0.0, 0.0, s, c)
    bone_b.parent = bone_a
    bone_a.children.append(bone_b)

    model = KotorModel(name="test_skeleton")
    model.root_node = root
    return model


class _FakeNodePose:
    """Mimics ``AnimPose.nodes[name]`` — the animation engine's per-node output.

    ``MatrixPaletteUploader`` reads ``position`` and ``rotation`` attributes; no
    other state is needed for palette computation.
    """
    __slots__ = ("position", "rotation")

    def __init__(self, position, rotation):
        self.position = position
        self.rotation = rotation


class _FakeAnimPose:
    """Mimics ``AnimPose`` — just the ``nodes`` dict is consulted."""
    __slots__ = ("nodes",)

    def __init__(self, nodes_dict):
        self.nodes = nodes_dict


def _bind_pose_from_model(model: KotorModel) -> _FakeAnimPose:
    """Build an AnimPose-like object that mirrors the model's bind pose.

    Every node's pose (position, rotation) is copied verbatim from the
    ModelNode's static bind transform.  Feeding this into
    ``compute_palette`` as both ``anim_pose`` and ``anim_base_pose`` means
    ``world_pose == world_bind`` for every bone, so the palette must be
    identity.
    """
    nodes_dict = {}
    for node in model.all_nodes():
        nodes_dict[node.name] = _FakeNodePose(node.position, node.rotation)
    return _FakeAnimPose(nodes_dict)


# ─────────────────────────────────────────────────────────────────────────────
#  Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSkinningIdentityAtT0(unittest.TestCase):
    """Guard-rail for the VBO-bake / palette-compute coupling."""

    PLACES = 5  # 1e-5 float tolerance — palette math uses row-major doubles

    def _assert_flat_is_identity(self, flat, bone_name: str) -> None:
        """Compare a 16-element column-major flat mat4 against identity."""
        expected = _mat4_to_flat_col(_mat4_identity_py())
        for i in range(16):
            self.assertAlmostEqual(
                flat[i], expected[i], places=self.PLACES,
                msg=(
                    f"Bone '{bone_name}' palette matrix[{i}] = {flat[i]!r}, "
                    f"expected {expected[i]!r}.  This means the coupling "
                    f"between _build_vbo_data (vertex pre-bake) and "
                    f"compute_palette (world_pose × inv_bind) has drifted — "
                    f"one of them changed without the other being updated."
                ),
            )

    def test_palette_is_identity_when_pose_equals_bind(self):
        """Animation pose == bind pose → every palette matrix is identity.

        This is the canonical t=0 invariant: at frame zero of a non-trivial
        animation, the pose coincides with the rest pose, and the LBS output
        must reproduce the bind pose exactly.
        """
        model = _build_test_model()
        uploader = MatrixPaletteUploader(max_bones=128)
        uploader.build_inverse_bind_pose(model)

        pose_is_bind = _bind_pose_from_model(model)

        uploader.set_bind_pose_from_anim(pose_is_bind)
        palette = uploader.compute_palette(pose_is_bind)

        self.assertGreater(len(palette), 0,
                           "palette must contain at least one bone")
        for bm in palette:
            self._assert_flat_is_identity(bm.flat_col, bm.bone_name)

    def test_palette_is_identity_static_bind_when_anim_is_none(self):
        """With no animation (``anim_pose=None``), palette is identity.

        This is the simpler path — the early-return branch of
        ``compute_palette`` that emits an identity matrix per bone.  It's the
        steady state when the viewport is idle or the model has no animations.
        """
        model = _build_test_model()
        uploader = MatrixPaletteUploader(max_bones=128)
        uploader.build_inverse_bind_pose(model)

        palette = uploader.compute_palette(None)

        self.assertGreater(len(palette), 0)
        for bm in palette:
            self._assert_flat_is_identity(bm.flat_col, bm.bone_name)

    def test_palette_identity_via_anim_base_pose_kwarg(self):
        """Passing ``anim_base_pose`` rebuilds bind on-the-fly; result is still I.

        Exercises the ``compute_palette(anim, anim_base_pose=base)`` integration
        path (the simplest for callers that don't track bind state themselves).
        """
        model = _build_test_model()
        uploader = MatrixPaletteUploader(max_bones=128)
        uploader.build_inverse_bind_pose(model)

        pose_is_bind = _bind_pose_from_model(model)

        palette = uploader.compute_palette(pose_is_bind,
                                           anim_base_pose=pose_is_bind)

        self.assertGreater(len(palette), 0)
        for bm in palette:
            self._assert_flat_is_identity(bm.flat_col, bm.bone_name)


if __name__ == "__main__":
    unittest.main()
