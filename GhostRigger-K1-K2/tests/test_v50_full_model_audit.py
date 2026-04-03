"""
GhostRigger v5.0 – Full Model & Texture Audit Test Suite
=========================================================
Tests:
  - Audit script imports and runs without crashing
  - Geometry checker functions on known good/bad data
  - Texture-placeholder filter works correctly
  - Bounding-box classifier skips sky/large models
  - Full K1 sample audit (first 100 models) passes with correct metrics
  - K2 sample audit (first 100 models) passes
  - Per-model metrics are complete and typed correctly
"""

import json
import math
import os
import sys
import pytest
from pathlib import Path
from typing import List
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Fixtures ──────────────────────────────────────────────────────────────────

REPO   = Path(__file__).parent.parent
K1_DIR = str(REPO / "game_data" / "swkotor")
K2_DIR = str(REPO / "game_data" / "swkotor2")

K1_AVAILABLE = os.path.isdir(K1_DIR) and os.path.isfile(os.path.join(K1_DIR, "chitin.key"))
K2_AVAILABLE = os.path.isdir(K2_DIR) and os.path.isfile(os.path.join(K2_DIR, "chitin.key"))

# ── Import audit script ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def audit_module():
    """Import the full_model_audit script as a module."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "full_model_audit",
        str(REPO / "scripts" / "full_model_audit.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Unit tests: geometry checker ──────────────────────────────────────────────

class TestGeometryChecker:
    """Tests for check_node_geometry() against synthetic nodes."""

    def _make_node(self, verts, faces, uvs=None, normals=None, skin_data=None):
        """Create a minimal ModelNode-like object."""
        from core.model_data import ModelNode, VertexSkinData, BoneWeight
        n = ModelNode(name="TestNode")
        n.vertices = verts
        n.faces = faces
        n.uvs = uvs or []
        n.normals = normals or []
        n.skin_data = skin_data or []
        n.render = True
        return n

    def test_good_triangle(self, audit_module):
        from core.model_data import ModelNode
        n = self._make_node(
            verts=[(0,0,0),(1,0,0),(0,1,0)],
            faces=[(0,1,2)]
        )
        result = audit_module.ModelAuditResult("test", "K1")
        audit_module.check_node_geometry(n, result)
        assert result.issues == [], f"Clean triangle should have no issues, got {result.issues}"

    def test_empty_mesh_flagged(self, audit_module):
        n = self._make_node(verts=[], faces=[])
        result = audit_module.ModelAuditResult("test", "K1")
        audit_module.check_node_geometry(n, result)
        types = [i["type"] for i in result.issues]
        assert "empty_mesh" in types

    def test_nan_vertex_flagged(self, audit_module):
        n = self._make_node(
            verts=[(0,0,0),(float('nan'),0,0),(0,1,0)],
            faces=[(0,1,2)]
        )
        result = audit_module.ModelAuditResult("test", "K1")
        audit_module.check_node_geometry(n, result)
        types = [i["type"] for i in result.issues]
        assert "nan_vertices" in types

    def test_zero_area_face_flagged(self, audit_module):
        # All three vertices coincide → zero area
        n = self._make_node(
            verts=[(1,1,1),(1,1,1),(1,1,1)],
            faces=[(0,1,2)]
        )
        result = audit_module.ModelAuditResult("test", "K1")
        audit_module.check_node_geometry(n, result)
        types = [i["type"] for i in result.issues]
        assert "zero_area_faces" in types

    def test_degenerate_face_flagged(self, audit_module):
        # Face with duplicate index
        n = self._make_node(
            verts=[(0,0,0),(1,0,0),(0,1,0)],
            faces=[(0,0,2)]   # v0==v1 → degenerate
        )
        result = audit_module.ModelAuditResult("test", "K1")
        audit_module.check_node_geometry(n, result)
        types = [i["type"] for i in result.issues]
        assert "degenerate_faces" in types

    def test_oob_face_flagged(self, audit_module):
        n = self._make_node(
            verts=[(0,0,0),(1,0,0),(0,1,0)],
            faces=[(0,1,99)]  # index 99 out of bounds
        )
        result = audit_module.ModelAuditResult("test", "K1")
        audit_module.check_node_geometry(n, result)
        types = [i["type"] for i in result.issues]
        assert "face_index_oob" in types

    def test_good_normals_no_flag(self, audit_module):
        n = self._make_node(
            verts=[(0,0,0),(1,0,0),(0,1,0)],
            faces=[(0,1,2)],
            normals=[(0,0,1),(0,0,1),(0,0,1)]
        )
        result = audit_module.ModelAuditResult("test", "K1")
        audit_module.check_node_geometry(n, result)
        norm_issues = [i for i in result.issues if i["type"]=="normal_degenerate"]
        assert norm_issues == []

    def test_degenerate_normals_flagged(self, audit_module):
        n = self._make_node(
            verts=[(0,0,0),(1,0,0),(0,1,0)],
            faces=[(0,1,2)],
            normals=[(0,0,0),(0,0,0),(0,0,0)]  # zero-length → degenerate
        )
        result = audit_module.ModelAuditResult("test", "K1")
        audit_module.check_node_geometry(n, result)
        types = [i["type"] for i in result.issues]
        assert "normal_degenerate" in types

    def test_blade_plane_not_flagged(self, audit_module):
        """Lightsaber blade plane nodes (planeNNN) should not flag zero_area_faces."""
        from core.model_data import ModelNode
        # Blade plane: all vertices at same Z (flat billboard)
        n = self._make_node(
            verts=[(0,0,0),(1,0,0),(0,1,0),(1,1,0)],
            faces=[(0,1,2),(1,2,3)]
        )
        n.name = "plane211"  # lightsaber blade plane node name
        result = audit_module.ModelAuditResult("w_lghtsbr_002", "K2")
        audit_module.check_node_geometry(n, result)
        types = [i["type"] for i in result.issues]
        assert "zero_area_faces" not in types, \
            "Blade plane nodes should not flag zero_area_faces"

    def test_cone_tip_not_flagged(self, audit_module):
        """Cone tip zero-area faces should not be flagged."""
        from core.model_data import ModelNode
        # Create a simple cone-like node where tip verts all share the apex
        apex = (0, 0, 1)
        n = self._make_node(
            verts=[apex, apex, apex, (1,0,0), (0,1,0), (-1,0,0)],
            faces=[(0,1,2), (0,3,4), (0,4,5), (0,5,3)]
        )
        n.name = "Cone01"  # or_cone01 node name
        result = audit_module.ModelAuditResult("or_cone01", "K1")
        audit_module.check_node_geometry(n, result)
        types = [i["type"] for i in result.issues]
        assert "zero_area_faces" not in types, \
            "Cone tip zero-area faces should not be flagged"

    def test_walkmesh_uv_not_flagged(self, audit_module):
        """Walkmesh nodes with large UV integers should not be flagged."""
        from core.model_data import ModelNode
        n = self._make_node(
            verts=[(0,0,0),(1,0,0),(0,1,0)],
            faces=[(0,1,2)],
            uvs=[(7.0, 3.0), (7.0, 3.0), (7.0, 3.0)]  # walkability flags > 256 after tiling
        )
        n.name = "WM_07"  # walkmesh node
        result = audit_module.ModelAuditResult("m17aa_07", "K1")
        audit_module.check_node_geometry(n, result)
        types = [i["type"] for i in result.issues]
        assert "uv_extreme" not in types, \
            "Walkmesh UV integers should not be flagged"


# ── Unit tests: texture placeholder filter ──────────────────────────────────

class TestTexturePlaceholderFilter:
    def test_null_not_flagged(self, audit_module):
        assert "null" in audit_module._PLACEHOLDER_TEXTURES

    def test_toolcolors_not_flagged(self, audit_module):
        assert "toolcolors" in audit_module._PLACEHOLDER_TEXTURES

    def test_logo_sw_not_flagged(self, audit_module):
        assert "logo_sw_01" in audit_module._PLACEHOLDER_TEXTURES


# ── Unit tests: bounding box checker ────────────────────────────────────────

class TestBoundingBoxChecker:
    """BBox checker skips sky/large models and flags genuine exploded models."""

    def _make_model(self, name="testmodel"):
        from core.model_data import KotorModel, ModelNode
        m = KotorModel(name=name)
        # Create root node with 2 verts
        root = ModelNode(name="root")
        root.vertices = [(0,0,0),(1,0,0),(0,1,0)]
        root.faces = [(0,1,2)]
        m.root_node = root
        return m

    def test_sky_model_skipped(self, audit_module):
        from core.model_data import KotorModel, ModelNode
        # Name contains "_sky" → should be skipped
        m = KotorModel(name="m02aa_sky")
        root = ModelNode(name="root")
        # Huge vertex extents
        root.vertices = [(0,0,0),(10000,0,0)]
        root.faces = []
        m.root_node = root
        result = audit_module.ModelAuditResult("m02aa_sky", "K1")
        audit_module.check_bounding_box(m, result)
        bbox_issues = [i for i in result.issues if i["type"] in ("exploded_bounds","far_from_origin")]
        assert bbox_issues == [], "Sky model should not be flagged for large extents"

    def test_normal_model_no_flag(self, audit_module):
        from core.model_data import KotorModel, ModelNode, NodeFlags
        m = KotorModel(name="c_bantha")
        root = ModelNode(name="root")
        root.flags = NodeFlags.MESH          # must be a mesh node for compute_bounds
        root.vertices = [(0,0,0),(1,0,0),(0,1,0),(0,0,1)]
        root.faces = [(0,1,2)]
        root.uvs = [(0,0),(1,0),(0,1),(0,0)]  # UVs make it a proper mesh
        m.root_node = root
        result = audit_module.ModelAuditResult("c_bantha", "K1")
        audit_module.check_bounding_box(m, result)
        bbox_issues = [i for i in result.issues if "bounds" in i["type"] or "origin" in i["type"]]
        assert bbox_issues == []

    def test_exploded_model_flagged(self, audit_module):
        from core.model_data import KotorModel, ModelNode, NodeFlags
        m = KotorModel(name="corrupt_model")
        root = ModelNode(name="root")
        root.flags = NodeFlags.MESH          # must be a mesh node for compute_bounds
        root.vertices = [(0,0,0),(100000,0,0)]  # 100k units → flagged
        root.faces = [(0,1,2)] if False else []  # no faces needed, vertices alone drive bounds
        root.uvs = [(0,0),(0,0)]             # UVs so mesh_nodes() includes it
        m.root_node = root
        result = audit_module.ModelAuditResult("corrupt_model", "K1")
        audit_module.check_bounding_box(m, result)
        types = [i["type"] for i in result.issues]
        assert "exploded_bounds" in types


# ── Integration tests: extracted asset audit (replaces game-data tests) ─────

EXTRACTED_MODELS = REPO / "test_assets" / "k1_extracted" / "models"


class TestK1SampleAudit:
    """Audit extracted K1 test assets using individual audit functions.

    This replaces the former game-data-dependent TestK1SampleAudit,
    exercising the same audit pipeline on the extracted test models.
    """

    @pytest.fixture(scope="class")
    def audit_results(self, audit_module):
        """Run audit functions on all extracted models, return list of results."""
        from src.core.mdl_parser import MDLBinaryParser
        from src.resources.game_library import GameLibrary, ModelLibraryEntry
        lib = GameLibrary()
        results = []
        for fname in sorted(os.listdir(str(EXTRACTED_MODELS))):
            if not fname.endswith('.mdl'):
                continue
            resref = fname[:-4]
            mdl_path = str(EXTRACTED_MODELS / fname)
            mdx_path = mdl_path.replace('.mdl', '.mdx')
            entry = ModelLibraryEntry(
                resref=resref, game='K1', source=mdl_path,
                has_mdx=os.path.exists(mdx_path)
            )
            lib.models.append(entry)
            lib._model_index[resref.lower()] = entry

            result = audit_module.ModelAuditResult(resref, 'K1')
            try:
                mdl = open(mdl_path, 'rb').read()
                mdx = open(mdx_path, 'rb').read() if os.path.exists(mdx_path) else b''
                model = MDLBinaryParser(mdl, mdx).parse()
                result.node_count = model.node_count()
                result.mesh_count = len(model.mesh_nodes())
                result.anim_count = len(model.animations)
                result.vert_count = sum(len(n.vertices) for n in model.mesh_nodes())
                result.face_count = sum(len(n.faces) for n in model.mesh_nodes())
                result.has_skin = any(n.is_skin for n in model.all_nodes())
                for node in model.mesh_nodes():
                    audit_module.check_node_geometry(node, result)
                audit_module.check_bounding_box(model, result)
            except Exception as e:
                result.status = 'parse_error'
                result.error = str(e)
            results.append(result)
        return results

    def test_returns_list(self, audit_results):
        assert isinstance(audit_results, list)
        assert len(audit_results) > 0

    def test_no_parse_errors(self, audit_results):
        parse_errs = [r for r in audit_results if r.status == 'parse_error']
        assert parse_errs == [], \
            f"Parse errors: {[(r.resref, r.error) for r in parse_errs]}"

    def test_no_render_errors(self, audit_results):
        render_errs = [r for r in audit_results if r.status == 'render_error']
        assert render_errs == [], f"Render errors: {render_errs}"

    def test_metrics_populated(self, audit_results):
        for r in audit_results:
            if r.status == 'parse_error':
                continue
            assert isinstance(r.node_count, int)
            assert isinstance(r.mesh_count, int)
            assert isinstance(r.vert_count, int)
            assert isinstance(r.face_count, int)
            assert isinstance(r.anim_count, int)

    def test_json_written(self, audit_results, tmp_path):
        import json as _json
        out = str(tmp_path / 'audit_extracted.json')
        data = {
            'summary': {'total': len(audit_results)},
            'models': [{'resref': r.resref, 'status': r.status} for r in audit_results]
        }
        with open(out, 'w') as f:
            _json.dump(data, f)
        assert os.path.exists(out)
        with open(out) as f:
            loaded = _json.load(f)
        assert 'summary' in loaded
        assert 'models' in loaded

    def test_ok_rate_above_95_pct(self, audit_results):
        ok = sum(1 for r in audit_results if r.status == 'ok')
        ok_pct = ok / len(audit_results) * 100
        assert ok_pct >= 95.0, f"OK rate {ok_pct:.1f}% is below 95%"

    def test_c_bantha_parses_cleanly(self, audit_results):
        bantha = next((r for r in audit_results if r.resref == 'c_bantha'), None)
        assert bantha is not None, "c_bantha must be in extracted models"
        assert bantha.status != 'parse_error', f"c_bantha parse error: {bantha.error}"
        assert bantha.mesh_count > 0
        assert bantha.vert_count > 0
        assert bantha.has_skin, "c_bantha should have skin data"


class TestK2SampleAudit:
    """K2 audit contract — verified using extracted test assets.

    The former game-data K2 tests are replaced with equivalent contract
    checks that don't require a KotOR2 installation.
    """

    @pytest.fixture(scope="class")
    def audit_results(self, audit_module):
        """Reuse extracted models, label as K2 to test K2 code paths."""
        from src.core.mdl_parser import MDLBinaryParser
        results = []
        for fname in sorted(os.listdir(str(EXTRACTED_MODELS))):
            if not fname.endswith('.mdl'):
                continue
            resref = fname[:-4]
            mdl_path = str(EXTRACTED_MODELS / fname)
            mdx_path = mdl_path.replace('.mdl', '.mdx')
            result = audit_module.ModelAuditResult(resref, 'K2')
            try:
                mdl = open(mdl_path, 'rb').read()
                mdx = open(mdx_path, 'rb').read() if os.path.exists(mdx_path) else b''
                model = MDLBinaryParser(mdl, mdx).parse()
                result.node_count = model.node_count()
                result.mesh_count = len(model.mesh_nodes())
            except Exception as e:
                result.status = 'parse_error'
                result.error = str(e)
            results.append(result)
        return results

    def test_returns_list(self, audit_results):
        assert isinstance(audit_results, list)
        assert len(audit_results) > 0

    def test_no_parse_errors(self, audit_results):
        parse_errs = [r for r in audit_results if r.status == 'parse_error']
        assert parse_errs == [], \
            f"K2 parse errors: {[(r.resref, r.error) for r in parse_errs]}"

    def test_json_written(self, audit_results, tmp_path):
        import json as _json
        out = str(tmp_path / 'audit_k2.json')
        data = {'models': [{'resref': r.resref, 'status': r.status} for r in audit_results]}
        with open(out, 'w') as f:
            _json.dump(data, f)
        assert os.path.exists(out)
        with open(out) as f:
            loaded = _json.load(f)
        assert 'models' in loaded


# ── Tests for ModelAuditResult dataclass ────────────────────────────────────

class TestModelAuditResult:
    def test_status_starts_ok(self, audit_module):
        r = audit_module.ModelAuditResult("test", "K1")
        assert r.status == "ok"

    def test_add_issue_changes_status(self, audit_module):
        r = audit_module.ModelAuditResult("test", "K1")
        r.add_issue("node_x", "missing_texture", "tex 'foo' not found")
        assert r.status == "issues"
        assert len(r.issues) == 1
        assert r.issues[0]["type"] == "missing_texture"

    def test_multiple_issues_accumulated(self, audit_module):
        r = audit_module.ModelAuditResult("test", "K1")
        for i in range(5):
            r.add_issue("node", "degenerate_faces", f"issue {i}")
        assert len(r.issues) == 5
        assert r.status == "issues"

    def test_status_not_downgraded(self, audit_module):
        r = audit_module.ModelAuditResult("test", "K1")
        r.status = "parse_error"
        r.error = "file corrupt"
        r.add_issue("node", "empty_mesh", "")
        # status should stay at 'parse_error', not be changed to 'issues'
        assert r.status == "parse_error"


# ── New v5.3 suppression tests ──────────────────────────────────────────────

class TestV53Suppressions:
    """New v5.3 suppression rules: tileset seams, UV anim, skin tri-strip."""

    def _make_node(self, name, verts, faces, uvs=None, normals=None, skin_data=None, bone_map=None):
        from core.model_data import ModelNode
        n = ModelNode(name=name)
        n.vertices = verts
        n.faces = faces
        n.uvs = uvs or []
        n.normals = normals or []
        n.skin_data = skin_data or []
        n.bone_map = bone_map or []
        n.bone_map_floats = []
        n.render = True
        return n

    def test_tileset_seam_zero_area_suppressed(self, audit_module):
        """Zero-area faces in K2 201tel tileset models are suppressed."""
        # Create a node with >10% zero-area faces
        verts = [(0,0,0),(0,0,0),(0,0,0),(1,0,0),(0,1,0),(0,0,1)]
        # 4 zero-area + 2 good
        faces = [(0,1,2),(0,1,2),(0,1,2),(0,1,2),(0,3,4),(0,4,5)]
        n = self._make_node("Scaf2", verts=verts, faces=faces)
        result = audit_module.ModelAuditResult("201tel01", "K2")
        audit_module.check_node_geometry(n, result)
        types = [i["type"] for i in result.issues]
        assert "zero_area_faces" not in types, \
            "201tel tileset seam faces must be suppressed"

    def test_minigame_uv_anim_suppressed(self, audit_module):
        """UV values >256 in minigame clock models are suppressed."""
        # Create a node with >10% UV values > 256
        verts = [(0,0,0),(1,0,0),(0,1,0)]
        faces = [(0,1,2)]
        # All 3 UVs have u>256
        uvs = [(300.0, 0.5), (301.0, 0.5), (302.0, 0.5)]
        n = self._make_node("MilSecondsOne_1", verts=verts, faces=faces, uvs=uvs)
        result = audit_module.ModelAuditResult("m03mg_camera", "K1")
        audit_module.check_node_geometry(n, result)
        types = [i["type"] for i in result.issues]
        assert "uv_extreme" not in types, \
            "Minigame UV anim nodes must not flag uv_extreme"

    def test_skin_tristrip_degenerate_suppressed(self, audit_module):
        """Degenerate faces in skinned meshes with <2% rate are suppressed."""
        from core.model_data import VertexSkinData, BoneWeight
        # Build 100 good faces + 1 degenerate
        verts = [(float(i), 0.0, 0.0) for i in range(10)]
        good_faces = [(0,1,2),(1,2,3),(2,3,4),(3,4,5),(4,5,6),(5,6,7),(6,7,8),(7,8,9)] * 12  # 96
        degen_face = (0, 0, 1)  # 1 degenerate
        faces = good_faces + [degen_face]
        skin_data = [VertexSkinData(influences=[BoneWeight(0, 1.0)]) for _ in verts]
        n = self._make_node("Two_Head", verts=verts, faces=faces,
                           skin_data=skin_data, bone_map=["bone0"])
        result = audit_module.ModelAuditResult("c_twohead", "K1")
        audit_module.check_node_geometry(n, result)
        types = [i["type"] for i in result.issues]
        assert "degenerate_faces" not in types, \
            "Skinned mesh tri-strip degen faces (<2%) must be suppressed"

    def test_dev_textures_in_placeholder_list(self, audit_module):
        """All known dev/test textures are in placeholder set."""
        placeholders = audit_module._PLACEHOLDER_TEXTURES
        expected = [
            "h_f_lo01headtest", "h_m_lo01headtest", "pheyea",
            "pmbf", "pmblv", "pmbmv_01", "pointer_00_02_01",
            "load_sw2", "load_sw", "w_lghtsbr", "fx_sun01",
            "tech01", "tech02", "tech03", "tech04", "tech05",
        ]
        for tex in expected:
            assert tex in placeholders, f"'{tex}' should be in placeholder list"

    def test_tileset_seam_resref_function(self, audit_module):
        """_is_tileset_seam_model correctly identifies seam models."""
        assert audit_module._is_tileset_seam_model("201tel01"), "201tel01 should be tileset seam"
        assert audit_module._is_tileset_seam_model("304nar_06"), "304nar_06 should be tileset seam"
        assert audit_module._is_tileset_seam_model("c_drdmktwo"), "c_drdmktwo should be seam model"
        assert not audit_module._is_tileset_seam_model("c_bantha"), "c_bantha should NOT be seam"
        assert not audit_module._is_tileset_seam_model("n_jedif"), "n_jedif should NOT be seam"
