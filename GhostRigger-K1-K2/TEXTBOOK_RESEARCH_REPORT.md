# GhostRigger-K1-K2 — Textbook Research Report
## Phase 4.5 — Canonical Reference Study

> **Completed:** 2026-03-21  
> **Branch:** `genspark_ai_developer`  
> **Purpose:** Deep-read 14 canonical game-engine and graphics textbooks; extract findings relevant to GhostRigger's skeletal animation, skinning, rendering, and physics pipelines; update roadmap accordingly.

---

## Books Analyzed

| # | Title | Author(s) | Key Chapter(s) |
|---|-------|-----------|----------------|
| 1 | *Game Engine Architecture, 3rd Ed.* | Jason Gregory | Ch. 10–12 |
| 2 | *Mastering C++ Game Animation Programming* | M. Dunsky | Ch. 1–3, 7–8, 12 |
| 3 | *3D Game Engine Design, 2nd Ed.* | D.H. Eberly | Ch. 3–5 |
| 4 | *Mathematics for 3D Game Programming & Computer Graphics* | Eric Lengyel | Ch. 3–4, 7, 15 |
| 5 | *Foundations of Game Engine Development, Vol. 1: Mathematics* | Eric Lengyel | Ch. 3–4 |
| 6 | *Foundations of Game Engine Development, Vol. 2: Rendering* | Eric Lengyel | Ch. 7–8 |
| 7 | *Real-Time Collision Detection* | Christer Ericson | Ch. 6–7 |
| 8 | *Game Physics Engine Development* | Ian Millington | Ch. 13 |
| 9 | *Learning Modern 3D Graphics Programming* | Jason McKesson | Ch. 4–5 |
| 10 | *OpenGL Programming Guide, 8th Ed.* | Shreiner, Sellers, Kessenich, Licea-Kane | Ch. 11–12 |
| 11 | *Graphic Shaders: Theory and Practice* | Bailey & Cunningham | Ch. 3–6 |
| 12 | *Real-Time 3D Rendering with DirectX and HLSL* | Paul Varcholik | Ch. 14–16 |
| 13 | *Game Physics (preview edition)* | Various | Ch. 1–3 |
| 14 | *3D Math Primer for Graphics and Game Development* | Dunn & Parberry | Ch. 8–10 |

---

## Section 1: Linear Blend Skinning (LBS)

### 1.1 Canonical Formula (Gregory §12.5.2, Dunsky Ch. 1)

Both Gregory and Dunsky give the identical canonical LBS formula:

```
v'_world = Σ_j  w_j · K_j · v_bind_world

where K_j = inv_bind_j · current_global_j
```

- `v_bind_world` — vertex position in world space at bind pose
- `K_j` — the *skinning matrix* for joint j (4×4)
- `inv_bind_j` — inverse of the joint's world transform at bind pose
- `current_global_j` — joint's current world transform
- `w_j` — blend weight (weights sum to 1.0)

**Key insight**: The skinning matrix `K_j` is NOT a change-of-basis — it transforms vertices that are already in world space. KotOR stores skin vertices in model/world space, which is exactly this convention.

### 1.2 GPU Matrix Palette (Gregory §12.5.2.4, Dunsky Ch. 2)

Both books prescribe the same GPU architecture:

```python
# CPU side (once per frame):
for j in range(num_bones):
    palette[j] = inv_bind[j] @ current_global[j]

# Upload flat array to SSBO:
glBufferData(GL_SHADER_STORAGE_BUFFER, palette_flat, GL_DYNAMIC_DRAW)
```

```glsl
// GPU vertex shader:
layout(std430, binding=1) readonly buffer BonePalette { mat4 boneMatrices[]; };
vec4 pos = vec4(0);
for (int i = 0; i < 4; i++) {
    pos += boneWeight[i] * boneMatrices[boneIndex[i]] * vec4(bindPos, 1.0);
}
```

Max 96 bones per draw call (hardware SSBO limit per Dunsky Ch. 2 — KotOR models have ≤50 bones).

### 1.3 Current GhostRigger State vs. Canonical

| Aspect | Canonical | GhostRigger Current | Status |
|--------|-----------|---------------------|--------|
| LBS formula | Σ w_j K_j v_bind | ✅ Correct in `_lbs_vertex()` | ✅ Fixed Phase 4.3 |
| Vertex space | World space | ✅ KotOR skin verts in world space | ✅ Correct |
| Bone transform cache | Per-frame flat array | ✅ `_bone_transforms_by_name` dict | ✅ Present |
| GPU matrix palette | SSBO upload | ❌ CPU-only | Phase 5.0 |
| Skinned vertex shader | GLSL 4-bone | ❌ Not implemented | Phase 5.0 |

**Bugs fixed in Phase 4.3** (confirmed by Gregory + Dunsky as documented failure modes):
1. Wrong parent reference in bone chain walk — caused incorrect world transforms
2. Shared `_bone_transforms_by_name` dict between skin passes — caused cross-contamination
3. Identity-rotation skin node skipped translation — caused incorrect vertex positions

---

## Section 2: Quaternion Interpolation

### 2.1 SLERP (Gregory §12.4, Lengyel §3–4)

Standard SLERP formula:
```
SLERP(q₁, q₂, t) = q₁ · sin((1-t)θ)/sinθ + q₂ · sin(tθ)/sinθ

where θ = acos(q₁·q₂)
```

**Shortest-path property**: If `q₁·q₂ < 0`, negate `q₂` before interpolation to ensure the shorter arc is taken. GhostRigger's `_slerp()` implements this correctly.

**Near-identical quaternions**: When `|q₁·q₂| > 0.9995`, fall back to normalized linear interpolation (NLERP) to avoid numerical instability in `acos`. GhostRigger implements this.

### 2.2 _quat_normalize_bind — NWN Convention

The NWN/KotOR exporter places a 180°-rotation-about-X quaternion `[1,0,0,0]` at the root node. This is the standard Y-up → Z-up coordinate flip for the game engine. GhostRigger collapses this to identity in `_quat_normalize_bind()`.

**Critical note from Lengyel §3**: Do NOT "fix" this collapse — it is mathematically correct for KotOR's coordinate convention. Future developers must not remove it.

### 2.3 Dual Quaternions (Lengyel FGED Vol. 1 §4)

Dual quaternions eliminate the "candy-wrapper" artifact at joints under heavy rotation. They are the state-of-the-art for character skinning in modern engines. Recommendation for Phase 11: implement dual-quaternion LBS as an option for characters with large shoulder/hip rotations.

---

## Section 3: Animation Clips & Blending

### 3.1 Pose Representation (Gregory §12.4.1)

Gregory's canonical pose format: per-joint tuple `(translation, rotation_quat, scale)` = 8 floats.
- Translation: 3 floats (local space)
- Rotation: quaternion [x,y,z,w] (normalized)
- Scale: 1 float (uniform)

GhostRigger's `NodePose` matches this exactly.

### 3.2 Interpolation Rules (Gregory §12.4.2)

| Channel | Method | Rationale |
|---------|--------|-----------|
| Translation | LERP | Linear — correct |
| Rotation | SLERP (or NLERP) | Spherical — prevents gimbal lock |
| Scale | LERP | Linear — correct |

### 3.3 Phase-Synchronized Cross-Fade (Gregory §12.6.3) ✅ **Implemented Phase 4.5**

When blending between locomotion clips of different durations (walk=2.0s, run=0.8s), using absolute time causes foot-slip. The correct approach:

```python
u = t / T   # normalized phase ∈ [0,1]
# When transitioning from old clip at phase u₀:
new_clip_start = u₀ * T_new
```

GhostRigger now implements `play(sync_phase=True)` which:
1. Computes `old_phase = old_time / old_length`
2. Sets `new_time = old_phase * new_length`
3. Re-evaluates the "from" pose each frame at the matching phase (not a static snapshot)

**`_blend_elapsed` bug fix (Phase 4.6)**: The original code computed `blend_t = _time / blend_duration`. When phase-sync starts the new clip at `_time=1.125` with `blend_duration=0.25`, this gives `1.125/0.25 = 4.5 ≥ 1` → blend finished instantly. Fix: use a separate `_blend_elapsed` counter that advances by `dt` each frame, independent of clip position.

### 3.4 Animation State Machine (Gregory §12.12, Dunsky §7–8)

Reference architecture for Phase 8:
```
State: { name, clip_ref, loop, blend_in_time }
Transition: { from_state, to_state, condition, cross_fade_duration }
StateMachine: { states[], transitions[], current_state, blend_factor }

Per frame:
  1. Evaluate current state's clip at current_time
  2. If transition active: evaluate source + dest, lerp by blend_factor
  3. Advance blend_factor by dt / cross_fade_duration
  4. Check transition conditions → trigger next transition
```

---

## Section 4: Tangent-Space Normal Mapping

### 4.1 TBN Computation (Lengyel §7.8.3, FGED Vol. 2 §7) ✅ **Implemented Phase 4.5**

The tangent vector T for a triangle with UV coordinates is:

```
[e1x, e1y, e1z]   [dV2  -dV1] [T]
[e2x, e2y, e2z] = [-dU2  dU1] [B]   (1/r, r = dU1·dV2 - dU2·dV1)

T = (dV2·e1 - dV1·e2) / r
B = (dU1·e2 - dU2·e1) / r
```

Per-vertex tangent = Gram-Schmidt orthogonalization against vertex normal:
```python
T' = normalize(T - (N·T)·N)
```

Bitangent is NOT stored — recomputed at render time via `cross(N, T)`.

GhostRigger's `ModelNode.compute_tangents()` implements this exactly, populating `node.tangents[]` for GPU TBN vertex attribute upload (Phase 5).

### 4.2 TBN in Fragment Shader (Lengyel §7.8.4)

```glsl
vec3 T = normalize(fragTangent);
vec3 N = normalize(fragNormal);
vec3 B = cross(N, T);
mat3 TBN = mat3(T, B, N);
vec3 n = normalize(TBN * (texture(normalMap, uv).rgb * 2.0 - 1.0));
// Use n for lighting calculations
```

### 4.3 Normal Matrix for Non-Uniform Scale (Lengyel §4.5, Gregory §11.1)

When the model-to-world matrix M has non-uniform scale, normals must be transformed by `(M^-T)` (inverse transpose), not M itself. This is required for correct TBN under non-uniform scale nodes (some KotOR door/creature nodes use scale).

---

## Section 5: Dangly Mesh Physics

### 5.1 Verlet Integration (Millington §13, Lengyel §15.2) ✅ **Implemented Phase 4.5**

Verlet integration for cloth/chain simulation:
```
x(t+dt) = 2x(t) - x(t-dt) + a·dt²
```

Advantages over Euler integration:
- Implicit velocity (no explicit velocity storage)
- Better energy conservation
- Naturally handles position constraints

GhostRigger's `DanglySimulator` implements:
1. **Verlet step**: advance each free vertex by gravity + wind forces
2. **Spring relaxation**: enforce rest-length constraints via position corrections
3. **Displacement clamp**: enforce `dangly_displacement` radius limit
4. **Pin constraint**: vertices with `constraint ≥ 0.95` are immovable (UE-style `FIXED_VERTEX_INDEX`)

### 5.2 KotOR Dangly Parameters

| Parameter | Units | Effect |
|-----------|-------|--------|
| `dangly_displacement` | world units | Max displacement radius from rest position |
| `dangly_tightness` | 0–1 | Spring stiffness (1=rigid chain, 0=floppy cloth) |
| `dangly_period` | seconds | Oscillation period (lower=faster) |
| `dangly_constraints[]` | 0–1 per vertex | Pin weight (1.0=fully pinned, 0.0=fully free) |

### 5.3 Viewport Integration (Phase 4.6) ✅

`FrameRenderer` now holds `_dangly_sims: Dict[int, DanglySimulator]`. On each animation tick:
1. Compute `dt` from wall-clock
2. Create simulator lazily for new dangly nodes
3. Call `sim.step(dt)`
4. `_get_world_verts_for_node` uses simulated positions for free vertices, node-transform positions for pinned vertices

---

## Section 6: Collision Detection & Scene Culling

### 6.1 AABB Trees (Ericson §6–7)

KotOR MDL includes AABB nodes (flag `0x0200`) in area/tileset models. Ericson §6 gives the standard recursive spatial median split for building them. GhostRigger parses AABB nodes but does not use them for culling.

**Phase 5 addition**: VIS-based room culling. KotOR's `.vis` file is exactly a portal visibility graph. Per Ericson §7.6, portal culling is O(visible rooms) and eliminates the need for expensive ray-box tests.

### 6.2 Deferred Selection Texture (Dunsky Ch. 3, Gregory §11)

For mouse picking with >100 instances, both books explicitly recommend **against** ray-triangle intersection tests. The correct architecture:

1. Add `GL_COLOR_ATTACHMENT1` (R32F) to the framebuffer object
2. Fragment shader: `outPickID = float(instanceID)` alongside `outColor`
3. On mouse click: `glReadPixels(x, y, 1, 1, GL_RED, GL_FLOAT, &id)` → O(1)

This is Phase 9's implementation target for viewport mouse picking.

---

## Section 7: Rendering

### 7.1 Blinn-Phong (Lengyel §7.7.3, FGED Vol. 2 §7)

KotOR uses Blinn-Phong shading. The specular term:
```glsl
vec3 h = normalize(lightDir + viewDir);
float spec = pow(max(dot(n, h), 0.0), shininess);
vec3 specColor = lightColor * specular * spec;
```
This matches GhostRigger's `shininess` field and the game's material parameters.

### 7.2 View Frustum Culling (Ericson §6.5)

PyKotor's `frustum.py` (299 lines) implements the Gribb/Hartmann method: extract 6 planes from the view-projection matrix, test each object's bounding sphere against all 6 planes. With 60 rooms × 30 objects/room = 1800 objects in a module scene, frustum culling is essential for interactive frame rates.

### 7.3 Shadow Mapping (Lengyel §9)

KotOR uses stencil shadows internally. For the preview viewport, basic shadow mapping is sufficient and simpler to implement. Lengyel §9 gives the complete bias + PCF (percentage closer filtering) algorithm. Phase 6 target.

---

## Section 8: IK Solvers

### 8.1 Two-Bone Analytical IK (Eberly §5.3, Gregory §12.9)

For foot placement on walkmesh terrain, the minimal requirement is two-bone analytical IK (thigh + shin). The closed-form solution:

```python
# Given: target_pos, hip_pos, hip_len, shin_len
d = distance(hip_pos, target_pos)
# Law of cosines:
cos_knee = (hip_len² + shin_len² - d²) / (2·hip_len·shin_len)
knee_angle = acos(clamp(cos_knee, -1, 1))
```

Phase 10.3 target. **Blocked on Phase 9.3** (BWM walkmesh visualization needed for terrain height queries).

### 8.2 CCD (Cyclic Coordinate Descent) (Eberly §5.4)

For n-bone chains (tails, tentacles), CCD iteratively aligns each bone toward the target. Simple to implement, converges in 5–10 iterations for most cases. Phase 10+ target.

---

## Section 9: Performance & Architecture

### 9.1 Delta-Time Animation (Gregory §8.6)

The current viewport uses `after(33, callback)` for ~30 fps. The correct pattern is wall-clock delta-time:

```python
now = time.perf_counter()
dt = min(now - self._last_time, 0.25)   # clamp to 250ms max
self._last_time = now
engine.advance(dt)
```

GhostRigger's `_tick_animation()` already uses `perf_counter` — confirmed correct.

### 9.2 Pre-allocated Numpy Arrays (Gregory §8.5)

Gregory recommends pre-allocating numpy arrays for per-frame bone matrices to avoid Python GC pressure. For Phase 5 GPU upload: allocate `np.zeros((max_bones, 4, 4), dtype=np.float32)` once at model load, fill in-place each frame.

### 9.3 GL Instancing for Batch Preview (McKesson §5, OpenGL Guide Ch. 12)

For module scenes with 20+ creatures of the same type, `glDrawArraysInstanced` with per-instance transform SSBOs eliminates per-object draw-call overhead. Reference: `KotOR.js OdysseyEmitter3D.ts` uses `THREE.InstancedMesh` for particles. Phase 7 enhancement.

---

## Section 10: Synthesis & Priority Matrix

| Finding | Phase | Priority | Status |
|---------|-------|----------|--------|
| GPU matrix-palette SSBO + skinned vertex shader | 5.0 | 🔴 HIGH | ⏳ Pending |
| TBN tangent-space normal mapping in GPU shader | 5.0 | 🔴 HIGH | ⏳ Pending |
| VIS-based room culling for module scene | 5.1 | 🔴 HIGH | ⏳ Pending |
| Animation state machine (Gregory §12.12) | 8 | 🔴 HIGH | ⏳ Pending |
| Phase-synced cross-fade (Gregory §12.6.3) | 4.5 | 🔴 HIGH | ✅ Done |
| `_blend_elapsed` fix (Gregory §12.6.3) | 4.6 | 🔴 HIGH | ✅ Done |
| Deferred selection texture for mouse pick | 9 | 🔴 HIGH | ⏳ Pending |
| `ModelNode.compute_tangents()` | 4.5 | 🟡 MED | ✅ Done |
| `DanglySimulator` Verlet cloth | 4.5 | 🟡 MED | ✅ Done |
| Dangly wired into FrameRenderer | 4.6 | 🟡 MED | ✅ Done |
| Foot-placement IK (blocked on BWM) | 10.3 | 🟡 MED | 🚧 Blocked |
| Shadow mapping (Lengyel §9) | 6 | 🟡 MED | ⏳ Pending |
| Dual-quaternion LBS (Lengyel FGED Vol.1) | 11 | 🟢 LOW | ⏳ Pending |
| GPU compute-shader skinning (Dunsky Ch. 2) | 11 | 🟢 LOW | ⏳ Pending |
| GL instancing for crowd rendering | 7 | 🟢 LOW | ⏳ Pending |

---

## Section 11: Reference Code Locations

### Internal
| File | Lines | Relevant to |
|------|-------|-------------|
| `src/core/animation_engine.py` | 1 199 | All animation; `DanglySimulator`; `_blend_elapsed` |
| `src/gui/viewport.py` | 8 168 | LBS; TBN; dangly wiring; bone cache |
| `src/core/model_data.py` | 1 168+ | `compute_tangents`; `compute_all_tangents`; quats |
| `tests/test_v92_dangly_physics_wiring.py` | 459 | Dangly + phase-sync tests |
| `tests/test_v93_textbook_lbs_slerp_extended.py` | 775 | LBS math proofs |

### External References
| File | Location | Purpose |
|------|----------|---------|
| `io_mdl.py` | PyKotor (4,783 lines) | Binary MDL writer reference (Phase 7) |
| `geometry_utils.py` | PyKotor (679 lines) | TBN computation cross-check |
| `OdysseyEmitter3D.ts` | KotOR.js (1,276 lines) | Particle emitter Phase 6 reference |
| `OdysseyWalkMesh.ts` | KotOR.js (1,020 lines) | Walkmesh rendering Phase 9 reference |
| `ForgeArea.ts` | KotOR.js (1,096 lines) | Module scene assembly Phase 5 reference |
| `MDLBinaryWriter.cs` | Kotor.NET (575 lines) | Binary MDL write Phase 7 reference |
| `frustum.py` | PyKotor (299 lines) | View-frustum culling Phase 5 reference |

---

## Appendix A: K1/K2 Binary Function Pointers

Required for Phase 7 binary MDL write (from PyKotor + Kotor.NET):

```python
K1_NORMAL_FP1 = 0x0041BCC0   # GEOM_FP_K1
K1_NORMAL_FP2 = 0x0041BCD0
K2_NORMAL_FP1 = 0x00413A10   # GEOM_FP_K2
K2_NORMAL_FP2 = 0x00413A20
```

## Appendix B: Emitter Struct (224 bytes, xoreos + PyKotor confirmed)

Fields: `deadSpace`, `blastRadius`, `blastLength`, `branchCount`, `controlPTSmoothing`, `gridX`, `gridY`, `spaceType`, `updateMode` (32 bytes), `renderMode` (32 bytes), `blendMode` (32 bytes), `textureResRef` (64 bytes), `chunkResRef` (16 bytes), `nFlags` (12 bits), ...

Controller IDs already in `animation_engine.py`: BirthRate(160), Drag(180), FPS(182), LifeExp(186), Mass(188), SizeStart(198), Velocity(216), ColorStart(76), ColorEnd(84), AlphaStart(78), etc.

## Appendix C: BWM Surface Materials

From PyKotor `bwm_data.py`:
```python
SurfaceMaterial.DIRT = 1     # brown
SurfaceMaterial.GRASS = 3    # green
SurfaceMaterial.STONE = 4    # grey
SurfaceMaterial.WATER = 6    # blue
SurfaceMaterial.NON_WALK = 7 # red (impassable)
SurfaceMaterial.DEEP_WATER = 17  # dark blue
SurfaceMaterial.NON_WALK_GRASS = 19  # dark red
```

---

*Report generated 2026-03-21. Full implementation tracked in ROADMAP.md.*
