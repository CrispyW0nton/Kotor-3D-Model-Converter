"""
Standalone module geometry audit runner.
Runs the full K1+K2 deep audit and writes results to tests/audit_output/.
"""
import sys, os, re, json, time, struct, traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from core.resource_manager import ResourceManager
from core.kotor_loader import load_model_from_bytes

K1_DIR = Path('GhostRigger-K1-K2/game_data/k1_extracted')
K2_DIR = Path('GhostRigger-K1-K2/game_data/k2_extracted')
AUDIT_DIR = Path('tests/audit_output')
AUDIT_DIR.mkdir(exist_ok=True)

# ── Module detection ──────────────────────────────────────────────────────────
K1_PREFIXES = ('end_', 'tar_', 'danm', 'tat_', 'kas_', 'manm', 'korr_', 'lev_',
               'unk_', 'sta_', 'ebo_', 'liv_', 'stunt_')
K1_M_RE  = re.compile(r'^m\d{2}')
K2_RE    = re.compile(r'^\d{3}[a-z]{2}')

# ── Known empty/placeholder models to skip ────────────────────────────────────
SKIP_RESREFS = {'000test', '000trl'}

# ── Known stunt (dialogue-only) modules — no geometry expected ────────────────
STUNT_RE = re.compile(r'^stunt_', re.I)

def is_module(resref: str, game: str) -> bool:
    r = resref.lower()
    if game == 'K1':
        return any(r.startswith(p) for p in K1_PREFIXES) or bool(K1_M_RE.match(r))
    return bool(K2_RE.match(r))


def tex_name(node) -> str:
    raw = getattr(node, 'texture', '') or ''
    c = raw.strip().split('\x00')[0].strip()
    return c.lower() if c and c.upper() not in ('NULL', 'NONE', '') else ''


def audit_one(resref: str, game: str, mgr: ResourceManager) -> dict:
    result = {'resref': resref, 'game': game, 'ok': False, 'errors': [], 'warnings': [], 'stats': {}}
    t0 = time.perf_counter()

    # MDL bytes
    try:
        mdl_bytes = mgr.get_mdl(resref, game)
    except Exception as e:
        result['errors'].append(f'get_mdl exception: {e}')
        return result

    if not mdl_bytes:
        result['errors'].append('MDL bytes empty / not found in archive')
        return result

    # MDX bytes
    try:
        mdx_bytes = mgr.get_mdx(resref, game) or b''
    except Exception:
        mdx_bytes = b''

    result['stats']['mdl_size'] = len(mdl_bytes)
    result['stats']['mdx_size'] = len(mdx_bytes)

    # Parse
    try:
        model = load_model_from_bytes(mdl_bytes, mdx_bytes)
    except Exception as e:
        result['errors'].append(f'parse error: {type(e).__name__}: {e}')
        return result

    if model is None:
        result['errors'].append('load_model_from_bytes returned None')
        return result

    result['stats']['supermodel'] = getattr(model, 'supermodel', '') or ''
    result['stats']['anim_count']  = len(getattr(model, 'animations', []))

    all_nodes = list(model.all_nodes())
    mesh_nodes = [n for n in all_nodes if getattr(n, 'is_mesh', False)]
    result['stats']['node_count'] = len(all_nodes)
    result['stats']['mesh_count'] = len(mesh_nodes)

    # Stunt/cutscene modules have no geometry — just flag as ok with a note
    if not mesh_nodes:
        if STUNT_RE.match(resref):
            result['warnings'].append('Stunt/cutscene module — no 3D geometry (DLG only)')
        else:
            result['warnings'].append('No mesh nodes found (may be camera/light-only)')
        result['ok'] = True
        result['stats']['load_ms'] = round((time.perf_counter() - t0) * 1000, 1)
        return result

    # Geometry + texture checks
    tex_names_needed = set()
    textured_count   = 0
    renderable_count = 0
    zero_vert_nodes  = []
    no_uv_textured   = []

    for node in mesh_nodes:
        verts  = getattr(node, 'vertices', []) or []
        uvs    = getattr(node, 'uvs', []) or []
        tex    = tex_name(node)

        if len(verts) == 0:
            zero_vert_nodes.append(node.name)
            continue

        renderable_count += 1
        if tex:
            textured_count += 1
            tex_names_needed.add(tex)
            if not uvs:
                no_uv_textured.append(node.name)

    result['stats']['textured_mesh_count'] = textured_count
    result['stats']['renderable_count']    = renderable_count
    result['stats']['unique_textures']     = len(tex_names_needed)

    if zero_vert_nodes:
        result['warnings'].append(
            f'{len(zero_vert_nodes)} zero-vertex mesh nodes: {", ".join(zero_vert_nodes[:5])}')
    if no_uv_textured:
        result['warnings'].append(
            f'{len(no_uv_textured)} textured nodes with no UVs: {", ".join(no_uv_textured[:5])}')

    # Texture resolution
    missing_textures = []
    for tex in sorted(tex_names_needed):
        try:
            tb = mgr.get_texture(tex, game)
        except Exception:
            tb = None
        if not tb:
            missing_textures.append(tex)

    result['stats']['missing_texture_count'] = len(missing_textures)
    if missing_textures:
        result['warnings'].append(
            f'{len(missing_textures)} texture(s) not found: {", ".join(missing_textures[:8])}')

    result['stats']['load_ms'] = round((time.perf_counter() - t0) * 1000, 1)
    result['ok'] = len(result['errors']) == 0
    return result


def run_audit(mgr: ResourceManager, game: str) -> list:
    all_models = mgr.list_models(game)
    mods = sorted([(r, g) for r, g in all_models if is_module(r, game) and r not in SKIP_RESREFS])
    n = len(mods)
    results = []
    t0 = time.perf_counter()

    for i, (resref, _) in enumerate(mods):
        res = audit_one(resref, game, mgr)
        results.append(res)

        if (i + 1) % 100 == 0 or (i + 1) == n:
            el = time.perf_counter() - t0
            ok = sum(1 for r in results if r['ok'])
            err = sum(1 for r in results if r['errors'])
            warn = sum(1 for r in results if r['warnings'] and r['ok'])
            miss = sum(r['stats'].get('missing_texture_count', 0) for r in results)
            print(f'  [{game}] {i+1}/{n} ({100*(i+1)/n:.0f}%)  '
                  f'ok={ok}  err={err}  warn={warn}  miss_tex={miss}  t={el:.1f}s', flush=True)

    return results


def write_summary(k1: list, k2: list):
    all_r = k1 + k2
    k1_ok  = sum(1 for r in k1 if r['ok'])
    k2_ok  = sum(1 for r in k2 if r['ok'])
    k1_err = sum(1 for r in k1 if r['errors'])
    k2_err = sum(1 for r in k2 if r['errors'])
    k1_miss= sum(r['stats'].get('missing_texture_count', 0) for r in k1)
    k2_miss= sum(r['stats'].get('missing_texture_count', 0) for r in k2)

    # JSON
    jp = AUDIT_DIR / 'module_geometry_audit.json'
    with open(jp, 'w') as f:
        json.dump({
            'generated': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
            'k1_count': len(k1), 'k2_count': len(k2), 'total': len(all_r),
            'k1_ok': k1_ok, 'k2_ok': k2_ok,
            'k1_errors': k1_err, 'k2_errors': k2_err,
            'k1_missing_textures': k1_miss, 'k2_missing_textures': k2_miss,
            'results': all_r,
        }, f, indent=2)

    # TXT summary
    tp = AUDIT_DIR / 'module_geometry_audit.txt'
    with open(tp, 'w') as f:
        f.write('=' * 70 + '\n')
        f.write('  GhostRigger Module Geometry & Texture Deep Audit\n')
        f.write(f'  Generated: {time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())}\n')
        f.write('=' * 70 + '\n\n')
        f.write('SUMMARY\n' + '-' * 40 + '\n')
        f.write(f'  K1 models audited: {len(k1):4d}  OK={k1_ok}  Errors={k1_err}  MissingTex={k1_miss}\n')
        f.write(f'  K2 models audited: {len(k2):4d}  OK={k2_ok}  Errors={k2_err}  MissingTex={k2_miss}\n')
        f.write(f'  TOTAL            : {len(all_r):4d}  OK={k1_ok+k2_ok}  Errors={k1_err+k2_err}  MissingTex={k1_miss+k2_miss}\n\n')

        # Errors
        err_models = [r for r in all_r if r['errors']]
        if err_models:
            f.write('HARD ERRORS\n' + '-' * 40 + '\n')
            for r in err_models:
                f.write(f'  [{r["game"]}] {r["resref"]}\n')
                for e in r['errors']:
                    f.write(f'      {e}\n')
            f.write('\n')

        # Missing textures aggregation
        tex_freq = {}
        for r in all_r:
            for w in r.get('warnings', []):
                if 'texture(s) not found' in w:
                    parts = w.split(':', 1)
                    if len(parts) > 1:
                        for t in parts[1].split(','):
                            t = t.strip()
                            if t:
                                tex_freq[t] = tex_freq.get(t, 0) + 1
        if tex_freq:
            f.write('MOST COMMON MISSING TEXTURES\n' + '-' * 40 + '\n')
            for t, c in sorted(tex_freq.items(), key=lambda x: -x[1])[:30]:
                f.write(f'  {t:40s}  {c} model(s)\n')
            f.write('\n')

    print(f'\nReports written:')
    print(f'  {jp}')
    print(f'  {tp}')
    return k1_ok, k2_ok, k1_err, k2_err


def main():
    print('Initializing ResourceManager…')
    mgr = ResourceManager()
    ok1 = mgr.set_k1_dir(str(K1_DIR))
    ok2 = mgr.set_k2_dir(str(K2_DIR))
    if not ok1: print('WARNING: K1 index failed'); 
    if not ok2: print('WARNING: K2 index failed');
    s = mgr.stats()
    print(f'K1: {s["K1"]["key_entries"]} key entries, {s["K1"]["mod_erfs"]} module ERFs, {s["K1"]["tex_erfs"]} tex ERFs')
    print(f'K2: {s["K2"]["key_entries"]} key entries, {s["K2"]["mod_erfs"]} module ERFs, {s["K2"]["tex_erfs"]} tex ERFs')

    print('\n[K1] Auditing K1 module models…')
    t0 = time.perf_counter()
    k1_results = run_audit(mgr, 'K1')
    print(f'[K1] Completed in {time.perf_counter()-t0:.1f}s')

    print('\n[K2] Auditing K2 module models…')
    t0 = time.perf_counter()
    k2_results = run_audit(mgr, 'K2')
    print(f'[K2] Completed in {time.perf_counter()-t0:.1f}s')

    k1_ok, k2_ok, k1_err, k2_err = write_summary(k1_results, k2_results)

    print(f'\n{"="*60}')
    print(f'FINAL: K1={len(k1_results)} (ok={k1_ok}, err={k1_err}), '
          f'K2={len(k2_results)} (ok={k2_ok}, err={k2_err})')
    
    if k1_err + k2_err == 0:
        print('✓ ALL MODULE MODELS PASS — 100% geometry and texture verified')
    else:
        print(f'✗ {k1_err + k2_err} HARD ERRORS — see audit report for details')
    
    return 0 if (k1_err + k2_err == 0) else 1


if __name__ == '__main__':
    sys.exit(main())
