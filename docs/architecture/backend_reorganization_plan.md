# Backend Reorganization Plan

Date: 2026-05-31

This plan tracks the incremental move of reusable backend logic out of GUI
packages while keeping public import paths stable during migration.

## Lockdown Status

As of 2026-06-01, the broad backend/GUI split is in the stabilization phase.
The remaining work is tracked as a punch list rather than a single open-ended
move:

| Item | Status | Notes |
|---|---|---|
| Required adapter sources must be tracked despite broad local diagnostic ignores. | Locked | `.gitignore` explicitly un-ignores `src/adapters/rendering/gpu_diagnostics_exports.py`, and a source-contract test checks that required adapter module stays visible to Git. |
| Decide compatibility-facade permanence. | Locked | The compatibility-facade policy below freezes `src.core.qt_core` as public legacy API and marks old GUI backend-style roots as transitional compatibility paths. New runtime code must not import these facades. |
| Add named core port boundaries. | In use | `src.core.ports` names the stable headless boundaries for `GameResourceProvider`, `TextureDecoder`, `ViewportRendererPort`, `ScriptCompilerPort`, and `FileWriterPort`. The resource browser now consumes `GameResourceProvider` records through the port package, `ExportJobContext` structurally implements `FileWriterPort` for staged writes, UE5 workbench handoff files can be written through an injected `FileWriterPort`, viewport renderer adapters/factory proxies consume `ViewportRendererPort`, and script compile requests have an explicit unavailable `ScriptCompilerPort` adapter. Additional callers should migrate when their workflow slice is touched. |
| Classify still-headless top-level packages. | Locked | `src.formats`, `src.io`, `src.resources`, `src.unreal`, `src.workbench`, and `src.systems` are classified in the package map and guarded as headless packages. |
| Keep workflow services on `ResourceAddress`, `GameResourceProvider`, `ValidationReport` / `ValidationBus`, and `ExportJob`. | Ongoing | These service records exist and are guarded where introduced; export writers should use `ExportJobContext.write_bytes` / `write_text` for staged file writes instead of adding new ad-hoc write pipelines. Future product slices should keep using the shared resource, validation, and export primitives. |
| Final verification pass. | Repeat per slice | Prefer targeted `py_compile`, source-contract tests, renderer/lightmap/camera/sequence tests tied to touched modules, and visible app testing only when UI/startup/viewport behavior changes. |

## Dependency Direction

```text
Qt widgets and dialogs
-> GUI controllers and view-models
-> application services and use cases
-> domain models and DTOs
-> ports and interfaces
-> adapters for PyKotor, filesystem, Blender, FBX SDK, GPU, Qt viewport, MCP
```

Backend packages must not import `src.gui` unless the module is explicitly a GUI
adapter. Compatibility facades may remain under old paths while callers migrate,
but facades must stay lazy or logic-free.

The source-contract tests enforce this as a migration guardrail:
`test_backend_packages_do_not_import_gui_directly` scans headless backend,
tooling, and integration packages for real `src.gui` imports;
`test_tracked_non_contract_tests_use_backend_owners_not_gui_facades` keeps
ordinary tracked tests on canonical backend owners; and
`test_gui_backend_compatibility_paths_stay_thin` prevents old GUI
backend-like folders from growing new implementation classes or functions.
Backend-behavior contract tests also use canonical `src.core.*` and
`src.adapters.*` owners for camera DTOs, transform-gizmo behavior, renderer
adapter behavior, BAS renderer contracts, GPU transform math, and software frame
rendering, leaving old `src.gui.*` imports only in explicit compatibility
assertions.
`test_gui_backend_compatibility_paths_do_not_use_wildcard_reexports` prevents
those old paths from returning to wildcard re-export or `globals().update`
symbol-table copying.
`test_core_implementation_modules_do_not_manipulate_sys_path` keeps core
implementation modules on package imports instead of local `sys.path` hacks.
The explicit exemptions are public lazy facades that intentionally aggregate
compatibility names while old implementation paths are reduced to logic-free
aliases or explicit lazy forwarding.

## Compatibility Facade Policy

New runtime code must not import these facades. Compatibility imports exist only
to keep old public paths working while implementation owners live under
`src.core`, `src.adapters`, or `src.math`.

| Facade root | Decision | Allowed implementation shape | Retirement candidates |
|---|---|---|---|
| `src.core.qt_core` | Frozen public compatibility API | Lazy backend facade that forwards to canonical `src.core.*`, `src.adapters.*`, and `src.math.*` owners. Do not teach or use this route in new code. | Individual submodule paths can retire only after a documented public deprecation window and source-contract proof that in-repo runtime/tests no longer need them outside explicit compatibility assertions. |
| `src.gui.camera` | Transitional compatibility path | Package root may use explicit lazy forwarding; module files must be logic-free aliases over `src.core.camera`, `src.adapters.qt_viewport`, or `src.math.camera_math`. | Module-level camera DTO/workflow aliases once external compatibility policy allows removing old GUI backend-style imports. |
| `src.gui.lighting` | Transitional compatibility path | Package root may use explicit lazy forwarding; module files must be logic-free aliases over `src.core.lighting`, `src.adapters.gpu`, `src.adapters.qt_viewport`, or dialog-owned Qt worker modules. | Backend/domain/lightmap aliases after public deprecation; Qt worker alias after dialogs consistently own the public surface. |
| `src.gui.rendering` | Transitional compatibility path | Renderer-neutral modules alias `src.core.rendering`; concrete renderer paths alias `src.adapters.rendering`; public GPU/WGPU export tables must use explicit lazy forwarding only. | Backend-style rendering aliases after external users move to `src.core.rendering` or `src.adapters.rendering`; public aggregate renderer facades stay until a renderer-plugin API replaces them. |
| `src.gui.textures` | Transitional compatibility path | Module files must be logic-free aliases over `src.core.graphics` texture and atlas helpers. | Texture helper aliases after external callers move to `src.core.graphics`. |
| `src.gui.gizmo` | Transitional compatibility path | Package root may use explicit lazy forwarding; module files must be logic-free aliases over `src.core.gizmo` or `src.math.transform_math`. | Transform-gizmo aliases after external callers move to `src.core.gizmo` and `src.math.transform_math`. |

The canonical GUI facade remains `src.gui.qt_lib`; this table is only about old
backend-style GUI paths and the backend `qt_core` compatibility route.

## Current Boundary Leaks

| Backend caller | Current GUI dependency | Target owner | Status |
|---|---|---|---|
| `src/core/game/kotor_install.py` | `src.gui.textures.tpc` | `src.core.graphics.tpc` | Migrated |
| `src/sequence/sequence_render.py` | `src.gui.camera.*` | `src.core.camera` plus `src.adapters.qt_viewport` | Migrated through explicit Qt viewport adapter |
| `src/core/validation/viewport_validator.py` | `src.gui.camera.arcball_camera`, `src.gui.rendering.frame_core.renderer` | `src.core.camera`, `src.core.rendering.frame_core`, `src.adapters.qt_viewport` | Migrated through explicit Qt viewport adapter and backend software renderer |
| `src/math/gpu_math.py` | `src.gui.rendering.gpu_core.diagnostics` | `src.math.gpu_math` local helper | Migrated |
| `src/converters/mesh_converter.py` | `src.gui.lighting.lightmap_export_bridge` | `src.core.lighting.lightmap_export_bridge` | Migrated; bake pipeline split into core service plus GPU adapter |

## Package Map

| Old path | New owner | Reason | Compatibility strategy | Targeted tests |
|---|---|---|---|---|
| `src.gui.textures.tpc` | `src.core.graphics.tpc` | TPC detection, DXT decode, image loading, and embedded TXI extraction are headless KOTOR texture-format logic. | Keep `src.gui.textures.tpc` as a logic-free module alias until old public imports are retired. | `py_compile`; import smoke for old and new paths; `tests/test_core_contracts.py::test_texture_format_helpers_are_backend_owned`; `tests/test_regression.py::test_k2_rgba_lightmap_txi_starts_at_clean_boundary`. |
| `src.gui.textures.txi` | `src.core.graphics.txi` | TXI parsing and material metadata application are headless texture-format logic. | Keep `src.gui.textures.txi` as a logic-free module alias until old public imports are retired. | `py_compile`; import smoke for old and new paths; `tests/test_core_contracts.py::test_texture_format_helpers_are_backend_owned`; `tests/test_regression.py::test_k2_rgba_lightmap_txi_starts_at_clean_boundary`. |
| `src.gui.textures.tpc_render_utils` and `src.gui.textures.qt_tpc_render_utils` | `src.core.graphics.tpc_render_utils` | TPC/DXT image loading and PIL triangle texture paste helpers are headless render/texture utilities. | Keep GUI and Qt-prefixed paths as logic-free module aliases over the backend owner. | `py_compile`; import smoke for old and new paths; `tests/test_core_contracts.py::test_tpc_render_utils_are_backend_owned`. |
| `src.gui.rendering.accel` and `src.gui.textures.tex_atlas` | `src.core.rendering.accel` and `src.core.graphics.tex_atlas` | Software-render acceleration and PIL-to-NumPy texture-array caches are headless render/graphics support. | Keep GUI paths and Qt-prefixed paths as logic-free module aliases; frame-core dependencies import the backend owners directly. | `py_compile`; `tests/test_core_contracts.py::test_software_render_accel_and_texture_array_cache_are_backend_owned`; targeted Qt import checks. |
| `src.gui.camera` package root | `src.core.camera` and `src.adapters.qt_viewport.still_frame_renderer` | The package root is a public compatibility entrypoint, not an owner for camera DTOs, camera managers, render settings, or still-frame viewport capture. | Preserve package attributes through an explicit lazy forwarding map; do not eager-import backend classes from the GUI package root. | `py_compile`; `tests/test_core_contracts.py::test_camera_state_and_dtos_are_backend_owned`; `tests/test_core_contracts.py::test_camera_workflow_state_is_backend_owned`; thin-facade guard. |
| `src.gui.camera.arcball_camera` and camera DTO modules | `src.core.camera` | Camera state and render request/result DTOs are reusable outside Qt widgets. | Keep GUI facades for existing viewport/tests as logic-free module aliases, but internal backend callers migrate to `src.core.camera`. | `py_compile`; import smoke for old and new paths; `tests/test_core_contracts.py::test_camera_state_and_dtos_are_backend_owned`; focused camera contract tests. |
| `src.gui.camera.camera_controller`, `camera_viewport_adapter`, `camera_manager`, `camera_picker`, camera presets, selection/target/rig records, and render manifest | `src.core.camera` | Scene camera workflow orchestration, ArcBall camera state adaptation, projected camera-handle picking, preset records, selection state, target/rig DTOs, and still-render manifests are headless camera application/domain support. | Keep old GUI camera paths as logic-free module aliases over the backend owners; GUI panels and viewport shared dependencies import the backend owner directly. | `py_compile`; import smoke for old and new paths; `tests/test_core_contracts.py::test_camera_workflow_state_is_backend_owned`; focused camera manager/render-frame contracts. |
| `src.core.animation.skinning_profiles.generated_character_skinning` | `src.core.animation.skinning_profiles.types.generated_character_skinning` | Generated per-resource skinning registry data belongs with typed skinning-profile data, while the older import path remains public compatibility. | Preserve the old core path as a package-relative module alias so both `src.core` and `core` import layouts resolve to the typed owner. | `py_compile`; import smoke for old and typed paths; `tests/test_core_contracts.py::test_animation_skinning_profiles_include_generated_character_registry`. |
| `src.gui.rendering.gpu_core.diagnostics._matrix_from_pos_quat_np` and `src.gui.rendering.gpu_core.math_helpers` | `src.math.gpu_math` | Matrix construction and scene GPU transform helpers are shared math, not GUI diagnostics ownership. | Keep old diagnostics attributes and the old math-helper module path as compatibility routes to the canonical math helper. | `py_compile`; `tests/test_core_contracts.py::test_gpu_matrix_helper_is_math_owned`. |
| `src.gui.lighting.lightmap_export_bridge` | `src.core.lighting.lightmap_export_bridge` | Generated-lightmap export manifests are headless conversion/export logic. | Keep the old GUI path as a logic-free module alias until callers migrate. | `py_compile`; `tests/test_core_contracts.py::test_lightmap_export_bridge_is_backend_owned`; `tests/test_lightmap_baker.py::test_lightmap_export_bridge_discovers_generated_assignments`. |
| Direct backend imports of Qt viewport renderers | `src.adapters.qt_viewport.frame_renderer` | Sequence image export and validation capture still rely on Qt/viewport rendering, so the dependency should be an explicit adapter boundary. | Backend callers import adapter factory functions; the adapter imports GUI implementation details. | `py_compile`; `tests/test_core_contracts.py::test_backend_renderer_dependencies_use_qt_viewport_adapter`; targeted sequence/validation import checks. |
| `src.gui.camera.frame_renderer` | `src.adapters.qt_viewport.still_frame_renderer` | Still-frame export drives the active Qt viewport render pipeline and therefore belongs to the explicit Qt viewport adapter boundary rather than GUI camera DTO ownership. | Preserve `src.gui.camera.frame_renderer` as a logic-free module alias; viewport shared dependencies and adapter factories import the adapter owner directly. | `py_compile`; import smoke for old/new paths; `tests/test_core_contracts.py::test_still_frame_renderer_suppresses_viewport_camera_overlays`; Qt facade checks. |
| `src.gui.camera.camera_overlays` | `src.adapters.qt_viewport.camera_overlays` | Letterbox/safe-frame/guide overlay drawing is part of Qt viewport capture/presentation, not reusable camera domain ownership, and adapter code should not import it from GUI. | Preserve `src.gui.camera.camera_overlays` as a logic-free module alias and `src.gui.qt_lib.camera.camera_overlays` as a compatibility facade; viewport dependencies and still-frame export import the adapter owner directly. | `py_compile`; import smoke for old/new paths; `tests/test_core_contracts.py::test_camera_overlays_are_qt_viewport_adapter_owned`; still-frame overlay regression. |
| `src.gui.camera.camera_gizmo_renderer` | `src.adapters.qt_viewport.camera_gizmo_renderer` | Camera helper/frustum drawing is viewport adapter presentation code over backend camera DTOs and math helpers, not GUI camera-domain ownership. | Preserve `src.gui.camera.camera_gizmo_renderer` as a logic-free module alias and `src.gui.qt_lib.camera.camera_gizmo_renderer` as a compatibility facade; viewport dependencies import the adapter owner directly. | `py_compile`; import smoke for old/new paths; `tests/test_core_contracts.py::test_camera_gizmo_renderer_is_qt_viewport_adapter_owned`; targeted Qt facade checks. |
| `src.gui.lighting.lighting_viewport_controller` | `src.adapters.qt_viewport.lighting_viewport_controller` | Applying lighting UI state to renderer attributes is viewport adapter wiring over backend lighting state, not GUI lighting domain ownership. | Preserve the old GUI path as a logic-free module alias and the `src.gui.qt_lib` route as a compatibility facade; new code imports the adapter owner directly. | `py_compile`; import smoke for old/new paths; `tests/test_core_contracts.py::test_lighting_preview_state_and_cache_are_backend_owned`; targeted Qt facade checks. |
| `src.gui.lighting.lightmap_*` support modules, UV atlas/channel helpers, and raycast helpers | `src.core.lighting` | Lightmap settings/jobs, manifests, output, padding, rasterization, UV validation, atlas generation, sampling, denoise/compare, and lighting/shadow solve helpers are headless services. | GUI panels/workers call backend services; the GPU-context solver now lives behind an explicit adapter. Old GUI support-module paths remain logic-free module aliases. | `py_compile`; import smoke for old and new paths; `tests/test_core_contracts.py::test_lightmap_bake_support_helpers_are_backend_owned`; `tests/test_lightmap_baker.py`. |
| `src.gui.lighting.lightmap_baker` pipeline | `src.core.lighting.lightmap_baker` plus `src.adapters.gpu.lightmap_baker` | The bake orchestration pipeline is a headless service over core lightmap dependencies. The GPU-default baker is a concrete adapter because it wires the backend pipeline to the ModernGL lightmap solver. | `src.core.lighting.lightmap_baker.LightmapBaker` defaults to the CPU lighting solver; `src.adapters.gpu.lightmap_baker.LightmapBaker` subclasses it and injects `LightmapGpuSolver`; the old GUI baker path is a logic-free facade. | `py_compile`; import smoke for core/adapter/facade paths; `tests/test_core_contracts.py::test_lightmap_baker_pipeline_is_backend_owned_with_gui_gpu_adapter`; `tests/test_lightmap_baker.py`. |
| `src.gui.lighting.lightmap_bake_worker` | `src.gui.dialogs.lightmap_bake_worker` | The bake worker is a Qt dialog worker, not reusable lighting backend logic, and `src.gui.lighting` is reserved for compatibility facades over backend/adapters. | Preserve the old GUI lighting path as a logic-free module alias; `QtLightmapBakerDialog` imports the dialog-owned worker directly. | `py_compile`; import smoke for old/new paths; `tests/test_core_contracts.py::test_gui_backend_compatibility_paths_stay_thin`; `tests/test_core_contracts.py::test_lightmap_baker_pipeline_is_backend_owned_with_gui_gpu_adapter`. |
| `src.gui.lighting.lightmap_gpu_solver` | `src.adapters.gpu.lightmap_gpu_solver` | The ModernGL direct-light solver is a concrete GPU adapter over core lightmap buffers and solver fallback, not GUI lighting product logic. | Keep the old GUI path as a logic-free module alias and preserve the `src.gui.qt_lib` facade; GUI baker imports the adapter owner directly. | `py_compile`; import smoke for adapter/old GUI/qt_lib paths; `tests/test_core_contracts.py::test_lightmap_gpu_solver_is_explicit_gpu_adapter`; focused lightmap GPU fallback test. |
| `src.gui.rendering.gpu_core.diagnostics` ModernGL context/runtime/probe setup | `src.adapters.gpu.moderngl_context`, `src.adapters.gpu.moderngl_runtime`, `src.adapters.gpu.viewport_probe`, and `src.adapters.rendering.gpu_diagnostics_exports` | Standalone ModernGL context creation, backend selection, optional runtime imports, GPU-skinning availability, env-gated VBO probe output, and compatibility aggregation are concrete GPU/renderer adapter concerns, not GUI diagnostics ownership. | Keep GUI diagnostics as a logic-free alias over the adapter-owned export table; the export table uses explicit name-to-owner entries instead of wildcard-copying symbols or walking target-module `__all__`, GPU adapters and ModernGL resource/renderer modules import adapter/runtime/probe owners directly, and the public renderer facade routes individual helpers to core or adapter owners. | `py_compile`; import smoke for adapter/old/public paths; `tests/test_core_contracts.py::test_lightmap_gpu_solver_is_explicit_gpu_adapter`; `tests/test_core_contracts.py::test_gui_backend_compatibility_paths_stay_thin`; focused GPU diagnostic tests. |
| `src.gui.lighting` package root | `src.core.lighting` | The package root is a public compatibility entrypoint, not an owner for light models, light groups, light managers, or lighting enums. | Preserve package attributes through an explicit lazy forwarding map; do not eager-import backend lighting classes from the GUI package root. | `py_compile`; `tests/test_core_contracts.py::test_lighting_domain_and_render_data_are_backend_owned`; thin-facade guard. |
| `src.gui.lighting` domain records and renderer-neutral lighting snapshots | `src.core.lighting` | Light models, enums, selection/grouping, Aurora conversion, generated rig recipes, export records, helper geometry policy, lighting settings, shader-complexity scoring, and render-data snapshots are headless domain/application support. | GUI panels, pickers, viewport controllers, dialogs, and render hosts import `src.core.lighting` directly; old GUI and `src.gui.qt_lib` domain paths remain logic-free module aliases or facades. | `py_compile`; `tests/test_core_contracts.py::test_lighting_domain_and_render_data_are_backend_owned`; `tests/test_wgpu_lighting_integration.py`; focused lighting panel/render-data contracts. |
| `src.gui.lighting.lightmap_controller`, `material_map_controller`, and `preview_cache` | `src.core.lighting` | Lightmap preview state, material-map toggle state, and deterministic preview cache keys are headless viewport/application state, not widgets. | Keep old GUI paths as logic-free module aliases; GUI baker and viewport bridge import the core owners directly. | `py_compile`; import smoke for old/new/facade paths; `tests/test_core_contracts.py::test_lighting_preview_state_and_cache_are_backend_owned`; focused lightmap baker checks. |
| `src.gui.lighting.light_picker` | `src.core.lighting.light_picker` | Light helper hit-testing is screen-space picking policy with injected projection and transform callbacks, not Qt widget code. | Keep the old GUI path as a logic-free module alias and preserve the `src.gui.qt_lib` facade; viewport shared dependencies import the core owner directly. | `py_compile`; import smoke for old/new/facade paths; `tests/test_core_contracts.py::test_light_picker_is_backend_owned`; focused light-picker test. |
| `src.gui.rendering.picking`, renderer settings/capabilities/interface/backend, renderer performance/profiler, hardware diagnostics, viewport display DTOs | `src.core.rendering` | Renderer contracts, CPU picking math, display state, frame pacing, profiling, and diagnostics are renderer-neutral backend support. | Preserve `src.gui.rendering.*`, `src.gui.viewports.viewport_display`, and `src.gui.qt_lib` routes as public compatibility facades; old GUI rendering contract/display paths are logic-free module aliases and runtime code imports `src.core.rendering` directly. | `py_compile`; import smoke for old and new paths; `tests/test_core_contracts.py::test_renderer_contract_helpers_are_backend_owned`; renderer backend/stage focused tests. |
| `src.gui.viewports.viewport_navigation` profile definitions and `src.gui.rendering.viewport_navigation` shim | `src.core.rendering.viewport_navigation` | Navigation profile records, labels, help text, and normalization are renderer-neutral settings data; core should not import PySide6 just to normalize profile values. | Preserve `src.gui.viewports.viewport_navigation`, `src.gui.rendering.viewport_navigation`, and `src.gui.qt_lib.viewports.viewport_navigation` as compatibility facades; `src.gui.rendering.viewport_navigation` is a logic-free module alias and runtime code imports `src.core.rendering.viewport_navigation` directly. GUI event code may still pass Qt modifier objects into the backend-owned bitmask helper. | `py_compile`; import smoke for old/new/facade paths; `tests/test_core_contracts.py::test_renderer_contract_helpers_are_backend_owned`; `tests/test_core_contracts.py::test_viewport_navigation_profiles_are_available`; runtime import scan for old GUI navigation paths. |
| Duplicate renderer `_hex_to_rgb_float` helpers | `src.core.rendering.color_utils` | Hex color parsing is renderer-neutral support shared by ModernGL and WGPU adapters, not GUI diagnostics or WGPU resource ownership. | GPU diagnostics and WGPU shared import the backend helper; public GPU/WGPU renderer facades route the helper to core. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_renderer_color_utils_are_backend_owned`. |
| `src.gui.rendering.gpu_core.debug_tables` | `src.core.rendering.gpu_debug_tables` | Per-model material/UV/texture diagnostic table generation is backend rendering diagnostics, not GUI adapter logic. | Preserve the old GPU-core path as a logic-free module alias; ModernGL renderer imports the backend owner directly and the public `gpu_renderer` facade exports the backend route. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_gpu_debug_tables_are_backend_owned`; targeted diagnostic table smoke. |
| Environment/config subset of `src.gui.rendering.gpu_core.diagnostics` | `src.core.rendering.gpu_diagnostics_config` | Diagnostic trace/dump paths and debug visualization mode selectors are environment-driven backend configuration, not GUI adapter logic. | The adapter-owned diagnostics export table imports and re-exports the backend owner; public `gpu_renderer` facade routes these helpers to core. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_gpu_diagnostics_config_is_backend_owned`; focused diagnostic env regression tests. |
| Pure heuristic/record subset of `src.gui.rendering.gpu_core.diagnostics` | `src.core.rendering.gpu_diagnostics_records` | Diagnostic data-shaping helpers and renderer-neutral heuristics should be reusable backend rendering support, while ModernGL context/runtime/probe behavior remains adapter-owned. | Keep `src.gui.rendering.gpu_core.diagnostics` as a logic-free module alias over `src.adapters.rendering.gpu_diagnostics_exports`; public `gpu_renderer` facade routes migrated helpers to core or adapters. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_gpu_diagnostics_records_are_backend_owned`; focused GPU diagnostic regression tests. |
| GPU VBO layout constants and `_split_vbo_attributes_for_gpu` from `src.gui.rendering.gpu_core.resources` | `src.core.rendering.gpu_vbo_layout` | The split between packed float attributes and integer bone IDs is a pure renderer data-layout contract shared by diagnostics, resources, and public facades, not GUI resource-cache ownership. | Keep `_build_vbo_data` in the existing ModernGL resource adapter for now; GPU resources, diagnostics records, public `gpu_renderer`, and `src.core.qt_core` import or route the backend layout owner. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_gpu_vbo_layout_helpers_are_backend_owned`; focused GPU skin VBO layout regressions. |
| `src.gui.rendering.gpu_core.shaders` | `src.core.rendering.gpu_shaders` | ModernGL shader source strings are renderer backend data and do not depend on a GUI surface or GL context. | Preserve the old GPU-core path as a logic-free module alias; ModernGL renderer imports the backend owner directly and the public `gpu_renderer` facade exports the backend route. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_gpu_shader_sources_are_backend_owned`; shader contract tests. |
| Pure helper subset of `src.gui.rendering.gpu_core.scene_helpers` | `src.core.rendering.gpu_scene_helpers` | Model bounds, TPC/TXI metadata application, base-skeleton constant re-export, and supermodel composite wrappers are model/texture helpers used by render adapters, not GUI presentation. | The old GUI scene-helper path is a logic-free module alias over `src.adapters.rendering.moderngl_scene_helpers`; public facade routes pure helpers to core and the concrete autoframe renderer to the adapter owner. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_gpu_scene_helpers_are_backend_owned`; focused GPU renderer/autoframe import checks. |
| `src.gui.rendering.gpu_core.scene_helpers.render_model_autoframe` | `src.adapters.rendering.moderngl_scene_helpers` | Autoframe rendering creates and drives a concrete ModernGL `GpuRenderer`, so it belongs to the renderer adapter boundary rather than GUI package ownership. | Preserve `src.gui.rendering.gpu_core.scene_helpers` as a module alias over the adapter owner and `src.gui.rendering.gpu_renderer` as a lazy compatibility facade; MCP/debug tooling imports the adapter owner directly. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_gpu_scene_helpers_are_backend_owned`; targeted Qt facade checks. |
| `src.gui.rendering.wgpu_core.shaders` and `src/gui/rendering/shaders/*.wgsl` | `src.core.rendering.wgpu_shaders` and `src/core/rendering/shaders/*.wgsl` | WGPU shader source loading, inline fallback strings, and WGSL assets are renderer backend data and do not depend on a GUI surface or WGPU device. | Preserve the old WGPU-core Python path as a logic-free module alias; WGPU renderer imports the backend shader helpers/constants by explicit name and the public `wgpu_renderer` facade exports the backend route. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_wgpu_shader_sources_are_backend_owned`; focused WGPU shader source tests. |
| Pure DTO/helper subset of `src.gui.rendering.wgpu_core.shared` | `src.core.rendering.wgpu_shared` | WGPU resource records, backend-selection constants, color conversion, projection/view matrix helpers, and adapter-info extraction are pure renderer support, while Qt/rendercanvas probing remains GUI adapter-owned. | Keep `src.gui.rendering.wgpu_core.shared` as the WGPU adapter surface that re-exports backend helpers through explicit named imports and owns the probe script; public `wgpu_renderer` exports pure helpers from `src.core.rendering.wgpu_shared`. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_wgpu_shared_dtos_and_helpers_are_backend_owned`; focused WGPU color/backend-selection tests. |
| `src.gui.rendering.skeleton_render_data` | `src.core.rendering.skeleton_render_data` | Skeleton overlay DTOs, skinning arrays, and CPU skinning fallback helpers are backend render data, not widget code. | Preserve `src.gui.rendering.skeleton_render_data` as a logic-free module alias while runtime callers migrate to `src.core.rendering`. | `py_compile`; `tests/test_core_contracts.py::test_skeleton_render_data_is_backend_owned`; `tests/test_wgpu_stage7_render_data.py` focused cases. |
| `src.gui.rendering.mesh_render_data` adapter wrapper | `src.adapters.rendering.mesh_render_data` over `src.core.rendering.mesh_render_data` | Mesh/material render-data DTOs, material extraction, texture conversion, world-matrix helpers, normal smoothing, and BAS attachment transforms are backend render-data support. The ModernGL VBO builder is adapter-owned and injected where needed. | Preserve `src.gui.rendering.mesh_render_data` as a logic-free module alias over `src.adapters.rendering.mesh_render_data`; the adapter lazily forwards core names and explicitly overrides VBO-injected helpers, while WGPU runtime callers import `src.core.rendering.mesh_render_data` and pass the adapter VBO builder explicitly. | `py_compile`; `tests/test_core_contracts.py::test_mesh_render_data_is_backend_owned_with_gui_vbo_adapter`; WGPU stage render-data cases; focused regression cases for `_build_vbo_data` parity through the adapter facade. |
| `src.gui.rendering.renderer_factory`, `null_renderer`, `moderngl_renderer`, and `direct3d_renderer` | `src.adapters.rendering` | Backend selection and concrete viewport renderer adapters are runtime adapter wiring, not GUI package ownership or core renderer contracts. | Preserve the old GUI renderer paths as logic-free module aliases; alias the old renderer-factory module to the adapter owner so monkeypatch/import workflows keep targeting the implementation module. | `py_compile`; import smoke for old/new paths; `tests/test_core_contracts.py::test_viewport_renderer_adapters_have_explicit_owner`; focused renderer backend-selection tests. |
| `src.gui.rendering.wgpu_core` and WGPU renderer implementation route in `src.gui.rendering.wgpu_renderer` | `src.adapters.rendering.wgpu_core` | The WGPU renderer owns Qt/rendercanvas surface creation and wgpu device resources, so it is a concrete viewport renderer adapter rather than reusable GUI presentation or core rendering logic. | Preserve old `src.gui.rendering.wgpu_core.*` module paths as aliases and keep `src.gui.rendering.wgpu_renderer` as the public lazy facade; route WGPU implementation exports to the adapter owner. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_viewport_renderer_adapters_have_explicit_owner`; focused WGPU renderer/backend tests. |
| `src.gui.rendering.gpu_core.renderer` ModernGL renderer implementation | `src.adapters.rendering.moderngl_renderer_impl` | The concrete ModernGL renderer is a rendering adapter over ModernGL runtime/context services and core render data, not GUI widget code. | Preserve `src.gui.rendering.gpu_core.renderer` as a logic-free module alias; keep `src.adapters.rendering.moderngl_legacy_bridge` as a stable compatibility route while callers migrate to focused adapter owners. | `py_compile`; import smoke for old/bridge/new/public paths; `tests/test_core_contracts.py::test_adapter_gui_imports_are_explicit_boundary_bridges`; `tests/test_core_contracts.py::test_viewport_renderer_adapters_have_explicit_owner`; focused ModernGL/BAS source contracts. |
| Public GPU renderer export table in `src.gui.rendering.gpu_renderer` and Qt route in `src.gui.rendering.qt_gpu_renderer` | `src.adapters.rendering.gpu_renderer_exports` | The lazy compatibility table aggregates core rendering helpers and concrete adapter exports, so its owner should be the adapter boundary rather than a GUI package. | Preserve both old GUI paths as logic-free compatibility facades over the adapter export table; `qt_gpu_renderer` uses lazy attribute forwarding for GPU exports and Qt-facing renderer-factory aliases from `src.adapters.rendering.renderer_factory`. | `py_compile`; import smoke for adapter/old GUI/Qt routes; `tests/test_core_contracts.py::test_runtime_sources_do_not_import_gui_backend_facades`; `tests/test_core_contracts.py::test_gui_backend_compatibility_paths_stay_thin`; `tests/test_core_contracts.py::test_viewport_renderer_adapters_have_explicit_owner`. |
| Public WGPU renderer export table in `src.gui.rendering.wgpu_renderer` | `src.adapters.rendering.wgpu_renderer_exports` | The lazy WGPU compatibility table aggregates core WGPU DTOs/shaders and concrete WGPU adapter exports, so it belongs at the adapter boundary rather than in the GUI package. | Preserve `src.gui.rendering.wgpu_renderer` as a logic-free alias facade over an explicit adapter export table; avoid broad fallback module probing so only deliberate compatibility names are exposed. | `py_compile`; import smoke for adapter/old GUI/qt_lib routes; `tests/test_core_contracts.py::test_gui_backend_compatibility_paths_stay_thin`; `tests/test_core_contracts.py::test_viewport_renderer_adapters_have_explicit_owner`; WGPU shader/shared focused contracts. |
| `src.gui.rendering.gpu_core.benchmark` and `src.gui.rendering.gpu_core.cli` | `src.adapters.rendering.moderngl_benchmark` and `src.adapters.rendering.moderngl_cli` | The ModernGL throughput benchmark and command-line smoke entry point are adapter tooling over the concrete renderer, not GUI package logic. | Preserve old GPU-core module paths as logic-free module aliases and route public `src.gui.rendering.gpu_renderer` exports to the adapter modules. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_gpu_benchmark_adapter_imports_renderer_dependencies_explicitly`; tiny benchmark smoke. |
| `src.gui.gizmo` transform gizmo mode, draw-data, picker, renderer, controller, and coordinator | `src.core.gizmo` | Transform gizmo state, screen-space picking policy, renderer-neutral draw commands, command generation, and drag application are headless transform workflow support. | Preserve old GUI gizmo module paths as logic-free module aliases over `src.core.gizmo`; keep the package root as an explicit lazy forwarding map so importing `src.gui.gizmo` does not eagerly import the backend package; viewport shared dependencies import `src.core.gizmo` directly. | `py_compile`; import smoke for old and new paths; `tests/test_core_contracts.py::test_transform_gizmo_helpers_are_backend_owned`; focused gizmo mode/transform tests. |
| `src.formats` | Headless file-format package for now; future split into `src.core.formats` or focused subsystem owners only when callers need domain-specific ownership. | GFF reader/writer/types are reusable binary/text format helpers and must not depend on Qt or GUI packages. | Keep public `src.formats.*` imports stable; GUI and backend code may consume it, but formats must remain headless and should migrate into core only with a deliberate compatibility plan. | `py_compile`; `tests/test_core_contracts.py::test_integration_packages_are_headless_and_classified`; focused GFF reader/writer tests when touched. |
| `src.infra` | Headless infrastructure package. | Process/service support such as MCP autostart is app infrastructure, not GUI presentation and not core domain logic. | Keep `src.infra.*` free of GUI and Qt imports; move GUI-specific startup affordances to explicit Qt adapters if they appear. | `py_compile`; `tests/test_core_contracts.py::test_integration_packages_are_headless_and_classified`; focused infra tests when touched. |
| `src.io.fbx` | External FBX IO adapter package. | FBX SDK path discovery, diagnostics, scene adaptation, import, and export bridge external Autodesk/FBX dependencies into GhostRigger data contracts. The SDK path mutation is adapter setup, not core domain behavior. | Keep public `src.io.fbx.*` imports stable; keep Autodesk SDK probing here or under a future `src.adapters.fbx` split, never in core domain modules or GUI widgets. | `py_compile`; `tests/test_core_contracts.py::test_integration_packages_are_headless_and_classified`; focused FBX diagnostics/import/export tests. |
| `src.measurement` | Headless measurement/domain utility package. | Unit systems, grid/angle/percent snapping, dimensions, and formatting are reusable viewport/tool services but not Qt widget code. | Keep public `src.measurement.*` imports stable and headless; GUI tools consume these services through viewport/tool controllers. | `py_compile`; `tests/test_core_contracts.py::test_integration_packages_are_headless_and_classified`; focused measurement tests when touched. |
| `src.mesh_tools` | Headless mesh-editing service package. | Mesh element types, topology, attach/bridge/connect/weld operations, selection conversion, history, preservation, and validation are reusable mesh-editing services, not GUI presentation. | Keep public `src.mesh_tools.*` imports stable and headless; GUI tools orchestrate these operations without owning the mesh logic. | `py_compile`; `tests/test_core_contracts.py::test_integration_packages_are_headless_and_classified`; focused mesh-tool tests when touched. |
| `src.resources` | Headless game-resource discovery package. | Game installation detection and library registration are resource-provider infrastructure consumed by GUI and backend workflows, not Qt presentation. | Keep public `src.resources.*` imports stable and headless; promote shared resource-provider contracts into `src.core.resources` only with a deliberate compatibility plan. | `py_compile`; `tests/test_core_contracts.py::test_integration_packages_are_headless_and_classified`; focused game-library tests when touched. |
| `src.autorig` | Headless autorig/cloth-rig service package with Qt presentation under `src.adapters.qt_autorig` | Auto-rigging, AcuRig, GRig, and cloth rigging are headless model-editing services used by GUI and workflows; optional dialogs belong behind an explicit Qt adapter. | Keep public `src.autorig.*` imports stable; compatibility dialog helpers in `cloth_rig.py` delegate to `src.adapters.qt_autorig.cloth_dialogs` without importing Qt in autorig modules. | `py_compile`; `tests/test_core_contracts.py::test_integration_packages_are_headless_and_classified`; focused autorig/cloth tests. |
| `src.ipc` GUI-thread callback dispatch | `src.adapters.qt_ipc.threading` | IPC client/server code is application infrastructure and should not import PySide directly; Qt event-loop scheduling is a presentation adapter concern. | Keep public IPC helper names stable; `src.ipc` delegates callback marshaling to the Qt IPC adapter and falls back to direct callback execution when no Qt loop is active. | `py_compile`; import smoke for client/server/adapter; `tests/test_core_contracts.py::test_ipc_callback_dispatch_uses_qt_adapter_boundary`; headless Qt/Tk source scan. |
| `src.unreal` | Unreal integration adapter package for now; future split into `src.adapters.unreal` only when more external Unreal services appear. | Quinn skeleton assets, Unreal bone-map loading, and Unreal/KOTOR retarget helpers are external-engine integration logic, not Qt GUI code and not generic core domain ownership. | Keep public `src.unreal.*` imports stable; enforce that the package stays headless and consumes core DTOs/services rather than GUI widgets. | `py_compile`; `tests/test_core_contracts.py::test_integration_packages_are_headless_and_classified`; focused Unreal retargeting tests. |
| `src.workbench` | Headless workbench/export service package for now. | UE5 rig export request/result code is a use-case service consumed by UI and tests; it should remain free of Qt widgets until a dedicated GUI workbench surface owns presentation. | Keep public `src.workbench.*` imports stable; enforce headless dependencies and document any future split before moving modules. | `py_compile`; `tests/test_core_contracts.py::test_integration_packages_are_headless_and_classified`; `tests/test_workbench_ue5_rig_export.py`. |
| `src.systems` | Domain/system service package. | BAS attachment alignment and model-recipe logic are product-domain services shared by UI, renderers, and tests, not GUI presentation code. | Keep `src.systems.*` headless; GUI may consume it, but systems must not import GUI or Qt. | `py_compile`; `tests/test_core_contracts.py::test_integration_packages_are_headless_and_classified`; BAS contract tests. |
| `src.gui.rendering.frame_core` | `src.core.rendering.frame_core` | The PIL/software `FrameRenderer`, rasterizer, texture cache, colors, diagnostics, and mixins are Tk-free software-render backend code used by validation, scripts, and viewport hosts. | Preserve old `src.gui.rendering.frame_core.*`, `src.gui.rendering.viewport_core`, and `src.gui.viewports.frame_renderer` paths as logic-free module aliases; runtime callers import the backend owner directly. | `py_compile`; `tests/test_core_contracts.py::test_software_frame_renderer_is_backend_owned`; focused frame-renderer contracts; Qt import facade check. |
| `src.core.rendering.frame_core.math_helpers` | `src.math.frame_math` | Shared software frame-render math, UV, and sorting helpers belong in the project math package rather than a renderer backend shim. | Preserve the old frame-core math-helper path as a module alias over `src.math.frame_math`; frame-core runtime imports the canonical math owner directly. | `py_compile`; import smoke for old/new paths; `tests/test_core_contracts.py::test_software_frame_renderer_is_backend_owned`. |
| `src.core.ports` | Headless port boundary package. | Stable workflow boundaries should be named once instead of rediscovered through concrete services, GUI facades, or adapter implementation classes. | Re-export the existing `GameResourceProvider` protocol and `IViewportRenderer` as `ViewportRendererPort`; define initial `TextureDecoder`, `ScriptCompilerPort`, and `FileWriterPort` protocols for new slices. `src.gui.panels.qt_resource_browser_model` consumes resource provider records through the port package, `ExportJobContext` now provides staged `FileWriterPort` methods, `src.workbench.ue5_rig_export` accepts a `FileWriterPort` for manifest/setup-note handoff files with `src.adapters.files.LocalFileWriter` as the default, `src.adapters.rendering.null_renderer` plus the fallback renderer factory consume the viewport renderer contract through `ViewportRendererPort`, and `src.adapters.scripts.UnavailableScriptCompiler` provides a deterministic blocking `ScriptCompilerPort` fallback until a real NWScript compiler adapter exists. Migrate additional concrete callers when touched rather than forcing a broad churn pass. | `py_compile`; `tests/test_core_contracts.py::test_core_ports_define_named_headless_boundaries`; `tests/test_core_contracts.py::test_resource_browser_uses_core_ports_resource_boundary`; `tests/test_core_contracts.py::test_export_job_context_implements_file_writer_port`; `tests/test_core_contracts.py::test_local_file_writer_implements_file_writer_port`; `tests/test_core_contracts.py::test_null_renderer_uses_viewport_renderer_port_boundary`; `tests/test_core_contracts.py::test_renderer_factory_proxy_uses_viewport_renderer_port_boundary`; `tests/test_core_contracts.py::test_unavailable_script_compiler_implements_script_compiler_port`; targeted resource/export/renderer/script/workbench tests. |
| GPU/ModernGL/WGPU adapters | GUI or `src.adapters` where backend-specific | Qt/OpenGL/WGPU host integration remains adapter-owned until renderer ports are introduced. | Keep renderer adapters at explicit GUI/adapter boundaries and move reusable pieces to core when they become renderer-neutral. | Renderer backend/picking/stage tests tied to moved modules. |

## Slice Checklist

For each slice:

1. Move implementation to the owning backend package.
2. Leave old imports as thin compatibility facades only where needed.
3. Update internal runtime imports to the canonical owner.
4. Add import-contract coverage so backend packages cannot depend on `src.gui`.
5. Run `python -m py_compile` on changed modules and targeted pytest cases only.
6. Record the completed reorganization in `CHANGES.md`.

## Completed Slices

### Backend Import Boundary Guard

Added an AST source-contract test that scans `src/core`, `src/sequence`,
`src/converters`, `src/autorig`, `src/math`, `src/ipc`, `src/kotormcp`,
`src/unreal`, `src/workbench`, `src/systems`, `src/adapters/gpu`, and
`src/resources` for direct `src.gui` imports. Explicit adapters, such as the Qt
viewport adapter, remain the allowed place for GUI dependencies.

Added companion guardrails that keep ordinary tracked tests from importing
backend-owned camera, rendering, lighting, texture, or gizmo APIs through GUI
compatibility paths, and that keep old GUI backend-like folders thin by failing
when they grow new top-level classes or functions outside explicitly exempted
facades and remaining ModernGL implementation files.

Updated MCP tooling imports to consume canonical `src.core.*` and path-shim
`core.*` owners directly for model loading, texture decoding, resource
management, animation sampling, GPU skinning, Unity export/validation, and
Malak smoke helpers. A source contract now rejects `src.core.qt_core` and
`core.qt_core` references from `src/kotormcp`.

Updated selected core runtime modules to avoid the backend facade for sibling
core helpers: `kotor_loader` now imports vertex-space classification directly
from `src.core.geometry.vertex_space`; the lightmap rasterizer and mesh
render-data helpers import quaternion math directly from
`src.core.geometry.model_data`; and `resource_manager` uses its local resource
type constants without self-importing through `src.core.qt_core`.

Updated `src.core.graphics.tpc_render_utils` so both editable and bare-path
loader fallbacks route through canonical `core.game.kotor_loader` owners rather
than the backend facade.

Updated the software frame renderer backend to import geometry DTOs/quaternion
helpers, animation/dangly simulation, GPU-skinning palette helpers, walkmesh
draw data, render constants, and vertex-space enums from canonical `src.core.*`
packages rather than the `src.core.qt_core` facade.

Updated module layout, walkmesh, and hydration services to import
`module_format` and `module_loader` from canonical `src.core.modules` /
`core.modules` owners instead of `src.core.qt_core.modules`.

Updated `src.core.animation.animation_library` to import model loading and
animation-engine construction from canonical `src.core.game` and
`src.core.animation` owners instead of routing through `src.core.qt_core`.

Updated `src.core.assets.asset_preview` to import geometry DTOs, composite
workflow services, and model loading from canonical `src.core.geometry`,
`src.core.workflow`, and `src.core.game` owners instead of the backend facade.

Updated shared workflow scaffolding and the Supermodel composite workflow to
import geometry DTOs, validation services, character workflow services,
creature assembly helpers, workflow base utilities, and `SceneIO` from
canonical `src.core.*` owners instead of routing through `src.core.qt_core`.

Updated the Head and Headless Body character workflow services to import
workflow base helpers, model DTOs, validation services, character-builder
helpers, KOTOR loaders, interchange importers, animation supermodel resolution,
MDL writing, `SceneIO`, and LIP reading from canonical `src.core.*` owners
instead of routing through `src.core.qt_core`.

Updated the Character Builder backend service to import MDL parser/writer
helpers, KOTOR install/load helpers, geometry DTO flags, and creature assembly
from canonical `src.core.*` / `core.*` owners instead of routing through
`src.core.qt_core` / `core.qt_core`.

Updated the template builder backend service to import geometry DTOs and KOTOR
model loading from canonical `src.core.*` / `core.*` owners instead of routing
through `src.core.qt_core` / `core.qt_core`.

Updated the animation-retargeting skeleton template picker to import the
Character Builder backend from canonical `src.core.characters` /
`core.characters` owners instead of routing through the backend facade.

Updated remaining non-facade `src.core` usage examples and package docs so they
point at canonical backend owners rather than teaching the compatibility facade
as the default route. A broad source-contract guard now rejects
`src.core.qt_core` / `core.qt_core` references anywhere under `src/core` except
the facade files themselves.

Added a broader facade-route source contract for headless backend packages and
scripts so `src/core`, `src/sequence`, `src/converters`, `src/autorig`,
`src/math`, `src/ipc`, `src/kotormcp`, `src/unreal`, `src/workbench`,
`src/systems`, `src/resources`, and `scripts` stay on canonical backend owners
rather than routing through `qt_core`.

Updated `src/core/README.md` to match that direction: canonical subsystem
owners are the preferred import route for new GUI, tool, and backend code, while
`qt_core.py` is documented as a compatibility facade for legacy public paths.
The core import smoke tests now separate those concerns: the facade tests still
exercise `src.core.qt_core`, while the ordinary subsystem smoke test imports
canonical subsystem owners directly.

Tightened the GUI backend compatibility facade guard to scan nested function and
class definitions, not only top-level definitions. This prevents Qt or backend
implementation classes from hiding behind conditional blocks in old
backend-like GUI packages.

Added a runtime import guard so source files and scripts do not route reusable
backend-owned camera, rendering, lighting, texture, or gizmo APIs through old
GUI compatibility facades. The guard has no runtime exceptions for these old
backend-like GUI packages.

### Viewport Renderer Adapter Selection

Moved the renderer fallback proxy, backend selection helper, null diagnostic
renderer, ModernGL renderer wrapper, and Direct3D placeholder adapter into
`src/adapters/rendering/`. The old GUI renderer paths remain compatibility
facades, with `src/gui/rendering/renderer_factory.py` aliasing the adapter
module so existing monkeypatch and import workflows still patch the
implementation owner.

Moved the WGPU renderer implementation modules into
`src/adapters/rendering/wgpu_core/` as the concrete Qt/rendercanvas viewport
renderer adapter. The old `src/gui/rendering/wgpu_core/` modules now alias the
adapter owner, and the public WGPU lazy export table lives in
`src/adapters/rendering/wgpu_renderer_exports.py`. The old
`src/gui/rendering/wgpu_renderer.py` path is now a logic-free alias facade while
continuing to expose core-owned WGPU DTOs and shader helpers through explicit
export-table entries rather than fallback probing across WGPU modules. The WGPU
resource cache imports shared DTOs and helper functions by explicit name from
its adapter shared module instead of wildcard-copying the adapter import hub. The
WGPU renderer imports resource-cache, backend render contracts, WGPU shared
helpers, and shader helpers by explicit canonical route instead of consuming its
local resource/shared modules through wildcard import hubs.

Moved the concrete ModernGL `GpuRenderer` implementation into
`src/adapters/rendering/moderngl_renderer_impl.py`. The old
`src.gui.rendering.gpu_core.renderer` path is now a logic-free module alias, and
`src/adapters/rendering/moderngl_legacy_bridge.py` remains as a
stable compatibility route over adapter-owned implementation modules. The
ModernGL renderer imports GPU math, resource helpers, shader strings, and debug
table compatibility names by explicit canonical owner instead of wildcard
imports from backend/resource modules.

Moved the ModernGL resource/cache/VBO-builder implementation into
`src/adapters/rendering/moderngl_resources.py`. The old
`src.gui.rendering.gpu_core.resources` path is now a logic-free module alias,
while the public GPU facade, WGPU adapter, mesh-render-data adapter, and
viewport prebuild helpers import the adapter owner directly. IPC hot-reload
defaults and MCP render-helper stale-module cleanup now name adapter/core routes
instead of `src.gui.rendering.gpu_core.*` so tooling follows the same boundary.
The resource adapter imports shared GPU matrix/scene transform helpers from
`src.math.gpu_math` by explicit name rather than wildcard-copying the math
module into the adapter namespace.

Removed the public GPU facade's broad fallback probing of GUI ModernGL
diagnostics and renderer internals. Public compatibility names now route through
explicit backend or adapter owners, including BAS transform math through
`src.math.gpu_math`; the old GUI ModernGL implementation paths are logic-free
module aliases or facades over adapter/core owners.

Moved the public GPU renderer lazy export table into
`src/adapters/rendering/gpu_renderer_exports.py`. The old
`src.gui.rendering.gpu_renderer` and `src.gui.rendering.qt_gpu_renderer` routes
are now logic-free facades over the adapter export table, with the Qt route
using lazy attribute forwarding for renderer-factory aliases from the adapter
owner.

Updated skinning diagnostic scripts that exercise the ModernGL renderer or GPU
skin-dump records to import those helpers from
`src.adapters.rendering.moderngl_legacy_bridge` or
`src.core.rendering.gpu_diagnostics_records` directly instead of going through
`src.gui.qt_lib.rendering.gpu_renderer`.

Updated qBone diagnostic scripts and the Unity export helper to import backend
resource, animation, MDL-reader, game-loader, and Unity export helpers from
their canonical `src.core.*` packages instead of the broad
`src.core.qt_core` backend facade.

Updated the remaining script-level backend facade routes (`diagnose_bonemap`,
`diagnose_k2_geometry`, `qa_common`, and the Malak Unity smoke launcher) to use
canonical `src.core.game`, `src.core.geometry`, `src.core.mdl`, and
`src.core.special` owners. The source contract now rejects any `src.core.qt_core`
reference from tracked scripts.

Removed the local `sys.path.insert` fallback from
`src/core/templates/template_builder.py`; it now uses a normal package-relative
import for model-data types. A source contract rejects future `sys.path.append`
or `sys.path.insert` calls from core implementation modules.

Converted the generated skinning registry compatibility path
`src/core/animation/skinning_profiles/generated_character_skinning.py` from a
wildcard re-export into a package-relative module alias over
`src.core.animation.skinning_profiles.types.generated_character_skinning`, so
the typed profile directory remains the implementation owner while old imports
stay stable.

Moved the ModernGL benchmark and command-line smoke helpers into
`src/adapters/rendering/moderngl_benchmark.py` and
`src/adapters/rendering/moderngl_cli.py`. The old GPU-core paths remain
logic-free module aliases, and the public `gpu_renderer` facade routes
`_benchmark` and `_main` to the adapter modules.

### Texture Format Helpers

Moved TPC/TXI implementation from `src/gui/textures/` to
`src/core/graphics/`. The GUI texture modules now alias the backend owner,
and backend/core imports use `src.core.graphics` directly.

### TPC Render Utilities

Moved the headless TPC/DXT image helpers and PIL textured-triangle paste utility
from `src/gui/textures/tpc_render_utils.py` to `src/core/graphics/`. The GUI and
Qt-prefixed paths remain logic-free module aliases over the backend owner.

### Software Render Acceleration

Moved the NumPy/Numba software-render acceleration helpers and PIL-to-NumPy
texture-array cache into `src/core/rendering/accel.py` and
`src/core/graphics/tex_atlas.py`. GUI and Qt-prefixed paths remain facades, and
the software frame-renderer dependency hub imports these backend owners directly.

Reduced `src/gui/rendering/accel.py`, `src/gui/rendering/qt_accel.py`,
`src/gui/textures/tex_atlas.py`, and `src/gui/textures/qt_tex_atlas.py` to
logic-free module aliases over their backend owners.

### Software Frame Renderer

Moved the Tk-free PIL/software `FrameRenderer` package from
`src/gui/rendering/frame_core/` to `src/core/rendering/frame_core/`. The old GUI
frame-core modules, `src/gui/rendering/viewport_core.py`, and
`src/gui/viewports/frame_renderer.py` remain logic-free module aliases, while
scripts, IPC reload defaults, the Qt viewport adapter, and viewport shared
dependencies now target the backend owner directly.

Reduced `src/gui/rendering/viewport_core.py` to a logic-free module alias over
`src.core.rendering.frame_core.renderer` so old GUI backend-like folders no
longer need a function/class exemption for this route.

Reduced `src/core/rendering/frame_core/math_helpers.py` to a module alias over
`src.math.frame_math`; frame-core implementation modules already import shared
math helpers from the canonical math package directly.

Removed the remaining frame-core wildcard import hubs. The renderer diagnostics,
colors, rasterizer, texture cache, mixin import barrel, and renderer mixin
modules now import their backend math, graphics, camera, dependency, and helper
names explicitly, while old GUI frame-core paths remain logic-free aliases over
the backend owner. `tests/test_core_contracts.py` now guards `src/core` and
`src/adapters` against new wildcard import hubs or `globals().update` symbol
copying.

### Camera State And DTOs

Moved the Qt-free ArcBall camera state, cinematic camera DTO, render settings,
and render output helper from `src/gui/camera/` to `src/core/camera/`. The GUI
camera modules now alias the backend owner. The camera math compatibility path
aliases `src.math.camera_math`. The viewport frame renderer and camera overlays
remain GUI-owned until a renderer port/adapter slice is added.

### Camera Workflow State

Moved scene-camera workflow controller, manager state, projected camera-handle
picker, ArcBall viewport adapter, camera presets, selection state, target/rig
records, and still-render manifest helpers into `src/core/camera/`. The old GUI
camera workflow paths remain logic-free module aliases over the backend owners,
while the camera panel, still-frame render host, and viewport shared
dependencies import the backend owner directly. The camera overlay, helper
renderer, and viewport-bound still-frame renderer remain GUI-owned
presentation/adapter code.

### GPU Matrix Helper

Moved `_matrix_from_pos_quat_np` ownership into `src/math/gpu_math.py`. The GUI
diagnostics module imports and re-exports the math helper so existing diagnostic
imports keep working while math code no longer depends on `src.gui`.
The old `src/gui/rendering/gpu_core/math_helpers.py` path is now a direct module
alias to `src.math.gpu_math`.

### Lightmap Export Bridge

Moved generated-lightmap assignment discovery and export-manifest writing from
`src/gui/lighting/lightmap_export_bridge.py` to
`src/core/lighting/lightmap_export_bridge.py`. The GUI module remains as a
logic-free module alias. The larger lightmap bake services have since been
split between core services and explicit GPU/Qt adapter edges.

### Lightmap Bake Support Helpers

Moved lightmap bake settings/jobs, output/manifest helpers, rasterization,
sampling, padding, UV validation, UV atlas generation, denoise/compare helpers,
raycast backend, and CPU lighting/shadow solve helpers into `src/core/lighting/`.
The old GUI support paths remain logic-free module aliases. The Qt worker and
GUI-facing baker shell remain in `src/gui/lighting/` and import the backend
support modules directly.

### Lightmap Baker Pipeline

Moved the headless lightmap bake orchestration pipeline into
`src/core/lighting/lightmap_baker.py`. The core baker defaults to the CPU
lighting solver so backend code stays GUI-free. The GPU-default baker now lives
in `src/adapters/gpu/lightmap_baker.py` as the concrete adapter that injects
`LightmapGpuSolver` by default, preserving dialog and worker behavior. The old
GUI path remains a logic-free module alias.

Moved the Qt lightmap bake worker out of `src.gui.lighting` and into
`src.gui.dialogs.lightmap_bake_worker`. The old lighting path remains a
logic-free module alias, and `QtLightmapBakerDialog` imports the dialog-owned
worker directly so `src.gui.lighting` stays a backend-compatibility facade
package.

### Lightmap GPU Solver Adapter

Moved the ModernGL direct-light solver into
`src/adapters/gpu/lightmap_gpu_solver.py`. The old GUI path remains a
logic-free module alias and the `src.gui.qt_lib` route remains a compatibility
facade, while the GUI lightmap baker imports the adapter owner directly. It now
obtains standalone context creation from the explicit ModernGL context adapter
instead of the public GUI renderer facade.

### ModernGL Context Adapter

Moved the standalone ModernGL context backend selection/factory helpers into
`src/adapters/gpu/moderngl_context.py`, moved optional ModernGL runtime
imports/availability flags into `src/adapters/gpu/moderngl_runtime.py`, and
moved the env-gated GPU VBO probe into `src/adapters/gpu/viewport_probe.py`.
The old GUI diagnostics module is now a compatibility facade with no local
functions, and the public GPU renderer facade still exports the helpers for
compatibility. GPU adapters and the ModernGL resource/renderer modules import
the adapter/runtime/probe owners directly instead of using GUI diagnostics as a
dependency hub. The adapter-owned diagnostics export table now lazily forwards
helpers from core/adapter owners instead of wildcard-copying their symbol
tables.

### Lighting Domain And Render Data

Moved editable light records, lighting enums, selection/grouping state, Aurora
light conversion, generated rig presets, light export records, helper geometry
policy, lighting settings persistence, shader-complexity scoring, and
renderer-neutral lighting snapshots into `src/core/lighting/`. GUI panels,
pickers, diagnostics, and WGPU/ModernGL render hosts now consume these backend
owners directly while old GUI paths remain logic-free module aliases.

### Lighting Preview State And Cache

Moved lightmap preview state, material-map toggle state, and deterministic
lightmap preview cache keys into `src/core/lighting/`. The old GUI paths remain
logic-free module aliases, while the GUI lightmap baker and lighting viewport
bridge import the backend owners directly. The viewport bridge itself stays
GUI-owned because it mutates renderer attributes.

### Light Helper Picking

Moved screen-space light-helper picking policy into
`src/core/lighting/light_picker.py`. The old GUI path remains a logic-free
module alias and the `src.gui.qt_lib` route remains a compatibility facade,
while the Qt viewport shared dependency imports the backend owner directly.

### Integration And System Packages

Classified `src.autorig`, `src.formats`, `src.infra`, `src.io`,
`src.measurement`, `src.mesh_tools`, `src.resources`, `src.unreal`,
`src.workbench`, and `src.systems` as headless integration/service areas rather
than GUI extension points. `src.autorig` owns AutoRigger/AcuRig/GRig/cloth
model-editing services while optional cloth dialogs live in
`src.adapters.qt_autorig`. `src.formats` owns reusable GFF format helpers for
now. `src.infra` owns app/service infrastructure such as MCP autostart.
`src.io.fbx` owns FBX SDK configuration, diagnostics, scene adaptation, import,
and export adapter logic. `src.measurement` owns unit/snap/dimension helpers.
`src.mesh_tools` owns mesh-editing operations, topology, history, and
validation. `src.resources` owns game detection and game-library registration.
`src.unreal` may continue to own the public Quinn and Unreal-retargeting import
paths while it adapts external Unreal skeleton/FBX data into core DTOs.
`src.workbench` may own headless export/use-case helpers such as UE5 rig export
requests. `src.systems` owns product-domain systems such as BAS attachment
alignment and model recipes. These packages must remain free of Qt and
`src.gui` imports; UI surfaces consume them through public services or explicit
adapters instead.

`src.unreal` now imports core geometry and animation DTOs directly from
`src.core.geometry` and `src.core.animation` rather than the `src.core.qt_core`
facade. The integration package source contract also forbids `src.core.qt_core`
imports so these headless packages keep consuming canonical backend owners.

Moved optional cloth preset and confirmation dialogs into
`src/adapters/qt_autorig/cloth_dialogs.py`. The public
`src.autorig.cloth_rig` helper names remain as compatibility wrappers, but the
autorig package itself no longer imports PySide or contains UI dialog code.

Moved duplicated IPC Qt event-loop callback scheduling into
`src/adapters/qt_ipc/threading.py`. `src.ipc.client` and `src.ipc.server` keep
their public callback helper methods and direct headless fallback behavior, but
they no longer import PySide directly.

### Qt Viewport Renderer Adapter

Added `src/adapters/qt_viewport/frame_renderer.py` as the explicit boundary for
backend callers that still need Qt viewport rendering. `src/sequence` and
`src/core/validation` now import adapter factory functions instead of importing
`src.gui` renderer modules directly.

Moved the still-frame renderer that drives an existing Qt viewport into
`src/adapters/qt_viewport/still_frame_renderer.py`. The old
`src/gui/camera/frame_renderer.py` path remains a logic-free module alias, while
viewport shared dependencies and adapter factories import the adapter owner
directly.

### Renderer Contracts And Display DTOs

Moved renderer backend identifiers, capabilities, settings, interface contracts,
viewport display-state DTOs, CPU picking helpers, renderer performance keys,
profiling primitives, and hardware diagnostics into `src/core/rendering/`. The
old GUI rendering/display paths remain compatibility facades, and GUI renderer
adapters now import the canonical backend contracts directly.

Reduced the old GUI renderer contract/display routes, including hardware
diagnostics, to logic-free module aliases over their backend owners.

### Renderer Color Helpers

Moved shared hex color parsing into `src/core/rendering/color_utils.py`. The
ModernGL diagnostics compatibility path and WGPU shared helper module now import
the backend owner, and public GPU/WGPU renderer facades route the helper to core.

### GPU Debug Tables

Moved per-model material, UV-channel, texture-cache, and material-role
diagnostic table generation into `src/core/rendering/gpu_debug_tables.py`. The
old `src/gui/rendering/gpu_core/debug_tables.py` path remains a compatibility
module alias, while the ModernGL renderer and public GPU renderer facade export
the backend owner directly.

### GPU Diagnostics Config

Moved GPU diagnostic trace/dump path helpers and debug visualization mode
selectors into `src/core/rendering/gpu_diagnostics_config.py`. The
adapter-owned diagnostics export table imports and re-exports the backend
owner, and the public GPU renderer facade routes those helpers to core.

### GPU Diagnostics Records

Started moving renderer-neutral GPU diagnostic data-shaping helpers into
`src/core/rendering/gpu_diagnostics_records.py`. The first slices moved the
diffuse atlas auto-clamp heuristic, GL state trace record builder, and lightmap
data-dump record helpers out of GUI diagnostics. The matrix JSON helpers used by
skin diagnostics, pure skin diagnostic selection helpers, and skin diagnostic
palette/delta utilities also moved to this backend owner. qBone JSON/matrix and
node-world pose-chain diagnostic helpers now live there too. Quaternion and
xoreos first-frame orientation diagnostic helpers are also backend-owned. The
3G skin-transform formula table, formula evaluator, and role/probe selectors
now live there as well. Skin-bind equivalence record generation also moved to
core. The pure skin dump record assembler, live-slot records, and 3G candidate
records now live in core too, with the old GUI diagnostics module and public
GPU renderer facade preserving compatibility imports.

Moved the remaining compatibility aggregation in
`src.gui.rendering.gpu_core.diagnostics` into
`src/adapters/rendering/gpu_diagnostics_exports.py`. The old GUI diagnostics
path is now a logic-free alias over the adapter export table, which uses
explicit name-to-owner entries rather than probing target-module `__all__`
values. Actual diagnostic helpers remain owned by core rendering modules or
concrete GPU adapters.

### GPU VBO Layout Helpers

Moved the pure ModernGL VBO layout constants and
`_split_vbo_attributes_for_gpu` into `src/core/rendering/gpu_vbo_layout.py`.
The ModernGL resource adapter in `src/adapters/rendering/moderngl_resources.py`
owns `_build_vbo_data` and imports the backend layout splitter. GPU diagnostics
records import the VBO format constants from the backend owner, while the public
GPU renderer facade and `src.core.qt_core` expose the same backend route for
compatibility.

### ModernGL Shader Sources

Moved the static ModernGL shader source strings into
`src/core/rendering/gpu_shaders.py`. The old
`src/gui/rendering/gpu_core/shaders.py` path remains a logic-free module alias,
while the ModernGL renderer and public GPU renderer facade export the backend
owner directly.

### ModernGL Scene Helpers

Moved model-bound computation, texture TXI metadata application, base-skeleton
constant re-export, and supermodel composite wrapper support into
`src/core/rendering/gpu_scene_helpers.py`.

### ModernGL Autoframe Adapter

Moved the concrete `render_model_autoframe` helper into
`src/adapters/rendering/moderngl_scene_helpers.py` because it creates and
drives the ModernGL renderer. The old GUI scene-helper path remains a
logic-free module alias over the adapter owner, while the public GPU facade
routes pure helpers to core and autoframe rendering to the adapter.

### Qt Viewport Camera Overlays

Moved letterbox, safe-frame, and camera-guide overlay drawing into
`src/adapters/qt_viewport/camera_overlays.py`. The old GUI camera path remains
a logic-free module alias, while viewport dependencies and still-frame export use
the adapter owner directly.

### Qt Viewport Camera Gizmo

Moved camera helper and frustum drawing into
`src/adapters/qt_viewport/camera_gizmo_renderer.py`. The old GUI camera path
remains a logic-free module alias, while viewport dependencies use the adapter
owner directly.

### Viewport Navigation Profiles

Moved viewport navigation profile records, help text, label lookup, and
normalization into `src/core/rendering/viewport_navigation.py`. The old GUI
viewports and rendering paths remain compatibility facades, while runtime
callers import the core owner directly and the core owner stays free of Qt
imports.

Reduced `src/gui/rendering/viewport_navigation.py` to a logic-free module alias
over the core owner, matching the tightened compatibility-facade guard.

### Qt Viewport Lighting State Bridge

Moved the lighting-to-renderer attribute bridge into
`src/adapters/qt_viewport/lighting_viewport_controller.py`. The old GUI
lighting path remains a logic-free module alias, while new code should import the
adapter owner directly.

### WGPU Shader Sources

Moved WGPU shader source loading, inline fallback WGSL strings, and the
`wgpu_mesh_textured.wgsl` / `wgpu_mesh_skinned.wgsl` assets into
`src/core/rendering/`. The old `src/gui/rendering/wgpu_core/shaders.py` Python
path remains a logic-free module alias, while the WGPU renderer and public WGPU
renderer facade export the backend owner directly.
The WGPU adapter imports the shader loaders and WGSL constants by explicit name
instead of wildcard-copying the backend shader module.

### WGPU Shared DTOs And Helpers

Moved WGPU resource DTOs, backend-selection constants, color conversion helpers,
matrix helpers, and adapter-info extraction into
`src/core/rendering/wgpu_shared.py`. The old
`src/gui/rendering/wgpu_core/shared.py` module remains the GUI WGPU adapter
surface for Qt/rendercanvas probing; its adapter owner re-exports the
backend-owned pure helpers through explicit named imports for existing WGPU
renderer/resource imports, avoiding wildcard ownership blur.

### Skeleton Render Data

Moved skeleton overlay DTOs, skinning array extraction, and CPU skinning fallback
helpers into `src/core/rendering/skeleton_render_data.py`. The old GUI path
remains a logic-free module alias, and mesh/WGPU/viewport pipeline callers now
import the backend owner directly.

### Mesh Render Data

Moved mesh/material render-data DTOs, material extraction, texture conversion,
world-matrix helpers, normal smoothing, BAS attachment transforms, and related
headless mesh helpers into `src/core/rendering/mesh_render_data.py`. The
ModernGL-backed adapter wrapper now lives at
`src/adapters/rendering/mesh_render_data.py` and injects `_build_vbo_data` from
`src.adapters.rendering.moderngl_resources`. The old GUI path is a logic-free
module alias over that adapter. WGPU runtime callers import the backend
owner and pass the adapter VBO builder explicitly so core stays free of GUI
imports while render behavior keeps the established VBO path.
The adapter now uses lazy forwarding for core mesh-render-data names instead of
copying the core module dictionary with `globals().update`.

### Transform Gizmo Helpers

Moved renderer-neutral transform gizmo modes, draw-data DTOs, screen-space
picker, command-generation renderer, drag controller, and high-level transform
gizmo coordinator into `src/core/gizmo/`. The old GUI gizmo paths remain
logic-free module aliases or lazy package compatibility routes, and viewport
shared dependencies now import the backend owner directly. The old
`src/gui/gizmo/transform_math.py` path aliases `src.math.transform_math`. The Qt
viewport remains responsible for wiring mouse events, history, repaint
scheduling, and display surfaces.
