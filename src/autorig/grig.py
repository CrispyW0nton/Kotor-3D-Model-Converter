"""
GRig – Ghost Rigger Manual Rigging System
==========================================
A drag-and-drop, symmetry-aware bone placement system for KotOR models.
Designed after AcuRig (Reallusion AccuRIG) and MeshyAI's rigging workflow.

Core Concepts
-------------
1. **Bone Pin Placement** – Click or drag to place bone guides anywhere in 3D.
   - Pins auto-snap to mesh surface (nearest vertex projection).
   - Mirrored bone pins update automatically when moved (L↔R symmetry).
   - Double-click a pin to rename or re-parent it.

2. **Bone Chain Builder** – Connect pins into chains (Spine, Arm, Leg, Tail).
   - Click two pins → auto-inserts intermediate bones.
   - "IK-ready" annotation stored in JSON template.

3. **Symmetry Engine** – Full L/R mirroring at guide + weight level.
   - Mirror axis configurable (X default, or Y).
   - Tolerance-based vertex pair detection.
   - One-click "Mirror Weights L→R" and "R→L".

4. **Weight Painting Modes**:
   - Heat-map (proximity-based) – same as AcuRig/AccuRIG.
   - Sphere brush – paint weights within a spherical radius.
   - Flood fill – assign single bone to entire mesh region.
   - Smooth brush – blend adjacent vertex weights.
   - Relax brush – normalize influence spikes.

5. **Influence Inspector** – per-vertex weight chart.
   - Shows all bone influences for selected vertex.
   - Direct numeric editing.
   - "Prune" button removes influences below threshold.

6. **Pose Bind** – set bind pose to T-pose, A-pose, or current.

7. **Template Library** – save/load named rig templates as JSON.
   - Quick-apply to any loaded model.
   - Batch-apply to folder of models.

8. **Bone Palette** – hierarchical drag-and-drop bone tree editor.
   - Drag bone in palette to reparent it.
   - Inline rename by double-click.
   - Per-bone colour coding.
"""

from __future__ import annotations
import math, logging, json, os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set, Any
from enum import Enum

try:
    from ..core.model_data import (
        KotorModel, ModelNode, NodeFlags, VertexSkinData, BoneWeight
    )
except ImportError:
    from core.qt_core.geometry.model_data import (  # type: ignore[no-redef]
        KotorModel, ModelNode, NodeFlags, VertexSkinData, BoneWeight
    )

from .accurig import (
    RigGuide, MIRROR_PAIRS, BONE_COLOURS,
    HUMANOID_GUIDES, QUADRUPED_GUIDES, DROID_GUIDES,
    PROFILE_HUMANOID, PROFILE_QUADRUPED, PROFILE_DROID, PROFILE_PROP,
    ProfileDetector, GuidePlacer, BoneMask, SymmetryEnforcer,
    WeightPainter, PoseCorrector, AcuRig,
    MAX_INFLUENCES, MIN_WEIGHT, HEAT_FALLOFF
)

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Brush Modes  (MeshyAI-style painting modes)
# ─────────────────────────────────────────────────────────────────────────────

class BrushMode(Enum):
    HEAT_MAP   = "heat_map"     # proximity-based auto-skin (AccuRIG style)
    SPHERE     = "sphere"       # spherical paint brush
    FLOOD      = "flood_fill"   # assign all vertices in mesh
    SMOOTH     = "smooth"       # blend adjacent weights
    RELAX      = "relax"        # normalize weight spikes
    ERASE      = "erase"        # remove bone influence from verts


# ─────────────────────────────────────────────────────────────────────────────
#  Bone Pin  (enhanced RigGuide with drag state and chain info)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BonePin:
    """
    A placed bone guide pin – the fundamental GRig placement element.
    Extends RigGuide with:
    - drag_active: True while user is dragging this pin in the viewport
    - snap_vertex_idx: nearest mesh vertex index for surface snapping
    - chain_id: which bone chain this pin belongs to
    - ik_tip: marks this pin as an IK end effector
    - weight_locked: prevents heat-map from overwriting manual weights
    - display_size: visual pin radius in world units
    """
    name:           str
    position:       Tuple[float, float, float] = (0.0, 0.0, 0.0)
    bone_parent:    Optional[str]              = None
    locked:         bool                       = False
    mirror_of:      Optional[str]              = None
    colour:         Tuple[int, int, int]       = (255, 200, 0)
    # GRig-specific
    drag_active:    bool                       = False
    snap_vertex_idx: int                       = -1
    chain_id:       Optional[str]              = None
    ik_tip:         bool                       = False
    weight_locked:  bool                       = False
    display_size:   float                      = 0.06

    def to_rig_guide(self) -> RigGuide:
        """Convert to a RigGuide for compatibility with AcuRig pipeline."""
        return RigGuide(
            name        = self.name,
            position    = self.position,
            bone_parent = self.bone_parent,
            locked      = self.locked,
            mirror_of   = self.mirror_of,
            colour      = self.colour,
        )

    @staticmethod
    def from_rig_guide(g: RigGuide) -> 'BonePin':
        """Create a BonePin from an existing RigGuide."""
        return BonePin(
            name        = g.name,
            position    = g.position,
            bone_parent = g.bone_parent,
            locked      = g.locked,
            mirror_of   = g.mirror_of,
            colour      = g.colour,
        )

    def distance_to(self, other: 'BonePin') -> float:
        ax, ay, az = self.position
        bx, by, bz = other.position
        return math.sqrt((ax-bx)**2 + (ay-by)**2 + (az-bz)**2)

    def to_dict(self) -> Dict:
        return {
            'name':        self.name,
            'position':    list(self.position),
            'bone_parent': self.bone_parent,
            'locked':      self.locked,
            'mirror_of':   self.mirror_of,
            'colour':      list(self.colour),
            'chain_id':    self.chain_id,
            'ik_tip':      self.ik_tip,
            'weight_locked': self.weight_locked,
        }

    @staticmethod
    def from_dict(d: Dict) -> 'BonePin':
        return BonePin(
            name          = d['name'],
            position      = tuple(d['position']),
            bone_parent   = d.get('bone_parent'),
            locked        = d.get('locked', False),
            mirror_of     = d.get('mirror_of'),
            colour        = tuple(d.get('colour', [255, 200, 0])),
            chain_id      = d.get('chain_id'),
            ik_tip        = d.get('ik_tip', False),
            weight_locked = d.get('weight_locked', False),
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Bone Chain  (connect pins into IK-ready chains)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BoneChain:
    """
    A named sequence of BonePins forming a limb chain.
    Example: 'left_arm' = [lshoulder, lforearm, lhand, lfinger01]
    """
    chain_id:   str
    pin_names:  List[str] = field(default_factory=list)
    ik_ready:   bool      = False
    colour:     Tuple[int, int, int] = (200, 200, 200)

    def add_pin(self, pin_name: str):
        if pin_name not in self.pin_names:
            self.pin_names.append(pin_name)

    def remove_pin(self, pin_name: str):
        if pin_name in self.pin_names:
            self.pin_names.remove(pin_name)


# ─────────────────────────────────────────────────────────────────────────────
#  Influence Inspector  (per-vertex weight viewer)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class VertexInfluence:
    """Weight data for a single vertex, as used by the Influence Inspector."""
    vertex_index: int
    mesh_name:    str
    position:     Tuple[float, float, float]
    influences:   List[Tuple[str, float]]   # [(bone_name, weight), ...]

    @staticmethod
    def from_skin_data(vi: int, node: ModelNode) -> Optional['VertexInfluence']:
        if not node.skin_data or vi >= len(node.skin_data):
            return None
        sd  = node.skin_data[vi]
        pos = node.vertices[vi] if vi < len(node.vertices) else (0, 0, 0)
        infl = []
        for bw in sd.influences:
            bname = (node.bone_map[bw.bone_index]
                     if bw.bone_index < len(node.bone_map) else f"bone_{bw.bone_index}")
            infl.append((bname, bw.weight))
        return VertexInfluence(
            vertex_index=vi, mesh_name=node.name,
            position=pos, influences=infl
        )


# ─────────────────────────────────────────────────────────────────────────────
#  GRig Brush Engine  (multi-mode weight painting)
# ─────────────────────────────────────────────────────────────────────────────

class GRigBrush:
    """
    Multi-mode weight painting brush for GRig.
    Supports: heat-map, sphere, flood, smooth, relax, erase.
    """

    def __init__(self, mode: BrushMode = BrushMode.SPHERE,
                 radius: float = 0.3, weight: float = 1.0,
                 falloff: float = 2.0, smooth_iter: int = 2):
        self.mode       = mode
        self.radius     = radius
        self.weight     = weight
        self.falloff    = falloff
        self.smooth_iter = smooth_iter
        self._painter   = WeightPainter(heat_falloff=falloff)

    # ── Sphere mode ──────────────────────────────────────────────────────────

    def paint_sphere(self, node: ModelNode, bone_name: str,
                     center: Tuple[float, float, float],
                     radius: Optional[float] = None,
                     weight: Optional[float] = None) -> int:
        """Paint weights in a sphere. Returns count of vertices affected."""
        r = radius if radius is not None else self.radius
        w = weight if weight is not None else self.weight
        return self._painter.paint_sphere(node, bone_name, center, r, w)

    # ── Flood fill mode ──────────────────────────────────────────────────────

    def flood_fill(self, node: ModelNode, bone_name: str,
                   weight: Optional[float] = None) -> int:
        """Assign all vertices in the mesh to bone_name with given weight."""
        w = weight if weight is not None else self.weight
        if not node.vertices:
            return 0
        if bone_name not in node.bone_map:
            node.bone_map.append(bone_name)
        bi = node.bone_map.index(bone_name)
        node.flags |= int(NodeFlags.SKIN)
        node.skin_data = [
            VertexSkinData(influences=[BoneWeight(bi, w)])
            for _ in node.vertices
        ]
        log.info(f"GRigBrush.flood_fill: {len(node.vertices)} verts → {bone_name} (w={w:.2f})")
        return len(node.vertices)

    # ── Smooth mode ───────────────────────────────────────────────────────────

    def smooth_in_sphere(self, node: ModelNode,
                         center: Tuple[float, float, float],
                         radius: Optional[float] = None,
                         iterations: int = 2) -> int:
        """Smooth vertex weights within sphere radius. Returns affected count."""
        r = radius if radius is not None else self.radius
        if not node.skin_data or not node.vertices:
            return 0

        affected_indices = [
            i for i, (vx, vy, vz) in enumerate(node.vertices)
            if (vx - center[0])**2 + (vy - center[1])**2 + (vz - center[2])**2 <= r*r
        ]

        if not affected_indices:
            return 0

        # Build neighbor map (vertices within r/2 of each other)
        for _ in range(iterations):
            for vi in affected_indices:
                vx, vy, vz = node.vertices[vi]
                neighbors = [
                    j for j, (ox, oy, oz) in enumerate(node.vertices)
                    if j != vi and
                    (ox-vx)**2 + (oy-vy)**2 + (oz-vz)**2 < (r*0.5)**2
                ]
                if not neighbors or vi >= len(node.skin_data):
                    continue
                # Average weights with neighbors
                all_bone_weights: Dict[int, float] = {}
                # self weights
                if vi < len(node.skin_data):
                    for bw in node.skin_data[vi].influences:
                        all_bone_weights[bw.bone_index] = (
                            all_bone_weights.get(bw.bone_index, 0) + bw.weight)
                # neighbor weights
                for ni in neighbors:
                    if ni >= len(node.skin_data):
                        continue
                    for bw in node.skin_data[ni].influences:
                        all_bone_weights[bw.bone_index] = (
                            all_bone_weights.get(bw.bone_index, 0) + bw.weight * 0.3)
                # Normalize
                total = sum(all_bone_weights.values())
                if total > 0:
                    node.skin_data[vi].influences = [
                        BoneWeight(k, v/total)
                        for k, v in sorted(all_bone_weights.items(), key=lambda x: -x[1])[:MAX_INFLUENCES]
                        if v/total >= MIN_WEIGHT
                    ]

        return len(affected_indices)

    # ── Erase mode ────────────────────────────────────────────────────────────

    def erase_in_sphere(self, node: ModelNode, bone_name: str,
                        center: Tuple[float, float, float],
                        radius: Optional[float] = None) -> int:
        """Remove bone influence within sphere. Returns count of vertices changed."""
        r = radius if radius is not None else self.radius
        if not node.skin_data or not node.vertices:
            return 0
        if bone_name not in node.bone_map:
            return 0
        bi = node.bone_map.index(bone_name)
        count = 0
        for vi, (vx, vy, vz) in enumerate(node.vertices):
            if (vx - center[0])**2 + (vy - center[1])**2 + (vz - center[2])**2 > r*r:
                continue
            if vi >= len(node.skin_data):
                continue
            sd = node.skin_data[vi]
            old_len = len(sd.influences)
            sd.influences = [bw for bw in sd.influences if bw.bone_index != bi]
            if len(sd.influences) < old_len:
                sd.normalize()
                count += 1
        return count

    # ── Relax mode ────────────────────────────────────────────────────────────

    def relax_in_sphere(self, node: ModelNode,
                        center: Tuple[float, float, float],
                        radius: Optional[float] = None) -> int:
        """Normalize weight spikes within sphere. Returns count of vertices relaxed."""
        r = radius if radius is not None else self.radius
        if not node.skin_data or not node.vertices:
            return 0
        count = 0
        for vi, (vx, vy, vz) in enumerate(node.vertices):
            if (vx - center[0])**2 + (vy - center[1])**2 + (vz - center[2])**2 > r*r:
                continue
            if vi >= len(node.skin_data):
                continue
            sd = node.skin_data[vi]
            if len(sd.influences) > 1:
                sd.normalize()
                count += 1
        return count

    # ── Heat-map mode ─────────────────────────────────────────────────────────

    def apply_heat_map(self, model: KotorModel,
                       pins: Dict[str, BonePin],
                       mask: Optional[BoneMask] = None) -> int:
        """Apply heat-map skinning to entire model from pin positions."""
        guides = {name: pin.to_rig_guide() for name, pin in pins.items()}
        return self._painter.skin_model(model, guides, mask)


# ─────────────────────────────────────────────────────────────────────────────
#  GRig Symmetry Engine  (enhanced, bidirectional)
# ─────────────────────────────────────────────────────────────────────────────

class GRigSymmetry:
    """
    Enhanced L/R symmetry for GRig.
    - Bidirectional mirroring (L→R or R→L)
    - Configurable mirror axis (X, Y, Z)
    - Tolerance control
    - Per-pin auto-mirror when pin is moved
    """

    def __init__(self, axis: str = 'x', tolerance: float = 0.005):
        self.axis      = axis
        self.tolerance = tolerance
        self._se       = SymmetryEnforcer()

    def mirror_pin(self, pin: BonePin, pins: Dict[str, 'BonePin'],
                   direction: str = 'l_to_r') -> bool:
        """
        Mirror a single pin to its counterpart.
        direction: 'l_to_r' or 'r_to_l'
        Returns True if a mirror partner was found and updated.
        """
        pname = pin.name.lower()
        partner_name = None

        if direction == 'l_to_r':
            for l_name, r_name in MIRROR_PAIRS.items():
                if pname == l_name:
                    partner_name = r_name; break
        else:
            for l_name, r_name in MIRROR_PAIRS.items():
                if pname == r_name:
                    partner_name = l_name; break

        if partner_name is None:
            return False

        # Find partner in pins dict (case-insensitive)
        partner_key = next(
            (k for k in pins if k.lower() == partner_name), None)
        if partner_key is None:
            return False

        partner = pins[partner_key]
        if partner.locked:
            return False

        ax, ay, az = pin.position
        if self.axis == 'x':
            partner.position = (-ax, ay, az)
        elif self.axis == 'y':
            partner.position = (ax, -ay, az)
        elif self.axis == 'z':
            partner.position = (ax, ay, -az)
        return True

    def enforce_all(self, pins: Dict[str, 'BonePin'],
                    direction: str = 'l_to_r') -> int:
        """Mirror all pins. Returns count of pairs updated."""
        guides = {n: p.to_rig_guide() for n, p in pins.items()}
        result = self._se.enforce_guide_symmetry(guides, self.axis)
        # Copy mirrored positions back
        for name, g in guides.items():
            if name in pins:
                pins[name].position = g.position
        return result

    def find_vertex_pairs(self, node: ModelNode) -> Dict[int, int]:
        """Find symmetric vertex pairs on a mesh node."""
        return self._se.find_symmetric_vertices(node, self.axis, self.tolerance)

    def mirror_weights(self, node: ModelNode, direction: str = 'l_to_r') -> int:
        """Mirror vertex weights. Returns count of vertices updated."""
        if direction == 'l_to_r':
            return self._se.mirror_weights_lr(node)
        else:
            # R→L: temporarily swap bone_map names then call mirror
            # For now, call the standard L→R mirror after flipping names
            swapped_bmap = []
            for bname in node.bone_map:
                bl = bname.lower()
                found = False
                for l_n, r_n in MIRROR_PAIRS.items():
                    if bl == l_n:
                        swapped_bmap.append(bname.replace(l_n, r_n)); found = True; break
                    elif bl == r_n:
                        swapped_bmap.append(bname.replace(r_n, l_n)); found = True; break
                if not found:
                    swapped_bmap.append(bname)
            orig = node.bone_map[:]
            node.bone_map = swapped_bmap
            count = self._se.mirror_weights_lr(node)
            node.bone_map = orig
            return count


# ─────────────────────────────────────────────────────────────────────────────
#  GRig  –  Main facade (matches AcuRig API + GRig extensions)
# ─────────────────────────────────────────────────────────────────────────────

class GRig:
    """
    GRig – Ghost Rigger Interactive Rigging System.

    Inspired by:
    - Reallusion AccuRIG: anatomical guide placement, one-click rig generation
    - MeshyAI: drag-and-drop bone placement, IK chain builder, influence inspector

    Workflow
    --------
    1. grig.detect_profile(model)          → humanoid / quadruped / droid / prop
    2. grig.auto_place_pins(model, profile) → place anatomical pins
    3. [User drags pins in the 3D viewport / adjusts in GRig Panel]
    4. grig.add_pin(name, position)         → manually add a pin
    5. grig.move_pin(name, position)        → drag a pin (mirrors partner auto)
    6. grig.lock_pin(name)                  → prevent auto-mirror from moving it
    7. grig.connect_chain(pins, chain_name) → create a bone chain
    8. grig.enforce_symmetry()              → mirror all L/R pins
    9. grig.generate_skeleton(model)        → create ModelNode bones
    10. grig.apply_weights(model)           → heat-map skin all mesh nodes
    11. grig.save_template(path)            → save to JSON
    12. grig.load_template(path)            → load from JSON
    """

    def __init__(self):
        self._pins:     Dict[str, BonePin]    = {}
        self._chains:   Dict[str, BoneChain]  = {}
        self._profile   = PROFILE_HUMANOID
        self._detector  = ProfileDetector()
        self._placer    = GuidePlacer()
        self.brush      = GRigBrush()
        self.symmetry   = GRigSymmetry()
        self.mask       = BoneMask()
        self._painter   = WeightPainter()
        self._pose_corr = PoseCorrector()
        # Selected pin (for UI highlight)
        self.selected_pin: Optional[str] = None
        # History for undo (list of pin dicts)
        self._history:  List[Dict[str, Any]] = []
        self._max_history = 20

    # ── Step 1: Profile ───────────────────────────────────────────────────────

    def detect_profile(self, model: KotorModel) -> str:
        """Auto-detect rig profile from model geometry and node names."""
        self._profile = self._detector.detect(model)
        log.info(f"GRig.detect_profile: {self._profile}")
        return self._profile

    # ── Step 2: Pin placement ─────────────────────────────────────────────────

    def auto_place_pins(self, model: KotorModel,
                        profile: Optional[str] = None,
                        snap_to_bones: bool = True) -> Dict[str, BonePin]:
        """
        Auto-place anatomical bone pins using profile templates.
        Equivalent to AccuRIG's 'Auto-Place Guides' or MeshyAI's initial bone set.
        """
        if profile is None:
            profile = self._profile
        self._push_history()
        guides = self._placer.place_guides(model, profile, {})
        if snap_to_bones:
            for g in guides.values():
                if not g.locked:
                    self._placer.snap_to_bone(g, model, 0.4)
        # Convert to BonePins
        self._pins = {}
        for name, g in guides.items():
            bp = BonePin.from_rig_guide(g)
            colour = BONE_COLOURS.get(name, (200, 200, 200))
            bp.colour = colour
            self._pins[name] = bp
        # Auto-assign chains
        self._build_default_chains(profile)
        log.info(f"GRig.auto_place_pins: {len(self._pins)} pins placed ({profile})")
        return dict(self._pins)

    def add_pin(self, name: str, position: Tuple[float, float, float],
                parent: Optional[str] = None,
                colour: Optional[Tuple[int, int, int]] = None,
                auto_mirror: bool = True) -> BonePin:
        """
        Add a new bone pin at the given position.
        If auto_mirror=True and name matches a mirror pair, creates the mirrored pin too.
        """
        self._push_history()
        colour = colour or BONE_COLOURS.get(name.lower(), (255, 200, 0))
        pin = BonePin(name=name, position=position, bone_parent=parent, colour=colour)
        self._pins[name] = pin
        if auto_mirror:
            # Check if this pin has a mirror partner defined
            for l_n, r_n in MIRROR_PAIRS.items():
                partner_name = None
                if name.lower() == l_n: partner_name = r_n
                elif name.lower() == r_n: partner_name = l_n
                if partner_name and partner_name not in self._pins:
                    ax, ay, az = position
                    mirror_pos = (-ax, ay, az)
                    partner_colour = BONE_COLOURS.get(partner_name, colour)
                    mirror_pin = BonePin(name=partner_name, position=mirror_pos,
                                        bone_parent=parent, colour=partner_colour,
                                        mirror_of=name)
                    self._pins[partner_name] = mirror_pin
                    pin.mirror_of = partner_name
                    log.debug(f"GRig.add_pin: auto-created mirror '{partner_name}'")
                    break
        return pin

    def move_pin(self, name: str, new_position: Tuple[float, float, float],
                 auto_mirror: bool = True) -> bool:
        """
        Move a pin to a new position.
        If auto_mirror=True, the L/R counterpart updates automatically (like AccuRIG).
        Returns True if pin was found and moved.
        """
        if name not in self._pins:
            return False
        self._push_history()
        pin = self._pins[name]
        if pin.locked:
            log.debug(f"GRig.move_pin: '{name}' is locked – ignoring")
            return False
        pin.position = new_position
        if auto_mirror:
            self.symmetry.mirror_pin(pin, self._pins)
        return True

    def snap_pin_to_mesh(self, name: str, model: KotorModel,
                         radius: float = 0.5) -> bool:
        """Snap pin to nearest mesh vertex. Returns True if snapped."""
        if name not in self._pins:
            return False
        pin = self._pins[name]
        best_dist = float('inf')
        best_pos  = None
        best_vi   = -1
        px, py, pz = pin.position
        for node in model.all_nodes():
            if not node.is_mesh or not node.vertices:
                continue
            for vi, (vx, vy, vz) in enumerate(node.vertices):
                d = (vx-px)**2 + (vy-py)**2 + (vz-pz)**2
                if d < best_dist and d < radius**2:
                    best_dist = d
                    best_pos  = (vx, vy, vz)
                    best_vi   = vi
        if best_pos is not None:
            pin.position = best_pos
            pin.snap_vertex_idx = best_vi
            return True
        return False

    def remove_pin(self, name: str) -> bool:
        """Remove a pin (and its mirror partner if desired)."""
        if name not in self._pins:
            return False
        self._push_history()
        del self._pins[name]
        # Remove from chains
        for chain in self._chains.values():
            chain.remove_pin(name)
        return True

    def lock_pin(self, name: str):
        if name in self._pins:
            self._pins[name].locked = True

    def unlock_pin(self, name: str):
        if name in self._pins:
            self._pins[name].locked = False

    def select_pin(self, name: Optional[str]):
        self.selected_pin = name

    def get_pin(self, name: str) -> Optional[BonePin]:
        return self._pins.get(name)

    def get_all_pins(self) -> Dict[str, BonePin]:
        return dict(self._pins)

    def pin_count(self) -> int:
        return len(self._pins)

    # ── Step 3: Chain Builder ────────────────────────────────────────────────

    def connect_chain(self, pin_names: List[str], chain_name: str,
                      ik_ready: bool = False,
                      colour: Optional[Tuple[int, int, int]] = None) -> BoneChain:
        """
        Create a bone chain from a sequence of pins.
        Automatically assigns parent-child relationships along the chain.
        """
        chain = BoneChain(chain_id=chain_name, pin_names=pin_names[:],
                          ik_ready=ik_ready, colour=colour or (200, 200, 200))
        self._chains[chain_name] = chain
        # Set parent relationships
        for i in range(1, len(pin_names)):
            pname = pin_names[i]
            par   = pin_names[i-1]
            if pname in self._pins:
                self._pins[pname].bone_parent = par
                self._pins[pname].chain_id    = chain_name
            if par in self._pins:
                self._pins[par].chain_id = chain_name
        # Mark IK tip
        if ik_ready and pin_names:
            tip_name = pin_names[-1]
            if tip_name in self._pins:
                self._pins[tip_name].ik_tip = True
        log.info(f"GRig.connect_chain: '{chain_name}' → {pin_names}")
        return chain

    def auto_insert_bone(self, pin_a: str, pin_b: str,
                         new_name: str, t: float = 0.5) -> Optional[BonePin]:
        """
        Insert a new pin at position t (0..1) between pin_a and pin_b.
        Useful for adding elbow / knee pins to a two-bone chain.
        """
        if pin_a not in self._pins or pin_b not in self._pins:
            return None
        pa = self._pins[pin_a].position
        pb = self._pins[pin_b].position
        new_pos = (
            pa[0] + (pb[0]-pa[0])*t,
            pa[1] + (pb[1]-pa[1])*t,
            pa[2] + (pb[2]-pa[2])*t,
        )
        return self.add_pin(new_name, new_pos, parent=pin_a, auto_mirror=False)

    def get_chains(self) -> Dict[str, BoneChain]:
        return dict(self._chains)

    # ── Step 4: Symmetry ─────────────────────────────────────────────────────

    def enforce_symmetry(self, direction: str = 'l_to_r') -> int:
        """Mirror all L/R pins. Returns count of pairs updated."""
        count = self.symmetry.enforce_all(self._pins, direction)
        log.info(f"GRig.enforce_symmetry ({direction}): {count} pairs updated")
        return count

    def mirror_weights_on_model(self, model: KotorModel,
                                direction: str = 'l_to_r') -> int:
        """Mirror vertex weights on all mesh nodes. Returns total vertices mirrored."""
        total = 0
        for node in model.all_nodes():
            if node.is_mesh and node.skin_data:
                total += self.symmetry.mirror_weights(node, direction)
        return total

    # ── Step 5: Skeleton generation ──────────────────────────────────────────

    def generate_skeleton(self, model: KotorModel,
                          pins: Optional[Dict[str, BonePin]] = None) -> KotorModel:
        """
        Generate ModelNode bones from BonePins and attach to model.
        Respects bone_parent hierarchy from pins and chains.
        """
        if pins is None:
            pins = self._pins
        active_pins = {n: p for n, p in pins.items()
                       if n not in self.mask._masked}
        if not active_pins:
            log.warning("GRig.generate_skeleton: no active pins")
            return model

        root = model.root_node
        if root is None:
            root = ModelNode(name='rootdummy', flags=int(NodeFlags.HEADER))
            model.root_node = root

        existing_names = {n.name for n in model.all_nodes()}
        bone_nodes: Dict[str, ModelNode] = {}

        # Create/update bone nodes
        for pname, pin in active_pins.items():
            if pname in existing_names:
                existing = model.find_node(pname)
                if existing:
                    existing.position = pin.position
                    bone_nodes[pname] = existing
                    continue
            bn = ModelNode(name=pname, flags=int(NodeFlags.HEADER),
                           position=pin.position)
            bone_nodes[pname] = bn

        # Wire parent-child
        for pname, pin in active_pins.items():
            par = pin.bone_parent
            if par and par in bone_nodes:
                child  = bone_nodes[pname]
                parent = bone_nodes[par]
                if child not in parent.children:
                    parent.children.append(child)

        # Attach root pin to model root
        root_pin_name = 'root' if 'root' in bone_nodes else next(iter(bone_nodes), None)
        if root_pin_name:
            rn = bone_nodes[root_pin_name]
            if rn not in root.children:
                root.children.append(rn)

        log.info(f"GRig.generate_skeleton: {len(bone_nodes)} bones created/updated")
        return model

    # ── Step 6: Weight application ────────────────────────────────────────────

    def apply_weights(self, model: KotorModel,
                      pins: Optional[Dict[str, BonePin]] = None,
                      mode: BrushMode = BrushMode.HEAT_MAP,
                      smooth_iterations: int = 2) -> int:
        """
        Apply skin weights to all mesh nodes.
        mode: BrushMode.HEAT_MAP (default) or BrushMode.FLOOD
        Returns total vertices weighted.
        """
        if pins is None:
            pins = self._pins
        if mode == BrushMode.HEAT_MAP:
            total = self.brush.apply_heat_map(model, pins, self.mask)
        else:
            total = 0
            for node in model.all_nodes():
                if node.is_mesh and node.vertices:
                    # Flood: assign nearest pin
                    for vi, (vx, vy, vz) in enumerate(node.vertices):
                        nearest = min(pins.values(),
                                      key=lambda p: (p.position[0]-vx)**2 +
                                                    (p.position[1]-vy)**2 +
                                                    (p.position[2]-vz)**2)
                        if nearest.name not in node.bone_map:
                            node.bone_map.append(nearest.name)
                        bi = node.bone_map.index(nearest.name)
                        if vi >= len(node.skin_data):
                            node.skin_data.append(
                                VertexSkinData(influences=[BoneWeight(bi, 1.0)]))
                        else:
                            node.skin_data[vi].influences = [BoneWeight(bi, 1.0)]
                    total += len(node.vertices)

        if smooth_iterations > 0:
            for node in model.all_nodes():
                if node.is_mesh and node.skin_data:
                    self._painter.smooth_weights(node, smooth_iterations)

        log.info(f"GRig.apply_weights: {total} vertices weighted (mode={mode.value})")
        return total

    # ── Influence inspector ───────────────────────────────────────────────────

    def inspect_vertex(self, model: KotorModel, mesh_name: str,
                       vertex_index: int) -> Optional[VertexInfluence]:
        """Get weight info for a specific vertex (for the Influence Inspector)."""
        node = model.find_node(mesh_name)
        if node is None:
            return None
        return VertexInfluence.from_skin_data(vertex_index, node)

    def set_vertex_weight(self, model: KotorModel, mesh_name: str,
                          vertex_index: int, bone_name: str, weight: float) -> bool:
        """
        Set a specific bone's weight on a specific vertex.
        Auto-normalizes all influences on that vertex.
        """
        node = model.find_node(mesh_name)
        if node is None or vertex_index >= len(node.vertices):
            return False
        if bone_name not in node.bone_map:
            node.bone_map.append(bone_name)
        bi = node.bone_map.index(bone_name)
        if vertex_index >= len(node.skin_data):
            node.skin_data = node.skin_data + [
                VertexSkinData() for _ in range(vertex_index + 1 - len(node.skin_data))]
        sd = node.skin_data[vertex_index]
        # Update or add influence
        found = False
        for bw in sd.influences:
            if bw.bone_index == bi:
                bw.weight = weight; found = True; break
        if not found:
            sd.influences.append(BoneWeight(bi, weight))
        if weight > 0:
            sd.normalize()
        else:
            sd.influences = [bw for bw in sd.influences if bw.bone_index != bi]
        return True

    def prune_vertex_weights(self, model: KotorModel, threshold: float = 0.01) -> int:
        """
        Remove all bone influences below threshold from every vertex.
        Returns total influences pruned.
        """
        pruned = 0
        for node in model.all_nodes():
            if not node.is_mesh or not node.skin_data:
                continue
            for sd in node.skin_data:
                old_count = len(sd.influences)
                sd.influences = [bw for bw in sd.influences if bw.weight >= threshold]
                pruned += old_count - len(sd.influences)
                if sd.influences:
                    sd.normalize()
        log.info(f"GRig.prune_vertex_weights: pruned {pruned} influences (threshold={threshold})")
        return pruned

    # ── Weight stats ──────────────────────────────────────────────────────────

    def weight_stats(self, model: KotorModel) -> Dict:
        """Return detailed weight statistics across entire model."""
        total_verts = 0; total_weighted = 0
        node_stats = {}
        bone_usage: Dict[str, int] = {}
        nan_count = 0

        for node in model.all_nodes():
            if not node.is_mesh: continue
            nv = len(node.vertices) if node.vertices else 0
            nw = sum(1 for sd in node.skin_data if sd.influences) if node.skin_data else 0
            avg_infl = 0.0
            if node.skin_data:
                avg_infl = sum(len(sd.influences) for sd in node.skin_data) / max(len(node.skin_data), 1)
                for sd in node.skin_data:
                    for bw in sd.influences:
                        if math.isnan(bw.weight):
                            nan_count += 1
                        bname = (node.bone_map[bw.bone_index]
                                 if bw.bone_index < len(node.bone_map) else f"bone_{bw.bone_index}")
                        bone_usage[bname] = bone_usage.get(bname, 0) + 1
            node_stats[node.name] = {
                'verts': nv, 'weighted': nw, 'avg_influences': round(avg_infl, 2)
            }
            total_verts    += nv
            total_weighted += nw

        return {
            'total_verts':    total_verts,
            'total_weighted': total_weighted,
            'coverage_pct':   round(total_weighted / max(total_verts, 1) * 100, 1),
            'nan_weights':    nan_count,
            'bone_usage':     bone_usage,
            'nodes':          node_stats,
        }

    # ── Bind pose ─────────────────────────────────────────────────────────────

    def set_tpose(self) -> Dict[str, BonePin]:
        """Adjust arm pins to T-pose position."""
        guides = self._pose_corr.apply_tpose(
            {n: p.to_rig_guide() for n, p in self._pins.items()})
        for name, g in guides.items():
            if name in self._pins:
                self._pins[name].position = g.position
        return dict(self._pins)

    def set_apose(self) -> Dict[str, BonePin]:
        """Adjust arm pins to A-pose position."""
        guides = self._pose_corr.apply_apose(
            {n: p.to_rig_guide() for n, p in self._pins.items()})
        for name, g in guides.items():
            if name in self._pins:
                self._pins[name].position = g.position
        return dict(self._pins)

    # ── Template I/O ──────────────────────────────────────────────────────────

    def save_template(self, path: str):
        """Save GRig session to a JSON template file."""
        data = {
            'grig_version': '1.0',
            'profile': self._profile,
            'pins': {name: pin.to_dict() for name, pin in self._pins.items()},
            'chains': {
                cid: {'pin_names': c.pin_names, 'ik_ready': c.ik_ready,
                      'colour': list(c.colour)}
                for cid, c in self._chains.items()
            },
            'masked_bones': self.mask.masked_bones,
            'symmetry_axis': self.symmetry.axis,
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        log.info(f"GRig template saved → {path} ({len(self._pins)} pins)")

    def load_template(self, path: str) -> Dict[str, BonePin]:
        """Load a GRig template from JSON. Returns pin dict."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self._profile = data.get('profile', PROFILE_HUMANOID)
        self._pins = {}
        for name, pd in data.get('pins', {}).items():
            self._pins[name] = BonePin.from_dict(pd)
        self._chains = {}
        for cid, cd in data.get('chains', {}).items():
            self._chains[cid] = BoneChain(
                chain_id  = cid,
                pin_names = cd.get('pin_names', []),
                ik_ready  = cd.get('ik_ready', False),
                colour    = tuple(cd.get('colour', [200, 200, 200])),
            )
        self.mask.clear()
        for bname in data.get('masked_bones', []):
            self.mask.mask(bname)
        self.symmetry.axis = data.get('symmetry_axis', 'x')
        log.info(f"GRig template loaded ← {path} ({len(self._pins)} pins)")
        return dict(self._pins)

    def reset(self):
        """Reset all pins, chains, mask."""
        self._push_history()
        self._pins.clear()
        self._chains.clear()
        self.mask.clear()
        self.selected_pin = None

    # ── Undo ──────────────────────────────────────────────────────────────────

    def _push_history(self):
        """Save current pin state to undo history."""
        snapshot = {name: pin.to_dict() for name, pin in self._pins.items()}
        self._history.append(snapshot)
        if len(self._history) > self._max_history:
            self._history.pop(0)

    def undo(self) -> bool:
        """Restore previous pin state. Returns True if undo was available."""
        if not self._history:
            return False
        snapshot = self._history.pop()
        self._pins = {name: BonePin.from_dict(d) for name, d in snapshot.items()}
        return True

    # ── Quick full rig ────────────────────────────────────────────────────────

    def rig_model_full(self, model: KotorModel,
                       profile: Optional[str] = None,
                       smooth_iterations: int = 2) -> Tuple[KotorModel, Dict]:
        """
        One-shot pipeline: detect → place pins → generate skeleton → apply weights.
        Returns (rigged_model, weight_stats).
        """
        if profile is None:
            profile = self.detect_profile(model)
        self.auto_place_pins(model, profile, snap_to_bones=True)
        self.enforce_symmetry()
        self.generate_skeleton(model)
        self.apply_weights(model, smooth_iterations=smooth_iterations)
        stats = self.weight_stats(model)
        log.info(f"GRig.rig_model_full: {profile}, {len(self._pins)} pins, "
                 f"{stats['total_weighted']}/{stats['total_verts']} weighted")
        return model, stats

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _build_default_chains(self, profile: str):
        """Build default bone chains for the given profile."""
        self._chains.clear()
        if profile in (PROFILE_HUMANOID, PROFILE_DROID):
            self.connect_chain(
                ['root', 'hip', 'stomach', 'chest', 'neck', 'head'],
                'spine', colour=(255, 165, 0))
            if all(n in self._pins for n in ['lshoulder', 'lforearm', 'lhand']):
                self.connect_chain(
                    ['lshoulder', 'lforearm', 'lhand'], 'left_arm',
                    ik_ready=True, colour=(255, 100, 100))
            if all(n in self._pins for n in ['rshoulder', 'rforearm', 'rhand']):
                self.connect_chain(
                    ['rshoulder', 'rforearm', 'rhand'], 'right_arm',
                    ik_ready=True, colour=(100, 100, 255))
            if all(n in self._pins for n in ['lthigh', 'lcalf', 'lankle']):
                self.connect_chain(
                    ['lthigh', 'lcalf', 'lankle', 'ltoebase'], 'left_leg',
                    ik_ready=True, colour=(255, 80, 80))
            if all(n in self._pins for n in ['rthigh', 'rcalf', 'rankle']):
                self.connect_chain(
                    ['rthigh', 'rcalf', 'rankle', 'rtoebase'], 'right_leg',
                    ik_ready=True, colour=(80, 80, 255))
        elif profile == PROFILE_QUADRUPED:
            self.connect_chain(
                ['root', 'hip', 'stomach', 'chest', 'neck', 'head'],
                'spine', colour=(255, 165, 0))
            if 'tail_root' in self._pins:
                self.connect_chain(
                    ['tail_root', 'tail_mid', 'tail_tip'], 'tail',
                    colour=(150, 100, 200))


# ─────────────────────────────────────────────────────────────────────────────
#  GRig Panel Data Model  (for the Tkinter UI in main_window.py)
# ─────────────────────────────────────────────────────────────────────────────

class GRigPanelState:
    """
    Lightweight state object held by the GRig UI panel.
    Bridges GRig engine ↔ Tkinter callbacks.
    """
    def __init__(self):
        self.grig             = GRig()
        self.active_brush     = BrushMode.SPHERE
        self.brush_radius     = 0.3
        self.brush_weight     = 1.0
        self.brush_falloff    = 2.0
        self.smooth_iter      = 2
        self.selected_pin     = None
        self.selected_mesh    = None
        self.selected_vertex  = -1
        self.viewport_3d_pins = True    # draw pins in 3D viewport

    def refresh_from_grig(self):
        self.selected_pin = self.grig.selected_pin
