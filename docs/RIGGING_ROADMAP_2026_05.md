# GhostRigger Rigging & Character Builder Roadmap — May 2026

**Branch:** `qt-ghostrigger`
**Status:** Authoritative roadmap for the rigging / character-builder track on the Qt
branch. Supersedes the rigging-related portions of
`.ghostrigger_reference/ROADMAP.md` (M5 Character Builder) and the "AcuRig" line
under §11 of `README.md`. The MDL/MDX/FBX/visual-parity tracks in those documents
remain authoritative for their respective scopes.

**Source references baked into this plan:**

- Stewart Jones — *Digital Creature Rigging: Wings, Tails & Tentacles for
  Animation & VFX* (CRC Press, 2019) — methodology, naming, weighting workflow,
  cloth and spline-IK guidance.
- AccuRig 6-step workflow video — Load Character → Check Model → Body Rig →
  Hand Rig → Check Actor → Add Motions (numbered left-sidebar UX, joint-dot
  guide system, dual front/back view, midpoint placement, joint-opacity/size
  sliders, symmetry, finger count, export to iClone / USD / FBX).
- Facial rigging tutorial video — left wizard sidebar, central head viewport,
  context-sensitive right-hand property panel, ortho front/side presets,
  jaw-pivot precision, neck hierarchy, weight-paint influence lock list,
  viseme/expression scrub.

---

## 1. The Four KOTOR Model Types — What "Rig Mode" Means For Each

KOTOR characters are not a single rig topology. The Character Builder window
must operate in **one of four modes**, selected from a button strip at the top
of the right-hand properties panel (parity with the AccuRig sidebar number
buttons, but as a *mode* selector — the 6-step workflow inside each mode is
different).

| Mode | KOTOR Reality | Source Files | Rig Skeleton | UX Comparable |
|------|--------------|-------------|--------------|---------------|
| **Headless Body** | Body mesh with no head (`pfbc*`, `pmbc*`, `n_darkjedi`, etc.). Skinned to a humanoid skeleton that ends at the `neck` bone. The head plugs in at the `headhook` dummy. | Single MDL/MDX; `supermodel = "S_Male02"` etc. | Humanoid (chest → neck → headhook + arms + legs). No jaw, no eye bones. | **AccuRig body rig** verbatim, but truncated at the neck. |
| **Head** | Standalone head model (`pfhc*`, `pmhc*`, `p_hk47`, etc.). Either rigid (jaw is geometry only) or rigged with jaw / lip bones for talking heads. | Single MDL/MDX; `supermodel = "head"` or NULL. | Head + neck stub + optional jaw, eyes (L/R), tongue, teeth-upper, teeth-lower. | **Facial rigging video** — wizard sidebar + viseme preview. |
| **Supermodel (Combined)** | Body + head assembled together at runtime via `headhook`. Carries the *full* humanoid animation set (the "supermodel"). | Two MDL/MDX pairs assembled in scene; supermodel reference (e.g. `S_Female02.mdl`) supplies animation cycles. | Full hierarchy: humanoid + facial chain glued at `headhook`. | AccuRig + Facial back-to-back (workflow steps appended). |
| **Creature** | Non-humanoid (`c_bantha`, `c_dewback`, `c_rancor`, `c_gammorean`, `c_drdastro`, etc.). Skeleton is bespoke per species. Wings (`c_drexl`?), tails (`c_dewback`), tentacles (`c_rancor` mouth), no fingers in many cases. | Single MDL/MDX; species-specific supermodel chains (`c_sup_*`). | Anatomy-driven, often quadruped + tail/wing/tentacle add-ons. | **Stewart Jones book** — wings/tails/tentacles, custom spline-IK, COG at chest for fliers / center-of-mass for swimmers. |

These four labels are **already represented** in the data layer:

- `src/core/model_data.py::PartSlot` — `HEADLESS_BODY`, `HEAD_SHELL`, etc.
- `src/core/model_data.py::ModelClassification` — `CHARACTER = 4`, `FLYER = 64`.
- `src/autorig/accurig.py::PROFILE_HUMANOID / QUADRUPED / DROID / CREATURE`.

What is **missing** is a single source of truth that *combines* the part-slot
data with the rig-profile data into a "rig mode" selector that the Character
Builder window can switch on. This is the first piece of work below (P0-A).

---

## 2. Top-Level Information Architecture

### 2.1 Character Builder Window — Final Layout

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

### 2.2 Step Visibility Per Mode

| Step | Headless | Head | Supermodel | Creature |
|------|----------|------|------------|----------|
| 1 Load Model | ● | ● | ● (loads body + head) | ● |
| 2 Check Model (T-pose / center / ground) | ● | ● (front-face) | ● | ● |
| 3 Body Rig | ● | — | ● | ● (Creature skeleton sub-tabs) |
| 4 Hand Rig | ● | — | ● | conditional (creature with hands, e.g. `c_gammorean`) |
| 5 Face Rig | — | ● | ● | conditional (creatures with jaw, e.g. `c_rancor`) |
| 6 Check Actor (preview motion) | ● | ● | ● | ● |
| 7 Add Motions / Export | ● | ● | ● | ● |

Creature mode injects two extra sub-tabs into Step 3 for the appendage rigs
(see §4): **Tail / Tentacle** and **Wings**.

---

## 3. Roadmap — Concrete Milestones

Effort is in dev-days. Priority: **P0 = ship next**, **P1 = follow-up**,
**P2 = stretch**. All work lands on `qt-ghostrigger`; nothing touches `main`.
Audit-first rule from `AGENTS.md` continues to apply: every fix to skin /
render math ships a `scripts/dump_*.py` and a `docs/*_audit_*.md`.

### P0 — Mode-Aware Character Builder Foundation  (≈ 8 dev-days)

The current `qt_character_builder_panel.py` (231 lines) is a single 5-tab
panel with placeholder buttons — no mode awareness. Phase P0 replaces it with
a real four-mode workspace and wires it to the existing autorig backends.

| Task | File | Effort | Acceptance |
|------|------|--------|-----------|
| **P0-A** | `src/core/character_builder.py` | 1d | Add `RigMode` enum (`HEADLESS / HEAD / SUPERMODEL / CREATURE`) + `detect_rig_mode(model)` heuristic (uses `ModelClassification`, supermodel string, presence of `headhook` and finger bones). Unit-tested against ≥ 12 reference models per mode pulled from the MCP scan. |
| **P0-B** | `src/gui/qt_character_builder_panel.py` (replace) | 2d | Three-pane layout (sidebar / viewport / properties). Sidebar shows mode strip + numbered step buttons (`QToolButton`, exclusive `QButtonGroup`). Right panel is a `QStackedWidget` index-linked to the active step. |
| **P0-C** | `src/gui/qt_character_builder_window.py` | 0.5d | Convert from façade to a real `QMainWindow` housing the new panel, with menubar (File / Edit / View / Tools / Rigging) wired to the actions already in `qt_main_window.py`. Persist last-used mode in `QSettings`. |
| **P0-D** | `src/gui/qt_viewport.py` | 1.5d | Add **dual-view mode** (front + back, split horizontally). Reuses the existing `set_dual_viewport_mode()` plumbing from the retarget window. Cameras are linked-orbit: yaw mirrored, pitch shared. |
| **P0-E** | `src/gui/qt_viewport_overlay.py` (new) | 1d | Joint-dot screen-space overlay (`QPainter.paintEvent` on top of the GL widget). Cyan dots = primary chain (limbs), yellow = spine/aux. Per-dot drag, hover-highlight, alt-click-to-reset. Honors `joint_opacity` / `joint_size` sliders. |
| **P0-F** | `src/gui/qt_character_builder_panel.py` | 1d | Step 3 (Body Rig) right-panel widgets: joint-name `QComboBox`, symmetry `QCheckBox`, midpoint-placement `QCheckBox`, whole-mesh/front-part `QRadioButton`, opacity slider, size slider, reset-masks `QPushButton`. Wire each to a signal the overlay listens to. |
| **P0-G** | `tests/test_character_builder_modes.py` | 1d | Mode-detection golden tests (12+ models per mode); panel build-up smoke tests; overlay click→guide-move signal test. |

**Acceptance gate P0:** open the builder, switch through all four modes
without exception, see the correct step set per mode (per §2.2 table),
confirm guide dots draw on a loaded `pmbc05` and a loaded `c_bantha`.

### P1 — Body & Hand Rig Pass  (≈ 6 dev-days)

Make Step 3 + Step 4 do useful work for **Headless / Supermodel** modes. The
backend (`src/autorig/accurig.py`) already has guide-placement, mirror, and
skeleton-build code — Phase P1 wires it to the new UI.

| Task | File | Effort | Acceptance |
|------|------|--------|-----------|
| **P1-A** | `src/autorig/accurig.py` | 1d | Add `auto_place_guides(model, profile)` that returns positions using the existing `HUMANOID_GUIDES` normalised coordinates × measured model bbox height. Already partially present — finish + cover with tests. |
| **P1-B** | `src/gui/qt_character_builder_panel.py` | 1d | Step 3 actions: "Auto-Place Guides", "Mirror Left → Right", "Build Skeleton". Wire to `accurig.py`. Build inserts bones into the live `KotorModel` and refreshes the viewport. |
| **P1-C** | `src/autorig/accurig.py` | 1d | **Blocked-weighting workflow** per Jones Ch.5: 100% per-bone → mirror → remove zero weights → step-smooth at 0/10/25/50/75/90/100. Implemented as a coroutine reporting % progress to the status bar. Caps influences at 4 (KOTOR engine limit). |
| **P1-D** | `src/gui/qt_character_builder_panel.py` | 1d | Step 4 (Hand Rig): finger-count `QComboBox` (`0, 1, 3, 5`), thumb-direction gizmo toggle, "Copy to Other Hand" button. Camera auto-zooms to hand bbox when entering Step 4. |
| **P1-E** | `src/gui/qt_viewport_overlay.py` | 1d | Add **influence-colour heatmap** mode (blue → red) keyed off the active selected bone. Toggled via View menu. Used to verify weighting in Step 3. |
| **P1-F** | `tests/test_blocked_weighting.py` | 1d | Verify weighting pipeline: every vertex sum-to-1.0, max 4 influences, mirror symmetry within 1e-4, monotone-smooth invariant (no negative weights mid-blend). |

### P2 — Face Rig (Head / Supermodel modes)  (≈ 5 dev-days)

Implements the facial-rigging video workflow. The data layer already supports
the slots (`EYES`, `TEETH`, `TONGUE`, `LASHES`) — Phase P2 adds the bone-level
rig.

| Task | File | Effort | Acceptance |
|------|------|--------|-----------|
| **P2-A** | `src/autorig/face_rig.py` (new) | 1.5d | Face-rig profile: `head_root`, `jaw`, `eye_L`, `eye_R`, `tongue`, `teeth_upper` (parented to head), `teeth_lower` (parented to jaw). Pivot for `jaw` at the TMJ-equivalent landmark (slightly forward of the ear hook). |
| **P2-B** | `src/gui/qt_character_builder_panel.py` | 1d | Step 5 properties panel: jaw-pivot XYZ spinners (constrained to X = 0 unless symmetry off), eye-radius slider, "Snap eyes to mesh sockets" button. |
| **P2-C** | `src/gui/qt_viewport.py` | 0.5d | Ortho preset buttons (Front / 3-Quarter / Side / Top) floating in the viewport top-right next to the existing FPS HUD. |
| **P2-D** | `src/gui/qt_viseme_panel.py` (new) | 1d | Bottom dock for Step 5: viseme/expression sliders (Jaw Open, Smile L, Smile R, Brow Up, Blink L, Blink R). Live-drives the skin in the viewport via the existing GPU skinning path. |
| **P2-E** | `src/gui/qt_viewport_overlay.py` | 0.5d | Centre-line guideline (X = 0 dashed line in front view) so the user can verify symmetry. Red-warning HUD chip if `jaw.position.x != 0` in symmetric mode. |
| **P2-F** | `tests/test_face_rig.py` | 0.5d | Build a face rig on a known `pfhc01` head, assert correct bone count, hierarchy, and pivot placement against a golden JSON. |

### P3 — Creature Rig (Wings · Tails · Tentacles)  (≈ 9 dev-days)

This is the Stewart Jones-driven phase. Creature mode adds two appendage
sub-systems on top of the body rig. The existing `src/autorig/cloth_rig.py`
(1618 lines!) is the foundation for membrane / cloth dynamics — Phase P3
extends rather than rewrites.

| Task | File | Effort | Acceptance |
|------|------|--------|-----------|
| **P3-A** | `src/autorig/creature_profiles.py` (new) | 1d | Per-species profile presets (`bantha`, `dewback`, `rancor`, `gammorean`, `kath_hound`, `tach`, `wraid`). Each profile = guide list + which appendages are present (`has_tail`, `has_wings`, `has_tentacles`, `has_hands`). |
| **P3-B** | `src/autorig/spline_ik.py` (new) | 1.5d | Custom Spline-IK per Jones Ch.6: chain of `Point` helpers `Path-Constrained` to a polyline, with `LookAt` + `Upnode` constraints to prevent twist flipping. Bake-down to per-bone Euler at export. |
| **P3-C** | `src/autorig/creature_profiles.py` + `accurig.py` | 1.5d | **Tail tab**: pick "Standard Spline-IK" (quick) vs "Custom Spline-IK" (no flip). Joint count slider (3–24). Joints auto-distribute along a user-drawn polyline. |
| **P3-D** | `src/autorig/wing_rig.py` (new) | 2d | Wing rig with the FLAP / FOLD / LINK three-tier point-helper hierarchy. **Reaction-Manager-equivalent** in Python: a single `fold_amount` 0.0-1.0 attribute drives interpolated rotation of every FOLD locator from open-pose at 0 to folded-pose at 1. Add per-feather/membrane FK array for secondary motion. |
| **P3-E** | `src/autorig/cloth_rig.py` | 1d | Extend the existing cloth rigger with a "wing-membrane" preset: attaches to the wing's leading-edge bones, applies Jones-style spring/flex damping defaults, supports per-vertex pin-weights. |
| **P3-F** | `src/gui/qt_creature_rig_panel.py` (new) | 1.5d | Step 3 sub-tabs for Creature mode: **Body**, **Tail**, **Wings**, **Tentacles**. Each sub-tab routes to the matching panel. Species profile combo at the top auto-populates the sub-tabs. |
| **P3-G** | `tests/test_creature_rigs.py` | 0.5d | Golden tests: build bantha (no wings, has tail), rancor (no wings, tentacle-arms, jaw), gammorean (humanoid + tail-stub). Assert bone counts, parent chains, and weight totals. |

### P4 — Validation, Motion Preview & Export Polish  (≈ 4 dev-days)

Completes Steps 6 & 7 of the workflow for **all four modes**.

| Task | File | Effort | Acceptance |
|------|------|--------|-----------|
| **P4-A** | `src/gui/qt_character_builder_panel.py` | 1d | Step 6 (Check Actor): motion-library list (idle / walk / run / squat / talk / damage). Plays via the existing animation engine. Warning chip if a required bone is missing or weights don't sum to 1.0. |
| **P4-B** | `src/core/rig_validator.py` (new) | 1d | Centralised rig-health checks: hierarchy integrity, weight normalisation (Σ = 1.0, max 4), zero-weight removal, supermodel-bone-name match. Returns a `RigHealthReport` dataclass with severities. |
| **P4-C** | `src/gui/qt_character_builder_panel.py` | 0.5d | Right-panel validation widget showing the `RigHealthReport` as a coloured list (green / amber / red). Click an issue → camera frames the offending bone in the viewport. |
| **P4-D** | `src/gui/qt_export_dialog.py` (new) | 1d | Step 7 export dropdown: KOTOR MDL/MDX (round-trip), KOTOR ASCII MDL, FBX (re-uses M1 pipeline), glTF / GLB (re-uses M7). Mode-aware defaults — e.g. Head mode defaults to MDL+TPC bundle. |
| **P4-E** | `docs/character_builder_audit_2026_05.md` (new) | 0.5d | Audit document per `AGENTS.md`: before/after screenshots of the four modes, golden-report deltas, performance numbers. |

### P5 — Stretch Goals  (≈ 5 dev-days, no fixed order)

- **P5-A** Live mirror across X = 0 while a user drags a joint guide (face & body).
- **P5-B** Heat-map / geodesic weight initialisation (replacing the current
  inverse-distance fallback in `accurig.py`).
- **P5-C** Viseme presets driven by `dialog.tlk` phoneme data → lipsync preview
  inside Step 5 (uses `src/core/lip_reader.py`).
- **P5-D** "Reaction Manager" GUI: a node-graph editor wiring a master
  custom-attribute slider to N slave rotations, per Jones Ch.4.
- **P5-E** Asset-library browser side panel (drag-drop heads / bodies onto a
  Supermodel mode workspace).
- **P5-F** Undo/redo stack for all rig edits (`QUndoStack`) — currently absent.

---

## 4. Architectural Notes & Conventions

### 4.1 Naming convention (adopted from Jones, adapted for KOTOR)

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
`BS` / `MEMB` (membrane). Internal-only — KOTOR's actual on-disk MDL bone
names stay byte-identical to the originals (the converter only round-trips
existing names); the convention applies to **new** rig helpers GhostRigger
introduces.

### 4.2 Engine-export constraints (hard rules)

These come from both KOTOR's Aurora engine and Jones's real-time-engine
chapter. They are enforced by `rig_validator.py` (P4-B):

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

### 4.3 The "always preserve" guardrails

Lifted unchanged from `README.md` §12 (`.cursor/rules/project-identity.mdc`):

- Never modify `src/core/creature_appearance.py:snap_head_onto_body`.
- Never reintroduce centroid-magnitude heuristics for vertex-space.
- Never bypass `read_mdl_safe`.
- Never treat skin-node vertices as world-space.
- Quaternion convention stays xyzw.

### 4.4 UX rules baked into the layout

- **Numbered left sidebar.** Mirrors AccuRig 1-N step buttons; each button
  is a `QToolButton` with an integer badge in the icon. Sequential gating
  — Step N+1 enabled only when Step N reports `valid=True`.
- **Right-panel `QStackedWidget`.** Step index ↔ stack index; no duplicate
  property widgets, easy to add new steps.
- **Dual front/back viewport.** Already half-built in `qt_viewport.py`
  (`set_dual_viewport_mode`). P0-D finishes the linked-orbit cameras.
- **Joint colour code.** Cyan = primary chain joints (knee, elbow, jaw,
  tail segments). Yellow = secondary / aux (spine, neck, midpoints).
- **Existing FPS overlay (top-right of viewport) stays.** New mode-strip
  HUD chip goes top-left so it doesn't fight the FPS counter.
- **Live mirror is opt-in** (P5-A). Default is post-edit mirror on a
  button — safer for low-poly KOTOR meshes where snap order matters.

---

## 5. Critical Path

```
P0 (Mode-aware shell) ──┬──> P1 (Body + Hand) ──┬──> P4 (Validation + Export)
                        │                       │
                        ├──> P2 (Face)  ────────┤
                        │                       │
                        └──> P3 (Creature) ─────┘
                                                │
                                                └──> P5 (Stretch)
```

P0 must land first — every later phase depends on the `RigMode` enum and the
new panel scaffold. P1, P2, P3 can run in parallel after P0 is on `main` of
the qt branch. P4 runs once any two of P1 / P2 / P3 have shipped (so there
is something for the validator to validate).

**Estimated total to "Done for all four modes":** 32 dev-days
(P0 8 + P1 6 + P2 5 + P3 9 + P4 4). P5 is open-ended.

---

## 6. Reference Cross-Links

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
| COG placement (biped/quadruped/flier/swimmer) | Jones, Ch.3 |
| Cloth modifier for wing membranes | Jones, Ch.7 |
| Real-time engine export constraints (4 influences, single hierarchy) | Jones, Appendix A |

---

## 7. What This Roadmap Does **Not** Change

- The MDL / MDX / FBX export work already on `qt-ghostrigger`
  (`src/converters/mesh_converter.py`) — that track stays as scoped in
  `.ghostrigger_reference/ROADMAP.md` M1.
- The GPU renderer migration — that track stays as scoped in M3 / M4.
- The MCP-driven validation pipeline — stays as the regression backbone for
  every Phase below.
- The existing AccuRig backend (`src/autorig/accurig.py`) — extended, never
  rewritten. The existing Animation Retarget Workbench
  (`src/gui/qt_retarget_window.py`) — untouched; we *reuse* its dual-viewport
  pattern in P0-D.
- The cloth rigger (`src/autorig/cloth_rig.py`) — extended in P3-E with the
  wing-membrane preset, never rewritten.

---

*This roadmap supersedes M5 of `.ghostrigger_reference/ROADMAP.md` and §11
"AcuRig" bullet of `README.md`. Once P0 ships, update both upstream docs to
point here as the active source of truth for the rigging track.*
