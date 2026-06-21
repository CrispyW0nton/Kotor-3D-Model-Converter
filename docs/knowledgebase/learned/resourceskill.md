# Resource And Asset Pipeline Skill

Use this skill for resource discovery, game-file references, textures, materials,
asset pipeline handoff, renderer residency, and debug tooling.

## Book Grounding

- `Game Engine Architecture`: tools and asset pipeline, file systems, resource manager, engine configuration, debug drawing, in-game menus, screenshots, and profiling.
- `3D Math Primer`: texture mapping, local lighting model, light sources, skeletal animation, and real-time graphics pipeline.
- `3dsmax2020_ref_guide`: viewport shading modes, edged faces, clipping, mesh statistics, texture display, and geometry problem analysis.
- Qt books: model/view for resource browsers, background work for loading, and visible UI feedback.

## Workflow

1. Identify whether the value is a source reference, loaded resource, decoded asset, renderer resource, or user-authored override.
2. Preserve source game data unless the user explicitly chooses export/write.
3. Keep resource discovery and serialization in `src/resources`, `src/io`, or `src/formats`; keep renderer residency in renderer/adapters packages.
4. Track lifecycle: discover -> resolve -> decode -> validate -> cache -> present -> release/invalidate.
5. For textures/materials, separate texture bytes, decoded image, sampler/material policy, UV mapping, lightmap handling, and backend upload.
6. For resource browsers and module tools, use model/view data and avoid blocking the UI during scanning or decode.
7. Add debug affordances that reveal actual asset state: IDs, resrefs, paths, dimensions/counts, material slots, cache hits, and backend residency.

## Asset Lifecycle Details

- Discovery finds candidate assets and metadata without heavy decode.
- Resolution maps logical addresses/resrefs to concrete source files or game
  resources.
- Decode parses bytes into structured data with version and format metadata.
- Validation checks required fields, dimensions, counts, references, and
  compatibility before runtime use.
- Cache stores decoded or uploaded state with an invalidation key.
- Presentation adapts resource data for UI/renderer without taking ownership of
  source truth.
- Release/invalidate clears CPU/GPU residency without losing source references.

## Debug Fields To Expose

- Source address/resref and game.
- File/path/archive origin when available.
- Decoded dimensions/counts/format/version.
- Material slot and texture/lightmap names.
- Cache key and dirty/reload state.
- Backend resource handle/residency state.
- Validation warnings and missing dependency list.

## GhostRigger Checks

- KMAP and KMAX files should stay versioned, human-readable, and reference heavy assets rather than storing blobs.
- Imported module renderer behavior should use `K2:001ebo1` / `001EBO1` as the primary visible fixture unless another module is named.
- Texture, material, lightmap, and MDL parsing changes require MCP-backed ground truth checks.
- UI resource workflow changes require real Debug app testing.

## Failure Patterns

- Asset appears stale: check cache key, invalidation path, source file timestamp/version, and renderer upload reuse.
- Texture loads but renders wrong: inspect TPC/TXI decode, UVs, material slot, sampler, lightmap policy, and backend binding.
- Resource browser freezes: move scanning/decoding off the UI thread.
- Export changes source data unexpectedly: preserve references and stage output separately.
