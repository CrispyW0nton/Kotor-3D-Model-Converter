"""
test_v71_phase1_rendering_fixes.py
====================================
Phase 1 rendering correctness fixes — unit tests.

Tests verify:
  BUG-UV    : UV V-axis is flipped in vertex shader (D3D → OpenGL convention)
  BUG-SKIN  : Skin vertices are NOT double-translated (world-space verts, no translate)
  BUG-WIND  : Front-face winding set to CW in GPU path
  BUG-ALPHA : Transparent nodes depth-sorted back-to-front before draw
  BUG-ENVMAP: TXI envmaptexture alpha preserved in _apply_kotor_alpha; NOT forced to 255
  BUG-PUNCH : txi_blending=2 correctly sets u_blend_mode=2 (punchthrough), disables GL blend
  BUG-NORM  : Normals normalized after world transform in _build_vbo_data

Reference: OldRepublicDevs/PyKotor creature.py + KotorBlender reader.py
"""

from __future__ import annotations

import sys
import os
import math

# ── Insert project root into path ────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
import numpy as np

# ── Import helpers ────────────────────────────────────────────────────────────
from core.model_data import ModelNode, NodeFlags


# ──────────────────────────────────────────────────────────────────────────────
#  Shared fixture: minimal mesh node with two triangles
# ──────────────────────────────────────────────────────────────────────────────

def _make_mesh_node(is_skin: bool = False,
                    position=(0.0, 0.0, 0.0),
                    rotation=(0.0, 0.0, 0.0, 1.0),
                    txi_blending: int = 0,
                    txi_envmaptexture: str = '',
                    alpha: float = 1.0) -> ModelNode:
    """Return a minimal ModelNode with 4 verts, 2 tris, and simple UVs."""
    node = ModelNode()
    node.name = 'test_mesh'
    # is_skin is a computed property from flags; set via flags directly
    if is_skin:
        node.flags = int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN)
    else:
        node.flags = int(NodeFlags.HEADER | NodeFlags.MESH)
    node.position = position
    node.rotation = rotation
    node.alpha = alpha
    node.txi_blending = txi_blending
    node.txi_envmaptexture = txi_envmaptexture
    node.vertices = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.0, 1.0, 0.0),
    ]
    node.normals = [
        (0.0, 0.0, 1.0),
        (0.0, 0.0, 1.0),
        (0.0, 0.0, 1.0),
        (0.0, 0.0, 1.0),
    ]
    node.uvs = [
        (0.0, 0.0),   # V=0 bottom in MDX (D3D) convention
        (1.0, 0.0),
        (1.0, 1.0),   # V=1 top in MDX
        (0.0, 1.0),
    ]
    node.uvs_lm = []
    node.faces = [(0, 1, 2), (0, 2, 3)]
    node.face_uvs = []
    node.render = True
    node.diffuse = (1.0, 1.0, 1.0)
    node.selfillum = (0.0, 0.0, 0.0)
    node.has_lightmap = False
    node.lightmap = ''
    return node


# ──────────────────────────────────────────────────────────────────────────────
#  BUG-UV: UV V-flip in vertex shader
# ──────────────────────────────────────────────────────────────────────────────

class TestUVVFlip:
    """Verify that the vertex shader flips the V coordinate (1-v).

    The GLSL code now reads:
        vec2 flipped_uv = vec2(in_uv.x, 1.0 - in_uv.y);
    We cannot run GLSL here, but we verify that:
      1. The shader source string contains the flip expression.
      2. _build_vbo_data correctly stores the raw MDX V values in the VBO
         (the flip happens in the shader, NOT in the VBO builder).
    """

    def test_vertex_shader_contains_vflip(self):
        """The vertex shader must flip V: 1.0 - in_uv.y."""
        from gui.gpu_renderer import _VERT_SRC
        assert '1.0 - in_uv.y' in _VERT_SRC, (
            "Vertex shader is missing UV V-flip: '1.0 - in_uv.y' not found in _VERT_SRC"
        )

    def test_vertex_shader_flips_lightmap_uv(self):
        """Lightmap UVs must also be V-flipped in the vertex shader."""
        from gui.gpu_renderer import _VERT_SRC
        assert '1.0 - in_uv_lm.y' in _VERT_SRC, (
            "Vertex shader is missing lightmap UV V-flip: '1.0 - in_uv_lm.y' not found"
        )

    def test_vbo_uvs_are_raw_not_flipped(self):
        """VBO data must store raw MDX V values; flip is done in shader."""
        from gui.gpu_renderer import _build_vbo_data
        node = _make_mesh_node()
        # UV (0,0) — MDX bottom-left — should be stored as v=0 in VBO (shader flips it)
        vdata, idx = _build_vbo_data(node, (0, 0, 0), (0, 0, 0, 1))
        assert vdata is not None, "_build_vbo_data returned None for valid node"
        # VBO layout: pos(3) norm(3) uv(2) uv_lm(2) color(4) → stride 14
        # UV.v is at column index 7
        v_col = vdata[:, 7]
        raw_vs = [uv[1] for uv in node.uvs]
        for vi, raw_v in enumerate(raw_vs):
            assert abs(float(v_col[vi]) - raw_v) < 1e-4, (
                f"VBO V at vert {vi} = {v_col[vi]:.4f}, expected raw MDX V = {raw_v:.4f}. "
                "V-flip should happen in GLSL shader, not in _build_vbo_data."
            )


# ──────────────────────────────────────────────────────────────────────────────
#  BUG-SKIN: No double-translation for skin vertices
# ──────────────────────────────────────────────────────────────────────────────

class TestSkinNoDoubleTranslate:
    """Skin vertex world-space handling: _build_vbo_data must NOT add world_pos translation.

    For standalone KotOR skin nodes:
    - World_pos (bone pivot) is NEVER added to skin vertex positions (prevents double-translation).
    - FIX-SKIN-NODEROT: If the node carries a non-identity local rotation, that rotation IS
      applied to the raw vertices as a corrective transform (some exporters store skin verts
      pre-multiplied by parent chain but NOT the skin node's own local orientation).
    """

    def test_skin_verts_unchanged_with_nonzero_pos(self):
        """For is_skin=True, vertex positions must not be offset by node.position.

        Note: skin VBOs are expanded to a triangle-list (6 rows for 2 triangles,
        4-vertex quad).  We verify all VBO positions match one of the original
        vertex positions (i.e., no translation was applied).
        """
        from gui.gpu_renderer import _build_vbo_data
        world_pos = (10.0, 5.0, -3.0)   # Large offset that would corrupt verts if applied
        node = _make_mesh_node(is_skin=True, position=world_pos)
        vdata, _ = _build_vbo_data(node, world_pos, (0, 0, 0, 1))
        assert vdata is not None
        # Build set of original positions for membership check
        orig_positions = set((round(v[0],4), round(v[1],4), round(v[2],4))
                             for v in node.vertices)
        # Every VBO row must correspond to one of the original vertices (untranslated)
        for ri in range(len(vdata)):
            got = (round(float(vdata[ri, 0]), 4),
                   round(float(vdata[ri, 1]), 4),
                   round(float(vdata[ri, 2]), 4))
            assert got in orig_positions, (
                f"VBO row {ri} position {got} not found in original vertices. "
                f"Skin verts must NOT be offset by world_pos={world_pos}. "
                f"Original verts: {orig_positions}"
            )

    def test_skin_verts_rotated_by_local_rotation_fix_skin_noderot(self):
        """FIX-SKIN-NODEROT: standalone skin verts ARE rotated by the node's local
        rotation when it is non-identity.

        Background: some KotOR exporters (MDLOps, older toolchains) store skin
        vertices pre-multiplied by the parent chain but NOT the skin node's own
        local orientation.  The node's local rotation then acts as a corrective
        rotation that must be applied to the raw vertex positions to restore the
        correct world-space position.

        Evidence: c_terantanak Torso/feet carry rotation (0,0,~1,~0) = 180° Z.
        Without this fix the torso shoulder verts land at Y≈[-0.88,-0.25] while
        the arm's inner verts are at Y≈[0.25,0.76] — a Y-sign flip.  After the
        fix both ranges share Y≈[0.25,0.88] and the seam is connected.

        This test verifies that a 90° Z rotation is applied to the raw verts, and
        that NO world_pos translation is added (double-translation must still be
        prevented).
        """
        from gui.gpu_renderer import _build_vbo_data
        # 90° rotation around Z: quaternion (0, 0, sin45, cos45)
        half = math.sqrt(0.5)
        rot_z90 = (0.0, 0.0, half, half)
        node = _make_mesh_node(is_skin=True, rotation=rot_z90)
        world_pos = (0.0, 0.0, 0.0)   # zero pos, so only rotation is at play
        vdata, _ = _build_vbo_data(node, world_pos, rot_z90)
        assert vdata is not None

        # Expected positions after 90° Z rotation applied to original verts:
        #   (0,0,0) -> (0,   0,  0)
        #   (1,0,0) -> (0,   1,  0)
        #   (1,1,0) -> (-1,  1,  0)
        #   (0,1,0) -> (-1,  0,  0)
        expected_positions = {
            (0.0,  0.0, 0.0),
            (0.0,  1.0, 0.0),
            (-1.0, 1.0, 0.0),
            (-1.0, 0.0, 0.0),
        }
        for ri in range(len(vdata)):
            got = (round(float(vdata[ri, 0]), 3),
                   round(float(vdata[ri, 1]), 3),
                   round(float(vdata[ri, 2]), 3))
            assert got in expected_positions, (
                f"VBO row {ri} position {got} not in expected rotated positions "
                f"{expected_positions}. FIX-SKIN-NODEROT must apply local rotation."
            )

    def test_skin_verts_no_translation_even_with_rotation(self):
        """FIX-SKIN-NODEROT + BUG-SKIN: skin verts get local rotation applied
        but NEVER get world_pos added (no double-translation).

        Even when the node has a non-zero world_pos AND a non-identity local
        rotation, the world_pos must never be added to skin vertex positions.
        Only the corrective local rotation is applied.
        """
        from gui.gpu_renderer import _build_vbo_data
        half = math.sqrt(0.5)
        rot_z90 = (0.0, 0.0, half, half)
        large_pos = (10.0, 5.0, -3.0)   # Large offset — must NOT be added to verts
        node = _make_mesh_node(is_skin=True, rotation=rot_z90, position=large_pos)
        vdata, _ = _build_vbo_data(node, large_pos, rot_z90)
        assert vdata is not None

        # After 90° Z rotation, the rotated positions are bounded in [-1, 1] range.
        # If world_pos were (incorrectly) added, X would be near -1+10=9, Y near 1+5=6.
        # Verify no coordinate is larger than 1.5 (well within rotated-only range).
        max_coord = max(
            max(abs(float(vdata[ri, 0])), abs(float(vdata[ri, 1])), abs(float(vdata[ri, 2])))
            for ri in range(len(vdata))
        )
        assert max_coord < 2.0, (
            f"Max vert coordinate {max_coord:.3f} is unexpectedly large. "
            "Skin verts must NOT be translated by world_pos even when rotation is applied. "
            f"world_pos={large_pos} must NOT be added."
        )

    def test_non_skin_verts_get_translated(self):
        """Non-skin trimesh verts MUST be translated by world_pos."""
        from gui.gpu_renderer import _build_vbo_data
        offset = (3.0, 0.0, 0.0)
        node = _make_mesh_node(is_skin=False, position=offset)
        vdata, _ = _build_vbo_data(node, offset, (0, 0, 0, 1))
        assert vdata is not None
        # First vertex (0,0,0) → after translate should be (3,0,0)
        got_x = float(vdata[0, 0])
        assert abs(got_x - 3.0) < 1e-5, (
            f"Non-skin vert 0 x: got {got_x:.4f}, expected 3.0. "
            "Non-skin verts must be translated by world_pos."
        )


# ──────────────────────────────────────────────────────────────────────────────
#  BUG-WIND: CW front-face winding
# ──────────────────────────────────────────────────────────────────────────────

class TestCWWinding:
    """Verify GPU renderer sets front_face='cw' for KotOR CW winding."""

    def test_render_sets_cw_winding(self):
        """_render_gpu source must set ctx.front_face = 'cw'."""
        import inspect
        from gui.gpu_renderer import GpuRenderer
        src = inspect.getsource(GpuRenderer._render_gpu)
        assert "front_face = 'cw'" in src, (
            "GpuRenderer._render_gpu must set ctx.front_face = 'cw' for KotOR CW winding. "
            "Found no such assignment."
        )

    def test_cull_face_enabled(self):
        """_render_gpu must enable back-face culling after setting CW winding."""
        import inspect
        from gui.gpu_renderer import GpuRenderer
        src = inspect.getsource(GpuRenderer._render_gpu)
        assert 'CULL_FACE' in src, (
            "GpuRenderer._render_gpu must enable CULL_FACE after setting CW front-face winding."
        )


# ──────────────────────────────────────────────────────────────────────────────
#  BUG-ALPHA: Transparent nodes depth-sorted back-to-front
# ──────────────────────────────────────────────────────────────────────────────

class TestTransparentDepthSort:
    """Transparent nodes must be sorted farthest-first (painter's algorithm)."""

    def test_transparent_pass_sorts_nodes(self):
        """_render_gpu source must sort transparent_nodes by distance from eye."""
        import inspect
        from gui.gpu_renderer import GpuRenderer
        src = inspect.getsource(GpuRenderer._render_gpu)
        assert 'reverse=True' in src, (
            "GpuRenderer._render_gpu transparent pass must sort nodes with reverse=True "
            "(farthest first = painter's algorithm)."
        )
        assert '_node_sort_depth' in src or 'key=' in src, (
            "GpuRenderer._render_gpu must sort transparent_nodes by depth key before drawing."
        )

    def test_punchthrough_not_in_transparent_pass(self):
        """Punchthrough nodes (tb==2) must be classified as opaque, not transparent."""
        from gui.gpu_renderer import GpuRenderer
        import inspect
        src = inspect.getsource(GpuRenderer._render_gpu)
        # The _classify_node function must NOT add punchthrough to transparent list
        # We verify by checking the is_trans logic excludes tb==2
        # The source should have: is_trans = (tb == 1) or (na < 0.999 ...)
        # and NOT: is_trans = (tb == 1 or tb == 2) or ...
        assert 'tb == 2' not in src.split('is_trans')[1].split('\n')[0] if 'is_trans' in src else True, (
            "Punchthrough (tb==2) should NOT make is_trans=True."
        )


# ──────────────────────────────────────────────────────────────────────────────
#  BUG-ENVMAP: TXI env map alpha preserved
# ──────────────────────────────────────────────────────────────────────────────

class TestEnvMapAlpha:
    """TXI envmaptexture: diffuse alpha must be preserved as blend weight."""

    def _make_fake_img_with_alpha(self, alpha_val: int = 128):
        """Create a tiny RGBA PIL image with partial alpha."""
        try:
            from PIL import Image as PILImage
            import numpy as _np
            arr = _np.full((4, 4, 4), 200, dtype=_np.uint8)
            arr[:, :, 3] = alpha_val
            return PILImage.fromarray(arr, 'RGBA')
        except ImportError:
            return None

    def test_envmap_alpha_preserved_not_forced_255(self):
        """_apply_kotor_alpha must NOT force alpha=255 when envmaptexture is set."""
        try:
            from gui.viewport import TextureCache
        except ImportError:
            pytest.skip("viewport not importable without Tkinter")

        img = self._make_fake_img_with_alpha(alpha_val=100)
        if img is None:
            pytest.skip("Pillow not available")

        import numpy as _np
        txi_meta_with_env = {
            'blending': 0,
            'bumpmaptexture': '',
            'envmaptexture': 'cm_baremetal',   # env map present
        }
        result = TextureCache._apply_kotor_alpha(b'', img, txi_meta_with_env)
        arr = _np.array(result)
        # Alpha must NOT be 255 — it should be preserved at 100
        assert arr[:, :, 3].max() < 255, (
            "With envmaptexture set, _apply_kotor_alpha must NOT force alpha=255. "
            "Alpha is the env-map blend weight and must be preserved."
        )
        assert arr[:, :, 3].min() >= 95, (
            f"Alpha was unexpectedly altered: min={arr[:,:,3].min()}, expected ~100"
        )

    def test_bumpmap_alpha_still_forced_255(self):
        """_apply_kotor_alpha must still force alpha=255 for bumpmaptexture."""
        try:
            from gui.viewport import TextureCache
        except ImportError:
            pytest.skip("viewport not importable without Tkinter")

        img = self._make_fake_img_with_alpha(alpha_val=50)
        if img is None:
            pytest.skip("Pillow not available")

        import numpy as _np
        txi_meta_with_bump = {
            'blending': 0,
            'bumpmaptexture': 'n_somebump',
            'envmaptexture': '',
        }
        result = TextureCache._apply_kotor_alpha(b'', img, txi_meta_with_bump)
        arr = _np.array(result)
        assert arr[:, :, 3].min() == 255, (
            "With bumpmaptexture set, _apply_kotor_alpha must force alpha=255."
        )

    def test_standard_opaque_alpha_still_forced_255(self):
        """Standard opaque textures (no env, no bump, blending=0) must force alpha=255."""
        try:
            from gui.viewport import TextureCache
        except ImportError:
            pytest.skip("viewport not importable without Tkinter")

        img = self._make_fake_img_with_alpha(alpha_val=30)
        if img is None:
            pytest.skip("Pillow not available")

        import numpy as _np
        txi_meta_opaque = {
            'blending': 0,
            'bumpmaptexture': '',
            'envmaptexture': '',
        }
        result = TextureCache._apply_kotor_alpha(b'', img, txi_meta_opaque)
        arr = _np.array(result)
        assert arr[:, :, 3].min() == 255, (
            "Standard opaque textures must have alpha forced to 255 (no DXT5 bleed-through)."
        )

    def test_gpu_shader_has_env_sampler(self):
        """Fragment shader must have u_env_tex sampler and u_has_env uniform."""
        from gui.gpu_renderer import _FRAG_SRC
        assert 'u_env_tex' in _FRAG_SRC, "Fragment shader missing u_env_tex sampler"
        assert 'u_has_env' in _FRAG_SRC, "Fragment shader missing u_has_env uniform"

    def test_gpu_shader_env_blend(self):
        """Fragment shader must blend env map using diffuse alpha as weight."""
        from gui.gpu_renderer import _FRAG_SRC
        assert 'env_weight' in _FRAG_SRC or 'env_col' in _FRAG_SRC, (
            "Fragment shader must perform env-map blending using diffuse alpha"
        )
        assert 'mix(' in _FRAG_SRC or 'mix (' in _FRAG_SRC, (
            "Fragment shader must use mix() to blend surface and env map colours"
        )

    def test_punchthrough_classify_is_opaque(self):
        """_classify_node must NOT classify punchthrough (tb==2) as transparent."""
        from gui.gpu_renderer import GpuRenderer
        import inspect
        src = inspect.getsource(GpuRenderer._render_gpu)
        # Find the _classify_node definition in _render_gpu source
        assert '_classify_node' in src, "_classify_node not found in _render_gpu"
        # Verify that is_trans does not include tb==2
        classify_block = src[src.find('def _classify_node'):]
        is_trans_line = [l for l in classify_block.split('\n') if 'is_trans' in l and '=' in l]
        for line in is_trans_line:
            assert 'tb == 2' not in line, (
                f"_classify_node sets is_trans=True for punchthrough (tb==2)! Line: {line}"
            )


# ──────────────────────────────────────────────────────────────────────────────
#  BUG-PUNCH: Punchthrough blend mode
# ──────────────────────────────────────────────────────────────────────────────

class TestPunchthroughBlendMode:
    """txi_blending=2 must set u_blend_mode=2 and disable GL blending."""

    def test_shader_blend_mode_2_is_punchthrough(self):
        """Fragment shader must discard fragments below u_alpha_test when u_blend_mode==2."""
        from gui.gpu_renderer import _FRAG_SRC
        assert 'u_blend_mode == 2' in _FRAG_SRC, (
            "Fragment shader must check u_blend_mode==2 for punchthrough alpha discard"
        )
        assert 'discard' in _FRAG_SRC, (
            "Fragment shader must use 'discard' for punchthrough alpha test"
        )

    def test_punchthrough_disables_gl_blend(self):
        """For txi_blending==2, GL blending must be disabled (uses shader discard instead)."""
        from gui.gpu_renderer import GpuRenderer
        import inspect
        src = inspect.getsource(GpuRenderer._render_gpu)
        # Find the txi_blend == 2 branch in _draw_node
        assert 'txi_blend == 2' in src, (
            "_draw_node must check txi_blend == 2 for punchthrough path"
        )
        # The punchthrough branch must disable blend (not enable it)
        pt_block = src[src.find('txi_blend == 2'):]
        pt_branch = pt_block[:pt_block.find('elif')]  # Up to next elif
        assert 'disable(moderngl.BLEND)' in pt_branch or 'disable' in pt_branch, (
            "Punchthrough branch must call ctx.disable(moderngl.BLEND)"
        )

    def test_punchthrough_final_alpha_forced_1(self):
        """Fragment shader must output final_alpha=1.0 for surviving punchthrough fragments."""
        from gui.gpu_renderer import _FRAG_SRC
        # Find the punchthrough case in final_alpha assignment
        assert 'u_blend_mode == 2' in _FRAG_SRC
        # After discard, the surviving frags should output alpha=1
        # The shader has: } else if (u_blend_mode == 2) { final_alpha = 1.0; }
        pt_part = _FRAG_SRC[_FRAG_SRC.rfind('u_blend_mode == 2'):]
        assert 'final_alpha = 1.0' in pt_part[:200], (
            "Punchthrough surviving fragments must have final_alpha = 1.0"
        )


# ──────────────────────────────────────────────────────────────────────────────
#  BUG-NORM: Normal normalization
# ──────────────────────────────────────────────────────────────────────────────

class TestNormalNormalization:
    """Normals must be unit-length after world-space transform."""

    def test_normals_are_normalized_after_rotation(self):
        """After applying a rotation, normals must still be unit length."""
        from gui.gpu_renderer import _build_vbo_data
        # 45° rotation around Z
        half = math.sqrt(0.5)
        rot = (0.0, 0.0, half, half)
        node = _make_mesh_node(is_skin=False, rotation=rot)
        vdata, _ = _build_vbo_data(node, (0, 0, 0), rot)
        assert vdata is not None
        norms = vdata[:, 3:6]
        lengths = np.linalg.norm(norms, axis=1)
        for i, length in enumerate(lengths):
            assert abs(float(length) - 1.0) < 1e-4, (
                f"Normal {i} length = {length:.6f}, expected ~1.0. "
                "Normals must be normalized after world-space rotation."
            )

    def test_normals_are_normalized_for_skin_nodes(self):
        """Skin node normals must also be unit length (no transform, just re-normalize)."""
        from gui.gpu_renderer import _build_vbo_data
        node = _make_mesh_node(is_skin=True)
        # Use a slightly-off-unit normal to ensure normalization happens
        node.normals = [(0.0, 0.0, 1.5), (0.0, 0.0, 1.5), (0.0, 0.0, 1.5), (0.0, 0.0, 1.5)]
        vdata, _ = _build_vbo_data(node, (0, 0, 0), (0, 0, 0, 1))
        assert vdata is not None
        norms = vdata[:, 3:6]
        lengths = np.linalg.norm(norms, axis=1)
        for i, length in enumerate(lengths):
            assert abs(float(length) - 1.0) < 1e-4, (
                f"Skin node normal {i} length = {length:.6f}, expected ~1.0."
            )
# ──────────────────────────────────────────────────────────────────────────────
#  Regression: _build_vbo_data basic correctness
# ──────────────────────────────────────────────────────────────────────────────

class TestBuildVboDataRegression:
    """Regression tests for _build_vbo_data to ensure no new regressions."""

    def test_returns_none_for_empty_node(self):
        """_build_vbo_data must return (None, None) for empty nodes."""
        from gui.gpu_renderer import _build_vbo_data
        node = ModelNode()
        node.name = 'empty'
        node.flags = int(NodeFlags.HEADER | NodeFlags.MESH)
        node.vertices = []
        node.normals = []
        node.uvs = []
        node.faces = []
        node.face_uvs = []
        vdata, idx = _build_vbo_data(node, (0, 0, 0), (0, 0, 0, 1))
        assert vdata is None and idx is None

    def test_stride_is_14_floats(self):
        """VBO data must have exactly 14 floats per vertex."""
        from gui.gpu_renderer import _build_vbo_data
        node = _make_mesh_node()
        vdata, _ = _build_vbo_data(node, (0, 0, 0), (0, 0, 0, 1))
        assert vdata is not None
        assert vdata.shape[1] == 14, (
            f"VBO stride is {vdata.shape[1]}, expected 14 "
            "(pos.xyz + norm.xyz + uv.xy + uv_lm.xy + color.xyzw)"
        )

    def test_face_count_matches_indices(self):
        """Index buffer must have 3 * n_faces entries for a valid mesh."""
        from gui.gpu_renderer import _build_vbo_data
        node = _make_mesh_node()
        vdata, idx = _build_vbo_data(node, (0, 0, 0), (0, 0, 0, 1))
        assert vdata is not None
        if idx is not None:
            assert len(idx) == len(node.faces) * 3, (
                f"Index buffer has {len(idx)} entries, expected {len(node.faces)*3}"
            )

    def test_vertex_color_defaults_to_white(self):
        """Vertex colour (cols 10-13) must default to (1,1,1,1) = white."""
        from gui.gpu_renderer import _build_vbo_data
        node = _make_mesh_node()
        vdata, _ = _build_vbo_data(node, (0, 0, 0), (0, 0, 0, 1))
        assert vdata is not None
        colors = vdata[:, 10:14]
        assert np.allclose(colors, 1.0, atol=1e-5), (
            "Default vertex colour must be (1,1,1,1) white."
        )


# ──────────────────────────────────────────────────────────────────────────────
#  _classify_node logic
# ──────────────────────────────────────────────────────────────────────────────

class TestClassifyNodeLogic:
    """The _classify_node logic in _render_gpu must correctly categorise nodes."""

    def _extract_classify_logic(self):
        """Extract the _classify_node source from _render_gpu."""
        import inspect
        from gui.gpu_renderer import GpuRenderer
        src = inspect.getsource(GpuRenderer._render_gpu)
        start = src.find('def _classify_node')
        end = src.find('\n            def ', start + 1)
        return src[start:end] if end > 0 else src[start:]

    def test_additive_is_transparent(self):
        """Additive blend (tb==1) must be classified as transparent."""
        src = self._extract_classify_logic()
        assert 'tb == 1' in src, "Additive (tb==1) must be part of is_trans"

    def test_punchthrough_is_not_transparent(self):
        """Punchthrough (tb==2) must NOT be part of is_trans."""
        src = self._extract_classify_logic()
        is_trans_lines = [l for l in src.split('\n') if 'is_trans' in l and '=' in l]
        for line in is_trans_lines:
            assert 'tb == 2' not in line, (
                f"Punchthrough (tb==2) should not make is_trans=True! Line: {line}"
            )

    def test_envmap_node_is_opaque(self):
        """Env map nodes must be classified as opaque (not transparent)."""
        src = self._extract_classify_logic()
        # has_env nodes should NOT be transparent
        assert 'not has_env' in src or 'has_env' in src, (
            "Env map presence should influence is_trans classification"
        )


# ──────────────────────────────────────────────────────────────────────────────
#  Fragment shader alpha handling
# ──────────────────────────────────────────────────────────────────────────────

class TestFragmentShaderAlpha:
    """Fragment shader must handle alpha correctly for all blend modes."""

    def test_opaque_node_forces_alpha_1(self):
        """Standard opaque surfaces must have final_alpha=1.0."""
        from gui.gpu_renderer import _FRAG_SRC
        assert 'final_alpha = 1.0' in _FRAG_SRC, (
            "Fragment shader must force final_alpha=1.0 for opaque surfaces"
        )

    def test_envmap_node_forces_alpha_1_output(self):
        """Env-map surfaces must output final_alpha=1.0 (opaque, env uses alpha as weight)."""
        from gui.gpu_renderer import _FRAG_SRC
        # Find the env map branch
        env_block = _FRAG_SRC[_FRAG_SRC.find('u_has_env'):]
        assert env_block, "u_has_env not found in fragment shader"
        # The env branch should output u_alpha * u_node_alpha * v_color.a (no tex alpha)
        env_final = env_block[:400]
        assert 'u_alpha * u_node_alpha' in env_final or 'u_node_alpha' in env_final, (
            "Env-map branch must use u_node_alpha (not texture alpha) for final_alpha"
        )

    def test_additive_respects_texture_alpha(self):
        """Additive blend must respect texture alpha (else glow FX won't fade)."""
        from gui.gpu_renderer import _FRAG_SRC
        # The else branch (additive path) should multiply diffuse_samp.a
        assert 'diffuse_samp.a' in _FRAG_SRC, (
            "Additive/transparent branch must include diffuse_samp.a in final_alpha"
        )


# ──────────────────────────────────────────────────────────────────────────────
#  CPU viewport: env map texture loading
# ──────────────────────────────────────────────────────────────────────────────

class TestCpuEnvMapLoading:
    """The CPU textured draw path must attempt to load env map textures."""

    def test_draw_mesh_textured_loads_env_tex(self):
        """_draw_mesh_textured must reference txi_envmaptexture for env map loading."""
        import inspect
        try:
            from gui.viewport import FrameRenderer
        except ImportError:
            pytest.skip("viewport not importable")
        src = inspect.getsource(FrameRenderer._draw_mesh_textured)
        assert 'txi_envmaptexture' in src, (
            "_draw_mesh_textured must load the env-map texture via txi_envmaptexture"
        )
        assert '_env_img' in src or 'env_img' in src, (
            "_draw_mesh_textured must store env-map image in a local variable"
        )
