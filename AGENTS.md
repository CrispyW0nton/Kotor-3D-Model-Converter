# GhostRigger Agent Instructions

## MCP tools are for backend/model-pipeline validation only

Before writing or modifying backend code that handles MDL loading, vertex
transforms, textures, skinning, model pipeline comparison, or game-file parsing,
FIRST query the MCP tools to get ground-truth data from the actual game files.
Do not guess. Do not assume based on code comments.

Do not use MCP tools, headless widget construction, or backend probes as a
substitute for visual UI/workflow testing. Use them only for backend logic and
data-pipeline truth checks.

## Backend MCP tools do not require the GUI

The MCP tools in ghostrigger_tools.py import GhostRigger's Python modules directly.
The PYTHONPATH in .cursor/mcp.json includes the GhostRigger root directory.
If you get an ImportError, fix the import path — don't ask the user to open GhostRigger.

## When fixing a bug:
1. Use compare_model_pipelines(game, resref) to confirm the bug exists
2. Use inspect_mdl(game, resref) to get PyKotor ground truth
3. Use inspect_mdl_ghostrigger(game, resref) to see what GhostRigger produces
4. Identify the divergence
5. Fix the code
6. Re-run compare_model_pipelines to confirm the fix
7. Run only targeted regression checks by default. Do not run broad/full scans unless the user explicitly approves them for that task.

## When running tests:
- Prefer `python -m py_compile ...`, targeted single test files, or specific `pytest path::test_name` cases tied to the change.
- Do not run broad suites such as `pytest tests/`, `pytest tests/ -x`, `pytest tests/ -m "not slow"`, or full-scan tests unless the user explicitly asks for them.
- Do not run `pytest tests/test_mcp_full_scan.py` unless the user explicitly asks for the complete 6,078-model validation.
- When testing whether application behavior works, launch the actual
  GhostRigger Debug application from the active Visual Studio instance and test
  it on screen. Visible testing is required for UI, startup, viewport,
  theme/layout, and workflow checks. Do not replace this with MCP calls, direct
  widget screenshots, or backend-only probes.

## Core visible test fixtures

When testing simple application behavior, prefer the smallest fixture that
exercises the workflow:

- Static-object workflows: use `PLC_bench` for selection, selection modes, mesh
  tools, and pivot tools on static meshes. It is the fastest baseline for
  object-tool testing.
- Animation workflows: use `N_DarthMalak` as the whole-model animation baseline
  with the `walk` animation looped unless the user explicitly names another
  model or animation. For headless/body-part coverage, use Carth's body with
  Carth's head attached. For cloth-model coverage, use Bastila's body and head.
- Module and lighting workflows: use the Ebon Hawk module, preferably
  `K2:001ebo1` / `001EBO1` unless the user explicitly names another module.

## Renderer module test fixture

When working on renderer behavior for imported modules, use `K2:001ebo1` /
`001EBO1` as the primary visible test module unless the user explicitly names
another module. It is the baseline module for OpenGL-vs-D3D lighting,
lightmap, texture, and material parity checks.

## Animation test fixture

When testing animations, use `N_DarthMalak` with the `walk` animation looped
unless the user explicitly names another model or animation.

## Change log

After any fix or software change is successfully completed, update `CHANGES.md`
with a dated entry. Include the relevant `T###` roadmap task ID when one applies,
a concise summary of the change, the affected files or subsystem, and the
verification performed. Keep entries factual so future agents can avoid repeating
completed work.

Every new `CHANGES.md` entry must include an owner line using the project owner's
GitHub username: `Owner: LordVaderCW`. If the change overlaps, merges, rebases,
or otherwise intersects work from another contributor, also include an
`Intersects:` line naming the other user or branch/commit when known and briefly
state the touched subsystem, for example `Intersects: upstream/qt-ghostrigger
Character Builder export changes`. This keeps concurrent changelog edits
attributable and easier to merge.

Before merging an upstream or long-lived branch, create a temporary pre-merge
safety branch from the current HEAD, for example
`codex/pre-merge-<branch>-<YYYYMMDD>`. After the merge is committed and the
post-merge checks pass, delete that temporary safety branch so it does not remain
as stale branch clutter. Keep the merge commit and changelog entry; the temporary
branch is only a rollback handle during the merge.

## Python terminal cheatsheet

When adding, changing, or discovering useful commands for the embedded Python
terminal, update `CHEETSHEET.md`. Keep it focused on commands a user can paste
into the terminal, especially helpers exposed by the GUI such as selected-model,
viewport, animation, export, diagnostic, or debugging commands.

## Commit format:
fix(scope): short description
feat(scope): short description  
chore(cleanup): short description
test(scope): short description

## Active branch — `qt-ghostrigger` (M0–M11 roadmap)

The active development branch is `qt-ghostrigger`. The roadmap lives at
`knowledge_base/roadmap/02_roadmap_2026_05.md`. Every commit message must
reference its `T###` task ID. Open PRs against `qt-ghostrigger`, never `main`.

## Architecture and system boundaries

GhostRigger now uses a separated filesystem architecture. Before adding or
moving code, identify the owning layer and put the change in that layer first;
do not append new behavior to a convenient window, panel, viewport, or helper
file just because that is where the call starts.

- `src/core/<domain>/` owns headless domain models, services, validation,
  scene/project state, resource rules, import/export decisions, and workflow
  policies. Core code must not import Qt or `src.gui.*`.
- `src/systems/<system_name>/` owns focused feature systems and model pipelines
  that sit above core primitives, such as BAS assembly/composition. New durable
  systems should get their own package here instead of being embedded in GUI
  windows or viewport modules.
- `src/adapters/<technology_or_surface>/` owns glue to external runtimes,
  renderer backends, Qt-facing adapters, file/runtime APIs, and integration
  boundaries. Keep technology-specific details here when they are not pure core
  logic and not direct widget code.
- `src/gui/windows/`, `src/gui/panels/`, `src/gui/dialogs/`, and
  `src/gui/viewports/` own presentation, widgets, signals, user gestures,
  theme/layout application, and calls into services. They must not become the
  owner of parsing, model-pipeline logic, transform math, resource lifetime
  rules, export formats, validation policy, or reusable business functions.
- `src/math/` owns reusable math. Do not hide new transform, camera, layout,
  pivot, projection, or coordinate-system math inside GUI files.
- `src/io/`, `src/formats/`, and `src/resources/` own file formats, resource
  discovery, and serialization/deserialization concerns. Do not implement
  game-file parsing or format writing inside windows, panels, or viewport code.

When adding a new function or system:

1. Search for the existing owner with `rg` and inspect nearby packages before
   editing.
2. Name the owning product surface and owning code package in the change notes
   or plan, for example `src/systems/bas`, `src/core/scene`,
   `src/core/modules`, `src/adapters/qt_viewport`, or `src/gui/panels`.
3. If no owner exists, create a focused module/package in the correct layer and
   expose a small API for the UI to call. Do not create another broad
   `helpers.py`, `utils.py`, or window-local function pile.
4. Keep dependency direction clean: GUI may call core/systems/adapters; adapters
   may wrap core/systems for a runtime; core and systems must stay usable
   without importing GUI widgets.
5. Window files such as `qt_main_window.py`, `module_editor_window.py`,
   `qt_character_builder_window.py`, `qt_retarget_window.py`, and files under
   `src/gui/windows/application_core/shared/` may orchestrate workflows, but
   new reusable logic belongs in the owning core/system/adapter module first.
6. If a window or panel change needs more than signal wiring, widget state, or a
   short call into a service, extract the function into the owning subsystem and
   keep the GUI as the caller.
7. Add or update focused tests/contracts for the owning layer. Prefer testing
   core/system behavior without Qt, then add visible GUI checks only for the
   actual UI workflow.

## Tk removal — completed in M3 / T302

Milestone M3 / T302 deleted the eight legacy Tk modules that previously
lived under `src/gui/`. They are gone from the working tree and survive
only in git history (commit `838831f` is the last ref before deletion):

- `src/gui/main_window.py`              — legacy Tk main window
- `src/gui/character_builder_window.py` — legacy Tk Character Builder
- `src/gui/blueprint_editor.py`         — legacy Tk UTC/UTP/UTD editor
- `src/gui/modular_panel.py`            — legacy Tk module-editor panel
- `src/gui/matrix_background.py`        — legacy Tk MP4 background engine
- `src/gui/icon_manager.py`             — legacy Tk PhotoImage icon loader
- `src/gui/viewport_tk.py`              — Tk widgets split out of viewport.py (T001)
- `src/gui/viewport.py`                 — backward-compat shim that re-exported both

All UI work now happens under the grouped `src/gui/` category folders and is
imported through the central `src/gui/qt_lib.py` facade. The `src/gui` package
root should contain only `qt_lib.py`, `__init__.py`, and documentation.
`tests/test_qt_only_imports.py` includes guards (`test_legacy_tk_modules_are_deleted`,
`test_no_gui_module_imports_tkinter`, `test_gui_root_only_keeps_central_qt_lib`)
that fail CI if any of the eight files return, if a new root shim appears, or
if a new file under `src/gui/` imports tkinter.

## Qt imports

- `src.gui.rendering.frame_core.renderer` - Tk-free software frame-rendering backend.
- `src.gui.camera.arcball_camera` - ArcBall camera state.
- `src.gui.textures.tpc` / `src.gui.textures.txi` - TPC/TXI texture helpers.
- `src.gui.qt_lib.viewports.viewport_display` - viewport display mode state.
- `src.gui.qt_lib.viewports.viewport_navigation` - viewport navigation profiles.
- `src.gui.qt_lib.viewports.qt_viewport` - Qt viewport widgets.
- `src.gui.qt_lib.windows.qt_main_window` - Qt main window entry point.
- `src.gui.qt_lib.<category>.<module>` - canonical Qt GUI import route.

Do not add `from .viewport import ...` anywhere; that shim no longer exists.
Import `FrameRenderer`, `ArcBallCamera`, `_load_tpc_bytes`, `_is_tpc_data`,
  `_clean_tex_name`, etc. through `src.math.frame_math`.
  Viewport display and navigation modules live under `src/gui/viewports/`;
  do not add new viewport-owned modules under `src/gui/rendering/`.
  The software frame-renderer backend lives under `src/gui/rendering/frame_core/`,
  ArcBall camera state under `src/gui/camera/`, and TPC/TXI texture helpers under
  `src/gui/textures/`. Keep the `src/gui/viewports/frame_renderer.py` facade thin.

## Math helpers

- Shared project math helpers live under `src/math/`.
- Do not add new math helper modules under `src/gui/`, renderer backend folders,
  viewport folders, camera folders, or gizmo folders. Keep those old paths as
  compatibility shims only when needed.
- Import canonical math helpers directly from `src.math.*`, for example
  `src.math.frame_math`, `src.math.gpu_math`, `src.math.camera_math`,
  `src.math.transform_math`, and `src.math.viewcube_math`.

## Qt viewport module structure

- Keep `src/gui/viewports/qt_viewport.py` as a lazy public compatibility
  facade. Do not put implementation back into this file.
- Keep `src/gui/viewports/viewport_core/widget.py` as a lazy widget facade.
  Do not grow it into another large implementation module.
- Shared viewport imports and helper APIs belong under
  `src/gui/viewports/viewport_core/shared/`, split by responsibility:
  dependency imports, icon helpers, selection-mode constants, joint-dot
  palette helpers, weight heat-map helpers, and similar non-widget support.
- Actual viewport widgets belong under `src/gui/viewports/viewport_core/widgets/`.
  New standalone viewport widgets should be added as focused modules there and
  exported through the lazy facade when they are part of the public viewport API.
- `QtViewportWidget` behavior is composed from focused mixin modules in
  `viewport_core/widgets/` (`construction`, `scene_models`, `display_controls`,
  `camera_workflow`, `measurement_controls`, `transform_camera`,
  `selection_mesh`, `history_animation`, `event_navigation`,
  `rendering_pipeline`, `overlay_layers`, `picking_hover`,
  `drag_interactions`, `resource_cache`, and `state_helpers`). Patch the owning
  mixin module instead of editing unrelated viewport behavior.
- If a new viewport feature needs many methods, create a new focused mixin
  module and add it to `QtViewportWidget` deliberately. Preserve the existing
  public import path through `src.gui.qt_lib.viewports.qt_viewport`.
- Update the source-contract tests that assemble viewport source from split
  files when adding a new viewport module that those contracts need to inspect.

## UI/workbench boundaries

- Respect separate modules, panels, and standalone workbench windows. Before
  adding a feature, identify the owning product surface: Main Viewport/KMAX,
  Retarget Workbench, Character Studio, Module Studio, Map Studio, Resource
  Browser, Validation, Export, or Project/session infrastructure.
- Treat GUI windows as composition roots and presentation shells. They may wire
  menus, actions, panels, dialogs, signals, progress, and theme/layout state,
  but they should call into the owning `src/core/`, `src/systems/`, or
  `src/adapters/` module for reusable behavior.
- Do not add parsing, import/export decisions, resource placement, transform
  algorithms, model composition, validation, renderer residency, or workflow
  policy directly to `src/gui/windows/*`, `src/gui/panels/*`, or
  `src/gui/viewports/*`. Add that code to the matching subsystem and keep the
  UI layer thin.
- Keep workflow-specific controls inside their owning window or panel. For
  example, retarget mode, source/target animation choices, output animation
  naming, and retarget readiness belong in the Animation Retargeting Workbench,
  not the main viewport header or command bar.
- The main window may provide shared services such as `ProjectManager`,
  current scene/model access, game-library rows, file dialogs, logging,
  theme/layout registration, and command routing, but it should not display
  persistent controls for a workflow-specific mode unless that workflow is the
  main viewport itself.
- Shared architecture such as `GhostRiggerProject`, `ResourceAddress`,
  `GameResourceProvider`, `ValidationBus`, and `ExportJob` should stay headless
  or service-oriented. UI code should consume those services through the
  appropriate studio/window boundary rather than bypassing the owning module.
- When roadmap work begins, include a module-boundary checkpoint: owning
  studio/window, user task, source/target resource type, validation/export
  gates, and what must remain outside the slice.

## Theme and layout system

- Do not hardcode new UI colours. Add or consume tokens through `src/gui/libtheme/` and the active `ThemeManager`.
- Do not hardcode major GUI sizes, splitter proportions, or toolbar density. Add or consume layout metrics through `LayoutManager` and XML files in `config/themes/layouts/`.
- The Matrix look is a selectable XML theme (`config/themes/themes/matrix.xml`), not a global style constant.
- New GUI modules should be theme-aware: use application stylesheet tokens where possible, and add an `apply_ghost_theme(theme)` hook for custom painting.
- New standalone windows and major dock panels should also expose `apply_ghost_layout(layout)` when they own splitter sizes, toolbar density, row heights, or fixed control sizes.
- New panels should have stable layout ids so community layouts can size, hide, or reposition them.
- Standalone windows opened from the main shell must register with the active `ThemeManager` when practical, or receive the current theme/layout from their parent during construction.
- New UI must be checked in Default/native, Matrix, Droid, Dark, Light, and Classic. Classic/Light must not ship low-contrast labels, disabled text, table headers, or input fields.
- Avoid blocking the UI thread during theme application. Use cached stylesheets/icons, debounce hot-reload or settings-triggered apply calls, and never trigger a second full theme apply from a `themeChanged` handler.
- When adding visible UI, update `config/themes/README.md` and `knowledge_base/theme_layout_system.md` if new theme tokens, layout ids, or button modes are introduced.

## Module Editor / KMAP

- KMAP files must be versioned and human-readable.
- Do not store heavy mesh, animation, or texture blobs in `.kmap` unless a future schema explicitly requires it.
- Use stable IDs for KMAP projects, modules, rooms, walkmeshes, textures, materials, blueprints, lights, cameras, and scene objects.
- Preserve source KOTOR module data unless the user explicitly chooses an export/write operation.
- New Module Editor windows and panels must be theme/layout aware and must not hardcode Matrix-only colours or major fixed sizes.
- Store source asset references plus editable scene overrides in KMAP; preserve unknown metadata for forward compatibility.

## KMAX Scene Editor

- Do not treat GhostRigger as a single-model viewer.
- The main viewport must always be scene-based and usable when the scene is empty.
- Do not clear scenes silently; destructive scene actions must be explicit and dirty scenes must prompt to save.
- Double-click model import must respect the user's clear/add/cancel choice.
- `.kmax` files must be versioned, human-readable scene files.
- Do not store huge raw mesh, animation, or texture data in `.kmax` unless a future schema explicitly requires it.
- Preserve stable scene object IDs, source references, transforms, material overrides, and unknown metadata.
- Use `KMaxSceneManager` for active KMAX scene state.
- New viewport systems must support empty scenes and multi-object scenes.
- Do not replace existing viewport, gizmo, renderer, or scene systems when adding viewport tools.
- Pivot tools must integrate with `SceneObjectInstance.transform` and `SceneObjectInstance.pivot`.
- Axis/reference modes must use `TransformReferenceController`.
- New viewport controls must be theme/layout aware.
- Do not silently corrupt object transforms when moving pivots; visible geometry should remain stable for pivot-only edits.
- Preserve `.kmax` compatibility for scenes that do not yet contain pivot data.
