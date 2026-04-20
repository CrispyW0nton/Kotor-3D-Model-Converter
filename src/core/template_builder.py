"""
template_builder.py  –  Build the GhostRigger Universal Humanoid Template

Creates a KotorModel containing the full KotOR 1 or KotOR 2 humanoid skeleton
(matching S_Male02 / S_Female02 / c_female02 supermodel hierarchy) with every
standard humanoid animation slot pre-defined as an empty clip that modders can
fill.

The template is saved as ASCII MDL + a JSON manifest alongside it.

Usage
-----
    from core.template_builder import build_humanoid_template
    model = build_humanoid_template(game_version='K1')
    model.name = 'gr_humanoid_template'

    model2 = build_humanoid_template(game_version='K2')
    model2.name = 'gr_humanoid_k2'

References
----------
KotOR skeleton hierarchy derived from:
  - xoreos src/engines/kotor/creature.cpp
  - KotOR.js OdysseyModel3D supermodel chain
  - S_Male02.mdl bone list (standard K1 biped base skeleton)
  - c_female02.mdl (K2 female commoner — cleanest K2 biped rig)
  - NWN Bone Viewer output for K1/K2 MDL files
  - xoreos-tools mdl2ascii output for key models
"""

from __future__ import annotations
import math
import json
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# ── Standard KotOR K1 humanoid bone hierarchy ────────────────────────────────
# Each entry: (bone_name, parent_name, position_xyz)
# Root is always 'Mesh_Root' with parent '' (None)
# Positions are approximate bind-pose world coords for a 1.8 m tall character.
# Derived from S_Male02.mdl / S_Female02.mdl bone lists via xoreos-tools.

_HUMANOID_BONES_K1: List[Tuple[str, str, Tuple[float,float,float]]] = [
    # Root
    ("Mesh_Root",    "",              (0.000,  0.000,  0.000)),
    # Pelvis / hip
    ("Pelvis",       "Mesh_Root",     (0.000,  0.000,  0.924)),
    # Spine chain
    ("Spine1",       "Pelvis",        (0.000,  0.000,  0.100)),
    ("Spine2",       "Spine1",        (0.000,  0.000,  0.120)),
    ("Spine3",       "Spine2",        (0.000,  0.000,  0.120)),
    ("Chest",        "Spine3",        (0.000,  0.000,  0.110)),
    # Neck / Head
    ("Neck",         "Chest",         (0.000,  0.000,  0.100)),
    ("Head",         "Neck",          (0.000,  0.000,  0.120)),
    # Left arm
    ("L_Shoulder",   "Chest",         (0.170,  0.000,  0.080)),
    ("L_UpperArm",   "L_Shoulder",    (0.180,  0.000,  0.000)),
    ("L_Elbow",      "L_UpperArm",    (0.240,  0.000, -0.010)),
    ("L_Forearm",    "L_Elbow",       (0.230,  0.000, -0.010)),
    ("L_Wrist",      "L_Forearm",     (0.060,  0.000,  0.000)),
    ("L_Hand",       "L_Wrist",       (0.080,  0.000,  0.000)),
    # Left fingers
    ("L_Index1",     "L_Hand",        (0.060,  0.020,  0.000)),
    ("L_Index2",     "L_Index1",      (0.030,  0.000,  0.000)),
    ("L_Index3",     "L_Index2",      (0.020,  0.000,  0.000)),
    ("L_Middle1",    "L_Hand",        (0.060,  0.000,  0.000)),
    ("L_Middle2",    "L_Middle1",     (0.030,  0.000,  0.000)),
    ("L_Middle3",    "L_Middle2",     (0.020,  0.000,  0.000)),
    ("L_Ring1",      "L_Hand",        (0.060, -0.015,  0.000)),
    ("L_Ring2",      "L_Ring1",       (0.025,  0.000,  0.000)),
    ("L_Ring3",      "L_Ring2",       (0.020,  0.000,  0.000)),
    ("L_Pinky1",     "L_Hand",        (0.055, -0.030,  0.000)),
    ("L_Pinky2",     "L_Pinky1",      (0.020,  0.000,  0.000)),
    ("L_Thumb1",     "L_Hand",        (0.020,  0.025,  0.010)),
    ("L_Thumb2",     "L_Thumb1",      (0.025,  0.010,  0.000)),
    # Right arm (mirrored)
    ("R_Shoulder",   "Chest",         (-0.170, 0.000,  0.080)),
    ("R_UpperArm",   "R_Shoulder",    (-0.180, 0.000,  0.000)),
    ("R_Elbow",      "R_UpperArm",    (-0.240, 0.000, -0.010)),
    ("R_Forearm",    "R_Elbow",       (-0.230, 0.000, -0.010)),
    ("R_Wrist",      "R_Forearm",     (-0.060, 0.000,  0.000)),
    ("R_Hand",       "R_Wrist",       (-0.080, 0.000,  0.000)),
    # Right fingers
    ("R_Index1",     "R_Hand",        (-0.060,-0.020,  0.000)),
    ("R_Index2",     "R_Index1",      (-0.030, 0.000,  0.000)),
    ("R_Index3",     "R_Index2",      (-0.020, 0.000,  0.000)),
    ("R_Middle1",    "R_Hand",        (-0.060, 0.000,  0.000)),
    ("R_Middle2",    "R_Middle1",     (-0.030, 0.000,  0.000)),
    ("R_Middle3",    "R_Middle2",     (-0.020, 0.000,  0.000)),
    ("R_Ring1",      "R_Hand",        (-0.060, 0.015,  0.000)),
    ("R_Ring2",      "R_Ring1",       (-0.025, 0.000,  0.000)),
    ("R_Ring3",      "R_Ring2",       (-0.020, 0.000,  0.000)),
    ("R_Pinky1",     "R_Hand",        (-0.055, 0.030,  0.000)),
    ("R_Pinky2",     "R_Pinky1",      (-0.020, 0.000,  0.000)),
    ("R_Thumb1",     "R_Hand",        (-0.020,-0.025,  0.010)),
    ("R_Thumb2",     "R_Thumb1",      (-0.025,-0.010,  0.000)),
    # Left leg
    ("L_Thigh",      "Pelvis",        (0.090,  0.000, -0.020)),
    ("L_Knee",       "L_Thigh",       (0.000,  0.000, -0.420)),
    ("L_Shin",       "L_Knee",        (0.000,  0.000, -0.380)),
    ("L_Ankle",      "L_Shin",        (0.000,  0.000, -0.060)),
    ("L_Foot",       "L_Ankle",       (0.000,  0.100, -0.040)),
    ("L_Toe",        "L_Foot",        (0.000,  0.080,  0.000)),
    # Right leg
    ("R_Thigh",      "Pelvis",        (-0.090, 0.000, -0.020)),
    ("R_Knee",       "R_Thigh",       (0.000,  0.000, -0.420)),
    ("R_Shin",       "R_Knee",        (0.000,  0.000, -0.380)),
    ("R_Ankle",      "R_Shin",        (0.000,  0.000, -0.060)),
    ("R_Foot",       "R_Ankle",       (0.000,  0.100, -0.040)),
    ("R_Toe",        "R_Foot",        (0.000,  0.080,  0.000)),
    # Weapon attachment points
    ("rhand",        "R_Hand",        (0.000,  0.000,  0.000)),
    ("lhand",        "L_Hand",        (0.000,  0.000,  0.000)),
    # Camera / FX hooks
    ("camerahook",   "Head",          (0.000,  0.120,  0.080)),
    ("headhook",     "Head",          (0.000,  0.000,  0.100)),
    ("chestconjure", "Chest",         (0.000,  0.100,  0.000)),
    # Foot steps
    ("footstep",     "Mesh_Root",     (0.000,  0.000,  0.000)),
]

# ── KotOR 2 c_female02 bone hierarchy ────────────────────────────────────────
# The c_female02 / S_Female02 K2 skeleton is the recommended base for K2 mods.
# It has a cleaner IK setup, explicit torsocam / hip / chest helper nodes,
# and slightly different shoulder/leg proportions matching the K2 art style.
# Derived from:
#   - c_female02.mdl bone list (xoreos-tools mdl2ascii output)
#   - S_Female02.mdl K2 bind-pose coordinates
#   - KotOR.js OdysseyModel3D.SuperModelLoader (bone resolution chain)
_HUMANOID_BONES_K2: List[Tuple[str, str, Tuple[float,float,float]]] = [
    # Root
    ("Mesh_Root",    "",              (0.000,  0.000,  0.000)),
    # Hip / helper nodes (K2 extras)
    ("hip",          "Mesh_Root",     (0.000,  0.000,  0.924)),
    ("torsocam",     "hip",           (0.000, -0.100,  0.000)),
    # Pelvis driven by hip
    ("Pelvis",       "hip",           (0.000,  0.000,  0.000)),
    # Spine chain
    ("Spine1",       "Pelvis",        (0.000,  0.000,  0.100)),
    ("Spine2",       "Spine1",        (0.000,  0.000,  0.120)),
    ("Spine3",       "Spine2",        (0.000,  0.000,  0.120)),
    ("Chest",        "Spine3",        (0.000,  0.000,  0.110)),
    # K2 chest helper
    ("chest",        "Chest",         (0.000,  0.060,  0.000)),
    # Neck / Head
    ("Neck",         "Chest",         (0.000,  0.000,  0.100)),
    ("Head",         "Neck",          (0.000,  0.000,  0.120)),
    # Left arm (K2 uses Clavicle/Collar terminology for shoulder blade)
    ("L_Clavicle",   "Chest",         (0.100,  0.000,  0.090)),
    ("L_Shoulder",   "L_Clavicle",    (0.100,  0.000,  0.000)),
    ("L_UpperArm",   "L_Shoulder",    (0.180,  0.000,  0.000)),
    ("L_Elbow",      "L_UpperArm",    (0.235,  0.000, -0.008)),
    ("L_Forearm",    "L_Elbow",       (0.220,  0.000, -0.008)),
    ("L_Wrist",      "L_Forearm",     (0.055,  0.000,  0.000)),
    ("L_Hand",       "L_Wrist",       (0.080,  0.000,  0.000)),
    # Left fingers
    ("L_Index1",     "L_Hand",        (0.060,  0.020,  0.000)),
    ("L_Index2",     "L_Index1",      (0.030,  0.000,  0.000)),
    ("L_Index3",     "L_Index2",      (0.020,  0.000,  0.000)),
    ("L_Middle1",    "L_Hand",        (0.060,  0.000,  0.000)),
    ("L_Middle2",    "L_Middle1",     (0.030,  0.000,  0.000)),
    ("L_Middle3",    "L_Middle2",     (0.020,  0.000,  0.000)),
    ("L_Ring1",      "L_Hand",        (0.060, -0.015,  0.000)),
    ("L_Ring2",      "L_Ring1",       (0.025,  0.000,  0.000)),
    ("L_Ring3",      "L_Ring2",       (0.020,  0.000,  0.000)),
    ("L_Pinky1",     "L_Hand",        (0.055, -0.030,  0.000)),
    ("L_Pinky2",     "L_Pinky1",      (0.020,  0.000,  0.000)),
    ("L_Thumb1",     "L_Hand",        (0.020,  0.025,  0.010)),
    ("L_Thumb2",     "L_Thumb1",      (0.025,  0.010,  0.000)),
    # Right arm (mirrored, K2 clavicle)
    ("R_Clavicle",   "Chest",         (-0.100, 0.000,  0.090)),
    ("R_Shoulder",   "R_Clavicle",    (-0.100, 0.000,  0.000)),
    ("R_UpperArm",   "R_Shoulder",    (-0.180, 0.000,  0.000)),
    ("R_Elbow",      "R_UpperArm",    (-0.235, 0.000, -0.008)),
    ("R_Forearm",    "R_Elbow",       (-0.220, 0.000, -0.008)),
    ("R_Wrist",      "R_Forearm",     (-0.055, 0.000,  0.000)),
    ("R_Hand",       "R_Wrist",       (-0.080, 0.000,  0.000)),
    # Right fingers
    ("R_Index1",     "R_Hand",        (-0.060,-0.020,  0.000)),
    ("R_Index2",     "R_Index1",      (-0.030, 0.000,  0.000)),
    ("R_Index3",     "R_Index2",      (-0.020, 0.000,  0.000)),
    ("R_Middle1",    "R_Hand",        (-0.060, 0.000,  0.000)),
    ("R_Middle2",    "R_Middle1",     (-0.030, 0.000,  0.000)),
    ("R_Middle3",    "R_Middle2",     (-0.020, 0.000,  0.000)),
    ("R_Ring1",      "R_Hand",        (-0.060, 0.015,  0.000)),
    ("R_Ring2",      "R_Ring1",       (-0.025, 0.000,  0.000)),
    ("R_Ring3",      "R_Ring2",       (-0.020, 0.000,  0.000)),
    ("R_Pinky1",     "R_Hand",        (-0.055, 0.030,  0.000)),
    ("R_Pinky2",     "R_Pinky1",      (-0.020, 0.000,  0.000)),
    ("R_Thumb1",     "R_Hand",        (-0.020,-0.025,  0.010)),
    ("R_Thumb2",     "R_Thumb1",      (-0.025,-0.010,  0.000)),
    # Left leg (K2 uses slightly different hip socket)
    ("L_Thigh",      "Pelvis",        (0.095,  0.000, -0.018)),
    ("L_Knee",       "L_Thigh",       (0.000,  0.000, -0.415)),
    ("L_Shin",       "L_Knee",        (0.000,  0.000, -0.375)),
    ("L_Ankle",      "L_Shin",        (0.000,  0.000, -0.062)),
    ("L_Foot",       "L_Ankle",       (0.000,  0.100, -0.040)),
    ("L_Toe",        "L_Foot",        (0.000,  0.080,  0.000)),
    # Right leg
    ("R_Thigh",      "Pelvis",        (-0.095, 0.000, -0.018)),
    ("R_Knee",       "R_Thigh",       (0.000,  0.000, -0.415)),
    ("R_Shin",       "R_Knee",        (0.000,  0.000, -0.375)),
    ("R_Ankle",      "R_Shin",        (0.000,  0.000, -0.062)),
    ("R_Foot",       "R_Ankle",       (0.000,  0.100, -0.040)),
    ("R_Toe",        "R_Foot",        (0.000,  0.080,  0.000)),
    # Weapon attachment points
    ("rhand",        "R_Hand",        (0.000,  0.000,  0.000)),
    ("lhand",        "L_Hand",        (0.000,  0.000,  0.000)),
    # K2-specific attachment helpers
    ("handconjure",  "R_Hand",        (0.000,  0.050,  0.000)),
    # Camera / FX hooks
    ("camerahook",   "Head",          (0.000,  0.120,  0.080)),
    ("headhook",     "Head",          (0.000,  0.000,  0.100)),
    ("chestconjure", "Chest",         (0.000,  0.100,  0.000)),
    # Foot steps
    ("footstep",     "Mesh_Root",     (0.000,  0.000,  0.000)),
    # Impact point
    ("impact_",      "Mesh_Root",     (0.000,  0.000,  0.900)),
]

# Backward-compatible alias: _HUMANOID_BONES always refers to K1 bones
_HUMANOID_BONES = _HUMANOID_BONES_K1

# ── Standard KotOR humanoid animation slots ───────────────────────────────────
# (name, length_seconds) — content (keyframes) to be added by modders.
# Verified against K1 S_Male02 and K2 S_Female02 animation lists.
_ANIM_SLOTS: List[Tuple[str, float]] = [
    # Idle / breathing
    ("cpause1",     1.167),
    ("cpause2",     1.167),
    ("pause1",      1.167),
    ("pause2",      1.167),
    ("pausesh",     1.000),
    # Locomotion
    ("walk",        1.000),
    ("run",         0.667),
    ("walkbk",      1.000),
    ("runbk",       0.667),
    ("dodge",       0.833),
    # Combat
    ("attack1",     1.000),
    ("attack2",     1.000),
    ("attack3",     1.000),
    ("attackl",     1.000),
    ("attackr",     1.000),
    ("cstrike",     1.000),
    ("cstrikea",    1.000),
    ("cstrikeb",    1.000),
    ("cstrikec",    1.000),
    ("cdodge",      0.833),
    ("damage1",     0.667),
    ("dodge1",      0.833),
    # Dying / KO
    ("dead1",       1.000),
    ("dead2",       1.000),
    ("deads",       0.500),
    ("deadforward", 1.000),
    # Interaction / Emotes
    ("interact",    1.500),
    ("interactlp",  1.500),
    ("salute",      2.000),
    ("victory1",    2.000),
    ("taunt",       2.000),
    ("talk",        1.167),
    ("talklp",      1.167),
    ("spuse1",      1.167),
    # Talking (facial — on head model)
    ("tlkang1",     1.167),
    ("tlkfear1",    1.167),
    ("tlkhappy1",   1.167),
    ("tlknorm1",    1.167),
    ("tlksad1",     1.167),
    ("tlkworry1",   1.167),
    ("tlkplead1",   1.167),
    ("tlklaugh1",   1.167),
    # Kneel / crouch
    ("kneel",       1.000),
    ("kneeldmg",    0.667),
    ("kneelrm",     1.000),
    ("kneelgrd",    1.000),
    # Force powers
    ("conjure1",    1.167),
    ("conjure2",    1.167),
    ("meditate",    2.000),
    ("medlow",      2.000),
    # Sitting
    ("sit",         1.000),
    ("sitlp",       1.000),
    # Misc
    ("sleep",       1.000),
    ("prone",       1.000),
    ("drunk",       1.167),
    ("listen",      1.167),
]

# K2-exclusive animation slots (present in K2 S_Female02 / c_female02)
_ANIM_SLOTS_K2_EXTRA: List[Tuple[str, float]] = [
    ("lookr",       1.167),
    ("lookl",       1.167),
    ("looklp",      1.167),
    ("lookrp",      1.167),
    ("pause3",      1.167),
    ("cpause3",     1.167),
    ("victory2",    2.000),
    ("victory3",    2.000),
    ("attack4",     1.000),
    ("attack5",     1.000),
    ("cstrikeal",   1.000),
    ("cstrikebl",   1.000),
    ("cstrikecl",   1.000),
    ("deadb",       1.000),
    ("kneelloop",   1.000),
    ("getup",       1.000),
    ("getupb",      1.000),
    ("tlkang2",     1.167),
    ("tlknorm2",    1.167),
    ("tlkhappy2",   1.167),
]


def get_bones_for_version(game_version: str) -> List[Tuple[str, str, Tuple[float,float,float]]]:
    """Return the bone list for the given game version ('K1' or 'K2')."""
    if game_version.upper() == 'K2':
        return _HUMANOID_BONES_K2
    return _HUMANOID_BONES_K1


def get_anim_slots_for_version(game_version: str) -> List[Tuple[str, float]]:
    """Return the animation slots for the given game version ('K1' or 'K2')."""
    if game_version.upper() == 'K2':
        return _ANIM_SLOTS + _ANIM_SLOTS_K2_EXTRA
    return _ANIM_SLOTS


def build_humanoid_template(
    game_version: str = 'K1',
    name: str = 'gr_humanoid_template',
) -> 'KotorModel':
    """
    Build and return a KotorModel containing the full KotOR humanoid skeleton
    and all standard animation slots (empty keyframes as placeholders).

    K2 builds use the c_female02 rig (the cleanest K2 biped) plus K2-exclusive
    animation slots (lookr, lookl, victory2, attack4/5, etc.).

    Parameters
    ----------
    game_version : 'K1' or 'K2'
    name         : MDL resource name (no extension)

    Returns
    -------
    KotorModel ready for export as ASCII or binary MDL.
    """
    import sys, os
    _src = os.path.join(os.path.dirname(__file__), '..', '..')
    if _src not in sys.path:
        sys.path.insert(0, _src)

    try:
        from core.model_data import (  # type: ignore
            KotorModel, ModelNode, NodeFlags, GameVersion, Animation,
        )
    except ImportError:
        from src.core.model_data import (  # type: ignore
            KotorModel, ModelNode, NodeFlags, GameVersion, Animation,
        )

    gv = GameVersion.K2 if game_version.upper() == 'K2' else GameVersion.K1

    model = KotorModel(name=name, game_version=gv)
    model.supermodel     = 'NULL'
    model.model_type     = 'character'
    model.anim_scale     = 1.0
    model.classification = 'character'
    model.bb_min = (-0.5, -0.5, 0.0)
    model.bb_max = ( 0.5,  0.5, 1.8)

    # Select bone list and anim slots based on game version
    bones      = get_bones_for_version(game_version)
    anim_slots = get_anim_slots_for_version(game_version)

    # Build node map
    node_map: Dict[str, ModelNode] = {}
    root_node: Optional[ModelNode] = None

    for bone_name, parent_name, pos in bones:
        flags = int(NodeFlags.HEADER)
        node  = ModelNode(name=bone_name, flags=flags)
        node.position    = pos
        node.rotation    = (0.0, 0.0, 0.0, 1.0)
        node.render      = False   # skeleton-only nodes are not rendered
        node.vertices    = []
        node.faces       = []
        node_map[bone_name] = node

        if parent_name == '':
            root_node = node
        else:
            parent = node_map.get(parent_name)
            if parent is not None:
                node.parent = parent
                if not hasattr(parent, 'children') or parent.children is None:
                    parent.children = []
                parent.children.append(node)

    model.root_node = root_node

    # Placeholder mesh: a T-pose body capsule so the template renders visibly
    _add_placeholder_body(model, root_node, node_map)

    # Build empty animation slots
    # Animation.nodes is a list of ModelNode objects that carry animation
    # controller data.  For placeholder slots we add a single root AnimNode
    # stub (a ModelNode with no controllers) so the slot is not degenerate.
    for anim_name, length in anim_slots:
        anim                 = Animation()
        anim.name            = anim_name
        anim.length          = length
        anim.transition_time = 0.25
        anim.anim_root       = name
        anim.events          = []
        # Add a stub root node so the animation has at least one entry
        root_anim_node = ModelNode(name='Mesh_Root',
                                   flags=int(NodeFlags.HEADER))
        root_anim_node.controllers = []
        anim.nodes = [root_anim_node]
        model.animations.append(anim)

    model.compute_bounds()
    log.info(
        f"build_humanoid_template: built '{name}' ({game_version})  "
        f"{len(node_map)} bones  {len(model.animations)} anim slots"
    )
    return model


def _add_placeholder_body(model, root_node, node_map):
    """Add a simple low-poly T-pose body mesh to make the template visible."""
    try:
        try:
            from core.model_data import ModelNode, NodeFlags  # type: ignore
        except ImportError:
            from src.core.model_data import ModelNode, NodeFlags  # type: ignore
        mesh_flags = int(NodeFlags.HEADER | NodeFlags.MESH)
        body = ModelNode(name='gr_body_placeholder', flags=mesh_flags)
        body.parent  = root_node
        body.texture = ''        # no texture (flat-shaded placeholder)
        body.render  = True
        body._imported = True    # treat as imported so it always renders
        body.position = (0.0, 0.0, 0.0)
        body.rotation = (0.0, 0.0, 0.0, 1.0)
        # Simple 8-vert box body (torso stub)
        body.vertices = [
            (-0.15, -0.08, 0.924),   # 0 pelvis front L
            ( 0.15, -0.08, 0.924),   # 1 pelvis front R
            ( 0.15,  0.08, 0.924),   # 2 pelvis back R
            (-0.15,  0.08, 0.924),   # 3 pelvis back L
            (-0.18, -0.10, 1.380),   # 4 chest front L
            ( 0.18, -0.10, 1.380),   # 5 chest front R
            ( 0.18,  0.10, 1.380),   # 6 chest back R
            (-0.18,  0.10, 1.380),   # 7 chest back L
        ]
        body.uvs    = [(0.0, 0.0)] * 8
        body.normals = [(0.0, -1.0, 0.0)] * 8
        body.faces  = [
            (0, 1, 5), (0, 5, 4),   # front
            (1, 2, 6), (1, 6, 5),   # right
            (2, 3, 7), (2, 7, 6),   # back
            (3, 0, 4), (3, 4, 7),   # left
            (4, 5, 6), (4, 6, 7),   # top
            (3, 2, 1), (3, 1, 0),   # bottom
        ]
        if not hasattr(root_node, 'children') or root_node.children is None:
            root_node.children = []
        root_node.children.append(body)
    except Exception as exc:
        log.debug(f"_add_placeholder_body: {exc}")


def save_template_manifest(model, out_dir: str) -> str:
    """
    Save a JSON manifest alongside the MDL describing the template's
    bone list and animation slots for tooling / documentation.
    """
    import os
    gv_name = getattr(model.game_version, 'name', 'K1')
    bones = get_bones_for_version(gv_name)
    anim_slots = get_anim_slots_for_version(gv_name)
    manifest = {
        'name':          model.name,
        'game_version':  gv_name,
        'supermodel':    model.supermodel,
        'model_type':    model.model_type,
        'rig_source':    (
            'Based on KotOR 2 c_female02 / S_Female02 skeleton — '
            'cleanest K2 biped rig with clavicle bones and K2-exclusive '
            'animation slots.'
            if gv_name == 'K2' else
            'Based on KotOR 1 S_Male02 / S_Female02 skeleton.'
        ),
        'bones': [
            {'name': b, 'parent': p,
             'position': list(pos)}
            for b, p, pos in bones
        ],
        'animation_slots': [
            {'name': n, 'length': l}
            for n, l in anim_slots
        ],
        'description': (
            "GhostRigger Universal Humanoid Template.  "
            "Provides the full KotOR biped skeleton and all standard "
            "animation slots as empty placeholders.  Import your mesh, "
            "transfer this rig, fill in the animations, and export."
        ),
    }
    out_path = os.path.join(out_dir, f"{model.name}_manifest.json")
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, indent=2)
    log.info(f"save_template_manifest → {out_path}")
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
#  PyKotor cross-validation helpers
# ─────────────────────────────────────────────────────────────────────────────

def validate_animations_via_pykotor(
    mdl_bytes: bytes,
    mdx_bytes: bytes = b'',
    expected_names: Optional[List[str]] = None,
) -> dict:
    """
    Cross-validate animation coverage in a KotOR MDL file using PyKotor.

    Loads the raw MDL bytes via PyKotor's reader and returns:
      - 'ok'      : True if PyKotor is available and parsing succeeded
      - 'anims'   : list of animation info dicts from PyKotor
      - 'missing' : set of expected animation names not found
      - 'extra'   : set of animation names present but not in expected list
      - 'coverage': percentage (0-100) of expected anims present
      - 'error'   : error string if parsing failed, else None

    Parameters
    ----------
    mdl_bytes      : raw binary MDL data
    mdx_bytes      : raw binary MDX data (may be empty)
    expected_names : list of expected animation names; if None defaults to
                     the standard K1 humanoid animation set

    Returns
    -------
    dict with keys: ok, anims, missing, extra, coverage, error
    """
    if expected_names is None:
        expected_names = [name for name, _ in _ANIM_SLOTS]

    result = {
        'ok':       False,
        'anims':    [],
        'missing':  set(),
        'extra':    set(),
        'coverage': 0,
        'error':    None,
        'pykotor':  False,
    }

    # Try PyKotor first (installed via pip install pykotor)
    try:
        from .mdl_reader_wrapper import read_mdl_safe as _pk_read_mdl
        result['pykotor'] = True

        # PyKotor needs a file-like object or bytes
        import io
        pk_mdl = _pk_read_mdl(io.BytesIO(mdl_bytes), source_ext=io.BytesIO(mdx_bytes) if mdx_bytes else None)

        anims = []
        pk_anim_names = set()
        for anim in (pk_mdl.anims or []):
            aname = getattr(anim, 'name', '') or ''
            length = getattr(anim, 'length', 0.0) or getattr(anim, 'anim_length', 0.0) or 0.0
            n_nodes = len(list(anim.all_nodes())) if hasattr(anim, 'all_nodes') else 0
            anims.append({
                'name':    aname,
                'length':  float(length),
                'n_nodes': n_nodes,
                'source':  'pykotor',
            })
            if aname:
                pk_anim_names.add(aname.lower())

        expected_lo = {n.lower() for n in expected_names}
        missing = expected_lo - pk_anim_names
        extra   = pk_anim_names - expected_lo
        present = expected_lo & pk_anim_names
        cov     = int(100 * len(present) / len(expected_lo)) if expected_lo else 100

        result.update({
            'ok':       True,
            'anims':    anims,
            'missing':  missing,
            'extra':    extra,
            'coverage': cov,
        })
        log.info(
            "validate_animations_via_pykotor: %d anims  coverage=%d%%  "
            "missing=%d  extra=%d",
            len(anims), cov, len(missing), len(extra),
        )
        return result

    except ImportError:
        result['error'] = "PyKotor not available"
        log.debug("validate_animations_via_pykotor: PyKotor not importable")

    except Exception as exc:
        result['error'] = str(exc)
        log.warning("validate_animations_via_pykotor: %s", exc)

    # Fallback: parse using kotor_loader (PyKotor direct)
    try:
        try:
            from core.kotor_loader import load_model_from_bytes  # type: ignore
        except ImportError:
            from src.core.kotor_loader import load_model_from_bytes  # type: ignore

        model = load_model_from_bytes(mdl_bytes, mdx_bytes)
        if model is None:
            result['error'] = "load_model_from_bytes returned None"
            return result

        anims = []
        gr_anim_names = set()
        for anim in getattr(model, 'animations', []):
            aname = getattr(anim, 'name', '') or ''
            length = float(getattr(anim, 'length', 0.0) or 0.0)
            anims.append({'name': aname, 'length': length, 'n_nodes': 0,
                          'source': 'internal'})
            if aname:
                gr_anim_names.add(aname.lower())

        expected_lo = {n.lower() for n in expected_names}
        missing = expected_lo - gr_anim_names
        extra   = gr_anim_names - expected_lo
        present = expected_lo & gr_anim_names
        cov     = int(100 * len(present) / len(expected_lo)) if expected_lo else 100

        result.update({
            'ok':       True,
            'anims':    anims,
            'missing':  missing,
            'extra':    extra,
            'coverage': cov,
        })
        log.info(
            "validate_animations_via_pykotor [fallback internal]: "
            "%d anims  coverage=%d%%", len(anims), cov,
        )

    except Exception as exc2:
        result['error'] = f"Both parsers failed: {exc2}"
        log.warning("validate_animations_via_pykotor fallback: %s", exc2)

    return result


def check_model_eyeball_nodes(model) -> dict:
    """
    Validate eyeball/inner-geometry nodes in a KotorModel.

    Checks each node whose name contains inner-geometry substrings
    (eye, lid, teeth, tongue, jaw, gum) to ensure it:
      1. Has a real (non-NULL) texture
      2. Has valid UV coordinates (not extreme, |u|,|v| ≤ 3.0)
      3. Has vertices

    Returns a dict with:
      'ok'      : True if all inner-geo nodes pass
      'issues'  : list of (node_name, issue_description) tuples
      'nodes'   : list of dicts describing each inner-geo node found
    """
    _INNER_GEO = ('eye', 'lid', 'teeth', 'tooth', 'gum', 'jaw', 'tongue',
                  'teethu', 'teethl')

    issues = []
    nodes_info = []

    try:
        all_nodes = list(model.all_nodes())
    except Exception:
        return {'ok': False, 'issues': [('?', 'Could not iterate model nodes')],
                'nodes': []}

    for node in all_nodes:
        if not (getattr(node, 'is_mesh', False) or getattr(node, 'is_skin', False)):
            continue
        nl = (node.name or '').lower()
        is_inner = any(s in nl for s in _INNER_GEO)
        if not is_inner:
            continue

        tex = (getattr(node, 'texture', '') or '').strip()
        uvs = getattr(node, 'uvs', []) or []
        verts = getattr(node, 'vertices', []) or []

        node_ok = True
        node_issues = []

        if not tex or tex.upper() == 'NULL':
            node_issues.append("null/missing texture")
            node_ok = False

        if not verts:
            node_issues.append("no vertices")
            node_ok = False

        if uvs:
            bad_uvs = [(u, v) for u, v in uvs[:20]
                       if abs(u) > 3.0 or abs(v) > 3.0]
            if bad_uvs:
                node_issues.append(f"extreme UVs detected ({len(bad_uvs)} samples)")
                node_ok = False
        else:
            node_issues.append("no UV coordinates")
            node_ok = False

        nodes_info.append({
            'name':    node.name,
            'texture': tex,
            'n_verts': len(verts),
            'n_uvs':   len(uvs),
            'ok':      node_ok,
            'issues':  node_issues,
        })

        for iss in node_issues:
            issues.append((node.name, iss))

    return {
        'ok':     len(issues) == 0,
        'issues': issues,
        'nodes':  nodes_info,
    }
