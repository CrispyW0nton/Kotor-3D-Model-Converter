# GhostRigger Development Roadmap Recommendations

Date: 2026-05-23

## 1. Recommended Architecture Target

GhostRigger should become a four-studio suite over shared headless services:

1. Character Studio: import, fit, rig, skin, preview, export KOTOR-compatible
   characters.
2. Retarget Studio: retarget KOTOR to KOTOR, KOTOR to Unreal, and Unreal to
   KOTOR.
3. Module Studio: hydrate, inspect, edit, validate, and save module resources.
4. Map Studio: build layouts, place objects, author scenarios, and package
   installable module outputs.

Every studio should use the same lifecycle:

`load/import -> normalize -> author -> validate -> preview -> export/stage -> verify`

No UI button should call a writer directly without validation and an export
transaction layer.

## 2. Proposed `GhostRiggerProject`

Add a suite-level project/session model.

Suggested responsibilities:

- game installation references;
- active KMAX scene and KMAP projects;
- loaded target/source KOTOR models;
- imported source meshes and animation clips;
- retarget profiles and output naming;
- hydrated module resource addresses;
- validation reports;
- preview scene state;
- export candidates and manifests.

The project should store references and metadata, not heavy raw game assets by
default.

Initial coding slice:

`T2301: Add GhostRiggerProject dataclasses and JSON save/load with resource addresses.`

## 3. Proposed `GameResourceProvider`

Add one resource provider interface for:

- KEY/BIF/RIM/ERF/MOD lookup;
- Override and custom module priority;
- resource address normalization;
- PyKotor-backed typed resource loading where possible;
- source provenance for validation and export manifests.

This should reduce duplicate resource plumbing between MDL loading, Module
Studio, Map Studio, MCP tools, and Character Studio.

## 4. Proposed `PreviewScene`

Unify preview state so Character, Retarget, Module, and Map Studio can share:

- active model/scene;
- local animation overrides;
- camera and overlays;
- selected object/node/resource;
- validation badges;
- screenshot/capture hooks;
- visual QA state.

Retarget preview already has a good in-memory local override pattern. Promote
that concept into the shared preview layer.

## 5. Proposed `ValidationBus`

Add a shared validation report model:

| Field | Purpose |
|---|---|
| `severity` | info, warning, error, blocking |
| `subsystem` | character, retarget, module, map, script, export |
| `target` | resource address or project object id |
| `code` | stable issue id |
| `message` | user-facing text |
| `details` | structured debug data |
| `fix_hint` | optional recommendation |
| `navigation` | UI route to select affected object/field |

Subsystem validators should publish to the bus; UI panels should subscribe or
render snapshots.

## 6. Proposed `ExportJob`

Add a transaction helper used by all writers:

1. preflight and collect blocking issues;
2. write to temp/staging;
3. run readback/semantic validation;
4. write manifest;
5. promote to final destination;
6. optionally create backup;
7. on failure, leave no partial final output.

This should wrap retarget MDL/MDX export, Character Studio MDL/MDX export,
module save, custom module package, FBX export, and future Patch Manager staging.

## 7. Proposed Module / Map / Scenario Workspace Model

Use three explicit layers:

| Layer | Description | Example |
|---|---|---|
| Hydrated module state | Real KOTOR resources loaded from RIM/MOD/override | ARE/GIT/IFO, UTC/UTP/UTD, DLG/NCS refs |
| Authoring scene state | GhostRigger editable state | KMAP rooms/objects, KMAX scene transforms, sequence data |
| Staged package state | Installable or testable output | `.mod`, Override resources, manifests, Patch Manager package |

Scenario Authoring should build on this model:

- object palette creates GIT instances and templates;
- dialogue/script picker uses resource provider and ScriptService;
- sequence editor binds cameras/actors/animations/scripts;
- package stage writes resources and manifest through `ExportJob`.

## 8. First Safe Coding Slices

Completed:

1. `T2301: GhostRiggerProject + ResourceAddress`
   - Add dataclasses and JSON roundtrip tests.
   - Status: foundation implemented; studio migration remains.

2. `T2302: ValidationBus`
   - Add shared issue/report schema and adapters for one existing validator.
   - Status: foundation implemented; Qt issue model/panel remains.

3. `T2303: ExportJob`
   - Add staging/promotion helper and migrate retarget preview export first.
   - Status: foundation implemented; non-retarget exports remain.

4. `T2304: GameResourceProvider`
   - Add interface and PyKotor-backed adapter.
   - Start with read-only resource lookup and provenance.
   - Status: foundation implemented; studio migration remains.

Next:

5. `T2305: Provider-backed resource browser models`
   - Add Qt models/proxy filtering for provider results.
   - Rows carry `ResourceAddress` and exact resref/restype casing.

6. `T2306: ValidationBus issue model/panel`
   - Add a model/view validation issue surface.
   - Filter by severity/subsystem/source and preserve navigation targets.

7. `T2307: Undo command foundation`
   - Add undoable edit commands before broad Module/Map save workflows.

8. `T2308: Shared job/progress service bridge`
   - Add progress/cancel/result wrappers for scans, imports, validators,
     exports, and external `QProcess` tools.

## 9. Best Next Product Slices

### Character Builder

Next product slice: `NativeSkeletonSnapshot`.

Why: imported meshes can only become game-safe characters if export preserves
the base KOTOR node hierarchy, names, hooks, skin metadata, and supermodel
relationship.

### Module Editor

Next product slice: hydrate/edit/save one safe GIT object field through the Qt
Module Editor with dirty-state tracking and reload verification.

Why: this proves the user-facing editor, typed data, save pipeline, and
validation can cooperate.

### Map Builder

Next product slice: KMAP object placement palette backed by Module Studio
template types.

Why: Taris/Sith Base style scenario authoring needs placed creatures,
waypoints, triggers, doors, and placeables before cutscene logic can be useful.

### Retarget Workbench

Next product slice: named retarget quality/correction mode plus KOTOR to Unreal
contract.

Why: Unreal to KOTOR and KOTOR to KOTOR are now preview/export candidates. The
remaining retarget risk is quality/game-tested confidence and the pending
KOTOR-to-Unreal exporter.

## 10. Specific First Codex Coding Prompt After Audit

Title: Add read-only GameResourceProvider foundation

Goal:

Add one resource provider interface for KOTOR game resources, module resources,
Override/project layers, local files, and generated outputs.

Suggested files:

- `src/core/resources/game_resource_provider.py`
- `src/core/resources/resource_result.py`
- `tests/test_game_resource_provider.py`

Requirements:

- resolve `ResourceAddress` values read-only;
- preserve resref/restype/game/module/layer/provenance;
- fake provider tests first;
- PyKotor-backed adapter if practical;
- no save/write behavior;
- no proprietary bytes committed.

Acceptance:

- provider returns typed metadata and source provenance;
- duplicate/shadowed resources produce warnings;
- future Qt resource models can consume provider result DTOs.
