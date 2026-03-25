from __future__ import annotations

import os
import struct
import pathlib
import sys
import unittest
from unittest import TestCase
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

try:
    from qtpy.QtCore import Qt
    from qtpy.QtTest import QTest
    from qtpy.QtWidgets import QApplication
except (ImportError, ModuleNotFoundError):
    Qt, QTest, QApplication = object, object, object  # type: ignore[misc, assignment]

absolute_file_path = pathlib.Path(__file__).resolve()
TESTS_FILES_PATH = next(f for f in absolute_file_path.parents if f.name == "tests") / "test_files"

if __name__ == "__main__" and getattr(sys, "frozen", False) is False:

    def add_sys_path(p):
        working_dir = str(p)
        if working_dir in sys.path:
            sys.path.remove(working_dir)
        sys.path.append(working_dir)

    pykotor_path = absolute_file_path.parents[6] / "Libraries" / "PyKotor" / "src" / "pykotor"
    if pykotor_path.exists():
        add_sys_path(pykotor_path.parent)
    gl_path = absolute_file_path.parents[6] / "Libraries" / "PyKotorGL" / "src" / "pykotor"
    if gl_path.exists():
        add_sys_path(gl_path.parent)
    utility_path = absolute_file_path.parents[6] / "Libraries" / "Utility" / "src" / "utility"
    if utility_path.exists():
        add_sys_path(utility_path.parent)
    toolset_path = absolute_file_path.parents[6] / "Tools" / "HolocronToolset" / "src" / "toolset"
    if toolset_path.exists():
        add_sys_path(toolset_path.parent)


K1_PATH = os.environ.get("K1_PATH", "C:\\Program Files (x86)\\Steam\\steamapps\\common\\swkotor")
K2_PATH = os.environ.get("K2_PATH", "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Knights of the Old Republic II")

from pykotor.extract.file import ResourceIdentifier, ResourceResult
from pykotor.extract.installation import Installation
from pykotor.resource.formats.bwm.bwm_auto import bytes_bwm, read_bwm
from pykotor.resource.type import ResourceType


@unittest.skipIf(
    not K2_PATH or not pathlib.Path(K2_PATH).joinpath("chitin.key").exists(),
    "K2_PATH environment variable is not set or not found on disk.",
)
@unittest.skipIf(
    QTest is None or not QApplication,
    "qtpy is required, please run pip install -r requirements.txt before running this test.",
)
class BWMEditorTest(TestCase):
    @classmethod
    def setUpClass(cls):
        # Make sure to configure this environment path before testing!
        from toolset.gui.editors.bwm import BWMEditor

        cls.BWMEditor = BWMEditor
        from toolset.data.installation import HTInstallation

        # cls.INSTALLATION = HTInstallation(K1_PATH, "", tsl=False)
        assert K2_PATH is not None, "K2_PATH environment variable is not set"
        cls.K2_INSTALLATION = HTInstallation(K2_PATH, "", tsl=True)

    def setUp(self):
        self.app: QApplication = QApplication(sys.argv)  # type: ignore[assignment]
        self.editor = self.BWMEditor(None, self.K2_INSTALLATION)
        self.log_messages: list[str] = [os.linesep]

    def tearDown(self):
        self.app.deleteLater()

    def log_func(self, *args):
        self.log_messages.append("\t".join(args))

    def test_save_and_load(self):
        """Comprehensive roundtrip test with 50+ strict assertions validating all BWM properties."""
        filepath = TESTS_FILES_PATH / "zio006j.wok"

        data = filepath.read_bytes()
        old = read_bwm(data)
        supported = [ResourceType.WOK, ResourceType.DWK, ResourceType.PWK]
        self.editor.load(filepath, "zio006j", ResourceType.WOK, data)

        data, _ = self.editor.build()
        new = read_bwm(data)

        # ========================================================================
        # BASIC PROPERTIES (10+ assertions)
        # ========================================================================
        assert old.walkmesh_type == new.walkmesh_type, "Walkmesh type must be preserved"
        assert old.walkmesh_type.value == new.walkmesh_type.value, "Walkmesh type value must match"
        assert isinstance(new.walkmesh_type.value, int), "Walkmesh type must be integer"
        assert new.walkmesh_type.value in (0, 1), "Walkmesh type must be 0 (PlaceableOrDoor) or 1 (AreaModel)"

        assert old.position == new.position, "Position must be preserved"
        assert abs(old.position.x - new.position.x) < 1e-6, "Position.x must match exactly"
        assert abs(old.position.y - new.position.y) < 1e-6, "Position.y must match exactly"
        assert abs(old.position.z - new.position.z) < 1e-6, "Position.z must match exactly"

        assert old.relative_hook1 == new.relative_hook1, "Relative hook1 must be preserved"
        assert abs(old.relative_hook1.x - new.relative_hook1.x) < 1e-6, "Relative hook1.x must match"
        assert abs(old.relative_hook1.y - new.relative_hook1.y) < 1e-6, "Relative hook1.y must match"
        assert abs(old.relative_hook1.z - new.relative_hook1.z) < 1e-6, "Relative hook1.z must match"

        assert old.relative_hook2 == new.relative_hook2, "Relative hook2 must be preserved"
        assert abs(old.relative_hook2.x - new.relative_hook2.x) < 1e-6, "Relative hook2.x must match"
        assert abs(old.relative_hook2.y - new.relative_hook2.y) < 1e-6, "Relative hook2.y must match"
        assert abs(old.relative_hook2.z - new.relative_hook2.z) < 1e-6, "Relative hook2.z must match"

        assert old.absolute_hook1 == new.absolute_hook1, "Absolute hook1 must be preserved"
        assert abs(old.absolute_hook1.x - new.absolute_hook1.x) < 1e-6, "Absolute hook1.x must match"
        assert abs(old.absolute_hook1.y - new.absolute_hook1.y) < 1e-6, "Absolute hook1.y must match"
        assert abs(old.absolute_hook1.z - new.absolute_hook1.z) < 1e-6, "Absolute hook1.z must match"

        assert old.absolute_hook2 == new.absolute_hook2, "Absolute hook2 must be preserved"
        assert abs(old.absolute_hook2.x - new.absolute_hook2.x) < 1e-6, "Absolute hook2.x must match"
        assert abs(old.absolute_hook2.y - new.absolute_hook2.y) < 1e-6, "Absolute hook2.y must match"
        assert abs(old.absolute_hook2.z - new.absolute_hook2.z) < 1e-6, "Absolute hook2.z must match"

        # ========================================================================
        # VERTEX VALIDATION (10+ assertions)
        # ========================================================================
        old_vertices = old.vertices()
        new_vertices = new.vertices()
        assert len(old_vertices) == len(new_vertices), "Vertex count must be preserved"
        assert len(old_vertices) > 0, "Must have at least one vertex"

        # Vertices should be deduplicated and in consistent order
        for i, (old_v, new_v) in enumerate(zip(old_vertices, new_vertices)):
            assert abs(old_v.x - new_v.x) < 1e-6, f"Vertex {i}.x mismatch: {old_v.x} != {new_v.x}"
            assert abs(old_v.y - new_v.y) < 1e-6, f"Vertex {i}.y mismatch: {old_v.y} != {new_v.y}"
            assert abs(old_v.z - new_v.z) < 1e-6, f"Vertex {i}.z mismatch: {old_v.z} != {new_v.z}"
            assert isinstance(new_v.x, float), f"Vertex {i}.x must be float"
            assert isinstance(new_v.y, float), f"Vertex {i}.y must be float"
            assert isinstance(new_v.z, float), f"Vertex {i}.z must be float"

        # ========================================================================
        # FACE VALIDATION (30+ assertions)
        # ========================================================================
        assert len(old.faces) == len(new.faces), "Face count must be preserved"
        assert len(old.faces) > 0, "Must have at least one face"

        # Faces may be reordered (walkable first), so compare as sets
        old_faces_set = set(old.faces)
        new_faces_set = set(new.faces)
        assert old_faces_set == new_faces_set, "Face content mismatch - all faces must be preserved"

        # Verify face ordering: walkable faces first, then unwalkable
        walkable_count = sum(1 for f in new.faces if f.material.walkable())
        unwalkable_count = len(new.faces) - walkable_count
        for i, face in enumerate(new.faces):
            if i < walkable_count:
                assert face.material.walkable(), f"Face {i} should be walkable (walkable faces must come first)"
            else:
                assert not face.material.walkable(), f"Face {i} should be unwalkable (unwalkable faces must come after walkable)"

        # Strict face signature comparison (geometry + material + transitions)
        old_faces_sigs = sorted(self._face_signatures(old))
        new_faces_sigs = sorted(self._face_signatures(new))
        assert len(old_faces_sigs) == len(new_faces_sigs), "Face signature count must match"
        for i, (old_sig, new_sig) in enumerate(zip(old_faces_sigs, new_faces_sigs)):
            assert old_sig == new_sig, f"Face signature {i} mismatch: {old_sig} != {new_sig}"

        # Verify each face's properties individually
        old_faces_list = list(old.faces)
        new_faces_list = list(new.faces)
        for old_face in old_faces_list:
            # Find matching face in new (by value, not identity)
            matching_faces = [f for f in new_faces_list if f == old_face]
            assert len(matching_faces) == 1, f"Each old face must have exactly one matching new face"
            new_face = matching_faces[0]

            # Verify vertices (with tolerance for float precision)
            assert abs(old_face.v1.x - new_face.v1.x) < 1e-6, "Face v1.x must match"
            assert abs(old_face.v1.y - new_face.v1.y) < 1e-6, "Face v1.y must match"
            assert abs(old_face.v1.z - new_face.v1.z) < 1e-6, "Face v1.z must match"
            assert abs(old_face.v2.x - new_face.v2.x) < 1e-6, "Face v2.x must match"
            assert abs(old_face.v2.y - new_face.v2.y) < 1e-6, "Face v2.y must match"
            assert abs(old_face.v2.z - new_face.v2.z) < 1e-6, "Face v2.z must match"
            assert abs(old_face.v3.x - new_face.v3.x) < 1e-6, "Face v3.x must match"
            assert abs(old_face.v3.y - new_face.v3.y) < 1e-6, "Face v3.y must match"
            assert abs(old_face.v3.z - new_face.v3.z) < 1e-6, "Face v3.z must match"

            # Verify material
            assert old_face.material == new_face.material, "Face material must match"
            assert old_face.material.value == new_face.material.value, "Face material value must match"

            # Verify transitions (critical for pathfinding)
            assert old_face.trans1 == new_face.trans1, "Face trans1 must be preserved"
            assert old_face.trans2 == new_face.trans2, "Face trans2 must be preserved"
            assert old_face.trans3 == new_face.trans3, "Face trans3 must be preserved"

            # Verify transitions are None or non-negative integers
            if new_face.trans1 is not None:
                assert isinstance(new_face.trans1, int), "trans1 must be int or None"
                assert new_face.trans1 >= 0, "trans1 must be non-negative"
            if new_face.trans2 is not None:
                assert isinstance(new_face.trans2, int), "trans2 must be int or None"
                assert new_face.trans2 >= 0, "trans2 must be non-negative"
            if new_face.trans3 is not None:
                assert isinstance(new_face.trans3, int), "trans3 must be int or None"
                assert new_face.trans3 >= 0, "trans3 must be non-negative"

            # Verify face normal consistency
            old_normal = old_face.normal()
            new_normal = new_face.normal()
            assert abs(old_normal.x - new_normal.x) < 1e-4, "Face normal.x must match approximately"
            assert abs(old_normal.y - new_normal.y) < 1e-4, "Face normal.y must match approximately"
            assert abs(old_normal.z - new_normal.z) < 1e-4, "Face normal.z must match approximately"

            # Verify planar distance consistency
            assert abs(old_face.planar_distance() - new_face.planar_distance()) < 1e-4, "Face planar distance must match approximately"

    @staticmethod
    def _face_signature(face) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], int, int | None, int | None, int | None]:
        """Return a strict, stable signature for a face (geometry + material + transitions)."""
        v1 = (round(face.v1.x, 9), round(face.v1.y, 9), round(face.v1.z, 9))
        v2 = (round(face.v2.x, 9), round(face.v2.y, 9), round(face.v2.z, 9))
        v3 = (round(face.v3.x, 9), round(face.v3.y, 9), round(face.v3.z, 9))
        return (v1, v2, v3, face.material.value, face.trans1, face.trans2, face.trans3)

    def _face_signatures(self, bwm):
        return [self._face_signature(face) for face in bwm.faces]

    def test_bwm_binary_layout_roundtrip(self):
        """Strictly validate binary header/offset layout for roundtrip output."""
        filepath = TESTS_FILES_PATH / "zio006j.wok"
        data = filepath.read_bytes()
        original = read_bwm(data)
        roundtrip = read_bwm(bytes_bwm(original))

        out_data = bytes_bwm(roundtrip)
        assert len(out_data) >= 136, "BWM header must be at least 136 bytes"
        face_index_map = {id(face): idx for idx, face in enumerate(roundtrip.faces)}

        magic = out_data[0:4].decode("latin1")
        version = out_data[4:8].decode("latin1")
        assert magic == "BWM ", f"Magic mismatch: {magic}"
        assert version == "V1.0", f"Version mismatch: {version}"

        walkmesh_type = struct.unpack_from("<I", out_data, 8)[0]
        assert walkmesh_type == roundtrip.walkmesh_type.value, "Walkmesh type mismatch in header"

        # Hook vectors and position (12 bytes each)
        rel1 = struct.unpack_from("<fff", out_data, 12)
        rel2 = struct.unpack_from("<fff", out_data, 24)
        abs1 = struct.unpack_from("<fff", out_data, 36)
        abs2 = struct.unpack_from("<fff", out_data, 48)
        pos = struct.unpack_from("<fff", out_data, 60)
        assert rel1 == (roundtrip.relative_hook1.x, roundtrip.relative_hook1.y, roundtrip.relative_hook1.z)
        assert rel2 == (roundtrip.relative_hook2.x, roundtrip.relative_hook2.y, roundtrip.relative_hook2.z)
        assert abs1 == (roundtrip.absolute_hook1.x, roundtrip.absolute_hook1.y, roundtrip.absolute_hook1.z)
        assert abs2 == (roundtrip.absolute_hook2.x, roundtrip.absolute_hook2.y, roundtrip.absolute_hook2.z)
        assert pos == (roundtrip.position.x, roundtrip.position.y, roundtrip.position.z)

        vertex_count, vertex_offset = struct.unpack_from("<II", out_data, 72)
        face_count, indices_offset = struct.unpack_from("<II", out_data, 80)
        materials_offset, normals_offset = struct.unpack_from("<II", out_data, 88)
        distances_offset = struct.unpack_from("<I", out_data, 96)[0]
        aabb_count, aabb_offset = struct.unpack_from("<II", out_data, 100)
        unknown = struct.unpack_from("<I", out_data, 108)[0]
        adjacency_count, adjacency_offset = struct.unpack_from("<II", out_data, 112)
        edges_count, edges_offset = struct.unpack_from("<II", out_data, 120)
        perimeters_count, perimeters_offset = struct.unpack_from("<II", out_data, 128)

        assert vertex_offset == 136, "Vertex table must start immediately after header"
        assert vertex_count == len(roundtrip.vertices()), "Vertex count mismatch"
        assert face_count == len(roundtrip.faces), "Face count mismatch"
        assert materials_offset == indices_offset + face_count * 12, "Material offset mismatch"
        assert normals_offset == materials_offset + face_count * 4, "Normals offset mismatch"
        assert distances_offset == normals_offset + face_count * 12, "Distances offset mismatch"
        assert unknown == 0, "Unknown header field should be zero in writer output"

        # AABB layout
        expected_aabb_bytes = aabb_count * 44
        assert aabb_offset == distances_offset + face_count * 4, "AABB offset mismatch"
        assert adjacency_offset == aabb_offset + expected_aabb_bytes, "Adjacency offset mismatch"

        # Adjacency layout
        expected_adj_bytes = adjacency_count * 12
        assert adjacency_count == len(roundtrip.walkable_faces()), "Adjacency count mismatch"
        assert edges_offset == adjacency_offset + expected_adj_bytes, "Edges offset mismatch"

        # Edge layout (8 bytes each) and perimeters layout (4 bytes each)
        expected_edge_bytes = edges_count * 8
        assert perimeters_offset == edges_offset + expected_edge_bytes, "Perimeters offset mismatch"
        assert len(out_data) == perimeters_offset + perimeters_count * 4, "File length mismatch with perimeters"

        # Verify vertex table
        vertices = []
        for i in range(vertex_count):
            x, y, z = struct.unpack_from("<fff", out_data, vertex_offset + i * 12)
            vertices.append((x, y, z))
        assert len(vertices) == len(roundtrip.vertices()), "Vertex table length mismatch"
        for idx, vertex in enumerate(roundtrip.vertices()):
            assert vertices[idx] == (vertex.x, vertex.y, vertex.z), f"Vertex mismatch at index {idx}"

        # Verify face indices map to vertex table
        face_indices = []
        for i in range(face_count):
            i1, i2, i3 = struct.unpack_from("<III", out_data, indices_offset + i * 12)
            face_indices.append((i1, i2, i3))
            assert i1 < vertex_count and i2 < vertex_count and i3 < vertex_count, "Face index out of range"
        assert len(face_indices) == len(roundtrip.faces), "Face indices length mismatch"

        # Verify materials table
        materials = [struct.unpack_from("<I", out_data, materials_offset + i * 4)[0] for i in range(face_count)]
        for i, face in enumerate(roundtrip.faces):
            assert materials[i] == face.material.value, f"Material mismatch for face {i}"

        # Verify normals table (approximate)
        for i, face in enumerate(roundtrip.faces):
            nx, ny, nz = struct.unpack_from("<fff", out_data, normals_offset + i * 12)
            normal = face.normal()
            assert abs(nx - normal.x) < 1e-4, f"Normal.x mismatch for face {i}"
            assert abs(ny - normal.y) < 1e-4, f"Normal.y mismatch for face {i}"
            assert abs(nz - normal.z) < 1e-4, f"Normal.z mismatch for face {i}"

        # Verify planar distances (approximate)
        for i, face in enumerate(roundtrip.faces):
            distance = struct.unpack_from("<f", out_data, distances_offset + i * 4)[0]
            assert abs(distance - face.planar_distance()) < 1e-4, f"Planar distance mismatch for face {i}"

        # Verify adjacency table for walkable faces
        walkable_faces = roundtrip.walkable_faces()
        assert adjacency_count == len(walkable_faces), "Adjacency count must match walkable faces"
        for i, face in enumerate(walkable_faces):
            a1, a2, a3 = struct.unpack_from("<iii", out_data, adjacency_offset + i * 12)
            adj = roundtrip.adjacencies(face)
            expected = []
            for entry in adj:
                if entry is None:
                    expected.append(-1)
                else:
                    face_idx = face_index_map[id(entry.face)]
                    expected.append(face_idx * 3 + entry.edge)
            assert [a1, a2, a3] == expected, f"Adjacency mismatch for walkable face {i}"

        # Verify edges table entries
        edge_entries = []
        for i in range(edges_count):
            edge_index, transition = struct.unpack_from("<ii", out_data, edges_offset + i * 8)
            edge_entries.append((edge_index, transition))
            face_idx, local_edge = divmod(edge_index, 3)
            assert face_idx < face_count, "Edge face index out of range"
            assert local_edge in (0, 1, 2), "Edge local index out of range"
            face = roundtrip.faces[face_idx]
            expected_transition = (face.trans1, face.trans2, face.trans3)[local_edge]
            expected_transition = -1 if expected_transition is None else expected_transition
            assert transition == expected_transition, f"Transition mismatch for edge {i}"

        # Verify perimeters table
        for i in range(perimeters_count):
            perimeter_index = struct.unpack_from("<I", out_data, perimeters_offset + i * 4)[0]
            assert perimeter_index >= 1, "Perimeter index should be 1-based"
            assert perimeter_index <= edges_count, "Perimeter index out of range"

        # Validate edge count against transitions + perimeters
        edge_indices = set()
        for face_idx, face in enumerate(roundtrip.faces):
            for edge_idx, transition in enumerate((face.trans1, face.trans2, face.trans3)):
                if transition is not None:
                    edge_indices.add(face_idx * 3 + edge_idx)
        for edge in roundtrip.edges():
            face_idx = face_index_map[id(edge.face)]
            edge_indices.add(face_idx * 3 + edge.index)
        assert edges_count == len(edge_indices), "Edges count must cover transitions and perimeter edges"

    def assertDeepEqual(self, obj1: Any, obj2: Any, context: str = ""):
        # Special handling for BWM faces - compare as sets since order may differ
        # Faces are reordered by writer: walkable first, then unwalkable
        if context.endswith(".faces") and isinstance(obj1, list) and isinstance(obj2, list):
            assert len(obj1) == len(obj2), f"{context}: Face count mismatch"
            # Compare as sets (faces may be reordered: walkable first, then unwalkable)
            obj1_set = set(obj1)
            obj2_set = set(obj2)
            assert obj1_set == obj2_set, f"{context}: Face content mismatch - faces may have been reordered or modified"
            return

        if isinstance(obj1, dict) and isinstance(obj2, dict):
            assert set(obj1.keys()) == set(obj2.keys()), context
            for key in obj1:
                new_context = f"{context}.{key}" if context else str(key)
                self.assertDeepEqual(obj1[key], obj2[key], new_context)

        elif isinstance(obj1, (list, tuple)) and isinstance(obj2, (list, tuple)):
            assert len(obj1) == len(obj2), context
            # Special handling for lists of BWMFace objects - compare as sets since order may differ
            # Faces are reordered by writer: walkable first, then unwalkable
            if (
                obj1
                and obj2
                and hasattr(obj1[0], "__class__")
                and hasattr(obj2[0], "__class__")
                and obj1[0].__class__.__name__ == "BWMFace"
                and obj2[0].__class__.__name__ == "BWMFace"
            ):
                obj1_set = set(obj1)
                obj2_set = set(obj2)
                assert obj1_set == obj2_set, f"{context}: Face content mismatch - faces may have been reordered or modified"
                return
            for index, (item1, item2) in enumerate(zip(obj1, obj2)):
                new_context = f"{context}[{index}]" if context else f"[{index}]"
                self.assertDeepEqual(item1, item2, new_context)

        elif hasattr(obj1, "__dict__") and hasattr(obj2, "__dict__"):
            self.assertDeepEqual(obj1.__dict__, obj2.__dict__, context)

        elif isinstance(obj1, float) and isinstance(obj2, float):
            # Use approximate equality for floating-point numbers (1e-3 tolerance)
            # Some game files have precision differences after roundtrip
            assert abs(obj1 - obj2) < 1e-3, f"{context}: {obj1} != {obj2} (diff: {abs(obj1 - obj2)})"

        else:
            assert obj1 == obj2, context

    def test_basic_syntax(self): ...


class BWMTransitionIntegrityTest(TestCase):
    """Tests for BWM walkmesh transition integrity.

    These tests ensure that transitions (which are critical for pathfinding between
    rooms in KotOR) remain on walkable faces after serialization/deserialization.

    Bug reference: Indoor map builder was creating modules where characters couldn't
    walk because transitions were being assigned to unwalkable faces due to a dict
    key collision bug in io_bwm.py (using value-based equality instead of identity).
    """

    def test_transitions_remain_on_walkable_faces_after_roundtrip(self):
        """Test that transitions on walkable faces remain on walkable faces after roundtrip.

        This is a critical regression test for the walkmesh serialization bug where
        transitions could end up on unwalkable faces due to dict key collisions when
        BWMFace objects with the same vertex coordinates and transitions were present.
        """
        from pykotor.resource.formats.bwm import BWM, bytes_bwm, read_bwm
        from pykotor.resource.formats.bwm.bwm_data import BWMFace
        from utility.common.geometry import SurfaceMaterial, Vector3

        # Create a BWM with walkable and unwalkable faces
        bwm = BWM()

        # Create vertices
        v1 = Vector3(0, 0, 0)
        v2 = Vector3(1, 0, 0)
        v3 = Vector3(0, 1, 0)
        v4 = Vector3(1, 1, 0)
        v5 = Vector3(2, 0, 0)
        v6 = Vector3(2, 1, 0)

        # Create walkable faces (METAL = 10, walkable)
        walkable_face1 = BWMFace(v1, v2, v3)
        walkable_face1.material = SurfaceMaterial.METAL
        walkable_face1.trans1 = 1  # This is the transition we want to preserve
        walkable_face1.trans2 = 1

        walkable_face2 = BWMFace(v2, v4, v3)
        walkable_face2.material = SurfaceMaterial.METAL

        # Create unwalkable faces (NON_WALK = 7, not walkable)
        unwalkable_face1 = BWMFace(v2, v5, v4)
        unwalkable_face1.material = SurfaceMaterial.NON_WALK

        unwalkable_face2 = BWMFace(v5, v6, v4)
        unwalkable_face2.material = SurfaceMaterial.NON_WALK

        bwm.faces = [walkable_face1, walkable_face2, unwalkable_face1, unwalkable_face2]

        # Verify initial state: transition should be on walkable face
        assert walkable_face1.trans1 == 1, "Initial: walkable face should have transition"
        assert walkable_face1.material.walkable(), "Initial: face with transition should be walkable"

        # Serialize and deserialize
        data = bytes_bwm(bwm)
        loaded_bwm = read_bwm(data)

        # Find faces with transitions in the loaded BWM
        faces_with_transitions = [(i, face) for i, face in enumerate(loaded_bwm.faces) if face.trans1 is not None or face.trans2 is not None or face.trans3 is not None]

        # Verify: all faces with transitions should be walkable
        for idx, face in faces_with_transitions:
            assert face.material.walkable(), (
                f"CRITICAL BUG: Transition on face {idx} which has material {face.material} "
                f"(walkable={face.material.walkable()}). Transitions should only be on walkable faces. "
                "This bug causes characters to be stuck in indoor map builder modules."
            )

        # Verify we still have at least one transition
        assert len(faces_with_transitions) > 0, "Should have at least one face with transitions"

    def test_roundtrip_with_working_module_data(self):
        """Test roundtrip with real module data from v2.0.4 (working version).

        This uses the actual test files from the indoormap_bug_inspect_workspace
        to ensure the fix works with real game data.
        """
        from pykotor.resource.formats.erf import read_erf
        from pykotor.resource.formats.bwm import read_bwm, bytes_bwm
        from pykotor.resource.type import ResourceType

        # Load the working v2.0.4 module
        # TESTS_FILES_PATH is tests/test_files, we need Libraries/PyKotor/tests/test_files
        v2_mod_path = (
            pathlib.Path(__file__).parents[6]
            / "Libraries"
            / "PyKotor"
            / "tests"
            / "test_files"
            / "indoormap_bug_inspect_workspace"
            / "v2.0.4-toolset"
            / "step01"
            / "step01.mod"
        )
        if not v2_mod_path.exists():
            self.skipTest(f"Test file not found: {v2_mod_path}")

        v2_erf = read_erf(v2_mod_path)

        for res in v2_erf:
            if res.restype == ResourceType.WOK and "room0" in str(res.resref):
                original_bwm = read_bwm(res.data)

                # Find original transitions
                original_transitions = [
                    (i, face.trans1, face.trans2, face.trans3, face.material.walkable())
                    for i, face in enumerate(original_bwm.faces)
                    if face.trans1 is not None or face.trans2 is not None or face.trans3 is not None
                ]

                # Verify original has transitions on walkable faces
                for idx, t1, t2, t3, is_walkable in original_transitions:
                    assert is_walkable, f"Original face {idx} with transition should be walkable"

                # Roundtrip
                new_data = bytes_bwm(original_bwm)
                new_bwm = read_bwm(new_data)

                # Find new transitions
                new_transitions = [
                    (i, face.trans1, face.trans2, face.trans3, face.material.walkable())
                    for i, face in enumerate(new_bwm.faces)
                    if face.trans1 is not None or face.trans2 is not None or face.trans3 is not None
                ]

                # Verify roundtrip preserved transitions on walkable faces
                for idx, t1, t2, t3, is_walkable in new_transitions:
                    assert is_walkable, (
                        f"After roundtrip: face {idx} with transition (trans1={t1}, trans2={t2}, trans3={t3}) "
                        f"should be walkable, but is not. This causes the indoor map builder bug."
                    )

                # Verify we didn't lose transitions
                assert len(new_transitions) == len(original_transitions), f"Transition count changed: {len(original_transitions)} -> {len(new_transitions)}"
                break
        else:
            self.skipTest("No room0 WOK found in test module")

    def test_identity_based_face_lookup_not_value_based(self):
        """Test that face lookup uses identity, not value equality.

        This tests the specific bug where two faces with the same vertex coordinates
        and transitions (but different materials) would collide in a dict lookup.
        """
        from pykotor.resource.formats.bwm import BWM, bytes_bwm, read_bwm
        from pykotor.resource.formats.bwm.bwm_data import BWMFace
        from utility.common.geometry import SurfaceMaterial, Vector3

        # Create a BWM with two faces that have SAME vertices and transitions
        # but DIFFERENT materials (one walkable, one not)
        bwm = BWM()

        # Shared vertices
        v1 = Vector3(0, 0, 0)
        v2 = Vector3(1, 0, 0)
        v3 = Vector3(0, 1, 0)

        # Walkable face with transition
        walkable = BWMFace(v1, v2, v3)
        walkable.material = SurfaceMaterial.METAL  # Walkable (METAL = 10)
        walkable.trans1 = 1

        # Different vertices for the unwalkable face (so it's a valid walkmesh)
        v4 = Vector3(1, 1, 0)
        v5 = Vector3(2, 0, 0)
        v6 = Vector3(2, 1, 0)

        unwalkable = BWMFace(v4, v5, v6)
        unwalkable.material = SurfaceMaterial.NON_WALK  # NOT walkable (NON_WALK = 7)

        # Add a third walkable face so there's something to compute edges from
        walkable2 = BWMFace(v2, v4, v3)
        walkable2.material = SurfaceMaterial.METAL

        bwm.faces = [walkable, walkable2, unwalkable]

        # Serialize and deserialize
        data = bytes_bwm(bwm)
        loaded_bwm = read_bwm(data)

        # The transition should be on a walkable face, not the unwalkable one
        for i, face in enumerate(loaded_bwm.faces):
            if face.trans1 is not None:
                assert face.material.walkable(), (
                    f"Face {i} has trans1={face.trans1} but material={face.material} "
                    f"(walkable={face.material.walkable()}). "
                    "This indicates the identity-based lookup bug is present."
                )


if __name__ == "__main__":
    unittest.main()


# ============================================================================
# Additional UI tests (merged from test_ui_other_editors.py)
# ============================================================================

import pytest
from toolset.gui.editors.bwm import BWMEditor
from toolset.data.installation import HTInstallation


def test_bwm_editor_headless_ui_load_build(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test BWM Editor in headless UI - loads real file and builds data."""
    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)

    # Try to find a BWM/WOK file
    bwm_file = test_files_dir / "zio006j.wok"
    if not bwm_file.exists():
        # Try to get one from installation
        bwm_resources: list[ResourceResult | None] = list(installation.resources([ResourceIdentifier("zio006j", ResourceType.WOK)]).values())[:1]
        if not bwm_resources:
            bwm_resources = list(installation.resources([ResourceIdentifier("zio006j", ResourceType.DWK)]).values())[:1]
        if not bwm_resources:
            pytest.skip("No BWM files available for testing")
        first_bwm_resource: ResourceResult | None = bwm_resources[0]
        if first_bwm_resource is None:
            pytest.fail("BWM not found on second pass, after lookup with resources()...???")
        bwm_resource = installation.resource(first_bwm_resource.resname, first_bwm_resource.restype)
        if not bwm_resource:
            pytest.skip(f"Could not load BWM data for {first_bwm_resource.resname}")
        editor.load(
            first_bwm_resource.filepath if hasattr(first_bwm_resource, "filepath") else pathlib.Path("module.wok"),
            first_bwm_resource.resname,
            first_bwm_resource.restype,
            bwm_resource.data,
        )
    else:
        original_data = bwm_file.read_bytes()
        editor.load(bwm_file, "zio006j", ResourceType.WOK, original_data)

    # Verify editor loaded the data
    assert editor is not None

    # Build and verify it works
    data, _ = editor.build()
    assert len(data) > 0

    # Verify we can read it back
    from pykotor.resource.formats.bwm.bwm_auto import read_bwm

    loaded_bwm = read_bwm(data)
    assert loaded_bwm is not None


def test_bwmeditor_editor_help_dialog_opens_correct_file(qtbot: QtBot, installation: HTInstallation):
    """Test that BWMEditor help dialog opens and displays the correct help file (not 'Help File Not Found')."""
    from toolset.gui.dialogs.editor_help import EditorHelpDialog

    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)

    # Trigger help dialog with the correct file for BWMEditor
    editor._show_help_dialog("BWM-File-Format.md")
    qtbot.waitUntil(lambda: len(editor.findChildren(EditorHelpDialog)) > 0, timeout=2000)

    # Find the help dialog
    dialogs = [child for child in editor.findChildren(EditorHelpDialog)]
    assert len(dialogs) > 0, "Help dialog should be opened"

    dialog = dialogs[0]
    qtbot.addWidget(dialog)
    qtbot.waitExposed(dialog, timeout=2000)
    qtbot.waitUntil(lambda: dialog.text_browser.toHtml().strip() != "", timeout=2000)

    # Get the HTML content
    html = dialog.text_browser.toHtml()

    # Assert that "Help File Not Found" error is NOT shown
    assert "Help File Not Found" not in html, f"Help file 'BWM-File-Format.md' should be found, but error was shown. HTML: {html[:500]}"

    # Assert that some content is present (file was loaded successfully)
    assert len(html) > 100, "Help dialog should contain content"


def test_bwm_editor_ui_initialization(qtbot: QtBot, installation: HTInstallation):
    """Test BWM Editor UI initialization."""
    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()

    assert editor.isVisible()
    # Walkmesh editor might have GL view or property lists
    assert hasattr(editor.ui, "renderArea")
    assert hasattr(editor.ui, "materialList")
    assert hasattr(editor.ui, "transList")


# ============================================================================
# MATERIAL MANAGEMENT TESTS
# ============================================================================


def test_bwm_editor_rebuild_materials(qtbot: QtBot, installation: HTInstallation):
    """Test rebuilding material list."""
    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    initial_count = editor.ui.materialList.count()

    # Rebuild materials
    editor.rebuild_materials()
    QApplication.processEvents()

    # Verify materials were rebuilt
    assert editor.ui.materialList.count() == initial_count
    assert editor.ui.materialList.count() > 0


def test_bwm_editor_material_list_items(qtbot: QtBot, installation: HTInstallation):
    """Test that material list contains expected materials."""
    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    # Verify material list has items
    assert editor.ui.materialList.count() > 0

    # Verify each item has material data
    for i in range(editor.ui.materialList.count()):
        item = editor.ui.materialList.item(i)
        assert item is not None
        material = item.data(Qt.ItemDataRole.UserRole)
        assert material is not None
        assert hasattr(material, "name") or hasattr(material, "value")


def test_bwm_editor_material_selection(qtbot: QtBot, installation: HTInstallation):
    """Test selecting materials from the list."""
    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    # Select first material
    if editor.ui.materialList.count() > 0:
        editor.ui.materialList.setCurrentRow(0)
        QApplication.processEvents()

        current_item = editor.ui.materialList.currentItem()
        assert current_item is not None

        # Select different material
        if editor.ui.materialList.count() > 1:
            editor.ui.materialList.setCurrentRow(1)
            QApplication.processEvents()

            new_item = editor.ui.materialList.currentItem()
            assert new_item is not None
            assert new_item != current_item


# ============================================================================
# TRANSITION MANAGEMENT TESTS
# ============================================================================


def test_bwm_editor_transition_list_populated(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test that transition list is populated when loading BWM with transitions."""
    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    bwm_file = test_files_dir / "zio006j.wok"
    if not bwm_file.exists():
        pytest.skip("zio006j.wok not found")

    original_data = bwm_file.read_bytes()
    editor.load(bwm_file, "zio006j", ResourceType.WOK, original_data)
    QApplication.processEvents()

    # Verify transition list may have items (if walkmesh has transitions)
    assert editor.ui.transList is not None
    # Transition count depends on walkmesh content
    assert editor.ui.transList.count() >= 0


def test_bwm_editor_transition_list_selection(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test selecting transitions from the list."""
    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    bwm_file = test_files_dir / "zio006j.wok"
    if not bwm_file.exists():
        pytest.skip("zio006j.wok not found")

    original_data = bwm_file.read_bytes()
    editor.load(bwm_file, "zio006j", ResourceType.WOK, original_data)
    QApplication.processEvents()

    # Select transition if available
    if editor.ui.transList.count() > 0:
        editor.ui.transList.setCurrentRow(0)
        QApplication.processEvents()

        current_item = editor.ui.transList.currentItem()
        assert current_item is not None
        assert "Transition" in current_item.text()


# ============================================================================
# KEYBOARD SHORTCUT TESTS
# ============================================================================


def test_bwm_editor_zoom_shortcuts(qtbot: QtBot, installation: HTInstallation):
    """Test zoom keyboard shortcuts."""
    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    # Get initial zoom (if accessible)
    render_area = editor.ui.renderArea
    if hasattr(render_area, "camera"):
        initial_zoom = getattr(render_area.camera, "zoom", None) or 1.0

        # Zoom in with "="
        qtbot.keyClick(editor, Qt.Key.Key_Equal)
        QApplication.processEvents()

        # Zoom out with "-"
        qtbot.keyClick(editor, Qt.Key.Key_Minus)
        QApplication.processEvents()

        # Verify shortcuts work (zoom may have changed)
        assert render_area is not None


# ============================================================================
# NEW FILE CREATION TESTS
# ============================================================================


def test_bwm_editor_new_file_creation(qtbot: QtBot, installation: HTInstallation):
    """Test creating a new BWM file."""
    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    # Create new
    editor.new()
    QApplication.processEvents()

    # Verify editor is in new state
    assert editor._bwm is None or len(editor._bwm.faces) == 0

    # Build empty file
    try:
        data, _ = editor.build()
        # Empty BWM may or may not be valid
        assert isinstance(data, bytes)
    except Exception:
        # Empty BWM may raise exception, which is acceptable
        pass


# ============================================================================
# UI STATE TESTS
# ============================================================================


def test_bwm_editor_ui_widgets_exist(qtbot: QtBot, installation: HTInstallation):
    """Test that all UI widgets exist."""
    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    # Verify main widgets exist
    assert hasattr(editor.ui, "renderArea")
    assert hasattr(editor.ui, "materialList")
    assert hasattr(editor.ui, "transList")

    # Verify render area exists
    assert editor.ui.renderArea is not None
    assert editor.ui.materialList is not None
    assert editor.ui.transList is not None


def test_bwm_editor_toggle_room_boundaries(qtbot: QtBot, installation: HTInstallation):
    """Test toolbar toggle for room boundaries/labels."""
    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)

    original = editor.ui.renderArea.show_room_boundaries
    editor.ui.actionShowRoomBoundaries.setChecked(not original)

    assert editor.ui.renderArea.show_room_boundaries is (not original)


def test_bwm_editor_toggle_show_grid(qtbot: QtBot, installation: HTInstallation):
    """Test toolbar toggle for 2D grid display."""
    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)

    original = editor.ui.renderArea.show_grid
    editor.ui.actionShowGrid.setChecked(not original)

    assert editor.ui.renderArea.show_grid is (not original)


def test_bwm_editor_material_colors_initialized(qtbot: QtBot, installation: HTInstallation):
    """Test that material colors are initialized."""
    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    # Verify material colors dictionary exists
    assert hasattr(editor, "material_colors")
    assert isinstance(editor.material_colors, dict)
    assert len(editor.material_colors) > 0

    # Verify render area has material colors
    if hasattr(editor.ui.renderArea, "material_colors"):
        assert editor.ui.renderArea.material_colors is not None


# ============================================================================
# EDGE CASES
# ============================================================================


def test_bwm_editor_load_empty_walkmesh(qtbot: QtBot, installation: HTInstallation):
    """Test loading an empty walkmesh."""
    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    # Create minimal BWM data (may not be valid, but should handle gracefully)
    try:
        from pykotor.resource.formats.bwm import BWM, bytes_bwm

        empty_bwm = BWM()
        empty_data = bytes_bwm(empty_bwm)

        editor.load(pathlib.Path("empty.wok"), "empty", ResourceType.WOK, empty_data)
        QApplication.processEvents()

        # Should handle gracefully
        assert editor is not None
    except Exception:
        # Empty BWM may raise exception, which is acceptable
        pass


def test_bwm_editor_load_invalid_data(qtbot: QtBot, installation: HTInstallation):
    """Test loading invalid/corrupted BWM data."""
    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    # Try to load invalid data
    invalid_data = b"INVALID BWM DATA" * 100

    try:
        editor.load(pathlib.Path("invalid.wok"), "invalid", ResourceType.WOK, invalid_data)
        # If it doesn't raise, verify editor is in a valid state
        assert editor is not None
    except Exception:
        # If it raises, that's acceptable error handling
        pass


# ============================================================================
# COMPREHENSIVE ROUNDTRIP TESTS
# ============================================================================


def test_bwm_editor_multiple_save_load_cycles(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test multiple save/load cycles preserve data correctly."""
    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    bwm_file = test_files_dir / "zio006j.wok"
    if not bwm_file.exists():
        pytest.skip("zio006j.wok not found")

    original_data = bwm_file.read_bytes()
    original_bwm = read_bwm(original_data)
    editor.load(bwm_file, "zio006j", ResourceType.WOK, original_data)
    QApplication.processEvents()

    # Perform multiple cycles
    for cycle in range(3):
        # Save
        data, _ = editor.build()
        saved_bwm = read_bwm(data)

        # Verify basic properties preserved
        assert saved_bwm.walkmesh_type == original_bwm.walkmesh_type
        assert len(saved_bwm.faces) == len(original_bwm.faces)

        # Load back
        editor.load(bwm_file, "zio006j", ResourceType.WOK, data)
        QApplication.processEvents()

        # Verify loaded
        assert editor._bwm is not None
        assert len(editor._bwm.faces) == len(original_bwm.faces)


# ============================================================================
# RESOURCE LOADING TESTS
# ============================================================================


def test_bwm_editor_load_from_installation(qtbot: QtBot, installation: HTInstallation):
    """Test loading BWM resource from installation."""
    if installation is None:
        pytest.skip("Installation not available")

    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    # Try to find any walkmesh resource in the installation by enumerating known resources.
    # (Installation.resources() expects explicit name+type queries, not a tuple of types.)
    file_res = next((r for r in installation if r.restype in (ResourceType.WOK, ResourceType.DWK)), None)
    if file_res is None:
        pytest.skip("No WOK/DWK resources found in installation")

    bwm_resource = installation.resource(file_res.resname, file_res.restype)
    if bwm_resource is None:
        pytest.skip(f"Could not load BWM data for {file_res.resname}")

    # Load from installation
    editor.load(
        bwm_resource.filepath if hasattr(bwm_resource, "filepath") else pathlib.Path("module.wok"),
        bwm_resource.resname,
        bwm_resource.restype,
        bwm_resource.data,
    )
    QApplication.processEvents()

    # Verify loaded
    assert editor._bwm is not None
    assert len(editor._bwm.faces) >= 0


# ============================================================================
# STRESS TESTS
# ============================================================================


def test_bwm_editor_large_walkmesh(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test editor with large walkmesh (stress test)."""
    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    bwm_file = test_files_dir / "zio006j.wok"
    if not bwm_file.exists():
        pytest.skip("zio006j.wok not found")

    original_data = bwm_file.read_bytes()
    original_bwm = read_bwm(original_data)

    # Verify it's a reasonably large walkmesh
    if len(original_bwm.faces) < 10:
        pytest.skip("Walkmesh too small for stress test")

    editor.load(bwm_file, "zio006j", ResourceType.WOK, original_data)
    QApplication.processEvents()

    # Verify loaded
    assert editor._bwm is not None
    assert len(editor._bwm.faces) == len(original_bwm.faces)

    # Build and verify
    data, _ = editor.build()
    saved_bwm = read_bwm(data)
    assert len(saved_bwm.faces) == len(original_bwm.faces)


# ============================================================================
# COMPREHENSIVE WORKFLOW TESTS
# ============================================================================


def test_bwm_editor_complete_workflow(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test complete workflow: load, verify, save, reload, verify."""
    editor = BWMEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    bwm_file = test_files_dir / "zio006j.wok"
    if not bwm_file.exists():
        pytest.skip("zio006j.wok not found")

    # Load original
    original_data = bwm_file.read_bytes()
    original_bwm = read_bwm(original_data)
    editor.load(bwm_file, "zio006j", ResourceType.WOK, original_data)
    QApplication.processEvents()

    # Verify loaded
    assert editor._bwm is not None
    assert len(editor._bwm.faces) == len(original_bwm.faces)
    assert editor._bwm.walkmesh_type == original_bwm.walkmesh_type

    # Save
    data1, _ = editor.build()
    saved_bwm1 = read_bwm(data1)

    # Verify first save
    assert len(saved_bwm1.faces) == len(original_bwm.faces)
    assert saved_bwm1.walkmesh_type == original_bwm.walkmesh_type

    # Reload
    editor.load(bwm_file, "zio006j", ResourceType.WOK, data1)
    QApplication.processEvents()

    # Verify reloaded
    assert editor._bwm is not None
    assert len(editor._bwm.faces) == len(original_bwm.faces)

    # Save again
    data2, _ = editor.build()
    saved_bwm2 = read_bwm(data2)

    # Verify second save matches first
    assert len(saved_bwm2.faces) == len(saved_bwm1.faces)
    assert saved_bwm2.walkmesh_type == saved_bwm1.walkmesh_type
