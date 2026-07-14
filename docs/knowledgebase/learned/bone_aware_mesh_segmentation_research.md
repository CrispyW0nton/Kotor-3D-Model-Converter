# Bone-Influence-Aware Mesh Segmentation: Literature Review & Algorithm Recommendations

**Purpose:** Foundational research for the GhostRigger anatomically-aware mesh splitter.
The KOTOR engine limits each mesh node to ≤16 bones in its `bone_map` palette and
≤4 bone influences per vertex. Characters with >16 influencing bones must be split
into multiple mesh nodes, and those splits must align with skeletal joints to prevent
cross-joint tearing artifacts during animation.

**Date:** 2026-06-30
**Status:** Research complete; implementation design ready.

---

## A. THE PROBLEM FORMALIZED

### Input

| Symbol | Description | GhostRigger Source |
|--------|-------------|-------------------|
| **M** | Mesh: vertices V (N×3), faces F (list of vertex-index triples) | `ModelNode.vertices`, `ModelNode.faces` |
| **W** | Per-vertex skin weight matrix: for each vertex v_i, a set of (bone_index, weight) pairs, max 4 | `ModelNode.skin_data[i].influences[j]` → `BoneWeight(bone_index, weight)` |
| **B** | Bone palette: list of bone names indexed by `bone_index` | `ModelNode.bone_map: List[str]` |
| **S** | Skeleton: bone hierarchy with joint pivot positions | Donor template (`reference_model`), accessible via `_skin_weighted_bone_map_fit_positions()` (L1629) |
| **K** | Max bones per sub-mesh palette | K = 16 (KOTOR engine limit) |
| **J** | Max influences per vertex | J = 4 (KOTOR engine limit) |

### Constraints on the Partition

Given mesh M and weights W, partition faces F into groups G₁ ... Gₖ such that:

1. **Bone budget:** Each Gᵢ's **union of influencing bones** (across all its vertices) has ≤ K=16 distinct bone indices. Formally: |∪_{v ∈ vertices(Gᵢ)} bones(v)| ≤ 16.
2. **Topological connectivity:** Each Gᵢ is connected in the face-adjacency graph (or nearly so — see Edge Cases).
3. **Joint alignment:** Boundaries between Gᵢ and Gⱼ pass through regions that are skeletal joint transition zones — i.e., areas where no single bone has dominant (>50%) influence, or where the dominant bone changes. This prevents a face that straddles a high-mobility joint from being in the same node as a face anchored to the parent bone.
4. **Balance:** The partition should avoid degenerate splits (e.g., one node with 15 bones and 95% of faces, another with 1 bone and 5%). When multiple valid K-bone partitions exist, prefer the one with fewer total nodes and more balanced face counts.
5. **Skinning preservation:** No vertex's bone influences are lost. Every (bone_index, weight) pair in the original `skin_data` must be present in the split node's remapped `skin_data` + `bone_map`.

### Why This Is Hard

This is a **constrained graph partitioning** problem. The bone-budget constraint (1) couples non-local faces: two faces at opposite ends of the mesh that share even one bone index are linked. Finding the minimum-cardinality partition satisfying all constraints is **NP-complete** (reduces to graph coloring / set cover). However, good heuristic solutions are achievable (see Section B).

### Current Splitter's Gap

The current `split_imported_mesh_nodes()` (L5755) and `_split_mesh_node_by_components()` (L5654) have a critical guard at lines 5661 and 5777:

```python
if getattr(node, "skin_data", None) or getattr(node, "bone_map", None):
    return []  # SKIPS ALL SKINNED NODES
```

**The current splitter never touches skinned meshes.** It only splits unskinned geometry via `_connected_face_components()` (L5603), which is purely topological (welded-vertex-position flood fill, no bone awareness). There is no code path that:
- Reads `skin_data` to determine per-face bone influence sets
- Checks whether a face group exceeds the 16-bone palette limit
- Aligns cut boundaries to skeletal joints

The existing `segment_mesh_by_bones()` in `heat_diffusion_skinning.py` (L313) assigns each vertex to its **nearest bone by Euclidean distance** — it does NOT consider actual skin weight sets and is not designed for K-bone partitioning.

---

## B. ALGORITHM SURVEY

### B1. Skin Partitioning via Greedy Bone-Palette Insertion (Paanakker 2007)

**Source:** Ferns Paanakker, "Skinned Mesh Export: Optimization," Game Developer Magazine, 2007.
**Relevance:** ⭐⭐⭐⭐⭐ — This is the industry-standard approach for the exact problem.

**How it works:**

1. **Build face-level bone sets:** For each triangle, collect the union of bone indices from its 3 vertices. A single triangle can reference up to 3×4=12 distinct bones in the worst case (4 per vertex, no overlap).
2. **Group triangles into "partitions":** Triangles are sorted by their bone-set signature and greedily grouped. Two triangles can be in the same partition only if their combined bone union stays within K.
3. **Optimize partition ordering** using one of two strategies:
   - **Simple Algorithm (fast):** Sort partitions by bone-set (e.g., ascending), append to the current chunk until full, then start a new chunk. O(n log n).
   - **Cheapest Insertion (higher quality):** For each partition, try inserting it at every position in the current solution; pick the position that minimizes total matrix-upload cost. O(n²) but produces 60% less redundant data on consoles.
4. **Output:** A set of chunks, each with ≤K bones and a remapped bone index palette.

**Signals needed:** Per-vertex bone indices + weights (= `skin_data`). No geometry, no skeleton required.
**Complexity:** O(F × J) to build face sets; O(F log F) for simple, O(F²) for cheapest insertion. For KOTOR meshes (typically 500-5000 faces), this is trivially fast.
**Handles open shells?** ✅ Yes — it operates on faces and their vertex bone sets, no topology assumption.
**Pure Python/numpy?** ✅ Trivially — the core is set operations and sorting.
**Joint alignment?** ❌ Not directly — it minimizes bone palette overlap, but doesn't guarantee cuts at joints. However, because it groups faces sharing bone sets, natural joint boundaries (where dominant bone changes) tend to become partition boundaries.

**Key quote:** "Optimally partitioning an arbitrary mesh is an NP-complete problem... but by using heuristics we can generate solutions that perform quite well in practice."

---

### B2. Bounded Biharmonic Weights / Influence-Region Segmentation (Jacobson et al. 2011)

**Source:** Jacobson, Baran, Popović, Sorkine, "Bounded Biharmonic Weights for Real-Time Deformation," ACM TOG 30(4), SIGGRAPH 2011.
**Relevance:** ⭐⭐⭐⭐ — For boundary alignment and influence-field computation.

**How it works:**

BBW minimizes the Laplacian energy `∫‖Δw_j‖² dV` subject to:
- Handle interpolation: `w_j = δ_{jk}` at handle k
- Partition of unity: `Σ_j w_j = 1`
- Bounds: `0 ≤ w_j ≤ 1`

This produces smooth, localized, non-negative weight fields. The key insight for segmentation: **each bone's influence field forms a natural Voronoi-like region** on the mesh surface. Where two influence fields overlap significantly is a joint transition zone.

**For segmentation:**
1. Compute (or reuse donor) BBW weights for each bone
2. For each vertex, find the **dominant bone** (highest weight)
3. Group contiguous faces sharing the same dominant bone → anatomical segments
4. Merge small segments into neighbors
5. Apply bone-budget partitioning within each segment

**Signals needed:** Mesh geometry + bone handle positions. If donor skin weights exist, they serve the same purpose (they ARE the influence fields).
**Complexity:** Computing BBW from scratch requires QP solver (MOSEK/scipy.optimize): O(N^1.5) per handle. But reusing donor weights is O(N).
**Handles open shells?** ✅ Yes — BBW explicitly supports open cages and arbitrary topology.
**Pure Python/numpy?** ⚠️ Computing from scratch needs `scipy.sparse` + QP solver. Reusing donor weights: pure numpy.
**Joint alignment?** ✅ Excellent — dominant-bone boundaries align with joint transition zones.

**For GhostRigger:** The donor template already provides skin weights. We don't need to compute BBW from scratch — we can treat the donor's `skin_data` as the influence field and segment by dominant bone.

---

### B3. Skeleton Extraction by Mesh Contraction (Au et al. 2008)

**Source:** Au, Tai, Chu, Cohen-Or, Lee, "Skeleton Extraction by Mesh Contraction," ACM TOG 27(3), SIGGRAPH 2008.
**Relevance:** ⭐⭐⭐ — Useful for skeleton-from-mesh, but GhostRigger already has donor skeletons.

**How it works:**

1. **Contract** the mesh geometry to zero volume via constrained Laplacian smoothing (implicit, global solve)
2. **Connectivity surgery** collapses edges to produce a 1D curve skeleton
3. **Embedding refinement** centers skeleton nodes
4. **Segmentation** uses the skeleton-mesh vertex correspondence: each skeleton node owns a set of original vertices (Πₖ). Segments are derived by grouping vertices by their owning skeleton branch.

**For segmentation:** The skeleton-vertex mapping gives anatomical segments directly. Each branch of the skeleton = one body part = one candidate segment.

**Signals needed:** Mesh geometry only (no skeleton input — it extracts one).
**Complexity:** Contraction: O(N) per iteration, ~10 iterations. Surgery: O(E log E).
**Handles open shells?** ❌ No — requires **closed manifold meshes** with >5000 vertices. KOTOR meshes are open shells with arbitrary topology.
**Pure Python/numpy?** ⚠️ Needs sparse Laplacian solver. The `skeletor` Python package (navis-org/skeletor, 259 stars) implements this and is pip-installable.
**Joint alignment?** ✅ The skeleton naturally captures joint locations.

**Verdict:** Not suitable as primary algorithm due to closed-manifold requirement, but `skeletor` could provide a diagnostic skeleton for validation if needed.

---

### B4. Normalized Cuts on Face Adjacency Graph (Shi & Malik 1997/2000, adapted)

**Source:** Shi & Malik, "Normalized Cuts and Image Segmentation," IEEE TPAMI 2000. Adapted to 3D meshes by Katz & Tal (2003), Golovinskiy & Funkhouser (2008).
**Relevance:** ⭐⭐⭐ — Good theoretical framework, but overkill for this problem.

**How it works:**

1. Build a **face adjacency graph** G=(F, E) where edges connect adjacent faces (sharing an edge or vertex)
2. Weight each edge by **deformation affinity**: `w_ij = exp(-‖d_i - d_j‖² / σ²)` where `d_i` is a deformation descriptor for face i
3. Solve the **generalized eigenvalue problem**: `(D - W)y = λDy` where D is the degree matrix
4. The eigenvector corresponding to the 2nd-smallest eigenvalue gives a real-valued assignment; threshold it to get a bipartition
5. Recursively partition until each segment satisfies the bone-budget constraint

**Deformation descriptor options:**
- Bone influence set similarity (Jaccard distance between face bone sets)
- Weighted bone vector difference (treat skin weights as a point in M-dimensional space)
- Per-bone dominance (argmax bone index)

**Signals needed:** Face adjacency (already available via `_connected_face_components` pattern) + skin weights.
**Complexity:** Eigendecomposition of sparse N×N matrix: O(N^1.5) to O(N²). For 5000 faces, feasible.
**Handles open shells?** ✅ Yes — graph-based, topology-agnostic.
**Pure Python/numpy?** ✅ `scipy.sparse.linalg.eigsh` handles sparse symmetric matrices.
**Joint alignment?** ✅ If edge weights encode deformation similarity, cuts naturally fall at joint boundaries.
**Bone budget?** ⚠️ Normalized cuts don't directly enforce a K-bone constraint — you need a custom stopping criterion (check bone union at each recursion level).

**Verdict:** Elegant but introduces unnecessary complexity. The eigenvalue solve is heavier than needed and doesn't directly enforce the K-bone constraint. Better suited as a post-processing refinement.

---

### B5. Unreal Engine's Section → Chunk Pipeline (Industry Reference)

**Source:** Unreal Engine 5.8 Documentation, "Skeletal Mesh Rendering Paths."
**Relevance:** ⭐⭐⭐⭐ — Reference for how production engines handle this.

**How UE does it:**

1. **Sections** are defined by material assignments (one section per material)
2. Within each section, the build process creates **Chunks** — subdivisions where the bone palette would exceed the platform limit
3. Chunk creation is automatic at import/build time
4. Each chunk = one draw call at runtime
5. UE defaults: 8-bit bone index = 256 bone palette; mobile = 75 bones per section; KOTOR's equivalent is 16

**Key difference from GhostRigger:** UE's chunking is purely bone-budget-driven (like B1 above). It does NOT explicitly align chunks to joints — it relies on the artist having created reasonable skin weights. UE doesn't care about visual tearing because each chunk is still rendered as part of the same continuous mesh (shared vertex buffer, just different index ranges). The GPU blends across chunk boundaries because the vertices are duplicated at the seam with their full weight sets.

**Insight for GhostRigger:** In UE, chunk boundaries are invisible because the GPU renders the full mesh in one vertex buffer. KOTOR is different — each node is a **separate mesh** with its own `bone_map`. Vertices at the boundary belong to one node or the other, and during animation, if a vertex on node A is influenced by a bone in node B's hierarchy, it won't deform correctly. This is why **joint alignment matters more for KOTOR than for modern engines**.

---

## C. RECOMMENDED ALGORITHM: Bone-Influence-Aware Greedy Partitioning (BIAGP)

### Rationale

Given GhostRigger's constraints:
- ✅ Donor skin weights available (`_skin_weighted_bone_map_fit_positions()` reads them)
- ✅ Python/numpy/trimesh stack, no QP solver guaranteed
- ✅ Open-shell meshes with arbitrary topology
- ✅ K=16 bone palette limit
- ✅ Existing `build_adjacency_graph()` and `_connected_face_components()` utilities

The recommended approach is a **hybrid of B1 (greedy bone-palette insertion) + B2 (dominant-bone influence regions)**:

1. **Phase 1** uses dominant-bone regions from skin weights to establish anatomically meaningful initial segments (joint alignment)
2. **Phase 2** checks each segment against the K-bone budget and splits over-budget segments using greedy bone-palette partitioning (bone budget)
3. **Phase 3** refines boundaries to ensure no face straddles a joint transition

This is implementable in ~300-400 lines of pure Python/numpy, reusing existing utilities.

---

### Step-by-Step Algorithm

#### Phase 0: Extract Per-Vertex Bone Data

```python
def extract_vertex_bone_sets(
    skin_data: List[VertexSkinData],
    bone_map: List[str],
) -> List[set[int]]:
    """Return, for each vertex, the set of bone indices that influence it."""
    result = []
    for vsd in skin_data:
        bone_indices = set()
        for bw in vsd.influences:
            if bw.weight > 0:  # skip zero-weight entries
                bone_indices.add(int(bw.bone_index))
        result.append(bone_indices)
    return result
```

#### Phase 1: Dominant-Bone Region Growing (Joint Alignment)

For each face, compute the **dominant bone** = the bone with the highest total weight across the face's 3 vertices. Then grow connected regions of faces sharing the same dominant bone.

```python
def compute_face_dominant_bones(
    faces: List[Sequence[int]],
    skin_data: List[VertexSkinData],
) -> List[int]:
    """For each face, return the bone index with highest aggregate weight."""
    face_dominant = []
    for face in faces:
        bone_weight_sum: Dict[int, float] = defaultdict(float)
        for vi in face[:3]:
            if vi < len(skin_data):
                for bw in skin_data[vi].influences:
                    bone_weight_sum[int(bw.bone_index)] += float(bw.weight)
        if bone_weight_sum:
            face_dominant.append(max(bone_weight_sum, key=bone_weight_sum.get))
        else:
            face_dominant.append(-1)  # unweighted face
    return face_dominant
```

Then group faces by dominant bone using the face adjacency graph (adapted from `_connected_face_components`). This produces **anatomical regions** — each region is a contiguous patch of mesh dominated by one bone.

**Result:** Initial segments S₁ ... Sₘ where each Sᵢ is a connected face group with the same dominant bone.

#### Phase 2: Bone-Budget Enforcement (K=16 Check)

For each segment Sᵢ, compute the **union of bone influences** across all its vertices:

```python
def segment_bone_union(
    face_indices: List[int],
    faces: List[Sequence[int]],
    vertex_bone_sets: List[set[int]],
) -> set[int]:
    bones = set()
    for fi in face_indices:
        for vi in faces[fi][:3]:
            if vi < len(vertex_bone_sets):
                bones |= vertex_bone_sets[vi]
    return bones
```

If |segment_bone_union(Sᵢ)| ≤ 16: ✅ keep as-is.

If |segment_bone_union(Sᵢ)| > 16: ❌ split using greedy bone-palette partitioning (Phase 2b).

#### Phase 2b: Greedy Bone-Palette Splitting (for Over-Budget Segments)

When a segment exceeds K=16 bones (e.g., a dense torso with many spine/rib influences), split it:

1. **Sort faces** by their bone-set size (ascending — faces with fewer bones first)
2. **Initialize** the first chunk with the first face's bone set
3. **For each remaining face:**
   - Compute `new_union = current_chunk_bones | face_bone_set`
   - If `|new_union| ≤ 16`: add face to current chunk, update `current_chunk_bones`
   - If `|new_union| > 16`: close current chunk, start new chunk with this face
4. **Post-process:** merge chunks that are small or share many bones (cheapest-insertion optimization from B1)

```python
def greedy_bone_budget_split(
    face_indices: List[int],
    faces: List[Sequence[int]],
    vertex_bone_sets: List[set[int]],
    max_bones: int = 16,
) -> List[List[int]]:
    """Split faces into groups where each group's bone union ≤ max_bones."""
    # Build per-face bone sets, sort by size
    face_bones = []
    for fi in face_indices:
        bones = set()
        for vi in faces[fi][:3]:
            if vi < len(vertex_bone_sets):
                bones |= vertex_bone_sets[vi]
        face_bones.append((fi, bones))
    face_bones.sort(key=lambda x: len(x[1]))  # fewest-bone faces first

    chunks = []
    current_faces = []
    current_bones = set()
    for fi, fb in face_bones:
        union = current_bones | fb
        if len(union) <= max_bones:
            current_faces.append(fi)
            current_bones = union
        else:
            if current_faces:
                chunks.append(current_faces)
            current_faces = [fi]
            current_bones = set(fb)
    if current_faces:
        chunks.append(current_faces)
    return chunks
```

**Connectivity check:** After greedy splitting, verify each chunk is connected in the face-adjacency graph. If not, split into connected sub-chunks (they automatically satisfy the bone budget since subsets preserve the ≤K property).

#### Phase 3: Boundary Refinement (Optional, Joint Snapping)

After Phases 1-2, partition boundaries should be checked for joint alignment. A boundary face pair (face in chunk A, adjacent face in chunk B) is "joint-aligned" if:
- The two faces have different dominant bones
- The weight transition between them is gradual (no single bone has >80% influence on both)

If a boundary is NOT joint-aligned (e.g., two adjacent faces in different chunks have the same dominant bone — this can happen after Phase 2b greedy splitting), attempt to swap the boundary face to the other chunk if the bone budget allows.

**This phase is optional for v1** — Phases 1-2 already produce joint-aligned boundaries in the common case because Phase 1 segments by dominant bone.

#### Phase 4: Node Reconstruction

For each final segment/chunk, build a new `ModelNode`:
1. Collect unique vertex indices used by the segment's faces
2. Build vertex remap (old index → new index)
3. Build the segment's `bone_map`: the union of bone indices, looked up in the original `bone_map`
4. Remap `skin_data`: for each vertex, remap `bone_index` from global to segment-local
5. Copy `vertices`, `normals`, `tangents`, `uvs`, `faces` (remapped), `face_uvs`, `face_mats`

---

### Data Structures Needed

```python
@dataclass
class FaceBoneSet:
    """Per-face bone influence data."""
    face_index: int
    dominant_bone: int           # highest aggregate weight bone
    bone_set: frozenset[int]     # all influencing bones (union of 3 vertices)
    bone_weight_vector: Dict[int, float]  # bone -> total weight (for affinity)

@dataclass
class MeshSegment:
    """A candidate sub-mesh segment."""
    face_indices: List[int]
    bone_union: set[int]
    dominant_bone: int
    is_connected: bool
    vertex_indices: Set[int]     # unique vertices used by faces
```

### Estimated Implementation Complexity

| Component | Lines of Code | Difficulty |
|-----------|--------------|------------|
| Phase 0: vertex bone extraction | ~20 | Easy |
| Phase 1: dominant-bone regions | ~60 | Medium |
| Phase 2: bone-budget check + greedy split | ~80 | Medium |
| Phase 3: boundary refinement | ~50 | Hard (optional for v1) |
| Phase 4: node reconstruction (reuse existing pattern) | ~100 | Medium |
| Tests + validation | ~100 | Medium |
| **Total** | **~350-400** | **Medium** |

The existing `_split_mesh_node_by_components()` (L5654) and its vertex/face remapping logic (~100 lines, L5676-5797) can be directly reused for Phase 4.

---

## D. EDGE CASES

### D1. A Single Region Needs >16 Bones (Dense Torso)

**Scenario:** A torso mesh segment has 20+ influencing bones (spine, ribs, clavicles, pelvis). The dominant-bone approach produces one large segment that exceeds K=16.

**Solution:** Phase 2b (greedy bone-palette splitting) handles this. The greedy algorithm splits the segment into 2+ sub-segments, each with ≤16 bones. The split will likely occur at a natural boundary (where the bone set changes) because faces are sorted by bone-set size.

**Trade-off:** The split may not be perfectly joint-aligned. Mitigation: after greedy splitting, check boundary faces and attempt swaps (Phase 3). If the torso truly requires >16 bones with no clean cut, the only option is to **reduce influences** (drop lowest-weight bones, re-normalize) — this is a weight-optimization step, not a segmentation step.

### D2. Donor Weights Are Unavailable

**Scenario:** No donor template loaded, or donor has no `skin_data`.

**Solution:** Fall back to **geometric segmentation** using `segment_mesh_by_bones()` (nearest-bone by Euclidean distance) from `heat_diffusion_skinning.py`. This gives approximate dominant-bone regions. Then run Phase 2 (bone-budget check) on the geometric regions.

**Alternative:** Run the full heat-diffusion skinning pipeline (`compute_heat_diffusion_weights()`) to synthesize weights from bone positions, then use those as the influence field for Phase 1.

**Code path:**
```python
if node.skin_data and node.bone_map:
    # Use existing skin weights (preferred)
    vertex_bone_sets = extract_vertex_bone_sets(node.skin_data, node.bone_map)
elif bone_positions_available:
    # Synthesize weights via heat diffusion
    weights = compute_heat_diffusion_weights(vertices, faces, bone_positions, ...)
    vertex_bone_sets = [{k for k, v in w.items() if v > threshold} for w in weights]
else:
    # No bone data at all — fall back to current topological splitter
    return _split_mesh_node_by_components(node)
```

### D3. UV Seams and Smoothing Groups

**Problem:** KOTOR uses per-face UVs (`face_uvs`) and per-face materials (`face_mats`). Splitting a mesh creates duplicate vertices at the boundary (vertices shared between two chunks). Each chunk needs its own copy of boundary vertices with correct UVs.

**Solution:** The existing `_split_mesh_node_by_components()` already handles this correctly (L5676-5797) — it builds a `vertex_map` and `uv_map` per component, duplicating shared vertices. The same pattern applies for bone-aware splitting. The only addition: boundary vertices need their `skin_data` entries duplicated and `bone_index` remapped to the chunk-local palette.

**Smoothing groups / normals:** KOTOR doesn't use explicit smoothing groups. Normals are per-vertex (`node.normals`). When duplicating boundary vertices, copy the normal as-is. No special handling needed.

### D4. Faces With Zero or Missing Skin Data

**Problem:** Some faces may have vertices with empty `skin_data` (no influences). This happens for unweighted geometry mixed into a skinned node.

**Solution:** Assign these faces to the segment of their dominant-bone-region neighbor (nearest adjacent face with skin data). If no skinned neighbor exists, assign to the segment with the smallest bone palette (leaving room for future weighting).

### D5. Single Face Requiring >16 Bones

**Problem:** A single triangle has 3 vertices × 4 influences = 12 bones, but with bone indices spanning >16 distinct values across non-adjacent faces in a dense region.

**Note:** A single face can have at most 12 distinct bone indices (3 vertices × 4 max influences). Since 12 < 16, **a single face can never exceed the K=16 budget by itself**. The problem only arises when multiple faces in a connected region collectively exceed 16 bones.

**However:** If the donor mesh has more than 4 influences per vertex (some DCC tools allow 8+), a single face could theoretically have 3×8=24 bone indices. In that case, **cap influences to 4 first** using `cap_influences()` from `heat_diffusion_skinning.py`, then proceed with segmentation.

### D6. Bone Index Remapping Across Nodes

**Problem:** When a mesh is split, each sub-node gets its own `bone_map` (palette). Bone indices in `skin_data` must be remapped from the global palette to the sub-node's local palette.

**Solution:**
```python
# For each segment, build local bone_map and remap skin_data
local_bone_list = sorted(segment.bone_union)
global_to_local = {global_idx: local_idx for local_idx, global_idx in enumerate(local_bone_list)}
local_bone_map = [original_bone_map[g] for g in local_bone_list]

for vi in segment.vertex_indices:
    for bw in skin_data[vi].influences:
        bw.bone_index = global_to_local[int(bw.bone_index)]
```

This must happen during Phase 4 (node reconstruction).

---

## E. IMPLEMENTATION ROADMAP

### Phase 1: Core Algorithm (v1 — Minimum Viable)

1. **Create `bone_aware_splitter.py`** in `GhostRigger.Core.Math/Python/src/math/`
2. Implement `extract_vertex_bone_sets()`, `compute_face_dominant_bones()`, `greedy_bone_budget_split()`
3. Implement `partition_skinned_mesh()` — the main entry point combining all phases
4. Wire into `split_imported_mesh_nodes()` — remove the `skipped_skinned` guard, route skinned nodes to the new splitter
5. Test on a known >16-bone creature (e.g., Drexl, which has wing/torso/pelvis complexes)

**Estimated effort:** 2-3 days, ~350 lines.

### Phase 2: Refinements (v2)

1. Add Phase 3 (boundary refinement / joint snapping)
2. Add cheapest-insertion optimization for chunk ordering
3. Add validation: verify no split node exceeds 16 bones (assert), verify skin data integrity
4. Add diagnostic output: per-node bone count, segment visualization

### Phase 3: Integration (v3)

1. UI integration in the workflow: show split preview before applying
2. Handle the fallback path (no donor weights → heat diffusion synthesis)
3. Batch processing for multi-node meshes
4. Performance: vectorize with numpy for large meshes (>10K faces)

---

## F. KEY REFERENCES

| # | Paper / Source | Year | Key Contribution | Used For |
|---|---------------|------|-----------------|----------|
| 1 | Paanakker, "Skinned Mesh Export: Optimization" (Game Developer) | 2007 | Greedy bone-palette partitioning, cheapest insertion | **Primary algorithm (Phase 2)** |
| 2 | Jacobson et al., "Bounded Biharmonic Weights" (ACM TOG) | 2011 | Smooth localized weight fields, influence regions | **Dominant-bone segmentation (Phase 1)** |
| 3 | Au et al., "Skeleton Extraction by Mesh Contraction" (SIGGRAPH) | 2008 | Skeleton-vertex mapping for segmentation | Reference; `skeletor` Python lib available |
| 4 | Shi & Malik, "Normalized Cuts" (IEEE TPAMI) | 2000 | Graph spectral partitioning | Theoretical basis; optional refinement |
| 5 | Unreal Engine 5.8 Docs, "Skeletal Mesh Rendering Paths" | 2024 | Section→Chunk splitting reference | Industry validation |
| 6 | glTF 2.0 Spec, Skins tutorial (Khronos) | 2017+ | JOINTS_0/WEIGHTS_0 vertex attributes | Data model reference |
| 7 | `skeletor` Python library (navis-org) | 2024 | Au 2008 implementation in Python | Diagnostic tooling |
| 8 | `heat_diffusion_skinning.py` (GhostRigger existing) | — | `build_adjacency_graph`, `cap_influences`, `segment_mesh_by_bones` | **Reusable utilities** |

---

## G. SUMMARY

**The recommended algorithm is Bone-Influence-Aware Greedy Partitioning (BIAGP)**, a hybrid approach:

1. **Segment by dominant bone** (from donor skin weights) → anatomically aligned regions
2. **Enforce K=16 bone budget** via greedy bone-palette splitting (Paanakker 2007) → compliant sub-meshes
3. **Refine boundaries** at joint transition zones → tear-free animation

This approach:
- Uses data already available in GhostRigger (`skin_data`, `bone_map`, donor templates)
- Is implementable in pure Python/numpy (~350 LOC)
- Handles open-shell, arbitrary-topology meshes
- Produces joint-aligned partition boundaries
- Falls back gracefully when donor weights are unavailable (heat diffusion synthesis)
- Reuses existing code patterns (`_connected_face_components`, `_split_mesh_node_by_components` vertex remapping)

The critical implementation change is removing the `skipped_skinned` guard at lines 5661 and 5777 of `headless_body_workflow.py` and routing skinned nodes through the new `partition_skinned_mesh()` function instead.
