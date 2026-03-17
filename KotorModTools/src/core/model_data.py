"""
Core KotOR Model Data Structures
Handles KotOR 1 & 2 MDL/MDX binary models, ASCII MDL text format,
all node types: trimesh, skin, dangly, lightsaber, emitter, light, dummy, reference
"""

import struct, math, logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Any
from enum import IntFlag, IntEnum

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
#  Enums / Constants
# ──────────────────────────────────────────────────────────────

class NodeFlags(IntFlag):
    HEADER    = 0x0001
    LIGHT     = 0x0002
    EMITTER   = 0x0004
    CAMERA    = 0x0008
    REFERENCE = 0x0010
    MESH      = 0x0020
    SKIN      = 0x0040
    ANIM      = 0x0080
    DANGLY    = 0x0100
    AABB      = 0x0200
    SABER     = 0x0800

class GameVersion(IntEnum):
    K1 = 1
    K2 = 2

class ModelClassification(IntEnum):
    EFFECT    = 0
    TILE      = 1
    CHARACTER = 2
    DOOR      = 4

GEOM_FP_K1 = (4273776, 4216096)
GEOM_FP_K2 = (4285200, 4216320)

# ──────────────────────────────────────────────────────────────
#  Bone / Joint Data  (used by the auto-rigger)
# ──────────────────────────────────────────────────────────────

@dataclass
class BoneWeight:
    bone_index: int   = 0
    weight:     float = 0.0

@dataclass
class VertexSkinData:
    """Up to 4 bone influences per vertex (KotOR limit)"""
    influences: List[BoneWeight] = field(default_factory=list)

    def normalize(self):
        total = sum(b.weight for b in self.influences)
        if total > 0:
            for b in self.influences:
                b.weight /= total

    def to_packed(self) -> Tuple[Tuple[float,...], Tuple[int,...]]:
        padded = (self.influences + [BoneWeight(0,0.0)]*4)[:4]
        return (tuple(b.weight for b in padded),
                tuple(b.bone_index for b in padded))

# ──────────────────────────────────────────────────────────────
#  Model Node
# ──────────────────────────────────────────────────────────────

@dataclass
class ModelNode:
    name:     str   = "node"
    flags:    int   = int(NodeFlags.HEADER)
    index:    int   = 0
    number:   int   = 0

    # Transform
    position: Tuple[float,float,float]       = (0.0, 0.0, 0.0)
    rotation: Tuple[float,float,float,float] = (0.0, 0.0, 0.0, 1.0)  # xyzw quaternion

    # Graph
    parent:   Optional['ModelNode']   = field(default=None, repr=False)
    children: List['ModelNode']       = field(default_factory=list)

    # ── Mesh ──
    vertices:     List[Tuple[float,float,float]] = field(default_factory=list)
    normals:      List[Tuple[float,float,float]] = field(default_factory=list)
    tangents:     List[Tuple[float,float,float]] = field(default_factory=list)
    uvs:          List[Tuple[float,float]]       = field(default_factory=list)
    uvs_lm:       List[Tuple[float,float]]       = field(default_factory=list)
    faces:        List[Tuple[int,int,int]]       = field(default_factory=list)
    face_mats:    List[int]                      = field(default_factory=list)

    # Material
    texture:      str   = ""
    lightmap:     str   = ""
    bump_map:     str   = ""
    diffuse:      Tuple[float,float,float] = (0.8, 0.8, 0.8)
    ambient:      Tuple[float,float,float] = (0.2, 0.2, 0.2)
    specular:     Tuple[float,float,float] = (0.0, 0.0, 0.0)
    shininess:    float = 0.0
    alpha:        float = 1.0
    has_shadow:   bool  = True
    render:       bool  = True
    selfillum:    Tuple[float,float,float] = (0.0, 0.0, 0.0)
    transparency_hint: int = 0
    has_lightmap: bool  = False
    beaming:      bool  = False
    background_geometry: bool = False
    rotate_texture: bool = False

    # ── Skin weights ──
    skin_data:    List[VertexSkinData] = field(default_factory=list)
    bone_map:     List[str]            = field(default_factory=list)  # bone_map[i] = bone node name

    # ── Dangly ──
    dangly_constraints: List[float] = field(default_factory=list)
    dangly_displacement: float = 0.5
    dangly_tightness:    float = 0.5
    dangly_period:       float = 1.0

    # ── Light ──
    light_radius:     float = 5.0
    light_color:      Tuple[float,float,float] = (1.0, 1.0, 1.0)
    light_multiplier: float = 1.0
    light_shadow:     bool  = True
    light_flare:      bool  = False
    light_fading:     bool  = False
    light_ambient_only: bool = False
    light_dynamic:    int   = 0

    # ── Emitter ──
    emitter_params: Dict[str, Any] = field(default_factory=dict)

    # Bounding sphere / box
    bb_min: Tuple[float,float,float] = (0.0, 0.0, 0.0)
    bb_max: Tuple[float,float,float] = (0.0, 0.0, 0.0)
    radius: float = 0.0

    # Controllers (animation keyframes)
    controllers: List[Dict] = field(default_factory=list)

    # ── Flags helpers ──
    @property
    def is_mesh(self):   return bool(self.flags & NodeFlags.MESH)
    @property
    def is_skin(self):   return bool(self.flags & NodeFlags.SKIN)
    @property
    def is_dangly(self): return bool(self.flags & NodeFlags.DANGLY)
    @property
    def is_light(self):  return bool(self.flags & NodeFlags.LIGHT)
    @property
    def is_saber(self):  return bool(self.flags & NodeFlags.SABER)
    @property
    def is_emitter(self):return bool(self.flags & NodeFlags.EMITTER)
    @property
    def is_dummy(self):
        return self.flags == int(NodeFlags.HEADER)

    @property
    def type_label(self) -> str:
        if self.is_saber:   return "lightsaber"
        if self.is_skin:    return "skin"
        if self.is_dangly:  return "danglymesh"
        if self.is_mesh:    return "trimesh"
        if self.is_light:   return "light"
        if self.is_emitter: return "emitter"
        if self.flags & NodeFlags.REFERENCE: return "reference"
        if self.flags & NodeFlags.AABB:      return "aabb"
        return "dummy"

    def compute_bounds(self):
        if not self.vertices:
            return
        xs = [v[0] for v in self.vertices]
        ys = [v[1] for v in self.vertices]
        zs = [v[2] for v in self.vertices]
        self.bb_min = (min(xs), min(ys), min(zs))
        self.bb_max = (max(xs), max(ys), max(zs))
        cx = (min(xs)+max(xs))/2
        cy = (min(ys)+max(ys))/2
        cz = (min(zs)+max(zs))/2
        self.radius = max(math.sqrt((v[0]-cx)**2+(v[1]-cy)**2+(v[2]-cz)**2)
                         for v in self.vertices)

    def world_position(self) -> Tuple[float,float,float]:
        """Accumulate position up the hierarchy (no rotation applied – simplified)"""
        px, py, pz = self.position
        node = self.parent
        while node:
            px += node.position[0]
            py += node.position[1]
            pz += node.position[2]
            node = node.parent
        return (px, py, pz)

    def clone_shallow(self) -> 'ModelNode':
        n = ModelNode(name=self.name, flags=self.flags, index=self.index)
        n.position = self.position
        n.rotation = self.rotation
        n.texture  = self.texture
        n.diffuse  = self.diffuse
        n.ambient  = self.ambient
        return n

# ──────────────────────────────────────────────────────────────
#  Animation
# ──────────────────────────────────────────────────────────────

@dataclass
class AnimEvent:
    time: float = 0.0
    name: str   = ""

@dataclass
class Animation:
    name:            str   = "default"
    length:          float = 0.0
    transition_time: float = 0.25
    anim_root:       str   = ""
    events:          List[AnimEvent]  = field(default_factory=list)
    nodes:           List[ModelNode]  = field(default_factory=list)

# ──────────────────────────────────────────────────────────────
#  Full Model
# ──────────────────────────────────────────────────────────────

@dataclass
class KotorModel:
    name:           str            = "unnamed"
    supermodel:     str            = "NULL"
    classification: str            = "character"
    game_version:   GameVersion    = GameVersion.K1
    model_type:     int            = int(ModelClassification.CHARACTER)
    disable_fog:    bool           = False
    anim_scale:     float          = 1.0

    root_node:   Optional[ModelNode] = None
    animations:  List[Animation]     = field(default_factory=list)

    bb_min:  Tuple[float,float,float] = (0.0, 0.0, 0.0)
    bb_max:  Tuple[float,float,float] = (0.0, 0.0, 0.0)
    radius:  float = 0.0

    # File paths
    mdl_path: str = ""
    mdx_path: str = ""

    def all_nodes(self) -> List[ModelNode]:
        result = []
        def _walk(n):
            result.append(n)
            for c in n.children: _walk(c)
        if self.root_node: _walk(self.root_node)
        return result

    def mesh_nodes(self) -> List[ModelNode]:
        return [n for n in self.all_nodes() if n.is_mesh]

    def bone_nodes(self) -> List[ModelNode]:
        return [n for n in self.all_nodes() if n.is_dummy and not n.is_mesh]

    def find_node(self, name: str) -> Optional[ModelNode]:
        nl = name.lower()
        for n in self.all_nodes():
            if n.name.lower() == nl: return n
        return None

    def compute_bounds(self):
        verts = []
        for n in self.mesh_nodes():
            verts.extend(n.vertices)
        if not verts: return
        xs=[v[0] for v in verts]; ys=[v[1] for v in verts]; zs=[v[2] for v in verts]
        self.bb_min = (min(xs), min(ys), min(zs))
        self.bb_max = (max(xs), max(ys), max(zs))
        cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
        self.radius = max(math.sqrt((v[0]-cx)**2+(v[1]-cy)**2+(v[2]-cz)**2) for v in verts)

    def node_count(self) -> int:
        return len(self.all_nodes())

    def texture_list(self) -> List[str]:
        seen = set()
        result = []
        for n in self.mesh_nodes():
            for t in [n.texture, n.lightmap, n.bump_map]:
                if t and t not in seen:
                    seen.add(t); result.append(t)
        return result
