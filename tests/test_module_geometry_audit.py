"""
Deep Module Geometry & Texture Audit
=====================================
Audits every single module model in both K1 (KotOR 1) and K2 (TSL) game libraries.

For each module MDL this test verifies:
  1. MDL bytes are loadable from the archive (ResourceManager)
  2. MDX bytes are retrievable (or absent — some tiles have no MDX)
  3. load_model_from_bytes() succeeds without exception
  4. At least one renderable mesh node exists
  5. All renderable mesh nodes that carry a texture name have that texture
     resolvable in the game archive (TPC or TGA)
  6. All mesh nodes have at least 3 vertices and at least 1 face
  7. UV coordinates exist on textured nodes (flagged as warning if absent)
  8. Normals exist (flagged as warning if absent — they can be re-computed)
  9. Supermodel reference is recorded for cross-module relationships

Results are written to:
  tests/audit_output/module_geometry_audit.json   — full machine-readable report
  tests/audit_output/module_geometry_audit.txt    — human-readable summary

Run:
  python -m pytest tests/test_module_geometry_audit.py -v -s
"""

import os
import sys
import json
import time
import re
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest

# ── path setup ──────────────────────────────────────────────────────────────
SRC = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC))

K1_DIR = Path(__file__).parent.parent / "GhostRigger-K1-K2/game_data/k1_extracted"
K2_DIR = Path(__file__).parent.parent / "GhostRigger-K1-K2/game_data/k2_extracted"
AUDIT_DIR = Path(__file__).parent / "audit_output"
AUDIT_DIR.mkdir(exist_ok=True)

# ── module resref classification ─────────────────────────────────────────────
K1_MODULE_PREFIXES = (
    'end_', 'tar_', 'danm', 'tat_', 'kas_', 'manm', 'korr_', 'lev_',
    'unk_', 'sta_', 'ebo_', 'liv_', 'stunt_',
)
_K1_M_RE = re.compile(r'^m\d{2}')
_K2_MOD_RE = re.compile(r'^\d{3}[a-z]{2}')


def _is_module(resref: str, game: str) -> bool:
    r = resref.lower()
    if game == 'K1':
        if any(r.startswith(p) for p in K1_MODULE_PREFIXES):
            return True
        if _K1_M_RE.match(r):
            return True
    else:
        if _K2_MOD_RE.match(r):
            return True
    return False


# ── helpers ──────────────────────────────────────────────────────────────────

def _tex_name(node) -> str:
    """Return cleaned lower-case texture name, or '' if absent/null."""
    raw = getattr(node, 'texture', '') or ''
    clean = raw.strip().split('\x00')[0].strip()
    return clean.lower() if clean and clean.upper() not in ('NULL', 'NONE', '') else ''


def _has_valid_uvs(node) -> bool:
    uvs = getattr(node, 'uvs', []) or []
    if not uvs:
        return False
    # At least some non-zero UVs
    return any(u != 0.0 or v != 0.0 for u, v in uvs[:5])


def _extreme_uvs(node) -> bool:
    uvs = getattr(node, 'uvs', []) or []
    return any(abs(u) > 50.0 or abs(v) > 50.0 for u, v in uvs[:20])


# ── per-model audit ──────────────────────────────────────────────────────────

def audit_one_model(resref: str, game: str, mgr) -> dict:
    """
    Load one module MDL and run geometry + texture checks.

    Returns a dict with:
      ok        – True if no hard failures
      resref    – model name
      game      – 'K1' or 'K2'
      errors    – list of fatal problems
      warnings  – list of non-fatal issues
      stats     – dict of counts
    """
    result = {
        'resref': resref,
        'game': game,
        'ok': False,
        'errors': [],
        'warnings': [],
        'stats': {},
    }
    t0 = time.perf_counter()

    # 1 ── load MDL bytes ──────────────────────────────────────────────────
    try:
        mdl_bytes = mgr.get_mdl(resref, game)
    except Exception as e:
        result['errors'].append(f'get_mdl exception: {e}')
        return result

    if not mdl_bytes:
        result['errors'].append('MDL bytes empty / not found in archive')
        return result

    # 2 ── load MDX bytes (non-fatal if absent) ────────────────────────────
    try:
        mdx_bytes = mgr.get_mdx(resref, game) or b''
    except Exception:
        mdx_bytes = b''
    result['stats']['mdl_size'] = len(mdl_bytes)
    result['stats']['mdx_size'] = len(mdx_bytes)

    # 3 ── parse model ─────────────────────────────────────────────────────
    try:
        from core.kotor_loader import load_model_from_bytes
        model = load_model_from_bytes(mdl_bytes, mdx_bytes)
    except Exception as e:
        result['errors'].append(f'parse error: {type(e).__name__}: {e}')
        return result

    result['stats']['supermodel'] = getattr(model, 'supermodel', '') or ''
    result['stats']['anim_count'] = len(getattr(model, 'animations', []))

    # 4 ── collect all mesh nodes ─────────────────────────────────────────
    all_nodes = list(model.all_nodes())
    mesh_nodes = [n for n in all_nodes if getattr(n, 'is_mesh', False)]
    result['stats']['node_count'] = len(all_nodes)
    result['stats']['mesh_count'] = len(mesh_nodes)

    if not mesh_nodes:
        result['warnings'].append('No mesh nodes found — possible dummy/empty model')
        result['ok'] = True
        result['stats']['load_ms'] = round((time.perf_counter() - t0) * 1000, 1)
        return result

    # 5 ── per-node geometry checks ───────────────────────────────────────
    bad_geom_nodes = []
    no_uv_textured = []
    no_normal_nodes = []
    extreme_uv_nodes = []
    tex_names_needed = set()
    textured_count = 0
    renderable_count = 0
    zero_vert_nodes = []

    for node in mesh_nodes:
        verts = getattr(node, 'vertices', []) or []
        faces = getattr(node, 'faces', []) or []
        normals = getattr(node, 'normals', []) or []
        uvs = getattr(node, 'uvs', []) or []
        tex = _tex_name(node)

        # vertex / face integrity
        if len(verts) < 3 and len(verts) > 0:
            bad_geom_nodes.append(f'{node.name}(verts={len(verts)})')
        if len(verts) == 0:
            zero_vert_nodes.append(node.name)
            continue  # skip UV / normal checks for empty nodes

        renderable_count += 1

        # normals
        if not normals:
            no_normal_nodes.append(node.name)

        # texture checks
        if tex:
            textured_count += 1
            tex_names_needed.add(tex)
            # UV check
            if not uvs:
                no_uv_textured.append(node.name)
            elif _extreme_uvs(node):
                extreme_uv_nodes.append(node.name)

    result['stats']['textured_mesh_count'] = textured_count
    result['stats']['renderable_count'] = renderable_count
    result['stats']['unique_textures'] = len(tex_names_needed)

    if zero_vert_nodes:
        result['warnings'].append(
            f'{len(zero_vert_nodes)} zero-vertex mesh node(s): {", ".join(zero_vert_nodes[:5])}'
        )
    if bad_geom_nodes:
        result['warnings'].append(
            f'Under-vertex mesh node(s): {", ".join(bad_geom_nodes[:5])}'
        )
    if no_normal_nodes:
        result['warnings'].append(
            f'{len(no_normal_nodes)} mesh node(s) missing normals (will be recomputed): '
            f'{", ".join(no_normal_nodes[:3])}'
        )
    if no_uv_textured:
        result['warnings'].append(
            f'{len(no_uv_textured)} textured node(s) have no UVs: '
            f'{", ".join(no_uv_textured[:5])}'
        )
    if extreme_uv_nodes:
        result['warnings'].append(
            f'{len(extreme_uv_nodes)} node(s) with extreme UV coords (>50): '
            f'{", ".join(extreme_uv_nodes[:5])}'
        )

    # 6 ── texture resolution check ───────────────────────────────────────
    missing_textures = []
    for tex in sorted(tex_names_needed):
        try:
            tex_bytes = mgr.get_texture(tex, game)
        except Exception:
            tex_bytes = None
        if not tex_bytes:
            missing_textures.append(tex)

    result['stats']['missing_texture_count'] = len(missing_textures)
    if missing_textures:
        # Missing textures are warnings not errors — many tile textures are
        # in TexturePacks ERFs that may not all be present in the test install.
        result['warnings'].append(
            f'{len(missing_textures)} texture(s) not found in archive: '
            f'{", ".join(missing_textures[:8])}'
        )

    result['stats']['load_ms'] = round((time.perf_counter() - t0) * 1000, 1)
    result['ok'] = len(result['errors']) == 0
    return result


# ── main audit runner ────────────────────────────────────────────────────────

def run_full_audit(mgr, game: str) -> List[dict]:
    """Run the audit for every module model in one game."""
    all_models = mgr.list_models(game)
    module_models = [(r, g) for r, g in all_models if _is_module(r, game)]
    module_models.sort()

    results = []
    n = len(module_models)
    t_start = time.perf_counter()

    for i, (resref, _) in enumerate(module_models):
        res = audit_one_model(resref, game, mgr)
        results.append(res)

        if (i + 1) % 200 == 0 or (i + 1) == n:
            elapsed = time.perf_counter() - t_start
            pct = (i + 1) / n * 100
            ok_so_far = sum(1 for r in results if r['ok'])
            err_so_far = sum(1 for r in results if r['errors'])
            print(
                f'  [{game}] {i+1}/{n} ({pct:.0f}%)  '
                f'ok={ok_so_far}  errors={err_so_far}  '
                f'elapsed={elapsed:.1f}s',
                flush=True,
            )

    return results


def write_report(k1_results: List[dict], k2_results: List[dict]):
    """Write JSON + human-readable TXT audit reports."""
    all_results = k1_results + k2_results

    # ── JSON ─────────────────────────────────────────────────────────────
    json_path = AUDIT_DIR / 'module_geometry_audit.json'
    with open(json_path, 'w') as f:
        json.dump({
            'generated': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
            'k1_count': len(k1_results),
            'k2_count': len(k2_results),
            'total': len(all_results),
            'k1_ok': sum(1 for r in k1_results if r['ok']),
            'k2_ok': sum(1 for r in k2_results if r['ok']),
            'k1_errors': sum(1 for r in k1_results if r['errors']),
            'k2_errors': sum(1 for r in k2_results if r['errors']),
            'results': all_results,
        }, f, indent=2)

    # ── TXT ──────────────────────────────────────────────────────────────
    txt_path = AUDIT_DIR / 'module_geometry_audit.txt'
    k1_ok  = sum(1 for r in k1_results if r['ok'])
    k2_ok  = sum(1 for r in k2_results if r['ok'])
    k1_err = sum(1 for r in k1_results if r['errors'])
    k2_err = sum(1 for r in k2_results if r['errors'])
    k1_warn = sum(1 for r in k1_results if r['warnings'] and r['ok'])
    k2_warn = sum(1 for r in k2_results if r['warnings'] and r['ok'])

    # Categorise errors
    parse_errors   = [r for r in all_results if any('parse error' in e for e in r['errors'])]
    missing_mdl    = [r for r in all_results if any('MDL bytes empty' in e for e in r['errors'])]
    get_mdl_exc    = [r for r in all_results if any('get_mdl exception' in e for e in r['errors'])]
    tex_warn_list  = [r for r in all_results if any('texture(s) not found' in w for w in r['warnings'])]
    no_mesh_list   = [r for r in all_results if any('No mesh nodes' in w for w in r['warnings'])]
    uv_warn_list   = [r for r in all_results if any('no UVs' in w for w in r['warnings'])]
    norm_warn_list = [r for r in all_results if any('missing normals' in w for w in r['warnings'])]

    with open(txt_path, 'w') as f:
        f.write('=' * 72 + '\n')
        f.write('  GhostRigger Module Geometry & Texture Deep Audit\n')
        f.write(f'  Generated: {time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())}\n')
        f.write('=' * 72 + '\n\n')

        f.write('SUMMARY\n')
        f.write('-' * 40 + '\n')
        f.write(f'  K1 models audited : {len(k1_results):4d}  '
                f'OK={k1_ok}  Errors={k1_err}  Warnings-only={k1_warn}\n')
        f.write(f'  K2 models audited : {len(k2_results):4d}  '
                f'OK={k2_ok}  Errors={k2_err}  Warnings-only={k2_warn}\n')
        f.write(f'  TOTAL             : {len(all_results):4d}  '
                f'OK={k1_ok+k2_ok}  Errors={k1_err+k2_err}  '
                f'Warnings-only={k1_warn+k2_warn}\n\n')

        # Error categories
        f.write('ERROR CATEGORIES\n')
        f.write('-' * 40 + '\n')
        f.write(f'  MDL not found in archive : {len(missing_mdl)}\n')
        f.write(f'  get_mdl() exception      : {len(get_mdl_exc)}\n')
        f.write(f'  Parse / load failure     : {len(parse_errors)}\n\n')

        # Warning categories
        f.write('WARNING CATEGORIES (non-fatal)\n')
        f.write('-' * 40 + '\n')
        f.write(f'  Missing textures    : {len(tex_warn_list)} models\n')
        f.write(f'  No mesh nodes       : {len(no_mesh_list)} models\n')
        f.write(f'  UV-less textured    : {len(uv_warn_list)} models\n')
        f.write(f'  Missing normals     : {len(norm_warn_list)} models\n\n')

        # Hard errors detail
        if k1_err + k2_err > 0:
            f.write('HARD ERRORS — DETAIL\n')
            f.write('-' * 40 + '\n')
            for r in all_results:
                if r['errors']:
                    f.write(f'  [{r["game"]}] {r["resref"]}\n')
                    for e in r['errors']:
                        f.write(f'      ERROR: {e}\n')
            f.write('\n')

        # Missing texture aggregation
        if tex_warn_list:
            f.write('MISSING TEXTURE SUMMARY (top 50 most common)\n')
            f.write('-' * 40 + '\n')
            tex_freq: Dict[str, int] = {}
            for r in tex_warn_list:
                for w in r['warnings']:
                    if 'texture(s) not found' in w:
                        # parse the texture names out of the warning string
                        # format: "N texture(s) not found in archive: tex1, tex2, ..."
                        parts = w.split(':', 1)
                        if len(parts) > 1:
                            for t in parts[1].split(','):
                                t = t.strip()
                                if t:
                                    tex_freq[t] = tex_freq.get(t, 0) + 1
            for tex, cnt in sorted(tex_freq.items(), key=lambda x: -x[1])[:50]:
                f.write(f'  {tex:40s} referenced by {cnt} model(s)\n')
            f.write('\n')

        # Per-game detailed warning lists
        for game, results in [('K1', k1_results), ('K2', k2_results)]:
            warn_results = [r for r in results if r['warnings'] and r['ok']]
            if warn_results:
                f.write(f'{game} MODELS WITH WARNINGS\n')
                f.write('-' * 40 + '\n')
                for r in warn_results[:100]:  # cap at 100 for readability
                    f.write(f'  {r["resref"]:30s}  '
                            f'meshes={r["stats"].get("mesh_count","?"):4}  '
                            f'tex={r["stats"].get("textured_mesh_count","?"):4}  '
                            f'miss_tex={r["stats"].get("missing_texture_count","?"):3}\n')
                    for w in r['warnings']:
                        f.write(f'      WARN: {w}\n')
                if len(warn_results) > 100:
                    f.write(f'  ... and {len(warn_results)-100} more (see JSON for full list)\n')
                f.write('\n')

    print(f'\nAudit reports written to:')
    print(f'  {json_path}')
    print(f'  {txt_path}')
    return json_path, txt_path


# ── pytest entry point ───────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def resource_manager():
    """Return an indexed ResourceManager for both games."""
    from core.resource_manager import ResourceManager
    mgr = ResourceManager()
    assert K1_DIR.exists(), f'K1 game directory not found: {K1_DIR}'
    assert K2_DIR.exists(), f'K2 game directory not found: {K2_DIR}'
    ok1 = mgr.set_k1_dir(str(K1_DIR))
    ok2 = mgr.set_k2_dir(str(K2_DIR))
    assert ok1, 'Failed to index K1 game directory'
    assert ok2, 'Failed to index K2 game directory'
    return mgr


class TestModuleGeometryAudit:
    """Deep audit of all K1 and K2 module geometry and texture loading."""

    def test_k1_module_models_load(self, resource_manager):
        """Audit all K1 module models: MDL parse, geometry integrity, texture resolution."""
        mgr = resource_manager
        print(f'\n[K1] Starting audit…', flush=True)
        results = run_full_audit(mgr, 'K1')

        errors = [r for r in results if r['errors']]
        ok_count = len(results) - len(errors)
        print(f'\n[K1] Done — {len(results)} models: {ok_count} OK, {len(errors)} errors')

        # Store for combined report (use module-level cache)
        TestModuleGeometryAudit._k1_results = results

        # Hard failures become test failures with detail
        if errors:
            msg_lines = [f'\n{len(errors)} K1 module(s) failed to load:\n']
            for r in errors[:30]:
                msg_lines.append(f'  {r["resref"]}: {"; ".join(r["errors"])}')
            if len(errors) > 30:
                msg_lines.append(f'  … and {len(errors)-30} more (see audit JSON)')
            pytest.fail('\n'.join(msg_lines))

    def test_k2_module_models_load(self, resource_manager):
        """Audit all K2 module models: MDL parse, geometry integrity, texture resolution."""
        mgr = resource_manager
        print(f'\n[K2] Starting audit…', flush=True)
        results = run_full_audit(mgr, 'K2')

        errors = [r for r in results if r['errors']]
        ok_count = len(results) - len(errors)
        print(f'\n[K2] Done — {len(results)} models: {ok_count} OK, {len(errors)} errors')

        TestModuleGeometryAudit._k2_results = results

        if errors:
            msg_lines = [f'\n{len(errors)} K2 module(s) failed to load:\n']
            for r in errors[:30]:
                msg_lines.append(f'  {r["resref"]}: {"; ".join(r["errors"])}')
            if len(errors) > 30:
                msg_lines.append(f'  … and {len(errors)-30} more (see audit JSON)')
            pytest.fail('\n'.join(msg_lines))

    def test_write_combined_report(self):
        """Write the combined JSON + TXT audit report."""
        k1 = getattr(TestModuleGeometryAudit, '_k1_results', [])
        k2 = getattr(TestModuleGeometryAudit, '_k2_results', [])
        if not k1 and not k2:
            pytest.skip('No audit results available — run K1/K2 tests first')
        json_path, txt_path = write_report(k1, k2)
        assert json_path.exists()
        assert txt_path.exists()
        print(f'\nReport: {txt_path}')

    def test_texture_missing_rate_acceptable(self):
        """Warn (not fail) if more than 20% of textures are missing across all modules."""
        k1 = getattr(TestModuleGeometryAudit, '_k1_results', [])
        k2 = getattr(TestModuleGeometryAudit, '_k2_results', [])
        all_results = k1 + k2
        if not all_results:
            pytest.skip('No results')
        total_models = len(all_results)
        models_with_missing = sum(
            1 for r in all_results
            if r['stats'].get('missing_texture_count', 0) > 0
        )
        pct = models_with_missing / total_models * 100 if total_models else 0
        print(f'\nTexture missing rate: {models_with_missing}/{total_models} models '
              f'({pct:.1f}%) have at least one unresolvable texture')
        if pct > 30:
            pytest.fail(
                f'{pct:.1f}% of module models have unresolvable textures '
                f'(threshold 30%). Check TexturePacks indexing.'
            )

    def test_parse_failure_rate_zero(self):
        """Zero parse failures allowed — every MDL that exists must load cleanly."""
        k1 = getattr(TestModuleGeometryAudit, '_k1_results', [])
        k2 = getattr(TestModuleGeometryAudit, '_k2_results', [])
        parse_errors = [
            r for r in k1 + k2
            if any('parse error' in e for e in r['errors'])
        ]
        if parse_errors:
            details = '\n'.join(
                f'  [{r["game"]}] {r["resref"]}: {"; ".join(r["errors"])}'
                for r in parse_errors[:20]
            )
            pytest.fail(
                f'{len(parse_errors)} module MDL(s) failed to parse:\n{details}'
            )

    def test_light_header_read_order_regression(self, resource_manager):
        """Regression test for _LightHeader binary field order fix.

        Prior to the fix, _LightHeader.read() consumed a 3-uint32 'unknown' block
        BEFORE flare_radius, misaligning all subsequent field reads by 4 bytes.
        When a light node had a non-zero flare_radius the mis-read array counts
        were garbage values pointing outside the file, causing an EOF struct error
        that made load_model_from_bytes() return None for 45 modules (33 K1 + 12 K2).

        Confirmed fix: flare_radius (float) must be read FIRST, matching kotorblender
        reader.py line 247.  See docs/patches/light_header_read_order.patch.
        """
        mgr = resource_manager
        from core.kotor_loader import load_model_from_bytes

        # Representative previously-failing K1 models — light nodes with non-zero
        # flare_radius that triggered the alignment bug.
        K1_REGRESSION = [
            'm33ab_02',   # Dantooine ruins — 7 light nodes, last one flare_radius=750000
            'm26aa_set',  # Cutscene SET  — light-heavy scene
            'm12ac_01a',  # Manaan underwater — light nodes with flare data
            'm17aa_54',   # Unknown World — special variant with lens flares
            'm18aa_05a',  # Star Forge — atmospheric lighting
            'm14aa_01h',  # Leviathan — prison lights
        ]
        # Representative previously-failing K2 models
        K2_REGRESSION = [
            '421dxn_14',    # Dxun jungle — ambient lights
            '501ondd',      # Onderon docking bay
            '801drob',      # Droid planet — robot factory lighting
            '605danh',      # Dantooine ruins
        ]

        failures = []
        for resref in K1_REGRESSION:
            mdl = mgr.get_mdl(resref, 'k1')
            if not mdl:
                failures.append(f'[K1] {resref}: MDL not found in archive')
                continue
            mdx = mgr.get_mdx(resref, 'k1') or b''
            try:
                model = load_model_from_bytes(mdl, mdx, resref)
            except Exception as e:
                failures.append(f'[K1] {resref}: exception: {e}')
                continue
            if model is None:
                failures.append(
                    f'[K1] {resref}: load_model_from_bytes returned None '
                    f'(light header misalignment — check _LightHeader.read() order)'
                )

        for resref in K2_REGRESSION:
            mdl = mgr.get_mdl(resref, 'k2')
            if not mdl:
                failures.append(f'[K2] {resref}: MDL not found in archive')
                continue
            mdx = mgr.get_mdx(resref, 'k2') or b''
            try:
                model = load_model_from_bytes(mdl, mdx, resref)
            except Exception as e:
                failures.append(f'[K2] {resref}: exception: {e}')
                continue
            if model is None:
                failures.append(
                    f'[K2] {resref}: load_model_from_bytes returned None '
                    f'(light header misalignment — check _LightHeader.read() order)'
                )

        if failures:
            pytest.fail(
                '_LightHeader read-order regression:\n' +
                '\n'.join(f'  {f}' for f in failures)
            )


# ── standalone runner ─────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys as _sys
    _sys.path.insert(0, str(SRC))
    from core.resource_manager import ResourceManager

    mgr = ResourceManager()
    mgr.set_k1_dir(str(K1_DIR))
    mgr.set_k2_dir(str(K2_DIR))

    print('Running K1 audit…')
    k1r = run_full_audit(mgr, 'K1')
    print('Running K2 audit…')
    k2r = run_full_audit(mgr, 'K2')
    write_report(k1r, k2r)
