# GhostRigger (Kotor-3D-Model-Converter) — Full Architecture and Codebase Audit + Fix Roadmap

> **Format note:** Markdown was chosen because this is a developer-facing technical architecture audit and implementation roadmap. It needs durable structure, code/file references, tables, checklists, and easy handoff into GitHub issues, design docs, and AI developer workflows.

---

## Table of Contents

1. [Audit Metadata](#audit-metadata)
2. [Methodology](#methodology)
3. [Repository Shape and Codebase Statistics](#repository-shape-and-codebase-statistics)
4. [What Was Directly Inspected in Source](#what-was-directly-inspected-in-source)
5. [High-Level Architecture Audit](#high-level-architecture-audit)
6. [Rendering Architecture Audit](#rendering-architecture-audit)
7. [Texture Wrapping and Module Tiling Audit](#texture-wrapping-and-module-tiling-audit)
8. [Depth Rendering / See-Through Face Audit](#depth-rendering--see-through-face-audit)
9. [Performance and Memory Audit](#performance-and-memory-audit)
10. [Import/Export Pipeline Audit](#importexport-pipeline-audit)
11. [Character Builder Audit](#character-builder-audit)
12. [Module Loading and Module Editor Audit](#module-loading-and-module-editor-audit)
13. [Dependency and Environment Audit](#dependency-and-environment-audit)
14. [Testing Audit](#testing-audit)
15. [Problem-by-Problem Root Cause Matrix](#problem-by-problem-root-cause-matrix)
16. [Code-Level Roadmap by File](#code-level-roadmap-by-file)
17. [External Reference Stack and What Each Project Should Teach GhostRigger](#external-reference-stack-and-what-each-project-should-teach-ghostrigger)
18. [Applied Guidance from the 3 Attached Books](#applied-guidance-from-the-3-attached-books)
19. [Most Important Conclusions](#most-important-conclusions)
20. [Appendix: Direct Evidence Excerpts](#appendix-direct-evidence-excerpts)

---

## Audit Metadata

| Item | Value |
|---|---|
| Repository | https://github.com/CrispyW0nton/Kotor-3D-Model-Converter |
| Commit audited | `2739d2729236714af6e07ff779c6ac5c2ba82fb6` |
| Commit message | `feat(gltf,particle,walkmesh): Phase 6.1 + Phase 8 (GLTF) + Phase 9.3/9.4 — CPU Particle Emitter, GLTF Importer, Walkmesh Write + Toggle` |
| Audit date | 2026-04-13 |

---

## Methodology

This audit combined five layers of review:

1. **Direct repository scan**
   - cloned the repository
   - inspected tree shape, file distribution, code concentration, and commit metadata

2. **Code-level inspection of the source tree**
   - inspected high-risk files directly
   - searched for rendering, FBX, texture, depth, UV, cache, and dependency behaviors
   - reviewed file-local docstrings and comments as part of implementation intent

3. **Architecture-level review**
   - mapped product surfaces to code ownership
   - identified where orchestration is centralized
   - distinguished true subsystems from large GUI orchestration modules

4. **Comparison against external reference projects and prior KOTOR workflow research**
   - GhostRigger was compared conceptually against PyKotor, KotorBlender, KotOR.js, reone, xoreos, ufbx, FBX2glTF, and openfbx
   - prior research on KOTOR head/body assembly, facial rigs, supermodels, lip sync, module loading, and exporter workflows was folded in

5. **Application of the 3 attached book findings**
   - **rendering/OpenGL book:** GPU architecture, depth buffering, alpha handling, camera/projection, batching
   - **skinning/animation book:** bind pose, offset matrices, LBS correctness, retargeting, axis mapping
   - **engine/tools architecture book:** modularity, single source of truth, asset conditioning, editor ergonomics, maintainability

This document therefore reflects both **what the source currently does** and **what it should do next**.

---

## Repository Shape and Codebase Statistics

### Source tree summary

- `src/autorig`
  - `accurig.py`
  - `auto_rigger.py`
  - `cloth_rig.py`
  - `grig.py`
  - `retarget_engine.py`

- `src/converters`
  - `mesh_converter.py`
  - `normal_map.py`

- `src/core`
  - `animation_engine.py`
  - `animation_library.py`
  - `character_builder.py`
  - `creature_appearance.py`
  - `diagnostics.py`
  - `game_library_ext.py`
  - `gltf_importer.py`
  - `gpu_skinning.py`
  - `kotor_install.py`
  - `kotor_loader.py`
  - `mdl_parser.py`
  - `mdl_porter.py`
  - `mdl_writer.py`
  - `model_data.py`
  - `module_format.py`
  - `module_loader.py`
  - `override_layer.py`
  - `particle_emitter.py`
  - `pykotor_bridge.py`
  - `resource_manager.py`
  - `scene_manager.py`
  - `template_builder.py`
  - `twoda.py`
  - `validation_service.py`
  - `walkmesh_renderer.py`

- `src/gui`
  - `accel.py`
  - `blueprint_editor.py`
  - `character_builder_window.py`
  - `gpu_renderer.py`
  - `icon_manager.py`
  - `main_window.py`
  - `modular_panel.py`
  - `tex_atlas.py`
  - `tpc_render_utils.py`
  - `viewport.py`

- integration layers
  - `src/ipc`
  - `src/kotormcp`

### Codebase statistics

- **81 Python files**
- **75,360 Python LOC**

### Largest files

| File | Lines | Functions | Classes |
|---|---:|---:|---:|
| `src/gui/main_window.py` | 11,976 | 401 | 16 |
| `src/gui/viewport.py` | 9,323 | 215 | 6 |
| `src/converters/mesh_converter.py` | 3,535 | 61 | 7 |
| `src/gui/character_builder_window.py` | 3,532 | 161 | 12 |
| `src/gui/gpu_renderer.py` | 3,147 | 49 | 8 |
| `src/core/creature_appearance.py` | 2,161 | — | — |
| `src/core/animation_engine.py` | 1,966 | — | — |

### Internal coupling scan

**Most imported internal modules**
- `core.model_data` — 53
- `core.kotor_loader` — 25
- `converters.mesh_converter` — 19
- `core.mdl_parser` — 12
- `kotormcp.state` — 11
- `core.creature_appearance` — 10
- `core.animation_library` — 9

**Highest outgoing internal imports**
- `gui.main_window` — 92
- `gui.character_builder_window` — 31
- `core.character_builder` — 16
- `gui.viewport` — 13

This is a strong signal that the system already has reusable subsystems, but the **GUI layer remains the main integration gravity well**.

---

## What Was Directly Inspected in Source

The following files were directly inspected because they are central to the user-reported problems:

### Core architectural files
- `README.md`
  - establishes claimed architecture, capabilities, and current product framing
- `requirements.txt`
  - shows actual dependency expectations
- `pyproject.toml`
  - shows packaging/dependency boundaries

### Rendering and texture correctness
- `src/gui/viewport.py`
  - current production viewport behavior
  - CPU renderer, UV sentinel logic, depth workarounds, texture handling, threading
- `src/gui/gpu_renderer.py`
  - alternative GPU renderer path
  - depth buffer, TXI handling, texture wrapping, caches
- `src/gui/accel.py`
  - NumPy/Numba acceleration layer for the CPU pipeline
- `src/core/model_data.py`
  - rendering data structures, TXI fields, node semantics
- `src/core/resource_manager.py`
  - texture/raw asset loading and memory behavior

### Import/export and Unreal-facing issues
- `src/converters/mesh_converter.py`
  - OBJ import/export
  - FBX import/export
  - handwritten ASCII FBX path
  - texture conversion
- `src/core/kotor_loader.py`
  - parsing contract and hard dependency on PyKotor
- `src/gui/main_window.py`
  - export routing and UI exposure
- `src/gui/character_builder_window.py`
  - export routing in the new builder

### Character builder and validation
- `src/core/character_builder.py`
  - templates, bone groups, backend logic
- `src/core/validation_service.py`
  - pre-export validation rules
- `src/gui/character_builder_window.py`
  - standalone builder shell and current workflow framing

### Module stack
- `src/core/module_loader.py`
  - high-level module loading bridge
- `src/core/scene_manager.py`
  - scene assembly and room/object graph

### Tests relevant to the reported problems
- `tests/test_v99_full_character_export.py`
- `tests/test_v71_phase1_rendering_fixes.py`
- `tests/test_v95_resource_manager.py`

---

## High-Level Architecture Audit

### Product surfaces

The system currently exposes **five major product surfaces**:

1. **Main window / model viewer**
2. **Renderer / viewport**
3. **Character builder**
4. **Module editor**
5. **Import/export pipeline**

This matches the stated product ambition. The issue is not lack of subsystems; it is **where the subsystems are orchestrated and how consistently they are used**.

### Dominant orchestration modules

Two files dominate the architecture:

- `src/gui/main_window.py`
- `src/gui/viewport.py`

They are oversized, highly connected, and act as **UI-centric orchestration hubs**. This is visible in both raw size and import coupling.

#### Why this matters
- changes to product behavior are likely to cross UI and engine boundaries
- regression risk is high
- code navigation is expensive
- subsystem ownership is blurred
- architectural improvements exist in parallel files but are not always wired into production behavior

### Partial subsystem separation exists

The repository is not flat or naive. It already contains:
- `core/*` backend layers
- `autorig/*` rigging subsystems
- `converters/*` interchange pipeline
- `gui/*` UI surfaces
- `module_loader.py` and `scene_manager.py` as relatively clean non-GUI domain layers
- `validation_service.py` as a policy layer

So the project has **real subsystem intent**.

### But orchestration remains concentrated in giant GUI modules

The architectural problem is not absence of modules. It is that the major user workflows still flow through giant UI files which:
- own too much state
- coordinate too many concerns
- duplicate some workflow surfaces
- make it difficult to enforce one clean path for rendering/export/builder behavior

### Character builder architecture status

`src/gui/character_builder_window.py` already implements a standalone `tk.Toplevel` workflow shell with:
- **Assembly**
- **Rig**
- **Face**
- **Preview**
- **Export**

That is the right direction.

`src/core/character_builder.py` acts as a backend for:
- K1/K2 templates
- template registry
- bone groups
- selection logic

`src/core/validation_service.py` already exists and is a strong architectural foundation for making exports safer and less ambiguous.

### Architectural conclusion

GhostRigger is not missing core ideas. It is missing **architectural consolidation**:
- one primary viewport architecture
- one primary character workflow
- one primary validated export path
- less orchestration in giant GUI files

---

## Rendering Architecture Audit

### Claimed architecture vs actual production architecture

The README still advertises a **CPU-based PIL renderer with two-pass depth sorting**.

That is not just documentation drift. It reflects the fact that the **main viewport architecture is still fundamentally framed around the CPU renderer**, even though a GPU renderer exists elsewhere.

### `viewport.py` production renderer

`src/gui/viewport.py` defines `FrameRenderer` with these caps:

- `MAX_TRIS = 80_000`
- `MAX_TRIS_TEXTURED = 5_000`
- `MAX_TRIS_TEXTURED_ACCEL = 10_000`
- `MAX_TRIS_TEXTURED_STILL = 50_000`

It renders PIL RGBA frames in a **background thread**.

This reveals the actual architectural center of gravity:
- CPU rendering
- threading around CPU image generation
- quality/performance caps
- many special-case workarounds

### Painter’s algorithm workarounds are built into production behavior

`viewport.py` contains:
- `_UV_SENTINEL = 100.0`
- inner-geometry substring promotion for eyes/teeth/gum/tongue
- face mesh substring handling
- explicit commentary acknowledging that head models contain inner geometry
- explicit commentary acknowledging that painter’s algorithm creates problems

This is direct evidence that the CPU renderer is not merely simple; it is **carrying a large body of compensating logic for problems a proper depth-buffered renderer should solve structurally**.

### `gpu_renderer.py` is materially better architected

`src/gui/gpu_renderer.py` exists as a separate ModernGL/EGL renderer and already implements or documents:

- depth buffer
- alpha-test
- two-pass rendering
- `GL_REPEAT` texture wrapping
- lightmap support
- envmap support
- TXI support
- persistent world-transform cache
- mesh cache
- texture cache
- MSAA
- culling
- camera/projection matrices
- GPU-first draw model

This is a much more professional rendering architecture.

### But `viewport.py` does not meaningfully integrate `GpuRenderer`

The key architectural issue:

- `gpu_renderer.py` exists
- `viewport.py` knows about acceleration and CPU optimizations
- **but the main viewport still drives `FrameRenderer`, not a unified GPU-first rendering path**

This split must be stated plainly:

> **A GPU renderer exists in the codebase, but the main viewport architecture is still effectively centered on the CPU/PIL `FrameRenderer`.**

### Consequence

The codebase currently pays for both:
- a large CPU renderer with extensive correctness workarounds
- a separate GPU renderer with better primitives

without fully reaping the benefit of the GPU architecture in the production viewport.

---

## Texture Wrapping and Module Tiling Audit

### Source evidence

`viewport.py` uses **UV sentinel filtering** and skips triangles whose UV components exceed a threshold.

The comments state:
- the threshold was raised from `20.0` to `100.0`
- this was done to avoid filtering legitimate tiled meshes

`gpu_renderer.py` contains explicit fixes for tiled UVs and states that module/area/tile models are exempted with sentinel values around `1e6`.

`accel.py` uses **frac()-style wrap** for `GL_REPEAT`-like behavior in the NumPy/Numba rasterizer.

`model_data.py` already has:
- `txi_clamp_s`
- `txi_clamp_t`

`resource_manager.py` and renderer-side code already parse:
- `alpha_test`
- some TXI metadata

### What this means architecturally

The codebase **knows** about the texture wrapping problem and has implemented fixes in multiple places.

But the policy is **inconsistent and fragmented** across:

- `src/gui/viewport.py`
- `src/gui/accel.py`
- `src/gui/gpu_renderer.py`
- `src/core/model_data.py`
- TXI parsing/application behavior

### Why the current approach is brittle

UV validity is currently mixed with heuristics like:
- magnitude-based sentinels
- model classification exemptions
- seam-handling assumptions

This is fragile because **large UV values are often legitimate** in tiled/module geometry.

### Audit conclusion

The codebase has scattered tactical fixes but not one authoritative UV/wrap policy.

#### Required architectural principle
UV validity should **not** be based on magnitude heuristics.

It should be based on:
- actual seam/proxy metadata
- per-face UV ownership
- explicit wrap mode semantics
- TXI-driven sampler state
- mesh data provenance, not coordinate magnitude

---

## Depth Rendering / See-Through Face Audit

### Source evidence

`viewport.py` contains:
- inner-geometry substring promotion
- face mesh substring handling
- special logic for eyes/teeth/gums/tongues

These exist specifically because inner geometry is showing incorrectly through faces or disappearing behind them.

### Architectural interpretation

Those are not primary rendering features. They are **compensating controls for painter’s algorithm limitations**.

### GPU renderer evidence

`gpu_renderer.py` already documents that it uses:
- depth testing
- culling
- two-pass rendering
- explicit transparent handling

and explicitly claims to fix transparent geometry issues.

### Audit conclusion

The current visible bug — eyeballs and teeth/gums showing through faces incorrectly — persists because:

> **the production viewport is still architecturally bound to the CPU painter pipeline instead of the GPU z-buffered pipeline.**

This is the core rendering truth of the repo.

The CPU path is trying to simulate correctness through sorting and special-case promotion rules. The GPU path is the correct structural direction.

---

## Performance and Memory Audit

### Production renderer cost model

`FrameRenderer` is very large and CPU-heavy.

Rendering happens by producing **PIL RGBA images in a background thread**.

Textured rendering caps are low because PIL affine triangle rendering is slow. The file itself acknowledges this via conservative textured triangle limits.

### Override loading behavior

`src/core/resource_manager.py` preloads all Override files fully into memory in `_GameInstall._load_override()`.

That means one layer of memory residency is already guaranteed before textures/models are decoded.

### Cache layers likely causing duplication

The current architecture likely duplicates data across multiple layers:

1. **raw bytes**
   - `resource_manager.py`
   - override bytes
   - archive bytes

2. **decoded PIL images**
   - viewport texture cache
   - decoded texture images

3. **NumPy arrays**
   - acceleration path
   - tex array cache
   - rasterization buffers

4. **GL textures**
   - `gpu_renderer.py` texture cache

5. **model trees / scene data**
   - possibly duplicated across main window, builder scene, exported variants, deep copies

### Explicit source evidence for GPU cache cost

`gpu_renderer.py` keeps a GL texture cache with:
- `MAX_ENTRIES = 512`

and notes a worst-case VRAM estimate of roughly:
- **~341 MB for 512 512x512 textures**

That is reasonable for a GPU-only renderer, but in this project it sits **alongside** the CPU/PIL caches rather than replacing them.

### UI surface duplication

The repo has both:
- a large main window runtime
- a large standalone character builder runtime

That is not inherently wrong, but with current orchestration it increases the risk of:
- duplicated model state
- duplicated texture/image state
- duplicated viewport behavior
- cross-surface cache duplication

### Dependency-sensitive environment evidence

Running selected tests in the sandbox failed during collection because `pykotor` was not installed.

Observed exact failure:

- `tests/test_v99_full_character_export.py`
- `tests/test_v95_resource_manager.py`

failed to collect due to:

> `ModuleNotFoundError: No module named 'pykotor'`

### Performance and memory conclusion

The current memory/performance problem is not just “Python is slow.” It is a combination of:

- CPU-first viewport architecture
- multiple parallel rendering/cache paths
- preload-heavy resource behavior
- duplicated decoded representations
- large UI orchestration surfaces

---

## Import/Export Pipeline Audit

### Source shape

`src/converters/mesh_converter.py` contains:
- OBJ importer
- FBX importer
- FBX exporter
- GLTF importer/export-related logic
- texture conversion utilities

This file is a central interchange hub.

### FBX export strategy

`FBXExporter.export()` uses this priority order:

1. Autodesk FBX SDK
2. `pyassimp`
3. handwritten **ASCII FBX 7.4** fallback

This is a valid fallback strategy conceptually, but the handwritten ASCII path becomes the practical path whenever optional dependencies are absent or unreliable.

### Current sandbox dependency reality

Installed package check showed:

- `pyassimp` — **NO**
- `trimesh` — **NO**
- `pygltflib` — **NO**
- `moderngl` — **NO**
- `PIL` — **OK**

So in a minimal/default environment, much of the advertised interchange stack is unavailable.

### Loader dependency contract

`src/core/kotor_loader.py` hard-imports PyKotor and explicitly describes:

> **PyKotor is the only parsing path.**

That makes the pipeline dependency-sensitive at import time, not only at feature-use time.

### UI exposure of export path

- `src/gui/main_window.py` exposes FBX export and recommends full-character export for Unreal
- `src/gui/character_builder_window.py` also exposes FBX export

So the export feature is product-visible and positioned as a real workflow, not an experiment.

### Weakness of current exporter tests

The exporter test strategy is materially weaker than the UI suggests.

`tests/test_v99_full_character_export.py` mostly validates **text/token presence** in exported FBX content:
- `FBXHeaderExtension`
- `GlobalSettings`
- `Objects`
- `AnimationStack`
- `Takes`
- `Deformer`
- `Pose`
- `Connections`

That is useful as a format smoke test, but it is **not equivalent** to validating that:
- Unreal imports the skeletal mesh
- Blender imports the armature cleanly
- Assimp/ufbx parse the hierarchy and skin clusters correctly
- animations bind to the right skeleton
- materials resolve correctly

### Likely causes of Unreal import failure

Based on source inspection, likely root causes include:

1. **Custom handwritten ASCII FBX path is fragile**
   - handcrafted exporters often satisfy token-level structure while failing importer-specific semantic expectations

2. **Skeleton generation relies on placeholder synthetic bones**
   - missing supermodel bones are synthesized
   - this may not match what UE expects for a coherent bind skeleton

3. **Bind-pose and transform assumptions may not match UE expectations for all real models**
   - column-major/world-matrix assumptions can be locally correct but still wrong in importer interpretation
   - especially risky when mixing accessory/head/body/supermodel-derived skeletons

4. **Exporter correctness is tested textually, not against a real importer**
   - no proof of Blender/Assimp/Unreal acceptance as part of CI

5. **Texture material authoring is simplistic**
   - TGA sidecars
   - Phong material definitions
   - limited mapping to modern engine material expectations

### Audit conclusion

The FBX exporter should currently be considered:
- **ambitious**
- **substantially implemented**
- **not yet validated as a dependable DCC/game-engine interchange path**

### Required next step

GhostRigger should add **round-trip validation against real importers**, at minimum:
- Blender
- Assimp/ufbx

and ideally:
- Unreal smoke tests via scripted import logs or automated import validation harnesses

---

## Character Builder Audit

### Existing builder architecture

`src/gui/character_builder_window.py` already exists as a standalone window with:
- Assembly
- Rig
- Face
- Preview
- Export

This is a major positive architectural step.

### But it is not fully mature yet

The file explicitly describes some modes as **placeholders**.

So while the shell matches the intended redesign, the deeper workflow consolidation is incomplete.

### Backend support is already present

`src/core/character_builder.py` includes:
- template registry for K1/K2 body/head templates
- large KOTOR skeleton bone groups
- selection and template-loading support

`src/core/validation_service.py` already covers:
- hooks
- supermodel mismatch
- K1/K2 mismatch
- missing bones
- unrigged skin meshes
- weight normalization errors

### Audit conclusion

The character builder has the beginnings of the right architecture.

However, it still needs to become:
- the **primary**
- **simplified**
- **validated**
- **task-driven**

workflow,

rather than another surface layered on top of existing main-window-centric behavior.

The architecture is ready for consolidation, but not yet consolidated.

---

## Module Loading and Module Editor Audit

### Relative strength in the repo

`src/core/module_loader.py` is a high-level bridge between:
- `module_format.py`
- `scene_manager.py`
- `walkmesh_renderer.py`
- `game_library_ext.py`

Its docstring explicitly references `KotOR.js ForgeArea.ts`.

### Why this matters

This is one of the cleaner architecture zones in the repository because it is:
- more layered
- less GUI-dependent
- more explicit about responsibilities
- closer to an engine/editor boundary than the viewport stack

### Audit conclusion

The module loader architecture is **cleaner than the viewport architecture** and should be treated as a relative strength.

It is a useful model for how more of GhostRigger should be organized:
- domain logic in `core`
- GUI as consumer, not owner, of domain behavior

---

## Dependency and Environment Audit

### Observed sandbox package state

Installed packages check showed:

- `pyassimp` — NO
- `trimesh` — NO
- `pygltflib` — NO
- `moderngl` — NO
- `PIL` — OK

### Interpretation

Large parts of the pipeline are therefore feature-gated by optional dependencies.

This means the program’s advertised capabilities exceed what the default environment guarantees unless dependencies are correctly installed.

### Practical implication

A user can reach UI surfaces for:
- FBX export
- glTF behavior
- GPU rendering
- advanced interchange

while the actual runtime may silently or structurally degrade into fallback behavior.

### Audit conclusion

The environment/dependency model needs to become more explicit:
- startup diagnostics
- feature readiness matrix
- dependency checks surfaced in UI
- environment self-test command
- CI matrix covering minimal vs full environments

---

## Testing Audit

### Claimed vs locally reproduced state

The README claims roughly **5007 tests passing**.

However, the local sandbox could not reproduce relevant tests without `pykotor`.

### Relevant observed test failure

`pytest` collection failed for:

- `tests/test_v99_full_character_export.py`
- `tests/test_v95_resource_manager.py`

because:

> `ModuleNotFoundError: No module named 'pykotor'`

### Nature of current export tests

Many export-related tests are **content/token tests**, not downstream importer compatibility tests.

That means they validate:
- output contains expected sections
- output contains named tokens
- certain serialized blocks are present

but they do **not** validate:
- real importer acceptance
- skeleton usability
- animation usability
- material usability
- Unreal/Blender/DCC compatibility

### Recommended layered test strategy

#### 1. Unit tests for token structure
- keep current textual FBX structure tests
- they are useful as low-level serializer regressions

#### 2. Parser/importer round-trip tests
- export FBX
- import through Blender or Assimp/ufbx
- assert skeleton count, bone names, animation count, mesh count, material slots

#### 3. Viewport image regression tests
- canonical head with eyes/teeth/tongue
- assert image output correctness
- catch see-through face regressions visually

#### 4. Performance regression tests
- memory snapshots
- FPS targets
- cache growth checks
- big module load performance

#### 5. Real-world smoke tests
Run canonical assets through full workflows:
- `c_selkath`
- `c_bantha`
- `N_sithpraet`
- player heads with facial rigs
- module room geometry with tiled UVs

### Testing conclusion

The repo has a strong test culture signal, but the **most painful user-facing failures are not yet being tested at the right semantic level**.

---

## Problem-by-Problem Root Cause Matrix

| Problem | Root architectural cause | Evidence in source | Immediate containment fix | Proper long-term fix |
|---|---|---|---|---|
| Module texture wrapping / bad tiling | Inconsistent UV/wrap policy across CPU, accel, GPU, and TXI layers | `viewport.py` sentinel filtering; `gpu_renderer.py` module exemptions; `accel.py` frac wrap; `model_data.py` clamp flags | Disable UV-magnitude-based rejection for module/tile models; unify wrap defaults to repeat unless TXI clamp says otherwise | Remove sentinel-driven UV validity rules entirely; move to authoritative per-face/per-sampler wrap semantics |
| RAM usage / slowness | CPU-first viewport architecture plus duplicated cache layers and preload-heavy resource behavior | `FrameRenderer` CPU thread rendering; override preload in `resource_manager.py`; PIL/NumPy/GL cache layers | Add memory diagnostics, lower redundant caches, avoid duplicate decoded representations, make override loading lazy or bounded | Make GPU renderer primary, rationalize cache ownership, lazy-load override assets, unify model/texture residency rules |
| Unusable FBX export to Unreal | Handwritten ASCII FBX serializer tested textually rather than importer-semantically | `FBXExporter.export()` fallback order; token-based tests in `test_v99_full_character_export.py` | Add Blender/ufbx validation script and exporter self-check report | Replace or harden handwritten path with importer-validated interchange pipeline and round-trip tests |
| Depth issues showing eyeballs and teeth through faces | Production viewport still depends on painter’s algorithm and workarounds | `viewport.py` inner-geometry promotion and face rules; `gpu_renderer.py` already has depth testing and two-pass rendering | Route problematic head rendering to GPU path when available | Make GPU renderer the primary viewport path and demote CPU renderer to fallback/offline mode |

---

## Code-Level Roadmap by File

## Phase 1 — Stabilize textures/depth/export

### `src/gui/viewport.py`
- stop using UV-magnitude sentinel logic as a primary correctness gate
- isolate legacy CPU-only heuristics behind compatibility flags
- add explicit warning banner when CPU fallback is active
- remove production dependence on painter-order hacks for face correctness
- keep only minimal CPU fallback needed for headless/test/offline use

### `src/gui/gpu_renderer.py`
- harden module texture wrap handling as the authoritative implementation
- ensure sampler state derives from node TXI flags consistently
- expose renderer readiness status to UI
- add deterministic debug overlays for:
  - depth
  - alpha-test
  - UVs
  - material slots
  - inner geometry

### `src/gui/accel.py`
- treat this as CPU fallback acceleration, not primary architecture
- align wrap behavior with GPU path
- ensure no silent policy differences remain relative to GPU sampler logic

### `src/core/resource_manager.py`
- stop preloading all Override files into memory by default
- add lazy or bounded loading for Override assets
- add metrics for:
  - raw bytes loaded
  - decoded textures count
  - cache hit/miss
- expose resource residency stats for diagnostics

### `src/converters/mesh_converter.py`
- add exporter validation report generation
- emit warnings when using handwritten ASCII FBX fallback
- log actual dependency path chosen
- add optional external validation hook for Blender/ufbx
- separate serializer correctness from engine-compatibility assertions

### `src/core/kotor_loader.py`
- make PyKotor dependency failure explicit and friendlier
- add feature probes instead of hard-crashing unrelated surfaces during import
- centralize loader diagnostics

---

## Phase 2 — Make GPU renderer the primary viewport

### `src/gui/viewport.py`
- invert architecture: GPU-first, CPU-second
- `FrameRenderer` becomes fallback/offline renderer
- main viewport should prefer `GpuRenderer` whenever available
- minimize duplicated state between CPU and GPU paths

### `src/gui/gpu_renderer.py`
- become the canonical viewport backend
- expose a stable renderer interface consumed by viewport shell
- add texture/material readiness logging and render health status
- support consistent node filtering and per-node material rules

### `src/gui/main_window.py`
- stop implicitly centering workflow on the legacy viewport behavior
- surface renderer backend status clearly
- add user-facing “GPU active / CPU fallback” indicator
- route render settings to a backend-neutral renderer interface

---

## Phase 3 — Reduce memory duplication and improve responsiveness

### `src/core/resource_manager.py`
- move to lazy/raw asset cache with eviction policy
- avoid permanent byte residency for all override files
- add configurable cache ceilings

### `src/gui/viewport.py`
- eliminate duplicate PIL/NumPy caches where not needed in GPU-first mode
- keep only minimal CPU cache layer
- measure and log image/framebuffer sizes and cache pressure

### `src/gui/gpu_renderer.py`
- unify texture cache ownership
- avoid duplicated uploads across windows when feasible
- add explicit cache invalidation APIs tied to model unload / scene swap

### `src/gui/main_window.py`
- reduce persistent duplicated model state across surfaces
- simplify orchestration pathways
- make the main window consume builder/module/editor services rather than duplicating them

### `src/gui/character_builder_window.py`
- ensure builder scene/model ownership is clean and isolated
- avoid deep-copy-heavy flows where possible
- use shared immutable source assets plus editable working scene objects

---

## Phase 4 — Harden FBX/glTF/OBJ export and importer validation

### `src/converters/mesh_converter.py`
- add round-trip import validation against:
  - Blender
  - Assimp/ufbx
- add exporter conformance checks:
  - bind pose node count
  - cluster counts
  - animation stack naming
  - material-texture linkage
- produce machine-readable export reports

### `src/core/kotor_loader.py`
- document and validate bind-pose assumptions
- add conversion diagnostics for supermodel-derived skeleton completion

### `src/gui/main_window.py`
- separate “export file generated” from “export validated”
- present warnings clearly:
  - ASCII fallback used
  - synthetic bones inserted
  - missing material sidecars
  - dependency path degraded

### `src/gui/character_builder_window.py`
- export only through validated backend
- display validation summary inline before final export

---

## Phase 5 — Simplify and consolidate the character builder UX

### `src/gui/character_builder_window.py`
- make this the primary workflow for head/body assembly, rigging, preview, and export
- finish placeholder modes
- ensure Assembly/Rig/Face/Preview/Export each map to clear backend services
- reduce ambiguity and hidden state
- use this window as the authoritative character workflow, not a secondary surface

### `src/core/character_builder.py`
- formalize template transfer services
- formalize part slot definitions and assembly rules
- add canonical K1/K2 rig transfer modes
- expose simpler APIs for GUI use

### `src/core/validation_service.py`
- expand validation into exporter gatekeeping
- add severity promotion for importer-risk scenarios
- add Unreal-facing and DCC-facing validation profiles

### `src/gui/main_window.py`
- remove overlapping character-builder responsibilities
- launch builder as the default character editing surface

---

## Phase 6 — Broaden module pipeline and engine-style scene assembly

### `src/core/module_loader.py`
- keep as domain-first module loading layer
- broaden support for room assembly, visibility, and resource diagnostics
- deepen parity with engine-style scene construction

### `src/core/scene_manager.py`
- strengthen room/object graph ownership
- support better streaming, culling, and debug visibility states
- provide cleaner scene data to viewport and module editor

### `src/gui/modular_panel.py`
- consume scene/module services, not reimplement them
- use module loader architecture as a model for separating GUI from domain logic

---

## External Reference Stack and What Each Project Should Teach GhostRigger

### 1. GhostRigger / Kotor-3D-Model-Converter
https://github.com/CrispyW0nton/Kotor-3D-Model-Converter

**Lesson:** the repo already contains the necessary subsystems; the next step is consolidation, not endless feature branching.

### 2. PyKotor
https://github.com/OldRepublicDevs/PyKotor

**Lesson:** file-format authority should be centralized. GhostRigger should reduce parsing duplication and dependency ambiguity around KOTOR resource handling.

### 3. KotorBlender
https://github.com/seedhartha/kotorblender

**Lesson:** DCC-facing correctness matters more than text serialization. Model import/export behavior should be validated against practical art-tool workflows.

### 4. KotOR.js
https://github.com/KobaltBlu/KotOR.js/

**Lesson:** a modern renderer/tool stack can coexist with deep KOTOR-specific semantics. GhostRigger should study how tooling and runtime concepts are kept aligned.

### 5. reone
https://github.com/seedhartha/reone

**Lesson:** engine-style resource and scene discipline helps editor reliability. Module and runtime assembly should be data-driven and explicit.

### 6. xoreos
https://github.com/xoreos/xoreos

**Lesson:** low-level engine semantics are best handled structurally, not through UI-layer workarounds. Rendering and format correctness should follow engine reality.

### 7. ufbx
https://github.com/bqqbarbhg/ufbx

**Lesson:** interchange validation should go through robust, battle-tested importers. GhostRigger needs this kind of parser in its exporter validation stack.

### 8. FBX2glTF
https://github.com/facebookincubator/FBX2glTF

**Lesson:** modern interchange needs conversion pipelines verified against real runtimes. Export should be validated through downstream consumers, not only by generation.

### 9. openfbx
https://github.com/nem0/openfbx

**Lesson:** lightweight importer validation is valuable. Even a secondary validation parser can catch serious structural exporter defects.

---

## Applied Guidance from the 3 Attached Books

## 1. OpenGL / rendering book

Most relevant takeaways:
- VBO/VAO-based GPU pipeline
- hardware depth testing
- alpha testing for punch-through/cutout materials
- clear view/projection matrix separation
- batch rendering
- instancing
- proper viewport and camera structure

### Applied conclusion
GhostRigger should replace the CPU painter path as the production viewport architecture with a professional GPU-backed viewport. The current GPU renderer already points in that direction; it needs to become primary, not optional.

---

## 2. Mesh processing / animation book

Most relevant takeaways:
- bind pose discipline
- explicit bone data structure
- offset matrices
- normalized weights
- linear blend skinning correctness
- retargeting maps
- axis remapping
- standardized base poses

### Applied conclusion
Rig transfer and export correctness depend on disciplined skeleton semantics, not ad hoc serializer output. This directly affects:
- supermodel bone synthesis
- bind pose generation
- exporter reliability
- character builder rig transfer
- Unreal import success

---

## 3. Engine/tools architecture book

Most relevant takeaways:
- single source of truth
- modular architecture
- integrated editor/runtime data
- clear asset conditioning pipeline
- cleaner UI ergonomics
- minimal modal depth
- asset registries
- hot reload
- maintainability through explicit interfaces

### Applied conclusion
GhostRigger’s next maturity step is architectural simplification:
- one authoritative viewport path
- one authoritative character workflow
- clearer domain/backend layers
- less orchestration concentration in giant GUI files
- reduced duplication of asset representations and editing surfaces

---

## Most Important Conclusions

1. **The repo already contains many of the right subsystems, but they are not yet architecturally consolidated.**

2. **The biggest single product problem is that the codebase has a GPU renderer but the main viewport behavior is still effectively designed around the CPU/PIL renderer and its workarounds.**

3. **The biggest single pipeline problem is that the FBX exporter is tested as text generation, not as a verified DCC/game-engine interchange path.**

4. **The biggest single architecture problem is orchestration concentration in giant GUI files.**

5. The module loader stack is a relative strength and should serve as a model for future architectural cleanup.

6. The character builder has the right shell and validation direction, but it still needs to become the main workflow rather than a parallel one.

---

## Appendix: Direct Evidence Excerpts

- **`viewport.py` UV sentinel**
  - `_UV_SENTINEL = 100.0`
  - comment explains it was raised from 20.0 to 100.0 to avoid incorrectly filtering legitimate tiled meshes

- **`viewport.py` production renderer caps**
  - `MAX_TRIS = 80_000`
  - `MAX_TRIS_TEXTURED = 5_000`
  - `MAX_TRIS_TEXTURED_ACCEL = 10_000`
  - `MAX_TRIS_TEXTURED_STILL = 50_000`

- **`viewport.py` acknowledges inner-geometry pain**
  - comments explicitly discuss eyes, eyelids, teeth, tongue, gum, jaw, and painter’s-algorithm limitations

- **`gpu_renderer.py` capability set**
  - documents depth buffer, alpha test, two-pass rendering, `GL_REPEAT`, lightmaps, envmaps, TXI support, caches, and MSAA

- **`resource_manager.py` override preloading**
  - `_GameInstall._load_override()` preloads loose Override files into `_override: Dict[str, bytes]`

- **`character_builder_window.py` mode list**
  - `Assembly`
  - `Rig`
  - `Face`
  - `Preview`
  - `Export`

- **`validation_service.py` rules**
  - hook missing/misaligned
  - weight unnormalized/zero/overflow
  - supermodel mismatch
  - K1/K2 mismatch
  - bone missing
  - skin mesh unrigged
  - no geometry

- **`kotor_loader.py` parsing contract**
  - explicitly states: **“PyKotor is the only parsing path.”**

- **`mesh_converter.py` FBX exporter priority**
  - Autodesk FBX SDK
  - pyassimp
  - handwritten ASCII FBX 7.4 fallback

- **local dependency observation**
  - installed in sandbox: `PIL`
  - missing in sandbox: `pyassimp`, `trimesh`, `pygltflib`, `moderngl`

- **local pytest observation**
  - `tests/test_v99_full_character_export.py` and `tests/test_v95_resource_manager.py` failed to collect because `pykotor` was not installed

--- 

## Final Engineering Position

GhostRigger is already much closer to a serious KOTOR toolchain than a prototype. The work now is not to keep adding workaround systems in parallel. The work is to:

- make the **GPU renderer** the real viewport,
- make the **character builder** the real character workflow,
- make the **exporters** importer-validated instead of token-validated,
- and reduce architectural gravity around giant GUI files.

Only after that consolidation will the individual fixes for tiling, RAM, FBX usability, and depth artifacts stop reappearing as recurring symptoms.