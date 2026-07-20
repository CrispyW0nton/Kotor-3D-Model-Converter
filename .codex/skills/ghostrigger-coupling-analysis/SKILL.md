---
name: ghostrigger-coupling-analysis
description: >
  Analyze coupling, cohesion, and package-boundary decisions in the GhostRigger
  codebase. Use when deciding whether to merge, split, move, or create native
  packages; when evaluating import direction violations; when resolving
  circular dependencies; when auditing the 109-project native package sprawl;
  or when applying knowledge_base/package_ownership_model.md. Covers the five
  coupling dimensions (strength, distance, volatility, type, cost), the seven
  cohesion levels, connascence taxonomy, and rebalancing drifted coupling.
---

# GhostRigger Coupling Analysis

Make deliberate coupling decisions for GhostRigger's hybrid C++ + embedded
Python architecture. The codebase has 109 native projects, 40 empty
`Domain.Core.*` stubs, and a documented ownership model that has drifted from
the actual repository structure. This skill provides the decision framework.

## When to Use

- Deciding whether to merge/split/move a native package
- Evaluating whether a new package boundary is justified
- Auditing import direction violations (e.g., core importing Qt)
- Resolving circular dependencies between packages
- Deciding whether empty Domain.Core.* stubs should be kept or removed
- Evaluating whether the DLL-embedded Python payload coupling is healthy

## Core Principle

**Balance, don't minimize.** Zero coupling means no interactions. The goal is
to keep *essential* coupling deliberate, explicit, and low-magnitude, while
eliminating *accidental* coupling that leaks knowledge across boundaries
without benefit.

## The Five Coupling Dimensions — Score Any Boundary

Score 1 (cheap) to 5 (expensive). The **worst dimension dominates**.

1. **Strength** — how much knowledge flows across it? Name/type = 1;
   value/identity = 4–5. Use the connascence spectrum.
2. **Distance** — same module = 1; same package = 2; different packages same
   build = 3; different DLLs/builds = 4; different machines = 5.
3. **Volatility** — coupling toward stable upstream is cheap; coupling stable
   code to volatile downstream is expensive. (This is why core must not
   import Qt — Qt is volatile presentation, core is stable.)
4. **Type** — data < stamp < control < common-environment < content. Content
   coupling (reaching into internals) is always 5.
5. **Cost** — build time, test surface, cognitive load, change propagation.

## Cohesion Levels (Merge/Split Signal)

Evaluate the module's cohesion (Constantine's 7 levels, worst → best):

1. Coincidental — random grouping (merge candidate)
2. Logical — categorically related but independently executable
3. Temporal — executed at the same time
4. Procedural — executed in sequence
5. Communicational — operate on the same data
6. Sequential — output of one feeds input of next
7. Functional — does one thing well (ideal boundary)

**Rule:** A package scoring ≤3 on cohesion is a merge candidate. A package
scoring 7 on cohesion with high coupling strength is a split candidate.

## GhostRigger Application

### The 40 Empty Domain.Core.* Stubs

Score each stub:
- **Strength** = N/A (0 code, 0 coupling today) → score 1
- **Volatility** = high (no implementation = no contract = will change)
- **Distance** = N/A (no consumers)
- **Cost** = maintenance overhead of tracking 40 empty projects in the solution

**Decision:** Unless a stub has a documented future ABI/runtime/adapter reason,
it should be merged or removed. The ownership model's prime rule applies: "Do
not keep a package only because it already exists."

### The Native Payload Coupling

The `_DllPythonPayloadImporter` in `main.py` couples Python source to DLL-embedded
RCDATA resources:
- **Strength** = 4 (sha256 hash identity, resource_name → module resolution)
- **Distance** = 4 (cross-DLL boundary, Windows kernel32 API)
- **Volatility** = low (RCDATA format is stable)
- **Type** = data coupling (resource_name + byte content)

**Assessment:** This is intentional, high-strength, high-distance coupling
justified by the deployment boundary (single .exe distribution). Keep it but
document the contract explicitly.

### Import Direction Rule

- GUI → adapters → systems → core/math/io/resources/formats
- Core must not import Qt or `src.gui.*`
- Adapters wrap core/systems for a runtime; they don't own domain policy
- Tools orchestrate lower layers; they don't own reusable behavior

## Deep Reference

Read these for full decision trees, connascence taxonomy, and rebalancing
patterns:

- `docs/knowledgebase/learned/couplingdesignskill.md` — merge/split decision
  framework, rebalancing drifted coupling, fractal coupling geometry
- `docs/knowledgebase/learned/couplingskill.md` — connascence spectrum,
  cohesion level catalog, patterns as boundary tools
- `knowledge_base/package_ownership_model.md` — canonical package owners
- `docs/knowledgebase/learned/architectureskill.md` — layering patterns
  (ports/adapters, service layer, repository pattern)
