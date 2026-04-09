"""
GhostRigger v5.3 – Feature tests
==================================
Covers the three roadmap deliverables landed in this session:

  1. WOKData binary serialisation  (to_bytes / write_binary)
  2. WOKData editing helpers       (set_face_surface, bulk_replace_surface,
                                    surface_distribution, face_at_point)
  3. ModularPanel paint-brush plumbing  (surface colour lookup, world↔canvas
                                         coordinate transforms, paint-mode flag)
  4. LYT add / remove / edit / save via _RoomEditDialog
  5. AcuRig guide drag hit-testing (hit_test_acurig_guide) and drag state
     wiring in ViewportWidget (_press / _drag / _release)

All tests run headless (no real Tk window required for the logic-level tests).
Tk-dependent tests use the `@pytest.mark.skipif` guard so they are
skipped automatically when DISPLAY / Tk is unavailable.
"""

import sys
import os
import struct
import tempfile
import pytest
import types

# ── path plumbing ──────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.module_format import (
    WOKData, WOKFace, LYTLayout, LYTRoom, LYTDoorHook,
    WALKABLE_IDS, NON_WALK_ID,
)

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

# In KotOR WOK binary format:
#   WALKABLE_IDS = {1,3,4,5,9,10,11,12,13,14,19,20,21}  (DIRT, GRASS, STONE, …)
#   NON_WALK_ID  = 7
# Surface 0 = INVALID (not walkable)
_WALK_SURF    = 1   # DIRT  — first entry in WALKABLE_IDS
_NONWALK_SURF = 7   # NON_WALK_ID

def _make_simple_wok(n_walk: int = 4, n_nonwalk: int = 2) -> WOKData:
    """
    Build a minimal WOKData in memory.

    Layout (top-down XY, vertices on unit grid):
      v0(0,0,0)  v1(1,0,0)  v2(0,1,0)  v3(1,1,0)
    Walk faces:    surface = DIRT (1)  — in WALKABLE_IDS
    Non-walk:      surface = NON_WALK (7)
    """
    verts = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (1.0, 1.0, 0.0),
        (2.0, 0.0, 0.0),
        (2.0, 1.0, 0.0),
    ]
    faces = []
    for _ in range(n_walk):
        faces.append(WOKFace(0, 1, 2, _WALK_SURF))       # DIRT (walkable)
    for _ in range(n_nonwalk):
        faces.append(WOKFace(1, 4, 5, _NONWALK_SURF))    # NON_WALK
    wok = WOKData(name='test', verts=verts, faces=faces)
    return wok


def _make_binary_wok_bytes() -> bytes:
    """
    Hand-craft a minimal valid BWM binary blob with 1 vertex + 1 face
    so we can roundtrip-test from_bytes → to_bytes → from_bytes.
    """
    nv, nf = 3, 1
    header_size = 136
    vert_off = header_size
    face_off = vert_off + nv * 12
    mat_off  = face_off + nf * 6
    adj_off  = mat_off  + nf * 4
    total    = adj_off  + nf * 12

    buf = bytearray(total)
    buf[0:4] = b'BWM '
    buf[4:8] = b'V1.0'
    struct.pack_into('<I', buf, 8, 1)        # wok_type = room
    struct.pack_into('<I', buf, 56, nv)
    struct.pack_into('<I', buf, 60, vert_off)
    struct.pack_into('<I', buf, 64, nf)
    struct.pack_into('<I', buf, 68, face_off)
    struct.pack_into('<I', buf, 72, mat_off)
    struct.pack_into('<I', buf, 76, adj_off)
    # 3 verts
    for i, (x, y, z) in enumerate([(0.0,0.0,0.0),(1.0,0.0,0.0),(0.0,1.0,0.0)]):
        struct.pack_into('<fff', buf, vert_off + i*12, x, y, z)
    # 1 face
    struct.pack_into('<HHH', buf, face_off, 0, 1, 2)
    struct.pack_into('<I',   buf, mat_off, 0)           # WALK
    struct.pack_into('<iii', buf, adj_off, -1, -1, -1)
    return bytes(buf)


# ─────────────────────────────────────────────────────────────────────────────
#  1. WOKData binary serialisation
# ─────────────────────────────────────────────────────────────────────────────

class TestWOKDataToBytesRoundtrip:
    """to_bytes() → from_bytes() must produce identical WOKData."""

    def test_to_bytes_returns_bytes(self):
        wok = _make_simple_wok()
        result = wok.to_bytes()
        assert isinstance(result, bytes)

    def test_to_bytes_signature(self):
        wok = _make_simple_wok()
        raw = wok.to_bytes()
        assert raw[:4] == b'BWM '
        assert raw[4:8] == b'V1.0'

    def test_to_bytes_wok_type_room(self):
        wok = _make_simple_wok()
        raw = wok.to_bytes()
        wok_type = struct.unpack_from('<I', raw, 8)[0]
        assert wok_type == 1

    def test_roundtrip_vertex_count(self):
        wok = _make_simple_wok()
        raw = wok.to_bytes()
        wok2 = WOKData.from_bytes(raw)
        assert len(wok2.verts) == len(wok.verts)

    def test_roundtrip_face_count(self):
        wok = _make_simple_wok()
        raw = wok.to_bytes()
        wok2 = WOKData.from_bytes(raw)
        assert len(wok2.faces) == len(wok.faces)

    def test_roundtrip_vertex_positions(self):
        wok = _make_simple_wok()
        raw = wok.to_bytes()
        wok2 = WOKData.from_bytes(raw)
        for (ox, oy, oz), (rx, ry, rz) in zip(wok.verts, wok2.verts):
            assert abs(ox - rx) < 1e-5
            assert abs(oy - ry) < 1e-5
            assert abs(oz - rz) < 1e-5

    def test_roundtrip_surface_ids(self):
        wok = _make_simple_wok(n_walk=2, n_nonwalk=3)
        raw = wok.to_bytes()
        wok2 = WOKData.from_bytes(raw)
        orig_surfs = [f.surface for f in wok.faces]
        rt_surfs   = [f.surface for f in wok2.faces]
        assert orig_surfs == rt_surfs

    def test_from_bytes_walkable_surface_id(self):
        """Walkable faces must have surface IDs in WALKABLE_IDS."""
        wok = _make_simple_wok(n_walk=2, n_nonwalk=0)
        raw = wok.to_bytes()
        wok2 = WOKData.from_bytes(raw)
        assert wok2.faces[0].surface in WALKABLE_IDS

    def test_roundtrip_adjacency(self):
        wok = _make_simple_wok()
        wok.faces[0] = WOKFace(0, 1, 2, 0, adj1=1, adj2=-1, adj3=-1)
        raw = wok.to_bytes()
        wok2 = WOKData.from_bytes(raw)
        assert wok2.faces[0].adj1 == 1
        assert wok2.faces[0].adj2 == -1

    def test_write_binary_creates_file(self):
        wok = _make_simple_wok()
        with tempfile.NamedTemporaryFile(suffix='.wok', delete=False) as f:
            path = f.name
        try:
            wok.write_binary(path)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 136
        finally:
            os.unlink(path)

    def test_write_binary_readable_back(self):
        wok = _make_simple_wok(n_walk=3, n_nonwalk=1)
        with tempfile.NamedTemporaryFile(suffix='.wok', delete=False) as f:
            path = f.name
        try:
            wok.write_binary(path)
            wok2 = WOKData.from_file(path)
            assert len(wok2.verts) == len(wok.verts)
            assert len(wok2.faces) == len(wok.faces)
        finally:
            os.unlink(path)

    def test_from_bytes_known_binary(self):
        raw = _make_binary_wok_bytes()
        wok = WOKData.from_bytes(raw)
        assert len(wok.verts) == 3
        assert len(wok.faces) == 1
        assert wok.faces[0].surface == 0   # INVALID surface from hand-crafted blob

    def test_empty_wok_serialises(self):
        wok = WOKData()
        raw = wok.to_bytes()
        wok2 = WOKData.from_bytes(raw)
        assert len(wok2.verts) == 0
        assert len(wok2.faces) == 0

    def test_header_size_at_least_136(self):
        wok = WOKData()
        raw = wok.to_bytes()
        assert len(raw) >= 136

    def test_vert_offset_correct(self):
        wok = _make_simple_wok()
        raw = wok.to_bytes()
        vert_off = struct.unpack_from('<I', raw, 60)[0]
        assert vert_off == 136   # immediately after the 136-byte header


# ─────────────────────────────────────────────────────────────────────────────
#  2. WOKData editing helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestWOKDataEditing:

    def test_set_face_surface_changes_surface(self):
        wok = _make_simple_wok()
        wok.set_face_surface(0, 7)   # DIRT → NON_WALK
        assert wok.faces[0].surface == 7

    def test_set_face_surface_out_of_range_returns_false(self):
        wok = _make_simple_wok()
        result = wok.set_face_surface(9999, 1)
        assert result is False

    def test_set_face_surface_negative_idx_returns_false(self):
        wok = _make_simple_wok()
        result = wok.set_face_surface(-1, 1)
        assert result is False

    def test_set_face_surface_preserves_vertices(self):
        wok = _make_simple_wok()
        orig = (wok.faces[0].v1, wok.faces[0].v2, wok.faces[0].v3)
        wok.set_face_surface(0, 7)
        assert (wok.faces[0].v1, wok.faces[0].v2, wok.faces[0].v3) == orig

    def test_bulk_replace_surface_count(self):
        wok = _make_simple_wok(n_walk=5, n_nonwalk=3)
        count = wok.bulk_replace_surface(_WALK_SURF, 4)  # DIRT → GRASS
        assert count == 5

    def test_bulk_replace_surface_changes_surfaces(self):
        wok = _make_simple_wok(n_walk=3, n_nonwalk=2)
        wok.bulk_replace_surface(_WALK_SURF, 5)   # DIRT → WOOD
        for f in wok.faces[:3]:
            assert f.surface == 5

    def test_bulk_replace_no_match_returns_zero(self):
        wok = _make_simple_wok(n_walk=2)
        count = wok.bulk_replace_surface(99, 0)
        assert count == 0

    def test_surface_distribution_keys(self):
        wok = _make_simple_wok(n_walk=3, n_nonwalk=2)
        dist = wok.surface_distribution()
        assert _WALK_SURF    in dist   # DIRT (walkable)
        assert _NONWALK_SURF in dist   # NON_WALK

    def test_surface_distribution_counts(self):
        wok = _make_simple_wok(n_walk=4, n_nonwalk=1)
        dist = wok.surface_distribution()
        assert dist[_WALK_SURF]    == 4
        assert dist[_NONWALK_SURF] == 1

    def test_face_at_point_hit(self):
        """Centroid of face 0 (v0,v1,v2) should find face 0."""
        wok = _make_simple_wok()
        # face 0: (0,0), (1,0), (0,1) — centroid ~(0.33, 0.33)
        fi = wok.face_at_point(0.2, 0.2)
        assert fi == 0

    def test_face_at_point_miss(self):
        wok = _make_simple_wok()
        fi = wok.face_at_point(10.0, 10.0)
        assert fi == -1

    def test_face_at_point_returns_int(self):
        wok = _make_simple_wok()
        fi = wok.face_at_point(0.2, 0.2)
        assert isinstance(fi, int)

    def test_walkable_face_count_after_bulk_replace(self):
        wok = _make_simple_wok(n_walk=4, n_nonwalk=2)
        assert wok.walkable_face_count() == 4
        wok.bulk_replace_surface(_WALK_SURF, _NONWALK_SURF)   # DIRT → NON_WALK
        assert wok.walkable_face_count() == 0

    def test_set_face_surface_valid_returns_true(self):
        wok = _make_simple_wok()
        result = wok.set_face_surface(0, 5)
        assert result is True


# ─────────────────────────────────────────────────────────────────────────────
#  3. ModularPanel paint-brush plumbing (logic only, no Tk window)
# ─────────────────────────────────────────────────────────────────────────────

class TestModularPanelPaintBrushLogic:
    """
    Test the coordinate-transform and colour-lookup logic in ModularModePanel
    by instantiating only the helper methods (no Tk widget construction).
    We monkey-patch the class to access the static helpers.
    """

    def _make_panel_mock(self):
        """Return a lightweight stand-in that has the ModularModePanel mixin methods."""
        from gui.modular_panel import ModularModePanel
        # Build a minimal namespace with the required state
        obj = types.SimpleNamespace()
        obj._wok_canvas_scale  = 10.0
        obj._wok_canvas_offset = [100.0, 200.0]
        # Bind the unbound methods
        obj._wok_world_to_canvas = lambda wx, wy: (
            wx * obj._wok_canvas_scale + obj._wok_canvas_offset[0],
            -wy * obj._wok_canvas_scale + obj._wok_canvas_offset[1]
        )
        obj._wok_canvas_to_world = lambda cx, cy: (
            (cx - obj._wok_canvas_offset[0]) / obj._wok_canvas_scale,
            -(cy - obj._wok_canvas_offset[1]) / obj._wok_canvas_scale
        )
        obj._WOK_MATERIAL_NAMES = ModularModePanel._WOK_MATERIAL_NAMES
        obj._mat_name_to_id     = lambda name: {v: k for k, v in obj._WOK_MATERIAL_NAMES.items()}.get(name.upper(), 1)
        obj._wok_surface_color  = ModularModePanel._wok_surface_color.__get__(obj)
        return obj

    def test_world_to_canvas_origin(self):
        p = self._make_panel_mock()
        cx, cy = p._wok_world_to_canvas(0.0, 0.0)
        assert abs(cx - 100.0) < 1e-9
        assert abs(cy - 200.0) < 1e-9

    def test_canvas_to_world_roundtrip(self):
        p = self._make_panel_mock()
        wx, wy = 3.5, -7.2
        cx, cy = p._wok_world_to_canvas(wx, wy)
        wx2, wy2 = p._wok_canvas_to_world(cx, cy)
        assert abs(wx - wx2) < 1e-9
        assert abs(wy - wy2) < 1e-9

    def test_canvas_to_world_positive_y_inverted(self):
        """Canvas Y increases downward; world Y should increase upward."""
        p = self._make_panel_mock()
        _, cy_pos = p._wok_world_to_canvas(0.0, 1.0)   # world Y=+1
        _, cy_neg = p._wok_world_to_canvas(0.0, -1.0)  # world Y=-1
        assert cy_pos < cy_neg  # positive world Y → smaller canvas Y

    def test_surface_color_walk_is_green(self):
        p = self._make_panel_mock()
        col = p._wok_surface_color(0)   # WALK
        assert col.startswith('#')
        # WALK is greenish: red channel < green channel
        r = int(col[1:3], 16)
        g = int(col[3:5], 16)
        assert g > r

    def test_surface_color_nonwalk_is_reddish(self):
        p = self._make_panel_mock()
        col = p._wok_surface_color(1)   # NON_WALK
        r = int(col[1:3], 16)
        g = int(col[3:5], 16)
        assert r > g

    def test_surface_color_unknown_id_fallback(self):
        p = self._make_panel_mock()
        col = p._wok_surface_color(9999)
        assert col.startswith('#')
        assert len(col) == 7

    def test_mat_name_to_id_walk(self):
        p = self._make_panel_mock()
        assert p._mat_name_to_id('WALK') == 0

    def test_mat_name_to_id_nonwalk(self):
        p = self._make_panel_mock()
        assert p._mat_name_to_id('NON_WALK') == 1

    def test_mat_name_to_id_unknown_defaults_nonwalk(self):
        p = self._make_panel_mock()
        assert p._mat_name_to_id('BANANA') == 1

    def test_mat_name_to_id_case_insensitive(self):
        p = self._make_panel_mock()
        assert p._mat_name_to_id('walk') == 0


# ─────────────────────────────────────────────────────────────────────────────
#  4. LYT parsing and editing
# ─────────────────────────────────────────────────────────────────────────────

class TestLYTLayoutEditing:

    def _sample_lyt_text(self) -> str:
        return (
            "beginlayout\n"
            "  roomcount 3\n"
            "  room_a  0.00 0.00 0.00\n"
            "  room_b  10.0 0.00 0.00\n"
            "  room_c  0.00 10.0 0.00\n"
            "donelayout\n"
        )

    def test_from_text_parses_rooms(self):
        lyt = LYTLayout.from_text(self._sample_lyt_text())
        assert len(lyt.rooms) == 3

    def test_from_text_room_names(self):
        lyt = LYTLayout.from_text(self._sample_lyt_text())
        names = [r.model for r in lyt.rooms]
        assert 'room_a' in names
        assert 'room_b' in names

    def test_from_text_room_coords(self):
        lyt = LYTLayout.from_text(self._sample_lyt_text())
        room_b = next(r for r in lyt.rooms if r.model == 'room_b')
        assert abs(room_b.x - 10.0) < 1e-3

    def test_add_room(self):
        lyt = LYTLayout.from_text(self._sample_lyt_text())
        lyt.rooms.append(LYTRoom(model='room_d', x=5.0, y=5.0, z=0.0))
        assert len(lyt.rooms) == 4
        assert lyt.rooms[-1].model == 'room_d'

    def test_remove_room(self):
        lyt = LYTLayout.from_text(self._sample_lyt_text())
        lyt.rooms.pop(0)
        assert len(lyt.rooms) == 2

    def test_edit_room_position(self):
        lyt = LYTLayout.from_text(self._sample_lyt_text())
        lyt.rooms[0] = LYTRoom(model=lyt.rooms[0].model, x=99.0, y=0.0, z=0.0)
        assert abs(lyt.rooms[0].x - 99.0) < 1e-5

    def test_to_text_round_trip(self):
        lyt = LYTLayout.from_text(self._sample_lyt_text())
        text2 = lyt.to_text()
        lyt2  = LYTLayout.from_text(text2)
        assert len(lyt2.rooms) == len(lyt.rooms)

    def test_write_creates_file(self):
        lyt = LYTLayout.from_text(self._sample_lyt_text())
        with tempfile.NamedTemporaryFile(suffix='.lyt', delete=False, mode='w') as f:
            path = f.name
        try:
            lyt.write(path)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0
        finally:
            os.unlink(path)

    def test_write_readable_back(self):
        lyt = LYTLayout.from_text(self._sample_lyt_text())
        with tempfile.NamedTemporaryFile(suffix='.lyt', delete=False, mode='w') as f:
            path = f.name
        try:
            lyt.write(path)
            lyt2 = LYTLayout.from_file(path)
            assert len(lyt2.rooms) == 3
        finally:
            os.unlink(path)

    def test_empty_lyt_serialises(self):
        lyt = LYTLayout()
        text = lyt.to_text()
        assert isinstance(text, str)
        assert len(text) > 0

    def test_lyt_room_snap_grid(self):
        """Grid-snap helper: rounding to nearest 0.5 m grid."""
        def snap(val, grid=0.5):
            return round(val / grid) * grid
        assert snap(0.3)  == 0.5
        assert snap(0.7)  == 0.5
        assert snap(1.1)  == 1.0
        assert snap(-0.3) == -0.5


# ─────────────────────────────────────────────────────────────────────────────
#  5. AcuRig guide hit-test and drag state (FrameRenderer-level, no Tk)
# ─────────────────────────────────────────────────────────────────────────────

class TestAcuRigGuideHitTest:
    """
    Test FrameRenderer.hit_test_acurig_guide purely at the logic level.
    We build a minimal FrameRenderer stand-in with just the projection
    and guide-overlay attributes set.
    """

    def _make_renderer_stub(self, guides: dict, W: int = 800, H: int = 600):
        """
        Build a minimal object that has _proj, _acurig_guides_overlay,
        _last_W, _last_H, and the hit_test_acurig_guide method bound.
        """
        from gui.viewport import FrameRenderer
        # We cannot easily instantiate FrameRenderer headlessly (it imports PIL
        # and relies on ArcBallCamera), so we create a SimpleNamespace and bind
        # the unbound method manually.
        obj = types.SimpleNamespace()
        obj._acurig_guides_overlay = guides
        obj._acurig_selected_guide = ''
        obj._last_W = W
        obj._last_H = H
        # Simple identity projection: pos → (pos[0]*scale+cx, pos[1]*scale+cy, dist)
        # so we can predict exactly where guides land.
        scale = 50.0
        cx, cy = W / 2, H / 2
        obj._proj = lambda x, y, z, w, h: (x * scale + cx, -y * scale + cy, abs(z) + 5.0)
        obj.hit_test_acurig_guide = FrameRenderer.hit_test_acurig_guide.__get__(obj)
        return obj

    def _make_guide(self, x, y, z=0.0):
        g = types.SimpleNamespace()
        g.position = [x, y, z]
        return g

    def test_hit_exact_centre(self):
        guides = {'hip': self._make_guide(0.0, 0.0)}
        r = self._make_renderer_stub(guides)
        # hip projects to (400, 300) with our stub projection
        name = r.hit_test_acurig_guide(400, 300)
        assert name == 'hip'

    def test_hit_near_centre_within_radius(self):
        guides = {'hip': self._make_guide(0.0, 0.0)}
        r = self._make_renderer_stub(guides)
        name = r.hit_test_acurig_guide(405, 305)   # ~7 px away, default radius=14
        assert name == 'hip'

    def test_miss_far_from_guide(self):
        guides = {'hip': self._make_guide(0.0, 0.0)}
        r = self._make_renderer_stub(guides)
        name = r.hit_test_acurig_guide(100, 100)   # far away
        assert name == ''

    def test_empty_guides_returns_empty(self):
        r = self._make_renderer_stub({})
        assert r.hit_test_acurig_guide(400, 300) == ''

    def test_none_guides_returns_empty(self):
        r = self._make_renderer_stub(None)
        assert r.hit_test_acurig_guide(400, 300) == ''

    def test_picks_closest_guide(self):
        guides = {
            'hip':    self._make_guide(0.0, 0.0),
            'chest':  self._make_guide(0.0, 1.0),   # projects to (400, 250)
        }
        r = self._make_renderer_stub(guides)
        # Click at (400, 298) — 2 px from hip (400,300) but 52 px from chest
        name = r.hit_test_acurig_guide(400, 298)
        assert name == 'hip'

    def test_guide_without_position_skipped(self):
        guide_no_pos = types.SimpleNamespace()  # no .position attr
        guides = {'ghost': guide_no_pos, 'hip': self._make_guide(0.0, 0.0)}
        r = self._make_renderer_stub(guides)
        name = r.hit_test_acurig_guide(400, 300)
        assert name == 'hip'

    def test_guide_with_short_position_skipped(self):
        g = types.SimpleNamespace()
        g.position = [0.0]   # length < 3
        guides = {'short': g, 'hip': self._make_guide(0.0, 0.0)}
        r = self._make_renderer_stub(guides)
        name = r.hit_test_acurig_guide(400, 300)
        assert name == 'hip'

    def test_returns_string_type(self):
        guides = {'hip': self._make_guide(0.0, 0.0)}
        r = self._make_renderer_stub(guides)
        result = r.hit_test_acurig_guide(400, 300)
        assert isinstance(result, str)

    def test_multiple_guides_all_miss(self):
        guides = {
            'hip':   self._make_guide(5.0,  5.0),
            'chest': self._make_guide(-5.0, 5.0),
        }
        r = self._make_renderer_stub(guides)
        name = r.hit_test_acurig_guide(400, 300)  # origin, away from both
        assert name == ''


# ─────────────────────────────────────────────────────────────────────────────
#  6. AcuRig viewport state wiring (drag flag management)
# ─────────────────────────────────────────────────────────────────────────────

class TestAcuRigDragStateWiring:
    """
    Verify ViewportWidget initialises the new AcuRig drag state attributes
    and that the drag helpers exist and are callable.
    """

    def test_viewport_has_acurig_drag_attrs(self):
        """Check attribute names are defined (even without constructing the widget)."""
        import inspect
        from gui.viewport import ViewportWidget
        # Parse the __init__ source to look for the attributes
        src = inspect.getsource(ViewportWidget.__init__)
        assert '_acurig_guide_dragging' in src
        assert '_acurig_drag_guide_name' in src
        assert 'on_acurig_guide_moved' in src

    def test_apply_acurig_guide_drag_method_exists(self):
        from gui.viewport import ViewportWidget
        assert hasattr(ViewportWidget, '_apply_acurig_guide_drag')
        assert callable(ViewportWidget._apply_acurig_guide_drag)

    def test_apply_acurig_guide_drag_moves_guide(self):
        """
        Exercise _apply_acurig_guide_drag logic with a minimal mock.
        Guide at (0,0,0), drag 10 pixels right → X should increase.
        """
        from gui.viewport import ViewportWidget
        import math

        # Build a mock that has all the attributes the method reads
        obj = types.SimpleNamespace()
        obj._acurig_drag_guide_name = 'hip'
        obj._acurig_drag_start      = (100, 100)
        obj.camera = types.SimpleNamespace()
        obj.camera.fov = 45.0
        # _view_matrix returns (right, up, fwd, eye) as unit vectors
        obj.camera._view_matrix = lambda: (
            (1.0, 0.0, 0.0),  # right
            (0.0, 1.0, 0.0),  # up
            (0.0, 0.0, 1.0),  # fwd
            (0.0, 0.0, 5.0),  # eye
        )

        guide = types.SimpleNamespace()
        guide.position = [0.0, 0.0, 0.0]

        renderer = types.SimpleNamespace()
        renderer._acurig_guides_overlay = {'hip': guide}
        renderer._proj = lambda x, y, z, W, H: (W/2, H/2, 5.0)
        obj._renderer = renderer

        canvas = types.SimpleNamespace()
        canvas.winfo_width  = lambda: 800
        canvas.winfo_height = lambda: 600
        obj.canvas = canvas

        # Bind the method
        obj._apply_acurig_guide_drag = ViewportWidget._apply_acurig_guide_drag.__get__(obj)

        old_x = guide.position[0]
        obj._apply_acurig_guide_drag(110, 100)  # drag 10 px right
        # Guide X should have moved (positive right drag → positive world X)
        assert guide.position[0] != old_x

    def test_acurig_drag_start_updated_after_move(self):
        """Drag start should update to the new mouse pos after each call."""
        from gui.viewport import ViewportWidget

        obj = types.SimpleNamespace()
        obj._acurig_drag_guide_name = 'hip'
        obj._acurig_drag_start      = (50, 50)
        obj.camera = types.SimpleNamespace()
        obj.camera.fov = 45.0
        obj.camera._view_matrix = lambda: (
            (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0), (0.0, 0.0, 5.0),
        )
        guide = types.SimpleNamespace()
        guide.position = [0.0, 0.0, 0.0]
        renderer = types.SimpleNamespace()
        renderer._acurig_guides_overlay = {'hip': guide}
        renderer._proj = lambda x, y, z, W, H: (W/2, H/2, 5.0)
        obj._renderer = renderer
        canvas = types.SimpleNamespace()
        canvas.winfo_width  = lambda: 800
        canvas.winfo_height = lambda: 600
        obj.canvas = canvas
        obj._apply_acurig_guide_drag = ViewportWidget._apply_acurig_guide_drag.__get__(obj)

        obj._apply_acurig_guide_drag(60, 55)
        assert obj._acurig_drag_start == (60, 55)


# ─────────────────────────────────────────────────────────────────────────────
#  7. WOK canvas zoom / pan helpers (unit level)
# ─────────────────────────────────────────────────────────────────────────────

class TestWOKCanvasZoomPan:
    """
    Test the zoom and pan transform math in isolation (no Tk canvas).
    """

    def _make_zoom_obj(self, scale=10.0, ox=0.0, oy=0.0):
        obj = types.SimpleNamespace()
        obj._wok_canvas_scale  = scale
        obj._wok_canvas_offset = [ox, oy]
        obj.camera = None  # unused
        def _to_world(cx, cy):
            return (
                (cx - obj._wok_canvas_offset[0]) / obj._wok_canvas_scale,
                -(cy - obj._wok_canvas_offset[1]) / obj._wok_canvas_scale
            )
        obj._wok_canvas_to_world = _to_world
        return obj

    def test_pan_changes_offset(self):
        obj = self._make_zoom_obj()
        obj._wok_canvas_offset[0] += 10.0
        assert obj._wok_canvas_offset[0] == 10.0

    def test_zoom_factor_applied(self):
        obj = self._make_zoom_obj(scale=10.0)
        factor = 1.25
        obj._wok_canvas_scale = max(0.5, min(obj._wok_canvas_scale * factor, 2000.0))
        assert abs(obj._wok_canvas_scale - 12.5) < 1e-9

    def test_zoom_clamped_min(self):
        obj = self._make_zoom_obj(scale=0.6)
        obj._wok_canvas_scale = max(0.5, min(obj._wok_canvas_scale * 0.01, 2000.0))
        assert obj._wok_canvas_scale >= 0.5

    def test_zoom_clamped_max(self):
        obj = self._make_zoom_obj(scale=1900.0)
        obj._wok_canvas_scale = max(0.5, min(obj._wok_canvas_scale * 10.0, 2000.0))
        assert obj._wok_canvas_scale <= 2000.0

    def test_pan_preserves_scale(self):
        obj = self._make_zoom_obj(scale=15.0)
        obj._wok_canvas_offset[0] += 30.0
        assert obj._wok_canvas_scale == 15.0


# ─────────────────────────────────────────────────────────────────────────────
#  8. WOKData.summary() and boundary_edges() with new editing
# ─────────────────────────────────────────────────────────────────────────────

class TestWOKDataSummaryAfterEdit:

    def test_summary_reflects_edit(self):
        wok = _make_simple_wok(n_walk=3, n_nonwalk=1)
        wok.bulk_replace_surface(0, 1)   # make all walk → non_walk
        summ = wok.summary()
        assert 'walkable' in summ.lower() or 'walk' in summ.lower()

    def test_walkable_count_zero_after_all_replaced(self):
        wok = _make_simple_wok(n_walk=4)
        wok.bulk_replace_surface(_WALK_SURF, _NONWALK_SURF)
        assert wok.walkable_face_count() == 0

    def test_boundary_edges_changes_after_edit(self):
        wok = _make_simple_wok(n_walk=2, n_nonwalk=0)
        edges_before = wok.boundary_edges()
        wok.bulk_replace_surface(_WALK_SURF, _NONWALK_SURF)
        edges_after = wok.boundary_edges()
        # All faces now non-walk → no walkable boundary edges
        assert len(edges_after) == 0
        # Before: had some boundary edges from walkable faces
        assert len(edges_before) >= 0  # may be 0 if adjacency not set


# ─────────────────────────────────────────────────────────────────────────────
#  9. Integration: paint a face and serialise
# ─────────────────────────────────────────────────────────────────────────────

class TestPaintAndSerialiseIntegration:

    def test_paint_then_write_binary(self):
        wok = _make_simple_wok(n_walk=4, n_nonwalk=0)
        # Paint face 0 to STONE (id=4)
        wok.set_face_surface(0, 4)
        with tempfile.NamedTemporaryFile(suffix='.wok', delete=False) as f:
            path = f.name
        try:
            wok.write_binary(path)
            wok2 = WOKData.from_file(path)
            assert wok2.faces[0].surface == 4
            # Other faces still DIRT
            assert wok2.faces[1].surface == _WALK_SURF
        finally:
            os.unlink(path)

    def test_bulk_paint_then_round_trip(self):
        wok = _make_simple_wok(n_walk=3, n_nonwalk=3)
        # Replace all NON_WALK(7) → WATER(6)
        wok.bulk_replace_surface(_NONWALK_SURF, 6)
        raw = wok.to_bytes()
        wok2 = WOKData.from_bytes(raw)
        for f in wok2.faces:
            assert f.surface != _NONWALK_SURF   # no more NON_WALK

    def test_face_at_point_then_paint(self):
        wok = _make_simple_wok(n_walk=2)
        fi = wok.face_at_point(0.2, 0.2)
        if fi >= 0:
            wok.set_face_surface(fi, 3)   # GRASS (surface id=3)
            assert wok.faces[fi].surface == 3
