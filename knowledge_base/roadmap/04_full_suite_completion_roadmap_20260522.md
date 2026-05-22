# GhostRigger Full Suite Completion Roadmap

Date: 2026-05-22
Branch: `qt-ghostrigger`

## Purpose

This roadmap reframes GhostRigger as a complete KOTOR/Odyssey creation suite rather than only a model viewer or character builder. It builds on the existing Qt roadmap, the native KOTOR Character Builder plan, and the newly stabilized retargeting foundation.

The target product has four authoring studios:

1. Character Studio: import custom FBX/OBJ/glTF models, fit them to a KOTOR node hierarchy, rig/skin them, preview inherited or custom animations, and export MDL/MDX plus patch data.
2. Retarget Studio: retarget animation in three directions: KOTOR to KOTOR, KOTOR to Unreal, and Unreal to KOTOR.
3. Module Studio: hydrate, inspect, edit, validate, and save KOTOR modules, including GFF-backed placed objects and walkmesh data.
4. Map Studio: build area layouts, author LYT/VIS/WOK, set up placeables/NPCs/doors/triggers, and package installable `.mod` outputs.

## Current Structure Audit

### Shared Foundation

Existing strong pieces:

- `src/core/game/`: KOTOR install detection, PyKotor bridge, MDL loading, slot/supermodel resolution.
- `src/core/geometry/model_data.py`: shared model/node/animation data structures.
- `src/core/mdl/`: binary MDL reader/writer/porter boundary.
- `src/core/animation/`: Aurora animation evaluator, supermodel resolver, GPU skinning support.
- `src/core/assets/`: game resource manager, override layer, asset preview workbench.
- `src/core/validation/`: animation block and writer roundtrip validation.
- `src/core/scene/`: scene manager, KMAX scene/object/resource model, serializer, validator, and transform-reference controls.
- `src/core/level/`: KMAP level/project model, serializer, validator, module/room instances, export bridge, and texture resolver.
- `src/gui/viewports/` and `src/gui/rendering/`: Qt viewport and renderer stack.
- `src/kotormcp/`: MCP resource, model, module, walkmesh, retargeting, and debug tool surfaces.

Main gap:

- There is no single project/session model that ties loaded game installs, imported assets, retarget profiles, target model, module/map state, validation reports, and export candidates together.

### Character Studio

Existing strong pieces:

- `src/core/characters/headless_body_workflow.py`: large service layer for import, fit, guides, skeleton generation, motion assignment, validation, export, and launch workflow.
- `src/core/characters/head_workflow.py`: head/facial/LIP workflow service.
- `src/core/characters/character_builder.py`: template loading, template rig application, headhook, facial bone checks, skeleton selector.
- `src/core/characters/creature_appearance.py`: appearance-driven creature/body/head assembly and FBX export helpers.
- `src/core/skeleton/skeleton_builder.py`: imported mesh to skeleton binding scaffold.
- `src/autorig/accurig.py`, `auto_rigger.py`, `grig.py`, `cloth_rig.py`: guide placement, masking, symmetry, weighting, cloth, and legacy/experimental rig tools.
- `src/gui/windows/qt_character_builder_window.py`: Qt Character Builder UI shell.
- Existing roadmap: `03_character_builder_native_kotor_pipeline.md`.

Main gaps:

- Native KOTOR DAG preservation is still the central launch risk. Imported meshes must be bound to cloned KOTOR node hierarchies, not exported as generic armatures.
- Weight transfer should prefer library/base-model skin transfer before nearest-bone fallback.
- Export readiness needs representative golden MDL/MDX assets and in-game/Patch Manager smoke tests.
- Creature mode remains less complete than humanoid/head workflows.

### Retarget Studio

Existing strong pieces:

- `src/core/retargeting/`: source clip abstraction, FBX source import, coordinate conversion, profile/mapping/reference-pose layer, calibrated frames, solver, preview, export, strict slot gate, and Aurora writer integration.
- `src/core/animation_retargeting/retargeter.py`: KOTOR-to-KOTOR pose/animation retargeting scaffold.
- `src/unreal/animation_retargeting.py`: Unreal-target retargeting helper with KOTOR/UE alias mapping and twist weighting.
- `src/unreal/quinn.py`: Unreal Quinn skeleton/model loading utilities.
- `src/core/export/unity_export_bridge.py` and `unity_import_validator.py`: Unity bridge and validation support.
- `src/gui/windows/qt_retarget_preview_controller.py`: Qt preview/export controller for the UE to KOTOR path.
- Tests now cover slot validation, Aurora controller semantics, writer roundtrip, UE/FBX source import, mapping/reference poses, calibrated retarget frames, preview, and preview export.

Main gaps:

- The three retarget directions are implemented as separate islands rather than one explicit mode system.
- UE to KOTOR now has the strongest safety gate; KOTOR to KOTOR and KOTOR to UE need the same preview/export/readback discipline.
- Final exact segment correction from the PMBAM idle success should be promoted from candidate knowledge into a first-class solver mode.
- KOTOR to UE needs a product flow for skeleton export, FBX animation clip output, Unity/UE validation, and retarget profile save/load.

### Module Studio

Existing strong pieces:

- `src/core/modules/module_hydration.py`: module archive hydration.
- `src/core/modules/module_object_inspector.py`: typed GFF-backed object inspector.
- `src/core/modules/module_save_pipeline.py`: deterministic module save pipeline with backups and changed-resource manifest.
- `src/core/modules/module_reference_safety.py`: referenced in tests and roadmap as save preflight.
- `src/core/modules/module_editor_controller.py` plus `module_editor_model.py` and related services: newer KMAP-aware Module Editor controller/model/service layer from LordVader's fork.
- `src/gui/windows/module_editor_window.py` and `src/gui/panels/module_editor/`: Qt Module/Level Editor shell, asset browser, outliner, properties, toolbar, rooms, walkmesh, validation, porter, and export panels.
- `src/core/walkmesh/walkmesh_editor.py`: walkmesh face selection, material painting, validation, and roundtrip checks.
- `src/formats/gff_reader.py` and `gff_writer.py`: GFF reader/writer layer.
- Tests cover module categories, hydration, object inspection, reference safety, save pipeline, and walkmesh editing.

Main gaps:

- The backend and new Module Editor UI now overlap. The next step is consolidation: one Module Studio workflow should decide when it is editing hydrated RIM/MOD resources, KMAP authoring state, or staged package output.
- Script/dialog reference resolution needs a user-facing workflow for external/base-game refs.
- GFF editing should expose field-level validation, undo/redo, and dirty-state tracking.

### Map Studio

Existing strong pieces:

- `src/core/scene/lyt_room_graph.py`: LYT room graph and room add/move helpers.
- `src/core/level/`: KMAP project/level state for authored maps and room/module instances.
- `src/core/geometry/map_snap_tools.py`: snap/alignment tools for rooms and placed objects.
- `src/core/scene/vis_editor.py`: editable VIS state and visibility preview.
- `src/core/modules/area_wok_integration.py`: area WOK checks and seam warnings.
- `src/core/modules/custom_module_packager.py`: install-safe custom module package staging.
- `examples/kmap/` and `examples/kmax/`: seed examples for level and scene serialization.
- Tests cover LYT room graph, snap tools, VIS editor, area WOK integration, and custom module packaging.

Main gaps:

- Map Builder now has a KMAP/KMAX spine and Qt Module Editor panels, but the older LYT/VIS/WOK authoring services still need to be wired into that product surface.
- Placeable/NPC/door authoring must connect Map Studio placement to Module Studio GFF/template editing.
- Custom area model creation from imported geometry is not yet a polished loop.
- KMAX scene-object transforms, authored pivots, and KOTOR module room transforms need one documented conversion contract before exported maps can be trusted.

## Target Architecture

### Product Studios

GhostRigger should expose four top-level studios, each with a thin Qt shell over headless core services:

- Character Studio: character/head/creature import, fitting, rigging, preview, export.
- Retarget Studio: animation conversion and validation in all three directions.
- Module Studio: module resource/object editing.
- Map Studio: area layout/map construction and packaging.

### Shared Core Services

Add these explicit services so the studios do not duplicate state:

- `GhostRiggerProject`: session document containing game install refs, imported assets, target models, retarget profiles, module/map state, validation reports, and export candidates.
- `GameResourceProvider`: single access point for KEY/BIF/RIM/ERF/override resources, replacing ad hoc resource plumbing.
- `PreviewScene`: shared character/module/map preview state with attachments, active animation, camera, overlays, and validation badges.
- `KMaxSceneBridge`: adapter between KMAX scene objects and KOTOR model/module/map authoring so viewport transforms, pivots, and serialized KMAP data agree.
- `ValidationBus`: central validation report model with severity, source subsystem, target resource, fix suggestions, and UI navigation hooks.
- `ExportJob`: common export transaction that preflights, writes to temp/staging, verifies readback, emits manifest, and then promotes to final output.

### Data Flow Rule

Every studio should follow the same lifecycle:

`Load/import -> normalize -> author -> validate -> preview -> export/stage -> verify -> install/test`

No direct writer call should be reachable from a UI button without passing through validation and a transaction-style export job.

## Roadmap to Completion

### M23 - Suite Foundation and Project Model

Goal: give all studios one shared project/session spine.

| ID | Task | Acceptance |
|----|------|------------|
| T2301 | Add `GhostRiggerProject` dataclasses and JSON save/load. | Project stores game install paths, open assets, retarget profiles, module/map sessions, export candidates, and validation history. |
| T2302 | Add `ValidationBus` and standard report payloads. | Character, retarget, module, and map validations can all publish UI-ready issues with severity and target object links. |
| T2303 | Add `ExportJob` transaction helper. | Exports write to staging/temp paths, verify readback, then promote outputs; failed preflight leaves no partial files. |
| T2304 | Normalize resource access through one provider interface. | KOTOR loaders, Module Studio, Map Studio, Character Studio, and MCP tools can share one configured resource provider. |
| T2305 | Reconcile KMAX/KMAP with existing Module/Map services. | KMAX scene objects, KMAP room/module instances, LYT/VIS/WOK services, and module package outputs have one documented data-flow contract. |
| T2306 | Repo hygiene pass. | Remove stale `__pycache__`/pytest temp dirs from workspace, document scratch-output policies, and keep generated assets ignored. |

### M24 - Retarget Studio Tri-Mode Productization

Goal: make all three retarget directions explicit, repeatable, and equally validated.

| ID | Task | Acceptance |
|----|------|------------|
| T2401 | Add retarget mode enum and shared request/result contracts. | Modes: `kotor_to_kotor`, `kotor_to_unreal`, `unreal_to_kotor`. Each declares source, target, profile, preview, and export requirements. |
| T2402 | Promote exact segment correction into core solver mode. | PMBAM idle result can be regenerated by a tracked solver path, not a one-off scratch experiment. |
| T2403 | Give KOTOR-to-KOTOR the same preview/export gates as UE-to-KOTOR. | Local animation override preview, structural validation, writer readback, and no-write-on-invalid behavior all pass. |
| T2404 | Give KOTOR-to-UE a formal FBX export pipeline. | Stock KOTOR animation exports to UE-compatible FBX with manifest, skeleton map, sampled pose audit, and Unity/UE validation hooks. |
| T2405 | Build the Retarget Studio Qt panel. | User chooses mode, source, target, profile, slot/clip, Preview, and Export. The UI does not contain solver math. |
| T2406 | Add tri-mode regression fixtures. | One representative fixture per direction runs source import, mapping, preview/evaluate, export/readback where applicable. |

### M25 - Character Studio Native DAG Lock

Goal: finish the native KOTOR skeleton/skin foundation for custom imported characters.

| ID | Task | Acceptance |
|----|------|------------|
| T2501 | Implement `NativeSkeletonSnapshot`. | Captures exact node names, parent links, flags, local transforms, hooks, mesh/skin metadata, and supermodel string from selected base models. |
| T2502 | Split viewport display hiding from export DAG state. | Hiding `_g`/helper nodes in the viewport never removes or renames export nodes. |
| T2503 | Rework Build Skeleton around clone-native-DAG-then-bind. | Imported FBX/OBJ/glTF mesh is attached to the cloned KOTOR hierarchy, preserving inherited animation binding. |
| T2504 | Add structural diff report after build. | User sees preserved nodes, added mesh nodes, changed transforms, missing hooks, and skin row counts. |
| T2505 | Add golden native-DAG tests. | Representative K1/K2 body, head, full-body, and creature references pass snapshot and build diff gates. |

### M26 - Character Studio Binding and Export

Goal: turn imported meshes into reloadable, playable KOTOR assets.

| ID | Task | Acceptance |
|----|------|------------|
| T2601 | Audit current `skeleton_builder.py` binding tables against MDL writer/loader facts. | Bone maps, qbone/tbone lists, bind poses, and skin rows are verified by write/readback tests. |
| T2602 | Add library/base-mesh weight transfer. | Imported humanoid mesh can copy weights from a selected vanilla/custom body before nearest-bone fallback. |
| T2603 | Keep nearest-bone auto-rig as a fallback with visible quality warnings. | No comparable base mesh still yields a usable first-pass rig. |
| T2604 | Add Character Studio export preflight. | Blocks missing hooks, missing supermodel, invalid skin rows, unnormalized weights, and invalid animation assignments. |
| T2605 | Generate optional 2DA/Patch Manager helper output. | Export can emit appearance/head row suggestions and install-staging metadata. |
| T2606 | Golden export and reload tests. | Imported body/head/full-body examples export to MDL/MDX, reload, preview inherited animations, and pass parity reports. |

### M27 - Character Studio Creature and Advanced Rigging

Goal: complete the creature track after humanoid/head export is stable.

| ID | Task | Acceptance |
|----|------|------------|
| T2701 | Implement creature profile workflows. | Quadruped, winged, tail, tentacle, droid, and humanoid variants expose mode-specific guides and validation. |
| T2702 | Add spline-IK chain service. | Tail/tentacle/spine chains have authored controls and ROM tests. |
| T2703 | Add wing rig service. | Wing FLAP/FOLD/LINK/CTRL layers can be generated and previewed. |
| T2704 | Add creature ROM generator. | Creature profiles generate and preview range-of-motion clips. |
| T2705 | Add creature export/reload goldens. | At least one stock creature-style and one imported creature fixture pass export/reload validation. |

### M28 - Module Studio UI and Save Confidence

Goal: expose the existing module backend as a real modder workflow.

| ID | Task | Acceptance |
|----|------|------------|
| T2801 | Consolidate the new Module Editor window with module hydration/save services. | One Module Studio window can load hydrated modules or KMAP projects and clearly show which data layer is being edited. |
| T2802 | Wire GFF-backed object forms. | Creatures, doors, placeables, triggers, encounters, waypoints, sounds, stores, and transitions can be edited with dirty-state tracking. |
| T2803 | Add object placement viewport overlay. | Placed objects appear in the viewport with selectable markers and editable transforms. |
| T2804 | Wire WOK editor UI. | Face selection, material painting, walkability validation, and roundtrip checks are visible and undoable. |
| T2805 | Add module save transaction. | Save creates backups, changed-resource manifest, reference-safety report, and no partial output on failure. |
| T2806 | Add module regression fixtures. | Representative K1 and TSL modules hydrate, edit one safe field, save to temp, reload, and compare resources. |

### M29 - Map Studio Layout Authoring

Goal: make map/area layout editing visual and integrated.

| ID | Task | Acceptance |
|----|------|------------|
| T2901 | Promote KMAP/KMAX into the Map Studio shell. | Room graph, 3D layout viewport, room properties, VIS editor, WOK overlay, and package panel all operate on the same KMAP/KMAX-backed state. |
| T2902 | Add room/model library browser. | User can browse existing room models or imported custom room MDL/MDX pairs. |
| T2903 | Wire room add/move/snap tools. | Doorway/grid snapping updates LYT state and viewport transforms deterministically. |
| T2904 | Wire VIS editor UI. | Users can author visibility links and preview culling relationships. |
| T2905 | Add seam/WOK validation overlay. | Missing WOKs, invalid surface materials, reversed/degenerate faces, and seam gaps appear as actionable warnings. |

### M30 - Map Studio Object and Encounter Setup

Goal: connect map layout with gameplay object authoring.

| ID | Task | Acceptance |
|----|------|------------|
| T3001 | Add placeable/NPC/door/trigger palette. | Palette can instantiate templates into GIT data with correct resrefs and transforms. |
| T3002 | Add template creation/edit flow. | New UTC/UTP/UTD/UTT/etc. templates can be created or cloned and edited in Module Studio forms. |
| T3003 | Add transition/link authoring. | Doors, triggers, and waypoints can link to target modules/rooms with reference checks. |
| T3004 | Add script/dialog picker with reference safety. | Object scripts and conversations can be selected from module/base resources and validated before packaging. |
| T3005 | Add encounter/spawn authoring. | Encounters and spawn points can be edited visually and saved safely. |

### M31 - Map Packaging and Game Test Flow

Goal: produce installable custom modules with confidence.

| ID | Task | Acceptance |
|----|------|------------|
| T3101 | Add custom module package wizard. | Packs ARE/GIT/IFO, LYT/VIS/WOK, room MDL/MDX, templates, scripts, dialogs, and manifest. |
| T3102 | Add Patch Manager staging output. | Package writes install-safe output folder with module, override resources, and manifest. |
| T3103 | Add in-game smoke checklist and optional launcher hook. | User gets exact install/test steps and validation report for game testing. |
| T3104 | Add full map golden package. | A small custom area with room, WOK, placeable, waypoint, door/transition, and NPC validates and packages. |

### M32 - Suite QA, Polish, and Beta

Goal: harden the suite for modder beta.

| ID | Task | Acceptance |
|----|------|------------|
| T3201 | Add full suite smoke tests. | Character, retarget, module, and map smoke workflows run headlessly on clean checkout where fixtures permit. |
| T3202 | Add visual regression coverage. | Viewport captures for representative characters, animations, modules, WOKs, and maps are compared against goldens. |
| T3203 | Add crash-safe autosave/recovery for project sessions. | Project/session state can recover after interrupted authoring. |
| T3204 | Add beta documentation. | User docs cover import, rig, retarget, module edit, map build, package, and test workflows. |
| T3205 | Add release packaging. | Windows build includes Qt app, MCP helpers, docs, examples, and no proprietary game assets. |

## Recommended Immediate Sprint

Start with M23, then M24/T2402.

1. T2301 - add a project/session model so future UI work has one source of truth.
2. T2305 - reconcile LordVader's KMAX/KMAP scene work with the existing Module/Map services.
3. T2302 - centralize validation reports so all studios speak the same language.
4. T2303 - add export transactions so no studio writes partial or unverified outputs.
5. T2402 - promote exact segment correction from the PMBAM success path into the tracked retarget solver.
6. T2405 - make Retarget Studio a tri-mode UI once the core contracts are unified.

This order keeps the momentum from the retargeting breakthrough while protecting the much larger Character/Module/Map roadmap from state-management drift.

## Completion Definition

GhostRigger is "complete enough for beta" when:

- A user can import a custom character FBX/OBJ/glTF, bind it to a native KOTOR node hierarchy, preview inherited/custom animations, export MDL/MDX, and stage install metadata.
- A user can retarget KOTOR to KOTOR, KOTOR to UE, and UE to KOTOR from one Retarget Studio, with preview and verified export gates for each direction.
- A user can load a stock module, edit placed objects and walkmesh data, save safely, and reload the module.
- A user can build a simple custom map, author LYT/VIS/WOK and placed objects, package it as `.mod`, and stage it for game testing.
- All four flows publish validation reports through one UI model and use transaction-style exports with readback or package verification.
