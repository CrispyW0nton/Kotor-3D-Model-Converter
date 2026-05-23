# Python and Clean Architecture for GhostRigger

Date: 2026-05-23

Sources reviewed:

- Harry Percival and Bob Gregory, *Architecture Patterns with Python*
- Robert C. Martin, *Clean Architecture*
- Official Qt docs listed in `qt_python_ui_architecture_for_ghostrigger.md`
- Existing GhostRigger architecture docs and roadmap

This note translates the architecture material into GhostRigger-specific
boundaries. It is a working guide for future implementation decisions.

## Architecture Target

GhostRigger should be organized around use cases, not around widgets or file
formats.

The dependency direction should be:

```text
UI / CLI / MCP / Qt Designer forms
-> controllers / application services
-> domain models and use cases
-> ports/interfaces
-> adapters for PyKotor, filesystem, MDL writer, FBX importer, Ghidra, Qt
```

The UI can know about core DTOs. Core services must not know about Qt widgets.

## Current Good Foundations

GhostRigger already has the right seeds:

- `GhostRiggerProject` and `ResourceAddress` give the suite a session spine.
- `ValidationBus` gives one diagnostic shape across studios.
- `ExportJob` gives a staged, verified write transaction.
- Retarget preview/export already keeps solver, preview, and writer concerns
  separate.
- KMAP/KMAX use human-readable scene/project files.
- Module hydration/save services are headless and testable.

These should become the default pattern for every studio.

## Recommended Layer Names

| Layer | Responsibility | Examples |
|---|---|---|
| Domain | KOTOR/Aurora facts and project state. | `ResourceAddress`, animation blocks, KMAP/KMAX entities, retarget profiles. |
| Application service | One user goal, headless. | sample KOTOR animation, build retarget preview, export preview, hydrate module, package map. |
| Port/interface | Boundary to volatile details. | `GameResourceProvider`, script compiler bridge, file writer, viewport adapter. |
| Adapter | Concrete implementation of a port. | PyKotor resource adapter, MDL writer, FBX importer, Ghidra MCP client, Qt viewport adapter. |
| Presentation | Qt actions, panels, view-models, Qt models. | `RetargetWorkbenchController`, future validation issue model. |

## Service Layer Rules

Every non-trivial command should have a headless service function or class:

```text
Retarget:
  build preview, export last preview, sample source animation

Character:
  import mesh, choose native KOTOR DAG, fit guides, bind mesh, validate export

Module:
  hydrate module, edit GFF field, validate refs, save/export package

Map:
  place object, snap room, edit VIS, validate WOK seams, package module
```

Services return result objects with validation/warnings. They do not open
dialogs, mutate widgets, or depend on `QMainWindow`.

## Repository and Unit of Work, GhostRigger Version

The book patterns around repositories and units of work map cleanly to KOTOR
resources:

- Repository equivalent: `GameResourceProvider` should load resources by
  `ResourceAddress` and report provenance/layer.
- Unit of work equivalent: `ExportJob` should stage a set of outputs, verify
  them, and promote together.
- Domain events equivalent: `ValidationBus` and future project event log can
  announce "resource changed", "preview stale", "export candidate verified".

Do not invent separate save pipelines for every studio. They should share
preflight, staging, verification, manifest, and rollback behavior.

## Dependency Inversion Rules

Core use cases should depend on abstractions when the dependency is volatile:

- KOTOR installation/archive access: use a provider interface.
- Script compile/decompile: use a `ScriptService` bridge, not hardcoded process
  calls from widgets.
- Ghidra/engine analysis: local diagnostic adapter only, never production UI.
- Qt viewport: core preview returns data; a viewport adapter applies it.
- Filesystem writes: use `ExportJob`.

It is fine for core KOTOR code to depend on stable value types and dataclasses.
It is not fine for core export logic to depend on a button, status label, or
file dialog.

## Data Ownership Rules

GhostRigger should be strict about what is source, preview, and output:

```text
Source asset:
  original KOTOR model/module/resource/imported mesh/FBX

Authoring state:
  GhostRiggerProject, KMAP, KMAX, retarget profile, guide overrides

Preview state:
  in-memory model copy, local animation override, viewport selection

Export candidate:
  staged files, manifest, validation report, readback proof
```

Never mutate source assets during preview. Never call an export "game-ready"
until it has passed readback and the applicable in-game/Patch Manager test.

## GhostRigger Use-Case Templates

### Retarget Preview

```text
input DTO:
  source, target, profile, output naming
service:
  resolve names, sample/evaluate, solve, audit
output DTO:
  preview model, animation block, audit report, warnings
writer:
  none
```

### Retarget Export

```text
input DTO:
  last preview result, original target model, output paths
service:
  preflight, write staged MDL/MDX, verify readback, promote
output DTO:
  ExportJobResult, manifest, verification status
writer:
  only inside ExportJob writer callback
```

### Module Edit

```text
input DTO:
  ResourceAddress, object id, field path, new value
service:
  validate type/reference, apply command to authoring state
output DTO:
  validation report, dirty-state event
writer:
  none until save/export
```

### Map Package

```text
input DTO:
  KMAP/KMAX/scenario workspace, target module id
service:
  build resources, validate refs/walkmesh/layout, stage package
output DTO:
  ExportJobResult, manifest
```

## Tests as Architecture

The architecture books both reinforce that tests should pin behavior at the
use-case boundary. For GhostRigger, prioritize:

- contract tests for `GameResourceProvider`;
- service tests with fake providers/adapters;
- golden/readback tests at MDL/MDX, MOD, FBX boundaries;
- UI controller tests that monkeypatch services and assert routing/status;
- no-widget core tests for every new use case;
- in-game/Patch Manager tests as explicit opt-in smoke checks, not normal unit
  tests.

## Near-Term Architecture Rules

1. New code that writes files must use `ExportJob`.
2. New code that reports user-facing diagnostics must emit or convert to
   `ValidationReport`.
3. New code that identifies a KOTOR resource should use `ResourceAddress`.
4. Qt code should route through controllers/application services.
5. Module/Map editing should use undoable commands before broad UI save is
   expanded.
6. Retarget, Character, Module, and Map workflows should be gradually attached
   to `GhostRiggerProject`.
7. KOTOR-specific byte and node casing rules beat generic engine assumptions.
