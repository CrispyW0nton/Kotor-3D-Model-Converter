# GhostRigger Programming Crosswalk

Date: 2026-05-23

This crosswalk combines the Qt/Python/Clean Architecture/UI references into
one decision guide for GhostRigger development.

## Read Before Coding

| Work area | Required knowledge-base notes |
|---|---|
| Qt panels, dialogs, actions, inspectors | `qt_python_ui_architecture_for_ghostrigger.md` |
| Resource trees, validation tables, property inspectors, long-running Qt actions | `coding_books_second_pass_2026_05_23.md` |
| Product scope, feature ownership, capability honesty | `coding_books_third_pass_scope_sanity_2026_05_23.md` |
| Core services, project state, adapters | `python_clean_architecture_for_ghostrigger.md` |
| Retarget math, transforms, animation fidelity | `dunn_parberry_3d_math_primer_2e.md`, `vince_mathematics_for_computer_graphics_7e.md` |
| Engine/resource/runtime systems | `gregory_game_engine_architecture_4e_vol1.md`, `ghostrigger_engine_crosswalk.md` |
| MDL/MDX crash or binary behavior | `knowledge_base/reference/ghidra_odyssey_mcp.md`, MCP ground truth tools |
| KOTOR resource, module, patching, and MDL source credibility | `knowledge_base/reference/kotor_modding_verified_sources.md` |

## Program-Wide Principles

1. KOTOR correctness is source-of-truth driven.
   Use MCP/PyKotor/Ghidra/game files before changing MDL, skinning, rendering,
   vertex transforms, or texture behavior.

2. UI is a shell over use cases.
   Widgets collect input, show readiness, and route `QAction`s. They do not
   solve retargeting, save modules, or write MDL/MDX directly.

3. Preview is not export.
   Preview may mutate in-memory copies only. Export uses `ExportJob` and
   readback/validation gates.

4. Resource identity must be explicit.
   Use `ResourceAddress` for resref/restype/module/layer/local-file/project
   identity. Avoid raw strings when the string means a KOTOR resource.

5. Diagnostics must be navigable.
   Use `ValidationReport` and exact target metadata. Preserve Aurora node casing.

6. Modder UX must be honest.
   Distinguish working, previewable, export candidate, and game-tested.

7. List and tree UIs need a model/view justification.
   Resource browsers, validation issue tables, module contents, object
   outliners, and scenario lists should use Qt models and proxy filtering unless
   the data is genuinely tiny and static.

8. Authoring edits need undo before broad save/export exposure.
   Module, Map, Scenario, and Character edits should be represented as
   undoable commands before the workflow becomes modder-facing.

9. Every feature needs an owning studio and capability label.
   If a feature cannot say which studio owns it, what KOTOR modder task it
   completes, and whether it is query-only, previewable, export-candidate, or
   game-tested, it should be parked.

## Studio-Specific Rules

### Retarget Studio

- Current working modes: `Unreal to KOTOR`, `KOTOR to KOTOR`.
- Pending mode: `KOTOR to Unreal`.
- Source animation name and target output name are different concepts.
- KOTOR output names are either vanilla slot overrides or custom patch names.
- Export must use the exact last successful preview result.
- Custom patch output is not vanilla-playable unless the runtime patch calls it.

### Character Studio

- Imported FBX/OBJ/glTF meshes must be bound to a native KOTOR/Aurora node DAG.
- Never export an imported UE/generic skeleton as if it were a KOTOR character.
- Preserve hook nodes, supermodel relationship, node names/casing, skin metadata,
  texture casing, and MDX layout where required.
- The next launch-critical architecture is `NativeSkeletonSnapshot` plus
  Character Studio export preflight through ValidationBus/ExportJob.

### Module Studio

- Hydrated module resources, KMAP authoring state, and staged package output are
  separate layers.
- Object edits should become undoable commands before broad save workflows are
  exposed.
- Reference safety is part of save preflight, not an afterthought.
- Use PyKotor/Holocron concepts for resource clarity, but keep GhostRigger's
  authoring scene, validation, and transaction model.

### Map Studio and Scenario Authoring

- KMAX is the editable scene, KMAP is the module/map authoring document, and
  KOTOR resources are the runtime artifacts.
- Object placement, room snapping, VIS, WOK, dialogue/script refs, and package
  output should all converge through `GhostRiggerProject`.
- The user should see whether they are editing a scene object, a module
  resource, or a package candidate.

## UI Language Rules

Use KOTOR modder vocabulary:

- `resref`, `restype`, `module`, `Override`, `MDL/MDX`, `supermodel`,
  `animation slot`, `custom animation patch`, `GIT`, `ARE`, `IFO`, `UTC`,
  `UTP`, `DLG`, `NSS/NCS`, `LYT`, `VIS`, `WOK`.

Avoid vague labels:

- "Asset" when the user needs `resref/restype`.
- "Animation name" when the distinction is source clip, KOTOR slot, or custom
  patch name.
- "Save" when the action stages a package or writes Override candidates.

## Roadmap Checkpoint Template

Every future prompt or slice should include:

```text
Roadmap position:
  milestone/task, user-facing goal, incomplete after this slice

Scope sanity:
  owning studio, modder task, target resource/object, capability label

KOTOR modder story:
  what the modder can do, what UI they see, what KOTOR terms appear

UX acceptance:
  mode/source/target/output/runtime safety visible, errors actionable

Safety gates:
  ValidationBus, ExportJob, no partial writes, exact casing/resource identity

Capability honesty:
  working vs previewable vs export candidate vs game-tested
```

## "Stop and Audit" Triggers

Pause and re-check architecture when:

- a widget needs to know binary MDL offsets;
- a save/export bypasses `ExportJob`;
- a validation message cannot be mapped to a `ResourceAddress` or node/object;
- two modules implement the same resource lookup differently;
- a workflow needs background loading but runs in a click handler;
- a resource tree, validation list, or property inspector is built by manually
  rebuilding widget items instead of a model/proxy;
- a Module/Map/Scenario edit cannot be undone;
- a subprocess or external compiler is launched directly from a widget instead
  of a service/adapter;
- a doc or UI claims "game-ready" without readback and in-game proof;
- a KOTOR output path lowercases or normalizes names that came from game files.
