# Tool Belt Skill

Use this before changing Map Studio toolbars, modeling palettes, command belts,
hotkeys, mode buttons, favorites, presets, or user-customizable tool layouts.

Sources: Qt action/model-view/undo guidance from Fitzpatrick, Summerfield, and
Lee; Maya-style workflow lessons from O'Hailey; performance and interaction
discipline from Hayes, Marschner/Shirley, and Xu.

## Working Rules

- Treat every visible tool as an action with a stable command key, label,
  shortcut, tooltip, icon, enabled state, and owning service/API.
- The tool belt is a presentation surface. It may arrange, filter, favorite,
  and invoke commands; it must not own mesh math, KMAP mutations, validation
  policy, or export decisions.
- Support customization through stored preferences, not hardcoded per-window
  button edits. Presets should round-trip through KMAP/KMAX or user config when
  the layout is project/user state.
- Keep modes visually obvious: Object, Vertex, Edge, Face, Terrain, Walkmesh,
  Placement, Lighting, Validation, and Export should not feel like the same
  button family.
- Avoid one giant toolbar. Use grouped belts: primitive/modeling, component
  edit, snap/pivot, terrain brush, placement, validation/export, and viewport
  display.
- Tool availability must follow selection and readiness state. Disabled tools
  should explain why in status text or tooltip.
- Prefer Qt actions and model/view-backed palettes so menus, toolbars, hotkeys,
  command search, and customization all invoke the same command definitions.
- Keep workflow-specific tool belts inside the owning studio. Map Studio tools
  stay in the Level Editor / Map Studio; Retarget and Character Builder controls
  stay in their own windows.

## GhostRigger Applications

- Map Studio's modeling belt should expose primitives, extrusion, bevel, inset,
  split, fill, triangulate, bridge, boolean, separate/combine, snap, pivot, and
  terrain brushes as stable action IDs.
- User preferences should be able to hide tools a modder does not use, pin
  favorites, and switch between compact, Maya-like, terrain, and validation
  presets.
- Command search should route to actions, not duplicate button handlers.
- Every action that mutates KMAP state must create or reuse a command object so
  undo/redo and readiness invalidation stay consistent.
- Tooltips should use KOTOR words when relevant: WOK, MDL/MDX, LYT, VIS, PTH,
  GIT, ARE, IFO, resref, Override, and `.mod`.

## Preflight Checklist

- What is the stable action key?
- Which studio owns the action?
- Which core/system/adapter API does the action call?
- What selection or readiness state enables it?
- Is the operation live-preview, commit, validation, or export?
- Does it create undo/redo history?
- Does it invalidate MDL/MDX/WOK/LYT/VIS/PTH/.mod readiness?
- Is the tool visible in the right preset and hidden from unrelated windows?

## Tests To Prefer

- Source-contract tests for action IDs, object names, and tool-belt preference
  serialization.
- Controller tests that assert disabled reasons before UI display tests.
- Focused GUI tests that click an action and verify it calls the owning service.
- Regression tests for saving/restoring custom tool-belt presets.
