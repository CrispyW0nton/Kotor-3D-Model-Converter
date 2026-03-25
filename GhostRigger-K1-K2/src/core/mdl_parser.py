"""
MDL Binary Parser  – reads KotOR 1 & 2 .mdl + .mdx files
MDL ASCII Parser   – reads decompiled text MDL (mdlops output)
MDL ASCII Writer   – writes text MDL for mdlops compilation
MDL Binary Writer  – writes binary MDL + MDX

Loading strategy (Phase 14.2):
  parse_files() → tries PyKotor bridge first (real disk KotOR MDL files),
                  falls back to legacy parser if bridge unavailable/fails.
  parse()       → always uses legacy parser (correct for synthetic MDLs
                  produced by MDLBinaryWriter; PyKotor may mis-read them).
"""

import struct, math, logging, os
from typing import List, Optional, Dict, Tuple
from pathlib import Path
from .model_data import (
    KotorModel, ModelNode, NodeFlags, GameVersion, Animation, AnimEvent,
    VertexSkinData, BoneWeight
)

log = logging.getLogger(__name__)

# ── PyKotor bridge (optional) ────────────────────────────────────────────────
_BRIDGE_AVAILABLE = False
try:
    from .pykotor_bridge import (
        load_model_via_pykotor as _bridge_load_mdl,
        is_pykotor_available as _bridge_is_available,
    )
    _BRIDGE_AVAILABLE = _bridge_is_available()
    log.debug(f"mdl_parser: PyKotor bridge {'available' if _BRIDGE_AVAILABLE else 'not available'}")
except Exception as _bridge_err:
    log.debug(f"mdl_parser: bridge import failed ({_bridge_err})")

# ─────────────────────────────  Helper  ──────────────────────────────

def _rstrip(b: bytes) -> str:
    """
    Read a null-terminated ASCII string from a fixed-width byte buffer.
    Stops at the FIRST null byte (correct for KotOR's 32/64-byte name fields).
    Previously used rstrip(b'\x00') which only strips TRAILING nulls, leaving
    binary garbage when the null terminator is not at the very end of the field.
    """
    end = b.find(b'\x00')
    if end < 0:
        end = len(b)
    return b[:end].decode('ascii', errors='replace').strip()

def _bpad(s: str, n: int) -> bytes:
    return s.encode('ascii')[:n].ljust(n, b'\x00')

def _ru32(data, off): return struct.unpack_from('<I', data, off)[0]
def _rf32(data, off): return struct.unpack_from('<f', data, off)[0]
def _ru16(data, off): return struct.unpack_from('<H', data, off)[0]

# ─────────────────────────────  Binary Parser  ──────────────────────────────

class MDLBinaryParser:
    """
    Parses a binary KotOR MDL + MDX pair into a KotorModel.
    All offsets in the MDL are relative to byte 12 (after the file header).

    Usage:
        # From bytes (original):
        parser = MDLBinaryParser(mdl_bytes, mdx_bytes)
        model  = parser.parse()

        # From file paths (convenience wrapper):
        parser = MDLBinaryParser.from_files("c_bantha.mdl", "c_bantha.mdx")
        model  = parser.parse()
        # OR combined:
        model  = MDLBinaryParser.parse_files("c_bantha.mdl", "c_bantha.mdx")
    """
    BASE = 12

    def __init__(self, mdl: bytes, mdx: bytes):
        self.mdl = mdl
        self.mdx = mdx
        self._names: List[str] = []
        self._cache: Dict[int, ModelNode] = {}
        self.model = KotorModel()
        # Xbox flag: set to True when function pointer identifies an Xbox binary.
        # Xbox models differ in: bone_map array uses Sint16LE (not float32),
        # MDX per-vertex bone indices use 4×uint16 (not 4×float), and the
        # skin section header skips 8 bytes (not 12) before the MDX offsets.
        # Confirmed by xoreos model_kotor.cpp readSkin() and kotorblender reader.py.
        self._is_xbox: bool = False

    @classmethod
    def from_files(cls, mdl_path: str, mdx_path: str = "") -> 'MDLBinaryParser':
        """Convenience constructor: read MDL/MDX from disk then create parser."""
        mdl_data = Path(mdl_path).read_bytes()
        if mdx_path:
            mdx_data = Path(mdx_path).read_bytes() if Path(mdx_path).exists() else b''
        else:
            # Try sibling .mdx file automatically
            mdx_guess = Path(mdl_path).with_suffix('.mdx')
            mdx_data = mdx_guess.read_bytes() if mdx_guess.exists() else b''
        return cls(mdl_data, mdx_data)

    @classmethod
    def parse_files(cls, mdl_path: str, mdx_path: str = "") -> KotorModel:
        """One-shot: parse MDL/MDX files and return KotorModel.

        Tries the PyKotor bridge first (correct UV, skin, animation handling),
        falls back to the legacy parser if the bridge is unavailable or fails.
        """
        if _BRIDGE_AVAILABLE:
            try:
                model = _bridge_load_mdl(str(mdl_path), str(mdx_path) if mdx_path else '')
                if model is not None:
                    log.debug(f"parse_files: loaded '{mdl_path}' via PyKotor bridge")
                    return model
            except Exception as e:
                log.debug(f"parse_files: bridge failed ({e}), falling back to legacy parser")

        # Legacy parser fallback
        parser = cls.from_files(mdl_path, mdx_path)
        model  = parser.parse()
        model.mdl_path = str(mdl_path)
        model.mdx_path = str(mdx_path) if mdx_path else str(Path(mdl_path).with_suffix('.mdx'))
        log.debug(f"parse_files: loaded '{mdl_path}' via legacy parser")
        return model

    # ── Public entry point ──────────────────────────────────────────────────

    def parse(self) -> KotorModel:
        B = self.BASE
        d = self.mdl

        if len(d) < B + 168:
            raise ValueError("MDL file too small")

        # File header (12 bytes)
        # [0] unused, [4] mdl_size, [8] mdx_size

        # Geometry header at offset B (80 bytes)
        fp1, fp2 = _ru32(d, B), _ru32(d, B+4)
        self.model.name = _rstrip(d[B+8: B+40])
        root_node_off   = _ru32(d, B+40)
        node_count      = _ru32(d, B+44)
        geo_type        = struct.unpack_from('B', d, B+77)[0]

        # Detect game version and platform (PC vs Xbox).
        # Xbox function pointer values from KotorBlender types.py:
        #   K1 Xbox fp1 = 4254992, K2 Xbox fp1 = 4285872
        # PC function pointer values (existing detection):
        #   K1 PC fp1 = 4273776 or 4273392, K2 PC fp1 = 4285200 or 4284816
        _K1_XBOX_FP1 = 4254992
        _K2_XBOX_FP1 = 4285872
        if   fp1 in (4273776, 4273392): self.model.game_version = GameVersion.K1
        elif fp1 in (4285200, 4284816): self.model.game_version = GameVersion.K2
        elif fp1 == _K1_XBOX_FP1:
            self.model.game_version = GameVersion.K1; self._is_xbox = True
        elif fp1 == _K2_XBOX_FP1:
            self.model.game_version = GameVersion.K2; self._is_xbox = True
        else:
            self.model.game_version = GameVersion.K1
        if self._is_xbox:
            log.debug(f"Xbox MDL detected (fp1=0x{fp1:08x}), using int16 bone encoding")

        # Model header at offset B+80 (88 bytes)
        M = B + 80
        raw_model_type = struct.unpack_from('B', d, M)[0]
        self.model.model_type = raw_model_type
        # Map raw model_type byte → classification string
        # Verified against KotorBlender types.py CLASS_BY_VALUE (seedhartha/kotorblender):
        #   0x00 (0)  = OTHER/EFFECT  – area/room/FX geometry
        #   0x01 (1)  = EFFECT        – particle FX models
        #   0x02 (2)  = TILE          – tile/misc models
        #   0x04 (4)  = CHARACTER     – humanoids, creatures, NPCs
        #   0x08 (8)  = DOOR          – door models
        #   0x10 (16) = LIGHTSABER    – saber blade geometry (was previously unmapped!)
        #   0x20 (32) = PLACEABLE     – inventory items, placeables
        #   0x40 (64) = FLYER         – small creatures, camera models
        _MODEL_TYPE_CLS = {
            0: 'effect', 1: 'effects', 2: 'tile',
            4: 'character', 8: 'door', 16: 'lightsaber',
            32: 'placeable', 64: 'flyer',
        }
        self.model.classification = _MODEL_TYPE_CLS.get(raw_model_type, 'character')
        # Subclassification byte (M+1): Confirmed by PyKotor/reone as a uint8 at
        # binary offset 0x51.  Default value is 4 for Placeable, 0 otherwise.
        # Purpose is undocumented; preserved verbatim for round-trip fidelity.
        self.model.subclassification = struct.unpack_from('B', d, M+1)[0]
        # M+2: Unknown byte — PyKotor wiki notes "possibly smoothing-related".
        # Preserved for round-trip fidelity.
        self.model.unknown_byte = struct.unpack_from('B', d, M+2)[0]
        # M+3: Affected_by_fog flag (0=no fog, 1=fog)
        self.model.disable_fog = bool(struct.unpack_from('B', d, M+3)[0])
        anim_array_off = _ru32(d, M+8)
        anim_count     = _ru32(d, M+12)
        bx1,by1,bz1   = struct.unpack_from('<fff', d, M+24)
        bx2,by2,bz2   = struct.unpack_from('<fff', d, M+36)
        self.model.bb_min = (bx1,by1,bz1)
        self.model.bb_max = (bx2,by2,bz2)
        self.model.radius  = _rf32(d, M+48)
        self.model.anim_scale = _rf32(d, M+52)
        self.model.supermodel = _rstrip(d[M+56:M+88])

        # Name array header at offset B+168
        N = B + 168
        names_arr_off  = _ru32(d, N+16)
        names_count    = _ru32(d, N+20)

        # Read name strings
        self._names = []
        for i in range(min(names_count, 4096)):
            ptr_off = B + names_arr_off + i*4
            if ptr_off+4 > len(d): break
            str_off = _ru32(d, ptr_off)
            abs_off = B + str_off
            if abs_off < len(d):
                end = d.find(b'\x00', abs_off)
                end = end if end > abs_off else abs_off+64
                self._names.append(d[abs_off:end].decode('ascii','replace'))

        # Parse node tree
        # Wrapped in a broad except so unusual models (RARE_CHAR type-64 like
        # c_brith, corrupt node offsets) cannot crash the whole application.
        if root_node_off:
            try:
                self.model.root_node = self._parse_node(B + root_node_off, None)
            except Exception as e:
                import traceback as _tb
                log.error(
                    f"_parse_node failed for '{self.model.name}': {e}\n"
                    f"  model_type={self.model.model_type}  "
                    f"game_version={self.model.game_version}  "
                    f"root_node_off=0x{root_node_off:08x}  "
                    f"MDL_size={len(d)}\n"
                    f"Full traceback:\n{_tb.format_exc()}"
                )
                # Attempt a minimal stub root so the app can display something
                if self.model.root_node is None:
                    from .model_data import ModelNode
                    self.model.root_node = ModelNode(name=self.model.name or 'root')

        # ── Parse animations ─────────────────────────────────────────────────
        if anim_count > 0 and anim_array_off > 0:
            self._parse_animations(anim_array_off, anim_count)

        self.model.compute_bounds()
        # ── Post-process: generate flat normals for mesh nodes lacking them ──
        self._generate_missing_normals(self.model)
        # ── Post-process: apply bind-pose controllers to node properties ──────
        self._apply_bind_pose_controllers(self.model)
        return self.model

    @staticmethod
    def _generate_missing_normals(model):
        """
        Generate flat (area-weighted smooth) normals for every mesh node that
        lacks them.  Bone-proxy meshes (MESH but not SKIN, no UVs) receive
        normals so the viewport can shade them correctly.

        Uses an iterative walk to avoid Python recursion-limit crashes on
        deeply nested models (e.g. c_brith RARE_CHAR type-64).
        """
        def _iter_nodes(root):
            stack = [root]
            while stack:
                n = stack.pop()
                yield n
                for c in reversed(n.children):
                    stack.append(c)

        if model.root_node is None:
            return
        for node in _iter_nodes(model.root_node):
            if not node.is_mesh:
                continue
            if not node.vertices:
                continue
            if node.normals and len(node.normals) == len(node.vertices):
                continue  # already has valid normals
            faces = node.faces if (hasattr(node, 'faces') and node.faces) else []
            verts = node.vertices
            ns  = [[0.0, 0.0, 0.0] for _ in range(len(verts))]
            cnt = [0] * len(verts)
            for face in faces:
                if len(face) < 3:
                    continue
                v1, v2, v3 = face[0], face[1], face[2]
                if max(v1, v2, v3) >= len(verts):
                    continue
                ax, ay, az = verts[v1]
                bx, by, bz = verts[v2]
                cx, cy, cz = verts[v3]
                ux, uy, uz = bx-ax, by-ay, bz-az
                vx, vy, vz = cx-ax, cy-ay, cz-az
                nx = uy*vz - uz*vy
                ny = uz*vx - ux*vz
                nz = ux*vy - uy*vx
                length = math.sqrt(nx*nx + ny*ny + nz*nz) or 1.0
                nx /= length; ny /= length; nz /= length
                for vi in (v1, v2, v3):
                    ns[vi][0] += nx; ns[vi][1] += ny; ns[vi][2] += nz
                    cnt[vi] += 1
            result = []
            for i, n in enumerate(ns):
                if cnt[i]:
                    length = math.sqrt(n[0]*n[0]+n[1]*n[1]+n[2]*n[2]) or 1.0
                    result.append((n[0]/length, n[1]/length, n[2]/length))
                else:
                    result.append((0.0, 0.0, 1.0))
            node.normals = result
            log.debug(f"Generated {len(result)} normals for '{node.name}'")

    @staticmethod
    def _apply_bind_pose_controllers(model) -> None:
        """
        Apply bind-pose controller values to node properties.

        The binary MDL stores many material/transform properties as animation
        controllers rather than plain header fields — including self-illumination
        colour and alpha.

        This post-process step reads the FIRST keyframe value of each controller
        and pushes it into the corresponding ModelNode field, so the viewport and
        rigging tools can access them without having to inspect raw controller lists.

        Controller type IDs (verified against KotorBlender types.py):
          8   position              → node.position  (override header if all-zero)
          20  orientation           → node.rotation  (override header if identity)
          100 CTRL_MESH_SELFILLUMCOLOR → node.selfillum  (3 floats: r,g,b)
          132 CTRL_MESH_ALPHA          → node.alpha       (1 float)
        """
        if model.root_node is None:
            return

        def _iter_nodes(root):
            stack = [root]
            while stack:
                n = stack.pop()
                yield n
                for c in reversed(n.children):
                    stack.append(c)

        for node in _iter_nodes(model.root_node):
            if not hasattr(node, 'controllers') or not node.controllers:
                continue
            for ctrl in node.controllers:
                ctype  = ctrl.get('type', -1)
                values = ctrl.get('values', [])
                if not values:
                    continue
                v0 = values[0]  # first keyframe = bind pose

                if ctype == 100 and len(v0) >= 3:
                    # self-illumination colour — visible on droid eyes, glass panels, etc.
                    # CTRL_MESH_SELFILLUMCOLOR = 100 (not 132); confirmed against xoreos
                    # Verified against KotorBlender types.py CTRL_MESH_SELFILLUMCOLOR=100
                    node.selfillum = (float(v0[0]), float(v0[1]), float(v0[2]))

                elif ctype == 132 and len(v0) >= 1:
                    # per-node alpha (transparency)
                    # CTRL_MESH_ALPHA = 132 (not 100); confirmed against xoreos
                    # Verified against KotorBlender types.py CTRL_MESH_ALPHA=132
                    node.alpha = float(v0[0])

                elif ctype == 128 and len(v0) >= 1:
                    # xoreos CTRL_ALPHA = 128 (some BioWare tools use 128, others 132)
                    # Only apply if node.alpha is still default (1.0) to avoid
                    # overwriting a legitimate 132-based alpha read earlier.
                    if abs(node.alpha - 1.0) < 1e-6:
                        node.alpha = float(v0[0])

                elif ctype == 8 and len(v0) >= 3:
                    # Bind-pose position controller.
                    # KotOR binary MDL: the header position field IS the primary
                    # bind-pose source and is always set correctly by the exporter.
                    # The controller's first keyframe duplicates the header value.
                    # Only override the header if it is exactly (0,0,0) AND the
                    # controller has a non-zero value — this handles the minority of
                    # models where the exporter left the header position at zero and
                    # stored the real position only in the controller.
                    # GUARD: validate controller values are finite before applying.
                    import math as _m_pos
                    cv0, cv1, cv2 = float(v0[0]), float(v0[1]), float(v0[2])
                    if (_m_pos.isfinite(cv0) and _m_pos.isfinite(cv1) and _m_pos.isfinite(cv2)):
                        px, py, pz = node.position
                        if abs(px) < 1e-9 and abs(py) < 1e-9 and abs(pz) < 1e-9:
                            if abs(cv0) > 1e-9 or abs(cv1) > 1e-9 or abs(cv2) > 1e-9:
                                node.position = (cv0, cv1, cv2)

                elif ctype == 20 and len(v0) >= 4:
                    # Bind-pose orientation controller: the controller IS the
                    # authoritative bind-pose source in binary MDL; the header
                    # rotation is often left at identity/zero as a placeholder.
                    # CRITICAL FIX (v5.2): Do NOT force positive-w canonicalization
                    # here.  While q and -q represent the same rotation, forcing
                    # w > 0 alters the quaternion's sign, which interferes with
                    # _quat_normalize_bind's threshold test (|w| < 0.05 triggers
                    # the NWN 180-X collapse).  A controller value like w=-0.02
                    # represents a near-180° X rotation that SHOULD be collapsed;
                    # if we negate it to w=+0.02 and the threshold passes the
                    # collapse, we get the correct behavior.  But if the intent
                    # was a very-small w from a slightly non-180 rotation, we
                    # must preserve the sign so _quat_normalize_bind can still
                    # identify it as NOT a pure 180-X and preserve it.
                    # The positive-w convention is only needed for ANIMATION
                    # interpolation (to prevent quaternion flips between keyframes);
                    # for the static bind pose it creates more problems than it solves.
                    cx, cy, cz, cw = float(v0[0]), float(v0[1]), float(v0[2]), float(v0[3])
                    mag = (cx*cx + cy*cy + cz*cz + cw*cw) ** 0.5
                    if mag > 1e-9:
                        cx /= mag; cy /= mag; cz /= mag; cw /= mag
                        node.rotation = (cx, cy, cz, cw)
                    # else: degenerate zero-quaternion — leave node.rotation unchanged

    # ── Animation parser ────────────────────────────────────────────────────

    def _parse_animations(self, anim_array_off: int, anim_count: int):
        """
        Parse all animation blocks from the binary MDL.

        The animation array is an array of offsets (relative to BASE), each
        pointing to an animation geometry header.

        Animation geometry header layout (same as model geo header):
          +0   funcptr1 (4)
          +4   funcptr2 (4)
          +8   name (32)
          +40  root_node_off (4)   ← offset of anim root node (from BASE)
          +44  node_count (4)
          +48  unknown (4)
          +52  geometry_type (1 byte at +77)
          → total geo header: 80 bytes

        Animation model header (at +80):
          +0   length (float)            ← animation length in seconds
          +4   transition_time (float)   ← blend/transition time
          +8   anim_root name (32 bytes) ← root node name to animate
          +40  events array off (4)
          +44  events count (4)
          +48  events count2 (4)
        """
        B = self.BASE
        d = self.mdl

        for i in range(min(anim_count, 512)):
            ptr_off = B + anim_array_off + i * 4
            if ptr_off + 4 > len(d):
                break
            anim_off = _ru32(d, ptr_off)
            if anim_off == 0:
                continue
            abs_anim = B + anim_off
            try:
                anim = self._parse_one_animation(abs_anim)
                if anim:
                    self.model.animations.append(anim)
            except Exception as e:
                log.debug(f"Animation[{i}] parse error: {e}")

        log.debug(f"Parsed {len(self.model.animations)} animations for {self.model.name}")

    def _parse_one_animation(self, abs_off: int) -> Optional[Animation]:
        """Parse a single animation block starting at abs_off."""
        B = self.BASE
        d = self.mdl

        if abs_off + 120 > len(d):
            return None

        o = abs_off

        # Geometry header (80 bytes)
        fp1 = _ru32(d, o); o += 4
        fp2 = _ru32(d, o); o += 4
        anim_name   = _rstrip(d[o:o+32]); o += 32
        root_off    = _ru32(d, o); o += 4
        node_count  = _ru32(d, o); o += 4
        o += 4   # unknown
        # skip 48 bytes more to reach +80
        o = abs_off + 80

        # Animation model header (starts at +80)
        # Binary layout (verified against c_bantha.mdl raw bytes):
        #   +80  length (float)          ← animation length in seconds
        #   +84  transition_time (float) ← blend/transition time
        #   +88  anim_root_name (32 b)   ← name of the root node to animate
        #   +120 events_offset (uint32)
        #   +124 events_count  (uint32)
        #   +128 events_alloc  (uint32)
        # Previous code had anim_root_name first (at +80) which gave garbage bytes.
        length         = _rf32(d, o); o += 4
        trans_time     = _rf32(d, o); o += 4
        anim_root_name = _rstrip(d[o:o+32]); o += 32
        events_off     = _ru32(d, o); o += 4
        events_cnt     = _ru32(d, o); o += 4
        o += 4   # events_cnt2

        anim = Animation(
            name            = anim_name if anim_name else f"anim_{len(self.model.animations)}",
            length          = max(0.0, length),
            transition_time = trans_time,
            anim_root       = anim_root_name,
        )

        # Parse events
        if events_cnt > 0 and events_off > 0:
            ev_abs = B + events_off
            for j in range(min(events_cnt, 256)):
                ep = ev_abs + j * 36   # event = float time (4) + name (32)
                if ep + 36 > len(d): break
                ev_time = _rf32(d, ep)
                ev_name = _rstrip(d[ep+4:ep+36])
                anim.events.append(AnimEvent(time=ev_time, name=ev_name))

        # Parse animation node tree
        if root_off > 0:
            anim_cache: Dict[int, ModelNode] = {}
            anim_node = self._parse_anim_node(B + root_off, None, anim_cache)
            if anim_node:
                # Collect all animation nodes
                def _collect(n):
                    anim.nodes.append(n)
                    for c in n.children: _collect(c)
                _collect(anim_node)

        # ── Derive animation length from keyframe times if stored length is 0 ──
        # Many KotOR animations store length = 0.0 in the header even though
        # they have valid keyframe data.  Derive the real length from the max
        # time value across all controller tracks so playback/scrubbing works.
        #
        # BUG-04 FIX: use max(ctrl['times']) instead of ctrl['times'][-1].
        # KotOR MDL keyframe arrays are not guaranteed to be sorted; using [-1]
        # would return the last-written key (often the loopback key at t=0 for
        # looping anims), producing a length of 0 and breaking scrubbing.
        # max() is O(n) but always correct regardless of key order.
        if anim.length <= 0.0 and anim.nodes:
            max_t = 0.0
            for an in anim.nodes:
                for ctrl in an.controllers:
                    if ctrl['times']:
                        max_t = max(max_t, max(ctrl['times']))  # BUG-04: max() not [-1]
            if max_t > 0.0:
                anim.length = max_t
                log.debug(f"  Anim '{anim.name}': derived length={anim.length:.3f}s from keyframes")

        log.debug(f"  Anim '{anim.name}': len={anim.length:.2f}s, "
                  f"{len(anim.nodes)} nodes, {len(anim.events)} events")
        return anim

    def _parse_anim_node(self, abs_off: int, parent: Optional[ModelNode],
                         cache: Dict[int, ModelNode]) -> Optional[ModelNode]:
        """Parse an animation node (same base layout as geometry node)."""
        if abs_off in cache:
            return cache[abs_off]
        d = self.mdl
        B = self.BASE
        o = abs_off

        if o + 80 > len(d):
            return None

        node_type  = _ru16(d, o); o += 2
        index_num  = _ru16(d, o); o += 2
        node_num   = _ru16(d, o); o += 2
        pad        = _ru16(d, o); o += 2
        root_off   = _ru32(d, o); o += 4
        parent_off = _ru32(d, o); o += 4
        px, py, pz = struct.unpack_from('<fff', d, o); o += 12
        # Binary format stores orientation as (w, x, y, z) — reorder to internal (x,y,z,w)
        rw_bin, rx, ry, rz = struct.unpack_from('<ffff', d, o); o += 16
        rw = rw_bin
        child_arr_off = _ru32(d, o); o += 4
        child_cnt     = _ru32(d, o); o += 4
        child_cnt2    = _ru32(d, o); o += 4
        ctrl_arr_off  = _ru32(d, o); o += 4
        ctrl_cnt      = _ru32(d, o); o += 4
        ctrl_cnt2     = _ru32(d, o); o += 4
        ctrl_data_off = _ru32(d, o); o += 4
        ctrl_data_cnt = _ru32(d, o); o += 4
        ctrl_data_cnt2= _ru32(d, o); o += 4

        name = (self._names[index_num] if 0 <= index_num < len(self._names)
                else self._names[node_num] if 0 <= node_num < len(self._names)
                else f"node_{index_num}")

        node = ModelNode(
            name=name, flags=node_type, index=index_num, number=node_num,
            position=(px, py, pz), rotation=(rx, ry, rz, rw), parent=parent
        )
        cache[abs_off] = node

        # Parse controllers for this animation node
        if ctrl_cnt > 0 and ctrl_arr_off > 0 and ctrl_data_off > 0:
            node.controllers = self._parse_controllers(
                ctrl_arr_off, ctrl_cnt, ctrl_data_off, ctrl_data_cnt)

        # Children
        for i in range(min(child_cnt, 512)):
            ptr = B + child_arr_off + i * 4
            if ptr + 4 > len(d): break
            c_off = _ru32(d, ptr)
            if c_off == 0: continue
            child = self._parse_anim_node(B + c_off, node, cache)
            if child is not None and child not in node.children:
                node.children.append(child)

        return node

    def _parse_controllers(self, ctrl_arr_off: int, ctrl_cnt: int,
                            ctrl_data_off: int, ctrl_data_cnt: int) -> List[Dict]:
        """
        Parse the controller array for a node.

        Controller entry (16 bytes):
          +0  type (uint32)    – controller type ID
          +4  unknown (uint16)
          +6  row_count (uint16) – number of keyframes
          +8  timekey_off (uint16) – offset into ctrl_data array for time keys
          +10 data_off (uint16)   – offset into ctrl_data array for values
          +12 columns (uint8)    – number of float columns per keyframe
          +13 padding (3 bytes)

        Controller data is a packed float32 array (ctrl_data).

        Controller type IDs (from NWN/KotOR research):
          8   = position                    (3 floats: x,y,z)
          20  = orientation                 (4 floats: x,y,z,w quaternion)
          36  = scale                       (1 float)
          100 = CTRL_MESH_SELFILLUMCOLOR    (3 floats: r,g,b)  ← KotorBlender-verified
          132 = CTRL_MESH_ALPHA             (1 float)          ← KotorBlender-verified

        CRITICAL: xoreos uses Alpha=128, KotorBlender uses Alpha=132.
        We follow KotorBlender since it is more authoritative for KotOR binary format.
        Previous docstring had these SWAPPED (100=alpha, 132=selfillum) which was WRONG.
        """
        B = self.BASE
        d = self.mdl
        controllers = []

        # Controller type IDs verified against KotorBlender types.py and xoreos.
        # Full emitter controller table (IDs 80–392) sourced from
        # KotorBlender types.py EMITTER_CONTROLLER_KEYS.  All 31 emitter
        # controllers decoded.  Light controllers (76–140) also distinguished
        # from mesh controllers.
        # Controller type ID → human-readable name mapping.
        # IDs that overlap between Light, Mesh, and Emitter contexts
        # (Python dict: later entry wins, so emitter names take priority for
        # overlapping IDs — this matches how the KotOR engine resolves them):
        #   80  = CTRL_EMITTER_ALPHAEND   (was CTRL_LIGHT_ALPHAEND — same value)
        #   84  = CTRL_EMITTER_ALPHASTART (was CTRL_LIGHT_ALPHASTART)
        #   88  = CTRL_LIGHT_RADIUS = 88 (KotOR.js); CTRL_EMITTER_BIRTHRATE = 88
        #   96  = CTRL_EMITTER_COMBINETIME (also CTRL_LIGHT_SHADOWRADIUS)
        #   100 = CTRL_MESH_SELFILLUMCOLOR=3ch / CTRL_EMITTER_DRAG=1ch (node type disambiguates)
        #   140 = CTRL_EMITTER_RANDVEL (also CTRL_LIGHT_MULTIPLIER)
        CTRL_TYPE_NAMES = {
            8:   'position',
            20:  'orientation',
            36:  'scale',
            76:  'color',              # CTRL_LIGHT_COLOR (3 floats r,g,b)
            80:  'alphaend',           # CTRL_EMITTER_ALPHAEND = 80
            84:  'alphastart',         # CTRL_EMITTER_ALPHASTART = 84
            88:  'radius',             # CTRL_LIGHT_RADIUS=88 (KotOR.js) / CTRL_EMITTER_BIRTHRATE=88
            92:  'bounce_co',          # CTRL_EMITTER_BOUNCE_CO = 92
            96:  'combinetime',        # CTRL_EMITTER_COMBINETIME = 96
            100: 'selfillum_color',    # CTRL_MESH_SELFILLUMCOLOR = 100 (3 floats r,g,b)
            104: 'fps',                # CTRL_EMITTER_FPS = 104
            108: 'frameend',           # CTRL_EMITTER_FRAMEEND = 108
            112: 'framestart',         # CTRL_EMITTER_FRAMESTART = 112
            116: 'grav',               # CTRL_EMITTER_GRAV = 116
            120: 'lifeexp',            # CTRL_EMITTER_LIFEEXP = 120
            124: 'mass',               # CTRL_EMITTER_MASS = 124
            128: 'alpha_xoreos',       # xoreos CTRL_ALPHA = 128 (1 float)
            132: 'alpha',              # CTRL_MESH_ALPHA = 132 (1 float) KotorBlender
            136: 'particlerot',        # CTRL_EMITTER_PARTICLEROT = 136
            140: 'randvel',            # CTRL_EMITTER_RANDVEL = 140 / CTRL_LIGHT_MULTIPLIER
            144: 'sizestart',          # CTRL_EMITTER_SIZESTART = 144
            148: 'sizeend',            # CTRL_EMITTER_SIZEEND = 148
            152: 'sizestart_y',        # CTRL_EMITTER_SIZESTART_Y = 152
            156: 'sizeend_y',          # CTRL_EMITTER_SIZEEND_Y = 156
            160: 'spread',             # CTRL_EMITTER_SPREAD = 160
            164: 'threshold',          # CTRL_EMITTER_THRESHOLD = 164
            168: 'velocity',           # CTRL_EMITTER_VELOCITY = 168
            172: 'xsize',              # CTRL_EMITTER_XSIZE = 172
            176: 'ysize',              # CTRL_EMITTER_YSIZE = 176
            180: 'blurlength',         # CTRL_EMITTER_BLURLENGTH = 180
            184: 'lightningdelay',     # CTRL_EMITTER_LIGHTNINGDELAY = 184
            188: 'lightningradius',    # CTRL_EMITTER_LIGHTNINGRADIUS = 188
            192: 'lightningscale',     # CTRL_EMITTER_LIGHTNINGSCALE = 192
            196: 'lightningsubdiv',    # CTRL_EMITTER_LIGHTNINGSUBDIV = 196
            200: 'lightningzigzag',    # CTRL_EMITTER_LIGHTNINGZIGZAG = 200
            216: 'alphamid',           # CTRL_EMITTER_ALPHAMID = 216
            220: 'percentstart',       # CTRL_EMITTER_PERCENTSTART = 220
            224: 'percentmid',         # CTRL_EMITTER_PERCENTMID = 224
            228: 'percentend',         # CTRL_EMITTER_PERCENTEND = 228
            232: 'sizemid',            # CTRL_EMITTER_SIZEMID = 232
            236: 'sizemid_y',          # CTRL_EMITTER_SIZEMID_Y = 236
            240: 'randombirthrate',    # CTRL_EMITTER_RANDOMBIRTHRATE = 240
            252: 'targetsize',         # CTRL_EMITTER_TARGETSIZE = 252
            256: 'numcontrolpts',      # CTRL_EMITTER_NUMCONTROLPTS = 256
            260: 'controlptradius',    # CTRL_EMITTER_CONTROLPTRADIUS = 260
            264: 'controlptdelay',     # CTRL_EMITTER_CONTROLPTDELAY = 264
            268: 'tangentspread',      # CTRL_EMITTER_TANGENTSPREAD = 268
            272: 'tangentlength',      # CTRL_EMITTER_TANGENTLENGTH = 272
            284: 'colormid',           # CTRL_EMITTER_COLORMID = 284 (3 floats RGB)
            380: 'colorend',           # CTRL_EMITTER_COLOREND = 380 (3 floats RGB)
            392: 'colorstart',         # CTRL_EMITTER_COLORSTART = 392 (3 floats RGB)
            502: 'detonate',           # CTRL_EMITTER_DETONATE = 502 (KotOR.js Detonate)
        }

        ctrl_data_abs = B + ctrl_data_off

        CTRL_ORIENTATION = 20  # quaternion controller type
        _PACKED_QUAT_COLS = 2  # columns=2 signals packed quaternion (3×int16)
        # CTRL_FLAG_BEZIER (bit 0x10 in the columns byte): Bezier spline storage.
        # When this flag is set, each value row stores: value + in_tangent + out_tangent
        # (3× the normal column count).  Only the first value in each triplet is used
        # for simple playback; tangents are needed for smooth Bezier interpolation.
        # Source: KotorBlender types.py CTRL_FLAG_BEZIER = 0x10
        # Source: KotorBlender reader.py lines 802-805 (bezier = num_columns & 0x10)
        _CTRL_FLAG_BEZIER = 0x10

        for i in range(min(ctrl_cnt, 256)):
            ep = B + ctrl_arr_off + i * 16
            if ep + 16 > len(d): break

            ctrl_type  = _ru32(d, ep)
            unk        = _ru16(d, ep + 4)   # padding/reserved uint16 (KotorBlender: skip(2))
            row_count  = _ru16(d, ep + 6)
            time_off   = _ru16(d, ep + 8)
            data_off   = _ru16(d, ep + 10)
            columns_raw = struct.unpack_from('B', d, ep + 12)[0]

            # Decode CTRL_FLAG_BEZIER from the columns byte.
            # Bit 0x10: when set, each value row has 3× columns stored
            # (value + in_tangent + out_tangent).  The raw column count field
            # encodes: (actual_columns & 0xF) | (bezier_flag & 0x10).
            # Source: KotorBlender reader.py line 802-805.
            _is_bezier = bool(columns_raw & _CTRL_FLAG_BEZIER)
            columns = columns_raw & 0x0F  # strip bezier flag to get actual columns
            if columns == 0:
                columns = columns_raw  # fallback if flag-stripping gives 0
            # Bezier rows store 3× the actual columns (val + 2 tangents)
            _stride_cols = columns * 3 if _is_bezier else columns

            if row_count == 0 or columns == 0:
                continue
            # Sanity-cap: a real KotOR animation controller has at most a few
            # thousand keyframes.  Values above 4096 indicate corrupt/bad data;
            # skip rather than hang in a >65 k iteration loop.
            # Note: columns > 64 check uses the masked value (bezier bit stripped)
            if row_count > 4096 or columns > 64:
                continue

            type_name = CTRL_TYPE_NAMES.get(ctrl_type, f'ctrl_{ctrl_type}')

            # Read time keys
            times = []
            for k in range(row_count):
                tp = ctrl_data_abs + (time_off + k) * 4
                if tp + 4 > len(d): break
                times.append(_rf32(d, tp))

            # ── Read value data ─────────────────────────────────────────────
            # SPECIAL CASE: orientation controller with columns == 2
            # In KotOR binary MDL, when an orientation (type 20) controller has
            # columns == 2, each keyframe row is ONE packed uint32 using a
            # 10-11-11 bit packing scheme (from xoreos / NWN engine source):
            #
            #   temp   = ctrl_data[data_off + k]  (one uint32 per keyframe)
            #   x = 1.0 - (temp & 0x7FF)         / 1023.0   (11 bits, x)
            #   y = 1.0 - ((temp >> 11) & 0x7FF) / 1023.0   (11 bits, y)
            #   z = 1.0 - (temp >> 22)            / 511.0    (10 bits, z)
            #   mag2 = x*x + y*y + z*z
            #   w = -sqrt(1 - mag2)  if mag2 < 1   (w is negative in KotOR)
            #   otherwise: normalize xyz, w = 0.0
            #
            # The data_off and time_off are FLOAT32-ARRAY indices into the
            # node's controller data pool (same 4-byte stride for both time
            # and packed-quat rows, since each packed quat = 1 uint32 = 4 bytes).
            values = []
            if ctrl_type == CTRL_ORIENTATION and columns == _PACKED_QUAT_COLS:
                # ── Packed quaternion decoder (verified against KotorBlender reader.py
                # orientation_controller_to_quaternion + seedhartha/kotorblender) ──
                #
                # Each keyframe is stored as ONE uint32 with 10-11-11 bit packing:
                #   bits  0-10  (11 bits): x component  →  (bits / 1023.0) - 1.0
                #   bits 11-21  (11 bits): y component  →  (bits / 1023.0) - 1.0
                #   bits 22-31  (10 bits): z component  →  (bits /  511.0) - 1.0
                #   w = +sqrt(1 - x²-y²-z²)   (positive, nwn convention)
                #
                # CRITICAL FIX: Previous code used '1.0 - x/1023' which INVERTS
                # the sign of all xyz components, producing mirror-image rotations
                # on every packed-quat animation keyframe.  The correct formula is
                # '(x/1023.0) - 1.0' as used in both xoreos and KotorBlender.
                for k in range(row_count):
                    dp = ctrl_data_abs + (data_off + k) * 4
                    if dp + 4 > len(d): break
                    temp = struct.unpack_from('<I', d, dp)[0]
                    # Correct decoding formula (KotorBlender-verified):
                    qx = ((temp & 0x7FF) / 1023.0) - 1.0
                    qy = (((temp >> 11) & 0x7FF) / 1023.0) - 1.0
                    qz = ((temp >> 22) / 511.0) - 1.0
                    mag2 = qx*qx + qy*qy + qz*qz
                    if mag2 < 1.0:
                        qw = math.sqrt(1.0 - mag2)   # always positive (KotorBlender convention)
                    else:
                        # over-unit quaternion (rounding error): normalize and set w=0
                        nl = math.sqrt(mag2)
                        if nl > 1e-9:
                            qx /= nl; qy /= nl; qz /= nl
                        qw = 0.0
                    # Note: KotorBlender does NOT negate xyz when qw<0 for packed quats;
                    # the formula always produces qw>=0.  We preserve this convention.
                    values.append([qx, qy, qz, qw])
            else:
                # KotOR uses Bezier-spline storage for position (cols=3n)
                # and sometimes packs extra tangent floats after the base value.
                # Canonical component counts (VERIFIED against KotorBlender types.py):
                #   position=3, orientation=4, scale/alpha=1, colour/selfillum=3
                # CRITICAL FIX: previous table had 100=1(alpha) and 132=3(selfillum)
                # which is SWAPPED. Correct mapping:
                #   100 = CTRL_MESH_SELFILLUMCOLOR (3 floats: r,g,b)
                #   128 = xoreos CTRL_ALPHA (1 float)
                #   132 = CTRL_MESH_ALPHA (1 float) - KotorBlender convention
                _CANONICAL_COLS = {
                    8:   3,   # position (x,y,z)
                    20:  4,   # orientation (x,y,z,w)
                    36:  1,   # scale
                    76:  3,   # color (r,g,b)
                    80:  1,   # radius / alphaend
                    84:  1,   # shadow_radius / alphastart
                    88:  1,   # vertical_displacement / birthrate
                    92:  1,   # bounce_co
                    96:  1,   # multiplier / combinetime
                    100: 3,   # CTRL_MESH_SELFILLUMCOLOR (r,g,b) / drag (1)
                    104: 1,   # fps
                    108: 1,   # frameend
                    112: 1,   # framestart
                    116: 1,   # grav
                    120: 1,   # lifeexp
                    124: 1,   # mass
                    128: 1,   # xoreos CTRL_ALPHA / p2p_bezier2
                    132: 1,   # CTRL_MESH_ALPHA / p2p_bezier3
                    136: 1,   # particlerot
                    140: 1,   # texture_anim / randvel
                    144: 1,   # sizestart
                    148: 1,   # sizeend
                    152: 1,   # sizestart_y
                    156: 1,   # sizeend_y
                    160: 1,   # spread
                    164: 1,   # threshold
                    168: 1,   # velocity
                    172: 1,   # xsize
                    176: 1,   # ysize
                    180: 1,   # blurlength
                    184: 1,   # lightningdelay
                    188: 1,   # lightningradius
                    192: 1,   # lightningscale
                    196: 1,   # lightningsubdiv
                    200: 1,   # lightningzigzag
                    216: 1,   # alphamid
                    220: 1,   # percentstart
                    224: 1,   # percentmid
                    228: 1,   # percentend
                    232: 1,   # sizemid
                    236: 1,   # sizemid_y
                    240: 1,   # CTRL_EMITTER_RANDOMBIRTHRATE (single float, emitter-only)
                    252: 1,   # targetsize
                    256: 1,   # numcontrolpts
                    260: 1,   # controlptradius
                    264: 1,   # controlptdelay
                    268: 1,   # tangentspread
                    272: 1,   # tangentlength
                    284: 3,   # colormid (r,g,b)
                    380: 3,   # colorend (r,g,b)
                    392: 3,   # colorstart (r,g,b)
                    502: 1,   # CTRL_EMITTER_DETONATE = 502 (KotOR.js Detonate, 1 float)
                }
                canon = _CANONICAL_COLS.get(ctrl_type, columns)
                read_cols = min(columns, canon)

                # CTRL_FLAG_BEZIER: the data stride is _stride_cols (= columns * 3
                # when bezier, else columns).  We read only the first `read_cols`
                # components of each row; the tangent data (positions 1 and 2 in
                # each bezier triplet) are discarded for now — they would be needed
                # only for smooth Bezier interpolation between keys.
                for k in range(row_count):
                    row_vals = []
                    for col in range(read_cols):
                        vp = ctrl_data_abs + (data_off + k * _stride_cols + col) * 4
                        if vp + 4 > len(d): break
                        v = _rf32(d, vp)
                        # Sanitize: treat NaN or extremely large values as 0.0
                        if not math.isfinite(v) or abs(v) > 1e30:
                            v = 0.0
                        row_vals.append(v)
                    if row_vals:
                        values.append(row_vals)

            if times and values:
                # Sanitize time keys: drop pairs where time is NaN/Inf
                clean_times, clean_values = [], []
                for t_k, v_k in zip(times, values):
                    if math.isfinite(t_k):
                        clean_times.append(t_k)
                        clean_values.append(v_k)
                if clean_times:
                    controllers.append({
                        'type':    ctrl_type,
                        'name':    type_name,
                        'times':   clean_times,
                        'values':  clean_values,
                        'columns': columns,
                        'bezier':  _is_bezier,  # True if data uses Bezier spline storage
                    })

        return controllers

    # ── Node parser  ────────────────────────────────────────────────────────

    def _parse_node(self, abs_off: int, parent: Optional[ModelNode]) -> Optional[ModelNode]:
        """
        Parse a node tree iteratively (BFS/stack-based) to avoid Python's
        recursion limit crashing the app on deeply nested or unusual models
        such as c_brith (RARE_CHAR type-64) which can have long child chains.

        Uses self._cache to detect offset cycles (same offset already parsed).
        """
        if abs_off in self._cache:
            return self._cache[abs_off]

        d = self.mdl
        B = self.BASE

        # Work queue: (abs_offset, parent_node)
        work: List[tuple] = [(abs_off, parent)]
        root_node: Optional[ModelNode] = None

        while work:
            cur_off, cur_parent = work.pop()

            # Cycle / already-parsed check
            if cur_off in self._cache:
                node = self._cache[cur_off]
                # Re-attach to parent if needed (can happen in shared-child MDL)
                if cur_parent is not None and node not in cur_parent.children:
                    cur_parent.children.append(node)
                if root_node is None:
                    root_node = node
                continue

            # Bounds check: node header is 80 bytes minimum
            if cur_off + 80 > len(d):
                log.debug(f"_parse_node: offset {cur_off} out of bounds "
                          f"(file {len(d)} bytes)")
                continue

            o = cur_off
            node_type  = _ru16(d, o);    o += 2
            index_num  = _ru16(d, o);    o += 2
            node_num   = _ru16(d, o);    o += 2
            pad        = _ru16(d, o);    o += 2
            root_off   = _ru32(d, o);    o += 4
            parent_off = _ru32(d, o);    o += 4
            px,py,pz   = struct.unpack_from('<fff', d, o);  o += 12
            # Binary format stores orientation as (w, x, y, z) — reorder to internal (x,y,z,w)
            rw_bin,rx,ry,rz = struct.unpack_from('<ffff',d, o);  o += 16
            rw = rw_bin  # w stays as rw; internal format is (x,y,z,w)
            child_arr_off  = _ru32(d, o); o += 4
            child_cnt      = _ru32(d, o); o += 4
            child_cnt2     = _ru32(d, o); o += 4
            ctrl_arr_off   = _ru32(d, o); o += 4
            ctrl_cnt       = _ru32(d, o); o += 4
            ctrl_cnt2      = _ru32(d, o); o += 4
            ctrl_data_off  = _ru32(d, o); o += 4
            ctrl_data_cnt  = _ru32(d, o); o += 4
            ctrl_data_cnt2 = _ru32(d, o); o += 4

            name = (self._names[index_num] if 0 <= index_num < len(self._names)
                    else self._names[node_num] if 0 <= node_num < len(self._names)
                    else f"node_{index_num}")

            node = ModelNode(
                name=name, flags=node_type, index=index_num, number=node_num,
                position=(px, py, pz), rotation=(rx, ry, rz, rw), parent=cur_parent
            )
            self._cache[cur_off] = node

            # Diagnostic: log every node's position and type at DEBUG level
            # This lets us verify bone node positions in the log file.
            import math as _m
            rot_len = _m.sqrt(rx*rx + ry*ry + rz*rz + rw*rw)
            log.debug(
                f"NODE [{name}] flags=0x{node_type:04x}  "
                f"pos=({px:.3f},{py:.3f},{pz:.3f})  "
                f"rot=({rx:.3f},{ry:.3f},{rz:.3f},{rw:.3f})  "
                f"|q|={rot_len:.4f}  "
                f"idx={index_num}  num={node_num}  "
                f"off=0x{cur_off:08x}  "
                f"children={child_cnt}"
            )

            if root_node is None:
                root_node = node

            # Attach to parent
            if cur_parent is not None and node not in cur_parent.children:
                cur_parent.children.append(node)

            # Parse bind-pose controllers
            if ctrl_cnt > 0 and ctrl_arr_off > 0 and ctrl_data_off > 0:
                try:
                    node.controllers = self._parse_controllers(
                        ctrl_arr_off, ctrl_cnt, ctrl_data_off, ctrl_data_cnt)
                except Exception as e:
                    log.debug(f"_parse_node ctrl parse error ({name}): {e}")

            # Parse emitter header (before mesh: KotorBlender order is
            # light → emitter → reference → mesh)
            if node_type & NodeFlags.EMITTER:
                try:
                    self._parse_emitter(node, o)
                except Exception as e:
                    log.debug(f"_parse_node emitter parse error ({name}): {e}")

            # Parse reference node: stores the referenced model name (char[32])
            # and a reattachable flag (uint32).
            # Reference:  PyKotor io_mdl.py _ReferenceHeader (model:char[32], reattachable:uint32)
            #             xoreos  aurora/modelnode.cpp NWN::ModelNodeReference::load()
            if node_type & NodeFlags.REFERENCE:
                try:
                    self._parse_reference(node, o)
                except Exception as e:
                    log.debug(f"_parse_node reference parse error ({name}): {e}")

            # Parse mesh data
            if node_type & NodeFlags.MESH:
                try:
                    self._parse_mesh(node, o)
                except Exception as e:
                    log.debug(f"_parse_node mesh parse error ({name}): {e}")

            # Enqueue children (push in reverse order so first child is popped first)
            safe_child_cnt = min(child_cnt, 512)
            children_to_add = []
            for i in range(safe_child_cnt):
                ptr = B + child_arr_off + i * 4
                if ptr + 4 > len(d):
                    break
                c_off = _ru32(d, ptr)
                if c_off == 0:
                    continue
                child_abs = B + c_off
                if child_abs == cur_off:
                    log.debug(f"_parse_node: self-referential child in {name!r}, skipping")
                    continue
                children_to_add.append((child_abs, node))
            # Push in reverse so iteration order matches original DFS
            for item in reversed(children_to_add):
                work.append(item)

        return root_node

    def _parse_emitter(self, node: ModelNode, off: int):
        """
        Parse the emitter node binary header (immediately after the base node header).

        Binary layout (verified against KotorBlender reader.py lines 252–310):
          +0   dead_space          (float32)  — min distance from emitter to particle birth
          +4   blast_radius        (float32)  — radius for blast-type emitters
          +8   blast_length        (float32)  — length for blast-type emitters
          +12  num_branches        (uint32)   — number of emitter branches (lightning)
          +16  ctrl_point_smoothing (float32) — control-point smoothing for curve emitters
          +20  x_grid              (uint32)   — X subdivision for sheet/grid emitters
          +24  y_grid              (uint32)   — Y subdivision
          +28  spawn_type          (uint32)   — spawning shape (0=point, 1=radius, etc.)
          +32  update_mode         (char[32]) — particle behavior update string
          +64  render_mode         (char[32]) — particle rendering mode ('Normal','Motion Blur',etc.)
          +96  blend_mode          (char[32]) — blend equation ('Lighten','Normal','Punch-Through',etc.)
          +128 texture_name        (char[32]) — emitter texture (diffuse map for particles)
          +160 chunk_name          (char[16]) — aurora engine chunk name (rarely used)
          +176 twosided_tex        (uint32)   — two-sided texture flag
          +180 loop                (uint32)   — loop flag (1 = looping emitter)
          +184 render_order        (uint16)   — draw order (higher = drawn later)
          +186 frame_blending      (uint8)    — per-frame alpha blending flag
          +187 depth_texture_name  (char[32]) — depth-texture/shadow map name
          +219 padding             (uint8)    — 1-byte padding
          +220 flags               (uint32)   — emitter flags (EMITTER_FLAG_* bitmask)
          Total: 224 bytes

        Emitter flags (from KotorBlender types.py EMITTER_FLAG_*):
          0x0001 p2p            – point-to-point emitter
          0x0002 p2p_sel        – p2p selective
          0x0004 affected_wind  – affected by wind system
          0x0008 tinted         – particles tinted by vertex color
          0x0010 bounce         – particles bounce off surfaces
          0x0020 random         – random particle birth
          0x0040 inherit        – inherit parent node velocity
          0x0080 inheritvel     – inherit parent velocity magnitude
          0x0100 inherit_local  – inherit local-space transform
          0x0200 splat          – splat-type emitter
          0x0400 inherit_part   – inherited particles
          0x0800 depth_texture  – uses depth texture
        """
        d = self.mdl
        o = off
        try:
            if o + 224 > len(d):
                return
            dead_space  = struct.unpack_from('<f',  d, o)[0]; o += 4
            blast_r     = struct.unpack_from('<f',  d, o)[0]; o += 4
            blast_l     = struct.unpack_from('<f',  d, o)[0]; o += 4
            num_branches= _ru32(d, o);                         o += 4
            ctrl_smooth = struct.unpack_from('<f',  d, o)[0]; o += 4
            x_grid      = _ru32(d, o);                         o += 4
            y_grid      = _ru32(d, o);                         o += 4
            spawn_type  = _ru32(d, o);                         o += 4
            update_mode = _rstrip(d[o:o+32]).lower();          o += 32
            render_mode = _rstrip(d[o:o+32]).lower();          o += 32
            blend_mode  = _rstrip(d[o:o+32]).lower();          o += 32
            texture     = _rstrip(d[o:o+32]).lower();          o += 32
            chunk_name  = _rstrip(d[o:o+16]).lower();          o += 16
            twosided    = _ru32(d, o);                         o += 4
            loop        = _ru32(d, o);                         o += 4
            render_order= _ru16(d, o);                         o += 2
            frame_blend = struct.unpack_from('B', d, o)[0];   o += 1
            depth_tex   = _rstrip(d[o:o+32]).lower();          o += 32
            o += 1   # padding
            flags       = _ru32(d, o);                         o += 4

            # Store in emitter_params dict (used by ASCII writer)
            ep = node.emitter_params
            ep['deadspace']        = dead_space
            ep['blastradius']      = blast_r
            ep['blastlength']      = blast_l
            ep['numbranches']      = num_branches
            ep['controlptsmoothing'] = ctrl_smooth
            ep['xgrid']            = x_grid
            ep['ygrid']            = y_grid
            ep['spawntype']        = spawn_type
            if update_mode:  ep['update']  = update_mode
            if render_mode:  ep['emitter_render'] = render_mode
            if blend_mode:   ep['blend']   = blend_mode
            if texture:      ep['texture'] = texture
            if chunk_name:   ep['chunkname'] = chunk_name
            ep['twosidedtex']  = int(twosided)
            ep['loop']         = int(loop)
            ep['renderorder']  = render_order
            ep['frameblending']= int(frame_blend)
            if depth_tex:    ep['depth_texture_name'] = depth_tex
            ep['flags']        = flags
            # Decode individual flags for convenient access
            ep['p2p']            = int(bool(flags & 0x0001))
            ep['p2p_sel']        = int(bool(flags & 0x0002))
            ep['affected_wind']  = int(bool(flags & 0x0004))
            ep['tinted']         = int(bool(flags & 0x0008))
            ep['bounce']         = int(bool(flags & 0x0010))
            ep['random']         = int(bool(flags & 0x0020))
            ep['inherit']        = int(bool(flags & 0x0040))
            ep['inheritvel']     = int(bool(flags & 0x0080))
            ep['inherit_local']  = int(bool(flags & 0x0100))
            ep['splat']          = int(bool(flags & 0x0200))
            ep['inherit_part']   = int(bool(flags & 0x0400))
            ep['depth_texture']  = int(bool(flags & 0x0800))

            log.debug(
                f"  EMITTER [{node.name}]: update={update_mode!r} render={render_mode!r} "
                f"blend={blend_mode!r} tex={texture!r} xgrid={x_grid} ygrid={y_grid} "
                f"flags=0x{flags:04x}"
            )
        except Exception as e:
            log.debug(f"Emitter parse error on {node.name}: {e}")

    def _parse_reference(self, node: ModelNode, off: int):
        """
        Parse the binary reference node header.

        Binary layout (PyKotor io_mdl.py _ReferenceHeader):
          +0   model         (char[32])  — null-terminated resref of the referenced model
          +32  reattachable  (uint32)    — 1 = reattachable (can be detached/reattached)

        Reference nodes are used for:
          - Placeable objects that reference a separate model (e.g., gi_datapad01)
          - Dynamic props in area models (lights/effects that are spawned at runtime)
          - Head/body hooks that reference specific model resrefs

        The parsed data is stored in node.emitter_params (repurposed as a generic
        node-extra-data dict, since reference nodes have no mesh geometry).

        Reference: PyKotor io_mdl.py _ReferenceHeader
                   xoreos  src/aurora/modelnode.cpp NWN::ModelNodeReference::load()
        """
        d = self.mdl
        o = off
        if o + 36 > len(d):
            return
        try:
            raw_name = d[o:o+32]
            # Null-terminate and strip
            null_pos = raw_name.find(b'\x00')
            if null_pos >= 0:
                raw_name = raw_name[:null_pos]
            ref_model = raw_name.decode('ascii', errors='replace').strip().lower()
            reattachable = struct.unpack_from('<I', d, o + 32)[0]
            node.emitter_params['ref_model']     = ref_model
            node.emitter_params['reattachable']  = bool(reattachable)
            log.debug(
                f"  REFERENCE [{node.name}]: ref_model={ref_model!r} "
                f"reattachable={bool(reattachable)}"
            )
        except Exception as e:
            log.debug(f"Reference parse error on {node.name}: {e}")

    def _parse_mesh(self, node: ModelNode, off: int):
        d   = self.mdl
        mdx = self.mdx
        B   = self.BASE
        o   = off

        # ── Mesh header (verified against N_sithpraet.mdl K1 binary) ───────
        # +0   funcptr1 (4)
        # +4   funcptr2 (4)
        # +8   faces array offset (4)
        # +12  faces array count (4)
        # +16  faces array count2 (4)
        # +20  bounding_box_min (12)
        # +32  bounding_box_max (12)
        # +44  radius (4)
        # +48  average_position (12)
        # +60  diffuse color (12)
        # +72  ambient color (12)
        # +84  transparency_hint (4)
        # +88  texture name (32)
        # +120 lightmap name (32)
        # +152 unknown × 6 (24 bytes)
        # +176 vertex_indices_count array (4+4+4=12)
        # +188 vertex_offsets array (4+4+4=12)
        # +200 inv_counter array (4+4+4=12)
        # +212 {-1, -1, 0} unknown (12)
        # +224 saber unknowns (8)
        # +232 unknown (4)
        # +236 4 floats (16)
        # +252 mdx_data_size (4)
        # +256 mdx_data_bitmap (4)
        # +260 mdx offsets ×11 (44): vertex, normal, vc, t1, lm, t2, t3, bmp, unk1, unk2, unk3
        # +304 vert_count (uint16)
        # +306 tex_count (uint16)
        # +308 has_lightmap (uint8)
        # +309 rotate_texture (uint8)
        # +310 background_geometry (uint8)
        # +311 has_shadow (uint8)
        # +312 beaming (uint8)
        # +313 render (uint8)
        # +314 unknown (2)
        # +316 total_area (float)
        # +320 unknown (4)
        # [K2 only: +324 unknown (4), +328 unknown (4)]
        # +324 mdx_data_offset  [K2: +332]
        # +328 vertices_offset  [K2: +336]

        o += 8   # skip fp1, fp2

        faces_off   = _ru32(d,o); o+=4
        faces_cnt   = _ru32(d,o); o+=4
        o           += 4  # faces_cnt2

        # bounding box
        bx1,by1,bz1 = struct.unpack_from('<fff',d,o); o+=12
        bx2,by2,bz2 = struct.unpack_from('<fff',d,o); o+=12
        o += 4   # radius
        avg_px, avg_py, avg_pz = struct.unpack_from('<fff',d,o); o+=12  # average position (AveragePoint)

        dr,dg,db = struct.unpack_from('<fff',d,o); o+=12
        ar,ag,ab = struct.unpack_from('<fff',d,o); o+=12
        transp   = _ru32(d,o); o+=4
        tex_name = _rstrip(d[o:o+32]).lower(); o+=32   # bitmap  (slot 0) — primary texture
        lm_name  = _rstrip(d[o:o+32]).lower(); o+=32   # bitmap2 (slot 1) — lightmap or secondary texture
        # bitmap3 and bitmap4: two extra 12-byte texture name slots (KotorBlender verified).
        # Used for multi-layer textures in area/tile models.  Not common in character models.
        # Previously skipped as "6 unknown uint32s" (=24 bytes total), which is correct
        # since 12+12=24 bytes.  Now we read them explicitly to support multi-layer textures.
        bm3_name = _rstrip(d[o:o+12]).lower(); o+=12   # bitmap3 (slot 2) — tertiary texture
        bm4_name = _rstrip(d[o:o+12]).lower(); o+=12   # bitmap4 (slot 3) — quaternary texture

        o += 12  # vic array (off/cnt/cnt2)
        o += 12  # vo array  (off/cnt/cnt2)
        o += 12  # inv array (off/cnt/cnt2)
        o += 12  # {-1, -1, 0}
        o +=  8  # saber vals (8 bytes)
        # UV animation fields (KotorBlender: animate_uv + uv_dir_x/y + uv_jitter + uv_jitter_speed)
        animate_uv   = _ru32(d,o); o+=4    # animate_uv flag (uint32)
        uv_dir_x     = _rf32(d,o); o+=4    # UV scroll direction X
        uv_dir_y     = _rf32(d,o); o+=4    # UV scroll direction Y
        uv_jitter    = _rf32(d,o); o+=4    # UV jitter magnitude
        uv_jitter_spd= _rf32(d,o); o+=4    # UV jitter speed
        # (total 20 bytes consumed here — same as previous o+=4 + o+=16)

        mdx_data_size   = _ru32(d,o); o+=4
        mdx_data_bitmap = _ru32(d,o); o+=4

        # 11 MDX channel offsets (0xFFFFFFFF = absent) — 11 × 4 = 44 bytes
        # Slot ordering confirmed against KotorBlender reader.py (off_mdx_verts…off_mdx_tan_space4)
        # and xoreos model_kotor.cpp offNormals / offUV[0..3] layout.
        # See also PyKotor io_mdl.py _TrimeshHeader fields mdx_vertex_offset … unknown3..8.
        #
        #  Slot  Field          Bitmap bit  Bytes/vertex  Description
        #  ─────────────────────────────────────────────────────────────────────
        #   0    mdx_v_off      0x0001      12 (3×f32)    Vertex XYZ positions
        #   1    mdx_n_off      0x0020      12 (3×f32)    Vertex normals (Xbox: 4 bytes compressed)
        #   2    mdx_vc_off     0x0040       4 (RGBA u8)  Vertex colors (MDX_FLAG_COLOR)
        #   3    mdx_t1_off     0x0002       8 (2×f32)    UV set 1 / Texture0  ("tverts" in ASCII)
        #   4    mdx_lm_off     0x0004       8 (2×f32)    UV set 2 / Texture1 / lightmap ("tverts1")
        #   5    mdx_t2_off     0x0008       8 (2×f32)    UV set 3 / Texture2  (rare; extra tiles)
        #   6    mdx_t3_off     0x0010       8 (2×f32)    UV set 4 / Texture3  (very rare)
        #   7    mdx_tan1_off   0x0080      36 (9×f32)    Tangent-space for Texture0 (T/B/N vectors)
        #   8    mdx_tan2_off   0x0100      36 (9×f32)    Tangent-space for Texture1 (no vanilla usage)
        #   9    mdx_tan3_off   0x0200      36 (9×f32)    Tangent-space for Texture2 (no vanilla usage)
        #  10    mdx_tan4_off   0x0400      36 (9×f32)    Tangent-space for Texture3 (no vanilla usage)
        #
        # NOTE: slot 7 was previously mislabelled "mdx_bmp_off" (bump-map channel).
        #       KotorBlender names it off_mdx_tan_space1; it is the tangent-space data
        #       for Texture0 needed for normal/bump mapping (36 bytes = T + B + N vectors).
        #       Slots 8-10 ("mdx_unk1/2/3") are tan-space slots for textures 1-3;
        #       no vanilla K1/K2 model uses them.
        mdx_v_off    = _ru32(d,o); o+=4   # slot 0: vertex XYZ
        mdx_n_off    = _ru32(d,o); o+=4   # slot 1: normals
        mdx_vc_off   = _ru32(d,o); o+=4   # slot 2: vertex colors (MDX_FLAG_COLOR 0x40)
        mdx_t1_off   = _ru32(d,o); o+=4   # slot 3: UV set 1 (Texture0)
        mdx_lm_off   = _ru32(d,o); o+=4   # slot 4: UV set 2 / lightmap (Texture1)
        mdx_t2_off   = _ru32(d,o); o+=4   # slot 5: UV set 3 (Texture2)
        mdx_t3_off   = _ru32(d,o); o+=4   # slot 6: UV set 4 (Texture3)
        mdx_tan1_off = _ru32(d,o); o+=4   # slot 7: tangent-space Tex0 (0x0080, 36 bytes)
        mdx_tan2_off = _ru32(d,o); o+=4   # slot 8: tangent-space Tex1 (0x0100, no vanilla)
        mdx_tan3_off = _ru32(d,o); o+=4   # slot 9: tangent-space Tex2 (0x0200, no vanilla)
        mdx_tan4_off = _ru32(d,o); o+=4   # slot10: tangent-space Tex3 (0x0400, no vanilla)

        vert_cnt   = _ru16(d,o); o+=2
        tex_cnt    = _ru16(d,o); o+=2
        has_lm     = struct.unpack_from('B',d,o)[0]; o+=1
        rot_tex    = struct.unpack_from('B',d,o)[0]; o+=1
        bg_geo     = struct.unpack_from('B',d,o)[0]; o+=1
        has_shadow = struct.unpack_from('B',d,o)[0]; o+=1
        beaming    = struct.unpack_from('B',d,o)[0]; o+=1
        has_render = struct.unpack_from('B',d,o)[0]; o+=1

        # ── K2/TSL extra mesh header fields (verified against KotorBlender reader.py) ──
        # In KotOR 2 (TSL) the 6-flag sequence (has_lm, rot_tex, bg_geo, shadow,
        # beaming, render) is immediately followed by 8 extra bytes for dirt/hologram:
        #   +0  dirt_enabled     (uint8)
        #   +1  padding          (uint8)
        #   +2  dirt_texture     (uint16)
        #   +4  dirt_coord_space (uint16)
        #   +6  hide_in_holograms(uint8)
        #   +7  padding          (uint8)
        # These 8 bytes come BEFORE the standard skip(2)+total_area+skip(4) section.
        # PREVIOUS BUG: these 8 bytes were added AFTER the padding/area section,
        # shifting mdx_data_off and verts_off by 8 bytes for ALL K2 models.
        # Reference: Kotor.NET MDLBinaryStructure.cs TrimeshHeader TSLUnknown1/2 comment.
        k2_dirt_enabled = False
        k2_dirt_texture = 0
        k2_dirt_coord_space = 0
        k2_hide_in_holograms = False
        if self.model.game_version == GameVersion.K2:
            k2_dirt_enabled      = bool(struct.unpack_from('B',d,o)[0]); o+=1
            o += 1  # padding byte
            k2_dirt_texture      = struct.unpack_from('<H',d,o)[0]; o+=2
            k2_dirt_coord_space  = struct.unpack_from('<H',d,o)[0]; o+=2
            k2_hide_in_holograms = bool(struct.unpack_from('B',d,o)[0]); o+=1
            o += 1  # padding byte

        o += 2   # 2 unknown/padding bytes
        o += 4   # total_area (float)
        o += 4   # unknown uint32 (padding)

        mdx_data_off = _ru32(d,o); o+=4
        verts_off    = _ru32(d,o); o+=4

        # ── K2 auto-detect fallback: validate mdx/verts offsets ──────────────
        # If game_version was guessed as K1 (unknown fp1) but mdx_data_off or
        # verts_off are implausible, try the K2 variant (extra 8-byte skip).
        # Plausibility: offset must be > 0 and within the MDX data size or be
        # 0xFFFFFFFF (absent).  A clearly out-of-range value (> 10 MB) when the
        # file is smaller strongly suggests the wrong variant was chosen.
        _mdx_size = len(self.mdx) if self.mdx else 0
        _mdl_size = len(d)
        def _off_looks_bad(off: int, data_size: int) -> bool:
            """Return True if 'off' looks like a mis-parsed offset."""
            if off == 0xFFFFFFFF or off == 0:
                return False   # absent/zero is valid
            return off > max(data_size, _mdl_size) + 4096  # allow small over-run
        if (self.model.game_version == GameVersion.K1
                and (_off_looks_bad(mdx_data_off, _mdx_size)
                     or _off_looks_bad(verts_off, _mdx_size))):
            # Re-try with K2 8-byte skip: rewind o back 8 bytes, skip 8, re-read
            o_retry = o - 8        # step back past the two uint32s we just read
            o_retry += 8           # apply the K2 dirt-block skip
            mdx_data_off_k2 = _ru32(d, o_retry);     o_retry += 4
            verts_off_k2    = _ru32(d, o_retry)
            if (not _off_looks_bad(mdx_data_off_k2, _mdx_size)
                    and not _off_looks_bad(verts_off_k2, _mdx_size)):
                log.debug(
                    f"[{self.model.name}] K2 auto-detect: K1 offsets bad "
                    f"(mdx=0x{mdx_data_off:08x} verts=0x{verts_off:08x}); "
                    f"switching to K2 offsets "
                    f"(mdx=0x{mdx_data_off_k2:08x} verts=0x{verts_off_k2:08x})"
                )
                self.model.game_version = GameVersion.K2
                mdx_data_off = mdx_data_off_k2
                verts_off    = verts_off_k2
                o = o_retry + 4   # advance past verts_off_k2
                # Also go back and re-read the K2 dirt/hologram fields now that
                # we know the model is K2. Rewind to just after the 6 flag bytes,
                # which are at (o_retry - 8 - 2 - 4 - 4).
                dirt_base = o_retry - 8 - 10  # 8=dirty skip, 10=padding(2)+area(4)+skip(4)
                if dirt_base >= 0 and dirt_base + 8 <= len(d):
                    k2_dirt_enabled      = bool(struct.unpack_from('B',d,dirt_base)[0])
                    # byte 1: padding — skip
                    k2_dirt_texture      = struct.unpack_from('<H',d,dirt_base+2)[0]
                    k2_dirt_coord_space  = struct.unpack_from('<H',d,dirt_base+4)[0]
                    k2_hide_in_holograms = bool(struct.unpack_from('B',d,dirt_base+6)[0])

        # ── Store mesh properties ────────────────────────────────────────────
        node.texture      = tex_name
        node.lightmap     = lm_name
        node.diffuse      = (dr,dg,db)
        node.ambient      = (ar,ag,ab)
        node.has_shadow      = bool(has_shadow)
        node.render          = bool(has_render)
        node.has_lightmap    = bool(has_lm)
        node.beaming         = bool(beaming)
        node.rotate_texture  = bool(rot_tex)
        node.transparency_hint = transp
        node.bb_min = (bx1,by1,bz1)
        node.bb_max = (bx2,by2,bz2)
        # Average position (AveragePoint): centroid of all face vertices in mesh-local space.
        # Kotor.NET TrimeshHeader.AveragePoint; xoreos _averagePoint.
        # Used for accurate transparent-surface depth sorting.
        node.mesh_average_point = (avg_px, avg_py, avg_pz)
        # K2/TSL dirt and hologram fields (parsed above; 0/False for K1 models)
        node.dirt_enabled       = k2_dirt_enabled
        node.dirt_texture       = k2_dirt_texture
        node.dirt_coord_space   = k2_dirt_coord_space
        node.hide_in_holograms  = k2_hide_in_holograms
        # UV animation parameters (from mesh header animate_uv + direction/jitter fields)
        node.animate_uv    = bool(animate_uv)
        node.uv_dir_x      = float(uv_dir_x)
        node.uv_dir_y      = float(uv_dir_y)
        node.uv_jitter     = float(uv_jitter)
        node.uv_jitter_speed = float(uv_jitter_spd)

        # ── Multi-texture: build texture_names list ──────────────────────────
        # tex_cnt tells how many material zones this mesh uses.
        # Slot 0 = bitmap  (primary texture / diffuse)
        # Slot 1 = bitmap2 (lightmap when has_lightmap=1, OR secondary texture when has_lightmap=0)
        # Slot 2 = bitmap3 (tertiary texture — used in area models)
        # Slot 3 = bitmap4 (quaternary texture)
        # face_mats[i] is the 0-based slot index for face i.
        node.tex_count = max(1, int(tex_cnt))
        node.texture_names = [tex_name]
        if node.tex_count > 1:
            # bitmap2: real second material texture when !has_lightmap, else lightmap
            secondary = lm_name if (lm_name and not bool(has_lm)) else ''
            node.texture_names.append(secondary)
        if node.tex_count > 2:
            node.texture_names.append(bm3_name)
        if node.tex_count > 3:
            node.texture_names.append(bm4_name)
        # Pad to tex_count slots with empty strings
        while len(node.texture_names) < node.tex_count:
            node.texture_names.append('')
        log.debug(f"  {node.name}: tex_cnt={node.tex_count} "
                  f"texture_names={node.texture_names}")

        if vert_cnt == 0 or vert_cnt > 65535:
            log.debug(f"  {node.name}: vert_cnt={vert_cnt} (skipping geometry)")
            return

        # ── Read vertex positions ────────────────────────────────────────────
        # Primary: from MDX (vertex channel at mdx_v_off within stride)
        # Fallback: from MDL vertex array
        verts_loaded = False

        # CRITICAL FIX: mdx_data_off == 0 is VALID – it means data starts at the
        # very first byte of the MDX buffer.  The old condition 'mdx_data_off > 0'
        # incorrectly skipped models whose MDX data starts at offset 0, causing
        # missing UVs, normals and vertex positions for a large class of prop and
        # placeable models (plc_*, m*_prop*, gi_*, etc.).
        # Overflow guard: ensure mdx_data_off + vert_cnt * mdx_data_size
        # doesn't overflow on corrupt/malformed MDL data.
        # Validation mirrors UE5 SkeletalMesh.cpp CalculateInvRefMatrices() where
        # buffer bounds are validated before any pointer arithmetic.  Failures are
        # logged with actionable diagnostics so users can identify corrupt assets.
        _mdx_stride_bytes = int(mdx_data_size) * int(vert_cnt)
        _mdx_valid = (mdx_data_size > 0
                      and mdx_data_size < 512  # sanity: stride can't be >512 bytes
                      and _mdx_stride_bytes <= 64 * 1024 * 1024  # max 64 MB per mesh
                      and mdx_data_off + _mdx_stride_bytes <= len(mdx)
                      and len(mdx) > 0)

        if not _mdx_valid and mdx_data_size > 0 and vert_cnt > 0:
            # Emit structured diagnostic so the user knows which node is affected
            # and whether this is a corrupt asset vs. a legitimate edge-case.
            if mdx_data_size >= 512:
                log.warning(
                    f"{node.name}: MDX stride {mdx_data_size} B exceeds "
                    f"512 B sanity limit – likely corrupt MDL (max allowed: 511 B). "
                    f"Falling back to MDL vertex array."
                )
            elif _mdx_stride_bytes > 64 * 1024 * 1024:
                log.warning(
                    f"{node.name}: MDX total stride bytes "
                    f"{_mdx_stride_bytes // (1024*1024)} MB "
                    f"({vert_cnt} verts × {mdx_data_size} B) exceeds 64 MB cap. "
                    f"Falling back to MDL vertex array."
                )
            elif mdx_data_off + _mdx_stride_bytes > len(mdx):
                log.warning(
                    f"{node.name}: MDX data would read past buffer end "
                    f"(off={mdx_data_off}, total={_mdx_stride_bytes}, "
                    f"mdx_len={len(mdx)}). Falling back to MDL vertex array."
                )

        if (_mdx_valid and mdx_v_off != 0xFFFFFFFF):
            stride = mdx_data_size
            for i in range(vert_cnt):
                base = mdx_data_off + i * stride
                if base + mdx_v_off + 12 > len(mdx): break
                node.vertices.append(struct.unpack_from('<fff', mdx, base + mdx_v_off))
            verts_loaded = len(node.vertices) == vert_cnt

        if not verts_loaded and verts_off > 0:
            # Fall back to vertex array in MDL
            va = B + verts_off
            for i in range(vert_cnt):
                p = va + i * 12
                if p + 12 > len(d): break
                node.vertices.append(struct.unpack_from('<fff', d, p))

        # ── Read per-vertex MDX channels (normals, UVs) ─────────────────────
        # Verified MDX bitmap flag values (deadlystream.com MDL/MDX Technical Details,
        # MagnusII research, confirmed empirically against full K1+K2 model set):
        #
        #   MDX Bitmap Bit → Data present in stride:
        #   0x0001 (bit   1) – Vertex XYZ coordinates (12 bytes: 3 × float)
        #   0x0002 (bit   2) – Texture0 UV coords, 'tverts' in ASCII  (8 bytes: 2 × float)
        #   0x0004 (bit   4) – Texture1 UV coords, 'tverts1' in ASCII (8 bytes: 2 × float)
        #                        Used as lightmap UVs when has_lightmap=1.
        #   0x0008 (bit   8) – Texture2 UV (unused in vanilla KotOR)
        #   0x0010 (bit  16) – Texture3 UV (unused in vanilla KotOR)
        #   0x0020 (bit  32) – Vertex Normals (12 bytes: 3 × float)
        #                        On Xbox: compressed as uint32 (11-11-10 bit packed)
        #   0x0040 (bit  64) – Vertex Colors (4 bytes: R,G,B,A packed uint8×4)
        #                        KotorBlender: MDX_FLAG_COLOR = 0x0040, off_mdx_colors
        #                        Rarely used in KotOR; room-tile models may use them.
        #                        Source: KotorBlender types.py line 109.
        #   0x0080 (bit 128) – Tangent Space Tex0 (36 bytes: 9 × float = T,B,N vectors)
        #                        Required for normal/bump mapping on Texture0.
        #   0x0100 (bit 256) – Tangent Space Tex1 (36 bytes: 9 × float) [NO vanilla usage]
        #   0x0200 (bit 512) – Tangent Space Tex2 (36 bytes: 9 × float) [NO vanilla usage]
        #   0x0400 (bit1024) – Tangent Space Tex3 (36 bytes: 9 × float) [NO vanilla usage]
        #
        # RESEARCH NOTE (v13): Bits 0x100–0x400 are confirmed as per-texture tangent
        # spaces by deadlystream.com MagnusII theory and KotorBlender types.py constants
        # MDX_FLAG_TANGENT2=0x100, MDX_FLAG_TANGENT3=0x200, MDX_FLAG_TANGENT4=0x400.
        # No vanilla K1/K2 models use them (only Tex0 tangent space 0x0080 exists
        # in game data). They would enable bump-mapping on texture slots 1-3
        # independently. Left unimplemented in stride reader: if present, each adds
        # 36 bytes to the stride at offset slots 9/10/11 in the MDL offset array.
        #
        # MDL header offset array (11 slots × 4 bytes = 44 bytes, starting at +260):
        #   Slot 0 (mdx_v_off):    Vertex XYZ offset    (bitmap bit 0x01)
        #   Slot 1 (mdx_n_off):    Vertex Normal offset  (bitmap bit 0x20)
        #   Slot 2 (mdx_vc_off):   Vertex Color offset   (bitmap bit 0x40 = MDX_FLAG_COLOR)
        #                            4 bytes per vertex: RGBA packed uint8 × 4
        #                            Confirmed: KotorBlender off_mdx_colors, types.py MDX_FLAG_COLOR
        #   Slot 3 (mdx_t1_off):   Texture0 UV offset    (bitmap bit 0x02)
        #   Slot 4 (mdx_lm_off):   Texture1/LM UV offset (bitmap bit 0x04)
        #   Slot 5 (mdx_t2_off):   Texture2 UV offset    (bitmap bit 0x08)
        #   Slot 6 (mdx_t3_off):   Texture3 UV offset    (bitmap bit 0x10)
        #   Slot 7 (mdx_tan1_off): Tangent-space Tex0    (bitmap bit 0x80, 36 bytes)
        #                            KotorBlender: off_mdx_tan_space1; required for bumpmap on Tex0
        #   Slot 8 (mdx_tan2_off): Tangent-space Tex1    (bitmap bit 0x100, no vanilla usage)
        #   Slot 9 (mdx_tan3_off): Tangent-space Tex2    (bitmap bit 0x200, no vanilla usage)
        #   Slot10 (mdx_tan4_off): Tangent-space Tex3    (bitmap bit 0x400, no vanilla usage)
        #
        # IMPORTANT: The bitmap bits and the slot indices are NOT the same ordering.
        # A typical vanilla model has bitmap=0x23 (bits 0x01+0x02+0x20):
        #   → vertex positions, Texture0 UVs, and normals present.
        # The 'offset-valid' check (_t1_ok etc.) is the definitive gate for reading;
        # the bitmap check is a secondary hint used only for diagnostics.
        _bm_has_n  = bool(mdx_data_bitmap & 0x020)  # bit 32: vertex normals
        _bm_has_t1 = bool(mdx_data_bitmap & 0x002)  # bit  2: primary UV (Texture0)
        _bm_has_lm = bool(mdx_data_bitmap & 0x004)  # bit  4: secondary UV (Texture1/lightmap)
        _bm_has_t2 = bool(mdx_data_bitmap & 0x008)  # bit  8: Texture2 UV
        _bm_has_t3 = bool(mdx_data_bitmap & 0x010)  # bit 16: Texture3 UV
        _bm_has_vc = bool(mdx_data_bitmap & 0x040)  # bit 64: vertex colors (MDX_FLAG_COLOR)

        # Determine which channels are actually readable:
        # Channel is valid if offset != ABSENT and offset is within the stride.
        # For UV2/UV3 channels: additionally require that the bitmap bit is set
        # OR the offset is meaningfully different from the primary UV offset.
        # This prevents false-positive UV channel reads when the MDX header has
        # stale/garbage offset values for unused extra-UV slots (seen in some
        # K2 area models where mdx_t2_off == mdx_t1_off despite tex_count=1).
        _ABSENT = 0xFFFFFFFF
        # Xbox normals are 4 bytes (compressed uint32), PC normals are 12 bytes (3×float)
        _n_bytes = 4 if self._is_xbox else 12
        _n_ok  = (mdx_n_off  != _ABSENT and mdx_n_off  + _n_bytes <= mdx_data_size)
        _t1_ok = (mdx_t1_off != _ABSENT and mdx_t1_off +  8 <= mdx_data_size)
        _lm_ok = (mdx_lm_off != _ABSENT and mdx_lm_off +  8 <= mdx_data_size)
        # UV2 / UV3: only read if bitmap confirms presence OR tex_count > 2
        _t2_raw_ok = (mdx_t2_off != _ABSENT and mdx_t2_off +  8 <= mdx_data_size)
        _t3_raw_ok = (mdx_t3_off != _ABSENT and mdx_t3_off +  8 <= mdx_data_size)
        # For UV2/UV3, also require that the offset differs from UV1 (not aliased)
        # and the bitmap bit is set or we have 3+ material textures on this node.
        _has_multi_tex = (node.tex_count >= 3)
        _t2_ok = _t2_raw_ok and (_bm_has_t2 or _has_multi_tex) and (mdx_t2_off != mdx_t1_off)
        _t3_ok = _t3_raw_ok and (_bm_has_t3 or node.tex_count >= 4) and (mdx_t3_off != mdx_t1_off)

        # If bitmap says channel is absent but offset says it's present, trust
        # the offset unless it's clearly out of range. If bitmap bit IS set but
        # offset is 0xFFFFFFFF (absent), the channel is definitely not readable.
        # Log a diagnostic warning for any bitmap/offset mismatch.
        if _bm_has_n != _n_ok and mdx_data_size > 0:
            log.debug(f"  {node.name}: normal bitmap={_bm_has_n} vs offset_valid={_n_ok} "
                      f"(n_off={mdx_n_off:#x} stride={mdx_data_size})")
        if _bm_has_t1 != _t1_ok and mdx_data_size > 0:
            log.debug(f"  {node.name}: UV1 bitmap={_bm_has_t1} vs offset_valid={_t1_ok} "
                      f"(t1_off={mdx_t1_off:#x} stride={mdx_data_size})")
        if _t2_raw_ok and not _t2_ok and mdx_data_size > 0:
            log.debug(f"  {node.name}: UV2 offset valid but skipping "
                      f"(bitmap={_bm_has_t2} multi_tex={_has_multi_tex} "
                      f"t2_off={mdx_t2_off:#x} t1_off={mdx_t1_off:#x})")
        if _t3_raw_ok and not _t3_ok and mdx_data_size > 0:
            log.debug(f"  {node.name}: UV3 offset valid but skipping "
                      f"(bitmap={_bm_has_t3} tex_cnt={node.tex_count} "
                      f"t3_off={mdx_t3_off:#x} t1_off={mdx_t1_off:#x})")

        if _mdx_valid:
            stride = mdx_data_size
            # Pre-flight check: read ALL per-vertex channels in one loop to ensure
            # that normals/UVs/LM-UVs always have the same count as vertices.
            # Previously, individual bounds checks could cause partial reads where
            # e.g. the first 10 vertices have normals but the rest don't, leaving
            # a mismatched array that causes indexing errors in the renderer.
            _norms_tmp  = []
            _uvs_tmp    = []
            _uvs_lm_tmp = []
            _uvs_2_tmp  = []
            _uvs_3_tmp  = []

            for i in range(vert_cnt):
                base = mdx_data_off + i * stride

                # Normals
                # PC:   12 bytes (3 × float32)
                # Xbox: 4 bytes (uint32, 11-11-10 bit packed — same packing as
                #       compressed quaternions).  Decompression formula from
                #       KotorBlender reader.py decompress_vector_xbox():
                #         x bits  0-10 (11 bits): val/1023.0        if <1024
                #                                  (val-2047)/1023.0 otherwise
                #         y bits 11-21 (11 bits): same scale
                #         z bits 22-31 (10 bits): val/511.0 if <512 else (val-1023)/511.0
                #       Source: KotorBlender reader.py lines 883-900.
                if _n_ok:
                    if self._is_xbox:
                        # Xbox: 4-byte compressed normal (uint32)
                        if base + mdx_n_off + 4 <= len(mdx):
                            comp = struct.unpack_from('<I', mdx, base + mdx_n_off)[0]
                            # Decompress 11-11-10 bit packed normal
                            tmp = comp & 0x7FF
                            nx = tmp / 1023.0 if tmp < 1024 else (tmp - 2047) / 1023.0
                            tmp = (comp >> 11) & 0x7FF
                            ny = tmp / 1023.0 if tmp < 1024 else (tmp - 2047) / 1023.0
                            tmp = comp >> 22
                            nz = tmp / 511.0 if tmp < 512 else (tmp - 1023) / 511.0
                            _norms_tmp.append((nx, ny, nz))
                        else:
                            _norms_tmp.append((0.0, 0.0, 1.0))
                    elif base + mdx_n_off + 12 <= len(mdx):
                        nx, ny, nz = struct.unpack_from('<fff', mdx, base + mdx_n_off)
                        # Sanity-check: reject degenerate normals (all-zero or NaN)
                        if math.isfinite(nx) and math.isfinite(ny) and math.isfinite(nz):
                            _norms_tmp.append((nx, ny, nz))
                        else:
                            _norms_tmp.append((0.0, 0.0, 1.0))  # default up normal
                    else:
                        _norms_tmp.append((0.0, 0.0, 1.0))  # bounds miss

                # UV set 1 (8 bytes: 2×float)
                if _t1_ok and base + mdx_t1_off + 8 <= len(mdx):
                    u, v = struct.unpack_from('<ff', mdx, base + mdx_t1_off)
                    # Sanity-check: finite UV values
                    if math.isfinite(u) and math.isfinite(v):
                        _uvs_tmp.append((u, v))
                    else:
                        _uvs_tmp.append((0.0, 0.0))
                elif _t1_ok:
                    _uvs_tmp.append((0.0, 0.0))  # bounds miss

                # Lightmap UV (8 bytes: 2×float)
                if _lm_ok and base + mdx_lm_off + 8 <= len(mdx):
                    u, v = struct.unpack_from('<ff', mdx, base + mdx_lm_off)
                    if math.isfinite(u) and math.isfinite(v):
                        _uvs_lm_tmp.append((u, v))
                    else:
                        _uvs_lm_tmp.append((0.0, 0.0))
                elif _lm_ok:
                    _uvs_lm_tmp.append((0.0, 0.0))  # bounds miss

                # UV set 2 (8 bytes: 2×float) — Texture2 channel
                if _t2_ok and base + mdx_t2_off + 8 <= len(mdx):
                    u, v = struct.unpack_from('<ff', mdx, base + mdx_t2_off)
                    if math.isfinite(u) and math.isfinite(v):
                        _uvs_2_tmp.append((u, v))
                    else:
                        _uvs_2_tmp.append((0.0, 0.0))
                elif _t2_ok:
                    _uvs_2_tmp.append((0.0, 0.0))

                # UV set 3 (8 bytes: 2×float) — Texture3 channel
                if _t3_ok and base + mdx_t3_off + 8 <= len(mdx):
                    u, v = struct.unpack_from('<ff', mdx, base + mdx_t3_off)
                    if math.isfinite(u) and math.isfinite(v):
                        _uvs_3_tmp.append((u, v))
                    else:
                        _uvs_3_tmp.append((0.0, 0.0))
                elif _t3_ok:
                    _uvs_3_tmp.append((0.0, 0.0))

            # Only store channel data if we got a full set (count == vert_cnt).
            # Partial arrays cause renderer IndexErrors; it's safer to discard them.
            if len(_norms_tmp) == vert_cnt:
                node.normals = _norms_tmp
            elif _norms_tmp:
                log.warning(f"  {node.name}: normal count {len(_norms_tmp)} != vert_cnt "
                            f"{vert_cnt} — discarding partial normals")

            if len(_uvs_tmp) == vert_cnt:
                node.uvs = _uvs_tmp
            elif _uvs_tmp:
                log.warning(f"  {node.name}: UV count {len(_uvs_tmp)} != vert_cnt "
                            f"{vert_cnt} — discarding partial UVs")

            if len(_uvs_lm_tmp) == vert_cnt:
                node.uvs_lm = _uvs_lm_tmp
            elif _uvs_lm_tmp:
                log.debug(f"  {node.name}: LM-UV count {len(_uvs_lm_tmp)} != vert_cnt "
                          f"{vert_cnt} — discarding partial LM-UVs")

            if len(_uvs_2_tmp) == vert_cnt:
                node.uvs_2 = _uvs_2_tmp
            elif _uvs_2_tmp:
                log.debug(f"  {node.name}: UV2 count {len(_uvs_2_tmp)} != vert_cnt "
                          f"{vert_cnt} — discarding partial UV2s")

            if len(_uvs_3_tmp) == vert_cnt:
                node.uvs_3 = _uvs_3_tmp
            elif _uvs_3_tmp:
                log.debug(f"  {node.name}: UV3 count {len(_uvs_3_tmp)} != vert_cnt "
                          f"{vert_cnt} — discarding partial UV3s")

        # ── Diagnostic: log MDX channel layout for debugging UV/normal issues ─
        # Emitted at DEBUG level so it appears in the log file but not the UI.
        log.debug(
            f"  MESH DIAG [{node.name}]: "
            f"verts={len(node.vertices)}/{vert_cnt}  "
            f"normals={len(node.normals)}  "
            f"uvs={len(node.uvs)}  "
            f"uvs_lm={len(node.uvs_lm)}  "
            f"faces={len(node.faces)}  "
            f"stride={mdx_data_size}  "
            f"bitmap=0x{mdx_data_bitmap:08x}  "
            f"mdx_valid={_mdx_valid}  "
            f"n_ok={_n_ok}  t1_ok={_t1_ok}  lm_ok={_lm_ok}  "
            f"v_off={mdx_v_off}  n_off={mdx_n_off:#x}  "
            f"t1_off={mdx_t1_off:#010x}  lm_off={mdx_lm_off:#010x}  "
            f"t2_off={mdx_t2_off:#010x}  t3_off={mdx_t3_off:#010x}  "
            f"mdx_data_off={mdx_data_off}  verts_off={verts_off}  "
            f"mdx_len={len(mdx)}"
        )
        # Sample first UV to catch inverted/wrong UV range
        if node.uvs:
            u0, v0 = node.uvs[0]
            log.debug(
                f"  UV SAMPLE [{node.name}]: first UV=({u0:.4f}, {v0:.4f})  "
                f"tex={tex_name!r}  tex_cnt={tex_cnt}  has_lm={has_lm}  "
                f"bitmap_t1={_bm_has_t1}  t1_ok={_t1_ok}"
            )

        # ── Read faces ──────────────────────────────────────────────────────
        # Face entry = 32 bytes: normal(12) planeDist(4) mat(4) adjFaces(6) verts(6)
        # Clamp face material index (mat) to [0, tex_count-1].
        # The mat field is a raw uint32; corrupt MDL data can produce 0xFFFFFFFF
        # or other values far exceeding the valid texture slot range.  Without
        # clamping, out-of-range indices crash _get_tex_for_face with IndexError
        # or cause a silent index miss that renders the wrong texture.
        _max_slot = max(0, node.tex_count - 1)
        if faces_cnt > 0 and faces_off > 0:
            fa = B + faces_off
            for i in range(min(faces_cnt, 65535)):
                p = fa + i * 32
                if p + 32 > len(d): break
                mat = struct.unpack_from('<I', d, p + 16)[0]
                # Clamp to valid texture slot range immediately at parse time
                mat = int(mat) & 0x7FFFFFFF  # strip sign-extended garbage
                mat = min(mat, _max_slot)
                v1, v2, v3 = struct.unpack_from('<HHH', d, p + 26)
                node.faces.append((v1, v2, v3))
                node.face_mats.append(mat)

        log.debug(f"  {node.name}: {len(node.vertices)} verts, "
                  f"{len(node.faces)} faces, tex={tex_name!r}")

        # ── Skin weights ────────────────────────────────────────────────────
        if node.flags & NodeFlags.SKIN:
            self._parse_skin(node, o, vert_cnt, mdx_data_off, mdx_data_size, mdx)

        # ── Dangly (cloth) mesh data ─────────────────────────────────────────
        # Dangly header immediately follows the mesh header (at offset `o`).
        # If SKIN is also set (unusual but possible), skin was parsed at `o`
        # and the dangly header would be at o + skin_header_size (100 bytes).
        # Skin header is 100 bytes (not 28) — the extra 72 bytes
        # are qbone(12) + tbone(12) + garbage(12) + bone_indices[16](32) + pad(4).
        # Verified against KotorBlender io_scene_kotor/format/mdl/reader.py.
        # In practice KotOR never combines SKIN+DANGLY, so this path is rarely hit.
        if node.flags & NodeFlags.DANGLY:
            dangly_off = o + 100 if (node.flags & NodeFlags.SKIN) else o
            self._parse_dangly(node, dangly_off)

    def _parse_skin(self, node, skin_hdr_off, vert_cnt, mdx_data_off, mdx_data_size, mdx):
        """
        KotOR skin node header (after the mesh header):

        Verified against KotorBlender io_scene_kotor/format/mdl/reader.py:
          +0   compile_weights array descriptor (3 × uint32 = 12 bytes: off/cnt/cnt2)
          +12  MDX weight-channel offset (uint32, offset within each MDX stride)
          +16  MDX bone-ref channel offset (uint32)
          +20  bone_map array offset in MDL (relative to BASE)
          +24  bone_map count
          +28  qbone_array descriptor (3 × uint32 = 12 bytes)  ← previously skipped
          +40  tbone_array descriptor (3 × uint32 = 12 bytes)  ← previously skipped
          +52  garbage_array descriptor (3 × uint32 = 12 bytes)  ← previously skipped
          +64  bone_indices[16] (16 × uint16 = 32 bytes)  ← previously skipped
          +96  padding (4 bytes)  ← previously skipped
          +100 (end of skin header, 100 bytes total after mesh header)

        The bone_map is a **float32** array of length bm_cnt on PC.
          value == -1.0  → bone slot unused
          value == N.0   → this slot corresponds to the node whose
                           'number' field (from the node header) equals N

        XBOX ENCODING (confirmed by xoreos model_kotor.cpp readSkin()):
          - Bone_map array entries are Sint16LE (2 bytes each), NOT float32.
            Value is cast directly to float: float(sint16_val).
            -1 (0xFFFF signed) = unused slot.
          - MDX per-vertex bone_refs are 4×uint16LE (8 bytes), NOT 4×float (16 bytes).
          - Skin section header skips 8 bytes before MDX offsets (vs 12 on PC).
            The 4-byte difference is because the compile_weights array is shorter.

        MDX per-vertex skin data (at mdx_sw_off / mdx_br_off within stride):
          PC:   4 × float32 weights  +  4 × float32 bone_refs
          Xbox: 4 × float32 weights  +  4 × uint16  bone_refs (Sint16LE cast to float)

        CRITICAL: The MDX bone_ref values are NOT direct indices into the full
        bone_map array.  They are indices into a COMPACT sub-list of the active
        (non -1) bone slots.  I.e.:
          compact_bones = [node_num for node_num in bone_map_floats if node_num >= 0]
          bone_ref = k  →  node_number = compact_bones[k]
        This is the correct KotOR/NWN convention verified against K1 binary files.
        """
        d = self.mdl; B = self.BASE; o = skin_hdr_off
        is_xbox = self._is_xbox
        try:
            # Xbox skips 8 bytes before MDX offsets; PC skips 12.
            # The compile_weights array is 3×uint32 on PC (12 bytes) but
            # only 2×uint32 on Xbox (8 bytes). Confirmed by xoreos readSkin().
            o += (8 if is_xbox else 12)   # skip compile_weights array descriptor
            sw_off  = _ru32(d, o); o += 4   # MDX weight-channel offset in stride
            sbr_off = _ru32(d, o); o += 4   # MDX bone-ref channel offset in stride
            bm_off  = _ru32(d, o); o += 4   # bone_map offset in MDL (from BASE)
            bm_cnt  = _ru32(d, o); o += 4   # number of bone_map entries
            # ── Read qbone/tbone inverse-bind descriptors ───────────────────
            # qbone_arr descriptor (3 × uint32 = 12 bytes): off, count, count2
            # tbone_arr descriptor (3 × uint32 = 12 bytes): off, count, count2
            # These contain the per-compact-bone inverse bind quaternion/position,
            # i.e. the stored inverse of the bone's world transform at bind pose.
            # KotOR.js reads these as bone_inverse_matrix and passes to THREE.Skeleton.
            # References: OdysseyModelNodeSkin.ts boneQuaternionDefinition / bonePositionDefinition
            qb_off = _ru32(d, o); qb_cnt = _ru32(d, o+4); o += 12   # qbone array descriptor
            tb_off = _ru32(d, o); tb_cnt = _ru32(d, o+4); o += 12   # tbone array descriptor
            o += 12   # skip garbage_array descriptor (3 × uint32)

            # ── Read bone_parts (17 uint16 entries) ──────────────────────────
            # bone_parts[i] = the node_number of the i-th compact bone in this skin mesh.
            # MDX per-vertex bone_ref float k → compact index k → node_num = bone_parts[k].
            # This is the CORRECT way to resolve compact bone indices to node names.
            # KotOR.js (OdysseyModelNodeSkin.ts) reads 17 uint16 entries here.
            # Note: the array is always 17 uint16 = 34 bytes; valid entries are at [0..N-1]
            # where N = number of active (non -1.0) entries in bone_map_floats.
            # Unused trailing slots contain garbage bytes (NOT 0xFFFF).
            # We read all 17 here and slice to active_count later (after reading bone_map).
            bone_parts_raw: List[int] = []
            for i in range(17):
                val = struct.unpack_from('<H', d, o)[0]
                bone_parts_raw.append(val)
                o += 2
            o += 2   # 2-byte pad: 17×2=34 bytes + 2 pad = 36 → total header 12+4+4+4+4+12+12+12+36 = 100 bytes ✓

            # ── Read bone map (to determine active_count) ─────────────────────
            # PC:   float32 per entry (4 bytes), -1.0 = unused
            # Xbox: Sint16LE per entry (2 bytes), cast directly to float
            #       -1 (0xFFFF signed) = unused  (no scale factor!)
            bm_abs = B + bm_off
            bone_map_floats: List[float] = []
            _entry_size = 2 if is_xbox else 4
            for i in range(min(bm_cnt, 512)):
                ptr = bm_abs + i * _entry_size
                if ptr + _entry_size > len(d):
                    break
                if is_xbox:
                    # Sint16LE → cast to Python int → float (no scale factor)
                    v = float(struct.unpack_from('<h', d, ptr)[0])
                else:
                    v = _rf32(d, ptr)
                bone_map_floats.append(v)

            # active_count = number of non-(-1) entries in bone_map.
            # bone_parts_raw[0..active_count-1] are the valid compact bone node numbers.
            # Trailing entries (active_count..16) are garbage and must be discarded.
            active_count = sum(1 for v in bone_map_floats if v >= 0.0)

            # Build num_to_name map for bone name resolution.
            # Walk the parsed cache to map node.number → node.name
            num_to_name: Dict[int, str] = {}
            for _off, cached_node in self._cache.items():
                num_to_name[cached_node.number] = cached_node.name

            # Slice bone_parts to active_count (the actual number of compact bones).
            # This discards garbage beyond the valid entries without relying on sentinel
            # values (which are absent in KotOR's bone_parts array).
            bone_parts: List[int] = bone_parts_raw[:active_count]

            # Read qbone quaternions (w,x,y,z each as float32, 16 bytes per entry)
            # These are the inverse-bind rotations, indexed by compact bone index (0..active_count-1).
            # KotOR.js: bone_quaternions[i] at boneQuaternionDefinition.offset + i*16
            qbones: List = []
            if qb_cnt > 0 and qb_off > 0 and qb_off < len(d):
                for i in range(min(qb_cnt, 128)):
                    ptr = B + qb_off + i * 16
                    if ptr + 16 > len(d):
                        break
                    # KotOR.js reads w first, then x,y,z
                    w, x, y, z = struct.unpack_from('<ffff', d, ptr)
                    qbones.append((x, y, z, w))  # store as (x,y,z,w) for internal convention
            node.inv_bind_quats = qbones   # compact-index → (x,y,z,w) inverse-bind quaternion

            # Read tbone translations (x,y,z each as float32, 12 bytes per entry)
            # These are the inverse-bind positions, indexed by compact bone index.
            tbones: List = []
            if tb_cnt > 0 and tb_off > 0 and tb_off < len(d):
                for i in range(min(tb_cnt, 128)):
                    ptr = B + tb_off + i * 12
                    if ptr + 12 > len(d):
                        break
                    x, y, z = struct.unpack_from('<fff', d, ptr)
                    tbones.append((x, y, z))
            node.inv_bind_positions = tbones  # compact-index → (x,y,z) inverse-bind position

            log.debug(f"  {node.name}: active_count={active_count} bone_parts={len(bone_parts)} "
                      f"qbone={len(qbones)} tbone={len(tbones)}")

            # ── Build bone_map from bone_parts (the correct compact index mapping) ──
            # bone_parts[i] = node_number of the i-th compact bone slot.
            # MDX per-vertex bone_refs are compact indices 0..N-1 that index into bone_parts.
            # This correctly maps left-side skin nodes to left-side bones (and right to right).
            #
            # FIX-BONE-PARTS (v7.0): Use bone_parts to build bone_map instead of bone_map_floats.
            # Reference: KotOR.js OdysseyModelNodeSkin.ts bone_parts array + bone_inverse_matrix.
            #
            # Fallback: if bone_parts is empty (e.g. Xbox models or unusual PC models),
            # fall back to the compact list derived from bone_map_floats.
            node.bone_map_floats = bone_map_floats   # store for reference / Xbox fallback
            node.bone_map = []
            if bone_parts:
                for node_num in bone_parts:
                    bname = num_to_name.get(node_num, '')
                    if not bname and node_num < len(self._names):
                        bname = self._names[node_num]
                    if not bname:
                        bname = f'bone_{node_num}'
                    node.bone_map.append(bname)
                log.debug(f"  {node.name}: bone_parts bone_map → {len(node.bone_map)} bones")
            else:
                # Fallback: derive compact bone list from bone_map_floats (active entries only)
                compact_bones_fb: List[int] = [int(round(v)) for v in bone_map_floats if v >= 0]
                for node_num in compact_bones_fb:
                    bname = num_to_name.get(node_num, '')
                    if not bname and node_num < len(self._names):
                        bname = self._names[node_num]
                    if not bname:
                        bname = f'bone_{node_num}'
                    node.bone_map.append(bname)
                log.debug(f"  {node.name}: fallback bone_map → {len(node.bone_map)} bones")

            # ── Read per-vertex weights from MDX ─────────────────────────────
            # PC:   bone_ref values are float32 compact indices (4×4 = 16 bytes)
            # Xbox: bone_ref values are uint16 compact indices  (4×2 = 8 bytes)
            # In both cases values are indices into compact_bones[], NOT into
            # the full bone_map array.
            stride = mdx_data_size if mdx_data_size else 32
            # Validate MDX bounds for skin data before parsing vertices.
            # sw_off/sbr_off of 0xFFFFFFFF means channel absent.
            # sw_off == 0 can be valid (weight data starts at stride offset 0),
            # but sbr_off == 0 without sw_off being reasonable is a sign of
            # a corrupt/unusual model – we guard with explicit bounds checks.
            sw_valid  = (sw_off  != 0xFFFFFFFF and sw_off  < stride)
            sbr_valid = (sbr_off != 0xFFFFFFFF and sbr_off < stride)
            # Xbox bone_ref block is 8 bytes (4×uint16); PC is 16 bytes (4×float32)
            _sbr_size = 8 if is_xbox else 16
            # BUGFIX: removed the erroneous '+ stride' from the upper bound check.
            # Previously: mdx_data_off + vert_cnt * stride <= len(mdx) + stride
            # This allowed reading up to 1 stride PAST the end of the MDX buffer,
            # which on a tight MDX buffer causes struct.unpack_from to read garbage
            # or raise struct.error, which was swallowed by the outer try/except.
            # The per-vertex bounds check (base + sw_off + 16 <= len(mdx)) still
            # catches individual out-of-bounds reads, but the pre-flight check
            # should be tight to skip corrupt models early.
            mdx_skin_safe = (len(mdx) > 0 and stride > 0
                             and mdx_data_off + vert_cnt * stride <= len(mdx))
            for i in range(min(vert_cnt, 65535)):
                base = mdx_data_off + i * stride
                sd = VertexSkinData()
                if mdx_skin_safe and sw_valid and base + sw_off + 16 <= len(mdx):
                    wts = struct.unpack_from('<ffff', mdx, base + sw_off)
                    if sbr_valid and base + sbr_off + _sbr_size <= len(mdx):
                        if is_xbox:
                            # Xbox: 4 × uint16LE cast to float (no scale factor)
                            brs = tuple(float(v) for v in
                                        struct.unpack_from('<HHHH', mdx, base + sbr_off))
                        else:
                            brs = struct.unpack_from('<ffff', mdx, base + sbr_off)
                    else:
                        brs = (-1.0, -1.0, -1.0, -1.0)
                    for j in range(4):
                        wj = wts[j]
                        if wj > 1e-5 and brs[j] >= 0:
                            compact_idx = int(round(brs[j]))
                            if 0 <= compact_idx < len(node.bone_map):
                                sd.influences.append(BoneWeight(compact_idx, wj))
                    # UE-inspired: normalize bone weights so they sum to 1.0
                    # (UE applies VECTOR_INV_65535 normalization to uint16 weights;
                    # KotOR stores raw floats, but they may not sum exactly to 1.0
                    # due to float precision or authoring errors.  Normalizing here
                    # makes LBS in the viewport numerically correct.)
                    if sd.influences:
                        wsum = sum(b.weight for b in sd.influences)
                        if wsum > 1e-5 and abs(wsum - 1.0) > 1e-4:
                            inv = 1.0 / wsum
                            for b in sd.influences:
                                b.weight *= inv
                node.skin_data.append(sd)
        except Exception as e:
            log.debug(f"Skin parse error on {node.name}: {e}")
            import traceback; log.debug(traceback.format_exc())

    def _parse_dangly(self, node: ModelNode, hdr_off: int):
        """
        Parse dangly (cloth) mesh data from a binary KotOR MDL node.

        Dangly mesh node extra header (immediately after the mesh header block,
        or after the skin block if the SKIN flag is also set — though in practice
        KotOR never combines DANGLY+SKIN).

        Verified against:
          - PyKotor io_mdl.py _DanglymeshHeader (NickHugi/PyKotor, 2024)
          - KotOR game EXE class MdlNodeDanglyMesh (constructor at 0x0044ae00)
          - PartDanglyMesh (0x00447980), NodeVertexDangly (0x004787e0)
          - ParseNode function at 0x004680e0 (Lane/T3M4 reverse-engineering, 2026)

        Binary layout (28 bytes total):
          +0   constraints_array_offset  (uint32, relative to BASE)
          +4   constraints_array_count   (uint32)
          +8   constraints_array_count2  (uint32)
          +12  displacement              (float32)  — max swing amplitude
          +16  tightness                 (float32)  — spring stiffness
          +20  period                    (float32)  — oscillation period (s)
          +24  unknown0                  (uint32)   — runtime pointer, ignored

        NodeVertexDangly constraint array: each entry is a single float32
        (4 bytes each, 1 entry per vertex).  Raw game values are 0.0–255.0;
        we normalise to 0.0–1.0 for internal storage (0.0=free, 1.0=pinned).
        """
        d = self.mdl; B = self.BASE; o = hdr_off
        try:
            if o + 24 > len(d):
                return
            cst_off = _ru32(d, o); o += 4
            cst_cnt = _ru32(d, o); o += 4
            _       = _ru32(d, o); o += 4   # count2 (ignored)
            displacement = struct.unpack_from('<f', d, o)[0]; o += 4
            tightness    = struct.unpack_from('<f', d, o)[0]; o += 4
            period       = struct.unpack_from('<f', d, o)[0]; o += 4

            node.dangly_displacement = displacement
            node.dangly_tightness    = tightness
            node.dangly_period       = period

            # Read constraint floats
            if cst_cnt > 0 and cst_off > 0 and cst_off + cst_cnt * 4 <= len(d):
                cst_base = B + cst_off
                raw_csts = list(
                    struct.unpack_from(f'<{cst_cnt}f', d, cst_base)
                )
                # Binary MDL constraints are 0.0–255.0; normalise to 0.0–1.0
                # for internal storage.
                if raw_csts and max(raw_csts) > 1.0 + 1e-6:
                    raw_csts = [max(0.0, min(1.0, c / 255.0)) for c in raw_csts]
                node.dangly_constraints = raw_csts
            elif cst_cnt > 0:
                # Fallback: default constraints (0.5 = medium constraint)
                node.dangly_constraints = [0.5] * len(node.vertices)

            log.debug(
                f"  {node.name}: dangly disp={displacement:.3f} "
                f"tight={tightness:.3f} period={period:.3f} "
                f"constraints={len(node.dangly_constraints)}"
            )
        except Exception as e:
            log.debug(f"Dangly parse error on {node.name}: {e}")


# ─────────────────────────────  ASCII Parser  ──────────────────────────────

class MDLAsciiParser:
    """Parses the text-format ASCII MDL produced by MDLOps"""

    def parse_file(self, path: str) -> KotorModel:
        with open(path, 'r', encoding='ascii', errors='replace') as f:
            return self.parse(f.readlines())

    def parse_string(self, text: str) -> KotorModel:
        """Parse an ASCII MDL from a string (convenience wrapper for parse())."""
        return self.parse(text.splitlines(keepends=True))

    def parse(self, lines: List[str]) -> KotorModel:
        self._lines = [l.strip() for l in lines]
        self._pos   = 0
        self._stack: List[ModelNode] = []
        model = KotorModel()

        while self._pos < len(self._lines):
            t = self._tok()
            if not t:
                self._pos += 1; continue
            cmd = t[0].lower()

            if   cmd == 'newmodel'          and len(t)>1: model.name       = t[1]
            elif cmd == 'setsupermodel'     and len(t)>2: model.supermodel  = t[2]
            elif cmd == 'classification'    and len(t)>1: model.classification = t[1].lower()
            elif cmd == 'setanimationscale' and len(t)>1: model.anim_scale  = float(t[1])
            elif cmd == 'node'              and len(t)>2:
                node = self._parse_node_block(t[1], t[2])
                # Register in node name map for parent resolution
                if not hasattr(self, '_node_map'):
                    self._node_map = {}
                self._node_map[node.name] = node
                if model.root_node is None:
                    model.root_node = node
            elif cmd == 'newanim'           and len(t)>1:
                anim = self._parse_anim_block(t[1])
                model.animations.append(anim)
            elif cmd == 'donemodel': break
            self._pos += 1

        # Resolve deferred parent-name references (KotOR flat top-level node format)
        # Each node parsed with a _pending_parent_name gets linked to its parent here.
        node_map = getattr(self, '_node_map', {})
        if node_map:
            for nname, nnode in node_map.items():
                pname = getattr(nnode, '_pending_parent_name', None)
                if pname and pname.upper() != 'NULL':
                    parent_node = node_map.get(pname)
                    if parent_node and parent_node is not nnode:
                        # Only link if not already linked via stack mechanism
                        if nnode.parent is None:
                            nnode.parent = parent_node
                            if nnode not in parent_node.children:
                                parent_node.children.append(nnode)
            self._node_map = {}

        # map classification to model_type (corrected KotOR values)
        # Map ASCII classification string → binary model_type byte
        # Aligned with KotorBlender types.py CLASS_BY_VALUE
        cls_map = {
            'effect': 0, 'other': 0,              # OTHER/EFFECT
            'effects': 1,                          # EFFECT (particle FX)
            'tile': 2, 'misc': 2,                  # TILE (was misc)
            'character': 4,                        # CHARACTER
            'door': 8,                             # DOOR
            'lightsaber': 16,                      # LIGHTSABER (0x10, newly added)
            'placeable': 32, 'item': 32,           # PLACEABLE (was item)
            'flyer': 64, 'rare_char': 64,          # FLYER (was rare_char)
        }
        model.model_type = cls_map.get(model.classification, 4)
        model.compute_bounds()
        MDLBinaryParser._generate_missing_normals(model)
        MDLBinaryParser._apply_bind_pose_controllers(model)
        return model

    def _parse_anim_block(self, anim_name: str) -> 'Animation':
        """Parse a newanim … doneanim block."""
        from .model_data import Animation, AnimEvent
        anim = Animation(name=anim_name)
        self._pos += 1

        while self._pos < len(self._lines):
            t = self._tok()
            if not t: self._pos += 1; continue
            cmd = t[0].lower()

            if cmd == 'doneanim':
                return anim
            elif cmd == 'length'     and len(t)>1: anim.length          = float(t[1])
            elif cmd == 'transtime'  and len(t)>1: anim.transition_time = float(t[1])
            elif cmd == 'animroot'   and len(t)>1: anim.anim_root       = t[1]
            elif cmd == 'event'      and len(t)>2:
                anim.events.append(AnimEvent(time=float(t[1]), name=t[2]))
            elif cmd == 'node'       and len(t)>2:
                node = self._parse_node_block(t[1], t[2])
                anim.nodes.append(node)

            self._pos += 1

        return anim

    def _tok(self) -> List[str]:
        return self._lines[self._pos].split() if self._pos < len(self._lines) else []

    def _parse_node_block(self, type_str: str, name: str) -> ModelNode:
        flags = _ascii_type_to_flags(type_str)
        node  = ModelNode(name=name, flags=flags)
        if self._stack:
            p = self._stack[-1]
            node.parent = p
            p.children.append(node)
        self._stack.append(node); self._pos += 1

        while self._pos < len(self._lines):
            t = self._tok()
            if not t: self._pos += 1; continue
            cmd = t[0].lower()

            if cmd == 'endnode':
                # Populate texture_names for multi-texture ASCII nodes
                # bitmap = slot 0, bitmap2 = slot 1 (secondary texture)
                node.texture_names = [node.texture] if node.texture else ['']
                if node.lightmap and not node.has_lightmap:
                    # bitmap2 without a real lightmap = secondary material texture
                    node.texture_names.append(node.lightmap)
                    node.tex_count = 2
                self._stack.pop(); return node

            elif cmd == 'parent' and len(t)>1:
                # Store parent name as a string for deferred resolution
                # (KotOR ASCII MDL: nodes are top-level with parent keyword)
                node._pending_parent_name = t[1]
            elif cmd == 'position'  and len(t)>=4:
                node.position = (float(t[1]),float(t[2]),float(t[3]))
            elif cmd == 'orientation' and len(t)>=5:
                node.rotation = (float(t[1]),float(t[2]),float(t[3]),float(t[4]))
            elif cmd == 'bitmap'    and len(t)>1: node.texture = t[1]
            elif cmd == 'bitmap2'   and len(t)>1: node.lightmap = t[1]
            elif cmd == 'bumpmap'   and len(t)>1: node.bump_map = t[1]
            elif cmd == 'diffuse'   and len(t)>=4:
                node.diffuse = (float(t[1]),float(t[2]),float(t[3]))
            elif cmd == 'ambient'   and len(t)>=4:
                node.ambient = (float(t[1]),float(t[2]),float(t[3]))
            elif cmd == 'specular'  and len(t)>=4:
                node.specular= (float(t[1]),float(t[2]),float(t[3]))
            elif cmd == 'shininess' and len(t)>1: node.shininess = float(t[1])
            elif cmd == 'shadow'    and len(t)>1: node.has_shadow = int(t[1])!=0
            elif cmd == 'render'    and len(t)>1: node.render     = int(t[1])!=0
            elif cmd == 'alpha'     and len(t)>1: node.alpha      = float(t[1])
            elif cmd == 'selfillumcolor' and len(t)>=4:
                node.selfillum = (float(t[1]),float(t[2]),float(t[3]))
            elif cmd == 'transparencyhint' and len(t)>1: node.transparency_hint = int(t[1])
            elif cmd == 'lightmapped' and len(t)>1: node.has_lightmap = int(t[1])!=0
            elif cmd == 'beaming'   and len(t)>1: node.beaming = int(t[1])!=0
            elif cmd == 'rotatetexture' and len(t)>1: node.rotate_texture = int(t[1])!=0  
            elif cmd == 'displacement' and len(t)>1: node.dangly_displacement = float(t[1])
            elif cmd == 'tightness'    and len(t)>1: node.dangly_tightness    = float(t[1])
            elif cmd == 'period'       and len(t)>1: node.dangly_period       = float(t[1])
            elif cmd == 'radius'       and len(t)>1: node.light_radius        = float(t[1])
            elif cmd == 'multiplier'   and len(t)>1: node.light_multiplier    = float(t[1])
            elif cmd == 'color'        and len(t)>=4:
                node.light_color = (float(t[1]),float(t[2]),float(t[3]))

            elif cmd == 'verts' and len(t)>1:
                count = int(t[1]); self._pos+=1
                for _ in range(count):
                    vt = self._tok()
                    if len(vt)>=3:
                        node.vertices.append((float(vt[0]),float(vt[1]),float(vt[2])))
                    self._pos+=1
                continue

            elif cmd == 'tverts' and len(t)>1:
                count = int(t[1]); self._pos+=1
                for _ in range(count):
                    vt = self._tok()
                    if len(vt)>=2:
                        node.uvs.append((float(vt[0]),float(vt[1])))
                    self._pos+=1
                continue

            elif cmd == 'normals' and len(t)>1:
                count = int(t[1]); self._pos+=1
                for _ in range(count):
                    vt = self._tok()
                    if len(vt)>=3:
                        node.normals.append((float(vt[0]),float(vt[1]),float(vt[2])))
                    self._pos+=1
                continue

            elif cmd == 'faces' and len(t)>1:
                # ASCII face format: v1 v2 v3 smooth t1 t2 t3 mat
                # v1/v2/v3 = vertex indices; t1/t2/t3 = UV indices; mat = material slot.
                # KotOR ASCII MDL uses separate tvert indices that may differ from vertex indices.
                # We store face_uvs as a parallel list of tvert triples so the viewport can
                # sample the correct UV for each face vertex.
                count = int(t[1]); self._pos+=1
                for _ in range(count):
                    ft = self._tok()
                    if len(ft)>=3:
                        v1, v2, v3 = int(ft[0]), int(ft[1]), int(ft[2])
                        node.faces.append((v1, v2, v3))
                        # Read tvert indices (positions 4,5,6) and material (position 7)
                        if len(ft) >= 7:
                            t1, t2, t3 = int(ft[4]), int(ft[5]), int(ft[6])
                        else:
                            # Fall back to vertex indices if tvert indices missing
                            t1, t2, t3 = v1, v2, v3
                        if not hasattr(node, 'face_uvs'):
                            node.face_uvs = []
                        node.face_uvs.append((t1, t2, t3))
                        if len(ft) >= 8:
                            mat = min(int(ft[7]) & 0x7FFFFFFF,
                                      max(0, getattr(node, 'tex_count', 1) - 1))
                            node.face_mats.append(mat)
                        else:
                            node.face_mats.append(0)
                    self._pos+=1
                continue

            elif cmd == 'constraints' and len(t)>1:
                count = int(t[1]); self._pos+=1
                raw = []
                for _ in range(count):
                    ct = self._tok()
                    if ct: raw.append(float(ct[0]))
                    self._pos+=1
                # Normalise to 0.0–1.0 internal range.
                # Game MDL files (via MDLOps) store 0.0–255.0; our generated
                # constraints use 0.0–1.0.  Auto-detect and normalise.
                if raw and max(raw) > 1.0 + 1e-6:
                    raw = [max(0.0, min(1.0, c / 255.0)) for c in raw]
                node.dangly_constraints.extend(raw)
                continue

            elif cmd == 'weights' and len(t)>1:
                # ASCII skin weight format: one line per vertex, each line is
                #   "bone_name weight [bone_name weight ...]"
                # Build skin_data (list of VertexInfluence) and bone_map.
                from .model_data import VertexSkinData, BoneWeight
                count = int(t[1]); self._pos+=1
                bone_name_to_idx = {}
                bone_compact = []
                for vi_idx in range(count):
                    wt = self._tok()
                    infl = []
                    if wt:
                        # May be multiple bone/weight pairs on same line
                        pairs = wt
                        i2 = 0
                        while i2 + 1 < len(pairs):
                            bname = pairs[i2]
                            try:
                                bw = float(pairs[i2+1])
                            except (ValueError, IndexError):
                                i2 += 1; continue
                            if bname not in bone_name_to_idx:
                                bone_name_to_idx[bname] = len(bone_compact)
                                bone_compact.append(bname)
                            infl.append(BoneWeight(
                                bone_index=bone_name_to_idx[bname],
                                weight=bw))
                            i2 += 2
                    node.skin_data.append(VertexSkinData(influences=infl))
                    self._pos += 1
                # Store compact bone names in bone_map
                node.bone_map = bone_compact
                continue

            elif cmd == 'node' and len(t)>=3:
                self._parse_node_block(t[1], t[2])

            # ── Animation controller keyframe tables ──────────────────────────
            elif cmd in _ASCII_CTRL_CMDS and len(t) > 1:
                ctrl_info = _ASCII_CTRL_CMDS[cmd]
                ctype, ncols = ctrl_info
                count = int(t[1]); self._pos += 1
                times_out = []; vals_out = []
                for _ in range(count):
                    kt = self._tok()
                    if kt and len(kt) >= ncols + 1:
                        try:
                            tk = float(kt[0])
                            row = [float(kt[j+1]) for j in range(ncols)]
                            times_out.append(tk)
                            vals_out.append(row)
                        except (ValueError, IndexError):
                            pass
                    self._pos += 1
                if times_out:
                    node.controllers.append({
                        'type':   ctype,
                        'name':   cmd,
                        'times':  times_out,
                        'values': vals_out,
                        'columns': ncols,
                    })
                continue

            self._pos += 1
        return node


# ── ASCII controller keyword → (type_id, ncols) ──────────────────────────────
# Controller type IDs verified against KotorBlender types.py (seedhartha):
#   CTRL_MESH_SELFILLUMCOLOR = 100  (3 floats: r,g,b)
#   CTRL_MESH_ALPHA          = 132  (1 float)
# PREVIOUS BUG: alpha was mapped to type 100 and selfillum to 132, which is
# BACKWARDS.  The correct mapping (per KotorBlender types.py + NWN binary spec):
#   alphakey        → type 132  (1 column)
#   selfillumcolorkey → type 100 (3 columns)
_ASCII_CTRL_CMDS = {
    'positionkey':        (8,   3),
    'orientationkey':     (20,  4),
    'scalekey':           (36,  1),
    'alphakey':           (132, 1),   # CTRL_MESH_ALPHA = 132
    'colorkey':           (76,  3),
    'selfillumcolorkey':  (100, 3),   # CTRL_MESH_SELFILLUMCOLOR = 100
}


# ─────────────────────────────  ASCII Writer  ──────────────────────────────

class MDLAsciiWriter:
    """Writes ASCII MDL ready for MDLOps compilation"""

    def _build_lines(self, model: KotorModel) -> List[str]:
        """Build all lines of the ASCII MDL output (without writing to disk)."""
        lines = []
        lines.append("# Exported by KotorModTools v1.0")
        lines.append(f"newmodel {model.name}")
        lines.append(f"setsupermodel {model.name} {model.supermodel}")
        lines.append(f"classification {model.classification}")
        lines.append(f"setanimationscale {model.anim_scale:.6f}")
        if model.disable_fog: lines.append(f"setfog 0")
        lines.append("")

        if model.root_node:
            self._write_node(model.root_node, lines)

        # Animations
        for anim in model.animations:
            self._write_anim(anim, model.name, lines)

        lines.append(f"donemodel {model.name}")
        lines.append("")
        return lines

    def to_string(self, model: KotorModel) -> str:
        """Return the full ASCII MDL as a string (no file I/O)."""
        return '\n'.join(self._build_lines(model))

    def write(self, model: KotorModel, path: str):
        lines = self._build_lines(model)
        with open(path, 'w', encoding='ascii', errors='replace') as f:
            f.write('\n'.join(lines))
        log.info(f"Wrote ASCII MDL → {path}")

    def _write_node(self, node: ModelNode, lines: List[str]):
        pname = node.parent.name if node.parent else "NULL"
        lines.append(f"node {node.type_label} {node.name}")
        lines.append(f"  parent {pname}")
        px,py,pz = node.position
        lines.append(f"  position {px:.6f} {py:.6f} {pz:.6f}")
        rx,ry,rz,rw = node.rotation
        lines.append(f"  orientation {rx:.6f} {ry:.6f} {rz:.6f} {rw:.6f}")

        if node.is_mesh:
            self._write_mesh(node, lines)
        if node.is_light:
            self._write_light(node, lines)
        if node.is_dangly:
            self._write_dangly(node, lines)
        if node.is_emitter:
            self._write_emitter(node, lines)

        # Write bind-pose controller data for non-animation nodes that have it
        for ctrl in node.controllers:
            ctype  = ctrl.get('type', -1)
            times  = ctrl.get('times', [])
            values = ctrl.get('values', [])
            if not times or not values:
                continue
            label, ncols = self._CTRL_LABELS.get(ctype, (None, None))
            if label is None:
                continue
            nkeys = len(times)
            lines.append(f"  {label} {nkeys}")
            for i, tk in enumerate(times):
                row = list(values[i]) if i < len(values) else []
                while len(row) < ncols:
                    row.append(0.0)
                row = row[:ncols]
                vals_str = " ".join(f"{v:.6f}" for v in row)
                lines.append(f"    {tk:.6f} {vals_str}")

        for ch in node.children:
            self._write_node(ch, lines)

        lines.append("endnode")
        lines.append("")

    def _write_mesh(self, n: ModelNode, L: List[str]):
        if n.texture:      L.append(f"  bitmap {n.texture}")
        if n.lightmap:     L.append(f"  bitmap2 {n.lightmap}")
        if n.has_lightmap: L.append(f"  lightmapped 1")
        if n.bump_map:     L.append(f"  bumpmap {n.bump_map}")
        dr,dg,db = n.diffuse
        L.append(f"  diffuse {dr:.4f} {dg:.4f} {db:.4f}")
        ar,ag,ab = n.ambient
        L.append(f"  ambient {ar:.4f} {ag:.4f} {ab:.4f}")
        sr,sg,sb = n.specular
        L.append(f"  specular {sr:.4f} {sg:.4f} {sb:.4f}")
        L.append(f"  shininess {n.shininess:.4f}")
        L.append(f"  shadow {1 if n.has_shadow else 0}")
        L.append(f"  render {1 if n.render else 0}")
        L.append(f"  alpha {n.alpha:.4f}")
        ir,ig,ib = n.selfillum
        L.append(f"  selfillumcolor {ir:.4f} {ig:.4f} {ib:.4f}")
        L.append(f"  transparencyhint {n.transparency_hint}")
        L.append(f"  beaming {1 if n.beaming else 0}")
        L.append(f"  backgroundgeometry {1 if n.background_geometry else 0}")
        L.append(f"  rotatetexture {1 if n.rotate_texture else 0}")

        if n.vertices:
            L.append(f"  verts {len(n.vertices)}")
            for x,y,z in n.vertices: L.append(f"    {x:.6f} {y:.6f} {z:.6f}")

        if n.uvs:
            L.append(f"  tverts {len(n.uvs)}")
            for u,v in n.uvs: L.append(f"    {u:.6f} {v:.6f}")

        if n.normals:
            L.append(f"  normals {len(n.normals)}")
            for x,y,z in n.normals: L.append(f"    {x:.6f} {y:.6f} {z:.6f}")

        if n.faces:
            has_uv = bool(n.uvs)
            L.append(f"  faces {len(n.faces)}")
            for fi,(v1,v2,v3) in enumerate(n.faces):
                sm = 1
                mat = n.face_mats[fi] if fi < len(n.face_mats) else 1
                if has_uv:
                    t1 = min(v1, len(n.uvs)-1)
                    t2 = min(v2, len(n.uvs)-1)
                    t3 = min(v3, len(n.uvs)-1)
                    L.append(f"    {v1} {v2} {v3} {sm} {t1} {t2} {t3} {mat}")
                else:
                    L.append(f"    {v1} {v2} {v3} {sm} {v1} {v2} {v3} {mat}")

        # Skin weights
        if n.is_skin and n.skin_data:
            bone_names = ' '.join(n.bone_map)
            if bone_names: L.append(f"  boneconstraints {len(n.bone_map)}")
            L.append(f"  weights {len(n.skin_data)}")
            for sd in n.skin_data:
                parts = []
                for inf in sd.influences[:4]:
                    if inf.weight > 0.0001:
                        bn = n.bone_map[inf.bone_index] if inf.bone_index < len(n.bone_map) else str(inf.bone_index)
                        parts.append(f"{bn} {inf.weight:.4f}")
                L.append(f"    {' '.join(parts) if parts else '0 1.0000'}")

    def _write_light(self, n: ModelNode, L: List[str]):
        L.append(f"  radius {n.light_radius:.4f}")
        r,g,b = n.light_color
        L.append(f"  color {r:.4f} {g:.4f} {b:.4f}")
        L.append(f"  multiplier {n.light_multiplier:.4f}")
        L.append(f"  shadow {1 if n.light_shadow else 0}")
        L.append(f"  flare {1 if n.light_flare else 0}")
        L.append(f"  fadinglight {1 if n.light_fading else 0}")
        L.append(f"  ambientonly {1 if n.light_ambient_only else 0}")

    def _write_dangly(self, n: ModelNode, L: List[str]):
        L.append(f"  displacement {n.dangly_displacement:.4f}")
        L.append(f"  tightness {n.dangly_tightness:.4f}")
        L.append(f"  period {n.dangly_period:.4f}")
        if n.dangly_constraints:
            # KotOR MDL constraint scale: 0.0 (free) – 255.0 (pinned).
            # Our ClothConstraintPainter generates normalised 0.0–1.0 values.
            # Binary-read constraints from game files come in at 0.0–255.0.
            # Auto-detect: if all values ≤ 1.0 assume normalised → scale × 255.
            csts = n.dangly_constraints
            if csts and max(csts) <= 1.0 + 1e-6:
                csts = [max(0.0, min(255.0, c * 255.0)) for c in csts]
            L.append(f"  constraints {len(csts)}")
            for c in csts: L.append(f"    {c:.4f}")

    def _write_emitter(self, n: ModelNode, L: List[str]):
        for k,v in n.emitter_params.items():
            L.append(f"  {k} {v}")

    def _write_anim(self, anim: Animation, model_name: str, L: List[str]):
        L.append(f"newanim {anim.name} {model_name}")
        L.append(f"  length {anim.length:.4f}")
        L.append(f"  transtime {anim.transition_time:.4f}")
        if anim.anim_root: L.append(f"  animroot {anim.anim_root}")
        for ev in anim.events:
            L.append(f"  event {ev.time:.4f} {ev.name}")
        for node in anim.nodes:
            self._write_anim_node(node, L)
        L.append(f"doneanim {anim.name} {model_name}")
        L.append("")

    # Controller-type → (ASCII label, column count)
    # Verified against KotorBlender types.py:
    #   CTRL_MESH_SELFILLUMCOLOR = 100  → "selfillumcolorkey" (3 cols)
    #   CTRL_MESH_ALPHA          = 132  → "alphakey"          (1 col)
    _CTRL_LABELS = {
        8:   ("positionkey",       3),
        20:  ("orientationkey",    4),
        36:  ("scalekey",          1),
        76:  ("colorkey",          3),
        100: ("selfillumcolorkey", 3),   # CTRL_MESH_SELFILLUMCOLOR = 100
        132: ("alphakey",          1),   # CTRL_MESH_ALPHA = 132
    }

    def _write_anim_node(self, node: 'ModelNode', L: List[str]):
        """Write an animation node block, including controller keyframe tables."""
        pname = node.parent.name if node.parent else "NULL"
        L.append(f"node {node.type_label} {node.name}")
        L.append(f"  parent {pname}")

        # Write controller keyframe data
        for ctrl in node.controllers:
            ctype  = ctrl.get('type', -1)
            times  = ctrl.get('times', [])
            values = ctrl.get('values', [])
            if not times or not values:
                continue
            label, ncols = self._CTRL_LABELS.get(ctype, (None, None))
            if label is None:
                continue  # unknown / unsupported controller type
            nkeys = len(times)
            L.append(f"  {label} {nkeys}")
            for i, tk in enumerate(times):
                row = values[i] if i < len(values) else []
                # Pad or truncate to ncols
                row = list(row)
                while len(row) < ncols:
                    row.append(0.0)
                row = row[:ncols]
                vals_str = " ".join(f"{v:.6f}" for v in row)
                L.append(f"    {tk:.6f} {vals_str}")

        for ch in node.children:
            self._write_anim_node(ch, L)
        L.append("endnode")
        L.append("")


# ─────────────────────────────  Helpers  ──────────────────────────────

def _ascii_type_to_flags(t: str) -> int:
    t = t.lower()
    base = int(NodeFlags.HEADER)
    if t == 'trimesh':    return base | int(NodeFlags.MESH)
    if t == 'skin':       return base | int(NodeFlags.MESH) | int(NodeFlags.SKIN)
    if t == 'danglymesh': return base | int(NodeFlags.MESH) | int(NodeFlags.DANGLY)
    if t == 'lightsaber': return base | int(NodeFlags.MESH) | int(NodeFlags.SABER)
    if t == 'light':      return base | int(NodeFlags.LIGHT)
    if t == 'emitter':    return base | int(NodeFlags.EMITTER)
    if t == 'reference':  return base | int(NodeFlags.REFERENCE)
    if t == 'aabb':       return base | int(NodeFlags.AABB)
    return base
