# GhostRigger Program Architecture Audit

Date: 2026-05-23
Branch: `qt-ghostrigger`
Scope: coding knowledge-base refresh plus current program sanity audit

## 1. Executive Summary

GhostRigger is in a strong but sensitive phase. The retargeting stack is now a
real product surface, and the suite has the beginning of the shared architecture
it needed: `GhostRiggerProject`, `ResourceAddress`, `ValidationBus`, and
`ExportJob`.

The next risk is product spread. Character, Retarget, Module, Map, Sequence,
and Patch Manager workflows can now grow quickly, but they must not grow as
separate state islands. The books and current Qt docs all point toward the same
answer: thin UI, explicit command/use-case boundaries, model/view for complex
data, undoable edits for authoring, background jobs for slow operations, and
transactional export.

Third-pass scope sanity: GhostRigger should be a KOTOR/Odyssey modding suite,
not a generic DCC tool or engine editor. New work should serve Character,
Retarget, Module, or Map/Scenario Studio directly, or be shared infrastructure
those studios need.

## 2. Current Capability Snapshot

| Area | Status | Notes |
|---|---|---|
| Retarget `Unreal to KOTOR` | Working preview/export candidate | Supports custom output names and staged export. Game readiness still depends on the specific target model/export path and live test. |
| Retarget `KOTOR to KOTOR` | Working preview/export candidate | Samples source KOTOR animation through evaluator and uses existing preview/export gates. |
| Retarget `KOTOR to Unreal` | Pending | Mode exists but exporter contract is not implemented. |
| Retarget Workbench UX | Improved | Readiness/status layer now explains mode, source, target, output, runtime safety, preview/export readiness. |
| Project/session model | Working foundation | `GhostRiggerProject` exists but studios are not fully migrated to it. |
| ValidationBus | Working foundation | Core schema and adapters exist; UI issue panel remains pending. |
| ExportJob | Working foundation | Retarget preview export uses staged transaction. Character/Module/Map exports still need migration. |
| Character Studio | Partial | Strong workflow pieces, but game-safe native KOTOR DAG export remains launch-critical. |
| Module Studio | Partial/strong backend | Hydration, inspection, save, reference safety, WOK tooling exist. Needs unified project/undo/export UX. |
| Map Studio | Partial/strong backend | KMAP/KMAX, LYT/VIS/WOK and package services exist. Needs scenario workflow and authoring cohesion. |
| Sequence/Cutscene | Partial | UI and track foundations exist. Needs binding to module/map/script resource model. |

## 3. Architecture Strengths

- The latest retarget work follows the desired architecture: source sampler,
  solver, preview, naming, export, and UI readiness are separate.
- Retarget export no longer writes directly; it uses `ExportJob`.
- Validation has a shared shape and preserves exact Aurora node casing.
- Project state has a JSON-friendly model that avoids embedding proprietary
  asset bytes.
- Module and Map backends are mostly headless and testable.
- Qt/Tk boundary is guarded; new GUI work is Qt-only.
- Ghidra/engine analysis is documented as local diagnostic tooling, not a
  committed secret-bearing dependency.

## 4. Architecture Risks

| Risk | Impact | Recommended correction |
|---|---|---|
| `qt_main_window.py` remains a broad orchestrator | UI changes may accrete business logic | Continue extracting controllers/view-models and QAction registry responsibilities. |
| Complex lists/trees still risk widget-item implementations | Sorting/filtering/selection can become fragile | Add Qt models for resources, validation issues, outliner, and workbench readiness/details. |
| Module/Map edits need undo foundation | Direct mutations can become unsafe for modders | Add QUndoStack-backed command layer before expanding save/edit UI. |
| Character export can drift from native KOTOR DAG | Game crashes or A-pose assets | Make native DAG snapshot/export parity the next Character Studio launch gate. |
| ExportJob not yet universal | Different studios can reintroduce partial writes | Migrate Character, Module, Map, FBX, and Patch Manager staging exports. |
| GameResourceProvider missing | Resource lookup remains duplicated | Implement read-only provider before more Module/Map/Character UI expansion. |
| UI may overclaim readiness | Modders need trustworthy status | Use "previewable", "export candidate", "game-tested" labels explicitly. |

## 5. Qt/UI Audit Findings

The official Qt docs reinforce several immediate GhostRigger actions:

- Use `QAction` for shared commands across toolbar/menu/shortcuts.
- Use model/view for resource trees, validation lists, object outliners, and
  module contents.
- Use Designer forms selectively for stable forms, not product logic.
- Use the Undo Framework for editable documents.
- Use threads/jobs for time-consuming work and communicate results back to the
  GUI thread.

Current state:

- Retarget Workbench has moved in the right direction with readiness DTOs and
  controller routing.
- Sequence Editor already uses `QAction` patterns and can inform future command
  organization.
- Theme/layout infrastructure exists and should remain mandatory for new panels.
- A future ValidationBus issue panel should be model/view from day one.

Second-pass book review tightened the UI conclusion:

- `QSortFilterProxyModel` should be the default filter/sort layer for
  validation issues, resource browsers, module contents, and object outliners.
- `QDataWidgetMapper` is worth considering for stable GFF/template inspectors,
  but only behind undoable edit commands.
- `QFileSystemModel` is useful for local import/project folders, not KOTOR
  archive resources. Archive resources need a provider-backed custom model.
- `QSettings` should hold preferences, recent files, game installs, and
  layout/theme state. It must not become a project-content store.
- `QProcess`, `QThreadPool`, `QRunnable`, and progress/cancel UI belong behind
  job/service adapters, not inside click handlers.

## 6. Clean Architecture Audit Findings

The suite now has the correct foundation but needs stricter dependency direction.

Desired dependency flow:

```text
Qt widgets/actions
-> controllers/view-models
-> application services
-> domain/use-case DTOs
-> ports/adapters
-> filesystem/PyKotor/MDL writer/FBX/Ghidra/Qt viewport details
```

The largest current gap is `GameResourceProvider`. Without it, Module Studio,
Map Studio, Character Studio, Retarget Studio, and MCP tools will continue to
resolve KOTOR resources through parallel paths.

Second-pass clean-architecture correction: `GameResourceProvider` should be
treated as a port, not a loader utility. Widgets and controllers ask use-case
services for resource summaries, previews, and typed payloads; adapters decide
whether bytes came from Override, MOD/RIM/ERF, KEY/BIF, project-generated
outputs, or local files.

## 7. KOTOR Source Credibility Audit

Credible KOTOR modding references fall into tiers:

1. Implementation/format sources: PyKotor/OpenKotOR, xoreos/xoreos-docs,
   reone, KotOR.js, and engine/Ghidra/MCP inspection.
2. Mature community tools: Holocron Toolset, KotorBlender, MDLOps, KOTORMax.
3. Workflow/tutorial sources: DeadlyStream, KotOR Modding Guide, KLE docs, and
   KOTOR Modding Wiki pages.

Design consequences:

- Resource identity should be `(game, module/layer, resref, restype,
  provenance)`, not just a display name.
- Override/module/base archive resolution order must be represented explicitly.
- Template resources and placed module instances must remain distinct in UI and
  project state.
- Patch-style outputs should prefer staged manifests and merge-aware workflows
  over destructive direct writes.
- MDL/MDX guidance from community docs is useful but not sufficient for binary
  writer changes; PyKotor/xoreos/reone/KotOR.js plus MCP/Ghidra/game testing are
  the stricter source tier.

## 8. Modder Experience Audit

GhostRigger should feel like a KOTOR tool, not a generic 3D tool. The readiness
slice was a good step because it says:

- which retarget mode is active;
- what source animation is being sampled;
- what target model is selected;
- what output animation name will be attached;
- whether the output is vanilla-slot-safe or custom-patch-only;
- whether export is blocked by stale preview.

The same pattern should spread:

- Character Studio: "Base KOTOR DAG", "supermodel", "hooks", "export
  candidate", "in-game smoke: not run".
- Module Studio: "hydrated module resource", "KMAP authoring state", "staged
  package", "Override/Modules target".
- Map Studio: "room model", "LYT", "VIS", "WOK", "GIT object", "template
  resref", "script/dialog refs".

## 9. Test and Validation Audit

Strong:

- retarget controller/core/export coverage;
- MDL writer/readback regressions;
- project/validation/export foundations;
- module/map headless service coverage;
- secret hygiene.

Missing or next:

- Qt model/view tests for validation/resource/outliner models;
- provider-backed resource model tests that preserve resref/restype/module/layer
  and exact case;
- Character Studio native DAG export parity goldens;
- ExportJob migration tests for module package and character export;
- QUndo command tests for Module/Map edits;
- GameResourceProvider contract tests with fake provider and PyKotor-backed
  adapter;
- opt-in live game smoke checklist surfaced in docs or tool commands.

## 10. Scope Sanity Check

GhostRigger should stay within four product pillars:

1. Character Studio.
2. Retarget Studio.
3. Module Studio.
4. Map/Scenario Studio.

Anything else should be judged by whether it supports those pillars. For
example:

- Ghidra is a diagnostic tool for engine correctness, not a product feature.
- Patch Manager support is an export/staging/runtime workflow, not a replacement
  for safe local export.
- Unity/Unreal bridges are interoperability surfaces, not the core KOTOR truth.

Feature acceptance should include a capability label:

- query-only;
- previewable;
- export candidate;
- game-tested;
- experimental;
- requires custom patch.

This prevents a technically impressive feature from being presented as safer or
more complete than it is.

## 11. Immediate Recommendations

1. Finish `T2304 GameResourceProvider`.
2. Add provider-backed Qt models for resources before building richer browsers.
3. Add a `ValidationBus` Qt model/panel.
4. Add an undo-command foundation for Module/Map authoring.
5. Add a shared job/progress service bridge for scans/imports/exports.
6. Migrate Module/Map/Character exports to `ExportJob`.
7. Promote Retarget Workbench readiness into a proper model/view panel if it
   grows beyond the current labels.
8. Lock Character Studio native KOTOR DAG export parity before broader UI polish.
9. Keep PMBAM/animation export fixes as named solver/export modes with tests,
   not manual calibration knowledge only.
