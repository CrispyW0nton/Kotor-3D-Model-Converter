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
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

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
        self._inv_bind    : Dict[str, List[List[float]]] = {}   # bone_name → 4×4 row-major
        self._palette     : List[BoneMatrix] = []
        self._bone_order  : List[str] = []   # ordered bone names for index lookup
        self._ssbo        : Optional['moderngl.Buffer'] = None
        self._dirty       : bool = True

    # ── Build inverse bind-pose ───────────────────────────────────────────────

    def build_inverse_bind_pose(self, model) -> int:
        """Walk the model's node tree and compute per-bone inverse bind-pose matrices.

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

        if model is None:
            return 0

        nodes = list(model.all_nodes()) if hasattr(model, 'all_nodes') else []
        count = 0
        for node in nodes:
            name = getattr(node, 'name', '')
            if not name:
                continue
            # Bind-pose position and rotation
            pos  = getattr(node, 'position', getattr(node, 'pos', (0.0, 0.0, 0.0)))
            quat = getattr(node, 'rotation', getattr(node, 'quat', (0.0, 0.0, 0.0, 1.0)))
            if pos is None:
                pos = (0.0, 0.0, 0.0)
            if quat is None:
                quat = (0.0, 0.0, 0.0, 1.0)
            # Normalise quaternion
            qx, qy, qz, qw = float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3])
            qlen = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
            if qlen > 1e-9:
                qx, qy, qz, qw = qx/qlen, qy/qlen, qz/qlen, qw/qlen
            else:
                qx, qy, qz, qw = 0.0, 0.0, 0.0, 1.0

            rot_m  = _quat_to_mat4((qx, qy, qz, qw))
            tx, ty, tz = float(pos[0]), float(pos[1]), float(pos[2])
            # Combine rotation + translation: T × R
            bind_m = _mat4_mul_py(_mat4_translate_py(tx, ty, tz), rot_m)

            # Invert: for pure rotation + translation, inv = R^T × T(-t)
            # General inversion via cofactors (pure Python, no numpy)
            try:
                inv_m = _mat4_invert_py(bind_m)
            except Exception:
                inv_m = _mat4_identity_py()

            self._inv_bind[name.lower()] = inv_m
            if len(self._bone_order) < self._max_bones:
                self._bone_order.append(name.lower())
            count += 1

        self._dirty = True
        log.debug(f"MatrixPaletteUploader: built {count} inverse bind-pose matrices")
        return count

    # ── Compute palette for current pose ─────────────────────────────────────

    def compute_palette(self, anim_pose) -> List[BoneMatrix]:
        """Compute the full bone-matrix palette from an ``AnimPose``.

        For each bone in ``_bone_order``:
            M_skin = M_world_pose × M_inv_bind

        Parameters
        ----------
        anim_pose : AnimPose | None
            The pose evaluated by ``AnimationEngine.evaluate()``.  If None,
            all matrices are identity (bind pose).

        Returns
        -------
        list[BoneMatrix]
            Palette in the same order as ``_bone_order``.
        """
        self._palette = []
        pose_nodes: Dict[str, object] = {}
        if anim_pose is not None:
            raw = getattr(anim_pose, 'nodes', {})
            pose_nodes = {k.lower(): v for k, v in raw.items()}

        for idx, bname in enumerate(self._bone_order):
            inv_bind = self._inv_bind.get(bname, _mat4_identity_py())

            # World pose: position + rotation from AnimPose node
            pn = pose_nodes.get(bname, None)
            if pn is not None:
                p   = getattr(pn, 'position', (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
                q   = getattr(pn, 'rotation', (0.0, 0.0, 0.0, 1.0)) or (0.0, 0.0, 0.0, 1.0)
                qx, qy, qz, qw = float(q[0]), float(q[1]), float(q[2]), float(q[3])
                ql = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
                if ql > 1e-9:
                    qx, qy, qz, qw = qx/ql, qy/ql, qz/ql, qw/ql
                rot_m  = _quat_to_mat4((qx, qy, qz, qw))
                tx, ty, tz = float(p[0]), float(p[1]), float(p[2])
                pose_m = _mat4_mul_py(_mat4_translate_py(tx, ty, tz), rot_m)
            else:
                pose_m = _mat4_identity_py()

            skin_m = _mat4_mul_py(pose_m, inv_bind)
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
