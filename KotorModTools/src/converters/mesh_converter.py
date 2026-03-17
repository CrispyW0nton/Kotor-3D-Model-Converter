"""
Mesh Converters
OBJ ↔ KotorModel,  FBX → KotorModel,  KotorModel → OBJ/FBX
TGA ↔ TPC texture conversion
"""

import os, struct, math, logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from ..core.model_data import (
    KotorModel, ModelNode, NodeFlags, GameVersion,
    VertexSkinData, BoneWeight
)

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
#  OBJ Importer
# ──────────────────────────────────────────────────────────────────────

class OBJImporter:
    def import_file(self, obj_path: str,
                    model_name: str = "",
                    game_version: GameVersion = GameVersion.K1,
                    supermodel: str = "NULL",
                    classification: str = "character") -> KotorModel:
        p = Path(obj_path)
        if not model_name: model_name = p.stem[:32]

        model = KotorModel(name=model_name, supermodel=supermodel,
                           game_version=game_version, classification=classification)
        cls_map = {'character':2,'tile':1,'door':4,'effect':0}
        model.model_type = cls_map.get(classification.lower(), 2)

        root = ModelNode(name=model_name, flags=int(NodeFlags.HEADER))
        model.root_node = root

        materials: Dict[str, Dict] = {}
        mtl_path = p.with_suffix('.mtl')
        if mtl_path.exists():
            materials = self._parse_mtl(str(mtl_path))

        all_v:  List[Tuple[float,float,float]] = []
        all_vt: List[Tuple[float,float]]       = []
        all_vn: List[Tuple[float,float,float]] = []

        current_mat  = ""
        current_name = "mesh_0"
        groups: List[Dict] = []
        cur: Optional[Dict] = None

        def flush():
            nonlocal cur
            if cur and cur['faces']: groups.append(cur)
            cur = None

        def new_group(n, m=""):
            nonlocal cur, current_name, current_mat
            flush()
            current_name = n[:32]
            current_mat  = m or current_mat
            cur = {'name': current_name, 'mat': current_mat, 'faces': []}

        with open(obj_path, 'r', encoding='utf-8', errors='replace') as f:
            for raw in f:
                ln = raw.strip()
                if not ln or ln[0]=='#': continue
                t  = ln.split()
                c  = t[0].lower()
                if   c=='v'  and len(t)>=4: all_v.append((float(t[1]),float(t[2]),float(t[3])))
                elif c=='vt' and len(t)>=3: all_vt.append((float(t[1]),1.0-float(t[2])))
                elif c=='vn' and len(t)>=4: all_vn.append((float(t[1]),float(t[2]),float(t[3])))
                elif c in ('g','o') and len(t)>1: new_group(t[1])
                elif c=='usemtl' and len(t)>1:
                    current_mat = t[1]
                    if cur: cur['mat'] = current_mat
                    else:   new_group(f"mesh_{len(groups)}", current_mat)
                elif c=='f':
                    if cur is None: new_group(f"mesh_{len(groups)}")
                    parsed = [self._fv(tok) for tok in t[1:]]
                    for i in range(1, len(parsed)-1):
                        cur['faces'].append([parsed[0], parsed[i], parsed[i+1]])
        flush()

        for gi, g in enumerate(groups):
            if not g['faces']: continue
            node = self._make_node(g, all_v, all_vt, all_vn, materials, gi)
            node.parent = root
            root.children.append(node)

        model.compute_bounds()
        return model

    def _fv(self, tok: str) -> Tuple[int,int,int]:
        p = tok.split('/')
        vi  = int(p[0])-1 if p[0]   else 0
        vti = int(p[1])-1 if len(p)>1 and p[1] else -1
        vni = int(p[2])-1 if len(p)>2 and p[2] else -1
        return vi, vti, vni

    def _make_node(self, g, all_v, all_vt, all_vn, materials, idx) -> ModelNode:
        node = ModelNode(name=g['name'],
                         flags=int(NodeFlags.HEADER|NodeFlags.MESH),
                         index=idx)
        mat = materials.get(g['mat'], {})
        node.texture = mat.get('diff_map', g['mat'])[:32] if g['mat'] else ""
        node.diffuse = mat.get('diffuse', (0.8,0.8,0.8))
        node.ambient = mat.get('ambient', (0.2,0.2,0.2))

        idx_map: Dict[Tuple,int] = {}
        ov: List[Tuple[float,float,float]] = []
        out: List[Tuple[float,float]]       = []
        on: List[Tuple[float,float,float]] = []
        of: List[Tuple[int,int,int]]        = []

        def gi_(vi,vti,vni):
            key = (vi,vti,vni)
            if key in idx_map: return idx_map[key]
            n = len(ov)
            idx_map[key] = n
            ov.append(all_v[vi] if 0<=vi<len(all_v) else (0,0,0))
            out.append(all_vt[vti] if 0<=vti<len(all_vt) else (0,0))
            on.append(all_vn[vni] if 0<=vni<len(all_vn) else (0,0,1))
            return n

        for tri in g['faces']:
            a,b,c = gi_(*tri[0]), gi_(*tri[1]), gi_(*tri[2])
            of.append((a,b,c))

        node.vertices = ov; node.uvs = out
        node.normals  = on if any(x!=(0,0,1) for x in on) else self._flat_normals(ov,of)
        node.faces    = of
        node.compute_bounds()
        return node

    def _flat_normals(self, verts, faces):
        ns = [[0.0,0.0,0.0]] * len(verts)
        cnt= [0] * len(verts)
        for v1,v2,v3 in faces:
            if max(v1,v2,v3) >= len(verts): continue
            ax,ay,az=verts[v1]; bx,by,bz=verts[v2]; cx,cy,cz=verts[v3]
            ux,uy,uz=bx-ax,by-ay,bz-az; vx,vy,vz=cx-ax,cy-ay,cz-az
            nx=uy*vz-uz*vy; ny=uz*vx-ux*vz; nz=ux*vy-uy*vx
            l=math.sqrt(nx*nx+ny*ny+nz*nz) or 1
            nx/=l;ny/=l;nz/=l
            for vi in (v1,v2,v3):
                ns[vi][0]+=nx; ns[vi][1]+=ny; ns[vi][2]+=nz; cnt[vi]+=1
        result = []
        for i,n in enumerate(ns):
            if cnt[i]: l=math.sqrt(sum(x*x for x in n)) or 1; result.append((n[0]/l,n[1]/l,n[2]/l))
            else: result.append((0,0,1))
        return result

    def _parse_mtl(self, path: str) -> Dict[str,Dict]:
        mats: Dict[str,Dict] = {}; cur = None
        with open(path,'r',encoding='utf-8',errors='replace') as f:
            for ln in f:
                t = ln.strip().split()
                if not t: continue
                c = t[0].lower()
                if c=='newmtl' and len(t)>1: cur=t[1]; mats[cur]={}
                elif cur:
                    if   c=='kd' and len(t)>=4: mats[cur]['diffuse']=(float(t[1]),float(t[2]),float(t[3]))
                    elif c=='ka' and len(t)>=4: mats[cur]['ambient']=(float(t[1]),float(t[2]),float(t[3]))
                    elif c=='map_kd' and len(t)>1: mats[cur]['diff_map']=Path(t[-1]).stem[:32]
                    elif c=='map_bump' and len(t)>1: mats[cur]['bump_map']=Path(t[-1]).stem[:32]
        return mats


# ──────────────────────────────────────────────────────────────────────
#  FBX Importer (via pyassimp or trimesh)
# ──────────────────────────────────────────────────────────────────────

class FBXImporter:
    def import_file(self, path: str,
                    model_name: str = "",
                    game_version: GameVersion = GameVersion.K1,
                    supermodel: str = "NULL",
                    classification: str = "character") -> Optional[KotorModel]:
        if not model_name: model_name = Path(path).stem[:32]
        # Try pyassimp first, then trimesh
        try:
            return self._load_assimp(path, model_name, game_version, supermodel, classification)
        except ImportError:
            pass
        try:
            return self._load_trimesh(path, model_name, game_version, supermodel, classification)
        except ImportError:
            pass
        log.error("FBX import: install 'pyassimp' or 'trimesh[easy]'")
        return None

    def _load_assimp(self, path, model_name, gv, sm, cl) -> KotorModel:
        import pyassimp, pyassimp.postprocess as pp
        flags = (pp.aiProcess_Triangulate | pp.aiProcess_GenSmoothNormals |
                 pp.aiProcess_JoinIdenticalVertices | pp.aiProcess_LimitBoneWeights |
                 pp.aiProcess_CalcTangentSpace)
        scene = pyassimp.load(path, processing=flags)
        model = KotorModel(name=model_name, supermodel=sm, game_version=gv, classification=cl)
        root  = ModelNode(name=model_name, flags=int(NodeFlags.HEADER))
        model.root_node = root

        # Skeleton: walk assimp node tree for bone hierarchy
        self._walk_assimp_nodes(scene.rootnode, root, scene)

        pyassimp.release(scene)
        model.compute_bounds()
        return model

    def _walk_assimp_nodes(self, ai_node, parent_node, scene):
        """Recursively mirror the assimp scene graph into KotorModel nodes"""
        import numpy as np
        mat = ai_node.transformation
        # Extract translation from 4x4 matrix (row-major in assimp)
        tx, ty, tz = float(mat[0][3]), float(mat[1][3]), float(mat[2][3])

        node = ModelNode(name=ai_node.name[:32] or "node",
                         flags=int(NodeFlags.HEADER),
                         position=(tx, ty, tz),
                         parent=parent_node)
        parent_node.children.append(node)

        # Check if this node has associated mesh
        for mesh_idx in ai_node.meshes:
            mesh = scene.meshes[mesh_idx]
            mesh_node = self._assimp_mesh(mesh, scene)
            mesh_node.parent = node
            node.children.append(mesh_node)

        for child in ai_node.children:
            self._walk_assimp_nodes(child, node, scene)

    def _assimp_mesh(self, ai_mesh, scene) -> ModelNode:
        is_skin = hasattr(ai_mesh,'bones') and len(ai_mesh.bones)>0
        flags   = int(NodeFlags.HEADER|NodeFlags.MESH)
        if is_skin: flags |= int(NodeFlags.SKIN)

        node = ModelNode(name=ai_mesh.name[:32] or "mesh", flags=flags)
        node.vertices = [(float(v[0]),float(v[1]),float(v[2])) for v in ai_mesh.vertices]
        if len(ai_mesh.normals):
            node.normals = [(float(n[0]),float(n[1]),float(n[2])) for n in ai_mesh.normals]
        if len(ai_mesh.texturecoords) and len(ai_mesh.texturecoords[0]):
            node.uvs = [(float(u[0]),1.0-float(u[1])) for u in ai_mesh.texturecoords[0]]
        node.faces = [(int(f.indices[0]),int(f.indices[1]),int(f.indices[2])) for f in ai_mesh.faces]

        # Material
        if scene.materials and ai_mesh.materialindex < len(scene.materials):
            mat = scene.materials[ai_mesh.materialindex]
            for prop in mat.properties:
                k = prop.key.lower()
                if '$tex.file' in k and '1,0' in k:
                    node.texture = Path(str(prop.data)).stem[:32]
                elif '$clr.diffuse' in k:
                    d = prop.data
                    node.diffuse = (float(d[0]),float(d[1]),float(d[2]))

        # Skin
        if is_skin:
            n_verts = len(node.vertices)
            wt = [[BoneWeight(0,0.0)]*4 for _ in range(n_verts)]
            sc = [0]*n_verts
            node.bone_map = []
            for bi, bone in enumerate(ai_mesh.bones):
                node.bone_map.append(bone.name[:32])
                for w in bone.weights:
                    vi = w.vertexid
                    if vi < n_verts and sc[vi] < 4:
                        wt[vi][sc[vi]] = BoneWeight(bi, w.weight); sc[vi]+=1
            node.skin_data = [VertexSkinData(influences=[b for b in row if b.weight>0]) for row in wt]

        node.compute_bounds()
        return node

    def _load_trimesh(self, path, model_name, gv, sm, cl) -> KotorModel:
        import trimesh
        scene = trimesh.load(path)
        model = KotorModel(name=model_name, supermodel=sm, game_version=gv, classification=cl)
        root  = ModelNode(name=model_name, flags=int(NodeFlags.HEADER))
        model.root_node = root
        geoms = scene.geometry if hasattr(scene,'geometry') else {model_name:scene}
        for gname, mesh in geoms.items():
            n = ModelNode(name=gname[:32], flags=int(NodeFlags.HEADER|NodeFlags.MESH), parent=root)
            n.vertices = [tuple(v) for v in mesh.vertices.tolist()]
            n.faces    = [tuple(f) for f in mesh.faces.tolist()]
            if hasattr(mesh,'vertex_normals') and mesh.vertex_normals is not None:
                n.normals = [tuple(x) for x in mesh.vertex_normals.tolist()]
            if hasattr(mesh,'visual') and hasattr(mesh.visual,'uv') and mesh.visual.uv is not None:
                n.uvs = [(float(u),1.0-float(v)) for u,v in mesh.visual.uv.tolist()]
            n.compute_bounds()
            root.children.append(n)
        model.compute_bounds()
        return model


# ──────────────────────────────────────────────────────────────────────
#  KotorModel → OBJ Exporter
# ──────────────────────────────────────────────────────────────────────

class OBJExporter:
    def export(self, model: KotorModel, obj_path: str):
        p = Path(obj_path); mp = p.with_suffix('.mtl')
        obj_lines = [f"# KotorModTools export – {model.name}", f"mtllib {mp.name}", ""]
        mtl_lines = ["# KotorModTools materials", ""]; seen_mats = set()

        vo = vto = vno = 0
        for node in model.mesh_nodes():
            if not node.vertices: continue
            obj_lines.append(f"o {node.name}")
            for x,y,z in node.vertices: obj_lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")
            for u,v  in node.uvs:       obj_lines.append(f"vt {u:.6f} {1-v:.6f}")
            for x,y,z in node.normals:  obj_lines.append(f"vn {x:.6f} {y:.6f} {z:.6f}")
            if node.texture:
                obj_lines.append(f"usemtl {node.texture}")
                if node.texture not in seen_mats:
                    seen_mats.add(node.texture)
                    r,g,b=node.diffuse; ar,ag,ab=node.ambient
                    mtl_lines+=[f"newmtl {node.texture}",
                                 f"Ka {ar:.4f} {ag:.4f} {ab:.4f}",
                                 f"Kd {r:.4f} {g:.4f} {b:.4f}",
                                 f"map_Kd {node.texture}.tga",""]
            huv = bool(node.uvs); hn = bool(node.normals)
            for v1,v2,v3 in node.faces:
                def fi(v, o): return v+1+o
                if huv and hn:
                    obj_lines.append(f"f {fi(v1,vo)}/{fi(v1,vto)}/{fi(v1,vno)} "
                                     f"{fi(v2,vo)}/{fi(v2,vto)}/{fi(v2,vno)} "
                                     f"{fi(v3,vo)}/{fi(v3,vto)}/{fi(v3,vno)}")
                elif huv:
                    obj_lines.append(f"f {fi(v1,vo)}/{fi(v1,vto)} "
                                     f"{fi(v2,vo)}/{fi(v2,vto)} "
                                     f"{fi(v3,vo)}/{fi(v3,vto)}")
                else:
                    obj_lines.append(f"f {fi(v1,vo)} {fi(v2,vo)} {fi(v3,vo)}")
            obj_lines.append("")
            vo  += len(node.vertices)
            vto += len(node.uvs)
            vno += len(node.normals)

        Path(obj_path).write_text('\n'.join(obj_lines))
        mp.write_text('\n'.join(mtl_lines))
        log.info(f"Exported OBJ → {obj_path}")


# ──────────────────────────────────────────────────────────────────────
#  FBX Exporter (via pyassimp or fbx SDK)
# ──────────────────────────────────────────────────────────────────────

class FBXExporter:
    """
    Export KotorModel to FBX.
    Uses pyassimp export if available, otherwise falls back to OBJ
    with a note to convert externally.
    """
    def export(self, model: KotorModel, fbx_path: str) -> bool:
        try:
            import pyassimp
            return self._export_assimp(model, fbx_path)
        except ImportError:
            pass
        # Fallback: export as OBJ and inform user
        obj_path = str(Path(fbx_path).with_suffix('.obj'))
        log.warning("FBX export requires pyassimp. Exporting as OBJ instead.")
        OBJExporter().export(model, obj_path)
        return False

    def _export_assimp(self, model: KotorModel, fbx_path: str) -> bool:
        try:
            import pyassimp
            scene = pyassimp.core.AssimpLib()
            # pyassimp export is complex – use OBJ for now
            obj_path = str(Path(fbx_path).with_suffix('.obj'))
            OBJExporter().export(model, obj_path)
            log.info(f"Note: FBX export via pyassimp not yet fully implemented. Saved as OBJ: {obj_path}")
            return False
        except Exception as e:
            log.error(f"FBX export failed: {e}")
            return False


# ──────────────────────────────────────────────────────────────────────
#  TGA ↔ TPC Texture Converter
# ──────────────────────────────────────────────────────────────────────

TPC_GREY = 1; TPC_RGB = 2; TPC_RGBA = 4; TPC_DXT1 = 12; TPC_DXT5 = 14
TPC_HDR  = 128

def tga_to_tpc(tga_path: str, tpc_path: str, txi_str: str = "", mipmaps: bool = True) -> bool:
    try:
        with open(tga_path,'rb') as f: raw = f.read()
        id_len,cm_type,img_type = struct.unpack_from('<BBB',raw,0)
        w,h = struct.unpack_from('<HH',raw,12)
        bpp = raw[16]
        desc= raw[17]
        off = 18 + id_len

        # Handle RLE-compressed TGA (types 9,10,11)
        is_rle = img_type in (9,10,11)
        is_bw  = img_type in (3,11)

        if is_rle:
            px = bpp//8; total = w*h
            pxdata = bytearray()
            pos = off
            while len(pxdata) < total*px and pos < len(raw):
                rep = raw[pos]; pos+=1
                if rep & 0x80:  # run
                    cnt = (rep&0x7F)+1
                    p   = raw[pos:pos+px]; pos+=px
                    pxdata.extend(p*cnt)
                else:           # raw
                    cnt = rep+1
                    pxdata.extend(raw[pos:pos+cnt*px]); pos+=cnt*px
            pixel_data = bytes(pxdata)
        else:
            pixel_data = raw[off:]

        # Flip vertically if origin is top-left (bit 5 of descriptor = 0 means bottom-left)
        row_sz = w * (bpp//8)
        rows   = [pixel_data[i*row_sz:(i+1)*row_sz] for i in range(h)]
        if not (desc & 0x20):  # bottom-left origin
            rows = list(reversed(rows))
        pixel_data = b''.join(rows)

        # Convert BGR(A) → RGB(A) and determine TPC encoding
        px = bpp//8
        converted = bytearray()
        if bpp == 32:
            for i in range(0, len(pixel_data), 4):
                b,g,r,a = pixel_data[i],pixel_data[i+1],pixel_data[i+2],pixel_data[i+3]
                converted.extend([r,g,b,a])
            enc = TPC_RGBA
        elif bpp == 24:
            for i in range(0, len(pixel_data), 3):
                b,g,r = pixel_data[i],pixel_data[i+1],pixel_data[i+2]
                converted.extend([r,g,b])
            enc = TPC_RGB
        elif bpp == 8:
            converted.extend(pixel_data); enc = TPC_GREY
        else:
            return False

        # Build mip chain
        mips = [bytes(converted)]
        if mipmaps:
            mips = _gen_mips(bytes(converted), w, h, bpp//8)

        # TPC header (128 bytes)
        total_sz = sum(len(m) for m in mips)
        hdr = bytearray(TPC_HDR)
        struct.pack_into('<I',hdr,0,total_sz)
        struct.pack_into('<H',hdr,8,w)
        struct.pack_into('<H',hdr,10,h)
        hdr[12] = enc
        hdr[13] = len(mips)

        with open(tpc_path,'wb') as f:
            f.write(hdr)
            for m in mips: f.write(m)
            if txi_str: f.write(txi_str.encode('ascii'))
        return True
    except Exception as e:
        log.error(f"TGA→TPC failed: {e}")
        return False


def tpc_to_tga(tpc_path: str, tga_path: str) -> bool:
    try:
        with open(tpc_path,'rb') as f: data = f.read()
        data_sz = struct.unpack_from('<I',data,0)[0]
        w,h     = struct.unpack_from('<H',data,8)[0], struct.unpack_from('<H',data,10)[0]
        enc     = data[12]
        mips    = data[13]

        off = TPC_HDR
        bpp = {TPC_GREY:1, TPC_RGB:3, TPC_RGBA:4}.get(enc)
        if bpp is None:
            log.error(f"DXT decompression not supported in standalone mode")
            return False

        pixel_data = data[off:off+w*h*bpp]

        # RGB(A) → BGR(A)
        converted = bytearray()
        if bpp == 4:
            for i in range(0,len(pixel_data),4):
                r,g,b,a=pixel_data[i],pixel_data[i+1],pixel_data[i+2],pixel_data[i+3]
                converted.extend([b,g,r,a])
            img_type=2; tga_bpp=32
        elif bpp == 3:
            for i in range(0,len(pixel_data),3):
                r,g,b=pixel_data[i],pixel_data[i+1],pixel_data[i+2]
                converted.extend([b,g,r])
            img_type=2; tga_bpp=24
        else:
            converted.extend(pixel_data); img_type=3; tga_bpp=8

        hdr = struct.pack('<BBBHHHHHHHBB',0,0,img_type,0,0,0,0,0,w,h,tga_bpp,0x20)
        with open(tga_path,'wb') as f:
            f.write(hdr); f.write(bytes(converted))
        return True
    except Exception as e:
        log.error(f"TPC→TGA failed: {e}"); return False


def _gen_mips(data: bytes, w: int, h: int, bpp: int) -> List[bytes]:
    mips = [data]
    cur = bytearray(data)
    cw, ch = w, h
    while cw > 1 or ch > 1:
        nw, nh = max(1,cw>>1), max(1,ch>>1)
        nxt = bytearray(nw*nh*bpp)
        for y in range(nh):
            for x in range(nw):
                for c in range(bpp):
                    s = []
                    for dy in range(2):
                        for dx in range(2):
                            sx=min(x*2+dx,cw-1); sy=min(y*2+dy,ch-1)
                            s.append(cur[(sy*cw+sx)*bpp+c])
                    nxt[(y*nw+x)*bpp+c] = sum(s)//4
        mips.append(bytes(nxt)); cur=nxt; cw,ch=nw,nh
    return mips
