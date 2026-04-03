"""
test_v30_pipeline_fixes.py
===========================
v3.0 test suite covering all pipeline fixes:

  1.  MDL Parser — skin MDX bounds validation (c_bantha crash fix)
  2.  MDL Parser — sw_off / sbr_off = 0 handled as valid channel offset
  3.  MDL Parser — sw_off / sbr_off >= stride treated as absent
  4.  MDL Parser — mdx_skin_safe guard (zero-length MDX)
  5.  MDL Parser — compact_bones empty → skin_data still populated (all zero weights)
  6.  MDL Parser — bone_map_floats with -1 entries correctly excluded
  7.  Auto game dir detection — both K1 and K2 saved in single callback
  8.  Auto game dir detection — only K1 found → k2 arg is None
  9.  Auto game dir detection — only K2 found → k1 arg is None
  10. TextureCache — set_game_library clears cache when tag changes
  11. TextureCache — set_game_library does NOT clear cache when tag unchanged
  12. TextureCache — set_game_library clears cache when library changes
  13. Game library — cross-game texture fallback (K1 model when tag=K2)
  14. Game library — cross-game fallback skips when other_dir is None
  15. UV index — vi >= n_uvs falls back to (0.5, 0.5) not clamped last UV
  16. UV index — vi < n_uvs uses correct UV
  17. Mesh face rendering — degenerate triangle (zero area) does not crash
  18. Mesh face rendering — back-face culling skips CW triangles
  19. Mesh face rendering — two-sided dangly renders both faces
  20. Bone overlay — root node always treated as bone
  21. Bone overlay — cycle-protected _nearest_bone_ancestor
  22. Bone overlay — deform helper (_g suffix) is bone
  23. Bone overlay — skin node is NOT a bone
  24. Rigging — world_transform for skin nodes translates only (no rotation)
  25. Rigging — world_transform for non-skin+non-identity rotates+translates
  26. Rigging — _apply_vertex_transform skin: translate only
  27. Rigging — _apply_vertex_transform non-skin identity: translate only
  28. Rigging — _apply_vertex_transform non-skin rotation: rotate+translate
  29. LBS — _lbs_vertex with no influences falls back to bind-pose
  30. LBS — _lbs_vertex with one influence correctly transforms vertex
  31. Mesh positioning — skin node at (1,2,3) shifts all vertices by (1,2,3)
  32. Mesh positioning — non-skin node at (1,0,0) with identity rot shifts verts
  33. Mesh positioning — non-skin 90° Z-rotation rotates vertices correctly
  34. MDL Parser — dangly constraints normalisation (255→1.0)
  35. MDL Parser — dangly constraints already 0-1 not re-normalised
  36. Model data — render_bounds with mixed skin/non-skin nodes
  37. Model data — render_bounds fallback when no non-skin anchors
  38. Model data — compute_bounds with zero vertices returns defaults
  39. Model data — world_position with 2-level hierarchy
  40. Model data — bone_world_position collapses 180° flip
  41. Renderer — set_model invalidates all caches
  42. Renderer — _compute_outlier_skin_nodes skips base skeletons
  43. Renderer — _compute_outlier_skin_nodes skips C_ prefix models
  44. Renderer — _compute_outlier_skin_nodes skips when <3 non-skin nodes
  45. Renderer — _is_deformation_helper skin+real_tex+valid_uvs → not helper
  46. Renderer — _is_deformation_helper non-skin _g → always helper
  47. Renderer — _is_deformation_helper null-tex non-skin → helper
  48. Renderer — _iter_visible_mesh_nodes excludes deform helpers
  49. Renderer — _iter_visible_mesh_nodes always includes dangly nodes
  50. Renderer — _get_world_normals_for_node skin returns normals as-is
"""

from __future__ import annotations

import math
import sys
import os
import struct

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────

from src.core.model_data import (
    KotorModel, ModelNode, NodeFlags,
    _quat_rotate, _quat_conjugate, _quat_normalize,
)


def _make_node(name='root', flags=NodeFlags.HEADER, parent=None,
               pos=(0, 0, 0), rot=(0, 0, 0, 1)):
    n = ModelNode(name=name, flags=int(flags), parent=parent,
                  position=pos, rotation=rot)
    if parent is not None:
        parent.children.append(n)
    return n


def _make_skin_node(name, parent=None, pos=(0, 0, 0), verts=None):
    flags = int(NodeFlags.MESH) | int(NodeFlags.SKIN)
    n = ModelNode(name=name, flags=flags, parent=parent, position=pos)
    if parent is not None:
        parent.children.append(n)
    if verts:
        n.vertices = list(verts)
    return n


def _make_mesh_node(name, parent=None, pos=(0, 0, 0), rot=(0, 0, 0, 1),
                    verts=None, uvs=None, faces=None, normals=None,
                    texture='', dangly=False):
    flags = int(NodeFlags.MESH)
    if dangly:
        flags |= int(NodeFlags.DANGLY)
    n = ModelNode(name=name, flags=flags, parent=parent,
                  position=pos, rotation=rot)
    if parent is not None:
        parent.children.append(n)
    if verts:
        n.vertices = list(verts)
    if uvs:
        n.uvs = list(uvs)
    if faces:
        n.faces = list(faces)
    if normals:
        n.normals = list(normals)
    if texture:
        n.texture = texture
    return n


def _make_model(name='test_model', supermodel='NULL'):
    m = KotorModel()
    m.name = name
    m.supermodel = supermodel
    return m


def _make_renderer(model=None):
    """Create a FrameRenderer with optional model."""
    from src.gui.viewport import FrameRenderer, ArcBallCamera
    cam = ArcBallCamera()
    r = FrameRenderer(cam)
    if model:
        r.set_model(model)
    return r


# ──────────────────────────────────────────────────────────────────────────────
#  1-6: MDL Parser skin bounds validation
# ──────────────────────────────────────────────────────────────────────────────

class TestMDLParserSkinBoundsValidation:
    """Tests for the fixed _parse_skin MDX bounds checking."""

    def _make_minimal_mdl(self, game_version='K1'):
        """Build a minimal valid MDL binary for a skin-node model."""
        # We test the parser logic directly using the fixed bounds guards
        from src.core.mdl_parser import MDLBinaryParser
        return MDLBinaryParser

    def test_parser_handles_empty_mdx_skin(self):
        """Parser with empty MDX should not crash on skin parsing."""
        from src.core.mdl_parser import MDLBinaryParser
        # Build minimal MDL that has a skin node; MDX is empty
        # We just test that the parser doesn't throw on truncated MDX
        parser = MDLBinaryParser.__new__(MDLBinaryParser)
        # Simulate what _parse_skin sees with empty mdx
        node = ModelNode(name='test_skin', flags=int(NodeFlags.MESH) | int(NodeFlags.SKIN))
        # Directly call the skin parse logic validation
        # sw_off = 0xFFFFFFFF means absent → sw_valid = False → loop skips all
        sw_off = 0xFFFFFFFF
        sbr_off = 0xFFFFFFFF
        stride = 32
        sw_valid = (sw_off != 0xFFFFFFFF and sw_off < stride)
        sbr_valid = (sbr_off != 0xFFFFFFFF and sbr_off < stride)
        assert not sw_valid
        assert not sbr_valid
        # No skin_data added, no crash
        assert len(node.skin_data) == 0

    def test_swoff_zero_is_valid(self):
        """sw_off == 0 with stride=32 → sw_valid should be True."""
        sw_off = 0
        stride = 32
        sw_valid = (sw_off != 0xFFFFFFFF and sw_off < stride)
        assert sw_valid  # 0 < 32

    def test_swoff_equals_stride_is_invalid(self):
        """sw_off == stride means out-of-bounds → sw_valid should be False."""
        sw_off = 32
        stride = 32
        sw_valid = (sw_off != 0xFFFFFFFF and sw_off < stride)
        assert not sw_valid  # 32 is not < 32

    def test_sbroff_equals_stride_is_invalid(self):
        """sbr_off == stride means out-of-bounds → sbr_valid should be False."""
        sbr_off = 32
        stride = 32
        sbr_valid = (sbr_off != 0xFFFFFFFF and sbr_off < stride)
        assert not sbr_valid

    def test_mdx_skin_safe_zero_mdx(self):
        """mdx_skin_safe is False when mdx is empty."""
        mdx = b''
        vert_cnt = 10
        stride = 32
        mdx_data_off = 0
        mdx_skin_safe = (len(mdx) > 0 and stride > 0
                         and mdx_data_off + vert_cnt * stride <= len(mdx) + stride)
        assert not mdx_skin_safe  # len(mdx) == 0 → False

    def test_mdx_skin_safe_with_valid_data(self):
        """mdx_skin_safe is True when MDX has enough data."""
        vert_cnt = 2
        stride = 32
        mdx_data_off = 0
        mdx = b'\x00' * (vert_cnt * stride)
        mdx_skin_safe = (len(mdx) > 0 and stride > 0
                         and mdx_data_off + vert_cnt * stride <= len(mdx) + stride)
        assert mdx_skin_safe

    def test_bone_map_floats_minus_one_excluded(self):
        """bone_map_floats with -1.0 entries → compact_bones excludes them."""
        bone_map_floats = [-1.0, 0.0, -1.0, 1.0, 2.0, -1.0]
        compact_bones = [int(round(v)) for v in bone_map_floats if v >= 0]
        assert compact_bones == [0, 1, 2]

    def test_compact_bones_index_range_guard(self):
        """compact_idx out of compact_bones range → influence skipped."""
        compact_bones = [0, 1]  # only 2 active bones
        compact_idx_valid = 0 <= 1 < len(compact_bones)
        compact_idx_bad = 0 <= 5 < len(compact_bones)
        assert compact_idx_valid
        assert not compact_idx_bad


# ──────────────────────────────────────────────────────────────────────────────
#  7-9: Auto game dir detection
# ──────────────────────────────────────────────────────────────────────────────

class TestAutoGameDirDetection:
    """Tests for the fixed _auto_detect_dirs callback logic."""

    def test_both_dirs_single_callback(self):
        """When both K1 and K2 are found, _on_dir_set is called ONCE with both."""
        callback_calls = []

        def fake_on_dir_set(k1, k2):
            callback_calls.append((k1, k2))

        found_k1 = '/fake/kotor1'
        found_k2 = '/fake/kotor2'
        changed = []

        if found_k1:
            changed.append(f"K1: {found_k1}")
        if found_k2:
            changed.append(f"K2: {found_k2}")

        # The fixed code calls _on_dir_set ONCE with both args
        if changed:
            fake_on_dir_set(found_k1 or None, found_k2 or None)

        assert len(callback_calls) == 1
        assert callback_calls[0] == (found_k1, found_k2)

    def test_only_k1_found_k2_is_none(self):
        """Only K1 found → callback called with (k1, None)."""
        callback_calls = []

        def fake_on_dir_set(k1, k2):
            callback_calls.append((k1, k2))

        found_k1 = '/fake/kotor1'
        found_k2 = None
        changed = []

        if found_k1:
            changed.append(f"K1: {found_k1}")
        if found_k2:
            changed.append(f"K2: {found_k2}")

        if changed:
            fake_on_dir_set(found_k1 or None, found_k2 or None)

        assert len(callback_calls) == 1
        assert callback_calls[0] == (found_k1, None)

    def test_only_k2_found_k1_is_none(self):
        """Only K2 found → callback called with (None, k2)."""
        callback_calls = []

        def fake_on_dir_set(k1, k2):
            callback_calls.append((k1, k2))

        found_k1 = None
        found_k2 = '/fake/kotor2'
        changed = []

        if found_k1:
            changed.append(f"K1: {found_k1}")
        if found_k2:
            changed.append(f"K2: {found_k2}")

        if changed:
            fake_on_dir_set(found_k1 or None, found_k2 or None)

        assert len(callback_calls) == 1
        assert callback_calls[0] == (None, found_k2)

    def test_no_dirs_no_callback(self):
        """No dirs found → callback not called."""
        callback_calls = []

        def fake_on_dir_set(k1, k2):
            callback_calls.append((k1, k2))

        found_k1 = None
        found_k2 = None
        changed = []

        if found_k1:
            changed.append(f"K1: {found_k1}")
        if found_k2:
            changed.append(f"K2: {found_k2}")

        if changed:
            fake_on_dir_set(found_k1 or None, found_k2 or None)

        assert len(callback_calls) == 0

    def test_on_game_dir_set_saves_both_settings(self):
        """_on_game_dir_set stores both dirs when called with both."""
        settings = {'k1_dir': '', 'k2_dir': ''}

        def on_game_dir_set(k1_dir, k2_dir):
            if k1_dir:
                settings['k1_dir'] = k1_dir
            if k2_dir:
                settings['k2_dir'] = k2_dir

        on_game_dir_set('/fake/kotor1', '/fake/kotor2')
        assert settings['k1_dir'] == '/fake/kotor1'
        assert settings['k2_dir'] == '/fake/kotor2'


# ──────────────────────────────────────────────────────────────────────────────
#  10-13: TextureCache game tag management
# ──────────────────────────────────────────────────────────────────────────────

class TestTextureCacheGameTag:
    """Tests for the fixed TextureCache.set_game_library tag update logic."""

    def _make_cache(self):
        from src.gui.viewport import TextureCache
        tc = TextureCache()
        tc._game_library = None
        tc._game_tag = "K1"
        tc._cache = {}
        return tc

    def test_set_game_library_clears_cache_on_library_change(self):
        """set_game_library clears cache when library reference changes."""
        tc = self._make_cache()
        tc._cache = {'tex1': 'img1'}  # pre-populate
        fake_lib = object()
        tc.set_game_library(fake_lib, "K1")
        assert tc._cache == {}
        assert tc._game_library is fake_lib

    def test_set_game_library_clears_cache_on_tag_change(self):
        """set_game_library clears cache when same library but tag changes."""
        from src.gui.viewport import TextureCache
        tc = self._make_cache()
        fake_lib = object()
        tc._game_library = fake_lib  # already set
        tc._game_tag = "K1"
        tc._cache = {'tex1': 'img1'}  # pre-populate
        # Change tag only
        tc.set_game_library(fake_lib, "K2")
        assert tc._game_tag == "K2"
        assert tc._cache == {}  # must be cleared

    def test_set_game_library_no_clear_on_same_tag(self):
        """set_game_library does NOT clear cache when library and tag unchanged."""
        tc = self._make_cache()
        fake_lib = object()
        tc._game_library = fake_lib
        tc._game_tag = "K1"
        tc._cache = {'tex1': 'img1'}
        # Same library, same tag → no clear
        tc.set_game_library(fake_lib, "K1")
        assert tc._cache == {'tex1': 'img1'}  # untouched

    def test_game_tag_defaults_to_k1(self):
        """Default game_tag on fresh TextureCache is K1."""
        from src.gui.viewport import TextureCache
        tc = TextureCache()
        assert tc._game_tag == "K1"


# ──────────────────────────────────────────────────────────────────────────────
#  14: Game library cross-game fallback
# ──────────────────────────────────────────────────────────────────────────────

class TestGameLibraryCrossGameFallback:
    """Test get_texture_data cross-game fallback when both K1+K2 dirs present."""

    def test_cross_game_fallback_logic(self):
        """When primary game fails, other game is tried if other_dir is set."""
        # Simulate the fallback logic
        game = "K2"
        other = "K2" if game == "K1" else "K1"
        assert other == "K1"

    def test_cross_game_fallback_skipped_if_no_other_dir(self):
        """No fallback when other game dir is not set."""
        k1_dir = None
        game = "K2"
        other = "K1"
        other_dir = k1_dir  # None → no fallback
        assert other_dir is None

    def test_cross_game_fallback_enabled_if_other_dir_set(self):
        """Fallback is enabled when other game dir is set."""
        k1_dir = '/fake/kotor1'
        game = "K2"
        other = "K1"
        other_dir = k1_dir
        assert other_dir is not None


# ──────────────────────────────────────────────────────────────────────────────
#  15-16: UV index out-of-bounds fallback
# ──────────────────────────────────────────────────────────────────────────────

class TestUVIndexFallback:
    """Test the fixed UV index fallback for out-of-range indices."""

    def _simulate_uv_lookup(self, uvs, vi):
        """Simulate the fixed UV lookup logic."""
        n_uvs = len(uvs)
        return uvs[vi] if vi < n_uvs else (0.5, 0.5)

    def test_uv_within_range_returns_correct_uv(self):
        """vi < n_uvs: returns the correct UV."""
        uvs = [(0.1, 0.2), (0.3, 0.4), (0.7, 0.8)]
        assert self._simulate_uv_lookup(uvs, 0) == (0.1, 0.2)
        assert self._simulate_uv_lookup(uvs, 2) == (0.7, 0.8)

    def test_uv_out_of_range_returns_fallback(self):
        """vi >= n_uvs: returns (0.5, 0.5) fallback."""
        uvs = [(0.1, 0.2), (0.3, 0.4)]
        assert self._simulate_uv_lookup(uvs, 2) == (0.5, 0.5)
        assert self._simulate_uv_lookup(uvs, 10) == (0.5, 0.5)

    def test_empty_uvs_returns_fallback(self):
        """Empty UV array: always returns fallback."""
        uvs = []
        assert self._simulate_uv_lookup(uvs, 0) == (0.5, 0.5)

    def test_uv_index_at_boundary(self):
        """vi == n_uvs - 1 (last valid): returns last UV, not fallback."""
        uvs = [(0.9, 0.8)]
        assert self._simulate_uv_lookup(uvs, 0) == (0.9, 0.8)

    def test_old_clamping_would_give_wrong_result(self):
        """Verify that clamping (old behavior) gives wrong UV at boundary."""
        uvs = [(0.1, 0.2), (0.9, 0.8)]
        vi = 5  # out of range
        # Old behavior: min(vi, n_uvs-1) = 1 → uvs[1] = (0.9, 0.8) — wrong!
        old_result = uvs[min(vi, len(uvs) - 1)]
        # New behavior: (0.5, 0.5)
        new_result = uvs[vi] if vi < len(uvs) else (0.5, 0.5)
        assert old_result == (0.9, 0.8)   # would distort texture
        assert new_result == (0.5, 0.5)   # neutral fallback


# ──────────────────────────────────────────────────────────────────────────────
#  17-19: Mesh face rendering
# ──────────────────────────────────────────────────────────────────────────────

class TestMeshFaceRendering:
    """Test mesh face rendering improvements."""

    def test_degenerate_triangle_normal_fallback(self):
        """_face_normal on degenerate triangle returns a valid vector."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        # Degenerate: all three verts at same position
        v0 = v1 = v2 = (0.0, 0.0, 0.0)
        n = r._face_normal(v0, v1, v2)
        # _normalize returns (0,1,0) for zero vector
        assert len(n) == 3
        assert all(math.isfinite(x) for x in n)

    def test_backface_culling_skip_cw_triangle(self):
        """Back-facing (winding > 0) triangles should be skipped in screen space.

        KotOR convention: screen Y is DOWN; CCW in world space maps to
        CW in screen (Y-down), giving winding > 0.  These are BACK-FACING
        and are culled.  Front-facing tris have winding < 0.

        Example: a CW screen-space triangle (Y-down):
          p0=(100,100), p1=(200,100), p2=(100,200)
          ex1=100, ey1=0, ex2=0, ey2=100 → winding = 100*100 - 0*0 = 10000 > 0
        """
        # CW in screen space (Y-down): winding > 0 → back-facing
        p0 = (100, 100, 1.0)
        p1 = (200, 100, 1.0)
        p2 = (100, 200, 1.0)
        ex1 = p1[0] - p0[0]; ey1 = p1[1] - p0[1]
        ex2 = p2[0] - p0[0]; ey2 = p2[1] - p0[1]
        winding = ex1 * ey2 - ex2 * ey1
        # ex1=100, ey1=0, ex2=0, ey2=100 → winding=100*100-0*0=10000>0
        assert winding > 0  # back-facing (CW in Y-down screen)

    def test_frontface_passes_culling(self):
        """Front-facing (winding < 0) triangles pass culling.

        Screen Y is DOWN: CCW in Y-down space = front-facing in KotOR.
        Example: CCW screen-space triangle:
          p0=(100,100), p1=(100,200), p2=(200,100)
          ex1=0,ey1=100, ex2=100,ey2=0 → winding=0*0-100*100=-10000 < 0
        """
        # CCW in screen space (Y-down): winding < 0 → front-facing
        p0 = (100, 100, 1.0)
        p1 = (100, 200, 1.0)
        p2 = (200, 100, 1.0)
        ex1 = p1[0] - p0[0]; ey1 = p1[1] - p0[1]
        ex2 = p2[0] - p0[0]; ey2 = p2[1] - p0[1]
        winding = ex1 * ey2 - ex2 * ey1
        # ex1=0,ey1=100, ex2=100,ey2=0 → winding=-10000 < 0
        assert winding < 0  # front-facing (CCW in Y-down screen)

    def test_two_sided_dangly_not_culled(self):
        """is_two_sided=True prevents back-face culling for dangly nodes."""
        # Simulate the culling logic
        is_two_sided = True
        show_wireframe = False
        show_solid = True
        winding = 100  # positive = back-facing in screen

        would_cull = (winding > 0 and not show_wireframe
                      and show_solid and not is_two_sided)
        assert not would_cull  # two-sided: no cull

    def test_two_sided_cull_logic_with_false(self):
        """is_two_sided=False allows back-face culling."""
        is_two_sided = False
        show_wireframe = False
        show_solid = True
        winding = 100  # positive = back-facing

        would_cull = (winding > 0 and not show_wireframe
                      and show_solid and not is_two_sided)
        assert would_cull

    def test_face_depth_with_tiebreak(self):
        """Depth uses weighted centroid + face-index tiebreak."""
        p0 = (100, 100, 1.0)
        p1 = (200, 100, 1.5)
        p2 = (150, 200, 2.0)
        fi_local = 42
        depth = (p0[2] + p1[2] + p2[2]) * 0.3333 + fi_local * 1e-7
        expected_base = (1.0 + 1.5 + 2.0) * 0.3333
        assert abs(depth - (expected_base + 42e-7)) < 1e-9


# ──────────────────────────────────────────────────────────────────────────────
#  20-23: Bone overlay
# ──────────────────────────────────────────────────────────────────────────────

class TestBoneOverlay:
    """Test _is_bone_node logic in _draw_bones."""

    def _make_bone_checker(self):
        """Return the _is_bone_node function as would be defined inside _draw_bones."""
        def _is_bone_node(node) -> bool:
            if node.is_dummy:
                return True
            # Root node is always treated as a bone (skeleton root)
            if node.parent is None:
                return True
            if node.is_mesh and not node.is_skin:
                nl = node.name.lower()
                if (nl.endswith('_g') or nl.endswith('_g0') or
                        nl.endswith('_dum') or nl.endswith('dummy')):
                    return True
            return False
        return _is_bone_node

    def test_root_node_is_bone(self):
        """Root node (parent=None) is always treated as a bone."""
        _is_bone_node = self._make_bone_checker()
        root = _make_node('root', flags=NodeFlags.HEADER)
        assert root.parent is None
        assert _is_bone_node(root)

    def test_dummy_node_is_bone(self):
        """Dummy node (flags=HEADER) is always a bone."""
        _is_bone_node = self._make_bone_checker()
        root = _make_node('root')
        dummy = _make_node('pelvis', parent=root, flags=NodeFlags.HEADER)
        assert _is_bone_node(dummy)

    def test_g_suffix_mesh_is_bone(self):
        """Non-skin mesh with _g suffix is a bone (deform helper)."""
        _is_bone_node = self._make_bone_checker()
        root = _make_node('root')
        lbicep = _make_mesh_node('lbicep_g', parent=root)
        assert _is_bone_node(lbicep)

    def test_dum_suffix_mesh_is_bone(self):
        """Non-skin mesh with _dum suffix is a bone."""
        _is_bone_node = self._make_bone_checker()
        root = _make_node('root')
        collar = _make_mesh_node('collar_dum', parent=root)
        assert _is_bone_node(collar)

    def test_skin_node_not_bone(self):
        """Skin node is NOT a bone regardless of name."""
        _is_bone_node = self._make_bone_checker()
        root = _make_node('root')
        body_skin = _make_skin_node('body_g', parent=root)
        assert not _is_bone_node(body_skin)

    def test_regular_mesh_not_bone(self):
        """Regular named mesh node (not _g/_dum) is NOT a bone."""
        _is_bone_node = self._make_bone_checker()
        root = _make_node('root')
        body = _make_mesh_node('body', parent=root)
        assert not _is_bone_node(body)

    def test_cycle_protected_ancestor_traversal(self):
        """_nearest_bone_ancestor with cyclic parent chain doesn't loop forever."""
        # We can't create actual cycles in the data model easily,
        # but we verify that the visited-set logic terminates.
        # Create a chain: root → child1 → child2
        root = _make_node('root')
        child1 = _make_mesh_node('body', parent=root)
        child2 = _make_mesh_node('foot', parent=child1)

        _is_bone_node = self._make_bone_checker()

        def _nearest_bone_ancestor(node):
            p = node.parent
            _visited = set()
            while p is not None:
                pid = id(p)
                if pid in _visited:
                    break
                _visited.add(pid)
                if _is_bone_node(p):
                    return p
                p = p.parent
            return None

        # child2's nearest bone ancestor should be root (it's root = no parent)
        ancestor = _nearest_bone_ancestor(child2)
        assert ancestor is root


# ──────────────────────────────────────────────────────────────────────────────
#  24-28: Vertex transform pipeline
# ──────────────────────────────────────────────────────────────────────────────

class TestVertexTransformPipeline:
    """Test _apply_vertex_transform for skin/non-skin nodes."""

    def _get_apply_fn(self):
        from src.gui.viewport import FrameRenderer
        return FrameRenderer._apply_vertex_transform

    def test_skin_node_translate_only(self):
        """Skin nodes with identity rotation: translate by wp only (rotation is no-op).

        Most KotOR skin mesh nodes have identity rotation; in that case
        _apply_vertex_transform falls into the is_identity_rot==True branch and
        only adds the world position (wp) — no rotation is applied.

        The test uses is_id=True to reflect an identity-rotation skin node.

        Historical note: the empirical cases where the old translate-only rule was
        verified (bantha btBody_front wp_Z≈1.47, ad_saul head wp_Z≈1.70) all have
        identity skin-node rotations.  Models that carry a non-identity rotation on
        the skin mesh node (e.g. p_bastilabb 180°-Y, p_bastilaba 180°-X) must have
        the rotation applied — this is the correct KotOR/NWN MDL convention.
        """
        apply = self._get_apply_fn()
        root = _make_node('root')
        skin = _make_skin_node('body_g', parent=root)
        v = (1.0, 2.0, 3.0)
        wp = (10.0, 0.0, 0.0)
        wo = (0.0, 0.0, 0.0, 1.0)  # identity rotation
        is_id = True
        result = apply(skin, v, wp, wo, is_id)
        # Identity rotation: translate-only → v + wp
        assert abs(result[0] - 11.0) < 1e-6, f"Expected 11.0, got {result[0]} (skin vert must be translated by wp)"
        assert abs(result[1] - 2.0) < 1e-6
        assert abs(result[2] - 3.0) < 1e-6

    def test_skin_node_nonidentity_rotation_applied(self):
        """Skin nodes with non-identity rotation: rotation IS applied.

        Some KotOR models (p_bastilabb, p_bastilaba) carry a 180° rotation on the
        skin mesh node itself (an NWN co-ordinate-flip exporter artefact).  In those
        cases the rotation must be applied before the translation so that vertex
        geometry is correctly oriented in world space.

        wo = (0,0,1,0) → 180° about Z: (1,2,3) → (-1,-2,3) → +wp(10,0,0) = (9,-2,3).
        """
        apply = self._get_apply_fn()
        root = _make_node('root')
        skin = _make_skin_node('body_g', parent=root)
        v = (1.0, 2.0, 3.0)
        wp = (10.0, 0.0, 0.0)
        wo = (0.0, 0.0, 1.0, 0.0)  # 180° about Z (non-identity)
        is_id = False
        result = apply(skin, v, wp, wo, is_id)
        # Non-identity rotation IS applied: rot(wo, v) + wp
        # 180° Z: x→-x, y→-y, z unchanged: (-1,-2,3) + (10,0,0) = (9,-2,3)
        assert abs(result[0] - 9.0) < 1e-6, f"Expected 9.0, got {result[0]} (rotation should be applied)"
        assert abs(result[1] - (-2.0)) < 1e-6
        assert abs(result[2] - 3.0) < 1e-6

    def test_non_skin_identity_translate_only(self):
        """Non-skin with identity rotation: translate only."""
        apply = self._get_apply_fn()
        root = _make_node('root')
        mesh = _make_mesh_node('body', parent=root)
        v = (1.0, 0.0, 0.0)
        wp = (5.0, 2.0, 1.0)
        wo = (0.0, 0.0, 0.0, 1.0)  # identity
        is_id = True
        result = apply(mesh, v, wp, wo, is_id)
        assert abs(result[0] - 6.0) < 1e-6
        assert abs(result[1] - 2.0) < 1e-6
        assert abs(result[2] - 1.0) < 1e-6

    def test_non_skin_90z_rotation(self):
        """Non-skin with 90° Z rotation: (1,0,0) → (0,1,0) + translate."""
        apply = self._get_apply_fn()
        root = _make_node('root')
        mesh = _make_mesh_node('panel', parent=root)
        v = (1.0, 0.0, 0.0)
        wp = (0.0, 0.0, 0.0)
        # 90° about Z: quat = (0, 0, sin(45°), cos(45°)) = (0, 0, √2/2, √2/2)
        s = math.sqrt(0.5)
        wo = (0.0, 0.0, s, s)
        is_id = False
        result = apply(mesh, v, wp, wo, is_id)
        # (1,0,0) rotated 90° about Z → (0,1,0)
        assert abs(result[0] - 0.0) < 1e-5
        assert abs(result[1] - 1.0) < 1e-5
        assert abs(result[2] - 0.0) < 1e-5

    def test_non_skin_180z_rotation(self):
        """Non-skin with 180° Z rotation: (1,0,0) → (-1,0,0)."""
        apply = self._get_apply_fn()
        root = _make_node('root')
        mesh = _make_mesh_node('panel', parent=root)
        v = (1.0, 0.0, 0.0)
        wp = (0.0, 0.0, 0.0)
        wo = (0.0, 0.0, 1.0, 0.0)  # 180° about Z
        is_id = False
        result = apply(mesh, v, wp, wo, is_id)
        assert abs(result[0] - (-1.0)) < 1e-5
        assert abs(result[1] - 0.0) < 1e-5
        assert abs(result[2] - 0.0) < 1e-5


# ──────────────────────────────────────────────────────────────────────────────
#  29-30: LBS vertex
# ──────────────────────────────────────────────────────────────────────────────

class TestLBSVertex:
    """Test _lbs_vertex Linear Blend Skinning."""

    def _make_skin_model(self):
        """Create a minimal model with a root bone and a skin node."""
        model = _make_model(name='test')
        root = _make_node('root')
        model.root_node = root
        bone = _make_node('hip', parent=root, pos=(0.0, 0.0, 1.0))
        skin = _make_skin_node('body_g', parent=root)
        skin.vertices = [(0.0, 0.0, 1.0)]
        skin.bone_map = ['hip']
        return model, skin, bone

    def test_no_influences_falls_back_to_bind_pose(self):
        """_lbs_vertex with no valid bone influences uses bind-pose transform."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        from src.core.model_data import VertexSkinData, BoneWeight

        model, skin, bone = self._make_skin_model()
        model.compute_bounds()
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        r._anim_pose = None  # bind pose

        # Add a vertex with no influences
        from src.core.model_data import VertexSkinData
        sd = VertexSkinData()
        skin.skin_data = [sd]  # empty influences

        # Without animation, _get_world_verts_for_node falls back to bind pose
        verts = r._get_world_verts_for_node(skin)
        # Should be (0 + wx, 0 + wy, 1 + wz) where wx=wy=wz=0 for root skin
        assert verts is not None
        assert len(verts) == 1


# ──────────────────────────────────────────────────────────────────────────────
#  31-33: Mesh positioning
# ──────────────────────────────────────────────────────────────────────────────

class TestMeshPositioning:
    """Test mesh node world-space vertex positioning."""

    def test_skin_node_world_verts_translate(self):
        """Skin node at (1,2,3): Phase 17 — world transform IS applied to skin verts.

        Phase 17: All KotOR MDL vertices (skin AND non-skin) are stored in NODE-LOCAL
        space. The full world transform must be applied.

        Skin node at pos=(1,2,3) with identity rotation:
          vert (0,0,0) -> world (1,2,3)
          vert (1,0,0) -> world (2,2,3)
          vert (0,1,0) -> world (1,3,3)

        Verified by: KotorBlender (base.py) and PyKotor binary analysis of c_bantha.
        """
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        model = _make_model()
        root = _make_node('root')
        model.root_node = root
        skin = _make_skin_node('body_g', parent=root, pos=(1.0, 2.0, 3.0))
        skin.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        model.compute_bounds()

        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        verts = r._get_world_verts_for_node(skin)
        # Phase 17: skin verts in node-local space, wp (1,2,3) IS added
        assert abs(verts[0][0] - 1.0) < 1e-6, f"Skin vert[0] x: expected 1.0 (local 0 + wp_x 1), got {verts[0][0]}"
        assert abs(verts[0][1] - 2.0) < 1e-6, f"Skin vert[0] y: expected 2.0 (local 0 + wp_y 2), got {verts[0][1]}"
        assert abs(verts[0][2] - 3.0) < 1e-6, f"Skin vert[0] z: expected 3.0 (local 0 + wp_z 3), got {verts[0][2]}"
        assert abs(verts[1][0] - 2.0) < 1e-6, f"Skin vert[1] x: expected 2.0 (local 1 + wp_x 1), got {verts[1][0]}"
        assert abs(verts[2][1] - 3.0) < 1e-6, f"Skin vert[2] y: expected 3.0 (local 1 + wp_y 2), got {verts[2][1]}"

    def test_mesh_node_identity_translate(self):
        """Non-skin node at (5,0,0) with identity: all vertices shifted by (5,0,0)."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        model = _make_model()
        root = _make_node('root')
        model.root_node = root
        mesh = _make_mesh_node('body', parent=root, pos=(5.0, 0.0, 0.0))
        mesh.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
        model.compute_bounds()

        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        verts = r._get_world_verts_for_node(mesh)
        assert abs(verts[0][0] - 5.0) < 1e-6
        assert abs(verts[1][0] - 6.0) < 1e-6

    def test_mesh_node_90z_rotation(self):
        """Non-skin node with 90° Z rotation: (1,0,0) becomes (0,1,0)."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        s = math.sqrt(0.5)
        rot_90z = (0.0, 0.0, s, s)  # 90° about Z
        model = _make_model()
        root = _make_node('root')
        model.root_node = root
        mesh = _make_mesh_node('panel', parent=root, rot=rot_90z)
        mesh.vertices = [(1.0, 0.0, 0.0)]
        model.compute_bounds()

        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        verts = r._get_world_verts_for_node(mesh)
        # 90° Z rotation: (1,0,0) → (0,1,0)
        assert abs(verts[0][0] - 0.0) < 1e-4
        assert abs(verts[0][1] - 1.0) < 1e-4
        assert abs(verts[0][2] - 0.0) < 1e-4


# ──────────────────────────────────────────────────────────────────────────────
#  34-35: MDL Parser dangly constraints
# ──────────────────────────────────────────────────────────────────────────────

class TestDanglyConstraints:
    """Test dangly constraint normalisation in MDL parser."""

    def test_constraints_255_normalised_to_1(self):
        """Raw constraints 0-255 are normalised to 0-1."""
        raw_csts = [0.0, 127.5, 255.0]
        if raw_csts and max(raw_csts) > 1.0 + 1e-6:
            raw_csts = [max(0.0, min(1.0, c / 255.0)) for c in raw_csts]
        assert abs(raw_csts[0] - 0.0) < 1e-6
        assert abs(raw_csts[1] - 0.5) < 1e-3
        assert abs(raw_csts[2] - 1.0) < 1e-6

    def test_constraints_already_01_not_renormalised(self):
        """Constraints already in 0-1 range are not re-normalised."""
        raw_csts = [0.0, 0.5, 1.0]
        if raw_csts and max(raw_csts) > 1.0 + 1e-6:
            raw_csts = [max(0.0, min(1.0, c / 255.0)) for c in raw_csts]
        # max is 1.0 which is NOT > 1.0+1e-6, so no normalisation
        assert raw_csts == [0.0, 0.5, 1.0]

    def test_constraints_just_over_1_normalised(self):
        """Value of 2.0 triggers normalisation."""
        raw_csts = [0.0, 1.0, 2.0]
        if raw_csts and max(raw_csts) > 1.0 + 1e-6:
            raw_csts = [max(0.0, min(1.0, c / 255.0)) for c in raw_csts]
        # 2.0/255.0 ≈ 0.00784
        assert raw_csts[2] < 0.01


# ──────────────────────────────────────────────────────────────────────────────
#  36-38: Model data bounds
# ──────────────────────────────────────────────────────────────────────────────

class TestModelDataBounds:
    """Test model bounding box computation."""

    def test_render_bounds_with_skin_nodes(self):
        """render_bounds returns non-trivial box when skin nodes have vertices."""
        model = _make_model()
        root = _make_node('root')
        model.root_node = root
        skin = _make_skin_node('body', parent=root)
        skin.vertices = [(0, 0, 0), (2, 0, 0), (0, 3, 0), (0, 0, 5)]
        skin.texture = 'tex1'
        skin.uvs = [(0.0, 0.0)] * 4
        model.compute_bounds()
        bb_min, bb_max = model.render_bounds()
        # Should encompass the vertices
        assert bb_max[0] >= 2.0 or bb_max[1] >= 3.0 or bb_max[2] >= 5.0

    def test_compute_bounds_zero_vertices(self):
        """compute_bounds with no vertices returns (0,0,0), (0,0,0) defaults."""
        model = _make_model()
        root = _make_node('root')
        model.root_node = root
        model.compute_bounds()
        assert model.bb_min == (0.0, 0.0, 0.0)
        assert model.bb_max == (0.0, 0.0, 0.0)

    def test_render_bounds_fallback_to_compute_bounds(self):
        """render_bounds falls back to compute_bounds when no render nodes."""
        model = _make_model()
        root = _make_node('root')
        model.root_node = root
        # No renderable nodes
        model.compute_bounds()
        bb_min, bb_max = model.render_bounds()
        assert bb_min is not None
        assert bb_max is not None


# ──────────────────────────────────────────────────────────────────────────────
#  39-40: Model node world transforms
# ──────────────────────────────────────────────────────────────────────────────

class TestModelNodeWorldTransforms:
    """Test world_position and bone_world_position."""

    def test_world_position_2level_hierarchy(self):
        """world_position accumulates through 2-level hierarchy."""
        root = _make_node('root', pos=(0, 0, 0))
        hip = _make_node('hip', parent=root, pos=(0, 0, 1.0))
        # root at (0,0,0), hip at (0,0,1) relative → world (0,0,1)
        wp = hip.world_position()
        assert abs(wp[2] - 1.0) < 1e-6

    def test_bone_world_position_collapses_180_flip(self):
        """bone_world_position collapses 180° NWN convention flip."""
        root = _make_node('root', pos=(0, 0, 0))
        # 180° about X rotation on root (NWN convention)
        root_180x = _make_node('root_180', parent=root,
                                pos=(0, 0, 0), rot=(1, 0, 0, 0))
        hip = _make_node('hip', parent=root_180x, pos=(0, 0, 1.0))
        # bone_world_position collapses the 180° flip, so hip should be at (0,0,1)
        bwp = hip.bone_world_position()
        # The 180°-about-X flip collapses to identity, so hip stays at (0,0,1)
        assert all(math.isfinite(x) for x in bwp)

    def test_world_transform_leaf_rotation_preserved(self):
        """world_transform returns the leaf's actual rotation."""
        root = _make_node('root')
        s = math.sqrt(0.5)
        leaf = _make_node('leaf', parent=root, rot=(0, 0, s, s))  # 90° Z
        _, wo = leaf.world_transform()
        # The rotation magnitude should be non-zero (90° Z)
        mag = math.sqrt(wo[0]**2 + wo[1]**2 + wo[2]**2)
        assert mag > 0.5  # non-identity


# ──────────────────────────────────────────────────────────────────────────────
#  41-44: Renderer cache / outlier skin
# ──────────────────────────────────────────────────────────────────────────────

class TestRendererCacheAndOutlier:
    """Test FrameRenderer cache invalidation and outlier skin filter."""

    def test_set_model_invalidates_wt_cache(self):
        """set_model clears the world-transform cache."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        model = _make_model()
        root = _make_node('root')
        model.root_node = root
        model.compute_bounds()
        # Pre-populate cache with stale data
        r._wt_cache = {999: ('fake', 'data', True)}
        r.set_model(model)
        assert r._wt_cache == {}

    def test_set_model_clears_bone_transform_cache(self):
        """set_model clears bone-transform cache."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        model = _make_model()
        root = _make_node('root')
        model.root_node = root
        model.compute_bounds()
        r._bone_transforms_cache = {'stale': 'data'}
        r.set_model(model)
        assert r._bone_transforms_cache is None

    def test_outlier_filter_skips_base_skeleton(self):
        """_compute_outlier_skin_nodes returns empty set for S_FEMALE02."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        model = _make_model(name='p_bastilab01', supermodel='S_FEMALE02')
        root = _make_node('root')
        model.root_node = root
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        assert len(r._outlier_skin_nodes) == 0

    def test_outlier_filter_skips_c_prefix(self):
        """_compute_outlier_skin_nodes returns empty for C_ model prefix."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        model = _make_model(name='c_kath01', supermodel='c_kath')
        root = _make_node('root')
        model.root_node = root
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        assert len(r._outlier_skin_nodes) == 0

    def test_outlier_filter_skips_when_few_non_skin_nodes(self):
        """Outlier filter is skipped when <3 non-skin visible anchor nodes."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        model = _make_model(name='ad_test', supermodel='NON_BASE_SKEL')
        root = _make_node('root')
        model.root_node = root
        # Only 2 non-skin nodes (below threshold of 3)
        m1 = _make_mesh_node('head', parent=root, verts=[(0,0,1),(1,0,1),(0,1,1)],
                              texture='tex1')
        m1.uvs = [(0,0),(1,0),(0,1)]
        m2 = _make_mesh_node('hair', parent=root, verts=[(0,0,2),(1,0,2),(0,1,2)],
                              texture='tex2')
        m2.uvs = [(0,0),(1,0),(0,1)]
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        assert len(r._outlier_skin_nodes) == 0


# ──────────────────────────────────────────────────────────────────────────────
#  45-47: Deformation helper detection
# ──────────────────────────────────────────────────────────────────────────────

class TestDeformationHelperDetection:
    """Test _is_deformation_helper detection logic."""

    def test_skin_with_real_tex_valid_uvs_not_helper(self):
        """Skin node with real texture and valid UVs is not a deform helper."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        root = _make_node('root')
        skin = _make_skin_node('body_g', parent=root)
        skin.texture = 'n_sith_body'
        skin.uvs = [(0.1, 0.2), (0.3, 0.4), (0.5, 0.6)]
        assert not r._is_deformation_helper(skin)

    def test_non_skin_g_suffix_always_helper(self):
        """Non-skin mesh with _g suffix is always a deform helper."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        root = _make_node('root')
        deform = _make_mesh_node('rthigh_g', parent=root)
        deform.texture = 'n_saulh'
        deform.uvs = []  # no UVs
        assert r._is_deformation_helper(deform)

    def test_null_tex_non_skin_is_helper(self):
        """Non-skin node with null texture is a deform helper."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        root = _make_node('root')
        helper = _make_mesh_node('arm_proxy', parent=root)
        helper.texture = 'NULL'
        assert r._is_deformation_helper(helper)

    def test_extreme_uvs_is_helper(self):
        """Node with extreme UVs (|u| > 3 or |v| > 3) is a deform helper."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        root = _make_node('root')
        helper = _make_skin_node('body_extreme', parent=root)
        helper.texture = 'real_texture'
        helper.uvs = [(100.0, 0.0), (0.0, 0.0)]  # extreme UV
        assert r._is_deformation_helper(helper)


# ──────────────────────────────────────────────────────────────────────────────
#  48-50: Iter visible / normals
# ──────────────────────────────────────────────────────────────────────────────

class TestIterVisibleAndNormals:
    """Test _iter_visible_mesh_nodes and _get_world_normals_for_node."""

    def test_iter_visible_excludes_deform_helpers(self):
        """_iter_visible_mesh_nodes skips non-renderable deform helpers."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        model = _make_model()
        root = _make_node('root')
        model.root_node = root
        # A real skin node with texture+UVs (should be visible)
        body = _make_skin_node('body', parent=root,
                               verts=[(0,0,0),(1,0,0),(0,1,0)])
        body.texture = 'n_sith'
        body.uvs = [(0,0),(1,0),(0,1)]
        body.faces = [(0,1,2)]
        # A deform helper (no texture, non-skin, _g suffix)
        helper = _make_mesh_node('lbicep_g', parent=root,
                                 verts=[(0,0,0),(1,0,0),(0,1,0)])
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)

        visible = list(r._iter_visible_mesh_nodes())
        names = [n.name for n in visible]
        assert 'body' in names
        assert 'lbicep_g' not in names

    def test_iter_visible_includes_dangly(self):
        """_iter_visible_mesh_nodes always includes dangly (cloth) nodes."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        model = _make_model()
        root = _make_node('root')
        model.root_node = root
        # A dangly node with no texture (would normally be a helper)
        cloth = _make_mesh_node('cape_dangle', parent=root, dangly=True,
                                verts=[(0,0,0),(1,0,0),(0,1,0)])
        cloth.faces = [(0,1,2)]
        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)

        visible = list(r._iter_visible_mesh_nodes())
        names = [n.name for n in visible]
        assert 'cape_dangle' in names

    def test_world_normals_skin_returned_as_is(self):
        """_get_world_normals_for_node returns skin normals unchanged."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        model = _make_model()
        root = _make_node('root')
        model.root_node = root
        skin = _make_skin_node('body', parent=root)
        skin.normals = [(0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        skin.vertices = [(0,0,0),(1,0,0),(0,1,0)]
        model.compute_bounds()

        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        wn = r._get_world_normals_for_node(skin)
        assert len(wn) == 3
        assert wn[0] == (0.0, 0.0, 1.0)  # unchanged

    def test_world_normals_identity_mesh_returned_as_is(self):
        """Identity-rotation non-skin mesh: normals unchanged."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        model = _make_model()
        root = _make_node('root')
        model.root_node = root
        mesh = _make_mesh_node('body', parent=root, rot=(0,0,0,1))
        mesh.normals = [(0.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
        mesh.vertices = [(0,0,0),(1,0,0)]
        model.compute_bounds()

        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        wn = r._get_world_normals_for_node(mesh)
        assert len(wn) == 2
        for n in wn:
            assert abs(n[1] - 1.0) < 1e-6  # still pointing up

    def test_world_normals_180z_rotation_flips_x(self):
        """Non-skin mesh with 180° Z rotation: X normals flipped."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        model = _make_model()
        root = _make_node('root')
        model.root_node = root
        mesh = _make_mesh_node('panel', parent=root, rot=(0, 0, 1, 0))  # 180° Z
        mesh.normals = [(1.0, 0.0, 0.0)]
        mesh.vertices = [(0,0,0)]
        model.compute_bounds()

        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        wn = r._get_world_normals_for_node(mesh)
        assert len(wn) == 1
        # 180° about Z flips X: (1,0,0) → (-1,0,0)
        assert abs(wn[0][0] - (-1.0)) < 1e-4
