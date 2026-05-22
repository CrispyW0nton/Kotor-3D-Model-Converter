# GhostRigger Suite Architecture Audit

Date: 2026-05-22
Branch audited: qt-ghostrigger
Scope: read-only source and capability audit

## 1. Executive Summary

GhostRigger is now more than a model viewer. It has substantial headless core
services for KOTOR/Odyssey MDL loading and writing, animation retargeting,
module hydration/save, KMAP/KMAX scene state, walkmesh editing, and Qt product
surfaces. The strongest tested area is currently Retarget Studio, especially
the Unreal/FBX to KOTOR path and its slot, evaluator, preview, export, and
writer/readback gates.

The main architectural risk is not lack of pieces. It is fragmentation. The
suite has several project/session models (`KMaxScene`, `KMapProject`,
`RetargetWorkbenchState`, Module Editor models, character workflow request/result
objects), but no single `GhostRiggerProject` spine that ties game installations,
open assets, validations, previews, and export candidates together.

Recommended next architecture slice: add a shared `GhostRiggerProject` session
model plus stable resource addresses. Follow it with `ValidationBus` and
`ExportJob` so all studios share the same validate-preview-export lifecycle.

## 2. Repository Source Map

| Area | Primary files | Current shape |
|---|---|---|
| Game/resource access | `src/core/game/`, `src/core/assets/`, `src/core/game/kotor_loader.py` | KOTOR install/resource loading, PyKotor bridge, animation slot/supermodel resolution, override/resource layers. |
| Model and geometry data | `src/core/geometry/model_data.py`, `src/core/geometry/vertex_space.py` | Shared model/node/animation structures and coordinate-space helpers. |
| MDL/MDX boundary | `src/core/mdl/`, `src/core/retargeting/aurora_animation_writer.py` | Binary reader/writer/porter boundary, retarget animation writer integration, current active writer fixes in working tree. |
| Animation | `src/core/animation/`, `src/core/validation/animation_block_validator.py` | Aurora evaluator, GPU skinning support, structural animation validation, writer roundtrip validation. |
| Retargeting | `src/core/retargeting/`, `src/unreal/`, `src/core/animation_retargeting/` | Modern retarget stack plus older KOTOR/UE scaffolds. UE to KOTOR is strongest; KOTOR to KOTOR and KOTOR to Unreal are pending adapters. |
| Character Studio | `src/core/characters/`, `src/core/skeleton/`, `src/autorig/`, `src/gui/windows/qt_character_builder_window.py` | Import/guide/skeleton/bind/export workflow services and Qt shell. Native KOTOR DAG preservation remains the key launch risk. |
| Module Studio | `src/core/modules/`, `src/gui/windows/module_editor_window.py`, `src/gui/panels/module_editor/` | Module hydration, object inspection, save pipeline, KMAP-aware Qt Module Editor panels. Needs one canonical workflow across hydrated modules, KMAP authoring, and staged packages. |
| Map Studio | `src/core/level/`, `src/core/scene/`, `src/core/walkmesh/`, `examples/kmap/`, `examples/kmax/` | KMAP/KMAX state, layout/room graph, VIS, walkmesh tools, module packager and export bridge. Visual placement and scenario authoring are partial. |
| Sequence/cutscene | `src/sequence/`, `src/gui/sequence_editor/` | Timeline/sequence data and Qt editor foundation. Needs integration with Module/Map object and script systems. |
| Qt shell | `src/gui/windows/qt_main_window.py`, `src/gui/qt_lib.py`, `src/gui/viewports/`, `src/gui/rendering/` | Central Qt entry point, grouped Qt facade, viewport and rendering stack. Legacy Tk modules are guarded by tests. |
| MCP/debug tooling | `src/kotormcp/`, `mcp__ghostrigger__` tools | Resource, module, walkmesh, retargeting, render, and Ghidra/decompile tool surfaces. Ghidra endpoint/credentials must remain local-only. |
| Roadmaps/docs | `knowledge_base/roadmap/`, `docs/knowledgebase/`, `CHANGES.md` | Strong planning base. Some top-level README content is stale and still references older Tk/Genspark-era language. |

## 3. Major Subsystems

### Retarget Studio

Modern retargeting is centered under `src/core/retargeting/`.
Implemented pieces include:

- source animation abstractions and audit helpers;
- FBX/UE source import interface;
- KOTOR source animation sampler;
- mapping/profile/reference-pose layers;
- calibrated frame and solver helpers;
- headless preview/audit;
- Qt preview/export controllers;
- verified MDL/MDX preview export path;
- tri-mode workbench contracts.

The current implemented product path is `Unreal to KOTOR`. `KOTOR to KOTOR`
and `KOTOR to Unreal` are represented as explicit pending modes.

### Character Studio

Character work is split between headless workflows and Qt windows/panels.
`headless_body_workflow.py`, `character_builder.py`, `head_workflow.py`, and
`skeleton_builder.py` give a strong starting point for import, guide placement,
skeleton selection, binding, validation, and export. The roadmap correctly
states that native KOTOR DAG preservation must become the authoritative
character export model.

### Module Studio

Module Studio has a real backend:

- `module_hydration.py` for archive/resource hydration;
- `module_object_inspector.py` for typed object edits;
- `module_save_pipeline.py` for deterministic save output;
- `module_reference_safety.py` and WOK integration checks;
- `module_editor_controller.py` plus Qt module editor panels.

The remaining work is mostly product cohesion and transaction safety: one UI
should make clear whether the user is editing raw hydrated module resources,
KMAP authoring state, or staged package output.

### Map Studio

Map Studio has a KMAP/KMAX spine:

- `KMapProject` stores module/room/object/light/camera/sequence/blueprint data;
- `KMaxScene` stores general editable 3D scene state;
- LYT room graph, VIS editor, walkmesh editor, and custom module packager exist;
- export bridge writes manifest first and only attempts FBX when mesh assembly is available.

This is the right safety posture. The next gap is to connect object placement,
GFF/template editing, scripts/dialogs, and module packaging into one scenario
authoring workflow.

## 4. Current Project / Session / State Model

There is no single project document. Instead, state exists in several islands:

| State object | Purpose | Gap |
|---|---|---|
| `KMaxScene` / `KMaxSceneManager` | General 3D scene and object transforms | Not yet the universal app project/session. |
| `KMapProject` | Map/level authoring state | Separate from hydrated module resource state. |
| Module editor model/controller | Module hydration, KMAP services, UI panel state | Needs canonical boundaries with KMAP and save pipeline. |
| `RetargetWorkbenchState` | Tri-mode retarget UI state | Not persisted as part of a project. |
| `RetargetPreviewUiState` | UE to KOTOR preview/export state | Good local state, but not tied to project identity/export candidates. |
| Character workflow dataclasses | Headless character build request/result state | Strong service model, but not unified with project/export systems. |

Recommended target: `GhostRiggerProject` should store resource addresses,
open documents, validation reports, preview scenes, and export candidates rather
than duplicating these concepts per studio.

## 5. Core Service Boundaries

Good headless/UI separation already exists in several places:

- Retarget math lives in `src/core/retargeting/`; Qt controllers call it.
- Module data and KMAP state live in `src/core/modules/` and `src/core/level/`;
  Qt panels call controllers/services.
- Character workflows have pure service objects separate from the Qt window.
- The viewport adapter around retarget preview is intentionally thin.

Boundary risks:

- `qt_main_window.py` still owns a large amount of application orchestration.
- Older retarget modules (`src/core/animation_retargeting/retargeter.py`,
  `src/unreal/animation_retargeting.py`) overlap with the modern
  `src/core/retargeting/` system.
- Local GFF readers/writers overlap conceptually with PyKotor typed GFF/generic
  resource models.
- KMAX, KMAP, hydrated module state, and package manifests are related but not
  yet mediated by one project/session layer.

## 6. Qt UI / Window / Panel Map

| UI entry | Files | Notes |
|---|---|---|
| Main window | `src/gui/windows/qt_main_window.py` | Central action registry, viewport, scene manager, retarget workbench actions, module editor actions, IPC pings. Large and should stay thin over controllers. |
| Retarget workbench | `src/gui/windows/qt_retarget_workbench_controller.py`, `qt_retarget_preview_controller.py` | Mode contracts and UE to KOTOR preview/export delegation. |
| Character Builder | `src/gui/windows/qt_character_builder_window.py`, `src/gui/panels/qt_character_builder_panel.py` | Product surface for character workflows. |
| Module Editor | `src/gui/windows/module_editor_window.py`, `src/gui/panels/module_editor/` | Standalone KMAP/Module Editor with validation, walkmesh, room, export, blueprint panels. |
| Sequence Editor | `src/gui/sequence_editor/` | Timeline/sequence surface that can become cutscene/scenario authoring. |
| Unreal Animator | `src/gui/windows/qt_unreal_animator.py` | Separate UE-oriented animation surface that should eventually align with Retarget Studio contracts. |
| Viewports/rendering | `src/gui/viewports/`, `src/gui/rendering/`, `src/gui/qt_lib.py` | Qt viewport and rendering facade. Tk removal is guarded by tests. |

## 7. Test Coverage Map

Strong coverage exists for:

- retarget slot resolution and export gate;
- Aurora controller semantics;
- animation writer/readback roundtrip;
- UE/FBX source import abstraction;
- mapping/reference pose;
- basic retarget solver;
- KOTOR animation source sampler;
- preview/export controller behavior;
- retarget workbench modes;
- character head/body workflow pieces;
- KMAX/gizmo/scene transform behavior;
- MCP resource/skinning/texture exposure;
- secret hygiene for local Ghidra credentials.

Important test files include:

- `tests/test_basic_retarget_solver.py`
- `tests/test_retarget_preview_gate.py`
- `tests/test_retarget_preview_export.py`
- `tests/test_kotor_animation_source_sampler.py`
- `tests/test_ghostrigger_retarget_workbench_controller.py`
- `tests/test_headless_body_workflow.py`
- `tests/test_qt_only_imports.py`
- `tests/test_mcp_full_scan.py`
- `tests/test_secret_hygiene.py`

Gaps:

- no full Character Studio golden export/reload suite yet;
- no complete KOTOR to KOTOR preview/export tests yet;
- no KOTOR to Unreal FBX export tests yet;
- Module/Map tests should include roundtrip save/reload fixtures for actual
  edited module resources;
- in-game smoke tests remain external/manual and should stay opt-in.

## 8. Dependency Map

GhostRigger is MIT licensed. `pyproject.toml` exposes optional extras for GUI,
KOTOR/PyKotor, mesh, and MCP-style workflows.

Important dependency categories:

- Qt: PySide6 and the local `src/gui/qt_lib.py` facade.
- Rendering: ModernGL/Pillow/NumPy style stack.
- KOTOR resources: optional PyKotor bridge and local readers/writers.
- Mesh import/export: trimesh/open3d/FBX-related adapters where available.
- MCP/debug: GhostRigger MCP tools and local Ghidra/AgentDecompile integration.

License note: PyKotor/Holocron are LGPL-3.0-or-later. GhostRigger should prefer
depending on PyKotor as a library or subprocess/tool boundary, not copying code
into the MIT repo without an explicit license review.

## 9. Overlap / Conflict Map

| Overlap | Risk | Recommendation |
|---|---|---|
| Modern retarget stack vs older `animation_retargeting` / `src/unreal` helpers | Divergent solver and naming rules | Keep modern `src/core/retargeting/` authoritative; wrap older helpers or retire them after coverage. |
| KMAX vs KMAP vs hydrated module state | Users may not know which layer they are editing | Add `GhostRiggerProject` and explicit resource/state layer labels in UI. |
| Local GFF code vs PyKotor typed generics | Duplicated bug surface for module editing | Prefer PyKotor typed generics where possible; use GhostRigger wrappers for UI/state/validation. |
| Character skeleton builder vs native KOTOR DAG requirement | Imported skeletons could leak into exported KOTOR assets | Make `NativeSkeletonSnapshot` and clone-DAG-then-bind the export path. |
| Main window orchestration vs dedicated controllers | UI logic can become product logic | Move product flows into controllers/services; keep Qt actions thin. |
| Stale docs vs current Qt architecture | Misleads future agents | Update top-level docs after architecture spine lands. |

## 10. Architectural Risks

1. Writer/export correctness is still the highest-stakes area because game
   crashes happen at binary-engine boundaries.
2. Retarget Studio can regress if the exact PMBAM idle success path is not
   promoted into tested solver/export behavior.
3. Character Studio cannot ship until it proves native KOTOR DAG preservation
   and skin/bind metadata stability.
4. Module/Map Studio can corrupt mods if save/export actions are reachable
   without preflight, staging, backup, and reload validation.
5. Local-only Ghidra/debug endpoints are powerful and must stay untracked.
   `tests/test_secret_hygiene.py` is the right guard and should remain in CI.

## 11. Immediate Recommendations

1. Add `GhostRiggerProject` plus resource address/session model.
2. Add a shared `ValidationBus` so Character, Retarget, Module, and Map reports
   have one severity/target/fix shape.
3. Add `ExportJob` for transactional write, readback, manifest, and promotion.
4. Reconcile KMAX/KMAP/module hydrated state with one documented data-flow.
5. Keep Retarget Studio moving, but do the next KOTOR to KOTOR adapter through
   the existing sampler/profile/preview/export gates rather than a parallel path.
