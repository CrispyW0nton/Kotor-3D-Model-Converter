"""
Phase 24 – OBJ / FBX import render fix tests
=============================================
Tests that verify imported OBJ/FBX models are always rendered in the viewport
and are never mis-classified as KotOR deformation-helper nodes.

Root cause that was fixed:
  • A previous edit inserted the _imported early-exit inside the *docstring* of
    _is_deformation_helper() in viewport.py, creating a SyntaxError that
    prevented the program from starting at all.
  • The _is_render_helper() function in model_data.render_bounds() also lacked
    the _imported check, causing camera framing to produce a zero-size bounding
    box for texture-less OBJ imports.
  • OBJImporter._make_node, FBXImporter._assimp_mesh, and FBXImporter._load_trimesh
    all now tag produced nodes with _imported=True and render=True.
"""
import copy
import math
import tempfile
import os
import pytest
import sys

sys.path.insert(0, "src")

from core.model_data import ModelNode, NodeFlags, KotorModel, GameVersion
from converters.mesh_converter import OBJImporter


# ── Helpers ──────────────────────────────────────────────────────────────────

def _clean_tex(name: str) -> str:
    if not name:
        return ""
    return "".join(c for c in name if 32 <= ord(c) < 127).strip()


def _is_deformation_helper(node) -> bool:
    """Mirrors FrameRenderer._is_deformation_helper() from viewport.py."""
    if getattr(node, "_imported", False):
        return False
    tex = _clean_tex(getattr(node, "texture", "") or "")
    is_null = not tex or tex.upper() == "NULL"
    if node.is_skin and not is_null and node.uvs:
        if not any(abs(u) > 3.0 or abs(v) > 3.0 for u, v in node.uvs[:20]):
            return False
    if node.uvs and any(abs(u) > 3.0 or abs(v) > 3.0 for u, v in node.uvs[:20]):
        return True
    name_lower = node.name.lower()
    if not node.is_skin and (
        name_lower.endswith("_g") or name_lower.endswith("_g0") or name_lower.endswith("_dum")
    ):
        return True
    if is_null and not node.is_skin:
        return True
    if is_null and node.is_skin and (
        not node.uvs or all(u == 0.0 and v == 0.0 for u, v in node.uvs[:5])
    ):
        return True
    if not node.is_skin and not node.uvs:
        return True
    return False


def _make_obj(content: str) -> str:
    """Write OBJ content to a temp file, return path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".obj", delete=False)
    f.write(content)
    f.close()
    return f.name


# ── OBJ_WITH_UVS ─────────────────────────────────────────────────────────────
OBJ_UV = """\
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
vt 0 0
vt 1 0
vt 1 1
vt 0 1
vn 0 0 1
g face
f 1/1/1 2/2/1 3/3/1
f 1/1/1 3/3/1 4/4/1
"""

# ── OBJ_NO_UVS ───────────────────────────────────────────────────────────────
OBJ_NO_UV = """\
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
g face
f 1 2 3
f 1 3 4
"""

# ── OBJ_WITH_MATERIAL ────────────────────────────────────────────────────────
OBJ_MAT = """\
mtllib skin.mtl
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
vt 0 0
vt 1 0
vt 1 1
vt 0 1
vn 0 0 1
usemtl skin_tex
g skin_mesh
f 1/1/1 2/2/1 3/3/1
"""

# ── OBJ with _g-suffix group name (should still render because _imported) ────
OBJ_G_SUFFIX = """\
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
g lbicep_g
f 1 2 3
f 1 3 4
"""


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestOBJImportRenderable:
    """Mesh nodes from OBJ imports must always be rendered."""

    def _import_and_get_mesh_nodes(self, obj_src: str):
        path = _make_obj(obj_src)
        try:
            model = OBJImporter().import_file(path)
        finally:
            os.unlink(path)
        return [n for n in model.all_nodes() if n.is_mesh]

    def test_obj_with_uvs_tagged_imported(self):
        nodes = self._import_and_get_mesh_nodes(OBJ_UV)
        assert nodes, "Expected at least one mesh node"
        for n in nodes:
            assert getattr(n, "_imported", False), f"{n.name}: _imported not set"

    def test_obj_no_uvs_tagged_imported(self):
        nodes = self._import_and_get_mesh_nodes(OBJ_NO_UV)
        assert nodes
        for n in nodes:
            assert getattr(n, "_imported", False), f"{n.name}: _imported not set"

    def test_obj_g_suffix_tagged_imported(self):
        """_g suffix nodes from OBJ import must NOT be filtered out."""
        nodes = self._import_and_get_mesh_nodes(OBJ_G_SUFFIX)
        assert nodes
        for n in nodes:
            assert getattr(n, "_imported", False)

    def test_render_flag_set_on_import(self):
        nodes = self._import_and_get_mesh_nodes(OBJ_UV)
        for n in nodes:
            assert n.render is True, f"{n.name}: render should be True"

    def test_not_deformation_helper_with_uvs(self):
        nodes = self._import_and_get_mesh_nodes(OBJ_UV)
        for n in nodes:
            assert not _is_deformation_helper(n), f"{n.name} wrongly marked as deform helper"

    def test_not_deformation_helper_without_uvs(self):
        nodes = self._import_and_get_mesh_nodes(OBJ_NO_UV)
        for n in nodes:
            assert not _is_deformation_helper(n), f"{n.name} wrongly marked as deform helper (no UVs)"

    def test_not_deformation_helper_g_suffix(self):
        """KotOR _g heuristic must be bypassed for _imported nodes."""
        nodes = self._import_and_get_mesh_nodes(OBJ_G_SUFFIX)
        for n in nodes:
            assert not _is_deformation_helper(n), f"{n.name} wrongly marked as deform helper (g suffix)"

    def test_not_deformation_helper_empty_texture(self):
        """OBJ nodes with empty texture (no MTL) must not be filtered."""
        path = _make_obj(OBJ_NO_UV)
        try:
            model = OBJImporter().import_file(path)
        finally:
            os.unlink(path)
        for n in model.all_nodes():
            if n.is_mesh:
                assert n.texture == "" or n.texture is None or n.texture == "mesh_0"
                assert not _is_deformation_helper(n)


class TestDeepCopyPreservesImported:
    """deepcopy (used by RetargetEngine) must preserve _imported."""

    def test_deepcopy_preserves_imported(self):
        node = ModelNode(name="t", flags=int(NodeFlags.HEADER | NodeFlags.MESH))
        node._imported = True
        node.render = True
        node2 = copy.deepcopy(node)
        assert getattr(node2, "_imported", False) is True

    def test_deepcopy_preserves_render(self):
        node = ModelNode(name="t", flags=int(NodeFlags.HEADER | NodeFlags.MESH))
        node._imported = True
        node.render = True
        node2 = copy.deepcopy(node)
        assert node2.render is True


class TestRenderBoundsImported:
    """render_bounds() must include _imported nodes for camera framing."""

    def _build_model_with_imported_node(self, texture="", with_uvs=True):
        model = KotorModel(name="test", game_version=GameVersion.K1)
        root = ModelNode(name="test", flags=int(NodeFlags.HEADER))
        n = ModelNode(
            name="mesh", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=root
        )
        n._imported = True
        n.render = True
        n.texture = texture
        n.vertices = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0)]
        n.faces = [(0, 1, 2)]
        if with_uvs:
            n.uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]
        else:
            n.uvs = []
        root.children = [n]
        model.root_node = root
        return model

    def test_imported_node_included_in_bounds_with_uvs(self):
        model = self._build_model_with_imported_node(texture="", with_uvs=True)
        bounds = model.render_bounds()
        # Bounds should NOT be a degenerate zero box
        mn, mx = bounds
        assert mx[0] > mn[0] or mx[1] > mn[1] or mx[2] > mn[2], (
            f"render_bounds was zero for _imported node: {bounds}"
        )

    def test_imported_node_included_in_bounds_no_uvs(self):
        model = self._build_model_with_imported_node(texture="", with_uvs=False)
        bounds = model.render_bounds()
        mn, mx = bounds
        assert mx[0] > mn[0] or mx[1] > mn[1] or mx[2] > mn[2], (
            f"render_bounds was zero for _imported node (no UVs): {bounds}"
        )

    def test_imported_node_null_tex_included(self):
        """Null-texture _imported nodes must still be included in bounds."""
        model = self._build_model_with_imported_node(texture="NULL", with_uvs=True)
        bounds = model.render_bounds()
        mn, mx = bounds
        assert mx[0] > mn[0] or mx[1] > mn[1] or mx[2] > mn[2]

    def test_obj_import_render_bounds_non_degenerate(self):
        """Full OBJ import: render_bounds must not be a point."""
        obj_src = """\
v -1 0 0
v  1 0 0
v  1 2 0
v -1 2 0
vt 0 0
vt 1 0
vt 1 1
vt 0 1
vn 0 0 1
g body
f 1/1/1 2/2/1 3/3/1
f 1/1/1 3/3/1 4/4/1
"""
        path = _make_obj(obj_src)
        try:
            model = OBJImporter().import_file(path)
        finally:
            os.unlink(path)
        mn, mx = model.render_bounds()
        dx = mx[0] - mn[0]
        dy = mx[1] - mn[1]
        assert dx > 0 or dy > 0, f"render_bounds is degenerate: {(mn, mx)}"


class TestViewportSyntaxCheck:
    """The viewport.py file must be importable (no SyntaxErrors)."""

    def test_viewport_no_syntax_error(self):
        import py_compile
        try:
            py_compile.compile("src/gui/viewport.py", doraise=True)
        except SyntaxError as e:
            pytest.fail(f"viewport.py has a SyntaxError: {e}")

    def test_deformation_helper_imported_bypass_is_first_check(self):
        """The _imported early-exit must be the VERY FIRST check in the function
        body (before any texture/UV analysis) to ensure all OBJ/FBX nodes render."""
        with open("src/gui/viewport.py", "r", encoding="utf-8") as f:
            src = f.read()
        # Find the method
        start = src.find("def _is_deformation_helper(self, node")
        assert start != -1, "_is_deformation_helper not found in viewport.py"
        # Find the closing quote of the docstring
        doc_start = src.find('"""', start)
        assert doc_start != -1
        doc_end = src.find('"""', doc_start + 3)
        assert doc_end != -1
        # The first non-comment, non-blank line after the docstring should contain
        # 'if getattr(node, ' and '_imported'
        body_after_doc = src[doc_end + 3 :]
        # Find first executable line
        for line in body_after_doc.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            assert "_imported" in stripped, (
                f"First executable line after docstring does not check _imported: {stripped!r}"
            )
            break
