# Architecture Skill

Use this skill when deciding ownership, boundaries, tests, dependency direction,
service extraction, package placement, or refactoring strategy.

## Book Grounding

- `Architecture Patterns with Python`: domain model, value objects/entities, repositories, ports/adapters, service layer, unit of work, and test pyramid tradeoffs.
- `Clean Architecture`: SRP, OCP, DIP, entities, use cases, interface adapters, and keeping policies independent of frameworks.
- `Game Engine Architecture`: runtime architecture, asset pipeline, resource manager, subsystem startup/shutdown, debugging, profiling, and tools.
- `Refactoring UI`: systematize repeated decisions and avoid one-off design drift in UI surfaces.

## Workflow

1. Name the behavior and its owner before editing. Choose core, systems, adapters, math, io/formats/resources, GUI, or native package based on responsibility.
2. Keep policies inward and frameworks outward. Core and systems should not import Qt or GUI packages.
3. Use ports/adapters when infrastructure varies: filesystem, renderer backend, game resource provider, external tools, MCP, or native runtime.
4. Use a service layer for workflow orchestration that coordinates repositories/providers/domain objects and exposes a small API to UI.
5. Use repositories/providers for storage and resource access instead of letting domain rules know file/runtime details.
6. Add abstractions only where they cut real coupling or duplication. Do not create broad `helpers.py` or `utils.py` piles.
7. Test at the cheapest useful layer first, then add visible checks for user-facing workflows.

## GhostRigger Boundaries

- `src/core/<domain>/`: headless domain models, services, validation, scene/project state, resource rules, import/export decisions, workflow policies.
- `src/systems/<system_name>/`: focused feature systems and model pipelines above core primitives.
- `src/adapters/<technology_or_surface>/`: external runtimes, renderer backends, Qt-facing adapters, file/runtime APIs, integration glue.
- `src/gui/...`: widgets, windows, panels, signals, user gestures, theme/layout, and calls into services.
- `src/math/`: reusable transform, camera, pivot, projection, and coordinate-system math.
- `src/io`, `src/formats`, `src/resources`: file formats, resource discovery, serialization/deserialization.

## Failure Patterns

- A window file gains parsing/export/math rules: move logic to owning core/system/adapter module.
- A core module imports Qt: dependency direction is inverted.
- Tests require patching many internals: abstraction may be missing at the boundary.
- A native package duplicates Python behavior without a contract: add or update focused source-contract tests.
- A workflow needs multiple panels to know private details: create a service/use-case API.
