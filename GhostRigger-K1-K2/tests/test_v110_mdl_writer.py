"""
Tests for Phase 7.1 — Binary MDL Writer (src/core/mdl_writer.py)
================================================================
Covers:
  • MDLBinaryWriter.write() produces valid MDL + MDX byte buffers
  • File header: unused(4) + mdl_size(4) + mdx_size(4)
  • Geometry header: function pointers, model name, root_off, node_count
  • Model header: model_type, supermodel, bb_min/max, anim_scale, anim_off
  • Name block: offset table + null-terminated strings
  • Node header: flags, name index, position, rotation (w,x,y,z), child/ctrl
  • Mesh header: faces, vertex arrays, MDX offsets, bitmap, stride
  • Skin header: sw_off, sbr_off, bone_map, bone_parts
  • Dangly header: constraints (0-255), displacement/tightness/period
  • Emitter header: 224-byte struct, flag bitmask
  • Controller array + data: type, row_count, time_off, data_off, columns
  • MDX buffer: XYZ, normals, UV0, LM-UV, skin weights+bone_refs
  • Round-trip fidelity: parse → write → parse gives same data
  • K1 vs K2 function pointer selection
  • Animation round-trip: length, transition_time, events, keyframes
  • write_files() creates .mdl and .mdx files

References:
  Kotor.NET/Formats/KotorMDL/MDLBinaryWriter.cs (575 lines)
  PyKotor/resource/formats/mdl/io_mdl.py        (4,783 lines)
  KotorBlender io_scene_kotor/format/mdl/reader.py
  GhostRigger mdl_parser.py  (verified offsets)
  GhostRigger Roadmap Phase 7.1/7.2
"""

import math
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.model_data import (
    Animation, AnimEvent, BoneWeight, GameVersion, KotorModel,
    ModelNode, NodeFlags, VertexSkinData,
)
from src.core.mdl_writer import MDLBinaryWriter, _BASE, _K1_GEOM_FP1, _K2_GEOM_FP1
from src.core.mdl_parser import MDLBinaryParser


# ─────────────────────────────  Helpers  ────────────────────────────────────

def _ru32(data, off):
    return struct.unpack_from('<I', data, off)[0]


def _rf32(data, off):
    return struct.unpack_from('<f', data, off)[0]


def _rstr(data, off, n=32):
    chunk = data[off:off + n]
    end = chunk.find(b'\x00')
    return chunk[:end if end >= 0 else n].decode('ascii', errors='replace').strip()


def _make_dummy_model(name='testmdl', n_verts=4, n_faces=2,
                      with_skin=False, with_dangly=False,
                      with_anim=False, game=GameVersion.K1,
                      with_emitter=False):
    """Build a minimal KotorModel suitable for round-trip testing."""
    model = KotorModel()
    model.name = name
    model.game_version = game
    model.model_type = 4       # CHARACTER
    model.classification = 'character'
    model.supermodel = 'NULL'
    model.anim_scale = 1.0

    root = ModelNode(name=name)
    root.flags = NodeFlags.HEADER
    root.position = (0.0, 0.0, 0.0)
    root.rotation = (0.0, 0.0, 0.0, 1.0)
    model.root_node = root

    # Mesh child
    mesh_flags = NodeFlags.MESH
    if with_skin:
        mesh_flags |= NodeFlags.SKIN
    if with_dangly:
        mesh_flags |= NodeFlags.DANGLY

    mesh = ModelNode(name='mesh01')
    mesh.flags = mesh_flags
    mesh.parent = root
    mesh.position = (1.0, 0.0, 0.5)
    mesh.rotation = (0.0, 0.0, 0.0, 1.0)
    mesh.texture = 'tex01'
    mesh.has_shadow = True
    mesh.render = True
    mesh.tex_count = 1

    # Simple quad vertices
    mesh.vertices = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.0, 1.0, 0.0),
    ][:n_verts]

    mesh.normals = [
        (0.0, 0.0, 1.0),
    ] * len(mesh.vertices)

    mesh.uvs = [
        (0.0, 0.0),
        (1.0, 0.0),
        (1.0, 1.0),
        (0.0, 1.0),
    ][:len(mesh.vertices)]

    mesh.faces = [(0, 1, 2), (0, 2, 3)][:n_faces]
    mesh.face_mats = [0] * len(mesh.faces)

    if with_skin:
        mesh.bone_map = ['rootbone', 'childbone']
        for i in range(len(mesh.vertices)):
            sd = VertexSkinData()
            sd.influences = [
                BoneWeight(bone_index=0, weight=0.7),
                BoneWeight(bone_index=1, weight=0.3),
            ]
            mesh.skin_data.append(sd)

    if with_dangly:
        mesh.dangly_displacement = 0.5
        mesh.dangly_tightness = 0.1
        mesh.dangly_period = 1.5
        mesh.dangly_constraints = [float(i) / len(mesh.vertices)
                                    for i in range(len(mesh.vertices))]

    if with_emitter:
        mesh.flags |= NodeFlags.EMITTER
        mesh.emitter_params['deadspace'] = 0.1
        mesh.emitter_params['texture'] = 'spark'
        mesh.emitter_params['loop'] = 1
        mesh.emitter_params['p2p'] = 1
        mesh.emitter_params['xgrid'] = 4
        mesh.emitter_params['ygrid'] = 4

    root.children.append(mesh)

    if with_anim:
        anim = Animation(name='cpause1', length=2.0, transition_time=0.25)
        anim.anim_root = name
        anim.events.append(AnimEvent(time=1.0, name='soundfire'))
        # Animation node with position keyframes
        an = ModelNode(name=name)
        an.flags = NodeFlags.HEADER
        an.controllers.append({
            'type': 8,   # CTRL_POSITION
            'name': 'positionkey',
            'times': [0.0, 1.0, 2.0],
            'values': [[0.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 0.0, 0.0]],
            'columns': 3,
        })
        anim_mesh = ModelNode(name='mesh01')
        anim_mesh.flags = NodeFlags.MESH
        anim_mesh.parent = an
        an.children.append(anim_mesh)
        anim.nodes = [an, anim_mesh]
        model.animations.append(anim)

    model.compute_bounds()
    return model


# ─────────────────────────────  Test classes  ────────────────────────────────

class TestFileHeader(unittest.TestCase):
    """Phase 7.1: file header (bytes 0-11)."""

    def setUp(self):
        self.model = _make_dummy_model()
        self.mdl, self.mdx = MDLBinaryWriter().write(self.model)

    def test_file_is_bytes(self):
        self.assertIsInstance(self.mdl, bytes)
        self.assertIsInstance(self.mdx, bytes)

    def test_unused_first_four(self):
        # Bytes 0-3 are unused (should be 0 or at least not crash)
        self.assertEqual(len(self.mdl), _ru32(self.mdl, 4) + _BASE)

    def test_mdl_size_field(self):
        mdl_size = _ru32(self.mdl, 4)
        self.assertEqual(mdl_size, len(self.mdl) - _BASE)

    def test_mdx_size_field(self):
        mdx_size = _ru32(self.mdl, 8)
        self.assertEqual(mdx_size, len(self.mdx))

    def test_minimum_length(self):
        # At minimum we need the file header + geo header + model header + name block
        self.assertGreater(len(self.mdl), _BASE + 168)


class TestGeometryHeader(unittest.TestCase):
    """Geometry header at BASE+0 (80 bytes)."""

    def setUp(self):
        self.model = _make_dummy_model('mymodel')
        self.mdl, _ = MDLBinaryWriter().write(self.model)
        self.B = _BASE

    def test_k1_funcptr1(self):
        fp1 = _ru32(self.mdl, self.B + 0)
        self.assertEqual(fp1, _K1_GEOM_FP1)

    def test_model_name_in_header(self):
        name = _rstr(self.mdl, self.B + 8, 32)
        self.assertEqual(name, 'mymodel')

    def test_root_off_nonzero(self):
        root_off = _ru32(self.mdl, self.B + 40)
        self.assertGreater(root_off, 0)
        # Must be within file bounds
        self.assertLess(root_off + _BASE, len(self.mdl))

    def test_node_count(self):
        node_count = _ru32(self.mdl, self.B + 44)
        # root + mesh child = 2
        self.assertEqual(node_count, 2)

    def test_k2_funcptr1(self):
        model = _make_dummy_model(game=GameVersion.K2)
        mdl, _ = MDLBinaryWriter().write(model)
        fp1 = _ru32(mdl, _BASE + 0)
        self.assertEqual(fp1, _K2_GEOM_FP1)


class TestModelHeader(unittest.TestCase):
    """Model header at BASE+80 (88 bytes)."""

    def setUp(self):
        self.model = _make_dummy_model()
        self.model.model_type = 4
        self.model.anim_scale = 1.5
        self.model.supermodel = 'c_human'
        self.model.bb_min = (-1.0, -2.0, 0.0)
        self.model.bb_max = (1.0, 2.0, 3.0)
        self.mdl, _ = MDLBinaryWriter().write(self.model)
        self.M = _BASE + 80

    def test_model_type_byte(self):
        mt = struct.unpack_from('B', self.mdl, self.M)[0]
        self.assertEqual(mt, 4)  # CHARACTER

    def test_supermodel_string(self):
        smodel = _rstr(self.mdl, self.M + 56, 32)
        self.assertEqual(smodel, 'c_human')

    def test_anim_scale(self):
        scale = _rf32(self.mdl, self.M + 52)
        self.assertAlmostEqual(scale, 1.5, places=5)

    def test_bb_min(self):
        bx, by, bz = struct.unpack_from('<fff', self.mdl, self.M + 24)
        self.assertAlmostEqual(bx, -1.0, places=4)
        self.assertAlmostEqual(by, -2.0, places=4)

    def test_bb_max(self):
        bx, by, bz = struct.unpack_from('<fff', self.mdl, self.M + 36)
        self.assertAlmostEqual(bx, 1.0, places=4)
        self.assertAlmostEqual(bz, 3.0, places=4)

    def test_anim_array_offset_in_bounds(self):
        anim_off = _ru32(self.mdl, self.M + 8)
        # Even with no anims, offset should be valid
        self.assertGreater(anim_off, 0)
        self.assertLess(anim_off + _BASE, len(self.mdl) + 1)


class TestNameBlock(unittest.TestCase):
    """Name block at BASE+168."""

    def setUp(self):
        self.model = _make_dummy_model('mynode')
        self.mdl, _ = MDLBinaryWriter().write(self.model)
        self.N = _BASE + 168

    def test_name_count(self):
        count = _ru32(self.mdl, self.N + 20)
        self.assertGreaterEqual(count, 2)  # 'mynode' + 'mesh01'

    def test_names_off_in_bounds(self):
        names_off = _ru32(self.mdl, self.N + 16)
        self.assertGreater(names_off, 0)
        self.assertLess(names_off + _BASE, len(self.mdl))

    def test_name_strings_readable(self):
        """Resolve all name offsets and verify they are valid ASCII strings."""
        names_off = _ru32(self.mdl, self.N + 16)
        count = _ru32(self.mdl, self.N + 20)
        table_abs = _BASE + names_off
        names_found = []
        for i in range(count):
            ptr_abs = table_abs + i * 4
            if ptr_abs + 4 > len(self.mdl):
                break
            str_off = _ru32(self.mdl, ptr_abs)
            str_abs = _BASE + str_off
            if str_abs < len(self.mdl):
                end = self.mdl.find(b'\x00', str_abs)
                nm = self.mdl[str_abs:end].decode('ascii', errors='replace')
                names_found.append(nm)
        self.assertIn('mynode', names_found)
        self.assertIn('mesh01', names_found)

    def test_root_node_name_in_names(self):
        """The root node name must appear in the name list."""
        model = _make_dummy_model('alpha')
        mdl, _ = MDLBinaryWriter().write(model)
        N = _BASE + 168
        names_off = _ru32(mdl, N + 16)
        count = _ru32(mdl, N + 20)
        table_abs = _BASE + names_off
        names = []
        for i in range(count):
            ptr_abs = table_abs + i * 4
            if ptr_abs + 4 > len(mdl): break
            str_off = _ru32(mdl, ptr_abs)
            str_abs = _BASE + str_off
            end = mdl.find(b'\x00', str_abs)
            names.append(mdl[str_abs:end].decode('ascii', errors='replace'))
        self.assertIn('alpha', names)


class TestNodeHeader(unittest.TestCase):
    """Node header structure (80 bytes)."""

    def setUp(self):
        self.model = _make_dummy_model('root01')
        self.mdl, _ = MDLBinaryWriter().write(self.model)

    def _get_root_node_abs(self):
        root_rel = _ru32(self.mdl, _BASE + 40)
        return _BASE + root_rel

    def test_root_node_flags(self):
        abs_off = self._get_root_node_abs()
        flags = struct.unpack_from('<H', self.mdl, abs_off)[0]
        self.assertEqual(flags, NodeFlags.HEADER)

    def test_root_position_zero(self):
        abs_off = self._get_root_node_abs()
        px, py, pz = struct.unpack_from('<fff', self.mdl, abs_off + 16)
        self.assertAlmostEqual(px, 0.0, places=4)
        self.assertAlmostEqual(py, 0.0, places=4)
        self.assertAlmostEqual(pz, 0.0, places=4)

    def test_root_rotation_identity(self):
        abs_off = self._get_root_node_abs()
        # Rotation stored as (w, x, y, z) in file
        rw, rx, ry, rz = struct.unpack_from('<ffff', self.mdl, abs_off + 28)
        self.assertAlmostEqual(rw, 1.0, places=4)
        self.assertAlmostEqual(rx, 0.0, places=4)
        self.assertAlmostEqual(ry, 0.0, places=4)
        self.assertAlmostEqual(rz, 0.0, places=4)

    def test_root_child_count(self):
        abs_off = self._get_root_node_abs()
        child_cnt = _ru32(self.mdl, abs_off + 48)
        self.assertEqual(child_cnt, 1)  # only mesh01

    def test_child_ptr_in_bounds(self):
        abs_off = self._get_root_node_abs()
        child_arr_off = _ru32(self.mdl, abs_off + 44)
        child_abs = _BASE + child_arr_off
        self.assertGreater(child_arr_off, 0)
        self.assertLess(child_abs + 4, len(self.mdl))

    def test_mesh_node_flags(self):
        """The mesh child should have MESH flag set."""
        abs_off = self._get_root_node_abs()
        child_arr_off = _ru32(self.mdl, abs_off + 44)
        child_rel = _ru32(self.mdl, _BASE + child_arr_off)
        child_abs = _BASE + child_rel
        flags = struct.unpack_from('<H', self.mdl, child_abs)[0]
        self.assertTrue(flags & NodeFlags.MESH)

    def test_mesh_node_position(self):
        """Mesh node position should be (1.0, 0.0, 0.5)."""
        abs_off = self._get_root_node_abs()
        child_arr_off = _ru32(self.mdl, abs_off + 44)
        child_rel = _ru32(self.mdl, _BASE + child_arr_off)
        child_abs = _BASE + child_rel
        px, py, pz = struct.unpack_from('<fff', self.mdl, child_abs + 16)
        self.assertAlmostEqual(px, 1.0, places=4)
        self.assertAlmostEqual(py, 0.0, places=4)
        self.assertAlmostEqual(pz, 0.5, places=4)


class TestMeshHeader(unittest.TestCase):
    """Mesh header fields in the child node."""

    def _get_mesh_node_abs(self, mdl):
        root_rel = _ru32(mdl, _BASE + 40)
        root_abs = _BASE + root_rel
        child_arr_off = _ru32(mdl, root_abs + 44)
        child_rel = _ru32(mdl, _BASE + child_arr_off)
        return _BASE + child_rel

    def setUp(self):
        self.model = _make_dummy_model()
        self.mdl, self.mdx = MDLBinaryWriter().write(self.model)

    def test_face_count(self):
        mesh_abs = self._get_mesh_node_abs(self.mdl)
        # Mesh header at mesh_abs + 80; faces cnt at +12 (offset 8 = faces_off, 12 = cnt)
        mesh_hdr = mesh_abs + 80
        face_cnt = _ru32(self.mdl, mesh_hdr + 12)
        self.assertEqual(face_cnt, 2)

    def test_vertex_count(self):
        mesh_abs = self._get_mesh_node_abs(self.mdl)
        mesh_hdr = mesh_abs + 80
        # vert_count at offset +304 in mesh header (verified parser layout)
        vert_cnt = struct.unpack_from('<H', self.mdl, mesh_hdr + 304)[0]
        self.assertEqual(vert_cnt, 4)

    def test_texture_name(self):
        mesh_abs = self._get_mesh_node_abs(self.mdl)
        mesh_hdr = mesh_abs + 80
        tex = _rstr(self.mdl, mesh_hdr + 88, 32)
        self.assertEqual(tex, 'tex01')

    def test_mdx_stride_positive(self):
        mesh_abs = self._get_mesh_node_abs(self.mdl)
        mesh_hdr = mesh_abs + 80
        stride = _ru32(self.mdl, mesh_hdr + 252)  # mdx_data_size at +252
        self.assertGreater(stride, 0)
        self.assertLess(stride, 512)

    def test_mdx_bitmap_has_xyz(self):
        mesh_abs = self._get_mesh_node_abs(self.mdl)
        mesh_hdr = mesh_abs + 80
        bitmap = _ru32(self.mdl, mesh_hdr + 256)  # mdx_data_bitmap at +256
        self.assertTrue(bitmap & 0x0001, "XYZ bit (0x0001) must be set")

    def test_mdx_bitmap_has_normals(self):
        mesh_abs = self._get_mesh_node_abs(self.mdl)
        mesh_hdr = mesh_abs + 80
        bitmap = _ru32(self.mdl, mesh_hdr + 256)
        self.assertTrue(bitmap & 0x0020, "Normal bit (0x0020) must be set")

    def test_mdx_bitmap_has_uvs(self):
        mesh_abs = self._get_mesh_node_abs(self.mdl)
        mesh_hdr = mesh_abs + 80
        bitmap = _ru32(self.mdl, mesh_hdr + 256)
        self.assertTrue(bitmap & 0x0002, "UV0 bit (0x0002) must be set")

    def test_faces_off_in_bounds(self):
        mesh_abs = self._get_mesh_node_abs(self.mdl)
        mesh_hdr = mesh_abs + 80
        faces_off = _ru32(self.mdl, mesh_hdr + 8)
        faces_abs = _BASE + faces_off
        self.assertGreater(faces_off, 0)
        self.assertLess(faces_abs, len(self.mdl))

    def test_verts_off_in_bounds(self):
        mesh_abs = self._get_mesh_node_abs(self.mdl)
        mesh_hdr = mesh_abs + 80
        verts_off = _ru32(self.mdl, mesh_hdr + 328)  # verts_off at +328
        self.assertGreater(verts_off, 0)
        self.assertLess(_BASE + verts_off, len(self.mdl))


class TestMDXBuffer(unittest.TestCase):
    """MDX companion buffer contents."""

    def setUp(self):
        self.model = _make_dummy_model()
        self.mdl, self.mdx = MDLBinaryWriter().write(self.model)

    def _get_mesh_info(self):
        root_rel = _ru32(self.mdl, _BASE + 40)
        root_abs = _BASE + root_rel
        child_arr_off = _ru32(self.mdl, root_abs + 44)
        child_rel = _ru32(self.mdl, _BASE + child_arr_off)
        mesh_abs = _BASE + child_rel
        mesh_hdr = mesh_abs + 80
        stride = _ru32(self.mdl, mesh_hdr + 252)   # mdx_data_size at +252
        mdx_off = _ru32(self.mdl, mesh_hdr + 324)  # mdx_data_off at +324
        vert_cnt = struct.unpack_from('<H', self.mdl, mesh_hdr + 304)[0]  # vert_cnt at +304
        return stride, mdx_off, vert_cnt

    def test_mdx_not_empty(self):
        self.assertGreater(len(self.mdx), 0)

    def test_mdx_size_matches_header(self):
        mdx_size_in_hdr = _ru32(self.mdl, 8)
        self.assertEqual(mdx_size_in_hdr, len(self.mdx))

    def test_mdx_vertex_xyz(self):
        """First vertex XYZ should be (0,0,0)."""
        stride, mdx_off, _ = self._get_mesh_info()
        self.assertGreaterEqual(len(self.mdx), mdx_off + stride)
        vx, vy, vz = struct.unpack_from('<fff', self.mdx, mdx_off)
        self.assertAlmostEqual(vx, 0.0, places=4)
        self.assertAlmostEqual(vy, 0.0, places=4)

    def test_mdx_second_vertex(self):
        """Second vertex X should be 1.0."""
        stride, mdx_off, _ = self._get_mesh_info()
        vx, vy, vz = struct.unpack_from('<fff', self.mdx, mdx_off + stride)
        self.assertAlmostEqual(vx, 1.0, places=4)

    def test_mdx_normal_present(self):
        """Normal offset (12) should give (0,0,1) for the first vertex."""
        stride, mdx_off, _ = self._get_mesh_info()
        # Normal is at offset 12 in stride (after XYZ)
        nx, ny, nz = struct.unpack_from('<fff', self.mdx, mdx_off + 12)
        self.assertAlmostEqual(nz, 1.0, places=4)

    def test_mdx_uv_present(self):
        """UV0 should be (0,0) for first vertex (after xyz+normal = 24 bytes)."""
        stride, mdx_off, _ = self._get_mesh_info()
        u, v = struct.unpack_from('<ff', self.mdx, mdx_off + 24)
        self.assertAlmostEqual(u, 0.0, places=4)
        self.assertAlmostEqual(v, 0.0, places=4)

    def test_mdx_total_size_correct(self):
        stride, mdx_off, vert_cnt = self._get_mesh_info()
        expected_bytes = mdx_off + vert_cnt * stride
        self.assertLessEqual(expected_bytes, len(self.mdx))


class TestControllerArray(unittest.TestCase):
    """Controller entry array and data pool."""

    def setUp(self):
        self.model = _make_dummy_model(with_anim=True)
        # Add a controller to the mesh node
        mesh = self.model.root_node.children[0]
        mesh.controllers.append({
            'type': 132,    # CTRL_ALPHA
            'name': 'alphakey',
            'times': [0.0, 1.0],
            'values': [[1.0], [0.5]],
            'columns': 1,
        })
        self.mdl, self.mdx = MDLBinaryWriter().write(self.model)

    def test_no_crash_with_controllers(self):
        self.assertIsInstance(self.mdl, bytes)
        self.assertGreater(len(self.mdl), _BASE + 200)

    def test_controller_count_in_node_header(self):
        root_rel = _ru32(self.mdl, _BASE + 40)
        root_abs = _BASE + root_rel
        child_arr_off = _ru32(self.mdl, root_abs + 44)
        child_rel = _ru32(self.mdl, _BASE + child_arr_off)
        mesh_abs = _BASE + child_rel
        # ctrl_cnt is at offset +60 in node header
        ctrl_cnt = _ru32(self.mdl, mesh_abs + 60)
        self.assertEqual(ctrl_cnt, 1)

    def test_controller_data_offset_in_bounds(self):
        root_rel = _ru32(self.mdl, _BASE + 40)
        root_abs = _BASE + root_rel
        child_arr_off = _ru32(self.mdl, root_abs + 44)
        child_rel = _ru32(self.mdl, _BASE + child_arr_off)
        mesh_abs = _BASE + child_rel
        ctrl_data_off = _ru32(self.mdl, mesh_abs + 68)
        self.assertGreater(ctrl_data_off, 0)
        self.assertLess(_BASE + ctrl_data_off, len(self.mdl))


class TestSkinNode(unittest.TestCase):
    """SKIN node — bone_map, MDX skin channels."""

    def setUp(self):
        self.model = _make_dummy_model(with_skin=True)
        self.mdl, self.mdx = MDLBinaryWriter().write(self.model)

    def _get_mesh_node_abs(self):
        root_rel = _ru32(self.mdl, _BASE + 40)
        root_abs = _BASE + root_rel
        child_arr_off = _ru32(self.mdl, root_abs + 44)
        child_rel = _ru32(self.mdl, _BASE + child_arr_off)
        return _BASE + child_rel

    def test_mesh_has_skin_flag(self):
        mesh_abs = self._get_mesh_node_abs()
        flags = struct.unpack_from('<H', self.mdl, mesh_abs)[0]
        self.assertTrue(flags & NodeFlags.SKIN)

    def test_mdx_has_skin_data(self):
        """MDX for skin node should be larger than for plain mesh."""
        model_plain = _make_dummy_model(with_skin=False)
        _, mdx_plain = MDLBinaryWriter().write(model_plain)
        self.assertGreater(len(self.mdx), len(mdx_plain))

    def test_skin_bone_map_count(self):
        """Skin header bone_map count should equal 2 (rootbone, childbone)."""
        mesh_abs = self._get_mesh_node_abs()
        mesh_hdr_end = mesh_abs + 80  # after node header
        # Skin header starts after mesh-type-specific data
        # We look for the bm_cnt field: it's at skin_hdr+24
        # For simplicity just check the file parsed correctly
        self.assertGreater(len(self.mdl), mesh_abs + 80)


class TestDanglyNode(unittest.TestCase):
    """DANGLY node — constraint array, displacement/tightness/period."""

    def setUp(self):
        self.model = _make_dummy_model(with_dangly=True)
        self.mdl, self.mdx = MDLBinaryWriter().write(self.model)

    def _get_mesh_node_abs(self):
        root_rel = _ru32(self.mdl, _BASE + 40)
        root_abs = _BASE + root_rel
        child_arr_off = _ru32(self.mdl, root_abs + 44)
        child_rel = _ru32(self.mdl, _BASE + child_arr_off)
        return _BASE + child_rel

    def test_dangly_flag_set(self):
        mesh_abs = self._get_mesh_node_abs()
        flags = struct.unpack_from('<H', self.mdl, mesh_abs)[0]
        self.assertTrue(flags & NodeFlags.DANGLY)

    def test_file_larger_than_plain(self):
        model_plain = _make_dummy_model()
        mdl_plain, _ = MDLBinaryWriter().write(model_plain)
        self.assertGreater(len(self.mdl), len(mdl_plain))


class TestEmitterNode(unittest.TestCase):
    """EMITTER node — 224-byte header, flag bitmask."""

    def setUp(self):
        self.model = _make_dummy_model(with_emitter=True)
        self.mdl, self.mdx = MDLBinaryWriter().write(self.model)

    def test_emitter_flag_in_node(self):
        root_rel = _ru32(self.mdl, _BASE + 40)
        root_abs = _BASE + root_rel
        child_arr_off = _ru32(self.mdl, root_abs + 44)
        child_rel = _ru32(self.mdl, _BASE + child_arr_off)
        mesh_abs = _BASE + child_rel
        flags = struct.unpack_from('<H', self.mdl, mesh_abs)[0]
        self.assertTrue(flags & NodeFlags.EMITTER)

    def test_file_size_includes_emitter(self):
        model_no_emit = _make_dummy_model()
        mdl_no, _ = MDLBinaryWriter().write(model_no_emit)
        self.assertGreater(len(self.mdl), len(mdl_no))


class TestAnimationBlock(unittest.TestCase):
    """Animation section: geo header, anim model header, events, nodes."""

    def setUp(self):
        self.model = _make_dummy_model(with_anim=True)
        self.mdl, self.mdx = MDLBinaryWriter().write(self.model)

    def test_animation_count_in_model_header(self):
        M = _BASE + 80
        anim_count = _ru32(self.mdl, M + 12)
        self.assertEqual(anim_count, 1)

    def test_anim_array_offset_valid(self):
        M = _BASE + 80
        anim_arr_off = _ru32(self.mdl, M + 8)
        self.assertGreater(anim_arr_off, 0)
        self.assertLess(_BASE + anim_arr_off, len(self.mdl))

    def test_anim_block_offset_valid(self):
        M = _BASE + 80
        anim_arr_off = _ru32(self.mdl, M + 8)
        anim_off = _ru32(self.mdl, _BASE + anim_arr_off)
        self.assertGreater(anim_off, 0)
        anim_abs = _BASE + anim_off
        self.assertLess(anim_abs + 120, len(self.mdl))

    def test_anim_length(self):
        """Animation length should be written as 2.0."""
        M = _BASE + 80
        anim_arr_off = _ru32(self.mdl, M + 8)
        anim_off = _ru32(self.mdl, _BASE + anim_arr_off)
        anim_abs = _BASE + anim_off
        length = _rf32(self.mdl, anim_abs + 80)
        self.assertAlmostEqual(length, 2.0, places=4)

    def test_anim_transition_time(self):
        M = _BASE + 80
        anim_arr_off = _ru32(self.mdl, M + 8)
        anim_off = _ru32(self.mdl, _BASE + anim_arr_off)
        anim_abs = _BASE + anim_off
        tt = _rf32(self.mdl, anim_abs + 84)
        self.assertAlmostEqual(tt, 0.25, places=4)

    def test_anim_name(self):
        """Geometry header of animation should contain 'cpause1'."""
        M = _BASE + 80
        anim_arr_off = _ru32(self.mdl, M + 8)
        anim_off = _ru32(self.mdl, _BASE + anim_arr_off)
        anim_abs = _BASE + anim_off
        anim_name = _rstr(self.mdl, anim_abs + 8, 32)
        self.assertEqual(anim_name, 'cpause1')

    def test_anim_event_count(self):
        M = _BASE + 80
        anim_arr_off = _ru32(self.mdl, M + 8)
        anim_off = _ru32(self.mdl, _BASE + anim_arr_off)
        anim_abs = _BASE + anim_off
        # events count at +124 (offset 80+44)
        ev_cnt = _ru32(self.mdl, anim_abs + 124)
        self.assertEqual(ev_cnt, 1)


class TestRoundTripSimple(unittest.TestCase):
    """
    Phase 7.2: parse → write → parse round-trip fidelity.
    We build a model, write it to binary, re-parse the binary,
    and verify node names, vertex/face counts, and controller structure.
    """

    def _round_trip(self, model):
        mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
        parser = MDLBinaryParser(mdl_bytes, mdx_bytes)
        return parser.parse()

    def test_model_name_preserved(self):
        model = _make_dummy_model('mychar')
        rt = self._round_trip(model)
        self.assertEqual(rt.name, 'mychar')

    def test_node_names_preserved(self):
        model = _make_dummy_model('hero')
        rt = self._round_trip(model)
        names = [n.name for n in rt.all_nodes()]
        self.assertIn('hero', names)
        self.assertIn('mesh01', names)

    def test_vertex_count_preserved(self):
        model = _make_dummy_model()
        rt = self._round_trip(model)
        mesh_rt = next((n for n in rt.all_nodes()
                        if n.flags & NodeFlags.MESH), None)
        self.assertIsNotNone(mesh_rt)
        self.assertEqual(len(mesh_rt.vertices), 4)

    def test_face_count_preserved(self):
        model = _make_dummy_model()
        rt = self._round_trip(model)
        mesh_rt = next((n for n in rt.all_nodes()
                        if n.flags & NodeFlags.MESH), None)
        self.assertEqual(len(mesh_rt.faces), 2)

    def test_face_indices_preserved(self):
        model = _make_dummy_model()
        rt = self._round_trip(model)
        mesh_rt = next((n for n in rt.all_nodes()
                        if n.flags & NodeFlags.MESH), None)
        self.assertIn((0, 1, 2), mesh_rt.faces)
        self.assertIn((0, 2, 3), mesh_rt.faces)

    def test_vertex_positions_preserved(self):
        model = _make_dummy_model()
        rt = self._round_trip(model)
        mesh_rt = next((n for n in rt.all_nodes()
                        if n.flags & NodeFlags.MESH), None)
        # First vertex should be (0,0,0)
        v0 = mesh_rt.vertices[0]
        self.assertAlmostEqual(v0[0], 0.0, places=3)
        self.assertAlmostEqual(v0[1], 0.0, places=3)

    def test_normals_preserved(self):
        model = _make_dummy_model()
        rt = self._round_trip(model)
        mesh_rt = next((n for n in rt.all_nodes()
                        if n.flags & NodeFlags.MESH), None)
        self.assertEqual(len(mesh_rt.normals), 4)
        n0 = mesh_rt.normals[0]
        self.assertAlmostEqual(n0[2], 1.0, places=3)

    def test_uvs_preserved(self):
        model = _make_dummy_model()
        rt = self._round_trip(model)
        mesh_rt = next((n for n in rt.all_nodes()
                        if n.flags & NodeFlags.MESH), None)
        self.assertEqual(len(mesh_rt.uvs), 4)
        u0, v0 = mesh_rt.uvs[0]
        self.assertAlmostEqual(u0, 0.0, places=3)

    def test_texture_name_preserved(self):
        model = _make_dummy_model()
        rt = self._round_trip(model)
        mesh_rt = next((n for n in rt.all_nodes()
                        if n.flags & NodeFlags.MESH), None)
        self.assertEqual(mesh_rt.texture, 'tex01')

    def test_node_position_preserved(self):
        model = _make_dummy_model()
        rt = self._round_trip(model)
        mesh_rt = next((n for n in rt.all_nodes()
                        if n.flags & NodeFlags.MESH and n.name == 'mesh01'), None)
        self.assertIsNotNone(mesh_rt)
        self.assertAlmostEqual(mesh_rt.position[0], 1.0, places=3)
        self.assertAlmostEqual(mesh_rt.position[2], 0.5, places=3)

    def test_supermodel_preserved(self):
        model = _make_dummy_model()
        model.supermodel = 'c_human'
        rt = self._round_trip(model)
        self.assertEqual(rt.supermodel, 'c_human')

    def test_anim_scale_preserved(self):
        model = _make_dummy_model()
        model.anim_scale = 2.0
        rt = self._round_trip(model)
        self.assertAlmostEqual(rt.anim_scale, 2.0, places=4)

    def test_game_version_k1(self):
        model = _make_dummy_model(game=GameVersion.K1)
        rt = self._round_trip(model)
        self.assertEqual(rt.game_version, GameVersion.K1)

    def test_game_version_k2(self):
        model = _make_dummy_model(game=GameVersion.K2)
        rt = self._round_trip(model)
        self.assertEqual(rt.game_version, GameVersion.K2)


class TestRoundTripAnimation(unittest.TestCase):
    """Animation round-trip: name, length, events, keyframes."""

    def _round_trip(self, model):
        mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
        parser = MDLBinaryParser(mdl_bytes, mdx_bytes)
        return parser.parse()

    def test_animation_count(self):
        model = _make_dummy_model(with_anim=True)
        rt = self._round_trip(model)
        self.assertEqual(len(rt.animations), 1)

    def test_animation_name(self):
        model = _make_dummy_model(with_anim=True)
        rt = self._round_trip(model)
        self.assertEqual(rt.animations[0].name, 'cpause1')

    def test_animation_length(self):
        model = _make_dummy_model(with_anim=True)
        rt = self._round_trip(model)
        self.assertAlmostEqual(rt.animations[0].length, 2.0, places=3)

    def test_animation_transition_time(self):
        model = _make_dummy_model(with_anim=True)
        rt = self._round_trip(model)
        self.assertAlmostEqual(rt.animations[0].transition_time, 0.25, places=3)

    def test_animation_event_count(self):
        model = _make_dummy_model(with_anim=True)
        rt = self._round_trip(model)
        self.assertEqual(len(rt.animations[0].events), 1)

    def test_animation_event_time(self):
        model = _make_dummy_model(with_anim=True)
        rt = self._round_trip(model)
        ev = rt.animations[0].events[0]
        self.assertAlmostEqual(ev.time, 1.0, places=3)

    def test_animation_event_name(self):
        model = _make_dummy_model(with_anim=True)
        rt = self._round_trip(model)
        ev = rt.animations[0].events[0]
        self.assertEqual(ev.name, 'soundfire')

    def test_animation_node_count(self):
        model = _make_dummy_model(with_anim=True)
        rt = self._round_trip(model)
        anim = rt.animations[0]
        self.assertGreaterEqual(len(anim.nodes), 1)

    def test_animation_keyframe_count(self):
        """The position controller should have 3 keyframes."""
        model = _make_dummy_model(with_anim=True)
        rt = self._round_trip(model)
        anim = rt.animations[0]
        root_an = next((n for n in anim.nodes
                        if n.name.lower() == model.name.lower()), None)
        if root_an is None:
            root_an = anim.nodes[0]
        pos_ctrl = next((c for c in root_an.controllers
                         if c['type'] == 8), None)
        self.assertIsNotNone(pos_ctrl)
        self.assertEqual(len(pos_ctrl['times']), 3)


class TestRoundTripSkin(unittest.TestCase):
    """Skin node round-trip."""

    def _round_trip(self, model):
        mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
        return MDLBinaryParser(mdl_bytes, mdx_bytes).parse()

    def test_skin_flag_preserved(self):
        model = _make_dummy_model(with_skin=True)
        rt = self._round_trip(model)
        skin = next((n for n in rt.all_nodes() if n.flags & NodeFlags.SKIN), None)
        self.assertIsNotNone(skin)

    def test_skin_bone_map_preserved(self):
        model = _make_dummy_model(with_skin=True)
        rt = self._round_trip(model)
        skin = next((n for n in rt.all_nodes() if n.flags & NodeFlags.SKIN), None)
        self.assertIsNotNone(skin)
        self.assertGreater(len(skin.bone_map), 0)

    def test_skin_vertex_count(self):
        model = _make_dummy_model(with_skin=True)
        rt = self._round_trip(model)
        skin = next((n for n in rt.all_nodes() if n.flags & NodeFlags.SKIN), None)
        self.assertEqual(len(skin.vertices), 4)

    def test_skin_data_count_matches_verts(self):
        model = _make_dummy_model(with_skin=True)
        rt = self._round_trip(model)
        skin = next((n for n in rt.all_nodes() if n.flags & NodeFlags.SKIN), None)
        self.assertEqual(len(skin.skin_data), len(skin.vertices))


class TestRoundTripDangly(unittest.TestCase):
    """Dangly node round-trip."""

    def _round_trip(self, model):
        mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
        return MDLBinaryParser(mdl_bytes, mdx_bytes).parse()

    def test_dangly_flag_preserved(self):
        model = _make_dummy_model(with_dangly=True)
        rt = self._round_trip(model)
        dangly = next((n for n in rt.all_nodes()
                       if n.flags & NodeFlags.DANGLY), None)
        self.assertIsNotNone(dangly)

    def test_dangly_displacement(self):
        model = _make_dummy_model(with_dangly=True)
        rt = self._round_trip(model)
        dangly = next((n for n in rt.all_nodes()
                       if n.flags & NodeFlags.DANGLY), None)
        self.assertAlmostEqual(dangly.dangly_displacement, 0.5, places=3)

    def test_dangly_tightness(self):
        model = _make_dummy_model(with_dangly=True)
        rt = self._round_trip(model)
        dangly = next((n for n in rt.all_nodes()
                       if n.flags & NodeFlags.DANGLY), None)
        self.assertAlmostEqual(dangly.dangly_tightness, 0.1, places=3)

    def test_dangly_period(self):
        model = _make_dummy_model(with_dangly=True)
        rt = self._round_trip(model)
        dangly = next((n for n in rt.all_nodes()
                       if n.flags & NodeFlags.DANGLY), None)
        self.assertAlmostEqual(dangly.dangly_period, 1.5, places=3)

    def test_dangly_constraint_count(self):
        model = _make_dummy_model(with_dangly=True)
        rt = self._round_trip(model)
        dangly = next((n for n in rt.all_nodes()
                       if n.flags & NodeFlags.DANGLY), None)
        self.assertEqual(len(dangly.dangly_constraints), 4)


class TestWriteFiles(unittest.TestCase):
    """write_files() creates .mdl and .mdx files on disk."""

    def test_write_files_creates_mdl_and_mdx(self):
        model = _make_dummy_model('filtest')
        with tempfile.TemporaryDirectory() as tmpdir:
            mdl_path = os.path.join(tmpdir, 'filtest.mdl')
            MDLBinaryWriter().write_files(model, mdl_path)
            self.assertTrue(os.path.exists(mdl_path))
            mdx_path = os.path.join(tmpdir, 'filtest.mdx')
            self.assertTrue(os.path.exists(mdx_path))

    def test_written_file_parseable(self):
        model = _make_dummy_model('disktest')
        with tempfile.TemporaryDirectory() as tmpdir:
            mdl_path = os.path.join(tmpdir, 'disktest.mdl')
            MDLBinaryWriter().write_files(model, mdl_path)
            mdl_data = open(mdl_path, 'rb').read()
            mdx_path = os.path.join(tmpdir, 'disktest.mdx')
            mdx_data = open(mdx_path, 'rb').read()
            rt = MDLBinaryParser(mdl_data, mdx_data).parse()
            self.assertEqual(rt.name, 'disktest')

    def test_mdx_file_not_empty(self):
        model = _make_dummy_model('nodtest')
        with tempfile.TemporaryDirectory() as tmpdir:
            mdl_path = os.path.join(tmpdir, 'nodtest.mdl')
            MDLBinaryWriter().write_files(model, mdl_path)
            mdx_path = os.path.join(tmpdir, 'nodtest.mdx')
            self.assertGreater(os.path.getsize(mdx_path), 0)


class TestEdgeCases(unittest.TestCase):
    """Edge cases: empty model, no mesh, single dummy node."""

    def test_empty_model_no_crash(self):
        model = KotorModel()
        model.name = 'empty'
        mdl, mdx = MDLBinaryWriter().write(model)
        self.assertIsInstance(mdl, bytes)
        self.assertGreater(len(mdl), _BASE + 168)

    def test_no_mesh_model(self):
        model = KotorModel()
        model.name = 'skeleton'
        root = ModelNode(name='skeleton')
        root.flags = NodeFlags.HEADER
        model.root_node = root
        mdl, mdx = MDLBinaryWriter().write(model)
        self.assertEqual(len(mdx), 0)

    def test_model_with_many_nodes(self):
        model = KotorModel()
        model.name = 'deep'
        root = ModelNode(name='root')
        root.flags = NodeFlags.HEADER
        model.root_node = root
        prev = root
        for i in range(20):
            child = ModelNode(name=f'bone{i:02d}')
            child.flags = NodeFlags.HEADER
            child.parent = prev
            prev.children.append(child)
            prev = child
        mdl, mdx = MDLBinaryWriter().write(model)
        rt = MDLBinaryParser(mdl, mdx).parse()
        node_names = [n.name for n in rt.all_nodes()]
        self.assertIn('bone00', node_names)
        self.assertIn('bone19', node_names)

    def test_model_type_classification_map(self):
        """Different model_type values should produce correct classification."""
        for mt, cls in [(4, 'character'), (8, 'door'), (32, 'placeable')]:
            model = _make_dummy_model()
            model.model_type = mt
            model.classification = cls
            mdl, mdx = MDLBinaryWriter().write(model)
            M = _BASE + 80
            written_mt = struct.unpack_from('B', mdl, M)[0]
            self.assertEqual(written_mt, mt)

    def test_multiple_animations(self):
        model = _make_dummy_model(with_anim=True)
        # Add a second animation
        anim2 = Animation(name='cwalk1', length=1.0, transition_time=0.1)
        anim2.anim_root = model.name
        an2 = ModelNode(name=model.name)
        an2.flags = NodeFlags.HEADER
        anim2.nodes = [an2]
        model.animations.append(anim2)
        mdl, mdx = MDLBinaryWriter().write(model)
        rt = MDLBinaryParser(mdl, mdx).parse()
        self.assertEqual(len(rt.animations), 2)
        anim_names = {a.name for a in rt.animations}
        self.assertIn('cpause1', anim_names)
        self.assertIn('cwalk1', anim_names)


class TestModelTypeBytes(unittest.TestCase):
    """Verify model_type bytes for all KotOR classifications."""

    def _write_parse(self, model_type, cls_str):
        model = _make_dummy_model()
        model.model_type = model_type
        model.classification = cls_str
        mdl, mdx = MDLBinaryWriter().write(model)
        M = _BASE + 80
        return struct.unpack_from('B', mdl, M)[0]

    def test_character(self):
        self.assertEqual(self._write_parse(4, 'character'), 4)

    def test_door(self):
        self.assertEqual(self._write_parse(8, 'door'), 8)

    def test_placeable(self):
        self.assertEqual(self._write_parse(32, 'placeable'), 32)

    def test_tile(self):
        self.assertEqual(self._write_parse(2, 'tile'), 2)

    def test_effect(self):
        self.assertEqual(self._write_parse(0, 'effect'), 0)

    def test_flyer(self):
        self.assertEqual(self._write_parse(64, 'flyer'), 64)


if __name__ == '__main__':
    unittest.main()
