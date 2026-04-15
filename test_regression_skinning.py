#!/usr/bin/env python3
"""
test_regression_skinning.py — Automated Regression Tests for GPU Skinning
=========================================================================
Tests the FIX-SKIN-ANIM + FIX-SKIN-BONEIDX fixes with real KotOR game
assets.  These tests validate:

1. Bind-pose palette identity:  When no animation is active, all bone
   matrices in the palette must be identity (within tolerance).

2. Bone-map remap correctness:  For every skin node, the local bone_map
   indices must map to valid entries in the DFS-ordered palette, and the
   resolved name must match.

3. Parent-chain accumulation:  Animated palette matrices must be finite,
   have reasonable translation magnitudes (<500), and determinants near 1.

4. Golden fixture:  c_kraytdragon cwalk at t=0.98s bind-pose palette
   must remain all-identity; animated palette must have ≥50 non-identity
   bones with max translation <100.

Requires game data in game_data/swkotor/ with chitin.key and data/models.bif.
Tests are skipped (not failed) if game data is unavailable.

Usage:
    python -m pytest test_regression_skinning.py -v
    python test_regression_skinning.py  # standalone
"""

import sys, os, struct, math
import pytest

_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

import numpy as np

from src.core.gpu_skinning import MatrixPaletteUploader, MAX_BONES
from src.core.model_data import KotorModel


# ─── Game data availability ─────────────────────────────────────────────────

GAME_DIR = os.path.join(os.path.dirname(__file__), 'game_data', 'swkotor')
KEY_PATH = os.path.join(GAME_DIR, 'chitin.key')
HAS_GAME_DATA = os.path.exists(KEY_PATH) and os.path.exists(os.path.join(GAME_DIR, 'data', 'models.bif'))

skip_no_game = pytest.mark.skipif(
    not HAS_GAME_DATA,
    reason="Game data not available (chitin.key or models.bif missing)"
)


# ─── BIF extraction ─────────────────────────────────────────────────────────

def extract_mdl_mdx(model_names):
    """Extract MDL+MDX pairs from chitin.key/models.bif."""
    results = {}
    target = {n.lower() for n in model_names}
    with open(KEY_PATH, 'rb') as f:
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
                    bif_path = os.path.join(GAME_DIR, bif_files[bif_idx])
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


def _load_model(name, data):
    """Load a model from extracted MDL+MDX data."""
    from src.core.kotor_loader import load_model_from_bytes
    return load_model_from_bytes(data['mdl'], data['mdx'])


# ─── Fixtures ────────────────────────────────────────────────────────────────

_model_cache = {}

def _get_model(name):
    """Cache-load a model to avoid redundant BIF extraction across tests."""
    if name not in _model_cache:
        data = extract_mdl_mdx([name])
        if name not in data or 'mdl' not in data[name]:
            _model_cache[name] = None
        else:
            _model_cache[name] = _load_model(name, data[name])
    return _model_cache[name]


# ─── Test helpers ────────────────────────────────────────────────────────────

def _palette_to_numpy(palette):
    """Convert palette list[BoneMatrix] to numpy array."""
    n = len(palette)
    arr = np.zeros((n, 4, 4), dtype=np.float32)
    for i, bm in enumerate(palette):
        for r in range(4):
            for c in range(4):
                arr[i, r, c] = bm.flat_col[c * 4 + r]  # col-major to row-major
    return arr


# ═════════════════════════════════════════════════════════════════════════════
#  TEST: Bind-Pose Palette Identity
# ═════════════════════════════════════════════════════════════════════════════

SKINNED_MODELS = ['c_kraytdragon', 'c_bantha', 'c_rancor', 'c_selkath',
                  'c_dewback', 'c_gammorean', 'n_commf', 'c_brith']

@skip_no_game
@pytest.mark.parametrize("model_name", SKINNED_MODELS)
def test_bind_pose_identity(model_name):
    """Bind-pose (no animation) palette must produce all-identity matrices."""
    model = _get_model(model_name)
    if model is None:
        pytest.skip(f"{model_name} not extractable from BIF")

    uploader = MatrixPaletteUploader()
    n_bones = uploader.build_inverse_bind_pose(model)
    assert n_bones > 0, f"No bones found in {model_name}"

    palette = uploader.compute_palette(None)  # bind pose = no animation
    identity = np.eye(4, dtype=np.float32)

    max_diff = 0.0
    worst_bone = ""
    for bm in palette:
        m = np.array(bm.flat_col, dtype=np.float32).reshape(4, 4, order='F')
        diff = np.abs(m - identity).max()
        if diff > max_diff:
            max_diff = diff
            worst_bone = bm.bone_name

    assert max_diff < 1e-3, (
        f"{model_name}: bind-pose NOT identity — worst bone '{worst_bone}' "
        f"max_diff={max_diff:.6f}"
    )


# ═════════════════════════════════════════════════════════════════════════════
#  TEST: Bone-Map Remap Correctness
# ═════════════════════════════════════════════════════════════════════════════

@skip_no_game
@pytest.mark.parametrize("model_name", SKINNED_MODELS)
def test_bone_map_remap(model_name):
    """Every bone_map entry must resolve to a valid palette entry with matching name."""
    model = _get_model(model_name)
    if model is None:
        pytest.skip(f"{model_name} not extractable from BIF")

    uploader = MatrixPaletteUploader()
    uploader.build_inverse_bind_pose(model)

    skin_nodes = [n for n in model.all_nodes() if getattr(n, 'is_skin', False)]
    assert len(skin_nodes) > 0, f"{model_name}: no skin nodes found"

    issues = []
    for sn in skin_nodes:
        bmap = getattr(sn, 'bone_map', [])
        for local_idx, bname in enumerate(bmap):
            if not bname:
                continue
            pidx = uploader.bone_index(bname)
            if pidx < 0:
                issues.append(f"{sn.name}: bone_map[{local_idx}]='{bname}' NOT in palette")
            else:
                palette_name = uploader._bone_order[pidx]
                if palette_name != bname.lower():
                    issues.append(
                        f"{sn.name}: bone_map[{local_idx}]='{bname}' → "
                        f"palette[{pidx}]='{palette_name}' NAME MISMATCH"
                    )

    assert len(issues) == 0, (
        f"{model_name}: bone_map remap issues:\n" +
        "\n".join(issues[:10])
    )


# ═════════════════════════════════════════════════════════════════════════════
#  TEST: Parent-Chain Accumulation (Animated)
# ═════════════════════════════════════════════════════════════════════════════

ANIMATED_MODELS = ['c_kraytdragon', 'c_bantha', 'c_rancor', 'c_selkath',
                   'c_dewback', 'c_gammorean']

@skip_no_game
@pytest.mark.parametrize("model_name", ANIMATED_MODELS)
def test_parent_chain_animated(model_name):
    """Animated palette matrices must be finite with reasonable magnitudes."""
    model = _get_model(model_name)
    if model is None:
        pytest.skip(f"{model_name} not extractable from BIF")

    from src.core.animation_engine import AnimationEngine
    engine = AnimationEngine(model)

    # Find first available walk/idle animation
    anims = [a.name for a in getattr(model, 'animations', [])]
    target_anim = None
    for candidate in ['cwalk', 'crun', 'cpause1', 'creadyr', 'g0a1']:
        for a in anims:
            if a.lower() == candidate.lower():
                target_anim = a
                break
        if target_anim:
            break

    if target_anim is None:
        pytest.skip(f"{model_name}: no suitable animation found (available: {anims[:5]})")

    engine.play(target_anim, loop=True, blend=False)
    anim_length = engine._current_anim.length if engine._current_anim else 1.0
    engine.seek(0.5 * anim_length)
    pose = engine.evaluate(0.5 * anim_length)

    uploader = MatrixPaletteUploader()
    uploader.build_inverse_bind_pose(model)
    palette = uploader.compute_palette(pose)

    issues = []
    for bm in palette:
        m = np.array(bm.flat_col, dtype=np.float32).reshape(4, 4, order='F')

        if not np.all(np.isfinite(m)):
            issues.append(f"'{bm.bone_name}': contains NaN/Inf")
            continue

        tx, ty, tz = m[0, 3], m[1, 3], m[2, 3]
        mag = math.sqrt(tx * tx + ty * ty + tz * tz)
        if mag > 500.0:
            issues.append(f"'{bm.bone_name}': extreme translation {mag:.1f}")

        det = np.linalg.det(m[:3, :3])
        if abs(det) < 0.01 or abs(det) > 100.0:
            issues.append(f"'{bm.bone_name}': unusual det {det:.4f}")

    assert len(issues) == 0, (
        f"{model_name} animated palette issues:\n" +
        "\n".join(issues[:10])
    )


# ═════════════════════════════════════════════════════════════════════════════
#  TEST: Golden Fixture — c_kraytdragon cwalk
# ═════════════════════════════════════════════════════════════════════════════

@skip_no_game
def test_golden_kraytdragon_cwalk():
    """c_kraytdragon cwalk golden fixture:
    - Bind-pose palette = all identity
    - Animated palette has ≥50 non-identity bones, max translation < 100
    - At least 5 skin nodes with correct bone_map remapping
    """
    model = _get_model('c_kraytdragon')
    if model is None:
        pytest.skip("c_kraytdragon not extractable")

    uploader = MatrixPaletteUploader()
    n_bones = uploader.build_inverse_bind_pose(model)
    assert n_bones == 75, f"Expected 75 bones, got {n_bones}"

    # Bind-pose identity
    bp_palette = uploader.compute_palette(None)
    identity = np.eye(4, dtype=np.float32)
    for bm in bp_palette:
        m = np.array(bm.flat_col, dtype=np.float32).reshape(4, 4, order='F')
        assert np.abs(m - identity).max() < 1e-3, f"Bone '{bm.bone_name}' not identity in bind pose"

    # Animated palette
    from src.core.animation_engine import AnimationEngine
    engine = AnimationEngine(model)
    cwalk = None
    for a in getattr(model, 'animations', []):
        if a.name.lower() == 'cwalk':
            cwalk = a
            break
    assert cwalk is not None, "cwalk animation not found"

    engine.play(cwalk.name, loop=True, blend=False)
    engine.seek(0.98)
    pose = engine.evaluate(0.98)
    anim_palette = uploader.compute_palette(pose)

    non_identity_count = 0
    max_translation = 0.0
    for bm in anim_palette:
        m = np.array(bm.flat_col, dtype=np.float32).reshape(4, 4, order='F')
        assert np.all(np.isfinite(m)), f"Bone '{bm.bone_name}' has NaN/Inf"
        diff = np.abs(m - identity).max()
        if diff > 0.01:
            non_identity_count += 1
        tx, ty, tz = m[0, 3], m[1, 3], m[2, 3]
        mag = math.sqrt(tx * tx + ty * ty + tz * tz)
        max_translation = max(max_translation, mag)

    assert non_identity_count >= 50, (
        f"Expected ≥50 non-identity bones, got {non_identity_count}"
    )
    assert max_translation < 100.0, (
        f"Max translation {max_translation:.1f} exceeds limit"
    )

    # Skin nodes and bone_map
    skin_nodes = [n for n in model.all_nodes() if getattr(n, 'is_skin', False)]
    assert len(skin_nodes) == 5, f"Expected 5 skin nodes, got {len(skin_nodes)}"

    for sn in skin_nodes:
        bmap = getattr(sn, 'bone_map', [])
        assert len(bmap) > 0, f"Skin node '{sn.name}' has empty bone_map"
        for local_idx, bname in enumerate(bmap):
            if bname:
                pidx = uploader.bone_index(bname)
                assert pidx >= 0, (
                    f"Skin '{sn.name}': bone_map[{local_idx}]='{bname}' "
                    f"not found in palette"
                )


# ═════════════════════════════════════════════════════════════════════════════
#  TEST: Skeleton Depth Diversity
# ═════════════════════════════════════════════════════════════════════════════

@skip_no_game
def test_skeleton_depth_diversity():
    """Ensure our test set covers diverse skeleton depths."""
    depths = {}
    for name in SKINNED_MODELS:
        model = _get_model(name)
        if model is None:
            continue
        max_depth = 0

        def _walk(node, d):
            nonlocal max_depth
            if d > max_depth:
                max_depth = d
            for child in getattr(node, 'children', []):
                _walk(child, d + 1)

        if model.root_node:
            _walk(model.root_node, 0)
        depths[name] = max_depth

    # We need at least 4 models loaded with depth > 4
    loaded = {k: v for k, v in depths.items() if v > 0}
    assert len(loaded) >= 4, f"Need ≥4 models, got {len(loaded)}: {loaded}"

    deep = {k: v for k, v in loaded.items() if v >= 10}
    assert len(deep) >= 2, f"Need ≥2 deep skeletons (depth≥10), got {len(deep)}: {deep}"


# ═════════════════════════════════════════════════════════════════════════════
#  TEST: CPU-side LBS Parity
# ═════════════════════════════════════════════════════════════════════════════

@skip_no_game
def test_cpu_lbs_parity():
    """CPU-side LBS on representative vertices produces finite, reasonable results."""
    model = _get_model('c_kraytdragon')
    if model is None:
        pytest.skip("c_kraytdragon not extractable")

    from src.core.animation_engine import AnimationEngine
    uploader = MatrixPaletteUploader()
    uploader.build_inverse_bind_pose(model)
    engine = AnimationEngine(model)

    cwalk = None
    for a in getattr(model, 'animations', []):
        if a.name.lower() == 'cwalk':
            cwalk = a
            break
    if cwalk is None:
        pytest.skip("cwalk not found")

    engine.play(cwalk.name, loop=True, blend=False)
    engine.seek(0.5)
    pose = engine.evaluate(0.5)
    palette = uploader.compute_palette(pose)

    skin_nodes = [n for n in model.all_nodes() if getattr(n, 'is_skin', False)]
    verts_checked = 0

    for sn in skin_nodes[:3]:
        verts = getattr(sn, 'vertices', getattr(sn, 'verts', []))
        sd = getattr(sn, 'skin_data', [])
        bmap = getattr(sn, 'bone_map', [])

        for vi in range(min(10, len(verts), len(sd))):
            v = np.array(verts[vi][:3], dtype=np.float64)
            vsd = sd[vi]
            result = np.zeros(3, dtype=np.float64)
            total_w = 0.0

            for inf in getattr(vsd, 'influences', []):
                bidx = getattr(inf, 'bone_index', 0)
                w = getattr(inf, 'weight', 0.0)
                if w < 1e-6:
                    continue
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
                assert np.all(np.isfinite(result)), f"NaN/Inf at vertex {vi} of {sn.name}"
                mag = np.linalg.norm(result)
                assert mag < 500.0, f"Extreme position {mag:.1f} at vertex {vi} of {sn.name}"
                verts_checked += 1

    assert verts_checked >= 10, f"Checked only {verts_checked} vertices (expected ≥10)"


# ═════════════════════════════════════════════════════════════════════════════
#  Standalone runner
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    if not HAS_GAME_DATA:
        print("SKIP: Game data not available")
        sys.exit(0)

    print("=" * 70)
    print("GPU Skinning Regression Tests (Real Assets)")
    print("=" * 70)

    passed = 0
    failed = 0
    skipped = 0

    test_funcs = [
        ('bind_pose_identity', SKINNED_MODELS, test_bind_pose_identity),
        ('bone_map_remap', SKINNED_MODELS, test_bone_map_remap),
        ('parent_chain_animated', ANIMATED_MODELS, test_parent_chain_animated),
    ]

    for test_name, models_list, test_func in test_funcs:
        for mn in models_list:
            try:
                test_func(mn)
                print(f"  PASS: {test_name}({mn})")
                passed += 1
            except pytest.skip.Exception as e:
                print(f"  SKIP: {test_name}({mn}): {e}")
                skipped += 1
            except AssertionError as e:
                print(f"  FAIL: {test_name}({mn}): {e}")
                failed += 1
            except Exception as e:
                print(f"  FAIL: {test_name}({mn}): {e}")
                failed += 1

    single_tests = [
        ('golden_kraytdragon_cwalk', test_golden_kraytdragon_cwalk),
        ('skeleton_depth_diversity', test_skeleton_depth_diversity),
        ('cpu_lbs_parity', test_cpu_lbs_parity),
    ]

    for test_name, test_func in single_tests:
        try:
            test_func()
            print(f"  PASS: {test_name}")
            passed += 1
        except pytest.skip.Exception as e:
            print(f"  SKIP: {test_name}: {e}")
            skipped += 1
        except AssertionError as e:
            print(f"  FAIL: {test_name}: {e}")
            failed += 1
        except Exception as e:
            print(f"  FAIL: {test_name}: {e}")
            failed += 1

    print(f"\n{'=' * 70}")
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    print(f"{'=' * 70}")
    sys.exit(1 if failed > 0 else 0)
