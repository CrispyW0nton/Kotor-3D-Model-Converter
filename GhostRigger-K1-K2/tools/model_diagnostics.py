"""
K1 Model Diagnostics & Rendering Test
======================================
Parses every extracted .mdl/.mdx, renders each model from multiple angles,
identifies render/rig issues, extracts textures properly, and saves a
diagnostic report + preview images.

Run:
    cd /path/to/GhostRigger-K1-K2
    python3 GhostRigger-K1-K2/tools/model_diagnostics.py
"""

import sys, os, struct, math, logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.mdl_parser import MDLBinaryParser
from src.core.model_data import KotorModel, ModelNode, NodeFlags, GameVersion

log = logging.getLogger('diagnostics')
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL = True
except ImportError:
    _PIL = False

# ─── Paths ────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).parent.parent
K1_DIR    = ROOT / 'test_assets' / 'k1_extracted'
MODELS    = K1_DIR / 'models'
TEXTURES  = K1_DIR / 'textures'
OUT_DIR   = ROOT / 'test_assets' / 'diagnostics'
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ─── Math helpers ─────────────────────────────────────────────────────────────

def norm3(v):
    l = math.sqrt(v[0]**2+v[1]**2+v[2]**2)
    return (v[0]/l, v[1]/l, v[2]/l) if l > 1e-9 else (0,1,0)

def dot3(a,b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]

def cross3(a,b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def sub3(a,b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])

def quat_to_mat3(rx,ry,rz,rw):
    """Convert quaternion to 3×3 rotation matrix."""
    x,y,z,w = rx,ry,rz,rw
    l = math.sqrt(x*x+y*y+z*z+w*w)
    if l > 1e-9: x/=l; y/=l; z/=l; w/=l
    m = [
        1-2*(y*y+z*z),  2*(x*y-z*w),   2*(x*z+y*w),
        2*(x*y+z*w),    1-2*(x*x+z*z), 2*(y*z-x*w),
        2*(x*z-y*w),    2*(y*z+x*w),   1-2*(x*x+y*y),
    ]
    return m

def mat3_mul_vec3(m, v):
    """Multiply 3×3 matrix by 3-vector."""
    return (
        m[0]*v[0]+m[1]*v[1]+m[2]*v[2],
        m[3]*v[0]+m[4]*v[1]+m[5]*v[2],
        m[6]*v[0]+m[7]*v[1]+m[8]*v[2],
    )

def world_transform_node(node):
    """Walk up the node tree to compute the cumulative world position."""
    pos = list(node.position)
    n = node.parent
    while n:
        m = quat_to_mat3(*n.rotation)
        lp = mat3_mul_vec3(m, pos)
        pos = [lp[0]+n.position[0], lp[1]+n.position[1], lp[2]+n.position[2]]
        n = n.parent
    return tuple(pos)

# ─── Software Rasterizer ─────────────────────────────────────────────────────

class SWRaster:
    """Simple software rasterizer: Z-up, flat-shaded or textured triangles."""

    def __init__(self, W=512, H=512):
        self.W = W; self.H = H
        self.img  = Image.new('RGB', (W,H), (30,30,35))
        self.draw = ImageDraw.Draw(self.img)
        self.zbuf = [1e18]*W*H

    def clear(self, bg=(30,30,35)):
        self.img  = Image.new('RGB', (self.W,self.H), bg)
        self.draw = ImageDraw.Draw(self.img)
        self.zbuf = [1e18]*self.W*self.H

    def project(self, vx,vy,vz, eye, fwd, right, up, dist, fov_rad):
        """Project world→screen. Returns (sx,sy,depth) or None if behind."""
        ev = sub3((vx,vy,vz), eye)
        depth = dot3(ev, fwd)
        if depth < 0.01: return None
        sx_ndc = dot3(ev, right) / depth
        sy_ndc = dot3(ev, up)    / depth
        scale  = self.H / (2*math.tan(fov_rad*0.5))
        sx = int(self.W/2 + sx_ndc * scale)
        sy = int(self.H/2 - sy_ndc * scale)
        return sx, sy, depth

    def draw_triangle(self, pts, color):
        """Draw a filled triangle. pts = [(sx,sy,d),(sx,sy,d),(sx,sy,d)]"""
        if None in pts: return
        (ax,ay,az),(bx,by,bz),(cx,cy,cz) = pts
        # Backface cull in screen space
        ex=bx-ax; ey=by-ay; fx=cx-ax; fy=cy-ay
        if ex*fy-ey*fx > 0: return  # back-facing (Z-up screen Y flipped)
        # Shading
        depth = (az+bz+cz)/3.0
        self.draw.polygon([(ax,ay),(bx,by),(cx,cy)], fill=color)

    def draw_wireframe(self, pts, color=(180,180,180)):
        if None in pts: return
        (ax,ay,_),(bx,by,_),(cx,cy,_) = pts
        self.draw.line([(ax,ay),(bx,by),(cx,cy),(ax,ay)], fill=color, width=1)


def build_camera(azimuth_deg, elevation_deg, dist, target=(0,0,1)):
    """Return (eye, fwd, right, up) for a Z-up world."""
    az  = math.radians(azimuth_deg)
    el  = math.radians(elevation_deg)
    ce  = math.cos(el)
    eye = (
        target[0] + dist*ce*math.cos(az),
        target[1] + dist*ce*math.sin(az),
        target[2] + dist*math.sin(el),
    )
    fwd  = norm3(sub3(target, eye))
    world_up = (0,0,1)
    right = norm3(cross3(fwd, world_up))
    if dot3(right,right)<1e-6:
        world_up=(0,1,0); right=norm3(cross3(fwd,world_up))
    up = norm3(cross3(right, fwd))
    return eye, fwd, right, up


def render_model_offscreen(model: KotorModel, az=30, el=20, W=512, H=512,
                            light_dir=(0.5,0.3,1.0), wireframe=False) -> 'Image.Image':
    """Render a KotorModel to a PIL Image."""
    if not _PIL:
        raise RuntimeError("Pillow not available")

    rast = SWRaster(W, H)

    # Compute bounds
    all_verts = []
    def collect(n):
        wp = world_transform_node(n)
        for v in n.vertices:
            all_verts.append((v[0]+wp[0], v[1]+wp[1], v[2]+wp[2]))
        for c in n.children: collect(c)
    if model.root_node: collect(model.root_node)

    if not all_verts:
        rast.draw.text((10,H//2), "No geometry", fill=(255,100,100))
        return rast.img

    xs = [v[0] for v in all_verts]
    ys = [v[1] for v in all_verts]
    zs = [v[2] for v in all_verts]
    cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
    dx=max(xs)-min(xs); dy=max(ys)-min(ys); dz=max(zs)-min(zs)
    size=max(math.sqrt(dx*dx+dy*dy+dz*dz),0.01)
    dist = size * 1.1

    target = (cx, cy, cz)
    eye, fwd, right, up = build_camera(az, el, dist, target)
    fov_rad = math.radians(45)

    light = norm3(light_dir)

    # Collect triangles with depth for painter's sort
    tris = []

    def render_node(node):
        wp = world_transform_node(node)
        verts = [(v[0]+wp[0], v[1]+wp[1], v[2]+wp[2]) for v in node.vertices]
        if not verts or not node.faces: 
            for c in node.children: render_node(c)
            return

        # Flat diffuse color from node
        diff = node.diffuse if node.diffuse != (0,0,0) else (0.6, 0.6, 0.6)
        base_r = int(_clamp(diff[0],0,1)*220)
        base_g = int(_clamp(diff[1],0,1)*220)
        base_b = int(_clamp(diff[2],0,1)*220)
        if base_r < 40 and base_g < 40 and base_b < 40:
            base_r = base_g = base_b = 160  # fallback grey

        for f in node.faces:
            v1,v2,v3 = f
            if v1>=len(verts) or v2>=len(verts) or v3>=len(verts): continue
            a,b,c = verts[v1], verts[v2], verts[v3]
            # Face normal
            ab = sub3(b,a); ac = sub3(c,a)
            fn = cross3(ab,ac)
            l2 = fn[0]**2+fn[1]**2+fn[2]**2
            if l2 < 1e-12: continue
            fn = (fn[0]/math.sqrt(l2), fn[1]/math.sqrt(l2), fn[2]/math.sqrt(l2))
            lit = max(0.1, dot3(fn, light))
            cr = int(base_r*lit); cg = int(base_g*lit); cb = int(base_b*lit)
            depth = ((a[0]+b[0]+c[0])/3 - eye[0])**2 + \
                    ((a[1]+b[1]+c[1])/3 - eye[1])**2 + \
                    ((a[2]+b[2]+c[2])/3 - eye[2])**2
            tris.append((depth, a, b, c, (cr,cg,cb)))

        for ch in node.children: render_node(ch)

    if model.root_node: render_node(model.root_node)

    # Sort far→near
    tris.sort(key=lambda t: -t[0])

    for _, a, b, c, color in tris:
        pa = rast.project(*a, eye, fwd, right, up, dist, fov_rad)
        pb = rast.project(*b, eye, fwd, right, up, dist, fov_rad)
        pc = rast.project(*c, eye, fwd, right, up, dist, fov_rad)
        if wireframe:
            rast.draw_wireframe((pa,pb,pc), color)
        else:
            rast.draw_triangle((pa,pb,pc), color)

    return rast.img


def _clamp(v, lo, hi): return max(lo, min(hi, v))


# ─── Diagnostic checks ────────────────────────────────────────────────────────

def check_model(model: KotorModel, name: str) -> dict:
    """Run a suite of diagnostic checks on a parsed model."""
    issues = []
    warnings = []
    stats = {}

    # Walk nodes
    mesh_nodes = []
    bone_nodes = []
    skin_nodes = []
    all_nodes  = []

    def walk(n, depth=0):
        all_nodes.append(n)
        if n.flags & NodeFlags.MESH:  mesh_nodes.append(n)
        if n.flags & NodeFlags.SKIN:  skin_nodes.append(n)
        if not (n.flags & NodeFlags.MESH):  bone_nodes.append(n)
        for c in n.children: walk(c, depth+1)

    if model.root_node: walk(model.root_node)

    stats['nodes']        = len(all_nodes)
    stats['mesh_nodes']   = len(mesh_nodes)
    stats['skin_nodes']   = len(skin_nodes)
    stats['total_verts']  = sum(len(n.vertices) for n in mesh_nodes)
    stats['total_faces']  = sum(len(n.faces)    for n in mesh_nodes)
    stats['game_version'] = model.game_version.name

    # Check 1: Zero-geometry mesh nodes
    empty_meshes = [n.name for n in mesh_nodes if not n.vertices]
    if empty_meshes:
        warnings.append(f"Mesh nodes with no vertices: {empty_meshes[:5]}")

    # Check 2: Out-of-range face indices
    bad_faces = []
    for n in mesh_nodes:
        for fi, f in enumerate(n.faces):
            if any(idx >= len(n.vertices) for idx in f):
                bad_faces.append(f"{n.name}[{fi}]={f} (vc={len(n.vertices)})")
    if bad_faces:
        issues.append(f"Out-of-range face indices ({len(bad_faces)} total): {bad_faces[:3]}")
        stats['bad_faces'] = len(bad_faces)

    # Check 3: UV / vertex count mismatch
    uv_mismatch = []
    for n in mesh_nodes:
        if n.uvs and len(n.uvs) != len(n.vertices):
            uv_mismatch.append(f"{n.name}: uvs={len(n.uvs)} verts={len(n.vertices)}")
    if uv_mismatch:
        warnings.append(f"UV/vertex count mismatch ({len(uv_mismatch)} nodes): {uv_mismatch[:3]}")

    # Check 4: Degenerate triangles
    degen = 0
    for n in mesh_nodes:
        for f in n.faces:
            if len(set(f)) < 3: degen += 1
    if degen:
        warnings.append(f"Degenerate faces (duplicate verts): {degen}")
        stats['degen_faces'] = degen

    # Check 5: Skin bone_map validity
    for n in skin_nodes:
        empty_bm = sum(1 for b in n.bone_map if not b)
        total_bm  = len(n.bone_map)
        if total_bm == 0:
            issues.append(f"Skin node {n.name}: empty bone_map")
        elif empty_bm/max(total_bm,1) > 0.8:
            warnings.append(f"Skin node {n.name}: {empty_bm}/{total_bm} unused bone slots")

    # Check 6: World position sanity
    for n in mesh_nodes:
        wp = world_transform_node(n)
        dist = math.sqrt(wp[0]**2+wp[1]**2+wp[2]**2)
        if dist > 200:
            issues.append(f"Node {n.name} very far from origin: world_pos={wp}")

    # Check 7: Normals validity
    for n in mesh_nodes:
        if n.normals:
            zero_normals = sum(1 for nx,ny,nz in n.normals
                               if abs(nx)+abs(ny)+abs(nz) < 0.01)
            if zero_normals > len(n.normals)*0.1:
                warnings.append(f"Node {n.name}: {zero_normals}/{len(n.normals)} zero normals")

    # Check 8: Inverted / non-manifold geometry
    for n in mesh_nodes:
        if n.vertices and n.faces:
            # Check if centroid is within rough bounding box
            xs = [v[0] for v in n.vertices]
            ys = [v[1] for v in n.vertices]
            zs = [v[2] for v in n.vertices]
            cx=(min(xs)+max(xs))/2
            cy=(min(ys)+max(ys))/2
            cz=(min(zs)+max(zs))/2
            span = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
            if span > 50:
                warnings.append(f"Node {n.name}: large vertex span {span:.1f} units")

    # Check 9: Texture references
    tex_names = set()
    for n in mesh_nodes:
        if n.texture: tex_names.add(n.texture.lower())
    stats['texture_refs'] = sorted(tex_names)

    missing_tex = []
    for t in tex_names:
        found = any((TEXTURES/f"{t}{ext}").exists()
                    for ext in ['.tga','.tpc','.png'])
        if not found: missing_tex.append(t)
    if missing_tex:
        warnings.append(f"Missing textures: {missing_tex[:10]}")
        stats['missing_textures'] = missing_tex

    return {
        'name':     name,
        'stats':    stats,
        'issues':   issues,
        'warnings': warnings,
    }


# ─── Texture extraction using parser ─────────────────────────────────────────

def extract_model_textures(model: KotorModel, k1data_dir: Path):
    """Use parsed model's texture refs to extract the correct textures."""
    sys.path.insert(0, str(Path(__file__).parent))
    from bif_extractor import K1DataExtractor
    ex = K1DataExtractor(str(k1data_dir))

    tex_names = set()
    def walk(n):
        if n.texture: tex_names.add(n.texture.lower())
        for c in n.children: walk(c)
    if model.root_node: walk(model.root_node)

    extracted = {}
    for t in tex_names:
        if not t or t == 'null': continue
        # Check if already extracted
        already = False
        for ext in ['.tga', '.tpc', '.png']:
            if (TEXTURES / f"{t}{ext}").exists():
                already = True
                break
        if already:
            log.debug(f"  Texture already extracted: {t}")
            continue

        data, ext = ex.extract_texture(t)
        if data:
            p = TEXTURES / f"{t}{ext}"
            p.write_bytes(data)
            extracted[t] = str(p)
            log.info(f"  Texture {t}{ext}: {len(data):,} bytes")
        else:
            log.warning(f"  Texture NOT FOUND: {t}")
    return extracted


# ─── Main diagnostic runner ───────────────────────────────────────────────────

def run_diagnostics():
    if not _PIL:
        log.error("Pillow not installed. Run: pip install Pillow")
        return

    k1data_dir = Path(__file__).parent.parent.parent.parent / 'k1Data'
    if not k1data_dir.exists():
        k1data_dir = Path(os.environ.get('KOTOR_K1_DIR', 'game_data/k1_extracted'))

    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("  GhostRigger-K1-K2  —  K1 Model Diagnostics Report")
    report_lines.append("=" * 70)
    report_lines.append("")

    mdl_files = sorted(MODELS.glob('*.mdl'))
    if not mdl_files:
        log.error(f"No .mdl files found in {MODELS}")
        return

    log.info(f"Found {len(mdl_files)} models to diagnose")

    all_results = []

    for mdl_path in mdl_files:
        name = mdl_path.stem
        mdx_path = MODELS / f"{name}.mdx"
        log.info(f"\n{'─'*60}")
        log.info(f"Diagnosing: {name}")

        try:
            mdl_bytes = mdl_path.read_bytes()
            mdx_bytes = mdx_path.read_bytes() if mdx_path.exists() else b''

            parser = MDLBinaryParser(mdl_bytes, mdx_bytes)
            model  = parser.parse()

            # Extract textures using real names from parser
            if k1data_dir.exists():
                extract_model_textures(model, k1data_dir)

            result = check_model(model, name)
            all_results.append(result)

            # Print stats
            s = result['stats']
            log.info(f"  Nodes={s['nodes']}  Mesh={s['mesh_nodes']}  Skin={s['skin_nodes']}")
            log.info(f"  Verts={s['total_verts']}  Faces={s['total_faces']}")
            for issue in result['issues']:
                log.error(f"  ❌ {issue}")
            for warn in result['warnings']:
                log.warning(f"  ⚠️  {warn}")

            # Generate render preview (4 angles)
            angles = [(-45,15), (45,15), (135,15), (0,70)]
            panels = []
            for az, el in angles:
                try:
                    img = render_model_offscreen(model, az=az, el=el, W=300, H=300)
                    panels.append(img)
                except Exception as e:
                    log.error(f"  Render error at az={az}: {e}")
                    err_img = Image.new('RGB',(300,300),(80,20,20))
                    ImageDraw.Draw(err_img).text((10,140), f"Render error:\n{e}", fill=(255,100,100))
                    panels.append(err_img)

            # Stitch into 4-panel strip
            strip = Image.new('RGB', (300*4 + 3*4, 300 + 40), (20,20,25))
            d = ImageDraw.Draw(strip)
            for i, (panel, (az,el)) in enumerate(zip(panels, angles)):
                strip.paste(panel, (i*304, 40))
                d.text((i*304+8, 2), f"{name}  az={az}° el={el}°", fill=(200,200,200))
                # Overlay stats
                issue_color = (255,80,80) if result['issues'] else (80,255,80)
                status = f"V:{s['total_verts']} F:{s['total_faces']}"
                if result['issues']:
                    status += f"  ❌{len(result['issues'])} issues"
                d.text((i*304+8, 16), status, fill=issue_color)

            out_path = OUT_DIR / f"{name}_diagnostic.png"
            strip.save(str(out_path))
            log.info(f"  Saved: {out_path.name}")

        except Exception as e:
            import traceback
            log.error(f"  FAILED to parse {name}: {e}")
            log.error(traceback.format_exc())
            all_results.append({
                'name': name, 'stats': {}, 
                'issues': [f"Parse failed: {e}"], 'warnings': []
            })

    # ── Summary report ────────────────────────────────────────────────────────
    report_lines.append(f"Models tested: {len(all_results)}")
    report_lines.append("")

    total_issues = 0
    for r in all_results:
        s = r.get('stats', {})
        issues = r['issues']
        warns  = r['warnings']
        total_issues += len(issues)

        status = "OK" if not issues else f"ISSUES ({len(issues)})"
        line = f"  {r['name']:<20} {status:<20}"
        if s:
            line += f"  V={s.get('total_verts',0):>6}  F={s.get('total_faces',0):>6}"
        report_lines.append(line)
        for iss in issues:
            report_lines.append(f"      ❌ {iss}")
        for w in warns:
            report_lines.append(f"      ⚠  {w}")

    report_lines.append("")
    report_lines.append(f"Total issues found: {total_issues}")

    # Save text report
    report_path = OUT_DIR / 'diagnostic_report.txt'
    report_path.write_text('\n'.join(report_lines))
    log.info(f"\nReport saved: {report_path}")
    print('\n'.join(report_lines))

    # ── Combined overview image ────────────────────────────────────────────────
    if _PIL and all_results:
        n = len(mdl_files)
        cols = min(4, n)
        rows = math.ceil(n / cols)
        OW, OH = 300, 300
        overview = Image.new('RGB', (cols*OW, rows*OH), (15,15,20))
        for idx, mdl_path in enumerate(mdl_files):
            name = mdl_path.stem
            mdx_path = MODELS / f"{name}.mdx"
            try:
                mdl_bytes = mdl_path.read_bytes()
                mdx_bytes = mdx_path.read_bytes() if mdx_path.exists() else b''
                parser = MDLBinaryParser(mdl_bytes, mdx_bytes)
                model  = parser.parse()
                thumb  = render_model_offscreen(model, az=-45, el=20, W=OW, H=OH-25)
                panel  = Image.new('RGB',(OW,OH),(15,15,20))
                panel.paste(thumb, (0,25))
                d2 = ImageDraw.Draw(panel)
                r = next((x for x in all_results if x['name']==name), {})
                issue_c = (255,80,80) if r.get('issues') else (80,255,80)
                d2.text((4,2), name, fill=(220,220,220))
                sv = r.get('stats',{})
                d2.text((4,14), f"V:{sv.get('total_verts',0)} F:{sv.get('total_faces',0)}", fill=issue_c)
            except Exception as e:
                panel = Image.new('RGB',(OW,OH),(60,20,20))
                ImageDraw.Draw(panel).text((8,8), f"{name}\nFAILED\n{str(e)[:40]}", fill=(255,100,100))

            col = idx % cols
            row = idx // cols
            overview.paste(panel, (col*OW, row*OH))

        ov_path = OUT_DIR / 'overview.png'
        overview.save(str(ov_path))
        log.info(f"Overview saved: {ov_path}")


if __name__ == '__main__':
    run_diagnostics()
