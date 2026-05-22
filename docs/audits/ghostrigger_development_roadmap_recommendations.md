# GhostRigger Development Roadmap Recommendations

Date: 2026-05-22

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

## 8. First 5 Safe Coding Slices

1. `T2301: GhostRiggerProject + ResourceAddress`
   - Add dataclasses and JSON roundtrip tests.
   - No UI migration yet.

2. `T2302: ValidationBus`
   - Add shared issue/report schema and adapters for one existing validator.
   - Start with Retarget Preview and KMAP validator.

3. `T2303: ExportJob`
   - Add staging/promotion helper and migrate retarget preview export first.
   - Keep existing writer gates unchanged.

4. `T2304: GameResourceProvider`
   - Add interface and PyKotor-backed adapter.
   - Start with read-only resource lookup and provenance.

5. `T2305: KMAX/KMAP/Module State Contract`
   - Document and test how KMAX scene objects, KMAP rooms/objects, and hydrated
     module resources refer to each other.

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

Next product slice: KOTOR to KOTOR preview mode.

Flow:

`sample source KOTOR slot -> existing profile/reference/solver path -> preview local override on target -> export through existing verified path`

Do not start KOTOR to Unreal until KOTOR to KOTOR reuses all the same safety
gates.

## 10. Specific First Codex Coding Prompt After Audit

Title: Add GhostRiggerProject session model and resource addresses

Goal:

Add a headless `GhostRiggerProject` data model that can store the shared session
state needed by Character, Retarget, Module, and Map Studio without moving any
existing UI behavior yet.

Suggested files:

- `src/core/project/ghostrigger_project.py`
- `src/core/project/resource_address.py`
- `tests/test_ghostrigger_project_model.py`

Requirements:

- JSON save/load roundtrip;
- resource addresses for KOTOR installation resources, local files, generated
  outputs, KMAP/KMAX objects, and retarget profiles;
- no embedded proprietary game asset bytes;
- migration/version field;
- validation-friendly stable ids;
- no writer calls;
- no UI refactor in this slice.

Acceptance:

- new project model roundtrips sample Character, Retarget, Module, and Map
  references;
- existing retarget/module/character tests continue to pass;
- docs show how existing state islands will migrate gradually.
