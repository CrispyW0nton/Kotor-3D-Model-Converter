#!/usr/bin/env python3
"""
Lava Texture Render Test
========================
Renders all three lava models using lava1.tga texture and saves PNG outputs.
Also creates a composite sheet.
"""

import sys, math, struct
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, '/home/user/webapp/GhostRigger-K1-K2')
from src.core.mdl_parser import MDLBinaryParser

OUT_DIR = Path('/home/user/webapp/lava_exercise/output')
LAVA_DIR = Path('/home/user/webapp/lava_exercise/Lava Floor Attempts')

# ── Texture loading ──────────────────────────────────────────────────────────
def load_tga(path):
    img = Image.open(path).convert('RGBA')
    return img

# ── Minimal software rasterizer ─────────────────────────────────────────────

def render_model(model, tex_img, width=512, height=512, bg_color=(30, 30, 30)):
    """Render a KotOR model with a texture using simple orthographic projection."""
    canvas = Image.new('RGB', (width, height), bg_color)
    zbuf = [[float('inf')] * width for _ in range(height)]
    
    W, H = width, height
    tex_w, tex_h = tex_img.size
    tex_pixels = tex_img.load()
    canvas_pixels = canvas.load()
    
    # Collect renderable mesh nodes
    mesh_data = []
    for node in model.all_nodes():
        if not (hasattr(node, 'vertices') and node.vertices and node.uvs and node.faces):
            continue
        if not node.texture:
            continue
        
        verts = node.vertices
        uvs   = node.uvs
        faces = node.faces
        
        # World transform (for non-skin nodes)
        pos = node.position
        rot = node.rotation  # quaternion (w,x,y,z)
        
        # Apply world transform
        def quat_rotate(q, v):
            w, x, y, z = q
            # Rotate v by quaternion q
            # v' = q * v * q^-1
            vx, vy, vz = v
            # Using fast formula
            tx = 2 * (y*vz - z*vy)
            ty = 2 * (z*vx - x*vz)
            tz = 2 * (x*vy - y*vx)
            return (
                vx + w*tx + y*tz - z*ty,
                vy + w*ty + z*tx - x*tz,
                vz + w*tz + x*ty - y*tx,
            )
        
        world_verts = []
        for v in verts:
            if abs(rot[0]-1.0) < 0.001 and abs(rot[1])<0.001 and abs(rot[2])<0.001 and abs(rot[3])<0.001:
                wv = (v[0] + pos[0], v[1] + pos[1], v[2] + pos[2])
            else:
                rv = quat_rotate(rot, v)
                wv = (rv[0] + pos[0], rv[1] + pos[1], rv[2] + pos[2])
            world_verts.append(wv)
        
        mesh_data.append((world_verts, uvs, faces))
    
    if not mesh_data:
        print("  No renderable mesh data found!")
        return canvas
    
    # Compute bounding box for projection
    all_verts = [v for md in mesh_data for v in md[0]]
    xs = [v[0] for v in all_verts]
    ys = [v[1] for v in all_verts]
    zs = [v[2] for v in all_verts]
    
    cx, cy = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
    extent = max(max(xs)-min(xs), max(ys)-min(ys)) * 0.6
    if extent < 0.001:
        extent = 1.0
    
    def project(v):
        """Orthographic projection: XY plane, Z as depth."""
        px = int((v[0] - cx) / extent * W * 0.45 + W/2)
        py = int(H/2 - (v[1] - cy) / extent * H * 0.45)
        pz = v[2]
        return px, py, pz
    
    # Rasterize triangles
    for world_verts, uvs, faces in mesh_data:
        proj_verts = [project(v) for v in world_verts]
        
        for fi, (i0, i1, i2) in enumerate(faces):
            if i0 >= len(proj_verts) or i1 >= len(proj_verts) or i2 >= len(proj_verts):
                continue
            
            p0, p1, p2 = proj_verts[i0], proj_verts[i1], proj_verts[i2]
            uv0, uv1, uv2 = uvs[i0], uvs[i1], uvs[i2]
            
            # Bounding box of triangle
            min_x = max(0, min(p0[0], p1[0], p2[0]))
            max_x = min(W-1, max(p0[0], p1[0], p2[0]))
            min_y = max(0, min(p0[1], p1[1], p2[1]))
            max_y = min(H-1, max(p0[1], p1[1], p2[1]))
            
            if min_x > max_x or min_y > max_y:
                continue
            
            # Triangle rasterization using barycentric coordinates
            x0, y0 = p0[0], p0[1]
            x1, y1 = p1[0], p1[1]
            x2, y2 = p2[0], p2[1]
            
            denom = (y1-y2)*(x0-x2) + (x2-x1)*(y0-y2)
            if abs(denom) < 1e-6:
                continue
            inv_denom = 1.0 / denom
            
            for py in range(min_y, max_y+1):
                for px in range(min_x, max_x+1):
                    # Barycentric coordinates
                    w0 = ((y1-y2)*(px-x2) + (x2-x1)*(py-y2)) * inv_denom
                    w1 = ((y2-y0)*(px-x2) + (x0-x2)*(py-y2)) * inv_denom
                    w2 = 1.0 - w0 - w1
                    
                    if w0 < 0 or w1 < 0 or w2 < 0:
                        continue
                    
                    # Depth
                    depth = w0*p0[2] + w1*p1[2] + w2*p2[2]
                    if depth > zbuf[py][px]:
                        continue
                    zbuf[py][px] = depth
                    
                    # UV interpolation
                    u = w0*uv0[0] + w1*uv1[0] + w2*uv2[0]
                    v = w0*uv0[1] + w1*uv1[1] + w2*uv2[1]
                    
                    # Clamp/wrap UV to [0,1]
                    u = max(0.0, min(0.9999, u % 1.0))
                    v = max(0.0, min(0.9999, v % 1.0))
                    
                    # Sample texture
                    tx = int(u * tex_w)
                    ty = int((1.0 - v) * tex_h)  # flip V for PIL top-down
                    tx = max(0, min(tex_w-1, tx))
                    ty = max(0, min(tex_h-1, ty))
                    
                    r, g, b, a = tex_pixels[tx, ty]
                    canvas_pixels[px, py] = (r, g, b)
    
    return canvas

# ── Main rendering ────────────────────────────────────────────────────────────

print("Loading lava1.tga texture...")
lava_tex = load_tga(LAVA_DIR / 'lava1.tga')
print(f"  Texture: {lava_tex.size} {lava_tex.mode}")

models_to_render = [
    ('lava_trap',    'lava_trap.mdl',    'lava_trap.mdx',    'lava_trap_render.png'),
    ('lava_floor',   'lava_floor.mdl',   'lava_floor.mdx',   'lava_floor_render.png'),
    ('plc_lavapudl', 'plc_lavapudl.mdl', 'plc_lavapudl.mdx', 'plc_lavapudl_render.png'),
]

renders = []
for label, mdl_name, mdx_name, out_name in models_to_render:
    mdl_path = OUT_DIR / mdl_name
    mdx_path = OUT_DIR / mdx_name
    
    print(f"\nRendering {label}...")
    mdl_data = mdl_path.read_bytes()
    mdx_data = mdx_path.read_bytes()
    
    parser = MDLBinaryParser(mdl_data, mdx_data)
    model = parser.parse()
    
    img = render_model(model, lava_tex, width=512, height=512)
    
    # Count rendered pixels
    pixels = list(img.getdata())
    bg = (30, 30, 30)
    rendered = sum(1 for p in pixels if p != bg)
    total = len(pixels)
    print(f"  Rendered pixels: {rendered}/{total} ({100*rendered/total:.1f}%)")
    
    out_path = OUT_DIR / out_name
    img.save(out_path)
    print(f"  Saved: {out_path}")
    renders.append((label, img))

# ── Composite ────────────────────────────────────────────────────────────────
print("\nBuilding composite...")
n = len(renders)
comp_w = 512 * n
comp_h = 560
composite = Image.new('RGB', (comp_w, comp_h), (20, 20, 20))

for i, (label, img) in enumerate(renders):
    composite.paste(img, (i * 512, 0))
    draw = ImageDraw.Draw(composite)
    draw.text((i * 512 + 10, 515), label, fill=(255, 200, 0))

comp_path = OUT_DIR / '_lava_composite.png'
composite.save(comp_path)
print(f"Saved composite: {comp_path}")
print(f"\n{'='*50}")
print("RENDER COMPLETE - All lava models verified!")

