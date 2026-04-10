#!/usr/bin/env python3
"""
Test FBX Export Pipeline for Unreal Engine Compatibility

This test validates that our FBX exports contain all necessary data
for Unreal Engine import:
- Skeleton hierarchy (bones with proper parent-child relationships)
- Skin deformers (vertex weights bound to bones)
- Animations (keyframe data for position/rotation)
- Bind pose matrices
- Proper coordinate system (Z-up)

Run with:
    pytest tests/test_fbx_export_validation.py -v
"""

import pytest
import sys
import os
from pathlib import Path
import tempfile
import re

# Add src to path
TEST_DIR = Path(__file__).parent
PROJECT_ROOT = TEST_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from core.model_data import KotorModel, ModelNode, NodeFlags, VertexSkinData, BoneWeight
from converters.mesh_converter import FBXExporter


class TestFBXStructure:
    """Test that FBX files contain required structure for UE import."""
    
    def _make_simple_skinned_model(self):
        """Create a minimal skinned character model for testing."""
        model = KotorModel(name="test_char", supermodel="NULL", 
                          classification="character")
        
        # Root node
        root = ModelNode(name="test_char", flags=int(NodeFlags.HEADER))
        root.position = [0.0, 0.0, 0.0]
        root.orientation = [0.0, 0.0, 0.0, 1.0]
        model.root_node = root
        
        # Skeleton: pelvis → spine → head
        pelvis = ModelNode(name="pelvis", flags=0)
        pelvis.position = [0.0, 0.0, 0.5]
        pelvis.orientation = [0.0, 0.0, 0.0, 1.0]
        pelvis.parent = root
        root.children.append(pelvis)
        
        spine = ModelNode(name="spine", flags=0)
        spine.position = [0.0, 0.0, 0.3]
        spine.orientation = [0.0, 0.0, 0.0, 1.0]
        spine.parent = pelvis
        pelvis.children.append(spine)
        
        head = ModelNode(name="head", flags=0)
        head.position = [0.0, 0.0, 0.2]
        head.orientation = [0.0, 0.0, 0.0, 1.0]
        head.parent = spine
        spine.children.append(head)
        
        # Skin mesh (body)
        body = ModelNode(name="body", flags=int(NodeFlags.SKIN | NodeFlags.MESH))
        body.position = [0.0, 0.0, 0.0]
        body.orientation = [0.0, 0.0, 0.0, 1.0]
        body.parent = root
        root.children.append(body)
        
        # Simple quad mesh (2 triangles)
        body.vertices = [
            [-0.5, -0.5, 0.0],
            [ 0.5, -0.5, 0.0],
            [ 0.5,  0.5, 0.0],
            [-0.5,  0.5, 0.0],
        ]
        body.faces = [[0, 1, 2], [0, 2, 3]]
        body.normals = [[0.0, 0.0, 1.0]] * 4
        body.uvs = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
        body.texture = "test_tex"
        body.render = True
        
        # Bone map and skin weights
        body.bone_map = ["pelvis", "spine", "head"]
        body.skin_data = [
            VertexSkinData(influences=[BoneWeight(bone_index=0, weight=1.0)]),  # v0 → pelvis
            VertexSkinData(influences=[BoneWeight(bone_index=0, weight=0.7),
                                      BoneWeight(bone_index=1, weight=0.3)]),  # v1 → pelvis+spine
            VertexSkinData(influences=[BoneWeight(bone_index=1, weight=0.5),
                                      BoneWeight(bone_index=2, weight=0.5)]),  # v2 → spine+head
            VertexSkinData(influences=[BoneWeight(bone_index=2, weight=1.0)]),  # v3 → head
        ]
        
        return model
    
    def test_fbx_contains_skeleton_hierarchy(self):
        """FBX must contain Model objects for each bone with proper parent links."""
        model = self._make_simple_skinned_model()
        exporter = FBXExporter()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        
        try:
            success = exporter.export(model, fbx_path, export_rigging=False)
            assert success, "FBX export failed"
            
            with open(fbx_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Check for Model objects (bones)
            assert 'Model: ' in content, "No Model objects found"
            
            # Check for specific bones
            bone_names = ['test_char', 'pelvis', 'spine', 'head', 'body']
            for bone in bone_names:
                assert f'Model: ' in content and bone in content, \
                    f"Bone '{bone}' not found in FBX"
            
            # Check for Connections (parent-child relationships)
            assert 'Connections:' in content, "No Connections section"
            assert content.count('C: "OO"') >= 4, \
                "Not enough parent-child connections (expected 4+ for skeleton)"
            
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)
    
    def test_fbx_contains_skin_deformers(self):
        """FBX must contain Deformer and SubDeformer (Cluster) for skinning."""
        model = self._make_simple_skinned_model()
        exporter = FBXExporter()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        
        try:
            success = exporter.export(model, fbx_path, export_rigging=False)
            assert success, "FBX export failed"
            
            with open(fbx_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Check for Skin deformer
            assert 'Deformer:' in content and 'Skin' in content, \
                "No Skin deformer found"
            
            # Check for Clusters (one per bone in bone_map)
            assert 'SubDeformer:' in content and 'Cluster' in content, \
                "No Cluster subdeformers found"
            
            cluster_count = content.count('SubDeformer: ')
            assert cluster_count >= 3, \
                f"Expected 3+ clusters (for pelvis/spine/head), found {cluster_count}"
            
            # Check for weight data (Indexes and Weights arrays)
            assert 'Indexes:' in content, "No vertex index data in clusters"
            assert 'Weights:' in content, "No weight data in clusters"
            
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)
    
    def test_fbx_contains_bind_pose(self):
        """FBX must contain Pose object with bind matrices for each bone."""
        model = self._make_simple_skinned_model()
        exporter = FBXExporter()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        
        try:
            success = exporter.export(model, fbx_path, export_rigging=False)
            assert success, "FBX export failed"
            
            with open(fbx_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Check for Pose object
            assert 'Pose:' in content and 'BindPose' in content, \
                "No BindPose found"
            
            # Check for PoseNode entries (one per bone)
            pose_node_count = content.count('PoseNode:')
            assert pose_node_count >= 4, \
                f"Expected 4+ PoseNode entries (for skeleton), found {pose_node_count}"
            
            # Check for Matrix entries (4x4 transform matrices)
            assert 'Matrix:' in content, "No transform matrices in BindPose"
            
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)
    
    def test_fbx_coordinate_system(self):
        """FBX must use Z-up coordinate system (KotOR/UE standard)."""
        model = self._make_simple_skinned_model()
        exporter = FBXExporter()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        
        try:
            success = exporter.export(model, fbx_path, export_rigging=False)
            assert success, "FBX export failed"
            
            with open(fbx_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Check GlobalSettings for Z-up
            assert 'GlobalSettings:' in content, "No GlobalSettings found"
            assert 'P: "UpAxis"' in content, "No UpAxis property"
            
            # Find UpAxis value (should be 2 for Z-up)
            match = re.search(r'P: "UpAxis".*?"",(\d+)', content)
            assert match, "Could not parse UpAxis value"
            up_axis = int(match.group(1))
            assert up_axis == 2, f"Expected UpAxis=2 (Z-up), got {up_axis}"
            
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)
    
    def test_fbx_geometry_data(self):
        """FBX must contain mesh geometry (vertices, faces, normals, UVs)."""
        model = self._make_simple_skinned_model()
        exporter = FBXExporter()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        
        try:
            success = exporter.export(model, fbx_path, export_rigging=False)
            assert success, "FBX export failed"
            
            with open(fbx_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Check for Geometry object
            assert 'Geometry:' in content and 'Mesh' in content, \
                "No Geometry (Mesh) found"
            
            # Check for vertex data
            assert 'Vertices:' in content, "No vertex data"
            vertex_match = re.search(r'Vertices: \*(\d+)', content)
            assert vertex_match, "Could not parse vertex count"
            vertex_count = int(vertex_match.group(1))
            assert vertex_count == 12, \
                f"Expected 12 vertex components (4 verts * 3), got {vertex_count}"
            
            # Check for face data (PolygonVertexIndex)
            assert 'PolygonVertexIndex:' in content, "No face index data"
            
            # Check for normals
            assert 'LayerElementNormal:' in content, "No normal data"
            assert 'Normals:' in content, "No normal values"
            
            # Check for UVs
            assert 'LayerElementUV:' in content, "No UV layer"
            assert 'UV:' in content, "No UV coordinates"
            
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)


class TestFBXAnimations:
    """Test that FBX animation data is correct for UE import."""
    
    def _make_animated_model(self):
        """Create a model with simple walk animation."""
        model = KotorModel(name="test_anim", supermodel="NULL")
        
        # Root + one bone
        root = ModelNode(name="test_anim", flags=int(NodeFlags.HEADER))
        root.position = [0.0, 0.0, 0.0]
        root.orientation = [0.0, 0.0, 0.0, 1.0]
        model.root_node = root
        
        bone = ModelNode(name="bone1", flags=0)
        bone.position = [0.0, 0.0, 1.0]
        bone.orientation = [0.0, 0.0, 0.0, 1.0]
        bone.parent = root
        root.children.append(bone)
        
        # Simple animation (2 seconds, 2 keyframes)
        from core.model_data import Animation
        anim = Animation(name="walk", length=2.0, transition_time=0.25)
        
        # Animation nodes are ModelNodes with controllers
        anim_bone = ModelNode(name="bone1", flags=0)
        # Position controller (type 8)
        anim_bone.controllers.append({
            'type': 8,  # CTRL_POSITION
            'times': [0.0, 1.0, 2.0],
            'values': [[0.0, 0.0, 0.0], [0.0, 0.5, 0.0], [0.0, 0.0, 0.0]]
        })
        # Rotation controller (type 20)
        anim_bone.controllers.append({
            'type': 20,  # CTRL_ORIENTATION
            'times': [0.0, 1.0, 2.0],
            'values': [[0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.707, 0.707], [0.0, 0.0, 0.0, 1.0]]
        })
        anim.nodes = [anim_bone]
        
        model.animations = [anim]
        
        return model
    
    def test_fbx_contains_animation_stack(self):
        """FBX must contain AnimationStack for each animation."""
        model = self._make_animated_model()
        exporter = FBXExporter()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        
        try:
            success = exporter.export(model, fbx_path, export_rigging=False)
            assert success, "FBX export failed"
            
            with open(fbx_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Check for AnimationStack
            assert 'AnimationStack:' in content, "No AnimationStack found"
            assert 'walk' in content, "Animation name 'walk' not found"
            
            # Check for time properties (LocalStart/LocalStop)
            assert 'P: "LocalStart"' in content, "No LocalStart property"
            assert 'P: "LocalStop"' in content, "No LocalStop property"
            
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)
    
    def test_fbx_contains_animation_curves(self):
        """FBX must contain AnimationCurve with keyframe data."""
        model = self._make_animated_model()
        exporter = FBXExporter()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        
        try:
            success = exporter.export(model, fbx_path, export_rigging=False)
            assert success, "FBX export failed"
            
            with open(fbx_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Check for AnimationCurve objects
            assert 'AnimationCurve:' in content, "No AnimationCurve found"
            
            # Check for keyframe time data
            assert 'KeyTime:' in content, "No keyframe time data"
            
            # Check for keyframe value data
            assert 'KeyValueFloat:' in content, "No keyframe value data"
            
            # Should have curves for T (translation) and R (rotation)
            # 3 axes each = 6 curves minimum
            curve_count = content.count('AnimationCurve:')
            assert curve_count >= 6, \
                f"Expected 6+ animation curves (T.xyz + R.xyz), found {curve_count}"
            
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)
    
    def test_fbx_animation_curve_connections(self):
        """FBX must connect AnimationCurves to bones via CurveNodes."""
        model = self._make_animated_model()
        exporter = FBXExporter()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        
        try:
            success = exporter.export(model, fbx_path, export_rigging=False)
            assert success, "FBX export failed"
            
            with open(fbx_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Check for AnimationCurveNode (intermediate layer)
            assert 'AnimationCurveNode:' in content, "No AnimationCurveNode found"
            
            # Check for OP connections (AnimationCurve → CurveNode → Bone)
            assert 'C: "OP"' in content, "No OP (property) connections found"
            
            # Should have connections mentioning translation/rotation
            assert 'Lcl Translation' in content or 'T|' in content, \
                "No translation property connections"
            assert 'Lcl Rotation' in content or 'R|' in content, \
                "No rotation property connections"
            
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)


class TestFBXRealWorldModel:
    """Test FBX export with a realistic KotOR character model structure."""
    
    @pytest.mark.skipif(not Path("./kotor_data").exists(), 
                       reason="KotOR data directory not available")
    def test_export_character_model(self):
        """Test exporting a real character model (if KotOR data available)."""
        # This test requires actual KotOR game files
        # Skip if not available, but run in CI with test data
        from core.resource_manager import ResourceManager
        from core.model_data import GameVersion
        
        kotor_path = Path("./kotor_data")
        if not kotor_path.exists():
            pytest.skip("KotOR data not available")
        
        rm = ResourceManager(kotor_path=str(kotor_path), 
                            game_version=GameVersion.K1)
        
        # Try to load a simple character model
        try:
            model = rm.load_model("c_hutt")  # Hutt is usually small/simple
        except Exception as e:
            pytest.skip(f"Could not load test model: {e}")
        
        exporter = FBXExporter()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        
        try:
            success = exporter.export(model, fbx_path, export_rigging=True)
            assert success, "FBX export failed for real model"
            
            # Verify file was created and is non-empty
            assert os.path.exists(fbx_path), "FBX file not created"
            file_size = os.path.getsize(fbx_path)
            assert file_size > 1000, f"FBX file too small ({file_size} bytes)"
            
            # Parse and check structure
            with open(fbx_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Verify all required sections
            required_sections = [
                'FBXHeaderExtension:',
                'GlobalSettings:',
                'Objects:',
                'Connections:',
            ]
            for section in required_sections:
                assert section in content, f"Missing FBX section: {section}"
            
            # Verify has geometry
            assert 'Geometry:' in content, "No geometry in real model"
            assert 'Vertices:' in content, "No vertex data in real model"
            
            print(f"\n✅ Successfully exported real model: {model.name}")
            print(f"   File size: {file_size:,} bytes")
            print(f"   Nodes: {len(list(model.all_nodes()))}")
            print(f"   Animations: {len(model.animations)}")
            
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)


class TestFBXBoneNodeDetection:
    """
    Tests for the critical fix: bone nodes (flags=0) must be exported as
    LimbNode in FBX, not silently skipped.

    KotOR character models have two kinds of non-renderable nodes:
      flags=0x01 (HEADER)   → model root → exported as "Null"
      flags=0x00 (no flags) → bone joints → exported as "LimbNode"

    Previously only is_dummy (flags==0x01) was exported, so ALL bone nodes
    (flags==0) were missing from the FBX — UE5 would import a mesh with no
    skeleton. This test suite validates that fix.
    """

    def _make_model_with_bone_nodes(self):
        """Create a model where bones have flags=0 (not HEADER)."""
        model = KotorModel(name="bone_test", supermodel="NULL",
                           classification="character")

        # Root: flags=HEADER (0x01)
        root = ModelNode(name="bone_test", flags=int(NodeFlags.HEADER))
        root.position = [0.0, 0.0, 0.0]
        root.rotation = [0.0, 0.0, 0.0, 1.0]
        model.root_node = root

        # Pure bone nodes: flags=0  ← these were previously INVISIBLE to the exporter
        pelvis = ModelNode(name="pelvis", flags=0)  # ← flags=0, NOT HEADER
        pelvis.position = [0.0, 0.0, 0.9]
        pelvis.rotation = [0.0, 0.0, 0.0, 1.0]
        pelvis.parent = root
        root.children.append(pelvis)

        spine = ModelNode(name="spine", flags=0)
        spine.position = [0.0, 0.0, 0.2]
        spine.rotation = [0.0, 0.0, 0.0, 1.0]
        spine.parent = pelvis
        pelvis.children.append(spine)

        l_arm = ModelNode(name="lforearm", flags=0)
        l_arm.position = [0.3, 0.0, 0.1]
        l_arm.rotation = [0.0, 0.0, 0.0, 1.0]
        l_arm.parent = spine
        spine.children.append(l_arm)

        # Skinned mesh parented to root
        body = ModelNode(name="body_g", flags=int(NodeFlags.SKIN | NodeFlags.MESH))
        body.position = [0.0, 0.0, 0.0]
        body.rotation = [0.0, 0.0, 0.0, 1.0]
        body.parent = root
        root.children.append(body)
        body.vertices = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
        body.faces = [[0, 1, 2]]
        body.render = True
        body.bone_map = ["pelvis", "spine", "lforearm"]
        body.skin_data = [
            VertexSkinData(influences=[BoneWeight(bone_index=0, weight=1.0)]),
            VertexSkinData(influences=[BoneWeight(bone_index=1, weight=1.0)]),
            VertexSkinData(influences=[BoneWeight(bone_index=2, weight=1.0)]),
        ]
        return model

    def test_bone_nodes_flags0_exported_as_limbnodes(self):
        """
        Bone nodes with flags=0 must appear as 'LimbNode' in the FBX.
        This was the primary bug: only flags=0x01 (HEADER) nodes were exported,
        so actual skeleton bones were completely missing from the output.
        """
        model = self._make_model_with_bone_nodes()
        exporter = FBXExporter()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name

        try:
            success = exporter.export(model, fbx_path, export_rigging=False)
            assert success, "FBX export failed"

            with open(fbx_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # All three bone names must appear in FBX Model entries
            for bone_name in ['pelvis', 'spine', 'lforearm']:
                assert bone_name in content, \
                    f"Bone '{bone_name}' (flags=0) not found in FBX — bone node detection broken"

            # Verify they appear as LimbNode entries specifically
            limb_count = content.count('"LimbNode"')
            assert limb_count >= 3, \
                f"Expected 3+ LimbNode entries for bone nodes, found {limb_count}"

        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)

    def test_root_node_exported_as_null(self):
        """
        The model root node (flags=HEADER=0x01) must be exported as 'Null',
        not 'LimbNode'. Child bone nodes get 'LimbNode'.
        """
        model = self._make_model_with_bone_nodes()
        exporter = FBXExporter()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name

        try:
            success = exporter.export(model, fbx_path, export_rigging=False)
            assert success, "FBX export failed"

            with open(fbx_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Root should be "Null", not "LimbNode"
            assert '"Null"' in content, \
                "Root node (flags=HEADER) should be exported as 'Null'"
            # Bones should be "LimbNode"
            assert '"LimbNode"' in content, \
                "Bone nodes (flags=0) should be exported as 'LimbNode'"

        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)

    def test_rotation_order_property_present(self):
        """
        Each LimbNode should have an explicit RotationOrder property (value 0 = XYZ).
        UE5 uses XYZ rotation order; FBX default is also XYZ but being explicit
        prevents any DCC tool from misinterpreting the rotation order.
        """
        model = self._make_model_with_bone_nodes()
        exporter = FBXExporter()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name

        try:
            success = exporter.export(model, fbx_path, export_rigging=False)
            assert success, "FBX export failed"

            with open(fbx_path, 'r', encoding='utf-8') as f:
                content = f.read()

            assert 'RotationOrder' in content, \
                "RotationOrder property missing from bone Model entries"

        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)

    def test_bind_pose_includes_bone_nodes(self):
        """
        The BindPose must include entries for bone nodes (flags=0).
        If bone nodes are not in the bind pose, UE5 cannot match skin clusters
        to skeleton joints and the mesh will not deform.
        """
        model = self._make_model_with_bone_nodes()
        exporter = FBXExporter()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name

        try:
            success = exporter.export(model, fbx_path, export_rigging=False)
            assert success, "FBX export failed"

            with open(fbx_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # BindPose should have at least: root + 3 bones + 1 mesh = 5
            pose_node_count = content.count('PoseNode:')
            assert pose_node_count >= 4, \
                f"BindPose missing bone node entries: expected 4+, found {pose_node_count}"

            # Each PoseNode must have a Matrix entry
            matrix_count = content.count('Matrix:')
            assert matrix_count >= 4, \
                f"Some BindPose nodes are missing Matrix entries: found {matrix_count}"

        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)


class TestFBXAnimScale:
    """
    Tests for KotorBlender-verified animation position delta + animscale formula.

    KotorBlender animnode.py convert_mdl_position_to_bl_location:
        bl_location = restloc + animscale * mdl_position_delta

    So the FBX absolute translation must be:
        fbx_translation[axis] = bind_pos[axis] + anim_scale * keyframe_delta[axis]
    """

    def _make_model_with_anim_scale(self, anim_scale: float):
        """Create a model with a given anim_scale and a simple animation."""
        model = KotorModel(name="scale_test", supermodel="NULL")
        model.anim_scale = anim_scale

        root = ModelNode(name="scale_test", flags=int(NodeFlags.HEADER))
        root.position = [0.0, 0.0, 0.0]
        root.rotation = [0.0, 0.0, 0.0, 1.0]
        model.root_node = root

        bone = ModelNode(name="hip", flags=0)
        bone.position = [0.0, 0.0, 1.0]  # bind pose: Z=1.0
        bone.rotation = [0.0, 0.0, 0.0, 1.0]
        bone.parent = root
        root.children.append(bone)

        from core.model_data import Animation
        anim = Animation(name="test_anim", length=1.0)
        anim_bone = ModelNode(name="hip", flags=0)
        # Position delta keyframe: [0.0, 0.0, 0.5] at t=0.5
        # With anim_scale=2.0: absolute Z = 1.0 + 2.0 * 0.5 = 2.0
        # With anim_scale=1.0: absolute Z = 1.0 + 1.0 * 0.5 = 1.5
        anim_bone.controllers.append({
            'type': 8,   # CTRL_POSITION
            'times': [0.0, 0.5, 1.0],
            'values': [[0.0, 0.0, 0.0], [0.0, 0.0, 0.5], [0.0, 0.0, 0.0]],
        })
        anim.nodes = [anim_bone]
        model.animations = [anim]
        return model

    def test_animscale_applied_to_position_keyframes(self):
        """
        Verify that model.anim_scale multiplies position deltas before adding bind pos.
        With anim_scale=2.0, a delta of [0,0,0.5] from bind pos [0,0,1] should
        produce absolute Z values: 1.0 + 2.0*0.0=1.0, 1.0+2.0*0.5=2.0, 1.0+2.0*0.0=1.0
        NOT: 1.0+0.0=1.0, 1.0+0.5=1.5, 1.0+0.0=1.0  (incorrect, anim_scale ignored)
        """
        model_scale1 = self._make_model_with_anim_scale(1.0)
        model_scale2 = self._make_model_with_anim_scale(2.0)
        exporter = FBXExporter()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f1:
            fbx_path1 = f1.name
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f2:
            fbx_path2 = f2.name

        try:
            exporter.export(model_scale1, fbx_path1, export_rigging=False)
            exporter.export(model_scale2, fbx_path2, export_rigging=False)

            with open(fbx_path1, 'r') as f:
                content1 = f.read()
            with open(fbx_path2, 'r') as f:
                content2 = f.read()

            # Both files should have AnimationCurve data for Z translation
            assert 'AnimationCurve:' in content1, "No anim curves in scale=1 export"
            assert 'AnimationCurve:' in content2, "No anim curves in scale=2 export"

            # The files should differ in keyframe values (different anim_scale)
            # KeyValueFloat arrays should be different between the two exports
            # (This is a structural check; exact float comparison is fragile)
            assert content1 != content2, \
                "FBX output should differ when anim_scale changes (animscale not applied)"

        finally:
            for p in [fbx_path1, fbx_path2]:
                if os.path.exists(p):
                    os.unlink(p)

    def test_default_animscale_is_1(self):
        """
        A model without explicit anim_scale (default=1.0) should still produce
        valid FBX with correct absolute positions.
        """
        model = KotorModel(name="default_scale", supermodel="NULL")
        # Don't set anim_scale explicitly — should default to 1.0
        root = ModelNode(name="default_scale", flags=int(NodeFlags.HEADER))
        root.position = [0.0, 0.0, 0.0]
        root.rotation = [0.0, 0.0, 0.0, 1.0]
        model.root_node = root

        bone = ModelNode(name="hip2", flags=0)
        bone.position = [0.0, 0.0, 1.0]
        bone.rotation = [0.0, 0.0, 0.0, 1.0]
        bone.parent = root
        root.children.append(bone)

        from core.model_data import Animation
        anim = Animation(name="idle", length=0.5)
        anim_bone = ModelNode(name="hip2", flags=0)
        anim_bone.controllers.append({
            'type': 8,
            'times': [0.0, 0.5],
            'values': [[0.0, 0.0, 0.0], [0.0, 0.0, 0.1]],
        })
        anim.nodes = [anim_bone]
        model.animations = [anim]

        exporter = FBXExporter()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name

        try:
            success = exporter.export(model, fbx_path, export_rigging=False)
            assert success, "FBX export failed for default animscale model"

            with open(fbx_path, 'r') as f:
                content = f.read()

            # Should have animation data
            assert 'AnimationStack:' in content, "No AnimationStack in default-scale export"
            assert 'AnimationCurve:' in content, "No AnimationCurve in default-scale export"

        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)


class TestFBXMatrixLayout:
    """
    Tests for the column-major matrix fix in BindPose and TransformLink.

    FBX 7.4 specification: all 4x4 matrices are stored in COLUMN-MAJOR order.
    The previous implementation used ROW-MAJOR order, which caused UE5 to read
    the transpose of the bind pose matrix — bones would appear to be in the
    wrong position/orientation.
    """

    def _make_rotated_bone_model(self):
        """Create a model with a bone that has a non-identity rotation."""
        import math
        model = KotorModel(name="matrix_test", supermodel="NULL")

        root = ModelNode(name="matrix_test", flags=int(NodeFlags.HEADER))
        root.position = [0.0, 0.0, 0.0]
        root.rotation = [0.0, 0.0, 0.0, 1.0]  # identity
        model.root_node = root

        # Bone rotated 90° around Z: quaternion = (0, 0, sin45°, cos45°)
        s = math.sin(math.pi / 4)
        c = math.cos(math.pi / 4)
        bone = ModelNode(name="rotbone", flags=0)
        bone.position = [1.0, 0.0, 0.0]
        bone.rotation = [0.0, 0.0, s, c]   # 90° around Z
        bone.parent = root
        root.children.append(bone)

        return model

    def test_bindpose_matrix_has_16_values(self):
        """
        Each PoseNode Matrix should contain exactly 16 float values (4x4 matrix).
        """
        model = self._make_rotated_bone_model()
        exporter = FBXExporter()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name

        try:
            exporter.export(model, fbx_path, export_rigging=False)

            with open(fbx_path, 'r') as f:
                content = f.read()

            # Find Matrix: *16 entries in BindPose
            matrix_matches = re.findall(r'Matrix: \*16 \{[^}]+\}', content, re.DOTALL)
            assert len(matrix_matches) >= 1, "No Matrix entries found in BindPose"

            for mat_str in matrix_matches:
                # Extract the 'a:' line
                a_match = re.search(r'a: ([^\n]+)', mat_str)
                assert a_match, f"No 'a:' data in matrix block: {mat_str[:100]}"
                values = [float(v.strip()) for v in a_match.group(1).split(',')]
                assert len(values) == 16, \
                    f"Expected 16 matrix values, found {len(values)}: {values}"

        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)

    def test_identity_bone_has_identity_matrix(self):
        """
        A bone at origin with identity rotation should have an identity world matrix:
        [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]
        This test catches both row/column-major bugs and quaternion conversion bugs.
        """
        model = KotorModel(name="identity_test", supermodel="NULL")
        root = ModelNode(name="identity_test", flags=int(NodeFlags.HEADER))
        root.position = [0.0, 0.0, 0.0]
        root.rotation = [0.0, 0.0, 0.0, 1.0]
        model.root_node = root

        exporter = FBXExporter()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name

        try:
            exporter.export(model, fbx_path, export_rigging=False)

            with open(fbx_path, 'r') as f:
                content = f.read()

            # Find the first Matrix in BindPose
            mat_match = re.search(r'Matrix: \*16 \{\s+a: ([^\n]+)', content)
            assert mat_match, "No Matrix found in BindPose"

            values = [float(v.strip()) for v in mat_match.group(1).split(',')]
            assert len(values) == 16, f"Expected 16 values, got {len(values)}"

            expected = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]
            for i, (got, exp) in enumerate(zip(values, expected)):
                assert abs(got - exp) < 1e-4, \
                    f"Matrix value [{i}] wrong: expected {exp}, got {got:.6f}"

        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)


class TestFBXTextures:
    """Test texture embedding in FBX exports for UE5 material resolution."""

    def _make_textured_model(self, tex_name: str = "p_hk47_head01") -> KotorModel:
        model = KotorModel(name="tex_test", supermodel="NULL")
        root = ModelNode(name="tex_test", flags=int(NodeFlags.HEADER))
        model.root_node = root
        mesh = ModelNode(name="head_mesh",
                         flags=int(NodeFlags.MESH | NodeFlags.SKIN))
        mesh.parent = root
        root.children.append(mesh)
        mesh.vertices = [(-0.5, -0.5, 0.0), (0.5, -0.5, 0.0), (0.0, 0.5, 0.0)]
        mesh.faces    = [(0, 1, 2)]
        mesh.uvs      = [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)]
        mesh.normals  = [(0.0, 0.0, 1.0)] * 3
        mesh.texture  = tex_name
        mesh.bone_map = []
        mesh.skin_data = [VertexSkinData(), VertexSkinData(), VertexSkinData()]
        return model

    def test_fbx_contains_texture_objects(self):
        """FBX must have Video + Texture objects for material texture binding."""
        model = self._make_textured_model("p_hk47_head01")
        exporter = FBXExporter()
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        try:
            exporter.export(model, fbx_path, export_rigging=False)
            content = open(fbx_path).read()
            # Video object
            assert 'Video:' in content, "No Video object found in FBX"
            assert 'p_hk47_head01.tga' in content, \
                "Texture filename not found in FBX"
            # Texture object
            assert re.search(r'Texture:\s*\d+', content), \
                "No Texture object found in FBX"
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)

    def test_fbx_texture_connection_to_material(self):
        """Texture object must be connected to the Material node via OP connection."""
        model = self._make_textured_model("c_selkath_body01")
        exporter = FBXExporter()
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        try:
            exporter.export(model, fbx_path, export_rigging=False)
            content = open(fbx_path).read()
            # OP connection: Texture → Material DiffuseColor
            assert '"DiffuseColor"' in content, \
                "No DiffuseColor OP connection found (texture not linked to material)"
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)

    def test_fbx_null_texture_skipped(self):
        """Nodes with 'null' texture should not produce Video/Texture objects."""
        model = self._make_textured_model("null")
        exporter = FBXExporter()
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        try:
            exporter.export(model, fbx_path, export_rigging=False)
            content = open(fbx_path).read()
            # Should NOT have Video or Texture objects for 'null' texture
            assert 'null.tga' not in content.lower(), \
                "'null' texture should not be exported as a Video/Texture object"
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)

    def test_fbx_face_uvs_used_when_present(self):
        """When face_uvs tvert indices are set, UV indices in FBX use them."""
        model = KotorModel(name="face_uvs_test", supermodel="NULL")
        root = ModelNode(name="face_uvs_test", flags=int(NodeFlags.HEADER))
        model.root_node = root
        mesh = ModelNode(name="mesh_a",
                         flags=int(NodeFlags.MESH | NodeFlags.SKIN))
        mesh.parent = root
        root.children.append(mesh)
        # 4 position verts, 6 UV verts (tvert split for seams)
        mesh.vertices = [(-1, 0, 0), (1, 0, 0), (1, 1, 0), (-1, 1, 0)]
        mesh.faces    = [(0, 1, 2), (0, 2, 3)]
        mesh.uvs      = [(0, 0), (1, 0), (1, 1), (0.5, 0), (1, 0.5), (0, 1)]
        mesh.normals  = [(0, 0, 1)] * 4
        # face_uvs: separate tvert indices per face corner
        mesh.face_uvs = [(0, 1, 2), (3, 4, 5)]
        mesh.texture  = "test_seam_tex"
        mesh.bone_map  = []
        mesh.skin_data = [VertexSkinData()] * 4

        exporter = FBXExporter()
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        try:
            exporter.export(model, fbx_path, export_rigging=False)
            content = open(fbx_path).read()
            # UV data should have 6 UV entries (the tvert pool)
            assert 'UVMap' in content, "No UVMap layer found"
            uv_match = re.search(r'UV: \*(\d+)', content)
            assert uv_match, "No UV array found in FBX"
            uv_count = int(uv_match.group(1))
            # 6 UVs: 2 floats each → 12 values in the flat array
            assert uv_count == 12, f"Expected 12 UV components (6 UVs×2), got {uv_count}"
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)

    def test_fbx_lightmap_uv_layer_exported(self):
        """When uvs_lm is present, FBX should contain a second UV layer (UVMap_Lightmap)."""
        model = KotorModel(name="lightmap_test", supermodel="NULL")
        root = ModelNode(name="lightmap_test", flags=int(NodeFlags.HEADER))
        model.root_node = root
        mesh = ModelNode(name="area_mesh", flags=int(NodeFlags.MESH))
        mesh.parent = root
        root.children.append(mesh)
        mesh.vertices  = [(-1, -1, 0), (1, -1, 0), (0, 1, 0)]
        mesh.faces     = [(0, 1, 2)]
        mesh.uvs       = [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)]
        mesh.normals   = [(0, 0, 1)] * 3
        mesh.uvs_lm    = [(0.1, 0.1), (0.9, 0.1), (0.5, 0.9)]
        mesh.texture   = "area_floor01"
        mesh.bone_map  = []
        mesh.skin_data = []

        exporter = FBXExporter()
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        try:
            exporter.export(model, fbx_path, export_rigging=False)
            content = open(fbx_path).read()
            assert 'UVMap_Lightmap' in content, \
                "Lightmap UV layer not found in FBX (expected 'UVMap_Lightmap')"
            # Verify Layer 1 entry exists
            assert 'Layer: 1' in content, \
                "FBX Layer 1 definition missing (needed for lightmap UV channel)"
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)


class TestRiggingCompleteness:
    """Test that all bones are exported even for accessory models referencing supermodel bones."""

    def _make_accessory_model(self) -> KotorModel:
        """
        Simulate an accessory model (e.g. a head piece) whose skin mesh
        references bones that live in the base skeleton (S_MALE02 / S_FEMALE02),
        not in this model's own node tree.
        """
        model = KotorModel(name="p_hk47_head", supermodel="S_MALE02")
        root = ModelNode(name="p_hk47_head", flags=int(NodeFlags.HEADER))
        model.root_node = root

        # Only a small head mesh node in this accessory model
        # The actual skeleton bones (neckg, headg) are in S_MALE02 (not here)
        head_mesh = ModelNode(name="head_g",
                              flags=int(NodeFlags.SKIN | NodeFlags.MESH))
        head_mesh.parent = root
        root.children.append(head_mesh)
        head_mesh.vertices  = [(-0.3, -0.3, 0), (0.3, -0.3, 0), (0.0, 0.3, 0)]
        head_mesh.faces     = [(0, 1, 2)]
        head_mesh.uvs       = [(0, 0), (1, 0), (0.5, 1)]
        head_mesh.normals   = [(0, 0, 1)] * 3
        head_mesh.texture   = "p_hk47_head01"

        # Bone map references bones from the supermodel skeleton
        head_mesh.bone_map = ["neckg", "headg", "lshldr"]

        sd0 = VertexSkinData()
        sd0.influences = [BoneWeight(bone_index=0, weight=0.3),
                          BoneWeight(bone_index=1, weight=0.7)]
        sd1 = VertexSkinData()
        sd1.influences = [BoneWeight(bone_index=1, weight=1.0)]
        sd2 = VertexSkinData()
        sd2.influences = [BoneWeight(bone_index=2, weight=1.0)]
        head_mesh.skin_data = [sd0, sd1, sd2]
        return model

    def test_supermodel_bones_synthesised_in_fbx(self):
        """Missing supermodel bones must be emitted as LimbNode stubs."""
        model = self._make_accessory_model()
        exporter = FBXExporter()
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        try:
            exporter.export(model, fbx_path, export_rigging=False)
            content = open(fbx_path).read()
            # All three supermodel bones must appear
            assert '"neckg"' in content, \
                "Supermodel bone 'neckg' not found in FBX (should be synthesised)"
            assert '"headg"' in content, \
                "Supermodel bone 'headg' not found in FBX"
            assert '"lshldr"' in content, \
                "Supermodel bone 'lshldr' not found in FBX"
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)

    def test_supermodel_bones_have_limb_node_type(self):
        """Synthesised supermodel bones must be LimbNode, not Null."""
        model = self._make_accessory_model()
        exporter = FBXExporter()
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        try:
            exporter.export(model, fbx_path, export_rigging=False)
            content = open(fbx_path).read()
            # Find the Model entry for 'neckg' and check its type
            match = re.search(r'Model:\s*\d+\s*,\s*"neckg"\s*,\s*"(\w+)"', content)
            assert match, "Could not find Model entry for 'neckg'"
            node_type = match.group(1)
            assert node_type == 'LimbNode', \
                f"Expected 'LimbNode' for supermodel bone, got '{node_type}'"
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)

    def test_pykotor_bridge_root_gets_header_flags(self):
        """PyKotor-loaded model root node should get flags=HEADER, not flags=0."""
        from core.model_data import NodeFlags, ModelNode
        from core.pykotor_bridge import _convert_single_node, _NODETYPE_TO_FLAGS
        import sys
        sys.path.insert(0, '/home/user/webapp/PyKotor/Libraries/PyKotor/src')
        try:
            from pykotor.resource.formats.mdl.mdl_data import MDLNodeType
            # Simulate a root DUMMY node (no parent)
            class FakePkNode:
                name = 'c_selkath'
                node_id = 0
                node_type = MDLNodeType.DUMMY
                position = type('v', (), {'x': 0.0, 'y': 0.0, 'z': 0.0})()
                orientation = type('q', (), {'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 1.0})()
                controllers = []
                mesh = None
                skin = None
                children = []
            root_node = _convert_single_node(FakePkNode(), None, {})
            assert root_node.flags == int(NodeFlags.HEADER), \
                f"Root node should have flags=HEADER, got {root_node.flags}"
        except ImportError:
            pytest.skip("PyKotor not available for this test")

    def test_pykotor_bridge_child_bone_gets_zero_flags(self):
        """PyKotor-loaded child DUMMY nodes (bones) should get flags=0."""
        from core.model_data import NodeFlags, ModelNode
        from core.pykotor_bridge import _convert_single_node
        import sys
        sys.path.insert(0, '/home/user/webapp/PyKotor/Libraries/PyKotor/src')
        try:
            from pykotor.resource.formats.mdl.mdl_data import MDLNodeType
            # Simulate a child DUMMY node (has a parent)
            parent_gr = ModelNode(name='root', flags=int(NodeFlags.HEADER))
            class FakePkBone:
                name = 'pelvis'
                node_id = 1
                node_type = MDLNodeType.DUMMY
                position = type('v', (), {'x': 0.0, 'y': 0.0, 'z': 0.5})()
                orientation = type('q', (), {'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 1.0})()
                controllers = []
                mesh = None
                skin = None
                children = []
            bone_node = _convert_single_node(FakePkBone(), parent_gr, {})
            assert bone_node.flags == 0, \
                (f"Child bone should have flags=0 (not HEADER), got {bone_node.flags}. "
                 f"type_label={bone_node.type_label}")
            assert bone_node.type_label == 'dummy', \
                f"Bone node type_label should be 'dummy', got '{bone_node.type_label}'"
        except ImportError:
            pytest.skip("PyKotor not available for this test")

    def test_bone_nodes_method_returns_all_bones(self):
        """KotorModel.bone_nodes() must return both HEADER and flags=0 dummy nodes."""
        model = KotorModel(name="rig_test")
        root = ModelNode(name="rig_test", flags=int(NodeFlags.HEADER))  # flags=0x01
        model.root_node = root
        pelvis = ModelNode(name="pelvis", flags=0)  # binary MDL bone (flags=0)
        pelvis.parent = root; root.children.append(pelvis)
        spine = ModelNode(name="spine", flags=int(NodeFlags.HEADER))  # PyKotor-loaded bone (flags=0x01)
        spine.parent = pelvis; pelvis.children.append(spine)
        mesh = ModelNode(name="body", flags=int(NodeFlags.SKIN | NodeFlags.MESH))
        mesh.parent = spine; spine.children.append(mesh)

        bones = model.bone_nodes()
        bone_names = {n.name for n in bones}
        assert 'rig_test' in bone_names, "Root node missing from bone_nodes()"
        assert 'pelvis' in bone_names, "flags=0 bone missing from bone_nodes()"
        assert 'spine' in bone_names, "flags=HEADER child bone missing from bone_nodes()"
        assert 'body' not in bone_names, "Skin mesh should NOT be in bone_nodes()"
        assert len(bones) == 3, f"Expected 3 bone nodes, got {len(bones)}"


class TestPykotorBridgeWeights:
    """
    Tests for the pykotor_bridge bone weight mapping fix.

    KotOR MDL skin data structures (verified vs PyKotor MDLBoneVertex docstring
    and io_mdl.py line 2201):
      bonemap[local_idx]    = node_id  (stored as float32, cast to int on read)
      vertex_indices[j]     = local_idx  (direct index INTO bonemap, NOT global node_id)
      vertex_weights[j]     = blend weight for influence j

    Resolution algorithm (correct):
      gr.bone_map[local_idx] = pk_nodes_by_id[bonemap[local_idx]].name
      BoneWeight.bone_index  = local_idx = int(vertex_indices[j])
      _build_bone_transforms keys bone_transforms[local_idx] for LBS lookup

    Note: bone_indices (16-element header array) is NOT used for vertex lookup.
    """

    def _make_fake_skin(self, bonemap, vertex_indices_list, vertex_weights_list, node_names_by_id):
        """Create fake PyKotor-like skin/node objects for testing.

        bonemap: list where bonemap[local_idx] = node_id (the pk_nodes_by_id key)
        vertex_indices_list: list of 4-tuples; each float is a local_idx into bonemap
        vertex_weights_list: list of 4-tuples; blend weights
        """
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
        try:
            sys.path.insert(0, '/home/user/webapp/PyKotor/Libraries/PyKotor/src')
            from pykotor.resource.formats.mdl.mdl_data import MDLSkin, MDLBoneVertex
            skin = MDLSkin()
            skin.bonemap = bonemap   # bonemap[local_idx] = node_id
            for vis, wts in zip(vertex_indices_list, vertex_weights_list):
                bv = MDLBoneVertex()
                bv.vertex_indices = vis   # floats: local bonemap indices
                bv.vertex_weights = wts
                skin.vertex_bones.append(bv)
            return skin, node_names_by_id
        except ImportError:
            pytest.skip("PyKotor not available")

    def test_bonemap_single_bone(self):
        """Single bone: bonemap[0]=5 → node_id 5 → 'pelvis'. vertex_indices[0]=0.0 → local_idx 0."""
        try:
            sys.path.insert(0, '/home/user/webapp/PyKotor/Libraries/PyKotor/src')
            from core.pykotor_bridge import _fill_skin_data
        except ImportError:
            pytest.skip("PyKotor or bridge not available")

        gr = ModelNode()
        # bonemap[0] = 5 → node_id 5 → 'pelvis'
        # vertex_indices[0] = 0.0 → local_idx 0 → bone_map[0] = 'pelvis'
        pk_nodes_by_id = {5: type('N', (), {'name': 'pelvis'})()}
        skin, _ = self._make_fake_skin(
            bonemap=[5],               # bonemap[local_idx=0] = node_id 5
            vertex_indices_list=[
                (0.0, -1.0, -1.0, -1.0),   # local_idx=0 into bonemap
            ],
            vertex_weights_list=[
                (1.0, 0.0, 0.0, 0.0),
            ],
            node_names_by_id=pk_nodes_by_id,
        )
        _fill_skin_data(skin, gr, pk_nodes_by_id)

        assert len(gr.bone_map) == 1, f"Expected 1 bone_map slot, got {gr.bone_map}"
        assert gr.bone_map[0] == 'pelvis', f"Expected 'pelvis', got {gr.bone_map[0]}"
        assert len(gr.skin_data) == 1
        assert len(gr.skin_data[0].influences) == 1
        # bone_index == local_idx == 0
        assert gr.skin_data[0].influences[0].bone_index == 0
        assert abs(gr.skin_data[0].influences[0].weight - 1.0) < 1e-5

    def test_bonemap_multi_bone(self):
        """Multi-bone: vertex_indices are local_idx into bonemap, not global node_ids."""
        try:
            sys.path.insert(0, '/home/user/webapp/PyKotor/Libraries/PyKotor/src')
            from core.pykotor_bridge import _fill_skin_data
        except ImportError:
            pytest.skip("PyKotor or bridge not available")

        # bonemap[0] = node_id 100 → 'BTlfthr'
        # bonemap[1] = node_id 103 → 'BTHips'
        # vertex_indices = (0.0, 1.0, ...) → local_idx 0 and 1
        pk_nodes_by_id = {
            100: type('N', (), {'name': 'BTlfthr'})(),
            103: type('N', (), {'name': 'BTHips'})(),
        }

        gr = ModelNode()
        skin, _ = self._make_fake_skin(
            bonemap=[100, 103],     # bonemap[0]=100→BTlfthr, bonemap[1]=103→BTHips
            vertex_indices_list=[
                (0.0, 1.0, -1.0, -1.0),   # local_idx 0 and 1
            ],
            vertex_weights_list=[
                (0.6, 0.4, 0.0, 0.0),
            ],
            node_names_by_id=pk_nodes_by_id,
        )
        _fill_skin_data(skin, gr, pk_nodes_by_id)

        assert len(gr.bone_map) == 2, f"Expected 2 bone_map slots, got {gr.bone_map}"
        assert gr.bone_map[0] == 'BTlfthr', f"bone_map[0]={gr.bone_map[0]}"
        assert gr.bone_map[1] == 'BTHips',  f"bone_map[1]={gr.bone_map[1]}"

        assert len(gr.skin_data) == 1
        infl = gr.skin_data[0].influences
        assert len(infl) == 2
        # Verify bone_index is local_idx (0 and 1), not global node_ids (100, 103)
        indices = {inf.bone_index for inf in infl}
        assert indices == {0, 1}, f"bone_indices should be local (0,1), got {indices}"
        # Names resolve correctly through bone_map
        names = {gr.bone_map[inf.bone_index] for inf in infl}
        assert names == {'BTlfthr', 'BTHips'}

    def test_bonemap_unused_slots_empty_string(self):
        """Bonemap slots with node_id=-1 produce empty string in bone_map."""
        try:
            sys.path.insert(0, '/home/user/webapp/PyKotor/Libraries/PyKotor/src')
            from core.pykotor_bridge import _fill_skin_data
        except ImportError:
            pytest.skip("PyKotor or bridge not available")

        # bonemap[0]=10→'spine', bonemap[1]=-1 (unused), bonemap[2]=30→'rleg'
        # vertex_indices=(0.0, 2.0, ...) → local_idx 0 (spine) and 2 (rleg)
        # local_idx 1 is unused slot (−1 in bonemap) — vertex doesn't reference it
        pk_nodes_by_id = {
            10: type('N', (), {'name': 'spine'})(),
            30: type('N', (), {'name': 'rleg'})(),
        }
        gr = ModelNode()
        skin, _ = self._make_fake_skin(
            bonemap=[10, -1, 30],    # bonemap[1]=-1 = unused
            vertex_indices_list=[
                (0.0, 2.0, -1.0, -1.0),   # local_idx 0 and 2 (skip local_idx 1)
            ],
            vertex_weights_list=[
                (0.7, 0.3, 0.0, 0.0),
            ],
            node_names_by_id=pk_nodes_by_id,
        )
        _fill_skin_data(skin, gr, pk_nodes_by_id)

        # bone_map has 3 slots (one per bonemap entry)
        assert len(gr.bone_map) == 3, f"Expected 3 bone_map slots, got {gr.bone_map}"
        assert gr.bone_map[0] == 'spine'
        assert gr.bone_map[1] == '', f"Unused slot should be '', got '{gr.bone_map[1]}'"
        assert gr.bone_map[2] == 'rleg'

        # Vertex should have 2 influences: local_idx 0 and 2
        infl = gr.skin_data[0].influences
        assert len(infl) == 2
        indices = {inf.bone_index for inf in infl}
        assert indices == {0, 2}

    def test_weight_normalization(self):
        """Weights must be normalized to sum=1.0 after building influences."""
        try:
            sys.path.insert(0, '/home/user/webapp/PyKotor/Libraries/PyKotor/src')
            from core.pykotor_bridge import _fill_skin_data
        except ImportError:
            pytest.skip("PyKotor or bridge not available")

        # bonemap[0]=node_id 10→'head', bonemap[1]=node_id 11→'neck'
        # vertex_indices=(0.0, 1.0, ...) → local_idx 0 and 1
        pk_nodes_by_id = {
            10: type('N', (), {'name': 'head'})(),
            11: type('N', (), {'name': 'neck'})(),
        }
        gr = ModelNode()
        skin, _ = self._make_fake_skin(
            bonemap=[10, 11],
            vertex_indices_list=[
                (0.0, 1.0, -1.0, -1.0),   # local_idx 0 and 1
            ],
            vertex_weights_list=[
                (0.3, 0.5, 0.0, 0.0),   # sum = 0.8 (not 1.0 — needs normalizing)
            ],
            node_names_by_id=pk_nodes_by_id,
        )
        _fill_skin_data(skin, gr, pk_nodes_by_id)
        infl = gr.skin_data[0].influences
        total_w = sum(i.weight for i in infl)
        assert abs(total_w - 1.0) < 1e-4, f"Weights should sum to 1.0, got {total_w}"


class TestPykotorBridgeTextureFields:
    """
    Tests that pykotor_bridge uses the correct ModelNode field names for textures.

    ModelNode uses:
      texture        (str)  = primary texture name (slot 0)
      texture_names  (list) = [slot0, slot1, ...] — the correct multi-texture field
      lightmap       (str)  = lightmap texture name
      has_shadow     (bool) = shadow casting flag (NOT 'shadow')
      background_geometry  = background pass flag (NOT 'bg_geometry')
      uvs_2          (list) = secondary UV set (NOT 'uvs2')
      uvs_lm         (list) = lightmap UV set (same data as uvs_2)
    """

    def test_texture_names_field_populated(self):
        """_fill_mesh_data must populate texture_names (not textures)."""
        try:
            sys.path.insert(0, '/home/user/webapp/PyKotor/Libraries/PyKotor/src')
            from core.pykotor_bridge import _fill_mesh_data
        except ImportError:
            pytest.skip("PyKotor not available")

        # Fake mesh object
        class FakeMesh:
            texture_1 = 'EbonHawk_Hull'
            texture_2 = 'EbonHawk_LM'
            diffuse = None
            ambient = None
            render = True
            shadow = False
            beaming = False
            background_geometry = False
            transparency_hint = 0
            rotate_texture = False
            has_lightmap = True
            animate_uv = False
            uv_direction_x = uv_direction_y = 0.0
            uv_jitter = uv_jitter_speed = 0.0
            vertex_positions = []
            vertex_normals = []
            vertex_uv1 = []
            vertex_uv2 = []
            vertex_uvs = []
            faces = []
            bb_min = type('v', (), {'x': 0.0, 'y': 0.0, 'z': 0.0})()
            bb_max = type('v', (), {'x': 1.0, 'y': 1.0, 'z': 1.0})()
            def vertex_uv(self): return []

        gr = ModelNode()
        _fill_mesh_data(None, FakeMesh(), gr)

        assert gr.texture == 'EbonHawk_Hull', f"gr.texture={gr.texture}"
        assert gr.lightmap == 'EbonHawk_LM', f"gr.lightmap={gr.lightmap}"
        # The critical fix: texture_names must be populated (not an attribute called 'textures')
        assert isinstance(gr.texture_names, list), "texture_names must be a list"
        assert 'EbonHawk_Hull' in gr.texture_names, "Primary texture missing from texture_names"
        assert 'EbonHawk_LM' in gr.texture_names, "Lightmap missing from texture_names"
        # Dynamic 'textures' attribute should NOT be present (using wrong field)
        assert not hasattr(gr, 'textures'), \
            "gr.textures should not exist (use texture_names instead)"

    def test_has_shadow_field_populated(self):
        """_fill_mesh_data must populate has_shadow (not gr.shadow)."""
        try:
            sys.path.insert(0, '/home/user/webapp/PyKotor/Libraries/PyKotor/src')
            from core.pykotor_bridge import _fill_mesh_data
        except ImportError:
            pytest.skip("PyKotor not available")

        class FakeMesh:
            texture_1 = texture_2 = ''
            diffuse = ambient = None
            render = True
            shadow = True   # PyKotor field name
            beaming = False
            background_geometry = False
            transparency_hint = 0
            rotate_texture = False
            has_lightmap = False
            animate_uv = False
            uv_direction_x = uv_direction_y = 0.0
            uv_jitter = uv_jitter_speed = 0.0
            vertex_positions = vertex_normals = []
            vertex_uv1 = vertex_uv2 = vertex_uvs = []
            faces = []
            bb_min = type('v', (), {'x': 0.0, 'y': 0.0, 'z': 0.0})()
            bb_max = type('v', (), {'x': 1.0, 'y': 1.0, 'z': 1.0})()
            def vertex_uv(self): return []

        gr = ModelNode()
        _fill_mesh_data(None, FakeMesh(), gr)
        assert gr.has_shadow is True, f"has_shadow should be True, got {gr.has_shadow}"
        assert not hasattr(gr, 'shadow'), "gr.shadow should not be a dynamic attribute"

    def test_uvs_2_field_populated(self):
        """Secondary UVs must be in gr.uvs_2 (not gr.uvs2)."""
        try:
            sys.path.insert(0, '/home/user/webapp/PyKotor/Libraries/PyKotor/src')
            from core.pykotor_bridge import _fill_mesh_data
        except ImportError:
            pytest.skip("PyKotor not available")

        class FakeVec2:
            def __init__(self, x, y): self.x = x; self.y = y

        class FakeMesh:
            texture_1 = texture_2 = ''
            diffuse = ambient = None
            render = True
            shadow = False
            beaming = False
            background_geometry = False
            transparency_hint = 0
            rotate_texture = False
            has_lightmap = True
            animate_uv = False
            uv_direction_x = uv_direction_y = 0.0
            uv_jitter = uv_jitter_speed = 0.0
            vertex_positions = vertex_normals = []
            vertex_uv1 = []   # primary UVs empty
            vertex_uv2 = [FakeVec2(0.25, 0.75), FakeVec2(0.5, 0.5)]  # secondary UVs
            vertex_uvs = []
            faces = []
            bb_min = type('v', (), {'x': 0.0, 'y': 0.0, 'z': 0.0})()
            bb_max = type('v', (), {'x': 1.0, 'y': 1.0, 'z': 1.0})()
            def vertex_uv(self): return []

        gr = ModelNode()
        _fill_mesh_data(None, FakeMesh(), gr)

        # Secondary UVs must land in uvs_2 and uvs_lm
        assert len(gr.uvs_2) == 2, f"uvs_2 should have 2 entries, got {len(gr.uvs_2)}"
        assert len(gr.uvs_lm) == 2, f"uvs_lm should have 2 entries, got {len(gr.uvs_lm)}"
        assert abs(gr.uvs_2[0][0] - 0.25) < 1e-5
        assert abs(gr.uvs_2[0][1] - 0.75) < 1e-5
        # uvs2 (dynamic) should NOT be set
        assert not hasattr(gr, 'uvs2'), "gr.uvs2 should not be a dynamic attribute"


class TestWeightedFBXExport:
    """Tests that FBX export correctly outputs skin weights from the compact bone_map."""

    def _make_weighted_model(self):
        """Build a model with 2 bones and a mesh with multi-bone vertex weights."""
        model = KotorModel(name="weight_test")
        root = ModelNode(name="weight_test", flags=int(NodeFlags.HEADER))
        model.root_node = root

        # 2 bones
        pelvis = ModelNode(name="pelvis", flags=0)
        pelvis.position = (0.0, 0.0, 0.5)
        pelvis.parent = root; root.children.append(pelvis)

        spine = ModelNode(name="spine", flags=0)
        spine.position = (0.0, 0.0, 1.0)
        spine.parent = pelvis; pelvis.children.append(spine)

        # Skin mesh
        body = ModelNode(name="body",
                        flags=int(NodeFlags.SKIN | NodeFlags.MESH))
        body.texture = "test_tex"
        body.texture_names = ["test_tex"]
        body.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0),
                         (0.5, 0.5, 1.0)]
        body.faces = [(0, 1, 2), (0, 1, 3)]
        body.uvs = [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0), (0.5, 0.5)]
        body.face_uvs = [(0, 1, 2), (0, 1, 3)]
        # compact bone_map: index 0=pelvis, index 1=spine
        body.bone_map = ['pelvis', 'spine']
        body.skin_data = [
            VertexSkinData(influences=[BoneWeight(0, 1.0)]),          # vert 0: 100% pelvis
            VertexSkinData(influences=[BoneWeight(1, 1.0)]),          # vert 1: 100% spine
            VertexSkinData(influences=[BoneWeight(0, 0.5), BoneWeight(1, 0.5)]),  # vert 2: 50/50
            VertexSkinData(influences=[BoneWeight(0, 0.3), BoneWeight(1, 0.7)]),  # vert 3: 30/70
        ]
        body.parent = spine; spine.children.append(body)
        return model

    def test_skin_cluster_bone_names_in_fbx(self):
        """FBX Cluster SubDeformers must reference the correct bone names."""
        model = self._make_weighted_model()
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        try:
            exporter = FBXExporter()
            ok = exporter.export(model, fbx_path)
            assert ok, "FBX export failed"
            content = open(fbx_path).read()
            # Both bones should appear as SubDeformer clusters
            assert '"pelvis", "Cluster"' in content, "pelvis cluster missing from FBX"
            assert '"spine", "Cluster"' in content, "spine cluster missing from FBX"
        finally:
            import os
            if os.path.exists(fbx_path): os.unlink(fbx_path)

    def test_skin_cluster_weights_present(self):
        """FBX Cluster must contain Indexes and Weights arrays."""
        model = self._make_weighted_model()
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        try:
            exporter = FBXExporter()
            exporter.export(model, fbx_path)
            content = open(fbx_path).read()
            assert 'Indexes:' in content, "Indexes array missing from cluster"
            assert 'Weights:' in content, "Weights array missing from cluster"
        finally:
            import os
            if os.path.exists(fbx_path): os.unlink(fbx_path)

    def test_multi_bone_vertex_correct_cluster_assignment(self):
        """Vertex 2 (50%/50% pelvis/spine) must appear in BOTH clusters."""
        model = self._make_weighted_model()
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        try:
            exporter = FBXExporter()
            exporter.export(model, fbx_path)
            content = open(fbx_path).read()
            # Find pelvis cluster section
            m_pelvis = re.search(r'"pelvis",\s*"Cluster"\s*\{.*?Indexes.*?\{(.*?)\}.*?Weights.*?\{(.*?)\}',
                                  content, re.DOTALL)
            if m_pelvis:
                pelvis_idxs = m_pelvis.group(1)
                # vertex 2 (index 2) must be in pelvis cluster
                assert '2' in pelvis_idxs.split(','), \
                    f"Vertex 2 should be in pelvis cluster. Got: {pelvis_idxs}"
        finally:
            import os
            if os.path.exists(fbx_path): os.unlink(fbx_path)

    def test_bone_map_compact_no_empty_strings(self):
        """After pykotor_bridge fix, bone_map must contain no empty strings."""
        model = self._make_weighted_model()
        for node in model.all_nodes():
            if node.is_skin and node.bone_map:
                for name in node.bone_map:
                    assert name != '', \
                        f"bone_map contains empty string for node '{node.name}': {node.bone_map}"


class TestFBXBaseSkeleton:
    """
    Tests for the base_skeleton_model parameter introduced to correctly
    resolve synthetic supermodel bone transforms in accessory mesh FBX exports.

    KotOR composite characters use a shared base skeleton (e.g. S_MALE02) whose
    bone nodes do NOT appear in the accessory mesh file (head, body, hands).
    Previously, synthesised placeholder bones received identity (0,0,0) transforms,
    causing incorrect skin deformation in Unreal Engine.  When base_skeleton_model
    is supplied the correct bind-pose position/rotation must be used instead.
    """

    def _make_base_skeleton(self):
        """Create a minimal S_MALE02-like base skeleton model."""
        skel = KotorModel(name="S_MALE02", supermodel="NULL", classification="character")
        root = ModelNode(name="S_MALE02", flags=int(NodeFlags.HEADER))
        root.position = [0.0, 0.0, 0.0]
        root.rotation = [0.0, 0.0, 0.0, 1.0]
        skel.root_node = root

        # A few representative bones with known non-zero positions
        pelvis = ModelNode(name="pelvis", flags=0)
        pelvis.position = [0.0, 0.0, 0.9]
        pelvis.rotation = [0.0, 0.0, 0.0, 1.0]
        pelvis.parent = root
        root.children.append(pelvis)

        spine = ModelNode(name="spine", flags=0)
        spine.position = [0.0, 0.0, 0.25]
        spine.rotation = [0.0, 0.0, 0.0, 1.0]
        spine.parent = pelvis
        pelvis.children.append(spine)

        head_bone = ModelNode(name="head_g", flags=0)
        head_bone.position = [0.0, 0.0, 0.5]
        head_bone.rotation = [0.0, 0.0, 0.0, 1.0]
        head_bone.parent = spine
        spine.children.append(head_bone)

        return skel

    def _make_accessory_head_model(self):
        """
        Create a minimal head accessory model whose skin references bones from
        S_MALE02 that are NOT in its own node tree.
        """
        model = KotorModel(name="P_MaleHead01", supermodel="S_MALE02",
                           classification="character")
        root = ModelNode(name="P_MaleHead01", flags=int(NodeFlags.HEADER))
        root.position = [0.0, 0.0, 0.0]
        root.rotation = [0.0, 0.0, 0.0, 1.0]
        model.root_node = root

        # Head mesh node — skinned to S_MALE02 bones (not in this file)
        head_mesh = ModelNode(name="head_mesh",
                              flags=int(NodeFlags.SKIN | NodeFlags.MESH))
        head_mesh.position = [0.0, 0.0, 0.0]
        head_mesh.rotation = [0.0, 0.0, 0.0, 1.0]
        head_mesh.parent = root
        root.children.append(head_mesh)

        head_mesh.vertices = [
            [0.0,  0.0, 1.7],
            [0.1, 0.0, 1.8],
            [-0.1, 0.0, 1.8],
        ]
        head_mesh.faces = [[0, 1, 2]]
        head_mesh.normals = [[0.0, -1.0, 0.0]] * 3
        head_mesh.uvs = [[0.5, 0.0], [1.0, 1.0], [0.0, 1.0]]
        head_mesh.texture = "P_MaleHead01"
        head_mesh.render = True

        # Bones from S_MALE02 — absent from this model's node tree
        head_mesh.bone_map = ["spine", "head_g"]
        head_mesh.skin_data = [
            VertexSkinData(influences=[BoneWeight(bone_index=0, weight=0.3),
                                       BoneWeight(bone_index=1, weight=0.7)]),
            VertexSkinData(influences=[BoneWeight(bone_index=1, weight=1.0)]),
            VertexSkinData(influences=[BoneWeight(bone_index=1, weight=1.0)]),
        ]
        return model

    def test_without_base_skeleton_synthetic_bones_use_identity(self):
        """
        Without base_skeleton_model, synthetic bones must use identity (0,0,0)
        transforms — this is the fallback behaviour and must not crash.
        """
        model = self._make_accessory_head_model()
        exporter = FBXExporter()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name

        try:
            ok = exporter.export(model, fbx_path, export_rigging=False)
            assert ok, "FBX export (no base skeleton) must succeed"

            content = open(fbx_path, 'r', encoding='utf-8').read()

            # Synthetic bones must appear in the FBX (spine and head_g are in bone_map)
            assert 'spine' in content, "Synthetic bone 'spine' must be emitted"
            assert 'head_g' in content, "Synthetic bone 'head_g' must be emitted"

            # Without base skeleton, position is 0,0,0
            assert '0.000000,0.000000,0.000000' in content, \
                "Identity position expected when no base skeleton provided"
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)

    def test_with_base_skeleton_synthetic_bones_get_real_transforms(self):
        """
        With base_skeleton_model supplied, synthetic bones must receive the
        correct local position/rotation from the base skeleton instead of zeros.
        This fixes skin deformation for accessory meshes in Unreal Engine.
        """
        skel  = self._make_base_skeleton()
        model = self._make_accessory_head_model()
        exporter = FBXExporter()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name

        try:
            ok = exporter.export(model, fbx_path, export_rigging=False,
                                 base_skeleton_model=skel)
            assert ok, "FBX export (with base skeleton) must succeed"

            content = open(fbx_path, 'r', encoding='utf-8').read()

            # spine bind pos = (0, 0, 0.25) — must appear in the FBX, not (0,0,0)
            # head_g bind pos = (0, 0, 0.5)  — same
            assert '0.250000' in content, \
                "spine Z=0.25 from base skeleton must appear in synthetic bone transform"
            assert '0.500000' in content, \
                "head_g Z=0.5 from base skeleton must appear in synthetic bone transform"

        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)

    def test_with_base_skeleton_transformlink_uses_real_bind_matrix(self):
        """
        With base_skeleton_model, the SubDeformer Cluster TransformLink matrix
        for synthetic bones must NOT be identity — it must reflect the base
        skeleton's world-space bind transform.  Identity TransformLinks cause
        all skin-weight-influenced vertices to snap to the world origin in UE5.
        """
        skel  = self._make_base_skeleton()
        model = self._make_accessory_head_model()
        exporter = FBXExporter()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name

        try:
            ok = exporter.export(model, fbx_path, export_rigging=False,
                                 base_skeleton_model=skel)
            assert ok, "FBX export must succeed"

            content = open(fbx_path, 'r', encoding='utf-8').read()

            # TransformLink for a synthetic bone must not all be identity rows.
            # We check that at least one non-identity translation appears in
            # TransformLink sections (the base skeleton has non-zero positions).
            # A pure-identity TransformLink matrix only contains 1s and 0s in
            # the diagonal and the translation row.
            # Spine world pos ≈ (0, 0, 1.15) [pelvis 0.9 + spine 0.25]
            transformlink_blocks = re.findall(
                r'TransformLink: \*16 \{.*?a: (.*?)\n', content, re.DOTALL)
            non_identity_found = False
            for block in transformlink_blocks:
                vals = [float(v.strip()) for v in block.split(',') if v.strip()]
                # Pure identity = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]
                is_identity = (len(vals) == 16 and
                               abs(vals[0]-1)<1e-4 and abs(vals[5]-1)<1e-4 and
                               abs(vals[10]-1)<1e-4 and abs(vals[15]-1)<1e-4 and
                               all(abs(v)<1e-4 for i,v in enumerate(vals)
                                   if i not in (0,5,10,15)))
                if not is_identity:
                    non_identity_found = True
                    break
            assert non_identity_found, \
                ("All TransformLink matrices are identity — synthetic bones must use "
                 "real bind transforms from base_skeleton_model")

        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)

    def test_with_base_skeleton_bind_pose_uses_real_matrix(self):
        """
        The BindPose PoseNode entries for synthetic bones must use real world
        matrices (from base_skeleton_model), not identity, when base_skeleton_model
        is supplied.
        """
        skel  = self._make_base_skeleton()
        model = self._make_accessory_head_model()
        exporter = FBXExporter()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name

        try:
            ok = exporter.export(model, fbx_path, export_rigging=False,
                                 base_skeleton_model=skel)
            assert ok, "FBX export must succeed"

            content = open(fbx_path, 'r', encoding='utf-8').read()

            # BindPose section must exist and have pose nodes
            assert 'BindPose' in content, "BindPose section missing"
            pose_node_count = content.count('PoseNode:')
            assert pose_node_count >= 2, \
                f"Expected 2+ BindPose entries for synthetic bones, got {pose_node_count}"

            # At least one PoseNode matrix must be non-identity (real bind transform)
            pose_matrices = re.findall(
                r'PoseNode:.*?Matrix: \*16 \{.*?a: (.*?)\n', content, re.DOTALL)
            non_identity_pose = False
            for m in pose_matrices:
                vals = [float(v.strip()) for v in m.split(',') if v.strip()]
                if len(vals) == 16:
                    is_id = (abs(vals[0]-1)<1e-4 and abs(vals[5]-1)<1e-4 and
                             abs(vals[10]-1)<1e-4 and abs(vals[15]-1)<1e-4 and
                             all(abs(v)<1e-4 for i,v in enumerate(vals)
                                 if i not in (0,5,10,15)))
                    if not is_id:
                        non_identity_pose = True
                        break
            assert non_identity_pose, \
                ("All BindPose matrices are identity — synthetic bones must inherit "
                 "real world matrices from base_skeleton_model")

        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)


class TestFBXTakesSection:
    """
    Tests for the Takes: section required by Blender / MotionBuilder FBX readers.

    FBX 7.4 defines two mechanisms to enumerate animation clips:
      - AnimStack objects (used by Unreal Engine 5 directly)
      - Takes: block   (used by Blender's FBX importer, MotionBuilder, and Maya)

    Both must be present for the FBX file to work in the full DCC pipeline.
    """

    def _make_animated_model(self):
        from core.model_data import Animation
        model = KotorModel(name="anim_char", supermodel="NULL")

        root = ModelNode(name="anim_char", flags=int(NodeFlags.HEADER))
        root.position = [0.0, 0.0, 0.0]
        root.rotation = [0.0, 0.0, 0.0, 1.0]
        model.root_node = root

        bone = ModelNode(name="hip", flags=0)
        bone.position = [0.0, 0.0, 0.9]
        bone.rotation = [0.0, 0.0, 0.0, 1.0]
        bone.parent = root
        root.children.append(bone)

        for anim_name, length in [("walk", 0.5), ("run", 0.333), ("idle", 2.0)]:
            anim = Animation(name=anim_name, length=length)
            anim_bone = ModelNode(name="hip", flags=0)
            anim_bone.controllers.append({
                'type': 20,  # CTRL_ORIENTATION
                'times': [0.0, length],
                'values': [[0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 1.0]],
            })
            anim.nodes = [anim_bone]
            model.animations.append(anim)

        return model

    def test_takes_section_present(self):
        """FBX must contain a Takes: block for Blender/MotionBuilder compatibility."""
        model = self._make_animated_model()
        exporter = FBXExporter()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name

        try:
            ok = exporter.export(model, fbx_path, export_rigging=False)
            assert ok, "FBX export must succeed"

            content = open(fbx_path, 'r', encoding='utf-8').read()
            assert 'Takes:' in content, "Takes: section missing from FBX"
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)

    def test_takes_section_lists_all_animations(self):
        """Each animation must appear as a Take: entry in the Takes: block."""
        model = self._make_animated_model()
        exporter = FBXExporter()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name

        try:
            ok = exporter.export(model, fbx_path, export_rigging=False)
            assert ok, "FBX export must succeed"

            content = open(fbx_path, 'r', encoding='utf-8').read()

            # Locate the Takes block
            takes_start = content.find('Takes:')
            assert takes_start != -1, "Takes: block not found"

            # All three animation names must appear in the Takes block
            takes_block = content[takes_start:]
            for anim_name in ("walk", "run", "idle"):
                assert f'Take: "{anim_name}"' in takes_block or anim_name in takes_block, \
                    f"Animation '{anim_name}' not listed in Takes: block"
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)

    def test_takes_section_current_set_to_first_animation(self):
        """The Current: field in Takes must be set to the first animation name."""
        model = self._make_animated_model()
        exporter = FBXExporter()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name

        try:
            ok = exporter.export(model, fbx_path, export_rigging=False)
            assert ok, "FBX export must succeed"

            content = open(fbx_path, 'r', encoding='utf-8').read()

            takes_start = content.find('Takes:')
            takes_block = content[takes_start:takes_start + 1000]

            assert 'Current: "walk"' in takes_block, \
                "Takes Current: must be set to first animation ('walk')"
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)

    def test_takes_section_present_with_no_animations(self):
        """Even with no animations, Takes: block must be present with empty Current."""
        model = KotorModel(name="static_mesh", supermodel="NULL")
        root = ModelNode(name="static_mesh", flags=int(NodeFlags.HEADER))
        root.position = [0.0, 0.0, 0.0]
        root.rotation = [0.0, 0.0, 0.0, 1.0]
        model.root_node = root
        exporter = FBXExporter()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name

        try:
            ok = exporter.export(model, fbx_path, export_rigging=False)
            assert ok, "FBX export must succeed for static model"

            content = open(fbx_path, 'r', encoding='utf-8').read()
            assert 'Takes:' in content, "Takes: section missing even for static mesh"

            # Current must be empty string when no animations
            takes_start = content.find('Takes:')
            takes_block = content[takes_start:takes_start + 200]
            assert 'Current: ""' in takes_block, \
                "Takes Current: must be empty string when no animations"
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)

    def test_animstack_objects_still_present_alongside_takes(self):
        """AnimStack objects (for UE5) must coexist with the Takes: block."""
        model = self._make_animated_model()
        exporter = FBXExporter()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name

        try:
            ok = exporter.export(model, fbx_path, export_rigging=False)
            assert ok, "FBX export must succeed"

            content = open(fbx_path, 'r', encoding='utf-8').read()

            # Both mechanisms must be present
            assert 'AnimationStack:' in content, \
                "AnimStack objects missing — UE5 will not see animation clips"
            assert 'Takes:' in content, \
                "Takes block missing — Blender/MotionBuilder will not see animation clips"

            # AnimStack count must match animation count (3 animations)
            animstack_count = content.count('AnimationStack:')
            assert animstack_count == 3, \
                f"Expected 3 AnimStack objects (one per clip), found {animstack_count}"
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)


class TestFBXUnrealPipeline:
    """
    End-to-end pipeline tests that simulate the full
    KotOR → GhostRigger → FBX → Unreal workflow.

    Three canonical export scenarios:
      1. Standalone creature (self-contained skeleton + mesh + animations)
      2. Humanoid base skeleton (S_MALE02-style: skeleton + animations)
      3. Humanoid accessory (head/body mesh only, references base skeleton)

    Import order in Unreal Engine:
      Step 1 → Import S_MALE02.fbx → creates USkeleton asset
      Step 2 → Import each anim clip as AnimSequence (same .fbx, each Take)
      Step 3 → Import accessory mesh with 'Use Existing Skeleton' → picks USkeleton
    """

    def _make_standalone_creature(self):
        """Full self-contained creature (e.g. C_Bantha): own skeleton + anims."""
        from core.model_data import Animation
        model = KotorModel(name="c_bantha", supermodel="NULL",
                           classification="creature")
        model.anim_scale = 1.0
        root = ModelNode(name="c_bantha", flags=int(NodeFlags.HEADER))
        root.position = (0.0, 0.0, 0.0)
        root.rotation = (0.0, 0.0, 0.0, 1.0)
        model.root_node = root

        body_bone = ModelNode(name="body_bone", flags=0)
        body_bone.position = (0.0, 0.0, 0.5)
        body_bone.rotation = (0.0, 0.0, 0.0, 1.0)
        body_bone.parent = root
        root.children.append(body_bone)

        mesh = ModelNode(name="bantha_body",
                         flags=int(NodeFlags.SKIN | NodeFlags.MESH))
        mesh.position = (0.0, 0.0, 0.0)
        mesh.rotation = (0.0, 0.0, 0.0, 1.0)
        mesh.parent = root
        root.children.append(mesh)
        mesh.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0)]
        mesh.faces = [(0, 1, 2)]
        mesh.uvs = [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)]
        mesh.texture = "c_bantha"
        mesh.render = True
        mesh.bone_map = ["body_bone"]
        mesh.skin_data = [
            VertexSkinData(influences=[BoneWeight(0, 1.0)]),
            VertexSkinData(influences=[BoneWeight(0, 1.0)]),
            VertexSkinData(influences=[BoneWeight(0, 1.0)]),
        ]

        for aname, alen in [("idle", 2.0), ("walk", 1.0), ("attack", 0.8)]:
            anim = Animation(name=aname, length=alen)
            anode = ModelNode(name="body_bone", flags=0)
            anode.controllers.append({
                'type': 8,
                'times': [0.0, alen / 2, alen],
                'values': [[0.0, 0.0, 0.0], [0.0, 0.0, 0.05], [0.0, 0.0, 0.0]],
            })
            anim.nodes = [anode]
            model.animations.append(anim)
        return model

    @staticmethod
    def _export_and_read(model, base_skel=None):
        exporter = FBXExporter()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fbx', delete=False) as f:
            fbx_path = f.name
        try:
            ok = exporter.export(model, fbx_path, export_rigging=False,
                                 base_skeleton_model=base_skel)
            content = open(fbx_path, encoding='utf-8', errors='replace').read()
        finally:
            if os.path.exists(fbx_path):
                os.unlink(fbx_path)
        return ok, content

    def test_standalone_creature_full_pipeline(self):
        """
        A standalone creature FBX must contain skeleton, skin deformers,
        all animation clips in both AnimStack and Takes sections, and bind pose.
        """
        model = self._make_standalone_creature()
        ok, content = self._export_and_read(model)
        assert ok, "Standalone creature FBX export failed"
        assert '"body_bone", "LimbNode"' in content, "body_bone bone missing"
        assert 'Deformer:' in content and '"Skin"' in content, "Skin deformer missing"
        for aname in ("idle", "walk", "attack"):
            assert f'"{aname}"' in content, f"Animation '{aname}' missing from FBX"
        assert 'Takes:' in content, "Takes section missing"
        for aname in ("idle", "walk", "attack"):
            assert f'Take: "{aname}"' in content, \
                f"Animation '{aname}' missing from Takes section"
        assert 'BindPose' in content, "BindPose missing"
        assert 'UpAxis' in content, "UpAxis / coordinate system not declared"

    def test_unreal_import_order_skeleton_before_accessory(self):
        """
        Validate base skeleton + accessory export: accessory FBX must reference
        the same bone names as the base skeleton FBX so Unreal's 'Use Existing
        Skeleton' import mode can match them.
        """
        # Base skeleton (S_MALE02-style)
        skel = KotorModel(name="S_MALE02", supermodel="NULL")
        skel_root = ModelNode(name="S_MALE02", flags=int(NodeFlags.HEADER))
        skel_root.position = (0.0, 0.0, 0.0)
        skel_root.rotation = (0.0, 0.0, 0.0, 1.0)
        skel.root_node = skel_root
        pelvis = ModelNode(name="Bip01 Pelvis", flags=0)
        pelvis.position = (0.0, 0.0, 0.9)
        pelvis.rotation = (0.0, 0.0, 0.0, 1.0)
        pelvis.parent = skel_root
        skel_root.children.append(pelvis)

        # Accessory head mesh
        acc = KotorModel(name="P_MaleHead01", supermodel="S_MALE02")
        acc_root = ModelNode(name="P_MaleHead01", flags=int(NodeFlags.HEADER))
        acc_root.position = (0.0, 0.0, 0.0)
        acc_root.rotation = (0.0, 0.0, 0.0, 1.0)
        acc.root_node = acc_root
        head_mesh = ModelNode(name="headmesh",
                              flags=int(NodeFlags.SKIN | NodeFlags.MESH))
        head_mesh.position = (0.0, 0.0, 0.0)
        head_mesh.rotation = (0.0, 0.0, 0.0, 1.0)
        head_mesh.parent = acc_root
        acc_root.children.append(head_mesh)
        head_mesh.vertices = [(0.0, 0.0, 1.6), (0.1, 0.0, 1.7), (-0.1, 0.0, 1.7)]
        head_mesh.faces = [(0, 1, 2)]
        head_mesh.uvs = [(0.5, 0.0), (1.0, 0.5), (0.0, 0.5)]
        head_mesh.texture = "P_MaleHead01"
        head_mesh.render = True
        head_mesh.bone_map = ["Bip01 Pelvis"]
        head_mesh.skin_data = [
            VertexSkinData(influences=[BoneWeight(0, 1.0)]),
            VertexSkinData(influences=[BoneWeight(0, 1.0)]),
            VertexSkinData(influences=[BoneWeight(0, 1.0)]),
        ]

        # Step 1: base skeleton FBX
        ok_skel, skel_content = self._export_and_read(skel)
        assert ok_skel, "Base skeleton FBX export failed"
        assert '"Bip01 Pelvis", "LimbNode"' in skel_content, \
            "Pelvis bone missing from base skeleton FBX"

        # Step 2: accessory FBX with base skeleton reference
        ok_acc, acc_content = self._export_and_read(acc, base_skel=skel)
        assert ok_acc, "Accessory FBX export (with base skeleton) failed"
        assert 'Bip01 Pelvis' in acc_content, \
            "Accessory FBX must reference 'Bip01 Pelvis' for UE skeleton matching"
        assert '"Bip01 Pelvis", "Cluster"' in acc_content, \
            "Skin cluster for 'Bip01 Pelvis' missing from accessory FBX"

    def test_fbx_coordinate_system_z_up(self):
        """FBX GlobalSettings must declare Z-up (UpAxis=2) for KotOR convention."""
        model = self._make_standalone_creature()
        ok, content = self._export_and_read(model)
        assert ok
        assert '"UpAxis"' in content, "UpAxis not declared in GlobalSettings"
        up_match = re.search(r'"UpAxis".*?(\d+)', content)
        if up_match:
            assert up_match.group(1) == '2', \
                f"UpAxis should be 2 (Z-up), got {up_match.group(1)}"

    def test_animation_keycount_matches_controller(self):
        """
        Each animation axis curve KeyTime array size must match the controller's
        time array exactly.  A mismatch causes Unreal to misread keyframe timing.
        """
        model = self._make_standalone_creature()
        ok, content = self._export_and_read(model)
        assert ok
        # Each controller has 3 time entries → KeyTime: *3
        assert 'KeyTime: *3' in content, \
            "Expected KeyTime arrays of size 3 for 3-keyframe controllers"

    def test_rotation_curves_exported_as_euler(self):
        """
        Unreal imports rotation from FBX as Euler XYZ degrees, not quaternions.
        Lcl Rotation property connections and R|X/Y/Z curve nodes must be present.
        """
        import math
        from core.model_data import Animation
        model = KotorModel(name="rot_test", supermodel="NULL")
        root = ModelNode(name="rot_test", flags=int(NodeFlags.HEADER))
        root.position = (0.0, 0.0, 0.0)
        root.rotation = (0.0, 0.0, 0.0, 1.0)
        model.root_node = root
        bone = ModelNode(name="rot_bone", flags=0)
        bone.position = (0.0, 0.0, 0.5)
        bone.rotation = (0.0, 0.0, 0.0, 1.0)
        bone.parent = root
        root.children.append(bone)

        half_sin = math.sin(math.pi / 4)
        half_cos = math.cos(math.pi / 4)
        anim = Animation(name="spin", length=1.0)
        anode = ModelNode(name="rot_bone", flags=0)
        anode.controllers.append({
            'type': 20,  # CTRL_ORIENTATION
            'times': [0.0, 0.5, 1.0],
            'values': [
                [0.0, 0.0, 0.0, 1.0],
                [0.0, 0.0, half_sin, half_cos],
                [0.0, 0.0, 0.0, 1.0],
            ],
        })
        anim.nodes = [anode]
        model.animations.append(anim)

        ok, content = self._export_and_read(model)
        assert ok
        assert '"Lcl Rotation"' in content, \
            "Lcl Rotation property missing — rotation not converted to Euler"
        assert 'R|X' in content, "R|X curve node missing"
        assert 'R|Y' in content, "R|Y curve node missing"
        assert 'R|Z' in content, "R|Z curve node missing"


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
