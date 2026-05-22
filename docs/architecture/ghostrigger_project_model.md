# GhostRigger Project Model

`GhostRiggerProject` is the suite-level session spine for Character Studio,
Retarget Studio, Module Studio, Map Studio, and scenario authoring. It stores
lightweight references to work, assets, validation snapshots, and export
candidates so each studio can share one project document instead of creating
isolated state islands.

## Resource Addresses

KOTOR resources are not identified by filesystem paths alone. The same resref
can exist in KEY/BIF archives, modules, Override, generated staging folders, or
project-local outputs. `ResourceAddress` captures that provenance with fields
such as:

- `scheme`: `game_resource`, `module_resource`, `override_resource`,
  `project_resource`, `local_file`, `generated_output`, `kmap_object`,
  `kmax_object`, `retarget_profile`, `preview_result`, or `export_candidate`;
- `game`: `k1`, `k2`, or `unknown`;
- `module_id`: for module-scoped resources such as `tar_m09aa`;
- `resref` and `restype`: KOTOR resource identity such as `gr_beklead.UTC`;
- `layer`: `base`, `override`, `project`, `generated`, or `staged`;
- `path`: local file reference when a path is the real source of truth;
- `object_id` and `fragment`: object/field references inside KMAP/KMAX/project
  data;
- `metadata`: small JSON metadata only.

The model intentionally keeps addresses stable and deterministic through
`stable_key()` so future validation, dependency graphs, and export jobs can
reference the same resource consistently.

## What Project JSON Must Not Store

Project JSON must not embed proprietary KOTOR asset bytes, MDL/MDX payloads,
textures, FBX data, or arbitrary Python objects. Store paths, resrefs, generated
output addresses, and validation summaries instead. `save_ghostrigger_project`
will fail if metadata contains non-JSON-serializable values such as raw bytes.

## Studio Migration Path

Character Studio can store imported mesh addresses, selected native KOTOR base
models, rig/build jobs, and verified MDL/MDX export candidates.

Retarget Studio can store source/target/profile addresses, preview/export
addresses, vanilla-slot vs custom-patch output naming, and whether the custom
runtime animation patch is required.

Module Studio can store hydrated module workspaces, edited resource addresses,
GFF save manifests, walkmesh work, and package candidates.

Map Studio can store KMAP/KMAX scene addresses, room/object references,
scenario packages, cutscene sequence references, and staged module/package
outputs.

This first slice does not migrate any UI yet. Existing studios can adopt the
project model gradually as their controllers become project-aware.
