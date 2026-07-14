# Map Studio Cross-Check: Holocron, GhostScripter, Play-in-Editor

Date: 2026-07-12
Owner: LordVaderCW
Task: 019f489a-168a-7b20-875e-cd33a47c53da (Audit Map Studio workflow)

This document preserves the completed read-only audits from the 2026-07-09
through 2026-07-12 Map Studio continuation so they are not rediscovered.
No code was implemented as part of these audits. No new in-game proof is
claimed anywhere in this document.

Evidence classes used throughout:

- **Directly observed behavior**: seen by the user or agent in the running
  Debug application or in the real game.
- **Source-derived fact**: read from exact source code at a pinned commit.
- **Design inference**: an architectural conclusion, not a measured fact.
- **Headless proof**: script/pytest/profiler output without a visible app.
- **Visible Debug-app proof**: the rebuilt GhostStudio Debug executable was
  operated and observed.
- **Real-game proof**: the user personally warped and confirmed in KOTOR.
  None of the audits below produced new real-game proof.

## 1. Holocron Toolset Audit

Official source: https://github.com/OpenKotOR/HolocronToolset
Audited commit: `5635e346bec0d7bc38e7485f721c8e6ca42ded5d` (source-derived)
PyKotor: https://github.com/OpenKotOR/PyKotor
Local PyKotor checkout: `C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\PyKotor`
(its `Tools\HolocronToolset` directory was empty/uninitialized during the
audit; official web source was used instead).

Prior comparison: `docs/audits/holocron_toolset_comparison.md`.

### 1.1 Demand-aware rendering (highest priority)

Source-derived: Holocron's module renderer
(`src/toolset/gui/widgets/renderer/module.py`) gates repaint work with
`_scene_has_pending_async_work`, `_mouse_world_refresh_needed`, and
`_needs_continuous_render` instead of broadly rebuilding on every edit.

Source-derived (GhostStudio): many placement, light, and property edits
route through `module_editor_window.py::_refresh_all`, a broad synchronous
rebuild that re-derives placements, room lights, the combined viewport
preview model, fallback markers, outline geometry, walkability overlays,
walkmesh status, room choices, connection audits, readiness, and validation
on every call.

Headless proof (prior measurement): the broad refresh averaged roughly
25 ms before paint and OS overhead.

Required direction (design inference): replace broad refreshes with
command-specific dirty updates — update the affected placement
transform/model in place, touch only relevant outliner/table/property rows,
dirty only necessary renderer/overlay caches, debounce readiness and
validation, and reserve full scene/model rebuilds for topology/resource
changes. This is Phase B of the continuation plan.

### 1.2 Typed template editing

Design inference from Holocron's per-type editors: expand the proven
Placeable Builder pattern to UTC creatures, UTD doors, UTT triggers,
UTE encounters, UTS sounds, UTM stores, and UTW waypoints, with
`Edit Template` and `Create Variant` from selected placements. Animated
doors may appear under the user-facing Place category but must preserve
their real UTD/GIT Door engine type.

### 1.3 Details split

Design inference: a selected gameplay object should expose three clean
surfaces — Instance (GIT position, facing, visibility, editor state),
Template (typed UTC/UTP/UTD/etc fields and dependencies), and
Assembly/Puzzle (multi-resource behavior and parameters when applicable).

### 1.4 Deep links

Design inference: add real NSS/NCS selection and editing, DLG links,
resource dependency views, resource → references navigation, placement →
template navigation, and typed local/global parameter workflows.

### 1.5 Command history

Design inference: room, module, blueprint, placement, and property
mutations must use consistent command, undo, and dirty-state handling.

### 1.6 Additional quality-of-life gaps

Design inference from feature comparison: searchable type-bucketed
outliner, shared 2D plan + 3D selection, placement marquee, editable VIS
matrix, align/distribute/nudge, camera bookmarks, isolate/solo selection,
sound audition, cancellable asynchronous export/stage/install, and clear
resource-collision and dependency reports.

### 1.7 Holocron defects not to copy

Source-derived from the audited commit:

- Resource writes that can orphan files.
- Partial undo / direct mutations.
- Save-to-MOD paths that write only GIT/LYT.
- Blank maps that copy source PTH instead of generating it.
- Prototype DLG graphs with hardcoded data.
- Parser/readback success treated as engine proof.

GhostStudio's stronger existing behaviors to preserve: direct drop,
keep-placing, WOK grounding, End-key snap, actual model previews,
Placeable Builder, command snapshots, dependency closure, archive
readback, and raw/game-proof gates.

## 2. GhostScripter Ownership and IPC Audit

Repository: `C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\GhostScripter-K1-K2`

### 2.1 Facts (source-derived)

- GhostScripter is GPL-3.0; GhostStudio is MIT. Explicit
  relicensing/dual-licensing must be resolved before copying code;
  otherwise implement cleanly from public formats, PyKotor, retail
  fixtures, and behavior tests.
- It runs a second Qt/application/package system and duplicates GFF, DLG,
  ERF, TLK, 2DA, JRL, KEY/BIF, and resource handling.
- It maintains a separate project/database/revision authority.
- Its current REST IPC bridge drops payload data and lacks
  revision/hash transactions; duplicate IPC servers exist; large binaries
  are commonly transported as base64; shutdown and capability handling are
  inadequate.
- Port compatibility state: GhostStudio 7001, GhostScripter 7002, legacy
  GModular 7003, planned event bus 7000.
- Its dialogue editor widget is ~3,454 lines; do not begin integration by
  porting it.

### 2.2 Architecture decision (design inference, adopted)

Do not wholesale merge the GhostScripter application and do not make its
REST IPC bridge the permanent primary workflow. Instead build a shared
Qt-free authoring core inside GhostStudio:

- Core.IO owns PyKotor-backed DLG/GFF/JRL/TLK/2DA and NSS/NCS artifact IO.
- Core.Resources owns `GameResourceProvider` and `ResourceAddress`.
- Core.Project owns document references, target game, revisions, content
  hashes, dirty state, and generated-output references.
- Core.Workflow provides `ScriptCompileService`, `ScriptDecompileService`,
  `DialogueAuthoringService`, `QuestAuthoringService`,
  `NarrativePackageService`, and `GlobalVariableCatalogService`.
- Core.Validation handles ResRefs, missing resources, dialogue links,
  unknown fields, compilation, global registration, JRL agreement,
  hashes, dependencies, and K1/K2 differences.
- Core.Scene retains placement and hook/reference intent and consumes a
  typed `NarrativeArtifactSet`.
- Core.Automation exposes the same headless services over MCP/versioned
  IPC without duplicating compilers or writers.

Precise Map Studio integration point (source-derived):
`module_editor_controller.py::authored_project_extra_resources()` currently
combines texture, placeable, and creature resources but lacks general
script, dialogue, JRL, and 2DA artifacts. Extend it with a typed artifact
set, not loose dictionaries. Start with one Qt-free script compilation
service (Phase D).

## 3. Puzzle and Variable Correction

Headless proof: a focused scan inspected 896 unique K2 UTPs and found zero
containing `VarTable`. `207tel` GIT placeables primarily contain template
reference, position, bearing, and K2 tweak color.

Conclusion (source-derived + design inference): there is no monolithic
"puzzle placeable" in the engine. Puzzle behavior is composed from ordinary
placed templates, script hooks, compiled NSS/NCS, runtime local variables,
module/global variables with `globalcat.2da` registration where
appropriate, and DLG/JRL/TLK/item/store dependencies.

The current proof puzzle uses local boolean slot 40 on three switch
placeables (headless matrix proof only).

Implementation direction (Phase E): an `AuthoredGameplayAssembly`
prefab with stable assembly ID, member placement IDs, member roles/tags,
dependency edges, editable parameters, script hooks and DLG references,
local-variable indices, global-catalog patch operations, JRL/TLK
dependencies, generated resources, and validation reports. Dragging a
puzzle library entry must atomically create ordinary members, preserve
independent selection, and create one undo step. Export closure must
include every required UTP/UTC/UTD/UTM/UTI/DLG/NSS/NCS/JRL/2DA/TLK
resource or patch operation.

## 4. Honest Play-in-Editor Architecture

Design decision (adopted): expose two clearly separate modes.

### 4.1 Simulate in Editor

Safe scope: WOK/PTH click-to-move preview, start/transition reachability,
door/trigger/encounter volumes, placement models and facing,
hostile/friendly/free-roam intent, puzzle dependency graph, missing
template/script/dialog diagnostics, approximate lighting/sound preview.

Label it `Simulation — not KOTOR proof`. It must not claim exact NWScript
execution, AI, combat, animation state, KOTOR lightmaps, save-state
behavior, or engine pathfinding.

### 4.2 Build & Test in KOTOR 2

`MapStudioGameTestWorkflow` under Core.Workflow with a full transactional
state machine: KMAP snapshot + authored-state digest lock; export into
`Saved/GameTestStaging/<session-id>`; MOD readback + raw engine-contract
revalidation; MOD/dependency hashes; exact KOTOR 2 root/executable
verification; refusal to mutate files while KOTOR runs; collision scan of
Modules and required Override files; in-session backups; same-directory
temp copy + hash verify + atomic replace; stale `currentgame/plcaa.mod`
detection (block by default, explicit backed-up quarantine only while the
game is stopped); optional input-queue reset; logger armed before launch
and bound to exact PID/executable path; user-facing instruction to load a
normal save and run `warp plcaa`; automated warp kept
optional/experimental; exact game-window capture + logger analysis; user
functional checklist; proof recorded only when build hashes, logger,
evidence, and checks match the locked revision; rollback only of files
still matching this session's installed hashes.

### 4.3 Current gaps (source-derived)

- `prepare_authored_module_install` still uses direct `shutil.copy2`.
- Installation lacks a game-running gate and a complete transaction.
- Generic smoke/evidence scripts still alias old `grdev01` helpers.
- Map Studio launch handoff only opens a command/folder.
- DirectInput commands lack session/command acknowledgements.
- Fixed-ratio menu automation can falsely succeed.
- Reference automation can delete the entire `currentgame`.
- Proof manifests are not fully hash-bound.
- Normal installation does not yet transactionally deliver all Override
  dependencies.

Hard rules: never write into KOTOR process memory; never claim an embedded
Odyssey engine; never broadly delete `currentgame`.

## 5. Evidence Status Summary

Visible Debug-app proof (as of 2026-07-12):

- Real `207tel` loaded; 90-event 3ds Max Alt+MMB orbit processed in
  1.072 s without a hung window
  (`Saved/VisibleProof/map_studio_207tel_performance_2026-07-12`).

Headless proof:

- `207tel` steady-state profile (`Saved/Profiles/map_studio_207tel_steady_state.json`):
  raw ModernGL 13.593 ms median (~73.57 FPS); headless Qt orbit 23.009 ms
  median / 24.264 ms p95 (~43.46 FPS) at 1280x720.
- TPC bounded-mip loading: first ten `207tel` textures 53.13 s → 1.77 s;
  `tel_hw10` 15.455 s → 0.205 s.
- GModeler picking: deferred exact rebuild 236.944 ms once (was 931.82 ms
  per camera move); cached occupied-cell pick 0.498 ms median / 4.183 ms p95.
- Custom `plcaa` headless gameplay matrix 19/19
  (`scripts/k2_plcaa_gameplay_matrix.py`).
- 896-UTP `VarTable` scan (section 3).

Real-game proof: none new from these audits. The user has not yet proven
the normal Map Studio UI → export → install → `warp plcaa` loop for enemy
hostility, NPC roaming, terminal, container, ordered puzzle, animated
door, transition, player start, sounds/triggers, paint, terrain, WOK,
lighting, or sky. All in-game development testing must use custom `plcaa`.
