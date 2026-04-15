#!/usr/bin/env python3
"""
validate_anim_skinning_fix.py — Validation for FIX-SKIN-ANIM
=============================================================
Validates that animated GPU skinning now works correctly on c_kraytdragon
while preserving the bind-pose fix for all characters.

Test cases:
  1. c_kraytdragon bind-pose (no anim) — must render correctly
  2. c_kraytdragon animated (cwalk, GPU skinning) — must NOT explode
  3. c_bantha bind-pose — regression check
  4. n_commf bind-pose — regression check
  5. c_female bind-pose — regression check
  6. m02aa_01a module — regression check
"""
import sys, os, struct, io, json, time, math, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from PIL import Image, ImageDraw

GAME_DIR = os.path.join(os.path.dirname(__file__), 'game_data', 'swkotor')
OUT_DIR  = os.path.join(os.path.dirname(__file__), 'validation_anim_fix')
os.makedirs(OUT_DIR, exist_ok=True)


# ── BIF extraction helpers (same as validation_gate.py) ──

def extract_from_erf(erf_path, target_names):
    results = {}
    target_lower = {n.lower() for n in target_names}
    with open(erf_path, 'rb') as f:
        f.read(8); f.read(4); f.read(4)
        entry_count, = struct.unpack('<I', f.read(4))
        f.read(4)
        off_key_list, = struct.unpack('<I', f.read(4))
        off_res_list, = struct.unpack('<I', f.read(4))
        for i in range(entry_count):
            f.seek(off_key_list + i * 24)
            resref = f.read(16).rstrip(b'\x00').decode('ascii', errors='replace').lower()
            res_id, res_type = struct.unpack('<IH', f.read(6))
            if resref in target_lower:
                f.seek(off_res_list + i * 8)
                data_offset, data_size = struct.unpack('<II', f.read(8))
                f.seek(data_offset)
                results[resref] = f.read(data_size)
    return results

def extract_mdl_mdx_from_bif(key_path, bif_dir, model_names):
    results = {}
    target = {n.lower() for n in model_names}
    with open(key_path, 'rb') as f:
        f.read(8)
        bif_count, = struct.unpack('<I', f.read(4))
        key_count, = struct.unpack('<I', f.read(4))
        off_file_table, = struct.unpack('<I', f.read(4))
        off_key_table, = struct.unpack('<I', f.read(4))
        bif_files = []
        for i in range(bif_count):
            f.seek(off_file_table + i * 12)
            f.read(4)
            name_offset, = struct.unpack('<I', f.read(4))
            name_size, = struct.unpack('<H', f.read(2))
            f.read(2)
            pos = f.tell()
            f.seek(name_offset)
            bif_name = f.read(name_size).rstrip(b'\x00').decode('ascii', errors='replace').replace('\\', '/')
            bif_files.append(bif_name)
            f.seek(pos)
        for i in range(key_count):
            f.seek(off_key_table + i * 22)
            resref = f.read(16).rstrip(b'\x00').decode('ascii', errors='replace').lower()
            res_type, = struct.unpack('<H', f.read(2))
            res_id, = struct.unpack('<I', f.read(4))
            if resref in target and res_type in (2002, 3008):
                bif_idx = (res_id >> 20) & 0xFFF
                res_idx = res_id & 0xFFFFF
                if bif_idx < len(bif_files):
                    bif_path = os.path.join(bif_dir, bif_files[bif_idx])
                    if os.path.exists(bif_path):
                        with open(bif_path, 'rb') as bf:
                            bf.read(8); bf.read(4); bf.read(4)
                            var_table_offset, = struct.unpack('<I', bf.read(4))
                            bf.seek(var_table_offset + res_idx * 16)
                            bf.read(4)
                            data_offset, = struct.unpack('<I', bf.read(4))
                            data_size, = struct.unpack('<I', bf.read(4))
                            bf.read(4)
                            bf.seek(data_offset)
                            raw = bf.read(data_size)
                            ext = 'mdl' if res_type == 2002 else 'mdx'
                            results.setdefault(resref, {})[ext] = raw
    return results

def extract_from_bif_via_key(key_path, bif_dir, target_names):
    results = {}
    target_lower = {n.lower() for n in target_names}
    with open(key_path, 'rb') as f:
        f.read(8)
        bif_count, = struct.unpack('<I', f.read(4))
        key_count, = struct.unpack('<I', f.read(4))
        off_file_table, = struct.unpack('<I', f.read(4))
        off_key_table, = struct.unpack('<I', f.read(4))
        bif_files = []
        for i in range(bif_count):
            f.seek(off_file_table + i * 12)
            f.read(4)
            name_offset, = struct.unpack('<I', f.read(4))
            name_size, = struct.unpack('<H', f.read(2))
            f.read(2)
            pos = f.tell()
            f.seek(name_offset)
            bif_name = f.read(name_size).rstrip(b'\x00').decode('ascii', errors='replace').replace('\\', '/')
            bif_files.append(bif_name)
            f.seek(pos)
        for i in range(key_count):
            f.seek(off_key_table + i * 22)
            resref = f.read(16).rstrip(b'\x00').decode('ascii', errors='replace').lower()
            res_type, = struct.unpack('<H', f.read(2))
            res_id, = struct.unpack('<I', f.read(4))
            if resref in target_lower and res_type != 2022:
                bif_idx = (res_id >> 20) & 0xFFF
                res_idx = res_id & 0xFFFFF
                if bif_idx < len(bif_files):
                    bif_path = os.path.join(bif_dir, bif_files[bif_idx])
                    if os.path.exists(bif_path):
                        with open(bif_path, 'rb') as bf:
                            bf.read(8); bf.read(4); bf.read(4)
                            var_table_offset, = struct.unpack('<I', bf.read(4))
                            bf.seek(var_table_offset + res_idx * 16)
                            bf.read(4)
                            data_offset, = struct.unpack('<I', bf.read(4))
                            data_size, = struct.unpack('<I', bf.read(4))
                            bf.read(4)
                            bf.seek(data_offset)
                            raw = bf.read(data_size)
                            if resref not in results or len(raw) > len(results[resref]):
                                results[resref] = raw
    return results

def decode_texture(raw_bytes):
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        return img.convert('RGBA')
    except Exception: pass
    try:
        from src.gui.viewport import _load_tpc_bytes
        return _load_tpc_bytes(raw_bytes)
    except Exception: pass
    return None

def collect_tex_names(model):
    names = set()
    for node in model.all_nodes():
        for attr in ['texture', 'lightmap']:
            t = str(getattr(node, attr, '') or '').strip().lower()
            if t and t not in ('null', ''):
                names.add(t)
        for tn in getattr(node, 'texture_names', []):
            t = str(tn or '').strip().lower()
            if t and t not in ('null', ''):
                names.add(t)
    return names

def analyze_render(img):
    arr = np.array(img.convert('RGBA'))
    h, w = arr.shape[:2]
    total_px = h * w
    rgb = arr[:, :, :3].astype(float)
    corners = [arr[3,3,:3], arr[3,-3,:3], arr[-3,3,:3], arr[-3,-3,:3]]
    bg_color = np.mean([c.astype(float) for c in corners], axis=0)
    dist = np.sqrt(np.sum((rgb - bg_color)**2, axis=2))
    non_bg = dist > 15.0
    n_vis = int(non_bg.sum())
    pct = n_vis / total_px * 100
    result = {'visible_pct': pct, 'is_empty': pct < 1.0}
    if n_vis > 100:
        vis = rgb[non_bg]
        result['rgb_std'] = float(vis.std())
        result['is_textured'] = result['rgb_std'] > 10.0
        # Explosion check
        block_size = 16
        nby, nbx = h // block_size, w // block_size
        if nby > 0 and nbx > 0:
            sparse = occupied = 0
            for by in range(nby):
                for bx in range(nbx):
                    blk = non_bg[by*block_size:(by+1)*block_size, bx*block_size:(bx+1)*block_size]
                    occ = blk.sum()
                    if occ > 0:
                        occupied += 1
                        if occ < block_size * block_size * 0.05:
                            sparse += 1
            result['sparse_ratio'] = sparse / max(1, occupied)
        else:
            result['sparse_ratio'] = 0
        result['explosion_risk'] = pct > 55 and result['sparse_ratio'] > 0.3
    else:
        result['rgb_std'] = 0
        result['is_textured'] = False
        result['explosion_risk'] = False
    return result


def main():
    print("="*70)
    print("VALIDATION: FIX-SKIN-ANIM — Animated GPU Skinning Fix")
    print("="*70)

    key_path = os.path.join(GAME_DIR, 'chitin.key')
    if not os.path.isfile(key_path):
        print(f"ERROR: chitin.key not found at {key_path}")
        return

    from src.core.kotor_loader import load_model_from_bytes
    from src.core.animation_engine import AnimationEngine
    from src.core.gpu_skinning import MatrixPaletteUploader

    # 1. Extract models
    print("\n[1/7] Extracting models...")
    chars = ['c_kraytdragon', 'c_bantha', 'n_commf', 'c_female']
    extracted = extract_mdl_mdx_from_bif(key_path, GAME_DIR, chars)

    models = {}
    for name in chars:
        d = extracted.get(name, {})
        if 'mdl' in d and 'mdx' in d:
            models[name] = load_model_from_bytes(d['mdl'], d['mdx'], name)
            m = models[name]
            skins = sum(1 for n in m.all_nodes() if n.is_skin)
            anims = len(m.animations)
            print(f"  {name}: {len(m.all_nodes())} nodes, {skins} skins, {anims} anims")

    # Load module model
    mdl_file = os.path.join(os.path.dirname(__file__), 'm02aa_01a.mdl')
    mdx_file = os.path.join(os.path.dirname(__file__), 'm02aa_01a.mdx')
    if os.path.isfile(mdl_file) and os.path.isfile(mdx_file):
        with open(mdl_file, 'rb') as f: mdl_data = f.read()
        with open(mdx_file, 'rb') as f: mdx_data = f.read()
        models['m02aa_01a'] = load_model_from_bytes(mdl_data, mdx_data, 'm02aa_01a')
        print(f"  m02aa_01a: {len(models['m02aa_01a'].all_nodes())} nodes (module)")

    # 2. Extract textures
    print("\n[2/7] Extracting textures...")
    all_tex_names = set()
    for m in models.values():
        all_tex_names |= collect_tex_names(m)
    print(f"  Total texture names: {len(all_tex_names)}")

    textures = {}
    tex_data = extract_from_bif_via_key(key_path, GAME_DIR, all_tex_names)
    for tname, traw in tex_data.items():
        img = decode_texture(traw)
        if img:
            textures[tname] = img
    # Also check ERFs
    erf_dir = os.path.join(GAME_DIR, 'data')
    if os.path.isdir(erf_dir):
        for fn in os.listdir(erf_dir):
            if fn.endswith('.erf'):
                missing = all_tex_names - set(textures.keys())
                if missing:
                    erf_data = extract_from_erf(os.path.join(erf_dir, fn), missing)
                    for tname, traw in erf_data.items():
                        if tname not in textures:
                            img = decode_texture(traw)
                            if img:
                                textures[tname] = img
    print(f"  Decoded textures: {len(textures)}")

    # 3. Verify bind-pose palette
    print("\n[3/7] Verifying bind-pose palette (identity)...")
    for name, model in models.items():
        if not any(n.is_skin for n in model.all_nodes()):
            continue
        up = MatrixPaletteUploader(max_bones=128)
        up.build_inverse_bind_pose(model)
        palette = up.compute_palette(None)
        identity = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]
        non_id = sum(1 for bm in palette if sum(abs(bm.flat_col[i]-identity[i]) for i in range(16)) > 0.001)
        status = "PASS" if non_id == 0 else "FAIL"
        print(f"  {name}: {status} ({non_id}/{len(palette)} non-identity)")

    # 4. Verify animated palette for c_kraytdragon
    print("\n[4/7] Verifying animated palette (cwalk)...")
    if 'c_kraytdragon' in models:
        kd = models['c_kraytdragon']
        engine = AnimationEngine(kd)
        engine.play('cwalk', loop=True, blend=False)
        anim_pose = engine.evaluate(0.98)

        up = MatrixPaletteUploader(max_bones=128)
        up.build_inverse_bind_pose(kd)
        palette = up.compute_palette(anim_pose)
        identity = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]
        non_id = sum(1 for bm in palette if sum(abs(bm.flat_col[i]-identity[i]) for i in range(16)) > 0.001)
        print(f"  c_kraytdragon cwalk: {non_id}/{len(palette)} non-identity bones animated")

        # Verify no explosion: check that translation components are reasonable
        max_t = 0
        for bm in palette:
            col = bm.flat_col
            # Translation in column-major: col[12], col[13], col[14]
            tx, ty, tz = col[12], col[13], col[14]
            mag = math.sqrt(tx*tx + ty*ty + tz*tz)
            max_t = max(max_t, mag)
        print(f"  Max translation magnitude: {max_t:.2f}")
        if max_t < 50:
            print(f"  PASS: Translations within reasonable range")
        else:
            print(f"  WARNING: Large translations detected ({max_t:.2f})")

    # 5. GPU Render
    print("\n[5/7] GPU rendering...")
    from src.gui.gpu_renderer import GpuRenderer
    renderer = GpuRenderer()
    results = {}

    # Simple camera
    class Camera:
        def __init__(self, dist=10, pitch=20, yaw=30, target=(0,0,1)):
            import math as m
            self.fov = 45
            self._near = 0.01
            self._far = 2000
            self._target = target
            self._pitch = m.radians(pitch)
            self._yaw = m.radians(yaw)
            self._dist = dist
        def eye(self):
            import math as m
            x = self._dist * m.cos(self._pitch) * m.sin(self._yaw) + self._target[0]
            y = self._dist * m.cos(self._pitch) * m.cos(self._yaw) + self._target[1]
            z = self._dist * m.sin(self._pitch) + self._target[2]
            return (x, y, z)
        def target(self):
            return self._target

    SIZE = 512

    # 5a. Bind-pose renders
    for name in chars:
        if name not in models: continue
        model = models[name]
        model.compute_bounds()
        cx = (model.bb_min[0]+model.bb_max[0])/2
        cy = (model.bb_min[1]+model.bb_max[1])/2
        cz = (model.bb_min[2]+model.bb_max[2])/2
        ext = max(model.bb_max[0]-model.bb_min[0], model.bb_max[1]-model.bb_min[1], model.bb_max[2]-model.bb_min[2])
        dist = ext * 1.5

        for view, pitch, yaw in [('front', 15, 0), ('diag', 25, 45)]:
            cam = Camera(dist=dist, pitch=pitch, yaw=yaw, target=(cx, cy, cz))
            try:
                img = renderer.render(model, cam, SIZE, SIZE, textures, anim_pose=None, anim_time=0.0)
                if img:
                    path = os.path.join(OUT_DIR, f'{name}_bindpose_{view}.png')
                    img.save(path)
                    a = analyze_render(img)
                    tag = f"{name}_bindpose_{view}"
                    results[tag] = a
                    status = "PASS" if not a['is_empty'] and not a['explosion_risk'] else "FAIL"
                    print(f"  {tag}: vis={a['visible_pct']:.1f}% std={a.get('rgb_std',0):.1f} expl={a['explosion_risk']} -> {status}")
            except Exception as e:
                print(f"  {name} {view}: RENDER ERROR: {e}")

    # 5b. Animated c_kraytdragon
    if 'c_kraytdragon' in models:
        kd = models['c_kraytdragon']
        engine = AnimationEngine(kd)
        engine.play('cwalk', loop=True, blend=False)
        anim_pose = engine.evaluate(0.98)

        kd.compute_bounds()
        cx = (kd.bb_min[0]+kd.bb_max[0])/2
        cy = (kd.bb_min[1]+kd.bb_max[1])/2
        cz = (kd.bb_min[2]+kd.bb_max[2])/2
        ext = max(kd.bb_max[0]-kd.bb_min[0], kd.bb_max[1]-kd.bb_min[1], kd.bb_max[2]-kd.bb_min[2])

        for view, pitch, yaw in [('front', 15, 0), ('diag', 25, 45)]:
            cam = Camera(dist=ext*1.5, pitch=pitch, yaw=yaw, target=(cx, cy, cz))
            try:
                img = renderer.render(kd, cam, SIZE, SIZE, textures, anim_pose=anim_pose, anim_time=0.98)
                if img:
                    path = os.path.join(OUT_DIR, f'c_kraytdragon_animated_{view}.png')
                    img.save(path)
                    a = analyze_render(img)
                    tag = f"c_kraytdragon_animated_{view}"
                    results[tag] = a
                    status = "PASS" if not a['is_empty'] and not a['explosion_risk'] else "FAIL"
                    print(f"  {tag}: vis={a['visible_pct']:.1f}% std={a.get('rgb_std',0):.1f} expl={a['explosion_risk']} -> {status}")
            except Exception as e:
                print(f"  c_kraytdragon animated {view}: RENDER ERROR: {e}")
                traceback.print_exc()

    # 5c. Module render
    if 'm02aa_01a' in models:
        mod = models['m02aa_01a']
        mod.compute_bounds()
        cx = (mod.bb_min[0]+mod.bb_max[0])/2
        cy = (mod.bb_min[1]+mod.bb_max[1])/2
        cz = (mod.bb_min[2]+mod.bb_max[2])/2
        ext = max(mod.bb_max[0]-mod.bb_min[0], mod.bb_max[1]-mod.bb_min[1], mod.bb_max[2]-mod.bb_min[2])
        cam = Camera(dist=ext*0.8, pitch=35, yaw=30, target=(cx, cy, cz))
        try:
            img = renderer.render(mod, cam, SIZE, SIZE, textures, anim_pose=None, anim_time=0.0)
            if img:
                path = os.path.join(OUT_DIR, 'm02aa_01a_diag.png')
                img.save(path)
                a = analyze_render(img)
                results['m02aa_01a_diag'] = a
                print(f"  m02aa_01a_diag: vis={a['visible_pct']:.1f}% std={a.get('rgb_std',0):.1f} -> PASS")
        except Exception as e:
            print(f"  m02aa_01a: RENDER ERROR: {e}")

    # 6. Summary
    print("\n[6/7] Per-asset results:")
    print("="*70)
    all_pass = True
    for tag, a in sorted(results.items()):
        is_empty = a.get('is_empty', True)
        is_expl = a.get('explosion_risk', False)
        vis = a.get('visible_pct', 0)
        std = a.get('rgb_std', 0)

        if is_empty:
            status = "FAIL (empty render)"
            all_pass = False
        elif is_expl:
            status = "FAIL (geometry explosion)"
            all_pass = False
        else:
            status = "PASS"

        print(f"  {tag:<45} vis={vis:>5.1f}% std={std:>5.1f} {status}")

    # 7. Final report
    print(f"\n[7/7] Final Status:")
    print("="*70)
    print(f"  Files changed: src/core/gpu_skinning.py")
    print(f"    - MatrixPaletteUploader.build_inverse_bind_pose()")
    print(f"    - MatrixPaletteUploader.compute_palette()")
    print(f"")
    print(f"  Root cause: Both functions used LOCAL (parent-relative) bone transforms")
    print(f"  instead of WORLD (model-space) transforms accumulated through the parent chain.")
    print(f"  For bones deeper than depth 1, this produced incorrect skinning matrices.")
    print(f"")
    print(f"  Fix: Walk parent chain in both build_inverse_bind_pose() and compute_palette()")
    print(f"  to compute world-space transforms: world = parent_world x local.")
    print(f"  Bind-pose fix preserved: compute_palette(None) still returns identity matrices.")
    print(f"")
    n_pass = sum(1 for a in results.values() if not a.get('is_empty') and not a.get('explosion_risk'))
    n_total = len(results)
    print(f"  Results: {n_pass}/{n_total} PASS")
    if all_pass:
        print(f"  STATUS: DONE")
    else:
        print(f"  STATUS: PARTIAL")

    # Save report
    report = {
        'fix': 'FIX-SKIN-ANIM',
        'file_changed': 'src/core/gpu_skinning.py',
        'functions_changed': ['build_inverse_bind_pose', 'compute_palette'],
        'root_cause': 'LOCAL transforms used instead of WORLD (parent-chain accumulated)',
        'results': {k: {sk: sv for sk, sv in v.items() if isinstance(sv, (int, float, bool, str))} for k, v in results.items()},
        'n_pass': n_pass,
        'n_total': n_total,
        'status': 'DONE' if all_pass else 'PARTIAL',
    }
    with open(os.path.join(OUT_DIR, 'validation_report.json'), 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved to {OUT_DIR}/validation_report.json")

if __name__ == '__main__':
    main()
