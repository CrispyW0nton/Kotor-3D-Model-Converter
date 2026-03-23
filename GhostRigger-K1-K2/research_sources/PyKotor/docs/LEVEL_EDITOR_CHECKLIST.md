# Module Designer: All-In-One Level Editor Feature Checklist

Comprehensive feature roadmap for transforming the Module Designer into a Unity/UE5/Hammer-class level editor for KotOR modules.

**Philosophy**: Merge the Indoor Builder, Walkmesh Editor, and current Module Designer into a **single unified environment** where all level editing tasks happen in one canvas with contextual modes.

---

> **Scope rule for this doc**: Only keep ideas that translate into concrete changes in the existing Module Designer implementation: [Tools/HolocronToolset/src/toolset/gui/windows/module_designer.py](Tools/HolocronToolset/src/toolset/gui/windows/module_designer.py) and [Tools/HolocronToolset/src/ui/windows/module_designer.ui](Tools/HolocronToolset/src/ui/windows/module_designer.ui).

> **Current Module Designer baseline (verified)**: 3D OpenGL viewport (`mainRenderer`) + 2D walkmesh renderer (`flatRenderer`) stacked; left panel has `resourceTree` and `lytTree` + room transform spinboxes; right panel is a flat `instanceList`; per-type visibility toggles; QUndoStack; Blender integration.

### What other editors do better (and what we should actually implement here)

| Capability to Steal | Why It Matters in Our UI | Implement In Module Designer |
|---|---|---|
| **Explicit tool/mode state** (select / transform / place / walkmesh edit) | Our interaction is currently implicit and hard to reason about | Add a small tool palette/toolbar in the UI; add a state machine in `module_designer.py` that routes mouse events differently by mode |
| **Transform gizmos** (translate/rotate/scale + axis lock) | Dragging without gizmos is imprecise; no discoverable affordance | Render gizmos in `mainRenderer`; connect gizmo drag → `MoveCommand`/`RotateCommand` and update Blender sync |
| **Inspector dock** (inline property editing for selection) | Right now properties live in separate dialogs; slow for iteration | Add a dock/panel that populates from selected `GITInstance` (and from selected walkmesh face when in Walkmesh Mode) |
| **Hierarchy + search + grouping** (rooms → instances, folders/layers) | `instanceList` doesn’t scale; no structure; no search | Replace `instanceList` with a tree view grouped by room + type; add search filter; add user-defined groups (visgroups/layers) |
| **Drag-and-drop placement from resources** | Resource tree is browse-only; placement is friction | Enable `resourceTree` drag; accept drops in `mainRenderer`; create a ghost preview and place via walkmesh raycast |
| **Surface/grid/angle snapping** (editor-side helpers) | We place/drag with no snap; alignment is painful | Add snap settings + indicators; apply snapping inside the 3D controls when moving/placing instances |
| **Walkmesh edit in the 3D viewport** (vertex/edge/face selection) | We can render walkmesh but can’t edit it in-place | Add Walkmesh Mode that switches raycast targets to BWM geometry; add selection highlights + edit operations |
| **Walkmesh face properties panel** (surfacemat + walk flags) | We don’t expose per-face editing; this is core functionality | Add a `walkmeshTab` (or inspector section) showing surfacemat + walk/walkCheck/lineOfSight and writes back to BWM |
| **VIS editor tab** (room-to-room visibility matrix + viz) | VIS is a core KotOR format; current workflow is a hack | Add `visTab` with a matrix editor and in-viewport visualization of links |
| **Camera: orbit + fly + speed + bookmarks** | Navigation is a productivity multiplier | Extend the existing controls to support both orbit and fly navigation; expose speed + bookmark slots in UI |
| **Multi-view layout option** (orthographic helpers) | Precise alignment is hard with a single view | Provide a toggle that swaps the render area into a 4-pane splitter with perspective + orthographic views |
| **Validation + build/test loop** (errors surfaced early) | We save GIT but don’t help the user ship a playable module | Add “Check for Problems” (broken resrefs, missing models, degenerate faces) and a “Build & Launch” action |

### Source mapping (only for attribution of the idea)
- **Creation Kit**: navmesh edit mode in-viewport, reference browser/filtering, layers, VIS-like occlusion mindset.
- **Dragon Age Toolset**: tight 2D (layout) + 3D (preview/placement) integration, trigger region drawing workflow.
- **Unity/Unreal**: inspector+hierarchy workflow, gizmos, drag/drop placement, snapping, scene organization.
- **Hammer/Radiant**: multi-view precision layouts, error checking pipeline mindset.
- **Blender**: edit-mode mental model for vertex/edge/face manipulation.
- **Forge**: KotOR-specific proof that 3D walkmesh editing + object placement is viable and already implemented elsewhere.
- [ ] **Layer definitions**: User-defined layers (e.g., "Enemies", "Loot", "Scripted")
- [ ] **Layer assignment**: Assign objects to layers
- [ ] **Layer filtering**: Toggle entire layer visibility
- [ ] **Layer locking**: Lock all objects in a layer

---

## 🔍 Inspector Panel (Unity Inspector analog)

### Object Properties Editor
- [ ] **Transform**: Position (X/Y/Z), Rotation (Euler/Quaternion), Scale
- [ ] **Blueprint fields**: All UTC/UTD/UTP/etc. GFF fields editable inline
- [ ] **Scripts dropdown**: Assign OnSpawn/OnDeath/etc. scripts via file picker
- [ ] **Tags/Comments**: User metadata for organization
- [ ] **Preview thumbnail**: Show 3D model miniature for selected object
- [ ] **Resource link**: Click to open blueprint in dedicated editor

### Walkmesh Face Properties (when face selected in Walkmesh Mode)
- [ ] **Surface Material**: Dropdown from surfacemat.2da
- [ ] **Walkable flags**: walk, walkCheck, lineOfSight (checkboxes)
- [ ] **Adjacent faces**: List of neighboring face indices
- [ ] **Face normal**: Display as read-only vector
- [ ] **Area (m²)**: Display face surface area

### Room Properties (when room selected in Layout Mode)
- [ ] **Model**: Resref dropdown with preview
- [ ] **Position/Rotation**: Transform in LYT coordinates
- [ ] **Linked rooms**: VIS visibility list (editable checkboxes)
- [ ] **Ambient light**: Color picker + intensity slider
- [ ] **Fog settings**: Color, near/far distances

---

## 🧰 Asset Browser (Unity Project Window analog)

### Resource Explorer Integration
- [ ] **Searchable asset library**: All game + mod resources indexed
- [ ] **Type filters**: UTC, UTD, UTP, MDL, TGA, WAV, etc.
- [ ] **Thumbnail previews**: Auto-generate for models/textures
- [ ] **Favorites**: Star frequently-used blueprints
- [ ] **Recent files**: Quick access to last 20 opened resources
- [ ] **Drag-and-drop**: Drag blueprint from browser into 3D viewport to place

### Kit/Prefab System (Unity Prefab analog)
- [ ] **Kit browser**: Visual grid of indoor kits with thumbnails
- [ ] **Prefab groups**: Save multi-object arrangements as reusable prefabs
- [ ] **Prefab variants**: Override properties on placed instances

---

## 🎨 Material & Texture System

### Texture Browser (Hammer-style)
- [ ] **Grid view**: All TGA/TPC textures with previews
- [ ] **Search/filter**: By name, folder, resolution
- [ ] **Apply to selection**: Select faces/objects and apply texture
- [ ] **Texture alignment tools**: Offset, scale, rotation per face

### Material Editor (UE5 Material Editor lite)
- [ ] **Shader preview**: Show how texture will look in-game
- [ ] **Tint color overlay**
- [ ] **Transparency/Alpha settings**
- [ ] **Emissive glow** for self-lit textures

---

## ⚙️ Build Pipeline & Export

### Module Build Settings
- [ ] **Target game**: K1/K2 toggle with format conversion warnings
- [ ] **Compression**: Toggle ERF compression
- [ ] **Validation**: Pre-build checks (missing textures, broken scripts, etc.)
- [ ] **Build log**: Detailed step-by-step output window
- [ ] **Quick test**: Build + launch game at module entry point

### Export Options
- [ ] **Export current area to .mod**: Standalone module file
- [ ] **Export individual resources**: LYT, VIS, ARE, GIT, WOK files separately
- [ ] **Export screenshot**: High-res render of current viewport for documentation

---

## 📐 Editing Tools (Hammer/Radiant-inspired)

### Geometry Tools
- [ ] **Vertex merge**: Weld nearby vertices (for cleaning up walkmeshes)
- [ ] **Face split**: Subdivide selected face into triangles
- [ ] **Edge flip**: Flip shared edge between two triangles
- [ ] **Extrude**: Pull face outward to create new geometry (for walkmesh extensions)
- [ ] **Bevel**: Round edges of selected faces

### Measurement Tools
- [ ] **Distance ruler**: Click-to-measure between two points
- [ ] **Area calculator**: Select faces to see total walkable area
- [ ] **Angle display**: Show angles between edges/faces

### Snapping System (Unity-standard)
- [ ] **Grid snapping**: Snap position to grid increments (configurable 0.1/0.5/1.0 units)
- [ ] **Vertex snapping**: Hold V to snap to nearest vertex (Hammer-style)
- [ ] **Surface snapping**: Drop object onto walkable surface below cursor
- [ ] **Rotation snapping**: Snap rotation to 15°/30°/45°/90° increments

---

## 🎬 Preview & Testing

### In-Editor Playback
- [ ] **Animation preview**: Play room/object animations in viewport
- [ ] **Walkmesh collision test**: Drop a test sphere to see walkable paths
- [ ] **Camera path preview**: Scrub through camera movements
- [ ] **Trigger visualization**: Show trigger volumes as colored wireframe boxes

### Quick Launch
- [ ] **Build + Launch**: One-click build .mod and boot game to test
- [ ] **Warp code generation**: Auto-generate cheat codes for testing
- [ ] **Spawn test NPCs**: Place dummy creatures for scale reference

---

## 🔗 Integration with Existing Toolset Features

### Cross-Editor Workflow
- [ ] **Double-click object**: Opens blueprint in dedicated editor (UTC/UTD/etc.)
- [ ] **Script editor integration**: Right-click script field → "Edit in NSS Editor"
- [ ] **Dialog editor link**: Right-click creature → "Edit Dialog"
- [ ] **2DA editor link**: Right-click dropdown → "Edit 2DA Entry"

### Data Synchronization
- [ ] **Live blueprint updates**: When blueprint edited externally, refresh in viewport
- [ ] **Conflict resolution**: Warn if external changes conflict with unsaved module edits
- [ ] **Version control hints**: Show Git status icons on modified resources

---

## 🌐 Multiplayer/Collaboration (Future)

- [ ] **Live co-editing**: Multiple users edit same module (à la Google Docs)
- [ ] **Change highlighting**: See other users' cursors + selections
- [ ] **Voice chat integration**: Optional VOIP for design discussions
- [ ] **Version history**: Rollback to previous module states

---

## 📊 Performance & Optimization

### Scene Optimization Tools
- [ ] **Face count display**: Show triangle count per room/object
- [ ] **Texture memory usage**: Warn if too many high-res textures loaded
- [ ] **Walkmesh complexity analyzer**: Suggest simplification for over-dense meshes
- [ ] **Vis optimization**: Auto-suggest VIS relationships based on occlusion

### Editor Performance
- [ ] **LOD system**: Distant objects render as bounding boxes (Unity-style)
- [ ] **Frustum culling**: Don't render objects outside camera view
- [ ] **Lazy loading**: Load room models on-demand when visible
- [ ] **Background processing**: Compile/build on separate thread

---

## 🎨 UI/UX Enhancements

### Theme System
- [ ] **Dark mode** (default)
- [ ] **Light mode**
- [ ] **High contrast mode** (accessibility)
- [ ] **Custom color schemes**: User-defined workspace colors

### Dockable Panels (Unity-style)
- [ ] **Drag-and-drop panel arrangement**: Rearrange Inspector/Hierarchy/Browser
- [ ] **Save layouts**: Workspace presets (e.g., "Walkmesh Editing", "Object Placement")
- [ ] **Pop-out panels**: Undock panels to external windows (multi-monitor)

### Keyboard Shortcuts (Unity-standard)
- [ ] **Q**: Pan tool
- [ ] **W**: Move tool
- [ ] **E**: Rotate tool
- [ ] **R**: Scale tool
- [ ] **F**: Focus on selection
- [ ] **Delete**: Delete selected objects
- [ ] **Ctrl+D**: Duplicate
- [ ] **Ctrl+Z/Y**: Undo/Redo
- [ ] **Ctrl+S**: Save
- [ ] **Space**: Toggle mode (Layout/Object/Walkmesh)
- [ ] **Alt+LMB**: Orbit camera
- [ ] **Alt+RMB**: Zoom camera
- [ ] **Alt+MMB**: Pan camera

---

## 🧪 QA & Debug Tools

### Debug Visualization
- [ ] **Wireframe overlay**: Show polygon edges on shaded models
- [ ] **Normals display**: Show vertex/face normals as directional arrows
- [ ] **UV map display**: Show texture coordinates
- [ ] **Collision shapes**: Highlight DWK/PWK walkmeshes in different colors
- [ ] **Path visualization**: Show PTH connections as bezier curves
- [ ] **Sound radius**: Show UTS max distance as wireframe sphere
- [ ] **Trigger polygons**: Highlight encounter/trigger zones in translucent color

### Error Detection
- [ ] **Missing texture warnings**: Red checkerboard on missing materials
- [ ] **Broken script references**: Yellow warning icon on invalid ResRef
- [ ] **Overlapping geometry**: Detect Z-fighting faces
- [ ] **Degenerate triangles**: Warn about zero-area faces in walkmesh
- [ ] **Unreachable areas**: Show walkmesh islands not connected to rest

---

## 📚 Documentation & Help

### In-Editor Help
- [ ] **Tooltips**: Hover over every button/field for explanation
- [ ] **Mode tutorials**: First-time popups explaining each mode
- [ ] **Video tutorials**: Embedded YouTube links for complex workflows
- [ ] **Shortcuts cheat sheet**: Press F1 to show modal with all hotkeys

### Templates & Examples
- [ ] **Starter templates**: Empty module, single-room test, outdoor test
- [ ] **Example modules**: Pre-built demos showing best practices
- [ ] **Asset pack browser**: Download community kits/prefabs

---

## 🚀 Next-Gen Features (Long-Term Vision)

- [ ] **AI-assisted placement**: "Place 5 enemies in this room" → Auto-distributes
- [ ] **Procedural generation**: Randomize room layouts from seed
- [ ] **Blender bridge**: Live-sync with Blender for advanced modeling
- [ ] **VR editing**: Edit levels in VR headset (à la Unreal VR Mode)
- [ ] **Cloud rendering**: Offload lightmap baking to remote server
- [ ] **Voice commands**: "Add a door here" → Hands-free editing

---

## 🏁 Immediate Priorities (Merge Plan Alignment)

Based on the Forge merge plan, these are the **critical path** items to implement first:

### Implementation Log (Phase 1)

| File | Change | Status |
|---|---|---|
| `module_designer.ui` | Added mode selector (QLabel + QComboBox "modeSelector" with Object/Layout/Walkmesh + separator) | ✅ Done |
| `module_designer.ui` | Added `layoutTab` ("Indoor") with kit/module selectors, component lists, options, build button | ✅ Done |
| `module_designer.ui` | Added `walkmeshTab` ("Walkmesh") with paint controls, material list, face properties | ✅ Done |
| `module_designer.ui` | Added `visTab` ("VIS") with visMatrix tree widget, set all / clear all buttons | ✅ Done |
| `module_designer.ui` | Added `IndoorMapRenderer` to splitter (starts hidden), registered as custom widget | ✅ Done |
| `module_designer.py` | Added `EditorMode` enum (OBJECT=0, LAYOUT=1, WALKMESH=2) | ✅ Done |
| `module_designer.py` | Added indoor builder state to `__init__` (IndoorMap, kits, paint state, ModuleKitManager) | ✅ Done |
| `module_designer.py` | Added `_on_mode_changed` + `_apply_mode_visibility` (show/hide renderers + tabs per mode) | ✅ Done |
| `module_designer.py` | Added `_setup_indoor_kits` / `_setup_indoor_modules` / `_setup_indoor_signals` | ✅ Done |
| `module_designer.py` | Added `_populate_walkmesh_material_list` with colored swatches | ✅ Done |
| `module_designer.py` | Added kit/module selection handlers, paint toggle, build handler | ✅ Done |
| `module_designer.py` | Added indoor renderer event stubs (mouse moved/pressed/released/scrolled) | ✅ Done |
| `module_designer.py` | Port room operations: place, delete, duplicate, merge, rotate, flip | ✅ Done |
| `module_designer.py` | Port clipboard: cut/copy/paste rooms with walkmesh overrides | ✅ Done |
| `module_designer.py` | Port right-click context menu (room/hook actions, rotate/flip sub-menus) | ✅ Done |
| `module_designer.py` | Port renderer signals: rooms_moved, rooms_rotated, warp_moved | ✅ Done |
| `module_designer.py` | Added `_initialize_indoor_options` (sync UI checkboxes to renderer state) | ✅ Done |
| `module_designer.py` | Connected `customContextMenuRequested` signal for indoor context menu | ✅ Done |
| `module_designer.py` | Port walkmesh paint stroke logic (`_begin/_apply/_finish_indoor_paint_stroke`, `_current_indoor_material`) | ✅ Done |
| `module_designer.py` | Port scroll-wheel handling (zoom, drag rotation, placement rotation) | ✅ Done |
| `module_designer.py` | Port `_cancel_all_indoor_operations` (marquee, drag, paint, placement cancel) | ✅ Done |
| `module_designer.py` | Port Layout mode status bar updates (`_update_indoor_status_bar`) | ✅ Done |
| `module_designer.py` | Port view navigation helpers (`_indoor_reset_view`, `_indoor_center_on_selection`, `_indoor_add_connected_to_selection`) | ✅ Done |
| `module_designer.py` | Port extra keyboard shortcuts (P=paint toggle, Home/Ctrl+0=reset view, F5=refresh, Ctrl+S/N/O=file I/O) | ✅ Done |
| `module_designer.py` | Port indoor file I/O (`_indoor_new`, `_indoor_open`, `_indoor_save`, `_indoor_save_as`) | ✅ Done |
| `module_designer.py` | Moved `PaintWalkmeshCommand` and `ZOOM_WHEEL_SENSITIVITY` from TYPE_CHECKING to runtime imports | ✅ Done |
| `module_designer.py` | Connected `sig_mouse_double_clicked` in `_setup_indoor_signals` for connected selection | ✅ Done |
| `module_designer.py` | Added `_on_indoor_mouse_double_clicked` handler (double-click room → add connected rooms to selection) | ✅ Done |
| `module_designer.ui` | Replaced `QListWidget instanceList` with `QWidget instancePanel` → `QVBoxLayout` → `QLineEdit instanceSearchEdit` + `QTreeWidget instanceTree` | ✅ Done |
| `uic/module_designer.py` | Updated UIC Python file to match: `instancePanel`, `instanceSearchEdit` (placeholder + clear), `instanceTree` (headerHidden, ExtendedSelection, CustomContextMenu) | ✅ Done |
| `module_designer.py` | Rewrote `rebuild_instance_list` to build hierarchical QTreeWidget grouped by GIT type (Creatures, Placeables, Doors, etc.) with item counts | ✅ Done |
| `module_designer.py` | Added `_filter_instance_tree(text)` — live search filter that shows/hides tree items and groups | ✅ Done |
| `module_designer.py` | Updated `select_instance_items_on_list` to iterate QTreeWidget (group → child traversal) | ✅ Done |
| `module_designer.py` | Updated `on_instance_list_single_clicked` / `double_clicked` / `get_git_instance_from_highlighted_list_item` / `on_instance_list_right_clicked` for QTreeWidgetItem API | ✅ Done |
| `module_designer.py` | Updated signal connections: `instanceTree.clicked/doubleClicked/customContextMenuRequested` + `instanceSearchEdit.textChanged` | ✅ Done |
| `module_designer.py` | Updated `_apply_mode_visibility` to use `instancePanel.setVisible` | ✅ Done |
| `designer_controls.py` | Added 2D→3D camera sync: `snap_camera_to_selected` in 2D controls also snaps 3D `mainRenderer` camera | ✅ Done |
| `designer_controls.py` | Added 3D→2D camera sync: `move_camera_to_selected` in 3D controls also snaps 2D `flatRenderer` camera | ✅ Done |

### Implementation Log (Phase 2+ UX — Session 6)

| File | Change | Status |
|---|---|---|
| `module_designer.ui` | Added `resourceSearchEdit` QLineEdit above `resourceTree` in `resourceTabLayout` (DA Toolset-style filter) | ✅ Done |
| `uic/module_designer.py` | Added matching `resourceSearchEdit` with placeholder text and clear button | ✅ Done |
| `module_designer.py` | Connected `resourceSearchEdit.textChanged` → `_filter_resource_tree`; added `_filter_resource_tree(text)` for live resource tree filtering | ✅ Done |
| `module_designer.py` | Added `EditorTool` enum (SELECT=0, MOVE=1, ROTATE=2) after `EditorMode` | ✅ Done |
| `module_designer.ui` | Added checkable tool QPushButtons (`toolSelectBtn`/`toolMoveBtn`/`toolRotateBtn`) + `toolSeparator` in toolbar | ✅ Done |
| `uic/module_designer.py` | Added matching 3 tool QPushButtons (checkable, Select checked by default) + VLine separator | ✅ Done |
| `module_designer.py` | Added `_setup_tool_buttons()` — creates QButtonGroup for mutual exclusivity, connects clicked signals | ✅ Done |
| `module_designer.py` | Added `_set_active_tool(tool)` — switches active tool, updates button checked state, shows status message | ✅ Done |
| `module_designer.py` | Added `_active_tool` state in `__init__`, tool visibility toggle in `_apply_mode_visibility` (hidden in Layout mode) | ✅ Done |
| `module_designer.py` | Added `_handle_object_mode_key_press(e)` — handles keyboard shortcuts for Object/Walkmesh modes | ✅ Done |
| `module_designer.py` | Q/W/E hotkeys → switch to Select/Move/Rotate tool, F → focus selected, Z → cycle viewport shading | ✅ Done |
| `module_designer.py` | Delete/Backspace → delete selected instances in Object mode | ✅ Done |
| `module_designer.py` | Camera bookmarks: Ctrl+1..9 saves, 1..9 recalls (stores x,y,z,pitch,yaw,distance) with 2D sync | ✅ Done |
| `module_designer.py` | Added `_cycle_viewport_shading()` — toggles lightmapCheck between Lightmapped/Solid + status message | ✅ Done |
| `module_designer.py` | Added `_save_camera_bookmark(slot)` / `_recall_camera_bookmark(slot)` with 2D flatRenderer sync | ✅ Done |
| `module_designer.py` | Added persistent status bar (`_setup_status_bar`) — permanent Mode / Tool / Selection labels, updated on mode/tool/selection changes | ✅ Done |
| `module_designer.py` | Added `duplicate_selected_instances()` — deep-copies selected GIT instances with (0.5, 0.5, 0) offset, adds to GIT, syncs Blender | ✅ Done |
| `module_designer.py` | Added Ctrl+D (duplicate) and Space (cycle editor mode) hotkeys in `_handle_object_mode_key_press` | ✅ Done |
| `module_designer.py` | Added camera HUD overlay (`_setup_camera_hud`) — translucent QLabel on mainRenderer showing real-time X/Y/Z/Pitch/Yaw/Distance, updated every 200ms | ✅ Done |
| `module_designer.ui` | Added snap controls: `snapCheck` (QCheckBox), `snapSizeSpin` (QDoubleSpinBox 0.05-10m), `rotSnapCheck`, `rotSnapDegreeSpin` (1-90°), `snapSeparator` | ✅ Done |
| `uic/module_designer.py` | Added matching snap controls + separator in toolbar | ✅ Done |
| `module_designer.py` | Added `_snap_to_grid(value)` / `_snap_rotation(degrees)` helpers; wired grid snap into `move_selected`, rotation snap into `rotate_selected` | ✅ Done |
| `module_designer.py` | Added G key toggles grid snap, snap controls hidden in Layout mode via `_apply_mode_visibility` | ✅ Done |

### Implementation Log (Phase 2+ UX — Session 7)

| File | Change | Status |
|---|---|---|
| `designer_controls.py` | Modified `ModuleDesignerControls3d.on_mouse_moved` to gate instance-drag on `_active_tool`: SELECT tool blocks all instance manipulation; ROTATE tool redirects left-drag to rotation instead of XY move | ✅ Done |
| `module_designer.ui` | Added `propertiesGroup` QGroupBox (with QFormLayout) to `instancePanel`: ResRef/Type read-only labels, X/Y/Z QDoubleSpinBoxes, Bearing QDoubleSpinBox, "Open Blueprint" QPushButton | ✅ Done |
| `uic/module_designer.py` | Added matching `propertiesGroup`, `propResRefValue`, `propTypeValue`, `propXSpin`, `propYSpin`, `propZSpin`, `propBearingSpin`, `propOpenBlueprintBtn` widgets wired into `instancePanelLayout` | ✅ Done |
| `module_designer.py` | Added `_setup_properties_panel()` — wires spinbox `valueChanged` + button `clicked` signals, initialises `_inspector_updating` guard | ✅ Done |
| `module_designer.py` | Added `_update_properties_panel()` — refreshes inspector fields from `selected_instances[0]`: resref, type‑name, XYZ position, bearing in degrees; disables bearing spinbox for non-bearing instance types | ✅ Done |
| `module_designer.py` | Added `_on_inspector_position_changed()` — pushes `MoveCommand` to undo stack when XYZ spinboxes edited, invalidates scene cache | ✅ Done |
| `module_designer.py` | Added `_on_inspector_bearing_changed()` — updates `instance.bearing` (radians) from bearing spinbox, invalidates scene cache | ✅ Done |
| `module_designer.py` | Added `_on_inspector_open_blueprint()` — calls `edit_instance()` for selected instance from inspector "Open Blueprint" button | ✅ Done |
| `module_designer.py` | Called `_update_properties_panel()` at end of `set_selection()` so inspector auto-syncs on every selection change | ✅ Done |
| `module_designer.py` | Fixed `on_instance_list_double_clicked` to also call `edit_instance(instance)`, opening the blueprint editor on double-click (previously only focused/selected) | ✅ Done |
| `module_designer.py` | Added `_RESTYPE_TO_GIT_CLASS` module-level dict mapping `ResourceType.UTC/UTP/UTD/UTW/UTS/UTE/UTT/UTM` → GIT instance classes | ✅ Done |
| `module_designer.py` | Added `_setup_resource_dnd()` — enables `resourceTree.setDragEnabled(True)` + `DragOnly`, sets `mainRenderer.setAcceptDrops(True)`, installs self as event filter | ✅ Done |
| `module_designer.py` | Added `eventFilter(obj, event)` — handles `DragEnter`/`DragMove`/`Drop`/`DragLeave` events on `mainRenderer`; accepts drop when `_dragged_resource` is set | ✅ Done |
| `module_designer.py` | Added `_handle_resource_drop(resource, screen_pos)` — maps resource type to GIT class, resolves world position via `screen_to_world_from_depth_buffer` (with cursor fallback), pre-sets resref, calls `add_instance()` | ✅ Done |
| `module_designer.py` | Added `QAbstractItemView` + `QEvent` to runtime imports | ✅ Done |

1. ~~Integrate indoor builder room-layout logic into `module_designer.py` as "Layout Mode"~~ ✅ **DONE** — EditorMode enum, mode selector combo, `_on_mode_changed`, `_apply_mode_visibility`, indoor state in `__init__`, kit/module selectors, indoor renderer wired up
2. Retire standalone `indoor_builder.ui` — _deferred until all builder.py logic fully ported_
3. ~~Add mode selector toolbar (Layout/Object/Walkmesh/Lighting/Terrain/NavMesh)~~ ✅ **DONE** — Mode selector combo in toolbar with Object/Layout/Walkmesh modes; tab visibility toggles per mode
4. Port 3D room placement with doorhook snapping to Module Designer — _partially done: IndoorMapRenderer embedded + signals connected; snap checkboxes wired; full placement flow needs more builder.py migration_
5. **3D room preview**: Render full textured rooms in viewport during placement

### Phase 2: Walkmesh Editing (Forge Port + Creation Kit Navmesh analog)
1. Implement face/vertex/edge raycast picking in `ModuleRenderer`
2. Add vertex drag gizmo (OpenGL translation handles with snap-to-grid)
3. Create `walkmeshTab` in left panel with material/flag inspector
4. Port normal arrow visualization (per-face directional indicators)
5. Add perimeter edge highlighting (boundary detection)
6. **Walkmesh toolbar**: Face/Vertex/Edge mode switcher (Creation Kit-style)

### Phase 3: VIS Editor (Creation Kit Cell Visibility analog)
1. Add `visTab` with room-to-room visibility checkbox matrix
2. Replace `set_all_visible()` with granular per-room control
3. Visualize VIS relationships as colored connection lines in 3D viewport
4. **Auto-VIS generation**: Analyze room adjacency and doorhook connections to suggest optimal VIS
5. **Occlusion testing**: Preview in-game visibility from selected room's perspective

### Phase 4: Scene Graph & Object Placement (Unity Hierarchy + Creation Kit Render Window)
1. ~~Build hierarchical scene tree (Unity-style Hierarchy panel)~~ ✅ **DONE** — Replaced flat `QListWidget instanceList` with `QTreeWidget instanceTree` grouped by GIT type (Creatures, Placeables, Doors, etc.) with item counts + search filter `QLineEdit`
2. Implement blueprint browser drag-and-drop into 3D viewport
3. Add transform gizmos (translate/rotate/scale) with axis locking
4. Support all 11 GIT object types with property inspector
5. **Alignment tools**: Snap to other objects, align to center/edges, distribute evenly
6. **Group selection**: Create temporary groups for batch transforms

### Phase 5: Multi-View & Camera (Hammer 4-panel layout)
1. Add 4-panel layout (Top/Front/Side/Perspective orthographic views)
2. Implement Unity/Creation Kit camera controls (WASD flythrough, Alt+LMB orbit, MMB pan)
3. ~~Add camera bookmarks (Ctrl+1-9 to save, 1-9 to recall — Creation Kit-style)~~ ✅ **DONE** — Ctrl+1..9 saves, 1..9 recalls camera position/orientation with 2D sync
4. **Walk mode**: Constrained camera movement on walkmesh surface for player-perspective testing
5. **Split-screen preview**: Side-by-side comparison views

### Phase 6: Polish & UX (Unity/Creation Kit standards)
1. Implement full undo/redo stack across all modes
2. ~~Add keyboard shortcut system (Q/W/E/R for tools, F to focus, Delete to remove)~~ ✅ **DONE** — Q/W/E for Select/Move/Rotate tools, F to focus, Delete/Backspace to remove, Z for shading, camera bookmarks
3. Create dockable panel system (drag-and-drop rearrangement)
4. Add dark mode theme (Unity-inspired)
5. **Workspace layouts**: Save/load panel arrangements (e.g., "Walkmesh Editing", "Object Placement", "Lighting")

---

## ✅ Success Criteria

The Module Designer will be considered "complete" when:

1. ✅ A user can **create a new module from scratch** (rooms, objects, walkmeshes, VIS) without leaving the editor
2. ✅ All **Indoor Builder** room-assembly features work seamlessly in 3D Layout Mode
3. ✅ All **Forge walkmesh editing** features work in Walkmesh Mode with Creation Kit-level precision
4. ✅ The **scene hierarchy** mirrors Unity's clarity (expand/collapse, search/filter, visibility toggles)
5. ✅ **4-panel orthographic view** matches Hammer/Radiant workflows for precise 3D alignment
6. ✅ **Walkmesh vertex editing** is as intuitive as Blender's (click vertex → drag gizmo → update mesh)
7. ✅ **Build + Launch** compiles a playable `.mod` and boots the game in < 30 seconds
8. ✅ **Undo/redo** works flawlessly for every operation (room placement, object transforms, walkmesh edits, VIS changes)
9. ✅ The UI is **intuitive enough** that a Unity/UE5/Creation Kit user can start editing with zero training
10. ✅ **No external tools** are needed for basic level design (100% self-contained workflow)

---

## 📖 Reference Inspirations — Gap Analysis

> **Current Module Designer state**: 3D OpenGL viewport + 2D walkmesh renderer (stacked), left panel with Resources tab and Layout tab (room position spinboxes + lytTree), right panel with a flat `QListWidget` of instances, visibility checkboxes per GIT type, QUndoStack, Blender export integration, status bar. **No transform gizmos, no walkmesh vertex editing, no inspector panel, no hierarchy, no multi-select, no VIS editor, no search/filter, no snap helpers, no right-click context menu in viewport, no face property editor.**

---

### **Bethesda Creation Kit** (Skyrim/Fallout 4)
*Gold standard for 3D RPG cell editing. KotOR room = CK cell, GIT object = CK reference, walkmesh = navmesh.*

| What It Does | We Don't Have This | Implement As |
|---|---|---|
| **Navmesh Mode toggle** — same viewport, different interaction layer | No walkmesh vertex editing at all in 3D view | Walkmesh Mode button in toolbar; switch raycast target from GIT objects to BWM vertices |
| **Generate Navmesh** — auto-triangulates walkable area from room geometry | `on_generate_walkmesh` exists but no face editing after | Right-click walkmesh → auto-fill gaps, merge islands |
| **Finalize Navmesh** — computes edge adjacency/portals in one click | Adjacency must be hand-authored or left broken | One-click "Finalize" rebuilds all edge/transition links from current geometry |
| **Reference Browser** — filterable table of all placed objects (type, position, tag, resref) | `instanceList` is a flat unsorted list with no search | Replace with `QTreeView` grouped by type; add search bar above it |
| **Layer system** — Architecture/Props/Lighting layers; toggle at layer level | Visibility is global per-type only | Named layers: group instances → toggle whole layer in/out |
| **Camera bookmarks** — Ctrl+1–9 saves camera view, 1–9 recalls | None | `QAction` array; save/restore camera matrix per slot |
| **Double-click opens editor** — double-click object → properties dialog | Works (opens resource editor dialog) | ✅ Already have this — extend to show inline inspector instead |
| **Audio emitter preview** — wireframe sphere showing UTS max distance | Sound objects show as icons, no radius visualization | Draw sphere overlay when UTS selected using `maxDistance` field |
| **Edge portal marking** — mark walkmesh edges as doorway transitions | Door transitions are implicit; no visual indication | Highlight transition edges in walkmesh view; allow marking them |

---

### **BioWare Dragon Age Toolset**
*Closest analog to KotOR — same third-person RPG genre, GFF-based data, area = module.*

| What It Does | We Don't Have This | Implement As |
|---|---|---|
| **Synchronized 2D+3D views** — select in 2D map → 3D view jumps to it | 2D and 3D are independent; selecting in one doesn't update other | Emit selection signal from `flatRenderer` → camera/selection sync in `mainRenderer` |
| **Drag blueprint from library into viewport** — drag UTC/UTP directly into 3D view | Resource tree is browse-only; no drag-and-drop into viewport | Make `resourceTree` source of `QDrag`; `mainRenderer` accepts drops → raycast spawn position |
| **Waypoint network visualization** — lines connecting waypoint objects | Waypoints show as dots, no connections shown | Draw lines between waypoints that share the same tag/patrol route |
| **Trigger polygon drawing** — draw freeform 2D polygon → creates trigger/encounter | Triggers placed as single point; polygon shape must be edited in separate dialog | In 2D view: polygon drawing tool for triggers and encounter geometry |
| **Resource browser search** — type partial name → instant filter | `resourceTree` has no search bar | Add `QLineEdit` filter above `resourceTree`; hide non-matching items |
| **Area properties panel** — music, ambient sound, minimap, fog in one place | ARE properties only accessible through the ARE editor (separate window) | Add an "Area" tab to the left panel showing ARE key fields inline |
| **Lighting presets** — one-click mood (Interior/Dawn/Dusk) | Lightmap toggle (on/off) only | Preset buttons that set ambient light color + fog to common moods for quick preview |

---

### **Unity Editor** (2020+)
*Baseline for modern 3D editor UX. Every gap here is a standard that users will expect.*

| What It Does | We Don't Have This | Implement As |
|---|---|---|
| **Transform gizmo (W/E/R)** — color-coded XYZ handles for move/rotate/scale | Objects drag freely; no axis-locked handles | Render OpenGL gizmo handles on selected instance; W/E/R keys switch mode |
| **Inspector panel** — all properties of selection in scrollable side panel (no modal) | Properties only shown in separate dialog windows | Add right-side dock `QWidget` that populates with GIT struct fields on selection change |
| **Hierarchy with search** — tree of all scene objects, type icons, search filter | Flat `QListWidget`, no tree, no search | Replace `instanceList` with `QTreeWidget` grouped by GIT type; add search `QLineEdit` |
| **Multi-select** — Ctrl+Click or drag-box → batch transform, batch property edit | Single selection only | Track `selected_instances: list` → already exists; expose to viewport for drag-box selection |
| **Vertex snapping (V key)** — snap object origin to nearest vertex on any mesh | No snapping at all when dragging | While dragging, if V held: find nearest walkmesh vertex; snap placement to it |
| **Surface snapping** — drop object onto walkmesh surface below cursor | Objects placed at flat Z; no auto-ground | Raycast downward from cursor on drop/move; set object Z to hit point |
| **Focus Selected (F key)** — camera frames selection tightly | No focus shortcut | `F` key → compute bounding box of selected instances → set camera position/target |
| **Frame All (A key)** — camera frames entire scene | No frame-all | `A` key → bounding box of all loaded instances → set camera |
| **Gizmo visibility toggles** — show/hide sound spheres, trigger boxes, camera frustums | No per-gizmo overlay toggles | Add overlay checkboxes: Show Sound Radii / Show Trigger Shapes / Show Camera FOV |
| **Coordinate space (World/Local)** — toggle whether gizmo axes align to world or object | Always world-space | Button in toolbar; affects how rotate/scale gizmo axes are oriented |

---

### **Unreal Engine 5**
*Best-in-class viewport navigation and scene organization.*

| What It Does | We Don't Have This | Implement As |
|---|---|---|
| **WASD fly camera with mouse look** | Alt+drag orbit only; no WASD flythrough | Right-click + drag in 3D view activates mouse look; WASD moves camera while held |
| **Camera speed slider** — scroll wheel adjusts fly speed in real-time | Fixed camera speed | Scroll wheel while in fly mode → adjust `camera_move_speed`; show current speed in status bar |
| **Outliner folders** — drag objects into named folders; toggle folder visibility | No grouping at all in instance list | Folders in `QTreeWidget`: right-click → "New Group"; drag instances between groups |
| **Details panel search filter** — type property name → scroll to matching field | No inspector panel at all | When inspector is added, put a `QLineEdit` at top that filters/highlights matching fields |
| **Right-click context menu in viewport** — place object, frame selection, hide, etc. | No context menu on 3D viewport right-click | Connect `customContextMenuRequested` on `mainRenderer` → build context-sensitive `QMenu` |
| **Viewport toolbar mode buttons** — visual icon buttons for Select/Move/Rotate/Scale | No mode buttons; interaction mode is implicit | Add toolbar row above 3D viewport: Select / Move / Rotate / Scale icon buttons |

---

### **Valve Hammer** (Source SDK)
*Precision multi-view layout; best for spatial alignment work.*

| What It Does | We Don't Have This | Implement As |
|---|---|---|
| **4-panel layout** — Top/Front/Side/Perspective simultaneously | One 3D + one 2D stacked vertically; can't see all axes at once | `QSplitter` with 4 panes: 3D perspective + 3 orthographic (XY top-down, XZ front, YZ side) |
| **Maximize active view** — double-click panel to fill the window | Fixed split only | Double-click on any sub-renderer → reparent to fill main area; double-click again to restore |
| **Grid size hotkeys ([ and ])** — increase/decrease snap grid in 2 keystrokes | No grid snapping at all | `[` / `]` keys cycle snap grid size (0.1 / 0.5 / 1.0 / 2.0 units); show current in status bar |
| **Visgroups** — named groups with per-group visibility toggle | Type-level visibility checkboxes only | Named Visgroups in left panel; drag objects in; one toggle per group |
| **Error checker** — "Check for Problems" scans for missing textures, broken refs | No validation tools | Menu item → scan module for broken resrefs, missing models, degenerate walkmesh faces |
| **Compile pipeline** — one-click Build → launches game | Save GIT only; no build+launch | Add "Build & Launch" action that calls `build_mod_from_indoor_file()` → game spawn warp |

---

### **Blender**
*Best walkmesh vertex editing workflow reference — we need Blender's Edit Mode concept.*

| What It Does | We Don't Have This | Implement As |
|---|---|---|
| **Edit Mode vs Object Mode** — Tab key toggles; completely different interaction in same viewport | No walkmesh editing in 3D view at all | Tab or toolbar button: Object Mode (GIT instances) ↔ Walkmesh Mode (BWM vertices/faces) |
| **Vertex / Edge / Face select modes (1/2/3)** — granular selection within mesh | N/A — no mesh editing | In Walkmesh Mode: 1=vertex select, 2=edge select, 3=face select; highlight accordingly |
| **Merge Vertices (M)** — weld nearby/overlapping vertices | No geometry cleanup tools | In Walkmesh Mode: M key → merge dialog (at cursor / at center / by distance) |
| **Snap modes (Shift+Tab)** — cycle vertex/edge/face/grid snapping | No snap at all | Snap pie menu cycling through modes; sticky state shown in status bar |
| **Properties panel** — context-sensitive; shows face material when face selected | No per-element property view | When walkmesh face selected → show surfacemat dropdown + walk/walkCheck/lineOfSight booleans in inspector |
| **Viewport shading (Z key)** — Wireframe/Solid/Material toggle | Lightmap checkbox (on/off) only | Z key cycles 3D viewport shading: Wireframe / Solid / Lightmapped |
| **Box select (B key)** — drag rectangle to select multiple vertices/objects | No box select | B key → drag selection rectangle in 3D viewport; add all intersecting objects/vertices to selection |

---

### **GTKRadiant / id Tech**
*Per-face editing workflow that directly maps to surfacemat on walkmesh triangles.*

| What It Does | We Don't Have This | Implement As |
|---|---|---|
| **Surface Inspector** — per-selected-face numeric fields (no dialog close required) | No per-face editing; surfacemat not editable | `walkmeshTab` dock: when face selected → show surfacemat dropdown + flags inline |
| **Entity key-value editor** — raw struct fields visible as editable key-value table | GIT struct editing only via full resource editor window | In inspector panel: show GIT instance fields as editable `QTableWidget` rows (key / value) |
| **Free camera WASD** | Orbit-only; WASD not usable for flythrough | Right-click-held activates free look; WASD moves; right-click-release returns to orbit |
| **Group system** — Ctrl+G groups brushes; move as unit | No grouping | Multi-select → right-click → "Group" → assigned Visgroup |

---

## 🎯 Universal Patterns (Implement in All Modes)

| Pattern | We Have | Gap |
|---|---|---|
| **One window, no modal dialogs for properties** | Properties open separate dialog | Inline inspector dock panel |
| **Undo everything including view changes** | QUndoStack on GIT ops | Viewpoint/walkmesh edits not undoable yet |
| **Visual feedback on selection** | 3D selection highlight | No gizmo, no bounding box outline |
| **Immediate property feedback** | Dialog requires Apply / OK | Inspector should write-through to model on field change |
| **Keyboard shortcuts for all tools** | Ctrl+Z/S only | W/E/R/F/A/B/Tab/Z/[/] all unassigned |
| **Status bar showing active mode + snap state** | Mouse coords + selected instance | Need: current mode, current snap size, coordinate space |
