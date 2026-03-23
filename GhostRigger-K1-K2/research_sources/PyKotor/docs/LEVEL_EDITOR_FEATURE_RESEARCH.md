# Comprehensive Game Level Editor Feature Research
## Benchmarking Industry Standards for KotOR Module Designer

**Research Date:** March 2026  
**Scope:** Analysis of 5 professional game level editors + KotOR engine capabilities  
**Purpose:** Document canonical feature-set for comprehensive KotOR Module Designer

---

## TABLE OF CONTENTS

1. [Industry Editor Analysis](#industry-editor-analysis)
   - [Unity Editor](#unity-editor)
   - [Unreal Engine 5](#unreal-engine-5)
   - [Valve Hammer Editor](#valve-hammer-editor)
   - [Radiant (Quake 3)](#radiant-quake-3)
   - [CryEngine Sandbox](#cryengine-sandbox)
2. [KotOR Engine Capabilities](#kotor-engine-capabilities)
3. [Canonical Checklist](#canonical-checklist-for-kotor-module-designer)

---

# INDUSTRY EDITOR ANALYSIS

## Unity Editor

### Core Viewport Tools
- **Transform Tools:** Move/Rotate/Scale gizmos with world/local space toggle
- **Snap & Grid:** Vertex/Surface snapping, adjustable grid size
- **Gizmo Modes:** Translation, rotation, scale with different space handling
- **Camera Control:** Orbit, pan, zoom with configurable speed
- **Viewport Overlays:** Scene statistics, gizmos visibility, lighting modes
- **Multiple Views:** Scene View and Game View simultaneously

### Subsystem Editors (All edit in same viewport)
- **Scene Objects:** GameObjects (hierarchical)
- **Mesh Editing:** Vertex/edge/face selection (via plugins)
- **Terrain:** Built-in Terrain Editor (paint heights, paint splats)
- **Lighting:** Place lights, adjust properties real-time
- **Particles:** Particle System Editor integrated
- **Physics:** Collider visualization, physics debugging
- **UI/Canvas:** Render overlay for UI elements
- **Animation:** Timeline and animation curve editin integrated

### Property Inspectors
- **Inspector Panel:** Object properties shown per selected item
- **Material Editor:** Shader properties
- **Terrain Tools:** Height/splat/vegetation painters
- **Prefab Variants:** Override-capable property system
- **Auto-expose:** Only relevant properties shown per object type

### Specialized Tools
- **Terrain Editor:** Sculpt, paint heightmap, vegetation layer painting
- **Particle System:** Visual effect tuning
- **Sprite Atlas:** 2D asset packing
- **AI Navigation:** NavMesh baking and visualization
- **Audio Mixer:** Real-time audio adjustments

### Viewport Modes
- **Shaded:** Full lighting
- **Wireframe:** Geometry wireframe overlay
- **Shadow Cascades:** Visualize shadow maps
- **Overdraw:** Show overdraw heatmap
- **Lightmap Visualization:** UV layout preview
- **Lighting Complexity:** Pixel light performance heatmap
- **Material Validation:** Check shader compatibility

### Hierarchy Management
- **Scene Hierarchy Panel:** Full tree view with drag-drop organization
- **Prefab System:** Nested prefab inheritance with overrides
- **GameObject Parenting:** Transform hierarchies with children
- **Search/Filter:** Hierarchical search by name/tag/type
- **Grouping:** Folder-style organization within scene
- **Multi-selection:** Organize groups contextually

### Scripting/Logic
- **Visual Node Editors:** Animator (state machines), Timeline (sequencing)
- **Event System:** Callback-based messaging, UnityEvents
- **Serialization:** Inspector exposes C# properties automatically
- **Custom Editors:** Script monobehaviors auto-detect properties

---

## Unreal Engine 5

### Core Viewport Tools
- **Transform Tools:** Advanced gizmos with snap-to-grid, snap-to-surface
- **Gizmo Customization:** World/local/screen-space axes
- **Camera Modes:** Freely positionable camera with speeds
- **Bookmarked Views:** Save/restore camera positions (Viewpoints)
- **Viewport Layouts:** Multiple perspectives (Top, Side, Front, 3D)
- **Real-time Lighting Preview:** Immediate visual feedback

### Subsystem Editors (All in unified viewport)
- **Static Meshes:** Place, scale, material assignment
- **Landscapes:** Integrated landscape sculpting
- **Foliage:** Foliage mode (procedural and Nanite)
- **Lights:** Directional, point, spot with dynamic shadows
- **Particles:** Niagara particle editor embedded
- **Cameras:** Camera placement and sequencing
- **Volumes:** VisVolume, PhysicsVolume, TriggerVolume visualization
- **Water:** Water bodies with wave parameters

### Property Inspectors
- **Details Panel:** All selected object properties
- **World Outliner:** Hierarchical browsing
- **Material Instance Editor:** Dynamic material tweaking
- **Landscape Editor:** Multi-layer painting
- **Foliage Painter:** Density and instance sculpting

### Specialized Tools
- **Landscape Tools:** 
  - Sculpting (raise/lower with brush falloff)
  - Multi-layer painting (blend materials by altitude/slope)
  - Erosion simulation
  - Flatten/Ramp/Terrace brushes
  - Heightmap import/export
- **Foliage Mode:**
  - Procedural Vegetation Editor (new in UE 5.7)
  - Instance painter with customizable brushes
  - Density-based placement
  - Nanite-enabled foliage rendering
- **Nanite System:** Micro-polygon rendering for high-detail static geometry
- **Sequencer:** Timeline-based cinematics, camera paths, animation blending
- **Lighting:**
  - Global Illumination (Lumen)
  - Dynamic lighting with baked lightmaps
  - Light importance volumes
  - Lightmap density visualization
- **Physics:**
  - Ragdoll editor
  - Collision shape visualization
  - Physics constraint editing

### Viewport Modes
- **Lit:** Full lighting
- **Unlit:** No lighting
- **Wireframe:** Geometry only
- **Lightmap Density:** Shows baked lightmap resolution
- **Reflections:** Shows reflection captures
- **Exposure:** HDR exposure control
- **Ray Traced:** Shows ray-traced effects preview

### Hierarchy Management
- **World Outliner:** Full organization tree
- **Folders:** Organizational hierarchy (prefab-like)
- **Layers:** Object visibility/locking by layer
- **Collections:** Grouping for export/management
- **Level Instances:** Nested levels with instancing

### Scripting/Logic
- **Blueprints:** Visual scripting with event/function nodes
- **Material Editor:** Node-based shader graph
- **Sequencer:** Timeline for cutscenes and animations
- **Destroy-able Geometry:** Destruction event triggers
- **Trigger Callbacks:** Overlap/hit event binding

---

## Valve Hammer Editor

### Core Viewport Tools
- **Brush Tools:** Box, wedge, pyramid, cylinder creation
- **Vertex Manipulation:** Drag vertices to shape brushes
- **Snap-to-Grid:** Adjustable grid snapping
- **3D/2D Views:** Orthogonal top/front/side + isometric 3D
- **Scroll Lock:** Synchronized pan across views
- **Texture Alignment:** Per-face UV alignment tools

### Subsystem Editors
- **Brush Geometry:** CSG-based room construction
- **Entity Placement:** Point entities and entity groups
- **Vertices:** Direct vertex editing for brush shapes
- **Textures:** Face texture assignment and UV mapping
- **Lighting:** Light entity placement with properties
- **Connections:** Entity I/O (input/output) connections visual

### Property Inspectors
- **Object Properties Dialog:** 
  - Classname, properties, I/O connections per entity
  - VisGroup tabs for organization
  - Conditional field visibility based on entity type
- **Smart Edit:** Context-sensitive properties based on selection

### Specialized Tools
- **VisGroups:** 
  - Layer-like organization system (visibility groups)
  - Auto-groups (Triggers, Lights, Water, etc.)
  - Show/hide entire groups
  - Affects compile-time visibility
- **Texture Tools:**
  - Texture browser with filter
  - Apply/replace texture across selection
  - Texture alignment tools (shift/scale/rotate)
- **Cordon Tool:** Clip work area to specific volume
- **Block Tool:** Create world brushes (CSG)
- **Entity Tool:** Paint entity instances
- **Camera Tool:** Define camera start positions

### Viewport Modes
- **3D:** Isometric rendering
- **Wireframe:** Edges only
- **Textured:** Full texture display
- **Flat Shaded:** Flat color with normals
- **Default (Solid):** Solid shapes
- **Render Mode:** Software vs hardware

### Hierarchy Management
- **Object Groups:** Group multi-select for movement
- **VisGroups:** Visibility and organizational grouping
- **Named Objects:** Tag and reference system
- **Logical Grouping:** Organize by entity type

### Scripting/Logic
- **Entity I/O System:**
  - Input/output connections (visual linking)
  - Event triggering on specific conditions
  - Relay entities for logic chains
- **Scripting Entities:** Per-map scripting via entity properties
- **Named Entity References:** Cross-entity communication

---

## Radiant (Quake 3)

### Core Viewport Tools
- **Brush Creation:** Free-form brush dragging
- **CSG Operations:** Carve, hollow, merge
- **Texture Application:** Drag-drop textures on brushes
- **Vertex Editing:** Direct vertex manipulation
- **Edge Beveling:** Chamfer sharp edges
- **Snap & Grid:** World-space grid with configurable cell size
- **Multi-viewport:** Top, front, side, 3D isometric

### Subsystem Editors
- **Brushes:** CSG geometry construction
- **Entities:** Point and brush entities
- **Lights:** Light source placement
- **Textures/Shaders:** Shader application and animation
- **Connectivity:** Target/targeted entity linking visual

### Property Inspectors
- **Entity Inspector:** 
  - Key-value properties per entity
  - Dropdown for predefined entity types
  - Real-time property editing
  - Target connection visualization

### Specialized Tools
- **Light Editor:**
  - Light radius visualization
  - Brightness adjustment
  - Light color picker
  - Falloff curves
- **Texture Alignment Tools:**
  - UV rotation/scale
  - Per-face alignment
  - Global texture replacement
- **Model Placement:** Place .md3 models as entities
- **Particle/Effect Emitters:** Configurable emitter entities

### Viewport Modes
- **Wireframe:** Geometry outline
- **Flat Shaded:** Solid faces with normal visualization
- **Textured:** Full texture rendering
- **Lighting Preview:** Baked light preview (requires recompile)

### Hierarchy Management
- **Entity Grouping:** Group entities for organization
- **Folder-like Grouping:** Hierarchical entity organization
- **Entity Lists:** Side panel showing all entities
- **Filter View:** Show/hide entity types

### Scripting/Logic
- **Entity Targeting:**
  - Target/targetname system
  - Visual connection drawing
  - Relay and trigger entities
- **Trigger Geometry:** Special-content textures (clip, trigger, etc.)
- **Particle Triggering:** Emitter start/stop conditions

---

## CryEngine Sandbox

### Core Viewport Tools
- **Transform Tools:** Move/rotate/scale with gizmos
- **Snap Options:** Grid, angle, surface snap
- **Coordinate Display:** Position/rotation feedback in real-time
- **Viewport Navigation:** Orbit, pan, zoom camera
- **Multiple Cameras:** Bookmarked positions for common views

### Subsystem Editors (All in unified viewport)
- **Terrain Editor:** Integrated heightmap sculpting
- **Vegetation:** Procedural plant/tree/grass placement
- **Objects:** Static and dynamic mesh placement
- **Lights:** Point/directional/projected lights
- **Particle Systems:** Integrated effect editor
- **Sound Zones:** Area-based audio volumes
- **Water:** Water simulation parameters and placement
- **Roads:** Spline-based road building

### Property Inspectors
- **Properties Panel:** Object-specific properties
- **Materials:** Shader and material assignment
- **Terrain Materials:** Multi-layer terrain texture painting
- **Vegetation Painter:** Procedural vegetation settings

### Specialized Tools
- **Terrain Editor:**
  - Raise/lower brush with falloff
  - Smooth/flatten operations
  - Erosion simulation
  - Splat painting (multi-layer texturing)
  - Splat maps visualization
  - Vegetation density painting
- **Vegetation Tools:**
  - Category-based placement (Trees, Bushes, Grass)
  - Density painting
  - Rotation and scale randomization
  - Per-brush vegetation types
- **Sound Zones:**
  - Area-based audio volumes
  - Reverb parameters
  - Ambient sound placement
- **Particle Editor:** Visual effect node graph
- **Lighting:**
  - IES light profiles
  - Lightmap generation
  - Global illumination parameters
- **Water Editor:** Wave height, flow, foam parameters

### Viewport Modes
- **Shaded:** Full dynamic lighting
- **Wireframe:** Geometry wireframe
- **Lighting Only:** Baked lighting preview
- **Terrain Height Map:** Height values visualization
- **Splat Map:** Texture layer density display
- **Vertex Colors:** Painted vertex color visualization

### Hierarchy Management
- **Object Browser:** Hierarchical object tree (2-pane)
- **Prefab System:** Prefab instances with overrides
- **Layers:** Organizational/visibility layers
- **Search:** Find objects by name/type
- **Grouping:** Logical grouping for management

### Scripting/Logic
- **Flowgraph:** Node-based visual scripting
  - Input/output node connections
  - Conditional logic nodes
  - Event triggers
  - Data transformation nodes
- **Script Entities:** Lua script assignment per entity
- **Dynamic Objects:** Rigidbody and physics triggers

---

# KotOR ENGINE CAPABILITIES

## File Format Overview

KotOR uses a modular approach to level data with specialized formats for different aspects of area structure:

### LYT (Layout) - Room/Area Spatial Structure
**Purpose:** Define how area geometry is assembled from room models

**Editable Components:**
- `Rooms` (RoomCount): 
  - Model reference (MDL file ResRef)
  - X, Y, Z position in world space
  - One room per module line
- `Tracks` (TrackCount):
  - Swoop racing track booster elements
  - Model and position
  - Only in K2 racing modules
- `Obstacles` (ObstacleCount):
  - Swoop racing hazard elements
  - Model and position
  - Racing-specific (K2)
- `Door Hooks` (DoorHookCount):
  - Door placement points
  - Room association (which room this door opens into)
  - Door name identifier
  - X, Y, Z position
  - Quaternion orientation (rotation)
  - Optional additional float parameters for some implementations

**File Format:** Plain ASCII text
- Structured with `beginlayout` / `donelayout` keywords
- Each section declares a count followed by entries
- **Reference:** `vendor/reone/src/libs/resource/format/lytreader.cpp`

---

### GIT (Game Instance Template) - Dynamic Object Placement
**Purpose:** Define where all game objects are positioned in an area

**Editable Instance Lists:**

| Instance Type | Purpose | Template Type | Editable Properties |
|---------------|---------|---------------|---------------------|
| **Creatures** | NPCs, enemies, party members | UTC | ResRef, position, bearing (rotation), appearance override, equipment |
| **Doors** | Interactive doors for transitions | UTD | ResRef, position, bearing, tag, linked module, linked waypoint, transition text, color tint, HP override |
| **Placeables** | Furniture, containers, scenery | UTP | ResRef, position, bearing, color tint, HP, useable flag |
| **Triggers** | Trigger zones for scripts/events | UTT | Position, geometry (collision shape), tag, script on trigger |
| **Waypoints** | Navigation points, spawn markers | UTW | ResRef, position, tag, spawning flags |
| **Encounters** | Spawn zones with creature groups | UTE | Position, geometry, tag, respawn behavior |
| **Sounds** | Positional audio emitters | UTS | ResRef, position, volume, pitch, loop behavior |
| **Stores** | Merchant vendors | UTM | ResRef, position, tag, inventory |
| **Cameras** | Camera definitions for cutscenes | - | Position, look-at target, FOV |

**Common Instance Fields (All objects):**
- Position: X, Y, Z world coordinates
- Bearing: Rotation angle
- Tag: Unique identifier for scripting reference
- Template ResRef: Link to blueprint (UTC/UTD/UTP/etc.)

**File Format:** GFF (Generic File Format) binary
- Hierarchical structure with nested types
- Type-safe field system

---

### ARE (Area) - Static Environmental Properties
**Purpose:** Define area-wide environmental settings (never changes at runtime)

**Editable Subsystems:**

| Subsystem | Editable Elements |
|-----------|-------------------|
| **Lighting** | Ambient color (RGB), ambient sounds, ambient music |
| **Sun/Directional Light** | Direction, color, intensity |
| **Fog** | Far/near fog distance, fog color, fog enabled |
| **Grass/Vegetation** | Grass/flora texture and rendering enabled |
| **Skybox/Weather** | Skybox texture, weather effect type |
| **Scripts** | OnEnter script, OnExit script, heartbeat script |
| **Load Screens** | Transition loading screen ResRef |
| **Campaign/Module Info** | Campaign-specific flags |
| **Minimap** | Minimap TARGA texture reference |

**File Format:** GFF binary

---

### VIS (Visibility) - Occlusion Culling Graph
**Purpose:** Define which rooms are visible from other rooms (occlusion culling optimization)

**Editable Components:**
- Parent Room Lines: Room name + visible child count
- Child Room Indentation: Each visible child room on indented lines
- Recursively defines visibility chains

**File Format:** Plain ASCII text
- Deterministic parent-child hierarchy
- Two-space indentation for children
- Names are case-insensitive

**Performance Impact:**
- Without VIS: All rooms rendered (poor performance)
- With VIS: Only visible rooms rendered (10-50x fewer draw calls)
- **Critical optimization:** Not required but highly recommended for complex areas

---

### PTH (Path) - Pathfinding/AI Navigation
**Purpose:** Define navigation paths for creature AI and pathfinding

**Editable Components:**
- Path Points: X, Y, Z coordinates
- Path Connections (Edges): Which points connect to which
- Connection Properties: Type flags, transition costs

**File Format:** GFF binary

---

### WOK (Walkmesh/BWM) - Collision and Pathfinding Per-Room
**Purpose:** Define collision geometry and walkable areas for each room

**Editable Components (per room file):**
- Face Geometry: Triangle mesh for collision
- Face Flags: Walkable, non-walkable, geometry type
- Edge Connections: Which edges can be traversed
- Material Type: Affects sound and footstep type

**File Format:** Binary BWM (BioWare Walkmesh)
- One WOK/BWM file per LYT room
- Paired with MDL/MDX model file by ResRef

**Relationship:**
- LYT defines room positions
- Each room has corresponding WOK file by ResRef
- Engine loads WOK when loading room from LYT

---

### MDL/MDX - Room Model Geometry
**Purpose:** 3D geometry for each room

**Editable Components:**
- Geometry: Vertices, triangles, materials
- Animations: Room-specific animations
- Emitters: VFX/particle emitter definitions
- Lighting: Per-model ambient/diffuse overrides

**File Format:** Binary (compiled 3D model)
- Referenced by LYT room entries
- Paired with WOK by ResRef name

---

## Relationship Map

```
┌─ ARE (Area)
│  └─ Static: Lighting, fog, weather, scripts, music, minimap
│
├─ LYT (Layout)
│  ├─ Rooms → MDL/MDX (geometry)
│  │         → WOK (collision/pathfinding)
│  ├─ Door Hooks → Link to GIT doors
│  ├─ Tracks (K2 racing only)
│  └─ Obstacles (K2 racing only)
│
├─ GIT (Game Instance Template)
│  ├─ Creatures (UTC templates)
│  ├─ Doors (UTD templates)
│  ├─ Placeables (UTP templates)
│  ├─ Triggers (UTT templates)
│  ├─ Waypoints
│  ├─ Encounters (UTE templates)
│  ├─ Stores (UTM templates)
│  ├─ Sounds (UTS templates)
│  └─ Cameras
│
├─ VIS (Visibility)
│  └─ Room visibility culling graph
│
└─ PTH (Pathfinding)
   └─ AI navigation paths
```

---

## What KotOR CAN Edit (Currently)

The engine supports all above structures. What can be changed:
- Room positions and orientations (LYT)
- All object placement (GIT)
- Object properties (bearing, color tint, HP, scripts)
- Area-wide properties (ARE: lighting, fog, scripts)
- Visibility optimization (VIS)
- Pathfinding routes (PTH)
- Walkmesh collision (WOK)
- Room models (MDL/MDX)

---

# CANONICAL CHECKLIST FOR KOTOR MODULE DESIGNER

## Overview
This checklist defines the "all-in-one" module designer feature scope based on industry standards and KotOR's engine capabilities. Items are prioritized by criticality, feasibility, and user-workflow value.

---

## TIER 1: CRITICAL (Must-Have)

### A. Unified 3D Viewport
- [ ] Single integrated 3D viewport showing entire area
- [ ] Real-time rendering of:
  - LYT rooms (MDL/MDX geometry)
  - LYT door hooks (visual placement guides)
  - GIT object instances (creatures, doors, placeables, etc.)
  - WOK wireframe overlay (collision geometry, optional toggle)
  - Lighting preview (ARE ambient + direct light)
- [ ] Camera controls:
  - [ ] Orbit/pan/zoom with mouse
  - [ ] Bookmarked view positions (save/load camera positions)
  - [ ] Multiple synchronized views (top, front, side, 3D)
- [ ] Viewport modes:
  - [ ] Shaded (full lighting)
  - [ ] Wireframe (geometry wireframe)
  - [ ] Collision (WOK overlay)
  - [ ] Textured (material preview)
  - [ ] Unlit (flat render)

### B. Transform/Placement Tools
- [ ] Move tool (translate objects in 3D)
  - [ ] World-space movement
  - [ ] Plane-constrained movement (XY, XZ, YZ)
  - [ ] Free dragging
- [ ] Rotate tool
  - [ ] Quaternion-based rotation (yaw/pitch/roll)
  - [ ] Visual rotation gizmo (bearing angle indicator)
- [ ] Scale tool (for non-critical adjustments)
- [ ] Snap-to-grid:
  - [ ] Configurable grid size (0.25, 0.5, 1.0, etc. units)
  - [ ] Grid visualization on ground plane
  - [ ] Toggle snap on/off
- [ ] Gizmo display:
  - [ ] 3-axis widget (RGB color-coded)
  - [ ] Real-time position display during movement
  - [ ] Undo/redo for all transformations

### C. Object Selection & Hierarchy
- [ ] Selection in 3D viewport:
  - [ ] Click-to-select individual objects
  - [ ] Bounding box highlight on selection
  - [ ] Multi-select (Shift+click)
  - [ ] Drag-selection (marquee select)
  - [ ] Select-all / deselect-all
- [ ] Hierarchy panel:
  - [ ] Expandable tree showing all GIT objects by type
  - [ ] Filter by object type (Creatures, Doors, Placeables, etc.)
  - [ ] Drag-reorder (optional; may not affect game behavior)
  - [ ] Show/hide objects in tree
- [ ] Search capability:
  - [ ] Search by object tag/name
  - [ ] Search by template ResRef
  - [ ] Filter results in real-time

### D. Room Management (LYT Editing)
- [ ] Room list panel:
  - [ ] Show all rooms from LYT
  - [ ] Add new room
  - [ ] Delete room (with safeguards)
  - [ ] Edit room properties:
    - [ ] Model ResRef
    - [ ] X, Y, Z position
- [ ] Room placement in viewport:
  - [ ] Drag rooms to move them
  - [ ] Snap rooms to grid
  - [ ] Visual bounding box for each room
- [ ] Door hook management:
  - [ ] List all door hooks per room
  - [ ] Add/remove door hooks
  - [ ] Edit hook properties:
    - [ ] Room association (which room)
    - [ ] Hook name
    - [ ] Position (X, Y, Z)
    - [ ] Rotation (quaternion/bearing)
- [ ] Visual feedback:
  - [ ] Room geometry rendering
  - [ ] Door hook placement markers with orientation visualization
  - [ ] Highlight selected room

### E. Object Placement (GIT Editing)
- [ ] Add objects to area:
  - [ ] Creature picker (select UTC template)
  - [ ] Door picker (select UTD template)
  - [ ] Placeable picker (select UTP template)
  - [ ] Trigger picker (define geometry)
  - [ ] Waypoint, Sound, Store, Encounter pickers
  - [ ] Click in viewport to place, or use panel interface
- [ ] Object selection properties:
  - [ ] Common fields (position, bearing/rotation, tag)
  - [ ] Type-specific fields:
    - [ ] **Doors:** LinkedToModule, LinkedTo, TransitionDestin, color tint
    - [ ] **Placeables:** Color tint, useable flag, HP override
    - [ ] **Creatures:** Appearance override, equipment display
    - [ ] **Triggers:** Script on trigger, geometry (collision shape)
    - [ ] **Sounds:** Volume, pitch, loop behavior
    - [ ] **Encounters:** Respawn settings, creature group
- [ ] Bulk operations:
  - [ ] Delete multiple objects
  - [ ] Duplicate with offset
  - [ ] Rotate/align multiple objects

### F. Property Inspector
- [ ] Properties panel showing selected object:
  - [ ] All editable fields with appropriate input types
  - [ ] Field validation (e.g., ResRef must exist)
  - [ ] Dropdown for enums (e.g., appearance IDs, class indices)
  - [ ] Text input for ResRef/tags
  - [ ] Numeric input for positions, colors, etc.
  - [ ] Boolean checkboxes for flags
- [ ] Dynamic fields:
  - [ ] Show only relevant fields based on object type
  - [ ] Conditional visibility (e.g., LinkedToModule only for doors)
- [ ] Real-time updates:
  - [ ] Changes reflect immediately in 3D viewport
  - [ ] Lighting/appearance updated on change

### G. File I/O
- [ ] Load existing module:
  - [ ] Parse ARE, LYT, GIT, VIS, WOK, PTH files
  - [ ] Display all data in editor
- [ ] Save module:
  - [ ] Write ARE, LYT, GIT back to disk
  - [ ] Preserve VIS, WOK, PTH (or regenerate)
  - [ ] Automatic backup of original files
- [ ] Export/import:
  - [ ] Export to editable text formats (debug)
  - [ ] Import from external tools

### H. Undo/Redo System
- [ ] Full undo/redo for all operations:
  - [ ] Object placement
  - [ ] Property edits
  - [ ] Transformation
  - [ ] Deletion/creation
- [ ] Undo stack (configurable depth)
- [ ] Visual feedback on undo/redo

---

## TIER 2: HIGH PRIORITY (Core Usability)

### A. Advanced Lighting
- [ ] Visualization of ARE ambient lighting
- [ ] Edit area ambient light:
  - [ ] RGB color picker
  - [ ] Intensity slider
- [ ] Sun/directional light editor:
  - [ ] Direction control (pitch/yaw)
  - [ ] Color and intensity
  - [ ] Shadow toggle
- [ ] Fog editor:
  - [ ] Near/far distance
  - [ ] Fog color
  - [ ] Enabled toggle
- [ ] Real-time preview:
  - [ ] Update viewport lighting as properties change
  - [ ] Baked lightmap preview (if computed)

### B. VIS (Visibility) Editor
- [ ] Visual graph editor for room visibility:
  - [ ] Show rooms as nodes
  - [ ] Draw directed edges (parent → visible children)
  - [ ] Add/remove visibility links
  - [ ] Validate consistency (no orphaned rooms)
- [ ] Text editor view:
  - [ ] Raw VIS format editing with syntax highlighting
  - [ ] Parse and validate on load
- [ ] Performance hints:
  - [ ] Warn if all rooms mutually visible (defeats culling)
  - [ ] Warn if rooms are orphaned (never render)
  - [ ] Statistics (average visible rooms per room)

### C. Terrain/Landscape Editing
- [ ] If creating new areas (future):
  - [ ] Heightmap import/export
  - [ ] Terrain sculpting (raise/lower)
  - [ ] Splat/layer painting
  - [ ] Grass density painting
- [ ] For existing areas:
  - [ ] WOK visualization
  - [ ] WOK collision inspection

### D. Advanced Object Management
- [ ] Grouping objects:
  - [ ] Create named groups
  - [ ] Group visibility toggle
  - [ ] Bulk operations on groups
- [ ] Layer system (like Hammer VisGroups):
  - [ ] Assign objects to layers
  - [ ] Show/hide by layer
  - [ ] Lock layers to prevent editing
- [ ] Search and replace:
  - [ ] Find all objects of type X
  - [ ] Find by tag pattern
  - [ ] Replace property values (e.g., change script on all triggers)

### E. Trigger/Encounter Editing
- [ ] Trigger geometry visualization:
  - [ ] Draw collision shape in viewport
  - [ ] Edit shape (adjust box/sphere/polygon)
  - [ ] Show trigger radius
- [ ] Script binding:
  - [ ] Browse available scripts
  - [ ] Assign trigger script
  - [ ] Syntax highlighting in script editor
  - [ ] Script parameter hints
- [ ] Encounter spawn setup:
  - [ ] Configure creature resources to spawn
  - [ ] Spawn count override
  - [ ] Respawn behavior

### F. Scripting/Event System
- [ ] Script editor panel:
  - [ ] Edit per-area scripts (OnEnter, OnExit, Heartbeat)
  - [ ] Syntax highlighting for NCS/Python
  - [ ] Script validation/compilation hints
- [ ] Trigger event binding:
  - [ ] Drag-drop event connections between objects
  - [ ] Visual event graph (optional)
- [ ] Script browser:
  - [ ] List available scripts in module
  - [ ] Search by function name

### G. Pathfinding (PTH) Editor
- [ ] Visualize pathfinding nodes:
  - [ ] Draw nodes as points in viewport
  - [ ] Show connections (edges) between nodes
  - [ ] Node constraint indicators
- [ ] Add/remove path nodes:
  - [ ] Context menu in viewport
  - [ ] Properties for node (position, flags)
- [ ] Auto-generation (from template):
  - [ ] Generate from trigger geometry or waypoints

### H. Door/Transition Setup
- [ ] Visual door linking:
  - [ ] Click door → target door link
  - [ ] Show which rooms doors connect
  - [ ] Highlight transition path in viewport
- [ ] Transition properties:
  - [ ] Load screen text customization
  - [ ] Module and waypoint linking
  - [ ] Visual feedback for linked transitions

### I. Color/Material Tweaking
- [ ] Placeable/door color tint picker:
  - [ ] RGB color picker
  - [ ] Live preview in viewport
  - [ ] Save presets
- [ ] Material assignment (if supported):
  - [ ] Change material ResRef
  - [ ] Preview material in viewport

---

## TIER 3: MEDIUM PRIORITY (Workflow Enhancement)

### A. Advanced Viewport Features
- [ ] Performance profiling:
  - [ ] Polygon count indicator
  - [ ] Draw call count
  - [ ] Load time statistics
- [ ] Lighting overlay modes:
  - [ ] Heatmap (overdraw analysis)
  - [ ] Shadow cascade visualization
  - [ ] Light complexity per pixel
- [ ] LOD visualization:
  - [ ] Show model LOD levels as you zoom
  - [ ] LOD transition preview
- [ ] Minimap:
  - [ ] 2D top-down view of area
  - [ ] Object indicators
  - [ ] Player/camera position indicator
  - [ ] Click to jump camera

### B. Template Management
- [ ] Template browser:
  - [ ] Browse available UTC/UTD/UTP templates
  - [ ] Preview template appearance
  - [ ] Show template properties
- [ ] Template overrides:
  - [ ] Show which properties are overridden per instance
  - [ ] Revert to template default
- [ ] Bulk template replacement:
  - [ ] Find all instances of template X
  - [ ] Replace with template Y (with conflict handling)

### C. Animation Preview
- [ ] Creature animation playback:
  - [ ] Play animations attached to creature instances
  - [ ] Select animation from dropdown
  - [ ] Looping toggle
  - [ ] Frame-by-frame control
- [ ] Object animation:
  - [ ] Door open/close animation
  - [ ] Placeable activation animation
  - [ ] Timeline preview (if using sequencer for cinematics)

### D. Particle/Effect Preview
- [ ] Emitter visualization:
  - [ ] Preview particle effects in viewport
  - [ ] Adjust emitter properties
  - [ ] Toggle effect on/off
- [ ] Sound preview:
  - [ ] Play positional sounds in viewport
  - [ ] Visualize sound radius
  - [ ] Volume/pitch adjustment

### E. Validation & Error Reporting
- [ ] Syntax/logic checks:
  - [ ] Warn on orphaned objects (in GIT but not linked)
  - [ ] Warn on dangling script references
  - [ ] Warn on missing resources (template, script, model)
  - [ ] Warn on circular transitions
  - [ ] Detect missing door hooks for GIT doors
- [ ] Compilation hints:
  - [ ] Test compile module → report errors
  - [ ] Validate GFF data integrity

### F. Batch Operations
- [ ] Align objects:
  - [ ] Align to grid
  - [ ] Align to first selected object
  - [ ] Distribute evenly across area
- [ ] Duplicate with array:
  - [ ] Create N copies in grid pattern
  - [ ] Create copies along path
  - [ ] Configurable offset/rotation
- [ ] Convert/batch-change:
  - [ ] Change all creature appearances
  - [ ] Change all lighting properties
  - [ ] Rename tags with pattern matching

### G. Comparison/Diff View
- [ ] Load two module versions side-by-side:
  - [ ] Highlight differences
  - [ ] Show object additions/removals
  - [ ] Compare property changes
  - [ ] Visual diff in viewport

### H. Prefab/Archetype System (Future)
- [ ] Save object groups as prefabs:
  - [ ] Save selection as reusable block
  - [ ] Instance prefabs with unified editing
  - [ ] Lock prefab instances to prevent direct editing
- [ ] Prefab variants:
  - [ ] Create variant with overrides
  - [ ] Propagate changes to instances

---

## TIER 4: LOW PRIORITY (Quality-of-Life)

### A. Rendering & Aesthetics
- [ ] Custom material for selected objects (highlight color)
- [ ] Gizmo size/color customization
- [ ] Shading mode (smooth, flat, normal)
- [ ] Background skybox rendering option
- [ ] Fog in viewport (match area fog)
- [ ] Wireframe transparency control

### B. Measurement & Debugging Tools
- [ ] Distance measurement tool:
  - [ ] Click two points → show distance
  - [ ] Useful for level layout planning
- [ ] Angle measurement
- [ ] Area calculation (for encounter zones, etc.)
- [ ] FPS/performance profiler in editor viewport

### C. Documentation & Help
- [ ] Context-sensitive help:
  - [ ] Hover on fields → tooltip
  - [ ] Help panel explaining each property
- [ ] Tutorial mode:
  - [ ] Step-by-step guide for new users
  - [ ] Suggested workflows
- [ ] Cheatsheet:
  - [ ] Common keyboard shortcuts
  - [ ] Workflow tips

### D. Preferences & Settings
- [ ] Configurable keybinds
- [ ] Grid and snap settings
- [ ] Gizmo appearance
- [ ] Camera speed
- [ ] Auto-save frequency
- [ ] Theme (dark/light mode)

### E. Export Utilities
- [ ] Export to format suitable for external tools (Blender, etc.)
- [ ] Generate report (object count, script summary, etc.)
- [ ] Asset inventory (used models, textures, scripts)

---

## PRIORITY IMPLEMENTATION ORDER

### Phase 1: Foundation (MVP)
Focus on TIER 1 essentials for basic level editing:

1. **Unified 3D Viewport** with LYT room rendering + GIT object placement
2. **Transform Tools** (move/rotate) with snap-to-grid
3. **Object Selection & Hierarchy** panel
4. **Property Inspector** for basic object editing
5. **File I/O** (load/save ARE, LYT, GIT)
6. **Undo/Redo** system
7. **Room Management** (LYT editing in viewport)

**Outcome:** Users can load existing modules, move objects, edit properties, and save.

---

### Phase 2: Usability (Core Enhancement)
Build on Phase 1 with TIER 2 features:

1. **Advanced Lighting Editor** (ARE ambient + sun)
2. **VIS (Visibility) Editor** with graph visualization
3. **Trigger/Encounter Editors** with geometry
4. **Door/Transition Setup** with visual linking
5. **Advanced Object Management** (grouping, layers, search)
6. **Pathfinding (PTH) Editor**
7. **Scripting Integration** (script editor + validation)

**Outcome:** Users can fully customize area lighting, setup encounters, manage visibility, and implement scripts.

---

### Phase 3: Polish (Refinement)
Add TIER 3 features for workflow enhancement:

1. **Advanced Viewport Features** (minimap, performance profiling)
2. **Template Management** (browser, overrides, bulk replacement)
3. **Animation/Effect Preview**
4. **Validation & Error Reporting**
5. **Batch Operations** (align, duplicate array, mass changes)
6. **Comparison/Diff View**

**Outcome:** Professional-grade editing with performance optimization and advanced workflows.

---

### Phase 4: Polish+ (Quality-of-Life)
Add TIER 4 features and refinements:

1. **Rendering & Aesthetics** customization
2. **Measurement Tools**
3. **Documentation & Help system**
4. **Preferences & Settings**
5. **Export Utilities**
6. **Prefab System** (stretch goal)

**Outcome:** Fully-featured, user-friendly level editor matching industry standards.

---

## Feature Dependencies & Notes

### Critical Warnings
- **WOK/Walkmesh:** Currently read-only in most tools. Real walkmesh editing requires specialized knowledge. Recommend surfacing collision visualization but flag as "advanced."
- **VIS Generation:** Consider auto-generation from room adjacency, but allow manual override for optimization.
- **Pathfinding:** PTH regeneration might be automatic based on creature spawn points and waypoints.

### Workflow Assumptions
- **Per-Room Editing:** Users may edit one room's objects at a time (filter by room), which simplifies UI.
- **Template Lock:** Objects inherit properties from UTC/UTD/UTP. Only overrides are stored in GIT. This affects bulk edits.
- **Script Validation:** Assume scripts are pre-compiled (NCS). Editor can validate references but not recompile.

### Performance Considerations
- Large areas (100+ objects) need efficient viewport rendering (LOD, culling).
- Undo stack should be bounded (e.g., last 100 operations).
- VIS computation for large areas may require background threading.

---

## Summary Table

| Feature Area | TIER 1 | TIER 2 | TIER 3 | TIER 4 |
|--------------|--------|--------|--------|--------|
| **Viewport** | Basic 3D + modes | Lighting + VIS | Minimap + profiling | Aesthetics |
| **Transform** | Move/rotate/grid | - | Batch align | - |
| **Rooms** | Add/delete/position | - | - | - |
| **Objects** | Place/select/props | Advanced management | Batch ops | - |
| **Lighting** | - | Full editor | - | - |
| **Scripting** | - | Event binding | - | Help |
| **Validation** | - | Error checking | Diff view | - |
| **Polish** | Undo/redo | Auto-save hints | Performance | UI themes |

---

## Epilogue: Industry Benchmark Comparison

How KotOR Module Designer should map to industry standards:

| Industry Feature | KotOR Equivalent |
|------------------|-----------------|
| **Unity Hierarchy** | GIT object tree + LYT rooms |
| **Unreal World Outliner** | Custom hierarchy panel |
| **Hammer VisGroups** | Layer system for GIT objects |
| **Hammer Entity I/O** | Trigger scripts + waypoint linking |
| **Radiant Light Editor** | ARE lighting + VIS occlusion |
| **CryEngine Terrain Editor** | LYT room placement (rooms = terrain tiles) |
| **CryEngine Vegetation** | GIT placeables + encounters |
| **All Editors: Gizmos** | Unified transform tools |
| **All Editors: Property Panels** | GIT/ARE/LYT property inspectors |

By implementing the above checklist, KotOR Module Designer will achieve **parity with professional level editors** for the specific tasks of area/module authoring.

---

**End of Research Document**

*Last Updated: March 2026*
*Status: Research Complete — Ready for Implementation Planning*
