"""
Headless render test — generates front/back/left/right views of multiple models
to diagnose texture wrapping issues with TPC/TPA textures.

Usage:
    cd GhostRigger-K1-K2
    python3 tools/headless_render_test.py

Architecture: Uses three tools as designed:
  Tool 1 – GameLibrary  (src/resources/game_library.py)
  Tool 2 – MDLBinaryParser (src/core/mdl_parser.py)
  Tool 3 – tpc_render_utils + PIL rasterizer (src/gui/tpc_render_utils.py)

v2 changes:
  - apply_world_transforms=True: applies bind-pose world transforms to all
    vertices before rendering, matching the viewport's _get_world_verts_for_node
    behaviour.  Previously raw local-space vertices were used, causing the bantha
    "mouth on tail" and "upside-down body" artefacts.
  - renderable_only=True: skips nodes with render=False and deformation helpers,
    matching the viewport's _is_deformation_helper filter.
  - World-space bounding box used for camera framing (not raw-vertex bbox).
  - Face normals computed in world space for correct shading.
"""
import sys, os, math, io, struct, logging

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_SRC_ROOT  = os.path.join(_REPO_ROOT, 'src')
sys.path.insert(0, _SRC_ROOT)    # resources.game_library, core.mdl_parser, etc.
sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault('DISPLAY', ':99')
logging.basicConfig(level=logging.WARNING)

from PIL import Image, ImageDraw

# Tool 1: Game library (archive reader)
from resources.game_library import GameLibrary
# Tool 2: MDL/MDX binary parser
from core.mdl_parser import MDLBinaryParser
# Tool 3 (utils): Pure-Python TPC loader + UV-mapped triangle renderer
from gui.tpc_render_utils import (
    _is_tpc_data, _load_tpc_bytes, _clean_tex_name,
    _paste_textured_triangle, _UV_SENTINEL
)
# World-transform helpers from model_data
from core.model_data import (
    _quat_rotate, _quat_normalize_bind, _quat_normalize, _quat_mul
)


# ── Game Library ──────────────────────────────────────────────────────────────
GL = GameLibrary()
GL._scan_game(os.path.join(_REPO_ROOT, 'game_data', 'k1_extracted'), 'K1', lambda *a: None, False)
GL._scan_game(os.path.join(_REPO_ROOT, 'game_data', 'k2_extracted'), 'K2', lambda *a: None, False)
print(f"Library: models={len(GL._model_index)}")


# ── Texture cache ─────────────────────────────────────────────────────────────
class HeadlessTexCache:
    """Thin cache that loads TPC/TGA textures via GameLibrary."""
    def __init__(self, gl, game):
        self.gl   = gl
        self.game = game
        self._c   = {}

    def get(self, name):
        if not name:
            return None
        k = _clean_tex_name(name).lower()
        if k in self._c:
            return self._c[k]
        # Try exact name first, then digit-append fallback
        raw = self.gl.get_texture_data(k, self.game)
        if not raw:
            raw = self.gl.get_texture_data(k + '01', self.game)
        img = None
        if raw:
            if _is_tpc_data(raw):
                img = _load_tpc_bytes(raw)
            else:
                try:
                    img = Image.open(io.BytesIO(raw)).convert('RGBA')
                except Exception:
                    pass
        if img and img.mode != 'RGBA':
            img = img.convert('RGBA')
        self._c[k] = img
        return img


# ── Model loader ──────────────────────────────────────────────────────────────
def load_model(name, game):
    k = name.lower()
    entry = GL._model_index.get(k)
    if not entry:
        return None
    try:
        mdl_bytes, mdx_bytes = GL.get_model_data(entry)
        if not mdl_bytes:
            return None
        parser = MDLBinaryParser(mdl_bytes, mdx_bytes or b'')
        return parser.parse()
    except Exception as e:
        print(f"  ERROR loading {name}: {e}")
        return None


# ── World-transform helpers ───────────────────────────────────────────────────
def _is_identity_quat(q):
    """Return True if quaternion (xyzw) is effectively identity."""
    x, y, z, w = q
    return (abs(x) < 1e-4 and abs(y) < 1e-4 and abs(z) < 1e-4 and
            abs(abs(w) - 1.0) < 1e-4)


def _get_node_world_transform(node):
    """
    Compute bind-pose world transform for a node, matching the viewport's
    _node_world_transform logic (bind-pose, no animation).

    Returns (world_pos, world_quat, is_identity) where:
      - world_pos  : (wx, wy, wz) world-space position
      - world_quat : (x, y, z, w) orientation quaternion
      - is_identity: True when orientation is effectively identity

    Parent nodes in the chain use _quat_normalize_bind to collapse 180° X-axis
    rotations (the NWN/KotOR exporter convention), while the leaf node keeps its
    actual rotation for correct vertex orientation.
    """
    chain = []
    n = node
    visited = set()
    while n is not None:
        nid = id(n)
        if nid in visited:
            break
        visited.add(nid)
        chain.append(n)
        n = n.parent
        if len(chain) > 512:
            break
    chain.reverse()  # root first

    wx, wy, wz = 0.0, 0.0, 0.0
    aq = [0.0, 0.0, 0.0, 1.0]  # identity xyzw
    last_i = len(chain) - 1

    for i, nd in enumerate(chain):
        lx, ly, lz = nd.position
        rx, ry, rz = _quat_rotate(aq, (lx, ly, lz))
        wx += rx;  wy += ry;  wz += rz
        # Leaf: keep actual rotation for vertex transform
        # Parents: collapse 180°-flips for correct position accumulation
        if i == last_i:
            bind_rot = _quat_normalize(nd.rotation)
        else:
            bind_rot = _quat_normalize_bind(nd.rotation)
        aq = _quat_mul(aq, bind_rot)

    is_id = _is_identity_quat(aq)
    return (wx, wy, wz), tuple(aq), is_id


def _apply_vertex_transform(v, wp, wo, is_id):
    """Transform vertex v from node-local to world space."""
    if is_id:
        return (v[0] + wp[0], v[1] + wp[1], v[2] + wp[2])
    rx, ry, rz = _quat_rotate(wo, v)
    return (rx + wp[0], ry + wp[1], rz + wp[2])


def _get_world_verts(node):
    """Return all vertices of node in world space."""
    verts = node.vertices or []
    if not verts:
        return []
    wp, wo, is_id = _get_node_world_transform(node)
    return [_apply_vertex_transform(v, wp, wo, is_id) for v in verts]


# ── Deformation-helper filter (mirrors OBJExporter._is_deformation_helper) ──
def _is_deformation_helper(node):
    """
    Detect KotOR deformation-helper mesh nodes that should NOT be rendered.
    Mirrors the logic in viewport.py::FrameRenderer._is_deformation_helper.
    """
    tex = _clean_tex_name(getattr(node, 'texture', '') or '')
    is_null_tex = (not tex or tex.upper() == 'NULL')
    is_skin = bool(getattr(node, 'is_skin', False))
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


def _is_renderable(node):
    """Return True if this node should be rendered."""
    if not getattr(node, 'vertices', None):
        return False
    if not getattr(node, 'render', True):
        return False
    if not getattr(node, 'faces', None):
        return False
    if not getattr(node, 'uvs', None):
        return False
    if getattr(node, 'is_emitter', False) or getattr(node, 'is_light', False):
        return False
    if _is_deformation_helper(node):
        return False
    return True


# ── Node collector ────────────────────────────────────────────────────────────
def collect_renderable_nodes(model):
    """
    Walk the node tree and collect renderable mesh nodes.

    v2: Uses the same filtering as the viewport and OBJ exporter:
      - render=True only (not deformation helpers, not engine-internal proxies)
      - Has vertices, faces, AND UVs
      - Not an emitter or light
    """
    nodes = []
    def walk(n):
        if _is_renderable(n):
            nodes.append(n)
        for c in (getattr(n, 'children', []) or []):
            walk(c)
    if hasattr(model, 'root_node') and model.root_node:
        walk(model.root_node)
    return nodes


# ── Renderer ─────────────────────────────────────────────────────────────────
def render_view(model, tex_cache, W=400, H=400, azimuth=0.0, elevation=20.0):
    """
    Render a model from the given azimuth/elevation angles.
    Returns a PIL RGB Image.

    v2 fixes:
      - Applies bind-pose world transforms to all vertices before rendering.
        Previously raw node-local vertices were used, causing displaced geometry.
      - Filters to renderable nodes only (same as viewport and OBJ exporter).
      - Uses world-space bounding box for camera framing.
      - Computes face normals in world space for correct lighting.
    """
    img  = Image.new('RGB', (W, H), (18, 18, 40))
    draw = ImageDraw.Draw(img)

    # Collect renderable nodes (render=True, has verts+faces+uvs, not deform helpers)
    mesh_nodes = collect_renderable_nodes(model)
    if not mesh_nodes:
        return img

    # Build world-space vertex cache for each node
    world_verts_cache = {}
    for n in mesh_nodes:
        world_verts_cache[id(n)] = _get_world_verts(n)

    # Collect all WORLD-SPACE vertices for bounding-box auto-scale
    # Using world-space ensures the camera frame matches the actual rendered shape.
    all_wv = []
    for n in mesh_nodes:
        all_wv.extend(world_verts_cache[id(n)])
    if not all_wv:
        return img

    xs=[v[0] for v in all_wv]; ys=[v[1] for v in all_wv]; zs=[v[2] for v in all_wv]
    cx=(max(xs)+min(xs))/2; cy=(max(ys)+min(ys))/2; cz=(max(zs)+min(zs))/2
    sz=max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs), 0.01)
    scale=min(W,H)*0.72/sz

    az=math.radians(azimuth)
    el=math.radians(elevation)
    cos_az,sin_az=math.cos(az),math.sin(az)
    cos_el,sin_el=math.cos(el),math.sin(el)

    def proj(v):
        vx=v[0]-cx; vy=v[1]-cy; vz=v[2]-cz
        px=vx*cos_az - vz*sin_az; py=vy; pz=vx*sin_az + vz*cos_az
        py2= py*cos_el + pz*sin_el
        pz2=-py*sin_el + pz*cos_el
        return (int(W/2+px*scale), int(H/2-py2*scale), pz2)

    # Fixed upper-left light direction
    lx=math.cos(math.radians(60))*math.sin(math.radians(45))
    ly=math.sin(math.radians(60))
    lz=-math.cos(math.radians(60))*math.cos(math.radians(45))

    tris = []
    for n in mesh_nodes:
        # Use world-space vertices (v2 fix)
        wverts   = world_verts_cache[id(n)]
        faces    = n.faces    or []
        uvs      = n.uvs      or []
        face_uvs = getattr(n, 'face_uvs', []) or []
        nv=len(wverts); nu=len(uvs)
        has_fuv=(len(face_uvs)==len(faces))

        tex_name = getattr(n,'texture','') or ''
        tex_img  = tex_cache.get(tex_name)

        for fi, face in enumerate(faces):
            if len(face) < 3: continue
            i0,i1,i2=face[0],face[1],face[2]
            if i0>=nv or i1>=nv or i2>=nv: continue

            if has_fuv:
                t0,t1,t2=face_uvs[fi][0],face_uvs[fi][1],face_uvs[fi][2]
            else:
                t0,t1,t2=i0,i1,i2

            uv0=uvs[t0] if t0<nu else (0.5,0.5)
            uv1=uvs[t1] if t1<nu else (0.5,0.5)
            uv2=uvs[t2] if t2<nu else (0.5,0.5)

            # Project world-space vertices to screen
            s0=proj(wverts[i0]); s1=proj(wverts[i1]); s2=proj(wverts[i2])
            depth=(s0[2]+s1[2]+s2[2])/3.0

            # Compute face normal in world space for correct lighting
            v0=wverts[i0]; v1=wverts[i1]; v2=wverts[i2]
            e1=(v1[0]-v0[0],v1[1]-v0[1],v1[2]-v0[2])
            e2=(v2[0]-v0[0],v2[1]-v0[1],v2[2]-v0[2])
            fnx=e1[1]*e2[2]-e1[2]*e2[1]
            fny=e1[2]*e2[0]-e1[0]*e2[2]
            fnz=e1[0]*e2[1]-e1[1]*e2[0]
            fn_len=max(1e-8,(fnx*fnx+fny*fny+fnz*fnz)**0.5)
            fnx/=fn_len; fny/=fn_len; fnz/=fn_len
            ndotl=abs(fnx*lx+fny*ly+fnz*lz)
            intensity=min(1.0, 0.25 + 0.75*ndotl)
            shade=(int(215*intensity),)*3

            tris.append((depth, s0,s1,s2, uv0,uv1,uv2, tex_img, shade))

    # Back-to-front (painter's algorithm)
    tris.sort(key=lambda t: -t[0])

    for depth,s0,s1,s2,uv0,uv1,uv2,tex_img,shade in tris:
        sp0=(s0[0],s0[1]); sp1=(s1[0],s1[1]); sp2=(s2[0],s2[1])
        if tex_img:
            _paste_textured_triangle(img, tex_img, sp0,sp1,sp2, uv0,uv1,uv2, W,H, shade)
        else:
            fill=(int(70*shade[0]//215),)*3
            draw.polygon([sp0,sp1,sp2], fill=fill)

    return img


# ── Models to test ────────────────────────────────────────────────────────────
MODELS = [
    # (name, game, description)
    ('c_bantha',      'K1', 'K1 DXT5-512 TPA'),
    ('c_rancor',      'K1', 'K1 DXT5-512 TPA'),
    ('c_kinrath',     'K1', 'K1 DXT1-512 TPA'),
    ('c_gammorean',   'K1', 'K1 DXT1-256 TPA'),
    ('c_dewback',     'K1', 'K1 DXT1-256 TPA'),
    ('c_jawa',        'K1', 'K1 DXT1-512 TPA'),
    ('c_khounda',     'K1', 'K1 DXT1-512 TPA'),
    ('c_ithorian',    'K1', 'K1 DXT1-512 TPA'),
    ('c_drdassassin', 'K1', 'K1 DXT5-512 TPA'),
    ('c_kraytdragon', 'K1', 'K1 DXT1-1024 TPA'),
    ('c_hutt',        'K1', 'K1 DXT5-512 TPA'),
    ('c_drexl',       'K2', 'K2 DXT1-512 TPA'),
]

# FIX-LABEL: KotOR creatures face +Y (nose/eyes at the +Y end of the model).
# The proj() azimuth rotates in the XZ plane (Y is the viewing/forward axis).
#   az=0   → camera along +Y looking toward -Y → sees the face     → 'front'
#   az=90  → camera along +X looking toward -X → right profile     → 'right'
#   az=180 → camera along -Y looking toward +Y → sees rear/tail    → 'back'
#   az=270 → camera along -X looking toward +X → left profile      → 'left'
VIEWS   = [('front', 0), ('right', 90), ('back', 180), ('left', 270)]
PANEL_W = 350
PANEL_H = 350
LABEL_H = 24
OUT_DIR = os.path.join(_REPO_ROOT, 'render_test_output')
os.makedirs(OUT_DIR, exist_ok=True)

all_strips = []

for mname, game, note in MODELS:
    print(f"\n[{mname}] ({game}) {note}")
    model = load_model(mname, game)
    if not model:
        print(f"  SKIP: not in model index")
        continue

    tc  = HeadlessTexCache(GL, game)
    tex = tc.get(mname + '01') or tc.get(mname)
    if tex:
        print(f"  texture: {tex.size[0]}x{tex.size[1]} {tex.mode}  OK")
    else:
        print(f"  texture: NOT FOUND")

    # Report renderable node count
    renderable = collect_renderable_nodes(model)
    print(f"  renderable nodes: {len(renderable)} – {[n.name for n in renderable]}")

    row_imgs = []
    for vname, az in VIEWS:
        vi = render_view(model, tc, W=PANEL_W, H=PANEL_H, azimuth=az, elevation=20.0)
        labeled = Image.new('RGB', (PANEL_W, PANEL_H+LABEL_H), (8, 8, 20))
        labeled.paste(vi, (0, LABEL_H))
        d = ImageDraw.Draw(labeled)
        d.text((4, 4), f"{mname} {vname} [{note}]", fill=(170, 170, 255))
        row_imgs.append(labeled)
        print(f"  {vname}", end=' ', flush=True)
    print()

    strip_w = PANEL_W * len(VIEWS)
    strip_h = PANEL_H + LABEL_H
    strip   = Image.new('RGB', (strip_w, strip_h), (8, 8, 20))
    for i, vi in enumerate(row_imgs):
        strip.paste(vi, (i*PANEL_W, 0))

    path = os.path.join(OUT_DIR, f'{mname}_{game}.png')
    strip.save(path)
    print(f"  -> {path}")
    all_strips.append((mname, strip))

    # Quick quality check
    import numpy as np
    arr = np.array(strip)
    # Exclude background (18,18,40) and labels (8,8,20)
    non_bg = arr[arr[:,:,0] > 25]
    if len(non_bg) > 100:
        print(f"  Quality: {len(non_bg)} colored pixels, mean RGB=({non_bg[:,0].mean():.0f},{non_bg[:,1].mean():.0f},{non_bg[:,2].mean():.0f})")
    else:
        print(f"  WARNING: only {len(non_bg)} non-background pixels — model may not be rendering!")

# ── Composite sheet ───────────────────────────────────────────────────────────
if all_strips:
    sh = sum(s.height for _,s in all_strips) + 8*len(all_strips)
    sw = all_strips[0][1].width
    sheet = Image.new('RGB', (sw, sh), (4, 4, 12))
    y = 0
    for _,s in all_strips:
        sheet.paste(s, (0, y)); y += s.height + 8
    sp = os.path.join(OUT_DIR, '_composite.png')
    sheet.save(sp)
    print(f"\nComposite: {sp}  ({sw}x{sh})")

print("Done.")
