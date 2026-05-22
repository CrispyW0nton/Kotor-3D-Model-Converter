"""
MDL Binary Writer  –  writes KotOR 1/2 .mdl + .mdx files
==========================================================
Phase 7.1 implementation.

References:
  • PyKotor/resource/formats/mdl/io_mdl.py   (4,783 lines, NickHugi/PyKotor)
  • Kotor.NET/Formats/KotorMDL/MDLBinaryWriter.cs  (575 lines)
  • KotorBlender/io_scene_kotor/format/mdl/reader.py  (seedhartha)
  • xoreos/src/aurora/model_nwn.cpp
  • GhostRigger mdl_parser.py  (verified offsets)

Binary layout overview
----------------------
[0 .. 11]      File header   (12 bytes):  unused(4) mdl_size(4) mdx_size(4)
[12 ..]        BASE = 12

Geometry header  (80 bytes, at BASE+0):
  +0  funcptr1   uint32
  +4  funcptr2   uint32
  +8  name       char[32]
  +40 root_off   uint32    (relative to BASE)
  +44 node_count uint32
  +48 unknown0   uint32
  +52 ref_count  uint32
  +56..75        runtime/ref padding
  +76 geo_type   uint8    (MaxTree subtype: 2=model, 5=animation)
  +77..79        padding / unknown bytes (3 bytes)

Model header  (88 bytes, at BASE+80):
  +0   model_type       uint8
  +1   subclassification uint8
  +2   unknown_byte      uint8
  +3   disable_fog       uint8
  +4   unknown0          uint32
  +8   anim_array_off    uint32   (relative to BASE)
  +12  anim_count        uint32
  +16  anim_count2       uint32
  +20  unknown2          uint32
  +24  bb_min            3×float
  +36  bb_max            3×float
  +48  radius            float
  +52  anim_scale        float
  +56  supermodel        char[32]

  Total model header = 88 bytes → ends at BASE+168

Name block header (48 bytes, at BASE+168):
  +0   unknown[4]   4×uint32
  +16  names_off    uint32   (relative to BASE)
  +20  names_count  uint32
  +24  names_count2 uint32
  +28..47           unknown (5×uint32)

  → Name offset table starts at BASE + names_off
  → Each entry: uint32 offset (relative to BASE) pointing to null-term string

Node header  (80 bytes per node):
  +0   node_type    uint16
  +2   index_num    uint16
  +4   node_num     uint16
  +6   pad          uint16
  +8   root_off     uint32   (relative to BASE)
  +12  parent_off   uint32   (relative to BASE)
  +16  position     3×float
  +28  rotation     4×float  (file layout is w,x,y,z; our ModelNode uses x,y,z,w internally —
                               verified against PyKotor _NodeHeader.read, KotorBlender
                               reader.py, and KotOR.js OdysseyModelNodeHeader)
  +44  child_arr_off uint32  (relative to BASE)
  +48  child_cnt    uint32
  +52  child_cnt2   uint32
  +56  ctrl_arr_off uint32   (relative to BASE)
  +60  ctrl_cnt     uint32
  +64  ctrl_cnt2    uint32
  +68  ctrl_data_off uint32  (relative to BASE)
  +72  ctrl_data_cnt uint32
  +76  ctrl_data_cnt2 uint32
  Total: 80 bytes

Mesh header  (332 bytes for K1, 340 bytes for K2 [+8 dirt fields]):
  (see _write_mesh_header for full layout)

Skin header  (100 bytes after mesh header):
  (see _write_skin_header)

Dangly header  (28 bytes after mesh header):
  (see _write_dangly_header)

Emitter header  (224 bytes after base node header):
  (see _write_emitter_header)

MDX companion buffer:
  Per-vertex stride (determined by _mdx_stride):
    Vertex XYZ  3×float32 (always)
    Normal      3×float32 (if has normals)
    UV0         2×float32 (if has UVs)
    LM UV       2×float32 (if has uvs_lm)
    Skin weights 4×float32 + 4×float32 bone_refs (if SKIN)
"""

from __future__ import annotations

import struct
import math
import logging
import copy
from dataclasses import dataclass, field
from io import BytesIO
from typing import Dict, List, Optional, Tuple

from ..geometry.model_data import (
    Animation, AnimEvent, BoneWeight, GameVersion, KotorModel,
    ModelNode, NodeFlags, VertexSkinData,
)

log = logging.getLogger(__name__)

# ─────────────────────────────  Constants  ──────────────────────────────────
#
# PC function pointer pairs — verified against KotorBlender types.py
# (`io_scene_kotor/format/mdl/types.py` in OpenKotOR/kotorblender) and
# PyKotor's ``io_mdl._TrimeshHeader`` K1/K2 function pointer constants.
#
# There are FOUR distinct FP-pair families in a KotOR binary MDL:
#
#   1. MODEL_FN_PTR  — the TOP-LEVEL geometry header (at BASE + 0).  This is the
#                      one written into the model's outer 80-byte geometry
#                      header.  These values differ between K1/K2 PC vs XBOX.
#   2. ANIM_FN_PTR   — the geometry header embedded in every Animation block.
#                      Completely distinct values from MODEL_FN_PTR.
#   3. MESH_FN_PTR   — the first 8 bytes of every TrimeshHeader (type=MESH).
#                      PyKotor calls these ``K1_FUNCTION_POINTER0/1``.
#   4. SKIN_FN_PTR / DANGLY_FN_PTR — replace MESH_FN_PTR when the node carries
#                      the SKIN or DANGLY flag respectively.
#
# Prior revisions of this writer mixed families (used MODEL_FN_PTR in place of
# MESH_FN_PTR, and a geometry fp2 in place of ANIM_FN_PTR_2), which produces
# files that crash the engine and confuse PyKotor's reader.

# ── Model (top-level geometry header) ────────────────────────────────────────
_K1_MODEL_FP1 = 4273776   # 0x0041BCC0  (MODEL_FN_PTR_1_K1_PC)
_K1_MODEL_FP2 = 4216096   # 0x0040A120  (MODEL_FN_PTR_2_K1_PC)
_K2_MODEL_FP1 = 4285200   # 0x0041E850  (MODEL_FN_PTR_1_K2_PC)
_K2_MODEL_FP2 = 4216320   # 0x0040A200  (MODEL_FN_PTR_2_K2_PC)

# Backwards-compat aliases (legacy name used elsewhere in the module).
_K1_GEOM_FP1 = _K1_MODEL_FP1
_K1_GEOM_FP2 = _K1_MODEL_FP2
_K2_GEOM_FP1 = _K2_MODEL_FP1
_K2_GEOM_FP2 = _K2_MODEL_FP2

# ── Animation geometry header ────────────────────────────────────────────────
# Used for the geometry header embedded inside each animation block.
# Source: KotorBlender types.py ANIM_FN_PTR_{1,2}_K{1,2}_PC.
_K1_ANIM_FP1 = 4273392   # 0x0041BB30  (ANIM_FN_PTR_1_K1_PC)
_K1_ANIM_FP2 = 4451552   # 0x00440F20  (ANIM_FN_PTR_2_K1_PC)  ← NOT 4216096
_K2_ANIM_FP1 = 4284816   # 0x0041E6D0  (ANIM_FN_PTR_1_K2_PC)
_K2_ANIM_FP2 = 4522928   # 0x00451C70  (ANIM_FN_PTR_2_K2_PC)  ← NOT 4216320

# ── Mesh / Skin / Dangly node-type function pointers ─────────────────────────
# These populate the first 8 bytes of every TrimeshHeader subheader.
# Source: PyKotor ``io_mdl._TrimeshHeader.K*_FUNCTION_POINTER0/1`` and
# KotorBlender types.py MESH/SKIN/DANGLY FN_PTR constants.
_K1_MESH_FP1   = 4216656  # 0x00405750
_K1_MESH_FP2   = 4216672  # 0x00405760
_K2_MESH_FP1   = 4216880  # 0x00405830
_K2_MESH_FP2   = 4216896  # 0x00405840

_K1_SKIN_FP1   = 4216592  # 0x00405710
_K1_SKIN_FP2   = 4216608  # 0x00405720
_K2_SKIN_FP1   = 4216816  # 0x004057F0
_K2_SKIN_FP2   = 4216832  # 0x00405800

# NOTE: KotorBlender/PyKotor list the DANGLY pair as (FP1=0x00405740,
# FP2=0x00405730) — fp2 is lower than fp1 on purpose, this is NOT a swap.
_K1_DANGLY_FP1 = 4216640  # 0x00405740
_K1_DANGLY_FP2 = 4216624  # 0x00405730
_K2_DANGLY_FP1 = 4216864  # 0x00405820
_K2_DANGLY_FP2 = 4216848  # 0x00405810


def _mesh_fp_pair(is_k2: bool, flags: int) -> Tuple[int, int]:
    """Return the (fp1, fp2) pair that belongs at the start of a trimesh
    subheader, selected by node flags (SKIN / DANGLY specialisation)."""
    if flags & NodeFlags.SKIN:
        return (_K2_SKIN_FP1, _K2_SKIN_FP2) if is_k2 else (_K1_SKIN_FP1, _K1_SKIN_FP2)
    if flags & NodeFlags.DANGLY:
        return (_K2_DANGLY_FP1, _K2_DANGLY_FP2) if is_k2 else (_K1_DANGLY_FP1, _K1_DANGLY_FP2)
    return (_K2_MESH_FP1, _K2_MESH_FP2) if is_k2 else (_K1_MESH_FP1, _K1_MESH_FP2)

_BASE = 12          # all MDL offsets are relative to byte 12

# Controller type IDs (verified against KotorBlender types.py)
CTRL_POSITION    = 8
CTRL_ORIENTATION = 20
CTRL_SCALE       = 36
CTRL_ALPHA       = 132    # KotorBlender CTRL_MESH_ALPHA
CTRL_SELFILLUM   = 100    # CTRL_MESH_SELFILLUMCOLOR (r,g,b)
CTRL_COLOR       = 76

# ─────────────────────────────  Helper writers  ──────────────────────────────

def _wu32(val: int) -> bytes:
    return struct.pack('<I', val & 0xFFFFFFFF)

def _wi32(val: int) -> bytes:
    return struct.pack('<i', val)

def _wu16(val: int) -> bytes:
    return struct.pack('<H', val & 0xFFFF)

def _wf32(val: float) -> bytes:
    if not math.isfinite(val):
        val = 0.0
    return struct.pack('<f', val)

def _wstr(s: str, n: int) -> bytes:
    """Encode string into n-byte null-padded ASCII field."""
    b = s.encode('ascii', errors='replace')[:n]
    return b.ljust(n, b'\x00')

def _align4(buf: BytesIO) -> None:
    """Pad BytesIO buffer to 4-byte alignment."""
    pos = buf.tell()
    pad = (4 - (pos % 4)) % 4
    if pad:
        buf.write(b'\x00' * pad)

# ─────────────────────────────  Offset tracking  ─────────────────────────────

@dataclass
class _NodeInfo:
    """Per-node write metadata collected during the first pass."""
    node:              ModelNode
    node_off:          int = 0    # absolute offset of node header in MDL buffer
    child_arr_off:     int = 0    # absolute offset of child pointer array
    ctrl_arr_off:      int = 0    # absolute offset of controller entry array
    ctrl_data_off:     int = 0    # absolute offset of controller float data
    ctrl_data_cnt:     int = 0
    name_index:        int = 0
    parent_off:        int = 0    # absolute offset of parent node (0 if root)
    root_off:          int = 0    # absolute offset of root node
    mesh_faces_off:    int = 0
    mesh_verts_off:    int = 0    # fallback vertex array offset (MDL)
    mdx_data_off:      int = 0    # byte offset into MDX buffer for this node
    mdx_stride:        int = 0    # bytes per vertex in MDX
    skin_bm_off:       int = 0    # bone_map float array offset (in MDL)
    skin_bm_cnt:       int = 0
    dangly_cst_off:    int = 0    # constraint float array offset (in MDL)
    dangly_cst_cnt:    int = 0


# ─────────────────────────────  Main writer  ─────────────────────────────────

class MDLBinaryWriter:
    """
    Serialise a KotorModel to binary MDL + MDX bytes.

    Usage::

        mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
        # or to files:
        MDLBinaryWriter().write_files(model, '/path/to/model.mdl')
    """

    def write_files(self, model: KotorModel, mdl_path: str) -> None:
        """Write MDL and MDX files to disk (MDX path derived from mdl_path)."""
        from pathlib import Path
        mdl_bytes, mdx_bytes = self.write(model)
        p = Path(mdl_path)
        p.write_bytes(mdl_bytes)
        mdx_path = p.with_suffix('.mdx')
        mdx_path.write_bytes(mdx_bytes)
        log.debug(f"Wrote {len(mdl_bytes)} B MDL + {len(mdx_bytes)} B MDX → {mdl_path}")

    def write(self, model: KotorModel) -> Tuple[bytes, bytes]:
        """
        Returns (mdl_bytes, mdx_bytes).

        Algorithm (mirrors Kotor.NET MDLBinaryWriter):
          1. Flatten node tree → ordered name list
          2. Write MDX vertex buffer (all mesh nodes concatenated)
          3. Write MDL:
             a. 12-byte file header  (sizes patched at end)
             b. Geometry header (80 B)
             c. Model header    (88 B)
             d. Name block      (48 B + offset table + strings)
             e. For each node (DFS): node header, child ptr array,
                ctrl array, ctrl data, type-specific data
             f. Animation offset array
             g. For each animation: anim geometry header + anim model
                header + event array + anim nodes
          4. Patch mdl_size / mdx_size in file header
        """
        self._model = model
        self._is_k2 = (model.game_version == GameVersion.K2)
        self._child_arr_data_locs: Dict[int, int] = {}  # id(node) → abs pos of child ptr array data

        # ── 1. Collect nodes (DFS pre-order) ────────────────────────────────
        self._nodes: List[ModelNode] = []
        self._node_off: Dict[int, int] = {}   # id(node) → MDL offset
        self._node_info: Dict[int, _NodeInfo] = {}  # id(node) → _NodeInfo

        def _collect(n: ModelNode):
            self._nodes.append(n)
            for c in n.children:
                _collect(c)

        if model.root_node:
            _collect(model.root_node)

        self._node_index_by_name: Dict[str, int] = {}
        for idx, nd in enumerate(self._nodes):
            nm = (nd.name or '').lower()
            if nm and nm not in self._node_index_by_name:
                self._node_index_by_name[nm] = idx

        # ── 2. Build name list (deduplicated, preserving DFS order) ─────────
        self._names: List[str] = []
        self._name_idx: Dict[str, int] = {}
        for nd in self._nodes:
            nm = nd.name.lower() if nd.name else 'unnamed'
            if nm not in self._name_idx:
                self._name_idx[nm] = len(self._names)
                self._names.append(nm)
        # Also add animation node names
        for anim in model.animations:
            for an in anim.nodes:
                nm = an.name.lower() if an.name else 'unnamed'
                if nm not in self._name_idx:
                    self._name_idx[nm] = len(self._names)
                    self._names.append(nm)

        # ── 3. Build MDX buffer ──────────────────────────────────────────────
        self._mdx_buf = BytesIO()
        self._node_mdx: Dict[int, Tuple[int, int]] = {}  # id(node) → (offset, stride)
        for nd in self._nodes:
            if nd.flags & NodeFlags.MESH and nd.vertices:
                self._write_mdx_node(nd)

        mdx_bytes = self._mdx_buf.getvalue()

        # ── 4. Write MDL ─────────────────────────────────────────────────────
        buf = BytesIO()

        # 4a. File header placeholder (patched later)
        buf.write(b'\x00' * 12)

        # 4b. Geometry header (80 bytes)
        fp1 = _K2_GEOM_FP1 if self._is_k2 else _K1_GEOM_FP1
        fp2 = _K2_GEOM_FP2 if self._is_k2 else _K1_GEOM_FP2
        buf.write(_wu32(fp1))
        buf.write(_wu32(fp2))
        buf.write(_wstr(model.name or 'unnamed', 32))
        self._root_off_patch = buf.tell()  # patch root_off later
        buf.write(_wu32(0))                # root_node_off (patched)
        buf.write(_wu32(len(self._nodes))) # node_count
        # MaxTree subtype byte lives at geometry header +0x4C.  The K1 engine's
        # AsModel() masks this byte with 0x7F and requires value 2 before
        # InputBinary::Read writes model fields through the returned pointer.
        buf.write(b'\x00' * (76 - (buf.tell() - _BASE)))
        buf.write(b'\x02')                 # geometry_type = 2 (model)
        buf.write(b'\x00' * (80 - (buf.tell() - _BASE)))

        # 4c. Model header (88 bytes at BASE+80)
        assert buf.tell() == _BASE + 80, f"Model header at wrong offset: {buf.tell()}"
        buf.write(struct.pack('B', model.model_type & 0xFF))
        buf.write(struct.pack('B', getattr(model, 'subclassification', 0) & 0xFF))
        buf.write(struct.pack('B', getattr(model, 'unknown_byte', 0) & 0xFF))
        buf.write(struct.pack('B', 1 if model.disable_fog else 0))
        buf.write(_wu32(0))               # unknown0
        self._anim_arr_off_patch = buf.tell()   # anim_array_off (patched)
        buf.write(_wu32(0))
        buf.write(_wu32(len(model.animations)))  # anim_count
        buf.write(_wu32(len(model.animations)))  # anim_count2
        buf.write(_wu32(0))               # unknown2
        # Bounding box
        bb_min = model.bb_min or (0.0, 0.0, 0.0)
        bb_max = model.bb_max or (0.0, 0.0, 0.0)
        buf.write(struct.pack('<fff', *bb_min))
        buf.write(struct.pack('<fff', *bb_max))
        buf.write(_wf32(getattr(model, 'radius', 0.0)))
        buf.write(_wf32(model.anim_scale or 1.0))
        buf.write(_wstr(model.supermodel or 'NULL', 32))
        # Pad to exactly 88 bytes
        _written = buf.tell() - (_BASE + 80)
        if _written < 88:
            buf.write(b'\x00' * (88 - _written))

        # 4d. Name block (48 bytes at BASE+168)
        assert buf.tell() == _BASE + 168, f"Name block at wrong offset: {buf.tell()}"
        # 4 unknown uint32s
        buf.write(b'\x00' * 16)
        self._names_arr_off_patch = buf.tell()   # names_off (patched)
        buf.write(_wu32(0))
        buf.write(_wu32(len(self._names)))
        buf.write(_wu32(len(self._names)))
        # 5 more unknown uint32s
        buf.write(b'\x00' * 20)
        assert buf.tell() == _BASE + 216, f"After name block: {buf.tell()}"

        # Write name offset table + strings
        names_table_off = buf.tell() - _BASE  # relative to BASE
        # First pass: write placeholder offsets
        names_table_start = buf.tell()
        for _ in self._names:
            buf.write(_wu32(0))  # patched below
        # Write strings
        name_str_offsets: List[int] = []
        for nm in self._names:
            name_str_offsets.append(buf.tell() - _BASE)
            buf.write(nm.encode('ascii', errors='replace') + b'\x00')
        _align4(buf)
        # Patch names_off and offset table
        end = buf.tell()
        buf.seek(self._names_arr_off_patch)
        buf.write(_wu32(names_table_off))
        buf.seek(names_table_start)
        for off in name_str_offsets:
            buf.write(_wu32(off))
        buf.seek(end)

        # ── 4e. Write node tree ──────────────────────────────────────────────
        root_off = self._write_node_tree(buf, model.root_node)
        # Patch root_off in geometry header
        end = buf.tell()
        buf.seek(self._root_off_patch)
        buf.write(_wu32(root_off))
        buf.seek(end)

        # ── 4f. Animation offset array ───────────────────────────────────────
        anim_arr_rel = buf.tell() - _BASE
        end = buf.tell()
        buf.seek(self._anim_arr_off_patch)
        buf.write(_wu32(anim_arr_rel))
        buf.seek(end)

        # Placeholder anim offsets (patched after writing anims)
        anim_off_table_start = buf.tell()
        for _ in model.animations:
            buf.write(_wu32(0))

        # ── 4g. Write animations ─────────────────────────────────────────────
        anim_offsets: List[int] = []
        for anim in model.animations:
            anim_offsets.append(buf.tell() - _BASE)
            self._write_animation(buf, anim)

        # Patch anim offset table
        end = buf.tell()
        buf.seek(anim_off_table_start)
        for off in anim_offsets:
            buf.write(_wu32(off))
        buf.seek(end)

        # ── 4h. Patch file header ────────────────────────────────────────────
        mdl_buf = buf.getvalue()
        mdl_size = len(mdl_buf) - _BASE
        mdx_size = len(mdx_bytes)
        mdl_buf = (b'\x00' * 4
                   + struct.pack('<I', mdl_size)
                   + struct.pack('<I', mdx_size)
                   + mdl_buf[12:])

        log.debug(f"MDLBinaryWriter: {model.name!r} → MDL {len(mdl_buf)} B, "
                  f"MDX {mdx_size} B, {len(self._nodes)} nodes, "
                  f"{len(model.animations)} anims")

        return mdl_buf, mdx_bytes

    def build(self, model: KotorModel) -> Tuple[bytes, bytes]:
        """Alias for write() — returns (mdl_bytes, mdx_bytes).

        Many tests call writer.build(model); this is identical to write(model).
        """
        return self.write(model)

    # ─────────────────────────────  MDX  ────────────────────────────────────

    def _mdx_stride_for(self, node: ModelNode) -> Tuple[int, Dict[str, int]]:
        """
        Compute MDX vertex stride and channel offsets for a mesh node.

        Channel layout (matches KotorBlender types.py MDX_FLAG_* values):
          offset 0        : XYZ       3×float32  12 bytes  (always)
          offset 12       : Normal    3×float32  12 bytes  (if normals)
          offset 24/12    : UV0       2×float32   8 bytes  (if uvs)
          ...
          Skin weights come after geometry channels.

        Returns (stride_bytes, channel_offsets_dict).
        channel_offsets_dict keys: 'v', 'n', 'uv', 'lm', 'sw', 'br'
        Values are byte offsets within one vertex stride (0xFFFFFFFF = absent).
        """
        ABSENT = 0xFFFFFFFF
        offsets: Dict[str, int] = {
            'v':  0,        # XYZ always at 0
            'n':  ABSENT,
            'uv': ABSENT,
            'lm': ABSENT,
            'sw': ABSENT,   # skin weights (4×float)
            'br': ABSENT,   # bone refs (4×float)
        }
        off = 12  # after XYZ

        if node.normals:
            offsets['n'] = off
            off += 12

        if node.uvs:
            offsets['uv'] = off
            off += 8

        if node.uvs_lm:
            offsets['lm'] = off
            off += 8

        if node.flags & NodeFlags.SKIN and node.skin_data:
            offsets['sw'] = off
            off += 16   # 4×float weights
            offsets['br'] = off
            off += 16   # 4×float bone refs

        # Align stride to 4-byte boundary (KotOR always does this)
        stride = (off + 3) & ~3
        return stride, offsets

    def _write_mdx_node(self, node: ModelNode) -> None:
        """Write one mesh node's vertex data into the MDX buffer."""
        stride, offsets = self._mdx_stride_for(node)
        mdx_start = self._mdx_buf.tell()
        ABSENT = 0xFFFFFFFF

        vert_cnt = len(node.vertices)
        for i in range(vert_cnt):
            row = bytearray(stride)

            # XYZ
            vx, vy, vz = node.vertices[i]
            struct.pack_into('<fff', row, offsets['v'], vx, vy, vz)

            # Normal
            if offsets['n'] != ABSENT and i < len(node.normals):
                nx, ny, nz = node.normals[i]
                struct.pack_into('<fff', row, offsets['n'], nx, ny, nz)

            # UV0
            if offsets['uv'] != ABSENT and i < len(node.uvs):
                u, v = node.uvs[i]
                struct.pack_into('<ff', row, offsets['uv'], u, v)

            # Lightmap UV
            if offsets['lm'] != ABSENT and i < len(node.uvs_lm):
                u, v = node.uvs_lm[i]
                struct.pack_into('<ff', row, offsets['lm'], u, v)

            # Skin weights + bone refs
            if (offsets['sw'] != ABSENT and offsets['br'] != ABSENT
                    and i < len(node.skin_data)):
                sd = node.skin_data[i]
                wts = [0.0, 0.0, 0.0, 0.0]
                brs = [-1.0, -1.0, -1.0, -1.0]
                for k, bw in enumerate(sd.influences[:4]):
                    wts[k] = float(bw.weight)
                    brs[k] = float(bw.bone_index)
                struct.pack_into('<ffff', row, offsets['sw'], *wts)
                struct.pack_into('<ffff', row, offsets['br'], *brs)

            self._mdx_buf.write(bytes(row))

        self._node_mdx[id(node)] = (mdx_start, stride)

    # ─────────────────────────────  Node tree  ──────────────────────────────

    def _write_node_tree(self, buf: BytesIO,
                         root: Optional[ModelNode]) -> int:
        """
        Write all geometry nodes DFS.
        Returns offset of root node (relative to BASE), or 0 if no root.

        Two-pass strategy:
          Pass 1: Write every node header + type-specific data + ctrl arrays.
                  Record each node's absolute offset.
                  Leave child pointer arrays as placeholder zeros.
          Pass 2: Patch child pointer arrays now that all node offsets are known.
                  Also patch root_off and parent_off fields.
        """
        if root is None:
            return 0

        # Collect DFS order
        ordered: List[ModelNode] = []
        def _dfs(n: ModelNode):
            ordered.append(n)
            for c in n.children:
                _dfs(c)
        _dfs(root)

        # Pass 1: write all node headers + type-specific data, record offsets
        node_abs_off: Dict[int, int] = {}           # id(node) → absolute offset
        child_arr_patches: Dict[int, int] = {}       # id(node) → abs position of child_arr_off field
        root_off_patches: Dict[int, int] = {}        # id(node) → abs position of root_off field
        parent_off_patches: Dict[int, int] = {}      # id(node) → abs position of parent_off field

        for nd in ordered:
            _align4(buf)
            node_abs_off[id(nd)] = buf.tell()
            self._write_one_node_pass1(
                buf, nd,
                child_arr_patches, root_off_patches, parent_off_patches)

        # Pass 2: patch root_off, parent_off, and child pointer arrays
        root_abs = node_abs_off[id(ordered[0])]
        cur_end = buf.tell()

        for nd in ordered:
            nd_abs = node_abs_off[id(nd)]
            parent_abs = node_abs_off.get(id(nd.parent), 0)

            # Patch root_off
            if id(nd) in root_off_patches:
                buf.seek(root_off_patches[id(nd)])
                buf.write(_wu32(root_abs - _BASE))

            # Patch parent_off
            if id(nd) in parent_off_patches:
                buf.seek(parent_off_patches[id(nd)])
                buf.write(_wu32(parent_abs - _BASE if parent_abs else 0))

        buf.seek(cur_end)

        # Patch child pointer arrays (written after all nodes, or at end of each node body)
        # We already wrote them inline in pass1; now overwrite with real values.
        # The child ptr arrays were written right after the node body; their locations
        # were stored in child_arr_patches as the position of the child_arr_off field.
        # We need to seek to each child array and write correct child offsets.
        # The arrays themselves were written as placeholder zeros inline.
        # We need the actual arrays' locations — they were written as part of the node body.
        # Retrieve from our per-node child_arr_info stored during pass1.
        for nd in ordered:
            if not nd.children:
                continue
            arr_loc = self._child_arr_data_locs.get(id(nd))
            if arr_loc is None:
                continue
            buf.seek(arr_loc)
            for child in nd.children:
                c_abs = node_abs_off.get(id(child), 0)
                buf.write(_wu32(c_abs - _BASE if c_abs else 0))

        buf.seek(cur_end)
        return root_abs - _BASE

    def _write_one_node_pass1(self, buf: BytesIO, node: ModelNode,
                               child_arr_patches: Dict[int, int],
                               root_off_patches: Dict[int, int],
                               parent_off_patches: Dict[int, int]) -> None:
        """
        Write a single node: header + type-specific data + child ptr array +
        controller arrays.  Forward references (root_off, parent_off, child
        ptr values) are written as 0 and patched in pass 2.
        """
        node_start = buf.tell()

        nm = (node.name or 'unnamed').lower()
        name_idx = self._name_idx.get(nm, 0)

        # ── Node header  (80 bytes) ──────────────────────────────────────────
        buf.write(_wu16(node.flags))
        buf.write(_wu16(name_idx))   # index_num
        buf.write(_wu16(name_idx))   # node_num
        buf.write(_wu16(0))          # pad

        root_off_patches[id(node)] = buf.tell()
        buf.write(_wu32(0))          # root_off (patched in pass 2)
        parent_off_patches[id(node)] = buf.tell()
        buf.write(_wu32(0))          # parent_off (patched in pass 2)

        px, py, pz = node.position if node.position else (0.0, 0.0, 0.0)
        buf.write(struct.pack('<fff', px, py, pz))

        # Rotation: internal tuple is (x, y, z, w); on-disk layout is W-first.
        # Verified against three independent references, all of which read the
        # quaternion in W → X → Y → Z order after the node position field:
        #   • PyKotor  ``_NodeHeader.read`` (io_mdl.py): reads ``orientation.w``,
        #     ``orientation.x``, ``orientation.y``, ``orientation.z`` in turn.
        #   • KotorBlender ``reader.py``   (format/mdl/reader.py)
        #   • KotOR.js     ``OdysseyModelNodeHeader.ts``
        # So the writer must emit W first.  Do NOT swap.
        rx, ry, rz, rw = (node.rotation if node.rotation
                          else (0.0, 0.0, 0.0, 1.0))
        buf.write(struct.pack('<ffff', rw, rx, ry, rz))

        # Child array placeholder
        child_arr_patch = buf.tell()
        child_arr_patches[id(node)] = child_arr_patch
        buf.write(_wu32(0))                           # child_arr_off (patched)
        buf.write(_wu32(len(node.children)))          # child_cnt
        buf.write(_wu32(len(node.children)))          # child_cnt2

        # Controller array placeholder
        ctrl_arr_patch = buf.tell()
        buf.write(_wu32(0))                           # ctrl_arr_off (patched)
        ctrl_count = len(node.controllers)
        buf.write(_wu32(ctrl_count))
        buf.write(_wu32(ctrl_count))

        # Controller data placeholder
        ctrl_data_patch = buf.tell()
        buf.write(_wu32(0))                           # ctrl_data_off (patched)
        ctrl_data_cnt = self._count_ctrl_data(node)
        buf.write(_wu32(ctrl_data_cnt))
        buf.write(_wu32(ctrl_data_cnt))

        assert buf.tell() == node_start + 80, (
            f"Node header wrong size: {buf.tell() - node_start}")

        # ── Type-specific data ───────────────────────────────────────────────
        if node.flags & NodeFlags.EMITTER:
            self._write_emitter_header(buf, node)

        if node.flags & NodeFlags.REFERENCE:
            self._write_reference_header(buf, node)

        if node.flags & NodeFlags.MESH:
            self._write_mesh_header(buf, node)

        # ── Child pointer array (data) ───────────────────────────────────────
        # Write placeholder zeros; pass 2 will overwrite with real offsets.
        _align4(buf)
        child_arr_data_off = buf.tell() - _BASE
        if not hasattr(self, '_child_arr_data_locs'):
            self._child_arr_data_locs: Dict[int, int] = {}
        self._child_arr_data_locs[id(node)] = buf.tell()
        for _ in node.children:
            buf.write(_wu32(0))   # placeholder; patched in pass 2

        # Patch child_arr_off in node header
        end = buf.tell()
        buf.seek(child_arr_patch)
        buf.write(_wu32(child_arr_data_off))
        buf.seek(end)

        # ── Controller array + data ──────────────────────────────────────────
        self._write_controllers(buf, node, ctrl_arr_patch, ctrl_data_patch)

    def _count_ctrl_data(self, node: ModelNode) -> int:
        """Count total float entries in controller data pool."""
        total = 0
        for ctrl in node.controllers:
            rows = len(ctrl.get('times', []))
            cols = ctrl.get('columns', 1)
            total += rows          # time keys
            total += rows * cols   # value data
        return total

    def _write_controllers(self, buf: BytesIO, node: ModelNode,
                           arr_patch: int, data_patch: int) -> None:
        """Write controller entry array and controller data pool."""
        if not node.controllers:
            return

        # Build controller entries
        # Each entry = 16 bytes:
        #   type(4) unknown(2) row_count(2) time_off(2) data_off(2) columns(1) pad(1) pad2(2)
        # Source: mdl_parser._parse_controllers

        _align4(buf)
        ctrl_arr_off = buf.tell() - _BASE
        # Controller entry stubs (patched with offsets below)
        entries_start = buf.tell()
        for ctrl in node.controllers:
            buf.write(b'\x00' * 16)

        _align4(buf)
        ctrl_data_off = buf.tell() - _BASE
        data_start = buf.tell()

        # Write time keys + values for all controllers
        ctrl_meta: List[Tuple[int, int]] = []   # (time_pool_off, data_pool_off)
        running = 0

        for ctrl in node.controllers:
            times  = ctrl.get('times', [])
            values = ctrl.get('values', [])
            cols   = ctrl.get('columns', 1)
            rows   = len(times)

            time_off = running
            for t in times:
                buf.write(_wf32(float(t)))
                running += 1

            val_off = running
            for row in values:
                for col in range(cols):
                    v = row[col] if col < len(row) else 0.0
                    buf.write(_wf32(float(v)))
                running += cols

            ctrl_meta.append((time_off, val_off))

        end = buf.tell()

        # Patch controller entries
        buf.seek(entries_start)
        for (ctrl, (t_off, v_off)) in zip(node.controllers, ctrl_meta):
            ctype = ctrl.get('type', 0)
            cols  = ctrl.get('columns', 1)
            rows  = len(ctrl.get('times', []))
            buf.write(_wu32(ctype))
            buf.write(_wu16(0))            # unknown
            buf.write(_wu16(rows))         # row_count
            buf.write(_wu16(t_off & 0xFFFF))
            buf.write(_wu16(v_off & 0xFFFF))
            buf.write(struct.pack('B', cols & 0x0F))
            buf.write(b'\x00' * 3)         # pad

        buf.seek(entries_start - (entries_start - (buf.tell())))  # reset
        buf.seek(end)

        # Patch ctrl_arr_off and ctrl_data_off in node header
        buf.seek(arr_patch)
        buf.write(_wu32(ctrl_arr_off))
        buf.seek(data_patch)
        buf.write(_wu32(ctrl_data_off))
        buf.seek(end)

    # ─────────────────────────────  Mesh header  ────────────────────────────

    def _write_mesh_header(self, buf: BytesIO, node: ModelNode) -> None:
        """
        Write the mesh header matching the exact parser layout
        (verified against mdl_parser._parse_mesh field-by-field).

        Exact layout:
          +0    funcptr1/2        (8 B)
          +8    faces off/cnt/cnt2 (12 B)
          +20   bb_min            (12 B)
          +32   bb_max            (12 B)
          +44   radius            (4 B)
          +48   avg_position      (12 B)
          +60   diffuse           (12 B)
          +72   ambient           (12 B)
          +84   transparency_hint (4 B)
          +88   tex_name          (32 B)
          +120  lm_name           (32 B)
          +152  unknown0          (24 B)   opaque bytes preserved from read;
                                           NOT two 12-byte bitmap names
          +176  vic array         (12 B)   off/cnt/cnt2 (zeros)
          +188  vo array          (12 B)   off/cnt/cnt2 (zeros)
          +200  inv array         (12 B)   off/cnt/cnt2 (zeros)
          +212  {-1,-1,0}         (12 B)   unknown
          +224  saber vals        (8 B)    unknown
          +232  animate_uv        (4 B)    UV animation flag
          +236  uv_dir_x          (4 B)
          +240  uv_dir_y          (4 B)
          +244  uv_jitter         (4 B)
          +248  uv_jitter_speed   (4 B)
          +252  mdx_data_size     (4 B)
          +256  mdx_data_bitmap   (4 B)
          +260  MDX offsets[11]   (44 B)   11×uint32
          +304  vert_cnt          (2 B)    uint16
          +306  tex_cnt           (2 B)    uint16
          +308  has_lightmap      (1 B)
          +309  rotate_texture    (1 B)
          +310  background_geometry (1 B)
          +311  has_shadow        (1 B)
          +312  beaming           (1 B)
          +313  render            (1 B)
          [K2 only]:
          +314  dirt_enabled      (1 B)
          +315  padding           (1 B)
          +316  dirt_texture      (2 B)
          +318  dirt_coord_space  (2 B)
          +320  hide_in_holograms (1 B)
          +321  padding           (1 B)
          +314/322  2 pad bytes
          +316/324  total_area    (4 B)
          +320/328  unknown       (4 B)
          +324/332  mdx_data_off  (4 B)  ← byte offset into MDX buffer
          +328/336  verts_off     (4 B)  ← MDL vertex fallback array

          Followed by:
            face array (face_cnt × 32 B)
            MDL vertex array (vert_cnt × 12 B)
          Then skin/dangly headers if applicable.
        """
        # Mesh-subheader FPs differ by node flag family (MESH vs SKIN vs DANGLY).
        # Using the TOP-LEVEL geometry fp pair here (the old behaviour) produces
        # files that the KotOR engine refuses to load because the runtime vtable
        # dispatch in ``CMDLMesh`` / ``CMDLSkinMesh`` matches on these FPs.
        fp1, fp2 = _mesh_fp_pair(self._is_k2, int(node.flags))

        vert_cnt  = len(node.vertices)
        face_cnt  = len(node.faces)
        tex_name  = (node.texture or '').lower()
        lm_name   = (node.lightmap or '').lower()
        # NOTE: the 24 bytes at mesh-header offset +152 are NOT two 12-byte
        # bitmap name slots.  PyKotor (and KotorBlender) parse them as an
        # opaque ``unknown0`` block (``reader.read_bytes(24)``).  Writing
        # nul-terminated text there can be mis-interpreted by downstream
        # readers and validators.  We preserve any bytes we captured at load
        # time via ``node.mesh_unknown0``; otherwise we emit 24 zero bytes.
        mesh_unknown0: bytes = bytes(getattr(node, 'mesh_unknown0', b'') or b'')
        if len(mesh_unknown0) < 24:
            mesh_unknown0 = mesh_unknown0.ljust(24, b'\x00')
        else:
            mesh_unknown0 = mesh_unknown0[:24]

        bb_min  = getattr(node, 'mesh_bb_min', None) or (0.0, 0.0, 0.0)
        bb_max  = getattr(node, 'mesh_bb_max', None) or (0.0, 0.0, 0.0)
        avg_pt  = getattr(node, 'mesh_average_point', None) or (0.0, 0.0, 0.0)
        diffuse = node.diffuse or (1.0, 1.0, 1.0)
        ambient = node.ambient or (0.0, 0.0, 0.0)
        tex_cnt = max(1, getattr(node, 'tex_count', 1))

        # MDX channel layout
        if node.vertices:
            mdx_off, mdx_stride = self._node_mdx.get(id(node), (0, 0))
        else:
            mdx_off, mdx_stride = 0, 0

        _, ch_offsets = self._mdx_stride_for(node)
        ABSENT = 0xFFFFFFFF

        # 11-slot MDX channel offset table (slot order from parser):
        #   [0] xyz  [1] normal  [2] vert_color  [3] uv0  [4] lm_uv
        #   [5] uv2  [6] uv3  [7..10] tangent spaces
        tvert_offs = [
            ch_offsets['v'],        # [0] xyz
            ch_offsets['n'],        # [1] normal
            ABSENT,                 # [2] vertex color
            ch_offsets['uv'],       # [3] UV0
            ch_offsets['lm'],       # [4] LM UV
            ABSENT,                 # [5] UV2
            ABSENT,                 # [6] UV3
            ABSENT, ABSENT, ABSENT, ABSENT,   # [7-10] tangent spaces
        ]

        # MDX bitmap
        mdx_bitmap = 0x0001  # XYZ always present
        if ch_offsets['n'] != ABSENT:
            mdx_bitmap |= 0x0020
        if ch_offsets['uv'] != ABSENT:
            mdx_bitmap |= 0x0002
        if ch_offsets['lm'] != ABSENT:
            mdx_bitmap |= 0x0004

        # ── Write header fields in exact parser order ────────────────────────
        mesh_hdr_start = buf.tell()

        # +0  fp1/fp2
        buf.write(_wu32(fp1))
        buf.write(_wu32(fp2))

        # +8  faces descriptor (off / cnt / cnt2)
        faces_off_patch = buf.tell()
        buf.write(_wu32(0))             # faces_off (patched later)
        buf.write(_wu32(face_cnt))
        buf.write(_wu32(face_cnt))

        # +20 bounding box + radius + avg_pos
        buf.write(struct.pack('<fff', *bb_min))
        buf.write(struct.pack('<fff', *bb_max))
        buf.write(_wf32(getattr(node, 'mesh_radius', 0.0)))
        buf.write(struct.pack('<fff', *avg_pt))

        # +60 diffuse + ambient + transparency_hint
        buf.write(struct.pack('<fff', *diffuse))
        buf.write(struct.pack('<fff', *ambient))
        buf.write(_wu32(getattr(node, 'transparency_hint', 0)))

        # +88  tex_name (32 B) + lm_name (32 B)
        buf.write(_wstr(tex_name, 32))
        buf.write(_wstr(lm_name, 32))

        # +152: 24-byte ``unknown0`` block.  Previously written as two 12-byte
        # ASCII strings ("bm3_name" / "bm4_name") — that layout does not match
        # any known reference reader (PyKotor reads opaque bytes here, so do
        # KotorBlender and Kotor.NET).  Emit the raw bytes captured at load
        # time so round-trip tests produce identical files.
        buf.write(mesh_unknown0)

        # +176 vic/vo/inv arrays (3 × 12 B = 36 B) + {-1,-1,0} (12 B) + saber (8 B)
        buf.write(b'\x00' * 36)          # vic + vo + inv
        buf.write(b'\xff\xff\xff\xff' * 2 + b'\x00' * 4)  # {-1,-1,0}
        buf.write(b'\x00' * 8)           # saber vals

        # +232 UV animation fields (20 B)
        buf.write(_wu32(1 if getattr(node, 'animate_uv', False) else 0))
        buf.write(_wf32(getattr(node, 'uv_dir_x', 0.0)))
        buf.write(_wf32(getattr(node, 'uv_dir_y', 0.0)))
        buf.write(_wf32(getattr(node, 'uv_jitter', 0.0)))
        buf.write(_wf32(getattr(node, 'uv_jitter_speed', 0.0)))

        # +252 mdx_data_size + mdx_data_bitmap
        buf.write(_wu32(mdx_stride))
        buf.write(_wu32(mdx_bitmap))

        # +260 11 MDX channel offsets (44 B)
        for off in tvert_offs:
            buf.write(_wu32(off))

        # +304 vert_cnt + tex_cnt
        buf.write(_wu16(vert_cnt))
        buf.write(_wu16(tex_cnt))

        # +308 6 flag bytes
        buf.write(struct.pack('B', 1 if node.has_lightmap else 0))
        buf.write(struct.pack('B', 1 if node.rotate_texture else 0))
        buf.write(struct.pack('B', 1 if getattr(node, 'background_geometry', False) else 0))
        buf.write(struct.pack('B', 1 if node.has_shadow else 0))
        buf.write(struct.pack('B', 1 if node.beaming else 0))
        buf.write(struct.pack('B', 1 if node.render else 0))

        # K2-specific fields (8 B)
        if self._is_k2:
            buf.write(struct.pack('B', 1 if getattr(node, 'dirt_enabled', False) else 0))
            buf.write(b'\x00')
            buf.write(_wu16(getattr(node, 'dirt_texture', 0)))
            buf.write(_wu16(getattr(node, 'dirt_coord_space', 0)))
            buf.write(struct.pack('B', 1 if getattr(node, 'hide_in_holograms', False) else 0))
            buf.write(b'\x00')

        # 2 pad + 4 total_area + 4 unknown
        buf.write(b'\x00' * 2)
        buf.write(_wf32(getattr(node, 'mesh_total_area', 0.0)))
        buf.write(b'\x00' * 4)

        # mdx_data_off + verts_off
        buf.write(_wu32(mdx_off))           # MDX byte offset

        verts_off_patch = buf.tell()
        buf.write(_wu32(0))                 # MDL vertex array (patched below)

        # ── Skin header (if SKIN) — must be at o = right after fixed mesh header ──
        if node.flags & NodeFlags.SKIN:
            self._write_skin_header(buf, node)

        # ── Dangly header (if DANGLY) — must be at o = right after fixed mesh header ──
        if node.flags & NodeFlags.DANGLY:
            self._write_dangly_header(buf, node)

        # ── AABB: 4-byte ``offset_to_aabb`` field + minimal tree ─────────────
        # PyKotor ``_Node.read`` reads a single int32 immediately after the
        # trimesh/skin/dangly headers when ``type_id & AABB`` is set.  Without
        # this field walkmesh nodes fail to parse (reader gets misaligned and
        # subsequent data / children pointers go to garbage offsets).
        if node.flags & NodeFlags.AABB:
            self._write_aabb_section(buf, node)

        # ── Face array — placed after skin/dangly headers, offset patched above ──
        _align4(buf)
        faces_off_abs = buf.tell()
        for i, (v1, v2, v3) in enumerate(node.faces):
            mat = node.face_mats[i] if i < len(node.face_mats) else 0
            # 32-byte face entry:
            #   normal(12) plane_dist(4) material(4) adj_faces(6) vertices(6)
            buf.write(struct.pack('<fff', 0.0, 0.0, 1.0))  # face normal
            buf.write(_wf32(0.0))                           # plane distance
            buf.write(_wu32(mat))
            buf.write(b'\x00' * 6)                          # adjacent faces (runtime)
            buf.write(struct.pack('<HHH', v1, v2, v3))

        # Patch faces_off
        end = buf.tell()
        buf.seek(faces_off_patch)
        buf.write(_wu32(faces_off_abs - _BASE))
        buf.seek(end)

        # ── MDL vertex array (fallback XYZ only) ────────────────────────────
        _align4(buf)
        verts_off_abs = buf.tell()
        for vx, vy, vz in node.vertices:
            buf.write(struct.pack('<fff', vx, vy, vz))

        # Patch verts_off
        end = buf.tell()
        buf.seek(verts_off_patch)
        buf.write(_wu32(verts_off_abs - _BASE))
        buf.seek(end)

    def _write_skin_header(self, buf: BytesIO, node: ModelNode) -> None:
        """
        Write the 100-byte skin sub-header (``_SkinmeshHeader`` in PyKotor
        parlance) that immediately follows the mesh header for SKIN nodes,
        plus the qbone / tbone / bonemap data arrays pointed at by it.

        Layout — verified field-for-field against PyKotor
        ``io_mdl._SkinmeshHeader.read`` / ``.write`` (100 bytes on the nose):

          +0   unknown_weights       int32
          +4   unknown3              int32
          +8   unknown4              int32
          +12  offset_to_mdx_weights uint32  (MDX weight-channel byte offset)
          +16  offset_to_mdx_bones   uint32  (MDX bone-ref-channel byte offset)
          +20  offset_to_bonemap     uint32  (rel BASE)
          +24  bonemap_count         uint32
          +28  offset_to_qbones      uint32
          +32  qbones_count          uint32
          +36  qbones_count2         uint32
          +40  offset_to_tbones      uint32
          +44  tbones_count          uint32
          +48  tbones_count2         uint32
          +52  offset_to_unknown0    uint32
          +56  unknown0_count        uint32
          +60  unknown0_count2       uint32
          +64  bones[16]             uint16[16]  (32 B — NOT 17!)
          +96  unknown1              uint32      (4 B pad — NOT 2!)
          = 100 B

        Previous revisions wrote ``bone_parts[17]`` + 2 pad bytes.  That summed
        to 100 B by coincidence but desynchronised PyKotor's reader on the
        ``bones`` tuple length and trailing padding.
        """
        _, ch_offsets = self._mdx_stride_for(node)

        sw_off  = ch_offsets.get('sw', 0xFFFFFFFF)
        sbr_off = ch_offsets.get('br', 0xFFFFFFFF)

        # Bonemap entries.  ``node.bone_map_floats`` is the authoritative
        # float32 array captured at load; fall back to per-index floats derived
        # from the bone name list when we're writing a fresh model.
        bone_map_names  = list(node.bone_map or [])
        bonemap_floats  = list(getattr(node, 'bone_map_floats', []) or [])
        bm_cnt          = len(bonemap_floats) if bonemap_floats else len(bone_map_names)
        if not bonemap_floats and bone_map_names:
            bonemap_floats = [float(self._skin_bone_node_index(nm)) for nm in bone_map_names]

        qbones = list(getattr(node, 'qbone_list', []) or [])
        tbones = list(getattr(node, 'tbone_list', []) or [])

        skin_hdr_start = buf.tell()

        # +0  unknown_weights / unknown3 / unknown4 (3×int32)
        buf.write(b'\x00' * 12)
        # +12 MDX channel offsets (weights / bone refs)
        buf.write(_wu32(sw_off))
        buf.write(_wu32(sbr_off))
        # +20 bonemap desc (patched below)
        bm_off_patch = buf.tell()
        buf.write(_wu32(0))
        buf.write(_wu32(bm_cnt))
        # +28 qbones desc (patched below)
        qb_off_patch = buf.tell()
        buf.write(_wu32(0))
        buf.write(_wu32(len(qbones)))
        buf.write(_wu32(len(qbones)))
        # +40 tbones desc (patched below)
        tb_off_patch = buf.tell()
        buf.write(_wu32(0))
        buf.write(_wu32(len(tbones)))
        buf.write(_wu32(len(tbones)))
        # +52 offset_to_unknown0 / counts (zeros — we don't emit this array)
        buf.write(b'\x00' * 12)
        # +64 bones[16] uint16 — partial-skin "head bone" references.
        # Unused slots are sentinel 0xFFFF (= -1 as int16), matching the
        # defaults PyKotor assigns in ``_SkinmeshHeader.__init__``.
        for i in range(16):
            bone_idx = self._skin_bone_node_index(bone_map_names[i]) if i < len(bone_map_names) else -1
            if bone_idx >= 0:
                buf.write(_wu16(bone_idx))
            else:
                buf.write(_wu16(0xFFFF))
        # +96 unknown1 uint32 pad
        buf.write(_wu32(0))

        assert buf.tell() - skin_hdr_start == 100, (
            f"Skin sub-header wrong size: {buf.tell() - skin_hdr_start}")

        # ── Data arrays pointed-to by the header above ────────────────────
        # Bonemap float32 array.  Count = bm_cnt (may be 0 for skin nodes
        # whose weights use direct bone indices instead of a remap table).
        _align4(buf)
        if bm_cnt > 0:
            bm_abs = buf.tell()
            for v in bonemap_floats[:bm_cnt]:
                buf.write(_wf32(float(v)))
            # Pad the array up to bm_cnt entries (if provided list is short).
            pad_entries = bm_cnt - len(bonemap_floats)
            for _ in range(max(0, pad_entries)):
                buf.write(_wf32(-1.0))
            end = buf.tell()
            buf.seek(bm_off_patch)
            buf.write(_wu32(bm_abs - _BASE))
            buf.seek(end)

        # qbones: Vector4 each (16 bytes)
        if qbones:
            _align4(buf)
            qb_abs = buf.tell()
            for qx, qy, qz, qw in qbones:
                buf.write(struct.pack('<ffff', qx, qy, qz, qw))
            end = buf.tell()
            buf.seek(qb_off_patch)
            buf.write(_wu32(qb_abs - _BASE))
            buf.seek(end)

        # tbones: Vector3 each (12 bytes)
        if tbones:
            _align4(buf)
            tb_abs = buf.tell()
            for tx, ty, tz in tbones:
                buf.write(struct.pack('<fff', tx, ty, tz))
            end = buf.tell()
            buf.seek(tb_off_patch)
            buf.write(_wu32(tb_abs - _BASE))
            buf.seek(end)

    def _skin_bone_node_index(self, name: str) -> int:
        """Return the node id this writer will emit for a skin palette bone."""
        key = str(name or '').lower()
        if not key:
            return -1
        return int(getattr(self, '_node_index_by_name', {}).get(key, -1))

    def _write_dangly_header(self, buf: BytesIO, node: ModelNode) -> None:
        """
        Write the 28-byte dangly header that follows the mesh header.
        Layout (verified against mdl_parser._parse_dangly):
          +0  constraints_off uint32
          +4  constraints_cnt uint32
          +8  constraints_cnt2 uint32
          +12 displacement float
          +16 tightness float
          +20 period float
          +24 unknown uint32
        """
        constraints = node.dangly_constraints or []
        # Convert back to 0-255 range for binary format
        cst_denorm = [max(0.0, min(255.0, c * 255.0)) for c in constraints]
        cst_cnt = len(cst_denorm)

        cst_off_patch = buf.tell()
        buf.write(_wu32(0))             # constraints_off (patched)
        buf.write(_wu32(cst_cnt))
        buf.write(_wu32(cst_cnt))
        buf.write(_wf32(node.dangly_displacement or 0.0))
        buf.write(_wf32(node.dangly_tightness or 0.25))
        buf.write(_wf32(node.dangly_period or 1.0))
        buf.write(_wu32(0))             # unknown (runtime pointer)

        # Constraint float array
        _align4(buf)
        cst_abs = buf.tell()
        for c in cst_denorm:
            buf.write(_wf32(c))

        end = buf.tell()
        buf.seek(cst_off_patch)
        buf.write(_wu32(cst_abs - _BASE))
        buf.seek(end)

    def _write_aabb_section(self, buf: BytesIO, node: ModelNode) -> None:
        """
        Write the 4-byte AABB tree offset field plus a minimal AABB tree
        immediately after it.

        Layout (per PyKotor ``_Node.write`` / MDLOps):
          +0  offset_to_aabb  int32  (= current_pos - 12 + 4, i.e. the byte
                                     right after this field, relative to BASE)
          +4  aabb_tree       N × 40-byte entries

        Each AABB tree entry (40 B) is:
          bounding_box_min   3×float (12)
          bounding_box_max   3×float (12)
          leaf_face_index    int32   (4)   (-1 for internal nodes)
          split_plane        int32   (4)   (axis index: 0/1/2, or -1 for leaves)
          offset_to_left     int32   (4)   (relative to BASE)
          offset_to_right    int32   (4)

        We do not currently parse the source AABB tree into ModelNode, so we
        synthesise a minimal 1-leaf tree spanning the mesh bounding box.
        This is sufficient to keep the file structurally valid and PyKotor's
        reader aligned; real walkmesh content preservation is a Phase-4 task.
        """
        # The offset stored in the field is a BASE-relative pointer to the
        # AABB tree, which begins immediately after the 4-byte field itself.
        tree_off_rel = (buf.tell() + 4) - _BASE
        buf.write(_wi32(tree_off_rel))

        # Compute a mesh-local bounding box from the node's vertex cloud.
        if node.vertices:
            xs = [v[0] for v in node.vertices]
            ys = [v[1] for v in node.vertices]
            zs = [v[2] for v in node.vertices]
            bb_min = (min(xs), min(ys), min(zs))
            bb_max = (max(xs), max(ys), max(zs))
        else:
            bb_min = getattr(node, 'mesh_bb_min', None) or (0.0, 0.0, 0.0)
            bb_max = getattr(node, 'mesh_bb_max', None) or (0.0, 0.0, 0.0)

        # One-leaf AABB: leaf_face_index=0 (or -1 if no faces), no children,
        # split_plane=-1 (sentinel for "leaf").
        leaf_face = 0 if node.faces else -1
        buf.write(struct.pack('<fff', *bb_min))
        buf.write(struct.pack('<fff', *bb_max))
        buf.write(_wi32(leaf_face))
        buf.write(_wi32(-1))   # split_plane (-1 = leaf)
        buf.write(_wi32(0))    # offset_to_left  (0 = none)
        buf.write(_wi32(0))    # offset_to_right (0 = none)

    def _write_emitter_header(self, buf: BytesIO, node: ModelNode) -> None:
        """
        Write the 224-byte emitter header (verified against mdl_parser._parse_emitter).
        """
        ep = node.emitter_params
        buf.write(_wf32(ep.get('deadspace', 0.0)))
        buf.write(_wf32(ep.get('blastradius', 0.0)))
        buf.write(_wf32(ep.get('blastlength', 0.0)))
        buf.write(_wu32(ep.get('numbranches', 0)))
        buf.write(_wf32(ep.get('controlptsmoothing', 0.0)))
        buf.write(_wu32(ep.get('xgrid', 0)))
        buf.write(_wu32(ep.get('ygrid', 0)))
        buf.write(_wu32(ep.get('spawntype', 0)))
        buf.write(_wstr(ep.get('update', ''), 32))
        buf.write(_wstr(ep.get('emitter_render', ''), 32))
        buf.write(_wstr(ep.get('blend', ''), 32))
        buf.write(_wstr(ep.get('texture', ''), 32))
        buf.write(_wstr(ep.get('chunkname', ''), 16))
        buf.write(_wu32(ep.get('twosidedtex', 0)))
        buf.write(_wu32(ep.get('loop', 0)))
        buf.write(_wu16(ep.get('renderorder', 0)))
        buf.write(struct.pack('B', ep.get('frameblending', 0)))
        buf.write(_wstr(ep.get('depth_texture_name', ''), 32))
        buf.write(b'\x00')             # padding
        # Build flags bitmask from individual flag fields
        flags = 0
        _flag_map = [
            ('p2p', 0x0001), ('p2p_sel', 0x0002), ('affected_wind', 0x0004),
            ('tinted', 0x0008), ('bounce', 0x0010), ('random', 0x0020),
            ('inherit', 0x0040), ('inheritvel', 0x0080), ('inherit_local', 0x0100),
            ('splat', 0x0200), ('inherit_part', 0x0400), ('depth_texture', 0x0800),
        ]
        for fname, fbit in _flag_map:
            if ep.get(fname, 0):
                flags |= fbit
        buf.write(_wu32(flags))

    def _write_reference_header(self, buf: BytesIO, node: ModelNode) -> None:
        """Write the 36-byte reference node header."""
        ep = node.emitter_params
        ref_model  = ep.get('ref_model', '')
        reattach   = 1 if ep.get('reattachable', False) else 0
        buf.write(_wstr(ref_model, 32))
        buf.write(_wu32(reattach))

    # ─────────────────────────────  Animations  ─────────────────────────────

    def _write_animation(self, buf: BytesIO, anim: Animation) -> None:
        """
        Write one animation block.
        Layout mirrors the model geometry + model headers:
          Geometry header (80 B) — uses anim fp1/fp2
          Animation model header (52 B)
          Event array
          Animation node tree
        """
        anim_nodes = self._animation_nodes_with_hierarchy(anim, self._nodes)
        anim_root_name = anim.anim_root or (anim_nodes[0].name if anim_nodes else '')
        node_count = len(anim_nodes)

        fp1 = _K2_ANIM_FP1 if self._is_k2 else _K1_ANIM_FP1
        fp2 = _K2_ANIM_FP2 if self._is_k2 else _K1_ANIM_FP2

        geo_start = buf.tell()

        # Geometry header (80 bytes)
        buf.write(_wu32(fp1))
        buf.write(_wu32(fp2))
        buf.write(_wstr(anim.name or 'default', 32))
        anim_root_off_patch = buf.tell()
        buf.write(_wu32(0))              # root_node_off (patched)
        buf.write(_wu32(node_count))
        # Animation geometry headers use the same MaxTree subtype byte at
        # +0x4C; stock animation blocks use value 5.
        buf.write(b'\x00' * (76 - (buf.tell() - geo_start)))
        buf.write(b'\x05')               # geometry_type = 5 (animation)
        buf.write(b'\x00' * (80 - (buf.tell() - geo_start)))

        # Animation model header (starts at geo_start+80)
        assert buf.tell() == geo_start + 80
        buf.write(_wf32(anim.length or 0.0))
        buf.write(_wf32(anim.transition_time or 0.25))
        buf.write(_wstr(anim_root_name, 32))

        events_off_patch = buf.tell()
        buf.write(_wu32(0))              # events_off (patched)
        buf.write(_wu32(len(anim.events)))
        buf.write(_wu32(len(anim.events)))

        # Events array
        _align4(buf)
        if anim.events:
            events_off_abs = buf.tell()
            for ev in anim.events:
                buf.write(_wf32(ev.time))
                buf.write(_wstr(ev.name or '', 32))
            # Patch events_off
            end = buf.tell()
            buf.seek(events_off_patch)
            buf.write(_wu32(events_off_abs - _BASE))
            buf.seek(end)

        # Animation node tree
        if anim_nodes:
            anim_node_abs: Dict[int, int] = {}
            root_off = self._write_anim_node_tree(buf, anim_nodes[0], anim_node_abs)

            # Patch root_off in geo header
            end = buf.tell()
            buf.seek(anim_root_off_patch)
            buf.write(_wu32(root_off))
            buf.seek(end)

    def _animation_nodes_with_hierarchy(self, anim: Animation, all_nodes: List[ModelNode]) -> List[ModelNode]:
        """Return animation nodes as a geometry-hierarchy tree.

        Retarget preview can use flat animation-node lists because playback
        resolves by name. Binary MDL readers walk only descendants of the
        animation root, so export must add controllerless ancestor stubs.
        """
        source_nodes = list(getattr(anim, 'nodes', None) or [])
        if not source_nodes:
            return []

        geom_by_name = {
            str(getattr(node, 'name', '') or '').lower(): node
            for node in (all_nodes or [])
            if getattr(node, 'name', '')
        }
        order_by_name = {
            str(getattr(node, 'name', '') or '').lower(): index
            for index, node in enumerate(all_nodes or [])
            if getattr(node, 'name', '')
        }
        local_by_name: Dict[str, ModelNode] = {}

        def clone_anim_node(node: ModelNode) -> ModelNode:
            cloned = copy.copy(node)
            cloned.children = []
            cloned.parent = None
            cloned.controllers = list(getattr(node, 'controllers', []) or [])
            return cloned

        def clone_stub_node(node: ModelNode) -> ModelNode:
            cloned = node.clone_shallow() if hasattr(node, 'clone_shallow') else copy.copy(node)
            cloned.children = []
            cloned.parent = None
            cloned.controllers = []
            return cloned

        for node in source_nodes:
            key = str(getattr(node, 'name', '') or '').lower()
            if key:
                local_by_name[key] = clone_anim_node(node)

        for key in list(local_by_name):
            geom = geom_by_name.get(key)
            parent = getattr(geom, 'parent', None) if geom is not None else None
            while parent is not None:
                parent_key = str(getattr(parent, 'name', '') or '').lower()
                if parent_key and parent_key not in local_by_name:
                    local_by_name[parent_key] = clone_stub_node(parent)
                parent = getattr(parent, 'parent', None)

        for node in local_by_name.values():
            node.children = []
            node.parent = None

        roots: List[ModelNode] = []
        for key, node in local_by_name.items():
            geom = geom_by_name.get(key)
            parent = getattr(geom, 'parent', None) if geom is not None else None
            linked = False
            while parent is not None:
                parent_key = str(getattr(parent, 'name', '') or '').lower()
                parent_node = local_by_name.get(parent_key)
                if parent_node is not None:
                    node.parent = parent_node
                    parent_node.children.append(node)
                    linked = True
                    break
                parent = getattr(parent, 'parent', None)
            if not linked:
                roots.append(node)

        root_key = str(getattr(anim, 'anim_root', '') or '').lower()
        requested_root = local_by_name.get(root_key) if root_key else None
        root_node = requested_root if requested_root in roots else None
        if root_node is None and roots:
            root_node = min(
                roots,
                key=lambda node: order_by_name.get(
                    str(getattr(node, 'name', '') or '').lower(),
                    1_000_000,
                ),
            )
        if root_node is not None:
            for node in list(roots):
                if node is root_node:
                    continue
                node.parent = root_node
                root_node.children.append(node)

        ordered: List[ModelNode] = []
        seen = set()

        def visit(node: ModelNode) -> None:
            nid = id(node)
            if nid in seen:
                return
            seen.add(nid)
            ordered.append(node)
            node.children.sort(
                key=lambda child: order_by_name.get(
                    str(getattr(child, 'name', '') or '').lower(),
                    1_000_000,
                )
            )
            for child in node.children:
                visit(child)

        if root_node is not None:
            visit(root_node)
        for node in sorted(
            local_by_name.values(),
            key=lambda item: order_by_name.get(
                str(getattr(item, 'name', '') or '').lower(),
                1_000_000,
            ),
        ):
            visit(node)
        return ordered

    def _write_anim_node_tree(self, buf: BytesIO, root: ModelNode,
                               anim_node_abs: Dict[int, int]) -> int:
        """Write animation nodes (two-pass); returns root offset (relative to BASE)."""
        # Flatten
        ordered: List[ModelNode] = []
        seen: set[int] = set()

        def _dfs(n):
            nid = id(n)
            if nid in seen:
                return
            seen.add(nid)
            ordered.append(n)
            for c in n.children:
                _dfs(c)
        _dfs(root)

        # Pass 1: write all nodes, record positions
        root_off_patches: Dict[int, int] = {}
        parent_off_patches: Dict[int, int] = {}
        anim_child_data_locs: Dict[int, int] = {}

        for nd in ordered:
            _align4(buf)
            anim_node_abs[id(nd)] = buf.tell()
            self._write_one_anim_node_pass1(
                buf, nd,
                root_off_patches, parent_off_patches, anim_child_data_locs)

        # Pass 2: patch root_off, parent_off, and child ptr arrays
        root_abs = anim_node_abs[id(ordered[0])]
        cur_end = buf.tell()

        for nd in ordered:
            parent_abs = anim_node_abs.get(id(nd.parent), 0)
            if id(nd) in root_off_patches:
                buf.seek(root_off_patches[id(nd)])
                buf.write(_wu32(root_abs - _BASE))
            if id(nd) in parent_off_patches:
                buf.seek(parent_off_patches[id(nd)])
                buf.write(_wu32(parent_abs - _BASE if parent_abs else 0))

        buf.seek(cur_end)

        for nd in ordered:
            if not nd.children:
                continue
            arr_loc = anim_child_data_locs.get(id(nd))
            if arr_loc is None:
                continue
            buf.seek(arr_loc)
            for child in nd.children:
                c_abs = anim_node_abs.get(id(child), 0)
                buf.write(_wu32(c_abs - _BASE if c_abs else 0))

        buf.seek(cur_end)
        return root_abs - _BASE

    def _write_one_anim_node_pass1(self, buf: BytesIO, node: ModelNode,
                                    root_off_patches: Dict[int, int],
                                    parent_off_patches: Dict[int, int],
                                    anim_child_data_locs: Dict[int, int]) -> None:
        """Write a single animation node (80-byte header + controllers only).

        Real KotOR animation nodes are always DUMMY (type 1) regardless of what
        the geometry node carries.  Writing MESH/SKIN flags here would cause
        PyKotor (and the original NWN engine) to expect a full TrimeshHeader
        after the 80-byte base, which we do not emit for animation nodes.
        """
        node_start = buf.tell()
        nm = (node.name or 'unnamed').lower()
        name_idx = self._name_idx.get(nm, 0)

        # Animation nodes must always be DUMMY (0x0001) — see NWN binary spec
        # and PyKotor io_mdl.py.  Mesh flags belong only in geometry nodes.
        anim_flags = 1  # NodeType.DUMMY
        buf.write(_wu16(anim_flags))
        buf.write(_wu16(name_idx))
        buf.write(_wu16(name_idx))
        buf.write(_wu16(0))

        root_off_patches[id(node)] = buf.tell()
        buf.write(_wu32(0))          # root_off (patched pass 2)
        parent_off_patches[id(node)] = buf.tell()
        buf.write(_wu32(0))          # parent_off (patched pass 2)

        px, py, pz = node.position or (0.0, 0.0, 0.0)
        buf.write(struct.pack('<fff', px, py, pz))
        rx, ry, rz, rw = node.rotation or (0.0, 0.0, 0.0, 1.0)
        buf.write(struct.pack('<ffff', rw, rx, ry, rz))

        # Children
        child_arr_patch = buf.tell()
        buf.write(_wu32(0))
        buf.write(_wu32(len(node.children)))
        buf.write(_wu32(len(node.children)))

        ctrl_arr_patch = buf.tell()
        buf.write(_wu32(0))
        ctrl_count = len(node.controllers)
        buf.write(_wu32(ctrl_count))
        buf.write(_wu32(ctrl_count))

        ctrl_data_patch = buf.tell()
        buf.write(_wu32(0))
        ctrl_data_cnt = self._count_ctrl_data(node)
        buf.write(_wu32(ctrl_data_cnt))
        buf.write(_wu32(ctrl_data_cnt))

        assert buf.tell() == node_start + 80

        # Child pointer array (placeholder zeros; patched in pass 2)
        _align4(buf)
        child_arr_data_off = buf.tell() - _BASE
        anim_child_data_locs[id(node)] = buf.tell()
        for _ in node.children:
            buf.write(_wu32(0))
        end = buf.tell()
        buf.seek(child_arr_patch)
        buf.write(_wu32(child_arr_data_off))
        buf.seek(end)

        self._write_controllers(buf, node, ctrl_arr_patch, ctrl_data_patch)
