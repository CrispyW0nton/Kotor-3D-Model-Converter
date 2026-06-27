# Python Performance & Class-Design Engineering Skill

Use this skill for the **engineering discipline** of Python in GhostRigger:
profiling and optimising a hot path, choosing a concurrency strategy for a long
computation, designing a Python class/module for cohesion and implementation
hiding, applying a design pattern *correctly* in Python, and setting code-quality
and linting gates. This is the *process/discipline* layer, not the mechanism
layer. For the *how-it-works* of the GIL, ctypes, and the meta-path importer read
`learned/advancedpythonskill.md`; for idioms read `learned/pythonskill.md`; for
the payload pipeline and the GoF catalogue read `learned/pythonpackagingskill.md`.
Reach for this one when the question is "how do I engineer this well — measure,
structure, and verify it?" rather than "how does this mechanism work?"

## Book Grounding

- `Advanced_Python_Programming_-_Quan_Nguyen.pdf`: the profiling workflow
  (cProfile → line_profiler → memory_profiler), NumPy vectorisation as a
  middle-tier optimisation, Cython/Numba as a last resort, multiprocessing vs.
  asyncio, and the deadlock / race-condition / GIL failure modes.
- `Expert_Python_Programming_-_Tarek_Ziade.pdf`: syntax best practices below and
  above the class level, writing and structuring packages and applications, code
  management, test-driven discipline, optimisation *principles* (measure first),
  and profiling methodology.
- `Software_Design_for_Python_Programmers_-_Maximiliano_Mak.pdf`: iterate toward
  good design, good class design (cohesion, SRP), hide class implementations,
  don't surprise users, design subclasses right (LSP), and the Pythonic
  application of Template Method, Strategy, Factory, Adapter, Façade, Iterator,
  Visitor, Observer, State, Singleton, Composite, and Decorator. Mak is the
  class-design spine none of the other Python skills use.

## Workflow — The Engineering Process

1. **Name the behaviour and its owner first** (see `architectureskill.md` and the
   ownership model) before writing code. Requirements before implementation.
2. **Design the class/module for cohesion + hiding**: one responsibility, hide
   internals, expose behaviour not data, no surprising side effects.
3. **Write it simple and correct first; keep that version as the test oracle.**
4. **Profile before optimising** — measure the real hot path with a
   representative workload.
5. **Optimise at the cheapest effective layer, in order**: algorithm → vectorise
   (NumPy) → release the GIL (Cython `nogil` / a C extension) → parallelise
   (processes). Stop at the first layer that meets the budget.
6. **Re-measure wall-clock before/after.** A clever rewrite that is slower is the
   single most common outcome.

## Profiling Methodology (the disciplined workflow)

- **Level 1 — `cProfile`:** find the hot function by cumulative time.
  `python -m cProfile -o out.prof -s cumtime <script>`; drill with `pstats` or
  `snakeviz out.prof`. This tells you *which* function, not *which line*.
- **Level 2 — `line_profiler`:** decorate the suspected function with `@profile`
  and run `kernprof -lv`. This is where the actual bottleneck line surfaces.
- **Level 3 — `memory_profiler`:** reach for it only when the symptom is
  allocation/GC pressure or runaway memory, not raw CPU.
- **Discipline rules:** always profile a *representative* workload (a real scene
  export, a real validation batch), never a toy loop; prefer an algorithmic
  improvement (O(n²) → O(n log n)) over micro-typing; only then reach for Cython
  or Numba; and keep the un-optimised serial version as the correctness oracle
  you regression-check against.

## Concurrency Decision Model (process; see advancedpythonskill for GIL mechanics)

| Workload | Right tool | Why |
|---|---|---|
| CPU-bound Python loop (scan/validate/compute) | `ProcessPoolExecutor`, or NumPy/Cython with `nogil` | Threads cannot parallelise CPU-bound Python (GIL) |
| I/O-bound (files, sockets) | threads or `asyncio` | GIL is released while waiting |
| Long work that must update Qt | worker thread + `pyqtSignal` carrying plain data | Qt objects are GUI-thread-affine |

**Process rule:** chunk work so each unit is much larger than the
serialisation/IPC round-trip. Per-item parallelism (one vertex, one model per
task) is routinely *slower* than serial because the dispatch cost dominates. Pick
`ProcessPoolExecutor` for CPU-bound Python because it sidesteps the GIL — but
budget the cost of copying data into each worker.

## Class Design Rules (Mak — the differentiator from the other Python skills)

- **SRP:** a class has one reason to change. If a class accumulates independent
  reasons (parsing *and* rendering *and* persistence), split the responsibility;
  do not just split the file.
- **Cohesion:** all of a class's methods should operate on the same data toward
  one purpose. A class that mixes concerns is coincidentally/ logically cohesive
  — see `couplingskill.md` for the levels.
- **Hide implementation:** expose behaviour, not internal structures. A class
  whose internals are read and mutated by many callers has low hiding and high
  accidental coupling, however tidy it looks.
- **Don't surprise users:** a method does what its name says — no hidden side
  effects, no silently mutating inputs, consistent return types. Surprising
  behaviour forces every caller to learn undocumented rules.
- **Design subclasses right (LSP):** a subclass must be substitutable for its
  base. Overriding a method to reject a case the base accepted breaks the
  contract. Prefer composition over inheritance when behaviour varies; use
  `abc.ABC`/`typing.Protocol` to make the contract explicit.

## Module / Package Structure (Ziade + Mak)

- One responsibility per module; make public exports intentional (`__all__`
  where it clarifies the API surface).
- **No import-time side effects** — no filesystem scans, no window opens, no
  heavy optional-dependency imports at module top level. This is doubly binding
  in GhostRigger because `_DllPythonPayloadImporter` runs on the import path for
  arbitrary modules (see advancedpythonskill); import-time work breaks both dev
  mode and the packaged DLL build.
- **No `helpers.py` / `utils.py` junk drawers** (AGENTS.md). Name the concept;
  if you cannot name it, it does not belong in a module yet.
- Keep the entrypoint thin: services orchestrate, domain stays headless, Qt lives
  only in GUI.

## Code-Quality & Linting Gates (Ziade code management)

- `python -m py_compile` on changed files first — the cheapest gate; it also
  catches the common payload-stale divergence (a file that compiles in dev but
  was packaged from an older version).
- Type-hint public APIs; run `ruff`/`mypy` on the changed scope, not the whole
  tree.
- **TDD discipline:** write the failing test, implement until green, refactor
  while green. Keep the fast test as the oracle.
- Keep tests small, deterministic, and close to the owning layer; patch only at
  real boundaries.

## GhostRigger Application

### Profiling target — `ValidationService`

`src/core/diagnostics/validation_service.py` is the textbook profiling
candidate. It is currently **serial, pure-Python**: `ValidationService.validate()`
iterates per-slot → per-node → per-vertex, recomputing skin-weight sums and
influence counts in Python loops, with a `max_weight_errors` cap (default 20) that
is already a pragmatic throttle — a clear signal the loop is known to be heavy.
Apply the workflow: cProfile a representative multi-part scene, confirm the
per-vertex weight loop is the hot path with line_profiler, *then* choose between
vectorising the sums in NumPy, process-parallelising across slots/models, or
moving the kernel to Cython with `nogil`. Do not assume the answer before
profiling.

### NumPy for vertex/skin math — a candidate, not a given

The math and skinning code paths are **not currently NumPy-based**. Vectorising
the bone-influence and weight-normalisation loops is a *candidate* optimisation,
applied only after profiling proves that path is the bottleneck. Premature
NumPy-ification of code that is fast enough adds a dependency and a mental-model
tax for no gain.

### The payload importer as a robustness/load boundary

`_DllPythonPayloadImporter` (in
`native/GhostRigger.Native.Core.Host/main.py`) resolves every packaged import
through `ctypes` → `kernel32.FindResourceA`/`LoadResource`/`LockResource` →
RCDATA → `compile(..., "exec")`. Two engineering rules follow: (1) keep module
loading off the per-frame hot path — modules are imported once at startup, not
every render; (2) the empty-file sha256 sentinel (`e3b0c442…`) handled in
`get_data` is a real edge of the byte-identity contract and must survive any
refactor of the loader. The loader itself must stay fast and dependency-free
because it runs on the import path for arbitrary modules.

### Concurrency for validation and batch exports

When parallelising CPU-bound Python (validation sweeps, batch MDL/MDX import,
batch export), choose `ProcessPoolExecutor` — threads cannot help CPU-bound
Python under the GIL. Chunk per-model (not per-vertex), pass **plain Python
data** (ints, lists, dataclasses) into workers, never live widget/Qt references,
and communicate results back via `pyqtSignal` on the GUI thread. See
`advancedpythonskill.md` for the QThread worker pattern and `qtuiskill.md` for
widget affinity.

### Packaging the multi-DLL payload distribution

The generator, the per-project `GeneratePythonPayload.py`, and each
`GhostRiggerPythonPayload.rc` are the build-artifact layer (see
`pythonpackagingskill.md` for the pipeline). The engineering rule here is
contract-focused: byte-identity is the contract, compile/optimisation flags are
part of it, and the build must be deterministic for a given source tree + flags —
so regenerate from canonical `src/`, never hand-edit a packaged copy.

### Class design applied

`ValidationIssue` / `Severity` (dataclass + enum) and `ValidationService` are a
good local template: one responsibility per unit, internals hidden behind a
small `validate()`/`errors`/`warnings`/`passed` surface. Follow that shape for
new services rather than growing a method-per-rule god-object.

## Patterns Applied Correctly in Python (Mak; complements pythonpackagingskill)

- **Template Method:** define an algorithm skeleton in a base, override steps in
  subclasses — a clean fit for a validation *rule pipeline* where each rule is
  one overridden step sharing the iterate-and-collect skeleton.
- **Strategy:** pick an algorithm/backend at runtime (renderer backends, fast vs.
  thorough validation) behind a common interface.
- **Adapter / Façade:** for renderer and runtime compatibility shims. Mak's
  emphasis on *not surprising users* applies directly — the adapter must preserve
  the contract callers expect; a façade that just forwards every call 1:1 adds no
  value.
- **Observer:** Qt signals/slots (see `qtuiskill.md`).
- **State / Singleton / Composite / Decorator:** apply only where they cut real
  complexity. Singleton especially is an anti-pattern when it hides global
  mutable state — prefer dependency injection.

## Anti-Patterns to Reject

- Optimising before profiling; optimising the wrong layer.
- Premature NumPy-ification or premature abstraction.
- Threads for CPU-bound Python (the GIL makes them a no-op for parallelism).
- A subclass that narrows a base method's accepted inputs (LSP violation).
- Import-time side effects (breaks the meta-path importer and dev equivalence).
- A Singleton that smuggles global mutable state behind a "pattern".

## Cross-References

- `learned/pythonskill.md` — idiomatic Python (comprehensions, generators,
  pathlib, exceptions). Read for routine code.
- `learned/advancedpythonskill.md` — the *mechanisms*: GIL internals, ctypes/C
  interop, `_DllPythonPayloadImporter`, QThread workers, payload packaging.
- `learned/pythonpackagingskill.md` — the payload pipeline and the GoF pattern
  catalogue (Command/Strategy/Adapter/Façade/Observer/Factory/Bridge).
- `learned/couplingskill.md` — class cohesion and implementation hiding as
  coupling signals; connascence taxonomy.
- `learned/architectureskill.md` — name the owner before coding.
- `learned/qtuiskill.md` — signals/slots and QThread affinity.
- `AGENTS.md` — testing rules, "no helpers.py/utils.py", payload test files.
