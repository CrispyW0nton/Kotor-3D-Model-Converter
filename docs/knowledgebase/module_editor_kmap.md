# Module Editor, Level Editor, and KMAP

The standalone Module Editor is GhostRigger's first Level Editor surface. It is a top-level Qt window, not a dock-only panel, and works on GhostRigger-authored `.kmap` projects.

## Concepts

- A KOTOR module is original game data: LYT room layout, WOK walkmeshes, ARE/GIT/IFO resources, templates, textures, and related files.
- A KMAP project is GhostRigger's editable level/map format. It stores references to source assets plus transforms, visibility, walkmesh edits, blueprints, texture/material references, validation state, and export/build metadata.
- The Level Editor uses KMAP as the assembled scene format. One KMAP can reference multiple module or room instances.

## Format

KMAP is JSON, human-readable, versioned, and uses the `.kmap` extension. The root object uses:

- `file_type: "GhostRiggerKMap"`
- `file_version: 1`
- `project`, `units`, `modules`, `rooms`, `walkmeshes`, `blueprints`, `textures`, `materials`, `objects`, `lights`, `cameras`, `sequences`, `exports`, and `metadata`

KMAP files must not embed heavy raw mesh or texture data by default. Store source paths, resource resrefs, stable IDs, and editable overrides.

## Editing Workflow

The Module Editor can create/open/save KMAP projects, import module references, load LYT files into room instances, associate WOK files with rooms, edit room/module transforms, track blueprints, and run validation. The outliner, viewport-state table, and properties panel all read from the same `KMapProject` model.

The Assets tab mirrors rows from the main Game Library scan. Module/tile model rows import as KMAP room instances with their model resref, game, module code, and source metadata preserved. Creature, character, item, template, and other model rows import as blueprint entries so they can be placed in the level without embedding source mesh data. The main Game Library also exposes "Add to Level" / "Add to Level Editor" actions that open the standalone Level Editor and send the selected asset into the active KMAP scene.

## Export and Build

The builder generates a structured manifest first. Full KOTOR archive writing remains experimental unless an existing backend can safely write the target resource. FBX export uses `LevelExportBridge`: it writes a sidecar manifest and only attempts mesh export when a compatible assembled model is available.

## Validation

`KMapValidator` reports missing source modules, missing room models, missing LYT/WOK links, walkmesh-room mismatches, duplicate IDs, invalid transforms, missing textures/lightmaps, blueprint gaps, game mismatch risks, output path issues, and unsupported export states.

## Future Work

Future Level Editor passes should connect real multi-room mesh assembly to the viewport renderer, expand WOK face painting UX, integrate resource providers for module archive hydration, and promote experimental build operations only when they can avoid overwriting source KOTOR data.
