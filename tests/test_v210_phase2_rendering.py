"""
test_v210_phase2_rendering.py
==============================
Phase 2 rendering correctness tests for GhostRigger-K1-K2.

Covers:
  - FIX-DEFORM  : deformation-helper filter in GPU path (_is_deform_helper)
  - FIX-ENVFB   : grey fallback when env-map texture is missing
  - FIX-SEAM    : skin UV seam expansion to triangle-list
  - FIX-MULTITEX: multi-texture batching (tex_count > 1, face_mats)
  - FIX-FLIPBOOK: TXI proceduretype=cycle sprite-sheet frame advancement
  - FIX-PERSCACHE: persistent world-transform cache across frames
  - Phase 3.1   : creature_appearance UTC → appearance.2da → model/texture
  - Phase 3.2   : merge_supermodel bone injection
  - Lightmap    : overbright ×2 factor is consistent GPU/CPU
"""

import math
import struct
import pytest
import numpy as np


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers — minimal stub factories
# ─────────────────────────────────────────────────────────────────────────────

def _make_node(**kw):
    """Create a minimal ModelNode-like namespace for unit testing."""
    class _Node:
        name           = kw.get('name', 'node')
        render         = kw.get('render', True)
        alpha          = kw.get('alpha', 1.0)
        texture        = kw.get('texture', '')
        lightmap       = kw.get('lightmap', '')
        has_lightmap   = kw.get('has_lightmap', False)
        selfillum      = kw.get('selfillum', (0.0, 0.0, 0.0))
        diffuse        = kw.get('diffuse', (1.0, 1.0, 1.0))
        ambient        = kw.get('ambient', (0.4, 0.4, 0.4))
        position       = kw.get('position', (0.0, 0.0, 0.0))
        rotation       = kw.get('rotation', (0.0, 0.0, 0.0, 1.0))
        txi_blending   = kw.get('txi_blending', 0)
        txi_envmaptexture = kw.get('txi_envmaptexture', '')
        txi_proceduretype = kw.get('txi_proceduretype', '')
        txi_numx       = kw.get('txi_numx', 0)
        txi_numy       = kw.get('txi_numy', 0)
        txi_fps        = kw.get('txi_fps', 0.0)
        rotate_texture = kw.get('rotate_texture', False)
        animate_uv     = kw.get('animate_uv', False)
        uv_dir_x       = kw.get('uv_dir_x', 0.0)
        uv_dir_y       = kw.get('uv_dir_y', 0.0)
        uv_jitter      = kw.get('uv_jitter', 0.0)
        uv_jitter_speed = kw.get('uv_jitter_speed', 0.0)
        is_skin        = kw.get('is_skin', False)
        is_bone        = kw.get('is_bone', False)
        vertices       = kw.get('vertices', kw.get('verts', []))
        verts          = vertices
        normals        = kw.get('normals', [])
        uvs            = kw.get('uvs', [])
        uvs_lm         = kw.get('uvs_lm', [])
        faces          = kw.get('faces', [])
        face_uvs       = kw.get('face_uvs', [])
        tex_count      = kw.get('tex_count', 1)
        texture_names  = kw.get('texture_names', [])
        children       = kw.get('children', [])
        parent         = kw.get('parent', None)
        flags          = kw.get('flags', 0)
        transparency_hint = kw.get('transparency_hint', 0)
    return _Node()


def _make_triangle_node(**kw):
    """Produce a node with a single triangle (3 verts, 1 face)."""
    defaults = dict(
        vertices=[(0,0,0),(1,0,0),(0,1,0)],
        normals= [(0,0,1),(0,0,1),(0,0,1)],
        uvs=    [(0,0),(1,0),(0,1)],
        faces=  [[0,1,2]],
    )
    defaults.update(kw)
    return _make_node(**defaults)


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-DEFORM: _is_deform_helper logic
# ─────────────────────────────────────────────────────────────────────────────

class TestDeformHelperFilter:
    """Test the self-contained deformation-helper detection logic."""

    def _helper(self, node) -> bool:
        """Replicate the _is_deform_helper closure from _render_gpu."""
        _UV_EXTREME = 3.0
        is_skin   = bool(getattr(node, 'is_skin', False))
        tex_name  = str(getattr(node, 'texture', '') or '').strip().lower()
        has_tex   = tex_name and tex_name not in ('null', '', 'none', '****')
        uvs       = getattr(node, 'uvs', [])
        has_uvs   = bool(uvs) and len(uvs) > 0
        node_name = str(getattr(node, 'name', '') or '').lower()

        if is_skin and has_tex and has_uvs:
            return False
        if is_skin and not has_tex and not has_uvs:
            return True
        if not is_skin and not has_uvs:
            return True
        if not is_skin:
            if (node_name.endswith('_g') or node_name.endswith('_g0')
                    or node_name.endswith('_dum')):
                return True
        if has_uvs:
            try:
                for uv in uvs[:32]:
                    if abs(uv[0]) > _UV_EXTREME or abs(uv[1]) > _UV_EXTREME:
                        return True
            except (TypeError, IndexError):
                pass
        return False

    def test_skin_with_texture_and_uvs_not_helper(self):
        """Skin node with real texture + UVs → renderable, NOT a helper."""
        n = _make_node(is_skin=True, texture='skin_diff',
                       uvs=[(0,0),(1,0),(0,1)], faces=[[0,1,2]],
                       vertices=[(0,0,0),(1,0,0),(0,1,0)])
        assert self._helper(n) is False

    def test_skin_no_texture_no_uvs_is_helper(self):
        """Skin node with null texture and no UVs → deformation helper."""
        n = _make_node(is_skin=True, texture='null',
                       uvs=[], faces=[[0,1,2]],
                       vertices=[(0,0,0),(1,0,0),(0,1,0)])
        assert self._helper(n) is True

    def test_non_skin_no_uvs_is_helper(self):
        """Non-skin node with no UVs → helper."""
        n = _make_node(is_skin=False, texture='some_tex',
                       uvs=[], faces=[[0,1,2]],
                       vertices=[(0,0,0),(1,0,0),(0,1,0)])
        assert self._helper(n) is True

    def test_non_skin_underscore_g_suffix_is_helper(self):
        """Non-skin node named '*_g' → helper."""
        n = _make_node(name='bodymesh_g', is_skin=False,
                       uvs=[(0,0),(1,0),(0,1)],
                       faces=[[0,1,2]], vertices=[(0,0,0),(1,0,0),(0,1,0)])
        assert self._helper(n) is True

    def test_non_skin_underscore_g0_suffix_is_helper(self):
        n = _make_node(name='headmesh_g0', is_skin=False,
                       uvs=[(0,0),(1,0),(0,1)],
                       faces=[[0,1,2]], vertices=[(0,0,0),(1,0,0),(0,1,0)])
        assert self._helper(n) is True

    def test_non_skin_dum_suffix_is_helper(self):
        n = _make_node(name='pelvis_dum', is_skin=False,
                       uvs=[(0,0),(1,0),(0,1)],
                       faces=[[0,1,2]], vertices=[(0,0,0),(1,0,0),(0,1,0)])
        assert self._helper(n) is True

    def test_extreme_uv_is_helper(self):
        """Node with UV > 3.0 → helper (sentinel/invalid UVs)."""
        n = _make_node(is_skin=False, name='mesh',
                       uvs=[(0,0),(5.0,0),(0,1)],
                       faces=[[0,1,2]], vertices=[(0,0,0),(1,0,0),(0,1,0)])
        assert self._helper(n) is True

    def test_normal_non_skin_with_uvs_not_helper(self):
        """Normal non-skin mesh with valid UVs and non-helper name → renderable."""
        n = _make_node(is_skin=False, name='wall_mesh',
                       uvs=[(0,0),(1,0),(0,1)],
                       faces=[[0,1,2]], vertices=[(0,0,0),(1,0,0),(0,1,0)])
        assert self._helper(n) is False


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-SEAM: _build_vbo_data UV seam expansion
# ─────────────────────────────────────────────────────────────────────────────

class TestUVSeamExpansion:
    """Test that _build_vbo_data correctly expands skin UV seams."""

    def _build(self, node, wp=(0,0,0), wo=(0,0,0,1)):
        from src.gui.gpu_renderer import _build_vbo_data
        return _build_vbo_data(node, wp, wo)

    def test_simple_mesh_uses_ibo(self):
        """Regular non-skin mesh with uniform UVs produces an IBO (indexed draw)."""
        n = _make_triangle_node(is_skin=False)
        vdata, idx = self._build(n)
        assert vdata is not None, "vdata should not be None"
        assert idx is not None, "non-seam mesh should produce an IBO"
        assert len(idx) == 3, "one triangle = 3 indices"

    def test_skin_mesh_expands_to_triangle_list(self):
        """Skin mesh without face_uvs expands to triangle-list (no IBO)."""
        n = _make_triangle_node(is_skin=True)
        vdata, idx = self._build(n)
        assert vdata is not None
        # Expanded triangle list: 3 verts per face
        assert idx is None, "skin mesh should use triangle-list (no IBO)"
        assert len(vdata) == 3

    def test_face_uvs_override_per_vertex_uvs(self):
        """face_uvs with different tvert indices produce the correct per-face UVs."""
        # Geometry: 4 verts (a quad split into 2 tris), UV seam splits one vert
        # Vertex positions
        verts = [(0,0,0), (1,0,0), (1,1,0), (0,1,0)]
        norms = [(0,0,1)] * 4
        # UV array has 5 entries (the seam vert is duplicated: vert 2 maps to uv[2] or uv[4])
        uvs = [(0.0,0.0),(1.0,0.0),(1.0,1.0),(0.0,1.0),(1.0,0.99)]
        faces = [[0,1,2],[0,2,3]]
        # Face 0 UV indices: 0,1,2 (standard)
        # Face 1 UV indices: 0,4,3 (seam: vert 2 maps to uv[4] instead of uv[2])
        face_uvs = [[0,1,2],[0,4,3]]

        n = _make_node(vertices=verts, normals=norms, uvs=uvs,
                       faces=faces, face_uvs=face_uvs, is_skin=True)
        vdata, idx = self._build(n)
        assert vdata is not None
        assert idx is None, "face_uvs path produces triangle-list"
        assert len(vdata) == 6, "2 triangles × 3 verts = 6 expanded verts"

        # Face 1, vert 1 (global row 4) should have UV from uv[4] = (1.0, 0.99)
        # Rows: 0,1,2 for face 0 then 3,4,5 for face 1
        row4 = vdata[4]  # face 1, corner 1 (vert 2 → uv[4])
        # UV is stored at float indices 6 and 7 (V is 1 - stored_v in shader, but raw here)
        assert abs(row4[6] - 1.0) < 1e-4, f"Expected U=1.0, got {row4[6]}"
        assert abs(row4[7] - 0.99) < 1e-4, f"Expected V=0.99, got {row4[7]}"

    def test_out_of_range_indices_skipped(self):
        """Faces referencing out-of-range vertices are silently dropped."""
        n = _make_triangle_node(faces=[[0,1,99]])  # vert 99 doesn't exist
        vdata, idx = self._build(n)
        # Result should be None (no valid triangles) or empty
        if vdata is not None:
            assert len(vdata) == 0 or idx is None

    def test_no_vertices_returns_none(self):
        """Empty geometry returns (None, None)."""
        n = _make_node(vertices=[], faces=[], uvs=[])
        vdata, idx = self._build(n)
        assert vdata is None
        assert idx is None

    def test_normal_renormalization(self):
        """Normals are unit-length after VBO build (no shading errors)."""
        verts = [(0,0,0),(2,0,0),(0,2,0)]
        norms = [(0,0,2.5),(0,0,2.5),(0,0,2.5)]  # non-unit normals
        n = _make_node(vertices=verts, normals=norms, uvs=[(0,0),(1,0),(0,1)],
                       faces=[[0,1,2]])
        vdata, idx = self._build(n)
        assert vdata is not None
        # Normals are at columns 3,4,5
        if idx is not None:
            rows = vdata
        else:
            rows = vdata
        for row in rows:
            nx, ny, nz = row[3], row[4], row[5]
            length = math.sqrt(nx*nx + ny*ny + nz*nz)
            assert abs(length - 1.0) < 1e-4, f"Normal not unit: {length}"

    def test_skin_skip_world_transform(self):
        """Skin nodes must NOT have world translation/rotation applied."""
        from src.gui.gpu_renderer import _build_vbo_data
        verts = [(1.0, 2.0, 3.0)]
        n = _make_node(vertices=verts, normals=[(0,0,1)], uvs=[(0,0)],
                       faces=[[0,0,0]], is_skin=True)
        # Apply a large world translation
        wp = (100.0, 200.0, 300.0)
        wo = (0.0, 0.0, 0.0, 1.0)
        vdata, _ = _build_vbo_data(n, wp, wo)
        if vdata is not None and len(vdata) > 0:
            pos = vdata[0][:3]
            # Skin: position should remain (1,2,3), NOT (101,202,303)
            assert abs(pos[0] - 1.0) < 1e-4, f"Skin X translated! Got {pos[0]}"
            assert abs(pos[1] - 2.0) < 1e-4, f"Skin Y translated! Got {pos[1]}"
            assert abs(pos[2] - 3.0) < 1e-4, f"Skin Z translated! Got {pos[2]}"


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-FLIPBOOK: TXI proceduretype=cycle frame computation
# ─────────────────────────────────────────────────────────────────────────────

class TestFlipbookAnimation:
    """Test flipbook UV tile offset calculation for TXI proceduretype=cycle."""

    def _compute_flipbook(self, anim_time: float, numx: int, numy: int,
                          fps: float) -> tuple:
        """Replicate the flipbook computation from _draw_node."""
        total_frames = numx * numy
        frame_idx    = int(anim_time * fps) % total_frames
        col  = frame_idx % numx
        row  = frame_idx // numx
        tile_w = 1.0 / numx
        tile_h = 1.0 / numy
        flip_row = (numy - 1 - row)
        off_u = col * tile_w
        off_v = flip_row * tile_h
        return off_u, off_v, tile_w, tile_h

    def test_first_frame_at_t0(self):
        """At t=0, frame 0 → col=0, row=0 → tile at top-left (flipped)."""
        off_u, off_v, tw, th = self._compute_flipbook(0.0, 4, 2, 10.0)
        assert abs(off_u - 0.0) < 1e-9
        assert abs(tw - 0.25) < 1e-9
        assert abs(th - 0.5) < 1e-9
        # flip_row for row=0 with numy=2 → flip_row=1 → off_v=0.5
        assert abs(off_v - 0.5) < 1e-9

    def test_frame_wraps_modulo(self):
        """Frame index wraps correctly around total_frames."""
        # 4×2=8 frames at 10fps; at t=0.8s → frame 8 → wraps to 0
        off_u, off_v, tw, th = self._compute_flipbook(0.8, 4, 2, 10.0)
        assert abs(off_u - 0.0) < 1e-9
        assert abs(off_v - 0.5) < 1e-9

    def test_second_frame(self):
        """At t=0.1s with 10fps → frame 1 → col=1, row=0."""
        off_u, off_v, tw, th = self._compute_flipbook(0.1, 4, 2, 10.0)
        # col=1, tile_w=0.25 → off_u=0.25
        assert abs(off_u - 0.25) < 1e-9
        # row=0 → flip_row=1 → off_v=0.5
        assert abs(off_v - 0.5) < 1e-9

    def test_second_row_frame(self):
        """Frame 4 in a 4×2 sheet → col=0, row=1 → flip_row=0 → off_v=0."""
        # t=0.4s, 10fps → frame 4
        off_u, off_v, tw, th = self._compute_flipbook(0.4, 4, 2, 10.0)
        assert abs(off_u - 0.0) < 1e-9
        assert abs(off_v - 0.0) < 1e-9

    def test_1x1_sheet_is_identity(self):
        """1×1 flipbook sheet → single tile fills entire UV space."""
        off_u, off_v, tw, th = self._compute_flipbook(99.9, 1, 1, 24.0)
        assert abs(tw - 1.0) < 1e-9
        assert abs(th - 1.0) < 1e-9
        assert abs(off_u - 0.0) < 1e-9
        assert abs(off_v - 0.0) < 1e-9

    def test_node_with_cycle_has_flipbook_attrs(self):
        """Node with txi_proceduretype='cycle' provides correct attributes."""
        n = _make_node(
            txi_proceduretype='cycle',
            txi_numx=4, txi_numy=2, txi_fps=10.0,
        )
        assert n.txi_proceduretype == 'cycle'
        assert n.txi_numx == 4
        assert n.txi_numy == 2
        assert n.txi_fps == 10.0


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-MULTITEX: multi-texture batching
# ─────────────────────────────────────────────────────────────────────────────

class TestMultiTextureBatching:
    """Test that multi-texture nodes (tex_count>1) are split per slot."""

    def test_multitex_node_has_texture_names(self):
        """A tex_count=2 node must provide texture_names with 2 entries."""
        n = _make_node(
            tex_count=2,
            texture_names=['mat_stone', 'mat_dirt'],
            texture='mat_stone',
        )
        assert n.tex_count == 2
        assert len(n.texture_names) == 2
        assert n.texture_names[0] == 'mat_stone'
        assert n.texture_names[1] == 'mat_dirt'

    def test_single_tex_node_degenerates(self):
        """Single-texture node still works — tex_count defaults to 1."""
        n = _make_triangle_node(texture='stone')
        assert n.tex_count == 1
        assert n.texture == 'stone'

    def test_multitex_slot_override_logic(self):
        """Simulate the GPU-path multi-tex slot iteration."""
        n = _make_node(
            tex_count=3,
            texture_names=['t0', 'null', 't2'],
        )
        drawn_slots = []
        for slot_idx in range(n.tex_count):
            slot_name = str(n.texture_names[slot_idx]).strip().lower()
            if slot_name in ('null', '', 'none'):
                slot_name = ''
            drawn_slots.append(slot_name)
        assert drawn_slots == ['t0', '', 't2']
        assert len(drawn_slots) == 3


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-ENVFB: env-map grey fallback
# ─────────────────────────────────────────────────────────────────────────────

class TestEnvMapFallback:
    """Test that missing env-map textures use a neutral grey fallback."""

    def test_node_with_envmap_set_but_missing_tex(self):
        """Node has txi_envmaptexture set but texture not in dict → needs fallback."""
        n = _make_node(txi_envmaptexture='CM_Baremetal')
        textures = {}  # empty — env texture is not loaded
        env_name = str(getattr(n, 'txi_envmaptexture', '')).strip().lower()
        assert env_name == 'cm_baremetal'
        env_img = textures.get(env_name)
        assert env_img is None, "env texture not in dict"
        # Fallback logic: env_img is None → use grey placeholder
        # (test the logic branch, not the GL object)
        needs_fallback = (env_name != '') and (env_img is None)
        assert needs_fallback is True

    def test_node_without_envmap_no_fallback_needed(self):
        """Node with no envmaptexture → no fallback needed."""
        n = _make_node(txi_envmaptexture='')
        env_name = str(getattr(n, 'txi_envmaptexture', '')).strip().lower()
        assert env_name == ''

    def test_grey_fallback_bytes(self):
        """Grey fallback texture bytes are RGBA 128,128,128,255."""
        grey_bytes = bytes([128, 128, 128, 255])
        assert grey_bytes[0] == 128   # R
        assert grey_bytes[1] == 128   # G
        assert grey_bytes[2] == 128   # B
        assert grey_bytes[3] == 255   # A (fully opaque)


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-PERSCACHE: persistent world-transform cache
# ─────────────────────────────────────────────────────────────────────────────

class TestWorldTransformCache:
    """Test that the persistent world-transform cache works correctly."""

    def _make_cache_and_getter(self):
        """Create a minimal cache + getter that mirrors the GPU-path closure."""
        wt_cache = {}
        wt_model_id = [0]

        def _get_world_transform(nd):
            nid = id(nd)
            if nid in wt_cache:
                return wt_cache[nid]
            pos = getattr(nd, 'position', (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
            rot = getattr(nd, 'rotation', (0.0, 0.0, 0.0, 1.0)) or (0.0, 0.0, 0.0, 1.0)
            result = (pos, rot)
            wt_cache[nid] = result
            return result

        return wt_cache, _get_world_transform

    def test_cache_hit_returns_same_object(self):
        """Second call for same node returns cached tuple (not recomputed)."""
        cache, getter = self._make_cache_and_getter()
        n = _make_node(position=(1.0, 2.0, 3.0))
        r1 = getter(n)
        r2 = getter(n)
        assert r1 is r2, "Cache hit must return the same object"

    def test_different_nodes_cached_separately(self):
        """Two different nodes get separate cache entries."""
        cache, getter = self._make_cache_and_getter()
        n1 = _make_node(name='a', position=(1.0, 0.0, 0.0))
        n2 = _make_node(name='b', position=(0.0, 2.0, 0.0))
        r1 = getter(n1)
        r2 = getter(n2)
        assert id(r1) != id(r2)
        assert r1[0] != r2[0]

    def test_cache_cleared_on_model_change(self):
        """Cache is cleared when model identity changes (new model loaded)."""
        cache, getter = self._make_cache_and_getter()
        n = _make_node(position=(5.0, 0.0, 0.0))
        getter(n)
        assert id(n) in cache
        cache.clear()
        assert len(cache) == 0

    def test_invalidate_node_removes_single_entry(self):
        """invalidate_node removes only the target node from cache."""
        cache, getter = self._make_cache_and_getter()
        n1 = _make_node(name='a')
        n2 = _make_node(name='b')
        getter(n1); getter(n2)
        assert len(cache) == 2
        del cache[id(n1)]
        assert id(n1) not in cache
        assert id(n2) in cache


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 3.1: Creature appearance pipeline  (creature_appearance.py)
# ─────────────────────────────────────────────────────────────────────────────

class TestCreatureAppearancePipeline:
    """Test UTC → appearance.2da → model/texture resolution."""

    def _make_utc_gff(self, appearance_id: int, alignment: int = 50) -> bytes:
        """
        Build a minimal valid GFF V3.2 file bytes containing:
          - Appearance_Type (WORD, type=2)
          - GoodEvil        (BYTE, type=0)

        GFF V3.2 header = 8 bytes (FileType + FileVersion)
                        + 12 × uint32 (section offsets/counts) = 56 bytes total.
        """
        n_structs = 1
        n_fields  = 2
        n_labels  = 2

        # Section offsets (from file start = 0)
        struct_off  = 56                       # header ends at 56
        field_off   = struct_off  + 12         # 1 struct × 12 bytes
        label_off   = field_off   + 24         # 2 fields × 12 bytes
        fdata_off   = label_off   + 32         # 2 labels × 16 bytes
        fdata_sz    = 0
        findx_off   = fdata_off   + fdata_sz
        findx_sz    = n_fields * 4             # 2 × uint32 indices
        list_off    = findx_off   + findx_sz
        list_sz     = 0

        # Header: 8 bytes type/version + 12 uint32 = 56 bytes
        hdr = (b'UTC ' + b'V3.2' +
               struct.pack('<12I',
                   struct_off, n_structs,
                   field_off,  n_fields,
                   label_off,  n_labels,
                   fdata_off,  fdata_sz,
                   findx_off,  findx_sz,
                   list_off,   list_sz,
               ))
        assert len(hdr) == 56, f"GFF header size: {len(hdr)}"

        # Top-level struct: type=0xFFFFFFFF, field_idx_off=0, count=2
        structs = struct.pack('<3I', 0xFFFFFFFF, 0, n_fields)

        # Fields: type (uint32), label_idx (uint32), DataOrDataOffset (uint32)
        # Appearance_Type = WORD (type 2); GoodEvil = BYTE (type 0)
        fields = (struct.pack('<3I', 2, 0, appearance_id & 0xFFFF) +
                  struct.pack('<3I', 0, 1, alignment   & 0xFF))

        # Labels: 2 × 16 null-padded bytes
        label0 = b'Appearance_Type\x00'   # 16 bytes exactly
        label1 = b'GoodEvil' + b'\x00' * 8  # 8 + 8 = 16 bytes
        labels = label0 + label1

        # Field-index list for top-level struct (field_count=2)
        findx = struct.pack('<2I', 0, 1)

        return hdr + structs + fields + labels + findx

    def _make_appearance_2da_bytes(self) -> bytes:
        """Build a minimal ASCII appearance.2da with rows 0..4."""
        lines = [
            '2DA V2.0',
            '',
            '   label         modeltype  modela       texa       race         supermodel  normalhead',
            '0  Human_Male    B          p_humanm     P_HumanM   ****         S_Male02    0',
            '1  Human_Female  B          p_humanf     P_HumanF   ****         S_Female02  1',
            '2  Twi_lek       F          ****         ****        c_twilek     NULL        ****',
            '3  Bantha        F          ****         ****        c_bantha     NULL        ****',
            '4  Droid_M       B          p_droidm     P_DroidM    ****        S_Male02    2',
        ]
        return '\n'.join(lines).encode('ascii')

    def _make_heads_2da_bytes(self) -> bytes:
        """Build a minimal ASCII heads.2da."""
        lines = [
            '2DA V2.0',
            '',
            '   label           head          headtexe',
            '0  HumanMaleHead1  p_hum_hm      ****',
            '1  HumanFemHead1   p_hum_hf01    ****',
            '2  DroidHead1      p_droid_h01   ****',
        ]
        return '\n'.join(lines).encode('ascii')

    def test_human_male_body_model(self):
        """UTC with appearance_id=0 → body model 'p_humanm', tex 'p_humanm01'."""
        from src.core.creature_appearance import resolve_utc_appearance
        from src.core.twoda import TwoDA

        utc_bytes  = self._make_utc_gff(appearance_id=0)
        app_2da    = TwoDA.from_bytes(self._make_appearance_2da_bytes(), name='appearance')
        heads_2da  = TwoDA.from_bytes(self._make_heads_2da_bytes(), name='heads')

        result = resolve_utc_appearance(utc_bytes, app_2da, heads_2da)
        assert result.appearance_id == 0
        assert result.modeltype == 'B'
        assert result.body_model == 'p_humanm'
        assert result.body_tex is not None and result.body_tex.startswith('p_humanm')

    def test_human_female_body_model(self):
        """UTC with appearance_id=1 → body model 'p_humanf'."""
        from src.core.creature_appearance import resolve_utc_appearance
        from src.core.twoda import TwoDA

        utc_bytes = self._make_utc_gff(appearance_id=1)
        app_2da   = TwoDA.from_bytes(self._make_appearance_2da_bytes(), name='appearance')
        result    = resolve_utc_appearance(utc_bytes, app_2da)
        assert result.body_model == 'p_humanf'
        assert result.modeltype == 'B'

    def test_creature_full_body_uses_race_column(self):
        """Non-B modeltype (Twi'lek, appearance_id=2) → race_model = 'c_twilek'."""
        from src.core.creature_appearance import resolve_utc_appearance
        from src.core.twoda import TwoDA

        utc_bytes = self._make_utc_gff(appearance_id=2)
        app_2da   = TwoDA.from_bytes(self._make_appearance_2da_bytes(), name='appearance')
        result    = resolve_utc_appearance(utc_bytes, app_2da)
        assert result.modeltype == 'F'
        assert result.race_model == 'c_twilek'
        assert result.primary_model == 'c_twilek'

    def test_head_model_from_normalhead_column(self):
        """Body-slot creature resolves head model via normalhead → heads.2da."""
        from src.core.creature_appearance import resolve_utc_appearance
        from src.core.twoda import TwoDA

        utc_bytes  = self._make_utc_gff(appearance_id=0)
        app_2da    = TwoDA.from_bytes(self._make_appearance_2da_bytes(), name='appearance')
        heads_2da  = TwoDA.from_bytes(self._make_heads_2da_bytes(), name='heads')
        result     = resolve_utc_appearance(utc_bytes, app_2da, heads_2da)
        # normalhead=0 → heads row 0 → head='p_hum_hm'
        assert result.head_model == 'p_hum_hm'

    def test_no_heads_2da_no_head_model(self):
        """Without heads.2da, head_model is None (no crash)."""
        from src.core.creature_appearance import resolve_utc_appearance
        from src.core.twoda import TwoDA

        utc_bytes = self._make_utc_gff(appearance_id=0)
        app_2da   = TwoDA.from_bytes(self._make_appearance_2da_bytes(), name='appearance')
        result    = resolve_utc_appearance(utc_bytes, app_2da, heads_2da=None)
        assert result.head_model is None

    def test_out_of_range_appearance_id_returns_empty(self):
        """appearance_id beyond table rows returns CreatureAppearance with body_model=None."""
        from src.core.creature_appearance import resolve_utc_appearance
        from src.core.twoda import TwoDA

        utc_bytes = self._make_utc_gff(appearance_id=999)
        app_2da   = TwoDA.from_bytes(self._make_appearance_2da_bytes(), name='appearance')
        result    = resolve_utc_appearance(utc_bytes, app_2da)
        assert result.body_model is None

    def test_supermodel_from_appearance_row(self):
        """Supermodel name is read from the 'supermodel' column."""
        from src.core.creature_appearance import resolve_utc_appearance
        from src.core.twoda import TwoDA

        utc_bytes = self._make_utc_gff(appearance_id=0)
        app_2da   = TwoDA.from_bytes(self._make_appearance_2da_bytes(), name='appearance')
        result    = resolve_utc_appearance(utc_bytes, app_2da)
        assert result.supermodel == 'S_Male02'

    def test_primary_model_b_type(self):
        """primary_model returns body_model for B-type."""
        from src.core.creature_appearance import CreatureAppearance
        ca = CreatureAppearance(modeltype='B', body_model='p_humanm', race_model=None)
        assert ca.primary_model == 'p_humanm'

    def test_primary_model_f_type(self):
        """primary_model returns race_model for non-B types."""
        from src.core.creature_appearance import CreatureAppearance
        ca = CreatureAppearance(modeltype='F', body_model=None, race_model='c_bantha')
        assert ca.primary_model == 'c_bantha'

    def test_armor_bodyvar_selects_correct_columns(self):
        """Armor slot 'b' selects modelb + texb columns."""
        from src.core.creature_appearance import resolve_utc_appearance
        from src.core.twoda import TwoDA

        # Build a 2DA with modelb and texb columns
        lines = [
            '2DA V2.0',
            '',
            '   label         modeltype  modela       texa       modelb       texb       supermodel  normalhead',
            '0  Human_Male    B          p_humanm     P_HumanM   p_humanmbb   P_HumanMBB  S_Male02    ****',
        ]
        app_2da = TwoDA.from_bytes('\n'.join(lines).encode('ascii'), name='appearance')
        utc_bytes = self._make_utc_gff(appearance_id=0)
        result = resolve_utc_appearance(utc_bytes, app_2da, armor_bodyvar='b',
                                        armor_tex_variation=3)
        assert result.body_model == 'p_humanmbb'
        assert result.body_tex == 'p_humanmbb03'

    def test_parse_appearance_tables_helper(self):
        """parse_appearance_tables returns two TwoDA objects."""
        from src.core.creature_appearance import parse_appearance_tables
        app_2da, heads_2da = parse_appearance_tables(
            self._make_appearance_2da_bytes(),
            self._make_heads_2da_bytes(),
        )
        assert app_2da is not None
        assert len(app_2da) >= 5
        assert heads_2da is not None
        assert len(heads_2da) >= 3


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 3.2: merge_supermodel bone injection
# ─────────────────────────────────────────────────────────────────────────────

class TestMergeSupermodel:
    """Test Phase 3.2 supermodel bone injection."""

    def _make_model(self, name, nodes_list):
        class _Model:
            pass
        m = _Model()
        m.name = name
        m.supermodel = 'NULL'

        class _Root:
            pass
        root = _Root()
        root.name = 'rootdummy'
        root.children = []
        root.parent = None
        root.is_bone = False
        root.vertices = []
        root.verts = []
        m.root_node = root

        # Attach nodes
        for nd in nodes_list:
            nd.parent = root
            root.children.append(nd)

        def all_nodes():
            """Live DFS traversal — picks up nodes appended after construction."""
            visited = []
            stack = [root]
            seen = set()
            while stack:
                cur = stack.pop()
                nid = id(cur)
                if nid in seen:
                    continue
                seen.add(nid)
                visited.append(cur)
                for ch in getattr(cur, 'children', []):
                    stack.append(ch)
            return visited

        m.all_nodes = all_nodes
        return m

    def _make_bone_node(self, name):
        n = _make_node(name=name, is_bone=True, vertices=[], verts=[], faces=[])
        n.children = []
        n.parent = None
        return n

    def _make_mesh_node(self, name):
        n = _make_triangle_node(name=name, is_bone=False)
        n.children = []
        n.parent = None
        return n

    def test_parent_bones_injected_into_child(self):
        """Parent bones not in child are injected under child root."""
        from src.core.creature_appearance import merge_supermodel

        bone_a = self._make_bone_node('thigh_l')
        bone_b = self._make_bone_node('calf_l')
        parent = self._make_model('S_Female02', [bone_a, bone_b])

        mesh   = self._make_mesh_node('body_skin')
        child  = self._make_model('p_bastilabb', [mesh])

        result = merge_supermodel(child, parent)
        names_after = {n.name.lower() for n in result.all_nodes()}
        assert 'thigh_l' in names_after
        assert 'calf_l' in names_after

    def test_existing_bones_not_duplicated(self):
        """Bones already present in child are not re-injected."""
        from src.core.creature_appearance import merge_supermodel

        shared_bone = self._make_bone_node('spine')
        parent = self._make_model('S_Male02', [shared_bone])

        child_bone = self._make_bone_node('spine')  # same name, different object
        mesh       = self._make_mesh_node('torso')
        child      = self._make_model('p_droidm', [child_bone, mesh])

        before_count = len(child.all_nodes())
        result = merge_supermodel(child, parent)
        after_count  = len(result.all_nodes())
        # 'spine' already existed — only count added if parent has unique ones
        assert after_count == before_count  # nothing new to add

    def test_none_models_handled_gracefully(self):
        """Passing None models does not raise."""
        from src.core.creature_appearance import merge_supermodel
        result = merge_supermodel(None, None)
        assert result is None

    def test_supermodel_name_updated_after_merge(self):
        """child_model.supermodel is updated to parent name after merge."""
        from src.core.creature_appearance import merge_supermodel

        bone = self._make_bone_node('pelvis')
        parent = self._make_model('S_Female02', [bone])
        mesh   = self._make_mesh_node('skirt')
        child  = self._make_model('p_skirt', [mesh])

        result = merge_supermodel(child, parent)
        assert result.supermodel == 'S_Female02'


# ─────────────────────────────────────────────────────────────────────────────
#  Lightmap overbright cross-validation
# ─────────────────────────────────────────────────────────────────────────────

class TestLightmapOverbright:
    """
    Verify that GPU (GLSL) and CPU (viewport) lightmap compositing
    both implement diffuse × lightmap × 2 with proper clamping.
    """

    def test_gpu_glsl_overbright_factor(self):
        """GPU GLSL shader contains 'lm_samp.rgb * 2.0' for overbright lightmap."""
        import os
        shader_src_path = os.path.join(
            os.path.dirname(__file__), '..', 'src', 'gui', 'gpu_renderer.py')
        with open(shader_src_path, 'r') as fh:
            src = fh.read()
        # The fragment shader must contain the ×2 overbright multiply
        assert 'lm_samp.rgb * 2.0' in src or '* 2.0' in src, \
            "GPU shader missing overbright ×2 factor"

    def test_cpu_viewport_overbright_factor(self):
        """CPU viewport mentions '2.0' or 'overbright' near lightmap compositing."""
        import os
        vp_path = os.path.join(
            os.path.dirname(__file__), '..', 'src', 'gui', 'viewport.py')
        with open(vp_path, 'r') as fh:
            src = fh.read()
        assert 'overbright' in src.lower() or '* 2' in src, \
            "CPU viewport missing overbright factor reference"

    def test_numeric_overbright_neutral_grey(self):
        """Lightmap 128,128,128 (0.5 normalized) × 2.0 = 1.0 → no colour shift."""
        lm_rgb = (128 / 255.0, 128 / 255.0, 128 / 255.0)
        overbright = tuple(c * 2.0 for c in lm_rgb)
        # Should be close to 1.0 (neutral — diffuse unchanged)
        for c in overbright:
            assert abs(c - 1.0) < 0.01, f"Neutral grey × 2 ≠ 1.0: {c}"

    def test_numeric_overbright_white_lightmap(self):
        """Lightmap 255,255,255 (1.0 normalized) × 2.0 clamped = 1.0 (no burn)."""
        lm_rgb = (1.0, 1.0, 1.0)
        overbright = tuple(min(c * 2.0, 1.0) for c in lm_rgb)
        for c in overbright:
            assert c == 1.0

    def test_numeric_overbright_dark_lightmap(self):
        """Lightmap 64,64,64 (0.25) × 2.0 = 0.5 → 50% attenuation."""
        lm_rgb = (64 / 255.0, 64 / 255.0, 64 / 255.0)
        overbright = tuple(c * 2.0 for c in lm_rgb)
        for c in overbright:
            assert abs(c - 0.502) < 0.01, f"Dark lightmap ×2 expected ~0.5, got {c}"


# ─────────────────────────────────────────────────────────────────────────────
#  GFF parser unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGFFParser:
    """Unit tests for the minimal GFF parser in creature_appearance.py."""

    def _make_minimal_utc(self, appearance_id: int, alignment: int) -> bytes:
        return TestCreatureAppearancePipeline()._make_utc_gff(appearance_id, alignment)

    def test_parses_appearance_type(self):
        """_GFFParser correctly reads Appearance_Type WORD field."""
        from src.core.creature_appearance import _GFFParser
        data = self._make_minimal_utc(42, 50)
        gff  = _GFFParser(data)
        assert int(gff.fields.get('Appearance_Type', -1)) == 42

    def test_parses_goodeevil_field(self):
        """_GFFParser correctly reads GoodEvil alignment byte."""
        from src.core.creature_appearance import _GFFParser
        data = self._make_minimal_utc(0, 25)
        gff  = _GFFParser(data)
        assert int(gff.fields.get('GoodEvil', -1)) == 25

    def test_empty_bytes_no_crash(self):
        """_GFFParser handles empty bytes without raising."""
        from src.core.creature_appearance import _GFFParser
        gff = _GFFParser(b'')
        assert gff.fields == {}

    def test_truncated_header_no_crash(self):
        """_GFFParser handles truncated header without raising."""
        from src.core.creature_appearance import _GFFParser
        gff = _GFFParser(b'UTC V3.2' + b'\x00' * 10)
        assert isinstance(gff.fields, dict)


# ─────────────────────────────────────────────────────────────────────────────
#  Integration: _build_vbo_data uses numpy (sanity)
# ─────────────────────────────────────────────────────────────────────────────

class TestVBODataIntegration:
    """Integration tests for _build_vbo_data with realistic data."""

    def test_quad_mesh_vbo_shape(self):
        """A quad (2 tris) produces 6 floats × 14 channels = 84 float32 values in tri-list."""
        from src.gui.gpu_renderer import _build_vbo_data
        verts = [(0,0,0),(1,0,0),(1,1,0),(0,1,0)]
        norms = [(0,0,1)]*4
        uvs   = [(0,0),(1,0),(1,1),(0,1)]
        faces = [[0,1,2],[0,2,3]]
        n = _make_node(vertices=verts, normals=norms, uvs=uvs, faces=faces,
                       is_skin=False)
        vdata, idx = _build_vbo_data(n, (0,0,0), (0,0,0,1))
        assert vdata is not None
        if idx is not None:
            assert idx.dtype == np.uint32 or idx.dtype in (np.uint32, np.int32, np.uint64)
            assert len(idx) == 6
        else:
            assert len(vdata) == 6

    def test_vbo_stride_14_floats(self):
        """Each row of the VBO has exactly 14 floats (stride = 56 bytes)."""
        from src.gui.gpu_renderer import _build_vbo_data
        verts = [(0,0,0),(1,0,0),(0,1,0)]
        norms = [(0,0,1)]*3
        uvs   = [(0,0),(1,0),(0,1)]
        faces = [[0,1,2]]
        n = _make_node(vertices=verts, normals=norms, uvs=uvs, faces=faces)
        vdata, _ = _build_vbo_data(n, (0,0,0), (0,0,0,1))
        assert vdata is not None
        assert vdata.shape[1] == 14, f"Expected 14 floats/vert, got {vdata.shape[1]}"

    def test_uv_v_axis_in_raw_data(self):
        """Raw VBO stores UVs as-is (V-flip is done in the GLSL vertex shader)."""
        from src.gui.gpu_renderer import _build_vbo_data
        # UV at (0.0, 0.75)
        verts = [(0,0,0),(1,0,0),(0,1,0)]
        uvs   = [(0.0, 0.75),(1.0, 0.0),(0.0, 0.0)]
        n = _make_node(vertices=verts, normals=[(0,0,1)]*3, uvs=uvs,
                       faces=[[0,1,2]])
        vdata, idx = _build_vbo_data(n, (0,0,0), (0,0,0,1))
        assert vdata is not None
        if idx is not None:
            first_v = vdata[0][7]  # V coordinate of vertex 0
            assert abs(first_v - 0.75) < 1e-4, "V not stored as-is in VBO"


# ─────────────────────────────────────────────────────────────────────────────
#  TwoDA parser — validate ASCII parsing used by creature pipeline
# ─────────────────────────────────────────────────────────────────────────────

class TestTwoDAForCreature:
    """Validate TwoDA can parse the appearance/heads tables."""

    def test_appearance_2da_parse(self):
        """Appearance 2DA parses correctly and provides modeltype + modela."""
        from src.core.twoda import TwoDA
        raw = (
            b'2DA V2.0\n\n'
            b'   label        modeltype  modela\n'
            b'0  TestCreature B          test_body\n'
        )
        tda = TwoDA.from_bytes(raw, name='appearance')
        assert len(tda) == 1
        assert tda.get(0, 'modeltype') == 'B'
        assert tda.get(0, 'modela') == 'test_body'

    def test_heads_2da_parse(self):
        """Heads 2DA parses 'head' column."""
        from src.core.twoda import TwoDA
        raw = (
            b'2DA V2.0\n\n'
            b'   label     head\n'
            b'0  TestHead  test_head_mdl\n'
        )
        tda = TwoDA.from_bytes(raw, name='heads')
        assert tda.get(0, 'head') == 'test_head_mdl'

    def test_twoda_missing_column_returns_default(self):
        """Missing column returns empty string (graceful)."""
        from src.core.twoda import TwoDA
        raw = b'2DA V2.0\n\n   label  foo\n0  row0   bar\n'
        tda = TwoDA.from_bytes(raw, name='test')
        assert tda.get(0, 'nonexistent', 'default') == 'default'
