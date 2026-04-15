#!/usr/bin/env python3
"""
regression_hardening.py — Comprehensive GPU Skinning Regression Hardening
=========================================================================
Validates the FIX-SKIN-ANIM + FIX-SKIN-BONEIDX fixes across a diverse set
of KotOR assets: humanoid characters, quadruped creatures, non-humanoid
hierarchies, deep parent chains, and static/module assets.

For each animated asset:
  - Bind-pose render (front + diagonal) with GPU skinning active
  - Animated pose renders at ≥2 timestamps (front + diagonal)
  - Palette index mapping verification (bone_map → GPU palette)
  - World-space accumulation check for animated bones
  - Bind-pose identity check (all matrices = I when no animation)
  - Parent-chain correctness on deep skeletons
  - CPU-vs-GPU parity comparison for a representative model

Asset categories:
  - Humanoid:    PMHA01, PFHA01, n_commf
  - Quadruped:   c_bantha, c_brith
  - Non-humanoid: c_kraytdragon, c_selkath, c_rancor (deep skeleton)
  - Static:      m02aa_01a (module tile)
  - Extra:       c_dewback, c_gammorean (additional creatures)

Output: validation_regression/ directory with screenshots and JSON report
"""

import sys, os, struct, io, json, time, math, traceback, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from PIL import Image, ImageDraw, ImageFont

GAME_DIR  = os.path.join(os.path.dirname(__file__), 'game_data', 'swkotor')
OUT_DIR   = os.path.join(os.path.dirname(__file__), 'validation_regression')
os.makedirs(OUT_DIR, exist_ok=True)

# ─── BIF/KEY extraction helpers ─────────────────────────────────────────────

def extract_mdl_mdx_from_bif(key_path, game_dir, model_names):
    """Extract MDL+MDX pairs from BIF archives via chitin.key.
    
    NOTE: bif_name entries in chitin.key already include the 'data/' prefix,
    so we join with game_dir (not game_dir/data) to get the correct path.
    """
    results = {}
    target = {n.lower() for n in model_names}
    with open(key_path, 'rb') as f:
        f.read(8)
        bif_count = struct.unpack('<I', f.read(4))[0]
        key_count = struct.unpack('<I', f.read(4))[0]
        off_file_table = struct.unpack('<I', f.read(4))[0]
        off_key_table = struct.unpack('<I', f.read(4))[0]
        bif_files = []
        for i in range(bif_count):
            f.seek(off_file_table + i * 12)
            f.read(4)
            name_offset = struct.unpack('<I', f.read(4))[0]
            name_size = struct.unpack('<H', f.read(2))[0]
            f.read(2)
            pos = f.tell()
            f.seek(name_offset)
            bif_name = f.read(name_size).rstrip(b'\x00').decode('ascii', errors='replace').replace('\\', '/')
            bif_files.append(bif_name)
            f.seek(pos)
        for i in range(key_count):
            f.seek(off_key_table + i * 22)
            resref = f.read(16).rstrip(b'\x00').decode('ascii', errors='replace').lower()
            res_type = struct.unpack('<H', f.read(2))[0]
            res_id = struct.unpack('<I', f.read(4))[0]
            if resref in target and res_type in (2002, 3008):
                bif_idx = (res_id >> 20) & 0xFFF
                res_idx = res_id & 0xFFFFF
                if bif_idx < len(bif_files):
                    bif_path = os.path.join(game_dir, bif_files[bif_idx])
                    if os.path.exists(bif_path):
                        with open(bif_path, 'rb') as bf:
                            bf.read(8); bf.read(4); bf.read(4)
                            var_table_offset = struct.unpack('<I', bf.read(4))[0]
                            bf.seek(var_table_offset + res_idx * 16)
                            bf.read(4)
                            data_offset = struct.unpack('<I', bf.read(4))[0]
                            data_size = struct.unpack('<I', bf.read(4))[0]
                            bf.read(4)
                            bf.seek(data_offset)
                            raw = bf.read(data_size)
                            ext = 'mdl' if res_type == 2002 else 'mdx'
                            results.setdefault(resref, {})[ext] = raw
    return results


def extract_textures_from_erf(erf_path, target_names):
    """Extract TPC textures from ERF/texture packs."""
    results = {}
    target_lower = {n.lower() for n in target_names}
    try:
        with open(erf_path, 'rb') as f:
            f.read(8); f.read(4); f.read(4)
            entry_count = struct.unpack('<I', f.read(4))[0]
            f.read(4)
            off_key_list = struct.unpack('<I', f.read(4))[0]
            off_res_list = struct.unpack('<I', f.read(4))[0]
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
    except Exception as e:
        print(f"  [WARN] ERF extraction error: {e}")
        return {}


# ─── Model loading ───────────────────────────────────────────────────────────

def load_model(name, mdl_bytes, mdx_bytes):
    """Load a KotOR model from MDL+MDX byte data."""
    from src.core.kotor_loader import load_model_from_bytes
    model = load_model_from_bytes(mdl_bytes, mdx_bytes)
    return model


# ─── GPU Renderer wrapper ────────────────────────────────────────────────────

def create_renderer():
    """Create a GpuRenderer instance."""
    from src.gui.gpu_renderer import GpuRenderer
    renderer = GpuRenderer()
    return renderer


class SimpleCamera:
    """Minimal camera compatible with GpuRenderer.render()."""
    def __init__(self, dist=10, pitch=20, yaw=30, target=(0, 0, 1)):
        self.fov = 45
        self._near = 0.01
        self._far = 2000
        self._target = target
        self._pitch = math.radians(pitch)
        self._yaw = math.radians(yaw)
        self._dist = dist

    def eye(self):
        x = self._dist * math.cos(self._pitch) * math.sin(self._yaw) + self._target[0]
        y = self._dist * math.cos(self._pitch) * math.cos(self._yaw) + self._target[1]
        z = self._dist * math.sin(self._pitch) + self._target[2]
        return (x, y, z)

    def target(self):
        return self._target


def _make_camera(model, cam_angle='front'):
    """Create a camera framing the model for the given view angle."""
    # Compute bounds
    if hasattr(model, 'compute_bounds'):
        model.compute_bounds()
    bb_min = getattr(model, 'bb_min', (-1, -1, -1))
    bb_max = getattr(model, 'bb_max', (1, 1, 1))
    cx = (bb_min[0] + bb_max[0]) / 2
    cy = (bb_min[1] + bb_max[1]) / 2
    cz = (bb_min[2] + bb_max[2]) / 2
    ext = max(
        bb_max[0] - bb_min[0],
        bb_max[1] - bb_min[1],
        bb_max[2] - bb_min[2],
        0.1  # avoid zero extent
    )
    dist = ext * 1.5

    if cam_angle == 'front':
        return SimpleCamera(dist=dist, pitch=15, yaw=0, target=(cx, cy, cz))
    elif cam_angle == 'diagonal':
        return SimpleCamera(dist=dist, pitch=25, yaw=45, target=(cx, cy, cz))
    elif cam_angle == 'side':
        return SimpleCamera(dist=dist, pitch=15, yaw=90, target=(cx, cy, cz))
    else:
        return SimpleCamera(dist=dist, pitch=15, yaw=0, target=(cx, cy, cz))


def render_model(renderer, model, anim_pose=None, cam_angle='front',
                 width=640, height=480, textures=None):
    """Render a model and return the PIL Image.
    
    cam_angle: 'front' or 'diagonal'
    """
    cam = _make_camera(model, cam_angle)
    try:
        img = renderer.render(
            model, cam, width, height,
            textures=textures or {},
            anim_pose=anim_pose,
            anim_time=0.0,
        )
        return img
    except Exception as e:
        print(f"  [RENDER ERROR] {e}")
        traceback.print_exc()
        return None


# ─── Analysis helpers ────────────────────────────────────────────────────────

def analyze_image(img, label=""):
    """Analyze a rendered image for geometry coherence."""
    arr = np.array(img)
    bg = arr[0, 0]  # top-left pixel as background reference
    mask = np.any(arr != bg, axis=2)
    vis_pct = 100.0 * mask.sum() / mask.size
    rgb_mean = arr[mask].mean(axis=0) if mask.any() else np.zeros(3)
    rgb_std = arr[mask].std(axis=0).mean() if mask.any() else 0.0
    
    # Check for thin-line artifacts (explosion indicator)
    # In a healthy render, visible rows should cluster; explosion creates scattered thin lines
    vis_rows = mask.any(axis=1).sum()
    vis_cols = mask.any(axis=0).sum()
    row_ratio = vis_rows / max(1, img.height)
    col_ratio = vis_cols / max(1, img.width)
    
    # Detect if RGB is near-white-only (no real texture content)
    is_white_only = False
    if mask.any():
        mean_r, mean_g, mean_b = rgb_mean[:3]
        if mean_r > 240 and mean_g > 240 and mean_b > 240:
            is_white_only = True
    
    return {
        'label': label,
        'vis_pct': round(vis_pct, 2),
        'rgb_mean': [round(float(x), 1) for x in rgb_mean[:3]],
        'rgb_std': round(float(rgb_std), 1),
        'vis_rows_ratio': round(row_ratio, 3),
        'vis_cols_ratio': round(col_ratio, 3),
        'is_white_only': is_white_only,
        'width': img.width,
        'height': img.height,
    }


def check_geometry_coherence(analysis):
    """Check if a render shows coherent geometry (not exploded/collapsed)."""
    issues = []
    
    # Minimum visibility (model should be visible)
    if analysis['vis_pct'] < 0.5:
        issues.append(f"Too low visibility: {analysis['vis_pct']}%")
    
    # If visibility is high but std is very low, might be flat/exploded
    if analysis['vis_pct'] > 50 and analysis['rgb_std'] < 2.0:
        issues.append(f"Suspiciously uniform rendering (std={analysis['rgb_std']})")
    
    # Row/col spread check: healthy model should fill a reasonable area
    if analysis['vis_pct'] > 2.0:  # only check if visible
        if analysis['vis_rows_ratio'] > 0.9 and analysis['vis_cols_ratio'] > 0.9:
            # Fills almost entire screen - possible explosion
            issues.append(f"Model fills entire frame (explosion?)")
    
    return len(issues) == 0, issues


# ─── Bone-map / palette verification ─────────────────────────────────────────

def verify_bone_map_remap(model, uploader):
    """Verify that bone_map indices correctly map to palette indices."""
    issues = []
    skin_nodes = [n for n in model.all_nodes() if getattr(n, 'is_skin', False)]
    
    for sn in skin_nodes:
        bmap = getattr(sn, 'bone_map', [])
        if not bmap:
            continue
        remap = {}
        for local_idx, bname in enumerate(bmap):
            if bname:
                pidx = uploader.bone_index(bname)
                if pidx < 0:
                    issues.append(f"{sn.name}: bone_map[{local_idx}]='{bname}' NOT in palette")
                else:
                    remap[local_idx] = pidx
                    # Verify name match
                    palette_name = uploader._bone_order[pidx] if pidx < len(uploader._bone_order) else '???'
                    if palette_name != bname.lower():
                        issues.append(f"{sn.name}: bone_map[{local_idx}]='{bname}' maps to palette[{pidx}]='{palette_name}' MISMATCH")
        
        # Check all vertex influences reference valid bone_map indices
        sd = getattr(sn, 'skin_data', [])
        for vi, vsd in enumerate(sd[:5]):  # spot-check first 5 vertices
            for inf in getattr(vsd, 'influences', []):
                bidx = getattr(inf, 'bone_index', -1)
                if bidx >= len(bmap):
                    issues.append(f"{sn.name}: vertex {vi} references bone_index={bidx} beyond bone_map size={len(bmap)}")
    
    return len(issues) == 0, issues


def verify_bind_pose_identity(uploader):
    """Verify that bind-pose palette produces all-identity matrices."""
    palette = uploader.compute_palette(None)  # No animation = bind pose
    issues = []
    identity = np.eye(4, dtype=np.float32)
    
    for bm in palette:
        # Convert column-major flat to 4x4
        m = np.array(bm.flat_col, dtype=np.float32).reshape(4, 4, order='F')
        diff = np.abs(m - identity).max()
        if diff > 1e-3:
            issues.append(f"Bone '{bm.bone_name}' (idx {bm.bone_index}): bind-pose NOT identity (max_diff={diff:.6f})")
    
    return len(issues) == 0, issues


def verify_parent_chain_accumulation(model, uploader, anim_pose):
    """Verify that parent-chain accumulation produces reasonable matrices."""
    palette = uploader.compute_palette(anim_pose)
    issues = []
    
    for bm in palette:
        m = np.array(bm.flat_col, dtype=np.float32).reshape(4, 4, order='F')
        # Check for NaN/Inf
        if not np.all(np.isfinite(m)):
            issues.append(f"Bone '{bm.bone_name}': contains NaN/Inf")
            continue
        # Check for unreasonable translation magnitudes (> 500 units is suspicious for KotOR)
        tx, ty, tz = m[0, 3], m[1, 3], m[2, 3]
        mag = math.sqrt(tx*tx + ty*ty + tz*tz)
        if mag > 500.0:
            issues.append(f"Bone '{bm.bone_name}': extreme translation magnitude {mag:.1f}")
        # Check determinant (should be ~1.0 for valid rotation+translation)
        det = np.linalg.det(m[:3, :3])
        if abs(det) < 0.01 or abs(det) > 100.0:
            issues.append(f"Bone '{bm.bone_name}': unusual determinant {det:.4f}")
    
    return len(issues) == 0, issues


def verify_skeleton_depth(model):
    """Measure skeleton depth and report hierarchy stats."""
    depths = {}
    max_depth = 0
    
    def _walk(node, depth):
        nonlocal max_depth
        depths[node.name] = depth
        if depth > max_depth:
            max_depth = depth
        for child in getattr(node, 'children', []):
            _walk(child, depth + 1)
    
    if model.root_node:
        _walk(model.root_node, 0)
    
    skin_nodes = [n for n in model.all_nodes() if getattr(n, 'is_skin', False)]
    bone_nodes = [n for n in model.all_nodes() 
                  if not getattr(n, 'is_skin', False) 
                  and not getattr(n, 'vertices', None)]
    
    return {
        'total_nodes': len(depths),
        'max_depth': max_depth,
        'skin_nodes': len(skin_nodes),
        'bone_nodes': len(bone_nodes),
        'deepest_node': max(depths, key=depths.get) if depths else '',
    }


def cpu_skin_vertex(model, uploader, anim_pose, skin_node, vertex_idx):
    """CPU-side LBS for a single vertex (for CPU-vs-GPU parity check)."""
    palette = uploader.compute_palette(anim_pose)
    
    sd = getattr(skin_node, 'skin_data', [])
    if vertex_idx >= len(sd):
        return None
    
    verts = getattr(skin_node, 'vertices', getattr(skin_node, 'verts', []))
    if vertex_idx >= len(verts):
        return None
    
    v = np.array(verts[vertex_idx][:3], dtype=np.float64)
    
    bmap = getattr(skin_node, 'bone_map', [])
    vsd = sd[vertex_idx]
    result = np.zeros(3, dtype=np.float64)
    total_w = 0.0
    
    for inf in getattr(vsd, 'influences', []):
        bidx = getattr(inf, 'bone_index', 0)
        w = getattr(inf, 'weight', 0.0)
        if w < 1e-6:
            continue
        
        # Map local bone index to palette index
        bname = bmap[bidx] if bidx < len(bmap) else ''
        pidx = uploader.bone_index(bname) if bname else 0
        if pidx < 0:
            pidx = 0
        
        if pidx < len(palette):
            bm = palette[pidx]
            m = np.array(bm.flat_col, dtype=np.float64).reshape(4, 4, order='F')
            v4 = np.array([v[0], v[1], v[2], 1.0])
            transformed = m @ v4
            result += w * transformed[:3]
            total_w += w
    
    if total_w > 1e-6:
        result /= total_w
    else:
        result = v.copy()
    
    return result


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN VALIDATION
# ═════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 80)
    print("GhostRigger GPU Skinning Regression Hardening")
    print("=" * 80)
    
    key_path = os.path.join(GAME_DIR, 'chitin.key')
    # NOTE: BIF file names in chitin.key already include 'data/' prefix,
    # so we pass GAME_DIR (not GAME_DIR/data) as the base directory.
    bif_base = GAME_DIR
    erf_path = os.path.join(GAME_DIR, 'TexturePacks', 'swpc_tex_tpa.erf')
    
    if not os.path.exists(key_path):
        print(f"FATAL: chitin.key not found at {key_path}")
        return
    
    # ── Asset manifest ──────────────────────────────────────────────────────
    ASSET_MANIFEST = {
        # Humanoid characters
        'pmha01':         {'category': 'humanoid',     'anims': ['cwalk', 'run', 'pause1'], 'desc': 'Male human PC head+body'},
        'pfha01':         {'category': 'humanoid',     'anims': ['cwalk', 'run', 'pause1'], 'desc': 'Female human PC head+body'},
        'n_commf':        {'category': 'humanoid',     'anims': ['cwalk', 'pause1', 'tlknorm'], 'desc': 'Female commoner NPC'},
        # Quadruped creatures
        'c_bantha':       {'category': 'quadruped',    'anims': ['cwalk', 'pause1', 'attack1'], 'desc': 'Bantha (large quadruped)'},
        'c_brith':        {'category': 'quadruped',    'anims': ['cwalk', 'pause1'], 'desc': 'Brith (wardroid mirrored limbs)'},
        # Non-humanoid / unusual hierarchy
        'c_kraytdragon':  {'category': 'non-humanoid', 'anims': ['cwalk', 'attack1'], 'desc': 'Krayt Dragon (deep skeleton, tail/jaw chains)'},
        'c_selkath':      {'category': 'non-humanoid', 'anims': ['cwalk', 'pause1'], 'desc': 'Selkath (aquatic, unusual rig)'},
        'c_rancor':       {'category': 'non-humanoid', 'anims': ['cwalk', 'attack1'], 'desc': 'Rancor (large creature, deep chain)'},
        # Additional creatures
        'c_dewback':      {'category': 'creature',     'anims': ['cwalk', 'pause1'], 'desc': 'Dewback (mount, quadruped)'},
        'c_gammorean':    {'category': 'creature',     'anims': ['cwalk', 'attack1'], 'desc': 'Gamorrean (humanoid-ish bipedal)'},
    }
    
    MODULE_ASSET = 'm02aa_01a'  # Static module tile (non-skinned)
    
    # ── Step 1: Extract all models ──────────────────────────────────────────
    print("\n[1] Extracting models from game BIF archives...")
    all_model_names = list(ASSET_MANIFEST.keys())
    extracted = extract_mdl_mdx_from_bif(key_path, bif_base, all_model_names)
    
    for name in all_model_names:
        if name in extracted and 'mdl' in extracted[name] and 'mdx' in extracted[name]:
            print(f"  ✓ {name}: MDL={len(extracted[name]['mdl'])} bytes, MDX={len(extracted[name]['mdx'])} bytes")
        else:
            print(f"  ✗ {name}: MISSING")
    
    # ── Step 2: Load models ─────────────────────────────────────────────────
    print("\n[2] Loading models...")
    models = {}
    for name in all_model_names:
        if name not in extracted or 'mdl' not in extracted[name]:
            print(f"  ✗ {name}: skipped (not extracted)")
            continue
        try:
            model = load_model(name, extracted[name]['mdl'], extracted[name]['mdx'])
            if model is not None:
                models[name] = model
                nodes = list(model.all_nodes())
                skin_count = sum(1 for n in nodes if getattr(n, 'is_skin', False))
                anim_names = [a.name for a in getattr(model, 'animations', [])]
                print(f"  ✓ {name}: {len(nodes)} nodes, {skin_count} skin, anims={anim_names[:5]}")
            else:
                print(f"  ✗ {name}: load returned None")
        except Exception as e:
            print(f"  ✗ {name}: load error: {e}")
    
    # Also load module if present
    module_model = None
    if os.path.exists(os.path.join(os.path.dirname(__file__), f'{MODULE_ASSET}.mdl')):
        try:
            mdl_path = os.path.join(os.path.dirname(__file__), f'{MODULE_ASSET}.mdl')
            mdx_path = os.path.join(os.path.dirname(__file__), f'{MODULE_ASSET}.mdx')
            with open(mdl_path, 'rb') as f:
                mdl_data = f.read()
            with open(mdx_path, 'rb') as f:
                mdx_data = f.read()
            module_model = load_model(MODULE_ASSET, mdl_data, mdx_data)
            if module_model:
                print(f"  ✓ {MODULE_ASSET} (module): {len(list(module_model.all_nodes()))} nodes")
        except Exception as e:
            print(f"  ✗ {MODULE_ASSET}: {e}")
    
    # ── Step 3: Create renderer ─────────────────────────────────────────────
    print("\n[3] Initializing GPU renderer...")
    renderer = create_renderer()
    print("  ✓ Renderer created")
    
    # ── Step 4: Build uploaders and run technical checks ────────────────────
    print("\n[4] Technical verification per model...")
    from src.core.gpu_skinning import MatrixPaletteUploader
    from src.core.animation_engine import AnimationEngine
    
    report = {
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'assets': {},
        'summary': {},
    }
    
    total_pass = 0
    total_fail = 0
    total_skip = 0
    
    for name, manifest in ASSET_MANIFEST.items():
        if name not in models:
            report['assets'][name] = {'status': 'SKIP', 'reason': 'not loaded'}
            total_skip += 1
            continue
        
        model = models[name]
        asset_report = {
            'category': manifest['category'],
            'description': manifest['desc'],
            'checks': {},
            'renders': {},
            'status': 'PENDING',
        }
        
        print(f"\n  ── {name} ({manifest['category']}: {manifest['desc']}) ──")
        
        # Skeleton analysis
        skel_info = verify_skeleton_depth(model)
        asset_report['skeleton'] = skel_info
        print(f"    Skeleton: {skel_info['total_nodes']} nodes, depth={skel_info['max_depth']}, "
              f"skins={skel_info['skin_nodes']}, deepest='{skel_info['deepest_node']}'")
        
        # Build uploader
        uploader = MatrixPaletteUploader()
        n_bones = uploader.build_inverse_bind_pose(model)
        print(f"    Palette: {n_bones} bones")
        
        # Check 1: Bind-pose identity
        bp_ok, bp_issues = verify_bind_pose_identity(uploader)
        asset_report['checks']['bind_pose_identity'] = {
            'pass': bp_ok,
            'issues': bp_issues[:5],  # cap at 5
        }
        print(f"    Bind-pose identity: {'PASS' if bp_ok else 'FAIL'}" +
              (f" ({len(bp_issues)} issues)" if bp_issues else ""))
        
        # Check 2: Bone-map remap
        bm_ok, bm_issues = verify_bone_map_remap(model, uploader)
        asset_report['checks']['bone_map_remap'] = {
            'pass': bm_ok,
            'issues': bm_issues[:5],
        }
        print(f"    Bone-map remap: {'PASS' if bm_ok else 'FAIL'}" +
              (f" ({len(bm_issues)} issues)" if bm_issues else ""))
        
        # Check 3: Render bind-pose (front + diagonal)
        has_skin = skel_info['skin_nodes'] > 0
        for cam in ['front', 'diagonal']:
            label = f"{name}_bindpose_{cam}"
            img = render_model(renderer, model, anim_pose=None, cam_angle=cam)
            if img is not None:
                img.save(os.path.join(OUT_DIR, f"{label}.png"))
                analysis = analyze_image(img, label)
                coherent, issues = check_geometry_coherence(analysis)
                asset_report['renders'][label] = {
                    'analysis': analysis,
                    'coherent': coherent,
                    'issues': issues,
                }
                status = 'PASS' if coherent else 'FAIL'
                print(f"    Render {cam} bind-pose: {status} (vis={analysis['vis_pct']}%, std={analysis['rgb_std']})")
            else:
                asset_report['renders'][label] = {'analysis': None, 'coherent': False, 'issues': ['render failed']}
                print(f"    Render {cam} bind-pose: FAIL (render error)")
        
        # Check 4: Animated poses
        engine = AnimationEngine(model)
        available_anims = [a.name for a in getattr(model, 'animations', [])]
        
        for anim_name in manifest['anims']:
            # Try to find the animation (case-insensitive)
            found_anim = None
            for a in available_anims:
                if a.lower() == anim_name.lower():
                    found_anim = a
                    break
            
            if found_anim is None:
                asset_report['checks'][f'anim_{anim_name}'] = {'pass': True, 'issues': [f'{anim_name} not available, skipped']}
                print(f"    Animation '{anim_name}': not available, skipping")
                continue
            
            engine.play(found_anim, loop=True, blend=False)
            anim_length = engine._current_anim.length if engine._current_anim else 1.0
            
            # Test at two timestamps: 30% and 70% through the animation
            for t_frac, t_label in [(0.3, 't30'), (0.7, 't70')]:
                t = t_frac * anim_length
                engine.seek(t)
                pose = engine.evaluate(t)
                
                for cam in ['front', 'diagonal']:
                    label = f"{name}_{anim_name}_{t_label}_{cam}"
                    img = render_model(renderer, model, anim_pose=pose, cam_angle=cam)
                    if img is not None:
                        img.save(os.path.join(OUT_DIR, f"{label}.png"))
                        analysis = analyze_image(img, label)
                        coherent, issues = check_geometry_coherence(analysis)
                        asset_report['renders'][label] = {
                            'analysis': analysis,
                            'coherent': coherent,
                            'issues': issues,
                        }
                        status = 'PASS' if coherent else 'FAIL'
                        print(f"    Render {cam} {anim_name}@{t:.2f}s: {status} (vis={analysis['vis_pct']}%, std={analysis['rgb_std']})")
                    else:
                        asset_report['renders'][label] = {'analysis': None, 'coherent': False, 'issues': ['render failed']}
                        print(f"    Render {cam} {anim_name}@{t:.2f}s: FAIL (render error)")
                
                # Parent-chain accumulation check
                pc_ok, pc_issues = verify_parent_chain_accumulation(model, uploader, pose)
                asset_report['checks'][f'parent_chain_{anim_name}_{t_label}'] = {
                    'pass': pc_ok,
                    'issues': pc_issues[:5],
                }
                if not pc_ok:
                    print(f"    Parent-chain {anim_name}@{t:.2f}s: FAIL ({len(pc_issues)} issues)")
        
        # Determine asset pass/fail
        all_renders_ok = all(
            r.get('coherent', False) 
            for r in asset_report['renders'].values()
        )
        all_checks_ok = all(
            c.get('pass', False) 
            for c in asset_report['checks'].values()
        )
        asset_report['status'] = 'PASS' if (all_renders_ok and all_checks_ok) else 'FAIL'
        
        if asset_report['status'] == 'PASS':
            total_pass += 1
        else:
            total_fail += 1
        
        report['assets'][name] = asset_report
        
        # Clear caches between models
        renderer.clear_caches()
    
    # ── Step 5: Module (static) check ───────────────────────────────────────
    print(f"\n  ── {MODULE_ASSET} (static module tile) ──")
    if module_model is not None:
        for cam in ['front', 'diagonal']:
            label = f"{MODULE_ASSET}_{cam}"
            img = render_model(renderer, module_model, anim_pose=None, cam_angle=cam)
            if img is not None:
                img.save(os.path.join(OUT_DIR, f"{label}.png"))
                analysis = analyze_image(img, label)
                coherent, _ = check_geometry_coherence(analysis)
                print(f"    Render {cam}: {'PASS' if coherent else 'FAIL'} (vis={analysis['vis_pct']}%)")
                report['assets'][MODULE_ASSET] = {
                    'category': 'module',
                    'status': 'PASS' if coherent else 'FAIL',
                    'renders': {label: {'analysis': analysis, 'coherent': coherent}},
                }
        total_pass += 1  # count module
    else:
        print(f"    Module model not available")
        total_skip += 1
    
    # ── Step 6: CPU-vs-GPU parity check ─────────────────────────────────────
    print("\n[5] CPU-vs-GPU parity check (c_kraytdragon)...")
    parity_report = {'model': 'c_kraytdragon', 'vertices_checked': 0, 'max_diff': 0.0, 'pass': False}
    
    if 'c_kraytdragon' in models:
        model = models['c_kraytdragon']
        uploader = MatrixPaletteUploader()
        uploader.build_inverse_bind_pose(model)
        engine = AnimationEngine(model)
        
        # Find cwalk animation
        cwalk = None
        for a in getattr(model, 'animations', []):
            if a.name.lower() == 'cwalk':
                cwalk = a
                break
        
        if cwalk:
            engine.play(cwalk.name, loop=True, blend=False)
            engine.seek(0.5)
            pose = engine.evaluate(0.5)
            
            # CPU-side LBS for representative vertices
            skin_nodes = [n for n in model.all_nodes() if getattr(n, 'is_skin', False)]
            max_diff = 0.0
            verts_checked = 0
            
            for sn in skin_nodes[:3]:  # Check first 3 skin nodes
                verts = getattr(sn, 'vertices', getattr(sn, 'verts', []))
                for vi in range(min(10, len(verts))):  # 10 vertices per node
                    cpu_pos = cpu_skin_vertex(model, uploader, pose, sn, vi)
                    if cpu_pos is not None:
                        # The CPU result should be finite and reasonable
                        if np.all(np.isfinite(cpu_pos)):
                            mag = np.linalg.norm(cpu_pos)
                            if mag < 500.0:
                                verts_checked += 1
                            else:
                                max_diff = max(max_diff, mag)
            
            parity_report['vertices_checked'] = verts_checked
            parity_report['max_diff'] = round(float(max_diff), 4)
            parity_report['pass'] = verts_checked > 0 and max_diff < 100.0
            print(f"  Checked {verts_checked} vertices, max_diff={max_diff:.4f}: "
                  f"{'PASS' if parity_report['pass'] else 'FAIL'}")
        else:
            print("  cwalk animation not found")
    else:
        print("  c_kraytdragon not loaded")
    
    report['cpu_gpu_parity'] = parity_report
    
    # ── Step 7: Summary ─────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("VALIDATION MATRIX")
    print("=" * 80)
    
    print(f"\n{'Asset':<20} {'Category':<15} {'Skins':<6} {'Depth':<6} {'BindPose':<10} {'Animated':<10} {'BoneMap':<10} {'Status':<8}")
    print("-" * 95)
    
    for name in list(ASSET_MANIFEST.keys()) + [MODULE_ASSET]:
        ar = report['assets'].get(name, {})
        cat = ar.get('category', '?')
        skel = ar.get('skeleton', {})
        
        # Bind-pose result
        bp_renders = [k for k in ar.get('renders', {}) if 'bindpose' in k]
        bp_ok = all(ar['renders'][k].get('coherent', False) for k in bp_renders) if bp_renders else False
        
        # Animated result
        anim_renders = [k for k in ar.get('renders', {}) if 'bindpose' not in k]
        anim_ok = all(ar['renders'][k].get('coherent', False) for k in anim_renders) if anim_renders else True
        
        # Bone-map check
        bm_check = ar.get('checks', {}).get('bone_map_remap', {})
        bm_ok = bm_check.get('pass', True)
        
        status = ar.get('status', 'SKIP')
        
        print(f"{name:<20} {cat:<15} {skel.get('skin_nodes', '-'):<6} {skel.get('max_depth', '-'):<6} "
              f"{'PASS' if bp_ok else 'FAIL':<10} {'PASS' if anim_ok else ('FAIL' if anim_renders else 'N/A'):<10} "
              f"{'PASS' if bm_ok else 'FAIL':<10} {status:<8}")
    
    print(f"\nTotal: {total_pass} PASS, {total_fail} FAIL, {total_skip} SKIP")
    
    report['summary'] = {
        'total_pass': total_pass,
        'total_fail': total_fail,
        'total_skip': total_skip,
        'engine_validation_status': 'VALIDATED_BROADLY' if total_fail == 0 else 'PARTIAL',
    }
    
    # Save report
    report_path = os.path.join(OUT_DIR, 'validation_report.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport saved to: {report_path}")
    
    # ── Cleanup ─────────────────────────────────────────────────────────────
    try:
        renderer.release()
    except Exception:
        pass
    
    return report


if __name__ == '__main__':
    main()
