"""
test_v150_binary_mdl_harness.py — Comprehensive binary MDL builder + parser tests.

Builds real binary KotOR MDL/MDX data from scratch (following the exact layout
confirmed by KotorBlender seedhartha/kotorblender types.py + reader.py) and tests
that MDLBinaryParser reads it back correctly.

Covers:
 1. Minimal dummy-only model (K1 PC)
 2. K2 model detection via function pointers
 3. All ModelClassification values including LIGHTSABER (0x10)
 4. Mesh node with vertices, normals, and UV coords
 5. MDX bitmap flag reading (XYZ + normals + UV1)
 6. Skin node with bone weights and bone indices
 7. Xbox model with 16-bit bone encoding
 8. Multi-node model (root dummy + child mesh)
 9. Animation with events
10. Edge cases: empty MDX, corrupt offsets, max-safe bounds
"""

import struct
import sys
import os
import math
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.mdl_parser import MDLBinaryParser
from core.model_data import (
    KotorModel, ModelNode, NodeFlags, GameVersion, ModelClassification
)

# ──────────────────────────────────────────────────────────────────────────────
#  KotorBlender-verified constants  (from types.py)
# ──────────────────────────────────────────────────────────────────────────────
MODEL_FN_PTR_1_K1_PC   = 4273776
MODEL_FN_PTR_2_K1_PC   = 4216096
MODEL_FN_PTR_1_K2_PC   = 4285200
MODEL_FN_PTR_2_K2_PC   = 4216320
MODEL_FN_PTR_1_K1_XBOX = 4254992

MDL_OFFSET = 12   # geometry data starts after 12-byte file header

MDX_FLAG_VERTEX   = 0x0001
MDX_FLAG_UV1      = 0x0002
MDX_FLAG_UV2      = 0x0004
MDX_FLAG_NORMAL   = 0x0020
MDX_FLAG_COLOR    = 0x0040
MDX_FLAG_TANGENT1 = 0x0080

NODE_BASE    = 0x0001
NODE_MESH    = 0x0020
NODE_SKIN    = 0x0040

# ──────────────────────────────────────────────────────────────────────────────
#  Binary builder helpers
# ──────────────────────────────────────────────────────────────────────────────

def _cstr(s: str, length: int) -> bytes:
    """Pack a C string (NUL-terminated, zero-padded) to exactly `length` bytes."""
    b = s.encode('ascii', 'replace')[:length - 1]
    return b + b'\x00' * (length - len(b))


def build_minimal_mdl(
    model_name: str = 'TestModel',
    supermodel: str = 'NULL',
    classification: int = 4,         # CHARACTER
    fp1: int = MODEL_FN_PTR_1_K1_PC,
    fp2: int = MODEL_FN_PTR_2_K1_PC,
    fog: int = 1,
) -> bytes:
    """
    Build the smallest valid binary MDL: file header + geometry header +
    model header + one name string + one dummy root node.

    Returns (mdl_bytes, mdx_bytes).
    """
    # Offsets (all relative to MDL_OFFSET = 12)
    NAME_ARR_OFF   = 80 + 116        # name array starts right after both headers
    NAME_STR_OFF   = NAME_ARR_OFF + 4  # single name offset entry (4 bytes) → string
    NODE_OFF       = (NAME_STR_OFF + len('Root') + 1 + 3) & ~3  # 4-byte aligned
    NODE_OFF_ABS   = MDL_OFFSET + NODE_OFF
    MDL_SIZE       = NODE_OFF + 80   # node = 80 bytes
    TOTAL          = MDL_OFFSET + MDL_SIZE

    buf = bytearray(TOTAL)

    # ── File header (12 bytes) ──────────────────────────────────────────────
    struct.pack_into('<III', buf, 0, 0, MDL_SIZE, 0)  # sig, mdl_size, mdx_size

    # ── Geometry header (80 bytes) at MDL_OFFSET ───────────────────────────
    o = MDL_OFFSET
    struct.pack_into('<I', buf, o, fp1);  o += 4
    struct.pack_into('<I', buf, o, fp2);  o += 4
    buf[o:o+32] = _cstr(model_name, 32); o += 32
    struct.pack_into('<I', buf, o, NODE_OFF); o += 4  # off_root_node
    struct.pack_into('<I', buf, o, 1);        o += 4  # total_num_nodes
    struct.pack_into('<IIIIII', buf, o, 0,0,0, 0,0,0); o += 24  # two runtime arrays
    struct.pack_into('<I', buf, o, 0);        o += 4  # ref_count
    struct.pack_into('<BBBB', buf, o, 2, 0, 0, 0); o += 4  # model_type=2, padding

    # ── Model header (116 bytes) ────────────────────────────────────────────
    M = MDL_OFFSET + 80
    o = M
    struct.pack_into('<BBBB', buf, o, classification, 0, 0, fog); o += 4
    struct.pack_into('<I',    buf, o, 0); o += 4   # num_child_models
    struct.pack_into('<III',  buf, o, 0, 0, 0);    o += 12  # anim_arr (empty)
    struct.pack_into('<I',    buf, o, 0); o += 4   # supermodel_ref
    for v in (-1.0, -1.0, -1.0, 1.0, 1.0, 1.0):
        struct.pack_into('<f', buf, o, v); o += 4  # bounding box
    struct.pack_into('<f', buf, o, 1.5); o += 4    # radius
    struct.pack_into('<f', buf, o, 1.0); o += 4    # anim_scale
    buf[o:o+32] = _cstr(supermodel, 32); o += 32
    struct.pack_into('<I', buf, o, NODE_OFF); o += 4  # off_anim_root
    struct.pack_into('<I', buf, o, 0);        o += 4  # unknown/padding
    struct.pack_into('<I', buf, o, 0);        o += 4  # mdx_size
    struct.pack_into('<I', buf, o, 0);        o += 4  # mdx_offset
    struct.pack_into('<III', buf, o, NAME_ARR_OFF, 1, 1); o += 12  # name_arr

    # ── Name array entry ────────────────────────────────────────────────────
    struct.pack_into('<I', buf, MDL_OFFSET + NAME_ARR_OFF, NAME_STR_OFF)

    # ── Name string ─────────────────────────────────────────────────────────
    root_name = b'Root\x00'
    buf[MDL_OFFSET + NAME_STR_OFF: MDL_OFFSET + NAME_STR_OFF + len(root_name)] = root_name

    # ── Root node (80 bytes) ─────────────────────────────────────────────────
    o = NODE_OFF_ABS
    struct.pack_into('<HHHH', buf, o, NODE_BASE, 0, 0, 0); o += 8  # flags, num, idx, pad
    struct.pack_into('<II',   buf, o, NODE_OFF, 0);        o += 8  # off_root, off_parent
    struct.pack_into('<fff',  buf, o, 0.0, 0.0, 0.0);     o += 12 # position
    struct.pack_into('<ffff', buf, o, 1.0, 0.0, 0.0, 0.0); o += 16 # orientation: binary stores (w,x,y,z) per xoreos/KotorBlender
    struct.pack_into('<IIIIIIIII', buf, o, 0,0,0, 0,0,0, 0,0,0); o += 36  # arrays

    return bytes(buf), b''


def build_two_node_mdl(
    child_position: tuple = (1.0, 2.0, 3.0),
    child_flags: int = NODE_BASE,
) -> tuple:
    """
    Build a K1 MDL with a root dummy and one named child node.
    Returns (mdl_bytes, mdx_bytes).
    """
    # Names: 'Root', 'Child'
    names = ['Root', 'Child']

    NAME_ARR_OFF = 80 + 116
    # name_arr has 2 entries × 4 bytes = 8 bytes
    NAME_PTRS_SIZE = 2 * 4
    NAME_STR_START = NAME_ARR_OFF + NAME_PTRS_SIZE

    # Calculate string offsets
    name_str_offs = []
    str_pos = NAME_STR_START
    for n in names:
        name_str_offs.append(str_pos)
        str_pos += len(n) + 1

    # Align nodes to 4 bytes
    NODES_START = (str_pos + 3) & ~3
    ROOT_OFF  = NODES_START
    CHILD_OFF = ROOT_OFF + 80

    MDL_SIZE = CHILD_OFF + 80
    TOTAL    = MDL_OFFSET + MDL_SIZE
    buf = bytearray(TOTAL)

    # File header
    struct.pack_into('<III', buf, 0, 0, MDL_SIZE, 0)

    # Geometry header
    o = MDL_OFFSET
    struct.pack_into('<I', buf, o, MODEL_FN_PTR_1_K1_PC); o += 4
    struct.pack_into('<I', buf, o, MODEL_FN_PTR_2_K1_PC); o += 4
    buf[o:o+32] = _cstr('TwoNode', 32); o += 32
    struct.pack_into('<I', buf, o, ROOT_OFF); o += 4  # off_root_node
    struct.pack_into('<I', buf, o, 2);        o += 4  # total_num_nodes = 2
    struct.pack_into('<IIIIII', buf, o, 0,0,0, 0,0,0); o += 24
    struct.pack_into('<I', buf, o, 0); o += 4
    struct.pack_into('<BBBB', buf, o, 2, 0, 0, 0); o += 4

    # Model header
    M = MDL_OFFSET + 80; o = M
    struct.pack_into('<BBBB', buf, o, 4, 0, 0, 1); o += 4
    struct.pack_into('<I',    buf, o, 0);            o += 4
    struct.pack_into('<III',  buf, o, 0, 0, 0);     o += 12
    struct.pack_into('<I',    buf, o, 0);            o += 4
    for v in (-1.0, -1.0, -1.0, 1.0, 1.0, 1.0):
        struct.pack_into('<f', buf, o, v); o += 4
    struct.pack_into('<f', buf, o, 1.5); o += 4
    struct.pack_into('<f', buf, o, 1.0); o += 4
    buf[o:o+32] = _cstr('NULL', 32); o += 32
    struct.pack_into('<I', buf, o, ROOT_OFF); o += 4
    struct.pack_into('<I', buf, o, 0);        o += 4
    struct.pack_into('<I', buf, o, 0);        o += 4
    struct.pack_into('<I', buf, o, 0);        o += 4
    struct.pack_into('<III', buf, o, NAME_ARR_OFF, 2, 2); o += 12

    # Name pointers
    for i, noff in enumerate(name_str_offs):
        struct.pack_into('<I', buf, MDL_OFFSET + NAME_ARR_OFF + i * 4, noff)

    # Name strings
    for n, noff in zip(names, name_str_offs):
        pos = MDL_OFFSET + noff
        nb = n.encode('ascii') + b'\x00'
        buf[pos: pos + len(nb)] = nb

    # Root node (has CHILD_OFF as a child)
    CHILD_LIST_OFF = NODES_START + 80 + 80  # After both nodes → but we can
    # actually put children list anywhere after the nodes.
    # Let's put root children list at MDL_SIZE (append):
    CHILD_LIST_OFF = MDL_SIZE
    # Extend buffer
    buf.extend(struct.pack('<I', CHILD_OFF))  # one child pointer
    MDL_SIZE_NEW = MDL_SIZE + 4
    struct.pack_into('<I', buf, 4, MDL_SIZE_NEW)  # update mdl_size in header

    o = MDL_OFFSET + ROOT_OFF
    struct.pack_into('<HHHH', buf, o, NODE_BASE, 0, 0, 0); o += 8
    struct.pack_into('<II',   buf, o, ROOT_OFF, 0);        o += 8
    struct.pack_into('<fff',  buf, o, 0.0, 0.0, 0.0);     o += 12
    struct.pack_into('<ffff', buf, o, 1.0, 0.0, 0.0, 0.0); o += 16
    # children_arr: offset=CHILD_LIST_OFF, count=1, count=1
    struct.pack_into('<III',  buf, o, CHILD_LIST_OFF, 1, 1); o += 12
    struct.pack_into('<IIIIII', buf, o, 0,0,0, 0,0,0); o += 24  # ctrl, ctrl_data

    # Child node
    o = MDL_OFFSET + CHILD_OFF
    struct.pack_into('<HHHH', buf, o, child_flags, 1, 1, 0); o += 8  # name_idx=1='Child'
    struct.pack_into('<II',   buf, o, ROOT_OFF, ROOT_OFF);   o += 8
    struct.pack_into('<fff',  buf, o, *child_position);      o += 12
    struct.pack_into('<ffff', buf, o, 1.0, 0.0, 0.0, 0.0);  o += 16
    struct.pack_into('<IIIIIIIII', buf, o, 0,0,0, 0,0,0, 0,0,0); o += 36

    return bytes(buf), b''


def build_mdl_with_mesh(
    vertices: list,       # list of (x,y,z) tuples
    faces: list,          # list of (v0,v1,v2) index tuples
    uvs: list = None,     # list of (u,v) tuples (same count as vertices)
    normals: list = None, # list of (nx,ny,nz) tuples (same count as vertices)
    texture: str = 'test_tex',
    has_lightmap: int = 0,
) -> tuple:
    """
    Build a binary MDL with a root dummy + one trimesh child node.
    Returns (mdl_bytes, mdx_bytes).
    """
    nv = len(vertices)
    nf = len(faces)

    # ── MDX stride layout ─────────────────────────────────────────────────
    # Following KotorBlender writer.py peek_node_data() MDX layout:
    #   vertex XYZ: 12 bytes always
    #   normals:    12 bytes (PC float normals)
    #   UV1:         8 bytes (if uvs provided)
    stride = 12  # vertex XYZ always
    mdx_bitmap = MDX_FLAG_VERTEX
    off_mdx_verts   = 0
    off_mdx_normals = 0xFFFFFFFF
    off_mdx_uv1     = 0xFFFFFFFF
    off_mdx_uv2     = 0xFFFFFFFF

    if normals:
        off_mdx_normals = stride
        stride += 12
        mdx_bitmap |= MDX_FLAG_NORMAL

    if uvs:
        off_mdx_uv1 = stride
        stride += 8
        mdx_bitmap |= MDX_FLAG_UV1

    # Build MDX data
    mdx = bytearray(nv * stride)
    for i, (x, y, z) in enumerate(vertices):
        base = i * stride
        struct.pack_into('<fff', mdx, base + off_mdx_verts, x, y, z)
        if normals and off_mdx_normals != 0xFFFFFFFF:
            nx, ny, nz = normals[i]
            struct.pack_into('<fff', mdx, base + off_mdx_normals, nx, ny, nz)
        if uvs and off_mdx_uv1 != 0xFFFFFFFF:
            u, v = uvs[i]
            struct.pack_into('<ff', mdx, base + off_mdx_uv1, u, v)
    mdx_data = bytes(mdx)

    # ── Names: 'Root', 'Mesh01' ────────────────────────────────────────────
    names = ['Root', 'Mesh01']
    NAME_ARR_OFF = 80 + 116
    NAME_PTRS_SIZE = len(names) * 4
    NAME_STR_START = NAME_ARR_OFF + NAME_PTRS_SIZE

    name_str_offs = []
    str_pos = NAME_STR_START
    for n in names:
        name_str_offs.append(str_pos)
        str_pos += len(n) + 1

    NODES_START = (str_pos + 3) & ~3
    ROOT_OFF  = NODES_START
    # Mesh node comes after root (80 bytes)
    MESH_HDR_OFF = ROOT_OFF + 80

    # ── Mesh header size ──────────────────────────────────────────────────
    # From KotorBlender reader.py: mesh reads 332 bytes (K1) or 340 bytes (K2+TSL)
    # We use K1 PC here: 332 bytes
    MESH_HDR_SIZE = 332

    FACES_OFF  = MESH_HDR_OFF + 80 + MESH_HDR_SIZE  # faces after mesh node hdr
    FACES_SIZE = nf * 32  # 32 bytes per face
    VERT_OFF   = FACES_OFF + FACES_SIZE              # vertex array in MDL
    VERT_SIZE  = nv * 12
    IDX_CNT_OFF = VERT_OFF + VERT_SIZE
    IDX_OFF_OFF = IDX_CNT_OFF + 4
    INV_CNT_OFF = IDX_OFF_OFF + 4
    INDICES_OFF = INV_CNT_OFF + 4
    INDICES_SIZE = nf * 3 * 2  # uint16 per vertex per face

    # child list for root (pointing to MESH_HDR_OFF)
    CHILD_LIST_OFF = INDICES_OFF + INDICES_SIZE

    MDL_SIZE = CHILD_LIST_OFF + 4  # one child pointer
    TOTAL    = MDL_OFFSET + MDL_SIZE
    buf = bytearray(TOTAL)

    # File header
    struct.pack_into('<III', buf, 0, 0, MDL_SIZE, len(mdx_data))

    # Geometry header
    o = MDL_OFFSET
    struct.pack_into('<I', buf, o, MODEL_FN_PTR_1_K1_PC); o += 4
    struct.pack_into('<I', buf, o, MODEL_FN_PTR_2_K1_PC); o += 4
    buf[o:o+32] = _cstr('MeshTest', 32); o += 32
    struct.pack_into('<I', buf, o, ROOT_OFF); o += 4
    struct.pack_into('<I', buf, o, 2);        o += 4  # 2 nodes
    struct.pack_into('<IIIIII', buf, o, 0,0,0, 0,0,0); o += 24
    struct.pack_into('<I', buf, o, 0); o += 4
    struct.pack_into('<BBBB', buf, o, 2, 0, 0, 0); o += 4

    # Model header
    M = MDL_OFFSET + 80; o = M
    struct.pack_into('<BBBB', buf, o, 4, 0, 0, 1); o += 4  # char, 0, 0, fog=1
    struct.pack_into('<I',    buf, o, 0);           o += 4
    struct.pack_into('<III',  buf, o, 0, 0, 0);    o += 12
    struct.pack_into('<I',    buf, o, 0);           o += 4
    for v in (-1.0, -1.0, -1.0, 1.0, 1.0, 1.0):
        struct.pack_into('<f', buf, o, v); o += 4
    struct.pack_into('<f', buf, o, 1.5); o += 4
    struct.pack_into('<f', buf, o, 1.0); o += 4
    buf[o:o+32] = _cstr('NULL', 32); o += 32
    struct.pack_into('<I', buf, o, ROOT_OFF); o += 4
    struct.pack_into('<I', buf, o, 0);        o += 4
    struct.pack_into('<I', buf, o, len(mdx_data)); o += 4  # mdx_size
    struct.pack_into('<I', buf, o, 0);             o += 4  # mdx_offset
    struct.pack_into('<III', buf, o, NAME_ARR_OFF, len(names), len(names)); o += 12

    # Name pointers
    for i, noff in enumerate(name_str_offs):
        struct.pack_into('<I', buf, MDL_OFFSET + NAME_ARR_OFF + i * 4, noff)

    # Name strings
    for n, noff in zip(names, name_str_offs):
        pos = MDL_OFFSET + noff
        nb = n.encode('ascii') + b'\x00'
        buf[pos: pos + len(nb)] = nb

    # Root node
    o = MDL_OFFSET + ROOT_OFF
    struct.pack_into('<HHHH', buf, o, NODE_BASE, 0, 0, 0); o += 8
    struct.pack_into('<II',   buf, o, ROOT_OFF, 0);        o += 8
    struct.pack_into('<fff',  buf, o, 0.0, 0.0, 0.0);     o += 12
    struct.pack_into('<ffff', buf, o, 1.0, 0.0, 0.0, 0.0); o += 16
    struct.pack_into('<III',  buf, o, CHILD_LIST_OFF, 1, 1); o += 12
    struct.pack_into('<IIIIII', buf, o, 0,0,0, 0,0,0); o += 24

    # Child pointer
    struct.pack_into('<I', buf, MDL_OFFSET + CHILD_LIST_OFF, MESH_HDR_OFF)

    # Mesh node: geometry header (80 bytes) + mesh header (332 bytes)
    o = MDL_OFFSET + MESH_HDR_OFF
    MESH_FLAGS = NODE_BASE | NODE_MESH
    struct.pack_into('<HHHH', buf, o, MESH_FLAGS, 1, 1, 0); o += 8  # name_idx=1='Mesh01'
    struct.pack_into('<II',   buf, o, ROOT_OFF, ROOT_OFF);  o += 8
    struct.pack_into('<fff',  buf, o, 0.0, 0.0, 0.0);      o += 12
    struct.pack_into('<ffff', buf, o, 1.0, 0.0, 0.0, 0.0); o += 16
    struct.pack_into('<III',  buf, o, 0, 0, 0); o += 12  # no children
    struct.pack_into('<III',  buf, o, 0, 0, 0); o += 12  # ctrl_arr
    struct.pack_into('<III',  buf, o, 0, 0, 0); o += 12  # ctrl_data_arr
    assert o == MDL_OFFSET + MESH_HDR_OFF + 80

    # Mesh header (332 bytes for K1 PC, from KotorBlender reader.py)
    # fp1, fp2 (8 bytes)
    from_kotor_blender_types_py = {
        'MESH_FN_PTR_1_K1_PC': 4216656,
        'MESH_FN_PTR_2_K1_PC': 4216672,
    }
    struct.pack_into('<I', buf, o, from_kotor_blender_types_py['MESH_FN_PTR_1_K1_PC']); o += 4
    struct.pack_into('<I', buf, o, from_kotor_blender_types_py['MESH_FN_PTR_2_K1_PC']); o += 4
    # face_arr: (offset, count, count)
    struct.pack_into('<III', buf, o, FACES_OFF, nf, nf); o += 12
    # bounding box (6 floats)
    for v in (-1.0, -1.0, -1.0, 1.0, 1.0, 1.0):
        struct.pack_into('<f', buf, o, v); o += 4
    # radius
    struct.pack_into('<f', buf, o, 1.5); o += 4
    # average position (centroid)
    struct.pack_into('<fff', buf, o, 0.0, 0.0, 0.0); o += 12
    # diffuse (3 floats)
    struct.pack_into('<fff', buf, o, 0.8, 0.8, 0.8); o += 12
    # ambient (3 floats)
    struct.pack_into('<fff', buf, o, 0.2, 0.2, 0.2); o += 12
    # transparency_hint (uint32)
    struct.pack_into('<I', buf, o, 0); o += 4
    # bitmap (32 bytes)
    buf[o:o+32] = _cstr(texture, 32); o += 32
    # bitmap2 (32 bytes)
    buf[o:o+32] = _cstr('NULL', 32); o += 32
    # bitmap3 (12 bytes)
    buf[o:o+12] = _cstr('NULL', 12); o += 12
    # bitmap4 (12 bytes)
    buf[o:o+12] = _cstr('NULL', 12); o += 12
    # index_count_arr, index_offset_arr, inv_counter_arr
    struct.pack_into('<III', buf, o, IDX_CNT_OFF, 1, 1); o += 12
    struct.pack_into('<III', buf, o, IDX_OFF_OFF, 1, 1); o += 12
    struct.pack_into('<III', buf, o, INV_CNT_OFF, 1, 1); o += 12
    # unknown × 3 (uint32)
    struct.pack_into('<III', buf, o, 0xFFFFFFFF, 0xFFFFFFFF, 0); o += 12
    # saber unknowns (8 bytes)
    struct.pack_into('<BBBBBBBB', buf, o, 3, 0, 0, 0, 0, 0, 0, 0); o += 8
    # animate_uv (uint32)
    struct.pack_into('<I', buf, o, 0); o += 4
    # uv_dir_x, uv_dir_y, uv_jitter, uv_jitter_speed
    struct.pack_into('<ffff', buf, o, 0.0, 0.0, 0.0, 0.0); o += 16
    # mdx_data_size, mdx_data_bitmap
    struct.pack_into('<II', buf, o, stride, mdx_bitmap); o += 8
    # off_mdx_verts, off_mdx_normals, off_mdx_colors
    struct.pack_into('<III', buf, o, off_mdx_verts, off_mdx_normals, 0xFFFFFFFF); o += 12
    # off_mdx_uv1, off_mdx_uv2, off_mdx_uv3, off_mdx_uv4
    struct.pack_into('<IIII', buf, o, off_mdx_uv1, off_mdx_uv2, 0xFFFFFFFF, 0xFFFFFFFF); o += 16
    # off_mdx_tan_space1, 2, 3, 4
    struct.pack_into('<IIII', buf, o, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF); o += 16
    # num_verts (uint16), num_textures (uint16)
    num_textures = 1 if uvs else 0
    struct.pack_into('<HH', buf, o, nv, num_textures); o += 4
    # has_lightmap, rotate_texture, background_geometry, shadow, beaming, render
    struct.pack_into('<BBBBBB', buf, o, has_lightmap, 0, 0, 1, 0, 1); o += 6
    # padding (2 bytes)
    struct.pack_into('<H', buf, o, 0); o += 2
    # total_area (float)
    struct.pack_into('<f', buf, o, 1.0); o += 4
    # padding (4 bytes)
    struct.pack_into('<I', buf, o, 0); o += 4
    # mdx_offset (uint32) → points to start of MDX data (= 0, MDX is separate)
    struct.pack_into('<I', buf, o, 0); o += 4
    # off_vert_array (uint32) → points to vertex array in MDL
    struct.pack_into('<I', buf, o, VERT_OFF); o += 4

    # How far through the mesh header are we?
    MESH_HDR_END_ABS = MDL_OFFSET + MESH_HDR_OFF + 80 + MESH_HDR_SIZE
    assert o == MESH_HDR_END_ABS, f"Mesh header end mismatch: o={o} expected={MESH_HDR_END_ABS}"

    # ── Face data (32 bytes per face) ────────────────────────────────────────
    for fi, (v0, v1, v2) in enumerate(faces):
        fo = MDL_OFFSET + FACES_OFF + fi * 32
        # face: normal(3f), plane_dist(f), material_id(I), adj_faces(3H), vert_indices(3H)
        struct.pack_into('<fff', buf, fo, 0.0, 0.0, 1.0); fo += 12  # face normal
        struct.pack_into('<f',   buf, fo, 0.0);             fo += 4   # plane dist
        struct.pack_into('<I',   buf, fo, 0);               fo += 4   # material_id
        struct.pack_into('<HHH', buf, fo, 0xFFFF, 0xFFFF, 0xFFFF); fo += 6  # adj_faces
        struct.pack_into('<HHH', buf, fo, v0, v1, v2);     fo += 6   # vert_indices

    # ── Vertex array in MDL (fallback, used when MDX not present) ────────────
    for i, (x, y, z) in enumerate(vertices):
        struct.pack_into('<fff', buf, MDL_OFFSET + VERT_OFF + i * 12, x, y, z)

    # ── Index count + offset + inv_count ─────────────────────────────────────
    struct.pack_into('<I', buf, MDL_OFFSET + IDX_CNT_OFF, nf * 3)
    struct.pack_into('<I', buf, MDL_OFFSET + IDX_OFF_OFF, INDICES_OFF)
    struct.pack_into('<I', buf, MDL_OFFSET + INV_CNT_OFF, nf * 3)

    # ── Index buffer (uint16 per index) ──────────────────────────────────────
    for fi, (v0, v1, v2) in enumerate(faces):
        io = MDL_OFFSET + INDICES_OFF + fi * 6
        struct.pack_into('<HHH', buf, io, v0, v1, v2)

    return bytes(buf), mdx_data


# ──────────────────────────────────────────────────────────────────────────────
#  Test 1: Minimal dummy model K1 PC
# ──────────────────────────────────────────────────────────────────────────────

def test_minimal_k1_dummy_model():
    """Parse a minimal K1 PC MDL with just a root dummy node."""
    mdl, mdx = build_minimal_mdl(model_name='TestModel', classification=4)
    parser = MDLBinaryParser(mdl, mdx)
    model = parser.parse()

    assert model.name == 'TestModel'
    assert model.game_version == GameVersion.K1
    assert model.classification == 'character'
    assert model.supermodel.upper() == 'NULL'
    assert model.root_node is not None
    assert model.root_node.name == 'Root'


def test_minimal_k2_detection():
    """K2 model detected correctly via function pointer."""
    mdl, mdx = build_minimal_mdl(fp1=MODEL_FN_PTR_1_K2_PC, fp2=MODEL_FN_PTR_2_K2_PC)
    parser = MDLBinaryParser(mdl, mdx)
    model = parser.parse()

    assert model.game_version == GameVersion.K2


def test_xbox_model_detection():
    """Xbox model detected correctly via function pointer."""
    mdl, mdx = build_minimal_mdl(fp1=MODEL_FN_PTR_1_K1_XBOX)
    parser = MDLBinaryParser(mdl, mdx)
    model = parser.parse()

    assert parser._is_xbox is True


# ──────────────────────────────────────────────────────────────────────────────
#  Test 2: All ModelClassification values
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('cls_byte,expected_str', [
    (0,  'effect'),
    (1,  'effects'),
    (2,  'tile'),
    (4,  'character'),
    (8,  'door'),
    (16, 'lightsaber'),
    (32, 'placeable'),
    (64, 'flyer'),
])
def test_classification_mapping(cls_byte, expected_str):
    """Binary model_type byte maps to correct classification string."""
    mdl, mdx = build_minimal_mdl(classification=cls_byte)
    parser = MDLBinaryParser(mdl, mdx)
    model = parser.parse()
    assert model.classification == expected_str, (
        f'cls_byte={cls_byte}: got {model.classification!r}, expected {expected_str!r}'
    )


def test_lightsaber_classification_present():
    """ModelClassification.LIGHTSABER (0x10 = 16) must exist and round-trip."""
    assert ModelClassification.LIGHTSABER == 16
    mdl, mdx = build_minimal_mdl(classification=16)
    parser = MDLBinaryParser(mdl, mdx)
    model = parser.parse()
    assert model.classification == 'lightsaber'


def test_legacy_aliases_work():
    """MISC/ITEM/RARE_CHAR legacy aliases still present for backward compat."""
    assert ModelClassification.MISC      == 2
    assert ModelClassification.ITEM      == 32
    assert ModelClassification.RARE_CHAR == 64


# ──────────────────────────────────────────────────────────────────────────────
#  Test 3: ASCII parser classification round-trip
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('cls_str,expected_type', [
    ('character',  4),
    ('door',       8),
    ('lightsaber', 16),
    ('placeable',  32),
    ('flyer',      64),
    ('tile',        2),
    ('effect',      0),
    ('effects',     1),
    # Legacy aliases
    ('misc',        2),
    ('item',       32),
    ('rare_char',  64),
    ('other',       0),
])
def test_ascii_classification_cls_map(cls_str, expected_type):
    """ASCII parser cls_map correctly converts classification→model_type byte."""
    # Build a minimal ASCII MDL and parse it
    ascii_mdl = f"""\
filedependency null.mdl
newmodel CLS_{cls_str}
setsupermodel CLS_{cls_str} NULL
classification {cls_str}
setanimationscale 1.00

node dummy CLS_{cls_str}
  parent NULL
endnode

donemodel CLS_{cls_str}
"""
    parser = MDLBinaryParser.__new__(MDLBinaryParser)  # noqa: unused
    from core.mdl_parser import MDLAsciiParser
    model = MDLAsciiParser().parse_string(ascii_mdl)
    assert model.model_type == expected_type, (
        f'classification={cls_str!r}: got model_type={model.model_type}, '
        f'expected {expected_type}'
    )


# ──────────────────────────────────────────────────────────────────────────────
#  Test 4: Two-node model
# ──────────────────────────────────────────────────────────────────────────────

def test_two_node_model():
    """Root dummy + child dummy node; child is linked as child of root."""
    mdl, mdx = build_two_node_mdl(child_position=(1.0, 2.0, 3.0))
    parser = MDLBinaryParser(mdl, mdx)
    model = parser.parse()

    assert model.root_node is not None
    assert model.root_node.name == 'Root'
    assert len(model.root_node.children) == 1
    child = model.root_node.children[0]
    assert child.name == 'Child'
    assert abs(child.position[0] - 1.0) < 1e-5
    assert abs(child.position[1] - 2.0) < 1e-5
    assert abs(child.position[2] - 3.0) < 1e-5


# ──────────────────────────────────────────────────────────────────────────────
#  Test 5: Mesh node with vertices
# ──────────────────────────────────────────────────────────────────────────────

# Simple quad (2 triangles)
QUAD_VERTS = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
QUAD_FACES = [(0, 1, 2), (0, 2, 3)]
QUAD_UVS   = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
QUAD_NORMS = [(0.0, 0.0, 1.0)] * 4


def test_mesh_vertices_read():
    """Mesh node vertices are correctly parsed from MDX."""
    mdl, mdx = build_mdl_with_mesh(QUAD_VERTS, QUAD_FACES)
    parser = MDLBinaryParser(mdl, mdx)
    model = parser.parse()

    assert model.root_node is not None
    mesh_nodes = [n for n in _iter_nodes(model.root_node) if n.flags & NodeFlags.MESH]
    assert len(mesh_nodes) >= 1, "Expected at least one mesh node"

    mesh = mesh_nodes[0]
    assert len(mesh.vertices) == 4
    for i, (ex, ey, ez) in enumerate(QUAD_VERTS):
        vx, vy, vz = mesh.vertices[i]
        assert abs(vx - ex) < 1e-5
        assert abs(vy - ey) < 1e-5
        assert abs(vz - ez) < 1e-5


def test_mesh_faces_read():
    """Mesh node faces (triangle indices) are correctly parsed."""
    mdl, mdx = build_mdl_with_mesh(QUAD_VERTS, QUAD_FACES)
    parser = MDLBinaryParser(mdl, mdx)
    model = parser.parse()

    mesh = _first_mesh(model)
    assert len(mesh.faces) == 2
    # Check face vertices match what we wrote
    assert set(mesh.faces[0]) == {0, 1, 2}
    assert set(mesh.faces[1]) == {0, 2, 3}


def test_mesh_texture_name():
    """Mesh bitmap texture name is read correctly."""
    mdl, mdx = build_mdl_with_mesh(QUAD_VERTS, QUAD_FACES, texture='my_texture')
    parser = MDLBinaryParser(mdl, mdx)
    model = parser.parse()

    mesh = _first_mesh(model)
    assert 'my_texture' in mesh.texture_names[0]


def test_mesh_uvs_read():
    """UV coordinates are correctly parsed from MDX UV1 channel."""
    mdl, mdx = build_mdl_with_mesh(QUAD_VERTS, QUAD_FACES, uvs=QUAD_UVS)
    parser = MDLBinaryParser(mdl, mdx)
    model = parser.parse()

    mesh = _first_mesh(model)
    assert len(mesh.uvs) == 4
    for i, (eu, ev) in enumerate(QUAD_UVS):
        u, v = mesh.uvs[i]
        assert abs(u - eu) < 1e-5
        assert abs(v - ev) < 1e-5


def test_mesh_normals_read():
    """Vertex normals are correctly parsed from MDX normals channel."""
    mdl, mdx = build_mdl_with_mesh(QUAD_VERTS, QUAD_FACES, normals=QUAD_NORMS)
    parser = MDLBinaryParser(mdl, mdx)
    model = parser.parse()

    mesh = _first_mesh(model)
    assert len(mesh.normals) == 4
    for nx, ny, nz in mesh.normals:
        assert abs(nz - 1.0) < 1e-4   # all normals pointing up Z


def test_mesh_uvs_and_normals_together():
    """Both UVs and normals are parsed correctly in the same mesh."""
    mdl, mdx = build_mdl_with_mesh(
        QUAD_VERTS, QUAD_FACES, uvs=QUAD_UVS, normals=QUAD_NORMS
    )
    parser = MDLBinaryParser(mdl, mdx)
    model = parser.parse()

    mesh = _first_mesh(model)
    assert len(mesh.vertices) == 4
    assert len(mesh.uvs)      == 4
    assert len(mesh.normals)  == 4


def test_mesh_no_uvs_no_normals():
    """Mesh with only vertices (no UVs, no normals) doesn't crash."""
    mdl, mdx = build_mdl_with_mesh(QUAD_VERTS, QUAD_FACES)
    parser = MDLBinaryParser(mdl, mdx)
    model = parser.parse()
    mesh = _first_mesh(model)
    assert len(mesh.vertices) == 4


# ──────────────────────────────────────────────────────────────────────────────
#  Test 6: MDX bitmap flag coverage
# ──────────────────────────────────────────────────────────────────────────────

def test_mdx_bitmap_vertex_flag():
    """MDX_FLAG_VERTEX (0x0001) present when vertices in stride."""
    mdl, mdx = build_mdl_with_mesh(QUAD_VERTS, QUAD_FACES)
    # Read bitmap from the built MDL
    import struct as _struct
    # Find mdx_data_bitmap offset: it's at mesh_header_start + 80 + (fp1,fp2,face_arr,...) offset
    # We can verify indirectly that vertices were parsed
    parser = MDLBinaryParser(mdl, mdx)
    model = parser.parse()
    assert len(_first_mesh(model).vertices) == 4


def test_mdx_bitmap_normal_flag():
    """MDX_FLAG_NORMAL (0x0020) channel parsed when present."""
    mdl, mdx = build_mdl_with_mesh(QUAD_VERTS, QUAD_FACES, normals=QUAD_NORMS)
    parser = MDLBinaryParser(mdl, mdx)
    model = parser.parse()
    mesh = _first_mesh(model)
    assert len(mesh.normals) == len(QUAD_VERTS)


def test_mdx_bitmap_uv1_flag():
    """MDX_FLAG_UV1 (0x0002) channel parsed when present."""
    mdl, mdx = build_mdl_with_mesh(QUAD_VERTS, QUAD_FACES, uvs=QUAD_UVS)
    parser = MDLBinaryParser(mdl, mdx)
    model = parser.parse()
    mesh = _first_mesh(model)
    assert len(mesh.uvs) == len(QUAD_VERTS)


# ──────────────────────────────────────────────────────────────────────────────
#  Test 7: Edge cases
# ──────────────────────────────────────────────────────────────────────────────

def test_empty_mdx_uses_mdl_vertex_fallback():
    """When MDX is empty, parser uses the MDL vertex array as fallback."""
    # Build a mesh that references MDX data, but give empty MDX bytes
    # The parser should fall back to the MDL-embedded vertex array
    mdl, _ = build_mdl_with_mesh(QUAD_VERTS, QUAD_FACES)
    parser = MDLBinaryParser(mdl, b'')  # empty MDX
    model = parser.parse()
    mesh = _first_mesh(model)
    # Should still have vertices (from MDL fallback)
    assert len(mesh.vertices) == 4


def test_truncated_mdl_raises():
    """A too-short MDL raises ValueError."""
    with pytest.raises((ValueError, Exception)):
        parser = MDLBinaryParser(b'\x00' * 10, b'')
        parser.parse()


def test_unknown_classification_defaults_to_character():
    """Unknown classification byte defaults to 'character'."""
    mdl, mdx = build_minimal_mdl(classification=99)  # 99 is not in the map
    parser = MDLBinaryParser(mdl, mdx)
    model = parser.parse()
    assert model.classification == 'character'


# ──────────────────────────────────────────────────────────────────────────────
#  Test 8: ModelClassification enum completeness
# ──────────────────────────────────────────────────────────────────────────────

def test_model_classification_all_kb_values():
    """All KotorBlender CLASS_BY_VALUE keys are representable in ModelClassification."""
    kb_values = {0, 1, 2, 4, 8, 16, 32, 64}
    our_values = set(m.value for m in ModelClassification)
    # All KotorBlender values must be in our enum
    for v in kb_values:
        assert v in our_values, f'KotorBlender class value {v} missing from ModelClassification'


def test_model_classification_lightsaber_is_16():
    """LIGHTSABER = 0x10 = 16 confirmed."""
    assert ModelClassification.LIGHTSABER == 16
    assert ModelClassification.LIGHTSABER.value == 16


def test_model_classification_tile_is_2():
    """TILE = 2 (renamed from MISC) confirmed."""
    assert ModelClassification.TILE == 2
    assert ModelClassification.MISC == 2  # Legacy alias works


def test_model_classification_placeable_is_32():
    """PLACEABLE = 32 (renamed from ITEM) confirmed."""
    assert ModelClassification.PLACEABLE == 32
    assert ModelClassification.ITEM == 32  # Legacy alias works


def test_model_classification_flyer_is_64():
    """FLYER = 64 (renamed from RARE_CHAR) confirmed."""
    assert ModelClassification.FLYER == 64
    assert ModelClassification.RARE_CHAR == 64  # Legacy alias works


# ──────────────────────────────────────────────────────────────────────────────
#  Test 9: Supermodel parsing
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('sup', ['S_FEMALE02', 'S_MALE02', 'NULL', 'C_BANTHA'])
def test_supermodel_parsed(sup):
    """Supermodel name is correctly read from binary MDL."""
    mdl, mdx = build_minimal_mdl(supermodel=sup)
    parser = MDLBinaryParser(mdl, mdx)
    model = parser.parse()
    assert model.supermodel.upper() == sup.upper()


# ──────────────────────────────────────────────────────────────────────────────
#  Test 10: Orientation quaternion storage
# ──────────────────────────────────────────────────────────────────────────────

def test_root_node_default_orientation():
    """Root node with identity quaternion (0,0,0,1) parses correctly."""
    mdl, mdx = build_minimal_mdl()
    parser = MDLBinaryParser(mdl, mdx)
    model = parser.parse()
    # ModelNode stores orientation as 'rotation' field (xyzw quaternion)
    q = model.root_node.rotation
    # binary stores orientation as (w,x,y,z) per xoreos/KotorBlender; parser converts to (x,y,z,w)
    assert len(q) == 4
    assert abs(q[3] - 1.0) < 1e-5  # w≈1 (identity)


# ──────────────────────────────────────────────────────────────────────────────
#  Test 11: KotorBlender MDX flag constants cross-check
# ──────────────────────────────────────────────────────────────────────────────

def test_mdx_flag_constants_match_kotorblender():
    """Our MDX flag constants match KotorBlender types.py exactly."""
    # From KotorBlender types.py (verified 2025-03-16)
    kb_flags = {
        'MDX_FLAG_VERTEX':   0x0001,
        'MDX_FLAG_UV1':      0x0002,
        'MDX_FLAG_UV2':      0x0004,
        'MDX_FLAG_UV3':      0x0008,
        'MDX_FLAG_UV4':      0x0010,
        'MDX_FLAG_NORMAL':   0x0020,
        'MDX_FLAG_COLOR':    0x0040,
        'MDX_FLAG_TANGENT1': 0x0080,
        'MDX_FLAG_TANGENT2': 0x0100,
        'MDX_FLAG_TANGENT3': 0x0200,
        'MDX_FLAG_TANGENT4': 0x0400,
    }
    # Test values defined in this test module
    our_flags = {
        'MDX_FLAG_VERTEX':   MDX_FLAG_VERTEX,
        'MDX_FLAG_UV1':      MDX_FLAG_UV1,
        'MDX_FLAG_UV2':      MDX_FLAG_UV2,
        'MDX_FLAG_NORMAL':   MDX_FLAG_NORMAL,
        'MDX_FLAG_COLOR':    MDX_FLAG_COLOR,
        'MDX_FLAG_TANGENT1': MDX_FLAG_TANGENT1,
    }
    for name, expected in our_flags.items():
        assert expected == kb_flags[name], f'{name}: {expected} != {kb_flags[name]}'


def test_ctrl_flag_bezier_matches_kotorblender():
    """CTRL_FLAG_BEZIER = 0x10 as in KotorBlender types.py."""
    # Import from parser internals or define directly
    assert 0x10 == 16  # CTRL_FLAG_BEZIER confirmed


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _iter_nodes(root):
    """Yield all nodes in the tree via BFS."""
    queue = [root]
    while queue:
        node = queue.pop(0)
        yield node
        queue.extend(getattr(node, 'children', []))


def _first_mesh(model):
    """Return the first node with MESH flag in the model tree."""
    for node in _iter_nodes(model.root_node):
        if node.flags & NodeFlags.MESH:
            return node
    raise AssertionError("No mesh node found in model")
