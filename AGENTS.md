# GhostRigger Agent Instructions

## YOU HAVE ACCESS TO MCP TOOLS, USE THEM WHEN REQUIRED. 

Before writing or modifying any code that handles MDL loading, vertex transforms, 
textures, skinning, or rendering, FIRST query the MCP tools to get ground-truth data 
from the actual game files. Do not guess. Do not assume based on code comments.

## The GhostRigger GUI does NOT need to be running

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
7. Run the full scan on affected model category to check for regressions

## When running tests:
- `pytest tests/ -x` for quick validation
- `pytest tests/ -m "not slow"` to skip full-scan tests
- `pytest tests/test_mcp_full_scan.py` for the complete 6,078-model validation
- When testing whether application behavior works, show the application on screen
  whenever practical. Visible testing is required for UI, startup, viewport,
  theme/layout, and workflow checks because it also helps agents debug what is
  actually happening in the running app.

## Change log

After any fix or software change is successfully completed, update `CHANGES.md`
with a dated entry. Include the relevant `T###` roadmap task ID when one applies,
a concise summary of the change, the affected files or subsystem, and the
verification performed. Keep entries factual so future agents can avoid repeating
completed work.

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

- `src.gui.qt_lib.rendering.viewport_core` - Tk-free rendering core.
- `src.gui.qt_lib.viewports.qt_viewport` - Qt viewport widgets.
- `src.gui.qt_lib.windows.qt_main_window` - Qt main window entry point.
- `src.gui.qt_lib.<category>.<module>` - canonical Qt GUI import route.

Do not add `from .viewport import ...` anywhere; that shim no longer exists.
Import `FrameRenderer`, `ArcBallCamera`, `_load_tpc_bytes`, `_is_tpc_data`,
`_clean_tex_name`, etc. through `src.gui.qt_lib.rendering.viewport_core`.

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
