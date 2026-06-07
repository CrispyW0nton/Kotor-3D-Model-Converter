# GhostRigger Native Migration Plan

Date: 2026-06-04
Branch: `qt-ghostrigger`

## Goal

Move GhostRigger toward a native graphics/runtime spine without discarding the
working Python/Qt product. Python remains the control layer for UI workflows,
KOTOR game semantics, MCP validation, project/session formats, module and map
authoring, and regression orchestration. C++ owns only the hot model-runtime and
renderer paths once each boundary has parity tests and visible verification.

The strict project-boundary and phase foundation lives in
`knowledge_base/cpp_integration_phases.md`. Read that document before adding new
native DLL projects, renderer packages, shared native systems, or Python bridge
surfaces.

The current Visual Studio solution is the entry point for this migration. It is
a launcher and native workspace first, not a rewrite of the application.

## Current State

- `GhostRigger.sln` opens the native Visual Studio workspace.
- `native/GhostRigger.Native/` builds a C++ launcher that starts the existing
  Python Qt application.
- `native/GhostRigger.Native.NativeCore/` owns the first shared native core package for
  renderer/toolbox-neutral version, capability, diagnostics, and handle
  foundations.
- `native/GhostRigger.Native.NativeCore.Diagnostics/` owns the first shared
  native diagnostics package for renderer/toolbox-neutral diagnostic record
  schema metadata and lightweight record formatting.
- `native/GhostRigger.Native.NativeCore.Math/` owns the first shared native math
  package for renderer/toolbox-neutral bounds, center, and matrix point-transform
  helpers.
- `native/GhostRigger.Native.NativeCore.DEBUG/` verifies the shared native core ABI from
  Visual Studio without requiring Python.
- `native/GhostRigger.Native.NativeCore.Diagnostics.DEBUG/` verifies the shared
  native diagnostics ABI from Visual Studio without requiring Python.
- `native/GhostRigger.Native.NativeCore.Math.DEBUG/` verifies the shared native
  math ABI from Visual Studio without requiring Python.
- `native/GhostRigger.Runtime/` owns the first native DLL boundary for renderer
  lifecycle, retained scene handles, mesh/texture-resource descriptors,
  mesh position/index buffer payloads, mesh vertex/index-range update payloads,
  mesh transform payloads, mesh skinning influence payloads, texture byte and
  region-update payloads,
  material descriptors,
  animation sample payloads,
  skin-palette descriptors and
  matrix-update/range-update payloads, native frame descriptors/statistics, and capability
  diagnostics. It also owns the first bounds-ray picking contract over retained
  mesh descriptors, retained-bounds query/culling diagnostics, and draw-list
  assembly statistics before triangle-accurate rendered picking and real draw
  submission are introduced.
- `native/GhostRigger.Runtime.DEBUG/` verifies the native runtime ABI from
  Visual Studio without requiring Python.
- `native/GhostRigger.Renderer.Contracts/` owns the renderer-neutral backend,
  surface, draw-item, and frame-stat schema metadata that concrete renderer
  packages must share before D3D12/WGPU draw submission moves native.
- `native/GhostRigger.Renderer.Contracts.DEBUG/` verifies the renderer contract
  ABI from Visual Studio without requiring Python.
- `native/GhostRigger.Renderer.Null/` owns the first concrete renderer backend
  package behind the renderer contract boundary. It is diagnostic-only and does
  not own GPU devices or draw submission.
- `native/GhostRigger.Renderer.Null.DEBUG/` verifies the diagnostic renderer
  backend ABI from Visual Studio without requiring Python.
- `native/GhostRigger.Renderer.D3D12/` owns the first hardware renderer backend
  package boundary behind the renderer contract boundary. It can probe DXGI
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
  readiness metadata, and report failure-diagnostic metadata, but it is
  diagnostic-only in Phase 1 and does
  not record draws or enable real draw submission yet.
  `Present` is only reachable through the guarded present-call diagnostic after
  prior swap-chain, back-buffer, RTV, clear-pass, and fence readiness gates pass.
- `native/GhostRigger.Renderer.D3D12.DEBUG/` verifies the D3D12 renderer package
  ABI, DXGI adapter-probe export, D3D12 device-readiness export,
  queue/swap-chain readiness export, diagnostic context create/destroy/export,
  descriptor-heap/command-allocator readiness export, command-list readiness
  export, native surface/swap-chain readiness export, render-target/back-buffer
  metadata export, resource-barrier/clear-pass metadata export,
  command-recording dry-run frame metadata export, guarded command-list
  reset/close diagnostics export, guarded no-draw command execution/fence
  readiness diagnostics export, present-readiness metadata export,
  guarded swap-chain creation diagnostics export, guarded back-buffer/RTV
  diagnostics export, guarded barrier/clear recording diagnostics export,
  guarded clear-pass execution/fence diagnostics export, post-clear
  present-readiness diagnostics export, guarded present-call diagnostics export,
  post-present frame/accounting diagnostics export, failure-diagnostic export,
  native draw-list readiness metadata export, native resource-binding readiness
  metadata export, pipeline-state/root-signature readiness metadata export,
  guarded shader-bytecode metadata export, shader reflection/input-layout
  metadata export, guarded root-signature metadata export,
  guarded pipeline-state object metadata export, guarded draw-command
  recording metadata export, guarded draw-submission readiness metadata export,
  guarded post-draw frame/accounting readiness metadata export, and
  device-requirement metadata from Visual Studio without requiring Python.
- `native/templates/` owns the Phase 1 scaffolding for future native DLL and
  DEBUG executable projects.
- `src.adapters.native_core.package_registry` detects native package
  availability and capability metadata without starting the GUI. It now exposes
  a reusable package spec so future `GhostRigger.Native.NativeCore.*`,
  `GhostRigger.Runtime.Shared.*`, and `GhostRigger.Renderer.*` packages can be
  added consistently. The D3D12 registry entry reports the complete guarded
  Phase 1 D3D12 metadata capability set advertised by the native DLL.
- `native/GhostRigger.Tools.Retargeting/` owns the first native toolbox package
  boundary for the Retarget Workbench. It reports package capabilities,
  owner-boundary metadata, and a solve-packet schema placeholder while keeping
  native solve execution disabled and requiring Python fallback.
- `native/GhostRigger.Tools.Retargeting.DEBUG/` verifies the Retargeting toolbox
  package ABI, capabilities export, owner-boundary metadata, and solve-packet
  schema placeholder from Visual Studio without requiring Python.
- `native/GhostRigger.Tools.Export/` owns the native toolbox package boundary
  for export and validation helpers. It reports package capabilities,
  owner-boundary metadata, and a preflight-packet schema placeholder while
  keeping native file writes disabled and requiring Python fallback.
- `native/GhostRigger.Tools.Export.DEBUG/` verifies the Export toolbox package
  ABI, capabilities export, owner-boundary metadata, and preflight-packet schema
  placeholder from Visual Studio without requiring Python.
- Renderer selection is isolated behind `src.adapters.rendering.renderer_factory`
  and `src.core.ports.viewport_renderer`.
- Existing renderer adapters include ModernGL, WGPU, pygfx/WGPU, experimental
  Direct3D, the native runtime contract, and null diagnostic backends.

Native project naming:
- Anchor projects: `GhostRigger.Native`, `GhostRigger.Native.NativeCore`,
  `GhostRigger.Runtime`.
- Shared core extensions: `GhostRigger.Native.NativeCore.{System}`.
- Shared runtime contracts: `GhostRigger.Runtime.Shared.{System}`.
- Renderer contracts: `GhostRigger.Renderer.Contracts`.
- Renderer backends: `GhostRigger.Renderer.{Backend}`.
- Toolbox migrations from Python: `GhostRigger.Tools.{Toolname}`.
- Phase 1 native main-window package: `GhostRigger.Windows.MainWindow`.

The first concrete toolbox and window migration candidates are documented in
`knowledge_base/native_toolbox_window_migration_candidates.md`.

## Migration Principles

1. Do not rewrite product workflows wholesale.
2. Move native code behind existing ports first.
3. Keep game-file truth checks in Python/MCP until native parsers are proven.
4. Require Python and native paths to produce comparable diagnostics.
5. Prefer native libraries with small C ABI or explicit adapter layers.
6. Keep Qt ownership clear: Python owns current widgets; native owns
   render/runtime resources until a full native UI decision is justified.
7. Every native subsystem needs targeted tests, pipeline comparisons, and
   visible viewport verification before becoming the default.

## What Stays Python For Now

- Qt windows, panels, dialogs, themes, layouts, and workflow orchestration.
- KOTOR game-resource indexing and MCP-backed ground truth checks.
- Character Builder, BAS, retargeting, module/map authoring, and export policy.
- `.kmax`, `.kmap`, project/session persistence, validation bus, and user-facing
  safety rules.
- High-level tests and visual harness orchestration.
- Format semantics that are still changing or not yet fully verified.

## What Moves To C++ First

1. Renderer scene residency: retained scene graph, mesh handles, material
   handles, texture handles, and frame diagnostics.
2. Mesh and texture resources: static/dynamic vertex buffers, index buffers,
   texture upload, sampler state, material flags, lightmap channels, and
   resource lifetime.
3. Skeletal animation runtime: sampled node transforms, supermodel pose
   application, bone palette updates, and native diagnostics for animation
   slot/source data.
4. Skinning hot paths: GPU palette upload, CPU fallback skinning, BAS attachment
   skinning cases, and per-frame dirty-region updates.
5. Picking and bounds acceleration: rendered-mesh bounds, raycast acceleration,
   hover/selection hits, gizmo centers, and focus/orbit bounds.
6. Export/readback helpers: start with native validators/readback utilities
   before replacing writers.

## Staged Deliverables

### N0: Native Workspace Baseline

Owner package: `native/GhostRigger.Native`

Acceptance:
- Visual Studio can load the solution and project.
- Debug and Release x64 compile in a VS developer environment.
- Running with no args starts `python main.py --gui qt` from the repo root.

### N1: Native Adapter Contract

Owner packages: `native/GhostRigger.Runtime`,
`src/adapters/rendering/native_core`, `src.core.ports.viewport_renderer`

Acceptance:
- Python can load the native runtime and report capabilities.
- Renderer factory can select the native backend and fall back cleanly.
- Targeted tests cover backend normalization, factory ordering, diagnostics, and
  missing-runtime behavior.
- `GhostRigger.Runtime.DEBUG` validates the exported C ABI from native code.
- The native runtime can create, clear, diagnose, and destroy retained scene
  handles before mesh/texture resources are introduced.
- The native runtime accepts mesh/texture-resource descriptors into retained
  scenes and reports mesh/vertex/index/texture byte counts plus mesh bounds
  before actual GPU buffers are introduced.
- The native runtime accepts contiguous mesh position/index payloads and reports
  payload update counts plus position/index checksums. This is the vertex/index
  buffer upload contract before D3D buffer residency is implemented.
- The native runtime accepts mesh vertex-range payloads that patch a retained
  position-buffer span without re-uploading the whole mesh. This is the dirty
  vertex-span contract for dynamic deformation, CPU fallback skinning handoff,
  and future D3D/WGPU-style buffer updates.
- The native runtime accepts mesh index-range payloads that patch a retained
  index-buffer span without re-uploading the whole mesh. This is the dirty
  topology contract for generated mesh edits, preview overlays, and future
  D3D/WGPU-style index-buffer updates.
- The native runtime accepts per-mesh world transform payloads and reports
  transform update counts/checksums, stores the world matrix, and refreshes
  transformed retained bounds. This is the transform residency contract before
  native draw submission is implemented.
- The native runtime accepts and retains per-vertex skinning influence payloads,
  then reports vertex/influence counts, retained bone-index/weight byte totals,
  and bone-index/weight checksums. This is the input-buffer contract for future
  native GPU skinning and CPU fallback skinning.
- The native runtime accepts mesh-to-skin-palette bindings so resource
  residency can prove which retained palette buffer a skinned draw will use.
- The native runtime reports GPU-skinning dispatch readiness for the
  bounds-filtered draw set: skinned meshes, GPU-ready meshes, CPU-fallback
  meshes, missing palettes/influences, skinned vertices, influence counts, and
  palette bytes. This is diagnostic dispatch planning before native shader
  execution.
- The native runtime emits optional per-mesh GPU-skinning dispatch item payloads
  containing mesh id, skin-palette id, skinned vertex/influence counts, palette
  matrix/byte counts, mesh flags, and GPU-ready/CPU-fallback status bits. This
  gives the future compute shader and CPU fallback scheduler concrete retained
  mesh packets instead of aggregate counters only.
- The native runtime exposes a CPU skinning helper that accepts vec3 position
  and normal buffers, per-vertex bone indices/weights, and 4x4 palette
  matrices, then writes skinned output buffers plus checksum stats. Python still
  owns pose selection and fallback policy until parity/visual validation proves
  native fallback replacement is safe.
- The native runtime reports CPU skinning fallback batch readiness for the
  bounds-filtered draw set, including forced-fallback scheduling for GPU-ready
  skinned meshes. The stats report fallback mesh count, GPU-ready mesh count,
  missing palette/influence blockers, skinned vertex/influence counts, palette
  matrix counts, and output position/normal buffer bytes before per-frame
  fallback uploads are introduced.
- The native runtime emits optional per-mesh CPU skinning fallback batch item
  payloads containing mesh id, skin-palette id, skinned vertex/influence counts,
  palette matrix counts, packed output position/normal byte ranges, mesh flags,
  and GPU-ready/CPU-fallback/blocker status bits. This gives the future native
  CPU fallback uploader concrete retained mesh work packets instead of aggregate
  byte counts only.
- The native runtime can execute a CPU fallback position-skinning pass over
  retained mesh positions, retained bone indices/weights, and the bound retained
  skin-palette matrices, storing retained skinned position buffers and reporting
  executed mesh count, skipped mesh count, skinned vertices, applied influences,
  output bytes, and checksum diagnostics. Normal skinning and upload/readback
  integration remain future slices.
- The native runtime can read back retained CPU-skinned position buffers by mesh
  id and vertex range so Python validation/export code can compare native
  fallback output before the renderer or exporters consume it as authoritative.
- The native runtime computes retained bounds for CPU-skinned position buffers
  and reports aggregate skinned-bounds validity/min/max diagnostics. These
  bounds are the next bridge toward deformation-aware picking, culling, focus,
  and export validation.
- Native bounds query and bounds-ray picking can opt into CPU-skinned bounds via
  a descriptor flag, allowing deformation-aware acceleration checks while
  preserving transformed bind-pose bounds for existing callers.
- Draw-list assembly, diagnostic command recording, and resource-residency
  checks use the same opt-in CPU-skinned bounds flag for their bounds-filtered
  draw set, keeping deformation-aware culling and draw planning aligned.
- GPU-skinning dispatch planning, CPU fallback batch planning, and retained CPU
  fallback execution also use the opt-in CPU-skinned bounds flag for
  bounds-filtered scheduling. This keeps deformation-aware animation work
  packets aligned with the draw set that Python/Qt is asking native code to
  render or validate.
- The native runtime accepts texture byte payloads and reports uploaded byte
  counts/checksums. This is the texture upload contract before D3D texture
  residency and sampler/material binding are implemented.
- The native runtime accepts texture region payloads that patch a retained
  texture byte span by rectangle and row pitch. This is the dirty texture-region
  contract for future streaming, lightmap edits, and D3D/WGPU-style texture
  updates.
- The native runtime exposes a resource upload-plan contract that emits
  caller-owned mesh, texture, and skin-palette upload packets with retained
  resource ids, byte counts, generation counters, type ids, and readiness
  status. This is the diagnostic queue shape that future D3D12/WGPU resource
  upload code can consume before replacing the current in-memory packet plan.
- The native runtime exposes a diagnostic device-resource allocation contract
  behind the upload plan. It assigns stable native handles for mesh
  vertex/index buffers, texture resources, and skin-palette buffers, reports
  allocation versus reuse, and preserves generation counters so later D3D12/WGPU
  objects can replace the diagnostic handles without changing Python
  orchestration.
- The native runtime separates diagnostic device-resource allocation from
  upload commits. Upload commits track the last resident generation for mesh,
  texture, and skin-palette resources, report committed/skipped/missing
  resources, and preserve byte totals for the future copy/upload queue and
  resource-state transition layer.
- The native runtime exposes diagnostic resource-state transition planning
  after upload commits. It tracks upload, vertex-buffer, index-buffer, and
  shader-resource style states, reports transition/already-ready/missing-upload
  counts, and emits caller-owned transition packets that future D3D12/WGPU
  barriers can replace directly.
- The native runtime accepts mesh material descriptors with flags, base colour,
  and diffuse/lightmap texture bindings. This is the draw-call material contract
  before shader/pipeline-state ownership is implemented.
- The native runtime accepts material-state updates that patch render flags and
  base colour without rebinding textures. This is the dirty draw-state contract
  for selection tint, render-mode changes, and future native draw-call assembly.
- The native runtime accepts animation sample descriptors with clip hash, time,
  duration, loop flags, pose-matrix counts, and pose checksums. Python still
  computes/validates poses; this is the sample handoff contract before native
  skeletal animation sampling is implemented.
- The native runtime exposes an animation palette sampling helper that blends
  two 4x4 matrix palettes into an output palette with checksum stats. Python
  still owns KOTOR clip selection, supermodel inheritance, and parity
  validation until native sampling is proven against real fixtures.
- The native runtime accepts skin-palette descriptors and update notifications
  before actual bone-matrix buffers or GPU palette uploads are introduced.
- The native runtime accepts skin-palette matrix payloads and reports matrix
  counts/checksums/update counts. Python still computes/validates the pose; C++
  now owns the upload contract that a future GPU palette buffer will consume.
- The native runtime accepts skin-palette matrix range payloads that patch a
  retained matrix span without replacing the full palette. This is the dirty
  range contract for future GPU palette-buffer updates during animation ticks.
- The native runtime accepts per-frame viewport descriptors and reports frame
  index, visible mesh count, draw-call count, triangle count, dirty-resource
  count, and frame diagnostics before actual swap-chain submission is
  introduced.
- The native runtime can raycast against transformed retained mesh bounds and
  return a native mesh id, distance, world position, transformed bounds, and
  candidate count. This is an acceleration contract only; triangle-accurate
  rendered picking remains an N5 acceptance item.
- The native runtime can query an axis-aligned bounds volume against transformed
  retained mesh bounds and return candidate/visible counts, the first native
  mesh id, and aggregate visible bounds. This is the retained culling contract
  before camera-frustum planes and draw submission move native.
- The native runtime can assemble a draw list from retained mesh
  resources, optionally filtered by a bounds volume, and report draw count,
  triangle count, material texture binding count, first mesh id, selected
  native mesh ids, draw-item payloads, and draw bounds. Draw items include mesh
  id, index count, material slot/flags, mesh flags, and retained texture ids.
  Draw batches group consecutive items by material flags, material slot, and
  retained texture ids. This is the draw-submission contract before D3D command
  recording.
- The native runtime can record stats for the command stream it would build
  from retained draw batches: draw calls, state changes, texture binds,
  triangles, and total command count. This is still diagnostic command
  recording, not a real D3D command list.
- The native runtime can report resource residency for the bounds-filtered draw
  set: resident mesh buffers, missing mesh buffers, texture references,
  resident/missing textures, skin-palette references, resident/missing skin
  palettes, and retained vertex/index/texture/palette byte counts. This is the
  D3D/WGPU-style residency gate before command recording becomes backed by real
  GPU resources.
- `native/GhostRigger.Runtime.Shared.Descriptors/` owns the first renderer-neutral
  runtime descriptor schema package for mesh, material, and frame descriptor
  metadata that future runtime and renderer DLLs can share.
- `native/GhostRigger.Runtime.Shared.Descriptors.DEBUG/` verifies the shared
  runtime descriptor ABI from Visual Studio without requiring Python.
- `native/GhostRigger.Runtime.Shared.Resources/` owns the renderer-neutral
  resource residency schema package for resource identifiers, residency records,
  upload packets, and transition packets.
- `native/GhostRigger.Runtime.Shared.Resources.DEBUG/` verifies the shared
  runtime resource ABI from Visual Studio without requiring Python.

### N2: Native Retained Scene DEBUG

Owner packages: `native/GhostRigger.Runtime`,
`src/adapters/rendering/native_core`

Acceptance:
- Empty scene and one test mesh render without crashing.
- Visible app DEBUG check opens the actual GhostRigger viewport.
- Existing non-native renderers still work.

### N3: Native KOTOR Mesh Path

Owner packages: `native/GhostRigger.Runtime`, `src/core/rendering`,
`src/adapters/rendering/native_core`

Acceptance:
- `K2:001ebo1` module fixture renders with texture/lightmap parity intent.
- `N_DarthMalak` static pose renders solid textured meshes.
- Compare diagnostics with WGPU/pygfx paths for mesh/material counts.

### N4: Native Animation And Skinning Runtime

Owner packages: `native/GhostRigger.Runtime`, `src/core/animation`,
`src/core/rendering`, `src/adapters/rendering/native_core`

Acceptance:
- `N_DarthMalak` with looped `walk` animates visibly in the actual app.
- BAS `P_CarthBB + pmha01` remains attached across inherited and local head
  animation cases.
- Native frame diagnostics meet or exceed current WGPU/pygfx performance on
  targeted fixtures.
- Native draw-list assembly reports the same retained mesh and triangle counts
  that future D3D command recording will consume.

### N5: Native Picking, Bounds, And Tool Data

Owner packages: `native/GhostRigger.Runtime`,
`src/gui/viewports/viewport_core/widgets`, `src/adapters/rendering/native_core`

Acceptance:
- Native retained bounds can answer coarse hover/selection acceleration queries
  without Python walking every mesh.
- Native retained bounds can answer coarse visibility/culling queries without
  Python walking every mesh.
- Hover and selection hit the rendered mesh, not stale source vertices.
- Gizmo centers match rendered bounds for skinned and rigid fixtures.
- Camera navigation and transform tools keep existing behavior.

### N6: Export/Readback Native Helpers

Owner packages: `native/GhostRigger.Runtime`, `src/core/mdl`, `src/core/export`

Acceptance:
- Exported MDL/MDX reloads through GhostRigger and PyKotor.
- Unity skinned-character validation proves representative characters import as
  skinned renderers or documents a deliberate fallback.
- Native helpers improve confidence without bypassing MCP ground truth.

## Launch-Critical Work Before Broad Native Expansion

- Finish Character Builder export/readback gates.
- Prove Unity skinned-character import for representative characters.
- Keep actual-app visual checks for renderer, startup, viewport, theme/layout,
  and workflow behavior.
- Preserve targeted regression testing by default; broad scans remain explicit.
