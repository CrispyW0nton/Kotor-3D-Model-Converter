# GhostRigger Roadmap Adjustments

Date: 2026-05-23

This document updates the roadmap using the new coding knowledge base and the
current state after `T2301`, `T2302`, `T2303`, `T2401`, `T2403`, and `T2405`.

## 1. Roadmap Position

Completed foundations:

- `T2301`: `GhostRiggerProject` and `ResourceAddress`
- `T2302`: `ValidationBus`
- `T2303`: `ExportJob`
- `T2401`: tri-mode Retarget Workbench plus custom KOTOR output naming
- `T2403`: `KOTOR to KOTOR` preview/export mode
- `T2405`: Retarget Workbench readiness/status layer

The architecture foundation is now ahead of several product surfaces. The next
work should use it instead of bypassing it.

Third-pass scope sanity adds one more rule: no feature should enter the roadmap
unless it names its owning studio, modder task, target resource/object, safety
gates, and capability label.

## 2. Recommended Near-Term Order

### 1. T2304: GameResourceProvider

Why now:

- every studio needs consistent KOTOR resource lookup;
- Module/Map/Character and Retarget currently risk duplicating lookup;
- `ResourceAddress` needs a provider to become more than a DTO.

Acceptance:

- read-only provider interface;
- fake provider tests;
- PyKotor/local loader adapter if practical;
- provenance/layer in results;
- no writer behavior yet.

### 2. T2305: Provider-Backed Resource Browser Models

Why:

- KOTOR modding starts with resources, resrefs, types, modules, and provenance;
- the second book pass reinforced Qt model/view and proxy filtering;
- `QFileSystemModel` is not enough for KEY/BIF/RIM/ERF/MOD/Override resources.

Acceptance:

- `QAbstractItemModel` or typed list/tree models for provider results;
- `QSortFilterProxyModel` filtering by module, restype, layer, and text;
- rows carry `ResourceAddress` and exact resref/restype casing;
- local filesystem imports remain separate from archive-backed game resources.

### 3. T2306: Validation Issue Qt Model and Panel

Why:

- `ValidationBus` exists but modders need one issue surface;
- model/view should be used before issue UIs sprawl.

Acceptance:

- `QAbstractTableModel` or list model for `ValidationReport`;
- filters by severity/subsystem;
- exact target/node casing preserved;
- clicking an issue can later navigate via `ValidationNavigationTarget`.

### 4. T2307: Undo Command Foundation for Authoring

Why:

- Module and Map editors are dangerous without undoable changes;
- Qt Undo Framework maps directly to KMAP/KMAX/GFF field edits.

Acceptance:

- command base/adapters for resource/object edits;
- clean/dirty state;
- tests for undo/redo of a GFF field, KMAP object transform, and VIS link.

### 5. T2308: Shared Job/Progress Service Bridge

Why:

- FBX imports, resource scans, validation sweeps, exports, and external tool
  calls must not block the UI thread;
- the Qt books specifically point to `QThreadPool`, `QRunnable`, `QProcess`,
  and progress/cancel UI as first-class GUI infrastructure.

Acceptance:

- headless job DTO plus Qt adapter;
- progress, cancellation, log messages, and result/error payloads;
- QProcess wrapper for external compilers/validators;
- no direct subprocess launches from widgets.

### 6. T2402 Follow-Up: Retarget Quality Mode Polish

Why:

- PMBAM success involved calibrated segment correction and binary export
  safety. It should become a named, repeatable mode.

Acceptance:

- named solver/profile option;
- test fixture protecting arm/leg segment accuracy;
- no manual-only PMBAM calibration step hidden in docs;
- capability label: "viewport verified" vs "game tested".

### 7. Character Studio Native DAG Lock

Why:

- Character Studio launch depends on native KOTOR hierarchy preservation just
  like retarget export did.

Acceptance:

- `NativeSkeletonSnapshot`;
- imported mesh bind-to-cloned-KOTOR-DAG path;
- MDL/MDX export parity tests for node names, hooks, skin metadata, texture
  casing, bounds, and supermodel.

## 3. Adjustments by Product Pillar

### Retarget Studio

Current status:

- `Unreal to KOTOR`: preview/export candidate.
- `KOTOR to KOTOR`: preview/export candidate.
- `KOTOR to Unreal`: pending.

Adjustment:

- before `KOTOR to Unreal`, stabilize Retarget Workbench UX and PMBAM quality
  modes;
- add a validation issue panel so retarget audit issues are navigable;
- keep export using last preview only.

### Character Studio

Current status:

- UI and workflow pieces are substantial;
- export correctness is not yet proven at the same standard as retarget PMBAM
  animation injection.

Adjustment:

- make native KOTOR DAG preservation the gate before new rigging features;
- use the same byte/case/skin metadata caution learned from PMBAM;
- route export through `ExportJob`.

### Module Studio

Current status:

- strong headless services;
- UI needs safer editing semantics.

Adjustment:

- add GameResourceProvider and QUndo command foundation first;
- distinguish hydrated resources, KMAP authoring, and staged package in UI;
- migrate saves/packages to `ExportJob`.

### Map and Scenario Studio

Current status:

- KMAP/KMAX/LYT/VIS/WOK services exist;
- scenario authoring remains a workflow layer.

Adjustment:

- use QUndo commands for placement/snap/VIS edits;
- use model/view outliners and property inspectors;
- connect scripts/dialogs through a ScriptService bridge rather than copying
  GhostScripter code into the repo.

## 4. Prompt Standard Going Forward

Every future development prompt should include:

```text
Roadmap position:
  milestone/task, user-facing goal, incomplete after this slice

Scope sanity:
  owning studio, KOTOR modder task, target resource/object, capability label

KOTOR modder story:
  what a modder can do, exact UI/workflow, KOTOR terms used

UX acceptance:
  mode/source/target/output visible, vanilla-safe/custom-patch status visible,
  actionable errors

Safety/validation/export gates:
  ValidationBus, ExportJob, no partial writes, exact Aurora casing, MCP ground
  truth where required

Capability honesty:
  working, previewable, export candidate, game-tested
```

Feature parking rule:

```text
If a proposed feature does not clearly serve Character Studio, Retarget Studio,
Module Studio, or Map/Scenario Studio, park it unless it is shared
infrastructure needed by those studios.
```

## 5. First Next Coding Prompt Recommendation

Title: Add read-only GameResourceProvider foundation

Goal:

Create one resource provider interface for KOTOR game resources, local files,
override/module layers, and project-generated resources. It should resolve
`ResourceAddress` values into typed bytes/metadata/provenance without writing.

Why:

This unlocks cleaner Character, Retarget, Module, and Map workflows and reduces
duplicated loader assumptions.

Non-goals:

- no save pipeline migration;
- no Patch Manager install;
- no UI resource browser yet;
- no broad PyKotor code copy.

Acceptance:

- fake provider tests;
- local/KOTOR provider adapter where practical;
- provider result includes address, source layer, bytes or typed object, and
  warnings;
- no secrets or proprietary bytes committed;
- docs update showing how studios should use it.
