# GhostStudio Program-Wide UI/UX Audit

Date: 2026-07-28

Owner: LordVaderCW

Plan: `docs/plans/2026-07-28-program-wide-ui-ux-overhaul.md`

## Audit standard

This audit treats usability as a product and workflow property, not a styling pass. Each surface is evaluated against four questions:

1. Can the user identify where they are, what they are editing, and what state it is in?
2. Can the user discover the next meaningful action without remembering internal terminology?
3. Does every action provide timely feedback and a safe recovery path?
4. Does the workflow remain readable, accessible, and responsive on the target machine and display sizes?

The questions derive from the strategy-to-surface model in *The Elements of User Experience*, Norman's discoverability/signifier/feedback model, Krug's scanability and trunk test, and the decision-load and responsiveness principles in *Laws of UX*.

## Implementation status

### U2 shared shell — completed 2026-07-28

Findings A1 and A2 are resolved in the isolated
`codex/program-wide-ux-overhaul` branch. The 32-button command strip was
replaced by a small task hierarchy and a searchable, categorized product
launcher; developer commands require explicit Developer Mode; controls have
accessible names and font-derived targets; and startup no longer overwrites
saved navigation or layout state.

Visible proof used the freshly rebuilt Debug application. The shell was
unclipped at 1366x768, reflowed at 1280x720, survived all six supported themes,
and opened Map Studio through the filtered launcher. The product route also
established a performance baseline: the shell used about 428 MB, while opening
Map Studio blocked visible response for roughly 23 seconds and raised working
set to about 691 MB. A3 and Map Studio's own construction path therefore remain
priority inputs for U5 and U6.

## Surface inventory

| Surface family | Primary surfaces | Main owners | Dominant audit risks |
|---|---|---|---|
| Shared shell | Main window, header, command strip, menus, status bar, docks, first-run tutorial, workspace/profile controls | `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/qt_main_window.py`; `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/` | Action overload, icon ambiguity, duplicated layout concepts, overwritten preferences, eager startup cost |
| Browse and inspect | Content Browser, Resource Browser, 2DA Browser, Animation Browser, Scene, Properties, Nodes, Module Meshes | GUI Display panels and shared resource-panel mixins | Overlapping names, unclear search scope, selection side effects, empty-result recovery |
| Map authoring | Map Studio, workflow pages, tool belts, room/environment/terrain/placement/walkmesh/texture panels, PIE and proof dialogs | `native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py`; module-editor panels; owning Core Scene/Tools services | Too many simultaneous navigation systems, hidden readiness, unclear derived WOK/floor state, source/template discovery |
| Stock module editing | Module Editor, preview, TGA/TXI/WOK/LYT/VIS/GIT/template/metadata/DLG editors | `native/GhostRigger.Core.Tools/Python/src/gui/windows/stock_module_editor_window.py` | One long undifferentiated center column, unclear active resource context, patch/export safety |
| Character authoring | Character Builder selector/window, custom rigged builder, head/body/facial pages, workflow rail, validation/export | GUI Display windows/panels and Core Tools controllers | Naming drift, stage readiness, source-target-output identity, advanced controls before prerequisites |
| Animation authoring | Retargeting Workbench, Unreal Animator, Sequence Editor, Animation Browser, rigging and BAS panels | Core Tools windows/controllers; GUI Display sequence/panels | Duplicate output state, inconsistent theme ownership, source/target ambiguity, preview freshness |
| Asset authoring | GUI Editor, Placeable Builder, Particle Editor, Blueprint Editor, Scripting Suite | GUI Display and Core Tools windows/controllers | Inconsistent task spines, resource identity, validation/export visibility, ad-hoc error dialogs |
| Supporting tools | Settings, Diagnostics, Output Log, Python Terminal, texture/material/lightmap/UV tools, pickers and setup dialogs | GUI Display dialogs/panels | Developer controls exposed as ordinary settings, hardcoded presentation, raw exceptions, keyboard/scale gaps |

## High-confidence findings

### A1. The main command strip cannot fit its own minimum presentation

`WindowChromeMixin._make_command_bar` creates 32 fixed 30-pixel tool buttons, four fixed 34-pixel menu buttons, a scene pill, Workspace selector, and Visual Profile selector. Before layout spacing, margins, and stretch behavior, the fixed controls require roughly 1606 pixels. The buttons force icon-only presentation and set `_gr_ignore_layout_button_mode`, so layout profiles cannot repair the density.

Evidence:

- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/window_chrome.py:781`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/window_chrome.py:904`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/window_chrome.py:1094`

Impact: At laptop widths the first view becomes a clipped field of unlabeled icons. This violates scanability, increases decision time, hides major products behind tooltips, and makes the shell's own layout system ineffective.

Owner unit: U2.

### A2. Saved presentation state is overwritten during startup

The main window loads settings, then `_apply_startup_ui_defaults` forces the 3ds Max navigation profile, forces the `default` layout, and removes default-layout overrides. The same window presents Workspace and Visual Profile selectors as if the user's choices persist.

Evidence:

- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/qt_main_window.py:270`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/qt_main_window.py:411`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/window_chrome.py:904`

Impact: The interface teaches the user that customization is unreliable and makes restart behavior contradict the visible controls.

Owner units: U2, U8.

### A3. The main shell eagerly constructs dormant tools

`MainWindowLayoutMixin._build_layout` constructs the content/resource/2DA/scene/properties/animation/BAS panels, Rig window, Texture Tool window, Blueprint Editor window, and many docks before first usable paint. It also schedules BAS catalog work immediately.

Evidence:

- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/main_layout.py:76`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/main_layout.py:116`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/main_layout.py:142`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/main_layout.py:147`

Impact: Users pay startup memory and construction cost for features they may not open, which is especially harmful on the HP Pavilion-class target.

Owner unit: U5.

### A4. Product vocabulary does not provide one conceptual model

The code and documentation use GhostStudio, Ghost-Studio, Ghost Studio, and GhostRigger. The same products appear as Character Studio/Builder, Retarget Studio/Retargeting Workbench, Module Studio/Editor, and Map Studio/KMAP Area Authoring/Level Editor. Repository text contains all variants in significant numbers.

Evidence:

- `README.md:286`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/window_chrome.py:193`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/window_chrome.py:241`
- `native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py:1198`

Impact: A newcomer cannot confidently map tutorials, menus, windows, project formats, or troubleshooting guidance to the same product.

Owner units: U1, U2, U6-U9.

### A5. Search and browse surfaces overlap without explaining scope

Content Browser, Library/Animation Browser, Resource Browser, and 2DA Browser are separate concepts in the main shell. Some older entry points alias the same underlying content panel while other similarly named entry points open different data and actions.

Evidence:

- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/main_layout.py:76`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/main_layout.py:143`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/main_layout.py:147`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/window_chrome.py:207`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/window_chrome.py:286`

Impact: Users must memorize which browser contains a model, raw resource, animation, or 2DA table and what double-click will do.

Owner units: U2, U8.

### A6. Map Studio exposes competing navigation systems while hiding proof state

The Map Studio shell composes a main toolbar, workspace selector, default/custom tool belts, command search, eight workflow pages, left/right tab regions, and marking menus. Readiness and Validation/Output are present but initially hidden.

Evidence:

- `native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py:1457`
- `native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py:1781`

Impact: The first view emphasizes mechanisms instead of the create-connect-walk-place-validate-export task loop. Users can manipulate geometry without seeing whether it produces usable floor, aligned WOK, or export-ready state.

Owner unit: U6.

### A7. Stock Module Editor lacks contextual progressive disclosure

The stock editor stacks a large preview and separate TGA, TXI, WOK, LYT/VIS, GIT, template, metadata, and dialogue editors into one center column instead of presenting the editor relevant to the current resource and selection.

Evidence:

- `native/GhostRigger.Core.Tools/Python/src/gui/windows/stock_module_editor_window.py:278`
- `native/GhostRigger.Core.Tools/Python/src/gui/windows/stock_module_editor_window.py:592`

Impact: The user sees implementation categories before establishing which resource is active or which patch action is safe.

Owner unit: U6.

### A8. Retarget output state is duplicated

The Retargeting Workbench creates two independent sets of similarly named output controls and reassigns instance attributes during construction.

Evidence:

- `native/GhostRigger.Core.Tools/Python/src/gui/windows/qt_retarget_window.py:338`
- `native/GhostRigger.Core.Tools/Python/src/gui/windows/qt_retarget_window.py:401`

Impact: Visible values and controller references can disagree, leaving the user unsure which target slot/name/export policy will be applied.

Owner unit: U7.

### A9. Actionable error infrastructure exists but is not the default

`error_report.py` supports structured error details and recovery-oriented presentation, but most product windows still create ad-hoc message boxes. Current GUI payloads contain hundreds of information/warning/critical calls, many displaying raw `str(exc)`.

Evidence:

- `native/GhostRigger.Core.GUI.Display/Python/src/gui/dialogs/error_report.py:1`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/dialogs/error_report.py:163`
- `native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py:2443`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/qt_custom_rigged_character_builder_window.py:2425`

Impact: Failure quality depends on the window author. Users receive inconsistent detail, no recovery action, and internal exception wording.

Owner unit: U3 followed by U6-U8 migrations.

### A10. Advanced and developer presentation is inverted

Settings places renderer backend, fallback, safe mode, FPS, idle behavior, diagnostics cadence, dirty overlays, and bloom tuning under General while Advanced contains only theme hot reload. The main Tools menu also exposes IPC/developer operations after a separator but without a user-selectable developer mode.

Evidence:

- `native/GhostRigger.Core.GUI.Display/Python/src/gui/dialogs/qt_settings_dialog.py:140`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/dialogs/qt_settings_dialog.py:325`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/window_chrome.py:525`

Impact: New users face system internals before ordinary task preferences, while the real complexity remains poorly grouped.

Owner units: U2, U8.

### A11. Some workbenches bypass shared themes

Unreal Animator defines and applies a hardcoded dark stylesheet rather than participating fully in the six-theme system.

Evidence:

- `native/GhostRigger.Core.Tools/Python/src/gui/windows/qt_unreal_animator.py:24`
- `native/GhostRigger.Core.Tools/Python/src/gui/windows/qt_unreal_animator.py:194`

Impact: Light/Classic compatibility and cross-workbench consistency cannot be guaranteed by shared theme tests.

Owner units: U4, U7.

### A12. Shortcut identity is not globally controlled

The shell assigns `Ctrl+Shift+A` to both Animation Library and the Retargeting Workbench.

Evidence:

- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/window_chrome.py:207`
- `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/window_chrome.py:222`

Impact: Keyboard behavior depends on focus and registration order, undermining learnability and accessibility.

Owner units: U2, U4.

### A13. Current automated UI evidence is broad but not equivalent to user proof

The repository has strong widget/source contracts, six packaged themes, nine layouts/profiles, a 16-task Getting Started catalog, renderer pacing tests, and live IPC capture routes. Most tests construct widgets or inspect source rather than exercising a complete user task through a freshly built native Debug host. The existing executable predates this branch, and there is no durable matrix tying a commit, executable timestamp, task, theme, layout, DPI, screen size, result, capture, and timing together.

Evidence:

- `tests/test_theme_layout_loading.py`
- `tests/test_getting_started_tutorial.py`
- `native/GhostRigger.Core.Automation/Python/src/ipc/server.py`
- `native/GhostRigger.Core.Automation/Python/src/ipc/client.py`
- `native/GhostRigger.Native.Core.Host/GhostRigger.Native.Core.Host.vcxproj`

Impact: A green source-contract test can coexist with clipped, unreadable, unreachable, or misleading behavior in the application users run.

Owner unit: U9, with per-unit evidence beginning at U2.

### A14. Accessibility and small-screen coverage are sparse

Only a small minority of GUI Display Python files currently assign accessibility names or descriptions, explicit tab-order setup is absent, and theme validation checks tokens rather than contrast. The packaged Compact layout requests 1360x820, which is taller than a 1366x768 laptop display before Windows chrome and scaling.

Evidence:

- `native/GhostRigger.Core.GUI.Display/Python/src/gui/libtheme/theme_validator.py`
- `config/themes/layouts/compact.xml`
- `tests/test_theme_layout_loading.py`

Impact: Supported themes and layouts can validate structurally while keyboard, assistive technology, scaling, focus, and clipping failures remain invisible.

Owner units: U4, U9.

### A15. Portable performance policy is not suite-wide

Renderer profiling and frame-governor foundations exist, and Map Studio has an Iris Xe-oriented portable policy. General renderer defaults still target 60 FPS with bloom and a 512 MB texture budget, while the shell and other studios do not share the same portable policy or wall-clock/memory gates.

Evidence:

- `native/GhostRigger.Core.Rendering/Python/src/core/rendering/renderer_settings.py`
- `native/GhostRigger.Core.Rendering/Python/src/core/rendering/renderer_profiler.py`
- `native/GhostRigger.Core.Rendering/Python/src/core/rendering/renderer_performance.py`
- `native/GhostRigger.Core.Scene/Python/src/core/modules/map_studio_modeling_tools.py`

Impact: The target laptop can receive lower-cost Map Studio settings but still pay full-cost shell, theme, preview, and other workbench behavior.

Owner units: U5, U9.

## Existing patterns to extend

- Task-based workspace presets in `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/workspace_presets.py`.
- First-run routes and real workspace handoff in `native/GhostRigger.Core.GUI.Display/Python/src/gui/dialogs/qt_getting_started_window.py`.
- The Character workflow rail's stage names and blocked reasons in `native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/qt_workflow_rail.py`.
- Scripting Suite's left navigation, Start page, and safety messaging in `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/qt_scripting_dialogue_studio.py`.
- Shared progress panel/toast in `native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/progress_toast.py`.
- Structured error report presentation in `native/GhostRigger.Core.GUI.Display/Python/src/gui/dialogs/error_report.py`.
- `CollapsibleGroupBox` in `native/GhostRigger.Core.GUI.Display/Python/src/gui/libtheme/collapsible_group.py`.
- Theme and layout managers plus `tests/test_theme_layout_loading.py`.

## Baseline conclusions

The highest-leverage first implementation is the shared shell rather than another isolated studio redesign. The shell currently violates the target width mechanically, presents too many peer actions, duplicates workspace concepts, conflicts on shortcuts, and overwrites saved layout state. Fixing that layer creates a reusable action hierarchy and vocabulary for later studio migrations.

Performance work must follow immediately after the shell slice because many dormant tools are eagerly constructed before first usable paint. Error/recovery and accessibility primitives should land before migrating individual studios; otherwise each studio will continue creating bespoke message boxes and control semantics.
