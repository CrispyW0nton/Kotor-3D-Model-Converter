#!/usr/bin/env python3
"""
Comprehensive model render test - validates all models render correctly
with proper textures, transforms, and visual output.
"""
import sys, os, math, struct, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logging.basicConfig(level=logging.WARNING)

from src.core.mdl_parser import MDLBinaryParser
from src.core.model_data import KotorModel, ModelNode, NodeFlags, _quat_rotate

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL = True
except ImportError:
    print("ERROR: Pillow required"); sys.exit(1)

MODEL_DIR   = "test_assets/k1_extracted/models"
TEX_DIR     = "test_assets/k1_extracted/textures"
OUTPUT_DIR  = "test_assets/diagnostics"

MODELS = [
    "c_bantha","c_brith","c_dewback","c_drdastro","c_drdmkfour",
    "c_drdmkone","c_drdmktwo","c_drdprot","c_drdspyder","c_gammorean",
    "c_ithorian","c_jawa","c_kath","c_khounda","c_kinrath",
    "c_rakghoul","c_rancor","c_selkath"
]

# ─── Import rendering components ────────────────────────────────────────────

# We inline a minimal renderer that matches what the GUI uses

def _normalize(v):
    l = math.sqrt(v[0]**2+v[1]**2+v[2]**2)
    return (v[0]/l,v[1]/l,v[2]/l) if l>1e-9 else (0,0,1)

def _cross(a,b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def _dot(a,b):
    return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]

def _sub(a,b):
    return (a[0]-b[0],a[1]-b[1],a[2]-b[2])

def _clamp(v,lo,hi):
    return max(lo,min(hi,v))

def _is_tpc_data(data):
    if len(data) < 128: return False
    data_sz = struct.unpack_from('<I', data, 0)[0]
    w = struct.unpack_from('<H', data, 8)[0]
    h = struct.unpack_from('<H', data, 10)[0]
    enc = data[12]
    if w==0 or h==0 or w>4096 or h>4096: return False
    if enc not in (1,2,4,12,13,14): return False
    bx = max(1,(w+3)//4); by = max(1,(h+3)//4)
    valid = {bx*by*8, bx*by*16, w*h, w*h*3, w*h*4}
    if data_sz in valid: return True
    if data_sz>0 and 128+data_sz<=len(data)+1024 and enc in (12,13,14): return True
    return False

def _decomp_dxt1(data,w,h):
    result=bytearray(w*h*4); bw=max(1,(w+3)//4); bh=max(1,(h+3)//4)
    for by2 in range(bh):
        for bx2 in range(bw):
            pos=(by2*bw+bx2)*8
            if pos+8>len(data): continue
            c0r=struct.unpack_from('<H',data,pos)[0]
            c1r=struct.unpack_from('<H',data,pos+2)[0]
            lk=struct.unpack_from('<I',data,pos+4)[0]
            def e(c): return (((c>>11)&31)*255//31,((c>>5)&63)*255//63,(c&31)*255//31)
            c0,c1=e(c0r),e(c1r)
            if c0r>c1r:
                cols=[c0,c1,tuple((2*c0[i]+c1[i])//3 for i in range(3)),tuple((c0[i]+2*c1[i])//3 for i in range(3))]
            else:
                cols=[c0,c1,tuple((c0[i]+c1[i])//2 for i in range(3)),(0,0,0)]
            for py2 in range(4):
                for px2 in range(4):
                    col=cols[(lk>>(2*(py2*4+px2)))&3]
                    gx,gy=bx2*4+px2,by2*4+py2
                    if gx<w and gy<h:
                        o=(gy*w+gx)*4; result[o]=col[0]; result[o+1]=col[1]; result[o+2]=col[2]; result[o+3]=255
    return result

def _decomp_dxt5(data,w,h):
    result=bytearray(w*h*4); bw=max(1,(w+3)//4); bh=max(1,(h+3)//4)
    for by2 in range(bh):
        for bx2 in range(bw):
            pos=(by2*bw+bx2)*16
            if pos+16>len(data): continue
            a0,a1=data[pos],data[pos+1]
            abits=struct.unpack_from('<Q',data,pos+1)[0]>>8
            c0r=struct.unpack_from('<H',data,pos+8)[0]; c1r=struct.unpack_from('<H',data,pos+10)[0]
            lk=struct.unpack_from('<I',data,pos+12)[0]
            def e(c): return (((c>>11)&31)*255//31,((c>>5)&63)*255//63,(c&31)*255//31)
            c0,c1=e(c0r),e(c1r)
            cols=[c0,c1,tuple((2*c0[i]+c1[i])//3 for i in range(3)),tuple((c0[i]+2*c1[i])//3 for i in range(3))]
            if a0>a1:
                als=[a0,a1,(6*a0+a1)//7,(5*a0+2*a1)//7,(4*a0+3*a1)//7,(3*a0+4*a1)//7,(2*a0+5*a1)//7,(a0+6*a1)//7]
            else:
                als=[a0,a1,(4*a0+a1)//5,(3*a0+2*a1)//5,(2*a0+3*a1)//5,(a0+4*a1)//5,0,255]
            for py2 in range(4):
                for px2 in range(4):
                    col=cols[(lk>>(2*(py2*4+px2)))&3]
                    alpha=als[(abits>>(3*(py2*4+px2)))&7]
                    gx,gy=bx2*4+px2,by2*4+py2
                    if gx<w and gy<h:
                        o=(gy*w+gx)*4; result[o]=col[0]; result[o+1]=col[1]; result[o+2]=col[2]; result[o+3]=alpha
    return result

def _load_tpc(data):
    if len(data)<128: return None
    data_sz=struct.unpack_from('<I',data,0)[0]
    w=struct.unpack_from('<H',data,8)[0]; h=struct.unpack_from('<H',data,10)[0]
    enc=data[12]
    if w==0 or h==0: return None
    px=data[128:]
    bx=max(1,(w+3)//4); by2=max(1,(h+3)//4)
    dxt1=bx*by2*8; dxt5=bx*by2*16
    try:
        if enc==1:
            if len(px)>=w*h: return Image.frombytes('L',(w,h),px[:w*h]).convert('RGBA')
        elif enc==2:
            if data_sz==w*h*3 and len(px)>=w*h*3: return Image.frombytes('RGB',(w,h),px[:w*h*3]).convert('RGBA')
            if len(px)>=dxt1 and data_sz==dxt1: return Image.frombytes('RGBA',(w,h),bytes(_decomp_dxt1(px,w,h)))
        elif enc==4:
            if len(px)>=w*h*4: return Image.frombytes('RGBA',(w,h),px[:w*h*4])
        elif enc==12:
            if len(px)>=dxt1: return Image.frombytes('RGBA',(w,h),bytes(_decomp_dxt1(px,w,h)))
        elif enc in (13,14):
            if len(px)>=dxt5: return Image.frombytes('RGBA',(w,h),bytes(_decomp_dxt5(px,w,h)))
        if data_sz==dxt5 and len(px)>=dxt5: return Image.frombytes('RGBA',(w,h),bytes(_decomp_dxt5(px,w,h)))
        if data_sz==dxt1 and len(px)>=dxt1: return Image.frombytes('RGBA',(w,h),bytes(_decomp_dxt1(px,w,h)))
    except Exception as e:
        print(f"  TPC decode error: {e}")
    return None

def load_texture(name, tex_dir):
    if not name or name.upper() in ('NULL',''):
        return None
    clean = name.lower()
    for ext in ('.tga','.tpc','.png'):
        p = os.path.join(tex_dir, clean+ext)
        if os.path.exists(p):
            try:
                with open(p,'rb') as f: raw=f.read()
                if _is_tpc_data(raw):
                    img = _load_tpc(raw)
                    if img: return img.resize((256,256), Image.LANCZOS).convert('RGBA')
                img = Image.open(p).convert('RGBA')
                if img.size[0]>512 or img.size[1]>512:
                    img = img.resize((512,512), Image.LANCZOS)
                return img
            except Exception as e:
                print(f"  Texture load error {p}: {e}")
    return None

def _apply_vtx(node, v, wp, wo, is_id):
    if node.is_skin and is_id: return v
    if is_id: return (v[0]+wp[0],v[1]+wp[1],v[2]+wp[2])
    rx,ry,rz = _quat_rotate(wo,v)
    return (rx+wp[0],ry+wp[1],rz+wp[2])

def project(x,y,z, eye,right,up,fwd, W,H, fov=45.0):
    dx,dy,dz = x-eye[0],y-eye[1],z-eye[2]
    cx=_dot((dx,dy,dz),right); cy=_dot((dx,dy,dz),up); cz=_dot((dx,dy,dz),fwd)
    if cz<0.01: return None
    f=1.0/math.tan(math.radians(fov)*0.5)
    sx=int(W*0.5+(cx/cz)*f*H*0.5)
    sy=int(H*0.5-(cy/cz)*f*H*0.5)
    return sx,sy,cz

def camera_for_bb(bb_min,bb_max):
    cx=(bb_min[0]+bb_max[0])*0.5; cy=(bb_min[1]+bb_max[1])*0.5; cz=(bb_min[2]+bb_max[2])*0.5
    az=math.radians(-45); el=math.radians(25)
    dx=bb_max[0]-bb_min[0]; dy=bb_max[1]-bb_min[1]; dz=bb_max[2]-bb_min[2]
    diag=math.sqrt(dx*dx+dy*dy+dz*dz)
    dist=max(0.5, diag*1.4)
    ce=math.cos(el)
    ex=cx+dist*ce*math.cos(az); ey=cy+dist*ce*math.sin(az); ez=cz+dist*math.sin(el)
    eye=(ex,ey,ez); target=(cx,cy,cz)
    fwd=_normalize(_sub(target,eye))
    wup=(0,0,1)
    right=_normalize(_cross(fwd,wup))
    if _dot(right,right)<1e-6: right=_normalize(_cross(fwd,(0,1,0)))
    up=_cross(right,fwd)
    return eye,right,up,fwd

def sample_tex(img, u, v):
    if img is None: return (180,180,200,255)
    w,h=img.size
    u=u%1.0; v=1.0-(v%1.0)
    px=int(u*w)%w; py=int(v*h)%h
    try:
        p=img.getpixel((px,py))
        if len(p)>=4: return p
        if len(p)==3: return (p[0],p[1],p[2],255)
        return (p[0],p[0],p[0],255)
    except: return (180,180,200,255)

def render_model(model, tex_dir, W=320, H=320, textured=True):
    """Render a model to a PIL Image."""
    # Collect all renderable mesh nodes
    mesh_nodes = []
    def _walk(n):
        if n.is_mesh and n.vertices and n.faces: mesh_nodes.append(n)
        for c in n.children: _walk(c)
    if model.root_node: _walk(model.root_node)

    if not mesh_nodes:
        img = Image.new('RGB',(W,H),(20,20,40))
        ImageDraw.Draw(img).text((10,H//2),"No geometry",(200,100,100))
        return img

    # Compute world verts for camera framing (UV nodes only for render bounds)
    wverts = []
    wt_cache = {}
    def get_wt(n):
        nid=id(n)
        if nid not in wt_cache:
            wp,wo = n.world_transform()
            wo_rot=math.sqrt(wo[0]**2+wo[1]**2+wo[2]**2)
            wt_cache[nid]=(wp,wo,wo_rot<0.001)
        return wt_cache[nid]

    for n in mesh_nodes:
        if not n.uvs: continue  # render bounds: UV nodes only
        wp,wo,is_id = get_wt(n)
        for v in n.vertices:
            wv = _apply_vtx(n,v,wp,wo,is_id)
            wverts.append(wv)

    if not wverts:
        # Fall back to all verts
        for n in mesh_nodes:
            wp,wo,is_id = get_wt(n)
            for v in n.vertices:
                wv = _apply_vtx(n,v,wp,wo,is_id)
                wverts.append(wv)

    xs=[v[0] for v in wverts]; ys=[v[1] for v in wverts]; zs=[v[2] for v in wverts]
    bb_min=(min(xs),min(ys),min(zs)); bb_max=(max(xs),max(ys),max(zs))

    eye,right,up,fwd = camera_for_bb(bb_min,bb_max)
    light_dir = _normalize((0.6,0.5,1.0))
    ambient = 0.22

    # Load textures
    tex_cache = {}
    if textured:
        for n in mesh_nodes:
            tn = n.texture_clean.lower()
            if tn and tn not in ('null','') and tn not in tex_cache:
                tex_cache[tn] = load_texture(tn, tex_dir)

    # Collect triangles
    tris = []
    for n in mesh_nodes:
        is_helper = not n.uvs
        wp,wo,is_id = get_wt(n)
        world_verts = [_apply_vtx(n,v,wp,wo,is_id) for v in n.vertices]
        nv=len(n.vertices); nn=len(n.normals); nuv=len(n.uvs)
        tn = n.texture_clean.lower() if n.texture_clean else ''
        tex_img = tex_cache.get(tn) if (textured and tn and tn!='null') else None

        for face in n.faces:
            if len(face)<3: continue
            v0,v1,v2=face[0],face[1],face[2]
            if v0>=nv or v1>=nv or v2>=nv: continue
            wv0=world_verts[v0]; wv1=world_verts[v1]; wv2=world_verts[v2]
            p0=project(*wv0,eye,right,up,fwd,W,H)
            p1=project(*wv1,eye,right,up,fwd,W,H)
            p2=project(*wv2,eye,right,up,fwd,W,H)
            if p0 is None or p1 is None or p2 is None: continue
            depth=(p0[2]+p1[2]+p2[2])/3.0

            # Normal
            if nn>max(v0,v1,v2):
                nx=(n.normals[v0][0]+n.normals[v1][0]+n.normals[v2][0])/3
                ny=(n.normals[v0][1]+n.normals[v1][1]+n.normals[v2][1])/3
                nz=(n.normals[v0][2]+n.normals[v1][2]+n.normals[v2][2])/3
                nl=math.sqrt(nx*nx+ny*ny+nz*nz)
                if nl>1e-9: nx/=nl;ny/=nl;nz/=nl
                norm=(nx,ny,nz)
            else:
                e1=_sub(wv1,wv0); e2=_sub(wv2,wv0)
                norm=_normalize(_cross(e1,e2))

            ndotl=max(0,_dot(norm,light_dir))
            ndotl=max(ndotl,max(0,-_dot(norm,light_dir))*0.35)
            shade=ambient+(1-ambient)*ndotl

            if is_helper:
                fill=(int(30*shade),int(30*shade),int(50*shade))
                tris.append((depth,((p0[0],p0[1]),(p1[0],p1[1]),(p2[0],p2[1])),fill,None,None,None))
                continue

            # UV
            uv0=uv1=uv2=(0.5,0.5)
            if nuv>0:
                ui0=min(v0,nuv-1); ui1=min(v1,nuv-1); ui2=min(v2,nuv-1)
                uv0,uv1,uv2=n.uvs[ui0],n.uvs[ui1],n.uvs[ui2]

            if textured and tex_img is not None:
                # Compute centroid UV for flat-approx textured render
                uc=(uv0[0]+uv1[0]+uv2[0])/3; vc=(uv0[1]+uv1[1]+uv2[1])/3
                tc=sample_tex(tex_img,uc,vc)
                r=int(_clamp(tc[0]*shade,0,255))
                g=int(_clamp(tc[1]*shade,0,255))
                b=int(_clamp(tc[2]*shade,0,255))
                fill=(r,g,b)
            else:
                dr=int(_clamp(n.diffuse[0]*220*shade,30,240))
                dg=int(_clamp(n.diffuse[1]*220*shade,30,240))
                db=int(_clamp(n.diffuse[2]*220*shade,30,240))
                fill=(dr,dg,db)
                if n.is_skin: db=min(db+25,255)

            tris.append((depth,((p0[0],p0[1]),(p1[0],p1[1]),(p2[0],p2[1])),fill,tex_img,uv0,(uv1,uv2)))

    tris.sort(key=lambda t: -t[0])

    img=Image.new('RGB',(W,H),(18,18,40))
    draw=ImageDraw.Draw(img)

    for _,pts,fill,_,_,_ in tris:
        flat=[pts[0][0],pts[0][1],pts[1][0],pts[1][1],pts[2][0],pts[2][1]]
        draw.polygon(flat,fill=fill)

    return img

def analyze_model(model_name, issues):
    """Return status line for a model."""
    mdl_path=os.path.join(MODEL_DIR,model_name+".mdl")
    mdx_path=os.path.join(MODEL_DIR,model_name+".mdx")
    if not os.path.exists(mdl_path):
        return None, f"MISSING: {model_name}"

    try:
        model=MDLBinaryParser.parse_files(mdl_path,mdx_path)
    except Exception as e:
        return None, f"PARSE ERROR {model_name}: {e}"

    # Gather stats
    mesh_nodes=[n for n in model.all_nodes() if n.is_mesh]
    uv_nodes=[n for n in mesh_nodes if n.uvs]
    skin_nodes=[n for n in mesh_nodes if n.is_skin]
    vc=sum(len(n.vertices) for n in mesh_nodes)
    fc=sum(len(n.faces) for n in mesh_nodes)
    textures=model.texture_list()

    rbb_min, rbb_max = model.render_bounds()
    dx=rbb_max[0]-rbb_min[0]; dy=rbb_max[1]-rbb_min[1]; dz=rbb_max[2]-rbb_min[2]
    size_ok = dx>0.01 and (dy>0.01 or dz>0.01)

    # Check textures exist
    missing=[t for t in textures if t.upper()!='NULL' and not any(
        os.path.exists(os.path.join(TEX_DIR,t+ext)) for ext in ('.tga','.tpc','.png')
    )]

    # Check for exploded geometry (render bounds too large vs expected model size)
    max_dim = max(dx,dy,dz)
    exploded = max_dim > 20.0  # 20m would be abnormal for a creature

    issue_list = []
    if missing: issue_list.append(f"missing_tex:{missing[:3]}")
    if exploded: issue_list.append(f"exploded_bounds:{max_dim:.1f}m")
    if not uv_nodes: issue_list.append("no_uv_nodes")
    if vc==0: issue_list.append("no_verts")

    status = "OK" if not issue_list else ("WARN: "+", ".join(issue_list))
    if issue_list:
        issues[model_name] = issue_list

    info = (f"V={vc} F={fc} mesh={len(mesh_nodes)} uv={len(uv_nodes)} "
            f"skin={len(skin_nodes)} tex={len(textures)} "
            f"bounds={dx:.2f}x{dy:.2f}x{dz:.2f}m")

    return model, status, info


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("\n" + "="*70)
    print("  GhostRigger-K1-K2  Full Model Render Test")
    print("="*70)

    issues = {}
    models_ok = []
    models_warn = []
    models_fail = []

    # Grid layout: 6 per row, flat + textured side by side
    COLS = 6
    CELL_W = 300; CELL_H = 300
    LABEL_H = 24

    # Collect all rendered images for grid
    render_results = {}

    for model_name in MODELS:
        result = analyze_model(model_name, issues)
        if result[0] is None:
            models_fail.append(model_name)
            print(f"  ✗ {model_name:20s} {result[1]}")
            continue

        model, status, info = result
        if "WARN" in status:
            models_warn.append(model_name)
            print(f"  ⚠ {model_name:20s} {status}")
            print(f"    {info}")
        else:
            models_ok.append(model_name)
            print(f"  ✓ {model_name:20s} {info}")

        # Render flat and textured
        try:
            flat_img = render_model(model, TEX_DIR, W=CELL_W, H=CELL_H, textured=False)
            tex_img  = render_model(model, TEX_DIR, W=CELL_W, H=CELL_H, textured=True)
            render_results[model_name] = (flat_img, tex_img, status)
        except Exception as e:
            print(f"  ✗ Render error {model_name}: {e}")
            import traceback; traceback.print_exc()
            models_fail.append(model_name)

    # Build combined grid: flat on left, textured on right for each model
    n = len(render_results)
    ROWS = (n + COLS - 1) // COLS
    grid_w = COLS * CELL_W * 2 + COLS * 4  # 2 views per model + gap
    grid_h = ROWS * (CELL_H + LABEL_H) + 60

    grid = Image.new('RGB', (grid_w, grid_h), (12,12,28))
    gdraw = ImageDraw.Draw(grid)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    except:
        font = font_sm = ImageFont.load_default()

    gdraw.text((10,8), "GhostRigger-K1-K2 | Full Model Render Test", fill=(200,200,255), font=font)
    gdraw.text((10,26), f"Models: {len(MODELS)}  OK: {len(models_ok)}  Warn: {len(models_warn)}  Fail: {len(models_fail)}", fill=(160,160,200), font=font_sm)

    for idx,(model_name,(flat_img,tex_img,status)) in enumerate(render_results.items()):
        row = idx // COLS
        col = idx % COLS
        x0 = col * (CELL_W * 2 + 4)
        y0 = 50 + row * (CELL_H + LABEL_H)

        # Flat view
        grid.paste(flat_img, (x0, y0 + LABEL_H))
        # Textured view
        grid.paste(tex_img, (x0 + CELL_W, y0 + LABEL_H))

        # Label
        col_txt = (100,255,100) if "OK" in status else (255,200,80)
        gdraw.text((x0+2, y0+2), f"{model_name}", fill=col_txt, font=font_sm)
        gdraw.text((x0+CELL_W, y0+2), "FLAT", fill=(130,130,180), font=font_sm)
        gdraw.text((x0+CELL_W+30, y0+2), "|", fill=(80,80,120), font=font_sm)
        gdraw.text((x0+CELL_W+40, y0+2), "TEX", fill=(130,180,130), font=font_sm)

        # Draw separator line
        gdraw.line([x0+CELL_W-1, y0+LABEL_H, x0+CELL_W-1, y0+LABEL_H+CELL_H], fill=(50,50,100), width=1)

    out_path = os.path.join(OUTPUT_DIR, "v2.0_full_test.png")
    grid.save(out_path)
    print(f"\n  → Grid saved: {out_path} ({grid_w}x{grid_h})")

    # Print summary
    print("\n" + "="*70)
    print(f"  Results: {len(models_ok)}/{len(MODELS)} OK, {len(models_warn)} warnings, {len(models_fail)} failures")
    if issues:
        print("\n  Issues found:")
        for m,iss in issues.items():
            print(f"    {m}: {', '.join(iss)}")
    print("="*70)
    return 0 if not models_fail else 1

if __name__ == '__main__':
    sys.exit(main())
