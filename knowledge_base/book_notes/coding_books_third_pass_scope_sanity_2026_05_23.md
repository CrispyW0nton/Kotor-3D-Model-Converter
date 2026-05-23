# Coding Books Third-Pass Scope Sanity

Date: 2026-05-23

Purpose: revisit the six programming/UI/architecture books with one question:
what should GhostRigger be, what should it not be, and what architecture keeps
the tool useful for KOTOR modders instead of impressive-but-scattered?

Books re-scanned:

- Lee Zhi Eng, *Qt 6 C++ GUI Programming Cookbook*, 3rd ed.
- Mark Summerfield, *Rapid GUI Programming with Python and Qt*
- Martin Fitzpatrick, *Create GUI Applications with Python and Qt6*
- Steve Schoger and Adam Wathan, *Refactoring UI*
- Harry Percival and Bob Gregory, *Architecture Patterns with Python*
- Robert C. Martin, *Clean Architecture*

## Scope Conclusion

GhostRigger should be a KOTOR/Odyssey creation suite, not a general-purpose DCC
application, not a full game-engine replacement, and not a clone of Holocron
Toolset or Blender.

North star:

```text
Help a KOTOR modder create, preview, validate, export, stage, and test
game-compatible KOTOR assets, animations, modules, and scenarios.
```

Everything belongs only if it supports one of four studios:

1. Character Studio.
2. Retarget Studio.
3. Module Studio.
4. Map/Scenario Studio.

## What The Third Pass Added

### The tool needs command/query boundaries

Architecture Patterns with Python and Clean Architecture both point to the same
shape: commands mutate, queries inspect. GhostRigger should make this explicit.

Examples:

- Query: list resources in module `tar_m09aa`.
- Command: create a staged module package.
- Query: show retarget readiness.
- Command: build preview.
- Command: export last approved preview.

This matters because modders need to know when the tool is only inspecting and
when it can change disk state.

### Use cases should be named like modder goals

Avoid vague internal actions such as "run pipeline" or "process data".

Use-case names should sound like:

- `load_kotor_module`
- `inspect_resource`
- `edit_gff_field`
- `place_module_object`
- `build_retarget_preview`
- `export_last_preview`
- `bind_imported_mesh_to_native_dag`
- `stage_patch_package`

These names keep the program anchored to actual user workflows.

### GhostRigger needs a "capability honesty" vocabulary

Refactoring UI's emphasis on clear state maps directly to modding safety.

Use these labels consistently:

- `implemented`: code path exists and is tested headlessly.
- `previewable`: can be visually inspected in GhostRigger.
- `export candidate`: writes staged/readback-verified outputs.
- `game-tested`: verified in KOTOR or a live-equivalent smoke path.
- `requires custom patch`: not vanilla-slot/runtime safe by itself.
- `experimental`: useful but not yet trusted for normal modder output.

Do not call a feature game-ready just because a unit test passes.

### Undo and transaction boundaries define product readiness

Module/Map/Scenario editing should not be broadly exposed until edits can be:

- undone/redone;
- validated with a target resource/object;
- staged through ExportJob;
- reloaded or verified after write.

The product can still expose read-only browsing earlier.

### UI should optimize for the next safe action

Empty states and status panels should answer:

- what is loaded?
- what is selected?
- what can I do next?
- what is missing?
- what will be written, and where?
- is this vanilla-safe or patch-required?

Dense professional tools should not explain themselves with marketing copy, but
they must expose state clearly.

## Scope Test For New Features

Before adding a feature, answer all questions:

1. Which studio owns this?
2. What KOTOR modder task does it complete?
3. What resource or project object is the target?
4. Is it query-only, preview-only, export-candidate, or game-tested?
5. Does it require ValidationBus?
6. Does it write files? If yes, does it use ExportJob?
7. Does it preserve exact KOTOR resource identity and Aurora node casing?
8. Can a user undo it if it edits authoring state?
9. Is it something Holocron, Blender, KotorBlender, MDLOps, or Unreal already
   does better? If yes, what GhostRigger-specific KOTOR value is added?
10. What remains incomplete after this slice?

If the answers are weak, park the feature.

## What GhostRigger Should Not Become

- A general Blender replacement.
- A generic Unreal retargeting product.
- A general game engine/editor unrelated to KOTOR.
- A patch installer that bypasses safe staging and manifests.
- A binary MDL writer that invents behavior without MCP/PyKotor/Ghidra truth.
- A UI playground where each panel manages its own private resource state.
- A collection of one-off fix scripts that never become named modes/tests.

## Third-Pass Roadmap Corrections

The next architecture work should stay boring and structural:

1. `GameResourceProvider`
2. provider-backed Qt models
3. ValidationBus issue panel
4. undo command foundation
5. shared job/progress service bridge

Only then should the suite expand major new product surfaces.

Product work should prefer:

1. retarget quality/game-tested confidence;
2. Character Studio native DAG export lock;
3. Module/Map read-only resource browsing and safe undoable edits;
4. KOTOR to Unreal only after the KOTOR resource/provider and retarget quality
   pieces are stable.

## Current Honest State

GhostRigger is already useful as a technical KOTOR asset/retargeting workbench.
It is not yet a complete modder suite.

Strongest area:

- Retarget Studio and MDL animation export gates.

Most important architecture gap:

- Shared resource/provider model and provider-backed UI models.

Most important product gap:

- Character Studio game-safe custom character export.

Most important modder-experience gap:

- One coherent project/resource/validation/undo/export surface across studios.
