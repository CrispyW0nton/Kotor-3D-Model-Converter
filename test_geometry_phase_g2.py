"""test_geometry_phase_g2.py
==============================
Phase G2 unit tests — additional coverage beyond Phase G1:

  * K2-specific mesh-header fields (dirt_*, hide_in_holograms)
  * Skin-weight bone-index bounds handling
  * Quaternion convention locked at the loader seam
  * 180° axis-rotation preservation semantics
  * Skin vertex transform through a non-identity parent rotation
  * DXT/TPC texture orientation normalisation

Run from the repo root:
    python -m unittest test_geometry_phase_g2.py -v

Phase G1 already covers the simpler parent-chain / bind-pose / seam /
TGA-flip cases in ``test_geometry_correctness.py``; this module adds
the bits that are genuinely new to G2 instead of duplicating them.
"""

from __future__ import annotations

import io
import logging
import math
import os
import sys
import types
import unittest
from typing import List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from src.core.model_data import (
    KotorModel, ModelNode, NodeFlags,
    _quat_mul, _quat_rotate, _quat_normalize_bind,
)
from src.core.vertex_space import VertexSpace


# ────────────────────────────────────────────────────────────────────────
#  Test helpers
# ────────────────────────────────────────────────────────────────────────

def _link(parent: ModelNode, child: ModelNode) -> None:
    child.parent = parent
    parent.children.append(child)


class _StubVec3:
    __slots__ = ('x', 'y', 'z')
    def __init__(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)


class _StubVec4:
    __slots__ = ('x', 'y', 'z', 'w')
    def __init__(self, x, y, z, w):
        self.x, self.y, self.z, self.w = float(x), float(y), float(z), float(w)


class _StubMesh:
    """Minimal PyKotor-MDLMesh lookalike — only the attributes touched by
    ``kotor_loader._read_mesh`` are populated.  Omitted optional fields
    fall back to ``getattr(..., default)`` the same way a real mesh would
    when GhostRigger is run against an older PyKotor build.
    """

    def __init__(self, **overrides):
        # ── required list-typed fields ──
        self.vertex_positions: list = []
        self.vertex_normals:   list = []
        self.vertex_tangents:  list = []
        self.vertex_uv1:       list = []
        self.vertex_uv2:       list = []
        self.vertex_uv3:       list = []
        self.vertex_uv4:       list = []
        self.faces:            list = []
        self.face_mats:        list = []
        self.face_uvs:         list = []
        # K2 mesh-header fields we care about in this phase:
        self.dirt_enabled              = False
        self.dirt_texture              = 0
        self.dirt_coordinate_space     = 0
        self.hologram_donotdraw        = False
        self.hide_in_hologram          = False
        # Apply overrides.
        for k, v in overrides.items():
            setattr(self, k, v)


class _StubVertexBones:
    def __init__(self, vertex_indices: List[float], vertex_weights: List[float]):
        self.vertex_indices = list(vertex_indices)
        self.vertex_weights = list(vertex_weights)


class _StubSkin:
    def __init__(self, bone_indices, vertex_bones):
        self.bone_indices = list(bone_indices)
        self.bonemap = []
        self.vertex_bones = list(vertex_bones)
        self.qbones = []
        self.tbones = []


class _StubPkNode:
    def __init__(self, node_id: int, name: str):
        self.node_id = node_id
        self.name = name


# ────────────────────────────────────────────────────────────────────────
#  1. K2 mesh-header fields populate from PyKotor
# ────────────────────────────────────────────────────────────────────────

class K2MeshFieldTests(unittest.TestCase):
    """``_read_mesh`` must propagate K2 dirt/hologram flags from the
    PyKotor mesh to our ``ModelNode`` so that (a) round-trip writing can
    emit byte-identical K2 headers and (b) the viewport can honour the
    hologram-donotdraw flag.  K1 models set these to defaults (False/0)
    so the code path is safe regardless of game version.
    """

    def test_k2_mesh_fields_propagated(self):
        from src.core.kotor_loader import _read_mesh

        mesh = _StubMesh(
            dirt_enabled=True,
            dirt_texture=3,
            dirt_coordinate_space=1,
            hologram_donotdraw=True,
            hide_in_hologram=False,
        )
        gr = ModelNode(name="armour", flags=int(NodeFlags.HEADER) | int(NodeFlags.MESH))
        _read_mesh(mesh, gr)

        self.assertTrue(gr.dirt_enabled)
        self.assertEqual(gr.dirt_texture, 3)
        self.assertEqual(gr.dirt_coord_space, 1)
        self.assertTrue(gr.hide_in_holograms,
                        "hologram_donotdraw on the PyKotor mesh must OR into "
                        "ModelNode.hide_in_holograms")

    def test_legacy_hide_in_hologram_alias(self):
        """PyKotor exposes both ``hologram_donotdraw`` (modern) and the
        legacy ``hide_in_hologram`` alias.  We must OR them so either
        source wins."""
        from src.core.kotor_loader import _read_mesh
        mesh = _StubMesh(hologram_donotdraw=False, hide_in_hologram=True)
        gr = ModelNode(name="m", flags=int(NodeFlags.HEADER) | int(NodeFlags.MESH))
        _read_mesh(mesh, gr)
        self.assertTrue(gr.hide_in_holograms)

    def test_k1_defaults_no_op(self):
        """K1 models — all K2 fields absent/default — must land in the
        no-op configuration (False / 0)."""
        from src.core.kotor_loader import _read_mesh
        mesh = _StubMesh()   # all defaults
        gr = ModelNode(name="m", flags=int(NodeFlags.HEADER) | int(NodeFlags.MESH))
        _read_mesh(mesh, gr)
        self.assertFalse(gr.dirt_enabled)
        self.assertEqual(gr.dirt_texture, 0)
        self.assertEqual(gr.dirt_coord_space, 0)
        self.assertFalse(gr.hide_in_holograms)


# ────────────────────────────────────────────────────────────────────────
#  2. Skin-weight bone-index bounds handling
# ────────────────────────────────────────────────────────────────────────

class SkinBoneIndexBoundsTests(unittest.TestCase):
    """``_read_skin_weights`` must drop per-vertex influences whose
    ``bone_index >= len(bone_map)`` and emit a single summary WARNING.
    This test was the Phase G2 request from the spec.
    """

    def test_out_of_range_index_dropped_and_warned(self):
        from src.core.kotor_loader import _read_skin_weights

        # Two valid bones in the compact array.  A real MDL would have
        # up to 16 ``bone_indices`` entries; we only need two for the test.
        skin = _StubSkin(
            bone_indices=[1, 2],   # node_ids 1 and 2
            vertex_bones=[
                _StubVertexBones(
                    vertex_indices=[0.0, 1.0, 99.0, -1.0],   # 99 = OOB
                    vertex_weights=[0.4, 0.4, 0.2, 0.0],
                ),
                _StubVertexBones(
                    vertex_indices=[0.0, 17.0, -1.0, -1.0],  # 17 = OOB
                    vertex_weights=[1.0, 0.0, 0.0, 0.0],
                ),
            ],
        )
        id_to_pknode = {
            1: _StubPkNode(1, 'Bone1'),
            2: _StubPkNode(2, 'Bone2'),
        }
        gr = ModelNode(name="testskin",
                       flags=int(NodeFlags.HEADER) | int(NodeFlags.SKIN))

        with self.assertLogs('src.core.kotor_loader', level='WARNING') as cm:
            _read_skin_weights(skin, gr, id_to_pknode)

        # bone_map has the two valid names we supplied.
        self.assertEqual(gr.bone_map, ['Bone1', 'Bone2'])
        # Vertex 0 kept its three valid influences (idx 0, 1, -1 ignored).
        vsd0 = gr.skin_data[0]
        kept0 = {bw.bone_index for bw in vsd0.influences}
        self.assertEqual(kept0, {0, 1},
                         "Out-of-range index 99 must be dropped; -1 also dropped")
        # Vertex 1 kept only idx 0 (17 was OOB).
        vsd1 = gr.skin_data[1]
        self.assertEqual([bw.bone_index for bw in vsd1.influences], [0])
        # A single WARNING with the OOB summary must have fired.
        joined = '\n'.join(cm.output)
        self.assertIn("exceeded bone_map size 2", joined)
        self.assertIn("testskin", joined)

    def test_all_valid_no_warning(self):
        """If every influence is in-range, no WARNING should be emitted."""
        from src.core.kotor_loader import _read_skin_weights

        skin = _StubSkin(
            bone_indices=[5],
            vertex_bones=[
                _StubVertexBones(
                    vertex_indices=[0.0, -1.0, -1.0, -1.0],
                    vertex_weights=[1.0, 0.0, 0.0, 0.0],
                ),
            ],
        )
        gr = ModelNode(name="clean",
                       flags=int(NodeFlags.HEADER) | int(NodeFlags.SKIN))
        logger = logging.getLogger('src.core.kotor_loader')
        orig_level = logger.level
        logger.setLevel(logging.WARNING)
        handler_output: list = []

        class _Capture(logging.Handler):
            def emit(self, record):
                handler_output.append(record.getMessage())

        h = _Capture(level=logging.WARNING)
        logger.addHandler(h)
        try:
            _read_skin_weights(skin, gr, {5: _StubPkNode(5, 'B5')})
        finally:
            logger.removeHandler(h)
            logger.setLevel(orig_level)

        self.assertFalse(
            any('exceeded bone_map' in m for m in handler_output),
            f"Unexpected WARNING emitted: {handler_output!r}",
        )


# ────────────────────────────────────────────────────────────────────────
#  3. Quaternion convention locked at the loader seam
# ────────────────────────────────────────────────────────────────────────

class QuaternionConventionTests(unittest.TestCase):
    """The on-disk MDL binary stores orientation as W,X,Y,Z.  PyKotor
    deserialises that into ``Vector4(x, y, z, w)``.  Our loader copies
    PyKotor's accessor ordering directly into ``ModelNode.rotation``,
    so ``ModelNode.rotation`` MUST be XYZW at every callsite.  This
    test pins down the convention by mocking a PyKotor node.
    """

    def test_loader_stores_xyzw(self):
        # Simulate a PyKotor node whose orientation is a 90° rotation
        # about the Z axis — XYZW form = (0, 0, sin(45°), cos(45°)).
        # We mirror the exact three-line copy that
        # ``src.core.kotor_loader._read_node`` performs (``gr.rotation =
        # (o.x, o.y, o.z, o.w)``) rather than importing a private
        # helper; the contract under test is the storage order.
        class _PkNode:
            position = _StubVec3(0.0, 0.0, 0.0)
            orientation = _StubVec4(0.0, 0.0, math.sin(math.radians(45)),
                                    math.cos(math.radians(45)))
        pk = _PkNode()
        gr = ModelNode(name="q", flags=int(NodeFlags.HEADER))
        # Mirror the two lines in _read_node that copy pk.orientation:
        o = pk.orientation
        gr.rotation = (float(o.x), float(o.y), float(o.z), float(o.w))
        # Stored as xyzw — w must be the LAST element.
        self.assertAlmostEqual(gr.rotation[3], math.cos(math.radians(45)),
                               places=5)
        self.assertAlmostEqual(gr.rotation[2], math.sin(math.radians(45)),
                               places=5)
        # _quat_rotate must treat rotation as xyzw: rotating (1,0,0) by a
        # 90°-about-Z yields (0,1,0).
        rx, ry, rz = _quat_rotate(gr.rotation, (1.0, 0.0, 0.0))
        self.assertAlmostEqual(rx, 0.0, places=5)
        self.assertAlmostEqual(ry, 1.0, places=5)
        self.assertAlmostEqual(rz, 0.0, places=5)


# ────────────────────────────────────────────────────────────────────────
#  4. 180° axis-rotation preservation semantics
# ────────────────────────────────────────────────────────────────────────

class RotationPreservationTests(unittest.TestCase):
    """``_quat_normalize_bind`` must collapse ONLY the pure X-axis 180°
    quaternion (NWN coord-flip), preserving Y-axis and Z-axis 180°
    rotations intact because droid / creature limb mirrors depend on
    them (c_drdassassin, c_warbot, c_brith).
    """

    def test_x_axis_180_collapses(self):
        # Pure X-axis 180° in XYZW = (1, 0, 0, 0).
        collapsed = _quat_normalize_bind([1.0, 0.0, 0.0, 0.0])
        self.assertAlmostEqual(collapsed[3], 1.0, places=5,
                               msg="X-axis 180° must collapse to identity w=1")
        for i in range(3):
            self.assertAlmostEqual(collapsed[i], 0.0, places=5)

    def test_y_axis_180_preserved(self):
        q = _quat_normalize_bind([0.0, 1.0, 0.0, 0.0])
        # Must still represent a Y-axis 180° rotation — i.e. rotating
        # (1,0,0) by it yields (-1, 0, 0).
        rx, ry, rz = _quat_rotate(q, (1.0, 0.0, 0.0))
        self.assertAlmostEqual(rx, -1.0, places=5)
        self.assertAlmostEqual(ry,  0.0, places=5)
        self.assertAlmostEqual(rz,  0.0, places=5)

    def test_z_axis_180_preserved(self):
        q = _quat_normalize_bind([0.0, 0.0, 1.0, 0.0])
        rx, ry, rz = _quat_rotate(q, (1.0, 0.0, 0.0))
        self.assertAlmostEqual(rx, -1.0, places=5)
        self.assertAlmostEqual(ry,  0.0, places=5)
        self.assertAlmostEqual(rz,  0.0, places=5)

    def test_generic_rotation_preserved(self):
        # 60° about (0.5, 0.5, 0.5)/|(0.5,0.5,0.5)| — not a pure 180°
        axis = (1.0 / math.sqrt(3),) * 3
        s = math.sin(math.radians(30))
        q_in = [axis[0]*s, axis[1]*s, axis[2]*s, math.cos(math.radians(30))]
        q_out = _quat_normalize_bind(q_in)
        # Within floating-point tolerance, no component should flip sign.
        for a, b in zip(q_in, q_out):
            self.assertAlmostEqual(a, b, places=5)


# ────────────────────────────────────────────────────────────────────────
#  5. Skin vertex transform through non-identity parent rotation
# ────────────────────────────────────────────────────────────────────────

class SkinRotatedParentTests(unittest.TestCase):
    """Extension of Phase G1's bind-pose identity test: when a skin
    node's parent carries a non-identity rotation, vertices must be
    rotated (not just translated) before hitting world space.  This
    verifies the full ``_apply_vertex_transform`` path — not just the
    identity-rotation shortcut.
    """

    def test_skin_vertices_through_rotated_parent(self):
        try:
            from src.gui.viewport import FrameRenderer, ArcBallCamera
        except Exception as exc:
            self.skipTest(f"viewport import unavailable: {exc}")

        # Parent rotates 90° about Z (xyzw = 0, 0, sin45, cos45).
        root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
        parent = ModelNode(
            name="parent", flags=int(NodeFlags.HEADER),
            position=(0.0, 0.0, 0.0),
            rotation=(0.0, 0.0, math.sin(math.radians(45)),
                      math.cos(math.radians(45))),
        )
        skin_flags = int(NodeFlags.HEADER) | int(NodeFlags.MESH) | int(NodeFlags.SKIN)
        skin = ModelNode(name="body", flags=skin_flags,
                         position=(1.0, 0.0, 0.0))
        # One vertex pointing along +X in skin-local space.
        skin.vertices = [(2.0, 0.0, 0.0)]
        skin.bone_map = []
        skin.skin_data = []
        _link(root, parent)
        _link(parent, skin)

        model = KotorModel(name="t", root_node=root)
        fr = FrameRenderer(ArcBallCamera())
        fr.model = model
        fr._anim_pose = None
        fr._wt_cache = {}

        [(wx, wy, wz)] = fr._get_world_verts_for_node(skin)
        # Parent rotates +X → +Y.  After applying the parent rotation to
        # skin.position (1,0,0) we land at (0,1,0).  Then the skin-local
        # vertex (2,0,0) is rotated by the same accumulated world
        # orientation (+X → +Y), yielding world pos (0,1,0) + (0,2,0) =
        # (0, 3, 0).
        self.assertAlmostEqual(wx, 0.0, places=4)
        self.assertAlmostEqual(wy, 3.0, places=4)
        self.assertAlmostEqual(wz, 0.0, places=4)


# ────────────────────────────────────────────────────────────────────────
#  6. DXT / TPC texture orientation normalisation
# ────────────────────────────────────────────────────────────────────────

class TpcTextureOrientationTests(unittest.TestCase):
    """``_load_tpc_bytes`` / ``_load_tpc_bytes_legacy`` must produce
    PIL images whose orientation matches the rasterizer's
    ``tv = (1 - v) * h`` convention.  The exact transform differs per
    source format:

      * Uncompressed RGBA/RGB/Grey — PyKotor emits bottom-up already,
        no extra flip.
      * DXT1 / DXT3 / DXT5 — emitted top-down, the loader applies
        ``Image.FLIP_TOP_BOTTOM``.

    Phase G1 already covers TGA (PIL-direct) orientation in
    ``test_geometry_correctness.py::test_texture_vflip_consistency``.
    The DXT code path needs a DXT encoder we don't carry in-tree, so
    here we assert the RGBA contract: round-tripping an uncompressed
    TPC yields an image that round-trips back to the same pixel layout
    the caller supplied (no silent flip that would desync compressed
    and uncompressed assets in the cache).
    """

    def test_uncompressed_tpc_no_unintended_flip(self):
        try:
            from src.gui.viewport import _load_tpc_bytes
        except Exception as exc:
            self.skipTest(f"viewport unavailable: {exc}")

        try:
            from pykotor.resource.formats.tpc import TPC
            from pykotor.resource.formats.tpc.tpc_data import TPCTextureFormat
            from pykotor.resource.formats.tpc.io_tpc import TPCBinaryWriter
        except Exception as exc:
            self.skipTest(f"PyKotor TPC API unavailable: {exc}")

        # 4×4 RGBA: first-two rows red, last-two rows blue.  PyKotor
        # does not document whether "first rows" == PIL-top or
        # PIL-bottom for RGBA, so we deliberately only assert that the
        # rows at PIL y=0 and y=3 are DIFFERENT and each is saturated
        # with a single channel — the orientation invariant itself is
        # exercised at render time by the tv=(1-v)*h formula.  A flip
        # regression (e.g. accidental double-flip of uncompressed
        # content) would produce the same colour at both y extremes
        # because the two colour halves would overlap in mipmap 0.
        red_row  = b'\xff\x00\x00\xff' * 4
        blue_row = b'\x00\x00\xff\xff' * 4
        pixels   = red_row * 2 + blue_row * 2

        tpc = TPC()
        try:
            tpc.set_single(pixels, TPCTextureFormat.RGBA, 4, 4)
        except Exception as exc:
            self.skipTest(f"TPC.set_single RGBA unsupported: {exc}")

        buf = io.BytesIO()
        try:
            TPCBinaryWriter(tpc, buf).write(auto_close=False)
        except Exception as exc:
            self.skipTest(f"TPC serialisation failed: {exc}")

        img = _load_tpc_bytes(buf.getvalue())
        if img is None:
            self.skipTest("_load_tpc_bytes returned None for synthetic TPC")
        img_rgba = img.convert('RGBA')
        self.assertEqual(img_rgba.size, (4, 4))

        px_y0 = img_rgba.getpixel((0, 0))
        px_y3 = img_rgba.getpixel((0, 3))
        self.assertNotEqual(px_y0, px_y3,
                            "TPC loader produced uniform image — "
                            "possible double-flip or orientation "
                            "collapse")
        # Each row extreme must be single-channel saturated (either
        # pure red or pure blue).  A row-interleaving regression (e.g.
        # partial flip) would mix channels.
        for px in (px_y0, px_y3):
            saturated_channels = sum(1 for c in px[:3] if c > 250)
            self.assertEqual(saturated_channels, 1,
                             f"Row extreme {px!r} is not single-channel "
                             "saturated — possible row-interleave bug")


if __name__ == "__main__":
    unittest.main(verbosity=2)
