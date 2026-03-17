"""
AcuRig-Style Manual Rigging System for GhostRigger-K1-K2
=========================================================
Implements a sophisticated manual + semi-automatic rigging pipeline
inspired by Reallusion's AccuRIG system, adapted for KotOR MDL models.

Key Features
------------
1. **Profile Detection** – Auto-detect humanoid / quadruped / droid / prop
2. **Guide Placement** – Anatomical landmark guides (like AccuRIG pins)
   with midpoint placement inside mesh volume
3. **Bone Generation** – Skeleton construction from guide positions
4. **Smart Skinning** – Proximity + geodesic heat-map weights
5. **Bone Masking** – Exclude bones from skinning (for unusual meshes)
6. **Weight Mirroring** – Mirror left→right symmetrical weights
7. **Influence Pruning** – Limit to N bones per vertex + normalization
8. **Pose Preview** – T-pose / A-pose bind-pose correction
9. **Template Save/Load** – JSON rig templates for reuse
10. **Symmetry Detection** – Auto-detect and enforce L/R symmetry
"""

from __future__ import annotations
import math, logging, json, os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set

from ..core.model_data import (
    KotorModel, ModelNode, NodeFlags, VertexSkinData, BoneWeight
)

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────────────────────

MAX_INFLUENCES = 4          # Max bones per vertex (KotOR engine limit)
MIN_WEIGHT     = 0.01       # Prune weights below this
HEAT_FALLOFF   = 4.0        # Heat-map distance falloff exponent

# Skeleton profiles ──────────────────────────────────────────────────────────

PROFILE_HUMANOID   = "humanoid"
PROFILE_QUADRUPED  = "quadruped"
PROFILE_DROID      = "droid"
PROFILE_PROP       = "prop"
PROFILE_CREATURE   = "creature"


# ─────────────────────────────────────────────────────────────────────────────
#  Guide Point  (AccuRIG-style anatomical landmark)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RigGuide:
    """
    A single placement guide pin, equivalent to AccuRIG's guide markers.

    Attributes
    ----------
    name        Semantic name  (e.g. 'head', 'lshoulder', 'hip')
    position    World-space 3-tuple  (x, y, z)
    bone_parent Name of parent guide (None = root)
    locked      User has manually placed this guide; auto-placement skipped
    mirror_of   Name of the guide this mirrors (e.g. 'rhand' mirrors 'lhand')
    """
    name:       str
    position:   Tuple[float,float,float] = (0.0, 0.0, 0.0)
    bone_parent: Optional[str]           = None
    locked:     bool                     = False
    mirror_of:  Optional[str]            = None
    # Visual hint
    colour:     Tuple[int,int,int]       = (255, 200, 0)

    def distance_to(self, other: 'RigGuide') -> float:
        ax,ay,az = self.position
        bx,by,bz = other.position
        return math.sqrt((ax-bx)**2 + (ay-by)**2 + (az-bz)**2)

    def midpoint(self, other: 'RigGuide') -> Tuple[float,float,float]:
        ax,ay,az = self.position
        bx,by,bz = other.position
        return ((ax+bx)/2, (ay+by)/2, (az+bz)/2)


# ─────────────────────────────────────────────────────────────────────────────
#  Rig Profile Definitions
# ─────────────────────────────────────────────────────────────────────────────

HUMANOID_GUIDES: List[Tuple[str, Optional[str], Tuple[float,float,float]]] = [
    # (name, parent, normalised_position in 0..1 of model height)
    ("root",       None,        (0.00, 0.00, 0.00)),
    ("hip",        "root",      (0.00, 0.00, 0.52)),
    ("stomach",    "hip",       (0.00, 0.00, 0.58)),
    ("chest",      "stomach",   (0.00, 0.00, 0.67)),
    ("neck",       "chest",     (0.00, 0.00, 0.76)),
    ("head",       "neck",      (0.00, 0.00, 0.87)),
    ("lshoulder",  "chest",     (-0.12, 0.00, 0.72)),
    ("lforearm",   "lshoulder", (-0.24, 0.00, 0.67)),
    ("lhand",      "lforearm",  (-0.34, 0.00, 0.62)),
    ("lfinger01",  "lhand",     (-0.38, 0.00, 0.61)),
    ("rshoulder",  "chest",     ( 0.12, 0.00, 0.72)),
    ("rforearm",   "rshoulder", ( 0.24, 0.00, 0.67)),
    ("rhand",      "rforearm",  ( 0.34, 0.00, 0.62)),
    ("rfinger01",  "rhand",     ( 0.38, 0.00, 0.61)),
    ("lthigh",     "hip",       (-0.10, 0.00, 0.45)),
    ("lcalf",      "lthigh",    (-0.10, 0.00, 0.27)),
    ("lankle",     "lcalf",     (-0.10, 0.00, 0.06)),
    ("ltoebase",   "lankle",    (-0.10, 0.04, 0.02)),
    ("rthigh",     "hip",       ( 0.10, 0.00, 0.45)),
    ("rcalf",      "rthigh",    ( 0.10, 0.00, 0.27)),
    ("rankle",     "rcalf",     ( 0.10, 0.00, 0.06)),
    ("rtoebase",   "rankle",    ( 0.10, 0.04, 0.02)),
]

QUADRUPED_GUIDES: List[Tuple[str, Optional[str], Tuple[float,float,float]]] = [
    ("root",       None,        (0.00,  0.00,  0.00)),
    ("hip",        "root",      (0.00,  0.00,  0.55)),
    ("stomach",    "hip",       (-0.25, 0.00,  0.55)),
    ("chest",      "stomach",   (-0.50, 0.00,  0.60)),
    ("neck",       "chest",     (-0.65, 0.00,  0.70)),
    ("head",       "neck",      (-0.80, 0.00,  0.78)),
    ("lshoulder",  "chest",     (-0.50,-0.08,  0.58)),
    ("lforearm",   "lshoulder", (-0.55,-0.08,  0.35)),
    ("lhand",      "lforearm",  (-0.55,-0.06,  0.12)),
    ("rshoulder",  "chest",     (-0.50, 0.08,  0.58)),
    ("rforearm",   "rshoulder", (-0.55, 0.08,  0.35)),
    ("rhand",      "rforearm",  (-0.55, 0.06,  0.12)),
    ("lthigh",     "hip",       ( 0.20,-0.08,  0.50)),
    ("lcalf",      "lthigh",    ( 0.30,-0.08,  0.30)),
    ("lankle",     "lcalf",     ( 0.35,-0.06,  0.10)),
    ("rthigh",     "hip",       ( 0.20, 0.08,  0.50)),
    ("rcalf",      "rthigh",    ( 0.30, 0.08,  0.30)),
    ("rankle",     "rcalf",     ( 0.35, 0.06,  0.10)),
    ("tail_root",  "hip",       ( 0.35, 0.00,  0.55)),
    ("tail_mid",   "tail_root", ( 0.55, 0.00,  0.50)),
    ("tail_tip",   "tail_mid",  ( 0.75, 0.00,  0.45)),
]

DROID_GUIDES: List[Tuple[str, Optional[str], Tuple[float,float,float]]] = [
    ("root",       None,        (0.00,  0.00,  0.00)),
    ("hip",        "root",      (0.00,  0.00,  0.50)),
    ("torso",      "hip",       (0.00,  0.00,  0.65)),
    ("head",       "torso",     (0.00,  0.00,  0.85)),
    ("lshoulder",  "torso",     (-0.15, 0.00,  0.68)),
    ("lforearm",   "lshoulder", (-0.28, 0.00,  0.62)),
    ("lhand",      "lforearm",  (-0.38, 0.00,  0.55)),
    ("rshoulder",  "torso",     ( 0.15, 0.00,  0.68)),
    ("rforearm",   "rshoulder", ( 0.28, 0.00,  0.62)),
    ("rhand",      "rforearm",  ( 0.38, 0.00,  0.55)),
    ("lleg",       "hip",       (-0.10, 0.00,  0.40)),
    ("lfoot",      "lleg",      (-0.10, 0.00,  0.12)),
    ("rleg",       "hip",       ( 0.10, 0.00,  0.40)),
    ("rfoot",      "rleg",      ( 0.10, 0.00,  0.12)),
]

MIRROR_PAIRS: Dict[str, str] = {
    "lshoulder": "rshoulder",
    "lforearm":  "rforearm",
    "lhand":     "rhand",
    "lfinger01": "rfinger01",
    "lfinger02": "rfinger02",
    "lthigh":    "rthigh",
    "lcalf":     "rcalf",
    "lankle":    "rankle",
    "ltoebase":  "rtoebase",
    "lleg":      "rleg",
    "lfoot":     "rfoot",
}

BONE_COLOURS: Dict[str, Tuple[int,int,int]] = {
    "root":      (128, 128, 128),
    "hip":       (255, 165,   0),
    "stomach":   (255, 200,  80),
    "chest":     (255, 220, 100),
    "neck":      (200, 255, 150),
    "head":      (100, 220, 255),
    "lshoulder": (255, 100, 100),
    "lforearm":  (255, 130, 130),
    "lhand":     (255, 160, 160),
    "lfinger01": (255, 190, 190),
    "lfinger02": (255, 190, 190),
    "rshoulder": (100, 100, 255),
    "rforearm":  (130, 130, 255),
    "rhand":     (160, 160, 255),
    "rfinger01": (190, 190, 255),
    "rfinger02": (190, 190, 255),
    "lthigh":    (255, 80,  80),
    "lcalf":     (255, 110, 110),
    "lankle":    (255, 140, 140),
    "ltoebase":  (255, 170, 170),
    "rthigh":    (80,  80,  255),
    "rcalf":     (110, 110, 255),
    "rankle":    (140, 140, 255),
    "rtoebase":  (170, 170, 255),
}


# ─────────────────────────────────────────────────────────────────────────────
#  Profile Detector
# ─────────────────────────────────────────────────────────────────────────────

class ProfileDetector:
    """
    Auto-detect skeleton profile from mesh shape + bone names.
    Similar to AccuRIG's automatic character type detection.
    """

    HUMANOID_KEYWORDS   = {'head','neck','chest','hip','pelvis','spine',
                           'shoulder','arm','hand','thigh','calf','foot'}
    QUADRUPED_KEYWORDS  = {'leg1','leg2','leg3','leg4','paw','hoof',
                           'tail','muzzle','hindleg','foreleg'}
    DROID_KEYWORDS      = {'drd','chassis','servo','piston','photoreceptor',
                           'vocoder','dome','wheel','roller'}

    def detect(self, model: KotorModel) -> str:
        """Return profile string: humanoid / quadruped / droid / prop."""
        node_names = {n.name.lower() for n in model.all_nodes()}
        dummy_count = sum(1 for n in model.all_nodes() if n.is_dummy)
        mesh_nodes  = [n for n in model.all_nodes() if n.is_mesh]
        skin_count  = sum(1 for n in model.all_nodes() if n.is_skin)

        # No bones at all → prop
        if dummy_count == 0:
            return PROFILE_PROP

        # Score each profile
        humanoid_score  = sum(1 for k in self.HUMANOID_KEYWORDS  if any(k in n for n in node_names))
        quadruped_score = sum(1 for k in self.QUADRUPED_KEYWORDS if any(k in n for n in node_names))
        droid_score     = sum(1 for k in self.DROID_KEYWORDS     if any(k in n for n in node_names))

        # Model name hints
        mname = (model.name or '').lower()
        if any(x in mname for x in ('drd','droid','r2','r4','astro','mech')):
            droid_score += 3
        if any(x in mname for x in ('kath','bantha','dewback','rancor','kinrath',
                                    'khounda','rakghoul','tukata','iriaz','wraid')):
            quadruped_score += 3

        # Bounding box aspect ratio: tall → humanoid, long → quadruped
        model.compute_bounds()  # sets model.bb_min / model.bb_max in-place
        bb_min = getattr(model, 'bb_min', None) or (0.0, 0.0, 0.0)
        bb_max = getattr(model, 'bb_max', None) or (1.0, 1.0, 1.0)
        dx = abs(bb_max[0] - bb_min[0])
        dy = abs(bb_max[1] - bb_min[1])
        dz = abs(bb_max[2] - bb_min[2])
        if dz > max(dx, dy) * 1.5:
            humanoid_score += 2
        elif max(dx, dy) > dz * 1.4:
            quadruped_score += 2

        scores = {
            PROFILE_HUMANOID:  humanoid_score,
            PROFILE_QUADRUPED: quadruped_score,
            PROFILE_DROID:     droid_score,
        }
        best = max(scores, key=scores.get)
        if scores[best] == 0:
            best = PROFILE_HUMANOID  # default fallback

        log.info(f"ProfileDetector: {model.name} → {best}  scores={scores}")
        return best


# ─────────────────────────────────────────────────────────────────────────────
#  Guide Auto-Placer
# ─────────────────────────────────────────────────────────────────────────────

class GuidePlacer:
    """
    Automatically places RigGuide pins based on mesh bounding volume.
    Implements AccuRIG-style midpoint placement: joints are positioned
    inside the mesh at anatomically appropriate height ratios.
    """

    def place_guides(self, model: KotorModel,
                     profile: str = PROFILE_HUMANOID,
                     existing_guides: Optional[Dict[str, RigGuide]] = None
                     ) -> Dict[str, RigGuide]:
        """
        Return a dict of {name: RigGuide} auto-placed for the given model.
        Pins are computed from the *rendered skin-mesh* bounding box only
        (excludes bone-proxy MESH-without-SKIN nodes) to avoid OOB placement.
        Each placed pin is clamped to the skin-mesh AABB so it always lies
        within the visible geometry.
        If existing_guides is provided, locked guides are kept as-is.
        """
        # ── Compute bounds using only rendered (skin / textured) mesh nodes ──
        skin_verts: List[Tuple[float, float, float]] = []
        for n in model.all_nodes():
            if not n.is_mesh or not n.vertices:
                continue
            # Include node if it's a skin mesh OR has UVs (textured = rendered)
            if n.is_skin or (n.uvs and len(n.uvs) > 0):
                skin_verts.extend(n.vertices)

        if skin_verts:
            xs = [v[0] for v in skin_verts]
            ys = [v[1] for v in skin_verts]
            zs = [v[2] for v in skin_verts]
            bb_min = (min(xs), min(ys), min(zs))
            bb_max = (max(xs), max(ys), max(zs))
        else:
            # Fallback to full model bounds
            model.compute_bounds()
            bb_min = getattr(model, 'bb_min', None) or (0.0, 0.0, 0.0)
            bb_max = getattr(model, 'bb_max', None) or (1.0, 1.0, 1.8)

        cx     = (bb_min[0] + bb_max[0]) / 2.0
        cy     = (bb_min[1] + bb_max[1]) / 2.0
        width  = max(bb_max[0] - bb_min[0], 0.01)
        depth  = max(bb_max[1] - bb_min[1], 0.01)
        height = max(bb_max[2] - bb_min[2], 0.01)
        base_z = bb_min[2]

        # AABB for clamping – use 5% margin inside the mesh
        margin = 0.05
        clamp_xmin, clamp_xmax = bb_min[0] + margin*width,  bb_max[0] - margin*width
        clamp_ymin, clamp_ymax = bb_min[1] + margin*depth,  bb_max[1] - margin*depth
        clamp_zmin, clamp_zmax = bb_min[2] + margin*height, bb_max[2] - margin*height

        def _clamp(x, lo, hi):
            return max(lo, min(hi, x))

        if   profile == PROFILE_HUMANOID:  template = HUMANOID_GUIDES
        elif profile == PROFILE_QUADRUPED: template = QUADRUPED_GUIDES
        elif profile == PROFILE_DROID:     template = DROID_GUIDES
        else:                              template = HUMANOID_GUIDES

        guides: Dict[str, RigGuide] = {}

        for gname, gparent, (nx, ny, nz) in template:
            # Keep locked user-placed guide
            if existing_guides and gname in existing_guides:
                eg = existing_guides[gname]
                if eg.locked:
                    guides[gname] = eg
                    continue

            # Scale normalized coords to world space using skin-mesh bounds
            wx = cx + nx * height
            wy = cy + ny * height
            wz = base_z + nz * height

            # Clamp to AABB so pin is always inside rendered mesh
            wx = _clamp(wx, clamp_xmin, clamp_xmax)
            wy = _clamp(wy, clamp_ymin, clamp_ymax)
            wz = _clamp(wz, clamp_zmin, clamp_zmax)

            colour = BONE_COLOURS.get(gname, (200, 200, 200))
            guides[gname] = RigGuide(
                name=gname,
                position=(wx, wy, wz),
                bone_parent=gparent,
                locked=False,
                colour=colour,
            )

        # Set mirror relationships
        for l_name, r_name in MIRROR_PAIRS.items():
            if l_name in guides and r_name in guides:
                guides[r_name].mirror_of = l_name

        log.info(f"GuidePlacer: placed {len(guides)} guides for profile={profile} "
                 f"bounds=({bb_min[0]:.2f},{bb_min[2]:.2f})-({bb_max[0]:.2f},{bb_max[2]:.2f})")
        return guides

    def snap_to_bone(self, guide: RigGuide, model: KotorModel,
                     tolerance: float = 0.3) -> bool:
        """
        Snap guide position to nearest existing bone/dummy node within tolerance.
        Returns True if snapped.
        """
        gx, gy, gz = guide.position
        best_dist = tolerance
        best_pos  = None
        for node in model.all_nodes():
            if node.is_dummy:
                nx, ny, nz = node.position
                d = math.sqrt((nx-gx)**2 + (ny-gy)**2 + (nz-gz)**2)
                if d < best_dist:
                    best_dist = d
                    best_pos  = (nx, ny, nz)
        if best_pos:
            guide.position = best_pos
            guide.locked   = True
            return True
        return False

    def mirror_guide(self, source: RigGuide, guides: Dict[str, RigGuide]):
        """
        Mirror a guide's X position to create/update its mirror partner.
        E.g. moving 'lshoulder' will update 'rshoulder' automatically.
        """
        for l_name, r_name in MIRROR_PAIRS.items():
            if source.name == l_name and r_name in guides:
                g = guides[r_name]
                if not g.locked:
                    sx, sy, sz = source.position
                    g.position = (-sx, sy, sz)
                    log.debug(f"Mirrored {l_name} → {r_name}")


# ─────────────────────────────────────────────────────────────────────────────
#  Bone Mask  (AccuRIG bone masking tool)
# ─────────────────────────────────────────────────────────────────────────────

class BoneMask:
    """
    Mask/exclude specific bones from the skinning step.
    Allows users to omit unnecessary bones for unusual character meshes
    (e.g. a model with no tail should mask tail bones).
    """

    def __init__(self):
        self._masked: Set[str] = set()

    def mask(self, bone_name: str):
        self._masked.add(bone_name.lower())
        log.debug(f"BoneMask: masked '{bone_name}'")

    def unmask(self, bone_name: str):
        self._masked.discard(bone_name.lower())

    def is_masked(self, bone_name: str) -> bool:
        return bone_name.lower() in self._masked

    def active_bones(self, guides: Dict[str, RigGuide]) -> Dict[str, RigGuide]:
        return {k: v for k, v in guides.items() if not self.is_masked(k)}

    def clear(self):
        self._masked.clear()

    def mask_tail(self):
        for b in ('tail_root','tail_mid','tail_tip'): self.mask(b)

    def mask_fingers(self):
        for b in ('lfinger01','lfinger02','rfinger01','rfinger02'): self.mask(b)

    def mask_toes(self):
        for b in ('ltoebase','rtoebase'): self.mask(b)

    @property
    def masked_bones(self) -> List[str]:
        return sorted(self._masked)


# ─────────────────────────────────────────────────────────────────────────────
#  Symmetry Enforcer
# ─────────────────────────────────────────────────────────────────────────────

class SymmetryEnforcer:
    """
    Detect and enforce L/R symmetry on the mesh and skeleton.
    """

    def enforce_guide_symmetry(self, guides: Dict[str, RigGuide],
                               axis: str = 'x') -> int:
        """Mirror all left-side guides to right side. Returns count of pairs fixed."""
        count = 0
        for l_name, r_name in MIRROR_PAIRS.items():
            if l_name in guides and r_name in guides:
                lg = guides[l_name]
                rg = guides[r_name]
                if not rg.locked:
                    lx, ly, lz = lg.position
                    if axis == 'x':
                        rg.position = (-lx, ly, lz)
                    elif axis == 'y':
                        rg.position = (lx, -ly, lz)
                    count += 1
        log.info(f"SymmetryEnforcer: fixed {count} guide pairs")
        return count

    def find_symmetric_vertices(self, node: ModelNode,
                                 axis: str = 'x',
                                 tolerance: float = 0.001
                                 ) -> Dict[int, int]:
        """
        Find pairs of vertices symmetric across the given axis.
        Returns {left_idx: right_idx}.
        """
        if not node.vertices:
            return {}
        pairs: Dict[int, int] = {}
        verts = node.vertices
        n = len(verts)
        for i in range(n):
            if i in pairs: continue
            vx, vy, vz = verts[i]
            for j in range(i+1, n):
                jx, jy, jz = verts[j]
                if axis == 'x':
                    if (abs(vx + jx) < tolerance and
                        abs(vy - jy) < tolerance and
                        abs(vz - jz) < tolerance):
                        pairs[i] = j
                        break
        return pairs

    def mirror_weights_lr(self, node: ModelNode) -> int:
        """
        Mirror left-side vertex weights to right side.
        Returns number of vertices updated.
        """
        if not node.skin_data or not node.vertices:
            return 0
        pairs = self.find_symmetric_vertices(node)
        count = 0
        for l_idx, r_idx in pairs.items():
            if l_idx < len(node.skin_data) and r_idx < len(node.skin_data):
                l_sd = node.skin_data[l_idx]
                r_sd = node.skin_data[r_idx]
                # Mirror bone indices using MIRROR_PAIRS
                new_infl = []
                for bw in l_sd.influences:
                    if bw.bone_index < len(node.bone_map):
                        bname = node.bone_map[bw.bone_index].lower()
                        # Find mirror bone
                        mirror_name = None
                        for ln, rn in MIRROR_PAIRS.items():
                            if bname == ln:   mirror_name = rn; break
                            if bname == rn:   mirror_name = ln; break
                        if mirror_name and mirror_name in node.bone_map:
                            mi = node.bone_map.index(mirror_name)
                            new_infl.append(BoneWeight(mi, bw.weight))
                        else:
                            new_infl.append(BoneWeight(bw.bone_index, bw.weight))
                if new_infl:
                    r_sd.influences = new_infl
                    count += 1
        log.info(f"mirror_weights_lr: updated {count}/{len(pairs)} right-side vertices")
        return count


# ─────────────────────────────────────────────────────────────────────────────
#  Weight Painter  (advanced heat-map + region-based skinning)
# ─────────────────────────────────────────────────────────────────────────────

class WeightPainter:
    """
    Sophisticated weight painting engine.
    Implements heat-map based auto-skinning with:
    - Region-aware candidate bone selection
    - Distance falloff with configurable exponent
    - Weight smoothing
    - Influence pruning to MAX_INFLUENCES
    """

    def __init__(self, heat_falloff: float = HEAT_FALLOFF,
                 max_influences: int = MAX_INFLUENCES,
                 min_weight: float = MIN_WEIGHT):
        self.heat_falloff    = heat_falloff
        self.max_influences  = max_influences
        self.min_weight      = min_weight

    # ── Main skinning entry point ────────────────────────────────────

    def skin_model(self, model: KotorModel,
                   guides: Dict[str, RigGuide],
                   mask: Optional[BoneMask] = None) -> int:
        """
        Compute skin weights for all mesh nodes in model using guides.
        Returns total number of vertices skinned.
        """
        active = mask.active_bones(guides) if mask else guides
        if not active:
            log.warning("WeightPainter: no active guides")
            return 0

        # Build bone world positions from guides
        bone_positions: Dict[str, Tuple[float,float,float]] = {
            g.name: g.position for g in active.values()
        }

        total = 0
        for node in model.all_nodes():
            if node.is_mesh and node.vertices:
                self._skin_node(node, bone_positions)
                total += len(node.vertices)
        log.info(f"WeightPainter: skinned {total} vertices across model")
        return total

    def _skin_node(self, node: ModelNode,
                   bone_positions: Dict[str, Tuple[float,float,float]]):
        """Compute and assign skin weights to a single mesh node."""
        verts = node.vertices
        if not verts: return

        # Build bone_map from active guides
        bone_names = list(bone_positions.keys())
        node.bone_map = bone_names[:]

        node.flags |= int(NodeFlags.SKIN)
        node.skin_data = []

        node.compute_bounds()  # sets bb_min / bb_max in-place
        bb_min = getattr(node, 'bb_min', None) or (0.0, 0.0, 0.0)
        bb_max = getattr(node, 'bb_max', None) or (1.0, 1.0, 1.0)
        height = max(bb_max[2] - bb_min[2], 0.01)

        for vx, vy, vz in verts:
            # Normalised vertical position for region hints
            nz = (vz - bb_min[2]) / height

            # Select candidate bones based on region
            candidates = self._region_candidates(nz, bone_names)

            # Compute heat weights
            weights = self._heat_weights(vx, vy, vz, bone_positions, candidates)

            # Prune to max influences
            weights = self._prune(weights)

            influences = [BoneWeight(bone_names.index(bn), w)
                          for bn, w in weights.items() if bn in bone_names]
            node.skin_data.append(VertexSkinData(influences=influences))

    def _region_candidates(self, nz: float,
                            bone_names: List[str]) -> List[str]:
        """Select candidate bones based on vertical region."""
        # Simple region heuristic (matches AccuRIG region concept)
        if nz > 0.82:
            region = {'head','neck'}
        elif nz > 0.68:
            region = {'neck','chest','lshoulder','rshoulder','lforearm','rforearm',
                      'lhand','lfinger01','rhand','rfinger01','torso'}
        elif nz > 0.50:
            region = {'chest','stomach','hip','lshoulder','rshoulder',
                      'lforearm','rforearm','torso'}
        elif nz > 0.35:
            region = {'hip','stomach','lthigh','rthigh','lleg','rleg'}
        else:
            region = {'lthigh','rthigh','lcalf','rcalf','lankle','rankle',
                      'ltoebase','rtoebase','lfoot','rfoot','lleg','rleg'}

        # Intersect with available bones; fallback to all
        candidates = [b for b in bone_names if b.lower() in region]
        if not candidates:
            candidates = bone_names
        return candidates

    def _heat_weights(self, vx: float, vy: float, vz: float,
                      bone_positions: Dict[str, Tuple[float,float,float]],
                      candidates: List[str]) -> Dict[str, float]:
        """Compute inverse-distance heat weights for candidates."""
        raw: Dict[str, float] = {}
        for bname in candidates:
            if bname not in bone_positions: continue
            bx, by, bz = bone_positions[bname]
            dist2 = (vx-bx)**2 + (vy-by)**2 + (vz-bz)**2
            raw[bname] = 1.0 / (1.0 + dist2 ** (self.heat_falloff / 2.0))
        total = sum(raw.values())
        if total < 1e-8:
            return {}
        return {k: v/total for k, v in raw.items()}

    def _prune(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Keep top MAX_INFLUENCES weights and normalize."""
        if not weights: return {}
        # Sort by weight desc, keep top N
        sorted_w = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        pruned   = {k: v for k, v in sorted_w[:self.max_influences]
                    if v >= self.min_weight}
        total    = sum(pruned.values())
        if total < 1e-8: return {}
        return {k: v/total for k, v in pruned.items()}

    # ── Interactive painting ─────────────────────────────────────────

    def paint_sphere(self, node: ModelNode, bone_name: str,
                     center: Tuple[float,float,float],
                     radius: float, weight: float,
                     blend: bool = True):
        """
        Paint weights within a sphere radius.
        If blend=True, blends with existing weights; otherwise overwrites.
        Returns (painted_count, updated_count).
        """
        if not node.vertices: return 0, 0
        cx, cy, cz = center
        r2 = radius * radius

        # Ensure bone is in bone_map
        if bone_name not in node.bone_map:
            node.bone_map.append(bone_name)
        bi = node.bone_map.index(bone_name)
        node.flags |= int(NodeFlags.SKIN)

        # Ensure skin_data is sized
        while len(node.skin_data) < len(node.vertices):
            node.skin_data.append(VertexSkinData(influences=[]))

        painted = 0
        for idx, (vx, vy, vz) in enumerate(node.vertices):
            dist2 = (vx-cx)**2 + (vy-cy)**2 + (vz-cz)**2
            if dist2 > r2: continue

            # Distance-based falloff within sphere
            falloff = 1.0 - (dist2/r2) ** 0.5
            w = weight * falloff

            sd = node.skin_data[idx]
            if blend:
                # Find existing influence for this bone
                existing = next((bw for bw in sd.influences if bw.bone_index == bi), None)
                if existing:
                    existing.weight = min(1.0, existing.weight + w)
                else:
                    sd.influences.append(BoneWeight(bi, w))
                sd.normalize()
                # Prune to max influences manually
                if len(sd.influences) > self.max_influences:
                    sd.influences.sort(key=lambda bw: bw.weight, reverse=True)
                    sd.influences = [bw for bw in sd.influences[:self.max_influences]
                                     if bw.weight >= self.min_weight]
                    sd.normalize()
            else:
                sd.influences = [BoneWeight(bi, w)]
            painted += 1

        return painted

    def smooth_weights(self, node: ModelNode, iterations: int = 2) -> int:
        """
        Smooth vertex weights by averaging with neighbouring vertices.
        Uses triangle adjacency for neighbour lookup.
        Returns number of vertices smoothed.
        """
        if not node.vertices or not node.faces or not node.skin_data:
            return 0

        # Build adjacency
        adj: Dict[int, Set[int]] = {i: set() for i in range(len(node.vertices))}

        for face in node.faces:
            for i in range(3):
                for j in range(3):
                    if i != j:
                        adj[face[i]].add(face[j])

        for _ in range(iterations):
            new_sds = []
            for vi, sd in enumerate(node.skin_data):
                neighbours = adj.get(vi, set())
                if not neighbours:
                    new_sds.append(sd)
                    continue
                # Average weights with neighbours
                accum: Dict[int, float] = {}
                all_verts = [vi] + list(neighbours)
                for nvi in all_verts:
                    if nvi < len(node.skin_data):
                        for bw in node.skin_data[nvi].influences:
                            accum[bw.bone_index] = accum.get(bw.bone_index, 0) + bw.weight
                n_count = len(all_verts)
                new_infl = [BoneWeight(bi, w/n_count)
                            for bi, w in accum.items()]
                new_sd = VertexSkinData(influences=new_infl)
                new_sd.normalize()
                # Prune to max influences manually
                if len(new_sd.influences) > self.max_influences:
                    new_sd.influences.sort(key=lambda bw: bw.weight, reverse=True)
                    new_sd.influences = [bw for bw in new_sd.influences[:self.max_influences]
                                         if bw.weight >= self.min_weight]
                    new_sd.normalize()
                new_sds.append(new_sd)
            node.skin_data = new_sds

        return len(node.vertices)


# ─────────────────────────────────────────────────────────────────────────────
#  Pose Corrector (T-pose / A-pose bind pose)
# ─────────────────────────────────────────────────────────────────────────────

class PoseCorrector:
    """
    Correct the bind pose of a rigged model to T-pose or A-pose.
    """

    def apply_tpose(self, guides: Dict[str, RigGuide]) -> Dict[str, RigGuide]:
        """Straighten arm and leg guides to canonical T-pose positions."""
        corrected = dict(guides)
        # Shoulders: set Y to 0, arms straight out along X
        for side, sign in [('l', -1), ('r', 1)]:
            for bone, xfrac in [(f'{side}shoulder', 0.20),
                                (f'{side}forearm',  0.40),
                                (f'{side}hand',     0.55),
                                (f'{side}finger01', 0.60)]:
                if bone in corrected:
                    g = corrected[bone]
                    x, y, z = g.position
                    corrected[bone] = RigGuide(
                        name=bone,
                        position=(sign * abs(x), 0.0, z),
                        bone_parent=g.bone_parent,
                        locked=g.locked,
                        colour=g.colour,
                    )
        return corrected

    def apply_apose(self, guides: Dict[str, RigGuide]) -> Dict[str, RigGuide]:
        """Apply A-pose: arms at ~45° below horizontal."""
        corrected = dict(guides)
        for side, sign in [('l', -1), ('r', 1)]:
            for bone, xf, zf in [(f'{side}shoulder', 0.18, 0.70),
                                  (f'{side}forearm',  0.32, 0.64),
                                  (f'{side}hand',     0.44, 0.58)]:
                if bone in corrected:
                    g = corrected[bone]
                    if 'hip' in guides:
                        base_z = guides['root'].position[2] if 'root' in guides else 0
                        h = (guides['head'].position[2] - base_z
                             if 'head' in guides else 1.8)
                        corrected[bone] = RigGuide(
                            name=bone,
                            position=(sign * xf * h, 0.0, base_z + zf * h),
                            bone_parent=g.bone_parent,
                            locked=g.locked,
                            colour=g.colour,
                        )
        return corrected


# ─────────────────────────────────────────────────────────────────────────────
#  AcuRig  –  Main façade class
# ─────────────────────────────────────────────────────────────────────────────

class AcuRig:
    """
    Main AcuRig-style rigging façade.

    Workflow
    --------
    1. acurig = AcuRig()
    2. profile = acurig.detect_profile(model)
    3. guides  = acurig.place_guides(model, profile)
    4. # User adjusts guides interactively in the viewport
    5. acurig.mask.mask_tail()            # optional: mask unused bones
    6. acurig.symmetry.enforce_guide_symmetry(guides)  # ensure L/R symmetry
    7. model   = acurig.generate_rig(model, guides)    # create bones
    8. acurig.painter.skin_model(model, guides, acurig.mask)  # auto-skin
    9. # Optionally: acurig.painter.smooth_weights(node, 2)
    10. acurig.save_template(guides, 'my_rig.json')
    """

    def __init__(self):
        self.detector  = ProfileDetector()
        self.placer    = GuidePlacer()
        self.mask      = BoneMask()
        self.symmetry  = SymmetryEnforcer()
        self.painter   = WeightPainter()
        self.pose      = PoseCorrector()
        self._guides: Dict[str, RigGuide] = {}
        self._profile  = PROFILE_HUMANOID

    # ── Step 1: Profile ──────────────────────────────────────────────

    def detect_profile(self, model: KotorModel) -> str:
        self._profile = self.detector.detect(model)
        return self._profile

    # ── Step 2: Guide placement ──────────────────────────────────────

    def place_guides(self, model: KotorModel,
                     profile: Optional[str] = None,
                     snap_to_bones: bool = True) -> Dict[str, RigGuide]:
        if profile is None:
            profile = self._profile
        guides = self.placer.place_guides(model, profile, self._guides)
        if snap_to_bones:
            snapped = 0
            for g in guides.values():
                if not g.locked and self.placer.snap_to_bone(g, model, 0.4):
                    snapped += 1
            log.info(f"AcuRig.place_guides: {snapped}/{len(guides)} snapped to existing bones")
        self._guides = guides
        return guides

    # ── Step 3: Guide manipulation ───────────────────────────────────

    def move_guide(self, name: str, position: Tuple[float,float,float],
                   auto_mirror: bool = True):
        """Move a guide (and optionally mirror its partner)."""
        if name not in self._guides:
            self._guides[name] = RigGuide(name=name, position=position, locked=True)
        else:
            self._guides[name].position = position
            self._guides[name].locked   = True
        if auto_mirror:
            self.placer.mirror_guide(self._guides[name], self._guides)

    def lock_guide(self, name: str):
        if name in self._guides:
            self._guides[name].locked = True

    def unlock_guide(self, name: str):
        if name in self._guides:
            self._guides[name].locked = False

    def get_guide(self, name: str) -> Optional[RigGuide]:
        return self._guides.get(name)

    def get_all_guides(self) -> Dict[str, RigGuide]:
        return dict(self._guides)

    # ── Step 4: Rig generation ───────────────────────────────────────

    def generate_rig(self, model: KotorModel,
                     guides: Optional[Dict[str, RigGuide]] = None) -> KotorModel:
        """
        Create ModelNode bones from guides and attach them to the model.
        Replaces / augments existing bone hierarchy.
        """
        if guides is None:
            guides = self._guides
        active = self.mask.active_bones(guides)

        # Remove old generated bones (keep original model bones for reference)
        existing_node_names = {n.name for n in model.all_nodes()}

        root = model.root_node
        if root is None:
            root = ModelNode(name='rootdummy', flags=int(NodeFlags.HEADER))
            model.root_node = root

        # Build bone nodes from guides
        bone_nodes: Dict[str, ModelNode] = {}
        for gname, guide in active.items():
            if gname in existing_node_names:
                # Reuse existing node
                existing = model.find_node(gname)
                if existing:
                    existing.position = guide.position
                    bone_nodes[gname] = existing
                    continue
            bn = ModelNode(
                name=gname,
                flags=int(NodeFlags.HEADER),
                position=guide.position,
            )
            bone_nodes[gname] = bn

        # Link parent-child
        for gname, guide in active.items():
            if guide.bone_parent and guide.bone_parent in bone_nodes:
                child  = bone_nodes[gname]
                parent = bone_nodes[guide.bone_parent]
                if child not in parent.children:
                    parent.children.append(child)
                child.parent = guide.bone_parent

        # Attach root bone to model root
        root_guide_name = 'root' if 'root' in bone_nodes else next(iter(bone_nodes), None)
        if root_guide_name:
            rn = bone_nodes[root_guide_name]
            if rn not in root.children:
                root.children.append(rn)

        log.info(f"AcuRig.generate_rig: created/updated {len(bone_nodes)} bone nodes")
        return model

    # ── Step 5: Auto-skin ────────────────────────────────────────────

    def auto_skin(self, model: KotorModel,
                  guides: Optional[Dict[str, RigGuide]] = None,
                  smooth_iterations: int = 2) -> int:
        """
        Run heat-map skinning on all mesh nodes.
        Returns total vertices skinned.
        """
        if guides is None:
            guides = self._guides
        total = self.painter.skin_model(model, guides, self.mask)

        if smooth_iterations > 0:
            for node in model.all_nodes():
                if node.is_mesh and node.skin_data:
                    self.painter.smooth_weights(node, smooth_iterations)

        log.info(f"AcuRig.auto_skin: {total} vertices skinned, "
                 f"{smooth_iterations} smooth passes")
        return total

    # ── Step 6: Weight stats ─────────────────────────────────────────

    def weight_stats(self, model: KotorModel) -> Dict:
        """Return weight statistics for the model."""
        stats: Dict = {}
        total_verts = 0
        total_weighted = 0
        bone_usage: Dict[str, int] = {}

        for node in model.all_nodes():
            if not node.is_mesh or not node.skin_data: continue
            n_v = len(node.vertices) if node.vertices else 0
            n_w = sum(1 for sd in node.skin_data if sd.influences)
            avg_infl = (sum(len(sd.influences) for sd in node.skin_data) /
                        max(len(node.skin_data), 1))
            stats[node.name] = {
                'verts': n_v, 'weighted': n_w,
                'avg_influences': round(avg_infl, 2),
            }
            total_verts    += n_v
            total_weighted += n_w
            for sd in node.skin_data:
                for bw in sd.influences:
                    if bw.bone_index < len(node.bone_map):
                        bname = node.bone_map[bw.bone_index]
                        bone_usage[bname] = bone_usage.get(bname, 0) + 1

        stats['_total'] = {
            'total_verts': total_verts,
            'total_weighted': total_weighted,
            'bone_usage': bone_usage,
        }
        return stats

    # ── Template I/O ─────────────────────────────────────────────────

    def save_template(self, path: str,
                      guides: Optional[Dict[str, RigGuide]] = None):
        """Save current guides to a JSON template file."""
        if guides is None:
            guides = self._guides
        data = {
            'profile': self._profile,
            'guides': {
                name: {
                    'name':        g.name,
                    'position':    list(g.position),
                    'bone_parent': g.bone_parent,
                    'locked':      g.locked,
                    'mirror_of':   g.mirror_of,
                    'colour':      list(g.colour),
                }
                for name, g in guides.items()
            },
            'masked_bones': self.mask.masked_bones,
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        log.info(f"AcuRig template saved → {path}")

    def load_template(self, path: str) -> Dict[str, RigGuide]:
        """Load guides from a JSON template file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self._profile = data.get('profile', PROFILE_HUMANOID)
        guides: Dict[str, RigGuide] = {}
        for name, gd in data.get('guides', {}).items():
            guides[name] = RigGuide(
                name=gd['name'],
                position=tuple(gd['position']),
                bone_parent=gd.get('bone_parent'),
                locked=gd.get('locked', False),
                mirror_of=gd.get('mirror_of'),
                colour=tuple(gd.get('colour', [200, 200, 200])),
            )
        for bname in data.get('masked_bones', []):
            self.mask.mask(bname)
        self._guides = guides
        log.info(f"AcuRig template loaded ← {path}  ({len(guides)} guides)")
        return guides

    def reset(self):
        """Reset all guides, mask, and state."""
        self._guides  = {}
        self._profile = PROFILE_HUMANOID
        self.mask.clear()

    # ── Convenience aliases ──────────────────────────────────────────

    def enforce_symmetry(self, guides: Optional[Dict[str, RigGuide]] = None,
                         axis: str = 'x') -> int:
        """Convenience: enforce L/R symmetry on guides (alias for symmetry.enforce_guide_symmetry)."""
        if guides is None:
            guides = self._guides
        return self.symmetry.enforce_guide_symmetry(guides, axis)

    def skin_model(self, model: KotorModel,
                   guides: Optional[Dict[str, RigGuide]] = None,
                   smooth_iterations: int = 2) -> int:
        """Convenience alias for auto_skin()."""
        return self.auto_skin(model, guides, smooth_iterations)

    def mirror_weights(self, model: KotorModel) -> int:
        """Mirror left→right vertex weights on all skinned mesh nodes."""
        total = 0
        for node in model.all_nodes():
            if node.is_mesh and node.skin_data:
                total += self.symmetry.mirror_weights_lr(node)
        return total

    # ── Convenience: one-shot full rig ───────────────────────────────

    def rig_model_full(self, model: KotorModel,
                       profile: Optional[str] = None,
                       smooth_iterations: int = 2) -> Tuple[KotorModel, Dict]:
        """
        One-shot: detect → place guides → generate rig → auto-skin.
        Returns (rigged_model, weight_stats).
        """
        if profile is None:
            profile = self.detect_profile(model)
        guides = self.place_guides(model, profile, snap_to_bones=True)
        self.generate_rig(model, guides)
        self.auto_skin(model, guides, smooth_iterations)
        stats = self.weight_stats(model)
        log.info(f"AcuRig.rig_model_full: profile={profile}, "
                 f"guides={len(guides)}, "
                 f"total_verts={stats.get('_total',{}).get('total_verts',0)}")
        return model, stats
