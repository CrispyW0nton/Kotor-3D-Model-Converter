# Coding Books Second-Pass Findings

Date: 2026-05-23

Purpose: capture what the second sweep found beyond the first knowledge-base
pass. The main direction did not change, but several implementation details are
now explicit enough to guide future GhostRigger coding.

Books re-scanned:

- Lee Zhi Eng, *Qt 6 C++ GUI Programming Cookbook*, 3rd ed.
- Mark Summerfield, *Rapid GUI Programming with Python and Qt*
- Martin Fitzpatrick, *Create GUI Applications with Python and Qt6*
- Steve Schoger and Adam Wathan, *Refactoring UI*
- Harry Percival and Bob Gregory, *Architecture Patterns with Python*
- Robert C. Martin, *Clean Architecture*

## What Was Missing From The First Pass

### Qt/PySide6 Implementation Details

The first pass captured actions, model/view, undo, and threading. The second
pass adds these concrete GhostRigger implications:

| Topic | GhostRigger implication |
|---|---|
| `QSortFilterProxyModel` | Validation issues, resource browsers, and object outliners should filter/sort through proxy models instead of rebuilding lists. |
| `QDataWidgetMapper` | GFF/template property inspectors can bind selected model rows to form fields when the model is stable. Use carefully with undo commands. |
| `QFileSystemModel` | Good for local project/import folders, not for KOTOR archive resources. Archive resources need a custom model backed by `GameResourceProvider`. |
| `QTreeView` / `QTableView` | Natural surfaces for module resource trees, KMAP/KMAX outliners, validation panels, and animation slot lists. |
| `QDockWidget` / `QSplitter` | Better fit for multi-panel modding workbenches than stacking everything into the main window. Must use layout tokens. |
| `QSettings` | Store user preferences, recent projects, theme/layout choice, and configured game installs. Do not store project content there. |
| `QProcess` | Use for external script compilers, optional validation tools, and subprocess bridges. Wrap it in a service/adapter, not widget code. |
| `QProgressDialog` / progress model | Long imports/exports/scans need progress and cancel state. Prefer a job model that can feed status bar and dialogs. |
| `QThreadPool` / `QRunnable` | Useful for short background tasks such as resource scanning, texture previews, and validation sweeps. Larger workflows should still report typed results. |
| Validators | Resource names, custom animation names, module IDs, and output paths should be validated at input time and at service preflight. |
| Drag/drop | Dragging resources into a scene/outliner should create commands with explicit resource addresses, not raw file paths. |

### Clean Architecture Details

The first pass covered dependency inversion and service boundaries. The second
pass reinforces:

- Use a message/event bus concept only where it clarifies cross-workflow state.
  GhostRigger already has `ValidationBus`; a future project event log can be
  smaller and more domain-specific.
- `ExportJob` is the repository/unit-of-work analogue for writes. It should
  become the only route for multi-file output.
- Keep view models explicit. A view model is not a Qt widget; it is the data the
  widget renders.
- Use case objects should name modder goals: "package module", "export retarget
  preview", "bind imported mesh to native DAG", not "run pipeline".
- Transactions and boundaries matter most where GhostRigger can corrupt files:
  module saves, Override writes, Patch Manager staging, MDL/MDX export.

### Refactoring UI Details

The first pass captured hierarchy and status clarity. The second pass adds:

- Empty states are product functionality. They should tell the modder what to
  load/select next.
- Defaults should be selected intentionally: target game, output path, output
  name mode, validation level, and save/package mode.
- Destructive actions need stronger visual treatment and confirmation, but the
  best safety is still staging/undo/preflight rather than modal spam.
- Dense panels need alignment and rhythm. Avoid random fixed widths; use
  layout metrics and theme tokens.
- Error states should be attached to the workflow object: resource, field,
  node, animation slot, module, or export candidate.

## Additions To Standing Rules

1. New list/tree/table UI must justify why it is not using a Qt model.
2. New editable Module/Map/Scenario data should have an undo command before it
   gets a save/export path.
3. Long-running actions need a job/progress/cancel story before they ship in UI.
4. `QProcess` use must live behind a service bridge, especially for script
   compilers, decompilers, and external validators.
5. User preferences belong in settings; mod state belongs in project files.
6. Every resource browser row should be able to produce a `ResourceAddress`.

## Source Scan Notes

Current source search showed:

- `QAction` is already used broadly in main, module, sequence, and theme editor
  surfaces.
- Real Qt item model classes are not yet prominent in `src`, which confirms the
  next UI infrastructure gap for resources/validation/outliners.
- `QUndoStack` is not yet a central dependency. Character guide and sequence
  systems have custom undo stacks, but Module/Map need a shared command layer.
- `ValidationBus`, `ExportJob`, and `ResourceAddress` exist and should now be
  pulled into more product surfaces.
