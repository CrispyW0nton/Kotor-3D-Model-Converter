# GhostRigger-K1-K2 — Context Snapshot
> **Generated:** 2026-03-21  
> **Purpose:** Compressed knowledge document preserving all critical facts from the Phase 4.5/4.6 research & implementation session.  
> Designed to survive sandbox resets. Read this first at the start of any new session.

---

## 1. Repository Coordinates

| Item | Value |
|------|-------|
| Remote URL | `https://github.com/CrispyW0nton/Kotor-3D-Model-Converter` |
| Active branch | `genspark_ai_developer` |
| Local path | `/home/user/webapp/GhostRigger-K1-K2/` |
| PR target | `main` |

### Commit history (most-recent first)
```
6ccf3ea  feat(animation): Phase 4.6 — blend_elapsed fix, dangly wiring tests, ROADMAP update
494470f  feat(animation): Phase 4.5 — textbook research pass + TBN tangents + Verlet dangly + phase-sync crossfade
f5cf683  feat(ghostrigger): v6.3 — skin vertex pipeline fix + test suite green
4c5391b  feat: GhostRigger v2.7 — KotOR Odyssey Engine pipeline (public release)
```
> **Note:** After a sandbox reset the working tree reverts to commit `0c5d8bd` / `4c5391b`.  
> All work from `f5cf683` onward must be re-applied from this document and the implementation sections below.

---

## 2. Source-File Map & Line Counts (Phase 4.6 state)

| File | Lines | Role |
|------|-------|------|
| `src/core/animation_engine.py` | 1 199 | AnimationEngine, AnimPose, DanglySimulator |
| `src/gui/viewport.py` | 8 168 | FrameRenderer, LBS pipeline, dangly wiring |
| `src/core/mdl_parser.py` | 2 665 | Binary + ASCII MDL reader; parent-link wiring |
| `src/core/model_data.py` | 1 168 | ModelNode, KotorModel, quaternion helpers, TBN |
| `src/core/mdl_porter.py` | 1 308 | ASCII MDL writer |
| `src/core/diagnostics.py` | 746 | Per-model audit panel |
| `src/core/game_library_ext.py` | 459 | 2DA/game-library helpers |
| `src/core/twoda.py` | 469 | 2DA table access |
| `src/core/module_format.py` | 812 | LYT/VIS/ARE/GIT parsers |
| `src/core/creature_appearance.py` | 954 | Appearance 2DA lookup |
| `tests/test_v92_dangly_physics_wiring.py` | 459 | 25 tests — dangly wiring |
| `tests/test_v93_textbook_lbs_slerp_extended.py` | 775 | 44 tests — LBS/SLERP math proofs |
| `tests/test_v92_textbook_improvements.py` | ~350 | 33 tests — Phase 4.5 improvements |
| `ROADMAP.md` | ~650 | Full phased roadmap (Phases 1–11) |
| `TEXTBOOK_RESEARCH_REPORT.md` | ~7 000 words | Full 14-book analysis |

---

## 3. Key Data Structures (model_data.py)

### 3.1 Enums & Constants
```python
class NodeFlags(IntFlag):
    HEADER=1, LIGHT=2, EMITTER=4, CAMERA=8, REFERENCE=16, MESH=32,
    SKIN=64, ANIM=128, DANGLY=256, AABB=512, SABER=1024

class GameVersion(IntEnum):  K1=1, K2=2

class ModelClassification(IntEnum):
    EFFECT=0, EFFECTS=1, TILE=2, CHARACTER=4, DOOR=8,
    LIGHTSABER=16, PLACEABLE=32, FLYER=64

GEOM_FP_K1 = 0x0041BCC0   # K1 geometry function pointer (also K1_NORMAL_FP1)
GEOM_FP_K2 = 0x00413A10   # K2 geometry function pointer (also K2_NORMAL_FP1)
K1_NORMAL_FP2 = 0x0041BCD0
K2_NORMAL_FP2 = 0x00413A20

KOTOR_BASE_SKELETONS: frozenset  # all standalone base skeleton names
# e.g. 'S_FEMALE02', 'C_BANTHA', 'WARDROID', etc.
```

### 3.2 ModelNode fields added in Phase 4.5
```python
# Phase 4.5 additions to ModelNode:
tangents: List[Tuple[float,float,float]]  = field(default_factory=list)
dangly_constraints: List[float]           = field(default_factory=list)
dangly_displacement: float                = 0.5
dangly_tightness:    float                = 0.5
dangly_period:       float                = 1.0
```

### 3.3 ModelNode.compute_tangents() — Phase 4.5 ✅
```python
def compute_tangents(self) -> None:
    """
    Per-vertex TBN tangent vectors via Lengyel Gram-Schmidt (2001).
    Ref: Lengyel §7.8.3; FGED Vol.2 §7.
    Populates self.tangents[].  Bitangents NOT stored — recompute via cross(n, t).
    """
    # Algorithm: per-triangle edge-based tangents accumulated, then
    # Gram-Schmidt orthogonalized against vertex normals.
    # Handles face_uvs ASCII MDL indexing.  Degenerate UVs → default (1,0,0).
```

### 3.4 KotorModel.compute_all_tangents() — Phase 4.5 ✅
```python
def compute_all_tangents(self) -> None:
    """Batch compute_tangents() over all mesh nodes. Skips non-mesh/header nodes."""
```

### 3.5 Quaternion helpers
```python
_quat_mul(a, b)              # Hamilton product
_quat_conjugate(q)           # conjugate
_quat_rotate(q, v)           # rotate vector v by quaternion q
_quat_normalize(q)           # unit quaternion
_quat_normalize_bind(q)      # NWN/KotOR coordinate-flip convention:
                              # 180°-about-X collapses to identity (do NOT remove!)
```

### 3.6 ModelNode.world_position / world_transform
```python
def world_position(self) -> Tuple[float,float,float]:
    """Walk parent chain; _quat_normalize_bind on non-leaf nodes; cycle guard 512."""

def world_transform(self) -> Tuple[pos3, quat4]:
    """Returns (world_pos, world_quat). Leaf node keeps raw rotation."""

def bone_world_position(self) -> Tuple[float,float,float]:
    """Collapses 180° on ALL nodes including leaf — for bone gizmo pivot."""
```

---

## 4. Animation Engine (animation_engine.py)

### 4.1 Controller type IDs
```python
CTRL_POSITION   = 8
CTRL_ORIENTATION= 20
CTRL_SCALE      = 36
CTRL_SELFILLUM  = 100
CTRL_ALPHA_X    = 128
CTRL_ALPHA      = 132
```

### 4.2 AnimationEngine.__init__ blend state (Phase 4.6 — with fix)
```python
self._blend_from_pose:  Optional[AnimPose] = None
self._blend_t:          float = 0.0    # blend fraction [0→1]
self._blend_elapsed:    float = 0.0    # ← NEW Phase 4.6: wall-clock elapsed since blend start
self._blend_duration:   float = 0.0    # total blend duration (s)
self._blend_sync_phase: bool  = False
self._blend_from_anim:  Optional[Animation] = None
self._blend_from_time:  float = 0.0
```

### 4.3 play() phase-sync logic (Phase 4.5)
```python
def play(self, anim_name, loop=True, blend=True, sync_phase=False) -> bool:
    ...
    if sync_phase and self._blend_from_anim is not None:
        old_phase = self._blend_from_time / max(0.001, old_anim.length)
        self._time = old_phase * max(0.001, new_anim.length)
    else:
        self._time = 0.0
```

### 4.4 advance() blend update — THE BUG THAT WAS FIXED (Phase 4.6)
```python
# WRONG (original — breaks when phase-sync starts clip at e.g. t=1.125):
self._blend_t = min(1.0, self._time / self._blend_duration)

# CORRECT (Phase 4.6 fix):
self._blend_elapsed += dt
self._blend_t = min(1.0, self._blend_elapsed / self._blend_duration)
if self._blend_t >= 1.0:
    self._blend_from_pose = None
    self._blend_t = self._blend_elapsed = self._blend_duration = 0.0
```
**Root cause:** When phase-sync starts the new clip at `_time=1.125` and `_blend_duration=0.25`,
the old formula gives `1.125/0.25 = 4.5 ≥ 1.0` → blend finishes instantly on first advance().
The fix uses a *separate* elapsed counter independent of clip position.

### 4.5 _eval_node() semantics
- **Position controllers (type 8):** values are *delta offsets* added to bind-pose position.  Zero delta = bind pose.
- **Orientation controllers (type 20):** values are *absolute* quaternions replacing bind rotation.
- **Scale / alpha / self-illumination:** also absolute.
- Rotations are normalized but NOT forced to positive-w until after all controllers (preserves shortest-path SLERP).

### 4.6 evaluate() cross-fade blend
```python
pose = lerp(from_pose, current_pose, blend_t)   # position: linear
pose = slerp(from_quat, current_quat, blend_t)  # rotation: spherical
pose = lerp(from_scale, current_scale, blend_t) # scale: linear
```
When `sync_phase=True`: "from" pose is re-evaluated *each frame* at `old_t = u_new * old_length`
(not a static snapshot), giving smooth phase-aligned blend throughout transition.

### 4.7 DanglySimulator — Phase 4.5 ✅
```python
class DanglySimulator:
    """
    Verlet cloth sim for KotOR dangly nodes.
    Ref: Millington §13; Lengyel §15.2; Gregory §12.7.
    """
    PIN_THRESHOLD: float = 0.95   # constraint >= this → vertex pinned (FIXED_VERTEX_INDEX)

    def __init__(self, node: ModelNode):
        # Initializes _pos, _prev_pos from node.vertices
        # Builds spring edges from face topology
        # Clamps params: displacement=max(0.001,node.dangly_displacement),
        #                tightness=clamp(0,1), period=max(0.01)

    def reset(self) -> None:
        """Reset to bind pose positions."""

    def step(self, dt, wind_dir=(0,0,0), gravity_scale=1.0) -> List[Tuple3]:
        """
        One Verlet integration step.
        Returns world-space vertex positions.
        Pinned verts (constraint >= PIN_THRESHOLD) are immovable.
        Post-step: clamp displacement to dangly_displacement radius.
        """
```

---

## 5. Viewport LBS Pipeline (viewport.py)

### 5.1 LBS formula (canonical)
```
v_world_anim = Σ w_i * (R_anim_i * R_bind_i⁻¹ * (v_bind_world − T_bind_i) + T_anim_i)
```
KotOR skin vertices are stored in **model/world space** (not local node space).
Non-skin trimesh vertices are stored in **node-local space** and need full hierarchy transform.

### 5.2 Bone transform cache (_bone_transforms_by_name)
```python
# Keyed by bone name (lower-cased)
# Value: (bind_world_pos, bind_world_quat, anim_world_pos, anim_world_quat)
# Rebuilt once per animation frame (pose ID changes each tick)
# Thread-safe: cache isolated during bind pass
# Bone name collisions: prefer non-skin (joint) nodes over skin mesh nodes
```

### 5.3 FIX-SKIN-NODEROT
Some KotOR exporters store skin vertices pre-rotated by the skin node's local rotation.
Fix: detect non-identity skin node rotation and apply it to skin vertices before LBS.

### 5.4 _node_world_transform (line 3825 in Phase 4.6 viewport.py)
```python
# Per-frame cache: full ancestor chain walk when animation pose is active
# Substitutes animated transforms for bind-pose transforms
# NaN guards + quaternion normalization
# Special: 180°-X-flip in NWN export → _quat_normalize_bind
# Returns (world_pos, world_quat)
```

### 5.5 Dangly wiring — Phase 4.6 ✅
```python
# In FrameRenderer.__init__:
self._dangly_sims: Dict[int, 'DanglySimulator'] = {}
self._dangly_last_time: float = 0.0

# In set_animation_pose(pose, ...):
#   1. If _dangly_last_time == 0.0: set to perf_counter() NOW (avoids giant first dt)
#   2. dt = now - _dangly_last_time
#   3. For each dangly node in model:
#        if id(node) not in _dangly_sims: create DanglySimulator(node)
#        _dangly_sims[id(node)].step(dt)
#   4. _dangly_last_time = now

# In _get_world_verts_for_node(node, ...):
#   If node.is_dangly() and _anim_pose is not None:
#       sim = _dangly_sims.get(id(node))
#       if sim:
#           for each vertex:
#               if constraint >= PIN_THRESHOLD: use node world transform (pinned)
#               else: use sim's simulated position
```

### 5.6 Skin proxy detection heuristics
```python
# Non-skin node is a proxy if:
#   - Its texture is used by exactly one skin mesh
#   - That skin mesh has more vertices than the non-skin piece
#   - Non-skin pieces ≤50 verts AND skin nodes >5× that count → body proxies
# Outlier skin nodes: centroid >1.5 units from Z-centroid of non-skin visible nodes
```

---

## 6. Phase 4.5 Textbook Findings → Roadmap Changes

### Books analyzed (14 total)
| Book | Author | Key Finding |
|------|--------|-------------|
| *Game Engine Architecture 3rd Ed.* | Gregory | LBS §12.5.2; anim blending §12.4; state machine §12.12; phase-sync §12.6.3 |
| *Mastering C++ Game Animation Programming* | Dunsky | GPU compute skinning Ch.2; SSBO palette; IK Ch.12; deferred selection Ch.3 |
| *3D Game Engine Design 2nd Ed.* | Eberly | Scene graph; IK solvers §5.3; hierarchical culling |
| *Mathematics for 3D Game Programming* | Lengyel | Quaternion SLERP §3-4; TBN §7.8.3; Cook-Torrance BRDF; shadow math |
| *FGED Vol.1: Math* | Lengyel | Transforms; dual quaternions |
| *FGED Vol.2: Rendering* | Lengyel | PBR; TBN §7; fog; decals |
| *Real-Time Collision Detection* | Ericson | BVH; AABB trees; portal culling §7.6 |
| *Game Physics Engine Development* | Millington | Spring-mass dangly §13; Verlet integration |
| *Learning Modern 3D Graphics Programming* | McKesson | OpenGL pipeline; vertex attributes §4 |
| *OpenGL Programming Guide 8th Ed.* | Shreiner et al. | Compute shaders; SSBOs; instancing |
| *Graphic Shaders* | Bailey & Cunningham | GLSL stages; geometry shaders |
| *Real-Time 3D Rendering with DirectX/HLSL* | Varcholik | HLSL reference |
| *Game Physics (preview)* | Various | Rigid body; forces |

### Roadmap changes triggered
1. **Phase 5.0** (NEW): Matrix-palette SSBO upload + TBN normal-map shader — `Kj = inv_bind[j] * current_global[j]`
2. **Phase 5.1**: VIS-based room culling added as *required* milestone (not optional)
3. **Phase 8.2**: Cross-fade must use normalized-time sync, not absolute time
4. **Phase 8**: Animation state-machine architecture defined (Gregory §12.12 + Dunsky §7-8):
   - States: `{name, clip_ref, loop, blend_in_time}`
   - Transitions: `{from_state, to_state, condition, cross_fade_duration}`
5. **Phase 9**: Deferred selection texture for mouse picking (GL_COLOR_ATTACHMENT1 → fragment outputs instanceID)
6. **Phase 10.3**: Foot IK blocked on Phase 9.3 (BWM visualization) — no terrain height = no IK
7. **Phase 10**: Dangly Verlet sub-task (now implemented)
8. **Phase 11**: GPU compute-shader skinning — Dunsky Ch.2 primary reference

### GPU skinned vertex shader (canonical, Gregory §12.5.2.4)
```glsl
layout(location=0) in vec3 position;  layout(location=1) in vec3 normal;
layout(location=2) in vec2 texcoord;  layout(location=3) in ivec4 boneIdx;
layout(location=4) in vec4 boneWgt;   layout(location=5) in vec4 tangent;
layout(std430, binding=1) readonly buffer BonePalette { mat4 boneMatrices[]; };
uniform mat4 MVP;  uniform mat3 normalMatrix;

void main() {
    vec4 pos = vec4(0); vec3 nrm = vec3(0); vec3 tan = vec3(0);
    for (int i = 0; i < 4; i++) {
        mat4 bm = boneMatrices[boneIdx[i]];
        pos += boneWgt[i] * bm * vec4(position, 1.0);
        nrm += boneWgt[i] * mat3(bm) * normal;
        tan += boneWgt[i] * mat3(bm) * tangent.xyz;
    }
    gl_Position = MVP * pos;
    fragNormal    = normalize(normalMatrix * nrm);
    fragTangent   = normalize(mat3(MVP) * tan);
    fragBitangent = cross(fragNormal, fragTangent) * tangent.w;
    fragTexcoord  = texcoord;
}
```

---

## 7. Reference Repository Map

| Repo | Language | Key File / Finding |
|------|----------|--------------------|
| xoreos | C++ | `model_kotor.cpp` — saber 8-vert layout; emitter 224-byte struct; AABB flag 0x0200 |
| KotOR.js | TypeScript | `OdysseyEmitter3D.ts` (1 276 lines); `OdysseyWalkMesh.ts` (1 020 lines); `ForgeArea.ts` (1 096 lines) |
| PyKotor | Python | `io_mdl.py` (4 783 lines) **primary ref for Phase 7 binary write**; `geometry_utils.py` TBN; `io_bwm.py` walkmesh R/W |
| Kotor.NET | C# | `MDLBinaryWriter.cs` (575 lines); `BWM.CalculateAABBs()` |
| kotorblender | Python/Blender | ASCII MDL round-trip + WOK co-import |
| PyKotor/KotorMCP | Python | `detectInstallations`, `listResources`, `describeResource`, `journalOverview` |

### K1/K2 binary function pointers (needed for Phase 7 write)
```
K1_NORMAL_FP1 = 0x0041BCC0   K1_NORMAL_FP2 = 0x0041BCD0
K2_NORMAL_FP1 = 0x00413A10   K2_NORMAL_FP2 = 0x00413A20
```

---

## 8. Test Suite State

| Test file | Tests | Status |
|-----------|-------|--------|
| `test_v92_dangly_physics_wiring.py` | 25 | ✅ all pass |
| `test_v93_textbook_lbs_slerp_extended.py` | 44 | ✅ all pass |
| `test_v92_textbook_improvements.py` | 33 | ✅ all pass |
| Earlier suites (v37–v90) | ~2 800 | ✅ all pass (6 skipped) |
| **Total (Phase 4.6)** | **~2 902** | ✅ green |

### What test_v93 covers
- **LBS skinning matrix** `Kj = inv_bind[j] * current_global[j]` — bind/rotate/translate/multi-joint
- **SLERP shortest-path**: dot<0 → negate q2; midpoint unit-length; 90° midpoint correct
- **`_interp_channel`** boundary: empty→None, before-first, after-last, exact, midpoint, large-N binary search
- **`_quat_normalize_bind`**: 180°-about-X → identity (NWN); 180° about Y/Z → preserved
- **Animation position delta semantics**: zero delta→bind pos; nonzero→bind+delta; orientation absolute
- **LERP linearity**: endpoints, midpoint, `_lerp3`
- **Dangly spring topology**: N-1 edges for chain-N; valid indices; positive rest lengths
- **`world_position` cycle guard**: depth-512 linear chain + circular cycle both complete without hang
- **Animation looping**: wrap at clip length, no-wrap before end, zero-advance no-op
- **`compute_all_tangents` edge cases**: empty model, header-only root, non-mesh nodes

### What test_v92_dangly covers
- DanglySimulator init from node
- Pinned vertices do not move
- Free vertices move under gravity
- spring topology built correctly
- displacement clamp enforced
- reset() restores bind pose
- step() returns correct vertex count
- PIN_THRESHOLD = 0.95
- viewport _dangly_sims dict created lazily
- _dangly_last_time initialized on set_model
- FrameRenderer.set_animation_pose advances sims
- world verts for dangly node during animation use sim positions

---

## 9. Known Gaps Remaining After Phase 4.6

| Gap | Phase | Priority |
|-----|-------|----------|
| No binary MDL **write** | 7 | HIGH — PyKotor `io_mdl.py` (4 783 lines) is primary ref |
| GPU matrix-palette SSBO + skinned vertex shader | 5.0 | HIGH |
| TBN in GPU fragment shader | 5.0 | HIGH |
| Module scene assembly (LYT rooms + GIT objects) | 5.1-5.2 | HIGH |
| VIS-based room culling | 5.1 | HIGH |
| Particle/emitter preview | 6 | MEDIUM |
| Walkmesh (BWM/PWK/DWK) visualization | 9 | MEDIUM |
| Animation state machine + blend tree | 8 | HIGH |
| Deferred selection texture for mouse pick | 9 | HIGH |
| Dangly physics in GPU renderer | 10 | MEDIUM |
| Foot-placement IK (blocked on Phase 9.3) | 10 | MEDIUM |
| GPU compute-shader skinning (crowd) | 11 | LOW |
| Override folder priority in resource loader | 12 | MEDIUM |
| NWScript compile/decompile button | 12 | MEDIUM |

---

## 10. Untracked Files (do not commit unless intentional)

```
GhostRigger-K1-K2/capture_demo_video.py
GhostRigger-K1-K2/ghostrigger_demo_v62.mp4
GhostRigger-K1-K2/proof_renders/         (directory)
GhostRigger-K1-K2/research_sources/kotorblender/
GhostRigger-K1-K2/research_sources/mdledit/
GhostRigger-K1-K2/tools/proof_render.py
../render_check/                          (sibling directory)
```

---

## 11. Resumption Checklist (after any sandbox reset)

1. `git log --oneline` — confirm which commits exist
2. If `6ccf3ea` is missing → re-apply Phases 4.5+4.6 from this document
3. Key files to re-create: `animation_engine.py` (+314 lines), `viewport.py` (dangly wiring ~80 lines), `model_data.py` (+139 lines), `tests/test_v92_dangly_physics_wiring.py` (459 lines), `tests/test_v93_textbook_lbs_slerp_extended.py` (775 lines), `ROADMAP.md` (Phase 4.5+4.6 sections), `TEXTBOOK_RESEARCH_REPORT.md`
4. Run `python -m pytest tests/test_v92_dangly_physics_wiring.py tests/test_v93_textbook_lbs_slerp_extended.py -q` — must be 69 passed
5. Commit → push → open/update PR to `main`
