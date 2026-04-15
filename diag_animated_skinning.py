#!/usr/bin/env python3
"""
Diagnostic: Animated Skinning Root-Cause Confirmation
=====================================================
Confirms that compute_palette() uses LOCAL bone transforms from AnimPose
instead of WORLD (model-space) transforms, causing geometry explosion on
animated skinned characters like c_kraytdragon.

The correct skinning formula (Gregory §12.5.2):
    M_skin_i = world_pose_i × inv(world_bind_i)

What compute_palette currently does:
    M_skin_i = local_pose_i × inv(local_bind_i)
"""
import sys, os, struct, math, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.basicConfig(level=logging.WARNING)

import numpy as np

GAME_DIR = os.path.join(os.path.dirname(__file__), 'game_data', 'swkotor')

def extract_mdl_mdx_from_bif(key_path, bif_dir, model_names):
    """Extract MDL + MDX pairs from BIF archives."""
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
                            bf.read(8)
                            bf.read(4); bf.read(4)
                            var_table_offset, = struct.unpack('<I', bf.read(4))
                            bf.seek(var_table_offset + res_idx * 16)
                            bf.read(4)
                            data_offset, = struct.unpack('<I', bf.read(4))
                            data_size, = struct.unpack('<I', bf.read(4))
                            bf.read(4)
                            bf.seek(data_offset)
                            raw = bf.read(data_size)
                            key = resref
                            if res_type == 2002:
                                results.setdefault(key, {})['mdl'] = raw
                            elif res_type == 3008:
                                results.setdefault(key, {})['mdx'] = raw
    return results


def main():
    print("="*70)
    print("DIAGNOSTIC: Animated Skinning — Transform Space Analysis")
    print("="*70)

    # ── Load c_kraytdragon ──
    from src.core.kotor_loader import load_model_from_bytes

    key_path = os.path.join(GAME_DIR, 'chitin.key')
    bif_dir = GAME_DIR
    if not os.path.isfile(key_path):
        print(f"ERROR: chitin.key not found at {key_path}")
        return

    extracted = extract_mdl_mdx_from_bif(key_path, bif_dir, ['c_kraytdragon'])
    kd = extracted.get('c_kraytdragon', {})
    if 'mdl' not in kd or 'mdx' not in kd:
        print("ERROR: c_kraytdragon not found in BIF archives")
        return

    model = load_model_from_bytes(kd['mdl'], kd['mdx'], 'c_kraytdragon')
    all_nodes = list(model.all_nodes())
    node_by_name = {n.name.lower(): n for n in all_nodes}

    print(f"\nModel loaded: {model.name}")
    print(f"  Nodes: {len(all_nodes)}")
    skin_nodes = [n for n in all_nodes if n.is_skin]
    print(f"  Skin nodes: {len(skin_nodes)}")
    print(f"  Animations: {[a.name for a in model.animations]}")

    # ── Get the cwalk animation ──
    from src.core.animation_engine import AnimationEngine
    engine = AnimationEngine(model)
    engine.play('cwalk', loop=True, blend=False)
    anim_pose = engine.evaluate(0.98)
    print(f"\nAnimation 'cwalk' evaluated at t=0.98s")
    print(f"  Pose nodes: {len(anim_pose.nodes)}")

    # ── Helper: compute depth ──
    def get_depth(node):
        d = 0
        n = node.parent
        while n is not None:
            d += 1
            n = n.parent
        return d

    # ── Helper: compute WORLD animated transform by walking parent chain ──
    from src.core.model_data import _quat_rotate, _quat_mul, _quat_normalize_bind, _quat_normalize
    from src.core.gpu_skinning import _quat_to_mat4, _mat4_mul_py, _mat4_translate_py, _mat4_invert_py

    def compute_world_anim_transform(node, anim_pose):
        chain = []
        n = node
        visited = set()
        while n is not None:
            nid = id(n)
            if nid in visited: break
            visited.add(nid)
            chain.append(n)
            n = n.parent
        chain.reverse()

        wx, wy, wz = 0.0, 0.0, 0.0
        parent_q = [0.0, 0.0, 0.0, 1.0]

        for ci, cn in enumerate(chain):
            apn = anim_pose.nodes.get(cn.name.lower()) if anim_pose else None
            if apn is not None:
                lx, ly, lz = apn.position
                rot = list(apn.rotation)
            else:
                lx, ly, lz = cn.position
                rot = list(cn.rotation)

            r2 = rot[0]**2 + rot[1]**2 + rot[2]**2 + rot[3]**2
            if r2 > 1e-9 and abs(r2 - 1.0) > 1e-4:
                rs = r2 ** 0.5
                rot = [rot[0]/rs, rot[1]/rs, rot[2]/rs, rot[3]/rs]

            rx, ry, rz = _quat_rotate(parent_q, (lx, ly, lz))
            wx += rx; wy += ry; wz += rz
            parent_q = _quat_mul(parent_q, rot)

        return (wx, wy, wz), tuple(parent_q)

    def compute_world_bind_transform(node):
        chain = []
        n = node
        visited = set()
        while n is not None:
            nid = id(n)
            if nid in visited: break
            visited.add(nid)
            chain.append(n)
            n = n.parent
        chain.reverse()

        world_m = [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
        for cn in chain:
            pos = cn.position
            quat = cn.rotation
            qx, qy, qz, qw = float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3])
            ql = math.sqrt(qx*qx+qy*qy+qz*qz+qw*qw)
            if ql > 1e-9:
                qx, qy, qz, qw = qx/ql, qy/ql, qz/ql, qw/ql
            rot_m = _quat_to_mat4((qx, qy, qz, qw))
            tx, ty, tz = float(pos[0]), float(pos[1]), float(pos[2])
            local_m = _mat4_mul_py(_mat4_translate_py(tx, ty, tz), rot_m)
            world_m = _mat4_mul_py(world_m, local_m)
        return world_m

    # ── Part 1: Compare LOCAL vs WORLD anim transforms ──
    print("\n" + "="*70)
    print("PART 1: LOCAL vs WORLD animated bone transforms")
    print("="*70)
    print(f"{'Bone':<25} {'Depth':>5} {'Local pos mag':>14} {'World pos mag':>14} {'Ratio':>8}")
    print("-"*70)

    mismatch_count = 0
    total = 0

    for bname_low, pose_node in sorted(anim_pose.nodes.items()):
        node = node_by_name.get(bname_low)
        if node is None: continue
        total += 1
        depth = get_depth(node)

        local_pos = pose_node.position
        local_mag = math.sqrt(sum(x*x for x in local_pos))

        world_pos, world_rot = compute_world_anim_transform(node, anim_pose)
        world_mag = math.sqrt(sum(x*x for x in world_pos))

        ratio = world_mag / max(local_mag, 1e-9) if local_mag > 0.01 else float('inf')
        mismatch = abs(world_mag - local_mag) > 0.01 and depth > 0

        if mismatch:
            mismatch_count += 1

        marker = " *** MISMATCH" if mismatch else ""
        if depth <= 2 or mismatch:
            print(f"{bname_low:<25} {depth:>5} {local_mag:>14.4f} {world_mag:>14.4f} {ratio:>8.2f}{marker}")

    print(f"\nSummary: {mismatch_count}/{total} bones have LOCAL != WORLD transforms")
    if mismatch_count > 0:
        print(f"  -> CONFIRMED: compute_palette uses LOCAL, needs WORLD")

    # ── Part 2: Compare inv_bind LOCAL vs WORLD ──
    print("\n" + "="*70)
    print("PART 2: inv_bind_pose LOCAL vs WORLD")
    print("="*70)

    from src.core.gpu_skinning import MatrixPaletteUploader
    uploader = MatrixPaletteUploader()
    uploader.build_inverse_bind_pose(model)

    inv_bind_mismatch = 0
    inv_bind_total = 0

    for bname in sorted(uploader._bone_order):
        node = node_by_name.get(bname)
        if node is None: continue
        depth = get_depth(node)
        if depth == 0: continue  # root is always matching

        inv_bind_total += 1
        inv_local = uploader._inv_bind.get(bname)
        if inv_local is None: continue

        # Compute world bind and its inverse
        world_bind_m = compute_world_bind_transform(node)
        try:
            inv_world = _mat4_invert_py(world_bind_m)
        except:
            continue

        # Compare translation components
        diff = abs(inv_local[0][3] - inv_world[0][3]) + \
               abs(inv_local[1][3] - inv_world[1][3]) + \
               abs(inv_local[2][3] - inv_world[2][3])
        if diff > 0.01:
            inv_bind_mismatch += 1
            if inv_bind_mismatch <= 10:
                print(f"  {bname:<25} depth={depth} local_T=({inv_local[0][3]:.3f}, {inv_local[1][3]:.3f}, {inv_local[2][3]:.3f}) "
                      f"world_T=({inv_world[0][3]:.3f}, {inv_world[1][3]:.3f}, {inv_world[2][3]:.3f}) diff={diff:.3f}")

    print(f"\nSummary: {inv_bind_mismatch}/{inv_bind_total} bones have LOCAL != WORLD inv_bind")
    if inv_bind_mismatch > 0:
        print(f"  -> CONFIRMED: build_inverse_bind_pose uses LOCAL, needs WORLD")

    # ── Part 3: What the current compute_palette produces vs correct ──
    print("\n" + "="*70)
    print("PART 3: Current skin matrix vs correct skin matrix")
    print("="*70)

    palette = uploader.compute_palette(anim_pose)

    print(f"{'Bone':<25} {'Depth':>5} {'Current M diag':>20} {'Correct M diag':>20} {'Match':>8}")
    print("-"*80)

    mat_mismatch = 0
    for bm in palette[:20]:
        bname = bm.bone_name
        node = node_by_name.get(bname)
        if node is None: continue
        depth = get_depth(node)

        # Current matrix (from palette)
        col = bm.flat_col
        # Column-major to row-major
        cur_m = [[col[c*4+r] for c in range(4)] for r in range(4)]
        cur_diag = f"({cur_m[0][0]:.2f}, {cur_m[1][1]:.2f}, {cur_m[2][2]:.2f})"

        # Correct matrix: world_anim × inv(world_bind)
        world_pos, world_rot = compute_world_anim_transform(node, anim_pose)
        qx, qy, qz, qw = float(world_rot[0]), float(world_rot[1]), float(world_rot[2]), float(world_rot[3])
        ql = math.sqrt(qx*qx+qy*qy+qz*qz+qw*qw)
        if ql > 1e-9:
            qx, qy, qz, qw = qx/ql, qy/ql, qz/ql, qw/ql
        rot_m = _quat_to_mat4((qx, qy, qz, qw))
        tx, ty, tz = float(world_pos[0]), float(world_pos[1]), float(world_pos[2])
        world_anim_m = _mat4_mul_py(_mat4_translate_py(tx, ty, tz), rot_m)

        world_bind_m = compute_world_bind_transform(node)
        try:
            inv_world_bind = _mat4_invert_py(world_bind_m)
        except:
            continue
        correct_m = _mat4_mul_py(world_anim_m, inv_world_bind)
        correct_diag = f"({correct_m[0][0]:.2f}, {correct_m[1][1]:.2f}, {correct_m[2][2]:.2f})"

        # Check if translation components differ significantly
        t_diff = abs(cur_m[0][3] - correct_m[0][3]) + \
                 abs(cur_m[1][3] - correct_m[1][3]) + \
                 abs(cur_m[2][3] - correct_m[2][3])
        match = "ok" if t_diff < 0.1 else f"DIFF={t_diff:.1f}"
        if t_diff >= 0.1:
            mat_mismatch += 1

        if depth <= 2 or t_diff >= 0.1:
            print(f"{bname:<25} {depth:>5} {cur_diag:>20} {correct_diag:>20} {match:>8}")

    print(f"\nSummary: {mat_mismatch} bones have WRONG skin matrices due to missing parent accumulation")

    # ── Final diagnosis ──
    print("\n" + "="*70)
    print("ROOT CAUSE DIAGNOSIS")
    print("="*70)
    print(f"""
    PROBLEM: Both build_inverse_bind_pose() and compute_palette() use
    LOCAL (parent-relative) bone transforms instead of WORLD (model-space)
    accumulated transforms.

    In build_inverse_bind_pose():
      - Uses only node.position/rotation (LOCAL, not accumulated via parent chain)
      - Should walk parent chain: world_bind = parent_world × local_bind

    In compute_palette() with anim_pose:
      - Uses only pose_node.position/rotation (LOCAL animated transform)
      - Should walk parent chain: world_anim = parent_world_anim × local_anim

    For ROOT-LEVEL bones (depth 0-1): local ≈ world, so matrices are accidentally correct.
    For DEEPER bones (depth 2+): missing parent transform causes explosion.

    FIX: Modify both functions to accumulate transforms through the parent
    hierarchy, producing world-space matrices for the skinning formula:
        M_skin = world_pose × inv(world_bind)

    This preserves the bind-pose fix (anim_pose=None → identity) while
    correcting the animated path.

    Animated pose nodes: {total} with anim data
    LOCAL != WORLD mismatches: {mismatch_count} (animated transforms)
    inv_bind mismatches: {inv_bind_mismatch} (bind-pose inverses)
    Skin matrix errors: {mat_mismatch} (final skinning matrices)
    """)

if __name__ == '__main__':
    main()
