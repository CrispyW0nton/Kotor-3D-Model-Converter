#!/usr/bin/env python3
"""
GhostRigger Exhaustive Model-by-Model Audit
Audits ALL models in the game library, by category.
Reports parse failures, UV issues, geometry anomalies, and skin node data.
"""
import sys, os, traceback, time, json, math
sys.path.insert(0, '/home/user/webapp/GhostRigger-K1-K2')
sys.path.insert(0, '/home/user/webapp/PyKotor/Libraries/PyKotor/src')

from src.resources.game_library import GameLibrary
from src.core.mdl_parser import MDLBinaryParser

# ── Setup library ───────────────────────────────────────────────────────────
BASE = '/home/user/webapp/GhostRigger-K1-K2'
lib = GameLibrary()
lib.set_k1_dir(os.path.join(BASE, 'game_data', 'k1_extracted'))
lib.set_k2_dir(os.path.join(BASE, 'game_data', 'k2_extracted'))
lib.scan(os.path.join(BASE, 'game_data'))
all_models = lib.models
print(f"Library loaded: {len(all_models)} models", flush=True)

# ── Audit helpers ────────────────────────────────────────────────────────────
UV_SUSPICIOUS_THRESHOLD = 10.0

def audit_model(entry):
    """Return dict with audit results for one model."""
    result = {
        'resref': entry.resref,
        'game': entry.game,
        'parse_ok': False,
        'parse_error': None,
        'node_count': 0,
        'mesh_count': 0,
        'skin_count': 0,
        'tri_count': 0,
        'uv_issues': [],
        'geo_issues': [],
        'dup_names': [],
        'supermodel': '',
        'zero_vertex_meshes': 0,
        'warnings': [],
    }
    try:
        raw = lib.get_model_data(entry)
        # returns (mdl_bytes, mdx_bytes) tuple
        if not raw or not raw[0]:
            result['parse_error'] = 'no_mdl_bytes'
            return result

        mdl_b = raw[0]
        mdx_b = raw[1] if raw[1] else b''

        parser = MDLBinaryParser(mdl_b, mdx_b)
        model = parser.parse()

        result['parse_ok'] = True
        result['supermodel'] = getattr(model, 'supermodel', '') or ''

        nodes = list(model.all_nodes()) if hasattr(model, 'all_nodes') else []
        result['node_count'] = len(nodes)

        names_seen = {}
        mesh_nodes = []
        skin_nodes = []
        tri_total = 0

        for node in nodes:
            nm = getattr(node, 'name', '') or ''
            names_seen[nm] = names_seen.get(nm, 0) + 1

            # GhostRigger ModelNode uses is_mesh flag, not a .mesh sub-object
            if not getattr(node, 'is_mesh', False):
                continue

            mesh_nodes.append(node)
            vcount = len(getattr(node, 'vertices', None) or [])
            fcount = len(getattr(node, 'faces', None) or [])
            uvs = getattr(node, 'uvs', None) or []
            is_skin = bool(getattr(node, 'is_skin', False))

            if is_skin:
                skin_nodes.append(node)

            tri_total += fcount

            if vcount == 0 and fcount > 0:
                result['zero_vertex_meshes'] += 1
                result['geo_issues'].append(f"{nm}: 0 verts but {fcount} faces")

            # UV range check
            if uvs:
                u_vals = [uv[0] for uv in uvs if len(uv) >= 2]
                v_vals = [uv[1] for uv in uvs if len(uv) >= 2]
                if u_vals and v_vals:
                    u_max = max(abs(u) for u in u_vals)
                    v_max = max(abs(v) for v in v_vals)
                    if u_max > UV_SUSPICIOUS_THRESHOLD or v_max > UV_SUSPICIOUS_THRESHOLD:
                        result['uv_issues'].append(
                            f"{nm}: U_max={u_max:.1f} V_max={v_max:.1f}"
                        )

        result['mesh_count'] = len(mesh_nodes)
        result['skin_count'] = len(skin_nodes)
        result['tri_count'] = tri_total

        # Duplicate names
        dups = [nm for nm, cnt in names_seen.items() if cnt > 1 and nm]
        result['dup_names'] = dups

    except Exception as e:
        result['parse_error'] = f"{type(e).__name__}: {e}"

    return result


# ── Category selection ───────────────────────────────────────────────────────
# Audit important categories first, then cover everything
CATEGORIES = [
    ('creatures',    lambda r: r.startswith('c_')),
    ('npcs',         lambda r: r.startswith('n_')),
    ('placeables',   lambda r: r.startswith('plc_')),
    ('weapons',      lambda r: r.startswith('w_')),
    ('items',        lambda r: r.startswith('i_')),
    ('pc_models',    lambda r: r.startswith('pm')),
    ('doors',        lambda r: r.startswith('dor_')),
    ('vfx',          lambda r: r.startswith('v_')),
    ('supermodels',  lambda r: r.lower().startswith('s_')),
    ('all_other',    lambda r: True),
]

seen = set()
buckets = {}
for cat, pred in CATEGORIES:
    bucket = []
    for m in all_models:
        r = m.resref.lower()
        if m.resref not in seen and pred(r):
            bucket.append(m)
            seen.add(m.resref)
    buckets[cat] = bucket

print("\nModel counts by category:")
for cat, bucket in buckets.items():
    print(f"  {cat:20s}: {len(bucket):4d}")

# ── Run audit per category ────────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(BASE, 'audit_output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

all_results = {}
grand_parse_ok = 0
grand_parse_fail = 0
grand_uv_issues = 0
grand_geo_issues = 0

for cat, bucket in buckets.items():
    cat_results = []
    t0 = time.time()
    parse_ok = parse_fail = uv_cnt = geo_cnt = 0

    for entry in bucket:
        r = audit_model(entry)
        cat_results.append(r)
        if r['parse_ok']:
            parse_ok += 1
        else:
            parse_fail += 1
        if r['uv_issues']:
            uv_cnt += 1
        if r['geo_issues'] or r['dup_names']:
            geo_cnt += 1

    elapsed = time.time() - t0
    grand_parse_ok += parse_ok
    grand_parse_fail += parse_fail
    grand_uv_issues += uv_cnt
    grand_geo_issues += geo_cnt

    # Print summary
    print(f"\n{'='*60}")
    print(f"Category: {cat}  ({len(bucket)} models, {elapsed:.1f}s)")
    print(f"  Parse OK: {parse_ok}, Fail: {parse_fail}")
    print(f"  UV issues: {uv_cnt}, Geo/dup issues: {geo_cnt}")
    
    # Show failures
    failures = [r for r in cat_results if not r['parse_ok']]
    if failures:
        print(f"\n  PARSE FAILURES ({len(failures)}):")
        for r in failures[:10]:
            print(f"    {r['resref']:30s} -> {r['parse_error']}")
        if len(failures) > 10:
            print(f"    ... and {len(failures)-10} more")

    # Show UV issues
    uv_problems = [r for r in cat_results if r['uv_issues']]
    if uv_problems:
        print(f"\n  UV ISSUES ({len(uv_problems)}):")
        for r in uv_problems[:5]:
            print(f"    {r['resref']:30s}: {r['uv_issues'][:2]}")
        if len(uv_problems) > 5:
            print(f"    ... and {len(uv_problems)-5} more")

    # Show geo issues (excluding supermodel-inherited dups which are expected)
    real_geo = [r for r in cat_results if r['geo_issues']]
    if real_geo:
        print(f"\n  GEOMETRY ISSUES ({len(real_geo)}):")
        for r in real_geo[:5]:
            print(f"    {r['resref']:30s}: {r['geo_issues'][:2]}")
        if len(real_geo) > 5:
            print(f"    ... and {len(real_geo)-5} more")

    all_results[cat] = cat_results

    # Save per-category JSON
    out_path = os.path.join(OUTPUT_DIR, f'audit_{cat}.json')
    with open(out_path, 'w') as f:
        json.dump(cat_results, f, indent=2)
    print(f"  Saved: {out_path}")
    sys.stdout.flush()

# ── Grand totals ──────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print("GRAND TOTALS:")
print(f"  Total parse OK:    {grand_parse_ok}")
print(f"  Total parse FAIL:  {grand_parse_fail}")
print(f"  Models with UV issues:  {grand_uv_issues}")
print(f"  Models with geo issues: {grand_geo_issues}")
total = grand_parse_ok + grand_parse_fail
print(f"  Parse success rate: {100*grand_parse_ok/max(1,total):.1f}%")

# Save master summary
summary = {
    'total': total,
    'parse_ok': grand_parse_ok,
    'parse_fail': grand_parse_fail,
    'uv_issues': grand_uv_issues,
    'geo_issues': grand_geo_issues,
    'success_rate': round(100*grand_parse_ok/max(1,total), 2),
}
with open(os.path.join(OUTPUT_DIR, 'audit_summary.json'), 'w') as f:
    json.dump(summary, f, indent=2)
print(f"\nSaved: {OUTPUT_DIR}/audit_summary.json")
