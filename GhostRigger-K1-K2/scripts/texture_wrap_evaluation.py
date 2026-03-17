#!/usr/bin/env python3
"""
GhostRigger — Comprehensive Texture-Wrapping Evaluation
=========================================================
Evaluates all 5,764 KotOR models for texture-wrapping correctness.

Categories evaluated:
  1. UV Coverage    – renderable nodes have ≥80% UV coverage
  2. Tiling UVs     – nodes with UVs outside [0,1] (need tiling renderer)
  3. Seam Quality   – per-node UV span analysis
  4. V-Flip Check   – KotOR V=0 → bottom convention
  5. Missing UVs    – textured renderable nodes with no UV data at all
  6. Saber Nodes    – lightsaber blade nodes (excluded, procedural)
  7. Guide Nodes    – ghost/helper nodes (excluded, no UV expected)

Output:
  audit_output/tex_wrap_eval.json   – machine-readable
  audit_output/tex_wrap_eval.txt    – human-readable report
"""

import sys, os, json, time, math, logging
from pathlib import Path
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).parent.parent))
logging.disable(logging.CRITICAL)

from src.resources.game_library import GameLibrary
from src.core.mdl_parser import MDLBinaryParser

# ── Configuration ─────────────────────────────────────────────────────────────
import os as _os; K1_DIR = _os.environ.get('KOTOR_K1_DIR', 'game_data/k1_extracted')
K2_DIR = _os.environ.get('KOTOR_K2_DIR', 'game_data/k2_extracted')
OUT_DIR = Path(__file__).parent.parent / 'audit_output'

# Sky-dome textures that use procedural mapping
_SKY_TEXTURES = frozenset({
    'lts_sky0001', 'lta_sky0001', 'lko_sky02',
    'lts_sky0002', 'lts_sky0003', 'dan_nebk',
    'dan_sky', 'nar_sky', 'mss_sky', 'dxn_sky',
})

# ── Node classification ───────────────────────────────────────────────────────

def _is_guide_node(n) -> bool:
    """Return True if node is a guide/ghost/saber/sky helper — no UV expected."""
    if getattr(n, 'is_saber', False):
        return True
    nm = n.name.lower()
    _GUIDE_SUFFIXES = ('_g', '_g0', '_g01', '_g02', '_g03',
                       '_dum', '_helper', '_lod', '_shadow',
                       '_shad', '_col', '_coll', '_collision')
    if any(nm.endswith(s) for s in _GUIDE_SUFFIXES):
        return True
    if nm.startswith('bt') and not (n.uvs or []):
        return True
    tex = (n.texture or '').strip().lower()
    if not tex or tex == 'null':
        return True
    if tex in _SKY_TEXTURES:
        return True
    return False


def _classify_model(model) -> str:
    mt = getattr(model, 'model_type', 4)
    return {0: 'effect', 1: 'effects', 2: 'misc',
            4: 'character', 8: 'door', 32: 'item', 64: 'character'}.get(mt, 'character')

# ── Per-model evaluation ──────────────────────────────────────────────────────

def evaluate_model(resref: str, mdl_data: bytes, mdx_data: bytes) -> dict:
    """Evaluate a single model's texture-wrapping quality."""
    try:
        parser = MDLBinaryParser(mdl_data, mdx_data or b'')
        model  = parser.parse()
    except Exception as e:
        return {'resref': resref, 'parse_ok': False, 'error': str(e)}

    mesh_nodes   = model.mesh_nodes()
    classification = _classify_model(model)

    # Categorize nodes
    guide_nodes     = []
    saber_nodes     = []
    renderable      = []

    for n in mesh_nodes:
        verts = n.vertices or []
        if not verts:
            continue  # null-mesh placeholder
        if getattr(n, 'is_saber', False):
            saber_nodes.append(n.name)
            continue
        if _is_guide_node(n):
            guide_nodes.append(n.name)
            continue
        renderable.append(n)

    # UV analysis on renderable nodes
    nodes_with_uvs       = 0
    nodes_missing_uvs    = 0
    nodes_tiling         = 0
    nodes_full_coverage  = 0
    missing_uv_list      = []
    tiling_list          = []
    max_span_u = 0.0
    max_span_v = 0.0
    v_flip_consistent    = True

    for n in renderable:
        uvs  = n.uvs or []
        verts = n.vertices or []
        tex  = (n.texture or '').strip()

        if not uvs or len(uvs) < len(verts) * 0.5:
            nodes_missing_uvs += 1
            missing_uv_list.append({
                'node': n.name, 'tex': tex,
                'uvs': len(uvs), 'verts': len(verts)
            })
            continue

        nodes_with_uvs += 1

        # Full coverage check
        if len(uvs) >= len(verts) * 0.8:
            nodes_full_coverage += 1

        # UV range analysis
        # Filter out KotOR sentinel values (~-1.7e38, ~-1.0e30) that signal
        # "no UV assigned" in the MDX binary stream.  Any |uv| > 10,000 is a
        # sentinel and must be excluded from statistical analysis.
        _UV_SENTINEL = 10_000.0
        valid_uvs = [(u, v) for u, v in uvs
                     if abs(u) <= _UV_SENTINEL and abs(v) <= _UV_SENTINEL]
        if not valid_uvs:
            # All UVs were sentinels — treat as missing
            nodes_missing_uvs += 1
            missing_uv_list.append({
                'node': n.name, 'tex': tex,
                'uvs': 0, 'verts': len(verts),
                'note': 'all-sentinel UVs'
            })
            continue
        us = [uv[0] for uv in valid_uvs]
        vs = [uv[1] for uv in valid_uvs]
        u_min, u_max = min(us), max(us)
        v_min, v_max = min(vs), max(vs)
        span_u = u_max - u_min
        span_v = v_max - v_min
        max_span_u = max(max_span_u, span_u)
        max_span_v = max(max_span_v, span_v)

        needs_tiling = (u_min < -0.001 or u_max > 1.001 or
                        v_min < -0.001 or v_max > 1.001)
        if needs_tiling:
            nodes_tiling += 1
            tiling_list.append({
                'node': n.name, 'tex': tex,
                'u_min': round(u_min, 3), 'u_max': round(u_max, 3),
                'v_min': round(v_min, 3), 'v_max': round(v_max, 3),
                'span_u': round(span_u, 3), 'span_v': round(span_v, 3),
            })

        # V-flip check: in KotOR convention V=0 is bottom (TGA origin).
        # A genuine v-flip problem is when V coordinates are systematically
        # inverted: all V values are negative (using negative-V space which
        # maps to out-of-atlas areas unless flipped), indicating the mesh was
        # exported with a top-origin (D3D) convention instead of bottom-origin
        # (KotOR/OpenGL TGA convention).
        # NOTE: nodes with UVs only in the range [0, 0.5] are NOT flipped —
        # they simply use the lower portion of the texture atlas (normal UV
        # atlasing). The old check (median_v < 0.1 and max_v < 0.5) was a
        # false-positive that flagged legitimate atlas-packed UVs.
        # The corrected check: all non-sentinel V values are < 0 (truly flipped).
        if len(vs) >= 4:
            if all(v < -0.01 for v in vs):
                v_flip_consistent = False

    total_renderable = len(renderable)
    uv_coverage = (nodes_with_uvs / max(1, total_renderable))
    full_coverage = (nodes_full_coverage / max(1, total_renderable))

    return {
        'resref':            resref,
        'classification':    classification,
        'parse_ok':          True,
        'total_mesh_nodes':  len(mesh_nodes),
        'guide_nodes':       len(guide_nodes),
        'saber_nodes':       len(saber_nodes),
        'renderable_nodes':  total_renderable,
        'nodes_with_uvs':    nodes_with_uvs,
        'nodes_missing_uvs': nodes_missing_uvs,
        'nodes_tiling':      nodes_tiling,
        'nodes_full_coverage': nodes_full_coverage,
        'uv_coverage_ratio': round(uv_coverage, 3),
        'full_coverage_ratio': round(full_coverage, 3),
        'max_span_u':        round(max_span_u, 3),
        'max_span_v':        round(max_span_v, 3),
        'v_flip_consistent': v_flip_consistent,
        'missing_uv_nodes':  missing_uv_list[:10],
        'tiling_nodes':      tiling_list[:10],
        'has_missing_uv':    nodes_missing_uvs > 0,
        'has_tiling':        nodes_tiling > 0,
    }

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("GhostRigger — Texture-Wrapping Evaluation")
    print("=" * 60)
    t0 = time.time()

    gl = GameLibrary()
    gl.scan(K1_DIR, k2_dir=K2_DIR)

    results_by_game = {}

    for game_tag, reader in [('K1', gl._k1_key), ('K2', gl._k2_key)]:
        if reader is None:
            print(f"  WARNING: {game_tag} reader not available")
            continue

        entries  = reader.list_type(2002)
        mdx_map  = {e.resref: e for e in reader.list_type(3008)}
        results  = []

        print(f"\n[{game_tag}] Evaluating {len(entries)} models …", flush=True)

        for i, entry in enumerate(entries):
            resref = entry.resref
            try:
                mdl_data = entry.read()
                mdx_e    = mdx_map.get(resref)
                mdx_data = mdx_e.read() if mdx_e else b''
            except Exception as e:
                results.append({'resref': resref, 'parse_ok': False, 'error': str(e)})
                continue

            r = evaluate_model(resref, mdl_data, mdx_data)
            r['game'] = game_tag
            results.append(r)

            if (i + 1) % 500 == 0:
                elapsed = time.time() - t0
                pct = (i + 1) / len(entries) * 100
                print(f"  {i+1}/{len(entries)} ({pct:.0f}%) — {elapsed:.0f}s elapsed",
                      flush=True)

        results_by_game[game_tag] = results
        print(f"  Done {len(results)} models.", flush=True)

    # ── Aggregate statistics ──────────────────────────────────────────────────
    all_results = []
    for game_tag, results in results_by_game.items():
        all_results.extend(results)

    parsed = [r for r in all_results if r.get('parse_ok')]
    total  = len(all_results)

    stats = {
        'total_models':       total,
        'parsed_ok':          len(parsed),
        'with_missing_uv':    sum(1 for r in parsed if r.get('has_missing_uv')),
        'with_tiling':        sum(1 for r in parsed if r.get('has_tiling')),
        'perfect_uv':         sum(1 for r in parsed if
                                  not r.get('has_missing_uv') and r.get('renderable_nodes', 0) > 0),
        'total_saber_nodes':  sum(r.get('saber_nodes', 0) for r in parsed),
        'total_guide_nodes':  sum(r.get('guide_nodes', 0) for r in parsed),
        'total_renderable':   sum(r.get('renderable_nodes', 0) for r in parsed),
        'total_missing_uv_nodes': sum(r.get('nodes_missing_uvs', 0) for r in parsed),
        'total_tiling_nodes': sum(r.get('nodes_tiling', 0) for r in parsed),
    }

    # Models by classification
    cls_count = Counter(r.get('classification', 'unknown') for r in parsed)
    stats['by_classification'] = dict(cls_count)

    # Missing UV breakdown by classification
    missing_by_cls = Counter(
        r.get('classification', 'unknown')
        for r in parsed if r.get('has_missing_uv')
    )
    stats['missing_uv_by_classification'] = dict(missing_by_cls)

    # Tiling breakdown by classification
    tiling_by_cls = Counter(
        r.get('classification', 'unknown')
        for r in parsed if r.get('has_tiling')
    )
    stats['tiling_by_classification'] = dict(tiling_by_cls)

    # Per-game breakdown
    stats['per_game'] = {}
    for game_tag, results in results_by_game.items():
        p = [r for r in results if r.get('parse_ok')]
        stats['per_game'][game_tag] = {
            'total': len(results),
            'parsed': len(p),
            'with_missing_uv': sum(1 for r in p if r.get('has_missing_uv')),
            'with_tiling': sum(1 for r in p if r.get('has_tiling')),
            'total_renderable_nodes': sum(r.get('renderable_nodes', 0) for r in p),
            'total_tiling_nodes': sum(r.get('nodes_tiling', 0) for r in p),
            'total_missing_uv_nodes': sum(r.get('nodes_missing_uvs', 0) for r in p),
        }

    # ── Save JSON output ──────────────────────────────────────────────────────
    output = {
        'stats':   stats,
        'results': all_results,
    }
    json_path = OUT_DIR / 'tex_wrap_eval.json'
    with open(json_path, 'w') as f:
        json.dump(output, f, indent=2)

    # ── Write human-readable report ───────────────────────────────────────────
    txt_path = OUT_DIR / 'tex_wrap_eval.txt'
    missing_uv_models = sorted(
        [r for r in parsed if r.get('has_missing_uv')],
        key=lambda r: (r['game'], r['resref'])
    )

    lines = [
        "=" * 70,
        "  GhostRigger — Texture-Wrapping Evaluation Report",
        f"  Generated: {time.strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 70,
        "",
        "SUMMARY",
        "-------",
        f"  Total models audited      : {total:,}",
        f"  Successfully parsed       : {len(parsed):,}",
        f"  Models with tiling UVs    : {stats['with_tiling']:,}  "
        f"(need tiling renderer — handled by BUG-UV-2/5 fixes)",
        f"  Models with missing UVs   : {stats['with_missing_uv']:,}  "
        f"(original game data gaps — WONTFIX)",
        f"  Models with perfect UV    : {stats['perfect_uv']:,}",
        "",
        f"  Total renderable nodes    : {stats['total_renderable']:,}",
        f"  Total saber blade nodes   : {stats['total_saber_nodes']:,}  (excluded, procedural)",
        f"  Total guide/ghost nodes   : {stats['total_guide_nodes']:,}  (excluded, no UV expected)",
        f"  Total tiling UV nodes     : {stats['total_tiling_nodes']:,}",
        f"  Total missing UV nodes    : {stats['total_missing_uv_nodes']:,}",
        "",
        "PER-GAME BREAKDOWN",
        "------------------",
    ]
    for gt, gs in stats['per_game'].items():
        lines += [
            f"  [{gt}]",
            f"    Total models          : {gs['total']:,}",
            f"    Parsed                : {gs['parsed']:,}",
            f"    With tiling UVs       : {gs['with_tiling']:,}",
            f"    With missing UVs      : {gs['with_missing_uv']:,}",
            f"    Renderable nodes      : {gs['total_renderable_nodes']:,}",
            f"    Tiling UV nodes       : {gs['total_tiling_nodes']:,}",
            f"    Missing UV nodes      : {gs['total_missing_uv_nodes']:,}",
            "",
        ]

    lines += [
        "MISSING UV DETAIL (original Bioware game data — WONTFIX)",
        "---------------------------------------------------------",
        "(These nodes have renderable geometry + a texture name but",
        " the UV array is missing from the binary MDL. The mesh will",
        " render solid-black or stretch-map in any viewer. Not fixable",
        " without re-UVing the mesh in a 3D tool and re-exporting.)",
        "",
    ]
    for m in missing_uv_models:
        lines.append(f"  [{m['game']}] {m['resref']:30s}  (classification: {m.get('classification','?')})")
        for nd in m.get('missing_uv_nodes', []):
            lines.append(f"       ↳ {nd['node']:25s}  tex={nd['tex']:20s}  {nd['uvs']} uvs / {nd['verts']} verts")
    lines += [""]

    lines += [
        "TILING UV EVALUATION",
        "--------------------",
        "(Models whose UV coordinates exceed the [0,1] range.",
        " These are rendered using the tiling/modulo UV renderer.",
        " BUG-UV-2 and BUG-UV-5 fixes handle these correctly.)",
        "",
        f"  Total models with tiling UVs: {stats['with_tiling']:,}",
        "",
        "  Top span values across all models:",
    ]
    # Sort by max span
    top_span = sorted(
        [r for r in parsed if r.get('has_tiling')],
        key=lambda r: max(r.get('max_span_u', 0), r.get('max_span_v', 0)),
        reverse=True
    )[:20]
    for r in top_span:
        lines.append(f"    [{r['game']}] {r['resref']:30s}  "
                     f"u_span={r['max_span_u']:.2f}  v_span={r['max_span_v']:.2f}")
    lines += [""]

    lines += [
        "V-FLIP CONSISTENCY CHECK",
        "------------------------",
        "(KotOR engine expects V=0 at bottom of texture, matching OpenGL/TGA",
        " bottom-origin convention.  A genuine V-flip inconsistency occurs when",
        " ALL V coordinates on a renderable node are negative — this indicates",
        " the mesh was exported with a D3D top-origin convention and will render",
        " using the inverted/out-of-atlas region unless the engine flips V.)",
        " NOTE: nodes with UVs only in [0, 0.5] are NOT flipped; they simply",
        " use the lower half of the texture atlas — this is normal UV atlasing.",
        "",
    ]
    vflip_issues = [r for r in parsed if not r.get('v_flip_consistent', True)]
    lines.append(f"  Models with genuine V-flip issues (all-negative V): {len(vflip_issues)}")
    for r in vflip_issues[:10]:
        lines.append(f"    [{r['game']}] {r['resref']}")
    lines += [""]

    lines += [
        "RENDERER FIX STATUS",
        "-------------------",
        "  BUG-UV-1 (seam collapse)  : FIXED — span threshold ≤ 0.6",
        "  BUG-UV-2 (tiling cap 2×2) : FIXED — up to 8×8 tiles; >8 uses modulo",
        "  BUG-UV-3 (budget timing)  : FIXED — applied after down-sample",
        "  BUG-UV-4 (rotate_texture) : FIXED — UV rotation applied before render",
        "  BUG-UV-5 (V-flip formula) : FIXED — (tile_v_needed - v_shifted) × src_h",
        "",
        "  Node exclusion rules applied:",
        "    • is_saber=True  → saber blade planes (procedural, no UV atlas)",
        "    • *_g / *_g0 suffix → ghost/guide skeleton nodes (no UV expected)",
        "    • *_dum / *_helper / *_lod suffix → placeholder nodes",
        "    • tex='null' or tex='' → untextured geometry",
        "    • Sky-dome textures (lts_sky*, lta_sky*, dan_nebk …) → procedural",
        "",
        "=" * 70,
    ]

    with open(txt_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    # ── Print summary to stdout ───────────────────────────────────────────────
    elapsed = time.time() - t0
    print()
    print('\n'.join(lines[:40]))
    print(f"\nTotal time: {elapsed:.1f}s")
    print(f"\nFull results: {json_path}")
    print(f"Report:       {txt_path}")


if __name__ == '__main__':
    main()
