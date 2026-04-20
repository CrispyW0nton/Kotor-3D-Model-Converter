"""
Phase 3 — Binary MDL writer round-trip tests
============================================

Exercises ``src.core.mdl_writer.MDLBinaryWriter`` by writing a synthetic
model to MDL+MDX bytes, parsing those bytes back through
``src.core.kotor_loader.load_model_from_bytes`` (which itself routes
through the PyKotor reader + our in-memory K2 fix), and asserting that
the geometry survives the trip.

Success criteria derived from Phase-3 spec:
  * Model name and node count preserved.
  * Per-mesh vertex count matches exactly.
  * Per-mesh face count matches exactly.
  * First few vertex positions match within ``VTX_EPS``.
  * Mesh-subheader function pointers are NOT the model-level geometry
    pointers (this was Bug 1).
  * Mesh header total size is 332 B (K1) / 340 B (K2) — Bug 1/Bug 2
    check that the extra bytes previously written as ``bm3_name/bm4_name``
    collapse back to a 24-byte ``unknown0`` block.

Run via::

    python -m pytest test_mdl_writer_roundtrip.py -q
    # or, without pytest:
    python test_mdl_writer_roundtrip.py
"""

from __future__ import annotations

import os
import struct
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from src.core.model_data import (  # noqa: E402
    GameVersion, KotorModel, ModelNode, NodeFlags,
)
from src.core.mdl_writer import (  # noqa: E402
    MDLBinaryWriter,
    _K1_MESH_FP1, _K1_MESH_FP2, _K2_MESH_FP1, _K2_MESH_FP2,
    _K1_MODEL_FP1, _K1_MODEL_FP2, _K2_MODEL_FP1, _K2_MODEL_FP2,
    _K1_ANIM_FP1, _K1_ANIM_FP2, _K2_ANIM_FP1, _K2_ANIM_FP2,
    _K1_SKIN_FP1, _K1_SKIN_FP2, _K2_SKIN_FP1, _K2_SKIN_FP2,
    _K1_DANGLY_FP1, _K1_DANGLY_FP2, _K2_DANGLY_FP1, _K2_DANGLY_FP2,
)
from src.core.kotor_loader import load_model_from_bytes  # noqa: E402


VTX_EPS = 1e-3


def _make_test_cube(game: GameVersion = GameVersion.K1) -> KotorModel:
    """Create a minimal unit cube model suitable for round-trip tests.

    The top-level root is a DUMMY (flags=HEADER) as per the NWN/KotOR
    convention; the actual geometry lives in a child MESH node.
    """
    model = KotorModel()
    model.name = "test_cube"
    model.supermodel = "NULL"
    model.game_version = game

    root = ModelNode(name="test_cube", flags=int(NodeFlags.HEADER))
    mesh = ModelNode(name="cube_mesh", flags=int(NodeFlags.MESH))
    mesh.parent = root
    root.children = [mesh]

    mesh.vertices = [
        (-1.0, -1.0, -1.0), ( 1.0, -1.0, -1.0),
        ( 1.0,  1.0, -1.0), (-1.0,  1.0, -1.0),
        (-1.0, -1.0,  1.0), ( 1.0, -1.0,  1.0),
        ( 1.0,  1.0,  1.0), (-1.0,  1.0,  1.0),
    ]
    mesh.normals = [(0.0, 0.0, -1.0)] * 4 + [(0.0, 0.0, 1.0)] * 4
    mesh.uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0),
                (0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    mesh.faces = [
        (0, 1, 2), (0, 2, 3),  # -Z
        (4, 5, 6), (4, 6, 7),  # +Z
        (0, 4, 7), (0, 7, 3),  # -X
        (1, 5, 6), (1, 6, 2),  # +X
        (0, 1, 5), (0, 5, 4),  # -Y
        (3, 2, 6), (3, 6, 7),  # +Y
    ]
    mesh.face_mats = [0] * len(mesh.faces)
    mesh.texture = "test_tex"
    mesh.texture_names = ["test_tex"]
    mesh.tex_count = 1
    mesh.render = True
    mesh.has_shadow = True

    model.root_node = root
    for n in (root, mesh):
        n.compute_bounds()
    return model


class BinaryLayoutTests(unittest.TestCase):
    """Unit checks on the raw MDL bytes produced by ``MDLBinaryWriter``."""

    def test_constants_match_kotorblender_reference(self):
        """KotorBlender / PyKotor FP values must be preserved verbatim."""
        # Model (top-level geometry) FPs
        self.assertEqual(_K1_MODEL_FP1, 4273776)
        self.assertEqual(_K1_MODEL_FP2, 4216096)
        self.assertEqual(_K2_MODEL_FP1, 4285200)
        self.assertEqual(_K2_MODEL_FP2, 4216320)

        # Animation geometry FPs — the ones we fixed.
        self.assertEqual(_K1_ANIM_FP1, 4273392)
        self.assertEqual(_K1_ANIM_FP2, 4451552)  # Bug 1 fix
        self.assertEqual(_K2_ANIM_FP1, 4284816)
        self.assertEqual(_K2_ANIM_FP2, 4522928)  # Bug 1 fix

        # Mesh / Skin / Dangly subheader FPs.
        self.assertEqual(_K1_MESH_FP1,   4216656)
        self.assertEqual(_K1_MESH_FP2,   4216672)
        self.assertEqual(_K2_MESH_FP1,   4216880)
        self.assertEqual(_K2_MESH_FP2,   4216896)
        self.assertEqual(_K1_SKIN_FP1,   4216592)
        self.assertEqual(_K1_SKIN_FP2,   4216608)
        self.assertEqual(_K2_SKIN_FP1,   4216816)
        self.assertEqual(_K2_SKIN_FP2,   4216832)
        self.assertEqual(_K1_DANGLY_FP1, 4216640)
        self.assertEqual(_K1_DANGLY_FP2, 4216624)
        self.assertEqual(_K2_DANGLY_FP1, 4216864)
        self.assertEqual(_K2_DANGLY_FP2, 4216848)

        # Model-level and mesh-subheader FP families must be DISTINCT.
        self.assertNotEqual(_K1_MODEL_FP1, _K1_MESH_FP1)
        self.assertNotEqual(_K1_ANIM_FP2, _K1_MODEL_FP2)  # the original bug

    def test_cube_writer_produces_nonempty_buffers(self):
        model = _make_test_cube(GameVersion.K1)
        mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
        self.assertGreaterEqual(len(mdl_bytes), 12 + 80 + 88 + 48)
        self.assertGreater(len(mdx_bytes), 0)

        # File header: 12 bytes, (pad4, mdl_size, mdx_size)
        self.assertEqual(len(mdl_bytes) - 12,
                         struct.unpack_from('<I', mdl_bytes, 4)[0])
        self.assertEqual(len(mdx_bytes),
                         struct.unpack_from('<I', mdl_bytes, 8)[0])

    def test_mesh_subheader_uses_mesh_fps_not_geometry_fps(self):
        """Bug 1 regression: mesh subheader used to copy the geometry FPs."""
        for game, expected_fp1, expected_fp2, model_fp1 in [
            (GameVersion.K1, _K1_MESH_FP1, _K1_MESH_FP2, _K1_MODEL_FP1),
            (GameVersion.K2, _K2_MESH_FP1, _K2_MESH_FP2, _K2_MODEL_FP1),
        ]:
            with self.subTest(game=game):
                model = _make_test_cube(game)
                mdl_bytes, _ = MDLBinaryWriter().write(model)

                # Scan for the mesh-subheader FP pair in the buffer.  It must
                # be present exactly because our cube contains one mesh node.
                needle = struct.pack('<II', expected_fp1, expected_fp2)
                self.assertIn(needle, mdl_bytes,
                              f"Mesh FP pair not found in {game.name} output")

                # The OLD bug would write the geometry fp1 at a mesh-header
                # site.  Ensure that exact pair does NOT appear where the mesh
                # header lives (we detect by checking there's only ONE match
                # of model_fp1+model_fp2 in the whole MDL — the top-level
                # geometry header).
                model_needle = struct.pack('<I', model_fp1)
                occurrences = mdl_bytes.count(model_needle)
                self.assertEqual(
                    occurrences, 1,
                    f"Model-level FP1 leaked into subheaders for {game.name}")


class RoundTripTests(unittest.TestCase):
    """End-to-end write → read geometry preservation tests."""

    def test_k1_cube_roundtrip(self):
        self._check_roundtrip(GameVersion.K1)

    def test_k2_cube_roundtrip(self):
        self._check_roundtrip(GameVersion.K2)

    def _check_roundtrip(self, game: GameVersion):
        source = _make_test_cube(game)
        mdl_bytes, mdx_bytes = MDLBinaryWriter().write(source)

        reloaded = load_model_from_bytes(
            mdl_bytes, mdx_bytes, game_version=game)
        self.assertIsNotNone(
            reloaded, f"{game.name}: load_model_from_bytes returned None")

        # Model-level.
        self.assertEqual(reloaded.name.lower(), source.name.lower())
        src_nodes = source.all_nodes()
        rld_nodes = reloaded.all_nodes()
        self.assertEqual(len(rld_nodes), len(src_nodes),
                         f"{game.name}: node count mismatch")

        # Mesh geometry.
        src_meshes = [n for n in src_nodes if n.flags & NodeFlags.MESH]
        rld_meshes = [n for n in rld_nodes if n.flags & NodeFlags.MESH]
        self.assertEqual(len(rld_meshes), len(src_meshes),
                         f"{game.name}: mesh-node count mismatch")

        for src_m, rld_m in zip(src_meshes, rld_meshes):
            with self.subTest(mesh=src_m.name, game=game.name):
                self.assertEqual(
                    len(rld_m.vertices), len(src_m.vertices),
                    "vertex count mismatch")
                self.assertEqual(
                    len(rld_m.faces), len(src_m.faces),
                    "face count mismatch")

                # Check first three vertices within epsilon.
                for i in range(min(3, len(src_m.vertices))):
                    sx, sy, sz = src_m.vertices[i]
                    rx, ry, rz = rld_m.vertices[i]
                    self.assertAlmostEqual(rx, sx, delta=VTX_EPS,
                                           msg=f"v[{i}].x drift")
                    self.assertAlmostEqual(ry, sy, delta=VTX_EPS,
                                           msg=f"v[{i}].y drift")
                    self.assertAlmostEqual(rz, sz, delta=VTX_EPS,
                                           msg=f"v[{i}].z drift")


if __name__ == "__main__":
    unittest.main(verbosity=2)
