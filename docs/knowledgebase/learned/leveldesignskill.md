# Level Design Skill

Use this skill when authoring GhostRigger Map Studio and Module Studio areas:
laying out room geometry, composing KMAP/KMAX-backed rooms, building LYT
layouts, authoring VIS visibility, shaping WOK walkmeshes, placing gameplay
objects, and iterating toward an installable `.mod` game proof. The vocabulary
is architectural: spaces teach the player where to go and what is safe long
before any art is applied. Geometry and layout are the design.

## Book Grounding

- `Architectural_Approach_to_Level_Design_-_Christopher_Totten.pdf`: form-follows-
  function tied to gameplay metrics, scaffolding mechanisms, parti diagrams,
  scene readability and single/multi-scan spaces, grayboxing, the Nintendo Power
  pacing method, playtest discipline, modular design and schedules, figure-ground
  and form-void (Boolean add/subtract), arrivals and genius loci, the
  labyrinth/maze/rhizome spatial families, spatial size types, molecule design,
  hub-and-spoke, sandbox orientation problems, architectural weenies and
  landmarks, Kevin Lynch's legibility (landmarks/paths/nodes/edges/districts),
  camera views and sight lines, enemies-as-alternative-architecture, and tutorial
  skill gates plus reward types (glory/access/narrative/sustenance).
- `Level_Design_for_Games_-_Phil_Co.pdf`: preproduction (concept/thesis, asset
  lists, the level designer's role), production (sample the core gameplay,
  integrate visuals then audio, iterate), defining rules, perspective selection,
  theme/genre-driven design, and the level-design process and scheduling. (The
  source PDF is a scanned 2006 edition with poor OCR; treat these concepts as the
  organizing spine and confirm specifics against the architectural text.)
- `Procedural_Content_Generation_-_Paul_Martin_Eliasz.pdf` (UE5 PCG): for the
  *level-designer's* lens on procedural systems. Instanced rendering
  (ISM/HISM, hierarchical distance culling) is the reason a repeated kit can
  fill an area without exploding draw cost; the PCG-graph mental model
  (sample -> transform -> density filter -> spawn) is how to reason about
  scatter and mass placement; and performance budgeting (draw-call/LOD/
  distance-disable) is a constraint the layout must respect from the start.
  The deep Eliasz coverage lives in `learned/proceduralgenerationskill.md`;
  here we keep only the design-facing implications.
- Cross-reference `learned/gamedesignskill.md` for task loops, validation states,
  and playtest-style visible checks.

## Spatial Design Principles

1. **Form follows function.** The core gameplay loop dictates the metrics the
   space must serve. A combat arena, a dialogue hub, and a traversal corridor
   need different volumes. Decide the gameplay first, then the geometry.
2. **Design to the player's metrics.** Walk speed, jump distance, attack reach,
   and sight range are the units of level design. In Map Studio, room dimensions
   and door gaps should be validated against the same character scale KOTOR uses,
   not arbitrary grid sizes.
3. **Figure-ground.** Read a room as positive space (solid/massed) versus
   negative space (void). Healthy rooms alternate the two; a room that is all
   figure reads as clutter, all ground as empty. Use Map Studio's floor/wall/
   cube/cylinder primitives to build mass, then leave deliberate voids.
4. **Form-void (Boolean thinking).** Spaces evolve by adding and subtracting
   mass. This is exactly Map Studio's room-shaping operator set: `inset`,
   `bevel`, `cut`, `union`, and `transform` are Boolean form-void operations.
   Cut a doorway into a wall mass; union a ramp against a floor; inset to carve
   an alcove. Plan subtraction as deliberately as addition.
5. **Spatial size types.** Match volume to intent: narrow (compression,
   transition), intimate (small, safe, dialogue/reward), prospect (elevated,
   overview, vista). Use compression before release to make a vista land.
6. **Genius loci (spirit of place).** A memorable area has a distinct identity.
   Give each authored KMAP area one dominant idea (a lit chasm, a curved
   colonnade, a flooded vault) that the layout reinforces.

## Flow, Sightlines, and Pacing

1. **Molecule design.** Model the level as a graph: nodes are gameplay moments
   (combat, puzzle, reward, cutscene) and edges are circulation. Add Steiner
   points for optional shortcuts and secrets. In GhostRigger, gameplay placements
   (creature/door/waypoint/trigger/encounter) are the nodes; the WOK walkmesh and
   door links are the edges. If two nodes have no walkable edge, the layout is
   broken regardless of geometry.
2. **Spatial families.**
   - **Labyrinth (unicursal):** a single linear path. Best for scripted
     sequences and tutorials; low player agency.
   - **Maze (multicursal):** branching paths with dead ends. Good for exploration
     and search, but risks frustration if landmarks are weak.
   - **Rhizome:** fully interconnected; any node reachable from many. Suits hubs
     and supports fast-travel-style navigation.
   Most KOTOR modules are labyrinth-to-maze with a hub spine. Match the family to
   the module's purpose.
3. **Arrivals.** A reveal lands hardest after contrast: compress the player
   through a tight approach, then open into the destination. Use a deliberate
   procession (sequence of spaces) rather than dropping the player into the
   payoff. Door transitions in LYT are natural procession points.
4. **Sight lines and VIS.** What the player can see drives where they go. Author
   VIS visibility to expose the next landmark at the moment you want it seen, and
   to cull rooms that should be surprises. VIS is both a navigation tool and a
   performance gate; treat each room as a "scene" that must be readable from its
   intended point of entry.
5. **Nintendo Power pacing method.** (1) Identify the macro scope of the area.
   (2) Evenly distribute micro highlights (encounters, vistas, rewards) across
   it. (3) Design the circulation that connects them. Pacing is spacing: crowd
   highlights and the area feels chaotic; space them and it feels empty.

## Wayfinding and Landmarks

1. **Legibility (Kevin Lynch).** Players navigate via five elements: landmarks,
   paths, nodes, edges, and districts. Make at least the landmark and the path
   unambiguous in every area.
2. **Architectural weenies.** A tall, brightly lit, contrasting feature draws
   the player toward it (the Disney castle model). Place one dominant landmark
   per area and let sight lines from multiple rooms converge on it.
3. **Scene readability.** A room should be readable in a single scan (one clear
   purpose) or an intentional multi-scan (layered discovery). If a room's purpose
   is ambiguous, the geometry is failing. Lighting, scale contrast, and landmark
   placement carry the message before any text.
4. **Hub-and-spoke.** A central safe hub with spokes to challenge rooms is the
   natural KOTOR module pattern. Load spokes one at a time; the hub orients the
   player and resets them between encounters. Module Studio's module
   hydrate/save must preserve this hub-spoke topology.

## Modular Kit Construction

1. **Build from a kit.** Treat room primitives (floor/wall/cube/cylinder/arch/
   ramp/stairs) and shaped variants as a reusable kit, like construction toys.
   Define a grid/module size and snap everything to it so pieces compose.
2. **Schedules as style guides.** A schedule documents the canonical version of
   each piece (dimensions, materials, naming). Maintain a kit schedule so
   authored rooms stay consistent and variant explosion is controlled.
3. **Compose, then customize.** Assemble from kit pieces first; apply shaping
   ops (inset/bevel/cut/union) only where a specific room needs distinction.
   Mass-customize details, never the structural grid.

## Performance and Procedural Helpers in Authored Areas

1. **Instancing is why a kit scales.** Repeated room pieces (the same wall
   panel, pillar, arch) can fill a large module without crushing performance
   only if they render as instances, not unique geometry. Design the modular
   kit for reuse precisely because reuse is what instancing rewards. This
   matters directly for the Map Studio viewport; in-game KOTOR rendering is
   fixed, but a layout that demands thousands of unique draws will not package
   or play smoothly. Kit discipline (above) and instancing are the same idea.
2. **Think scatter as a PCG graph, then hand-tune.** Rocks, clutter, debris,
   and atmosphere props follow Eliasz's pipeline: sample a surface -> apply
   transform jitter -> filter by density/mask/slope -> spawn. Design the layout
   so scatter fills negative space without burying a room's single-scan read.
   Crowd/atmosphere (wandering ambient actors, moving light sources) is the
   same pattern at the gameplay layer — generated for ambience, never for
   authored meaning. See `learned/proceduralgenerationskill.md` for mechanics.
3. **Budget the area before you fill it.** Every authored module has a soft
   cap: room count (LYT), visibility-set size (VIS), walkable surface area
   (WOK), and placement count (GIT). Design within the budget. A spectacular
   vista that forces the renderer to draw half the rooms every frame, or a
   placement list that bloats the GIT past playability, fails the packaging
   and game-test gates no matter how well it reads.
4. **Procedural helpers serve authored intent.** PG accelerates the tedious
   and large-scale (heightfields, scatter, kit repetition); it must never
   place the narrative/balance objects (creatures, triggers, encounters,
   doors, waypoints) that the player reads as authored meaning. The level
   designer owns those nodes; PG fills the gaps between them.

## Blockout / Graybox Workflow

1. **Block in collider-scale geometry first.** Build the level from simple,
   collision-accurate primitives before any art. If the level plays badly as a
   graybox, art will not save it.
2. **Test circulation with the WOK.** The walkmesh is the truth of
   walkability. Author/validate WOK early so that every intended edge in the
   molecule diagram is actually traversable.
3. **Author to camera.** Decide the camera perspective (KOTOR is a fixed
   isometric-ish third-person view) and design room depth, ceiling height, and
   sight occlusion for that view, not for a free-fly editor camera.
4. **Iterate in Map Studio before packaging.** The Maya/ZBrush-inspired workspace
   exists for this: blockout, playtest-read, reshape, repeat. Do not commit to
   final geometry or placements until the graybox reads correctly.

## Encounter and Placement Design

1. **Place by purpose, not by decoration.** Each gameplay placement is a node in
   the molecule: creatures are challenges, triggers/encounters are scripted
   beats, doors are gates, waypoints are circulation anchors, sound/camera are
   atmosphere and direction, stores are reward hubs.
2. **Skill gates and rewards of access.** Block progress behind a mechanic the
   player has just learned (a locked door, a needed item, a switch). This is a
   reward of access. Prefer environmental skill gates over arbitrary locks where
   the fiction allows.
3. **Enemies as alternative architecture.** Enemies and triggers reshape a space:
   a horde shrinks the safe area, a patrol herds the player, a turret denies a
   flank. Design encounter placements as if they were walls that move.
4. **Scaffold difficulty.** Introduce a mechanic in a safe space, then ramp
   danger. Do not front-load every variant; reserve advanced combinations for
   later modules. A "lesson plan" per module prevents difficulty spikes.

## Lighting for Navigation

1. **Light draws the eye.** Brightness, color contrast, and moving light are the
   strongest wayfinding cues. Light the destination, the reward, and the
   landmark; leave hazards and secrets dimmer.
2. **Prospect and refuge.** Players seek overview (prospect) and safety (refuge).
   Light overlooks brightly and nest reward/safe rooms in calmer, lower light.
3. **Shade and shadow as information.** Shadows define mass and depth; use
   consistent shadow direction so geometry reads. Avoid flat uniform light that
   erases figure-ground.

## Playtest Iteration

1. **Watch real traversal, not intent.** Playtest whether the player goes where
   the design intends and understands each space without instruction.
2. **If they do not get it, it is not clear enough.** Do not blame the player; add
   a second redundant cue (light plus landmark plus geometry) before concluding
   the mechanic is the problem.
3. **Look for happy accidents.** Sometimes players find a better route or use than
   intended; capture and incorporate it.
4. **Do not interfere mid-test.** Let failure happen; it reveals where the layout
   punishes without teaching.
5. **Playtest for the current stage.** Test graybox for circulation and
   readability; test the packaged `.mod` for runtime behavior in the real game.

## GhostRigger Applications

- **Map Studio room authoring (M29-M31):** floor/wall/cube/cylinder/arch/ramp/
  stairs primitives mapped to figure-ground massing; `inset/bevel/cut/union/
  transform` shaping ops treated as Boolean form-void.
- **LYT layout composition:** room graph as molecule diagram; hub-and-spoke and
  spatial-family selection per module; door links as circulation edges.
- **VIS visibility authoring:** sight-line-driven scene readability and
  culling for both navigation and performance.
- **WOK walkmesh design:** walkable surfaces as the circulation truth; validate
  every molecule edge is traversable; sculpt edges to enable or deny routes.
- **Gameplay placement (creature/door/waypoint/trigger/encounter/sound/camera/
  store):** each placement as a molecule node; skill gates, reward placements,
  and enemies-as-architecture.
- **Maya/ZBrush-inspired workspace:** graybox/blockout-first iteration before
  committing to final geometry or placements.
- **Terrain builder (T2907):** heightfield sculpting and slope diagnostics serve
  prospect/refuge and sight-line design, not just decoration.
- **`grdev01` game proof (T3103) and golden package (T3105):** blockout, iterate,
  playtest-read, then package to installable `.mod` and prove in-game.
- **Module Studio (M28):** preserve hub-spoke topology and placed-object purpose
  when hydrating/editing/saving KOTOR modules.

## Validation

- **Walkability proof:** every intended circulation edge has a WOK-traversable
  path; no orphans in the molecule diagram.
- **Readability proof:** each room's purpose is clear from its intended camera
  entry point without explanatory text.
- **Landmark proof:** at least one weenie is visible from the area's main
  approach, and VIS exposes it at the designed moment.
- **Pacing proof:** highlights are evenly distributed; no difficulty spike
  front-loads mechanics the player has not been taught.
- **Runtime proof:** the authored area packages to `.mod`, loads in KOTOR, and
  plays as the graybox intended (see `grdev01` / T3105). Prefer real in-game
  testing over editor-only inspection.
