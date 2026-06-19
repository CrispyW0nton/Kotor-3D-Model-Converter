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

`GhostRigger.exe` is the owning process. It is built by the `GhostRigger.Native.Core.Host`
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
  `GhostRigger.Native.Core.Host` or a convenient runtime file.
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
| Debug configuration | real package output | Native ABI and project-level regression checks without Python/GUI | Product workflow replacement or parallel `.DEBUG` solution app |

Each new native project must declare:

- Owning product surface, such as Main Viewport/KMAX, Character Studio,
  Retarget Workbench, Module Studio, Map Studio, Resource Browser, Validation,
  Export, or Project/session infrastructure.
- Owning code package, such as `native/GhostRigger.Graphics.Renderer.Backend.D3D12`,
  `native/GhostRigger.Core.Tools.Retargeting`, `src/adapters/rendering/native_core`,
  or `src/core/rendering`.
- Python bridge method: C ABI, `.pyd`, host module, or shared-handle API.
- Data ownership: which side owns allocation, mutation, lifetime, and cleanup.
- Verification gate: native Debug target, targeted Python test, MCP comparison, and
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

- `GhostRigger.Graphics.Renderer.Shared.Contracts`: renderer-neutral native interfaces,
  descriptor structs, capability flags, diagnostics, draw-list records, and
  shared handle types.
- `GhostRigger.Graphics.Renderer.Backend.D3D12`: Windows Direct3D 12 renderer package.
- `GhostRigger.Graphics.Renderer.WGPU`: WGPU renderer package if/when the native WGPU path
  is promoted beyond Python adapters.
- `GhostRigger.Graphics.Renderer.Backend.Null`: diagnostic fallback package for tests and failure
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

- `GhostRigger.exe` hosts embedded Python in-process from the `GhostRigger.Native.Core.Host` project.
- The native host starts `main.py --gui qt` without launching a separate Python
  process.
- `GhostRigger.Native.Core.Foundation.dll` exists as the first shared native core package for
  renderer/toolbox-neutral version, capability, diagnostics, and handle
  foundations.
- `GhostRigger.Native.Core.Diagnostics.dll` exists as the first shared
  native core extension package for renderer/toolbox-neutral diagnostic record
  schema metadata and simple record formatting.
- `GhostRigger.Native.Core.Math.dll` exists as the shared native core
  math package for renderer/toolbox-neutral bounds, center, and matrix
  point-transform helpers.
- `GhostRigger.Runtime.Core.Host.dll` exists as the first C ABI bridge boundary.
- `GhostRigger.Runtime.Shared.Contracts.dll` exists as the first `GhostRigger.Runtime.Shared.*`
  package for renderer-neutral contract metadata shared by future runtime and
  renderer packages.
- `GhostRigger.Runtime.Shared.Descriptors.dll` exists as the first renderer-neutral
  runtime descriptor package for shared mesh, material, and frame descriptor
  schema metadata.
- `GhostRigger.Runtime.Shared.Resources.dll` exists as the renderer-neutral
  resource residency schema package for resource identifiers, residency records,
  upload packets, and transition packets.
- `GhostRigger.Graphics.Renderer.Shared.Contracts.dll` exists as the renderer-neutral package
  boundary for backend capability, surface, draw-item, and frame-stat schema
  metadata before D3D12/WGPU implementation DLLs are introduced.
- `GhostRigger.Graphics.Renderer.Backend.Null.dll` exists as the first concrete renderer backend
  package behind `GhostRigger.Graphics.Renderer.Shared.Contracts`; it is diagnostic-only and
  proves backend package shape without owning a real GPU device.
- `GhostRigger.Graphics.Renderer.Backend.D3D12.dll` exists as the first hardware renderer backend
  package boundary behind `GhostRigger.Graphics.Renderer.Shared.Contracts`; it can probe DXGI
  adapters, probe D3D12 feature-level 12_0 device-readiness without retaining a
  device, report command-queue/swap-chain readiness requirements without
  creating either object, create/destroy a diagnostic context that retains a
  D3D12 device and direct command queue for lifetime validation, retain
  diagnostic descriptor heaps, a direct command allocator, and a closed direct
  command list, report descriptor-heap/command-allocator/command-list readiness
  metadata, report native surface/swap-chain handle readiness metadata, report
  render-target/back-buffer metadata, report resource-barrier/clear-pass
  metadata, report command-recording dry-run frame metadata, run guarded
  command-list reset/close diagnostics, run guarded no-draw command
  execution/fence readiness diagnostics, report present-readiness metadata, run
  guarded swap-chain creation diagnostics behind an explicit native window
  handle, run guarded back-buffer acquisition and RTV creation diagnostics, run
  guarded render-target barrier/clear recording diagnostics, report guarded
  clear-pass command execution/fence diagnostics, report post-clear
  present-readiness diagnostics, run guarded present-call diagnostics, report
  post-present frame/accounting diagnostics, report native draw-list readiness
  metadata, report native resource-binding readiness metadata, report
  pipeline-state/root-signature readiness metadata, report guarded
  shader-bytecode metadata, report shader reflection/input-layout metadata,
  report guarded root-signature metadata, report guarded pipeline-state object
  metadata, report guarded draw-command recording metadata, report guarded
  draw-submission readiness metadata, report guarded post-draw frame/accounting
  readiness metadata, and report failure-diagnostic schema metadata, but it is
  still diagnostic-only in Phase 1
  and does not record draws or enable real draw submission. `Present` is only
  reachable through the guarded present-call diagnostic after prior swap-chain,
  back-buffer, RTV, clear-pass, and fence readiness gates pass.
- `GhostRigger.Native.Core.Foundation` Debug-target ABI check validates the shared native core ABI without
  Python or the GUI.
- `GhostRigger.Native.Core.Diagnostics` Debug-target ABI check validates the shared
  native diagnostics ABI without Python or the GUI.
- `GhostRigger.Native.Core.Math` Debug-target ABI check validates the shared native
  math ABI without Python or the GUI.
- `GhostRigger.Runtime.Shared.Contracts` Debug-target ABI check validates the shared runtime contract ABI
  without Python or the GUI.
- `GhostRigger.Runtime.Shared.Descriptors` Debug-target ABI check validates the shared
  runtime descriptor ABI without Python or the GUI.
- `GhostRigger.Runtime.Shared.Resources` Debug-target ABI check validates the shared runtime
  resource ABI without Python or the GUI.
- `GhostRigger.Graphics.Renderer.Shared.Contracts` Debug-target ABI check validates the renderer contract ABI
  without Python or the GUI.
- `GhostRigger.Graphics.Renderer.Backend.Null` Debug-target ABI check validates the diagnostic renderer
  backend ABI without Python or the GUI.
- `GhostRigger.Graphics.Renderer.Backend.ModernGL.dll` exists as the Phase 1 renderer package
  boundary for the existing Python ModernGL adapter. It reports renderer package
  capabilities, backend metadata, and adapter-bridge fallback metadata while
  keeping ModernGL context/device ownership in Python.
- `GhostRigger.Graphics.Renderer.Backend.ModernGL` Debug-target ABI check validates the ModernGL renderer
  package ABI without Python or the GUI.
- `GhostRigger.Graphics.Renderer.Backend.PyGFX.dll` exists as the Phase 1 renderer package
  boundary for the existing Python PyGFX/WGPU adapter. It reports renderer
  package capabilities, backend metadata, and adapter-bridge fallback metadata
  while keeping PyGFX/WGPU device ownership in Python.
- `GhostRigger.Graphics.Renderer.Backend.PyGFX` Debug-target ABI check validates the PyGFX renderer package
  ABI without Python or the GUI.
- `GhostRigger.Graphics.Renderer.Backend.D3D12` Debug-target ABI check validates the D3D12 renderer package
  ABI, DXGI adapter-probe export, D3D12 device-readiness export,
  queue/swap-chain readiness export, diagnostic context create/destroy/export,
  descriptor-heap/command-allocator readiness export, command-list readiness
  export, native surface/swap-chain readiness export, render-target/back-buffer
  metadata export, resource-barrier/clear-pass metadata export,
  command-recording dry-run frame metadata export, guarded command-list
  reset/close diagnostics export, no-draw execution/fence diagnostics export,
  present-readiness metadata export, guarded swap-chain creation diagnostics
  export, guarded back-buffer/RTV diagnostics export, guarded barrier/clear
  recording diagnostics export, guarded clear-pass execution/fence diagnostics
  export, post-clear present-readiness diagnostics export, guarded present-call
  diagnostics export, post-present frame/accounting diagnostics export,
  native draw-list readiness metadata export, native resource-binding readiness
  metadata export, pipeline-state/root-signature readiness metadata export,
  guarded shader-bytecode metadata export, shader reflection/input-layout
  metadata export, guarded root-signature metadata export,
  guarded pipeline-state object metadata export, guarded draw-command
  recording metadata export, guarded draw-submission readiness metadata export,
  guarded post-draw frame/accounting readiness metadata export,
  failure-diagnostic export, and device-requirement metadata
  without Python or the GUI.
- `GhostRigger.Runtime.Core.Host` Debug-target ABI check validates the runtime ABI without Python.
- Native handle/retained-scene bridge work has begun through the runtime
  contract.
- `src.adapters.native_core.package_registry` can detect
  `GhostRigger.Native.Core.Foundation.dll`,
  `GhostRigger.Native.Core.Diagnostics.dll`, and
  `GhostRigger.Native.Core.Math.dll`, and
  `GhostRigger.Runtime.Shared.Contracts.dll`, and
  `GhostRigger.Runtime.Shared.Descriptors.dll`, and
  `GhostRigger.Runtime.Shared.Resources.dll`, and
  `GhostRigger.Graphics.Renderer.Shared.Contracts.dll`, and `GhostRigger.Graphics.Renderer.Backend.Null.dll`,
  `GhostRigger.Graphics.Renderer.Backend.ModernGL.dll`, `GhostRigger.Graphics.Renderer.Backend.PyGFX.dll`, and
  `GhostRigger.Graphics.Renderer.Backend.D3D12.dll` availability and capabilities from
  Python without starting the GUI. The D3D12 registry entry exposes the complete
  guarded Phase 1 metadata capability set advertised by the native DLL.
- `GhostRigger.Core.Tools.Retargeting.dll` exists as the first native toolbox package
  boundary. It reports Retarget Workbench owner metadata, package capabilities,
  and a solve-packet schema placeholder while keeping native solve execution
  disabled and requiring the Python Retarget Workbench fallback.
- `GhostRigger.Core.Tools.Retargeting` Debug-target ABI check validates the Retargeting toolbox
  package ABI, owner-boundary metadata, capabilities export, and solve-packet
  schema placeholder without Python or the GUI.
- `GhostRigger.Core.Tools.Export.dll` exists as the native toolbox package boundary
  for export and validation helpers. It reports export workflow owner metadata,
  package capabilities, and a preflight-packet schema placeholder while keeping
  native file writes disabled and requiring the Python export fallback.
- `GhostRigger.Core.Tools.Export` Debug-target ABI check validates the Export toolbox package
  ABI, owner-boundary metadata, capabilities export, and preflight-packet schema
  placeholder without Python or the GUI.
- `GhostRigger.Core.Tools.CharacterBuilder.dll` exists as the native toolbox package
  boundary for Character Studio helpers. It reports Character Studio owner
  metadata, package capabilities, and an autofit-packet schema placeholder while
  keeping native autofit disabled and requiring the Python Character Studio
  fallback.
- `GhostRigger.Core.Tools.CharacterBuilder` Debug-target ABI check validates the Character
  Builder toolbox package ABI, owner-boundary metadata, capabilities export, and
  autofit-packet schema placeholder without Python or the GUI.
- `GhostRigger.Core.Tools.ContentBrowser.dll`,
  `GhostRigger.Core.Tools.ResourceBrowser.dll`, and
  `GhostRigger.Core.Tools.TwoDABrowser.dll` exist as Phase 1 browser/catalogue tool
  package boundaries. They report package capabilities, owner-boundary metadata,
  and catalogue/table schema placeholders while keeping native indexing and
  table queries disabled and requiring Python fallback.
- Their Debug-target ABI checks verify the browser/catalogue package ABIs,
  capabilities exports, owner-boundary metadata, and schema placeholders without
  Python or the GUI.
- `GhostRigger.Core.Tools.SceneInformation.dll`,
  `GhostRigger.Core.Tools.Properties.dll`, `GhostRigger.Core.Tools.Lighting.dll`,
  `GhostRigger.Core.Tools.Camera.dll`, and `GhostRigger.Core.Tools.ModuleMeshes.dll` exist
  as Phase 1 scene/workbench tool package boundaries. They report package
  capabilities, owner-boundary metadata, and scene/property/lighting/camera/
  module-mesh packet schema placeholders while keeping native scene querying,
  property edits, light/camera evaluation, and module-mesh indexing disabled and
  requiring Python fallback.
- Their Debug-target ABI checks verify the scene/workbench package ABIs,
  capabilities exports, owner-boundary metadata, and schema placeholders without
  Python or the GUI.
- `GhostRigger.Core.Tools.BAS.dll`,
  `GhostRigger.Core.Tools.NodeSkeletonBrowser.dll`,
  `GhostRigger.Core.Tools.SpriteMaterials.dll`,
  `GhostRigger.Core.Tools.PivotControls.dll`, and
  `GhostRigger.Core.Tools.SequenceEditor.dll` exist as the remaining requested Phase
  1 toolbox package boundaries. They report package capabilities,
  owner-boundary metadata, and attachment/node-tree/material/pivot/sequence
  packet schema placeholders while keeping native attachment evaluation,
  node-tree queries, sprite-material evaluation, pivot edits, and sequence
  evaluation disabled and requiring Python fallback.
- Their Debug-target ABI checks verify the remaining toolbox package ABIs,
  capabilities exports, owner-boundary metadata, and schema placeholders without
  Python or the GUI.
- `GhostRigger.Windows.Shell.Main.dll` exists as the Phase 1 native window
  package boundary for main-window host services. It reports main-window owner
  metadata, package capabilities, and a host-service schema placeholder while
  keeping the Python/Qt main window as the visible shell owner.
- `GhostRigger.Windows.Shell.Main` Debug-target ABI check validates the main-window package
  ABI, owner-boundary metadata, capabilities export, and host-service schema
  placeholder without Python or the GUI.
- `GhostRigger.Windows.Editor.Level.dll`,
  `GhostRigger.Windows.Workbench.AnimationRetarget.dll`,
  `GhostRigger.Windows.Legacy.Rigging.dll`, and
  `GhostRigger.Windows.Workbench.UnrealAnimator.dll` exist as Phase 1 native window
  package boundaries for the extra standalone/workbench windows. They report
  package capabilities, owner-boundary metadata, and host-service schema
  placeholders while keeping the Python/Qt windows as the visible shell owners.
- Their Debug-target ABI checks verify the extra window package ABIs,
  owner-boundary metadata, capabilities exports, and host-service schema
  placeholders without Python or the GUI.
- `native/GhostRigger.Native.Core.HostModulePackages.json` records the full Phase 1
  Python module sweep. The generated Visual Studio package pairs include
  `GhostRigger.Core.Modules` for `src/core/modules`, the core domains, top-level
  support packages, adapter category packages, GUI category packages, KOTOR MCP
  validation support, and `GhostRigger.Core.Tools.BAS`.
- The generated module package DLLs are diagnostic-only: they report C ABI
  version/capability metadata, owner-boundary metadata, and dependency-scan
  schema metadata while keeping `native_implementation_enabled:false` and
  `python_fallback_required:true`.
- Their Debug-target ABI checks verify the generated module package ABIs,
  owner-boundary metadata, and dependency-schema placeholders without Python or
  the GUI.
- `native/GhostRigger.PythonPayloadManifest.json` records the Phase 1.5
  embedded Python payload sweep. The payload map covers all 93 non-DEBUG native
  DLL projects and every `src/**/*.py` file at least once.
- The Phase 1.5 payload copies live under
  `native/<Project>/Python/src/...` and are built into native DLLs as
  `RCDATA` resources through per-project `GhostRiggerPythonPayload.rc` files,
  alongside per-project `GhostRiggerPythonPayload.json` manifests.
- The manifest contains 1,270 packaged Python file references. Duplicate source
  references are allowed and expected when product-surface DLLs, renderer DLLs,
  shared runtime DLLs, and diagnostic native-core extension DLLs all need a copy
  of the same Python owner surface.
- Phase 1.5 does not change runtime import behavior. The packaged Python files
  are byte-identical DLL payload copies; the active application still imports
  originals from `src/` until a later native bridge, extraction, or import path
  is deliberately enabled.
- Every payload DLL exposes the shared Phase 1.5 C ABI
  `gr_python_payload_manifest_json()` and `gr_python_payload_file_count()` so
  native code and embedded Python can verify the DLL-owned Python payload
  boundary without executing copied Python files.
- `GhostRigger.exe` has build-order project references to every payload DLL and
  runs a startup dependency audit before embedded Python executes `main.py`.
  After the native log console opens, the host loads each DLL, checks
  version/capability exports, reads the payload file count, and writes the
  audit directly to the console before Python emits the normal `main.py`
  startup log.
- `native/templates/` contains Phase 1 Visual Studio project templates for
  native DLL packages and real-project Debug verification targets, with
  ownership metadata and changelog requirements.

Native project naming foundation:

- The three anchor C++ projects are `GhostRigger.Native.Core.Host`, `GhostRigger.Native.Core.Foundation`,
  and `GhostRigger.Runtime.Core.Host`.
- Additional shared systems that extend the core foundation should use
  `GhostRigger.Native.Core.Foundation.{System}` naming.
- Additional runtime-shared contracts that multiple runtime or renderer
  packages consume should use `GhostRigger.Runtime.Shared.{System}` naming.
- Concrete toolbox packages that migrate Python toolbox logic to C++ must use
  `GhostRigger.Core.Tools.{Toolname}` naming, for example
  `GhostRigger.Core.Tools.Retargeting`, `GhostRigger.Core.Tools.Export`, or
  `GhostRigger.Core.Tools.CharacterBuilder`.
- The Phase 1 native main-window package must use
  `GhostRigger.Windows.Shell.Main` naming.
- Extra Phase 1 native window packages use
  `GhostRigger.Windows.<Type>.<WindowName>` naming, including
  `GhostRigger.Windows.Editor.Level`,
  `GhostRigger.Windows.Workbench.AnimationRetarget`,
  `GhostRigger.Windows.Legacy.Rigging`, and
  `GhostRigger.Windows.Workbench.UnrealAnimator`.
- Python module sweep packages use `GhostRigger.Core.{Domain}`,
  `GhostRigger.Adapters.<Type>.<AdapterName>`, and `GhostRigger.Core.GUI.{Category}` naming.
  Durable feature systems should merge into the owning `GhostRigger.Core.{Domain}` or
  `GhostRigger.Core.Tools.{Toolname}` package instead of creating a parallel
  `Systems.Feature` namespace. `GhostRigger.Core.Modules` is reserved for the native
  boundary that mirrors `src/core/modules`.
- Renderer contract packages use `GhostRigger.Graphics.Renderer.Shared.Contracts`, and concrete
  renderer backend packages use `GhostRigger.Graphics.Renderer.Backend.{Backend}`, for example
  `GhostRigger.Graphics.Renderer.Backend.D3D12` or the diagnostic `GhostRigger.Graphics.Renderer.Backend.Null`.
- Concrete renderer packages should name the owner clearly while depending on
  `GhostRigger.Native.Core.Foundation`, `GhostRigger.Native.Core.Foundation.*`, or
  `GhostRigger.Runtime.Shared.*` packages instead of duplicating shared code.

Required remaining foundation work:

- Continue adding separate Visual Studio projects for each durable native system
  instead of growing one monolithic runtime DLL.
- Use `GhostRigger.Core.Tools.{Toolname}` for C++ toolbox migrations and
  `GhostRigger.Windows.Shell.Main` for the Phase 1 native main-window package.
- Add shared native projects for cross-toolbox contracts, handle management,
  descriptors, math, resource residency, diagnostics, and common runtime
  helpers.
- Create one renderer DLL package per renderer backend, with
  `GhostRigger.Graphics.Renderer.Backend.Null` as the diagnostic backend pattern and
  `GhostRigger.Graphics.Renderer.Backend.D3D12` as the first hardware backend boundary.
- Use the native project templates for native toolbox DLLs, renderer DLLs, and
  real-project Debug verification targets so future agents add projects
  consistently.
- Add version and capability negotiation to every native package that Python can
  load.
- Add strict ownership documentation for all handle lifetimes crossing the
  Python/C++ boundary.
- Keep Python adapters under `src/adapters/` thin: load DLLs, marshal payloads,
  normalize diagnostics, and call existing core ports.

Phase 1 acceptance:

- The solution builds Debug and Release x64.
- Release solution output contains only shippable `.exe`, `.dll`, and `.lib`
  files; it does not contain `.pdb`, `.exp`, or Debug-only validation artifacts.
- Each native package has a real Debug target or a targeted ABI check.
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
- Native Debug targets or targeted ABI checks cover each DLL package
  independently.
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
- Targeted native Debug target or ABI check exists.
- Targeted Python adapter test exists.
- MCP comparison has been run for backend/model-pipeline truth when applicable.
- Visible app workflow has been tested when UI/viewport/startup behavior is
  affected.
- `CHANGES.md` records the completed slice and verification.

## Immediate Next Native Foundation Tasks

1. Use `native/templates/` for the next renderer/toolbox/shared DLL package and
   keep names under `GhostRigger.Native.Core.Foundation.{System}` or `GhostRigger.Runtime.Shared.{System}` when the
   package is shared rather than product-surface-specific.
2. Move the next renderer-neutral payload contract from `GhostRigger.Runtime.Core.Host`
   into `GhostRigger.Runtime.Shared.Contracts` once another runtime/renderer package needs
   it.
3. Extend `GhostRigger.Runtime.Shared.Descriptors` when future renderer-neutral
   mesh, material, frame, draw-list, or resource-residency payloads need stable
   shared schema metadata.
4. Extend `GhostRigger.Runtime.Shared.Resources` when future renderer-neutral
   upload, residency, transition, or resource-handle payloads need stable shared
   schema metadata.
5. Extend the Python-side native package registry entries as each native
   toolbox, renderer, or shared package gains version/capability exports.
6. Move reusable handle code into `GhostRigger.Native.Core.Foundation`, reusable
   diagnostic record/schema code into `GhostRigger.Native.Core.Diagnostics`,
   and reusable bounds/matrix helpers into `GhostRigger.Native.Core.Math`
   when another package needs them.
7. Extend the Python-side native package registry entries as each native package
   gains version/capability exports.
8. Document the first concrete toolbox DLL candidate before implementing it,
   including its `GhostRigger.Core.Tools.{Toolname}` project name, owner, bridge
   surface, tests, and fallback path.
9. Keep `knowledge_base/native_toolbox_window_migration_candidates.md` updated
   before implementing `GhostRigger.Tools.*` or `GhostRigger.Windows.Shell.Main`
   packages.
