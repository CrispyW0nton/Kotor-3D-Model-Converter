# GhostRigger v6.0 Iteration Roadmap
# ====================================
# Generated: 2026-04-13
# Source: ghostrigger_developer_handoff_bundle.zip + reference books
# Total Estimated Effort: 35-50 dev-days (~220 hours)
# Execution Order: M0 -> M1 -> M2 -> M3 -> M4 -> M5 -> M6 -> M7 -> M8

---

## Milestone Overview

| Milestone | Name | Priority | Effort | Bugs Fixed | Features | Dependencies |
|-----------|------|----------|--------|------------|----------|-------------|
| M0 | Environment & Audit | CRITICAL | 1-2 days | 0 | Setup | None |
| M1 | FBX Export Fix | HIGH | 5-7 days | 1 (broken FBX) | Unreal import | M0 |
| M2 | Texture Wrapping Fix | HIGH | 2-3 days | 1 (UV sentinel) | Correct tiling | M0 |
| M3 | GPU Renderer Foundation | HIGH | 7-9 days | 2 (depth, perf) | GPU viewport | M0 |
| M4 | GPU Renderer Polish | MEDIUM | 3-4 days | 0 | Quality | M3 |
| M5 | Character Builder | MEDIUM | 5-7 days | 0 | Dedicated workspace | M3, M1 |
| M6 | Performance Polish | MEDIUM | 3-4 days | 0 | Memory mgmt | M3 |
| M7 | Export Pipeline Expansion | LOW | 3-4 days | 0 | glTF, batch | M1 |
| M8 | Validation & Regression | LOW | 3-4 days | 0 | CI, golden tests | M1, M2, M3 |

---

## M0: Environment & Audit (COMPLETE as of v6.0)
**Status**: DONE

| Task | Description | Status | Notes |
|------|------------|--------|-------|
| T001 | Clone reference repos | PENDING | ufbx, KotorBlender, KotOR.js, reone, xoreos, FBX2glTF |
| T002 | Audit viewport.py rendering path | DONE | Documented in architecture_audit.html |
| T003 | Audit mesh_converter.py export path | DONE | FBX ASCII fallback identified |
| T004 | Audit gpu_renderer.py state | DONE | Exists but not primary path |
| T005 | Remove test suite & clutter | DONE | v6.0 commit |
| T006 | Set up knowledge base | DONE | .ghostrigger_reference/ |

### Remaining M0 Task
**T001 - Clone Reference Repos**: Must be done before M1 coding begins.
```bash
cd /home/user/webapp
mkdir -p .reference_repos
git clone --depth 1 https://github.com/bqqbarbhg/ufbx.git .reference_repos/ufbx
git clone --depth 1 https://github.com/seedhartha/kotorblender.git .reference_repos/kotorblender
git clone --depth 1 https://github.com/KobaltBlu/KotOR.js.git .reference_repos/kotorjs
git clone --depth 1 https://github.com/OldRepublicDevs/PyKotor.git .reference_repos/pykotor
git clone --depth 1 https://github.com/seedhartha/reone.git .reference_repos/reone
git clone --depth 1 https://github.com/xoreos/xoreos.git .reference_repos/xoreos
git clone --depth 1 https://github.com/facebookincubator/FBX2glTF.git .reference_repos/fbx2gltf
```

---

## M1: FBX Export Fix (Deliverable 1)
**Status**: NOT STARTED
**File**: `src/converters/mesh_converter.py`
**Knowledge**: `.ghostrigger_reference/knowledge_base/d1_fbx_export.md`
**Depends on**: M0 (reference repos cloned)
**Critical path**: T101 -> T102 -> T103 -> T105 -> T106 -> T107

| Task | Description | Hours | Status | Acceptance Criteria |
|------|------------|-------|--------|-------------------|
| T101 | Fix bone hierarchy export | 6 | PENDING | All MDL bones in FBX output; parent-child matches MDL tree |
| T102 | Implement FBX skin deformers | 8 | PENDING | Deformer + SubDeformer (Cluster) per weighted bone |
| T103 | Fix bind-pose matrix (Jk=Lk*Fk) | 8 | PENDING | TransformLink = global bind pose; Transform = offset |
| T104 | Synthetic bone stubs | 4 | PENDING | Non-skinned bones present as LimbNode |
| T105 | Weight normalization | 4 | PENDING | Per-vertex sum = 1.0; max 4 influences |
| T106 | Animation export to FBX | 4 | PENDING | AnimCurveNode per bone; keyframes match MDL |
| T107 | Regression tests | 4 | PENDING | ufbx parses output; Unreal imports without error |

### Pre-coding Checklist for M1
- [ ] Read `d1_fbx_export.md` completely
- [ ] Study ufbx `ufbx_skin_cluster` and `ufbx_skin_deformer` structures
- [ ] Study KotorBlender skin export code
- [ ] Review Mukundan Ch 7.5 (offset matrix) and 7.6 (vertex blending)
- [ ] Review Gregory Ch 5.3 (matrix conventions) and 5.4 (quaternions)
- [ ] Read the current `mesh_converter.py` FBX export section completely

### Commit Messages (prescribed)
```
feat(fbx): implement full skeleton hierarchy export (T101)
feat(fbx): add skin deformer and cluster nodes (T102)
feat(fbx): compute correct bind-pose matrices Jk=Lk*Fk (T103)
feat(fbx): add synthetic bone stubs for non-skinned nodes (T104)
feat(fbx): normalize vertex weights per bone (T105)
feat(fbx): export animation curves to FBX (T106)
test(fbx): add ufbx round-trip validation tests (T107)
```

---

## M2: Texture Wrapping Fix (Deliverable 2)
**Status**: NOT STARTED
**File**: `src/gui/viewport.py`
**Knowledge**: `.ghostrigger_reference/knowledge_base/d2_texture_wrapping.md`
**Depends on**: M0
**Can run in parallel with M1**

| Task | Description | Hours | Status | Acceptance Criteria |
|------|------------|-------|--------|-------------------|
| T201 | Remove UV sentinel logic | 4 | PENDING | No _UV_SENTINEL; no magnitude-based UV filter |
| T202 | Implement frac() UV repeat | 4 | PENDING | UVs > 1.0 tile via np.mod / fract() |
| T203 | Add TXI clamp/decal support | 4 | PENDING | TXI `clamp 1` -> clamp mode; else repeat |
| T204 | Remove module workaround code | 4 | PENDING | No special-case module UV handling |

### Pre-coding Checklist for M2
- [ ] Read `d2_texture_wrapping.md` completely
- [ ] Study KotOR.js TPC/TXI texture wrap handling
- [ ] Review Hayes Ch 7 (GL_REPEAT, GL_CLAMP_TO_EDGE)
- [ ] Read viewport.py sections with _UV_SENTINEL and np.clip
- [ ] Identify all UV sentinel references in codebase

### Commit Messages
```
fix(uv): remove UV sentinel filter and magnitude guard (T201)
fix(uv): implement frac() repeat for tiling textures (T202)
feat(uv): add TXI clamp/decal wrap mode support (T203)
refactor(uv): remove module-specific UV workaround (T204)
```

---

## M3: GPU Renderer Foundation (Deliverable 3)
**Status**: NOT STARTED
**File**: `src/gui/gpu_renderer.py`, `src/gui/viewport.py`
**Knowledge**: `.ghostrigger_reference/knowledge_base/d3_gpu_renderer.md`
**Depends on**: M0
**Can start in parallel with M1/M2 but needs M2 for texture params**

| Task | Description | Hours | Status | Acceptance Criteria |
|------|------------|-------|--------|-------------------|
| T301 | Create ModernGL context | 6 | PENDING | Standalone context; integrates with tkinter |
| T302 | VBO/VAO pipeline | 8 | PENDING | Per-mesh VAO with pos/norm/uv buffers |
| T303 | GLSL shaders (vertex + fragment) | 8 | PENDING | MVP transform + Blinn-Phong + texture sampling |
| T304 | Enable depth testing | 4 | PENDING | GL_DEPTH_TEST; FBO with depth attachment |
| T305 | Texture parameters (wrap, filter) | 6 | PENDING | GL_REPEAT default; GL_CLAMP per TXI |
| T306 | Three-pass rendering | 8 | PENDING | Opaque -> cutout -> transparent; no artifacts |
| T307 | Camera controls | 6 | PENDING | Orbit/pan/zoom; mouse+keyboard; matches CPU cam |
| T308 | Viewport toggle (CPU<->GPU) | 4 | PENDING | UI switch; both renderers produce similar output |
| T309 | Skeleton overlay | 5 | PENDING | Line-draw bones after mesh passes |

### Pre-coding Checklist for M3
- [ ] Read `d3_gpu_renderer.md` completely
- [ ] Study reone OpenGL context and shader code
- [ ] Study KotOR.js render pipeline
- [ ] Review Hayes Ch 4 (VBO/VAO), Ch 7 (textures), Ch 9 (real-time), Ch 13 (framebuffers)
- [ ] Review Gregory Ch 8 (render loop)
- [ ] Read the existing `gpu_renderer.py` completely

### Commit Messages
```
feat(gpu): create ModernGL standalone context (T301)
feat(gpu): implement VBO/VAO pipeline per mesh node (T302)
feat(gpu): add GLSL vertex and fragment shaders (T303)
feat(gpu): enable depth testing with FBO depth attachment (T304)
feat(gpu): set texture wrap/filter parameters per TXI (T305)
feat(gpu): implement three-pass rendering pipeline (T306)
feat(gpu): add orbit/pan/zoom camera controls (T307)
feat(gpu): add CPU<->GPU viewport toggle in UI (T308)
feat(gpu): add skeleton bone overlay rendering (T309)
```

---

## M4: GPU Renderer Polish
**Status**: NOT STARTED
**Depends on**: M3

| Task | Description | Hours | Status |
|------|------------|-------|--------|
| T401 | MSAA (4x multisampling) | 4 | PENDING |
| T402 | Environment/ambient lighting | 4 | PENDING |
| T403 | Debug overlays (wireframe, normals, UVs) | 6 | PENDING |
| T404 | Screenshot/export from GPU | 4 | PENDING |

---

## M5: Character Builder (Deliverable 4)
**Status**: NOT STARTED
**Depends on**: M3 (GPU viewport), M1 (export)
**Knowledge**: `.ghostrigger_reference/knowledge_base/d4_character_builder.md`

| Task | Description | Hours | Status |
|------|------------|-------|--------|
| T501 | New CharacterBuilder window | 8 | PENDING |
| T502 | Workflow navigation (5 modes) | 6 | PENDING |
| T503 | Part library browser | 6 | PENDING |
| T504 | Head-hook snapping | 4 | PENDING |
| T505 | Symmetry-aware rigging | 6 | PENDING |
| T506 | Camera presets | 3 | PENDING |
| T507 | Facial preview (LIP) | 4 | PENDING |
| T508 | Validation panel | 6 | PENDING |

---

## M6: Performance Polish (Deliverable 5)
**Status**: NOT STARTED
**Depends on**: M3 (GPU renderer)
**Knowledge**: `.ghostrigger_reference/knowledge_base/d5_performance.md`

| Task | Description | Hours | Status |
|------|------------|-------|--------|
| T601 | Texture cache with LRU eviction | 8 | PENDING |
| T602 | Lazy loading | 6 | PENDING |
| T603 | Frustum culling | 4 | PENDING |
| T604 | Background texture decoding | 6 | PENDING |

---

## M7: Export Pipeline Expansion
**Status**: NOT STARTED
**Depends on**: M1 (FBX fix)

| Task | Description | Hours | Status |
|------|------------|-------|--------|
| T701 | glTF/GLB skeletal export | 8 | PENDING |
| T702 | Side-car JSON metadata | 4 | PENDING |
| T703 | Batch export (all models in library) | 6 | PENDING |
| T704 | Export report generation | 4 | PENDING |

---

## M8: Validation & Regression Suite
**Status**: NOT STARTED
**Depends on**: M1, M2, M3

| Task | Description | Hours | Status |
|------|------------|-------|--------|
| T801 | Golden-file tests (known-good FBX) | 6 | PENDING |
| T802 | Visual regression (screenshot diff) | 6 | PENDING |
| T803 | Round-trip validation (export -> reimport) | 6 | PENDING |
| T804 | CI pipeline setup | 4 | PENDING |

---

## Critical Path

```
M0 (Setup) ──┬──> M1 (FBX Export) ──┬──> M5 (Character Builder)
              │                       │
              ├──> M2 (UV Fix) ──────>├──> M7 (Export Expansion)
              │                       │
              └──> M3 (GPU Renderer) ─┼──> M4 (GPU Polish)
                                      │
                                      ├──> M6 (Performance)
                                      │
                                      └──> M8 (Validation)
```

**Shortest path to "Done" (Iteration 1)**: M0 -> M1 + M2 (parallel) -> M3 -> verify all acceptance criteria

---

## Effort Summary by Module

| File | Total Hours | Risk | Milestones |
|------|------------|------|------------|
| `src/converters/mesh_converter.py` | ~50 h | HIGH | M1, M7 |
| `src/gui/gpu_renderer.py` | ~55 h | HIGH | M3, M4, M6 |
| `src/gui/viewport.py` | ~20 h | MEDIUM | M2, M3 |
| `src/gui/character_builder_window.py` | ~43 h | MEDIUM | M5 |
| `src/resources/resource_manager.py` | ~20 h | MEDIUM | M6 |
| `src/core/scene_manager.py` | ~14 h | LOW | M6 |
| `src/gui/main_window.py` | ~10 h | LOW | M3, M5 |
| Test infrastructure | ~22 h | LOW | M8 |

---

## Reference Study Order (before coding begins)

| Order | Repo/Book | Est. Time | What to Learn |
|-------|-----------|-----------|--------------|
| 1 | ufbx (repo) | 2-3 h | FBX skeletal structures (for M1) |
| 2 | KotorBlender (repo) | 3-4 h | Armature, skin export, animation (for M1) |
| 3 | KotOR.js (repo) | 2-3 h | GPU renderer architecture, TPC/TXI (for M2, M3) |
| 4 | Mukundan Ch 7 (book) | 2 h | Skeleton, bones, skinning, weights (for M1) |
| 5 | Hayes Ch 4, 7, 13 (book) | 2 h | VBO/VAO, textures, framebuffers (for M3) |
| 6 | Gregory Ch 5, 7, 8 (book) | 2 h | Math, resources, game loop (for M1, M3, M6) |
| 7 | PyKotor (repo) | 1-2 h | MDL/TPC parsing details (for M1, M2) |
| 8 | reone (repo) | 2-3 h | OpenGL KotOR renderer (for M3) |
| 9 | xoreos (repo) | 1-2 h | Aurora model loading (validation) |
| 10 | FBX2glTF (repo) | 1 h | Conversion patterns (for M7) |

---

## Rules of Engagement
1. **READ THE MANDATORY_CHECKLIST.md BEFORE EVERY TASK**
2. Only modify files specified in the task description
3. Verify approach against reference repos before coding
4. Verify approach against book principles before coding
5. Show diagnosis & plan before coding (explain what and why)
6. All existing functionality must be preserved
7. Commit with prescribed message format after each task
8. "Done" = FBX imports in Unreal + textures tile correctly + GPU depth works + all criteria met
