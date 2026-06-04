"""
character_builder.py  –  GhostRigger Character Builder Core
=============================================================
Consolidated module for KotOR 1 & 2 character building:

  * Template loading (body + head for K1 and K2)
  * Skeleton node selection (select all / by group)
  * Apply-template-rig workflow (skeleton transfer to imported mesh)
  * Head/body assembly validation
  * Export helpers (B1 separate MDL, merged preview)

This module is the authoritative backend for the CharacterBuilderPanel UI.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, List, Optional, Tuple, Dict, Set

log = logging.getLogger(__name__)

# ── Template directory ────────────────────────────────────────────────────────
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"

# ── Template file registry ────────────────────────────────────────────────────
TEMPLATES: Dict[str, Dict[str, str]] = {
    "K1": {
        "body": str(_TEMPLATES_DIR / "gr_body_k1.mdl"),
        "head": str(_TEMPLATES_DIR / "gr_head_k1.mdl"),
        "body_manifest": str(_TEMPLATES_DIR / "gr_body_k1_manifest.json"),
        "head_manifest": str(_TEMPLATES_DIR / "gr_head_k1_manifest.json"),
    },
    "K2": {
        "body": str(_TEMPLATES_DIR / "gr_body_k2.mdl"),
        "head": str(_TEMPLATES_DIR / "gr_head_k2.mdl"),
        "body_manifest": str(_TEMPLATES_DIR / "gr_body_k2_manifest.json"),
        "head_manifest": str(_TEMPLATES_DIR / "gr_head_k2_manifest.json"),
    },
}

# ── Bone groups for selection ────────────────────────────────────────────────
BONE_GROUPS: Dict[str, List[str]] = {
    "all":        [],   # populated dynamically by select_all()
    # Real KotOR game node names (pfbcm / pfhc01 skeleton — from BIF archives)
    # Legacy hand-crafted names (build_humanoid_template) are included too,
    # so group-select works regardless of which template source was used.
    "spine":      [
        # Real game names
        "rootdummy", "pelvis_g", "torso_g", "torsoUpr_g",
        "neck_g", "necklwr_g", "head_g", "Hturn_g",
        "breastbone", "torsocam",
        # Legacy hand-crafted names
        "Mesh_Root", "Pelvis", "Spine1", "Spine2", "Spine3",
        "Chest", "Neck", "Head", "hip", "chest",
    ],
    "left_arm":   [
        # Real game names
        "LArm", "lcollar_dum", "lcollar_g", "lbicep_g", "lbicepL_g",
        "lforearm_g", "lhand_g",
        "LaFngrB_g", "LaFngrT_g",
        "LbFngrB_g", "LbFngrT_g",
        "LcFngrB_g", "LcFngrT_g",
        "LdFngrB_g", "LdFngrT_g",
        "LThumbB_g", "LThumbT_g",
        # Legacy names
        "L_Clavicle", "L_Shoulder", "L_UpperArm", "L_Elbow",
        "L_Forearm", "L_Wrist", "L_Hand",
        "L_Index1", "L_Index2", "L_Index3",
        "L_Middle1", "L_Middle2", "L_Middle3",
        "L_Ring1", "L_Ring2", "L_Ring3",
        "L_Pinky1", "L_Pinky2",
        "L_Thumb1", "L_Thumb2",
    ],
    "right_arm":  [
        # Real game names
        "RArm", "rcollar_dum", "rcollar_g", "rbicep_g", "rbicepL_g",
        "rforearm_g", "rhand",
        "RaFngrB_g", "RaFngrT_g",
        "RbFngrB_g", "RbFngrT_g",
        "RcFngrB_g", "RcFngrT_g",
        "RdFngrB_g", "RdFngrT_g",
        "RThumbB_g", "RThumbT_g",
        # Legacy names
        "R_Clavicle", "R_Shoulder", "R_UpperArm", "R_Elbow",
        "R_Forearm", "R_Wrist", "R_Hand",
        "R_Index1", "R_Index2", "R_Index3",
        "R_Middle1", "R_Middle2", "R_Middle3",
        "R_Ring1", "R_Ring2", "R_Ring3",
        "R_Pinky1", "R_Pinky2",
        "R_Thumb1", "R_Thumb2",
    ],
    "left_leg":   [
        # Real game names
        "lthigh_g", "lshin_g", "lfoot_g", "lfootT_g",
        # Legacy names
        "L_Thigh", "L_Knee", "L_Shin", "L_Ankle", "L_Foot", "L_Toe",
    ],
    "right_leg":  [
        # Real game names
        "rthigh_g", "rshin_g", "rfoot_g", "rfootT_g",
        # Legacy names
        "R_Thigh", "R_Knee", "R_Shin", "R_Ankle", "R_Foot", "R_Toe",
    ],
    "head":       [
        # Real game names (pfhc01 head skeleton)
        "neck_g", "necklwr_g", "Hturn_g", "head_g", "talkdummy",
        "f_um_g", "f_lmc_g", "f_rmc_g", "f_jaw_g",
        "f_Rlm_g", "f_Llm_g", "f_tonguetip_g",
        "teethlower", "teethupper",
        "f_mdbrw_g", "f_lbrw_g", "f_rbrw_g",
        "MaskHook", "GoggleHook",
        "eyeLlid", "eyeRlid", "eyeLA", "eyeRA",
        "hairalpha", "Object01", "Object02",
        "cutscenedummy",
        # Legacy names
        "Neck", "Head", "camerahook", "headhook",
    ],
    "attachment": [
        # Real game names — special attachment / hook nodes
        "rhand", "lhand_g",
        "camerahook", "headconjure", "handconjure", "impact_bolt",
        "Impact", "LightsaberHook", "DeflectHook", "FreeLookHook",
        "breastbone",
        # Legacy names
        "lhand", "chestconjure", "footstep", "impact_",
    ],
}


# ═══════════════════════════════════════════════════════════════════════════════
#  Template Loading
# ═══════════════════════════════════════════════════════════════════════════════

def get_template_path(game: str = "K1", part: str = "body") -> Optional[str]:
    """Return the path to a template MDL file, or None if not found."""
    gv = game.upper()
    if gv not in TEMPLATES:
        log.warning("character_builder: unknown game version '%s'", game)
        return None
    path = TEMPLATES[gv].get(part)
    if path and os.path.isfile(path):
        return path
    log.debug("character_builder: template not found: %s/%s → %s", game, part, path)
    return None


def load_template(game: str = "K1", part: str = "body") -> Optional["KotorModel"]:
    """
    Load a GhostRigger template MDL (body or head) for the given game.

    Template files are ASCII MDL files exported by MDLAsciiWriter.  They are
    loaded via MDLAsciiParser (not PyKotor's binary reader) so that all nodes,
    including duplicate-named helper nodes, are preserved faithfully.

    Returns a KotorModel ready to use as a rig source, or None on failure.
    """
    path = get_template_path(game, part)
    if not path:
        log.warning("character_builder.load_template: template not found (%s/%s)", game, part)
        return None

    try:
        # Detect whether the file is ASCII (templates are always ASCII, but be safe)
        with open(path, "rb") as _fh:
            _magic = _fh.read(4)
        is_ascii = _magic[0:1] not in (b'\x00',)

        if is_ascii:
            # Templates are ASCII MDL — use the GhostRigger ASCII parser which
            # faithfully preserves all 76 nodes (including duplicates).
            try:
                from core.mdl.mdl_parser import MDLAsciiParser  # type: ignore
            except ImportError:
                from src.core.mdl.mdl_parser import MDLAsciiParser  # type: ignore

            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
            model = MDLAsciiParser().parse(lines)
        else:
            try:
                from core.game.kotor_loader import load_model_from_file  # type: ignore
            except ImportError:
                from src.core.game.kotor_loader import load_model_from_file  # type: ignore
            model = load_model_from_file(path)

        if model is None:
            log.error("character_builder.load_template: parser returned None for %s", path)
            return None
        log.info(
            "character_builder.load_template: loaded '%s' (%s/%s)  nodes=%d  anims=%d",
            model.name, game, part,
            model.node_count(),
            len(model.animations),
        )
        return model
    except Exception as exc:
        log.error("character_builder.load_template: failed to load '%s': %s", path, exc)
        return None


def _detect_game_dir(game: str) -> Optional[str]:
    """Return the configured KOTOR install path for *game*, if available."""
    try:
        try:
            from resources.game_detector import detect_kotor_dirs  # type: ignore
        except ImportError:
            from src.resources.game_detector import detect_kotor_dirs  # type: ignore
        k1_dir, k2_dir = detect_kotor_dirs(prefer_config=True)
        return k2_dir if str(game).upper().endswith("2") else k1_dir
    except Exception as exc:
        log.debug("character_builder._detect_game_dir failed: %s", exc)
        return None


def load_game_skeleton_source(
    resref: str,
    *,
    game: str = "K1",
    game_dir: Optional[str] = None,
) -> Optional["KotorModel"]:
    """Load a real KOTOR MDL/MDX by resref for use as a rig reference.

    This is the preferred source for Character Builder skeleton fitting.  It
    keeps the modder's chosen base body/supermodel tied to the actual installed
    game files instead of the older generated ``templates/gr_*`` MDLs.
    """
    name = str(resref or "").strip().lower()
    if not name:
        return None

    try:
        try:
            from core.game.kotor_install import KotorInstallation  # type: ignore
            from core.game.kotor_loader import load_model_from_bytes  # type: ignore
            from core.geometry.model_data import GameVersion  # type: ignore
        except ImportError:
            from src.core.game.kotor_install import KotorInstallation  # type: ignore
            from src.core.game.kotor_loader import load_model_from_bytes  # type: ignore
            from src.core.geometry.model_data import GameVersion  # type: ignore
    except Exception as exc:
        log.error("load_game_skeleton_source: import error: %s", exc)
        return None

    root = game_dir or _detect_game_dir(game)
    if not root:
        log.warning("load_game_skeleton_source: no KOTOR %s install configured", game)
        return None

    try:
        inst = KotorInstallation(root)
        mdl_bytes = inst.get_mdl(name)
        mdx_bytes = inst.get_mdx(name) or b""
        if not mdl_bytes:
            log.warning("load_game_skeleton_source: %s not found in %s", name, root)
            return None
        gv = GameVersion.K2 if str(game).upper().endswith("2") else GameVersion.K1
        model = load_model_from_bytes(mdl_bytes, mdx_bytes, game_version=gv)
        if model is not None:
            model.name = getattr(model, "name", None) or name
            setattr(model, "_gr_source_resref", name)
            setattr(model, "_gr_source_game", "K2" if gv == GameVersion.K2 else "K1")
            setattr(model, "_gr_source_layer", "game_library")
        return model
    except Exception as exc:
        log.error("load_game_skeleton_source: failed for %s/%s: %s", game, name, exc)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  v7.1 Head Attachment (Finding 3.3 — KotorBlender armature.py cross-ref)
# ═══════════════════════════════════════════════════════════════════════════════

# KotOR body models contain a "headhook" dummy node that specifies where the
# head model should be attached.  The head model's root position is snapped to
# the headhook's world transform to achieve correct positioning.
#
# Node name variants (from KotorBlender + KotOR.js + vanilla model analysis):
#   "headhook"      — standard PC/NPC body models
#   "cutscenehead"  — some cutscene body variants
#   "head_g"        — some creature models use this as head attachment
#
# Cross-ref: KotorBlender armature.py — headhook node for head snapping
# Cross-ref: KotOR.js OdysseyModel3D.ts — headhook lookup for attachment

HEADHOOK_NODE_NAMES = ('headhook', 'cutscenehead', 'head_g')


def find_headhook(body_model) -> Optional[Tuple[Tuple[float,float,float],
                                                  Tuple[float,float,float,float]]]:
    """Find the headhook attachment point in a body model.

    Searches the body model's node tree for nodes named "headhook",
    "cutscenehead", or "head_g" and returns their world transform.

    Parameters
    ----------
    body_model : KotorModel
        The body model to search.

    Returns
    -------
    (world_position, world_orientation) or None if no headhook found.
        world_position: (x, y, z) tuple
        world_orientation: (qx, qy, qz, qw) quaternion tuple
    """
    if body_model is None:
        return None
    try:
        for node in body_model.all_nodes():
            name_lower = node.name.lower().strip()
            if name_lower in HEADHOOK_NODE_NAMES:
                try:
                    wp, wo = node.world_transform()
                    log.debug(f"find_headhook: found '{node.name}' at pos=({wp[0]:.3f}, "
                              f"{wp[1]:.3f}, {wp[2]:.3f})")
                    return (wp, wo)
                except Exception as e:
                    log.debug(f"find_headhook: world_transform failed for '{node.name}': {e}")
                    return (node.position, node.rotation)
    except Exception as e:
        log.debug(f"find_headhook: search failed: {e}")
    return None


def validate_facial_bones(head_model) -> List[str]:
    """Validate that a head model contains the required facial bones.

    v7.1 (Finding 3.4 — KotorBlender armature.py bone naming conventions):
    Checks for the presence of required facial bones/hooks used by the
    KotOR engine for lip-sync animation and accessory attachment.

    Returns a list of warning strings for missing bones.
    """
    if head_model is None:
        return ["No head model provided"]

    # Required facial bones (from KotOR vanilla head models):
    #   head_g, necklwr_g, neck_g — base orientation
    #   f_jaw_g — jaw open/close (lip sync)
    #   f_um_g — upper mouth
    #   f_Llm_g, f_Rlm_g — left/right lower mouth
    #   MaskHook, GoggleHook — accessory attachment (optional but recommended)
    _REQUIRED_BONES = {
        'head_g':    'Head bone (base orientation)',
        'f_jaw_g':   'Jaw bone (lip sync open/close)',
        'f_um_g':    'Upper mouth (lip sync)',
    }
    _RECOMMENDED_BONES = {
        'necklwr_g': 'Lower neck bone',
        'neck_g':    'Neck bone',
        'f_llm_g':   'Left lower mouth',
        'f_rlm_g':   'Right lower mouth',
        'maskhook':  'Mask attachment hook',
        'gogglehook': 'Goggle attachment hook',
    }

    existing_names = set()
    try:
        for node in head_model.all_nodes():
            existing_names.add(node.name.lower().strip())
    except Exception:
        return ["Failed to enumerate head model nodes"]

    warnings = []
    for bone_name, description in _REQUIRED_BONES.items():
        if bone_name.lower() not in existing_names:
            warnings.append(f"MISSING required bone: '{bone_name}' ({description})")

    for bone_name, description in _RECOMMENDED_BONES.items():
        if bone_name.lower() not in existing_names:
            warnings.append(f"MISSING recommended bone: '{bone_name}' ({description})")

    return warnings


class LIPPlayback:
    """LIP sync playback engine for character builder facial preview.

    v7.2 (Finding 3.2 — KotOR.js LIPObject.ts lines 146-277 cross-ref):
    Implements the KotOR engine's lip-sync algorithm that drives facial
    bone animations from LIP keyframe data.

    Algorithm (matching KotOR.js LIPObject.ts):
    1. Load the model's 'talk' animation (from odysseyAnimationMap)
    2. For each animation node, index Position/Orientation controllers
       by the LIP shape index (0-15)
    3. Interpolate between keyframe shapes using:
       - lerp for position controllers
       - slerp for orientation controllers
    4. Interpolation factor = (elapsed - last.time) / (next.time - last.time)

    Reference: KotOR.js LIPObject.ts lines 146-277; PyKotor lip_data.py.
    """

    def __init__(self):
        self._lip_data = None      # LIPFile instance
        self._talk_anim = None     # Animation named 'talk' from head model
        self._elapsed = 0.0        # current playback time
        self._playing = False

    def load_lip(self, lip_file) -> bool:
        """Load a LIP file for playback.

        Parameters
        ----------
        lip_file : LIPFile
            A parsed LIP file (from lip_reader.py).

        Returns
        -------
        bool : True if loaded successfully.
        """
        if lip_file is None:
            return False
        self._lip_data = lip_file
        self._elapsed = 0.0
        return True

    def load_talk_animation(self, head_model) -> bool:
        """Find and cache the 'talk' animation from a head model.

        KotOR engine convention: the 'talk' animation contains per-shape
        bone poses for each of the 16 LIP visemes. The animation nodes
        carry Position and Orientation controllers indexed by shape.

        Parameters
        ----------
        head_model : KotorModel
            A loaded head model with animations.

        Returns
        -------
        bool : True if the 'talk' animation was found.
        """
        if head_model is None:
            return False
        anims = getattr(head_model, 'animations', [])
        for anim in anims:
            name = getattr(anim, 'name', '').lower()
            if name == 'talk' or name.endswith('_talk'):
                self._talk_anim = anim
                log.debug(f"LIPPlayback: found talk animation '{anim.name}'")
                return True
        log.debug("LIPPlayback: no 'talk' animation found in head model")
        return False

    def update(self, dt: float) -> Optional[dict]:
        """Advance playback by dt seconds and return current bone poses.

        Returns
        -------
        dict[str, dict] or None
            Mapping of bone_name → {'position': (x,y,z), 'rotation': (x,y,z,w)}
            for all facial bones affected by the current LIP shape.
            Returns None if playback is not active.
        """
        if not self._playing or self._lip_data is None:
            return None

        self._elapsed += dt

        # Check if we've passed the end of the LIP data
        sound_length = getattr(self._lip_data, 'sound_length', 0.0)
        if sound_length > 0 and self._elapsed > sound_length:
            self._playing = False
            self._elapsed = 0.0
            return None

        # Get interpolated shape values at current time
        # KotOR.js LIPObject.ts line 195: get the current and next keyframes
        shape_data = self._lip_data.get_shape_at_time(self._elapsed)
        if shape_data is None:
            return {}

        # shape_data contains (shape_index, interpolation_factor)
        # or just the shape index depending on lip_reader implementation
        current_shape = shape_data if isinstance(shape_data, int) else int(shape_data)

        # Build bone pose from talk animation controller data
        # KotOR.js algorithm: for each animation node, use shape index
        # to select Position/Orientation keyframe values
        if self._talk_anim is None:
            return {}

        poses = {}
        nodes = getattr(self._talk_anim, 'nodes', {})
        for bone_name, node_data in nodes.items():
            pose = {}
            # Position controller: indexed by shape index
            pos_vals = getattr(node_data, 'position_values', None)
            if pos_vals and current_shape < len(pos_vals):
                pose['position'] = tuple(pos_vals[current_shape][:3])

            # Rotation controller: indexed by shape index
            rot_vals = getattr(node_data, 'rotation_values', None)
            if rot_vals and current_shape < len(rot_vals):
                pose['rotation'] = tuple(rot_vals[current_shape][:4])

            if pose:
                poses[bone_name.lower()] = pose

        return poses

    def play(self):
        """Start playback from the beginning."""
        self._elapsed = 0.0
        self._playing = True

    def stop(self):
        """Stop playback and reset."""
        self._playing = False
        self._elapsed = 0.0

    def pause(self):
        """Pause playback at current position."""
        self._playing = False

    def resume(self):
        """Resume from current position."""
        self._playing = True

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def elapsed(self) -> float:
        return self._elapsed

    @property
    def duration(self) -> float:
        if self._lip_data is None:
            return 0.0
        return getattr(self._lip_data, 'sound_length', 0.0)


def rebuild_templates(out_dir: Optional[str] = None) -> List[str]:
    """
    Regenerate all template MDL files from real KotOR game data.

    Loads actual binary MDL/MDX files from the game BIF archives,
    strips all geometry to produce skeleton-only (all-dummy) templates,
    and saves them as ASCII MDL.

    Source models used:
      K1 body → pfbcm  (Female Commoner Medium, super=S_Female03)
      K1 head → pfhc01 (Female Human Head 01,   super=S_Female03)
      K2 body → pfbcm  (K2 version,              super=S_Female03)
      K2 head → pfhc01 (K2 version,              super=S_Female03)

    Parameters
    ----------
    out_dir : directory to write templates; defaults to the templates/ folder.

    Returns list of created file paths.
    """
    import json
    try:
        try:
            from core.game.kotor_install import KotorInstallation  # type: ignore
            from core.game.kotor_loader import load_model_from_bytes  # type: ignore
            from core.mdl.mdl_parser import MDLAsciiWriter  # type: ignore
            from core.geometry.model_data import NodeFlags  # type: ignore
        except ImportError:
            from src.core.game.kotor_install import KotorInstallation  # type: ignore
            from src.core.game.kotor_loader import load_model_from_bytes  # type: ignore
            from src.core.mdl.mdl_parser import MDLAsciiWriter  # type: ignore
            from src.core.geometry.model_data import NodeFlags  # type: ignore
    except Exception as exc:
        log.error("character_builder.rebuild_templates: import error: %s", exc)
        return []

    _repo = Path(__file__).parent.parent.parent
    k1_dir = str(_repo / "game_data" / "k1_extracted")
    k2_dir = str(_repo / "game_data" / "k2_extracted")
    out = Path(out_dir) if out_dir else _TEMPLATES_DIR
    out.mkdir(parents=True, exist_ok=True)

    def _strip(node):
        """Convert all non-dummy nodes to pure dummy skeleton nodes."""
        DUMMY = int(NodeFlags.HEADER)
        if node.type_label not in ("dummy", "reference"):
            node.vertices = []; node.faces = []; node.normals = []; node.uvs = []
            for attr in ("skin_weights", "bone_indices", "bone_weights",
                         "constraint_weights", "dangly_constraints"):
                if hasattr(node, attr):
                    setattr(node, attr, [])
            node.texture = ""; node.bitmap = ""; node.flags = DUMMY
        for c in node.children:
            _strip(c)

    _SOURCES = [
        ("pfbcm",  "gr_body_k1", "K1", k1_dir, "body"),
        ("pfhc01", "gr_head_k1", "K1", k1_dir, "head"),
        ("pfbcm",  "gr_body_k2", "K2", k2_dir, "body"),
        ("pfhc01", "gr_head_k2", "K2", k2_dir, "head"),
    ]

    created: List[str] = []
    for src_resref, out_name, game, game_dir, part in _SOURCES:
        try:
            inst = KotorInstallation(game_dir)
            mdl_bytes = inst.get_mdl(src_resref)
            mdx_bytes = inst.get_mdx(src_resref) or b""
            if not mdl_bytes:
                log.error("rebuild_templates: %s not found in %s", src_resref, game_dir)
                continue
            model = load_model_from_bytes(mdl_bytes, mdx_bytes)
            log.info("rebuild_templates: loaded %s (%d nodes, super=%s)",
                     src_resref, model.node_count(), model.supermodel)
            _strip(model.root_node)
            model.root_node.name = out_name
            model.name = out_name
            model.animations = []
            if hasattr(model, "compute_bounds"):
                model.compute_bounds()
            mdl_path = str(out / f"{out_name}.mdl")
            MDLAsciiWriter().write(model, mdl_path)
            # Write companion manifest
            node_info = []
            stack = [(model.root_node, None)]
            while stack:
                n, par = stack.pop()
                node_info.append({"name": n.name, "type": n.type_label,
                                  "parent": par.name if par else "NULL"})
                for c in reversed(n.children):
                    stack.append((c, n))
            manifest = {
                "name": out_name, "source_model": src_resref.upper(),
                "game_version": game, "part": part,
                "supermodel": model.supermodel,
                "node_count": model.node_count(), "nodes": node_info,
                "note": ("Skeleton-only template derived from real KotOR game data. "
                         "All geometry stripped; dummy nodes only."),
            }
            json_path = str(out / f"{out_name}_manifest.json")
            with open(json_path, "w") as fh:
                import json as _json
                _json.dump(manifest, fh, indent=2)
            created.append(mdl_path)
            log.info("rebuild_templates: wrote %s (%d nodes)", mdl_path, model.node_count())
        except Exception as exc:
            log.error("rebuild_templates: failed for %s/%s: %s", game, part, exc)

    return created


# ═══════════════════════════════════════════════════════════════════════════════
#  Skeleton Node Selection
# ═══════════════════════════════════════════════════════════════════════════════

class SkeletonSelector:
    """
    Manages multi-node selection on a KotorModel skeleton.

    Provides:
      - select_all()           – select every node in the model
      - select_group(name)     – select a named bone group (spine, left_arm, …)
      - select_by_names(names) – select specific nodes by name
      - clear()                – deselect all
      - selected_nodes         – list of currently selected ModelNode objects
    """

    def __init__(self, model=None):
        self._model = model
        self._selected: Set[str] = set()   # node names
        self._node_map: Dict[str, object] = {}  # name → ModelNode
        if model is not None:
            self._build_node_map()

    def set_model(self, model) -> None:
        self._model = model
        self._selected.clear()
        self._node_map.clear()
        if model is not None:
            self._build_node_map()

    def _build_node_map(self) -> None:
        try:
            for node in self._model.all_nodes():
                self._node_map[node.name] = node
        except Exception as exc:
            log.debug("SkeletonSelector._build_node_map: %s", exc)

    # ── Selection operations ─────────────────────────────────────────────────

    def select_all(self) -> List[str]:
        """Select every node in the model. Returns list of selected names."""
        self._selected = set(self._node_map.keys())
        log.debug("SkeletonSelector.select_all: %d nodes", len(self._selected))
        return list(self._selected)

    def select_skeleton_only(self) -> List[str]:
        """Select only skeleton (non-mesh) nodes."""
        try:
            try:
                from core.geometry.model_data import NodeFlags  # type: ignore
            except ImportError:
                from src.core.geometry.model_data import NodeFlags  # type: ignore
            MESH_FLAG = int(NodeFlags.MESH)
            SKIN_FLAG = int(NodeFlags.SKIN)
        except Exception:
            MESH_FLAG = SKIN_FLAG = 0

        selected = []
        for name, node in self._node_map.items():
            flags = getattr(node, "flags", 0) or 0
            is_mesh = bool(flags & MESH_FLAG) if MESH_FLAG else getattr(node, "is_mesh", False)
            is_skin = bool(flags & SKIN_FLAG) if SKIN_FLAG else getattr(node, "is_skin", False)
            if not (is_mesh or is_skin):
                self._selected.add(name)
                selected.append(name)
        return selected

    def select_group(self, group_name: str) -> List[str]:
        """
        Select a named bone group. group_name must be a key in BONE_GROUPS.
        Returns list of selected names (only those present in the model).
        """
        names = BONE_GROUPS.get(group_name, [])
        if group_name == "all":
            return self.select_all()
        added = []
        for name in names:
            if name in self._node_map:
                self._selected.add(name)
                added.append(name)
        log.debug("SkeletonSelector.select_group('%s'): %d nodes selected",
                  group_name, len(added))
        return added

    def select_by_names(self, names: List[str]) -> List[str]:
        """Select specific nodes by name. Returns names that were found."""
        found = []
        for name in names:
            if name in self._node_map:
                self._selected.add(name)
                found.append(name)
        return found

    def deselect(self, names: Optional[List[str]] = None) -> None:
        """Deselect given names, or all if names is None."""
        if names is None:
            self._selected.clear()
        else:
            for name in names:
                self._selected.discard(name)

    def clear(self) -> None:
        """Clear all selections."""
        self._selected.clear()

    def toggle(self, name: str) -> bool:
        """Toggle selection for a single node. Returns True if now selected."""
        if name in self._selected:
            self._selected.discard(name)
            return False
        self._selected.add(name)
        return True

    @property
    def selected_nodes(self) -> list:
        """Return list of selected ModelNode objects."""
        result = []
        for name in self._selected:
            node = self._node_map.get(name)
            if node is not None:
                result.append(node)
        return result

    @property
    def selected_names(self) -> List[str]:
        return list(self._selected)

    @property
    def count(self) -> int:
        return len(self._selected)

    def is_selected(self, name: str) -> bool:
        return name in self._selected

    def available_groups(self) -> List[str]:
        """Return list of group names that have at least one node in the model."""
        result = []
        for group, names in BONE_GROUPS.items():
            if group == "all":
                result.append("all")
                continue
            if any(n in self._node_map for n in names):
                result.append(group)
        return result


# ═══════════════════════════════════════════════════════════════════════════════
#  Apply-Template-Rig workflow
# ═══════════════════════════════════════════════════════════════════════════════

def apply_template_rig(
    mesh_model,
    template_model,
    game: str = "K1",
    scale_mode: str = "auto",
    scale_factor: float = 1.0,
) -> dict:
    """
    Transfer the template skeleton onto an imported mesh model.

    Existing imported armatures are intentionally removed.  Only visible mesh
    payload nodes are copied from ``mesh_model``; their current displayed
    transforms are baked into vertex positions, previous skin/bone influence
    tables are cleared, and the cleaned mesh nodes are parented under the chosen
    KOTOR skeleton.  The imported meshes are then converted to KOTOR skin nodes
    with bone-map, QBones/TBones, and per-vertex influence rows.

    Parameters
    ----------
    mesh_model      : KotorModel of the imported OBJ/FBX mesh (no rig)
    template_model  : KotorModel from load_template()
    game            : 'K1' or 'K2'
    scale_mode      : compatibility input only. Imported meshes should already
                      be auto-fitted before binding; the selected KOTOR
                      skeleton is never scaled here.
    scale_factor    : compatibility input only when scale_mode == 'manual'

    Returns
    -------
    dict with keys:
      'ok'       : bool
      'model'    : resulting KotorModel (mesh with template skeleton)
      'message'  : human-readable description
      'warnings' : list of strings
      'scale'    : applied scale factor
    """
    if mesh_model is None:
        return {"ok": False, "model": None, "message": "No mesh model provided",
                "warnings": [], "scale": 1.0}
    if template_model is None:
        return {"ok": False, "model": None, "message": "No template model provided",
                "warnings": [], "scale": 1.0}

    warnings: List[str] = []

    # Compute the caller's requested scale for diagnostics only. The selected
    # native KOTOR skeleton remains the final DAG authority and is not scaled
    # in this binding step.
    requested_scale = 1.0
    applied_scale = 1.0
    if scale_mode == "auto":
        try:
            mesh_h = _model_height(mesh_model)
            tmpl_h = _model_height(template_model)
            if tmpl_h > 0.01:
                requested_scale = mesh_h / tmpl_h
        except Exception as exc:
            warnings.append(f"Auto-scale failed: {exc}")
    elif scale_mode == "manual":
        requested_scale = max(0.01, float(scale_factor))
    else:
        warnings.append(f"Unknown scale mode '{scale_mode}'; using native template scale.")
    if abs(requested_scale - 1.0) > 0.001:
        warnings.append(
            "Requested skeleton scale "
            f"{requested_scale:.3f} was ignored; re-fit the imported mesh "
            "to the selected KOTOR base before binding."
        )

    # Clone mesh model
    try:
        import copy
        result_model = copy.deepcopy(mesh_model)
    except Exception as exc:
        return {"ok": False, "model": None,
                "message": f"Failed to clone mesh model: {exc}",
                "warnings": warnings, "scale": applied_scale}

    # Transfer skeleton from template: use the selected KOTOR hierarchy as the
    # only skeleton, then attach cleaned mesh payload nodes under that root.
    try:
        tmpl_root = template_model.root_node
        if tmpl_root is None:
            return {"ok": False, "model": None,
                    "message": "Template has no root node",
                    "warnings": warnings, "scale": applied_scale}

        native_skeleton_snapshot = None
        try:
            try:
                from .native_skeleton import capture_native_skeleton_snapshot
            except ImportError:  # pragma: no cover
                from src.core.characters.native_skeleton import capture_native_skeleton_snapshot  # type: ignore
            native_skeleton_snapshot = capture_native_skeleton_snapshot(
                template_model,
                game=game,
            )
        except Exception as exc:
            log.debug("apply_template_rig native snapshot failed: %s", exc, exc_info=True)
            warnings.append(f"Native skeleton snapshot failed: {exc}")

        import copy
        skel_root = copy.deepcopy(tmpl_root)

        removed_template_meshes = _strip_render_geometry_from_skeleton(skel_root)
        mesh_payloads = _extract_clean_mesh_payloads(mesh_model)
        if not mesh_payloads:
            return {"ok": False, "model": None,
                    "message": "Imported model has no renderable mesh payload to rig.",
                    "warnings": warnings, "scale": applied_scale}

        # Preserve the selected native base model's animation inheritance.  A
        # generated character should not silently switch to a generic humanoid
        # supermodel because PMBAM/PFBAM-style bodies inherit from specific
        # game supermodels such as S_KPMF0200.
        sm = str(getattr(template_model, "supermodel", "") or "").strip()
        result_model.supermodel = sm or "NULL"

        # Attach cleaned mesh payloads under the template skeleton root.
        for mesh_node in mesh_payloads:
            mesh_node.parent = skel_root
            skel_root.children.append(mesh_node)

        original_nodes = len(mesh_model.all_nodes()) if hasattr(mesh_model, "all_nodes") else 0
        removed_import_nodes = max(0, original_nodes - len(mesh_payloads))
        if removed_import_nodes:
            warnings.append(
                f"Removed {removed_import_nodes} imported armature/helper node(s)."
            )
        if removed_template_meshes:
            warnings.append(
                f"Removed {removed_template_meshes} reference mesh node(s) from the base skeleton."
            )

        result_model.root_node = skel_root
        result_model.animations = list(template_model.animations)
        if native_skeleton_snapshot is not None:
            setattr(result_model, "_gr_native_skeleton_snapshot", native_skeleton_snapshot)

        try:
            try:
                from ..skeleton.skeleton_builder import bind_imported_meshes_to_skeleton
            except ImportError:  # pragma: no cover
                from skeleton_builder import bind_imported_meshes_to_skeleton  # type: ignore
            bind_report = bind_imported_meshes_to_skeleton(
                result_model,
                mesh_nodes=mesh_payloads,
            )
            if not bind_report.ok:
                return {"ok": False, "model": None,
                        "message": bind_report.message or "Skeleton skin binding failed.",
                        "warnings": warnings + list(bind_report.warnings or []),
                        "scale": applied_scale}
            warnings.extend(bind_report.warnings or [])
            for mesh_node in mesh_payloads:
                setattr(mesh_node, "_gr_bound_to_kotor_skeleton", True)
                setattr(mesh_node, "_gr_kotor_skeleton_root", str(getattr(skel_root, "name", "") or ""))
                setattr(mesh_node, "_gr_kotor_bone_map_source", "character_builder_template_rig")
            metadata = getattr(result_model, "metadata", None)
            if not isinstance(metadata, dict):
                metadata = {}
                setattr(result_model, "metadata", metadata)
            native_metadata = (
                dict(getattr(native_skeleton_snapshot, "metadata", {}) or {})
                if native_skeleton_snapshot is not None else
                {}
            )
            native_base_resref = str(
                native_metadata.get("source_resref")
                or getattr(template_model, "_gr_source_resref", "")
                or getattr(template_model, "name", "")
                or ""
            )
            native_base_game = str(
                native_metadata.get("source_game")
                or getattr(template_model, "_gr_source_game", "")
                or game
                or ""
            )
            native_base_model_name = str(
                getattr(native_skeleton_snapshot, "model_name", "")
                if native_skeleton_snapshot is not None else
                getattr(template_model, "name", "")
            )
            imported_payload_name = str(getattr(mesh_model, "name", "") or "")
            payload_mesh_names = tuple(
                str(getattr(mesh_node, "name", "") or "")
                for mesh_node in mesh_payloads
            )
            metadata["character_builder_bind"] = {
                "status": "bound_to_native_kotor_skeleton",
                "skeleton_root": str(getattr(skel_root, "name", "") or ""),
                "native_base": {
                    "source_resref": native_base_resref,
                    "model_name": native_base_model_name,
                    "game": native_base_game,
                    "supermodel": sm or "NULL",
                    "dag_authority": "native_kotor_base",
                },
                "imported_payload": {
                    "model_name": imported_payload_name,
                    "mesh_role": "payload_guest",
                    "mesh_names": list(payload_mesh_names),
                    "removed_import_armature_or_helper_nodes": removed_import_nodes,
                },
                "mesh_count": len(mesh_payloads),
                "skinned_meshes": bind_report.skinned_meshes,
                "weighted_vertices": bind_report.weighted_vertices,
                "bone_slots": bind_report.bone_count,
                "source": "apply_template_rig",
                "skeleton_scale_applied": applied_scale,
                "requested_skeleton_scale": requested_scale,
            }
            try:
                from .character_rig_state import mark_native_template_final_rig
            except ImportError:  # pragma: no cover
                from src.core.characters.character_rig_state import mark_native_template_final_rig  # type: ignore
            mark_native_template_final_rig(
                result_model,
                source="apply_template_rig",
                native_snapshot_present=native_skeleton_snapshot is not None,
                native_base_resref=native_base_resref,
                native_base_model_name=native_base_model_name,
                native_base_game=native_base_game,
                imported_payload_name=imported_payload_name,
                payload_mesh_names=payload_mesh_names,
            )
            setattr(result_model, "_gr_character_builder_bind_complete", True)
        except Exception as exc:
            log.error("apply_template_rig skin bind failed: %s", exc, exc_info=True)
            return {"ok": False, "model": None,
                    "message": f"Skeleton skin binding failed: {exc}",
                    "warnings": warnings, "scale": applied_scale}

        log.info(
            "apply_template_rig: success  game=%s  scale=%.3f  "
            "skel_bones=%d  skinned=%d  weighted=%d  anims=%d",
            game, applied_scale,
            template_model.node_count(),
            bind_report.skinned_meshes,
            bind_report.weighted_vertices,
            len(result_model.animations),
        )
        return {
            "ok": True,
            "model": result_model,
            "message": (
                f"KOTOR skeleton built ({game}).  "
                f"Scale: {applied_scale:.3f}.  "
                f"Meshes: {len(mesh_payloads)}.  "
                f"Skinned: {bind_report.skinned_meshes}.  "
                f"Bone slots: {bind_report.bone_count}.  "
                f"Anims: {len(result_model.animations)}"
            ),
            "warnings": warnings,
            "scale": applied_scale,
            "requested_scale": requested_scale,
            "meshes": len(mesh_payloads),
            "skinned_meshes": bind_report.skinned_meshes,
            "weighted_vertices": bind_report.weighted_vertices,
            "bone_slots": bind_report.bone_count,
            "removed_import_nodes": removed_import_nodes,
            "native_skeleton_snapshot": native_skeleton_snapshot,
        }
    except Exception as exc:
        log.error("apply_template_rig: %s", exc, exc_info=True)
        return {
            "ok": False,
            "model": None,
            "message": f"apply_template_rig failed: {exc}",
            "warnings": warnings,
            "scale": applied_scale,
        }


def _quat_rotate_vec(q, v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """Rotate vector ``v`` by xyzw quaternion ``q``."""
    try:
        x, y, z, w = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
        vx, vy, vz = (float(v[0]), float(v[1]), float(v[2]))
    except Exception:
        return v
    # q * v * q^-1, expanded to avoid adding a numpy dependency here.
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


def _normalize_vec(v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    try:
        x, y, z = float(v[0]), float(v[1]), float(v[2])
    except Exception:
        return v
    mag = (x * x + y * y + z * z) ** 0.5
    if mag <= 1e-9:
        return (x, y, z)
    return (x / mag, y / mag, z / mag)


def _is_mesh_payload_node(node: Any) -> bool:
    if node is None:
        return False
    return bool(
        getattr(node, "is_mesh", False)
        or getattr(node, "is_skin", False)
        or (getattr(node, "vertices", None) and getattr(node, "faces", None))
    )


def _strip_render_geometry_from_skeleton(node: Any) -> int:
    """Remove visible reference meshes from a copied template skeleton tree.

    KotOR character rigs are unusual: many deformation joints are stored as
    tiny trimesh helper nodes (``pelvis_g``, ``Rhand_g``) with children below
    them.  Deleting every mesh node destroys the actual skeleton and loses
    hooks such as ``rhand``/``headhook``.  Keep helper-style mesh nodes as
    empty dummies and only drop leaf render payloads such as ``Torso``/``LArm``.
    """
    if node is None:
        return 0
    removed = 0
    kept = []
    for child in list(getattr(node, "children", []) or []):
        if _is_mesh_payload_node(child):
            if _is_template_skeleton_helper(child):
                _clear_template_render_payload(child)
            else:
                removed += 1
                continue
        removed += _strip_render_geometry_from_skeleton(child)
        child.parent = node
        kept.append(child)
    node.children = kept
    return removed


def _is_template_skeleton_helper(node: Any) -> bool:
    """Return True for KotOR deformation-helper mesh nodes to preserve."""
    name = str(getattr(node, "name", "") or "").strip().lower()
    if name.endswith(("_g", "_dum")):
        return True
    if name in {"rootdummy", "cutscenedummy", "talkdummy"}:
        return True
    # Any mesh node that parents other nodes is part of the transform chain.
    return bool(getattr(node, "children", None))


def _clear_template_render_payload(node: Any) -> None:
    """Turn a reference mesh/helper into an empty transform node."""
    try:
        from core.geometry.model_data import NodeFlags  # type: ignore
    except ImportError:                         # pragma: no cover
        from src.core.geometry.model_data import NodeFlags  # type: ignore

    for attr in (
        "vertices", "normals", "tangents", "uvs", "uvs_lm", "uvs_2", "uvs_3",
        "faces", "face_mats", "face_uvs", "skin_data", "bone_map",
        "bone_map_floats", "qbone_list", "tbone_list", "dangly_constraints",
    ):
        try:
            setattr(node, attr, [])
        except Exception:
            pass
    try:
        flags = int(getattr(node, "flags", 0))
        strip = (
            int(NodeFlags.MESH)
            | int(NodeFlags.SKIN)
            | int(NodeFlags.DANGLY)
            | int(NodeFlags.AABB)
            | int(NodeFlags.SABER)
        )
        node.flags = int((flags | int(NodeFlags.HEADER)) & ~strip)
    except Exception:
        pass
    node.render = False


def _clean_mesh_payload_node(node: Any) -> Any:
    import copy
    try:
        from core.geometry.model_data import NodeFlags  # type: ignore
    except ImportError:                         # pragma: no cover
        from src.core.geometry.model_data import NodeFlags  # type: ignore

    cleaned = copy.deepcopy(node)
    vertices_are_world = bool(getattr(node, "_gr_vertices_in_kotor_world", False))
    if vertices_are_world:
        world_pos = (0.0, 0.0, 0.0)
        world_rot = (0.0, 0.0, 0.0, 1.0)
    else:
        try:
            world_pos, world_rot = node.world_transform()
        except Exception:
            world_pos = tuple(getattr(node, "position", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0))
            world_rot = tuple(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0)) or (0.0, 0.0, 0.0, 1.0))

    baked_vertices = []
    for vert in list(getattr(node, "vertices", []) or []):
        try:
            if vertices_are_world:
                baked_vertices.append((float(vert[0]), float(vert[1]), float(vert[2])))
            else:
                rx, ry, rz = _quat_rotate_vec(world_rot, (float(vert[0]), float(vert[1]), float(vert[2])))
                baked_vertices.append((
                    rx + float(world_pos[0]),
                    ry + float(world_pos[1]),
                    rz + float(world_pos[2]),
                ))
        except Exception:
            baked_vertices.append(vert)
    if baked_vertices:
        cleaned.vertices = baked_vertices

    baked_normals = []
    for normal in list(getattr(node, "normals", []) or []):
        try:
            if vertices_are_world:
                baked_normals.append(_normalize_vec(normal))
            else:
                baked_normals.append(_normalize_vec(_quat_rotate_vec(world_rot, normal)))
        except Exception:
            baked_normals.append(normal)
    if baked_normals:
        cleaned.normals = baked_normals

    cleaned.parent = None
    cleaned.children = []
    cleaned.position = (0.0, 0.0, 0.0)
    cleaned.rotation = (0.0, 0.0, 0.0, 1.0)
    cleaned.flags = int((int(getattr(cleaned, "flags", 0)) | int(NodeFlags.MESH)) & ~int(NodeFlags.SKIN))
    cleaned.render = True
    cleaned.skin_data = []
    cleaned.bone_map = []
    cleaned.bone_map_floats = []
    cleaned.qbone_list = []
    cleaned.tbone_list = []
    setattr(cleaned, "_external_imported", True)
    if vertices_are_world:
        setattr(cleaned, "_gr_vertices_in_kotor_world", True)
    try:
        cleaned.compute_bounds()
    except Exception:
        pass
    return cleaned


def _extract_clean_mesh_payloads(mesh_model: Any) -> List[Any]:
    payloads: List[Any] = []
    nodes = mesh_model.all_nodes() if hasattr(mesh_model, "all_nodes") else []
    for node in nodes:
        if node is getattr(mesh_model, "root_node", None):
            continue
        if not _is_mesh_payload_node(node):
            continue
        if not getattr(node, "vertices", None):
            continue
        payloads.append(_clean_mesh_payload_node(node))
    return payloads


def _model_height(model) -> float:
    """Estimate the height of a model from its bounding box."""
    try:
        bb_min = model.bb_min
        bb_max = model.bb_max
        if bb_min and bb_max:
            return abs(bb_max[2] - bb_min[2])
    except Exception:
        pass
    try:
        zvals = []
        for node in model.all_nodes():
            pos = getattr(node, "position", None)
            if pos:
                zvals.append(pos[2])
        if len(zvals) >= 2:
            return max(zvals) - min(zvals)
    except Exception:
        pass
    return 1.8  # default humanoid height


def _scale_skeleton(node, scale: float) -> None:
    """Recursively scale all bone positions in a skeleton tree."""
    pos = getattr(node, "position", None)
    if pos:
        node.position = (pos[0] * scale, pos[1] * scale, pos[2] * scale)
    for child in (getattr(node, "children", []) or []):
        _scale_skeleton(child, scale)


# ═══════════════════════════════════════════════════════════════════════════════
#  Export helpers (re-exported from creature_appearance for convenience)
# ═══════════════════════════════════════════════════════════════════════════════

def export_character_b1(
    body_model,
    head_model,
    out_dir: str,
    game: str = "K1",
) -> dict:
    """
    Export body and head as two separate ASCII MDL files (Option B1).

    Delegates to creature_appearance.export_separate() for all validation.

    Returns
    -------
    dict with keys: ok, message, body_path, head_path, warnings
    """
    try:
        try:
            from core.characters.creature_appearance import CreatureAssembly  # type: ignore
        except ImportError:
            from src.core.characters.creature_appearance import CreatureAssembly  # type: ignore
    except Exception as exc:
        return {"ok": False, "message": f"Import error: {exc}",
                "body_path": None, "head_path": None, "warnings": []}

    asm = CreatureAssembly.from_models(body_model, head_model, game=game)
    if not asm.ok:
        return {
            "ok": False,
            "message": asm.warnings[0] if asm.warnings else "Assembly failed",
            "body_path": None,
            "head_path": None,
            "warnings": asm.warnings,
        }

    result = asm.export_separate(out_dir)
    return result


def list_template_files() -> List[Dict[str, str]]:
    """Return info dicts for all available template files."""
    entries = []
    for game in ("K1", "K2"):
        for part in ("body", "head"):
            path = get_template_path(game, part)
            size = os.path.getsize(path) if path else 0
            entries.append({
                "game":   game,
                "part":   part,
                "name":   f"gr_{part}_{game.lower()}",
                "path":   path or "(not found)",
                "exists": path is not None,
                "size":   size,
            })
    return entries
