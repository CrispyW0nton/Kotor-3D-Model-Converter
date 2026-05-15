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

## FROZEN Tk modules (read-only — scheduled for deletion in M3 / T302)

The following files carry a FROZEN banner at the top and must NOT receive
new features or business-logic changes. They are kept as references until
the Qt branch is feature-complete:

- `src/gui/main_window.py`              — legacy Tk main window
- `src/gui/character_builder_window.py` — legacy Tk Character Builder
- `src/gui/blueprint_editor.py`         — legacy Tk UTC/UTP/UTD editor
- `src/gui/modular_panel.py`            — legacy Tk module-editor panel
- `src/gui/matrix_background.py`        — legacy Tk MP4 background engine
- `src/gui/icon_manager.py`             — legacy Tk PhotoImage icon loader
- `src/gui/viewport_tk.py`              — Tk widgets split out of viewport.py (T001)

All new UI work happens under `src/gui/qt_*.py` and `src/gui/viewport_core.py`.

## Qt vs Tk imports

- `src.gui.viewport_core` — Tk-free rendering core. Safe to import under Qt.
- `src.gui.viewport_tk`   — Tk widgets only. Imports `tkinter`.
- `src.gui.viewport`      — backward-compat shim re-exporting both.

Qt code (`qt_*.py`) MUST import from `viewport_core` directly. Do not add
new `from .viewport import ...` lines anywhere.
