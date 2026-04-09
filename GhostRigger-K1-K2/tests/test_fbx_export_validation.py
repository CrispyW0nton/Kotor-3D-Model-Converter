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


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
