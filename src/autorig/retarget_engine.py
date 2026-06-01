"""
RetargetEngine  –  Phase 22  –  Scale-fit + Rig-Transfer + Animation-Retarget
==============================================================================

Full stateful pipeline for bringing an imported OBJ / FBX mesh into KotOR.

State machine stages (RetargetStage)
-------------------------------------
  EMPTY        – nothing loaded yet
  IMPORTED     – target mesh loaded, ready for a reference
  REFERENCED   – reference model loaded, ready to scale
  SCALED       – auto-scale applied, ready to transfer rig
  RIGGED       – rig transferred, ready for rig-edit or export
  RIG_EDIT     – user is adjusting bones in the viewport
  ANIM_READY   – animations transferred, ready to export

Public API (called by RetargetPanel in main_window.py)
------------------------------------------------------
  engine = RetargetEngine(progress_cb=…)

  engine.set_imported_model(model)          → dict(ok, message, …)
  engine.set_reference_model(model, name)   → dict(ok, message, …)
  engine.auto_scale(mode, manual_factor)    → dict(ok, message, scale_factor, …)
  engine.transfer_rig(scale_to_target, smooth_weights) → dict(ok, message, …)
  engine.begin_rig_edit()                   → dict(ok, message)
  engine.move_bone(name, new_pos)           → dict(ok, message)
  engine.confirm_rig_edit(recompute_weights)→ dict(ok, message)
  engine.cancel_rig_edit()                  → dict(ok, message)
  engine.transfer_animations()              → dict(ok, message, anim_count)
  engine.reset()
  engine.working_model                      → KotorModel | None
  engine.stage                              → RetargetStage

Helper classes (also imported by main_window.py)
-------------------------------------------------
  RetargetState      – named-tuple snapshot of engine state
  ScaleMode          – height / volume / manual constants
  ScaleSolver        – pure math helper for bounding-box fits
  MeshScaler         – applies a uniform scale factor to a KotorModel
  AnimationRetargeter – deep-copies animations + remaps node names
"""

from __future__ import annotations

import copy
import enum
import logging
import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

try:
    from ..core.geometry.model_data import (
        KotorModel, ModelNode, NodeFlags, BoneWeight,
        Animation, GameVersion,
    )
    from ..autorig.auto_rigger import AutoRigger, RigExtractor, RigTemplate
except ImportError:
    from core.geometry.model_data import (                               # type: ignore[no-redef]
        KotorModel, ModelNode, NodeFlags, BoneWeight,
        Animation, GameVersion,
    )
    from autorig.auto_rigger import AutoRigger, RigExtractor, RigTemplate  # type: ignore[no-redef]


# ─────────────────────────────────────────────────────────────────────────────
#  OrientationMode  –  source application coordinate convention
# ─────────────────────────────────────────────────────────────────────────────

class OrientationMode(str, enum.Enum):
    """
    Describes the source application's coordinate convention so the importer
    can rotate the mesh into KotOR's Z-up right-handed system.

    KotOR (Odyssey engine) convention:
        X = right,  Y = forward (into scene),  Z = up
        Characters stand along the +Z axis (feet at Z=0, head at Z≈1.8).
        Characters face the +Y direction by default.

    AUTO   – detect automatically from the model's bounding-box spans
    ZUP    – source is already Z-up (3ds Max, Cinema4D, KotOR-native)
    YUP    – source is Y-up (Blender default OBJ, Maya OBJ/FBX)
    XUP    – source is X-up (unusual; some older workflows)
    """
    AUTO = "AUTO"
    ZUP  = "ZUP"
    YUP  = "YUP"
    XUP  = "XUP"


# ─────────────────────────────────────────────────────────────────────────────
#  ModelOrientFixer  –  rotates imported geometry into KotOR's Z-up system
# ─────────────────────────────────────────────────────────────────────────────

class ModelOrientFixer:
    """
    Transforms an imported OBJ / FBX model from its source coordinate system
    into KotOR's Z-up right-handed coordinate system and snaps it to the floor.

    KotOR convention: X=right, Y=forward, Z=up.
    Characters should stand upright with feet near Z=0.

    Supported source conventions
    ----------------------------
    YUP  (Blender, Maya):  up=Y, forward=-Z
        Rotation: new_X = old_X,  new_Y = -old_Z,  new_Z = old_Y
        (90° rotation around +X axis)

    ZUP  (3ds Max, Cinema4D, KotOR-native):  up=Z, forward=Y
        No axis rotation needed; only floor-snap is applied.

    XUP  (rare):  up=X
        Rotation: new_X = -old_Z,  new_Y = old_Y,  new_Z = old_X
        (90° rotation around -Y axis)

    AUTO detection
    --------------
    Compares the bounding-box spans on each axis.  The tallest axis is assumed
    to be the "up" axis of the source application:
      dz largest → ZUP (no rotation)
      dy largest → YUP (rotate)
      dx largest → XUP (rotate)
    When spans are nearly equal (< 20% difference) the result defaults to ZUP.
    """

    # ── Vertex transforms ──────────────────────────────────────────────────

    @staticmethod
    def _rot_yup_to_zup(v: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Y-up → Z-up: X stays, Y↔Z with Z flip.  (x,y,z) → (x,-z,y)"""
        x, y, z = v
        return (x, -z, y)

    @staticmethod
    def _rot_xup_to_zup(v: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """X-up → Z-up: (x,y,z) → (-z, y, x)"""
        x, y, z = v
        return (-z, y, x)

    @staticmethod
    def _rot_normal_yup_to_zup(n: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Rotate a normal vector from Y-up to Z-up."""
        nx, ny, nz = n
        return (nx, -nz, ny)

    @staticmethod
    def _rot_normal_xup_to_zup(n: Tuple[float, float, float]) -> Tuple[float, float, float]:
        nx, ny, nz = n
        return (-nz, ny, nx)

    # ── Auto-detect ────────────────────────────────────────────────────────

    @staticmethod
    def detect(model: 'KotorModel') -> OrientationMode:
        """
        Inspect the model's bounding-box spans to guess its source up-axis.
        Returns the detected OrientationMode (ZUP / YUP / XUP).
        """
        model.compute_bounds()
        mn, mx = model.bb_min, model.bb_max
        dx = abs(mx[0] - mn[0])
        dy = abs(mx[1] - mn[1])
        dz = abs(mx[2] - mn[2])
        total = dx + dy + dz
        if total < 1e-6:
            return OrientationMode.ZUP  # degenerate model; no rotation
        # If the dominant axis is already Z: already Z-up
        if dz >= dx and dz >= dy:
            return OrientationMode.ZUP
        # If dominant axis is Y: Blender/Maya style
        if dy > dz and dy >= dx:
            return OrientationMode.YUP
        # Otherwise dominant axis is X
        return OrientationMode.XUP

    # ── Apply ──────────────────────────────────────────────────────────────

    @classmethod
    def apply(
        cls,
        model: 'KotorModel',
        mode: OrientationMode = OrientationMode.AUTO,
        floor_snap: bool = True,
        center_xz: bool = False,
    ) -> dict:
        """
        Rotate all mesh geometry in *model* in-place to match KotOR's Z-up
        coordinate system, then optionally snap the model to the floor (min Z = 0)
        and/or center it on the XZ plane.

        Parameters
        ----------
        model      : KotorModel  – the imported model (mutated in-place)
        mode       : OrientationMode  – AUTO / ZUP / YUP / XUP
        floor_snap : bool  – translate so the lowest vertex is at Z = 0
        center_xz  : bool  – translate so the model's XZ centroid is at (0, 0)

        Returns
        -------
        dict with keys:
          detected_mode : OrientationMode  – the mode actually used
          rotation_applied : bool          – True if axis rotation was performed
          floor_snap_applied : bool        – True if floor translation was applied
          translate : Tuple[float,float,float]  – net translation applied
          message : str
        """
        # ── 1. Determine actual mode ───────────────────────────────────────
        if mode == OrientationMode.AUTO:
            detected = cls.detect(model)
        else:
            detected = mode

        rotation_applied = (detected != OrientationMode.ZUP)

        # ── 2. Select vertex + normal transforms ──────────────────────────
        if detected == OrientationMode.YUP:
            v_fn = cls._rot_yup_to_zup
            n_fn = cls._rot_normal_yup_to_zup
        elif detected == OrientationMode.XUP:
            v_fn = cls._rot_xup_to_zup
            n_fn = cls._rot_normal_xup_to_zup
        else:
            v_fn = None
            n_fn = None

        # ── 3. Rotate all mesh-node vertices and normals ──────────────────
        all_nodes_list = list(model.all_nodes())
        for node in all_nodes_list:
            if not (node.is_mesh or node.is_skin):
                continue
            if not node.vertices:
                continue
            if v_fn is not None:
                node.vertices = [v_fn(v) for v in node.vertices]
                if node.normals:
                    node.normals = [n_fn(n) for n in node.normals]
            # Also rotate node position for any transformed geometry nodes
            if node.position and v_fn is not None:
                node.position = v_fn(node.position)

        # ── 4. Recompute bounds after rotation ────────────────────────────
        model.compute_bounds()
        mn, mx = model.bb_min, model.bb_max

        # ── 5. Floor snap  ────────────────────────────────────────────────
        tx, ty, tz = 0.0, 0.0, 0.0
        floor_applied = False
        if floor_snap and mn[2] != 0.0:
            tz = -mn[2]
            floor_applied = True

        # ── 6. Center on XZ  ──────────────────────────────────────────────
        if center_xz:
            cx = (mn[0] + mx[0]) * 0.5
            cy = (mn[1] + mx[1]) * 0.5
            tx = -cx
            ty = -cy

        # ── 7. Apply translation ──────────────────────────────────────────
        #
        # Imported OBJ/FBX geometry stores all vertex positions in world space
        # with node.position = (0,0,0).  KotorModel.compute_bounds() applies
        # world_transform() which accumulates node.position through the entire
        # parent chain and adds it to each vertex.  Therefore we must translate
        # ONLY the raw vertex arrays and leave every node.position untouched –
        # touching node.position would cause compute_bounds() to double-count
        # the translation and produce bounds offset by tx/ty/tz a second time.
        if tx != 0.0 or ty != 0.0 or tz != 0.0:
            for node in all_nodes_list:
                if not (node.is_mesh or node.is_skin):
                    continue
                if not node.vertices:
                    continue
                # Translate vertex positions only; never touch node.position.
                node.vertices = [
                    (v[0] + tx, v[1] + ty, v[2] + tz)
                    for v in node.vertices
                ]

        # ── 8. Final bounds recompute ─────────────────────────────────────
        model.compute_bounds()

        label_map = {
            OrientationMode.ZUP: "Z-up (no rotation)",
            OrientationMode.YUP: "Y-up → Z-up (Blender/Maya)",
            OrientationMode.XUP: "X-up → Z-up",
        }
        msg = (
            f"Orient: {label_map.get(detected, str(detected))}"
            + (f"  floor-snap Δz={tz:+.3f}" if floor_applied else "")
        )
        log.info(f"ModelOrientFixer.apply: {msg}")

        return {
            'detected_mode':    detected,
            'rotation_applied': rotation_applied,
            'floor_snap_applied': floor_applied,
            'translate':        (tx, ty, tz),
            'message':          msg,
        }

    # ── align_to_reference ─────────────────────────────────────────────────

    @classmethod
    def align_to_reference(
        cls,
        model: 'KotorModel',
        reference: 'KotorModel',
        match_floor: bool = True,
        center_xy: bool = True,
    ) -> dict:
        """
        Translate *model* so its origin and floor level match those of
        *reference* (a KotOR game model).

        KotOR reference characters sit with their feet at Z = 0 and their
        XY centroid at the scene origin (0, 0).  After this call the imported
        mesh will share the same coordinate frame as the reference, making
        subsequent bone-transfer and scaling operations spatially coherent.

        Parameters
        ----------
        model       : KotorModel – the imported working model (mutated in-place)
        reference   : KotorModel – the loaded game reference model
        match_floor : bool – snap model min-Z to match reference min-Z (≈ 0)
        center_xy   : bool – move model XY centroid to match reference centroid

        Returns
        -------
        dict with keys:
          translate      : (tx, ty, tz) applied
          ref_floor      : reference min-Z
          ref_cx, ref_cy : reference XY centroid
          message        : human-readable summary
        """
        model.compute_bounds()
        reference.compute_bounds()

        ref_mn = reference.bb_min
        ref_mx = reference.bb_max

        # Reference XY centroid and floor
        ref_cx = (ref_mn[0] + ref_mx[0]) * 0.5
        ref_cy = (ref_mn[1] + ref_mx[1]) * 0.5
        ref_floor = ref_mn[2]

        # Imported model current bounds
        imp_mn = model.bb_min
        imp_mx = model.bb_max
        imp_cx = (imp_mn[0] + imp_mx[0]) * 0.5
        imp_cy = (imp_mn[1] + imp_mx[1]) * 0.5
        imp_floor = imp_mn[2]

        tx = (ref_cx - imp_cx) if center_xy else 0.0
        ty = (ref_cy - imp_cy) if center_xy else 0.0
        tz = (ref_floor - imp_floor) if match_floor else 0.0

        # Apply translation to mesh vertex arrays only (never node.position –
        # see the comment in apply() for why).
        if tx != 0.0 or ty != 0.0 or tz != 0.0:
            for node in model.all_nodes():
                if not (node.is_mesh or node.is_skin):
                    continue
                if not node.vertices:
                    continue
                node.vertices = [
                    (v[0] + tx, v[1] + ty, v[2] + tz)
                    for v in node.vertices
                ]

        model.compute_bounds()

        parts = []
        if center_xy:
            parts.append(f"XY centred (Δx={tx:+.3f} Δy={ty:+.3f})")
        if match_floor:
            parts.append(f"floor matched (Δz={tz:+.3f})")
        msg = "Align to reference: " + ("  ".join(parts) if parts else "no change")
        log.info(f"ModelOrientFixer.align_to_reference: {msg}")

        return {
            'translate':  (tx, ty, tz),
            'ref_floor':  ref_floor,
            'ref_cx':     ref_cx,
            'ref_cy':     ref_cy,
            'message':    msg,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  ScaleMode  –  how to pick the reference dimension
# ─────────────────────────────────────────────────────────────────────────────

class ScaleMode(str, enum.Enum):
    HEIGHT = "HEIGHT"
    VOLUME = "VOLUME"
    MANUAL = "MANUAL"


# ─────────────────────────────────────────────────────────────────────────────
#  RetargetStage
# ─────────────────────────────────────────────────────────────────────────────

class RetargetStage(str, enum.Enum):
    EMPTY      = "EMPTY"
    IMPORTED   = "IMPORTED"
    REFERENCED = "REFERENCED"
    SCALED     = "SCALED"
    RIGGED     = "RIGGED"
    RIG_EDIT   = "RIG_EDIT"
    ANIM_READY = "ANIM_READY"


# ─────────────────────────────────────────────────────────────────────────────
#  RetargetState  –  snapshot bag (read-only view of the engine's state)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RetargetState:
    stage:              RetargetStage = RetargetStage.EMPTY
    import_name:        str           = ""
    import_height:      float         = 0.0
    import_mesh_count:  int           = 0
    ref_name:           str           = ""
    ref_height:         float         = 0.0
    ref_bone_count:     int           = 0
    ref_anim_count:     int           = 0
    scale_factor:       float         = 1.0
    bone_count:         int           = 0
    skin_node_count:    int           = 0
    anim_count:         int           = 0


# ─────────────────────────────────────────────────────────────────────────────
#  ScaleSolver  –  pure-math helper (no model mutations)
# ─────────────────────────────────────────────────────────────────────────────

class ScaleSolver:
    """Compute the scale factor needed to fit *src* bounds into *ref* bounds."""

    @staticmethod
    def span(bb_min: Tuple, bb_max: Tuple, mode: ScaleMode) -> float:
        dx = bb_max[0] - bb_min[0]
        dy = bb_max[1] - bb_min[1]
        dz = bb_max[2] - bb_min[2]
        if mode == ScaleMode.HEIGHT:
            return dz
        if mode == ScaleMode.VOLUME:
            return (max(0.0, dx) * max(0.0, dy) * max(0.0, dz)) ** (1.0 / 3.0)
        return dz  # fallback

    @classmethod
    def solve(
        cls,
        src_min: Tuple, src_max: Tuple,
        ref_min: Tuple, ref_max: Tuple,
        mode: ScaleMode = ScaleMode.HEIGHT,
        manual_factor: float = 1.0,
    ) -> float:
        if mode == ScaleMode.MANUAL:
            return max(1e-9, manual_factor)
        s_span = cls.span(src_min, src_max, mode)
        r_span = cls.span(ref_min, ref_max, mode)
        # Guard: degenerate source → no scale
        if s_span < 1e-6:
            return 1.0
        return r_span / max(s_span, 1e-9)


# ─────────────────────────────────────────────────────────────────────────────
#  MeshScaler  –  applies a uniform scale factor to every coordinate in a model
# ─────────────────────────────────────────────────────────────────────────────

class MeshScaler:
    """Apply a uniform scale to all node positions + vertex data in a KotorModel."""

    @staticmethod
    def apply(model: KotorModel, scale: float,
              src_floor: float = 0.0, dst_floor: float = 0.0) -> None:
        """
        Scale every vertex and node position uniformly.
        Shifts the model so that its floor (lowest Z) aligns with *dst_floor*
        after scaling.
        """
        has_floor_shift = abs(src_floor - dst_floor) > 1e-9
        if abs(scale - 1.0) < 1e-9 and not has_floor_shift:
            return

        visited: set = set()

        def _scale_node(n: ModelNode) -> None:
            nid = id(n)
            if nid in visited:
                return
            visited.add(nid)

            # Node's own position
            px, py, pz = n.position
            pz_adj = (pz - src_floor) * scale + dst_floor
            n.position = (px * scale, py * scale, pz_adj)

            # Vertex positions
            if n.vertices:
                new_v = []
                for vx, vy, vz in n.vertices:
                    new_v.append((
                        vx * scale,
                        vy * scale,
                        (vz - src_floor) * scale + dst_floor,
                    ))
                n.vertices = new_v

            for ch in n.children:
                _scale_node(ch)

        if model.root_node:
            _scale_node(model.root_node)

        model.compute_bounds()


# ─────────────────────────────────────────────────────────────────────────────
#  AnimationRetargeter  –  deep-copy + node-name remapping
# ─────────────────────────────────────────────────────────────────────────────

class AnimationRetargeter:
    """
    Copy animations from a *source* model into a *target* model.

    Node-key entries are filtered: only those whose name exists in the target
    model (or in the transferred bone set) are kept.
    """

    @staticmethod
    def transfer(
        target: KotorModel,
        source: KotorModel,
        keep_names: Optional[set] = None,
    ) -> int:
        """
        Deep-copy all animations from *source* into *target*.

        Returns the number of animations transferred.
        """
        target_names = {n.name for n in target.all_nodes()}
        if keep_names:
            target_names = target_names | keep_names

        copied = 0
        for src_anim in source.animations:
            anim = copy.deepcopy(src_anim)

            if hasattr(anim, 'node_keys') and anim.node_keys:
                filtered = {}
                for nname, keys in anim.node_keys.items():
                    if nname in target_names:
                        filtered[nname] = keys
                    else:
                        log.debug(
                            f"anim '{anim.name}': dropping keys for "
                            f"'{nname}' (not in target)"
                        )
                anim.node_keys = filtered

            target.animations.append(anim)
            copied += 1

        return copied


# ─────────────────────────────────────────────────────────────────────────────
#  RetargetEngine  –  the full stateful pipeline
# ─────────────────────────────────────────────────────────────────────────────

class RetargetEngine:
    """
    Stateful Import → Scale → Rig → Edit → Export pipeline.

    Every public method returns a dict with at minimum:
      { 'ok': bool, 'message': str, … }

    Progress is reported via the optional *progress_cb* callable:
      progress_cb(message: str, fraction: float)   (fraction in [0, 1])
    """

    def __init__(self, progress_cb: Optional[Callable] = None):
        self._progress_cb  = progress_cb or (lambda msg, pct: None)
        self._stage        = RetargetStage.EMPTY

        # Working model (deep-copy of the import, mutated in-place)
        self._working:   Optional[KotorModel] = None
        # Original import snapshot for cancel-rig-edit rollback
        self._import_snapshot: Optional[KotorModel] = None
        # Reference model (never mutated)
        self._reference: Optional[KotorModel] = None
        self._ref_name   = ""

        # Sub-components
        self._rigger    = AutoRigger()
        self._extractor = RigExtractor()
        self._scaler    = MeshScaler()
        self._retargeter = AnimationRetargeter()

        # Transferred bone nodes (name → ModelNode) for rig-edit
        self._bone_nodes: Dict[str, ModelNode] = {}

        # Snapshot of bone positions taken at begin_rig_edit for rollback
        self._bone_snapshot: Dict[str, Tuple] = {}

        # Accumulated scale factor (useful for UI display)
        self._cumulative_scale: float = 1.0

    # ── Properties ─────────────────────────────────────────────────────────

    @property
    def stage(self) -> RetargetStage:
        return self._stage

    @property
    def working_model(self) -> Optional[KotorModel]:
        return self._working

    @property
    def reference_model(self) -> Optional[KotorModel]:
        return self._reference

    def get_state(self) -> RetargetState:
        s = RetargetState(stage=self._stage)
        if self._working:
            s.import_name       = self._working.name
            s.import_height     = self._height(self._working)
            s.import_mesh_count = sum(
                1 for n in self._working.all_nodes()
                if n.is_mesh or n.is_skin
            )
        if self._reference:
            s.ref_name       = self._ref_name
            s.ref_height     = self._height(self._reference)
            s.ref_bone_count = self._bone_count(self._reference)
            s.ref_anim_count = len(self._reference.animations)
        s.scale_factor    = self._cumulative_scale
        s.bone_count      = len(self._bone_nodes)
        s.skin_node_count = (
            sum(1 for n in self._working.all_nodes()
                if n.is_skin and n.skin_data)
            if self._working else 0
        )
        s.anim_count = len(self._working.animations) if self._working else 0
        return s

    # ── Progress helper ─────────────────────────────────────────────────────

    def _progress(self, msg: str, pct: float) -> None:
        try:
            self._progress_cb(msg, pct)
        except Exception:
            pass

    # ── Utility ─────────────────────────────────────────────────────────────

    @staticmethod
    def _height(model: KotorModel) -> float:
        model.compute_bounds()
        return max(0.0, model.bb_max[2] - model.bb_min[2])

    @staticmethod
    def _bone_count(model: KotorModel) -> int:
        return sum(
            1 for n in model.all_nodes()
            if n.is_dummy or (n.flags & int(NodeFlags.HEADER))
        )

    @staticmethod
    def _mesh_count(model: KotorModel) -> int:
        return sum(1 for n in model.all_nodes() if n.is_mesh or n.is_skin)

    # ── Step 1 : set_imported_model ─────────────────────────────────────────

    def set_imported_model(self, model: KotorModel) -> dict:
        """
        Accept the model to be retargeted.

        The engine keeps a *working copy* so the caller's model is never
        mutated.

        Returns dict: ok, message, mesh_count, height, name.
        """
        if model is None:
            return {'ok': False, 'message': "No model provided."}

        self._working          = copy.deepcopy(model)
        self._import_snapshot  = None   # reset; snapshot is made before rig edit
        self._bone_nodes.clear()
        self._cumulative_scale = 1.0
        self._working.compute_bounds()

        n_mesh   = self._mesh_count(self._working)
        height   = self._height(self._working)
        name     = self._working.name or "imported"

        if n_mesh == 0:
            self._stage = RetargetStage.EMPTY
            return {
                'ok':         False,
                'message':    f"'{name}' has no mesh nodes – cannot retarget.",
                'mesh_count': 0,
                'height':     height,
                'name':       name,
            }

        self._stage = RetargetStage.IMPORTED
        msg = f"Imported '{name}'  ({n_mesh} mesh nodes,  height={height:.3f})"
        log.info(msg)
        self._progress(msg, 0.1)
        return {
            'ok':         True,
            'message':    msg,
            'mesh_count': n_mesh,
            'height':     height,
            'name':       name,
        }

    # ── Step 1b : orient_model ──────────────────────────────────────────────

    def orient_model(
        self,
        mode: 'OrientationMode' = OrientationMode.AUTO,
        floor_snap: bool = True,
        center_xz: bool = False,
    ) -> dict:
        """
        Rotate and translate the working model so it is correctly aligned with
        KotOR's Z-up coordinate system (X=right, Y=forward, Z=up).

        Must be called after set_imported_model() and before auto_scale().
        Calling it again re-applies orientation from the current working state.

        Parameters
        ----------
        mode       : OrientationMode – AUTO / ZUP / YUP / XUP.
                     AUTO uses bounding-box span detection.
        floor_snap : bool – move the model so its lowest vertex is at Z = 0.
        center_xz  : bool – center the model's X/Y footprint on the origin.

        Returns dict: ok, message, detected_mode, rotation_applied,
                      height_before, height_after.
        """
        if self._working is None:
            return {'ok': False, 'message': "No model imported yet."}

        height_before = self._height(self._working)

        result = ModelOrientFixer.apply(
            self._working,
            mode=mode,
            floor_snap=floor_snap,
            center_xz=center_xz,
        )

        # Invalidate cached bounds
        self._working.compute_bounds()
        height_after = self._height(self._working)

        msg = (
            f"Orient → {result['message']}  "
            f"h: {height_before:.3f} → {height_after:.3f}"
        )
        log.info(msg)
        self._progress(msg, 0.15)

        return {
            'ok':              True,
            'message':         msg,
            'detected_mode':   result['detected_mode'],
            'rotation_applied': result['rotation_applied'],
            'floor_snap_applied': result['floor_snap_applied'],
            'height_before':   height_before,
            'height_after':    height_after,
        }

    # ── Step 1b-extra : rotate_90 ───────────────────────────────────────────

    def rotate_90(self, axis: str = 'Z', direction: int = 1) -> dict:
        """
        Rotate the working model by 90 degrees around the specified axis.

        This is a fine-tune control for when auto-orient gets the yaw/facing
        direction wrong.  For example, a character imported from Blender may
        be correctly Z-up but facing the wrong horizontal direction (+X instead
        of +Y).  Clicking "Rotate 90°" fixes the yaw without re-running the
        full auto-detect pipeline.

        Parameters
        ----------
        axis      : str  – 'X', 'Y', or 'Z' (case-insensitive)
        direction : int  – +1 = counter-clockwise (positive rotation),
                           -1 = clockwise (negative rotation)

        Returns dict: ok, message, height_after
        """
        if self._working is None:
            return {'ok': False, 'message': "No model imported yet."}

        axis = axis.upper().strip()
        if axis not in ('X', 'Y', 'Z'):
            return {'ok': False, 'message': f"Unknown axis '{axis}' – use X, Y, or Z."}
        d = 1 if direction >= 0 else -1

        # Vertex rotation functions for each axis × direction
        # Positive (CCW viewed from +axis):
        #   Z: (x,y,z) → (-y,  x,  z)
        #   Y: (x,y,z) → ( z,  y, -x)
        #   X: (x,y,z) → ( x, -z,  y)
        # Negative (CW) = inverse of above:
        #   Z: (x,y,z) → ( y, -x,  z)
        #   Y: (x,y,z) → (-z,  y,  x)
        #   X: (x,y,z) → ( x,  z, -y)
        _ROT: dict = {
            ('Z', +1): lambda x, y, z: (-y,  x,  z),
            ('Z', -1): lambda x, y, z: ( y, -x,  z),
            ('Y', +1): lambda x, y, z: ( z,  y, -x),
            ('Y', -1): lambda x, y, z: (-z,  y,  x),
            ('X', +1): lambda x, y, z: ( x, -z,  y),
            ('X', -1): lambda x, y, z: ( x,  z, -y),
        }
        v_fn = _ROT[(axis, d)]
        # Normal transform = same rotation as vertex
        n_fn = v_fn

        for node in self._working.all_nodes():
            if not (node.is_mesh or node.is_skin):
                continue
            if node.vertices:
                node.vertices = [v_fn(*v) for v in node.vertices]
            if getattr(node, 'normals', None):
                node.normals = [n_fn(*n) for n in node.normals]
            if getattr(node, 'position', None) and node.position != (0.0, 0.0, 0.0):
                node.position = v_fn(*node.position)

        self._working.compute_bounds()
        height_after = self._height(self._working)
        dir_label = 'CCW' if d > 0 else 'CW'
        msg = f"Rotated 90° {dir_label} around {axis}-axis  h={height_after:.3f}"
        log.info(f"RetargetEngine.rotate_90: {msg}")
        return {'ok': True, 'message': msg, 'height_after': height_after}

    # ── Step 1c : align_to_reference ────────────────────────────────────────

    def align_to_reference(
        self,
        match_floor: bool = True,
        center_xy:   bool = True,
    ) -> dict:
        """
        Translate the working model so its pivot / floor level aligns with the
        loaded reference model's coordinate frame.

        KotOR reference characters live at the scene origin (XY centroid ≈ 0,
        feet at Z = 0).  Calling this after orient_model() ensures the imported
        mesh occupies the same coordinate frame as the reference before scaling
        and rig-transfer take place.

        Must be called after set_imported_model() (stage ≥ IMPORTED) and after
        set_reference_model() so a reference is available.

        Parameters
        ----------
        match_floor : bool – snap the imported model's floor (min-Z) to match
                             the reference floor (usually 0).
        center_xy   : bool – translate the imported model's XY centroid to
                             match the reference centroid (usually (0, 0)).

        Returns dict: ok, message, translate, height_before, height_after.
        """
        if self._working is None:
            return {'ok': False, 'message': "No model imported yet."}
        if self._reference is None:
            return {'ok': False,
                    'message': "No reference model loaded. Load a reference first."}

        height_before = self._height(self._working)

        result = ModelOrientFixer.align_to_reference(
            self._working,
            self._reference,
            match_floor=match_floor,
            center_xy=center_xy,
        )

        self._working.compute_bounds()
        height_after = self._height(self._working)

        tx, ty, tz = result['translate']
        msg = (
            f"Align → {result['message']}  h={height_after:.3f}"
        )
        log.info(msg)
        self._progress(msg, 0.18)

        return {
            'ok':           True,
            'message':      msg,
            'translate':    (tx, ty, tz),
            'height_before': height_before,
            'height_after':  height_after,
        }

    # ── Step 2 : set_reference_model ────────────────────────────────────────

    def set_reference_model(
        self,
        model: KotorModel,
        ref_name: str = "",
    ) -> dict:
        """
        Set the game model that provides the skeleton and animations.

        Returns dict: ok, message, height, bone_count, anim_count.
        """
        if model is None:
            return {'ok': False, 'message': "No reference model provided."}

        self._reference = model
        self._ref_name  = ref_name or model.name or "reference"
        model.compute_bounds()

        height      = self._height(model)
        bone_count  = self._bone_count(model)
        anim_count  = len(model.animations)

        if self._stage in (RetargetStage.EMPTY,):
            # No import yet — store reference but don't advance
            pass
        elif self._stage.value >= RetargetStage.IMPORTED.value:
            self._stage = RetargetStage.REFERENCED

        msg = (
            f"Reference: '{self._ref_name}'  "
            f"h={height:.3f}  bones={bone_count}  anims={anim_count}"
        )
        log.info(msg)
        self._progress(msg, 0.2)
        return {
            'ok':         True,
            'message':    msg,
            'height':     height,
            'bone_count': bone_count,
            'anim_count': anim_count,
        }

    # ── Step 3 : auto_scale ─────────────────────────────────────────────────

    def auto_scale(
        self,
        mode: ScaleMode = ScaleMode.HEIGHT,
        manual_factor: float = 1.0,
    ) -> dict:
        """
        Scale the working model to match the reference model's bounding-box.

        Returns dict: ok, message, scale_factor, src_height, new_height.
        """
        if self._working is None:
            return {'ok': False, 'message': "No model imported yet."}
        if self._reference is None and mode != ScaleMode.MANUAL:
            return {'ok': False, 'message': "No reference model loaded."}

        self._working.compute_bounds()
        src_min = self._working.bb_min
        src_max = self._working.bb_max
        src_height = max(0.0, src_max[2] - src_min[2])

        if self._reference:
            self._reference.compute_bounds()
            ref_min = self._reference.bb_min
            ref_max = self._reference.bb_max
        else:
            ref_min = ref_max = ((0,0,0), (0,0,0))

        scale = ScaleSolver.solve(
            src_min, src_max,
            ref_min, ref_max,
            mode=mode,
            manual_factor=manual_factor,
        )

        if abs(scale - 1.0) > 1e-9:
            MeshScaler.apply(
                self._working, scale,
                src_floor=src_min[2],
                dst_floor=ref_min[2] if self._reference else 0.0,
            )
        self._cumulative_scale *= scale
        self._working.compute_bounds()
        new_height = self._height(self._working)

        if self._stage.value >= RetargetStage.REFERENCED.value:
            self._stage = RetargetStage.SCALED

        msg = (
            f"Scaled ×{scale:.4f}  "
            f"({src_height:.3f} → {new_height:.3f},  mode={mode.value})"
        )
        log.info(msg)
        self._progress(msg, 0.4)
        return {
            'ok':          True,
            'message':     msg,
            'scale_factor': scale,
            'src_height':  src_height,
            'new_height':  new_height,
        }

    # ── Step 4 : transfer_rig ───────────────────────────────────────────────

    def transfer_rig(
        self,
        scale_to_target: bool = True,
        smooth_weights:  bool = True,
    ) -> dict:
        """
        Extract the rig from the reference model and apply it to the working model.

        Returns dict: ok, message, bone_count, skin_node_count.
        """
        if self._working is None:
            return {'ok': False, 'message': "No model imported yet."}
        if self._reference is None:
            return {'ok': False, 'message': "No reference model loaded."}

        self._progress("Extracting rig template…", 0.45)

        try:
            template = self._extractor.extract(self._reference)
        except Exception as exc:
            log.error(f"RigExtractor.extract failed: {exc}")
            return {'ok': False, 'message': f"Rig extraction failed: {exc}"}

        self._progress("Applying rig to mesh…", 0.55)

        try:
            self._rigger.rig_from_template(
                self._working, template,
                scale_to_target=scale_to_target,
            )
        except Exception as exc:
            log.error(f"rig_from_template failed: {exc}")
            return {'ok': False, 'message': f"Rig transfer failed: {exc}"}

        # Collect transferred bone nodes
        self._bone_nodes.clear()
        if self._working.root_node:
            for n in self._working.all_nodes():
                if n.name in template.bones:
                    self._bone_nodes[n.name] = n

        bone_count     = len(self._bone_nodes)
        skin_node_count = sum(
            1 for n in self._working.all_nodes()
            if n.is_skin and n.skin_data
        )

        # Mirror supermodel meta
        self._working.supermodel    = self._reference.supermodel
        self._working.game_version  = self._reference.game_version
        self._working.classification = self._reference.classification

        self._stage = RetargetStage.RIGGED

        msg = (
            f"Rig transferred: {bone_count} bones, "
            f"{skin_node_count} skin nodes"
        )
        log.info(msg)
        self._progress(msg, 0.7)
        return {
            'ok':             True,
            'message':        msg,
            'bone_count':     bone_count,
            'skin_node_count': skin_node_count,
        }

    # ── Step 5a : begin_rig_edit ─────────────────────────────────────────────

    def begin_rig_edit(self) -> dict:
        """
        Enter rig-edit mode.  Snapshots current bone positions for rollback.

        Returns dict: ok, message.
        """
        if self._working is None:
            return {'ok': False, 'message': "No model to edit."}
        if self._stage not in (RetargetStage.RIGGED,
                               RetargetStage.ANIM_READY,
                               RetargetStage.SCALED):
            # Allow entering edit from any stage that has a working model
            if self._working is None:
                return {'ok': False, 'message': "Complete rig transfer first."}

        # Snapshot bone positions for cancel
        self._bone_snapshot = {
            name: node.position
            for name, node in self._bone_nodes.items()
        }
        # Snapshot the entire working model for deep rollback
        self._import_snapshot = copy.deepcopy(self._working)

        self._stage = RetargetStage.RIG_EDIT
        msg = (
            f"Rig-edit mode active — {len(self._bone_nodes)} bones available. "
            f"Drag bones in the viewport, then click Confirm Rig."
        )
        log.info(msg)
        return {'ok': True, 'message': msg}

    # ── Step 5b : move_bone ─────────────────────────────────────────────────

    def move_bone(self, bone_name: str, new_pos: Tuple) -> dict:
        """
        Update a bone's position after a viewport gizmo drag.

        Returns dict: ok, message.
        """
        if self._stage != RetargetStage.RIG_EDIT:
            return {'ok': False, 'message': "Not in rig-edit mode."}
        node = self._bone_nodes.get(bone_name)
        if node is None:
            # Try searching the working model directly
            if self._working:
                for n in self._working.all_nodes():
                    if n.name == bone_name:
                        node = n
                        self._bone_nodes[bone_name] = n
                        break
        if node is None:
            return {'ok': False,
                    'message': f"Bone '{bone_name}' not found."}

        node.position = tuple(new_pos[:3])
        return {'ok': True, 'message': f"Bone '{bone_name}' moved."}

    # ── Step 5c : confirm_rig_edit ──────────────────────────────────────────

    def confirm_rig_edit(self, recompute_weights: bool = True) -> dict:
        """
        Anchor the current bone positions.

        If *recompute_weights* is True, re-skin all mesh nodes using the
        updated bone world positions (heat-map proximity).

        Returns dict: ok, message.
        """
        if self._working is None:
            return {'ok': False, 'message': "No working model."}

        self._stage = RetargetStage.RIGGED
        self._import_snapshot = None  # discard rollback snapshot

        n_reskinned = 0
        if recompute_weights and self._bone_nodes:
            try:
                rigger = AutoRigger()
                rigger._compute_world_positions(self._bone_nodes)
                rigger._bone_name_list = list(self._bone_nodes.keys())
                rigger._model_bb_min   = self._working.bb_min
                rigger._model_bb_max   = self._working.bb_max

                for node in self._working.all_nodes():
                    if (node.is_mesh or node.is_skin) and node.vertices:
                        rigger._skin_node(node, self._bone_nodes,
                                          rigger._bone_name_list)
                        n_reskinned += 1
            except Exception as exc:
                log.warning(f"confirm_rig_edit: weight recompute failed: {exc}")

        self._bone_snapshot.clear()

        msg = (
            f"Rig confirmed. "
            + (f"Re-skinned {n_reskinned} mesh nodes." if recompute_weights
               else "Weights unchanged.")
        )
        log.info(msg)
        return {'ok': True, 'message': msg}

    # ── Step 5d : cancel_rig_edit ───────────────────────────────────────────

    def cancel_rig_edit(self) -> dict:
        """
        Revert to the state before rig-edit mode was entered.

        Returns dict: ok, message.
        """
        if self._bone_snapshot:
            for name, pos in self._bone_snapshot.items():
                node = self._bone_nodes.get(name)
                if node:
                    node.position = pos
            self._bone_snapshot.clear()

        if self._import_snapshot is not None:
            self._working         = self._import_snapshot
            self._import_snapshot = None
            # Re-collect bone nodes from the restored model
            self._bone_nodes.clear()
            if self._working.root_node:
                for n in self._working.all_nodes():
                    if n.is_dummy or n.name in {bn for bn in self._bone_nodes}:
                        self._bone_nodes[n.name] = n

        self._stage = RetargetStage.RIGGED
        msg = "Rig edit cancelled — bone positions restored."
        log.info(msg)
        return {'ok': True, 'message': msg}

    # ── Step 6 : transfer_animations ────────────────────────────────────────

    def transfer_animations(self) -> dict:
        """
        Deep-copy all animations from the reference model into the working model.

        Returns dict: ok, message, anim_count.
        """
        if self._working is None:
            return {'ok': False, 'message': "No model imported yet."}
        if self._reference is None:
            return {'ok': False, 'message': "No reference model loaded."}

        # Clear existing animations first (avoid duplicates on repeat calls)
        self._working.animations.clear()

        keep_names = set(self._bone_nodes.keys())
        n = AnimationRetargeter.transfer(
            self._working, self._reference, keep_names=keep_names
        )

        self._stage = RetargetStage.ANIM_READY

        msg = f"Transferred {n} animation(s) from '{self._ref_name}'."
        log.info(msg)
        self._progress(msg, 0.9)
        return {'ok': True, 'message': msg, 'anim_count': n}

    # ── Utility: reset ──────────────────────────────────────────────────────

    def reset(self) -> None:
        """Reset the engine to the EMPTY state."""
        self._stage            = RetargetStage.EMPTY
        self._working          = None
        self._import_snapshot  = None
        self._reference        = None
        self._ref_name         = ""
        self._bone_nodes.clear()
        self._bone_snapshot.clear()
        self._cumulative_scale = 1.0
        log.info("RetargetEngine reset.")

    # ── bake_rig_edit ─────────────────────────────────────────────────────────

    def bake_rig_edit(self, model: Optional['KotorModel'] = None) -> int:
        """
        Re-skin all mesh/skin nodes using the current bone world positions.

        This is called by ViewportWidget.confirm_rig_edit() after the user has
        finished dragging bones in the viewport.

        Parameters
        ----------
        model:
            The KotorModel to re-skin.  Defaults to the working model.
            (The viewport passes its own copy of the model here.)

        Returns the number of mesh nodes that were re-skinned.
        """
        target = model if model is not None else self._working
        if target is None:
            log.warning("bake_rig_edit: no model to bake.")
            return 0
        if not self._bone_nodes:
            # Try to rebuild bone_nodes from the model
            for n in target.all_nodes():
                if n.is_dummy or (n.flags & 0x08):   # NodeFlags.HEADER
                    self._bone_nodes[n.name] = n

        if not self._bone_nodes:
            log.warning("bake_rig_edit: no bone nodes found – skipping re-skin.")
            return 0

        n_reskinned = 0
        try:
            rigger = AutoRigger()
            rigger._compute_world_positions(self._bone_nodes)
            rigger._bone_name_list = list(self._bone_nodes.keys())
            target.compute_bounds()
            rigger._model_bb_min = target.bb_min
            rigger._model_bb_max = target.bb_max

            for node in target.all_nodes():
                if (node.is_mesh or node.is_skin) and node.vertices:
                    rigger._skin_node(node, self._bone_nodes,
                                      rigger._bone_name_list)
                    n_reskinned += 1
        except Exception as exc:
            log.warning(f"bake_rig_edit: re-skin failed: {exc}")

        if n_reskinned:
            log.info(f"bake_rig_edit: re-skinned {n_reskinned} mesh nodes.")
        return n_reskinned

    # ── export_mdl ────────────────────────────────────────────────────────────

    def export_mdl(
        self,
        mdl_path: str,
        mdx_path: str = "",
        game_version: str = "",
        model_name: str = "",
    ) -> dict:
        """
        Write the working model to a KotOR binary MDL + MDX pair.

        Parameters
        ----------
        mdl_path     : destination .mdl path
        mdx_path     : destination .mdx path (auto-derived if empty)
        game_version : 'K1' or 'K2' — overrides the model's stored version
        model_name   : rename the model node before writing (empty = keep)

        Returns dict: ok, message, mdl_path, mdx_path.
        """
        import os
        from pathlib import Path as _P

        if self._working is None:
            return {'ok': False, 'message': "No working model to export."}

        if not mdx_path:
            mdx_path = str(_P(mdl_path).with_suffix('.mdx'))

        # Apply overrides on a deep-copy so we don't mutate the working model
        model = copy.deepcopy(self._working)

        if model_name:
            model.name = model_name
            if model.root_node:
                model.root_node.name = model_name

        if game_version:
            try:
                gv_map = {'K1': GameVersion.K1, 'K2': GameVersion.K2}
                if game_version.upper() in gv_map:
                    model.game_version = gv_map[game_version.upper()]
            except Exception:
                pass

        ok = export_as_mdl(model, mdl_path, mdx_path)
        if ok:
            msg = (
                f"Exported '{model.name}' → {_P(mdl_path).name}"
                f" + {_P(mdx_path).name}"
            )
            log.info(msg)
            return {'ok': True, 'message': msg,
                    'mdl_path': mdl_path, 'mdx_path': mdx_path}
        else:
            msg = f"Binary MDL export failed for '{_P(mdl_path).name}'."
            log.error(msg)
            return {'ok': False, 'message': msg}

    # ── Convenience: full pipeline in one call ──────────────────────────────

    def retarget(
        self,
        target: KotorModel,
        reference: KotorModel,
        scale_mode: ScaleMode = ScaleMode.HEIGHT,
    ) -> Tuple[dict, dict, dict]:
        """
        Run import → scale → rig-transfer in one call.

        Returns (import_result, scale_result, rig_result).
        """
        r_import = self.set_imported_model(target)
        r_ref    = self.set_reference_model(reference)
        r_scale  = self.auto_scale(mode=scale_mode)
        r_rig    = self.transfer_rig()
        return r_import, r_scale, r_rig


# ─────────────────────────────────────────────────────────────────────────────
#  Convenience export wrapper  (imported directly from GUI)
# ─────────────────────────────────────────────────────────────────────────────

def export_as_mdl(model: KotorModel, mdl_path: str, mdx_path: str = "") -> bool:
    """
    Write *model* to a KotOR binary MDL+MDX pair.

    Tries mdl_porter first (battle-tested binary writer), then falls back
    to mdl_writer.  Supports both relative-import (package) and sys.path
    (direct test / standalone) contexts.

    Returns True on success.
    """
    import os
    import importlib
    if not mdx_path:
        mdx_path = os.path.splitext(mdl_path)[0] + ".mdx"

    err_porter = None
    err_writer = None

    # ── Porter path ─────────────────────────────────────────────────────────
    for mod_name in ("src.core.mdl.mdl_porter", "core.mdl.mdl_porter"):
        try:
            _mod = importlib.import_module(mod_name)
            _mod.MDLBinaryWriter().write(model, mdl_path, mdx_path)
            log.info(f"export_as_mdl: wrote {mdl_path!r} via {mod_name}")
            return True
        except ModuleNotFoundError:
            continue
        except Exception as exc:
            err_porter = exc
            log.warning(f"export_as_mdl: mdl_porter ({mod_name}) failed ({exc}), trying mdl_writer…")
            break

    # ── mdl_writer fallback ──────────────────────────────────────────────────
    for mod_name in ("src.core.mdl.mdl_writer", "core.mdl.mdl_writer"):
        try:
            _mod = importlib.import_module(mod_name)
            _mod.MDLWriter().write_files(model, mdl_path)
            log.info(f"export_as_mdl: wrote {mdl_path!r} via {mod_name}")
            return True
        except ModuleNotFoundError:
            continue
        except Exception as exc:
            err_writer = exc
            log.error(
                f"export_as_mdl: both writers failed. "
                f"Porter: {err_porter}  Writer: {err_writer}"
            )
            return False

    log.error(
        f"export_as_mdl: no writer module found. "
        f"Porter: {err_porter}  Writer: {err_writer}"
    )
    return False
