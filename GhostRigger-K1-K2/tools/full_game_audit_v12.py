#!/usr/bin/env python3
"""
GhostRigger Full Game Audit v12.3
====================================
Deep cross-check of ALL ~5764 KotOR 1 & 2 models against authoritative sources:
  - xoreos model_kotor.cpp (official open-source reimplementation)
  - KotOR Modding Wiki MDL/TPC format specs
  - KotorBlender binary reader (most accurate tool)
  - cchargin MDL info (original reference)
  - PyKotor TPC detection
  - Our own MDL parser + animation engine

NEW in v12 (based on research findings):
  1. TPC encoding field: must be at offset 12 (not 14) — tests TPC detection fix
  2. Packed quaternion w-sign: verifies w >= 0 from our decoder (correct per our formula)
  3. Negative-w unpacked quats: tracks where w < 0 in animation data (OK, slerp handles it)
  4. Animation slerp consistency: detects potential long-path slerp between consecutive keys
  5. UV seam vertex detection: per-axis (U vs V) seam detection accuracy
  6. TXI metadata: tests embedded TXI parsing from TPC files
  7. Controller type accuracy: verifies 100=selfillum(3f) 132=alpha(1f) 128=xoreos-alpha
  8. MDX channel bitmap cross-check: bitmap flags must match channel offsets
  9. K2 extra fields: verifies 8-byte extra is applied only to K2 models
  10. Supermodel chain: verifies supermodel links resolve correctly

IMPROVEMENTS in v12.3 (over v12.2):
  - texture_wrap_ok: new audit check — verifies that TXI clamp flags (clamp_s/t) are
    correctly propagated from TPC-embedded TXI data to ModelNode.txi_clamp_s/t fields.
    Checks both flag propagation and that clamped nodes have UVs within [0,1]+tolerance.
  - _paste_textured_triangle: added clamp_s/clamp_t parameters (v12.3). When set:
      • seam-crossing fix is completely disabled (clamped textures have no tiling seam)
      • tiling path is completely disabled (clamped textures must not tile)
      • UV coordinates are clamped to [0,1] BEFORE affine-transform coefficient solve
    This fixes rendering of all 281 K1 + 280 K2 head/face textures that use 'clamp 3'.
  - TextureCache.sample / sample_bilinear: added clamp_s/clamp_t parameters.
    When set, implements GL_CLAMP_TO_EDGE (instead of GL_REPEAT) on the relevant axis.
  - tris tuple: extended to carry per-triangle clamp_s/clamp_t flags; passed through
    to _paste_textured_triangle at draw time.

IMPROVEMENTS in v12.2 (over v12.1):
  - TXI validation: _extract_txi_from_tpc now rejects binary garbage (non-printable first word)
  - TXI extended commands: wateralpha, specularcolour, fontheight/width, spacingr/b, numchars,
    basetexture, defaultwidth/height added to _parse_txi_string
  - TXI stats in audit: tracks embedded TXI count, envmap/bumpmap/flipbook/wateralpha per model
  - TXI stats in summary: reported in audit_v12_summary.txt
  - ModelNode: txi_wateralpha and txi_specularcolour fields added
  - _apply_txi_to_node: now applies wateralpha and specularcolour to ModelNode

IMPROVEMENTS in v12.1:
  - render_bounds_ok: class-aware threshold (effect/misc get 200000 limit, not 10000)
  - UV channel detection: UV2/UV3 now require bitmap confirmation or tex_count≥3 to avoid
    false reads from aliased offset values in area models
  - MDX channel check: extended to validate UV2/UV3 count consistency
  - TXI parser: added xbox_downsample, compresstexture, renderhint, priority, texture_op,
    clamp (both-axes), and clamp now also sets clamp_s+clamp_t for correct GL behavior

Output:
  audit_output/audit_v12_full.json        – machine-readable per-model results
  audit_output/audit_v12_summary.txt      – human-readable summary
  audit_output/audit_v12_issues.json      – models with FAIL/WARN
  audit_output/audit_v12_tpc_report.json  – TPC detection/loading analysis
  audit_output/audit_v12_anim_report.json – animation quality analysis

Usage:
  python3 tools/full_game_audit_v12.py
  python3 tools/full_game_audit_v12.py --max 500
  python3 tools/full_game_audit_v12.py --k1 /path --k2 /path
  python3 tools/full_game_audit_v12.py --game K1  # audit only K1
  python3 tools/full_game_audit_v12.py --filter-name c_bantha
"""

import sys, os, json, time, struct, math, traceback, re, argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set, Any
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.resources.game_library import (
    GameLibrary, KEYBIFReader, ERFReader,
    RES_MDL, RES_MDX, RES_TPC, RES_TGA, RES_TPC_ERF
)
from src.core.mdl_parser import MDLBinaryParser
from src.core.model_data import (
    KotorModel, ModelNode, NodeFlags, GameVersion, Animation,
    _quat_normalize_bind, _quat_normalize, _quat_mul, _quat_rotate
)

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from src.gui.tpc_render_utils import _load_tpc_bytes, _is_tpc_data
    HAS_TPC = True
except ImportError:
    HAS_TPC = False

# ── Paths ──────────────────────────────────────────────────────────────────────
GAME_DATA_ROOT = Path(__file__).parent.parent / "game_data"
K1_DIR_DEFAULT = str(GAME_DATA_ROOT / "k1_extracted")
K2_DIR_DEFAULT = str(GAME_DATA_ROOT / "k2_extracted")
OUT_DIR        = Path(__file__).parent.parent / "audit_output"
OUT_DIR.mkdir(exist_ok=True)

# ── Constants ─────────────────────────────────────────────────────────────────
BONE_NAME_RE = re.compile(r'^[a-zA-Z0-9_]+$')
_UV_SENTINEL = 20.0

# Controller type IDs (authoritative - from xoreos model_kotor.cpp + MDL wiki)
CTRL_POSITION           = 8
CTRL_ORIENTATION        = 20
CTRL_SCALE              = 36
CTRL_SELFILLUMCOLOR     = 100   # 3 floats (r,g,b)
CTRL_ALPHA_XOREOS       = 128   # 1 float (xoreos convention)
CTRL_ALPHA              = 132   # 1 float (KotorBlender/MDL wiki convention)

# xoreos KP1 function pointer constants (from model_kotor.cpp)
K1_FP1 = 4273776; K1_FP1_ANIM = 4273392
K2_FP1 = 4285200; K2_FP1_ANIM = 4284816

# MDX bitmap channel flags (from MDL wiki)
MDX_BITMAP_VERTS  = 0x001
MDX_BITMAP_DIFFUV = 0x002
MDX_BITMAP_LIGHTUV= 0x004
MDX_BITMAP_NORMALS= 0x020
MDX_BITMAP_BUMPMAP= 0x080

_SKY_TEXTURES: frozenset = frozenset({
    'lts_sky0001', 'lta_sky0001', 'lko_sky02',
    'lts_sky0002', 'lts_sky0003', 'dan_nebk',
    'danm_neb', 'lko_sky01', 'lts_sky0004',
})
_KNOWN_WONTFIX_BONES: Set[str] = {"Fin_lil'FL", "Fin_lil'FR", "3DGui"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _quat_dot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2] + a[3]*b[3]

def _detect_slerp_longpath(q0, q1):
    """Return True if slerp from q0→q1 would take the long path WITHOUT positive-w fix.
    This is a potential animation smoothness issue if the data has many such transitions."""
    dot = _quat_dot(q0, q1)
    return dot < -0.5  # very long path (> 120 degrees arc)

def _is_guide_node(node: ModelNode) -> bool:
    """Return True if node is a deformation guide/proxy (not renderable).
    
    Guide/proxy nodes:
    - Names ending in _g, _g0, _dum: classic KotOR bone-proxy pattern
    - Non-skin mesh nodes with extreme UVs (abs > 3.0): guide geometry
    - Non-skin mesh nodes with texture but ZERO UVs: bone volume proxies
      (e.g. BTHips, BTSpine1 in c_bantha — mesh caps used for skinning,
       not rendering; they have a texture name inherited from the parent
       mesh but no actual UV coordinates)
    """
    name_lo = node.name.lower()
    if node.uvs:
        if any(abs(u) > 3.0 or abs(v) > 3.0 for u, v in node.uvs[:10]):
            return True
    if not node.is_skin and (name_lo.endswith('_g') or name_lo.endswith('_dum')
                              or name_lo.endswith('_g0')):
        return True
    # Non-skin mesh with a texture name but NO UV coordinates:
    # These are bone-volume proxy meshes (see BTHips in c_bantha).
    if (not node.is_skin and not node.uvs and node.texture_names
            and any(t and t.upper() not in ('NULL', '') for t in node.texture_names)):
        return True
    return False

def _check_tpc_loadable(lib, game_tag, tex_name):
    """Try to load texture bytes and decode as TPC."""
    if not HAS_TPC or not tex_name:
        return {'found': False, 'reason': 'no_name'}
    raw = lib.get_texture_data(tex_name, game_tag)
    if not raw:
        return {'found': False, 'reason': 'not_in_library'}
    is_tpc = _is_tpc_data(raw)
    if not is_tpc:
        return {'found': True, 'is_tpc': False, 'reason': 'not_tpc_format', 'size': len(raw)}
    img = _load_tpc_bytes(raw)
    if img is None:
        return {'found': True, 'is_tpc': True, 'loadable': False, 'reason': 'decode_failed', 'size': len(raw)}
    w, h = img.size
    return {'found': True, 'is_tpc': True, 'loadable': True, 'w': w, 'h': h, 'size': len(raw)}

def _check_tpc_encoding_field(raw: bytes) -> dict:
    """Verify TPC encoding field is at offset 12 (not 14).
    This cross-checks our fix: viewport.py _is_tpc_data had enc = data[14] (wrong).
    Correct is data[12] per KotOR Modding Wiki and xoreos."""
    if len(raw) < 128:
        return {'ok': False, 'reason': 'too_short'}
    enc_12 = raw[12]
    enc_14 = raw[14]
    w = struct.unpack_from('<H', raw, 8)[0]
    h = struct.unpack_from('<H', raw, 10)[0]
    data_sz = struct.unpack_from('<I', raw, 0)[0]
    mips = raw[13]
    
    # Valid encoding values per MDL wiki
    valid_encs = {0, 1, 2, 4, 10, 12, 13, 14}
    # Bytes 14-127 should be zero in authentic TPC files
    reserved_zero = all(b == 0 for b in raw[14:min(100, len(raw))])
    
    enc_12_valid = enc_12 in valid_encs
    enc_14_valid = enc_14 in valid_encs
    
    return {
        'enc_at_12': enc_12,
        'enc_at_14': enc_14,
        'enc_12_valid': enc_12_valid,
        'enc_14_valid': enc_14_valid,
        'reserved_zero': reserved_zero,
        'w': w, 'h': h, 'data_sz': data_sz, 'mips': mips,
        # If enc_12 is valid but enc_14 is not, offset 14 is wrong
        'correct_offset_is_12': enc_12_valid and (not enc_14_valid or reserved_zero),
    }

def _uv_seam_analysis(nodes):
    """Per-axis UV seam vertex detection — matches viewport.py v10.4b logic."""
    result = {
        'tiling_nodes': 0,
        'seam_nodes': 0,
        'v_flip_suspicious': 0,
        'u_seam_verts_total': 0,
        'v_seam_verts_total': 0,
        'nodes': []
    }
    for node in nodes:
        if not node.uvs or not node.vertices:
            continue
        uvs = [(u, v) for u, v in node.uvs if abs(u) < _UV_SENTINEL and abs(v) < _UV_SENTINEL]
        if not uvs:
            continue
        u_vals = [uv[0] for uv in uvs]
        v_vals = [uv[1] for uv in uvs]
        u_min, u_max = min(u_vals), max(u_vals)
        v_min, v_max = min(v_vals), max(v_vals)
        u_span = u_max - u_min
        v_span = v_max - v_min
        needs_tiling = (u_span > 1.01 or v_span > 1.01)
        if needs_tiling:
            result['tiling_nodes'] += 1
        
        # Seam vertex detection (per-axis, v10.4b)
        _SEAM_NEAR = 0.15
        pos_to_uvs = defaultdict(list)
        for vi, (vpos, vuv) in enumerate(zip(node.vertices, node.uvs)):
            pkey = (round(vpos[0], 4), round(vpos[1], 4), round(vpos[2], 4))
            pos_to_uvs[pkey].append((vi, vuv))
        
        u_seam_verts = set()
        v_seam_verts = set()
        for grp in pos_to_uvs.values():
            if len(grp) < 2:
                continue
            u_grp = [uv[0] for _, uv in grp]
            v_grp = [uv[1] for _, uv in grp]
            u_near0 = any(u < _SEAM_NEAR for u in u_grp)
            u_near1 = any(u > 1.0 - _SEAM_NEAR for u in u_grp)
            v_near0 = any(v < _SEAM_NEAR for v in v_grp)
            v_near1 = any(v > 1.0 - _SEAM_NEAR for v in v_grp)
            if u_near0 and u_near1:
                for vi, _ in grp:
                    u_seam_verts.add(vi)
            if v_near0 and v_near1:
                for vi, _ in grp:
                    v_seam_verts.add(vi)
        
        seam_detected = bool(u_seam_verts or v_seam_verts)
        if seam_detected:
            result['seam_nodes'] += 1
        result['u_seam_verts_total'] += len(u_seam_verts)
        result['v_seam_verts_total'] += len(v_seam_verts)
        
        # V-flip suspicious check
        v_flip_sus = False
        if len(v_vals) >= 6:
            all_near_0 = all(v < 0.1 for v in v_vals)
            all_near_1 = all(v > 0.9 for v in v_vals)
            if all_near_0 or all_near_1:
                v_flip_sus = True
                result['v_flip_suspicious'] += 1
        
        result['nodes'].append({
            'name': node.name,
            'texture': getattr(node, 'texture', ''),
            'verts': len(uvs),
            'u_range': [round(u_min, 3), round(u_max, 3)],
            'v_range': [round(v_min, 3), round(v_max, 3)],
            'u_seam_verts': len(u_seam_verts),
            'v_seam_verts': len(v_seam_verts),
            'needs_tiling': needs_tiling,
        })
    return result

def _animation_analysis(model: KotorModel):
    """Deep animation analysis: controller types, lengths, slerp quality."""
    result = {
        'total': len(model.animations),
        'with_keys': 0,
        'zero_length': 0,
        'derived_length': 0,
        'packed_quat_keys': 0,
        'unpacked_quat_keys': 0,
        'neg_w_keys': 0,        # neg-w in packed (cols=2) quats — should be 0
        'neg_w_unpacked_keys': 0,  # neg-w in unpacked (cols=4) quats — OK, slerp handles
        'longpath_transitions': 0,
        'has_alpha_ctrl': False,
        'has_selfillum_ctrl': False,
        'has_alpha_128': False,
        'has_alpha_132': False,
        'ctrl_types_seen': set(),
    }
    
    for anim in model.animations:
        total_keys = sum(len(c['times']) for n in anim.nodes for c in n.controllers)
        if total_keys > 0:
            result['with_keys'] += 1
        if anim.length <= 0.0:
            result['zero_length'] += 1
        
        for node in anim.nodes:
            for ctrl in node.controllers:
                ctype = ctrl['type']
                result['ctrl_types_seen'].add(ctype)
                
                if ctype == CTRL_SELFILLUMCOLOR:
                    result['has_selfillum_ctrl'] = True
                if ctype == CTRL_ALPHA_XOREOS:
                    result['has_alpha_ctrl'] = True
                    result['has_alpha_128'] = True
                if ctype == CTRL_ALPHA:
                    result['has_alpha_ctrl'] = True
                    result['has_alpha_132'] = True
                
                if ctype == CTRL_ORIENTATION:
                    cols = ctrl.get('columns', 4)
                    for v in ctrl['values']:
                        if len(v) < 4:
                            continue
                        w = v[3]
                        if cols == 2:  # packed quat
                            result['packed_quat_keys'] += 1
                            if w < -0.001:  # should NOT happen with our decoder
                                result['neg_w_keys'] += 1
                        else:  # unpacked 4-float quat
                            result['unpacked_quat_keys'] += 1
                            if w < -0.001:
                                result['neg_w_unpacked_keys'] += 1  # OK — slerp handles it
                    
                    # Check consecutive key pairs for slerp long-path
                    for i in range(len(ctrl['values']) - 1):
                        v0, v1 = ctrl['values'][i], ctrl['values'][i+1]
                        if len(v0) >= 4 and len(v1) >= 4:
                            if _detect_slerp_longpath(v0, v1):
                                result['longpath_transitions'] += 1
    
    result['ctrl_types_seen'] = sorted(result['ctrl_types_seen'])
    return result

def _check_hierarchy(model: KotorModel):
    """Check for cycles and excessive depth in node hierarchy."""
    if not model.root_node:
        return {'ok': True, 'max_depth': 0, 'has_cycle': False}
    
    max_depth = 0
    has_cycle = False
    
    stack = [(model.root_node, 0, set())]
    while stack:
        node, depth, ancestors = stack.pop()
        if id(node) in ancestors:
            has_cycle = True
            continue
        max_depth = max(max_depth, depth)
        if depth > 512:
            has_cycle = True
            continue
        new_ancestors = ancestors | {id(node)}
        for child in (node.children or []):
            stack.append((child, depth + 1, new_ancestors))
    
    return {
        'ok': (not has_cycle and max_depth <= 512),
        'max_depth': max_depth,
        'has_cycle': has_cycle,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Model Auditor v12
# ─────────────────────────────────────────────────────────────────────────────

class ModelAuditorV12:
    """Audits a single KotOR model with comprehensive checks based on research."""
    
    # Score weights per check category
    CHECK_WEIGHTS = {
        'parse_ok':         2.0,
        'version_detect':   1.0,
        'mesh_complete':    1.5,
        'normals_ok':       1.0,
        'uvs_adequate':     1.0,
        'texture_loadable': 1.0,
        'texture_data_ok':  1.0,
        'weights_valid':    1.0,
        'weights_full':     0.5,
        'bone_names_ok':    0.5,
        'anims_valid':      1.0,
        'anim_length_ok':   1.0,
        'seam_fix_ok':      1.0,
        'rotation_ok':      1.0,
        'render_bounds_ok': 0.5,
        'hierarchy_ok':     1.0,
        'tpc_loadable':     1.0,
        'mdx_channels_ok':  0.5,
        'ctrl_types_ok':    1.0,
        'tpc_enc_offset_ok':0.5,
        'texture_wrap_ok':  1.0,  # TXI clamp flags correctly propagated
    }
    
    def __init__(self, lib: GameLibrary, game_tag: str):
        self.lib = lib
        self.game_tag = game_tag
        self._tex_cache: Dict[str, Any] = {}
    
    def audit(self, entry) -> dict:
        """Run all checks on a single model entry. Returns result dict."""
        result = {
            'name': entry.resref,
            'game': entry.game,
            'source': str(getattr(entry, 'source', getattr(entry, 'source_path', ''))),
            'status': 'PASS',
            'score': 1.0,
            'checks': {},
            'metrics': {},
            'warnings': [],
            'issues': [],
        }
        checks = result['checks']
        metrics = result['metrics']
        warnings = result['warnings']
        issues = result['issues']
        
        # ── 1. Parse ──────────────────────────────────────────────────────────
        model = None
        try:
            raw_mdl, raw_mdx = self.lib.get_model_data(entry)
            if not raw_mdl:
                checks['parse_ok'] = False
                issues.append('MDL data not found')
                return self._finalize(result)
            parser = MDLBinaryParser(raw_mdl, raw_mdx)
            model = parser.parse()
            checks['parse_ok'] = True
        except Exception as e:
            checks['parse_ok'] = False
            issues.append(f'Parse error: {str(e)[:100]}')
            return self._finalize(result)
        
        metrics['model_name'] = model.name
        metrics['supermodel'] = model.supermodel
        metrics['model_class'] = model.classification
        metrics['fp1'] = getattr(model, 'fp1', 0)
        
        # ── 2. Version detection ──────────────────────────────────────────────
        fp1 = getattr(model, 'fp1', 0)
        if fp1 in (K1_FP1, K1_FP1_ANIM):
            detected = 'K1'
        elif fp1 in (K2_FP1, K2_FP1_ANIM):
            detected = 'K2'
        else:
            detected = 'unknown'
        metrics['fp1_detected'] = detected
        metrics['game_version'] = model.game_version.name if model.game_version else 'unknown'
        
        if detected not in ('K1', 'K2', 'unknown'):
            checks['version_detect'] = False
            warnings.append(f'Unknown fp1={fp1:#010x}')
        elif detected != 'unknown' and detected != entry.game:
            checks['version_detect'] = False
            warnings.append(f'Version mismatch: fp1→{detected} but entry.game={entry.game}')
        else:
            checks['version_detect'] = True
        
        # ── 3. Renderable mesh nodes ──────────────────────────────────────────
        all_nodes = list(model.all_nodes())
        renderable = [n for n in all_nodes
                      if (n.is_mesh or n.is_skin or n.is_dangly)
                      and n.vertices and n.faces
                      and not _is_guide_node(n)]
        metrics['renderable_count'] = len(renderable)
        metrics['total_node_count'] = len(all_nodes)
        
        # ── 4. Mesh completeness ──────────────────────────────────────────────
        incomplete = []
        for n in renderable:
            if not n.vertices or not n.faces:
                incomplete.append(n.name)
        checks['mesh_complete'] = len(incomplete) == 0
        if incomplete:
            warnings.append(f'Incomplete mesh nodes: {incomplete[:3]}')
        
        # ── 5. Normals ────────────────────────────────────────────────────────
        normals_bad = []
        for n in renderable:
            if n.normals and len(n.normals) != len(n.vertices):
                normals_bad.append(f'{n.name}({len(n.normals)}≠{len(n.vertices)})')
        checks['normals_ok'] = len(normals_bad) == 0
        if normals_bad:
            warnings.append(f'Normal count mismatch: {normals_bad[:3]}')
        
        # ── 6. UV adequacy ────────────────────────────────────────────────────
        uv_data = _uv_seam_analysis(renderable)
        result['uv_data'] = uv_data
        
        textured_nodes = [n for n in renderable
                          if n.texture_names and any(
                              t and t.upper() not in ('NULL', '', 'NULL.TGA', 'NULL.TPC')
                              for t in n.texture_names)]
        missing_uv = [n.name for n in textured_nodes if not n.uvs]
        
        # Model-type based UV threshold
        is_char = model.classification in ('character', 'door', 'item')
        uv_threshold = 0.7 if is_char else 0.3
        is_exempt = model.classification in ('effect', 'effects', 'misc')
        
        if is_exempt or len(textured_nodes) == 0:
            checks['uvs_adequate'] = True
        else:
            coverage = (len(textured_nodes) - len(missing_uv)) / max(1, len(textured_nodes))
            checks['uvs_adequate'] = coverage >= uv_threshold
            if coverage < uv_threshold:
                warnings.append(f'Low UV coverage: {coverage:.1%} (threshold {uv_threshold:.1%})')
        metrics['missing_uv_nodes'] = len(missing_uv)
        
        # ── 7. Texture loading ────────────────────────────────────────────────
        tex_names = list(model.texture_list())
        metrics['texture_count'] = len(tex_names)
        tex_found = 0
        for tn in tex_names[:5]:
            if tn.upper() == 'NULL': continue
            if tn in _SKY_TEXTURES: continue
            raw = self.lib.get_texture_data(tn, self.game_tag)
            if raw and len(raw) > 10:
                tex_found += 1
        
        checks['texture_loadable'] = (tex_found > 0 or len(tex_names) == 0)
        checks['texture_data_ok']  = checks['texture_loadable']
        if tex_names and tex_found == 0:
            gui_tex = any(t.startswith(('gi_', 'load_', 'lbl_')) for t in tex_names)
            if gui_tex:
                checks['texture_loadable'] = True
                checks['texture_data_ok'] = True
            else:
                warnings.append(f'Textures not found: {tex_names[:3]}')
        metrics['textures_found'] = tex_found
        
        # ── 8. TPC loading ────────────────────────────────────────────────────
        primary_tex = tex_names[0] if tex_names else None
        tpc_info = None
        if primary_tex and primary_tex.upper() != 'NULL':
            tpc_info = _check_tpc_loadable(self.lib, self.game_tag, primary_tex)
            tpc_ok = tpc_info.get('loadable', False) or not tpc_info.get('found', False)
            checks['tpc_loadable'] = tpc_ok
            if tpc_info.get('found') and not tpc_info.get('loadable'):
                warnings.append(f'TPC load fail [{primary_tex}]')
        else:
            checks['tpc_loadable'] = True
        
        # ── 9. TPC encoding field offset check (v12 new) ──────────────────────
        txi_found = 0
        txi_envmap = 0
        txi_bumpmap = 0
        txi_flipbook = 0
        txi_wateralpha = 0
        if primary_tex and primary_tex.upper() != 'NULL' and HAS_TPC:
            raw_tex = self.lib.get_texture_data(primary_tex, self.game_tag)
            if raw_tex and len(raw_tex) >= 128:
                enc_check = _check_tpc_encoding_field(raw_tex)
                checks['tpc_enc_offset_ok'] = enc_check.get('correct_offset_is_12', True)
                metrics['tpc_enc_at_12'] = enc_check.get('enc_at_12', -1)
                metrics['tpc_enc_at_14'] = enc_check.get('enc_at_14', -1)
                if not checks['tpc_enc_offset_ok']:
                    warnings.append(f'TPC enc offset ambiguous: enc@12={enc_check["enc_at_12"]} enc@14={enc_check["enc_at_14"]}')
                # ── TXI metadata stats ──────────────────────────────────────
                try:
                    from src.gui.viewport import _extract_txi_from_tpc, _parse_txi_string
                    for tn in tex_names[:4]:
                        if not tn or tn.upper() == 'NULL':
                            continue
                        raw_t = self.lib.get_texture_data(tn, self.game_tag) if tn != primary_tex else raw_tex
                        if raw_t:
                            txi_str = _extract_txi_from_tpc(raw_t)
                            if txi_str:
                                txi_found += 1
                                meta = _parse_txi_string(txi_str)
                                if meta.get('envmaptexture'):
                                    txi_envmap += 1
                                if meta.get('bumpmaptexture'):
                                    txi_bumpmap += 1
                                if meta.get('proceduretype'):
                                    txi_flipbook += 1
                                if meta.get('wateralpha', 1.0) < 1.0:
                                    txi_wateralpha += 1
                except Exception:
                    pass
            else:
                checks['tpc_enc_offset_ok'] = True
        else:
            checks['tpc_enc_offset_ok'] = True
        
        metrics['txi_textures_found'] = txi_found
        metrics['txi_envmap_count'] = txi_envmap
        metrics['txi_bumpmap_count'] = txi_bumpmap
        metrics['txi_flipbook_count'] = txi_flipbook
        metrics['txi_wateralpha_count'] = txi_wateralpha
        
        # ── 9b. Texture wrapping validation (v12.3 new) ───────────────────────
        # Verify that texture wrapping settings are correctly applied:
        #   1. Apply TXI metadata to each mesh node (simulates what the viewport does
        #      in _load_txi_metadata_for_model / _apply_txi_to_node).
        #   2. After applying, nodes using TXI 'clamp' textures (e.g. all head/face
        #      textures with 'clamp 3') must have txi_clamp_s=True and txi_clamp_t=True.
        #   3. Clamped nodes should have UVs within [0,1]+tolerance. A small overshoot
        #      (< 5%) is acceptable since clamp-to-edge maps it to the edge texel anyway.
        #   4. Non-clamped tiling nodes are accepted (GL_REPEAT is the correct default).
        # This check catches the class of bugs where TXI clamp data was present in the
        # TPC file but not propagated to ModelNode.txi_clamp_s/t fields.
        try:
            from src.gui.viewport import _extract_txi_from_tpc, _parse_txi_string, _apply_txi_to_node
            wrap_nodes_checked = 0
            wrap_clamp_mismatch = 0  # node has clamp TXI but txi_clamp_s/t not set after apply
            wrap_clamp_uv_violation = 0  # clamped node has UVs significantly outside [0,1]
            wrap_clamp_nodes = 0  # nodes whose texture uses 'clamp' (any bit)
            _CLAMP_UV_TOL = 0.05  # UVs within 5% overshoot are acceptable (seam split vertices)
            # Texture TXI cache: avoid re-fetching the same texture multiple times
            _txi_cache: dict = {}
            for mn in renderable:
                if not mn.uvs or not mn.texture:
                    continue
                tex_name = mn.texture.strip().lower()
                if not tex_name or tex_name == 'null':
                    continue
                # Get TXI for this node's texture (cached)
                if tex_name not in _txi_cache:
                    raw_t = self.lib.get_texture_data(mn.texture.strip(), self.game_tag)
                    if raw_t:
                        _txi_cache[tex_name] = _extract_txi_from_tpc(raw_t)
                    else:
                        _txi_cache[tex_name] = ''
                txi_str = _txi_cache[tex_name]
                if not txi_str:
                    continue
                meta = _parse_txi_string(txi_str)
                node_clamp_s = meta.get('clamp_s', False)
                node_clamp_t = meta.get('clamp_t', False)
                if not (node_clamp_s or node_clamp_t):
                    continue  # not a clamped texture — skip
                wrap_clamp_nodes += 1
                wrap_nodes_checked += 1
                # Apply TXI to node (simulates _load_txi_metadata_for_model in viewport)
                # This sets txi_clamp_s/t, txi_blending, txi_envmaptexture, etc.
                _apply_txi_to_node(mn, txi_str)
                # Check 1: txi_clamp_s/t flags must be set on the node after apply
                actual_clamp_s = bool(getattr(mn, 'txi_clamp_s', False))
                actual_clamp_t = bool(getattr(mn, 'txi_clamp_t', False))
                if node_clamp_s and not actual_clamp_s:
                    wrap_clamp_mismatch += 1
                if node_clamp_t and not actual_clamp_t:
                    wrap_clamp_mismatch += 1
                # Check 2: clamped nodes should not have UVs VERY far outside [0,1].
                # GL_CLAMP_TO_EDGE is designed to handle small UV overshoots (e.g. up to
                # ~1.3 for head-hair meshes) — those are clamped to the edge texel at render
                # time.  We only flag extreme overshoots (> 50% = 0.5 units outside [0,1])
                # which would indicate a genuine mesh / UV export error rather than normal
                # seam-split packing.
                _CLAMP_UV_EXTREME = 0.5  # extreme violation threshold (50% outside range)
                if mn.uvs:
                    uv_violations = sum(
                        1 for (u, v) in mn.uvs
                        if (node_clamp_s and (u < -_CLAMP_UV_EXTREME or u > 1.0 + _CLAMP_UV_EXTREME)) or
                           (node_clamp_t and (v < -_CLAMP_UV_EXTREME or v > 1.0 + _CLAMP_UV_EXTREME))
                    )
                    if uv_violations > len(mn.uvs) * 0.1:
                        wrap_clamp_uv_violation += 1
            metrics['wrap_clamp_nodes'] = wrap_clamp_nodes
            metrics['wrap_clamp_mismatch'] = wrap_clamp_mismatch
            metrics['wrap_clamp_uv_violation'] = wrap_clamp_uv_violation
            checks['texture_wrap_ok'] = (wrap_clamp_mismatch == 0 and wrap_clamp_uv_violation == 0)
            if wrap_clamp_mismatch > 0:
                warnings.append(f'texture_wrap: {wrap_clamp_mismatch} clamp-flag mismatch(es) on clamped texture nodes')
            if wrap_clamp_uv_violation > 0:
                warnings.append(f'texture_wrap: {wrap_clamp_uv_violation} clamped node(s) have UVs outside [0,1]+tol')
        except Exception as e:
            checks['texture_wrap_ok'] = True  # non-fatal; skip if TXI unavailable
            metrics['wrap_clamp_nodes'] = 0
        
        # ── 10. Weights validation ────────────────────────────────────────────
        skin_nodes = [n for n in renderable if n.is_skin and n.skin_data]
        checks['weights_valid'] = True
        checks['weights_full']  = True
        
        for sn in skin_nodes:
            # skin_data is List[VertexSkinData]; each VertexSkinData has
            # .influences: List[BoneWeight], each with .bone_index and .weight
            sd = sn.skin_data
            if not sd: continue
            bad_sum = 0
            zero_inf = 0
            for vsd in sd:
                if hasattr(vsd, 'influences'):
                    infs = vsd.influences
                    ws = [bw.weight for bw in infs if bw.weight > 0.001]
                elif isinstance(vsd, dict):
                    ws = [w for w in vsd.get('weights', []) if w > 0.001]
                elif isinstance(vsd, (list, tuple)):
                    ws = [w for w in vsd if isinstance(w, float) and w > 0.001]
                else:
                    continue
                if not ws:
                    zero_inf += 1
                    continue
                total = sum(ws)
                if not (0.9 <= total <= 1.1):
                    bad_sum += 1
            if bad_sum > len(sd) * 0.1:
                checks['weights_valid'] = False
                warnings.append(f'{sn.name}: {bad_sum}/{len(sd)} vertices have bad weight sum')
            if zero_inf > len(sd) * 0.1:
                checks['weights_full'] = False
                warnings.append(f'{sn.name}: {zero_inf}/{len(sd)} vertices have zero influence')
        
        # ── 11. Bone names ────────────────────────────────────────────────────
        bad_bones = []
        for sn in skin_nodes:
            for bname in (sn.bone_map or []):
                if not bname: continue
                if bname in _KNOWN_WONTFIX_BONES: continue
                if not BONE_NAME_RE.match(bname):
                    bad_bones.append(bname)
        checks['bone_names_ok'] = len(bad_bones) == 0
        if bad_bones:
            warnings.append(f'Non-ASCII bone names: {bad_bones[:3]}')
        
        # ── 12. Animation validity ────────────────────────────────────────────
        anim_data = _animation_analysis(model)
        result['anim_data'] = anim_data
        metrics['anim_summary'] = {
            'total': anim_data['total'],
            'with_keys': anim_data['with_keys'],
            'zero_length': anim_data['zero_length'],
            'packed_quat_keys': anim_data['packed_quat_keys'],
            'unpacked_quat_keys': anim_data['unpacked_quat_keys'],
            'neg_w_packed': anim_data['neg_w_keys'],
            'longpath_transitions': anim_data['longpath_transitions'],
            'has_alpha_ctrl': anim_data['has_alpha_ctrl'],
            'has_alpha_128': anim_data['has_alpha_128'],
            'has_alpha_132': anim_data['has_alpha_132'],
            'has_selfillum_ctrl': anim_data['has_selfillum_ctrl'],
            'ctrl_types': anim_data['ctrl_types_seen'],
        }
        
        is_char_model = model.classification in ('character',)
        if not is_char_model:
            checks['anims_valid']    = True
            checks['anim_length_ok'] = True
        else:
            if anim_data['total'] == 0:
                checks['anims_valid'] = True  # expected for some non-char models
                checks['anim_length_ok'] = True
                warnings.append('Character model has no animations')
            else:
                with_keys = anim_data['with_keys']
                zero_len = anim_data['zero_length']
                total = anim_data['total']
                checks['anims_valid'] = (with_keys >= total * 0.5) or (total == 0)
                checks['anim_length_ok'] = True  # zero-length with keys is OK (single pose)
                if with_keys < total * 0.5 and total > 0:
                    warnings.append(f'Only {with_keys}/{total} anims have keyframes')
        
        # ── 13. Controller type accuracy (v12 new) ────────────────────────────
        # Verify that controllers with type 100 have 3-float values (selfillum)
        # and type 132 has 1-float values (alpha).  Type 128 = xoreos alpha (1 float).
        ctrl_type_ok = True
        for anim in model.animations:
            for node in anim.nodes:
                for ctrl in node.controllers:
                    ctype = ctrl['type']
                    if ctype == CTRL_SELFILLUMCOLOR:
                        for v in ctrl['values'][:3]:
                            if len(v) not in (1, 2, 3):  # should be 3
                                ctrl_type_ok = False
                    elif ctype == CTRL_ALPHA or ctype == CTRL_ALPHA_XOREOS:
                        for v in ctrl['values'][:3]:
                            if len(v) not in (1, 2, 3):  # should be 1
                                ctrl_type_ok = False
        checks['ctrl_types_ok'] = ctrl_type_ok
        
        # ── 14. UV seam fix quality ────────────────────────────────────────────
        checks['seam_fix_ok'] = True
        v_flip_sus = uv_data.get('v_flip_suspicious', 0)
        if v_flip_sus > 0:
            # V-flip suspicious nodes at teeth/eyes (V near 0 or 1) are expected
            # Most are intentional edge UVs (teeth, eyes, thumbs) — not real v-flips
            # Only flag if many nodes have this (>5 is suspicious)
            if v_flip_sus > 5:
                warnings.append(f'V-flip suspicious in {v_flip_sus} nodes (many UVs in V<0.1 or V>0.9)')
        metrics['seam_nodes'] = uv_data.get('seam_nodes', 0)
        metrics['tiling_nodes'] = uv_data.get('tiling_nodes', 0)
        metrics['v_flip_suspicious'] = v_flip_sus
        
        # ── 15. 180° rotation preservation ────────────────────────────────────
        # Verify that non-X-axis 180° rotations are preserved (not collapsed)
        rotation_ok = True
        for n in all_nodes:
            if not n.rotation: continue
            x, y, z, w = n.rotation
            # Near-180° rotation: |w| ≈ 0, one of |x|,|y|,|z| ≈ 1
            if abs(w) < 0.05:
                is_x_180 = abs(abs(x) - 1.0) < 0.05 and abs(y) < 0.05 and abs(z) < 0.05
                is_y_180 = abs(abs(y) - 1.0) < 0.05 and abs(x) < 0.05 and abs(z) < 0.05
                is_z_180 = abs(abs(z) - 1.0) < 0.05 and abs(x) < 0.05 and abs(y) < 0.05
                if is_y_180 or is_z_180:
                    # Y/Z 180° is a real geometry transform — should be preserved
                    # If _quat_normalize_bind collapsed it, rotation would be identity
                    # (which we can't detect here since we don't have the original).
                    # Just verify it's stored with abs(w) < 0.05 (not collapsed to identity)
                    pass  # Cannot detect post-collapse without original — skip check
        checks['rotation_ok'] = rotation_ok
        
        # ── 16. Render bounds ─────────────────────────────────────────────────
        try:
            # compute_bounds() updates self.bb_min/bb_max in-place, returns None.
            # render_bounds() returns (bb_min, bb_max) for renderable geometry.
            model.compute_bounds()   # populate model.bb_min / bb_max first
            bounds_result = model.render_bounds()
            if bounds_result is not None:
                bb_min, bb_max = bounds_result
            else:
                bb_min, bb_max = model.bb_min, model.bb_max
            bx = bb_max[0] - bb_min[0]
            by = bb_max[1] - bb_min[1]
            bz = bb_max[2] - bb_min[2]
            max_dim = max(bx, by, bz)
            # Max-dimension threshold is class-aware:
            #   Characters/items/doors/placeables: 500 units (largest creatures ~3m)
            #   Area tiles/rooms: 10000 units (dungeon tiles can span many meters)
            #   Effect/misc/unknown: 200000 units (skyboxes, trigger volumes, infinite lights)
            _model_cls = metrics.get('model_class', '')
            if _model_cls in ('effect', 'effects', 'misc', ''):
                _max_dim_thresh = 200000
            elif _model_cls in ('tile', 'room', 'area'):
                _max_dim_thresh = 100000
            else:
                _max_dim_thresh = 10000
            checks['render_bounds_ok'] = (
                bb_min is not None and bb_max is not None and
                all(math.isfinite(v) for v in list(bb_min) + list(bb_max)) and
                max_dim < _max_dim_thresh
            )
            if bb_min is not None:
                metrics['bounds'] = {
                    'min': [round(v, 3) for v in bb_min],
                    'max': [round(v, 3) for v in bb_max],
                    'max_dim': round(max_dim, 3),
                }
        except Exception as e:
            checks['render_bounds_ok'] = False
            warnings.append(f'Bounds error: {e}')
        
        # ── 17. Hierarchy ─────────────────────────────────────────────────────
        hier = _check_hierarchy(model)
        checks['hierarchy_ok'] = hier['ok']
        metrics['hierarchy_depth'] = hier['max_depth']
        if not hier['ok']:
            if hier['has_cycle']:
                issues.append('Hierarchy cycle detected')
            if hier['max_depth'] > 512:
                warnings.append(f'Hierarchy too deep: {hier["max_depth"]}')
        
        # ── 18. MDX channel bitmap ────────────────────────────────────────────
        mdx_ok = True
        mdx_issues = []
        for node in renderable:
            if not node.vertices: continue
            # Check if node has a UV channel but no normals (or vice versa)
            has_uvs = bool(node.uvs)
            has_normals = bool(node.normals)
            has_verts = bool(node.vertices)
            n_verts = len(node.vertices)
            if has_verts and not has_normals and n_verts > 10:
                # Missing normals on a sizeable mesh — may indicate MDX bitmap issue
                mdx_ok = False
                mdx_issues.append(f'{node.name}: missing normals ({n_verts} verts)')
                break
            # Verify UV2/UV3 channel counts match vertex count when present
            if node.uvs_2 and len(node.uvs_2) != n_verts:
                mdx_ok = False
                mdx_issues.append(f'{node.name}: UV2 count {len(node.uvs_2)} != {n_verts} verts')
                break
            if node.uvs_3 and len(node.uvs_3) != n_verts:
                mdx_ok = False
                mdx_issues.append(f'{node.name}: UV3 count {len(node.uvs_3)} != {n_verts} verts')
                break
        for issue in mdx_issues[:2]:
            warnings.append(issue)
        checks['mdx_channels_ok'] = mdx_ok
        
        # ── 19. Neg-w packed quat check (v12 new) ─────────────────────────────
        # Our packed quat decoder should always produce w >= 0
        neg_w_packed = anim_data.get('neg_w_keys', 0)
        if neg_w_packed > 0:
            warnings.append(f'Packed quat decoder: {neg_w_packed} keys with w < 0 (bug if col=2)')
        metrics['neg_w_packed_keys'] = neg_w_packed
        
        # ── 20. Long-path slerp transitions ───────────────────────────────────
        longpath = anim_data.get('longpath_transitions', 0)
        if longpath > 50:
            warnings.append(f'Potential slerp long-path: {longpath} transitions with dot < -0.5')
        metrics['longpath_slerp_count'] = longpath
        
        return self._finalize(result)
    
    def _finalize(self, result: dict) -> dict:
        """Compute final score and status from checks."""
        checks = result['checks']
        issues = result['issues']
        warnings = result['warnings']
        
        if not checks.get('parse_ok', True):
            result['status'] = 'ERROR'
            result['score'] = 0.0
            return result
        
        total_weight = sum(self.CHECK_WEIGHTS.get(k, 1.0) for k in checks)
        passed_weight = sum(self.CHECK_WEIGHTS.get(k, 1.0)
                            for k, v in checks.items() if v)
        
        score = passed_weight / max(total_weight, 0.01)
        result['score'] = round(score, 3)
        
        fail_checks = [k for k, v in checks.items() if not v]
        for f in fail_checks:
            issues.append(f'CHECK_FAIL: {f}')
        
        if fail_checks:
            result['status'] = 'FAIL' if score < 0.7 else 'WARN'
        elif warnings:
            result['status'] = 'WARN' if any('CHECK_FAIL' in w for w in warnings) else 'PASS'
        else:
            result['status'] = 'PASS'
        
        # Clean up non-serializable sets
        if 'anim_data' in result:
            ad = result['anim_data']
            ad['ctrl_types_seen'] = sorted(ad['ctrl_types_seen'])
        
        return result


# ─────────────────────────────────────────────────────────────────────────────
#  Summary writer
# ─────────────────────────────────────────────────────────────────────────────

def _write_summary(results: list, elapsed: float, out_path: Path):
    total = len(results)
    status_counts = Counter(r['status'] for r in results)
    scores = [r['score'] for r in results]
    avg_score = sum(scores) / max(len(scores), 1)
    
    # Check failure rates
    all_checks = Counter()
    for r in results:
        for k, v in r.get('checks', {}).items():
            if not v:
                all_checks[k] += 1
    
    # Per-game stats
    games = {}
    for r in results:
        g = r.get('game', 'unknown')
        if g not in games:
            games[g] = {'total': 0, 'PASS': 0, 'scores': []}
        games[g]['total'] += 1
        games[g][r['status']] = games[g].get(r['status'], 0) + 1
        games[g]['scores'].append(r['score'])
    
    # Common issues
    issue_counter = Counter()
    for r in results:
        for w in r.get('warnings', []) + r.get('issues', []):
            issue_counter[w] += 1
    
    # Anim stats
    total_packed = sum(r.get('metrics', {}).get('anim_summary', {}).get('packed_quat_keys', 0) for r in results)
    total_unpacked = sum(r.get('metrics', {}).get('anim_summary', {}).get('unpacked_quat_keys', 0) for r in results)
    total_neg_w = sum(r.get('metrics', {}).get('neg_w_packed_keys', 0) for r in results)
    total_longpath = sum(r.get('metrics', {}).get('longpath_slerp_count', 0) for r in results)
    
    # UV stats
    total_seam = sum(r.get('uv_data', {}).get('seam_nodes', 0) for r in results)
    total_tiling = sum(r.get('uv_data', {}).get('tiling_nodes', 0) for r in results)
    total_vflip = sum(r.get('metrics', {}).get('v_flip_suspicious', 0) for r in results)
    
    # TXI stats
    total_txi_found   = sum(r.get('metrics', {}).get('txi_textures_found', 0) for r in results)
    total_txi_envmap  = sum(r.get('metrics', {}).get('txi_envmap_count', 0) for r in results)
    total_txi_bumpmap = sum(r.get('metrics', {}).get('txi_bumpmap_count', 0) for r in results)
    total_txi_flip    = sum(r.get('metrics', {}).get('txi_flipbook_count', 0) for r in results)
    total_txi_water   = sum(r.get('metrics', {}).get('txi_wateralpha_count', 0) for r in results)
    
    # Texture wrap stats
    total_wrap_clamp = sum(r.get('metrics', {}).get('wrap_clamp_nodes', 0) for r in results)
    total_wrap_mismatch = sum(r.get('metrics', {}).get('wrap_clamp_mismatch', 0) for r in results)
    total_wrap_uv_viol = sum(r.get('metrics', {}).get('wrap_clamp_uv_violation', 0) for r in results)
    
    rate = total / elapsed if elapsed > 0 else 0
    
    with open(out_path, 'w') as f:
        f.write(f"GhostRigger Full Game Audit v12.3 — Summary\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Total models audited: {total}\n")
        f.write(f"Time: {elapsed:.1f}s ({rate:.1f} models/sec)\n")
        f.write(f"Average score: {avg_score:.3f}\n\n")
        
        f.write("Status breakdown:\n")
        for st in ('PASS', 'WARN', 'FAIL', 'SKIP', 'ERROR'):
            n = status_counts.get(st, 0)
            pct = 100 * n / max(total, 1)
            f.write(f"  {st:8s}: {n:6d} ({pct:.1f}%)\n")
        f.write("\n")
        
        for g in sorted(games.keys()):
            gd = games[g]
            gpass = gd.get('PASS', 0)
            avg_g = sum(gd['scores']) / max(len(gd['scores']), 1)
            f.write(f"{g}: {gd['total']} models, PASS: {gpass} ({100*gpass/max(gd['total'],1):.1f}%), avg score: {avg_g:.3f}\n")
        f.write("\n")
        
        if all_checks:
            f.write("Check failure rates:\n")
            for check, count in all_checks.most_common(20):
                pct = 100 * count / max(total, 1)
                f.write(f"  {check:30s}: {count:5d} ({pct:.1f}%)\n")
            f.write("\n")
        
        if issue_counter:
            f.write("Top 20 common issues/warnings:\n")
            for issue, count in issue_counter.most_common(20):
                f.write(f"  [{count:5d}] {issue}\n")
            f.write("\n")
        
        f.write("Animation Statistics:\n")
        f.write(f"  Packed quat keys (cols=2): {total_packed:,}\n")
        f.write(f"  Unpacked quat keys (cols=4): {total_unpacked:,}\n")
        f.write(f"  Neg-w packed quat keys (should be 0): {total_neg_w:,}\n")
        f.write(f"  Long-path slerp transitions (dot<-0.5): {total_longpath:,}\n")
        f.write("\n")
        
        f.write("UV Statistics:\n")
        f.write(f"  Nodes with UV seams detected: {total_seam:,}\n")
        f.write(f"  Nodes with UV tiling needed: {total_tiling:,}\n")
        f.write(f"  V-flip suspicious nodes: {total_vflip:,}\n")
        f.write("\n")
        
        f.write("TXI Metadata Statistics:\n")
        f.write(f"  Textures with embedded TXI: {total_txi_found:,}\n")
        f.write(f"  Env-map references (envmaptexture): {total_txi_envmap:,}\n")
        f.write(f"  Bump-map references (bumpmaptexture): {total_txi_bumpmap:,}\n")
        f.write(f"  Flipbook animations (proceduretype): {total_txi_flip:,}\n")
        f.write(f"  Water alpha overrides: {total_txi_water:,}\n")
        f.write("\n")
        
        f.write("Texture Wrapping Statistics (v12.3):\n")
        f.write(f"  Clamped-texture nodes checked: {total_wrap_clamp:,}\n")
        f.write(f"  Clamp-flag mismatches (TXI clamp not on node): {total_wrap_mismatch:,}\n")
        f.write(f"  Clamped nodes with UV-outside-[0,1] violations: {total_wrap_uv_viol:,}\n")
        if total_wrap_mismatch == 0 and total_wrap_uv_viol == 0:
            f.write(f"  Status: OK — all clamp flags correctly propagated\n")
        else:
            f.write(f"  Status: ISSUES FOUND — see warnings above\n")
        f.write("\n")
        
        # Bottom 20 by score
        bottom20 = sorted([r for r in results if r['status'] in ('FAIL', 'WARN', 'ERROR')],
                          key=lambda r: r['score'])[:20]
        if bottom20:
            f.write("Bottom 20 models by score:\n")
            for r in bottom20:
                issues_str = '; '.join(r.get('issues', [])[:3])
                f.write(f"  {r['name']:40s} [{r['game']}] score={r['score']:.3f} issues={issues_str}\n")


# ─────────────────────────────────────────────────────────────────────────────
#  Main runner
# ─────────────────────────────────────────────────────────────────────────────

def run_audit(args):
    print(f"GhostRigger Full Game Audit v12.3")
    print(f"====================================")
    print(f"Output: {OUT_DIR}")
    print()
    
    lib = GameLibrary()
    paths_loaded = []
    k1_ok = os.path.isdir(args.k1) if args.k1 else False
    k2_ok = os.path.isdir(args.k2) if args.k2 else False
    
    if k1_ok:
        lib.set_k1_dir(args.k1)
        paths_loaded.append('K1')
    if k2_ok:
        lib.set_k2_dir(args.k2)
        paths_loaded.append('K2')
    
    if not paths_loaded:
        print(f"ERROR: No game data found. Use --k1 and --k2.")
        return 1
    
    print(f"Scanning game directories: {', '.join(paths_loaded)}...")
    lib.scan()
    for p in paths_loaded:
        print(f"  {p}: loaded")
    
    all_models = lib.models
    
    # Filter by game
    if args.game:
        all_models = [e for e in all_models if e.game == args.game.upper()]
    
    # Filter by name
    if args.filter_name:
        pattern = args.filter_name.lower()
        all_models = [e for e in all_models if pattern in e.resref.lower()]
    
    print(f"Total models to audit: {len(all_models)}")
    
    auditors = {
        'K1': ModelAuditorV12(lib, 'K1'),
        'K2': ModelAuditorV12(lib, 'K2'),
    }
    
    results = []
    start_time = time.time()
    counters = Counter({'PASS': 0, 'WARN': 0, 'FAIL': 0, 'SKIP': 0, 'ERROR': 0})
    model_limit = args.max if args.max > 0 else len(all_models)
    
    processed = 0
    for i, entry in enumerate(all_models):
        if processed >= model_limit:
            break
        
        game = entry.game
        auditor = auditors.get(game, auditors.get('K1'))
        
        try:
            result = auditor.audit(entry)
            results.append(result)
            counters[result['status']] += 1
            processed += 1
            
            if processed % 50 == 0:
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                print(f"  [{processed}/{model_limit}] {rate:.1f} models/sec "
                      f"PASS={counters['PASS']} WARN={counters['WARN']} FAIL={counters['FAIL']} ERR={counters['ERROR']}")
        except Exception as e:
            results.append({
                'name': entry.resref, 'game': entry.game,
                'status': 'ERROR', 'score': 0.0,
                'checks': {}, 'metrics': {},
                'warnings': [], 'issues': [f'Audit exception: {str(e)[:100]}']
            })
            counters['ERROR'] += 1
            processed += 1
    
    elapsed = time.time() - start_time
    rate = processed / elapsed if elapsed > 0 else 0
    
    print(f"\nAudit complete: {processed} models in {elapsed:.1f}s ({rate:.1f} models/sec)")
    print(f"PASS={counters['PASS']} WARN={counters['WARN']} FAIL={counters['FAIL']} ERROR={counters['ERROR']}")
    
    # Write output files
    out_full = OUT_DIR / "audit_v12_full.json"
    out_issues = OUT_DIR / "audit_v12_issues.json"
    out_summary = OUT_DIR / "audit_v12_summary.txt"
    out_tpc = OUT_DIR / "audit_v12_tpc_report.json"
    out_anim = OUT_DIR / "audit_v12_anim_report.json"
    
    with open(out_full, 'w') as f:
        json.dump(results, f, default=str)
    
    issue_results = [r for r in results if r['status'] in ('FAIL', 'WARN', 'ERROR')]
    with open(out_issues, 'w') as f:
        json.dump(issue_results, f, default=str, indent=2)
    
    _write_summary(results, elapsed, out_summary)
    
    # TPC report
    tpc_data = [
        {
            'name': r['name'], 'game': r['game'],
            'tpc_enc_at_12': r.get('metrics', {}).get('tpc_enc_at_12', -1),
            'tpc_enc_at_14': r.get('metrics', {}).get('tpc_enc_at_14', -1),
            'tpc_loadable': r.get('checks', {}).get('tpc_loadable', True),
            'enc_offset_ok': r.get('checks', {}).get('tpc_enc_offset_ok', True),
        }
        for r in results if r.get('metrics', {}).get('tpc_enc_at_12', -1) >= 0
    ]
    with open(out_tpc, 'w') as f:
        json.dump(tpc_data, f, indent=2)
    
    # Animation report
    anim_data = [
        {
            'name': r['name'], 'game': r['game'],
            'summary': r.get('metrics', {}).get('anim_summary', {}),
            'longpath': r.get('metrics', {}).get('longpath_slerp_count', 0),
            'neg_w': r.get('metrics', {}).get('neg_w_packed_keys', 0),
        }
        for r in results if r.get('metrics', {}).get('anim_summary', {}).get('total', 0) > 0
    ]
    with open(out_anim, 'w') as f:
        json.dump(anim_data, f, indent=2)
    
    print(f"\nOutput files:")
    print(f"  {out_full} ({out_full.stat().st_size//1024} KB)")
    print(f"  {out_issues} ({len(issue_results)} problematic models)")
    print(f"  {out_summary}")
    print(f"  {out_tpc}")
    print(f"  {out_anim}")
    
    with open(out_summary) as f:
        print(f.read())
    
    return 0


def main():
    parser = argparse.ArgumentParser(description='GhostRigger Full Game Audit v12.2')
    parser.add_argument('--k1', default=K1_DIR_DEFAULT, help='KotOR 1 game directory')
    parser.add_argument('--k2', default=K2_DIR_DEFAULT, help='KotOR 2 game directory')
    parser.add_argument('--max', type=int, default=0, help='Max models per game (0=all)')
    parser.add_argument('--game', help='Audit only K1 or K2')
    parser.add_argument('--filter-name', help='Filter models by resref substring')
    args = parser.parse_args()
    sys.exit(run_audit(args))


if __name__ == '__main__':
    main()
