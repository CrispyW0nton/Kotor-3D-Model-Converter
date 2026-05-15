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

## Completed Validation & Pipeline Work

| Item | Status | Notes |
|------|--------|-------|
| MCP-driven validation pipeline | COMPLETE | KotorMCP-driven manifest, tiered scan, and analyzer committed |
| Full K1+K2 model scan | COMPLETE | 6,272 MDL resources scanned across K1 and K2 |
| K2 compatibility fixes | COMPLETE | Trimesh header and MDX offset handling validated |
| Head-accessory composite offset (Bug C) | COMPLETE | Composite attachment offsets validated by regression tests |
| Centroid heuristic removal | COMPLETE | VertexSpace enum replaces centroid-magnitude classification |
| Performance optimization | COMPLETE | 7.8x FPS boost retained in current renderer path |
| Lightmap overbright fix | COMPLETE | Lightmap handling no longer over-brightens module geometry |
| Unified render constants | COMPLETE | Shared render constants prevent divergent face/inner-geometry filters |
| Bonemap overflow handling | COMPLETE | Skin bonemap overflow path validated; 0 skinning issues in scan |

## Current / Next Work

| Item | Status | Notes |
|------|--------|-------|
| Walkmesh editing | NEXT | Continue Module Editor `.wok` selection, painting, and write-back |
| Module editing | NEXT | Continue `.lyt` scene graph, room placement, and GIT export |
| GPU renderer migration | IN PROGRESS | CPU renderer remains primary; GPU path still needs full migration |
| Resolve 48 upstream PyKotor load failures | NEXT | Requires PyKotor patches; GhostRigger has 0 GhostRigger-only load failures |
| Expand module-tier scan to full pipeline comparison | NEXT | Optimization needed; full module compare currently takes 2-4 min/model |

---

## M0: Environment & Audit (COMPLETE as of v6.0)
**Status**: DONE

| Task | Description | Status | Notes |
|------|------------|--------|-------|
| T001 | Clone reference repos | PENDING | ufbx, KotorBlender, KotOR.js, reone, xoreos, FBX2glTF |
| T002 | Audit viewport.py rendering path | DONE | Documented in architecture_audit.html |
| T003 | Audit mesh_converter.py export path | DONE | FBX ASCII fallback identified |
| T004 | Audit gpu_renderer.py state | DONE | Exists but not primary path |
| T005 | Remove obsolete clutter | DONE | Legacy diagnostics and generated junk removed; current MCP test suite retained |
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

## M5: Character Builder & Rigging Workspace (Deliverable 4)
**Status**: REPLANNED 2026-05 — four-mode workspace
**Depends on**: M3 (GPU viewport), M1 (export)
**Knowledge**: `.ghostrigger_reference/knowledge_base/d4_character_builder.md`
**Branch scope**: All work in this milestone lands on `qt-ghostrigger`. Nothing
touches `main`.

### Reference Sources (baked into this plan, 2026-05)

- **AccuRig 6-step workflow video** — Load Character → Check Model → Body Rig →
  Hand Rig → Check Actor → Add Motions. Numbered left-sidebar UX, joint-dot
  guide system, dual front/back view, midpoint placement, joint-opacity/size
  sliders, symmetry, finger count, export to iClone / USD / FBX.
- **Facial rigging tutorial video** — left wizard sidebar, central head viewport,
  context-sensitive right-hand property panel, ortho front/side presets,
  jaw-pivot precision, neck hierarchy, weight-paint influence-lock list,
  viseme / expression scrub.
- **Stewart Jones — *Digital Creature Rigging: Wings, Tails & Tentacles for
  Animation & VFX*** (CRC Press, 2019) — 3-Stage Asset Build (Base /
  Animation / Deformation), 12 rigging principles, naming convention,
  blocked-weighting workflow, Custom Spline-IK, wing FLAP/FOLD/LINK +
  Reaction-Manager fold driver, cloth membranes, real-time export
  constraints.

### The Four KOTOR Rig Modes

| Mode | KOTOR Reality | Skeleton | UX Comparable |
|------|--------------|----------|---------------|
| **Headless Body** | Body mesh with no head (`pfbc*`, `pmbc*`, `n_darkjedi`). Skinned humanoid skeleton ending at the `neck` bone; head plugs in at `headhook`. | Humanoid (chest → neck → headhook + arms + legs). No jaw, no eye bones. | AccuRig body rig, truncated at the neck. |
| **Head** | Standalone head model (`pfhc*`, `pmhc*`, `p_hk47`). Either rigid (jaw is geometry) or rigged with jaw + lip bones for talking heads. | Head + neck stub + optional jaw, eyes (L/R), tongue, teeth-upper, teeth-lower. | Facial rigging video — wizard sidebar + viseme preview. |
| **Supermodel (Combined)** | Body + head assembled at runtime via `headhook`. Carries the full humanoid animation set (the "supermodel"). | Full hierarchy: humanoid + facial chain glued at `headhook`. | AccuRig + Facial workflow steps appended. |
| **Creature** | Non-humanoid (`c_bantha`, `c_dewback`, `c_rancor`, `c_gammorean`, `c_drdastro`). Skeleton bespoke per species — wings, tails, tentacles, optional fingers. | Anatomy-driven, often quadruped + tail/wing/tentacle add-ons. | Jones book — wings/tails/tentacles, Custom Spline-IK, COG at chest for fliers, centre-of-mass for swimmers. |

These labels are already in the data layer
(`src/core/model_data.py::PartSlot`, `ModelClassification`,
`src/autorig/accurig.py::PROFILE_HUMANOID / QUADRUPED / DROID / CREATURE`) —
what is missing is a single `RigMode` selector that wires it all together
(T501).

### Final Window Layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Menu Bar:  File | Edit | View | Tools | Rigging | Help                       │
├────────────────┬─────────────────────────────────────┬───────────────────────┤
│  STEP SIDEBAR  │         CENTRAL VIEWPORT            │  CONTEXTUAL PROPERTY  │
│  (left, fixed) │   (front + back dual-view split,    │       PANEL           │
│                │    or single perspective view)      │  (right, QStackedW)   │
│ [Mode strip]   │                                     │                       │
│ ◉ Headless     │   ┌──────────┐ ┌──────────┐         │  Step header          │
│ ○ Head         │   │  FRONT   │ │   BACK   │         │  ──────────────       │
│ ○ Supermodel   │   │          │ │          │         │  Joint Name [dropdown]│
│ ○ Creature     │   │  • • •   │ │  • • •   │         │  ☐ Symmetry           │
│                │   │ • cyan • │ │ • cyan • │         │  ☐ Midpoint Placement │
│ 1 Load Model   │   │ • yellow │ │ • yellow │         │  ◉ Whole Mesh         │
│ 2 Check Model  │   │  • • •   │ │  • • •   │         │  ○ Front Part         │
│ 3 Body Rig     │   └──────────┘ └──────────┘         │                       │
│ 4 Hand Rig     │                                     │  Joint Opacity ───●── │
│ 5 Face Rig*    │   Bottom-left HUD: model name,      │  Joint Size    ──●─── │
│ 6 Check Actor  │   game version, classification.     │  [Reset All Masks]    │
│ 7 Add Motions  │   Top-right HUD: FPS + render time  │                       │
│                │   (already shipped: qt_viewport.py) │  ─── Upload & Save ── │
│                │                                     │  [Add Motions]        │
│                │                                     │  [Export ▼]           │
└────────────────┴─────────────────────────────────────┴───────────────────────┘
   * Step 5 is only present in Head and Supermodel modes.
```

### Step Visibility Per Mode

| Step | Headless | Head | Supermodel | Creature |
|------|----------|------|------------|----------|
| 1 Load Model | ● | ● | ● (body + head) | ● |
| 2 Check Model (T-pose / centre / ground) | ● | ● (front-face) | ● | ● |
| 3 Body Rig | ● | — | ● | ● (Creature skeleton sub-tabs) |
| 4 Hand Rig | ● | — | ● | conditional (`c_gammorean` etc.) |
| 5 Face Rig | — | ● | ● | conditional (`c_rancor` etc.) |
| 6 Check Actor (preview motion) | ● | ● | ● | ● |
| 7 Add Motions / Export | ● | ● | ● | ● |

Creature mode injects two extra sub-tabs into Step 3 for the appendage rigs:
**Tail / Tentacle** and **Wings**.

### M5 Task Breakdown — Phased Plan (32 dev-days total)

#### M5.P0 — Mode-Aware Character Builder Foundation (≈ 8 dev-days)

The current `qt_character_builder_panel.py` (231 lines) is a single 5-tab
panel with placeholder buttons. P0 replaces it with a real four-mode
workspace and wires it to the existing autorig backends.

| Task | File | Hours | Status | Acceptance |
|------|------|-------|--------|-----------|
| T501 | `src/core/character_builder.py` | 8 | PENDING | Add `RigMode` enum (`HEADLESS / HEAD / SUPERMODEL / CREATURE`) + `detect_rig_mode(model)` heuristic (`ModelClassification`, supermodel string, presence of `headhook` and finger bones). Unit-tested against ≥ 12 reference models per mode. |
| T502 | `src/gui/qt_character_builder_panel.py` (rewrite) | 16 | PENDING | Three-pane layout. Sidebar shows mode strip + numbered step buttons (`QToolButton`, exclusive `QButtonGroup`). Right panel = `QStackedWidget` index-linked to active step. |
| T503 | `src/gui/qt_character_builder_window.py` | 4 | PENDING | Convert from façade to real `QMainWindow` with menubar wired to existing actions in `qt_main_window.py`. Persist last-used mode in `QSettings`. |
| T504 | `src/gui/qt_viewport.py` | 12 | PENDING | Dual-view mode (front + back, split horizontally). Reuses existing `set_dual_viewport_mode()` from retarget window. Cameras linked-orbit: yaw mirrored, pitch shared. |
| T505 | `src/gui/qt_viewport_overlay.py` (new) | 8 | PENDING | Joint-dot screen-space overlay (`QPainter.paintEvent`). Cyan = primary chain (limbs), yellow = spine/aux. Per-dot drag, hover-highlight, alt-click reset. Honors opacity/size sliders. |
| T506 | `src/gui/qt_character_builder_panel.py` | 8 | PENDING | Step 3 right-panel widgets: joint-name `QComboBox`, symmetry `QCheckBox`, midpoint `QCheckBox`, whole-mesh/front-part `QRadioButton`, opacity + size sliders, reset-masks button. Each wired to a signal the overlay listens to. |
| T507 | `tests/test_character_builder_modes.py` | 8 | PENDING | Mode-detection golden tests (12+ models per mode); panel build-up smoke tests; overlay click→guide-move signal test. |

**P0 gate:** open the builder, switch through all four modes without
exception, see the correct step set per mode, confirm guide dots draw on
a loaded `pmbc05` and a loaded `c_bantha`.

#### M5.P1 — Body & Hand Rig Pass (≈ 6 dev-days)

Make Step 3 + Step 4 useful for **Headless / Supermodel**. Backend
(`src/autorig/accurig.py`) already has guide-placement, mirror, and
skeleton-build code — P1 wires it to the new UI.

| Task | File | Hours | Status | Acceptance |
|------|------|-------|--------|-----------|
| T511 | `src/autorig/accurig.py` | 8 | PENDING | `auto_place_guides(model, profile)` returning positions from `HUMANOID_GUIDES` × measured bbox height. Finish + cover with tests. |
| T512 | `src/gui/qt_character_builder_panel.py` | 8 | PENDING | Step 3 actions: "Auto-Place Guides", "Mirror Left → Right", "Build Skeleton". Build inserts bones into the live `KotorModel` and refreshes the viewport. |
| T513 | `src/autorig/accurig.py` | 8 | PENDING | **Blocked-weighting workflow** per Jones Ch.5: 100 % per-bone → mirror → remove zero weights → step-smooth at 0/10/25/50/75/90/100. Coroutine reporting % to the status bar. Caps influences at 4 (KOTOR engine limit). |
| T514 | `src/gui/qt_character_builder_panel.py` | 8 | PENDING | Step 4 (Hand Rig): finger-count `QComboBox` (`0, 1, 3, 5`), thumb-direction gizmo toggle, "Copy to Other Hand" button. Camera auto-zooms to hand bbox on entering Step 4. |
| T515 | `src/gui/qt_viewport_overlay.py` | 8 | PENDING | Influence-colour heatmap (blue → red) keyed off the active selected bone. Toggled via View menu. Used to verify weighting in Step 3. |
| T516 | `tests/test_blocked_weighting.py` | 8 | PENDING | Every vertex Σ = 1.0, max 4 influences, mirror symmetry within 1e-4, monotone-smooth invariant (no negative weights mid-blend). |

#### M5.P2 — Face Rig (Head / Supermodel modes, ≈ 5 dev-days)

Implements the facial-rigging-video workflow. Data layer already supports
the slots (`EYES`, `TEETH`, `TONGUE`, `LASHES`) — P2 adds the bone-level
rig.

| Task | File | Hours | Status | Acceptance |
|------|------|-------|--------|-----------|
| T521 | `src/autorig/face_rig.py` (new) | 12 | PENDING | Face-rig profile: `head_root`, `jaw`, `eye_L`, `eye_R`, `tongue`, `teeth_upper` (parented to head), `teeth_lower` (parented to jaw). `jaw` pivot at TMJ-equivalent landmark (slightly forward of ear hook). |
| T522 | `src/gui/qt_character_builder_panel.py` | 8 | PENDING | Step 5 properties panel: jaw-pivot XYZ spinners (constrained to X = 0 unless symmetry off), eye-radius slider, "Snap eyes to mesh sockets" button. |
| T523 | `src/gui/qt_viewport.py` | 4 | PENDING | Ortho preset buttons (Front / 3-Quarter / Side / Top) floating top-right beside the existing FPS HUD. |
| T524 | `src/gui/qt_viseme_panel.py` (new) | 8 | PENDING | Bottom dock for Step 5: viseme/expression sliders (Jaw Open, Smile L, Smile R, Brow Up, Blink L, Blink R). Live-drives the skin in the viewport via the existing GPU skinning path. |
| T525 | `src/gui/qt_viewport_overlay.py` | 4 | PENDING | Centre-line guideline (X = 0 dashed line in front view). Red-warning HUD chip if `jaw.position.x != 0` in symmetric mode. |
| T526 | `tests/test_face_rig.py` | 4 | PENDING | Build a face rig on a known `pfhc01` head; assert bone count, hierarchy, and pivot placement against a golden JSON. |

#### M5.P3 — Creature Rig: Wings · Tails · Tentacles (≈ 9 dev-days)

The Stewart Jones-driven phase. Creature mode adds two appendage sub-systems
on top of the body rig. Existing `src/autorig/cloth_rig.py` (1618 lines) is
the foundation for membrane / cloth dynamics — P3 extends rather than
rewrites.

| Task | File | Hours | Status | Acceptance |
|------|------|-------|--------|-----------|
| T531 | `src/autorig/creature_profiles.py` (new) | 8 | PENDING | Per-species profile presets (`bantha`, `dewback`, `rancor`, `gammorean`, `kath_hound`, `tach`, `wraid`). Each = guide list + appendage flags (`has_tail`, `has_wings`, `has_tentacles`, `has_hands`). |
| T532 | `src/autorig/spline_ik.py` (new) | 12 | PENDING | Custom Spline-IK per Jones Ch.6: chain of `Point` helpers `Path-Constrained` to a polyline, with `LookAt` + `Upnode` constraints to prevent twist flipping. Bake-down to per-bone Euler at export. |
| T533 | `src/autorig/creature_profiles.py` + `accurig.py` | 12 | PENDING | **Tail tab**: pick "Standard Spline-IK" (quick) vs "Custom Spline-IK" (no flip). Joint count slider (3-24). Joints auto-distribute along a user-drawn polyline. |
| T534 | `src/autorig/wing_rig.py` (new) | 16 | PENDING | Wing rig with FLAP / FOLD / LINK three-tier point-helper hierarchy. **Reaction-Manager-equivalent** in Python: a single `fold_amount` 0.0-1.0 attribute drives interpolated rotation of every FOLD locator from open-pose (0) to folded-pose (1). Per-feather/membrane FK array for secondary motion. |
| T535 | `src/autorig/cloth_rig.py` | 8 | PENDING | Extend existing cloth rigger with "wing-membrane" preset: attaches to wing leading-edge bones, applies Jones-style spring/flex damping defaults, supports per-vertex pin-weights. |
| T536 | `src/gui/qt_creature_rig_panel.py` (new) | 12 | PENDING | Step 3 sub-tabs for Creature mode: **Body**, **Tail**, **Wings**, **Tentacles**. Each sub-tab routes to the matching panel. Species combo at the top auto-populates the sub-tabs. |
| T537 | `tests/test_creature_rigs.py` | 4 | PENDING | Golden tests: build bantha (no wings, has tail), rancor (no wings, tentacle-arms, jaw), gammorean (humanoid + tail-stub). Assert bone counts, parent chains, weight totals. |

#### M5.P4 — Validation, Motion Preview & Export Polish (≈ 4 dev-days)

Completes Steps 6 & 7 of the workflow for **all four modes**.

| Task | File | Hours | Status | Acceptance |
|------|------|-------|--------|-----------|
| T541 | `src/gui/qt_character_builder_panel.py` | 8 | PENDING | Step 6 (Check Actor): motion-library list (idle / walk / run / squat / talk / damage). Plays via the existing animation engine. Warning chip if a required bone is missing or weights don't sum to 1.0. |
| T542 | `src/core/rig_validator.py` (new) | 8 | PENDING | Centralised rig-health checks: hierarchy integrity, weight normalisation, zero-weight removal, supermodel-bone-name match. Returns `RigHealthReport` dataclass with severities. |
| T543 | `src/gui/qt_character_builder_panel.py` | 4 | PENDING | Right-panel validation widget shows the `RigHealthReport` as a coloured list (green / amber / red). Click an issue → camera frames the offending bone. |
| T544 | `src/gui/qt_export_dialog.py` (new) | 8 | PENDING | Step 7 export dropdown: KOTOR MDL/MDX (round-trip), KOTOR ASCII MDL, FBX (re-uses M1 pipeline), glTF / GLB (re-uses M7). Mode-aware defaults — Head mode defaults to MDL+TPC bundle. |
| T545 | `docs/character_builder_audit_2026_05.md` (new) | 4 | PENDING | Audit doc per `AGENTS.md`: before/after screenshots of the four modes, golden-report deltas, performance numbers. |

#### M5.P5 — Stretch Goals (≈ 5 dev-days, no fixed order)

| Task | Description | Hours | Status |
|------|------------|-------|--------|
| T551 | Live mirror across X = 0 while a user drags a joint guide (face & body) | 8 | PENDING |
| T552 | Heat-map / geodesic weight initialisation (replacing the inverse-distance fallback in `accurig.py`) | 12 | PENDING |
| T553 | Viseme presets driven by `dialog.tlk` phoneme data → lipsync preview in Step 5 (uses `src/core/lip_reader.py`) | 8 | PENDING |
| T554 | "Reaction Manager" GUI: a node-graph editor wiring a master custom-attribute slider to N slave rotations, per Jones Ch.4 | 8 | PENDING |
| T555 | Asset-library browser side panel (drag-drop heads / bodies onto a Supermodel workspace) | 4 | PENDING |
| T556 | Undo/redo stack for all rig edits (`QUndoStack`) — currently absent | 4 | PENDING |

### Architectural Notes & Conventions

#### Naming convention (adopted from Jones, adapted for KOTOR)

```
CATEGORY_itemNameNumber_SIDE_TYPE
```

| Category | KOTOR mapping |
|----------|---------------|
| `CH`  | character (`pfbc*`, `pmbc*`, `p_hk47`) |
| `CR`  | creature (`c_bantha`, `c_dewback`) |
| `HD`  | head model (`pfhc*`, `pmhc*`) |
| `SM`  | supermodel (`S_Female02`, `S_Male02`, `c_sup_*`) |
| `RIG` | rig-only helpers (guides, IK targets, pole-vectors) |

Side: `L` / `R` / `C` / `UPR` / `LWR`. Type: `JNT` / `CTRL` / `IK` / `GEO` /
`BS` / `MEMB` (membrane). **Internal only** — KOTOR's actual on-disk MDL
bone names stay byte-identical to the originals (the converter only
round-trips existing names); the convention applies to **new** rig helpers
GhostRigger introduces.

#### Engine-export constraints (hard rules — enforced by T542 validator)

1. **Single skeleton hierarchy** — base rig must be one tree. No broken
   hierarchies on export. Animation rigs and IK helpers must bake down.
2. **Max 4 influences per vertex.** Sum-to-1.0. Remove zero weights.
3. **Bone names are stable.** Never rename an existing skinned bone — that
   invalidates the supermodel animation references.
4. **No `ExposeTM`-equivalents on export.** Helper nodes must be `dummy`
   nodes (Aurora-compatible) or be stripped at bake.
5. **`headhook` placement.** Supermodel mode must verify the body's
   `headhook` and the head's root sit at the same world position within
   1e-3 units after bind.

#### Always-preserve guardrails (from `.cursor/rules/project-identity.mdc`)

- Never modify `src/core/creature_appearance.py:snap_head_onto_body`.
- Never reintroduce centroid-magnitude heuristics for vertex-space.
- Never bypass `read_mdl_safe`.
- Never treat skin-node vertices as world-space.
- Quaternion convention stays xyzw.

#### UX rules baked into the layout

- **Numbered left sidebar.** Mirrors AccuRig 1-N step buttons; each button
  is a `QToolButton` with an integer badge. Sequential gating — Step N+1
  enabled only when Step N reports `valid=True`.
- **Right-panel `QStackedWidget`.** Step index ↔ stack index; no duplicate
  property widgets, easy to add new steps.
- **Dual front/back viewport.** Already half-built in `qt_viewport.py`
  (`set_dual_viewport_mode`). T504 finishes the linked-orbit cameras.
- **Joint colour code.** Cyan = primary chain joints (knee, elbow, jaw,
  tail segments). Yellow = secondary / aux (spine, neck, midpoints).
- **Existing FPS overlay (top-right of viewport) stays.** New mode-strip
  HUD chip goes top-left so it doesn't fight the FPS counter.
- **Live mirror is opt-in** (T551). Default is post-edit mirror on a
  button — safer for low-poly KOTOR meshes where snap order matters.

### M5 Critical Path

```
P0 (Mode-aware shell) ──┬──> P1 (Body + Hand) ──┬──> P4 (Validation + Export)
                        │                       │
                        ├──> P2 (Face)  ────────┤
                        │                       │
                        └──> P3 (Creature) ─────┘
                                                │
                                                └──> P5 (Stretch)
```

P0 must land first — every later phase depends on `RigMode` and the new
panel scaffold. P1, P2, P3 can run in parallel after P0 ships. P4 runs
once any two of P1/P2/P3 have shipped.

### Reference Cross-Links

| Topic | Source |
|-------|--------|
| 6-step sidebar workflow | AccuRig video (Load → Check → Body → Hand → Check → Motion) |
| Joint dot colour code, midpoint placement, opacity slider | AccuRig screenshot supplied by user |
| Front/back dual view | AccuRig screenshot — large central panel |
| Hand rig finger-count dropdown | AccuRig video — Step 4 right panel |
| Face wizard sidebar, contextual property panel | Facial rigging tutorial video |
| Jaw pivot at TMJ landmark | Facial rigging tutorial video |
| Influence-lock list, weight-paint heatmap | Facial rigging tutorial video |
| 12 rigging principles (KISS, planning, anatomy, biomech …) | Jones, Ch.1 |
| Naming convention `CATEGORY_itemNameNumber_SIDE_TYPE` | Jones, Ch.2 |
| 3-Stage Asset Build (Base / Animation / Deformation) | Jones, Ch.3 |
| Wing FLAP/FOLD/LINK + Reaction-Manager fold driver | Jones, Ch.4 |
| Spline-IK vs Custom Spline-IK trade-off | Jones, Ch.6 |
| Blocked-weighting → mirror → step-smooth | Jones, Ch.5 |
| COG placement (biped / quadruped / flier / swimmer) | Jones, Ch.3 |
| Cloth modifier for wing membranes | Jones, Ch.7 |
| Real-time engine export constraints (4 influences, single hierarchy) | Jones, Appendix A |

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
**Status**: IN PROGRESS
**Depends on**: M1, M2, M3

| Task | Description | Hours | Status |
|------|------------|-------|--------|
| T801 | Golden-file tests (known-good FBX) | 6 | PENDING |
| T802 | Visual regression (screenshot diff) | 6 | PENDING |
| T803 | Round-trip validation (export -> reimport) | 6 | PENDING |
| T804 | CI pipeline setup | 4 | PENDING |
| T805 | MCP-driven full-model validation | 0 | DONE |

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
| `src/gui/qt_character_builder_panel.py` + new rig modules | ~256 h | MEDIUM | M5 (P0-P5) |
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
