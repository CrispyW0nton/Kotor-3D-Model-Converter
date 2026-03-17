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
    VertexSkinData, BoneWeight,
    _quat_rotate, _quat_conjugate, _quat_normalize_bind, _quat_normalize, _quat_mul
)

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
#  OBJ Importer
# ──────────────────────────────────────────────────────────────────────

class OBJImporter:
    def import_obj(self, obj_path: str,
                   model_name: str = "",
                   game_version: GameVersion = GameVersion.K1,
                   supermodel: str = "NULL",
                   classification: str = "character") -> KotorModel:
        """Alias for import_file() – backward compatible."""
        return self.import_file(obj_path, model_name, game_version, supermodel, classification)

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
    """
    Export KotorModel to OBJ + MTL.

    KotOR UV convention: V is stored bottom-up (OpenGL style, 0=bottom, 1=top).
    OBJ format stores V the same way but Blender displays UVs with Y-up, so we
    flip V on export: vt_out = 1.0 - v_kotor.

    Only *renderable* nodes are exported:
      - Nodes with ``render=False`` are invisible engine-internal nodes (collision
        proxies, occluders, camera helpers) and are never exported.
      - Deformation-helper trimeshes (texture='null', extreme UVs, _g/_dum suffix)
        are skipped; they are used by the engine's SkinMesh pipeline and do not
        represent visible geometry.
    """

    # ── Helpers that mirror the viewport's _is_deformation_helper logic ──────

    @staticmethod
    def _clean_tex(name: str) -> str:
        """Return printable ASCII tex name, stripped."""
        if not name:
            return ''
        cleaned = ''.join(c for c in name if 32 <= ord(c) < 127)
        return cleaned.strip()

    @classmethod
    def _is_deformation_helper(cls, node) -> bool:
        """
        Return True if this mesh node is a hidden deformation-helper that
        should NOT appear in the exported OBJ.  Mirrors the logic in
        viewport.py::FrameRenderer._is_deformation_helper.
        """
        tex = cls._clean_tex(getattr(node, 'texture', '') or '')
        is_null_tex = (not tex or tex.upper() == 'NULL')
        is_skin = getattr(node, 'is_skin', False)
        uvs = getattr(node, 'uvs', []) or []

        # Skin node with a real texture and valid (non-extreme) UVs → visible
        if is_skin and not is_null_tex and uvs:
            if not any(abs(u) > 3.0 or abs(v) > 3.0 for u, v in uvs[:20]):
                return False

        # Extreme UV coordinates → always a deform helper
        if uvs and any(abs(u) > 3.0 or abs(v) > 3.0 for u, v in uvs[:20]):
            return True

        # Non-skin _g / _G / _dum nodes → always helpers
        name_lower = getattr(node, 'name', '').lower()
        if not is_skin and (name_lower.endswith('_g')
                            or name_lower.endswith('_g0')
                            or name_lower.endswith('_dum')):
            return True

        # Null-texture non-skin nodes → helpers
        if is_null_tex and not is_skin:
            return True

        # Null-texture skin nodes with no/zero UVs → helpers
        if is_null_tex and is_skin and (not uvs
                or all(u == 0.0 and v == 0.0 for u, v in uvs[:5])):
            return True

        return False

    @classmethod
    def _is_renderable(cls, node) -> bool:
        """
        Return True if the node should be included in the OBJ export.

        Criteria (must ALL pass):
          1. Has vertices.
          2. render flag is not explicitly False.
          3. Not a deformation helper.
          4. Not an emitter or light node (no visible geometry).
        """
        if not getattr(node, 'vertices', None):
            return False
        if not getattr(node, 'render', True):
            return False
        if getattr(node, 'is_emitter', False) or getattr(node, 'is_light', False):
            return False
        if cls._is_deformation_helper(node):
            return False
        return True

    # ── Bind-pose world-space transform helpers ──────────────────────────────

    @staticmethod
    def _node_bind_world_verts(node) -> List[Tuple[float, float, float]]:
        """
        Return vertices transformed to bind-pose world space.

        For skin nodes (is_skin=True) the vertices are stored in skin-node-local
        space.  The bind-pose world position is:

            v_world = rotate(skin_wo, v_local) + skin_wp

        where (skin_wp, skin_wo) is the node's world transform from
        ModelNode.world_transform().  When the skin-node rotation is the
        identity quaternion (the common case) this simplifies to:

            v_world = v_local + skin_wp

        For non-skin trimesh nodes the same formula applies, but the node's own
        rotation is *not* collapsed (see model_data.world_transform leaf-node
        handling), so the full rotation is applied to vertex positions.

        NOTE: This does NOT apply Linear Blend Skinning — it produces the
        correct bind-pose shape only for nodes whose vertex data is already
        stored in world/model space (simple non-skin meshes) OR for skin nodes
        whose raw vertex data represents bind-pose local coords that need only
        the skin node's world translation applied.  For c_bosdrexl and similar
        creatures the skin vertices ARE in node-local space and their correct
        placement requires this world-space offset.
        """
        verts = node.vertices or []
        if not verts:
            return []

        wp, wo = node.world_transform()
        wo_rot = math.sqrt(wo[0]**2 + wo[1]**2 + wo[2]**2)
        is_id = wo_rot < 0.001

        if is_id:
            return [(v[0] + wp[0], v[1] + wp[1], v[2] + wp[2]) for v in verts]
        else:
            result = []
            for v in verts:
                rv = _quat_rotate(wo, v)
                result.append((rv[0] + wp[0], rv[1] + wp[1], rv[2] + wp[2]))
            return result

    @staticmethod
    def _node_bind_world_normals(node) -> List[Tuple[float, float, float]]:
        """
        Return normals rotated by the node's bind-pose world rotation.
        Normals are direction vectors — translate only applies to positions, not
        directions, so only the rotation component is applied.
        """
        normals = node.normals or []
        if not normals:
            return []

        _wp, wo = node.world_transform()
        wo_rot = math.sqrt(wo[0]**2 + wo[1]**2 + wo[2]**2)
        is_id = wo_rot < 0.001

        if is_id:
            return list(normals)   # no rotation to apply
        else:
            return [_quat_rotate(wo, n) for n in normals]

    def export(self, model: KotorModel, obj_path: str):
        p = Path(obj_path); mp = p.with_suffix('.mtl')
        obj_lines = [f"# GhostRigger-K1-K2 export – {model.name}", f"mtllib {mp.name}", ""]
        mtl_lines = ["# GhostRigger-K1-K2 materials", ""]
        seen_mats: set = set()

        # Count skipped nodes for the header comment
        all_mesh  = list(model.mesh_nodes())
        renderable = [n for n in all_mesh if self._is_renderable(n)]
        skipped_render = sum(1 for n in all_mesh if not getattr(n, 'render', True))
        skipped_helper = sum(1 for n in all_mesh if getattr(n, 'render', True)
                             and self._is_deformation_helper(n)
                             and getattr(n, 'vertices', None))
        obj_lines.insert(1,
            f"# mesh nodes total={len(all_mesh)}  "
            f"exported={len(renderable)}  "
            f"skipped_render_false={skipped_render}  "
            f"skipped_deform_helpers={skipped_helper}")

        vo = vto = vno = 0
        for node in renderable:
            # Apply bind-pose world transform so vertices are in model/world space.
            # This is essential for skin nodes: KotOR stores skin vertices in
            # node-local space; without this offset, body-segment nodes like
            # Rwing_06 on c_bosdrexl appear displaced far from the creature body.
            world_verts   = self._node_bind_world_verts(node)
            world_normals = self._node_bind_world_normals(node)

            nv  = len(world_verts)
            nuv = len(node.uvs)
            nno = len(world_normals)

            obj_lines.append(f"o {node.name}")
            obj_lines.append(f"# verts={nv} uvs={nuv} normals={nno} faces={len(node.faces)}")

            for x, y, z in world_verts:
                obj_lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")

            # Write UVs – KotOR stores V bottom-up, OBJ convention is same.
            # We flip V here so that the exported file looks correct in Blender
            # (which loads UVs as-is and uses OpenGL convention Y-up).
            for u,v in node.uvs:
                obj_lines.append(f"vt {u:.6f} {(1.0 - v):.6f}")

            for x, y, z in world_normals:
                obj_lines.append(f"vn {x:.6f} {y:.6f} {z:.6f}")

            # Material – filter out 'null' placeholder textures
            raw_tex  = getattr(node, 'texture_clean', '') or getattr(node, 'texture', '') or ''
            tex_name = self._clean_tex(raw_tex)
            if tex_name.upper() in ('NULL', 'BLACK', ''):
                tex_name = ''
            mat_name = tex_name if tex_name else node.name
            obj_lines.append(f"usemtl {mat_name}")
            if mat_name not in seen_mats:
                seen_mats.add(mat_name)
                r,g,b   = node.diffuse
                ar,ag,ab = node.ambient
                sr,sg,sb = node.specular
                mtl_lines += [
                    f"newmtl {mat_name}",
                    f"Ka {ar:.4f} {ag:.4f} {ab:.4f}",
                    f"Kd {r:.4f} {g:.4f} {b:.4f}",
                    f"Ks {sr:.4f} {sg:.4f} {sb:.4f}",
                    f"Ns {max(node.shininess, 0.0):.2f}",
                    f"d  {node.alpha:.4f}",
                ]
                if tex_name:
                    mtl_lines.append(f"map_Kd {tex_name}.tga")
                mtl_lines.append("")

            # Faces: emit f v/vt/vn triples; clamp UV and normal indices safely
            huv = (nuv > 0)
            hn  = (nno > 0)
            obj_lines.append("s 1")  # smoothing group

            # Snapshot current global offsets to avoid closure capture issues
            _vo, _vto, _vno = vo, vto, vno

            for v1, v2, v3 in node.faces:
                if max(v1, v2, v3) >= nv:
                    continue   # skip degenerate faces with out-of-range indices

                if huv and hn:
                    ui1 = min(v1, nuv-1); ui2 = min(v2, nuv-1); ui3 = min(v3, nuv-1)
                    ni1 = min(v1, nno-1); ni2 = min(v2, nno-1); ni3 = min(v3, nno-1)
                    obj_lines.append(
                        f"f {v1+1+_vo}/{ui1+1+_vto}/{ni1+1+_vno} "
                        f"{v2+1+_vo}/{ui2+1+_vto}/{ni2+1+_vno} "
                        f"{v3+1+_vo}/{ui3+1+_vto}/{ni3+1+_vno}")
                elif huv:
                    ui1 = min(v1, nuv-1); ui2 = min(v2, nuv-1); ui3 = min(v3, nuv-1)
                    obj_lines.append(
                        f"f {v1+1+_vo}/{ui1+1+_vto} "
                        f"{v2+1+_vo}/{ui2+1+_vto} "
                        f"{v3+1+_vo}/{ui3+1+_vto}")
                elif hn:
                    ni1 = min(v1, nno-1); ni2 = min(v2, nno-1); ni3 = min(v3, nno-1)
                    obj_lines.append(
                        f"f {v1+1+_vo}//{ni1+1+_vno} "
                        f"{v2+1+_vo}//{ni2+1+_vno} "
                        f"{v3+1+_vo}//{ni3+1+_vno}")
                else:
                    obj_lines.append(
                        f"f {v1+1+_vo} {v2+1+_vo} {v3+1+_vo}")

            obj_lines.append("")
            vo  += nv
            vto += nuv
            vno += nno

        Path(obj_path).write_text('\n'.join(obj_lines), encoding='utf-8')
        mp.write_text('\n'.join(mtl_lines), encoding='utf-8')
        log.info(f"Exported OBJ → {obj_path}  "
                 f"({vo} verts, {len(renderable)}/{len(all_mesh)} mesh nodes exported)")


def _renderable_mesh_nodes(model: KotorModel):
    """
    Return a list of mesh nodes from *model* that represent renderable geometry.
    This is the same filter used by OBJExporter and the viewport's
    _iter_visible_mesh_nodes().  Shared by OBJExporter and FBXExporter so both
    produce identical output meshes.
    """
    return [n for n in model.mesh_nodes() if OBJExporter._is_renderable(n)]


# ──────────────────────────────────────────────────────────────────────
#  FBX Exporter (via pyassimp or fbx SDK)
# ──────────────────────────────────────────────────────────────────────

class FBXExporter:
    """
    Export KotorModel to FBX.

    Strategy (priority order):
      1. If `fbx-python-sdk` (fbx module) is available: use it for proper binary FBX.
      2. If `pyassimp` is available: use assimp export pipeline.
      3. Fallback: write FBX ASCII 7.4 format manually (no external deps).
         This is readable by Blender, Maya, 3ds Max and most DCC tools.
         Includes full mesh geometry, UV, normals, skinning (bind pose +
         skin cluster deformers), and the bone hierarchy as null/joint nodes.
    """

    def export(self, model: KotorModel, fbx_path: str) -> bool:
        # Try fbx module (Autodesk FBX Python SDK)
        try:
            import fbx as _fbx
            return self._export_fbx_sdk(model, fbx_path, _fbx)
        except ImportError:
            pass

        # Try pyassimp
        try:
            import pyassimp
            return self._export_assimp(model, fbx_path, pyassimp)
        except ImportError:
            pass

        # Fallback: FBX ASCII 7.4
        try:
            return self._export_fbx_ascii(model, fbx_path)
        except Exception as e:
            log.error(f"FBX ASCII export failed: {e}")
            # Last resort: OBJ
            obj_path = str(Path(fbx_path).with_suffix('.obj'))
            log.warning(f"Falling back to OBJ export: {obj_path}")
            OBJExporter().export(model, obj_path)
            return False

    # ── FBX SDK (Autodesk Python SDK) ─────────────────────────────────

    def _export_fbx_sdk(self, model: KotorModel, fbx_path: str, fbx) -> bool:
        """Export using Autodesk FBX Python SDK if available."""
        try:
            mgr     = fbx.FbxManager.Create()
            scene   = fbx.FbxScene.Create(mgr, model.name)
            info    = fbx.FbxDocumentInfo.Create(mgr, "DocInfo")
            info.mTitle   = model.name
            info.mSubject = f"KotOR model exported by GhostRigger-K1-K2"
            scene.SetSceneInfo(info)

            # Set Z-up axis system (KotOR convention)
            axis_sys = fbx.FbxAxisSystem(
                fbx.FbxAxisSystem.eZAxis,
                fbx.FbxAxisSystem.eParityOdd,
                fbx.FbxAxisSystem.eRightHanded)
            scene.GetGlobalSettings().SetAxisSystem(axis_sys)

            root = scene.GetRootNode()
            node_map: Dict[str, 'fbx.FbxNode'] = {}

            # Create skeleton nodes
            for n in model.all_nodes():
                if n.is_dummy:
                    skel_attr = fbx.FbxSkeleton.Create(mgr, n.name)
                    skel_attr.SetSkeletonType(
                        fbx.FbxSkeleton.eRoot if n.parent is None
                        else fbx.FbxSkeleton.eLimbNode)
                    fbx_node = fbx.FbxNode.Create(mgr, n.name)
                    fbx_node.SetNodeAttribute(skel_attr)
                    fbx_node.LclTranslation.Set(fbx.FbxDouble3(*n.position))
                    node_map[n.name] = fbx_node

            # Build hierarchy for skeleton
            for n in model.all_nodes():
                if n.name in node_map:
                    fbx_node = node_map[n.name]
                    if n.parent and n.parent.name in node_map:
                        node_map[n.parent.name].AddChild(fbx_node)
                    else:
                        root.AddChild(fbx_node)

            # Create mesh nodes (only renderable geometry)
            for mesh_node in _renderable_mesh_nodes(model):
                self._add_fbx_mesh(mgr, scene, root, mesh_node, node_map)

            # Save
            exporter = fbx.FbxExporter.Create(mgr, "")
            ok = exporter.Initialize(fbx_path, -1, mgr.GetIOSettings())
            if ok:
                exporter.Export(scene)
            exporter.Destroy()
            mgr.Destroy()
            if ok:
                log.info(f"FBX SDK export: {fbx_path}")
                return True
        except Exception as e:
            log.error(f"FBX SDK export error: {e}")
        return False

    def _add_fbx_mesh(self, mgr, scene, root_fbx_node, mesh_node: ModelNode,
                      node_map: dict):
        """Add one KotOR mesh node to the FBX scene (FBX SDK path)."""
        try:
            import fbx
            fbx_mesh = fbx.FbxMesh.Create(mgr, mesh_node.name)

            # Vertices
            fbx_mesh.InitControlPoints(len(mesh_node.vertices))
            for i, (x,y,z) in enumerate(mesh_node.vertices):
                fbx_mesh.SetControlPointAt(fbx.FbxVector4(x,y,z,0), i)

            # Faces
            for face in mesh_node.faces:
                fbx_mesh.BeginPolygon(-1, -1, False)
                for vi in face: fbx_mesh.AddPolygon(vi)
                fbx_mesh.EndPolygon()

            # Normals
            if mesh_node.normals:
                nrm_layer = fbx.FbxLayerElementNormal.Create(fbx_mesh, "Normals")
                nrm_layer.SetMappingMode(fbx.FbxLayerElement.eByControlPoint)
                nrm_layer.SetReferenceMode(fbx.FbxLayerElement.eDirect)
                for nx,ny,nz in mesh_node.normals:
                    nrm_layer.GetDirectArray().Add(fbx.FbxVector4(nx,ny,nz,0))
                fbx_mesh.GetLayer(0).SetNormals(nrm_layer)

            # UVs
            if mesh_node.uvs:
                uv_layer = fbx.FbxLayerElementUV.Create(fbx_mesh, "UVMap")
                uv_layer.SetMappingMode(fbx.FbxLayerElement.eByControlPoint)
                uv_layer.SetReferenceMode(fbx.FbxLayerElement.eDirect)
                for u,v in mesh_node.uvs:
                    uv_layer.GetDirectArray().Add(fbx.FbxVector2(u, v))
                fbx_mesh.GetLayer(0).SetUVs(uv_layer)

            fbx_node = fbx.FbxNode.Create(mgr, mesh_node.name)
            fbx_node.SetNodeAttribute(fbx_mesh)
            root_fbx_node.AddChild(fbx_node)
        except Exception as e:
            log.debug(f"FBX SDK mesh add error ({mesh_node.name}): {e}")

    # ── pyassimp path ─────────────────────────────────────────────────

    def _export_assimp(self, model: KotorModel, fbx_path: str, pyassimp) -> bool:
        """Export via pyassimp (limited skeleton support)."""
        try:
            # pyassimp export is immature; fall through to ASCII
            log.info("pyassimp FBX export attempted but not reliable – using ASCII FBX")
            return self._export_fbx_ascii(model, fbx_path)
        except Exception as e:
            log.error(f"pyassimp export error: {e}")
            return False

    # ── FBX ASCII 7.4 (zero-dependency fallback) ──────────────────────

    def _export_fbx_ascii(self, model: KotorModel, fbx_path: str) -> bool:
        """
        Write FBX ASCII 7.4 file.  No external dependencies required.
        Supported by Blender 2.79+, Maya 2016+, 3ds Max 2016+.

        Exports:
          - Geometry (vertices, normals, UVs, polygon indices)
          - Material (diffuse/specular colour + texture reference)
          - Skeleton (null-joint node hierarchy)
          - Skin deformers with weights (if skin nodes exist)
          - Bind pose
        """
        from datetime import datetime

        lines: List[str] = []
        w = lines.append

        # Only export renderable mesh nodes (respects render flag + deform helpers)
        mesh_nodes_list = _renderable_mesh_nodes(model)

        # ── Header ────────────────────────────────────────────────────
        now = datetime.now()
        w('; FBX 7.4.0 project file')
        w('; Created by GhostRigger-K1-K2')
        w(f'; Model: {model.name}')
        w('')
        w('FBXHeaderExtension:  {')
        w('\tFBXHeaderVersion: 1003')
        w('\tFBXVersion: 7400')
        w(f'\tCreationTimeStamp:  {{')
        w(f'\t\tVersion: 1000')
        w(f'\t\tYear: {now.year}')
        w(f'\t\tMonth: {now.month}')
        w(f'\t\tDay: {now.day}')
        w(f'\t\tHour: {now.hour}')
        w(f'\t\tMinute: {now.minute}')
        w(f'\t\tSecond: {now.second}')
        w(f'\t\tMillisecond: 0')
        w('\t}')
        w(f'\tCreator: "GhostRigger-K1-K2 FBX Exporter"')
        w('}')
        w('')
        w('GlobalSettings:  {')
        w('\tVersion: 1000')
        w('\tProperties70:  {')
        # Z-up right-handed (KotOR coordinate system)
        w('\t\tP: "UpAxis", "int", "Integer", "",2')
        w('\t\tP: "UpAxisSign", "int", "Integer", "",1')
        w('\t\tP: "FrontAxis", "int", "Integer", "",1')
        w('\t\tP: "FrontAxisSign", "int", "Integer", "",1')
        w('\t\tP: "CoordAxis", "int", "Integer", "",0')
        w('\t\tP: "CoordAxisSign", "int", "Integer", "",1')
        w('\t\tP: "UnitScaleFactor", "double", "Number", "",100')
        w('\t}')
        w('}')
        w('')

        # ── ID helpers ────────────────────────────────────────────────
        _id_counter = [1000]
        def new_id():
            _id_counter[0] += 1
            return _id_counter[0]

        # Assign IDs
        node_ids:    Dict[str, int] = {}
        mesh_ids:    Dict[str, int] = {}
        mat_ids:     Dict[str, int] = {}
        deform_ids:  Dict[str, int] = {}  # skin deformer per mesh
        cluster_ids: Dict[str, Dict[str,int]] = {}  # clusters[mesh_name][bone_name]
        pose_id = new_id()

        for n in model.all_nodes():
            node_ids[n.name] = new_id()
        for n in mesh_nodes_list:
            mesh_ids[n.name] = new_id()
            mat_ids[n.name]  = new_id()
            if n.is_skin:
                deform_ids[n.name] = new_id()
                cluster_ids[n.name] = {}
                for bname in n.bone_map:
                    cluster_ids[n.name][bname] = new_id()

        # ── Objects section ───────────────────────────────────────────
        w('Objects:  {')

        # Geometry objects
        for n in mesh_nodes_list:
            geo_id = mesh_ids[n.name]
            w(f'\tGeometry: {geo_id}, "{n.name}", "Mesh" {{')

            # Vertices
            verts_flat = [c for v in n.vertices for c in v]
            w(f'\t\tVertices: *{len(verts_flat)} {{')
            w('\t\t\ta: ' + ','.join(f'{x:.6f}' for x in verts_flat))
            w('\t\t}')

            # Polygon vertex index (FBX uses negative last index per poly)
            poly_idx = []
            for face in n.faces:
                for i, vi in enumerate(face):
                    poly_idx.append(vi if i < len(face)-1 else -(vi+1))
            w(f'\t\tPolygonVertexIndex: *{len(poly_idx)} {{')
            w('\t\t\ta: ' + ','.join(str(i) for i in poly_idx))
            w('\t\t}')

            # Normals layer
            if n.normals:
                nrm_flat = [c for nrm in n.normals for c in nrm]
                w('\t\tLayerElementNormal: 0 {')
                w('\t\t\tVersion: 101')
                w('\t\t\tName: ""')
                w('\t\t\tMappingInformationType: "ByControlPoint"')
                w('\t\t\tReferenceInformationType: "Direct"')
                w(f'\t\t\tNormals: *{len(nrm_flat)} {{')
                w('\t\t\t\ta: ' + ','.join(f'{x:.6f}' for x in nrm_flat))
                w('\t\t\t}')
                w('\t\t}')

            # UV layer
            if n.uvs:
                uv_flat = [c for uv in n.uvs for c in uv]
                # Build UV index array (one per polygon vertex)
                uv_idx = []
                for face in n.faces:
                    uv_idx.extend(face)
                w('\t\tLayerElementUV: 0 {')
                w('\t\t\tVersion: 101')
                w('\t\t\tName: "UVMap"')
                w('\t\t\tMappingInformationType: "ByControlPoint"')
                w('\t\t\tReferenceInformationType: "Direct"')
                w(f'\t\t\tUV: *{len(uv_flat)} {{')
                w('\t\t\t\ta: ' + ','.join(f'{x:.6f}' for x in uv_flat))
                w('\t\t\t}')
                w('\t\t}')

            # Material reference layer
            w('\t\tLayerElementMaterial: 0 {')
            w('\t\t\tVersion: 101')
            w('\t\t\tName: ""')
            w('\t\t\tMappingInformationType: "AllSame"')
            w('\t\t\tReferenceInformationType: "IndexToDirect"')
            w('\t\t\tMaterials: *1 {')
            w('\t\t\t\ta: 0')
            w('\t\t\t}')
            w('\t\t}')

            # Layer definition
            has_nrm = 'Normal' if n.normals else ''
            has_uv  = 'UV' if n.uvs else ''
            w('\t\tLayer: 0 {')
            w('\t\t\tVersion: 100')
            if n.normals:
                w('\t\t\tLayerElement:  {')
                w('\t\t\t\tType: "LayerElementNormal"')
                w('\t\t\t\tTypedIndex: 0')
                w('\t\t\t}')
            if n.uvs:
                w('\t\t\tLayerElement:  {')
                w('\t\t\t\tType: "LayerElementUV"')
                w('\t\t\t\tTypedIndex: 0')
                w('\t\t\t}')
            w('\t\t\tLayerElement:  {')
            w('\t\t\t\tType: "LayerElementMaterial"')
            w('\t\t\t\tTypedIndex: 0')
            w('\t\t\t}')
            w('\t\t}')

            w('\t}')  # end Geometry

        # Material objects
        for n in mesh_nodes_list:
            mid = mat_ids[n.name]
            tname = n.texture_clean or n.name
            w(f'\tMaterial: {mid}, "{tname}", "" {{')
            w('\t\tVersion: 102')
            w(f'\t\tShadingModel: "Phong"')
            w('\t\tMultiLayer: 0')
            w('\t\tProperties70:  {')
            d = n.diffuse
            w(f'\t\t\tP: "DiffuseColor","ColorRGB","Color","",{d[0]:.4f},{d[1]:.4f},{d[2]:.4f}')
            s = n.specular
            w(f'\t\t\tP: "SpecularColor","ColorRGB","Color","",{s[0]:.4f},{s[1]:.4f},{s[2]:.4f}')
            w(f'\t\t\tP: "Shininess","double","Number","",{n.shininess:.2f}')
            w(f'\t\t\tP: "Opacity","double","Number","",{n.alpha:.4f}')
            w('\t\t}')
            w('\t}')  # end Material

        import math as _m

        def _quat_to_euler_deg(qx, qy, qz, qw):
            """Convert xyzw quaternion to Euler XYZ degrees for FBX."""
            # Normalize
            mag = _m.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
            if mag > 1e-9:
                qx /= mag; qy /= mag; qz /= mag; qw /= mag
            sinr = 2*(qw*qx + qy*qz)
            cosr = 1 - 2*(qx*qx + qy*qy)
            ex = _m.degrees(_m.atan2(sinr, cosr))
            sinp = 2*(qw*qy - qz*qx)
            ey = _m.degrees(_m.asin(max(-1.0, min(1.0, sinp))))
            siny = 2*(qw*qz + qx*qy)
            cosy = 1 - 2*(qy*qy + qz*qz)
            ez = _m.degrees(_m.atan2(siny, cosy))
            return ex, ey, ez

        def _world_matrix_row_major(node) -> str:
            """Return 16 floats (row-major 4x4) for this node's world transform bind pose."""
            try:
                wp, wq = node.world_transform()
                qx, qy, qz, qw = wq
                # Build rotation matrix from quaternion
                xx = 1 - 2*(qy*qy + qz*qz)
                xy = 2*(qx*qy - qz*qw)
                xz = 2*(qx*qz + qy*qw)
                yx = 2*(qx*qy + qz*qw)
                yy = 1 - 2*(qx*qx + qz*qz)
                yz = 2*(qy*qz - qx*qw)
                zx = 2*(qx*qz - qy*qw)
                zy = 2*(qy*qz + qx*qw)
                zz = 1 - 2*(qx*qx + qy*qy)
                tx, ty, tz = wp
                # Row-major order (FBX convention)
                mat = [xx, xy, xz, 0,
                       yx, yy, yz, 0,
                       zx, zy, zz, 0,
                       tx, ty, tz, 1]
                return ','.join(f'{v:.6f}' for v in mat)
            except Exception:
                return '1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1'

        # Skeleton/joint model nodes (all dummy nodes)
        for n in model.all_nodes():
            if not n.is_dummy: continue
            nid = node_ids[n.name]
            w(f'\tModel: {nid}, "{n.name}", "LimbNode" {{')
            w('\t\tVersion: 232')
            w('\t\tProperties70:  {')
            px, py, pz = n.position
            w(f'\t\t\tP: "Lcl Translation","Lcl Translation","","A",{px:.6f},{py:.6f},{pz:.6f}')
            qx, qy, qz, qw = n.rotation
            ex, ey, ez = _quat_to_euler_deg(qx, qy, qz, qw)
            w(f'\t\t\tP: "Lcl Rotation","Lcl Rotation","","A",{ex:.4f},{ey:.4f},{ez:.4f}')
            w('\t\t}')
            w('\t}')  # end Model (skeleton node)

        # Mesh model nodes (non-dummy mesh nodes)
        for n in mesh_nodes_list:
            nid = node_ids[n.name]
            w(f'\tModel: {nid}, "{n.name}", "Mesh" {{')
            w('\t\tVersion: 232')
            w('\t\tProperties70:  {')
            px, py, pz = n.position
            w(f'\t\t\tP: "Lcl Translation","Lcl Translation","","A",{px:.6f},{py:.6f},{pz:.6f}')
            w('\t\t}')
            w('\t}')  # end Model (mesh node)

        # Skin deformers
        for n in mesh_nodes_list:
            if not n.is_skin: continue
            sid = deform_ids[n.name]
            w(f'\tDeformer: {sid}, "{n.name}_Skin", "Skin" {{')
            w('\t\tVersion: 101')
            w('\t\tLink_DeformAcuracy: 50')
            w('\t}')

            # Sub-deformers (clusters per bone)
            for bi, bname in enumerate(n.bone_map):
                if bname not in cluster_ids.get(n.name, {}):
                    continue
                cid = cluster_ids[n.name][bname]
                # Gather vertex indices + weights for this bone
                vi_list = []
                wt_list = []
                for vi, sd in enumerate(n.skin_data):
                    for inf in sd.influences:
                        if inf.bone_index == bi and inf.weight > 0:
                            vi_list.append(vi)
                            wt_list.append(inf.weight)
                if not vi_list: continue

                w(f'\tDeformer: {cid}, "{bname}", "Cluster" {{')
                w('\t\tVersion: 100')
                w(f'\t\tIndexes: *{len(vi_list)} {{')
                w('\t\t\ta: ' + ','.join(str(i) for i in vi_list))
                w('\t\t}')
                w(f'\t\tWeights: *{len(wt_list)} {{')
                w('\t\t\ta: ' + ','.join(f'{x:.6f}' for x in wt_list))
                w('\t\t}')
                # Transform = mesh world matrix (identity for skinned meshes)
                identity_m = '1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1'
                # TransformLink = bone world-space bind matrix
                bone_node = model.find_node(bname)
                if bone_node:
                    link_m = _world_matrix_row_major(bone_node)
                else:
                    link_m = identity_m
                w(f'\t\tTransform: *16 {{')
                w(f'\t\t\ta: {identity_m}')
                w('\t\t}')
                w(f'\t\tTransformLink: *16 {{')
                w(f'\t\t\ta: {link_m}')
                w('\t\t}')
                w('\t}')  # end Cluster deformer

        # Bind pose
        all_pose_nodes = (list(model.all_nodes()))
        w(f'\tPose: {pose_id}, "BIND_POSES", "BindPose" {{')
        w(f'\t\tType: "BindPose"')
        w(f'\t\tVersion: 100')
        w(f'\t\tNbPoseNodes: {len(all_pose_nodes)}')
        for n in all_pose_nodes:
            nid = node_ids[n.name]
            world_mat = _world_matrix_row_major(n)
            w(f'\t\tPoseNode:  {{')
            w(f'\t\t\tNode: {nid}')
            w(f'\t\t\tMatrix: *16 {{')
            w(f'\t\t\t\ta: {world_mat}')
            w(f'\t\t\t}}')
            w(f'\t\t}}')
        w('\t}')  # end Pose

        w('}')  # end Objects

        # ── Connections section ────────────────────────────────────────
        w('')
        w('Connections:  {')

        # Node → parent hierarchy
        for n in model.all_nodes():
            nid = node_ids[n.name]
            if n.parent and n.parent.name in node_ids:
                pid = node_ids[n.parent.name]
                w(f'\tC: "OO",{nid},{pid}')
            else:
                w(f'\tC: "OO",{nid},0')

        # Geometry → mesh model node
        for n in mesh_nodes_list:
            w(f'\tC: "OO",{mesh_ids[n.name]},{node_ids[n.name]}')

        # Material → mesh model node
        for n in mesh_nodes_list:
            w(f'\tC: "OO",{mat_ids[n.name]},{node_ids[n.name]}')

        # Skin deformer → geometry
        for n in mesh_nodes_list:
            if not n.is_skin: continue
            w(f'\tC: "OO",{deform_ids[n.name]},{mesh_ids[n.name]}')
            # Clusters → skin deformer
            for bname, cid in cluster_ids.get(n.name, {}).items():
                w(f'\tC: "OO",{cid},{deform_ids[n.name]}')
                # Cluster → bone joint node
                if bname in node_ids:
                    w(f'\tC: "OO",{node_ids[bname]},{cid}')

        w('}')  # end Connections

        # Write to file
        content = '\n'.join(lines)
        with open(fbx_path, 'w', encoding='utf-8') as f:
            f.write(content)

        log.info(f"FBX ASCII export: {fbx_path} "
                 f"({len(mesh_nodes_list)} meshes, "
                 f"{len(model.all_nodes())} nodes, "
                 f"{len(content)} bytes)")
        return True



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
    """
    Convert KotOR TPC texture to TGA.
    Supports uncompressed (Grey/RGB/RGBA) and DXT1/DXT5 block-compressed formats.
    KotOR TPC uses data_size field to identify compression:
      data_sz == w*h     → Grey (enc=1)
      data_sz == w*h*3   → RGB (enc=2 when uncompressed)
      data_sz == w*h*4   → RGBA (enc=4 when uncompressed)
      data_sz == (w//4)*(h//4)*8   → DXT1
      data_sz == (w//4)*(h//4)*16  → DXT5
    """
    try:
        with open(tpc_path,'rb') as f: data = f.read()
        if len(data) < TPC_HDR:
            return False
        data_sz = struct.unpack_from('<I',data,0)[0]
        w = struct.unpack_from('<H',data,8)[0]
        h = struct.unpack_from('<H',data,10)[0]
        enc = data[12]

        if w == 0 or h == 0:
            return False

        off = TPC_HDR
        pixel_data = data[off:]

        # Identify format by comparing data_sz to expected sizes
        dxt1_sz = max(8, (max(1,w//4)) * (max(1,h//4)) * 8)
        dxt5_sz = max(16, (max(1,w//4)) * (max(1,h//4)) * 16)

        if data_sz == w * h:
            # Greyscale
            raw = pixel_data[:w*h]
            img_type = 3; tga_bpp = 8
            converted = bytearray(raw)
        elif data_sz == w * h * 3:
            # RGB
            raw = pixel_data[:w*h*3]
            converted = bytearray()
            for i in range(0, len(raw), 3):
                r,g,b = raw[i],raw[i+1],raw[i+2]
                converted.extend([b,g,r])
            img_type = 2; tga_bpp = 24
        elif data_sz == w * h * 4:
            # RGBA
            raw = pixel_data[:w*h*4]
            converted = bytearray()
            for i in range(0, len(raw), 4):
                r,g,b,a = raw[i],raw[i+1],raw[i+2],raw[i+3]
                converted.extend([b,g,r,a])
            img_type = 2; tga_bpp = 32
        elif data_sz == dxt1_sz:
            # DXT1 block-compressed
            rgba = _decompress_dxt1(pixel_data, w, h)
            converted = bytearray()
            for i in range(0, len(rgba), 4):
                r,g,b,a = rgba[i],rgba[i+1],rgba[i+2],rgba[i+3]
                converted.extend([b,g,r,a])
            img_type = 2; tga_bpp = 32
        elif data_sz == dxt5_sz:
            # DXT5 block-compressed
            rgba = _decompress_dxt5(pixel_data, w, h)
            converted = bytearray()
            for i in range(0, len(rgba), 4):
                r,g,b,a = rgba[i],rgba[i+1],rgba[i+2],rgba[i+3]
                converted.extend([b,g,r,a])
            img_type = 2; tga_bpp = 32
        else:
            # Fallback: try uncompressed based on enc field
            bpp = {1:1, 2:3, 4:4}.get(enc, 3)
            expected = w * h * bpp
            if len(pixel_data) < expected:
                log.error(f"TPC→TGA: insufficient data for {w}x{h} enc={enc}")
                return False
            raw = pixel_data[:expected]
            if bpp == 4:
                converted = bytearray()
                for i in range(0,len(raw),4):
                    r,g,b,a=raw[i],raw[i+1],raw[i+2],raw[i+3]
                    converted.extend([b,g,r,a])
                img_type=2; tga_bpp=32
            elif bpp == 3:
                converted = bytearray()
                for i in range(0,len(raw),3):
                    r,g,b=raw[i],raw[i+1],raw[i+2]
                    converted.extend([b,g,r])
                img_type=2; tga_bpp=24
            else:
                converted = bytearray(raw); img_type=3; tga_bpp=8

        hdr = struct.pack('<BBBHHHHHHHBB',0,0,img_type,0,0,0,0,0,w,h,tga_bpp,0x20)
        with open(tga_path,'wb') as f:
            f.write(hdr); f.write(bytes(converted))
        return True
    except Exception as e:
        log.error(f"TPC→TGA failed: {e}"); return False


def _decompress_dxt1(data: bytes, w: int, h: int) -> bytes:
    """Software DXT1 decompressor. Returns RGBA bytes."""
    result = bytearray(w * h * 4)
    blocks_x = max(1, (w + 3) // 4)
    blocks_y = max(1, (h + 3) // 4)
    pos = 0
    for by in range(blocks_y):
        for bx in range(blocks_x):
            if pos + 8 > len(data): break
            c0r = struct.unpack_from('<H', data, pos)[0]
            c1r = struct.unpack_from('<H', data, pos+2)[0]
            lk  = struct.unpack_from('<I', data, pos+4)[0]
            pos += 8
            def e565(c):
                return (((c>>11)&0x1F)*255//31, ((c>>5)&0x3F)*255//63, (c&0x1F)*255//31)
            c0 = e565(c0r); c1 = e565(c1r)
            if c0r > c1r:
                cols = [c0,c1,
                        ((2*c0[0]+c1[0])//3,(2*c0[1]+c1[1])//3,(2*c0[2]+c1[2])//3),
                        ((c0[0]+2*c1[0])//3,(c0[1]+2*c1[1])//3,(c0[2]+2*c1[2])//3)]
            else:
                cols = [c0,c1,
                        ((c0[0]+c1[0])//2,(c0[1]+c1[1])//2,(c0[2]+c1[2])//2),
                        (0,0,0)]
            for py2 in range(4):
                for px2 in range(4):
                    idx=(lk>>(2*(py2*4+px2)))&3; col=cols[idx]
                    gx=bx*4+px2; gy=by*4+py2
                    if gx<w and gy<h:
                        o=(gy*w+gx)*4
                        result[o]=col[0]; result[o+1]=col[1]; result[o+2]=col[2]; result[o+3]=255
    return bytes(result)


def _decompress_dxt5(data: bytes, w: int, h: int) -> bytes:
    """Software DXT5 decompressor. Returns RGBA bytes."""
    result = bytearray(w * h * 4)
    blocks_x = max(1, (w + 3) // 4)
    blocks_y = max(1, (h + 3) // 4)
    pos = 0
    for by in range(blocks_y):
        for bx in range(blocks_x):
            if pos + 16 > len(data): break
            a0=data[pos]; a1=data[pos+1]
            abits=struct.unpack_from('<Q',data,pos+1)[0]>>8
            pos+=8
            c0r=struct.unpack_from('<H',data,pos)[0]; c1r=struct.unpack_from('<H',data,pos+2)[0]
            lk=struct.unpack_from('<I',data,pos+4)[0]; pos+=8
            def e565(c):
                return (((c>>11)&0x1F)*255//31,((c>>5)&0x3F)*255//63,(c&0x1F)*255//31)
            c0=e565(c0r); c1=e565(c1r)
            cols=[c0,c1,((2*c0[0]+c1[0])//3,(2*c0[1]+c1[1])//3,(2*c0[2]+c1[2])//3),
                        ((c0[0]+2*c1[0])//3,(c0[1]+2*c1[1])//3,(c0[2]+2*c1[2])//3)]
            if a0>a1: als=[a0,a1,(6*a0+a1)//7,(5*a0+2*a1)//7,(4*a0+3*a1)//7,(3*a0+4*a1)//7,(2*a0+5*a1)//7,(a0+6*a1)//7]
            else: als=[a0,a1,(4*a0+a1)//5,(3*a0+2*a1)//5,(2*a0+3*a1)//5,(a0+4*a1)//5,0,255]
            for py2 in range(4):
                for px2 in range(4):
                    ci=(lk>>(2*(py2*4+px2)))&3; ai=(abits>>(3*(py2*4+px2)))&7
                    col=cols[ci]; alpha=als[ai]
                    gx=bx*4+px2; gy=by*4+py2
                    if gx<w and gy<h:
                        o=(gy*w+gx)*4
                        result[o]=col[0]; result[o+1]=col[1]; result[o+2]=col[2]; result[o+3]=alpha
    return bytes(result)


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
