---
name: ghostrigger-map-authoring
description: >
  Work on GhostRigger's Map Studio and Module Studio: KMAP/KMAX area authoring,
  room geometry primitives (floor/wall/cube/cylinder/arch/ramp/stairs), LYT/VIS/WOK
  spatial layout, gameplay placement contracts (placeable/creature/door/waypoint/
  trigger/encounter/sound/camera/store), module hydration and editing, GFF-backed
  object forms, walkmesh editing, safe save transactions, package output, and
  game-test proof. Covers level design theory, grayboxing, modular design,
  procedural content generation, and the grdev01 game proof pipeline.
---

# GhostRigger Map & Module Authoring

Map Studio authors KMAP/KMAX-backed areas with room geometry, LYT/VIS/WOK data,
and gameplay placements. Module Studio hydrates, inspects, edits, validates, and
safely saves KOTOR modules. Both studios share resource discovery, validation,
and export infrastructure.

## When to Use

- Map Studio room/area authoring (T2901-T2907, T3001-T3006, T3101-T3105)
- Module Studio hydration/edit/save (T2801-T2806)
- KMAP/KMAX scene state management
- Room primitive operations (inset, bevel, cut/union, transforms)
- LYT room position layout and VIS room-to-room visibility
- WOK walkable surface editing and validation
- Gameplay placement (placeable, creature, door, waypoint, trigger, encounter)
- Module save transactions and GFF-backed object forms
- Package output and game-test proof (grdev01)

## Level Design Principles

### Form Follows Function (Verbs Drive Design)

Before placing geometry, name the gameplay verbs the area supports. KOTOR
modules are walked through, fought in, and explored — the level must serve
those verbs first. Room geometry, encounter placement, and path layout must
express the intended player experience before any visual dressing.

### Grayboxing First

Build the area with primitive shapes (floor, wall, cube, cylinder) before any
detailed geometry. Test sightlines, pacing, and flow with the graybox. Only
add detailed MDL rooms and placeables after the layout reads correctly.

### Modular Design

KOTOR modules are inherently modular: LYT defines room positions, each room has
its own MDL/MDX/WOK. Design rooms as reusable modules that can be rearranged.
The KMAP format should store room references plus editable overrides, not
heavy geometry blobs.

### Pathfinding Cues

Use architectural landmarks (Totten's "architectural weenies") and Kevin
Lynch's vocabulary (paths, edges, districts, nodes, landmarks) to guide player
navigation through the module without signposting.

## KOTOR Module Structure

| File | Type | Purpose |
|------|------|---------|
| ARE | GFF | Area data (ambient, skybox, camera) |
| GIT | GFF | Game instance data (creatures, placeables, doors, triggers, encounters) |
| IFO | GFF | Module info (name, entry, on-enter/exit scripts) |
| PTH | GFF | Pathfinding network |
| LYT | Text | Room layout positions (XYZ + room model names) |
| VIS | Text | Room-to-room visibility pairs |
| MDL/MDX | Binary | Room model and animation data |
| WOK | Binary | Walkmesh (walkable surfaces) |
| UTC/UTP/UTD/UTT/UTE/UTS/UTM | GFF | Object templates (creature/placeable/door/trigger/encounter/sound/store) |

## Room Primitive Operations

Map Studio's room primitives compile to room mesh/WOK data:
- **Floor/Wall/Cube/Cylinder**: base building blocks
- **Arch/Ramp/Stairs**: transition elements
- **Inset/Bevel**: shaping operations that persist through KMAP
- **Rectangular cut/union**: Boolean operations
- All operations must persist material, UV, normal/tangent, and WOK surface data

## Safe Module Save Rules

- Never overwrite source KOTOR data
- Use backups, changed-resource manifest, and reference-safety report
- Save uses `ExportJob` transaction: stage → preflight → verify → promote
- No partial output on failure
- Preserve unknown metadata for forward compatibility

## Package Output and Game Proof

1. Build authored module: ARE/GIT/IFO/PTH/LYT/VIS + room MDL/MDX/WOK
2. Run readiness checks (resources, references, validation)
3. Package as `.mod` with manifest and smoke-test manifest
4. Install-prep: choose output/install target
5. Game proof: launch KOTOR, warp to module, record screenshot/video evidence
6. Proof marks: load/spawn/placeable/walkability accepted

## Deep Reference

- `docs/knowledgebase/learned/leveldesignskill.md` — spatial typology, workflow,
  grayboxing, Kevin Lynch vocabulary, modular design, GhostRigger specifics
- `docs/knowledgebase/learned/proceduralgenerationskill.md` — ISM/HISM
  instancing, PCG graph systems, spline-driven generation, crowd spawning
- `docs/knowledgebase/learned/mapstudioskill.md` — Maya/ZBrush-inspired
  workspace rules, KOTR-specific map construction
- `docs/knowledgebase/learned/gamedesignskill.md` — mechanics, feedback,
  difficulty, narrative/task flow
