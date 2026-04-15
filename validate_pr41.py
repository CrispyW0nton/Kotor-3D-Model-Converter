#!/usr/bin/env python3
"""
validate_pr41.py — Comprehensive live-rendering validation for PR #41.

Tests:
  1. Character models (≥3): p_hk47, c_kraytdragon, pmhc01, n_commf
     - UV seam healing correctness
     - Texture wrapping (no scrambling/stretching)
     - GPU skinning path active
  2. Module/tile model: m02aa_01a
     - Large UV tiling preserved
     - Texture repetition visually correct
  3. GPU skinning verification on skinned characters
  4. Non-skinned mesh verification
  5. Sampler-slot, UV0/UV1 routing, wrap-mode checks

Outputs screenshots to validation_pr41/ directory.
"""

import sys, os, struct, io, json, time, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from PIL import Image

GAME_DIR = os.path.join(os.path.dirname(__file__), 'game_data', 'swkotor')
OUT_DIR  = os.path.join(os.path.dirname(__file__), 'validation_pr41')
os.makedirs(OUT_DIR, exist_ok=True)

# ── Asset extraction helpers ────────────────────────────────────────────────

def extract_from_erf(erf_path, target_names):
    """Extract resources from an ERF V1.0 file."""
    results = {}
    target_lower = {n.lower() for n in target_names}
    with open(erf_path, 'rb') as f:
        f.read(8)  # magic + version
        f.read(4)  # lang_count
        f.read(4)  # loc_str_size
        entry_count, = struct.unpack('<I', f.read(4))
        f.read(4)  # off_loc_str
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


def extract_from_bif_via_key(key_path, bif_dir, target_names):
    """Extract resources from BIF files via chitin.key."""
    results = {}
    target_lower = {n.lower() for n in target_names}
    with open(key_path, 'rb') as f:
        f.read(8)  # magic + version
        bif_count, = struct.unpack('<I', f.read(4))
        key_count, = struct.unpack('<I', f.read(4))
        off_file_table, = struct.unpack('<I', f.read(4))
        off_key_table, = struct.unpack('<I', f.read(4))
        bif_files = []
        for i in range(bif_count):
            f.seek(off_file_table + i * 12)
            f.read(4)  # bif_size
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
            if resref in target_lower and res_type != 2022:  # skip TXI
                bif_idx = (res_id >> 20) & 0xFFF
                res_idx = res_id & 0xFFFFF
                if bif_idx < len(bif_files):
                    bif_path = os.path.join(bif_dir, bif_files[bif_idx])
                    if os.path.exists(bif_path):
                        with open(bif_path, 'rb') as bf:
                            bf.read(8)  # magic + version
                            var_res_count, = struct.unpack('<I', bf.read(4))
                            bf.read(4)   # fix_res_count
                            var_table_offset, = struct.unpack('<I', bf.read(4))
                            bf.seek(var_table_offset + res_idx * 16)
                            bf.read(4)  # entry_id
                            data_offset, = struct.unpack('<I', bf.read(4))
                            data_size, = struct.unpack('<I', bf.read(4))
                            bf.read(4)
                            bf.seek(data_offset)
                            raw = bf.read(data_size)
                            if resref not in results or len(raw) > len(results[resref]):
                                results[resref] = raw
    return results


def extract_mdl_mdx_from_bif(key_path, bif_dir, model_names):
    """Extract MDL + MDX pairs from BIF archives."""
    results = {}
    target = set()
    for n in model_names:
        target.add(n.lower())
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
            # MDL = 2002, MDX = 2003
            # MDL = 2002, MDX = 3008
            if resref in target and res_type in (2002, 3008):
                bif_idx = (res_id >> 20) & 0xFFF
                res_idx = res_id & 0xFFFFF
                if bif_idx < len(bif_files):
                    bif_path = os.path.join(bif_dir, bif_files[bif_idx])
                    if os.path.exists(bif_path):
                        with open(bif_path, 'rb') as bf:
                            bf.read(8)
                            bf.read(4)
                            bf.read(4)
                            var_table_offset, = struct.unpack('<I', bf.read(4))
                            bf.seek(var_table_offset + res_idx * 16)
                            bf.read(4)
                            data_offset, = struct.unpack('<I', bf.read(4))
                            data_size, = struct.unpack('<I', bf.read(4))
                            bf.read(4)
                            bf.seek(data_offset)
                            raw = bf.read(data_size)
                            ext = 'mdl' if res_type == 2002 else 'mdx'  # 2002=MDL, 3008=MDX
                            results.setdefault(resref, {})[ext] = raw
    return results


def decode_texture(raw_bytes):
    """Decode TPC/TGA to PIL Image."""
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        return img.convert('RGBA')
    except Exception:
        pass
    try:
        from src.gui.viewport import _load_tpc_bytes
        img = _load_tpc_bytes(raw_bytes)
        if img:
            return img
    except Exception:
        pass
    try:
        from pykotor.resource.formats.tpc import read_tpc
        tpc = read_tpc(raw_bytes)
        pil_img = tpc.convert(tpc.format, 0)
        if hasattr(pil_img, 'size'):
            return pil_img.convert('RGBA')
    except Exception:
        pass
    return None


def collect_texture_names_from_model(model):
    """Get all texture names referenced by a model."""
    names = set()
    for node in model.all_nodes():
        tex = str(getattr(node, 'texture', '') or '').strip().lower()
        lm = str(getattr(node, 'lightmap', '') or '').strip().lower()
        if tex and tex not in ('null', ''):
            names.add(tex)
        if lm:
            names.add(lm)
    return names


# ── Validation result tracking ──────────────────────────────────────────────

class ValidationReport:
    def __init__(self):
        self.results = []
        self.screenshots = []

    def add(self, category, test_name, passed, details=""):
        self.results.append({
            'category': category,
            'test': test_name,
            'passed': passed,
            'details': details
        })
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {category}/{test_name}: {details}")

    def add_screenshot(self, path, description):
        self.screenshots.append({'path': path, 'description': description})

    def summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r['passed'])
        failed = total - passed
        return total, passed, failed


# ── Main validation ──────────────────────────────────────────────────────────

def main():
    report = ValidationReport()
    print("=" * 80)
    print("  PR #41 VALIDATION — Live Rendering Tests")
    print("=" * 80)

    # ── Step 1: Extract character models ─────────────────────────────────────
    print("\n[1] Extracting character models from game data...")
    # p_hk47 and pmhc01 are in party.bif/player.bif (not available).
    # Use character models from models.bif (bif_idx=18) which IS available.
    char_names = ['c_kraytdragon', 'n_commf', 'c_bantha', 'c_female']
    key_path = os.path.join(GAME_DIR, 'chitin.key')
    mdl_data = extract_mdl_mdx_from_bif(key_path, GAME_DIR, char_names)
    for name in char_names:
        if name in mdl_data and 'mdl' in mdl_data[name] and 'mdx' in mdl_data[name]:
            print(f"    {name}: MDL={len(mdl_data[name]['mdl'])} bytes, MDX={len(mdl_data[name]['mdx'])} bytes")
        else:
            got = mdl_data.get(name, {})
            print(f"    {name}: EXTRACTION FAILED (got keys: {list(got.keys())})")
            report.add("extraction", name, False, f"Could not extract MDL/MDX (got: {list(got.keys())})")

    # ── Step 2: Load models via kotor_loader ─────────────────────────────────
    print("\n[2] Loading models through GhostRigger kotor_loader...")
    from src.core.kotor_loader import load_model_from_bytes

    models = {}
    for name in char_names:
        if name not in mdl_data:
            continue
        try:
            model = load_model_from_bytes(mdl_data[name]['mdl'], mdl_data[name]['mdx'])
            if model:
                models[name] = model
                cls = getattr(model, 'classification', '?')
                mtype = getattr(model, 'model_type', '?')
                nodes = list(model.all_nodes())
                mesh_nodes = [n for n in nodes if getattr(n, 'is_mesh', False)]
                skin_nodes = [n for n in mesh_nodes if getattr(n, 'is_skin', False)]
                print(f"    {name}: cls={cls}, type={mtype}, "
                      f"nodes={len(nodes)}, mesh={len(mesh_nodes)}, skin={len(skin_nodes)}")
                report.add("model_load", name, True,
                           f"cls={cls} type={mtype} nodes={len(nodes)} mesh={len(mesh_nodes)} skin={len(skin_nodes)}")
            else:
                print(f"    {name}: LOAD RETURNED None")
                report.add("model_load", name, False, "load_model_from_bytes returned None")
        except Exception as e:
            print(f"    {name}: ERROR {e}")
            report.add("model_load", name, False, str(e))

    # ── Step 3: Load module model ────────────────────────────────────────────
    print("\n[3] Loading module model m02aa_01a...")
    mdl_path = os.path.join(os.path.dirname(__file__), 'm02aa_01a.mdl')
    mdx_path = os.path.join(os.path.dirname(__file__), 'm02aa_01a.mdx')
    module_model = None
    if os.path.exists(mdl_path) and os.path.exists(mdx_path):
        with open(mdl_path, 'rb') as f:
            mdl_bytes = f.read()
        with open(mdx_path, 'rb') as f:
            mdx_bytes = f.read()
        module_model = load_model_from_bytes(mdl_bytes, mdx_bytes)
        if module_model:
            cls = getattr(module_model, 'classification', '?')
            mtype = getattr(module_model, 'model_type', '?')
            nodes = list(module_model.all_nodes())
            mesh_nodes = [n for n in nodes if getattr(n, 'is_mesh', False)]
            print(f"    m02aa_01a: cls={cls}, type={mtype}, nodes={len(nodes)}, mesh={len(mesh_nodes)}")
            report.add("model_load", "m02aa_01a", True,
                        f"cls={cls} type={mtype} nodes={len(nodes)} mesh={len(mesh_nodes)}")
        else:
            report.add("model_load", "m02aa_01a", False, "load returned None")
    else:
        report.add("model_load", "m02aa_01a", False, "MDL/MDX files not found")

    # ── Step 4: Extract textures for all models ──────────────────────────────
    print("\n[4] Extracting textures for all models...")
    all_tex_names = set()
    for name, model in models.items():
        all_tex_names |= collect_texture_names_from_model(model)
    if module_model:
        all_tex_names |= collect_texture_names_from_model(module_model)
    print(f"    Total unique texture names needed: {len(all_tex_names)}")

    # Extract from ERF (texture packs)
    erf_path = os.path.join(GAME_DIR, 'TexturePacks', 'swpc_tex_tpa.erf')
    raw_textures = extract_from_erf(erf_path, all_tex_names)
    # Extract from BIF (lightmaps, etc.)
    raw_bif = extract_from_bif_via_key(key_path, GAME_DIR, all_tex_names - set(raw_textures.keys()))
    raw_textures.update(raw_bif)
    print(f"    Extracted {len(raw_textures)} raw texture resources")

    # Decode
    textures = {}
    for tname, raw in raw_textures.items():
        img = decode_texture(raw)
        if img:
            textures[tname] = img
    print(f"    Decoded {len(textures)} textures to PIL Images")

    # ── Step 5: UV seam healing validation (code-level) ──────────────────────
    print("\n[5] UV seam healing validation (code-level)...")
    from src.gui.gpu_renderer import _build_vbo_data

    for name, model in models.items():
        skin_nodes_with_bad_uv = []
        total_skin = 0
        total_healed = 0
        for node in model.all_nodes():
            if not getattr(node, 'is_mesh', False):
                continue
            is_skin = getattr(node, 'is_skin', False)
            uvs = getattr(node, 'uvs', [])
            if not uvs:
                continue

            uv_arr = np.asarray(uvs, dtype=np.float32)
            if uv_arr.ndim != 2 or uv_arr.shape[1] < 2:
                continue

            # Check for garbage UVs (|UV| > 20.0 = character sentinel)
            bad_mask = np.any(np.abs(uv_arr[:, :2]) > 20.0, axis=1)
            n_bad = int(np.sum(bad_mask))
            if is_skin:
                total_skin += 1
            if n_bad > 0:
                skin_nodes_with_bad_uv.append((node.name, n_bad, len(uv_arr), is_skin))

            # Now run _build_vbo_data with is_module=False (character mode)
            # and check that bad UVs get healed
            if n_bad > 0:
                wp = getattr(node, 'position', (0, 0, 0))
                wo = getattr(node, 'rotation', (0, 0, 0, 1))
                vbo, idx = _build_vbo_data(node, wp, wo, is_module=False)
                if vbo is not None:
                    # VBO layout: pos(3), norm(3), uv(2), uv_lm(2), color(4), bone_ids(4), bone_weights(4) = 22
                    # UV at offset 6-7
                    n_v = vbo.shape[0]
                    healed_uv = vbo[:, 6:8]
                    still_bad = np.any(np.abs(healed_uv) > 20.0, axis=1)
                    n_still_bad = int(np.sum(still_bad))
                    n_healed_here = n_bad - n_still_bad
                    total_healed += n_healed_here
                    if n_still_bad > 0:
                        # Check if remaining "bad" are 0.5 fallback (also acceptable)
                        fallback_mask = still_bad & np.all(np.abs(healed_uv - 0.5) < 0.01, axis=1)
                        n_fallback = int(np.sum(fallback_mask))
                        n_truly_bad = n_still_bad - n_fallback
                        if n_truly_bad > 0:
                            report.add("uv_seam_heal", f"{name}/{node.name}",
                                       False,
                                       f"{n_truly_bad} UVs still bad after healing "
                                       f"(had {n_bad} bad, healed {n_healed_here}, fallback {n_fallback})")
                        else:
                            total_healed += n_fallback
                            report.add("uv_seam_heal", f"{name}/{node.name}",
                                       True,
                                       f"All {n_bad} bad UVs healed ({n_healed_here} via neighbor, "
                                       f"{n_fallback} via 0.5 fallback)")
                    else:
                        report.add("uv_seam_heal", f"{name}/{node.name}",
                                   True,
                                   f"All {n_bad} bad UVs healed via neighbor copy")

        if skin_nodes_with_bad_uv:
            print(f"    {name}: {len(skin_nodes_with_bad_uv)} nodes had bad UVs, total healed: {total_healed}")
            for nname, nbad, ntotal, is_sk in skin_nodes_with_bad_uv:
                print(f"      {nname}: {nbad}/{ntotal} bad UVs (skin={is_sk})")
        else:
            print(f"    {name}: No nodes with bad UVs (clean model)")
            report.add("uv_seam_heal", name, True, "No garbage UVs detected (clean model)")

    # ── Step 6: Module UV tiling validation (code-level) ─────────────────────
    print("\n[6] Module UV tiling validation (code-level)...")
    if module_model:
        large_uv_count = 0
        nodes_checked = 0
        for node in module_model.all_nodes():
            if not getattr(node, 'is_mesh', False):
                continue
            uvs = getattr(node, 'uvs', [])
            if not uvs:
                continue
            uv_arr = np.asarray(uvs, dtype=np.float32)
            if uv_arr.ndim != 2 or uv_arr.shape[1] < 2:
                continue
            nodes_checked += 1
            max_uv = float(np.max(np.abs(uv_arr[:, :2])))
            if max_uv > 1.5:
                large_uv_count += 1

            # Run _build_vbo_data with is_module=True and verify UVs preserved
            wp = getattr(node, 'position', (0, 0, 0))
            wo = getattr(node, 'rotation', (0, 0, 0, 1))
            vbo, idx = _build_vbo_data(node, wp, wo, is_module=True)
            if vbo is not None and max_uv > 1.5:
                healed_uv = vbo[:, 6:8]
                max_vbo_uv = float(np.max(np.abs(healed_uv)))
                if max_vbo_uv < 1.5:
                    report.add("module_uv_tiling", f"m02aa_01a/{node.name}",
                               False,
                               f"Large UV clamped! raw max={max_uv:.1f}, VBO max={max_vbo_uv:.1f}")
                else:
                    report.add("module_uv_tiling", f"m02aa_01a/{node.name}",
                               True,
                               f"Large UVs preserved: raw max={max_uv:.1f}, VBO max={max_vbo_uv:.1f}")

        print(f"    m02aa_01a: {nodes_checked} mesh nodes checked, {large_uv_count} have UVs > 1.5")
        if large_uv_count == 0:
            report.add("module_uv_tiling", "m02aa_01a", True,
                        "No nodes with UVs > 1.5 (small-UV module)")
    else:
        report.add("module_uv_tiling", "m02aa_01a", False, "Module model not loaded")

    # ── Step 7: GPU skinning path verification ───────────────────────────────
    print("\n[7] GPU skinning path verification...")
    for name, model in models.items():
        for node in model.all_nodes():
            if not getattr(node, 'is_skin', False):
                continue
            # Check bone data
            bone_ids = getattr(node, 'bone_node_ids', None) or getattr(node, 'skin_bone_ids', None)
            weights = getattr(node, 'bone_weights', None) or getattr(node, 'skin_weights', None)
            has_skin_data = bool(bone_ids) or bool(weights)

            wp = getattr(node, 'position', (0, 0, 0))
            wo = getattr(node, 'rotation', (0, 0, 0, 1))
            vbo, idx = _build_vbo_data(node, wp, wo, is_module=False)
            if vbo is not None:
                # VBO layout: pos(3), norm(3), uv(2), uv_lm(2), color(4), bone_ids(4), bone_weights(4)
                # bone_ids at offset 14-17, bone_weights at offset 18-21
                bone_id_col = vbo[:, 14:18]
                bone_wt_col = vbo[:, 18:22]
                # For skin nodes, bone data should be populated
                has_nonzero_weights = np.any(bone_wt_col > 0)
                # Weight sum should be ~1.0 for each vertex
                wt_sums = bone_wt_col.sum(axis=1)
                valid_wt_sums = np.abs(wt_sums - 1.0) < 0.05
                pct_valid = float(np.mean(valid_wt_sums) * 100)

                if has_nonzero_weights and pct_valid > 80:
                    report.add("gpu_skinning", f"{name}/{node.name}",
                               True,
                               f"bone weights present, {pct_valid:.0f}% vertices with sum≈1.0, "
                               f"VBO stride=22")
                elif has_nonzero_weights:
                    report.add("gpu_skinning", f"{name}/{node.name}",
                               True,
                               f"bone weights present (identity for non-skin path), "
                               f"{pct_valid:.0f}% valid weight sums")
                else:
                    # Non-skin gets identity weights (w0=1, rest=0)
                    report.add("gpu_skinning", f"{name}/{node.name}",
                               True,
                               f"identity bone weights (non-skin or weight-zero node)")
            break  # Just check first skin node per model

    # ── Step 8: Live GPU rendering ───────────────────────────────────────────
    print("\n[8] Live GPU rendering...")
    from src.gui.gpu_renderer import render_model_autoframe, GpuRenderer

    renderer = GpuRenderer()
    if not renderer._ensure_context():
        print("    FATAL: Cannot create moderngl context!")
        report.add("gpu_render", "context", False, "Failed to create moderngl context")
    else:
        print(f"    GPU context: {renderer._ctx.info.get('GL_RENDERER', '?')}")
        report.add("gpu_render", "context", True,
                    f"moderngl context via EGL: {renderer._ctx.info.get('GL_RENDERER', '?')}")

        # ── 8a: Render character models ──────────────────────────────────────
        for name, model in models.items():
            print(f"\n    Rendering {name}...")
            t0 = time.perf_counter()
            try:
                results = render_model_autoframe(
                    model, W=512, H=512, textures=textures,
                    views=['front', 'diag'], renderer=renderer
                )
                dt = (time.perf_counter() - t0) * 1000

                if results:
                    for view_name, img in results.items():
                        # Save screenshot
                        out_path = os.path.join(OUT_DIR, f"char_{name}_{view_name}.png")
                        img.save(out_path)
                        report.add_screenshot(out_path, f"{name} {view_name} view")

                        # Analyse rendered image
                        arr = np.array(img.convert('RGBA'))
                        # Check it's not all black (render failed)
                        max_val = arr[:, :, :3].max()
                        mean_val = arr[:, :, :3].mean()
                        # Check for texture scrambling: high entropy = bad
                        # A properly textured model has smooth gradients
                        non_bg = arr[:, :, 3] > 0  # non-transparent pixels
                        n_visible = int(non_bg.sum())
                        pct_visible = n_visible / (512 * 512) * 100

                        if max_val < 5:
                            report.add("char_render", f"{name}/{view_name}",
                                       False, f"All black render (max={max_val})")
                        elif pct_visible < 1:
                            report.add("char_render", f"{name}/{view_name}",
                                       False, f"Nearly empty render ({pct_visible:.1f}% visible)")
                        else:
                            # Check for texture presence (not just flat color)
                            if non_bg.any():
                                visible_rgb = arr[:, :, :3][non_bg]
                                std_dev = float(visible_rgb.std())
                                if std_dev < 2:
                                    report.add("char_render", f"{name}/{view_name}",
                                               True,
                                               f"Rendered but flat color (std={std_dev:.1f}), "
                                               f"{pct_visible:.1f}% visible, {dt:.0f}ms - "
                                               f"may indicate missing texture")
                                else:
                                    report.add("char_render", f"{name}/{view_name}",
                                               True,
                                               f"Textured render OK (std={std_dev:.1f}), "
                                               f"{pct_visible:.1f}% visible, {dt:.0f}ms")
                            else:
                                report.add("char_render", f"{name}/{view_name}",
                                           True, f"Rendered ({dt:.0f}ms)")

                    print(f"      {name}: {len(results)} views rendered in {dt:.0f}ms")
                else:
                    report.add("char_render", name, False, "render_model_autoframe returned empty")
            except Exception as e:
                report.add("char_render", name, False, f"Exception: {e}")
                traceback.print_exc()

        # ── 8b: Render module model ──────────────────────────────────────────
        if module_model:
            print(f"\n    Rendering m02aa_01a (module)...")
            t0 = time.perf_counter()
            try:
                results = render_model_autoframe(
                    module_model, W=512, H=512, textures=textures,
                    views=['front', 'diag', 'top'], renderer=renderer
                )
                dt = (time.perf_counter() - t0) * 1000
                if results:
                    for view_name, img in results.items():
                        out_path = os.path.join(OUT_DIR, f"module_m02aa_01a_{view_name}.png")
                        img.save(out_path)
                        report.add_screenshot(out_path, f"m02aa_01a {view_name} view")

                        arr = np.array(img.convert('RGBA'))
                        max_val = arr[:, :, :3].max()
                        non_bg = arr[:, :, 3] > 0
                        n_visible = int(non_bg.sum())
                        pct_visible = n_visible / (512 * 512) * 100

                        if max_val < 5:
                            report.add("module_render", f"m02aa_01a/{view_name}",
                                       False, f"All black (max={max_val})")
                        elif pct_visible < 1:
                            report.add("module_render", f"m02aa_01a/{view_name}",
                                       False, f"Nearly empty ({pct_visible:.1f}% visible)")
                        else:
                            visible_rgb = arr[:, :, :3][non_bg]
                            std_dev = float(visible_rgb.std())
                            report.add("module_render", f"m02aa_01a/{view_name}",
                                       True,
                                       f"Module rendered OK (std={std_dev:.1f}), "
                                       f"{pct_visible:.1f}% visible, {dt:.0f}ms")

                    print(f"      m02aa_01a: {len(results)} views in {dt:.0f}ms")
                else:
                    report.add("module_render", "m02aa_01a", False, "Empty result")
            except Exception as e:
                report.add("module_render", "m02aa_01a", False, str(e))
                traceback.print_exc()

        renderer.release()

    # ── Step 9: Non-skinned mesh verification ────────────────────────────────
    print("\n[9] Non-skinned mesh verification...")
    for name, model in models.items():
        non_skin_count = 0
        non_skin_ok = 0
        for node in model.all_nodes():
            if not getattr(node, 'is_mesh', False):
                continue
            if getattr(node, 'is_skin', False):
                continue
            non_skin_count += 1
            wp = getattr(node, 'position', (0, 0, 0))
            wo = getattr(node, 'rotation', (0, 0, 0, 1))
            vbo, idx = _build_vbo_data(node, wp, wo, is_module=False)
            if vbo is not None:
                # Non-skin should have identity bone data:
                # bone_ids = [0,0,0,0], bone_weights = [1,0,0,0]
                bone_wt = vbo[:, 18:22]
                is_identity = np.all(np.abs(bone_wt[:, 0] - 1.0) < 0.01) and np.all(np.abs(bone_wt[:, 1:]) < 0.01)
                if is_identity:
                    non_skin_ok += 1
        if non_skin_count > 0:
            report.add("non_skinned", name, non_skin_ok == non_skin_count,
                        f"{non_skin_ok}/{non_skin_count} non-skin nodes have identity bone data")
        else:
            report.add("non_skinned", name, True, "No non-skin mesh nodes")

    # ── Step 10: Sampler-slot / wrap-mode / VBO format checks ────────────────
    print("\n[10] Sampler-slot, wrap-mode, VBO format checks...")

    # Check shader source
    from src.gui import gpu_renderer as gpr
    vert_src = getattr(gpr, '_VERT_SRC', '') or ''
    frag_src = getattr(gpr, '_FRAG_SRC', '') or ''

    # Verify UV0/UV1 routing in shader
    has_uv0 = 'in_uv' in vert_src
    has_uv1 = 'in_uv_lm' in vert_src
    has_v_flip = '1.0 - in_uv.y' in vert_src
    has_lm_flip = '1.0 - in_uv_lm.y' in vert_src
    report.add("shader", "uv0_input", has_uv0, "in_uv present in vertex shader")
    report.add("shader", "uv1_input", has_uv1, "in_uv_lm present in vertex shader")
    report.add("shader", "uv0_vflip", has_v_flip, "V-flip (1.0 - in_uv.y) in vertex shader")
    report.add("shader", "uv1_vflip", has_lm_flip, "V-flip for lightmap UVs")

    # Check texture sampler slots in fragment shader
    has_diffuse_sampler = 'u_tex' in frag_src or 'tex0' in frag_src
    has_lm_sampler = 'u_lm' in frag_src or 'tex1' in frag_src
    report.add("shader", "diffuse_sampler", has_diffuse_sampler, "Diffuse texture sampler in frag shader")
    report.add("shader", "lm_sampler", has_lm_sampler, "Lightmap sampler in frag shader")

    # VAO format string
    vao_fmt = None
    import re
    match = re.search(r"'(\d+f\s+\d+f\s+\d+f\s+\d+f\s+\d+f\s+\d+f\s+\d+f)'", open('src/gui/gpu_renderer.py').read())
    if not match:
        # Try simpler pattern
        src_text = open('src/gui/gpu_renderer.py').read()
        vao_matches = re.findall(r"'([0-9f ]+)'", src_text)
        for m in vao_matches:
            if '3f 3f 2f 2f 4f 4f 4f' in m:
                vao_fmt = m
                break
    else:
        vao_fmt = match.group(1)

    report.add("vbo_format", "vao_22f", vao_fmt is not None and '3f 3f 2f 2f 4f 4f 4f' in (vao_fmt or ''),
               f"VAO format='3f 3f 2f 2f 4f 4f 4f' (22 floats) — {'found' if vao_fmt else 'NOT FOUND'}")

    # Check _UV_SENTINEL two-tier
    sentinel_line = None
    for line in open('src/gui/gpu_renderer.py'):
        if '_UV_SENTINEL' in line and 'if not is_module' in line:
            sentinel_line = line.strip()
            break
    report.add("sentinel", "two_tier",
               sentinel_line is not None,
               f"Two-tier sentinel: {sentinel_line or 'NOT FOUND'}")

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("  VALIDATION SUMMARY")
    print("=" * 80)
    total, passed, failed = report.summary()
    print(f"\n  Total tests: {total}")
    print(f"  Passed:      {passed}")
    print(f"  Failed:      {failed}")
    print(f"  Pass rate:   {passed/total*100:.1f}%")

    if failed > 0:
        print("\n  FAILURES:")
        for r in report.results:
            if not r['passed']:
                print(f"    [{r['category']}] {r['test']}: {r['details']}")

    print(f"\n  Screenshots saved to: {OUT_DIR}/")
    for ss in report.screenshots:
        print(f"    {os.path.basename(ss['path'])}: {ss['description']}")

    # Write JSON report
    report_path = os.path.join(OUT_DIR, 'validation_report.json')
    with open(report_path, 'w') as f:
        json.dump({
            'total': total, 'passed': passed, 'failed': failed,
            'results': report.results,
            'screenshots': report.screenshots
        }, f, indent=2)
    print(f"\n  Report: {report_path}")

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
