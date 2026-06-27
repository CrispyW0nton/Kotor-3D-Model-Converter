# Python Packaging & Design Patterns Skill

Use this skill for two things that are deeply intertwined in GhostRigger: (1)
the **embedded Python payload packaging pipeline** — how `src/` Python becomes
DLL-embedded RCDATA resources with byte-identity guarantees, and (2) the
**design patterns** that make the codebase's boundaries work: Factory,
Strategy, Adapter, Facade, Observer, and especially Command (the foundation
for the planned T2307 undo system). The packaging content is GhostRigger's
analogue of classic Python distribution (`setup.py`/setuptools); the patterns
content is how the renderer backends, viewport shims, and command stack are
structured.

## Book Grounding

- `Expert_Python_Programming_-_Tarek_Ziade.pdf`: writing and releasing Python
  packages — the `setup.py`/setuptools model, namespace packages, the
  build/release/distribute cycle, and the philosophy of standardised,
  repeatable packaging that shortens boilerplate and eases releases.
- `Mastering_Python_Design_Patterns_-_Sakis_Kasampalis.pdf`: Factory,
  Adapter, Facade, Command, Observer, Strategy — each with intent, use cases,
  and Python implementation guidance.

## Part A — Packaging: The GhostRigger Payload Pipeline

### The classic model (what the pipeline mirrors)

Classic Python packaging (setuptools/distutils) is built around a `setup.py`
that calls `setup(name=...)` with metadata, declares the package contents, and
exposes commands: `build`, `sdist` (source tarball), `bdist` (binary), and
`install`. The principles that carry over to GhostRigger:
- A **manifest** declares exactly what belongs in the distributable.
- The distributable is a **derived artifact**, built from canonical source.
- The build is **repeatable**: same source + same settings -> same output.
- Namespace packages let many distributions share one top-level namespace
  (GhostRigger's `GhostRigger.Core.*` / `Domain.Core.*` trees are the analogue).

### GhostRigger's pipeline

GhostRigger does not ship `.whl` files; it ships **DLLs with embedded Python**.
The pipeline (`scripts/native_python_payload_generator.py`) turns canonical
`src/` modules into native resources:

1. **Canonical source**: `src/` (and `native/<Project>/Python/src/` where a
   package-local module is intentional and documented). This is the only place
   to edit logic.
2. **Manifest**: each native project has a `GhostRiggerPythonPayload.json`
   declaring which modules it owns and how they map to resources.
3. **Resource list (`.rc`)**: the manifest drives an `.rc` file that lists the
   RCDATA resources the C++ compiler embeds into the DLL.
4. **DLL projects**: 18 native projects embed their payloads.
5. **Byte-identity tests** (`tests/test_native_python_payloads.py`): assert
   the packaged bytes match the generator's output from source, so a
   hand-edited or stale payload fails CI.

### Pipeline engineering rules

- **Source-of-truth**: `src/` is canonical. The payload is a compiled
  artifact, like a `.so`. Never edit a packaged copy; it will be overwritten
  and it breaks byte-identity.
- **Regenerate after source edits**: when a module that is packaged into a DLL
  changes, regenerate the affected payloads and run focused payload tests —
  dev-mode tests passing is not sufficient because they run against `src/`,
  not the embedded bytes.
- **Compile flags are part of the contract**: the optimisation level and
  future-import settings used at packaging time must match what the runtime
  importer expects; they are encoded into byte-identity.
- **Manifests follow ownership**: a manifest entry should correspond to a
  real, owned package. Empty `Domain.Core.*` stubs that produce manifest entries
  for nothing are lifecycle-coupling overhead (see `couplingskill.md`).
- **Repeatable build**: the generator must be deterministic for a given source
  tree + flags. Non-determinism (timestamps, unordered iteration) causes
  spurious byte-identity failures.

### Adding / changing a package (checklist)

1. Decide whether it is a new package or a merge (run the coupling checklist in
   `couplingskill.md` first).
2. Put canonical code under `src/` (or document why a package-local module is
   intentional).
3. Update the project's `GhostRiggerPythonPayload.json` manifest.
4. Regenerate payloads.
5. Update the `.rc` resource list if modules were added/removed.
6. Run focused tests from `tests/test_native_python_payloads.py` and
   `tests/test_native_core_package_registry.py`.
7. `python -m py_compile` the changed files as the cheap first gate.

## Part B — Design Patterns

These patterns are the structural toolkit for GhostRigger's boundaries. Each
is tied to a concrete subsystem.

### Command (undo foundation — planned T2307)

Intent: encapsulate an operation as an object with `execute()` (and
`undo()`), so the invoker is decoupled from the performer, commands can be
queued/scheduled, and a sequence of executed commands supports multi-level
undo/redo.

Why it is the right fit for GhostRigger undo:
- Every model edit (move vertex, set bone weight, rename, transform) becomes a
  Command object that captures the before-state and knows how to reverse
  itself.
- A command stack (with an undo and redo pointer) gives multi-level undo by
  replaying `undo()`/`execute()` on the stored objects.
- The invoker (a menu action, a viewport gesture, a tool) does not need to know
  HOW the edit is performed — only that it can call `execute()`/`undo()`.
- Commands can be composed into macros (a group executed/undone atomically).

Implementation shape (Python):
```
class EditCommand:
    def execute(self): ...   # apply the change
    def undo(self): ...      # reverse it

class UndoStack:
    def __init__(self): self._done, self._undone = [], []
    def push(self, cmd): cmd.execute(); self._done.append(cmd); self._undone.clear()
    def undo(self):
        if self._done: cmd = self._done.pop(); cmd.undo(); self._undone.append(cmd)
    def redo(self):
        if self._undone: cmd = self._undone.pop(); cmd.execute(); self._done.append(cmd)
```
Rules: capture enough state in `execute()` to fully reverse it; keep commands
small and single-purpose; a command that touches the Qt UI should still own
its domain change and emit a signal — do not couple the command to widget
internals. The Command pattern is also the basis for transactional behaviour
and change logging (record every command for crash recovery / audit).

### Strategy (renderer backends / algorithms)

Intent: define a family of interchangeable algorithms and let the client pick
one at runtime without changing its code.

GhostRigger tie-in: the multiple renderer backends (D3D12 / ModernGL / PyGFX /
Null) are strategies behind a common render interface. Selecting the backend
at runtime (by capability, platform, or user preference) is the killer feature
of Strategy — the calling code is unaware which algorithm/backend runs.

Also applies to: export format selection, validation strategy (fast vs.
thorough), and any place where the same problem has several implementations
chosen by input size/criteria.

Implementation shape: a shared interface (abstract base / Protocol) with one
concrete strategy per implementation; the client holds a reference to the
interface, not a concrete class. Python's `sorted(key=...)` is the canonical
built-in Strategy example.

### Adapter (renderer/runtime compatibility)

Intent: convert one interface into another so incompatible components can work
together without either being modified. Respects the open/closed principle —
extend by wrapping, don't modify the foreign/legacy component.

GhostRigger tie-in: adapter wrappers reconcile the differing APIs of renderer
backends and runtime integrations so the rest of the code talks one shape.
Adapters are the implementation vehicle for contract coupling at a boundary
(see `couplingskill.md`): the upstream code depends on the adapter's target
interface; the adapter holds the foreign object and translates calls.

### Facade (viewport compatibility shims)

Intent: provide a single, simplified entry point over a complex subsystem,
exposing only what the client needs and hiding internal complexity. The
internal system loses no functionality; the client just sees less.

GhostRigger tie-in: the viewport compatibility shims are facades — a single
simple surface over the rendering subsystem so client code calls one method
instead of orchestrating many. Facades also promote loose coupling between
layers (one entry point per layer communicates through facades). A shallow
facade that just forwards every call 1:1 adds no value — a facade should
genuinely simplify and encapsulate.

### Observer (signal/slot, model->view)

Intent: a publisher (subject) notifies one or more subscribers (observers)
when its state changes, so views/data stay in sync without the publisher
knowing who its observers are.

GhostRigger tie-in: this is exactly Qt's signals/slots, used pervasively.
The model emits a signal; multiple views (viewport, property panel, outliner)
subscribe and update themselves. Adding/removing observers is dynamic at
runtime. The publisher stays decoupled from the subscribers — it just emits
notifications. (For the threading rules around emitting signals across
threads, see `advancedpythonskill.md` and `qtuiskill.md`.)

### Factory (constructing the right backend/object)

Intent: centralise object creation so the caller does not hard-code a concrete
class. Use when creation involves selection logic (pick a renderer backend by
capability), when you want to isolate the caller from construction details,
or when you build families of related objects.

GhostRigger tie-in: a factory selects and constructs the active renderer
backend from the registered strategies; document/model factories build the
correct concrete type from a format/version tag. Prefer a function or class
method factory over a heavyweight class hierarchy unless you need the
parametrised/abstract-factory variant.

## Pattern Selection Cheat-Sheet

| Need | Pattern | GhostRigger use |
|---|---|---|
| Undo/redo, transactional edits, macros | Command | T2307 undo stack; model edit operations |
| Pick an algorithm/backend at runtime | Strategy | D3D12/ModernGL/PyGFX/Null renderers |
| Make incompatible interfaces talk | Adapter | renderer/runtime compatibility wrappers |
| One simple entry point over a subsystem | Facade | viewport compatibility shims |
| Notify many views of a change | Observer | Qt signals/slots (model->view) |
| Centralise object creation with selection logic | Factory | backend selection, document construction |
| Decouple abstraction from implementation | Bridge | render abstraction vs. concrete backend |

## GhostRigger Applications

- **T2307 undo**: build the Command pattern + UndoStack as the foundation;
  model every domain edit as a reversible command.
- **Renderer architecture**: Strategy for backend selection, Adapter for
  compatibility, Facade for the viewport shim, Bridge structurally separating
  the render abstraction from each backend.
- **Model/view sync**: Observer via Qt signals for responsive multi-view
  updates.
- **Packaging**: maintain the source-of-truth pipeline; regenerate after edits;
  keep byte-identity tests green.

## Cross-References

- `learned/couplingskill.md` — patterns as boundary tools (Facade/Adapter/
  Bridge mapped to integration strength); package-merge decisions.
- `learned/advancedpythonskill.md` — the import machinery that loads these
  packaged payloads, and threading rules for command execution.
- `learned/qtuiskill.md` — signals/slots (Observer), QThread workers,
  widget affinity.
- `learned/pythonskill.md` — payload-care basics and `src/`-canonical rule.
- `AGENTS.md` — packaging test files and testing rules.
