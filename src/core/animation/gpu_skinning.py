"""
gpu_skinning.py — GhostRigger-K1-K2  Phase 5.0
================================================
Matrix-palette SSBO upload + TBN tangent-space computation.

This module provides two orthogonal features for the GPU renderer:

1.  **MatrixPaletteUploader**  (Gregory §12.5.2; Dunsky Ch.2)
    ─────────────────────────────────────────────────────────
    Converts an ``AnimPose`` (from ``AnimationEngine.evaluate()``) into a
    flat array of 4×4 bone matrices suitable for upload to the GPU.

    The bone matrix for bone *i* is:

        M_i = world_pose_i  ×  inverse_bind_pose_i

    so that a vertex *v* (stored in bind-pose local space) is transformed by:

        v_world = M_i × v_bind

    When ``moderngl`` is available the matrices are uploaded to a
    Shader Storage Buffer Object (SSBO) at binding point 0.  When ModernGL
    is absent (headless / CPU fallback) the matrices are returned as a flat
    ``numpy`` array that callers can use for software LBS.

    Reference:
        Gregory, *Game Engine Architecture* 3rd Ed. §12.5.2
        Dunsky, *Mastering C++ Game Animation Programming* Ch.2

2.  **TBNComputer**  (Lengyel §7.8)
    ──────────────────────────────
    Computes per-vertex tangent, bitangent and normal vectors from a mesh's
    position and UV data using the MikkTSpace-compatible formula:

        dP1 = P1 - P0,  dP2 = P2 - P0
        dUV1 = UV1 - UV0, dUV2 = UV2 - UV0

        T = (dUV2.y × dP1 - dUV1.y × dP2) / (dUV1.x×dUV2.y - dUV2.x×dUV1.y)
        B = (-dUV2.x × dP1 + dUV1.x × dP2) / (...)

    Per-vertex tangents are accumulated (area-weighted) and normalized.
    The handedness bit (T×B · N > 0 → +1, else -1) is stored in the W
    component of each tangent vec4 so that the fragment shader can
    reconstruct B = cross(N, T) × handedness.

    Reference:
        Lengyel, *Mathematics for 3D Game Programming* §7.8
        MikkTSpace algorithm (Morten S. Mikkelsen, 2010)
        PyKotor ``geometry_utils.py:compute_per_vertex_tangent_space()``

3.  **Shader source extensions**
    ─────────────────────────────
    ``VERT_SKIN_SRC`` and ``FRAG_TBN_SRC`` are GLSL string constants that
    extend the base GpuRenderer shaders with:
      • In the vertex shader:  bone-index / weight attributes; LBS transform;
        tangent / bitangent outputs.
      • In the fragment shader:  ``u_nmap_tex`` sampler; TBN unpacking;
        perturbed-normal Phong lighting.

    These constants are designed so that ``gpu_renderer.py`` can concatenate
    them with its existing shader source strings at compile time when the
    skinning or normal-map path is requested.
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# 3i Step 7 + 3j Step 4 — env-gated skinning formula switch.
#
# Default unset => G5_FULL_REF, the corrected qBone consumption path.
# Set ``GHOSTRIGGER_SKIN_FORMULA=F1_current_TR_inverse`` only when a
# legacy comparison render is needed. Setting
# ``GHOSTRIGGER_SKIN_FORMULA=F11_rotation_only_skin_bind_wrapper`` swaps
# ``compute_skin_node_palette`` to the diagnostic rotation-only outer
# wrapper variant identified in the 3i Step 7 audit:
#
#     M_i = inverse(R(skin_bind)) * world_pose_i * inverse(qBone/tBone) * R(skin_bind)
#
# ``G5_FULL_REF`` follows the 3j Step 3 corrected qBone consumption
# pipeline that matches reone's documented convention
# (``mdlmdxreader.cpp:280-288`` + ``modelnode.h:40``):
#
#   1. Resolve the influenced bone's GLOBAL DFS NODE INDEX in the model.
#   2. Read ``qbones[dfs_idx]`` / ``tbones[dfs_idx]`` (NOT the compact
#      ``bone_map`` slot index that production currently uses).
#   3. Decode the quaternion bytes as ``(qw, qx, qy, qz)`` (W-first,
#      matching KotOR.js, reone, and PyKotor's own ``_NodeHeader.read``).
#   4. Compose ``T(tBone) * R(qBone)`` and use it directly as the
#      inverse-bind matrix in ``world_pose_m * inv_bind`` --- do NOT
#      invert it before storage. The on-disk slot already encodes
#      ``inverse(bone_world) * skin_world`` per reone's documentation.
#
# G5 collapses the bind-pose self-test to <= 1e-6 on 50/50 audited probes
# across c_drexlf, c_brith, and c_bomabeast (3j-3 replay outcome). A
# direct K1 diagnostic also keeps n_bith/run skin meshes near their
# authored extents while the legacy F1 path expands them several meters.
#
# The F1 and F11 switches remain for audit/visual-gate work. See
# ``knowledge_base/audits/2026-05/skinning_parity.md`` 3i Step 7 and 3j Steps 3-5
# for the decision rule that gates promoting either formula to the default.
_SKIN_FORMULA_ENV = 'GHOSTRIGGER_SKIN_FORMULA'
_SKIN_FORMULA_F1 = 'F1_current_TR_inverse'
_SKIN_FORMULA_F11 = 'F11_rotation_only_skin_bind_wrapper'
_SKIN_FORMULA_G5 = 'G5_FULL_REF'
_SKIN_FORMULA_VALID = (_SKIN_FORMULA_F1, _SKIN_FORMULA_F11, _SKIN_FORMULA_G5)


@dataclass(frozen=True)
class SkinningSpeciesProfile:
    """Species-level defaults for choosing a skinning profile.

    Species is a guide, not a hard override: the resolver still validates the
    qBone/tBone layout on each skin node before selecting the final formula.
    """

    key: str
    label: str
    preferred_qbone_layout: str = "dfs"
    preferred_formula: str = _SKIN_FORMULA_G5


SKINNING_SPECIES_PROFILES: Dict[str, SkinningSpeciesProfile] = {
    "human": SkinningSpeciesProfile("human", "Human"),
    "bith": SkinningSpeciesProfile("bith", "Bith"),
    "droid": SkinningSpeciesProfile("droid", "Droid"),
    "utility_droid": SkinningSpeciesProfile("utility_droid", "Utility Droid"),
    "battle_droid": SkinningSpeciesProfile("battle_droid", "Battle Droid"),
    "yoda": SkinningSpeciesProfile("yoda", "Yoda"),
    "mandalorian": SkinningSpeciesProfile("mandalorian", "Mandalorian"),
    "gamorrean": SkinningSpeciesProfile("gamorrean", "Gamorrean"),
    "unknown": SkinningSpeciesProfile("unknown", "Unknown"),
}

def classify_skinning_species(model_name: str = "", supermodel: str = "",
                              node_names: Optional[List[str]] = None) -> str:
    """Classify a model into a species skinning profile.

    The rules intentionally use stable resref/supermodel conventions before
    broad humanoid fallbacks. Returning ``unknown`` is preferable to forcing a
    questionable species label onto an unusual model.
    """
    name = str(model_name or "").lower()
    super_name = str(supermodel or "").lower()
    haystack = " ".join([name, super_name] + [
        str(n or "").lower() for n in (node_names or [])
    ])

    if "bith" in haystack or "brith" in haystack:
        return "bith"
    if "yoda" in haystack:
        return "yoda"
    if "gammorean" in haystack or "gamorrean" in haystack or "gamorian" in haystack:
        return "gamorrean"
    if "mandalorian" in haystack or "mandalore" in haystack:
        return "mandalorian"

    utility_tokens = (
        "p_t3", "c_drdastro", "c_drdmkone", "c_drdmktwo", "c_drdmkfour",
        "c_drdprot", "c_drdprobe", "c_drdsentry", "plc_subdroid",
    )
    if any(token in haystack for token in utility_tokens):
        return "utility_droid"

    battle_tokens = (
        "c_drdwar", "c_drdassassin", "c_drdspyder", "c_tankdroid",
        "battledroid", "battle_droid", "plc_bdroid",
    )
    if any(token in haystack for token in battle_tokens):
        return "battle_droid"

    droid_tokens = ("p_hk", "hk47", "droid", "c_drd", "drd")
    if any(token in haystack for token in droid_tokens):
        return "droid"

    humanoid_supermodels = (
        "s_male", "s_female", "s_fml", "s_mal",
        "n_admrlsaulkar", "n_darthband", "n_darthrevan",
    )
    if (
        any(token in super_name for token in humanoid_supermodels)
        or name.startswith(("pf", "pm", "n_"))
        or name.startswith(("ad_", "cp_"))
    ):
        return "human"

    return "unknown"


def _explicit_skin_formula_override() -> str:
    raw = os.environ.get(_SKIN_FORMULA_ENV, '').strip()
    return raw if raw in _SKIN_FORMULA_VALID else ''


def _active_skin_formula() -> str:
    """Return the active skinning formula key, falling back to G5.

    Reads ``GHOSTRIGGER_SKIN_FORMULA`` on every call so that test
    scaffolding and capture scripts can flip the switch per-render
    without re-importing the module.  Unknown values silently fall back
    to the production G5 path so a typo never re-enables legacy skinning.
    """
    return _explicit_skin_formula_override() or _SKIN_FORMULA_G5

# ─────────────────────────────────────────────────────────────────────────────
#  Optional dependency stubs
# ─────────────────────────────────────────────────────────────────────────────

try:
    import numpy as np
    _NUMPY = True
except ImportError:
    _NUMPY = False
    log.warning("gpu_skinning: numpy not available – palette upload disabled")

try:
    import moderngl
    _MODERNGL = True
except ImportError:
    _MODERNGL = False


# ─────────────────────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────────────────────

#: Maximum bones in a KotOR model's skin palette (engine limit).
#: KotOR 1/2 supports up to 128 bone matrices in the palette.
MAX_BONES: int = 128

#: SSBO binding point for the bone-matrix palette.
BONE_PALETTE_BINDING: int = 0


# ─────────────────────────────────────────────────────────────────────────────
#  Quaternion helpers (pure-Python, no numpy dependency)
# ─────────────────────────────────────────────────────────────────────────────

def _quat_to_mat4(q: Tuple[float, float, float, float]) -> List[List[float]]:
    """Convert quaternion (x, y, z, w) to 4×4 column-major rotation matrix.

    Returns a flat list of 16 floats in column-major order (OpenGL convention).
    Row-major form is:
        | 1-2(y²+z²)   2(xy-wz)    2(xz+wy)  0 |
        | 2(xy+wz)    1-2(x²+z²)   2(yz-wx)  0 |
        | 2(xz-wy)    2(yz+wx)    1-2(x²+y²) 0 |
        | 0           0           0           1 |
    """
    x, y, z, w = q
    xx, yy, zz = 2*x*x, 2*y*y, 2*z*z
    xy, xz, yz = 2*x*y, 2*x*z, 2*y*z
    wx, wy, wz = 2*w*x, 2*w*y, 2*w*z
    # Row-major 4×4
    m = [
        [1-yy-zz, xy-wz,   xz+wy,   0.0],
        [xy+wz,   1-xx-zz, yz-wx,   0.0],
        [xz-wy,   yz+wx,   1-xx-yy, 0.0],
        [0.0,     0.0,     0.0,     1.0],
    ]
    return m


def _mat4_mul_py(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    """Multiply two 4×4 matrices (lists of rows)."""
    result = [[0.0]*4 for _ in range(4)]
    for i in range(4):
        for j in range(4):
            s = 0.0
            for k in range(4):
                s += a[i][k] * b[k][j]
            result[i][j] = s
    return result


def _mat4_identity_py() -> List[List[float]]:
    return [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]


def _mat4_translate_py(tx, ty, tz) -> List[List[float]]:
    return [[1,0,0,tx],[0,1,0,ty],[0,0,1,tz],[0,0,0,1]]


def _mat4_to_flat_col(m: List[List[float]]) -> List[float]:
    """Convert 4×4 row-major list to flat column-major (OpenGL) list."""
    out = []
    for col in range(4):
        for row in range(4):
            out.append(m[row][col])
    return out


def _mat4_rotation_only_py(m: List[List[float]]) -> List[List[float]]:
    """Return ``m`` with the translation column zeroed.

    Used by the 3i Step 7 F11 wrapper to construct the rotation-only
    outer transform that mirrors xoreos's ``ModelNode::computeInverseBindPose``
    behaviour (which builds an orientation-only chain).
    """
    return [
        [m[0][0], m[0][1], m[0][2], 0.0],
        [m[1][0], m[1][1], m[1][2], 0.0],
        [m[2][0], m[2][1], m[2][2], 0.0],
        [0.0,     0.0,     0.0,     1.0],
    ]


# ─────────────────────────────────────────────────────────────────────────────
#  BoneMatrix  – one palette entry
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BoneMatrix:
    """A single bone's skinning matrix M = world_pose × inv_bind_pose.

    Stored in column-major order as 16 floats for direct GL/SSBO upload.

    Attributes
    ----------
    flat_col : list[float]
        16-element list in column-major order (direct GPU upload format).
    bone_name : str
        Debug name for this palette entry.
    bone_index : int
        Index in the palette.
    """
    flat_col: List[float] = field(default_factory=lambda: _mat4_to_flat_col(
        _mat4_identity_py()))
    bone_name: str = ""
    bone_index: int = 0


# ─────────────────────────────────────────────────────────────────────────────
#  MatrixPaletteUploader
# ─────────────────────────────────────────────────────────────────────────────

class MatrixPaletteUploader:
    """Builds and uploads the bone-matrix palette for GPU skinning.

    Workflow
    --------
    1.  Build the bind-pose inverse matrices from the model's rest pose
        (call :meth:`build_inverse_bind_pose`).
    2.  Each frame, call :meth:`compute_palette` with the current
        ``AnimPose``.  This multiplies each bone's world pose by its cached
        inverse bind-pose, producing the final skinning matrix.
    3.  Upload the palette to the GPU with :meth:`upload_to_ssbo`
        (ModernGL required) or retrieve as a NumPy array with
        :meth:`as_numpy_array` for CPU-side LBS.

    SSBO layout (binding = ``BONE_PALETTE_BINDING = 0``)
    ─────────────────────────────────────────────────────
        layout(std430, binding = 0) readonly buffer BonePalette {
            mat4 u_bones[MAX_BONES];
        };

    References
    ──────────
    Gregory §12.5.2 — skinning matrix M = M_pose × M_inv_bind
    Dunsky Ch.2    — SSBO palette layout (std430, mat4 array)
    """

    def __init__(self, max_bones: int = MAX_BONES):
        self._max_bones   = max_bones
        self._inv_bind    : Dict[str, List[List[float]]] = {}   # bone_name → 4×4 row-major (WORLD-space inverse)
        self._palette     : List[BoneMatrix] = []
        self._bone_order  : List[str] = []   # ordered bone names for index lookup
        self._ssbo        : Optional['moderngl.Buffer'] = None
        self._dirty       : bool = True
        # FIX-SKIN-ANIM: Store node hierarchy for parent-chain walks during
        # animated palette computation.  Populated by build_inverse_bind_pose().
        self._node_lookup : Dict[str, object] = {}   # bone_name_lower → ModelNode
        self._node_parent : Dict[str, str] = {}      # bone_name_lower → parent_name_lower
        self._model_name: str = ""
        self._model_supermodel: str = ""
        self._model_node_count: int = 0
        self._skin_species: str = "unknown"
        self._skin_species_profile: SkinningSpeciesProfile = SKINNING_SPECIES_PROFILES["unknown"]
        # 3j Step 4 — DFS index lookup for the env-gated G5_FULL_REF path.
        # qBone/tBone arrays in the MDL are parallel to the global DFS node
        # order (length == total model node count), not the compact 16-entry
        # ``bone_map`` slot space. Populated by ``build_inverse_bind_pose``
        # so ``compute_skin_node_palette`` can index correctly under G5.
        self._name_to_dfs_index : Dict[str, int] = {}
        # FIX-SKIN-ANIM-D2: Per-animation inverse bind pose override.
        # When set, this replaces _inv_bind for palette computation.
        # Built from the animation's first-frame (t=0) pose to match the
        # vertex space (xoreos approach: boneTransform = absTransform * inv(absBaseTransform)).
        self._inv_bind_anim : Optional[Dict[str, List[List[float]]]] = None
        self._current_anim_bind_key : Optional[str] = None  # tracks which anim bind is cached
        self._skin_local_inv_bind_by_slot: Dict[int, List[List[float]]] = {}
        self._skin_local_direct_bind_by_slot: Dict[int, List[List[float]]] = {}
        self._skin_bind_matrix: Optional[List[List[float]]] = None
        self._skin_bind_inverse_matrix: Optional[List[List[float]]] = None
        self._skin_palette_formula: str = ""
        self._skin_inverse_bind_source: str = ""
        self._skin_profile_reason: str = ""

    # ── Build inverse bind-pose ───────────────────────────────────────────────

    def build_inverse_bind_pose(self, model) -> int:
        """Walk the model's node tree and compute per-bone inverse bind-pose matrices.

        FIX-SKIN-ANIM: Computes WORLD-SPACE (model-space) bind transforms by
        accumulating the parent chain for each bone, then inverts.  Previously
        used only LOCAL (parent-relative) transforms, which produced wrong
        skinning matrices for any bone deeper than depth 1 in the hierarchy.

        The world-space bind matrix for bone *i* is:
            world_bind_i = world_bind_parent × T(local_pos) × R(local_rot)

        And the inverse bind-pose stored is:
            inv_bind_i = inv(world_bind_i)

        Parameters
        ----------
        model : KotorModel
            A loaded KotOR model with ``all_nodes()`` support.

        Returns
        -------
        int
            Number of bone matrices built.
        """
        self._inv_bind.clear()
        self._bone_order.clear()
        self._node_lookup.clear()
        self._node_parent.clear()
        self._name_to_dfs_index.clear()
        self._model_name = ""
        self._model_supermodel = ""
        self._model_node_count = 0
        self._skin_species = "unknown"
        self._skin_species_profile = SKINNING_SPECIES_PROFILES["unknown"]

        if model is None:
            return 0

        nodes = list(model.all_nodes()) if hasattr(model, 'all_nodes') else []
        nodes = [n for n in nodes if not bool(getattr(n, "_gr_bas_attachment_layer", False))]
        self._model_name = str(getattr(model, 'name', '') or '').lower()
        self._model_supermodel = str(getattr(model, 'supermodel', '') or '').lower()
        # KMAX scene composites add wrapper nodes above imported MDLs.  When
        # present, use the copied MDL's original DFS span for qBone/tBone
        # layout detection so full source-indexed arrays are not mistaken for
        # compact bone_map arrays.
        source_dfs_indices = [
            int(idx)
            for idx in (getattr(n, "_gr_source_dfs_index", None) for n in nodes)
            if isinstance(idx, int) and idx >= 0
        ]
        self._model_node_count = (max(source_dfs_indices) + 1) if source_dfs_indices else len(nodes)
        self._skin_species = classify_skinning_species(
            self._model_name,
            self._model_supermodel,
            [str(getattr(n, 'name', '') or '') for n in nodes],
        )
        self._skin_species_profile = SKINNING_SPECIES_PROFILES.get(
            self._skin_species,
            SKINNING_SPECIES_PROFILES["unknown"],
        )

        # Build node lookup, parent map, and DFS-index lookup. The DFS index
        # is the position of the node in ``model.all_nodes()``, which matches
        # the index space used by the MDL's qBone/tBone arrays per
        # ``reone/src/libs/graphics/format/mdlmdxreader.cpp:280-288``.
        for dfs_idx, node in enumerate(nodes):
            name = getattr(node, 'name', '')
            if not name:
                continue
            name_lower = name.lower()
            self._node_lookup[name_lower] = node
            source_dfs_idx = getattr(node, "_gr_source_dfs_index", None)
            if isinstance(source_dfs_idx, int) and source_dfs_idx >= 0:
                self._name_to_dfs_index[name_lower] = source_dfs_idx
            else:
                self._name_to_dfs_index[name_lower] = dfs_idx
            parent = getattr(node, 'parent', None)
            if parent is not None:
                parent_name = getattr(parent, 'name', '')
                parent_lower = str(parent_name or '').lower()
                if parent_lower and parent_lower != name_lower:
                    self._node_parent[name_lower] = parent_lower
                elif parent_lower == name_lower:
                    log.warning(
                        "MatrixPaletteUploader: ignoring self-parent cycle on %s",
                        name,
                    )

        # Compute world-space bind matrices by walking parent chains.
        # Cache computed world bind matrices to avoid redundant chain walks.
        _world_bind_cache: Dict[str, List[List[float]]] = {}
        _world_bind_active: set[str] = set()

        def _get_world_bind(bone_name_lower: str) -> List[List[float]]:
            """Recursively compute the world-space bind matrix for a bone."""
            if bone_name_lower in _world_bind_cache:
                return _world_bind_cache[bone_name_lower]
            if bone_name_lower in _world_bind_active:
                log.warning(
                    "MatrixPaletteUploader: parent cycle detected at %s",
                    bone_name_lower,
                )
                m = _mat4_identity_py()
                _world_bind_cache[bone_name_lower] = m
                return m
            _world_bind_active.add(bone_name_lower)

            node = self._node_lookup.get(bone_name_lower)
            if node is None:
                m = _mat4_identity_py()
                _world_bind_cache[bone_name_lower] = m
                _world_bind_active.discard(bone_name_lower)
                return m

            # Local bind transform: T(pos) × R(quat)
            pos  = getattr(node, 'position', (0.0, 0.0, 0.0))
            quat = getattr(node, 'rotation', (0.0, 0.0, 0.0, 1.0))
            if pos is None:  pos = (0.0, 0.0, 0.0)
            if quat is None: quat = (0.0, 0.0, 0.0, 1.0)

            qx, qy, qz, qw = float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3])
            qlen = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
            if qlen > 1e-9:
                qx, qy, qz, qw = qx/qlen, qy/qlen, qz/qlen, qw/qlen
            else:
                qx, qy, qz, qw = 0.0, 0.0, 0.0, 1.0

            rot_m  = _quat_to_mat4((qx, qy, qz, qw))
            tx, ty, tz = float(pos[0]), float(pos[1]), float(pos[2])
            local_m = _mat4_mul_py(_mat4_translate_py(tx, ty, tz), rot_m)

            # world_bind = parent_world_bind × local_bind
            parent_name = self._node_parent.get(bone_name_lower)
            if parent_name is not None:
                parent_world = _get_world_bind(parent_name)
                world_m = _mat4_mul_py(parent_world, local_m)
            else:
                world_m = local_m

            _world_bind_cache[bone_name_lower] = world_m
            _world_bind_active.discard(bone_name_lower)
            return world_m

        count = 0
        for node in nodes:
            name = getattr(node, 'name', '')
            if not name:
                continue
            name_lower = name.lower()

            # Compute world-space bind matrix and invert
            world_bind_m = _get_world_bind(name_lower)
            try:
                inv_m = _mat4_invert_py(world_bind_m)
            except Exception:
                inv_m = _mat4_identity_py()

            self._inv_bind[name_lower] = inv_m
            if len(self._bone_order) < self._max_bones:
                self._bone_order.append(name_lower)
            count += 1

        self._dirty = True
        log.debug(f"MatrixPaletteUploader: built {count} world-space inverse bind-pose matrices")
        return count

    # ── Compute palette for current pose ─────────────────────────────────────

    def set_bind_pose_from_anim(self, anim_pose) -> int:
        """Rebuild inverse bind-pose matrices from an animation's first-frame pose.

        FIX-SKIN-ANIM-D2 (xoreos cross-ref: modelnode.cpp computeTransforms):
        ─────────────────────────────────────────────────────────────────────
        KotOR skin vertices are stored to match the animation's first-frame
        (t=0) pose, NOT the static node hierarchy rest pose.  This is because
        position keyframes are DELTA offsets added to the rest position, and
        t=0 keyframe deltas are often non-zero (e.g. Rootdummy shifts by
        ~1.17 units at t=0 of 'cwalk').

        The xoreos engine handles this by computing:
            _absoluteBaseTransform  = parent_base × local_base  (from anim first frame)
            _absoluteTransform      = parent_anim × local_anim  (from current frame)
            _boneTransform          = _absoluteTransform × inverse(_absoluteBaseTransform)

        When t = t0, boneTransform = identity, which is correct.

        This method builds the inverse of the first-frame world-space poses,
        which are then used as the bind reference in compute_palette().

        Parameters
        ----------
        anim_pose : AnimPose
            The animation's first-frame (t=0) pose from AnimationEngine.evaluate(0).

        Returns
        -------
        int
            Number of bind matrices updated.
        """
        if anim_pose is None:
            self._inv_bind_anim = None
            self._current_anim_bind_key = None
            return 0

        pose_nodes: Dict[str, object] = {}
        raw = getattr(anim_pose, 'nodes', {})
        pose_nodes = {k.lower(): v for k, v in raw.items()}

        _world_base_cache: Dict[str, List[List[float]]] = {}
        _world_base_active: set[str] = set()

        def _get_world_base(bone_name_lower: str) -> List[List[float]]:
            if bone_name_lower in _world_base_cache:
                return _world_base_cache[bone_name_lower]
            if bone_name_lower in _world_base_active:
                log.warning(
                    "MatrixPaletteUploader: base-pose parent cycle detected at %s",
                    bone_name_lower,
                )
                m = _mat4_identity_py()
                _world_base_cache[bone_name_lower] = m
                return m
            _world_base_active.add(bone_name_lower)

            pn = pose_nodes.get(bone_name_lower)
            if pn is not None:
                p = getattr(pn, 'position', (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
                q = getattr(pn, 'rotation', (0.0, 0.0, 0.0, 1.0)) or (0.0, 0.0, 0.0, 1.0)
            else:
                node = self._node_lookup.get(bone_name_lower)
                if node is not None:
                    p = getattr(node, 'position', (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
                    q = getattr(node, 'rotation', (0.0, 0.0, 0.0, 1.0)) or (0.0, 0.0, 0.0, 1.0)
                else:
                    m = _mat4_identity_py()
                    _world_base_cache[bone_name_lower] = m
                    _world_base_active.discard(bone_name_lower)
                    return m

            qx, qy, qz, qw = float(q[0]), float(q[1]), float(q[2]), float(q[3])
            ql = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
            if ql > 1e-9:
                qx, qy, qz, qw = qx/ql, qy/ql, qz/ql, qw/ql
            else:
                qx, qy, qz, qw = 0.0, 0.0, 0.0, 1.0

            rot_m = _quat_to_mat4((qx, qy, qz, qw))
            tx, ty, tz = float(p[0]), float(p[1]), float(p[2])
            local_m = _mat4_mul_py(_mat4_translate_py(tx, ty, tz), rot_m)

            parent_name = self._node_parent.get(bone_name_lower)
            if parent_name is not None:
                parent_world = _get_world_base(parent_name)
                world_m = _mat4_mul_py(parent_world, local_m)
            else:
                world_m = local_m

            _world_base_cache[bone_name_lower] = world_m
            _world_base_active.discard(bone_name_lower)
            return world_m

        inv_bind_anim: Dict[str, List[List[float]]] = {}
        count = 0
        for bname in self._bone_order:
            world_base = _get_world_base(bname)
            try:
                inv_m = _mat4_invert_py(world_base)
            except Exception:
                inv_m = _mat4_identity_py()
            inv_bind_anim[bname] = inv_m
            count += 1

        self._inv_bind_anim = inv_bind_anim
        log.debug(f"MatrixPaletteUploader: rebuilt {count} inverse bind matrices from anim first-frame (FIX-SKIN-ANIM-D2)")
        return count

    def _world_pose_matrix(self, bone_name_lower: str, pose_nodes: Dict[str, object],
                           cache: Dict[str, List[List[float]]],
                           _active: Optional[set[str]] = None) -> List[List[float]]:
        """Return world-space pose matrix for one bone, using pose overrides."""
        if bone_name_lower in cache:
            return cache[bone_name_lower]
        if _active is None:
            _active = set()
        if bone_name_lower in _active:
            log.warning(
                "MatrixPaletteUploader: pose parent cycle detected at %s",
                bone_name_lower,
            )
            m = _mat4_identity_py()
            cache[bone_name_lower] = m
            return m
        _active.add(bone_name_lower)

        pn = pose_nodes.get(bone_name_lower)
        if pn is not None:
            p = getattr(pn, 'position', (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
            q = getattr(pn, 'rotation', (0.0, 0.0, 0.0, 1.0)) or (0.0, 0.0, 0.0, 1.0)
        else:
            node = self._node_lookup.get(bone_name_lower)
            if node is not None:
                p = getattr(node, 'position', (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
                q = getattr(node, 'rotation', (0.0, 0.0, 0.0, 1.0)) or (0.0, 0.0, 0.0, 1.0)
            else:
                m = _mat4_identity_py()
                cache[bone_name_lower] = m
                _active.discard(bone_name_lower)
                return m

        qx, qy, qz, qw = float(q[0]), float(q[1]), float(q[2]), float(q[3])
        ql = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
        if ql > 1e-9:
            qx, qy, qz, qw = qx/ql, qy/ql, qz/ql, qw/ql
        else:
            qx, qy, qz, qw = 0.0, 0.0, 0.0, 1.0

        local_m = _mat4_mul_py(
            _mat4_translate_py(float(p[0]), float(p[1]), float(p[2])),
            _quat_to_mat4((qx, qy, qz, qw)),
        )
        parent_name = self._node_parent.get(bone_name_lower)
        if parent_name is not None:
            world_m = _mat4_mul_py(self._world_pose_matrix(parent_name, pose_nodes, cache, _active), local_m)
        else:
            world_m = local_m
        cache[bone_name_lower] = world_m
        _active.discard(bone_name_lower)
        return world_m

    @staticmethod
    def qbone_inverse_bind_matrix(qbone, tbone) -> List[List[float]]:
        """Build inverse-bind matrix from a skin node's qBone/tBone slot."""
        try:
            qx, qy, qz, qw = float(qbone[0]), float(qbone[1]), float(qbone[2]), float(qbone[3])
            tx, ty, tz = float(tbone[0]), float(tbone[1]), float(tbone[2])
        except Exception:
            return _mat4_identity_py()
        ql = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
        if ql > 1e-9:
            qx, qy, qz, qw = qx/ql, qy/ql, qz/ql, qw/ql
        else:
            qx, qy, qz, qw = 0.0, 0.0, 0.0, 1.0
        bind_m = _mat4_mul_py(_mat4_translate_py(tx, ty, tz), _quat_to_mat4((qx, qy, qz, qw)))
        try:
            return _mat4_invert_py(bind_m)
        except Exception:
            return _mat4_identity_py()

    @staticmethod
    def qbone_direct_bind_matrix(qbone, tbone) -> List[List[float]]:
        """Build the authored qBone/tBone matrix in TR order.

        xoreos's CPU path wraps the skin node bind around a per-bone inverse
        bind matrix (animation.cpp updateSkinnedModel + model_kotor.cpp skin
        reader). KotOR.js stores the qBone/tBone-derived matrix directly as
        the skin bone inverse matrix. GhostRigger keeps this helper available
        for 3g/3i diagnostics while production remains on the 3f inverse path.
        """
        try:
            qx, qy, qz, qw = float(qbone[0]), float(qbone[1]), float(qbone[2]), float(qbone[3])
            tx, ty, tz = float(tbone[0]), float(tbone[1]), float(tbone[2])
        except Exception:
            return _mat4_identity_py()
        ql = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
        if ql > 1e-9:
            qx, qy, qz, qw = qx/ql, qy/ql, qz/ql, qw/ql
        else:
            qx, qy, qz, qw = 0.0, 0.0, 0.0, 1.0
        return _mat4_mul_py(_mat4_translate_py(tx, ty, tz), _quat_to_mat4((qx, qy, qz, qw)))

    @staticmethod
    def qbone_inverse_bind_matrix_g5(qbone, tbone) -> List[List[float]]:
        """3j Step 4 - G5_FULL_REF qBone consumption (W-first, no invert).

        Build the per-bone inverse-bind matrix under reone's documented
        convention (``reone/src/libs/graphics/format/mdlmdxreader.cpp:286``
        + ``reone/include/reone/graphics/modelnode.h:40``):

            glm::mat4 boneMatrix(1.0f);
            boneMatrix *= glm::translate(glm::make_vec3(&tBoneValues[3 * i]));
            boneMatrix *= glm::mat4_cast(glm::quat(qBone[0], qBone[1], qBone[2], qBone[3]));
            // doc: each matrix is "inverse of bone transform in this node space"

        GLM's ``glm::quat`` constructor signature is ``quat(w, x, y, z)``,
        so ``qBone[0]`` from disk is the W component. The composed result
        is treated as the inverse-bind matrix directly --- it is NOT
        inverted.

        PyKotor stores the four disk floats verbatim into
        ``Vector4(x=f0, y=f1, z=f2, w=f3)`` (X-first), so the on-disk W
        byte ends up in ``qbone[0]`` and we remap to feed the existing
        ``_quat_to_mat4(qx, qy, qz, qw)`` helper:

            (qx, qy, qz, qw) <- (qbone[1], qbone[2], qbone[3], qbone[0])

        The caller is responsible for indexing ``qbones``/``tbones`` by
        the bone's GLOBAL DFS NODE INDEX in the model, not by the compact
        ``bone_map`` slot index. ``MatrixPaletteUploader._name_to_dfs_index``
        provides that lookup.

        Empirical 3j-3 result on c_drexlf, c_brith, c_bomabeast: with the
        DFS-indexed lookup plus this builder, ``bone_world * inv_bind``
        equals ``skin_world`` to <= 1e-6 on every probed bone --- the
        textbook bind-pose collapse for an LBS chain over NODE_LOCAL
        vertices. See ``knowledge_base/audits/2026-05/skinning_parity.md`` 3j Step 3.
        """
        try:
            qw_disk = float(qbone[0])
            qx = float(qbone[1])
            qy = float(qbone[2])
            qz = float(qbone[3])
            tx = float(tbone[0])
            ty = float(tbone[1])
            tz = float(tbone[2])
        except Exception:
            return _mat4_identity_py()
        ql = math.sqrt(qx * qx + qy * qy + qz * qz + qw_disk * qw_disk)
        if ql > 1e-9:
            qx /= ql
            qy /= ql
            qz /= ql
            qw_disk /= ql
        else:
            qx, qy, qz, qw_disk = 0.0, 0.0, 0.0, 1.0
        return _mat4_mul_py(
            _mat4_translate_py(tx, ty, tz),
            _quat_to_mat4((qx, qy, qz, qw_disk)),
        )

    def _resolve_skin_formula_for_skin_node(self, skin_node) -> str:
        """Choose the skinning profile from species plus qBone layout.

        Species provides the default convention family (Human, Bith, Droid,
        Utility Droid, Battle Droid, Yoda, Mandalorian, Gamorrean, etc.).
        The actual qBone/tBone shape still validates the decision per node:
        full DFS arrays use G5, compact arrays use F1, and explicit env
        overrides remain available for visual-gate comparisons.
        """
        override = _explicit_skin_formula_override()
        if override:
            self._skin_profile_reason = (
                f"env:{override} species={self._skin_species}"
            )
            return override

        bone_map = list(getattr(skin_node, 'bone_map', []) or [])
        q_count = len(getattr(skin_node, 'qbone_list', []) or [])
        t_count = len(getattr(skin_node, 'tbone_list', []) or [])
        qt_count = min(q_count, t_count)
        node_count = int(self._model_node_count or len(self._node_lookup) or 0)
        species = self._skin_species or "unknown"
        profile = self._skin_species_profile or SKINNING_SPECIES_PROFILES["unknown"]
        preferred_layout = str(getattr(profile, 'preferred_qbone_layout', 'dfs') or 'dfs')
        preferred_formula = str(getattr(profile, 'preferred_formula', _SKIN_FORMULA_G5) or _SKIN_FORMULA_G5)

        if preferred_layout == "compact" and bone_map and qt_count >= len(bone_map):
            self._skin_profile_reason = (
                f"species:{species} auto:compact_qbone model={self._model_name or '?'} "
                f"qt={qt_count} bone_map={len(bone_map)}"
            )
            return _SKIN_FORMULA_F1

        if node_count > 0 and qt_count >= node_count:
            self._skin_profile_reason = (
                f"species:{species} auto:dfs_qbone model={self._model_name or '?'} "
                f"qt={qt_count} nodes={node_count}"
            )
            return preferred_formula if preferred_formula in _SKIN_FORMULA_VALID else _SKIN_FORMULA_G5

        if bone_map and qt_count >= len(bone_map):
            self._skin_profile_reason = (
                f"species:{species} auto:compact_qbone model={self._model_name or '?'} "
                f"qt={qt_count} bone_map={len(bone_map)}"
            )
            return _SKIN_FORMULA_F1

        self._skin_profile_reason = (
            f"species:{species} auto:fallback_g5 model={self._model_name or '?'} "
            f"qt={qt_count} nodes={node_count} bone_map={len(bone_map)}"
        )
        return _SKIN_FORMULA_G5

    def compute_skin_node_palette(self, skin_node, anim_pose, anim_base_pose=None) -> List[BoneMatrix]:
        """Compute a local skin-node palette using qBone/tBone inverse binds.

        3g wrapper attempts were visually rejected. Keep the production path at
        the 3f baseline while 3i audits the raw vertex space and pose chain:

            animated_world * inverse(T(qBone/tBone) * R(qBone/tBone))      (F1)

        3i Step 7 — env-gated F11 diagnostic
        ------------------------------------
        When ``GHOSTRIGGER_SKIN_FORMULA=F11_rotation_only_skin_bind_wrapper``
        the per-bone matrix becomes::

            inverse(R(skin_bind)) * world_pose_m * inverse(qBone/tBone) * R(skin_bind)

        where ``R(skin_bind)`` is the rotation-only skin-node bind matrix
        (translation column zeroed). This mirrors xoreos's outer-wrapper
        transform inferred in 3i Step 6 and is used solely for the
        ``c_bomabeast`` visual gate. Step 7 reduction proved this collapses
        to F1 on the audited probes for ``c_drexlf``/``c_brith`` (identity
        bind rotation), so they serve as a no-op control while
        ``c_bomabeast`` is the falsification target.

        3j Step 4 — env-gated G5_FULL_REF reference path
        ------------------------------------------------
        When ``GHOSTRIGGER_SKIN_FORMULA=G5_FULL_REF`` the per-bone matrix
        keeps the textbook LBS shape ``world_pose_m * inv_bind`` but
        ``inv_bind`` is rebuilt under reone's documented convention with
        all three 3j-3 fixes applied jointly:

          1. ``inv_bind`` is read at ``qbones[dfs_idx]`` /
             ``tbones[dfs_idx]`` where ``dfs_idx`` is the influenced
             bone's GLOBAL DFS NODE INDEX in the model (NOT the compact
             ``bone_map`` slot index).
          2. The quaternion bytes are decoded W-first
             (``qbones[dfs_idx][0]`` is the W component).
          3. The composed ``T * R`` is used as the inverse-bind matrix
             directly --- it is NOT inverted before storage.

        On the 3j-3 audited probes (``c_drexlf``, ``c_brith``,
        ``c_bomabeast``) this collapses ``bone_world * inv_bind`` to
        ``skin_world`` within ~1e-6, satisfying the bind-pose self-test
        on 50/50 probes while F1 and the partial G3 fix both fail
        100%. G5 stays env-gated until 3j-5 (the joint visual gate plus
        the 50-model render-diff suite) clears it for production.
        """
        # Imported/custom payload skins that are bound to a native KOTOR DAG can
        # have normal skin weights but no qBone/tBone arrays. In that case the
        # animation's first frame is the only reliable bind reference for live
        # preview skinning, matching compute_palette(..., anim_base_pose=...).
        if anim_base_pose is not None:
            self.set_bind_pose_from_anim(anim_base_pose)
        self._palette = []
        self._skin_local_inv_bind_by_slot = {}
        self._skin_local_direct_bind_by_slot = {}
        self._skin_bind_matrix = None
        self._skin_bind_inverse_matrix = None
        force_anim_base_bind = (
            anim_base_pose is not None
            and bool(getattr(
                skin_node,
                "_gr_use_animation_base_bind_for_preview",
                False,
            ))
        )
        active_formula = self._resolve_skin_formula_for_skin_node(skin_node)
        if force_anim_base_bind:
            active_formula = _SKIN_FORMULA_F1
            self._skin_profile_reason = (
                "character_builder:animation_base_bind_preview "
                f"model={self._model_name or '?'}"
            )
        self._skin_palette_formula = active_formula
        self._skin_inverse_bind_source = "qBone_tBone_inverse_TR"
        pose_nodes = {k.lower(): v for k, v in getattr(anim_pose, 'nodes', {}).items()} if anim_pose is not None else {}
        active_inv_bind = self._inv_bind_anim if self._inv_bind_anim is not None else self._inv_bind
        world_cache: Dict[str, List[List[float]]] = {}
        skin_key = str(getattr(skin_node, 'name', '') or '').lower()
        if skin_key:
            skin_bind = self._world_pose_matrix(skin_key, {}, {})
        else:
            pos = getattr(skin_node, 'position', (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
            quat = getattr(skin_node, 'rotation', (0.0, 0.0, 0.0, 1.0)) or (0.0, 0.0, 0.0, 1.0)
            skin_bind = _mat4_mul_py(
                _mat4_translate_py(float(pos[0]), float(pos[1]), float(pos[2])),
                _quat_to_mat4(tuple(float(v) for v in quat[:4])),
            )
        try:
            inv_skin_bind = _mat4_invert_py(skin_bind)
        except Exception:
            inv_skin_bind = _mat4_identity_py()
        self._skin_bind_matrix = skin_bind
        self._skin_bind_inverse_matrix = inv_skin_bind
        skin_bind_rot_only: Optional[List[List[float]]] = None
        inv_skin_bind_rot_only: Optional[List[List[float]]] = None
        if active_formula == _SKIN_FORMULA_F11:
            skin_bind_rot_only = _mat4_rotation_only_py(skin_bind)
            try:
                inv_skin_bind_rot_only = _mat4_invert_py(skin_bind_rot_only)
            except Exception:
                inv_skin_bind_rot_only = _mat4_identity_py()
        bone_map = list(getattr(skin_node, 'bone_map', []) or [])
        qbones = list(getattr(skin_node, 'qbone_list', []) or [])
        tbones = list(getattr(skin_node, 'tbone_list', []) or [])
        formula_env_raw = os.environ.get(_SKIN_FORMULA_ENV, '').strip()
        if force_anim_base_bind:
            self._skin_inverse_bind_source = "animation_base_pose_imported_payload"
        elif active_formula == _SKIN_FORMULA_G5 and not formula_env_raw and (not qbones or not tbones):
            # Imported FBX skin meshes, such as the Unreal Animator Quinn target,
            # have normal bone maps and skin weights but no KotOR qBone/tBone
            # arrays. G5 would otherwise use identity inverse-bind matrices and
            # stretch the mesh by applying raw world poses to bind-space vertices.
            active_formula = _SKIN_FORMULA_F1
            self._skin_palette_formula = f"{_SKIN_FORMULA_F1}:hierarchy_bind_no_qbone"
            self._skin_inverse_bind_source = "hierarchy_inverse_bind_no_qbone"

        # 3j Step 4 — under G5_FULL_REF, qBone/tBone are indexed by the
        # bone's GLOBAL DFS NODE INDEX in the model (parallel to the
        # length-N MDL skinmesh bonemap), not by the compact bone_map slot
        # index that production currently uses. Document the active source
        # so audit captures and tests can verify which path produced the
        # palette without re-reading env state.
        if active_formula == _SKIN_FORMULA_G5:
            self._skin_inverse_bind_source = "qBone_tBone_dfs_indexed_TR_no_invert"
        for idx, bname in enumerate(bone_map[:self._max_bones]):
            bkey = str(bname or '').lower()
            world_pose_m = (
                self._world_pose_matrix(bkey, pose_nodes, world_cache)
                if bkey else _mat4_identity_py()
            )
            if active_formula == _SKIN_FORMULA_G5:
                # Resolve the bone's DFS index; fall back to identity if
                # the bone is missing from the lookup so a malformed
                # bone_map entry never crashes the renderer.
                dfs_idx = self._name_to_dfs_index.get(bkey, -1) if bkey else -1
                if 0 <= dfs_idx < len(qbones) and dfs_idx < len(tbones):
                    inv_bind = self.qbone_inverse_bind_matrix_g5(
                        qbones[dfs_idx], tbones[dfs_idx],
                    )
                    direct_bind = self.qbone_direct_bind_matrix(
                        qbones[dfs_idx], tbones[dfs_idx],
                    )
                else:
                    inv_bind = _mat4_identity_py()
                    direct_bind = _mat4_identity_py()
            else:
                if force_anim_base_bind:
                    inv_bind = active_inv_bind.get(bkey, _mat4_identity_py())
                else:
                    inv_bind = (
                        self.qbone_inverse_bind_matrix(qbones[idx], tbones[idx])
                        if idx < len(qbones) and idx < len(tbones)
                        else active_inv_bind.get(bkey, _mat4_identity_py())
                    )
                direct_bind = (
                    self.qbone_direct_bind_matrix(qbones[idx], tbones[idx])
                    if (
                        not force_anim_base_bind
                        and idx < len(qbones)
                        and idx < len(tbones)
                    )
                    else _mat4_invert_py(inv_bind)
                )
            self._skin_local_inv_bind_by_slot[idx] = inv_bind
            self._skin_local_direct_bind_by_slot[idx] = direct_bind
            if active_formula == _SKIN_FORMULA_F11 and skin_bind_rot_only is not None and inv_skin_bind_rot_only is not None:
                skin_m = _mat4_mul_py(
                    inv_skin_bind_rot_only,
                    _mat4_mul_py(
                        world_pose_m,
                        _mat4_mul_py(inv_bind, skin_bind_rot_only),
                    ),
                )
            else:
                # F1 (production) and G5 both use the textbook LBS shape
                # ``world_pose_m * inv_bind``. The semantic difference is
                # entirely in how ``inv_bind`` is constructed above.
                skin_m = _mat4_mul_py(world_pose_m, inv_bind)
            self._palette.append(BoneMatrix(
                flat_col=_mat4_to_flat_col(skin_m),
                bone_name=str(bname or ''),
                bone_index=idx,
            ))
        self._dirty = True
        return self._palette

    def compute_palette(self, anim_pose, anim_base_pose=None) -> List[BoneMatrix]:
        """Compute the full bone-matrix palette from an ``AnimPose``.

        For each bone in ``_bone_order``:
            M_skin = M_world_pose × M_inv_bind_ref

        FIX-SKIN-ANIM-D2 (xoreos cross-ref: modelnode.cpp computeTransforms):
        The inverse bind reference is now taken from the animation's first-frame
        pose (set via set_bind_pose_from_anim()) rather than the static node
        hierarchy.  This matches the xoreos formula:
            boneTransform = absoluteTransform × inverse(absoluteBaseTransform)
        where absoluteBaseTransform is built from the animation's initial frame.

        At t=0 of an animation, this produces identity matrices (correct).
        At other times, it produces the delta from the first frame.

        Falls back to the static hierarchy inverse bind if no animation bind
        has been set.

        Parameters
        ----------
        anim_pose : AnimPose | None
            The pose evaluated by ``AnimationEngine.evaluate()``.  If None,
            all matrices are identity (bind pose).
        anim_base_pose : AnimPose | None
            The animation's first-frame (t=0) pose.  If provided, the inverse
            bind is rebuilt from this pose on the fly.  This is the simplest
            integration path for callers that track animation state.

        Returns
        -------
        list[BoneMatrix]
            Palette in the same order as ``_bone_order``.
        """
        # FIX-SKIN-ANIM-D2: If caller provides a base pose, rebuild bind from it.
        if anim_base_pose is not None:
            self.set_bind_pose_from_anim(anim_base_pose)
        self._palette = []

        # FIX-SKIN-BINDPOSE: When anim_pose is None (no animation), the
        # palette must be all-identity.  KotOR skin vertices are stored in
        # world/bind-pose space; the correct bind-pose formula is:
        #   M_skin = bind_pose × inv_bind = I  (identity)
        if anim_pose is None:
            identity_flat = _mat4_to_flat_col(_mat4_identity_py())
            for idx, bname in enumerate(self._bone_order):
                bm = BoneMatrix(
                    flat_col   = list(identity_flat),
                    bone_name  = bname,
                    bone_index = idx,
                )
                self._palette.append(bm)
            self._dirty = True
            return self._palette

        pose_nodes: Dict[str, object] = {}
        raw = getattr(anim_pose, 'nodes', {})
        pose_nodes = {k.lower(): v for k, v in raw.items()}

        # FIX-SKIN-ANIM-D2: Use animation-derived bind if available,
        # otherwise fall back to static hierarchy bind.
        active_inv_bind = self._inv_bind_anim if self._inv_bind_anim is not None else self._inv_bind

        # Build world-space animated pose matrices by walking the parent chain.
        _world_anim_cache: Dict[str, List[List[float]]] = {}
        _world_anim_active: set[str] = set()

        def _get_world_anim(bone_name_lower: str) -> List[List[float]]:
            """Recursively compute the world-space animated transform for a bone."""
            if bone_name_lower in _world_anim_cache:
                return _world_anim_cache[bone_name_lower]
            if bone_name_lower in _world_anim_active:
                log.warning(
                    "MatrixPaletteUploader: animated parent cycle detected at %s",
                    bone_name_lower,
                )
                m = _mat4_identity_py()
                _world_anim_cache[bone_name_lower] = m
                return m
            _world_anim_active.add(bone_name_lower)

            # Get animated or bind-pose local transform
            pn = pose_nodes.get(bone_name_lower)
            if pn is not None:
                p = getattr(pn, 'position', (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
                q = getattr(pn, 'rotation', (0.0, 0.0, 0.0, 1.0)) or (0.0, 0.0, 0.0, 1.0)
            else:
                node = self._node_lookup.get(bone_name_lower)
                if node is not None:
                    p = getattr(node, 'position', (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
                    q = getattr(node, 'rotation', (0.0, 0.0, 0.0, 1.0)) or (0.0, 0.0, 0.0, 1.0)
                else:
                    m = _mat4_identity_py()
                    _world_anim_cache[bone_name_lower] = m
                    _world_anim_active.discard(bone_name_lower)
                    return m

            qx, qy, qz, qw = float(q[0]), float(q[1]), float(q[2]), float(q[3])
            ql = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
            if ql > 1e-9:
                qx, qy, qz, qw = qx/ql, qy/ql, qz/ql, qw/ql
            else:
                qx, qy, qz, qw = 0.0, 0.0, 0.0, 1.0

            rot_m = _quat_to_mat4((qx, qy, qz, qw))
            tx, ty, tz = float(p[0]), float(p[1]), float(p[2])
            local_m = _mat4_mul_py(_mat4_translate_py(tx, ty, tz), rot_m)

            # world_anim = parent_world_anim × local_anim
            parent_name = self._node_parent.get(bone_name_lower)
            if parent_name is not None:
                parent_world = _get_world_anim(parent_name)
                world_m = _mat4_mul_py(parent_world, local_m)
            else:
                world_m = local_m

            _world_anim_cache[bone_name_lower] = world_m
            _world_anim_active.discard(bone_name_lower)
            return world_m

        for idx, bname in enumerate(self._bone_order):
            inv_bind = active_inv_bind.get(bname, _mat4_identity_py())

            # World-space animated pose for this bone
            world_pose_m = _get_world_anim(bname)

            skin_m = _mat4_mul_py(world_pose_m, inv_bind)
            bm = BoneMatrix(
                flat_col   = _mat4_to_flat_col(skin_m),
                bone_name  = bname,
                bone_index = idx,
            )
            self._palette.append(bm)

        self._dirty = True
        return self._palette

    # ── NumPy fast-path ───────────────────────────────────────────────────────

    def as_numpy_array(self) -> Optional['np.ndarray']:
        """Return the palette as a float32 NumPy array of shape (N, 4, 4).

        Returns None if numpy is not available or palette is empty.
        Each matrix is in row-major order (consistent with numpy convention).
        """
        if not _NUMPY or not self._palette:
            return None
        n = len(self._palette)
        arr = np.zeros((n, 4, 4), dtype=np.float32)
        for i, bm in enumerate(self._palette):
            col = bm.flat_col
            # flat_col is column-major; convert back to row-major for numpy
            for r in range(4):
                for c in range(4):
                    arr[i, r, c] = col[c*4 + r]
        return arr

    def as_flat_bytes(self) -> bytes:
        """Return the palette as raw bytes for SSBO upload.

        Layout: N × 16 × float32 (column-major per matrix, std430).
        Pads to ``max_bones`` with identity matrices.
        """
        flat: List[float] = []
        for bm in self._palette:
            flat.extend(bm.flat_col)
        # Pad to max_bones with identity
        identity_flat = _mat4_to_flat_col(_mat4_identity_py())
        while len(flat) < self._max_bones * 16:
            flat.extend(identity_flat)
        flat = flat[:self._max_bones * 16]
        if _NUMPY:
            return np.array(flat, dtype=np.float32).tobytes()
        import struct
        return struct.pack(f'{len(flat)}f', *flat)

    # ── SSBO upload ───────────────────────────────────────────────────────────

    def upload_to_ssbo(self, ctx: 'moderngl.Context') -> Optional['moderngl.Buffer']:
        """Upload the current palette to a ModernGL SSBO.

        Creates the buffer on first call; resizes / re-uploads on change.

        Parameters
        ----------
        ctx : moderngl.Context

        Returns
        -------
        moderngl.Buffer | None
            The SSBO, or None if upload failed.
        """
        if not _MODERNGL or not _NUMPY:
            return None
        try:
            data = self.as_flat_bytes()
            if self._ssbo is None:
                self._ssbo = ctx.buffer(data, dynamic=True)
            else:
                self._ssbo.write(data)
            self._dirty = False
            return self._ssbo
        except Exception as e:
            log.warning(f"MatrixPaletteUploader: SSBO upload failed: {e}")
            return None

    def release(self):
        """Release the GPU SSBO buffer."""
        if self._ssbo is not None:
            try:
                self._ssbo.release()
            except Exception:
                pass
            self._ssbo = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def bone_count(self) -> int:
        return len(self._bone_order)

    @property
    def palette(self) -> List[BoneMatrix]:
        return list(self._palette)

    def bone_index(self, name: str) -> int:
        """Return the palette index for a bone name, or -1 if not found."""
        key = name.lower()
        try:
            return self._bone_order.index(key)
        except ValueError:
            return -1


# ─────────────────────────────────────────────────────────────────────────────
#  Pure-Python 4×4 matrix inversion (Gauss-Jordan)
# ─────────────────────────────────────────────────────────────────────────────

def _mat4_invert_py(m: List[List[float]]) -> List[List[float]]:
    """Invert a 4×4 matrix using Gauss-Jordan elimination.

    Raises ValueError if the matrix is singular.
    """
    # Augmented matrix [m | I]
    n = 4
    aug = [m[i][:] + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]

    for col in range(n):
        # Partial pivot
        max_row = col
        for row in range(col + 1, n):
            if abs(aug[row][col]) > abs(aug[max_row][col]):
                max_row = row
        aug[col], aug[max_row] = aug[max_row], aug[col]

        pivot = aug[col][col]
        if abs(pivot) < 1e-12:
            raise ValueError("Singular matrix")
        for j in range(2 * n):
            aug[col][j] /= pivot
        for row in range(n):
            if row != col:
                factor = aug[row][col]
                for j in range(2 * n):
                    aug[row][j] -= factor * aug[col][j]

    return [aug[i][n:] for i in range(n)]


# ─────────────────────────────────────────────────────────────────────────────
#  TBNComputer
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TBNResult:
    """Per-vertex TBN vectors for one ModelNode.

    All arrays have the same length (number of vertices).

    Attributes
    ----------
    tangents    : list[(tx, ty, tz, w)]  — w = handedness (+1 or -1)
    bitangents  : list[(bx, by, bz)]     — world-space bitangent
    normals     : list[(nx, ny, nz)]     — smoothed per-vertex normal
    """
    tangents   : List[Tuple[float, float, float, float]] = field(default_factory=list)
    bitangents : List[Tuple[float, float, float]]        = field(default_factory=list)
    normals    : List[Tuple[float, float, float]]        = field(default_factory=list)

    @property
    def vertex_count(self) -> int:
        return len(self.tangents)


class TBNComputer:
    """Compute per-vertex TBN (Tangent, Bitangent, Normal) vectors.

    Algorithm
    ---------
    For each triangle (P0, P1, P2) with UV (UV0, UV1, UV2):
        dP1 = P1 - P0;   dP2 = P2 - P0
        dT1 = UV1 - UV0; dT2 = UV2 - UV0
        det = dT1.x × dT2.y − dT2.x × dT1.y
        T_face = (dT2.y × dP1 − dT1.y × dP2) / det
        B_face = (dT1.x × dP2 − dT2.x × dP1) / det

    Accumulated face tangents / bitangents are weight-averaged per vertex
    (triangle area weighting via cross-product magnitude).  The final
    tangent is orthogonalized against the smoothed normal (Gram–Schmidt),
    and the handedness w = sign(dot(cross(N, T), B)) is stored in T.w.

    Reference: Lengyel §7.8; MikkTSpace (Mikkelsen 2010)
    """

    def compute(self, node) -> TBNResult:
        """Compute TBN vectors for a ModelNode.

        Parameters
        ----------
        node
            A ModelNode-like object with ``vertices``, ``normals``,
            ``uvs``, and ``faces`` attributes.

        Returns
        -------
        TBNResult
            Per-vertex TBN data. Returns an empty result on failure.
        """
        verts   = list(getattr(node, 'vertices', getattr(node, 'verts', [])))
        norms   = list(getattr(node, 'normals', []))
        uvs     = list(getattr(node, 'uvs', []))
        faces   = list(getattr(node, 'faces', []))

        n_verts = len(verts)
        n_faces = len(faces)

        if n_verts == 0 or n_faces == 0 or len(uvs) == 0:
            return TBNResult()

        # Ensure normals and UVs have the right size
        while len(norms) < n_verts:
            norms.append((0.0, 0.0, 1.0))
        while len(uvs) < n_verts:
            uvs.append((0.0, 0.0))

        # Accumulation buffers
        tan_acc  = [[0.0, 0.0, 0.0] for _ in range(n_verts)]
        btan_acc = [[0.0, 0.0, 0.0] for _ in range(n_verts)]

        for fi in range(n_faces):
            face = faces[fi]
            if len(face) < 3:
                continue
            i0, i1, i2 = int(face[0]), int(face[1]), int(face[2])
            if max(i0, i1, i2) >= n_verts:
                continue

            p0 = verts[i0]; p1 = verts[i1]; p2 = verts[i2]
            t0 = uvs[i0];   t1 = uvs[i1];   t2 = uvs[i2]

            # Edge vectors
            dp1x = float(p1[0])-float(p0[0]); dp1y = float(p1[1])-float(p0[1]); dp1z = float(p1[2])-float(p0[2])
            dp2x = float(p2[0])-float(p0[0]); dp2y = float(p2[1])-float(p0[1]); dp2z = float(p2[2])-float(p0[2])

            dt1u = float(t1[0])-float(t0[0]); dt1v = float(t1[1])-float(t0[1])
            dt2u = float(t2[0])-float(t0[0]); dt2v = float(t2[1])-float(t0[1])

            det = dt1u * dt2v - dt2u * dt1v
            if abs(det) < 1e-12:
                continue
            r = 1.0 / det

            tx = (dt2v * dp1x - dt1v * dp2x) * r
            ty = (dt2v * dp1y - dt1v * dp2y) * r
            tz = (dt2v * dp1z - dt1v * dp2z) * r

            bx = (dt1u * dp2x - dt2u * dp1x) * r
            by = (dt1u * dp2y - dt2u * dp1y) * r
            bz = (dt1u * dp2z - dt2u * dp1z) * r

            # Triangle area weight (cross-product magnitude)
            cx = dp1y*dp2z - dp1z*dp2y
            cy = dp1z*dp2x - dp1x*dp2z
            cz = dp1x*dp2y - dp1y*dp2x
            area = math.sqrt(cx*cx + cy*cy + cz*cz)

            for vi in (i0, i1, i2):
                tan_acc[vi][0]  += tx * area
                tan_acc[vi][1]  += ty * area
                tan_acc[vi][2]  += tz * area
                btan_acc[vi][0] += bx * area
                btan_acc[vi][1] += by * area
                btan_acc[vi][2] += bz * area

        # Build per-vertex TBN
        result_T = []
        result_B = []
        result_N = []

        for vi in range(n_verts):
            n_raw = norms[vi]
            nx, ny, nz = float(n_raw[0]), float(n_raw[1]), float(n_raw[2])
            nn = math.sqrt(nx*nx + ny*ny + nz*nz)
            if nn > 1e-9:
                nx, ny, nz = nx/nn, ny/nn, nz/nn

            tx, ty, tz = tan_acc[vi]
            # Gram-Schmidt orthogonalize T against N
            ndott = nx*tx + ny*ty + nz*tz
            tx -= ndott*nx; ty -= ndott*ny; tz -= ndott*nz
            tlen = math.sqrt(tx*tx + ty*ty + tz*tz)
            if tlen > 1e-9:
                tx, ty, tz = tx/tlen, ty/tlen, tz/tlen
            else:
                # Degenerate: pick an arbitrary tangent perpendicular to N
                if abs(nx) < 0.9:
                    tx, ty, tz = 1.0, 0.0, 0.0
                else:
                    tx, ty, tz = 0.0, 1.0, 0.0
                ndott = nx*tx + ny*ty + nz*tz
                tx -= ndott*nx; ty -= ndott*ny; tz -= ndott*nz
                tlen = math.sqrt(tx*tx + ty*ty + tz*tz)
                if tlen > 1e-9:
                    tx, ty, tz = tx/tlen, ty/tlen, tz/tlen

            bx, by, bz = btan_acc[vi]
            # Handedness: sign(dot(cross(N, T), B))
            cx = ny*tz - nz*ty
            cy = nz*tx - nx*tz
            cz = nx*ty - ny*tx
            handedness = 1.0 if (cx*bx + cy*by + cz*bz) >= 0.0 else -1.0

            # Normalized bitangent
            blen = math.sqrt(bx*bx + by*by + bz*bz)
            if blen > 1e-9:
                bx, by, bz = bx/blen, by/blen, bz/blen
            else:
                bx = cy; by = cz; bz = cx  # fallback: B = cross(N, T)

            result_T.append((tx, ty, tz, handedness))
            result_B.append((bx, by, bz))
            result_N.append((nx, ny, nz))

        return TBNResult(tangents=result_T, bitangents=result_B, normals=result_N)

    def compute_numpy(self, node) -> TBNResult:
        """NumPy-accelerated TBN computation (falls back to pure Python).

        Up to 30× faster than the pure-Python path for typical KotOR meshes
        (2k–15k triangles).
        """
        if not _NUMPY:
            return self.compute(node)

        verts  = getattr(node, 'vertices', getattr(node, 'verts', []))
        norms  = getattr(node, 'normals', [])
        uvs    = getattr(node, 'uvs', [])
        faces  = getattr(node, 'faces', [])

        n_verts = len(verts)
        n_faces = len(faces)
        if n_verts == 0 or n_faces == 0 or len(uvs) == 0:
            return TBNResult()

        try:
            V = np.array(verts,  dtype=np.float32)[:n_verts]
            N = np.array(norms,  dtype=np.float32)[:n_verts] if len(norms) >= n_verts else np.zeros((n_verts,3),np.float32)
            T = np.array(uvs,    dtype=np.float32)[:n_verts] if len(uvs)   >= n_verts else np.zeros((n_verts,2),np.float32)
            F = np.array(faces,  dtype=np.int32)
            if F.ndim == 1:
                F = F.reshape(-1, 3)
            if F.shape[1] < 3:
                return self.compute(node)
            # Pad arrays if needed
            if V.shape[0] < n_verts:
                V = np.vstack([V, np.zeros((n_verts - V.shape[0], 3), np.float32)])
            if N.shape[0] < n_verts:
                pad = np.zeros((n_verts - N.shape[0], 3), np.float32)
                pad[:,2] = 1.0
                N = np.vstack([N, pad])
            if T.shape[0] < n_verts:
                T = np.vstack([T, np.zeros((n_verts - T.shape[0], 2), np.float32)])
        except Exception:
            return self.compute(node)

        # Vectorized per-face computation
        i0 = F[:, 0]; i1 = F[:, 1]; i2 = F[:, 2]
        # Guard out-of-range indices
        valid = (i0 < n_verts) & (i1 < n_verts) & (i2 < n_verts)
        i0, i1, i2 = i0[valid], i1[valid], i2[valid]

        P0, P1, P2 = V[i0], V[i1], V[i2]
        T0, T1, T2 = T[i0], T[i1], T[i2]

        dP1 = P1 - P0; dP2 = P2 - P0
        dT1 = T1 - T0; dT2 = T2 - T0

        det = dT1[:,0]*dT2[:,1] - dT2[:,0]*dT1[:,1]
        det_safe = np.where(np.abs(det) < 1e-12, 1e-12, det)
        r = 1.0 / det_safe

        # Face tangents / bitangents
        TF = np.column_stack([
            (dT2[:,1]*dP1[:,c] - dT1[:,1]*dP2[:,c]) * r for c in range(3)
        ])
        BF = np.column_stack([
            (dT1[:,0]*dP2[:,c] - dT2[:,0]*dP1[:,c]) * r for c in range(3)
        ])

        # Area weights
        cross = np.cross(dP1, dP2)
        area  = np.linalg.norm(cross, axis=1, keepdims=True)

        # Accumulate
        tan_acc  = np.zeros((n_verts, 3), np.float64)
        btan_acc = np.zeros((n_verts, 3), np.float64)
        for fi in range(len(i0)):
            w = float(area[fi, 0])
            for idx in (int(i0[fi]), int(i1[fi]), int(i2[fi])):
                tan_acc[idx]  += TF[fi] * w
                btan_acc[idx] += BF[fi] * w

        # Normalize normals
        N_len = np.linalg.norm(N, axis=1, keepdims=True)
        N_len = np.where(N_len < 1e-9, 1.0, N_len)
        Nn = N / N_len

        # Gram-Schmidt: T_ortho = T - dot(T,N)*N
        dot_TN = np.sum(tan_acc * Nn, axis=1, keepdims=True)
        T_orth = tan_acc - dot_TN * Nn
        T_len  = np.linalg.norm(T_orth, axis=1, keepdims=True)
        T_len  = np.where(T_len < 1e-9, 1.0, T_len)
        T_norm = T_orth / T_len

        # Handedness: sign(dot(cross(N, T), B))
        NcrossT = np.cross(Nn, T_norm)
        hand    = np.sign(np.sum(NcrossT * btan_acc, axis=1))
        hand    = np.where(hand == 0, 1.0, hand)

        # Normalize bitangent
        B_len = np.linalg.norm(btan_acc, axis=1, keepdims=True)
        B_len = np.where(B_len < 1e-9, 1.0, B_len)
        B_norm = btan_acc / B_len

        result_T = [(float(T_norm[i,0]), float(T_norm[i,1]), float(T_norm[i,2]), float(hand[i]))
                    for i in range(n_verts)]
        result_B = [(float(B_norm[i,0]), float(B_norm[i,1]), float(B_norm[i,2]))
                    for i in range(n_verts)]
        result_N = [(float(Nn[i,0]), float(Nn[i,1]), float(Nn[i,2]))
                    for i in range(n_verts)]

        return TBNResult(tangents=result_T, bitangents=result_B, normals=result_N)


# ─────────────────────────────────────────────────────────────────────────────
#  GLSL Shader Extension Constants
# ─────────────────────────────────────────────────────────────────────────────

# Vertex shader addition: bone indices/weights inputs + LBS transform.
# Designed to be inserted into _VERT_SRC BEFORE the void main() block.
# When concatenated with the base _VERT_SRC these add:
#   in ivec4 in_bone_ids;    — 4 bone indices into u_bones[]
#   in vec4  in_weights;     — corresponding blend weights (must sum to 1)
#   in vec4  in_tangent;     — (Tx, Ty, Tz, handedness) from TBNComputer
# And export:
#   out vec3 v_tangent;      — world-space tangent (to fragment shader)
#   out vec3 v_bitangent;    — world-space bitangent
VERT_SKIN_UNIFORMS = """\
// ── Phase 5.0: Matrix-palette skinning (Gregory §12.5.2) ────────────────────
// SSBO bone-matrix palette (std430 layout, MAX_BONES=128)
// Requires GLSL 4.30 / GL_ARB_shader_storage_buffer_object
// Falls back to uniform mat4 array when SSBO unavailable.
#if defined(SKINNING_SSBO)
layout(std430, binding = 0) readonly buffer BonePalette {
    mat4 u_bones[128];
};
#else
// Uniform array fallback (max 128 bones, requires GL 3.3+)
uniform mat4 u_bones[128];
#endif
uniform int  u_skin_enabled;  // 1 = LBS skinning active

// ── Phase 5.0: Per-vertex skin attributes ────────────────────────────────────
in ivec4 in_bone_ids;   // 4 bone indices (−1 = unused)
in vec4  in_weights;    // corresponding blend weights

// ── Phase 5.0: TBN tangent attribute (from TBNComputer) ─────────────────────
in vec4  in_tangent;    // (Tx, Ty, Tz, handedness)

// Additional outputs to fragment shader
out vec3 v_tangent;
out vec3 v_bitangent;
"""

VERT_SKIN_MAIN = """\
// ── Phase 5.0: Linear Blend Skinning (Gregory §12.5.2) ──────────────────────
vec4 skinned_pos  = vec4(0.0);
vec3 skinned_norm = vec3(0.0);
vec3 skinned_tan  = vec3(0.0);
if (u_skin_enabled == 1) {
    for (int i = 0; i < 4; ++i) {
        int  bi = in_bone_ids[i];
        float w = in_weights[i];
        if (bi < 0 || w < 0.0001) continue;
        mat4 M = u_bones[bi];
        skinned_pos  += w * (M * vec4(in_pos, 1.0));
        skinned_norm += w * (mat3(M) * in_norm);
        skinned_tan  += w * (mat3(M) * in_tangent.xyz);
    }
} else {
    skinned_pos  = vec4(in_pos, 1.0);
    skinned_norm = in_norm;
    skinned_tan  = in_tangent.xyz;
}

// Orthonormalize tangent output (handles weight-sum imprecision)
vec3 N_out = normalize(u_normal_mat * skinned_norm);
vec3 T_out = normalize(mat3(u_normal_mat) * skinned_tan);
T_out = normalize(T_out - dot(T_out, N_out) * N_out);
v_tangent   = T_out;
v_bitangent = cross(N_out, T_out) * in_tangent.w;  // handedness
"""

# Fragment shader addition: normal-map sampling + TBN perturbed lighting.
# Inserted AFTER the existing uniform block, BEFORE void main().
FRAG_TBN_UNIFORMS = """\
// ── Phase 5.0: TBN normal map (Lengyel §7.8) ─────────────────────────────────
uniform sampler2D u_nmap_tex;   // normal map (tangent space, unit 4)
uniform int       u_has_nmap;   // 1 = normal map bound

// Inputs from skinning vertex shader
in vec3 v_tangent;
in vec3 v_bitangent;
"""

FRAG_TBN_NORMAL = """\
// ── Phase 5.0: Perturbed normal from normal map ────────────────────────────
// If a tangent-space normal map is bound, unpack and transform to world space.
// Uses the TBN matrix built from TBNComputer-derived vertex tangents.
vec3 N;
if (u_has_nmap == 1) {
    vec3 nmap_samp = texture(u_nmap_tex, v_uv).rgb * 2.0 - 1.0;
    // TBN columns: (v_tangent, v_bitangent, v_world_norm)
    mat3 TBN = mat3(
        normalize(v_tangent),
        normalize(v_bitangent),
        normalize(v_world_norm)
    );
    N = normalize(TBN * nmap_samp);
} else {
    N = normalize(v_world_norm);
}
"""

# SSBO layout declaration for GLSL (used in SSBO binding query)
SSBO_GLSL_DECL = """\
layout(std430, binding = 0) readonly buffer BonePalette {
    mat4 u_bones[128];
};
"""


# ─────────────────────────────────────────────────────────────────────────────
#  v7.2 TBN Validation (Finding 5.9 — reone v_model.glsl cross-ref)
# ─────────────────────────────────────────────────────────────────────────────

def validate_tbn(tbn_result: TBNResult) -> Dict[str, Any]:
    """Validate TBN vectors against reone reference implementation.

    Checks:
    1. All tangents are unit-length (within tolerance)
    2. All normals are unit-length
    3. T·N ≈ 0 (orthogonality after Gram-Schmidt)
    4. Handedness is ±1 (sign(dot(cross(N,T), B)))
    5. B = cross(N,T) × handedness (reconstructed bitangent matches)

    Reference: reone v_model.glsl lines 76-80; Lengyel §7.8 orthogonality.

    Returns
    -------
    dict with keys:
        'valid': bool — True if all checks pass
        'vertex_count': int — number of vertices
        'unit_tangent_errors': int — tangents not unit-length
        'unit_normal_errors': int — normals not unit-length
        'orthogonality_errors': int — T·N not near zero
        'handedness_errors': int — handedness not ±1
        'bitangent_errors': int — reconstructed B doesn't match
    """
    result = {
        'valid': True,
        'vertex_count': tbn_result.vertex_count,
        'unit_tangent_errors': 0,
        'unit_normal_errors': 0,
        'orthogonality_errors': 0,
        'handedness_errors': 0,
        'bitangent_errors': 0,
    }

    UNIT_TOL = 0.01       # tolerance for unit-length check
    ORTHO_TOL = 0.05      # tolerance for orthogonality (T·N ≈ 0)
    BITAN_TOL = 0.1       # tolerance for bitangent reconstruction

    for i in range(tbn_result.vertex_count):
        tx, ty, tz, tw = tbn_result.tangents[i]
        bx, by, bz = tbn_result.bitangents[i]
        nx, ny, nz = tbn_result.normals[i]

        # Check tangent unit length
        t_len = math.sqrt(tx*tx + ty*ty + tz*tz)
        if abs(t_len - 1.0) > UNIT_TOL:
            result['unit_tangent_errors'] += 1

        # Check normal unit length
        n_len = math.sqrt(nx*nx + ny*ny + nz*nz)
        if abs(n_len - 1.0) > UNIT_TOL:
            result['unit_normal_errors'] += 1

        # Check orthogonality: T·N should be ~0 after Gram-Schmidt
        dot_tn = tx*nx + ty*ny + tz*nz
        if abs(dot_tn) > ORTHO_TOL:
            result['orthogonality_errors'] += 1

        # Check handedness is ±1
        if abs(abs(tw) - 1.0) > UNIT_TOL:
            result['handedness_errors'] += 1

        # Check bitangent reconstruction: B should ≈ cross(N,T) * handedness
        # reone v_model.glsl: v_bitangent = cross(N_out, T_out) * in_tangent.w
        rb_x = (ny*tz - nz*ty) * tw
        rb_y = (nz*tx - nx*tz) * tw
        rb_z = (nx*ty - ny*tx) * tw
        diff_b = math.sqrt((bx-rb_x)**2 + (by-rb_y)**2 + (bz-rb_z)**2)
        if diff_b > BITAN_TOL:
            result['bitangent_errors'] += 1

    total_errors = sum(v for k, v in result.items() if k.endswith('_errors'))
    result['valid'] = (total_errors == 0)

    if total_errors > 0:
        log.warning(f"validate_tbn: {total_errors} errors in {tbn_result.vertex_count} vertices "
                    f"(tangent={result['unit_tangent_errors']}, normal={result['unit_normal_errors']}, "
                    f"ortho={result['orthogonality_errors']}, hand={result['handedness_errors']}, "
                    f"bitan={result['bitangent_errors']})")
    else:
        log.debug(f"validate_tbn: {tbn_result.vertex_count} vertices — all checks pass ✓")

    return result
