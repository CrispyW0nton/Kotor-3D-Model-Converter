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

# Models whose supermodel equals one of these names are STANDALONE (not accessories).
# Their skin-mesh vertices are already in model/world space; no world transform needed.
# Used by compute_bounds(), render_bounds(), and FrameRenderer._get_world_verts_for_node().
# Must be kept in sync with FrameRenderer._BASE_SKELETONS in viewport.py.
KOTOR_BASE_SKELETONS: frozenset = frozenset({
    # Standard PC/NPC humanoid base skeletons (K1 + K2)
    'S_FEMALE02', 'S_MALE02', 'S_FEMALE03', 'S_MALE03',
    # Creature / quadruped models – self-contained, never accessories
    'C_BANTHA', 'C_BRITH', 'C_DEWBACK', 'C_DURASTEEL',
    'C_KINRATH', 'C_KATH', 'C_RANCOR', 'C_WRAID', 'C_IRIAZ',
    'C_KHOUNDA', 'C_TARENTATEK', 'C_RANCORM', 'C_TUKE',
    'WARDROID', 'N_WARDROID',
    # Null / self-contained (no supermodel)
    'NULL', '', 'NONE',
})

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
    """
    KotOR model classification byte values.

    Verified against KotorBlender (seedhartha/kotorblender) types.py CLASS_BY_VALUE
    and confirmed against full K1+K2 chitin.key/models.bif model_type bytes.

      0x00 (  0) = OTHER/EFFECT  – room geometry, area modules, FX containers, GUI objects
      0x01 (  1) = EFFECT        – particle FX models (fx_*, hologram variants)
      0x02 (  2) = TILE          – tile/misc models (very few in vanilla)
      0x04 (  4) = CHARACTER     – ALL character/creature/NPC/PC models (c_*, n_*, p_*, ad_*)
      0x08 (  8) = DOOR          – door models (dor_*)
      0x10 ( 16) = LIGHTSABER    – lightsaber blade geometry (w_lghtsbr*, etc.)
      0x20 ( 32) = PLACEABLE     – placeables/inventory items (a_*, gi_*, g_*, waypoints)
      0x40 ( 64) = FLYER         – small creatures/camera models (c_brith, cameras)

    Note: Previous documentation listed DOOR=4, CHARACTER=2 which was INCORRECT.
    The actual KotOR engine uses 4 for characters, 8 for doors.
    LIGHTSABER (0x10=16) was previously missing from this enum.
    """
    EFFECT      = 0    # OTHER in KotorBlender – area/room/FX/GUI geometry
    EFFECTS     = 1    # EFFECT in KotorBlender – particle FX
    TILE        = 2    # TILE in KotorBlender – tile/misc (was MISC)
    CHARACTER   = 4    # CHARACTER – humanoids, creatures, NPCs
    DOOR        = 8    # DOOR – door models
    LIGHTSABER  = 16   # LIGHTSABER (0x10) – saber blade geometry (was MISSING)
    PLACEABLE   = 32   # PLACEABLE in KotorBlender – items/placeables (was ITEM)
    FLYER       = 64   # FLYER in KotorBlender – small creatures/cameras (was RARE_CHAR)

    # Legacy aliases for backwards-compatibility with existing code
    MISC      = 2   # alias for TILE
    ITEM      = 32  # alias for PLACEABLE
    RARE_CHAR = 64  # alias for FLYER

GEOM_FP_K1 = (4273776, 4216096)
GEOM_FP_K2 = (4285200, 4216320)

# ──────────────────────────────────────────────────────────────
#  Character Builder — Part Slots
# ──────────────────────────────────────────────────────────────

from enum import Enum as _Enum

class PartSlot(_Enum):
    """Canonical slot identifiers for character assembly.

    Every visible piece of a KotOR character maps to exactly one slot.
    The slot drives compatibility checking (K1 vs K2, species, body family)
    and determines which panel section an asset appears in inside the
    Assembly mode browser.

    Ordering follows the spec §8.1 / §6 asset-picker categories.
    """
    # ── Head group ───────────────────────────────────────────────────────
    HEAD_SHELL     = "head_shell"      # Primary head geometry (pfhc*, p_hk47, etc.)
    EYES           = "eyes"            # Eyeball geometry (eyeRA, eyeLA, etc.)
    TEETH          = "teeth"           # Teeth mesh (teethupper, teethLo, etc.)
    TONGUE         = "tongue"          # Tongue geometry
    HAIR           = "hair"            # Hair cards / hair geometry
    LASHES         = "lashes"          # Eyelash geometry
    # ── Body group ───────────────────────────────────────────────────────
    HEADLESS_BODY  = "headless_body"   # Body mesh without head (pfbc*, n_darkjedi, etc.)
    BODY_VARIANT   = "body_variant"    # Alternative body LOD / variant mesh
    # ── Attachment group ─────────────────────────────────────────────────
    ACCESSORY      = "accessory"       # Misc accessories (capes, belts, pouches)
    HOOK           = "hook"            # Helper hooks: headhook, MaskHook, GoggleHook, etc.
    # ── Catch-all ────────────────────────────────────────────────────────
    OTHER          = "other"           # Unknown / unclassified part


# Human-readable display name for each slot (used in UI labels)
PART_SLOT_LABELS: Dict[PartSlot, str] = {
    PartSlot.HEAD_SHELL:    "Head Shell",
    PartSlot.EYES:          "Eyeballs",
    PartSlot.TEETH:         "Teeth",
    PartSlot.TONGUE:        "Tongue",
    PartSlot.HAIR:          "Hair",
    PartSlot.LASHES:        "Lashes",
    PartSlot.HEADLESS_BODY: "Headless Body",
    PartSlot.BODY_VARIANT:  "Body Variant",
    PartSlot.ACCESSORY:     "Accessory",
    PartSlot.HOOK:          "Hook / Helper",
    PartSlot.OTHER:         "Other",
}

# ──────────────────────────────────────────────────────────────
#  Quaternion helpers  (used by world_position)
# ──────────────────────────────────────────────────────────────

def _quat_mul(a, b):
    """Multiply two quaternions ``a ⊗ b``, both stored as ``[x, y, z, w]``.

    Convention: XYZW (W last).  This matches:
      * PyKotor ``Vector4`` accessor (x, y, z, w).
      * KotorBlender internal quaternion form.
      * GLM / DirectXMath / three.js.
    The on-disk MDL binary stores W,X,Y,Z — ``kotor_loader._read_node``
    swaps the order at load time, so every caller in GhostRigger sees
    XYZW.  Cross-ref: xoreos ``Common::Matrix4::loadRotate`` reads the
    same (x,y,z,w) form after its own disk conversion.
    """
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [
        aw*bx + ax*bw + ay*bz - az*by,
        aw*by - ax*bz + ay*bw + az*bx,
        aw*bz + ax*by - ay*bx + az*bw,
        aw*bw - ax*bx - ay*by - az*bz,
    ]

def _quat_conjugate(q):
    """Return the conjugate (inverse for unit quaternion) of q = [x,y,z,w]."""
    x, y, z, w = q
    # Normalize first to ensure unit length
    l2 = x*x + y*y + z*z + w*w
    if l2 > 1e-9:
        l = math.sqrt(l2)
        x /= l; y /= l; z /= l; w /= l
    return (-x, -y, -z, w)

def _quat_rotate(q, v):
    """Rotate vector ``v`` by quaternion ``q = [x, y, z, w]``.

    Uses the standard two-cross-product form
        v' = v + 2·qw·(q_xyz × v) + 2·(q_xyz × (q_xyz × v))
    which is equivalent to the ``q · v · q*`` sandwich for unit
    quaternions and matches xoreos ``Common::Matrix4::rotate`` and
    KotOR.js ``THREE.Quaternion.multiplyVector``.  See ``_quat_mul``
    for the XYZW storage convention.
    """
    qx, qy, qz, qw = q
    # Normalize q to avoid drift
    l2 = qx*qx + qy*qy + qz*qz + qw*qw
    if l2 > 1e-9:
        l = math.sqrt(l2)
        qx /= l; qy /= l; qz /= l; qw /= l
    vx, vy, vz = v
    # t = 2 * cross(q.xyz, v)
    tx = 2*(qy*vz - qz*vy)
    ty = 2*(qz*vx - qx*vz)
    tz = 2*(qx*vy - qy*vx)
    # result = v + qw * t + cross(q.xyz, t)
    rx = vx + qw*tx + qy*tz - qz*ty
    ry = vy + qw*ty + qz*tx - qx*tz
    rz = vz + qw*tz + qx*ty - qy*tx
    return rx, ry, rz


def _quat_normalize(q):
    """Normalize a quaternion to unit length without any special-case collapsing."""
    x, y, z, w = q
    l2 = x*x + y*y + z*z + w*w
    if l2 < 1e-9:
        return [0.0, 0.0, 0.0, 1.0]
    l = math.sqrt(l2)
    return [x/l, y/l, z/l, w/l]


def _quat_normalize_bind(q):
    """
    Normalize quaternion and handle the NWN/KotOR coordinate-flip convention.

    NWN binary MDL stores quaternions as (x, y, z, w).  Root/dummy nodes often
    carry (1, 0, 0, 0) which is a 180° rotation about X used by the NWN exporter
    to convert Y-up (Max/Maya) space into the engine's Z-up bind pose.  When we
    accumulate this through the parent chain it causes downstream child positions
    to flip sign incorrectly.

    FIX (v4.0): Only collapse PURE X-AXIS 180° rotations — i.e. (±1, 0, 0, 0).
    This is the only genuine NWN coord-flip axis used by the Odyssey exporter.

    CRITICAL: Y-axis (0,±1,0,0) and Z-axis (0,0,±1,0) 180° rotations are REAL
    geometry transforms used in droid and creature models (e.g. c_drdassassin,
    c_warbot, c_brith) to mirror limb geometry between left and right sides.
    Collapsing these to identity causes mirrored limbs to appear in the wrong
    orientation — visible as "one leg facing forward, one rotated 180°" in the
    viewport.  They MUST be preserved so child node positions transform correctly.

    Retained behaviours:
      • (±1, 0, 0, 0) – 180° about X (NWN Y→Z coord flip) → collapse to identity
      • (0, ±1, 0, 0) – 180° about Y (real limb mirror)    → PRESERVE
      • (0,  0, ±1,0) – 180° about Z (real limb mirror)    → PRESERVE
      • All other real joint rotations                       → PRESERVE (normalize)

    Real half-angle rotations (e.g. 45° = w≈0.924, xyz≈0.383) are kept as-is.
    """
    x, y, z, w = q
    # Only collapse PURE X-axis 180° rotation: (±1, 0, 0, 0)
    # Test: |w| ≈ 0, |x| ≈ 1, y ≈ 0, z ≈ 0
    if abs(w) < 0.05:
        if abs(abs(x) - 1.0) < 0.05 and abs(y) < 0.05 and abs(z) < 0.05:
            # Pure X-axis 180° (NWN coord-flip) → collapse to identity
            return [0.0, 0.0, 0.0, 1.0]
        # All other 180-degree rotations (Y-axis, Z-axis, diagonal) are REAL
        # geometry/limb transforms — normalize and preserve them.
    # Return normalized quaternion
    l2 = x*x + y*y + z*z + w*w
    if l2 < 1e-9:
        return [0.0, 0.0, 0.0, 1.0]
    l = math.sqrt(l2)
    return [x/l, y/l, z/l, w/l]

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
    # UV sets 2 and 3 (MDX Texture2/Texture3 channels – rarely used in vanilla KotOR)
    uvs_2:        List[Tuple[float,float]]       = field(default_factory=list)
    uvs_3:        List[Tuple[float,float]]       = field(default_factory=list)
    faces:        List[Tuple[int,int,int]]       = field(default_factory=list)
    face_mats:    List[int]                      = field(default_factory=list)
    # face_uvs: per-face tvert (texture-vertex) index triples.
    # Used by ASCII MDL parser where tvert indices differ from vertex indices.
    # When empty (binary MDL or single-index ASCII), uvs[] is accessed directly
    # using the vertex index.  When non-empty, uvs[face_uvs[fi][0..2]] gives
    # the UV for each face vertex.
    face_uvs:     List[Tuple[int,int,int]]       = field(default_factory=list)

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
    # UV animation (animate_uv flag + scroll/jitter params from mesh header)
    animate_uv:   bool  = False
    uv_dir_x:     float = 0.0   # UV scroll speed X
    uv_dir_y:     float = 0.0   # UV scroll speed Y
    uv_jitter:    float = 0.0   # UV jitter magnitude
    uv_jitter_speed: float = 0.0  # UV jitter speed

    # ── Multi-texture support ──
    # KotOR binary MDL stores tex_count in the mesh header.  When tex_count > 1
    # the node carries multiple material zones: face_mats[i] is the 0-based index
    # of the texture that face i uses.  texture_names[0] == texture (primary),
    # texture_names[1] == secondary texture (often stored in the lightmap slot
    # when has_lightmap=False and tex_count==2), etc.
    # Viewport rendering MUST use texture_names[face_mats[fi]] per face.
    tex_count:      int        = 1                          # number of texture slots
    texture_names:  List[str]  = field(default_factory=list)  # [slot0, slot1, ...]

    # ── TXI metadata (parsed from embedded TPC TXI or standalone .txi file) ──
    # These fields affect how the texture is rendered:
    #   txi_blending      : 0=none, 1=additive, 2=punchthrough
    #   txi_cube          : True if texture is a cubemap (env sphere/cube map)
    #   txi_proceduretype : animation type ('cycle','water','arturo', etc.)
    #   txi_numx/numy     : flipbook grid dimensions (used with proceduretype='cycle')
    #   txi_fps           : flipbook animation frames-per-second
    #   txi_envmaptexture : name of environment-map companion texture
    #                       (set by both 'envmaptexture' AND 'bumpyshinytexture' TXI cmds)
    #   txi_bumpmaptexture: name of bumpmap / normal-map companion texture
    #   txi_bumpmapscaling: bumpmap intensity scale factor
    #   txi_rotate        : additional UV rotation in degrees (from TXI 'rotate' cmd)
    #   txi_loop          : True if animation should loop
    #   txi_clamp_s/t     : True = clamp-to-edge, False = repeat (GL_REPEAT default)
    #   txi_wateralpha    : TXI wateralpha (0..1) — semi-transparent water/glass surfaces
    #   txi_decal         : True = decal surface (alpha used as blend weight over bg)
    #   txi_isbumpmap     : True = this texture IS a bump/normal map (affects its loading)
    #   txi_islightmap    : True = this texture IS a lightmap
    txi_blending:       int   = 0
    txi_cube:           bool  = False
    txi_proceduretype:  str   = ''
    txi_numx:           int   = 0
    txi_numy:           int   = 0
    txi_fps:            float = 0.0
    txi_envmaptexture:  str   = ''
    txi_bumpmaptexture: str   = ''
    txi_bumpmapscaling: float = 1.0
    txi_rotate:         float = 0.0    # extra UV rotation (degrees) from TXI
    txi_loop:           bool  = True
    txi_clamp_s:        bool  = False  # S (U) wrap mode: False=repeat, True=clamp
    txi_clamp_t:        bool  = False  # T (V) wrap mode
    txi_wateralpha:     float = 1.0    # Water/transparency alpha multiplier (TXI wateralpha)
    txi_decal:          bool  = False  # TXI decal: alpha is blend weight over background
    txi_isbumpmap:      bool  = False  # TXI isbumpmap: this texture is a bump/normal map
    txi_islightmap:     bool  = False  # TXI islightmap: this texture is a lightmap
    txi_specularcolour: str   = ''     # Specular colour map texture name
    txi_alpha_test:    float = 0.5   # Per-node punchthrough threshold from TPC header [4-7]
                                      # Kotor.NET KotorModelLoader.cs: TransparencyHint at +84,
                                      # alpha_test float at TPC header bytes [4-7] (Aurora engine).
                                      # Default 0.5 matches the engine default discard threshold.

    # ── Skin weights ──
    skin_data:       List[VertexSkinData] = field(default_factory=list)
    bone_map:        List[str]            = field(default_factory=list)   # bone_map[i] = bone node name ('' = unused)
    bone_map_floats: List[float]          = field(default_factory=list)   # raw float32 values from MDL
    # v7.1 FIX-QBONETBONE (Finding 2.5 — reone mdlmdxreader.cpp cross-ref):
    # qBone/tBone arrays store per-bone bind-pose transforms from the MDL skin
    # header.  reone (lines 280-292) reads qBone quaternions AND tBone translation
    # vectors, then constructs per-bone bind matrices.  KotorBlender reads them
    # but doesn't use them (Blender reconstructs from world matrices).
    # We store them as fallback bind matrices for FBX export when
    # world_transform() computation fails (e.g. missing parent chain).
    # Format: qbone_list[i] = (qx, qy, qz, qw) quaternion for bone i
    #         tbone_list[i] = (tx, ty, tz) translation for bone i
    qbone_list: List[Tuple[float,float,float,float]] = field(default_factory=list)
    tbone_list: List[Tuple[float,float,float]]       = field(default_factory=list)

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

    # ── K2/TSL extra mesh fields (Kotor.NET TrimeshHeader TSLUnknown1/2) ──
    # Layout of the 8 bytes after the flag sequence in K2/TSL trimesh headers:
    #   byte 0: dirtenabled      — 1 = dirt decal overlay enabled
    #   byte 1: padding
    #   uint16 2-3: dirt_texture — dirt texture index (into global texture table)
    #   uint16 4-5: dirt_coord_space — coordinate space for dirt mapping
    #   byte 6: hide_in_holograms — 1 = do NOT render this mesh in hologram mode
    #   byte 7: padding
    # Reference: Kotor.NET MDLBinaryStructure.cs TrimeshHeader.TSLUnknown1/2 comment
    dirt_enabled:       bool  = False   # K2 only: dirt decal overlay
    dirt_texture:       int   = 0       # K2 only: dirt texture slot index
    dirt_coord_space:   int   = 0       # K2 only: dirt mapping coordinate space
    hide_in_holograms:  bool  = False   # K2 only: hide mesh in hologram rendering mode

    # ── Mesh average position (from TrimeshHeader AveragePoint / AveragePosition) ──
    # The Aurora engine stores the centroid of all face vertices (average of all vertex
    # positions) in the mesh header.  Used for transparent surface depth sorting:
    # when available, this gives a more accurate centroid than the bounding-box midpoint.
    # Kotor.NET: TrimeshHeader.AveragePoint; xoreos: _averagePoint.
    mesh_average_point: Tuple[float,float,float] = (0.0, 0.0, 0.0)

    # ── Trimesh header opaque fields ──
    # The 24 bytes at trimesh-header offset +152 are parsed as opaque data by
    # PyKotor, KotorBlender, and Kotor.NET (formerly mis-labelled in our writer
    # as ``bm3_name`` + ``bm4_name``).  We preserve the raw bytes captured at
    # load time so round-trip writing reproduces the source file byte-for-byte.
    mesh_unknown0: bytes = b"\x00" * 24

    # Bounding sphere / box
    bb_min: Tuple[float,float,float] = (0.0, 0.0, 0.0)
    bb_max: Tuple[float,float,float] = (0.0, 0.0, 0.0)
    radius: float = 0.0

    # D20-M: Per-node vertex coordinate space.
    # Computed at load time by vertex_space.compute_vertex_space().
    # 0 = NODE_LOCAL (apply world_transform), 1 = WORLD (no transform),
    # 2 = AABB_WALK (walkmesh, skip rendering).
    vertex_space: int = 0  # default NODE_LOCAL

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
    def is_reference(self): return bool(self.flags & NodeFlags.REFERENCE)
    @property
    def is_aabb(self):      return bool(self.flags & NodeFlags.AABB)
    @property
    def is_dummy(self):
        return self.flags == int(NodeFlags.HEADER)

    @property
    def texture_clean(self) -> str:
        """Return texture name with null bytes and binary garbage removed."""
        if not self.texture:
            return ''
        # Stop at first non-printable character
        out = []
        for ch in self.texture:
            if 32 <= ord(ch) <= 126:
                out.append(ch)
            else:
                break
        return ''.join(out).strip()

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
        """
        Compute the world-space position of this node by walking up the
        parent chain.

        KotOR coordinate system:
          - Y-forward, Z-up (right-handed).
          - Vertex positions in binary MDL are stored relative to the node's
            LOCAL pivot (i.e. node-local space).  The node position/rotation
            describe how the bone's pivot point is placed relative to its
            parent's pivot in the bind pose.
          - The root dummy node and many intermediate nodes carry
            (1, 0, 0, 0) — a 180° rotation about X — which is the standard
            NWN exporter convention to convert from the DCC tool's Y-up space
            into KotOR's Z-up game space.  When we naively accumulate these
            through the chain the even number of 180° flips cancels in the
            global orientation, but ODD-depth child positions flip sign
            incorrectly.  We therefore collapse 180°-about-axis rotations on
            PARENT (non-leaf) nodes using `_quat_normalize_bind` so that child
            positions sum correctly.

        Algorithm:
          Walk the chain from root to self, accumulating a world orientation
          quaternion (with 180°-axis flips on parent nodes collapsed to identity).
          At each node, rotate the node's local position by the PARENT's
          accumulated orientation, then add to the world position.
        """
        chain: List['ModelNode'] = []
        n = self
        _visited: set = set()   # cycle guard for corrupted MDL data
        while n is not None:
            nid = id(n)
            if nid in _visited:
                break   # break cycle silently
            _visited.add(nid)
            chain.append(n)
            n = n.parent
            if len(chain) > 512:   # safety cap: no valid KotOR model is deeper than 512
                break
        chain.reverse()  # root first

        wx, wy, wz = 0.0, 0.0, 0.0
        # Accumulated orientation of the PARENT at each step (start: identity)
        parent_orientation = [0.0, 0.0, 0.0, 1.0]   # xyzw quaternion

        for i, node in enumerate(chain):
            lx, ly, lz = node.position
            # Rotate this node's LOCAL position by parent's accumulated orientation
            rx, ry, rz = _quat_rotate(parent_orientation, (lx, ly, lz))
            wx += rx; wy += ry; wz += rz

            # For PARENT nodes in the chain: collapse 180°-about-axis rotations
            # to identity (NWN coord-flip convention fixes position accumulation).
            # For the LEAF (last) node: use the actual rotation unchanged,
            # because it will be used to orient geometry/vertices.
            is_leaf = (i == len(chain) - 1)
            if is_leaf:
                # Preserve leaf rotation exactly (important for non-skin mesh nodes)
                bind_rot = _quat_normalize(node.rotation)
            else:
                bind_rot = _quat_normalize_bind(node.rotation)
            parent_orientation = _quat_mul(parent_orientation, bind_rot)

        return (wx, wy, wz)

    def bone_world_position(self) -> Tuple[float, float, float]:
        """
        Return the world-space PIVOT position of this node for skeleton/bone rendering.

        Unlike world_position() (which preserves the leaf node's actual rotation for
        vertex transforms), this method collapses 180°-about-axis rotations on ALL
        nodes in the chain — including the leaf.  This gives the correct pivot point
        for displaying joint dots in the skeleton overlay, since we want the joint's
        POSITION in world space regardless of its orientation.

        Use this instead of world_position() when placing bone gizmos/dots.
        """
        chain: List['ModelNode'] = []
        n = self
        _visited2: set = set()
        while n is not None:
            nid = id(n)
            if nid in _visited2:
                break
            _visited2.add(nid)
            chain.append(n)
            n = n.parent
            if len(chain) > 512:
                break
        chain.reverse()

        wx, wy, wz = 0.0, 0.0, 0.0
        parent_orientation = [0.0, 0.0, 0.0, 1.0]

        for node in chain:
            lx, ly, lz = node.position
            rx, ry, rz = _quat_rotate(parent_orientation, (lx, ly, lz))
            wx += rx; wy += ry; wz += rz
            bind_rot = _quat_normalize_bind(node.rotation)
            parent_orientation = _quat_mul(parent_orientation, bind_rot)

        return (wx, wy, wz)

    def world_transform(self) -> Tuple[Tuple[float,float,float],
                                       Tuple[float,float,float,float]]:
        """
        Returns (world_position, world_orientation_quat) for this node.

        CRITICAL FIX for Wardroid / c_brith / droid model rendering:
          - Parent chain nodes: use _quat_normalize_bind (collapse 180°-flips)
            so that child NODE POSITIONS accumulate correctly.
          - The LEAF node's own rotation: use the RAW (non-collapsed) rotation,
            because this orientation is used to transform VERTEX positions from
            node-local to world space.  Collapsing 180° rotations on mesh nodes
            caused mirrored/rotated body parts to appear in the wrong orientation.

        For SKIN nodes the vertex transform is translation-only (rotation is
        already baked into vertex positions by the NWN/KotOR exporter), so this
        fix only affects non-skin trimesh nodes with 180°-rotated bind poses.
        """
        chain: List['ModelNode'] = []
        n = self
        _visited3: set = set()
        while n is not None:
            nid = id(n)
            if nid in _visited3:
                break
            _visited3.add(nid)
            chain.append(n)
            n = n.parent
            if len(chain) > 512:
                break
        chain.reverse()

        wx, wy, wz = 0.0, 0.0, 0.0
        aq = [0.0, 0.0, 0.0, 1.0]
        last_i = len(chain) - 1

        for i, node in enumerate(chain):
            lx, ly, lz = node.position
            rx, ry, rz = _quat_rotate(aq, (lx, ly, lz))
            wx += rx; wy += ry; wz += rz
            # Leaf node: preserve actual rotation for vertex transform
            # Parent nodes: collapse 180°-flips for correct position chain
            if i == last_i:
                bind_rot = _quat_normalize(node.rotation)
            else:
                bind_rot = _quat_normalize_bind(node.rotation)
            aq = _quat_mul(aq, bind_rot)

        return (wx, wy, wz), tuple(aq)

    def compute_tangents(self) -> None:
        """
        Compute per-vertex tangent vectors using the Lengyel (2001) Gram-Schmidt
        method and store them in ``self.tangents``.

        References:
          - Lengyel, *Mathematics for 3D Game Programming* §7.8.3
          - Lengyel, *FGED Vol.2: Rendering* §7
          - Game Engine Architecture §11.1

        Algorithm
        ---------
        For each triangle we compute the tangent vector from the UV-space and
        position-space edge vectors (standard "UV gradient" method), then
        accumulate the tangent contributions per vertex, and finally
        Gram-Schmidt orthogonalize against the vertex normal.

        Bitangents are NOT stored here; they can be recomputed at render time
        via ``cross(normal, tangent)``.  The tangent w-component (handedness,
        ±1) is not stored in this Python list — it is always +1 for KotOR MDL
        geometry; store it explicitly if you need GPU upload.

        If UV data is missing, a default tangent (1,0,0) is used.
        """
        nv = len(self.vertices)
        if nv == 0 or not self.faces:
            self.tangents = []
            return

        # Accumulation buffers
        tan: List[List[float]] = [[0.0, 0.0, 0.0] for _ in range(nv)]

        verts = self.vertices
        norms = self.normals
        uvs   = self.uvs

        for fi, face in enumerate(self.faces):
            if len(face) < 3:
                continue
            i0, i1, i2 = face[0], face[1], face[2]
            if i0 >= nv or i1 >= nv or i2 >= nv:
                continue

            # Get UVs — honour face_uvs when present (ASCII MDL tvert indexing)
            if self.face_uvs and fi < len(self.face_uvs):
                fu = self.face_uvs[fi]
                u0 = uvs[fu[0]] if uvs and fu[0] < len(uvs) else (0.0, 0.0)
                u1 = uvs[fu[1]] if uvs and fu[1] < len(uvs) else (0.0, 0.0)
                u2 = uvs[fu[2]] if uvs and fu[2] < len(uvs) else (0.0, 0.0)
            else:
                u0 = uvs[i0] if uvs and i0 < len(uvs) else (0.0, 0.0)
                u1 = uvs[i1] if uvs and i1 < len(uvs) else (0.0, 0.0)
                u2 = uvs[i2] if uvs and i2 < len(uvs) else (0.0, 0.0)

            # Position deltas
            v0 = verts[i0]; v1 = verts[i1]; v2 = verts[i2]
            dx1 = v1[0]-v0[0]; dy1 = v1[1]-v0[1]; dz1 = v1[2]-v0[2]
            dx2 = v2[0]-v0[0]; dy2 = v2[1]-v0[1]; dz2 = v2[2]-v0[2]

            # UV deltas
            ds1 = u1[0]-u0[0]; dt1 = u1[1]-u0[1]
            ds2 = u2[0]-u0[0]; dt2 = u2[1]-u0[1]

            r = ds1*dt2 - ds2*dt1
            if abs(r) < 1e-9:
                # Degenerate UV triangle — use world X axis as fallback tangent
                tx, ty, tz = 1.0, 0.0, 0.0
            else:
                inv_r = 1.0 / r
                tx = inv_r * (dt2*dx1 - dt1*dx2)
                ty = inv_r * (dt2*dy1 - dt1*dy2)
                tz = inv_r * (dt2*dz1 - dt1*dz2)

            for vi in (i0, i1, i2):
                tan[vi][0] += tx
                tan[vi][1] += ty
                tan[vi][2] += tz

        # Gram-Schmidt orthogonalization against vertex normals
        result: List[Tuple[float,float,float]] = []
        for vi in range(nv):
            n_vec = norms[vi] if (norms and vi < len(norms)) else (0.0, 0.0, 1.0)
            t_vec = tan[vi]
            # t' = normalize(t - (n · t) * n)
            dot = n_vec[0]*t_vec[0] + n_vec[1]*t_vec[1] + n_vec[2]*t_vec[2]
            ox = t_vec[0] - dot*n_vec[0]
            oy = t_vec[1] - dot*n_vec[1]
            oz = t_vec[2] - dot*n_vec[2]
            mag = math.sqrt(ox*ox + oy*oy + oz*oz)
            if mag > 1e-9:
                result.append((ox/mag, oy/mag, oz/mag))
            else:
                result.append((1.0, 0.0, 0.0))   # degenerate — use X axis

        self.tangents = result

    def compute_tangents(self) -> None:
        """
        Compute per-vertex tangent vectors using the Lengyel (2001) Gram-Schmidt
        method and populate ``self.tangents``.

        References:
          - Lengyel, *Mathematics for 3D Game Programming* §7.8.3
          - Lengyel, *FGED Vol.2: Rendering* §7
          - Eric Lengyel, "Computing Tangent Space Basis Vectors for an Arbitrary
            Mesh", Terathon Software, 2001.

        Algorithm:
          For each triangle, compute edge vectors in position and UV space, derive
          the tangent direction, accumulate into per-vertex sums, then
          Gram-Schmidt orthogonalize against the vertex normal.

        Notes:
          - Bitangent is NOT stored separately; recompute at render time via
            ``cross(normal, tangent)``.
          - Degenerate UVs (zero-area UV triangle) fall back to (1,0,0).
          - Respects ``face_uvs`` ASCII-MDL indexing when present.
          - Skips non-mesh nodes gracefully.
        """
        nv = len(self.vertices)
        if nv == 0 or not self.faces:
            self.tangents = []
            return

        # Accumulate raw tangent sums per vertex
        tan_sum: List[List[float]] = [[0.0, 0.0, 0.0] for _ in range(nv)]

        for fi, face in enumerate(self.faces):
            if len(face) < 3:
                continue
            i0, i1, i2 = face[0], face[1], face[2]
            if i0 >= nv or i1 >= nv or i2 >= nv:
                continue

            # Positions
            p0 = self.vertices[i0]; p1 = self.vertices[i1]; p2 = self.vertices[i2]
            e1x = p1[0]-p0[0]; e1y = p1[1]-p0[1]; e1z = p1[2]-p0[2]
            e2x = p2[0]-p0[0]; e2y = p2[1]-p0[1]; e2z = p2[2]-p0[2]

            # UV coordinates — respect face_uvs if present
            if self.face_uvs and fi < len(self.face_uvs):
                ti0, ti1, ti2 = self.face_uvs[fi]
            else:
                ti0, ti1, ti2 = i0, i1, i2

            def _get_uv(ti):
                if self.uvs and ti < len(self.uvs):
                    return self.uvs[ti]
                return (0.0, 0.0)

            uv0 = _get_uv(ti0); uv1 = _get_uv(ti1); uv2 = _get_uv(ti2)
            du1 = uv1[0]-uv0[0]; dv1 = uv1[1]-uv0[1]
            du2 = uv2[0]-uv0[0]; dv2 = uv2[1]-uv0[1]

            denom = du1*dv2 - du2*dv1
            if abs(denom) < 1e-9:
                # Degenerate UV triangle — use default tangent direction
                tx, ty, tz = 1.0, 0.0, 0.0
            else:
                r = 1.0 / denom
                tx = (dv2*e1x - dv1*e2x) * r
                ty = (dv2*e1y - dv1*e2y) * r
                tz = (dv2*e1z - dv1*e2z) * r

            for vi in (i0, i1, i2):
                tan_sum[vi][0] += tx
                tan_sum[vi][1] += ty
                tan_sum[vi][2] += tz

        # Gram-Schmidt orthogonalization against vertex normal
        result: List[Tuple[float, float, float]] = []
        for vi in range(nv):
            if self.normals and vi < len(self.normals):
                nx, ny, nz = self.normals[vi]
            else:
                nx, ny, nz = 0.0, 0.0, 1.0

            tx, ty, tz = tan_sum[vi]

            # Gram-Schmidt: t' = normalize(t - (n·t)*n)
            dot = nx*tx + ny*ty + nz*tz
            ox = tx - dot*nx
            oy = ty - dot*ny
            oz = tz - dot*nz

            mag = math.sqrt(ox*ox + oy*oy + oz*oz)
            if mag > 1e-9:
                result.append((ox/mag, oy/mag, oz/mag))
            else:
                result.append((1.0, 0.0, 0.0))   # degenerate fallback

        self.tangents = result

    def clone_shallow(self) -> 'ModelNode':
        n = ModelNode(name=self.name, flags=self.flags, index=self.index)
        n.position = self.position
        n.rotation = self.rotation
        n.texture  = self.texture
        n.diffuse  = self.diffuse
        n.ambient  = self.ambient
        n.shininess = self.shininess
        # Phase 3.7 fields
        n.mesh_average_point = self.mesh_average_point
        n.mesh_unknown0      = self.mesh_unknown0
        n.hide_in_holograms  = self.hide_in_holograms
        n.dirt_enabled       = self.dirt_enabled
        n.dirt_texture       = self.dirt_texture
        n.dirt_coord_space   = self.dirt_coord_space
        # Phase 3.8 TXI fields
        n.txi_specularcolour  = self.txi_specularcolour
        n.txi_envmaptexture   = self.txi_envmaptexture
        n.txi_bumpmaptexture  = self.txi_bumpmaptexture
        n.txi_bumpmapscaling  = self.txi_bumpmapscaling
        n.txi_blending        = self.txi_blending
        n.txi_alpha_test      = self.txi_alpha_test
        n.txi_wateralpha      = self.txi_wateralpha
        n.txi_decal           = self.txi_decal
        n.txi_isbumpmap       = self.txi_isbumpmap
        n.txi_islightmap      = self.txi_islightmap
        n.txi_proceduretype   = self.txi_proceduretype
        n.txi_numx            = self.txi_numx
        n.txi_numy            = self.txi_numy
        n.txi_fps             = self.txi_fps
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
    # subclassification (model header byte +1, binary offset 0x51):
    #   Preserved verbatim from binary.  PyKotor confirms defaults:
    #   4 for Placeable class, 0 for all other classifications.
    #   Purpose remains undocumented by Bioware; treat as opaque uint8.
    subclassification: int  = 0
    # unknown_byte (model header byte +2, binary offset 0x52):
    #   PyKotor wiki notes "possibly smoothing-related". Always 0 in vanilla K1/K2.
    #   Preserved verbatim for binary round-trip fidelity.
    unknown_byte:      int  = 0
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

    @property
    def nodes(self) -> List[ModelNode]:
        """Convenience alias for all_nodes() — returns all nodes in DFS order.

        Provided so that code written against the naive ``model.nodes`` API
        (common in external scripts and documentation examples) works without
        needing to call the method explicitly.  Internally delegates to
        ``all_nodes()``.
        """
        return self.all_nodes()

    def all_nodes(self) -> List[ModelNode]:
        """Return all nodes in DFS order using an iterative stack.

        The original recursive _walk hit Python's recursion limit (~1 000 frames)
        on deeply nested or unusual models such as c_brith (RARE_CHAR type-64).
        This iterative version handles arbitrarily deep hierarchies safely.

        A visited-ID set guards against cyclic node references (e.g. corrupt MDL
        data or test fixtures that deliberately create cycles) — without the guard
        a cycle would cause an infinite loop and hang the process.
        """
        result: List[ModelNode] = []
        if not self.root_node:
            return result
        stack = [self.root_node]
        visited: set = set()
        while stack:
            n = stack.pop()
            nid = id(n)
            if nid in visited:
                continue
            visited.add(nid)
            result.append(n)
            # Push children in reverse so first child is processed first
            for c in reversed(n.children):
                if id(c) not in visited:
                    stack.append(c)
        return result

    def mesh_nodes(self) -> List[ModelNode]:
        return [n for n in self.all_nodes() if n.is_mesh]

    def bone_nodes(self) -> List[ModelNode]:
        """Return all skeleton/joint nodes (non-mesh dummy nodes).

        Captures BOTH kinds of non-mesh nodes:
          - flags=HEADER (0x01) — model root and PyKotor-loaded dummy nodes
          - flags=0x00          — pure bone joints in binary-parsed models

        Previously this only returned nodes where is_dummy=True (flags==HEADER),
        silently omitting all flags=0 bone nodes from the skeleton list.
        """
        return [n for n in self.all_nodes() if n.type_label == 'dummy']

    def find_node(self, name: str) -> Optional[ModelNode]:
        nl = name.lower()
        for n in self.all_nodes():
            if n.name.lower() == nl: return n
        return None

    def compute_all_tangents(self) -> int:
        """
        Compute per-vertex tangent vectors for all mesh nodes that have UVs.

        Calls ``ModelNode.compute_tangents()`` on every mesh node.
        Returns the number of nodes that were processed.

        This should be called once after model load (mdl_parser already calls
        compute_bounds at parse time; tangents are computed lazily here so that
        callers that don't need TBN don't pay the cost).

        The computed tangents are stored in ``node.tangents`` and used by:
          - The GPU renderer (Phase 5) to build TBN matrices in the vertex shader
          - The diagnostics panel to report tangent data availability
          - The normal-map export pipeline (src/converters/normal_map.py)

        Reference: Lengyel §7.8.3; FGED Vol.2 §7 (TBN for normal mapping).
        """
        count = 0
        for n in self.mesh_nodes():
            if n.vertices and n.uvs:
                n.compute_tangents()
                count += 1
        return count

    def compute_bounds(self):
        """
        Compute model bounding box in world space.

        D20-M: Uses per-node vertex_space contract.
        NODE_LOCAL (0): apply world_transform (rotate + translate)
        WORLD (1): use vertices as-is (already world-space)
        AABB_WALK (2): skip (walkmesh, not rendered)

        All KotOR MDL vertices are NODE_LOCAL per xoreos and KotOR.js.
        """
        verts_world = []
        for n in self.all_nodes():
            if not n.vertices:
                continue
            if not (n.is_mesh or n.is_skin):
                continue

            vs = getattr(n, 'vertex_space', 0)  # default NODE_LOCAL
            if vs == 2:  # AABB_WALK — skip walkmesh nodes
                continue
            if vs == 1:  # WORLD — already world-space
                verts_world.extend(n.vertices)
                continue

            # NODE_LOCAL — apply full world transform (single application)
            wp, wo = n.world_transform()
            wo_rot = math.sqrt(wo[0]*wo[0] + wo[1]*wo[1] + wo[2]*wo[2])
            is_id = (wo_rot < 0.001)
            if is_id:
                wx, wy, wz = wp[0], wp[1], wp[2]
                verts_world.extend((v[0]+wx, v[1]+wy, v[2]+wz) for v in n.vertices)
            else:
                for v in n.vertices:
                    rx, ry, rz = _quat_rotate(wo, v)
                    verts_world.append((rx + wp[0], ry + wp[1], rz + wp[2]))

        if not verts_world:
            return
        xs=[v[0] for v in verts_world]
        ys=[v[1] for v in verts_world]
        zs=[v[2] for v in verts_world]
        self.bb_min = (min(xs), min(ys), min(zs))
        self.bb_max = (max(xs), max(ys), max(zs))
        cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
        self.radius = max(math.sqrt((v[0]-cx)**2+(v[1]-cy)**2+(v[2]-cz)**2)
                         for v in verts_world)

    def render_bounds(self):
        """
        Compute bounding box of only the *visible* (rendered) mesh nodes.

        Visible nodes are those with:
          - UV coordinates (deformation-helper trimeshes that lack UVs are excluded)
          - A real texture name (non-null) OR are skin nodes
          - Not ending in _g / _G (deformation-helper name pattern)

        This matches the viewport's _is_deformation_helper() rules so that the camera
        is framed exactly on the renderable geometry.

        Smart accessory handling: for models with a non-standard supermodel (not NULL
        and not a base skeleton like S_Female02/S_Male02), large skin-mesh outliers
        that lie far from the model's non-skin geometry are excluded from framing.
        This correctly frames cutscene overlay / accessory models (e.g. ad_saul which
        contains a body proxy skin mesh far below the actual face accessory).

        Falls back to compute_bounds() values if no UV nodes are found.
        """
        def _is_render_helper(n):
            """Mirror of FrameRenderer._is_deformation_helper() in viewport.py."""
            # OBJ / FBX imported nodes: always renderable — skip all heuristics
            if getattr(n, '_imported', False):
                return False
            raw = n.texture or ''
            t = raw.strip()
            for ext in ('.tga', '.tpc', '.dds', '.png'):
                if t.lower().endswith(ext):
                    t = t[:-4]
            tex = t.strip()
            is_null = (not tex or tex.upper() == 'NULL')

            # Skin node with a real texture and valid (non-extreme) UVs → visible
            if n.is_skin and not is_null and n.uvs:
                has_extreme = any(abs(u) > 3.0 or abs(v) > 3.0
                                  for u, v in n.uvs[:20])
                if not has_extreme:
                    return False

            if n.uvs:
                if any(abs(u) > 3.0 or abs(v) > 3.0 for u, v in n.uvs[:20]):
                    return True

            # Non-skin _g / _G or _dum nodes are ALWAYS deform helpers
            name_lower = n.name.lower()
            if not n.is_skin and (name_lower.endswith('_g')
                                  or name_lower.endswith('_g0')
                                  or name_lower.endswith('_dum')):
                return True

            # Null-texture non-skin nodes are deformation helpers
            if is_null and not n.is_skin:
                return True

            # Null-texture skin nodes with no / all-zero UVs
            if is_null and n.is_skin and (not n.uvs
                    or all(u == 0.0 and v == 0.0 for u, v in n.uvs[:5])):
                return True

            return False

        def _node_world_verts(n):
            """Return list of world-space (x,y,z) tuples for a mesh node.

            D20-M: Uses per-node vertex_space contract.
            NODE_LOCAL (0): apply world_transform (rotate + translate).
            WORLD (1): use vertices as-is (already world-space).
            AABB_WALK (2): skip (walkmesh, not rendered).

            References:
              xoreos model_kotor.cpp readMesh — raw MDX read, no transform
              KotOR.js OdysseyModel3D.ts      — matrixWorld for GPU
            """
            vs = getattr(n, 'vertex_space', 0)  # default NODE_LOCAL
            if vs == 2:  # AABB_WALK
                return []
            if vs == 1:  # WORLD
                return list(n.vertices)

            # NODE_LOCAL — apply full world transform (single application)
            wp, wo = n.world_transform()
            wo_rot = math.sqrt(wo[0]*wo[0] + wo[1]*wo[1] + wo[2]*wo[2])
            is_id = (wo_rot < 0.001)
            if is_id:
                wx, wy, wz = wp[0], wp[1], wp[2]
                return [(v[0]+wx, v[1]+wy, v[2]+wz) for v in n.vertices]
            else:
                result = []
                for v in n.vertices:
                    rx, ry, rz = _quat_rotate(wo, v)
                    result.append((rx + wp[0], ry + wp[1], rz + wp[2]))
                return result

        # D20-M: Collect world-space vertices from all visible (rendered) nodes.
        # No accessory/outlier heuristics — the vertex_space contract in
        # _node_world_verts handles the correct transform for every node type.
        all_verts = []

        for n in self.all_nodes():
            if not n.vertices:
                continue
            if not (n.is_mesh or n.is_skin):
                continue
            # Skip AABB_WALK nodes (walkmesh)
            if getattr(n, 'vertex_space', 0) == 2:
                continue
            if _is_render_helper(n):
                continue
            # Skip UV-less non-skin nodes UNLESS they are explicitly imported
            if not n.uvs and not getattr(n, '_imported', False):
                continue

            wv = _node_world_verts(n)
            if not wv:
                continue
            all_verts.extend(wv)

        if not all_verts:
            # Last resort: full model bounds
            return self.bb_min, self.bb_max

        xs = [v[0] for v in all_verts]
        ys = [v[1] for v in all_verts]
        zs = [v[2] for v in all_verts]

        rbb_min = (min(xs), min(ys), min(zs))
        rbb_max = (max(xs), max(ys), max(zs))
        return rbb_min, rbb_max

    def node_count(self) -> int:
        return len(self.all_nodes())

    def texture_list(self) -> List[str]:
        seen = set()
        result = []
        for n in self.mesh_nodes():
            for t in [n.texture_clean, n.lightmap, n.bump_map]:
                if t and t.upper() not in ('NULL', '') and t not in seen:
                    seen.add(t); result.append(t)
        return result

    def _compute_all_tangents_legacy(self) -> None:
        """Legacy no-return version kept for back-compat. Use compute_all_tangents()."""
        for node in self.all_nodes():
            if (node.flags & NodeFlags.MESH or
                    node.flags & NodeFlags.SKIN or
                    node.flags & NodeFlags.DANGLY or
                    node.flags & NodeFlags.SABER):
                if node.vertices:
                    node.compute_tangents()

    @classmethod
    def load(cls, mdl_path: str, mdx_path: str = "") -> 'KotorModel':
        """
        Convenience classmethod to load a KotorModel from MDL/MDX file paths.

        This is the primary entry point for scripts and external tools that need
        to load a model without importing MDLBinaryParser directly.

        Args:
            mdl_path: Path to the .mdl file (binary or ASCII).
            mdx_path: Optional path to the .mdx binary mesh data file.
                      If omitted, auto-detected as <mdl_path>.mdx.

        Returns:
            Loaded KotorModel instance.

        Example::

            model = KotorModel.load('game_data/extracted/models/n_darthrevan.mdl')
            print(model.name, model.supermodel)
        """
        from .kotor_loader import load_model_from_file
        return load_model_from_file(mdl_path, mdx_path)


# ──────────────────────────────────────────────────────────────
#  CharacterScene — canonical in-memory scene per GhostRigger spec §5
# ──────────────────────────────────────────────────────────────

import uuid as _uuid
import hashlib as _hashlib


def _make_asset_id(resref: str, game_version: str = "K1") -> str:
    """Produce a stable string GUID from (resref, game_version).

    The ID is deterministic: the same resref+game always yields the same
    string, so assets can be referenced by ID across sessions without
    persisting a database.

    Format: ``gr:<upper-resref>:<game>`` for simple cases; a compact
    hex digest is appended when resref contains non-ASCII characters.
    """
    key = f"{resref.upper()}:{game_version.upper()}"
    try:
        return f"gr:{resref.upper()}:{game_version.upper()}"
    except Exception:
        h = _hashlib.sha1(key.encode("utf-8", "replace")).hexdigest()[:12]
        return f"gr:{h}"


@dataclass
class SceneSlot:
    """One occupied slot in a CharacterScene.

    Attributes
    ----------
    slot        : Which PartSlot this entry occupies.
    model       : Loaded KotorModel (may be None if still loading).
    resref      : Source resref (lowercase, no extension).
    asset_id    : Stable string ID derived from resref + game_version.
    game_version: 'K1' or 'K2'.
    source_path : Absolute file path (for user-imported OBJ/FBX/MDL files).
                  Empty string when loaded from BIF/ERF archives.
    dirty       : True when the slot has been modified since last export.
    """
    slot:         PartSlot
    model:        Optional[KotorModel]               = None
    resref:       str                                = ""
    asset_id:     str                                = ""
    game_version: str                                = "K1"
    source_path:  str                                = ""
    dirty:        bool                               = False

    def __post_init__(self) -> None:
        if not self.asset_id and self.resref:
            self.asset_id = _make_asset_id(self.resref, self.game_version)


@dataclass
class CharacterScene:
    """Canonical in-memory character description shared by all builder modes.

    This is the single source of truth that drives the importer, renderer,
    validator, and exporter (GhostRigger spec §5).  Instead of each subsystem
    maintaining its own parallel model references, every part of the UI reads
    and writes CharacterScene slots.

    Attributes
    ----------
    scene_id        : Unique session GUID (regenerated each time a new scene
                      is created; not persisted).
    game_version    : 'K1' or 'K2' — drives compatibility checks.
    character_name  : Optional label for the character (for UI display).
    slots           : Dict mapping PartSlot → SceneSlot.  Only occupied slots
                      appear; missing slots mean "empty / not assigned".
    supermodel      : Expected supermodel string (e.g. 'S_Female02').
    dirty           : True when any slot has been modified since last save.
    metadata        : Arbitrary key/value pairs for tools to store extra state
                      (e.g. export settings, last camera position, etc.).

    Usage
    -----
    ::

        scene = CharacterScene(game_version='K1')
        scene.assign(PartSlot.HEAD_SHELL, head_model, resref='pfhc01')
        scene.assign(PartSlot.HEADLESS_BODY, body_model, resref='pfbcm')
        issues = ValidationService(scene).validate()
    """

    scene_id:       str                          = field(
        default_factory=lambda: str(_uuid.uuid4()))
    game_version:   str                          = "K1"
    character_name: str                          = ""
    slots:          Dict[PartSlot, SceneSlot]    = field(default_factory=dict)
    supermodel:     str                          = ""
    dirty:          bool                         = False
    metadata:       Dict[str, Any]               = field(default_factory=dict)

    # ── Slot management ──────────────────────────────────────────────────────

    def assign(
        self,
        slot: PartSlot,
        model: Optional[KotorModel],
        *,
        resref: str = "",
        game_version: str = "",
        source_path: str = "",
    ) -> SceneSlot:
        """Assign a model to a slot (or clear it when model is None).

        Creates a new SceneSlot, marks the scene dirty, and returns the
        created slot descriptor.
        """
        gv = game_version or self.game_version
        entry = SceneSlot(
            slot=slot,
            model=model,
            resref=resref.lower(),
            game_version=gv,
            source_path=source_path,
            dirty=True,
        )
        self.slots[slot] = entry
        self.dirty = True
        return entry

    def clear_slot(self, slot: PartSlot) -> None:
        """Remove a slot assignment."""
        self.slots.pop(slot, None)
        self.dirty = True

    def get(self, slot: PartSlot) -> Optional[SceneSlot]:
        """Return the SceneSlot for the given slot, or None."""
        return self.slots.get(slot)

    def get_model(self, slot: PartSlot) -> Optional[KotorModel]:
        """Shorthand: return the KotorModel for the given slot, or None."""
        entry = self.slots.get(slot)
        return entry.model if entry else None

    # ── Helpers ──────────────────────────────────────────────────────────────

    @property
    def is_empty(self) -> bool:
        """True when no slots are assigned."""
        return not self.slots

    @property
    def all_models(self) -> List[KotorModel]:
        """Return all non-None KotorModel objects from all assigned slots."""
        result = []
        for entry in self.slots.values():
            if entry.model is not None:
                result.append(entry.model)
        return result

    @property
    def head_model(self) -> Optional[KotorModel]:
        return self.get_model(PartSlot.HEAD_SHELL)

    @property
    def body_model(self) -> Optional[KotorModel]:
        return self.get_model(PartSlot.HEADLESS_BODY)

    def mark_clean(self) -> None:
        """Reset dirty flag on scene and all slots (call after successful save/export)."""
        self.dirty = False
        for entry in self.slots.values():
            entry.dirty = False

    def asset_id_for(self, slot: PartSlot) -> Optional[str]:
        """Return the stable asset ID for the given slot, or None."""
        entry = self.slots.get(slot)
        return entry.asset_id if entry else None

    def summary(self) -> str:
        """One-line human-readable summary for logging / UI status bars."""
        parts = []
        for slot, entry in self.slots.items():
            label = PART_SLOT_LABELS.get(slot, slot.value)
            parts.append(f"{label}={entry.resref or '?'}")
        return (f"CharacterScene({self.game_version}) "
                + (", ".join(parts) if parts else "(empty)"))

    # ── JSON persistence (Phase 2) ────────────────────────────────────────────

    # File format version written into every .ghostrig.json.
    # Increment when the schema changes in a breaking way.
    SCENE_FORMAT_VERSION: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the scene to a plain JSON-compatible dictionary.

        The dict can be round-tripped with ``CharacterScene.from_dict()``.
        Loaded KotorModel objects are *not* serialised (they can be re-loaded
        from ``source_path`` / resref).  Only the slot *metadata* is saved.

        Schema
        ------
        ::

            {
              "ghostrig_version": 1,
              "scene_id": "<uuid>",
              "game_version": "K1",
              "character_name": "Revan",
              "supermodel": "S_Female02",
              "metadata": { ... },
              "slots": [
                {
                  "slot": "head_shell",
                  "resref": "pfhc01",
                  "asset_id": "gr:PFHC01:K1",
                  "game_version": "K1",
                  "source_path": "/abs/path/pfhc01.mdl"
                },
                ...
              ]
            }
        """
        import datetime as _dt
        slot_list = []
        for slot, entry in self.slots.items():
            slot_list.append({
                "slot":         slot.value,
                "resref":       entry.resref,
                "asset_id":     entry.asset_id,
                "game_version": entry.game_version,
                "source_path":  entry.source_path,
            })
        return {
            "ghostrig_version": self.SCENE_FORMAT_VERSION,
            "scene_id":         self.scene_id,
            "game_version":     self.game_version,
            "character_name":   self.character_name,
            "supermodel":       self.supermodel,
            "saved_at":         _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            "metadata":         dict(self.metadata),
            "slots":            slot_list,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        load_models: bool = False,
    ) -> "CharacterScene":
        """Reconstruct a CharacterScene from a dict produced by ``to_dict()``.

        Parameters
        ----------
        data        : Dict previously returned by ``to_dict()`` (or loaded from
                      a ``.ghostrig.json`` file).
        load_models : When True, attempt to load each slot's model from
                      ``source_path`` using the standard file loader.  Slots
                      whose source_path does not exist are kept with
                      ``model=None`` and a warning is logged.
                      When False (default), all slots are created with
                      ``model=None``; the caller is responsible for loading.

        Returns
        -------
        CharacterScene with slots populated (models optionally loaded).

        Raises
        ------
        ValueError  : If ``data`` is missing required keys or has an
                      unsupported ``ghostrig_version``.
        """
        ver = data.get("ghostrig_version", 0)
        if ver > cls.SCENE_FORMAT_VERSION:
            raise ValueError(
                f"CharacterScene.from_dict: file version {ver} is newer than "
                f"this build supports ({cls.SCENE_FORMAT_VERSION}). "
                "Please update GhostRigger."
            )

        scene = cls(
            game_version   = data.get("game_version", "K1"),
            character_name = data.get("character_name", ""),
            supermodel     = data.get("supermodel", ""),
            metadata       = dict(data.get("metadata", {})),
        )
        # Preserve the original scene_id so references stay stable
        saved_id = data.get("scene_id", "")
        if saved_id:
            scene.scene_id = saved_id

        for slot_data in data.get("slots", []):
            slot_value = slot_data.get("slot", "")
            try:
                slot = PartSlot(slot_value)
            except ValueError:
                log.warning("CharacterScene.from_dict: unknown slot '%s', skipping",
                            slot_value)
                continue

            resref       = slot_data.get("resref", "")
            asset_id     = slot_data.get("asset_id", "")
            game_version = slot_data.get("game_version", scene.game_version)
            source_path  = slot_data.get("source_path", "")

            model = None
            if load_models and source_path:
                try:
                    from .kotor_loader import load_model_from_file
                    if _uuid.uuid4 and __import__("os").path.isfile(source_path):
                        model = load_model_from_file(source_path)
                        log.info("CharacterScene.from_dict: loaded %s from %s",
                                 resref, source_path)
                    else:
                        log.warning(
                            "CharacterScene.from_dict: source_path not found "
                            "for slot %s: %s", slot_value, source_path)
                except Exception as exc:
                    log.warning("CharacterScene.from_dict: failed to load %s: %s",
                                source_path, exc)

            entry = SceneSlot(
                slot         = slot,
                model        = model,
                resref       = resref,
                asset_id     = asset_id or _make_asset_id(resref, game_version),
                game_version = game_version,
                source_path  = source_path,
                dirty        = False,
            )
            scene.slots[slot] = entry

        scene.dirty = False
        return scene

    def to_json(self, indent: int = 2) -> str:
        """Return a JSON string representation of the scene."""
        import json as _json
        return _json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str, *, load_models: bool = False) -> "CharacterScene":
        """Parse a JSON string (as produced by ``to_json()``)."""
        import json as _json
        return cls.from_dict(_json.loads(text), load_models=load_models)


# ──────────────────────────────────────────────────────────────
#  SceneIO — save / load .ghostrig.json files
# ──────────────────────────────────────────────────────────────

class SceneIO:
    """Utility class for reading and writing ``.ghostrig.json`` scene files.

    A ``.ghostrig.json`` file is a UTF-8 JSON document that captures all
    slot metadata of a CharacterScene.  It is designed to sit next to the
    exported model files (e.g. ``pfhc01.mdl`` + ``pfhc01.ghostrig.json``).

    Usage
    -----
    ::

        # Save
        SceneIO.save(scene, "/path/to/revan.ghostrig.json")

        # Load (metadata only — models not re-loaded automatically)
        scene = SceneIO.load("/path/to/revan.ghostrig.json")

        # Load and attempt to re-open model files from their source_path
        scene = SceneIO.load("/path/to/revan.ghostrig.json", load_models=True)

        # Write side-car next to an exported model
        SceneIO.write_sidecar(scene, "/path/to/export/pfhc01.mdl")
    """

    EXTENSION = ".ghostrig.json"

    @staticmethod
    def save(scene: "CharacterScene", path: str) -> None:
        """Write the scene to *path* as a ``.ghostrig.json`` file.

        The parent directory is created if it does not exist.

        Parameters
        ----------
        scene : CharacterScene to serialise.
        path  : Destination file path (should end with ``.ghostrig.json``
                but any extension is accepted).

        Raises
        ------
        OSError : If the file cannot be written.
        """
        import json as _json
        import os as _os
        _os.makedirs(_os.path.dirname(_os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            _json.dump(scene.to_dict(), fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        scene.mark_clean()
        log.info("SceneIO.save: wrote %s (%d slot(s))", path, len(scene.slots))

    @staticmethod
    def load(path: str, *, load_models: bool = False) -> "CharacterScene":
        """Load a scene from a ``.ghostrig.json`` file.

        Parameters
        ----------
        path        : Path to the ``.ghostrig.json`` file.
        load_models : When True, attempt to re-open each slot's model from
                      its recorded ``source_path``.

        Returns
        -------
        CharacterScene (possibly with model=None slots if load_models=False
        or if source files are unavailable).

        Raises
        ------
        FileNotFoundError : If *path* does not exist.
        ValueError        : If the file format version is unsupported.
        json.JSONDecodeError : If the file is not valid JSON.
        """
        import json as _json
        with open(path, "r", encoding="utf-8") as fh:
            data = _json.load(fh)
        scene = CharacterScene.from_dict(data, load_models=load_models)
        log.info("SceneIO.load: read %s (%d slot(s))", path, len(scene.slots))
        return scene

    @staticmethod
    def write_sidecar(scene: "CharacterScene", model_path: str) -> str:
        """Write a side-car ``.ghostrig.json`` next to *model_path*.

        The sidecar filename is derived by replacing the model file's
        extension with ``.ghostrig.json``.

        Parameters
        ----------
        scene      : CharacterScene to serialise.
        model_path : Path to the primary exported model file
                     (e.g. ``/out/pfhc01.mdl`` or ``/out/revan.fbx``).

        Returns
        -------
        Absolute path of the written sidecar file.
        """
        import os as _os
        base = _os.path.splitext(model_path)[0]
        sidecar_path = base + SceneIO.EXTENSION
        SceneIO.save(scene, sidecar_path)
        return _os.path.abspath(sidecar_path)

    @staticmethod
    def find_sidecar(model_path: str) -> Optional[str]:
        """Return the sidecar path for *model_path* if it exists, else None."""
        import os as _os
        base = _os.path.splitext(model_path)[0]
        candidate = base + SceneIO.EXTENSION
        return candidate if _os.path.isfile(candidate) else None
