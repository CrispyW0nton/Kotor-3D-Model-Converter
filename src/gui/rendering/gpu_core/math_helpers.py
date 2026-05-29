from __future__ import annotations

from .diagnostics import *  # noqa: F401,F403
def _mat4_perspective(fov_y: float, aspect: float, near: float, far: float):
    """Build a right-handed perspective projection matrix (standard row-major).

    Standard GLM-style perspective (clip.w = -view_z, NDC.z in [-1,+1]):
      Row 0: (f/a, 0,   0,               0)
      Row 1: (0,   f,   0,               0)
      Row 2: (0,   0,   -(f+n)/(f-n),   -2fn/(f-n))
      Row 3: (0,   0,   -1,              0)

    clip.w = row3 . view_v = -view_z  (gives standard perspective divide)
    Use _mat4_tobytes() to convert to GLSL column-major bytes for upload.
    """
    f = 1.0 / math.tan(fov_y * 0.5)
    nf = 1.0 / (near - far)   # = -1/(far-near)
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) * nf      # -(f+n)/(f-n)
    m[2, 3] = 2.0 * far * near * nf  # -2fn/(f-n)
    m[3, 2] = -1.0                    # clip.w = -view_z
    return m


def _mat4_lookat(eye, center, up):
    """Build a right-handed look-at view matrix (standard row-major convention).

    Returns a standard 4x4 NumPy matrix where:
      row0 = right vector (s) + tx at [0,3]
      row1 = up vector (u) + ty at [1,3]
      row2 = -forward vector + tz at [2,3]
      row3 = (0, 0, 0, 1)
    Use _mat4_tobytes() to convert to GLSL column-major bytes.
    """
    eye = np.array(eye, dtype=np.float64)
    center = np.array(center, dtype=np.float64)
    up = np.array(up, dtype=np.float64)
    f = center - eye;  f /= np.linalg.norm(f)
    s = np.cross(f, up); s /= np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.eye(4, dtype=np.float32)
    m[0, :3] = s
    m[1, :3] = u
    m[2, :3] = -f
    m[0, 3] = -np.dot(s, eye)
    m[1, 3] = -np.dot(u, eye)
    m[2, 3] =  np.dot(f, eye)
    return m


def _mat4_identity():
    return np.eye(4, dtype=np.float32)


def _mat4_tobytes(m: np.ndarray) -> bytes:
    """Convert a standard row-major NumPy 4x4 matrix to GLSL column-major bytes.

    ModernGL/OpenGL reads mat4 uniforms in column-major order.  NumPy's tobytes()
    outputs row-major bytes.  Transposing before tobytes() gives column-major output.
    """
    return m.reshape(4, 4).T.astype(np.float32).tobytes()


def _mat4_mul(a, b):
    """Multiply two row-major 4x4 matrices: returns a @ b."""
    return (a.reshape(4, 4) @ b.reshape(4, 4)).astype(np.float32)


def _mat3_normal(model_mat: np.ndarray) -> np.ndarray:
    """Compute the normal matrix = transpose(inverse(model_mat_3x3))."""
    m33 = model_mat.reshape(4, 4)[:3, :3].copy()
    try:
        return np.linalg.inv(m33).T.astype(np.float32)
    except np.linalg.LinAlgError:
        return np.eye(3, dtype=np.float32)


def _scene_gpu_root_for_node(node):
    current = node
    visited = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if bool(getattr(current, "_gr_scene_object_root", False)) and bool(getattr(current, "_gr_scene_gpu_transform", False)):
            return current
        current = getattr(current, "parent", None)
    return None


def _mat4_from_pos_quat_scale(pos, quat, scale) -> np.ndarray:
    mat = _matrix_from_pos_quat_np(pos, quat)
    if mat is None:
        mat = np.eye(4, dtype=np.float64)
    try:
        sx, sy, sz = (float(v) for v in tuple(scale or (1.0, 1.0, 1.0))[:3])
    except Exception:
        sx, sy, sz = 1.0, 1.0, 1.0
    scale_mat = np.diag([sx, sy, sz, 1.0]).astype(np.float64)
    return (mat.reshape(4, 4) @ scale_mat).astype(np.float32)


def _scene_gpu_model_matrix(node) -> Optional[np.ndarray]:
    root = _scene_gpu_root_for_node(node)
    if root is None:
        return None
    return _mat4_from_pos_quat_scale(
        getattr(root, "position", (0.0, 0.0, 0.0)),
        getattr(root, "rotation", (0.0, 0.0, 0.0, 1.0)),
        getattr(root, "_gr_scale", (1.0, 1.0, 1.0)),
    )


def _bas_attachment_local_transform_np(node, bas_root):
    wx = wy = wz = 0.0
    parent_q = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    chain = []
    current = node
    visited = set()
    while current is not None:
        if id(current) in visited or len(chain) > 512:
            break
        visited.add(id(current))
        chain.append(current)
        if current is bas_root:
            break
        current = getattr(current, "parent", None)
    chain.reverse()
    for chain_node in chain:
        lx, ly, lz = getattr(chain_node, "position", (0.0, 0.0, 0.0))
        rot = list(getattr(chain_node, "rotation", (0.0, 0.0, 0.0, 1.0)))
        r2 = rot[0]**2 + rot[1]**2 + rot[2]**2 + rot[3]**2
        if r2 > 1e-9 and abs(r2 - 1.0) > 1e-4:
            rs = r2 ** 0.5
            rot = [rot[0] / rs, rot[1] / rs, rot[2] / rs, rot[3] / rs]
        rotated = _quat_rotate_batch(parent_q, np.array([[lx, ly, lz]], dtype=np.float64))[0]
        wx += float(rotated[0])
        wy += float(rotated[1])
        wz += float(rotated[2])
        px, py, pz, pw = parent_q
        nx, ny, nz, nw = np.array(rot, dtype=np.float64)
        parent_q = np.array([
            pw * nx + px * nw + py * nz - pz * ny,
            pw * ny - px * nz + py * nw + pz * nx,
            pw * nz + px * ny - py * nx + pz * nw,
            pw * nw - px * nx - py * ny - pz * nz,
        ], dtype=np.float64)
    q_len = float(np.linalg.norm(parent_q))
    if q_len > 1e-9:
        parent_q = parent_q / q_len
    else:
        parent_q = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    return (float(wx), float(wy), float(wz)), tuple(float(v) for v in parent_q.tolist())


def _quat_multiply_xyzw(parent, child) -> tuple[float, float, float, float]:
    px, py, pz, pw = (float(v) for v in tuple(parent)[:4])
    cx, cy, cz, cw = (float(v) for v in tuple(child)[:4])
    return (
        pw * cx + px * cw + py * cz - pz * cy,
        pw * cy - px * cz + py * cw + pz * cx,
        pw * cz + px * cy - py * cx + pz * cw,
        pw * cw - px * cx - py * cy - pz * cz,
    )


def _scene_authored_world_transform(node):
    root = _scene_gpu_root_for_node(node)
    if root is None:
        return None
    chain = []
    current = node
    visited = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        chain.append(current)
        if current is root:
            break
        current = getattr(current, "parent", None)
    if not chain or chain[-1] is not root:
        return None
    chain.reverse()
    world_pos = np.array([0.0, 0.0, 0.0], dtype=np.float64)
    world_rot = (0.0, 0.0, 0.0, 1.0)
    for current in chain:
        if current is root:
            local_pos = getattr(current, "_gr_scene_source_position", getattr(current, "position", (0.0, 0.0, 0.0)))
            local_rot = getattr(current, "_gr_scene_source_rotation", getattr(current, "rotation", (0.0, 0.0, 0.0, 1.0)))
        else:
            local_pos = getattr(current, "position", (0.0, 0.0, 0.0))
            local_rot = getattr(current, "rotation", (0.0, 0.0, 0.0, 1.0))
        try:
            local_vec = np.array([tuple(float(v) for v in tuple(local_pos)[:3])], dtype=np.float64)
        except Exception:
            local_vec = np.array([(0.0, 0.0, 0.0)], dtype=np.float64)
        world_pos = world_pos + _quat_rotate_batch(np.array(world_rot, dtype=np.float64), local_vec)[0]
        try:
            world_rot = _quat_multiply_xyzw(world_rot, local_rot)
        except Exception:
            pass
    return (tuple(float(v) for v in world_pos.tolist()), world_rot)


# ─────────────────────────────────────────────────────────────────────────────
#  Texture cache
# ─────────────────────────────────────────────────────────────────────────────


def _quat_rotate_batch(q: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Vectorized quaternion rotation for Nx3 points using q=(x,y,z,w)."""
    qx, qy, qz, qw = q
    q_vec = np.array([qx, qy, qz], dtype=np.float64)
    t = 2.0 * np.cross(q_vec, pts)
    return pts + qw * t + np.cross(q_vec, t)


__all__ = tuple(name for name in globals() if not name.startswith("__"))
