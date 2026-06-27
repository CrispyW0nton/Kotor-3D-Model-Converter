# Coupling & Module-Boundary Skill

Use this skill when deciding what becomes a package, what merges, what a module
is allowed to import, how to shape API contracts across GhostRigger boundaries,
and how to justify that 109 native packages should collapse toward ~18 real
owners. This is the architecture-decision lens that the package ownership model
(`knowledge_base/package_ownership_model.md`) and the AGENTS.md layering rules
depend on.

## Book Grounding

- `Balancing_Coupling_in_Software_Design_-_Vlad_Khononov.pdf`: coupling
  magnitude (shared lifecycle + shared knowledge), flow of knowledge
  (upstream/downstream), the connascence spectrum (static: name/type/meaning/
  algorithm/position; dynamic: execution/timing/value/identity), integration
  strength (intrusive/functional/model/contract), and "balancing" rather than
  blindly minimising coupling.
- `Structured_design_-_Larry_L_Constantine.pdf`: the original coupling
  spectrum (data/stamp/control/common/content), the seven levels of cohesion
  (coincidental -> logical -> temporal -> procedural -> communicational ->
  sequential -> functional), and design heuristics (module size, span of
  control, fan-in, scope of effect vs. scope of control).

## Core Concepts, Distilled

### Coupling is the glue, not the enemy

Coupling is just "connected." Components that collaborate MUST share knowledge
and therefore MUST be coupled to some degree. The goal is never zero coupling
— that would mean a system with no interactions. The goal is to eliminate
*accidental* coupling (knowledge that leaks across a boundary for no reason)
and to keep *essential* coupling (knowledge the collaboration genuinely needs)
deliberate, explicit, and low on the magnitude scale.

Two drivers raise coupling magnitude: **shared lifecycle** (deployed/tested/
built together) and **shared knowledge** (awareness of each other's interfaces,
types, behaviour, or implementation details). The more knowledge flows across a
boundary, the more often the two sides must change together.

### Flow of knowledge: upstream vs. downstream

Knowledge flows *against* the direction of dependency. An upstream component
provides functionality and exposes the knowledge of how to integrate with it.
A downstream component consumes that functionality and must know the upstream's
integration contract. In GhostRigger: `src/core/` is upstream of
`src/systems/`, which is upstream of `src/adapters/` and `src/gui/`. The core
must never import Qt because that would force the most stable, most reused
layer to know about the most volatile, presentation-specific layer — a gross
upward leak of knowledge.

### The connascence spectrum (use this to score any boundary)

When two modules must change together, ask *why*. The connascence model ranks
the reason from weakest (best) to strongest (worst). When several are present,
the strongest one dominates.

Static (compile/read-time, cheapest to detect):
1. **Name** — must agree on a name (method, variable, attr). Weakest; this is
   what every normal function call is.
2. **Type** — must agree on a type. Fine when the type is a stable domain
   value object owned by the upstream layer.
3. **Meaning** — must agree on a magic value (`status == 3`). Downgrade to
   name/type by introducing an enum or named constant.
4. **Algorithm** — must agree on an algorithm to interpret exchanged data
   (both sides recompute the same MD5, the same tangent-space basis). A sign
   that the logic belongs in ONE owner, not duplicated.
5. **Position** — must agree on element order (`data[2]` is the subject).
   Downgrade to name by using named arguments, dataclasses, or kwargs.

Dynamic (runtime, harder to detect):
6. **Execution** — must call methods in a fixed sequence
   (`open -> begin -> execute -> commit -> close`). High — the methods are
   really one protocol and likely belong together.
7. **Timing** — must observe a specific interval between calls.
8. **Value** — invariant: several values must change together to stay valid
   (triangle edges, `is_verified` + `priority_shipping`). These are "born
   together" — they should be in the same module, behind one setter.
9. **Identity** — must reference the exact same instance (shared connection
   pool, shared mutable model). Strongest — implies strongly consistent shared
   state.

Rule: a high connascence level is a signal to *keep things close*, not to add
indirection. If two things are connascent by value, putting them in separate
packages only adds accidental coupling (the bridge you build to keep them in
sync). Merge them.

### Cohesion (the other side of the same coin)

Cohesion is how tightly a module's internals belong together. The seven levels,
worst to best:

- **Coincidental** — grouped by accident (e.g. "these statements happened to
  repeat"). A "random module." Lowest.
- **Logical** — grouped because they do the same *category* of thing ("all
  error handlers"), but do not cooperate.
- **Temporal** — grouped only because they run at the same time
  ("initialise everything").
- **Procedural** — grouped because they execute in a sequence.
- **Communicational** — operate on the same data.
- **Sequential** — output of one feeds the input of the next.
- **Functional** — all elements cooperate to do exactly one thing. Highest.

Constantine's key result: **cohesion and coupling are inversely correlated.**
Maximising cohesion across modules approximates minimising inter-module
coupling. Practically, cohesion is the more useful handle — it answers
"Does this belong together as a module?" and "Does this belong in *this*
package or that one?"

## GhostRigger Tie-In: The 109-Package Problem

GhostRigger ships ~109 native (C++ host) packages, of which only ~18 have
documented owners and ~40 are empty `Domain.Core.*` stubs. This is a textbook
cohesion failure, and the coupling/cohesion lens tells you exactly how to
triage it.

### Why empty stubs violate cohesion

An empty `Domain.Core.Whatever` package is **coincidentally cohesive at best**
— it has no functional reason to exist; it was created as a slot that never got
filled. Empty/duplicate packages also raise **lifecycle coupling** for no
benefit: each one is a DLL project, a payload manifest entry, a `.rc` RCDATA
resource list, a registration in the package registry, and a byte-identity test
target — all of which must be maintained and kept in lockstep even though the
package carries no logic.

The ownership model mandates merging duplicate/empty packages into their real
owner. Apply the lens:
- If two packages share the same functional purpose -> **functional cohesion**
  says they are one module. Merge.
- If a package is empty -> it has no cohesive principle at all. Delete it or
  fold its intended responsibility into the nearest real owner.
- If a package duplicates another's data structures and re-implements the same
  algorithm -> **connascence of algorithm + value** says they are born
  together. Merge into the owner that owns the canonical data.

### The dependency-direction discipline (AGENTS.md layering)

GhostRigger layers are an enforcement of upstream/downstream knowledge flow:

```
src/core/        (headless domain — MOST upstream, most stable)
   ^
src/systems/     (orchestration, tool workflows)
   ^
src/adapters/    (renderer/Qt/runtime glue — MOST downstream re: core)
   ^
src/gui/         (presentation; Qt lives here and ONLY here)
```

- `src/core/` must NEVER import Qt, PySide6, or anything from `gui/` or
  `adapters/`. Importing Qt into core is **intrusive coupling** (the worst
  integration-strength level): it makes the most-reused layer depend on the
  most volatile one.
- `src/math/` and `src/io/` are leaf-level upstream utilities with maximal
  fan-in (many depend on them; they depend on nothing). High fan-in / low
  fan-out is exactly the "transform-centered" morphology Constantine
  recommends for stable, reusable leaves.
- Renderer backends (D3D12/ModernGL/PyGFX/Null) live in adapters and must
  implement a contract owned by a more abstract upstream layer, not leak their
  specifics back into systems/core.

## Decision Checklist: New Package vs. Merge Into an Owner

Walk this before creating `native/GhostRigger.Native.Core.NewThing/` or a new
`Domain.Core.*`:

1. **Functional cohesion** — Can you state the package's purpose in one
   sentence that is NOT also true of an existing owner? If two owners both
   claim it, you have a cohesion overlap. Merge.
2. **Born-together test** — Are its elements connascent by value/algorithm/
   identity with elements in another package? If yes, splitting them only adds
   a bridge. Merge.
3. **Lifecycle cost** — Does it need a DLL project, a `GhostRiggerPythonPayload.json`
   manifest, `.rc` RCDATA entries, registry wiring, and byte-identity tests?
   (Every native package does.) Is that maintenance burden justified by a
   distinct cohesive purpose, or is it accidental lifecycle coupling?
4. **Knowledge direction** — Does the new package depend only downward in the
   layer stack (core -> systems -> adapters -> gui)? If it would need to import
   from a higher layer, the boundary is wrong.
5. **Contract vs. model** — Is the package exposing an integration *contract*
   (stable, abstract, minimal knowledge) or leaking an implementation *model*
   (unstable, detailed)? If the latter, it is not yet ready to be a boundary.
6. **Owner exists?** — Does the ownership model already name an owner for this
   domain? Default to merging; only split when there is a *durable* reason
   (independent lifecycle, genuinely distinct cohesive purpose, or a hard
   decoupling need such as an optional runtime dependency).

## Designing the Contract at a Boundary

When two packages genuinely must be separate (e.g. a core domain package and
its renderer adapter), design the *contract*, not the implementation:

- Expose an integration-specific interface (an abstract base / Protocol) in
  the upstream layer. Downstream packages implement it. This is **contract
  coupling** — even its strongest degree shares less knowledge than the
  weakest implementation-model coupling.
- Keep the contract minimal: prefer connascence of name/type. Avoid magic
  integers (meaning), positional tuples (position), and "both sides must run
  the same algorithm" duplication (algorithm).
- The contract should be more stable than the implementation behind it, so the
  implementation can evolve faster without cascading changes downstream. This
  is precisely why renderer backends live behind a stable viewport/render
  contract.
- Watch for **shallow modules**: a DTO/contract that merely mirrors the
  implementation model (same fields, same types) encapsulates no knowledge —
  it adds a moving part for no value. Only introduce a contract object when it
  genuinely abstracts something.

## Patterns as Boundary Tools

Khononov maps the classic GoF patterns onto integration strength:
- **Facade** — a single simplified entry point over a complex subsystem;
  reduces the knowledge a client must hold. GhostRigger's viewport
  compatibility shims are facades.
- **Adapter** — converts one interface into another so incompatible components
  can talk without either changing. Used at renderer/runtime boundaries.
- **Bridge** — decouples an abstraction from its implementation so the two
  vary independently. This is the structural rationale for the multi-backend
  renderer design.

(See `pythonpackagingskill.md` for the implementation side of these patterns.)

## GhostRigger Applications

- **Package triage**: collapse the 40 empty `Domain.Core.*` stubs and merge
  duplicates toward the ~18 documented owners, using the checklist above.
- **New package proposals**: run the 6-step decision checklist; default to
  merge.
- **Layer enforcement**: reject any change that imports Qt into `src/core/`
  or crosses the dependency direction.
- **Contract design**: when adding a renderer adapter or runtime glue, define
  the contract in the upstream layer and keep it name/type-coupled.
- **Reviewing a boundary**: ask "what is the highest connascence level here,
  and does it justify this package existing separately?"

## Anti-Patterns to Reject

- "One package per concept I thought of" with no functional cohesion ->
  coincidental cohesion sprawl.
- Empty placeholder packages "for later" -> lifecycle coupling with zero
  value.
- A contract object that is a 1:1 field copy of the implementation model ->
  shallow module; encapsulates nothing.
- Duplicating an algorithm on both sides of a boundary to "avoid a
  dependency" -> you have not removed coupling, you have made it implicit and
  fragile (connascence of algorithm).
- Putting logic in a lower layer that imports a higher layer -> breaks the
  flow of knowledge and the layering rule.

## Cross-References

- `knowledge_base/package_ownership_model.md` — the ownership/merge mandate.
- `AGENTS.md` — layering rules, dependency direction, package ownership lists.
- `learned/architectureskill.md` — overall layering and morphology.
- `learned/cppnativeskill.md` — the C++ host / embedded Python boundary.
- `learned/pythonpackagingskill.md` — Facade/Adapter/Bridge implementation.
