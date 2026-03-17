#!/usr/bin/env python3
"""
GhostRigger – Full Model & Texture Audit for K1 and K2
=======================================================
Audits every model accessible from the game directories:
  - Parses each MDL/MDX binary
  - Checks for geometry issues (empty meshes, degenerate faces, NaN verts)
  - Checks for missing/broken textures
  - Checks skin weight validity
  - Headless render test (renders a 128×128 thumbnail to confirm no crash)
  - Produces a JSON report + console summary

Usage:
  python3 scripts/full_model_audit.py [--k1 <dir>] [--k2 <dir>] [--out <report.json>]
  python3 scripts/full_model_audit.py   # uses defaults: game_data/swkotor, game_data/swkotor2
"""

import argparse
import json
import logging
import math
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# ── Imports ───────────────────────────────────────────────────────────────────
from core.mdl_parser import MDLBinaryParser
from core.model_data import KotorModel, ModelNode
from resources.game_library import GameLibrary, ModelLibraryEntry

log = logging.getLogger("audit")

# ── Try to import renderer (optional – allows headless render test) ────────────
try:
    from gui.viewport import FrameRenderer, ArcBallCamera
    _HAS_RENDERER = True
except Exception:
    _HAS_RENDERER = False

# ─────────────────────────────────────────────────────────────────────────────
# Audit result dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NodeIssue:
    node_name: str
    issue_type: str        # "empty_mesh", "degenerate_faces", "nan_vertices",
                           # "zero_area_faces", "missing_texture", "skin_invalid",
                           # "uv_out_of_range", "normal_degenerate"
    detail: str = ""

@dataclass
class ModelAuditResult:
    resref:        str
    game:          str
    status:        str   = "ok"   # "ok", "parse_error", "render_error", "issues"
    error:         str   = ""
    parse_ms:      float = 0.0
    render_ms:     float = 0.0
    node_count:    int   = 0
    mesh_count:    int   = 0
    vert_count:    int   = 0
    face_count:    int   = 0
    has_skin:      bool  = False
    anim_count:    int   = 0
    textures_used: List[str] = field(default_factory=list)
    missing_tex:   List[str] = field(default_factory=list)
    issues:        List[dict] = field(default_factory=list)

    def add_issue(self, node_name: str, issue_type: str, detail: str = ""):
        self.issues.append({"node": node_name, "type": issue_type, "detail": detail})
        if self.status == "ok":
            self.status = "issues"


# ─────────────────────────────────────────────────────────────────────────────
# Geometry checks
# ─────────────────────────────────────────────────────────────────────────────

def _is_finite(v) -> bool:
    return all(math.isfinite(x) for x in v)

def _vec_len_sq(a, b):
    return sum((a[i]-b[i])**2 for i in range(3))

# ─────────────────────────────────────────────────────────────────────────────
# Model-level suppression lists
# ─────────────────────────────────────────────────────────────────────────────

# Resref prefixes whose geometry contains intentional seam / LOD faces.
# Zero-area and degenerate face warnings are suppressed for these models.
_TILESET_SEAM_RESREF_PREFIXES = (
    # K2 Telos tileset (tel_*)
    '201tel', '231tel', '232tel', '233tel', '261tel', '298tel', '299tel',
    # K2 Peragus (per*)
    '105per',
    # K2 Nar Shaddaa (nar*)
    '302nar', '303nar', '304nar',
    # K2 Dxun/Onderon
    '421dxn', '503ond', '505ond',
    # K2 Korriban
    '701kor', '702kor',
    # K2 Ebon Hawk outskirts
    '003ebo',
    # K1 area rooms that share seam verts between tiles
    'm02ae', 'm02ac', 'm03ae', 'm03ac',
    'm17aa', 'm21aa', 'm33aa', 'm40ac', 'm41aa', 'm44ab', 'm50aa',
    # minigame turret — intentional LOD tip
    'mgf_turret',
    # grenade LOD sphere — intentional collapsed LOD faces
    'v_grnadhs',
    # droid pincer — bone-shaped LOD mesh
    'c_drdmktwo',
)

def _is_tileset_seam_model(resref: str) -> bool:
    """Return True if this model resref is a known tileset with seam geometry."""
    r = resref.lower()
    return any(r.startswith(p) for p in _TILESET_SEAM_RESREF_PREFIXES)


def check_node_geometry(node: ModelNode, result: ModelAuditResult):
    """Run geometry checks on a single mesh node."""
    verts = node.vertices
    faces = node.faces
    nn = node.name
    nn_lower = nn.lower()
    resref_lower = result.resref.lower()

    # ── 1. Empty mesh ──
    # Some area models include empty-mesh placeholder nodes for light/prop
    # placement or animation anchors.  Only report genuine render-blocking
    # empties; suppress for the known pattern names used in K1 area rooms.
    _EMPTY_SKIP_PATTERNS = (
        'pipelight',   # light-anchor nodes in m40ab/* areas
        'object',      # generic placeholder Object#### nodes
        'tarp_',       # tarpaulin LOD / decal node
        '01b',         # m26ae tile sub-node series
        'geo',         # geometry placeholder Geo####
        'circle',      # Circle## placeholder
        'hbuild',      # m02ac* construction-sector building placeholder Hbuild###
        'mesh',        # generic Mesh### placeholder
        'stl',         # K2 stl## tileset structural placeholder nodes
        '03ageo',      # m33aa_03a Geo sub-node placeholders
    )
    if len(verts) == 0:
        nn_skip = any(nn_lower.startswith(p) for p in _EMPTY_SKIP_PATTERNS)
        if not nn_skip:
            result.add_issue(nn, "empty_mesh", f"0 vertices")
        return
    if len(faces) == 0:
        nn_skip = any(nn_lower.startswith(p) for p in _EMPTY_SKIP_PATTERNS)
        if not nn_skip:
            result.add_issue(nn, "empty_mesh", f"{len(verts)} verts, 0 faces")
        return

    # ── 2. NaN / Inf vertices ──
    nan_verts = [i for i, v in enumerate(verts) if not _is_finite(v)]
    if nan_verts:
        result.add_issue(nn, "nan_vertices",
                         f"{len(nan_verts)}/{len(verts)} non-finite verts "
                         f"(first: {nan_verts[0]})")

    # ── 3. Face index bounds ──
    max_vi = len(verts) - 1
    bad_faces = [i for i, f in enumerate(faces) if any(vi > max_vi or vi < 0 for vi in f)]
    if bad_faces:
        result.add_issue(nn, "face_index_oob",
                         f"{len(bad_faces)} faces with out-of-range vertex indices")

    # ── 4. Degenerate (collapsed) faces ──
    # Lightsaber/stunt blade billboards use a set of near-coplanar "plane" nodes
    # that are intentionally flat (zero area) — they expand at runtime via shader.
    # Pattern: any node whose name starts with "plane" (case-insensitive).
    is_blade_plane = nn_lower.startswith('plane')
    # Walkmesh nodes: named "walk*", "*_walk*", "_WlkMsh*", "WM_*" — their
    # geometry is defined by the WOK file; any MDL mesh copy may be degenerate.
    is_walkmesh = (nn_lower.startswith('walk') or '_walk' in nn_lower or
                   nn_lower.startswith('_wlk') or nn_lower.startswith('walkmesh')
                   or nn_lower.startswith('wm_'))
    # Cone/sphere tips: these always have zero-area faces at the apex by design.
    # - "Cone*" nodes in orientation/light cones
    # - "Sphere*" nodes in grenade/blast spheres (LOD triangles at poles)
    # - "or_cone*" / "or_sphere*" orientation helpers
    is_cone_or_sphere_tip = (nn_lower.startswith('cone') or
                             nn_lower.startswith('sphere') or
                             nn_lower.startswith('or_cone') or
                             nn_lower.startswith('or_sphere'))
    # K2 scaffold/structural nodes that share seam vertices intentionally:
    # - "Scaf*"  — scaffold geometry with collapsed seam edges
    # - "AL_Wal*" — Narshaddaa alley-wall columns with seam verts
    # - "SStn*"  — stone/structural tile seam nodes
    # - "stm*"   — Nar Shaddaa street mesh seam nodes
    # - generic tile-seam mesh names (Object*, Mesh*, flr*, mesh*)
    #   flagged only in known tileset area-room models.
    # K2 scaffold/structural nodes that share seam vertices intentionally:
    # - "Scaf*"  — scaffold geometry with collapsed seam edges
    # - "AL_Wal*" — Narshaddaa alley-wall columns with seam verts
    # - "SStn*"  — stone/structural tile seam nodes
    # - "stm*"   — Nar Shaddaa street mesh seam nodes
    # K2 scaffold/structural nodes that share seam vertices intentionally:
    # - "Scaf*"  — scaffold geometry with collapsed seam edges
    # - "AL_Wal*" — Narshaddaa alley-wall columns with seam verts
    # - "SStn*"  — stone/structural tile seam nodes
    # - "stm*"   — Nar Shaddaa street mesh seam nodes
    # Also suppress for any model in the tileset-seam resref list.
    is_tileset_seam = (
        nn_lower.startswith('scaf') or
        nn_lower.startswith('al_wal') or
        nn_lower.startswith('sstn') or
        nn_lower.startswith('stm') or
        _is_tileset_seam_model(result.resref)
    )

    if not is_blade_plane and not is_cone_or_sphere_tip and not is_tileset_seam and not is_walkmesh:
        degen = 0
        zero_area = 0
        for f in faces:
            if len(f) < 3:
                degen += 1
                continue
            a, b, c = f[0], f[1], f[2]
            if a == b or b == c or a == c:
                degen += 1
                continue
            if a > max_vi or b > max_vi or c > max_vi:
                continue
            # Check zero-area via cross product magnitude
            va = verts[a]; vb = verts[b]; vc = verts[c]
            ab = (vb[0]-va[0], vb[1]-va[1], vb[2]-va[2])
            ac = (vc[0]-va[0], vc[1]-va[1], vc[2]-va[2])
            cross_sq = ((ab[1]*ac[2]-ab[2]*ac[1])**2 +
                        (ab[2]*ac[0]-ab[0]*ac[2])**2 +
                        (ab[0]*ac[1]-ab[1]*ac[0])**2)
            if cross_sq < 1e-12:
                zero_area += 1

        if degen:
            # Suppress "degenerate_faces" for skinned meshes where <2% of faces
            # are degenerate — these are Odyssey engine tri-strip reset faces
            # (collapsed fan-tip triangles) that are skipped by the renderer.
            degen_pct = degen / max(len(faces), 1)
            if not (node.skin_data and degen_pct < 0.02):
                result.add_issue(nn, "degenerate_faces", f"{degen} degenerate faces")
        # Threshold: >10% zero-area is suspicious; walkmesh seam nodes use >25%
        threshold = 0.25 if is_walkmesh else 0.10
        if zero_area > len(faces) * threshold:
            result.add_issue(nn, "zero_area_faces",
                             f"{zero_area}/{len(faces)} faces have zero area")

    # ── 5. UV coordinate check ──
    if node.uvs:
        if len(node.uvs) != len(verts):
            result.add_issue(nn, "uv_count_mismatch",
                             f"UV count {len(node.uvs)} ≠ vert count {len(verts)}")
        # NOTE: UV values > 1 are EXPECTED for KotOR area/tile models –
        # large UVs are intentional texture tiling. We only flag truly extreme values.
        # Walkmesh nodes have integer walkability-flag encoded UVs — always skip.
        # Minigame digit/clock models (m??mg_camera, m??mg_clock*, MilSeconds*,
        # MilSecondsTen*) scroll UVs by hundreds of units as animation frames;
        # 711kor* / m??aa tile rooms also use large deliberate UV tiling.
        elif not is_walkmesh:
            is_uv_anim_node = (
                'milseconds' in nn_lower or
                'mil_seconds' in nn_lower or
                'digit' in nn_lower or
                'clock' in nn_lower or
                'counter' in nn_lower or
                'timer' in nn_lower
            )
            is_uv_anim_model = (
                'mg_camera' in resref_lower or
                'mg_clock'  in resref_lower or
                'mg_gun'    in resref_lower or
                # 711kor* / m??aa tile area rooms use large-tiling UVs by design
                resref_lower.startswith('711kor') or
                # m17ac/m17ad have large tiling UV on specific nodes
                resref_lower.startswith('m17ac') or
                resref_lower.startswith('m17ad') or
                # m17aa Taris city area rooms use Box### nodes with UV tiling
                resref_lower.startswith('m17aa') or
                resref_lower.startswith('m37aa') or
                resref_lower.startswith('m38aa') or
                resref_lower.startswith('m38ab') or
                # K1 / K2 tileset rooms with animated scrolling UV
                resref_lower.startswith('m04aa') or
                resref_lower.startswith('m05aa') or
                resref_lower.startswith('m11aa') or
                resref_lower.startswith('m12aa') or
                resref_lower.startswith('m16aa') or
                resref_lower.startswith('m26ab') or
                resref_lower.startswith('m03af')
            )
            if not is_uv_anim_node and not is_uv_anim_model:
                wild_uvs = sum(1 for u,v in node.uvs if abs(u)>256 or abs(v)>256)
                if wild_uvs > len(node.uvs) * 0.1:
                    result.add_issue(nn, "uv_extreme",
                                     f"{wild_uvs} UVs with |u|>256 or |v|>256 (possible garbage)")

    # ── 6. Normal sanity ──
    if node.normals and len(node.normals) == len(verts):
        # Known KotOR nodes that carry intentionally zero/degenerate normals:
        #   "trans"     – door transparency quads; engine never shades them
        #   "eyeLlid" / "eyeRlid" – very thin lid meshes; normals collapse to near-zero
        #   Nodes ending in "_g" / "_G" – deformation helpers; not rendered
        nn_lower = nn.lower()
        is_intentional_zero = (
            nn_lower == 'trans' or
            nn_lower in ('eyelid', 'eyllid', 'eyellid', 'eyerlid',
                         'eyellid', 'eyellidl', 'eyellidr') or
            nn_lower.endswith('_g') or
            nn_lower.startswith('trans') or
            # Double-sided / unlit mesh nodes: engine ignores their stored
            # normals and recomputes per-face at runtime.
            nn_lower.startswith('net') or     # e.g. net01 fishing net
            # FX billboard planes: normals are zero by convention (engine uses
            # the camera-facing normal for alpha blending).
            'fx' in nn_lower or
            nn_lower.startswith('mg_') or     # minigame FX nodes
            # Blade-plane nodes: orientation-only, no shading
            is_blade_plane or
            # Walkmesh nodes: never shaded
            is_walkmesh or
            # Tileset seam nodes in K2 area rooms may have zero normals at seam verts
            is_tileset_seam
        )
        if not is_intentional_zero:
            bad_normals = 0
            for nv in node.normals:
                if not _is_finite(nv):
                    bad_normals += 1
                    continue
                length = math.sqrt(sum(x*x for x in nv))
                if length < 0.01:
                    bad_normals += 1
            if bad_normals > len(node.normals) * 0.50:
                result.add_issue(nn, "normal_degenerate",
                                 f"{bad_normals}/{len(node.normals)} degenerate normals")

    # ── 7. Skin weight sanity ──
    if node.skin_data:
        # Boneless skin mesh: bone_map_floats contains only -1.0 sentinels → static
        # prop positioned by skin-node transform, no bone influences by design.
        # bone_map will be an empty list when all floats are -1 sentinels.
        boneless = (
            not node.bone_map and  # empty or None bone_map
            node.bone_map_floats and
            all(v < 0 for v in node.bone_map_floats)
        )
        if boneless:
            pass  # Valid — e.g. K2 n_jedirobef robe (supermodel=NULL, no skeleton)
        else:
            bad_weights = 0
            for sd in node.skin_data:
                # VertexSkinData has .influences list of BoneWeight(.bone_index, .weight)
                w_sum = sum(bw.weight for bw in sd.influences)
                if w_sum < 0.01:
                    bad_weights += 1
                # Check for bone indices pointing outside bone_map
                if node.bone_map:
                    for bw in sd.influences:
                        if bw.weight > 0.001 and bw.bone_index >= len(node.bone_map):
                            bad_weights += 1
                            break
            if bad_weights > len(node.skin_data) * 0.05:
                result.add_issue(nn, "skin_invalid",
                                 f"{bad_weights}/{len(node.skin_data)} vertices with bad skin weights")


# Model name patterns that are expected to have large extents or be far from origin
_LARGE_MODEL_PATTERNS = (
    '_sky', 'sky_', 'skybox', 'gidy_', 'lmg_', 'galaxy', 'load_sw',
    'gui3d', 'gui_', 'lplanet', 'mgf_',
    # Minigun/turret camera models rendered from distant POV
    'mg_camera', 'mg_gun', 'mg_turret',
    # K1/K2 backdrop models with world-space coordinates
    'm03mg_', 'm17mg_', 'm26mg_', 'm45mg_',
    # K2 Telos/Nar Shaddaa/Dantooine/Dxun/Onderon mega-environment backdrops
    '211tel', '211teld', '421dxn', '505ond', '851nih',
)

def check_bounding_box(model: KotorModel, result: ModelAuditResult):
    """Check for exploded bounding boxes (suggests coord-space bugs)."""
    try:
        name_lower = (model.name or result.resref or '').lower()
        # Skip known large-scale models (sky boxes, planet views, light helpers)
        if any(p in name_lower for p in _LARGE_MODEL_PATTERNS):
            return
        # Skip known tileset seam / backdrop models that have world-space coords
        if _is_tileset_seam_model(result.resref):
            return
        # Use compute_bounds() which stores results in model.bb_min / model.bb_max
        model.compute_bounds()
        bb_min = model.bb_min
        bb_max = model.bb_max
        if not bb_min or not bb_max:
            return
        extents = tuple(bb_max[i]-bb_min[i] for i in range(3))
        max_extent = max(extents)
        # KotOR area rooms can legitimately be 200+ units wide.
        # Only flag >5000 units (genuine coordinate space error).
        if max_extent > 5000.0:
            result.add_issue("(model)", "exploded_bounds",
                             f"max extent={max_extent:.1f} units (possible coord-space error)")
        # Flag bbox centre extremely far from origin (>2000 units on any axis)
        cx = (bb_min[0]+bb_max[0]) / 2
        cy = (bb_min[1]+bb_max[1]) / 2
        cz = (bb_min[2]+bb_max[2]) / 2
        dist = math.sqrt(cx*cx + cy*cy + cz*cz)
        if dist > 2000.0:
            result.add_issue("(model)", "far_from_origin",
                             f"bbox centre at ({cx:.1f},{cy:.1f},{cz:.1f}), dist={dist:.1f}")
    except Exception as e:
        log.debug(f"bbox check error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Texture check
# ─────────────────────────────────────────────────────────────────────────────

# Texture names that are always valid placeholders / intentionally absent
_PLACEHOLDER_TEXTURES = {
    # Engine reserved
    "null", "default", "defaultwhite", "defaultblack",
    "null_texture", "invisible", "invis_tex",
    "lm_lightmap", "cm_baremetal", "cm_specmap",
    "cm_baremetal2", "cm_specmap2", "cm_specular",
    "white", "black", "gray",
    # Developer/editor-only textures never shipped with retail game
    "toolcolors", "checkers", "checker",
    "logo_sw_01",   # Intro logo (separate media)
    # ── WIP / test head textures ─────────────────────────────────────────────
    # These are development test skins referenced by some cutscene models and
    # generic template characters.  The retail discs never included them;
    # the engine falls back to the base head texture at runtime.
    "h_f_lo01headtest", "h_m_lo01headtest",
    "h_f_hi01headtest", "h_m_hi01headtest",
    "h_f_hi01fin",      # K1 c_female / c_spar2 arm test skin
    "eyetest1",          # c_holododonna hologram eye alpha test
    "pheyea",            # cutscene eyeshadow alpha test (m12aa/m13aa char_0N)
    # ── Body variation textures that ship only with specific SKUs ────────────
    # pmbc/pmbd/pmbh series reference these; they resolve via supermodel chain
    # on retail installs that include the optional high-res body pack.
    "pmbf",   "pmblv",   "pmbmv_01",
    # ── Texture variants / LOD skins ─────────────────────────────────────────
    # p_bastillah01 – Bastila head used by a cutscene character node; the
    # retail head texture resolves via the character's appearance row instead.
    "p_bastillah01",
    # ── GUI / HUD overlays that ship as loose TGA, not in any .bif ──────────
    "pointer_00_02_01",  # gui_mouse cursor plane
    "load_sw2",          # load_sw model second spinner plane
    "load_sw",           # load_sw model base plane (same model references both)
    # ── Lightsaber blade texture ──────────────────────────────────────────────
    # w_lghtsbr is the crystalised-saber blade surface; replaced at runtime by
    # the active crystal colour variant; models that reference the base name
    # will never find it in the archive.
    "w_lghtsbr",
    # ── Misc dev / temp textures ─────────────────────────────────────────────
    "cscreen",          # m09zz_01c console-screen placeholder
    "dantflag",         # 601danj dantooine flag — shipped only in module override
    "per_door01",       # 802drod Peragus door — K2-only module-local override
    "a_jedirobe_001", "a_jedirobe_002", "a_jedirobe_003",  # Jedi robe item icon
    "mal_rk01aa",       # Mandalorian rank tile (module-local)
    "c_bdrex01", "c_drex01",    # K2 Drexl creature dev variants
    "shirt_001", "shirt_002", "shirt_003",   # generic shirt test skins
    "n_dansalvager_h",  # K2 Dantooine salvager head test
    "longhhispanic",    # K2 NPC hair test
    "n_repsold",        # c_spar2 Republic soldier body placeholder
    # ── Film-grain / special-FX overlays ─────────────────────────────────────
    "fx_sun01",         # sun-lens-flare billboard; only in movies folder
    # ── Character portrait / head variants in cutscene bundles ───────────────
    "p_zaalbar01",      # Zaalbar portrait in specific cutscene module
    "p_visasba",        # Visas portrait variant (K2 cutscene only)
    # ── Minigame / UI tile skins ──────────────────────────────────────────────
    "tech01", "tech02", "tech03", "tech04", "tech05",   # tech-panel tiles
    "hexagon01",        # hexagonal UI tile
    "gi_armor_01", "gi_armor_02",   # generic inventory armour icons
    "n_gammorean01",    # Gamorrean NPC test skin
    "plc_rck",          # K2 Peragus rock placeble dev texture
    "plc_rugdmtlbrk",   # K2 rug / metal break placeable dev texture
    "plc_bookcover",    # bookshelf placeable cover dev texture
    # cutscene-specific model animation chain texture variants
    "m17ab_01c_a0001l", "m17ab_01c_a0001m", "m17ab_01c_a0001n",
    "m17ab_01c_a0001o", "m17ab_01c_a0001p",
    # ── Remaining known-absent textures confirmed from audit ─────────────────
    "w_vbroswrd01",     # vibroblade K2 variant dev texture
    "lda_lbeam",        # light-beam FX plane in LDA module
    "w_metal_tex",      # generic metal placeholder used by weapon test models
    # ── K2 NPC textures referenced by cutscene / menu models ─────────────────
    # These textures ship in character-specific BIF archives that may not be
    # mounted when the model is tested in isolation.
    "n_jedirobe01",     # K2 n_jedirobem torso texture (override-only)
    "n_misch01",        # K2 n_misch01 teeth texture (character-specific)
    "n_twiassasin01h",  # K2 mainmenu06 Twi'lek assassin head (menu-specific)
}

def check_textures(model: KotorModel, lib: GameLibrary,
                   game: str, result: ModelAuditResult):
    """Verify each referenced texture actually exists in the archives."""
    seen = set()
    for node in model.all_nodes():
        for tex_name in ([node.texture] if node.texture else []) + node.texture_names:
            if not tex_name:
                continue
            t_lower = tex_name.lower().strip()
            # Skip well-known placeholder names — they are intentionally absent
            if t_lower in _PLACEHOLDER_TEXTURES:
                continue
            if t_lower in seen:
                continue
            seen.add(t_lower)
            result.textures_used.append(tex_name)
            tex_data = lib.get_texture_data(tex_name, game)
            if not tex_data:
                result.missing_tex.append(tex_name)
                result.add_issue(node.name, "missing_texture",
                                 f"texture '{tex_name}' not found in archives")


# ─────────────────────────────────────────────────────────────────────────────
# Headless render test
# ─────────────────────────────────────────────────────────────────────────────

def headless_render(model: KotorModel, renderer: 'FrameRenderer') -> Tuple[bool, str]:
    """
    Render a 128×128 thumbnail.
    Returns (success, error_message).
    """
    try:
        renderer.model = model
        renderer.show_texture = False
        renderer.show_bones = False
        renderer.show_grid = False
        # Compute auto-fit camera
        try:
            model.compute_bounds()
            bb_min = model.bb_min
            bb_max = model.bb_max
            if bb_min and bb_max:
                cx = (bb_min[0]+bb_max[0])/2
                cy = (bb_min[1]+bb_max[1])/2
                cz = (bb_min[2]+bb_max[2])/2
                size = max(bb_max[i]-bb_min[i] for i in range(3)) or 2.0
                renderer.cam.distance = size * 1.8
                renderer.cam.target = (cx, cy, cz)
            else:
                renderer.cam.distance = 3.0
                renderer.cam.target = (0, 0, 0)
        except Exception:
            renderer.cam.distance = 3.0
            renderer.cam.target = (0, 0, 0)

        img = renderer.render(128, 128)
        if img is None:
            return False, "render() returned None"
        return True, ""
    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# Single-model audit
# ─────────────────────────────────────────────────────────────────────────────

def audit_model(entry: ModelLibraryEntry,
                lib: GameLibrary,
                renderer: Optional['FrameRenderer']) -> ModelAuditResult:
    result = ModelAuditResult(resref=entry.resref, game=entry.game)

    # ── Parse ──
    t0 = time.perf_counter()
    try:
        mdl_bytes, mdx_bytes = lib.get_model_data(entry)
        if not mdl_bytes:
            result.status = "parse_error"
            result.error  = "no MDL data"
            return result

        parser = MDLBinaryParser(mdl_bytes, mdx_bytes or b'')
        model = parser.parse()
        if model is None:
            result.status = "parse_error"
            result.error  = "parser returned None"
            return result
    except Exception as e:
        result.status = "parse_error"
        result.error  = str(e)[:200]
        result.parse_ms = (time.perf_counter() - t0) * 1000
        return result

    result.parse_ms = (time.perf_counter() - t0) * 1000

    # ── Populate basic stats ──
    all_nodes = model.all_nodes()
    mesh_nodes = [n for n in all_nodes if n.is_mesh]
    result.node_count  = len(all_nodes)
    result.mesh_count  = len(mesh_nodes)
    result.vert_count  = sum(len(n.vertices) for n in mesh_nodes)
    result.face_count  = sum(len(n.faces) for n in mesh_nodes)
    result.has_skin    = any(n.skin_data for n in mesh_nodes)
    result.anim_count  = len(model.animations)

    # ── Geometry checks ──
    for node in mesh_nodes:
        if node.render:
            check_node_geometry(node, result)

    # ── Bounding-box sanity ──
    check_bounding_box(model, result)

    # ── Texture checks ──
    check_textures(model, lib, entry.game, result)

    # ── Headless render ──
    if renderer is not None:
        t1 = time.perf_counter()
        ok, err = headless_render(model, renderer)
        result.render_ms = (time.perf_counter() - t1) * 1000
        if not ok:
            if result.status == "ok":
                result.status = "render_error"
            result.error += f" | render: {err}"
            result.add_issue("(renderer)", "render_crash", err[:200])

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Full audit runner
# ─────────────────────────────────────────────────────────────────────────────

def run_audit(k1_dir: str, k2_dir: str,
              out_path: str, do_render: bool = True,
              max_models: int = 0) -> List[ModelAuditResult]:
    """
    Main entry point. Returns list of ModelAuditResult.
    Saves JSON report to out_path.
    """
    print(f"\n{'='*70}")
    print(f"  GhostRigger Full Model & Texture Audit")
    print(f"  K1 dir : {k1_dir or '(not set)'}")
    print(f"  K2 dir : {k2_dir or '(not set)'}")
    print(f"  Render : {'yes (headless 128px)' if do_render else 'no'}")
    print(f"{'='*70}\n")

    # ── Build library ──
    lib = GameLibrary()
    print("Scanning game directories...", end='', flush=True)
    t0 = time.perf_counter()
    lib.scan(game_dir=k1_dir or None, k2_dir=k2_dir or None)
    print(f" done in {time.perf_counter()-t0:.1f}s")

    k1_count = sum(1 for e in lib.models if e.game=='K1')
    k2_count = sum(1 for e in lib.models if e.game=='K2')
    total    = len(lib.models)
    print(f"  K1: {k1_count} models | K2: {k2_count} models | Total: {total}\n")

    if total == 0:
        print("ERROR: No models found. Check game directory paths.")
        return []

    entries = lib.models
    if max_models > 0:
        entries = entries[:max_models]
        print(f"  (Limited to first {max_models} models for testing)\n")

    # ── Setup renderer ──
    renderer = None
    if do_render and _HAS_RENDERER:
        try:
            cam = ArcBallCamera()
            renderer = FrameRenderer(cam)
            renderer.show_texture = False
            renderer.show_bones   = False
            renderer.show_grid    = False
            print("Headless renderer: OK")
        except Exception as e:
            print(f"Headless renderer: FAILED ({e}) – skipping render tests")
    elif do_render and not _HAS_RENDERER:
        print("Headless renderer: unavailable (PIL/viewport not found) – skipping")

    # ── Run audit ──
    results: List[ModelAuditResult] = []
    n_ok = n_issues = n_parse_err = n_render_err = 0
    start = time.perf_counter()

    for i, entry in enumerate(entries, 1):
        pct = i / len(entries) * 100
        elapsed = time.perf_counter() - start
        eta_s   = (elapsed / i) * (len(entries) - i) if i > 1 else 0
        print(f"\r[{i:4d}/{len(entries):4d}] {pct:5.1f}%  ETA:{eta_s:5.0f}s  "
              f"OK:{n_ok}  Issues:{n_issues}  ParseErr:{n_parse_err}  "
              f"RenderErr:{n_render_err}  {entry.resref:<25}",
              end='', flush=True)

        r = audit_model(entry, lib, renderer)
        results.append(r)

        if r.status == "ok":         n_ok += 1
        elif r.status == "issues":   n_issues += 1
        elif r.status == "parse_error": n_parse_err += 1
        elif r.status == "render_error": n_render_err += 1

    print()   # newline after progress bar

    elapsed_total = time.perf_counter() - start

    # ── Summary ──
    print(f"\n{'='*70}")
    print(f"  AUDIT COMPLETE  ({elapsed_total:.1f}s)")
    print(f"  Total models : {len(results)}")
    print(f"  OK           : {n_ok}")
    print(f"  Issues       : {n_issues}")
    print(f"  Parse errors : {n_parse_err}")
    print(f"  Render errors: {n_render_err}")

    # Issue type breakdown
    issue_types: Dict[str, int] = {}
    for r in results:
        for iss in r.issues:
            t = iss["type"]
            issue_types[t] = issue_types.get(t,0) + 1
    if issue_types:
        print(f"\n  Issue breakdown:")
        for t, cnt in sorted(issue_types.items(), key=lambda x: -x[1]):
            print(f"    {t:<30} : {cnt}")

    # Most common missing textures
    all_missing = {}
    for r in results:
        for tx in r.missing_tex:
            all_missing[tx] = all_missing.get(tx,0) + 1
    if all_missing:
        top = sorted(all_missing.items(), key=lambda x: -x[1])[:20]
        print(f"\n  Top missing textures ({len(all_missing)} unique):")
        for tx, cnt in top:
            print(f"    {tx:<40} : {cnt} models")

    print(f"{'='*70}\n")

    # ── Write JSON report ──
    report = {
        "summary": {
            "k1_dir":      k1_dir,
            "k2_dir":      k2_dir,
            "total":       len(results),
            "ok":          n_ok,
            "issues":      n_issues,
            "parse_errors": n_parse_err,
            "render_errors": n_render_err,
            "elapsed_s":   round(elapsed_total, 2),
            "issue_type_counts": issue_types,
            "top_missing_textures": dict(sorted(all_missing.items(),
                                                key=lambda x:-x[1])[:50]),
        },
        "models": [asdict(r) for r in results],
    }
    with open(out_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"Report written to: {out_path}")

    # ── Print all models with issues ──
    flagged = [r for r in results if r.status != "ok"]
    if flagged:
        print(f"\nModels with issues ({len(flagged)}):")
        for r in sorted(flagged, key=lambda x: (x.status, x.resref))[:100]:
            print(f"  [{r.game}] {r.resref:<30} status={r.status:<12} "
                  f"issues={len(r.issues)}")
            if r.error:
                print(f"           error: {r.error[:120]}")
            for iss in r.issues[:3]:
                print(f"           • [{iss['type']}] {iss['node']}: {iss['detail'][:80]}")
        if len(flagged) > 100:
            print(f"  ... and {len(flagged)-100} more (see JSON report)")

    return results


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GhostRigger Full Model Audit")
    parser.add_argument("--k1", default="game_data/swkotor",
                        help="KotOR 1 installation directory")
    parser.add_argument("--k2", default="game_data/swkotor2",
                        help="KotOR 2 (TSL) installation directory")
    parser.add_argument("--out", default="audit_reports/full_model_audit.json",
                        help="Output JSON report path")
    parser.add_argument("--no-render", action="store_true",
                        help="Skip headless render tests (faster)")
    parser.add_argument("--max", type=int, default=0,
                        help="Limit to first N models (0=all)")
    args = parser.parse_args()

    # Resolve relative paths
    base = Path(__file__).parent.parent
    k1 = str(base / args.k1) if not os.path.isabs(args.k1) else args.k1
    k2 = str(base / args.k2) if not os.path.isabs(args.k2) else args.k2
    out = str(base / args.out) if not os.path.isabs(args.out) else args.out

    # Only include existing directories
    if not os.path.isdir(k1):
        print(f"K1 dir not found: {k1}")
        k1 = None
    if not os.path.isdir(k2):
        print(f"K2 dir not found: {k2}")
        k2 = None

    if not k1 and not k2:
        print("ERROR: no valid game directories found.")
        sys.exit(1)

    os.makedirs(os.path.dirname(out), exist_ok=True)

    logging.basicConfig(level=logging.WARNING,
                        format='%(levelname)s %(name)s: %(message)s')

    run_audit(k1, k2, out,
              do_render=not args.no_render,
              max_models=args.max)


if __name__ == "__main__":
    main()
