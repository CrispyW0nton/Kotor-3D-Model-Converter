# GhostRigger Native Visual Studio Host

Open `GhostRigger.sln` from the repository root in Visual Studio 2022.

Before adding new native projects or Python bridge surfaces, read
`knowledge_base/cpp_integration_phases.md`. The detailed migration/status plan
is `knowledge_base/native_migration_plan.md`. Prefer extending an existing
aggregate DLL owner over adding a new DLL.

The first native application project is a C++ Windows host. It embeds the local
Python 3.13 runtime in `GhostRigger.exe` and runs the existing
`main.py --gui qt` path inside that native process. The current UI is still the
Python/Qt application, but the process, debugger target, and future graphics
integration point now belong to the Visual Studio solution.

Current Debug policy: `Debug` means the real project configuration run through
Visual Studio. Do not add parallel `.DEBUG` application projects to
`GhostRigger.sln`; use the owning package target in `Debug|x64` plus targeted
Python/ctypes ABI tests for native verification.

Visual Studio project display names should follow the canonical
ownership model in `knowledge_base/package_ownership_model.md` directly in the
solution. Do not use solution folders as a substitute for canonical project
names. Keep ABI/package names stable during migration unless a batch explicitly
updates project files, references, payload manifests, tests, bridge lookups,
and compatibility shims together. Legacy live project names are compatibility
state, not authority for new packages.

The first native runtime project is `GhostRigger.Runtime.Core.Host`, a DLL with a tiny C
ABI used by Python to query native runtime version, lifecycle, retained scene
handles, mesh/texture-resource descriptors, skin-palette descriptors,
mesh position/index buffer payloads, mesh vertex/index-range update payloads,
mesh transform payloads with transformed bounds, retained mesh skinning influence payloads,
CPU skinning helper payloads, CPU fallback batch statistics and item payloads,
CPU fallback execution statistics, CPU-skinned position readback payloads,
CPU-skinned bounds diagnostics,
CPU-skinned bounds picking/query/draw-planning selection,
CPU-skinned bounds skinning-scheduler selection,
resource upload-plan payloads,
diagnostic device-resource allocation payloads,
diagnostic device-resource upload-commit payloads,
diagnostic device-resource transition payloads,
mesh skin-palette bindings, GPU-skinning dispatch statistics and item payloads,
texture byte and region-update payloads, material descriptors and material-state updates, animation sample payloads,
animation palette sampling helper payloads, skin-palette
matrix-update and matrix-range-update payloads, native frame descriptors/statistics, bounds-ray picking diagnostics,
retained-bounds query/culling diagnostics,
draw-list assembly diagnostics,
capabilities, and diagnostics. It is an adapter contract first; real retained
rendering, GPU palette buffers, and triangle-accurate picking will be added
behind that boundary in later migration slices.

`GhostRigger.Native.Core.Foundation` is the first shared Phase 1 native core package. It is
renderer/toolbox neutral and owns shared foundations such as version reporting,
capability reporting, diagnostics contract placement, and stable handle
allocation patterns. Future renderer and toolbox DLLs should depend on shared
core contracts instead of duplicating handle or diagnostic logic.

`GhostRigger.Native.Core.Foundation` is the first shared native core
extension package. It owns the renderer/toolbox-neutral diagnostic record
schema and lightweight record formatting helper that future native runtime,
renderer, and toolbox DLLs can share instead of inventing local diagnostic
payload shapes.

`GhostRigger.Native.Core.Foundation` is the shared native core math package for
renderer/toolbox-neutral bounds, center, and matrix point-transform helpers.
Future renderer, picking, gizmo, and resource-residency packages should depend
on it instead of duplicating small math routines in local DLLs.

The anchor C++ projects are `GhostRigger.Native.Core.Host`,
`GhostRigger.Native.Core.Foundation`, and `GhostRigger.Runtime.Core.Host`.
Shared core systems should go into `GhostRigger.Native.Core.Foundation`,
`GhostRigger.Runtime.Core`, or `GhostRigger.Runtime.Shared` unless a separate
runtime, ABI, dependency, or deployment boundary is required. Use
`native/templates/` only when that boundary is real.

Native toolbox migrations from Python belong inside the aggregate
`GhostRigger.Core.Tools` DLL and should stay focused on product workflows.
Visible windows, panels, widgets, toolbars, dialogs, notifications, and view
state belong inside `GhostRigger.Core.GUI.Display`; interactive helper objects
such as gizmos, pickers, dummies, transform handles, and snapping guides belong
inside `GhostRigger.Core.GUI.Helpers`.

Reusable logic shared by multiple tools, GUI packages, renderers, or runtime
packages belongs in the canonical Core, Systems, Runtime, Native Core, or
Bridge or Core owner before product-surface packages consume it.

The first toolbox and window candidates are recorded in
`knowledge_base/native_toolbox_window_migration_candidates.md`; update that file
before adding new module folders inside `GhostRigger.Core.Tools`,
`GhostRigger.Core.GUI.Display`, `GhostRigger.Core.GUI.Helpers`,
`GhostRigger.Core.Automation`, or `GhostRigger.Core.Bridge`.

`GhostRigger.Core.Tools` is the first native toolbox package boundary.
It is diagnostic-only in Phase 1: it reports package capabilities, owner
boundary metadata, and a solve-packet schema placeholder while keeping native
retarget solving disabled and requiring the Python Retarget Workbench fallback.

`GhostRigger.Core.Tools` is the Phase 1 native toolbox package boundary for
export and validation helpers. It is diagnostic-only: it reports package
capabilities, owner-boundary metadata, and a preflight-packet schema placeholder
while keeping native file writes disabled and requiring the Python export
fallback.

`GhostRigger.Core.Tools` is the Phase 1 native toolbox package
boundary for Character Studio helpers. It is diagnostic-only: it reports package
capabilities, owner-boundary metadata, and an autofit-packet schema placeholder
while keeping native autofit disabled and requiring the Python Character Studio
fallback.

`GhostRigger.Core.Tools`, `GhostRigger.Core.Tools`, and
`GhostRigger.Core.Tools` are Phase 1 native toolbox package boundaries
for browser/catalogue workflows. They are diagnostic-only: they report package
capabilities, owner-boundary metadata, and catalogue/table schema placeholders
while keeping native indexing and table queries disabled and requiring Python
fallback.

`GhostRigger.Core.Tools`, `GhostRigger.Core.Tools`,
`GhostRigger.Core.Tools`, `GhostRigger.Core.Tools`, and
`GhostRigger.Core.Tools` are Phase 1 native toolbox package boundaries
for scene/workbench inspection and editing workflows. They are diagnostic-only:
they report package capabilities, owner-boundary metadata, and scene/property/
lighting/camera/module-mesh packet schema placeholders while keeping native
scene querying, property edits, light/camera evaluation, and module-mesh
indexing disabled and requiring Python fallback.

`GhostRigger.Core.Tools`,
`GhostRigger.Core.Tools`, `GhostRigger.Core.Tools`,
`GhostRigger.Core.Tools`, and `GhostRigger.Core.Tools` are
Phase 1 native toolbox package boundaries for the remaining requested tool
surfaces. They are diagnostic-only: they report package capabilities,
owner-boundary metadata, and attachment/node-tree/material/pivot/sequence packet
schema placeholders while keeping native attachment evaluation, node-tree
queries, sprite-material evaluation, pivot edits, and sequence evaluation
disabled and requiring Python fallback.

`GhostRigger.Core.GUI.Display` is a current legacy Phase 1 native window
compatibility package for main-window host services. It is diagnostic-only: it
reports package capabilities, owner-boundary metadata, and a host-service schema
placeholder while keeping the Python/Qt main window as the visible shell owner.
Future work should split or merge this surface into canonical GUI Display,
Automation, Project/Session, or NativeHost owners according to
`knowledge_base/package_ownership_model.md`.

`GhostRigger.Core.Tools`,
`GhostRigger.Core.Tools`,
`GhostRigger.Core.Tools`, and
`GhostRigger.Core.Tools` are current legacy Phase 1 native
window compatibility packages for the extra standalone/workbench windows. They
are diagnostic-only: they report package capabilities, owner-boundary metadata,
and host-service schema placeholders while keeping the Python/Qt windows as the
visible shell owners. Future work should merge them into the owning Tool, GUI
Display, GUI Helpers, Project/Session, or Automation package unless a real
runtime, ABI, dependency, or deployment reason keeps them separate.

`native/GhostRigger.Native.Core.HostModulePackages.json` records the Phase 1 full Python
module sweep. The sweep adds diagnostic Visual Studio package boundaries for
every durable Python subsystem currently identified from `src/`, including
`GhostRigger.Core.Scene` for `src/core/modules`, core domains such as scene,
level, animation, MDL, lighting, validation, project/session infrastructure,
top-level support packages such as math, measurement, formats, IO, IPC,
converters, autorig, Unreal, mesh tools, sequence, infrastructure, and KOTOR
MCP validation, plus adapter, GUI category, and `GhostRigger.Core.Tools`
packages. These packages are native-readiness boundaries only: Python still
owns the current implementation until a later migration slice proves parity.

`native/GhostRigger.PythonPayloadManifest.json` records the Phase 1.5 embedded
Python payload sweep. It maps every non-DEBUG native DLL project to packaged
Python source copies under `native/<Project>/Python/src/...` and builds
them into the DLL as `RCDATA` resources through `GhostRiggerPythonPayload.rc`.
The manifest covers all 18 Python-payload DLL projects and 1,249 packaged Python file
references; duplicated references are intentional when toolbox, renderer,
window, or shared-runtime package boundaries depend on the same Python owner.
These are packaged copies only; the active Python application still imports the
originals from `src/` until a later bridge, extraction, or import path is
deliberately enabled.

Each payload DLL also exports the shared Phase 1.5 resource ABI:
`gr_python_payload_manifest_json()` returns the embedded
`GhostRiggerPythonPayload.json` resource and `gr_python_payload_file_count()`
returns its manifest file count. `GhostRigger.exe` has build-order project
references to every payload DLL and probes those DLLs after the native startup
log console opens but before embedded Python starts. The host writes each DLL
dependency, version ABI, capabilities ABI, and Python payload file count
directly to the native console before `main.py` prints its Python startup log.

`GhostRigger.Runtime.Shared` is the first renderer-neutral runtime
descriptor package. It publishes stable schema metadata for mesh, material, and
frame descriptors so future runtime and renderer DLLs can share payload shapes
instead of redefining descriptor contracts locally.

`GhostRigger.Runtime.Shared` owns renderer-neutral resource residency
schema metadata for resource identifiers, residency records, upload packets,
and transition packets. Future D3D12/WGPU renderer packages should depend on
this package for resource-state payload shapes instead of inventing local queue
schemas.

Renderer-neutral contracts, render state, materials, texture upload policy,
renderer resources, backend interfaces, and backend implementations now belong
under `GhostRigger.Core.Rendering.*`. Canonical renderer package names include
`GhostRigger.Core.Rendering`, `GhostRigger.Core.Rendering`,
`GhostRigger.Core.Rendering`, and
`GhostRigger.Core.Rendering.{Backend}` such as
`GhostRigger.Core.Rendering`,
`GhostRigger.Core.Rendering`,
`GhostRigger.Core.Rendering`, and
`GhostRigger.Core.Rendering`.

`GhostRigger.Core.Rendering` and
`GhostRigger.Core.Rendering.*` are the current canonical native
renderer contract/backend package names. They are valid ABI verification
targets and should be extended or merged only when a future batch preserves the
real renderer-neutral contract or backend runtime boundary.

`GhostRigger.Core.Rendering` is diagnostic-only and proves the
backend DLL/Debug-validator pattern before a hardware renderer owns a real
device.

`GhostRigger.Core.Rendering` and
`GhostRigger.Core.Rendering` packages are Phase 1 renderer
boundaries for the existing Python renderer adapters. They are diagnostic-only:
they report package capabilities, backend metadata, and adapter-bridge fallback
metadata while leaving ModernGL/PyGFX device and surface ownership in Python
until later parity gates.

`GhostRigger.Core.Rendering` is the first hardware renderer
backend boundary. In Phase 1 it is diagnostic-only: it
reports D3D12 package
capabilities, backend metadata, device requirements, DXGI adapter-probe output,
feature-level 12_0 device-readiness without retaining a device, and
command-queue/swap-chain readiness requirements without creating either object,
diagnostic retained device/queue lifetime metadata, diagnostic descriptor heaps,
direct command allocator, closed direct command-list readiness metadata, and
native surface/swap-chain handle readiness metadata, render-target/back-buffer
metadata, resource-barrier/clear-pass metadata, and failure-diagnostic metadata,
command-recording dry-run frame metadata, and guarded command-list reset/close
diagnostics, and guarded no-draw command execution/fence readiness diagnostics,
present-readiness metadata, and guarded swap-chain creation diagnostics behind
an explicit native window handle, and guarded back-buffer acquisition and RTV
creation diagnostics, and guarded render-target barrier/clear recording
diagnostics, guarded clear-pass command execution/fence diagnostics, and
post-clear present-readiness diagnostics, and guarded present-call diagnostics,
and post-present frame/accounting diagnostics, and native draw-list readiness
metadata, and native resource-binding readiness metadata, and
pipeline-state/root-signature readiness metadata, and guarded shader-bytecode
metadata, and shader reflection/input-layout metadata, and guarded
root-signature metadata, guarded pipeline-state object metadata, and guarded
draw-command recording metadata, and guarded draw-submission readiness
metadata, and guarded post-draw frame/accounting readiness metadata, but it
does not record draws or create a real draw submission path yet.
`Present` is only reachable through the guarded present-call diagnostic after
prior swap-chain, back-buffer, RTV, clear-pass, and fence readiness gates pass.

Build `GhostRigger.Native.Core.Host` to produce `GhostRigger.exe`, then run it from Visual Studio. The host is a
Windows-subsystem application, but while GhostRigger is still under active
construction it opens the startup log console by default before Python starts,
preserving the visible `ghostrigger.main` and diagnostics log output. With no
arguments it embeds Python and runs the equivalent of:

```powershell
main.py --gui qt
```

Set `GHOSTRIGGER_PYTHON` if Visual Studio should use a specific interpreter:

```powershell
$env:GHOSTRIGGER_PYTHON = "C:\Path\To\python.exe"
```

The checked-in Visual Studio debugger environment points at the local Python
3.13 install used for this workspace:

```text
C:\Users\KingJamesIX\AppData\Local\Programs\Python\Python313\python.exe
```

If `GHOSTRIGGER_PYTHON` is not set, the host uses that local Python 3.13 home
when it exists. The build links against `python313.lib` and copies
`python313.dll` plus `python3.dll` beside `GhostRigger.exe`.

Hosted runs set `GHOSTRIGGER_NATIVE_HOST=1` and
`GHOSTRIGGER_EMBEDDED_PYTHON=1` before Python starts. Set
`GHOSTRIGGER_NATIVE_LOG_CONSOLE=0` to suppress the startup log console only
after we decide the application no longer needs it. Use
`--native-host-debug` to verify the native entrypoint without initializing
Python, and `--native-embed-init-debug` to verify embedded Python
initialization/finalization without opening the Qt application.

Any command-line arguments passed to `GhostRigger.exe` are forwarded to
`main.py`, replacing the default `--gui qt`.

Build `GhostRigger.Runtime.Core.Host` to produce:

```text
build\vs\x64\Debug\GhostRigger.Runtime.Core.Host.dll
```

Release builds are packaging-clean by default. The Release output folder should
contain only shippable `.exe`, `.dll`, and `.lib` files. Debug-only validation
artifacts, `.pdb`, and `.exp` files belong outside the Release output.

Set `GHOSTRIGGER_NATIVE_RUNTIME` to a specific DLL path when testing a runtime
outside the default Visual Studio output folders.

Build `GhostRigger.Runtime.Core.Host` in `Debug|x64` and run its targeted ABI checks to
verify the exported C ABI without starting Python. The checks cover version,
capabilities, lifecycle, retained scene lifecycle, mesh/texture descriptor
add/remove, mesh bounds diagnostics, mesh position/index buffer payload,
mesh vertex/index-range update diagnostics, transform payload with transformed bounds, retained skinning influence
count/byte diagnostics, CPU skinning helper outputs,
texture byte payload and region-update diagnostics, material descriptor/state diagnostics,
animation palette sampling helper outputs, skin-palette descriptor
add/update/remove, skin-palette matrix update and range-update diagnostics, animation sample diagnostics, native frame
descriptor/stat echo, bounds-ray picking over transformed retained mesh bounds,
retained-bounds query/culling over transformed mesh bounds, draw-list assembly
statistics, mesh-id output, draw-item payloads, and draw-batch payloads over retained mesh resources, and
command-recording statistics over native draw batches, and
resource-residency statistics for retained mesh buffers, texture bindings, and
skin-palette buffers, GPU-skinning dispatch statistics and per-mesh dispatch item
payloads, CPU skinning fallback batch statistics and per-mesh fallback item
payloads, retained CPU fallback execution statistics, CPU-skinned position
readback payloads, CPU-skinned bounds diagnostics, CPU-skinned bounds
pick/query/draw-planning selection, CPU-skinned bounds skinning-scheduler
selection, resource upload-plan payloads, diagnostic device-resource allocation
payloads, diagnostic device-resource upload-commit payloads, diagnostic
device-resource transition payloads, and diagnostics exports.

Build `GhostRigger.Native.Core.Foundation` in `Debug|x64` to verify the shared native core ABI
without starting Python or the GUI:

```text
build\vs\x64\Debug\GhostRigger.Native.Core.Foundation.dll
```

Python can query the shared native core package without starting the GUI through
`src.adapters.native_core.package_registry.query_native_core_status()`.

Build `GhostRigger.Native.Core.Foundation` in `Debug|x64` to verify the
shared diagnostics ABI without starting Python or the GUI:

```text
build\vs\x64\Debug\GhostRigger.Native.Core.Foundation.dll
```

Python can query the diagnostics package through
`src.adapters.native_core.package_registry.query_native_core_diagnostics_status()`.

Build `GhostRigger.Native.Core.Foundation` in `Debug|x64` to verify the shared
math ABI without starting Python or the GUI:

```text
build\vs\x64\Debug\GhostRigger.Native.Core.Foundation.dll
```

Python can query the math package through
`src.adapters.native_core.package_registry.query_native_core_math_status()`.

Build `GhostRigger.Runtime.Shared` in `Debug|x64` to verify the
shared runtime descriptor ABI without starting Python or the GUI:

```text
build\vs\x64\Debug\GhostRigger.Runtime.Shared
```

Python can query the descriptor package through
`src.adapters.native_core.package_registry.query_runtime_shared_descriptors_status()`.

Build `GhostRigger.Runtime.Shared` in `Debug|x64` to verify the shared
runtime resource ABI without starting Python or the GUI:

```text
build\vs\x64\Debug\GhostRigger.Runtime.Shared
```

Python can query the resource package through
`src.adapters.native_core.package_registry.query_runtime_shared_resources_status()`.

Build the current legacy `GhostRigger.Core.Rendering` in
`Debug|x64` to verify the renderer contract ABI without starting Python or the
GUI:

```text
build\vs\x64\Debug\GhostRigger.Core.Rendering
```

Python can query the renderer contract package through
`src.adapters.native_core.package_registry.query_renderer_contracts_status()`.

Build the current legacy `GhostRigger.Core.Rendering` in
`Debug|x64` to verify the diagnostic renderer backend ABI without starting
Python or the GUI:

```text
build\vs\x64\Debug\GhostRigger.Core.Rendering
```

Python can query the diagnostic renderer backend package through
`src.adapters.native_core.package_registry.query_renderer_null_status()`.

Build the current legacy `GhostRigger.Core.Rendering` and
`GhostRigger.Core.Rendering` in `Debug|x64` to verify the
Python-adapter renderer package ABI boundaries without starting Python or the
GUI:

```text
build\vs\x64\Debug\GhostRigger.Core.Rendering
build\vs\x64\Debug\GhostRigger.Core.Rendering
```

Python can query those renderer packages through
`src.adapters.native_core.package_registry.query_renderer_moderngl_status()` and
`src.adapters.native_core.package_registry.query_renderer_pygfx_status()`.

Build the current legacy `GhostRigger.Core.Rendering` in
`Debug|x64` to verify the D3D12 renderer package ABI, DXGI adapter-probe
export, D3D12 device-readiness export,
queue/swap-chain readiness export, diagnostic context create/destroy/export,
descriptor-heap/command-allocator readiness export, command-list readiness
export, native surface/swap-chain readiness export, render-target/back-buffer
metadata export, resource-barrier/clear-pass metadata export,
command-recording dry-run frame metadata export, guarded command-list
reset/close diagnostics export, guarded root-signature metadata export,
guarded pipeline-state object metadata export, guarded draw-command recording
metadata export, guarded draw-submission readiness metadata export,
guarded post-draw frame/accounting readiness metadata export,
failure-diagnostic export, and device-requirement metadata without starting
Python or the GUI:

```text
build\vs\x64\Debug\GhostRigger.Core.Rendering
```

Python can query the D3D12 renderer package through
`src.adapters.native_core.package_registry.query_renderer_d3d12_status()`.
Use `renderer_d3d12_guarded_metadata_capabilities(status)` to read the complete
guarded Phase 1 metadata surface advertised by the native DLL without starting
Python GUI code.
