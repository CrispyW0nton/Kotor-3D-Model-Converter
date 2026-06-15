# GhostRigger IPC TODO

Last updated: 2026-06-05

This is the living backlog for finishing GhostRigger's IPC integration. Update it after each IPC slice lands so future work can start from the actual remaining gaps instead of re-scanning the whole application.

## Ground Rules

- Launch GhostRigger through `build\vs\x64\Release\GhostRiggerNative.exe` for UI and visual workflow verification. Do not launch `main.py` directly for app-level tests.
- For visual, viewport, theme, layout, startup, and workflow behavior, verify on screen. IPC/backend probes can support the work, but they do not replace visible testing.
- Use MCP/model-pipeline tools only for backend/game-file ground truth, not as a substitute for UI workflow testing.
- Prefer small IPC slices with targeted regression checks and one visible smoke path.
- Keep route behavior on the Qt/main-window side where it drives existing UI services, not duplicated in `src/ipc`.

## Current IPC Coverage

These routes already exist in `src/ipc/server.py` and have matching client helpers where useful.

- Health and shell state: `/api/ping`, `/api/health`, `/api/reload`, `/api/state`, `/api/capture_viewport`.
- Scene and model loading: `/api/load_model`, `/api/open_mdl`, `/api/open_utc`, `/api/open_utp`, `/api/open_utd`, `/api/new_scene`, `/api/open_scene`, `/api/save_scene`.
- Workbench and panel opening: `/api/show_panel`, `/api/open_tool`.
- Viewport/render controls: `/api/viewport_command`, `/api/appearance`, `/api/set_renderer_backend`, `/api/set_dummy_helpers`, `/api/set_light_helpers`, `/api/select_helper`.
- Current-model animation controls: `/api/animation_command`.
- Module mesh selection: `/api/select_module_mesh`.
- KMAX scene objects: `/api/create_scene_camera`, `/api/create_scene_light`, `/api/select_scene_object`, `/api/set_scene_object_visibility`, `/api/scene_object_command`, `/api/scene_object_properties`.
- Library/resource browsers: `/api/library_search`, `/api/library_select`, `/api/resource_search`, `/api/resource_select`.
- MCP proxy routes under `/mcp/*` exist for backend validation surfaces only.

## Done Recently

- [x] Native C++ launched IPC server startup from the Qt main-window composition layer.
- [x] Visual-QA routes for renderer switching, helper visibility/selection, module mesh selection, and viewport capture.
- [x] State readback for scene, selection, renderer/display, active model, animation, and dock visibility.
- [x] Appearance route for theme/layout changes and state readback.
- [x] Animation command route for current-model select/play/stop/loop/seek.
- [x] Content Browser search/select/load route pair.
- [x] Resource Browser search/select/activate route pair.
- [x] Scene object command route for select/focus/rename/duplicate/delete/lock/visibility.
- [x] Scene object property route for transforms and camera/light-specific fields.

## P0 - IPC Foundation

- [ ] Add a capabilities/discovery endpoint, either `/api/capabilities` or a stable section in `/api/state`, listing IPC schema version, available routes, route aliases, panels, tools, renderer backends, themes, layouts, and app version.
- [ ] Standardize route response envelopes. Several older routes return immediate `ok` for queued GUI work while newer routes return readback. Pick a consistent `status`, `message`, `data`, `error`, `operation_id` shape.
- [ ] Add a startup/readiness endpoint or explicit `/api/state` fields for app startup, content-library readiness, active workers, and busy/progress state.
- [ ] Add operation status readback for long-running GUI jobs, including library scans, imports, exports, lightmap bakes, render-frame jobs, retarget previews, and module builds.
- [ ] Add route-level validation helpers for stable errors on missing payload fields, invalid aliases, missing scene objects, missing output paths, and unavailable workbench state.
- [ ] Document the IPC protocol with examples for Python terminal helpers and external tools.
- [ ] Add a targeted native visual IPC smoke harness that launches `GhostRiggerNative.exe`, pings IPC, drives a small visible workflow, captures the viewport, and shuts down cleanly if supported.

## P1 - Main Shell and File Workflows

- [ ] Add path-based import routes for ASCII MDL, binary MDL/MDX, OBJ, FBX, and GLB/GLTF so IPC callers can bypass file dialogs while using the existing import workflows.
- [ ] Add path-based export routes for ASCII MDL, binary MDL, OBJ, FBX, selected FBX, GLB/GLTF, and humanoid template export.
- [ ] Add texture directory and resource-root settings routes with state readback.
- [ ] Add MDLOps integration routes for set path/status, compile ASCII to binary, decompile binary, port current model, and generate module files.
- [ ] Add model-info and diagnostics snapshot routes for current model summaries, renderer diagnostics, GPU upload stats, selected object summaries, and current warnings.
- [ ] Add log routes for tail, clear, search/filter, and export of the Output Log.
- [ ] Add settings routes for read/write/reset of app settings, renderer defaults, game directories, visual profiles, navigation profiles, and persistence behavior.
- [ ] Add FBX SDK status/setup routes for scan, test configuration, save, and clear.

## P1 - Viewport, Scene, and Selection

- [ ] Expand `/api/viewport_command` with explicit camera/view operations for named views, safe-frame toggles, render mode/shade mode readback, axis/reference mode, snapping, transform mode, and measurement controls.
- [ ] Add read/write IPC for transform type-in values, grid spacing, angle snap, percent snap, and unit/display settings.
- [ ] Add robust scene selection routes that can select by scene object id, object name, helper node path, light node path, skeleton node name, and module mesh name.
- [ ] Add skeleton/node panel routes for search, select, multi-select, visibility, transform edit, expand/collapse state, and selected node property readback.
- [ ] Add Scene Outliner-specific coverage for helper node selection, light node selection, object add-to-sequence, and hierarchy readback.
- [ ] Add Properties panel read/write coverage beyond scene-object properties: selected model metadata, character mode, node fields, module mesh rows, and common object fields.
- [ ] Add Adjust Pivot panel routes for pivot mode, center/reset/bake actions, pivot-only edits, and state readback.
- [ ] Add Mesh Tools panel routes for sub-object selection mode, selection conversion, attach/detach, weld/target weld, bridge, connect, cap border, delete, normal flip/recalculate, history undo/redo, and validation readback.

## P1 - Cameras, Lighting, Materials

- [ ] Expand camera IPC with set active/clear active, create from current view, align camera to view, align view to camera, duplicate/delete, lens/sensor/resolution/framing edits, and camera tree readback.
- [ ] Add render-frame IPC for path-based still rendering through the existing render-frame workflow, including camera id, resolution, transparent background, format, preview, and final output path.
- [ ] Expand lighting IPC with lighting mode, map toggles, lightmap settings, shader complexity mode, helper visibility, generated rig presets, per-light selection, per-light edits, and light hierarchy readback.
- [ ] Add lightmap baker IPC for bake settings, validation, start/cancel/progress, preview/apply/revert, output manifest path, and generated assignment readback.
- [ ] Add Sprite Materials IPC for sprite row query/select, class/render mode, opacity, cutoff, matte key, glow strength, save overrides, clear overrides, and selected scene-object override readback.
- [ ] Add Texture Tool and Normal Map IPC for opening source textures, previewing channels, generating normal maps, exporting generated textures, and applying texture outputs to selected model/materials.
- [ ] Add UV Viewer IPC for open/select mesh, capture/export UV preview, select UV island if supported, and geometry preview capture.

## P1 - Content and Resource Browsers

- [ ] Expand Content Browser IPC beyond search/select/load: scan, deep scan, extract, asset actions, batch actions, primary scene load, add to current scene, character builder handoff, retarget source/target handoff, and module editor import/new-module handoff.
- [ ] Expand Resource Browser IPC with scan/refresh, resource preview details, activated-resource result readback, blueprint/resource editor handoff, and 2DA table open/select.
- [ ] Add 2DA Browser IPC for refresh by game, list tables, select table, query rows, edit/save if the UI supports it, and visible selection readback.
- [ ] Add stable asset identity payloads for library/resource selections so callers can round-trip game, source, resref, extension, path, module, tags, and compatibility flags.

## P2 - Animation and Retargeting

- [ ] Expand current animation IPC with source switching, inheritance game/supermodel edits, animation library scan/refresh, available clip readback, and source preview controls.
- [ ] Add Retarget Workbench routes for source/target current model, source/target library selection, source/target game-library selection, external import by path, preview/apply/pause/stop, root-motion toggle, source animation playback, and profile load/save.
- [ ] Add retarget export IPC for preview/export paths and result artifact readback.
- [ ] Add Unreal Animator routes for source load, target FBX import, mapping refresh, frame source/target, preview/stop, bake animation, export FBX animation, reload animator code, selected bone readback, and mapping edits if supported.
- [ ] Add Sequence Editor routes for create/open/save sequence, add/remove scene object, bind/unbind tracks, create/edit keyframes, scrub/play/stop, export, and sequence state readback.

## P2 - Character, Rigging, and BAS

- [ ] Add Body Attachment System IPC for mode changes, slot selection, attach by slot/resref/path, clear slot, save build, load build if supported, and attachment state readback.
- [ ] Add Character Builder/Character Studio IPC for game/mode selection, head/body/equipment selection, workflow rail step, validation, preview animation, jump-to-section, launch/open selected asset, and export/build actions.
- [ ] Add Inspector/Character Studio IPC for guide placement, skeleton generation, template selection, hand/head rig actions, viseme calibration, attachment preview, validation/check model, ROM test, and fit adjustment fields.
- [ ] Add rigging IPC for quick autorig, remove rigging, rig window actions, weight stats, UE5 rig export, selected joint/weight state, and export result readback.

## P2 - Module Editor and Blueprint Workflows

- [ ] Add Module Editor IPC for new/open/save/save-as KMAP, import module, import selected library asset, export FBX, export scene package, validate, build module files, open output folder, and dirty/project state readback.
- [ ] Add Module Editor viewport/outliner routes for select item, transform item, duplicate/delete/rename, set visibility/locked, change view mode, change selection mode, and item hierarchy readback.
- [ ] Add Module Editor tab routes for rooms, blueprints, walkmesh, builder, porter, and validation actions exposed by the module editor panels.
- [ ] Add KMAP project state route for module metadata, rooms, assets, selected item, validation issues, export settings, and output paths.
- [ ] Add Blueprint Editor IPC for open/create blueprint, read/write fields, save, dirty state, validation, script/dialog handoff, and selected template readback.

## P2 - Cross-App IPC and External Tools

- [ ] Add configurable outgoing IPC targets for GhostScripter/GModular instead of hard-coded menu-only pings.
- [ ] Add outgoing IPC event/readback routes for ping status, blueprint saved notifications, GModular viewport refresh, and cross-app failure messages.
- [ ] Add route(s) for opening scripts/dialogs in GhostScripter with explicit target state readback.
- [ ] Add a compact IPC examples section to `CHEETSHEET.md` once user-pasteable commands are stable enough.
- [ ] Add a route matrix/checklist test that verifies route registration and client helper coverage without launching broad suites.

## Verification Backlog

- [ ] Native visible smoke: launch `GhostRiggerNative.exe`, verify `/api/health`, `/api/state`, `/api/open_tool`, `/api/show_panel`, `/api/capture_viewport`.
- [ ] Module visible smoke: load `K2:001ebo1` / `001EBO1`, test ModernGL and Direct3D/WGPU module mesh selection via viewport and Module Meshes panel.
- [ ] Animation visible smoke: load `N_DarthMalak`, select/play/loop `walk`, seek, stop, and capture viewport.
- [ ] Theme/layout visible smoke: cycle Default/native, Matrix, Droid, Dark, Light, and Classic through IPC and verify readable UI.
- [ ] Scene object smoke: create camera/light, edit properties, select/focus/duplicate/delete, and verify Scene Outliner, Camera panel, Lighting panel, and viewport agree.

