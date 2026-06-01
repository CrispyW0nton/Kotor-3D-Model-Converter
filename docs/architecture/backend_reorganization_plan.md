# Backend Reorganization Plan

Date: 2026-05-31

This plan tracks the incremental move of reusable backend logic out of GUI
packages while keeping public import paths stable during migration.

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

## Current Boundary Leaks

| Backend caller | Current GUI dependency | Target owner | Status |
|---|---|---|---|
| `src/core/game/kotor_install.py` | `src.gui.textures.tpc` | `src.core.graphics.tpc` | Migrated |
| `src/sequence/sequence_render.py` | `src.gui.camera.*` | `src.core.camera` plus `src.adapters.qt_viewport` | Migrated through explicit Qt viewport adapter |
| `src/core/validation/viewport_validator.py` | `src.gui.camera.arcball_camera`, `src.gui.rendering.frame_core.renderer` | `src.core.camera`, `src.core.rendering.frame_core`, `src.adapters.qt_viewport` | Migrated through explicit Qt viewport adapter and backend software renderer |
| `src/math/gpu_math.py` | `src.gui.rendering.gpu_core.diagnostics` | `src.math.gpu_math` local helper | Migrated |
| `src/converters/mesh_converter.py` | `src.gui.lighting.lightmap_export_bridge` | `src.core.lighting.lightmap_export_bridge` | Export bridge migrated; bake services pending |

## Package Map

| Old path | New owner | Reason | Compatibility strategy | Targeted tests |
|---|---|---|---|---|
| `src.gui.textures.tpc` | `src.core.graphics.tpc` | TPC detection, DXT decode, image loading, and embedded TXI extraction are headless KOTOR texture-format logic. | Keep `src.gui.textures.tpc` as a logic-free re-export facade until old public imports are retired. | `py_compile`; import smoke for old and new paths; `tests/test_core_contracts.py::test_texture_format_helpers_are_backend_owned`; `tests/test_regression.py::test_k2_rgba_lightmap_txi_starts_at_clean_boundary`. |
| `src.gui.textures.txi` | `src.core.graphics.txi` | TXI parsing and material metadata application are headless texture-format logic. | Keep `src.gui.textures.txi` as a logic-free re-export facade until old public imports are retired. | `py_compile`; import smoke for old and new paths; `tests/test_core_contracts.py::test_texture_format_helpers_are_backend_owned`; `tests/test_regression.py::test_k2_rgba_lightmap_txi_starts_at_clean_boundary`. |
| `src.gui.textures.tpc_render_utils` | `src.core.graphics.tpc_render_utils` | TPC/DXT image loading and PIL triangle texture paste helpers are headless render/texture utilities. | Keep GUI and Qt-prefixed paths as facades. | `py_compile`; import smoke for old and new paths; `tests/test_core_contracts.py::test_tpc_render_utils_are_backend_owned`. |
| `src.gui.rendering.accel` and `src.gui.textures.tex_atlas` | `src.core.rendering.accel` and `src.core.graphics.tex_atlas` | Software-render acceleration and PIL-to-NumPy texture-array caches are headless render/graphics support. | Keep GUI paths and Qt-prefixed paths as facades; frame-core dependencies import the backend owners directly. | `py_compile`; `tests/test_core_contracts.py::test_software_render_accel_and_texture_array_cache_are_backend_owned`; targeted Qt import checks. |
| `src.gui.camera.arcball_camera` and camera DTO modules | `src.core.camera` | Camera state and render request/result DTOs are reusable outside Qt widgets. | Keep GUI facades for existing viewport/tests, but internal backend callers migrate to `src.core.camera`. | `py_compile`; import smoke for old and new paths; `tests/test_core_contracts.py::test_camera_state_and_dtos_are_backend_owned`; focused camera contract tests. |
| `src.gui.camera.camera_controller`, `camera_viewport_adapter`, `camera_manager`, `camera_picker`, camera presets, selection/target/rig records, and render manifest | `src.core.camera` | Scene camera workflow orchestration, ArcBall camera state adaptation, projected camera-handle picking, preset records, selection state, target/rig DTOs, and still-render manifests are headless camera application/domain support. | Keep old GUI camera paths as logic-free facades; GUI panels and viewport shared dependencies import the backend owner directly. | `py_compile`; import smoke for old and new paths; `tests/test_core_contracts.py::test_camera_workflow_state_is_backend_owned`; focused camera manager/render-frame contracts. |
| `src.gui.rendering.gpu_core.diagnostics._matrix_from_pos_quat_np` | `src.math.gpu_math._matrix_from_pos_quat_np` | Matrix construction is shared GPU math, not GUI diagnostics ownership. | Keep the old diagnostics module attribute by importing the canonical math helper. | `py_compile`; `tests/test_core_contracts.py::test_gpu_matrix_helper_is_math_owned`. |
| `src.gui.lighting.lightmap_export_bridge` | `src.core.lighting.lightmap_export_bridge` | Generated-lightmap export manifests are headless conversion/export logic. | Keep the old GUI path as a logic-free re-export facade until callers migrate. | `py_compile`; `tests/test_core_contracts.py::test_lightmap_export_bridge_is_backend_owned`; `tests/test_lightmap_baker.py::test_lightmap_export_bridge_discovers_generated_assignments`. |
| Direct backend imports of Qt viewport renderers | `src.adapters.qt_viewport.frame_renderer` | Sequence image export and validation capture still rely on Qt/viewport rendering, so the dependency should be an explicit adapter boundary. | Backend callers import adapter factory functions; the adapter imports GUI implementation details. | `py_compile`; `tests/test_core_contracts.py::test_backend_renderer_dependencies_use_qt_viewport_adapter`; targeted sequence/validation import checks. |
| `src.gui.lighting.lightmap_*` support modules, UV atlas/channel helpers, and raycast helpers | `src.core.lighting` | Lightmap settings/jobs, manifests, output, padding, rasterization, UV validation, atlas generation, sampling, denoise/compare, and lighting/shadow solve helpers are headless services. | GUI panels/workers call backend services; the GPU-context solver now lives behind an explicit adapter. Old GUI support-module paths remain facades. | `py_compile`; import smoke for old and new paths; `tests/test_core_contracts.py::test_lightmap_bake_support_helpers_are_backend_owned`; `tests/test_lightmap_baker.py`. |
| `src.gui.lighting.lightmap_baker` pipeline | `src.core.lighting.lightmap_baker` plus GUI GPU-solver adapter | The bake orchestration pipeline is a headless service over core lightmap dependencies. The GUI path should only preserve the existing GPU-solver default. | `src.core.lighting.lightmap_baker.LightmapBaker` defaults to the CPU lighting solver; `src.gui.lighting.lightmap_baker.LightmapBaker` subclasses it and injects `LightmapGpuSolver`. | `py_compile`; import smoke for core/facade/GUI paths; `tests/test_core_contracts.py::test_lightmap_baker_pipeline_is_backend_owned_with_gui_gpu_adapter`; `tests/test_lightmap_baker.py`. |
| `src.gui.lighting.lightmap_gpu_solver` | `src.adapters.gpu.lightmap_gpu_solver` | The ModernGL direct-light solver is a concrete GPU adapter over core lightmap buffers and solver fallback, not GUI lighting product logic. | Keep the old GUI and `src.gui.qt_lib` routes as facades; GUI baker imports the adapter owner directly. | `py_compile`; import smoke for adapter/old GUI/qt_lib paths; `tests/test_core_contracts.py::test_lightmap_gpu_solver_is_explicit_gpu_adapter`; focused lightmap GPU fallback test. |
| `src.gui.rendering.gpu_core.diagnostics` ModernGL context/runtime/probe setup | `src.adapters.gpu.moderngl_context`, `src.adapters.gpu.moderngl_runtime`, and `src.adapters.gpu.viewport_probe` | Standalone ModernGL context creation, backend selection, optional runtime imports, GPU-skinning availability, and env-gated VBO probe output are concrete GPU adapter setup, not GUI diagnostics or public renderer facade ownership. | Keep GUI diagnostics and public `src.gui.rendering.gpu_renderer` routes as compatibility exports; GPU adapters and ModernGL resource/renderer modules import adapter/runtime/probe owners directly. | `py_compile`; import smoke for adapter/old/public paths; `tests/test_core_contracts.py::test_lightmap_gpu_solver_is_explicit_gpu_adapter`; `tests/test_regression.py::test_gl_context_backend_candidates_are_platform_aware`; focused GPU VBO/resource tests. |
| `src.gui.lighting` domain records and renderer-neutral lighting snapshots | `src.core.lighting` | Light models, enums, selection/grouping, Aurora conversion, generated rig recipes, export records, helper geometry policy, lighting settings, shader-complexity scoring, and render-data snapshots are headless domain/application support. | GUI panels, pickers, viewport controllers, and render hosts import `src.core.lighting`; old GUI domain paths remain facades. | `py_compile`; `tests/test_core_contracts.py::test_lighting_domain_and_render_data_are_backend_owned`; `tests/test_wgpu_lighting_integration.py`; focused lighting panel/render-data contracts. |
| `src.gui.lighting.lightmap_controller`, `material_map_controller`, and `preview_cache` | `src.core.lighting` | Lightmap preview state, material-map toggle state, and deterministic preview cache keys are headless viewport/application state, not widgets. | Keep old GUI paths as facades; GUI baker and viewport bridge import the core owners directly. | `py_compile`; import smoke for old/new/facade paths; `tests/test_core_contracts.py::test_lighting_preview_state_and_cache_are_backend_owned`; focused lightmap baker checks. |
| `src.gui.lighting.light_picker` | `src.core.lighting.light_picker` | Light helper hit-testing is screen-space picking policy with injected projection and transform callbacks, not Qt widget code. | Keep the old GUI and `src.gui.qt_lib` paths as facades; viewport shared dependencies import the core owner directly. | `py_compile`; import smoke for old/new/facade paths; `tests/test_core_contracts.py::test_light_picker_is_backend_owned`; focused light-picker test. |
| `src.gui.rendering.picking`, renderer settings/capabilities/interface/backend, renderer performance/profiler, hardware diagnostics, viewport display DTOs | `src.core.rendering` | Renderer contracts, CPU picking math, display state, frame pacing, profiling, and diagnostics are renderer-neutral backend support. | Preserve `src.gui.rendering.*` and `src.gui.viewports.viewport_display` facades for public imports while runtime code migrates to `src.core.rendering`. | `py_compile`; import smoke for old and new paths; `tests/test_core_contracts.py::test_renderer_contract_helpers_are_backend_owned`; renderer backend/stage focused tests. |
| Duplicate renderer `_hex_to_rgb_float` helpers | `src.core.rendering.color_utils` | Hex color parsing is renderer-neutral support shared by ModernGL and WGPU adapters, not GUI diagnostics or WGPU resource ownership. | GPU diagnostics and WGPU shared import the backend helper; public GPU/WGPU renderer facades route the helper to core. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_renderer_color_utils_are_backend_owned`. |
| `src.gui.rendering.gpu_core.debug_tables` | `src.core.rendering.gpu_debug_tables` | Per-model material/UV/texture diagnostic table generation is backend rendering diagnostics, not GUI adapter logic. | Preserve the old GPU-core path as a facade; ModernGL renderer imports the backend owner directly and the public `gpu_renderer` facade exports the backend route. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_gpu_debug_tables_are_backend_owned`; targeted diagnostic table smoke. |
| Environment/config subset of `src.gui.rendering.gpu_core.diagnostics` | `src.core.rendering.gpu_diagnostics_config` | Diagnostic trace/dump paths and debug visualization mode selectors are environment-driven backend configuration, not GUI adapter logic. | GUI diagnostics imports and re-exports the backend owner; public `gpu_renderer` facade routes these helpers to core. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_gpu_diagnostics_config_is_backend_owned`; focused diagnostic env regression tests. |
| Pure heuristic/record subset of `src.gui.rendering.gpu_core.diagnostics` | `src.core.rendering.gpu_diagnostics_records` | Diagnostic data-shaping helpers and renderer-neutral heuristics should be reusable backend rendering support, while ModernGL context probes remain adapter-owned. | GUI diagnostics imports and re-exports backend-owned helpers; public `gpu_renderer` facade routes migrated helpers to core. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_gpu_diagnostics_records_are_backend_owned`; focused GPU diagnostic regression tests. |
| GPU VBO layout constants and `_split_vbo_attributes_for_gpu` from `src.gui.rendering.gpu_core.resources` | `src.core.rendering.gpu_vbo_layout` | The split between packed float attributes and integer bone IDs is a pure renderer data-layout contract shared by diagnostics, resources, and public facades, not GUI resource-cache ownership. | Keep `_build_vbo_data` in the existing ModernGL resource adapter for now; GPU resources, diagnostics records, public `gpu_renderer`, and `src.core.qt_core` import or route the backend layout owner. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_gpu_vbo_layout_helpers_are_backend_owned`; focused GPU skin VBO layout regressions. |
| `src.gui.rendering.gpu_core.shaders` | `src.core.rendering.gpu_shaders` | ModernGL shader source strings are renderer backend data and do not depend on a GUI surface or GL context. | Preserve the old GPU-core path as a facade; ModernGL renderer imports the backend owner directly and the public `gpu_renderer` facade exports the backend route. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_gpu_shader_sources_are_backend_owned`; shader contract tests. |
| Pure helper subset of `src.gui.rendering.gpu_core.scene_helpers` | `src.core.rendering.gpu_scene_helpers` | Model bounds, TPC/TXI metadata application, base-skeleton constant re-export, and supermodel composite wrappers are model/texture helpers used by render adapters, not GUI presentation. | Keep `render_model_autoframe` in the GUI scene-helper adapter because it creates a concrete `GpuRenderer`; old GUI and public facade paths re-export pure helpers from core. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_gpu_scene_helpers_are_backend_owned`; focused GPU renderer/autoframe import checks. |
| `src.gui.rendering.wgpu_core.shaders` and `src/gui/rendering/shaders/*.wgsl` | `src.core.rendering.wgpu_shaders` and `src/core/rendering/shaders/*.wgsl` | WGPU shader source loading, inline fallback strings, and WGSL assets are renderer backend data and do not depend on a GUI surface or WGPU device. | Preserve the old WGPU-core Python path as a facade; WGPU renderer imports the backend owner directly and the public `wgpu_renderer` facade exports the backend route. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_wgpu_shader_sources_are_backend_owned`; focused WGPU shader source tests. |
| Pure DTO/helper subset of `src.gui.rendering.wgpu_core.shared` | `src.core.rendering.wgpu_shared` | WGPU resource records, backend-selection constants, color conversion, projection/view matrix helpers, and adapter-info extraction are pure renderer support, while Qt/rendercanvas probing remains GUI adapter-owned. | Keep `src.gui.rendering.wgpu_core.shared` as the WGPU adapter surface that re-exports backend helpers and owns the probe script; public `wgpu_renderer` exports pure helpers from `src.core.rendering.wgpu_shared`. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_wgpu_shared_dtos_and_helpers_are_backend_owned`; focused WGPU color/backend-selection tests. |
| `src.gui.rendering.skeleton_render_data` | `src.core.rendering.skeleton_render_data` | Skeleton overlay DTOs, skinning arrays, and CPU skinning fallback helpers are backend render data, not widget code. | Preserve `src.gui.rendering.skeleton_render_data` as a facade while runtime callers migrate to `src.core.rendering`. | `py_compile`; `tests/test_core_contracts.py::test_skeleton_render_data_is_backend_owned`; `tests/test_wgpu_stage7_render_data.py` focused cases. |
| `src.gui.rendering.mesh_render_data` | `src.core.rendering.mesh_render_data` plus GUI VBO-builder adapter | Mesh/material render-data DTOs, material extraction, texture conversion, world-matrix helpers, normal smoothing, and BAS attachment transforms are backend render-data support. The existing ModernGL VBO builder remains GUI/GPU-owned for now and is injected where needed. | Preserve `src.gui.rendering.mesh_render_data` as a facade/adapter that injects `_build_vbo_data`; WGPU runtime callers import `src.core.rendering.mesh_render_data` and pass the GUI VBO builder explicitly. | `py_compile`; `tests/test_core_contracts.py::test_mesh_render_data_is_backend_owned_with_gui_vbo_adapter`; WGPU stage render-data cases; focused regression cases for `_build_vbo_data` parity through the GUI facade. |
| `src.gui.rendering.renderer_factory`, `null_renderer`, `moderngl_renderer`, and `direct3d_renderer` | `src.adapters.rendering` | Backend selection and concrete viewport renderer adapters are runtime adapter wiring, not GUI package ownership or core renderer contracts. | Preserve the old GUI renderer paths as compatibility facades; alias the old renderer-factory module to the adapter owner so monkeypatch/import workflows keep targeting the implementation module. | `py_compile`; import smoke for old/new paths; `tests/test_core_contracts.py::test_viewport_renderer_adapters_have_explicit_owner`; focused renderer backend-selection tests. |
| `src.gui.rendering.wgpu_core` and WGPU renderer implementation route in `src.gui.rendering.wgpu_renderer` | `src.adapters.rendering.wgpu_core` | The WGPU renderer owns Qt/rendercanvas surface creation and wgpu device resources, so it is a concrete viewport renderer adapter rather than reusable GUI presentation or core rendering logic. | Preserve old `src.gui.rendering.wgpu_core.*` module paths as aliases and keep `src.gui.rendering.wgpu_renderer` as the public lazy facade; route WGPU implementation exports to the adapter owner. | `py_compile`; import smoke for old/public/new paths; `tests/test_core_contracts.py::test_viewport_renderer_adapters_have_explicit_owner`; focused WGPU renderer/backend tests. |
| `src.gui.gizmo` transform gizmo mode, draw-data, picker, renderer, controller, and coordinator | `src.core.gizmo` | Transform gizmo state, screen-space picking policy, renderer-neutral draw commands, command generation, and drag application are headless transform workflow support. | Preserve old GUI gizmo paths as compatibility facades; viewport shared dependencies import `src.core.gizmo` directly. | `py_compile`; import smoke for old and new paths; `tests/test_core_contracts.py::test_transform_gizmo_helpers_are_backend_owned`; focused gizmo mode/transform tests. |
| `src.gui.rendering.frame_core` | `src.core.rendering.frame_core` | The PIL/software `FrameRenderer`, rasterizer, texture cache, colors, diagnostics, and mixins are Tk-free software-render backend code used by validation, scripts, and viewport hosts. | Preserve old `src.gui.rendering.frame_core.*`, `src.gui.rendering.viewport_core`, and `src.gui.viewports.frame_renderer` paths as thin facades; runtime callers import the backend owner directly. | `py_compile`; `tests/test_core_contracts.py::test_software_frame_renderer_is_backend_owned`; focused frame-renderer contracts; Qt import facade check. |
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
`src/converters`, `src/math`, and `src/adapters/gpu` for direct `src.gui`
imports. Explicit adapters, such as the Qt viewport adapter, remain the allowed
place for GUI dependencies.

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
adapter owner, and the public `src/gui/rendering/wgpu_renderer.py` facade routes
`WgpuRenderer` and `WgpuResourceCache` to the adapter package while continuing
to expose core-owned WGPU DTOs and shader helpers.

### Texture Format Helpers

Moved TPC/TXI implementation from `src/gui/textures/` to
`src/core/graphics/`. The GUI texture modules now re-export the backend owner,
and backend/core imports use `src.core.graphics` directly.

### TPC Render Utilities

Moved the headless TPC/DXT image helpers and PIL textured-triangle paste utility
from `src/gui/textures/tpc_render_utils.py` to `src/core/graphics/`. The GUI and
Qt-prefixed paths remain compatibility facades.

### Software Render Acceleration

Moved the NumPy/Numba software-render acceleration helpers and PIL-to-NumPy
texture-array cache into `src/core/rendering/accel.py` and
`src/core/graphics/tex_atlas.py`. GUI and Qt-prefixed paths remain facades, and
the software frame-renderer dependency hub imports these backend owners directly.

### Software Frame Renderer

Moved the Tk-free PIL/software `FrameRenderer` package from
`src/gui/rendering/frame_core/` to `src/core/rendering/frame_core/`. The old GUI
frame-core modules, `src/gui/rendering/viewport_core.py`, and
`src/gui/viewports/frame_renderer.py` remain compatibility facades, while
scripts, IPC reload defaults, the Qt viewport adapter, and viewport shared
dependencies now target the backend owner directly.

### Camera State And DTOs

Moved the Qt-free ArcBall camera state, cinematic camera DTO, render settings,
and render output helper from `src/gui/camera/` to `src/core/camera/`. The GUI
camera modules now re-export the backend owner. The viewport frame renderer and
camera overlays remain GUI-owned until a renderer port/adapter slice is added.

### Camera Workflow State

Moved scene-camera workflow controller, manager state, projected camera-handle
picker, ArcBall viewport adapter, camera presets, selection state, target/rig
records, and still-render manifest helpers into `src/core/camera/`. GUI camera
paths remain compatibility facades, while the camera panel, still-frame render
host, and viewport shared dependencies import the backend owner directly. The
camera overlay, helper renderer, and viewport-bound still-frame renderer remain
GUI-owned presentation/adapter code.

### GPU Matrix Helper

Moved `_matrix_from_pos_quat_np` ownership into `src/math/gpu_math.py`. The GUI
diagnostics module imports and re-exports the math helper so existing diagnostic
imports keep working while math code no longer depends on `src.gui`.

### Lightmap Export Bridge

Moved generated-lightmap assignment discovery and export-manifest writing from
`src/gui/lighting/lightmap_export_bridge.py` to
`src/core/lighting/lightmap_export_bridge.py`. The GUI module remains as a
compatibility facade. The larger lightmap bake services remain a future slice
because the current stack still includes a Qt worker and GPU context adapter.

### Lightmap Bake Support Helpers

Moved lightmap bake settings/jobs, output/manifest helpers, rasterization,
sampling, padding, UV validation, UV atlas generation, denoise/compare helpers,
raycast backend, and CPU lighting/shadow solve helpers into `src/core/lighting/`.
The Qt worker and GUI-facing baker shell remain in `src/gui/lighting/` and
import the backend support modules directly.

### Lightmap Baker Pipeline

Moved the headless lightmap bake orchestration pipeline into
`src/core/lighting/lightmap_baker.py`. The core baker defaults to the CPU
lighting solver so backend code stays GUI-free. The old GUI path remains a
small adapter subclass that injects `LightmapGpuSolver` by default, preserving
dialog and worker behavior.

### Lightmap GPU Solver Adapter

Moved the ModernGL direct-light solver into
`src/adapters/gpu/lightmap_gpu_solver.py`. The old GUI and `src.gui.qt_lib`
paths remain compatibility facades, while the GUI lightmap baker imports the
adapter owner directly. It now obtains standalone context creation from the
explicit ModernGL context adapter instead of the public GUI renderer facade.

### ModernGL Context Adapter

Moved the standalone ModernGL context backend selection/factory helpers into
`src/adapters/gpu/moderngl_context.py`, moved optional ModernGL runtime
imports/availability flags into `src/adapters/gpu/moderngl_runtime.py`, and
moved the env-gated GPU VBO probe into `src/adapters/gpu/viewport_probe.py`.
The old GUI diagnostics module is now a compatibility facade with no local
functions, and the public GPU renderer facade still exports the helpers for
compatibility. GPU adapters and the ModernGL resource/renderer modules import
the adapter/runtime/probe owners directly instead of using GUI diagnostics as a
dependency hub.

### Lighting Domain And Render Data

Moved editable light records, lighting enums, selection/grouping state, Aurora
light conversion, generated rig presets, light export records, helper geometry
policy, lighting settings persistence, shader-complexity scoring, and
renderer-neutral lighting snapshots into `src/core/lighting/`. GUI panels,
pickers, diagnostics, and WGPU/ModernGL render hosts now consume these backend
owners directly while old GUI paths remain compatibility facades.

### Lighting Preview State And Cache

Moved lightmap preview state, material-map toggle state, and deterministic
lightmap preview cache keys into `src/core/lighting/`. The old GUI paths remain
compatibility facades, while the GUI lightmap baker and lighting viewport bridge
import the backend owners directly. The viewport bridge itself stays GUI-owned
because it mutates renderer attributes.

### Light Helper Picking

Moved screen-space light-helper picking policy into
`src/core/lighting/light_picker.py`. The old GUI and `src.gui.qt_lib` paths
remain compatibility facades, while the Qt viewport shared dependency imports
the backend owner directly.

### Qt Viewport Renderer Adapter

Added `src/adapters/qt_viewport/frame_renderer.py` as the explicit boundary for
backend callers that still need Qt viewport rendering. `src/sequence` and
`src/core/validation` now import adapter factory functions instead of importing
`src.gui` renderer modules directly.

### Renderer Contracts And Display DTOs

Moved renderer backend identifiers, capabilities, settings, interface contracts,
viewport display-state DTOs, CPU picking helpers, renderer performance keys,
profiling primitives, and hardware diagnostics into `src/core/rendering/`. The
old GUI rendering/display paths remain compatibility facades, and GUI renderer
adapters now import the canonical backend contracts directly.

### Renderer Color Helpers

Moved shared hex color parsing into `src/core/rendering/color_utils.py`. The
ModernGL diagnostics compatibility path and WGPU shared helper module now import
the backend owner, and public GPU/WGPU renderer facades route the helper to core.

### GPU Debug Tables

Moved per-model material, UV-channel, texture-cache, and material-role
diagnostic table generation into `src/core/rendering/gpu_debug_tables.py`. The
old `src/gui/rendering/gpu_core/debug_tables.py` path remains a compatibility
facade, while the ModernGL renderer and public GPU renderer facade export the
backend owner directly.

### GPU Diagnostics Config

Moved GPU diagnostic trace/dump path helpers and debug visualization mode
selectors into `src/core/rendering/gpu_diagnostics_config.py`. GUI diagnostics
imports and re-exports the backend owner, and the public GPU renderer facade
routes those helpers to core.

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
GPU renderer facade re-exporting the backend functions. The remaining GUI
diagnostics ownership is limited to concrete ModernGL context/probe adapter
behavior.

### GPU VBO Layout Helpers

Moved the pure ModernGL VBO layout constants and
`_split_vbo_attributes_for_gpu` into `src/core/rendering/gpu_vbo_layout.py`.
The ModernGL resource adapter still owns `_build_vbo_data`, but it now imports
the backend layout splitter. GPU diagnostics records import the VBO format
constants from the backend owner, while the public GPU renderer facade and
`src.core.qt_core` expose the same backend route for compatibility.

### ModernGL Shader Sources

Moved the static ModernGL shader source strings into
`src/core/rendering/gpu_shaders.py`. The old
`src/gui/rendering/gpu_core/shaders.py` path remains a compatibility facade,
while the ModernGL renderer and public GPU renderer facade export the backend
owner directly.

### ModernGL Scene Helpers

Moved model-bound computation, texture TXI metadata application, base-skeleton
constant re-export, and supermodel composite wrapper support into
`src/core/rendering/gpu_scene_helpers.py`. The GUI
`src/gui/rendering/gpu_core/scene_helpers.py` module now keeps the concrete
`render_model_autoframe` adapter because it creates `GpuRenderer`, and it
imports the backend helper functions directly.

### WGPU Shader Sources

Moved WGPU shader source loading, inline fallback WGSL strings, and the
`wgpu_mesh_textured.wgsl` / `wgpu_mesh_skinned.wgsl` assets into
`src/core/rendering/`. The old `src/gui/rendering/wgpu_core/shaders.py` Python
path remains a compatibility facade, while the WGPU renderer and public WGPU
renderer facade export the backend owner directly.

### WGPU Shared DTOs And Helpers

Moved WGPU resource DTOs, backend-selection constants, color conversion helpers,
matrix helpers, and adapter-info extraction into
`src/core/rendering/wgpu_shared.py`. The old
`src/gui/rendering/wgpu_core/shared.py` module remains the GUI WGPU adapter
surface for Qt/rendercanvas probing and re-exports the backend-owned pure
helpers for existing WGPU renderer/resource imports.

### Skeleton Render Data

Moved skeleton overlay DTOs, skinning array extraction, and CPU skinning fallback
helpers into `src/core/rendering/skeleton_render_data.py`. The old GUI path
remains a facade, and mesh/WGPU/viewport pipeline callers now import the backend
owner directly.

### Mesh Render Data

Moved mesh/material render-data DTOs, material extraction, texture conversion,
world-matrix helpers, normal smoothing, BAS attachment transforms, and related
headless mesh helpers into `src/core/rendering/mesh_render_data.py`. The old GUI
path remains a compatibility adapter that injects the existing ModernGL
`_build_vbo_data` helper. WGPU runtime callers import the backend owner and pass
the GUI VBO builder explicitly so core stays free of GUI imports while render
behavior keeps the established VBO path.

### Transform Gizmo Helpers

Moved renderer-neutral transform gizmo modes, draw-data DTOs, screen-space
picker, command-generation renderer, drag controller, and high-level transform
gizmo coordinator into `src/core/gizmo/`. The old GUI gizmo paths remain
compatibility facades, and viewport shared dependencies now import the backend
owner directly. The Qt viewport remains responsible for wiring mouse events,
history, repaint scheduling, and display surfaces.
