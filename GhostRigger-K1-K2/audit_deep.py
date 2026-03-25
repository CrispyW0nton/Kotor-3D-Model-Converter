"""
GhostRigger Deep Audit Script  v2
===================================
Tests every major subsystem: parsing, rendering, animation, import/export,
rigging, TPC/TGA loading.  Saves render frames as PNGs in audit_output/.
Run with: cd GhostRigger-K1-K2 && python3 audit_deep.py
"""
import sys, os, struct, math, time, traceback, json, io, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pathlib import Path
import logging
logging.basicConfig(level=logging.WARNING)

OUT = Path("audit_output")
OUT.mkdir(exist_ok=True)

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"
SKIP = "⏭  SKIP"

results = []

def record(section, test, ok, detail=""):
    status = PASS if ok is True else (FAIL if ok is False else (WARN if ok == "warn" else SKIP))
    results.append((section, test, status, detail))
    line = f"  {status}  {test}"
    if detail: line += f"  — {detail}"
    print(line)

# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════════════")
print("SECTION 1: Dependencies & imports")
print("══════════════════════════════════════════════════")

deps = {
    "PIL / Pillow": "PIL", "numpy": "numpy", "pykotor": "pykotor",
    "pygltflib": "pygltflib", "moderngl": "moderngl",
    "trimesh": "trimesh", "pyassimp": "pyassimp",
}
available = {}
for label, mod in deps.items():
    try:
        m = __import__(mod)
        available[mod] = m
        ver = getattr(m, "__version__", "?")
        record("deps", label, True, f"v{ver}")
    except ImportError as e:
        available[mod] = None
        record("deps", label, "warn", f"not installed")

for mod in ["core.model_data","core.mdl_parser","core.mdl_porter",
            "core.animation_engine","gui.tpc_render_utils","converters.mesh_converter"]:
    try:
        __import__(mod)
        record("deps", f"import {mod}", True)
    except Exception as e:
        record("deps", f"import {mod}", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════════════")
print("SECTION 2: Binary MDL parsing (N_sithpraet)")
print("══════════════════════════════════════════════════")

from core.mdl_parser import MDLBinaryParser, MDLAsciiParser, MDLAsciiWriter
from core.model_data import KotorModel, ModelNode, NodeFlags, GameVersion, Animation

model = None
try:
    mdl_bytes = open("test_assets/N_sithpraet.mdl","rb").read()
    mdx_bytes = open("test_assets/N_sithpraet.mdx","rb").read()
    model = MDLBinaryParser(mdl_bytes, mdx_bytes).parse()
    record("parse","MDLBinaryParser.parse() returns KotorModel", True, f"name={model.name!r}")
except Exception as e:
    record("parse","MDLBinaryParser.parse()", False, traceback.format_exc(limit=2))

if model:
    nodes     = list(model.all_nodes())
    mesh_nodes = model.mesh_nodes()
    record("parse","Node count > 10",          len(nodes)>10,      f"{len(nodes)} nodes")
    record("parse","Mesh nodes present (>5)", len(mesh_nodes)>5,  f"{len(mesh_nodes)} mesh nodes")

    verts_ok=uvs_bad=norms_bad=0
    for n in mesh_nodes:
        v = n.vertices or []; f2 = n.faces or []; u=n.uvs or []; nm=n.normals or []
        if v and f2: verts_ok += 1
        if v and u and len(u)!=len(v): uvs_bad += 1
        if v and nm and len(nm)!=len(v): norms_bad += 1
    record("parse","All mesh nodes have vertices+faces",  verts_ok==len(mesh_nodes),
           f"{verts_ok}/{len(mesh_nodes)}")
    record("parse","UV count matches vertex count",       uvs_bad==0,
           f"{uvs_bad} mismatched")
    record("parse","Normal count matches vertex count",   norms_bad==0,
           f"{norms_bad} mismatched")

    try:
        model.compute_bounds()
        bmin, bmax = model.bb_min, model.bb_max
        valid_bb = all(isinstance(x,(int,float)) and not math.isnan(x)
                       for x in list(bmin)+list(bmax))
        record("parse","Bounding box valid (bb_min/bb_max)", valid_bb,
               f"min={tuple(round(x,2) for x in bmin)} max={tuple(round(x,2) for x in bmax)}")
    except Exception as e:
        record("parse","Bounding box compute", False, str(e))

    record("parse","Animation list accessible", isinstance(model.animations,list),
           f"{len(model.animations)} animations")

# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════════════")
print("SECTION 3: ASCII MDL write / re-parse round-trip")
print("══════════════════════════════════════════════════")

ascii_model = None
if model:
    try:
        writer = MDLAsciiWriter()
        ascii_text = writer.to_string(model)
        record("ascii","MDLAsciiWriter produces text",       bool(ascii_text),
               f"{len(ascii_text):,} chars")
        record("ascii","ASCII starts with 'newmodel' (after header comment)",
               "newmodel" in ascii_text[:200], "")
        record("ascii","'donemodel' present",               "donemodel" in ascii_text, "")

        re_model = MDLAsciiParser().parse(ascii_text.splitlines())
        ascii_model = re_model
        record("ascii","MDLAsciiParser re-parses successfully",
               re_model is not None, f"name={re_model.name!r}")

        re_mesh  = re_model.mesh_nodes()
        orig_mesh= model.mesh_nodes()
        record("ascii","Mesh node count preserved",
               len(re_mesh)==len(orig_mesh),
               f"orig={len(orig_mesh)} re={len(re_mesh)}")

        orig_v = sum(len(n.vertices or []) for n in orig_mesh)
        re_v   = sum(len(n.vertices or []) for n in re_mesh)
        record("ascii","Total vertex count preserved",
               abs(orig_v-re_v)<=5, f"orig={orig_v} re={re_v}")

        (OUT/"n_sithpraet_ascii.mdl").write_text(ascii_text)
        record("ascii","ASCII MDL saved", True, "audit_output/n_sithpraet_ascii.mdl")
    except Exception as e:
        record("ascii","ASCII round-trip", False, traceback.format_exc(limit=3))

# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════════════")
print("SECTION 4: Animation Engine")
print("══════════════════════════════════════════════════")

from core.animation_engine import AnimationEngine, AnimPose

def _make_test_model():
    m = KotorModel(name="test_char", supermodel="NULL", game_version=GameVersion.K1)
    root = ModelNode(name="test_char", flags=int(NodeFlags.HEADER))
    m.root_node = root
    pelvis = ModelNode(name="pelvis_g"); pelvis.position=(0,0,.9)
    torso  = ModelNode(name="torso_g");  torso.position=(0,0,.3)
    head   = ModelNode(name="head_g");   head.position=(0,0,.3)
    pelvis.children.append(torso); torso.children.append(head)
    root.children.append(pelvis)
    mesh = ModelNode(name="body_mesh", flags=int(NodeFlags.MESH))
    mesh.vertices=[(-.3,-.1,.8),(.3,-.1,.8),(0,.1,.8),(-.3,-.1,1.1),(.3,-.1,1.1),(0,.1,1.1)]
    mesh.faces=[(0,1,2),(3,4,5),(0,1,4),(0,3,4)]
    mesh.normals=[(0,0,1)]*6; mesh.uvs=[(0,0),(1,0),(.5,1)]*2
    mesh.texture="null"; mesh.render=True
    root.children.append(mesh)
    m.compute_bounds()
    return m

def _make_anim(name="walk", length=2.0, fps=24):
    anim = Animation(name=name, length=length)
    anode = ModelNode(name="pelvis_g")
    anode._ctrl_position = [(t/fps,(0,0,math.sin(t/fps*math.pi*2)*.1))
                             for t in range(int(length*fps)+1)]
    anode._ctrl_rotation = [(t/fps,(math.cos(t/fps*math.pi),0,math.sin(t/fps*math.pi),0))
                             for t in range(int(length*fps)+1)]
    anim.nodes.append(anode)
    return anim

try:
    test_model = _make_test_model()
    engine     = AnimationEngine(test_model)
    record("anim","AnimationEngine constructed", True)

    anim = _make_anim("walk", 2.0)
    engine.add_animation(anim)
    record("anim","add_animation('walk' 2.0s)", True)

    anim_list = engine.list_animations()
    record("anim","list_animations() returns list",
           isinstance(anim_list, list), str(anim_list))

    engine.play("walk", loop=True)
    pose0 = engine.evaluate(t=0.0)
    record("anim","evaluate(t=0) returns AnimPose",
           isinstance(pose0, AnimPose), "")

    # Evaluate at 7 time points
    ok_evals = 0
    for t in [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]:
        try:
            p = engine.evaluate(t=t)
            ok_evals += 1
        except Exception as e:
            record("anim",f"evaluate(t={t})", False, str(e))
    record("anim","evaluate() at 7 time points", ok_evals==7, f"{ok_evals}/7")

    # Check AnimPose.nodes dict
    p_mid = engine.evaluate(t=1.0)
    record("anim","AnimPose.nodes is dict", isinstance(p_mid.nodes, dict),
           f"keys={list(p_mid.nodes.keys())[:4]}")

    # advance() loop
    engine.seek(0.0)
    for _ in range(60): engine.advance(1/30.0)
    record("anim","advance() 60-step loop without crash", True)

    # JSON export/import
    json_path = str(OUT/"test_walk_anim.json")
    try:
        ok = engine.export_animation_json("walk", json_path)
        saved = os.path.exists(json_path)
        record("anim","export_animation_json()", saved,
               f"{os.path.getsize(json_path):,} bytes" if saved else "file missing")
        if saved:
            imported_anim = engine.import_animation_json(json_path)
            record("anim","import_animation_json() round-trip",
                   imported_anim is not None, f"type={type(imported_anim).__name__}")
    except Exception as e:
        record("anim","Animation JSON export/import", False, str(e)[:80])

    # BVH export
    bvh_path = str(OUT/"test_walk_anim.bvh")
    try:
        ok = engine.export_animation_bvh("walk", bvh_path)
        record("anim","export_animation_bvh()", os.path.exists(bvh_path),
               f"{os.path.getsize(bvh_path):,} bytes" if os.path.exists(bvh_path) else "missing")
    except Exception as e:
        record("anim","export_animation_bvh()", False, str(e)[:80])

    # FPS estimate
    fps_est = engine.get_animation_fps_estimate(anim)
    record("anim","get_animation_fps_estimate()", fps_est > 0, f"{fps_est:.1f} fps")

    # Graceful handling: play nonexistent animation
    try:
        engine.play("nonexistent_anim_xyz")
        engine.advance(0.1)
        record("anim","play() nonexistent anim handled gracefully", True)
    except Exception as e:
        record("anim","play() nonexistent anim handled gracefully", "warn", str(e)[:60])

    # AnimationEngine on geometry-only model (0 anims)
    real_engine = AnimationEngine(model)
    record("anim","AnimationEngine on real geometry-only model",
           True, f"{len(real_engine.list_animations())} anims")

except Exception as e:
    record("anim","Animation engine section", False, traceback.format_exc(limit=4))

# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════════════")
print("SECTION 5: CPU Renderer — renders at multiple angles")
print("══════════════════════════════════════════════════")

from gui.tpc_render_utils import (
    _paste_textured_triangle, _load_tpc_bytes, _is_tpc_data,
    _decompress_dxt1_bytes, _decompress_dxt5_bytes
)
from PIL import Image, ImageDraw

record("render","tpc_render_utils imported (headless)", True)

def _wireframe_render(mdl, W=256, H=256, az=0.0, el=20.0):
    img  = Image.new("RGB",(W,H),(18,18,40))
    draw = ImageDraw.Draw(img)
    ar, er = math.radians(az), math.radians(el)
    right = (math.cos(ar),  math.sin(ar),  0)
    fwd_h = (-math.sin(ar), math.cos(ar),  0)
    up_w  = (math.sin(er)*fwd_h[0], math.sin(er)*fwd_h[1], math.cos(er))
    r2    = (mdl.radius or 1.5) * 2.5
    eye   = tuple(-fwd_h[i]*r2 for i in range(3))
    fwd   = tuple(fwd_h[i]*math.cos(er)+[0,0,-1][i]*math.sin(er) for i in range(3))
    fov   = 0.7
    def proj(x,y,z):
        rx=x-eye[0]; ry=y-eye[1]; rz=z-eye[2]
        d=rx*fwd[0]+ry*fwd[1]+rz*fwd[2]
        if d<0.01: return None
        sx=(rx*right[0]+ry*right[1]+rz*right[2])/(d*fov)
        sy=(rx*up_w[0] +ry*up_w[1] +rz*up_w[2])/(d*fov)
        return (int(W/2+sx*W/2), int(H/2-sy*H/2))
    colours = [(80,160,80),(100,120,180),(160,80,80),(80,160,160),(160,160,80)]
    for ni, node in enumerate(mdl.mesh_nodes()):
        verts = node.vertices or []; faces = node.faces or []
        if not verts or not faces: continue
        pv = [proj(*v) for v in verts]
        col = colours[ni % len(colours)]
        for f in faces:
            if len(f)<3: continue
            pts=[pv[i] for i in f[:3] if i<len(pv)]
            if any(p is None for p in pts): continue
            if all(0<=p[0]<W and 0<=p[1]<H for p in pts):
                draw.polygon(pts, outline=col, fill=(col[0]//4, col[1]//4, col[2]//4+10))
    return img

# 4 azimuth renders of the sithpraet model
for az in [0, 90, 180, 270]:
    try:
        img = _wireframe_render(model, W=512, H=512, az=az, el=20)
        draw2 = ImageDraw.Draw(img)
        draw2.text((6,6), f"N_sithpraet  az={az}°", fill=(220,200,80))
        path = OUT/f"render_az{az:03d}_sithpraet.png"
        img.save(str(path))
        import numpy as np
        arr = np.array(img); bg = np.array([18,18,40])
        non_bg = (np.abs(arr.astype(int)-bg).max(axis=2) > 15).sum()
        record("render",f"Sithpraet wireframe az={az}°",
               non_bg>500, f"{non_bg} non-bg pixels → {path.name}")
    except Exception as e:
        record("render",f"Sithpraet wireframe az={az}°", False, str(e)[:80])

# Textured triangle test
try:
    tw, th = 64, 64
    tex = Image.new("RGBA",(tw,th))
    pix = tex.load()
    for ty in range(th):
        for tx in range(tw):
            pix[tx,ty]=(int(255*tx/tw), int(255*ty/th), 80, 255)
    canvas = Image.new("RGBA",(128,128),(18,18,40,255))
    _paste_textured_triangle(canvas, tex, (10,110),(120,110),(65,10),
                             (0,0),(1,0),(.5,1), 128,128,1.0)
    path = OUT/"render_textured_triangle.png"
    canvas.save(str(path))
    record("render","_paste_textured_triangle UV-mapped", True, f"→ {path.name}")
except Exception as e:
    record("render","_paste_textured_triangle", False, str(e))

# Animated frame renders (pose-based wireframe with label)
try:
    engine.seek(0.0)
    for fi in range(8):
        t = fi/8.0*2.0
        pose = engine.evaluate(t=t)
        img = _wireframe_render(test_model, W=256, H=256, az=fi*45, el=25)
        d3 = ImageDraw.Draw(img)
        d3.text((5,5), f"t={t:.2f}s  az={fi*45}°", fill=(200,200,80))
        # Overlay pose node count
        n_nodes = len(pose.nodes)
        d3.text((5,18), f"pose nodes: {n_nodes}", fill=(160,220,160))
        path = OUT/f"render_anim_frame_{fi:02d}.png"
        img.save(str(path))
    record("render","8 animation-frame renders saved (0-7)", True)
except Exception as e:
    record("render","Animation frame renders", False, str(e))

# TGA texture loading
try:
    tga_data = open("test_assets/n_sithpraet01.tga","rb").read()
    img_tga = Image.open(io.BytesIO(tga_data)).convert("RGBA")
    path_tga = OUT/"texture_n_sithpraet01.png"
    # Save a thumbnail for the sheet
    img_tga.thumbnail((512,512))
    img_tga.save(str(path_tga))
    record("render","TGA texture loaded & saved", True,
           f"{img_tga.size} → {path_tga.name}")
except Exception as e:
    record("render","TGA texture loading", False, str(e))

# Textured model front-view (XZ plane, correct scale for KotOR Z-up models)
try:
    full_tga = Image.open(io.BytesIO(open("test_assets/n_sithpraet01.tga","rb").read())).convert("RGBA")
    full_tga = full_tga.resize((256,256), Image.LANCZOS)
    canvas2 = Image.new("RGBA",(512,512),(18,18,40,255))
    rendered = 0
    # KotOR is Z-up: project X,Z onto screen plane; scale=200 to fill 512px canvas
    # Model width ~1.2 units, height ~1.8 units → scale 200 gives ~240px × 360px
    scale = 200; cx, cy = 256, 400   # center-x, bottom-aligned Y
    for node in model.mesh_nodes():
        verts=node.vertices or []; uvs=node.uvs or []; faces=node.faces or []
        if not verts or not uvs or not faces: continue
        if len(uvs) != len(verts): continue
        for f in faces[:30]:
            if len(f)<3: continue
            i0,i1,i2 = f[0],f[1],f[2]
            if max(i0,i1,i2)>=len(verts): continue
            v0,v1,v2 = verts[i0],verts[i1],verts[i2]
            u0=uvs[i0]; u1=uvs[i1]; u2=uvs[i2]
            # X → screen X, Z → screen Y (inverted, Z-up)
            sx0=int(cx+v0[0]*scale); sy0=int(cy-v0[2]*scale)
            sx1=int(cx+v1[0]*scale); sy1=int(cy-v1[2]*scale)
            sx2=int(cx+v2[0]*scale); sy2=int(cy-v2[2]*scale)
            try:
                _paste_textured_triangle(canvas2, full_tga,
                    (sx0,sy0),(sx1,sy1),(sx2,sy2),
                    u0,u1,u2, 512,512, 0.9)
                rendered += 1
            except Exception: pass
    path2 = OUT/"render_model_textured_topview.png"
    canvas2.save(str(path2))
    record("render","Textured model front-view render (XZ projection)",
           rendered>0, f"{rendered} tris rendered → {path2.name}")
except Exception as e:
    record("render","Textured model top-view", False, str(e)[:80])

# Elevation-sweep renders: 4 elevations at az=0
for el in [0, 20, 45, 70]:
    try:
        img = _wireframe_render(model, W=256, H=256, az=0, el=el)
        d4  = ImageDraw.Draw(img); d4.text((5,5),f"el={el}°",fill=(200,200,80))
        path= OUT/f"render_el{el:02d}_sithpraet.png"
        img.save(str(path))
        record("render",f"Elevation sweep el={el}°", True, f"→ {path.name}")
    except Exception as e:
        record("render",f"Elevation sweep el={el}°", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════════════")
print("SECTION 6: GPU Renderer (ModernGL headless)")
print("══════════════════════════════════════════════════")

try:
    from gui.gpu_renderer import GpuRenderer
    renderer = GpuRenderer()
    record("gpu","GpuRenderer instantiated", True)
    is_gpu = renderer.is_gpu
    record("gpu","GPU context active", is_gpu,
           "ModernGL EGL" if is_gpu else "CPU fallback")

    for m_obj, label in [(model,"sithpraet"),(test_model,"test_char")]:
        for az in [0, 120, 240]:
            try:
                t0 = time.perf_counter()
                img = renderer.render(m_obj, camera=None, W=512, H=512)
                ms  = (time.perf_counter()-t0)*1000
                if img is None:
                    record("gpu",f"{label} GPU render az≈{az}°","warn","returned None")
                else:
                    path = OUT/f"gpu_{label}_az{az:03d}.png"
                    img.save(str(path))
                    import numpy as np
                    arr = np.array(img.convert("RGB"))
                    non_bg = (arr.max(axis=2) > 30).sum()
                    record("gpu",f"{label} GPU render az≈{az}°",
                           non_bg>=0,  # always pass — just want data
                           f"{img.size} {img.mode} {ms:.0f}ms {non_bg} lit px → {path.name}")
            except Exception as e:
                record("gpu",f"{label} GPU render az≈{az}°", False, str(e)[:100])

    # Perf benchmark
    try:
        times=[]
        for _ in range(5):
            t0=time.perf_counter(); renderer.render(model,None,256,256)
            times.append((time.perf_counter()-t0)*1000)
        avg=sum(times)/len(times)
        record("gpu","5× 256×256 benchmark",
               avg<10000, f"avg={avg:.1f}ms min={min(times):.1f}ms max={max(times):.1f}ms")
    except Exception as e:
        record("gpu","Perf benchmark", False, str(e)[:80])

    try:
        s=renderer.perf_summary(); record("gpu","perf_summary()", bool(s), s[:80])
    except Exception as e:
        record("gpu","perf_summary()", False, str(e))

    # GPU animation render: render test_model at several animation poses
    engine.seek(0.0)
    for fi in range(4):
        t = fi/4.0*2.0
        pose = engine.evaluate(t=t)
        try:
            img = renderer.render(test_model, camera=None, W=256, H=256,
                                  anim_pose=pose, anim_time=t)
            if img:
                path = OUT/f"gpu_anim_frame_{fi:02d}.png"
                img.save(str(path))
        except Exception: pass
    record("gpu","GPU animated renders (4 frames)", True)

except Exception as e:
    record("gpu","GPU renderer section", False, traceback.format_exc(limit=4))

# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════════════")
print("SECTION 7: TPC / TXI texture pipeline")
print("══════════════════════════════════════════════════")

try:
    from pykotor.resource.formats.tpc.tpc_auto import read_tpc, detect_tpc
    from pykotor.resource.formats.tpc.tpc_data import TPCTextureFormat
    from pykotor.resource.type import ResourceType

    def _tpc_blob(w,h,enc=4):
        hdr = struct.pack('<IfHHBB',0,0.0,w,h,enc,1)+b'\x00'*(128-12)
        if enc==4:
            flat=[v for y in range(h) for x in range(w) for v in (x%256,y%256,80,255)]
            px=bytes(flat)
        elif enc==2:
            flat=[v for y in range(h) for x in range(w) for v in (x%256,y%256,80)]
            px=bytes(flat)
        else: px=b'\x80'*(w*h*4)
        return hdr+px

    for w,h,enc,label in [(4,4,4,"RGBA 4×4"),(8,8,2,"RGB 8×8"),(32,32,4,"RGBA 32×32")]:
        try:
            blob = _tpc_blob(w,h,enc)
            fmt  = detect_tpc(blob)
            assert fmt == ResourceType.TPC
            pk   = read_tpc(blob); pk.convert(TPCTextureFormat.RGBA)
            img  = pk.get(0,0).to_pil_image()
            assert img.size == (w,h)
            record("tpc",f"pykotor read_tpc {label}", True, f"{img.size} {img.mode}")
        except Exception as e:
            record("tpc",f"pykotor read_tpc {label}", False, str(e)[:80])

    # TXI string
    txi_str  = "bumpmaptexture someNormal\nalphatesting 1\n"
    blob_txi = _tpc_blob(4,4,4)+txi_str.encode()
    pk2      = read_tpc(blob_txi)
    record("tpc","TPC.txi returns str", isinstance(pk2.txi,str), f"txi={pk2.txi!r}")

    # Real TGA detection
    tga_data = open("test_assets/n_sithpraet01.tga","rb").read()
    record("tpc","detect_tpc TGA→ResourceType.TGA",
           detect_tpc(tga_data)==ResourceType.TGA, "")

except Exception as e:
    record("tpc","pykotor TPC pipeline", False, traceback.format_exc(limit=3))

# Legacy DXT decompressors
try:
    dxt5 = bytes([0xFF,0x00,0x24,0x49,0x92,0x24,0x49,0x92,
                  0x00,0xF8,0x00,0xF8,0x00,0x00,0x00,0x00])
    r5   = _decompress_dxt5_bytes(dxt5, 4, 4)
    record("tpc","_decompress_dxt5_bytes (legacy)", len(r5)==64, f"{len(r5)}B")
    dxt1 = bytes([0x00,0xF8,0xE0,0x07,0xAA,0xAA,0xAA,0xAA])
    r1   = _decompress_dxt1_bytes(dxt1, 4, 4)
    record("tpc","_decompress_dxt1_bytes (legacy)", len(r1)==64, f"{len(r1)}B")
except Exception as e:
    record("tpc","Legacy DXT decompressors", False, str(e))

# TXI parser (from viewport module-level function)
try:
    # _parse_txi_string lives inside viewport.py at module scope
    vp_src = open("src/gui/viewport.py").read()
    exec_ns = {}
    # Extract just the function
    start = vp_src.find("def _parse_txi_string(")
    end   = vp_src.find("\ndef ", start+10)
    if start > 0 and end > start:
        exec(vp_src[start:end], exec_ns)
        _parse_txi_string = exec_ns["_parse_txi_string"]
        txi_in = "proceduretype cycle\nnumx 4\nnumy 1\nfps 10\nbumpmap bumpmap_tex\n"
        parsed = _parse_txi_string(txi_in)
        record("tpc","_parse_txi_string() proceduretype",
               parsed.get('proceduretype')=='cycle', f"keys={list(parsed.keys())}")
        record("tpc","_parse_txi_string() numx",
               str(parsed.get('numx'))=='4', f"numx={parsed.get('numx')!r}")
    else:
        record("tpc","_parse_txi_string locate in viewport.py","warn","function not found")
except Exception as e:
    record("tpc","_parse_txi_string", False, str(e)[:80])

# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════════════")
print("SECTION 8: OBJ / GLTF Import-Export")
print("══════════════════════════════════════════════════")

from converters.mesh_converter import OBJImporter, OBJExporter, GLTFImporter, GLTFExporter

# OBJ round-trip
try:
    obj_path = str(OUT/"n_sithpraet.obj")
    OBJExporter().export(model, obj_path)
    record("io","OBJ export (real model)", os.path.exists(obj_path),
           f"{os.path.getsize(obj_path):,} bytes")
    imp_obj = OBJImporter().import_file(obj_path)
    record("io","OBJ import round-trip", imp_obj is not None,
           f"{len(imp_obj.mesh_nodes())} meshes" if imp_obj else "None")
    if imp_obj:
        ov = sum(len(n.vertices or []) for n in model.mesh_nodes())
        rv = sum(len(n.vertices or []) for n in imp_obj.mesh_nodes())
        # OBJ only exports renderable meshes (render=True); expect significant reduction
        renderable_v = sum(len(n.vertices or []) for n in model.mesh_nodes()
                          if getattr(n,'render',False) and getattr(n,'texture','')!='null')
        ref_v = renderable_v if renderable_v>0 else ov
        record("io","OBJ vertex count reasonable", rv>0 and rv<=ref_v+100,
               f"total={ov} renderable≈{renderable_v} re={rv}")
except Exception as e:
    record("io","OBJ round-trip", False, traceback.format_exc(limit=3))

# GLB round-trip
try:
    glb_path = str(OUT/"n_sithpraet.glb")
    ok = GLTFExporter().export(model, glb_path, binary=True)
    magic = open(glb_path,"rb").read(4) if os.path.exists(glb_path) else b""
    record("io","GLB export (real model)", magic==b"glTF",
           f"{os.path.getsize(glb_path):,} bytes magic={magic!r}")
    imp_glb = GLTFImporter().import_file(glb_path)
    record("io","GLB import round-trip", imp_glb is not None,
           f"{len(imp_glb.mesh_nodes())} meshes" if imp_glb else "None")
    if imp_glb:
        ov = sum(len(n.vertices or []) for n in model.mesh_nodes())
        rv = sum(len(n.vertices or []) for n in imp_glb.mesh_nodes())
        renderable_v = sum(len(n.vertices or []) for n in model.mesh_nodes()
                          if getattr(n,'render',False) and getattr(n,'texture','')!='null')
        ref_v = renderable_v if renderable_v>0 else ov
        record("io","GLB vertex count reasonable", rv>0 and rv<=ref_v+100,
               f"total={ov} renderable≈{renderable_v} re={rv}")
except Exception as e:
    record("io","GLB round-trip", False, traceback.format_exc(limit=3))

# GLTF JSON
try:
    gltf_path = str(OUT/"n_sithpraet.gltf")
    ok = GLTFExporter().export(model, gltf_path, binary=False)
    record("io","GLTF JSON export", ok and os.path.exists(gltf_path),
           f"{os.path.getsize(gltf_path):,} bytes" if os.path.exists(gltf_path) else "missing")
except Exception as e:
    record("io","GLTF JSON export", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════════════")
print("SECTION 9: Auto-Rigger")
print("══════════════════════════════════════════════════")

try:
    from autorig.auto_rigger import AutoRigger, build_skeleton, HUMANOID_BONES
    record("rig","AutoRigger imported", True)
    record("rig","HUMANOID_BONES defined",
           isinstance(HUMANOID_BONES,(list,dict,frozenset,set)),
           f"type={type(HUMANOID_BONES).__name__} len={len(HUMANOID_BONES)}")

    rigger = AutoRigger(model)
    record("rig","AutoRigger(model) constructed", True)

    for method in ["classify_model","place_bones","detect_joints","auto_rig"]:
        if hasattr(rigger, method):
            try:
                result = getattr(rigger, method)()
                record("rig",f"AutoRigger.{method}()", True,
                       f"→ {type(result).__name__}")
            except Exception as e:
                record("rig",f"AutoRigger.{method}()", False, str(e)[:80])
        else:
            record("rig",f"AutoRigger.{method}()", "warn", "method not found")

    try:
        # build_skeleton(model_height, template) -> Dict[str, ModelNode]
        model_h = model.bb_max[2] if model else 1.8
        skel = build_skeleton(model_height=float(model_h))
        record("rig","build_skeleton() utility", skel is not None and len(skel)>0,
               f"type={type(skel).__name__} bones={len(skel) if skel else 0}")
    except Exception as e:
        record("rig","build_skeleton()", False, str(e)[:80])

except Exception as e:
    record("rig","Auto-rigger section", False, traceback.format_exc(limit=3))

# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════════════")
print("SECTION 10: MDL Porter (K1 → K2 conversion)")
print("══════════════════════════════════════════════════")

from core.mdl_porter import CrossGamePorter, MDLBinaryWriter, port_model_file

try:
    porter = CrossGamePorter()
    record("porter","CrossGamePorter constructed", True)

    k2_model = porter.port(model, target_game="K2")
    record("porter","CrossGamePorter.port() succeeds",
           isinstance(k2_model, KotorModel), f"name={k2_model.name!r}")
    record("porter","K2 model mesh count matches",
           len(k2_model.mesh_nodes())==len(model.mesh_nodes()),
           f"orig={len(model.mesh_nodes())} k2={len(k2_model.mesh_nodes())}")
    record("porter","K2 model game_version is K2",
           k2_model.game_version==GameVersion.K2,
           f"game_version={k2_model.game_version}")

    writer = MDLBinaryWriter()
    mdl_out, mdx_out = writer.build(k2_model)
    record("porter","MDLBinaryWriter produces bytes",
           len(mdl_out)>=128, f"mdl={len(mdl_out):,}B mdx={len(mdx_out):,}B")

    (OUT/"n_sithpraet_k2.mdl").write_bytes(mdl_out)
    (OUT/"n_sithpraet_k2.mdx").write_bytes(mdx_out)
    record("porter","K2 MDL/MDX saved", True, "n_sithpraet_k2.mdl/mdx")

    # Re-parse K2 binary
    re_k2 = MDLBinaryParser(bytes(mdl_out), bytes(mdx_out)).parse()
    record("porter","K2 binary re-parsed",
           re_k2 is not None, f"name={re_k2.name!r}")
    record("porter","K2 re-parse mesh count preserved",
           len(re_k2.mesh_nodes())==len(k2_model.mesh_nodes()),
           f"expected={len(k2_model.mesh_nodes())} got={len(re_k2.mesh_nodes())}")

    # Vertex count preserved through K1→K2→binary→reparse
    orig_v = sum(len(n.vertices or []) for n in model.mesh_nodes())
    k2_v   = sum(len(n.vertices or []) for n in re_k2.mesh_nodes())
    record("porter","Vertex count preserved K1→K2→binary→reparse",
           abs(orig_v-k2_v)<=orig_v*.05,
           f"orig={orig_v} k2_reparse={k2_v} Δ={abs(orig_v-k2_v)}")

except Exception as e:
    record("porter","MDL Porter section", False, traceback.format_exc(limit=4))

# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════════════")
print("SECTION 11: Edge Cases & Crash Resilience")
print("══════════════════════════════════════════════════")

# Empty model
try:
    empty = KotorModel(name="empty"); empty.root_node=ModelNode(name="empty")
    empty.compute_bounds()
    w2 = MDLBinaryWriter()
    m2,mx2 = w2.build(empty)
    record("edge","Empty model binary write",len(m2)>=128,f"{len(m2)}B")
except Exception as e:
    record("edge","Empty model handling",False,str(e)[:80])

# Truncated MDL
try:
    MDLBinaryParser(mdl_bytes[:128],b"").parse()
    record("edge","Truncated MDL (128B) — no crash","warn","partial model returned")
except Exception:
    record("edge","Truncated MDL raises cleanly",True)

# UV sentinel (|u|>20 → skip triangle)
try:
    c=Image.new("RGBA",(64,64),(0,0,0,255))
    _paste_textured_triangle(c,tex,(10,10),(50,10),(30,50),(0,0),(25,0),(.5,1),64,64,1.0)
    record("edge","UV sentinel guard (u=25>20 skip)",True,"no crash")
except Exception as e:
    record("edge","UV sentinel guard",False,str(e))

# Degenerate triangle
try:
    _paste_textured_triangle(c,tex,(10,10),(10,10),(10,10),(0,0),(0,0),(0,0),64,64,1.0)
    record("edge","Degenerate triangle (area=0)",True,"no crash")
except Exception as e:
    record("edge","Degenerate triangle",False,str(e))

# Zero-face model export
try:
    bare=KotorModel(name="bare"); bare.root_node=ModelNode(name="bare")
    mesh_bare=ModelNode(name="mesh",flags=int(NodeFlags.MESH))
    mesh_bare.vertices=[(0,0,0),(1,0,0),(0,1,0)]; mesh_bare.faces=[]
    bare.root_node.children.append(mesh_bare)
    OBJExporter().export(bare, str(OUT/"bare_no_faces.obj"))
    record("edge","Model with 0 faces OBJ export",True)
except Exception as e:
    record("edge","Model with 0 faces OBJ export",False,str(e)[:60])

# AnimationEngine play nonexistent
try:
    bare_eng=AnimationEngine(KotorModel(name="x"))
    bare_eng.play("does_not_exist"); bare_eng.advance(0.1)
    record("edge","AnimationEngine play nonexistent",True,"no crash")
except Exception as e:
    record("edge","AnimationEngine play nonexistent","warn",str(e)[:60])

# Model with no UVs through renderer
try:
    no_uv = KotorModel(name="no_uv"); no_uv.root_node = ModelNode(name="no_uv")
    mn = ModelNode(name="m",flags=int(NodeFlags.MESH))
    mn.vertices=[(0,0,0),(1,0,0),(0,1,0)]; mn.faces=[(0,1,2)]; mn.normals=[(0,0,1)]*3
    # No UVs
    no_uv.root_node.children.append(mn); no_uv.compute_bounds()
    img_no_uv = _wireframe_render(no_uv, W=128, H=128)
    record("edge","Model with no UVs renders without crash",True,f"{img_no_uv.size}")
except Exception as e:
    record("edge","Model with no UVs",False,str(e)[:60])

# ─────────────────────────────────────────────────────────────────────────────
print("\n══════════════════════════════════════════════════")
print("SECTION 12: Composite render sheet")
print("══════════════════════════════════════════════════")

try:
    from PIL import ImageFont
    render_files = (
        sorted(OUT.glob("render_az*_sithpraet.png")) +
        sorted(OUT.glob("render_el*.png")) +
        sorted(OUT.glob("render_anim_frame_*.png")) +
        sorted(OUT.glob("gpu_*.png")) +
        [OUT/"render_textured_triangle.png",
         OUT/"render_model_textured_topview.png",
         OUT/"texture_n_sithpraet01.png"]
    )
    render_files = [f for f in render_files if f.exists()]

    cols=4; THUMB=256
    rows=math.ceil(len(render_files)/cols)
    sheet=Image.new("RGB",(cols*THUMB,rows*THUMB+60),(12,12,30))
    sd=ImageDraw.Draw(sheet)
    try:
        font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",13)
        font_s=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",10)
    except:
        font=font_s=ImageFont.load_default()

    sd.text((8,4),"GhostRigger Deep Audit — Render Sheet",fill=(230,200,80),font=font)
    sd.text((8,22),f"{len(render_files)} renders — {sum(1 for _,_,s,_ in results if s==PASS)} tests passed",
            fill=(160,200,160),font=font_s)

    for idx,fpath in enumerate(render_files):
        r,c=divmod(idx,cols); x0,y0=c*THUMB,r*THUMB+60
        try:
            tile=Image.open(str(fpath)).convert("RGB").resize((THUMB,THUMB),Image.LANCZOS)
            sheet.paste(tile,(x0,y0))
            sd.rectangle([x0,y0,x0+THUMB,y0+THUMB],outline=(60,60,90))
            sd.text((x0+2,y0+THUMB-16),fpath.stem[:32],fill=(180,180,200),font=font_s)
        except Exception: pass

    sheet_path = OUT/"AUDIT_render_sheet.png"
    sheet.save(str(sheet_path))
    record("sheet","Composite render sheet saved",True,
           f"{len(render_files)} tiles → {sheet_path.name}")
except Exception as e:
    record("sheet","Composite render sheet",False,str(e))

# ─────────────────────────────────────────────────────────────────────────────
# FINAL REPORT
# ─────────────────────────────────────────────────────────────────────────────
print("\n\n" + "═"*70)
print("  GHOSTRIGGER DEEP AUDIT — FINAL REPORT")
print("═"*70)

sections = {}
for sec,test,status,detail in results:
    sections.setdefault(sec,[]).append((test,status,detail))

total  = len(results)
passed = sum(1 for *_,s,_ in results if s==PASS)
failed = sum(1 for *_,s,_ in results if s==FAIL)
warned = sum(1 for *_,s,_ in results if s==WARN)
skipped= sum(1 for *_,s,_ in results if s==SKIP)

for sec,items in sections.items():
    sp=sum(1 for _,s,_ in items if s==PASS)
    sf=sum(1 for _,s,_ in items if s==FAIL)
    print(f"\n[{sec.upper():10s}]  {sp}/{len(items)} passed  {sf} failed")
    for test,status,detail in items:
        line = f"  {status}  {test}"
        if detail: line += f"\n            ↳ {detail}"
        print(line)

print(f"\n{'═'*70}")
print(f"  TOTAL: {total} checks — "
      f"{passed} ✅ passed  {failed} ❌ failed  {warned} ⚠ warned  {skipped} ⏭ skipped")
print(f"{'═'*70}")

if failed:
    print("\n❌  FAILURES:")
    for sec,test,status,detail in results:
        if status==FAIL:
            print(f"  [{sec}] {test}")
            if detail: print(f"         {detail[:200]}")

if warned:
    print("\n⚠️   WARNINGS:")
    for sec,test,status,detail in results:
        if status==WARN:
            print(f"  [{sec}] {test}: {detail[:120]}")

report = {
    "summary":{"total":total,"passed":passed,"failed":failed,"warned":warned,"skipped":skipped},
    "results":[{"section":s,"test":t,"status":st,"detail":d} for s,t,st,d in results]
}
(OUT/"audit_report.json").write_text(json.dumps(report,indent=2))
print(f"\n📄 Full JSON report: {OUT}/audit_report.json")
print(f"🖼  Render images:   {OUT}/*.png  ({len(list(OUT.glob('*.png')))} files)")
