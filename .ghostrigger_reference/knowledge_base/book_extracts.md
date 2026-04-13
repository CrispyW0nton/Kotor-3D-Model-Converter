# Book Knowledge Extracts for GhostRigger
# =========================================
# Distilled principles and patterns from the three reference books.
# Consult this BEFORE implementing any algorithm or architecture decision.

---

## Book 1: Hayes - Computer Graphics Development with OpenGL (2025)

### Ch 4 - Buffers and Vertex Arrays (VBO/VAO)
**Applies to**: D3 (GPU Renderer), tasks T301-T302

- **VBO (Vertex Buffer Object)**: Stores vertex data (positions, normals, UVs, colors) in GPU memory
- **VAO (Vertex Array Object)**: Records the vertex attribute configuration (which VBOs, strides, offsets)
- **Pattern**: Create VAO first, bind it, then create/bind VBOs and set vertex attribute pointers
- **GLSL Shaders**: Vertex shader processes per-vertex (transform by MVP), fragment shader processes per-pixel (lighting, texturing)
- **Shader compilation**: Create shader -> attach source -> compile -> create program -> attach shaders -> link
- **GhostRigger application**: `gpu_renderer.py` must create VAO per mesh node, with VBOs for position, normal, UV, bone weights/indices

### Ch 7 - Textures and Mapping
**Applies to**: D2 (Texture Wrapping), D3 (GPU Renderer), tasks T201-T204, T305

- **Texture coordinates**: Range [0,1] maps to full texture; values >1 enable tiling via GL_REPEAT
- **Wrap modes**: GL_REPEAT (tile), GL_CLAMP_TO_EDGE (stretch edge pixels), GL_MIRRORED_REPEAT
- **Loading**: Use stb_image pattern: load -> glGenTextures -> glBindTexture -> glTexImage2D -> set parameters
- **Mipmaps**: glGenerateMipmap() for distance-based LOD; use GL_LINEAR_MIPMAP_LINEAR for quality
- **GhostRigger application**: Remove UV sentinel (`_UV_SENTINEL = 100.0`), use `frac()` in shader for GL_REPEAT, honor TXI `clamp` directive with GL_CLAMP_TO_EDGE

### Ch 9 - Real-Time Rendering Techniques
**Applies to**: D3 (GPU Renderer), tasks T303-T306

- **Render loop**: Clear buffers -> update uniforms -> draw calls -> swap buffers
- **Time-based animation**: Pass elapsed time as uniform for animated effects
- **Optimization**: Minimize state changes, batch draw calls, use instancing for repeated geometry
- **GhostRigger application**: GPU renderer render loop must: clear color+depth -> set uniforms (MVP, lights) -> opaque pass -> alpha-test pass -> transparent pass -> skeleton overlay -> swap

### Ch 13 - Framebuffers and Post-Processing
**Applies to**: D3 (GPU Renderer), tasks T306-T307

- **FBO (Framebuffer Object)**: Off-screen render target with attached color and depth textures
- **Depth buffer**: Attach as GL_DEPTH_ATTACHMENT with GL_DEPTH_COMPONENT24 format
- **MSAA**: Create multisampled FBO, blit to regular FBO for resolve
- **GhostRigger application**: GPU renderer needs depth attachment for proper z-testing; MSAA for quality; FBO for potential screenshot/export

---

## Book 2: Mukundan - 3D Mesh Processing and Character Animation (2022)

### Ch 2 - Mesh Representation and File Formats
**Applies to**: D1 (FBX Export), tasks T101-T107

- **Vertex list + polygon list**: Fundamental mesh representation; vertices indexed by faces
- **OBJ format**: `v` (vertex), `vt` (texture coord), `vn` (normal), `f` (face with v/vt/vn indices)
- **Normal computation**: Face normal = cross product of two edge vectors; vertex normal = average of adjacent face normals
- **Anticlockwise winding**: Standard convention for front-facing polygons (CCW when viewed from outside)
- **GhostRigger application**: FBX exporter must output correct vertex/normal/UV data with proper winding order; ensure normals are normalized

### Ch 7 - Character Animation: Skeleton, Bones, Skinning
**Applies to**: D1 (FBX Export), D4 (Character Builder), tasks T101-T107, T501-T507

#### 7.3 Skeleton Hierarchy
- **Node hierarchy**: Joint positions specified relative to parent; maps directly to scene graph
- **Base pose / zero pose**: Initial skeleton configuration with all joint angles = 0
- **BVH format**: Hierarchy section (joints + offsets) + Motion section (keyframes with Euler angles)
- **Euler angle sequences**: Z,Y,X (3DS Max) or Z,X,Y (DAZ/MotionBuilder); GhostRigger must handle KOTOR's convention

#### 7.4 Skeleton Animation
- **Node matrix update**: For each keyframe, compute translation * rotation matrix from position/rotation keys, replace node's transform
- **Quaternion interpolation**: Use SLERP between rotation keys for smooth animation
- **Recursive traversal**: Push/pop matrix stack while traversing hierarchy; each child inherits parent's cumulative transform

#### 7.5 Bones and Offset Matrix (CRITICAL for FBX export)
- **Bone structure**: index, name (matches joint name), vertex set (indices), offset matrix
- **Offset matrix (F)**: Transforms vertices from mesh space to joint space (joint at origin)
  - Simple case: `F = Translation(-Jx, -Jy, -Jz)` where J is joint position in mesh space
  - General case: May include rotation to align with joint's local axes
- **Bind pose matrix**: The inverse of the offset matrix; transforms from joint space to mesh space
- **FBX bind-pose formula**: `Jk = Lk * Fk` where Lk = local transform, Fk = offset matrix
  - The global bind-pose for bone k: product of all local transforms from root to k
  - Each bone's `TransformLink` in FBX = inverse of offset matrix = global bind pose
- **GhostRigger application**: `mesh_converter.py` FBX exporter MUST:
  1. Write full skeleton hierarchy (all bones, not just weighted ones)
  2. Compute correct offset matrices from KOTOR MDL node hierarchy
  3. Write FBX `Deformer` nodes with proper `TransformLink` (global bind pose)
  4. Include synthetic stubs for bones without geometry

#### 7.6 Vertex Blending (Skinning)
- **Weight normalization**: Sum of weights per vertex MUST equal 1.0
- **Blended transform**: `v' = (w1*J1 + w2*J2 + ...)*v` where Ji = bone's combined transform
- **Normal blending**: Normal matrix = inverse-transpose of the blended matrix (NOT just the blended matrix directly)
- **Max influences**: Typically 4 bones per vertex for GPU skinning; normalize after clamping
- **GhostRigger application**: FBX exporter must normalize weights per vertex; GPU renderer skinning shader needs max 4 bone influences per vertex

#### 7.7 Animation Retargeting
- **Joint name mapping**: One-to-one correspondence between source and target skeletons
- **Euler angle mapping**: Rotation axes may differ between source/target; requires careful per-joint mapping
- **GhostRigger application**: Character Builder rig transfer must map KOTOR skeleton joints to user's target skeleton

---

## Book 3: Gregory - Game Engine Architecture, 4th Edition (2024)

### Ch 5 - 3D Math for Games
**Applies to**: D1 (FBX Export), D3 (GPU Renderer), all matrix operations

#### 5.3 Matrices
- **Affine matrix (4x4)**: Preserves parallelism; combines rotation + translation + scale
- **Matrix multiplication**: `P = A * B` applies B first, then A (right-to-left order)
- **Column-major vs row-major**: OpenGL uses column-major; DirectX/FBX uses row-major. MUST transpose when converting between conventions
- **Inverse**: For orthonormal rotation matrix, inverse = transpose. For general affine, compute full inverse
- **GhostRigger application**: KOTOR MDL stores transforms as position + orientation quaternion; must compose into 4x4 matrices for FBX export. Watch column/row major convention!

#### 5.4 Quaternions
- **Unit quaternion**: `q = [a*sin(theta/2), cos(theta/2)]` where a = rotation axis, theta = angle
- **Quaternion to matrix**: Standard conversion formula (avoid gimbal lock of Euler angles)
- **SLERP**: Spherical linear interpolation for smooth rotation blending
- **GhostRigger application**: KOTOR MDL uses quaternions for joint orientations; FBX ASCII uses Euler angles; must convert correctly

### Ch 7 - Resources and the File System
**Applies to**: D5 (Performance), D6 (Module/Scene), tasks T601-T604

#### 7.2 The Resource Manager
- **Two components**: Offline tool chain (asset pipeline) + runtime manager (load/unload)
- **Lifetime management**: Load resources in advance of need; unload when no longer referenced
- **Reference counting**: Track how many systems reference a resource; unload at refcount = 0
- **Streaming**: Load resources asynchronously to avoid frame hitches
- **Memory budgets**: Set per-resource-type memory limits; evict LRU when budget exceeded
- **GhostRigger application**: `resource_manager.py` must implement:
  1. Lazy loading (don't pre-load all textures)
  2. Reference counting for texture/model caches
  3. LRU eviction when GPU texture cache exceeds budget
  4. Separate cache tiers: disk -> CPU memory -> GPU memory

### Ch 8 - The Game Loop and Real-Time Simulation
**Applies to**: D3 (GPU Renderer), tasks T301-T307

#### 8.1-8.3 Rendering Loop and Game Loop
- **Render loop pattern**: `while(!quit) { updateCamera(); updateScene(); renderScene(); swapBuffers(); }`
- **Windows message pump**: Service OS messages first, then run game loop iteration
- **Callback-driven**: Framework calls `frameStarted()` -> render -> `frameEnded()`
- **Event-based**: Post events into future; process them in priority order each frame
- **GhostRigger application**: Tkinter is callback-driven; GPU renderer must integrate with tkinter's `after()` for animation loop. Pattern: tkinter event -> update camera/scene -> GPU render -> swap buffers -> schedule next frame

#### 8.4-8.5 Time Management
- **Frame delta time**: Measure elapsed time between frames; multiply by speed for frame-rate-independent animation
- **Fixed timestep**: Decouple physics/simulation from rendering frame rate
- **GhostRigger application**: Animation playback must use delta-time, not frame count, for consistent speed regardless of GPU performance

---

## Quick Reference: Book Section -> GhostRigger Task Mapping

| Task | Book Section | Key Principle |
|------|-------------|---------------|
| T101 (Bone hierarchy) | Mukundan 7.3-7.5 | Node hierarchy = joint hierarchy; offset matrix formula |
| T102 (Skin deformer) | Mukundan 7.5-7.6 | Bone struct: name, vertex set, weights, offset matrix |
| T103 (Bind-pose) | Mukundan 7.5.1, Gregory 5.3 | Jk = Lk * Fk; column vs row major |
| T104 (Weight normalization) | Mukundan 7.6 | Sum of weights = 1.0; max 4 influences |
| T201 (UV sentinel removal) | Hayes Ch 7 | GL_REPEAT via frac(); no sentinel needed |
| T202 (TXI clamp support) | Hayes Ch 7 | GL_CLAMP_TO_EDGE for non-tiling textures |
| T301 (ModernGL context) | Hayes Ch 4, Gregory 8.1 | VAO/VBO setup; render loop integration |
| T302 (VBO/VAO pipeline) | Hayes Ch 4 | Per-mesh VAO with position/normal/UV/weight VBOs |
| T303 (Shaders) | Hayes Ch 4, Ch 7 | Vertex: MVP transform + skinning; Fragment: texture + lighting |
| T304 (Depth testing) | Hayes Ch 13 | glEnable(GL_DEPTH_TEST); depth attachment on FBO |
| T601 (Texture caching) | Gregory 7.2 | LRU eviction, memory budgets, lazy loading |
| T801 (Golden file tests) | All books | Validate against known-good outputs |
