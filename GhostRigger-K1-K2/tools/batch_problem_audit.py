#!/usr/bin/env python3
"""
batch_problem_audit.py – Slice-based problem-model scanner for GhostRigger.

Usage:
    python3 tools/batch_problem_audit.py --game K1 --start 0 --count 500 --out /tmp/k1_0.json
    python3 tools/batch_problem_audit.py --game K2 --start 500 --count 500 --out /tmp/k2_500.json

Produces a JSON file listing only models that have at least one of:
  - mesh_pos_issue  : extreme / non-finite world positions for character/door/item models
  - tex_wrap_issue  : UV ranges outside [0,1] on character/item models (tiling expected, not bugs)
                      or UV completely missing on a textured mesh
  - bone_issue      : weight errors, <90% coverage on genuinely-weighted skins, bad bone names
  - parse_fail      : could not parse MDL at all

Each entry: { resref, game, issue_types: [...], details: [...] }

-----------------------------------------------------------------------
EXCLUSION RULES (v2 — post deep-diagnosis)
-----------------------------------------------------------------------
UV checks skip nodes that are:
  A. is_saber=True  — lightsaber blade planes (procedural geometry,
                      no UV array stored; rendered via saber glow shader)
  B. _g/_g0/_g01 suffix — KotOR "guide/ghost" skeleton-visualiser nodes.
                      These are used as rig helpers and intentionally
                      carry no UV data (e.g. lfoot_g, rcollar_g,
                      pelvis_g, rthigh_g, BTHips, BTSpine1 …)
  C. _dum/_helper/_lod suffix — dummy / LOD placeholders
  D. tex = 'null' or '' — no texture assigned; nothing to wrap
  E. tex in sky_set    — sky-dome quads use procedural skybox mapping,
                         not a UV atlas (lts_sky0001, lta_sky0001, etc.)
  F. vert_cnt == 0      — null-mesh placeholder (already handled)

Bone-name checks:
  WONTFIX pattern: names matching KNOWN_WONTFIX_BONES are original Bioware
  data quirks (apostrophes, digit-start).  They are flagged with category
  'bone_name_wontfix' but do NOT raise a bone_issue that blocks the model.
-----------------------------------------------------------------------
"""

import argparse, json, math, sys, os, logging, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
logging.disable(logging.CRITICAL)

RES_MDL = 2002
RES_MDX = 3008

# Valid bone-name pattern (ASCII identifier, no apostrophes, no digit-start)
BONE_NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,63}$')

# Known Bioware data quirks — original game files, WONTFIX
KNOWN_WONTFIX_BONES: set = {
    "Fin_lil'FL",
    "Fin_lil'FR",
    "3DGui",
}

# Sky-dome textures that intentionally have no UV layout
_SKY_TEXTURES: set = {
    'lts_sky0001', 'lta_sky0001', 'lko_sky02',
    'lts_sky0002', 'lts_sky0003', 'dan_nebk',
    'dan_sky', 'nar_sky', 'mss_sky', 'dxn_sky',
}

# ── node helpers ─────────────────────────────────────────────────────────────

def _is_guide_node(n) -> bool:
    """
    Return True if this mesh node is a KotOR "guide/ghost" helper that
    intentionally carries no UV data.

    Rules (in priority order):
      A. Lightsaber blade node (is_saber flag)
      B. Name ends with a guide-suffix: _g  _g0  _g01  _dum  _helper  _lod
      C. Name starts with 'bt' AND has no uvs (bantha-style bone nodes)
      D. tex='null' or tex='' (untextured geometry)
      E. Sky-dome texture (procedural mapping, no UV needed)
    """
    # A: saber blade
    if getattr(n, 'is_saber', False):
        return True

    nm = n.name.lower()

    # B: guide/ghost suffix
    _GUIDE_SUFFIXES = ('_g', '_g0', '_g01', '_g02', '_g03',
                       '_dum', '_helper', '_lod', '_shadow', '_shad',
                       '_col', '_coll', '_collision')
    if any(nm.endswith(s) for s in _GUIDE_SUFFIXES):
        return True

    # C: BT-prefix bone nodes (e.g. BTHips, BTSpine1)
    if nm.startswith('bt') and not (getattr(n, 'uvs', None) or []):
        return True

    # D: texture is null / empty
    tex = (getattr(n, 'texture', '') or '').strip().lower()
    if not tex or tex == 'null':
        return True

    # E: sky-dome texture
    if tex in _SKY_TEXTURES:
        return True

    return False


# ── classification helper ────────────────────────────────────────────────────

def _classify(model) -> str:
    """Return a simple string classification from model_type byte."""
    mt = getattr(model, 'model_type', 4)
    _MAP = {0: 'effect', 1: 'effects', 2: 'misc',
            4: 'character', 8: 'door', 32: 'item', 64: 'character'}
    return _MAP.get(mt, 'character')


def _world_pos_ok(node, classification: str) -> bool:
    """Return True if world position is finite and within expected range."""
    _LARGE = {'effect', 'effects', 'misc', 'tile', 'area', 'door', 'item', 'fx'}
    try:
        wp, _ = node.world_transform()
        limit = 200_000.0 if classification in _LARGE else 2_000.0
        return all(math.isfinite(v) and abs(v) <= limit for v in wp)
    except Exception:
        return False


# ── UV analysis ──────────────────────────────────────────────────────────────

def _uv_stats(mesh_nodes) -> dict:
    """
    Return per-model UV statistics for texture-wrapping evaluation.
    Only considers nodes that are NOT guide/ghost helpers.
    """
    tiling_nodes   = 0
    missing_uv     = 0
    total_renderable = 0
    max_span_u = 0.0
    max_span_v = 0.0
    details    = []

    for n in mesh_nodes:
        if _is_guide_node(n):
            continue
        verts = getattr(n, 'vertices', None) or []
        if not verts:
            continue
        total_renderable += 1
        uvs = getattr(n, 'uvs', None) or []
        tex = (getattr(n, 'texture', '') or '').strip()

        if not uvs or len(uvs) < len(verts) * 0.5:
            missing_uv += 1
            details.append({
                'node': n.name, 'tex': tex,
                'uvs': len(uvs), 'verts': len(verts),
                'issue': 'missing_uvs',
            })
            continue

        # Filter out KotOR sentinel UV values (~-1.7e38, ~-1.0e30 → "no UV").
        # Any |uv| > 10 000 is a sentinel; exclude before computing ranges.
        _UV_SENTINEL = 10_000.0
        valid_uvs = [(u, v) for u, v in uvs
                     if abs(u) <= _UV_SENTINEL and abs(v) <= _UV_SENTINEL]
        if not valid_uvs:
            missing_uv += 1
            details.append({
                'node': n.name, 'tex': tex,
                'uvs': 0, 'verts': len(verts),
                'issue': 'missing_uvs', 'note': 'all-sentinel UVs',
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
            tiling_nodes += 1
            details.append({
                'node': n.name, 'tex': tex,
                'u_min': round(u_min, 3), 'u_max': round(u_max, 3),
                'v_min': round(v_min, 3), 'v_max': round(v_max, 3),
                'issue': 'tiling',
            })

    return {
        'total_renderable': total_renderable,
        'missing_uv':       missing_uv,
        'tiling_nodes':     tiling_nodes,
        'max_span_u':       round(max_span_u, 3),
        'max_span_v':       round(max_span_v, 3),
        'details':          details,
    }


# ── main audit logic ─────────────────────────────────────────────────────────

def _audit_one(resref: str, mdl_data: bytes, mdx_data: bytes) -> dict | None:
    """
    Audit a single model. Returns a problem dict or None if clean.
    """
    from src.core.mdl_parser import MDLBinaryParser

    issue_types = []
    details     = []
    wontfix     = []

    # 1. Parse
    try:
        parser = MDLBinaryParser(mdl_data, mdx_data or b'')
        model  = parser.parse()
    except Exception as e:
        return {'issue_types': ['parse_fail'], 'details': [f"parse error: {e}"]}

    classification = _classify(model)
    mesh_nodes = model.mesh_nodes()
    all_nodes  = model.all_nodes()

    # ── 2. Mesh position issues ──────────────────────────────────────────────
    is_large_model = classification in ('effect', 'effects', 'misc', 'tile', 'fx')
    if not is_large_model:
        pos_issues = []
        for n in all_nodes[:200]:
            if not _world_pos_ok(n, classification):
                try:
                    wp, _ = n.world_transform()
                    pos_issues.append(
                        f"{n.name}: pos {[round(x, 1) for x in wp]}")
                except Exception:
                    pos_issues.append(f"{n.name}: world_transform error")
        if pos_issues:
            issue_types.append('mesh_pos_issue')
            details.extend(pos_issues[:5])

    # ── 3. UV / texture wrapping ─────────────────────────────────────────────
    #
    # We separate two sub-categories:
    #   tex_missing   – renderable, textured node with <50% UV coverage
    #   tex_tiling    – renderable node with UVs outside [0,1] (expected for
    #                   many KotOR models; listed for awareness, not as error)
    #
    uv = _uv_stats(mesh_nodes)
    missing_uv_nodes = [d for d in uv['details'] if d['issue'] == 'missing_uvs']
    tiling_nodes     = [d for d in uv['details'] if d['issue'] == 'tiling']

    if missing_uv_nodes:
        issue_types.append('tex_missing_uv')
        for d in missing_uv_nodes[:5]:
            details.append(
                f"{d['node']} (tex={d['tex']}): {d['uvs']} uvs / {d['verts']} verts")

    # Tiling is informational (not an error) but we record it
    if tiling_nodes:
        issue_types.append('tex_tiling')
        details.append(
            f"{len(tiling_nodes)} nodes have tiling UVs "
            f"(max_span u={uv['max_span_u']:.2f} v={uv['max_span_v']:.2f})")

    # ── 4. Bone / weight issues ──────────────────────────────────────────────
    skin_nodes = [n for n in mesh_nodes if n.is_skin]
    if skin_nodes:
        bone_issues = []

        for sn in skin_nodes:
            if not sn.skin_data:
                bone_issues.append(f"{sn.name}: no skin_data")
                continue

            # All-inactive bone map = valid overlay (robe/cape)
            bm_floats    = getattr(sn, 'bone_map_floats', None)
            has_bm_slots = bm_floats is not None and len(bm_floats) > 0
            all_inactive = has_bm_slots and all(v < 0 for v in bm_floats)
            if all_inactive:
                continue  # overlay robe/cape — no weights needed

            skinnable = len(sn.vertices)
            weighted  = sum(1 for sd in sn.skin_data if sd.influences)
            coverage  = weighted / max(1, skinnable)
            if coverage < 0.9:
                bone_issues.append(f"{sn.name}: {coverage:.0%} weight coverage")

            bad_sums = sum(
                1 for sd in sn.skin_data[:100]
                if sd.influences and
                   not 0.9 <= sum(i.weight for i in sd.influences) <= 1.1
            )
            if bad_sums > 5:
                bone_issues.append(
                    f"{sn.name}: {bad_sums} verts with bad weight sums")

            if not sn.bone_map and not all_inactive and sn.skin_data and not has_bm_slots:
                bone_issues.append(f"{sn.name}: empty bone_map with no slots")

        # Bone name check — separate WONTFIX from real errors
        all_bone_names: set = set()
        for sn in skin_nodes:
            all_bone_names.update(b for b in sn.bone_map if b)

        bad_bones = [b for b in all_bone_names if not BONE_NAME_RE.match(b)]
        real_bad  = [b for b in bad_bones if b not in KNOWN_WONTFIX_BONES]
        wf_bad    = [b for b in bad_bones if b in KNOWN_WONTFIX_BONES]

        if real_bad:
            bone_issues.append(f"bad bone names: {real_bad[:3]}")
        if wf_bad:
            wontfix.append(f"wontfix bone names (original Bioware data): {wf_bad[:3]}")

        if bone_issues:
            issue_types.append('bone_issue')
            details.extend(bone_issues[:5])

    if not issue_types and not wontfix:
        return None   # clean model

    # Build result, always include wontfix info even if no real errors
    result: dict = {'issue_types': issue_types, 'details': details}
    if wontfix:
        result['wontfix'] = wontfix
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description='GhostRigger slice-based problem scanner')
    ap.add_argument('--game',  required=True, choices=['K1', 'K2'])
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--count', type=int, default=300)
    ap.add_argument('--out',   required=True)
    ap.add_argument('--k1',    default=os.environ.get('KOTOR_K1_DIR', 'game_data/k1_extracted'))
    ap.add_argument('--k2',    default=os.environ.get('KOTOR_K2_DIR', 'game_data/k2_extracted'))
    args = ap.parse_args()

    from src.resources.game_library import GameLibrary
    gl = GameLibrary()
    if args.game == 'K1':
        gl.scan(args.k1)
        reader = gl._k1_key
    else:
        gl.scan(k2_dir=args.k2)
        reader = gl._k2_key

    if reader is None:
        print(f"ERROR: could not load {args.game} reader from "
              f"{args.k1 if args.game == 'K1' else args.k2}")
        sys.exit(1)

    entries = reader.list_type(RES_MDL)
    total   = len(entries)
    chunk   = entries[args.start: args.start + args.count]
    print(f"[batch_audit] {args.game}  slice {args.start}–{args.start + len(chunk) - 1}"
          f"  ({len(chunk)} of {total} total)", flush=True)

    problems: list = []
    for i, entry in enumerate(chunk):
        resref = entry.resref
        try:
            mdl_data  = entry.read()
            mdx_entry = reader.get(resref, RES_MDX)
            mdx_data  = mdx_entry.read() if mdx_entry else b''
        except Exception as e:
            problems.append({
                'resref': resref, 'game': args.game,
                'issue_types': ['parse_fail'],
                'details': [f"read error: {e}"],
            })
            continue

        result = _audit_one(resref, mdl_data, mdx_data)
        if result:
            result['resref'] = resref
            result['game']   = args.game
            problems.append(result)

        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(chunk)} done — {len(problems)} problems so far",
                  flush=True)

    print(f"[batch_audit] Done. {len(problems)} problem models in this slice.", flush=True)

    with open(args.out, 'w') as f:
        json.dump(problems, f, indent=2)
    print(f"[batch_audit] Written → {args.out}", flush=True)


if __name__ == '__main__':
    main()
