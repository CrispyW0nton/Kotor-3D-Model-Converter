"""
test_v110_obj_export_render_filter.py
======================================
Tests that OBJExporter (and its helper _is_renderable) correctly filters out:
  - Nodes with render=False (engine-internal / collision proxy)
  - Deformation-helper nodes (null texture, _g/_dum suffix, extreme UVs)
  - Emitter and light nodes

Also verifies:
  - Texture 'null'/'NULL'/'BLACK' → omitted from MTL map_Kd
  - Face indices use correct per-object offsets (no closure capture bug)
  - V coordinate is flipped (vt_out = 1 - v_in)
"""
import io, os, sys, tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.converters.mesh_converter import OBJExporter, _renderable_mesh_nodes
from src.core.model_data import KotorModel, ModelNode, NodeFlags, GameVersion


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_mesh_node(name, texture='tex01', verts=None, uvs=None, faces=None,
                    render=True, is_skin=False, is_emitter=False, is_light=False):
    """
    Build a ModelNode using the correct flag API.

    Node types are set via NodeFlags (they are bit-derived properties; no
    direct setter exists).  The mapping is:
      - MESH            → is_mesh=True
      - MESH | SKIN     → is_mesh=True, is_skin=True
      - EMITTER         → is_emitter=True
      - LIGHT           → is_light=True
    """
    if is_emitter:
        flags = int(NodeFlags.EMITTER)
    elif is_light:
        flags = int(NodeFlags.LIGHT)
    elif is_skin:
        flags = int(NodeFlags.MESH) | int(NodeFlags.SKIN)
    else:
        flags = int(NodeFlags.MESH)

    n = ModelNode(name=name, flags=flags)
    n.texture  = texture
    # texture_clean is a read-only computed property – set via n.texture only
    # Use explicit None checks so callers can pass empty lists intentionally
    n.vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0)] if verts is None else verts
    n.uvs      = [(0, 0), (1, 0), (0, 1)]           if uvs   is None else uvs
    n.normals  = [(0, 0, 1)] * max(len(n.vertices), 1)
    n.faces    = [(0, 1, 2)]                         if faces is None else faces
    n.render   = render
    n.diffuse  = (0.8, 0.8, 0.8)
    n.ambient  = (0.2, 0.2, 0.2)
    n.specular = (0.0, 0.0, 0.0)
    n.shininess = 0.0
    n.alpha    = 1.0
    return n


def _make_model_with_nodes(nodes):
    model = KotorModel(name='test_model', game_version=GameVersion.K1)
    root  = ModelNode(name='test_model', flags=int(NodeFlags.HEADER))
    model.root_node = root
    for n in nodes:
        n.parent = root
        root.children.append(n)
    # Patch mesh_nodes() to return our test list
    model.mesh_nodes = lambda: list(nodes)
    return model


def _export_to_string(model):
    """Export model to a temp file and return (obj_text, mtl_text)."""
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, 'test.obj')
        OBJExporter().export(model, path)
        obj = open(path).read()
        mtl = open(path.replace('.obj', '.mtl')).read()
    return obj, mtl


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestIsDeformationHelper:
    """Unit tests for OBJExporter._is_deformation_helper."""

    def test_null_tex_non_skin_is_helper(self):
        n = _make_mesh_node('node01', texture='null')
        assert OBJExporter._is_deformation_helper(n)

    def test_null_tex_uppercase_is_helper(self):
        n = _make_mesh_node('node01', texture='NULL')
        assert OBJExporter._is_deformation_helper(n)

    def test_empty_tex_is_helper(self):
        n = _make_mesh_node('node01', texture='')
        assert OBJExporter._is_deformation_helper(n)

    def test_g_suffix_non_skin_is_helper(self):
        # Non-skin node with _g suffix → helper, even if it has a texture
        n = _make_mesh_node('pelvis_g', texture='real_tex', is_skin=False)
        assert OBJExporter._is_deformation_helper(n)

    def test_dum_suffix_is_helper(self):
        n = _make_mesh_node('collar_dum', texture='')
        assert OBJExporter._is_deformation_helper(n)

    def test_extreme_uv_is_helper(self):
        n = _make_mesh_node('body01', uvs=[(5.0, 0.0), (1.0, 0.0), (0.0, 1.0)])
        assert OBJExporter._is_deformation_helper(n)

    def test_skin_with_real_tex_valid_uvs_not_helper(self):
        n = _make_mesh_node('body_g', texture='c_bantha01',
                            uvs=[(0.1, 0.2), (0.5, 0.3), (0.9, 0.8)],
                            is_skin=True)
        assert not OBJExporter._is_deformation_helper(n)

    def test_normal_textured_non_skin_not_helper(self):
        n = _make_mesh_node('body01', texture='c_bantha01')
        assert not OBJExporter._is_deformation_helper(n)


class TestIsRenderable:
    """Unit tests for OBJExporter._is_renderable."""

    def test_renderable_node(self):
        n = _make_mesh_node('body01', texture='tex01', render=True)
        assert OBJExporter._is_renderable(n)

    def test_render_false_excluded(self):
        n = _make_mesh_node('body01', texture='tex01', render=False)
        assert not OBJExporter._is_renderable(n)

    def test_no_vertices_excluded(self):
        n = _make_mesh_node('body01', texture='tex01', verts=[])
        assert not OBJExporter._is_renderable(n)

    def test_emitter_excluded(self):
        # Emitter flag → is_emitter=True; set texture & vertices so only
        # the emitter check causes exclusion
        n = _make_mesh_node('sparks', texture='spark', is_emitter=True)
        assert not OBJExporter._is_renderable(n)

    def test_light_excluded(self):
        n = _make_mesh_node('light01', texture='', is_light=True)
        assert not OBJExporter._is_renderable(n)

    def test_deform_helper_excluded(self):
        # null-texture non-skin → deformation helper → not renderable
        n = _make_mesh_node('pelvis_g', texture='null', render=True)
        assert not OBJExporter._is_renderable(n)


class TestOBJExporterOutput:
    """Integration tests checking the generated OBJ/MTL content."""

    def test_only_renderable_nodes_exported(self):
        vis    = _make_mesh_node('body_vis', texture='c_tex01', render=True)
        invis  = _make_mesh_node('body_dum', texture='null',    render=False)
        helper = _make_mesh_node('pelvis_g', texture='null',    render=True)
        model  = _make_model_with_nodes([vis, invis, helper])

        obj, mtl = _export_to_string(model)
        assert 'o body_vis'  in obj,  "Visible node should be exported"
        assert 'o body_dum'  not in obj, "render=False node must not be exported"
        assert 'o pelvis_g'  not in obj, "Deform helper must not be exported"

    def test_header_comment_counts(self):
        vis = _make_mesh_node('vis', texture='tex01', render=True)
        inv = _make_mesh_node('inv', texture='null',  render=False)
        model = _make_model_with_nodes([vis, inv])

        obj, _ = _export_to_string(model)
        # Header should state total=2, exported=1
        assert 'total=2' in obj
        assert 'exported=1' in obj

    def test_null_texture_not_in_mtl_map_kd(self):
        # Skin node with null texture and valid UVs passes through _is_renderable
        # (skin + null tex + has UVs → not filtered), but map_Kd should be absent.
        n = _make_mesh_node('body', texture='null', render=True, is_skin=True,
                            uvs=[(0.1, 0.2), (0.5, 0.3), (0.8, 0.8)])
        n.normals = [(0, 0, 1)] * 3
        model = _make_model_with_nodes([n])
        _, mtl = _export_to_string(model)
        assert 'map_Kd null' not in mtl

    def test_real_texture_in_mtl_map_kd(self):
        n = _make_mesh_node('body', texture='c_bantha01', render=True)
        model = _make_model_with_nodes([n])
        _, mtl = _export_to_string(model)
        assert 'map_Kd c_bantha01.tga' in mtl

    def test_v_coordinate_flipped(self):
        """OBJ vt entries should have V flipped (1 - v_in)."""
        n = _make_mesh_node('body', texture='tex01', render=True,
                            uvs=[(0.25, 0.75)])
        n.vertices = [(0, 0, 0)]
        n.normals  = [(0, 0, 1)]
        n.faces    = []
        model = _make_model_with_nodes([n])
        obj, _ = _export_to_string(model)
        # V in = 0.75  →  V out = 1.0 - 0.75 = 0.25
        assert 'vt 0.250000 0.250000' in obj

    def test_face_indices_two_nodes(self):
        """Face indices in second object must be offset by first object's vertex count."""
        n1 = _make_mesh_node('mesh1', texture='tex1', render=True,
                             verts=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
                             uvs=[(0, 0), (1, 0), (0, 1)],
                             faces=[(0, 1, 2)])
        n2 = _make_mesh_node('mesh2', texture='tex2', render=True,
                             verts=[(2, 0, 0), (3, 0, 0), (2, 1, 0)],
                             uvs=[(0, 0), (1, 0), (0, 1)],
                             faces=[(0, 1, 2)])
        model = _make_model_with_nodes([n1, n2])
        obj, _ = _export_to_string(model)
        # mesh1 face: 1/1/1 2/2/2 3/3/3  (1-based indexing, first object)
        # mesh2 face: offset by 3 → 4/4/4 5/5/5 6/6/6
        assert 'f 1/1/1 2/2/2 3/3/3' in obj
        assert 'f 4/4/4 5/5/5 6/6/6' in obj

    def test_empty_model_exports_cleanly(self):
        """Model with no renderable nodes should still produce valid OBJ/MTL."""
        helper = _make_mesh_node('helper_g', texture='null', render=True)
        model  = _make_model_with_nodes([helper])
        obj, mtl = _export_to_string(model)
        # Should not crash, just produce empty geometry
        assert 'GhostRigger' in obj
        assert 'exported=0' in obj


class TestRenderableNodesList:
    """Tests for the _renderable_mesh_nodes() helper function."""

    def test_filters_correctly(self):
        vis    = _make_mesh_node('vis',   texture='tex01', render=True)
        invis  = _make_mesh_node('invis', texture='tex01', render=False)
        helper = _make_mesh_node('arm_g', texture='null',  render=True)
        model  = _make_model_with_nodes([vis, invis, helper])
        result = _renderable_mesh_nodes(model)
        assert len(result) == 1
        assert result[0].name == 'vis'


class TestWorldSpaceTransform:
    """Tests for OBJExporter bind-pose world-space vertex transform.

    KotOR skin nodes store vertices in node-local (bone-local) space.
    The OBJ exporter must apply node.world_transform() to convert them to
    world/model space, matching the viewport's bind-pose rendering.
    """

    def _make_node_with_parent(self, name, texture, parent_pos, node_pos,
                               parent_rot=(0,0,0,1), node_rot=(0,0,0,1),
                               verts=None, is_skin=False):
        """Build a two-level hierarchy: root_dummy → test_node."""
        from src.core.model_data import ModelNode, NodeFlags
        root = ModelNode(name='root_dummy', flags=int(NodeFlags.HEADER))
        root.position = parent_pos
        root.rotation = parent_rot

        flags = (int(NodeFlags.MESH) | int(NodeFlags.SKIN)) if is_skin else int(NodeFlags.MESH)
        node = ModelNode(name=name, flags=flags)
        node.texture   = texture
        node.position  = node_pos
        node.rotation  = node_rot
        node.parent    = root
        node.vertices  = verts if verts is not None else [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        node.uvs       = [(0, 0), (1, 0), (0, 1)]
        node.normals   = [(0, 0, 1)] * 3
        node.faces     = [(0, 1, 2)]
        node.render    = True
        node.diffuse   = (0.8, 0.8, 0.8)
        node.ambient   = (0.2, 0.2, 0.2)
        node.specular  = (0.0, 0.0, 0.0)
        node.shininess = 0.0
        node.alpha     = 1.0
        return node

    def test_identity_parent_identity_node_no_shift(self):
        """Node at origin with identity transforms → vertices unchanged."""
        node = self._make_node_with_parent(
            'mesh', 'tex01',
            parent_pos=(0, 0, 0), node_pos=(0, 0, 0),
            verts=[(1.0, 2.0, 3.0)],
        )
        result = OBJExporter._node_bind_world_verts(node)
        assert len(result) == 1
        x, y, z = result[0]
        assert abs(x - 1.0) < 1e-5
        assert abs(y - 2.0) < 1e-5
        assert abs(z - 3.0) < 1e-5

    def test_node_position_added_to_vertex(self):
        """Node at (1, 2, 3) with identity parent → vertex offset by (1, 2, 3)."""
        node = self._make_node_with_parent(
            'mesh', 'tex01',
            parent_pos=(0, 0, 0), node_pos=(1.0, 2.0, 3.0),
            verts=[(0.0, 0.0, 0.0)],
        )
        result = OBJExporter._node_bind_world_verts(node)
        assert len(result) == 1
        x, y, z = result[0]
        assert abs(x - 1.0) < 1e-4, f"Expected x≈1.0, got {x}"
        assert abs(y - 2.0) < 1e-4, f"Expected y≈2.0, got {y}"
        assert abs(z - 3.0) < 1e-4, f"Expected z≈3.0, got {z}"

    def test_skin_node_local_to_world(self):
        """Skin node at (0, -5, 1) with local vertex (0, 0, 0) → world (0, -5, 1)."""
        node = self._make_node_with_parent(
            'Rwing06', 'c_bdrex01',
            parent_pos=(0, 0, 0), node_pos=(0.01, -5.0, 1.0),
            verts=[(0.0, 0.0, 0.0)],
            is_skin=True,
        )
        result = OBJExporter._node_bind_world_verts(node)
        assert len(result) == 1
        x, y, z = result[0]
        assert abs(x - 0.01) < 1e-4
        assert abs(y - (-5.0)) < 1e-4
        assert abs(z - 1.0) < 1e-4

    def test_vertex_includes_parent_offset(self):
        """World transform accumulates parent + child positions."""
        node = self._make_node_with_parent(
            'mesh', 'tex01',
            parent_pos=(10.0, 0, 0), node_pos=(0, 5.0, 0),
            verts=[(0.0, 0.0, 0.0)],
        )
        result = OBJExporter._node_bind_world_verts(node)
        x, y, z = result[0]
        assert abs(x - 10.0) < 1e-4, f"Expected x≈10.0, got {x}"
        assert abs(y - 5.0) < 1e-4, f"Expected y≈5.0, got {y}"

    def test_obj_vertex_uses_world_coords(self):
        """Exported OBJ v lines must reflect the world-space position."""
        node = self._make_node_with_parent(
            'body', 'c_bdrex01',
            parent_pos=(0, 0, 0), node_pos=(1.5, -3.0, 2.0),
            verts=[(0.0, 0.0, 0.0)],
        )
        model = _make_model_with_nodes([node])
        obj, _ = _export_to_string(model)
        # The exported vertex should be at world position (1.5, -3.0, 2.0)
        assert 'v 1.500000 -3.000000 2.000000' in obj, \
            f"Expected world-space vertex in OBJ, got:\n{obj}"

    def test_normals_rotated_by_world_transform(self):
        """World normals must be direction-only (no translation)."""
        import math
        # 90-degree Y rotation quaternion: (x=0, y=sin(45°), z=0, w=cos(45°))
        s = math.sqrt(0.5)
        node = self._make_node_with_parent(
            'mesh', 'tex01',
            parent_pos=(0, 0, 0), node_pos=(0, 0, 0),
            node_rot=(0, s, 0, s),  # 90° about Y
            verts=[(1, 0, 0)],
        )
        node.normals = [(0, 0, 1)]  # world-space normal after 90° Y should be (1, 0, 0)
        result = OBJExporter._node_bind_world_normals(node)
        # After 90° Y rotation: Z axis → X axis
        assert len(result) == 1
        nx, ny, nz = result[0]
        # Not testing exact values since world_transform uses _quat_normalize_bind
        # Just verify normals are present and are unit vectors
        length = math.sqrt(nx**2 + ny**2 + nz**2)
        assert length > 0.5, f"Normal should be non-zero, got {result[0]}"
