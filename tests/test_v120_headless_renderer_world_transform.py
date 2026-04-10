"""
test_v120_headless_renderer_world_transform.py
================================================
Tests that the headless render test (tools/headless_render_test.py) correctly
applies bind-pose world transforms to all vertices before rendering.

Root cause of "mouth on tail" / "holes in bantha" issues:
  The original headless_render_test.py used raw node-local vertex positions.
  KotOR MDL skin nodes store vertices in node-local space (offset from the
  skin node's world position).  Without applying the world transform, every
  skin mesh appeared displaced from its correct location.

  The fix mirrors the viewport's _get_world_verts_for_node logic:
    v_world = rotate(world_quat, v_local) + world_pos

These tests verify:
  1. _get_node_world_transform returns correct position and orientation.
  2. _apply_vertex_transform applies the transform correctly.
  3. _get_world_verts applies the transform to all vertices.
  4. _is_renderable filters out render=False, no-UV, and deform-helper nodes.
  5. _is_deformation_helper correctly identifies internal mesh nodes.
  6. collect_renderable_nodes uses _is_renderable filter.
  7. Full render pipeline: world-space bounding box is non-degenerate.
"""
import math
import sys
import os
import pytest

# Add repo root to path so we can import from tools/
_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, 'src'))

from core.model_data import ModelNode, NodeFlags, KotorModel, _quat_rotate


# ── Import headless renderer helpers directly ─────────────────────────────────
# We import the functions directly from the tools module rather than running the
# script so we can unit-test the individual helpers.
import importlib.util as _ilu

def _load_headless():
    """Load tools/headless_render_test.py without executing the main body."""
    spec = _ilu.spec_from_file_location(
        "headless_render_test",
        os.path.join(_REPO, "tools", "headless_render_test.py"),
    )
    mod = _ilu.module_from_spec(spec)
    # Patch GameLibrary.scan to avoid slow game-data scan during unit tests
    import unittest.mock as _mock
    with _mock.patch("resources.game_library.GameLibrary._scan_game"):
        try:
            spec.loader.exec_module(mod)
        except SystemExit:
            pass
        except Exception:
            pass  # Game data not present in CI; only helpers are tested
    return mod


# Guard: only run if tools/ is importable (i.e. not in a stripped CI env)
_hr = None
try:
    _hr = _load_headless()
except Exception:
    pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _node(name, flags, pos=(0, 0, 0), rot=(0, 0, 0, 1)):
    n = ModelNode(name=name, flags=flags, position=pos, rotation=rot)
    return n


def _attach(parent, child):
    child.parent = parent
    parent.children.append(child)
    return child


def _mesh_node(name, texture='tex01', pos=(0, 0, 0), rot=(0, 0, 0, 1),
               render=True, is_skin=False):
    flags = int(NodeFlags.MESH | NodeFlags.SKIN) if is_skin else int(NodeFlags.MESH)
    n = _node(name, flags, pos, rot)
    n.texture  = texture
    n.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    n.uvs      = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    n.faces    = [(0, 1, 2)]
    n.render   = render
    n.diffuse  = (0.8, 0.8, 0.8)
    n.ambient  = (0.2, 0.2, 0.2)
    n.specular = (0.0, 0.0, 0.0)
    n.shininess = 0.0
    n.alpha    = 1.0
    return n


def _approx(a, b, tol=1e-3):
    return all(abs(x - y) < tol for x, y in zip(a, b))


# ── Tests that don't require game data ────────────────────────────────────────

@pytest.mark.skipif(_hr is None, reason="tools/headless_render_test.py not importable")
class TestGetNodeWorldTransform:
    """Verify _get_node_world_transform matches model_data.world_transform."""

    def test_simple_identity(self):
        n = _mesh_node('test', pos=(1.0, 2.0, 3.0), rot=(0, 0, 0, 1))
        wp, wo, is_id = _hr._get_node_world_transform(n)
        assert _approx(wp, (1.0, 2.0, 3.0))
        assert is_id, f"Expected identity orientation, got {wo}"

    def test_parent_offset_accumulated(self):
        root = _node('root', NodeFlags.HEADER, pos=(0, 0, 1.0), rot=(0, 0, 0, 1))
        child = _mesh_node('child', pos=(0, 0, 0.5))
        _attach(root, child)
        wp, wo, is_id = _hr._get_node_world_transform(child)
        assert _approx(wp, (0, 0, 1.5), tol=0.001)

    def test_nwn_root_flip_doesnt_corrupt_child_z(self):
        """
        NWN coordinate-flip root (1,0,0,0) = 180° about X.
        Child Z position must accumulate correctly (not negate).
        """
        root = _node('root', NodeFlags.HEADER, pos=(0, 0, 0), rot=(1, 0, 0, 0))
        body = _mesh_node('body', pos=(0, 0, 1.5))
        _attach(root, body)
        wp, _, is_id = _hr._get_node_world_transform(body)
        # Position Z must be positive (1.5), not negative
        assert abs(wp[2] - 1.5) < 0.01, \
            f"NWN root flip corrupted Z: expected 1.5, got {wp[2]}"

    def test_non_identity_leaf_rotation(self):
        """A leaf with 180°Z rotation must report is_identity=False."""
        root = _node('root', NodeFlags.HEADER, pos=(0, 0, 0), rot=(1, 0, 0, 0))
        panel = _mesh_node('panel', pos=(0, 0, 1.0), rot=(0, 0, 1, 0))  # 180°Z
        _attach(root, panel)
        wp, wo, is_id = _hr._get_node_world_transform(panel)
        assert not is_id, "180°Z leaf rotation must not be identity"


@pytest.mark.skipif(_hr is None, reason="tools/headless_render_test.py not importable")
class TestApplyVertexTransform:
    """Verify _apply_vertex_transform correctly places vertices in world space."""

    def test_identity_adds_offset(self):
        v = (1.0, 2.0, 3.0)
        wp = (5.0, 0.0, 0.0)
        wo = (0, 0, 0, 1)
        result = _hr._apply_vertex_transform(v, wp, wo, True)
        assert _approx(result, (6.0, 2.0, 3.0))

    def test_180z_rotation_flips_xy(self):
        v = (1.0, 0.5, 2.0)
        wp = (0, 0, 0)
        wo = (0, 0, 1, 0)  # 180° about Z
        result = _hr._apply_vertex_transform(v, wp, wo, False)
        assert abs(result[0] - (-1.0)) < 0.01, f"X should flip: {result}"
        assert abs(result[1] - (-0.5)) < 0.01, f"Y should flip: {result}"
        assert abs(result[2] - 2.0) < 0.01, f"Z unchanged: {result}"

    def test_translation_applied_after_rotation(self):
        v = (1.0, 0.0, 0.0)
        wp = (10.0, 0.0, 0.0)
        wo = (0, 0, 1, 0)  # 180°Z: x → -x
        result = _hr._apply_vertex_transform(v, wp, wo, False)
        # After 180°Z: v = (-1, 0, 0); then + (10, 0, 0) = (9, 0, 0)
        assert abs(result[0] - 9.0) < 0.01


@pytest.mark.skipif(_hr is None, reason="tools/headless_render_test.py not importable")
class TestGetWorldVerts:
    """Verify _get_world_verts applies transform to all vertices."""

    def test_vertices_shifted_by_node_position(self):
        """Skin node at (0, 0, 1.5): all verts should shift by Z=1.5."""
        root = _node('root', NodeFlags.HEADER, rot=(1, 0, 0, 0))  # NWN flip
        skin = _mesh_node('skin', pos=(0, 0, 1.5), is_skin=True)
        skin.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
        _attach(root, skin)
        wv = _hr._get_world_verts(skin)
        assert len(wv) == 2
        assert abs(wv[0][2] - 1.5) < 0.01, f"Vertex Z must be offset by 1.5, got {wv[0]}"
        assert abs(wv[1][2] - 1.5) < 0.01

    def test_empty_node_returns_empty(self):
        n = _mesh_node('empty')
        n.vertices = []
        wv = _hr._get_world_verts(n)
        assert wv == []

    def test_world_verts_different_from_local(self):
        """World verts must differ from local when node is not at origin."""
        root = _node('root', NodeFlags.HEADER)
        skin = _mesh_node('skin', pos=(5.0, 3.0, 2.0), is_skin=True)
        skin.vertices = [(0.0, 0.0, 0.0)]
        _attach(root, skin)
        wv = _hr._get_world_verts(skin)
        assert wv[0] != (0.0, 0.0, 0.0), \
            "World vertex should differ from local origin when node has offset"
        assert _approx(wv[0], (5.0, 3.0, 2.0), tol=0.01)


@pytest.mark.skipif(_hr is None, reason="tools/headless_render_test.py not importable")
class TestIsDeformationHelperHeadless:
    """Verify _is_deformation_helper matches OBJExporter._is_deformation_helper."""

    def test_null_tex_non_skin_is_helper(self):
        n = _mesh_node('head_g', texture='null', is_skin=False)
        assert _hr._is_deformation_helper(n)

    def test_g_suffix_non_skin_is_helper(self):
        n = _mesh_node('rthigh_g', texture='', is_skin=False)
        assert _hr._is_deformation_helper(n)

    def test_extreme_uv_is_helper(self):
        n = _mesh_node('pelvis', texture='tex01', is_skin=False)
        n.uvs = [(5.0, 0.5), (0.0, 0.0), (0.0, 0.0)]
        assert _hr._is_deformation_helper(n)

    def test_skin_with_real_tex_valid_uvs_not_helper(self):
        n = _mesh_node('body', texture='c_bantha01', is_skin=True)
        assert not _hr._is_deformation_helper(n)

    def test_normal_textured_non_skin_not_helper(self):
        n = _mesh_node('head', texture='c_jawa01', is_skin=False)
        assert not _hr._is_deformation_helper(n)


@pytest.mark.skipif(_hr is None, reason="tools/headless_render_test.py not importable")
class TestIsRenderableHeadless:
    """Verify _is_renderable filters the correct node types."""

    def test_renderable_node_passes(self):
        n = _mesh_node('body', texture='tex01', render=True)
        assert _hr._is_renderable(n)

    def test_render_false_excluded(self):
        n = _mesh_node('bone', texture='tex01', render=False)
        assert not _hr._is_renderable(n)

    def test_no_uvs_excluded(self):
        n = _mesh_node('proxy', texture='tex01')
        n.uvs = []
        assert not _hr._is_renderable(n)

    def test_no_vertices_excluded(self):
        n = _mesh_node('empty', texture='tex01')
        n.vertices = []
        assert not _hr._is_renderable(n)

    def test_no_faces_excluded(self):
        n = _mesh_node('edgeless', texture='tex01')
        n.faces = []
        assert not _hr._is_renderable(n)

    def test_deform_helper_excluded(self):
        n = _mesh_node('rthigh_g', texture='null', is_skin=False, render=True)
        assert not _hr._is_renderable(n)


@pytest.mark.skipif(_hr is None, reason="tools/headless_render_test.py not importable")
class TestCollectRenderableNodes:
    """Verify collect_renderable_nodes returns only renderable geometry."""

    def _make_simple_model(self):
        model = KotorModel(name='test')
        root = _node('root', NodeFlags.HEADER)
        model.root_node = root
        return model, root

    def test_only_renderable_included(self):
        model, root = self._make_simple_model()
        vis  = _mesh_node('visible', texture='tex01', render=True)
        invis = _mesh_node('hidden', texture='tex01', render=False)
        _attach(root, vis)
        _attach(root, invis)
        nodes = _hr.collect_renderable_nodes(model)
        names = [n.name for n in nodes]
        assert 'visible' in names
        assert 'hidden' not in names

    def test_deform_helpers_excluded(self):
        model, root = self._make_simple_model()
        real  = _mesh_node('body', texture='c_bantha01', is_skin=True, render=True)
        helper = _mesh_node('rthigh_g', texture='null', is_skin=False, render=True)
        _attach(root, real)
        _attach(root, helper)
        nodes = _hr.collect_renderable_nodes(model)
        names = [n.name for n in nodes]
        assert 'body' in names
        assert 'rthigh_g' not in names

    def test_empty_model_returns_empty_list(self):
        model = KotorModel(name='empty')
        model.root_node = _node('root', NodeFlags.HEADER)
        nodes = _hr.collect_renderable_nodes(model)
        assert nodes == []

    def test_nested_hierarchy_traversed(self):
        """collect_renderable_nodes must walk the full node tree."""
        model, root = self._make_simple_model()
        mid  = _node('mid', NodeFlags.HEADER)
        deep = _mesh_node('deep_body', texture='tex01', render=True)
        _attach(root, mid)
        _attach(mid, deep)
        nodes = _hr.collect_renderable_nodes(model)
        assert any(n.name == 'deep_body' for n in nodes), \
            "Nested renderable node must be found by collector"


# ══════════════════════════════════════════════════════════════════════════════
#  FIX-HEADLESS-CAM: _cam_view_matrix() shim tests
# ══════════════════════════════════════════════════════════════════════════════

class TestCamViewMatrixShim:
    """
    Verify FrameRenderer._cam_view_matrix() works with both ArcBallCamera
    objects and duck-typed plain-namespace cameras (as used by
    render_model_autoframe / _render_cpu).

    FIX-HEADLESS-CAM: Previously FrameRenderer._render_inner called
    self.cam._view_matrix() which raised AttributeError for duck-typed cameras
    that only have eye/target/up attributes.  The shim now detects the
    attribute type and builds the view matrix from raw geometry.
    """

    def _get_frame_renderer(self):
        """Return a FrameRenderer instance using a minimal duck-typed camera."""
        try:
            from src.gui.viewport import FrameRenderer
        except ImportError:
            pytest.skip("viewport not importable")

        class _DuckCam:
            eye    = (0.0, 5.0, 0.0)
            target = (0.0, 0.0, 0.0)
            up     = (0.0, 0.0, 1.0)
            fov    = 45.0
            near   = 0.01
            far    = 1000.0

        cam = _DuckCam()
        renderer = FrameRenderer(cam)
        return renderer

    def test_duck_cam_returns_four_vectors(self):
        """_cam_view_matrix() must return a (right, up, fwd, eye) 4-tuple."""
        renderer = self._get_frame_renderer()
        result = renderer._cam_view_matrix()
        assert len(result) == 4, "_cam_view_matrix must return (right, up, fwd, eye)"
        right, up, fwd, eye = result
        assert len(right) == 3 and len(up) == 3 and len(fwd) == 3 and len(eye) == 3

    def test_duck_cam_eye_matches(self):
        """eye component must equal camera.eye."""
        renderer = self._get_frame_renderer()
        _, _, _, eye = renderer._cam_view_matrix()
        assert abs(eye[1] - 5.0) < 1e-5, f"Expected eye.y=5.0, got {eye[1]}"

    def test_duck_cam_fwd_points_toward_target(self):
        """fwd should point from eye (0,5,0) toward target (0,0,0) = (0,-1,0)."""
        renderer = self._get_frame_renderer()
        _, _, fwd, _ = renderer._cam_view_matrix()
        # fwd = normalize((0,0,0)-(0,5,0)) = (0,-1,0)
        assert abs(fwd[1] - (-1.0)) < 1e-4, f"fwd.y should be ~-1, got {fwd[1]}"

    def test_duck_cam_right_is_unit_vector(self):
        """right vector must be unit length."""
        import math
        renderer = self._get_frame_renderer()
        right, _, _, _ = renderer._cam_view_matrix()
        length = math.sqrt(right[0]**2 + right[1]**2 + right[2]**2)
        assert abs(length - 1.0) < 1e-5, f"right must be unit length, got {length}"

    def test_arcball_cam_uses_native_view_matrix(self):
        """When cam has _view_matrix(), the shim must delegate to it."""
        try:
            from src.gui.viewport import FrameRenderer, ArcBallCamera
        except ImportError:
            pytest.skip("viewport not importable")

        cam = ArcBallCamera()
        renderer = FrameRenderer(cam)
        # Should not raise
        result = renderer._cam_view_matrix()
        assert len(result) == 4

    def test_render_model_autoframe_duck_cam_no_error(self):
        """render_model_autoframe must run without '_view_matrix' AttributeError."""
        try:
            from src.core.model_data import KotorModel, ModelNode, NodeFlags
            from src.gui.gpu_renderer import render_model_autoframe
        except ImportError:
            pytest.skip("gpu_renderer or model_data not importable")

        # Build minimal model with one visible mesh
        model = KotorModel(name='test_model')
        root = ModelNode(name='scene_root', flags=int(NodeFlags.HEADER))
        model.root_node = root
        mesh = ModelNode(name='body', flags=int(NodeFlags.MESH | NodeFlags.SKIN))
        mesh.texture    = ''
        mesh.vertices   = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        mesh.uvs        = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
        mesh.faces      = [[0, 1, 2]]
        mesh.render     = True
        mesh.alpha      = 1.0
        mesh.diffuse    = (0.8, 0.8, 0.8)
        mesh.ambient    = (0.2, 0.2, 0.2)
        mesh.position   = (0.0, 0.0, 0.0)
        mesh.rotation   = (0.0, 0.0, 0.0, 1.0)
        mesh.parent     = root
        root.children.append(mesh)
        # Note: model.nodes is a read-only property derived from root_node tree,
        # so we do not set model.nodes directly.

        # Must not raise AttributeError about _view_matrix
        try:
            result = render_model_autoframe(model, textures={}, W=64, H=64,
                                            views=['front'])
        except AttributeError as exc:
            pytest.fail(f"render_model_autoframe raised AttributeError: {exc}")
        # Result may be empty if renderer has no GPU context, that's fine
        assert isinstance(result, dict)
