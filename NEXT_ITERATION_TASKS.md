# GhostRigger — Next Iteration Comprehensive Task List
# =====================================================
# Generated: 2026-04-14
# Source: ghostrigger_module_texture_fix_research.zip + ghostrigger_module_texture_implementation_guide.md
# Cross-referenced against: current codebase state (commit 448fd4d), deep audit (42 findings),
# ROADMAP.md (M0-M8), architecture audit (6 phases), character builder spec (18 sections),
# knowledge base (D1-D6), and performance profiling (PR #37: 79 fps interactive).
#
# This is NOT a summary. It is a derived implementation plan based on exhaustive analysis
# of all data in the provided research files, validated against the live codebase.

---

## Current State Assessment (as of 2026-04-14)

### Implementation Scoreboard
| Category | Done | Remaining | Completion |
|----------|------|-----------|------------|
| Deep Audit Findings (42 total) | 26 | 16 | 62% |
| Roadmap M0 (Setup) | 5/6 | 1 | 83% |
| Roadmap M1 (FBX Export) | 0/7 | 7 | 0% |
| Roadmap M2 (Texture Wrapping) | 3/4 | 1 | 75% |
| Roadmap M3 (GPU Renderer) | 9/9 | 0 | 100% |
| Roadmap M4 (GPU Polish) | 3/4 | 1 | 75% |
| Roadmap M5 (Character Builder) | 2/8 | 6 | 25% |
| Roadmap M6 (Performance) | 2/4 | 2 | 50% |
| Roadmap M7 (Export Expansion) | 0/4 | 4 | 0% |
| Roadmap M8 (Validation/Regression) | 1/4 | 3 | 25% |

### Key Files and Current State
| File | Lines | Status |
|------|-------|--------|
| `src/gui/gpu_renderer.py` | 4,219 | GPU primary path operational; 79 fps interactive; MSAA, 3-pass, lightmap, env-map, TXI working |
| `src/gui/viewport.py` | 9,452 | GPU toggle wired; interactive flag functional; CPU fallback preserved |
| `src/converters/mesh_converter.py` | 3,826 | ASCII FBX 7.4 fallback — skeleton/skin cluster export NOT Unreal-validated |
| `src/gui/character_builder_window.py` | 3,532 | 5-mode shell exists (Assembly/Rig/Face/Preview/Export); most modes placeholder |
| `src/core/gpu_skinning.py` | 39,124 | MatrixPaletteUploader + SSBO + TBN exist; NOT integrated with render loop |
| `src/core/scene_manager.py` | 1,215 | Frustum class exists; room/object graph partially implemented |
| `src/core/validation_service.py` | 443 | Hooks, supermodel, K1/K2, weights validation — basic rules exist |
| `src/core/resource_manager.py` | 912 | Override preloading; NO lazy loading; NO LRU eviction |

### What Has Been Achieved (PRs #27-#37)
- ✅ GPU renderer foundation (ModernGL/EGL, depth buffer, 3-pass rendering)
- ✅ Module texture loading via PyKotor integration
- ✅ Lightmap compositing (FIX-LMROLE, FIX-LMSHADE, FIX-LMWRAP, FIX-LMBRIGHT)
- ✅ Environment map blending (FIX-ENVBLEND, FIX-ENVFB)
- ✅ Multi-texture node splitting, TXI blend modes, punch-through alpha
- ✅ Performance optimization: dual-FBO, half-res interactive, cached uniforms (79 fps)
- ✅ Deformation-helper mesh filtering, skin-proxy detection
- ✅ Persistent world-transform cache (O(1) lookup)
- ✅ Feature bitmask in fragment shader (FEAT_* flags)
- ✅ Hashed alpha testing, OIT transparency output
- ✅ Dangly mesh + lightsaber vertex shader support
- ✅ Deep audit cross-reference: 26 of 42 findings implemented

---

## PHASE A: GPU Skinning Integration (HIGH PRIORITY)
**Source:** Finding 5.1, gpu_skinning.py, d3_gpu_renderer.md, deep_audit lines 215-230
**Risk:** HIGH — skin vertices are currently pre-baked to world space; GPU skinning enables real-time animation

### A1: Wire MatrixPaletteUploader into GpuRenderer render loop
**File:** `src/gui/gpu_renderer.py`
**Depends on:** gpu_skinning.py (already exists with MatrixPaletteUploader, SSBO, TBN)
**Hours:** 8
**Details:**
- gpu_renderer.py currently states "Without GPU skinning, the best we can do..." (line 2302) and "should only change via GPU skinning (not yet implemented)" (line 2631)
- gpu_skinning.py contains `MatrixPaletteUploader.build_inverse_bind_pose()`, `compute_palette()`, `upload_to_ssbo()`, and `as_flat_bytes()` — all ready for integration
- reone reference: `v_model.glsl` lines 37-56 — `uBones[MAX_BONES=24]` uniform buffer with 4 bone indices/weights per vertex
- Task: In `_render_gpu()`, detect skin nodes, call `build_inverse_bind_pose()` once per model, then `compute_palette(anim_pose)` each frame, and `upload_to_ssbo()` before draw calls

### A2: Add bone index + weight vertex attributes to VBO layout
**File:** `src/gui/gpu_renderer.py` (`_build_vbo_data`)
**Hours:** 6
**Details:**
- Current VBO layout: 14 floats per vertex (pos×3, norm×3, uv×2, uv_lm×2, color×4)
- Required addition: bone_indices (ivec4) + bone_weights (vec4) = 8 additional floats per vertex
- For skin nodes: read bone_weights and bone_indices from MDL node skin data (4 per vertex, already parsed by kotor_loader)
- For non-skin nodes: fill with identity (index 0, weight 1.0, remaining zero)
- This changes the vertex stride from 14→22 floats; shader `in` declarations must match

### A3: Extend vertex shader with skeletal animation
**File:** `src/gui/gpu_renderer.py` (`_VERT_SRC`)
**Hours:** 6
**Details:**
- Add `FEAT_SKIN = 1 << 10` to feature bitmask (already defined in fragment shader)
- Add `in ivec4 in_bone_indices; in vec4 in_bone_weights;`
- Add `uniform mat4 u_bones[24];` (matches reone MAX_BONES=24)
- When `featureEnabled(FEAT_SKIN)`: compute `P = sum(u_bones[idx] * P * w)` for position and normal
- This replaces the current bind-pose-only world-space pre-bake for skin meshes
- Result: real-time skeletal animation in GPU viewport

### A4: Validate GPU skinning against known models
**Files:** New test file
**Hours:** 4
**Details:**
- Test with c_selkath (creature), PMHA01 (player head), c_brith (creature with wings)
- Verify: no extreme stretching, skin deformation matches KotOR engine behavior
- Verify: animated poses produce correct limb/joint positions
- Regression: ensure non-skin meshes (modules, placeables) are unaffected

---

## PHASE B: FBX Export Fix for Unreal (HIGH PRIORITY)
**Source:** D1 knowledge file, Findings 1.1-1.5, ROADMAP M1 (T101-T107), dev prompt Deliverable 1
**Risk:** HIGH — 0% complete; FBX export is user-facing feature that currently fails in Unreal
**File:** `src/converters/mesh_converter.py` (3,826 lines)

### B1: Fix bone hierarchy export — all MDL bones in FBX output
**Hours:** 6 | **Roadmap Task:** T101
**Details:**
- Current code filters on `n.is_dummy` for skeleton nodes — KotOR bones are not always flagged as dummy
- Finding 1.2: Must add `classification == CHARACTER` check (already implemented in v7.1 for internal use)
- FBX requires: `Model: <id>, "Model::<bone_name>", "LimbNode"` for EVERY bone, not just dummy-flagged ones
- Parent-child connections must match MDL node tree exactly
- Cross-reference: KotorBlender `armature.py` lines 129-192

### B2: Implement FBX skin deformers with correct clusters
**Hours:** 8 | **Roadmap Task:** T102
**Details:**
- Each skinned mesh needs: `Deformer: <id>, "Deformer::", "Skin"` + `Deformer: <id>, "Deformer::<bone>", "Cluster"` per bone
- Each cluster contains: vertex indices, weights, Transform (offset matrix), TransformLink (global bind pose)
- Cross-reference: ufbx `ufbx_skin_cluster.bind_to_world` = TransformLink, `ufbx_skin_cluster.geometry_to_bone` = Transform
- FBX Connections required: Cluster→Skin, Skin→Geometry, Bone→Cluster

### B3: Fix bind-pose matrix computation (Jk = Lk × Fk)
**Hours:** 8 | **Roadmap Task:** T103
**Details:**
- Mukundan 7.5.1: Offset matrix F = Translation(-Jx, -Jy, -Jz) for simple case
- TransformLink = inverse of offset matrix = global bind pose for each bone
- Gregory 5.3: MUST handle column-major (OpenGL) vs row-major (FBX) correctly — transpose when converting
- Finding 2.5: Use qBone/tBone arrays from MDL skin header (now stored in ModelNode.qbone_list/tbone_list per v7.1) as fallback bind matrices
- FBX2glTF reference: `globalBindposeInverseMatrix = transformLinkMatrix.Inverse() * transformMatrix`

### B4: Add synthetic bone stubs for supermodel bones
**Hours:** 4 | **Roadmap Task:** T104
**Details:**
- Current code synthesizes placeholder bones with potentially identity matrices
- When `base_skeleton_model` is available (from supermodel resolution), pull real transforms from it
- Non-skinned bones must still be present as LimbNode — Unreal requires complete hierarchy
- Cross-reference: KotorBlender export — how supermodel bones are included in the armature

### B5: Weight normalization — max 4 influences, sum to 1.0
**Hours:** 4 | **Roadmap Task:** T105
**Details:**
- Finding 1.4: Already implemented internally (v7.0) but must be applied to FBX export path specifically
- Sort influences by weight descending, keep top 4, re-normalize sum to 1.0
- Zero-weight guard: every vertex must have at least one bone influence
- FBX2glTF reference: `FbxSkinningAccess.cpp` lines 59-83

### B6: Animation export — rest-pose delta keyframes + Bezier handles
**Hours:** 6 | **Roadmap Task:** T106
**Details:**
- Finding 1.1: Export rotation keyframes as DELTAS from rest pose: `quat_delta = quat_inv(rest_quat) * anim_quat`
- Finding 1.5: Detect Bezier controller data (CTRL_FLAG_BEZIER=0x10) and export with `KeyAttrFlags: 24840`
- AnimCurveNode per bone per channel (Tx, Ty, Tz, Rx, Ry, Rz)
- Gregory 5.4: KotOR uses quaternions; FBX ASCII uses Euler angles — convert via matrix intermediate
- Bake keyframes at 30 fps for Unreal compatibility

### B7: FBX round-trip validation tests
**Hours:** 6 | **Roadmap Task:** T107
**Details:**
- Export c_selkath → parse with ufbx (if available) or ast-based FBX parser
- Validate: skeleton node count matches, parent-child hierarchy correct, skin cluster count matches bone count
- Validate: weight normalization (sum per vertex == 1.0 within epsilon)
- Validate: bind pose matrices are invertible and non-degenerate
- Add Unreal smoke test harness if possible

---

## PHASE C: Remaining Texture/UV Fixes (MEDIUM PRIORITY)
**Source:** D2 knowledge file, ROADMAP M2 (T201-T204), dev prompt Deliverable 2

### C1: Remove the last UV sentinel remnants from CPU path
**Hours:** 3 | **Roadmap Task:** T204 (partially done)
**Details:**
- `_UV_SENTINEL` is now `1e18` (effectively disabled, line 175 of viewport.py) — but the constant and filtering infrastructure still exist
- 6+ references to `_UV_SENTINEL` / `_accel_uv_sentinel` remain in viewport.py (lines 166, 175, 5104, 5113, 5867, 5875, 5893, 6025)
- Task: Remove the `_UV_SENTINEL` constant entirely, remove `_accel_sentinel_filter` calls, and replace with NaN/Inf-only guards
- GPU path already handles this correctly via GL_REPEAT; CPU path alignment is needed

### C2: Add TXI clamp_s/clamp_t per-texture wrap mode to CPU path
**Hours:** 3 | **Roadmap Task:** T203 (partial)
**Details:**
- `model_data.py` already has `txi_clamp_s` and `txi_clamp_t` fields
- GPU renderer already uses these for GL_CLAMP_TO_EDGE vs GL_REPEAT
- CPU path in viewport.py does not distinguish per-texture wrap mode — uses global `np.mod` (frac)
- Task: When rendering in CPU fallback, check node.txi_clamp_s/t and use np.clip vs np.mod accordingly

---

## PHASE D: GPU Renderer Polish — Remaining Items (MEDIUM PRIORITY)
**Source:** ROADMAP M4, d3_gpu_renderer.md, architecture audit Phase 2

### D1: Debug overlays — wireframe, normals, UVs, weights, depth
**Hours:** 6 | **Roadmap Task:** T403
**Details:**
- Character builder spec §8.4 requires viewport debug modes: wireframe, textured, weights, normals, UV, depth, skeleton
- Architecture audit §10.2 specifies debug passes as "Must" priority
- Implementation: Add separate shader programs or uniform-driven modes for:
  - Wireframe: draw triangles as lines (moderngl polygon offset + line mode)
  - Normals: visualize normals as color (fragment shader: `frag_color = vec4(abs(normal), 1.0)`)
  - UVs: visualize UV coordinates as RG color
  - Weights: color vertices by bone weight (heat map: blue→green→red)
  - Depth: linearize depth buffer and display as grayscale
- Wire into viewport.py's shade mode badges (currently "[TEX+PHONG]", "[FLAT(drag)]")

### D2: Screenshot/export from GPU renderer
**Hours:** 4 | **Roadmap Task:** T404
**Details:**
- GPU renderer already produces PIL images from FBO readback
- Add explicit high-resolution screenshot function: render at 2×/4× canvas size, read full MSAA resolve, save as PNG
- Support batch screenshot for model comparison workflows
- Hook into main_window.py screenshot menu item

### D3: Skeleton bone overlay improvements
**Hours:** 4 | **Roadmap Task:** T309 (partially done)
**Details:**
- Skeleton overlay exists in CPU path and partially in GPU path
- Needs: clickable bone selection in GPU mode for character builder Rig mode
- Needs: bone-name labels in overlay (small text rendering or canvas overlay)
- Needs: color-coded bone display (selected=yellow, active=green, default=white)

---

## PHASE E: Character Builder Completion (MEDIUM PRIORITY)
**Source:** D4 knowledge file, character_builder_spec.md, ROADMAP M5 (T501-T508)

### E1: Assembly mode — searchable part library browser
**Hours:** 8 | **Roadmap Task:** T503
**Details:**
- Spec §8.1: user must choose game target (K1/K2), race/species, body template, head template, eyes, teeth, tongue, hair, lashes, accessories, hooks
- Resource manager must index available parts with stable IDs and searchable metadata
- Thumbnail previews for heads/bodies
- Compatibility warnings (K1 part in K2 family, etc.)
- character_builder.py already has template registry and bone groups — expose via browser UI

### E2: Assembly mode — head-hook snapping with preview
**Hours:** 4 | **Roadmap Task:** T504
**Details:**
- Finding 3.3: `find_headhook()` + `HEADHOOK_NODE_NAMES` already implemented (v7.1)
- Task: Wire into character builder Assembly mode — when user selects head+body, snap head root to body's headhook world transform
- Visualize alignment in GPU viewport
- Check seam continuity at neck boundary

### E3: Rig mode — template-guided KOTOR rig transfer
**Hours:** 8 | **Roadmap Task:** T505 (partial)
**Details:**
- Spec §8.2: Template transfer as default for KOTOR heads and humanoid bodies
- Must support: manual joint move/rotate with gizmos, mirror/symmetry editing, lock centerline, region-based selection
- auto_rigger.py has Library Rig and heat-map weights; grig.py has manual bone assignment + brush weight painting
- Task: integrate these into Rig mode panel with mode-appropriate tool exposure
- Add symmetry-aware weight mirroring (L↔R bone pairs)

### E4: Face mode — facial validation and phoneme preview
**Hours:** 6 | **Roadmap Task:** T507
**Details:**
- Finding 3.4: validate_facial_bones() already implemented (v7.1) — checks head_g, f_jaw_g, f_um_g, f_Llm_g, f_Rlm_g, MaskHook, GoggleHook
- Finding 3.1-3.2: LIPPlayback class exists in character_builder.py (v7.2)
- Task: Wire facial validation into Face mode panel
- Add phoneme test preset buttons (jaw open/close, blink, test phonemes)
- Add close-up camera preset for face inspection
- Add seam/clipping check visualization around neck, lips, eyelids, eyeballs, teeth

### E5: Preview mode — animation playback + lighting presets
**Hours:** 5 | **Roadmap Task:** T506 (partial)
**Details:**
- Spec §8.4: Must support idle, walk, talk, test expression, test phoneme
- Lighting presets: neutral studio, high contrast, overhead, in-game approximate
- Viewport debug modes should be accessible from Preview mode
- Turntable playback with optional side-by-side compare against template
- Camera presets: front/back/left/right/top/bottom buttons already referenced in spec

### E6: Export mode — validated export with pre-flight checks
**Hours:** 6 | **Roadmap Task:** T508
**Details:**
- Spec §8.5: KOTOR MDL/MDX workflow, FBX, glTF/GLB, OBJ, Sidecar JSON
- validation_service.py rules (hooks, supermodel, K1/K2, weights) must gate export
- Display validation summary inline before final export
- Generate machine-readable export report (JSON) with warnings
- Emit sidecar JSON preserving: game target, supermodel, hooks, head/body pairing, material IDs, validation results

---

## PHASE F: Performance & Memory Management (MEDIUM PRIORITY)
**Source:** D5 knowledge file, ROADMAP M6 (T601-T604), architecture audit Phase 3

### F1: Lazy loading for Override assets
**Hours:** 6 | **Roadmap Task:** T602
**Details:**
- resource_manager.py `_GameInstall._load_override()` currently preloads ALL Override files into `_override: Dict[str, bytes]`
- Gregory 7.2: "Don't load until first reference; placeholder texture until ready"
- Task: Replace eager preload with lazy-on-first-access pattern
- Add configurable cache ceiling (default 512 MB CPU, 256 MB GPU)
- Track hit/miss metrics for diagnostics

### F2: LRU eviction for GPU texture cache
**Hours:** 6 | **Roadmap Task:** T601
**Details:**
- `_GlTexCache` in gpu_renderer.py uses `OrderedDict` with `MAX_ENTRIES=512` and LRU eviction
- Worst-case: ~341 MB VRAM for 512 512×512 textures
- Current implementation exists but lacks reference counting or memory budget enforcement
- Task: Add per-texture size tracking, enforce VRAM budget (configurable, default 256 MB), add eviction logging
- Coordinate with CPU PIL cache to avoid redundant decoded textures

### F3: Frustum culling integration in GPU renderer
**Hours:** 4 | **Roadmap Task:** T603
**Details:**
- scene_manager.py already has `Frustum` class with `test_sphere()`, `test_aabb()`, and `update_from_matrix()`
- gpu_renderer.py does not perform frustum culling before draw calls
- For module scenes with many rooms, this can skip significant geometry
- Task: Before each node's draw call, test its bounding sphere/AABB against the camera frustum
- Compute and cache per-node bounding volumes during VBO build

### F4: Background texture decoding
**Hours:** 6 | **Roadmap Task:** T604
**Details:**
- DXT1/DXT5 decompression, TPC header parsing currently happen synchronously
- Gregory 7.2: "Decode/upload textures asynchronously to avoid frame hitches"
- Task: Spawn texture decode on background thread, use 1×1 placeholder until ready, then hot-swap
- Coordinate with GPU texture cache invalidation on swap

---

## PHASE G: Module Scene & Export Pipeline Expansion (LOWER PRIORITY)
**Source:** D6 knowledge file, ROADMAP M6-M7, architecture audit Phase 6

### G1: LYT room positioning integration
**Hours:** 4 | **Finding:** 4.1
**Details:**
- scene_manager.py + module_loader.py already implement basic LYT parsing
- Task: Verify rooms are positioned correctly using LYT offsets; add visual diagnostics
- Test with m02aa (Taris) which was the validation model for lightmap/module fixes

### G2: LYT door hook quaternion integration
**Hours:** 3 | **Finding:** 4.2 (already in data model)
**Details:**
- LYTDoorHook already has qx/qy/qz/qw fields; parser reads optional quaternion (v7.2)
- Task: Apply door rotation during module scene assembly; verify doors are correctly oriented
- Test with known door-heavy modules

### G3: Walkmesh surface-type FBX materials for Unreal
**Hours:** 4 | **Finding:** 4.3 (already in data model)
**Details:**
- WALKMESH_FBX_MATERIALS dict + get_walkmesh_fbx_material() exist (v7.2)
- Task: Wire into actual FBX export path — when exporting module walkmesh to FBX, use surface-type materials
- Maps to UE5 physics material system for walkable/non-walkable/water surfaces

### G4: glTF/GLB skeletal export
**Hours:** 8 | **Roadmap Task:** T701
**Details:**
- gltf_importer.py exists but export path is incomplete
- Need: mesh + skeleton + skin extension + animation export to glTF 2.0
- Cross-reference: FBX2glTF conversion patterns
- This provides modern interchange alternative to FBX

### G5: Batch export — all models in library
**Hours:** 6 | **Roadmap Task:** T703
**Details:**
- Character builder already has single-model export
- Task: Add batch export UI — select multiple models from library, export all to chosen format
- Progress bar, per-model validation report, skip/continue on errors

### G6: Sidecar JSON metadata emission
**Hours:** 4 | **Roadmap Task:** T702
**Details:**
- Spec §13: Every non-native export should emit sidecar JSON with: game target, supermodel, hooks, head/body pairing, material IDs, asset IDs, source templates, validation results, export settings
- Template exists in character_builder_spec §13
- Wire into FBX/glTF/OBJ export paths

---

## PHASE H: Validation & Regression Hardening (LOWER PRIORITY)
**Source:** ROADMAP M8 (T801-T804), architecture audit Testing section

### H1: Golden-file tests — known-good FBX reference outputs
**Hours:** 6 | **Roadmap Task:** T801
**Details:**
- Export canonical models (c_selkath, PMHA01, player body) → save as golden files
- Compare future exports against golden files for structural regression
- Detect: changed bone count, missing skin clusters, altered bind pose matrices

### H2: Visual regression — screenshot diff for rendering
**Hours:** 6 | **Roadmap Task:** T802
**Details:**
- Render canonical models via GPU renderer → save as reference screenshots
- Use image diff (SSIM or pixel MSE) to detect rendering regressions
- Key models: c_selkath (creature), PMHA01 (head), m02aa_01a (module room)
- Catches: texture corruption, depth artifacts, lighting changes

### H3: Round-trip validation — export → reimport
**Hours:** 6 | **Roadmap Task:** T803
**Details:**
- Export FBX → reimport via available parser → verify structure matches
- If ufbx available: use C parser for definitive validation
- Otherwise: use ast-based FBX token parser or Blender Python API
- Verify: node count, hierarchy, skin weights, animation keyframes

### H4: CI pipeline setup
**Hours:** 4 | **Roadmap Task:** T804
**Details:**
- GitHub Actions workflow for: syntax check, pytest, FBX validation
- Matrix: Python 3.10/3.11/3.12, with/without optional deps
- PyKotor install must succeed for test collection
- Add environment self-test command

---

## PHASE I: Remaining Deep Audit Findings (LOWER PRIORITY)
**Source:** deep_audit_cross_reference.md — findings NOT yet implemented

### I1: Finding 2.3 — Bone map float→int cast validation
**Hours:** 2
**Details:**
- Verify MDL parser correctly reads bone_map as float on PC and casts to int
- Handle -1.0 sentinel for unused slots (0xFFFF for uint16, -1.0 for float)
- KotorBlender `reader.py` lines 508-521; xoreos `model_kotor.cpp` lines 942-958

### I2: Finding 2.4 — Skin weight reading order verification
**Hours:** 2
**Details:**
- Verify: 4 weights + 4 bone indices per vertex from MDX data
- All reference repos agree: weights first, then indices
- Audit kotor_loader.py to ensure this order is correct

### I3: Finding 2.1/2.2 — NODE_SKIN flag and CLASS_CHARACTER verification
**Hours:** 1
**Details:**
- Confirm NODE_SKIN = 0x0040 and CLASS_CHARACTER = 0x04 are used correctly
- Already confirmed in audit — this is a validation pass, not new code

### I4: Finding 5.1 — Complete GPU skinning integration testing
**Hours:** 4
**Details:**
- After Phase A is complete, validate GPU skinning against all reference implementations
- Verify bone matrix palette matches reone's `uBones[MAX_BONES=24]`
- Test with various bone counts (2-bone creature through 24+ bone humanoid)

### I5: Finding 4.4 — Room frustum culling full integration
**Hours:** 4
**Details:**
- After Phase F3, test frustum culling with multi-room modules
- Verify: rooms fully outside frustum produce zero draw calls
- Benchmark: FPS improvement on large modules (20+ rooms)

---

## PHASE J: Architecture Consolidation (ONGOING)
**Source:** Architecture audit conclusions, engine architecture book guidance

### J1: Make GPU renderer the default viewport path
**Hours:** 4
**Details:**
- Architecture audit conclusion: "the main viewport behavior is still effectively centered on the CPU renderer"
- Task: Invert priority — viewport.py should prefer GpuRenderer when available, FrameRenderer becomes offline/fallback only
- Add user-facing "GPU active / CPU fallback" indicator in viewport HUD
- Already partially done via _toggle_gpu_renderer; need to make GPU the default

### J2: Reduce viewport.py CPU-renderer dead code
**Hours:** 8
**Details:**
- viewport.py is 9,452 lines — much of which is CPU painter's algorithm and workaround infrastructure
- With GPU as default, the CPU path can be simplified
- Remove: inner-geometry substring promotion logic (handled by GPU depth buffer)
- Remove: painter's algorithm sorting code (replaced by GPU z-buffer)
- Preserve: CPU fallback core functionality for headless/no-GPU environments

### J3: Unify texture cache ownership
**Hours:** 4
**Details:**
- Currently: PIL cache in viewport.py + GL cache in gpu_renderer.py + potential overlap
- Task: Single cache tier model: Disk → CPU PIL (budget 512MB) → GPU GL (budget 256MB)
- gpu_renderer._GlTexCache should be the authoritative GPU cache; viewport should delegate
- Eliminate duplicate PIL image retention when GPU has the texture uploaded

### J4: Domain-driven GUI panels (module editor)
**Hours:** 6
**Details:**
- Architecture audit: module loader stack is a relative strength; use as model for rest of codebase
- modular_panel.py should consume scene/module services, not reimplement them
- scene_manager.py provides clean domain data; GUI should be presentation only

---

## EXECUTION PRIORITY ORDER

### Sprint 1 (Highest Impact, Core Functionality)
1. **B1-B7** — FBX Export Fix (0% complete, user-facing failure)
2. **A1-A4** — GPU Skinning Integration (enables real-time animation)

### Sprint 2 (User Experience, Polish)
3. **D1** — Debug overlays (needed for character builder)
4. **E1-E6** — Character Builder completion
5. **C1-C2** — Final UV sentinel cleanup

### Sprint 3 (Performance, Reliability)
6. **F1-F4** — Performance & memory management
7. **D2-D3** — Screenshot export + skeleton overlay improvements
8. **H1-H4** — Validation & regression suite

### Sprint 4 (Expansion, Consolidation)
9. **G1-G6** — Module scene + export pipeline expansion
10. **I1-I5** — Remaining deep audit findings
11. **J1-J4** — Architecture consolidation

---

## CROSS-REFERENCE: Task → Source Evidence

| Task | Research Source | Knowledge File | Reference Repo | Book Section |
|------|---------------|----------------|----------------|-------------|
| A1-A4 | Finding 5.1 | d3_gpu_renderer.md | reone v_model.glsl | Mukundan 7.5-7.6 |
| B1 | Finding 1.2 | d1_fbx_export.md | KotorBlender armature.py | Mukundan 7.3 |
| B2 | T102 | d1_fbx_export.md | ufbx ufbx.h | Mukundan 7.5 |
| B3 | Finding 1.3 | d1_fbx_export.md | FBX2glTF FbxSkinningAccess.cpp | Mukundan 7.5.1, Gregory 5.3 |
| B4 | T104 | d1_fbx_export.md | KotorBlender export.py | Mukundan 7.5 |
| B5 | Finding 1.4 | d1_fbx_export.md | ufbx ufbx.h | Mukundan 7.6 |
| B6 | Findings 1.1, 1.5 | d1_fbx_export.md | KotorBlender armature.py | Gregory 5.4 |
| B7 | T107 | d1_fbx_export.md | ufbx test/ | — |
| C1 | T201, T204 | d2_texture_wrapping.md | KotOR.js TPCObject.ts | Hayes Ch 7 |
| C2 | T203 | d2_texture_wrapping.md | reone texture.cpp | Hayes Ch 7 |
| D1 | T403 | d3_gpu_renderer.md | reone shaders | Hayes Ch 9 |
| D2 | T404 | d3_gpu_renderer.md | — | Hayes Ch 13 |
| D3 | T309 | d3_gpu_renderer.md | KotOR.js | — |
| E1-E6 | T501-T508 | d4_character_builder.md | PyKotor, KotorBlender | Gregory 7.2 |
| F1 | T602 | d5_performance.md | — | Gregory 7.2 |
| F2 | T601 | d5_performance.md | KotOR.js | Gregory 7.2 |
| F3 | Finding 4.4, T603 | d5_performance.md | reone context.h | Gregory 12.5 |
| F4 | T604 | d5_performance.md | — | Gregory 7.2 |
| G1 | Finding 4.1 | d6_module_scene.md | KotorBlender lyt.py | — |
| G4 | T701 | — | FBX2glTF | — |
| H1-H4 | T801-T804 | — | ufbx, KotorBlender | — |
| J1-J4 | Arch audit | — | reone, KotOR.js | Gregory Ch 7-8 |

---

## TOTAL ESTIMATED EFFORT

| Phase | Tasks | Hours | Priority |
|-------|-------|-------|----------|
| A: GPU Skinning | 4 | 24 | HIGH |
| B: FBX Export | 7 | 42 | HIGH |
| C: UV Cleanup | 2 | 6 | MEDIUM |
| D: GPU Polish | 3 | 14 | MEDIUM |
| E: Character Builder | 6 | 37 | MEDIUM |
| F: Performance | 4 | 22 | MEDIUM |
| G: Module/Export | 6 | 29 | LOWER |
| H: Validation | 4 | 22 | LOWER |
| I: Audit Findings | 5 | 13 | LOWER |
| J: Architecture | 4 | 22 | ONGOING |
| **TOTAL** | **45** | **231** | — |

---

## PRE-CODING PROTOCOL REMINDER

Before ANY task above, follow the MANDATORY_CHECKLIST.md:
1. Read knowledge base INDEX.md
2. Identify deliverable and read knowledge file
3. Check cross_reference_map.md for reference repos and books
4. Check book_extracts.md for relevant principles
5. Check ROADMAP.md for dependencies
6. Read the FULL source file before editing
7. State diagnosis and plan BEFORE writing code
