# Qt Branch Audit — `qt-ghostrigger` @ `bd787f3+`

**Date:** 2026-05-15
**Branch:** `qt-ghostrigger` (head: `3448116` — post sync from LordVaderCW fork)
**Audited against:** Reallusion AccuRig demo, facial rig tutorial (`pLRxzsPAqrE`),
Stewart Jones *Digital Creature Rigging: Wings, Tails & Tentacles* (2019, CRC Press),
and the existing `.ghostrigger_reference/docs/character_builder_spec.md`.

---

## 1. UI Framework Status — Qt vs Tkinter

### 1.1 Verdict: **Hybrid. Qt is the default startup path, but Tk is still installed and still wired into legacy modules.**

`main.py:240-256` picks the GUI mode:

```python
if gui_mode in ("auto", "qt"):
    try:
        from src.gui.qt_main_window import run as _run_qt
        rc = _run_qt(_APP_DIR, startup_input=vars(args))
        ...
    except Exception:
        ...
        log.warning("Qt shell unavailable; falling back to Tkinter.")
        _install_exception_hooks(logfile, install_tk_hook=True)

# Tk fallback always reachable
from src.gui.main_window import run as _run_gui, KotorModToolsApp
```

So `auto` and `qt` go to Qt first; only if Qt fails to import does the launcher fall through to the 12,313-line legacy `main_window.py`. On any modern dev box this is effectively a Qt-only build, but the Tk codepath is still **compiled-in** and **referenced** by Qt-side modules.

### 1.2 Tk import audit

Hits remaining in `src/`:

| File | Lines | Status | Action needed |
|------|-------|--------|---------------|
| `src/gui/main_window.py` | 12,313 | Legacy Tk monolith — still imported as fallback | **Freeze**, do not extend |
| `src/gui/character_builder_window.py` | 3,532 | Legacy Tk Character Builder | **Deprecate** — replace with Qt window |
| `src/gui/viewport.py` | (Tk + shared) | Owns `FrameRenderer` + `ArcBallCamera` — **still imported by `qt_viewport.py`** | **Refactor:** split renderer/camera out of Tk file |
| `src/gui/blueprint_editor.py` | Tk | Used only by Tk path | **Freeze** |
| `src/gui/modular_panel.py` | Tk | Used only by Tk path | **Freeze** |
| `src/gui/matrix_background.py` | Tk | Replaced by `qt_matrix_background.py` | **Freeze** |
| `src/gui/icon_manager.py` | Tk | Replaced by `qt_icon_manager.py` | **Freeze** |
| `src/autorig/cloth_rig.py:788-1216` | Tk (3 sites) | **Bug:** Tk popups inside a service module | **Fix:** swap for Qt dialogs or pure-API result objects |
| `src/ipc/client.py:99`, `src/ipc/server.py:341` | Tk `_default_root.after()` | Marshals IPC callbacks back onto Tk main-thread | **Fix:** use `QtCore.QTimer.singleShot(0, ...)` or `QMetaObject.invokeMethod` instead |

**Critical defect:** `qt_viewport.py:15` imports `ArcBallCamera` and `FrameRenderer` from `src/gui/viewport.py`, which itself imports `tkinter` at module load. Right now the Tk module-level imports succeed silently because Tk is present, but this creates a brittle coupling and a real risk that headless / packaged builds break.

### 1.3 Recommendation

Treat the Qt shell as the **only supported front-end** going forward. The Tk fallback should be:

1. Demoted from `auto` → `qt-only` (Tk only via explicit `--gui=tk`).
2. Extracted-not-deleted: keep `main_window.py` / `character_builder_window.py` as read-only references for one more milestone, then remove.
3. `viewport.py` must be split into:
   - `src/gui/viewport_core.py` (`FrameRenderer`, `ArcBallCamera`, `_BASE_SKELETONS`) — **no GUI imports**.
   - `src/gui/viewport_tk.py` (the Tk widget) — kept only if Tk path stays.

---

## 2. Qt Module Map

### 2.1 Top-level shell (`qt_main_window.py`, 3,281 lines)

Imports the following Qt panels (all clean, no Tk):

```
qt_library_panel        ← Library tab (autodetect, scan, load, retarget)
qt_log_panel
qt_matrix_background    ← Matrix-style background animation
qt_properties_panel     ← Properties + Skeleton inspectors
qt_viewport             ← Main 3D viewport widget (depends on Tk-tainted viewport.py)
qt_animation_panel      ← Animation library + retarget panel
qt_blueprint_editor
qt_character_builder_panel  ← Stub embedded Builder panel + Builder window
qt_diagnostics_panel
qt_dialogs              ← About / format ref / IPC info / nav ref
qt_modular_panel        ← Modular (module / area) editor
qt_normal_map_panel
qt_resource_panel       ← Resource browser + 2DA browser
qt_retarget_window      ← Standalone Animation Retarget Workbench
qt_rig_panel            ← Auto / Library / GRig / Manual / AcuRig tabs
qt_settings_dialog
qt_texture_panel
```

### 2.2 Character Builder — current implementation

| File | LOC | Role | Maturity |
|------|-----|------|----------|
| `qt_character_builder_window.py` | 13 | Re-export shim | — |
| `qt_character_builder_panel.py` | 231 | `QtCharacterBuilderPanel` (embedded) + `QtCharacterBuilderWindow` (popout) | **Stub: 5 tabs of placeholder buttons** |
| `src/core/character_builder.py` | 940 | Backend: template load, headhook discovery, facial validation, `LIPPlayback`, `SkeletonSelector`, `apply_template_rig`, `export_character_b1` | Working |
| `src/core/validation_service.py` | 443 | 10 issue codes (HOOK_MISSING, HOOK_MISALIGNED, WEIGHT_UNNORMALIZED, etc.) | Working |
| `src/core/creature_appearance.py` | 2,161 | UTC → appearance.2da → body+head model resolution | Working |
| `src/core/model_data.py` (PartSlot, CharacterScene) | — | Canonical scene model with 11 PartSlots | Working |

**Gap:** the Qt window today is essentially five tabs of buttons (Assembly / Selection / Transform / Rig / Export) with no viewport, no asset browser, no symmetry tools, no validation HUD, no model-type awareness. The spec in `.ghostrigger_reference/docs/character_builder_spec.md` is the source of truth for what it *should* be — we just haven't built it.

### 2.3 Retarget workbench (already shipped)

`qt_retarget_window.py:507` is the new high-water mark for what a Qt workspace looks like in this codebase: dual viewports, paced rendering, FPS overlays, tool menus (Cloth Rigging). The Character Builder should be built to match that quality bar.

### 2.4 Rigging backends — already in place

| Module | LOC | Purpose |
|--------|-----|---------|
| `src/autorig/auto_rigger.py` | 904 | Procedural heat-map weighting, profile autodetect |
| `src/autorig/accurig.py` | 1,119 | AccuRig-style guide pins (humanoid/quadruped/droid/prop/**creature**) + weight transfer |
| `src/autorig/grig.py` | 1,099 | Manual rig: symmetry, bone-pin placement, weight brushes |
| `src/autorig/cloth_rig.py` | 1,618 | Dangly-mesh cloth (K1 ↔ K2 port) — **has Tk leaks** |
| `src/autorig/retarget_engine.py` | 1,449 | Scale-fit + rig transfer + anim retarget (state machine) |
| `src/core/animation_retargeting/retargeter.py` | 240 | New scale-preserving retargeter (LordVaderCW commit) |

**All five profile types already exist in `accurig.py`**: `humanoid`, `quadruped`, `droid`, `prop`, `creature`. The plumbing is there; we just need to surface them.

---

## 3. KOTOR Model-Type Taxonomy (drives the four Builder modes)

This is the missing piece in the current UI. KOTOR has four distinct character-asset shapes, and each needs its own assembly + rig + validation workflow. Mapping:

| # | Mode label | KOTOR asset class | Example resrefs | What's loaded | Required hooks | Required bones | Default rig path |
|---|------------|-------------------|-----------------|---------------|----------------|----------------|------------------|
| **1** | **Headless Body** | Body without head; head will be attached separately at runtime via `appearance.2da` | `pfbcm`, `pfbam`, `pmbam`, `n_darkjedi`, `n_sithsolda` | One body MDL + MDX | `headhook`, `rhand`, optional: `lhand_g`, `camerahook`, `chestconjure`, `handconjure`, `impact_bolt` | full pelvis→spine→limbs chain, **no** face bones | AcuRig **humanoid** profile, supermodel = `S_Male/Female 02/03` |
| **2** | **Head** | Standalone head model for facial rigging + LIP | `pmhc01`, `pfhc01`, `p_hk47head`, `phead*` | Head MDL + MDX | `headhook` (placement reference back to body), `talkdummy`, optional: `MaskHook`, `GoggleHook`, `camerahook`, `cutscenedummy` | `head_g`, `necklwr_g`, `neck_g`, `f_jaw_g`, `f_um_g`, `f_lmc_g`, `f_rmc_g`, eyes, lashes, teeth, tongue | Facial bone template + LIP `talk` animation binding |
| **3** | **Supermodel (Head + Headless combined)** | A preview-time composite: headless body **plus** an attached head, snapped at `headhook`. Used to authoring K1/K2 PC/NPC variants. *Not* a single shipped MDL — it's an in-tool assembly. | `S_Male02` + `pmhc01` | Two MDLs co-loaded; head snaps onto body's `headhook` world transform | Body hooks **AND** head hooks (intersection enforced) | Body skeleton + Head facial bones; supermodel string on body must match game | Composite rig: body uses humanoid template, head retains facial template; validation runs both rule sets |
| **4** | **Creature** | Standalone non-humanoid model: head, body, animations all in one MDL; supermodel is itself (or `NULL`) | `c_bantha`, `c_rancor`, `c_dewback`, `c_ithorian`, `c_kinrath`, `c_jawa`, `c_drdastro` | One MDL + MDX | None of the headhook/talkdummy set; uses creature-specific hooks (`impact_*`, `cameramaster`) | Whatever the creature defines — quadruped, multi-leg, tentacled, winged, droid; **no** facial-bone requirement | AcuRig **creature / quadruped / droid / prop** profile, supermodel typically `NULL` or `c_<base>` |

### 3.1 Detection rules (auto-pick mode on Load)

```python
def detect_model_type(model: KotorModel) -> CharacterMode:
    name = (model.name or "").lower()
    nodes = {n.name.lower() for n in model.iter_nodes()}
    classification = model.model_type        # ModelClassification enum
    supermodel = (model.supermodel or "").upper()

    # 1. Anything not classified as CHARACTER / FLYER → reject (placeable, door, etc.)
    if classification not in (ModelClassification.CHARACTER,
                              ModelClassification.FLYER):
        return CharacterMode.UNSUPPORTED

    # 2. Creature: c_* prefix OR creature-only hooks OR non-humanoid topology
    if name.startswith("c_") or name.startswith("n_") and supermodel in _KOTOR_BASE_SKELETONS:
        return CharacterMode.CREATURE

    # 3. Head: has talkdummy or head_g + f_jaw_g
    if "talkdummy" in nodes or ("head_g" in nodes and "f_jaw_g" in nodes
                                and "pelvis_g" not in nodes):
        return CharacterMode.HEAD

    # 4. Headless body: has headhook + rhand but no facial bones
    if "headhook" in nodes and "rhand" in nodes and "f_jaw_g" not in nodes:
        return CharacterMode.HEADLESS_BODY

    # 5. Default: ambiguous / older PC base — let user pick
    return CharacterMode.AMBIGUOUS
```

**Mode switcher in the toolbar:** four buttons (Headless / Head / Supermodel / Creature) that the user can override at any time. Default is the auto-detection.

---

## 4. Visual / HUD design — derived from AccuRig + the facial-rig tutorial

The user has stated the screen layout should match the AccuRig HUD example (the supplied screenshot), implemented in our existing green-on-black GhostRigger theme (`qt_theme.C` accent `#00FF7A`).

### 4.1 Master layout (5 regions)

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ TOP TOOLBAR    [Mode: Headless | Head | Supermodel | Creature]  [Game: K1|K2]  │ 5%
│                [Front][Back][L][R][T][B][Persp][Ortho]  [Sym][Snap][Validate] │
├──────────────┬────────────────────────────────────────────────┬────────────────┤
│ LEFT RAIL    │ CENTER VIEWPORT                                │ RIGHT INSPECTOR│
│ (numbered    │  Dual front+back orthographic (Body modes)     │                │
│ workflow,    │  Single perspective with close-up (Head mode)  │  Joint Name    │ 
│ ~15%)        │  Top-right MINI THUMBNAIL of full character     │  Symmetry [✓]  │
│              │  FPS overlay (already in qt_viewport.py)        │  Mask [ ]      │ 70%
│  1 Load      │  Joint dots: yellow=center, cyan=side,         │  Reset Masks   │
│  2 Check     │              red=L, green=R                     │  Midpoint Plc  │
│  3 Body Rig  │  Click-drag to move, mirror-aware, snap-to-mesh│  Whole / Front │
│  4 Hand Rig  │                                                │  Joint Opacity │
│  5 Face Rig  │                                                │  Joint Size    │
│  6 Check     │                                                │  ──────────────│
│  7 Motions   │                                                │  Add Motions   │
│  8 Export    │                                                │  Export        │
├──────────────┴────────────────────────────────────────────────┴────────────────┤
│ BOTTOM STRIP: Validation banner ⚠ • Animation scrubber • Export log • Stats   │ 10%
└────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Left-rail step list per mode

The left rail is **mode-aware**. Step numbering stays consistent but the visible steps change.

| Step | Headless Body | Head | Supermodel | Creature |
|------|---------------|------|------------|----------|
| 1 | Load Body | Load Head | Load Body + Load Head | Load Creature |
| 2 | Check Model (T-pose, scale) | Check Model | Check both, fit at `headhook` | Check Model |
| 3 | Body Rig (humanoid pins) | Head Rig (head/neck/jaw) | Body Rig | Profile Pick (humanoid / quadruped / droid / prop / wings / tentacles) |
| 4 | Hand Rig (fingers) | Face Rig (lids, lip corners) | Hand Rig | Limb Rig (per profile) |
| 5 | — | LIP & Phoneme Test | Face Rig | Special: Tail / Wing / Tentacle Spline-IK |
| 6 | Check Actor (idle/walk/talk) | Check Face (jaw/blink/visemes) | Check Actor + Face | ROM Test (Stewart Jones range-of-motion) |
| 7 | Add Motions (anim library) | — | Add Motions | Add Motions |
| 8 | Validate + Export | Validate + Export | Validate + Export | Validate + Export |

### 4.3 Right inspector — contextual content per step (AccuRig parity)

Direct ports from the AccuRig HUD reference, re-skinned to KOTOR semantics:

| AccuRig control | GhostRigger equivalent | Backing module |
|-----------------|------------------------|----------------|
| Joint Name dropdown | `QComboBox` populated from the active skeleton's bone list | `accurig.py:RigGuide` |
| Symmetry toggle | `QCheckBox`, drives `grig.SymmetryEngine` | `grig.py` |
| Mask + Reset All Masks | Per-region bone-influence mask | `accurig.bone_masks` |
| Midpoint Placement | Push pin to volume centroid | `accurig.midpoint_placement` |
| Whole Mesh / Front Part | Limit mesh probe to forward hemisphere (Stewart Jones blocking trick) | new helper in `grig.py` |
| Joint Opacity slider | Bone overlay alpha in viewport | `qt_viewport.py` overlay layer |
| Joint Size slider | Bone marker radius | `qt_viewport.py` |
| Add Motions | Open Animation Library (existing `qt_animation_panel`) | wired |
| Export | Open Export panel (KOTOR / FBX / glTF / OBJ) | `mesh_converter.py` |

### 4.4 Center viewport — extensions over current `qt_viewport.py`

The viewport already has:
- FPS / render-time overlay (top-right, from `bd787f3`)
- Dual-mode paced rendering (from retarget workbench)
- Live animation preview using GPU fast-path

We need to add:
- **Front+Back ortho split** (already 50% there via retarget dual-mode — generalize it)
- **Joint dot HUD layer**: colored 2D-projected markers over 3D mesh, mouse-interactive
- **Mini-thumbnail inset** (top-right corner) showing full-character silhouette at neutral pose so a closeup edit still shows global context
- **Snap-view buttons** as a floating cluster at top-center (Front/Back/L/R/T/B)
- **Heat-map skin-weight overlay** (blue→red gradient on selected bone)

---

## 5. Stewart Jones — what we adopt from *Digital Creature Rigging*

The book is 3ds-Max-specific, but the principles map cleanly. Highest-value takeaways for the Creature mode:

1. **3-Stage Asset Build (3SAB):** Base Rig → Animation Rig → Deformation Rig. Map directly to our Creature mode steps:
   - **Base Rig** = AcuRig guide placement + skeleton generation (existing)
   - **Animation Rig** = controller layer (NEW; not present in GhostRigger today)
   - **Deformation Rig** = cloth, dangly, twist (cloth exists; twist + per-shot deformers new)

2. **Naming convention:** `CATEGORY_itemNameNumber_SIDE_TYPE` (e.g. `CH_bantha_limb003_L_JNT`). KOTOR's native names override this in-engine, but the in-tool canonical scene graph should track both: a stable internal ID **and** the KOTOR-engine export name.

3. **Skinning workflow (verbatim adopt):**
   1. Erase auto-weights
   2. 100% blocked weights per bone
   3. Smooth with 0/10/25/50/75/90/100% falloff steps
   4. Mirror across X with adjustable threshold
   5. Cap influences at 4 (KOTOR engine limit — already enforced in `accurig.py:MAX_INFLUENCES`)
   6. Run a ROM (Range-of-Motion) test animation

4. **Spline IK for tails / tentacles / spines:** Place a Line/spline along the chain, drop a Spline IK solver, expose helpers at each CV, add LookAt constraints for twist. **Action:** add a `tail_rig.py` / `spline_ik.py` module mirroring `cloth_rig.py`'s shape but driving rotation chains.

5. **Wing rig:** two-bone arm chain (shoulder → elbow → wrist) **plus** secondary two-bone chains for each membrane spine and claw. Layered control: `FLAP_LOC` (waveform automation) → `FOLD_LOC` (reaction-manager) → `LINK_LOC` (buffer) → `CTRL` (manual FK override). **Action:** add `wing_rig.py` with the four-layer control structure.

6. **ROM (Range-of-Motion) test files:** A linear animation that hits every extreme pose. **Action:** auto-generate a ROM clip per profile in `accurig.py` so step 6 ("Check Actor / ROM Test") is one click.

7. **Color-coded controls:** center=yellow, L=red, R=green, additional core=blue, extras=white/purple. Already half-aligned with our `qt_theme` accents. Apply consistently to bone dots and gizmos.

8. **Blendshapes / Morphs for face:** Use only where KOTOR allows. KOTOR drives faces via the `talk` animation + LIP files (bone-based), so the Builder's Face mode stays bone-first. Reserve morphs for **out-of-engine** FBX/glTF exports where modern pipelines (Unreal, Blender) expect blendshapes.

---

## 6. Pain points & gaps confirmed by audit

| # | Issue | Severity | Where |
|---|-------|----------|-------|
| 1 | Qt Character Builder is a stub — zero viewport, zero asset browser | HIGH | `qt_character_builder_panel.py` |
| 2 | No `CharacterMode` enum / no model-type detection | HIGH | `model_data.py` (would belong here) |
| 3 | No left-rail step workflow widget | HIGH | new `qt_workflow_rail.py` |
| 4 | Tk leaks: `cloth_rig.py`, IPC `_default_root.after`, `viewport.py` import dep | MEDIUM | listed §1.2 |
| 5 | `viewport.py` mixes Tk widget + renderer/camera — blocks clean Qt-only builds | MEDIUM | needs split |
| 6 | No Range-of-Motion auto-clip generator | MEDIUM | `accurig.py` extension |
| 7 | No spline-IK / wing / tail rigging modules | MEDIUM | new files in `src/autorig/` |
| 8 | Bone-dot HUD overlay missing in `qt_viewport.py` | MEDIUM | viewport extension |
| 9 | Mini-thumbnail inset missing | LOW | viewport extension |
| 10 | Symmetry toggle present in `grig.py` but not exposed in any Qt panel | MEDIUM | rig panel wiring |
| 11 | Validation service exists but no banner UI to surface it | MEDIUM | bottom-strip widget |
| 12 | Old `.ghostrigger_reference/ROADMAP.md` predates Qt migration; M5 Character Builder bullets are obsolete | HIGH | superseded by this doc |

---

## 7. Decision: Qt-only going forward

Marking this explicitly because the user asked: **the Qt branch is the only branch we extend.** Specifically:

- All new Character Builder work goes to `src/gui/qt_character_builder_*.py`.
- All new viewport features go to `src/gui/qt_viewport.py` (with renderer/camera split out of `viewport.py` into `viewport_core.py`).
- The Tk-side files (`main_window.py`, `character_builder_window.py`, `blueprint_editor.py`, `modular_panel.py`, `matrix_background.py`, `icon_manager.py`) are **frozen**. No new features land there. They stay only as a runtime fallback until M3 of the new roadmap, at which point they're removed.
- `cloth_rig.py` Tk popups become Qt dialogs *before* we extend the cloth module further.
- `ipc/{client,server}.py` `_default_root.after()` calls become `QTimer.singleShot(0, ...)` *before* the next IPC feature.

This is the entry condition for the fresh roadmap (see `02_roadmap_2026_05.md`).
