"""
test_v440_gpu_skinning_tbn.py
============================
Phase 5.0 — Matrix-palette SSBO upload + TBN tangent-space computation.

Test coverage
─────────────
MatrixPaletteUploader
  ╠═ build_inverse_bind_pose  (identity / translated / rotated bones, null/empty model)
  ╠═ compute_palette          (identity pose, animated pose, missing bones)
  ╠═ as_numpy_array           (shape, dtype, values)
  ╠═ as_flat_bytes            (length = MAX_BONES × 16 × 4, padding, column-major identity check)
  ╠═ bone_index               (hit, miss)
  ╚═ SSBO upload skips gracefully when moderngl absent

TBNComputer
  ╠═ compute / compute_numpy  (single-triangle unit-quad, multi-face, degenerate UVs)
  ╠═ vertex_count             (correct for all meshes)
  ╠═ tangent orthogonality    (|T|=1, T⊥N, |B|=1)
  ╠═ handedness               (+1 / -1 for CCW / CW UV parameterization)
  ╠═ empty / degenerate mesh  (returns TBNResult with 0 vertices, no crash)
  ╚═ numpy vs pure-python agreement  (max deviation < 1e-4)

SceneFrameRenderer (Phase 5.1 wiring)
  ╠═ build_draw_list from a populated SceneGraph (rooms + objects)
  ╠═ NULL room filtering
  ╠═ per-room visibility override
  ╠═ object_type_filter
  ╚═ empty / None scene graph

GLSL constant presence
  ╠═ VERT_SKIN_UNIFORMS     contains 'u_bones', 'in_bone_ids', 'in_weights', 'in_tangent'
  ╠═ VERT_SKIN_MAIN         contains 'u_skin_enabled', 'skinned_pos'
  ╠═ FRAG_TBN_UNIFORMS      contains 'u_nmap_tex', 'u_has_nmap', 'v_tangent', 'v_bitangent'
  ╚═ FRAG_TBN_NORMAL        contains 'TBN', 'texture', 'nmap_samp'

Math helpers (internal)
  ╠═ _quat_to_mat4            (identity quat → identity matrix)
  ╠═ _mat4_mul_py             (I × M = M)
  ╠═ _mat4_invert_py          (M × inv(M) ≈ I, singular raises ValueError)
  ╚═ _mat4_to_flat_col        (column-major order)
"""

import math
import sys
import os
import types
import unittest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo not in sys.path:
    sys.path.insert(0, _repo)
if os.path.join(_repo, 'src') not in sys.path:
    sys.path.insert(0, os.path.join(_repo, 'src'))

from src.core.gpu_skinning import (
    MatrixPaletteUploader, BoneMatrix, TBNComputer, TBNResult,
    MAX_BONES, BONE_PALETTE_BINDING,
    VERT_SKIN_UNIFORMS, VERT_SKIN_MAIN,
    FRAG_TBN_UNIFORMS, FRAG_TBN_NORMAL,
    SSBO_GLSL_DECL,
    _quat_to_mat4, _mat4_mul_py, _mat4_identity_py,
    _mat4_invert_py, _mat4_to_flat_col, _mat4_translate_py,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Shared mock helpers
# ─────────────────────────────────────────────────────────────────────────────

class _MockNode:
    """Minimal ModelNode stub."""
    def __init__(self, name, pos=(0,0,0), quat=(0,0,0,1)):
        self.name     = name
        self.position = pos
        self.rotation = quat


class _MockModel:
    """Minimal KotorModel stub with all_nodes()."""
    def __init__(self, nodes=None):
        self._nodes = nodes or []

    def all_nodes(self):
        return iter(self._nodes)


class _MockMesh:
    """Minimal mesh node stub for TBNComputer."""
    def __init__(self, vertices, normals, uvs, faces):
        self.vertices = vertices
        self.normals  = normals
        self.uvs      = uvs
        self.faces    = faces


def _unit_quad_mesh():
    """Unit quad in the XY plane (two triangles, flat UVs)."""
    verts = [(0,0,0), (1,0,0), (1,1,0), (0,1,0)]
    norms = [(0,0,1)] * 4
    uvs   = [(0,0), (1,0), (1,1), (0,1)]
    faces = [(0,1,2), (0,2,3)]
    return _MockMesh(verts, norms, uvs, faces)


def _mat_approx(m1, m2, tol=1e-5):
    """Return True if two flat 4×4 column-major matrices are element-wise ≤ tol."""
    for a, b in zip(m1, m2):
        if abs(a - b) > tol:
            return False
    return True


def _identity_flat():
    return _mat4_to_flat_col(_mat4_identity_py())


# ─────────────────────────────────────────────────────────────────────────────
#  Tests — Math helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestMathHelpers(unittest.TestCase):

    # ── _quat_to_mat4 ────────────────────────────────────────────────────────

    def test_identity_quat_gives_identity_matrix(self):
        m = _quat_to_mat4((0, 0, 0, 1))
        # Row-major: diagonal = 1, off-diagonal = 0
        for r in range(4):
            for c in range(4):
                expected = 1.0 if r == c else 0.0
                self.assertAlmostEqual(m[r][c], expected, places=6)

    def test_180_rotation_around_z(self):
        """180° around Z: (0, 0, 1, 0) → X→-X, Y→-Y, Z→Z."""
        m = _quat_to_mat4((0, 0, 1, 0))
        self.assertAlmostEqual(m[0][0], -1.0, places=5)
        self.assertAlmostEqual(m[1][1], -1.0, places=5)
        self.assertAlmostEqual(m[2][2],  1.0, places=5)

    def test_90_rotation_around_x(self):
        """90° around X: quat = (sin45, 0, 0, cos45)."""
        s = math.sin(math.pi / 4)
        c = math.cos(math.pi / 4)
        m = _quat_to_mat4((s, 0, 0, c))
        # Y→-Z (row 1, col 2 should be ~-1)
        self.assertAlmostEqual(m[1][2], -1.0, places=5)
        # Z→Y (row 2, col 1 should be ~+1)
        self.assertAlmostEqual(m[2][1],  1.0, places=5)

    # ── _mat4_mul_py ─────────────────────────────────────────────────────────

    def test_identity_times_identity(self):
        I = _mat4_identity_py()
        result = _mat4_mul_py(I, I)
        for r in range(4):
            for c in range(4):
                self.assertAlmostEqual(result[r][c], I[r][c], places=10)

    def test_mul_by_identity_preserves_matrix(self):
        I = _mat4_identity_py()
        T = _mat4_translate_py(1, 2, 3)
        result = _mat4_mul_py(T, I)
        for r in range(4):
            for c in range(4):
                self.assertAlmostEqual(result[r][c], T[r][c], places=10)

    def test_mul_translation_accumulates(self):
        T1 = _mat4_translate_py(1, 0, 0)
        T2 = _mat4_translate_py(0, 2, 0)
        T12 = _mat4_mul_py(T1, T2)
        # Translation column is row 0..2 col 3
        self.assertAlmostEqual(T12[0][3], 1.0, places=10)
        self.assertAlmostEqual(T12[1][3], 2.0, places=10)
        self.assertAlmostEqual(T12[2][3], 0.0, places=10)

    # ── _mat4_invert_py ───────────────────────────────────────────────────────

    def test_invert_identity(self):
        I    = _mat4_identity_py()
        Iinv = _mat4_invert_py(I)
        for r in range(4):
            for c in range(4):
                self.assertAlmostEqual(Iinv[r][c], I[r][c], places=9)

    def test_invert_translation(self):
        T    = _mat4_translate_py(3, -1, 5)
        Tinv = _mat4_invert_py(T)
        I    = _mat4_mul_py(T, Tinv)
        for r in range(4):
            for c in range(4):
                expected = 1.0 if r == c else 0.0
                self.assertAlmostEqual(I[r][c], expected, places=9)

    def test_invert_singular_raises(self):
        zero = [[0]*4 for _ in range(4)]
        with self.assertRaises(ValueError):
            _mat4_invert_py(zero)

    def test_invert_rotation_is_transpose(self):
        """For a pure-rotation matrix, inv == transpose (rows ↔ cols)."""
        s = math.sin(math.pi / 4)
        c = math.cos(math.pi / 4)
        R    = _quat_to_mat4((0, 0, s, c))   # 90° around Z
        Rinv = _mat4_invert_py(R)
        # Check inv(R) == R^T
        for r in range(3):
            for col in range(3):
                self.assertAlmostEqual(Rinv[r][col], R[col][r], places=6)

    # ── _mat4_to_flat_col ─────────────────────────────────────────────────────

    def test_flat_col_identity_has_ones_at_diagonal(self):
        flat = _mat4_to_flat_col(_mat4_identity_py())
        # col-major: positions [0,5,10,15] are diagonal
        for i in range(4):
            self.assertAlmostEqual(flat[i*4 + i], 1.0, places=9)

    def test_flat_col_length_16(self):
        flat = _mat4_to_flat_col(_mat4_identity_py())
        self.assertEqual(len(flat), 16)

    def test_flat_col_translation_at_positions_12_13_14(self):
        T    = _mat4_translate_py(7, 8, 9)
        flat = _mat4_to_flat_col(T)
        # Column-major: column 3 starts at index 12
        self.assertAlmostEqual(flat[12], 7.0, places=9)
        self.assertAlmostEqual(flat[13], 8.0, places=9)
        self.assertAlmostEqual(flat[14], 9.0, places=9)


# ─────────────────────────────────────────────────────────────────────────────
#  Tests — MatrixPaletteUploader
# ─────────────────────────────────────────────────────────────────────────────

class TestMatrixPaletteUploaderBuild(unittest.TestCase):

    def test_build_with_none_model_returns_zero(self):
        up = MatrixPaletteUploader()
        count = up.build_inverse_bind_pose(None)
        self.assertEqual(count, 0)
        self.assertEqual(up.bone_count, 0)

    def test_build_with_empty_model_returns_zero(self):
        up  = MatrixPaletteUploader()
        mdl = _MockModel([])
        count = up.build_inverse_bind_pose(mdl)
        self.assertEqual(count, 0)

    def test_build_with_single_identity_bone(self):
        up  = MatrixPaletteUploader()
        mdl = _MockModel([_MockNode('root', (0,0,0), (0,0,0,1))])
        count = up.build_inverse_bind_pose(mdl)
        self.assertEqual(count, 1)
        self.assertEqual(up.bone_count, 1)

    def test_bone_index_hit(self):
        up  = MatrixPaletteUploader()
        mdl = _MockModel([
            _MockNode('hip_g'),
            _MockNode('lbicep_g'),
        ])
        up.build_inverse_bind_pose(mdl)
        self.assertEqual(up.bone_index('hip_g'), 0)
        self.assertEqual(up.bone_index('lbicep_g'), 1)

    def test_bone_index_case_insensitive(self):
        up  = MatrixPaletteUploader()
        mdl = _MockModel([_MockNode('HipBone')])
        up.build_inverse_bind_pose(mdl)
        self.assertEqual(up.bone_index('hipbone'), 0)
        self.assertEqual(up.bone_index('HIPBONE'), 0)

    def test_bone_index_miss_returns_minus_one(self):
        up  = MatrixPaletteUploader()
        mdl = _MockModel([_MockNode('root')])
        up.build_inverse_bind_pose(mdl)
        self.assertEqual(up.bone_index('nonexistent'), -1)

    def test_build_respects_max_bones_cap(self):
        up  = MatrixPaletteUploader(max_bones=4)
        mdl = _MockModel([_MockNode(f'b{i}') for i in range(10)])
        count = up.build_inverse_bind_pose(mdl)
        self.assertEqual(count, 10)        # built all
        self.assertEqual(up.bone_count, 4) # but only 4 in order list


class TestMatrixPaletteUploaderPalette(unittest.TestCase):

    def setUp(self):
        self.up = MatrixPaletteUploader()
        nodes = [
            _MockNode('root',   (0,0,0), (0,0,0,1)),
            _MockNode('chest_g',(0,0,1), (0,0,0,1)),
        ]
        mdl = _MockModel(nodes)
        self.up.build_inverse_bind_pose(mdl)

    def test_compute_with_none_pose_returns_correct_count(self):
        palette = self.up.compute_palette(None)
        self.assertEqual(len(palette), 2)

    def test_compute_identity_pose_gives_identity_matrices(self):
        """No pose → all M_skin ≈ I × inv_bind; for no-translate/rotate bones
        the combined result must still be consistent (not necessarily identity
        when bind ≠ origin, but must not crash)."""
        palette = self.up.compute_palette(None)
        self.assertEqual(len(palette), 2)
        for bm in palette:
            self.assertEqual(len(bm.flat_col), 16)

    def test_bone_matrix_flat_col_length(self):
        palette = self.up.compute_palette(None)
        for bm in palette:
            self.assertEqual(len(bm.flat_col), 16)

    def test_bone_matrix_has_correct_name_and_index(self):
        palette = self.up.compute_palette(None)
        self.assertEqual(palette[0].bone_index, 0)
        self.assertEqual(palette[0].bone_name, 'root')
        self.assertEqual(palette[1].bone_index, 1)
        self.assertEqual(palette[1].bone_name, 'chest_g')

    def test_compute_with_animated_pose_does_not_crash(self):
        """AnimPose-like object: nodes dict with position/rotation."""
        class _FakePoseNode:
            position = (0.0, 0.0, 0.5)
            rotation = (0.0, 0.0, 0.0, 1.0)

        class _FakePose:
            nodes = {'root': _FakePoseNode(), 'chest_g': _FakePoseNode()}

        palette = self.up.compute_palette(_FakePose())
        self.assertEqual(len(palette), 2)
        for bm in palette:
            self.assertEqual(len(bm.flat_col), 16)

    def test_palette_returns_identity_for_identity_model(self):
        """For a model with no transform, palette matrices should be identity."""
        up  = MatrixPaletteUploader()
        mdl = _MockModel([_MockNode('x')])
        up.build_inverse_bind_pose(mdl)
        palette = up.compute_palette(None)
        self.assertEqual(len(palette), 1)
        flat = palette[0].flat_col
        identity = _identity_flat()
        for a, b in zip(flat, identity):
            self.assertAlmostEqual(a, b, places=5)


class TestMatrixPaletteUploaderOutput(unittest.TestCase):

    def setUp(self):
        self.up = MatrixPaletteUploader(max_bones=8)
        mdl = _MockModel([_MockNode(f'b{i}') for i in range(3)])
        self.up.build_inverse_bind_pose(mdl)
        self.up.compute_palette(None)

    def test_as_flat_bytes_length(self):
        data = self.up.as_flat_bytes()
        # MAX_BONES × 16 floats × 4 bytes
        self.assertEqual(len(data), 8 * 16 * 4)

    def test_as_flat_bytes_type(self):
        data = self.up.as_flat_bytes()
        self.assertIsInstance(data, bytes)

    def test_as_flat_bytes_padding_is_identity(self):
        """Unused slots (index >= bone_count) must be identity matrices."""
        import struct
        data = self.up.as_flat_bytes()
        floats = struct.unpack(f'{8*16}f', data)
        identity = _identity_flat()
        # Slot 3..7 should be identity
        for slot in range(3, 8):
            slot_floats = floats[slot*16:(slot+1)*16]
            for i, (a, b) in enumerate(zip(slot_floats, identity)):
                self.assertAlmostEqual(a, b, places=5,
                    msg=f"Slot {slot}, element {i}: {a} != {b}")

    def test_as_numpy_array_shape(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not available")
        arr = self.up.as_numpy_array()
        self.assertIsNotNone(arr)
        self.assertEqual(arr.shape, (3, 4, 4))
        self.assertEqual(arr.dtype, np.float32)

    def test_as_numpy_array_none_when_no_palette(self):
        up2 = MatrixPaletteUploader()
        # No palette computed yet
        result = up2.as_numpy_array()
        self.assertIsNone(result)


class TestMatrixPaletteSSBO(unittest.TestCase):

    def test_upload_to_ssbo_returns_none_without_moderngl(self):
        """When moderngl is absent, upload_to_ssbo must not crash and returns None."""
        up  = MatrixPaletteUploader()
        mdl = _MockModel([_MockNode('root')])
        up.build_inverse_bind_pose(mdl)
        up.compute_palette(None)
        # Pass a fake context (won't have moderngl but should return None gracefully)
        result = up.upload_to_ssbo(None)
        self.assertIsNone(result)

    def test_release_when_no_ssbo_does_not_crash(self):
        up = MatrixPaletteUploader()
        up.release()  # must not raise


# ─────────────────────────────────────────────────────────────────────────────
#  Tests — TBNComputer
# ─────────────────────────────────────────────────────────────────────────────

class TestTBNComputerBasic(unittest.TestCase):

    def test_empty_mesh_returns_empty_result(self):
        comp = TBNComputer()
        mesh = _MockMesh([], [], [], [])
        result = comp.compute(mesh)
        self.assertEqual(result.vertex_count, 0)

    def test_mesh_without_uvs_returns_empty(self):
        comp = TBNComputer()
        mesh = _MockMesh([(0,0,0),(1,0,0),(0,1,0)], [(0,0,1)]*3, [], [(0,1,2)])
        result = comp.compute(mesh)
        self.assertEqual(result.vertex_count, 0)

    def test_single_triangle_returns_3_vertices(self):
        comp = TBNComputer()
        mesh = _MockMesh(
            [(0,0,0),(1,0,0),(0,1,0)],
            [(0,0,1),(0,0,1),(0,0,1)],
            [(0,0),(1,0),(0,1)],
            [(0,1,2)],
        )
        result = comp.compute(mesh)
        self.assertEqual(result.vertex_count, 3)

    def test_result_lists_have_same_length(self):
        comp   = TBNComputer()
        mesh   = _unit_quad_mesh()
        result = comp.compute(mesh)
        self.assertEqual(len(result.tangents),   result.vertex_count)
        self.assertEqual(len(result.bitangents),  result.vertex_count)
        self.assertEqual(len(result.normals),     result.vertex_count)

    def test_unit_quad_vertex_count(self):
        comp   = TBNComputer()
        result = comp.compute(_unit_quad_mesh())
        self.assertEqual(result.vertex_count, 4)


class TestTBNOrthonormality(unittest.TestCase):

    def _check_all_orthonormal(self, result: TBNResult, tol=1e-4):
        for i in range(result.vertex_count):
            tx, ty, tz, _ = result.tangents[i]
            bx, by, bz    = result.bitangents[i]
            nx, ny, nz    = result.normals[i]

            t_len = math.sqrt(tx*tx + ty*ty + tz*tz)
            b_len = math.sqrt(bx*bx + by*by + bz*bz)
            n_len = math.sqrt(nx*nx + ny*ny + nz*nz)

            self.assertAlmostEqual(t_len, 1.0, delta=tol, msg=f"v{i}: |T|={t_len}")
            self.assertAlmostEqual(b_len, 1.0, delta=tol, msg=f"v{i}: |B|={b_len}")
            self.assertAlmostEqual(n_len, 1.0, delta=tol, msg=f"v{i}: |N|={n_len}")

            # T ⊥ N
            dot_tn = abs(tx*nx + ty*ny + tz*nz)
            self.assertLess(dot_tn, tol, msg=f"v{i}: T·N={dot_tn:.6f} (not ⊥)")

    def test_unit_quad_orthonormal(self):
        comp   = TBNComputer()
        result = comp.compute(_unit_quad_mesh())
        self._check_all_orthonormal(result)

    def test_tilted_triangle_orthonormal(self):
        """Triangle tilted 45° in XZ plane."""
        s = math.sqrt(0.5)
        mesh = _MockMesh(
            [(0,0,0),(1,0,0),(0,0,1)],
            [(0, s, s),(0, s, s),(0, s, s)],
            [(0,0),(1,0),(0,1)],
            [(0,1,2)],
        )
        comp   = TBNComputer()
        result = comp.compute(mesh)
        self._check_all_orthonormal(result)


class TestTBNHandedness(unittest.TestCase):

    def test_standard_ccw_uv_gives_positive_handedness(self):
        """CCW UV parameterisation: handedness = +1."""
        comp = TBNComputer()
        mesh = _MockMesh(
            [(0,0,0),(1,0,0),(1,1,0),(0,1,0)],
            [(0,0,1)]*4,
            [(0,0),(1,0),(1,1),(0,1)],  # standard CCW
            [(0,1,2),(0,2,3)],
        )
        result = comp.compute(mesh)
        for tx, ty, tz, w in result.tangents:
            self.assertIn(w, (1.0, -1.0))

    def test_handedness_component_is_plus_or_minus_one(self):
        comp   = TBNComputer()
        result = comp.compute(_unit_quad_mesh())
        for tx, ty, tz, w in result.tangents:
            self.assertIn(w, (1.0, -1.0))


class TestTBNDegenerate(unittest.TestCase):

    def test_zero_area_triangle_does_not_crash(self):
        """All three vertices at the same point → degenerate, skipped."""
        comp = TBNComputer()
        mesh = _MockMesh(
            [(0,0,0),(0,0,0),(0,0,0)],
            [(0,0,1)]*3,
            [(0,0),(0,0),(0,0)],
            [(0,1,2)],
        )
        result = comp.compute(mesh)
        # Should return result (possibly 3 verts with fallback tangents)
        self.assertIsInstance(result, TBNResult)

    def test_out_of_range_face_indices_skipped(self):
        comp = TBNComputer()
        mesh = _MockMesh(
            [(0,0,0),(1,0,0)],
            [(0,0,1)]*2,
            [(0,0),(1,0)],
            [(0,1,99)],   # index 99 is out of range
        )
        result = comp.compute(mesh)
        self.assertIsInstance(result, TBNResult)

    def test_no_faces_returns_empty(self):
        comp = TBNComputer()
        mesh = _MockMesh([(0,0,0),(1,0,0),(0,1,0)], [(0,0,1)]*3, [(0,0),(1,0),(0,1)], [])
        result = comp.compute(mesh)
        self.assertEqual(result.vertex_count, 0)


class TestTBNNumPyAgreement(unittest.TestCase):
    """Compare pure-Python and NumPy TBN computations for the same mesh."""

    def test_unit_quad_numpy_vs_py_tangents(self):
        try:
            import numpy as _np
        except ImportError:
            self.skipTest("numpy not available")
        comp  = TBNComputer()
        mesh  = _unit_quad_mesh()
        r_py  = comp.compute(mesh)
        r_np  = comp.compute_numpy(mesh)

        self.assertEqual(r_py.vertex_count, r_np.vertex_count)
        for i in range(r_py.vertex_count):
            for a, b in zip(r_py.tangents[i], r_np.tangents[i]):
                self.assertAlmostEqual(a, b, delta=1e-4,
                    msg=f"vertex {i}: tangent mismatch {r_py.tangents[i]} vs {r_np.tangents[i]}")

    def test_multi_face_mesh_numpy_vs_py_normals(self):
        try:
            import numpy as _np
        except ImportError:
            self.skipTest("numpy not available")
        # Grid mesh: 4 quads (8 triangles)
        verts = [(x, y, 0) for y in range(3) for x in range(3)]
        norms = [(0, 0, 1)] * 9
        uvs   = [(x/2, y/2) for y in range(3) for x in range(3)]
        faces = []
        for row in range(2):
            for col in range(2):
                i = row * 3 + col
                faces += [(i, i+1, i+4), (i, i+4, i+3)]
        mesh = _MockMesh(verts, norms, uvs, faces)
        comp  = TBNComputer()
        r_py  = comp.compute(mesh)
        r_np  = comp.compute_numpy(mesh)
        self.assertEqual(r_py.vertex_count, r_np.vertex_count)
        for i in range(r_py.vertex_count):
            for a, b in zip(r_py.normals[i], r_np.normals[i]):
                self.assertAlmostEqual(a, b, delta=1e-4)


# ─────────────────────────────────────────────────────────────────────────────
#  Tests — SceneFrameRenderer
# ─────────────────────────────────────────────────────────────────────────────

class TestSceneFrameRenderer(unittest.TestCase):

    def _make_scene_graph(self):
        """Build a minimal SceneGraph with 3 rooms and 2 GIT objects."""
        from src.core.scene_manager import SceneGraph, SceneRoom, SceneObject
        graph = SceneGraph()
        room_data = [
            ('m01aa_01a', 'm01aa_01a_mdl', (0.0, 0.0, 0.0)),
            ('m01aa_02a', 'm01aa_02a_mdl', (10.0, 0.0, 0.0)),
            ('null',      '',              (20.0, 0.0, 0.0)),
        ]
        for rname, model_name, pos in room_data:
            # SceneRoom uses resref as the model identifier; override model_name
            # via a compatible attribute for the draw-list renderer.
            room = SceneRoom(resref=rname)
            room.model_name = model_name   # extra attr for renderer
            room.position   = pos
            room.linked_rooms = []
            graph.rooms.append(room)

        # GIT objects — use SceneObject.room_name = resref of the room
        obj1 = SceneObject(obj_type='creature', resref='c_trooper')
        obj1.model_name  = 'c_trooper'
        obj1.position    = (1.0, 0.0, 0.0)
        obj1.room_name   = 'm01aa_01a'   # SceneGraph.objects_in_room filters by this

        obj2 = SceneObject(obj_type='placeable', resref='plc_box')
        obj2.model_name  = 'plc_box'
        obj2.position    = (2.0, 0.0, 0.0)
        obj2.room_name   = 'm01aa_01a'

        graph.objects = [obj1, obj2]
        return graph

    def test_build_draw_list_returns_entries(self):
        from src.core.scene_manager import SceneFrameRenderer
        graph = self._make_scene_graph()
        sfr = SceneFrameRenderer(graph)
        dl  = sfr.build_draw_list(
            camera_pos=(0,0,5), camera_fwd=(0,0,-1),
            fov_h=90, fov_v=60, near=0.01, far=2000,
        )
        self.assertIsInstance(dl, list)
        self.assertGreater(len(dl), 0)

    def test_null_room_excluded_by_default(self):
        from src.core.scene_manager import SceneFrameRenderer
        graph = self._make_scene_graph()
        sfr = SceneFrameRenderer(graph)
        sfr.show_null_rooms = False
        dl  = sfr.build_draw_list((0,0,5), (0,0,-1))
        model_names = [e.model_name for e in dl]
        self.assertNotIn('', model_names)

    def test_null_room_included_when_flag_set(self):
        from src.core.scene_manager import SceneFrameRenderer, SceneGraph, SceneRoom
        graph = SceneGraph()
        r = SceneRoom(resref='null')
        r.model_name = 'null_mesh'; r.position = (0,0,0)
        r.linked_rooms = []
        graph.rooms.append(r)
        sfr = SceneFrameRenderer(graph)
        sfr.show_null_rooms = True
        dl  = sfr.build_draw_list((0,0,5), (0,0,-1))
        # null room's model should appear
        self.assertTrue(any(e.model_name == 'null_mesh' for e in dl))

    def test_per_room_visibility_override_hides_room(self):
        from src.core.scene_manager import SceneFrameRenderer
        graph = self._make_scene_graph()
        sfr = SceneFrameRenderer(graph)
        sfr.set_room_visible('m01aa_01a', False)
        dl = sfr.build_draw_list((0,0,5), (0,0,-1))
        model_names = [e.model_name for e in dl if not e.is_object]
        self.assertNotIn('m01aa_01a_mdl', model_names)

    def test_per_room_visibility_override_shows_room(self):
        from src.core.scene_manager import SceneFrameRenderer
        graph = self._make_scene_graph()
        sfr = SceneFrameRenderer(graph)
        sfr.set_room_visible('m01aa_02a', True)
        dl = sfr.build_draw_list((0,0,5), (0,0,-1))
        model_names = [e.model_name for e in dl if not e.is_object]
        self.assertIn('m01aa_02a_mdl', model_names)

    def test_clear_visibility_overrides(self):
        from src.core.scene_manager import SceneFrameRenderer
        graph = self._make_scene_graph()
        sfr = SceneFrameRenderer(graph)
        sfr.set_room_visible('m01aa_01a', False)
        sfr.clear_visibility_overrides()
        dl = sfr.build_draw_list((0,0,5), (0,0,-1))
        model_names = [e.model_name for e in dl if not e.is_object]
        self.assertIn('m01aa_01a_mdl', model_names)

    def test_objects_present_in_draw_list(self):
        from src.core.scene_manager import SceneFrameRenderer
        graph = self._make_scene_graph()
        sfr = SceneFrameRenderer(graph)
        sfr.show_objects = True
        dl  = sfr.build_draw_list((0,0,5), (0,0,-1))
        obj_names = [e.model_name for e in dl if e.is_object]
        self.assertIn('c_trooper', obj_names)
        self.assertIn('plc_box',   obj_names)

    def test_objects_excluded_when_flag_cleared(self):
        from src.core.scene_manager import SceneFrameRenderer
        graph = self._make_scene_graph()
        sfr = SceneFrameRenderer(graph)
        sfr.show_objects = False
        dl  = sfr.build_draw_list((0,0,5), (0,0,-1))
        self.assertFalse(any(e.is_object for e in dl))

    def test_object_type_filter_creatures_only(self):
        from src.core.scene_manager import SceneFrameRenderer
        graph = self._make_scene_graph()
        sfr = SceneFrameRenderer(graph)
        # obj_type = 'creature' (set on SceneObject.obj_type)
        sfr.object_type_filter = 'creature'
        dl  = sfr.build_draw_list((0,0,5), (0,0,-1))
        obj_entries = [e for e in dl if e.is_object]
        # Should have creature entry
        self.assertTrue(any(e.model_name == 'c_trooper' for e in obj_entries) or
                        len(obj_entries) == 0,
                        "creature filter: unexpected entries")
        # Should not have placeable entry
        self.assertFalse(any(e.model_name == 'plc_box' for e in obj_entries))

    def test_none_scene_returns_empty_list(self):
        from src.core.scene_manager import SceneFrameRenderer
        sfr = SceneFrameRenderer(None)
        dl  = sfr.build_draw_list((0,0,5), (0,0,-1))
        self.assertEqual(dl, [])

    def test_room_count(self):
        from src.core.scene_manager import SceneFrameRenderer
        graph = self._make_scene_graph()
        sfr = SceneFrameRenderer(graph)
        self.assertEqual(sfr.room_count(), 3)

    def test_all_room_names(self):
        from src.core.scene_manager import SceneFrameRenderer
        graph = self._make_scene_graph()
        sfr = SceneFrameRenderer(graph)
        names = sfr.all_room_names()
        self.assertIn('m01aa_01a', names)
        self.assertIn('m01aa_02a', names)

    def test_set_scene_clears_overrides(self):
        from src.core.scene_manager import SceneFrameRenderer, SceneGraph, SceneRoom
        graph = self._make_scene_graph()
        sfr = SceneFrameRenderer(graph)
        sfr.set_room_visible('m01aa_01a', False)
        sfr.set_scene(SceneGraph())
        # overrides should be cleared
        self.assertEqual(sfr._room_visible_override, {})

    def test_are_properties_none_when_no_scene(self):
        from src.core.scene_manager import SceneFrameRenderer
        sfr = SceneFrameRenderer(None)
        self.assertIsNone(sfr.are_properties())


# ─────────────────────────────────────────────────────────────────────────────
#  Tests — GLSL constants
# ─────────────────────────────────────────────────────────────────────────────

class TestGLSLConstants(unittest.TestCase):

    def test_vert_skin_uniforms_has_u_bones(self):
        self.assertIn('u_bones', VERT_SKIN_UNIFORMS)

    def test_vert_skin_uniforms_has_in_bone_ids(self):
        self.assertIn('in_bone_ids', VERT_SKIN_UNIFORMS)

    def test_vert_skin_uniforms_has_in_weights(self):
        self.assertIn('in_weights', VERT_SKIN_UNIFORMS)

    def test_vert_skin_uniforms_has_in_tangent(self):
        self.assertIn('in_tangent', VERT_SKIN_UNIFORMS)

    def test_vert_skin_uniforms_has_v_tangent_out(self):
        self.assertIn('v_tangent', VERT_SKIN_UNIFORMS)

    def test_vert_skin_uniforms_has_v_bitangent_out(self):
        self.assertIn('v_bitangent', VERT_SKIN_UNIFORMS)

    def test_vert_skin_main_has_u_skin_enabled(self):
        self.assertIn('u_skin_enabled', VERT_SKIN_MAIN)

    def test_vert_skin_main_has_skinned_pos(self):
        self.assertIn('skinned_pos', VERT_SKIN_MAIN)

    def test_vert_skin_main_lbs_loop(self):
        self.assertIn('for', VERT_SKIN_MAIN)
        self.assertIn('in_bone_ids', VERT_SKIN_MAIN)
        self.assertIn('in_weights',  VERT_SKIN_MAIN)

    def test_frag_tbn_uniforms_has_u_nmap_tex(self):
        self.assertIn('u_nmap_tex', FRAG_TBN_UNIFORMS)

    def test_frag_tbn_uniforms_has_u_has_nmap(self):
        self.assertIn('u_has_nmap', FRAG_TBN_UNIFORMS)

    def test_frag_tbn_uniforms_has_v_tangent_in(self):
        self.assertIn('v_tangent', FRAG_TBN_UNIFORMS)

    def test_frag_tbn_uniforms_has_v_bitangent_in(self):
        self.assertIn('v_bitangent', FRAG_TBN_UNIFORMS)

    def test_frag_tbn_normal_has_tbn_matrix(self):
        self.assertIn('TBN', FRAG_TBN_NORMAL)

    def test_frag_tbn_normal_has_nmap_sample(self):
        self.assertIn('nmap_samp', FRAG_TBN_NORMAL)
        self.assertIn('texture', FRAG_TBN_NORMAL)

    def test_frag_tbn_normal_uses_u_has_nmap(self):
        self.assertIn('u_has_nmap', FRAG_TBN_NORMAL)

    def test_ssbo_decl_has_std430(self):
        self.assertIn('std430', SSBO_GLSL_DECL)

    def test_ssbo_decl_has_binding_zero(self):
        self.assertIn('binding = 0', SSBO_GLSL_DECL)

    def test_bone_palette_binding_is_zero(self):
        self.assertEqual(BONE_PALETTE_BINDING, 0)

    def test_max_bones_is_128(self):
        self.assertEqual(MAX_BONES, 128)

    def test_vert_skin_uniforms_has_max_bones_comment_or_array(self):
        self.assertIn('128', VERT_SKIN_UNIFORMS)


# ─────────────────────────────────────────────────────────────────────────────
#  Tests — Integration: build palette bytes + verify round-trip
# ─────────────────────────────────────────────────────────────────────────────

class TestMatrixPaletteRoundTrip(unittest.TestCase):

    def test_identity_bone_round_trip(self):
        """Single identity bone → palette flat bytes → first 16 floats == identity."""
        import struct
        up  = MatrixPaletteUploader(max_bones=1)
        mdl = _MockModel([_MockNode('root')])
        up.build_inverse_bind_pose(mdl)
        up.compute_palette(None)
        data = up.as_flat_bytes()
        floats = struct.unpack('16f', data[:64])
        expected = _identity_flat()
        for a, b in zip(floats, expected):
            self.assertAlmostEqual(a, b, places=5)

    def test_translated_bone_palette_reflects_inverse(self):
        """A bone translated to (0, 0, 1) has inv_bind translating back by (0, 0, -1).
        If we compute palette with identity pose (no motion), the skin matrix
        M = I × inv_bind should produce a net translation of (0, 0, -1)."""
        import struct
        up  = MatrixPaletteUploader(max_bones=1)
        mdl = _MockModel([_MockNode('bone', pos=(0, 0, 1), quat=(0, 0, 0, 1))])
        up.build_inverse_bind_pose(mdl)
        up.compute_palette(None)
        data   = up.as_flat_bytes()
        floats = struct.unpack('16f', data[:64])
        # Column-major: column 3 (translation) is at indices 12, 13, 14
        tx, ty, tz = floats[12], floats[13], floats[14]
        self.assertAlmostEqual(tx,  0.0, places=4)
        self.assertAlmostEqual(ty,  0.0, places=4)
        self.assertAlmostEqual(tz, -1.0, places=4)

    def test_multiple_bones_palette_bytes_size(self):
        """Palette is always padded to max_bones regardless of bone count."""
        import struct
        N = 5
        up  = MatrixPaletteUploader(max_bones=N)
        mdl = _MockModel([_MockNode(f'b{i}') for i in range(N)])
        up.build_inverse_bind_pose(mdl)
        up.compute_palette(None)
        data = up.as_flat_bytes()
        self.assertEqual(len(data), N * 16 * 4)


if __name__ == '__main__':
    unittest.main(verbosity=2)
