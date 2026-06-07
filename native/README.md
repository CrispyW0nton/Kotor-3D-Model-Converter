# GhostRigger Native Visual Studio Host

Open `GhostRigger.sln` from the repository root in Visual Studio 2022.

Before adding new native projects, renderer DLLs, toolbox DLLs, shared native
libraries, or Python bridge surfaces, read
`knowledge_base/cpp_integration_phases.md`. The detailed migration/status plan
is `knowledge_base/native_migration_plan.md`.

The first native application project is a C++ Windows host. It embeds the local
Python 3.13 runtime in `GhostRigger.exe` and runs the existing
`main.py --gui qt` path inside that native process. The current UI is still the
Python/Qt application, but the process, debugger target, and future graphics
integration point now belong to the Visual Studio solution.

The first native runtime project is `GhostRigger.Runtime`, a DLL with a tiny C
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

`GhostRigger.Native.NativeCore` is the first shared Phase 1 native core package. It is
renderer/toolbox neutral and owns shared foundations such as version reporting,
capability reporting, diagnostics contract placement, and stable handle
allocation patterns. Future renderer and toolbox DLLs should depend on shared
core contracts instead of duplicating handle or diagnostic logic.

The anchor C++ projects are `GhostRigger.Native`, `GhostRigger.Native.NativeCore`, and
`GhostRigger.Runtime`. New shared core systems should be named
`GhostRigger.Native.NativeCore.{System}`, while shared runtime contracts should be named
`GhostRigger.Runtime.Shared.{System}`. Use `native/templates/` when adding those packages
so output folders, warning levels, dependency shape, ownership metadata, and
DEBUG executable expectations stay consistent.

Build `GhostRigger.Native` to produce `GhostRigger.exe`, then run it from Visual Studio. The host is a
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

Build `GhostRigger.Runtime` to produce:

```text
build\vs\x64\Debug\GhostRigger.Runtime.dll
```

Release builds are packaging-clean by default. The Release output folder should
contain only shippable `.exe`, `.dll`, and `.lib` files. DEBUG validator
executables, `.pdb`, and `.exp` files belong outside the Release output.

Set `GHOSTRIGGER_NATIVE_RUNTIME` to a specific DLL path when testing a runtime
outside the default Visual Studio output folders.

Build and run `GhostRigger.Runtime.DEBUG` to verify the exported C ABI without
starting Python. It links against `GhostRigger.Runtime` and checks version,
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

Build and run `GhostRigger.Native.NativeCore.DEBUG` to verify the shared native core ABI
without starting Python or the GUI:

```text
build\vs\x64\Debug\GhostRigger.Native.NativeCore.DEBUG.exe
```

Python can query the shared native core package without starting the GUI through
`src.adapters.native_core.package_registry.query_native_core_status()`.
