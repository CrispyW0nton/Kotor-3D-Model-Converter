# C Game-Engine Programming Skill

Use this skill for the *game-engine architecture* side of GhostRigger's native
runtime: game-loop structure, scene/entity/component composition, asset and
resource lifecycles, the rendering pipeline organization, and camera systems.
This is the structural companion to `cppnativeskill.md` (which covers C++
mechanics, RAII, and the ABI boundary). Where `cppnativeskill` answers "how do
I write correct C++ at the boundary," this skill answers "what subsystems does a
game runtime need, and how should GhostRigger's native host be organized?"

## Book Grounding

- `Practical_C_Game_Programming_-_Zhenyu_George_Li.pdf`: the "Knight" 2D/3D
  engine reference implementation. Core lessons: the engine-as-framework split
  (kernel + reusable subsystems), the fixed/variable game loop with
  deterministic update, the `Scene` / `SceneObject` / `Component` composition
  model, the `Entity` class as a thin identity + transform handle, Big-O
  awareness for per-frame work, 2D rendering pipeline (sprite batching, blend
  modes, N-patch, parallax, isometric layering), and camera systems (orthographic
  vs perspective, view/projection composition, follow + deadzone).
- GhostRigger-native docs: `AGENTS.md`, `native/README.md`,
  `knowledge_base/cpp_integration_phases.md`,
  `knowledge_base/native_migration_plan.md`, and the package ownership model.

## The Engine/Framework Split

A game engine has two halves:

1. **Kernel / runtime** — the host that owns process lifecycle, the main loop,
   input, windowing, and the bridge to scripting (in GhostRigger, the embedded
   CPython host). This must be small, stable, and rarely changed.
2. **Reusable subsystems** — scene, rendering, resources, input, audio. These
   are the things a game *uses*, owned as focused modules.

In GhostRigger the split maps cleanly:

- **Kernel** = `GhostRigger.Native.Core.Host` (the `.exe` + `main.cpp` that
  boots CPython) and `GhostRigger.Runtime.Core` / `Runtime.Core.Host` (the C
  ABI, lifecycle, retained handles, diagnostics that Python consumes).
- **Subsystems** = `GhostRigger.Core.Rendering` (renderer-neutral contracts +
  backend implementations), `GhostRigger.Core.Scene` (scene state, hierarchy,
  selection), `GhostRigger.Core.Resources` (discovery, cache, residency),
  `GhostRigger.Core.Math` (transforms, cameras, projection).

The critical rule from the book: **the kernel stays thin; behavior lives in
subsystems.** Do not grow the host executable with domain logic. AGENTS.md
states this exactly: "Do not move real behavior into C++ merely because a native
package exists." Native packages that are boundary-only or diagnostic-only are
*kernel scaffolding*, not finished subsystems, and should be merged unless they
earn a real runtime boundary (see `couplingskill.md`).

## The Game Loop

A game loop is: read input → update simulation (fixed timestep) → render
(variable timestep) → present → wait. Knight's discipline that transfers
directly to a tool like GhostRigger:

- **Fixed update, variable render.** Simulation/animation logic steps in fixed
  deltas so it is deterministic and replayable. Rendering runs as fast as the
  display allows. GhostRigger's animation playback and pose evaluation should be
  fixed-step; the Qt viewport paint can be variable.
- **Accumulator pattern for stability.** When wall-clock time outruns a fixed
  step, accumulate the debt and run extra fixed steps (capped) rather than
  letting the simulation fall behind or lurch.
- **No heavy work on the loop thread.** Imports, scans, validations, and exports
  must run off the main/loop thread. In GhostRigger this is the planned
  cancellable job/progress bridge (T2308) and `QThread`/`pyqtSignal` pattern
  (see `advancedpythonskill.md`).
- **Big-O awareness per frame.** Per-frame work that touches every object must be
  linear or better; anything quadratic (n² visibility, n² picking) must be
  culled by spatial acceleration or run only on selection change, not every
  paint.

### GhostRigger tie-in
The Qt viewport already separates the software frame renderer
(`src/gui/rendering/frame_core.renderer`) from navigation and display controls.
Treat animation playback as a fixed-step update feeding that renderer; never tie
frame evaluation to paint cadence.

## Scene / SceneObject / Component Composition

Knight models the world as:

- **Scene** — the root container owning objects, camera, and update order.
- **SceneObject** — a node with identity, a transform (local + world), and a list
  of Components.
- **Component** — a focused behavior attached to an object (renderable, light,
  camera, script). Components read/write the object's transform but do not own
  siblings.

This is the composition-over-inheritance pattern and it maps almost 1:1 to
GhostRigger's scene model:

- `KMaxSceneManager` owns the active KMAX scene.
- `SceneObjectInstance` has `transform` and `pivot` (AGENTS.md: "Pivot tools
  must integrate with `SceneObjectInstance.transform` and
  `SceneObjectInstance.pivot`").
- KOTOR MDL nodes are the model-side equivalent: a node hierarchy where mesh,
  skin, light, emitter, and reference children are component-like attachments.

### Composition rules that carry over
- **Identity lives on the object, behavior on the component.** A transform, a
  stable ID, and parent linkage belong to the object. Everything else
  (renderable mesh, light parameters, skin weights) is a component.
- **Transforms compose down the hierarchy.** World = parent-world × local. Pivot
  edits must keep visible geometry stable (AGENTS.md) — this is exactly the
  component/transform separation: the pivot moves the object's origin, not its
  mesh vertices.
- **A component never reaches across to another object's internals.** If two
  objects must cooperate, route through the scene/controller, not a direct
  pointer. This keeps the dependency graph acyclic and is the same discipline as
  the layering rules in `couplingskill.md`.
- **Stable IDs for serialization.** Scene contracts (KMAX/KMAP) depend on stable
  object/subobject IDs; preserve them across edits and round-trips.

## Entity as Identity + Handle

Knight's `Entity` class is deliberately thin: an ID and a handle into the scene
table. The lesson: **do not put behavior on the entity.** Fat entity classes
that accumulate methods are an anti-pattern that breaks the composition model and
makes serialization harder. GhostRigger's `SceneObjectInstance` should stay a
data + transform carrier; behavior belongs in controllers, tools, and systems.

The runtime ABI in `GhostRigger.Runtime.Core` follows the same principle with
"retained handles" and "descriptors": C++ hands Python stable, opaque handles
plus plain descriptor structs, not rich objects. Keep it that way (see
`cppnativeskill.md` ABI checklist).

## Resource Lifecycle

A game engine's resource system has explicit phases. The book's pipeline is the
same one AGENTS.md mandates for GhostRigger:

1. **Discover** — find the resource by address (KOTOR uses resref + restype,
   not filesystem path alone; see `ResourceAddress` in
   `docs/architecture/ghostrigger_project_model.md`).
2. **Resolve** — pick the correct layer/provenance (base, override, project,
   generated, staged) and locate the bytes.
3. **Decode** — turn bytes into a usable form (TGA/TPC → RGBA, MDL/MDX → node
   tree, WOK → walkmesh).
4. **Upload / cache** — create the runtime resource (texture in GPU memory,
   compiled mesh) and cache it keyed by a stable address.
5. **Residency** — keep hot resources resident; evict cold ones under budget.
6. **Invalidate / release** — discard on edit, theme change, or shutdown.

GhostRigger rule (AGENTS.md): "Separate source references, loaded resources,
decoded assets, renderer resources, and user-authored overrides." Do not collapse
these phases — a resource address, its decoded image, its GPU upload, and the
user's override are four different things with four different lifetimes. Caching
on the wrong one causes stale textures and transform corruption.

## Rendering Pipeline Organization

Knight's 2D pipeline (batch sprites by texture/blend → sort by layer/depth →
draw) generalizes to the principles GhostRigger's renderer-neutral contracts
must follow:

- **Batch by state.** Group draws that share texture, material, and blend to
  minimize state changes. Backend implementations (D3D12 / ModernGL / PyGFX /
  Null) live in adapters and must implement a contract owned upstream — this is
  the Bridge pattern (see `pythonpackagingskill.md`).
- **Sort for correctness, then for performance.** Transparent/opaque ordering
  first; then front-to-back for early-z. Never let a backend reorder draws in a
  way that changes the visual result.
- **Camera drives view + projection.** The ArcBall camera
  (`src/gui/camera/arcball_camera`) is view; projection is separate. They
  compose into the view-projection matrix; do not bake one into the other.
- **Separate CPU asset truth from GPU resource state.** AGENTS.md is explicit:
  texture bytes, decoded image, sampler/material policy, UV mapping, lightmap
  handling, and backend upload are distinct concerns owned by distinct layers.

## Camera Systems

From the book:

- **Orthographic vs perspective.** Use ortho for level/layout work (Map Studio
  room authoring) where parallel lines must stay parallel; perspective for
  character/animation preview.
- **Follow + deadzone.** A follow camera tracks a target but ignores small
  movement inside a deadzone to avoid jitter — useful for object-focused
  viewport modes.
- **The offset lives at the root.** Coordinate-space conversion (Blender
  `x, z, -y` → KOTOR object space) belongs at import/root, not baked into every
  camera (see `technicalanimationskill.md` and `blenderpipelineskill.md`).
- **Always name the space.** object, world, parent, camera, clip, screen,
  UI/gizmo — a transform is meaningless without its space label
  (AGENTS.md Math Rules).

## GhostRigger Applications

- **Native host organization:** keep `Native.Core.Host` and `Runtime.Core` thin
  (kernel). Push real behavior into the correct `Core.*` subsystem owner, and
  only after proving a real runtime boundary (AGENTS.md native migration rules).
- **Scene work:** model edits as component-level operations on
  `SceneObjectInstance`; keep the entity thin; preserve stable IDs for
  serialization round-trips.
- **Resource bugs:** when a texture/material looks stale or a transform looks
  corrupted, walk the lifecycle phases — the bug is almost always a cache keyed
  on the wrong phase or a missing invalidation on edit.
- **Renderer parity:** when a backend looks wrong, compare against another
  backend through the same neutral contract; the divergence is usually a sorting
  or state-batch order difference, not a math error.
- **Performance:** per-frame work must be O(n) or better; move anything heavier
  off the loop/animation thread.

## Anti-Patterns to Reject

- **Fat entity / god-object scene node** that accumulates render, light, skin,
  and script methods. Break into components.
- **Behavior in the host executable.** The kernel grows; the system rots.
- **Baking coordinate conversion into the camera or per-mesh math.** Move it to
  the import root.
- **Caching on decoded bytes when the user override changed.** Invalidate by
  address + layer, not by byte content.
- **Quadratic per-frame checks** (visibility/picking across all objects every
  paint). Add spatial acceleration or run on selection change.
- **Letting the simulation step vary with render rate.** Animation becomes
  non-deterministic and replays won't match.

## Cross-References

- `learned/cppnativeskill.md` — C++ mechanics, RAII, the ABI boundary this
  runtime is built from.
- `learned/animationruntimeskill.md` — fixed-step pose evaluation, keyframes,
  runtime blending.
- `learned/renderingshaderskill.md` — the GPU pipeline this organizes.
- `learned/resourceskill.md` — the resource lifecycle in detail.
- `learned/couplingskill.md` — why subsystems must be cohesive, and why
  boundary-only native packages should merge.
- `learned/pythonpackagingskill.md` — Bridge/Adapter/Facade for the renderer
  backends.
- `docs/architecture/ghostrigger_project_model.md` — `ResourceAddress`
  provenance model.
