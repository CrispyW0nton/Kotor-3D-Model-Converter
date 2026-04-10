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
from typing import List, Optional, Tuple, Dict, Set

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

    Returns a KotorModel ready to use as a rig source, or None on failure.
    """
    path = get_template_path(game, part)
    if not path:
        log.warning("character_builder.load_template: template not found (%s/%s)", game, part)
        return None

    try:
        try:
            from core.kotor_loader import load_model_from_file  # type: ignore
        except ImportError:
            from src.core.kotor_loader import load_model_from_file  # type: ignore

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
            from core.kotor_install import KotorInstallation  # type: ignore
            from core.kotor_loader import load_model_from_bytes  # type: ignore
            from core.mdl_parser import MDLAsciiWriter  # type: ignore
            from core.model_data import NodeFlags  # type: ignore
        except ImportError:
            from src.core.kotor_install import KotorInstallation  # type: ignore
            from src.core.kotor_loader import load_model_from_bytes  # type: ignore
            from src.core.mdl_parser import MDLAsciiWriter  # type: ignore
            from src.core.model_data import NodeFlags  # type: ignore
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
                from core.model_data import NodeFlags  # type: ignore
            except ImportError:
                from src.core.model_data import NodeFlags  # type: ignore
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

    Parameters
    ----------
    mesh_model      : KotorModel of the imported OBJ/FBX mesh (no rig)
    template_model  : KotorModel from load_template()
    game            : 'K1' or 'K2'
    scale_mode      : 'auto' (match heights) or 'manual'
    scale_factor    : only used when scale_mode == 'manual'

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

    # Compute scale factor
    applied_scale = 1.0
    if scale_mode == "auto":
        try:
            mesh_h = _model_height(mesh_model)
            tmpl_h = _model_height(template_model)
            if tmpl_h > 0.01:
                applied_scale = mesh_h / tmpl_h
        except Exception as exc:
            warnings.append(f"Auto-scale failed: {exc}")
    elif scale_mode == "manual":
        applied_scale = max(0.01, float(scale_factor))

    # Clone mesh model
    try:
        import copy
        result_model = copy.deepcopy(mesh_model)
    except Exception as exc:
        return {"ok": False, "model": None,
                "message": f"Failed to clone mesh model: {exc}",
                "warnings": warnings, "scale": applied_scale}

    # Transfer skeleton from template: attach template's root as a skeleton
    # overlay. The mesh's root node becomes a child of template's Mesh_Root.
    try:
        tmpl_root = template_model.root_node
        if tmpl_root is None:
            return {"ok": False, "model": None,
                    "message": "Template has no root node",
                    "warnings": warnings, "scale": applied_scale}

        import copy
        skel_root = copy.deepcopy(tmpl_root)

        # Apply scale to skeleton positions if needed
        if abs(applied_scale - 1.0) > 0.001:
            _scale_skeleton(skel_root, applied_scale)
            warnings.append(f"Skeleton scaled by {applied_scale:.3f} to match mesh height")

        # Set supermodel to match game
        sm = "S_Female02" if game.upper() in ("K1", "K2") else "NULL"
        result_model.supermodel = sm

        # Attach mesh nodes under the template skeleton
        if result_model.root_node is not None:
            mesh_node = result_model.root_node
            skel_root.children = [c for c in (getattr(skel_root, "children", []) or [])
                                   if getattr(c, "is_mesh", False) is False
                                   and getattr(c, "is_skin", False) is False]
            skel_root.children.append(mesh_node)
            mesh_node.parent = skel_root

        result_model.root_node = skel_root
        result_model.animations = list(template_model.animations)

        log.info(
            "apply_template_rig: success  game=%s  scale=%.3f  "
            "skel_bones=%d  anims=%d",
            game, applied_scale,
            template_model.node_count(),
            len(result_model.animations),
        )
        return {
            "ok": True,
            "model": result_model,
            "message": (
                f"Template rig applied ({game}).  "
                f"Scale: {applied_scale:.3f}.  "
                f"Anims: {len(result_model.animations)}"
            ),
            "warnings": warnings,
            "scale": applied_scale,
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
            from core.creature_appearance import CreatureAssembly  # type: ignore
        except ImportError:
            from src.core.creature_appearance import CreatureAssembly  # type: ignore
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
