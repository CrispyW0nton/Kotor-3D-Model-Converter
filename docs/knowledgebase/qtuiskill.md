# Qt UI Skill

Use this before changing Qt windows, panels, actions, model/view data, toolbar
belts, theme/layout handling, threading, or workflow readiness.

Sources: Fitzpatrick PySide6, Summerfield PyQt, Lee Qt 6 cookbook, official Qt
docs referenced in prior notes, GhostRigger Qt architecture crosswalk.

## Working Rules

- Widgets route commands and display state. They do not own KOTOR parsing,
  export rules, transform math, retargeting, or module validation policy.
- Use `QAction` or command objects for user intent that appears in menus,
  toolbars, context menus, shortcuts, or command belts.
- Use model/view when data must sort, filter, preserve selection, show multiple
  views, or represent hierarchies.
- Long work belongs in jobs/workers, reporting back through signals/results.
- UI readiness is a first-class model: can preview, can export, stale preview,
  missing input, runtime requirements, and game-tested state.
- Theme/layout tokens are mandatory for visible UI. Do not hardcode new color
  palettes or major dimensions.

## GhostRigger Applications

- Workflow-specific controls stay inside the owning studio/window.
- Main viewport can host shared scene services but not persistent Retarget,
  Character Builder, or Map Studio controls.
- Map Studio tool belts should be customizable, stable-object-named, and backed
  by core tool policy.
- Validation and export should surface actionable errors before file writes.

## Preflight Checklist

- Which window/panel owns this workflow?
- Is this a UI-only change or reusable policy?
- Is the user command represented as a stable action?
- Are object names stable for tests?
- Does the UI update when readiness, selection, or project state changes?
- Does this block the GUI thread?
- Does it respect Default/Matrix/Droid/Dark/Light/Classic themes?

## Tests To Prefer

- Source-contract tests for object names, actions, signal wiring.
- Core tests for policy/data behavior without Qt.
- Visible app testing for theme, viewport, startup, and workflow behavior.
