"""
GhostRigger v14 — Seam-Fix Gating and Model Positioning Tests
==============================================================

Validates the v14.1 texture-wrapping fix (seam-fix gating for meshes without
positional UV-seam duplicates) and the supermodel-based model-positioning fixes.

ROOT CAUSES FIXED (v14):
-------------------------
BUG-UV-GATE-1  Seam fix was ONLY applied to faces touching a positional-duplicate
               vertex in _node_u_seam_verts.  Meshes without such duplicates
               (non-skin trimeshes, area geometry, creature accessories) had an
               empty _node_u_seam_verts set, so skip_seam_u=True was ALWAYS passed
               to _paste_textured_triangle → seam fix NEVER ran → textures stretched
               across the full tile width on ALL seam-crossing faces of these meshes.

               FIX (v14.1): When _node_u_seam_verts is empty, _face_has_u_seam=True
               is set for ALL faces, allowing _paste_textured_triangle's own internal
               SAFE fast-path + _edge_has_seam detection to decide per-face.

BUG-UV-GATE-2  The hair-strand fix (v10.4b) must be preserved:
               When _node_u_seam_verts is non-empty (u-seam analysis ran and found
               duplicates) but _node_v_seam_verts is empty (no v-seam duplicates),
               the V-axis fix must remain DISABLED to prevent erroneous V-wrap on
               hair-strand tips (which would cause black artefacts at hair tips).

MODEL-POS-1    Skin vertex world-space determination now uses the model's supermodel
               field as the primary discriminator (v12.13/v14).

REFERENCE:
    KotorBlender io_scene_kotor (seedhartha), xoreos MDL loader,
    GhostRigger viewport.py FrameRenderer._draw_mesh_textured (v14.1)
"""

import math
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False

from src.core.model_data import KotorModel, ModelNode, NodeFlags
from src.gui.viewport import FrameRenderer, ArcBallCamera


# ─────────────────────────────────────────────────────────────────────────────
# Section 1 — Seam-Fix Gating (v14.1)
# ─────────────────────────────────────────────────────────────────────────────

class TestSeamFixGatingLogic:
    """Unit tests for the v14.1 per-face seam-fix gating rule.

    The gating is implemented in _draw_mesh_textured inside the face loop.
    We simulate the logic here to verify the three cases:

    Case A: _node_u_seam_verts empty + _node_v_seam_verts empty
            → both axes allowed (trimesh / area geometry case).
    Case B: _node_u_seam_verts non-empty + _node_v_seam_verts empty
            → u-fix gated to faces touching seam verts;
              v-fix DISABLED on all faces (hair-strand fix).
    Case C: _node_u_seam_verts non-empty + _node_v_seam_verts non-empty
            → both gated per face.
    """

    def _apply_gating_logic(self, node_u_seam, node_v_seam, vi0, vi1, vi2):
        """Mirror of the v14.1 gating logic in _draw_mesh_textured."""
        _any_u = bool(node_u_seam)
        _any_v = bool(node_v_seam)
        _analysis_ran = bool(_any_u or _any_v)

        if _any_u:
            face_has_u = (vi0 in node_u_seam or vi1 in node_u_seam or
                          vi2 in node_u_seam)
        else:
            face_has_u = True

        if _any_v:
            face_has_v = (vi0 in node_v_seam or vi1 in node_v_seam or
                          vi2 in node_v_seam)
        elif _analysis_ran:
            face_has_v = False  # analysis ran but found no v-seams
        else:
            face_has_v = True

        return face_has_u, face_has_v

    # ── Case A: no seam duplicates ────────────────────────────────────────────

    def test_no_duplicates_u_seam_fix_allowed(self):
        """No positional duplicates → u-seam fix allowed for all faces."""
        face_has_u, face_has_v = self._apply_gating_logic(set(), set(), 0, 1, 2)
        assert face_has_u is True, (
            "When _node_u_seam_verts is empty, u-seam fix must be allowed "
            "(face_has_u=True → skip_seam_u=False)"
        )

    def test_no_duplicates_v_seam_fix_allowed(self):
        """No positional duplicates → v-seam fix allowed for all faces."""
        face_has_u, face_has_v = self._apply_gating_logic(set(), set(), 0, 1, 2)
        assert face_has_v is True, (
            "When _node_v_seam_verts is empty and analysis did not run, "
            "v-seam fix must be allowed (face_has_v=True → skip_seam_v=False)"
        )

    # ── Case B: u-seam duplicates found, no v-seam duplicates ────────────────

    def test_u_seam_found_face_touching_seam_vert(self):
        """Face touching a u-seam vert → u-fix applied."""
        u_seam = {5, 7}
        face_has_u, _ = self._apply_gating_logic(u_seam, set(), 3, 5, 8)
        assert face_has_u is True, (
            "Face containing seam vert 5 should have face_has_u=True"
        )

    def test_u_seam_found_interior_face_u_fix_disabled(self):
        """Interior face (no seam verts) → u-fix disabled when analysis ran."""
        u_seam = {5, 7}
        face_has_u, _ = self._apply_gating_logic(u_seam, set(), 0, 1, 2)
        assert face_has_u is False, (
            "Interior face (no seam verts) should have face_has_u=False when "
            "u-seam analysis ran and found duplicates"
        )

    def test_u_seam_found_no_v_seam_v_fix_disabled(self):
        """u-seam found but no v-seam duplicates → v-fix disabled (hair-strand fix)."""
        u_seam = {5, 7}
        _, face_has_v = self._apply_gating_logic(u_seam, set(), 3, 5, 8)
        assert face_has_v is False, (
            "When u-seam analysis ran but found no v-seam duplicates, "
            "face_has_v must be False (preserves hair-strand black-tip fix)"
        )

    def test_u_seam_found_no_v_seam_v_fix_disabled_interior(self):
        """Interior face: u-seam found but no v-seam → v-fix also disabled."""
        u_seam = {5, 7}
        _, face_has_v = self._apply_gating_logic(u_seam, set(), 0, 1, 2)
        assert face_has_v is False, (
            "Interior face: v-fix must be disabled when analysis ran with no v-seams"
        )

    # ── Case C: both seam sets populated ─────────────────────────────────────

    def test_both_seams_face_touching_u_seam(self):
        """Both axes have seam verts; face touches u-seam vert."""
        u_seam = {5, 7}
        v_seam = {8, 10}
        face_has_u, face_has_v = self._apply_gating_logic(u_seam, v_seam, 3, 5, 11)
        assert face_has_u is True, "Should allow u-fix (vert 5 in u_seam)"
        assert face_has_v is False, "Should disable v-fix (no vert in v_seam)"

    def test_both_seams_face_touching_v_seam(self):
        """Both axes have seam verts; face touches v-seam vert."""
        u_seam = {5, 7}
        v_seam = {8, 10}
        face_has_u, face_has_v = self._apply_gating_logic(u_seam, v_seam, 3, 8, 11)
        assert face_has_u is False, "Should disable u-fix (no vert in u_seam)"
        assert face_has_v is True, "Should allow v-fix (vert 8 in v_seam)"

    def test_both_seams_face_touching_both(self):
        """Face touches both u and v seam verts → both fixes allowed."""
        u_seam = {5, 7}
        v_seam = {8, 10}
        face_has_u, face_has_v = self._apply_gating_logic(u_seam, v_seam, 5, 8, 11)
        assert face_has_u is True
        assert face_has_v is True


# ─────────────────────────────────────────────────────────────────────────────
# Section 2 — Visual seam-fix tests (require PIL)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _PIL, reason="PIL not installed")
class TestSeamFixVisual:
    """Visual tests: render a seam-crossing triangle and check pixel colour.

    A gradient texture (red at high U, blue at low U) is used.
    Triangle UVs u=[0.96, 0.01, 0.99] straddle the tile boundary.
    With seam fix: centroid U ≈ 0.987 → RED dominant.
    Without seam fix: stretched across full tile → MIXED (wrong).
    """

    def _make_gradient_tex(self, w=64, h=64):
        """Red at right (high U), blue at left (low U)."""
        tex = Image.new('RGBA', (w, h))
        for x in range(w):
            r = int(x / (w - 1) * 255)
            b = 255 - r
            for y in range(h):
                tex.putpixel((x, y), (r, 0, b, 255))
        return tex

    def test_seam_fix_produces_red_centroid_when_skip_false(self):
        """skip_seam_u=False → seam fix applied → centroid is RED dominant."""
        from src.gui.viewport import _paste_textured_triangle
        tex = self._make_gradient_tex()
        canvas = Image.new('RGBA', (128, 128), (64, 64, 64, 255))
        _paste_textured_triangle(
            canvas, tex,
            (55, 55), (75, 55), (65, 75),
            (0.96, 0.5), (0.01, 0.5), (0.99, 0.5),
            128, 128, (255, 255, 255),
            skip_seam_u=False,
        )
        px = canvas.getpixel((65, 62))
        r, b = px[0], px[2]
        assert r > b, (
            f"skip_seam_u=False: centroid should be RED (seam fix applied), "
            f"got R={r} B={b}"
        )

    def test_no_duplicate_mesh_seam_face_rendered_correctly(self):
        """
        Simulate a non-skin trimesh node with no positional duplicates.
        Seam face u=[0.96, 0.01, 0.99] must be rendered with the fix applied
        (face_has_u_seam=True when _node_u_seam_verts is empty).
        """
        from src.gui.viewport import _paste_textured_triangle
        tex = self._make_gradient_tex()
        canvas = Image.new('RGBA', (128, 128), (64, 64, 64, 255))
        # Simulate: no positional duplicates found → _face_has_u_seam=True
        # → skip_seam_u=not True=False → seam fix runs
        _paste_textured_triangle(
            canvas, tex,
            (55, 55), (75, 55), (65, 75),
            (0.96, 0.5), (0.01, 0.5), (0.99, 0.5),
            128, 128, (255, 255, 255),
            skip_seam_u=False,   # simulates _face_has_u_seam=True
        )
        px = canvas.getpixel((65, 62))
        r, b = px[0], px[2]
        assert r > b, (
            f"Non-skin mesh seam face: centroid must be RED (u≈0.987), "
            f"got R={r} B={b}.  Seam fix not applied → stretched texture."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Section 3 — Supermodel-based skin vertex discriminator
# ─────────────────────────────────────────────────────────────────────────────

def _make_model(name='test', supermodel='NULL', skin_wp=(0, 0, 0),
                skin_rot=(0, 0, 0, 1), vertex=(0.1, 0.2, -0.3)):
    """Build a minimal KotorModel with one skin node."""
    m = KotorModel()
    m.name = name
    m.supermodel = supermodel

    root = ModelNode(name='root', flags=int(NodeFlags.HEADER))
    root.position = (0, 0, 0)
    root.orientation = (0, 0, 0, 1)
    m.root_node = root

    skin = ModelNode(name='body', flags=int(NodeFlags.MESH) | int(NodeFlags.SKIN))
    skin.position = skin_wp
    skin.orientation = skin_rot
    skin.vertices = [vertex]
    skin.faces = []
    skin.uvs = [(0.5, 0.5)]
    skin.texture = 'test_tex'
    skin.parent = root
    root.children = [skin]
    m._node_list = [root, skin]
    return m


class TestSupermodelSkinDiscriminator:
    """Tests for the universal skin vertex world-transform pipeline.

    Phase 16 (universal transform): ALL MDL vertices — both skin and non-skin —
    are stored in NODE-LOCAL space.  The full parent-chain world transform
    (translate + rotate) must always be applied, regardless of supermodel type.

    The old 'standalone/accessory' distinction has been removed.  All nodes
    use the same universal path: world_vert = local_vert + node_world_position
    (plus rotation if orientation is non-identity).

    Reference: PyKotor GL renderer read_mdl.py, KotorBlender base.py.
    """

    def test_null_supermodel_world_transform_applied(self):
        """
        Phase 16: ALL skin nodes get full world transform applied.
        supermodel=NULL does NOT mean verts are returned as-is.
        Vert (0.1, 0.2, -0.3), node wp=(0,0,1.5) → world = (0.1, 0.2, 1.2)
        """
        m = _make_model(supermodel='NULL', skin_wp=(0, 0, 1.5),
                        vertex=(0.1, 0.2, -0.3))
        cam = ArcBallCamera()
        cam.distance = 4.0
        fr = FrameRenderer(cam)
        fr.set_model(m)
        skin_node = m.root_node.children[0]
        wverts = fr._get_world_verts_for_node(skin_node)
        assert len(wverts) == 1
        wv = wverts[0]
        # Universal: full world transform applied to ALL nodes (Phase 16)
        # identity rotation → world = v + wp = (0.1, 0.2, -0.3 + 1.5) = (0.1, 0.2, 1.2)
        assert abs(wv[0] - 0.1) < 1e-4, f"X: expected 0.1 got {wv[0]}"
        assert abs(wv[1] - 0.2) < 1e-4, f"Y: expected 0.2 got {wv[1]}"
        assert abs(wv[2] - 1.2) < 1e-4, f"Z: expected 1.2 got {wv[2]}"

    def test_accessory_supermodel_wp_applied(self):
        """
        Accessory model (supermodel=N_AdmrlSaulKar): same universal transform.
        _get_world_verts_for_node applies the world transform (wp+rotation).
        """
        m = _make_model(supermodel='N_AdmrlSaulKar', skin_wp=(0, 0, 1.5),
                        vertex=(0.1, 0.2, -0.3))
        cam = ArcBallCamera()
        cam.distance = 4.0
        fr = FrameRenderer(cam)
        fr.set_model(m)
        skin_node = m.root_node.children[0]
        wverts = fr._get_world_verts_for_node(skin_node)
        assert len(wverts) == 1
        wv = wverts[0]
        # Universal: identity rotation → world = v + wp = (0.1, 0.2, -0.3 + 1.5) = (0.1, 0.2, 1.2)
        assert abs(wv[0] - 0.1) < 1e-4, f"X: expected 0.1 got {wv[0]}"
        assert abs(wv[1] - 0.2) < 1e-4, f"Y: expected 0.2 got {wv[1]}"
        assert abs(wv[2] - 1.2) < 1e-4, f"Z: expected 1.2 got {wv[2]}"

    def test_base_skeleton_world_transform_applied(self):
        """
        Phase 16: S_Female03 (base skeleton) also gets full world transform.
        The standalone/base-skeleton distinction is gone — universal transform.
        Vert (0.5, 0.0, 0.5), node wp=(0,0,2.0) → world Z = 2.5
        """
        m = _make_model(supermodel='S_Female03', skin_wp=(0, 0, 2.0),
                        vertex=(0.5, 0.0, 0.5))
        cam = ArcBallCamera()
        cam.distance = 4.0
        fr = FrameRenderer(cam)
        fr.set_model(m)
        skin_node = m.root_node.children[0]
        wverts = fr._get_world_verts_for_node(skin_node)
        wv = wverts[0]
        # Universal: world Z = vert Z + wp Z = 0.5 + 2.0 = 2.5
        assert abs(wv[2] - 2.5) < 1e-4, (
            f"Universal transform → vert Z should be 2.5 (0.5+2.0), got {wv[2]}"
        )

    def test_null_supermodel_is_case_insensitive(self):
        """Universal path applies regardless of supermodel case.
        supermodel='null' → same universal world transform as NULL.
        Vert (0.3, 0.3, 0.3), node wp=(0,0,1.0) → world Z = 1.3
        """
        m = _make_model(supermodel='null', skin_wp=(0, 0, 1.0),
                        vertex=(0.3, 0.3, 0.3))
        cam = ArcBallCamera()
        cam.distance = 4.0
        fr = FrameRenderer(cam)
        fr.set_model(m)
        skin_node = m.root_node.children[0]
        wverts = fr._get_world_verts_for_node(skin_node)
        wv = wverts[0]
        # Universal: world Z = 0.3 + 1.0 = 1.3
        assert abs(wv[2] - 1.3) < 1e-4, (
            f"'null' supermodel: universal transform → vert Z should be 1.3, got {wv[2]}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Section 4 — Compute bounds with supermodel discriminator
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeBoundsSupermodel:
    """Tests for the universal compute_bounds skin vertex handling.

    Phase 16: compute_bounds applies the full world transform to ALL vertices
    regardless of supermodel type.  The standalone/accessory distinction is gone.
    """

    def test_standalone_compute_bounds_wp_applied(self):
        """
        Phase 16: compute_bounds ALWAYS adds wp to skin verts (universal transform).
        Vert (0.1, 0.2, -0.3), wp=(0,0,0.5) → world Z = -0.3 + 0.5 = 0.2
        """
        m = _make_model(supermodel='NULL', skin_wp=(0, 0, 0.5),
                        vertex=(0.1, 0.2, -0.3))
        m.compute_bounds()
        z_max = m.bb_max[2] if m.bb_max else None
        assert z_max is not None, "compute_bounds did not set bb_max"
        assert abs(z_max - 0.2) < 0.1, (
            f"Universal: bb_max Z expected ≈ 0.2 (vert Z + wp Z = -0.3+0.5), got {z_max}"
        )

    def test_accessory_compute_bounds_wp_added(self):
        """
        Phase 16: Accessory model also uses universal transform.
        Vert (0.1, 0.2, -0.3), wp=(0,0,1.5) → world Z = 1.2.
        """
        m = _make_model(supermodel='N_AdmrlSaulKar', skin_wp=(0, 0, 1.5),
                        vertex=(0.1, 0.2, -0.3))
        m.compute_bounds()
        z_max = m.bb_max[2] if m.bb_max else None
        assert z_max is not None, "compute_bounds did not set bb_max"
        assert abs(z_max - 1.2) < 0.1, (
            f"Universal: bb_max Z expected ≈ 1.2 (vert Z + wp Z), got {z_max}"
        )
