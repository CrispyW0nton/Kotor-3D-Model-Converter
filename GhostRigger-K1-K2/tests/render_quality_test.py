#!/usr/bin/env python3
"""
render_quality_test.py — Headless texture-quality render test.

Renders KotOR models using the FrameRenderer pipeline and measures:
  - Black pixel percentage (lower = better texture coverage)
  - Textured pixel percentage  
  - UV coverage
  
Saves PNG renders to render_test_output_quality/
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw
import numpy as np

from src.core.mdl_parser import MDLBinaryParser
from src.gui.viewport import (
    FrameRenderer, TextureCache,
    _paste_textured_triangle,
    _vflip_nontiled,
)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'render_test_output_quality')
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _project_verts(verts, W=512, H=512, scale=None, cx=0, cy=0, cz=0):
    """Simple orthographic top/front projection.  Returns list of (sx, sy)."""
    if not verts:
        return []
    # Centre + scale
    xs = [v[0] - cx for v in verts]
    zs = [v[2] - cz for v in verts]
    if scale is None:
        rng = max(max(abs(x) for x in xs), max(abs(z) for z in zs), 0.001)
        scale = (min(W, H) * 0.42) / rng
    return [(int(W/2 + x*scale), int(H/2 - z*scale)) for x, z in zip(xs, zs)]


def _project_front(verts, W=512, H=512, scale=None, cx=0, cy=0, cz=0):
    """Front-view orthographic projection (X,Y axes)."""
    if not verts:
        return []
    xs = [v[0] - cx for v in verts]
    ys = [v[1] - cy for v in verts]
    if scale is None:
        rng = max(max(abs(x) for x in xs), max(abs(y) for y in ys), 0.001)
        scale = (min(W, H) * 0.42) / rng
    return [(int(W/2 + x*scale), int(H/2 - y*scale)) for x, y in zip(xs, ys)]


def render_model_textured(mdl_path, mdx_path, tex_dirs, output_path,
                          W=512, H=512, view='front'):
    """Render a model with textures using the UV pipeline. Return black pixel %."""
    m = MDLBinaryParser.parse_files(mdl_path, mdx_path)
    
    tc = TextureCache()
    tc.set_search_dirs(tex_dirs)

    canvas = Image.new('RGBA', (W, H), (30, 30, 30, 255))

    mesh_nodes = m.mesh_nodes()
    
    # Collect bounding box across all renderable nodes
    all_verts = []
    for node in mesh_nodes:
        tex = getattr(node, 'texture', '') or ''
        if not tex or tex.upper() == 'NULL':
            continue
        uvs = getattr(node, 'uvs', [])
        if not uvs:
            continue
        verts = getattr(node, 'vertices', [])
        # Apply node position
        pos = getattr(node, 'position', (0,0,0))
        for v in verts:
            all_verts.append((v[0]+pos[0], v[1]+pos[1], v[2]+pos[2]))

    if not all_verts:
        print(f"  [WARN] No renderable verts in {os.path.basename(mdl_path)}")
        return 100.0

    cx = sum(v[0] for v in all_verts) / len(all_verts)
    cy = sum(v[1] for v in all_verts) / len(all_verts)
    cz = sum(v[2] for v in all_verts) / len(all_verts)
    
    # Compute global scale
    if view == 'front':
        xs = [v[0]-cx for v in all_verts]; ys = [v[1]-cy for v in all_verts]
        rng = max(max(abs(x) for x in xs) if xs else 0.001,
                  max(abs(y) for y in ys) if ys else 0.001, 0.001)
    else:
        xs = [v[0]-cx for v in all_verts]; zs = [v[2]-cz for v in all_verts]
        rng = max(max(abs(x) for x in xs) if xs else 0.001,
                  max(abs(z) for z in zs) if zs else 0.001, 0.001)
    scale = (min(W, H) * 0.42) / rng

    textured_tris = 0
    total_tris = 0

    for node in mesh_nodes:
        tex_name = getattr(node, 'texture', '') or ''
        if not tex_name or tex_name.upper() == 'NULL':
            continue
        uvs = getattr(node, 'uvs', [])
        verts = getattr(node, 'vertices', [])
        faces = getattr(node, 'faces', [])
        if not uvs or not verts or not faces:
            continue

        # Check extreme UV (deform helper)
        has_extreme = any(abs(u)>3 or abs(v)>3 for u,v in uvs[:20])
        if has_extreme:
            continue

        tex_img = tc.get(tex_name)
        if tex_img is None:
            # Try lower-case
            tex_img = tc.get(tex_name.lower())

        pos = getattr(node, 'position', (0,0,0))

        for fi, face in enumerate(faces):
            if len(face) < 3:
                continue
            i0, i1, i2 = face[0], face[1], face[2]
            if i0 >= len(verts) or i1 >= len(verts) or i2 >= len(verts):
                continue
            if i0 >= len(uvs) or i1 >= len(uvs) or i2 >= len(uvs):
                continue

            v0 = (verts[i0][0]+pos[0], verts[i0][1]+pos[1], verts[i0][2]+pos[2])
            v1 = (verts[i1][0]+pos[0], verts[i1][1]+pos[1], verts[i1][2]+pos[2])
            v2 = (verts[i2][0]+pos[0], verts[i2][1]+pos[1], verts[i2][2]+pos[2])

            if view == 'front':
                sp0 = (int(W/2 + (v0[0]-cx)*scale), int(H/2 - (v0[1]-cy)*scale))
                sp1 = (int(W/2 + (v1[0]-cx)*scale), int(H/2 - (v1[1]-cy)*scale))
                sp2 = (int(W/2 + (v2[0]-cx)*scale), int(H/2 - (v2[1]-cy)*scale))
            else:
                sp0 = (int(W/2 + (v0[0]-cx)*scale), int(H/2 - (v0[2]-cz)*scale))
                sp1 = (int(W/2 + (v1[0]-cx)*scale), int(H/2 - (v1[2]-cz)*scale))
                sp2 = (int(W/2 + (v2[0]-cx)*scale), int(H/2 - (v2[2]-cz)*scale))

            uv0 = uvs[i0]
            uv1 = uvs[i1]
            uv2 = uvs[i2]
            
            total_tris += 1
            if tex_img is not None:
                _paste_textured_triangle(
                    canvas, tex_img,
                    sp0, sp1, sp2,
                    uv0, uv1, uv2,
                    W, H,
                    shade_color=(255, 255, 255),
                )
                textured_tris += 1
            else:
                # Flat shade fallback
                draw = ImageDraw.Draw(canvas)
                draw.polygon([sp0, sp1, sp2], fill=(180, 80, 80, 200))

    canvas.save(output_path)
    
    # Measure quality: count non-background pixels
    arr = np.array(canvas)
    bg = (30, 30, 30)
    is_bg = ((arr[:,:,0] == bg[0]) & (arr[:,:,1] == bg[1]) & (arr[:,:,2] == bg[2]))
    total_px = W * H
    bg_px = int(np.sum(is_bg))
    painted_px = total_px - bg_px
    
    # Of painted pixels, count dark (black-ish) ones
    painted_mask = ~is_bg
    dark = (arr[:,:,0] < 15) & (arr[:,:,1] < 15) & (arr[:,:,2] < 15) & painted_mask
    dark_px = int(np.sum(dark))
    dark_pct = (dark_px / max(painted_px, 1)) * 100
    
    print(f"  {os.path.basename(mdl_path):25s}  tris={total_tris:4d}  textured={textured_tris:4d}"
          f"  painted_px={painted_px:6d}  dark%={dark_pct:.1f}%"
          f"  tex_miss={total_tris - textured_tris}")
    return dark_pct


if __name__ == '__main__':
    print("=== Render Quality Test ===\n")
    
    test_assets = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               'test_assets')
    honorguard = os.path.join(test_assets, 'honorguard')
    
    tests = [
        ('N_sithpraet.mdl', 'N_sithpraet.mdx',
         [test_assets], 'sithpraet_front.png', 'front'),
        ('honorguard/N_sithpraet.mdl', 'honorguard/N_sithpraet.mdx',
         [honorguard], 'honorguard_front.png', 'front'),
    ]
    
    for mdl_rel, mdx_rel, tex_dirs, out_name, view in tests:
        mdl_path = os.path.join(test_assets, mdl_rel)
        mdx_path = os.path.join(test_assets, mdx_rel)
        if not os.path.exists(mdl_path):
            print(f"  SKIP: {mdl_path} not found")
            continue
        out_path = os.path.join(OUTPUT_DIR, out_name)
        render_model_textured(mdl_path, mdx_path, tex_dirs, out_path, view=view)
        print(f"  → Saved: {out_path}")
    
    # Also render all models in game_data if available
    k1_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'game_data', 'k1_extracted')
    if os.path.isdir(k1_dir):
        import glob
        mdl_files = glob.glob(os.path.join(k1_dir, 'models', 'c_*.mdl'))[:8]
        tex_dirs = [os.path.join(k1_dir, 'textures_tpa'),
                    os.path.join(k1_dir, 'texturepacks')]
        for mdl_path in mdl_files:
            mdx_path = mdl_path.replace('.mdl', '.mdx')
            if not os.path.exists(mdx_path):
                continue
            out_name = os.path.basename(mdl_path).replace('.mdl', '_render.png')
            out_path = os.path.join(OUTPUT_DIR, out_name)
            render_model_textured(mdl_path, mdx_path, tex_dirs, out_path)
            print(f"  → Saved: {out_path}")

    print("\nDone.")
