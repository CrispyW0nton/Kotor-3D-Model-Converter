# GhostRigger — UI/UX Audit Report

**Scope:** `native/GhostRigger.Core.GUI.Display/Python/src/gui/`
**Method:** Static code review of main window, viewport, panels, theme, dialogs, and shared application-core mixins.
**Auditor:** Hermes Agent subagent (read-only review).

---

## Executive summary

GhostRigger is an **ambitious, feature-dense single-window Qt application** (PySide6) that
exposes ~17 dock panels, 10 top-level menus, and ~60 actions. It is clearly written by people
who know the KotOR modding domain, and the *engine plumbing* (background workers, theme tokens,
progress toasts, detachable docks) is genuinely sophisticated. However, the **user-facing layer
has serious discoverability, consistency, and blocking-UX problems** that would overwhelm a new
modder and frustrate an experienced one.

The single most impactful issues, in priority order:

1. **No workspace / studio concept** — every panel ships open (or one click away), so the app
   presents all of its complexity at once. There is no "I'm rigging now / I'm animating now" mode.
2. **MDLOps compile/decompile and OBJ/FBX/GLTF import/export run synchronously on the UI thread**
   with no progress bar and no cancellation — the window freezes for up to 30s.
3. **The "Modules" top-level menu is a kitchen-sink** mixing workspace launchers, 14 panel
   toggles, file generation, and IPC plumbing — with no discoverable organization.
4. **No global undo/redo.** Undo exists *only* for viewport camera edits (`Ctrl+Z`/`Ctrl+Y` are
   scoped to the viewport, not scene mutations). Transform/scene changes are permanent.
5. **Raw exception strings shown to users** in 121 modal `QMessageBox.critical` calls — no
   user-friendly copy, no recovery hints, no error categories.
6. **Dangerous / unconventional keyboard shortcuts** (`Ctrl+W` clears the model, `Ctrl+M`
   exports binary, single-key `W/B/T/F/R` are unscoped).

---

## 1. Main window structure & navigation

**Files:** `windows/qt_main_window.py`, `windows/application_core/shared/main_layout.py`,
`windows/application_core/shared/window_chrome.py`, `windows/application_core/shared/dock_hosts.py`

### 1.1 There are no "studios" — it is one giant kitchen-sink window

Despite the task brief asking about "four studios," the codebase contains **no workspace/studio
abstraction**. `MainWindowLayoutMixin._build_layout()` (`main_layout.py:39-345`) eagerly instantiates
**17 dock panels** and wires **250+ signal connections** in a single 300-line method:

- Left dock: Content Browser stacked under Scene Outliner
- Right dock: Properties, Animation Browser, Body Attachment, Lighting, Cameras, Module Meshes,
  Sprite Materials, Mesh Tools, Adjust Pivot, Diagnostics
- Bottom dock: Output Log + Python Terminal (split horizontally)
- Plus 6 hidden panels (Nodes, 2DA, Resources, etc.) reachable only via the Modules menu

The `_detachable_panel_sizes` dict (`main_layout.py:146-164`) hard-codes pixel sizes for all 17
panels. New users land in a wall of panels with no guidance about which matter for their task.

**Recommendation:** Introduce a `Workspace` concept (like Blender/Unreal):
- "Modeling", "Rigging", "Animation", "Level Design" presets that show/hide dock groups.
- Persist the active workspace and restore it on launch.
- A workspace switcher in the header (the `ReservedTopUi` shell at `main_layout.py:40-60` already
  exists and would host it cleanly).

### 1.2 Menu bar is overloaded and inconsistently organized

`WindowChromeMixin._build_menu()` (`window_chrome.py:294-446`) creates **10 top-level menus**:
`File, Customise, Model, MDLOps, Help, Retarget, Modules, Tools, Create, IPC`.

Problems:
- **"Modules" is a kitchen-sink** (`window_chrome.py:379-406`): it contains workspace launchers
  (Map Studio, Module Editor, Rigging, Retarget, Sequence Editor), **14 panel toggles**
  (Content Browser, Scene, Properties, … Python Terminal), module-file actions (Port, Generate),
  and an "About" item. 22+ entries with no sub-grouping.
- **Panel toggles are split across menus**: some in Modules, Character Builder in Tools,
  Animation Browser duplicated in both Modules and Tools.
- **No "View" menu** — wireframe/grid/bones toggles live under "Model," which is unintuitive.
- **No "Edit" menu** — there is no global Undo/Redo/Copy/Paste/Preferences entry point.
- **No "Window" menu** — the conventional place for panel toggles is missing.
- **"IPC" menu exposes internal plumbing to end users** (`window_chrome.py:433-446`):
  "Ping GhostScripter (port 7002)" has no business being user-visible. Move to a hidden
  developer/debug menu (e.g. toggle with a `--debug` flag or env var).
- **Spelling inconsistency**: "Customise" (British) vs. "Color", "Behavior" (American) used
  elsewhere. Pick one locale.

**Recommendation:** Restructure to `File, Edit, View, Create, Tools, Window, Help` and move
domain menus (MDLOps, Retarget, Modules) under Tools or a "Workflow" umbrella. Hide IPC behind a
dev flag.

### 1.3 Dangerous / unconventional keyboard shortcuts

From `_build_actions()` (`window_chrome.py:33-292`):

| Shortcut | Action | Concern |
|---|---|---|
| `Ctrl+W` | **Clear Model** | Conventionally "close document/tab." Clears user's work with no confirmation. |
| `Ctrl+M` | Export Binary MDL | Conventionally "minimize window" on Windows/macOS. |
| `Ctrl+R` | Auto-Rig | Conventionally "reload." |
| `Ctrl+A` | Animation Library | Conflicts with standard "Select All" inside tree/list widgets. |
| `Ctrl+D` | Diagnostics | Conventionally "duplicate." |
| `Ctrl+B` | Character Builder | Conventionally "bold." |
| `F2` | Settings | Conventionally "rename." |
| `W`/`B`/`T`/`F`/`R` | Viewport toggles | Single-key shortcuts risk firing while typing in panels unless explicitly scoped to the viewport widget's focus. |

**Recommendation:** Audit every shortcut against platform conventions; scope single-key
shortcuts to the viewport via `QShortcut` with `Qt.WidgetWithChildrenShortcut` context, or move
them to `Ctrl+Shift+` prefixes.

### 1.4 Dead "compatibility placeholder" widgets

`main_layout.py:338-344` creates orphan widgets purely to satisfy legacy code paths:
```python
self.k1_dir_edit = QtWidgets.QLineEdit(...)
self.k2_dir_edit = QtWidgets.QLineEdit(...)
self.scan_button = QtWidgets.QPushButton("Scan")
self.library_list = QtWidgets.QListWidget()
self.library_filter = QtWidgets.QLineEdit()
self.props_text = QtWidgets.QTextEdit()
```
These are never laid out. They are migration debt that should be deleted once the real
Content Browser / Settings Dialog fully own these responsibilities.

---

## 2. Viewport UX

**Files:** `viewports/qt_viewport.py` (70-line facade), `viewports/viewport_core/widget.py`,
`viewports/viewport_core/widgets/*` (16 mixin files), `windows/application_core/shared/window_chrome.py`
(viewport toolbar band).

### 2.1 Good foundations, but viewport-only undo

The viewport is a **16-mixin composition** (`viewport_core/widget.py`) — camera, selection,
gizmo, overlays, measurement, construction, etc. are cleanly separated. Camera controls,
selection feedback, and a transform gizmo all exist. There's a ViewCube, snap view bar,
transform type-in bar, and mini thumbnail. This is solid work.

**But:** undo/redo is **viewport-scoped only** (`window_chrome.py:104-109`):
```python
self.undo_viewport_action ... setShortcut("Ctrl+Z") ... _call_viewport("undo")
self.redo_viewport_action ... setShortcut("Ctrl+Y") ... _call_viewport("redo")
```
`Ctrl+Z` only reverts viewport camera edits. **Scene-level mutations (move, delete, rename,
light/camera changes, mesh operations) are not undoable at all.** This is a major workflow gap
for a content-creation tool.

**Recommendation:** Introduce a central `QUndoStack` and wrap mutating operations
(`_record_transform_event`, `_record_lighting_event`, `_record_camera_event` hooks already exist
in `main_layout.py:268,276,286`) in `QUndoCommand` subclasses.

### 2.2 Viewport toolbar band is always-on and mode-coupled

`window_chrome.py:_make_viewport_toolbar_band()` builds a toolbar with "Modeling" and "Blockout"
tabs whose buttons all delegate to `_run_map_studio_viewport_modeling_command` — i.e. they do
nothing unless Map Studio is open. This wastes vertical space in the common case and is confusing
(buttons appear enabled but are effectively dead).

**Recommendation:** Hide the band until Map Studio is active, or disable/grey the buttons with a
tooltip "Open Map Studio to enable."

### 2.3 Hardcoded sizes throughout the viewport chrome

`window_chrome.py` and `viewport_core/widgets/*` are littered with magic numbers:
`setFixedSize(30, 22)`, `setFixedSize(34, 22)`, `setIconSize(QSize(18, 18))`,
`setFixedHeight(58)` (header), `setMinimumWidth(420)` (viewport). These do not scale with DPI or
the theme's metric tokens (which *do* exist — see §4).

---

## 3. Panel & dialog quality

**Files:** `panels/qt_properties_panel.py` (1055 lines), `panels/qt_content_browser_panel.py`
(1717), `panels/qt_inspector_panel.py` (2543), `panels/qt_character_builder_panel.py` (**4605**),
`panels/qt_library_panel.py` (2484), `panels/qt_log_panel.py` (499), `dialogs/qt_settings_dialog.py`
(758), `dialogs/qt_dialogs.py`, `dialogs/qt_export_dialog.py`.

### 3.1 Panels are monolithic

Several panels have grown to monolithic sizes that resist maintenance:
- `qt_character_builder_panel.py` — **4605 lines**
- `qt_inspector_panel.py` — **2543 lines**
- `qt_library_panel.py` — **2484 lines**
- `qt_content_browser_panel.py` — **1717 lines**

These should be decomposed into sub-widgets (the viewport team already did this with 16 mixins;
the panels should follow suit).

### 3.2 Properties panel only edits Position

`qt_properties_panel.py` exposes a Transform group with **Position only** — no Rotation, no Scale
spin boxes. For a 3D modeler this is a surprising limitation; users must use the gizmo for
rotation/scale. The transform group is also hidden by default (`setVisible(False)`) with no
affordance showing it exists when a node is selected.

### 3.3 Module browser duplicates four near-identical sub-tabs

The Properties panel's module browser has four tabs (Meshes, Walls, NULL Meshes, Walkmeshes),
each with its own filter box, tree, and count label — heavy duplication that should be one
parameterized component.

### 3.4 Settings dialog is well-structured

`qt_settings_dialog.py` uses a `QTabWidget` with Paths / General / Renderer / Theme tabs, an
auto-detect button with a tooltip, and is **non-modal** (`setWindowModality(NonModal)`) — good.
This is a model the rest of the dialogs should follow.

### 3.5 Log panel is good but lacks filter/search

`qt_log_panel.py` is well-built: syntax-highlighted, level auto-detection via regex, save/copy/
clear, auto-surfaces on error, capped at `MAX_LOG_LINES = 500` (hardcoded). Missing: a level
filter row, a search/find box, and a configurable line cap (long debug sessions lose history).

---

## 4. Theme & layout system

**Files:** `libtheme/style_tokens.py`, `libtheme/theme_manager.py`, `libtheme/layout_applier.py`,
`windows/application_core/shared/splash.py`, plus `qt_lib.py` shim.

### 4.1 A real token system exists — but legacy hardcoded colors linger

`style_tokens.py` defines `LEGACY_MATRIX_COLORS`, `FALLBACK_COLORS`, and
`NATIVE_FALLBACK_COLORS` — a proper token system with semantic keys (`panel.background`,
`input.focusBorder`, `accent.primary`, etc.). `ThemeManager`, `LayoutManager`, and
`layout_applier.py` provide a mature theming + layout pipeline.

**However**, many widgets still bypass tokens and read legacy keys directly:
- `window_chrome.py:22-24`: `C = dict(LEGACY_MATRIX_COLORS)` then uses `C['accent']`,
  `C['gold']`, `C['text2']` in inline stylesheets.
- `qt_properties_panel.py` and `qt_log_panel.py` import `C` from `qt_theme` and use `C['gold']`,
  `C['success']`, etc. directly in Python rather than going through the theme object.
- `qt_workflow_rail.py` has a hardcoded `_CHARACTER_MODE_BADGE_COLORS` dict with literal hex
  values (`#3FA9F5`, …) that ignore the active theme entirely.
- `splash.py:30-51` defines yet another parallel `BRANDED_SPLASH_COLORS` token set.

This means a user who switches to the native/light theme will still see matrix-green accents in
these widgets. The migration to tokens is half-finished.

**Recommendation:** Complete the token migration; add a lint/test that fails when
`LEGACY_MATRIX_COLORS` is imported outside the theme layer.

### 4.2 `qt_lib.py` is a meta-path-finder alias shim

`gui/qt_lib.py` (321 lines) registers a custom `MetaPathFinder` that aliases
`src.gui.qt_lib.panels.qt_content_browser_panel` → `src.gui.panels.qt_content_browser_panel`,
and so on for ~120 modules across 13 groups. This is clever indirection but:
- Confuses IDEs and `grep`/`rg` (the import path doesn't match the file path).
- Every import pays a lazy-load cost on first access.
- New contributors must learn two naming schemes.

**Recommendation:** Migrate imports to the real paths and delete the shim, or document it
prominently. The shim currently makes the codebase harder to navigate than necessary.

---

## 5. Error handling UX

**Files:** `windows/application_core/shared/model_io.py` (19 modal dialogs),
`windows/application_core/shared/retarget_*.py` (23 dialogs), all panels/dialogs.
**Total: 121 `QMessageBox.(critical|warning|information|question)` calls.**

### 5.1 Raw exception strings shown to users

The dominant pattern (e.g. `model_io.py:40-42, 64-66, 161-163, 187-189, …`):
```python
except Exception as exc:
    self._log(f"OBJ import error: {exc}", "error")
    QtWidgets.QMessageBox.critical(self, "OBJ Import Error", str(exc))
```
Users see raw Python tracebacks/exception messages (e.g. "IndexError: list index out of range")
with **no explanation of what went wrong, why, or how to recover.** There are no error codes,
categories, or "Show details / Copy / Report" affordances.

### 5.2 Errors are purely modal

All 121 are blocking modal dialogs. There is no non-modal error toast, no error list view, no
"don't show again." For batch operations (e.g. batch library export) the user must click through
one dialog per failure.

### 5.3 Good: FBX SDK missing-path handling is a model

`model_io.py:300-325` (`_ensure_fbx_sdk_available_for_action`) is the gold standard: it explains
*why* FBX is disabled, offers "Open Setup Assistant" *and* "Open Autodesk Download Page" actions,
and is informative rather than just blocking. The rest of the error handling should follow this
pattern.

**Recommendation:**
- Create an `ErrorReport` abstraction with `category`, `user_message`, `detail`, `recovery_actions`.
- Render errors in the existing Diagnostics panel (or a dedicated Error List) instead of modally.
- Translate known exception types (FileNotFoundError, parse errors, missing-dependency
  ImportError) into friendly copy with recovery suggestions.

---

## 6. Onboarding & discoverability

### 6.1 A guided workflow rail exists — but only in Character Builder

`panels/qt_workflow_rail.py` implements a 5-step guided workflow (Select Base → Add Parts → … →
Export). This is the **only onboarding-like structure in the entire app**, and it lives inside
the Character Builder window — the main window has nothing equivalent.

**Bug/dead-complexity:** `qt_workflow_rail.py` defines **six identical step lists**
(`_STEPS_HEADLESS_BODY`, `_STEPS_HEAD`, `_STEPS_SUPERMODEL`, `_STEPS_HUMANOID`, `_STEPS_CREATURE`,
`_STEPS_FALLBACK`) that are all the same 5 steps. The mode-awareness is essentially dead code.

### 6.2 Splash screen is informative

`splash.py` (`QtStartupSplash`) shows staged progress (Native audit → Renderer/hardware scan →
Resources → Workspace) with a live launch log, percent, and clear/done markers. This is
well-executed.

### 6.3 Tooltips are unevenly distributed

196 `setToolTip`/`setStatusTip`/`setWhatsThis` calls across 49 files — but heavily concentrated:
`qt_inspector_panel.py` has 43, `qt_character_builder_panel.py` 14, `window_chrome.py` 11.
Many menu actions in `window_chrome.py` (e.g. the 14 panel toggles, the IPC actions, MDLOps
actions) have **no tooltip or status tip**. A new user hovering "Ping GModular (port 7003)"
gets no explanation.

**Recommendation:** Add `setStatusTip` to every `QAction` (cheap, shows in the status bar); add
`setToolTip` to toolbar buttons; add a first-run "Welcome / Getting Started" overlay or a
`Help → Interactive Tour`.

---

## 7. Performance UX

### 7.1 MDL loading is async with progress — the gold standard

`workers.py` (`ModelLoadWorker`, `ResourceModelLoadWorker`,
`load_module_room_models_from_game_resources`) runs on `QThread` with a 5-step `progress` signal
wired to `progress_toast.py` (a non-modal, viewport-anchored toast). This is excellent.

### 7.2 OBJ/FBX/GLTF import & export block the UI thread

Despite the async infrastructure existing, `model_io.py` runs **all** of these synchronously on
the calling (UI) thread:
- `_import_obj_from_path` (`:32-42`)
- `_import_fbx_model` (`:121-142`)
- `_import_gltf` (`:143-163`)
- `_save_ascii_mdl`, `_export_mdl_binary`, `_export_obj`, `_export_fbx`, `_export_gltf`,
  `_export_humanoid_template`, `_port_current_model`

FBX export in particular can take many seconds; the window freezes with no progress and no cancel.

### 7.3 MDLOps compile/decompile blocks the UI for up to 30s

`model_io.py:513-530` (`_run_mdlops`):
```python
result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=str(cwd))
```
This is a **synchronous subprocess call on the UI thread** with a 30-second timeout and **no
progress indicator and no cancellation.** The entire app appears hung. This should use the same
`ModelLoadWorker` pattern (a `QProcess` or a `QThread` worker).

**Recommendation:** Route all import/export/compile/decompile through the existing
`QThread`+`progress_toast` pipeline. Add a Cancel button to the toast for long operations.

---

## 8. Workflow cohesion

### 8.1 The four "studios" feel like one window + three detached children

The brief references "four studios." In practice:
- **Main window** = the kitchen-sink dock window.
- **Map Studio / Module Editor** = separate `QMainWindow` (`qt_module_editor_window.py`).
- **Character Builder** = separate window with its own viewport and workflow rail.
- **Retarget Workbench / Unreal Animator** = separate windows with their own viewport adapters.

Each child window re-implements its own viewport (`QtRetargetViewportWidget`,
`QtCharacterBuilderViewportWidget`, `QtUnrealAnimatorViewportWidget` — all facades over the same
`viewport_core.widget`). They share the theme but **not selection, not undo history, not scene
state.** There is no obvious way to move an asset from the Character Builder back into the main
scene, or to share a selection between the Retarget Workbench and the main viewport.

**Recommendation:** Define a shared `SceneContext` / `SelectionService` that all windows bind to,
so selecting a node in one window highlights it everywhere. Consider tabbed MDI for the child
studios instead of free-floating windows.

### 8.2 Signal wiring is a 250-line flat block

`main_layout.py:70-327` is a single method that connects ~130 signals with no grouping or
comments. This makes it hard to see which panels belong to which workflow. Grouping the
connections by feature area (with section comments) would dramatically improve maintainability
and make it obvious where a "workspace" abstraction could slice the wiring.

---

## 9. Quality-of-life quick wins (ranked)

| # | Issue | Effort | Impact |
|---|---|---|---|
| 1 | Move MDLOps + OBJ/FBX/GLTF I/O to background threads with progress + cancel | Medium | High |
| 2 | Add a central `QUndoStack` for scene/transform/light/camera edits | Medium-High | High |
| 3 | Restructure menus (File/Edit/View/Create/Tools/Window/Help); hide IPC behind dev flag | Low-Medium | High |
| 4 | Introduce Workspace presets (Modeling/Rigging/Animation/Level) that toggle dock groups | Medium | High |
| 5 | Replace raw `str(exc)` in 121 dialogs with friendly `ErrorReport` + recovery actions | Medium | High |
| 6 | Reassign dangerous shortcuts (`Ctrl+W`, `Ctrl+M`, `Ctrl+R`, `Ctrl+A`, `Ctrl+D`, `F2`) | Low | Medium |
| 7 | Complete the theme-token migration (remove `LEGACY_MATRIX_COLORS` usage in panels) | Medium | Medium |
| 8 | Add `setStatusTip` to all ~60 actions; add a first-run welcome/tour | Low | Medium |
| 9 | Add Rotation + Scale to the Properties Transform group | Low | Medium |
| 10 | Add level-filter + search + configurable cap to the Output Log | Low | Low-Medium |
| 11 | Auto-run Diagnostics on model load; surface real validation (parse/texture) not just GPU stats | Medium | Medium |
| 12 | Delete the dead compatibility placeholders in `main_layout.py:338-344` | Trivial | Low |
| 13 | Collapse the 6 identical workflow-rail step lists into one | Trivial | Low |
| 14 | Decompose the 2000-4600-line panels into sub-widgets | High | Medium |

---

## 10. Where Hermes skills could help

A Hermes skill (project-scoped automation) would be valuable for:

- **`ghostrigger-ux-lint`**: a pre-commit/CI skill that fails when (a) `LEGACY_MATRIX_COLORS` is
  imported outside `libtheme/`, (b) a `QMessageBox.critical` is added without an `ErrorReport`
  wrapper, (c) a `subprocess.run`/blocking call appears in a file under
  `windows/application_core/shared/` outside a `QThread` worker, (d) hardcoded `setFixed*`
  pixel sizes appear outside the theme layer.
- **`ghostrigger-shortcut-audit`**: a skill that enumerates all `setShortcut` calls and flags
  conflicts with platform conventions or with each other.
- **`ghostrigger-panel-scaffold`**: a skill that generates a new dock panel skeleton (with theme
  tokens, tooltips, an `apply_ghost_theme` hook, and the detachable-dock registration) to enforce
  consistency and stop the monolithic-panel growth.
- **`ghostrigger-menu-architecture`**: a skill that renders the current menu/action graph and
  highlights entries that are duplicated, orphaned, or in the wrong top-level menu.

---

*End of report. No source files were modified during this audit.*
