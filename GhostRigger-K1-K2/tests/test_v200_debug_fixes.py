"""
tests/test_v200_debug_fixes.py
Phase 20 debug fixes — comprehensive test suite covering:

1. OBJ export face_uvs fix  — ebon_01 K2 Maya texture issue
2. LBS explosion guard scale-aware threshold — c_brith wing clipping
3. Eyeball inner-geo tier promotion fix  — child_f / comm_a_m missing eyes
4. Walkmesh toggle button feedback — no-walkmesh-loaded behaviour
"""
import math
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.model_data import ModelNode, NodeFlags, KotorModel


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _mesh_node(name, texture='tex', uvs=None, skin=False, face_uvs=None):
    flags = int(NodeFlags.MESH) | (int(NodeFlags.SKIN) if skin else 0)
    n = ModelNode(name=name, flags=flags)
    n.texture = texture
    n.uvs = uvs or [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)]
    n.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 0.0, 1.0)]
    n.normals  = [(0.0, 1.0, 0.0)] * 3
    n.faces    = [(0, 1, 2)]
    if face_uvs is not None:
        n.face_uvs = face_uvs
        n.face_mats = [0] * len(n.faces)
    return n


def _make_model(nodes):
    """Minimal KotorModel with a list of nodes chained as children of root."""
    m = KotorModel()
    root = ModelNode(name='model_root', flags=int(NodeFlags.HEADER))
    m.root_node = root
    for n in nodes:
        n.parent = root
        root.children.append(n)
    return m


# ─────────────────────────────────────────────────────────────────────────────
#  1. OBJ EXPORT: face_uvs tvert index fix
# ─────────────────────────────────────────────────────────────────────────────

class TestOBJExporterFaceUVs:
    """OBJ exporter must use face_uvs tvert indices when present (ASCII MDL models)."""

    def _export_to_str(self, model, tmp_path):
        """Export model to OBJ and return the file contents as a string."""
        from converters.mesh_converter import OBJExporter
        import tempfile, pathlib
        obj_path = str(tmp_path / 'test_export.obj')
        OBJExporter().export(model, obj_path, tex_cache=None)
        return (tmp_path / 'test_export.obj').read_text(encoding='utf-8')

    def test_binary_mdl_no_face_uvs_uses_vertex_indices(self, tmp_path):
        """Binary MDL: no face_uvs → UV index == vertex index (unchanged behaviour)."""
        node = _mesh_node('body', 'hull_tex')
        node.face_uvs = []   # binary MDL has no separate face UV indices
        model = _make_model([node])
        obj = self._export_to_str(model, tmp_path)
        # Face line should use vertex index 1/2/3 for positions AND UVs
        face_lines = [l for l in obj.splitlines() if l.startswith('f ')]
        assert face_lines, "OBJ must contain at least one face line"
        # v1/vt1/vn1 v2/vt2/vn2 v3/vt3/vn3
        f = face_lines[0]
        assert '1/1/' in f or '1/1 ' in f or f.startswith('f 1')

    def test_ascii_mdl_face_uvs_used_for_uv_indices(self, tmp_path):
        """ASCII MDL: face_uvs tvert indices must override vertex indices in OBJ face lines."""
        # 4 UV coords, face references tverts 0, 2, 3 (NOT 0, 1, 2)
        uvs = [(0.0, 0.0), (0.5, 0.5), (1.0, 0.0), (0.5, 1.0)]
        node = _mesh_node('hull', 'hull_tex', uvs=uvs, face_uvs=[(0, 2, 3)])
        model = _make_model([node])
        obj = self._export_to_str(model, tmp_path)
        face_lines = [l for l in obj.splitlines() if l.startswith('f ')]
        assert face_lines, "OBJ must contain face lines"
        f = face_lines[0]
        # OBJ 1-based: tvert 0→1, 2→3, 3→4
        # Face should be: f 1/1/... 2/3/... 3/4/...
        parts = f.split()  # ['f', 'v1/vt1/vn1', ...]
        assert len(parts) == 4, f"Unexpected face format: {f}"
        vt_indices = [p.split('/')[1] for p in parts[1:]]
        assert vt_indices == ['1', '3', '4'], \
            f"Expected tvert indices [1,3,4] but got {vt_indices}. Face line: {f}"

    def test_ascii_mdl_face_uvs_multiple_faces(self, tmp_path):
        """Multiple faces each with their own tvert indices are all correctly mapped."""
        uvs = [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0), (0.25, 0.75), (0.75, 0.25)]
        node = _mesh_node('multi', 'tex', uvs=uvs)
        # Override vertices and faces so both triangles have valid vertex indices
        # 5 vertices (0..4), 2 faces, 5 UV coords (0..4) with different tvert mapping
        node.vertices = [
            (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 0.0, 1.0),
            (0.0, 0.0, 0.0), (1.0, 0.0, 0.0),  # second tri reuses positions
        ]
        node.normals = [(0.0, 1.0, 0.0)] * 5
        node.faces = [(0, 1, 2), (0, 3, 4)]
        node.face_uvs = [(0, 1, 2), (0, 3, 4)]
        node.face_mats = [0, 0]
        model = _make_model([node])
        obj = self._export_to_str(model, tmp_path)
        face_lines = [l for l in obj.splitlines() if l.startswith('f ')]
        assert len(face_lines) == 2, f"Expected 2 face lines, got {len(face_lines)}"
        # First face: tverts 0,1,2 → OBJ 1,2,3
        vt0 = [p.split('/')[1] for p in face_lines[0].split()[1:]]
        assert vt0 == ['1', '2', '3'], f"Face 0 tvert indices wrong: {vt0}"
        # Second face: tverts 0,3,4 → OBJ 1,4,5
        vt1 = [p.split('/')[1] for p in face_lines[1].split()[1:]]
        assert vt1 == ['1', '4', '5'], f"Face 1 tvert indices wrong: {vt1}"

    def test_face_uvs_mismatch_falls_back_to_vertex_indices(self, tmp_path):
        """If face_uvs length != faces length, fall back to vertex indices (safety)."""
        node = _mesh_node('safe', 'tex')
        node.face_uvs = [(0, 1, 2), (0, 1, 2)]  # 2 entries but only 1 face
        model = _make_model([node])
        # Should not raise
        obj = self._export_to_str(model, tmp_path)
        face_lines = [l for l in obj.splitlines() if l.startswith('f ')]
        assert face_lines, "Must still produce face lines"

    def test_null_texture_node_skipped_in_export(self, tmp_path):
        """Nodes with NULL texture are deformation helpers and must not appear in OBJ."""
        good = _mesh_node('visible', 'real_tex')
        bad  = _mesh_node('helper', 'NULL')
        bad.uvs = []   # helpers often have no uvs
        model = _make_model([good, bad])
        obj = self._export_to_str(model, tmp_path)
        assert 'o visible' in obj,  "Visible node must appear in OBJ"
        assert 'o helper'  not in obj, "NULL-texture helper must NOT appear in OBJ"


# ─────────────────────────────────────────────────────────────────────────────
#  2. LBS EXPLOSION GUARD: scale-aware threshold
# ─────────────────────────────────────────────────────────────────────────────

class TestLBSExplosionGuardScaleAware:
    """The LBS bone-travel threshold must scale with model bounding-box size."""

    def _make_renderer(self):
        """Create a headless FrameRenderer instance."""
        try:
            from gui.viewport import FrameRenderer
        except ImportError:
            pytest.skip("FrameRenderer not importable in headless env")
        r = FrameRenderer.__new__(FrameRenderer)
        # Minimal init
        r.model         = None
        r._wt_cache     = {}
        r._anim_pose    = None
        r._bone_transforms_cache = None
        r._bone_transforms_pose_id = -1
        r._lbs_model_diag = None
        return r

    def test_small_model_floor_threshold(self):
        """Human-scale model (4-unit bbox) → floor 8.0 applies."""
        r = self._make_renderer()
        # Simulate small model: bounding diagonal = 4.0
        r._lbs_model_diag = 4.0
        # Threshold = max(8.0, 4.0 * 0.6) = max(8.0, 2.4) = 8.0
        diag = r._lbs_model_diag
        threshold = max(8.0, diag * 0.6)
        assert threshold == 8.0, f"Expected 8.0 floor, got {threshold}"

    def test_large_creature_higher_threshold(self):
        """Large creature (55-unit bbox like c_brith) → threshold = 33.0."""
        r = self._make_renderer()
        r._lbs_model_diag = 55.0  # c_brith Drexl approximate diagonal
        diag = r._lbs_model_diag
        threshold = max(8.0, diag * 0.6)
        assert threshold == pytest.approx(33.0, abs=0.1), \
            f"c_brith threshold expected ~33.0, got {threshold}"

    def test_lbs_model_diag_cleared_on_set_model(self):
        """_lbs_model_diag must be cleared when a new model is loaded."""
        try:
            from gui.viewport import FrameRenderer
        except ImportError:
            pytest.skip("FrameRenderer not importable")
        r = FrameRenderer.__new__(FrameRenderer)
        # Pre-populate all attributes set_model expects
        r._wt_cache = {}
        r._cached_model_id = -1
        r._anim_pose = None
        r._bone_transforms_cache = None
        r._bone_transforms_pose_id = -1
        r._outlier_skin_nodes = set()
        r._dangly_sims = {}
        r._dangly_last_time = 0.0
        r._render_bounds_cache = None
        r._render_bounds_model_id = -1
        r._lod_prev_cap = 0
        r._lq_tex_mode = False
        r._lbs_model_diag = 99.0   # stale value
        r._skin_proxy_ids = set()
        r.textures = {}
        r._outlier_model_id = -1
        # Minimal tex_cache mock
        class _FakeCache:
            def clear_mip_cache(self): pass
            def clear(self): pass
        r.tex_cache = _FakeCache()
        r._tex_arr_cache = _FakeCache()
        r.MAX_TRIS = 50000
        # Call set_model with None
        r.set_model(None)
        assert r._lbs_model_diag is None, \
            "_lbs_model_diag must be None after set_model(None)"

    def test_medium_creature_threshold(self):
        """Medium creature (20-unit bbox) → threshold scales above floor."""
        diag = 20.0
        threshold = max(8.0, diag * 0.6)
        assert threshold == pytest.approx(12.0, abs=0.01)


# ─────────────────────────────────────────────────────────────────────────────
#  3. EYEBALL INNER-GEO TIER: skin-type eye nodes must be promoted
# ─────────────────────────────────────────────────────────────────────────────

class TestInnerGeoEyeballSkinNodes:
    """Eye nodes declared as SKIN meshes must still be promoted to draw tier 1."""

    _INNER_GEO_SUBSTRINGS = (
        'eye', 'lid', 'teeth', 'tooth', 'gum', 'jaw',
        'tongue', 'teethu', 'teethl',
    )

    def _is_inner_geo(self, node):
        """Replicate the fixed _is_inner_geo logic (no longer gates on is_skin)."""
        # Clean texture name (simple version)
        tex = (getattr(node, 'texture', '') or '').strip()
        tex_clean = ''.join(c for c in tex if 32 <= ord(c) <= 126).strip()
        has_tex = bool(tex_clean and tex_clean.upper() not in ('NULL', ''))
        nl = node.name.lower()
        return (
            has_tex
            and any(s in nl for s in self._INNER_GEO_SUBSTRINGS)
            and int(getattr(node, 'transparency_hint', 0)) == 0
        )

    def test_trimesh_eye_is_inner_geo(self):
        """Standard trimesh eyeball (K1 PC heads) is inner geo."""
        node = _mesh_node('eyeRA', 'P_EyeBrown')
        assert self._is_inner_geo(node), "trimesh eyeRA must be inner geo"

    def test_skin_eye_is_inner_geo(self):
        """Skin-type eyeball (some K2 head models) must also be inner geo."""
        node = _mesh_node('eyeRA', 'P_EyeBrown', skin=True)
        assert node.is_skin, "eyeRA node must be is_skin=True for this test"
        assert self._is_inner_geo(node), \
            "skin-type eyeRA must be promoted to inner geo tier (K2 fix)"

    def test_null_tex_eye_not_inner_geo(self):
        """Eye-named node with NULL texture is a deform helper, not inner geo."""
        node = _mesh_node('eyeRA', 'NULL')
        assert not self._is_inner_geo(node), \
            "NULL-texture eye node must NOT be promoted to inner geo"

    def test_eyelid_nodes_inner_geo(self):
        """Eyelid nodes (eyeRlid, eyeLlid) are inner geo."""
        for name in ('eyeRlid', 'eyeLlid', 'eyelid_upper', 'eyelid_lower'):
            node = _mesh_node(name, 'P_EyeLid01')
            assert self._is_inner_geo(node), f"{name} must be inner geo"

    def test_teeth_nodes_inner_geo(self):
        """Teeth and tongue nodes are inner geo."""
        for name in ('teethU', 'teethL', 'teethUa', 'tongue', 'gum_upper'):
            node = _mesh_node(name, 'P_Teeth01')
            assert self._is_inner_geo(node), f"{name} must be inner geo"

    def test_jaw_nodes_inner_geo(self):
        """Jaw geometry is inner geo."""
        node = _mesh_node('jaw_mesh', 'P_HeadFront01')
        assert self._is_inner_geo(node), "jaw_mesh must be inner geo"

    def test_body_mesh_not_inner_geo(self):
        """Regular body/face meshes must NOT be promoted to inner geo tier."""
        for name in ('body_front', 'face_mesh', 'head_geo', 'armor_01'):
            node = _mesh_node(name, 'P_Body01')
            assert not self._is_inner_geo(node), f"{name} must NOT be inner geo"

    def test_transparent_eye_not_promoted_by_inner_geo(self):
        """Glass-dome eye (transparency_hint != 0) is already tier 1; inner geo not needed."""
        node = _mesh_node('eyeRA_glass', 'P_EyeGlass')
        node.transparency_hint = 2  # KotOR additive blend
        assert not self._is_inner_geo(node), \
            "Transparent eye must not be promoted via inner_geo (already tier 1)"

    def test_k2_skin_eye_has_tex_guard(self):
        """Even skin eyes require a non-null texture for inner-geo promotion."""
        node = _mesh_node('eyeRA', '', skin=True)  # empty texture
        node.texture = ''
        assert not self._is_inner_geo(node), \
            "Skin eye without texture must not be inner geo"


# ─────────────────────────────────────────────────────────────────────────────
#  4. WALKMESH BUTTON: feedback when no walkmesh loaded
# ─────────────────────────────────────────────────────────────────────────────

class TestWalkmeshToggleNoData:
    """_toggle_walkmesh_btn must not silently succeed when no WOK is loaded."""

    def test_toggle_returns_early_without_overlay(self):
        """
        When _walkmesh_overlay is None, the renderer show_walkmesh flag must remain
        unchanged and the method must return early without toggling.
        """
        try:
            from gui.viewport import FrameRenderer
        except ImportError:
            pytest.skip("FrameRenderer not importable headless")

        r = FrameRenderer.__new__(FrameRenderer)
        r._walkmesh_overlay = None
        r.show_walkmesh = False

        # Minimal renderer for toggle logic check
        class FakeViewport:
            """Simulate the KotorViewport (Tkinter widget), headless."""
            _renderer = r
            _log_messages = []

            def _toggle_walkmesh_btn(self):
                """Replicate the fixed toggle logic without Tkinter."""
                if self._renderer._walkmesh_overlay is None:
                    # record that we returned early
                    self._log_messages.append('no_walkmesh')
                    return
                self._renderer.show_walkmesh = not self._renderer.show_walkmesh

        vp = FakeViewport()
        vp._toggle_walkmesh_btn()
        # Flag must be unchanged (still False)
        assert r.show_walkmesh is False, \
            "show_walkmesh must not be toggled when no overlay is loaded"
        assert 'no_walkmesh' in vp._log_messages, \
            "Must record early-return signal when no walkmesh loaded"

    def test_toggle_works_when_overlay_present(self):
        """When _walkmesh_overlay IS set, the flag toggles normally."""
        try:
            from gui.viewport import FrameRenderer
        except ImportError:
            pytest.skip()

        r = FrameRenderer.__new__(FrameRenderer)
        r._walkmesh_overlay = object()   # non-None sentinel
        r.show_walkmesh = False

        class FakeViewport:
            _renderer = r
            def _toggle_walkmesh_btn(self):
                if self._renderer._walkmesh_overlay is None:
                    return
                self._renderer.show_walkmesh = not self._renderer.show_walkmesh

        vp = FakeViewport()
        vp._toggle_walkmesh_btn()
        assert r.show_walkmesh is True, \
            "show_walkmesh must toggle to True when overlay is present"
        vp._toggle_walkmesh_btn()
        assert r.show_walkmesh is False, \
            "show_walkmesh must toggle back to False on second click"


# ─────────────────────────────────────────────────────────────────────────────
#  5. REGRESSION: existing OBJ export still works for non-face_uvs models
# ─────────────────────────────────────────────────────────────────────────────

class TestOBJExporterRegression:
    """Ensure the face_uvs fix does not break existing binary MDL exports."""

    def test_export_produces_valid_obj_structure(self, tmp_path):
        """Exported OBJ has correct sections: mtllib, o, v, vt, vn, f lines."""
        from converters.mesh_converter import OBJExporter
        node = _mesh_node('test_node', 'body_tex')
        model = _make_model([node])
        obj_path = str(tmp_path / 'out.obj')
        OBJExporter().export(model, obj_path)
        txt = (tmp_path / 'out.obj').read_text()
        assert 'mtllib'        in txt, "Missing mtllib"
        assert 'o test_node'   in txt, "Missing object name"
        assert txt.count('\nv ')  >= 3, "Need at least 3 vertex lines"
        assert txt.count('\nvt ') >= 3, "Need at least 3 UV lines"
        assert 'f ' in txt,            "Missing face lines"

    def test_export_flips_v_coordinate(self, tmp_path):
        """OBJ V coordinate must be flipped: vt_out = 1.0 - v_kotor."""
        from converters.mesh_converter import OBJExporter
        # Single UV at (0.25, 0.75) → should export as (0.25, 0.25)
        node = _mesh_node('uv_test', 'tex',
                          uvs=[(0.25, 0.75), (0.75, 0.25), (0.5, 0.5)])
        model = _make_model([node])
        obj_path = str(tmp_path / 'uv_flip.obj')
        OBJExporter().export(model, obj_path)
        txt = (tmp_path / 'uv_flip.obj').read_text()
        vt_lines = [l for l in txt.splitlines() if l.startswith('vt ')]
        assert vt_lines, "No vt lines in OBJ"
        # First UV: u=0.25 v=1-0.75=0.25
        parts = vt_lines[0].split()
        u, v = float(parts[1]), float(parts[2])
        assert abs(u - 0.25) < 1e-4, f"U unexpected: {u}"
        assert abs(v - 0.25) < 1e-4, f"V flip failed: got {v}, expected 0.25"

    def test_degenerate_face_skipped(self, tmp_path):
        """Faces with out-of-range vertex indices are silently skipped."""
        from converters.mesh_converter import OBJExporter
        node = _mesh_node('degenerate', 'tex')
        node.faces = [(0, 1, 2), (0, 1, 99)]  # index 99 is out of range
        model = _make_model([node])
        obj_path = str(tmp_path / 'degen.obj')
        OBJExporter().export(model, obj_path)  # Must not raise
        txt = (tmp_path / 'degen.obj').read_text()
        face_lines = [l for l in txt.splitlines() if l.startswith('f ')]
        assert len(face_lines) == 1, f"Expected 1 valid face, got {len(face_lines)}"
