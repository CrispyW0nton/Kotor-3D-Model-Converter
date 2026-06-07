# GhostRigger Phased C++ Integration Foundation

Date: 2026-06-07
Branch: `qt-ghostrigger`
Status: Foundation document
Related: `knowledge_base/native_migration_plan.md`, `native/README.md`

## Purpose

This document is the strict foundation for adopting the C++ hosted architecture
across GhostRigger. It defines how the native host, native DLL projects,
renderer packages, shared systems, and Python bridge are allowed to grow.

The goal is not a wholesale rewrite. The goal is to keep Python excellent at
workflow orchestration and UI while C++ takes ownership of the hot paths that
benefit from direct memory control, native graphics APIs, fast rasterisation,
GPU resource ownership, model-runtime residency, skinning, picking, streaming,
and other performance-sensitive systems.

## Core Architecture Statement

`GhostRigger.exe` is the owning process. It is built by the `GhostRigger.Native`
Visual Studio project, embeds Python, and runs the
existing Qt application in-process. Because C++ and Python now share the same
process, Python can access native C++ functionality through stable bridge
surfaces instead of launching sidecar processes or duplicating runtime logic.

Allowed bridge surfaces:

1. C ABI DLLs loaded by Python through `ctypes` or `cffi`.
2. Python extension modules (`.pyd`) imported directly by Python.
3. Host-registered Python modules created by `GhostRigger.exe` before
   `main.py` runs.
4. Narrow shared-handle APIs for host-owned runtime objects such as renderer
   devices, retained scenes, buffers, textures, skin palettes, and frame
   contexts.

The C ABI DLL route is the baseline because it is testable from C++ DEBUG
programs and Python without requiring the full GUI. Richer `.pyd` or
host-registered modules may be added only when the owning system needs a more
expressive Python API and still preserves a targeted native DEBUG path.

## Non-Negotiable Boundaries

- Every durable native system must live in its own Visual Studio project or in
  a clearly named shared native project. Do not pile unrelated systems into
  `GhostRigger.Native` or a convenient runtime file.
- Shared code used by more than one toolbox, renderer, window, or native
  system belongs in a shared native project. Do not duplicate the same C++ logic
  across renderer DLLs or toolbox DLLs.
- Python remains the current UI/workflow owner until an explicit native UI
  decision is made. Native systems expose services; Python decides user intent.
- Renderer implementations are DLL packages. The host or Python bridge selects
  them through a renderer contract; UI code never reaches directly into a
  renderer's private implementation.
- The native host owns process startup, embedded Python configuration, and
  host-wide native module registration. Feature DLLs do not initialize Python.
- Backend/model-pipeline migrations must be proven against game-file truth
  using the GhostRigger MCP tools before replacing Python behavior.
- UI, startup, viewport, theme/layout, and workflow behavior must be tested in
  the visible GhostRigger application. Backend probes and MCP tools are not a
  substitute for visual UI testing.
- Native adoption must be incremental. A native path can become the default only
  after the Python path, native path, diagnostics, and visible behavior agree on
  targeted fixtures.

## Native Project Shape

The Visual Studio solution should grow as a set of deliberately small projects:

| Project type | Output | Owns | Must not own |
|--------------|--------|------|--------------|
| Host | `.exe` | Embedded Python startup, process lifetime, host modules, global native services | Toolbox logic, renderer internals, file-format policy |
| Bridge contract | `.dll` and headers | Stable C ABI, handle types, version/capability queries, diagnostics | Renderer-specific device code |
| Shared native core | `.lib` or `.dll` | Math, memory helpers, handles, diagnostics packets, common resource descriptors | UI decisions, game-specific guesses |
| Toolbox native package | `.dll` or `.pyd` | One feature system such as animation runtime, model runtime, skinning, picking, export/readback helper | Unrelated toolbox behavior |
| Renderer package | `.dll` | One renderer backend and its GPU/device/resource implementation | Python UI state, non-renderer workflow policy |
| DEBUG project | `.exe` | Native ABI and project-level regression checks without Python/GUI | Product workflow replacement |

Each new native project must declare:

- Owning product surface, such as Main Viewport/KMAX, Character Studio,
  Retarget Workbench, Module Studio, Map Studio, Resource Browser, Validation,
  Export, or Project/session infrastructure.
- Owning code package, such as `native/GhostRigger.Renderer.D3D12`,
  `native/GhostRigger.Tools.Retargeting`, `src/adapters/rendering/native_core`,
  or `src/core/rendering`.
- Python bridge method: C ABI, `.pyd`, host module, or shared-handle API.
- Data ownership: which side owns allocation, mutation, lifetime, and cleanup.
- Verification gate: native DEBUG executable, targeted Python test, MCP comparison, and
  visible app check where applicable.

## Shared-System Rule

Anything used conjunctively or collectively by multiple toolboxes, windows, or
renderers must be a shared project. Examples include:

- Stable native handle allocation and lookup.
- Renderer-neutral mesh, material, texture, skin-palette, animation-sample, and
  frame descriptor structs.
- Matrix, quaternion, transform, bounds, and ray helpers used by both renderer
  and picking systems.
- Diagnostics packet schemas and capability reporting.
- Resource residency bookkeeping that more than one renderer consumes.
- CPU fallback routines that must match GPU or renderer output.

Shared projects must expose small APIs and versioned structs. They should not
know about Qt widgets, dock panels, theme/layout state, or user workflow
commands.

## Renderer DLL Rule

Each renderer backend is its own package. A renderer DLL may depend on shared
native projects and the bridge contract, but renderer packages must not depend
on each other's implementation details.

Baseline renderer packages should follow this shape:

- `GhostRigger.Renderer.Contracts`: renderer-neutral native interfaces,
  descriptor structs, capability flags, diagnostics, draw-list records, and
  shared handle types.
- `GhostRigger.Renderer.D3D12`: Windows Direct3D 12 renderer package.
- `GhostRigger.Renderer.WGPU`: WGPU renderer package if/when the native WGPU path
  is promoted beyond Python adapters.
- `GhostRigger.Renderer.Null`: diagnostic fallback package for tests and failure
  reporting, not a product-facing renderer mode.

Renderer DLLs should own:

- Device/context creation for that backend.
- GPU resource allocation and residency.
- Upload queues, resource transitions, pipeline state, shaders, and draw
  submission.
- Renderer-local diagnostics and frame statistics.
- Native picking/readback only when the renderer contract defines it.

Renderer DLLs must not own:

- Qt toolbar state, settings dialogs, or theme/layout application.
- KOTOR resource discovery or game-file truth decisions.
- Project save/load policy.
- Workflow-specific UI behavior such as Retarget Workbench controls.

## Python Access Contract

Python may call native systems, but native systems must keep the Python-facing
surface narrow.

Good Python-facing APIs:

- `create_scene() -> handle`
- `destroy_scene(handle)`
- `upload_mesh(scene, mesh_descriptor, vertex_payload, index_payload)`
- `update_transform(scene, mesh_id, matrix)`
- `query_capabilities() -> dict`
- `get_diagnostics(scene) -> dict`
- `render_frame(scene, frame_descriptor)`

Poor Python-facing APIs:

- APIs that require Python to poke at renderer-private structures.
- APIs that return raw mutable internal pointers without ownership rules.
- APIs that encode Qt widget state into native renderer objects.
- APIs that duplicate Python-side parsing or export policy before a migration
  gate proves the native version.

All Python wrappers must handle missing DLLs, version mismatch, unsupported
backend capabilities, and clean fallback without corrupting the active scene.

## Phase 1: Foundations And Plumbing

Purpose: establish the native host, bridge contracts, project boundaries, and
first shared runtime handles without moving product behavior prematurely.

Current completed foundation:

- `GhostRigger.exe` hosts embedded Python in-process from the `GhostRigger.Native` project.
- The native host starts `main.py --gui qt` without launching a separate Python
  process.
- `GhostRigger.Native.NativeCore.dll` exists as the first shared native core package for
  renderer/toolbox-neutral version, capability, diagnostics, and handle
  foundations.
- `GhostRigger.Native.NativeCore.Diagnostics.dll` exists as the first shared
  native core extension package for renderer/toolbox-neutral diagnostic record
  schema metadata and simple record formatting.
- `GhostRigger.Native.NativeCore.Math.dll` exists as the shared native core
  math package for renderer/toolbox-neutral bounds, center, and matrix
  point-transform helpers.
- `GhostRigger.Runtime.dll` exists as the first C ABI bridge boundary.
- `GhostRigger.Runtime.Shared.Contracts.dll` exists as the first `GhostRigger.Runtime.Shared.*`
  package for renderer-neutral contract metadata shared by future runtime and
  renderer packages.
- `GhostRigger.Runtime.Shared.Descriptors.dll` exists as the first renderer-neutral
  runtime descriptor package for shared mesh, material, and frame descriptor
  schema metadata.
- `GhostRigger.Runtime.Shared.Resources.dll` exists as the renderer-neutral
  resource residency schema package for resource identifiers, residency records,
  upload packets, and transition packets.
- `GhostRigger.Renderer.Contracts.dll` exists as the renderer-neutral package
  boundary for backend capability, surface, draw-item, and frame-stat schema
  metadata before D3D12/WGPU implementation DLLs are introduced.
- `GhostRigger.Renderer.Null.dll` exists as the first concrete renderer backend
  package behind `GhostRigger.Renderer.Contracts`; it is diagnostic-only and
  proves backend package shape without owning a real GPU device.
- `GhostRigger.Renderer.D3D12.dll` exists as the first hardware renderer backend
  package boundary behind `GhostRigger.Renderer.Contracts`; it can probe DXGI
  adapters, probe D3D12 feature-level 12_0 device-readiness without retaining a
  device, report command-queue/swap-chain readiness requirements without
  creating either object, create/destroy a diagnostic context that retains a
  D3D12 device and direct command queue for lifetime validation, retain
  diagnostic descriptor heaps, a direct command allocator, and a closed direct
  command list, report descriptor-heap/command-allocator/command-list readiness
  metadata, report native surface/swap-chain handle readiness metadata, report
  render-target/back-buffer metadata, and report failure-diagnostic schema
  metadata, but it is still diagnostic-only in Phase 1 and does not create swap
  chains, acquire back buffers, create RTVs, present, execute command lists, or
  submit draws.
- `GhostRigger.Native.NativeCore.DEBUG.exe` validates the shared native core ABI without
  Python or the GUI.
- `GhostRigger.Native.NativeCore.Diagnostics.DEBUG.exe` validates the shared
  native diagnostics ABI without Python or the GUI.
- `GhostRigger.Native.NativeCore.Math.DEBUG.exe` validates the shared native
  math ABI without Python or the GUI.
- `GhostRigger.Runtime.Shared.Contracts.DEBUG.exe` validates the shared runtime contract ABI
  without Python or the GUI.
- `GhostRigger.Runtime.Shared.Descriptors.DEBUG.exe` validates the shared
  runtime descriptor ABI without Python or the GUI.
- `GhostRigger.Runtime.Shared.Resources.DEBUG.exe` validates the shared runtime
  resource ABI without Python or the GUI.
- `GhostRigger.Renderer.Contracts.DEBUG.exe` validates the renderer contract ABI
  without Python or the GUI.
- `GhostRigger.Renderer.Null.DEBUG.exe` validates the diagnostic renderer
  backend ABI without Python or the GUI.
- `GhostRigger.Renderer.D3D12.DEBUG.exe` validates the D3D12 renderer package
  ABI, DXGI adapter-probe export, D3D12 device-readiness export,
  queue/swap-chain readiness export, diagnostic context create/destroy/export,
  descriptor-heap/command-allocator readiness export, command-list readiness
  export, native surface/swap-chain readiness export, render-target/back-buffer
  metadata export, failure-diagnostic export, and device-requirement metadata
  without Python or the GUI.
- `GhostRigger.Runtime.DEBUG.exe` validates the runtime ABI without Python.
- Native handle/retained-scene bridge work has begun through the runtime
  contract.
- `src.adapters.native_core.package_registry` can detect
  `GhostRigger.Native.NativeCore.dll`,
  `GhostRigger.Native.NativeCore.Diagnostics.dll`, and
  `GhostRigger.Native.NativeCore.Math.dll`, and
  `GhostRigger.Runtime.Shared.Contracts.dll`, and
  `GhostRigger.Runtime.Shared.Descriptors.dll`, and
  `GhostRigger.Runtime.Shared.Resources.dll`, and
  `GhostRigger.Renderer.Contracts.dll`, and `GhostRigger.Renderer.Null.dll`,
  and `GhostRigger.Renderer.D3D12.dll` availability and capabilities from
  Python without starting the GUI.
- `native/templates/` contains Phase 1 Visual Studio project templates for
  native DLL packages and DEBUG executables, with ownership metadata and
  changelog requirements.

Native project naming foundation:

- The three anchor C++ projects are `GhostRigger.Native`, `GhostRigger.Native.NativeCore`,
  and `GhostRigger.Runtime`.
- Additional shared systems that extend the core foundation should use
  `GhostRigger.Native.NativeCore.{System}` naming.
- Additional runtime-shared contracts that multiple runtime or renderer
  packages consume should use `GhostRigger.Runtime.Shared.{System}` naming.
- Concrete toolbox packages that migrate Python toolbox logic to C++ must use
  `GhostRigger.Tools.{Toolname}` naming, for example
  `GhostRigger.Tools.Retargeting`, `GhostRigger.Tools.Export`, or
  `GhostRigger.Tools.CharacterBuilder`.
- The Phase 1 native main-window package must use
  `GhostRigger.Windows.MainWindow` naming.
- Renderer contract packages use `GhostRigger.Renderer.Contracts`, and concrete
  renderer backend packages use `GhostRigger.Renderer.{Backend}`, for example
  `GhostRigger.Renderer.D3D12` or the diagnostic `GhostRigger.Renderer.Null`.
- Concrete renderer packages should name the owner clearly while depending on
  `GhostRigger.Native.NativeCore`, `GhostRigger.Native.NativeCore.*`, or
  `GhostRigger.Runtime.Shared.*` packages instead of duplicating shared code.

Required remaining foundation work:

- Continue adding separate Visual Studio projects for each durable native system
  instead of growing one monolithic runtime DLL.
- Use `GhostRigger.Tools.{Toolname}` for C++ toolbox migrations and
  `GhostRigger.Windows.MainWindow` for the Phase 1 native main-window package.
- Add shared native projects for cross-toolbox contracts, handle management,
  descriptors, math, resource residency, diagnostics, and common runtime
  helpers.
- Create one renderer DLL package per renderer backend, with
  `GhostRigger.Renderer.Null` as the diagnostic backend pattern and
  `GhostRigger.Renderer.D3D12` as the first hardware backend boundary.
- Use the native project templates for native toolbox DLLs, renderer DLLs, and
  native DEBUG executables so future agents add projects consistently.
- Add version and capability negotiation to every native package that Python can
  load.
- Add strict ownership documentation for all handle lifetimes crossing the
  Python/C++ boundary.
- Keep Python adapters under `src/adapters/` thin: load DLLs, marshal payloads,
  normalize diagnostics, and call existing core ports.

Phase 1 acceptance:

- The solution builds Debug and Release x64.
- Release solution output contains only shippable `.exe`, `.dll`, and `.lib`
  files; it does not contain `.pdb`, `.exp`, or DEBUG validator executables.
- Each native package has a DEBUG executable or a targeted ABI check.
- Python can detect package availability and report capabilities for native
  packages without starting the GUI.
- Missing native packages fall back cleanly.
- `knowledge_base/native_migration_plan.md`, `native/README.md`, and this file
  agree on the current ownership model.

## Phase 2: Building Work

Purpose: bring the native pieces together so they work as a coordinated runtime
instead of isolated proof-of-concept DLLs.

Phase 2 work areas:

- Retained scene residency: native scene handles, mesh handles, material
  handles, texture handles, skin-palette handles, generation counters, and
  lifetime diagnostics.
- Model runtime bridge: mesh descriptors, vertex/index buffers, dirty range
  updates, transform updates, bounds, and resource upload plans.
- Animation runtime bridge: sampled pose payloads, palette updates,
  supermodel-related diagnostics, blending helpers, and CPU/GPU skinning
  handoff contracts.
- Skinning runtime: native CPU fallback, GPU skinning dispatch planning,
  palette residency, readback, deformation-aware bounds, and parity checks.
- Picking and culling: transformed bounds, CPU-skinned bounds where requested,
  ray queries, draw-list filtering, and later triangle/rendered picking.
- Renderer integration: renderer-contract implementation, resource residency,
  upload queues, state transitions, shader/pipeline state, draw submission, and
  frame statistics.
- Python adapter integration: existing `src.core.ports.*` and
  `src.adapters.*` paths call native packages behind stable interfaces.
- Failure/fallback integration: any unsupported feature returns diagnostics and
  falls back to the existing Python/renderer path instead of crashing.

Phase 2 acceptance:

- Targeted MCP comparisons confirm backend/model-pipeline parity before native
  parsing or transform behavior replaces Python behavior.
- Targeted Python tests cover adapters, fallback, diagnostics, and data
  marshalling.
- Native DEBUG executables cover each DLL package independently.
- Visible GhostRigger checks confirm viewport/workflow behavior for the affected
  surface.
- Performance-sensitive paths show measurable improvement or lower frame-time
  variance before they are made default.

## Phase 3: Decorative And Presentation Integration

Purpose: connect native-backed systems to the product's visible identity and UI
objects without moving visual policy into C++.

Phase 3 covers:

- Graphical interface objects that expose native-backed features.
- Stable command IDs, button IDs, action names, and object names for native
  renderer/toolbox controls.
- Logo, SVG, icon, and handle resources used by the UI to represent native
  systems.
- Viewport manipulation handles, gizmo IDs, selection handles, helper handles,
  and renderer diagnostic overlays.
- Theme/layout integration for any new native-backed visible controls.
- Settings and capability presentation for renderer packages and toolbox DLLs.

Phase 3 rules:

- UI assets remain in the GUI/resource layer, not buried inside renderer DLLs.
- Native systems may expose capability flags and stable IDs; Python/Qt decides
  how to display them.
- New visible UI must use theme tokens and layout metrics, not hardcoded Matrix
  colours or fixed sizes.
- New workflow controls belong in their owning workbench/window/panel, not in
  the main viewport unless the main viewport is the actual owner.

Phase 3 acceptance:

- Default/native, Matrix, Droid, Dark, Light, and Classic themes remain legible.
- Layouts do not overflow or hide new controls.
- UI object names and command IDs are stable enough for IPC/visual QA.
- Visible app testing confirms the actual workflow, not only backend probes.

## Phase 4: Final Polishing

Purpose: make the native-hosted product feel finished, dependable, and safe for
daily use.

Phase 4 work areas:

- Startup polish: native host messaging, failure reporting, missing-runtime
  prompts, and release-mode logging behavior.
- Packaging polish: DLL placement, dependency discovery, version reporting,
  release manifests, and updater/install notes.
- Performance polish: frame pacing, memory pressure, upload scheduling,
  background loading, cache eviction, and renderer fallback cost.
- Diagnostics polish: user-facing native capability summaries, developer-level
  detailed diagnostics, and regression artifacts.
- Safety polish: crash containment where possible, clean shutdown, handle leak
  checks, stale resource detection, and fallback paths.
- Documentation polish: update knowledge base, native README, project templates,
  and change log after each completed native slice.

Phase 4 acceptance:

- Debug and Release x64 builds pass targeted native and Python checks.
- The actual application starts, renders, and closes cleanly through the native
  host.
- Native renderer/toolbox packages report clear capabilities and failure
  reasons.
- The default path is faster, more stable, or more capable than the old path on
  the targeted fixture.
- The previous Python behavior remains available as a fallback until the native
  path has enough coverage to remove it deliberately.

## Migration Gate Checklist

Before making any native system authoritative, confirm:

- Owning product surface is named.
- Owning native project is named.
- Shared dependencies are in shared projects, not duplicated.
- Python bridge shape is documented.
- Handles have explicit lifetime rules.
- Version/capability negotiation exists.
- Missing-DLL and unsupported-feature fallback exists.
- Targeted native DEBUG executable exists.
- Targeted Python adapter test exists.
- MCP comparison has been run for backend/model-pipeline truth when applicable.
- Visible app workflow has been tested when UI/viewport/startup behavior is
  affected.
- `CHANGES.md` records the completed slice and verification.

## Immediate Next Native Foundation Tasks

1. Use `native/templates/` for the next renderer/toolbox/shared DLL package and
   keep names under `GhostRigger.Native.NativeCore.{System}` or `GhostRigger.Runtime.Shared.{System}` when the
   package is shared rather than product-surface-specific.
2. Move the next renderer-neutral payload contract from `GhostRigger.Runtime`
   into `GhostRigger.Runtime.Shared.Contracts` once another runtime/renderer package needs
   it.
3. Extend `GhostRigger.Runtime.Shared.Descriptors` when future renderer-neutral
   mesh, material, frame, draw-list, or resource-residency payloads need stable
   shared schema metadata.
4. Extend `GhostRigger.Runtime.Shared.Resources` when future renderer-neutral
   upload, residency, transition, or resource-handle payloads need stable shared
   schema metadata.
5. Extend `GhostRigger.Renderer.D3D12` from render-target/back-buffer metadata
   diagnostics into resource-barrier and clear-pass metadata diagnostics before
   adding present or real draw submission.
6. Move reusable handle code into `GhostRigger.Native.NativeCore`, reusable
   diagnostic record/schema code into `GhostRigger.Native.NativeCore.Diagnostics`,
   and reusable bounds/matrix helpers into `GhostRigger.Native.NativeCore.Math`
   when another package needs them.
7. Extend the Python-side native package registry entries as each native package
   gains version/capability exports.
8. Document the first concrete toolbox DLL candidate before implementing it,
   including its `GhostRigger.Tools.{Toolname}` project name, owner, bridge
   surface, tests, and fallback path.
9. Keep `knowledge_base/native_toolbox_window_migration_candidates.md` updated
   before implementing `GhostRigger.Tools.*` or `GhostRigger.Windows.MainWindow`
   packages.
