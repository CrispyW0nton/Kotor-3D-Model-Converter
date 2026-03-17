#!/usr/bin/env python3
"""
audit_no_geometry.py  –  Identify every model that would show
"No renderable geometry – check MDL/MDX paths" in the viewport.

A model has no renderable geometry when every mesh node returns 0 vertices
after parsing.  We replicate the exact same logic used in viewport.py's
_draw_stats method.

Usage:
    cd GhostRigger-K1-K2
    python3 tools/audit_no_geometry.py
"""
import sys, os, json, time, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from resources.game_library import GameLibrary
from core.mdl_parser import MDLBinaryParser

K1_DIR = os.path.join(os.path.dirname(__file__), '..', 'game_data', 'k1_extracted')
K2_DIR = os.path.join(os.path.dirname(__file__), '..', 'game_data', 'k2_extracted')

# ── Categories of result ─────────────────────────────────────────────────────
has_geo_k1    = []   # (resref, verts, faces, textures)
has_geo_k2    = []
no_geo_k1     = []   # (resref, reason, node_count, mesh_count, face_count)
no_geo_k2     = []
errors_k1     = []   # (resref, error_msg)
errors_k2     = []
no_mdl_k1     = []   # resref  — entry exists but get_model_data returns None
no_mdl_k2     = []


def check_model(gl, entry):
    """Return (status, details_dict)"""
    try:
        mdl_data, mdx_data = gl.get_model_data(entry)
        if mdl_data is None:
            return 'no_mdl', {'reason': 'get_model_data returned None'}

        model = MDLBinaryParser(mdl_data, mdx_data or b'').parse()

        total_verts = 0
        total_faces = 0
        textures    = set()
        mesh_nodes  = list(model.mesh_nodes())

        for node in mesh_nodes:
            verts = node.vertices if hasattr(node, 'vertices') and node.vertices else []
            faces = node.faces   if hasattr(node, 'faces')    and node.faces    else []
            total_verts += len(verts)
            total_faces += len(faces)
            tex = getattr(node, 'texture', None) or getattr(node, 'texture1', None)
            if tex:
                textures.add(tex.strip().lower())

        if total_verts == 0:
            all_n = list(model.all_nodes())
            return 'no_geo', {
                'reason':     'all mesh nodes have 0 vertices',
                'node_count': len(all_n),
                'mesh_count': len(mesh_nodes),
                'face_count': total_faces,
            }

        return 'ok', {
            'verts':    total_verts,
            'faces':    total_faces,
            'textures': list(textures),
        }

    except Exception as e:
        return 'error', {'error': str(e), 'trace': traceback.format_exc()[-500:]}


def main():
    print("=== GhostRigger No-Geometry Audit ===")
    print(f"K1: {K1_DIR}")
    print(f"K2: {K2_DIR}\n")

    gl = GameLibrary()
    gl.set_k1_dir(K1_DIR)
    gl.set_k2_dir(K2_DIR)
    gl.scan(progress_cb=lambda *a: None)
    print(f"Library loaded: {len(gl.models)} models total\n")

    k1_models = [e for e in gl.models if e.game == 'K1']
    k2_models = [e for e in gl.models if e.game == 'K2']
    print(f"K1: {len(k1_models)} | K2: {len(k2_models)}\n")

    total = len(gl.models)
    t0 = time.time()

    for idx, entry in enumerate(gl.models):
        if idx % 300 == 0:
            elapsed = time.time() - t0
            print(f"  [{idx}/{total}] {elapsed:.1f}s  …  "
                  f"no_geo={len(no_geo_k1)+len(no_geo_k2)}, "
                  f"errors={len(errors_k1)+len(errors_k2)}", flush=True)

        status, details = check_model(gl, entry)
        tag = entry.game

        if status == 'ok':
            rec = (entry.resref, details['verts'], details['faces'], details['textures'])
            (has_geo_k1 if tag == 'K1' else has_geo_k2).append(rec)
        elif status == 'no_geo':
            rec = (entry.resref, details['reason'], details['node_count'],
                   details['mesh_count'], details['face_count'])
            (no_geo_k1 if tag == 'K1' else no_geo_k2).append(rec)
        elif status == 'no_mdl':
            (no_mdl_k1 if tag == 'K1' else no_mdl_k2).append(entry.resref)
        else:
            rec = (entry.resref, details['error'])
            (errors_k1 if tag == 'K1' else errors_k2).append(rec)

    elapsed = time.time() - t0
    print(f"\nAudit complete in {elapsed:.1f}s\n")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"K1  has-geometry : {len(has_geo_k1):5d}")
    print(f"K1  NO-geometry  : {len(no_geo_k1):5d}  ← show warning in viewport")
    print(f"K1  no-MDL-data  : {len(no_mdl_k1):5d}")
    print(f"K1  parse-errors : {len(errors_k1):5d}")
    print()
    print(f"K2  has-geometry : {len(has_geo_k2):5d}")
    print(f"K2  NO-geometry  : {len(no_geo_k2):5d}  ← show warning in viewport")
    print(f"K2  no-MDL-data  : {len(no_mdl_k2):5d}")
    print(f"K2  parse-errors : {len(errors_k2):5d}")

    # ── Detailed no-geo list ──────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("K1 NO-GEOMETRY MODELS (all)")
    print("=" * 60)
    for resref, reason, nc, mc, fc in sorted(no_geo_k1):
        print(f"  {resref:<35s}  nodes={nc:3d}  meshes={mc:3d}  faces={fc:5d}")

    print("\n" + "=" * 60)
    print("K2 NO-GEOMETRY MODELS (all)")
    print("=" * 60)
    for resref, reason, nc, mc, fc in sorted(no_geo_k2):
        print(f"  {resref:<35s}  nodes={nc:3d}  meshes={mc:3d}  faces={fc:5d}")

    # ── Error list ────────────────────────────────────────────────────────────
    if errors_k1 or errors_k2:
        print("\n" + "=" * 60)
        print("PARSE ERRORS (first 40)")
        print("=" * 60)
        for resref, err in (errors_k1 + errors_k2)[:40]:
            print(f"  {resref:<35s}  {err[:80]}")

    # ── No-MDL list ───────────────────────────────────────────────────────────
    if no_mdl_k1 or no_mdl_k2:
        print("\n" + "=" * 60)
        print("NO MDL DATA (first 40)")
        print("=" * 60)
        for r in (no_mdl_k1 + no_mdl_k2)[:40]:
            print(f"  {r}")

    # ── Save JSON report ──────────────────────────────────────────────────────
    report = {
        'k1_no_geo':  [{'resref': r, 'nodes': nc, 'meshes': mc, 'faces': fc}
                       for r, _, nc, mc, fc in no_geo_k1],
        'k2_no_geo':  [{'resref': r, 'nodes': nc, 'meshes': mc, 'faces': fc}
                       for r, _, nc, mc, fc in no_geo_k2],
        'k1_no_mdl':  no_mdl_k1,
        'k2_no_mdl':  no_mdl_k2,
        'k1_errors':  [{'resref': r, 'error': e} for r, e in errors_k1],
        'k2_errors':  [{'resref': r, 'error': e} for r, e in errors_k2],
        'summary': {
            'k1_has_geo': len(has_geo_k1),
            'k1_no_geo':  len(no_geo_k1),
            'k1_no_mdl':  len(no_mdl_k1),
            'k1_errors':  len(errors_k1),
            'k2_has_geo': len(has_geo_k2),
            'k2_no_geo':  len(no_geo_k2),
            'k2_no_mdl':  len(no_mdl_k2),
            'k2_errors':  len(errors_k2),
        }
    }
    out_path = os.path.join(os.path.dirname(__file__), '..', 'audit_output', 'no_geometry_audit.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nJSON report → {out_path}")


if __name__ == '__main__':
    main()
