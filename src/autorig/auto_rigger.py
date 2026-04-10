"""
Auto-Rigger for KotOR Models
=============================
Provides automatic bone assignment based on KotOR's standard skeleton hierarchy.

KotOR Character Skeleton (from k_sup_males / k_sup_females supermodels):
  Root -> Pelvis -> Stomach -> Chest -> Neck -> Head
                                              -> LShoulder -> LForearm -> LHand
                                              -> RShoulder -> RForearm -> RHand
                           -> LThigh -> LCalf -> LAnkle -> LToebase
                           -> RThigh -> RCalf -> RAnkle -> RToebase

The auto-rigger v2:
1. Vertex region detection by height bands
2. Per-region bone candidate pre-filtering  
3. Heat-map weights with region bias
4. Weight-painting colour preview generator
5. Weight statistics per node
6. Improved FBX bone name mapping
"""

import math, logging, colorsys
from typing import List, Dict, Optional, Tuple
try:
    from ..core.model_data import KotorModel, ModelNode, NodeFlags, VertexSkinData, BoneWeight
except ImportError:
    from core.model_data import KotorModel, ModelNode, NodeFlags, VertexSkinData, BoneWeight  # type: ignore[no-redef]

log = logging.getLogger(__name__)


# ── Standard KotOR Humanoid Skeleton Template ──────────────────────────────

HUMANOID_BONES = [
    ("torsocam",  None,         (0.0,  0.0,  0.0 )),
    ("hip",       "torsocam",   (0.0,  0.0,  0.52)),
    ("lthigh",    "hip",        (-0.1, 0.0,  0.45)),
    ("lcalf",     "lthigh",     (-0.1, 0.0,  0.27)),
    ("lankle",    "lcalf",      (-0.1, 0.0,  0.06)),
    ("ltoebase",  "lankle",     (-0.1, 0.04, 0.02)),
    ("rthigh",    "hip",        ( 0.1, 0.0,  0.45)),
    ("rcalf",     "rthigh",     ( 0.1, 0.0,  0.27)),
    ("rankle",    "rcalf",      ( 0.1, 0.0,  0.06)),
    ("rtoebase",  "rankle",     ( 0.1, 0.04, 0.02)),
    ("stomach",   "hip",        (0.0,  0.0,  0.58)),
    ("chest",     "stomach",    (0.0,  0.0,  0.65)),
    ("neck",      "chest",      (0.0,  0.0,  0.75)),
    ("head",      "neck",       (0.0,  0.0,  0.85)),
    ("lshoulder", "chest",      (-0.12,0.0,  0.70)),
    ("lforearm",  "lshoulder",  (-0.22,0.0,  0.65)),
    ("lhand",     "lforearm",   (-0.30,0.0,  0.60)),
    ("lfinger01", "lhand",      (-0.33,0.0,  0.59)),
    ("lfinger02", "lhand",      (-0.33,0.02, 0.59)),
    ("rshoulder", "chest",      ( 0.12,0.0,  0.70)),
    ("rforearm",  "rshoulder",  ( 0.22,0.0,  0.65)),
    ("rhand",     "rforearm",   ( 0.30,0.0,  0.60)),
    ("rfinger01", "rhand",      ( 0.33,0.0,  0.59)),
    ("rfinger02", "rhand",      ( 0.33,0.02, 0.59)),
]

CREATURE_BONES = [
    ("torsocam",  None,       (0.0,  0.0, 0.0 )),
    ("hip",       "torsocam", (0.0,  0.0, 0.40)),
    ("chest",     "hip",      (0.0,  0.0, 0.60)),
    ("neck",      "chest",    (0.0,  0.0, 0.72)),
    ("head",      "neck",     (0.0,  0.0, 0.85)),
    ("lleg1",     "hip",      (-0.15,0.0, 0.35)),
    ("lleg2",     "lleg1",    (-0.12,0.0, 0.15)),
    ("lfoot",     "lleg2",    (-0.10,0.0, 0.04)),
    ("rleg1",     "hip",      ( 0.15,0.0, 0.35)),
    ("rleg2",     "rleg1",    ( 0.12,0.0, 0.15)),
    ("rfoot",     "rleg2",    ( 0.10,0.0, 0.04)),
    ("larm1",     "chest",    (-0.20,0.0, 0.62)),
    ("larm2",     "larm1",    (-0.28,0.0, 0.55)),
    ("rarm1",     "chest",    ( 0.20,0.0, 0.62)),
    ("rarm2",     "rarm1",    ( 0.28,0.0, 0.55)),
]

ATTACHMENT_NODES = [
    ("lhand_attach",  "lhand",  (0.0, 0.0, 0.0)),
    ("rhand_attach",  "rhand",  (0.0, 0.0, 0.0)),
    ("head_attach",   "head",   (0.0, 0.0, 0.0)),
    ("chest_attach",  "chest",  (0.0, 0.0, 0.0)),
    ("back_attach",   "chest",  (0.0,-0.15,0.0)),
]

REGION_BONES = {
    "head":        ["head", "neck"],
    "neck":        ["neck", "head", "chest"],
    "chest":       ["chest", "stomach", "lshoulder", "rshoulder"],
    "stomach":     ["stomach", "chest", "hip"],
    "hip":         ["hip", "stomach", "lthigh", "rthigh"],
    "l_upper_arm": ["lshoulder", "chest"],
    "l_lower_arm": ["lforearm", "lshoulder", "lhand"],
    "l_hand":      ["lhand", "lforearm", "lfinger01", "lfinger02"],
    "r_upper_arm": ["rshoulder", "chest"],
    "r_lower_arm": ["rforearm", "rshoulder", "rhand"],
    "r_hand":      ["rhand", "rforearm", "rfinger01", "rfinger02"],
    "l_upper_leg": ["lthigh", "hip"],
    "l_lower_leg": ["lcalf", "lthigh", "lankle"],
    "l_foot":      ["lankle", "lcalf", "ltoebase"],
    "r_upper_leg": ["rthigh", "hip"],
    "r_lower_leg": ["rcalf", "rthigh", "rankle"],
    "r_foot":      ["rankle", "rcalf", "rtoebase"],
}

# Bone colour map for weight-paint preview
_BONE_HUE_MAP = {
    "torsocam": 0.0,  "hip": 0.05,  "stomach": 0.10, "chest": 0.15,
    "neck":     0.20, "head": 0.25,
    "lshoulder":0.33, "lforearm":0.38, "lhand":0.42,
    "lfinger01":0.44, "lfinger02":0.45,
    "rshoulder":0.55, "rforearm":0.60, "rhand":0.63,
    "rfinger01":0.65, "rfinger02":0.66,
    "lthigh":   0.72, "lcalf":0.76, "lankle":0.79, "ltoebase":0.80,
    "rthigh":   0.87, "rcalf":0.90, "rankle":0.93, "rtoebase":0.95,
    "lleg1":    0.72, "lleg2":0.76, "lfoot":0.80,
    "rleg1":    0.87, "rleg2":0.90, "rfoot":0.95,
    "larm1":    0.33, "larm2":0.38, "rarm1":0.55, "rarm2":0.60,
}

def _bone_colour(name: str) -> Tuple[int, int, int]:
    key = name.lower()
    hue = _BONE_HUE_MAP.get(key, (hash(key) & 0xFFFF) / 0xFFFF)
    r, g, b = colorsys.hsv_to_rgb(hue, 0.85, 1.0)
    return (int(r*255), int(g*255), int(b*255))


# ── Bone Node builder ──────────────────────────────────────────────────────

def build_skeleton(model_height: float = 1.8, template: str = "humanoid") -> Dict[str, ModelNode]:
    tmpl = HUMANOID_BONES if template == "humanoid" else CREATURE_BONES
    nodes: Dict[str, ModelNode] = {}
    for bone_name, parent_name, norm_pos in tmpl:
        node = ModelNode(name=bone_name, flags=int(NodeFlags.HEADER))
        wx = norm_pos[0] * model_height
        wy = norm_pos[1] * model_height
        wz = norm_pos[2] * model_height
        node.position = (wx, wy, wz)
        if parent_name and parent_name in nodes:
            p = nodes[parent_name]
            node.parent = p
            p.children.append(node)
            px, py, pz = p.position
            node.position = (wx-px, wy-py, wz-pz)
        nodes[bone_name] = node
    return nodes


# ──────────────────────────────────────────────────────────────────────
#  Rig Template data classes  (used by RigExtractor + AutoRigger)
# ──────────────────────────────────────────────────────────────────────

class BoneInfo:
    """Lightweight representation of one bone from a KotOR model."""
    def __init__(self, name: str, parent: Optional[str],
                 position: Tuple[float,float,float],
                 world_pos: Tuple[float,float,float],
                 rotation: Tuple[float,float,float,float]):
        self.name      = name
        self.parent    = parent
        self.position  = position
        self.world_pos = world_pos
        self.rotation  = rotation

    def __repr__(self):
        return f"BoneInfo({self.name!r}, parent={self.parent!r})"


class SkinMeshInfo:
    """Info about one skinned mesh node."""
    def __init__(self, node_name: str, texture: str,
                 bone_map: List[str], vert_count: int, skin_data: list):
        self.node_name  = node_name
        self.texture    = texture
        self.bone_map   = bone_map
        self.vert_count = vert_count
        self.skin_data  = skin_data


class RigTemplate:
    """
    A rig template extracted from an existing KotOR model.
    Can be applied to a new model via AutoRigger.rig_from_template().
    """
    def __init__(self, source_model: str,
                 bones: Dict[str, BoneInfo],
                 height: float,
                 bb_min: Tuple[float,float,float],
                 bb_max: Tuple[float,float,float],
                 skinned_meshes: List[SkinMeshInfo]):
        self.source_model   = source_model
        self.bones          = bones
        self.height         = height
        self.bb_min         = bb_min
        self.bb_max         = bb_max
        self.skinned_meshes = skinned_meshes

    @property
    def bone_names(self) -> List[str]:
        return list(self.bones.keys())

    def world_positions(self) -> Dict[str, Tuple[float,float,float]]:
        """Return normalized (0..1) world positions of all bones."""
        h = self.height or 1.0
        return {name: (b.world_pos[0]/h, b.world_pos[1]/h, b.world_pos[2]/h)
                for name, b in self.bones.items()}

    def summary(self) -> str:
        lines = [
            f"RigTemplate from '{self.source_model}':",
            f"  Bones:          {len(self.bones)}",
            f"  Model height:   {self.height:.3f}",
            f"  Skinned meshes: {len(self.skinned_meshes)}",
            f"  BB: ({self.bb_min[0]:.2f},{self.bb_min[1]:.2f},{self.bb_min[2]:.2f})"
            f" → ({self.bb_max[0]:.2f},{self.bb_max[1]:.2f},{self.bb_max[2]:.2f})",
            "",
            "  Bone hierarchy:",
        ]
        # Sort by depth (parents first)
        for name, bi in self.bones.items():
            indent = "    " if bi.parent else "  "
            lines.append(f"{indent}{name}  parent={bi.parent or 'ROOT'}"
                         f"  pos=({bi.position[0]:.2f},{bi.position[1]:.2f},{bi.position[2]:.2f})")
        return '\n'.join(lines)

    # ── Serialization ─────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize template to a JSON-serializable dict."""
        return {
            'source_model': self.source_model,
            'height': self.height,
            'bb_min': list(self.bb_min),
            'bb_max': list(self.bb_max),
            'bones': {
                name: {
                    'name':       bi.name,
                    'parent':     bi.parent,
                    'position':   list(bi.position),
                    'world_pos':  list(bi.world_pos),
                    'rotation':   list(bi.rotation) if hasattr(bi, 'rotation') else [0,0,0,1],
                    'is_dummy':   getattr(bi, 'is_dummy', True),
                }
                for name, bi in self.bones.items()
            },
            'skinned_meshes': [
                {
                    'node_name':   sm.node_name,
                    'texture':     getattr(sm, 'texture', ''),
                    'bone_map':    list(sm.bone_map),
                    'vert_count':  getattr(sm, 'vert_count', 0),
                }
                for sm in self.skinned_meshes
            ],
        }

    def save(self, path: str):
        """Save template to a .json file."""
        import json
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)
        log.info(f"RigTemplate saved → {path}")

    @classmethod
    def load(cls, path: str) -> 'RigTemplate':
        """Load template from a .json file."""
        import json
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        bones = {}
        for name, bd in data['bones'].items():
            bones[name] = BoneInfo(
                name=bd['name'],
                parent=bd.get('parent'),
                position=tuple(bd['position']),
                world_pos=tuple(bd['world_pos']),
                rotation=tuple(bd.get('rotation', [0,0,0,1])),
            )
        skinned_meshes = [
            SkinMeshInfo(
                node_name=sm['node_name'],
                texture=sm.get('texture', ''),
                bone_map=sm['bone_map'],
                vert_count=sm.get('vert_count', 0),
                skin_data=[],
            )
            for sm in data.get('skinned_meshes', [])
        ]
        return cls(
            source_model=data['source_model'],
            bones=bones,
            height=data['height'],
            bb_min=tuple(data['bb_min']),
            bb_max=tuple(data['bb_max']),
            skinned_meshes=skinned_meshes,
        )


# ──────────────────────────────────────────────────────────────────────
#  Rig Extractor  – reads bone hierarchy from existing KotOR model
# ──────────────────────────────────────────────────────────────────────

class RigExtractor:
    """
    Extracts the bone hierarchy and skin weight structure from an existing
    KotOR model so it can be re-applied to a new mesh.

    Usage:
        extractor  = RigExtractor()
        template   = extractor.extract(source_model)   # get RigTemplate
        rigger     = AutoRigger()
        new_model  = rigger.rig_from_template(target_model, template)
    """

    def extract(self, source_model: KotorModel) -> RigTemplate:
        """
        Extract a RigTemplate from a KotOR model.

        KotOR models have two kinds of "bones":
          a) Dummy nodes (is_dummy=True) – the standard armature nodes used in
             humanoid supermodel skeletons (hip, chest, lthigh, etc.)
          b) Mesh nodes referenced in bone_maps – KotOR creatures (bantha,
             gammorean, rancor, etc.) use actual mesh nodes as deform bones.
             The bone_map of a skin mesh lists node NAMES, and those names may
             refer to any node in the hierarchy.

        This extractor collects BOTH kinds so the template faithfully represents
        the source model's complete deform skeleton.
        """
        bones: Dict[str, BoneInfo] = {}
        all_nodes_by_name: Dict[str, ModelNode] = {}

        # First pass: index every node by name
        def _index(node: ModelNode):
            all_nodes_by_name[node.name] = node
            for ch in node.children:
                _index(ch)

        if source_model.root_node:
            _index(source_model.root_node)

        # Collect bone names referenced in any skin-mesh bone_map
        deform_bone_names: set = set()
        skinned_meshes_raw: List[SkinMeshInfo] = []
        for n in source_model.mesh_nodes():
            if n.is_skin and n.bone_map:
                for bname in n.bone_map:
                    if bname and bname.strip():
                        deform_bone_names.add(bname)
                if n.skin_data:
                    skinned_meshes_raw.append(SkinMeshInfo(
                        node_name  = n.name,
                        texture    = n.texture,
                        bone_map   = list(n.bone_map),
                        vert_count = len(n.vertices),
                        skin_data  = n.skin_data,
                    ))

        def _add_bone(node: ModelNode):
            """Register node as a bone in the template."""
            if node.name in bones:
                return
            # Determine parent: walk up until we find another bone or root
            parent_name = None
            p = node.parent
            while p is not None:
                if p.name in deform_bone_names or p.is_dummy:
                    parent_name = p.name
                    break
                p = p.parent
            wp = node.world_position()
            bones[node.name] = BoneInfo(
                name      = node.name,
                parent    = parent_name,
                position  = node.position,
                world_pos = wp,
                rotation  = node.rotation,
            )

        # Second pass: collect dummy nodes (standard armature)
        def _walk_dummies(node: ModelNode):
            if node.is_dummy:
                _add_bone(node)
            for ch in node.children:
                _walk_dummies(ch)

        if source_model.root_node:
            _walk_dummies(source_model.root_node)

        # Third pass: add any deform bones from bone_maps not already captured
        for bname in sorted(deform_bone_names):
            if bname in all_nodes_by_name and bname not in bones:
                _add_bone(all_nodes_by_name[bname])

        # If NO bones found at all (pure prop / no armature), add root node
        if not bones and source_model.root_node:
            _add_bone(source_model.root_node)

        source_model.compute_bounds()
        bb_min  = source_model.bb_min
        bb_max  = source_model.bb_max
        height  = max(0.01, bb_max[2] - bb_min[2])

        tmpl = RigTemplate(
            source_model   = source_model.name,
            bones          = bones,
            height         = height,
            bb_min         = bb_min,
            bb_max         = bb_max,
            skinned_meshes = skinned_meshes_raw,
        )
        log.info(f"Extracted rig from '{source_model.name}': "
                 f"{len(bones)} bones, {len(skinned_meshes_raw)} skinned meshes")
        return tmpl


# ── Auto-Rigger ────────────────────────────────────────────────────────────


class AutoRigger:
    """
    Automatically rigs mesh nodes to a KotOR humanoid skeleton.
    v2 improvements: region-biased weight assignment, weight preview, stats.

    Usage (convenience):
        rigger = AutoRigger()
        rigged_model = rigger.auto_rig(model)          # returns same model, mutated
        rigged_model = rigger.rig_model(model)         # same, explicit API
    """

    MAX_INFLUENCES = 4

    def __init__(self, model: Optional[KotorModel] = None):
        """
        Create an AutoRigger.

        Args:
            model: Optional KotorModel to rig immediately. If provided,
                   calling auto_rig() with no arguments will use it.
        """
        self._default_model = model
        self.template:         str   = "humanoid"
        self.model_height:     float = 1.8
        self.heat_falloff:     float = 4.0
        self.min_weight:       float = 0.01
        self._bone_world_pos:  Dict[str, Tuple[float,float,float]] = {}
        self._bone_name_list:  List[str] = []
        self._model_bb_min:    Tuple[float,float,float] = (0,0,0)
        self._model_bb_max:    Tuple[float,float,float] = (0,0,0)

    def auto_rig(self, model: Optional[KotorModel] = None,
                 template: str = "humanoid") -> KotorModel:
        """
        Convenience wrapper: auto-rig ``model`` (or the model passed at init).

        Returns the same model with skin weights applied.
        Raises ValueError if no model is available.
        """
        m = model or self._default_model
        if m is None:
            raise ValueError("auto_rig(): no model provided")
        return self.rig_model(m, template=template)

    def rig_model(self, model: KotorModel,
                  template: str = "humanoid",
                  existing_bones: Optional[Dict[str, ModelNode]] = None) -> KotorModel:
        self.template = template
        model.compute_bounds()
        bmin = model.bb_min; bmax = model.bb_max
        self._model_bb_min = bmin
        self._model_bb_max = bmax
        self.model_height = max(0.1, bmax[2] - bmin[2])
        model_center = ((bmin[0]+bmax[0])/2, (bmin[1]+bmax[1])/2, bmin[2])

        bones = existing_bones or build_skeleton(self.model_height, template)

        root_bone = bones.get("torsocam") or bones.get(list(bones.keys())[0])
        if root_bone and root_bone.parent is None:
            cx, cy, cz = model_center
            root_bone.position = (cx, cy, cz)

        self._compute_world_positions(bones)
        self._bone_name_list = list(bones.keys())

        if model.root_node:
            existing = {c.name for c in model.root_node.children}
            if root_bone.name not in existing:
                root_bone.parent = model.root_node
                model.root_node.children.insert(0, root_bone)
        else:
            model.root_node = root_bone

        for node in model.mesh_nodes():
            self._skin_node(node, bones, self._bone_name_list)

        log.info(f"Auto-rigged '{model.name}' with {len(bones)} bones "
                 f"(template={template}, falloff={self.heat_falloff})")
        return model

    def generate_weight_preview(self, node: ModelNode,
                                 image_size: int = 256) -> Optional[bytes]:
        """Generate weight-painting PNG preview for a skin mesh node."""
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            return None
        if not node.vertices or not node.uvs or not node.skin_data:
            return None
        img = Image.new('RGB', (image_size, image_size), (20, 20, 20))
        draw = ImageDraw.Draw(img)
        for face in node.faces:
            if len(face) < 3: continue
            try:
                pts = []; colours = []
                for vi in face:
                    if vi >= len(node.uvs) or vi >= len(node.skin_data): break
                    u, v = node.uvs[vi]
                    px = int((u % 1.0) * image_size)
                    py = int((1.0 - (v % 1.0)) * image_size)
                    pts.append((px, py))
                    sd = node.skin_data[vi]
                    cr = cg = cb = 0
                    for inf in sd.influences[:4]:
                        if inf.weight > 0:
                            bname = (self._bone_name_list[inf.bone_index]
                                     if inf.bone_index < len(self._bone_name_list)
                                     else "unknown")
                            bc = _bone_colour(bname)
                            cr += int(bc[0] * inf.weight)
                            cg += int(bc[1] * inf.weight)
                            cb += int(bc[2] * inf.weight)
                    colours.append((max(0,min(255,cr)), max(0,min(255,cg)), max(0,min(255,cb))))
                if len(pts) == 3:
                    avg = (sum(c[0] for c in colours)//3,
                           sum(c[1] for c in colours)//3,
                           sum(c[2] for c in colours)//3)
                    draw.polygon(pts, fill=avg)
            except Exception:
                pass
        import io; buf = io.BytesIO(); img.save(buf, 'PNG'); return buf.getvalue()

    def get_weight_stats(self, model: KotorModel) -> Dict[str, Dict]:
        stats = {}
        for node in model.mesh_nodes():
            if not node.is_skin or not node.skin_data: continue
            inf_counts = [len(sd.influences) for sd in node.skin_data]
            avg = sum(inf_counts) / len(inf_counts) if inf_counts else 0
            bone_usage: Dict[str, float] = {}
            for sd in node.skin_data:
                for inf in sd.influences:
                    if inf.bone_index < len(node.bone_map):
                        bname = node.bone_map[inf.bone_index]
                        bone_usage[bname] = bone_usage.get(bname, 0.0) + inf.weight
            stats[node.name] = {
                'total_verts':       len(node.skin_data),
                'avg_influences':    avg,
                'max_influences':    max(inf_counts) if inf_counts else 0,
                'zero_weight_verts': sum(1 for c in inf_counts if c == 0),
                'bone_usage':        bone_usage,
            }
        return stats

    def _compute_world_positions(self, bones: Dict[str, ModelNode]):
        self._bone_world_pos.clear()
        for name, bone in bones.items():
            pos = list(bone.position)
            parent = bone.parent
            while parent and parent.name in bones:
                pos[0] += parent.position[0]
                pos[1] += parent.position[1]
                pos[2] += parent.position[2]
                parent = parent.parent
            self._bone_world_pos[name] = (pos[0], pos[1], pos[2])

    def _vertex_region(self, vz: float) -> str:
        bmin_z = self._model_bb_min[2]; bmax_z = self._model_bb_max[2]
        h = bmax_z - bmin_z
        if h < 1e-6: return "hip"
        t = (vz - bmin_z) / h
        if t < 0.08: return "foot"
        if t < 0.20: return "lower_leg"
        if t < 0.38: return "upper_leg"
        if t < 0.56: return "hip"
        if t < 0.62: return "stomach"
        if t < 0.72: return "chest"
        if t < 0.78: return "shoulder"
        if t < 0.82: return "neck"
        return "head"

    def _region_candidate_bones(self, region: str, vx: float,
                                  bone_name_list: List[str]) -> List[str]:
        side = 'l' if vx < -0.01 else ('r' if vx > 0.01 else None)
        region_map = {
            "head":      ["head", "neck"],
            "neck":      ["neck", "head", "chest"],
            "shoulder":  (["lshoulder","lforearm"] if side=='l'
                          else ["rshoulder","rforearm"] if side=='r'
                          else ["lshoulder","rshoulder"]),
            "chest":     ["chest", "stomach", "neck", "lshoulder", "rshoulder"],
            "stomach":   ["stomach", "chest", "hip"],
            "hip":       ["hip", "stomach", "lthigh", "rthigh"],
            "upper_leg": (["lthigh","hip","lcalf"] if side=='l'
                          else ["rthigh","hip","rcalf"] if side=='r'
                          else ["lthigh","rthigh","hip"]),
            "lower_leg": (["lcalf","lthigh","lankle"] if side=='l'
                          else ["rcalf","rthigh","rankle"] if side=='r'
                          else ["lcalf","rcalf"]),
            "foot":      (["lankle","lcalf","ltoebase"] if side=='l'
                          else ["rankle","rcalf","rtoebase"] if side=='r'
                          else ["lankle","rankle"]),
        }
        cands = region_map.get(region, list(bone_name_list))
        return [b for b in cands if b in bone_name_list]

    def _skin_node(self, node: ModelNode, bones: Dict[str, ModelNode],
                   bone_name_list: List[str]):
        """
        Assign skin weights to every vertex in *node* using a heat-diffusion
        style falloff.

        Improvements over the raw inverse-distance approach:
        - Gaussian heat kernel:  w = exp(-dist² * σ²) where σ = heat_falloff
        - Region-biased bone candidates keep topologically correct weights
        - Zero-weight guard: every vertex gets at least one influence
        - Normalisation performed twice (pre/post pruning) so weights sum to 1
        """
        if not node.vertices: return
        node.flags |= int(NodeFlags.SKIN)
        node.bone_map  = bone_name_list[:]
        node.skin_data = []
        bone_idx = {name: i for i, name in enumerate(bone_name_list)}

        # Pre-compute squared falloff coefficient: Gaussian w = exp(-k * d²)
        # heat_falloff=4 → tight, 2 → diffuse.  We map it to σ² = falloff²
        sigma_sq = self.heat_falloff ** 2

        for vx, vy, vz in node.vertices:
            region = self._vertex_region(vz)
            cand_names = self._region_candidate_bones(region, vx, bone_name_list)
            # Always include full bone list as fallback so no vertex is uninfluenced
            if len(cand_names) < self.MAX_INFLUENCES:
                # Extend with nearby global candidates (sorted by height proximity)
                global_sorted = sorted(
                    bone_name_list,
                    key=lambda b: (
                        abs(self._bone_world_pos.get(b, (0, 0, 0))[2] - vz)
                    )
                )
                for gb in global_sorted:
                    if gb not in cand_names:
                        cand_names.append(gb)
                    if len(cand_names) >= self.MAX_INFLUENCES * 2:
                        break

            dists: List[Tuple[float, str]] = []
            for bname in cand_names:
                if bname not in self._bone_world_pos: continue
                bpos = self._bone_world_pos[bname]
                dx = vx - bpos[0]; dy = vy - bpos[1]; dz = vz - bpos[2]
                d2 = dx*dx + dy*dy + dz*dz
                # Gaussian heat kernel
                w = math.exp(-d2 * sigma_sq / max(0.001, d2 + 0.25))
                dists.append((d2, bname, w))

            # Sort by ascending distance
            dists.sort(key=lambda x: x[0])

            influences = []
            for d2, bname, w in dists[:self.MAX_INFLUENCES * 2]:
                influences.append(BoneWeight(bone_idx.get(bname, 0), w))

            # Normalise
            total = sum(inf.weight for inf in influences)
            if total > 1e-9:
                for inf in influences: inf.weight /= total

            # Prune below threshold
            influences = [inf for inf in influences if inf.weight >= self.min_weight]
            influences.sort(key=lambda x: -x.weight)
            influences = influences[:self.MAX_INFLUENCES]

            # Re-normalise after pruning
            total = sum(inf.weight for inf in influences)
            if total > 1e-9:
                for inf in influences: inf.weight /= total
            else:
                influences = []  # force fallback below

            # Zero-weight guard: always assign at least one bone
            if not influences:
                # Closest bone in full list
                fallback_name = min(
                    bone_name_list,
                    key=lambda b: (
                        lambda p: (vx-p[0])**2 + (vy-p[1])**2 + (vz-p[2])**2
                    )(self._bone_world_pos.get(b, (vx, vy, vz)))
                )
                fallback_idx = bone_idx.get(fallback_name, bone_idx.get("torsocam", bone_idx.get("hip", 0)))
                influences = [BoneWeight(fallback_idx, 1.0)]

            node.skin_data.append(VertexSkinData(influences=influences))

    def rig_from_template(self, target_model: KotorModel,
                          template: 'RigTemplate',
                          scale_to_target: bool = True) -> KotorModel:
        """
        Apply a RigTemplate (extracted from another KotOR model) to target_model.

        The bone hierarchy is rebuilt, scaled to the target's bounding box, and
        skin weights are re-computed using the template's bone world positions.
        """
        target_model.compute_bounds()
        tb_min  = target_model.bb_min
        tb_max  = target_model.bb_max
        t_height = max(0.01, tb_max[2] - tb_min[2])
        t_center = ((tb_min[0]+tb_max[0])/2,
                    (tb_min[1]+tb_max[1])/2, tb_min[2])
        scale = (t_height / template.height) if scale_to_target else 1.0

        # Rebuild bone nodes from template
        bone_nodes: Dict[str, ModelNode] = {}
        for name, bi in template.bones.items():
            node = ModelNode(
                name     = bi.name,
                flags    = int(NodeFlags.HEADER),
                rotation = bi.rotation,
                position = (bi.position[0]*scale,
                            bi.position[1]*scale,
                            bi.position[2]*scale),
            )
            bone_nodes[name] = node

        # Wire parent/child
        root_bone = None
        for name, bi in template.bones.items():
            if bi.parent and bi.parent in bone_nodes:
                p = bone_nodes[bi.parent]
                bone_nodes[name].parent = p
                p.children.append(bone_nodes[name])
            elif bi.parent is None:
                root_bone = bone_nodes[name]

        if root_bone is None:
            root_bone = next(iter(bone_nodes.values()))

        # Offset root to target model center
        root_bone.position = (t_center[0], t_center[1], t_center[2])

        # Attach to model
        if target_model.root_node:
            existing = {c.name for c in target_model.root_node.children}
            if root_bone.name not in existing:
                root_bone.parent = target_model.root_node
                target_model.root_node.children.insert(0, root_bone)
        else:
            target_model.root_node = root_bone

        # Compute world positions of template bones (scaled)
        self._bone_world_pos.clear()
        self._compute_world_positions(bone_nodes)
        bone_name_list = list(bone_nodes.keys())
        self._bone_name_list = bone_name_list
        self._model_bb_min = tb_min
        self._model_bb_max = tb_max

        # Skin all mesh nodes
        for node in target_model.mesh_nodes():
            self._skin_node(node, bone_nodes, bone_name_list)

        log.info(f"Rigged '{target_model.name}' from template '{template.source_model}' "
                 f"({len(bone_nodes)} bones, scale={scale:.3f})")
        return target_model

    # ── Manual rig helpers ────────────────────────────────────────────────

    def assign_vertex_bone(self, node: ModelNode, vert_idx: int,
                           bone_name: str, weight: float = 1.0):
        """Manually assign a single vertex to a bone (interactive rigging)."""
        if vert_idx >= len(node.vertices): return
        while len(node.skin_data) <= vert_idx:
            node.skin_data.append(VertexSkinData())
        node.flags |= int(NodeFlags.SKIN)
        if bone_name not in node.bone_map:
            node.bone_map.append(bone_name)
        bone_idx = node.bone_map.index(bone_name)
        sd = node.skin_data[vert_idx]
        sd.influences = [inf for inf in sd.influences if inf.bone_index != bone_idx]
        sd.influences.append(BoneWeight(bone_idx, weight))
        sd.normalize()
        sd.influences.sort(key=lambda x: -x.weight)
        sd.influences = sd.influences[:self.MAX_INFLUENCES]
        sd.normalize()

    def clear_vertex_weights(self, node: ModelNode, vert_idx: int):
        """Clear all bone influences for a vertex."""
        if vert_idx < len(node.skin_data):
            node.skin_data[vert_idx] = VertexSkinData()

    def paint_weights_by_region(self, node: ModelNode,
                                 bone_name: str,
                                 center: Tuple[float,float,float],
                                 radius: float,
                                 weight: float = 1.0,
                                 blend: bool = True):
        """Paint weights onto all vertices within a sphere of given radius."""
        if not node.vertices: return
        node.flags |= int(NodeFlags.SKIN)
        if bone_name not in node.bone_map:
            node.bone_map.append(bone_name)
        while len(node.skin_data) < len(node.vertices):
            node.skin_data.append(VertexSkinData())
        cx, cy, cz = center
        r2 = radius * radius
        for vi, (vx, vy, vz) in enumerate(node.vertices):
            dx, dy, dz = vx-cx, vy-cy, vz-cz
            dist2 = dx*dx + dy*dy + dz*dz
            if dist2 > r2: continue
            t = 1.0 - math.sqrt(dist2) / max(radius, 1e-9)
            w = weight * (t * t)
            self.assign_vertex_bone(node, vi, bone_name, w)

    def retarget_bones(self, model: KotorModel,
                       bone_mapping: Dict[str, str]) -> KotorModel:
        """Rename bones in model to match KotOR naming. bone_mapping = {old: new}"""
        for node in model.all_nodes():
            if node.name in bone_mapping:
                old = node.name; node.name = bone_mapping[old]
                log.debug(f"Retargeted: {old!r} → {node.name!r}")
            if node.is_skin and node.bone_map:
                node.bone_map = [bone_mapping.get(b, b) for b in node.bone_map]
        return model

    def detect_skeleton_type(self, model: KotorModel) -> str:
        names = {n.name.lower() for n in model.all_nodes()}
        humanoid_hints = {'head','neck','chest','hip','lhand','rhand','lthigh','rthigh','lcalf','rcalf'}
        creature_hints = {'lleg1','rleg1','lleg2','rleg2'}
        if len(names & humanoid_hints) >= 3: return "humanoid"
        if len(names & creature_hints) >= 2: return "creature"
        if sum(1 for n in model.all_nodes() if n.is_dummy) < 2: return "prop"
        return "humanoid"

    def extract_rig_template(self, source_model: KotorModel) -> 'RigTemplate':
        """Extract a RigTemplate from a model (convenience wrapper for RigExtractor.extract)."""
        return RigExtractor().extract(source_model)

    def bind_pose_from_fbx_bones(self, model: KotorModel) -> Dict[str, str]:
        fbx_to_kotor: Dict[str, str] = {}
        fbx_bones = [n for n in model.all_nodes() if n.is_dummy]
        kotor_synonyms: Dict[str, List[str]] = {
            'hip':       ['hip','pelvis','hips','root','bip01','bip_pelvis','cog'],
            'stomach':   ['stomach','spine','spine1','abdomen','lowerspine'],
            'chest':     ['chest','spine2','upperchest','upperback'],
            'neck':      ['neck','neck1'],
            'head':      ['head','skull','cranium'],
            'lshoulder': ['lshoulder','leftshoulder','shoulder_l','l_shoulder','clavicle_l'],
            'rshoulder': ['rshoulder','rightshoulder','shoulder_r','r_shoulder','clavicle_r'],
            'lforearm':  ['lforearm','leftforearm','forearm_l','l_forearm','lowerarm_l'],
            'rforearm':  ['rforearm','rightforearm','forearm_r','r_forearm','lowerarm_r'],
            'lhand':     ['lhand','lefthand','hand_l','l_hand'],
            'rhand':     ['rhand','righthand','hand_r','r_hand'],
            'lthigh':    ['lthigh','leftthigh','thigh_l','l_thigh','upperleg_l'],
            'rthigh':    ['rthigh','rightthigh','thigh_r','r_thigh','upperleg_r'],
            'lcalf':     ['lcalf','leftcalf','calf_l','l_calf','lowerleg_l','shin_l'],
            'rcalf':     ['rcalf','rightcalf','calf_r','r_calf','lowerleg_r','shin_r'],
            'lankle':    ['lankle','leftankle','ankle_l','l_ankle','foot_l'],
            'rankle':    ['rankle','rightankle','ankle_r','r_ankle','foot_r'],
            'ltoebase':  ['ltoebase','lefttoe','toe_l','l_toe'],
            'rtoebase':  ['rtoebase','righttoe','toe_r','r_toe'],
        }
        strip_prefixes = ['mixamorig:','mixamorig_','bip01 ','bip01_','character1_']
        def _norm(s):
            s = s.lower()
            for p in strip_prefixes:
                if s.startswith(p): s = s[len(p):]
            return s.replace(' ','').replace('_','').replace('.','').replace('-','')
        for fbx_bone in fbx_bones:
            fn = _norm(fbx_bone.name)
            for kotor_name, synonyms in kotor_synonyms.items():
                for syn in synonyms:
                    syn_n = syn.replace('_','').replace('.','').replace(' ','')
                    if fn == syn_n or fn.endswith(syn_n) or syn_n.endswith(fn):
                        fbx_to_kotor[fbx_bone.name] = kotor_name
                        break
                if fbx_bone.name in fbx_to_kotor: break
        log.info(f"Auto bone mapping: {len(fbx_to_kotor)}/{len(fbx_bones)} bones matched")
        return fbx_to_kotor


# ── Pose Utilities ─────────────────────────────────────────────────────────

def normalize_skeleton_to_kotor(model: KotorModel) -> KotorModel:
    bones = {n.name: n for n in model.all_nodes() if n.is_dummy}
    root_dummies = [n for n in bones.values()
                    if n.parent is None or n.parent.name == model.name]
    for rd in root_dummies:
        if rd.name.lower() not in ('torsocam', model.name.lower()):
            rd.name = 'torsocam'; break
    return model


def get_bone_colour_map() -> Dict[str, Tuple[int,int,int]]:
    all_bones = [b[0] for b in HUMANOID_BONES + CREATURE_BONES]
    return {b: _bone_colour(b) for b in all_bones}
