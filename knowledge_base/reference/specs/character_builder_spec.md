# GhostRigger Character Builder & Rendering Redesign Spec

## 1. Executive Summary

GhostRigger should shift from a generic, crowded, multi-purpose character-builder tab into a **dedicated, task-focused Character Builder window/workspace**.

The core thesis of this redesign is:

> **Template-guided KOTOR rig transfer + manual rigging + truthful GPU viewport + modular asset picker + validation-first workflow**

This means the redesigned Character Builder must:

1. **Open as its own workspace/window** when the user enters character-building mode.
2. **Default to KOTOR-safe template transfer workflows** for heads and bodies.
3. **Also provide professional-feeling manual rigging tools** with transform gizmos, symmetry, region targeting, and weight editing.
4. **Render honestly** using a GPU-backed viewport with a real depth buffer, not CPU painter/depth-sort approximations.
5. **Expose modular asset assembly** for all major skin/part meshes: heads, headless bodies, eyeballs, teeth, tongues, hair, lashes, accessories, and hooks.
6. **Validate continuously** against KOTOR-specific requirements such as hooks, facial bones, supermodels, seam alignment, and export compatibility.
7. **Support modern interchange** to FBX/glTF/OBJ while preserving KOTOR-specific metadata for round-trip and Unreal-facing workflows.

This spec is intended for the AI developer / engineering team implementing the redesign.

---

## 2. Sources Audited

### Core repositories and tools

| Tool / Repo | Link | Purpose |
|---|---|---|
| **GhostRigger / Kotor-3D-Model-Converter** | https://github.com/CrispyW0nton/Kotor-3D-Model-Converter | Primary codebase; current model viewer, animation, character builder, module editor, and exporters. |
| **PyKotor** | https://github.com/OldRepublicDevs/PyKotor | KOTOR/TSL file-format backend; useful for resources, textures, 2DA, MDL/TPC/GFF handling. |
| **KotorBlender** | https://github.com/seedhartha/kotorblender | Strong DCC-side reference for KotOR model import/export, armature rebuild, animations, and asset workflows. |
| **KotOR.js** | https://github.com/KobaltBlu/KotOR.js/ | Modern engine/tool UX reference; useful for viewport architecture, modular tooling, and lip-sync editor precedent. |
| **reone** | https://github.com/seedhartha/reone | Open-source KOTOR/TSL engine reference for resource loading and runtime-oriented architecture. |
| **xoreos** | https://github.com/xoreos/xoreos | Engine-level reference for Aurora/Odyssey-style loading and rendering discipline. |
| **ufbx** | https://github.com/bqqbarbhg/ufbx | Robust FBX/OBJ ingestion candidate for skeletons, meshes, skinning, and animation import. |
| **FBX2glTF** | https://github.com/facebookincubator/FBX2glTF | Useful modern interchange reference and conversion helper for FBX → glTF/GLB workflows. |

### Community and research references

In addition to source repositories, this spec incorporates practical KOTOR modding research from community sources such as **Deadly Stream**, modding discussions, and related documentation covering:

- custom head creation,
- facial rig preservation,
- headless body workflows,
- headhook/AuroraBase alignment,
- supermodel dependency and validation,
- K1 ↔ K2 porting issues,
- LIP/lip-sync workflows,
- facial animation failures due to bad weights/bonemaps,
- helper hooks such as `MaskHook` and `GoggleHook`.

These findings consistently support the same conclusion:

> **For KOTOR heads and humanoid bodies, template-guided transplant onto a known-good target-game rig is safer and more reliable than generic autorigging.**

---

## 3. Video UX Analysis

The uploaded rigging demo shows a **clean dedicated rigging workspace** with the following characteristics:

- a **large 3D viewport on the left**,
- a **tall right control sidebar**,
- simple **camera view buttons**,
- **undo/redo** history controls,
- a **reset** command,
- **bone display toggles**,
- a **guided linear workflow**,
- **transform gizmos** for direct manipulation,
- **direct joint manipulation** in the viewport,
- fast **front/side/top** inspection.

### What GhostRigger should adopt

GhostRigger should adopt the following experience-level traits from the demo:

1. **Dedicated workspace feel**  
   The rigging experience should not feel like one tab among many. It should feel like entering a purpose-built editing mode.

2. **Viewport-first design**  
   The viewport must dominate the interface. Rigging is spatial; the viewport should be the primary surface, not a secondary preview.

3. **Tight control surface**  
   The right-side panel should expose only the tools relevant to the current mode.

4. **Low-friction camera switching**  
   One-click front/left/right/top/back views are essential for proportion checks and rig alignment.

5. **Immediate direct manipulation**  
   Users should be able to click joints/bones and move them using gizmos without opening layered dialogs.

6. **Linear, guided workflow**  
   The user should feel guided from assembly → rig → face → preview → export.

### What GhostRigger should improve beyond the demo

GhostRigger must go further than the demo in these areas:

1. **KOTOR-specific intelligence**  
   The demo is generic; GhostRigger must validate supermodels, hooks, seam alignment, facial rigs, and head/body attachment rules.

2. **Modular skin-part assembly**  
   The user must be able to choose from all relevant in-game skin parts: eyes, teeth, tongue, hair, lashes, accessories, and body/head variants.

3. **Facial close-up workflow**  
   The demo focuses on body rigging; GhostRigger must add a dedicated facial validation and editing mode.

4. **Symmetry and regional rigging assistance**  
   Manual rigging must support mirror editing, centerline locking, region masks, and brush-based weight edits.

5. **Truthful rendering**  
   The viewport must not lie about occlusion or UV behavior. Depth bugs and tiling bugs undermine rigging trust.

---

### Screenshot references from the demo

#### 1. Overall workspace layout

![Demo screenshot - full rigging workspace](https://www.genspark.ai/api/files/s/ZxE1LHpq?token=Z0FBQUFBQnAzRGxkdTVNSnhyX1EyZjBUNmY3V0dvSktDY0xCZXZNMEM3NTl4RXBTWmxNZTU2RzV5bG0wTEN4T3dOcG9Xc0hzQjJqd09vWU9DRHd5NzUyZy1ncHhKQWFxSnpwQkJqTWRwa1R6b0IydWJPNTl2WGh3Y0hqZFFiWXBmV05BeWh0LVdsNV9tcXVyb3JTazYwZXZneDNlNE50Q05nd1I4UGdaWlQyekxPUDVTYk5JQ2JkSFRNemRuazMycF8tbDJwNVg5VllhQ1ZYekxkU0NNbGR2Sk1EdENFblY5UUtla19EWjQyaWtGbXhLcVBEZkZtR3g4YmRDZm01M1RaTjRZaVQ4YTJiTno3NFdRQ0tRdVZ1eGI0a1ZpRkpoTlE9PQ)

**Design takeaway:** The viewport is the dominant surface, while the sidebar remains tall, predictable, and secondary. GhostRigger should prioritize this same visual hierarchy.

#### 2. Head and neck editing focus

![Demo screenshot - head and neck adjustment](https://www.genspark.ai/api/files/s/Tn1bGltN?token=Z0FBQUFBQnAzRGxkMm1QNnBCNUZEMWwyZm5hUEktSXotM3JRMmxVMkROekpsQ3pwUGZrNWV5V1QzRXc0UE8xR3BTaU9TbHJQREg5QlZjQ1NRNGNnLW0xRGIybTR5aHBhQ1h6T2E3VEZyV0xfeUNJX0hzQmxDSUUzVU1zaGRzWWxGUlliVVk5R3I4OFB1aDBHZkI1NTdESDR0SEVOd09QQ1ZpaHVvcWktTVBWT2RQOWpzV1RhSlNkdkxER210WlNMOTd4TmRMSnNUQ21zX2JLcEVvRlpFTXJfQUhNeXM4UXdkdmpyOUdVaVdpUmMyeW5Oa0xfSmk1M0ptbWRJRlNTZ3EyMmNKVEpCOVVHYURHUlllYVl1NC1QWnZoMVZDUE9SUUE9PQ)

**Design takeaway:** GhostRigger needs a dedicated close-up facial/head workflow, not just a full-body rigging mode.

#### 3. Side inspection for pelvis and leg alignment

![Demo screenshot - side view inspection](https://www.genspark.ai/api/files/s/JmJS6EI6?token=Z0FBQUFBQnAzRGxkTWtsRW5HVGVNb05HWXlwcE9lOEJTOGloaGpnbHZRWkJnd2xNa2VIaXdyaFNPQ2N3Q2NOWWZadC1GdkFEOS1UYTk4MmVzZ1EtTHJacFJwaUdCQXUzbFA0UlkyU3RxUkVwM2VuN01hZTRRNUpxdVI1emI5NksxWXlNOExwUHBZNHBSeHVGV1B3akhFSXYtTkh5ZVE4V1YxNTJhZzlXc0pQOVEwUzY1bS1EeE9LMU1YbjFweko5VUVuZmJmdjN6MjdOXy1mbkRxc2dVZTRTcF9aRkVpb1FfUldGTGpEd05EYTY4X1B5eURPV3FhYnR2WTVGcnd3LVhuOHFTRXhydm5tVWFJSFBYMHc4dWNhLUFFcEIwSDM3TVE9PQ)

**Design takeaway:** Orthographic-like inspection views should be one-click accessible and central to rig correctness checks.

#### 4. Full-body proportion check

![Demo screenshot - full body alignment](https://www.genspark.ai/api/files/s/ZY0jKxiq?token=Z0FBQUFBQnAzRGxkTVhfMjY1YnRrMnJmWS1vRF9POTlOSHRISkQ0SkZlUDdwZVdra2ptUmxzYXdzSlNTcW1aUlZaOU9wWm90ZE9jTnBGZ21EeXRGMHgwRnN6ZldMQlJJd25YRERZX2ItYnlfTHVQbGtBOEF0VW5wMEtGVlF1VC1nTTRGVmVNd2dtak54dEdqWTVId0RLSElLampVaWNHWEx0OVJwcGJhX1lObTVPdHV2RDZOeFFNUXNXR0owNkFuUm1tTDg2XzRZaTdjWDhRQVN6eTN6Tk4yX0ppcXVYSzY2Vy1UVGdQMkdwWVlHbnZyNTVHN3pESlUxMHB5YXFESWtSak9JektfUlBXWnF5cUtIT0FNRlVVak9vR0NoUENXOVE9PQ)

**Design takeaway:** The builder must support fast whole-character checks for scale, limb length, foot placement, and head/body coherence.

#### 5. Elbow symmetry and limb editing

![Demo screenshot - elbow adjustment and symmetry](https://www.genspark.ai/api/files/s/AvbL1920?token=Z0FBQUFBQnAzRGxkY2lscFhaa3l4cFRYcmx0STdKYTZEWF8xamRFZUVtREczVW1KaFhLZDhJQm9vNE5VRmZTVXdwQkpPamFKYzFrOExVeUs5VTRTREhGcjcxa3NnN2s0MzZrdGZ5RXdVNWNQWUUwVFZPTWltZy15eUxNRy1VVzFwdUp1enQxVTlVNF9zOW5TUDg0MFdkNTRJNnlnckM5OXJBSW5WcmZoRzNSb2JwV21JdWhPZnptbVl2N2VpMlAwQXAxT0ZqdjNuSnJhRUJkYjlKM29nRFpTazM0NnVnUTRCZl9KSUh0U2V4V1ptQTFqSUhoRkVndEFJNTNkTEJPcmYyQ0Zsb2lSUUx5cUMxRGpVVzJaOVdXTVF5cU5kbDI3Z1E9PQ)

**Design takeaway:** GhostRigger must provide strong mirrored editing for paired limbs and comparable facial left/right structures.

---

## 4. Design Principles Synthesized from the 3 Attached Books

### Book 1: modern OpenGL / rendering architecture guide

#### Relevant principles

| Principle | Summary | Concrete implication for GhostRigger |
|---|---|---|
| **VBO/VAO-based rendering** | Vertex data should live in GPU memory and be bound via explicit vertex-array state. | **Must** move viewport rendering away from CPU compositing toward GPU-resident mesh buffers. |
| **Real depth buffering** | Overlap and occlusion should be resolved by the hardware depth buffer. | **Must** replace painter/depth-sort approximations for default viewport rendering. |
| **Alpha testing / cutout handling** | Hair cards, lashes, and similar assets need threshold-based handling before general transparency. | **Must** add a dedicated alpha-tested cutout pass for lashes, hair cards, and similar materials. |
| **View/projection separation** | Camera logic depends on explicit view and projection matrices. | **Must** support stable orbit, inspection views, and close-up facial cameras with reproducible camera state. |
| **Batching / instancing** | Rendering should minimize redundant CPU-GPU traffic and draw overhead. | **Should** batch static preview elements and support efficient part toggling. |
| **Viewport architecture** | Rendering should be treated as a layered subsystem, not ad hoc drawing logic. | **Must** formalize viewport passes, debug overlays, and render state ownership. |

### Book 2: mesh processing, skeletons, bind pose, skinning, retargeting guide

#### Relevant principles

| Principle | Summary | Concrete implication for GhostRigger |
|---|---|---|
| **Bind pose matters** | Skinning and rig transfer only work predictably if the bind/reference pose is explicit. | **Must** store canonical bind pose data in the internal character model and use it during transfer/export. |
| **Bone data structure** | Bones must carry name, index, influenced vertices, and offset/bind matrices. | **Must** formalize a canonical skeleton/bone model rather than relying on loose importer state. |
| **Skin weights sum to 1** | Vertex weights must be normalized to avoid unstable deformation. | **Must** provide normalize/repair tools and validation. |
| **Overlap zones at joints** | Smooth deformation needs controlled weight overlap around bends. | **Should** expose smoothing tools and region-aware defaults for shoulders, elbows, jaw, lips, and neck. |
| **Twist links** | Axial rotation artifacts benefit from additional twist structures where applicable. | **Should** support helper/twist logic in canonical scene representation, even if export reduces to KOTOR-compatible structures. |
| **Retarget maps** | Rig transfer requires joint-name mapping and sometimes axis remap. | **Must** define explicit source→template joint maps and K1↔K2 conversion maps. |
| **Recursive transforms** | Skeleton evaluation must walk hierarchy correctly. | **Must** centralize transform propagation in the animation/scene layer. |

### Book 3: engine architecture, editor/tool architecture, asset pipeline, UI ergonomics guide

#### Relevant principles

| Principle | Summary | Concrete implication for GhostRigger |
|---|---|---|
| **Single-source-of-truth data** | Runtime and tools should share canonical data when possible. | **Must** create a canonical internal character/scene model shared by importer, viewport, validation, and exporter. |
| **Modular subsystems** | Rendering, animation, resources, and tools should be loosely coupled. | **Must** separate assembly, rigging, rendering, validation, and export services. |
| **Scene graph discipline** | Hierarchical assets and attachments should be represented explicitly. | **Must** represent head/body/hook attachments in a robust graph model. |
| **Asset registry** | Assets need stable identifiers and predictable lookup. | **Must** use GUID/string-id style references for parts, textures, templates, and exports. |
| **Minimal modal complexity** | Professional tools reduce nested dialogs and surface relevant controls inline. | **Must** redesign Character Builder around modes and panels, not stacked popups. |
| **Search / filter / batch operations** | Large asset libraries require fast lookup. | **Must** provide searchable part pickers, compatibility warnings, and recent/favorite flows. |
| **Explicit startup/shutdown** | Complex tools should initialize in a visible, deterministic order. | **Should** formalize subsystem startup for viewport, resource managers, and services. |
| **Hot reload** | Asset iteration improves dramatically with reload-friendly architecture. | **Should** support refresh/reload of selected parts and textures during editing. |

---

## 5. Problem Statement: Current GhostRigger Character Builder Pain Points

Prior research and repo review indicate the current Character Builder has the following problems:

1. **Too many mixed responsibilities in one complex panel**  
   Assembly, rigging, snapping, export, and diagnostics are too tightly mixed.

2. **CPU depth-sorted renderer causes false visuals**  
   This creates misleading occlusion, especially for inner face geometry such as eyeballs, teeth, tongue, lids, and lashes.

3. **Bad UV wrapping / tiling interpretation**  
   Out-of-range UV behavior and tiling assumptions are not consistently handled.

4. **Manual rigging experience is difficult**  
   The current builder does not feel like a professional direct-manipulation rigging environment.

5. **Insufficient symmetry tooling**  
   Mirror editing, centerline locking, mirrored weights, and paired joint workflows need to be stronger.

6. **Asset selection is not clean enough**  
   Users need explicit, searchable access to all relevant skin meshes and attachments:
   eyes, teeth, tongue, hair, lashes, hooks, headless bodies, and variants.

7. **No dedicated close-up facial validation workflow**  
   Face editing and validation should not be buried inside a general model UI.

8. **Export path is confusing and validation is insufficient**  
   Users need pre-export checks and explicit output targets for KOTOR, FBX, glTF/GLB, and OBJ.

---

## 6. Product Vision

When the user enters Character Builder, a **dedicated Character Builder window** should open.

It should feel like a **professional DCC/game tool**, not a crowded side tab.

The redesigned builder must support both:

1. **template-guided KOTOR-compatible rig transfer**, and  
2. **manual rigging/editing with symmetry, transform gizmos, and validation**.

It must support selecting all major skin/part meshes from game assets, including:

- head shells,
- eyeballs,
- teeth,
- tongue,
- hair,
- lashes,
- accessories,
- hooks,
- headless bodies,
- body variants,
- species/race-specific components where applicable.

It must also support:

- **K1/K2 target selection**,
- **head-body snapping via `headhook`**,
- **facial validation**,
- **animation preview**,
- export to:
  - **KOTOR**
  - **FBX**
  - **glTF/GLB**
  - **OBJ**

---

## 7. Proposed UX / Window Layout

### High-level design

The Character Builder should be a **dedicated window/workspace** with five major regions:

1. **Top toolbar**
2. **Left asset/assembly browser**
3. **Center GPU viewport**
4. **Right contextual inspector**
5. **Bottom validation/log/timeline strip**

### Primary modes

- **Assembly**
- **Rig**
- **Face**
- **Preview**
- **Export**

These modes should be explicit and top-level. The design should be **simpler than the current builder while more powerful**.

---

### ASCII wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ Character Builder                                                                           │
│ [Project] [K1/K2] [Assembly] [Rig] [Face] [Preview] [Export]   [Undo] [Redo] [Reset]      │
│ [Front] [Back] [Left] [Right] [Top] [Bottom] [Persp] [Ortho] [Symmetry] [Snap] [Validate] │
├───────────────────────┬───────────────────────────────────────────────┬──────────────────────┤
│ LEFT PANEL            │ CENTER VIEWPORT                              │ RIGHT PANEL          │
│ Asset / Assembly      │ GPU 3D View                                  │ Context Inspector    │
│ -------------------   │ -------------------------------------------   │ -------------------  │
│ Search parts          │ Character / head / body                       │ Mode-specific tools  │
│ Recent/Favorites      │ Bones / gizmos / overlays                     │ Selection details    │
│ Body templates        │ Turntable / orbit / inspect                   │ Symmetry controls    │
│ Head templates        │ Lighting presets                              │ Weight paint tools   │
│ Eyes                  │ UV / depth / normals debug                    │ Hook settings        │
│ Teeth                 │ Animation preview                             │ Validation details   │
│ Tongue                │                                               │ Export settings      │
│ Hair                  │                                               │                      │
│ Accessories           │                                               │                      │
│ Hooks                 │                                               │                      │
├───────────────────────┴───────────────────────────────────────────────┴──────────────────────┤
│ BOTTOM STRIP: Validation | Warnings | Timeline | Animation Scrubber | Export Log | Stats   │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

### UX goals

| Goal | Requirement |
|---|---|
| Reduce clutter | **Must** isolate workflows by mode. |
| Preserve power | **Must** keep advanced tools available in-context. |
| Increase trust | **Must** show accurate render/debug output. |
| Reduce ambiguity | **Must** expose selection, compatibility, and validation state clearly. |
| Improve flow | **Should** guide user through a left-to-right, top-to-bottom workflow. |

---

## 8. Detailed UX Requirements

## 8.1 Assembly Mode

### Purpose
Assemble a valid character from compatible KOTOR parts and/or imported donor meshes.

### Requirements

#### Core selection controls

The user must be able to choose:

- **game target**: K1 or K2
- **race/species/family**
- **body template**
- **head template**
- **eyes**
- **teeth**
- **tongue**
- **hair**
- **lashes**
- **accessories**
- **hooks / helper objects**

#### Browser features

| Feature | Priority | Notes |
|---|---|---|
| Searchable asset list | Must | Filter by name, type, game, species, compatibility. |
| Thumbnail preview | Must | Show quick visual identity for heads, bodies, and major parts. |
| Favorites / recent | Should | Useful for iterative workflows. |
| Compatibility warnings | Must | Warn if K1 part is used in K2 family without conversion, etc. |
| Source filter | Should | Vanilla game, imported donor, current project, favorites. |

#### Workflow rules

- **Must** support headless body + separate head workflows.
- **Must** support snap preview for head/body assembly using `headhook`.
- **Must** allow part swapping without destroying rig state where possible.
- **Must** preserve hidden but required helper objects in the assembly graph.
- **Must Not** silently attach incompatible rigs without warning.

---

## 8.2 Rig Mode

### Purpose
Transfer KOTOR-safe rigs or manually adjust rig placement and weights.

### Requirements

#### Rigging options

| Feature | Priority | Notes |
|---|---|---|
| Template transfer | Must | Default for KOTOR heads and humanoid bodies. |
| Manual joint move/rotate | Must | Gizmo-driven, direct manipulation. |
| Mirror / symmetry editing | Must | Optional and per-axis configurable. |
| Lock centerline | Must | For nose, jaw center, spine, sternum, neck, chin, etc. |
| Region-based selection | Must | Fast access to face/body rig zones. |
| Weight painting | Must | Brush-based; visualized in viewport. |
| Normalize weights | Must | Repair invalid weights. |
| Smooth weights | Must | Joint transition cleanup. |
| Mirror weights | Must | Especially important for paired features. |

#### Region-based selection examples

**Face regions**
- jaw
- upper lip
- lower lip
- lip corners
- lids
- brows
- cheeks
- neck
- ears (if relevant)
- eyes
- tongue / mouth interior

**Body regions**
- clavicle
- shoulder
- elbow
- wrist
- spine
- pelvis
- thigh
- knee
- ankle
- foot

#### Manual manipulation rules

- **Must** support click-selecting joints in viewport.
- **Must** support move/rotate gizmos.
- **Should** support numeric transform entry.
- **Should** support stepwise guided joint editing for beginners.
- **Must** allow per-side unlock for asymmetrical characters.
- **Must Not** overwrite donor mesh placement without undo support.

---

## 8.3 Face Mode

### Purpose
Dedicated close-up workflow for facial rig validation and refinement.

### Requirements

- **Must** switch viewport to a close-up facial camera preset.
- **Must** allow selecting facial bones directly.
- **Must** provide quick presets for:
  - jaw open/close,
  - blink,
  - mouth open,
  - test phonemes,
  - eye look directions.
- **Must** preview `MaskHook` and `GoggleHook` alignment.
- **Must** run seam and clipping checks around:
  - neck seam,
  - lips,
  - eyelids,
  - eyeballs,
  - teeth,
  - tongue.
- **Should** support left/right compare overlays.
- **Should** support x-ray and depth debug for face internals.

---

## 8.4 Preview Mode

### Purpose
Evaluate assembly, skinning, and rendering before export.

### Requirements

- **Must** support:
  - idle
  - walk
  - talk
  - test expression
  - test phoneme
- **Must** include lighting presets:
  - neutral studio
  - high contrast
  - overhead
  - in-game approximate
- **Must** include viewport debug modes:
  - wireframe
  - textured
  - weights
  - normals
  - UV
  - depth
  - skeleton
- **Should** support turntable playback.
- **Should** support side-by-side compare against template.

---

## 8.5 Export Mode

### Purpose
Export validated assets for KOTOR and external pipelines.

### Requirements

| Export Type | Priority | Notes |
|---|---|---|
| KOTOR export | Must | MDL/MDX + associated metadata workflow. |
| FBX export | Must | Main skeletal export for Unreal/DCC workflows. |
| glTF/GLB export | Must | Modern interchange / preview / web-friendly export. |
| OBJ export | Should | Static/convenience export. |
| Sidecar JSON export | Must | Preserve KOTOR-specific metadata. |
| Validation report export | Must | Human-readable export summary and warnings. |

---

## 9. KOTOR-Specific Technical Requirements

## 9.1 Real workflow for KOTOR custom heads and headless bodies

Based on prior research, the real KOTOR-safe workflow is:

1. **Use canonical target-game rigs/templates** whenever possible.
2. **Transfer donor mesh onto target-game rig** rather than trying to generic-autorig everything.
3. **Preserve required facial bones and helper hooks**.
4. **Attach heads to bodies via the body `headhook` / head `AuroraBase` relationship**.
5. **Validate correct supermodel assignment** by game and animation family.
6. **For K1↔K2 conversion, re-home the mesh to the target rig** rather than simply renaming bones.

### Key rule

> **Canonical target-game rig/template transfer is safer than generic autorig for KOTOR heads and headless bodies.**

---

## 9.2 Critical KOTOR concepts

| Concept | Meaning | Why it matters |
|---|---|---|
| `headhook` | Body-side attachment point for head placement | Determines final head positioning/alignment. |
| `AuroraBase` | Root/base attachment context on the head model | Participates in how the head is placed relative to body. |
| `MaskHook` | Helper hook for mask equipment | Required for gear alignment and compatibility. |
| `GoggleHook` | Helper hook for goggle equipment | Required for headgear positioning. |
| `head_g` | Main head bone/node | Central to facial/head deformation hierarchy. |
| `necklwr_g` | Lower neck bone/node | Important for seam continuity and neck deformation. |
| `neck_g` | Neck bone/node | Important for head-neck motion and weighting. |
| `f_jaw_g` | Jaw bone/node | Critical for mouth opening and speech-like motion. |
| Upper/lower lip corner bones | Facial lip deformation bones | Required for better speech/blink/facial behavior. |
| Supermodels | Animation inheritance chain | Determines animation availability and behavior. |
| Bonemap / skin weights | Bone references + weighting | Incorrect maps cause broken deformation. |
| `appearance.2da` | Creature/body appearance table | Controls model association and usage rules. |
| `heads.2da` | Head selection table | Controls how heads are registered and referenced. |
| `LIP` files | Lip-sync animation data | Needed for dialogue mouth movement in-game. |

---

## 9.3 Common KOTOR failure modes

| Failure | Likely cause |
|---|---|
| Gaping mouth | Wrong facial rig or bad jaw/lip weights |
| Detached lips/cheeks | Target mesh not re-homed to correct rig |
| Missing blinks | Missing or incorrect eyelid/eye/facial bone setup |
| Misweighted jaw | Incorrect weight transfer or broken facial bonemap |
| Lip/face clipping | K1/K2 rig mismatch or poor seam fitting |
| Missing hook parenting | `MaskHook` / `GoggleHook` lost or misparented |
| Wrong animation behavior | Incorrect supermodel assignment |
| Broken eye motion | Eye-related bones misnamed, missing, or misweighted |

### Validation requirement

GhostRigger **Must** detect these issues before export whenever possible.

---

## 10. Rendering Redesign Spec

## 10.1 Rendering direction

The default viewport should move from **CPU painter/depth-sort behavior** to **GPU-backed rendering**.

### Required architecture

Inspired by Book 1 and the current repo direction, GhostRigger should adopt:

1. **VBO/VAO-backed mesh upload**
2. **Real depth buffer**
3. **Opaque pass**
4. **Alpha-tested cutout pass**
5. **Transparent pass**
6. **Skeleton overlay pass**
7. **Debug visualization passes**

---

## 10.2 Required render passes

| Pass | Requirement | Purpose |
|---|---|---|
| Opaque pass | Must | Render main solid geometry with depth write/test enabled. |
| Alpha-tested cutout pass | Must | Handle hair cards, lashes, and cutout materials without false sorting. |
| Transparent pass | Should | Handle true transparency after opaque/cutout geometry. |
| Skeleton overlay pass | Must | Draw selectable rig/bones/gizmos clearly over model. |
| Debug passes | Must | UVs, normals, weights, depth, selection, face internals. |

---

## 10.3 Current bug fixes to explicitly address

### Bug: eyeballs visible through head
**Cause:** false occlusion from CPU sorting.  
**Fix:** render face shell and eyeballs through real per-pixel depth testing.

### Bug: incorrect UV wrapping / tiling
**Cause:** mesh-space assumptions and/or destructive UV handling.  
**Fix:** preserve raw UVs and apply wrap behavior in sampler/material logic.

### Bug: misleading alpha/depth behavior
**Cause:** insufficient render-stage separation for cutout vs transparent surfaces.  
**Fix:** separate alpha-tested and transparent passes.

---

## 10.4 Texture / sampler rules

| Rule | Priority |
|---|---|
| Do not normalize/clamp UVs destructively | Must |
| Preserve out-of-range UVs | Must |
| Apply wrap mode in material sampler | Must |
| Support KOTOR TPC/TGA/TXI behavior where feasible | Must |
| Add UV/sampler debug view | Must |
| Show material state in UI | Should |

### Material/debug visibility

The user should be able to inspect:

- texture source,
- wrap mode,
- alpha mode,
- UV range,
- whether the texture came from TPC/TGA,
- any TXI-like interpretation used by the tool.

---

## 10.5 Renderer acceptance criteria

The renderer is considered correct enough for this phase when:

- **Eyeballs no longer appear through opaque face shells** in normal preview.
- **Teeth and tongue** are correctly occluded by lips/cheeks where expected.
- **Hair cards / lashes** render predictably in cutout mode.
- **Out-of-range UVs** display using wrap/sampler rules rather than destructive correction.
- **Depth debug mode** clearly shows shell ordering and internal geometry.
- **Selection and skeleton overlays** remain usable without corrupting depth interpretation.

---

## 11. Data / System Architecture

GhostRigger should use a **single internal canonical scene/character model** shared by tools and runtime-like systems.

### Recommended subsystems

| Subsystem | Role |
|---|---|
| Asset registry | Stable IDs and metadata for templates, parts, textures, exports |
| Resource resolver | Locate K1/K2 assets, project assets, imported assets |
| Canonical skeleton/mesh/skin model | Single source of truth for assembled character state |
| Render scene | GPU-ready scene representation and debug layers |
| Character assembly service | Build assembled character from parts/templates |
| Rig transfer service | Template-guided transfer and K1/K2 re-home operations |
| Manual rigging service | Joint editing, symmetry, weighting tools |
| Validation service | KOTOR checks, geometry checks, export checks |
| Export service | KOTOR, FBX, glTF/GLB, OBJ, sidecar JSON |

### Architectural rules

- **Must** use GUID/string-id based asset references.
- **Must** keep template, mesh, skeleton, and export metadata linked through stable IDs.
- **Should** support hot reload / refresh for project assets and textures.
- **Must** avoid duplicated internal representations where feasible.

These recommendations align directly with the tool/runtime and asset-pipeline guidance from **Book 3**.

---

## 12. Concrete Engineering Instructions by GhostRigger Area

## 12.1 `src/gui/viewport.py`

### Refactor / add

- Replace default CPU depth-sort path with a **GPU-first rendering path**.
- Introduce explicit render passes:
  - opaque,
  - alpha-tested,
  - transparent,
  - skeleton overlay,
  - debug overlays.
- Add debug visualizations for:
  - UVs,
  - normals,
  - weights,
  - depth,
  - face internals.
- Add stable camera presets:
  - front,
  - back,
  - left,
  - right,
  - top,
  - bottom,
  - face close-up.

### Outcome
Viewport becomes trustworthy and suitable for serious rigging.

---

## 12.2 `src/gui/main_window.py`

### Refactor / add

- Move Character Builder into a **dedicated window/workspace entry point**.
- Add mode switching:
  - Assembly
  - Rig
  - Face
  - Preview
  - Export
- Reduce shared-tab clutter by moving builder-specific UI out of generic main panels.
- Add toolbar commands for:
  - camera views,
  - symmetry,
  - validate,
  - reset,
  - undo/redo.

### Outcome
Character Builder becomes a clean, self-contained workflow.

---

## 12.3 `src/autorig/auto_rigger.py`

### Refactor / add

- Position this as a **fallback generic rigging path**, not the default KOTOR head path.
- Add explicit separation between:
  - generic autorig,
  - template-guided KOTOR transfer.
- Ensure output can map into canonical skeleton representation.

### Outcome
Autorig remains available but no longer drives KOTOR-safe head/body workflows.

---

## 12.4 `src/autorig/grig.py`

### Refactor / add

- Expand into the main **manual rigging service**.
- Add:
  - direct joint selection/edit support,
  - symmetry state,
  - centerline locking,
  - region presets,
  - weight normalize/smooth/mirror operations.
- Expose selection and weighting state to viewport overlays.

### Outcome
Manual rigging becomes usable and professional-feeling.

---

## 12.5 `src/autorig/accurig.py`

### Refactor / add

- Preserve as guided rigging assistance, but integrate into Rig mode as an optional helper layer.
- Add compatibility with symmetry and canonical skeleton mapping.
- Do not let this bypass KOTOR validation.

### Outcome
Guided rigging remains useful without becoming a hidden separate system.

---

## 12.6 `src/converters/mesh_converter.py`

### Refactor / add

- Route imports through a cleaner canonical scene model.
- Improve FBX/OBJ/glTF import/export handling.
- Preserve:
  - skinning,
  - skeleton hierarchy,
  - materials,
  - UVs,
  - animations,
  - metadata where possible.
- Avoid destructive UV rewriting.
- Add sidecar JSON emission support.

### Outcome
Interchange becomes reliable and round-trip aware.

---

## 12.7 `src/core/model_data.py`

### Refactor / add

- Formalize the canonical scene/character model:
  - mesh parts,
  - materials,
  - skeleton,
  - bind pose,
  - hooks,
  - metadata,
  - source template references.
- Add explicit part categories:
  - head shell,
  - eyes,
  - teeth,
  - tongue,
  - hair,
  - lashes,
  - accessories,
  - hooks,
  - body.

### Outcome
All systems operate on a single authoritative character representation.

---

## 12.8 `src/core/animation_engine.py`

### Refactor / add

- Ensure hierarchical recursive transform propagation is explicit and reusable.
- Add support for:
  - preview animation clips,
  - test facial poses,
  - test phoneme poses,
  - template-comparison preview.
- Expose skeleton palette cleanly to renderer.

### Outcome
Animation preview becomes a core validation tool.

---

## 12.9 `src/core/resource_manager.py`

### Refactor / add

- Expand resource resolution for:
  - K1 install,
  - K2 install,
  - project-local assets,
  - imported donor assets.
- Add asset indexing with stable IDs and searchable metadata.
- Support classification by:
  - game,
  - type,
  - species/family,
  - compatibility.

### Outcome
Assembly mode gets a fast, structured asset browser.

---

## 12.10 `src/core/pykotor_bridge.py`

### Refactor / add

- Centralize KOTOR-specific parsing/bridge logic here as much as feasible.
- Use this layer to expose:
  - textures,
  - model metadata,
  - resource lookups,
  - KOTOR export preconditions,
  - supermodel/hook-related data.
- Avoid duplicating KOTOR format logic elsewhere where PyKotor already solves it.

### Outcome
KOTOR-specific behavior stays consistent and maintainable.

---

## 13. Export / Interchange Strategy

### Canonical export flow

> **Internal canonical scene → KOTOR export / FBX export / glTF/GLB export / OBJ export**

### Recommendations

| Format | Role | Priority |
|---|---|---|
| KOTOR MDL/MDX workflow | Native modding/export target | Must |
| FBX | Main Unreal/DCC skeletal export | Must |
| glTF/GLB | Modern runtime/interchange export | Must |
| OBJ | Static/convenience export only | Should |

### Unreal-facing strategy

FBX and glTF should be treated as the **serious modern exports**.  
OBJ should remain a **convenience/static export**, not the main character pipeline.

### External references

- **ufbx**: https://github.com/bqqbarbhg/ufbx  
  Good candidate/reference for robust FBX/OBJ intake.
- **FBX2glTF**: https://github.com/facebookincubator/FBX2glTF  
  Useful reference/helper for modern conversion behavior.

### Sidecar JSON metadata

Every non-native export should optionally emit a sidecar JSON preserving:

- game target,
- supermodel,
- hooks,
- head/body pairing,
- material IDs,
- asset IDs,
- source templates,
- validation results,
- compatibility warnings,
- export settings.

---

## 14. Module Loading / Preview Implications

The improved asset/resource architecture should also improve **module scene assembly and preview**.

Why this matters:

- a better asset registry improves resource resolution,
- a canonical scene graph helps model placement and attachments,
- cleaner render architecture helps module previews too.

### References for discipline

- **reone**: https://github.com/seedhartha/reone
- **xoreos**: https://github.com/xoreos/xoreos
- **KotOR.js**: https://github.com/KobaltBlu/KotOR.js/

These projects are useful references for:

- resource resolution,
- scene assembly,
- game/runtime-oriented separation of concerns.

---

## 15. Lip Sync / Facial Animation Support

GhostRigger should initially focus on **lip-sync prep and facial validation**, not on inventing a brand-new phoneme ecosystem.

### Practical role of the tool

GhostRigger should support:

- audio/text organization for dialogue,
- facial rig validation,
- phoneme/test-pose preview,
- import/export of lip-related metadata where useful,
- preview hooks into the classic KOTOR lip pipeline.

### Classic workflow

The established KOTOR lip-sync pattern is broadly:

> **audio/text → phoneme/intermediate data → LIP**

GhostRigger’s first responsibility should be to make the character and face rig **ready for this pipeline**, not to replace the entire ecosystem.

### Required preview/test features

In Face/Preview modes, GhostRigger should support:

- jaw open/close,
- blink,
- test phoneme set,
- eye look directions,
- mouth-open stress test,
- talk-loop preview,
- optional scrub preview against voice audio.

---

## 16. Implementation Roadmap

## Phase 1 — Canonical character model + validation-first KOTOR workflow

**Goals**
- Define canonical scene/character data model.
- Implement template-guided KOTOR rig transfer path.
- Add KOTOR validation service.

**Outcomes**
- Safer head/body workflows.
- Pre-export validation of hooks, bones, and supermodels.

**Dependencies**
- `model_data.py`
- `pykotor_bridge.py`
- `resource_manager.py`

---

## Phase 2 — Dedicated Character Builder window + Assembly mode

**Goals**
- Create dedicated Character Builder workspace/window.
- Implement Assembly mode with searchable asset browser.
- Add part categories and compatibility warnings.

**Outcomes**
- Cleaner workflow.
- Much lower UX complexity.

**Dependencies**
- Phase 1 canonical model
- `main_window.py`
- resource indexing

---

## Phase 3 — GPU viewport migration

**Goals**
- Replace default CPU viewport behavior with GPU rendering.
- Implement depth buffer and explicit render passes.
- Add UV/depth/normals/weights debug modes.

**Outcomes**
- Honest rendering.
- Fix major visual trust issues.

**Dependencies**
- canonical render scene model
- `viewport.py`

---

## Phase 4 — Rig mode + manual rigging + symmetry

**Goals**
- Add direct joint manipulation.
- Add symmetry, centerline lock, region presets.
- Add weight painting and repair operations.

**Outcomes**
- Professional-feeling manual rigging workflow.

**Dependencies**
- Phase 2 workspace
- Phase 3 viewport
- `grig.py`
- `accurig.py`

---

## Phase 5 — Face mode + facial validation + preview

**Goals**
- Add close-up facial workflow.
- Add blink/jaw/phoneme presets.
- Add face seam and clipping diagnostics.

**Outcomes**
- Better head creation, facial fixes, and speech-readiness.

**Dependencies**
- Phase 4 rigging tools
- animation preview support

---

## Phase 6 — Modern export + broader editor integration

**Goals**
- Strengthen FBX/glTF export.
- Add sidecar JSON metadata.
- Improve module preview implications from shared architecture.

**Outcomes**
- Better Unreal-facing workflows.
- Better interoperability and future integration.

**Dependencies**
- All prior phases

---

## 17. Acceptance Criteria / Done Definition

### UI

- [ ] Character Builder opens as a dedicated workspace/window.
- [ ] Modes are explicit: Assembly, Rig, Face, Preview, Export.
- [ ] Asset browser supports search, thumbnails, and compatibility warnings.
- [ ] The workflow is simpler than the old panel.

### Renderer

- [ ] Default viewport is GPU-backed.
- [ ] Opaque geometry uses real depth buffering.
- [ ] Cutout/alpha-tested assets render in their own pass.
- [ ] UV/depth debug modes are available.
- [ ] Eyeballs are not visible through opaque heads in standard preview.

### Rigging

- [ ] Template transfer is the default KOTOR-safe path.
- [ ] Manual rigging supports gizmos and symmetry.
- [ ] Weight normalize/smooth/mirror tools are available.
- [ ] Centerline locking works.

### KOTOR validation

- [ ] Validation checks required hooks.
- [ ] Validation checks critical facial bones.
- [ ] Validation checks supermodel compatibility.
- [ ] Validation flags K1↔K2 unsafe conversions unless explicitly converted.

### Export

- [ ] KOTOR export works through validated path.
- [ ] FBX export preserves skeleton/material structure sufficiently for external use.
- [ ] glTF/GLB export is available.
- [ ] Sidecar JSON preserves KOTOR-specific metadata.

### Performance

- [ ] Viewport interaction is responsive for normal character editing workloads.
- [ ] Switching parts does not require full application restart.
- [ ] Reasonable hot reload/refresh is supported.

---

## 18. Risks and Non-Goals

### Risks

- KOTOR head/facial compatibility is sensitive to subtle rig and bonemap differences.
- K1↔K2 conversion remains structurally tricky.
- GPU migration may uncover hidden assumptions from the CPU viewport path.
- Round-trip interchange between KOTOR and modern formats may require metadata sidecars to avoid loss.

### Non-goals for Phase 1

- **Full arbitrary non-KOTOR autorig** is **not** a phase-1 goal.
- **Perfect automatic facial retargeting** is **not** a phase-1 goal.
- **A complete replacement for the existing KOTOR LIP ecosystem** is **not** a phase-1 goal.

---

## 19. Appendices

## Appendix A: Recommended external repositories and why

| Repo | Link | Why it matters |
|---|---|---|
| GhostRigger | https://github.com/CrispyW0nton/Kotor-3D-Model-Converter | Primary implementation target. |
| PyKotor | https://github.com/OldRepublicDevs/PyKotor | KOTOR format backend and tooling support. |
| KotorBlender | https://github.com/seedhartha/kotorblender | Best practical DCC reference for KotOR assets. |
| KotOR.js | https://github.com/KobaltBlu/KotOR.js/ | Modern tool/engine UX reference; useful viewport/editor patterns. |
| reone | https://github.com/seedhartha/reone | Runtime/resource architecture reference. |
| xoreos | https://github.com/xoreos/xoreos | Scene/resource/loading reference. |
| ufbx | https://github.com/bqqbarbhg/ufbx | Robust FBX/OBJ import candidate/reference. |
| FBX2glTF | https://github.com/facebookincubator/FBX2glTF | Modern interchange reference. |

---

## Appendix B: Concise glossary of KOTOR-specific terms

| Term | Definition |
|---|---|
| K1 | Star Wars: Knights of the Old Republic |
| K2 / TSL | Star Wars: Knights of the Old Republic II: The Sith Lords |
| Supermodel | Animation inheritance model chain used by KOTOR models |
| Headhook | Body attachment point for a separate head |
| AuroraBase | Base/root attachment context used in model hierarchy |
| MaskHook | Hook used for mask attachment |
| GoggleHook | Hook used for goggle attachment |
| Bonemap | Mapping from mesh skin data to bone references |
| `appearance.2da` | Table controlling creature/body appearance setup |
| `heads.2da` | Table controlling head definitions |
| LIP | KOTOR lip-sync animation resource |
| MDL/MDX | Native KOTOR model/resource pair |
| TPC/TGA/TXI | Texture formats / texture metadata used in KOTOR workflows |

---

## Appendix C: Design checklist for an AI developer before merging

### Architecture
- [ ] Is there now a single canonical character/scene representation?
- [ ] Are asset references stable and ID-based?
- [ ] Is KOTOR-specific logic centralized rather than duplicated?

### UX
- [ ] Does Character Builder open as a dedicated workspace?
- [ ] Are the five modes clearly separated?
- [ ] Is the viewport the dominant UI element?

### Rendering
- [ ] Is GPU rendering the default path?
- [ ] Are opaque/cutout/transparent passes separated?
- [ ] Are UV and depth debug tools present?

### Rigging
- [ ] Is template transfer the default for KOTOR heads/bodies?
- [ ] Is manual rigging direct-manipulation based?
- [ ] Do symmetry and centerline tools work?

### KOTOR correctness
- [ ] Are hooks validated?
- [ ] Are key facial bones validated?
- [ ] Is supermodel compatibility validated?
- [ ] Are K1/K2 conversion paths explicit?

### Export
- [ ] Are KOTOR, FBX, glTF/GLB exports present?
- [ ] Is OBJ treated only as convenience/static export?
- [ ] Is sidecar JSON emitted with KOTOR metadata?
- [ ] Does export produce a readable validation report?

---

## Final Implementation Position

GhostRigger should stop behaving like a generic, crowded panel and start behaving like a **professional KOTOR-aware character construction and rigging workspace**. The most important strategic shift is:

> **Default to template-guided KOTOR-safe transfer, then layer powerful manual rigging and a truthful GPU viewport on top.**

That combination best addresses the real needs surfaced by the demo analysis, the audited repositories, the engine/rendering references, the animation/retargeting guidance, and the accumulated KOTOR-specific research.