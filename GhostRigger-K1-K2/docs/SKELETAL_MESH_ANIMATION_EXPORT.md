# KotOR Skeletal Mesh & Animation Export Guide

## Overview

This document explains how to export KotOR character models (like the Selkath) with skeletal meshes and animations for use in Unreal Engine or other game engines.

## Important Concepts

### KotOR Model Structure

KotOR character models consist of several components:

1. **Skeleton/Bone Hierarchy**: A tree of nodes (bones) that define the character's structure
2. **Skin Meshes**: Geometry bound to the skeleton via vertex weights (skin weights)
3. **Animations**: Keyframe data for position/rotation of bones over time
4. **Supermodels**: Parent skeleton definitions (e.g., `S_Female03` for many creature models)

### The Problem with OBJ Format

**OBJ files DO NOT support:**
- Skeletal hierarchies
- Vertex skinning/bone weights
- Animations
- Rigging data

OBJ is a **static mesh format only** - it exports the model geometry in a single pose (usually bind/T-pose) with no animation or rigging information.

### The Problem with KotORBlender

Based on my research of the KotORBlender source code:

**KotORBlender ONLY exports to MDL format** (the native KotOR binary format). It does **NOT** export to FBX, OBJ, or any other standard game engine format with skeletal mesh support.

From the code:
```python
# io_scene_kotor/ops/mdl/export.py
class KB_OT_export_mdl(bpy.types.Operator, ExportHelper):
    bl_idname = "kb.mdlexport"
    bl_label = "Export KotOR MDL"
    filename_ext = ".mdl"
```

The workflow is:
1. Import MDL → Blender
2. Edit in Blender (using armatures or object-based animation)
3. Export back to MDL

**To get FBX/animation support, you must use GhostRigger.**

---

## GhostRigger Export Capabilities

### FBX Export (FULL Skeletal Mesh + Animation Support)

GhostRigger's `FBXExporter` class provides **complete** skeletal mesh and animation export:

**Supported Features:**
✅ **Skeletal hierarchy** - All bones exported as FBX null/joint nodes  
✅ **Skin meshes** - Vertex weights bound to bones via FBX skin deformers  
✅ **Animations** - All model animations exported as AnimationStacks/Layers  
✅ **Multiple animations** - Each KotOR animation becomes a separate FBX AnimStack  
✅ **Bone transforms** - Position + rotation keyframes (converted to Euler XYZ)  
✅ **World-space bind pose** - Proper bind matrices for each cluster/joint  

**Implementation Details:**
```python
# From src/converters/mesh_converter.py:897-1570

class FBXExporter:
    def export(self, model: KotorModel, fbx_path: str, 
               tex_cache=None, export_rigging=True):
        """
        Export KotorModel to FBX ASCII 7.4 format.
        Includes full skeleton hierarchy + skin deformers + animations.
        """
```

The FBX export:
1. **Builds node hierarchy** - All ModelNodes → FBX nodes with parent/child relationships
2. **Exports skin meshes** - Geometry + skin cluster deformers linking vertices to bones
3. **Writes bind poses** - 4x4 world transform matrices for each bone's bind pose
4. **Exports animations**:
   - Each `model.animations[i]` → FBX AnimationStack
   - Position controllers (type 8) → Translation curves (X/Y/Z)
   - Orientation controllers (type 20) → Rotation curves (Euler X/Y/Z in degrees)
   - Keyframe times converted to FBX ticks (46186158000 ticks/second)

**Animation Export Code:**
```python
# Lines 1406-1520
if model.animations:
    CTRL_POSITION = 8
    CTRL_ORIENTATION = 20
    
    for anim in model.animations:
        # Create AnimStack + AnimLayer
        stack_id = new_id()
        layer_id = new_id()
        
        # Export position/rotation curves for each animated bone
        for anim_node in anim.nodes:
            # Extract position/rotation controllers
            pos_times, pos_vals = ...
            rot_times, rot_vals = ...
            
            # Write AnimationCurveNode + AnimationCurve objects
            # Position: delta + bind → absolute
            # Rotation: quaternion → Euler XYZ degrees
```

### OBJ Export (Static Mesh Only)

OBJ export via `OBJExporter.export()` provides:
✅ Mesh geometry (vertices, faces, normals, UVs)  
✅ Materials (MTL file)  
❌ **NO skeletal hierarchy**  
❌ **NO bone weights**  
❌ **NO animations**  

Use OBJ only for static props, environment meshes, or reference geometry.

### GLTF Export (Full Support + Embedded Rigging)

GhostRigger's `GLTFExporter` provides:
✅ Skeletal hierarchy (GLTF nodes + skins)  
✅ Skin meshes with vertex weights  
✅ Animations (via GLTF animation samplers)  
✅ **PLUS** optional rigging JSON export (detailed weights/skeleton data)  

```python
# From src/converters/mesh_converter.py:2163
def export(self, model: KotorModel, path: str, binary=True,
           tex_cache=None, export_rigging=True):
    """
    When export_rigging=True, creates rigging/ subdirectory with:
    - rigging/<model>.skeleton.json  – full bone hierarchy
    - rigging/<model>.animations.json – animation list
    - rigging/<model>.weights.json – per-vertex skin weights
    """
```

---

## Recommended Workflows

### For Unreal Engine (Best Practice)

**Use FBX export:**

1. **In GhostRigger:**
   ```python
   from src.converters.mesh_converter import FBXExporter
   from src.core.resource_manager import ResourceManager
   
   # Load model (handles supermodel merging automatically)
   rm = ResourceManager(kotor_path="/path/to/kotor", game_version=GameVersion.K1)
   model = rm.load_model("c_selkath")
   
   # Export to FBX with all animations
   exporter = FBXExporter()
   exporter.export(model, "c_selkath.fbx", export_rigging=True)
   ```

2. **In Unreal Engine:**
   - Import FBX via Content Browser
   - Unreal will create:
     - Skeletal Mesh asset
     - Skeleton asset
     - Animation assets (one per AnimStack)
   - Set up Animation Blueprint to play animations

**Why FBX?**
- Industry standard for skeletal meshes
- Unreal Engine native support
- Preserves all animation data
- No manual rigging required

### For Blender/Maya (Alternative Workflow)

**Use GLTF export + manual rigging:**

1. Export to GLTF/GLB with `export_rigging=True`
2. Import GLTF into Blender/Maya
3. Use `rigging/*.json` files to:
   - Verify bone hierarchy
   - Cross-check vertex weights
   - Debug animation issues

**Why GLTF?**
- Open standard (JSON-based)
- Human-readable JSON rigging data
- Good for debugging/validation
- Supported by Blender 2.8+ natively

---

## Common Issues & Solutions

### Issue: "No skeletal mesh when importing OBJ"

**Cause:** OBJ format does not support skeletal meshes.  
**Solution:** Use FBX or GLTF export instead.

### Issue: "Animations not included in FBX"

**Check:**
1. Model was loaded via ResourceManager (not manually constructed)
2. Model has animations: `len(model.animations) > 0`
3. Animation nodes are not empty: `anim.nodes is not None`

**Debug:**
```python
print(f"Model: {model.name}")
print(f"Animations: {len(model.animations)}")
for anim in model.animations:
    print(f"  - {anim.name}: {anim.length}s, {len(anim.nodes)} nodes")
```

### Issue: "Selkath imports but has no skeleton"

**Cause:** Selkath uses supermodel `S_Female03` for skeleton definition.  
**Solution:** ResourceManager automatically merges supermodel skeleton when loading:

```python
# This happens automatically:
rm.load_model("c_selkath")
# ResourceManager finds supermodel=S_Female03
# Loads S_Female03.mdl
# Merges S_Female03 skeleton into c_selkath
# Returns complete model with skeleton
```

**Verify supermodel was loaded:**
```python
model = rm.load_model("c_selkath")
print(f"Root node children: {len(list(model.root_node.children))}")
# Should show skeleton bones (20-40+ nodes)
```

### Issue: "Missing 'usecomp' animation"

**Background:** Some character models use a composite animation named `usecomp` that's stored in the supermodel but referenced by equipped items (lightsabers, weapons, etc.).

**Solution:** Use `AnimationEngine.merge_usecomp_from()`:
```python
from src.core.animation_engine import AnimationEngine

# Load character (e.g., "c_calonord")
character_model = rm.load_model("c_calonord")

# Load parent supermodel explicitly
parent_model = rm.load_model("S_Male02")

# Merge usecomp animation
engine = AnimationEngine(character_model)
parent_engine = AnimationEngine(parent_model)
merged_count = engine.merge_usecomp_from(parent_engine)

print(f"Merged {merged_count} usecomp nodes")
```

**When is this needed?**
- Character models that equip weapons/items
- Models with `supermodel != NULL`
- When exporting for game modding (to preserve usecomp)

---

## API Reference

### ResourceManager.load_model()

```python
def load_model(self, model_name: str, 
               game_version: GameVersion = GameVersion.K1) -> KotorModel:
    """
    Load a KotOR model by name.
    Automatically handles:
    - Supermodel merging (skeleton inheritance)
    - MDL + MDX file loading
    - Animation parsing
    - Texture references
    
    Args:
        model_name: Model identifier (e.g., "c_selkath", "p_bastilah")
        game_version: K1 or K2 (default: K1)
    
    Returns:
        KotorModel with complete skeleton, animations, and mesh data
    """
```

### FBXExporter.export()

```python
def export(self, model: KotorModel, fbx_path: str, 
           tex_cache=None, export_rigging=True) -> bool:
    """
    Export KotorModel to FBX ASCII 7.4 format.
    
    Args:
        model: KotorModel to export
        fbx_path: Output FBX file path
        tex_cache: Optional texture cache for embedded textures
        export_rigging: If True, creates rigging/ subfolder with JSON data
    
    Returns:
        True on success
    
    Exports:
        - Full bone hierarchy (all nodes)
        - Skin meshes with vertex weights
        - All animations as AnimationStacks
        - Bind pose matrices
        - Materials (Phong shading)
    """
```

### GLTFExporter.export()

```python
def export(self, model: KotorModel, path: str, 
           binary=True, tex_cache=None, export_rigging=True) -> bool:
    """
    Export KotorModel to GLTF 2.0 or GLB format.
    
    Args:
        model: KotorModel to export
        path: Output file path (.gltf or .glb)
        binary: If True, export GLB; if False, export GLTF+BIN
        tex_cache: Optional texture cache
        export_rigging: If True, creates rigging/*.json alongside output
    
    Returns:
        True on success
    
    Rigging JSON files (when export_rigging=True):
        - rigging/<model>.skeleton.json
        - rigging/<model>.animations.json
        - rigging/<model>.weights.json
    """
```

---

## Testing Your Export

### Verify FBX Structure

```python
# After export, check FBX file size and animation count
import os
from pathlib import Path

fbx_file = Path("c_selkath.fbx")
print(f"FBX size: {fbx_file.stat().st_size / 1024:.1f} KB")

# Search for AnimationStack entries in FBX ASCII
with open(fbx_file, 'r') as f:
    content = f.read()
    anim_count = content.count('AnimationStack:')
    print(f"Animation stacks: {anim_count}")
```

### Import Test in Unreal Engine

1. Create new UE project
2. Import FBX via Content Browser
3. Check Import Options:
   - ✅ Import Animations
   - ✅ Import as Skeletal Mesh
   - ✅ Use T0 as Reference Pose
4. Verify imported assets:
   - Skeletal Mesh exists
   - Skeleton asset exists
   - Animation assets exist (one per KotOR animation)
5. Open Animation editor → Preview animations

---

## Summary

| Format | Skeleton | Animations | Skin Weights | Use Case |
|--------|----------|------------|--------------|----------|
| **FBX** (GhostRigger) | ✅ Full | ✅ All | ✅ Yes | **Unreal Engine (BEST)** |
| **GLTF** (GhostRigger) | ✅ Full | ✅ All | ✅ Yes | Blender/Maya/Debug |
| **OBJ** (GhostRigger) | ❌ No | ❌ No | ❌ No | Static props only |
| **MDL** (KotORBlender) | ✅ Full | ✅ All | ✅ Yes | KotOR modding only |

**Bottom line for Unreal Engine:**  
Use GhostRigger's `FBXExporter.export()` with `export_rigging=True` for complete skeletal mesh + animation export.

KotORBlender is only useful for:
- Editing models in Blender
- Exporting back to KotOR MDL format
- Lightmap baking
- Walkmesh editing

It **cannot** export to formats compatible with Unreal Engine.
