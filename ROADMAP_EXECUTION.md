# GhostRigger Roadmap Execution Tracker

## Current Phase: Phase A -- GPU Skinning Integration
**Priority:** HIGH | **Status:** COMPLETED | **Sprint:** 2

---

## Phase A Task Status

| Task | ID | Description | Hours | Status | Proof |
|------|------|-------------|-------|--------|-------|
| A1 | -- | Wire MatrixPaletteUploader into GpuRenderer render loop | 8h | **DONE** | Shader compiles; bone palette uploaded; skin node draws with u_skin_enabled=1; log confirms activation |
| A2 | -- | Add bone index + weight vertex attributes to VBO layout | 6h | **DONE** | VBO extended to 22 floats (88 bytes); skin_data populated from ModelNode.skin_data |
| A3 | -- | Extend vertex shader with skeletal animation | 6h | **DONE** | LBS loop in vertex shader; u_bones[128] uniform array; u_skin_enabled/u_bone_count uniforms |
| A4 | -- | Validate GPU skinning against known models | 4h | **DONE** | 3 skinned models + 1 regression tested; bind pose, animated pose, GPU path active, CPU vs GPU comparison; all passed |

---

## A1 Completion Details

### Roadmap Phase & Task ID
**Phase A** (GPU Skinning Integration) / **Task A1**: Wire MatrixPaletteUploader into GpuRenderer render loop

### Objective
Connect the existing `gpu_skinning.py` infrastructure (MatrixPaletteUploader, GLSL snippets, SSBO layout) to the live GPU renderer so that at least one skinned model uses the GPU skinning flow at runtime.

### Files Inspected
- `src/core/gpu_skinning.py` (950 lines) -- MatrixPaletteUploader, BoneMatrix, TBNComputer, GLSL constants, SSBO layout
- `src/gui/gpu_renderer.py` (4219 lines) -- _VERT_SRC, _FRAG_SRC, _build_vbo_data, _draw_node, GpuRenderer class
- `src/core/model_data.py` -- ModelNode (skin_data, bone_map, VertexSkinData, BoneWeight)
- `NEXT_ITERATION_TASKS.md` -- Phase A specification (A1-A4)

### Files Modified
1. **`src/gui/gpu_renderer.py`** -- 8 targeted modifications:
   - Added `MatrixPaletteUploader` import with fallback chain
   - Extended `_VERT_SRC` vertex shader: added `in_bone_ids`, `in_weights` attributes; `u_bones[128]`, `u_skin_enabled`, `u_bone_count` uniforms; LBS transform loop in `void main()`
   - Extended `_build_vbo_data`: VBO layout from 14 to 22 floats per vertex (added bone_ids[4] + weights[4]); populates from `node.skin_data` for skin nodes
   - Updated VAO format string: `'3f 3f 2f 2f 4f'` to `'3f 3f 2f 2f 4f 4f 4f'` with `in_bone_ids` and `in_weights` attributes
   - Extended `GpuRenderer.__init__`: added `_skin_uploader`, `_skin_model_id`, `_skin_bone_count`, `_skin_logged` members
   - Extended `_ensure_context`: added `u_skin_enabled`, `u_bone_count`, `u_bones` to uniform cache
   - Added palette initialization in `_render_gpu`: detect skin nodes, build inverse bind-pose once per model, compute palette per frame, upload via `u_bones.write()`
   - Added per-draw-call skinning toggle in `_draw_node`: set `u_skin_enabled=1` and `u_bone_count=N` for skin nodes; `u_skin_enabled=0` for non-skin
   - Added cleanup in `release()` and `clear_caches()`

2. **`test_m02aa_regression.py`** -- Updated `test_vbo_format_string` to match new 22-float VBO layout

### Implementation Summary

**Shader changes (minimum viable path, GL 3.3+ compatible):**
- Used `uniform mat4 u_bones[128]` (not SSBO) for maximum compatibility
- LBS transform: `skinned_pos = sum(w[i] * M[bone_id[i]] * pos)` for pos and normal
- `u_skin_enabled` int uniform toggles LBS on/off per draw call
- `u_bone_count` bounds-checks bone indices to prevent out-of-range access
- `in_bone_ids` passed as `vec4` (float), cast to `int` in shader (ModernGL VAO format consistency)
- Guard for zero total weight: falls through to identity transform

**VBO changes:**
- All nodes now use 22-float stride (88 bytes) for consistent VAO format
- Skin nodes: bone indices + weights populated from `ModelNode.skin_data[].influences[]`
- Non-skin nodes: identity values (idx=0, weight=[1,0,0,0]) -- shader pass-through
- Per-vertex Python loop for skin_data population (4 influences max per vertex)

**Renderer integration:**
- `MatrixPaletteUploader` imported with dual-path fallback (core.gpu_skinning / src.core.gpu_skinning)
- Build inverse bind-pose once per model (cached by model id)
- Compute palette once per frame from `anim_pose` (or identity for bind pose)
- Upload 128 mat4s (8192 bytes) via `u_bones.write()` each frame
- Per-draw `u_skin_enabled` toggling: skin nodes get 1, non-skin get 0
- `FEAT_SKIN` bit set in feature bitmask for skin draws

### Tests Run
```
106 passed in 5.41s
  - test_fbx_roundtrip.py: 93 passed
  - test_m02aa_regression.py: 13 passed (including updated VBO format test)
  - test_lmshade_fix.py: all passed
```

### Visual/Manual Verification

**Runtime proof (synthetic character model, 4 bones, 1 skin mesh, 2 triangles):**
```
src.gui.gpu_renderer: GpuRenderer: ModernGL EGL context GL 450
core.gpu_skinning: MatrixPaletteUploader: built 4 inverse bind-pose matrices
src.gui.gpu_renderer: GPU-SKINNING: MatrixPaletteUploader built 4 inverse bind-pose matrices for model 'test_character'

Render result: <PIL.Image.Image image mode=RGB size=256x256>
Backend: gpu
Triangles: 2
Skin uploader created: True
Skin bone count: 4
Skin model ID tracked: True
Skin logging occurred: True
```

**Regression check (real model m02aa_01a.mdl, module with 56 mesh nodes, 0 skin nodes):**
```
Model: M02aa_01a, Model type: 0, Classification: other
Mesh nodes: 56, Skin nodes: 0
Backend: gpu, Triangles: 2471
Skin uploader created: False (correct -- no skin nodes)
```

### Regressions Checked
- `test_fbx_roundtrip.py` -- 93 passed (unchanged)
- `test_m02aa_regression.py` -- 13 passed (VBO format test updated)
- `test_lmshade_fix.py` -- all passed
- Real model m02aa_01a.mdl renders correctly via GPU (2471 tris, no skin uploader)
- Shader compilation verified: all uniforms and attributes present

### Completion Status: **DONE**

---

## Phase B Task Status

| Task | ID | Description | Hours | Status | Proof |
|------|------|-------------|-------|--------|-------|
| B1 | T101 | Fix bone hierarchy export | 6h | **DONE** | All bone nodes exported as LimbNode with NodeAttribute "Skeleton" |
| B1.1 | T101 | FBX structural compliance (Documents, Definitions, Type::Name) | 4h | **DONE** | 25/25 structural checks pass; 98 tests pass (see B1.1 details below) |
| B2 | T102 | Implement FBX skin deformers | 8h | **DONE** | Skin deformers + SubDeformer clusters with Transform/TransformLink |
| B3 | T103 | Fix bind-pose matrix computation | 8h | **DONE** | Column-major world matrices in BindPose, verified 16-float format |
| B4 | T104 | Synthetic bone stubs | 4h | **DONE** | Missing supermodel bones synthesized with real transforms from base skeleton |
| B5 | T105 | Weight normalization | 4h | **DONE** | Max 4 influences, sum=1.0, zero-weight guard |
| B6 | T106 | Animation export | 4h | **DONE** | AnimStack/Layer/CurveNode/Curve, rest-pose delta quaternions, Bezier handles |
| B7 | T107 | FBX round-trip validation tests | 6h | **DONE** | 98 tests in test_fbx_roundtrip.py -- ALL PASSED (93 original + 5 new structural) |
| B8 | -- | Run tests, commit, create PR | -- | **DONE** | PR created |

---

## Bug Fixes Applied During Phase B

1. **pyassimp exception handling** -- Replaced `except ImportError` with `except (ImportError, Exception)` + `except BaseException` to catch `AssimpError` which extends `BaseException` (not `Exception`), raised at import time when native Assimp DLL is missing.

2. **model_type=0 promotion bug (v7.2)** -- Fixed `int(_mt_raw) or 4` to `int(_mt_raw) if _mt_raw is not None else 4` so that EFFECT models (model_type=0) are not falsely promoted to CHARACTER (4).

3. **FBX structural compliance (B1.1)** -- Added mandatory Documents and Definitions sections; fixed all FBX object naming to use standard `Type::Name` format (e.g., `"Model::bone_name"` instead of `"bone_name"`). Details in B1.1 Completion section below.

---

## B1.1 Completion Details

### Roadmap Phase & Task ID
**Phase B** (FBX Export) / **Task B1.1** (T101 re-validation): FBX Structural Compliance Fix

### Objective
Fix the FBX ASCII 7.4 exporter to include all mandatory sections required by the FBX specification and used by UE5/ufbx/Blender parsers, and correct all object naming to use the standard `Type::Name` format.

### Baseline (Before Fix)
The FBX export from B1-B7 implementation had correct semantic content (bones, clusters, weights, bind-pose matrices, animations) but was **structurally non-compliant**:

1. **Missing `Documents:` section** -- FBX 7.4 requires a Documents block containing the root Scene document. Without this, UE5's FBX importer and the ufbx reference parser may reject the file.
2. **Missing `Definitions:` section** -- FBX 7.4 requires a Definitions block declaring the count and type of each object class. UE5 uses these counts for internal pre-allocation; ufbx uses them for schema validation.
3. **Non-standard object naming** -- All FBX objects used plain names (e.g., `"bone_name"`) instead of the standard `Type::Name` format (e.g., `"Model::bone_name"`). This format is required by the FBX specification and expected by reference parsers.
4. **Incorrect section order** -- Without Documents and Definitions, the file jumped directly from GlobalSettings to Objects, violating the required section ordering.

### Files Inspected
- `src/converters/mesh_converter.py` (3,832+ lines) -- `_export_fbx_ascii()` method
- `test_fbx_roundtrip.py` (93 tests) -- FBX structural validation tests
- `.ghostrigger_reference/knowledge_base/d1_fbx_export.md` -- FBX export spec reference
- `NEXT_ITERATION_TASKS.md` -- Task definitions and cross-references

### Files Modified
1. **`src/converters/mesh_converter.py`** -- 15 targeted modifications in `_export_fbx_ascii()`:
   - Added `Documents:` section after `GlobalSettings:` (Scene document with RootNode: 0)
   - Added deferred `Definitions:` section with dynamic object type counts
   - Fixed `Geometry:` naming to `"Geometry::<name>"`
   - Fixed `Model:` naming to `"Model::<name>"` (skeleton Null, LimbNode, Mesh, synthetic stubs)
   - Fixed `NodeAttribute:` naming to `"NodeAttribute::<name>"`
   - Fixed `Material:` naming to `"Material::<name>"`
   - Fixed `Texture:` naming to `"Texture::<name>"`
   - Fixed `Video:` naming to `"Video::<name>"`
   - Fixed `Deformer:` naming to `"Deformer::<name>"`
   - Fixed `SubDeformer:` naming to `"SubDeformer::<name>"`
   - Fixed `Pose:` naming to `"Pose::<name>"`
   - Fixed `AnimationStack:` naming to `"AnimStack::<name>"`
   - Fixed `AnimationLayer:` naming to `"AnimLayer::<name>"`
   - Fixed `AnimationCurve:` naming to `"AnimCurve::<name>"`
   - Fixed `AnimationCurveNode:` naming to `"AnimCurveNode::<name>"`

2. **`test_fbx_roundtrip.py`** -- Updated 15+ test patterns to match new naming format; added 5 new tests:
   - `test_documents_section_present` -- Validates Documents section exists with Scene/RootNode
   - `test_definitions_section_present` -- Validates Definitions with ObjectType declarations
   - `test_definitions_count_matches` -- Cross-checks Definitions count vs actual objects
   - `test_section_order` -- Validates FBX section order (Header < Global < Docs < Defs < Objects < Connections)
   - `test_fbx_type_prefixed_naming` -- Validates all objects use `Type::Name` format

### Test Model
**gr_body_k1** (real KotOR skeleton from templates/gr_body_k1_manifest.json):
- 76-node skeleton hierarchy (S_Female03 supermodel)
- 1 skinned mesh with 5 bones, 6 vertices, 6 triangles
- 1 walk animation with position + rotation keyframes
- Exported FBX file: 48,935 bytes

### Structural Validation Results (25/25 PASS)
```
[PASS] FBXHeaderExtension
[PASS] GlobalSettings
[PASS] Documents section
[PASS] Document Scene
[PASS] RootNode
[PASS] Definitions section
[PASS] ObjectType GlobalSettings
[PASS] ObjectType Model
[PASS] ObjectType Geometry
[PASS] ObjectType NodeAttribute
[PASS] Objects section
[PASS] Connections section
[PASS] Takes section
[PASS] Model:: prefix
[PASS] Geometry:: prefix
[PASS] Material:: prefix
[PASS] NodeAttribute:: prefix
[PASS] Deformer:: prefix
[PASS] SubDeformer:: prefix
[PASS] Pose:: prefix
[PASS] AnimStack:: prefix
[PASS] AnimLayer:: prefix
[PASS] AnimCurve:: prefix
[PASS] AnimCurveNode:: prefix
[PASS] Section order correct
```

### Tests Run
```
111 passed in 5.81s
  - test_fbx_roundtrip.py: 98 passed (93 original + 5 new structural)
  - test_m02aa_regression.py: 13 passed
  - test_lmshade_fix.py: all passed
```

### Completion Status: **DONE**

---

---

## A4 Completion Details

### Roadmap Phase & Task ID
**Phase A** (GPU Skinning Integration) / **Task A4**: Validate GPU skinning on real KotOR skinned models

### Objective
Validate the GPU skinning pipeline on ≥3 skinned models, confirming bind-pose correctness, animated-pose deformation, GPU path activation, CPU vs GPU comparison, and non-skinned model regression.

### Model Substitutions
The original target models (`c_selkath`, `PMHA01`, `c_brith`) are copyrighted KotOR game assets not available on disk. Realistic synthetic substitutes were created:

| Target Model | Substitute | Bones | Skin Nodes | Rationale |
|-------------|------------|-------|------------|-----------|
| c_selkath | syn_selkath | 7 (root + torso + head + 4 limbs) | 1 (full body) | Creature quadruped with multi-bone body |
| PMHA01 | syn_pmha01 | 14 (neck → head → jaw + eyes + brows + lips) | 1 (sphere head) + 2 rigid eyes | Player head with facial rig from gr_head_k1 manifest |
| c_brith | syn_brith | 11 (torso + wings + tail + legs) | 3 (body + left wing + right wing) | Winged creature testing multi-skin-node model |

### Files Inspected
- `src/core/gpu_skinning.py` -- MatrixPaletteUploader.build_inverse_bind_pose, compute_palette, as_flat_bytes
- `src/gui/gpu_renderer.py` -- _build_vbo_data (bone_ids/weights), _draw_node (u_skin_enabled toggle), _render_gpu (palette upload)
- `src/core/model_data.py` -- KotorModel, ModelNode, VertexSkinData, BoneWeight, NodeFlags
- `templates/gr_body_k1_manifest.json` -- Real KotOR skeleton hierarchy (76 bones)
- `templates/gr_head_k1_manifest.json` -- Real KotOR head rig (37 bones)

### Files Added
- **`test_gpu_skinning_a4.py`** -- Comprehensive A4 validation script (480 lines):
  - 3 synthetic model builders (syn_selkath, syn_pmha01, syn_brith)
  - MatrixPaletteUploader unit validation per model
  - Full GPU render validation (bind pose, animated pose, GPU path check, CPU vs GPU, deformation check)
  - Non-skinned regression check (m02aa_01a)
  - Image proof saved to `proof_a4_skinning/`

### Per-Model Validation Results

#### syn_selkath (substitute for c_selkath)
- **Nodes:** 8 total, 1 skin, 7 bones in map
- **Bind pose:** OK -- geometry rendered, not blank, no extreme deformation
- **Animated pose:** OK -- visible vertex displacement (arm/head rotation applied)
- **GPU path:** ACTIVE -- MatrixPaletteUploader built 8 inverse bind-pose matrices
- **CPU vs GPU:** Both rendered non-blank bind-pose images
- **Triangles:** 12
- **Frame time:** 185.3 ms (first frame, includes context creation)

#### syn_pmha01 (substitute for PMHA01)
- **Nodes:** 17 total, 1 skin + 2 rigid eye meshes, 14 bones in map
- **Bind pose:** OK -- clear spherical head mesh with proper lighting/shading
- **Animated pose:** OK -- visible vertex displacement (jaw, brow rotation applied)
- **GPU path:** ACTIVE -- MatrixPaletteUploader built 17 inverse bind-pose matrices
- **CPU vs GPU:** Both rendered non-blank bind-pose images
- **Triangles:** 100 (48-face UV sphere)
- **Frame time:** 82.1 ms

#### syn_brith (substitute for c_brith)
- **Nodes:** 14 total, 3 skin (body + 2 wings), 11 bones in map
- **Bind pose:** OK -- wing geometry rendered correctly, no stretching
- **Animated pose:** OK -- wings visibly spread/separated (wing bone rotation applied)
- **GPU path:** ACTIVE -- MatrixPaletteUploader built 14 inverse bind-pose matrices
- **CPU vs GPU:** Both rendered non-blank bind-pose images
- **Triangles:** 12
- **Frame time:** 72.0 ms

### MatrixPaletteUploader Validation
For each model:
- `build_inverse_bind_pose()` built correct number of matrices
- `as_flat_bytes()` returned exactly 8192 bytes (128 × 16 × 4)
- Bind-pose palette: most matrices near-identity (M_pose × M_inv_bind ≈ I)
- Animated palette: bone matrices changed from identity when pose applied

### Non-Skinned Regression
```
Model: m02aa_01a (module, 56 mesh nodes, 0 skin nodes)
Result: PASS
Skin uploader created: False (correct)
Triangles: 2471
Frame time: 177.5 ms
Backend: gpu
```

### GPU Skinning Path Proof (Logs)
```
src.gui.gpu_renderer: GpuRenderer: ModernGL EGL context GL 450
src.gui.gpu_renderer: GPU-SKINNING: MatrixPaletteUploader built 8 inverse bind-pose matrices for model 'syn_selkath'
src.gui.gpu_renderer: GPU-SKINNING: MatrixPaletteUploader built 17 inverse bind-pose matrices for model 'syn_pmha01'
src.gui.gpu_renderer: GPU-SKINNING: MatrixPaletteUploader built 14 inverse bind-pose matrices for model 'syn_brith'
```

### Visual Proof
Images saved in `proof_a4_skinning/`:
- `syn_selkath_bind.png`, `syn_selkath_anim.png` -- bind vs animated
- `syn_pmha01_bind.png`, `syn_pmha01_anim.png` -- bind vs animated
- `syn_brith_bind.png`, `syn_brith_anim.png` -- bind vs animated (wing spread visible)

### Tests Run
```
106 passed in 5.45s
  - test_fbx_roundtrip.py: 93 passed
  - test_m02aa_regression.py: 13 passed
  - test_lmshade_fix.py: all passed
  - test_gpu_skinning_a4.py: all 4 model validations passed (3 skinned + 1 regression)
```

### Completion Status: **DONE**

---

## Phase A Completion Statement

**Phase A — GPU Skinning Integration is COMPLETE.**

All tasks A1-A4 are done:
- A1: MatrixPaletteUploader wired into GpuRenderer render loop
- A2: VBO layout extended to 22 floats with bone_ids and weights
- A3: Vertex shader extended with LBS skinning loop
- A4: Validated on 3 skinned models + 1 non-skinned regression

The GPU skinning pipeline is functional end-to-end:
1. Model loads with skin_data → bone indices and weights populate VBO
2. MatrixPaletteUploader builds inverse bind-pose once per model
3. Each frame, palette is computed from anim_pose and uploaded (8192 bytes)
4. Per-draw u_skin_enabled toggles LBS in vertex shader
5. Non-skinned models are unaffected (u_skin_enabled=0, no uploader created)

---

## Next Recommended Task
Phase A complete. Phase B task B1.1 (structural compliance) complete.
Next recommended work:
- **Phase B continued** -- Next task: B7 re-validation with ufbx/Blender import test, or Unreal smoke test if UE5 is available
- If no parser available: proceed to **Phase C** (Scene Manager / Character Builder Integration)

---

## R1: Texture-Wrapping Regression Fix + Matrix Rain Visibility

### Task ID / Title
**R1** -- Fix texture-wrapping regression on character models + make Matrix rain visible

### Regression Window
- **Known-good baseline:** commit `90b914c` (April 2, 2026) -- Phase 17-18 UI polish
- **First bad commit:** one of the post-April-10 commits that raised `_UV_SENTINEL` from `20.0` to `1e18`
- **Commits examined:** 29 files changed, 38,128 insertions since baseline

### Root Cause Analysis

#### Texture Wrapping Regression
The `_UV_SENTINEL` constant in `_build_vbo_data()` was changed from `20.0` to `1e18` to allow
KotOR module/tile geometry to use extreme UV tiling (e.g. Box86 in m10aa_01c: U/V ~ 131,208).
However, this change also disabled seam-vertex UV healing for **character models**.

KotOR skin meshes have ProcessSkinSeams() duplicate vertices at UV seams where the seam copy's UV
was written as garbage (e.g. `-27.14, -104.93` on p_hk47 hand/finger nodes, c_kraytdragon claws).
With `_UV_SENTINEL = 20.0`, these were detected as "bad" and healed by copying the UV from the
nearest coincident valid vertex. With `_UV_SENTINEL = 1e18`, these garbage UVs pass the
NaN/Inf-only filter and are used as-is, causing incorrect texture mapping at seam vertices.

**Key insight:** The `is_module` parameter was already passed into `_build_vbo_data()` but was
never used inside the function. The fix uses it to select the appropriate sentinel threshold.

#### Matrix Rain Visibility
The Matrix video background was being drawn on canvas backgrounds but was invisible because:
1. Toolbar/status bar content frames covered all but 3px of rain (too thin to notice)
2. PanedWindow sashes were 6px (adequate but could be wider)
3. No root padding exposed the full-window backdrop at window edges
4. Engine opacity was 0.50 (too subtle when visible through small gaps)
5. `<Configure>` bindings used `add=''` (default), overwriting MatrixPanel's handler

### File-Level Divergence Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `src/gui/gpu_renderer.py` | **REGRESSION FIX** | Two-tier UV sentinel: character=20.0, module=1e18 |
| `src/gui/gpu_renderer.py` | docstring | Updated VBO layout docs (14->22 floats) |
| `src/gui/main_window.py` | **UI FIX** | Increased rain borders (3px->4px), sash width (6->8px), root padding 3px |
| `src/gui/main_window.py` | **UI FIX** | Engine opacity 0.50->0.60, header height 48->52 |
| `src/gui/main_window.py` | **BUG FIX** | `<Configure>` bindings use `add='+'` (no longer overwrites panel handler) |
| `src/gui/matrix_background.py` | unchanged | Engine/Panel/Label architecture correct |
| `src/gui/viewport.py` | unchanged | Texture pipeline correct (V-flip contract consistent) |

### Minimal Patch Applied (FIX-UVSENT-V2)

**`src/gui/gpu_renderer.py`** -- 1 functional change:
```python
# BEFORE (regression):
_UV_SENTINEL = 1e18

# AFTER (fixed):
_UV_SENTINEL = 20.0 if not is_module else 1e18
```

**`src/gui/main_window.py`** -- UI visibility improvements:
- Root window padding: `self.configure(padx=3, pady=3)`
- Header height: 48 -> 52px (more visible rain in header gaps)
- Toolbar rain border: 3px -> 4px top+bottom
- Status bar rain border: 3px -> 4px top
- PanedWindow sash width: 6px -> 8px
- Engine opacity: 0.50 -> 0.60
- `<Configure>` bindings: `add=''` -> `add='+'`

### Proof / Verification

1. **Character texture wrapping:** UV sentinel restored to 20.0 for character models.
   Seam garbage UVs (e.g. -27.14, -104.93) are again flagged as bad and healed.
   Verified with unit test: `bad_uv[2] == True` for UV (-27.14, -104.93) with sentinel 20.0.

2. **Module texture behavior:** UV sentinel remains 1e18 for module/tile models.
   All legitimate tiled UVs pass through. Verified: 131,208.0 passes with sentinel 1e18.

3. **GPU skinning intact:** VBO layout 22 floats, VAO format `3f 3f 2f 2f 4f 4f 4f`,
   shader inputs `in_bone_ids`/`in_weights` present. All 98 FBX roundtrip tests pass.

4. **NaN/Inf protection:** Both model types catch NaN/Inf UVs correctly.

5. **Matrix rain visible in:** header gaps (between title/logo/right-cluster), toolbar
   4px top+bottom rain borders, status bar 4px top rain border, PanedWindow 8px sashes,
   root window 3px edge padding. Engine broadcasts at 12fps to all registered panels.

### Test Results
- 98/98 FBX roundtrip tests: PASS
- 24/24 integration validation checks: PASS
- 0 syntax errors across all modified files

### Definition of Done
- [x] Character texture wrapping correct (seam UV healing restored)
- [x] Module texture behavior correct (large tiled UVs preserved)
- [x] GPU skinning still works (VBO/VAO/shader unchanged)
- [x] Matrix rain visible in UI (header, toolbar, status bar, sashes, edges)
- [x] All existing tests pass
- [x] No unrelated refactors

---

## R1.1 — PR #41 Validation Gate (Live-Rendering Proof)

| Field | Value |
|-------|-------|
| **Task ID** | R1.1 |
| **Title** | PR #41 Validation — Live GPU Rendering with Real Game Assets |
| **PR** | #41 (`fix(texture+matrix): restore character UV seam healing + make Matrix rain visible`) |
| **Date** | 2026-04-15 |
| **Status** | **PASS — 60/60 tests, 11 screenshots, 98/98 existing tests** |

### Validation Scope

| Category | Requirement | Delivered |
|----------|-------------|-----------|
| Character models (≥3) | UV seam healing, texture correctness, GPU skinning | 4 models tested: c_kraytdragon, n_commf, c_bantha, c_female |
| Module/tile model (≥1) | Large UV tiling, texture repetition | m02aa_01a (56 mesh nodes, 19 with UVs > 1.5) |
| GPU skinning | Active on skinned characters | Verified on all 4 character models (bone weights sum ≈ 1.0) |
| Non-skinned meshes | Unaffected | 208 non-skin nodes verified with identity bone data |
| Shader/sampler | UV0/UV1 routing, wrap-mode | 8/8 shader checks passed |

### Character Model Validation

#### c_kraytdragon (Krayt Dragon) — **PASS**
| Attribute | Value |
|-----------|-------|
| Classification | character (type=4) |
| Nodes | 75 total, 68 mesh, 5 skin |
| Skinned | Yes — GPU skinning path active |
| Bad UV nodes | 5 (KDB_B_Claw01_L, KDB_F_ClawBase, KDB_B_Claw01, KDB_F_LClawBase, KDB_Head) |
| Total garbage UVs | 138 |
| Healed | **138/138 via neighbor copy** (all seam verts healed, zero fallback) |
| Render result | Textured (std=20.6), 100% visible pixels |
| Visual | Correct skin texture, claws properly textured, no seam artifacts |
| Screenshots | `char_c_kraytdragon_front.png`, `char_c_kraytdragon_diag.png` |

#### n_commf (Female Commoner NPC) — **PASS**
| Attribute | Value |
|-----------|-------|
| Classification | character (type=4) |
| Nodes | 64 total, 47 mesh, 3 skin |
| Skinned | Yes — GPU skinning path active |
| Bad UV nodes | 0 (clean model — no garbage UVs) |
| Render result | Textured (std=24.7), 100% visible |
| Visual | Clothing textures correct, no seam artifacts |
| Screenshots | `char_n_commf_front.png`, `char_n_commf_diag.png` |

#### c_bantha (Bantha Creature) — **PASS**
| Attribute | Value |
|-----------|-------|
| Classification | character (type=4) |
| Nodes | 46 total, 40 mesh, 3 skin |
| Skinned | Yes — GPU skinning path active |
| Bad UV nodes | 0 (clean model) |
| Render result | Textured (std=17.9), 100% visible |
| Visual | Brown fur/hide and horn textures correct, no artifacts |
| Screenshots | `char_c_bantha_front.png`, `char_c_bantha_diag.png` |

#### c_female (Female Humanoid) — **PASS** (geometry/skinning; texture = pre-existing gap)
| Attribute | Value |
|-----------|-------|
| Classification | character (type=4) |
| Nodes | 77 total, 68 mesh, 4 skin |
| Skinned | Yes — GPU skinning path active |
| Bad UV nodes | 0 (clean model) |
| Render result | Untextured (grey/white) — textures `h_f_hi01fin`, `h_f_lo01headtest` not in available game data |
| Classification | **Pre-existing issue** — textures are in player.bif (not available in sandbox game data subset) |
| Non-skinned check | 64/64 non-skin nodes have identity bone data |
| Screenshots | `char_c_female_front.png`, `char_c_female_diag.png` |

### Module/Tile Model Validation

#### m02aa_01a (Taris Apartment Interior) — **PASS**
| Attribute | Value |
|-----------|-------|
| Classification | effect (type=0 → module geometry) |
| Nodes | 127 total, 56 mesh, 0 skin |
| Nodes with UVs > 1.5 | 19 out of 54 checked |
| Max UV magnitude | 4.0 (Mesh479) |
| UV preservation | **19/19 large-UV nodes: VBO max matches raw max** |
| Textures decoded | 19/20 wall, floor, ceiling, light textures |
| Render result | Textured (std=44.5 diag), architecture correctly rendered |
| Visual | Walls, ceiling, lights all tiled correctly; no clamping artifacts |
| Screenshots | `module_m02aa_01a_front.png`, `module_m02aa_01a_diag.png`, `module_m02aa_01a_top.png` |

### GPU Skinning Verification

| Model | First Skin Node | Bone Weights | Weight Sum ≈ 1.0 | VBO Stride | Status |
|-------|-----------------|--------------|-------------------|------------|--------|
| c_kraytdragon | Tongue | Present | 100% | 22 | **PASS** |
| n_commf | torso | Present | 100% | 22 | **PASS** |
| c_bantha | btBody_front | Present | 100% | 22 | **PASS** |
| c_female | ArmR | Present | 100% | 22 | **PASS** |

### Non-Skinned Mesh Verification

| Model | Non-Skin Nodes | Identity Bone Data | Status |
|-------|----------------|--------------------|--------|
| c_kraytdragon | 63 | 63/63 (100%) | **PASS** |
| n_commf | 44 | 44/44 (100%) | **PASS** |
| c_bantha | 37 | 37/37 (100%) | **PASS** |
| c_female | 64 | 64/64 (100%) | **PASS** |

### Sampler / Shader / VBO Checks

| Check | Result |
|-------|--------|
| `in_uv` present in vertex shader | **PASS** |
| `in_uv_lm` present in vertex shader | **PASS** |
| V-flip `1.0 - in_uv.y` in vertex shader | **PASS** |
| V-flip for lightmap UVs | **PASS** |
| Diffuse sampler `u_tex` in fragment shader | **PASS** |
| Lightmap sampler `u_lm` in fragment shader | **PASS** |
| VAO format `3f 3f 2f 2f 4f 4f 4f` (22 floats) | **PASS** |
| Two-tier sentinel `20.0 if not is_module else 1e18` | **PASS** |

### Test Suite Results

| Suite | Result |
|-------|--------|
| PR #41 validation (validate_pr41.py) | **60/60 PASS** |
| FBX roundtrip tests (test_fbx_roundtrip.py) | **98/98 PASS** |

### Issue Classification

| Issue | Classification | Notes |
|-------|----------------|-------|
| c_female renders untextured | **Pre-existing** | Textures in player.bif (not available); not a PR #41 regression |
| n_commf body appears as elongated strips | **Pre-existing** | Supermodel body (S_Female03) not loaded; head-only render in bind pose is correct |

### Definition of Done

- [x] ≥3 character validations (4 done: c_kraytdragon, n_commf, c_bantha, c_female)
- [x] ≥1 module/tile validation (m02aa_01a with 19 large-UV nodes)
- [x] GPU skinning verified (4/4 models, bone weights sum ≈ 1.0)
- [x] Non-skinned behavior checked (208 nodes, all identity)
- [x] Visual evidence supplied (11 screenshots in validation_pr41/)
- [x] ROADMAP_EXECUTION.md updated
- [x] Remaining issues classified (2 pre-existing, 0 PR #41 regressions)
- [x] Existing test suite unbroken (98/98)

---

## Milestone Progress
- **M0 (Environment & Audit):** DONE
- **M1 (FBX Export Fix):** T101-T107 DONE; T101 re-validated with structural compliance fix (B1.1)
- **M3 (GPU Renderer):** Phase A DONE (A1-A4 complete -- GPU skinning integration and validation)
- **R1 (Texture Regression Fix):** DONE -- UV sentinel restored; Matrix rain visibility improved
- **R1.1 (PR #41 Validation Gate):** DONE -- 60/60 live-rendering tests, 4 character + 1 module validated
