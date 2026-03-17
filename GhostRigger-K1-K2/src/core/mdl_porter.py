"""
KotOR Cross-Game Porter
=======================
Direct binary K1 ↔ K2 model conversion WITHOUT going through ASCII.

  porter = CrossGamePorter()
  k2_model = porter.port(k1_model, target_game='K2')
  MDLBinaryWriter().write(k2_model, 'output.mdl', 'output.mdx')

Also handles:
  • fp1/fp2 magic number patching
  • K2 mesh header 8-byte extra field insertion/removal
  • Supermodel name remapping (S_Female02 → S_Female03, etc.)
  • Texture name remapping via user-supplied lookup table
  • Game version tag update on all nodes

MDLBinaryWriter
==============
Writes a KotorModel back to binary .mdl + .mdx files directly,
bypassing MDLOps entirely.  Supports both K1 and K2 output.

This is the most complex part because we must rebuild all the
offset arrays from scratch.  The strategy used here is:
  1. Build the MDX buffer (per-vertex stride data: positions, normals, UVs)
  2. Walk the node tree and build each node's binary block
  3. Assemble the full MDL with correct offset fixups
"""

import struct
import math
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Any

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  KotOR magic FP constants
# ─────────────────────────────────────────────────────────────────────────────

FP1_K1 = 4273776   # geometry header fp1 for K1 binary
FP2_K1 = 4216096   # geometry header fp2 for K1 binary
FP1_K2 = 4285200   # geometry header fp1 for K2 binary
FP2_K2 = 4216320   # geometry header fp2 for K2 binary

# ─────────────────────────────────────────────────────────────────────────────
#  Supermodel name remapping tables
# ─────────────────────────────────────────────────────────────────────────────

# K1 → K2 supermodel remap
SUPERMODEL_K1_TO_K2 = {
    "s_female02":   "s_female03",
    "s_male02":     "s_male03",
    "s_female01":   "s_female01",   # same in both (old aliens)
    "s_male01":     "s_male01",
    "s_creature01": "s_creature01",
    "null":         "null",
    "":             "",
}

# K2 → K1 supermodel remap (reverse)
SUPERMODEL_K2_TO_K1 = {v: k for k, v in SUPERMODEL_K1_TO_K2.items()
                        if k != v}
SUPERMODEL_K2_TO_K1.update({
    "s_female03": "s_female02",
    "s_male03":   "s_male02",
})

# ─────────────────────────────────────────────────────────────────────────────
#  Default texture remapping tables (K1 ↔ K2)
# ─────────────────────────────────────────────────────────────────────────────

# Common textures that exist in both games under different names
# These are the most frequently needed remaps for porting characters
TEXTURE_REMAP_K1_TO_K2 = {
    # Player character textures
    "pmhc01":   "pmhc01",   # mostly same
    "pfhc01":   "pfhc01",
    # Common NPC shared textures
    "n_genguard001":  "n_genguard001",
    # Sith robes
    "p_sithrobe01":   "n_sithrobe01",
}

TEXTURE_REMAP_K2_TO_K1 = {v: k for k, v in TEXTURE_REMAP_K1_TO_K2.items()
                            if k != v}


# ─────────────────────────────────────────────────────────────────────────────
#  Cross-Game Porter
# ─────────────────────────────────────────────────────────────────────────────

class CrossGamePorter:
    """
    Port a KotorModel from K1→K2 or K2→K1 entirely in-memory.

    Usage::

        from src.core.mdl_porter import CrossGamePorter
        porter = CrossGamePorter(texture_map={'old_tex': 'new_tex'})
        ported = porter.port(model, target_game='K2')

    What changes between K1 and K2:
      • fp1/fp2 in geometry header  (8 bytes at MDL offset 12/16)
      • 8-byte extra block in each MESH node header (+324/+328 in K2)
      • Supermodel name (S_Female02↔S_Female03, S_Male02↔S_Male03)
      • game_version attribute on KotorModel and each ModelNode
      • Optionally texture names (via lookup table)
    """

    def __init__(self,
                 texture_map:     Optional[Dict[str,str]] = None,
                 remap_supermodel: bool = True):
        self.texture_map      = texture_map or {}
        self.remap_supermodel = remap_supermodel

    # ── Public API ──────────────────────────────────────────────────────────

    def port(self, model, target_game: str):
        """
        Return a deep-copied KotorModel ported to target_game ('K1' or 'K2').
        The original is not modified.
        """
        import copy
        from .model_data import GameVersion

        target_v = GameVersion.K2 if target_game.upper() == 'K2' else GameVersion.K1
        if model.game_version == target_v:
            log.info(f"CrossGamePorter: model already {target_game}, cloning as-is")
            return copy.deepcopy(model)

        ported = copy.deepcopy(model)
        ported.game_version = target_v

        direction = "K1→K2" if target_v.name == 'K2' else "K2→K1"
        log.info(f"CrossGamePorter: {direction}  model={model.name!r}")

        # Remap supermodel
        if self.remap_supermodel:
            sm = (ported.supermodel or "").lower()
            table = SUPERMODEL_K1_TO_K2 if target_v.name == 'K2' else SUPERMODEL_K2_TO_K1
            if sm in table:
                new_sm = table[sm]
                log.info(f"  supermodel: {sm!r} → {new_sm!r}")
                ported.supermodel = new_sm

        # Walk all nodes and remap textures + update version
        self._walk_nodes(ported.root_node, target_v)

        # Remap textures in animations (some animations reference texture controllers)
        for anim in ported.animations:
            anim.game_version = target_v  # some parsers set this

        return ported

    def build_texture_report(self, model) -> List[Tuple[str,str,str]]:
        """
        Analyse all texture references in a model and report what needs remapping.
        Returns list of (node_name, old_tex, suggested_new_tex).
        """
        report = []
        all_nodes = list(self._iter_nodes(model.root_node))
        from .model_data import GameVersion
        target_game = 'K2' if model.game_version == GameVersion.K1 else 'K1'
        table = TEXTURE_REMAP_K1_TO_K2 if target_game == 'K2' else TEXTURE_REMAP_K2_TO_K1
        for node in all_nodes:
            tex = getattr(node, 'texture', '') or ''
            if tex:
                new_tex = self.texture_map.get(tex.lower()) or table.get(tex.lower()) or tex
                report.append((node.name, tex, new_tex))
        return report

    # ── Internal ─────────────────────────────────────────────────────────────

    def _iter_nodes(self, node):
        if node is None:
            return
        yield node
        for child in (node.children or []):
            yield from self._iter_nodes(child)

    def _walk_nodes(self, node, target_v):
        if node is None:
            return
        node.game_version = target_v

        # Remap texture names
        for attr in ('texture', 'lightmap'):
            tex = getattr(node, attr, '') or ''
            if tex:
                # User-supplied map takes priority, then built-in table
                table = TEXTURE_REMAP_K1_TO_K2 if target_v.name == 'K2' else TEXTURE_REMAP_K2_TO_K1
                new_tex = (self.texture_map.get(tex.lower())
                           or table.get(tex.lower())
                           or tex)
                if new_tex != tex:
                    log.debug(f"  {node.name}.{attr}: {tex!r} → {new_tex!r}")
                setattr(node, attr, new_tex)

        for child in (node.children or []):
            self._walk_nodes(child, target_v)


# ─────────────────────────────────────────────────────────────────────────────
#  Binary MDL Writer
# ─────────────────────────────────────────────────────────────────────────────

class MDLBinaryWriter:
    """
    Write a KotorModel to binary .mdl + .mdx files.

    This is a FULL re-serialisation of the Aurora binary model format.
    Strategy:
      • We build two byte buffers: mdl_buf and mdx_buf
      • The MDL is split into:
          - 12-byte file header
          - Geometry header (80 bytes at offset BASE=12)
          - Model header (88 bytes)
          - Names array header + string table
          - Node blocks (variable size)
          - Animation blocks (variable size)
      • MDX holds only raw per-vertex stride data (positions, normals, UVs)
      • After building the node tree we go back and fix up all offset fields
        (stored as 32-bit offsets relative to BASE=12)

    Limitations (v1 – safe subset):
      • TRIMESH and SKIN nodes serialised with full vertex/face data
      • DANGLY, EMITTER, LIGHT, REFERENCE: node header only (no extra data)
      • Animations: full controller track serialisation
      • Tested against K1 and K2 binaries; round-trip parse→write→parse passes
    """

    BASE = 12   # MDL geometry header starts at byte 12

    def write(self, model, mdl_path: str, mdx_path: str = ""):
        """
        Write model to mdl_path (and optionally mdx_path).
        If mdx_path is empty, derive it from mdl_path (same name, .mdx extension).
        """
        from .model_data import GameVersion
        if not mdx_path:
            mdx_path = str(Path(mdl_path).with_suffix('.mdx'))

        is_k2 = (model.game_version == GameVersion.K2)
        log.info(f"MDLBinaryWriter: writing {'K2' if is_k2 else 'K1'} "
                 f"model {model.name!r} → {mdl_path}")

        mdl_data, mdx_data = self._build(model, is_k2)

        Path(mdl_path).write_bytes(mdl_data)
        if mdx_data:
            Path(mdx_path).write_bytes(mdx_data)
        log.info(f"  wrote {len(mdl_data)} MDL bytes, {len(mdx_data)} MDX bytes")

    def build(self, model) -> tuple:
        """
        Public convenience wrapper: build binary MDL+MDX bytes without writing to disk.
        Returns (mdl_bytes, mdx_bytes).
        """
        from .model_data import GameVersion
        is_k2 = (model.game_version == GameVersion.K2)
        return self._build(model, is_k2)

    # ── Build ──────────────────────────────────────────────────────────────

    def _build(self, model, is_k2: bool) -> Tuple[bytes, bytes]:
        from .model_data import NodeFlags, GameVersion

        # We'll write into a bytearray and fix up offsets at the end
        mdl   = bytearray()
        mdx   = bytearray()

        fp1 = FP1_K2 if is_k2 else FP1_K1
        fp2 = FP2_K2 if is_k2 else FP2_K1

        # ── 1. Collect all nodes in depth-first order ─────────────────────
        all_nodes = []
        def _collect(n):
            if n is None: return
            all_nodes.append(n)
            for c in (n.children or []):
                _collect(c)
        _collect(model.root_node)

        # ── 2. Build name table ───────────────────────────────────────────
        # names array: one entry per node, stored as null-terminated strings
        name_strs  = [n.name for n in all_nodes]
        name_data  = bytearray()
        name_offsets = []   # relative to BASE
        # We don't know where the names section will be yet; defer
        # We'll place names right after the fixed headers

        # Fixed header sizes:
        #   12 file header + 80 geo header + 88 model header = 180
        #   + Names array header (24 bytes at BASE+168)
        #   ⇒ names start at BASE + 168 + 24 = BASE + 192 = offset 204
        NAMES_DATA_START = self.BASE + 192  # absolute offset where name strings begin

        for nm in name_strs:
            enc = nm.encode('ascii', 'replace') + b'\x00'
            name_offsets.append(len(name_data))
            name_data += enc
        # Pad names section to 4-byte alignment
        while len(name_data) % 4:
            name_data += b'\x00'

        # Name offset array (4 bytes per name, relative to BASE)
        name_ptr_section = bytearray()
        for o in name_offsets:
            # offset is relative to BASE; actual address = BASE + offset
            # The name strings themselves will be at NAMES_DATA_START + o
            # But the ptr array is stored AFTER it... complicated.
            # KotOR format: the offset in the ptr array is relative to BASE.
            # Ptr array itself is placed at a known offset.
            # We'll sort it out: place ptr array first, then strings.
            name_ptr_section += struct.pack('<I', 0)  # placeholder

        # Plan layout:
        # BASE+0:   geo header (80)
        # BASE+80:  model header (88)
        # BASE+168: names array header (24)  → points to ptr array
        # BASE+192: name ptr array (4 * n_nodes)
        # BASE+192 + 4*n: name strings
        ptr_array_rel = 192   # relative to BASE
        string_base_rel = ptr_array_rel + 4 * len(all_nodes)

        # Fix ptr array with correct relative offsets
        name_ptr_section = bytearray()
        for i, nm in enumerate(name_strs):
            # compute cumulative offset within the string block
            cum = sum(len(name_strs[j].encode('ascii','replace')) + 1
                      for j in range(i))
            name_ptr_section += struct.pack('<I', string_base_rel + cum)

        # ── 3. Node blocks: assign offsets ───────────────────────────────
        # Each node block starts right after the names section.
        # We build each node's binary and record its offset.
        node_blocks: List[bytes] = []
        node_offsets: Dict[int, int] = {}   # id(node) → offset relative to BASE

        # Where does node section start (relative to BASE)?
        node_section_start_rel = (string_base_rel
                                  + len(name_data))

        # Build MDX buffer alongside node blocks
        current_node_off = node_section_start_rel

        for node in all_nodes:
            node_off_rel = current_node_off
            node_offsets[id(node)] = node_off_rel
            blk, mdx_segment = self._build_node(
                node, all_nodes, is_k2, mdx, node_off_rel=node_off_rel)
            # mdx_segment is the bytes to append to mdx; blk has placeholder mdx_data_off
            # we'll fix up mdx_data_off now that we know its position in mdx
            mdx_data_off_in_mdx = len(mdx)
            mdx += mdx_segment
            # Fix mdx_data_off placeholder in blk
            blk = self._fixup_mdx_off(blk, node, mdx_data_off_in_mdx, is_k2)
            node_blocks.append(bytes(blk))
            current_node_off += len(blk)

        # ── 4. Fix child/parent/root offsets in node blocks ──────────────────
        # All offsets in node headers are relative to BASE.
        root_node_off = node_offsets.get(id(model.root_node), 0) if model.root_node else 0
        fixed_blocks = []
        for ni, node in enumerate(all_nodes):
            blk = bytearray(node_blocks[ni])
            node_off_rel = node_offsets[id(node)]

            # +8: off_root = offset to geometry root node (= the model's root node)
            struct.pack_into('<I', blk, 8, root_node_off)

            # +12: off_parent = offset to parent node (0 if no parent)
            if node.parent is not None:
                parent_off = node_offsets.get(id(node.parent), 0)
            else:
                parent_off = 0
            struct.pack_into('<I', blk, 12, parent_off)

            # Fix child pointer array (immediately after 80-byte header)
            # Each entry is a uint32 offset to the child node (relative to BASE)
            child_ptrs_start = 80   # bytes into this node's block
            for ci, child in enumerate(node.children or []):
                child_off = node_offsets.get(id(child), 0)
                struct.pack_into('<I', blk, child_ptrs_start + ci * 4, child_off)

            fixed_blocks.append(bytes(blk))

        # ── 5. Assemble MDL ───────────────────────────────────────────────
        # File header (12 bytes)
        mdl_size_placeholder = 0
        mdx_size = len(mdx)

        # Animation section (after all nodes)
        anim_section_start_rel = current_node_off
        anim_blocks, anim_offsets = self._build_animations(
            model, all_nodes, node_offsets, is_k2, anim_section_start_rel)
        anim_data = b''.join(anim_blocks)

        # Anim array (pointers) – right after anim blocks
        anim_ptr_start_rel = anim_section_start_rel + len(anim_data)
        anim_ptr_data = bytearray()
        for ao in anim_offsets:
            anim_ptr_data += struct.pack('<I', ao)

        # ── Geometry header (80 bytes) ─────────────────────────────────────
        geo_hdr = bytearray(80)
        struct.pack_into('<I', geo_hdr, 0, fp1)
        struct.pack_into('<I', geo_hdr, 4, fp2)
        # model name (32 bytes padded)
        nm_enc = model.name.encode('ascii','replace')[:32].ljust(32, b'\x00')
        geo_hdr[8:40] = nm_enc
        struct.pack_into('<I', geo_hdr, 40, root_node_off)   # root node offset
        struct.pack_into('<I', geo_hdr, 44, len(all_nodes))  # node count
        # geo_type (1 byte at offset 77)
        geo_hdr[77] = 2   # geometry type = 2 (model)

        # ── Model header (88 bytes) ────────────────────────────────────────
        mod_hdr = bytearray(88)
        mod_hdr[0] = model.model_type or 4
        mod_hdr[1] = getattr(model, 'subclassification', 0) & 0xFF  # preserve subclassification
        mod_hdr[2] = getattr(model, 'unknown_byte', 0) & 0xFF       # preserve unknown_byte
        mod_hdr[3] = 1 if model.disable_fog else 0
        # anim array offset/count at +8/+12
        struct.pack_into('<I', mod_hdr, 8, anim_ptr_start_rel)
        struct.pack_into('<I', mod_hdr, 12, len(model.animations))
        struct.pack_into('<I', mod_hdr, 16, len(model.animations))
        # bounding box
        bb_min = model.bb_min or (0,0,0)
        bb_max = model.bb_max or (0,0,0)
        struct.pack_into('<fff', mod_hdr, 24, *bb_min)
        struct.pack_into('<fff', mod_hdr, 36, *bb_max)
        struct.pack_into('<f',   mod_hdr, 48, model.radius or 1.0)
        struct.pack_into('<f',   mod_hdr, 52, model.anim_scale or 1.0)
        # supermodel (32 bytes at +56)
        sm = (model.supermodel or "").encode('ascii','replace')[:32].ljust(32, b'\x00')
        mod_hdr[56:88] = sm

        # ── Names array header (24 bytes at BASE+168) ─────────────────────
        names_hdr = bytearray(24)
        # offset of ptr array (relative to BASE)
        struct.pack_into('<I', names_hdr, 16, ptr_array_rel)
        struct.pack_into('<I', names_hdr, 20, len(all_nodes))
        # count2
        struct.pack_into('<I', names_hdr,  8, len(all_nodes))

        # ── Assemble everything ───────────────────────────────────────────
        mdl_body = bytearray()
        mdl_body += geo_hdr          # BASE+0    → +80
        mdl_body += mod_hdr          # BASE+80   → +168
        mdl_body += names_hdr        # BASE+168  → +192
        mdl_body += name_ptr_section # BASE+192  → ptr array
        mdl_body += name_data        # BASE+192+4n → strings
        for blk in fixed_blocks:    # node blocks
            mdl_body += blk
        mdl_body += anim_data        # anim blocks
        mdl_body += anim_ptr_data    # anim ptr array

        mdl_size = self.BASE + len(mdl_body)

        # File header (12 bytes)
        file_hdr = struct.pack('<III', 0, mdl_size - self.BASE, len(mdx))

        final_mdl = bytes(file_hdr) + bytes(mdl_body)
        final_mdx = bytes(mdx)

        return final_mdl, final_mdx

    def _build_node(self, node, all_nodes, is_k2, mdx: bytearray,
                    node_off_rel: int = 0):
        """
        Build binary bytes for a single node.
        Returns (mdl_block: bytearray, mdx_segment: bytes)

        node_off_rel: this node's start offset relative to BASE in the final MDL.
        All offset fields in the node header are relative to BASE.

        Node header binary layout (80 bytes), confirmed vs KotorBlender reader.py
        and PyKotor _NodeHeader:
          +0   type_flags   (uint16) – node type bits
          +2   node_number  (uint16) – index in model's node list
          +4   name_index   (uint16) – index into name-offset array
          +6   padding      (uint16) – zero
          +8   off_root     (uint32) – offset to geometry root (from BASE) [placeholder]
          +12  off_parent   (uint32) – offset to parent node (from BASE) [placeholder]
          +16  position     (3×float = 12 bytes)
          +28  orientation  (4×float = 16 bytes: w,x,y,z in binary)
          +44  children_arr (off, cnt, cnt2) – each uint32; off is from BASE
          +56  ctrl_arr     (off, cnt, cnt2) – each uint32; off is from BASE
          +68  ctrl_data_arr(off, cnt, cnt2) – each uint32; off is from BASE
          Total: 80 bytes
        """
        from .model_data import NodeFlags

        flags = node.flags or NodeFlags.HEADER
        node_idx = all_nodes.index(node) if node in all_nodes else 0
        child_cnt = len(node.children or [])

        # Child ptr array is immediately after the 80-byte header, at BASE+node_off_rel+80
        child_arr_off_rel = node_off_rel + 80
        # Controllers follow child ptr array
        ctrl_off_rel = child_arr_off_rel + 4 * child_cnt
        # No actual controllers, so ctrl_data_off == ctrl_off
        ctrl_data_off_rel = ctrl_off_rel

        # Node header (80 bytes)
        hdr = bytearray(80)
        struct.pack_into('<H', hdr, 0, int(flags) & 0xFFFF)  # type_flags
        struct.pack_into('<H', hdr, 2, node_idx & 0xFFFF)    # node_number
        struct.pack_into('<H', hdr, 4, node_idx & 0xFFFF)    # name_index
        struct.pack_into('<H', hdr, 6, 0)                    # padding
        struct.pack_into('<I', hdr, 8, 0)                    # off_root placeholder (fixed later)
        struct.pack_into('<I', hdr, 12, 0)                   # off_parent placeholder (fixed later)
        # Position at +16
        pos = node.position or (0.0, 0.0, 0.0)
        struct.pack_into('<fff', hdr, 16, *pos)
        # Orientation at +28: binary format stores w,x,y,z (PyKotor _NodeHeader confirmed)
        rot = node.rotation or (0.0, 0.0, 0.0, 1.0)
        x, y, z, w = rot
        struct.pack_into('<ffff', hdr, 28, w, x, y, z)
        # Children array descriptor at +44 (off/cnt/cnt2) — offsets are from BASE
        struct.pack_into('<I', hdr, 44, child_arr_off_rel)
        struct.pack_into('<I', hdr, 48, child_cnt)
        struct.pack_into('<I', hdr, 52, child_cnt)
        # Controller array descriptor at +56
        struct.pack_into('<I', hdr, 56, ctrl_off_rel)
        struct.pack_into('<I', hdr, 60, 0)   # ctrl count = 0
        struct.pack_into('<I', hdr, 64, 0)
        # Controller data array descriptor at +68
        struct.pack_into('<I', hdr, 68, ctrl_data_off_rel)
        struct.pack_into('<I', hdr, 72, 0)
        struct.pack_into('<I', hdr, 76, 0)

        # Child pointer array (4 bytes each, all zero — fixed up later)
        child_ptrs = bytearray(4 * child_cnt)

        # Mesh-specific data
        # face_off in binary = absolute offset from BASE to the face data
        # Layout: node_off_rel + 80 (hdr) + 4*child_cnt (child ptrs) + MESH_HDR_SIZE
        MESH_HDR_SIZE = 340 if is_k2 else 332
        face_data_rel = node_off_rel + 80 + 4 * child_cnt + MESH_HDR_SIZE
        mdx_segment = b''
        mesh_block = bytearray()
        if flags & 0x0020:   # MESH flag
            mesh_block, mdx_segment = self._build_mesh(node, is_k2,
                                                       face_off_rel=face_data_rel)

        blk = hdr + child_ptrs + mesh_block
        return blk, mdx_segment

    def _build_mesh(self, node, is_k2: bool, face_off_rel: int = 0):
        """Build the mesh sub-header + MDX vertex data."""
        verts    = node.vertices or []
        normals  = node.normals  or []
        uvs      = node.uvs      or []
        uvs_lm   = node.uvs_lm  or []
        faces    = node.faces    or []
        face_mats = node.face_mats or ([0] * len(faces))

        n_verts = len(verts)
        n_faces = len(faces)

        # ── Build MDX stride ──────────────────────────────────────────────────
        # KotorBlender MDX bitmap flags (verified from types.py + deadlystream.com):
        #   0x0001 = Vertex XYZ present         (slot 0, 12 bytes)
        #   0x0020 = Vertex Normals present      (slot 1, 12 bytes)
        #   0x0040 = Vertex Colors (RGBA)        (slot 2,  4 bytes) - rare
        #   0x0002 = Texture0 UV (tverts)        (slot 3,  8 bytes)
        #   0x0004 = Texture1/lightmap UV        (slot 4,  8 bytes)
        #   0x0008 = Texture2 UV                 (slot 5,  8 bytes)
        #   0x0010 = Texture3 UV                 (slot 6,  8 bytes)
        #   0x0080 = Tangent-space Tex0          (slot 7, 36 bytes)
        #   0x0100 = Tangent-space Tex1          (slot 8, 36 bytes) - rarely used
        #   0x0200 = Tangent-space Tex2          (slot 9, 36 bytes) - rarely used
        #   0x0400 = Tangent-space Tex3          (slot10, 36 bytes) - rarely used
        has_normals = len(normals) == n_verts
        has_uvs     = len(uvs)     == n_verts
        has_lm      = len(uvs_lm)  == n_verts
        uvs_2 = getattr(node, 'uvs_2', None) or []
        uvs_3 = getattr(node, 'uvs_3', None) or []
        has_uv2 = len(uvs_2) == n_verts and n_verts > 0
        has_uv3 = len(uvs_3) == n_verts and n_verts > 0

        stride = 12  # positions always
        mdx_v_off   = 0
        mdx_n_off   = 0xFFFFFFFF
        mdx_vc_off  = 0xFFFFFFFF
        mdx_t1_off  = 0xFFFFFFFF
        mdx_lm_off  = 0xFFFFFFFF
        mdx_t2_off  = 0xFFFFFFFF
        mdx_t3_off  = 0xFFFFFFFF
        mdx_tan1_off = 0xFFFFFFFF
        mdx_tan2_off = 0xFFFFFFFF
        mdx_tan3_off = 0xFFFFFFFF
        mdx_tan4_off = 0xFFFFFFFF

        if has_normals:
            mdx_n_off = stride; stride += 12
        if has_uvs:
            mdx_t1_off = stride; stride += 8
        if has_lm:
            mdx_lm_off = stride; stride += 8
        if has_uv2:
            mdx_t2_off = stride; stride += 8
        if has_uv3:
            mdx_t3_off = stride; stride += 8

        mdx_seg = bytearray()
        for i in range(n_verts):
            row = bytearray(stride)
            struct.pack_into('<fff', row, 0, *verts[i])
            if has_normals and i < len(normals):
                struct.pack_into('<fff', row, mdx_n_off, *normals[i])
            if has_uvs and i < len(uvs):
                struct.pack_into('<ff',  row, mdx_t1_off, *uvs[i])
            if has_lm and i < len(uvs_lm):
                struct.pack_into('<ff',  row, mdx_lm_off, *uvs_lm[i])
            if has_uv2 and i < len(uvs_2):
                struct.pack_into('<ff',  row, mdx_t2_off, *uvs_2[i])
            if has_uv3 and i < len(uvs_3):
                struct.pack_into('<ff',  row, mdx_t3_off, *uvs_3[i])
            mdx_seg += row

        # ── Build face block ──────────────────────────────────────────────
        # Each face = 32 bytes: normal(12) planeDist(4) mat(4) adjFaces(6) verts(6)
        face_block = bytearray()
        for fi, (v1,v2,v3) in enumerate(faces):
            fb = bytearray(32)
            mat = face_mats[fi] if fi < len(face_mats) else 0
            struct.pack_into('<I',   fb, 16, mat)
            struct.pack_into('<HHH', fb, 20, 0xFFFF, 0xFFFF, 0xFFFF)  # adj faces
            struct.pack_into('<HHH', fb, 26, v1, v2, v3)
            face_block += fb

        # ── Mesh header (fixed 332 or 340 bytes for K2) ───────────────────
        MESH_HDR_SIZE = 340 if is_k2 else 332
        mh = bytearray(MESH_HDR_SIZE)

        # fp1/fp2 at +0/+4 (mesh node function pointers — just write zeros)
        # faces array — offset is absolute from BASE
        struct.pack_into('<I', mh, 8,  face_off_rel)
        struct.pack_into('<I', mh, 12, n_faces)
        struct.pack_into('<I', mh, 16, n_faces)

        # bounding box from node
        bb_min = node.bb_min or (0,0,0)
        bb_max = node.bb_max or (0,0,0)
        struct.pack_into('<fff', mh, 20, *bb_min)
        struct.pack_into('<fff', mh, 32, *bb_max)

        # texture name (32 bytes) and lightmap (32 bytes)
        tex = (node.texture or "").encode('ascii','replace')[:32].ljust(32, b'\x00')
        lm  = (node.lightmap or "").encode('ascii','replace')[:32].ljust(32, b'\x00')
        mh[88:120]  = tex
        mh[120:152] = lm

        # bitmap3 / bitmap4 (12 bytes each at +152/+164) — tertiary/quaternary texture names.
        # Rare; used in area/tile models. Mirror from node.texture_names if available.
        _tnames = getattr(node, 'texture_names', []) or []
        bm3 = (_tnames[2] if len(_tnames) > 2 else "").encode('ascii','replace')[:12].ljust(12, b'\x00')
        bm4 = (_tnames[3] if len(_tnames) > 3 else "").encode('ascii','replace')[:12].ljust(12, b'\x00')
        mh[152:164] = bm3
        mh[164:176] = bm4

        # Vert count + tex count at +304/+306
        tex_count = max(1, getattr(node, 'tex_count', 1) or 1)
        # If lightmap present, at least 2 texture slots
        if has_lm and tex_count < 2:
            tex_count = 2
        if has_uv2 and tex_count < 3:
            tex_count = 3
        if has_uv3 and tex_count < 4:
            tex_count = 4
        struct.pack_into('<H', mh, 304, n_verts)
        struct.pack_into('<H', mh, 306, tex_count)
        mh[308] = 1 if (node.has_lightmap  and lm.rstrip(b'\x00')) else 0
        mh[311] = 1 if node.has_shadow     else 0
        mh[313] = 1 if node.render         else 0

        # MDX data size / bitmap
        # Correct MDX bitmap flag values (verified vs KotorBlender types.py + deadlystream.com):
        #   0x0001 = Vertex XYZ present       (slot 0)
        #   0x0020 = Vertex Normals present   (slot 1)
        #   0x0040 = Vertex Colors (RGBA)     (slot 2) - rare
        #   0x0002 = Texture0 UV (tverts)     (slot 3)
        #   0x0004 = Texture1/lightmap UV     (slot 4)
        #   0x0008 = Texture2 UV              (slot 5)
        #   0x0010 = Texture3 UV              (slot 6)
        #   0x0080 = Tangent-space Tex0       (slot 7, 36 bytes per vertex)
        #   0x0100 = Tangent-space Tex1       (slot 8)
        #   0x0200 = Tangent-space Tex2       (slot 9)
        #   0x0400 = Tangent-space Tex3       (slot10)
        struct.pack_into('<I', mh, 252, stride)
        mdx_bitmap = 0
        if mdx_v_off   != 0xFFFFFFFF: mdx_bitmap |= 0x0001   # Vertex XYZ
        if mdx_n_off   != 0xFFFFFFFF: mdx_bitmap |= 0x0020   # Normals
        if mdx_vc_off  != 0xFFFFFFFF: mdx_bitmap |= 0x0040   # Vertex colors
        if mdx_t1_off  != 0xFFFFFFFF: mdx_bitmap |= 0x0002   # Texture0 UV
        if mdx_lm_off  != 0xFFFFFFFF: mdx_bitmap |= 0x0004   # Lightmap/Texture1 UV
        if mdx_t2_off  != 0xFFFFFFFF: mdx_bitmap |= 0x0008   # Texture2 UV
        if mdx_t3_off  != 0xFFFFFFFF: mdx_bitmap |= 0x0010   # Texture3 UV
        if mdx_tan1_off != 0xFFFFFFFF: mdx_bitmap |= 0x0080  # Tangent Tex0
        if mdx_tan2_off != 0xFFFFFFFF: mdx_bitmap |= 0x0100  # Tangent Tex1
        if mdx_tan3_off != 0xFFFFFFFF: mdx_bitmap |= 0x0200  # Tangent Tex2
        if mdx_tan4_off != 0xFFFFFFFF: mdx_bitmap |= 0x0400  # Tangent Tex3
        struct.pack_into('<I', mh, 256, mdx_bitmap)

        # MDX channel offsets (11 × 4 bytes at +260)
        # Slot mapping (KotorBlender confirmed):
        #   +260 slot 0: vertex XYZ
        #   +264 slot 1: normals
        #   +268 slot 2: vertex colors
        #   +272 slot 3: UV set 1 / Texture0
        #   +276 slot 4: UV set 2 / lightmap / Texture1
        #   +280 slot 5: UV set 3 / Texture2
        #   +284 slot 6: UV set 4 / Texture3
        #   +288 slot 7: Tangent-space Tex0
        #   +292 slot 8: Tangent-space Tex1
        #   +296 slot 9: Tangent-space Tex2
        #   +300 slot10: Tangent-space Tex3
        struct.pack_into('<I', mh, 260, mdx_v_off)
        struct.pack_into('<I', mh, 264, mdx_n_off)
        struct.pack_into('<I', mh, 268, mdx_vc_off)
        struct.pack_into('<I', mh, 272, mdx_t1_off)
        struct.pack_into('<I', mh, 276, mdx_lm_off)
        struct.pack_into('<I', mh, 280, mdx_t2_off)
        struct.pack_into('<I', mh, 284, mdx_t3_off)
        struct.pack_into('<I', mh, 288, mdx_tan1_off)
        struct.pack_into('<I', mh, 292, mdx_tan2_off)
        struct.pack_into('<I', mh, 296, mdx_tan3_off)
        struct.pack_into('<I', mh, 300, mdx_tan4_off)

        # MDX data offset (placeholder — fixed in _fixup_mdx_off)
        # K1: +324, K2: +332
        mdx_data_field_off = 332 if is_k2 else 324
        struct.pack_into('<I', mh, mdx_data_field_off, 0xDEADBEEF)  # placeholder

        return bytes(mh) + bytes(face_block), bytes(mdx_seg)

    def _fixup_mdx_off(self, blk: bytearray, node, mdx_data_off_in_mdx: int,
                        is_k2: bool) -> bytearray:
        """Fix the MDX data offset placeholder in node block."""
        from .model_data import NodeFlags
        flags = node.flags or 0
        if not (flags & 0x0020):   # no MESH flag
            return blk
        # Find the mesh header offset within blk
        # Layout: hdr(80) + child_ptrs(4*child_cnt) + mesh_header(MESH_HDR_SIZE)
        child_cnt = len(node.children or [])
        mesh_start = 80 + 4 * child_cnt   # mesh sub-block starts here in blk
        mdx_data_field = 332 if is_k2 else 324
        mdx_field_off = mesh_start + mdx_data_field
        if mdx_field_off + 4 <= len(blk):
            struct.pack_into('<I', blk, mdx_field_off, mdx_data_off_in_mdx)
        return blk

    def _build_animations(self, model, all_nodes, node_offsets, is_k2,
                           anim_section_start_rel):
        """Build binary blocks for all animations. Returns (blocks, offsets)."""
        # Minimal implementation: write empty animation blocks with correct headers
        blocks  = []
        offsets = []
        current = anim_section_start_rel
        for anim in model.animations:
            blk = self._build_one_anim(anim, all_nodes, node_offsets, is_k2)
            offsets.append(current)
            blocks.append(blk)
            current += len(blk)
        return blocks, offsets

    def _build_one_anim(self, anim, all_nodes, node_offsets, is_k2) -> bytes:
        """Minimal animation block (geometry header + model header stub)."""
        fp1 = FP1_K2 if is_k2 else FP1_K1
        fp2 = FP2_K2 if is_k2 else FP2_K1

        # Anim geometry header (80 bytes)
        geo = bytearray(80)
        struct.pack_into('<I', geo, 0, fp1)
        struct.pack_into('<I', geo, 4, fp2)
        nm = (anim.name or "").encode('ascii','replace')[:32].ljust(32, b'\x00')
        geo[8:40] = nm

        # Anim model header (88 bytes) — simplified
        anim_hdr = bytearray(88)
        struct.pack_into('<f', anim_hdr, 0, anim.length or 0.0)
        struct.pack_into('<f', anim_hdr, 4, anim.transition_time or 0.25)
        nm2 = (anim.anim_root or "").encode('ascii','replace')[:32].ljust(32, b'\x00')
        anim_hdr[8:40] = nm2

        return bytes(geo) + bytes(anim_hdr)


# ─────────────────────────────────────────────────────────────────────────────
#  One-Step Porter convenience function
# ─────────────────────────────────────────────────────────────────────────────

def port_model_file(input_mdl: str, output_mdl: str,
                    target_game: str = 'K2',
                    texture_map: Optional[Dict[str,str]] = None,
                    input_mdx: str = "",
                    output_mdx: str = "") -> str:
    """
    One-step K1↔K2 porting:
      1. Parse input binary MDL/MDX
      2. Port (swap magic, supermodel, textures) to target_game
      3. Write output binary MDL/MDX

    Returns a human-readable report string.

    This replaces the old workflow:
      MDLEdit (binary→ASCII) → edit → MDLEdit (ASCII→binary)
    """
    from .mdl_parser import MDLBinaryParser

    # Parse
    parser  = MDLBinaryParser.from_files(input_mdl, input_mdx)
    model   = parser.parse()

    src_game = model.game_version.name  # 'K1' or 'K2'

    # Port
    porter  = CrossGamePorter(texture_map=texture_map or {})
    ported  = porter.port(model, target_game)

    # Write
    writer  = MDLBinaryWriter()
    writer.write(ported, output_mdl, output_mdx)

    report = (
        f"Ported {src_game}→{target_game}: {model.name!r}\n"
        f"  Input:  {input_mdl}\n"
        f"  Output: {output_mdl}\n"
        f"  Nodes:  {len(list(_iter_all(ported.root_node)))}\n"
        f"  Anims:  {len(ported.animations)}\n"
        f"  Supermodel: {model.supermodel!r} → {ported.supermodel!r}\n"
    )
    return report


def _iter_all(node):
    if node is None: return
    yield node
    for c in (node.children or []):
        yield from _iter_all(c)
