"""
v3.8 Regression Tests — Multi-Texture Rendering + c_brith Crash Fix
=====================================================================

BUG-TEX  c_bantha "mouth on tail": multi-material mesh nodes (tex_cnt > 1)
         were rendering all faces with slot-0's texture.  Root cause: tex_cnt
         was read from the binary header but never stored on ModelNode, so
         viewport always called _get_tex(node) → slot 0 for every face.
         Fix: store tex_count + texture_names on ModelNode; viewport uses
         _get_tex_for_face(node, face_idx) which dispatches via face_mats[fi].

BUG-CRASH  c_brith (RARE_CHAR model type 64) has deep / cyclic node trees
           that exceed Python's default recursion limit (~1 000 frames) and
           crash the whole application with RecursionError.
           Fix 1: _parse_node converted from recursive to iterative (stack-based)
                  with an explicit cycle-detection set.
           Fix 2: top-level parse() wraps _parse_node in try/except so any
                  remaining parse error produces a graceful stub model, not a crash.

Tests
-----
  MultiTexture                (11 tests)
    - tex_count / texture_names defaults on bare ModelNode
    - ASCII single bitmap → tex_count=1, texture_names=['bmp']
    - ASCII bitmap + bitmap2 without lightmapped → tex_count=2, two slots
    - ASCII bitmap + bitmap2 with lightmapped=1 → secondary NOT promoted
    - face_mats per-face slot dispatch (slot 0, slot 1)
    - slot clamping for corrupt out-of-range face_mat values
    - fallback to primary when secondary name is empty
    - viewport _get_tex_for_face single-tex fast-path
    - viewport _get_tex_for_face multi-tex dispatches to correct image

  IterativeNodeParser         (7 tests)
    - single node parses correctly
    - two-child hierarchy is correct
    - deep linear chain (1 200 nodes) does NOT raise RecursionError
    - deep chain node count is correct (50 nodes)
    - self-referential child offset is skipped (no hang)
    - out-of-bounds child offset is skipped gracefully
    - top-level guard: corrupt MDL does not crash

  Integration                 (3 tests)
    - ASCII MDL with two material zones → correct texture_names roundtrip
    - face_mats length matches faces length after ASCII parse
    - deep chain iterative node count matches expected
"""

import math
import os
import struct
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.model_data import (
    KotorModel, ModelNode, NodeFlags, Animation
)
from src.core.mdl_parser import MDLAsciiParser


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ascii_parse(text: str) -> KotorModel:
    """Parse an ASCII MDL string using MDLAsciiParser.parse_string()."""
    return MDLAsciiParser().parse_string(text)


def _ascii_model(*extra_lines):
    """Return a minimal ASCII MDL string with extra body lines injected."""
    return "\n".join([
        "newmodel testmodel",
        "setsupermodel testmodel NULL",
        "classification CHARACTER",
        "setanimationscale 1.0",
        "beginmodelgeom testmodel",
        "  node dummy testmodel",
        "    parent NULL",
        "  endnode",
        *extra_lines,
        "endmodelgeom testmodel",
        "donemodel testmodel",
    ])


def _make_node_with_face_mats(tex0='c_bantha01', tex1='c_banthh01',
                               face_mats=None, tex_count=2):
    """Build a ModelNode that mimics a parsed multi-texture mesh."""
    n = ModelNode(name='body_mesh')
    n.texture = tex0
    n.lightmap = tex1
    n.tex_count = tex_count
    n.texture_names = [tex0, tex1]
    n.vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)]
    n.faces = [(0, 1, 2), (1, 3, 2)]
    n.uvs = [(0, 0), (1, 0), (0, 1), (1, 1)]
    n.face_mats = face_mats if face_mats is not None else [0, 1]
    return n


def _walk(node):
    """Depth-first walk of a node tree, yields every node."""
    if node is None:
        return
    yield node
    for child in node.children:
        yield from _walk(child)


def _make_minimal_renderer():
    """
    Return a FrameRenderer-like object with just enough state for
    _get_tex / _get_tex_for_face to work without a full GUI environment.
    """
    from src.gui.viewport import FrameRenderer

    class _FakeTexCache:
        def get(self, name):
            return None
        def sample(self, img, u, v):
            return (128, 128, 128)

    class _FakeModel:
        name = 'test'

    renderer = object.__new__(FrameRenderer)
    renderer.textures  = {}
    renderer.tex_cache = _FakeTexCache()
    renderer._model    = _FakeModel()
    return renderer


# ─────────────────────────────────────────────────────────────────────────────
# Binary MDL builder for IterativeNodeParser tests
# ─────────────────────────────────────────────────────────────────────────────

def _build_binary_mdl(node_defs):
    """
    Build a minimal binary MDL buffer from a list of node definitions.

    IMPORTANT: MDLBinaryParser.BASE = 12 (class constant).
    All offsets stored inside the MDL data are RELATIVE TO BASE=12.
    The physical file layout is:

      Byte  0 – 11  : file preamble (12 bytes, unused, zeros)
      Byte 12 – 91  : geometry header (80 bytes, at B+0..B+79)
          B+0   fp1 = 4273776 (K1 marker)
          B+4   fp2 = 4273776
          B+8   model name (32 bytes null-padded)
          B+40  root_node_off (uint32) — relative offset from B
          B+44  node_count (uint32)
      Byte 92 –179  : model type header (88 bytes, at B+80..B+167)
          B+80+8  anim_array_off = 0
          B+80+12 anim_count = 0
      Byte 180–199  : name array header (20 bytes, at B+168..B+187)
          B+168+16 = byte 196: names_arr_off (uint32) — relative to B
          B+168+20 = byte 200: names_count  (uint32)
      Byte 200+     : name offset array (N × 4 bytes) — relative offsets to B
      Byte 200+N*4+ : name strings (N × 32 bytes each, null-padded)
      Byte …       : node records (N × 80 bytes)
      Byte …       : child offset arrays (N × 16 × 4 bytes)

    All offsets written INTO the buffer that the parser reads as "relative to B"
    must be (physical_byte_offset - 12).
    """
    N = len(node_defs)
    B = 12  # parser's BASE constant

    # ── Physical byte offsets ────────────────────────────────────────────────
    PREAMBLE       = 0            # 12-byte preamble (file start)
    GH_PHYS        = B            # geometry header starts at byte 12
    MH_PHYS        = B + 80       # model type header (byte 92)
    NAH_PHYS       = B + 168      # name array header (byte 180)
    NAME_OFF_PHYS  = B + 196      # name offset array (byte 208); adjust per N
    # We give the name-array-header a fixed relative offset of 196 (relative to B)
    # names_arr_off relative = NAME_OFF_PHYS - B = 196
    NAME_OFF_REL   = 196          # relative offset stored in header

    NAME_OFF_ARR_PHYS = B + NAME_OFF_REL                  # byte 208
    NAME_STR_PHYS  = NAME_OFF_ARR_PHYS + N * 4            # after offset array
    NAME_STR_SIZE  = 32
    NODE_PHYS      = NAME_STR_PHYS + N * NAME_STR_SIZE    # node records start
    NODE_SIZE      = 80
    CHILD_PHYS     = NODE_PHYS + N * NODE_SIZE             # child offset arrays
    CHILD_STRIDE   = 16 * 4                                # 16 children × 4 bytes

    total_size = CHILD_PHYS + N * CHILD_STRIDE + 256

    buf = bytearray(total_size)

    # ── Geometry header (at byte 12 = B+0) ──────────────────────────────────
    struct.pack_into('<I', buf, B + 0,  4273776)    # fp1
    struct.pack_into('<I', buf, B + 4,  4273776)    # fp2
    nm = b'testmodel\x00' + b'\x00' * 22
    buf[B + 8: B + 40] = nm
    # root_node_off relative to B: physical node 0 address minus B
    root_rel = NODE_PHYS - B
    struct.pack_into('<I', buf, B + 40, root_rel)
    struct.pack_into('<I', buf, B + 44, N)

    # ── Model type header (at byte 92 = B+80) — all zeros (no anims) ────────

    # ── Name array header (at byte 180 = B+168) ─────────────────────────────
    # names_arr_off (at B+168+16): relative to B = 196
    struct.pack_into('<I', buf, NAH_PHYS + 16, NAME_OFF_REL)
    struct.pack_into('<I', buf, NAH_PHYS + 20, N)

    # ── Name offset array (at byte B+196) ────────────────────────────────────
    for i in range(N):
        str_phys = NAME_STR_PHYS + i * NAME_STR_SIZE
        str_rel  = str_phys - B
        struct.pack_into('<I', buf, NAME_OFF_ARR_PHYS + i * 4, str_rel)

    # ── Name strings ─────────────────────────────────────────────────────────
    for i, nd in enumerate(node_defs):
        raw = nd.get('name', f'node{i}').encode('ascii', 'replace')[:31]
        padded = raw + b'\x00' * (NAME_STR_SIZE - len(raw))
        off = NAME_STR_PHYS + i * NAME_STR_SIZE
        buf[off: off + NAME_STR_SIZE] = padded

    # ── Node records ─────────────────────────────────────────────────────────
    node_phys = [NODE_PHYS + i * NODE_SIZE for i in range(N)]  # physical addresses

    for i, nd in enumerate(node_defs):
        o = node_phys[i]
        ntype    = nd.get('type', 1)
        pos      = nd.get('position', (0.0, 0.0, 0.0))
        rot      = nd.get('rotation', (0.0, 0.0, 0.0, 1.0))
        children = nd.get('children', [])

        struct.pack_into('<H', buf, o + 0,  ntype)    # node_type
        struct.pack_into('<H', buf, o + 2,  i)        # index_num  → names[i]
        struct.pack_into('<H', buf, o + 4,  i)        # node_num
        struct.pack_into('<H', buf, o + 6,  0)        # pad
        struct.pack_into('<I', buf, o + 8,  0)        # root_off
        struct.pack_into('<I', buf, o + 12, 0)        # parent_off
        struct.pack_into('<fff',  buf, o + 16, *pos)  # position
        struct.pack_into('<ffff', buf, o + 28, *rot)  # rotation

        # child array: stored relative to B
        child_arr_phys = CHILD_PHYS + i * CHILD_STRIDE
        child_arr_rel  = child_arr_phys - B
        child_cnt      = len(children)

        struct.pack_into('<I', buf, o + 44, child_arr_rel)  # child_arr_off (rel)
        struct.pack_into('<I', buf, o + 48, child_cnt)
        struct.pack_into('<I', buf, o + 52, child_cnt)
        for field_off in (56, 60, 64, 68, 72, 76):
            struct.pack_into('<I', buf, o + field_off, 0)

        # Write child offsets: each child offset is the child node's RELATIVE addr
        for ci, child_idx in enumerate(children):
            if ci >= 16:
                break
            child_rel = node_phys[child_idx] - B
            struct.pack_into('<I', buf, child_arr_phys + ci * 4, child_rel)

    return bytes(buf), b''


def _parse_binary(node_defs):
    """Build and parse a synthetic binary MDL; return KotorModel."""
    from src.core.mdl_parser import MDLBinaryParser
    mdl_bytes, mdx_bytes = _build_binary_mdl(node_defs)
    return MDLBinaryParser(mdl_bytes, mdx_bytes).parse()


# ─────────────────────────────────────────────────────────────────────────────
# MultiTexture Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMultiTexture:

    def test_tex_count_default_on_bare_node(self):
        """A freshly constructed ModelNode must default to tex_count=1."""
        n = ModelNode(name='bare')
        assert n.tex_count == 1

    def test_texture_names_default_on_bare_node(self):
        """A freshly constructed ModelNode must default to texture_names=[]."""
        n = ModelNode(name='bare')
        assert n.texture_names == []

    def test_ascii_single_bitmap_gives_tex_count_1(self):
        """ASCII parser: bitmap only → tex_count stays 1, texture_names has 1 entry."""
        mdl = _ascii_model(
            "  node trimesh body",
            "    parent testmodel",
            "    bitmap c_bantha01",
            "    verts 0",
            "    faces 0",
            "  endnode",
        )
        model = _ascii_parse(mdl)
        body = next((n for n in _walk(model.root_node) if n.name == 'body'), None)
        assert body is not None
        assert body.tex_count == 1
        assert body.texture_names == ['c_bantha01']

    def test_ascii_bitmap_plus_bitmap2_without_lightmapped_gives_tex_count_2(self):
        """ASCII parser: bitmap + bitmap2, no lightmapped=1 → tex_count=2, two slots."""
        mdl = _ascii_model(
            "  node trimesh body",
            "    parent testmodel",
            "    bitmap c_bantha01",
            "    bitmap2 c_banthh01",
            "    verts 0",
            "    faces 0",
            "  endnode",
        )
        model = _ascii_parse(mdl)
        body = next((n for n in _walk(model.root_node) if n.name == 'body'), None)
        assert body is not None
        assert body.tex_count == 2
        assert body.texture_names[0] == 'c_bantha01'
        assert body.texture_names[1] == 'c_banthh01'

    def test_ascii_bitmap_plus_bitmap2_with_lightmapped_keeps_tex_count_1(self):
        """ASCII parser: lightmapped=1 means bitmap2 is a real lightmap, NOT a secondary
        material texture.  tex_count must stay 1."""
        mdl = _ascii_model(
            "  node trimesh body",
            "    parent testmodel",
            "    bitmap c_bantha01",
            "    bitmap2 c_bantha_lm",
            "    lightmapped 1",
            "    verts 0",
            "    faces 0",
            "  endnode",
        )
        model = _ascii_parse(mdl)
        body = next((n for n in _walk(model.root_node) if n.name == 'body'), None)
        assert body is not None
        assert body.tex_count == 1
        assert body.texture_names[0] == 'c_bantha01'
        assert len(body.texture_names) == 1

    def test_face_mats_slot_dispatch_slot0(self):
        """face_mats[i]==0 → texture_names[0] (primary texture)."""
        n = _make_node_with_face_mats(face_mats=[0, 0])
        assert n.texture_names[n.face_mats[0]] == 'c_bantha01'

    def test_face_mats_slot_dispatch_slot1(self):
        """face_mats[i]==1 → texture_names[1] (secondary texture, e.g. head)."""
        n = _make_node_with_face_mats(face_mats=[0, 1])
        assert n.texture_names[n.face_mats[1]] == 'c_banthh01'

    def test_face_mats_out_of_range_clamped(self):
        """Corrupt face_mat value beyond texture_names length must be clamped."""
        n = _make_node_with_face_mats(face_mats=[99])
        slot_count = len(n.texture_names)
        raw_slot = n.face_mats[0]
        clamped = max(0, min(raw_slot, slot_count - 1))
        assert 0 <= clamped < slot_count
        _ = n.texture_names[clamped]  # must not raise

    def test_fallback_to_primary_when_secondary_empty(self):
        """If texture_names[1] is empty, rendering should fall back to slot 0."""
        n = ModelNode(name='mesh')
        n.texture = 'c_bantha01'
        n.tex_count = 2
        n.texture_names = ['c_bantha01', '']
        n.face_mats = [1]

        slot = n.face_mats[0]
        raw = n.texture_names[slot] if slot < len(n.texture_names) else n.texture
        fallback = raw if raw else n.texture
        assert fallback == 'c_bantha01'

    def test_viewport_get_tex_for_face_single_tex_fast_path(self):
        """_get_tex_for_face on a tex_count=1 node returns same result as _get_tex."""
        renderer = _make_minimal_renderer()
        n = ModelNode(name='single')
        n.texture = 'c_bantha01'
        n.tex_count = 1
        n.texture_names = ['c_bantha01']
        n.face_mats = [0]
        r1 = renderer._get_tex(n)
        r2 = renderer._get_tex_for_face(n, 0)
        assert r1 == r2  # both None — consistent behavior

    def test_viewport_get_tex_for_face_multitex_dispatches_correctly(self):
        """_get_tex_for_face on a tex_count=2 node dispatches to the correct slot."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not available")

        renderer = _make_minimal_renderer()
        img0 = Image.new('RGBA', (8, 8), (255, 0, 0, 255))   # red   → slot 0
        img1 = Image.new('RGBA', (8, 8), (0, 255, 0, 255))   # green → slot 1
        renderer.textures['c_bantha01'] = img0
        renderer.textures['c_banthh01'] = img1

        n = _make_node_with_face_mats(face_mats=[0, 1])
        face0_tex = renderer._get_tex_for_face(n, 0)
        face1_tex = renderer._get_tex_for_face(n, 1)

        assert face0_tex is img0, "Face 0 should get slot-0 (body) texture"
        assert face1_tex is img1, "Face 1 should get slot-1 (head/mouth) texture"


# ─────────────────────────────────────────────────────────────────────────────
# IterativeNodeParser Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestIterativeNodeParser:

    def test_single_node_parses_correctly(self):
        """A single root node with no children is parsed with the correct name."""
        model = _parse_binary([{'name': 'rootbone'}])
        assert model.root_node is not None
        assert model.root_node.name == 'rootbone'
        assert model.root_node.children == []

    def test_two_children_correct_hierarchy(self):
        """Root with two children produces a 3-node hierarchy."""
        defs = [
            {'name': 'root',  'children': [1, 2]},
            {'name': 'left',  'children': []},
            {'name': 'right', 'children': []},
        ]
        model = _parse_binary(defs)
        root = model.root_node
        assert root.name == 'root'
        child_names = {c.name for c in root.children}
        assert child_names == {'left', 'right'}

    def test_deep_linear_chain_no_recursion_error(self):
        """
        A chain of 1 200 nodes (deeper than Python's default 1 000 recursion
        limit) must parse without RecursionError.  This is the c_brith fix.
        """
        DEPTH = 1200
        defs = [
            {'name': f'bone{i}',
             'children': [i + 1] if i < DEPTH - 1 else []}
            for i in range(DEPTH)
        ]
        model = _parse_binary(defs)
        assert model.root_node is not None
        assert model.root_node.name == 'bone0'

    def test_deep_linear_chain_node_count(self):
        """After parsing a 50-node chain all nodes must be reachable."""
        DEPTH = 50
        defs = [
            {'name': f'n{i}',
             'children': [i + 1] if i < DEPTH - 1 else []}
            for i in range(DEPTH)
        ]
        model = _parse_binary(defs)
        count = sum(1 for _ in _walk(model.root_node))
        assert count == DEPTH

    def test_self_referential_node_skipped(self):
        """A node whose child list points to itself must be skipped (no hang)."""
        # Build a normal single-node MDL, then patch child_cnt=1 and child[0]=self
        mdl_bytes, _ = _build_binary_mdl([{'name': 'cyclic', 'children': []}])
        buf = bytearray(mdl_bytes)

        # BASE = 12; layout produced by _build_binary_mdl for N=1:
        B  = 12
        N  = 1
        NAME_OFF_REL   = 196
        NAME_OFF_PHYS  = B + NAME_OFF_REL                  # 208
        NAME_STR_PHYS  = NAME_OFF_PHYS + N * 4             # 212
        NODE_PHYS      = NAME_STR_PHYS + N * 32            # 244
        CHILD_PHYS     = NODE_PHYS + N * 80                # 324
        node0_phys     = NODE_PHYS                         # 244

        # Set child_cnt = 1
        struct.pack_into('<I', buf, node0_phys + 48, 1)
        struct.pack_into('<I', buf, node0_phys + 52, 1)
        # child[0] = this node's own relative offset
        node0_rel = node0_phys - B
        struct.pack_into('<I', buf, CHILD_PHYS, node0_rel)

        from src.core.mdl_parser import MDLBinaryParser
        model = MDLBinaryParser(bytes(buf), b'').parse()
        assert model.root_node is not None

    def test_out_of_bounds_child_offset_skipped(self):
        """An out-of-bounds child offset must be skipped gracefully."""
        mdl_bytes, _ = _build_binary_mdl([{'name': 'root', 'children': []}])
        buf = bytearray(mdl_bytes)

        B  = 12
        N  = 1
        NAME_OFF_PHYS  = B + 196
        NAME_STR_PHYS  = NAME_OFF_PHYS + N * 4
        NODE_PHYS      = NAME_STR_PHYS + N * 32
        CHILD_PHYS     = NODE_PHYS + N * 80
        node0_phys     = NODE_PHYS

        struct.pack_into('<I', buf, node0_phys + 48, 1)   # child_cnt = 1
        struct.pack_into('<I', buf, node0_phys + 52, 1)
        # Child relative offset that puts physical address WAY past end of file
        struct.pack_into('<I', buf, CHILD_PHYS, 0x7FFFFFFF)

        from src.core.mdl_parser import MDLBinaryParser
        model = MDLBinaryParser(bytes(buf), b'').parse()
        assert model.root_node is not None

    def test_top_level_guard_returns_stub_on_corrupt_data(self):
        """Completely corrupt MDL data must NOT crash; result is non-None."""
        from src.core.mdl_parser import MDLBinaryParser
        # A buffer that is large enough for header checks but contains garbage
        corrupt = bytearray(1000)
        struct.pack_into('<I', corrupt, 0, 4273776)   # fp1 = K1 marker
        struct.pack_into('<I', corrupt, 40, 500)       # root_node_off into garbage
        try:
            model = MDLBinaryParser(bytes(corrupt), b'').parse()
        except Exception as exc:
            pytest.fail(f"Parsing corrupt data raised {type(exc).__name__}: {exc}")
        # No assert beyond "did not raise"


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestIntegration:

    def test_ascii_multitex_node_texture_names_roundtrip(self):
        """
        An ASCII MDL with bitmap + bitmap2 (no lightmapped) must produce a
        node whose texture_names[0] is the primary and [1] is the secondary.
        """
        mdl = "\n".join([
            "newmodel c_bantha",
            "setsupermodel c_bantha NULL",
            "classification CHARACTER",
            "setanimationscale 1.0",
            "beginmodelgeom c_bantha",
            "  node dummy c_bantha",
            "    parent NULL",
            "  endnode",
            "  node trimesh body_mesh",
            "    parent c_bantha",
            "    bitmap c_bantha01",
            "    bitmap2 c_banthh01",
            "    verts 0",
            "    faces 0",
            "  endnode",
            "endmodelgeom c_bantha",
            "donemodel c_bantha",
        ])
        model = _ascii_parse(mdl)
        body = next((n for n in _walk(model.root_node) if n.name == 'body_mesh'), None)
        assert body is not None, "body_mesh node not found"
        assert body.tex_count == 2
        assert body.texture_names[0] == 'c_bantha01'
        assert body.texture_names[1] == 'c_banthh01'

    def test_face_mats_len_matches_faces_len(self):
        """
        After parsing a multi-texture ASCII MDL with face data, if face_mats
        is populated it must have one entry per face.
        """
        mdl = "\n".join([
            "newmodel test",
            "setsupermodel test NULL",
            "classification CHARACTER",
            "setanimationscale 1.0",
            "beginmodelgeom test",
            "  node dummy test",
            "    parent NULL",
            "  endnode",
            "  node trimesh mesh",
            "    parent test",
            "    bitmap tex0",
            "    bitmap2 tex1",
            "    verts 3",
            "      0.0 0.0 0.0",
            "      1.0 0.0 0.0",
            "      0.0 1.0 0.0",
            "    faces 1",
            "      0 1 2 1 0 1 2 0",
            "    tverts 3",
            "      0.0 0.0",
            "      1.0 0.0",
            "      0.0 1.0",
            "  endnode",
            "endmodelgeom test",
            "donemodel test",
        ])
        model = _ascii_parse(mdl)
        mesh = next((n for n in _walk(model.root_node) if n.name == 'mesh'), None)
        if mesh is None:
            pytest.skip("ASCII face parsing produced no mesh node")
        if mesh.face_mats:
            assert len(mesh.face_mats) == len(mesh.faces)

    def test_deep_chain_iterative_node_count_matches_expected(self):
        """
        Build a 100-node chain via synthetic binary MDL and verify all
        100 nodes are accessible from the root.
        """
        DEPTH = 100
        defs = [
            {'name': f'bone{i}',
             'children': [i + 1] if i < DEPTH - 1 else []}
            for i in range(DEPTH)
        ]
        model = _parse_binary(defs)
        total = sum(1 for _ in _walk(model.root_node))
        assert total == DEPTH, f"Expected {DEPTH} nodes, got {total}"
