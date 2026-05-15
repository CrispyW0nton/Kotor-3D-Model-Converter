# GhostRigger Agent Instructions

## You have MCP tools. Use them.

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

All UI work now happens under `src/gui/qt_*.py` and `src/gui/viewport_core.py`.
`tests/test_qt_only_imports.py` includes guards (`test_legacy_tk_modules_are_deleted`,
`test_no_gui_module_imports_tkinter`) that fail CI if any of the eight files
return or if a new file under `src/gui/` imports tkinter.

## Qt imports

- `src.gui.viewport_core` — Tk-free rendering core. Use everywhere.
- `src.gui.qt_*`          — the canonical Qt UI subtree.

Do not add `from .viewport import ...` anywhere; that shim no longer exists.
Import `FrameRenderer`, `ArcBallCamera`, `_load_tpc_bytes`, `_is_tpc_data`,
`_clean_tex_name`, etc. from `src.gui.viewport_core` directly.
