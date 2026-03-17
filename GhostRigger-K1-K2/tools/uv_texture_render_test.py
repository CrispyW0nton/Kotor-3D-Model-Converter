#!/usr/bin/env python3
"""
UV/Texture Rendering Diagnostic Tool
=====================================
Tests the full texture + UV pipeline on a set of models.
For each model it:
  1. Parses the MDL/MDX
  2. Audits all UV ranges (good / problematic nodes)
  3. Renders a textured view + UV layout overlay
  4. Measures render quality (black-pixel %, UV coverage)
  5. Writes a detailed per-model JSON report + composite PNG

Apply lessons learned from the lava_trap exercise:
  - Texture name must match the .tga file (case-insensitive search)
  - MDX vertex stride and UV offset must be parsed correctly
  - Tiling meshes (UV span > 1.5) need tiled texture path
  - Seam-crossing faces (UV span < 1, straddles 0/1 boundary) need seam fix
  - V-axis must be flipped: KotOR V=0 = bottom, PIL row=0 = top
"""

import sys, os, json, math
from pathlib import Path
import struct

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL = True
except ImportError:
    print("Pillow missing — install with: pip install Pillow")
    sys.exit(1)

import numpy as np

from src.core.mdl_parser import MDLBinaryParser
from src.gui.viewport import TextureCache, _paste_textured_triangle

ROOT   = Path(__file__).parent.parent
OUT    = ROOT / 'render_test_output' / 'uv_texture_workflow'
OUT.mkdir(parents=True, exist_ok=True)

# ── Colour helpers ────────────────────────────────────────────────────────────

def _clamp(v, lo, hi):  return max(lo, min(hi, v))
def _norm3(v):
    l = math.sqrt(v[0]**2+v[1]**2+v[2]**2)
    return (v[0]/l, v[1]/l, v[2]/l) if l > 1e-9 else (0, 1, 0)
def _dot3(a, b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def _cross3(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def _sub3(a, b):  return (a[0]-b[0], a[1]-b[1], a[2]-b[2])

# ── Camera / projection ────────────────────────────────────────────────────────

def _build_camera(az_deg, el_deg, dist, target=(0,0,0)):
    az = math.radians(az_deg); el = math.radians(el_deg)
    ce = math.cos(el)
    eye = (target[0]+dist*ce*math.cos(az),
           target[1]+dist*ce*math.sin(az),
           target[2]+dist*math.sin(el))
    fwd   = _norm3(_sub3(target, eye))
    world_up = (0, 0, 1)
    right = _norm3(_cross3(fwd, world_up))
    if _dot3(right, right) < 1e-6:
        world_up = (0, 1, 0); right = _norm3(_cross3(fwd, world_up))
    up = _norm3(_cross3(right, fwd))
    return eye, fwd, right, up

def _project(pt, eye, fwd, right, up, W, H, fov=45):
    ev    = _sub3(pt, eye)
    depth = _dot3(ev, fwd)
    if depth < 0.01: return None
    sx = _dot3(ev, right)/depth
    sy = _dot3(ev, up)/depth
    f  = 1.0 / math.tan(math.radians(fov)*0.5)
    px = int(W/2 + sx*f*H/2)
    py = int(H/2 - sy*f*H/2)
    return px, py, depth

# ── UV audit ─────────────────────────────────────────────────────────────────

def audit_uvs(model):
    """Analyse UV ranges across all mesh nodes.  Returns summary dict."""
    good = []
    tiling = []
    seam_issues = []
    missing_tex = []
    total_faces = 0
    total_verts = 0

    for node in model.all_nodes():
        if not (hasattr(node, 'uvs') and node.uvs):
            continue
        uvs = node.uvs
        total_verts += len(uvs)
        if hasattr(node, 'faces') and node.faces:
            total_faces += len(node.faces)

        us = [uv[0] for uv in uvs]
        vs = [uv[1] for uv in uvs]
        min_u, max_u = min(us), max(us)
        min_v, max_v = min(vs), max(vs)
        u_span = max_u - min_u
        v_span = max_v - min_v
        tex = (getattr(node, 'texture_names', None) or [''])[0]

        entry = {
            'name': node.name,
            'verts': len(uvs),
            'faces': len(node.faces) if hasattr(node,'faces') and node.faces else 0,
            'tex': tex,
            'u_range': [round(min_u,4), round(max_u,4)],
            'v_range': [round(min_v,4), round(max_v,4)],
            'u_span':  round(u_span,4),
            'v_span':  round(v_span,4),
        }
        if not tex:
            missing_tex.append(entry)
        if u_span > 1.5 or v_span > 1.5:
            entry['issue'] = 'tiling'
            tiling.append(entry)
        elif (min_u < -0.01 or max_u > 1.01 or min_v < -0.01 or max_v > 1.01):
            entry['issue'] = 'seam_shift'
            seam_issues.append(entry)
        else:
            entry['issue'] = 'ok'
            good.append(entry)

    return {
        'total_mesh_nodes': len(good)+len(tiling)+len(seam_issues),
        'total_verts': total_verts,
        'total_faces': total_faces,
        'good': good,
        'tiling': tiling,
        'seam_shift': seam_issues,
        'missing_tex': missing_tex,
    }

# ── Simple UV layout renderer ──────────────────────────────────────────────────

def render_uv_layout(model, W=512, H=512):
    """Draw UV island layout diagram (all UVs unwrapped in [0,1] box)."""
    img  = Image.new('RGB', (W, H), (15, 15, 30))
    draw = ImageDraw.Draw(img)

    # Grid lines at [0,1]
    draw.rectangle([0, 0, W-1, H-1], outline=(60, 60, 80))
    draw.line([(W//2, 0),(W//2, H)], fill=(40,40,60))
    draw.line([(0, H//2),(W, H//2)], fill=(40,40,60))

    colours = [(255,100,100), (100,255,100), (100,100,255),
               (255,255,100), (255,100,255), (100,255,255),
               (255,180,80),  (180,80,255),  (80,255,180)]
    ci = 0

    for node in model.all_nodes():
        if not (hasattr(node, 'uvs') and node.uvs and
                hasattr(node, 'faces') and node.faces):
            continue
        uvs = node.uvs
        col = colours[ci % len(colours)]; ci += 1

        # Wrap UVs to [0,1] for display (frac)
        for face in node.faces:
            if len(face) < 3: continue
            pts = []
            for vi in face[:3]:
                if vi >= len(uvs): continue
                u, v = uvs[vi]
                # frac wrap
                u = u - math.floor(u)
                v = v - math.floor(v)
                # V-flip for display (KotOR V=0 = bottom)
                px = int(u * (W-1))
                py = int((1.0-v) * (H-1))
                pts.append((px, py))
            if len(pts) == 3:
                draw.polygon(pts, outline=col)

    return img

# ── Flat-shaded textured renderer ─────────────────────────────────────────────

def _face_normal(verts, face):
    if len(face) < 3: return (0, 0, 1)
    v0 = verts[face[0]]; v1 = verts[face[1]]; v2 = verts[face[2]]
    e1 = _sub3(v1, v0); e2 = _sub3(v2, v0)
    n  = _cross3(e1, e2)
    return _norm3(n)

def _paste_tri_textured(img_rgba, tex_rgba, sp0, sp1, sp2,
                         uv0, uv1, uv2, W, H, shade=1.0):
    """Minimal UV-mapped triangle raster using PIL AFFINE."""
    from PIL import Image as _Img
    sx0,sy0 = int(sp0[0]),int(sp0[1])
    sx1,sy1 = int(sp1[0]),int(sp1[1])
    sx2,sy2 = int(sp2[0]),int(sp2[1])

    bx0 = max(0, min(sx0,sx1,sx2)); by0 = max(0, min(sy0,sy1,sy2))
    bx1 = min(W-1, max(sx0,sx1,sx2)); by1 = min(H-1, max(sy0,sy1,sy2))
    bw = bx1-bx0+1; bh = by1-by0+1
    if bw <= 0 or bh <= 0: return

    tw, th = tex_rgba.size
    rx0,ry0 = sx0-bx0, sy0-by0
    rx1,ry1 = sx1-bx0, sy1-by0
    rx2,ry2 = sx2-bx0, sy2-by0

    # V-flip (KotOR V=0=bottom → PIL row=0=top)
    tu0 = uv0[0]*tw;  tv0 = (1.0-uv0[1])*th
    tu1 = uv1[0]*tw;  tv1 = (1.0-uv1[1])*th
    tu2 = uv2[0]*tw;  tv2 = (1.0-uv2[1])*th

    # Seam-crossing fix (small span straddles boundary)
    def _uwrap(ref, v):
        diff = v - ref
        if diff >  0.5: return v - 1.0
        if diff < -0.5: return v + 1.0
        return v

    u0r,v0r = uv0
    u1r = _uwrap(u0r, uv1[0]); v1r = _uwrap(v0r, uv1[1])
    u2r = _uwrap(u0r, uv2[0]); v2r = _uwrap(v0r, uv2[1])

    # Centroid shift for out-of-range small-span faces
    u_span = max(u0r,u1r,u2r)-min(u0r,u1r,u2r)
    v_span = max(v0r,v1r,v2r)-min(v0r,v1r,v2r)

    if u_span < 1.5 and v_span < 1.5:
        uc = (u0r+u1r+u2r)/3.0; vc = (v0r+v1r+v2r)/3.0
        us = int(math.floor(uc)); vs = int(math.floor(vc))
        u0r-=us; u1r-=us; u2r-=us
        v0r-=vs; v1r-=vs; v2r-=vs
        tu0,tv0 = u0r*tw, (1.0-v0r)*th
        tu1,tv1 = u1r*tw, (1.0-v1r)*th
        tu2,tv2 = u2r*tw, (1.0-v2r)*th
    else:
        # Tiling: build a small tiled texture
        u_min = min(u0r,u1r,u2r); u_max = max(u0r,u1r,u2r)
        v_min = min(v0r,v1r,v2r); v_max = max(v0r,v1r,v2r)
        u_fl  = int(math.floor(u_min)); v_fl = int(math.floor(v_min))
        tu_n  = max(1, int(math.ceil(u_max))-u_fl)
        tv_n  = max(1, int(math.ceil(v_max))-v_fl)
        tu_n  = min(tu_n, 8); tv_n = min(tv_n, 8)
        src_w = max(1,min(tw,128)); src_h = max(1,min(th,128))
        thumb = tex_rgba.resize((src_w,src_h), _Img.BOX if hasattr(_Img,'BOX') else _Img.NEAREST)
        tiled = _Img.new('RGBA', (src_w*tu_n, src_h*tv_n))
        for ti in range(tu_n):
            for tj in range(tv_n):
                tiled.paste(thumb, (ti*src_w, tj*src_h))
        tex_rgba = tiled; tw,th = tiled.size
        u0r-=u_fl; u1r-=u_fl; u2r-=u_fl
        v0r-=v_fl; v1r-=v_fl; v2r-=v_fl
        tu0,tv0 = u0r*tw, (tv_n-v0r)*src_h
        tu1,tv1 = u1r*tw, (tv_n-v1r)*src_h
        tu2,tv2 = u2r*tw, (tv_n-v2r)*src_h

    # Solve affine system  src = A * dst + c
    det = (rx0*(ry1-ry2) + rx1*(ry2-ry0) + rx2*(ry0-ry1))
    if abs(det) < 1e-6: return
    a = ((tu0*(ry1-ry2)+tu1*(ry2-ry0)+tu2*(ry0-ry1))/det)
    b = ((tu0*(rx2-rx1)+tu1*(rx0-rx2)+tu2*(rx1-rx0))/det)
    c = ((tu0*(rx1*ry2-rx2*ry1)+tu1*(rx2*ry0-rx0*ry2)+tu2*(rx0*ry1-rx1*ry0))/det)
    d = ((tv0*(ry1-ry2)+tv1*(ry2-ry0)+tv2*(ry0-ry1))/det)
    e = ((tv0*(rx2-rx1)+tv1*(rx0-rx2)+tv2*(rx1-rx0))/det)
    f = ((tv0*(rx1*ry2-rx2*ry1)+tv1*(rx2*ry0-rx0*ry2)+tv2*(rx0*ry1-rx1*ry0))/det)

    patch = tex_rgba.transform(
        (bw, bh), _Img.AFFINE, (a, b, c, d, e, f),
        resample=_Img.BILINEAR, fillcolor=(0, 0, 0, 0))

    # Apply shading
    if shade < 0.999:
        sv = int(_clamp(shade*255, 0, 255))
        r,g,b,a_ch = patch.split()
        r = r.point(lambda p: int(p*shade))
        g = g.point(lambda p: int(p*shade))
        b = b.point(lambda p: int(p*shade))
        patch = Image.merge('RGBA', (r,g,b,a_ch))

    mask = Image.new('1', (bw, bh), 0)
    ImageDraw.Draw(mask).polygon(
        [(rx0,ry0),(rx1,ry1),(rx2,ry2)], fill=1, outline=1)

    img_rgba.paste(patch, (bx0, by0), mask)


def render_textured(model, tc: TextureCache,
                    W=512, H=512, az_deg=-45, el_deg=20):
    """Render model with textures.  Returns PIL Image (RGB)."""
    canvas = Image.new('RGBA', (W, H), (18, 18, 40, 255))

    # Collect geometry
    all_verts = []
    for node in model.all_nodes():
        if hasattr(node, 'vertices') and node.vertices:
            all_verts.extend(node.vertices)
    if not all_verts:
        img = Image.new('RGB', (W, H), (18, 18, 40))
        ImageDraw.Draw(img).text((10, H//2), 'No geometry', fill=(255,80,80))
        return img

    # Auto camera
    xs = [v[0] for v in all_verts]; ys = [v[1] for v in all_verts]; zs = [v[2] for v in all_verts]
    cx = (min(xs)+max(xs))/2; cy = (min(ys)+max(ys))/2; cz = (min(zs)+max(zs))/2
    radius = max(0.1, max(
        max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)) * 0.6)
    dist = radius * 2.5 + 0.5
    cam = _build_camera(az_deg, el_deg, dist, (cx, cy, cz))
    eye, fwd, right, up = cam

    light = _norm3((0.4, 0.6, 1.0))

    tris = []  # (depth, pts, tex, uv0,uv1,uv2, shade, alpha)
    for node in model.all_nodes():
        if not (hasattr(node, 'vertices') and node.vertices and
                hasattr(node, 'faces') and node.faces and
                hasattr(node, 'uvs') and node.uvs):
            continue

        verts = node.vertices
        uvs   = node.uvs
        faces = node.faces
        tex_name = (getattr(node, 'texture_names', None) or [''])[0]
        tex_img  = None
        if tex_name:
            tex_img = tc.get(tex_name)

        for face in faces:
            if len(face) < 3: continue
            vi0, vi1, vi2 = face[0], face[1], face[2]
            if max(vi0, vi1, vi2) >= len(verts): continue

            v0, v1, v2 = verts[vi0], verts[vi1], verts[vi2]
            p0 = _project(v0, eye, fwd, right, up, W, H)
            p1 = _project(v1, eye, fwd, right, up, W, H)
            p2 = _project(v2, eye, fwd, right, up, W, H)
            if p0 is None or p1 is None or p2 is None: continue

            depth = (p0[2]+p1[2]+p2[2]) / 3.0

            uv0 = uvs[vi0] if vi0 < len(uvs) else (0.5,0.5)
            uv1 = uvs[vi1] if vi1 < len(uvs) else (0.5,0.5)
            uv2 = uvs[vi2] if vi2 < len(uvs) else (0.5,0.5)

            n = _face_normal(verts, face)
            ndotl = max(0.0, _dot3(n, light))
            shade = 0.25 + 0.75 * ndotl

            tris.append((depth, (p0[:2],p1[:2],p2[:2]),
                         tex_img, uv0, uv1, uv2, shade))

    tris.sort(key=lambda t: -t[0])  # back-to-front

    for depth, pts, tex_img, uv0, uv1, uv2, shade in tris:
        sp0, sp1, sp2 = pts
        if tex_img is not None:
            tex_rgba = tex_img.convert('RGBA')
            _paste_tri_textured(canvas, tex_rgba,
                                sp0, sp1, sp2,
                                uv0, uv1, uv2,
                                W, H, shade)
        else:
            draw = ImageDraw.Draw(canvas)
            sv = int(_clamp(shade*180, 0, 255))
            pts_flat = [(int(sp0[0]),int(sp0[1])),
                        (int(sp1[0]),int(sp1[1])),
                        (int(sp2[0]),int(sp2[1]))]
            draw.polygon(pts_flat, fill=(sv, sv//2, sv//3, 255))

    return canvas.convert('RGB')


def render_viewport_pipeline(model, tc: TextureCache,
                              W=512, H=512, az_deg=-45, el_deg=20):
    """
    Render model using the ACTUAL viewport _paste_textured_triangle pipeline
    (seam-fix, tiling, centroid-shift, V-flip all included).
    This matches what the GhostRigger viewer displays exactly.
    Returns PIL Image (RGB).
    """
    canvas = Image.new('RGBA', (W, H), (18, 18, 40, 255))

    # Collect geometry for camera auto-fit
    all_verts = []
    for node in model.all_nodes():
        if hasattr(node, 'vertices') and node.vertices:
            all_verts.extend(node.vertices)
    if not all_verts:
        img = Image.new('RGB', (W, H), (18, 18, 40))
        ImageDraw.Draw(img).text((10, H//2), 'No geometry', fill=(255,80,80))
        return img

    xs = [v[0] for v in all_verts]; ys = [v[1] for v in all_verts]; zs = [v[2] for v in all_verts]
    cx = (min(xs)+max(xs))/2; cy = (min(ys)+max(ys))/2; cz = (min(zs)+max(zs))/2
    dist = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)) * 1.5 + 0.5
    cam = _build_camera(az_deg, el_deg, dist, (cx, cy, cz))
    eye, fwd, right, up = cam
    light = _norm3((0.4, 0.6, 1.0))

    tris = []
    for node in model.all_nodes():
        if not (hasattr(node, 'vertices') and node.vertices and
                hasattr(node, 'faces') and node.faces and
                hasattr(node, 'uvs') and node.uvs):
            continue
        tex_name = (getattr(node, 'texture_names', None) or [''])[0]
        # Skip null-texture deform helpers (shadow geometry)
        if not tex_name or tex_name.lower() == 'null':
            continue
        tex_img = tc.get(tex_name)
        if tex_img is None:
            continue

        verts = node.vertices; uvs = node.uvs; faces = node.faces

        for face in faces:
            if len(face) < 3: continue
            vi0, vi1, vi2 = face[0], face[1], face[2]
            if max(vi0, vi1, vi2) >= len(verts): continue
            p0 = _project(verts[vi0], eye, fwd, right, up, W, H)
            p1 = _project(verts[vi1], eye, fwd, right, up, W, H)
            p2 = _project(verts[vi2], eye, fwd, right, up, W, H)
            if p0 is None or p1 is None or p2 is None: continue
            depth = (p0[2]+p1[2]+p2[2]) / 3.0
            uv0 = uvs[vi0] if vi0 < len(uvs) else (0.5,0.5)
            uv1 = uvs[vi1] if vi1 < len(uvs) else (0.5,0.5)
            uv2 = uvs[vi2] if vi2 < len(uvs) else (0.5,0.5)
            n = _face_normal(verts, face)
            shade = max(0.25, 0.25 + 0.75 * max(0.0, _dot3(n, light)))
            sv = int(_clamp(shade * 255, 0, 255))
            tris.append((depth, (p0[:2],p1[:2],p2[:2]),
                         tex_img, uv0, uv1, uv2, (sv,sv,sv)))

    tris.sort(key=lambda t: -t[0])

    for depth, pts, tex_img, uv0, uv1, uv2, shade_col in tris:
        sp0, sp1, sp2 = pts
        try:
            _paste_textured_triangle(
                canvas, tex_img.convert('RGBA'),
                sp0, sp1, sp2, uv0, uv1, uv2,
                W, H, shade_col,
                sel_brightness=0, node_alpha=1.0,
                is_additive=False,
                skip_seam_u=False, skip_seam_v=False,
                clamp_s=False, clamp_t=False)
        except Exception:
            pass  # Skip any problematic triangle

    return canvas.convert('RGB')


# ── Quality metrics ────────────────────────────────────────────────────────────

def measure_quality(img):
    arr = np.array(img.convert('RGB'))  # ensure 3-channel HxWx3
    total = arr.shape[0] * arr.shape[1]
    black = int(np.all(arr < 12, axis=2).sum())
    # Background colour is (18,18,40) — not pure black
    bg_mask = (arr[:,:,0]<25) & (arr[:,:,1]<25) & (arr[:,:,2]<50)
    bg = int(bg_mask.sum())
    model_px = total - bg
    return {
        'total_px': int(total),
        'bg_px': int(bg),
        'model_px': int(model_px),
        'pure_black_px': int(black),
        'black_pct': round(100*black/total, 2),
    }


# ── Composite layout ──────────────────────────────────────────────────────────

def make_composite(model_name, render_img, uv_img, audit, quality):
    """Build a 3-panel composite: render | uv layout | stats."""
    W = 512; H = 512
    comp = Image.new('RGB', (W*2, H+120), (10, 10, 25))
    comp.paste(render_img.resize((W,H)), (0, 0))
    comp.paste(uv_img.resize((W,H)),    (W, 0))

    draw = ImageDraw.Draw(comp)
    y = H + 6
    draw.text((8,y), f"Model: {model_name}", fill=(220,220,220)); y += 16
    draw.text((8,y), f"Mesh nodes: {audit['total_mesh_nodes']}  "
                     f"Verts: {audit['total_verts']}  "
                     f"Faces: {audit['total_faces']}", fill=(180,180,180)); y += 16
    draw.text((8,y), f"UV: {len(audit['good'])} ok | "
                     f"{len(audit['tiling'])} tiling | "
                     f"{len(audit['seam_shift'])} seam-shift | "
                     f"{len(audit['missing_tex'])} no-tex",
              fill=(100,220,100)); y += 16
    draw.text((8,y), f"Black pixels: {quality['black_pct']}%  "
                     f"Model pixels: {quality['model_px']}", fill=(180,180,100))

    # UV problem list (up to 3 lines)
    y = H + 6
    issues = audit['tiling'][:3] + audit['seam_shift'][:2]
    for iss in issues[:4]:
        txt = (f"  {iss['name']}  U={iss['u_range']}  V={iss['v_range']}  "
               f"[{iss.get('issue','?')}]")
        draw.text((W+4, y), txt, fill=(255,160,80)); y += 14

    return comp


# ── Main ───────────────────────────────────────────────────────────────────────

TEST_MODELS = [
    ('test_assets/honorguard/N_sithpraet.mdl',
     'test_assets/honorguard/N_sithpraet.mdx',
     'test_assets/honorguard'),
    ('test_assets/N_sithpraet.mdl',
     'test_assets/N_sithpraet.mdx',
     'test_assets'),
]

# Also pick up K1 game models if available
K1_MODELS = ROOT / 'game_data' / 'k1_extracted' / 'models'
K1_TEX    = ROOT / 'game_data' / 'k1_extracted' / 'textures'
if K1_MODELS.exists():
    for p in sorted(K1_MODELS.glob('c_*.mdl'))[:8]:
        TEST_MODELS.append((str(p), str(p.with_suffix('.mdx')), str(K1_TEX)))

all_reports = []
composites  = []

for mdl_path, mdx_path, tex_dir in TEST_MODELS:
    mdl_p = ROOT / mdl_path if not os.path.isabs(mdl_path) else Path(mdl_path)
    mdx_p = ROOT / mdx_path if not os.path.isabs(mdx_path) else Path(mdx_path)
    if not mdl_p.exists():
        print(f"  skip (not found): {mdl_p.name}")
        continue

    name = mdl_p.stem
    print(f"\n── {name} ──────────────────────")

    try:
        model = MDLBinaryParser.parse_files(str(mdl_p),
                                             str(mdx_p) if mdx_p.exists() else '')
    except Exception as e:
        print(f"  PARSE ERROR: {e}"); continue

    # UV audit
    audit = audit_uvs(model)
    print(f"  Nodes: {audit['total_mesh_nodes']}  "
          f"Verts: {audit['total_verts']}  Faces: {audit['total_faces']}")
    print(f"  UV: {len(audit['good'])} ok | {len(audit['tiling'])} tiling | "
          f"{len(audit['seam_shift'])} seam-shift | {len(audit['missing_tex'])} no-tex")
    for t in audit['tiling'][:3]:
        print(f"    [tiling] {t['name']} U={t['u_range']} V={t['v_range']}")
    for t in audit['seam_shift'][:3]:
        print(f"    [seam]   {t['name']} U={t['u_range']} V={t['v_range']}")

    # Texture cache
    tc = TextureCache()
    tex_d = ROOT / tex_dir if not os.path.isabs(tex_dir) else Path(tex_dir)
    tc.set_search_dirs([str(tex_d)])

    # Render using simple affine path
    try:
        render_img = render_textured(model, tc, W=512, H=512, az_deg=-45, el_deg=20)
    except Exception as e:
        import traceback; traceback.print_exc()
        render_img = Image.new('RGB', (512,512), (40,10,10))

    # Render using full viewport pipeline (seam-fix, tiling, centroid-shift)
    try:
        vp_img = render_viewport_pipeline(model, tc, W=512, H=512, az_deg=-45, el_deg=20)
    except Exception as e:
        vp_img = render_img  # fallback to simple render

    uv_img = render_uv_layout(model, W=512, H=512)

    quality = measure_quality(render_img)
    vp_quality = measure_quality(vp_img)
    print(f"  Quality simple: black={quality['black_pct']}%  viewport: black={vp_quality['black_pct']}%  model_px={quality['model_px']}")

    # Save individual outputs
    render_img.save(OUT / f'{name}_render.png')
    vp_img.save(OUT / f'{name}_viewport.png')
    uv_img.save(OUT / f'{name}_uv_layout.png')

    # Composite: viewport render | UV layout
    comp = make_composite(name, vp_img, uv_img, audit, vp_quality)
    comp.save(OUT / f'{name}_composite.png')
    composites.append(comp)
    print(f"  Saved: {name}_viewport.png  {name}_uv_layout.png  {name}_composite.png")

    report = {
        'model': name,
        'path': str(mdl_p),
        'classification': model.classification,
        'game_version': str(model.game_version),
        'audit': audit,
        'quality_simple': quality,
        'quality_viewport': vp_quality,
    }
    all_reports.append(report)
    with open(OUT / f'{name}_report.json', 'w') as f:
        json.dump(report, f, indent=2)

# Build mega-composite
if composites:
    cols = min(2, len(composites))
    rows = (len(composites)+cols-1)//cols
    cw,ch = composites[0].size
    mega = Image.new('RGB', (cw*cols, ch*rows), (5,5,15))
    for i,c in enumerate(composites):
        r,co = divmod(i, cols)
        mega.paste(c, (co*cw, r*ch))
    mega.save(OUT / '_all_composite.png')
    print(f"\nMega composite saved: {OUT / '_all_composite.png'}")

# Summary
print("\n══ SUMMARY ══════════════════")
for rpt in all_reports:
    simple_b  = rpt.get('quality_simple', {}).get('black_pct', -1)
    vp_b      = rpt.get('quality_viewport', rpt.get('quality', {})).get('black_pct', -1)
    print(f"  {rpt['model']:30s}  "
          f"simple_black={simple_b:5.1f}%  vp_black={vp_b:5.1f}%  "
          f"tiling={len(rpt['audit']['tiling'])}  "
          f"seam={len(rpt['audit']['seam_shift'])}")

with open(OUT / '_summary.json', 'w') as f:
    json.dump(all_reports, f, indent=2)
print(f"\nAll outputs in: {OUT}")
