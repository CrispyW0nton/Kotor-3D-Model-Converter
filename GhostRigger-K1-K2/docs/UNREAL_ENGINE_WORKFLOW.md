# GhostRigger → Unreal Engine 5 Complete Workflow

## Quick Start (5 Minutes)

### Step 1: Load KotOR Model in GhostRigger

1. **Launch GhostRigger**
2. **File → Open MDL (binary)…**
3. Navigate to KotOR installation: `C:\Program Files\Steam\steamapps\common\swkotor\data\`
4. Select a character model (e.g., `c_selkath.mdl`, `p_bastilah.mdl`)
5. GhostRigger automatically:
   - Loads the MDL + MDX files
   - Merges supermodel skeleton (if applicable)
   - Loads all animations
   - Decodes textures (TPC → internal format)

### Step 2: Export to FBX

1. **File → Export FBX…**
2. Choose save location (e.g., `Desktop/ue_assets/c_selkath.fbx`)
3. Click **Save**
4. GhostRigger exports:
   - ✅ FBX file with full skeleton + animations
   - ✅ `rigging/` subfolder with JSON data (optional reference)

**Output:**
```
Desktop/ue_assets/
  ├── c_selkath.fbx              ← Import this into UE
  └── rigging/
      ├── c_selkath.skeleton.json
      ├── c_selkath.animations.json
      └── c_selkath.weights.json
```

### Step 3: Import into Unreal Engine 5

1. **Open your UE5 project**
2. **Content Browser → Right-click → Import to /Game/...**
3. Select `c_selkath.fbx`
4. **FBX Import Options:**
   - ✅ Import as Skeletal Mesh
   - ✅ Import Animations
   - ✅ Import Materials
   - ✅ Use T0 as Reference Pose
   - Skeleton: "Create New Asset" or select existing skeleton
5. Click **Import**

**UE5 Creates:**
- **Skeletal Mesh**: `SK_c_selkath`
- **Skeleton**: `SK_c_selkath_Skeleton`
- **Animations**: One asset per KotOR animation (e.g., `anim_walk`, `anim_run`, `anim_attack1`)

### Step 4: Verify in UE5

1. **Double-click Skeletal Mesh** → Opens Skeletal Mesh Editor
2. **Check skeleton hierarchy** (Outliner panel):
   - Root bone (model name)
   - Child bones (pelvis, spine, arms, legs, head, etc.)
3. **Open Animation Editor** (Animation → Preview)
4. **Select an animation** from dropdown
5. **Press Play** → Watch animation

**Success Indicators:**
- ✅ Model displays with proper proportions
- ✅ Skeleton bones visible and correctly named
- ✅ Animations play smoothly
- ✅ Mesh deforms correctly with bone rotations
- ✅ No vertex "explosions" or artifacts

---

## Common Issues & Solutions

### Issue: "Skeleton bones appear but mesh doesn't deform"

**Cause:** Skin weights not imported correctly  
**Check:**
```
1. Open FBX in text editor
2. Search for "SubDeformer:"
3. Should find entries like: SubDeformer: 1234, "pelvis", "Cluster"
4. Check for "Weights:" arrays
```

**Solution:**
- Re-export from GhostRigger with latest version (includes SubDeformer fix)
- Ensure model has `is_skin` flag set on mesh nodes

### Issue: "Animations are missing or import as static pose"

**Cause:** Model has no animation data  
**Check in GhostRigger:**
```
Model → Model Info... → Animations section
Should list animations like: walk, run, attack1, etc.
```

**Solution:**
- Some models (static props, placeables) have no animations - this is normal
- Character models should have 20-50+ animations
- If character has 0 animations, the MDL file may be corrupted
- Try loading from a different source (extracted BIF vs. game directory)

### Issue: "Textures are black or missing"

**Cause:** UE5 doesn't have the textures  
**Solution:**

1. **Extract textures from KotOR:**
   ```
   Use ERFEdit or reone toolkit:
   - Extract swpc_tex_tpa.erf → Desktop/kotor_textures/
   - Batch convert TPC → TGA using GhostRigger or reone
   ```

2. **Create UE5 materials:**
   ```
   Content Browser → Right-click → Material
   Name: M_Selkath
   
   Add nodes:
   - Texture Sample (Base Color texture)
   - Connect to Base Color pin
   - Set Material Domain: Surface
   - Set Blend Mode: Opaque (or Masked for transparency)
   ```

3. **Assign material to skeletal mesh:**
   ```
   Open SK_c_selkath
   Material Slots panel → Select slot
   Assign M_Selkath
   ```

### Issue: "Model is too small/large in UE5"

**Cause:** KotOR uses different scale than UE5  
**Solution:**

**In UE5 (after import):**
```
Skeletal Mesh Editor → Asset Details
→ Mesh → Scale → Uniform Scale: 100.0 (or 0.01)
```

**OR in GhostRigger (before export):**
```
Model → Transform tab
Scale: 100.0 (for cm → m conversion)
Re-export FBX
```

**Standard scales:**
- KotOR → UE5: **×100** (KotOR uses meters, UE5 uses centimeters)
- Human characters should be ~180-200 cm tall in UE5

### Issue: "Bones have weird names (dupli_1, group_0)"

**Cause:** Some KotOR models use non-standard naming  
**Solution:**

**Option 1: Accept as-is**  
- UE5 AnimBlueprint can map any bone names
- As long as hierarchy is correct, animations will work

**Option 2: Rename bones in GhostRigger**  
```
Model → Hierarchy panel
Right-click bone → Rename
Standard names: pelvis, spine, l_shoulder, r_shoulder, head, etc.
Re-export FBX
```

---

## Advanced Workflows

### Retargeting Animations Between Characters

**Problem:** You want to use Bastila's animations on a Selkath model

**Solution:**

1. **Export both models** to FBX:
   - `p_bastilah.fbx` (source animations)
   - `c_selkath.fbx` (target skeleton)

2. **Import both into UE5**

3. **Create IK Rig for each skeleton:**
   ```
   Content Browser → Right-click → Animation → IK Rig
   Name: IKRig_Bastila
   
   Open IK Rig:
   - Assign skeleton: SK_p_bastilah_Skeleton
   - Set Root Bone: pelvis
   - Add Chain: spine → head
   - Add Chain: l_shoulder → l_hand
   - Add Chain: r_shoulder → r_hand
   - Add Chain: l_hip → l_foot
   - Add Chain: r_hip → r_foot
   
   Repeat for IKRig_Selkath
   ```

4. **Create IK Retargeter:**
   ```
   Right-click → Animation → IK Retargeter
   Name: RTG_Bastila_to_Selkath
   
   Source IK Rig: IKRig_Bastila
   Target IK Rig: IKRig_Selkath
   
   Map chains:
   - Bastila Spine → Selkath Spine
   - Bastila LeftArm → Selkath LeftArm
   - etc.
   ```

5. **Retarget animations:**
   ```
   Right-click RTG_Bastila_to_Selkath
   → Batch Retarget Animations
   Select animations to retarget
   Choose output folder
   ```

### Creating Animation Blueprint for NPC

1. **Create Animation Blueprint:**
   ```
   Content Browser → Right-click → Animation → Animation Blueprint
   Parent Class: AnimInstance
   Target Skeleton: SK_c_selkath_Skeleton
   Name: ABP_Selkath
   ```

2. **Set up State Machine:**
   ```
   Event Graph:
   - Get Owner Velocity → Speed
   - Compare Speed > 0 → IsMoving (bool)
   
   Anim Graph:
   - Add State Machine
   - States: Idle, Walk, Run
   - Transitions:
     - Idle → Walk (IsMoving == true, Speed < 200)
     - Walk → Run (Speed > 200)
     - Any → Idle (IsMoving == false)
   ```

3. **Assign animations to states:**
   ```
   Idle state: Play anim_cpause1
   Walk state: Play anim_walk
   Run state: Play anim_run
   ```

4. **Use in Blueprint:**
   ```
   NPC_Selkath Blueprint:
   - Skeletal Mesh Component → SK_c_selkath
   - Anim Class → ABP_Selkath
   ```

### Exporting Modded Character Back to KotOR

**Workflow:** UE5 → GhostRigger → KotOR MDL

1. **Export from UE5** (using FBX export plugin):
   ```
   Content Browser → Right-click Skeletal Mesh
   → Asset Actions → Export...
   Format: FBX
   ```

2. **Import into GhostRigger:**
   ```
   File → Import FBX…
   Select exported FBX
   ```

3. **Convert to KotOR format:**
   ```
   File → Export Binary MDL…
   Choose K1 or K2
   Save as c_selkath_modded.mdl
   ```

4. **Test in-game:**
   ```
   Copy .mdl + .mdx to:
   KotOR/Override/
   
   Launch KotOR
   Spawn character (via save editor or console)
   ```

---

## Format Comparison Chart

| Feature | FBX (GhostRigger) | GLB/GLTF (GhostRigger) | OBJ (GhostRigger) | MDL (KotORBlender) |
|---------|-------------------|------------------------|-------------------|--------------------|
| **Skeleton hierarchy** | ✅ Full | ✅ Full | ❌ None | ✅ Full |
| **Skin weights** | ✅ Yes | ✅ Yes | ❌ None | ✅ Yes |
| **Animations** | ✅ All (as stacks) | ✅ All | ❌ None | ✅ All |
| **UE5 import** | ✅ Native | ✅ Via plugin | ⚠️ Static only | ❌ No |
| **Unity import** | ✅ Native | ✅ Native | ⚠️ Static only | ❌ No |
| **Blender import** | ✅ Native | ✅ Native | ✅ Yes | ⚠️ Via KotORBlender |
| **File size** | Medium | Small (binary) | Small | Small |
| **Human-readable** | ✅ ASCII | ⚠️ JSON only | ✅ Yes | ⚠️ With decompiler |
| **Best for** | **UE5/Unity/Maya** | Web/Blender/Debug | Static props | KotOR modding only |

---

## Recommended Workflow by Use Case

### Game Development (UE5/Unity)
```
KotOR MDL → GhostRigger → FBX → UE5/Unity
```
- Use FBX for skeletal meshes + animations
- Import directly into game engine
- Set up Animation Blueprint or Animator Controller
- Retarget animations if needed

### 3D Modeling (Blender/Maya)
```
KotOR MDL → GhostRigger → FBX or GLTF → Blender/Maya
```
- FBX for complex rigs with IK constraints
- GLTF for lightweight editing + debug JSON
- Edit mesh/UVs/weights in 3D software
- Export back to FBX → GhostRigger → MDL

### KotOR Modding
```
KotOR MDL → KotORBlender → Edit → Export MDL → KotOR
```
- Use KotORBlender ONLY for KotOR ↔ KotOR workflow
- GhostRigger can import KotORBlender's MDL output
- GhostRigger → UE5 → back to GhostRigger is possible

### Static Props / Environment
```
KotOR MDL → GhostRigger → OBJ → UE5/Blender
```
- OBJ sufficient for non-animated objects
- Faster export, smaller files
- No skeleton overhead

---

## Performance Tips

### Large Batch Exports

**Problem:** Need to export 100+ character models

**Solution:**
```python
# Use GhostRigger's batch export script
from src.core.resource_manager import ResourceManager
from src.converters.mesh_converter import FBXExporter
from pathlib import Path

rm = ResourceManager(kotor_path="C:/Program Files/Steam/steamapps/common/swkotor",
                    game_version=GameVersion.K1)

character_models = [
    "p_bastilah", "p_carth", "p_canderous", "p_hk47",
    "c_wookiee", "c_selkath", "c_hutt", "c_duros"
]

output_dir = Path("Desktop/ue_kotor_assets")
output_dir.mkdir(exist_ok=True)

exporter = FBXExporter()

for model_name in character_models:
    try:
        model = rm.load_model(model_name)
        fbx_path = output_dir / f"{model_name}.fbx"
        exporter.export(model, str(fbx_path), export_rigging=True)
        print(f"✅ {model_name}")
    except Exception as e:
        print(f"❌ {model_name}: {e}")
```

### Optimize FBX File Size

**For UE5 import:**
- Disable `export_rigging=False` if you don't need JSON debug data
- UE5 ignores rigging/ subfolder anyway

**For web/mobile:**
- Use GLTF/GLB instead of FBX
- Enable compression: `binary=True`
- Smaller files (50-70% reduction)

### Animation Filtering

**Problem:** Model has 50+ animations but you only need walk/run/attack

**Solution:**
```python
# In GhostRigger before export
model = rm.load_model("p_bastilah")

# Filter animations
wanted = ["walk", "run", "attack1", "attack2", "cpause1"]
model.animations = [a for a in model.animations if a.name in wanted]

# Now export only has 5 animations instead of 50+
exporter.export(model, "bastilah_minimal.fbx")
```

---

## Troubleshooting Checklist

Before asking for help, verify:

- [ ] GhostRigger version is latest (check GitHub releases)
- [ ] Model loads successfully in GhostRigger viewport
- [ ] Skeleton visible in GhostRigger (Model → Toggle Bones)
- [ ] Animations playable in GhostRigger Animation panel
- [ ] FBX file size > 10 KB (too small = export failed)
- [ ] FBX file contains "SubDeformer:" (search in text editor)
- [ ] UE5 import settings: "Import as Skeletal Mesh" enabled
- [ ] UE5 import settings: "Import Animations" enabled
- [ ] No errors in UE5 Output Log during import

**Still broken?**

1. Post issue on GitHub: https://github.com/CrispyW0nton/Kotor-3D-Model-Converter/issues
2. Include:
   - Model name (e.g., "c_selkath.mdl")
   - GhostRigger version
   - UE5 version
   - Screenshot of UE5 import settings
   - FBX file (if < 5 MB) or excerpt showing SubDeformer section

---

## Additional Resources

- **GhostRigger Documentation**: `docs/SKELETAL_MESH_ANIMATION_EXPORT.md`
- **Example Script**: `examples/export_selkath_to_unreal.py`
- **UE5 IK Retargeting**: https://docs.unrealengine.com/5.0/en-US/ik-rig-animation-retargeting-in-unreal-engine/
- **FBX Format Reference**: https://help.autodesk.com/view/FBX/2020/ENU/
- **KotOR MDL Format**: https://github.com/xoreos/xoreos-docs/blob/master/specs/biowareaurora/mdl.txt

---

## Summary: From KotOR to Unreal in 3 Steps

```
┌─────────────────┐
│  KotOR Game     │
│  c_selkath.mdl  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  GhostRigger    │
│  File → Export  │
│  FBX…           │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Unreal Engine  │
│  Import FBX     │
│  → SK_c_selkath │
└─────────────────┘
```

**That's it! Your KotOR character is now a UE5 skeletal mesh with full animations.**
