"""
ClothRig — K1 Cloth / Dangly Mesh Rigging System
=================================================
Ports the K2 dangly-mesh cloth simulation mechanics to KotOR 1 models.

KotOR 1 & 2 DANGLY MESH SPECIFICATION
--------------------------------------
Dangly mesh nodes use the DANGLY flag (0x0100) in the node type bitmask.
The **function pointers** in the binary MDL distinguish dangly meshes:
  K1 dangly = 4216640 / 4216624  (different from trimesh 4216656/4216672)

The binary dangly header (28 bytes, immediately after trimesh header) is:
  +0   constraints_array_offset  uint32  offset to constraint float32 array
  +4   constraints_array_count   uint32
  +8   constraints_array_count2  uint32  (duplicate)
  +12  displacement              float32  max swing amplitude in model units
  +16  tightness                 float32  spring stiffness
  +20  period                    float32  oscillation period in seconds
  +24  unknown                   uint32   always 0

CONSTRAINT VALUES — CRITICAL:
  The constraint array stores one float32 per vertex.
  Range in the binary MDL: 0.0 – 255.0 (NOT 0.0–1.0 as in NWN!).
  0.0   = vertex swings completely freely
  255.0 = vertex is fully pinned to parent bone

  The Revan's Flowing Cape mod uses a vertical gradient:
    top rows (attachment points): 255.0
    bottom hem:                    0.0
  This is why the cape flows — free bottom, pinned top.

INTERNAL REPRESENTATION:
  Internally we store constraints in the 0.0–1.0 normalised range for
  easier maths.  ClothRigExporter.to_mdl_scale() converts to 0.0–255.0
  for binary/ASCII export.

APPLYING TO K1 MODELS:
  1. Set node flags |= NodeFlags.DANGLY  (0x0100)
  2. Set displacement, tightness, period
  3. Generate per-vertex constraints (0.0–1.0 internally)
  4. Export multiplies constraints × 255.0 for MDL binary/ASCII output

Module contents:
  1. ClothRigConfig       — per-mesh cloth parameters
  2. ClothRigPreset       — named presets (Revan cape, robe, belt, etc.)
  3. ClothConstraintPainter — generates per-vertex constraints
  4. ClothRigger          — applies cloth rigging to a ModelNode / KotorModel
  5. ClothRigExporter     — validates and prepares nodes for K1 MDL export
  6. ClothRigPanel        — Tkinter UI panel for the main window
  7. ClothRigSimulator    — lightweight PBD physics preview

Usage (programmatic):
    rigger = ClothRigger()
    rigger.apply_cloth_to_node(node, ClothRigPreset.REVAN_CAPE)

Usage (export to ASCII MDL):
    exporter = ClothRigExporter()
    ok, issues = exporter.validate(node)
    ascii_lines = exporter.to_ascii_mdl_block(node)

Usage (UI):
    panel = ClothRigPanel(parent_frame, get_model=lambda: app.model,
                          on_updated=app._on_model_updated)
    panel.pack(fill='both', expand=True)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Internal imports (lazy to avoid circular deps)
# ─────────────────────────────────────────────────────────────────────────────

def _model_data():
    """Import model_data with fallback for both package and direct sys.path usage."""
    try:
        from ..core.model_data import ModelNode, KotorModel, NodeFlags
        return ModelNode, KotorModel, NodeFlags
    except ImportError:
        from core.qt_core.geometry.model_data import ModelNode, KotorModel, NodeFlags
        return ModelNode, KotorModel, NodeFlags


# ─────────────────────────────────────────────────────────────────────────────
#  Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ClothRigConfig:
    """
    Cloth simulation parameters for a single danglymesh node.
    Maps 1:1 to the MDL dangly fields used by both K1 and K2.
    """
    displacement: float = 0.5   # max swing amplitude (model units)
    tightness:    float = 0.5   # spring stiffness  0=floppy, 1=rigid
    period:       float = 1.0   # oscillation period (seconds)

    # Constraint generation strategy
    # 'vertical'  — top vertices pinned, bottom vertices free (robes/capes)
    # 'cape'      — top 40% fully pinned, bottom 60% cubic ease (Revan-accurate)
    # 'radial'    — centre pinned, edges free (skirts, loin cloth)
    # 'bone_dist' — constraint by distance to nearest pinning bone
    # 'uniform'   — all vertices same constraint (simple cloth)
    # 'manual'    — do not auto-generate, use existing constraints
    constraint_mode: str = 'vertical'
    constraint_pin:  float = 1.0   # constraint value for pinned verts
    constraint_free: float = 0.05  # constraint value for free verts

    def validate(self):
        self.displacement = max(0.01, min(10.0, self.displacement))
        self.tightness    = max(0.01, min(1.0,  self.tightness))
        self.period       = max(0.1,  min(10.0, self.period))
        self.constraint_pin  = max(0.0, min(1.0, self.constraint_pin))
        self.constraint_free = max(0.0, min(1.0, self.constraint_free))

    @property
    def pin_mdl(self) -> float:
        """Constraint pin value scaled to MDL binary range (0–255)."""
        return self.constraint_pin * 255.0

    @property
    def free_mdl(self) -> float:
        """Constraint free value scaled to MDL binary range (0–255)."""
        return self.constraint_free * 255.0


class ClothRigPreset:
    """
    Named presets matching K2 robe/clothing behaviour.
    Each preset is a (name, description, ClothRigConfig).
    """

    # ── Revan's Flowing Cape — reverse-engineered from Sithspecter's mod ──
    # Matches the cape/belt on N_DarthRevan.mdl (K1):
    #   displacement = 0.8  (large swing for dramatic effect)
    #   tightness    = 0.25 (floppy — cape flaps in the wind)
    #   period       = 1.6  (slow oscillation — heavy fabric weight)
    # Constraints: top 40% of verts fully pinned (255), bottom 60% free (0)
    # Using 'cape' mode: top-attached gradient matching N_DarthRevan reference
    REVAN_CAPE = ClothRigConfig(
        displacement=0.80, tightness=0.25, period=1.60,
        constraint_mode='cape', constraint_pin=1.0, constraint_free=0.0,
    )
    REVAN_BELT = ClothRigConfig(
        displacement=0.25, tightness=0.60, period=0.75,
        constraint_mode='radial', constraint_pin=1.0, constraint_free=0.0,
    )
    # Jedi Robe (K1 standard) — matches default K2 robe behaviour
    JEDI_ROBE = ClothRigConfig(
        displacement=0.55, tightness=0.28, period=1.30,
        constraint_mode='vertical', constraint_pin=1.0, constraint_free=0.02,
    )
    # ── Standard clothing presets ──────────────────────────────────────────
    ROBE_LOOSE = ClothRigConfig(
        displacement=0.60, tightness=0.30, period=1.20,
        constraint_mode='vertical', constraint_pin=1.0, constraint_free=0.02,
    )
    ROBE_STIFF = ClothRigConfig(
        displacement=0.30, tightness=0.70, period=0.80,
        constraint_mode='vertical', constraint_pin=1.0, constraint_free=0.10,
    )
    CAPE_LIGHT = ClothRigConfig(
        displacement=0.80, tightness=0.20, period=1.50,
        constraint_mode='vertical', constraint_pin=1.0, constraint_free=0.0,
    )
    CAPE_HEAVY = ClothRigConfig(
        displacement=0.50, tightness=0.45, period=1.10,
        constraint_mode='vertical', constraint_pin=1.0, constraint_free=0.0,
    )
    BELT       = ClothRigConfig(
        displacement=0.15, tightness=0.80, period=0.60,
        constraint_mode='radial', constraint_pin=1.0, constraint_free=0.20,
    )
    SKIRT      = ClothRigConfig(
        displacement=0.55, tightness=0.35, period=1.00,
        constraint_mode='radial', constraint_pin=1.0, constraint_free=0.0,
    )
    SASH       = ClothRigConfig(
        displacement=0.40, tightness=0.40, period=0.90,
        constraint_mode='vertical', constraint_pin=1.0, constraint_free=0.05,
    )
    STIFF_COLLAR = ClothRigConfig(
        displacement=0.10, tightness=0.90, period=0.40,
        constraint_mode='uniform', constraint_pin=0.80, constraint_free=0.80,
    )

    _ALL = {
        "Revan's Cape (K1 reference)":  REVAN_CAPE,
        "Revan's Belt (K1 reference)":  REVAN_BELT,
        "Jedi Robe (K1 standard)":    JEDI_ROBE,
        "Robe (Loose / K2 default)":    ROBE_LOOSE,
        "Robe (Stiff / formal)":        ROBE_STIFF,
        "Cape (Light)":                 CAPE_LIGHT,
        "Cape (Heavy)":                 CAPE_HEAVY,
        "Belt / Loin-cloth":            BELT,
        "Skirt":                        SKIRT,
        "Sash / Scarf":                 SASH,
        "Stiff Collar":                 STIFF_COLLAR,
    }

    @classmethod
    def names(cls) -> List[str]:
        return list(cls._ALL.keys())

    @classmethod
    def get(cls, name: str) -> ClothRigConfig:
        cfg = cls._ALL.get(name)
        if cfg is None:
            return cls.ROBE_LOOSE
        # Return a copy so presets are not mutated
        import copy
        return copy.copy(cfg)


# ─────────────────────────────────────────────────────────────────────────────
#  Constraint painter
# ─────────────────────────────────────────────────────────────────────────────

class ClothConstraintPainter:
    """
    Generates per-vertex constraint values for a danglymesh node.

    INTERNAL NORMALISED RANGE (0.0–1.0):
      1.0 = fully pinned (attached to parent bone, no movement)
      0.0 = completely free (maximum cloth simulation movement)

    MDL BINARY/ASCII EXPORT RANGE (0.0–255.0):
      Use ClothRigExporter.constraints_to_mdl(constraints) to scale.
      Example: 1.0 internal → 255.0 in MDL file

    The Revan's Flowing Cape mod uses the vertical gradient pattern:
      top attachment rows:  255.0  (fully pinned to shoulder/waist bone)
      middle transition:    lerped
      bottom hem:           0.0    (free to swing)
    """

    @staticmethod
    def generate(vertices: List[Tuple[float,float,float]],
                 cfg: ClothRigConfig,
                 pinning_bones: Optional[List[Tuple[float,float,float]]] = None,
                 ) -> List[float]:
        """
        Generate constraints for all vertices according to cfg.constraint_mode.

        vertices       — list of (x, y, z) in node-local space
        cfg            — ClothRigConfig
        pinning_bones  — list of (x, y, z) bone world positions for 'bone_dist' mode

        Returns a list of floats with len == len(vertices).
        """
        n = len(vertices)
        if n == 0:
            return []

        mode = cfg.constraint_mode
        pin  = cfg.constraint_pin
        free = cfg.constraint_free

        if mode == 'vertical':
            return ClothConstraintPainter._vertical(vertices, pin, free)
        elif mode == 'radial':
            return ClothConstraintPainter._radial(vertices, pin, free)
        elif mode == 'bone_dist' and pinning_bones:
            return ClothConstraintPainter._bone_dist(vertices, pinning_bones, pin, free)
        elif mode == 'cape':
            return ClothConstraintPainter._cape_gradient(vertices, pin, free)
        elif mode == 'uniform':
            # All vertices get the same mid-point constraint
            mid = (pin + free) * 0.5
            return [mid] * n
        else:
            # manual / fallback — return default 0.5 if no constraints yet set
            return [0.5] * n

    @staticmethod
    def _vertical(verts, pin: float, free: float) -> List[float]:
        """
        Top vertices (high Z) → pinned.  Bottom vertices (low Z) → free.
        Lerp in between.  Matches K2 robe/cloak behaviour and the
        Revan's Flowing Cape mod constraint pattern.

        For capes/robes the top 30% is typically fully pinned,
        the middle 40% lerps, and the bottom 30% is fully free.
        This 3-zone approach gives crisper pinning than a pure linear lerp.
        """
        zvals = [v[2] for v in verts]
        z_min, z_max = min(zvals), max(zvals)
        z_range = z_max - z_min
        if z_range < 1e-6:
            return [0.5] * len(verts)
        result = []
        PIN_ZONE  = 0.70   # top 30% → fully pinned
        FREE_ZONE = 0.30   # bottom 30% → fully free
        for v in verts:
            t = (v[2] - z_min) / z_range   # 0.0 at bottom, 1.0 at top
            if t >= PIN_ZONE:
                c = pin
            elif t <= FREE_ZONE:
                c = free
            else:
                # Smooth S-curve lerp in the middle zone
                s = (t - FREE_ZONE) / (PIN_ZONE - FREE_ZONE)  # 0–1 in middle
                s = s * s * (3 - 2 * s)   # smoothstep
                c = free + s * (pin - free)
            result.append(max(0.0, min(1.0, c)))
        return result

    @staticmethod
    def _radial(verts, pin: float, free: float) -> List[float]:
        """
        Centre XY → pinned.  Outer edge → free.  For skirts/belts.
        """
        if not verts:
            return []
        cx = sum(v[0] for v in verts) / len(verts)
        cy = sum(v[1] for v in verts) / len(verts)
        dists = [math.hypot(v[0]-cx, v[1]-cy) for v in verts]
        d_max = max(dists) or 1.0
        result = []
        for d in dists:
            t = d / d_max   # 0=centre, 1=edge
            c = pin + t * (free - pin)
            result.append(max(0.0, min(1.0, c)))
        return result

    @staticmethod
    def _bone_dist(verts, bones, pin: float, free: float) -> List[float]:
        """
        Vertices close to a pinning bone → high constraint.
        Vertices far from all bones → low constraint.
        """
        result = []
        for v in verts:
            min_d = min(
                math.sqrt((v[0]-b[0])**2+(v[1]-b[1])**2+(v[2]-b[2])**2)
                for b in bones
            )
            # Normalise distance (heuristic: 0.5 model units = fully pinned)
            t = min(1.0, min_d / 0.5)
            c = pin + t * (free - pin)
            result.append(max(0.0, min(1.0, c)))
        return result

    @staticmethod
    def _cape_gradient(verts, pin: float, free: float) -> List[float]:
        """
        Cape-specific gradient: top 40% of vertices fully pinned (attachment rows),
        bottom 60% eases from pin to free using a smooth cubic curve.

        This closely matches the observed constraint distribution in N_DarthRevan's
        flowing cape MDL (from Sithspecter's mod and the later DiePutinDie fix).

        The resulting animation: cape hangs naturally from the shoulders, with
        the bottom hem swinging freely while the top stays attached.
        """
        zvals = [v[2] for v in verts]
        z_min, z_max = min(zvals), max(zvals)
        z_range = z_max - z_min
        if z_range < 1e-6:
            return [pin] * len(verts)
        result = []
        for v in verts:
            t = (v[2] - z_min) / z_range   # 0.0=bottom (free), 1.0=top (pinned)
            if t >= 0.40:
                # Top 60%: fully pinned (attachment rows)
                c = pin
            else:
                # Bottom 40%: smooth cubic easing from pin to free
                t2 = t / 0.40   # remap 0..0.40 → 0..1
                t_curved = t2 * t2 * (3.0 - 2.0 * t2)
                c = free + t_curved * (pin - free)
            result.append(max(0.0, min(1.0, c)))
        return result


# ─────────────────────────────────────────────────────────────────────────────
#  ClothRigger — applies cloth rigging to model nodes
# ─────────────────────────────────────────────────────────────────────────────

class ClothRigger:
    """
    Applies K2-style cloth (danglymesh) rigging to K1 model nodes.

    The process:
    1. Find candidate mesh nodes (robes, clothing) by name pattern / selection
    2. Change the node flag from MESH (0x0021) → MESH|DANGLY (0x0121)
    3. Set displacement, tightness, period from the ClothRigConfig
    4. Generate per-vertex constraint values using ClothConstraintPainter
    5. Write back to the node's dangly_constraints list
    """

    # Node name patterns that indicate cloth geometry
    # Includes K1-specific names from N_DarthRevan (cape/belt) analysis
    CLOTH_NAME_PATTERNS = [
        'robe', 'cloak', 'cloth', 'cape', 'sash', 'skirt', 'belt',
        'pant', 'coat', 'tunic', 'shirt', 'vest', 'tabard', 'garb',
        'outfit', 'wear', 'mantle', 'habit', 'gown',
        # KotOR-specific naming conventions
        'mrobe', 'frobe', 'robe01', 'robe02', 'robe1', 'robe2',
        'robe_g', 'cloth_g', 'cape_g',
        # Revan / Darth Revan model nodes (from N_DarthRevan.mdl)
        'revan', 'darthrevan', 'dark_jedi',
        # Jedi/Sith robe abbreviations used in KotOR 1 models
        'jrobe', 'srobe', 'lrobe',
    ]

    def __init__(self):
        self._history: List[Dict[str, Any]] = []   # undo stack

    # ── Public API ────────────────────────────────────────────────────────

    def apply_cloth_to_node(
        self,
        node: 'ModelNode',
        cfg: Optional[ClothRigConfig] = None,
        pinning_bones: Optional[List[Tuple[float,float,float]]] = None,
    ) -> bool:
        """
        Apply cloth rigging to a single mesh node.

        node           — the ModelNode to convert to danglymesh
        cfg            — ClothRigConfig; defaults to ROBE_LOOSE preset
        pinning_bones  — optional list of bone world positions for 'bone_dist' mode

        Returns True on success.
        """
        ModelNode, _, NodeFlags = _model_data()

        if not node.is_mesh:
            log.warning("ClothRigger: node '%s' is not a mesh node — skipped", node.name)
            return False

        if cfg is None:
            cfg = ClothRigPreset.ROBE_LOOSE

        cfg.validate()

        # Save undo state
        self._push_undo(node)

        # ── Step 1: set DANGLY flag ───────────────────────────────────────
        node.flags = node.flags | int(NodeFlags.DANGLY)

        # ── Step 2: set cloth parameters ─────────────────────────────────
        node.dangly_displacement = cfg.displacement
        node.dangly_tightness    = cfg.tightness
        node.dangly_period       = cfg.period

        # ── Step 3: generate constraints ─────────────────────────────────
        if cfg.constraint_mode != 'manual' or not node.dangly_constraints:
            constraints = ClothConstraintPainter.generate(
                node.vertices, cfg, pinning_bones)
            node.dangly_constraints = constraints

        log.info(
            "ClothRigger: applied cloth to node '%s' — "
            "disp=%.2f tight=%.2f period=%.2f mode=%s verts=%d",
            node.name, cfg.displacement, cfg.tightness, cfg.period,
            cfg.constraint_mode, len(node.vertices),
        )
        return True

    def apply_cloth_to_model(
        self,
        model: 'KotorModel',
        cfg: Optional[ClothRigConfig] = None,
        node_names: Optional[List[str]] = None,
        auto_detect: bool = True,
    ) -> List[str]:
        """
        Apply cloth rigging to matching nodes in an entire model.

        model       — the KotorModel to process
        cfg         — ClothRigConfig to apply
        node_names  — explicit list of node names to target (overrides auto_detect)
        auto_detect — if True and node_names is None, use CLOTH_NAME_PATTERNS

        Returns list of node names that were modified.
        """
        if model is None or model.root_node is None:
            return []

        targets: List['ModelNode'] = []

        if node_names is not None:
            # Explicit selection
            name_set = {n.lower() for n in node_names}
            for node in model.all_nodes():
                if node.name.lower() in name_set and node.is_mesh:
                    targets.append(node)
        elif auto_detect:
            targets = self.find_cloth_candidates(model)
        else:
            return []

        # Get pinning bone positions (hip, chest, stomach)
        pinning_bones = self._get_pinning_bones(model)

        modified = []
        for node in targets:
            if self.apply_cloth_to_node(node, cfg, pinning_bones):
                modified.append(node.name)

        log.info("ClothRigger: modified %d node(s): %s", len(modified), modified)
        return modified

    def remove_cloth_from_node(self, node: 'ModelNode') -> bool:
        """Remove cloth rigging from a node (revert danglymesh to trimesh)."""
        _, _, NodeFlags = _model_data()

        if not node.is_dangly:
            return False

        self._push_undo(node)
        # Clear DANGLY flag
        node.flags = node.flags & ~int(NodeFlags.DANGLY)
        node.dangly_constraints = []
        log.info("ClothRigger: removed cloth from node '%s'", node.name)
        return True

    def find_cloth_candidates(self, model: 'KotorModel') -> List['ModelNode']:
        """
        Return mesh nodes that look like cloth geometry (robes, clothing).
        Uses CLOTH_NAME_PATTERNS and heuristics from K2 model analysis.
        """
        candidates = []
        patterns = [p.lower() for p in self.CLOTH_NAME_PATTERNS]

        for node in model.all_nodes():
            if not node.is_mesh or node.is_skin:
                continue  # cloth nodes are trimesh/dangly, not skin
            if not node.vertices:
                continue  # skip empty nodes

            name = node.name.lower()

            # Pattern match
            if any(p in name for p in patterns):
                candidates.append(node)
                continue

            # Heuristic: non-skin mesh with some vertices that is a child of a
            # torso/hip/chest bone — likely clothing geometry
            if node.parent:
                pname = node.parent.name.lower()
                if any(p in pname for p in ('torso', 'chest', 'hip', 'stomach', 'waist')):
                    if 5 <= len(node.vertices) <= 2000:
                        candidates.append(node)

        return candidates

    def undo_last(self, node: 'ModelNode') -> bool:
        """Undo the last cloth operation on the given node."""
        for state in reversed(self._history):
            if state['name'] == node.name:
                node.flags                = state['flags']
                node.dangly_displacement  = state['displacement']
                node.dangly_tightness     = state['tightness']
                node.dangly_period        = state['period']
                node.dangly_constraints   = list(state['constraints'])
                self._history.remove(state)
                log.info("ClothRigger: undone cloth on '%s'", node.name)
                return True
        return False

    def get_cloth_summary(self, model: 'KotorModel') -> Dict[str, Any]:
        """Return a summary of cloth nodes in the model."""
        cloth_nodes = []
        for node in model.all_nodes():
            if node.is_dangly:
                cloth_nodes.append({
                    'name':         node.name,
                    'verts':        len(node.vertices),
                    'displacement': node.dangly_displacement,
                    'tightness':    node.dangly_tightness,
                    'period':       node.dangly_period,
                    'constraints':  len(node.dangly_constraints),
                })
        return {
            'total_cloth_nodes': len(cloth_nodes),
            'nodes':             cloth_nodes,
        }

    # ── Helpers ───────────────────────────────────────────────────────────

    def _get_pinning_bones(self, model) -> List[Tuple[float,float,float]]:
        """Return world positions of key pinning bones (hip, chest, stomach)."""
        PINNING_NAMES = {'torso', 'chest', 'stomach', 'hip', 'waist',
                         'body', 'pelvis', 'ribcage'}
        bones = []
        for node in model.all_nodes():
            if node.name.lower() in PINNING_NAMES:
                bones.append(node.position)
        return bones or [(0.0, 0.0, 0.9)]   # fallback: ~waist height

    def _push_undo(self, node: 'ModelNode'):
        self._history.append({
            'name':         node.name,
            'flags':        node.flags,
            'displacement': node.dangly_displacement,
            'tightness':    node.dangly_tightness,
            'period':       node.dangly_period,
            'constraints':  list(node.dangly_constraints),
        })
        # Keep last 50 undo states
        if len(self._history) > 50:
            self._history.pop(0)


# ─────────────────────────────────────────────────────────────────────────────
#  ClothRigExporter — validates and converts cloth nodes for K1 MDL export
# ─────────────────────────────────────────────────────────────────────────────

class ClothRigExporter:
    """
    Validates danglymesh nodes and prepares them for K1 MDL ASCII/binary export.

    KEY CONSTRAINT SCALE CONVERSION:
      Internal storage (ClothConstraintPainter, ClothRigConfig): 0.0–1.0
      MDL binary & ASCII output (what KotOR engine reads):        0.0–255.0

    The KotOR game engine reads constraints as raw float32 values.
    The Revan's Flowing Cape mod uses values like 255.0 (fully pinned)
    and 0.0 (fully free) in the actual MDL file.

    This exporter handles the 0.0–1.0 → 0.0–255.0 scaling automatically.
    """

    MDL_CONSTRAINT_SCALE = 255.0

    @staticmethod
    def constraints_to_mdl(constraints: List[float]) -> List[float]:
        """
        Convert internal 0.0–1.0 constraints to MDL 0.0–255.0 scale.

        Example:
            internal  [1.0, 0.75, 0.5, 0.25, 0.0]
            → mdl     [255.0, 191.25, 127.5, 63.75, 0.0]
        """
        return [max(0.0, min(255.0, c * 255.0)) for c in constraints]

    @staticmethod
    def constraints_from_mdl(constraints: List[float]) -> List[float]:
        """
        Convert MDL 0.0–255.0 constraints to internal 0.0–1.0 scale.
        """
        return [max(0.0, min(1.0, c / 255.0)) for c in constraints]

    def validate(self, node: 'ModelNode') -> tuple:
        """
        Validate a node for K1 cloth export readiness.

        Returns (ok: bool, issues: List[str]).

        Checks:
          - Node has DANGLY flag set
          - displacement, tightness, period are in valid ranges
          - dangly_constraints length matches vertex count
          - At least some pinned vertices (max constraint > 0.1)
          - At least some free vertices (min constraint < 0.9) for non-stiff
        """
        issues = []

        # Check DANGLY flag
        try:
            try:
                from ..core.model_data import NodeFlags
            except ImportError:
                from core.qt_core.geometry.model_data import NodeFlags
            if not (node.flags & NodeFlags.DANGLY):
                issues.append("DANGLY flag not set — node is not a danglymesh")
        except Exception:
            pass

        # Check parameters
        if not (0.01 <= node.dangly_displacement <= 10.0):
            issues.append(
                f"displacement={node.dangly_displacement:.3f} out of range [0.01, 10.0]")
        if not (0.01 <= node.dangly_tightness <= 1.0):
            issues.append(
                f"tightness={node.dangly_tightness:.3f} out of range [0.01, 1.0]")
        if not (0.1 <= node.dangly_period <= 10.0):
            issues.append(
                f"period={node.dangly_period:.3f} out of range [0.1, 10.0]")

        # Check constraints
        n_verts = len(node.vertices) if node.vertices else 0
        n_csts  = len(node.dangly_constraints)

        if n_csts == 0:
            issues.append("No constraints set — use ClothRigger.apply_cloth_to_node() first")
        elif n_csts != n_verts:
            issues.append(
                f"Constraint count ({n_csts}) != vertex count ({n_verts}) — "
                f"regenerate constraints")
        else:
            max_c = max(node.dangly_constraints)
            min_c = min(node.dangly_constraints)
            if max_c < 0.05:
                issues.append(
                    "All constraints ≈ 0.0 — no vertices are pinned; "
                    "the cloth will fly off the model")
            if min_c > 0.95 and node.dangly_tightness < 0.9:
                issues.append(
                    "All constraints ≈ 1.0 — no free vertices; "
                    "cloth will not simulate (use uniform preset for stiff cloth)")

        return (len(issues) == 0, issues)

    def to_ascii_mdl_block(self, node: 'ModelNode') -> List[str]:
        """
        Generate the ASCII MDL dangly block for a node (MDLOps-compatible format).

        Constraints are output in the 0.0–255.0 range required by KotOR.
        """
        lines = [
            f"  displacement {node.dangly_displacement:.4f}",
            f"  tightness {node.dangly_tightness:.4f}",
            f"  period {node.dangly_period:.4f}",
        ]
        csts = self.constraints_to_mdl(node.dangly_constraints)
        if csts:
            lines.append(f"  constraints {len(csts)}")
            for c in csts:
                lines.append(f"    {c:.4f}")
        return lines

    def export_summary(self, node: 'ModelNode') -> str:
        """Return a human-readable export summary for the node."""
        ok, issues = self.validate(node)
        n_csts = len(node.dangly_constraints)
        if n_csts:
            mdl_csts = self.constraints_to_mdl(node.dangly_constraints)
            avg = sum(mdl_csts) / n_csts
            pin_count  = sum(1 for c in mdl_csts if c >= 230.0)
            free_count = sum(1 for c in mdl_csts if c <= 25.0)
        else:
            avg = pin_count = free_count = 0

        lines = [
            f"Node:         {node.name}",
            f"Status:       {'✓ Ready for export' if ok else '✗ Issues found'}",
            f"displacement: {node.dangly_displacement:.3f}",
            f"tightness:    {node.dangly_tightness:.3f}",
            f"period:       {node.dangly_period:.3f}",
            f"Constraints:  {n_csts} verts  "
            f"(avg {avg:.1f}/255  pinned={pin_count}  free={free_count})",
        ]
        if issues:
            lines.append("Issues:")
            for iss in issues:
                lines.append(f"  ! {iss}")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
#  ClothRigDialog — Qt-or-headless preset chooser  (M3/T301)
# ─────────────────────────────────────────────────────────────────────────────
#
#  History
#  -------
#  Prior to milestone M3 this file hosted a 620-line ``ClothRigPanel`` class
#  built directly on tkinter (preset combobox, sliders, listbox, radio
#  buttons, etc.). It was used only by ``src/gui/main_window.py`` — the
#  frozen legacy Tk shell that M3/T302 deletes — and pulled tkinter into
#  the autorig import graph for every consumer.
#
#  The active Qt cloth UI now lives in ``src/gui/qt_retarget_window.py``
#  under the "Cloth Rigging..." tools menu (see lines 61, 92, 261-387 of
#  that file). That dialog drives the same engine classes defined above
#  (``ClothRigger``, ``ClothRigPreset``, ``ClothRigConfig``,
#  ``ClothRigSimulator``) directly and does not need a re-usable panel
#  module any more.
#
#  What this block provides
#  ------------------------
#  A tiny backend-agnostic helper, ``run_cloth_preset_dialog``, that picks
#  a cloth preset for callers that previously relied on Tk popups
#  (``ClothRigPanel.__init__`` line 788, ``ClothRigPanel._make_slider``
#  line 1204, ``ClothRigPanel._make_small_slider`` line 1216 in the legacy
#  module). The helper:
#
#    1.  Uses ``QInputDialog`` if a ``QCoreApplication`` is live.
#    2.  Returns the requested default preset (or first available preset)
#        without raising when running headless / unit-tested.
#
#  The result is a plain ``ClothPresetChoice`` dataclass — never a Tk
#  variable, never a Qt widget — so cloth headless tests keep passing and
#  every public surface of this module stays Tk-free.

from dataclasses import dataclass as _dataclass


@_dataclass(frozen=True)
class ClothPresetChoice:
    """Result of ``run_cloth_preset_dialog`` — backend-agnostic.

    Attributes
    ----------
    preset_name:
        Selected preset string (one of ``ClothRigPreset.names()``).
    accepted:
        ``True`` if the user pressed OK / accepted the default,
        ``False`` if the dialog was cancelled.
    """

    preset_name: str
    accepted: bool = True


def _qt_application_running() -> bool:
    """Return ``True`` iff a ``QCoreApplication`` instance is live.

    Mirrors the Qt-first marshaling pattern used in ``src/ipc/client.py``
    and ``src/ipc/server.py`` after M0/T002.
    """
    try:
        from PySide6.QtCore import QCoreApplication  # noqa: PLC0415
        return QCoreApplication.instance() is not None
    except Exception:
        return False


def run_cloth_preset_dialog(
    parent=None,
    default_preset: Optional[str] = None,
    title: str = "Cloth Rigging Preset",
    message: str = "Pick a cloth preset to apply to the selected node(s):",
) -> ClothPresetChoice:
    """Pick a cloth preset via Qt when available, default otherwise.

    Replaces the three Tk popup sites that lived in the deleted
    ``ClothRigPanel`` class. Parameters mirror what those popups used to
    accept; the return is always a plain ``ClothPresetChoice`` so headless
    cloth tests run without an event loop.
    """
    available = ClothRigPreset.names()
    if not available:
        return ClothPresetChoice(preset_name="", accepted=False)

    chosen_default = default_preset if default_preset in available else available[0]

    if not _qt_application_running():
        # Headless / unit-test path: hand back the requested default.
        return ClothPresetChoice(preset_name=chosen_default, accepted=True)

    try:
        from PySide6.QtWidgets import QInputDialog  # noqa: PLC0415
        idx = available.index(chosen_default)
        name, ok = QInputDialog.getItem(
            parent, title, message, available, idx, False,
        )
        if not ok or not name:
            return ClothPresetChoice(preset_name=chosen_default, accepted=False)
        return ClothPresetChoice(preset_name=name, accepted=True)
    except Exception:
        # If Qt is importable but the dialog blows up (e.g. running under
        # an offscreen platform plugin that disallows modal dialogs), fall
        # back to the headless default rather than raise.
        return ClothPresetChoice(preset_name=chosen_default, accepted=True)


def confirm_cloth_action(
    parent=None,
    title: str = "Cloth Rigging",
    message: str = "Apply cloth rig to the selected node(s)?",
) -> bool:
    """Yes/no confirmation that does the right thing under Qt or headless.

    Used in place of the second and third Tk popup sites in the deleted
    ``ClothRigPanel`` (the slider rows that previously invoked
    ``messagebox.askyesno``). Headless callers always receive ``True`` so
    automated cloth rigging flows run unattended.
    """
    if not _qt_application_running():
        return True

    try:
        from PySide6.QtWidgets import QMessageBox  # noqa: PLC0415
        reply = QMessageBox.question(
            parent, title, message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return reply == QMessageBox.StandardButton.Yes
    except Exception:
        return True


# ─────────────────────────────────────────────────────────────────────────────
#  ClothRigSimulator — lightweight position-based dynamics (PBD) preview
# ─────────────────────────────────────────────────────────────────────────────

class ClothRigSimulator:
    """
    Lightweight cloth physics preview using Position-Based Dynamics (PBD).

    Simulates KotOR's dangly-mesh behaviour for viewport preview without
    needing the actual game engine.  Useful for previewing cloth rigs before
    export.

    The simulation mirrors KotOR's approach:
      - Vertices with constraint ≈ 1.0 are fully pinned (no movement)
      - Vertices with constraint ≈ 0.0 swing freely under gravity + damping
      - Spring constraints between adjacent vertices maintain mesh shape
      - displacement parameter caps maximum vertex displacement

    Usage:
        sim = ClothRigSimulator(node, gravity=(0, 0, -9.8), dt=1/30)
        for _ in range(steps):
            sim.step()
        deformed_verts = sim.positions
    """

    GRAVITY        = (0.0, 0.0, -9.8)   # world-space gravity (Z-up)
    DAMPING        = 0.98                # velocity damping per step
    ITERATIONS     = 4                   # constraint solver iterations per step

    def __init__(self, node: 'ModelNode',
                 gravity: tuple = GRAVITY,
                 dt: float = 1.0 / 30.0):
        """
        Initialise simulator from a danglymesh ModelNode.

        node    — must have vertices, dangly_constraints, and mesh face data
        gravity — 3-tuple (gx, gy, gz) world-space acceleration
        dt      — time step in seconds (default 1/30 for 30 fps preview)
        """
        self._node      = node
        self._gravity   = gravity
        self._dt        = dt

        verts = list(node.vertices)
        n     = len(verts)

        # Current positions and previous positions (for Verlet integration)
        self.positions  = [list(v) for v in verts]
        self._prev_pos  = [list(v) for v in verts]

        # Constraints: 1.0 = pinned, 0.0 = free
        raw = list(node.dangly_constraints) if node.dangly_constraints else [0.5] * n
        if len(raw) < n:
            raw.extend([0.5] * (n - len(raw)))
        self._constraints = raw[:n]

        # Cloth parameters from node
        self._disp      = getattr(node, 'dangly_displacement', 0.5)
        self._tightness = getattr(node, 'dangly_tightness',    0.5)
        self._period    = getattr(node, 'dangly_period',        1.0)

        # Build edge springs from mesh faces
        self._springs: List[Tuple[int, int, float]] = []  # (i, j, rest_length)
        self._build_springs(node.faces, verts)

        # Rest positions (for displacement capping)
        self._rest_pos = [list(v) for v in verts]

    # ── Public API ────────────────────────────────────────────────────────

    def step(self):
        """Advance simulation by one time step (dt seconds)."""
        dt = self._dt
        gx, gy, gz = self._gravity
        n = len(self.positions)

        # Tightness affects how strongly pinned verts resist displacement
        # High tightness = fast spring return to rest
        spring_stiffness = self._tightness * 0.8 + 0.1

        # ── 1. Verlet integration ────────────────────────────────────────
        for i in range(n):
            c = self._constraints[i]
            if c >= 0.999:
                continue   # fully pinned — no movement

            pos  = self.positions[i]
            prev = self._prev_pos[i]

            # Velocity estimate from last two positions
            vx = (pos[0] - prev[0]) * self.DAMPING
            vy = (pos[1] - prev[1]) * self.DAMPING
            vz = (pos[2] - prev[2]) * self.DAMPING

            # Gravity weighted by (1 - constraint): pinned verts resist more
            free_factor = 1.0 - c
            ax = gx * free_factor
            ay = gy * free_factor
            az = gz * free_factor

            # Store previous, update position
            self._prev_pos[i] = pos[:]
            pos[0] += vx + ax * dt * dt
            pos[1] += vy + ay * dt * dt
            pos[2] += vz + az * dt * dt

        # ── 2. Spring constraint solving (iterative) ─────────────────────
        for _ in range(self.ITERATIONS):
            for i, j, rest in self._springs:
                # Skip if both fully pinned
                ci = self._constraints[i]
                cj = self._constraints[j]
                if ci >= 0.999 and cj >= 0.999:
                    continue

                pi = self.positions[i]
                pj = self.positions[j]
                dx = pj[0] - pi[0]
                dy = pj[1] - pi[1]
                dz = pj[2] - pi[2]
                dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                if dist < 1e-9:
                    continue

                # Correction vector
                diff = (dist - rest) / dist
                corr_x = dx * diff * 0.5 * spring_stiffness
                corr_y = dy * diff * 0.5 * spring_stiffness
                corr_z = dz * diff * 0.5 * spring_stiffness

                # Distribute correction inversely proportional to pin constraint
                wi = 1.0 - ci   # free weight for i
                wj = 1.0 - cj   # free weight for j
                total_w = wi + wj
                if total_w < 1e-9:
                    continue
                fi = wi / total_w
                fj = wj / total_w

                if ci < 0.999:
                    self.positions[i][0] += corr_x * fi
                    self.positions[i][1] += corr_y * fi
                    self.positions[i][2] += corr_z * fi
                if cj < 0.999:
                    self.positions[j][0] -= corr_x * fj
                    self.positions[j][1] -= corr_y * fj
                    self.positions[j][2] -= corr_z * fj

        # ── 3. Displacement capping ───────────────────────────────────────
        # KotOR caps cloth vertex displacement at node.dangly_displacement
        for i in range(n):
            if self._constraints[i] >= 0.999:
                continue
            rest = self._rest_pos[i]
            pos  = self.positions[i]
            dx   = pos[0] - rest[0]
            dy   = pos[1] - rest[1]
            dz   = pos[2] - rest[2]
            dist = math.sqrt(dx*dx + dy*dy + dz*dz)
            if dist > self._disp:
                scale = self._disp / dist
                pos[0] = rest[0] + dx * scale
                pos[1] = rest[1] + dy * scale
                pos[2] = rest[2] + dz * scale

    def reset(self):
        """Reset simulation to bind-pose rest positions."""
        self.positions  = [list(v) for v in self._rest_pos]
        self._prev_pos  = [list(v) for v in self._rest_pos]

    def kinetic_energy(self) -> float:
        """Estimate total kinetic energy of all free vertices.

        Uses the Verlet velocity estimate: v ≈ (pos - prev_pos) / dt.
        Returns the sum of 0.5 * |v|^2 over all non-pinned vertices.
        Useful as a convergence / settling indicator for the UI.
        """
        dt = self._dt if self._dt > 1e-9 else (1.0 / 30.0)
        ke = 0.0
        for i, (pos, prev) in enumerate(zip(self.positions, self._prev_pos)):
            if self._constraints[i] >= 0.999:
                continue
            vx = (pos[0] - prev[0]) / dt
            vy = (pos[1] - prev[1]) / dt
            vz = (pos[2] - prev[2]) / dt
            ke += 0.5 * (vx*vx + vy*vy + vz*vz)
        return ke

    def total_displacement(self) -> float:
        """Return the total Euclidean displacement of all vertices from rest pose."""
        import math as _m
        total = 0.0
        for pos, rest in zip(self.positions, self._rest_pos):
            dx = pos[0] - rest[0]
            dy = pos[1] - rest[1]
            dz = pos[2] - rest[2]
            total += _m.sqrt(dx*dx + dy*dy + dz*dz)
        return total

    def apply_wind(self, direction: tuple = (0.0, 1.0, 0.0), strength: float = 2.0):
        """Apply a wind impulse (one-shot velocity delta to free vertices)."""
        wx, wy, wz = direction
        for i, pos in enumerate(self.positions):
            c = self._constraints[i]
            if c >= 0.999:
                continue
            free = 1.0 - c
            # Perturb previous position to create an implicit velocity
            self._prev_pos[i][0] -= wx * strength * free * self._dt
            self._prev_pos[i][1] -= wy * strength * free * self._dt
            self._prev_pos[i][2] -= wz * strength * free * self._dt

    # ── Internal helpers ──────────────────────────────────────────────────

    def _build_springs(self, faces, verts):
        """Build unique edge springs from mesh faces."""
        seen: set = set()
        for face in (faces or []):
            if len(face) < 3:
                continue
            for k in range(len(face)):
                i = face[k]
                j = face[(k + 1) % len(face)]
                if i == j or i >= len(verts) or j >= len(verts):
                    continue
                edge = (min(i, j), max(i, j))
                if edge in seen:
                    continue
                seen.add(edge)
                vi, vj = verts[i], verts[j]
                rest = math.sqrt(
                    (vi[0]-vj[0])**2 +
                    (vi[1]-vj[1])**2 +
                    (vi[2]-vj[2])**2
                )
                self._springs.append((i, j, rest))
