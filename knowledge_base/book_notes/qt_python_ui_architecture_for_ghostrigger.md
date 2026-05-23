# Qt and Python GUI Architecture for GhostRigger

Date: 2026-05-23

Sources reviewed:

- Lee Zhi Eng, *Qt 6 C++ GUI Programming Cookbook*, 3rd ed.
- Mark Summerfield, *Rapid GUI Programming with Python and Qt*
- Martin Fitzpatrick, *Create GUI Applications with Python and Qt6*
- Steve Schoger and Adam Wathan, *Refactoring UI*
- Official Qt for Python docs: https://doc.qt.io/qtforpython-6/
- Official Qt Model/View docs: https://doc.qt.io/qt-6/model-view-programming.html
- Official QAction docs: https://doc.qt.io/qt-6/qaction.html
- Official Qt Designer manual: https://doc.qt.io/qt-6/qtdesigner-manual.html
- Official Qt Undo Framework docs: https://doc.qt.io/qt-6/qundo.html
- Official Qt threading docs: https://doc.qt.io/qt-6/threads.html

This note converts the GUI material into GhostRigger-specific rules. It is not
a substitute for the books or Qt docs and intentionally avoids copying long
source passages.

## Core Rule

GhostRigger widgets should express state and route commands. They should not
own KOTOR business rules, MDL/MDX export rules, retarget math, module save
rules, or project persistence.

The preferred flow is:

```text
QAction / widget event
-> Qt controller or view-model
-> headless core service
-> ValidationReport / ExportJobResult / PreviewResult
-> Qt model/view or status widget update
```

## Qt Pattern Decisions

| Pattern | GhostRigger rule | Where to apply |
|---|---|---|
| `QAction` | Create one command object per user intent and reuse it in menu, toolbar, shortcut, and context menus. | Retarget preview/export, module save, map package, validation run, import/export commands. |
| Model/view | Use Qt models for trees, tables, validation lists, resource browsers, object outliners, module contents, and timeline data. | Module resource tree, KMAP/KMAX outliner, ValidationBus issue panel, asset browser, sequence editor. |
| Designer forms | Use `.ui` forms for stable forms/dialogs, but keep behavior in controllers/presenters. | Object property editors, export dialogs, settings panels. |
| Undo framework | All destructive authoring edits should go through command objects before save/export is enabled. | Module object edits, map placement, KMAX transforms, walkmesh face edits, sequence keyframes. |
| Threads/jobs | Long work must run outside the GUI thread and report back via signals/results. | FBX import, KOTOR resource scans, module hydration, MDL export, validation sweeps, full scans. |
| Signals/slots | Use for UI event routing and async completion, not for hidden business logic chains. | Controller-to-view notifications, job progress, selection changes. |

## Model/View Guidance

Use `QAbstractItemModel` or a typed adapter when the data is hierarchical or
shared by multiple views. GhostRigger has several natural model/view targets:

- game install resource browser: archive/layer/module/resref/restype tree;
- module contents: ARE/GIT/IFO/templates/scripts/dialogs/walkmesh grouped by type;
- KMAP/KMAX outliner: rooms, objects, lights, cameras, sequences;
- ValidationBus issues: severity, subsystem, code, target, fix hint;
- Retarget Workbench required inputs/status: one model feeding status labels,
  details panel, and eventual checklist;
- sequence timeline: tracks, clips, keys, events.

Do not back these with ad hoc widget lists once the data needs sorting,
filtering, selection preservation, drag/drop, or more than one view.

## QAction Guidance

Qt actions are the right abstraction for commands that appear in more than one
place. GhostRigger should gradually move from button-local lambdas to command
registries:

```text
preview_retarget_action
export_retarget_preview_action
validate_project_action
save_module_action
package_module_action
undo_action
redo_action
```

Every action should have:

- stable object name for tests;
- enabled state controlled by readiness/preflight, not by widget guesswork;
- user-facing status/error text when disabled if the workflow is complex;
- no direct writer call from the QAction handler.

## Undo Framework Guidance

Module Studio and Map Studio should not treat edits as direct mutations plus a
later save. They need undoable commands before they feel safe to modders.

Use command objects for:

- moving a placed object;
- changing a creature/template reference;
- editing a GFF field;
- painting a walkmesh face material;
- adding/removing VIS links;
- snapping a room;
- editing a sequence key.

The document/model is only modified through commands. Save actions become
enabled through the clean/dirty state. ExportJob still handles file writes.

## Threading and Job Guidance

Qt docs emphasize thread support and queued communication so time-consuming work
does not freeze the UI. GhostRigger should follow this split:

```text
GUI thread:
  update widgets, apply themes/layouts, mutate viewport/widgets

Worker/job:
  import FBX/glTF/OBJ
  scan KOTOR archives
  hydrate modules
  run validation sweeps
  export MDL/MDX/FBX/MOD packages to staging
```

Do not mutate Qt widgets from workers. Workers return immutable or owned result
objects. The UI then applies results on the main thread.

## Designer Guidance

Qt Designer is useful for stable forms, dialogs, and inspectors. It is not a
reason to move product logic into generated UI classes.

Good candidates:

- game install settings dialog;
- export options dialog;
- GFF object editor form shells;
- retarget profile metadata panel;
- project settings;
- validation filter panel.

Poor candidates:

- renderer/viewport internals;
- retarget solver logic;
- module save pipeline;
- dynamic resource-tree logic.

## Refactoring UI Guidance for Modder Tools

GhostRigger is not a marketing page. It is a dense creative tool. UI polish
means clarity, not decoration.

Use these rules:

- start every panel with the actual work object: module, model, source clip,
  target model, slot/custom name, export target;
- show mode, selected source, selected target, output, and runtime safety before
  buttons;
- prefer compact hierarchy over oversized cards;
- reserve bright accent color for active mode, selected object, blocking issue,
  or primary action;
- use spacing and grouping to show relationships instead of borders everywhere;
- keep helper text actionable: "Choose a source KOTOR animation" beats
  "Input missing";
- make empty states useful: tell the modder what to load next;
- never hide vanilla-safe vs custom-patch-only status until export time.

## GhostRigger UI Anti-Patterns

Avoid:

- business logic in `qt_main_window.py`;
- widget code importing MDL writers directly;
- resource browsers backed by widget item strings only;
- save/export actions that bypass ValidationBus or ExportJob;
- long operations in click handlers;
- one-off status strings that cannot feed tests or a future issue panel;
- lowercasing or normalizing Aurora node names for display and then reusing the
  display string for export;
- module/map edits without undo/dirty-state semantics.

## Coding Checklist Before UI Changes

Before adding or changing a Qt workflow:

1. Identify the user-facing command and create/reuse a `QAction`.
2. Put workflow state in a controller/view-model, not scattered widgets.
3. If the data is list/tree/table-like, define a model or model-ready DTO.
4. Route validation through `ValidationBus` or a convertible report.
5. Route file writes through `ExportJob`.
6. Keep workers off the GUI thread for slow work.
7. Add stable object names for testable controls.
8. Use theme/layout tokens, not hardcoded product colors or major sizes.
9. Write the modder-facing status in terms of KOTOR concepts: resref, module,
   Override, MDL/MDX, animation slot, custom patch, supermodel.
