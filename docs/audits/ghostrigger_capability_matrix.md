# GhostRigger Capability Matrix

Date: 2026-05-23

Status values: Working, Partial, Experimental, Stub, Missing, Unknown.

## Character Studio

| Capability | Existing implementation | Tests | Status | Gap | Recommended next task |
|---|---|---|---|---|---|
| Import FBX/OBJ/glTF and source model payloads | `src/core/characters/headless_body_workflow.py`, `src/loaders/gltf_importer.py`, main window import actions | `tests/test_headless_body_workflow.py`, import-related smoke tests | Partial | Import exists, but game-safe KOTOR hierarchy conversion is not proven for full custom characters | Add Character Studio fixture set for imported mesh to native KOTOR DAG export. |
| Native KOTOR DAG preservation | Roadmap `03_character_builder_native_kotor_pipeline.md`, `character_builder.py` templates | Some character mode tests | Partial | Needs first-class `NativeSkeletonSnapshot` and structural diff gate | Implement `NativeSkeletonSnapshot` and clone-native-DAG-then-bind path. |
| Auto-rig guide placement and skeleton building | `src/autorig/`, `src/core/skeleton/skeleton_builder.py` | `tests/test_headless_body_workflow.py`, UI tests | Experimental | Nearest-bone fallback exists; library/base mesh weight transfer is not yet a trusted primary path | Add base-model weight transfer before nearest-bone fallback. |
| Skin/bind export validation | `src/core/mdl/`, `src/core/validation/`, character workflow validation | Retarget writer tests, character workflow tests | Partial | Character-specific MDL/MDX export goldens are missing | Add write/readback goldens for body, head, full-body, creature. |
| Head/facial workflow | `src/core/characters/head_workflow.py`, head panels | `tests/test_head_workflow.py`, head UI tests | Partial | Needs integration into shared project/export transaction | Connect to `GhostRiggerProject` and `ExportJob`. |
| Creature workflow | `creature_appearance.py`, autorig creature-style services | Limited | Experimental | Creature profiles, ROM, wing/tail/IK chains are not productized | Define creature profiles after humanoid DAG lock. |

## Retarget Studio

| Capability | Existing implementation | Tests | Status | Gap | Recommended next task |
|---|---|---|---|---|---|
| Unreal/FBX source clip import | `source_animation.py`, `fbx_importer.py`, `source_skeleton_audit.py` | `tests/test_ue_fbx_source_import.py` | Working for abstraction, Partial for real backend | Real FBX backend availability is optional | Keep fake-backend tests; add opt-in real fixture coverage. |
| KOTOR source animation sampling | `kotor_source_animation.py` | `tests/test_kotor_animation_source_sampler.py` | Working | Still needed for KOTOR to Unreal | Use sampler as source adapter for UE-compatible export later. |
| Profile/mapping/reference poses | `retarget_profile.py`, `retarget_mapping.py`, `reference_pose.py`, frame audit | `tests/test_retarget_mapping_profile.py`, `tests/test_retarget_reference_pose.py` | Working | UI profile editor is missing | Add profile editor only after mode/product flows stabilize. |
| Basic UE to KOTOR solver | `retarget_solver.py`, `retarget_frames.py`, calibration helpers | `tests/test_basic_retarget_solver.py`, calibration tests | Working | Exact successful PMBAM segment correction should be a named tested solver mode | Promote PMBAM idle solution into solver options and goldens. |
| Headless preview/audit | `retarget_preview.py` | `tests/test_retarget_preview_gate.py` | Working | Mesh deformation audit is limited by headless skinning availability | Expand skinning/AABB checks when headless skinning is available. |
| Qt preview/export path | `qt_retarget_preview_controller.py`, `qt_retarget_workbench_controller.py` | `tests/test_ghostrigger_retarget_preview_controller.py`, export/workbench tests | Working for Unreal to KOTOR and KOTOR to KOTOR | KOTOR to Unreal remains pending | Add KOTOR to Unreal contract/export after provider and quality work. |
| Verified MDL/MDX export | `retarget_preview_export.py`, `aurora_animation_writer.py`, `mdl_writer.py`, `src/core/export/export_job.py` | `tests/test_retarget_preview_export.py`, writer roundtrip tests, `tests/test_export_job.py` | Working foundation | Retarget export uses staged transactions; Character/Module/Map exports still need migration | Keep MDL writer changes source-truth verified and migrate other exports to ExportJob. |
| KOTOR to KOTOR | `kotor_to_kotor_preview.py`, workbench controller | KOTOR-to-KOTOR core/controller tests | Working preview/export candidate | Needs more real-model/game-tested fixtures and quality modes | Add named quality/correction modes and capability labels. |
| KOTOR to Unreal | Mode contract and Unreal helper modules | Limited | Stub | Needs UE skeleton target/profile and FBX animation export | Add UE-compatible sampled clip exporter after KOTOR to KOTOR. |

## Module Studio

| Capability | Existing implementation | Tests | Status | Gap | Recommended next task |
|---|---|---|---|---|---|
| Module hydration | `module_hydration.py`, `module_loader.py` | Module hydration/reference tests | Partial | Needs stronger PyKotor-backed provider integration | Introduce `GameResourceProvider` and resource addresses. |
| Typed object inspection/editing | `module_object_inspector.py`, module editor panels | Object inspector tests | Partial | Field-level validation and undo/redo need product polish | Add dirty-field model and validation bus output. |
| Module save pipeline | `module_save_pipeline.py` | Save pipeline tests | Partial | Needs export transaction and reload comparison in UI | Route saves through `ExportJob`. |
| Reference safety | `module_reference_safety.py` | Reference tests | Partial | Needs user-facing unresolved ref workflows | Add reference browser/fix suggestions. |
| UTC/UTP/UTD/UTT/etc. editing | Object inspector and local GFF helpers | Limited | Partial | PyKotor typed generics are more complete | Use PyKotor generic models behind GhostRigger forms. |
| DLG/script integration | Some resource panels and IPC to GhostScripter | Limited | Stub | No unified dialogue/script authoring path | Add `ScriptService` bridge and DLG picker later. |
| Walkmesh editing | `src/core/walkmesh/`, module walkmesh panels | Walkmesh tests | Partial | Needs UI undo, seam overlays, package integration | Wire WOK editor into Module/Map shared validation. |

## Map Studio

| Capability | Existing implementation | Tests | Status | Gap | Recommended next task |
|---|---|---|---|---|---|
| KMAP authoring state | `kmap_model.py`, serializer, validator, project docs | KMAP/level tests | Partial | Needs single product shell with Module Studio layers | Define KMAP vs hydrated module data-flow contract. |
| KMAX scene state | `kmax_scene.py`, scene manager, serializer, validator | Gizmo/KMAX tests | Partial | Needs bridge to KMAP/module placement semantics | Add `KMaxSceneBridge` design and tests. |
| LYT room graph | `lyt_room_graph.py`, module layout service | Room graph tests | Partial | Needs direct visual room placement UX | Wire room graph into Map Studio viewport tools. |
| VIS editing | `vis_editor.py` | VIS/editor tests | Partial | Needs viewport culling preview workflow | Add UI previews and validation warnings. |
| WOK/walkmesh integration | `area_wok_integration.py`, `walkmesh_editor.py` | WOK tests | Partial | Needs seam and material overlay in main Map Studio | Add WOK overlay in KMAP viewport. |
| Placeables/NPCs/doors/triggers/waypoints | KMAP objects, module inspector, blueprint service | Some blueprint/module tests | Partial | Needs object palette and GIT/template writeback | Add object palette connected to typed template forms. |
| Scenario/cutscene authoring | `src/sequence/`, sequence editor | Sequence UI/model tests | Experimental | Needs dialogue/script/camera/combat binding | Build Scenario Workspace after Module/Map object placement. |
| Custom module packaging | `custom_module_packager.py` | Packager tests | Partial | Needs HoloPatcher/Patch Manager staging policy and game smoke checklist | Route packages through `ExportJob` and staging manifests. |

## Shared Infrastructure

| Capability | Existing implementation | Tests | Status | Gap | Recommended next task |
|---|---|---|---|---|---|
| Project/session document | `src/core/project/`, KMAX/KMAP/retarget/module refs | Project model tests plus KMAX/KMAP tests | Working foundation | Studios are not fully migrated | Gradually route studio state through `GhostRiggerProject`. |
| Resource provider | `game_library_ext.py`, PyKotor bridge, module loaders | MCP/resource tests | Partial | Resource lookup is still per subsystem | Add `GameResourceProvider`. |
| Validation reporting | `src/core/validation/validation_bus.py`, adapters, many subsystem validators | ValidationBus and subsystem tests | Working foundation | No shared Qt issue model/panel yet | Add model/view issue panel. |
| Export transactions | `src/core/export/export_job.py`, retarget export integration, module save pipeline, packager | ExportJob and retarget export tests | Working foundation | Module/Map/Character/FBX/Patch Manager not migrated | Migrate export surfaces through ExportJob. |
| Secret hygiene | `tests/test_secret_hygiene.py` | Secret hygiene test | Working | Keep local-only endpoint values out of docs/config | Include in CI and review all debug docs. |

## Scripting / GhostScripter Integration

| Capability | Existing implementation | Tests | Status | Gap | Recommended next task |
|---|---|---|---|---|---|
| GhostScripter repo integration | Optional path requested, not present locally; main window has IPC ping to port 7002 | None in this repo | Unknown | Source unavailable in audited workspace | Keep as separate repo/tool; design `ScriptService` bridge. |
| NSS/NCS compile/decompile | PyKotor has NCS/NSS format/compiler modules; GhostRigger has MCP/decompile tooling | MCP tests | Partial | No GhostRigger product-facing script service | Wrap PyKotor/GhostScripter through a bridge. |
| Trigger/dialog/action templates | Not found as productized GhostRigger templates | Unknown | Missing/Unknown | Scenario Authoring needs template generation | Add script template registry after Module/Map object placement. |

## Validation / Export / Package Systems

| Capability | Existing implementation | Tests | Status | Gap | Recommended next task |
|---|---|---|---|---|---|
| Animation structural validation | `animation_block_validator.py` | Retarget validation tests | Working | Continue expanding writer-specific checks | Keep as Retarget Studio gate. |
| Animation roundtrip verification | `animation_roundtrip_validator.py` | MDL animation roundtrip tests | Working/Partial | Real game smoke still revealed MDL writer gaps | Add regression fixtures for full hierarchy/controller export. |
| Module save/readback | `module_save_pipeline.py` | Module save tests | Partial | Needs transaction and reload diff in UI | Move through `ExportJob` and provider-backed reload comparison. |
| KMAP export manifest | `level_export_bridge.py`, `level_manifest.py` | Level export tests | Partial | FBX mesh assembly pending | Keep manifest-first until assembly is safe. |
| Custom module package | `custom_module_packager.py` | Packager tests | Partial | Needs install staging and external validator hooks | Add package export transaction. |
