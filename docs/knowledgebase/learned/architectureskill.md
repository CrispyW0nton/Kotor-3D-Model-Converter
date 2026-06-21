# Architecture Skill

Use this skill when deciding ownership, boundaries, tests, dependency direction,
service extraction, package placement, or refactoring strategy.

## Book Grounding

- `Architecture Patterns with Python`: domain model, value objects/entities, repositories, ports/adapters, service layer, unit of work, and test pyramid tradeoffs.
- `Clean Architecture`: SRP, OCP, DIP, entities, use cases, interface adapters, and keeping policies independent of frameworks.
- `Game Engine Architecture`: runtime architecture, asset pipeline, resource manager, subsystem startup/shutdown, debugging, profiling, and tools.
- `Refactoring UI`: systematize repeated decisions and avoid one-off design drift in UI surfaces.

## Workflow

1. Name the behavior and its owner before editing. Use
   `knowledge_base/package_ownership_model.md` as the package naming authority,
   then choose core, systems, adapters, math, IO, formats, resources, GUI
   Display, GUI Helpers, Runtime, Native Core, Project, Session, or native
   package based on responsibility.
2. Keep policies inward and frameworks outward. Core and systems should not import Qt or GUI packages.
3. Use ports/adapters when infrastructure varies: filesystem, renderer backend, game resource provider, external tools, MCP, or native runtime.
4. Use a service layer for workflow orchestration that coordinates repositories/providers/domain objects and exposes a small API to UI.
5. Use repositories/providers for storage and resource access instead of letting domain rules know file/runtime details.
6. Add abstractions only where they cut real coupling or duplication. Do not create broad `helpers.py` or `utils.py` piles.
7. Test at the cheapest useful layer first, then add visible checks for user-facing workflows.

## Native/Embedded Python Boundary

- Root `src/` is canonical for Python behavior unless a package explicitly owns
  package-local Python.
- Native projects are package boundaries, not permission to duplicate domain
  logic.
- Aggregate native owners such as `GhostRigger.Core.Rendering`,
  `GhostRigger.Core.IO`, `GhostRigger.Core.Math`, `GhostRigger.Core.Tools`, and
  `GhostRigger.Core.GUI.Display` should stay aligned with the ownership model.
- Embedded payload copies must be generated from canonical sources; divergence is
  an architecture smell unless documented.
- C++ migration needs a contract, an adapter path, parity validation, and a
  visible workflow check when behavior reaches users.

## Abstraction Signals

- Add an abstraction when multiple callers need the same policy, when tests need
  to replace infrastructure cleanly, or when external runtime boundaries vary.
- Do not add an abstraction solely to move code away from a file; name the
  domain concept first.
- If a package needs both UI and domain rules, split the domain rule first and
  let the UI consume it.

## GhostRigger Boundaries

- `src/core/<domain>/`: headless domain models, services, validation, scene/project state, resource rules, import/export decisions, workflow policies.
- `src/systems/<system_name>/`: focused feature systems and model pipelines above core primitives.
- `src/adapters/<technology_or_surface>/`: external runtimes, renderer backends, Qt-facing adapters, file/runtime APIs, integration glue.
- `src/gui/...`: widgets, windows, panels, signals, user gestures, theme/layout, and calls into services.
- `src/math/`: reusable transform, camera, pivot, projection, and coordinate-system math.
- `src/io`, `src/formats`, `src/resources`: file formats, resource discovery, serialization/deserialization.

Canonical package owners:

- IO owns read/write/import/export, serialization, MDL packing/extraction, FBX,
  archive access, resource-file access, and conversion.
- Automation owns IPC, MCP, scripting bridges, external APIs, background
  automation, command automation, and machine-facing events.
- Tools own user-facing product workflows and orchestrate lower layers.
- GUI Display owns visible presentation, layout, styling, widgets, panels,
  controls, icons, labels, menus, dialogs, notifications, and display-only
  state.
- GUI Helpers owns interactive helper objects such as gizmos, manipulators,
  transform handles, pickers, guides, dummies, snapping helpers, and drag
  handles.
- Scene owns scene state, objects, transforms, pivots, hierarchy, selection,
  placement, and KMAX scene contracts.
- Resources owns discovery, identity, addresses, references, lifetime, cache,
  and game/library lookup.
- Formats owns pure structures and format-level contracts; IO reads and writes
  them.
- Math owns reusable transforms, matrices, cameras, pivots, projections,
  coordinate conversion, normals, tangents, skinning math, and frame math.
- Rendering owns renderer-neutral contracts, render state, materials, texture
  upload policy, renderer resources, backend interfaces, and backends.
- Validation owns rules, checks, export gates, and comparison reports.
- Adapters own technology glue and must not own durable domain policy.
- Runtime/Native Core owns ABI, lifecycle, diagnostics, retained handles, host
  services, and C/C++ bridge surfaces.
- Project/Session owns project files, user sessions, workspace state, settings,
  dirty-state policy, and save/load workflow.

## Failure Patterns

- A window file gains parsing/export/math rules: move logic to owning core/system/adapter module.
- A core module imports Qt: dependency direction is inverted.
- Tests require patching many internals: abstraction may be missing at the boundary.
- A native package duplicates Python behavior without a contract: add or update focused source-contract tests.
- A workflow needs multiple panels to know private details: create a service/use-case API.
