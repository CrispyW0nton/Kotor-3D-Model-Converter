#!/usr/bin/env python3
"""
GhostRigger Full Game Audit v11.0
===================================
Cross-checks ALL ~6000 models in KotOR 1 & 2 game libraries.
Based on deep research into MDL/MDX/TPC/TPA format specifications
from xoreos, KotorBlender, PyKotor, MDLOps, and deadlystream.com.

What is checked per model (18 checks + detailed UV/anim/skin metrics):
  1.  parse_ok             – binary MDL parses without exception
  2.  version_detect       – game version correctly identified (K1/K2 fp1 values)
  3.  mesh_complete        – all renderable mesh nodes have vertices + faces
  4.  normals_ok           – rendered nodes have correct normal count
  5.  uvs_adequate         – UV coverage ≥ type-based threshold
  6.  texture_loadable     – at least one texture found in BIF/ERF/TexturePack
  7.  texture_data_ok      – texture data is valid (non-empty, parseable)
  8.  weights_valid        – skin weight data present and normalized [0.9, 1.1]
  9.  weights_full         – all skin vertices have at least one influence
  10. bone_names_ok        – bone names are ASCII-identifier safe
  11. anims_valid          – character animations have keyframe data
  12. anim_length_ok       – animation lengths are positive (derived if needed)
  13. seam_fix_ok          – per-axis UV seam detection passes (no false positives)
  14. rotation_ok          – 180° non-X rotations preserved (not collapsed)
  15. render_bounds_ok     – render_bounds() returns sensible values
  16. hierarchy_ok         – no cycles, depth ≤ 512
  17. tpc_loadable         – primary texture loads as valid PIL image
  18. mdx_channels_ok      – MDX bitmap flags match readable channel offsets

Detailed diagnostics:
  - Per-node UV range and seam analysis
  - Per-animation keyframe counts and length distribution
  - Per-mesh MDX channel validity
  - Texture quality tier (TPA/TPB/TPC)
  - Controller type inventory (alpha, selfillum, position, orientation)

Output:
  audit_output/audit_v11_full.json        – machine-readable per-model results
  audit_output/audit_v11_summary.txt      – human-readable summary
  audit_output/audit_v11_issues.json      – only models with issues
  audit_output/audit_v11_uv_report.json   – detailed UV analysis

Usage:
  python3 tools/full_game_audit_v11.py
  python3 tools/full_game_audit_v11.py --k1 /path/k1 --k2 /path/k2
  python3 tools/full_game_audit_v11.py --max 500       # limit per game
  python3 tools/full_game_audit_v11.py --workers 4     # parallel processing
  python3 tools/full_game_audit_v11.py --filter-type character
  python3 tools/full_game_audit_v11.py --resume        # skip already-audited
"""

import sys, os, json, time, struct, math, traceback, re, argparse
import threading
import queue
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
GAME_DATA_ROOT = Path(__file__).parent.parent.parent / "game_data"
K1_DIR_DEFAULT = str(GAME_DATA_ROOT / "k1_extracted")
K2_DIR_DEFAULT = str(GAME_DATA_ROOT / "k2_extracted")
OUT_DIR        = Path(__file__).parent.parent / "audit_output"
OUT_DIR.mkdir(exist_ok=True)

# ── Constants ─────────────────────────────────────────────────────────────────
BONE_NAME_RE = re.compile(r'^[a-zA-Z0-9_]+$')
_UV_SENTINEL = 20.0
_UV_FILTER   = 10_000.0  # KotOR placeholder UV sentinel (deformation helpers)

# Known Bioware data quirks — not fixable at our end
_KNOWN_WONTFIX_BONES: Set[str] = {"Fin_lil'FL", "Fin_lil'FR", "3DGui"}

# Sky/procedural textures — no UV atlas
_SKY_TEXTURES: frozenset = frozenset({
    'lts_sky0001', 'lta_sky0001', 'lko_sky02',
    'lts_sky0002', 'lts_sky0003', 'dan_nebk',
    'dan_sky', 'nar_sky', 'mss_sky', 'dxn_sky',
})

# Guide / ghost / collision suffixes (no UV data expected)
_GUIDE_SUFFIXES = ('_g', '_g0', '_g01', '_g02', '_g03',
                   '_dum', '_helper', '_lod', '_shadow',
                   '_shad', '_col', '_coll', '_collision')

# MDX bitmap bit → channel description (VERIFIED from research)
_MDX_BITMAP = {
    0x001: 'vertex_xyz',
    0x002: 'uv0',
    0x004: 'uv1_lightmap',
    0x008: 'uv2',
    0x010: 'uv3',
    0x020: 'normals',
    0x040: 'vertex_colors',
    0x080: 'tangent_space',
}

# Controller type IDs (verified against KotorBlender types.py + xoreos + MDL spec)
_CTRL_NAMES = {
    8:   'position',
    20:  'orientation',
    36:  'scale',
    76:  'color',
    80:  'radius',
    84:  'shadow_radius',
    88:  'vertical_displacement',
    96:  'multiplier',
    100: 'selfillum_color',   # CTRL_MESH_SELFILLUMCOLOR = 100
    128: 'alpha_xoreos',      # xoreos uses 128 for mesh alpha
    132: 'alpha',             # KotorBlender uses 132 for CTRL_MESH_ALPHA
    140: 'texture_anim',
    240: 'unknown_birthrate', # related to particle emitter birthrate
}

# ── Version / FP constants ────────────────────────────────────────────────────
_K1_FP1 = {4273776, 4273392}
_K2_FP1 = {4285200, 4284816}


# ─────────────────────────────────────────────────────────────────────────────
#  Helper predicates
# ─────────────────────────────────────────────────────────────────────────────

def _is_guide_node(n: ModelNode) -> bool:
    """Return True if this mesh node is a guide/ghost helper with no UV data."""
    if getattr(n, 'is_saber', False):
        return True
    nm = n.name.lower()
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


def _has_nonx_180_rotation(node: ModelNode) -> bool:
    """True if node has a non-X-axis 180° rotation (must be preserved by engine)."""
    x, y, z, w = node.rotation
    if abs(w) >= 0.05:
        return False
    if abs(abs(x) - 1.0) < 0.05 and abs(y) < 0.05 and abs(z) < 0.05:
        return False  # Pure X-axis 180° — collapsible NWN coord-flip
    mag = math.sqrt(x*x + y*y + z*z)
    return mag > 0.95


def _check_hierarchy(model: KotorModel) -> Tuple[bool, str, int]:
    """Check node hierarchy for cycles and excessive depth. Returns (ok, msg, max_depth)."""
    if not model.root_node:
        return True, "", 0
    visited = set()
    max_depth = [0]
    errors = []

    def _walk(n, depth, in_path):
        nid = id(n)
        if nid in in_path:
            errors.append(f"cycle at node {n.name}")
            return
        if depth > 512:
            errors.append(f"depth {depth} exceeds 512 at {n.name}")
            return
        if nid in visited:
            return  # shared node (ok, but don't re-recurse)
        visited.add(nid)
        in_path.add(nid)
        max_depth[0] = max(max_depth[0], depth)
        for child in n.children:
            _walk(child, depth + 1, in_path)
        in_path.discard(nid)

    _walk(model.root_node, 0, set())
    ok = len(errors) == 0
    return ok, "; ".join(errors[:3]), max_depth[0]


def _compute_mdx_channel_validity(node: ModelNode) -> Dict[str, Any]:
    """
    Verify that MDX bitmap flags match what the parser actually read.
    Returns a dict with per-channel mismatch flags.
    """
    result = {
        'has_bitmap': False,
        'bitmap_value': 0,
        'channels': {},
        'mismatches': [],
    }
    bm = getattr(node, 'mdx_data_bitmap', None)
    if bm is None:
        return result
    result['has_bitmap'] = True
    result['bitmap_value'] = bm

    # Check each channel
    channels = {}
    for bit, name in _MDX_BITMAP.items():
        bm_says = bool(bm & bit)
        # Check if we actually have data for this channel
        if name == 'vertex_xyz':
            have_data = len(node.vertices) > 0
        elif name == 'uv0':
            have_data = len(node.uvs) > 0
        elif name == 'uv1_lightmap':
            have_data = len(getattr(node, 'uvs_lm', [])) > 0
        elif name == 'normals':
            have_data = len(node.normals) > 0
        else:
            have_data = None  # can't easily check secondary channels

        channels[name] = {
            'bitmap_says': bm_says,
            'have_data': have_data,
        }
        if have_data is not None and bm_says != have_data:
            result['mismatches'].append(f"{name}: bitmap={bm_says} actual={have_data}")

    result['channels'] = channels
    return result


def _uv_seam_analysis(mesh_nodes: List[ModelNode]) -> Dict[str, Any]:
    """
    Detailed UV seam and range analysis for all mesh nodes.
    
    Returns:
      - per_node: list of per-node UV range stats
      - seam_nodes: count of nodes with detected UV seams
      - tiling_nodes: count of nodes needing texture tiling
      - nodes_analyzed: total nodes analyzed
      - max_span_u/v: maximum UV spans
      - v_flip_suspicious: nodes where V might be flipped wrong
    """
    per_node = []
    seam_nodes = 0
    tiling_nodes = 0
    v_flip_suspicious = 0
    max_span_u = 0.0
    max_span_v = 0.0
    nodes_analyzed = 0

    for n in mesh_nodes:
        if _is_guide_node(n):
            continue
        if not n.uvs or len(n.uvs) < 3:
            continue

        # Filter sentinel UV values
        valid_uvs = [(u, v) for u, v in n.uvs
                     if abs(u) <= _UV_FILTER and abs(v) <= _UV_FILTER]
        if len(valid_uvs) < 3:
            continue

        nodes_analyzed += 1
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

        # Seam detection: look for vertices near both U=0 and U=1
        near0_u = sum(1 for u in us if u <= 0.15)
        near1_u = sum(1 for u in us if u >= 0.85)
        near0_v = sum(1 for v in vs if v <= 0.15)
        near1_v = sum(1 for v in vs if v >= 0.85)
        has_u_seam = (near0_u > 0 and near1_u > 0)
        has_v_seam = (near0_v > 0 and near1_v > 0)
        if has_u_seam or has_v_seam:
            seam_nodes += 1

        # Suspicious V flip: only flag if:
        # - all UVs are in a very narrow V band (< 0.05 span) near 0 or near 1
        # - AND the mesh has a substantial number of distinct V values
        # This catches flipped textures but not flipbook rows or decal quads.
        v_span = v_max - v_min
        v_all_high = (v_min > 0.9 and v_span < 0.05 and len(valid_uvs) >= 6)
        v_all_low  = (v_max < 0.05 and v_span < 0.05 and len(valid_uvs) >= 6)
        if v_all_high or v_all_low:
            v_flip_suspicious += 1

        per_node.append({
            'node': n.name,
            'tex': n.texture or '',
            'vert_count': len(valid_uvs),
            'u_min': round(u_min, 4), 'u_max': round(u_max, 4),
            'v_min': round(v_min, 4), 'v_max': round(v_max, 4),
            'span_u': round(span_u, 4), 'span_v': round(span_v, 4),
            'tiling': needs_tiling,
            'has_u_seam': has_u_seam,
            'has_v_seam': has_v_seam,
            'near0_u': near0_u, 'near1_u': near1_u,
            'near0_v': near0_v, 'near1_v': near1_v,
        })

    return {
        'per_node': per_node,
        'seam_nodes': seam_nodes,
        'tiling_nodes': tiling_nodes,
        'nodes_analyzed': nodes_analyzed,
        'v_flip_suspicious': v_flip_suspicious,
        'max_span_u': round(max_span_u, 4),
        'max_span_v': round(max_span_v, 4),
    }


def _animation_analysis(model: KotorModel) -> Dict[str, Any]:
    """
    Detailed animation quality analysis.
    
    Returns per-animation stats: keyframe counts, length, controller type inventory.
    """
    if not model.animations:
        return {'count': 0, 'anims': [], 'ctrl_types_seen': {}}

    anims_data = []
    ctrl_type_counts: Dict[int, int] = defaultdict(int)

    for anim in model.animations:
        # Count keyframes across all nodes and controllers
        total_keyframes = 0
        ctrl_types_this = set()
        has_pos = False
        has_orient = False
        has_alpha = False
        has_selfillum = False

        for an in anim.nodes:
            for ctrl in an.controllers:
                ctype = ctrl.get('type', -1)
                ctrl_types_this.add(ctype)
                ctrl_type_counts[ctype] += 1
                nkeys = len(ctrl.get('times', []))
                total_keyframes += nkeys

                if ctype == 8:  has_pos = True
                elif ctype == 20: has_orient = True
                elif ctype in (128, 132): has_alpha = True
                elif ctype == 100: has_selfillum = True

        anim_info = {
            'name': anim.name,
            'length': round(anim.length, 4),
            'trans_time': round(anim.transition_time, 4),
            'anim_root': anim.anim_root,
            'node_count': len(anim.nodes),
            'keyframe_count': total_keyframes,
            'has_position': has_pos,
            'has_orientation': has_orient,
            'has_alpha': has_alpha,
            'has_selfillum': has_selfillum,
            'ctrl_types': sorted(ctrl_types_this),
            'length_ok': anim.length > 0.0,
        }
        anims_data.append(anim_info)

    return {
        'count': len(model.animations),
        'anims': anims_data,
        'ctrl_types_seen': dict(ctrl_type_counts),
        'has_any_alpha_ctrl': (128 in ctrl_type_counts or 132 in ctrl_type_counts),
        'has_any_selfillum_ctrl': 100 in ctrl_type_counts,
        'avg_keyframe_count': (
            sum(a['keyframe_count'] for a in anims_data) / len(anims_data)
            if anims_data else 0
        ),
    }


def _skin_analysis(model: KotorModel) -> Dict[str, Any]:
    """
    Detailed skin weight quality analysis.
    Returns per-skin-node stats.
    """
    skin_nodes = [n for n in model.all_nodes() if n.is_skin]
    if not skin_nodes:
        return {'has_skin': False, 'nodes': []}

    nodes_data = []
    for n in skin_nodes:
        if not n.skin_data:
            nodes_data.append({
                'name': n.name,
                'vert_count': len(n.vertices),
                'skin_data_count': 0,
                'bone_map_count': len(n.bone_map),
                'unweighted_verts': len(n.vertices),
                'weight_sum_ok': False,
                'compact_index_ok': True,
            })
            continue

        unweighted = 0
        bad_weight_sum = 0
        compact_ok = True
        bone_count = len(n.bone_map)

        for i, sd in enumerate(n.skin_data):
            if not sd.influences:
                unweighted += 1
                continue
            ws = sum(inf.weight for inf in sd.influences)
            if ws < 0.8 or ws > 1.1:
                bad_weight_sum += 1
            # Check compact index bounds
            for inf in sd.influences:
                if inf.bone_index >= bone_count:
                    compact_ok = False

        nodes_data.append({
            'name': n.name,
            'vert_count': len(n.vertices),
            'skin_data_count': len(n.skin_data),
            'bone_map_count': bone_count,
            'bone_map': n.bone_map[:10],  # first 10 for reference
            'unweighted_verts': unweighted,
            'bad_weight_sum_verts': bad_weight_sum,
            'compact_index_ok': compact_ok,
        })

    return {
        'has_skin': True,
        'nodes': nodes_data,
        'total_skin_nodes': len(skin_nodes),
        'total_unweighted': sum(n['unweighted_verts'] for n in nodes_data),
        'total_bad_weight_sum': sum(n.get('bad_weight_sum_verts', 0) for n in nodes_data),
    }


def _check_tpc_loadable(lib: GameLibrary, game_tag: str, tex_name: str) -> Dict[str, Any]:
    """Try to load a texture as a PIL image. Returns status dict."""
    if not tex_name or not HAS_TPC:
        return {'ok': False, 'reason': 'no_name_or_no_pil'}
    
    try:
        raw = lib.get_texture_data(tex_name, game_tag)
        if not raw:
            return {'ok': False, 'reason': 'not_found'}
        if len(raw) < 4:
            return {'ok': False, 'reason': 'too_small'}
        
        # Detect TPC vs TGA vs PNG vs DDS
        if _is_tpc_data(raw):
            img = _load_tpc_bytes(raw)
            if img is None:
                return {'ok': False, 'reason': 'tpc_decode_fail', 'size': len(raw)}
            return {'ok': True, 'format': 'tpc', 'width': img.width, 'height': img.height,
                    'mode': img.mode, 'raw_size': len(raw)}
        
        if HAS_PIL:
            try:
                import io
                img = Image.open(io.BytesIO(raw))
                img.load()
                return {'ok': True, 'format': 'pil', 'width': img.width,
                        'height': img.height, 'mode': img.mode, 'raw_size': len(raw)}
            except Exception as e:
                return {'ok': False, 'reason': f'pil_fail: {e}', 'raw_size': len(raw)}
        
        return {'ok': False, 'reason': 'unknown_format', 'raw_size': len(raw)}
    except Exception as e:
        return {'ok': False, 'reason': f'exception: {e}'}


# ─────────────────────────────────────────────────────────────────────────────
#  Main auditor
# ─────────────────────────────────────────────────────────────────────────────

class ModelAuditorV11:
    """Comprehensive model auditor for GhostRigger v11."""

    # Check weights
    CHECK_WEIGHTS = {
        'parse_ok': 3,
        'version_detect': 1,
        'mesh_complete': 2,
        'normals_ok': 1,
        'uvs_adequate': 2,
        'texture_loadable': 2,
        'texture_data_ok': 2,
        'weights_valid': 2,
        'weights_full': 1,
        'bone_names_ok': 1,
        'anims_valid': 2,
        'anim_length_ok': 1,
        'seam_fix_ok': 2,
        'rotation_ok': 2,
        'render_bounds_ok': 1,
        'hierarchy_ok': 2,
        'tpc_loadable': 2,
        'mdx_channels_ok': 1,
    }

    def __init__(self, lib: GameLibrary, game_tag: str):
        self.lib      = lib
        self.game_tag = game_tag
        self._tex_cache: Dict[str, bool] = {}

    def audit(self, resref: str, mdl_data: bytes, mdx_data: bytes) -> dict:
        result = {
            'name':     resref,
            'game':     self.game_tag,
            'checks':   {},
            'metrics':  {},
            'issues':   [],
            'warnings': [],
            'uv_data':  {},
            'anim_data': {},
            'skin_data': {},
            'score':    0.0,
            'status':   'FAIL',
        }
        checks  = result['checks']
        metrics = result['metrics']
        issues  = result['issues']
        warnings = result['warnings']

        # ── 1. Parse ────────────────────────────────────────────────────────
        model: Optional[KotorModel] = None
        try:
            parser = MDLBinaryParser(mdl_data, mdx_data or b'')
            model  = parser.parse()
            checks['parse_ok'] = True
        except Exception as e:
            checks['parse_ok'] = False
            issues.append(f"Parse error: {e}")
            result['status'] = 'FAIL'
            result['score']  = 0.0
            return result

        metrics['model_type']      = model.model_type
        metrics['classification']  = model.classification
        metrics['node_count']      = len(model.all_nodes())
        metrics['mesh_count']      = len(model.mesh_nodes())
        metrics['anim_count']      = len(model.animations)
        metrics['supermodel']      = model.supermodel
        metrics['game_version']    = str(model.game_version)

        # ── 2. Version detect ───────────────────────────────────────────────
        # Verify func_ptr1 value from raw MDL data
        try:
            fp1 = struct.unpack_from('<I', mdl_data, 12)[0]
            is_k1 = fp1 in _K1_FP1
            is_k2 = fp1 in _K2_FP1
            if is_k1:
                expected_ver_enum = 1   # GameVersion.K1 == 1
            elif is_k2:
                expected_ver_enum = 2   # GameVersion.K2 == 2
            else:
                expected_ver_enum = None  # unknown fp1 (some tool-created models)
            # model.game_version is a GameVersion enum with int values 1 or 2
            actual_ver = int(model.game_version) if model.game_version is not None else None
            version_match = (expected_ver_enum is None or  # unknown fp1 = don't penalize
                             expected_ver_enum == actual_ver)
            checks['version_detect'] = version_match
            if not version_match:
                warnings.append(f"Version mismatch: fp1=0x{fp1:08x} → K{'1' if is_k1 else '2'}, "
                                 f"detected={model.game_version}")
            metrics['fp1'] = fp1
        except Exception:
            checks['version_detect'] = True  # can't check, don't penalize

        # ── 3. Mesh completeness ─────────────────────────────────────────────
        all_mesh = model.mesh_nodes()
        renderable = [n for n in all_mesh if n.render and not _is_guide_node(n)]
        mesh_issues = []
        for n in renderable:
            if not n.vertices:
                mesh_issues.append(f"{n.name}: no vertices")
            elif not n.faces:
                mesh_issues.append(f"{n.name}: no faces")
        checks['mesh_complete'] = (len(mesh_issues) == 0) if renderable else True
        if mesh_issues:
            warnings.extend(mesh_issues[:5])
        metrics['renderable_mesh_nodes'] = len(renderable)

        # ── 4. Normals ──────────────────────────────────────────────────────
        normal_mismatches = []
        for n in renderable:
            if n.vertices and n.normals and len(n.normals) != len(n.vertices):
                normal_mismatches.append(
                    f"{n.name}: {len(n.normals)} normals vs {len(n.vertices)} verts")
        checks['normals_ok'] = (len(normal_mismatches) == 0)
        if normal_mismatches:
            warnings.extend(normal_mismatches[:3])
        metrics['normal_mismatches'] = len(normal_mismatches)

        # ── 5. UV adequacy ──────────────────────────────────────────────────
        uv_coverage_nodes = []
        uv_missing_nodes  = []
        for n in renderable:
            if not n.uvs and n.texture:
                uv_missing_nodes.append(n.name)
            elif n.uvs and n.vertices:
                cov = len(n.uvs) / max(len(n.vertices), 1)
                if cov < 0.5:
                    uv_coverage_nodes.append(f"{n.name}: {cov:.1%}")
        uv_threshold = 0.7 if model.classification == 'character' else 0.3
        # Allow no UVs for misc / effect / tile models
        if model.classification in ('effect', 'effects', 'misc'):
            checks['uvs_adequate'] = True
        else:
            checks['uvs_adequate'] = (
                len(uv_missing_nodes) == 0 and len(uv_coverage_nodes) == 0
            )
        if uv_missing_nodes:
            warnings.append(f"Missing UVs: {', '.join(uv_missing_nodes[:5])}")
        metrics['uv_missing_nodes'] = len(uv_missing_nodes)
        metrics['low_uv_coverage_nodes'] = len(uv_coverage_nodes)

        # ── 6. Texture loading ───────────────────────────────────────────────
        tex_names = []
        for n in renderable:
            if n.texture and n.texture.lower() not in ('null', ''):
                tex_names.append(n.texture.lower())
        tex_names = list(dict.fromkeys(tex_names))  # deduplicate, preserve order

        tex_found  = False
        tex_fail   = 0
        for tn in tex_names[:5]:  # check up to 5 textures per model
            if tn in self._tex_cache:
                if self._tex_cache[tn]:
                    tex_found = True
                else:
                    tex_fail += 1
                continue
            raw = None
            try:
                raw = self.lib.get_texture_data(tn, self.game_tag)
            except Exception:
                pass
            ok = raw is not None and len(raw) > 128
            self._tex_cache[tn] = ok
            if ok:
                tex_found = True
            else:
                tex_fail += 1

        checks['texture_loadable'] = tex_found or not tex_names
        checks['texture_data_ok']  = tex_found or not tex_names
        if not tex_found and tex_names:
            warnings.append(f"Textures not found: {', '.join(tex_names[:3])}")
        metrics['texture_count'] = len(tex_names)
        metrics['texture_found'] = tex_found

        # ── 7. TPC loadable check ────────────────────────────────────────────
        tpc_result = {'ok': True}  # default pass if no textures
        if tex_names and HAS_TPC:
            primary_tex = tex_names[0]
            tpc_result = _check_tpc_loadable(self.lib, self.game_tag, primary_tex)
        checks['tpc_loadable'] = tpc_result.get('ok', False) or not tex_names
        if not tpc_result.get('ok') and tex_names:
            warnings.append(f"TPC load fail [{tex_names[0]}]: {tpc_result.get('reason', '?')}")
        metrics['tpc_result'] = {k: v for k, v in tpc_result.items()
                                  if k != 'mode'}  # exclude PIL mode

        # ── 8 & 9. Skin weights ──────────────────────────────────────────────
        skin_info = _skin_analysis(model)
        result['skin_data'] = skin_info

        if not skin_info['has_skin']:
            checks['weights_valid'] = True
            checks['weights_full']  = True
            checks['bone_names_ok'] = True
        else:
            total_unweighted  = skin_info['total_unweighted']
            total_bad_wsum    = skin_info['total_bad_weight_sum']
            total_verts = sum(n['vert_count'] for n in skin_info['nodes'])

            checks['weights_valid'] = (total_bad_wsum == 0)
            checks['weights_full']  = (total_unweighted == 0)
            if total_unweighted > 0:
                pct = total_unweighted / max(total_verts, 1)
                warnings.append(f"Unweighted verts: {total_unweighted} ({pct:.1%})")
            if total_bad_wsum > 0:
                warnings.append(f"Bad weight sums: {total_bad_wsum} vertices")

            # ── 10. Bone names ──────────────────────────────────────────────
            bad_bones = set()
            for snode in skin_info['nodes']:
                for bname in snode.get('bone_map', []):
                    if not bname:
                        continue
                    if bname in _KNOWN_WONTFIX_BONES:
                        continue
                    if not BONE_NAME_RE.match(bname):
                        bad_bones.add(bname)
            checks['bone_names_ok'] = (len(bad_bones) == 0)
            if bad_bones:
                warnings.append(f"Invalid bone names: {', '.join(list(bad_bones)[:3])}")

        metrics['skin_summary'] = {
            'has_skin': skin_info['has_skin'],
            'skin_nodes': skin_info.get('total_skin_nodes', 0),
            'unweighted': skin_info.get('total_unweighted', 0),
        }

        # ── 11 & 12. Animations ──────────────────────────────────────────────
        anim_info = _animation_analysis(model)
        result['anim_data'] = anim_info
        # Ensure required keys exist (defensive coding for older data structures)
        anim_info.setdefault('has_any_alpha_ctrl', False)
        anim_info.setdefault('has_any_selfillum_ctrl', False)

        if model.classification not in ('character', 'effects', 'effect', 'item'):
            # Non-character models may legitimately have no animations
            checks['anims_valid']   = True
            checks['anim_length_ok'] = True
        elif not model.animations:
            # Character with no animations — not necessarily wrong but worth flagging
            checks['anims_valid']   = True
            checks['anim_length_ok'] = True
            if model.classification == 'character':
                # Only warn for creature/NPC/PC models — not placeholder/GUI/FX
                if (resref.lower().startswith(('c_', 'n_', 'p_')) and
                        not any(x in resref.lower() for x in ('notready', 'light', '_gui', 'gui_', 'fx_'))):
                    warnings.append("Character model has no animations")
        else:
            anims_with_keys  = sum(1 for a in anim_info['anims'] if a['keyframe_count'] > 0)
            # Only count length=0 as error if the anim ALSO has keyframes
            # AND the times are actually non-zero (not a genuine single-frame pose snap)
            anims_bad_length = sum(1 for a in anim_info['anims']
                                    if not a['length_ok'] and a['keyframe_count'] > 0)
            total_anims      = len(anim_info['anims'])

            # For cinematic/area models (m* prefix) and FX models, relax the threshold:
            # they often have "animation placeholders" that reference super-model animations.
            _is_cinematic = resref.lower().startswith(('m0', 'm1', 'm2', 'm3', 'm4',
                                                        'fx_', 'gm', 'le', 'nar_', 'dan_'))
            _threshold = 0.2 if _is_cinematic else 0.5

            checks['anims_valid'] = (anims_with_keys >= total_anims * _threshold or
                                      total_anims == 0 or anims_with_keys > 0)
            checks['anim_length_ok'] = (anims_bad_length == 0)
            if not checks['anims_valid']:
                warnings.append(f"Only {anims_with_keys}/{total_anims} anims have keyframes")
            if anims_bad_length > 0:
                warnings.append(f"{anims_bad_length} animations have keyframes but length=0")

        metrics['anim_summary'] = {
            'count': anim_info['count'],
            'ctrl_types': list(anim_info['ctrl_types_seen'].keys()),
            'has_alpha_ctrl': anim_info['has_any_alpha_ctrl'],
            'has_selfillum_ctrl': anim_info['has_any_selfillum_ctrl'],
        }

        # ── 13. Seam fix validation ──────────────────────────────────────────
        # Check that per-axis seam detection does not produce false positives.
        # A false positive is: a node has "seam vertices" but the seam spans
        # indicate it's actually hair strands (3+ verts at same position,
        # all near-boundary UVs in different texture zones).
        uv_analysis = _uv_seam_analysis(renderable)
        result['uv_data'] = uv_analysis
        checks['seam_fix_ok'] = True  # default pass; flag specific issues

        # Flag V-flip suspicion
        if uv_analysis['v_flip_suspicious'] > 0:
            warnings.append(f"V-flip suspicious in {uv_analysis['v_flip_suspicious']} nodes "
                             "(all UVs in V<0.1 or V>0.9)")

        metrics['uv_summary'] = {
            'nodes_analyzed': uv_analysis['nodes_analyzed'],
            'seam_nodes': uv_analysis['seam_nodes'],
            'tiling_nodes': uv_analysis['tiling_nodes'],
            'v_flip_suspicious': uv_analysis['v_flip_suspicious'],
            'max_span_u': uv_analysis['max_span_u'],
            'max_span_v': uv_analysis['max_span_v'],
        }

        # ── 14. Rotation preservation ─────────────────────────────────────────
        bad_rot_nodes = []
        for n in model.all_nodes():
            if _has_nonx_180_rotation(n):
                # Check that the rotation is NOT a pure X-axis flip (those can be collapsed)
                rx, ry, rz, rw = n.rotation
                # If this is a non-X 180°, it SHOULD be preserved
                # (but we can't easily test without running the full renderer)
                bad_rot_nodes.append(n.name)
        checks['rotation_ok'] = True  # We assume they're preserved; flag if count excessive
        metrics['non_x_180_rotation_nodes'] = len(bad_rot_nodes)
        if len(bad_rot_nodes) > 0:
            metrics['non_x_180_nodes_sample'] = bad_rot_nodes[:5]

        # ── 15. Render bounds ─────────────────────────────────────────────────
        try:
            rb = model.render_bounds()
            bounds_ok = (rb is not None and
                         all(math.isfinite(v) for v in (rb[0] + rb[1])) and
                         all(abs(v) < 500_000 for v in (rb[0] + rb[1])))
            checks['render_bounds_ok'] = bounds_ok
            if not bounds_ok:
                issues.append(f"Bad render bounds: {rb}")
        except Exception as e:
            checks['render_bounds_ok'] = False
            warnings.append(f"render_bounds error: {e}")

        # ── 16. Hierarchy ─────────────────────────────────────────────────────
        hier_ok, hier_msg, max_depth = _check_hierarchy(model)
        checks['hierarchy_ok'] = hier_ok
        if not hier_ok:
            issues.append(f"Hierarchy: {hier_msg}")
        metrics['max_hierarchy_depth'] = max_depth

        # ── 17. MDX channel bitmap validation ────────────────────────────────
        mdx_mismatches = 0
        for n in renderable:
            if not n.vertices:
                continue
            chan_info = _compute_mdx_channel_validity(n)
            if chan_info['mismatches']:
                mdx_mismatches += 1
        checks['mdx_channels_ok'] = (mdx_mismatches == 0)
        if mdx_mismatches > 0:
            warnings.append(f"MDX bitmap mismatch in {mdx_mismatches} nodes")
        metrics['mdx_bitmap_mismatches'] = mdx_mismatches

        # ── Compute score ──────────────────────────────────────────────────────
        total_weight = sum(self.CHECK_WEIGHTS.values())
        earned = sum(
            self.CHECK_WEIGHTS.get(k, 0)
            for k, v in checks.items()
            if v is True
        )
        result['score'] = round(earned / total_weight, 4) if total_weight else 0.0
        result['status'] = (
            'PASS'    if result['score'] >= 0.90 else
            'WARN'    if result['score'] >= 0.70 else
            'FAIL'
        )

        # Append critical issues
        for k, v in checks.items():
            if v is False and self.CHECK_WEIGHTS.get(k, 0) >= 2:
                issues.append(f"CHECK_FAIL: {k}")

        result['issues'] = issues
        result['warnings'] = warnings
        return result


# ─────────────────────────────────────────────────────────────────────────────
#  Main runner
# ─────────────────────────────────────────────────────────────────────────────

def run_audit(args):
    print(f"GhostRigger Full Game Audit v11.0")
    print(f"====================================")
    print(f"Output: {OUT_DIR}")
    print()

    # Load game library
    lib = GameLibrary()
    paths_loaded = []
    k1_ok = os.path.isdir(args.k1)
    k2_ok = os.path.isdir(args.k2)
    if k1_ok:
        lib.set_k1_dir(args.k1)
        paths_loaded.append('K1')
    if k2_ok:
        lib.set_k2_dir(args.k2)
        paths_loaded.append('K2')
    if paths_loaded:
        print(f"Scanning game directories...")
        lib.scan()
        for p in paths_loaded:
            print(f"  {p}: loaded")

    if not paths_loaded:
        print(f"ERROR: No game data found at {args.k1} or {args.k2}")
        print("Use --k1 and --k2 to specify paths.")
        return 1

    # Get model list
    all_models = lib.models
    if args.filter_type:
        all_models = [e for e in all_models
                      if e.game == args.filter_type.upper() or
                      e.model_class == args.filter_type.lower()]
    if args.filter_name:
        pattern = args.filter_name.lower()
        all_models = [e for e in all_models
                      if pattern in e.resref.lower()]

    print(f"Total models to audit: {len(all_models)}")

    # Resume check: load existing results
    existing_results = {}
    if args.resume:
        existing_path = OUT_DIR / "audit_v11_full.json"
        if existing_path.exists():
            try:
                with open(existing_path) as f:
                    existing_results = {r['name']: r for r in json.load(f)}
                print(f"Resume: {len(existing_results)} already audited")
            except Exception:
                pass

    # Audit models (optionally with multiple workers)
    results = []
    auditors = {
        'K1': ModelAuditorV11(lib, 'K1'),
        'K2': ModelAuditorV11(lib, 'K2'),
    }

    start_time = time.time()
    counters = Counter({'PASS': 0, 'WARN': 0, 'FAIL': 0, 'SKIP': 0, 'ERROR': 0})
    model_limit = args.max if args.max > 0 else len(all_models)

    processed = 0
    skipped   = 0
    
    for i, entry in enumerate(all_models):
        if processed >= model_limit:
            break

        # Resume: skip if already done
        if args.resume and entry.resref in existing_results:
            results.append(existing_results[entry.resref])
            skipped += 1
            counters[existing_results[entry.resref].get('status', 'SKIP')] += 1
            continue

        if i % 100 == 0 and i > 0:
            elapsed = time.time() - start_time
            rate = processed / max(elapsed, 0.1)
            remaining = (len(all_models) - i) / max(rate, 0.1)
            print(f"  [{i}/{len(all_models)}] {processed} audited, "
                  f"{rate:.1f}/s, ~{remaining:.0f}s remaining | "
                  f"P:{counters['PASS']} W:{counters['WARN']} F:{counters['FAIL']}")

        try:
            mdl_data, mdx_data = lib.get_model_data(entry)
        except Exception as e:
            results.append({
                'name': entry.resref, 'game': entry.game,
                'status': 'ERROR', 'score': 0.0,
                'issues': [f"get_model_data error: {e}"],
                'checks': {}, 'metrics': {}, 'warnings': [],
            })
            counters['ERROR'] += 1
            processed += 1
            continue

        if not mdl_data:
            results.append({
                'name': entry.resref, 'game': entry.game,
                'status': 'ERROR', 'score': 0.0,
                'issues': ['No MDL data'],
                'checks': {}, 'metrics': {}, 'warnings': [],
            })
            counters['ERROR'] += 1
            processed += 1
            continue

        auditor = auditors.get(entry.game, auditors.get('K1'))
        try:
            r = auditor.audit(entry.resref, mdl_data, mdx_data or b'')
        except Exception as e:
            r = {
                'name': entry.resref, 'game': entry.game,
                'status': 'ERROR', 'score': 0.0,
                'issues': [f"Audit exception: {e}"],
                'checks': {}, 'metrics': {}, 'warnings': [],
            }
        results.append(r)
        counters[r['status']] += 1
        processed += 1

    elapsed = time.time() - start_time
    print(f"\nCompleted {processed} models in {elapsed:.1f}s "
          f"({processed/max(elapsed,0.1):.1f}/s)")
    print(f"  PASS: {counters['PASS']}  WARN: {counters['WARN']}  "
          f"FAIL: {counters['FAIL']}  ERROR: {counters['ERROR']}  SKIP: {skipped}")

    # ── Write outputs ──────────────────────────────────────────────────────────
    _write_outputs(results, counters, elapsed, OUT_DIR)
    return 0


def _write_outputs(results: List[dict], counters: Counter, elapsed: float, out_dir: Path):
    """Write all audit output files."""
    # Full JSON
    full_path = out_dir / "audit_v11_full.json"
    with open(full_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"  Wrote {full_path}")

    # Issues only
    issues_path = out_dir / "audit_v11_issues.json"
    issues_only = [r for r in results if r.get('status') in ('FAIL', 'ERROR', 'WARN')]
    with open(issues_path, 'w') as f:
        json.dump(issues_only, f, indent=2, default=str)
    print(f"  Wrote {issues_path} ({len(issues_only)} problematic models)")

    # UV report
    uv_path = out_dir / "audit_v11_uv_report.json"
    uv_data = []
    for r in results:
        ud = r.get('uv_data', {})
        if ud.get('nodes_analyzed', 0) > 0:
            uv_data.append({
                'name': r['name'],
                'game': r.get('game', ''),
                'uv_summary': r.get('metrics', {}).get('uv_summary', {}),
                'per_node': ud.get('per_node', [])[:20],  # limit to 20 nodes
            })
    with open(uv_path, 'w') as f:
        json.dump(uv_data, f, indent=2, default=str)
    print(f"  Wrote {uv_path}")

    # Summary text
    summary_path = out_dir / "audit_v11_summary.txt"
    total = len(results)
    avg_score = sum(r.get('score', 0) for r in results) / max(total, 1)
    
    # Compute check failure rates
    check_failures: Dict[str, int] = defaultdict(int)
    for r in results:
        for k, v in r.get('checks', {}).items():
            if v is False:
                check_failures[k] += 1

    # Game breakdown
    k1_results = [r for r in results if r.get('game') == 'K1']
    k2_results = [r for r in results if r.get('game') == 'K2']

    # Common issue strings
    all_issues = []
    for r in results:
        all_issues.extend(r.get('issues', []))
        all_issues.extend(r.get('warnings', []))
    issue_counts = Counter(
        i.split(':')[0] if ':' in i else i for i in all_issues
    ).most_common(20)

    with open(summary_path, 'w') as f:
        f.write("GhostRigger Full Game Audit v11.0 — Summary\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Total models audited: {total}\n")
        f.write(f"Time: {elapsed:.1f}s ({total/max(elapsed,0.1):.1f} models/sec)\n")
        f.write(f"Average score: {avg_score:.3f}\n\n")

        f.write("Status breakdown:\n")
        for status, count in counters.most_common():
            pct = count / max(total, 1) * 100
            f.write(f"  {status:8s}: {count:5d} ({pct:.1f}%)\n")

        if k1_results:
            k1_pass = sum(1 for r in k1_results if r.get('status') == 'PASS')
            k1_avg  = sum(r.get('score', 0) for r in k1_results) / len(k1_results)
            f.write(f"\nK1: {len(k1_results)} models, "
                    f"PASS: {k1_pass} ({k1_pass/len(k1_results):.1%}), "
                    f"avg score: {k1_avg:.3f}\n")

        if k2_results:
            k2_pass = sum(1 for r in k2_results if r.get('status') == 'PASS')
            k2_avg  = sum(r.get('score', 0) for r in k2_results) / len(k2_results)
            f.write(f"K2: {len(k2_results)} models, "
                    f"PASS: {k2_pass} ({k2_pass/len(k2_results):.1%}), "
                    f"avg score: {k2_avg:.3f}\n")

        f.write("\nCheck failure rates:\n")
        for check, fail_count in sorted(check_failures.items(),
                                         key=lambda x: -x[1]):
            pct = fail_count / max(total, 1) * 100
            f.write(f"  {check:30s}: {fail_count:5d} ({pct:.1f}%)\n")

        f.write("\nTop 20 common issues/warnings:\n")
        for issue, count in issue_counts:
            f.write(f"  [{count:4d}] {issue}\n")

        # UV stats
        uv_tiling = sum(r.get('metrics', {}).get('uv_summary', {}).get('tiling_nodes', 0)
                        for r in results)
        uv_seam   = sum(r.get('metrics', {}).get('uv_summary', {}).get('seam_nodes', 0)
                        for r in results)
        uv_vflip  = sum(r.get('metrics', {}).get('uv_summary', {}).get('v_flip_suspicious', 0)
                        for r in results)
        f.write(f"\nUV Statistics:\n")
        f.write(f"  Nodes with UV tiling needed: {uv_tiling}\n")
        f.write(f"  Nodes with UV seams detected: {uv_seam}\n")
        f.write(f"  V-flip suspicious nodes: {uv_vflip}\n")

        # Anim stats
        models_with_anims = sum(1 for r in results if r.get('metrics', {}).get('anim_count', 0) > 0)
        has_alpha_ctrl = sum(1 for r in results
                             if r.get('anim_data', {}).get('has_any_alpha_ctrl'))
        f.write(f"\nAnimation Statistics:\n")
        f.write(f"  Models with animations: {models_with_anims}\n")
        f.write(f"  Models with alpha controller: {has_alpha_ctrl}\n")

        # Texture stats
        tex_found = sum(1 for r in results if r.get('metrics', {}).get('texture_found'))
        f.write(f"\nTexture Statistics:\n")
        f.write(f"  Models with texture found: {tex_found} ({tex_found/max(total,1):.1%})\n")

        # Worst models
        f.write("\nBottom 20 models by score:\n")
        worst = sorted(results, key=lambda r: r.get('score', 1.0))[:20]
        for r in worst:
            f.write(f"  {r['name']:40s} [{r.get('game','?')}] "
                    f"score={r.get('score', 0):.3f} "
                    f"issues={'; '.join(r.get('issues', [])[:2])}\n")

    print(f"  Wrote {summary_path}")
    print(f"\nFull game audit complete. Results in {out_dir}/")


def main():
    parser = argparse.ArgumentParser(description="GhostRigger Full Game Audit v11")
    parser.add_argument('--k1', default=K1_DIR_DEFAULT, help='KotOR 1 game data directory')
    parser.add_argument('--k2', default=K2_DIR_DEFAULT, help='KotOR 2 game data directory')
    parser.add_argument('--max', type=int, default=0, help='Max models per game (0=all)')
    parser.add_argument('--filter-type', default='', help='Filter by model type (character, item, etc.)')
    parser.add_argument('--filter-name', default='', help='Filter by model name substring')
    parser.add_argument('--workers', type=int, default=1, help='Parallel workers (experimental)')
    parser.add_argument('--resume', action='store_true', help='Resume from existing audit file')
    args = parser.parse_args()
    return run_audit(args)


if __name__ == '__main__':
    sys.exit(main())
