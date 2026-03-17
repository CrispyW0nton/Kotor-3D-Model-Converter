#!/usr/bin/env python3
"""
GhostRigger Multi-Angle Texture-Wrap Inspection Renderer v12.9
================================================================
Renders front / left / right / back stills of KotOR models using the FULL
viewport rasteriser pipeline (same _paste_textured_triangle, TXI clamp, seam-fix,
tiling path and UV transforms as the live viewport).

v12.9 FIXES (ROOT CAUSE: KotOR skin vertex space convention):
  - CRITICAL FIX: KotOR MDL skin vertices are stored in MODEL/WORLD space,
    NOT in skin-node-local space.  The skin node's position is the BONE PIVOT
    for animation, NOT a mesh origin.  Previously _world_verts() incorrectly
    applied the skin-node world transform (wp offset) to skin vertices, which
    were already in world space.  This displaced the rendered skin mesh by the
    node's local position (e.g. btBody_front wp=(0,-1.16,1.47) was incorrectly
    added to vertices already at the correct world coordinates).
  - Non-skin trimesh/dangly nodes still correctly apply the full world transform
    (their vertices ARE in node-local space).
  - LBS formula updated: v_bind_world = raw vertex (no skin_wp addition needed).
  - Same fix applied to viewport._get_world_verts_for_node() and _lbs_vertex().
  - Verified against MDLOps binary reader (direct MDX vertex read), xoreos
    Model_KotOR loader, and visual test renders of c_bantha, c_rancor etc.

v12.8 FIXES (TEXTURE WRAPPING ROOT CAUSE — skeleton bone nodes):
  - Fixed _is_deformation_helper() in viewport.py to correctly identify
    non-skin KotOR bone helper nodes that carry a texture name but have
    NO UV data (e.g. BTHips, BTSpine1, BTHead, BTShoulders on c_bantha).
    Previously these were rendered as flat-shaded opaque geometry blobs
    that obscured the real skin mesh, causing "textures look wrong" reports.
    Root cause: the check only excluded null-textured non-skin nodes and
    _g/_dum suffixed nodes, missing textured non-skin nodes without UVs.
    Fix: any non-skin node with no UV data is now classified as a helper.
  - This affects all quadruped/creature models that use skeleton-bone proxy
    trimeshes (c_bantha, c_rancor, c_dewback, c_kraytdragon, etc.)

v12.7 FIXES (ROOT CAUSE FOUND — deep TPC/TXI analysis):
  - DXT5 alpha channel in KotOR is NOT always transparency:
      * Textures with TXI 'bumpmaptexture' use the alpha channel as a BUMP MAP
        reference — the alpha stores inverse surface roughness/specularity.
        These textures (c_rancor01, c_hutt01, c_drdassassin01) must be treated
        as FULLY OPAQUE (alpha forced to 255 for rendering).
      * Textures with TXI 'blending punchthrough' use the TPC alpha_test_threshold
        from header[4-7] as a hard-cutoff alpha test.  Pixels with alpha < threshold
        are fully discarded; above threshold are treated as opaque.
      * Head textures (DXT1, enc=2) are inherently fully opaque (no alpha).
  - TexCache now reads TPC alpha_test_threshold (header bytes 4-7) and TXI
    blending mode, and returns correctly-processed RGBA images:
      * bumpmaptexture → alpha channel = 255 (force opaque)
      * punchthrough   → alpha test via threshold, binary 0/255 result
      * default        → alpha as-is (for real transparency like hair/glass)
  - This correctly renders the Rancor, Hutt, and other creatures whose DXT5
    textures previously appeared dark (83% partial-alpha over dark background).

v12.6 FIXES:
  - Proper per-pixel z-buffer with front-to-back rendering
  - Alpha thresholding for inspection renders
  - Background changed to mid-gray (80,80,80)

v12.5 FIXES:
  - Z-buffer (per-pixel depth test) added to render_view()
  - viewport._paste_textured_triangle: degenerate-UV skip for clamped textures

v12.4 FIXES:
  - Projection uses KotOR's Z-up coordinate system
  - Correct view azimuth angles
  - Perspective-correct projection

Designed to catch:
  - Texture painted in the wrong area of the model
  - UV seam stretches / tears
  - Missing faces / holes (black gaps that aren't backface culled)
  - Clamp-mode artifacts (repeat smear on head textures)
  - V-flip issues (texture upside-down)

Usage:
    cd /path/to/GhostRigger-K1-K2
    python3 tools/render_stills_v12.py [--out path] [--W 512] [--H 512]
"""

import sys, os, math, io, struct, argparse, logging
import numpy as _np

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, _REPO)
os.environ.setdefault('DISPLAY', ':99')
logging.basicConfig(level=logging.WARNING)

from PIL import Image, ImageDraw, ImageFont

# Full viewport pipeline
from src.gui.viewport import (
    _paste_textured_triangle, _UV_SENTINEL,
    _extract_txi_from_tpc, _parse_txi_string, _apply_txi_to_node,
    _uwrap_global, _edge_has_seam_global,
    _clamp as _clampf,
)
from src.resources.game_library import GameLibrary
from src.core.mdl_parser import MDLBinaryParser
from src.gui.tpc_render_utils import _is_tpc_data, _load_tpc_bytes, _clean_tex_name
from src.core.model_data import (
    _quat_rotate, _quat_normalize_bind, _quat_normalize, _quat_mul,
    _quat_conjugate,
)

# ── Argument parsing ──────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument('--out',  default=os.path.join(_REPO, 'render_stills_v12'))
ap.add_argument('--W',    type=int, default=480)
ap.add_argument('--H',    type=int, default=480)
ap.add_argument('--game', default='K1', choices=['K1','K2','both'])
ap.add_argument('--fov',  type=float, default=50.0, help='Field of view in degrees')
ap.add_argument('--elevation', type=float, default=18.0, help='Camera elevation in degrees')
args = ap.parse_args()

OUT_DIR = args.out
os.makedirs(OUT_DIR, exist_ok=True)

# ── Game Library ──────────────────────────────────────────────────────────────
GL = GameLibrary()
_k1 = os.path.join(_REPO, 'game_data', 'k1_extracted')
_k2 = os.path.join(_REPO, 'game_data', 'k2_extracted')
if os.path.isdir(_k1): GL._scan_game(_k1, 'K1', lambda *a: None, False)
if os.path.isdir(_k2): GL._scan_game(_k2, 'K2', lambda *a: None, False)
print(f"Library ready: {len(GL._model_index)} models")

# ── Texture cache with TXI awareness ─────────────────────────────────────────
# KotOR DXT5 alpha channel has three distinct meanings:
#
# 1. BUMPMAPTEXTURE: TXI 'bumpmaptexture ...' means the alpha stores inverse
#    surface roughness / bump-map reference data — NOT transparency.
#    These textures are FULLY OPAQUE surfaces (rancor, hutt, droid assassin).
#    Fix: force alpha channel = 255 (treat as fully opaque).
#
# 2. PUNCHTHROUGH: TXI 'blending punchthrough' uses the TPC header's
#    alpha_test_threshold (bytes 4-7, float 0..1) as a binary alpha cutoff.
#    Pixels with alpha >= threshold → opaque (255), below → transparent (0).
#    The KotOR engine uses GL_ALPHA_TEST with this threshold for hard cutouts.
#
# 3. STANDARD: No special blending — alpha is real per-pixel transparency
#    (e.g. hair meshes, eye meshes, glass panels, semi-transparent effects).
#    These are rendered with standard alpha compositing.
#
# The TPC header alpha_test_threshold (bytes 4-7) is the GL_ALPHA_TEST value.
# It ranges 0..1 (float). Common values: 0.765 = rancor, 0.714 = hutt.
# When alpha_test is non-zero AND blending is punchthrough, apply the cutoff.

def _process_texture_alpha(raw_bytes: bytes, img: 'Image.Image',
                            txi_meta: dict) -> 'Image.Image':
    """
    Apply correct KotOR alpha processing to a loaded RGBA texture image.

    KotOR uses alpha channels for three purposes depending on TXI metadata:
    1. bumpmaptexture present → alpha is bump data, NOT transparency → force opaque
    2. blending punchthrough → apply alpha_test_threshold from TPC header as cutoff
    3. standard → alpha as-is (glass, hair, transparent surfaces)

    Returns a new RGBA image with correctly processed alpha channel.
    """
    if img is None:
        return img

    blending = txi_meta.get('blending', 0)       # 0=normal, 1=additive, 2=punchthrough
    has_bump = bool(txi_meta.get('bumpmaptexture', ''))

    # Case 1: bumpmaptexture present → alpha is bump map data, NOT transparency.
    # These are solid creature surfaces (rancor, hutt, assassin droid).
    # Force alpha to 255 so the texture renders as fully opaque.
    if has_bump:
        arr = _np.array(img)
        arr[:, :, 3] = 255
        return Image.fromarray(arr, 'RGBA')

    # Case 2: punchthrough blending → apply TPC alpha_test_threshold as hard cutoff.
    # Read the alpha_test_threshold float from TPC header bytes [4-7].
    if blending == 2 and raw_bytes and len(raw_bytes) >= 8:
        try:
            alpha_test_f = struct.unpack_from('<f', raw_bytes, 4)[0]
        except Exception:
            alpha_test_f = 0.5
        # Clamp to valid range and convert to 0-255 integer threshold
        alpha_test_f = max(0.0, min(1.0, alpha_test_f))
        threshold = int(alpha_test_f * 255)
        if threshold > 0:
            arr = _np.array(img)
            alpha = arr[:, :, 3]
            arr[:, :, 3] = _np.where(alpha >= threshold, 255, 0).astype(_np.uint8)
            return Image.fromarray(arr, 'RGBA')

    # Case 3: standard alpha — return as-is.
    return img


class TexCache:
    def __init__(self, gl, game):
        self.gl   = gl
        self.game = game
        self._img : dict = {}
        self._txi : dict = {}
        self._raw : dict = {}   # cache raw bytes for alpha_test_threshold lookup

    def _key(self, name): return _clean_tex_name(name).lower() if name else ''

    def _get_raw(self, name):
        """Get raw texture bytes (cached)."""
        k = self._key(name)
        if not k: return None
        if k not in self._raw:
            raw = self.gl.get_texture_data(k, self.game) or \
                  self.gl.get_texture_data(k + '01', self.game)
            self._raw[k] = raw
        return self._raw[k]

    def get_img(self, name) -> 'Image.Image | None':
        k = self._key(name)
        if not k: return None
        if k not in self._img:
            raw = self._get_raw(name)
            img = None
            if raw:
                try:
                    img = (_load_tpc_bytes(raw) if _is_tpc_data(raw)
                           else Image.open(io.BytesIO(raw))).convert('RGBA')
                    # Apply correct KotOR alpha processing based on TXI metadata
                    meta = self.get_meta(name)
                    img = _process_texture_alpha(raw, img, meta)
                except Exception: pass
            self._img[k] = img
        return self._img[k]

    def get_txi(self, name) -> str:
        k = self._key(name)
        if not k: return ''
        if k not in self._txi:
            raw = self._get_raw(name)
            txi = ''
            if raw and _is_tpc_data(raw):
                txi = _extract_txi_from_tpc(raw)
            self._txi[k] = txi
        return self._txi[k]

    def get_meta(self, name) -> dict:
        txi = self.get_txi(name)
        return _parse_txi_string(txi) if txi else _parse_txi_string('')


# ── Viewport-matching projection helpers ──────────────────────────────────────
# KotOR is Z-up.  Viewport Camera uses:
#   eye = (dist*cos(el)*cos(az), dist*cos(el)*sin(az), dist*sin(el))
#   world_up = (0, 0, 1)
#   fwd = normalize(target - eye)
#   right = normalize(cross(fwd, world_up))
#   up    = cross(right, fwd)
#   project: sx = W/2 + (cx/cz)*f*H/2,  sy = H/2 - (cy/cz)*f*H/2

def _norm3(v):
    l = math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])
    if l < 1e-9: return (0.0,0.0,1.0)
    return (v[0]/l, v[1]/l, v[2]/l)

def _cross3(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def _dot3(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

def _sub3(a, b):
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])

def _build_view(target, azimuth_deg, elevation_deg, distance, fov_deg, W, H):
    """
    Build view matrix (right, up, fwd, eye, f) for Z-up KotOR world.
    azimuth=270 (or -90): camera is at -Y → looking at front face
    azimuth=0:            camera is at +X → right side
    azimuth=90:           camera is at +Y → back
    azimuth=180:          camera is at -X → left side
    """
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    ce = math.cos(el)
    ex = target[0] + distance * ce * math.cos(az)
    ey = target[1] + distance * ce * math.sin(az)
    ez = target[2] + distance * math.sin(el)
    eye = (ex, ey, ez)

    fwd   = _norm3(_sub3(target, eye))
    world_up = (0.0, 0.0, 1.0)
    right = _norm3(_cross3(fwd, world_up))
    if _dot3(right, right) < 1e-6:
        right = _norm3(_cross3(fwd, (0.0, 1.0, 0.0)))
    up = _cross3(right, fwd)  # already unit since fwd and right are unit and orthogonal

    f = 1.0 / math.tan(math.radians(fov_deg) * 0.5)
    return right, up, fwd, eye, f

def _project_point(pt, right, up, fwd, eye, f, W, H, near=0.01):
    """Project world point to (sx, sy, depth). Returns None if behind camera."""
    dx, dy, dz = pt[0]-eye[0], pt[1]-eye[1], pt[2]-eye[2]
    cx = _dot3((dx,dy,dz), right)
    cy = _dot3((dx,dy,dz), up)
    cz = _dot3((dx,dy,dz), fwd)
    if cz < near: return None
    sx = int(W*0.5 + (cx/cz)*f*H*0.5)
    sy = int(H*0.5 - (cy/cz)*f*H*0.5)
    return sx, sy, cz

def _auto_distance(all_wv, target, azimuth_deg, elevation_deg, fov_deg, W, H, margin=1.18):
    """Compute camera distance so all world vertices fit in the viewport."""
    right, up, fwd, _, f = _build_view(target, azimuth_deg, elevation_deg, 1.0, fov_deg, W, H)
    max_r = max_u = 0.0
    for v in all_wv:
        dv = _sub3(v, target)
        pr = abs(_dot3(dv, right))
        pu = abs(_dot3(dv, up))
        if pr > max_r: max_r = pr
        if pu > max_u: max_u = pu
    half_fov = math.tan(math.radians(fov_deg)*0.5)
    extent = max(max_r, max_u, 0.001)
    return extent * margin / half_fov


# ── Model helpers ─────────────────────────────────────────────────────────────
def _is_id_q(q): return (abs(q[0])<1e-4 and abs(q[1])<1e-4
                          and abs(q[2])<1e-4 and abs(abs(q[3])-1.0)<1e-4)

def _node_world_xform(node):
    chain, n, seen = [], node, set()
    while n:
        nid = id(n)
        if nid in seen: break
        seen.add(nid); chain.append(n); n = n.parent
        if len(chain) > 512: break
    chain.reverse()
    wx=wy=wz=0.0; aq=[0,0,0,1.0]
    for i, nd in enumerate(chain):
        rx,ry,rz = _quat_rotate(aq, nd.position)
        wx+=rx; wy+=ry; wz+=rz
        rot = (_quat_normalize if i==len(chain)-1 else _quat_normalize_bind)(nd.rotation)
        aq  = _quat_mul(aq, rot)
    return (wx,wy,wz), tuple(aq), _is_id_q(aq)

def _world_verts(node, bone_transforms=None):
    """Return world-space vertices for node. Uses LBS when bone_transforms provided.

    KotOR MDL vertex space convention (verified against MDLOps, xoreos, KotorBlender):
    - SKIN nodes: vertices are stored in MODEL/WORLD space already.
      The node's position is the bone PIVOT for animation only, not a mesh origin.
      In bind pose: return raw vertices unchanged.
      In animated pose: apply LBS using (v_world - bind_bone_world) → rotate → add anim_bone_world.
    - NON-SKIN mesh nodes: vertices are in NODE-LOCAL space.
      Apply the full parent-chain world transform (rotation + translation).
    """
    wp, wo, is_id = _node_world_xform(node)
    verts = node.vertices or []

    # ── LBS path: skin mesh with bone transforms ─────────────────────────────
    if (bone_transforms and node.is_skin and
            getattr(node, 'bone_map', None) and getattr(node, 'skin_data', None)):
        out = []
        skin_data = node.skin_data
        n_sd = len(skin_data)
        for vi, v in enumerate(verts):
            # Skin vertices are ALREADY in world space - use raw position
            vbx, vby, vbz = v[0], v[1], v[2]

            if vi >= n_sd:
                out.append((vbx, vby, vbz))
                continue

            influences = skin_data[vi].influences
            if not influences:
                out.append((vbx, vby, vbz))
                continue

            rx_tot = ry_tot = rz_tot = tw = 0.0
            for bw in influences:
                if bw.weight <= 0.0: continue
                bt = bone_transforms.get(bw.bone_index)
                if bt is None: continue
                bind_wp, bind_wo, anim_wp, anim_wo = bt
                w = bw.weight
                # v_bone_local = R_bind^-1 * (v_world - T_bind)
                dx = vbx - bind_wp[0]; dy = vby - bind_wp[1]; dz = vbz - bind_wp[2]
                bind_inv = _quat_conjugate(bind_wo)
                lx, ly, lz = _quat_rotate(bind_inv, (dx, dy, dz))
                # v_anim = R_anim * v_bone_local + T_anim
                ax, ay, az = _quat_rotate(anim_wo, (lx, ly, lz))
                rx_tot += w * (ax + anim_wp[0])
                ry_tot += w * (ay + anim_wp[1])
                rz_tot += w * (az + anim_wp[2])
                tw += w

            if tw < 0.001:
                out.append((vbx, vby, vbz))
            else:
                inv_w = 1.0 / tw
                out.append((rx_tot * inv_w, ry_tot * inv_w, rz_tot * inv_w))
        return out

    # ── Bind-pose path ────────────────────────────────────────────────────────
    # SKIN nodes: vertices are already in world/model space — return as-is.
    if node.is_skin:
        return list(verts)

    # NON-SKIN nodes: vertices are in local space — apply world transform.
    out = []
    for v in verts:
        if is_id: out.append((v[0]+wp[0], v[1]+wp[1], v[2]+wp[2]))
        else:
            rx, ry, rz = _quat_rotate(wo, v)
            out.append((rx+wp[0], ry+wp[1], rz+wp[2]))
    return out


def _eval_anim_pose(model, anim_name, time=0.0):
    """
    Evaluate an animation at the given time and return a dict:
      { node_name_lower: (pos, rot) }
    where pos=(x,y,z) and rot=(qx,qy,qz,qw) are DELTA values.

    If time == 0.0, returns the first keyframe for each bone.
    """
    anim = next((a for a in model.animations if a.name == anim_name), None)
    if not anim: return {}

    pose = {}
    def walk(n):
        for ctrl in getattr(n, 'controllers', []):
            times = ctrl.get('times', [])
            vals  = ctrl.get('values', [])
            if not times or not vals: continue
            # Find the value at the requested time (linear interpolation)
            if time <= times[0]:
                val = vals[0]
            elif time >= times[-1]:
                val = vals[-1]
            else:
                for i in range(len(times)-1):
                    if times[i] <= time <= times[i+1]:
                        t = (time - times[i]) / (times[i+1] - times[i])
                        v0, v1 = vals[i], vals[i+1]
                        val = [v0[k] + t*(v1[k]-v0[k]) for k in range(len(v0))]
                        break
                else:
                    val = vals[0]
            name = ctrl.get('name','')
            nm = n.name.lower()
            if nm not in pose:
                pose[nm] = {'pos': (0.0, 0.0, 0.0), 'rot': (0.0, 0.0, 0.0, 1.0)}
            if name == 'position' and len(val) >= 3:
                pose[nm]['pos'] = (val[0], val[1], val[2])
            elif name == 'orientation' and len(val) >= 4:
                pose[nm]['rot'] = (val[0], val[1], val[2], val[3])
        for c in (getattr(n, 'children', []) or []):
            walk(c)
    for anode in anim.nodes:
        walk(anode)
    return pose


def _build_bone_transforms_for_pose(model, skin_node, anim_pose):
    """
    Build bone_transforms dict { compact_bone_index: (bind_wp, bind_wo, anim_wp, anim_wo) }
    for LBS on skin_node, applying the given anim_pose delta over the bind pose.
    """
    bone_map = getattr(skin_node, 'bone_map', None)
    if not bone_map: return {}

    transforms = {}
    for bi, bone_name in enumerate(bone_map):
        if not bone_name: continue
        # Find the bone node in the model
        bnode = model.find_node(bone_name)
        if bnode is None: continue

        # Bind pose world transform
        bind_wp, bind_wo, _ = _node_world_xform(bnode)

        # Animated world transform: apply pose delta to bind pose
        if anim_pose:
            # Walk bone hierarchy, accumulating pose deltas
            chain = []
            n = bnode
            seen = set()
            while n:
                nid = id(n)
                if nid in seen: break
                seen.add(nid)
                chain.append(n)
                n = n.parent
                if len(chain) > 512: break
            chain.reverse()

            ax = ay = az = 0.0
            aq = [0.0, 0.0, 0.0, 1.0]
            for nd in chain:
                nm = nd.name.lower()
                delta = anim_pose.get(nm, {})
                dp = delta.get('pos', (0.0, 0.0, 0.0))
                dr = delta.get('rot', (0.0, 0.0, 0.0, 1.0))

                # Node's base position + animation delta
                base_p = nd.position
                pos = (base_p[0] + dp[0], base_p[1] + dp[1], base_p[2] + dp[2])
                # Node's base rotation composed with animation delta
                base_r = _quat_normalize_bind(nd.rotation)
                rot    = _quat_mul(base_r, dr)
                rot    = _quat_normalize(rot)

                rx, ry, rz = _quat_rotate(aq, pos)
                ax += rx; ay += ry; az += rz
                aq = _quat_mul(aq, rot)

            anim_wp = (ax, ay, az)
            anim_wo = tuple(_quat_normalize(aq))
        else:
            anim_wp = bind_wp
            anim_wo = bind_wo

        transforms[bi] = (bind_wp, bind_wo, anim_wp, anim_wo)

    return transforms

def _is_deform_helper(node):
    tex = _clean_tex_name(getattr(node,'texture','') or '')
    null = not tex or tex.upper()=='NULL'
    skin = bool(getattr(node,'is_skin',False))
    uvs  = getattr(node,'uvs',[]) or []
    if skin and not null and uvs and not any(abs(u)>3 or abs(v)>3 for u,v in uvs[:20]):
        return False
    if uvs and any(abs(u)>3 or abs(v)>3 for u,v in uvs[:20]): return True
    nm = getattr(node,'name','').lower()
    if not skin and (nm.endswith('_g') or nm.endswith('_g0') or nm.endswith('_dum')): return True
    if null and not skin: return True
    if null and skin and (not uvs or all(u==0 and v==0 for u,v in uvs[:5])): return True
    return False

def _renderable(node):
    if not getattr(node,'vertices',None): return False
    if not getattr(node,'render',True):   return False
    if not getattr(node,'faces',None):    return False
    if not getattr(node,'uvs',None):      return False
    if getattr(node,'is_emitter',False) or getattr(node,'is_light',False): return False
    return not _is_deform_helper(node)

def collect(model):
    out = []
    def walk(n):
        if _renderable(n): out.append(n)
        for c in (getattr(n,'children',[]) or []): walk(c)
    if model and model.root_node: walk(model.root_node)
    return out

def load_model(name, game):
    # Build a game-specific lookup from GL.models list (avoids K1/K2 overwrite in _model_index).
    # GL._model_index may be overwritten by K2 when K1+K2 share a model name (e.g. pmha05).
    # We must find the entry with the correct game tag.
    name_l = name.lower()
    e = None
    for entry in (GL.models or []):
        if entry.resref.lower() == name_l and entry.game == game:
            e = entry
            break
    if not e:
        # Fallback: try the shared index
        e = GL._model_index.get(name_l)
    if not e: return None
    try:
        mb, mx = GL.get_model_data(e)
        if not mb: return None
        return MDLBinaryParser(mb, mx or b'').parse()
    except Exception as ex:
        print(f"  LOAD ERROR {name}: {ex}"); return None


# ── Seam-split vertex detection (mirrors viewport per-node logic) ─────────────
def _build_seam_sets(node):
    """Return (u_seam_verts, v_seam_verts) sets of vertex indices."""
    uvs   = node.uvs or []
    verts = node.vertices or []
    if not uvs or not verts: return set(), set()
    _NEAR = 0.15
    pos2grp = {}
    for vi, (vpos, vuv) in enumerate(zip(verts, uvs)):
        pk = (round(vpos[0],4), round(vpos[1],4), round(vpos[2],4))
        pos2grp.setdefault(pk,[]).append((vi,vuv))
    u_sv, v_sv = set(), set()
    for grp in pos2grp.values():
        if len(grp) < 2: continue
        us = [uv[0] for _,uv in grp]; vs_ = [uv[1] for _,uv in grp]
        if any(u<_NEAR for u in us) and any(u>1-_NEAR for u in us):
            for vi,_ in grp: u_sv.add(vi)
        if any(v<_NEAR for v in vs_) and any(v>1-_NEAR for v in vs_):
            for vi,_ in grp: v_sv.add(vi)
    return u_sv, v_sv


# ── Alpha threshold for opaque-pixel z-buffer writes ─────────────────────────
# Threshold for what counts as "opaque" when writing to the z-buffer.
# After _process_texture_alpha(), bumpmaptexture textures have alpha=255 (all
# opaque), punchthrough textures have binary 0/255 alpha.  This threshold is
# used for any remaining partial-alpha textures (hair, glass, etc.).
# Setting to 64 means: any pixel with 25%+ alpha blocks further geometry.
_ZBUF_ALPHA_THRESHOLD = 64

# Background colour for the render canvas.
# A neutral mid-gray (128,128,128) gives the best contrast against both
# dark creatures (rancor, brown/dark colors) and bright head textures.
_BG_COLOUR = (128, 128, 128, 255)


def _zbuf_test_triangle(zbuf, sx0, sy0, sx1, sy1, sx2, sy2, W, H):
    """
    Return (inside_mask, bx0, by0, bx1, by1, zbuf_region_view).

    inside_mask  – boolean array [by:by1+1, bx:bx1+1], True inside triangle.
    zbuf_region  – view into zbuf for the bounding-box region (for cheap test).

    Does NOT update zbuf — caller must do that after determining opaque pixels.
    Returns (None, ...) if triangle is entirely off-screen or degenerate.
    """
    bx0 = max(0, min(sx0, sx1, sx2))
    by0 = max(0, min(sy0, sy1, sy2))
    bx1 = min(W-1, max(sx0, sx1, sx2))
    by1 = min(H-1, max(sy0, sy1, sy2))
    if bx0 > bx1 or by0 > by1:
        return None, bx0, by0, bx1, by1, None

    xs = _np.arange(bx0, bx1+1, dtype=_np.float32)
    ys = _np.arange(by0, by1+1, dtype=_np.float32)
    gx, gy = _np.meshgrid(xs, ys)

    e0 = (sx1 - sx0) * (gy - sy0) - (sy1 - sy0) * (gx - sx0)
    e1 = (sx2 - sx1) * (gy - sy1) - (sy2 - sy1) * (gx - sx1)
    e2 = (sx0 - sx2) * (gy - sy2) - (sy0 - sy2) * (gx - sx2)

    inside = ((e0 >= 0) & (e1 >= 0) & (e2 >= 0)) | \
             ((e0 <= 0) & (e1 <= 0) & (e2 <= 0))

    zbuf_region = zbuf[by0:by1+1, bx0:bx1+1]
    return inside, bx0, by0, bx1, by1, zbuf_region


# ── Main render function ──────────────────────────────────────────────────────
import math as _m

def render_view(model, tc: TexCache, W=480, H=480, azimuth=270.0, elevation=18.0,
                fov=50.0, two_sided=True):
    """
    Render one view using the FULL _paste_textured_triangle pipeline + z-buffer.
    Uses Z-up projection matching the viewport Camera exactly.
    TXI clamp, seam-fix, tiling, UV sentinel filtering all active.

    Z-buffer (v12.6): proper per-pixel depth test with front-to-back rendering:
      - Triangles sorted FRONT-to-BACK (closest first).
      - Each triangle is rendered into a tmp canvas.
      - Opaque pixels (alpha >= _ZBUF_ALPHA_THRESHOLD) update the z-buffer.
      - Only pixels that pass the depth test (depth < zbuf[px]) are composited.
      - Eliminates both painter's back-face bleed AND DXT partial-alpha darkening.

    Azimuth angles (Z-up, KotOR convention):
       90: front (camera at +Y → face visible when model faces +Y)
        0: right side (camera at +X)
      270: back  (camera at -Y)
      180: left  (camera at -X)
    """
    img  = Image.new('RGBA', (W, H), _BG_COLOUR)
    draw = ImageDraw.Draw(img)

    # Z-buffer: float32 array, initialised to +infinity (nothing drawn yet)
    zbuf = _np.full((H, W), _np.inf, dtype=_np.float32)

    nodes = collect(model)
    if not nodes: return img.convert('RGB')

    # ── LBS pose setup: pick the best rest-pose animation ────────────────────
    # Prefer cpause1/cpause2 (idle standing poses) for the most natural look.
    # Fall back to any animation if no pause is available.
    REST_ANIMS = ('cpause1', 'cpause2', 'pause1', 'pause2')
    anim_names = [a.name.lower() for a in model.animations]
    chosen_anim = None
    for name in REST_ANIMS:
        if name in anim_names:
            chosen_anim = next(a.name for a in model.animations if a.name.lower() == name)
            break
    if chosen_anim is None and model.animations:
        chosen_anim = model.animations[0].name

    anim_pose = _eval_anim_pose(model, chosen_anim, time=0.0) if chosen_anim else {}

    # Build per-node bone transforms (once per skin node) for LBS
    _bone_xform_cache = {}  # skin_node_id → bone_transforms dict
    def _get_bone_transforms(node):
        nid = id(node)
        if nid not in _bone_xform_cache:
            _bone_xform_cache[nid] = _build_bone_transforms_for_pose(model, node, anim_pose)
        return _bone_xform_cache[nid]

    # World-space vertex cache (uses LBS for skin nodes with pose data)
    def _world_verts_posed(node):
        if (node.is_skin and getattr(node,'bone_map',None) and
                getattr(node,'skin_data',None) and anim_pose):
            bt = _get_bone_transforms(node)
            if bt:
                return _world_verts(node, bone_transforms=bt)
        return _world_verts(node)

    wvc = {id(n): _world_verts_posed(n) for n in nodes}

    # Compute world-space bounding box for camera framing
    all_wv = [v for n in nodes for v in wvc[id(n)]]
    if not all_wv: return img.convert('RGB')
    xs=[v[0] for v in all_wv]; ys=[v[1] for v in all_wv]; zs=[v[2] for v in all_wv]
    cx=(max(xs)+min(xs))/2; cy=(max(ys)+min(ys))/2; cz=(max(zs)+min(zs))/2
    target = (cx, cy, cz)

    # Auto-fit camera distance for this view angle
    dist = _auto_distance(all_wv, target, azimuth, elevation, fov, W, H)
    dist = max(dist, 0.05)

    # Build view matrix (Z-up, perspective)
    right, up_v, fwd, eye, f_fov = _build_view(target, azimuth, elevation, dist, fov, W, H)

    def proj(v):
        result = _project_point(v, right, up_v, fwd, eye, f_fov, W, H)
        if result is None: return (0, 0, -1.0)  # behind camera sentinel
        return result

    # Light direction (from upper-left-front in Z-up world)
    # Light at az≈-45, el≈50 from target
    laz, lel = _m.radians(-45), _m.radians(50)
    lx = _m.cos(lel)*_m.cos(laz)
    ly = _m.cos(lel)*_m.sin(laz)
    lz = _m.sin(lel)

    tris = []
    for node in nodes:
        wverts = wvc[id(node)]
        faces  = node.faces or []
        uvs    = node.uvs   or []
        face_uvs= getattr(node,'face_uvs',[]) or []
        nv=len(wverts); nu=len(uvs)
        has_fuv=(len(face_uvs)==len(faces))

        tex_name = _clean_tex_name(getattr(node,'texture','') or '')
        tex_img  = tc.get_img(tex_name)

        # Load TXI and apply clamp flags
        txi_meta = tc.get_meta(tex_name)
        clamp_s  = bool(txi_meta.get('clamp_s', False))
        clamp_t  = bool(txi_meta.get('clamp_t', False))

        # Build seam-split vertex sets for this node
        u_seam_verts, v_seam_verts = _build_seam_sets(node)

        for fi, face in enumerate(faces):
            if len(face) < 3: continue
            i0,i1,i2 = face[0],face[1],face[2]
            if i0>=nv or i1>=nv or i2>=nv: continue
            if i0==i1 or i1==i2 or i0==i2: continue  # degenerate

            if has_fuv:
                t0,t1,t2 = face_uvs[fi][0],face_uvs[fi][1],face_uvs[fi][2]
            else:
                t0,t1,t2 = i0,i1,i2

            uv0 = uvs[t0] if t0<nu else (0.5,0.5)
            uv1 = uvs[t1] if t1<nu else (0.5,0.5)
            uv2 = uvs[t2] if t2<nu else (0.5,0.5)

            # UV sentinel filter (exact same threshold as viewport)
            if (abs(uv0[0])>_UV_SENTINEL or abs(uv0[1])>_UV_SENTINEL or
                abs(uv1[0])>_UV_SENTINEL or abs(uv1[1])>_UV_SENTINEL or
                abs(uv2[0])>_UV_SENTINEL or abs(uv2[1])>_UV_SENTINEL):
                continue

            s0=proj(wverts[i0]); s1=proj(wverts[i1]); s2=proj(wverts[i2])
            # Skip faces with any vertex behind camera
            if s0[2]<0.001 or s1[2]<0.001 or s2[2]<0.001: continue
            depth=(s0[2]+s1[2]+s2[2])/3.0

            # World-space face normal for lighting
            v0=wverts[i0]; v1=wverts[i1]; v2=wverts[i2]
            e1=(v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2])
            e2=(v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2])
            fnx=e1[1]*e2[2]-e1[2]*e2[1]
            fny=e1[2]*e2[0]-e1[0]*e2[2]
            fnz=e1[0]*e2[1]-e1[1]*e2[0]
            fl = max(1e-8,(fnx*fnx+fny*fny+fnz*fnz)**0.5)
            fnx/=fl; fny/=fl; fnz/=fl

            ndotl = fnx*lx + fny*ly + fnz*lz
            # Two-sided lighting: abs(dot) so back-faces aren't pitch-black
            intensity = min(1.0, 0.25 + 0.75*abs(ndotl))
            shade = (int(220*intensity),)*3

            # Per-face seam flags (mirrors viewport logic exactly)
            face_has_u = bool(u_seam_verts and
                (i0 in u_seam_verts or i1 in u_seam_verts or i2 in u_seam_verts))
            face_has_v = bool(v_seam_verts and
                (i0 in v_seam_verts or i1 in v_seam_verts or i2 in v_seam_verts))

            tris.append((depth,
                         (s0[0],s0[1]), (s1[0],s1[1]), (s2[0],s2[1]),
                         uv0, uv1, uv2,
                         tex_img, shade,
                         face_has_u, face_has_v,
                         clamp_s, clamp_t))

    # Sort FRONT-to-BACK: closest triangles processed first.
    # The z-buffer prevents distant triangles from overwriting pixels already
    # written by closer triangles — eliminating back-face bleed.
    tris.sort(key=lambda t: t[0])

    for (depth, sp0, sp1, sp2, uv0, uv1, uv2,
         tex_img, shade, face_has_u, face_has_v, clamp_s, clamp_t) in tris:

        sx0, sy0 = int(sp0[0]), int(sp0[1])
        sx1, sy1 = int(sp1[0]), int(sp1[1])
        sx2, sy2 = int(sp2[0]), int(sp2[1])

        # Compute inside-triangle mask and get zbuf region view.
        inside, bx0, by0, bx1, by1, zbuf_region = _zbuf_test_triangle(
            zbuf, sx0, sy0, sx1, sy1, sx2, sy2, W, H)
        if inside is None or not inside.any():
            continue  # off-screen or degenerate

        # Fast early reject: skip if all inside pixels are already closer in zbuf.
        # (This is an optimisation — the per-pixel test below is authoritative.)
        if _np.all(zbuf_region[inside] <= depth):
            continue

        bw = bx1 - bx0 + 1
        bh = by1 - by0 + 1

        if tex_img is not None:
            # Render into a temporary canvas, then apply z-buffer per pixel.
            tmp = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            _paste_textured_triangle(
                tmp, tex_img,
                sp0, sp1, sp2,
                uv0, uv1, uv2,
                W, H, shade,
                skip_seam_u=(not face_has_u),
                skip_seam_v=(not face_has_v),
                clamp_s=clamp_s,
                clamp_t=clamp_t,
            )
            tmp_arr = _np.array(tmp.crop((bx0, by0, bx1+1, by1+1)))

            # Pixels that pass the z-buffer: inside triangle AND depth < zbuf.
            zbuf_pass = inside & (depth < zbuf_region)

            # Opaque pixels (alpha >= threshold): update z-buffer so they
            # block triangles behind them.
            opaque = tmp_arr[:, :, 3] >= _ZBUF_ALPHA_THRESHOLD
            zbuf_region[zbuf_pass & opaque] = depth

            # For inspection purposes: treat any alpha >= threshold as fully
            # opaque.  This avoids the "dark haze" from DXT partial-alpha
            # compositing over the background and makes models render clearly.
            # Semi-transparent pixels (0 < alpha < threshold) are discarded so
            # they don't darken previously-drawn surfaces.
            write_mask = zbuf_pass & (tmp_arr[:, :, 3] >= _ZBUF_ALPHA_THRESHOLD)

            if write_mask.any():
                # Build output patch: only write pixels that pass z-buffer test
                # and are opaque; make everything else fully transparent.
                out_arr = tmp_arr.copy()
                out_arr[:, :, 3] = _np.where(write_mask, 255, 0)
                patch_img = Image.fromarray(out_arr.astype(_np.uint8), 'RGBA')
                img.paste(patch_img, (bx0, by0), patch_img.split()[3])
        else:
            # Flat-shaded fallback: only draw pixels that pass z-buffer.
            v_int = max(30, shade[0] * 60 // 220)
            fill = (v_int, v_int, v_int + 15, 255)
            zbuf_pass = inside & (depth < zbuf_region)
            if not zbuf_pass.any():
                continue
            # Update z-buffer for flat triangles.
            zbuf_region[zbuf_pass] = depth
            flat_patch = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
            flat_arr = _np.zeros((bh, bw, 4), dtype=_np.uint8)
            flat_arr[zbuf_pass] = fill
            flat_img = Image.fromarray(flat_arr, 'RGBA')
            img.paste(flat_img, (bx0, by0), flat_img.split()[3])

    return img.convert('RGB')


# ── Model list ────────────────────────────────────────────────────────────────
# Deliberately chosen to exercise:
#   - creatures (large tiling meshes)
#   - character bodies (skin with multiple mesh parts)
#   - character heads (clamp 3 textures)
#   - K2 models

MODELS = [
    # Creatures — tiling / large UV
    ('c_bantha',      'K1', 'creature'),
    ('c_rancor',      'K1', 'creature'),
    ('c_kraytdragon', 'K1', 'creature'),
    ('c_kinrath',     'K1', 'creature'),
    ('c_dewback',     'K1', 'creature'),
    ('c_gammorean',   'K1', 'creature'),
    ('c_drdassassin', 'K1', 'creature/envmap'),
    ('c_hutt',        'K1', 'creature/bumpmap'),
    ('c_jawa',        'K1', 'creature'),
    # Character heads — clamp 3
    ('pfha01',        'K1', 'head/clamp3'),
    ('pfha05',        'K1', 'head/clamp3/hairUV'),
    ('pfhb01',        'K1', 'head/clamp3'),
    ('pmha01',        'K1', 'head/clamp3'),
    ('pmha05',        'K1', 'head/clamp3'),
    ('pmhb01',        'K1', 'head/clamp3'),
    # K2 models
    ('c_drexl',       'K2', 'K2 creature'),
]

# KotOR Z-up view angles:
# All KotOR models face +Y (nose/face points toward +Y).
# Camera at +Y (az=90) looks in -Y direction → sees the face ("front").
# Camera at -Y (az=270) looks in +Y direction → sees the back.
# Camera at +X (az=0) → sees the right side (from viewer's perspective = model's left).
# Camera at -X (az=180) → sees the left side (from viewer's perspective = model's right).
#
# Standard cinematic convention: Front/Right/Back/Left
#   front  = az=90  (camera at +Y → face visible)
#   right  = az=0   (camera at +X → model's left side, viewer's right)
#   back   = az=270 (camera at -Y → back of head/body)
#   left   = az=180 (camera at -X → model's right side, viewer's left)
VIEWS  = [('front', 90), ('right', 0), ('back', 270), ('left', 180)]
W, H   = args.W, args.H
FOV    = args.fov
ELEV   = args.elevation
LABEL  = 28
BORDER = 2

print(f"\nRendering {len(MODELS)} models × {len(VIEWS)} views @ {W}×{H}px  FOV={FOV}°  elev={ELEV}°")
print(f"Output: {OUT_DIR}\n")

issues_found = []
all_strips   = []

for mname, game, desc in MODELS:
    print(f"[{mname}] ({game}) {desc}", end=' ... ', flush=True)
    model = load_model(mname, game)
    if not model:
        print("SKIP (not in index)")
        continue

    tc = TexCache(GL, game)

    nodes = collect(model)
    # Report TXI clamp info
    clamp_nodes = []
    for n in nodes:
        meta = tc.get_meta(getattr(n,'texture','') or '')
        if meta.get('clamp_s') or meta.get('clamp_t'):
            clamp_nodes.append(n.name)

    row_imgs = []
    for vname, az in VIEWS:
        vi = render_view(model, tc, W=W, H=H, azimuth=az, elevation=ELEV, fov=FOV)

        # Annotate
        panel = Image.new('RGB', (W, H + LABEL), (20, 20, 20))
        panel.paste(vi, (0, LABEL))
        d = ImageDraw.Draw(panel)
        label = f"{mname} {vname}  ({desc})"
        d.text((4, 5), label, fill=(180, 220, 255))
        if clamp_nodes:
            cnames = ','.join(clamp_nodes[:4])
            if len(clamp_nodes) > 4: cnames += f'+{len(clamp_nodes)-4}'
            d.text((4, 16), f"  clamp({len(clamp_nodes)}): {cnames}", fill=(255, 220, 120))
        row_imgs.append(panel)

    # Stitch into 4-view strip
    strip_w = (W + BORDER) * len(VIEWS)
    strip_h = H + LABEL
    strip = Image.new('RGB', (strip_w, strip_h), (10, 10, 10))
    for i, panel in enumerate(row_imgs):
        strip.paste(panel, (i * (W + BORDER), 0))

    path = os.path.join(OUT_DIR, f'{mname}_{game}.png')
    strip.save(path)

    # Quality analysis
    import numpy as np
    arr = np.array(strip)
    # Background is neutral mid-gray (128,128,128).
    # Non-background: pixels where any channel deviates >30 from 128, OR
    # where the max channel is > 160 (bright model pixels) OR < 100 (dark model pixels).
    # More robust: pixels NOT close to gray (128,128,128) within ±30.
    gray_dist = (np.abs(arr[:,:,0].astype(int) - 128) +
                 np.abs(arr[:,:,1].astype(int) - 128) +
                 np.abs(arr[:,:,2].astype(int) - 128))
    # Also count dark label bar as non-model
    bg_mask = (gray_dist < 30)  # within 10 per channel of gray background
    visible = arr[~bg_mask]
    n_vis = len(visible)

    # Check for suspicious pure-black regions inside the model silhouette
    # (pure black inside a textured area = MIGHT be missing UV / wrong face winding)
    # However: some textures (beards, dark hair) legitimately render as near-black.
    # We compare against each node's texture blackness to avoid false positives.
    body_region  = arr[LABEL:, :, :]
    black_in_body = np.sum((body_region[:,:,0]<10) &
                            (body_region[:,:,1]<10) &
                            (body_region[:,:,2]<10))
    total_body = body_region.shape[0] * body_region.shape[1]
    black_pct = 100.0 * black_in_body / max(total_body, 1)

    # Compute max texture darkness for this model's textures as a baseline
    max_tex_black_pct = 0.0
    seen_tex = set()
    for n in nodes:
        tex_name = getattr(n, 'texture', '') or ''
        tex_k = _clean_tex_name(tex_name).lower()
        if tex_k and tex_k not in seen_tex:
            seen_tex.add(tex_k)
            t = tc.get_img(tex_name)
            if t:
                ta = np.array(t.convert('RGB'))
                tb = float(np.mean((ta[:,:,0]<15) & (ta[:,:,1]<15) & (ta[:,:,2]<15))) * 100
                if tb > max_tex_black_pct: max_tex_black_pct = tb
    # Threshold: flag only if black_pct > texture_black_pct * 1.5 + 3% background tolerance
    adjusted_threshold = max(8.0, max_tex_black_pct * 1.5 + 3.0)

    status = "OK"
    if n_vis < 500:
        status = "WARN: almost no visible pixels"
        issues_found.append(f"{mname}: only {n_vis} non-bg pixels")
    elif black_pct > adjusted_threshold:
        status = f"WARN: {black_pct:.1f}% pure-black body pixels (holes? tex_black={max_tex_black_pct:.1f}%)"
        issues_found.append(f"{mname}: {black_pct:.1f}% black in body (tex has {max_tex_black_pct:.1f}% black) = possible holes")

    print(f"{n_vis:,} px  black={black_pct:.1f}%(thr={adjusted_threshold:.0f}%)  clamp={len(clamp_nodes)} nodes  [{status}]")
    if clamp_nodes:
        print(f"   clamp nodes: {clamp_nodes}")

    all_strips.append((mname, game, strip))


# ── Master composite sheet ────────────────────────────────────────────────────
if all_strips:
    sheet_w = all_strips[0][2].width
    sheet_h = sum(s.height for _,_,s in all_strips) + 6 * len(all_strips)
    sheet = Image.new('RGB', (sheet_w, sheet_h), (10, 10, 10))
    y = 0
    for _, _, s in all_strips:
        sheet.paste(s, (0, y)); y += s.height + 6
    comp_path = os.path.join(OUT_DIR, '_composite_v12.png')
    sheet.save(comp_path)
    print(f"\nComposite sheet: {comp_path}  ({sheet_w}×{sheet_h})")

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"Rendered {len(all_strips)}/{len(MODELS)} models")
if issues_found:
    print(f"\nISSUES FOUND ({len(issues_found)}):")
    for iss in issues_found:
        print(f"  !! {iss}")
else:
    print("No rendering issues detected.")
print('='*60)
