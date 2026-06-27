# C++ Game Programming Skill (Native Implementation & Python Bridge)

Use this skill for the **C++ implementation mechanics** of GhostRigger's native
runtime: the embedded-CPython host launch flow, the C++↔Python ABI boundary,
renderer-backend adapter contracts, performance-critical native code (culling,
command buffers, fixed-step update), and game algorithms (animation FSMs, A*
pathfinding, procedural generation) in C++. It is the implementation companion
to `learned/cppnativeskill.md` (write *correct* C++ at the boundary — RAII,
smart pointers, ABI checklist; read first) and `learned/cgameprogrammingskill.md`
(*organize* the runtime — kernel/subsystem split, scene composition, resource
lifecycle). Those answer "what subsystems exist"; this answers "how do I
implement them in C++ and bridge them to embedded Python?"

## Book Grounding

- `Practical_C_Game_Programming_-_Zhenyu_George_Li.pdf` ("Knight" raylib engine):
  C++ data-structure/algorithm selection for games, the 3D rendering pipeline in
  C++ (mesh/matrix/transform plumbing, draw-call batching), camera systems
  (view/projection composition, follow + deadzone), animation as finite-state
  machines, A* pathfinding, procedural generation (random acyclic maze via DFS),
  and Big-O discipline for per-frame work.
- `Game_Audio_Programming_-_Guy_Somberg.pdf`: patterns that generalize beyond
  audio — audio-object lifecycle (spawn/update/die), thread-safe command buffers,
  squared-distance culling (compare `d²`, never `sqrt`), data-driven events,
  streaming loops. Native systems-programming patterns for picking, culling,
  telemetry, and the editor runtime.
- GhostRigger-native sources: `native/GhostRigger.Native.Core.Host/Private/
  main.cpp`, `native/GhostRigger.Runtime.Shared/Python/src/core/rendering/
  renderer_backend.py`, `native/README.md`, `AGENTS.md`,
  `knowledge_base/cpp_integration_phases.md`,
  `knowledge_base/native_migration_plan.md`.

## The Native Host Launch Flow

`GhostRigger.Native.Core.Host` is a thin `.exe` whose `main.cpp` does one job:
bootstrap embedded CPython and hand control to `main.py`. Verify specifics
against the current `main.cpp`, but the sequence is:

1. **Resolve the repo root** — walk up from `cwd` and the executable directory
   (up to 10 levels) looking for `GhostRigger.sln` or `pyproject.toml` +
   `native/`; this anchors every later path.
2. **Discover the Python 3.13 home** — probe in order `GHOSTRIGGER_PYTHON_HOME`,
   `GHOSTRIGGER_PYTHON`, `%LOCALAPPDATA%\Programs\Python\Python313`,
   `%ProgramFiles%\Python313`, `%ProgramW6432%\Python313`; a valid home must
   contain `python313.dll`, `python.exe`, and `Lib/`.
3. **Audit native DLL dependencies (pre-Python)** — iterate the
   `ghostrigger::native::core::host::kNativeDependencySpecs[]` table from
   `GhostRiggerNativeDependencies.h`, `LoadLibraryExW(...,
   LOAD_WITH_ALTERED_SEARCH_PATH)` each DLL, resolve
   `gr_python_payload_file_count` via `GetProcAddress`, and classify each as
   OK / NO_PAYLOAD / MISSING, publishing the result to Python through the
   `GHOSTRIGGER_NATIVE_PREPYTHON_AUDIT` env var. This is the **DLL payload
   resolution chain**: the host loads each payload DLL, asks it how many Python
   files it carries, and only proceeds when the manifest is self-consistent.
   `--native-host-debug` / `--native-embed-init-debug` and
   `GHOSTRIGGER_NATIVE_LOG_CONSOLE` control diagnostics.
4. **Configure and start embedded Python** — build a `PyConfig`, set home and
   program paths, append `argv` (forwarding user args minus internal debug
   flags), initialize the interpreter, run `main.py`.

Constraints: the host stays thin (domain logic lives in `Core.*`, never
`main.cpp`); `<Python.h>` is included with `_DEBUG` temporarily `#undef`'d so a
Debug build links the release CPython ABI; every failure path must surface
(`MessageBoxW`/console audit). A silent host failure is a bug.

## The C++↔Python ABI Boundary

The runtime ABI (`GhostRigger.Runtime.Core` / `Runtime.Core.Host`) follows the
"retained handles + plain descriptors" model:

- **Opaque handles, not rich objects** — a stable identity plus a plain,
  versioned, C-compatible descriptor per operation.
- **Narrow C exports**, stable names, explicit calling convention,
  C-compatible types (e.g. `gr_python_payload_file_count`,
  `gr_rendering_normalize_renderer_backend`).
- **Never let a C++ exception cross the ABI** — translate to status/JSON;
  CPython's error state is Python's problem, not the C caller's.
- **Version every parsed payload additively** — never mutate a parsed struct.
- **Explicit string ownership** — static or caller-buffer `const char*`; never
  return a pointer into an object Python might outlive or free.

## C++ Rendering Pipeline & Backend Adapters

GhostRigger is renderer-neutral by contract; backends are adapters behind one
owned interface (Bridge/Adapter, `pythonpackagingskill.md`). Current identifiers
(`renderer_backend.py`): `MODERNGL_GL330` (OpenGL 3.3 via ModernGL, default/
`auto`), `WGPU_D3D12` (Direct3D 12 via wgpu; aliases `d3d12`, `direct3d`,
`native_d3d12`, `vulkan`, `wgpu_vulkan`), `PYGFX_WGPU` (PyGFX over wgpu), and
`NULL_DIAGNOSTIC` (no-op backend for headless/validation). `SUPPORTED_RENDERER_
BACKENDS` is the curated set; a native `gr_rendering_normalize_renderer_backend`
export can own canonicalization so Python and C++ agree.

Implementing a backend in C++: implement the upstream-neutral contract (a visual
divergence is usually a draw-sort or state-batch order difference, not a math
error); batch by state and sort for correctness then performance (opaque before
transparent, front-to-back for early-z); keep CPU asset truth separate from GPU
resource state (AGENTS.md — texture bytes, decoded image, sampler/material
policy, and backend upload are distinct lifetimes; caching on the wrong one
causes stale output).

## Game Loop, Fixed-Step Update, and Animation FSMs

From Li, applied to the native + Qt runtime:

- **Fixed update, variable render** — step simulation and pose evaluation in
  fixed deltas for determinism; let the Qt viewport paint at display cadence.
  Animation feeds the software frame renderer
  (`src/gui/rendering/frame_core.renderer`), never the reverse. Use an
  accumulator to run extra capped fixed steps when wall-clock outruns a step.
- **Animation as an FSM** — model states (idle/walk/attack/death), transitions,
  and blend windows as a finite-state machine in C++; states own their pose
  source, transitions guard on conditions and blend duration. Maps to KOTOR MDL
  anim refs and Aurora controller semantics
  (`learned/animationruntimeskill.md`).
- **No heavy work on the loop thread** — imports, scans, validations, exports
  run off the loop/animation thread (the T2308 cancellable job bridge).

## Performance-Critical Native Patterns (generalized from Somberg)

Somberg's audio patterns are systems-programming patterns for any hot native
path:

- **Squared-distance culling** — compare `d²`, never `sqrt(d²)`, in any
  per-frame proximity test (picking radius, cull distance, falloff). The single
  highest-leverage native perf rule.
- **Thread-safe command buffer** — submit work from the UI thread to a worker
  via a lock-free or mutexed buffer the worker drains; never share mutable state
  across threads without one. The right shape for the import/export/validation
  job bridge and any native renderer command queue, with plain data-driven
  payloads so one buffer path serves many producers.
- **Object lifecycle: spawn/update/die** — transient native objects (audio
  voices, particles, one-shot diagnostics) back onto a pool, not `new`/`delete`
  per frame. Reuse buffers; cap counts.
- **Per-frame work is O(n) or better** — quadratic checks run on selection
  change, not every paint (`cgameprogrammingskill.md`).

## Algorithms: A* and Procedural Generation

- **A\* pathfinding** — Li's A* is the reference for any native walkmesh path
  query (heuristic grid/navgraph search). It underpins PTH pathing validation:
  can the placed gameplay actually route across the WOK? Native A* over a baked
  nav-surface is the performance tier; Python checks are for correctness, not
  frame-rate paths.
- **Procedural generation (DFS maze)** — Li's depth-first random acyclic maze is
  a clean reference for connectivity-aware generation. In GhostRigger, PG is a
  *helper* for hand-authored modules, never the layout author
  (`learned/proceduralgenerationskill.md`); DFS/grid generators belong under
  `src/core/` or `src/systems/` as pure, seedable, testable functions.

## GhostRigger Applications

- **Host/launch bugs:** a "Python not found" or "NO_PAYLOAD" failure — walk the
  `main.cpp` sequence (repo-root → Python home → DLL audit → `PyConfig`); the
  failing step names the bug.
- **ABI additions:** new C++ capability for Python → narrow versioned export +
  plain descriptor + status-not-exception + a
  `tests/test_native_core_package_registry.py` test.
- **Renderer bugs:** wrong output on one backend → compare against another
  through the same contract; check sort/state-batch order and the
  CPU-asset-vs-GPU-state split before suspecting math.
- **Per-frame stalls:** profile for O(n²); move to squared-distance culling,
  spatial acceleration, or run on selection change.
- **Job/worker design:** use the thread-safe command-buffer shape for any native
  path receiving work from the UI thread.
- **Deterministic rebuilds:** the `grdev01` golden package (T3105) must
  reproduce — fixed-step update plus seeded generators, never wall-clock-driven
  or unseeded native RNG in the build path.

## Anti-Patterns to Reject

- **Domain logic in `main.cpp` / the host `.exe`** — the kernel grows, the system rots.
- **Rich C++ objects crossing the ABI** — always handles + plain descriptors.
- **Exceptions escaping a C export** — translate to status/JSON at the boundary.
- **Shared mutable state across threads without a command buffer.**
- **A backend that invents its own contract** — implement the upstream-neutral interface; resolve divergence by draw order.
- **Linking Debug CPython or rebuilding Python to match `_DEBUG`** — keep the `_DEBUG`-undef `<Python.h>` dance intact.

## Cross-References

`learned/cppnativeskill.md` (C++ mechanics/RAII/ABI — read first);
`learned/cgameprogrammingskill.md` (engine architecture); `learned/
animationruntimeskill.md` (FSMs); `learned/renderingshaderskill.md` (GPU
pipeline); `learned/proceduralgenerationskill.md` (DFS/A*); `learned/
pythonpackagingskill.md` (Bridge/Adapter backends).

## Validation

- **ABI changes:** `tests/test_native_python_payloads.py` +
  `tests/test_native_core_package_registry.py`; build the owning project in
  Debug|x64 and Release|x64.
- **Payload/manifest changes:** `tests/test_native_python_payloads.py` + the
  package-sweep tests; regenerate embedded Python from root `src/`, never
  hand-edit `native/<Project>/Python/...`.
- **Host/launch changes:** exercise repo-root + Python-home + DLL-audit in a
  clean environment; confirm `GHOSTRIGGER_NATIVE_PREPYTHON_AUDIT` and the
  `--native-host-debug` path behave.
- **Renderer-backend changes:** each `SUPPORTED_RENDERER_BACKENDS` entry
  round-trips through `normalize_renderer_backend` (Python and native); the
  Null backend still runs headless validations.
- **Per-frame/native perf changes:** profile; prove O(n) or better; confirm no new cross-thread shared state.
