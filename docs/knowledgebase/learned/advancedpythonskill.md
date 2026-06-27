# Advanced Python Skill (C-Interop, Performance, Import Machinery, Packaging)

This is the **advanced companion** to `learned/pythonskill.md`. The basic skill
covers idiomatic Python (comprehensions, generators, pathlib, exceptions,
testing hygiene). This one covers the things that only matter in a hybrid
C++ host + embedded Python product like GhostRigger: C/C++ interop and the
GIL, parallelism for long scans/validations/exports, the custom import
machinery that loads `.py` from DLL RCDATA, the payload packaging pipeline,
and how to keep the Qt UI thread non-blocking. Use the basic skill for
day-to-day Python; reach for this one when you touch a native boundary, a
performance hot path, the meta-path importer, or the packaging generator.

## Book Grounding

- `Advanced_Python_Programming_-_Quan_Nguyen.pdf`: C performance with Cython
  (static types, C arrays, typed memoryviews, profiling), Numba JIT, parallel
  processing (multiprocessing, `ProcessPoolExecutor`, OpenMP), concurrency
  (asyncio, thread pools), and a deep GIL chapter.
- `Expert_Python_Programming_-_Tarek_Ziade.pdf`: packaging and distribution
  (`setup.py`/setuptools, namespace packages, build/release cycles),
  optimisation and profiling methodology, and design patterns in the larger
  engineering context.

## 1. The GIL and What It Means for GhostRigger

CPython's Global Interpreter Lock lets only one thread execute Python bytecode
at a time. It exists because Python's memory model uses per-object reference
counts, and those counts are a shared resource that must be protected from
race conditions; a single coarse lock is the simplest, cheapest guard.

Consequences:
- **CPU-bound Python does not parallelise across threads.** Two threads each
  counting down 25M do not finish in half the wall-clock time — they finish
  in about the same time as one thread counting 50M, plus lock overhead.
- **I/O-bound code releases the GIL** while waiting (file/sockets), so threads
  still give concurrency for waiting, just not for computing.
- **C extensions can release the GIL** around long compute blocks
  (`Py_BEGIN_ALLOW_THREADS` / `Py_END_ALLOW_THREADS`), then re-acquire before
  touching Python objects. This is how NumPy computes in parallel. The native
  GhostRigger C++ host can do the same.
- **Multiprocessing sidesteps the GIL entirely** — each process has its own
  interpreter and its own lock.

GhostRigger implication: the embedded Python runs *inside* the C++ host
process, on the Qt UI thread unless you explicitly move work off it. Long
Python loops (model scans, validation sweeps, exports) hold the GIL and will
freeze the UI. See section 4.

## 2. C/C++ Interop

GhostRigger has two distinct C/C++ interop surfaces: the **native host** that
embeds Python (a C++ program calling `Py_Initialize` and the payload importer),
and any **C extension / ctypes** boundary a script uses to reach the runtime.

### Reference-counting discipline

Because every Python value is reference-counted, every C-level borrow of a
Python object must respect ownership:
- A borrowed reference (no ownership) is fine while you hold the GIL and the
  owner is alive. Steal/duplicate semantics vary by API; know which.
- When you create or take ownership, you MUST decref when done, on every path
  including error paths. Leaks here are silent and accumulate over a long
  editing session.
- Never touch a Python object's fields from C while the GIL is released.
- Cross-thread handoff of Python objects requires the GIL and a checked
  ownership transfer (the sending thread drops its reference only after the
  receiver has taken one).

### ctypes / cffi boundaries

When a Python script calls into a native DLL (the basic `pythonskill.md` rule
set, restated for emphasis): validate argument types, return codes, and
byte/string encoding; manage buffer lifetime (who frees it?); and handle
platform-specific DLL lookup. These are the cheapest interop to get wrong
because the type contract is implicit (connascence of type/meaning across a
foreign-function boundary).

### Cython / C extensions (when a hot loop needs C speed)

Cython is a Python superset that lets you annotate static types (`cdef int i`,
typed function signatures, typed memoryviews) and compile to C, bypassing
per-operation type lookups. The methodology from the source:
1. Write the loop in plain Python first; prove it correct.
2. **Profile** to confirm the loop is actually the bottleneck (section 3).
3. Add `cdef` types to the inner loop and to array buffers (typed memoryviews
   over `numpy` arrays or raw buffers avoid per-element boxing).
4. Re-measure; only keep type annotations that pay for themselves.
5. For true parallelism inside a Cython extension, release the GIL around the
   compute block (`with nogil:`) and optionally use `prange` (OpenMP).

The rule "optimise last, after profiling" matters in GhostRigger: model math
and validation loops are the usual real hot spots, not glue code.

## 3. Profiling Before Optimising

Discipline (from both source books): measure first, optimise the actual hot
path, and keep the serial version as a correctness oracle.
- Start with `cProfile` to find the hot function, then drill in.
- For fine-grained line timing, use `line_profiler` on the suspected function.
- Always compare wall-clock before/after; a "clever" rewrite that is slower is
  common.
- Prefer algorithmic improvements (O(n^2) -> O(n log n)) over micro-typing;
  then reach for Cython/Numba only if the hot loop is still too slow.

GhostRigger: validation sweeps over thousands of models and MDL/MDX import
parsing are the candidates. Profile a representative single-file import and a
moderate validation batch before assuming the GIL or threads are the answer.

## 4. Keeping the Qt UI Thread Non-Blocking

This is the single most important runtime rule for GhostRigger Python. The Qt
event loop runs on the main thread; the embedded Python executes on that same
thread unless you move work off it. A long Python loop does not just "feel
slow" — it stops the UI from painting, processing input, and emitting signals.

### Strategy selection by workload type

| Workload | Thread-safe? | Right tool |
|---|---|---|
| CPU-bound Python (scan, validate, compute) | GIL-blocked on threads | `QThread` worker + GIL-friendly chunking, or `ProcessPoolExecutor` for true parallelism |
| I/O-bound (read files, sockets) | Releases GIL while waiting | `QThread` worker or `QThreadPool` + `QRunnable` |
| Long but must touch Qt objects | Qt objects are GUI-thread-affine | Worker computes, emits a `pyqtSignal` with plain data; main thread applies it to widgets |

### The canonical off-thread pattern

1. Subclass `QThread` (or use `QThreadPool`/`QRunnable`) for the worker.
2. The worker does the heavy Python and emits `pyqtSignal` instances carrying
   **plain Python data** (ints, str, lists, dataclasses) — never live widget
   references.
3. The main thread connects those signals to slots that update widgets.
   `pyqtSlot`-decorated handlers on the main thread are the safe mutation
   point.
4. Never construct, parent, or call methods on `QWidget`/`QGraphics*` from a
   worker thread. Qt objects are not thread-safe and will crash or corrupt.
5. Keep the worker's per-chunk work large enough to amortise signal emission
   overhead but small enough to emit progress. The multiprocessing lesson
   applies: tiny tasks (one model per IPC round-trip) can be *slower* than
   serial because of communication overhead — chunk the work.

### When to use processes vs. threads

- Threads are lighter but cannot parallelise CPU-bound Python (GIL). Fine for
  I/O and for keeping the UI responsive while one Python computation runs
  (concurrency, not parallelism).
- `ProcessPoolExecutor`/`multiprocessing.Pool` give true parallelism for
  CPU-bound validation/scan batches, but each worker is a separate interpreter
  with separate memory; passing data costs IPC. Chunk tasks so each unit of
  work is much larger than the IPC round-trip.
- A C extension that releases the GIL is the best of both worlds for a hot
  compute kernel: it can run in parallel across threads without IPC cost.

## 5. The Import Machinery: `_DllPythonPayloadImporter`

GhostRigger's embedded Python does NOT load packages from the filesystem in
production. The native host registers a custom **meta-path finder**
(`_DllPythonPayloadImporter`, in
`native/GhostRigger.Native.Core.Host/main.py`) that serves `.py` modules out of
RCDATA resources embedded in the native DLLs. This is the most advanced and
most GhostRigger-specific piece of Python engineering in the repo.

### How meta-path finders work

`sys.meta_path` is a list of finders Python consults, in order, on every
import. A custom finder implements `find_spec(name, path, target)` and returns
a `ModuleSpec` (which carries a loader) when it claims a module, or `None` to
defer to the next finder. GhostRigger's finder:
1. Intercepts imports for the native package namespaces.
2. Resolves the module path to a DLL + RCDATA resource id from the payload
   manifest.
3. Loads the resource bytes and compiles/executes them via a loader that
   implements `create_module`/`exec_module`.

### Engineering rules for the importer

- **Order matters.** The custom finder must be registered before the default
  finders so native payloads win; but it must `return None` for anything it
  does not own so normal imports still work (the stdlib, third-party packages,
  dev-mode `src/`).
- **Dev mode vs. packaged mode.** During development, Python resolves the same
  modules from `src/` on disk. The finder is what makes the packaged DLL build
  behave identically. A `src/` edit that passes dev tests can still fail in
  the packaged build if payloads are stale — which is why regeneration matters.
- **Compile at load, not just at package.** The loader must produce the same
  bytecode semantics; mismatched compile flags (optimisation level, future
  imports) are a subtle source of divergent behaviour.
- **Do no import-time side effects.** Because the finder runs on the import
  path for arbitrary modules, its own dependencies must be minimal and its
  logic fast. Heavy work, file scans, or opening windows at import time break
  both dev mode and packaged mode (this restates the basic skill's rule, now
  with a concrete mechanism).
- **Byte-identity is the contract.** `tests/test_native_python_payloads.py`
  checks that the packaged payload bytes match the source. Any path that
  bypasses the generator (hand-editing a packaged copy) will fail these tests
  and drift from `src/`.

## 6. The Payload Packaging Pipeline

The generator (`scripts/native_python_payload_generator.py`) is GhostRigger's
custom distribution system: it takes the canonical `src/` Python, packs it into
`GhostRiggerPythonPayload.json` manifests and `.rc` RCDATA resource lists,
and embeds the result into the 18 DLL projects.

### Source-of-truth discipline

- `src/` is canonical. The packaged payloads are a **derived artifact**, like
  a compiled `.so`. Never edit a packaged copy as a shortcut — it is
  overwritten on the next regeneration and it breaks byte-identity.
- After a `src/` edit that touches a packaged module, regenerate the affected
  payloads and run the focused native payload tests
  (`tests/test_native_python_payloads.py`), not just the dev-mode tests.
- A manifest that lists a module must correspond to a real, owned package
  (see `couplingskill.md` — empty stubs create manifest churn for no value).
- The packaging model parallels classic setuptools packaging (`setup.py`,
  namespace packages, sdist/wheel) in spirit: a manifest declares what belongs
  in the distributable; the build embeds it. The difference is that
  GhostRigger's "wheel" is a DLL RCDATA blob, not a `.whl`.

### When to touch the generator

- Adding a new module to an existing native package -> update its manifest,
  regenerate, re-run byte-identity tests.
- Adding/removing a whole package -> coordinate with the ownership model; this
  is a coupling decision (see `couplingskill.md` checklist), not just a
  packaging one.
- Changing compile/optimisation flags -> regenerate everything, since
  byte-identity encodes the compile settings.

## 7. Testing the Hard Parts

The AGENTS.md testing rules apply, specialised here:
- `python -m py_compile` on changed files first — cheap syntax check that also
  catches the most common payload-source divergence (a file that compiles in
  dev but was packaged from an older version).
- Prefer targeted `pytest path::test_name` over broad suites.
- For native payload edits, use focused cases from
  `tests/test_native_python_payloads.py` and
  `tests/test_native_core_package_registry.py`.
- For C-extension/ctypes boundaries, test error cases and type conversions
  explicitly (the implicit type contract is where these break).
- For concurrency, test that the UI remains responsive (or that a worker
  emits its signals) — concurrency bugs are timing-dependent and won't show
  in a naive unit test.

## GhostRigger Applications

- **Native host integration**: GIL handling, refcount discipline, and the
  meta-path importer registration.
- **Performance**: profile MDL/MDX import and validation sweeps; only then
  reach for Cython/Numba or process parallelism.
- **UI responsiveness**: move every long Python computation to a `QThread`/pool
  worker; communicate back via `pyqtSignal` with plain data.
- **Packaging**: regenerate payloads after `src/` edits; never hand-edit
  packaged copies.
- **Importer changes**: keep the finder fast and dependency-free; preserve
  dev-mode equivalence.

## Cross-References

- `learned/pythonskill.md` — the basic skill (idioms, generators, exceptions,
  payload-care summary). Read that first for routine Python.
- `learned/cppnativeskill.md` — the C++ host side of the embedding boundary.
- `learned/qtuiskill.md` — Qt threading, signals/slots, widget affinity.
- `learned/couplingskill.md` — why each packaged package must justify its
  existence.
- `AGENTS.md` — testing rules and payload test file list.
