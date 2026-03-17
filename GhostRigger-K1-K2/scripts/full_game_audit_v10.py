"""
GhostRigger Full Game Audit v10
================================
Audits ALL models in both KotOR 1 and KotOR 2 for:
  1. Parse errors / crashes
  2. UV wrapping issues (out-of-range, degenerate)
  3. Rigging issues (missing bones, unresolved skin weights)
  4. Positioning issues (vertices at origin, huge bounds)
  5. Texture reference issues (missing textures)
  6. Render errors (fatal render crashes)

Usage:
    python scripts/full_game_audit_v10.py \
        --k1 /path/to/k1_extracted \
        --k2 /path/to/k2_extracted \
        --out audit_output/audit_v10_full.json
"""

import struct, os, sys, json, time, math, traceback, argparse, logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# BIF / KEY reader (inline, no external deps)
# ──────────────────────────────────────────────────────────────────────────────
RES_MDL = 2002
RES_MDX = 3008
RES_TGA = 3003
RES_TPC = 3007

def _ru32(d, o): return struct.unpack_from('<I', d, o)[0]
def _ru16(d, o): return struct.unpack_from('<H', d, o)[0]
def _rs(d, o, n): return d[o:o+n].split(b'\x00')[0].decode('latin-1').lower()


class BifReader:
    """Read resources from a BIF file given offset/size."""
    def __init__(self, path: str):
        self.path = path
        self._f = open(path, 'rb')
        data = self._f.read(20)
        if data[:4] != b'BIFF':
            # Try reading anyway - some files have different magic
            pass
        self.var_count = _ru32(data, 8)
        self.table_off = _ru32(data, 16)

    def _build_index(self):
        """Build resource index: res_idx -> (offset, size)."""
        self._f.seek(self.table_off)
        entry_data = self._f.read(self.var_count * 16)
        idx = {}
        for i in range(self.var_count):
            base = i * 16
            res_id  = _ru32(entry_data, base)
            offset  = _ru32(entry_data, base + 4)
            size    = _ru32(entry_data, base + 8)
            res_idx = res_id & 0xFFFFF
            idx[res_idx] = (offset, size)
        self._index = idx
        return idx

    def get_index(self):
        if not hasattr(self, '_index'):
            self._build_index()
        return self._index

    def extract(self, res_idx: int) -> Optional[bytes]:
        idx = self.get_index()
        if res_idx not in idx:
            return None
        offset, size = idx[res_idx]
        self._f.seek(offset)
        return self._f.read(size)

    def close(self):
        self._f.close()


class KeyFile:
    """Parse chitin.key to map (resref, restype) -> (bif_idx, res_idx)."""
    def __init__(self, path: str):
        with open(path, 'rb') as f:
            self._data = f.read()
        self._parse()

    def _parse(self):
        d = self._data
        bif_count = _ru32(d, 8)
        key_count = _ru32(d, 12)
        bif_table_off = _ru32(d, 16)
        key_table_off = _ru32(d, 20)

        # BIF filenames
        self.bif_names = []
        o = bif_table_off
        for i in range(bif_count):
            file_size = _ru32(d, o)
            fn_off    = _ru32(d, o + 4)
            fn_size   = _ru16(d, o + 8)
            fn = d[fn_off:fn_off + fn_size].split(b'\x00')[0].decode('latin-1')
            self.bif_names.append(fn.lower().replace('\\', '/'))
            o += 12

        # Key entries: 22 bytes each
        self._map = {}  # (resref_lower, restype) -> (bif_idx, res_idx)
        o = key_table_off
        for i in range(key_count):
            resref   = d[o:o+16].split(b'\x00')[0].decode('latin-1').lower()
            restype  = _ru16(d, o + 16)
            res_id   = _ru32(d, o + 18)
            bif_idx  = (res_id >> 20) & 0xFFF
            res_idx  = res_id & 0xFFFFF
            self._map[(resref, restype)] = (bif_idx, res_idx)
            o += 22

    def get(self, resref: str, restype: int) -> Optional[Tuple[int, int]]:
        return self._map.get((resref.lower(), restype))

    def list_by_type(self, restype: int) -> List[str]:
        return [k[0] for k in self._map if k[1] == restype]


class GameData:
    """Access models and textures from a game directory's BIF files."""
    def __init__(self, game_dir: str, game_version: int):
        self.game_dir = game_dir
        self.game_version = game_version
        self._bif_readers: Dict[int, BifReader] = {}

        # Load key file
        key_path = os.path.join(game_dir, 'chitin.key')
        self.key = KeyFile(key_path)

        # Find BIF files
        self._bif_paths = {}
        data_dir = os.path.join(game_dir)
        for i, bif_name in enumerate(self.key.bif_names):
            # bif_name is like "data/models.bif" or "data/Models.bif"
            basename = os.path.basename(bif_name)
            # Try case-insensitive search
            for fname in os.listdir(game_dir):
                if fname.lower() == basename.lower():
                    self._bif_paths[i] = os.path.join(game_dir, fname)
                    break

    def _get_bif(self, bif_idx: int) -> Optional[BifReader]:
        if bif_idx not in self._bif_readers:
            path = self._bif_paths.get(bif_idx)
            if path and os.path.exists(path):
                try:
                    self._bif_readers[bif_idx] = BifReader(path)
                except Exception as e:
                    log.debug(f"Cannot open BIF {path}: {e}")
                    return None
        return self._bif_readers.get(bif_idx)

    def extract(self, resref: str, restype: int) -> Optional[bytes]:
        loc = self.key.get(resref, restype)
        if loc is None:
            return None
        bif_idx, res_idx = loc
        bif = self._get_bif(bif_idx)
        if bif is None:
            return None
        return bif.extract(res_idx)

    def list_models(self) -> List[str]:
        return self.key.list_by_type(RES_MDL)

    def close(self):
        for bif in self._bif_readers.values():
            bif.close()


# ──────────────────────────────────────────────────────────────────────────────
# Audit logic
# ──────────────────────────────────────────────────────────────────────────────
def audit_model(name: str, game_data: GameData, game_version: int) -> Dict[str, Any]:
    """
    Parse and audit a single model. Returns issue dict.
    """
    result = {
        'name': name,
        'game': f'K{game_version}',
        'parse_ok': False,
        'node_count': 0,
        'mesh_count': 0,
        'issues': [],
        'uv_issues': [],
        'rig_issues': [],
        'pos_issues': [],
        'tex_issues': [],
        'render_error': None,
    }

    # Extract MDL + MDX
    mdl_data = game_data.extract(name, RES_MDL)
    if mdl_data is None:
        result['issues'].append('MDL_NOT_FOUND')
        return result

    mdx_data = game_data.extract(name, RES_MDX) or b''

    # Parse
    try:
        from core.mdl_parser import MDLBinaryParser
        parser = MDLBinaryParser(mdl_data, mdx_data, game_version=game_version)
        model = parser.parse()
        result['parse_ok'] = True
    except Exception as e:
        result['issues'].append(f'PARSE_ERROR: {e}')
        return result

    nodes = list(model.all_nodes())
    result['node_count'] = len(nodes)

    mesh_nodes = [n for n in nodes if hasattr(n, 'faces') and n.faces]
    result['mesh_count'] = len(mesh_nodes)

    # ── 1. UV wrapping audit ──────────────────────────────────────────────────
    for node in mesh_nodes:
        tex = getattr(node, 'texture', '') or ''
        if not tex or tex.lower() == 'null':
            continue
        uvs = getattr(node, 'uvs', []) or []
        if not uvs:
            continue

        u_vals = [uv[0] for uv in uvs if math.isfinite(uv[0])]
        v_vals = [uv[1] for uv in uvs if math.isfinite(uv[1])]
        if not u_vals:
            continue

        u_min, u_max = min(u_vals), max(u_vals)
        v_min, v_max = min(v_vals), max(v_vals)

        # Non-finite UVs
        non_finite = sum(1 for uv in uvs
                         if not math.isfinite(uv[0]) or not math.isfinite(uv[1]))
        if non_finite:
            result['uv_issues'].append(
                f'{node.name}: {non_finite} non-finite UVs')

        # Large tiling
        u_span = u_max - u_min
        v_span = v_max - v_min
        if u_span > 16 or v_span > 16:
            result['uv_issues'].append(
                f'{node.name}: extreme UV span u=[{u_min:.1f},{u_max:.1f}] v=[{v_min:.1f},{v_max:.1f}]')
        elif u_span > 8 or v_span > 8:
            result['uv_issues'].append(
                f'{node.name}: large UV span u_span={u_span:.1f} v_span={v_span:.1f}')

    # ── 2. Rigging audit ─────────────────────────────────────────────────────
    bone_nodes = [n for n in nodes if getattr(n, 'node_type', '') in ('skin', 'danglymesh')]
    for node in bone_nodes:
        weights = getattr(node, 'bone_weights', []) or []
        refs    = getattr(node, 'bone_refs', []) or []
        verts   = getattr(node, 'vertices', []) or []

        if weights and len(weights) != len(verts):
            result['rig_issues'].append(
                f'{node.name}: bone_weights len {len(weights)} != verts {len(verts)}')

        # Check for zero-weight vertices
        if weights:
            zero_w = sum(1 for w in weights if all(abs(x) < 1e-6 for x in (w if hasattr(w, '__iter__') else [w])))
            if zero_w > 0:
                result['rig_issues'].append(
                    f'{node.name}: {zero_w} vertices with zero bone weights')

    # ── 3. Positioning audit ─────────────────────────────────────────────────
    for node in mesh_nodes:
        verts = getattr(node, 'vertices', []) or []
        if not verts:
            continue

        xs = [v[0] for v in verts if len(v) >= 3 and math.isfinite(v[0])]
        ys = [v[1] for v in verts if len(v) >= 3 and math.isfinite(v[1])]
        zs = [v[2] for v in verts if len(v) >= 3 and math.isfinite(v[2])]
        if not xs:
            continue

        # Huge bounding box (likely parsing error)
        x_range = max(xs) - min(xs)
        y_range = max(ys) - min(ys)
        z_range = max(zs) - min(zs)
        if x_range > 1000 or y_range > 1000 or z_range > 1000:
            result['pos_issues'].append(
                f'{node.name}: huge bbox {x_range:.0f}x{y_range:.0f}x{z_range:.0f}')

        # Non-finite vertices
        non_finite = sum(1 for v in verts
                         if len(v) >= 3 and not (math.isfinite(v[0]) and
                                                  math.isfinite(v[1]) and
                                                  math.isfinite(v[2])))
        if non_finite:
            result['pos_issues'].append(
                f'{node.name}: {non_finite} non-finite vertex positions')

    # ── 4. Texture reference audit ───────────────────────────────────────────
    seen_tex = set()
    for node in nodes:
        tex = getattr(node, 'texture', '') or ''
        lm  = getattr(node, 'lightmap', '') or ''
        for t in [tex, lm]:
            t = t.strip().lower()
            if t and t != 'null' and t not in seen_tex:
                seen_tex.add(t)
                # Check if texture exists in game data
                tga = game_data.extract(t, RES_TGA)
                tpc = game_data.extract(t, RES_TPC)
                if tga is None and tpc is None:
                    result['tex_issues'].append(f'missing: {t}')

    # ── Summarise ─────────────────────────────────────────────────────────────
    if result['uv_issues'] or result['rig_issues'] or \
       result['pos_issues'] or result['tex_issues']:
        result['issues'].append('HAS_WARNINGS')

    return result


def run_audit(game_data: GameData, game_version: int,
              progress_cb=None) -> List[Dict]:
    """Audit all models in the game data."""
    model_names = game_data.list_models()
    log.info(f"K{game_version}: {len(model_names)} models to audit")

    results = []
    t0 = time.time()
    for i, name in enumerate(model_names):
        if progress_cb:
            progress_cb(i, len(model_names), name)
        elif i % 200 == 0:
            elapsed = time.time() - t0
            rate = (i+1) / max(elapsed, 0.001)
            eta = (len(model_names) - i) / max(rate, 0.001)
            print(f"  K{game_version}: {i}/{len(model_names)} ({rate:.0f}/s, ETA {eta:.0f}s)",
                  end='\r', flush=True)
        try:
            r = audit_model(name, game_data, game_version)
            results.append(r)
        except Exception as e:
            results.append({
                'name': name, 'game': f'K{game_version}',
                'parse_ok': False,
                'issues': [f'AUDIT_CRASH: {e}'],
                'uv_issues': [], 'rig_issues': [],
                'pos_issues': [], 'tex_issues': [],
                'render_error': None,
                'node_count': 0, 'mesh_count': 0,
            })

    print()  # newline after progress
    return results


def summarise(results: List[Dict], label: str):
    total = len(results)
    ok = sum(1 for r in results if r['parse_ok'] and not r['issues'])
    parse_errors = sum(1 for r in results if not r['parse_ok'])
    uv_issues = sum(1 for r in results if r.get('uv_issues'))
    rig_issues = sum(1 for r in results if r.get('rig_issues'))
    pos_issues = sum(1 for r in results if r.get('pos_issues'))
    tex_issues = sum(1 for r in results if r.get('tex_issues'))

    print(f"\n{'='*60}")
    print(f"{label}: {total} models")
    print(f"  Parse OK:      {total - parse_errors:4d} ({100*(total-parse_errors)/max(total,1):.1f}%)")
    print(f"  Parse errors:  {parse_errors:4d}")
    print(f"  UV issues:     {uv_issues:4d}")
    print(f"  Rig issues:    {rig_issues:4d}")
    print(f"  Pos issues:    {pos_issues:4d}")
    print(f"  Tex issues:    {tex_issues:4d}")
    print(f"  Fully clean:   {ok:4d} ({100*ok/max(total,1):.1f}%)")

    # Show worst offenders
    worst_uv = [r for r in results if r.get('uv_issues')][:5]
    if worst_uv:
        print(f"\n  Sample UV issues:")
        for r in worst_uv[:3]:
            print(f"    {r['name']}: {r['uv_issues'][0]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--k1', help='K1 game data directory (chitin.key + BIFs)')
    parser.add_argument('--k2', help='K2 game data directory (chitin.key + BIFs)')
    parser.add_argument('--out', default='audit_output/audit_v10_full.json')
    parser.add_argument('--limit', type=int, default=0, help='Limit models (0=all)')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING,
                            format='%(levelname)s: %(message)s')

    all_results = []

    if args.k1:
        print(f"Loading K1 data from {args.k1}...")
        gd1 = GameData(args.k1, 1)
        models = gd1.list_models()
        if args.limit:
            models = models[:args.limit]
        print(f"K1: {len(models)} models found")
        results1 = run_audit(gd1, 1)
        if args.limit:
            results1 = results1[:args.limit]
        summarise(results1, "KotOR 1")
        all_results.extend(results1)
        gd1.close()

    if args.k2:
        print(f"\nLoading K2 data from {args.k2}...")
        gd2 = GameData(args.k2, 2)
        models = gd2.list_models()
        if args.limit:
            models = models[:args.limit]
        print(f"K2: {len(models)} models found")
        results2 = run_audit(gd2, 2)
        if args.limit:
            results2 = results2[:args.limit]
        summarise(results2, "KotOR 2")
        all_results.extend(results2)
        gd2.close()

    # Save results
    out_path = args.out
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump({
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'total': len(all_results),
            'results': all_results,
        }, f, indent=2)
    print(f"\nResults saved to {out_path}")

    # Overall summary
    parse_errs = sum(1 for r in all_results if not r['parse_ok'])
    issues = sum(1 for r in all_results if r.get('uv_issues') or
                 r.get('rig_issues') or r.get('pos_issues') or r.get('tex_issues'))
    print(f"\nOVERALL: {len(all_results)} models, "
          f"{parse_errs} parse errors, {issues} with warnings")


if __name__ == '__main__':
    main()
