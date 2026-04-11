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
      • Proper BindPose (T-pose world transforms) for correct rigging

    Export modes
    ------------
    Sparse keyframe mode  (default, ``bake=False``):
        Writes the raw KotOR controller keyframes directly.  File size is
        small but downstream tools must interpolate between sparse keys.

    Baked curve mode  (``bake=True``, *recommended for FBX*):
        Samples the animation via ``AnimationEngine.evaluate()`` at uniform
        intervals (default 30 fps).  Evaluation uses SLERP for rotations and
        LERP for positions (Gregory §12.4, Mukundan §4.3), guaranteeing
        smooth playback in every DCC tool.  File size is larger but quality
        matches what you see in the GhostRigger viewport.

    Supported target skeletons
    --------------------------
      • KotOR native    — no bone_remap needed
      • Mixamo          — use AnimationRetargeter.KOTOR_TO_MIXAMO
      • UE5 Mannequin   — use AnimationRetargeter.KOTOR_TO_UE5
      • Custom          — provide your own bone_remap dict

    Usage::

        engine  = AnimationEngine(model)
        exp     = FBXAnimationExporter()

        # Sparse (small file, good for KotOR-aware tools):
        exp.export(engine, "walk", "/out/walk_sparse.fbx")

        # Baked (smooth curves, best for Blender / UE5 / Maya):
        exp.export_baked(engine, "walk", "/out/walk_baked.fbx", fps=30)

        # All animations in one file:
        exp.export_all_baked(engine, "/out/all_anims.fbx", fps=30)
    """

    def export(self,
               engine,
               anim_name: str,
               output_path: str,
               fps: float = 30.0,
               bone_remap: Optional[Dict[str, str]] = None,
               include_bind_pose: bool = True,
               bake: bool = False) -> bool:
        """
        Export a single animation to FBX.

        Parameters
        ----------
        engine           : AnimationEngine with a model loaded.
        anim_name        : Name of the animation to export.
        output_path      : .fbx output path.
        fps              : Bake frame rate (default 30).  Ignored for sparse mode.
        bone_remap       : Optional {kotor_bone_lower → target_bone_name} dict.
                           Build with AnimationRetargeter.build_map().
        include_bind_pose: If True, write bind-pose T-pose frame (recommended).
        bake             : If True use engine.evaluate() for SLERP-quality curves.
                           If False (default) write sparse KotOR keyframes directly.

        Returns True on success, False on failure.
        """
        anim = engine._find_anim(anim_name)
        if anim is None:
            log.error("FBXAnimationExporter.export: anim '%s' not found", anim_name)
            return False
        if bake:
            return self._write_fbx_baked(engine, [anim], output_path, fps,
                                         bone_remap, include_bind_pose)
        return self._write_fbx(engine, [anim], output_path, fps,
                               bone_remap, include_bind_pose)

    def export_baked(self,
                     engine,
                     anim_name: str,
                     output_path: str,
                     fps: float = 30.0,
                     bone_remap: Optional[Dict[str, str]] = None) -> bool:
        """
        Export a single animation as a *baked* FBX (uniform-interval samples).

        Uses ``engine.evaluate(t)`` to produce smooth SLERP-interpolated curves
        at ``fps`` samples per second, giving the same quality as the viewport.
        This is the recommended export path for Blender, UE5, and Maya.

        Parameters
        ----------
        engine      : AnimationEngine (model already loaded).
        anim_name   : Animation name string.
        output_path : Destination .fbx path.
        fps         : Sampling rate (24, 30, 60 are all valid; default 30).
        bone_remap  : Optional bone-rename map. Use AnimationRetargeter.build_map().

        Returns True on success, False on failure.
        """
        return self.export(engine, anim_name, output_path,
                           fps=fps, bone_remap=bone_remap,
                           include_bind_pose=True, bake=True)

    def export_all(self,
                   engine,
                   output_path: str,
                   fps: float = 30.0,
                   bone_remap: Optional[Dict[str, str]] = None,
                   bake: bool = False) -> bool:
        """Export ALL animations from the model into one FBX with multiple AnimStacks."""
        anims = engine.model.animations
        if not anims:
            log.warning("FBXAnimationExporter.export_all: no animations in model")
            return False
        if bake:
            return self._write_fbx_baked(engine, anims, output_path, fps, bone_remap, True)
        return self._write_fbx(engine, anims, output_path, fps, bone_remap, True)

    def export_all_baked(self,
                         engine,
                         output_path: str,
                         fps: float = 30.0,
                         bone_remap: Optional[Dict[str, str]] = None) -> bool:
        """
        Export ALL animations into one FBX using baked (SLERP-quality) curves.

        Produces a single .fbx with one AnimationStack per animation.
        Import into Blender: File > Import > FBX, then select the action in
        the Action Editor.  Import into UE5: Content Browser > Import > FBX
        Animation.  Import into Maya: File > Import.

        Parameters
        ----------
        engine      : AnimationEngine.
        output_path : Destination .fbx path.
        fps         : Sampling rate (default 30).
        bone_remap  : Optional bone-rename map.

        Returns True on success, False on failure.
        """
        return self.export_all(engine, output_path,
                               fps=fps, bone_remap=bone_remap, bake=True)

    def export_library_entry(self,
                             entry: 'AnimationEntry',
                             anim_lib: 'AnimationLibrary',
                             output_path: str,
                             fps: float = 30.0,
                             bone_remap: Optional[Dict[str, str]] = None,
                             bake: bool = False) -> bool:
        """
        Convenience: export a single AnimationEntry from the library.
        Handles lazy model loading automatically.
        """
        engine = anim_lib.get_engine(entry)
        if engine is None:
            log.error("FBXAnimationExporter: could not load model for %s", entry.model_name)
            return False
        return self.export(engine, entry.anim_name, output_path,
                           fps=fps, bone_remap=bone_remap, bake=bake)

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

            # ── Bind Pose section ─────────────────────────────────────────────
            # Reference: 3D Mesh Processing §4.3 (Mukundan):
            #   Jk = Lk * Fk  where Lk = world-space transform (hierarchy concat)
            #   Fk = Lk⁻¹    (offset matrix = inverse of world bind-pose transform)
            # Reference: Game Engine Architecture §12.4 (Gregory):
            #   WorldTransform(j) = WorldTransform(parent) × LocalTransform(j)
            #
            # The FBX BindPose stores each node's WORLD-space transform at T-pose.
            # This tells the importer (Blender/UE5/Maya) the correct joint placement
            # before any animation is applied. Without this, bones import in wrong positions.
            if include_bind_pose:
                world_transforms = _build_world_transforms(all_nodes)
                pose_id = new_id()
                w(f"\tPose: {pose_id}, \"BindPose\", \"BindPose\" {{")
                w(f"\t\tType: \"BindPose\"")
                w(f"\t\tVersion: 100")
                w(f"\t\tNbPoseNodes: {len(all_nodes)}")
                for n in all_nodes:
                    nid = node_ids[n.name]
                    wt  = world_transforms.get(n.name.lower(), _mat4_identity())
                    # Write 4×4 world matrix row-major
                    flat = [wt[r][c] for r in range(4) for c in range(4)]
                    mat_str = ",".join(f"{v:.8f}" for v in flat)
                    w(f"\t\tPoseNode:  {{")
                    w(f"\t\t\tNode: {nid}")
                    w(f"\t\t\tMatrix: *16 {{")
                    w(f"\t\t\t\ta: {mat_str}")
                    w(f"\t\t\t}}")
                    w(f"\t\t}}")
                w(f"\t}}")
                # Store for connections
                node_ids["__bindpose__"] = pose_id

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

    # ── Baked-curve FBX writer ────────────────────────────────────────────────

    def _write_fbx_baked(self,
                         engine,
                         anims: list,
                         output_path: str,
                         fps: float,
                         bone_remap: Optional[Dict[str, str]],
                         include_bind_pose: bool) -> bool:
        """
        Write FBX ASCII 7.4 using *baked* (uniform-interval) animation curves.

        Unlike _write_fbx() which writes sparse KotOR keyframes directly,
        this method evaluates the AnimationEngine at every frame using SLERP
        interpolation, then writes one keyframe per frame at the target fps.

        This guarantees:
          • Smooth playback in Blender, UE5, Maya, MotionBuilder
          • Correct SLERP-quality rotation curves (no gimbal artefacts)
          • Delta-position correctly resolved to absolute world-local position
          • Same visual result as the GhostRigger viewport

        Algorithm (Gregory §12.4 + Mukundan §4.3):
          1. For each animation, determine frame count = ceil(length * fps)
          2. For each frame t = frame / fps, call engine.evaluate(t)
          3. The returned AnimPose contains per-bone local-space positions
             and rotations (already SLERP-interpolated by the engine)
          4. Convert rotations from quaternion → Euler XYZ (FBX rotation order)
          5. Write FBX AnimationCurve with one key per frame
        """
        try:
            model  = engine.model
            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

            lines: List[str] = []
            w = lines.append
            _id_counter = [2000]   # distinct range from _write_fbx

            def new_id() -> int:
                _id_counter[0] += 1
                return _id_counter[0]

            # ── Collect all skeleton nodes ────────────────────────────────────
            all_nodes: List[Any] = []
            if model.root_node:
                def _collect(n):
                    all_nodes.append(n)
                    for c in n.children:
                        _collect(c)
                _collect(model.root_node)

            # ── Build node-id / name maps ─────────────────────────────────────
            node_ids:      Dict[str, int] = {}
            effective_name: Dict[str, str] = {}
            for n in all_nodes:
                nid = new_id()
                fbx_name = n.name
                if bone_remap:
                    fbx_name = bone_remap.get(n.name.lower(), n.name)
                node_ids[n.name]       = nid
                effective_name[n.name] = fbx_name

            # ── FBX header ────────────────────────────────────────────────────
            import datetime
            now = datetime.datetime.now()
            w("; FBX 7.4.0 project file")
            w("; Generated by GhostRigger-K1-K2 AnimationLibrary (baked curves)")
            w(f"; Model: {model.name}")
            w(f"; Animations: {', '.join(a.name for a in anims)}")
            w(f"; Bake FPS: {fps:.1f}")
            w("")
            w("FBXHeaderExtension:  {")
            w("\tFBXHeaderVersion: 1003")
            w("\tFBXVersion: 7400")
            w("\tCreationTimeStamp:  {")
            w(f"\t\tYear: {now.year}")
            w(f"\t\tMonth: {now.month}")
            w(f"\t\tDay: {now.day}")
            w("\t}")
            w("\tCreator: \"GhostRigger-K1-K2 (baked)\"")
            w("}")
            w("")
            w("GlobalSettings:  {")
            w("\tVersion: 1000")
            w("\tProperties70:  {")
            w("\t\tP: \"UpAxis\", \"int\", \"Integer\", \"\",2")
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

            # Write skeleton LimbNodes
            for n in all_nodes:
                nid      = node_ids[n.name]
                fbx_name = effective_name[n.name]
                is_root  = (n.parent is None)

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

                skel_id = new_id()
                skel_type = "Root" if is_root else "LimbNode"
                w(f"\tNodeAttribute: {skel_id}, \"{fbx_name}\", \"Skeleton\" {{")
                w(f"\t\tProperties70:  {{")
                w(f"\t\t\tP: \"Color\", \"ColorRGB\", \"Color\", \"\",0.8,0.8,0.8")
                w(f"\t\t\tP: \"Size\", \"double\", \"Number\", \"\",1")
                w(f"\t\t}}")
                w(f"\t}}")
                node_ids[f"__skel_{n.name}"] = skel_id

            # ── BindPose (T-pose world transforms) ───────────────────────────
            # Mukundan §4.3: Fk = (bind-pose global transform)⁻¹
            # Gregory §12.4: WorldTransform(j) = WorldTransform(parent) × Local(j)
            if include_bind_pose:
                world_transforms = _build_world_transforms(all_nodes)
                pose_id = new_id()
                w(f"\tPose: {pose_id}, \"BindPose\", \"BindPose\" {{")
                w(f"\t\tType: \"BindPose\"")
                w(f"\t\tVersion: 100")
                w(f"\t\tNbPoseNodes: {len(all_nodes)}")
                for n in all_nodes:
                    nid = node_ids[n.name]
                    wt  = world_transforms.get(n.name.lower(), _mat4_identity())
                    flat = [wt[r][c] for r in range(4) for c in range(4)]
                    mat_str = ",".join(f"{v:.8f}" for v in flat)
                    w(f"\t\tPoseNode:  {{")
                    w(f"\t\t\tNode: {nid}")
                    w(f"\t\t\tMatrix: *16 {{")
                    w(f"\t\t\t\ta: {mat_str}")
                    w(f"\t\t\t}}")
                    w(f"\t\t}}")
                w(f"\t}}")
                node_ids["__bindpose__"] = pose_id

            # ── Bake animations ───────────────────────────────────────────────
            # Gregory §12.4 + Mukundan §4.3:
            #   For each animation frame t = i/fps:
            #     pose = engine.evaluate(t)   ← SLERP-interpolated bone poses
            #     for each bone: extract local position + rotation from NodePose
            #     convert rotation quat → Euler XYZ (FBX rotation order)
            #     store as dense FBX AnimationCurve (one key per frame)
            #
            # CRITICAL: engine.evaluate() returns LOCAL-space transforms (not world).
            # The AnimPose.nodes[name].position is the bone's local position
            # (bind_pos + animated delta), and .rotation is the absolute quaternion.
            # These are exactly what FBX expects for Lcl Translation / Lcl Rotation.

            anim_connections: List[str] = []
            anim_stack_info:  List[Tuple[Any, int, int]] = []

            # Bind-pose per-node for fallback when bone not animated
            _bind_nodes = {n.name.lower(): n for n in all_nodes}

            for anim in anims:
                stack_id = new_id()
                layer_id = new_id()
                anim_stack_info.append((anim, stack_id, layer_id))

                length    = max(0.001, anim.length)
                n_frames  = max(1, int(math.ceil(length * fps)))
                anim_ticks = int(length * FBX_TICKS)

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

                # Set up engine for this animation (no cross-fade; direct evaluation)
                engine.play(anim.name, loop=False, blend=False)

                # Sample all frames ── O(n_frames × n_bones) ──────────────────
                # frames[t_idx][bone_name_lower] = (px, py, pz, rx, ry, rz, rw)
                sampled: List[Dict[str, Tuple]] = []
                for fi in range(n_frames):
                    t = fi / fps
                    pose = engine.evaluate(t)
                    frame_data: Dict[str, Tuple] = {}
                    for n in all_nodes:
                        nl = n.name.lower()
                        np_ = pose.nodes.get(nl)
                        if np_ is not None:
                            frame_data[nl] = (
                                np_.position[0], np_.position[1], np_.position[2],
                                np_.rotation[0], np_.rotation[1],
                                np_.rotation[2], np_.rotation[3],
                            )
                        else:
                            # Bone not animated: use bind pose
                            bind = _bind_nodes.get(nl)
                            if bind:
                                frame_data[nl] = (
                                    bind.position[0], bind.position[1], bind.position[2],
                                    bind.rotation[0], bind.rotation[1],
                                    bind.rotation[2], bind.rotation[3],
                                )
                    sampled.append(frame_data)

                # Build FBX time array (uniform)
                frame_times_ticks = [int((fi / fps) * FBX_TICKS) for fi in range(n_frames)]

                def _write_baked_curve(axis_label: str,
                                       axis_i: int,
                                       default_val: float,
                                       kvals: List[float],
                                       prop_name: str,
                                       nid: int):
                    cn_id = new_id()
                    cv_id = new_id()
                    ax    = axis_label[-1]
                    nt    = len(kvals)
                    w(f"\t\tAnimationCurveNode: {cn_id}, \"{axis_label}\", \"\" {{")
                    w(f"\t\t\tProperties70:  {{")
                    w(f"\t\t\t\tP: \"d|{ax}\", \"Number\", \"\", \"A\",{default_val:.6f}")
                    w(f"\t\t\t}}")
                    w(f"\t\t}}")
                    w(f"\t\tAnimationCurve: {cv_id}, \"\", \"\" {{")
                    w(f"\t\t\tDefault: {default_val:.6f}")
                    w(f"\t\t\tKeyVer: 4008")
                    w(f"\t\t\tKeyTime: *{nt} {{")
                    w("\t\t\t\ta: " + ",".join(str(t) for t in frame_times_ticks))
                    w(f"\t\t\t}}")
                    w(f"\t\t\tKeyValueFloat: *{nt} {{")
                    w("\t\t\t\ta: " + ",".join(f"{v:.6f}" for v in kvals))
                    w(f"\t\t\t}}")
                    # KeyAttrFlags: 24776 = cubic interpolation tangents-auto
                    # Use 8 for linear interpolation (more faithful to sparse data)
                    w(f"\t\t\tKeyAttrFlags: *{nt} {{")
                    w("\t\t\t\ta: " + ",".join(["8"] * nt))
                    w(f"\t\t\t}}")
                    w(f"\t\t\tKeyAttrRefCount: *1 {{")
                    w(f"\t\t\t\ta: {nt}")
                    w(f"\t\t\t}}")
                    w(f"\t\t}}")
                    anim_connections.append(f"\t\tC: \"OP\",{cv_id},{cn_id},\"d|{ax}\"")
                    anim_connections.append(f"\t\tC: \"OO\",{cn_id},{layer_id}")
                    anim_connections.append(f"\t\tC: \"OP\",{cn_id},{nid},\"{prop_name}\"")

                # Write per-bone curves
                anim_node_names = {an.name.lower() for an in anim.nodes}
                for n in all_nodes:
                    nl  = n.name.lower()
                    nid = node_ids.get(n.name)
                    if nid is None:
                        continue

                    # Only write curves for animated bones + root (which may move)
                    is_root   = (n.parent is None)
                    is_anim   = (nl in anim_node_names)
                    if not (is_anim or is_root):
                        continue

                    # Build per-axis value lists from sampled data
                    px_vals, py_vals, pz_vals = [], [], []
                    rx_vals, ry_vals, rz_vals = [], [], []

                    for frame_data in sampled:
                        fd = frame_data.get(nl)
                        if fd:
                            px_vals.append(fd[0]); py_vals.append(fd[1]); pz_vals.append(fd[2])
                            ex, ey, ez = _quat_to_euler_xyz(fd[3], fd[4], fd[5], fd[6])
                            rx_vals.append(ex); ry_vals.append(ey); rz_vals.append(ez)
                        else:
                            bind = _bind_nodes.get(nl)
                            bp = list(bind.position) if bind else [0.0, 0.0, 0.0]
                            br = list(bind.rotation) if bind else [0.0, 0.0, 0.0, 1.0]
                            px_vals.append(bp[0]); py_vals.append(bp[1]); pz_vals.append(bp[2])
                            ex, ey, ez = _quat_to_euler_xyz(br[0], br[1], br[2], br[3])
                            rx_vals.append(ex); ry_vals.append(ey); rz_vals.append(ez)

                    # Write translation curves
                    for axis_i, (label, kvals) in enumerate(zip(
                            ('T|X', 'T|Y', 'T|Z'),
                            (px_vals, py_vals, pz_vals))):
                        _write_baked_curve(label, axis_i, kvals[0] if kvals else 0.0,
                                           kvals, 'Lcl Translation', nid)

                    # Write rotation curves
                    for axis_i, (label, kvals) in enumerate(zip(
                            ('R|X', 'R|Y', 'R|Z'),
                            (rx_vals, ry_vals, rz_vals))):
                        _write_baked_curve(label, axis_i, kvals[0] if kvals else 0.0,
                                           kvals, 'Lcl Rotation', nid)

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

            # ── Connections ───────────────────────────────────────────────────
            w("")
            w("Connections:  {")

            for n in all_nodes:
                skel_id = node_ids.get(f"__skel_{n.name}")
                nid = node_ids[n.name]
                if skel_id:
                    w(f"\tC: \"OO\",{skel_id},{nid}")

            for n in all_nodes:
                nid = node_ids[n.name]
                if n.parent and n.parent.name in node_ids:
                    pid = node_ids[n.parent.name]
                    w(f"\tC: \"OO\",{nid},{pid}")
                else:
                    w(f"\tC: \"OO\",{nid},0")

            for anim, stack_id, layer_id in anim_stack_info:
                w(f"\tC: \"OO\",{layer_id},{stack_id}")

            for c in anim_connections:
                w(c)

            w("}")  # end Connections

            content = "\n".join(lines)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            total_frames = sum(max(1, int(math.ceil(max(0.001, a.length) * fps)))
                               for a in anims)
            log.info("FBXAnimationExporter (baked): wrote %s  anims=%d  frames=%d  bytes=%d",
                     output_path, len(anims), total_frames, len(content))
            return True

        except Exception as exc:
            log.error("FBXAnimationExporter._write_fbx_baked: %s", exc, exc_info=True)
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
                             on_progress: Optional[Callable] = None,
                             bake: bool = True) -> List[str]:
    """
    Export all matching animations from the library to output_dir.

    Parameters
    ----------
    anim_lib    : populated AnimationLibrary
    output_dir  : directory to write files into
    query       : optional text filter
    game        : "K1", "K2", or "All"
    fps         : bake frame rate (used when fmt="fbx" and bake=True)
    fmt         : "fbx", "bvh", or "json"
    bone_remap  : optional bone renaming dict
    on_progress : callback(done, total, current_file)
    bake        : if True (default) use engine.evaluate() for smooth FBX curves.
                  If False write sparse KotOR keyframes directly.

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
                                    fps=fps, bone_remap=bone_remap, bake=bake)
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
#
# Reference: "3D Mesh Processing and Character Animation" (Mukundan, 2022)
#   - §Skeleton: Jk = Lk * Fk  where Lk = parent_world * local_SQT
#   - §Skinning: v' = Σ wi * Ji * v   (Linear Blend Skinning)
#   - §Retargeting: Map-JN via hash maps, Map-EA for axis alignment
#
# Reference: "Game Engine Architecture 4th Ed" (Gregory, 2022)
#   - §Animation: SQT format — Scale + Quaternion + Translation
#   - §Quaternion SLERP: dot<0 → negate for shortest-path
#   - §Local→World: WorldTransform(j) = WorldTransform(parent) × LocalTransform(j)
# ─────────────────────────────────────────────────────────────────────────────


def _mat4_identity() -> List[List[float]]:
    """Return a 4×4 identity matrix as list of rows."""
    return [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]


def _mat4_mul(A: List[List[float]], B: List[List[float]]) -> List[List[float]]:
    """4×4 matrix multiply: C = A × B."""
    C = [[0.0]*4 for _ in range(4)]
    for i in range(4):
        for j in range(4):
            s = 0.0
            for k in range(4):
                s += A[i][k] * B[k][j]
            C[i][j] = s
    return C


def _mat4_from_sqt(px: float, py: float, pz: float,
                   qx: float, qy: float, qz: float, qw: float,
                   sx: float = 1.0, sy: float = 1.0, sz: float = 1.0
                   ) -> List[List[float]]:
    """
    Build a 4×4 TRS matrix from Scale-Quaternion-Translation (SQT).

    Algorithm (Game Engine Architecture §4.3.2):
      M = T * R * S
    where R is the rotation matrix from quaternion [qx,qy,qz,qw].

    This is the standard SQT → matrix conversion used by every game engine.
    The rotation matrix formula is the standard unit-quaternion → 3×3 matrix:

      [1-2(y²+z²)   2(xy-wz)    2(xz+wy) ]
      [2(xy+wz)    1-2(x²+z²)   2(yz-wx) ]
      [2(xz-wy)    2(yz+wx)    1-2(x²+y²)]
    """
    # Normalize quaternion for safety
    mag = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
    if mag > 1e-9:
        qx /= mag; qy /= mag; qz /= mag; qw /= mag
    else:
        qx, qy, qz, qw = 0.0, 0.0, 0.0, 1.0

    xx, yy, zz = qx*qx, qy*qy, qz*qz
    xy, xz, yz = qx*qy, qx*qz, qy*qz
    wx, wy, wz = qw*qx, qw*qy, qw*qz

    r00 = (1 - 2*(yy+zz)) * sx
    r01 = (2*(xy - wz))   * sy
    r02 = (2*(xz + wy))   * sz

    r10 = (2*(xy + wz))   * sx
    r11 = (1 - 2*(xx+zz)) * sy
    r12 = (2*(yz - wx))   * sz

    r20 = (2*(xz - wy))   * sx
    r21 = (2*(yz + wx))   * sy
    r22 = (1 - 2*(xx+yy)) * sz

    return [
        [r00, r01, r02, px],
        [r10, r11, r12, py],
        [r20, r21, r22, pz],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _mat4_inverse_trs(M: List[List[float]]) -> List[List[float]]:
    """
    Compute the inverse of a TRS matrix (no shear, no non-uniform scale in rotation).

    For a pure rotation+translation matrix:
      M = [ R | t ]  →  M⁻¹ = [ Rᵀ | -Rᵀt ]
          [ 0 | 1 ]             [ 0  |  1   ]

    This is the standard 'offset matrix' calculation used in skinning:
      Fk = (bind-pose global transform of joint k)⁻¹
    Reference: Mukundan §4.3 "The offset matrix transforms vertices from mesh
    space to the joint's local space (where the joint is at the origin)."
    """
    # Extract rotation (upper 3×3) and translation
    r = [[M[i][j] for j in range(3)] for i in range(3)]
    t = [M[i][3] for i in range(3)]

    # Inverse rotation = transpose (for orthonormal R)
    rt = [[r[j][i] for j in range(3)] for i in range(3)]

    # Inverse translation = -Rᵀ * t
    itx = -(rt[0][0]*t[0] + rt[0][1]*t[1] + rt[0][2]*t[2])
    ity = -(rt[1][0]*t[0] + rt[1][1]*t[1] + rt[1][2]*t[2])
    itz = -(rt[2][0]*t[0] + rt[2][1]*t[1] + rt[2][2]*t[2])

    return [
        [rt[0][0], rt[0][1], rt[0][2], itx],
        [rt[1][0], rt[1][1], rt[1][2], ity],
        [rt[2][0], rt[2][1], rt[2][2], itz],
        [0.0,      0.0,      0.0,      1.0],
    ]


def _build_world_transforms(nodes: list) -> Dict[str, List[List[float]]]:
    """
    Build the world-space (global) transformation matrix for every node
    by concatenating local SQT transforms down the hierarchy.

    Algorithm (3D Mesh Processing §3.2 + Game Engine Architecture §12.4):
      L0 = T0 * R0               (root: local = world)
      Lk = L_{parent(k)} * Tk * Rk   (children: multiply parent world × local)

    This implements the full parent→child transform chain that gives each
    joint its correct position and orientation in world space.

    Returns a dict: node_name_lower → 4×4 world transform matrix.
    """
    world: Dict[str, List[List[float]]] = {}

    def _visit(node, parent_world: List[List[float]]):
        px, py, pz = node.position
        rx, ry, rz, rw = node.rotation
        # Local SQT → matrix
        local_m = _mat4_from_sqt(px, py, pz, rx, ry, rz, rw)
        # World = parent_world × local
        world_m = _mat4_mul(parent_world, local_m)
        world[node.name.lower()] = world_m
        for child in node.children:
            _visit(child, world_m)

    for node in nodes:
        if node.parent is None:
            _visit(node, _mat4_identity())

    return world


def _slerp_quat(q1: Tuple, q2: Tuple, t: float) -> Tuple[float, float, float, float]:
    """
    SLERP between two quaternions with shortest-path correction.

    Algorithm (3D Mesh Processing §7.3 + Game Engine Architecture §4.3.1):
      1. Compute dot product
      2. If dot < 0: negate q2 (shortest-path / same hemisphere)
      3. If dot > 0.9995: use LERP + normalize (nearly identical)
      4. Else: SLERP formula = sin((1-t)Ω)/sinΩ * q1 + sin(tΩ)/sinΩ * q2

    The 'dot < 0 → negate' step is the critical fix for the 'long way around'
    rotation problem that causes 360° spin artifacts.
    """
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q2
    dot = x1*x2 + y1*y2 + z1*z2 + w1*w2
    if dot < 0.0:          # shortest-path correction
        x2, y2, z2, w2 = -x2, -y2, -z2, -w2
        dot = -dot
    if dot > 0.9995:       # nearly identical — use LERP + normalize
        rx = x1 + t*(x2-x1); ry = y1 + t*(y2-y1)
        rz = z1 + t*(z2-z1); rw = w1 + t*(w2-w1)
    else:
        theta_0 = math.acos(min(dot, 1.0))
        theta   = theta_0 * t
        s2      = math.sin(theta) / math.sin(theta_0)
        s1      = math.cos(theta) - dot * s2
        rx = s1*x1 + s2*x2; ry = s1*y1 + s2*y2
        rz = s1*z1 + s2*z2; rw = s1*w1 + s2*w2
    mag = math.sqrt(rx*rx + ry*ry + rz*rz + rw*rw)
    if mag > 1e-9:
        rx /= mag; ry /= mag; rz /= mag; rw /= mag
    return (rx, ry, rz, rw)


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
