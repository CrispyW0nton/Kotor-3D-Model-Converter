"""
MDL Binary Parser  – reads KotOR 1 & 2 .mdl + .mdx files
MDL ASCII Parser   – reads decompiled text MDL (mdlops output)
MDL ASCII Writer   – writes text MDL for mdlops compilation
MDL Binary Writer  – writes binary MDL + MDX
"""

import struct, math, logging, os
from typing import List, Optional, Dict, Tuple
from pathlib import Path
from .model_data import (
    KotorModel, ModelNode, NodeFlags, GameVersion, Animation, AnimEvent,
    VertexSkinData, BoneWeight
)

log = logging.getLogger(__name__)

# ─────────────────────────────  Helper  ──────────────────────────────

def _rstrip(b: bytes) -> str:
    return b.rstrip(b'\x00').decode('ascii', errors='replace')

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
    """
    BASE = 12

    def __init__(self, mdl: bytes, mdx: bytes):
        self.mdl = mdl
        self.mdx = mdx
        self._names: List[str] = []
        self._cache: Dict[int, ModelNode] = {}
        self.model = KotorModel()

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

        # Detect game version
        if   fp1 in (4273776, 4273392): self.model.game_version = GameVersion.K1
        elif fp1 in (4285200, 4284816): self.model.game_version = GameVersion.K2
        else:                           self.model.game_version = GameVersion.K1

        # Model header at offset B+80 (88 bytes)
        M = B + 80
        self.model.model_type = struct.unpack_from('B', d, M)[0]
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
        if root_node_off:
            self.model.root_node = self._parse_node(B + root_node_off, None)

        self.model.compute_bounds()
        return self.model

    # ── Node parser  ────────────────────────────────────────────────────────

    def _parse_node(self, abs_off: int, parent: Optional[ModelNode]) -> ModelNode:
        if abs_off in self._cache:
            return self._cache[abs_off]

        d = self.mdl
        o = abs_off

        node_type  = _ru16(d, o);    o+=2
        index_num  = _ru16(d, o);    o+=2
        node_num   = _ru16(d, o);    o+=2
        pad        = _ru16(d, o);    o+=2
        root_off   = _ru32(d, o);    o+=4
        parent_off = _ru32(d, o);    o+=4
        px,py,pz   = struct.unpack_from('<fff', d, o); o+=12
        rx,ry,rz,rw= struct.unpack_from('<ffff',d, o); o+=16
        child_arr_off  = _ru32(d, o); o+=4
        child_cnt      = _ru32(d, o); o+=4
        child_cnt2     = _ru32(d, o); o+=4
        ctrl_arr_off   = _ru32(d, o); o+=4
        ctrl_cnt       = _ru32(d, o); o+=4
        ctrl_cnt2      = _ru32(d, o); o+=4
        ctrl_data_off  = _ru32(d, o); o+=4
        ctrl_data_cnt  = _ru32(d, o); o+=4
        ctrl_data_cnt2 = _ru32(d, o); o+=4

        name = self._names[index_num] if 0 <= index_num < len(self._names) else f"node_{index_num}"

        node = ModelNode(
            name=name, flags=node_type, index=index_num, number=node_num,
            position=(px,py,pz), rotation=(rx,ry,rz,rw), parent=parent
        )
        self._cache[abs_off] = node

        # Parse mesh data
        if node_type & NodeFlags.MESH:
            self._parse_mesh(node, o)

        # Children
        B = self.BASE
        for i in range(min(child_cnt, 512)):
            ptr = B + child_arr_off + i*4
            if ptr+4 > len(d): break
            c_off = _ru32(d, ptr)
            if c_off == 0: continue
            child = self._parse_node(B + c_off, node)
            if child not in node.children:
                node.children.append(child)

        return node

    def _parse_mesh(self, node: ModelNode, off: int):
        d   = self.mdl
        mdx = self.mdx
        B   = self.BASE
        o   = off

        # Skip 2 func ptrs
        fp1 = _ru32(d,o); o+=4
        fp2 = _ru32(d,o); o+=4

        faces_off   = _ru32(d,o); o+=4
        faces_cnt   = _ru32(d,o); o+=4
        faces_cnt2  = _ru32(d,o); o+=4

        # bounding box
        bx1,by1,bz1 = struct.unpack_from('<fff',d,o); o+=12
        bx2,by2,bz2 = struct.unpack_from('<fff',d,o); o+=12
        radius       = struct.unpack_from('<f',d,o)[0]; o+=4
        avg          = struct.unpack_from('<fff',d,o);  o+=12

        dr,dg,db = struct.unpack_from('<fff',d,o); o+=12
        ar,ag,ab = struct.unpack_from('<fff',d,o); o+=12
        transp   = _ru32(d,o); o+=4
        tex_name = _rstrip(d[o:o+32]); o+=32
        lm_name  = _rstrip(d[o:o+32]); o+=32
        o += 24  # unknown

        vic_off  = _ru32(d,o); o+=4
        vic_cnt  = _ru32(d,o); o+=4
        vic_cnt2 = _ru32(d,o); o+=4
        vo_off   = _ru32(d,o); o+=4
        vo_cnt   = _ru32(d,o); o+=4
        vo_cnt2  = _ru32(d,o); o+=4
        inv_off  = _ru32(d,o); o+=4
        inv_cnt  = _ru32(d,o); o+=4
        inv_cnt2 = _ru32(d,o); o+=4
        o += 12  # {-1,-1,0}
        o +=  8  # saber vals
        o +=  4  # unknown
        o += 16  # 4 floats

        mdx_data_size   = _ru32(d,o); o+=4
        mdx_data_bitmap = _ru32(d,o); o+=4
        mdx_v_off       = _ru32(d,o); o+=4   # verts   in MDX (usually 0)
        mdx_n_off       = _ru32(d,o); o+=4   # normals
        mdx_vc_off      = _ru32(d,o); o+=4   # vertex colors
        mdx_t1_off      = _ru32(d,o); o+=4   # tex UV1
        mdx_lm_off      = _ru32(d,o); o+=4   # lightmap UV
        mdx_t2_off      = _ru32(d,o); o+=4
        mdx_t3_off      = _ru32(d,o); o+=4
        mdx_bmp_off     = _ru32(d,o); o+=4   # bump
        o += 16  # 4 more unknowns

        vert_cnt   = _ru16(d,o); o+=2
        tex_cnt    = _ru16(d,o); o+=2
        has_lm     = struct.unpack_from('B',d,o)[0]; o+=1
        rot_tex    = struct.unpack_from('B',d,o)[0]; o+=1
        bg_geo     = struct.unpack_from('B',d,o)[0]; o+=1
        has_shadow = struct.unpack_from('B',d,o)[0]; o+=1
        beaming    = struct.unpack_from('B',d,o)[0]; o+=1
        has_render = struct.unpack_from('B',d,o)[0]; o+=1
        o += 2   # unknowns
        total_area = struct.unpack_from('<f',d,o)[0]; o+=4
        o += 4   # unknown

        if self.model.game_version == GameVersion.K2:
            o += 8  # 2 extra K2 unknowns

        mdx_data_off = _ru32(d,o); o+=4
        verts_off    = _ru32(d,o); o+=4

        node.texture      = tex_name
        node.lightmap     = lm_name
        node.diffuse      = (dr,dg,db)
        node.ambient      = (ar,ag,ab)
        node.has_shadow   = bool(has_shadow)
        node.render       = bool(has_render)
        node.has_lightmap = bool(has_lm)
        node.beaming      = bool(beaming)
        node.transparency_hint = transp
        node.bb_min = (bx1,by1,bz1)
        node.bb_max = (bx2,by2,bz2)

        # ── Read vertex positions from MDL ──────────────────────────────────
        if vert_cnt > 0 and verts_off > 0:
            va = B + verts_off
            for i in range(min(vert_cnt, 65535)):
                p = va + i*12
                if p+12 > len(d): break
                node.vertices.append(struct.unpack_from('<fff',d,p))

        # ── Read vertex channels from MDX ───────────────────────────────────
        if vert_cnt > 0 and mdx_data_size > 0 and mdx_data_off < len(mdx):
            stride = mdx_data_size
            for i in range(min(vert_cnt, 65535)):
                base = mdx_data_off + i*stride
                # normals
                if mdx_n_off != 0xFFFFFFFF and base+mdx_n_off+12 <= len(mdx):
                    node.normals.append(struct.unpack_from('<fff',mdx,base+mdx_n_off))
                # tex UV1
                if mdx_t1_off != 0xFFFFFFFF and base+mdx_t1_off+8 <= len(mdx):
                    node.uvs.append(struct.unpack_from('<ff',mdx,base+mdx_t1_off))
                # lightmap UV
                if mdx_lm_off != 0xFFFFFFFF and base+mdx_lm_off+8 <= len(mdx):
                    node.uvs_lm.append(struct.unpack_from('<ff',mdx,base+mdx_lm_off))

        # ── Read faces ──────────────────────────────────────────────────────
        if faces_cnt > 0 and faces_off > 0:
            fa = B + faces_off
            for i in range(min(faces_cnt, 65535)):
                p = fa + i*32
                if p+32 > len(d): break
                # face: normal(fff) planeco(f) mat(I) adj(3H) verts(3H)
                nx,ny,nz,pc,mat = struct.unpack_from('<ffffi',d,p)
                v1,v2,v3 = struct.unpack_from('<HHH',d,p+24)
                node.faces.append((v1,v2,v3))
                node.face_mats.append(mat)

        # ── Skin weights ────────────────────────────────────────────────────
        if node.flags & NodeFlags.SKIN:
            self._parse_skin(node, o, vert_cnt, mdx_data_off, mdx_data_size, mdx)

    def _parse_skin(self, node, skin_hdr_off, vert_cnt, mdx_data_off, mdx_data_size, mdx):
        d = self.mdl; B = self.BASE; o = skin_hdr_off
        try:
            o += 12   # compile weight array (3 ints)
            sw_off = _ru32(d,o); o+=4   # MDX skin weights offset within MDX vertex
            sbr_off= _ru32(d,o); o+=4   # MDX bone ref offset within MDX vertex
            bm_off = _ru32(d,o); o+=4   # MDL bones map offset
            bm_cnt = _ru32(d,o); o+=4
            # Read bone map
            bm_abs = B + bm_off
            for i in range(min(bm_cnt, 256)):
                p = bm_abs + i*2
                if p+2 <= len(d):
                    node.bone_map.append(_ru16(d,p))
            # Read per-vertex weights from MDX
            stride = mdx_data_size if mdx_data_size else 32
            for i in range(min(vert_cnt, 65535)):
                base = mdx_data_off + i*stride
                sd = VertexSkinData()
                if sw_off != 0xFFFFFFFF and base+sw_off+16 <= len(mdx):
                    wts = struct.unpack_from('<ffff',mdx,base+sw_off)
                    brs = struct.unpack_from('<ffff',mdx,base+sbr_off) if sbr_off != 0xFFFFFFFF else (0,0,0,0)
                    for j in range(4):
                        if wts[j] > 0:
                            sd.influences.append(BoneWeight(int(brs[j]), wts[j]))
                node.skin_data.append(sd)
        except Exception as e:
            log.debug(f"Skin parse error on {node.name}: {e}")


# ─────────────────────────────  ASCII Parser  ──────────────────────────────

class MDLAsciiParser:
    """Parses the text-format ASCII MDL produced by MDLOps"""

    def parse_file(self, path: str) -> KotorModel:
        with open(path, 'r', encoding='ascii', errors='replace') as f:
            return self.parse(f.readlines())

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
                if model.root_node is None:
                    model.root_node = node
            elif cmd == 'donemodel': break
            self._pos += 1

        # map classification to model_type
        cls_map = {'character':2,'tile':1,'door':4,'effect':0}
        model.model_type = cls_map.get(model.classification, 2)
        model.compute_bounds()
        return model

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
                self._stack.pop(); return node

            elif cmd == 'parent':    pass
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
                count = int(t[1]); self._pos+=1
                for _ in range(count):
                    ft = self._tok()
                    if len(ft)>=3:
                        node.faces.append((int(ft[0]),int(ft[1]),int(ft[2])))
                    self._pos+=1
                continue

            elif cmd == 'constraints' and len(t)>1:
                count = int(t[1]); self._pos+=1
                for _ in range(count):
                    ct = self._tok()
                    if ct: node.dangly_constraints.append(float(ct[0]))
                    self._pos+=1
                continue

            elif cmd == 'node' and len(t)>=3:
                self._parse_node_block(t[1], t[2])

            self._pos += 1
        return node


# ─────────────────────────────  ASCII Writer  ──────────────────────────────

class MDLAsciiWriter:
    """Writes ASCII MDL ready for MDLOps compilation"""

    def write(self, model: KotorModel, path: str):
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
            L.append(f"  constraints {len(n.dangly_constraints)}")
            for c in n.dangly_constraints: L.append(f"    {c:.4f}")

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
            self._write_node(node, L)
        L.append(f"doneanim {anim.name} {model_name}")
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
