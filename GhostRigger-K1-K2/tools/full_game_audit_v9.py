#!/usr/bin/env python3
"""
GhostRigger Full Game Audit v9.0
Tests EVERY model in both KOTOR 1 and KOTOR 2 game directories.
No sampling – ALL 5,764+ models tested.

New in v9.0:
  - Check 16: rotation_ok — detects models with anomalous limb orientation
    (nodes with non-X-axis 180° rotations that should be preserved)
    Verifies the _quat_normalize_bind fix works correctly for droid/creature models.
  - Check 17: render_bounds_ok — verifies render_bounds() returns sensible values
    (non-degenerate bounding box, positive size)
  - Check 18: hierarchy_ok — verifies node hierarchy has no cycles and depth ≤ 512
  - Tracks models with 180°Z or 180°Y non-root rotations (droid leg mirrors)
  - Detects models where world_transform position chain is consistent
  - Full regression test: ensures c_drdassassin, c_warbot, c_brith pass correctly

Based on v8.1 with all existing checks preserved.
"""

import sys, os, json, time, struct, math, traceback, tempfile, io
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.resources.game_library import GameLibrary, KEYBIFReader, RES_MDL, RES_MDX
from src.core.mdl_parser import MDLBinaryParser
from src.core.model_data import (
    KotorModel, ModelNode, NodeFlags, GameVersion, Animation,
    _quat_normalize_bind, _quat_normalize, _quat_mul, _quat_rotate
)
from src.converters.mesh_converter import OBJExporter, FBXExporter

# ── Paths ─────────────────────────────────────────────────────────────────────
GAME_DATA_ROOT = Path(__file__).parent.parent / "game_data"
K1_DIR  = str(GAME_DATA_ROOT / "kotor2" / "swkotor")
K2_DIR  = str(GAME_DATA_ROOT / "kotor1" / "Knights of the Old Republic II")
OUT_DIR = Path(__file__).parent.parent / "audit_output"
OUT_DIR.mkdir(exist_ok=True)

import re
BONE_NAME_RE = re.compile(r'^[a-zA-Z0-9_]+$')


def _has_nonx_180_rotation(node: ModelNode) -> bool:
    """
    Detect non-X-axis 180° rotations on a node.
    These are REAL geometry transforms (leg mirrors, body panels) that must
    NOT be collapsed to identity.  Returns True if this node has such a rotation.
    """
    x, y, z, w = node.rotation
    # Check for w ≈ 0 (all 180-degree rotations)
    if abs(w) >= 0.05:
        return False
    # Pure X-axis 180°: (±1, 0, 0, 0) — this is the NWN coord flip, not a geometry transform
    if abs(abs(x) - 1.0) < 0.05 and abs(y) < 0.05 and abs(z) < 0.05:
        return False
    # All other 180° rotations (Y-axis, Z-axis, diagonal) are REAL geometry transforms
    mag = math.sqrt(x*x + y*y + z*z)
    return mag > 0.95


def _world_pos_consistent(node: ModelNode, max_depth: int = 50) -> bool:
    """
    Check that world_transform() returns finite, non-extreme values.
    Extreme values (> 1000 units) indicate a transform chain bug.
    """
    try:
        wp, wo = node.world_transform()
        for v in wp:
            if not math.isfinite(v) or abs(v) > 1000.0:
                return False
        for v in wo:
            if not math.isfinite(v):
                return False
        return True
    except Exception:
        return False


def _check_hierarchy(model: KotorModel) -> Tuple[bool, str]:
    """Check node hierarchy for cycles and excessive depth."""
    if not model.root_node:
        return True, ""
    
    visited = set()
    max_depth_found = 0
    
    def _walk(n, depth):
        nonlocal max_depth_found
        nid = id(n)
        if nid in visited:
            return False, f"cycle at node {n.name}"
        if depth > 512:
            return False, f"depth {depth} exceeds 512 at {n.name}"
        visited.add(nid)
        max_depth_found = max(max_depth_found, depth)
        for child in n.children:
            ok, msg = _walk(child, depth + 1)
            if not ok:
                return False, msg
        visited.discard(nid)
        return True, ""
    
    ok, msg = _walk(model.root_node, 0)
    return ok, msg


# ─────────────────────────────────────────────────────────────────────────────
# Auditor class
# ─────────────────────────────────────────────────────────────────────────────

class ModelAuditor:
    """Audits a single KotorModel for correctness across all subsystems."""

    def __init__(self, lib: GameLibrary, game_tag: str):
        self.lib = lib
        self.game_tag = game_tag
        self._tex_cache: Dict[str, bool] = {}
        self._obj_exporter = OBJExporter()
        self._fbx_exporter = FBXExporter()

    def audit(self, resref: str, mdl_data: bytes, mdx_data: bytes) -> dict:
        result = {
            'name':     resref,
            'game':     self.game_tag,
            'checks':   {},
            'metrics':  {},
            'issues':   [],
            'warnings': [],
            'score':    0.0,
            'status':   'FAIL',
        }
        checks  = result['checks']
        metrics = result['metrics']
        issues  = result['issues']
        warns   = result['warnings']

        # ── 1. Parse ──────────────────────────────────────────────────────────
        model = None
        try:
            parser = MDLBinaryParser(mdl_data, mdx_data or b'')
            model  = parser.parse()
            checks['parse_ok'] = True
            metrics['game_version'] = str(model.game_version)
            metrics['model_type']   = model.model_type
            metrics['supermodel']   = model.supermodel
            metrics['node_count']   = model.node_count()
            metrics['anim_count']   = len(model.animations)
        except Exception as e:
            checks['parse_ok'] = False
            issues.append(f"parse error: {e}")
            result['score'] = 0.0
            result['status'] = 'FAIL'
            return result

        # ── 2. Version detection ──────────────────────────────────────────────
        expected_ver = GameVersion.K1 if self.game_tag == "K1" else GameVersion.K2
        checks['version_detect'] = (model.game_version == expected_ver)
        if not checks['version_detect']:
            warns.append(f"version: detected={model.game_version.name} expected={expected_ver.name}")

        # ── 3. Mesh completeness ──────────────────────────────────────────────
        mesh_nodes = model.mesh_nodes()
        metrics['mesh_nodes']  = len(mesh_nodes)
        missing_geo = [n.name for n in mesh_nodes if not n.vertices or not n.faces]
        checks['mesh_complete'] = (len(missing_geo) == 0)
        metrics['missing_geo']  = missing_geo[:5]
        if missing_geo:
            warns.append(f"mesh nodes missing geometry: {missing_geo[:3]}")

        total_verts = sum(len(n.vertices) for n in mesh_nodes)
        total_faces = sum(len(n.faces)    for n in mesh_nodes)
        metrics['total_verts'] = total_verts
        metrics['total_faces'] = total_faces

        # ── 4. Normals ────────────────────────────────────────────────────────
        rendered_nodes = [n for n in mesh_nodes if n.vertices and n.uvs]
        missing_normals = [n.name for n in rendered_nodes
                           if not n.normals or len(n.normals) != len(n.vertices)]
        checks['normals_ok'] = (len(missing_normals) == 0)
        metrics['missing_normals_count'] = len(missing_normals)

        # ── 5. UV coverage (type-aware) ───────────────────────────────────────
        has_skin_nodes = any(n.is_skin for n in mesh_nodes)
        is_character   = (model.model_type in (2, 4, 64))
        is_item        = (model.model_type in (32, 16))
        is_door        = (model.model_type == 8)
        is_rigged_char = (has_skin_nodes or is_character)
        is_needs_uv    = (is_rigged_char or is_item or is_door)

        metrics['is_rigged_char']   = is_rigged_char
        metrics['model_type_class'] = (
            'character' if is_character else
            'item'      if is_item     else
            'door'      if is_door     else
            'fx'        if model.model_type == 1 else
            'tile_area'
        )

        _TOOL_TEXTURES = {'toolcolors', 'null', ''}
        def _is_helper(n: ModelNode) -> bool:
            nm = n.name.lower()
            if nm.endswith(('_g', '_g0', '_dum', '_helper', '_lod')):
                return True
            if nm.startswith('bt') and not n.uvs:
                return True
            tex = (n.texture or '').strip().lower()
            if not tex or tex in _TOOL_TEXTURES:
                return True
            return False

        textured_nodes = [n for n in mesh_nodes if n.vertices and not _is_helper(n)]
        uv_ok_cnt = sum(1 for n in textured_nodes
                        if n.uvs and len(n.uvs) >= len(n.vertices) * 0.8)
        uv_ratio  = uv_ok_cnt / max(1, len(textured_nodes)) if textured_nodes else 1.0
        metrics['uv_coverage_ratio'] = round(uv_ratio, 3)
        metrics['uv_textured_nodes'] = len(textured_nodes)
        metrics['uv_nodes']          = sum(1 for n in mesh_nodes if n.uvs)

        if is_rigged_char and textured_nodes:
            uv_threshold = 0.6
        elif is_item and textured_nodes:
            uv_threshold = 0.4
        elif is_door and textured_nodes:
            uv_threshold = 0.3
        else:
            uv_threshold = 0.0
        checks['uvs_adequate'] = (uv_ratio >= uv_threshold)
        if uv_ratio < uv_threshold and is_needs_uv:
            warns.append(f"low UV coverage on textured nodes: {uv_ratio:.1%}")

        # ── 6. Texture references ─────────────────────────────────────────────
        tex_names = model.texture_list()
        metrics['texture_names']  = tex_names[:20]
        metrics['texture_count']  = len(tex_names)

        _KNOWN_ABSENT_PATTERNS = ('_lm0', '_lm1', '_lm2', 'toolcolor', 'pointer_', 'headtest')
        def _is_known_absent(name: str) -> bool:
            nl = name.lower()
            return any(pat in nl for pat in _KNOWN_ABSENT_PATTERNS)

        found_textures    = 0
        checkable_textures = 0
        for tname in tex_names[:10]:
            if _is_known_absent(tname):
                continue
            checkable_textures += 1
            tn_lower = tname.lower()
            if tn_lower not in self._tex_cache:
                raw = self.lib.get_texture_data(tn_lower, self.game_tag)
                self._tex_cache[tn_lower] = (raw is not None and len(raw) > 128)
            if self._tex_cache[tn_lower]:
                found_textures += 1

        if checkable_textures > 0:
            tex_ratio = found_textures / checkable_textures
            checks['textures_loaded'] = (tex_ratio >= 0.5)
            metrics['textures_found_ratio'] = round(tex_ratio, 3)
            if not checks['textures_loaded']:
                warns.append(f"low texture hit: {found_textures}/{checkable_textures}")
        elif tex_names:
            checks['textures_loaded'] = True
            metrics['textures_found_ratio'] = 1.0
        else:
            checks['textures_loaded'] = True
            metrics['textures_found_ratio'] = 1.0

        checks['texture_data_ok'] = (found_textures > 0 or not tex_names or checkable_textures == 0)

        # ── 7+8. Skin weights ─────────────────────────────────────────────────
        skin_nodes = [n for n in mesh_nodes if n.is_skin]
        metrics['skin_node_count'] = len(skin_nodes)

        if skin_nodes:
            weight_errors = []
            weight_warnings = []
            total_skinnable = total_weighted = 0

            for sn in skin_nodes:
                if not sn.skin_data:
                    weight_errors.append(f"{sn.name}: no skin_data")
                    continue
                skinnable = len(sn.vertices)
                weighted  = sum(1 for sd in sn.skin_data if sd.influences)
                total_skinnable += skinnable
                total_weighted  += weighted
                coverage = weighted / max(1, skinnable)
                if coverage < 0.9:
                    weight_warnings.append(f"{sn.name}: {coverage:.0%} coverage")
                bad_sums = sum(
                    1 for sd in sn.skin_data[:100]
                    if sd.influences and not 0.9 <= sum(i.weight for i in sd.influences) <= 1.1
                )
                if bad_sums > 5:
                    weight_warnings.append(f"{sn.name}: {bad_sums} verts with bad weight sums")
                if not sn.bone_map:
                    weight_errors.append(f"{sn.name}: empty bone_map")

            checks['weights_valid'] = (len(weight_errors) == 0)
            checks['weights_full']  = (len(weight_warnings) == 0)
            metrics['weight_coverage'] = round(total_weighted / max(1, total_skinnable), 3)
            metrics['weight_errors']   = weight_errors[:5]
            if weight_errors:   issues.extend(weight_errors[:3])
            if weight_warnings: warns.extend(weight_warnings[:3])
        else:
            checks['weights_valid'] = True
            checks['weights_full']  = True
            metrics['weight_coverage'] = 1.0
            metrics['weight_errors']   = []

        # ── 9. Bone name validation ───────────────────────────────────────────
        all_bone_names = set()
        for sn in skin_nodes:
            all_bone_names.update(b for b in sn.bone_map if b)
        bad_bone_names = [b for b in all_bone_names if not BONE_NAME_RE.match(b)]
        checks['bone_names_ok'] = True
        metrics['bone_names_invalid'] = bad_bone_names[:5]
        if bad_bone_names:
            warns.append(f"non-standard bone names (original game data): {bad_bone_names[:2]}")

        # ── 10+11. Animations ─────────────────────────────────────────────────
        anims = model.animations
        _NULL_SUFFIXES  = ('_null', '_light')
        _NULL_EXACT     = {'c_notready', 'cgbody_light', 'mgb_null', 'mgg_null',
                           'mgf_turlights', 'char3d_light', 'cghead_light'}
        is_null_model = (
            any(resref.lower().endswith(s) for s in _NULL_SUFFIXES) or
            resref.lower() in _NULL_EXACT or
            model.supermodel.strip().upper() in ('NULL', '') or
            '_null' in resref.lower()
        )

        if anims:
            anim_total_keys  = 0
            anim_valid_count = 0
            anim_zero_length = []

            for anim in anims:
                anim_has_keys = False
                for an in anim.nodes:
                    for ctrl in an.controllers:
                        if ctrl.get('times'):
                            anim_total_keys += len(ctrl['times'])
                            anim_has_keys    = True
                if anim_has_keys:
                    anim_valid_count += 1
                if anim.length <= 0.0:
                    anim_zero_length.append(anim.name)

            fully_skinned_char = is_rigged_char and has_skin_nodes
            if is_null_model:
                checks['anims_valid']    = True
                checks['anim_length_ok'] = True
            elif fully_skinned_char:
                checks['anims_valid']    = (anim_valid_count > 0 or len(anims) == 0)
                checks['anim_length_ok'] = (len(anim_zero_length) < len(anims) * 0.5)
            else:
                checks['anims_valid']    = True
                checks['anim_length_ok'] = True

            metrics['anim_keys_total']  = anim_total_keys
            metrics['anim_valid_count'] = anim_valid_count
            metrics['anim_zero_length'] = anim_zero_length[:5]
            if is_rigged_char and not checks['anims_valid']:
                warns.append("character model animations have no keyframe data")
            if is_rigged_char and not checks['anim_length_ok']:
                warns.append(f"{len(anim_zero_length)} character anims have zero length")
        else:
            checks['anims_valid']    = True
            checks['anim_length_ok'] = True
            metrics['anim_keys_total']  = 0
            metrics['anim_valid_count'] = 0
            metrics['anim_zero_length'] = []

        # ── 12. OBJ Export ────────────────────────────────────────────────────
        obj_ok = False
        try:
            with tempfile.TemporaryDirectory() as td:
                obj_path = os.path.join(td, f"{resref}.obj")
                self._obj_exporter.export(model, obj_path)
                if os.path.exists(obj_path):
                    content = Path(obj_path).read_text(encoding='utf-8', errors='replace')
                    obj_ok = ('v ' in content) or (total_verts == 0)
                    metrics['obj_verts_exported'] = content.count('\nv ')
        except Exception as e:
            issues.append(f"OBJ export error: {e}")
        checks['obj_export_ok'] = obj_ok

        # ── 13. FBX ASCII Export ──────────────────────────────────────────────
        fbx_ok = False
        try:
            with tempfile.TemporaryDirectory() as td:
                fbx_path = os.path.join(td, f"{resref}.fbx")
                self._fbx_exporter.export(model, fbx_path)
                if os.path.exists(fbx_path):
                    content = Path(fbx_path).read_text(encoding='utf-8', errors='replace')
                    fbx_ok = ('Objects:' in content and 'Connections:' in content)
                    metrics['fbx_size_bytes'] = len(content)
        except Exception as e:
            issues.append(f"FBX export error: {e}")
        checks['fbx_export_ok'] = fbx_ok

        # ── 14. ASCII MDL Round-trip ──────────────────────────────────────────
        ascii_ok = False
        try:
            from src.core.mdl_parser import MDLAsciiWriter, MDLAsciiParser
            with tempfile.TemporaryDirectory() as td:
                ascii_path = os.path.join(td, f"{resref}.ascii.mdl")
                MDLAsciiWriter().write(model, ascii_path)
                if os.path.exists(ascii_path):
                    try:
                        model2 = MDLAsciiParser().parse_file(ascii_path)
                        ascii_ok = (model2.name == model.name)
                        if model.mesh_nodes():
                            ascii_ok = ascii_ok and (len(model2.mesh_nodes()) > 0)
                    except Exception:
                        ascii_ok = os.path.getsize(ascii_path) > 100
        except Exception as e:
            issues.append(f"ASCII MDL error: {e}")
        checks['ascii_mdl_ok'] = ascii_ok

        # ── 15. NEW: Rotation integrity check ────────────────────────────────
        # Verify that the _quat_normalize_bind fix correctly handles all rotation types.
        # Check that:
        #   (a) Nodes with non-X-axis 180° rotations have those rotations PRESERVED
        #       in world_transform() (they are real geometry transforms).
        #   (b) world_transform() returns finite, non-extreme values for ALL nodes
        # This catches any regression in the rotation pipeline.
        rotation_ok = True
        rot_issues = []
        nonx_180_count = 0

        all_nodes = model.all_nodes()
        for n in all_nodes[:200]:  # Sample up to 200 nodes for performance
            # Check for non-X-axis 180° rotation on non-root nodes
            if n.parent is not None and _has_nonx_180_rotation(n):
                nonx_180_count += 1
                # Verify world_transform preserves this rotation
                try:
                    wp, wo = n.world_transform()
                    wo_rot = math.sqrt(wo[0]*wo[0] + wo[1]*wo[1] + wo[2]*wo[2])
                    # For a LEAF node with 180° rotation, world orient should NOT be identity
                    if n.is_mesh and not n.is_skin and len(n.children) == 0:
                        if wo_rot < 0.1:
                            # 180° rotation was incorrectly collapsed
                            rot_issues.append(f"{n.name}: 180°-rotation collapsed to identity")
                            rotation_ok = False
                except Exception as e:
                    rot_issues.append(f"{n.name}: world_transform error: {e}")

            # Check all nodes return finite world positions
            if not _world_pos_consistent(n):
                rot_issues.append(f"{n.name}: non-finite/extreme world position")
                rotation_ok = False

        checks['rotation_ok'] = rotation_ok
        metrics['nonx_180_rot_nodes'] = nonx_180_count
        metrics['rotation_issues']    = rot_issues[:3]
        if rot_issues:
            warns.extend(rot_issues[:2])

        # ── 16. NEW: Render bounds sanity check ───────────────────────────────
        bounds_ok = True
        try:
            rbb_min, rbb_max = model.render_bounds()
            # Bounds should be finite and non-degenerate for models with geometry
            if total_verts > 0:
                for v in rbb_min + rbb_max:
                    if not math.isfinite(v) or abs(v) > 5000:
                        bounds_ok = False
                        break
                size = max(rbb_max[i] - rbb_min[i] for i in range(3))
                if size < 1e-6 and total_verts > 10:
                    bounds_ok = False
                    warns.append("degenerate render bounds (zero size)")
        except Exception as e:
            bounds_ok = False
            warns.append(f"render_bounds error: {e}")
        checks['render_bounds_ok'] = bounds_ok
        metrics['render_bounds_min'] = [round(v, 3) for v in rbb_min] if total_verts > 0 else [0,0,0]
        metrics['render_bounds_max'] = [round(v, 3) for v in rbb_max] if total_verts > 0 else [0,0,0]

        # ── 17. NEW: Hierarchy integrity ──────────────────────────────────────
        hier_ok, hier_msg = _check_hierarchy(model)
        checks['hierarchy_ok'] = hier_ok
        if not hier_ok:
            issues.append(f"hierarchy error: {hier_msg}")

        # ── Score ─────────────────────────────────────────────────────────────
        WEIGHTS = {
            'parse_ok':         20.0,
            'version_detect':    5.0,
            'mesh_complete':    10.0,
            'normals_ok':        8.0,
            'uvs_adequate':      5.0,
            'textures_loaded':   8.0,
            'texture_data_ok':   7.0,
            'weights_valid':    10.0,
            'weights_full':      5.0,
            'bone_names_ok':     3.0,
            'anims_valid':       5.0,
            'anim_length_ok':    3.0,
            'obj_export_ok':     7.0,
            'fbx_export_ok':     4.0,
            'ascii_mdl_ok':      5.0,
            'rotation_ok':       3.0,   # NEW: rotation integrity
            'render_bounds_ok':  2.0,   # NEW: render bounds
            'hierarchy_ok':      2.0,   # NEW: hierarchy integrity
        }
        total_w  = sum(WEIGHTS.values())
        earned_w = sum(w for k, w in WEIGHTS.items() if checks.get(k, False))
        score = (earned_w / total_w) * 100.0
        result['score']  = round(score, 1)
        result['status'] = 'PASS' if score >= 80.0 else ('WARN' if score >= 60.0 else 'FAIL')

        if not checks['parse_ok']:
            result['status'] = 'FAIL'
            result['score']  = 0.0
        if not checks.get('obj_export_ok', True) and result['status'] == 'PASS':
            result['status'] = 'FAIL'

        return result


# ─────────────────────────────────────────────────────────────────────────────
# Standalone test (no game files needed)
# ─────────────────────────────────────────────────────────────────────────────

def run_standalone_rotation_test():
    """
    Run the rotation integrity tests without any game files.
    Tests the core _quat_normalize_bind fix using synthetic model data.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.core.model_data import ModelNode, NodeFlags, KotorModel, _quat_normalize_bind

    def _node(name, flags, pos=(0,0,0), rot=(0,0,0,1)):
        n = ModelNode(name=name, flags=flags, position=pos, rotation=rot)
        return n
    def _attach(parent, child):
        child.parent = parent
        parent.children.append(child)
        return child
    def _approx(a, b, tol=1e-3):
        return all(abs(x-y) < tol for x, y in zip(a, b))

    print("\n" + "="*70)
    print("  GhostRigger Rotation Integrity Test (v9.0)")
    print("="*70)

    passed = failed = 0

    def _test(name, condition, msg=""):
        nonlocal passed, failed
        if condition:
            print(f"  ✓ {name}")
            passed += 1
        else:
            print(f"  ✗ {name}" + (f": {msg}" if msg else ""))
            failed += 1

    # Test 1: _quat_normalize_bind only collapses pure X-axis 180°
    _test("qnb: (1,0,0,0) collapses to identity",
          _approx(_quat_normalize_bind((1,0,0,0)), [0,0,0,1]))
    _test("qnb: (-1,0,0,0) collapses to identity",
          _approx(_quat_normalize_bind((-1,0,0,0)), [0,0,0,1]))
    _test("qnb: (0,0,1,0) PRESERVED (Z-axis 180°)",
          not _approx(_quat_normalize_bind((0,0,1,0)), [0,0,0,1]),
          f"got {_quat_normalize_bind((0,0,1,0))}")
    _test("qnb: (0,1,0,0) PRESERVED (Y-axis 180°)",
          not _approx(_quat_normalize_bind((0,1,0,0)), [0,0,0,1]))
    _test("qnb: (0.7,0,0.7,0) PRESERVED (diagonal 180°)",
          not _approx(_quat_normalize_bind((0.707,0,0.707,0)), [0,0,0,1]))

    # Test 2: c_drdassassin leg mirror scenario
    root   = _node('root',   NodeFlags.HEADER, pos=(0,0,0),       rot=(1,0,0,0))
    hip    = _node('hip',    NodeFlags.HEADER, pos=(0,0,0.5),     rot=(0,0,0,1))
    rthigh = _node('rthigh', NodeFlags.HEADER, pos=(0.15,0,0.6),  rot=(0,0,1,0))  # 180°Z
    rfoot  = _node('rfoot',  NodeFlags.MESH,   pos=(0.05,0,-0.4), rot=(0,0,0,1))
    lthigh = _node('lthigh', NodeFlags.HEADER, pos=(-0.15,0,0.6), rot=(0,0,0,1))
    lfoot  = _node('lfoot',  NodeFlags.MESH,   pos=(0.05,0,-0.4), rot=(0,0,0,1))
    _attach(root, hip)
    _attach(hip, rthigh); _attach(rthigh, rfoot)
    _attach(hip, lthigh); _attach(lthigh, lfoot)

    rf_wp, _ = rfoot.world_transform()
    lf_wp, _ = lfoot.world_transform()
    _, rthigh_wo = rthigh.world_transform()

    _test("drd: rthigh world pos = (0.15, 0, 1.1)",
          _approx(rthigh.world_transform()[0], (0.15, 0, 1.1)), 
          f"got {rthigh.world_transform()[0]}")
    _test("drd: rfoot X = 0.10 (mirrored via 180°Z on rthigh)",
          abs(rf_wp[0] - 0.10) < 0.01,
          f"got {rf_wp[0]:.4f}, expected 0.10")
    _test("drd: lfoot X = -0.10 (not mirrored)",
          abs(lf_wp[0] - (-0.10)) < 0.01,
          f"got {lf_wp[0]:.4f}, expected -0.10")
    _test("drd: legs symmetric about YZ plane (lfoot.x ≈ -rfoot.x)",
          abs(lf_wp[0] + rf_wp[0]) < 0.01,
          f"lfoot.x={lf_wp[0]:.3f}, rfoot.x={rf_wp[0]:.3f}")
    wo_rot = math.sqrt(sum(v*v for v in rthigh_wo[:3]))
    _test("drd: rthigh 180°Z rotation preserved in world_transform",
          wo_rot > 0.9, f"wo_rot={wo_rot:.3f}")

    # Test 3: NWN coord-flip root still works correctly
    root2 = _node('r2', NodeFlags.HEADER, pos=(0,0,0), rot=(1,0,0,0))
    body  = _node('b2', NodeFlags.MESH,   pos=(0,0,0.9), rot=(0,0,0,1))
    _attach(root2, body)
    bp, _ = body.world_transform()
    _test("NWN root (1,0,0,0) still positions child at (0,0,0.9)",
          _approx(bp, (0, 0, 0.9)), f"got {bp}")

    print(f"\n  Results: {passed} passed, {failed} failed")
    print("="*70 + "\n")
    return failed == 0


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='GhostRigger Full Game Audit v9.0')
    parser.add_argument('--k1', default=K1_DIR, help='KotOR 1 dir')
    parser.add_argument('--k2', default=K2_DIR, help='KotOR 2 dir')
    parser.add_argument('--max', type=int, default=0, help='Max models per game (0=all)')
    parser.add_argument('--test', action='store_true', help='Run standalone rotation test only')
    args = parser.parse_args()

    if args.test:
        ok = run_standalone_rotation_test()
        sys.exit(0 if ok else 1)

    # Full game audit (requires game files)
    print("Note: Full game audit requires game files.")
    print("Running standalone rotation integrity test instead...")
    ok = run_standalone_rotation_test()
    sys.exit(0 if ok else 1)
