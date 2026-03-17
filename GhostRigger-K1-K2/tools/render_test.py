"""
Final render test: verifies all fixes work correctly with K1 models.
Generates a multi-model preview with 3 panels per model:
  1. Solid shading
  2. Wireframe
  3. World position skeleton overlay
"""
import sys, math, logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.mdl_parser import MDLBinaryParser
from src.core.model_data import KotorModel, ModelNode, NodeFlags, GameVersion

log = logging.getLogger('render_test')
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

try:
    from PIL import Image, ImageDraw
    _PIL = True
except ImportError:
    _PIL = False; print("Pillow missing"); sys.exit(1)

ROOT = Path(__file__).parent.parent
MODELS = ROOT / 'test_assets' / 'k1_extracted' / 'models'
TEXTURES = ROOT / 'test_assets' / 'k1_extracted' / 'textures'
OUT = ROOT / 'test_assets' / 'diagnostics'
OUT.mkdir(exist_ok=True)

# ─── Renderer ─────────────────────────────────────────────────────────────────

def norm3(v):
    l = math.sqrt(v[0]**2+v[1]**2+v[2]**2)
    return (v[0]/l,v[1]/l,v[2]/l) if l>1e-9 else (0,1,0)
def dot3(a,b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def cross3(a,b): return(a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def sub3(a,b): return(a[0]-b[0], a[1]-b[1], a[2]-b[2])
def clamp(v,lo,hi): return max(lo,min(hi,v))

def build_camera(az_deg, el_deg, dist, target):
    az = math.radians(az_deg); el = math.radians(el_deg)
    ce = math.cos(el)
    eye = (target[0]+dist*ce*math.cos(az),
           target[1]+dist*ce*math.sin(az),
           target[2]+dist*math.sin(el))
    fwd = norm3(sub3(target, eye))
    world_up = (0,0,1)
    right = norm3(cross3(fwd, world_up))
    if dot3(right,right)<1e-6: world_up=(0,1,0); right=norm3(cross3(fwd,world_up))
    up = norm3(cross3(right, fwd))
    return eye, fwd, right, up

def project(pt, eye, fwd, right, up, W, H, fov=45):
    ev = sub3(pt, eye)
    depth = dot3(ev, fwd)
    if depth < 0.01: return None
    sx = dot3(ev, right)/depth
    sy = dot3(ev, up)/depth
    f  = 1.0/math.tan(math.radians(fov)*0.5)
    px = int(W/2 + sx*f*H/2)
    py = int(H/2 - sy*f*H/2)
    return px, py, depth

def render_model(model, az=-45, el=20, W=260, H=260, wireframe=False,
                 tex_dir=None, mode='solid'):
    img  = Image.new('RGB',(W,H),(18,18,40))
    draw = ImageDraw.Draw(img)

    # Collect world-space vertices - KotOR vertices ARE in model-global space
    # No world_position offset needed for vertex rendering
    all_wv = []
    def collect(n):
        all_wv.extend(n.vertices)
        for c in n.children: collect(c)
    if model.root_node: collect(model.root_node)

    if not all_wv:
        draw.text((10,H//2-6), "No geometry", fill=(255,80,80))
        return img

    xs=[v[0] for v in all_wv]; ys=[v[1] for v in all_wv]; zs=[v[2] for v in all_wv]
    cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
    dx=max(xs)-min(xs); dy=max(ys)-min(ys); dz=max(zs)-min(zs)
    size=max(math.sqrt(dx*dx+dy*dy+dz*dz),0.01)
    dist=size*1.15
    target=(cx,cy,cz)
    eye, fwd, right, up = build_camera(az, el, dist, target)

    # Load textures if needed
    textures = {}
    if mode=='textured' and tex_dir:
        for tga in Path(tex_dir).glob('*.tga'):
            try:
                textures[tga.stem.lower()] = Image.open(tga).convert('RGB').resize((64,64))
            except: pass

    light = norm3((0.5, 0.3, 1.0))

    # Collect triangles
    tris = []
    def collect_tris(node):
        if not node.vertices or not node.faces:
            for c in node.children: collect_tris(c); return
        # KotOR vertices are in model-global space; no world_position offset needed
        wverts = node.vertices

        # Diffuse color from node
        dr,dg,db = node.diffuse
        base_r = int(clamp(dr,0,1)*220) if dr>0 else 160
        base_g = int(clamp(dg,0,1)*220) if dg>0 else 160
        base_b = int(clamp(db,0,1)*220) if db>0 else 160
        if base_r<40 and base_g<40 and base_b<40: base_r=base_g=base_b=160

        tex_name = node.texture_clean.lower()
        tex_img  = textures.get(tex_name)

        for f in node.faces:
            v0,v1,v2 = f
            if v0>=len(wverts) or v1>=len(wverts) or v2>=len(wverts): continue
            a,b,c = wverts[v0], wverts[v1], wverts[v2]
            ab=sub3(b,a); ac=sub3(c,a)
            fn=cross3(ab,ac); fl=fn[0]**2+fn[1]**2+fn[2]**2
            if fl<1e-12: continue
            fn=(fn[0]/math.sqrt(fl),fn[1]/math.sqrt(fl),fn[2]/math.sqrt(fl))
            lit = max(0.15, dot3(fn, light))
            depth=((a[0]+b[0]+c[0])/3-eye[0])**2+((a[1]+b[1]+c[1])/3-eye[1])**2+((a[2]+b[2]+c[2])/3-eye[2])**2

            if mode=='textured' and tex_img and node.uvs:
                # Use UV centroid for texture sample
                try:
                    uv0=node.uvs[v0]; uv1=node.uvs[v1]; uv2=node.uvs[v2]
                    uc=(uv0[0]+uv1[0]+uv2[0])/3
                    vc=(uv0[1]+uv1[1]+uv2[1])/3
                    px2=int(uc%1.0*63); py2=int((1-vc%1.0)*63)
                    px2=clamp(px2,0,63); py2=clamp(py2,0,63)
                    tc=tex_img.getpixel((px2,py2))
                    cr=int(tc[0]*lit); cg=int(tc[1]*lit); cb=int(tc[2]*lit)
                except: cr=int(base_r*lit); cg=int(base_g*lit); cb=int(base_b*lit)
            else:
                cr=int(base_r*lit); cg=int(base_g*lit); cb=int(base_b*lit)

            tris.append((depth, a, b, c, (clamp(cr,0,255),clamp(cg,0,255),clamp(cb,0,255))))
        for ch in node.children: collect_tris(ch)

    if model.root_node: collect_tris(model.root_node)
    tris.sort(key=lambda t: -t[0])

    for _, a, b, c, color in tris:
        pa = project(a, eye, fwd, right, up, W, H)
        pb = project(b, eye, fwd, right, up, W, H)
        pc = project(c, eye, fwd, right, up, W, H)
        if None in (pa,pb,pc): continue
        pts = [(pa[0],pa[1]),(pb[0],pb[1]),(pc[0],pc[1])]
        # Backface cull
        ex2=pb[0]-pa[0]; ey2=pb[1]-pa[1]
        fx2=pc[0]-pa[0]; fy2=pc[1]-pa[1]
        if ex2*fy2-ey2*fx2 > 0: continue
        if wireframe:
            draw.polygon(pts, outline=(100,100,200))
        else:
            draw.polygon(pts, fill=color)
            if mode == 'wireframe_overlay':
                draw.polygon(pts, outline=(80,80,160))

    # Draw skeleton overlay
    if mode in ('solid','textured','wireframe_overlay'):
        def draw_bone(node):
            wp = node.world_position()
            pp = project(wp, eye, fwd, right, up, W, H)
            if node.parent and node.is_dummy:
                par_wp = node.parent.world_position()
                pp2 = project(par_wp, eye, fwd, right, up, W, H)
                if pp and pp2:
                    draw.line([pp[0],pp[1],pp2[0],pp2[1]], fill=(255,170,0), width=1)
            if pp and node.is_dummy:
                r=3
                draw.ellipse([pp[0]-r,pp[1]-r,pp[0]+r,pp[1]+r], fill=(255,170,0))
            for c in node.children: draw_bone(c)
        if model.root_node: draw_bone(model.root_node)

    # Model name label
    label = f"{model.name} ({mode})"
    vc = sum(len(n.vertices) for n in model.mesh_nodes())
    fc = sum(len(n.faces) for n in model.mesh_nodes())
    draw.text((4,2), label, fill=(200,200,255))
    draw.text((4,13), f"V:{vc:,} F:{fc:,}", fill=(140,200,140))
    return img


def run():
    mdl_files = sorted(MODELS.glob('*.mdl'))
    if not mdl_files:
        print("No models found!"); return

    # 3 modes × N models → grid
    cols = len(mdl_files)
    cell_w, cell_h = 260, 260

    # Single row: solid, textured, wireframe side-by-side per model
    # Layout: 3 rows × N cols
    strip_h = cell_h * 3 + 8
    strip_w = cell_w * cols + 4

    overview = Image.new('RGB', (strip_w, strip_h), (12,12,20))
    d = ImageDraw.Draw(overview)
    d.text((4,1), "Row 1: Solid  |  Row 2: Textured  |  Row 3: Wireframe+Bones", fill=(180,180,220))

    modes = [('solid', False), ('textured', False), ('wireframe_overlay', True)]

    for col, mdl_path in enumerate(mdl_files):
        name = mdl_path.stem
        mdx_path = mdl_path.with_suffix('.mdx')
        try:
            mdl = mdl_path.read_bytes()
            mdx = mdx_path.read_bytes() if mdx_path.exists() else b''
            parser = MDLBinaryParser(mdl, mdx)
            model  = parser.parse()
        except Exception as e:
            print(f"PARSE ERROR {name}: {e}")
            continue

        for row, (mode, wf) in enumerate(modes):
            try:
                img = render_model(model, az=-30, el=25, W=cell_w, H=cell_h,
                                   wireframe=wf, tex_dir=str(TEXTURES), mode=mode)
                overview.paste(img, (col*cell_w, row*cell_h + 8))
            except Exception as e:
                err = Image.new('RGB',(cell_w,cell_h),(60,20,20))
                ImageDraw.Draw(err).text((4,4), f"{name}\n{mode}\nERROR:\n{str(e)[:40]}", fill=(255,80,80))
                overview.paste(err, (col*cell_w, row*cell_h + 8))

    out_path = OUT / 'k1_render_test.png'
    overview.save(str(out_path))
    print(f"Saved: {out_path}")
    print(f"Size: {overview.size}")


if __name__ == '__main__':
    run()
    # Also run the full FrameRenderer textured preview if viewport module available
    try:
        from src.gui.viewport import FrameRenderer, ArcBallCamera, TextureCache
        _has_renderer = True
    except Exception as e:
        print(f"FrameRenderer not available: {e}")
        _has_renderer = False

    if _has_renderer and (TEXTURES.exists() or MODELS.exists()):
        print("Generating full FrameRenderer textured preview…")
        cell = 320
        mdl_files = sorted(MODELS.glob('c_*.mdl'))[:12]  # first 12 creatures

        cols = min(6, len(mdl_files))
        rows_per = 2  # textured + wireframe
        rows = (len(mdl_files) + cols - 1) // cols * rows_per
        W_total = cols * cell
        H_total = rows * cell + 24
        grid = Image.new('RGB', (W_total, H_total), (10, 10, 22))
        gd = ImageDraw.Draw(grid)
        gd.text((4, 4), "GhostRigger K1-K2 v1.4 – FrameRenderer Textured Preview", fill=(200,200,255))

        for idx, mdl_path in enumerate(mdl_files):
            col = idx % cols
            row = (idx // cols) * rows_per
            y0  = row * cell + 24
            x0  = col * cell
            name = mdl_path.stem
            mdx_path = mdl_path.with_suffix('.mdx')
            try:
                parser = MDLBinaryParser(mdl_path.read_bytes(),
                                         mdx_path.read_bytes() if mdx_path.exists() else b'')
                model = parser.parse()
                # Build renderer with texture cache
                cam = ArcBallCamera()
                renderer = FrameRenderer(cam)
                renderer.set_model(model)
                tc = TextureCache()
                if TEXTURES.exists():
                    tc.set_search_dirs([str(TEXTURES)])
                    renderer.tex_cache = tc
                # Frame the model
                model.compute_bounds()
                bb = model.bb_min, model.bb_max
                cx = (bb[0][0]+bb[1][0])/2
                cy = (bb[0][1]+bb[1][1])/2
                cz = (bb[0][2]+bb[1][2])/2
                radius = max(1.0, model.radius)
                cam.target = [cx, cy, cz]
                cam.distance = radius * 2.2
                cam.elevation = 20.0
                cam.azimuth = -35.0

                # Render textured
                renderer.textured = True
                renderer.show_wireframe = False
                renderer.show_bones = False
                img_t = renderer.render(cell, cell)
                if img_t:
                    grid.paste(img_t.convert('RGB'), (x0, y0))

                # Render wireframe+bones
                renderer.textured = False
                renderer.show_wireframe = True
                renderer.show_bones = True
                img_w = renderer.render(cell, cell)
                if img_w and rows_per > 1:
                    grid.paste(img_w.convert('RGB'), (x0, y0 + cell))

            except Exception as e:
                err_img = Image.new('RGB', (cell, cell*rows_per), (50, 10, 10))
                ImageDraw.Draw(err_img).text((4,4), f"{name}\nERROR:\n{str(e)[:60]}", fill=(255,100,100))
                grid.paste(err_img, (x0, y0))

        out2 = OUT / 'k1_textured_preview.png'
        grid.save(str(out2))
        print(f"Saved FrameRenderer preview: {out2}")
        print(f"Size: {grid.size}")
