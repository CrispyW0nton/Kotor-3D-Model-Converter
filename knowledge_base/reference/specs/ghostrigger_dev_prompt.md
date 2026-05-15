# GhostRigger v6.0 — Iteration 1 Development Prompt

---

## CONTEXT

You are starting a new development cycle on **GhostRigger**, a KotOR 1 & 2 model pipeline tool.

**Repository:** https://github.com/CrispyW0nton/Kotor-3D-Model-Converter

I have attached:
- **GhostRigger v6.0 Master Engineering Brief** — the full audit, root-cause analysis, and roadmap for every known issue. Read this document COMPLETELY before writing any code. It contains the exact file paths, line-level diagnoses, fix instructions, and acceptance criteria for every bug.
- **"Computer Graphics Development with OpenGL" (Hayes, 2025)** — reference for GPU rendering architecture, z-buffer depth testing, VBO/VAO patterns, texture wrap modes, and camera/projection matrices.
- **"3D Mesh Processing and Character Animation" (Mukundan, 2022)** — reference for skeletal mesh export, bind pose matrices (Jk = Lk × Fk), skin weights, offset matrices, and animation retargeting.
- **"Game Engine Architecture 4th Ed." (Gregory, 2024)** — reference for modular tool architecture, asset conditioning pipelines, resource management, and editor design patterns.

Consult these books when the master brief references them. They contain the correct algorithms and patterns.

---

## PROJECT SNAPSHOT

| Field | Value |
|-------|-------|
| Current version | v5.1.0 (2026-04-05) |
| Test suite | 5,007 passing · 11 skipped · 0 failures |
| License | MIT |
| Language | Python 3.10+ |
| UI framework | tkinter / ttk |
| Rendering | CPU PIL software rasterizer (primary), optional Numba/NumPy accel |
| KotOR backend | PyKotor (pykotor ≥ 2.3.1) |
| Optional deps | PyOpenGL, ModernGL, pyassimp, pygltflib |

### Key Source Files

| File | Lines | Responsibility |
|------|-------|----------------|
| `src/gui/viewport.py` | ~9,323 | CPU PIL software rasterizer, depth sorting, texture rendering, UV handling, inner-geometry workarounds |
| `src/gui/main_window.py` | ~10,000+ | Main window, five-pillar UI, character builder integration, module loading, library panel |
| `src/converters/mesh_converter.py` | ~3,535 | OBJ/FBX/glTF import and export, FBXExporter class, ASCII FBX 7.4 fallback |
| `src/autorig/auto_rigger.py` | — | Auto-rig, Library Rig, heat-map weights, skeleton templates (HUMANOID_BONES, CREATURE_BONES) |
| `src/autorig/accurig.py` | — | AcuRig guide-based biped rig with symmetry enforcement, profile detection |
| `src/autorig/grig.py` | — | GRig manual bone assignment with brush-mode weight painting |
| `src/core/mdl_parser.py` | — | MDL binary (PyKotor shim via kotor_loader.py) and ASCII parser/writer |
| `src/core/model_data.py` | — | In-memory model graph: KotorModel, ModelNode, Animation, VertexSkinData, BoneWeight |
| `src/core/animation_engine.py` | — | Animation curve interpolation and playback, supermodel chain resolution |
| `src/core/resource_manager.py` | — | Unified K1/K2 resource lookup, game install auto-detection |
| `src/core/pykotor_bridge.py` | — | PyKotor MDL/TPC/Anim adapter layer |
| `src/gui/modular_panel.py` | ~1,200 | Module Editor panel |

### Architecture: Five Pillars

1. **Model Viewer** — load K1/K2 models, skeleton overlay, walkmesh, display modes
2. **Animation** — browse/play/seek/export animations, supermodel chain resolution
3. **Character Builder** — Auto-Rig, Library Rig, GRig, AcuRig, head/body assembly, export
4. **Module Editor** — .lyt/.vis/.are/.git/.ifo, walkmesh tools, K1↔K2 porter
5. **Resource Browser** — 2DA viewer, .rim/.erf/.mod/.bif container browsing, MDLOps bridge

---

## CRITICAL BUGS — ROOT CAUSE ANALYSIS

There are four critical bugs. Each is documented with its root cause, the exact code locations, and the correct fix. Do not guess at causes — they have been diagnosed through a full codebase audit.

### Bug 1: Texture Wrapping / Bad Tiling on Modules

**Symptoms:** Module floor and wall textures appear stretched, clamped, or missing. Tiled textures that should repeat across large surfaces display incorrectly.

**Root cause in `src/gui/viewport.py`:**

1. **UV sentinel filtering** (line ~169):
```python
_UV_SENTINEL = 100.0
```
Triangles with any UV component exceeding 100.0 are silently skipped. KotOR module textures (floors, walls, terrain) intentionally use tiled UVs well beyond the 0–1 range. The sentinel was meant to filter placeholder UVs from seam-split vertices but incorrectly filters legitimate tiled UVs.

2. **Clamping instead of repeating** — the software rasterizer uses `np.clip()` (equivalent to `GL_CLAMP_TO_EDGE`) instead of `frac()` (equivalent to `GL_REPEAT`) for UV mapping.

3. **Band-aid workaround** (line ~5105):
```python
_accel_uv_sentinel = 1e6 if _accel_is_module else _UV_SENTINEL
```
This confirms the developers knew module textures needed special handling, but the workaround is fragile.

4. **Missing TXI clamp_s/clamp_t support** in the accel rendering path. Textures that should clamp are not distinguished from textures that should repeat.

**How KotorBlender and KotOR.js handle this:** No UV sentinel filtering. Raw UV values stored as-is. GPU handles tiling natively via `GL_REPEAT`. Neither tool has this bug.

---

### Bug 2: Performance / Excessive RAM / Sluggishness

**Symptoms:** The program uses excessive RAM. Orbit/pan is sluggish. Complex models stutter. The renderer drops to flat-shading during interaction to maintain framerate.

**Root cause in `src/gui/viewport.py`:**

The entire rendering pipeline is a **CPU-based PIL software rasterizer** — 9,323 lines of Python doing the GPU's job.

1. Each frame is drawn into a PIL Image and displayed via `tkinter Canvas.create_image()`.
2. **Painter's algorithm** requires sorting ALL triangles every frame — O(n log n) complexity vs. O(n) for z-buffer.
3. Interactive LOD fallback drops to flat-shading during orbit/pan because the renderer cannot maintain framerate:
```python
# Reduced interactive tri cap: 20k (was 25k) for better drag responsiveness
```
4. Triangle cap of `MAX_TRIS = 80_000`.
5. Texture decode (DXT1/DXT5 decompression, TPC header parsing) happens in Python on the CPU.
6. Python closure allocation overhead: ~2–3 µs per triangle, ~16 ms per 8,000-triangle textured frame.
7. No GPU offloading for any rendering operation.

**How every comparable tool handles this:** KotOR.js uses THREE.js WebGL. reone uses OpenGL. xoreos uses OpenGL. ALL comparable tools use GPU rendering. GhostRigger is the only one using CPU software rasterization.

---

### Bug 3: Broken FBX Export (Exports Succeed but Unreal Cannot Import)

**Symptoms:** Exporting a model (e.g., `c_selkath`) produces an .fbx file that appears to succeed, but Unreal Engine 5 cannot import it — no skeleton visible, mesh may be missing, animations do not load.

**Root cause in `src/converters/mesh_converter.py`:**

The FBX export uses a three-tier fallback strategy:
1. Autodesk FBX SDK (requires manual install — rarely available)
2. pyassimp (described as "immature" in the source code)
3. **ASCII FBX 7.4 manual write** (most commonly used fallback)

The ASCII fallback has structural problems:

1. **Skeleton export may miss bones.** The code filters on `n.is_dummy` to identify skeleton nodes, but KotOR bones are not always flagged as dummies. Actual bone nodes may be skipped.

2. **Skin deformers may be incomplete.** The mesh export creates geometry (vertices, faces, normals, UVs) but the skin cluster / sub-deformer creation for bone weights may not be correctly structured for Unreal's FBX importer.

3. **Bind pose matrices may be incorrect.** The code transforms vertices to world space using `v_world = rotate(skin_wo, v_local) + skin_wp`, but Unreal requires a specific FBX BindPose object with correct world-space matrices in column-major format.

4. **Synthetic/supermodel bones** are emitted as LimbNode stubs with potentially identity matrices instead of correct bind transforms.

5. Source code comment confirms limitation:
```python
# This does NOT apply Linear Blend Skinning — it produces the correct bind-pose shape only.
```

**What Unreal Engine requires from skeletal FBX:**
- Complete skeleton hierarchy with ALL bones as FBX Skeleton/LimbNode
- Every vertex must have at least one bone influence with skin weights summing to 1.0
- Proper FBX BindPose object with correct world-space matrices
- FBX version 2020.2 or compatible
- Correct coordinate system and unit scale

---

### Bug 4: Depth Rendering (Eyeballs / Teeth / Gums Visible Through Faces)

**Symptoms:** When viewing head models, inner geometry (eyeballs, teeth, gums, tongue) is visible through the outer face mesh. The problem varies with camera angle and head model.

**Root cause in `src/gui/viewport.py`:**

The renderer uses **painter's algorithm** (back-to-front centroid depth sorting) instead of a z-buffer.

```python
# Sort back-to-front (painter's algorithm)
depth = (p0[2] + p1[2] + p2[2]) * 0.3333 + fi * 1e-7
```

For complex face assemblies with nested geometry (eyeballs inside head, teeth inside mouth), centroid-based sorting **cannot** correctly determine draw order. The centroid of the eyeball may be at a similar depth to the face, causing it to draw on top.

The codebase has accumulated multiple workarounds across versions:

```python
_INNER_GEO_SUBSTRINGS: tuple = (
    'eye', 'lid', 'teeth', 'tooth', 'gum', 'jaw',
    'tongue', 'teethu', 'teethl', 'eyeball', 'cornea',
    'iris', 'pupil', 'gumskin', 'tonguemesh', 'jawskin',
    'eyelid', 'teetha', 'teethb',
)
```

Inner geometry nodes are "promoted" to tier 1 (drawn after tier 0 opaque geometry). Multiple `BUG FIX v20` and `BUG FIX v26` comments in the code show ongoing struggle with this issue across versions. These workarounds fail with certain camera angles and certain head models.

**This bug is fundamentally unsolvable with painter's algorithm.** The only correct fix is z-buffer depth testing.

---

## ITERATION 1 SCOPE — Three Deliverables

Complete these in order. Each must pass before moving to the next.

---

### Deliverable 1: Fix FBX Export → Unreal Import

**File:** `src/converters/mesh_converter.py`

**Instructions:**

1. Read the full FBX export analysis in the master brief (Section 2, Bug 3).
2. Audit the `FBXExporter` class and the `_export_fbx_ascii` path. Trace exactly how skeleton hierarchy, skin clusters, bind pose, and bone weights are written.
3. Cross-reference against KotorBlender's `io_scene_kotor/scene/armature.py` and `io_scene_kotor/ops/mdl/export.py` to understand how a correct KotOR skeleton is structured.
4. Cross-reference against ufbx's `ufbx.h` struct definitions (`ufbx_skin_deformer`, `ufbx_skin_cluster`, `ufbx_bone`) to understand what a valid FBX skeletal mesh looks like.
5. Fix the export so that:
   - ALL bones in the skeleton hierarchy are exported as FBX LimbNode objects with correct parent-child relationships — do not filter only on `is_dummy`.
   - Every skinned mesh has a proper FBX Skin deformer with SubDeformer/Cluster per influencing bone.
   - Each cluster contains the correct vertex indices, weights, and transform/transform-link matrices.
   - Bind pose is exported as a proper FBX BindPose object. Use the formula from the Mukundan book: **Jk = Lk × Fk** (concatenated node transform × offset matrix). Matrices must be column-major as FBX 7.4 requires.
   - Weight normalization: all vertex weights sum to 1.0. Zero-weight guard: every vertex has at least one bone influence.
   - Coordinate system and unit scale match Unreal expectations (Z-up, centimeters).
6. If synthetic/supermodel bones are referenced by skin clusters but missing from the model tree, emit them as LimbNode stubs with correct bind-pose local transforms (not identity matrices). When `base_skeleton_model` is available, pull the real transforms from it.
7. Export animations as separate FBX Take objects with baked keyframes at 30fps.

**Acceptance criteria:**
- Export `c_selkath` (creature Selkath) from K1. Import into Unreal Engine 5. Verify: skeleton hierarchy visible in Skeleton Editor, correct mesh attached, at least one animation playing, texture material slots present.
- Export `PMHC06` (K2 player head). Import into Unreal Engine 5. Verify: facial bones intact.
- All 5,007 existing tests still pass. New FBX round-trip tests added.

**Do NOT** rewrite the entire converter. Fix the ASCII FBX path specifically. Keep existing OBJ and glTF paths working.

---

### Deliverable 2: Fix Texture Wrapping on Modules

**File:** `src/gui/viewport.py`

**Instructions:**

1. Read the full texture wrapping analysis in the master brief (Section 2, Bug 1).
2. Cross-reference KotOR.js's `src/resource/TPCObject.ts` and `src/resource/TXI.ts` to see how TPC textures and TXI metadata (including clamp flags) are parsed in a working renderer.
3. Cross-reference KotorBlender's `io_scene_kotor/scene/material.py` to see how texture wrap modes are applied to materials.
4. Cross-reference PyKotor's `Libraries/PyKotor/src/pykotor/resource/formats/tpc/` to verify whether TXI `clamp_s`/`clamp_t` flags are exposed and whether GhostRigger's viewport reads them.
5. Apply these fixes:
   - **Remove the UV sentinel filtering logic entirely.** Do not filter triangles by UV magnitude. If placeholder UVs need filtering, use a node-type or vertex-flag check instead.
   - **Replace `np.clip()` UV handling with `frac()`** (modular arithmetic: `u = u - floor(u)`) to emulate `GL_REPEAT`. This is the default behavior for all diffuse textures.
   - **Add TXI clamp support:** when a texture's TXI metadata specifies `clamp_s` or `clamp_t`, use clamp-to-edge behavior for that specific texture. Otherwise default to repeat.
   - **Remove the `_accel_uv_sentinel = 1e6` module workaround** — it should no longer be needed.

**Acceptance criteria:**
- Load any K1 or K2 module area (e.g., Taris Upper City, Peragus Administration Level). Floor and wall textures tile correctly with no visible seams, stretching, or clamping artifacts.
- Compare visually against the same area rendered in KotOR.js (https://play.swkotor.net/) or in-game screenshots.
- NumPy acceleration path still works correctly.
- All existing tests pass. New UV wrapping regression tests added.

---

### Deliverable 3: GPU Renderer Foundation

**New file:** `src/gui/gpu_renderer.py`
**Modified file:** `src/gui/viewport.py` (add toggle to switch renderers)

**Instructions:**

1. Read the full performance and depth rendering analysis in the master brief (Sections 2.2 and 2.4).
2. Cross-reference KotOR.js's `src/apps/forge/UI3DRenderer.tsx` to see how KotOR.js implements a GPU-accelerated model viewer for its modding suite.
3. Cross-reference reone's `src/libs/graphics/` for how a C++ KotOR engine sets up OpenGL rendering with z-buffer and multi-pass transparency.
4. Cross-reference xoreos's `src/graphics/aurora/model_kotor.cpp` for how xoreos loads and renders KotOR MDL models with OpenGL.
5. Reference the Hayes OpenGL book for VBO/VAO setup, depth testing, texture parameters, and camera matrix math.
6. Implement the following in `gpu_renderer.py`:

**ModernGL context creation** — attach to the tkinter viewport widget. Use moderngl-window or embed via framebuffer-to-PIL bridge for initial integration.

**VBO/VAO mesh upload** — upload mesh vertex data to GPU buffers:
```
Attributes per vertex: position (vec3), normal (vec3), uv (vec2),
                       bone_weights (vec4), bone_indices (ivec4)
```

**Basic vertex + fragment shaders:**
```glsl
// Vertex shader
uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

in vec3 a_position;
in vec3 a_normal;
in vec2 a_uv;

out vec2 v_uv;
out vec3 v_normal;

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
    v_uv = a_uv;
    v_normal = mat3(u_model) * a_normal;
}

// Fragment shader
uniform sampler2D u_texture;
in vec2 v_uv;
in vec3 v_normal;
out vec4 fragColor;

void main() {
    vec3 light = normalize(vec3(0.3, 0.5, 1.0));
    float diff = max(dot(normalize(v_normal), light), 0.2);
    vec4 tex = texture(u_texture, v_uv);
    fragColor = vec4(tex.rgb * diff, tex.a);
}
```

**Z-buffer depth testing:**
```python
ctx.enable(moderngl.DEPTH_TEST)
# This single line replaces 500+ lines of painter's algorithm workarounds
```

**Three-pass rendering:**
- Pass 1: Opaque geometry — z-write ON, z-test LESS
- Pass 2: Alpha-test cutouts (hair cards, lashes) — z-write ON, discard fragments below alpha threshold
- Pass 3: Transparent geometry — z-write OFF, z-test LESS, sorted back-to-front

**Texture upload** with proper sampler parameters:
- `GL_REPEAT` as default wrap mode
- `GL_CLAMP_TO_EDGE` when TXI clamp flags are set
- `GL_LINEAR_MIPMAP_LINEAR` filtering with mipmaps generated via `glGenerateMipmap`

**Camera system:**
- Orbit/pan/zoom using lookAt view matrix + perspective projection matrix
- Pass as `uniform mat4` to vertex shader
- Camera presets: Front, Back, Left, Right, Top, Bottom

**Backface culling:** `ctx.enable(moderngl.CULL_FACE)`

**Renderer toggle:** Add a keyboard shortcut or menu item in `viewport.py` to switch between CPU and GPU renderer at runtime.

**Acceptance criteria:**
- Load `c_selkath` and any K1 player head (e.g., `PMHA01`) in the GPU renderer.
- **No depth artifacts** — eyeballs, teeth, gums are NOT visible through face mesh at any camera angle.
- **Textures render correctly** — no tiling bugs, no UV artifacts.
- **Smooth 60fps** orbit/pan/zoom for models under 100K triangles.
- **Skeleton overlay** visible when toggled.
- CPU renderer still works as fallback. Toggle switches cleanly between renderers.
- All existing tests pass. New GPU renderer basic rendering tests added.

---

## REFERENCE REPOSITORY CROSS-REFERENCE

Before writing any code, **clone the source code** of these OpenKotOR ecosystem repositories. These are working implementations of the exact systems you are fixing. When the instructions say "cross-reference," this is where you look.

```bash
mkdir -p ~/reference-repos && cd ~/reference-repos

# 1. PyKotor — KotOR file format library (Python). GhostRigger already depends on this.
git clone --depth 1 https://github.com/OldRepublicDevs/PyKotor.git

# 2. KotorBlender — Blender MDL import/export with armature/skeleton support
git clone --depth 1 https://github.com/seedhartha/kotorblender.git

# 3. KotOR.js — Full Odyssey engine reimplementation with GPU renderer + lip-sync editor
git clone --depth 1 https://github.com/KobaltBlu/KotOR.js.git

# 4. reone — C++ KotOR/TSL engine with OpenGL rendering and module loading
git clone --depth 1 https://github.com/seedhartha/reone.git

# 5. xoreos — C++ Aurora engine reimplementation (KotOR model loader reference)
git clone --depth 1 https://github.com/xoreos/xoreos.git

# 6. ufbx — Single-file C FBX/OBJ loader (skeletal mesh, skin weights, bind pose)
git clone --depth 1 https://github.com/bqqbarbhg/ufbx.git
```

### Cross-Reference Map: Deliverable 1 (FBX Export Fix)

| Repo | Key Files | What to Learn |
|------|-----------|---------------|
| **KotorBlender** | `io_scene_kotor/format/mdl/` | How KotOR bone hierarchy, skin weights, and bind pose are structured at the binary level. Canonical reference for what the MDL actually contains. |
| **KotorBlender** | `io_scene_kotor/scene/armature.py` | How KotOR skeleton nodes (meshes-as-bones) are converted into a proper armature with correct bone transforms. Study the armature rebuild logic. |
| **KotorBlender** | `io_scene_kotor/ops/mdl/export.py` | How a correctly-structured KotOR model is exported back out, preserving skeleton and skin data. |
| **KotOR.js** | `src/resource/GFFObject.ts`, `src/resource/LIPObject.ts` | How GFF and LIP structures are parsed in a working engine — verify export data matches what the game expects. |
| **PyKotor** | `Libraries/PyKotor/src/pykotor/resource/formats/mdl/` | The MDL format reader/writer GhostRigger already uses. Audit what skin weight and bone data PyKotor provides, and whether mesh_converter uses it correctly. |
| **ufbx** | `ufbx.h` (struct definitions around lines 4000–5000) | How a correct FBX file represents `ufbx_skin_deformer`, `ufbx_skin_cluster`, `ufbx_bone`, `ufbx_blend_channel`. Ground truth for what Unreal expects. |

### Cross-Reference Map: Deliverable 2 (Texture Wrapping Fix)

| Repo | Key Files | What to Learn |
|------|-----------|---------------|
| **KotOR.js** | `src/resource/TPCObject.ts`, `src/resource/TXI.ts` | How TPC textures and TXI metadata (including clamp flags) are parsed in a working KotOR renderer. |
| **KotorBlender** | `io_scene_kotor/format/tpc/` | How TPC textures are decoded and TXI attributes are read. |
| **KotorBlender** | `io_scene_kotor/scene/material.py` | How texture wrap modes are applied to materials — shows the correct default (repeat, not clamp). |
| **reone** | `src/libs/graphics/` (texture and material handling) | How an OpenGL-based KotOR renderer sets up texture samplers with correct wrap modes. |
| **PyKotor** | `Libraries/PyKotor/src/pykotor/resource/formats/tpc/` | The TPC reader GhostRigger depends on. Verify whether TXI clamp flags are exposed and used. |

### Cross-Reference Map: Deliverable 3 (GPU Renderer)

| Repo | Key Files | What to Learn |
|------|-----------|---------------|
| **KotOR.js** | `src/apps/forge/UI3DRenderer.tsx` | How KotOR.js implements a GPU-accelerated model viewer for KotOR Forge. Closest reference to what GhostRigger's GPU viewport should become. |
| **KotOR.js** | THREE.js integration files | How KotOR model data is fed into a GPU scene graph — mesh creation, material setup, skeleton binding, animation playback. |
| **reone** | `src/libs/graphics/` — shaders, mesh rendering, scene graph | How a C++ KotOR engine sets up OpenGL rendering with z-buffer, depth testing, and multi-pass transparency. Most complete "engine-grade" reference. |
| **xoreos** | `src/graphics/aurora/model_kotor.cpp` | How xoreos loads and renders KotOR MDL models with OpenGL — vertex buffer setup, texture binding, depth state. |
| **xoreos** | `src/graphics/aurora/model.cpp` | Base Aurora model renderer — skeleton, animations, and mesh rendering pipeline for GPU. |

### How to Use These References

1. **Before fixing the FBX exporter:** Open KotorBlender's `armature.py` and `export.py` side-by-side with GhostRigger's `mesh_converter.py`. Compare how each converts KotOR's node-based skeleton into standard bone hierarchies with bind pose matrices.

2. **Before fixing texture wrapping:** Open KotOR.js's `TPCObject.ts` and `TXI.ts` side-by-side with GhostRigger's TPC loading in `viewport.py`. Verify whether GhostRigger reads TXI clamp flags at all, and how KotOR.js applies wrap modes.

3. **Before building the GPU renderer:** Read KotOR.js's `UI3DRenderer.tsx` and reone's graphics pipeline. These show exactly how other projects feed KotOR model data into a GPU-accelerated 3D viewport with correct z-buffer depth testing.

4. **When something is ambiguous in GhostRigger's code:** Check how PyKotor handles the same data. GhostRigger already imports PyKotor — if PyKotor provides correct data that GhostRigger mishandles downstream, that narrows the bug.

5. **Do NOT copy code directly** from GPL-licensed repos (KotorBlender, KotOR.js, reone, xoreos) into GhostRigger (MIT-licensed). Use them as **reference implementations** to understand the correct data structures, algorithms, and behavior, then implement the fix in GhostRigger's own code. ufbx is MIT/Public Domain and PyKotor is LGPL — those have more permissive terms.

---

## BOOK-BACKED ENGINEERING PRINCIPLES

Reference these when implementing the fixes. The master brief tells you which section applies to which bug.

### From "Computer Graphics Development with OpenGL" (Hayes, 2025)

- **Z-buffer depth testing:** `glEnable(GL_DEPTH_TEST); glDepthFunc(GL_LESS);` — replaces painter's algorithm entirely
- **VBOs/VAOs:** Store mesh data on GPU via Vertex Buffer Objects; manage state via Vertex Array Objects
- **Texture wrapping:** `glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)` for tiling; `GL_CLAMP_TO_EDGE` for non-tiling
- **Alpha testing:** Discard fragments below an alpha threshold for cutout materials (hair, lashes)
- **Camera management:** `lookAt(cameraPos, cameraTarget, up)` for view matrix; `perspective(fov, aspect, near, far)` for projection; pass as `uniform mat4` to shaders
- **Frustum culling:** Skip objects whose bounding box is outside the camera frustum
- **Instanced rendering:** `glDrawArraysInstanced` for repeated geometry
- **Batch rendering:** Group static geometry into single draw calls

### From "3D Mesh Processing and Character Animation" (Mukundan, 2022)

- **Bind pose:** The pose where all joint angles are zero. The offset matrix F transforms vertices from mesh space to joint space.
- **Joint matrix formula:** `Jk = Lk × Fk` — concatenated node transform × offset matrix. This MUST be correctly implemented in the FBX export.
- **Vertex blending:** `v' = Σ(wi × Ji × v)` where weights sum to 1.0
- **Normal matrix for skinned meshes:** Inverse-transpose of the weighted sum of joint matrices — NOT the same as the position transform
- **Retargeting:** Requires joint name mapping (hash map) AND Euler angle axis remapping between source and target skeletons
- **Twist links:** Multiple closely located joints for forearm/neck to prevent candy-wrapper collapse at 180° rotation
- **Zero-weight guard:** Every vertex must have at least one bone influence

### From "Game Engine Architecture 4th Ed." (Gregory, 2024)

- **Modular architecture:** Loosely coupled subsystems with clear interfaces. Do not merge unrelated functionality.
- **Single source of truth:** Avoid dual data representations between editor and runtime. One data path.
- **Asset conditioning pipeline:** Exporter → Resource Compiler → Resource Linker → Engine binary
- **Resource registry:** GUID-based lookup with reference counting for lifetime management
- **Cache-friendly data layouts:** Organize data in small contiguous blocks; access sequentially for performance
- **Editor ergonomics:** Minimize modal dialogs, support batch operations, provide live preview, hot-reload
- **Custom allocators:** Stack/Pool/Chunk allocators over general-purpose heaps for rendering data

---

## RULES FOR THIS ITERATION

1. **Read the master brief first.** It contains exact root causes, file paths, line numbers, and fix strategies. Do not guess at causes.
2. **Clone and study the reference repos first.** The cross-reference map tells you exactly which files to read for each deliverable.
3. **Do not refactor unrelated systems.** Touch only the files needed for these three deliverables. Do not reorganize the UI, rename modules, or restructure the project layout.
4. **All 5,007 existing tests must pass** after every deliverable. Run `pytest` and report results.
5. **Add new tests** for each deliverable: FBX round-trip tests, UV wrapping regression tests, GPU renderer basic rendering tests.
6. **Commit each deliverable separately** with clear commit messages:
   - `fix(export): FBX skeletal mesh structure for Unreal import`
   - `fix(viewport): texture wrapping GL_REPEAT for module UVs`
   - `feat(viewport): ModernGL GPU renderer foundation with z-buffer`
7. **Do not remove the CPU renderer.** It stays as fallback. The GPU renderer is additive.
8. **When in doubt, consult the attached books** — they contain the correct algorithms. Then check the reference repos for working implementations.
9. **Show diagnosis and proposed changes before writing code** for each deliverable. Explain what you found in the source, what the reference repos do differently, and what you plan to change. Then implement.
10. **License compliance:** Do not copy code from GPL repos (KotorBlender, KotOR.js, reone, xoreos) into the MIT-licensed GhostRigger. Use them as reference only. ufbx (MIT/PD) and PyKotor (LGPL) have more permissive terms.

---

## WHAT "DONE" LOOKS LIKE

When this iteration is complete, I should be able to:

1. **Export `c_selkath` to FBX** → import into Unreal Engine 5 → see the skeleton in Skeleton Editor, mesh attached correctly, at least one animation playing, texture material slots present.
2. **Load a K1/K2 module area** → see floors and walls with correct repeating textures, no stretching or clamping artifacts.
3. **Toggle to the GPU renderer** → load a head model → see NO eyeballs or teeth through the face at any camera angle → orbit smoothly at 60fps.
4. **Run `pytest`** → all existing tests pass plus new tests for each deliverable.

---

## EXECUTION ORDER

Start with **Deliverable 1** (FBX export). Show me the diagnosis and proposed changes before writing code. Then implement, test, and move to **Deliverable 2**. Then **Deliverable 3**.

For each deliverable:
1. State which reference repo files you reviewed and what you learned
2. Explain the root cause you confirmed in GhostRigger's code
3. Describe your proposed fix
4. Implement the fix
5. Run tests and report results
6. Commit with the specified message format

Begin.
