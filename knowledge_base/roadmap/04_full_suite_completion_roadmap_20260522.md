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
- `src/core/modules/authored_room_primitives.py`: headless primitive builders for floors, walls, cubes, cylinders, arches, ramps, and stairs.
- `src/core/modules/authored_room_operations.py`: floor-plan inset, bevel, rectangular cut, rectangular union, and editable composition primitive operations.
- `src/core/modules/authored_module_objects.py`: authored GIT/IFO placement contracts for placeables, creatures, doors, waypoints, triggers, encounters, sounds, cameras, and stores.
- `src/core/modules/authored_module_export.py`: authored ARE/GIT/IFO/PTH/LYT/VIS, room MDL/MDX/WOK, package manifest, smoke contract, and staged `.mod` export.
- `examples/kmap/` and `examples/kmax/`: seed examples for level and scene serialization.
- Tests cover LYT room graph, snap tools, VIS editor, area WOK integration, and custom module packaging.

2026-06-18 scope clarification:

Map Studio is not only a room-layout editor or module-package helper. The intended product is a full KOTOR module creation studio where a modder can:

1. Build custom room geometry from scratch with primitives, extrusion, bevel, inset, boolean-style cut/union/difference operations, snapping, materials, and generated room MDL/MDX output.
2. Edit authored geometry through real component modes: Object, Vertex, Edge, Face, and Walkmesh. The tool should support the expected modeling basics such as selection masks, transform gizmos, grid/vertex/edge/face snapping, weld/merge vertices, bridge border edges, cut/split faces, extrude, bevel, inset, flatten, cleanup, triangulate, duplicate, delete, freeze transforms, center pivots, and undo/redo.
3. Build terrain patches from modder-friendly tools such as heightfields, sculpt brushes, slope flattening, ramps, terraces, cliffs, and material layers, then compile them into visible room mesh geometry plus matching WOK walkmesh data.
4. Generate and validate WOK walkmeshes from authored floor/ramp/stair/terrain surfaces, including surface type assignment, blocked/invalid triangle diagnostics, slope checks, transition edges, non-walk boundary blockers, and PTH/pathing hints.
5. Assemble rooms into a KOTOR area using LYT/VIS, starting with one-room authored modules and growing into multi-room layouts.
6. Place gameplay objects such as creatures, placeables, doors, triggers, encounters, sounds, cameras, waypoints, and stores, then write the corresponding GIT/IFO data.
7. Package ARE/GIT/IFO/PTH/LYT/VIS, room MDL/MDX/WOK, templates, scripts/dialog refs, and install metadata into a staged module package that can be copied into the game's `Modules` folder.
8. Prove the package in-game. Capability labels must remain honest: `previewable`, `export_candidate`, `installed_ready_for_game_test`, and `game_tested` are separate states.

2026-06-20 modeling-workspace scope clarification:

Map Studio should feel like a focused 3D modeling program, but not a generic Maya clone. Its modeling tools should use familiar DCC language because modders know those words, while the product logic stays KOTOR-specific:

- A primitive is not just visual mesh; it is authored room geometry that can become MDL/MDX render data, WOK walkable/non-walkable faces, LYT room membership, VIS culling metadata, and package manifest output.
- A vertex/edge/face edit is not accepted just because it looks correct in the viewport; it must preserve manifold room geometry where required, keep WOK generation sane, keep transitions explicit, preserve UV/material intent, and pass export validation.
- A terrain brush is not separate from the module compiler; terrain elevation, cliffs, ramps, and blocked areas must generate both render geometry and matching WOK/PTH/navigation intent.
- Maya-style tools are a UX vocabulary, not an excuse to bypass KOTOR gates. Every modeling command must have a visible KOTOR consequence, an undoable command record, validation feedback, and a staged export path.
- The Level Editor/Map Studio window is the owning UI surface. Modeling controls must stay inside the Map Studio workspaces and should not leak into unrelated main viewport, Character Studio, or Retarget Studio windows.

The practical modder story is:

1. Create or open a `.kmap` project.
2. Block out the area with planes, cubes, cylinders, walls, ramps, arches, stairs, and terrain patches.
3. Switch between Object, Vertex, Edge, Face, and Walkmesh modes to refine the shape with snap, weld, cut, bridge, extrude, bevel, inset, flatten, and cleanup tools.
4. Paint materials and WOK surface types while seeing whether a surface will be walkable, blocked, transition-only, water, grass, metal, or otherwise game-significant.
5. Add room boundaries, doors, transitions, visibility links, path points, gameplay placements, and script/dialog/template references.
6. Validate the authored map as KOTOR resources, not just as viewport geometry.
7. Export through `ExportJob` into a staged `.mod` package.
8. Record in-game proof before the UI calls the module `game_tested`.

The first proof remains `T2601 - grdev01`: a generated room with walkable floor, room resources, player start, one test placeable, minimal PTH, staged `.mod`, and recorded KOTOR evidence that `warp grdev01` loads, spawns on the floor, shows the placeable, and allows walking. Do not mark Map Studio game-tested until screenshot/video evidence is recorded through the proof manifest.

Main gaps:

- Product consolidation: the headless authored-module services are strong, but the visible Map Studio workflow still needs one coherent shell for modeling modes, geometry, terrain, WOK, LYT/VIS, gameplay placement, readiness, export, and proof handoff.
- Template editing: placement can reference UTC/UTP/UTD/UTT/UTE/UTS/UTM resrefs, but creating/cloning/editing those templates should route through Module Studio forms with reference safety.
- Visual authoring maturity: primitive operations, component editing, vertex snapping/welding, terrain building, placement markers, room outlines, WOK overlays, and package readiness need to feel like one modder workflow instead of separate test-backed capabilities.
- Conversion contracts: KMAX scene-object transforms, authored pivots, KMAP room transforms, LYT room positions, and generated room MDL/WOK coordinates need one documented roundtrip contract.
- Proof: the current `grdev01.mod` candidate is installed and package-verified, but still lacks recorded in-game evidence.

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

2026-05-23 status note:

- `T2301`, `T2302`, and `T2303` are implemented as foundations:
  `GhostRiggerProject`/`ResourceAddress`, `ValidationBus`, and `ExportJob`.
- `T2304 GameResourceProvider` is implemented as a read-only foundation:
  ResourceAddress-backed queries, provenance records, in-memory/project/local
  providers, a composite provider, and an adapter over the existing fast
  ResourceManager. Studio migration remains the next step.
- `T2305` has started with provider-backed Qt table/proxy models for resource
  rows and filters. Full panel integration and studio-specific browser wiring
  remain.
- The third coding-book pass adds a scope sanity rule: every new feature must
  name its owning studio, modder task, target resource/object, safety gates, and
  capability label before implementation.

| ID | Task | Acceptance |
|----|------|------------|
| DONE T2301 | Add `GhostRiggerProject` dataclasses and JSON save/load. | Project stores game install paths, open assets, retarget profiles, module/map sessions, export candidates, and validation history. |
| DONE T2302 | Add `ValidationBus` and standard report payloads. | Character, retarget, module, and map validations can all publish UI-ready issues with severity and target object links. |
| DONE T2303 | Add `ExportJob` transaction helper. | Exports write to staging/temp paths, verify readback, then promote outputs; failed preflight leaves no partial files. |
| DONE T2304 | Normalize resource access through one provider interface. | KOTOR loaders, Module Studio, Map Studio, Character Studio, and MCP tools can share one configured resource provider. |
| T2305 | Add provider-backed resource browser models. | Qt model/view resource lists expose `ResourceAddress`, resref, restype, module, layer, provenance, and filters from the shared provider. |
| T2306 | Add ValidationBus issue model and panel. | Modders see one filterable diagnostics surface for retarget, project, resource, module, map, and export issues. |
| T2307 | Add undo command foundation for authoring. | Module, map, KMAP/KMAX, and GFF edits can be made through undoable command objects before broad editing is exposed. |
| T2308 | Add shared job/progress bridge. | Long imports, resource scans, validation passes, and exports run as cancellable jobs without blocking Qt. |
| T2309 | Reconcile KMAX/KMAP with existing Module/Map services. | KMAX scene objects, KMAP room/module instances, LYT/VIS/WOK services, and module package outputs have one documented data-flow contract. |

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

Goal: make map/area layout editing visual and integrated while preserving the headless authored-module contracts.

| ID | Task | Acceptance |
|----|------|------------|
| DONE T2901 | Promote KMAP/KMAX into the Map Studio shell foundations. | KMAP/KMAX state, authored module payloads, room outline overlays, primitive handles, readiness panels, and package panels have test-backed integration paths. |
| DONE T2902 | Add authored room primitive palette foundations. | Floor, wall, cube, cylinder, arch, ramp, and stairs primitives can compile to room mesh data; floor/ramp/stairs contribute WOK faces where appropriate. |
| DONE T2903 | Add room shaping operations. | Inset, bevel, rectangular cut, rectangular union, outline-point edits, primitive transforms, dimensions, material, WOK surface, add/remove, and viewport drag operations persist through KMAP and remain exportable. |
| T2904 | Consolidate the visible Map Studio shell. | A modder sees one workflow for component modeling, geometry, terrain, WOK, LYT/VIS, placements, readiness, package output, and proof state rather than scattered Module Editor panels. |
| T2905 | Wire VIS and WOK editor UI into authored projects. | Users can author visibility links, preview culling, inspect WOK face types, paint surfaces, and see seam/invalid-triangle diagnostics from the same authored map session. |
| T2906 | Document KMAP/KMAX/LYT/MDL/WOK transform contract. | Room positions, scene-object transforms, pivots, authored primitive transforms, generated model coordinates, and WOK coordinates have a tested roundtrip contract. |
| T2907 | Add terrain builder foundations. | Users can create terrain patches from heightfields/sculpt controls, paint terrain materials, flatten playable paths, mark cliffs/non-walk areas, generate matching room MDL/MDX and WOK faces, and see slope/blocker diagnostics before export. |
| T2908 | Add component-modeling command stack. | Object, Vertex, Edge, Face, and Walkmesh edits are undoable commands backed by core geometry services, including snap, weld/merge, flatten, bridge, cut/split, extrude, bevel, inset, triangulate, cleanup, duplicate, delete, center pivot, and freeze transforms. |
| T2909 | Add viewport modeling gestures. | Map Studio supports selection masks, transform handles, grid snap, hold-`V` vertex snap, edge/face snap, local/world pivot modes, and clear highlighted previews before committing geometry edits. |
| T2910 | Wire component edits into KMAP persistence. | Component edits update authored room geometry, UV/material/WOK intent, validation status, and generated MDL/WOK outputs without losing unknown forward-compatible KMAP metadata. |
| T2911 | Add KOTOR modeling validation pass. | Nonmanifold geometry, degenerate faces, flipped normals, bad WOK slopes, missing transition edges, invalid UV/material references, and unsafe room/resource names produce actionable issues before export. |
| T2912 | Add material, UV, and lightmap authoring basics. | Modders can assign KOTOR textures/materials, inspect UVs, preserve UVs through common edits where possible, and prepare room geometry for lightmap/minimap workflows. |
| T2913 | Add first modeling golden module. | A small authored map built entirely from Map Studio primitives/component edits validates, packages, installs, loads in KOTOR, and records proof for room mesh, WOK, placement, transition, and walkability. |

### M30 - Map Studio Object and Encounter Setup

Goal: connect map layout with gameplay object authoring.

| ID | Task | Acceptance |
|----|------|------------|
| DONE T3001 | Add authored gameplay placement contracts. | Placeable, creature, door, waypoint, trigger, encounter, sound, camera, and store placements serialize into GIT/IFO-compatible data and validate against walkmesh positions. |
| T3002 | Add modder-facing placement palette. | Palette can search game/library templates, instantiate objects into GIT data, display labels/icons by type, and place them on walkable authored surfaces. |
| T3003 | Add template creation/edit flow. | New UTC/UTP/UTD/UTT/UTE/UTS/UTM templates can be created or cloned and edited in Module Studio forms, then referenced by Map Studio placements. |
| T3004 | Add transition/link authoring. | Doors, triggers, and waypoints can link to target modules/rooms with reference checks and visible fix hints. |
| T3005 | Add script/dialog picker with reference safety. | Object scripts and conversations can be selected from module/base resources and validated before packaging. |
| T3006 | Add encounter/spawn authoring UX. | Encounters and spawn points can be edited visually, validated against WOK/PTH, and saved safely. |

### M31 - Map Packaging and Game Test Flow

Goal: produce installable custom modules with confidence.

| ID | Task | Acceptance |
|----|------|------------|
| DONE T3101 | Add authored module package foundations. | ARE/GIT/IFO/PTH/LYT/VIS, room MDL/MDX/WOK, package manifest, smoke manifest, install-prep, and archive readback checks exist for authored modules. |
| DONE T3102 | Add install-safe smoke handoff. | `prepare_grdev01_authored_smoke.py`, status checks, launch handoff, proof recorder, and evidence-file gates keep package-ready and game-tested states separate. |
| T3103 | Finish the real `grdev01` game proof. | KOTOR is launched, `warp grdev01` is tested, screenshot/video evidence is recorded, and the proof manifest marks module load, floor spawn, placeable visibility, and walkability as accepted. |
| T3104 | Add user-facing package wizard. | Modders can choose output/install target, review resources, stage/copy module files, and see no-partial-write status without using scripts. |
| T3105 | Add full map golden package. | A small custom area with room, WOK, placeable, waypoint, door/transition, and NPC validates, packages, and has recorded proof. |

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

Current recommended order after the 2026-05-23 foundation pass:

1. T2305 - add provider-backed Qt resource browser models.
2. T2306 - add the ValidationBus issue model/panel.
3. T2307 - add the undo command foundation for Module/Map/KMAP/KMAX editing.
4. T2308 - add a shared job/progress bridge for scans, imports, exports, and validation.
5. T2309 - reconcile KMAX/KMAP with existing Module/Map services.
6. T2402 - promote exact PMBAM segment correction from the success path into a named, tested retarget solver mode.

This order keeps Retarget Studio momentum while turning the shared foundations into modder-visible infrastructure before broad Character, Module, and Map editing expands.

## Completion Definition

GhostRigger is "complete enough for beta" when:

- A user can import a custom character FBX/OBJ/glTF, bind it to a native KOTOR node hierarchy, preview inherited/custom animations, export MDL/MDX, and stage install metadata.
- A user can retarget KOTOR to KOTOR, KOTOR to UE, and UE to KOTOR from one Retarget Studio, with preview and verified export gates for each direction.
- A user can load a stock module, edit placed objects and walkmesh data, save safely, and reload the module.
- A user can build a simple custom map, author LYT/VIS/WOK and placed objects, package it as `.mod`, and stage it for game testing.
- All four flows publish validation reports through one UI model and use transaction-style exports with readback or package verification.
