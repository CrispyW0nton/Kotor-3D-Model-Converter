"""
animation_library.py — KotOR Animation Library & FBX Retargeting Pipeline
===========================================================================

Three key features:

1. AnimationLibrary
   Scans all game models (K1 + K2) and catalogs every animation.
   Supports search by name, model, length, or type.
   Keeps animations in memory (lazy-load) for playback & export.

2. FBXAnimationExporter
   Bakes a KotOR animation onto a KotorModel (or external FBX skeleton)
   and writes a self-contained FBX file that Blender / UE5 / Maya can read.

   Pipeline:
     KotOR MDL (binary) ──► AnimationEngine.eval_pose() per frame
         ──► bake absolute world-space bone transforms (pos + quat)
         ──► write FBX AnimStack / AnimLayer / AnimCurve per bone
         ──► optional retarget: map KotOR bone names → user FBX bone names

3. AnimationRetargeter
   Remaps bone names from the KotOR humanoid skeleton to a Mixamo-,
   UE5-Mannequin-, or user-defined skeleton via a configurable bone map.

Usage::

    lib = AnimationLibrary()
    lib.scan(game_library)          # populate from GameLibrary
    entry = lib.search("walk")[0]
    engine = lib.get_engine(entry)  # lazy-loads model

    exporter = FBXAnimationExporter()
    exporter.export(engine, "walk", "/out/walk.fbx")

    # With retargeting to Mixamo skeleton:
    remap = AnimationRetargeter.MIXAMO_MAP
    exporter.export(engine, "walk", "/out/walk_mixamo.fbx", bone_remap=remap)
"""

from __future__ import annotations

import json
import logging
import math
import os
import struct
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AnimationEntry:
    """One animation from the library."""
    model_name:  str          # source model resref (e.g. "c_bantha")
    game:        str          # "K1" or "K2"
    anim_name:   str          # animation name (e.g. "walk")
    length:      float        # animation length in seconds
    node_count:  int          # number of animated nodes
    key_count:   int          # total keyframe count across all nodes
    model_class: str          # "creature", "character", "placeable", etc.
    # Lazy refs — populated on first use
    _model_bytes: Optional[Tuple[bytes, bytes]] = field(default=None, repr=False)
    _model_obj:   Optional[Any]                 = field(default=None, repr=False)

    @property
    def display_name(self) -> str:
        return f"{self.model_name}::{self.anim_name}"

    @property
    def fps_estimate(self) -> float:
        """Rough FPS estimate from key density."""
        if self.length <= 0 or self.node_count == 0:
            return 30.0
        kpn = self.key_count / max(1, self.node_count)
        kps = kpn / max(0.001, self.length)
        for candidate in (60, 30, 25, 24, 15):
            if abs(kps - candidate) < candidate * 0.25:
                return float(candidate)
        return min(120.0, max(15.0, kps))


# ─────────────────────────────────────────────────────────────────────────────
#  AnimationLibrary
# ─────────────────────────────────────────────────────────────────────────────

class AnimationLibrary:
    """
    Scans the game library and catalogs every animation from every model.

    Scanning is done on a background thread; use ``on_progress`` and
    ``on_complete`` callbacks to update UI.
    """

    def __init__(self):
        self.entries: List[AnimationEntry] = []
        self._by_model: Dict[str, List[AnimationEntry]] = {}
        self._lock = threading.Lock()
        self._scan_thread: Optional[threading.Thread] = None
        self.is_scanning = False
        self.scan_progress: str = ""
        self.scan_count = 0
        self.scan_total = 0

    # ── Scanning ─────────────────────────────────────────────────────────────

    def scan(self,
             game_library,
             on_progress: Optional[Callable[[str, int, int], None]] = None,
             on_complete: Optional[Callable[[int], None]] = None,
             background: bool = True):
        """
        Scan all models in *game_library* and populate the animation catalog.

        Parameters
        ----------
        game_library  : GameLibrary instance (already scanned)
        on_progress   : callback(status_str, done_count, total_count)
        on_complete   : callback(total_anims_found)
        background    : If True, run in a background thread (non-blocking).
        """
        if self.is_scanning:
            log.warning("AnimationLibrary.scan: already scanning, ignoring")
            return

        def _run():
            self.is_scanning = True
            try:
                self._do_scan(game_library, on_progress)
            finally:
                self.is_scanning = False
                total = len(self.entries)
                if on_complete:
                    on_complete(total)
                log.info("AnimationLibrary scan complete: %d animations", total)

        if background:
            self._scan_thread = threading.Thread(target=_run, daemon=True,
                                                  name="anim-lib-scan")
            self._scan_thread.start()
        else:
            _run()

    def _do_scan(self, game_library, on_progress):
        """Internal: iterate all models and extract animation metadata."""
        try:
            from src.core.kotor_loader import load_model_from_bytes
        except ImportError:
            from core.kotor_loader import load_model_from_bytes  # type: ignore

        models = list(game_library.models)
        self.scan_total = len(models)
        new_entries: List[AnimationEntry] = []

        for i, entry in enumerate(models):
            self.scan_count = i
            if on_progress and (i % 20 == 0 or i == len(models) - 1):
                on_progress(
                    f"Scanning {entry.resref} ({i+1}/{len(models)})",
                    i + 1, len(models))

            try:
                mdl_bytes, mdx_bytes = game_library.get_model_data(entry)
                if not mdl_bytes:
                    continue
                model = load_model_from_bytes(mdl_bytes, mdx_bytes or b"")
                if model is None:
                    continue

                game = "K2" if getattr(entry, 'game', 'K1') == 'K2' else "K1"
                cls  = getattr(entry, 'classification', '') or getattr(model, 'classification', '') or 'unknown'

                for anim in model.animations:
                    total_keys = sum(
                        sum(len(c.get('times', [])) for c in n.controllers)
                        if isinstance(n.controllers, list) else
                        sum(len(v.get('times', [])) for v in n.controllers.values())
                        for n in anim.nodes
                    )
                    ae = AnimationEntry(
                        model_name  = entry.resref.lower(),
                        game        = game,
                        anim_name   = anim.name,
                        length      = anim.length,
                        node_count  = len(anim.nodes),
                        key_count   = total_keys,
                        model_class = cls,
                    )
                    # Cache raw bytes for lazy model loading
                    ae._model_bytes = (mdl_bytes, mdx_bytes or b"")
                    new_entries.append(ae)

            except Exception as exc:
                log.debug("AnimationLibrary: skip %s — %s", entry.resref, exc)

        with self._lock:
            self.entries = new_entries
            self._by_model.clear()
            for ae in new_entries:
                self._by_model.setdefault(ae.model_name, []).append(ae)

    # ── Query API ────────────────────────────────────────────────────────────

    def search(self,
               query: str = "",
               game: str = "All",
               model_class: str = "All",
               min_length: float = 0.0,
               max_length: float = 9999.0) -> List[AnimationEntry]:
        """Return filtered list of AnimationEntries."""
        q = query.strip().lower()
        results = []
        with self._lock:
            for ae in self.entries:
                if game != "All" and ae.game != game:
                    continue
                if model_class != "All" and ae.model_class.lower() != model_class.lower():
                    continue
                if not (min_length <= ae.length <= max_length):
                    continue
                if q and q not in ae.anim_name.lower() and q not in ae.model_name.lower():
                    continue
                results.append(ae)
        return results

    def get_model_animations(self, model_name: str) -> List[AnimationEntry]:
        """Return all animations for a given model."""
        with self._lock:
            return list(self._by_model.get(model_name.lower(), []))

    def get_all_model_names(self) -> List[str]:
        """Return sorted list of all model names that have animations."""
        with self._lock:
            return sorted(self._by_model.keys())

    def get_all_anim_names(self) -> List[str]:
        """Return sorted unique list of all animation names across all models."""
        with self._lock:
            return sorted({ae.anim_name for ae in self.entries})

    def get_engine(self, entry: AnimationEntry):
        """
        Return an AnimationEngine for the given entry.
        Lazy-loads the model from cached bytes on first call.
        """
        try:
            from src.core.animation_engine import AnimationEngine
            from src.core.kotor_loader import load_model_from_bytes
        except ImportError:
            from core.animation_engine import AnimationEngine  # type: ignore
            from core.kotor_loader import load_model_from_bytes  # type: ignore

        if entry._model_obj is None and entry._model_bytes:
            mdl_bytes, mdx_bytes = entry._model_bytes
            entry._model_obj = load_model_from_bytes(mdl_bytes, mdx_bytes)
        if entry._model_obj is None:
            return None
        engine = AnimationEngine(entry._model_obj)
        return engine

    @property
    def stats(self) -> Dict[str, int]:
        """Return basic statistics about the library."""
        with self._lock:
            return {
                'total_animations': len(self.entries),
                'total_models':     len(self._by_model),
                'k1_animations':    sum(1 for e in self.entries if e.game == 'K1'),
                'k2_animations':    sum(1 for e in self.entries if e.game == 'K2'),
            }


# ─────────────────────────────────────────────────────────────────────────────
#  Bone name mappings for retargeting
# ─────────────────────────────────────────────────────────────────────────────

class AnimationRetargeter:
    """
    Maps KotOR skeleton bone names to external skeleton bone names.

    Usage::

        remap = AnimationRetargeter.build_map(
            AnimationRetargeter.KOTOR_TO_MIXAMO)
        exporter.export(..., bone_remap=remap)
    """

    # KotOR humanoid bone names (K1/K2 female/male body skeletons)
    KOTOR_BONES = [
        "rootdummy", "pelvis_g",
        "torso_g", "torsoupr_g",
        "rcollar_g", "rbicep_g", "rbicepl_g", "rforearm_g", "rhand",
        "lcollar_g", "lbicep_g", "lbicepl_g", "lforearm_g", "lhand",
        "rthigh_g", "rshin_g", "rfoot_g", "rfoott_g",
        "lthigh_g", "lshin_g", "lfoot_g", "lfoott_g",
        "neck_g", "necklwr_g",
        "headhook", "camerahook", "headconjure",
    ]

    # KotOR → Mixamo bone name map
    KOTOR_TO_MIXAMO: Dict[str, str] = {
        "rootdummy":   "mixamorig:Hips",
        "pelvis_g":    "mixamorig:Hips",
        "torso_g":     "mixamorig:Spine",
        "torsoupr_g":  "mixamorig:Spine1",
        "rcollar_g":   "mixamorig:RightShoulder",
        "rbicep_g":    "mixamorig:RightArm",
        "rbicepl_g":   "mixamorig:RightForeArm",
        "rforearm_g":  "mixamorig:RightForeArm",
        "rhand":       "mixamorig:RightHand",
        "lcollar_g":   "mixamorig:LeftShoulder",
        "lbicep_g":    "mixamorig:LeftArm",
        "lbicepl_g":   "mixamorig:LeftForeArm",
        "lforearm_g":  "mixamorig:LeftForeArm",
        "lhand":       "mixamorig:LeftHand",
        "rthigh_g":    "mixamorig:RightUpLeg",
        "rshin_g":     "mixamorig:RightLeg",
        "rfoot_g":     "mixamorig:RightFoot",
        "rfoott_g":    "mixamorig:RightToeBase",
        "lthigh_g":    "mixamorig:LeftUpLeg",
        "lshin_g":     "mixamorig:LeftLeg",
        "lfoot_g":     "mixamorig:LeftFoot",
        "lfoott_g":    "mixamorig:LeftToeBase",
        "neck_g":      "mixamorig:Neck",
        "necklwr_g":   "mixamorig:Neck",
        "headhook":    "mixamorig:Head",
        "camerahook":  "mixamorig:Head",
        "headconjure": "mixamorig:Head",
    }

    # KotOR → Unreal Engine 5 Mannequin bone names
    KOTOR_TO_UE5: Dict[str, str] = {
        "rootdummy":   "pelvis",
        "pelvis_g":    "pelvis",
        "torso_g":     "spine_01",
        "torsoupr_g":  "spine_02",
        "rcollar_g":   "clavicle_r",
        "rbicep_g":    "upperarm_r",
        "rbicepl_g":   "lowerarm_r",
        "rforearm_g":  "lowerarm_r",
        "rhand":       "hand_r",
        "lcollar_g":   "clavicle_l",
        "lbicep_g":    "upperarm_l",
        "lbicepl_g":   "lowerarm_l",
        "lforearm_g":  "lowerarm_l",
        "lhand":       "hand_l",
        "rthigh_g":    "thigh_r",
        "rshin_g":     "calf_r",
        "rfoot_g":     "foot_r",
        "rfoott_g":    "ball_r",
        "lthigh_g":    "thigh_l",
        "lshin_g":     "calf_l",
        "lfoot_g":     "foot_l",
        "lfoott_g":    "ball_l",
        "neck_g":      "neck_01",
        "necklwr_g":   "neck_01",
        "headhook":    "head",
        "camerahook":  "head",
        "headconjure": "head",
    }

    @staticmethod
    def build_map(mapping: Dict[str, str],
                  case_insensitive: bool = True) -> Dict[str, str]:
        """
        Build a bone remap dictionary.

        Parameters
        ----------
        mapping          : Dict mapping KotOR bone names to target names.
        case_insensitive : If True, lookup is case-insensitive.

        Returns
        -------
        Dict[str, str] mapping lower-case KotOR bone names to target names.
        """
        if case_insensitive:
            return {k.lower(): v for k, v in mapping.items()}
        return dict(mapping)

    @staticmethod
    def from_json(path: str) -> Dict[str, str]:
        """Load a bone remap from a JSON file (dict: kotor_name → target_name)."""
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        return {k.lower(): v for k, v in raw.items()}

    @staticmethod
    def save_json(remap: Dict[str, str], path: str):
        """Save a bone remap to JSON."""
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(remap, f, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
#  FBX Animation Exporter
# ─────────────────────────────────────────────────────────────────────────────

FBX_TICKS = 46186158000   # FBX standard: 1 second = 46186158000 ticks


class FBXAnimationExporter:
    """
    Bakes a KotOR animation onto a skeleton and writes a self-contained FBX.

    The exported FBX contains:
      • Full bone hierarchy (as FBX Skeleton / LimbNode nodes)
      • Per-bone AnimationCurve data for translation (X/Y/Z) and rotation (X/Y/Z)
      • One AnimationStack + AnimationLayer per exported animation
      • Takes block for Blender / UE4 compatibility
      • Optional geometry stub (empty meshes) so that skin weights transfer

    Supported target formats:
      • KotOR native skeleton  — no bone_remap needed
      • Mixamo skeleton        — use AnimationRetargeter.KOTOR_TO_MIXAMO
      • UE5 Mannequin          — use AnimationRetargeter.KOTOR_TO_UE5
      • Custom                 — provide your own bone_remap dict

    Usage::

        engine  = AnimationEngine(model)
        exp     = FBXAnimationExporter()
        exp.export(engine, "walk",  "/out/walk.fbx")
        exp.export_all(engine,      "/out/all_anims.fbx")
    """

    def export(self,
               engine,
               anim_name: str,
               output_path: str,
               fps: float = 30.0,
               bone_remap: Optional[Dict[str, str]] = None,
               include_bind_pose: bool = True) -> bool:
        """
        Export a single animation to FBX.

        Parameters
        ----------
        engine           : AnimationEngine with a model loaded.
        anim_name        : Name of the animation to export.
        output_path      : .fbx output path.
        fps              : Bake frame rate (default 30).
        bone_remap       : Optional dict: {kotor_bone_lower → target_bone_name}.
                           Use AnimationRetargeter.build_map() to create one.
        include_bind_pose: If True, write bind-pose transform for T-pose frame 0.

        Returns
        -------
        True on success, False on failure.
        """
        anim = engine._find_anim(anim_name)
        if anim is None:
            log.error("FBXAnimationExporter.export: anim '%s' not found", anim_name)
            return False
        return self._write_fbx(engine, [anim], output_path, fps,
                               bone_remap, include_bind_pose)

    def export_all(self,
                   engine,
                   output_path: str,
                   fps: float = 30.0,
                   bone_remap: Optional[Dict[str, str]] = None) -> bool:
        """Export ALL animations from the model into one FBX with multiple AnimStacks."""
        anims = engine.model.animations
        if not anims:
            log.warning("FBXAnimationExporter.export_all: no animations in model")
            return False
        return self._write_fbx(engine, anims, output_path, fps, bone_remap, True)

    def export_library_entry(self,
                             entry: 'AnimationEntry',
                             anim_lib: 'AnimationLibrary',
                             output_path: str,
                             fps: float = 30.0,
                             bone_remap: Optional[Dict[str, str]] = None) -> bool:
        """
        Convenience: export a single AnimationEntry from the library.
        Handles lazy model loading automatically.
        """
        engine = anim_lib.get_engine(entry)
        if engine is None:
            log.error("FBXAnimationExporter: could not load model for %s", entry.model_name)
            return False
        return self.export(engine, entry.anim_name, output_path, fps, bone_remap)

    # ── Core FBX writer ───────────────────────────────────────────────────────

    def _write_fbx(self,
                   engine,
                   anims: list,
                   output_path: str,
                   fps: float,
                   bone_remap: Optional[Dict[str, str]],
                   include_bind_pose: bool) -> bool:
        """
        Internal: write FBX ASCII 7.4 file with animated bone data.

        KotOR convention:
          • Position keyframes = DELTA from bind-pose (must add bind_pos)
          • Orientation keyframes = absolute quaternion (replace bind rotation)
          • anim_scale on model scales position deltas (usually 1.0 for K1/K2)
        """
        try:
            model = engine.model
            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

            lines: List[str] = []
            w = lines.append
            _id_counter = [1000]

            def new_id() -> int:
                _id_counter[0] += 1
                return _id_counter[0]

            # ── Collect all nodes in hierarchy order ──────────────────────────
            all_nodes: List[Any] = []
            if model.root_node:
                def _collect(n):
                    all_nodes.append(n)
                    for c in n.children:
                        _collect(c)
                _collect(model.root_node)

            # ── Build node-id map ─────────────────────────────────────────────
            # Apply bone_remap if provided
            node_ids: Dict[str, int] = {}
            effective_name: Dict[str, str] = {}   # kotor_name → fbx_name
            for n in all_nodes:
                nid = new_id()
                fbx_name = n.name
                if bone_remap:
                    fbx_name = bone_remap.get(n.name.lower(), n.name)
                node_ids[n.name] = nid
                effective_name[n.name] = fbx_name

            # ── FBX header ────────────────────────────────────────────────────
            w("; FBX 7.4.0 project file")
            w("; Generated by GhostRigger-K1-K2 AnimationLibrary")
            w(f"; Model: {model.name}")
            w(f"; Animations: {', '.join(a.name for a in anims)}")
            w("")
            w("FBXHeaderExtension:  {")
            w("\tFBXHeaderVersion: 1003")
            w("\tFBXVersion: 7400")
            w("\tCreationTimeStamp:  {")
            import datetime
            now = datetime.datetime.now()
            w(f"\t\tYear: {now.year}")
            w(f"\t\tMonth: {now.month}")
            w(f"\t\tDay: {now.day}")
            w("\t}")
            w("\tCreator: \"GhostRigger-K1-K2\"")
            w("}")
            w("")
            w("GlobalSettings:  {")
            w("\tVersion: 1000")
            w("\tProperties70:  {")
            w("\t\tP: \"UpAxis\", \"int\", \"Integer\", \"\",2")        # Z-up
            w("\t\tP: \"UpAxisSign\", \"int\", \"Integer\", \"\",1")
            w("\t\tP: \"FrontAxis\", \"int\", \"Integer\", \"\",1")
            w("\t\tP: \"FrontAxisSign\", \"int\", \"Integer\", \"\",-1")
            w("\t\tP: \"CoordAxis\", \"int\", \"Integer\", \"\",0")
            w("\t\tP: \"CoordAxisSign\", \"int\", \"Integer\", \"\",1")
            w("\t\tP: \"UnitScaleFactor\", \"double\", \"Number\", \"\",1")
            w("\t}")
            w("}")
            w("")

            # ── Objects section ───────────────────────────────────────────────
            w("Objects:  {")

            # Write skeleton nodes
            for n in all_nodes:
                nid = node_ids[n.name]
                fbx_name = effective_name[n.name]
                is_root = (n.parent is None)

                # Node Model object
                w(f"\tModel: {nid}, \"{fbx_name}\", \"LimbNode\" {{")
                w(f"\t\tVersion: 232")
                w(f"\t\tProperties70:  {{")
                px, py, pz = n.position
                w(f"\t\t\tP: \"Lcl Translation\", \"Lcl Translation\", \"\", \"A\","
                  f"{px:.6f},{py:.6f},{pz:.6f}")
                rx, ry, rz, rw = n.rotation
                ex, ey, ez = _quat_to_euler_xyz(rx, ry, rz, rw)
                w(f"\t\t\tP: \"Lcl Rotation\", \"Lcl Rotation\", \"\", \"A\","
                  f"{ex:.6f},{ey:.6f},{ez:.6f}")
                w(f"\t\t\tP: \"Lcl Scaling\", \"Lcl Scaling\", \"\", \"A\","
                  f"1.000000,1.000000,1.000000")
                w(f"\t\t\tP: \"RotationOrder\", \"enum\", \"\", \"\",0")
                w(f"\t\t\tP: \"InheritType\", \"enum\", \"\", \"\",1")
                w(f"\t\t}}")
                w(f"\t\tShading: Y")
                w(f"\t\tCulling: \"CullingOff\"")
                w(f"\t}}")

                # Skeleton Attribute
                skel_id = new_id()
                skel_type = "Root" if is_root else "LimbNode"
                w(f"\tNodeAttribute: {skel_id}, \"{fbx_name}\", \"Skeleton\" {{")
                w(f"\t\tProperties70:  {{")
                w(f"\t\t\tP: \"Color\", \"ColorRGB\", \"Color\", \"\",0.8,0.8,0.8")
                w(f"\t\t\tP: \"Size\", \"double\", \"Number\", \"\",1")
                w(f"\t\t}}")
                w(f"\t}}")
                # Store skel_id for connections later
                node_ids[f"__skel_{n.name}"] = skel_id

            # ── Animation objects ─────────────────────────────────────────────
            anim_connections: List[str] = []
            _base_nodes = {n.name.lower(): n for n in all_nodes}
            anim_scale = getattr(model, 'anim_scale', 1.0) or 1.0

            anim_stack_info: List[Tuple[Any, int, int]] = []

            for anim in anims:
                stack_id = new_id()
                layer_id = new_id()
                anim_stack_info.append((anim, stack_id, layer_id))

                anim_ticks = int(anim.length * FBX_TICKS)
                w(f"\tAnimationStack: {stack_id}, \"|{anim.name}\", \"\" {{")
                w(f"\t\tProperties70:  {{")
                w(f"\t\t\tP: \"LocalStart\", \"KTime\", \"Time\", \"\",0")
                w(f"\t\t\tP: \"LocalStop\", \"KTime\", \"Time\", \"\",{anim_ticks}")
                w(f"\t\t\tP: \"ReferenceStart\", \"KTime\", \"Time\", \"\",0")
                w(f"\t\t\tP: \"ReferenceStop\", \"KTime\", \"Time\", \"\",{anim_ticks}")
                w(f"\t\t}}")
                w(f"\t}}")
                w(f"\tAnimationLayer: {layer_id}, \"{anim.name}_Layer\", \"\" {{")
                w(f"\t}}")

                if not anim.nodes:
                    continue

                anim_node_map = {an.name.lower(): an for an in anim.nodes}

                for n in all_nodes:
                    an = anim_node_map.get(n.name.lower())
                    if an is None:
                        continue
                    nid = node_ids.get(n.name)
                    if nid is None:
                        continue

                    # Extract position + rotation controllers
                    pos_times = pos_vals = None
                    rot_times = rot_vals = None
                    ctrl_src = an.controllers
                    if isinstance(ctrl_src, dict):
                        ctrl_list = [{'type': k, **v} for k, v in ctrl_src.items()]
                    else:
                        ctrl_list = list(ctrl_src or [])

                    CTRL_POS = 8
                    CTRL_ROT = 20
                    for ctrl in ctrl_list:
                        ct = ctrl.get('type', -1)
                        if ct == CTRL_POS:
                            pos_times = ctrl.get('times', [])
                            pos_vals  = ctrl.get('values', [])
                        elif ct == CTRL_ROT:
                            rot_times = ctrl.get('times', [])
                            rot_vals  = ctrl.get('values', [])

                    bind = _base_nodes.get(n.name.lower())
                    bind_pos = list(bind.position) if bind else [0.0, 0.0, 0.0]

                    def _write_curve(axis_label: str,
                                     axis_i: int,
                                     default_val: float,
                                     ktimes: list,
                                     kvals: list,
                                     prop_name: str):
                        cn_id = new_id()
                        cv_id = new_id()
                        ax = axis_label[-1]
                        w(f"\t\tAnimationCurveNode: {cn_id}, \"{axis_label}\", \"\" {{")
                        w(f"\t\t\tProperties70:  {{")
                        w(f"\t\t\t\tP: \"d|{ax}\", \"Number\", \"\", \"A\",{default_val:.6f}")
                        w(f"\t\t\t}}")
                        w(f"\t\t}}")
                        nt = len(ktimes)
                        ticks = [int(t * FBX_TICKS) for t in ktimes]
                        w(f"\t\tAnimationCurve: {cv_id}, \"\", \"\" {{")
                        w(f"\t\t\tDefault: {default_val:.6f}")
                        w(f"\t\t\tKeyVer: 4008")
                        w(f"\t\t\tKeyTime: *{nt} {{")
                        w("\t\t\t\ta: " + ",".join(str(t) for t in ticks))
                        w(f"\t\t\t}}")
                        w(f"\t\t\tKeyValueFloat: *{nt} {{")
                        w("\t\t\t\ta: " + ",".join(f"{v:.6f}" for v in kvals))
                        w(f"\t\t\t}}")
                        w(f"\t\t\tKeyAttrFlags: *{nt} {{")
                        w("\t\t\t\ta: " + ",".join(["24776"] * nt))
                        w(f"\t\t\t}}")
                        w(f"\t\t\tKeyAttrRefCount: *1 {{")
                        w(f"\t\t\t\ta: {nt}")
                        w(f"\t\t\t}}")
                        w(f"\t\t}}")
                        anim_connections.append(f"\t\tC: \"OP\",{cv_id},{cn_id},\"d|{ax}\"")
                        anim_connections.append(f"\t\tC: \"OO\",{cn_id},{layer_id}")
                        anim_connections.append(f"\t\tC: \"OP\",{cn_id},{nid},\"{prop_name}\"")

                    # Translation: delta + bind_pos, scaled by anim_scale
                    if pos_times and pos_vals:
                        for axis_i, label in enumerate(('T|X', 'T|Y', 'T|Z')):
                            kvals_abs = [
                                bind_pos[axis_i] + (v[axis_i] if len(v) > axis_i else 0.0) * anim_scale
                                for v in pos_vals
                            ]
                            _write_curve(label, axis_i, bind_pos[axis_i],
                                         pos_times, kvals_abs, 'Lcl Translation')

                    # Rotation: absolute quaternion → Euler XYZ degrees
                    if rot_times and rot_vals:
                        euler_list = []
                        for qv in rot_vals:
                            if len(qv) >= 4:
                                euler_list.append(_quat_to_euler_xyz(qv[0], qv[1], qv[2], qv[3]))
                            else:
                                euler_list.append((0.0, 0.0, 0.0))
                        for axis_i, label in enumerate(('R|X', 'R|Y', 'R|Z')):
                            kvals_rot = [e[axis_i] for e in euler_list]
                            default_r = kvals_rot[0] if kvals_rot else 0.0
                            _write_curve(label, axis_i, default_r,
                                         rot_times, kvals_rot, 'Lcl Rotation')

            w("}")  # end Objects

            # ── Takes (legacy compatibility) ──────────────────────────────────
            w("")
            w("Takes:  {")
            if anims:
                w(f"\tCurrent: \"{anims[0].name}\"")
                for anim in anims:
                    ticks = int(anim.length * FBX_TICKS)
                    w(f"\tTake: \"{anim.name}\" {{")
                    w(f"\t\tFileName: \"{anim.name}.tak\"")
                    w(f"\t\tLocalTime: 0,{ticks}")
                    w(f"\t\tReferenceTime: 0,{ticks}")
                    w(f"\t}}")
            else:
                w('\tCurrent: ""')
            w("}")

            # ── Connections section ───────────────────────────────────────────
            w("")
            w("Connections:  {")

            # Skeleton attribute → model node
            for n in all_nodes:
                skel_id = node_ids.get(f"__skel_{n.name}")
                nid = node_ids[n.name]
                if skel_id:
                    w(f"\tC: \"OO\",{skel_id},{nid}")

            # Node hierarchy
            for n in all_nodes:
                nid = node_ids[n.name]
                if n.parent and n.parent.name in node_ids:
                    pid = node_ids[n.parent.name]
                    w(f"\tC: \"OO\",{nid},{pid}")
                else:
                    w(f"\tC: \"OO\",{nid},0")

            # AnimStack → AnimLayer
            for anim, stack_id, layer_id in anim_stack_info:
                w(f"\tC: \"OO\",{layer_id},{stack_id}")

            # Animation curve connections
            for c in anim_connections:
                w(c)

            w("}")  # end Connections

            content = "\n".join(lines)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            log.info("FBXAnimationExporter: wrote %s (%d anims, %d bytes)",
                     output_path, len(anims), len(content))
            return True

        except Exception as exc:
            log.error("FBXAnimationExporter._write_fbx: %s", exc, exc_info=True)
            return False


# ─────────────────────────────────────────────────────────────────────────────
#  Batch export helper
# ─────────────────────────────────────────────────────────────────────────────

def batch_export_animations(anim_lib: AnimationLibrary,
                             output_dir: str,
                             query: str = "",
                             game: str = "All",
                             fps: float = 30.0,
                             fmt: str = "fbx",
                             bone_remap: Optional[Dict[str, str]] = None,
                             on_progress: Optional[Callable] = None) -> List[str]:
    """
    Export all matching animations from the library to output_dir.

    Parameters
    ----------
    anim_lib    : populated AnimationLibrary
    output_dir  : directory to write files into
    query       : optional text filter
    game        : "K1", "K2", or "All"
    fps         : bake frame rate
    fmt         : "fbx", "bvh", or "json"
    bone_remap  : optional bone renaming dict
    on_progress : callback(done, total, current_file)

    Returns
    -------
    List of paths actually written.
    """
    entries = anim_lib.search(query=query, game=game)
    os.makedirs(output_dir, exist_ok=True)
    exported: List[str] = []
    fbx_exp = FBXAnimationExporter()

    for i, entry in enumerate(entries):
        safe_model = _safe_filename(entry.model_name)
        safe_anim  = _safe_filename(entry.anim_name)
        out_name   = f"{safe_model}_{safe_anim}.{fmt}"
        out_path   = os.path.join(output_dir, out_name)

        if on_progress:
            on_progress(i, len(entries), out_path)

        try:
            engine = anim_lib.get_engine(entry)
            if engine is None:
                continue

            ok = False
            if fmt == "fbx":
                ok = fbx_exp.export(engine, entry.anim_name, out_path,
                                    fps=fps, bone_remap=bone_remap)
            elif fmt == "bvh":
                ok = engine.export_animation_bvh(entry.anim_name, out_path)
            elif fmt == "json":
                ok = engine.export_animation_json(entry.anim_name, out_path)

            if ok:
                exported.append(out_path)
        except Exception as exc:
            log.warning("batch_export_animations: skip %s — %s", entry.display_name, exc)

    if on_progress:
        on_progress(len(entries), len(entries), "")

    return exported


# ─────────────────────────────────────────────────────────────────────────────
#  Math helpers
# ─────────────────────────────────────────────────────────────────────────────

def _quat_to_euler_xyz(qx: float, qy: float, qz: float, qw: float
                       ) -> Tuple[float, float, float]:
    """Convert quaternion to intrinsic XYZ Euler angles in degrees."""
    mag = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
    if mag > 1e-9:
        qx /= mag; qy /= mag; qz /= mag; qw /= mag

    # Intrinsic XYZ (extrinsic ZYX): matches FBX default rotation order
    sinY = 2.0 * (qw * qy - qz * qx)
    sinY = max(-1.0, min(1.0, sinY))
    ry   = math.asin(sinY)

    sinX_cosY = 2.0 * (qw * qx + qy * qz)
    cosX_cosY = 1.0 - 2.0 * (qx * qx + qy * qy)
    rx = math.atan2(sinX_cosY, cosX_cosY)

    sinZ_cosY = 2.0 * (qw * qz + qx * qy)
    cosZ_cosY = 1.0 - 2.0 * (qy * qy + qz * qz)
    rz = math.atan2(sinZ_cosY, cosZ_cosY)

    return math.degrees(rx), math.degrees(ry), math.degrees(rz)


def _safe_filename(s: str) -> str:
    """Make a string safe for use as a filename."""
    return "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in s)[:64]
