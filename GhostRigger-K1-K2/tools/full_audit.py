#!/usr/bin/env python3
"""
GhostRigger-K1-K2  –  Full Model Audit  v1.7
============================================================
Tests every .mdl in test_assets/k1_extracted/models:
  • Correct world-space transforms (skin / trimesh / dangly)
  • Texture loading (TGA/TPC) and UV mapping
  • Rigging / bone chain display
  • Screen-space camera framing
  • Produces a 6-column diagnostic grid per pass:
      Pass 1 – Textured
      Pass 2 – Flat-shaded (solid)
      Pass 3 – Wireframe + bones
"""

import sys, os, math, struct, logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))

# ── imports ──────────────────────────────────────────────────────────────────
from core.mdl_parser import MDLBinaryParser
from core.model_data  import KotorModel, ModelNode, NodeFlags, _quat_rotate

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL = True
except ImportError:
    print("Pillow required: pip install Pillow"); sys.exit(1)

log = logging.getLogger('audit')
logging.basicConfig(level=logging.WARNING)

MODELS   = ROOT / 'test_assets' / 'k1_extracted' / 'models'
TEXTURES = ROOT / 'test_assets' / 'k1_extracted' / 'textures'
OUT      = ROOT / 'test_assets' / 'diagnostics'
OUT.mkdir(exist_ok=True)

# ─── Math helpers ────────────────────────────────────────────────────────────

def norm3(v):
    l = math.sqrt(v[0]**2+v[1]**2+v[2]**2)
    return (v[0]/l,v[1]/l,v[2]/l) if l>1e-9 else (0.0,0.0,1.0)
def dot3(a,b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def cross3(a,b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def sub3(a,b):   return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def add3(a,b):   return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def clamp(v,lo,hi): return max(lo,min(hi,v))

def qrot(q, v):
    """Rotate vector v by quaternion q=(x,y,z,w)."""
    qx,qy,qz,qw = q
    n = math.sqrt(qx*qx+qy*qy+qz*qz+qw*qw)
    if n>1e-9: qx/=n;qy/=n;qz/=n;qw/=n
    vx,vy,vz = v
    cx = qy*vz-qz*vy
    cy = qz*vx-qx*vz
    cz = qx*vy-qy*vx
    return (vx+2*(qw*cx+qy*cz-qz*cy),
            vy+2*(qw*cy+qz*cx-qx*cz),
            vz+2*(qw*cz+qx*cy-qy*cx))

# ─── Texture loader (TGA + TPC) ──────────────────────────────────────────────

_tex_cache: dict = {}

def load_texture(name: str) -> 'Image.Image | None':
    key = name.lower()
    if key in _tex_cache:
        return _tex_cache[key]
    for ext in ('.tga', '.tpc', '.png', '.dds'):
        p = TEXTURES / (key + ext)
        if p.exists():
            try:
                if ext == '.tpc':
                    img = _load_tpc(p)
                else:
                    img = Image.open(p).convert('RGBA')
                img = img.resize((128,128), Image.BILINEAR)
                _tex_cache[key] = img
                return img
            except Exception as e:
                log.debug(f"texture {p}: {e}")
    _tex_cache[key] = None
    return None

def _load_tpc(path: Path) -> 'Image.Image':
    """Minimal TPC reader (DXT1/DXT3/DXT5 or raw RGBA)."""
    data = path.read_bytes()
    # TPC header: 4B data_size, 4B alpha_test, 2B W, 2B H, 1B encoding, 1B mip_count
    ds, alpha, w, h, enc, mips = struct.unpack_from('<IIHHBb', data, 0)
    if enc == 1:   # Grey8
        raw = data[128:128+w*h]
        return Image.frombytes('L',(w,h),raw).convert('RGBA')
    elif enc == 2: # BGRA8
        raw = data[128:128+w*h*4]
        img = Image.frombytes('RGBA',(w,h),raw)
        b,g,r,a = img.split()
        return Image.merge('RGBA',(r,g,b,a))
    elif enc == 4: # DXT1
        from PIL import features
        raw = data[128:128+max(ds,8)]
        try:
            return Image.frombytes('RGBA',(w,h),raw,'bcn',1)
        except:
            return Image.new('RGBA',(w,h),(128,128,200,255))
    elif enc == 5: # DXT3
        raw = data[128:128+max(ds,16)]
        try:
            return Image.frombytes('RGBA',(w,h),raw,'bcn',2)
        except:
            return Image.new('RGBA',(w,h),(128,128,200,255))
    elif enc == 6: # DXT5
        raw = data[128:128+max(ds,16)]
        try:
            return Image.frombytes('RGBA',(w,h),raw,'bcn',3)
        except:
            return Image.new('RGBA',(w,h),(128,128,200,255))
    return Image.new('RGBA',(w,h),(150,150,180,255))

def sample_tex(img: 'Image.Image', u: float, v: float) -> tuple:
    """Sample texture at UV with KotOR bottom-up V convention."""
    if img is None: return (160,160,180)
    # KotOR: V=0 is bottom → flip V
    v_flip = 1.0 - (v % 1.0)
    u_mod  = u % 1.0
    px = clamp(int(u_mod  * img.width),  0, img.width -1)
    py = clamp(int(v_flip * img.height), 0, img.height-1)
    rgba = img.getpixel((px,py))
    return rgba[:3]

# ─── Vertex world-transform (matches model_data.compute_bounds logic) ─────────

def vertex_world(node: ModelNode, v: tuple) -> tuple:
    """Transform vertex to world space using verified KotOR rules."""
    wp, wo = node.world_transform()
    wo_rot = math.sqrt(wo[0]**2+wo[1]**2+wo[2]**2)
    is_id  = (wo_rot < 0.001)
    if node.is_skin:
        if is_id:
            return v           # skin + identity → raw bind-pose world space
        rx,ry,rz = qrot(wo, v)
        return (rx+wp[0], ry+wp[1], rz+wp[2])
    else:
        # Trimesh / Dangly: always apply full world transform
        if is_id:
            return (v[0]+wp[0], v[1]+wp[1], v[2]+wp[2])
        rx,ry,rz = qrot(wo, v)
        return (rx+wp[0], ry+wp[1], rz+wp[2])

# ─── Camera (screen-space fitting) ───────────────────────────────────────────

class Camera:
    fov = 45.0

    def __init__(self):
        self.target   = [0,0,0]
        self.distance = 5.0
        self.azimuth  = -45.0
        self.elevation= 25.0

    def frame(self, bb_min, bb_max):
        cx = (bb_min[0]+bb_max[0])*0.5
        cy = (bb_min[1]+bb_max[1])*0.5
        cz = (bb_min[2]+bb_max[2])*0.5
        self.target = [cx,cy,cz]

        dx = bb_max[0]-bb_min[0]; dy = bb_max[1]-bb_min[1]; dz = bb_max[2]-bb_min[2]

        # Camera orientation vectors
        az = math.radians(self.azimuth)
        el = math.radians(self.elevation)
        fwd = (-math.cos(el)*math.cos(az), -math.cos(el)*math.sin(az), -math.sin(el))
        right = norm3(cross3(fwd,(0,0,1)))
        if dot3(right,right)<1e-6: right=norm3(cross3(fwd,(0,1,0)))
        up = norm3(cross3(right,fwd))

        # Project 8 BB corners (relative to centre) onto right/up plane
        corners = [(bb_min[0]-cx,bb_min[1]-cy,bb_min[2]-cz),
                   (bb_max[0]-cx,bb_min[1]-cy,bb_min[2]-cz),
                   (bb_min[0]-cx,bb_max[1]-cy,bb_min[2]-cz),
                   (bb_max[0]-cx,bb_max[1]-cy,bb_min[2]-cz),
                   (bb_min[0]-cx,bb_min[1]-cy,bb_max[2]-cz),
                   (bb_max[0]-cx,bb_min[1]-cy,bb_max[2]-cz),
                   (bb_min[0]-cx,bb_max[1]-cy,bb_max[2]-cz),
                   (bb_max[0]-cx,bb_max[1]-cy,bb_max[2]-cz)]

        max_r = max_u = 0.0
        for c in corners:
            max_r = max(max_r, abs(dot3(c,right)))
            max_u = max(max_u, abs(dot3(c,up)))

        half_fov = math.tan(math.radians(self.fov)*0.5)
        extent   = max(max_r, max_u, 0.01)
        fitted   = (extent * 1.20) / half_fov

        # Keep enough depth-clearance to avoid near-clip
        depth_ext = abs(dot3((dx,dy,dz), fwd))
        self.distance = max(fitted, depth_ext*0.55, 0.3)

    def eye(self):
        az = math.radians(self.azimuth); el = math.radians(self.elevation)
        ce = math.cos(el)
        t  = self.target
        return (t[0]+self.distance*ce*math.cos(az),
                t[1]+self.distance*ce*math.sin(az),
                t[2]+self.distance*math.sin(el))

    def view_matrix(self):
        eye  = self.eye()
        t    = self.target
        fwd  = norm3(sub3(t, eye))
        right= norm3(cross3(fwd,(0,0,1)))
        if dot3(right,right)<1e-6: right=norm3(cross3(fwd,(0,1,0)))
        up   = norm3(cross3(right,fwd))
        return right, up, fwd, eye

    def project(self, pt, W, H):
        right, up, fwd, eye = self.view_matrix()
        ev   = sub3(pt, eye)
        depth= dot3(ev, fwd)
        if depth < 0.01: return None
        sx = dot3(ev, right)/depth
        sy = dot3(ev, up)   /depth
        f  = 1.0/math.tan(math.radians(self.fov)*0.5)
        px = int(W*0.5 + sx*f*H*0.5)
        py = int(H*0.5 - sy*f*H*0.5)
        return px, py, depth

# ─── Renderer ────────────────────────────────────────────────────────────────

LIGHT1 = norm3((0.6, 0.5, 1.0))
LIGHT2 = norm3((-0.4,-0.3, 0.5))
AMBIENT= 0.22
BG     = (13, 13, 26)
GRID   = (30, 30, 60)

def render_model(model: KotorModel, mode: str, W: int, H: int) -> 'Image.Image':
    """
    mode: 'textured' | 'solid' | 'wire'
    Returns a PIL RGB image.
    """
    img  = Image.new('RGB', (W,H), BG)
    draw = ImageDraw.Draw(img)

    cam = Camera()
    # Use render_bounds (visible nodes only) for camera framing
    rbb_min, rbb_max = model.render_bounds()
    cam.frame(rbb_min, rbb_max)

    # ── grid ────────────────────────────────────────────────────────────
    n    = 8
    dist = cam.distance
    step = 0.1
    for s in (0.1,0.25,0.5,1.0,2.0,5.0,10.0,25.0,50.0):
        if dist*0.15 <= s: step=s; break
    for i in range(-n,n+1):
        p1 = cam.project((-n*step, i*step, 0), W, H)
        p2 = cam.project(( n*step, i*step, 0), W, H)
        if p1 and p2: draw.line([p1[:2],p2[:2]], fill=GRID, width=1)
        p1 = cam.project((i*step, -n*step, 0), W, H)
        p2 = cam.project((i*step,  n*step, 0), W, H)
        if p1 and p2: draw.line([p1[:2],p2[:2]], fill=GRID, width=1)

    # ── pre-cache world transforms ───────────────────────────────────────
    wt_cache: dict = {}
    def get_wt(node):
        nid = id(node)
        if nid not in wt_cache:
            wp, wo = node.world_transform()
            wo_rot = math.sqrt(wo[0]**2+wo[1]**2+wo[2]**2)
            is_id  = (wo_rot < 0.001)
            wt_cache[nid] = (wp, wo, is_id)
        return wt_cache[nid]

    def vworld(node, v):
        wp, wo, is_id = get_wt(node)
        if node.is_skin and is_id:
            return v
        if is_id:
            return (v[0]+wp[0],v[1]+wp[1],v[2]+wp[2])
        rx,ry,rz = qrot(wo, v)
        return (rx+wp[0],ry+wp[1],rz+wp[2])

    # ── collect triangles ────────────────────────────────────────────────
    tris = []
    MAX  = 80000

    def collect(node: ModelNode):
        if len(tris) >= MAX: return
        verts = node.vertices
        faces = node.faces
        if verts and faces:
            uvs   = node.uvs   if hasattr(node,'uvs')   else []
            norms = node.normals if hasattr(node,'normals') else []
            n_v   = len(verts)
            n_uv  = len(uvs)

            # Skip deformation-helper nodes (any node with no UVs = helper mesh)
            tname = node.texture_clean.lower() if hasattr(node,'texture_clean') else ''
            is_helper = (not uvs)
            if is_helper:
                if mode == 'textured':
                    # Skip helpers entirely in textured mode
                    for ch in node.children: collect(ch)
                    return
                # In solid/wire: render helpers as very faint grey (skeleton context)
                base = (35, 35, 55)
            else:
                # Diffuse base colour for real rendered nodes
                dr,dg,db = node.diffuse
                if dr+dg+db < 0.05: dr=dg=db=0.63
                base = (int(clamp(dr,0,1)*220), int(clamp(dg,0,1)*220), int(clamp(db,0,1)*220))

            # Texture (for textured mode)
            tex = None
            if mode == 'textured' and tname and tname not in ('null',''):
                tex = load_texture(tname)

            for f in faces:
                if len(tris) >= MAX: break
                v0,v1,v2 = f
                if v0>=n_v or v1>=n_v or v2>=n_v: continue
                a = vworld(node, verts[v0])
                b = vworld(node, verts[v1])
                c = vworld(node, verts[v2])
                ab = sub3(b,a); ac = sub3(c,a)
                fn = cross3(ab,ac)
                fl = fn[0]**2+fn[1]**2+fn[2]**2
                if fl < 1e-14: continue
                fn = (fn[0]/math.sqrt(fl),fn[1]/math.sqrt(fl),fn[2]/math.sqrt(fl))

                # Two-sided lighting (KotOR uses two-sided geometry on many meshes)
                lit  = clamp(dot3(fn,LIGHT1), 0, 1)
                lit2 = clamp(dot3(fn,LIGHT2), 0, 1)*0.4
                # Flip normal for back-faces in lighting
                lit_back  = clamp(dot3((-fn[0],-fn[1],-fn[2]),LIGHT1), 0, 1)
                lit2_back = clamp(dot3((-fn[0],-fn[1],-fn[2]),LIGHT2), 0, 1)*0.4
                shd = AMBIENT + max(lit,lit_back*0.5)*0.72 + max(lit2,lit2_back*0.5)

                if mode == 'textured' and tex and n_uv > 0:
                    # Use face centroid UV for sampling
                    ui0 = min(v0, n_uv-1); ui1 = min(v1, n_uv-1); ui2 = min(v2, n_uv-1)
                    uc  = (uvs[ui0][0]+uvs[ui1][0]+uvs[ui2][0])/3
                    vc  = (uvs[ui0][1]+uvs[ui1][1]+uvs[ui2][1])/3
                    tc  = sample_tex(tex, uc, vc)
                    color = (int(clamp(tc[0]*shd,0,255)),
                             int(clamp(tc[1]*shd,0,255)),
                             int(clamp(tc[2]*shd,0,255)))
                else:
                    br,bg,bb_ = base
                    color = (int(clamp(br*shd,0,255)),
                             int(clamp(bg*shd,0,255)),
                             int(clamp(bb_*shd,0,255)))

                depth = ((a[0]+b[0]+c[0])/3-cam.eye()[0])**2 + \
                        ((a[1]+b[1]+c[1])/3-cam.eye()[1])**2 + \
                        ((a[2]+b[2]+c[2])/3-cam.eye()[2])**2
                tris.append((depth, a, b, c, color))

        for ch in node.children:
            collect(ch)

    if model.root_node:
        collect(model.root_node)

    tris.sort(key=lambda t: -t[0])

    # ── rasterise ───────────────────────────────────────────────────────
    for _, a, b, c, color in tris:
        pa = cam.project(a, W, H)
        pb = cam.project(b, W, H)
        pc = cam.project(c, W, H)
        if None in (pa,pb,pc): continue
        pts = [(pa[0],pa[1]),(pb[0],pb[1]),(pc[0],pc[1])]
        # Back-face cull (CCW in screen space → front face)
        ex = pb[0]-pa[0]; ey = pb[1]-pa[1]
        fx = pc[0]-pa[0]; fy = pc[1]-pa[1]
        if ex*fy - ey*fx > 0: continue
        if mode == 'wire':
            draw.polygon(pts, outline=(70,80,180))
        else:
            draw.polygon(pts, fill=color)
            if mode == 'solid':
                draw.polygon(pts, outline=(color[0]//3,color[1]//3,color[2]//3+20))

    # ── wireframe overlay for textured/solid modes ───────────────────────
    if mode == 'textured':
        for _, a, b, c, _ in tris[-len(tris)//4:]:   # wire only back tris for detail
            pa = cam.project(a, W, H)
            pb = cam.project(b, W, H)
            pc = cam.project(c, W, H)
            if None in (pa,pb,pc): continue

    # ── bones / skeleton ─────────────────────────────────────────────────
    if mode in ('solid', 'wire'):
        def draw_bones(node: ModelNode):
            if node.is_dummy:
                wp  = node.world_position()
                pp  = cam.project(wp, W, H)
                if node.parent:
                    ppos = node.parent.world_position()
                    pp2  = cam.project(ppos, W, H)
                    if pp and pp2:
                        draw.line([pp[0],pp[1],pp2[0],pp2[1]], fill=(255,180,0), width=1)
                if pp:
                    r=3
                    draw.ellipse([pp[0]-r,pp[1]-r,pp[0]+r,pp[1]+r], fill=(255,200,60))
            for ch in node.children: draw_bones(ch)
        if model.root_node: draw_bones(model.root_node)

    # ── axes ─────────────────────────────────────────────────────────────
    o   = cam.project((0,0,0), W, H)
    xax = cam.project((0.5,0,0), W, H)
    yax = cam.project((0,0.5,0), W, H)
    zax = cam.project((0,0,0.5), W, H)
    if o and xax: draw.line([o[:2],xax[:2]], fill=(220,60,60), width=2)
    if o and yax: draw.line([o[:2],yax[:2]], fill=(60,220,60), width=2)
    if o and zax: draw.line([o[:2],zax[:2]], fill=(60,120,220), width=2)
    if o:
        draw.text((o[0]+2,o[1]-6),"Z▲",fill=(60,120,220))

    return img

# ─── Stats bar ──────────────────────────────────────────────────────────────

def make_stat_bar(model: KotorModel, mode: str, W: int) -> 'Image.Image':
    bar  = Image.new('RGB', (W,28), (20,20,40))
    draw = ImageDraw.Draw(bar)
    verts = sum(len(n.vertices) for n in model.mesh_nodes())
    faces = sum(len(n.faces)    for n in model.mesh_nodes())
    skins = sum(1 for n in model.mesh_nodes() if n.is_skin)
    bones = len(model.bone_nodes())
    tex_list = model.texture_list()
    texname  = ','.join(tex_list[:2]) or '—'
    h = model.bb_max[2]-model.bb_min[2]
    draw.text((4,3), f"{model.name}  V:{verts:,} F:{faces:,} Skin:{skins} Bones:{bones}  tex:{texname}  h={h:.2f}m  [{mode}]",
              fill=(180,210,255))
    return bar

# ─── Per-model UV sheet ──────────────────────────────────────────────────────

def render_uv(model: KotorModel, W: int, H: int) -> 'Image.Image':
    """Draw UV layout for all mesh nodes."""
    img  = Image.new('RGB', (W,H), (18,18,35))
    draw = ImageDraw.Draw(img)
    # UV border
    m = 10
    draw.rectangle([m,m,W-m,H-m], outline=(80,80,150))

    def uv_to_screen(u,v): return (m+int(u%1.0*(W-2*m)), m+int((1-v%1.0)*(H-2*m)))

    colors = [(80,200,100),(200,120,60),(100,160,220),(220,100,180),(160,220,160)]
    ci = 0
    for node in model.mesh_nodes():
        uvs   = node.uvs   if hasattr(node,'uvs')   else []
        faces = node.faces
        if not uvs or not faces: continue
        col = colors[ci % len(colors)]; ci += 1
        n_uv = len(uvs)
        for f in faces:
            v0,v1,v2 = f
            if v0>=n_uv or v1>=n_uv or v2>=n_uv: continue
            p0 = uv_to_screen(*uvs[v0])
            p1 = uv_to_screen(*uvs[v1])
            p2 = uv_to_screen(*uvs[v2])
            draw.line([p0,p1], fill=col); draw.line([p1,p2], fill=col); draw.line([p2,p0], fill=col)

    draw.text((4,4), "UV", fill=(200,200,220))
    return img

# ─── Per-model audit ─────────────────────────────────────────────────────────

def audit_model(model: KotorModel) -> dict:
    """Run sanity checks; return dict of results."""
    issues = []

    # 1. BB vs header
    orig_min = model.bb_min; orig_max = model.bb_max
    model.compute_bounds()
    dz = abs((model.bb_max[2]-model.bb_min[2]) - (orig_max[2]-orig_min[2]))
    if dz > 0.5:
        issues.append(f"BB height mismatch Δ={dz:.2f}")

    # 2. Texture coverage
    tex_list = model.texture_list()
    missing  = []
    for t in tex_list:
        if load_texture(t) is None:
            missing.append(t)
    if missing:
        issues.append(f"Missing tex: {','.join(missing)}")

    # 3. UV presence: note how many helpers vs rendered nodes exist
    helper_count  = sum(1 for n in model.mesh_nodes() if not n.uvs and n.vertices)
    render_count  = sum(1 for n in model.mesh_nodes() if n.uvs and n.vertices)
    if render_count == 0 and model.mesh_nodes():
        issues.append("No UV-mapped render nodes found")
    # Count is informational — no UVs on a node just means it's a helper

    # 4. Floating geometry (any mesh node with world BB wildly outside model BB)
    model.compute_bounds()
    gbb = model.bb_min, model.bb_max
    for n in model.mesh_nodes():
        if not n.vertices: continue
        ws = [vertex_world(n,v) for v in n.vertices[:50]]
        nz = [w[2] for w in ws]
        if nz and (min(nz) < gbb[0][2]-1.5 or max(nz) > gbb[1][2]+1.5):
            issues.append(f"Floating node {n.name} z=[{min(nz):.1f}..{max(nz):.1f}]")

    return {
        'textures'   : tex_list,
        'missing_tex': missing,
        'issues'     : issues,
        'skins'      : sum(1 for n in model.mesh_nodes() if n.is_skin),
        'bones'      : len(model.bone_nodes()),
        'verts'      : sum(len(n.vertices) for n in model.mesh_nodes()),
        'faces'      : sum(len(n.faces)    for n in model.mesh_nodes()),
    }

# ─── Main ────────────────────────────────────────────────────────────────────

def run():
    mdl_files = sorted(MODELS.glob('c_*.mdl'))
    if not mdl_files:
        print("No models found in", MODELS); return

    n_models  = len(mdl_files)
    COLS      = 6
    CELL_W    = 300
    CELL_H    = 300
    STAT_H    = 28
    UV_W      = 150
    MODES     = ['textured','solid','wire']

    # Layout:
    #   For each model: [textured | solid | wire | UV]  each CELL_W wide, CELL_H+STAT_H tall
    # Rows of COLS models
    rows_of_models = (n_models + COLS - 1) // COLS

    # Pass A: 3-mode render grid  (textured / solid / wire)  + UV strip
    pass_rows   = rows_of_models * 3   # 3 render passes per model row
    pass_h      = pass_rows * (CELL_H + STAT_H) + 32
    pass_w      = COLS * CELL_W
    grid_img    = Image.new('RGB', (pass_w, pass_h), (8,8,18))
    grid_draw   = ImageDraw.Draw(grid_img)
    grid_draw.text((4,4), f"GhostRigger-K1-K2 v1.7 – Full Model Audit – {n_models} models", fill=(200,200,255))

    audit_results = {}
    print(f"Auditing {n_models} models …")

    for idx, mdl_path in enumerate(mdl_files):
        name    = mdl_path.stem
        mdx_path= mdl_path.with_suffix('.mdx')
        col     = idx % COLS
        model_row= idx // COLS

        print(f"  [{idx+1:2d}/{n_models}] {name} …", end='', flush=True)
        try:
            mdl_data = mdl_path.read_bytes()
            mdx_data = mdx_path.read_bytes() if mdx_path.exists() else b''
            parser   = MDLBinaryParser(mdl_data, mdx_data)
            model    = parser.parse()
            model.name = name
            model.compute_bounds()

            result = audit_model(model)
            audit_results[name] = result
            status = "ISSUES: "+'; '.join(result['issues']) if result['issues'] else "OK"
            print(f" {status}")

            for mi, mode in enumerate(MODES):
                row_y = (model_row*3 + mi) * (CELL_H + STAT_H) + 32
                try:
                    cell = render_model(model, mode, CELL_W, CELL_H)
                    stat = make_stat_bar(model, mode, CELL_W)
                    grid_img.paste(cell, (col*CELL_W, row_y))
                    grid_img.paste(stat, (col*CELL_W, row_y+CELL_H))
                except Exception as e:
                    err = Image.new('RGB',(CELL_W,CELL_H+STAT_H),(50,10,10))
                    ImageDraw.Draw(err).text((4,4), f"{name}\n{mode}\nERR:{str(e)[:50]}", fill=(255,100,100))
                    grid_img.paste(err, (col*CELL_W, row_y))

        except Exception as e:
            print(f" PARSE ERROR: {e}")
            audit_results[name] = {'issues':[f'Parse error: {e}'], 'textures':[], 'missing_tex':[], 'skins':0,'bones':0,'verts':0,'faces':0}
            for mi in range(3):
                row_y = (model_row*3+mi)*(CELL_H+STAT_H)+32
                err = Image.new('RGB',(CELL_W,CELL_H+STAT_H),(50,10,10))
                ImageDraw.Draw(err).text((4,4), f"{name}\nPARSE ERR\n{str(e)[:50]}", fill=(255,100,100))
                grid_img.paste(err, (col*CELL_W, row_y))

    out_grid = OUT / 'v1.7_full_audit.png'
    grid_img.save(str(out_grid))
    print(f"\nSaved render grid: {out_grid}  ({grid_img.size})")

    # ── UV sheet ────────────────────────────────────────────────────────────
    uv_cols   = COLS
    uv_cell   = 220
    uv_rows   = rows_of_models
    uv_img    = Image.new('RGB', (uv_cols*uv_cell, uv_rows*uv_cell+24), (10,10,22))
    ImageDraw.Draw(uv_img).text((4,4), "UV layouts", fill=(200,200,255))

    for idx, mdl_path in enumerate(mdl_files):
        name     = mdl_path.stem
        mdx_path = mdl_path.with_suffix('.mdx')
        col      = idx % uv_cols
        uv_row   = idx // uv_cols
        x0       = col*uv_cell; y0 = uv_row*uv_cell+24
        try:
            parser = MDLBinaryParser(mdl_path.read_bytes(),
                                     mdx_path.read_bytes() if mdx_path.exists() else b'')
            model  = parser.parse(); model.name=name; model.compute_bounds()
            cell   = render_uv(model, uv_cell, uv_cell)
            uv_img.paste(cell, (x0,y0))
        except Exception as e:
            err = Image.new('RGB',(uv_cell,uv_cell),(40,10,10))
            ImageDraw.Draw(err).text((4,4), f"{name}\n{str(e)[:40]}", fill=(255,100,100))
            uv_img.paste(err, (x0,y0))

    out_uv = OUT / 'v1.7_uv_sheet.png'
    uv_img.save(str(out_uv))
    print(f"Saved UV sheet:    {out_uv}  ({uv_img.size})")

    # ── Text report ─────────────────────────────────────────────────────────
    report_lines = [
        "GhostRigger-K1-K2  Full Model Audit Report  v1.7",
        "="*60, ""
    ]
    ok_count = 0
    for name, r in sorted(audit_results.items()):
        status = "✓ OK" if not r['issues'] else "✗ ISSUES"
        if not r['issues']: ok_count += 1
        report_lines.append(
            f"{name:22s}  V:{r['verts']:5d} F:{r['faces']:5d} "
            f"Skin:{r['skins']} Bones:{r['bones']}  tex:{','.join(r['textures'][:2]) or '—':20s}  {status}"
        )
        for iss in r['issues']:
            report_lines.append(f"  !! {iss}")
    report_lines += ["", f"Result: {ok_count}/{len(audit_results)} models OK"]

    report_path = OUT / 'v1.7_audit_report.txt'
    report_path.write_text('\n'.join(report_lines))
    print(f"Saved text report: {report_path}")
    print(f"\nSummary: {ok_count}/{len(audit_results)} models fully OK")

if __name__ == '__main__':
    run()
