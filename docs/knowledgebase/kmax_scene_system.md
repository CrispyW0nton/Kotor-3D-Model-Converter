# KMAX Scene System

KMAX is GhostRigger's general 3D scene/project format. It is distinct from KMAP
and GRSEQ:

- `.kmax` stores a general editable GhostRigger scene.
- `.kmap` stores level/map composition data.
- `.grseq` stores sequence and timeline data.

KMAX files are pretty JSON with `file_type: "GhostRiggerKMax"` and
`file_version: 1`. The first version stores lightweight scene state:

- scene identity, name, timestamps, game, units, settings, and metadata
- model object instances with stable IDs
- asset references for KOTOR/KOTOR2 resources or source paths
- per-object transform, visibility, lock, selection, group, and material override data
- lightweight cameras, lights, sequences, materials, textures, and KMAP references

KMAX does not embed large raw mesh, animation, or texture blobs by default. It
stores source references plus scene overrides so projects remain readable and
portable.

## Scene Manager

`KMaxSceneManager` owns the active `KMaxScene`. It creates new scenes, clears
objects, saves and loads `.kmax`, tracks dirty state, adds/removes/duplicates
model instances, manages selection, and serializes/deserializes scene data.

The main Qt shell uses the scene manager as the canonical active scene state.
The old loaded-model path is retained as an asset loading path, but imported
models become `SceneObjectInstance` records.

## Model Instances

Each imported model receives:

- a stable scene object ID
- a display name
- a `SceneResourceRef`
- an independent `Transform`
- visibility and lock flags
- material overrides and metadata

When a model is added to an existing scene, existing objects remain in place.
The first-pass placement mode uses world origin or an automatic X offset when
another object already occupies the origin.

## Viewport Bridge

The viewport always represents a scene. Empty scenes render the editor grid and
origin state. For multi-object rendering, the Qt viewport builds a lightweight
composite model from visible scene instances and feeds it through the existing
renderer. Scene object roots are tagged with KMAX object IDs so selection and
gizmo movement update the corresponding scene instance transform.

## Import Behavior

Double-clicking a model in an empty scene adds it immediately. If the scene
already contains objects, GhostRigger asks:

- Clear Scene and Load Model
- Add to Existing Scene
- Cancel

Clearing is never silent. Dirty scenes prompt to save before destructive actions.

## Dirty State

Scenes become dirty when objects are added, removed, renamed, duplicated,
transformed, hidden, locked, or when metadata changes. Saving or loading a KMAX
scene marks it clean.

## Extension Points

Future KMAP integration should use clean bridge methods such as:

- `import_kmap_into_scene(path)`
- `link_kmap_reference(path)`
- `export_scene_to_kmap(path)`

KMAX may reference KMAP projects, but the formats should stay separate.
