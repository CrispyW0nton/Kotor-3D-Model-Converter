"""
Phase 9.1/9.2 — Walkmesh Renderer Tests
========================================
Comprehensive test suite for src/core/walkmesh_renderer.py.

Tests cover:
  1. Surface material constants & color table completeness
  2. surface_color() and surface_name() helpers
  3. WalkmeshFace dataclass — vertex storage, color property, face normal
  4. WalkmeshOverlay — empty state, load_from_wok(), load_from_ascii_wok()
  5. WalkmeshOverlay filtering — walkable/non-walkable, by material
  6. WalkmeshOverlay.faces_for_render() — visibility toggle, filter flags
  7. WalkmeshOverlay.aabb() — bounding box from face verts
  8. WalkmeshOverlay.boundary_edges() — edge topology
  9. WalkmeshOverlay.summary()
  10. WalkmeshLoader — from_wok_data, from_scene_room, load_all_room_overlays
  11. build_draw_list() — draw list generation and filtering
  12. World-offset application on load
  13. Edge cases — empty wok, out-of-range indices, unknown material

Refs: KotOR.js OdysseyWalkMesh.ts; PyKotor bwm_data.py;
      GhostRigger Roadmap Phase 9.1-9.4.
"""

import math
import sys
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# ── import path ─────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.walkmesh_renderer import (
    # Constants
    SURFACE_INVALID, SURFACE_DIRT, SURFACE_OBSCURING, SURFACE_GRASS,
    SURFACE_STONE, SURFACE_WOOD, SURFACE_WATER, SURFACE_NON_WALK,
    SURFACE_TRANSPARENT, SURFACE_CARPET, SURFACE_METAL, SURFACE_PUDDLES,
    SURFACE_SWAMP, SURFACE_MUD, SURFACE_LEAVES, SURFACE_LAVA,
    SURFACE_BOTTOMLESS, SURFACE_DEEP_WATER, SURFACE_DOOR,
    SURFACE_NON_WALK_GRASS, SURFACE_SNOW, SURFACE_SAND, SURFACE_BAREBONES,
    WALKABLE_SURFACES, NON_WALKABLE_SURFACES,
    SURFACE_COLORS,
    # Functions
    surface_color, surface_name,
    # Classes
    WalkmeshFace, WalkmeshOverlay, WalkmeshLoader,
    WalkmeshDrawEntry, build_draw_list,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Surface constants
# ─────────────────────────────────────────────────────────────────────────────

class TestSurfaceConstants(unittest.TestCase):

    def test_surface_id_values(self):
        self.assertEqual(SURFACE_INVALID,   0)
        self.assertEqual(SURFACE_DIRT,      1)
        self.assertEqual(SURFACE_NON_WALK,  7)
        self.assertEqual(SURFACE_DOOR,      18)
        self.assertEqual(SURFACE_BAREBONES, 22)

    def test_walkable_set_excludes_non_walk(self):
        self.assertNotIn(SURFACE_NON_WALK, WALKABLE_SURFACES)
        self.assertNotIn(SURFACE_BOTTOMLESS, WALKABLE_SURFACES)
        self.assertNotIn(SURFACE_NON_WALK_GRASS, WALKABLE_SURFACES)

    def test_walkable_set_includes_walkable(self):
        for sid in (SURFACE_DIRT, SURFACE_GRASS, SURFACE_STONE,
                    SURFACE_WOOD, SURFACE_CARPET, SURFACE_METAL,
                    SURFACE_DOOR, SURFACE_SNOW, SURFACE_SAND):
            self.assertIn(sid, WALKABLE_SURFACES,
                          msg=f"surface {sid} should be walkable")

    def test_non_walkable_set(self):
        self.assertIn(SURFACE_NON_WALK,        NON_WALKABLE_SURFACES)
        self.assertIn(SURFACE_BOTTOMLESS,      NON_WALKABLE_SURFACES)
        self.assertIn(SURFACE_NON_WALK_GRASS,  NON_WALKABLE_SURFACES)

    def test_sets_disjoint(self):
        overlap = WALKABLE_SURFACES & NON_WALKABLE_SURFACES
        self.assertEqual(len(overlap), 0,
                         msg=f"surfaces appear in both sets: {overlap}")

    def test_color_table_completeness(self):
        """All surface IDs 0–22 must have a color entry."""
        for sid in range(23):
            self.assertIn(sid, SURFACE_COLORS,
                          msg=f"SURFACE_COLORS missing entry for id={sid}")

    def test_color_values_in_range(self):
        """All RGBA components must be in [0.0, 1.0]."""
        for sid, rgba in SURFACE_COLORS.items():
            for i, c in enumerate(rgba):
                self.assertGreaterEqual(c, 0.0,
                    msg=f"sid={sid} channel {i} < 0")
                self.assertLessEqual(c, 1.0,
                    msg=f"sid={sid} channel {i} > 1")

    def test_non_walk_is_red_prominent(self):
        """NON_WALK surface should be visually prominent (red-ish, high alpha)."""
        r, g, b, a = SURFACE_COLORS[SURFACE_NON_WALK]
        self.assertGreater(r, 0.6, "NON_WALK should be red-dominant")
        self.assertGreater(a, 0.6, "NON_WALK should have high alpha")

    def test_door_color_has_4_components(self):
        c = surface_color(SURFACE_DOOR)
        self.assertEqual(len(c), 4)


# ─────────────────────────────────────────────────────────────────────────────
# 2. surface_color / surface_name helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestSurfaceHelpers(unittest.TestCase):

    def test_known_color(self):
        c = surface_color(SURFACE_GRASS)
        self.assertEqual(c, SURFACE_COLORS[SURFACE_GRASS])

    def test_unknown_id_fallback(self):
        c = surface_color(9999)
        # Should return default fallback tuple, not raise
        self.assertEqual(len(c), 4)

    def test_surface_name_known(self):
        self.assertEqual(surface_name(SURFACE_DIRT), 'DIRT')
        self.assertEqual(surface_name(SURFACE_NON_WALK), 'NON_WALK')
        self.assertEqual(surface_name(SURFACE_DOOR), 'DOOR')
        self.assertEqual(surface_name(SURFACE_SNOW), 'SNOW')
        self.assertEqual(surface_name(SURFACE_BAREBONES), 'BAREBONES')

    def test_surface_name_unknown(self):
        name = surface_name(9999)
        self.assertIn('9999', name)  # should contain the ID

    def test_surface_name_all_known_ids(self):
        for sid in range(23):
            name = surface_name(sid)
            self.assertIsInstance(name, str)
            self.assertTrue(len(name) > 0)


# ─────────────────────────────────────────────────────────────────────────────
# 3. WalkmeshFace
# ─────────────────────────────────────────────────────────────────────────────

class TestWalkmeshFace(unittest.TestCase):

    def _make_face(self, surface=SURFACE_GRASS, walkable=True):
        return WalkmeshFace(
            v0=(0.0, 0.0, 0.0),
            v1=(1.0, 0.0, 0.0),
            v2=(0.0, 1.0, 0.0),
            surface=surface,
            walkable=walkable,
        )

    def test_vertex_storage(self):
        f = self._make_face()
        self.assertEqual(f.v0, (0.0, 0.0, 0.0))
        self.assertEqual(f.v1, (1.0, 0.0, 0.0))
        self.assertEqual(f.v2, (0.0, 1.0, 0.0))

    def test_surface_field(self):
        f = self._make_face(surface=SURFACE_METAL)
        self.assertEqual(f.surface, SURFACE_METAL)

    def test_color_property_matches_table(self):
        f = self._make_face(surface=SURFACE_METAL)
        self.assertEqual(f.color, surface_color(SURFACE_METAL))

    def test_walkable_flag_true(self):
        f = self._make_face(surface=SURFACE_DIRT, walkable=True)
        self.assertTrue(f.walkable)

    def test_walkable_flag_false(self):
        f = self._make_face(surface=SURFACE_NON_WALK, walkable=False)
        self.assertFalse(f.walkable)

    def test_normal_horizontal_triangle(self):
        """Triangle in XY plane should have normal pointing in +Z or -Z."""
        f = WalkmeshFace(
            v0=(0.0, 0.0, 0.0),
            v1=(1.0, 0.0, 0.0),
            v2=(0.0, 1.0, 0.0),
        )
        n = f.normal
        self.assertAlmostEqual(abs(n[2]), 1.0, places=5)
        self.assertAlmostEqual(n[0], 0.0, places=5)
        self.assertAlmostEqual(n[1], 0.0, places=5)

    def test_normal_vertical_triangle_yz(self):
        """Triangle in YZ plane should have normal pointing in +/-X."""
        f = WalkmeshFace(
            v0=(0.0, 0.0, 0.0),
            v1=(0.0, 1.0, 0.0),
            v2=(0.0, 0.0, 1.0),
        )
        n = f.normal
        self.assertAlmostEqual(abs(n[0]), 1.0, places=5)

    def test_normal_degenerate_triangle(self):
        """Degenerate (zero-area) triangle should return default normal."""
        f = WalkmeshFace(
            v0=(0.0, 0.0, 0.0),
            v1=(0.0, 0.0, 0.0),
            v2=(0.0, 0.0, 0.0),
        )
        n = f.normal
        self.assertEqual(len(n), 3)
        # Should be a unit vector (the fallback)
        length = math.sqrt(sum(c*c for c in n))
        self.assertAlmostEqual(length, 1.0, places=5)

    def test_normal_length_is_unit(self):
        f = WalkmeshFace(
            v0=(1.0, 2.0, 3.0),
            v1=(4.0, 5.0, 3.0),
            v2=(1.0, 8.0, 3.0),
        )
        n = f.normal
        length = math.sqrt(sum(c*c for c in n))
        self.assertAlmostEqual(length, 1.0, places=5)


# ─────────────────────────────────────────────────────────────────────────────
# 4. WalkmeshOverlay — load_from_ascii_wok
# ─────────────────────────────────────────────────────────────────────────────

ASCII_WOK = """\
# test walkmesh
verts 4
  0.0 0.0 0.0
  2.0 0.0 0.0
  2.0 2.0 0.0
  0.0 2.0 0.0
faces 3
  0 1 2 1
  0 2 3 3
  1 2 3 7
"""

class TestWalkmeshOverlayAscii(unittest.TestCase):

    def setUp(self):
        self.overlay = WalkmeshOverlay()
        self.overlay.load_from_ascii_wok(ASCII_WOK)

    def test_face_count(self):
        self.assertEqual(len(self.overlay.faces), 3)

    def test_surface_materials(self):
        surfs = sorted(f.surface for f in self.overlay.faces)
        self.assertEqual(surfs, [1, 3, 7])  # DIRT, GRASS, NON_WALK

    def test_walkable_faces(self):
        wf = self.overlay.walkable_faces()
        self.assertEqual(len(wf), 2)

    def test_non_walkable_faces(self):
        nf = self.overlay.non_walkable_faces()
        self.assertEqual(len(nf), 1)
        self.assertEqual(nf[0].surface, SURFACE_NON_WALK)

    def test_vertex_positions_correct(self):
        f0 = self.overlay.faces[0]
        self.assertAlmostEqual(f0.v0[0], 0.0)
        self.assertAlmostEqual(f0.v1[0], 2.0)
        self.assertAlmostEqual(f0.v2[0], 2.0)

    def test_default_offset_zero(self):
        self.assertEqual(self.overlay.offset, (0.0, 0.0, 0.0))

    def test_with_offset(self):
        overlay2 = WalkmeshOverlay()
        overlay2.load_from_ascii_wok(ASCII_WOK, world_offset=(10.0, 5.0, 1.0))
        f0 = overlay2.faces[0]
        self.assertAlmostEqual(f0.v0[0], 10.0)
        self.assertAlmostEqual(f0.v0[1], 5.0)
        self.assertAlmostEqual(f0.v0[2], 1.0)

    def test_comments_ignored(self):
        """Lines starting with # should be skipped."""
        self.assertEqual(len(self.overlay.faces), 3)  # not 4


class TestWalkmeshOverlayEmpty(unittest.TestCase):

    def test_empty_overlay_faces(self):
        ov = WalkmeshOverlay()
        self.assertEqual(len(ov.faces), 0)

    def test_empty_aabb_is_none(self):
        ov = WalkmeshOverlay()
        self.assertIsNone(ov.aabb())

    def test_visible_by_default(self):
        ov = WalkmeshOverlay()
        self.assertTrue(ov.visible)

    def test_faces_for_render_empty(self):
        ov = WalkmeshOverlay()
        self.assertEqual(ov.faces_for_render(), [])

    def test_summary_zero_faces(self):
        ov = WalkmeshOverlay()
        s = ov.summary()
        self.assertIn('0', s)


# ─────────────────────────────────────────────────────────────────────────────
# 5. WalkmeshOverlay — load_from_wok (using mock WOKData)
# ─────────────────────────────────────────────────────────────────────────────

def _make_wok_data(verts, faces_data):
    """Build a minimal mock WOKData namespace."""
    wok = SimpleNamespace()
    wok.verts = verts
    WFace = lambda v1, v2, v3, s: SimpleNamespace(v1=v1, v2=v2, v3=v3, surface=s)
    wok.faces = [WFace(*fd) for fd in faces_data]
    return wok


class TestWalkmeshOverlayFromWok(unittest.TestCase):

    def setUp(self):
        verts = [
            (0.0, 0.0, 0.0),
            (3.0, 0.0, 0.0),
            (3.0, 3.0, 0.0),
            (0.0, 3.0, 0.0),
        ]
        # (v1, v2, v3, surface)
        faces_data = [
            (0, 1, 2, SURFACE_STONE),
            (0, 2, 3, SURFACE_WOOD),
            (1, 2, 3, SURFACE_NON_WALK),
        ]
        self.wok = _make_wok_data(verts, faces_data)
        self.overlay = WalkmeshOverlay()
        self.overlay.load_from_wok(self.wok)

    def test_face_count(self):
        self.assertEqual(len(self.overlay.faces), 3)

    def test_walkable_count(self):
        self.assertEqual(len(self.overlay.walkable_faces()), 2)

    def test_non_walkable_count(self):
        self.assertEqual(len(self.overlay.non_walkable_faces()), 1)

    def test_face_surfaces(self):
        surfs = {f.surface for f in self.overlay.faces}
        self.assertIn(SURFACE_STONE, surfs)
        self.assertIn(SURFACE_WOOD, surfs)
        self.assertIn(SURFACE_NON_WALK, surfs)

    def test_world_offset_applied(self):
        overlay2 = WalkmeshOverlay()
        overlay2.load_from_wok(self.wok, world_offset=(5.0, 5.0, 2.0))
        f0 = overlay2.faces[0]
        self.assertAlmostEqual(f0.v0[0], 5.0)
        self.assertAlmostEqual(f0.v0[1], 5.0)
        self.assertAlmostEqual(f0.v0[2], 2.0)

    def test_out_of_range_index_skipped(self):
        """Faces with vertex indices >= len(verts) should be skipped."""
        verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
        bad_faces = [(0, 1, 99, SURFACE_DIRT)]  # index 99 is out of range
        wok_bad = _make_wok_data(verts, bad_faces)
        ov = WalkmeshOverlay()
        ov.load_from_wok(wok_bad)
        self.assertEqual(len(ov.faces), 0)

    def test_empty_wok_data(self):
        """Load from WOK with zero verts and faces."""
        wok_empty = _make_wok_data([], [])
        ov = WalkmeshOverlay()
        ov.load_from_wok(wok_empty)
        self.assertEqual(len(ov.faces), 0)

    def test_reload_clears_previous(self):
        """Calling load_from_wok again replaces old data."""
        self.overlay.load_from_wok(self.wok)  # reload
        self.assertEqual(len(self.overlay.faces), 3)


# ─────────────────────────────────────────────────────────────────────────────
# 6. WalkmeshOverlay — filtering
# ─────────────────────────────────────────────────────────────────────────────

class TestWalkmeshOverlayFiltering(unittest.TestCase):

    def setUp(self):
        # 3 walkable, 2 non-walkable faces
        self.overlay = WalkmeshOverlay()
        self.overlay.load_from_ascii_wok("""\
verts 4
  0 0 0
  1 0 0
  1 1 0
  0 1 0
faces 5
  0 1 2 1
  0 1 2 3
  0 1 2 4
  0 1 2 7
  0 1 2 16
""")

    def test_walkable_count(self):
        # surfaces 1(DIRT), 3(GRASS), 4(STONE) are walkable
        # surfaces 7(NON_WALK), 16(BOTTOMLESS) are not walkable
        walk = self.overlay.walkable_faces()
        self.assertEqual(len(walk), 3)

    def test_non_walkable_count(self):
        nwalk = self.overlay.non_walkable_faces()
        self.assertEqual(len(nwalk), 2)

    def test_faces_by_material(self):
        d = self.overlay.faces_by_material(SURFACE_DIRT)
        self.assertEqual(len(d), 1)
        g = self.overlay.faces_by_material(SURFACE_GRASS)
        self.assertEqual(len(g), 1)
        absent = self.overlay.faces_by_material(SURFACE_SNOW)
        self.assertEqual(len(absent), 0)

    def test_faces_for_render_both(self):
        result = self.overlay.faces_for_render(True, True)
        self.assertEqual(len(result), 5)

    def test_faces_for_render_walkable_only(self):
        result = self.overlay.faces_for_render(show_walkable=True, show_non_walkable=False)
        self.assertEqual(len(result), 3)

    def test_faces_for_render_non_walkable_only(self):
        result = self.overlay.faces_for_render(show_walkable=False, show_non_walkable=True)
        self.assertEqual(len(result), 2)

    def test_faces_for_render_none(self):
        result = self.overlay.faces_for_render(show_walkable=False, show_non_walkable=False)
        self.assertEqual(len(result), 0)

    def test_visibility_toggle(self):
        self.overlay.visible = False
        result = self.overlay.faces_for_render(True, True)
        self.assertEqual(len(result), 0)

    def test_visibility_re_enabled(self):
        self.overlay.visible = False
        self.overlay.visible = True
        result = self.overlay.faces_for_render(True, True)
        self.assertEqual(len(result), 5)


# ─────────────────────────────────────────────────────────────────────────────
# 7. WalkmeshOverlay.aabb()
# ─────────────────────────────────────────────────────────────────────────────

class TestWalkmeshOverlayAABB(unittest.TestCase):

    def test_simple_aabb(self):
        ov = WalkmeshOverlay()
        ov.load_from_ascii_wok("""\
verts 3
  0.0 0.0 0.0
  4.0 0.0 2.0
  0.0 6.0 1.0
faces 1
  0 1 2 1
""")
        bb = ov.aabb()
        self.assertIsNotNone(bb)
        bb_min, bb_max = bb
        self.assertAlmostEqual(bb_min[0], 0.0)
        self.assertAlmostEqual(bb_min[1], 0.0)
        self.assertAlmostEqual(bb_min[2], 0.0)
        self.assertAlmostEqual(bb_max[0], 4.0)
        self.assertAlmostEqual(bb_max[1], 6.0)
        self.assertAlmostEqual(bb_max[2], 2.0)

    def test_aabb_with_offset(self):
        ov = WalkmeshOverlay()
        ov.load_from_ascii_wok("""\
verts 3
  0.0 0.0 0.0
  1.0 0.0 0.0
  0.0 1.0 0.0
faces 1
  0 1 2 1
""", world_offset=(10.0, 20.0, 5.0))
        bb_min, bb_max = ov.aabb()
        self.assertAlmostEqual(bb_min[0], 10.0)
        self.assertAlmostEqual(bb_max[0], 11.0)
        self.assertAlmostEqual(bb_min[2], 5.0)

    def test_aabb_empty_returns_none(self):
        ov = WalkmeshOverlay()
        self.assertIsNone(ov.aabb())

    def test_aabb_multi_face(self):
        ov = WalkmeshOverlay()
        ov.load_from_ascii_wok("""\
verts 4
  -3.0 -3.0 -1.0
   3.0 -3.0 -1.0
   3.0  3.0  5.0
  -3.0  3.0  5.0
faces 2
  0 1 2 1
  0 2 3 1
""")
        bb_min, bb_max = ov.aabb()
        self.assertAlmostEqual(bb_min[0], -3.0)
        self.assertAlmostEqual(bb_max[0],  3.0)
        self.assertAlmostEqual(bb_min[2], -1.0)
        self.assertAlmostEqual(bb_max[2],  5.0)


# ─────────────────────────────────────────────────────────────────────────────
# 8. WalkmeshOverlay.boundary_edges()
# ─────────────────────────────────────────────────────────────────────────────

class TestBoundaryEdges(unittest.TestCase):
    """
    For a single isolated walkable triangle, all 3 edges are boundary
    (exterior) edges.  Two adjacent walkable triangles sharing an interior
    edge → 4 boundary edges.
    """

    def test_single_walkable_triangle_3_edges(self):
        ov = WalkmeshOverlay()
        ov.load_from_ascii_wok("""\
verts 3
  0 0 0
  1 0 0
  0 1 0
faces 1
  0 1 2 1
""")
        edges = ov.boundary_edges()
        self.assertEqual(len(edges), 3)

    def test_two_adjacent_walkable_share_edge(self):
        """
        Two triangles sharing one interior edge: 4 boundary edges total.
        v0=(0,0,0), v1=(2,0,0), v2=(1,1,0), v3=(1,-1,0)
        Tri1: v0,v1,v2 (DIRT)
        Tri2: v0,v1,v3 (GRASS)
        Shared edge v0–v1 is interior; 4 other edges are boundary.
        """
        ov = WalkmeshOverlay()
        ov.load_from_ascii_wok("""\
verts 4
  0 0 0
  2 0 0
  1 1 0
  1 -1 0
faces 2
  0 1 2 1
  0 1 3 3
""")
        edges = ov.boundary_edges()
        # Boundary = 4 exterior edges (the shared v0-v1 edge has 2 walkable faces,
        # so it's interior and should NOT appear; BUT since both sides are walkable
        # it's classified as an interior edge, leaving 4 boundary edges)
        # Note: our boundary_edges only marks as boundary if faces are walkable
        # on exterior OR walkability differs between faces.
        # Two walkable faces sharing an edge = interior → not reported.
        self.assertEqual(len(edges), 4)

    def test_boundary_at_walkable_non_walkable_interface(self):
        """
        Edge shared by walkable and non-walkable face → boundary edge.
        """
        ov = WalkmeshOverlay()
        ov.load_from_ascii_wok("""\
verts 4
  0 0 0
  1 0 0
  1 1 0
  0 1 0
faces 2
  0 1 2 1
  0 2 3 7
""")
        edges = ov.boundary_edges()
        # Should include the v0-v2 shared edge (walkable meets non-walkable)
        self.assertGreater(len(edges), 0)


# ─────────────────────────────────────────────────────────────────────────────
# 9. WalkmeshOverlay.summary()
# ─────────────────────────────────────────────────────────────────────────────

class TestWalkmeshOverlaySummary(unittest.TestCase):

    def test_summary_contains_face_count(self):
        ov = WalkmeshOverlay()
        ov.load_from_ascii_wok(ASCII_WOK)
        s = ov.summary()
        self.assertIn('3', s)  # 3 faces

    def test_summary_contains_walkable_count(self):
        ov = WalkmeshOverlay()
        ov.load_from_ascii_wok(ASCII_WOK)
        s = ov.summary()
        self.assertIn('2', s)  # 2 walkable

    def test_summary_is_string(self):
        ov = WalkmeshOverlay()
        s = ov.summary()
        self.assertIsInstance(s, str)


# ─────────────────────────────────────────────────────────────────────────────
# 10. WalkmeshLoader
# ─────────────────────────────────────────────────────────────────────────────

class TestWalkmeshLoader(unittest.TestCase):

    def test_from_wok_data_returns_overlay(self):
        verts = [(0.0,0.0,0.0),(1.0,0.0,0.0),(0.0,1.0,0.0)]
        wok = _make_wok_data(verts, [(0, 1, 2, SURFACE_GRASS)])
        loader = WalkmeshLoader()
        overlay = loader.from_wok_data(wok)
        self.assertIsInstance(overlay, WalkmeshOverlay)
        self.assertEqual(len(overlay.faces), 1)

    def test_from_wok_data_with_offset(self):
        verts = [(0.0,0.0,0.0),(1.0,0.0,0.0),(0.0,1.0,0.0)]
        wok = _make_wok_data(verts, [(0, 1, 2, SURFACE_GRASS)])
        loader = WalkmeshLoader()
        overlay = loader.from_wok_data(wok, world_offset=(5.0, 5.0, 0.0))
        self.assertAlmostEqual(overlay.faces[0].v0[0], 5.0)
        self.assertAlmostEqual(overlay.faces[0].v0[1], 5.0)

    def test_from_scene_room_with_wok(self):
        verts = [(0.0,0.0,0.0),(1.0,0.0,0.0),(0.0,1.0,0.0)]
        wok = _make_wok_data(verts, [(0, 1, 2, SURFACE_STONE)])
        room = SimpleNamespace(wok=wok, position=(2.0, 3.0, 0.0), resref='test_room')
        loader = WalkmeshLoader()
        overlay = loader.from_scene_room(room)
        self.assertIsInstance(overlay, WalkmeshOverlay)
        self.assertEqual(len(overlay.faces), 1)
        # world offset applied
        self.assertAlmostEqual(overlay.faces[0].v0[0], 2.0)

    def test_from_scene_room_no_wok_returns_none(self):
        room = SimpleNamespace(wok=None, position=(0.0, 0.0, 0.0), resref='room1')
        loader = WalkmeshLoader()
        result = loader.from_scene_room(room)
        self.assertIsNone(result)

    def test_load_all_room_overlays(self):
        verts = [(0.0,0.0,0.0),(1.0,0.0,0.0),(0.0,1.0,0.0)]
        wok1 = _make_wok_data(verts, [(0, 1, 2, SURFACE_DIRT)])
        wok2 = _make_wok_data(verts, [(0, 1, 2, SURFACE_STONE)])
        rooms = [
            SimpleNamespace(wok=wok1, position=(0.0,0.0,0.0), resref='room_a'),
            SimpleNamespace(wok=wok2, position=(10.0,0.0,0.0), resref='room_b'),
            SimpleNamespace(wok=None,  position=(20.0,0.0,0.0), resref='room_c'),
        ]
        scene = SimpleNamespace(rooms=rooms)
        loader = WalkmeshLoader()
        overlays = loader.load_all_room_overlays(scene)
        self.assertIn('room_a', overlays)
        self.assertIn('room_b', overlays)
        self.assertNotIn('room_c', overlays)
        self.assertEqual(len(overlays), 2)

    def test_from_file_missing_returns_none(self):
        loader = WalkmeshLoader()
        result = loader.from_file('/nonexistent/path/fake.wok')
        self.assertIsNone(result)


# ─────────────────────────────────────────────────────────────────────────────
# 11. build_draw_list()
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildDrawList(unittest.TestCase):

    def _make_overlay(self, wok_text, offset=(0.0,0.0,0.0)):
        ov = WalkmeshOverlay(offset)
        ov.load_from_ascii_wok(wok_text, offset)
        return ov

    _ASCII = """\
verts 3
  0 0 0
  1 0 0
  0 1 0
faces 2
  0 1 2 1
  0 1 2 7
"""

    def test_draw_list_returns_draw_entries(self):
        ov = self._make_overlay(self._ASCII)
        dl = build_draw_list({'room1': ov})
        self.assertTrue(all(isinstance(e, WalkmeshDrawEntry) for e in dl))

    def test_draw_list_length_both(self):
        ov = self._make_overlay(self._ASCII)
        dl = build_draw_list({'room1': ov}, show_walkable=True, show_non_walkable=True)
        self.assertEqual(len(dl), 2)

    def test_draw_list_walkable_only(self):
        ov = self._make_overlay(self._ASCII)
        dl = build_draw_list({'room1': ov}, show_walkable=True, show_non_walkable=False)
        self.assertEqual(len(dl), 1)

    def test_draw_list_non_walkable_only(self):
        ov = self._make_overlay(self._ASCII)
        dl = build_draw_list({'room1': ov}, show_walkable=False, show_non_walkable=True)
        self.assertEqual(len(dl), 1)

    def test_draw_list_colors_set(self):
        ov = self._make_overlay(self._ASCII)
        dl = build_draw_list({'r': ov})
        for entry in dl:
            self.assertEqual(len(entry.color), 4)
            for c in entry.color:
                self.assertGreaterEqual(c, 0.0)
                self.assertLessEqual(c, 1.0)

    def test_draw_list_hidden_overlay_excluded(self):
        ov = self._make_overlay(self._ASCII)
        ov.visible = False
        dl = build_draw_list({'room1': ov})
        self.assertEqual(len(dl), 0)

    def test_draw_list_multi_overlays(self):
        ov1 = self._make_overlay(self._ASCII)
        ov2 = self._make_overlay(self._ASCII)
        dl = build_draw_list({'r1': ov1, 'r2': ov2})
        self.assertEqual(len(dl), 4)

    def test_draw_list_empty_dict(self):
        dl = build_draw_list({})
        self.assertEqual(dl, [])

    def test_draw_entry_vertex_positions_match(self):
        ov = WalkmeshOverlay()
        ov.load_from_ascii_wok("""\
verts 3
  1.0 2.0 3.0
  4.0 5.0 6.0
  7.0 8.0 9.0
faces 1
  0 1 2 4
""")
        dl = build_draw_list({'r': ov})
        self.assertEqual(len(dl), 1)
        e = dl[0]
        self.assertAlmostEqual(e.v0[0], 1.0)
        self.assertAlmostEqual(e.v1[0], 4.0)
        self.assertAlmostEqual(e.v2[0], 7.0)


# ─────────────────────────────────────────────────────────────────────────────
# 12. World-offset correctness
# ─────────────────────────────────────────────────────────────────────────────

class TestWorldOffset(unittest.TestCase):

    def test_offset_applied_to_all_faces(self):
        wok_text = """\
verts 3
  0 0 0
  1 0 0
  0 1 0
faces 1
  0 1 2 1
"""
        ov = WalkmeshOverlay()
        ov.load_from_ascii_wok(wok_text, world_offset=(100.0, 200.0, 50.0))
        f = ov.faces[0]
        self.assertAlmostEqual(f.v0, (100.0, 200.0, 50.0))
        self.assertAlmostEqual(f.v1[0], 101.0)
        self.assertAlmostEqual(f.v2[1], 201.0)

    def test_negative_offset(self):
        wok_text = """\
verts 3
  5 5 5
  6 5 5
  5 6 5
faces 1
  0 1 2 1
"""
        ov = WalkmeshOverlay()
        ov.load_from_ascii_wok(wok_text, world_offset=(-5.0, -5.0, -5.0))
        f = ov.faces[0]
        self.assertAlmostEqual(f.v0[0], 0.0)
        self.assertAlmostEqual(f.v0[1], 0.0)
        self.assertAlmostEqual(f.v0[2], 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# 13. Edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases(unittest.TestCase):

    def test_unknown_surface_has_color(self):
        """Unknown surface IDs should still get a fallback color."""
        ov = WalkmeshOverlay()
        ov.load_from_ascii_wok("""\
verts 3
  0 0 0
  1 0 0
  0 1 0
faces 1
  0 1 2 255
""")
        self.assertEqual(len(ov.faces), 1)
        c = ov.faces[0].color
        self.assertEqual(len(c), 4)

    def test_non_walkable_color_is_prominent(self):
        """NON_WALK face should have visually prominent (high-alpha) color."""
        face = WalkmeshFace(
            v0=(0.0,0.0,0.0), v1=(1.0,0.0,0.0), v2=(0.0,1.0,0.0),
            surface=SURFACE_NON_WALK, walkable=False)
        r, g, b, a = face.color
        self.assertGreater(a, 0.5)

    def test_ascii_wok_empty_text(self):
        ov = WalkmeshOverlay()
        ov.load_from_ascii_wok("")
        self.assertEqual(len(ov.faces), 0)

    def test_ascii_wok_only_comments(self):
        ov = WalkmeshOverlay()
        ov.load_from_ascii_wok("# just a comment\n# another comment\n")
        self.assertEqual(len(ov.faces), 0)

    def test_wok_data_missing_verts_attr(self):
        """WOK data with no verts/faces attrs should not crash."""
        wok = SimpleNamespace()  # no .verts or .faces
        ov = WalkmeshOverlay()
        ov.load_from_wok(wok)
        self.assertEqual(len(ov.faces), 0)

    def test_walkmesh_face_default_surface(self):
        f = WalkmeshFace(v0=(0,0,0), v1=(1,0,0), v2=(0,1,0))
        self.assertEqual(f.surface, 0)  # SURFACE_INVALID

    def test_walkmesh_face_default_walkable(self):
        f = WalkmeshFace(v0=(0,0,0), v1=(1,0,0), v2=(0,1,0))
        self.assertTrue(f.walkable)  # default is True


if __name__ == '__main__':
    unittest.main(verbosity=2)
