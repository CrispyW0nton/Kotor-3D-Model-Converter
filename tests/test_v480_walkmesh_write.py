"""
test_v480_walkmesh_write.py — Phase 9.3/9.4: Walkmesh Write + Toggle
=====================================================================
Tests for:
  • WalkmeshWriter  (Phase 9.3 — walkmesh binary serialization)
  • WalkmeshToggleController  (Phase 9.4 — keyboard toggle)

Covers:
  WalkmeshWriter:
    • to_bytes() — produces valid BWM header (signature, version, counts)
    • Face vertex index round-trip
    • Material (surface) ID round-trip
    • Adjacency reconstruction
    • write_file() / write_wok_file() — disk I/O
    • roundtrip() — serialise → parse → compare face count
    • to_bytes_from_wok() — delegates to WOKData.to_bytes()
    • _compute_adjacency() — shared-edge detection
    • _pack() — buffer layout (offsets, sizes)
    • Empty overlay (zero faces)
    • Multi-face overlay
    • Mixed walkable/non-walkable materials

  WalkmeshToggleController:
    • toggle() — flips global visibility
    • on_key() — correct key consumed
    • on_key() — other key not consumed
    • toggle_room() — per-room visibility flip
    • set_all() — bulk show/hide
    • set_overlays() — replace overlay dict
    • set_key() — rebind key
    • visible property / setter
    • overlay_count
    • Sync propagated to WalkmeshOverlay.visible

All tests run headless (no rendering, no GPU required).
"""

import struct
import sys
import os
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.walkmesh_renderer import (
    WalkmeshOverlay, WalkmeshFace, WalkmeshLoader, WalkmeshWriter,
    WalkmeshToggleController, WalkmeshDrawEntry,
    SURFACE_INVALID, SURFACE_DIRT, SURFACE_NON_WALK, SURFACE_DOOR,
    SURFACE_GRASS, SURFACE_STONE, SURFACE_WATER,
    surface_color, surface_name,
)
from core.module_format import WOKData, WOKFace


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_simple_overlay(n_faces: int = 1, surface: int = SURFACE_DIRT) -> WalkmeshOverlay:
    """Build a WalkmeshOverlay with n_faces triangles."""
    overlay = WalkmeshOverlay()
    for i in range(n_faces):
        f = float(i)
        overlay.faces.append(WalkmeshFace(
            v0=(f,   0.0, 0.0),
            v1=(f+1, 0.0, 0.0),
            v2=(f,   1.0, 0.0),
            surface=surface,
            walkable=(surface not in (SURFACE_NON_WALK, SURFACE_INVALID)),
        ))
    return overlay


def _make_shared_edge_overlay() -> WalkmeshOverlay:
    """Two triangles sharing one edge — adjacency should find them."""
    overlay = WalkmeshOverlay()
    # Triangle 0: v(0,0,0), v(1,0,0), v(0,1,0)  — edge 0→1 shared with tri 1
    overlay.faces.append(WalkmeshFace(
        v0=(0,0,0), v1=(1,0,0), v2=(0,1,0), surface=SURFACE_DIRT))
    # Triangle 1: v(1,0,0), v(0,0,0), v(1,1,0)  — edge 1→0 shared with tri 0
    overlay.faces.append(WalkmeshFace(
        v0=(1,0,0), v1=(0,0,0), v2=(1,1,0), surface=SURFACE_STONE))
    return overlay


def _make_wok_data(n_faces: int = 2) -> WOKData:
    """Build a minimal WOKData object."""
    wok = WOKData(name="test")
    # Vertices: square (4 verts)
    wok.verts = [(0,0,0), (1,0,0), (1,1,0), (0,1,0)]
    for i in range(n_faces):
        adj1 = 1 if i == 0 else -1
        adj2 = -1
        adj3 = 0 if i == 1 else -1
        wok.faces.append(WOKFace(0, 1, 2, SURFACE_DIRT, adj1, adj2, adj3))
    return wok


def _parse_bwm_header(data: bytes) -> dict:
    """Parse the first 136 bytes of a BWM blob into a dict."""
    sig         = data[0:4]
    ver         = data[4:8]
    wok_type    = struct.unpack_from('<I', data, 8)[0]
    vert_count  = struct.unpack_from('<I', data, 56)[0]
    vert_offset = struct.unpack_from('<I', data, 60)[0]
    face_count  = struct.unpack_from('<I', data, 64)[0]
    face_offset = struct.unpack_from('<I', data, 68)[0]
    mat_offset  = struct.unpack_from('<I', data, 72)[0]
    adj_offset  = struct.unpack_from('<I', data, 76)[0]
    return dict(sig=sig, ver=ver, wok_type=wok_type,
                vert_count=vert_count, vert_offset=vert_offset,
                face_count=face_count, face_offset=face_offset,
                mat_offset=mat_offset, adj_offset=adj_offset)


# ─────────────────────────────────────────────────────────────────────────────
#  WalkmeshWriter — Binary Output Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestWalkmeshWriterBinary(unittest.TestCase):

    def test_signature(self):
        overlay = _make_simple_overlay(1)
        data = WalkmeshWriter().to_bytes(overlay)
        self.assertEqual(data[0:4], b'BWM ')

    def test_version(self):
        overlay = _make_simple_overlay(1)
        data = WalkmeshWriter().to_bytes(overlay)
        self.assertEqual(data[4:8], b'V1.0')

    def test_wok_type_room(self):
        overlay = _make_simple_overlay(1)
        data = WalkmeshWriter().to_bytes(overlay)
        h = _parse_bwm_header(data)
        self.assertEqual(h['wok_type'], 1)

    def test_face_count_one(self):
        overlay = _make_simple_overlay(1)
        data = WalkmeshWriter().to_bytes(overlay)
        h = _parse_bwm_header(data)
        self.assertEqual(h['face_count'], 1)

    def test_face_count_five(self):
        overlay = _make_simple_overlay(5)
        data = WalkmeshWriter().to_bytes(overlay)
        h = _parse_bwm_header(data)
        self.assertEqual(h['face_count'], 5)

    def test_vert_count_positive(self):
        overlay = _make_simple_overlay(1)
        data = WalkmeshWriter().to_bytes(overlay)
        h = _parse_bwm_header(data)
        self.assertGreater(h['vert_count'], 0)

    def test_header_size_136(self):
        """The data sections start after 136 bytes."""
        overlay = _make_simple_overlay(1)
        data = WalkmeshWriter().to_bytes(overlay)
        h = _parse_bwm_header(data)
        self.assertEqual(h['vert_offset'], 136)

    def test_face_offset_after_verts(self):
        overlay = _make_simple_overlay(1)
        data = WalkmeshWriter().to_bytes(overlay)
        h = _parse_bwm_header(data)
        expected_face_off = 136 + h['vert_count'] * 12
        self.assertEqual(h['face_offset'], expected_face_off)

    def test_mat_offset_after_faces(self):
        overlay = _make_simple_overlay(1)
        data = WalkmeshWriter().to_bytes(overlay)
        h = _parse_bwm_header(data)
        expected = h['face_offset'] + h['face_count'] * 6
        self.assertEqual(h['mat_offset'], expected)

    def test_adj_offset_after_mats(self):
        overlay = _make_simple_overlay(1)
        data = WalkmeshWriter().to_bytes(overlay)
        h = _parse_bwm_header(data)
        expected = h['mat_offset'] + h['face_count'] * 4
        self.assertEqual(h['adj_offset'], expected)

    def test_total_size_correct(self):
        overlay = _make_simple_overlay(2)
        data = WalkmeshWriter().to_bytes(overlay)
        h = _parse_bwm_header(data)
        expected = h['adj_offset'] + h['face_count'] * 12
        self.assertEqual(len(data), expected)

    def test_empty_overlay_valid(self):
        """Empty overlay should still produce a valid 136-byte header."""
        overlay = WalkmeshOverlay()
        data = WalkmeshWriter().to_bytes(overlay)
        h = _parse_bwm_header(data)
        self.assertEqual(h['face_count'], 0)
        self.assertEqual(h['vert_count'], 0)

    def test_material_id_round_trip(self):
        """Material ID must survive binary serialisation → re-parse."""
        for mat in (SURFACE_DIRT, SURFACE_NON_WALK, SURFACE_DOOR, SURFACE_GRASS):
            overlay = _make_simple_overlay(1, surface=mat)
            data = WalkmeshWriter().to_bytes(overlay)
            h = _parse_bwm_header(data)
            mat_val = struct.unpack_from('<I', data, h['mat_offset'])[0]
            self.assertEqual(mat_val, mat, f"material mismatch for surface {mat}")

    def test_vertex_position_round_trip(self):
        """A vertex at (3.0, 7.0, 0.0) must be recoverable from the blob."""
        overlay = WalkmeshOverlay()
        overlay.faces.append(WalkmeshFace(
            v0=(3.0, 7.0, 0.0), v1=(4.0, 7.0, 0.0), v2=(3.0, 8.0, 0.0),
            surface=SURFACE_DIRT))
        data  = WalkmeshWriter().to_bytes(overlay)
        h     = _parse_bwm_header(data)
        # Scan all verts to find (3.0, 7.0, 0.0)
        found = False
        for i in range(h['vert_count']):
            x, y, z = struct.unpack_from('<fff', data, h['vert_offset'] + i*12)
            if abs(x - 3.0) < 0.001 and abs(y - 7.0) < 0.001:
                found = True
        self.assertTrue(found)


# ─────────────────────────────────────────────────────────────────────────────
#  WalkmeshWriter — Adjacency Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestWalkmeshWriterAdjacency(unittest.TestCase):

    def test_isolated_triangle_no_adjacency(self):
        """A single isolated triangle has all adjacency = -1."""
        overlay = _make_simple_overlay(1)
        writer  = WalkmeshWriter()
        data    = writer.to_bytes(overlay)
        h       = _parse_bwm_header(data)
        a0, a1, a2 = struct.unpack_from('<iii', data, h['adj_offset'])
        self.assertEqual(a0, -1)
        self.assertEqual(a1, -1)
        self.assertEqual(a2, -1)

    def test_shared_edge_adjacency(self):
        """Two triangles sharing an edge should have one non-(-1) adjacency."""
        overlay = _make_shared_edge_overlay()
        writer  = WalkmeshWriter()
        data    = writer.to_bytes(overlay)
        h       = _parse_bwm_header(data)
        adjs_f0 = struct.unpack_from('<iii', data, h['adj_offset'])
        adjs_f1 = struct.unpack_from('<iii', data, h['adj_offset'] + 12)
        # At least one edge of face 0 should point to face 1
        self.assertTrue(any(a == 1 for a in adjs_f0) or any(a == 0 for a in adjs_f1))

    def test_compute_adjacency_static(self):
        """Static unit test for _compute_adjacency."""
        writer = WalkmeshWriter()
        # Triangle with shared edge: (0→1) in face 0, (1→0) in face 1
        faces = [(0, 1, 2), (1, 0, 3)]
        adjs  = writer._compute_adjacency(faces)
        # Face 0 edge (0→1) should be adjacent to face 1
        self.assertTrue(1 in adjs[0])


# ─────────────────────────────────────────────────────────────────────────────
#  WalkmeshWriter — WOKData delegation
# ─────────────────────────────────────────────────────────────────────────────

class TestWalkmeshWriterWOKData(unittest.TestCase):

    def test_to_bytes_from_wok_valid(self):
        wok  = _make_wok_data(2)
        data = WalkmeshWriter().to_bytes_from_wok(wok)
        self.assertEqual(data[0:4], b'BWM ')

    def test_to_bytes_from_wok_face_count(self):
        wok  = _make_wok_data(3)
        data = WalkmeshWriter().to_bytes_from_wok(wok)
        h    = _parse_bwm_header(data)
        self.assertEqual(h['face_count'], 3)


# ─────────────────────────────────────────────────────────────────────────────
#  WalkmeshWriter — Round-Trip Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestWalkmeshWriterRoundTrip(unittest.TestCase):

    def _roundtrip(self, overlay):
        return WalkmeshWriter.roundtrip(overlay)

    def test_roundtrip_face_count(self):
        overlay = _make_simple_overlay(4)
        rt      = self._roundtrip(overlay)
        self.assertEqual(len(rt.faces), len(overlay.faces))

    def test_roundtrip_surface_preserved(self):
        overlay = _make_simple_overlay(2, surface=SURFACE_WATER)
        rt      = self._roundtrip(overlay)
        for face in rt.faces:
            self.assertEqual(face.surface, SURFACE_WATER)

    def test_roundtrip_vertex_count_preserved(self):
        overlay = _make_simple_overlay(3)
        n_verts_orig = len(set(
            coord for f in overlay.faces
            for coord in (f.v0, f.v1, f.v2)))
        rt = self._roundtrip(overlay)
        n_verts_rt   = len(set(
            coord for f in rt.faces
            for coord in (f.v0, f.v1, f.v2)))
        self.assertEqual(n_verts_orig, n_verts_rt)

    def test_roundtrip_walkable_flag(self):
        overlay = _make_simple_overlay(1, surface=SURFACE_NON_WALK)
        rt      = self._roundtrip(overlay)
        # Non-walk surface → walkable should be False
        self.assertFalse(rt.faces[0].walkable)

    def test_roundtrip_empty(self):
        overlay = WalkmeshOverlay()
        rt      = self._roundtrip(overlay)
        self.assertEqual(len(rt.faces), 0)


# ─────────────────────────────────────────────────────────────────────────────
#  WalkmeshWriter — File I/O Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestWalkmeshWriterFileIO(unittest.TestCase):

    def test_write_file_creates_file(self):
        overlay = _make_simple_overlay(2)
        writer  = WalkmeshWriter()
        with tempfile.NamedTemporaryFile(suffix='.wok', delete=False) as f:
            path = f.name
        try:
            n = writer.write_file(overlay, path)
            self.assertGreater(n, 0)
            self.assertTrue(os.path.exists(path))
        finally:
            os.unlink(path)

    def test_write_file_byte_count(self):
        overlay = _make_simple_overlay(3)
        writer  = WalkmeshWriter()
        with tempfile.NamedTemporaryFile(suffix='.wok', delete=False) as f:
            path = f.name
        try:
            n       = writer.write_file(overlay, path)
            on_disk = os.path.getsize(path)
            self.assertEqual(n, on_disk)
        finally:
            os.unlink(path)

    def test_write_wok_file(self):
        wok    = _make_wok_data(2)
        writer = WalkmeshWriter()
        with tempfile.NamedTemporaryFile(suffix='.wok', delete=False) as f:
            path = f.name
        try:
            n = writer.write_wok_file(wok, path)
            self.assertGreater(n, 0)
        finally:
            os.unlink(path)


# ─────────────────────────────────────────────────────────────────────────────
#  WalkmeshToggleController Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestWalkmeshToggleController(unittest.TestCase):

    def _make_overlays(self, n=2) -> dict:
        return {f"room{i}": WalkmeshOverlay() for i in range(n)}

    def test_initial_visible_true(self):
        ctrl = WalkmeshToggleController()
        self.assertTrue(ctrl.visible)

    def test_toggle_flips_state(self):
        ctrl = WalkmeshToggleController()
        ctrl.toggle()
        self.assertFalse(ctrl.visible)

    def test_double_toggle_restores(self):
        ctrl = WalkmeshToggleController()
        ctrl.toggle()
        ctrl.toggle()
        self.assertTrue(ctrl.visible)

    def test_toggle_returns_new_state(self):
        ctrl = WalkmeshToggleController()
        result = ctrl.toggle()
        self.assertFalse(result)

    def test_on_key_w_consumed(self):
        ctrl = WalkmeshToggleController()
        consumed = ctrl.on_key('w')
        self.assertTrue(consumed)

    def test_on_key_w_uppercase_consumed(self):
        ctrl = WalkmeshToggleController()
        consumed = ctrl.on_key('W')
        self.assertTrue(consumed)

    def test_on_key_other_not_consumed(self):
        ctrl = WalkmeshToggleController()
        consumed = ctrl.on_key('x')
        self.assertFalse(consumed)

    def test_on_key_toggles_visibility(self):
        ctrl = WalkmeshToggleController()
        ctrl.on_key('w')
        self.assertFalse(ctrl.visible)

    def test_set_all_hide(self):
        ctrl = WalkmeshToggleController()
        ctrl.set_all(False)
        self.assertFalse(ctrl.visible)

    def test_set_all_show(self):
        ctrl = WalkmeshToggleController()
        ctrl.set_all(False)
        ctrl.set_all(True)
        self.assertTrue(ctrl.visible)

    def test_sync_to_overlays(self):
        overlays = self._make_overlays(2)
        ctrl = WalkmeshToggleController(overlays)
        ctrl.toggle()  # → False
        for ov in overlays.values():
            self.assertFalse(ov.visible)

    def test_sync_set_all_false(self):
        overlays = self._make_overlays(3)
        ctrl = WalkmeshToggleController(overlays)
        ctrl.set_all(False)
        for ov in overlays.values():
            self.assertFalse(ov.visible)

    def test_toggle_room(self):
        overlays = {'room0': WalkmeshOverlay(), 'room1': WalkmeshOverlay()}
        ctrl = WalkmeshToggleController(overlays)
        result = ctrl.toggle_room('room0')
        self.assertFalse(result)
        self.assertFalse(overlays['room0'].visible)
        self.assertTrue(overlays['room1'].visible)

    def test_toggle_room_nonexistent(self):
        ctrl = WalkmeshToggleController()
        result = ctrl.toggle_room('nonexistent')
        self.assertIsNone(result)

    def test_set_overlays_replaces(self):
        ctrl = WalkmeshToggleController()
        new_overlays = self._make_overlays(5)
        ctrl.set_overlays(new_overlays)
        self.assertEqual(ctrl.overlay_count, 5)

    def test_overlay_count(self):
        overlays = self._make_overlays(4)
        ctrl = WalkmeshToggleController(overlays)
        self.assertEqual(ctrl.overlay_count, 4)

    def test_set_key(self):
        ctrl = WalkmeshToggleController()
        ctrl.set_key('q')
        self.assertFalse(ctrl.on_key('w'))  # old key no longer active
        self.assertTrue(ctrl.on_key('q'))   # new key active

    def test_key_property(self):
        ctrl = WalkmeshToggleController(key='t')
        self.assertEqual(ctrl.key, 't')

    def test_visible_setter(self):
        overlays = self._make_overlays(2)
        ctrl = WalkmeshToggleController(overlays)
        ctrl.visible = False
        for ov in overlays.values():
            self.assertFalse(ov.visible)

    def test_no_overlays_toggle_safe(self):
        """Toggle with no overlays should not raise."""
        ctrl = WalkmeshToggleController()
        ctrl.toggle()
        ctrl.toggle()

    def test_set_overlays_syncs_visibility(self):
        """After set_overlays, new overlays get current state."""
        ctrl = WalkmeshToggleController()
        ctrl.set_all(False)
        new_overlays = self._make_overlays(2)
        ctrl.set_overlays(new_overlays)
        for ov in new_overlays.values():
            self.assertFalse(ov.visible)


if __name__ == '__main__':
    unittest.main()
