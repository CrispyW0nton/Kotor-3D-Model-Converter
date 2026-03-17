"""
Auto-Rigger for KotOR Models
=============================
Provides automatic bone assignment based on KotOR's standard skeleton hierarchy.

KotOR Character Skeleton (from k_sup_males / k_sup_females supermodels):
  Root → Pelvis → Stomach → Chest → Neck → Head
                                          → LShoulder → LForearm → LHand → LFinger01/02
                                          → RShoulder → RForearm → RHand → RFinger01/02
                         → LThigh → LCalf → LAnkle → LToebase
                         → RThigh → RCalf → RAnkle → RToebase

The auto-rigger:
1. Detects mesh regions via vertex position heuristics (height + centroid)
2. Assigns skin weights using heat-map style distance weighting
3. Supports both humanoid (character) and creature skeletons
4. Can bind an existing bone hierarchy from an imported FBX to KotOR names
"""

import math, logging
from typing import List, Dict, Optional, Tuple
from ..core.model_data import KotorModel, ModelNode, NodeFlags, VertexSkinData, BoneWeight

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
#  Standard KotOR Humanoid Skeleton Template
# ──────────────────────────────────────────────────────────────────────

HUMANOID_BONES = [
    # (name, parent, local_pos_relative_to_model_height, region_hint)
    # pos is normalized (0=feet, 1=top_of_head)
    ("torsocam",  None,         (0.0,  0.0,  0.0 )),   # root (origin)
    ("hip",       "torsocam",   (0.0,  0.0,  0.52)),   # pelvis
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

# Creature/Droid skeleton (simplified)
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

# Common weapon/equipment attachment points
ATTACHMENT_NODES = [
    ("lhand_attach",  "lhand",  (0.0, 0.0, 0.0)),
    ("rhand_attach",  "rhand",  (0.0, 0.0, 0.0)),
    ("head_attach",   "head",   (0.0, 0.0, 0.0)),
    ("chest_attach",  "chest",  (0.0, 0.0, 0.0)),
    ("back_attach",   "chest",  (0.0,-0.15,0.0)),
]

# Region → bones mapping (for auto-weight assignment)
REGION_BONES = {
    "head":         ["head", "neck"],
    "neck":         ["neck", "head", "chest"],
    "chest":        ["chest", "stomach", "lshoulder", "rshoulder"],
    "stomach":      ["stomach", "chest", "hip"],
    "hip":          ["hip", "stomach", "lthigh", "rthigh"],
    "l_upper_arm":  ["lshoulder", "chest"],
    "l_lower_arm":  ["lforearm", "lshoulder", "lhand"],
    "l_hand":       ["lhand", "lforearm", "lfinger01", "lfinger02"],
    "r_upper_arm":  ["rshoulder", "chest"],
    "r_lower_arm":  ["rforearm", "rshoulder", "rhand"],
    "r_hand":       ["rhand", "rforearm", "rfinger01", "rfinger02"],
    "l_upper_leg":  ["lthigh", "hip"],
    "l_lower_leg":  ["lcalf", "lthigh", "lankle"],
    "l_foot":       ["lankle", "lcalf", "ltoebase"],
    "r_upper_leg":  ["rthigh", "hip"],
    "r_lower_leg":  ["rcalf", "rthigh", "rankle"],
    "r_foot":       ["rankle", "rcalf", "rtoebase"],
}


# ──────────────────────────────────────────────────────────────────────
#  Bone Node builder
# ──────────────────────────────────────────────────────────────────────

def build_skeleton(model_height: float = 1.8, template: str = "humanoid") -> Dict[str, ModelNode]:
    """
    Build KotOR-compatible bone dummy nodes for a given model height.
    Returns {bone_name: ModelNode}
    """
    tmpl = HUMANOID_BONES if template == "humanoid" else CREATURE_BONES
    nodes: Dict[str, ModelNode] = {}

    for bone_name, parent_name, norm_pos in tmpl:
        node = ModelNode(
            name  = bone_name,
            flags = int(NodeFlags.HEADER),   # dummy = bone
        )
        # Scale normalized pos to actual model dimensions
        # norm_pos: x=left/right (±), y=forward/back, z=height 0..1
        wx = norm_pos[0] * model_height
        wy = norm_pos[1] * model_height
        wz = norm_pos[2] * model_height
        node.position = (wx, wy, wz)

        if parent_name and parent_name in nodes:
            p = nodes[parent_name]
            node.parent = p
            p.children.append(node)
            # Convert to local space
            px, py, pz = p.position
            node.position = (wx-px, wy-py, wz-pz)

        nodes[bone_name] = node

    return nodes


# ──────────────────────────────────────────────────────────────────────
#  Auto-Rigger
# ──────────────────────────────────────────────────────────────────────

class AutoRigger:
    """
    Automatically rigs mesh nodes to a KotOR humanoid skeleton.
    Algorithm:
      1. Compute model bounding box & height
      2. Build normalized bone positions
      3. For each mesh vertex, find nearest bones by distance
      4. Compute heat-map weights (inverse square distance, normalized)
      5. Clamp to 4 influences (KotOR max)
    """

    MAX_INFLUENCES = 4

    def __init__(self):
        self.template:      str   = "humanoid"
        self.model_height:  float = 1.8
        self.heat_falloff:  float = 4.0   # higher = sharper bone influence boundary
        self.min_weight:    float = 0.01  # prune weights below this
        self._bone_world_pos: Dict[str, Tuple[float,float,float]] = {}

    def rig_model(self, model: KotorModel,
                  template: str = "humanoid",
                  existing_bones: Optional[Dict[str, ModelNode]] = None
                  ) -> KotorModel:
        """
        Add skeleton to model and compute skin weights for all mesh nodes.
        Returns the modified model.
        """
        self.template = template

        # Compute model bounding box
        model.compute_bounds()
        bmin = model.bb_min; bmax = model.bb_max
        self.model_height = max(0.1, bmax[2] - bmin[2])
        model_center = ((bmin[0]+bmax[0])/2,
                        (bmin[1]+bmax[1])/2,
                        bmin[2])

        # Build or reuse bone nodes
        if existing_bones:
            bones = existing_bones
        else:
            bones = build_skeleton(self.model_height, template)

        # Offset bone roots to model center
        root_bone = bones.get("torsocam") or bones.get(list(bones.keys())[0])
        if root_bone and root_bone.parent is None:
            cx, cy, cz = model_center
            rx, ry, rz = root_bone.position
            root_bone.position = (cx, cy, cz)

        # Compute world positions of all bones
        self._compute_world_positions(bones)

        # Attach skeleton to model root node
        if model.root_node:
            root_bone.parent = model.root_node
            model.root_node.children.insert(0, root_bone)
        else:
            model.root_node = root_bone

        # Assign skin weights to each mesh node
        bone_name_list = list(bones.keys())
        for node in model.mesh_nodes():
            self._skin_node(node, bones, bone_name_list)

        log.info(f"Auto-rigged '{model.name}' with {len(bones)} bones")
        return model

    def _compute_world_positions(self, bones: Dict[str, ModelNode]):
        """Compute and cache world positions of bones by walking hierarchy"""
        for name, bone in bones.items():
            pos = list(bone.position)
            parent = bone.parent
            while parent:
                pos[0] += parent.position[0]
                pos[1] += parent.position[1]
                pos[2] += parent.position[2]
                parent = parent.parent
            self._bone_world_pos[name] = tuple(pos)

    def _skin_node(self, node: ModelNode,
                   bones: Dict[str, ModelNode],
                   bone_name_list: List[str]):
        """Assign skin weights to a mesh node"""
        if not node.vertices: return

        # Change node to skin type
        node.flags |= int(NodeFlags.SKIN)
        node.bone_map  = bone_name_list[:]
        node.skin_data = []

        for vx, vy, vz in node.vertices:
            # Compute distance from this vertex to each bone
            dists: List[Tuple[float, str]] = []
            for bname, bpos in self._bone_world_pos.items():
                dx = vx - bpos[0]
                dy = vy - bpos[1]
                dz = vz - bpos[2]
                dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                dists.append((dist, bname))

            dists.sort(key=lambda x: x[0])

            # Take closest N bones and compute heat weights
            closest = dists[:self.MAX_INFLUENCES * 2]
            influences = []
            for dist, bname in closest[:self.MAX_INFLUENCES]:
                if dist < 0.0001: dist = 0.0001
                w = 1.0 / (dist ** self.heat_falloff)
                influences.append(BoneWeight(bone_name_list.index(bname), w))

            # Normalize
            total = sum(inf.weight for inf in influences)
            if total > 0:
                for inf in influences:
                    inf.weight /= total

            # Prune tiny weights and keep top-4
            influences = [inf for inf in influences if inf.weight >= self.min_weight]
            influences.sort(key=lambda x: -x.weight)
            influences = influences[:self.MAX_INFLUENCES]

            # Re-normalize after pruning
            total = sum(inf.weight for inf in influences)
            if total > 0:
                for inf in influences:
                    inf.weight /= total

            sd = VertexSkinData(influences=influences)
            node.skin_data.append(sd)

    def retarget_bones(self, model: KotorModel,
                       bone_mapping: Dict[str, str]) -> KotorModel:
        """
        Rename bones in model to match KotOR naming convention.
        bone_mapping = {fbx_bone_name: kotor_bone_name}
        """
        for node in model.all_nodes():
            if node.name in bone_mapping:
                old = node.name
                node.name = bone_mapping[old]
                log.debug(f"Retargeted bone: {old} → {node.name}")
            # Update skin_data bone_map references
            if node.is_skin and node.bone_map:
                node.bone_map = [bone_mapping.get(b, b) for b in node.bone_map]
        return model

    def detect_skeleton_type(self, model: KotorModel) -> str:
        """Heuristically detect if model is humanoid, creature, or prop"""
        all_nodes = model.all_nodes()
        names = {n.name.lower() for n in all_nodes}

        humanoid_hints = {'head','neck','chest','hip','lhand','rhand',
                          'lthigh','rthigh','lcalf','rcalf'}
        creature_hints = {'lleg1','rleg1','lleg2','rleg2'}

        if len(names & humanoid_hints) >= 3:
            return "humanoid"
        if len(names & creature_hints) >= 2:
            return "creature"

        # Count dummy nodes vs mesh nodes
        dummy_count = sum(1 for n in all_nodes if n.is_dummy)
        if dummy_count < 2:
            return "prop"   # probably a weapon/item

        return "humanoid"   # default

    def bind_pose_from_fbx_bones(self, model: KotorModel) -> Dict[str, str]:
        """
        Attempt automatic mapping of FBX bone names to KotOR bone names.
        Returns the mapping dict.
        """
        fbx_to_kotor = {}
        fbx_bones = [n for n in model.all_nodes() if n.is_dummy]

        kotor_synonyms = {
            # KotOR name → possible FBX names (lower)
            'hip':       ['hip','pelvis','hips','root','bip01','bip_pelvis'],
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
        }

        for fbx_bone in fbx_bones:
            fn = fbx_bone.name.lower().replace(' ','').replace('_','').replace('.','')
            for kotor_name, synonyms in kotor_synonyms.items():
                for syn in synonyms:
                    if fn == syn.replace('_','').replace('.','') or fn in syn:
                        fbx_to_kotor[fbx_bone.name] = kotor_name
                        break
                if fbx_bone.name in fbx_to_kotor:
                    break

        log.info(f"Auto bone mapping: {len(fbx_to_kotor)} bones matched")
        return fbx_to_kotor


# ──────────────────────────────────────────────────────────────────────
#  Pose Utilities
# ──────────────────────────────────────────────────────────────────────

def normalize_skeleton_to_kotor(model: KotorModel) -> KotorModel:
    """
    Ensure the root bone is named 'torsocam' and the hierarchy
    matches KotOR conventions (required for supermodel inheritance).
    """
    bones = {n.name: n for n in model.all_nodes() if n.is_dummy}
    # If there's a single root dummy without a parent, rename it
    root_dummies = [n for n in bones.values() if n.parent is None or n.parent.name == model.name]
    for rd in root_dummies:
        if rd.name.lower() not in ('torsocam', model.name.lower()):
            rd.name = 'torsocam'
            break
    return model
