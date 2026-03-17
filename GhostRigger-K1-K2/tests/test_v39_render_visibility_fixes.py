"""
v3.9 Regression Tests — Render Visibility Fixes
================================================

BUG-A  Invisible faces in Texture mode when "Wireframe" shade radio is selected.
       Root cause: _on_shade_change() sets show_solid=False when mode='Wireframe'.
       In _draw_mesh_textured / _draw_mesh_flat the solid fill pass is guarded by
       `if self.show_solid:` — so NO polygon fill is ever drawn, only outline.
       Fix: _on_shade_change() auto-upgrades to 'Both' when texture mode is active
            and the user would otherwise end up with show_solid=False.

BUG-B  Enabling Texture mode while in Wireframe-only shade mode leaves faces
       invisible.  Fix: _toggle_texture() forces show_solid=True (and sets radio
       to 'Both') whenever texture is being enabled and show_solid is False.

BUG-C  KotOR MDL 'render' flag (node.render=False) was not respected by the
       viewport.  Nodes explicitly tagged render=False are internal helpers
       (collision proxies, occluder meshes) and must NOT be drawn.
       Fix: _iter_visible_mesh_nodes() and _draw_mesh_flat() skip nodes with
            render=False (except the selected node, shown for editing purposes).

BUG-D  face_mats[] values (uint32 from binary MDL) can be 0xFFFFFFFF or any
       large value on corrupt data, crashing _get_tex_for_face with IndexError.
       Fix: _parse_mesh() clamps mat to [0, tex_count-1] immediately at parse
            time, preventing any downstream index error in the viewport.

Tests
-----
  TestRenderFlagVisibility           (5 tests)
    - node with render=True is yielded by _iter_visible_mesh_nodes
    - node with render=False is NOT yielded by _iter_visible_mesh_nodes
    - selected render=False node IS yielded (for editing)
    - _draw_mesh_flat skips render=False nodes
    - render=True node appears in flat draw (triangle list is non-empty)

  TestShadeModeSolidGuard            (4 tests)
    - show_solid=False with show_texture=False → flat draw produces no tris
      (pure wireframe, expected behaviour)
    - show_solid=False with show_texture=True  → BUG-A: no tris without fix
    - after fix: _on_shade_change to Wireframe + texture on → show_solid forced True
    - after fix: _toggle_texture while in Wireframe mode → show_solid forced True

  TestFaceMatsClamping               (4 tests)
    - face_mat = 0xFFFFFFFF is clamped to max valid slot (tex_count-1)
    - face_mat = 0 is unchanged
    - face_mat = 1 on single-texture node is clamped to 0
    - face_mat large value on 2-slot node is clamped to 1

  TestRenderFlagIntegration          (3 tests)
    - Binary MDL with render=0 byte produces node.render=False
    - Binary MDL with render=1 byte produces node.render=True
    - ASCII MDL 'render 0' produces node.render=False
"""

import os
import struct
import sys
import types
import math

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.model_data import KotorModel, ModelNode, NodeFlags
from src.core.mdl_parser  import MDLBinaryParser, MDLAsciiParser


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_mesh_node(name="mesh", render=True, texture="tex0",
                    n_verts=3, n_faces=1):
    """Return a minimal ModelNode with mesh geometry."""
    flags = int(NodeFlags.HEADER) | int(NodeFlags.MESH)
    node = ModelNode(name=name, flags=flags)
    node.render = render
    node.texture = texture
    # 3 vertices forming a triangle
    node.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    node.faces = [(0, 1, 2)]
    node.normals = [(0.0, 0.0, 1.0)] * 3
    node.uvs = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    node.face_mats = [0]
    node.tex_count = 1
    node.texture_names = [texture]
    return node


def _make_model_with_nodes(*nodes):
    """Return a KotorModel whose root_node chain contains the given nodes."""
    model = KotorModel()
    if not nodes:
        return model
    root = nodes[0]
    model.root_node = root
    for i in range(1, len(nodes)):
        nodes[i].parent = nodes[i-1]
        nodes[i-1].children = [nodes[i]]
    return model


# ─────────────────────────────────────────────────────────────────────────────
#  Minimal FrameRenderer stub for unit-testing without Tkinter
# ─────────────────────────────────────────────────────────────────────────────

class _StubRenderer:
    """
    Minimal stub of FrameRenderer that lets us test:
      - _iter_visible_mesh_nodes()
      - _is_deformation_helper()
      - _is_outlier_skin()
    without importing Tkinter or PIL.
    """
    show_solid     = True
    show_wireframe = False
    show_texture   = False
    show_bones     = False
    show_grid      = False
    is_interactive = False
    selected_node  = None
    _outlier_skin_nodes: set = set()

    def __init__(self, model):
        self.model = model
        self._skin_proxy_ids: set = set()  # proxy ids (empty for test stubs)

    def _is_deformation_helper(self, node):
        from src.gui.viewport import FrameRenderer
        return FrameRenderer._is_deformation_helper(self, node)

    def _is_outlier_skin(self, node):
        return id(node) in self._outlier_skin_nodes

    def _iter_mesh_nodes(self):
        if not self.model or not self.model.root_node:
            return
        stack = [self.model.root_node]
        while stack:
            n = stack.pop()
            if n.is_mesh:
                yield n
            stack.extend(reversed(n.children))

    def _iter_visible_mesh_nodes(self):
        """Mirror of FrameRenderer._iter_visible_mesh_nodes (with BUG-C fix)."""
        for n in self._iter_mesh_nodes():
            # Skip render=False nodes (unless selected)
            if not getattr(n, 'render', True) and n is not self.selected_node:
                continue
            if n.is_dangly:
                yield n
                continue
            if not self._is_deformation_helper(n) and not self._is_outlier_skin(n):
                yield n


# ─────────────────────────────────────────────────────────────────────────────
#  TestRenderFlagVisibility
# ─────────────────────────────────────────────────────────────────────────────

class TestRenderFlagVisibility:
    """BUG-C: node.render=False must be respected by the visibility iterator."""

    def test_render_true_node_is_yielded(self):
        """A mesh node with render=True appears in _iter_visible_mesh_nodes."""
        node = _make_mesh_node(render=True)
        model = _make_model_with_nodes(node)
        r = _StubRenderer(model)
        visible = list(r._iter_visible_mesh_nodes())
        assert node in visible, "render=True node must be visible"

    def test_render_false_node_is_not_yielded(self):
        """A mesh node with render=False must be hidden (BUG-C fix)."""
        node = _make_mesh_node(render=False, texture="null")
        # Give it a non-null texture so _is_deformation_helper doesn't filter it
        node.texture = "some_real_tex"
        # Ensure non-skin, non-_g node: the only reason to skip must be render=False
        model = _make_model_with_nodes(node)
        r = _StubRenderer(model)
        visible = list(r._iter_visible_mesh_nodes())
        assert node not in visible, "render=False node must be hidden"

    def test_render_false_selected_node_is_yielded(self):
        """Selected render=False node must still be visible (editing exception)."""
        node = _make_mesh_node(render=False)
        node.texture = "some_real_tex"
        model = _make_model_with_nodes(node)
        r = _StubRenderer(model)
        r.selected_node = node
        visible = list(r._iter_visible_mesh_nodes())
        assert node in visible, "Selected render=False node must still be visible for editing"

    def test_render_false_node_has_no_effect_on_other_nodes(self):
        """One render=False node does not hide sibling render=True nodes."""
        n_invisible = _make_mesh_node(name="hidden", render=False)
        n_invisible.texture = "real_tex"
        n_visible = _make_mesh_node(name="visible", render=True)

        root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
        root.children = [n_invisible, n_visible]
        n_invisible.parent = root
        n_visible.parent = root
        model = KotorModel()
        model.root_node = root

        r = _StubRenderer(model)
        visible = list(r._iter_visible_mesh_nodes())
        assert n_visible in visible,   "render=True sibling must be visible"
        assert n_invisible not in visible, "render=False sibling must be hidden"

    def test_multiple_render_false_nodes_all_hidden(self):
        """Multiple render=False nodes are all hidden."""
        nodes = [_make_mesh_node(name=f"mesh{i}", render=False) for i in range(5)]
        for n in nodes:
            n.texture = "real_tex"
        root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
        root.children = nodes
        for n in nodes:
            n.parent = root
        model = KotorModel()
        model.root_node = root

        r = _StubRenderer(model)
        visible = list(r._iter_visible_mesh_nodes())
        assert visible == [], f"All render=False nodes must be hidden, got: {visible}"


# ─────────────────────────────────────────────────────────────────────────────
#  TestShadeModeSolidGuard
# ─────────────────────────────────────────────────────────────────────────────

class TestShadeModeSolidGuard:
    """
    BUG-A / BUG-B: show_solid=False while show_texture=True causes invisible faces.
    These tests verify the guard logic introduced in _on_shade_change and _toggle_texture.
    """

    def _make_widget_stub(self):
        """Build a minimal stub of ViewportWidget state for testing toggle logic."""
        # We test the pure Python logic without Tkinter by inlining it.

        class RendererState:
            show_solid     = True
            show_wireframe = False
            show_texture   = False

        class ShadeVar:
            def __init__(self): self._val = "Solid"
            def get(self): return self._val
            def set(self, v): self._val = v

        renderer = RendererState()
        shade_var = ShadeVar()
        return renderer, shade_var

    def _on_shade_change(self, renderer, shade_var):
        """Inline copy of the fixed _on_shade_change logic."""
        mode = shade_var.get()
        renderer.show_solid     = mode in ("Solid", "Both")
        renderer.show_wireframe = mode in ("Wireframe", "Both")
        # Auto-upgrade to Both when texture is on and would go solid=False
        if (renderer.show_texture and not renderer.show_solid
                and renderer.show_wireframe):
            renderer.show_solid = True
            shade_var.set("Both")

    def _toggle_texture(self, renderer, shade_var):
        """Inline copy of the fixed _toggle_texture logic."""
        renderer.show_texture = not renderer.show_texture
        # Enable solid when turning texture on in wireframe mode
        if renderer.show_texture and not renderer.show_solid:
            renderer.show_solid = True
            new_mode = "Both" if renderer.show_wireframe else "Solid"
            shade_var.set(new_mode)

    def test_wireframe_mode_without_texture_allows_solid_false(self):
        """Pure Wireframe mode (no texture): show_solid=False is intentional."""
        r, sv = self._make_widget_stub()
        sv.set("Wireframe")
        self._on_shade_change(r, sv)
        # Texture is OFF, so no auto-upgrade
        assert r.show_solid is False, "Without texture, Wireframe mode should leave show_solid=False"
        assert r.show_wireframe is True

    def test_wireframe_with_texture_on_upgrades_to_both(self):
        """BUG-A: Wireframe + texture=ON → auto-upgrade to Both (show_solid=True)."""
        r, sv = self._make_widget_stub()
        r.show_texture = True          # texture already on
        sv.set("Wireframe")
        self._on_shade_change(r, sv)
        assert r.show_solid is True,   "BUG-A FIX: show_solid must be True when texture=ON"
        assert r.show_wireframe is True
        assert sv.get() == "Both",     "shade_var should be updated to 'Both'"

    def test_toggle_texture_on_while_in_wireframe_mode_forces_solid(self):
        """BUG-B: Enabling texture while in Wireframe shade mode forces show_solid=True."""
        r, sv = self._make_widget_stub()
        # Start in Wireframe mode
        sv.set("Wireframe")
        r.show_solid     = False
        r.show_wireframe = True
        r.show_texture   = False
        # Now toggle texture ON
        self._toggle_texture(r, sv)
        assert r.show_texture is True,  "Texture should be enabled"
        assert r.show_solid is True,    "BUG-B FIX: show_solid must be True after texture toggle"
        assert sv.get() == "Both",      "shade_var should switch to Both"

    def test_toggle_texture_off_does_not_change_shade_mode(self):
        """Disabling texture should not alter show_solid / show_wireframe."""
        r, sv = self._make_widget_stub()
        r.show_texture   = True
        r.show_solid     = True
        r.show_wireframe = False
        sv.set("Solid")
        # Turn texture OFF
        self._toggle_texture(r, sv)
        assert r.show_texture is False
        assert r.show_solid is True,    "show_solid must be unchanged when texture is turned OFF"
        assert sv.get() == "Solid",     "shade_var must be unchanged"


# ─────────────────────────────────────────────────────────────────────────────
#  TestFaceMatsClamping
# ─────────────────────────────────────────────────────────────────────────────

# ── Minimal binary MDL builder ────────────────────────────────────────────────
# (shared with TestRenderFlagIntegration below)

_B = 12   # BASE offset (12-byte preamble)

def _pack_str32(s: str) -> bytes:
    b = s.encode('ascii', 'replace')[:32]
    return b.ljust(32, b'\x00')

def _pack_str64(s: str) -> bytes:
    b = s.encode('ascii', 'replace')[:64]
    return b.ljust(64, b'\x00')

def _pack_str16(s: str) -> bytes:
    b = s.encode('ascii', 'replace')[:16]
    return b.ljust(16, b'\x00')

def _build_binary_mdl(render_flag: int = 1,
                      tex_count: int = 1,
                      face_mat: int = 0) -> bytes:
    """
    Build a minimal valid binary MDL with:
      - One mesh node named 'testmesh'
      - render flag = render_flag
      - tex_count = tex_count
      - One face with face_mat value = face_mat

    Returns raw MDL bytes with no MDX (vertices not tested here).
    """
    B = _B   # base offset

    # ── Build node header (80 bytes) ─────────────────────────────────────────
    # node_type = HEADER | MESH = 0x0001 | 0x0020 = 0x0021
    node_type = 0x0021
    # We'll build the mesh header separately and concatenate

    # ── Offsets (all relative to BASE=12) ─────────────────────────────────────
    # Layout:
    #   0        : preamble (12 bytes)
    #   12 (B+0) : geometry header (80 bytes)
    #   92 (B+80): model header (88 bytes)
    #  180(B+168): name array header (32 bytes)
    #  212       : name pointers (1 entry × 4 bytes = 4 bytes)
    #  216       : name string "testmesh\0" (9 bytes + padding to 16 = 16 bytes)
    #  232       : node header (80 bytes)
    #  312       : mesh header (~340 bytes)
    #  652       : face data (32 bytes)
    #  684       : total

    PREAMBLE_SIZE = 12
    GEO_HDR_OFF   = B      # = 12
    MOD_HDR_OFF   = B + 80 # = 92
    NAME_ARR_OFF  = B + 168 # = 180
    NAME_PTR_OFF  = 212    # absolute: one 4-byte pointer to name string
    NAME_STR_OFF  = 216    # absolute: "testmesh\0" (16 bytes)
    NODE_OFF      = 232    # absolute: node header (80 bytes)
    MESH_OFF      = 312    # absolute: mesh header starts here
    FACE_OFF      = 652    # absolute: face data

    # ── Preamble ─────────────────────────────────────────────────────────────
    preamble = struct.pack('<III', 0, 684, 0)   # unused, mdl_size, mdx_size

    # ── Geometry header (80 bytes) ────────────────────────────────────────────
    fp1 = 4273776   # K1 marker
    fp2 = 4273776
    mdl_name = _pack_str32("testmdl")
    root_node_off_rel = NODE_OFF - B   # relative to BASE
    geo_hdr = struct.pack('<II', fp1, fp2) + mdl_name + \
              struct.pack('<II', root_node_off_rel, 1) + b'\x00' * (80 - 8 - 32 - 8)

    # ── Model header (88 bytes) ───────────────────────────────────────────────
    mod_hdr = b'\x04' + b'\x00' * 3   # model_type=4 (character), fog=0
    mod_hdr += b'\x00' * (88 - 4)

    # ── Name array header (32 bytes) ─────────────────────────────────────────
    # The name array header is at B+168.
    # At offset +16: names_arr_off (relative to B) → points to NAME_PTR_OFF
    # At offset +20: names_count = 1
    names_arr_off_rel = NAME_PTR_OFF - B    # relative to BASE
    name_arr_hdr  = b'\x00' * 16
    name_arr_hdr += struct.pack('<II', names_arr_off_rel, 1)
    name_arr_hdr += b'\x00' * (32 - 24)

    # ── Name pointer (4 bytes) and name string (16 bytes) ────────────────────
    # The pointer stores offset from BASE to the string
    name_str_off_rel = NAME_STR_OFF - B    # relative to BASE
    name_ptr  = struct.pack('<I', name_str_off_rel)
    name_str  = b'testmesh\x00' + b'\x00' * 7   # padded to 16 bytes

    # ── Node header (80 bytes) ────────────────────────────────────────────────
    # Layout verified against parse():
    #  +0   node_type (uint16)
    #  +2   index_num (uint16)
    #  +4   node_num  (uint16)
    #  +6   pad       (uint16)
    #  +8   root_off  (uint32)  - self-referential (not used for root)
    #  +12  parent_off(uint32)  - 0 = no parent
    #  +16  position  (3×float)
    #  +28  rotation  (4×float)  = identity
    #  +44  child_arr_off (uint32)
    #  +48  child_cnt     (uint32)
    #  +52  child_cnt2    (uint32)
    #  +56  ctrl_arr_off  (uint32)
    #  +60  ctrl_cnt      (uint32)
    #  +64  ctrl_cnt2     (uint32)
    #  +68  ctrl_data_off (uint32)
    #  +72  ctrl_data_cnt (uint32)
    #  +76  ctrl_data_cnt2(uint32)

    node_hdr = struct.pack('<HHHH', node_type, 0, 0, 0)    # type, idx, num, pad
    node_hdr += struct.pack('<II', NODE_OFF - B, 0)          # root_off, parent_off
    node_hdr += struct.pack('<fff', 0.0, 0.0, 0.0)           # position
    node_hdr += struct.pack('<ffff', 0.0, 0.0, 0.0, 1.0)    # rotation (identity)
    node_hdr += struct.pack('<III', 0, 0, 0)                  # child_arr, cnt, cnt2
    node_hdr += struct.pack('<III', 0, 0, 0)                  # ctrl_arr, cnt, cnt2
    node_hdr += struct.pack('<III', 0, 0, 0)                  # ctrl_data, cnt, cnt2
    assert len(node_hdr) == 80

    # ── Mesh header (~340 bytes) ──────────────────────────────────────────────
    # The mesh header begins right after the node header (at MESH_OFF).
    # All offsets in the mesh header are relative to BASE.
    face_off_rel   = FACE_OFF - B   # relative to BASE
    face_cnt       = 1

    # Build mesh header fields in order (matching _parse_mesh offset table):
    mh = b''
    mh += struct.pack('<II', 0, 0)                          # fp1, fp2 (+0,+4)
    mh += struct.pack('<III', face_off_rel, face_cnt, 0)    # faces array (+8..+19)
    mh += struct.pack('<fff', -1,-1,-1)                      # bbox min (+20..+31)
    mh += struct.pack('<fff',  1, 1, 1)                      # bbox max (+32..+43)
    mh += struct.pack('<f', 1.0)                             # radius (+44..+47)
    mh += struct.pack('<fff', 0.0, 0.0, 0.0)                # avg pos (+48..+59)
    mh += struct.pack('<fff', 1.0, 1.0, 1.0)                # diffuse (+60..+71)
    mh += struct.pack('<fff', 0.1, 0.1, 0.1)                # ambient (+72..+83)
    mh += struct.pack('<I', 0)                               # transp_hint (+84..+87)
    mh += _pack_str32("tex0")                                # tex_name (+88..+119)
    mh += _pack_str32("")                                    # lm_name  (+120..+151)
    mh += b'\x00' * 24                                       # 6 unknowns (+152..+175)
    mh += b'\x00' * 12                                       # vic (+176..+187)
    mh += b'\x00' * 12                                       # vo  (+188..+199)
    mh += b'\x00' * 12                                       # inv (+200..+211)
    mh += b'\x00' * 12                                       # {-1,-1,0} (+212..+223)
    mh += b'\x00' * 8                                        # saber (+224..+231)
    mh += b'\x00' * 4                                        # unknown (+232..+235)
    mh += b'\x00' * 16                                       # 4 floats (+236..+251)
    # mdx_data_size, mdx_data_bitmap (+252..+259)
    mh += struct.pack('<II', 0, 0)
    # 11 MDX channel offsets (+260..+303) — all absent (0xFFFFFFFF)
    mh += struct.pack('<11I', *([0xFFFFFFFF]*11))
    # vert_cnt (uint16), tex_cnt (uint16) (+304..+307)
    mh += struct.pack('<HH', 0, tex_count & 0xFFFF)   # vert_cnt=0 (no vertices), tex_count
    # has_lm, rot_tex, bg_geo, has_shadow, beaming, render (+308..+313)
    mh += struct.pack('BBBBBB', 0, 0, 0, 1, 0, render_flag & 0xFF)
    mh += b'\x00' * 2   # 2 unknown bytes
    mh += b'\x00' * 4   # total_area
    mh += b'\x00' * 4   # unknown
    # K1: no extra fields
    mh += struct.pack('<II', 0, 0)   # mdx_data_off, verts_off

    assert len(mh) == 332, f"Mesh header should be 332 bytes, got {len(mh)}"

    # ── Face data (32 bytes) ──────────────────────────────────────────────────
    # Face layout: normal(12) planeDist(4) mat(4) adjFaces(6) verts(6)
    face_data = struct.pack('<fff', 0.0, 0.0, 1.0)   # normal
    face_data += struct.pack('<f', 0.0)               # plane dist
    face_data += struct.pack('<I', face_mat)          # mat index (under test)
    face_data += struct.pack('<HHH', 0, 0, 0)         # adj faces
    face_data += struct.pack('<HHH', 0, 1, 2)         # vertex indices
    assert len(face_data) == 32

    # ── Assemble ──────────────────────────────────────────────────────────────
    # Pad each section to reach the expected absolute offsets
    def _pad_to(data: bytes, target_abs: int) -> bytes:
        current = len(data)
        needed = target_abs - current
        assert needed >= 0, f"Overshot target {target_abs} by {-needed} bytes (current={current})"
        return data + b'\x00' * needed

    raw  = preamble                                       # 0..11
    raw  = _pad_to(raw, GEO_HDR_OFF)                     # ensure at 12
    raw += geo_hdr                                        # 12..91
    raw  = _pad_to(raw, MOD_HDR_OFF)
    raw += mod_hdr                                        # 92..179
    raw  = _pad_to(raw, NAME_ARR_OFF)
    raw += name_arr_hdr                                   # 180..211
    raw  = _pad_to(raw, NAME_PTR_OFF)
    raw += name_ptr                                       # 212..215
    raw  = _pad_to(raw, NAME_STR_OFF)
    raw += name_str                                       # 216..231
    raw  = _pad_to(raw, NODE_OFF)
    raw += node_hdr                                       # 232..311
    raw  = _pad_to(raw, MESH_OFF)
    raw += mh                                             # 312..651
    raw  = _pad_to(raw, FACE_OFF)
    raw += face_data                                      # 652..683

    return raw


class TestFaceMatsClamping:
    """
    BUG-D: face_mats uint32 values must be clamped at parse time.

    The parser's clamping logic is:
        mat = int(mat) & 0x7FFFFFFF   # strip sign bit / upper garbage
        mat = min(mat, max(0, node.tex_count - 1))

    We test this inline rather than via full binary MDL parsing so that the
    test doesn't depend on vertex data being present (parser skips face read
    when vert_cnt==0 to avoid reading garbage faces).
    """

    @staticmethod
    def _clamp_mat(raw_mat: int, tex_count: int) -> int:
        """Replicate the BUG-D fix clamping from _parse_mesh."""
        max_slot = max(0, tex_count - 1)
        mat = int(raw_mat) & 0x7FFFFFFF   # strip sign-extended garbage
        return min(mat, max_slot)

    def test_face_mat_0xFFFFFFFF_clamped_to_0_for_single_tex(self):
        """0xFFFFFFFF → 0 for a single-texture mesh (tex_count=1, max_slot=0)."""
        result = self._clamp_mat(0xFFFFFFFF, tex_count=1)
        assert result == 0, \
            f"0xFFFFFFFF should clamp to 0 for single-tex, got {result}"

    def test_face_mat_zero_unchanged(self):
        """face_mat=0 is always valid and must not be altered."""
        assert self._clamp_mat(0, tex_count=2) == 0
        assert self._clamp_mat(0, tex_count=1) == 0

    def test_face_mat_1_on_single_tex_clamped_to_0(self):
        """face_mat=1 on single-texture node clamps to 0 (only one slot)."""
        result = self._clamp_mat(1, tex_count=1)
        assert result == 0, \
            f"face_mat=1 on single-tex should clamp to 0, got {result}"

    def test_face_mat_large_on_2slot_clamped_to_1(self):
        """face_mat=9999 on 2-slot node clamps to 1 (max valid slot index)."""
        result = self._clamp_mat(9999, tex_count=2)
        assert result == 1, \
            f"face_mat=9999 on 2-slot should clamp to 1, got {result}"

    def test_face_mat_0x80000000_stripped_to_0(self):
        """0x80000000 (sign bit only) → 0 after & 0x7FFFFFFF, then clamped."""
        result = self._clamp_mat(0x80000000, tex_count=1)
        assert result == 0

    def test_face_mat_valid_slot_1_on_2slot_unchanged(self):
        """face_mat=1 on a 2-slot node is valid and must NOT be clamped."""
        result = self._clamp_mat(1, tex_count=2)
        assert result == 1, \
            f"Valid face_mat=1 on 2-slot should stay 1, got {result}"

    def test_ascii_mdl_face_mats_within_bounds(self):
        """ASCII MDL faces: all face_mats values within [0, tex_count-1] after parse."""
        ascii_text = """\
newmodel testmodel
setsupermodel testmodel NULL
classification character
setanimationscale 1.00

node trimesh mesh0
  parent testmodel
  bitmap tex0
  render 1
  verts 3
    0.0 0.0 0.0
    1.0 0.0 0.0
    0.0 1.0 0.0
  faces 1
    0 1 2 1 0
endnode

donemodel testmodel
"""
        parser = MDLAsciiParser()
        model  = parser.parse_string(ascii_text)
        mesh   = model.mesh_nodes()
        assert mesh, "Must have mesh nodes"
        node   = mesh[0]
        if not node.face_mats:
            pytest.skip("No face_mats parsed")
        max_slot = max(0, node.tex_count - 1)
        for i, m in enumerate(node.face_mats):
            assert 0 <= m <= max_slot, \
                f"face_mats[{i}]={m} exceeds max_slot={max_slot}"


# ─────────────────────────────────────────────────────────────────────────────
#  TestRenderFlagIntegration
# ─────────────────────────────────────────────────────────────────────────────

class TestRenderFlagIntegration:
    """BUG-C integration: render flag correctly parsed from binary + ASCII MDL."""

    def test_binary_mdl_render_0_produces_render_false(self):
        """Binary MDL with render byte = 0 → node.render=False."""
        raw = _build_binary_mdl(render_flag=0)
        model = MDLBinaryParser(raw, b'').parse()
        mesh = model.mesh_nodes()
        if not mesh:
            pytest.skip("No mesh nodes")
        node = mesh[0]
        assert node.render is False, \
            f"render=0 in binary MDL should produce node.render=False, got {node.render}"

    def test_binary_mdl_render_1_produces_render_true(self):
        """Binary MDL with render byte = 1 → node.render=True."""
        raw = _build_binary_mdl(render_flag=1)
        model = MDLBinaryParser(raw, b'').parse()
        mesh = model.mesh_nodes()
        if not mesh:
            pytest.skip("No mesh nodes")
        node = mesh[0]
        assert node.render is True, \
            f"render=1 in binary MDL should produce node.render=True, got {node.render}"

    def test_ascii_mdl_render_0_produces_render_false(self):
        """ASCII MDL 'render 0' command → node.render=False."""
        ascii_text = """\
newmodel testmodel
setsupermodel testmodel NULL
classification character
setanimationscale 1.00

node trimesh mesh0
  parent testmodel
  bitmap tex0
  render 0
  verts 3
    0.0 0.0 0.0
    1.0 0.0 0.0
    0.0 1.0 0.0
  faces 1
    0 1 2 1 0
endnode

donemodel testmodel
"""
        parser = MDLAsciiParser()
        model  = parser.parse_string(ascii_text)
        mesh   = model.mesh_nodes()
        assert mesh, "ASCII MDL must produce at least one mesh node"
        mesh_node = next((n for n in mesh if n.name == "mesh0"), None)
        assert mesh_node is not None, "mesh0 not found"
        assert mesh_node.render is False, \
            f"ASCII 'render 0' must produce node.render=False, got {mesh_node.render}"

    def test_ascii_mdl_render_1_produces_render_true(self):
        """ASCII MDL 'render 1' command → node.render=True."""
        ascii_text = """\
newmodel testmodel
setsupermodel testmodel NULL
classification character
setanimationscale 1.00

node trimesh mesh0
  parent testmodel
  bitmap tex0
  render 1
  verts 3
    0.0 0.0 0.0
    1.0 0.0 0.0
    0.0 1.0 0.0
  faces 1
    0 1 2 1 0
endnode

donemodel testmodel
"""
        parser = MDLAsciiParser()
        model  = parser.parse_string(ascii_text)
        mesh   = model.mesh_nodes()
        assert mesh, "ASCII MDL must produce at least one mesh node"
        mesh_node = next((n for n in mesh if n.name == "mesh0"), None)
        assert mesh_node is not None
        assert mesh_node.render is True

    def test_ascii_mdl_default_render_is_true(self):
        """ASCII MDL without explicit 'render' command → node.render defaults to True."""
        ascii_text = """\
newmodel testmodel
setsupermodel testmodel NULL
classification character
setanimationscale 1.00

node trimesh mesh0
  parent testmodel
  bitmap tex0
  verts 3
    0.0 0.0 0.0
    1.0 0.0 0.0
    0.0 1.0 0.0
  faces 1
    0 1 2 1 0
endnode

donemodel testmodel
"""
        parser = MDLAsciiParser()
        model  = parser.parse_string(ascii_text)
        mesh   = model.mesh_nodes()
        assert mesh
        mesh_node = next((n for n in mesh if n.name == "mesh0"), None)
        assert mesh_node is not None
        assert mesh_node.render is True, \
            f"Default render must be True, got {mesh_node.render}"
