# GhostScripter to GhostStudio preservation matrix

**Audit date:** 2026-07-13
**Audit owner:** LordVaderCW
**Legacy source:** `C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\GhostScripter-K1-K2`
**Target:** `C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\Ghost-Studio`
**Purpose:** define, without overclaiming, what must be preserved before the standalone GhostScripter application can be considered fully integrated into GhostStudio.

## Executive verdict

All inventoried GhostScripter product systems now have a preserved or explicitly
superseding GhostStudio owner and a user-visible route in the standalone
**Scripting Suite** workbench. Native packaging and visible acceptance are
complete, so the former standalone application can be retired as the authoring
UI while its source repository remains a read-only migration/reference source.
This is a clean-room behavior integration; no GPL implementation or assets were
copied.

The current authoritative preservation snapshot is:

| Surface | Current result | Honest interpretation |
|---|---:|---|
| Legacy public MCP command names inventoried | 60/60 | Complete clean-room inventory. |
| Legacy public MCP names callable in GhostStudio | 60/60 | Every inventoried name is callable through a bounded KotorMCP compatibility adapter or its existing native command. |
| Bounded mutation writers | 8/8 | GFF, DLG, 2DA, ERF, SSF, LIP, PTH, and Override writes use typed GhostStudio owners, validation, semantic or exact readback, and explicit install gates instead of arbitrary filesystem writes. |
| Reachable Scripting Suite surfaces | 12/12 | Scripts & Dialogue, NWScript Reference, Quest Builder, JRL, 2DA/Globals, TLK, Voice/LIP/SSF, Project/History, Package/Test Install, Guided Workflows, Blueprint/GFF, and Integrated Tools are composed in one uncluttered window. |
| Project continuity | Preserved and strengthened | Portable JSON projects, read-only legacy SQLite/project import, an active Legacy History browser/recovery path for scripts, quests, dialogues, project metadata, 2DA plans, dependencies, preferences, and recents, immutable revisions, asset-filtered recovery, and persistent export/install/TLK receipts replace the standalone local database. |
| Audio/resource continuity | Preserved and strengthened | Dialogue and LIP preview resolve K1/K2 WAV plus genuine MP3 resources lazily from Override/module/StreamVoice/StreamWaves/StreamSounds/BIF precedence without decoding installations at startup. |
| Map Studio integration | Runtime narrative/data handoff | Validated NCS, DLG, JRL, 2DA, LIP, SSF, and typed GFF resources are staged for authored module export. TLK remains a deliberate global install with backup/restore receipts. |
| Packaging | ERF/MOD/SAV, stage, install, rollback | Archive readback, owned-output promotion, conflict inspection, backups, rollback, and receipts are present. SAV creation is labeled advanced and does not claim to synthesize a complete playable save from incomplete inputs. |
| Retail engine proof for this integration | None | PyKotor parsing and exact readback are necessary checks, not proof that KOTOR 1 or KOTOR 2 loads and executes the result. |

The product-system port, native payload, rebuilt workbench, and visible
all-theme acceptance are complete. User-run K1/K2 retail execution remains the
required engine oracle. That gate limits claims about engine behavior; it does
not justify dropping or reintroducing a separate GhostScripter subsystem.

## Post-integration resolution (authoritative)

| Legacy system | Preserved GhostStudio destination |
|---|---|
| NSS/NCS authoring, compile, disassembly, reference/search | Scripts & Dialogue plus NWScript Reference; authoritative disassembly and exact-recompile status remain visible, while completion inserts callable syntax and shows the target-game function signature. |
| DLG graph/forms/audio | Loss-aware Dialogue editor with graph/outline synchronization, searchable nodes, module/UTC-backed participant tags, typed fields (including K2 `DisplayInactive` BYTE round-trip), WAV/MP3 preview, existing-target links, shared targets/cycles, retarget/remove/delete actions, and a distinct editable-copy gate for opaque imported topology. |
| Quest templates and JRL | A versioned, reopenable Quest Definition editor plus Journal pages preserve variables, states, triggers, objectives, spawned resources, dependencies/conflicts, unknown legacy fields, stable resrefs, globals, generated handlers, and deterministic readback. Legacy script/quest/dialogue history can be browsed and recovered into a new location without modifying its source. |
| 2DA, `globalcat.2da`, and changes.ini | 2DA & Globals page with filtering, row/column operations, copy/paste, independent undo/redo, validation, readback, and conservative patch output. |
| TLK | Dedicated Talk Table workflow with metadata-preserving save and explicit global install/backup/restore policy; never silently staged as Override/module data. |
| LIP, SSF, voice preview | Voice/LIP/SSF page with synchronized LIP timeline preview, all retail SSF entries preserved, and target-game loose/BIF audio lookup. |
| ERF/MOD/SAV and Override delivery | Package & Test Install page backed by transactional archive/stage/install/rollback services and persistent receipts. |
| Projects, recents, preferences, revisions, export history | Project & History page; old project/SQLite inputs are read-only imports into a new portable GhostStudio project, with exact browse/recover records and provenance for legacy project JSON, quest artifacts, history, 2DA plans, dependencies, preferences, and recents. |
| GFF/blueprints, GIT/module resources | Typed Blueprint & GFF page plus direct routes to Resource Browser, Module Studio, and Map Studio. |
| Tutorials/help | Guided Workflows page with direct routing for script, dialogue, quest, 2DA, voice, packaging, Map handoff, and migration tasks. |
| IPC/MCP automation | Automation-owned port-7002 compatibility shim and all 60 legacy commands; required argument names and legacy response keys are preserved with additive bounded provenance/readback evidence. The eight mutation calls are typed/guarded adapters rather than arbitrary filesystem writers. |
| Map test workflow | Scripting Suite resources hand off to Map Studio/PIE for editor simulation and packaging; manual retail KOTOR remains the final oracle. |

## Audit method and clean-room boundary

This is a behavior-preservation audit, not a source port. GhostScripter declares GPL-3.0 in its README and license. This audit uses only observable product behavior, public command names, file-format expectations, tests, and documentation to define compatibility. No GhostScripter implementation text, Qt layouts, icons, database schema, or other assets should be copied into GhostStudio.

Evidence reviewed in the legacy repository:

- `README.md`, `README_TESTER.md`, `ROADMAP.md`, `SYSTEMS_DESIGN.md`, and `AUDIT_REPORT.md`.
- The main window and all editor/widget modules for NSS/NCS, DLG, quests, 2DA, TLK, JRL, LIP, SSF, ERF/MOD/SAV, assets, GIT, GFF, logs, and tutorials.
- Core services for compiling, decompiling, resource access, file formats, projects, SQLite history/preferences, IPC, MCP, and tests.
- The 2026-07-10 legacy audit evidence: 1,513 tests passed, 65 skipped, 309 subtests, plus 41 retail-resource integration tests. That audit proved parser/writer behavior on the fixtures it named; it did not replace visible human workflow testing.

Evidence reviewed in GhostStudio:

- `src/core/scripting/` services and their canonical tests.
- `src/gui/windows/qt_scripting_*.py`, `src/gui/controllers/scripting_*.py`, and the application scripting workflow.
- Map Studio integration, stock Module Editor, Resource Browser, Blueprint Editor, PIE contracts, and KotorMCP.
- `native/GhostRigger.Core.Automation/Python/src/kotormcp/tools/legacy_ghostscripter.py` and `tests/test_ghostscripter_automation_compat.py`.
- The embedded-Python package boundaries under `native/GhostRigger.Core.GUI.Display`, `native/GhostRigger.Core.Workflow`, and `native/GhostRigger.Core.Automation`.

No current GhostStudio test was executed as part of this documentation-only audit. A row that says a focused test “exists” means its source was inspected; the test must still pass in the final integration verification run.

## Status legend

| Status | Meaning |
|---|---|
| **Preserved** | Equivalent behavior exists in the proper owner, has a reachable product or automation route, and has focused verification. |
| **Superseded** | GhostStudio has a stronger workflow that covers the legacy user task; the stronger workflow still needs an obvious route from the scripting suite. |
| **Core-only** | The bounded backend exists, but the complete visible workflow or automation adapter does not. |
| **Unwired** | Presentation/controller code exists but is not composed into the launched window or connected to the application workflow. |
| **Partial** | Some data or behavior is available, but response semantics, enrichment, editing, validation, or delivery is incomplete. |
| **Safely withheld** | A broad mutation command is deliberately not exposed because GhostStudio requires validation, explicit ownership, transactions, and readback. This is a safety improvement only if an accessible bounded workflow exists. |
| **Missing** | No equivalent behavior was found. |
| **Unproven in game** | Structural readback exists, but KOTOR 1/KOTOR 2 runtime acceptance has not been demonstrated. |

## Initial product/UI gap matrix (historical audit evidence)

The rows in this section record the pre-integration gaps that drove the work.
Their status wording is historical and is superseded by the authoritative
post-integration table above; the verification language remains useful as the
retail acceptance checklist.

| Legacy surface/capability | GhostStudio owner and proposed location | Status | Current evidence | Exact completion verification / blocker |
|---|---|---|---|---|
| One standalone scripting workbench with project, editors, resources, build, and help navigation | `QtScriptingDialogueStudioWindow`, owned by GUI Display; orchestration in `ScriptingStudioController` and the application scripting workflow | **Partial** | The main GhostStudio launcher opens a separate Scripting & Dialogue Studio, keeping the main viewport uncluttered. The visible window currently composes Start, NSS/NCS, and DLG only. | Launch the native Debug application, open the scripting suite from its one clear main-shell button, and visually reach every page listed in this matrix without importing a Python module manually. Verify Default, Matrix, Droid, Dark, Light, and Classic themes. |
| NWScript source editor | `QtScriptEditorPage` + `ScriptingStudioService` | **Preserved with UX gaps** | Source tabs, syntax highlighting, find/replace, go-to-line, common shortcuts, save/close behavior, compile diagnostics, and lightweight completion exist. | Focused UI tests must pass; visible test must prove open/edit/save/undo/redo/find/replace/go-to-line/compile. Add a visible line-number gutter, full K1/K2 definition-backed completion, parameter/signature help, and configurable editor preferences before claiming full UX parity. |
| K1/K2 NWScript compiler | `ScriptingStudioService.compile_script` | **Preserved; unproven in game** | Uses the PyKotor compiler, validates resrefs, parses NCS back, and builds through an owned transactional output. `test_script_compile_produces_parseable_ncs_readback` exists for K1/K2. | Run the focused tests, then compile one deterministic K1 script and one K2 script, package each, trigger each script in retail game, and capture proof. |
| NCS decompile/reconstruction | `ScriptingStudioService.decompile_ncs` + `NWScriptReferenceService.inspect_ncs` | **Stronger/honest replacement** | GhostStudio always retains authoritative disassembly, fingerprints the original, and labels recovered source by exact-recompile status instead of calling reconstruction authoritative. | Run `test_ncs_inspection_always_keeps_authoritative_disassembly`, `test_studio_ncs_document_retains_original_fingerprint_and_disassembly`, and compatibility compile/decompile tests. Visible UI must show both recovered source and authoritative disassembly. |
| NWScript function database, categories, search, and signatures | `NWScriptReferenceService` + `QtScriptingReferencePage` | **Unwired** | Real K1 and K2 compiler definitions back the service; the reference page exists. It is not imported or composed by the window. | Compose the page, bind game selection/search/category/result activation, insert selected signatures into the active source tab, and visibly verify both K1/K2 definition sets. Run `test_reference_exposes_real_k1_and_k2_compiler_definitions`. |
| Visual DLG graph editing | `DialogueAuthoringContract`, `QtDialogueEditorPage`, graph widget | **Preserved and stronger** | Graph-first editing, pan/zoom/fit, movable nodes, synchronized outline, stable IDs, cycles/shared targets, and typed root/node/link fields exist. Unknown GFF data is preserved; unsafe topology edits are blocked. | Run all `tests/test_dialogue_authoring_contract.py` and dialogue UI tests. Visibly open one K1 and one K2 retail DLG, change a node/link field, save, reload, and confirm graph/opaque metadata. Retail-trigger each dialogue after packaging. |
| Dialogue node audio preview and audio browsing | Dialogue editor plus shared audio/resource services | **Missing from the DLG page** | DLG audio fields are editable, but no equivalent play/stop/browse workflow was found in the composed dialogue page. | Add resource-resolved voice/sound preview using GhostStudio’s audio adapter; verify WAV/MP3-equivalent playback for a K1 and K2 dialogue node and preserve the resource reference on save. |
| Quest templates/scaffolds | `QuestScaffoldService`, `QtQuestScaffoldPage`, `ScriptingDataController` | **Unwired** | Simple, branching, and companion templates generate coordinated JRL states, global variables, and NSS handlers with legal deterministic resrefs. Page and controller exist, but are not composed. | Compose and bind the page. Run `test_all_preserved_quest_templates_generate_journal_globals_and_scripts` and `test_long_quest_names_get_stable_legal_script_resrefs`. Visible test must preview, commit, edit, build, and then trigger one quest state in retail game. |
| Journal/JRL editor | `JournalDocument`, `QtQuestJournalPage`, `ScriptingDataController` | **Unwired** | Typed JRL edit/snapshot/write/readback exists and preserves unknown fields; page/controller exist. | Compose the page; open/edit/add/remove/save K1 and K2 JRL fixtures; run `test_jrl_roundtrip_uses_entrylist_word_end_and_preserves_unknown_fields` and page intent tests; package and confirm journal updates in retail game. |
| 2DA table editor | `TwoDADocument`, `QtTwoDAGlobalsPage`, `ScriptingDataController` | **Unwired with UX gaps** | Table load/edit/add/remove row/column and save/readback exist. The page uses a filtered model. | Compose it and verify open/edit/save/reload on K1/K2 tables. Preserve or explicitly redesign legacy undo/redo, copy/paste, row duplication, rename, search, and large-table responsiveness. Run focused data/page tests. |
| `changes.ini` generation for 2DA edits | `TwoDADocument.export_changes_ini` | **Core-only; installer proof missing** | Conservative diff generation exists and refuses row deletion. Compatibility alias exists. | Apply emitted `changes.ini` with HoloPatcher/TSLPatcher to a clean fixture, compare installed 2DA to the requested result, and test append/update/2DAMEMORY-style cases. Do not claim installer compatibility from syntax inspection alone. |
| `globalcat.2da` editor | `GlobalCatDocument` through `QtTwoDAGlobalsPage` | **Unwired** | BOOLEAN/NUMBER/STRING globals and location preservation exist. | Compose the page, add all three types, save/reload, package with scripts that use them, and exercise values in retail K1/K2. Run `test_globalcat_contract_registers_boolean_number_string_and_preserves_location`. |
| TLK editor | `TalkTableDocument`, `QtTalkTablePage`, `ScriptingDataController` | **Unwired; install semantics unresolved** | Add/edit/search/jump and metadata-preserving save exist. Unknown flags, raw resrefs, and trailing bytes are tested. | Compose page and visibly edit K1/K2 TLKs. Define explicit whole-game `dialog.tlk` backup/install/restore semantics; do not treat TLK as a normal Override file. Prove byte preservation and retail string lookup. |
| LIP editor | `LipDocument`, `QtLipSoundSetPage`, `ScriptingDataController` | **Unwired** | Duration, 16 viseme shapes, keyframes, phoneme mapping, snapshot, and PyKotor readback exist. | Compose page; add/move/delete keyframes, save/reload, preview with matching audio, and prove lip movement in retail game. Run `test_lip_keyframe_authoring_snapshot_and_pykotor_roundtrip`. |
| SSF editor | `SoundSetDocument`, `QtLipSoundSetPage`, `ScriptingDataController` | **Unwired; core tail preservation fixed** | The 28 named slots are editable. The core now accepts at least 28 entries and preserves unnamed retail tail entries byte-exactly; a 49-entry test retains meaningful index 33. | Compose page, present an explicit read-only/advanced view of unnamed tail entries, run both SSF tests, and retail-trigger an edited sound-set event. Never truncate a retail SSF to 28 entries. |
| ERF/MOD package builder | `NarrativePackagingService` + `QtScriptingPackageOverridePage` | **Unwired; unproven in game** | Explicit resource list, PyKotor archive build, exact resource readback, and owned-output promotion exist. Page exists but is not composed. | Compose/bind page, build K1 and K2 archives, re-open each resource, then install/launch and execute a script/dialogue/quest in retail game. |
| SAV package support | IO/package owner | **Missing** | Legacy UI advertised ERF/MOD/SAV. Current narrative package service accepts ERF/MOD, not SAV. | Either implement a validated SAV workflow with fixture/readback/runtime proof or document a deliberate product decision to route saves to a dedicated Save Editor and remove the scripting-suite parity requirement. |
| Override staging and install | `NarrativePackagingService.stage_override`, `inspect_stage`, `install_override` + package page | **Unwired but stronger core** | Separate staging, conflict inspection, explicit backup/rollback/receipt, and module-archive blocking exist. | Compose/bind page. Verify stage does not mutate the game, conflicts block silent overwrite, backup/rollback restores originals, and only valid Override resource types install. Add special policies for TLK and module archives. |
| Asset library: project/game resources, search, previews | Shared Resource Browser, scripting resource catalog, Map Studio/Module Editor texture/model previews | **Superseded in parts; route unwired** | GhostStudio has broader resource search and dedicated model/module/texture previews. The scripting suite’s catalog currently scans only NSS/NCS/DLG, and `QtScriptingIntegratedToolsPage` is not composed. | Compose the route page, route activation by type, and visibly preview the same TGA/TPC/model/script/dialogue resources the legacy library handled. Expand typed narrative catalog types without blocking the UI. |
| GIT viewer/editor | Map Studio and stock Module Editor | **Superseded** | Legacy GIT UI was principally a 2D browse/select surface. Map Studio can hydrate and stage actual gameplay objects in a 3D module workflow; stock Module Editor exposes module-local GIT/template data. | Provide an obvious route from the scripting suite. Visible test: open a stock module, select/edit a creature/placeable/door/trigger/waypoint/sound, deep-link its scripts/dialogue, export, and prove the object in retail game. |
| Generic GFF viewer/editor | Stock Module Editor and Resource Browser | **Partial** | Typed resources can be inspected and module-local templates can be edited, but there is no demonstrated general-purpose typed GFF tree editor equivalent for arbitrary GFF files. | Route arbitrary supported GFF resources to a typed field/tree editor, preserve unknown fields/types, block invalid writes, and round-trip K1/K2 fixtures. |
| Standalone UTC/UTP/UTD/UTI/UTE/UTM/UTS/UTT/UTW blueprint editing | Existing `QtBlueprintEditor` plus stock Module Editor/Map Studio | **Partial; current route overclaims** | The current standalone Blueprint Editor is a JSON/plain-text migration host with a Latin-1 preview, not a complete typed GFF editor. Module-local editing and 3D placement are stronger but do not replace standalone blueprint authoring. | Replace or upgrade the standalone editor with typed GFF forms for every advertised blueprint type, unknown-field preservation, validation, resource lookup, save/readback, and visible K1/K2 proof. Correct the Integrated Tools copy until that is true. |
| Compiler/build/log viewer | Scripting diagnostics panes plus shared Output Log | **Partial** | Script compile/build diagnostics are visible in the scripting window. A route card for the shared Output Log exists but is not composed or connected. | Compose the route, aggregate compiler/validation/package/IPC/runtime messages with severity/source/timestamp, and visibly navigate from an error to the owning document/resource. |
| Guided tutorial | Start page quick guide plus shared tutorial route | **Partial** | The scripting Start page provides compact instructions. The legacy multi-step tutorial depth is not matched, and the Integrated Tools tutorial route is uncomposed. | Provide task-based flows for first script, dialogue, quest, 2DA patch, package, Map Studio binding, and retail test; verify each can be completed by a new user without hidden terminal steps. |
| Projects, recents, revision history, preferences | `NarrativeProjectService`, `NarrativeRecentProjects`, project/history page, shared GhostStudio settings | **Partial/unwired** | Portable typed JSON projects, explicit JSON recents, and immutable full-project revision snapshots exist. Page exists but is not composed. Shared app themes/layouts are stronger than standalone preferences. | Compose/bind the page; implement legacy project/history migration; visibly create/open/save/reopen/revise/recover. Preserve user editor preferences through shared settings. |
| Legacy per-script, quest, and dialogue history | Project revision service | **Partial** | Full-project immutable revisions are safer and more coherent, but there is no per-asset history browser equivalent or migration from the legacy SQLite rows. | Add asset-level diff/filter/restore on top of immutable project revisions or document an explicit replacement UX. Import legacy history without mutating the source database. |
| Export history | Project/package workflow | **Missing** | No equivalent persistent export receipt/history browser was found. Install receipts exist only around an operation. | Persist package/stage/install receipts in the project, including exact inputs, hashes, destination, backup, result, and retail-test proof; expose them in Project/History. |
| Map Studio deep-link and build handoff | `ScriptingStudioWorkflowMixin`, Map Studio panels/controller/export staging | **Preserved for NSS/NCS/DLG; partial overall** | Script hooks and creature dialogue can open the suite with map context. Successful current NCS/DLG resources can be staged into the next authored export and are invalidated when edited. | Run all `tests/test_map_studio_scripting_studio_integration.py`; visibly deep-link, compile, return, export, and retail-trigger. Extend the handoff to JRL, 2DA/globalcat, LIP/SSF, and validated blueprints needed by the project. |
| Live testing in Map Studio PIE | Map Studio PIE | **Partial and intentionally non-authoritative** | PIE previews movement, walkmesh, creatures, placeables, and audio, but its own contract says it does not execute arbitrary NWScript/NCS handlers or Odyssey action queues. It cannot yet prove dialogue/quest behavior. | Keep the “not KOTOR proof” label. Add bounded dialogue/script simulation only where semantics are implemented; final acceptance remains a retail K1/K2 run with logs. |

## Initial core/data/safety gap matrix (historical audit evidence)

| Contract | GhostStudio owner | Status | Preserved behavior | Remaining proof or gap |
|---|---|---|---|---|
| K1/K2 compile definitions | Core Workflow scripting reference | **Preserved** | Real PyKotor definitions, category/function/constant lookup, signatures. | Run focused reference tests and compare representative K1-only/K2-only functions. |
| Script document identity and legal resrefs | Core Workflow scripting studio | **Preserved** | Game, resref, path, dirty state, diagnostics, compile output; invalid and embedded bytecode cases blocked. | Add migration mapping from legacy project scripts and visible rename/dependency updates. |
| Compile output truth | Core Workflow scripting studio | **Preserved structurally** | NCS parse-back and diagnostics; transactional build tree. | Retail execution proof required. |
| Decompile truth | Core Workflow scripting studio/reference | **Stronger** | Authoritative disassembly retained; recovered source never silently presented as exact. | Preserve exact-recompile hash evidence in project/export receipts. |
| DLG graph identity | Core Workflow dialogue contract | **Preserved** | Stable opaque IDs survive cycles/shared targets and UI synchronization. | Retail dialogue run required. |
| DLG known and unknown fields | Core Workflow dialogue contract/studio | **Preserved** | Full root/node/link field snapshots; localized strings; unknown GFF preservation; unsafe topology mutation blocked. | Add corpus tests for more retail K1/K2 DLG variants and audio preview. |
| Quest scaffolds | Core Workflow quest service | **Preserved in core** | Simple, branching, companion patterns coordinate JRL/globals/NSS and legal deterministic resrefs. | UI composition and retail state-transition proof. |
| 2DA binary editing | Core Workflow data authoring | **Preserved in core** | Snapshot/edit/binary round-trip. | Large-table performance and actual patch-installer proof. |
| TLK preservation | Core Workflow data authoring | **Preserved in core** | Language ID, flags, sound metadata, raw resref bytes, string data, and trailing data. | Safe global install/backup/restore and retail lookup proof. |
| JRL preservation | Core Workflow data authoring | **Preserved in core** | EntryList WORD semantics and unknown GFF fields. | UI and runtime journal proof. |
| Global variable catalog | Core Workflow data authoring | **Preserved in core** | Boolean/number/string groups and source placement. | UI and runtime variable proof. |
| LIP preservation | Core Workflow data authoring | **Preserved in core** | Duration, 16 shapes, keyframes, readback. | Audio-synchronized preview and runtime proof. |
| SSF preservation | Core Workflow data authoring | **Preserved in core** | At least 28 named slots plus byte-exact unnamed retail tail entries; edits do not truncate tail. | UI must disclose tails; runtime event proof. |
| Archive ownership | Core Workflow packaging | **Stronger** | Nonempty unowned output is never replaced; success replaces prior owned tree atomically; failures roll back. | Native payload test run and retail package proof. |
| Archive readback | Core Workflow packaging | **Preserved structurally** | Exact resource identity/data readback through PyKotor. | Vanilla byte-structural comparison where applicable and retail load. |
| Override safety | Core Workflow packaging | **Stronger** | Stage-first, explicit conflict/backup, rollback/receipt, archive blocking. | UI composition, resource-type policy, TLK policy, retail test. |
| Portable project | Core Project/Workflow scripting project | **Stronger format** | Versioned typed relative paths, dependency metadata, extensions, path-escape blocking. | Formal schema version/migration policy and visible workflow. |
| Revisions | Core Project/Workflow scripting project | **Stronger base** | Immutable full-project snapshots materialize into a new directory without overwrite. | Asset-level browsing/diff and old history migration. |
| Legacy `project.json` and SQLite migration | Project migration workflow | **Missing** | None found. | Build a read-only importer for old project metadata, recents, script/quest/dialogue snapshots, export history, and preferences. Import into a new folder; never modify the old project/database. |
| Heavy-blob policy | Project/IO | **Preserved** | Project manifest references typed assets rather than embedding arbitrary large binary data. | Enforce project-size/role validation for all new pages. |
| Game-file validation | Validation + format-specific core | **Partial** | Parse/readback, resref validation, unknown-field preservation, transactions. | Retail K1/K2 proof and vanilla structural comparisons remain mandatory. |
| Embedded payload parity | Native payload manifests/generator/tests | **In progress** | Canonical root modules and native package destinations exist in the working tree. | Regenerate affected packages; run focused byte-identity, package registry, project manifest, and native build/startup tests. |

## Initial project/package gap matrix (historical audit evidence)

| User outcome | Current path | Status | Exact acceptance test |
|---|---|---|---|
| Create/open/save a scripting project | `NarrativeProjectService` and uncomposed Project page | **Unwired** | Native Debug app: create a project in an empty directory, add typed assets/dependencies, save, close, reopen, and compare the manifest and referenced bytes. |
| Open an old GhostScripter project | No importer | **Missing** | Copy a representative legacy project to a fixture, import into a new GhostStudio folder, and compare scripts/dialogues/quests/data/history/preferences. Source bytes and DB must remain unchanged. |
| Recover earlier work | Immutable revision service and uncomposed history page | **Unwired** | Create two revisions, mutate/delete assets, materialize the older revision to a new folder, and prove the original/current folders were not overwritten. |
| Build script/dialogue resources | Scripting studio build service | **Preserved structurally** | Block invalid document without changing output; build valid NSS/NCS/DLG; exact readback; deliberately inject a promotion failure and prove rollback. |
| Build quest/data resources | Data controller `resource_snapshots` plus package/project plumbing | **Partial** | Commit quest/JRL/2DA/globalcat/TLK/LIP/SSF documents, add all expected resources to a project/package once, reload and compare. No resource may be silently omitted. |
| Build ERF/MOD | Narrative packaging service and uncomposed Package page | **Unwired** | Build both extensions for K1/K2 fixtures, exact archive readback, install to a clean test location, then retail-load and exercise resources. |
| Build SAV | None | **Missing** | Implement dedicated safe save workflow or explicitly retire it with a documented replacement. |
| Stage Override | Narrative packaging service and uncomposed Package page | **Unwired** | Stage to a clean owned directory, inspect contents/conflicts, and prove the game directory was untouched. |
| Install Override | Narrative packaging service and uncomposed Package page | **Unwired** | Install only after explicit confirmation, back up each collision, produce a receipt, verify exact destination bytes, then roll back exactly. |
| Install TLK | No correct global-TLK policy | **Missing** | Back up the game-root `dialog.tlk`, install a validated replacement/patch with explicit game selection, retail-resolve a changed StrRef, and restore exactly. |
| Hand resources to Map Studio export | NCS/DLG staged resource map | **Partial** | Extend typed staging to every project resource required by the authored module and test that authored export contains each exact byte once. |
| Test in PIE | Map Studio PIE | **Partial** | Simulate only implemented semantics, keep “not KOTOR proof,” and verify unsupported script/action/dialogue behavior is visibly reported rather than faked. |
| Test in retail KOTOR | Existing module install/live-log/game harnesses | **Not yet performed for this integration** | Build through the visible GhostStudio workflow, install, manually warp/trigger, capture KotorMCP log, and verify no crash plus intended script/dialogue/quest/data behavior. Repeat the relevant fixture in K1 and K2. |

## Initial IPC/event gap matrix (historical audit evidence)

The legacy three-process contract used GhostRigger on port 7001, GhostScripter on 7002, and GModular on 7003. Bringing the UI into GhostStudio makes in-process signals preferable, but external tools may still rely on the old public endpoints. In-process replacement is not wire compatibility.

| Legacy contract | GhostStudio state | Status | Required compatibility decision/test |
|---|---|---|---|
| Port 7002 `ping` | No Scripting Studio server was found. Existing `ipc.client.ping_all()` still assumes a separate GhostScripter process. | **Missing** | Either provide a port-7002 compatibility shim owned by Automation or formally version/deprecate the endpoint. Test the legacy request/response shape. |
| Port 7002 `status` | No equivalent endpoint found. | **Missing** | Return current project/game/open-document/build state without blocking Qt. |
| Port 7002 `open_script` | In-process Map Studio deep-link exists; port-7002 route does not. | **Partial** | Compatibility shim must focus/open the integrated window and preserve resref/module context. Test from an external process. |
| Port 7002 `open_dlg` | In-process Map Studio deep-link exists; port-7002 route does not. | **Partial** | Same as above with DLG context and selected object binding. |
| Port 7002 `open_2da` | Core/page code exists but no visible composition or IPC route. | **Missing** | Compose the page and add external route with game/source context. |
| Port 7002 `open_tlk` | Core/page code exists but no visible composition or IPC route. | **Missing** | Compose the page and add external route with explicit game/root-TLK semantics. |
| Outbound port 7003 `script_compiled` | No sender found in GhostStudio IPC client. | **Missing** | Emit only after readback-valid compile; include game/resref/hash/output and failure state. Test with a stub server. |
| Outbound port 7003 `refresh_viewport` | `refresh_gmodular_viewport()` exists in the shared IPC client. | **Preserved for external GModular** | Focused stub-server test must verify payload/action and nonblocking failure behavior. |
| Outbound port 7001 `open_utc`, `open_utp`, `open_utd`, `open_mdl`, `ping` | GhostStudio’s port-7001 server implements these actions and many stronger state/scene/resource/MCP routes. | **Preserved/superseded** | Run IPC contract tests against a live native Debug app and correct product branding in responses (`GhostStudio`, not legacy `GhostRigger`) if branding is public. |
| Polling bridge and `model_complete` callback | No equivalent scripting integration callback found. | **Missing or obsolete** | Determine whether any supported external workflow consumes it. If yes, add a versioned event; if no, record deprecation and migration to current resource/scene events. |
| Internal script/DLG handoff | Qt signals and Map Studio staging | **Stronger in-process replacement** | Run map integration tests and visibly prove focus, context, invalidation, build, and return-to-map behavior. |
| General event bus | Existing Qt signals, IPC server, KotorMCP | **Distributed/partial** | Publish a documented narrative event contract for document opened/changed/saved, compile started/completed/failed, build promoted/rolled back, package installed, and runtime proof recorded. |

## Initial 60-tool gap inventory (historical audit evidence)

This inventory preserves the evidence and completion criteria recorded before
the compatibility pass. Current counts and ownership decisions are in the
authoritative post-integration tables above and in the live
`legacyGhostScripterCompatibility` report.

### Verification evidence keys

- **A-INV:** `tests/test_ghostscripter_automation_compat.py::test_readme_inventory_is_exactly_sixty_unique_names`
- **A-REG:** `tests/test_ghostscripter_automation_compat.py::test_all_callable_registry_names_are_registered_without_duplicates`
- **A-WRITE:** `tests/test_ghostscripter_automation_compat.py::test_all_legacy_writers_are_callable_through_safe_ghoststudio_contracts` plus the format-specific writer/readback and guarded-install cases in the same file.
- **A-DIRECT:** `tests/test_ghostscripter_automation_compat.py::test_direct_alias_dispatch_and_specialized_arguments`
- **A-REF:** `tests/test_ghostscripter_automation_compat.py::test_nwscript_reference_aliases_use_ghoststudio_compiler_definitions`
- **A-COMP:** `tests/test_ghostscripter_automation_compat.py::test_compile_and_decompile_aliases_return_readback_evidence`
- **A-VOICE:** `tests/test_ghostscripter_automation_compat.py::test_ssf_and_lip_read_aliases_use_lossless_core_documents`
- **A-2DA:** `tests/test_ghostscripter_automation_compat.py::test_two_da_changes_ini_alias_is_bounded_and_refuses_deletes`
- **A-REPORT:** `tests/test_ghostscripter_automation_compat.py::test_compatibility_report_tool_can_filter_machine_readable_rows`

All callable rows still require **A-INV + A-REG + A-REPORT**. “Callable” means the name dispatches; it does not imply retail engine acceptance.

### Installation and discovery (7)

| Legacy name | GhostStudio owner/equivalent | Status | Exact verification or blocker |
|---|---|---|---|
| `gsDetectInstallations` | Automation `detectInstallations` | **Callable alias** | A-DIRECT; compare K1/K2 discovered roots and missing-install diagnostics. |
| `gsLoadInstallation` | Automation `loadInstallation` | **Callable alias** | A-DIRECT; load each game and verify the selected installation state changes once. |
| `gsListResources` | Automation `listResources` | **Callable alias** | A-DIRECT; compare paginated type/source/resref rows against direct KotorMCP output. |
| `gsDescribeResource` | Automation `describeResource` | **Callable alias** | A-DIRECT; compare identity, source, type, size, and ambiguity diagnostics. |
| `searchResources` | Automation `kotor_search_resources` | **Callable alias** | A-DIRECT plus a K1/K2 multi-source result fixture. |
| `searchAll` | Automation `kotor_search_resources` with all sources | **Callable alias** | A-DIRECT; assert the adapter forces all resource locations and remains bounded. |
| `listResType` | Automation `listResources` resource-type adapter | **Callable alias** | A-DIRECT; assert legacy `restype` maps to `resourceTypes`. |

### Format readers (17)

| Legacy name | GhostStudio owner/equivalent | Status | Exact verification or blocker |
|---|---|---|---|
| `readGFF` | Automation `kotor_read_gff` | **Callable alias** | A-DIRECT; compare typed fields and unknown field metadata on K1/K2 fixtures. |
| `readDLG` | Automation `kotor_read_gff(restype=dlg)` | **Callable alias** | A-DIRECT plus dialogue contract tests for cycles, links, localized text, and unknown fields. |
| `readTwoDA` | Automation `kotor_read_2da` | **Callable alias** | A-DIRECT; compare labels/columns/cells including blanks and `****`. |
| `readTLK` | Automation `kotor_read_tlk` | **Callable alias** | A-DIRECT plus K1/K2 flags/sound/resref/trailing-byte fixture comparison. |
| `readJournal` | Automation `kotor_read_gff(restype=jrl)` | **Callable alias** | A-DIRECT plus WORD `End` and unknown-field JRL fixture. |
| `journalOverview` | Native KotorMCP command | **Callable native name** | A-REG; compare category/entry counts and StrRefs with direct JRL read. |
| `readSSF` | Automation adapter over `SoundSetDocument` | **Callable alias with partial response** | A-VOICE currently proves the 28 named slots only. Extend the response and test with `test_ssf_preserves_meaningful_retail_tail_entries_byte_exactly`; it must also report every unnamed retail tail entry without truncating it. |
| `readLIP` | Automation adapter over `LipDocument` | **Callable alias** | A-VOICE; compare duration and every `(time, shape)` keyframe. |
| `readPTH` | Automation `kotor_read_gff(restype=pth)` | **Callable alias** | A-DIRECT; compare nodes/connections to direct PyKotor parse. |
| `readLTR` | PyKotor `read_ltr` | **Partial** | Add bounded JSON representation and tests for every LTR table/block/character probability; then expose the name. |
| `readGUI` | Automation `kotor_read_gff(restype=gui)` | **Callable alias** | A-DIRECT; compare typed GUI GFF fields and nested controls. |
| `readSave` | `kotor_list_saves` + archive listing | **Partial** | Implement the legacy decoded save overview semantics, explicit game/save identity, corruption diagnostics, and non-mutating tests. |
| `readNCS` | Workflow `NWScriptReferenceService.inspect_ncs` adapter | **Callable alias** | A-COMP; require authoritative disassembly, original SHA, recovered-source status, and exact-recompile evidence. |
| `readVIS` | PyKotor `read_vis` below automation | **Partial** | Add bounded room/visibility JSON and round-trip comparison for K1/K2 modules; expose only after semantic parity. |
| `readIFO` | Automation `kotor_read_gff(restype=ifo)` | **Callable alias** | A-DIRECT; compare module identity, entry point, area list, and unknown fields. |
| `readWAV` | PyKotor/audio adapter | **Partial** | Add a standalone inspector response for codec/rate/channels/duration/loop metadata and decode errors; fixture-test KOTOR WAV variants. |
| `readTXI` | Texture/TXI resource pipeline | **Partial** | Add standalone metadata response preserving unknown directives/order where required; compare against renderer-consumed policy. |

### Targeted lookups (7)

| Legacy name | GhostStudio owner/equivalent | Status | Exact verification or blocker |
|---|---|---|---|
| `twoDALookup` | Automation `kotor_lookup_2da` | **Callable alias** | A-DIRECT; verify row label/index and named-column lookup, blanks, and missing rows. |
| `moduleOverview` | Automation `kotor_describe_module` | **Callable alias** | A-DIRECT; compare module parts/resource counts/areas against archive inspection. |
| `nwscriptSignature` | Workflow `NWScriptReferenceService.function` | **Callable alias** | A-REF; verify K1/K2 overload/parameter/return/description data. |
| `nwscriptCategories` | Workflow `NWScriptReferenceService.categories` | **Callable alias** | A-REF; compare category membership for both games. |
| `searchNWScript` | Workflow `NWScriptReferenceService.search_functions` | **Callable alias** | A-REF; verify name/description search, game separation, and bounded result count. |
| `getNWScriptDB` | Workflow `NWScriptReferenceService` | **Callable alias** | A-REF; verify pagination is stable and all functions/constants are eventually reachable. |
| `pathfindRoute` | Math `WalkmeshRuntime.route` | **Core-only** | Define WOK/module source identity, coordinate space, floor/face selection, and unreachable-route response; expose an MCP adapter and compare it with PIE routing fixtures. |

### Format writers (8)

| Legacy name | GhostStudio owner/equivalent | Status | Exact verification or blocker |
|---|---|---|---|
| `writeGFF` | Workflow `BlueprintGFFDocument` | **Callable bounded adapter** | A-WRITE; complete typed documents preserve field types and unknown structures, while ambiguous legacy field inference requires explicit `allowLossy=true`; serialized bytes are read back before return. |
| `writeDLG` | Workflow `ScriptingStudioService.dialogue_bytes` | **Callable bounded adapter** | A-WRITE plus dialogue contract tests; graph structure, imported source fidelity, and K2 `DisplayInactive` are verified on readback. Retail-trigger K1/K2 DLGs before claiming engine proof. |
| `writeTwoDA` | Workflow `TwoDADocument` | **Callable bounded adapter** | A-WRITE; V2.0 and V2.b outputs receive semantic table readback with bounded row/column/cell counts. |
| `writeERF` | Workflow `NarrativePackagingService.build_archive` | **Callable bounded adapter** | A-WRITE; builds in an isolated owned temporary output and compares every resource identity and byte after archive readback. Retail archive loading remains a separate gate. |
| `writeSSF` | Workflow `SoundSetDocument` | **Callable bounded adapter** | A-WRITE; named slots and bounded unnamed retail-tail entries survive semantic readback. Optional Override installation uses the explicit guarded install contract. |
| `writeLIP` | Workflow `LipDocument` | **Callable bounded adapter** | A-WRITE; ordered viseme timelines are validated and compared after readback. |
| `writePTH` | Scene `AuthoredPathGraph` and authored PTH writer | **Callable bounded adapter** | A-WRITE; finite points, bounded directed edges, graph validation, and exact semantic readback are required. Optional installation uses the guarded Override contract. |
| `writeOverride` | Workflow stage/inspect/install | **Callable guarded install** | A-WRITE; requires separate existing absolute workspace/game roots, matching executable plus `chitin.key`, literal confirmation, a block-or-backup conflict policy, owned staging, receipt, and exact destination readback. |

### Script operations (3)

| Legacy name | GhostStudio owner/equivalent | Status | Exact verification or blocker |
|---|---|---|---|
| `compileScript` | Workflow `ScriptingStudioService.compile_script` | **Callable alias** | A-COMP; parse-back evidence and diagnostics required. Add retail K1/K2 execution proof. |
| `decompileScript` | Workflow `ScriptingStudioService.decompile_ncs` | **Callable alias** | A-COMP; authoritative disassembly must always remain present and recovered source must state exactness. |
| `compileSummary` | Workflow compile diagnostics | **Callable alias** | A-COMP; compare success/failure, diagnostics, SHA, size, and readback status with `compileScript`. |

### Patching (1)

| Legacy name | GhostStudio owner/equivalent | Status | Exact verification or blocker |
|---|---|---|---|
| `twoDAChangesINI` | Workflow `TwoDADocument.export_changes_ini` | **Callable alias** | A-2DA; additionally run the emitted patch with the real supported patch installer and compare installed output. |

### Composite resources (17)

| Legacy name | GhostStudio owner/equivalent | Status | Exact verification or blocker |
|---|---|---|---|
| `getResource` | Automation `get_resource` | **Callable alias** | A-DIRECT; verify source priority, exact bytes/base64, type, and ambiguity errors. |
| `getQuest` | Automation `get_quest` | **Callable alias** | A-DIRECT; compare journal category/states/text and related identifiers. |
| `getNpc` | Raw UTC through `get_resource` | **Partial** | Add appearance.2da, heads/body/model, TLK, scripts, inventory, feats/classes, and resource provenance enrichment. Test representative human/alien/droid NPCs. |
| `getCreature` | Raw UTC through `get_resource` | **Partial** | Same enriched creature contract as `getNpc`, including model/headhook resolution and unknown fields. |
| `getScript` | Raw NSS/NCS + NCS inspector | **Partial** | Return one bounded composite containing source if present, authoritative NCS disassembly, hashes, compile status, and provenance. |
| `getArea` | Raw ARE/GIT + module description | **Partial** | Aggregate ARE/GIT/LYT/VIS/PTH/WOK identities, environment, objects, scripts, transitions, and missing/corrupt parts. |
| `getModule` | Automation `kotor_describe_module` | **Callable alias** | A-DIRECT; compare module identity/parts/resources/areas and duplicate resolution. |
| `getDoor` | Raw UTD through `get_resource` | **Partial** | Enrich appearance/model, TLK, scripts, transition destination, key/lock, conversation, and provenance. |
| `getPlaceable` | Raw UTP through `get_resource` | **Partial** | Enrich appearance/model, TLK, scripts, inventory/container state, conversation/puzzle variables, and provenance. |
| `getItem` | Raw UTI through `get_resource` | **Partial** | Enrich baseitems.2da, TLK, properties, icon/model, upgrade data, and provenance. |
| `getEncounter` | Raw UTE through `get_resource` | **Partial** | Enrich spawn entries, factions, scripts, geometry, difficulty, and referenced UTCs. |
| `getTrigger` | Raw UTT through `get_resource` | **Partial** | Enrich geometry, scripts, transition destination, TLK, key/flags, and provenance. |
| `getWaypoint` | Raw UTW through `get_resource` | **Partial** | Enrich map-note/TLK, tag/template, bearing/location, transition/use semantics, and provenance. |
| `getStore` | Raw UTM through `get_resource` | **Partial** | Enrich inventory/items, prices/markups, TLK, scripts, and provenance. |
| `getSound` | Raw UTS through `get_resource` | **Partial** | Enrich sound/resref set, WAV metadata, spatial/loop/random properties, volume/range, and provenance. |
| `getFaction` | Raw FAC through `get_resource` | **Partial** | Enrich faction names and full relation matrix with stable identities and validation. |
| `getBlueprint` | Raw typed GFF through `get_resource` | **Partial** | Add automatic blueprint type detection, resource-specific validation/enrichment, unknown-field metadata, and links to the correct GhostStudio editor. |

## Stronger GhostStudio systems that must remain

The merge must preserve these improvements even when closing legacy gaps:

1. **Honest NCS recovery:** authoritative disassembly and exact-recompile evidence are never hidden behind reconstructed source.
2. **Opaque DLG preservation:** unknown GFF fields survive safe edits, and topology mutation is blocked when preservation cannot be guaranteed.
3. **Transactional owned output:** failed validation/build/promotion never leaves mixed resources or overwrites an unowned directory.
4. **Stage-first Override installation:** conflicts, backups, rollback, and receipts are explicit.
5. **Portable typed project manifests:** relative references and dependency metadata replace an opaque machine-local project.
6. **Immutable project revisions:** recovery materializes to a new directory and cannot silently overwrite current work.
7. **Map Studio context and invalidation:** map-bound scripts/dialogues can deep-link into the workbench; editing invalidates stale staged bytes.
8. **3D module authoring:** Map Studio is a stronger GIT placement/editing destination than the old 2D browser.
9. **Broader automation:** GhostStudio’s KotorMCP includes live logging, input/warp support, module/model validation, and Ghidra-assisted diagnostics beyond the legacy 60-name surface.
10. **Theme/layout integration:** the scripting suite is a separate GhostStudio workbench and should remain uncluttered, theme-aware, and layout-aware.

## Remaining acceptance gates

The implementation gaps above are resolved by the authoritative preservation
table. Payload regeneration, the native build, and the six-theme visible
workbench proof are complete. The remaining gates are product and engine proof:

1. Complete a no-terminal user workflow: import an old project, edit a script,
   dialogue, quest, table, voice resource, and blueprint, then package and hand
   the resources to Map Studio.
2. Have the user run the final K1 and K2 retail tests. Execute the produced
   script, conversation, quest transition, TLK lookup, SSF/LIP event, and typed
   blueprint/module content; retain KotorMCP logs and hashes in export history.
3. Exercise emitted `changes.ini` through the supported real patch installer
   and compare the installed 2DA bytes/semantics to the requested edits.
4. Keep every compatibility writer bounded: typed GFF by default, validated
   dialogue/path documents, finite size limits, readback, and explicit guarded
   install roots. Do not weaken these adapters into arbitrary filesystem
   writers when adding future compatibility fields.

## Completed acceptance evidence

- All affected embedded-Python payloads were regenerated. The root manifest now
  covers 1,289 packaged files, and focused byte-identity/package checks pass.
- The isolated Debug x64 host rebuilt with 0 warnings and 0 errors, staged and
  audited 18/18 payload DLLs, and produced `GhostStudio.exe` with SHA-256
  `814A3D89A24193CA39D4B39356A3A0B9B9C9B66DBBEF39B07C317B611A56A98E`.
- The real rebuilt native shell opened the Scripting Suite through its visible
  command button. All 12 pages were captured under Default, Matrix, Droid,
  Dark, Light, and Classic: 72/72 visible states passed.
- The final exact staged-snapshot integration set passed 227 tests. Real K2 resource
  compatibility smokes also resolved `appearance.2da`, `tutorial_garage`, and
  the complete `207tel` module resource inventory.

## Required focused verification set

At minimum, the final integration should run the following targeted files, not a broad repository sweep:

- `tests/test_scripting_studio_service.py`
- `tests/test_dialogue_authoring_contract.py`
- `tests/test_scripting_dialogue_studio_ui.py`
- `tests/test_scripting_dialogue_full_fields_ui.py`
- `tests/test_scripting_reference_service.py`
- `tests/test_scripting_quest_scaffold.py`
- `tests/test_scripting_data_authoring.py`
- `tests/test_scripting_data_pages.py`
- `tests/test_scripting_project_packaging.py`
- `tests/test_scripting_project_package_pages_ui.py`
- `tests/test_map_studio_scripting_studio_integration.py`
- `tests/test_ghostscripter_automation_compat.py`
- Focused cases from `tests/test_native_python_payloads.py`, `tests/test_native_core_package_registry.py`, and native host startup/build contracts touched by this integration.

Visible checks are additionally required because headless widget construction does not prove that the native application exposes a usable workbench. Retail KOTOR execution is additionally required because PyKotor parsing does not prove Odyssey engine acceptance.

## Final preservation conclusion

The correct current claim is:

> GhostStudio now preserves every inventoried GhostScripter product system in a clean-room, standalone Scripting Suite workbench or through an explicitly stronger typed GhostStudio workflow. All sixty legacy MCP names are callable, including eight bounded mutation adapters serviced through validated owned workflows instead of arbitrary filesystem writers. Native visible acceptance is complete; retail K1/K2 execution remains required before claiming engine proof.

This permits retirement of the standalone authoring UI, but it does not claim
that PyKotor readback or PIE simulation proves retail Odyssey behavior.
