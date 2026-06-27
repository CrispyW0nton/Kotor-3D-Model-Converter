# Procedural Generation Skill

Use this skill when adding procedural helpers to GhostRigger Map Studio: terrain
heightfield generation/sculpting, scatter and kit-assembly presets, slope and
density diagnostics, and generated room MDL/MDX + WOK. Procedural generation (PG)
in GhostRigger is a **helper for hand-authored KOTOR modules, not a replacement**.
Modules, rooms, and gameplay are authored by a human; PG accelerates the tedious,
repetitive, or large-scale parts (heightfields, scatter, kit repetition) and must
always sit under the owning `src/core/` or `src/systems/` layer — never in
window/viewport mixins (see `AGENTS.md`).

## Book Grounding

- `Procedural_Content_Generation_-_Paul_Martin_Eliasz.pdf` (Unreal Engine 5 PCG):
  the definition of PG (algorithm-generated data vs manual crafting; human assets
  + algorithm + RNG), when PG helps vs hurts, instanced rendering (ISM/HISM,
  hierarchical culling, distance-based LOD), the PCG graph pipeline
  (input -> sampler -> transform -> density remap/filter -> spawner), sampler
  types (Surface, Volume, Create Points Grid), texture-driven generation
  (Get/Sample Texture Data for heightmaps/masks/gradients), spline samplers
  (on-spline, on-interior), determinism via seeds and random-integer selection,
  terrain/biome placement driven by slope/height/biome texture projection, and
  optimization (virtualized geometry, World Position Offset distance disable,
  distance-field lighting, texture MIP/LOD/max-size, CPU profiling/draw calls,
  scalability settings, modularity/reusability, PCG Stamp baking to avoid
  regeneration, per-node debug visualization of points before spawning).
- Cross-reference `learned/leveldesignskill.md` (molecule diagrams, figure-ground,
  modular kits) and `learned/renderingshaderskill.md` (noise shader parameters).

## What Procedural Generation Is

1. **Definition.** PG generates data by algorithm rather than by hand, combining
   human-designed assets with algorithms and computer-generated randomness. The
   output is still content the user owns and can edit.
2. **Manual vs procedural.** Manual crafting gives full authorial control and
   bespoke quality. PG gives broad variation, smaller authored payloads, and fast
   mass placement. The right answer is usually hybrid: a human authors the
   structure and rules; PG fills the repetitive detail.
3. **Where PG earns its place:** large or repetitive surfaces (terrain
   heightfields), scatter (rocks, clutter, foliage-like props), kit repetition
   (reusing room modules at variant transforms), and any case where hand-placing
   every instance costs more than it returns in authored meaning.
4. **Where PG hurts:** anything a player reads as authored meaning. A KOTOR
   module's combat layout, story triggers, and key landmarks must be
   hand-placed. Do not procedurally place creatures, triggers, encounters,
   doors, or waypoints that carry narrative or balance weight.

## Core Techniques (and where they fit GhostRigger)

1. **Noise (value/Perlin/simplex).** The foundation of heightfields and organic
   variation. Feed a seeded noise function over a grid to produce a heightfield
   for the terrain builder; layer octaves (fBm) for detail. Expose frequency,
   amplitude, lacunarity, persistence, and seed as inspectable parameters.
2. **Heightfields.** A 2D grid of height samples is the terrain builder's core
   data (T2907). Generate via noise, then let the user sculpt. Slope diagnostics
   derive from the heightfield gradient (where is it too steep to be walkable?).
3. **Cellular automata.** Good for cave-like or organic void/mass patterns. Run
   birth/survival rules over a grid until stable; useful for suggestive
   heightfield detail or scatter masks, not for structural room layout.
4. **L-systems and grammar-based generation.** Rule-based rewriting suits
   branching structures (paths, corridors, vegetation-like scatter). Keep these
   as optional helpers; KOTOR room topology is authored, not grammar-grown.
5. **Sampling and point distribution.** The workhorse of scatter. Mirror the PCG
   pipeline: sample a surface (terrain) or volume for candidate points, apply a
   transform (offset/rotation/scale jitter), filter by density/mask, then spawn.
   Surface sampling scatters on terrain; grid sampling gives structured
   placement; volume sampling fills 3D regions.
6. **Density remap and filtering.** Control spawn probability with a remap curve
   and cull candidates below a density threshold. This is how you get "more rocks
   on slopes, none on flat paths" — density driven by slope or mask texture.
7. **Texture-driven generation.** Sample a texture (heightmap, slope mask, biome
   mask, color gradient) to drive where and what spawns. A grayscale mask is the
   simplest deterministic controller.

## Parameterization, Determinism, and Seeds

1. **Make every generator a parameterized preset.** Terrain patch presets (T2907)
   should be fully described by a small set of parameters (seed, noise settings,
   height range, resolution, mask). The same parameters must reproduce the same
   output bit-for-bit.
2. **Seeds are the contract.** A seed makes generation deterministic and
   reproducible — essential for a packaging tool. Never use unseeded global RNG
   in a generator whose output is baked into a `.mod`; the build must be
   repeatable.
3. **Separate generation from authored edits.** Generate the base, then let the
   user sculpt/override. Once the user has edited, treat the result as authored
   data; do not silently regenerate over it. (Equivalent to the PCG Stamp concept:
   bake generation results so they stop recomputing.)
4. **Expose parameters for debugging.** Like noise shaders, expose seed,
   frequency, amplitude, density threshold, and domain transform so a bad result
   can be diagnosed by tweaking one knob, not rewriting the generator.

## Room Primitive and Geometry Generation

1. **Primitives are parameterized geometry.** floor/wall/cube/cylinder/arch/ramp/
   stairs are each a small parameterized generator (dimensions, segments,
   material). Procedural generation here means "given parameters, emit the
   MDL/MDX geometry," not "invent the layout."
2. **Generated geometry must round-trip.** Anything generated must be editable as
   if hand-authored: the output MDL/MDX and WOK are first-class authored assets
   once emitted.
3. **WOK is generated with the geometry.** Walkable surfaces must be derived from
   the same parameters as the visible mesh so floor and walkmesh agree. A
   generated room whose WOK does not match its floor is a bug.

## Architecture and Placement (per AGENTS.md)

1. **Procedural helpers live in `src/core/` or `src/systems/`.** Generation logic
   is an owned subsystem, not viewport behavior. Windows and viewport mixins may
   call generators and render results, but must not contain generation code.
2. **Generators are pure, testable functions.** A terrain/heightfield generator
   should be callable without a Qt window or GL context: parameters in,
   heightfield/geometry/WOK out. This makes them unit-testable and reusable by
   packaging and export paths.
3. **PG never moves behavior into C++ just because a native package exists.** If
   a generator is migrated to native, it must prove ownership, parity,
   validation, and visible-workflow behavior (same `AGENTS.md` rule as all native
   migration).
4. **Deterministic generation enables the golden package.** The `grdev01` golden
   package (T3105) must rebuild reproducibly; any PG contributing to it must be
   seeded and parameterized, not ad hoc.

## Optimization Lessons (applied to GhostRigger scale)

- **Instancing and culling.** Repeated kit pieces and scatter should be
  instanced and culled hierarchically; do not upload unique geometry per
  instance. KOTOR's own rendering is fixed, but the editor viewport benefits.
- **Distance-based cost.** Disable expensive effects (vertex animation,
  high-detail geometry) beyond a distance; mirror the WPO-distance idea in the
  viewport, not in game output.
- **Texture budgets.** Generated/scattered assets must respect texture size and
  MIP limits; a generator that emits 8K textures per instance will not package.
- **Profile draw calls and CPU cost.** Generation runs on CPU then submits to GPU;
  measure both. A preset that takes seconds to regenerate harms the
  Maya/ZBrush-style sculpting loop.
- **Debug-visualize before spawning.** Show candidate points/density (like PCG
  debug mode) so the user tunes distribution before committing to geometry.

## When to Use PG vs Hand-Authoring

| Need | Approach |
| --- | --- |
| Terrain heightfield base shape | PG (noise + seed), then hand-sculpt |
| Scatter (rocks, clutter, debris) | PG (surface sample + density/mask) |
| Repeated kit rooms at variants | PG assembly from authored kit |
| Combat creature placement | Hand-author (meaning + balance) |
| Triggers / encounters / doors | Hand-author (narrative + flow) |
| Landmarks and weenies | Hand-author (wayfinding) |
| Walkmesh topology | Derived from authored/generated geometry |

## Validation

- **Determinism proof:** same parameters + seed reproduce identical
  heightfield/geometry/WOK across runs.
- **Round-trip proof:** generated geometry is editable as authored data and
  survives a generate -> edit -> save -> reload cycle without loss.
- **WOK/geometry parity proof:** the walkmesh matches the generated floor for
  every generated room.
- **Placement rule proof:** no narrative/balance object (creature, trigger,
  encounter, door, waypoint) is procedurally placed.
- **Location proof:** generation code lives under `src/core/` or `src/systems/`,
  not in any window or viewport mixin.
- **Packaging proof:** a PG-assisted area packages to `.mod` and loads/runs in
  KOTOR identically to a fully hand-authored one.
