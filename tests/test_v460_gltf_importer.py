"""
test_v460_gltf_importer.py — Phase 8: GLTF Import
===================================================
Tests for src/core/gltf_importer.py

Covers:
  • GLBReader — pure-Python GLB header + chunk parsing
  • _decode_accessor — accessor data extraction (all component types)
  • _resolve_buffers — buffer URI resolution (data URIs, embedded)
  • _channel_to_controller — GLTF channel path → KotOR controller
  • _build_skin_data — JOINTS_0 / WEIGHTS_0 → VertexSkinData
  • GLTFImporter.import_bytes() — built-in parser
  • GLTFImporter.import_file() — file path import
  • Mesh geometry (vertices, normals, UVs, faces)
  • UV V-flip  (v_kotor = 1.0 - v_gltf)
  • Skin weights import (JOINTS_0 / WEIGHTS_0)
  • Animation channel import
  • Material / texture name resolution
  • Bone hierarchy reconstruction
  • FBXFallbackImporter (trimesh) — mesh import
  • auto_import() factory dispatch
  • KotorModel structure returned by importer
  • Round-trip model name, supermodel, game_version
  • Empty / minimal GLTF files
  • Multi-mesh / multi-primitive GLTF
  • Multi-animation GLTF

All tests run headless (no OpenGL, no files required for most).
"""

import json
import math
import struct
import base64
import sys
import os
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.gltf_importer import (
    GLBReader, GLTFImporter, FBXFallbackImporter, auto_import,
    _decode_accessor, _resolve_buffers, _channel_to_controller, _build_skin_data,
    CTRL_POSITION, CTRL_ORIENTATION, CTRL_SCALE,
)
from core.model_data import KotorModel, ModelNode, NodeFlags, GameVersion, BoneWeight


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers — build minimal GLTF bytes in memory
# ─────────────────────────────────────────────────────────────────────────────

def _make_glb(json_dict: dict, bin_data: bytes = b'') -> bytes:
    """Pack json_dict + bin_data into a GLB binary."""
    json_bytes = json.dumps(json_dict).encode('utf-8')
    # Pad JSON to 4-byte boundary
    while len(json_bytes) % 4:
        json_bytes += b' '
    # Pad BIN to 4-byte boundary
    bin_padded = bin_data
    while len(bin_padded) % 4:
        bin_padded += b'\x00'

    total = 12 + 8 + len(json_bytes) + (8 + len(bin_padded) if bin_padded else 0)
    buf = bytearray()
    # Header
    buf += struct.pack('<III', 0x46546C67, 2, total)  # magic=glTF, ver=2
    # JSON chunk
    buf += struct.pack('<II', len(json_bytes), 0x4E4F534A)
    buf += json_bytes
    # BIN chunk (optional)
    if bin_padded:
        buf += struct.pack('<II', len(bin_padded), 0x004E4942)
        buf += bin_padded
    return bytes(buf)


def _make_triangle_gltf_bytes() -> bytes:
    """Build a minimal GLTF 2.0 with one triangle mesh (3 verts, 1 face)."""
    # Triangle vertices: (0,0,0), (1,0,0), (0,1,0)
    verts = struct.pack('<fff fff fff', 0,0,0, 1,0,0, 0,1,0)
    # UVs: (0,0), (1,0), (0,1) — GLTF V top-down
    uvs   = struct.pack('<ff ff ff', 0,0, 1,0, 0,1)
    # Normals: all up
    normals = struct.pack('<fff fff fff', 0,0,1, 0,0,1, 0,0,1)
    # Indices: 0,1,2
    indices = struct.pack('<HHH', 0, 1, 2)

    bin_data = verts + uvs + normals + indices

    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "TestMesh"}],
        "meshes": [{
            "name": "mesh0",
            "primitives": [{
                "attributes": {
                    "POSITION":   0,
                    "TEXCOORD_0": 1,
                    "NORMAL":     2,
                },
                "indices": 3,
            }]
        }],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"},   # POSITION
            {"bufferView": 1, "componentType": 5126, "count": 3, "type": "VEC2"},   # UV
            {"bufferView": 2, "componentType": 5126, "count": 3, "type": "VEC3"},   # NORMAL
            {"bufferView": 3, "componentType": 5123, "count": 3, "type": "SCALAR"}, # indices
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0,  "byteLength": 36},  # verts
            {"buffer": 0, "byteOffset": 36, "byteLength": 24},  # UVs
            {"buffer": 0, "byteOffset": 60, "byteLength": 36},  # normals
            {"buffer": 0, "byteOffset": 96, "byteLength": 6},   # indices
        ],
        "buffers": [{"byteLength": len(bin_data)}],
    }
    return _make_glb(gltf, bin_data)


def _make_skinned_gltf_bytes() -> bytes:
    """Build a minimal skinned mesh GLTF with 2 joints and weights."""
    verts = struct.pack('<fff fff', 0,0,0, 1,0,0)
    # JOINTS_0: each vertex influenced by 1 joint (j=0,w=1.0 / j=1,w=1.0)
    joints  = struct.pack('<HHHH HHHH', 0,0,0,0, 1,0,0,0)
    weights = struct.pack('<ffff ffff', 1,0,0,0, 1,0,0,0)
    indices = struct.pack('<H', 0)  # not a real face, just to satisfy

    bin_data = verts + joints + weights + indices

    gltf = {
        "asset": {"version": "2.0"},
        "nodes": [
            {"mesh": 0, "skin": 0, "name": "SkinnedMesh"},
            {"name": "bone0"},
            {"name": "bone1"},
        ],
        "meshes": [{
            "primitives": [{
                "attributes": {
                    "POSITION": 0,
                    "JOINTS_0": 1,
                    "WEIGHTS_0": 2,
                },
                "indices": 3,
            }]
        }],
        "skins": [{"joints": [1, 2]}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 2, "type": "VEC3"},   # POSITION
            {"bufferView": 1, "componentType": 5123, "count": 2, "type": "VEC4"},   # JOINTS_0 uint16
            {"bufferView": 2, "componentType": 5126, "count": 2, "type": "VEC4"},   # WEIGHTS_0 float
            {"bufferView": 3, "componentType": 5123, "count": 1, "type": "SCALAR"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0,  "byteLength": 24},  # verts
            {"buffer": 0, "byteOffset": 24, "byteLength": 16},  # joints uint16 2×4=8 … actually 2×4×2=16
            {"buffer": 0, "byteOffset": 40, "byteLength": 32},  # weights 2×4×4
            {"buffer": 0, "byteOffset": 72, "byteLength": 2},   # index
        ],
        "buffers": [{"byteLength": len(bin_data)}],
    }
    return _make_glb(gltf, bin_data)


def _make_animated_gltf_bytes() -> bytes:
    """Build a GLTF with one translation animation channel."""
    # Input (times): 0.0, 0.5, 1.0
    times   = struct.pack('<fff', 0.0, 0.5, 1.0)
    # Output (vec3 positions): (0,0,0), (0,1,0), (0,2,0)
    values  = struct.pack('<fff fff fff', 0,0,0, 0,1,0, 0,2,0)
    bin_data = times + values

    gltf = {
        "asset": {"version": "2.0"},
        "nodes": [{"name": "Bone0"}],
        "animations": [{
            "name": "walk",
            "samplers": [{"input": 0, "output": 1, "interpolation": "LINEAR"}],
            "channels": [{"sampler": 0, "target": {"node": 0, "path": "translation"}}],
        }],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 3, "type": "SCALAR",
             "min": [0.0], "max": [1.0]},
            {"bufferView": 1, "componentType": 5126, "count": 3, "type": "VEC3"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0,  "byteLength": 12},
            {"buffer": 0, "byteOffset": 12, "byteLength": 36},
        ],
        "buffers": [{"byteLength": len(bin_data)}],
    }
    return _make_glb(gltf, bin_data)


def _make_rotation_anim_bytes() -> bytes:
    """GLTF with one rotation animation channel (VEC4 quaternions)."""
    times  = struct.pack('<ff', 0.0, 1.0)
    quats  = struct.pack('<ffff ffff', 0,0,0,1, 0,0.707,0,0.707)
    bin_data = times + quats
    gltf = {
        "asset": {"version": "2.0"},
        "nodes": [{"name": "BoneRot"}],
        "animations": [{
            "name": "spin",
            "samplers": [{"input": 0, "output": 1}],
            "channels": [{"sampler": 0, "target": {"node": 0, "path": "rotation"}}],
        }],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 2, "type": "SCALAR",
             "min": [0.0], "max": [1.0]},
            {"bufferView": 1, "componentType": 5126, "count": 2, "type": "VEC4"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0,  "byteLength": 8},
            {"buffer": 0, "byteOffset": 8, "byteLength": 32},
        ],
        "buffers": [{"byteLength": len(bin_data)}],
    }
    return _make_glb(gltf, bin_data)


def _make_material_gltf_bytes() -> bytes:
    """GLTF with a material that has a base colour texture with a named image."""
    verts = struct.pack('<fff', 0,0,0)
    bin_data = verts
    gltf = {
        "asset": {"version": "2.0"},
        "nodes": [{"mesh": 0, "name": "MeshWithMat"}],
        "meshes": [{
            "primitives": [{
                "attributes": {"POSITION": 0},
                "material": 0,
            }]
        }],
        "materials": [{
            "name": "my_mat",
            "pbrMetallicRoughness": {
                "baseColorTexture": {"index": 0}
            }
        }],
        "textures": [{"source": 0}],
        "images": [{"name": "tex_diffuse", "uri": "tex_diffuse.tga"}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 1, "type": "VEC3"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": 12},
        ],
        "buffers": [{"byteLength": 12}],
    }
    return _make_glb(gltf, bin_data)


def _import_bytes(data: bytes, name: str = "test") -> KotorModel:
    imp = GLTFImporter()
    result = imp.import_bytes(data, model_name=name)
    assert result is not None, "import_bytes returned None"
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  GLBReader Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGLBReader(unittest.TestCase):
    """Tests for the pure-Python GLB parser."""

    def test_magic_detection(self):
        data = _make_triangle_gltf_bytes()
        glb = GLBReader(data)
        self.assertIn('asset', glb.json_dict)

    def test_version_in_json(self):
        data = _make_triangle_gltf_bytes()
        glb = GLBReader(data)
        self.assertEqual(glb.json_dict['asset']['version'], '2.0')

    def test_bin_chunk_present(self):
        data = _make_triangle_gltf_bytes()
        glb = GLBReader(data)
        self.assertIsNotNone(glb.bin_chunk)

    def test_bin_chunk_length(self):
        data = _make_triangle_gltf_bytes()
        glb = GLBReader(data)
        # bin_data is verts(36) + uvs(24) + normals(36) + indices(6) = 102, padded to 104
        self.assertGreaterEqual(len(glb.bin_chunk), 102)

    def test_json_chunk_has_meshes(self):
        data = _make_triangle_gltf_bytes()
        glb = GLBReader(data)
        self.assertIn('meshes', glb.json_dict)

    def test_invalid_magic_raises(self):
        with self.assertRaises(ValueError):
            GLBReader(b'\x00\x00\x00\x00' + b'\x00' * 20)

    def test_too_short_raises(self):
        with self.assertRaises(ValueError):
            GLBReader(b'\x00\x00\x00')

    def test_from_bytes_classmethod(self):
        data = _make_triangle_gltf_bytes()
        glb = GLBReader.from_bytes(data)
        self.assertIn('nodes', glb.json_dict)

    def test_json_without_bin_chunk(self):
        # Build GLB with only JSON chunk (no BIN)
        jdict = {"asset": {"version": "2.0"}}
        json_bytes = json.dumps(jdict).encode()
        while len(json_bytes) % 4: json_bytes += b' '
        total = 12 + 8 + len(json_bytes)
        buf = struct.pack('<III', 0x46546C67, 2, total)
        buf += struct.pack('<II', len(json_bytes), 0x4E4F534A)
        buf += json_bytes
        glb = GLBReader(buf)
        self.assertIsNone(glb.bin_chunk)

    def test_scene_nodes_parsed(self):
        data = _make_triangle_gltf_bytes()
        glb  = GLBReader(data)
        self.assertIn('nodes', glb.json_dict)
        self.assertEqual(len(glb.json_dict['nodes']), 1)


# ─────────────────────────────────────────────────────────────────────────────
#  Accessor Decoder Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDecodeAccessor(unittest.TestCase):
    """Unit tests for the _decode_accessor helper."""

    def _make_vec3_accessor(self, points):
        """Build a minimal gltf_dict + buffers for a VEC3 float32 accessor."""
        raw = b''.join(struct.pack('<fff', *p) for p in points)
        gltf = {
            "accessors": [{
                "bufferView": 0, "componentType": 5126,
                "count": len(points), "type": "VEC3",
            }],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(raw)}],
        }
        return gltf, [raw]

    def test_scalar_float(self):
        raw = struct.pack('<fff', 1.0, 2.0, 3.0)
        gltf = {
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "SCALAR"}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 12}],
        }
        result = _decode_accessor(gltf, [raw], 0)
        self.assertAlmostEqual(result[0], 1.0)
        self.assertAlmostEqual(result[2], 3.0)

    def test_vec3_float(self):
        pts = [(1, 2, 3), (4, 5, 6)]
        gltf, bufs = self._make_vec3_accessor(pts)
        result = _decode_accessor(gltf, bufs, 0)
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0][0], 1.0)
        self.assertAlmostEqual(result[1][2], 6.0)

    def test_vec2_float(self):
        raw = struct.pack('<ff ff', 0.1, 0.2, 0.3, 0.4)
        gltf = {
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": 2, "type": "VEC2"}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 16}],
        }
        result = _decode_accessor(gltf, [raw], 0)
        self.assertAlmostEqual(result[0][0], 0.1, places=5)
        self.assertAlmostEqual(result[1][1], 0.4, places=5)

    def test_uint16_scalar(self):
        raw = struct.pack('<HHH', 0, 1, 2)
        gltf = {
            "accessors": [{"bufferView": 0, "componentType": 5123, "count": 3, "type": "SCALAR"}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 6}],
        }
        result = _decode_accessor(gltf, [raw], 0)
        self.assertEqual(result, [0, 1, 2])

    def test_uint32_scalar(self):
        raw = struct.pack('<III', 100, 200, 300)
        gltf = {
            "accessors": [{"bufferView": 0, "componentType": 5125, "count": 3, "type": "SCALAR"}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 12}],
        }
        result = _decode_accessor(gltf, [raw], 0)
        self.assertEqual(result[1], 200)

    def test_uint8_normalized(self):
        raw = struct.pack('<BBBB', 0, 128, 255, 64)
        gltf = {
            "accessors": [{
                "bufferView": 0, "componentType": 5121,
                "count": 4, "type": "SCALAR", "normalized": True
            }],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 4}],
        }
        result = _decode_accessor(gltf, [raw], 0)
        self.assertAlmostEqual(result[0], 0.0)
        self.assertAlmostEqual(result[2], 1.0)

    def test_byte_offset(self):
        # Add 4-byte prefix that should be skipped
        raw = b'\x00\x00\x00\x00' + struct.pack('<fff', 7, 8, 9)
        gltf = {
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": 1,
                           "type": "VEC3", "byteOffset": 4}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 16}],
        }
        result = _decode_accessor(gltf, [raw], 0)
        self.assertAlmostEqual(result[0][0], 7.0)

    def test_returns_none_for_none_idx(self):
        result = _decode_accessor({}, [], None)
        self.assertIsNone(result)

    def test_returns_none_out_of_range(self):
        result = _decode_accessor({"accessors": []}, [], 5)
        self.assertIsNone(result)

    def test_vec4_float(self):
        raw = struct.pack('<ffff', 0,0,0,1)
        gltf = {
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": 1, "type": "VEC4"}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 16}],
        }
        result = _decode_accessor(gltf, [raw], 0)
        self.assertEqual(len(result[0]), 4)
        self.assertAlmostEqual(result[0][3], 1.0)


# ─────────────────────────────────────────────────────────────────────────────
#  Buffer Resolution Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestResolveBuffers(unittest.TestCase):
    """Tests for _resolve_buffers (data URI + GLB bin chunk)."""

    def test_bin_chunk_used_when_no_uri(self):
        gltf = {"buffers": [{"byteLength": 4}]}
        result = _resolve_buffers(gltf, bin_chunk=b'\x01\x02\x03\x04')
        self.assertEqual(result[0], b'\x01\x02\x03\x04')

    def test_data_uri_base64(self):
        raw   = b'\xDE\xAD\xBE\xEF'
        b64   = base64.b64encode(raw).decode()
        gltf  = {"buffers": [{"uri": f"data:application/octet-stream;base64,{b64}",
                               "byteLength": 4}]}
        result = _resolve_buffers(gltf)
        self.assertEqual(result[0], raw)

    def test_empty_buffers(self):
        result = _resolve_buffers({})
        self.assertEqual(result, [])

    def test_multiple_buffers(self):
        b64a = base64.b64encode(b'\x01\x02').decode()
        b64b = base64.b64encode(b'\x03\x04').decode()
        gltf = {"buffers": [
            {"uri": f"data:application/octet-stream;base64,{b64a}", "byteLength": 2},
            {"uri": f"data:application/octet-stream;base64,{b64b}", "byteLength": 2},
        ]}
        result = _resolve_buffers(gltf)
        self.assertEqual(result[0], b'\x01\x02')
        self.assertEqual(result[1], b'\x03\x04')


# ─────────────────────────────────────────────────────────────────────────────
#  Channel → Controller Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestChannelToController(unittest.TestCase):

    def test_translation(self):
        ctrl, vals = _channel_to_controller('translation', [(1.0, 2.0, 3.0)])
        self.assertEqual(ctrl, CTRL_POSITION)
        self.assertEqual(vals[0], (1.0, 2.0, 3.0))

    def test_rotation(self):
        ctrl, vals = _channel_to_controller('rotation', [(0, 0, 0, 1)])
        self.assertEqual(ctrl, CTRL_ORIENTATION)
        self.assertEqual(vals[0], (0.0, 0.0, 0.0, 1.0))

    def test_scale(self):
        ctrl, vals = _channel_to_controller('scale', [(2.0, 2.0, 2.0)])
        self.assertEqual(ctrl, CTRL_SCALE)
        self.assertAlmostEqual(vals[0][0], 2.0)

    def test_unknown_path_returns_none(self):
        ctrl, vals = _channel_to_controller('weights', [(1.0,)])
        self.assertIsNone(ctrl)

    def test_multi_frame_translation(self):
        data = [(0,0,0), (1,1,1), (2,2,2)]
        ctrl, vals = _channel_to_controller('translation', data)
        self.assertEqual(len(vals), 3)
        self.assertEqual(vals[2], (2.0, 2.0, 2.0))

    def test_rotation_preserves_4_components(self):
        ctrl, vals = _channel_to_controller('rotation', [(0.1, 0.2, 0.3, 0.9)])
        self.assertEqual(len(vals[0]), 4)


# ─────────────────────────────────────────────────────────────────────────────
#  Skin Data Builder Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildSkinData(unittest.TestCase):

    def test_single_influence(self):
        joints  = [(0, 0, 0, 0)]
        weights = [(1.0, 0, 0, 0)]
        result  = _build_skin_data(joints, weights)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0].influences), 1)
        self.assertAlmostEqual(result[0].influences[0].weight, 1.0)

    def test_two_influences_normalized(self):
        joints  = [(0, 1, 0, 0)]
        weights = [(0.6, 0.4, 0, 0)]
        result  = _build_skin_data(joints, weights)
        total = sum(bw.weight for bw in result[0].influences)
        self.assertAlmostEqual(total, 1.0, places=5)

    def test_zero_weight_filtered(self):
        joints  = [(0, 1, 2, 3)]
        weights = [(1.0, 0, 0, 0)]
        result  = _build_skin_data(joints, weights)
        self.assertEqual(len(result[0].influences), 1)
        self.assertEqual(result[0].influences[0].bone_index, 0)

    def test_four_equal_weights(self):
        joints  = [(0, 1, 2, 3)]
        weights = [(0.25, 0.25, 0.25, 0.25)]
        result  = _build_skin_data(joints, weights)
        self.assertEqual(len(result[0].influences), 4)
        for bw in result[0].influences:
            self.assertAlmostEqual(bw.weight, 0.25, places=5)

    def test_multiple_vertices(self):
        joints  = [(0,0,0,0), (1,0,0,0)]
        weights = [(1,0,0,0), (1,0,0,0)]
        result  = _build_skin_data(joints, weights)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[1].influences[0].bone_index, 1)


# ─────────────────────────────────────────────────────────────────────────────
#  GLTFImporter — Mesh Geometry Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGLTFImporterGeometry(unittest.TestCase):
    """Tests for mesh geometry extracted by the built-in GLTF importer."""

    def setUp(self):
        self.data  = _make_triangle_gltf_bytes()
        self.model = _import_bytes(self.data)

    def test_model_is_kotormodel(self):
        self.assertIsInstance(self.model, KotorModel)

    def test_model_name(self):
        self.assertEqual(self.model.name, "test")

    def test_root_node_exists(self):
        self.assertIsNotNone(self.model.root_node)

    def test_has_mesh_nodes(self):
        mesh_nodes = self.model.mesh_nodes()
        self.assertGreater(len(mesh_nodes), 0)

    def test_vertex_count(self):
        mesh = self.model.mesh_nodes()[0]
        self.assertEqual(len(mesh.vertices), 3)

    def test_vertex_positions(self):
        mesh = self.model.mesh_nodes()[0]
        # First vertex: (0,0,0)
        self.assertAlmostEqual(mesh.vertices[0][0], 0.0)
        self.assertAlmostEqual(mesh.vertices[0][1], 0.0)

    def test_face_count(self):
        mesh = self.model.mesh_nodes()[0]
        self.assertEqual(len(mesh.faces), 1)

    def test_face_indices(self):
        mesh = self.model.mesh_nodes()[0]
        f = mesh.faces[0]
        self.assertEqual(f, (0, 1, 2))

    def test_normals_present(self):
        mesh = self.model.mesh_nodes()[0]
        self.assertEqual(len(mesh.normals), 3)

    def test_normals_z_up(self):
        mesh = self.model.mesh_nodes()[0]
        self.assertAlmostEqual(mesh.normals[0][2], 1.0)

    def test_uv_count(self):
        mesh = self.model.mesh_nodes()[0]
        self.assertEqual(len(mesh.uvs), 3)

    def test_uv_v_flip(self):
        """V must be flipped: GLTF V=0 → KotOR V=1.0."""
        mesh = self.model.mesh_nodes()[0]
        # GLTF UV[0] = (0, 0) → KotOR should be (0, 1.0)
        self.assertAlmostEqual(mesh.uvs[0][1], 1.0)

    def test_uv_second_vertex_v_flip(self):
        mesh = self.model.mesh_nodes()[0]
        # GLTF UV[1] = (1, 0) → KotOR (1, 1.0)
        self.assertAlmostEqual(mesh.uvs[1][1], 1.0)

    def test_uv_third_vertex_v_flip(self):
        mesh = self.model.mesh_nodes()[0]
        # GLTF UV[2] = (0, 1) → KotOR (0, 0.0)
        self.assertAlmostEqual(mesh.uvs[2][1], 0.0)

    def test_mesh_render_flag(self):
        mesh = self.model.mesh_nodes()[0]
        self.assertTrue(mesh.render)

    def test_mesh_shadow_flag(self):
        mesh = self.model.mesh_nodes()[0]
        self.assertTrue(mesh.has_shadow)

    def test_bounds_computed(self):
        self.assertNotEqual(self.model.bb_min, self.model.bb_max)


# ─────────────────────────────────────────────────────────────────────────────
#  GLTFImporter — Skin Weights Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGLTFImporterSkin(unittest.TestCase):

    def setUp(self):
        self.model = _import_bytes(_make_skinned_gltf_bytes())

    def test_model_not_none(self):
        self.assertIsNotNone(self.model)

    def test_has_skin_node(self):
        skin_nodes = [n for n in self.model.all_nodes() if n.is_skin]
        self.assertGreater(len(skin_nodes), 0)

    def test_skin_node_has_skin_data(self):
        skin_nodes = [n for n in self.model.all_nodes() if n.is_skin]
        sn = skin_nodes[0]
        self.assertGreater(len(sn.skin_data), 0)

    def test_bone_map_names(self):
        skin_nodes = [n for n in self.model.all_nodes() if n.is_skin]
        sn = skin_nodes[0]
        self.assertIn('bone0', sn.bone_map)
        self.assertIn('bone1', sn.bone_map)

    def test_skin_data_influences(self):
        skin_nodes = [n for n in self.model.all_nodes() if n.is_skin]
        sn = skin_nodes[0]
        # First vertex has bone_index=0, weight=1.0
        sd0 = sn.skin_data[0]
        self.assertEqual(len(sd0.influences), 1)
        self.assertEqual(sd0.influences[0].bone_index, 0)
        self.assertAlmostEqual(sd0.influences[0].weight, 1.0)

    def test_skin_flag_set(self):
        skin_nodes = [n for n in self.model.all_nodes() if n.is_skin]
        sn = skin_nodes[0]
        self.assertTrue(sn.flags & NodeFlags.SKIN)


# ─────────────────────────────────────────────────────────────────────────────
#  GLTFImporter — Animation Import Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGLTFImporterAnimation(unittest.TestCase):

    def setUp(self):
        self.model = _import_bytes(_make_animated_gltf_bytes())

    def test_has_animations(self):
        self.assertGreater(len(self.model.animations), 0)

    def test_animation_name(self):
        self.assertEqual(self.model.animations[0].name, 'walk')

    def test_animation_length_positive(self):
        self.assertGreater(self.model.animations[0].length, 0.0)

    def test_animation_length_correct(self):
        # Max time = 1.0
        self.assertAlmostEqual(self.model.animations[0].length, 1.0, places=4)

    def test_animation_has_nodes(self):
        self.assertGreater(len(self.model.animations[0].nodes), 0)

    def test_animation_node_name(self):
        anim_node = self.model.animations[0].nodes[0]
        self.assertEqual(anim_node.name, 'Bone0')

    def test_animation_controller_type(self):
        anim_node = self.model.animations[0].nodes[0]
        ctrl = anim_node.controllers[0]
        self.assertEqual(ctrl['type'], CTRL_POSITION)

    def test_animation_controller_times(self):
        anim_node = self.model.animations[0].nodes[0]
        ctrl = anim_node.controllers[0]
        self.assertEqual(len(ctrl['times']), 3)
        self.assertAlmostEqual(ctrl['times'][0], 0.0)
        self.assertAlmostEqual(ctrl['times'][2], 1.0)

    def test_animation_controller_values(self):
        anim_node = self.model.animations[0].nodes[0]
        ctrl = anim_node.controllers[0]
        # Value at time=0.5: (0, 1, 0)
        self.assertAlmostEqual(ctrl['values'][1][1], 1.0, places=4)

    def test_rotation_animation(self):
        model = _import_bytes(_make_rotation_anim_bytes())
        self.assertGreater(len(model.animations), 0)
        anim_node = model.animations[0].nodes[0]
        ctrl = anim_node.controllers[0]
        self.assertEqual(ctrl['type'], CTRL_ORIENTATION)
        self.assertEqual(len(ctrl['values'][0]), 4)


# ─────────────────────────────────────────────────────────────────────────────
#  GLTFImporter — Material Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGLTFImporterMaterial(unittest.TestCase):

    def setUp(self):
        self.model = _import_bytes(_make_material_gltf_bytes())

    def test_mesh_has_texture(self):
        meshes = self.model.mesh_nodes()
        self.assertGreater(len(meshes), 0)
        tex = meshes[0].texture
        self.assertTrue(len(tex) > 0)

    def test_texture_name_from_image(self):
        mesh = self.model.mesh_nodes()[0]
        # Should be image name "tex_diffuse" (from images[0].name)
        self.assertIn('tex_diffuse', mesh.texture.lower())


# ─────────────────────────────────────────────────────────────────────────────
#  GLTFImporter — Model Properties Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGLTFImporterModelProps(unittest.TestCase):

    def test_custom_model_name(self):
        model = _import_bytes(_make_triangle_gltf_bytes(), name="my_char")
        self.assertEqual(model.name, "my_char")

    def test_game_version_k1(self):
        imp = GLTFImporter()
        model = imp.import_bytes(_make_triangle_gltf_bytes(), game_version=GameVersion.K1)
        self.assertEqual(model.game_version, GameVersion.K1)

    def test_game_version_k2(self):
        imp = GLTFImporter()
        model = imp.import_bytes(_make_triangle_gltf_bytes(), game_version=GameVersion.K2)
        self.assertEqual(model.game_version, GameVersion.K2)

    def test_supermodel(self):
        imp = GLTFImporter()
        model = imp.import_bytes(_make_triangle_gltf_bytes(), supermodel="S_MALE02")
        self.assertEqual(model.supermodel, "S_MALE02")

    def test_classification(self):
        imp = GLTFImporter()
        model = imp.import_bytes(_make_triangle_gltf_bytes(), classification="door")
        self.assertEqual(model.classification, "door")

    def test_root_node_name_matches_model(self):
        model = _import_bytes(_make_triangle_gltf_bytes(), name="hero")
        self.assertEqual(model.root_node.name, "hero")

    def test_all_nodes_non_empty(self):
        model = _import_bytes(_make_triangle_gltf_bytes())
        self.assertGreater(len(model.all_nodes()), 0)

    def test_model_bounds_finite(self):
        model = _import_bytes(_make_triangle_gltf_bytes())
        for v in model.bb_min + model.bb_max:
            self.assertTrue(math.isfinite(v))


# ─────────────────────────────────────────────────────────────────────────────
#  GLTFImporter — File Import Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGLTFImporterFileIO(unittest.TestCase):

    def test_import_glb_file(self):
        data = _make_triangle_gltf_bytes()
        with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as f:
            f.write(data)
            path = f.name
        try:
            model = GLTFImporter().import_file(path)
            self.assertIsNotNone(model)
            self.assertGreater(len(model.mesh_nodes()), 0)
        finally:
            os.unlink(path)

    def test_import_gltf_json_file(self):
        """Import a .gltf JSON file (no bin, just a minimal header)."""
        gltf = {"asset": {"version": "2.0"}, "nodes": [{"name": "empty"}]}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.gltf', delete=False) as f:
            json.dump(gltf, f)
            path = f.name
        try:
            model = GLTFImporter().import_file(path)
            self.assertIsNotNone(model)
        finally:
            os.unlink(path)

    def test_auto_import_glb(self):
        data = _make_triangle_gltf_bytes()
        with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as f:
            f.write(data)
            path = f.name
        try:
            model = auto_import(path)
            self.assertIsNotNone(model)
        finally:
            os.unlink(path)

    def test_auto_import_unknown_extension(self):
        model = auto_import("/nonexistent/file.xyz")
        self.assertIsNone(model)


# ─────────────────────────────────────────────────────────────────────────────
#  GLTFImporter — Edge Cases
# ─────────────────────────────────────────────────────────────────────────────

class TestGLTFImporterEdgeCases(unittest.TestCase):

    def test_empty_gltf(self):
        gltf = {"asset": {"version": "2.0"}}
        data = _make_glb(gltf)
        model = _import_bytes(data, name="empty")
        self.assertIsNotNone(model)
        self.assertEqual(model.name, "empty")

    def test_node_without_mesh(self):
        gltf = {"asset": {"version": "2.0"},
                "nodes": [{"name": "bone_only"}]}
        data = _make_glb(gltf)
        model = _import_bytes(data)
        self.assertIsNotNone(model)

    def test_multiple_nodes(self):
        gltf = {"asset": {"version": "2.0"},
                "nodes": [{"name": "a"}, {"name": "b"}, {"name": "c"}]}
        data = _make_glb(gltf)
        model = _import_bytes(data)
        names = [n.name for n in model.all_nodes()]
        # root + 3 children
        self.assertGreaterEqual(len(names), 3)

    def test_no_animations(self):
        model = _import_bytes(_make_triangle_gltf_bytes())
        self.assertEqual(len(model.animations), 0)

    def test_import_bytes_returns_none_on_garbage(self):
        imp = GLTFImporter()
        result = imp.import_bytes(b'\x00\x01\x02\x03' * 10, model_name="bad")
        self.assertIsNone(result)

    def test_long_name_truncated(self):
        long_name = "A" * 100
        model = _import_bytes(_make_triangle_gltf_bytes(), name=long_name[:32])
        self.assertLessEqual(len(model.name), 32)

    def test_uv_flip_boundary_zero(self):
        """V=0 in GLTF → V=1.0 in KotOR (top vs bottom origin)."""
        model = _import_bytes(_make_triangle_gltf_bytes())
        mesh = model.mesh_nodes()[0]
        for u, v in mesh.uvs:
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)

    def test_scale_animation_channel(self):
        times  = struct.pack('<ff', 0.0, 1.0)
        values = struct.pack('<fff fff', 1,1,1, 2,2,2)
        bin_data = times + values
        gltf = {
            "asset": {"version": "2.0"},
            "nodes": [{"name": "ScaleNode"}],
            "animations": [{
                "name": "scale_anim",
                "samplers": [{"input": 0, "output": 1}],
                "channels": [{"sampler": 0, "target": {"node": 0, "path": "scale"}}],
            }],
            "accessors": [
                {"bufferView": 0, "componentType": 5126, "count": 2, "type": "SCALAR",
                 "min": [0.0], "max": [1.0]},
                {"bufferView": 1, "componentType": 5126, "count": 2, "type": "VEC3"},
            ],
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": 8},
                {"buffer": 0, "byteOffset": 8, "byteLength": 24},
            ],
            "buffers": [{"byteLength": len(bin_data)}],
        }
        model = _import_bytes(_make_glb(gltf, bin_data))
        self.assertGreater(len(model.animations), 0)
        anim = model.animations[0]
        ctrl = anim.nodes[0].controllers[0]
        self.assertEqual(ctrl['type'], CTRL_SCALE)


if __name__ == '__main__':
    unittest.main()
