# Qt UI Skill

Use this skill for PySide6/Qt widgets, signals and slots, model/view, actions,
toolbars, dialogs, custom widgets, theme/layout behavior, long-running tasks,
and visible workflow testing.

## Book Grounding

- `Create GUI Applications with Python and Qt6`: signals/slots, widgets, layouts, actions, dialogs, windows, events, styles, palettes, icons, QSS, model/view, custom widgets, threads, timers, and Pythonic PySide6.
- `Rapid GUI Programming with Python and Qt`: dialogs, main windows, layouts, custom widgets, item graphics, model/view, databases, and multithreading.
- `Qt 6 C++ GUI Programming Cookbook`: style sheets, signals/slots, async patterns, property animation, state machines, and custom widgets.
- `Refactoring UI`: hierarchy, spacing, text, color, depth, contrast, and systematized design decisions.

## Workflow

1. Identify the product surface first: Main Viewport/KMAX, Retarget Workbench, Character Studio, Module Studio, Map Studio, Resource Browser, Validation, Export, or Project/session infrastructure.
2. Keep GUI code as presentation and orchestration. Reusable behavior belongs in core/systems/adapters and is called by the widget/window.
3. Prefer Qt-native signals, actions, models, delegates, and timers over ad hoc polling or global state.
4. Put long-running work behind threads, processes, workers, or service calls with progress/error reporting. Never block the UI thread during heavy work.
5. Use model/view for tabular or tree data that can change, be filtered, or be edited. Keep display roles separate from domain data.
6. Use theme and layout managers. Do not hardcode new colors, major sizes, splitter ratios, or Matrix-only assumptions.
7. Design dense workbench UIs with clear hierarchy and spacing. Use labels sparingly; emphasize the value/action, not decorative chrome.
8. Test visible behavior in the real Debug application when the change affects startup, viewport, theme/layout, or workflow.

## GhostRigger Checks

- New visible UI should support Default/native, Matrix, Droid, Dark, Light, and Classic themes.
- Add `apply_ghost_theme(theme)` for custom painting and `apply_ghost_layout(layout)` for owned splitter/toolbar/row sizing.
- Use `src/gui/qt_lib.py` facade routes and grouped GUI folders. Do not revive Tk modules or root-level GUI shims.
- For frontend-like UI changes in this desktop app, visual testing is required; backend probes do not count.

## Failure Patterns

- UI freezes during import/export: blocking work ran on the main thread.
- Table/tree loses edits or sorting: domain state and view roles are mixed.
- Theme breaks in Light/Classic: hardcoded color or low-contrast disabled/header/input styling.
- Widget grows into business logic: extract service/core function and leave only wiring.
- Signal fires twice: check connection lifetime and repeated setup during theme/layout refresh.
