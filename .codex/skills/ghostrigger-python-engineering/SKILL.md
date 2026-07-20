---
name: ghostrigger-python-engineering
description: >
  Apply advanced Python engineering practices to GhostRigger's 1,162-file
  embedded-Python codebase. Use for profiling and optimization (cProfile,
  line_profiler, memory_profiler), NumPy array operations for vertex/skin math,
  concurrency and parallelism (asyncio, multiprocessing, threading), C extensions
  and ctypes bridges to DLL payloads, embedded packaging design, design patterns
  for Python (adapter, facade, observer, command, strategy), code quality and
  linting, and managing the 18-payload-DLL distribution system.
---

# GhostRigger Python Engineering

GhostRigger's Python codebase is large (1,162 payload files across 18 DLL
projects), embedded in a C++ host, and performance-critical for viewport
rendering, MDL parsing, and animation evaluation.

## When to Use

- Python profiling and optimization (slow viewport, slow MDL load, slow validation)
- NumPy vectorization of vertex/normal/skin-weight math
- Concurrency for long-running jobs (imports, scans, validation, exports)
- ctypes / C extension work (DLL payload bridge, native ABI)
- Packaging and payload generation (18 DLL manifest system)
- Design pattern selection (adapter for renderer backends, observer for signals)
- Code quality, linting, and maintainability
- Managing the dual-source reality (root src/ vs native payload dirs)

## Profiling Workflow

1. **Start with `cProfile`** for function-level hot spots:
   ```python
   import cProfile; cProfile.run('expensive_call()', sort='cumulative')
   ```
2. **Drill down with `line_profiler`** for per-line cost in the hot function:
   ```python
   from line_profiler import LineProfiler; lp = LineProfiler()
   lp.add_function(target_func); lp.runcall(target_func)
   lp.print_stats()
   ```
3. **Check memory with `memory_profiler`** for large vertex/texture arrays:
   ```python
   from memory_profiler import profile
   @profile
   def load_mdl(path): ...
   ```

## NumPy for Vertex/Skin Math

Vectorize per-vertex operations:
- **Vertex transforms**: batch-multiply vertex position arrays (N×3) by 4×4
  matrices using `np.einsum` or `np.dot` with broadcasting
- **Skinning**: use pre-sorted bone-index arrays to scatter vertex weights
  into bone-local groups, transform per-bone, then gather back
- **Normals**: transform normals with the inverse-transpose of the model matrix;
  renormalize with `np.linalg.norm` on the last axis
- **Avoid per-vertex Python loops** — they are 100–1000× slower than vectorized ops

## Concurrency Model

| Pattern | When | Tool |
|---------|------|------|
| Async I/O | Non-blocking file/network/UI | `asyncio` |
| CPU parallelism | MDL batch parsing, full scans | `multiprocessing.Pool` |
| Thread offload | Qt-blocking long jobs | `QThread` + signal/slot |
| Process isolation | Crash-safe validation | subprocess |

**GIL awareness**: pure-Python loops hold the GIL. Use `multiprocessing` for
CPU-bound work, or release the GIL via Cython/ctypes/C extensions. NumPy
operations release the GIL for C-level computation.

## Embedded Payload Packaging

The 18 DLL projects each carry a Python payload manifest:
- `native/<Project>/GhostRiggerPythonPayload.json` — per-project manifest
- `native/<Project>/GhostRiggerPythonPayload.rc` — RCDATA resource list
- `native/<Project>/GeneratePythonPayload.py` — project-local wrapper
- `scripts/native_python_payload_generator.py <Project>` — regenerate one package
- `scripts/native_python_payload_generator.py --all` — regenerate all
- `tests/test_native_python_payloads.py` — byte-identity verification

## Design Patterns Applied

| Pattern | GhostRigger Use |
|---------|----------------|
| Adapter | Renderer backends (ModernGL/D3D12/PyGFX/Null) |
| Facade | `qt_viewport.py` lazy compatibility facade |
| Observer | Qt signals/slots for ValidationBus, theme changes |
| Command | Undo command foundation (T2307) |
| Strategy | Retarget mode policies (`kotor_to_kotor`, etc.) |
| Factory | Resource provider selection by scheme |
| MVC | GUI panels (view) → services (controller) → core (model) |

## Code Quality Rules

- No `helpers.py`, `utils.py`, or window-local function piles
- No broad compatibility namespaces (`GUI.Display.*` for new work)
- Prefer focused modules in the correct layer
- `py_compile` is the first check; targeted `pytest path::test` second
- Never run broad suites without explicit approval
- Keep Qt out of core/systems (the import direction rule)

## Deep Reference

- `docs/knowledgebase/learned/pythonengineeringskill.md` — profiling, NumPy,
  concurrency, ctypes bridge, packaging, GhostRigger-specific patterns
- `docs/knowledgebase/learned/advancedpythonskill.md` — Cython, Numba,
  exploring compilers, JAX, concurrent web requests, GIL internals
- `docs/knowledgebase/learned/pythonpackagingskill.md` — payload manifest
  system, setup.cfg, entry points, distribution
- `docs/knowledgebase/learned/pythonskill.md` — Pythonic implementation,
  iterators/generators, file/IO, testing/debugging
