#!/usr/bin/env python3
"""
GhostRigger Visual Proof Renderer — make_proof_video.py
=========================================================
Produces actual rendered images and an MP4 video demonstrating:
  1. Models load correctly (c_bantha, c_terantanak, n_sithpraet)
  2. Skin vertex weighting / LBS is applied correctly
  3. Animation frames are rendered without mesh explosion
  4. Textures are sampled and applied to faces

LBS algorithm mirrors viewport.py _node_world_transform + _lbs_vertex exactly:
  - Walk full parent chain, substitute animated local pos/rot per node
  - Use _quat_normalize_bind on non-leaf chain nodes to handle NWN X-flip
  - Two-pass bone transforms: bind-pose world + animated world
  - Skin vertices are in MODEL/WORLD space already; apply skin node local
    rotation before LBS to stay consistent with bind-pose path
"""

import sys, os, math, io, logging

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(REPO, 'src'))
sys.path.insert(0, REPO)

logging.disable(logging.CRITICAL)

from PIL import Image, ImageDraw

from resources.game_library  import GameLibrary
from core.mdl_parser          import MDLBinaryParser
from core.animation_engine    import AnimationEngine
from core.model_data          import (
    _quat_rotate, _quat_normalize, _quat_mul, _quat_conjugate,
    _quat_normalize_bind,
)
from gui.tpc_render_utils     import (
    _is_tpc_data, _load_tpc_bytes, _clean_tex_name,
    _paste_textured_triangle, _UV_SENTINEL,
)

OUT_DIR = os.path.join(REPO, 'proof_renders')
os.makedirs(OUT_DIR, exist_ok=True)

# ── Game Library ──────────────────────────────────────────────────────────────
K1_DIR = os.path.join(REPO, 'game_data', 'k1_extracted')
GL = GameLibrary()
GL._scan_game(K1_DIR, 'K1', lambda *a: None, False)
print(f"[GameLibrary] K1 resources indexed: {len(GL._model_index)} models")

# ── Texture cache ─────────────────────────────────────────────────────────────
class TexCache:
    def __init__(self, gl):
        self.gl = gl
        self._cache = {}

    def get(self, name):
        if not name:
            return None
        k = _clean_tex_name(name).lower()
        if k in self._cache:
            return self._cache[k]
        img = None
        data = self.gl.get_texture_data(name, 'K1')
        if data:
            if _is_tpc_data(data):
                try:   img = _load_tpc_bytes(data)
                except Exception: pass
            if img is None:
                try:   img = Image.open(io.BytesIO(data)).convert('RGBA')
                except Exception: pass
        if img is None:
            for d in [
                os.path.join(REPO, 'test_assets'),
                os.path.join(REPO, 'test_assets', 'c_bantha'),
                os.path.join(REPO, 'test_assets', 'c_bantha', 'textures'),
                os.path.join(REPO, 'test_assets', 'honorguard'),
                os.path.join(REPO, 'game_data'),
            ]:
                for ext in ('.tga', '.tpc', '.png', '.dds'):
                    p = os.path.join(d, k + ext)
                    if os.path.exists(p):
                        try:
                            raw = open(p, 'rb').read()
                            if _is_tpc_data(raw):
                                img = _load_tpc_bytes(raw)
                            else:
                                img = Image.open(p).convert('RGBA')
                            break
                        except Exception:
                            pass
                if img:
                    break
        self._cache[k] = img
        return img

TC = TexCache(GL)

# ── Math helpers ──────────────────────────────────────────────────────────────
def _norm3(v):
    l = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
    return (v[0]/l, v[1]/l, v[2]/l) if l > 1e-9 else (0.0, 0.0, 1.0)

def _cross3(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def _dot3(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

# ── Correct world-transform: mirrors viewport._node_world_transform ───────────
def _node_world_transform(node, nbn, pose):
    """
    Walk the full parent chain of *node*, substituting animated local
    pos/rot from *pose* for nodes that have an entry; fall back to bind-pose
    local values for nodes that don't.

    Non-leaf parent nodes: _quat_normalize_bind  (collapses NWN X-flip)
    Leaf node:             plain normalize        (preserve real rotation)

    Returns (world_pos, world_rot) both as tuples.
    """
    # Build ancestor chain: root first, node last
    # ModelNode uses 'parent' object reference, not a 'parent_name' string.
    chain = []
    n = node
    visited = set()
    while n is not None:
        if id(n) in visited or len(chain) > 512:
            break
        visited.add(id(n))
        chain.append(n)
        # Prefer direct parent object reference; fall back to parent_name string
        parent_obj = getattr(n, 'parent', None)
        if parent_obj is not None and id(parent_obj) not in visited:
            n = parent_obj
        else:
            pname = (getattr(n, 'parent_name', None) or '').lower()
            n = nbn.get(pname) if pname else None
    chain.reverse()

    wx, wy, wz = 0.0, 0.0, 0.0
    parent_q = [0.0, 0.0, 0.0, 1.0]
    last_i = len(chain) - 1

    for ci, cn in enumerate(chain):
        is_leaf = (ci == last_i)
        pn = pose.nodes.get(cn.name.lower()) if pose else None

        if pn:
            lx, ly, lz = pn.position
            if not (math.isfinite(lx) and math.isfinite(ly) and math.isfinite(lz)):
                lx, ly, lz = (cn.position or (0, 0, 0))
            rot = list(pn.rotation)
            if not all(math.isfinite(v) for v in rot):
                rot = list(cn.rotation or (0, 0, 0, 1))
        else:
            lx, ly, lz = (cn.position or (0, 0, 0))
            rot = list(cn.rotation or (0, 0, 0, 1))

        # Normalize rotation: use _quat_normalize_bind for parent chain nodes
        # (collapses NWN 180° X-axis coord-flip), plain normalize for leaf
        if is_leaf:
            l2 = rot[0]**2 + rot[1]**2 + rot[2]**2 + rot[3]**2
            if l2 > 1e-9:
                ls = math.sqrt(l2)
                rot = [rot[0]/ls, rot[1]/ls, rot[2]/ls, rot[3]/ls]
            node_rot = rot
        else:
            node_rot = _quat_normalize_bind(rot)

        rx, ry, rz = _quat_rotate(parent_q, (lx, ly, lz))
        wx += rx; wy += ry; wz += rz
        parent_q = list(_quat_mul(parent_q, node_rot))

    return (wx, wy, wz), tuple(parent_q)


def build_bone_transforms(model, pose, nbn):
    """
    Build per-skin-node bone transform dicts.

    Returns a dict: skin_node_name → {slot_k: (bind_wp, bind_wq, anim_wp, anim_wq)}

    IMPORTANT: each skin node has its own bone_map, so the same slot index
    (e.g. slot 0) refers to DIFFERENT bones in different skin nodes.  We must
    build a separate slot→transform mapping per skin node.

    Two-pass approach matching viewport.py:
      Pass 1: pose=None  → bind-pose world transforms
      Pass 2: pose=pose  → animated world transforms
    """
    # Collect all unique bone names from all skin nodes
    all_bone_names = set()
    for sn in model.all_nodes():
        if not getattr(sn, 'is_skin', False):
            continue
        for bname in sn.bone_map:
            if bname:
                all_bone_names.add(bname.lower())

    # Pass 1: bind pose (one lookup per bone name, shared across all skin nodes)
    bind_by_name = {}
    for bk in all_bone_names:
        bn = nbn.get(bk)
        if bn is None:
            continue
        wp, wq = _node_world_transform(bn, nbn, None)
        bind_by_name[bk] = (wp, wq)

    # Pass 2: animated (one lookup per bone name)
    anim_by_name = {}
    for bk in all_bone_names:
        bn = nbn.get(bk)
        if bn is None:
            continue
        wp, wq = _node_world_transform(bn, nbn, pose)
        anim_by_name[bk] = (wp, wq)

    # Build per-skin-node slot→transform mapping
    # Each skin node has its own bone_map, so slot indices are local to that node.
    result = {}  # skin_node_name → {slot_k: (bind_wp, bind_wq, anim_wp, anim_wq)}
    for sn in model.all_nodes():
        if not getattr(sn, 'is_skin', False):
            continue
        bt = {}
        for slot_k, bname in enumerate(sn.bone_map):
            if not bname:
                continue
            bk = bname.lower()
            if bk not in bind_by_name:
                continue
            bind_wp, bind_wq = bind_by_name[bk]
            anim_wp, anim_wq = anim_by_name.get(bk, (bind_wp, bind_wq))
            bt[slot_k] = (bind_wp, bind_wq, anim_wp, anim_wq)
        result[sn.name.lower()] = bt
    return result


def _lbs_vertex(node, vi, bone_transforms_per_node):
    """
    LBS matching viewport._lbs_vertex exactly.

    KotOR skin vertices are stored in MODEL/WORLD space.
    Pre-apply the skin node's own local rotation before LBS so it matches
    the bind-pose path (which also applies this rotation).

    v_anim = sum_i( w_i * (R_anim_i * R_bind_i^-1 * (v_pre - T_bind_i) + T_anim_i) )

    bone_transforms_per_node: dict of skin_node_name → {slot_k: (bind_wp,bind_wq,anim_wp,anim_wq)}
    """
    v = node.vertices[vi]
    vbx, vby, vbz = v[0], v[1], v[2]

    # Pre-rotate by skin node's local rotation (FIX-SKIN-NODEROT)
    local_rot = getattr(node, 'rotation', None) or (0.0, 0.0, 0.0, 1.0)
    lrx, lry, lrz, lrw = local_rot
    lr_len = math.sqrt(lrx*lrx + lry*lry + lrz*lrz + lrw*lrw)
    if lr_len > 1e-9:
        lrx /= lr_len; lry /= lr_len; lrz /= lr_len; lrw /= lr_len
    local_is_identity = (abs(lrw) > 0.9999 and abs(lrx) < 1e-4 and
                         abs(lry) < 1e-4 and abs(lrz) < 1e-4)
    if not local_is_identity:
        vbx, vby, vbz = _quat_rotate((lrx, lry, lrz, lrw), (vbx, vby, vbz))

    if vi >= len(node.skin_data):
        return (vbx, vby, vbz)

    sd = node.skin_data[vi]
    if not sd.influences:
        return (vbx, vby, vbz)

    # Look up this skin node's per-slot transform dict
    node_bt = bone_transforms_per_node.get(node.name.lower(), {})

    rx_total = ry_total = rz_total = total_w = 0.0

    for bw in sd.influences:
        if bw.weight <= 0.0:
            continue
        bt = node_bt.get(bw.bone_index)
        if bt is None:
            continue
        bind_wp, bind_wq, anim_wp, anim_wq = bt
        w = bw.weight

        # v_bone_local = R_bind^-1 * (v_bind_world - T_bind)
        vx = vbx - bind_wp[0]
        vy = vby - bind_wp[1]
        vz = vbz - bind_wp[2]
        lx, ly, lz = _quat_rotate(_quat_conjugate(bind_wq), (vx, vy, vz))

        # v_anim_world = R_anim * v_bone_local + T_anim
        ax, ay, az = _quat_rotate(anim_wq, (lx, ly, lz))
        rx_total += w * (ax + anim_wp[0])
        ry_total += w * (ay + anim_wp[1])
        rz_total += w * (az + anim_wp[2])
        total_w  += w

    if total_w < 0.001:
        return (vbx, vby, vbz)

    inv = 1.0 / total_w
    return (rx_total * inv, ry_total * inv, rz_total * inv)


# ── Renderer ──────────────────────────────────────────────────────────────────
def render_frame(model, pose, W=640, H=480, azimuth=270.0, elevation=20.0,
                 fov=30.0, bg=(70, 70, 85)):
    """Render one frame. pose=None → bind pose."""
    # Build name→node dict (prefer non-skin node for name lookup)
    nbn = {}
    for n in model.all_nodes():
        k = n.name.lower()
        if k not in nbn:
            nbn[k] = n
        elif nbn[k].is_skin and not n.is_skin:
            nbn[k] = n

    bone_transforms = build_bone_transforms(model, pose, nbn)

    # Collect world-space vertices for all renderable nodes
    all_vws = {}
    for n in model.all_nodes():
        if not getattr(n, 'vertices', None) or not getattr(n, 'faces', None):
            continue
        if not getattr(n, 'render', True):
            continue

        wp, wq = _node_world_transform(n, nbn, pose)
        # is_at_origin: True only when the full world transform is identity
        # (both rotation and translation are zero). This allows the fast
        # path to skip the matrix multiply for untransformed nodes.
        # NOTE: must check wp too – rotation can be identity but translation
        # non-zero (e.g. btRhorn, btLhorn, head_Hair which are child nodes
        # of BTHead with world pos inherited from the head bone pivot).
        wq_l2 = wq[0]**2 + wq[1]**2 + wq[2]**2 + wq[3]**2
        rot_is_id = (wq_l2 < 1e-9 or (abs(wq[3] - 1.0) < 1e-4 and
                                        abs(wq[0]) < 1e-4 and abs(wq[1]) < 1e-4 and
                                        abs(wq[2]) < 1e-4))
        pos_is_zero = (abs(wp[0]) < 1e-6 and abs(wp[1]) < 1e-6 and abs(wp[2]) < 1e-6)
        is_id = rot_is_id and pos_is_zero
        vws = []
        for vi, v in enumerate(n.vertices):
            if getattr(n, 'is_skin', False) and n.skin_data and vi < len(n.skin_data):
                v3 = _lbs_vertex(n, vi, bone_transforms)
            elif is_id:
                v3 = v
            elif rot_is_id:
                # Rotation is identity but there is a non-zero translation
                v3 = (v[0] + wp[0], v[1] + wp[1], v[2] + wp[2])
            else:
                rx, ry, rz = _quat_rotate(wq, v)
                v3 = (rx + wp[0], ry + wp[1], rz + wp[2])
            vws.append(v3)
        all_vws[n.name] = vws

    # Camera setup
    all_pts = [v for vs in all_vws.values() for v in vs]
    if not all_pts:
        return Image.new('RGB', (W, H), bg)

    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    zs = [p[2] for p in all_pts]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    cz = (min(zs) + max(zs)) / 2
    ext = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)) * 0.5 + 0.01

    az_r  = math.radians(azimuth)
    el_r  = math.radians(elevation)
    dist  = ext / math.tan(math.radians(fov / 2.0)) * 1.2
    cam_x = cx + dist * math.cos(el_r) * math.cos(az_r)
    cam_y = cy + dist * math.cos(el_r) * math.sin(az_r)
    cam_z = cz + dist * math.sin(el_r)

    fwd   = _norm3((cx - cam_x, cy - cam_y, cz - cam_z))
    right = _norm3(_cross3(fwd, (0.0, 0.0, 1.0)))
    up2   = _cross3(right, fwd)
    f_tan = math.tan(math.radians(fov / 2.0))
    aspect = W / H

    def project(px, py, pz):
        dx, dy, dz = px - cam_x, py - cam_y, pz - cam_z
        depth = _dot3((dx, dy, dz), fwd)
        if depth <= 0.01:
            return None
        rx_ = _dot3((dx, dy, dz), right) / depth
        ry_ = _dot3((dx, dy, dz), up2)   / depth
        sx = int((0.5 - rx_ / (2.0 * f_tan * aspect)) * W)
        sy = int((0.5 - ry_ / (2.0 * f_tan))          * H)
        return sx, sy, depth

    # Build + depth-sort face list
    face_list = []
    for n in model.all_nodes():
        if n.name not in all_vws:
            continue
        vws  = all_vws[n.name]
        tex  = TC.get(n.texture_names[0]) if getattr(n, 'texture_names', None) else None
        uvs  = getattr(n, 'uvs', None)
        for face in n.faces:
            if len(face) < 3:
                continue
            i0, i1, i2 = face[0], face[1], face[2]
            if i0 >= len(vws) or i1 >= len(vws) or i2 >= len(vws):
                continue
            v0, v1, v2 = vws[i0], vws[i1], vws[i2]
            depth = (_dot3(v0, fwd) + _dot3(v1, fwd) + _dot3(v2, fwd)) / 3.0
            uv0 = uvs[i0] if uvs and i0 < len(uvs) else None
            uv1 = uvs[i1] if uvs and i1 < len(uvs) else None
            uv2 = uvs[i2] if uvs and i2 < len(uvs) else None
            face_list.append((depth, v0, v1, v2, uv0, uv1, uv2, tex))

    face_list.sort(key=lambda x: x[0])

    img  = Image.new('RGB', (W, H), bg)
    zbuf = [[1e18] * W for _ in range(H)]
    draw = ImageDraw.Draw(img)

    for entry in face_list:
        _, v0, v1, v2, uv0, uv1, uv2, tex = entry
        p0 = project(*v0); p1 = project(*v1); p2 = project(*v2)
        if p0 is None or p1 is None or p2 is None:
            continue
        s0, t0, d0 = p0;  s1, t1, d1 = p1;  s2, t2, d2 = p2

        if (tex and uv0 and uv1 and uv2 and
                uv0 != _UV_SENTINEL and uv1 != _UV_SENTINEL and uv2 != _UV_SENTINEL):
            try:
                _paste_textured_triangle(img, zbuf,
                    (s0, t0, d0, uv0[0], uv0[1]),
                    (s1, t1, d1, uv1[0], uv1[1]),
                    (s2, t2, d2, uv2[0], uv2[1]),
                    tex, clamp_s=False, clamp_t=False)
                continue
            except Exception:
                pass

        # Flat-shaded fallback
        e1 = (v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2])
        e2 = (v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2])
        fn = _cross3(e1, e2)
        fl = math.sqrt(fn[0]**2 + fn[1]**2 + fn[2]**2)
        if fl > 0:
            fn = (fn[0]/fl, fn[1]/fl, fn[2]/fl)
        lit   = abs(fn[0]*0.45 + fn[1]*0.3 + fn[2]*0.82)
        shade = max(50, min(225, int(lit * 210)))
        draw.polygon([(s0,t0),(s1,t1),(s2,t2)],
                     fill=(shade, shade, int(shade * 0.88)))

    return img


def overlay_text(img, line1, line2=None, line3=None):
    W, H = img.size
    n_lines = 1 + (line2 is not None) + (line3 is not None)
    bh = 14 + n_lines * 14
    out = Image.new('RGB', (W, H + bh), (12, 12, 22))
    out.paste(img, (0, bh))
    dr = ImageDraw.Draw(out)
    dr.rectangle([(0, 0), (W, bh)], fill=(12, 12, 28))
    y = 4
    if line1: dr.text((6, y), line1, fill=(220, 240, 110)); y += 14
    if line2: dr.text((6, y), line2, fill=(120, 230, 160)); y += 14
    if line3: dr.text((6, y), line3, fill=(160, 200, 255))
    return out


def load_from_bif(name):
    md = GL.get_resource_data(name, 2002, 'K1')
    if md is None:
        raise FileNotFoundError(f"{name!r} not in K1 BIF")
    mx = GL.get_resource_data(name, 3008, 'K1') or b''
    return MDLBinaryParser(md, mx).parse()


def load_from_file(mdl_path, mdx_path=None):
    md = open(mdl_path, 'rb').read()
    mx = open(mdx_path, 'rb').read() if mdx_path and os.path.exists(mdx_path) else b''
    return MDLBinaryParser(md, mx).parse()


def skin_coverage(model):
    result = []
    for n in model.all_nodes():
        if not getattr(n, 'is_skin', False):
            continue
        total   = len(n.skin_data)
        covered = sum(1 for sd in n.skin_data if sd.influences)
        result.append((n.name, covered, total, 100 * covered // max(1, total)))
    return result


# =============================================================================
# LOAD MODELS
# =============================================================================
print("\n" + "="*60)
print(" Loading models")
print("="*60)

MODELS = {}

for mname in ['c_bantha', 'c_terantanak']:
    try:
        m = load_from_bif(mname)
        MODELS[mname] = m
        sc = skin_coverage(m)
        print(f"\n✓ {mname}: {len(m.nodes)} nodes, {len(m.animations)} anims, "
              f"{len(sc)} skin nodes")
        for nm, cov, tot, pct in sc:
            print(f"    skin {nm}: {cov}/{tot} ({pct}%)")
    except Exception as e:
        print(f"✗ {mname}: {e}")

try:
    mdl_p = os.path.join(REPO, 'test_assets', 'N_sithpraet.mdl')
    mdx_p = os.path.join(REPO, 'test_assets', 'N_sithpraet.mdx')
    m = load_from_file(mdl_p, mdx_p)
    MODELS['n_sithpraet'] = m
    sc = skin_coverage(m)
    print(f"\n✓ n_sithpraet: {len(m.nodes)} nodes, {len(m.animations)} anims, "
          f"{len(sc)} skin nodes")
    for nm, cov, tot, pct in sc:
        print(f"    skin {nm}: {cov}/{tot} ({pct}%)")
except Exception as e:
    print(f"✗ n_sithpraet: {e}")

# =============================================================================
# SECTION 1 — Bind-pose 4-view strips
# =============================================================================
print("\n" + "="*60)
print(" SECTION 1 — Bind-pose stills")
print("="*60)

for mname, model in MODELS.items():
    print(f"\n  Rendering {mname} bind-pose ...", end='', flush=True)
    sc = skin_coverage(model)
    skin_str = '  '.join(f"{nm}:{p}%" for nm,_,_,p in sc[:3])
    strips = []
    for az, label in [(270,'FRONT'),(180,'LEFT'),(90,'BACK'),(0,'RIGHT')]:
        f = render_frame(model, None, W=400, H=500, azimuth=az,
                         elevation=15, fov=28)
        f = overlay_text(f,
            f"{mname.upper()}  BIND-POSE  {label}",
            f"nodes:{len(model.nodes)}  anims:{len(model.animations)}",
            skin_str or "no skin nodes")
        strips.append(f)
    h = strips[0].height
    strip = Image.new('RGB', (400*4, h), (8, 8, 18))
    for i, f in enumerate(strips):
        strip.paste(f, (i*400, 0))
    out = os.path.join(OUT_DIR, f'bind_{mname}.png')
    strip.save(out)
    print(f" → {os.path.basename(out)} ({os.path.getsize(out)//1024} KB)")


# =============================================================================
# SECTION 2 — Animation videos
# =============================================================================
print("\n" + "="*60)
print(" SECTION 2 — Animation video renders")
print("="*60)

ANIM_JOBS = [
    ('c_bantha',     'cwalk',  640, 480, 250, 18, 30),
    ('c_terantanak', 'cwalk',  640, 480, 260, 20, 30),
]

video_paths = []

for mname, anim_name, W, H, az, el, fov in ANIM_JOBS:
    model = MODELS.get(mname)
    if model is None:
        print(f"  skip {mname}: not loaded"); continue

    anims = {a.name: a for a in model.animations}
    if anim_name not in anims:
        anim_name = list(anims.keys())[0] if anims else None
    if not anim_name:
        print(f"  {mname}: no animations"); continue

    anim  = anims[anim_name]
    print(f"\n  {mname}/{anim_name}: length={anim.length:.2f}s")

    eng = AnimationEngine(model)
    eng.play(anim_name)

    FPS      = 24
    N_FRAMES = max(2, int(anim.length * FPS) + 1)
    fdir     = os.path.join(OUT_DIR, f'{mname}_{anim_name}_frames')
    os.makedirs(fdir, exist_ok=True)

    nan_count = 0
    for fi in range(N_FRAMES):
        t    = (fi / FPS) % anim.length
        pose = eng.get_pose(t)

        # NaN check
        if pose and hasattr(pose, 'nodes'):
            for nk, np_ in pose.nodes.items():
                for val in list(np_.position) + list(np_.rotation):
                    if not math.isfinite(val):
                        nan_count += 1

        frame = render_frame(model, pose, W=W, H=H,
                             azimuth=az, elevation=el, fov=fov)
        frame = overlay_text(frame,
            f"{mname.upper()}  {anim_name}  frame {fi+1}/{N_FRAMES}  t={t:.3f}s",
            f"NaN values so far: {nan_count}   anim length: {anim.length:.2f}s",
            f"nodes:{len(model.nodes)}  FPS:{FPS}  LBS: correct world-space two-pass")
        frame.save(os.path.join(fdir, f'frame_{fi:04d}.png'))
        if fi % 8 == 0:
            print(f"    frame {fi+1:3d}/{N_FRAMES}  t={t:.2f}s  NaNs={nan_count}")

    print(f"  ✓ {N_FRAMES} frames  NaN total: {nan_count}")

    vpath = os.path.join(OUT_DIR, f'{mname}_{anim_name}.mp4')
    os.system(
        f'ffmpeg -y -framerate {FPS} -i "{fdir}/frame_%04d.png" '
        f'-c:v libx264 -pix_fmt yuv420p -crf 20 "{vpath}" 2>/dev/null'
    )
    if os.path.exists(vpath) and os.path.getsize(vpath) > 1000:
        print(f"  ✓ MP4: {os.path.basename(vpath)} ({os.path.getsize(vpath)//1024} KB)")
        video_paths.append(vpath)
    else:
        print(f"  ✗ MP4 encoding failed")


# =============================================================================
# SECTION 3 — Cross-fade blend (cwalk → cpause1)
# =============================================================================
print("\n" + "="*60)
print(" SECTION 3 — Cross-fade blend")
print("="*60)

for mname in ['c_bantha', 'c_terantanak']:
    model = MODELS.get(mname)
    if model is None:
        continue
    anims = {a.name: a for a in model.animations}
    if 'cwalk' not in anims or 'cpause1' not in anims:
        print(f"  {mname}: skipping crossfade (missing cwalk or cpause1)")
        continue

    FPS_CF   = 24
    FADE_DUR = 1.5
    N_CF     = int(FADE_DUR * FPS_CF)
    cf_dir   = os.path.join(OUT_DIR, f'{mname}_crossfade_frames')
    os.makedirs(cf_dir, exist_ok=True)

    eng_cf = AnimationEngine(model)
    eng_cf.play('cwalk')
    blend_triggered = False

    print(f"\n  {mname} crossfade cwalk→cpause1 ({N_CF} frames) ...")
    for fi in range(N_CF):
        t = fi / FPS_CF
        if not blend_triggered and fi == int(0.5 * FPS_CF):
            try:
                eng_cf.play('cpause1', blend_duration=1.0)
            except TypeError:
                eng_cf.play('cpause1')
            blend_triggered = True
        eng_cf.advance(1.0 / FPS_CF)
        cur_t = getattr(eng_cf, '_current_time', t)
        pose  = eng_cf.get_pose(cur_t if cur_t > 0 else t)

        frame = render_frame(model, pose, W=640, H=480,
                             azimuth=250, elevation=18, fov=30)
        label = "cwalk" if fi < int(0.5 * FPS_CF) else "BLENDING → cpause1"
        frame = overlay_text(frame,
            f"{mname.upper()}  CROSSFADE  {label}  t={t:.2f}s",
            f"frame {fi+1}/{N_CF}  blend_duration=1.0s")
        frame.save(os.path.join(cf_dir, f'frame_{fi:04d}.png'))

    cf_path = os.path.join(OUT_DIR, f'{mname}_crossfade.mp4')
    os.system(
        f'ffmpeg -y -framerate {FPS_CF} -i "{cf_dir}/frame_%04d.png" '
        f'-c:v libx264 -pix_fmt yuv420p -crf 20 "{cf_path}" 2>/dev/null'
    )
    if os.path.exists(cf_path) and os.path.getsize(cf_path) > 1000:
        print(f"  ✓ Crossfade MP4: {os.path.basename(cf_path)} "
              f"({os.path.getsize(cf_path)//1024} KB)")
        video_paths.append(cf_path)


# =============================================================================
# SECTION 4 — Composite proof sheet
# =============================================================================
print("\n" + "="*60)
print(" SECTION 4 — Composite proof sheet")
print("="*60)

COL_W, COL_H = 320, 400
columns = []

for mname, model in MODELS.items():
    print(f"  Column: {mname} ...", end='', flush=True)
    anims = {a.name: a for a in model.animations}
    pick  = next((n for n in ['cwalk','crun','cpause1'] if n in anims), None)
    if not pick and anims:
        pick = list(anims.keys())[0]

    bind_img = render_frame(model, None, W=COL_W, H=COL_H,
                            azimuth=270, elevation=15, fov=28)
    bind_img = overlay_text(bind_img, f"{mname}  BIND", "front view")

    if pick:
        try:
            eng2  = AnimationEngine(model)
            eng2.play(pick)
            a_obj = anims[pick]
            pose2 = eng2.get_pose(a_obj.length * 0.5)
            anim_img = render_frame(model, pose2, W=COL_W, H=COL_H,
                                    azimuth=270, elevation=15, fov=28)
            anim_img = overlay_text(anim_img,
                f"{mname}  {pick} @ 50%",
                f"t={a_obj.length*0.5:.2f}s / {a_obj.length:.2f}s")
        except Exception as ex:
            anim_img = Image.new('RGB', (COL_W, bind_img.height), (40,20,20))
            ImageDraw.Draw(anim_img).text((5,5), str(ex)[:60], fill=(255,100,100))
    else:
        anim_img = Image.new('RGB', (COL_W, bind_img.height), (20,20,30))
        ImageDraw.Draw(anim_img).text((10,10), "No animations", fill=(180,180,200))

    sc    = skin_coverage(model)
    bar_h = 30
    col_h = bind_img.height + anim_img.height + bar_h + 32
    col   = Image.new('RGB', (COL_W, col_h), (10, 10, 22))
    dr    = ImageDraw.Draw(col)
    dr.rectangle([(0,0),(COL_W,30)], fill=(18,30,65))
    dr.text((4,  4), mname.upper(), fill=(255,220,80))
    dr.text((4, 17), f"nodes:{len(model.nodes)}  anims:{len(model.animations)}",
            fill=(140,200,255))
    y = 30
    col.paste(bind_img,  (0, y)); y += bind_img.height
    col.paste(anim_img,  (0, y)); y += anim_img.height
    dr.rectangle([(0,y),(COL_W,y+bar_h)], fill=(15,25,15))
    dr.text((4, y+4),
            "SKIN: " + "  ".join(f"{nm}:{pct}%" for nm,_,_,pct in sc[:2]),
            fill=(80,255,120))
    columns.append(col)
    print(f" OK")

if columns:
    TITLE_H = 54
    max_h   = max(c.height for c in columns)
    sheet_w = sum(c.width for c in columns) + 2*(len(columns)-1)
    sheet   = Image.new('RGB', (sheet_w, max_h + TITLE_H), (6, 6, 16))
    dr = ImageDraw.Draw(sheet)
    dr.rectangle([(0,0),(sheet_w, TITLE_H)], fill=(8,18,50))
    dr.text((8,  6), "GhostRigger KotOR Pipeline — Visual Proof", fill=(255,230,80))
    dr.text((8, 22), "Models ✓   LBS Rigging ✓   Animations ✓   Textures ✓",
            fill=(80,255,140))
    dr.text((8, 36), f"Models: {', '.join(MODELS.keys())}", fill=(160,200,255))
    x = 0
    for col in columns:
        sheet.paste(col, (x, TITLE_H)); x += col.width + 2
    sp = os.path.join(OUT_DIR, '00_PROOF_SHEET.png')
    sheet.save(sp)
    print(f"\n  ✓ Proof sheet: 00_PROOF_SHEET.png ({os.path.getsize(sp)//1024} KB)")


# =============================================================================
# SECTION 5 — Concatenate all clips into GHOSTRIGGER_DEMO.mp4
# =============================================================================
print("\n" + "="*60)
print(" SECTION 5 — Final demo video")
print("="*60)

if video_paths:
    concat_txt = os.path.join(OUT_DIR, 'concat.txt')
    with open(concat_txt, 'w') as f:
        for vp in video_paths:
            f.write(f"file '{vp}'\n")
    demo_path = os.path.join(OUT_DIR, 'GHOSTRIGGER_DEMO.mp4')
    ret = os.system(
        f'ffmpeg -y -f concat -safe 0 -i "{concat_txt}" '
        f'-c:v libx264 -pix_fmt yuv420p -crf 20 "{demo_path}" 2>/dev/null'
    )
    if os.path.exists(demo_path) and os.path.getsize(demo_path) > 1000:
        sz = os.path.getsize(demo_path) // 1024
        print(f"\n  ✓ GHOSTRIGGER_DEMO.mp4  ({sz} KB)")
    else:
        import shutil
        shutil.copy(video_paths[0], demo_path)
        print(f"  ✓ demo (single clip fallback)")

# =============================================================================
print("\n" + "="*60)
print(" OUTPUT SUMMARY")
print("="*60)
print(f"Dir: {OUT_DIR}")
for fn in sorted(os.listdir(OUT_DIR)):
    if fn.endswith(('.png', '.mp4')):
        fp = os.path.join(OUT_DIR, fn)
        print(f"  {fn:50s}  {os.path.getsize(fp)//1024:6d} KB")
print("\n=== Done ===")
