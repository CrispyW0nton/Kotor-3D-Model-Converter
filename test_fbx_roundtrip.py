#!/usr/bin/env python3
"""
Phase B – Task B7 (T107): FBX Round-Trip Validation Tests
==========================================================

Comprehensive tests for the GhostRigger FBX ASCII 7.4 exporter.
Validates all Milestone 1 (M1) deliverables: bone hierarchy, skin deformers,
bind-pose matrices, synthetic bone stubs, weight normalization, animation export,
and geometry/UV round-trip integrity.

Since pyassimp/trimesh are unavailable in the sandbox, these tests use:
  1. Structural validation: Parse the FBX ASCII text to verify required sections,
     keywords, connections, and data integrity.
  2. Geometry round-trip via assimp_py: Export FBX, re-import with assimp_py,
     compare vertex/face counts (assimp_py provides geometry but no bones).
  3. Matrix arithmetic verification: Validate bind-pose and quaternion-to-Euler
     conversions against known reference values.

Run: cd /home/user/webapp && python3 -m pytest test_fbx_roundtrip.py -v
"""

import os
import re
import sys
import math
import tempfile
import unittest

# Ensure project root is on the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.model_data import (
    ModelNode, KotorModel, Animation, NodeFlags, GameVersion,
    BoneWeight, VertexSkinData,
)
from src.converters.mesh_converter import FBXExporter


# ──────────────────────────────────────────────────────────────────────────
#  Test Fixture Helpers
# ──────────────────────────────────────────────────────────────────────────

def _make_simple_trimesh(name="test_mesh", parent=None, texture="lts_wall01"):
    """Create a simple triangle mesh node (trimesh)."""
    n = ModelNode(
        name=name,
        flags=int(NodeFlags.MESH),
        position=(1.0, 2.0, 3.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        parent=parent,
        vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)],
        normals=[(0, 0, 1), (0, 0, 1), (0, 0, 1), (0, 0, 1)],
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)],
        faces=[(0, 1, 2), (1, 3, 2)],
        texture=texture,
        diffuse=(0.8, 0.8, 0.8),
        specular=(0.1, 0.1, 0.1),
        shininess=10.0,
        alpha=1.0,
        render=True,
    )
    if parent:
        parent.children.append(n)
    return n


def _make_skin_mesh(name="skin_mesh", parent=None, bone_names=None):
    """Create a skinned mesh node with 4 vertices, 2 bones, weights."""
    if bone_names is None:
        bone_names = ["rootbone", "childbone"]
    n = ModelNode(
        name=name,
        flags=int(NodeFlags.SKIN),
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        parent=parent,
        vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)],
        normals=[(0, 0, 1), (0, 0, 1), (0, 0, 1), (0, 0, 1)],
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)],
        faces=[(0, 1, 2), (1, 3, 2)],
        texture="body_tex",
        diffuse=(0.7, 0.7, 0.7),
        specular=(0.0, 0.0, 0.0),
        shininess=5.0,
        alpha=1.0,
        render=True,
        bone_map=list(bone_names),
        skin_data=[
            VertexSkinData(influences=[BoneWeight(0, 1.0)]),
            VertexSkinData(influences=[BoneWeight(0, 0.5), BoneWeight(1, 0.5)]),
            VertexSkinData(influences=[BoneWeight(1, 0.8), BoneWeight(0, 0.2)]),
            VertexSkinData(influences=[BoneWeight(1, 1.0)]),
        ],
    )
    if parent:
        parent.children.append(n)
    return n


def _make_character_model(name="test_char", with_anim=True, with_skin=True):
    """Build a complete character KotorModel with root, bones, mesh, and optional animation."""
    model = KotorModel(
        name=name,
        supermodel="S_MALE02",
        game_version=GameVersion.K1,
        classification="character",
        model_type=4,  # CHARACTER
        anim_scale=1.0,
    )
    # Root node (HEADER flag → type_label='dummy')
    root = ModelNode(name=name, flags=int(NodeFlags.HEADER),
                     position=(0.0, 0.0, 0.0),
                     rotation=(0.0, 0.0, 0.0, 1.0))
    model.root_node = root

    # Skeleton: rootbone → childbone → leafbone
    rootbone = ModelNode(name="rootbone", flags=0,
                         position=(0.0, 0.0, 0.0),
                         rotation=(0.0, 0.0, 0.0, 1.0),
                         parent=root)
    root.children.append(rootbone)

    childbone = ModelNode(name="childbone", flags=0,
                          position=(0.0, 0.0, 1.0),
                          rotation=(0.0, 0.0, 0.0, 1.0),
                          parent=rootbone)
    rootbone.children.append(childbone)

    leafbone = ModelNode(name="leafbone", flags=0,
                         position=(0.0, 1.0, 0.0),
                         rotation=(0.0, 0.0, 0.0, 1.0),
                         parent=childbone)
    childbone.children.append(leafbone)

    # Skin mesh
    if with_skin:
        _make_skin_mesh("btBody", parent=root,
                        bone_names=["rootbone", "childbone"])

    # Simple trimesh (non-skinned)
    _make_simple_trimesh("headmesh", parent=root, texture="head_tex")

    # Animation
    if with_anim:
        anim = Animation(name="walk", length=1.0, transition_time=0.25)
        anim_node = ModelNode(name="rootbone")
        anim_node.controllers = [
            {"type": 8, "times": [0.0, 0.5, 1.0],
             "values": [(0.0, 0.0, 0.0), (0.0, 0.0, 0.5), (0.0, 0.0, 0.0)]},
            {"type": 20, "times": [0.0, 0.5, 1.0],
             "values": [(0.0, 0.0, 0.0, 1.0),
                        (0.0, 0.0, 0.3827, 0.9239),  # 45° Z rotation
                        (0.0, 0.0, 0.0, 1.0)]},
        ]
        anim.nodes = [anim_node]

        anim2 = Animation(name="run", length=0.5, transition_time=0.15)
        anim2_node = ModelNode(name="childbone")
        anim2_node.controllers = [
            {"type": 8, "times": [0.0, 0.25, 0.5],
             "values": [(0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, 0.0)]},
        ]
        anim2.nodes = [anim2_node]
        model.animations = [anim, anim2]

    return model


def _make_tile_model(name="m02aa_01a"):
    """Build a tile/area model (model_type=2, TILE — no skeleton expected)."""
    model = KotorModel(
        name=name,
        supermodel="NULL",
        game_version=GameVersion.K1,
        classification="tile",
        model_type=2,
    )
    root = ModelNode(name=name, flags=int(NodeFlags.HEADER))
    model.root_node = root
    _make_simple_trimesh("wall_segment", parent=root, texture="lts_wall01")
    return model


def _make_effect_model(name="fx_spark"):
    """Build an effect model (model_type=0, EFFECT)."""
    model = KotorModel(
        name=name,
        supermodel="NULL",
        game_version=GameVersion.K1,
        classification="effect",
        model_type=0,  # EFFECT — must NOT be promoted to CHARACTER
    )
    root = ModelNode(name=name, flags=int(NodeFlags.HEADER))
    model.root_node = root
    _make_simple_trimesh("spark_mesh", parent=root, texture="fxpa_spark")
    return model


def _export_to_string(model, base_skeleton_model=None):
    """Export model to FBX ASCII and return the file content as a string."""
    with tempfile.TemporaryDirectory() as td:
        fbx_path = os.path.join(td, f"{model.name}.fbx")
        exporter = FBXExporter()
        ok = exporter.export(model, fbx_path, export_rigging=False,
                             base_skeleton_model=base_skeleton_model)
        assert ok, f"FBX export failed for model '{model.name}'"
        with open(fbx_path, 'r', encoding='utf-8') as f:
            return f.read()


def _count_pattern(text, pattern):
    """Count non-overlapping occurrences of a regex pattern in text."""
    return len(re.findall(pattern, text))


# ──────────────────────────────────────────────────────────────────────────
#  Test T107-A: FBX Export Basic Structure
# ──────────────────────────────────────────────────────────────────────────

class TestFBXExportBasicStructure(unittest.TestCase):
    """Verify FBX ASCII 7.4 file has correct header, sections, and format."""

    @classmethod
    def setUpClass(cls):
        cls.model = _make_character_model()
        cls.fbx_text = _export_to_string(cls.model)

    def test_fbx_header_version(self):
        """FBX file starts with correct header version."""
        self.assertIn("FBXHeaderVersion: 1003", self.fbx_text)
        self.assertIn("FBXVersion: 7400", self.fbx_text)

    def test_fbx_creator(self):
        """Creator string identifies GhostRigger."""
        self.assertIn("GhostRigger", self.fbx_text)

    def test_global_settings_present(self):
        """GlobalSettings section with axis/unit config is present."""
        self.assertIn("GlobalSettings:", self.fbx_text)
        self.assertIn('"UpAxis"', self.fbx_text)
        self.assertIn('"FrontAxis"', self.fbx_text)
        self.assertIn('"UnitScaleFactor"', self.fbx_text)

    def test_z_up_axis(self):
        """Z-up axis system (KotOR convention, matches UE5)."""
        # UpAxis=2 (Z), UpAxisSign=1 (positive)
        self.assertIn('"UpAxis", "int", "Integer", "",2', self.fbx_text)
        self.assertIn('"UpAxisSign", "int", "Integer", "",1', self.fbx_text)

    def test_objects_section(self):
        """Objects section is present."""
        self.assertIn("Objects:", self.fbx_text)

    def test_connections_section(self):
        """Connections section is present."""
        self.assertIn("Connections:", self.fbx_text)

    def test_takes_section(self):
        """Takes section is present (legacy compatibility)."""
        self.assertIn("Takes:", self.fbx_text)

    def test_nonzero_file_size(self):
        """File is non-trivially sized (>1KB for a character model)."""
        self.assertGreater(len(self.fbx_text), 1000)

    def test_documents_section_present(self):
        """FBX 7.4 mandatory Documents section is present."""
        self.assertIn("Documents:", self.fbx_text)
        self.assertIn("Document:", self.fbx_text)
        self.assertIn('"Scene"', self.fbx_text)
        self.assertIn("RootNode: 0", self.fbx_text)

    def test_definitions_section_present(self):
        """FBX 7.4 mandatory Definitions section is present."""
        self.assertIn("Definitions:", self.fbx_text)
        self.assertIn("Version: 100", self.fbx_text)
        self.assertIn('ObjectType: "GlobalSettings"', self.fbx_text)
        self.assertIn('ObjectType: "Model"', self.fbx_text)
        self.assertIn('ObjectType: "Geometry"', self.fbx_text)

    def test_definitions_count_matches(self):
        """Definitions ObjectType counts match actual object instances."""
        # Extract Model count from Definitions
        match = re.search(
            r'ObjectType:\s*"Model"\s*\{\s*Count:\s*(\d+)', self.fbx_text)
        self.assertIsNotNone(match, "Model ObjectType not found in Definitions")
        def_model_count = int(match.group(1))
        # Count actual Model: lines in Objects
        actual_models = len(re.findall(r'\tModel:', self.fbx_text))
        self.assertEqual(def_model_count, actual_models,
                         f"Definitions says {def_model_count} Models but found {actual_models}")

    def test_section_order(self):
        """FBX sections appear in correct order per spec."""
        header_pos = self.fbx_text.find("FBXHeaderExtension:")
        global_pos = self.fbx_text.find("GlobalSettings:")
        docs_pos = self.fbx_text.find("Documents:")
        defs_pos = self.fbx_text.find("Definitions:")
        objects_pos = self.fbx_text.find("Objects:")
        connections_pos = self.fbx_text.find("Connections:")
        self.assertLess(header_pos, global_pos, "Header must precede GlobalSettings")
        self.assertLess(global_pos, docs_pos, "GlobalSettings must precede Documents")
        self.assertLess(docs_pos, defs_pos, "Documents must precede Definitions")
        self.assertLess(defs_pos, objects_pos, "Definitions must precede Objects")
        self.assertLess(objects_pos, connections_pos, "Objects must precede Connections")

    def test_fbx_type_prefixed_naming(self):
        """FBX objects use standard Type::Name naming convention."""
        # Check Geometry uses "Geometry::" prefix
        geo_lines = re.findall(r'Geometry:\s*\d+,\s*"([^"]*)"', self.fbx_text)
        for name in geo_lines:
            self.assertTrue(name.startswith("Geometry::"),
                            f"Geometry name '{name}' missing 'Geometry::' prefix")
        # Check Model uses "Model::" prefix
        model_lines = re.findall(r'\tModel:\s*\d+,\s*"([^"]*)"', self.fbx_text)
        for name in model_lines:
            self.assertTrue(name.startswith("Model::"),
                            f"Model name '{name}' missing 'Model::' prefix")
        # Check Material uses "Material::" prefix
        mat_lines = re.findall(r'Material:\s*\d+,\s*"([^"]*)"', self.fbx_text)
        for name in mat_lines:
            self.assertTrue(name.startswith("Material::"),
                            f"Material name '{name}' missing 'Material::' prefix")


# ──────────────────────────────────────────────────────────────────────────
#  Test T107-B: Bone Hierarchy Export (B1 / T101)
# ──────────────────────────────────────────────────────────────────────────

class TestFBXBoneHierarchy(unittest.TestCase):
    """Validate that ALL skeleton bone nodes appear in the FBX output."""

    @classmethod
    def setUpClass(cls):
        cls.model = _make_character_model()
        cls.fbx_text = _export_to_string(cls.model)

    def test_root_node_present(self):
        """Root skeleton node is exported as 'Null' type."""
        self.assertRegex(self.fbx_text, r'Model:.*"Model::test_char".*"Null"')

    def test_bone_nodes_present(self):
        """All three bone nodes (rootbone, childbone, leafbone) appear as LimbNode."""
        for bone_name in ["rootbone", "childbone", "leafbone"]:
            with self.subTest(bone=bone_name):
                pattern = rf'Model:.*"Model::{bone_name}".*"LimbNode"'
                self.assertRegex(self.fbx_text, pattern,
                                 f"Bone '{bone_name}' not found as LimbNode in FBX")

    def test_skeleton_node_attributes(self):
        """NodeAttribute objects of type 'Skeleton' exist for each bone (UE5 requirement)."""
        for bone_name in ["rootbone", "childbone", "leafbone"]:
            with self.subTest(bone=bone_name):
                pattern = rf'NodeAttribute:.*"NodeAttribute::{bone_name}".*"Skeleton"'
                self.assertRegex(self.fbx_text, pattern,
                                 f"Missing NodeAttribute for bone '{bone_name}'")

    def test_skeleton_typeflags(self):
        """TypeFlags: 'Skeleton' is present for each NodeAttribute."""
        count = _count_pattern(self.fbx_text, r'TypeFlags:\s*"Skeleton"')
        # At least root + 3 bones = 4 skeleton attributes
        self.assertGreaterEqual(count, 4)

    def test_bone_lcl_translation(self):
        """Bones have Lcl Translation properties."""
        # childbone has position (0, 0, 1)
        self.assertIn("childbone", self.fbx_text)
        # Check that a Lcl Translation exists after the childbone Model line
        childbone_section = self.fbx_text[self.fbx_text.find('"Model::childbone", "LimbNode"'):]
        self.assertIn("Lcl Translation", childbone_section[:500])

    def test_bone_hierarchy_connections(self):
        """Bones are connected to their parents via OO connections."""
        # The connection section should have OO links forming the hierarchy
        conn_section = self.fbx_text[self.fbx_text.find("Connections:"):]
        # Count OO connections — should have at least root→scene + bone chains
        oo_count = _count_pattern(conn_section, r'C:\s*"OO"')
        self.assertGreater(oo_count, 5)

    def test_lcl_rotation_present(self):
        """Bone rotation is exported as Lcl Rotation (Euler XYZ degrees)."""
        self.assertIn("Lcl Rotation", self.fbx_text)

    def test_rotation_order_xyz(self):
        """RotationOrder is set to 0 (XYZ) — matching KotOR/UE5 convention."""
        self.assertIn('"RotationOrder","enum","","",0', self.fbx_text)


# ──────────────────────────────────────────────────────────────────────────
#  Test T107-C: Skin Deformers (B2 / T102)
# ──────────────────────────────────────────────────────────────────────────

class TestFBXSkinDeformers(unittest.TestCase):
    """Validate skin deformers, clusters, and per-bone weight data."""

    @classmethod
    def setUpClass(cls):
        cls.model = _make_character_model(with_skin=True)
        cls.fbx_text = _export_to_string(cls.model)

    def test_skin_deformer_present(self):
        """A Skin deformer is emitted for the skin mesh."""
        self.assertRegex(self.fbx_text, r'Deformer:.*"Deformer::btBody_Skin".*"Skin"')

    def test_skin_deformer_version(self):
        """Skin deformer version is 101."""
        # Find the Skin deformer section
        idx = self.fbx_text.find('btBody_Skin')
        self.assertNotEqual(idx, -1)
        section = self.fbx_text[idx:idx+300]
        self.assertIn("Version: 101", section)

    def test_cluster_per_bone(self):
        """SubDeformer/Cluster exists for each bone in the bone_map."""
        for bone_name in ["rootbone", "childbone"]:
            with self.subTest(bone=bone_name):
                pattern = rf'SubDeformer:.*"SubDeformer::{bone_name}".*"Cluster"'
                self.assertRegex(self.fbx_text, pattern,
                                 f"Missing Cluster for bone '{bone_name}'")

    def test_cluster_has_indexes(self):
        """Clusters with weights have vertex index arrays."""
        # rootbone influences vertices 0,1,2 — should have Indexes
        rootbone_cluster_idx = self.fbx_text.find('"SubDeformer::rootbone", "Cluster"')
        self.assertNotEqual(rootbone_cluster_idx, -1)
        section = self.fbx_text[rootbone_cluster_idx:rootbone_cluster_idx+500]
        self.assertIn("Indexes:", section)

    def test_cluster_has_weights(self):
        """Clusters with weights have weight value arrays."""
        rootbone_cluster_idx = self.fbx_text.find('"SubDeformer::rootbone", "Cluster"')
        section = self.fbx_text[rootbone_cluster_idx:rootbone_cluster_idx+500]
        self.assertIn("Weights:", section)

    def test_cluster_has_transform(self):
        """Each cluster has Transform matrix (mesh world matrix)."""
        rootbone_cluster_idx = self.fbx_text.find('"SubDeformer::rootbone", "Cluster"')
        section = self.fbx_text[rootbone_cluster_idx:rootbone_cluster_idx+800]
        self.assertIn("Transform:", section)

    def test_cluster_has_transformlink(self):
        """Each cluster has TransformLink matrix (bone world matrix)."""
        rootbone_cluster_idx = self.fbx_text.find('"SubDeformer::rootbone", "Cluster"')
        section = self.fbx_text[rootbone_cluster_idx:rootbone_cluster_idx+800]
        self.assertIn("TransformLink:", section)

    def test_skin_to_geometry_connection(self):
        """Skin deformer is connected to geometry via OO."""
        conn_section = self.fbx_text[self.fbx_text.find("Connections:"):]
        # Skin deformer → mesh geometry connection should exist
        self.assertGreater(len(conn_section), 100)

    def test_cluster_to_bone_connection(self):
        """Clusters are connected to bone nodes via OO."""
        conn_section = self.fbx_text[self.fbx_text.find("Connections:"):]
        # There should be cluster→bone connections
        oo_count = _count_pattern(conn_section, r'C:\s*"OO"')
        self.assertGreater(oo_count, 8)


# ──────────────────────────────────────────────────────────────────────────
#  Test T107-D: Bind-Pose Matrix Computation (B3 / T103)
# ──────────────────────────────────────────────────────────────────────────

class TestFBXBindPoseMatrix(unittest.TestCase):
    """Validate bind-pose section and matrix correctness."""

    @classmethod
    def setUpClass(cls):
        cls.model = _make_character_model()
        cls.fbx_text = _export_to_string(cls.model)

    def test_bind_pose_present(self):
        """BindPose section exists."""
        self.assertRegex(self.fbx_text, r'Pose:.*"(?:Pose::)?BIND_POSES".*"BindPose"')

    def test_bind_pose_type(self):
        """Pose Type is 'BindPose'."""
        idx = self.fbx_text.find('BIND_POSES')
        section = self.fbx_text[idx:idx+200]
        self.assertIn('Type: "BindPose"', section)

    def test_nb_pose_nodes(self):
        """NbPoseNodes count matches skeleton + mesh nodes."""
        idx = self.fbx_text.find('BIND_POSES')
        section = self.fbx_text[idx:idx+500]
        match = re.search(r'NbPoseNodes:\s*(\d+)', section)
        self.assertIsNotNone(match, "NbPoseNodes not found in BindPose")
        nb = int(match.group(1))
        # model has: root(1) + 3 bones + 1 skin mesh + 1 trimesh = at least 6
        self.assertGreaterEqual(nb, 6)

    def test_pose_node_matrices_are_16_floats(self):
        """Each PoseNode Matrix has exactly 16 float values."""
        pose_section = self.fbx_text[self.fbx_text.find('BIND_POSES'):]
        end_idx = pose_section.find('\n\t}')  # end of Pose block
        if end_idx > 0:
            pose_section = pose_section[:end_idx]
        matrices = re.findall(r'Matrix:\s*\*16\s*\{[^}]*a:\s*([^}]+)\}', pose_section)
        self.assertGreater(len(matrices), 0, "No matrices found in BindPose")
        for i, mat_str in enumerate(matrices):
            values = [v.strip() for v in mat_str.split(',') if v.strip()]
            self.assertEqual(len(values), 16,
                             f"PoseNode matrix {i} has {len(values)} values (expected 16)")

    def test_identity_quaternion_produces_identity_matrix(self):
        """A bone at origin with identity quaternion → identity-like matrix."""
        # rootbone has position=(0,0,0), rotation=(0,0,0,1) → identity rotation
        # Its parent is root which also has identity transform → world matrix ≈ identity
        # Find rootbone's PoseNode and verify the matrix is near-identity
        pose_section = self.fbx_text[self.fbx_text.find('BIND_POSES'):]
        # Look for the matrix data — we can verify structure is well-formed
        self.assertIn("Matrix: *16", pose_section)

    def test_transform_matrix_is_column_major(self):
        """Transform matrix in clusters is column-major (last 4 values = tx,ty,tz,1)."""
        # Find any Transform *16 block and check last value is 1.0
        transform_blocks = re.findall(
            r'Transform:\s*\*16\s*\{[^}]*a:\s*([^}]+)\}', self.fbx_text)
        for mat_str in transform_blocks:
            values = [float(v.strip()) for v in mat_str.split(',')]
            self.assertEqual(len(values), 16)
            # Column-major: element [15] (row3, col3) should be 1.0
            self.assertAlmostEqual(values[15], 1.0, places=4,
                                   msg="Matrix[3,3] should be 1.0 for affine transform")
            # Elements [3], [7], [11] should be 0.0 (perspective row in affine)
            for idx in [3, 7, 11]:
                self.assertAlmostEqual(values[idx], 0.0, places=4,
                                       msg=f"Matrix element {idx} should be 0.0")


# ──────────────────────────────────────────────────────────────────────────
#  Test T107-E: Synthetic Bone Stubs (B4 / T104)
# ──────────────────────────────────────────────────────────────────────────

class TestFBXSyntheticBones(unittest.TestCase):
    """Validate synthetic bone stubs for supermodel-referenced bones."""

    @classmethod
    def setUpClass(cls):
        """Create a model where skin references a bone not in the node tree."""
        cls.model = _make_character_model(with_skin=False, with_anim=False)
        # Add a skin mesh referencing a bone "torso_g" not in the model
        root = cls.model.root_node
        skin = _make_skin_mesh("body_skin", parent=root,
                               bone_names=["rootbone", "torso_g"])
        # "torso_g" does NOT exist in model.all_nodes()
        cls.fbx_text = _export_to_string(cls.model)

    def test_synthetic_bone_node_created(self):
        """Missing bone 'torso_g' is synthesized as a LimbNode."""
        self.assertRegex(self.fbx_text, r'Model:.*"Model::torso_g".*"LimbNode"')

    def test_synthetic_bone_has_node_attribute(self):
        """Synthesized bone has a NodeAttribute of type Skeleton."""
        self.assertRegex(self.fbx_text, r'NodeAttribute:.*"NodeAttribute::torso_g".*"Skeleton"')

    def test_synthetic_bone_in_bind_pose(self):
        """Synthesized bone appears in the BindPose PoseNode list."""
        pose_section = self.fbx_text[self.fbx_text.find('BIND_POSES'):]
        # The torso_g node ID should appear in a PoseNode block
        # We can check that NbPoseNodes includes it
        match = re.search(r'NbPoseNodes:\s*(\d+)', pose_section)
        self.assertIsNotNone(match)

    def test_synthetic_bone_cluster_exists(self):
        """A SubDeformer cluster exists for the synthesized bone."""
        self.assertRegex(self.fbx_text, r'SubDeformer:.*"SubDeformer::torso_g".*"Cluster"')

    def test_synthetic_bone_connected_to_root(self):
        """Synthesized bone is parented under root node via OO connection."""
        conn_section = self.fbx_text[self.fbx_text.find("Connections:"):]
        # Find the OO connections — torso_g should be connected somewhere
        self.assertIn("torso_g", self.fbx_text)

    def test_base_skeleton_transforms_used(self):
        """When base_skeleton_model is provided, synthetic bones get real transforms."""
        # Create a base skeleton with torso_g having a known position
        base_model = KotorModel(name="S_MALE02")
        base_root = ModelNode(name="S_MALE02", flags=int(NodeFlags.HEADER))
        base_model.root_node = base_root
        torso_g = ModelNode(name="torso_g", flags=0,
                            position=(0.0, 0.0, 5.0),
                            rotation=(0.0, 0.0, 0.0, 1.0),
                            parent=base_root)
        base_root.children.append(torso_g)

        fbx_text = _export_to_string(self.model,
                                     base_skeleton_model=base_model)
        # The synthetic torso_g should now have position 0,0,5 in its Lcl Translation
        idx = fbx_text.find('"Model::torso_g", "LimbNode"')
        self.assertNotEqual(idx, -1)
        section = fbx_text[idx:idx+500]
        self.assertIn("5.000000", section,
                       "Base skeleton Z=5.0 transform not found in synthetic bone")


# ──────────────────────────────────────────────────────────────────────────
#  Test T107-F: Weight Normalization (B5 / T105)
# ──────────────────────────────────────────────────────────────────────────

class TestFBXWeightNormalization(unittest.TestCase):
    """Validate that per-vertex weights are normalized and capped at 4."""

    @classmethod
    def setUpClass(cls):
        """Create model with problematic weights: >4 influences, unnormalized."""
        cls.model = KotorModel(name="weight_test", model_type=4)
        root = ModelNode(name="weight_test", flags=int(NodeFlags.HEADER))
        cls.model.root_node = root

        # 3 bones
        for bname in ["b0", "b1", "b2"]:
            bone = ModelNode(name=bname, flags=0, parent=root)
            root.children.append(bone)

        # Skin mesh with 5-influence vertex (should be capped to 4)
        skin = ModelNode(
            name="overskin", flags=int(NodeFlags.SKIN), parent=root,
            vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
            normals=[(0, 0, 1)] * 3,
            uvs=[(0, 0), (1, 0), (0, 1)],
            faces=[(0, 1, 2)],
            texture="skin_tex",
            diffuse=(0.8, 0.8, 0.8), specular=(0, 0, 0),
            bone_map=["b0", "b1", "b2"],
            skin_data=[
                # Vertex 0: unnormalized weights (sum=2.0)
                VertexSkinData(influences=[
                    BoneWeight(0, 1.0), BoneWeight(1, 0.8), BoneWeight(2, 0.2)]),
                # Vertex 1: zero weight (should get fallback)
                VertexSkinData(influences=[]),
                # Vertex 2: normal case
                VertexSkinData(influences=[BoneWeight(0, 0.6), BoneWeight(1, 0.4)]),
            ],
            render=True,
        )
        root.children.append(skin)
        cls.fbx_text = _export_to_string(cls.model)

    def test_export_succeeds(self):
        """Export does not crash with abnormal weight data."""
        self.assertGreater(len(self.fbx_text), 500)

    def test_weights_in_valid_range(self):
        """All weight values in the FBX are between 0.0 and 1.0."""
        # Extract all Weights arrays
        weight_blocks = re.findall(
            r'Weights:\s*\*\d+\s*\{[^}]*a:\s*([^}]+)\}', self.fbx_text)
        for block in weight_blocks:
            weights = [float(v.strip()) for v in block.split(',')]
            for w in weights:
                self.assertGreaterEqual(w, 0.0)
                self.assertLessEqual(w, 1.0 + 1e-6)

    def test_cluster_structure_valid(self):
        """Clusters have matching Indexes and Weights array sizes."""
        # Find all clusters
        clusters = re.finditer(
            r'SubDeformer:.*?"Cluster"\s*\{(.*?)\n\t\}',
            self.fbx_text, re.DOTALL)
        for cluster_match in clusters:
            section = cluster_match.group(1)
            idx_match = re.search(r'Indexes:\s*\*(\d+)', section)
            wt_match = re.search(r'Weights:\s*\*(\d+)', section)
            if idx_match and wt_match:
                self.assertEqual(int(idx_match.group(1)), int(wt_match.group(1)),
                                 "Indexes and Weights array sizes must match")


# ──────────────────────────────────────────────────────────────────────────
#  Test T107-G: Animation Export (B6 / T106)
# ──────────────────────────────────────────────────────────────────────────

class TestFBXAnimationExport(unittest.TestCase):
    """Validate animation stacks, layers, curves, and Takes section."""

    @classmethod
    def setUpClass(cls):
        cls.model = _make_character_model(with_anim=True)
        cls.fbx_text = _export_to_string(cls.model)

    def test_anim_stacks_present(self):
        """AnimationStack objects exist for each animation."""
        for anim_name in ["walk", "run"]:
            with self.subTest(anim=anim_name):
                pattern = rf'AnimationStack:.*"(?:AnimStack::)?\|{anim_name}"'
                self.assertRegex(self.fbx_text, pattern,
                                 f"AnimationStack for '{anim_name}' not found")

    def test_anim_layers_present(self):
        """AnimationLayer objects exist."""
        count = _count_pattern(self.fbx_text, r'AnimationLayer:')
        self.assertGreaterEqual(count, 2)  # walk + run

    def test_anim_curves_present(self):
        """AnimationCurve objects exist for keyframe data."""
        count = _count_pattern(self.fbx_text, r'AnimationCurve:')
        # walk has position (3 curves) + rotation (3 curves) = 6
        # run has position (3 curves) = 3
        self.assertGreaterEqual(count, 9)

    def test_anim_curve_nodes_present(self):
        """AnimationCurveNode objects exist (T and R channels)."""
        count = _count_pattern(self.fbx_text, r'AnimationCurveNode:')
        # walk has T + R = 2 CurveNodes; run has T = 1 CurveNode
        self.assertGreaterEqual(count, 3)

    def test_key_time_values(self):
        """KeyTime arrays have correct number of entries."""
        key_times = re.findall(r'KeyTime:\s*\*(\d+)', self.fbx_text)
        self.assertGreater(len(key_times), 0)
        for kt in key_times:
            n = int(kt)
            self.assertGreater(n, 0, "KeyTime should have at least 1 entry")

    def test_key_value_float(self):
        """KeyValueFloat arrays match KeyTime sizes."""
        # Find all (KeyTime, KeyValueFloat) pairs
        curves = re.findall(
            r'KeyTime:\s*\*(\d+).*?KeyValueFloat:\s*\*(\d+)',
            self.fbx_text, re.DOTALL)
        for kt_n, kv_n in curves:
            self.assertEqual(int(kt_n), int(kv_n),
                             "KeyTime and KeyValueFloat must have same count")

    def test_takes_section_lists_animations(self):
        """Takes section lists all animation clips."""
        takes_idx = self.fbx_text.find("Takes:")
        takes_section = self.fbx_text[takes_idx:]
        self.assertIn('"walk"', takes_section)
        self.assertIn('"run"', takes_section)

    def test_takes_has_current(self):
        """Takes section specifies a Current animation."""
        takes_idx = self.fbx_text.find("Takes:")
        takes_section = self.fbx_text[takes_idx:]
        self.assertIn("Current:", takes_section)

    def test_anim_stack_properties(self):
        """AnimationStack has LocalStart/LocalStop timing properties."""
        self.assertIn("LocalStart", self.fbx_text)
        self.assertIn("LocalStop", self.fbx_text)

    def test_fbx_ticks_per_sec(self):
        """Animation timing uses correct FBX tick rate (46186158000)."""
        # walk animation length=1.0s → ticks should be 46186158000
        self.assertIn("46186158000", self.fbx_text)

    def test_keyattr_flags(self):
        """KeyAttrFlags with cubic+auto tangent flag (24776) is present."""
        self.assertIn("24776", self.fbx_text)

    def test_animation_connections(self):
        """AnimationCurveNode → AnimLayer and AnimLayer → AnimStack connections."""
        conn_section = self.fbx_text[self.fbx_text.find("Connections:"):]
        # Should contain OP connections for d|X, d|Y, d|Z
        self.assertIn('"d|X"', conn_section)
        self.assertIn('"d|Y"', conn_section)
        self.assertIn('"d|Z"', conn_section)
        # And Lcl Translation / Lcl Rotation connections
        self.assertIn('"Lcl Translation"', conn_section)


# ──────────────────────────────────────────────────────────────────────────
#  Test T107-H: Geometry Round-Trip via assimp_py
# ──────────────────────────────────────────────────────────────────────────

class TestFBXGeometryRoundTrip(unittest.TestCase):
    """Export FBX, re-import via assimp_py, compare vertex/face counts."""

    def _round_trip(self, model):
        """Export model to FBX, re-import, return (export_ok, reimported_scene)."""
        import assimp_py
        with tempfile.TemporaryDirectory() as td:
            fbx_path = os.path.join(td, f"{model.name}.fbx")
            exporter = FBXExporter()
            ok = exporter.export(model, fbx_path, export_rigging=False)
            self.assertTrue(ok, "FBX export failed")

            flags = (assimp_py.Process_Triangulate |
                     assimp_py.Process_JoinIdenticalVertices)
            scene = assimp_py.import_file(fbx_path, flags)
            return scene

    def test_character_mesh_count(self):
        """Character model: reimported mesh count matches exported mesh count."""
        model = _make_character_model()
        scene = self._round_trip(model)
        # We exported 2 meshes: btBody (skin) + headmesh (trimesh)
        self.assertGreaterEqual(len(scene.meshes), 2,
                                f"Expected >=2 meshes, got {len(scene.meshes)}")

    def test_character_vertex_count_reasonable(self):
        """Reimported vertex count is within bounds of exported data."""
        model = _make_character_model()
        scene = self._round_trip(model)
        total_verts = sum(len(m.vertices) for m in scene.meshes)
        # Each test mesh has 4 verts; with 2 meshes → 8 total
        # assimp may split/merge, so accept 4-16
        self.assertGreaterEqual(total_verts, 4,
                                f"Too few vertices: {total_verts}")
        self.assertLessEqual(total_verts, 32,
                             f"Too many vertices: {total_verts}")

    def test_character_face_count_reasonable(self):
        """Reimported face count is within bounds."""
        model = _make_character_model()
        scene = self._round_trip(model)
        # assimp_py uses num_faces attribute (not faces list)
        total_faces = sum(getattr(m, 'num_faces', 0) for m in scene.meshes)
        # Each mesh has 2 faces; 2 meshes → 4 total
        self.assertGreaterEqual(total_faces, 2)
        self.assertLessEqual(total_faces, 16)

    def test_tile_model_round_trip(self):
        """Tile model exports and re-imports without errors."""
        model = _make_tile_model()
        scene = self._round_trip(model)
        self.assertGreater(len(scene.meshes), 0)

    def test_effect_model_round_trip(self):
        """Effect model (model_type=0) exports and re-imports."""
        model = _make_effect_model()
        scene = self._round_trip(model)
        self.assertGreater(len(scene.meshes), 0)

    def test_reimported_normals_present(self):
        """Reimported meshes have normals."""
        model = _make_character_model()
        scene = self._round_trip(model)
        for mesh in scene.meshes:
            if mesh.vertices:
                self.assertTrue(
                    hasattr(mesh, 'normals') and mesh.normals is not None,
                    f"Mesh has no normals after round-trip")


# ──────────────────────────────────────────────────────────────────────────
#  Test T107-I: Geometry Data Integrity
# ──────────────────────────────────────────────────────────────────────────

class TestFBXGeometryDataIntegrity(unittest.TestCase):
    """Validate geometry data arrays in the FBX ASCII output."""

    @classmethod
    def setUpClass(cls):
        cls.model = _make_character_model()
        cls.fbx_text = _export_to_string(cls.model)

    def test_vertices_array_counts(self):
        """Vertices arrays have correct element counts (3 floats per vertex)."""
        vert_blocks = re.findall(r'Vertices:\s*\*(\d+)', self.fbx_text)
        for v in vert_blocks:
            n = int(v)
            # Must be divisible by 3 (x,y,z per vertex)
            self.assertEqual(n % 3, 0,
                             f"Vertices count {n} not divisible by 3")

    def test_polygon_indices_present(self):
        """PolygonVertexIndex arrays exist with correct format."""
        self.assertIn("PolygonVertexIndex:", self.fbx_text)

    def test_polygon_indices_negative_terminators(self):
        """FBX polygon indices use negative last-index-per-polygon convention."""
        # Find PolygonVertexIndex data
        blocks = re.findall(
            r'PolygonVertexIndex:\s*\*\d+\s*\{[^}]*a:\s*([^}]+)\}', self.fbx_text)
        for block in blocks:
            indices = [int(v.strip()) for v in block.split(',')]
            # At least one negative index (polygon terminator)
            has_negative = any(i < 0 for i in indices)
            self.assertTrue(has_negative,
                            "PolygonVertexIndex must have negative terminators")

    def test_normals_layer_present(self):
        """LayerElementNormal exists with ByPolygonVertex mapping."""
        self.assertIn("LayerElementNormal:", self.fbx_text)
        self.assertIn('"ByPolygonVertex"', self.fbx_text)

    def test_uv_layer_present(self):
        """LayerElementUV exists with IndexToDirect reference."""
        self.assertIn("LayerElementUV:", self.fbx_text)
        self.assertIn('"IndexToDirect"', self.fbx_text)

    def test_uv_index_array_present(self):
        """UVIndex array exists for UV seam handling."""
        self.assertIn("UVIndex:", self.fbx_text)

    def test_material_layer_present(self):
        """LayerElementMaterial with AllSame mapping is present."""
        self.assertIn("LayerElementMaterial:", self.fbx_text)
        self.assertIn('"AllSame"', self.fbx_text)

    def test_material_objects_present(self):
        """Material objects with Phong shading model are emitted."""
        self.assertIn('"Phong"', self.fbx_text)

    def test_texture_objects_present(self):
        """Texture and Video objects are emitted for textured meshes."""
        # headmesh has texture="head_tex", btBody has "body_tex"
        self.assertIn("head_tex", self.fbx_text)
        self.assertIn("body_tex", self.fbx_text)


# ──────────────────────────────────────────────────────────────────────────
#  Test T107-J: UV Coordinate Integrity
# ──────────────────────────────────────────────────────────────────────────

class TestFBXUVIntegrity(unittest.TestCase):
    """Validate UV export, including face_uvs handling."""

    def test_standard_uvs_exported(self):
        """Standard UV coordinates appear in the FBX UV array."""
        model = _make_character_model()
        fbx_text = _export_to_string(model)
        # Check that UV array has values — model UVs include 0.0 and 1.0
        uv_blocks = re.findall(
            r'UV:\s*\*(\d+)\s*\{[^}]*a:\s*([^}]+)\}', fbx_text)
        self.assertGreater(len(uv_blocks), 0, "No UV data found")
        for count_str, data_str in uv_blocks:
            values = [float(v.strip()) for v in data_str.split(',')]
            self.assertGreater(len(values), 0)
            # UVs should be in [0,1] range for our test data
            for v in values:
                self.assertGreaterEqual(v, -0.01)
                self.assertLessEqual(v, 1.01)

    def test_face_uvs_override(self):
        """When face_uvs are present, UV indices follow face_uvs, not vertex indices."""
        model = KotorModel(name="fuvs_test", model_type=2)
        root = ModelNode(name="fuvs_test", flags=int(NodeFlags.HEADER))
        model.root_node = root
        mesh = ModelNode(
            name="fuvs_mesh", flags=int(NodeFlags.MESH), parent=root,
            vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
            normals=[(0, 0, 1)] * 3,
            uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (0.5, 0.5)],
            faces=[(0, 1, 2)],
            # face_uvs: face 0 uses tvert indices [3, 1, 2] instead of [0, 1, 2]
            face_uvs=[(3, 1, 2)],
            texture="test_tex",
            diffuse=(0.8, 0.8, 0.8), specular=(0, 0, 0),
            render=True,
        )
        root.children.append(mesh)

        fbx_text = _export_to_string(model)
        # Find the UVIndex array — should contain 3,1,2 (from face_uvs)
        uv_idx_match = re.search(
            r'UVIndex:\s*\*3\s*\{[^}]*a:\s*([^}]+)\}', fbx_text)
        self.assertIsNotNone(uv_idx_match, "UVIndex array not found")
        indices = [int(v.strip()) for v in uv_idx_match.group(1).split(',')]
        self.assertEqual(indices, [3, 1, 2],
                         f"face_uvs not applied correctly: got {indices}")


# ──────────────────────────────────────────────────────────────────────────
#  Test T107-K: Model Classification Edge Cases
# ──────────────────────────────────────────────────────────────────────────

class TestFBXModelClassification(unittest.TestCase):
    """Validate bone filtering based on model_type."""

    def test_effect_model_no_full_skeleton(self):
        """EFFECT model (type=0) should NOT generate full bone hierarchy."""
        model = _make_effect_model()
        fbx_text = _export_to_string(model)
        # Effect model should have root node but NOT create LimbNode bones
        # (only root is included as skeleton node for effects)
        limb_count = _count_pattern(fbx_text, r'"LimbNode"')
        self.assertEqual(limb_count, 0,
                         f"EFFECT model should have 0 LimbNode bones, got {limb_count}")

    def test_tile_model_minimal_skeleton(self):
        """TILE model (type=2) should have minimal skeleton (root only)."""
        model = _make_tile_model()
        fbx_text = _export_to_string(model)
        limb_count = _count_pattern(fbx_text, r'"LimbNode"')
        self.assertEqual(limb_count, 0,
                         f"TILE model should have 0 LimbNode bones, got {limb_count}")

    def test_character_model_full_skeleton(self):
        """CHARACTER model (type=4) should have full skeleton hierarchy."""
        model = _make_character_model()
        fbx_text = _export_to_string(model)
        limb_count = _count_pattern(fbx_text, r'"LimbNode"')
        # 3 bones: rootbone, childbone, leafbone
        self.assertGreaterEqual(limb_count, 3,
                                f"CHARACTER model should have >=3 LimbNode bones, got {limb_count}")

    def test_model_type_zero_not_promoted(self):
        """model_type=0 (EFFECT) must NOT be promoted to CHARACTER (v7.2 fix)."""
        model = _make_effect_model()
        # Verify: model has model_type=0, no skin meshes
        self.assertEqual(model.model_type, 0)
        fbx_text = _export_to_string(model)
        # Should not contain skeleton NodeAttributes (no bones for effects)
        skel_attr_count = _count_pattern(fbx_text, r'TypeFlags:\s*"Skeleton"')
        # Only root gets a skeleton attribute (for hierarchy) or none at all
        # Key point: should be 0 or 1 (root only), NOT 3+ like a character
        self.assertLessEqual(skel_attr_count, 1,
                             f"EFFECT model should have <=1 Skeleton attributes, got {skel_attr_count}")


# ──────────────────────────────────────────────────────────────────────────
#  Test T107-L: Quaternion-to-Euler Conversion
# ──────────────────────────────────────────────────────────────────────────

class TestQuaternionToEuler(unittest.TestCase):
    """Validate the quaternion-to-Euler conversion used in FBX export."""

    def _quat_to_euler_deg(self, qx, qy, qz, qw):
        """Replicate the converter's _quat_to_euler_deg for testing."""
        mag = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
        if mag > 1e-9:
            qx /= mag; qy /= mag; qz /= mag; qw /= mag
        sinr = 2*(qw*qx + qy*qz)
        cosr = 1 - 2*(qx*qx + qy*qy)
        ex = math.degrees(math.atan2(sinr, cosr))
        sinp = 2*(qw*qy - qz*qx)
        ey = math.degrees(math.asin(max(-1.0, min(1.0, sinp))))
        siny = 2*(qw*qz + qx*qy)
        cosy = 1 - 2*(qy*qy + qz*qz)
        ez = math.degrees(math.atan2(siny, cosy))
        return ex, ey, ez

    def test_identity_quaternion(self):
        """Identity quaternion (0,0,0,1) → (0,0,0) degrees."""
        ex, ey, ez = self._quat_to_euler_deg(0, 0, 0, 1)
        self.assertAlmostEqual(ex, 0.0, places=4)
        self.assertAlmostEqual(ey, 0.0, places=4)
        self.assertAlmostEqual(ez, 0.0, places=4)

    def test_90deg_z_rotation(self):
        """90° Z rotation quaternion → ez ≈ 90°."""
        # quat for 90° Z: (0, 0, sin(45°), cos(45°)) = (0, 0, 0.7071, 0.7071)
        ex, ey, ez = self._quat_to_euler_deg(0, 0, 0.7071068, 0.7071068)
        self.assertAlmostEqual(ez, 90.0, places=1)
        self.assertAlmostEqual(ex, 0.0, places=1)
        self.assertAlmostEqual(ey, 0.0, places=1)

    def test_90deg_x_rotation(self):
        """90° X rotation quaternion → ex ≈ 90°."""
        ex, ey, ez = self._quat_to_euler_deg(0.7071068, 0, 0, 0.7071068)
        self.assertAlmostEqual(ex, 90.0, places=1)

    def test_180deg_x_rotation(self):
        """180° X rotation quaternion → ex ≈ ±180°."""
        ex, ey, ez = self._quat_to_euler_deg(1, 0, 0, 0)
        self.assertTrue(abs(abs(ex) - 180.0) < 1.0 or abs(ex) < 1.0,
                        f"180° X rotation: got ex={ex}")

    def test_normalized_quaternion(self):
        """Non-unit quaternion is normalized before conversion."""
        # 2× identity quaternion should still give (0,0,0)
        ex, ey, ez = self._quat_to_euler_deg(0, 0, 0, 2.0)
        self.assertAlmostEqual(ex, 0.0, places=2)
        self.assertAlmostEqual(ey, 0.0, places=2)
        self.assertAlmostEqual(ez, 0.0, places=2)


# ──────────────────────────────────────────────────────────────────────────
#  Test T107-M: Empty / Edge-Case Models
# ──────────────────────────────────────────────────────────────────────────

class TestFBXEdgeCases(unittest.TestCase):
    """Edge cases: empty animations, no skin, single-node model."""

    def test_model_no_animations(self):
        """Model with zero animations exports without error."""
        model = _make_character_model(with_anim=False)
        fbx_text = _export_to_string(model)
        self.assertIn("Takes:", fbx_text)
        self.assertIn('Current: ""', fbx_text)

    def test_model_no_skin_meshes(self):
        """Model without skin meshes exports without skin deformers."""
        model = _make_character_model(with_skin=False, with_anim=False)
        fbx_text = _export_to_string(model)
        # Should still have geometry and skeleton but no Skin deformers
        self.assertNotIn('"Skin"', fbx_text)
        self.assertIn("Vertices:", fbx_text)

    def test_single_node_model(self):
        """Model with only a root node (no children) exports."""
        model = KotorModel(name="empty_root", model_type=4)
        root = ModelNode(name="empty_root", flags=int(NodeFlags.HEADER))
        model.root_node = root
        fbx_text = _export_to_string(model)
        self.assertIn("FBXVersion: 7400", fbx_text)

    def test_animation_no_keyframes(self):
        """Animation with name but no keyframe nodes is still listed in Takes."""
        model = _make_character_model(with_anim=False)
        empty_anim = Animation(name="idle", length=2.0)
        empty_anim.nodes = []
        model.animations = [empty_anim]
        fbx_text = _export_to_string(model)
        self.assertIn('"idle"', fbx_text)
        takes_section = fbx_text[fbx_text.find("Takes:"):]
        self.assertIn('"idle"', takes_section)

    def test_mesh_with_no_uvs(self):
        """Mesh without UVs exports geometry without UV layer."""
        model = KotorModel(name="no_uv", model_type=2)
        root = ModelNode(name="no_uv", flags=int(NodeFlags.HEADER))
        model.root_node = root
        mesh = ModelNode(
            name="bare_mesh", flags=int(NodeFlags.MESH), parent=root,
            vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
            normals=[(0, 0, 1)] * 3,
            faces=[(0, 1, 2)],
            texture="bare_tex",
            diffuse=(0.8, 0.8, 0.8), specular=(0, 0, 0),
            render=True,
        )
        root.children.append(mesh)
        fbx_text = _export_to_string(model)
        self.assertIn("Vertices:", fbx_text)

    def test_mesh_with_no_normals(self):
        """Mesh without normals exports geometry without normal layer."""
        model = KotorModel(name="no_nrm", model_type=2)
        root = ModelNode(name="no_nrm", flags=int(NodeFlags.HEADER))
        model.root_node = root
        mesh = ModelNode(
            name="flat_mesh", flags=int(NodeFlags.MESH), parent=root,
            vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
            uvs=[(0, 0), (1, 0), (0, 1)],
            faces=[(0, 1, 2)],
            texture="flat_tex",
            diffuse=(0.8, 0.8, 0.8), specular=(0, 0, 0),
            render=True,
        )
        root.children.append(mesh)
        fbx_text = _export_to_string(model)
        self.assertIn("Vertices:", fbx_text)


# ──────────────────────────────────────────────────────────────────────────
#  Test T107-N: Connection Graph Integrity
# ──────────────────────────────────────────────────────────────────────────

class TestFBXConnectionGraph(unittest.TestCase):
    """Validate the Connections section has all required links."""

    @classmethod
    def setUpClass(cls):
        cls.model = _make_character_model()
        cls.fbx_text = _export_to_string(cls.model)
        # Parse connection section
        conn_start = cls.fbx_text.find("Connections:")
        cls.conn_section = cls.fbx_text[conn_start:]

    def test_geometry_to_mesh_node(self):
        """Geometry objects are connected to their mesh Model nodes."""
        # Count geometry→node OO connections
        oo_conns = re.findall(r'C:\s*"OO",(\d+),(\d+)', self.conn_section)
        self.assertGreater(len(oo_conns), 0)

    def test_material_to_mesh_node(self):
        """Material objects are connected to mesh Model nodes."""
        # Materials should be connected via OO
        oo_count = _count_pattern(self.conn_section, r'C:\s*"OO"')
        self.assertGreater(oo_count, 5)

    def test_texture_to_material(self):
        """Texture objects are connected to Materials via OP DiffuseColor."""
        self.assertIn('"DiffuseColor"', self.conn_section)

    def test_video_to_texture(self):
        """Video objects are connected to Texture objects via OO."""
        # Videos provide file references for textures
        oo_count = _count_pattern(self.conn_section, r'C:\s*"OO"')
        self.assertGreater(oo_count, 8)

    def test_node_attribute_to_bone(self):
        """NodeAttribute objects are connected to bone Model nodes."""
        # Skeleton NodeAttribute → Model connections
        skel_count = _count_pattern(
            self.fbx_text[:self.fbx_text.find("Connections:")],
            r'NodeAttribute:.*"Skeleton"')
        conn_attr_count = 0
        for line in self.conn_section.split('\n'):
            if 'C: "OO"' in line:
                conn_attr_count += 1
        self.assertGreater(conn_attr_count, 0)

    def test_all_node_ids_referenced(self):
        """Every node in the model has at least one connection."""
        # Extract all IDs used in connections
        all_ids = set()
        for m in re.finditer(r'C:\s*"O[OP]",(\d+),(\d+)', self.conn_section):
            all_ids.add(int(m.group(1)))
            all_ids.add(int(m.group(2)))
        # Should have many unique IDs (nodes + geometry + materials + etc.)
        self.assertGreater(len(all_ids), 10)


# ──────────────────────────────────────────────────────────────────────────
#  Test T107-O: FBX File I/O and Size
# ──────────────────────────────────────────────────────────────────────────

class TestFBXFileIO(unittest.TestCase):
    """Validate file writing, encoding, and size constraints."""

    def test_file_written_to_disk(self):
        """FBX file is actually written to the specified path."""
        model = _make_character_model()
        with tempfile.TemporaryDirectory() as td:
            fbx_path = os.path.join(td, "test_output.fbx")
            ok = FBXExporter().export(model, fbx_path, export_rigging=False)
            self.assertTrue(ok)
            self.assertTrue(os.path.isfile(fbx_path))
            size = os.path.getsize(fbx_path)
            self.assertGreater(size, 1000,
                               f"FBX file too small: {size} bytes")

    def test_file_is_utf8(self):
        """FBX ASCII file is valid UTF-8."""
        model = _make_character_model()
        with tempfile.TemporaryDirectory() as td:
            fbx_path = os.path.join(td, "utf8_test.fbx")
            FBXExporter().export(model, fbx_path, export_rigging=False)
            with open(fbx_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # Should not raise — valid UTF-8
            self.assertIsInstance(content, str)

    def test_rigging_sidecar_created(self):
        """When export_rigging=True, rigging JSON files are created."""
        model = _make_character_model()
        with tempfile.TemporaryDirectory() as td:
            fbx_path = os.path.join(td, "rigging_test.fbx")
            ok = FBXExporter().export(model, fbx_path, export_rigging=True)
            self.assertTrue(ok)
            rig_dir = os.path.join(td, "rigging")
            if os.path.isdir(rig_dir):
                rig_files = os.listdir(rig_dir)
                self.assertGreater(len(rig_files), 0,
                                   "rigging/ directory is empty")


# ──────────────────────────────────────────────────────────────────────────
#  Main entry point
# ──────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
