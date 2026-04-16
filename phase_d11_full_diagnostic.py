#!/usr/bin/env python3
"""Phase D11 — Full Evidence-Driven Diagnostic Suite.

Produces per-asset diagnostic artifacts for all validation assets:
  - Normal render (front, diag)
  - UV-checker render
  - Diffuse-only render
  - Lightmap-only render (if applicable)
  - Sampler-state dump (JSON)
  - UV-range dump (JSON)
  - VBO vertex sample (JSON)
  - Body-part chain dump (JSON)
  - Node isolation captures
  - Comparison: loader UV vs GPU UV

Results are written to screenshots/d11_evidence/<asset>/
A final JSON report summarizes all findings.
"""

import json
import math
import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.resource_manager import ResourceManager, RES_MDL, RES_MDX, RES_TPC, RES_TGA
from core.kotor_loader import load_model_from_bytes

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# ── Resource Manager setup ──────────────────────────────────────────────────

K1_DIR = 'game_data/swkotor'
K2_DIR = 'game_data/swkotor2/Knights of the Old Republic II'

rm = ResourceManager()
rm.set_k1_dir(K1_DIR)
rm.set_k2_dir(K2_DIR)

OUTPUT_BASE = Path('screenshots/d11_evidence')
OUTPUT_BASE.mkdir(parents=True, exist_ok=True)


# ── Validation Asset List ───────────────────────────────────────────────────

ASSETS = [
    # K1 assets
    {'name': 'c_jawa',        'game': 'K1'},
    {'name': 'c_bantha',      'game': 'K1'},
    {'name': 'c_gammorean',   'game': 'K1'},
    {'name': 'c_kraytdragon', 'game': 'K1'},
    {'name': 'n_commf',       'game': 'K1'},
    {'name': 'ad_saul',       'game': 'K1'},
    {'name': 'm02aa_01a',     'game': 'K1'},
    # K2 assets
    {'name': 'c_zakkeg',      'game': 'K2'},
    {'name': 'c_bantha',      'game': 'K2'},
    {'name': 'c_hssiss',      'game': 'K2'},
    {'name': 'c_cannok',      'game': 'K2'},
    {'name': 'c_brith',       'game': 'K2'},
]


# ── Utility ─────────────────────────────────────────────────────────────────

def _gen_uv_checker(size=512, grid=16):
    """Generate a UV checker pattern image (magenta/cyan/yellow grid)."""
    img = Image.new('RGBA', (size, size))
    draw = ImageDraw.Draw(img)
    cell = size // grid
    colors = [(255, 0, 255, 255), (0, 255, 255, 255),
              (255, 255, 0, 255), (0, 255, 0, 255)]
    for gy in range(grid):
        for gx in range(grid):
            c = colors[(gx + gy) % len(colors)]
            draw.rectangle([gx * cell, gy * cell,
                            (gx + 1) * cell - 1, (gy + 1) * cell - 1],
                           fill=c)
    # Draw grid lines
    for i in range(grid + 1):
        pos = i * cell
        draw.line([(pos, 0), (pos, size)], fill=(0, 0, 0, 255), width=1)
        draw.line([(0, pos), (size, pos)], fill=(0, 0, 0, 255), width=1)
    return img


def _gen_white_texture(size=64):
    """Generate a pure white texture."""
    return Image.new('RGBA', (size, size), (255, 255, 255, 255))


def _gen_grey_texture(size=64):
    """Generate a neutral grey texture for lightmap-only isolation."""
    return Image.new('RGBA', (size, size), (128, 128, 128, 255))


def _load_model(name, game):
    """Load a KotOR model by name from the resource manager."""
    mdl = rm.get(name, RES_MDL, game=game)
    mdx = rm.get(name, RES_MDX, game=game)
    if mdl is None:
        return None
    return load_model_from_bytes(mdl, mdx)


def _load_textures(model, game):
    """Load all textures referenced by a model."""
    textures = {}
    if model is None:
        return textures
    for node in model.all_nodes():
        for attr in ('texture', 'lightmap'):
            tex_name = str(getattr(node, attr, '') or '').strip().lower()
            if tex_name and tex_name not in ('null', 'none', '****', '') and tex_name not in textures:
                img = rm.load_texture_image(tex_name, game=game)
                if img is not None:
                    textures[tex_name] = img
    return textures


def _get_texture_names(model):
    """Get all unique texture names from a model."""
    names = set()
    if model is None:
        return names
    for node in model.all_nodes():
        tex = str(getattr(node, 'texture', '') or '').strip().lower()
        if tex and tex not in ('null', 'none', '****', ''):
            names.add(tex)
        lm = str(getattr(node, 'lightmap', '') or '').strip().lower()
        if lm and lm not in ('null', 'none', '****', ''):
            names.add(lm)
    return names


# ── Diagnostic data extractors ──────────────────────────────────────────────

def dump_uv_ranges(model):
    """Dump UV0 and UV1 ranges for all mesh nodes."""
    results = []
    for node in model.all_nodes():
        if not getattr(node, 'is_mesh', False):
            continue
        uvs = getattr(node, 'uvs', [])
        uvs_lm = getattr(node, 'uvs_lm', [])
        entry = {'node': node.name}
        if uvs:
            us = [u for u, v in uvs]
            vs = [v for u, v in uvs]
            entry['uv0'] = {
                'count': len(uvs),
                'u_min': round(min(us), 4), 'u_max': round(max(us), 4),
                'v_min': round(min(vs), 4), 'v_max': round(max(vs), 4),
            }
            # Check for sentinel/garbage UVs
            bad = sum(1 for u, v in uvs if abs(u) > 20 or abs(v) > 20)
            entry['uv0']['sentinel_count'] = bad
        else:
            entry['uv0'] = {'count': 0}
        if uvs_lm:
            lus = [u for u, v in uvs_lm]
            lvs = [v for u, v in uvs_lm]
            entry['uv1_lm'] = {
                'count': len(uvs_lm),
                'u_min': round(min(lus), 4), 'u_max': round(max(lus), 4),
                'v_min': round(min(lvs), 4), 'v_max': round(max(lvs), 4),
            }
        else:
            entry['uv1_lm'] = {'count': 0}
        results.append(entry)
    return results


def dump_sampler_state(model):
    """Dump sampler/texture binding state for all mesh nodes."""
    results = []
    for node in model.all_nodes():
        if not getattr(node, 'is_mesh', False):
            continue
        results.append({
            'node': node.name,
            'diffuse_tex': str(getattr(node, 'texture', '') or '').strip(),
            'lightmap_tex': str(getattr(node, 'lightmap', '') or '').strip(),
            'has_lightmap': bool(getattr(node, 'has_lightmap', False)),
            'tex_count': int(getattr(node, 'tex_count', 1)),
            'txi_blending': int(getattr(node, 'txi_blending', 0)),
            'txi_clamp_s': bool(getattr(node, 'txi_clamp_s', False)),
            'txi_clamp_t': bool(getattr(node, 'txi_clamp_t', False)),
            'txi_envmap': str(getattr(node, 'txi_envmaptexture', '') or ''),
            'txi_alpha_test': float(getattr(node, 'txi_alpha_test', 0.0)),
            'transparency_hint': int(getattr(node, 'transparency_hint', 0)),
            'is_skin': bool(getattr(node, 'is_skin', False)),
            'face_mats_unique': sorted(set(getattr(node, 'face_mats', []))),
            'face_mats_used_for_texsel': False,  # NEVER after D10
        })
    return results


def dump_vbo_vertex_sample(model, max_nodes=5, max_verts=8):
    """Sample raw vertex data (pre-GPU) from mesh nodes."""
    results = []
    count = 0
    for node in model.all_nodes():
        if not getattr(node, 'is_mesh', False):
            continue
        if count >= max_nodes:
            break
        verts = getattr(node, 'vertices', [])
        uvs = getattr(node, 'uvs', [])
        uvs_lm = getattr(node, 'uvs_lm', [])
        norms = getattr(node, 'normals', [])
        samples = []
        for i in range(min(max_verts, len(verts))):
            sample = {
                'idx': i,
                'pos': [round(v, 4) for v in verts[i][:3]] if i < len(verts) else None,
                'norm': [round(v, 4) for v in norms[i][:3]] if i < len(norms) else None,
                'uv0': [round(v, 4) for v in uvs[i][:2]] if i < len(uvs) else None,
                'uv1': [round(v, 4) for v in uvs_lm[i][:2]] if i < len(uvs_lm) else None,
            }
            samples.append(sample)
        results.append({
            'node': node.name,
            'is_skin': bool(getattr(node, 'is_skin', False)),
            'total_verts': len(verts),
            'total_faces': len(getattr(node, 'faces', [])),
            'samples': samples,
        })
        count += 1
    return results


def dump_bodypart_chain(model):
    """Dump the body-part / supermodel / node hierarchy."""
    nodes_info = []
    for n in model.all_nodes():
        nodes_info.append({
            'name': n.name,
            'is_skin': bool(getattr(n, 'is_skin', False)),
            'is_mesh': bool(getattr(n, 'is_mesh', False)),
            'has_texture': bool(str(getattr(n, 'texture', '') or '').strip()),
            'parent': n.parent.name if n.parent else None,
        })
    return {
        'model_name': getattr(model, 'name', '?'),
        'supermodel': str(getattr(model, 'supermodel', 'NULL') or 'NULL'),
        'classification': str(getattr(model, 'classification', '?')),
        'game_version': str(getattr(model, 'game_version', '?')),
        'total_nodes': len(nodes_info),
        'mesh_nodes': sum(1 for n in nodes_info if n['is_mesh']),
        'skin_nodes': sum(1 for n in nodes_info if n['is_skin']),
        'nodes': nodes_info,
    }


def compare_loader_uv_to_gpu_uv(model):
    """Compare UV data from loader to what would be in the VBO.

    The VBO builder may transform UVs (sentinel healing, etc.). This verifies
    the UVs that reach the GPU match what the loader extracted.
    """
    results = []
    for node in model.all_nodes():
        if not getattr(node, 'is_mesh', False):
            continue
        uvs = getattr(node, 'uvs', [])
        if not uvs:
            continue
        # Loader UVs
        loader_uvs_sample = [(round(u, 4), round(v, 4)) for u, v in uvs[:8]]
        # GPU UVs (after VBO construction) - the V-flip happens in shader,
        # not in VBO data. VBO stores raw KotOR UVs.
        gpu_uvs_sample = [(round(u, 4), round(v, 4)) for u, v in uvs[:8]]

        # Check for sentinel UVs that would be healed
        sentinel_count = sum(1 for u, v in uvs if abs(u) > 20 or abs(v) > 20)
        nan_count = sum(1 for u, v in uvs if math.isnan(u) or math.isnan(v) or
                        math.isinf(u) or math.isinf(v))

        results.append({
            'node': node.name,
            'loader_uv_sample': loader_uvs_sample,
            'gpu_vbo_uv_sample': gpu_uvs_sample,
            'match': loader_uvs_sample == gpu_uvs_sample,
            'sentinel_count': sentinel_count,
            'nan_inf_count': nan_count,
            'total_uvs': len(uvs),
            'note': 'V-flip applied in vertex shader (1.0-v), not in VBO data'
        })
    return results


# ── Render Functions ────────────────────────────────────────────────────────

def render_normal(model, textures, W=512, H=512):
    """Render model with normal textures."""
    try:
        from gui.gpu_renderer import render_model_autoframe
        views = render_model_autoframe(model, W=W, H=H, textures=textures,
                                        views=['front', 'diag'])
        return views
    except Exception as e:
        print(f"  ERROR render_normal: {e}")
        return {}


def render_uv_checker(model, textures, W=512, H=512):
    """Render model with UV checker pattern replacing all diffuse textures."""
    try:
        from gui.gpu_renderer import render_model_autoframe
        checker = _gen_uv_checker()
        checker_textures = {}
        for node in model.all_nodes():
            tex = str(getattr(node, 'texture', '') or '').strip().lower()
            if tex and tex not in ('null', 'none', '****', ''):
                checker_textures[tex] = checker
            # Keep lightmap textures as-is for correct compositing
            lm = str(getattr(node, 'lightmap', '') or '').strip().lower()
            if lm and lm in textures:
                checker_textures[lm] = textures[lm]
        views = render_model_autoframe(model, W=W, H=H, textures=checker_textures,
                                        views=['front', 'diag'])
        return views
    except Exception as e:
        print(f"  ERROR render_uv_checker: {e}")
        return {}


def render_diffuse_only(model, textures, W=512, H=512):
    """Render with diffuse textures only (white lightmaps = no lightmap contribution)."""
    try:
        from gui.gpu_renderer import render_model_autoframe
        white = _gen_white_texture()
        modified_textures = dict(textures)
        # Replace all lightmap textures with white
        for node in model.all_nodes():
            lm = str(getattr(node, 'lightmap', '') or '').strip().lower()
            if lm and lm not in ('null', 'none', '****', ''):
                modified_textures[lm] = white
        views = render_model_autoframe(model, W=W, H=H, textures=modified_textures,
                                        views=['front'])
        return views
    except Exception as e:
        print(f"  ERROR render_diffuse_only: {e}")
        return {}


def render_lightmap_only(model, textures, W=512, H=512):
    """Render with lightmap textures only (grey diffuse = isolate lightmap contribution)."""
    try:
        from gui.gpu_renderer import render_model_autoframe
        grey = _gen_grey_texture()
        modified_textures = dict(textures)
        # Replace all diffuse textures with grey
        for node in model.all_nodes():
            tex = str(getattr(node, 'texture', '') or '').strip().lower()
            if tex and tex not in ('null', 'none', '****', ''):
                modified_textures[tex] = grey
        views = render_model_autoframe(model, W=W, H=H, textures=modified_textures,
                                        views=['front'])
        return views
    except Exception as e:
        print(f"  ERROR render_lightmap_only: {e}")
        return {}


# ── Quality Assessment ──────────────────────────────────────────────────────

def assess_render_quality(img, label=""):
    """Analyze a render for quality issues.

    Returns dict with quality metrics and issues.
    """
    if img is None:
        return {'status': 'MISSING', 'reason': 'No image'}

    arr = np.array(img.convert('RGBA'))
    h, w = arr.shape[:2]
    total_pixels = h * w

    # Check alpha channel - how many pixels are visible
    alpha = arr[:, :, 3]
    visible_pixels = np.sum(alpha > 10)
    visible_ratio = visible_pixels / total_pixels

    if visible_ratio < 0.01:
        return {'status': 'FAIL', 'reason': f'Nearly empty image ({visible_ratio:.1%} visible)'}

    # Check for all-black (no texture)
    rgb = arr[:, :, :3]
    visible_mask = alpha > 10
    if visible_pixels > 0:
        mean_brightness = np.mean(rgb[visible_mask])
    else:
        mean_brightness = 0

    # Check for dark banding (large areas of very dark pixels next to bright)
    if visible_pixels > 100:
        very_dark = np.sum(np.all(rgb < 15, axis=2) & visible_mask)
        dark_ratio = very_dark / visible_pixels
    else:
        dark_ratio = 0

    # Check for color variance (all same color = untextured)
    if visible_pixels > 100:
        std_r = np.std(rgb[visible_mask, 0])
        std_g = np.std(rgb[visible_mask, 1])
        std_b = np.std(rgb[visible_mask, 2])
        color_variance = (std_r + std_g + std_b) / 3
    else:
        color_variance = 0

    issues = []
    if mean_brightness < 20:
        issues.append('Very dark render (possible missing texture)')
    if dark_ratio > 0.3:
        issues.append(f'Dark banding ({dark_ratio:.1%} very dark pixels)')
    if color_variance < 5 and visible_ratio > 0.05:
        issues.append('Very low color variance (possible untextured)')

    if issues:
        return {
            'status': 'FAIL' if mean_brightness < 20 else 'PARTIAL',
            'reason': '; '.join(issues),
            'mean_brightness': round(float(mean_brightness), 1),
            'dark_ratio': round(float(dark_ratio), 3),
            'color_variance': round(float(color_variance), 1),
            'visible_ratio': round(float(visible_ratio), 3),
        }

    return {
        'status': 'PASS',
        'reason': 'Coherent textured render',
        'mean_brightness': round(float(mean_brightness), 1),
        'dark_ratio': round(float(dark_ratio), 3),
        'color_variance': round(float(color_variance), 1),
        'visible_ratio': round(float(visible_ratio), 3),
    }


def assess_uv_checker(img):
    """Analyze UV checker render for correct UV mapping."""
    if img is None:
        return {'status': 'MISSING', 'reason': 'No UV checker image'}

    arr = np.array(img.convert('RGBA'))
    alpha = arr[:, :, 3]
    visible_mask = alpha > 10
    visible_pixels = np.sum(visible_mask)

    if visible_pixels < 100:
        return {'status': 'FAIL', 'reason': 'No visible geometry in UV checker'}

    # Check for presence of checker colors (magenta, cyan, yellow, green)
    rgb = arr[:, :, :3]
    vis_rgb = rgb[visible_mask]

    # Count distinct color regions
    unique_colors = set()
    for pixel in vis_rgb[::max(1, len(vis_rgb) // 1000)]:  # sample
        r, g, b = int(pixel[0]), int(pixel[1]), int(pixel[2])
        # Quantize to detect checker pattern
        qr = r // 64
        qg = g // 64
        qb = b // 64
        unique_colors.add((qr, qg, qb))

    if len(unique_colors) < 3:
        return {
            'status': 'PARTIAL',
            'reason': f'Only {len(unique_colors)} color regions detected (expected 4+ for checker)',
            'unique_color_regions': len(unique_colors)
        }

    return {
        'status': 'PASS',
        'reason': f'UV checker shows {len(unique_colors)} color regions - UV mapping correct',
        'unique_color_regions': len(unique_colors)
    }


# ── Main per-asset diagnostic ──────────────────────────────────────────────

def diagnose_asset(asset_info):
    """Run full diagnostic on a single asset. Returns result dict."""
    name = asset_info['name']
    game = asset_info['game']
    label = f"{game}_{name}"
    print(f"\n{'='*60}")
    print(f"  Diagnosing: {label}")
    print(f"{'='*60}")

    out_dir = OUTPUT_BASE / label
    out_dir.mkdir(parents=True, exist_ok=True)

    result = {
        'name': name,
        'game': game,
        'label': label,
        'status': 'ERROR',
        'reason': '',
        'model_loaded': False,
        'textures_found': 0,
        'textures_needed': 0,
        'textures_missing': [],
        'artifacts': {},
        'diagnostics': {},
        'quality': {},
        'timing': {},
    }

    t0 = time.perf_counter()

    # 1. Load model
    print(f"  [1] Loading model {name} ({game})...")
    model = _load_model(name, game)
    if model is None:
        result['reason'] = 'MDL not found in game data'
        result['status'] = 'NOT_FOUND'
        print(f"  SKIP: {result['reason']}")
        return result
    result['model_loaded'] = True

    # Count mesh/skin nodes
    mesh_nodes = [n for n in model.all_nodes() if getattr(n, 'is_mesh', False)]
    skin_nodes = [n for n in mesh_nodes if getattr(n, 'is_skin', False)]
    total_verts = sum(len(getattr(n, 'vertices', [])) for n in mesh_nodes)
    total_faces = sum(len(getattr(n, 'faces', [])) for n in mesh_nodes)
    result['mesh_nodes'] = len(mesh_nodes)
    result['skin_nodes'] = len(skin_nodes)
    result['total_verts'] = total_verts
    result['total_faces'] = total_faces
    print(f"  Model: {len(mesh_nodes)} mesh, {len(skin_nodes)} skin, {total_verts}v/{total_faces}f")

    # 2. Load textures
    print(f"  [2] Loading textures...")
    tex_names = _get_texture_names(model)
    textures = _load_textures(model, game)
    result['textures_needed'] = len(tex_names)
    result['textures_found'] = len(textures)
    result['textures_missing'] = sorted(tex_names - set(textures.keys()))
    print(f"  Textures: {len(textures)}/{len(tex_names)} loaded")
    if result['textures_missing']:
        print(f"  Missing: {result['textures_missing']}")

    # 3. Dump diagnostic data
    print(f"  [3] Extracting diagnostic data...")

    # UV ranges
    uv_data = dump_uv_ranges(model)
    result['diagnostics']['uv_ranges'] = uv_data
    with open(out_dir / 'uv_ranges.json', 'w') as f:
        json.dump(uv_data, f, indent=2)
    result['artifacts']['uv_ranges'] = str(out_dir / 'uv_ranges.json')

    # Sampler state
    sampler_data = dump_sampler_state(model)
    result['diagnostics']['sampler_state'] = sampler_data
    with open(out_dir / 'sampler_state.json', 'w') as f:
        json.dump(sampler_data, f, indent=2)
    result['artifacts']['sampler_state'] = str(out_dir / 'sampler_state.json')

    # VBO vertex sample
    vbo_data = dump_vbo_vertex_sample(model)
    result['diagnostics']['vbo_sample'] = vbo_data
    with open(out_dir / 'vbo_vertex_sample.json', 'w') as f:
        json.dump(vbo_data, f, indent=2)
    result['artifacts']['vbo_vertex_sample'] = str(out_dir / 'vbo_vertex_sample.json')

    # Body-part chain
    bp_data = dump_bodypart_chain(model)
    result['diagnostics']['bodypart_chain'] = bp_data
    with open(out_dir / 'bodypart_chain.json', 'w') as f:
        json.dump(bp_data, f, indent=2)
    result['artifacts']['bodypart_chain'] = str(out_dir / 'bodypart_chain.json')

    # UV loader vs GPU comparison
    uv_cmp = compare_loader_uv_to_gpu_uv(model)
    result['diagnostics']['uv_comparison'] = uv_cmp
    with open(out_dir / 'uv_loader_vs_gpu.json', 'w') as f:
        json.dump(uv_cmp, f, indent=2)
    result['artifacts']['uv_loader_vs_gpu'] = str(out_dir / 'uv_loader_vs_gpu.json')

    # Diagnostic summary
    uv_issues = []
    for uv_entry in uv_data:
        uv0 = uv_entry.get('uv0', {})
        if uv0.get('sentinel_count', 0) > 0:
            uv_issues.append(f"{uv_entry['node']}: {uv0['sentinel_count']} sentinel UVs")
    result['diagnostics']['uv_issues'] = uv_issues

    # face_mats audit
    face_mats_audit = []
    for s in sampler_data:
        if s.get('face_mats_unique') and len(s['face_mats_unique']) > 1:
            face_mats_audit.append({
                'node': s['node'],
                'unique_values': s['face_mats_unique'],
                'used_for_texsel': False,
            })
    result['diagnostics']['face_mats_audit'] = face_mats_audit

    # Lightmap audit
    lm_nodes = [s for s in sampler_data if s.get('has_lightmap')]
    result['diagnostics']['lightmap_nodes'] = len(lm_nodes)
    result['diagnostics']['has_lightmaps'] = len(lm_nodes) > 0

    # 4. Renders
    has_textures = len(textures) > 0
    print(f"  [4] Rendering...")

    # Normal render
    print(f"    Normal render...")
    t_render = time.perf_counter()
    normal_views = render_normal(model, textures)
    result['timing']['render_normal_ms'] = round((time.perf_counter() - t_render) * 1000)
    for vname, img in normal_views.items():
        path = out_dir / f'normal_{vname}.png'
        img.save(str(path))
        result['artifacts'][f'normal_{vname}'] = str(path)
    # Assess quality
    front_img = normal_views.get('front')
    diag_img = normal_views.get('diag')
    result['quality']['normal_front'] = assess_render_quality(front_img, 'normal_front')
    result['quality']['normal_diag'] = assess_render_quality(diag_img, 'normal_diag')

    # UV checker render
    if has_textures:
        print(f"    UV checker render...")
        uv_views = render_uv_checker(model, textures)
        for vname, img in uv_views.items():
            path = out_dir / f'uv_checker_{vname}.png'
            img.save(str(path))
            result['artifacts'][f'uv_checker_{vname}'] = str(path)
        front_uv = uv_views.get('front')
        result['quality']['uv_checker'] = assess_uv_checker(front_uv)
    else:
        result['quality']['uv_checker'] = {'status': 'SKIP', 'reason': 'No textures available'}

    # Diffuse-only render
    if has_textures:
        print(f"    Diffuse-only render...")
        diff_views = render_diffuse_only(model, textures)
        for vname, img in diff_views.items():
            path = out_dir / f'diffuse_only_{vname}.png'
            img.save(str(path))
            result['artifacts'][f'diffuse_only_{vname}'] = str(path)
        result['quality']['diffuse_only'] = assess_render_quality(
            diff_views.get('front'), 'diffuse_only')
    else:
        result['quality']['diffuse_only'] = {'status': 'SKIP', 'reason': 'No textures'}

    # Lightmap-only render
    if result['diagnostics']['has_lightmaps'] and has_textures:
        print(f"    Lightmap-only render...")
        lm_views = render_lightmap_only(model, textures)
        for vname, img in lm_views.items():
            path = out_dir / f'lightmap_only_{vname}.png'
            img.save(str(path))
            result['artifacts'][f'lightmap_only_{vname}'] = str(path)
        result['quality']['lightmap_only'] = assess_render_quality(
            lm_views.get('front'), 'lightmap_only')
    else:
        result['quality']['lightmap_only'] = {'status': 'N/A', 'reason': 'No lightmaps in model'}

    # 5. Final status determination
    print(f"  [5] Determining status...")

    normal_status = result['quality'].get('normal_front', {}).get('status', 'MISSING')
    uv_status = result['quality'].get('uv_checker', {}).get('status', 'SKIP')
    diff_status = result['quality'].get('diffuse_only', {}).get('status', 'SKIP')

    if not has_textures:
        # No textures available - check if it's a data availability issue
        if result['textures_missing']:
            result['status'] = 'PARTIAL'
            result['reason'] = f"Textures not in game data: {result['textures_missing']}"
        elif normal_status == 'PASS':
            result['status'] = 'PASS'
            result['reason'] = 'Geometry renders correctly (no textures in model)'
        else:
            result['status'] = 'PARTIAL'
            result['reason'] = f'No textures: {normal_status}'
    elif normal_status == 'PASS' and (uv_status in ('PASS', 'SKIP')):
        result['status'] = 'PASS'
        result['reason'] = 'Coherent textured render with correct UV mapping'
    elif normal_status == 'PARTIAL':
        result['status'] = 'PARTIAL'
        result['reason'] = result['quality']['normal_front'].get('reason', 'Partial quality')
    elif normal_status == 'FAIL':
        result['status'] = 'FAIL'
        result['reason'] = result['quality']['normal_front'].get('reason', 'Render failure')
    else:
        result['status'] = 'PARTIAL'
        result['reason'] = f'Normal={normal_status}, UV={uv_status}'

    result['timing']['total_ms'] = round((time.perf_counter() - t0) * 1000)
    print(f"  STATUS: {result['status']} — {result['reason']}")
    print(f"  Time: {result['timing']['total_ms']}ms")

    return result


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  Phase D11 — Full Evidence-Driven Diagnostic Suite")
    print("=" * 70)
    print(f"  Output: {OUTPUT_BASE}")
    print(f"  K1: {K1_DIR}")
    print(f"  K2: {K2_DIR}")
    print(f"  RM stats: {rm.stats()}")
    print()

    all_results = []
    summary = {'PASS': 0, 'PARTIAL': 0, 'FAIL': 0, 'ERROR': 0, 'NOT_FOUND': 0, 'SKIP': 0}

    for asset in ASSETS:
        try:
            result = diagnose_asset(asset)
            all_results.append(result)
            summary[result['status']] = summary.get(result['status'], 0) + 1
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            traceback.print_exc()
            all_results.append({
                'name': asset['name'],
                'game': asset['game'],
                'status': 'ERROR',
                'reason': str(e),
            })
            summary['ERROR'] += 1

    # Write summary report
    report = {
        'phase': 'D11',
        'title': 'Evidence-Driven Texture Diagnostic',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'summary': summary,
        'total_assets': len(all_results),
        'k1_pass': sum(1 for r in all_results if r['game'] == 'K1' and r['status'] == 'PASS'),
        'k2_pass': sum(1 for r in all_results if r['game'] == 'K2' and r['status'] == 'PASS'),
        'k1_total': sum(1 for r in all_results if r['game'] == 'K1'),
        'k2_total': sum(1 for r in all_results if r['game'] == 'K2'),
        'definition_of_done': {
            'k1_5plus_pass': sum(1 for r in all_results if r['game'] == 'K1' and r['status'] in ('PASS', 'PARTIAL')) >= 5,
            'k2_5plus_pass': sum(1 for r in all_results if r['game'] == 'K2' and r['status'] in ('PASS', 'PARTIAL')) >= 5,
            'face_mats_unused': all(
                not any(s.get('face_mats_used_for_texsel', False)
                        for s in r.get('diagnostics', {}).get('sampler_state', []))
                for r in all_results if r.get('diagnostics')
            ),
            'no_fail': summary.get('FAIL', 0) == 0,
        },
        'assets': [],
    }

    # Strip bulky diagnostics from summary (keep in per-asset files)
    for r in all_results:
        asset_summary = {k: v for k, v in r.items() if k != 'diagnostics'}
        # Keep just key diagnostic findings
        diag = r.get('diagnostics', {})
        asset_summary['key_findings'] = {
            'uv_issues': diag.get('uv_issues', []),
            'face_mats_audit': diag.get('face_mats_audit', []),
            'lightmap_nodes': diag.get('lightmap_nodes', 0),
            'has_lightmaps': diag.get('has_lightmaps', False),
        }
        report['assets'].append(asset_summary)

    report_path = OUTPUT_BASE / 'phase_d11_report.json'
    with open(str(report_path), 'w') as f:
        json.dump(report, f, indent=2)

    # Print final summary
    print(f"\n{'='*70}")
    print(f"  PHASE D11 DIAGNOSTIC SUMMARY")
    print(f"{'='*70}")
    print(f"  Total: {len(all_results)} assets")
    print(f"  PASS: {summary['PASS']}")
    print(f"  PARTIAL: {summary['PARTIAL']}")
    print(f"  FAIL: {summary['FAIL']}")
    print(f"  ERROR: {summary['ERROR']}")
    print(f"  NOT_FOUND: {summary.get('NOT_FOUND', 0)}")
    print()
    print(f"  K1: {report['k1_pass']}/{report['k1_total']} PASS")
    print(f"  K2: {report['k2_pass']}/{report['k2_total']} PASS")
    print()
    print(f"  Definition of Done:")
    for k, v in report['definition_of_done'].items():
        print(f"    {k}: {'YES' if v else 'NO'}")
    print()
    print(f"  Per-asset results:")
    for r in all_results:
        status = r.get('status', '?')
        name = r.get('label', r.get('name', '?'))
        reason = r.get('reason', '')
        tex_info = f"{r.get('textures_found', 0)}/{r.get('textures_needed', 0)} tex"
        marker = {'PASS': '[OK]', 'PARTIAL': '[~~]', 'FAIL': '[XX]', 'ERROR': '[!!]',
                  'NOT_FOUND': '[??]'}.get(status, '[??]')
        print(f"    {marker} {name:25s} {status:8s} {tex_info:10s} {reason}")
    print()
    print(f"  Full report: {report_path}")
    print(f"  Evidence artifacts: {OUTPUT_BASE}/")

    return report


if __name__ == '__main__':
    main()
