# Mesh Containment for Open-Shell Meshes: Research Report

**Date:** 2026-06-30
**Context:** GhostRigger/KOTOR creature mesh import — fitting skeleton deformation bones inside non-watertight triangle meshes.
**Status:** Literature-grounded algorithm recommendation with implementation path.

---

## Executive Summary

The current codebase has two containment paths, both inadequate for open-shell meshes:

1. **Ray-casting parity** (`containment_fit.py`): 7-direction Möller-Trumbore majority vote. Requires watertight mesh. Fails on open boundaries.
2. **Oriented bounding box** (`_oriented_bounds_containment_solution` in `headless_body_workflow.py`): Tests if bones are inside a rotated AABB, NOT the actual mesh surface. Labeled `containment_guarantee: "oriented_bounds_only"`.

**Recommendation:** Replace both with a **signed-distance + generalized-winding-number hybrid** for the containment test, and use a **penalty-based gradient descent** with multi-start rotation hypotheses for the transform optimization. Use `igl.signed_distance` (libigl Python bindings) if available, else fall back to a pure-numpy GWN implementation with trimesh `ProximityQuery` for nearest-point acceleration.

---

## Part A: The Three Containment Definitions Compared

### A1. Signed-Distance (Local Normal + Proximity)

#### Mathematical Definition

Given query point **p** and mesh **M** (vertices V, faces F):

1. Find the nearest surface point **q** on M: **q** = argmin_{q'∈M} ‖**p** − **q'**‖
2. Let **n** be the outward-facing normal at **q** (face normal of the triangle containing **q**, or vertex-normal-interpolated for smooth surfaces)
3. **signed_distance(p)** = (**p** − **q**) · **n̂**

- **Negative** → **p** is inside the surface
- **Positive** → **p** is outside
- **Zero** → **p** is on the surface

This is the "pseudonormal" method (Bærentzen & Aanæs 2005).

#### How trimesh implements it (`trimesh.proximity.signed_distance`)

From the trimesh source (`proximity.py`):

```python
# 1. Find closest point + distance + triangle_id via R-tree + KD-tree
closest, distance, triangle_id = closest_point(mesh, points)

# 2. For points far from surface, determine sign:
#    Case A: projection lands INSIDE the closest triangle → use face normal
normals = mesh.face_normals[triangle_id]
projection = points[nonzero] - dot_to_normal * normals  # project to triangle plane
barycentric = points_to_barycentric(triangles, projection)
ontriangle = (all barycentric coords in [−tol, 1+tol])

# Where projection IS in the triangle:
sign = sign(dot(normal, point − projection))

#    Case B: projection lands OUTSIDE triangle (near edge/vertex) → ray-casting fallback
inside = mesh.ray.contains_points(points[~ontriangle])
sign = inside * 2 − 1.0
```

**Sign convention in trimesh:** inside → positive, outside → negative.

#### Failure Modes

| Failure Mode | Cause | Impact on GhostRigger |
|---|---|---|
| **Open boundaries** | Ray-casting fallback (Case B) gives inconsistent parity through gaps | **Critical** — KOTOR creature meshes (wings, capes, mouths) frequently have holes |
| **Flat surfaces** | Normal dot product is meaningless far from surface; near a plane, the sign oscillates based on which face is nearest | Moderate — creature meshes have some flat regions |
| **Near-edge ambiguity** | Closest feature is an edge, not a face; face normal of one of the two adjacent triangles gives arbitrary sign | High at thin features (ears, fingers) |
| **Degenerate/inconsistent normals** | Some exporters produce flipped normals on subsets of faces | **Critical** — OBJ/FBX exports from 3ds Max, Blender often have mixed normals |
| **Self-intersections** | Nearest surface point may be on a self-intersecting face with wrong normal direction | Moderate |

#### Computational Cost
- O(N log M) per query via R-tree + KD-tree acceleration
- ~50–60 bones against 10k–50k vertex mesh: **< 50ms** (trimesh `ProximityQuery`)
- With `embreex` installed: even faster ray-casting fallback

#### Implementation Complexity
- **Lowest** of the three options
- `trimesh.proximity.ProximityQuery(mesh).signed_distance(points)` — one function call
- But NOT robust on open shells due to ray-casting fallback

---

### A2. Generalized Winding Number (GWN) — Jacobson et al. 2013

#### Mathematical Definition

For a point **p** and a mesh M with faces F = {f₁, ..., f_m}:

$$w(\mathbf{p}) = \sum_{f \in F} \frac{\Omega_f(\mathbf{p})}{4\pi}$$

where **Ω_f(p)** is the **solid angle** subtended by triangle f as seen from **p**.

**Solid angle formula** (van Oosterom & Strackee 1983):

Let **a** = v₁ − **p**, **b** = v₂ − **p**, **c** = v₃ − **p** (vectors from query point to the triangle's three vertices).

$$\tan\left(\frac{\Omega_f}{2}\right) = \frac{\det[\mathbf{a}\ \mathbf{b}\ \mathbf{c}]}{\|\mathbf{a}\|\|\mathbf{b}\|\|\mathbf{c}\| + (\mathbf{a}\cdot\mathbf{b})\|\mathbf{c}\| + (\mathbf{b}\cdot\mathbf{c})\|\mathbf{a}\| + (\mathbf{c}\cdot\mathbf{a})\|\mathbf{b}\|}$$

Use `atan2(numerator, denominator) * 2` for numerical stability (handles the wraparound at ±π).

#### Properties

| Property | Detail |
|---|---|
| **Watertight mesh** | w = 0 outside, w = 1 inside (exact, up to float precision) |
| **Open mesh** | Smooth confidence field that degrades gracefully near holes — w ∈ (0, 1) near boundaries, still meaningful |
| **Harmonicity** | ∇²w = 0 away from surface (proven via symbolic differentiation). This means w is C^∞ smooth — no local artifacts |
| **Global information** | Every face contributes to w, so local ambiguities (which face is nearest?) are resolved by global context |
| **Jump discontinuity** | ±1 across each facet — the sign encodes inside/outside cleanly |
| **Orientation sensitivity** | Requires **consistent** triangle orientation. Randomly oriented faces will produce garbage |

#### Failure Modes

| Failure Mode | Cause | Impact |
|---|---|---|
| **Inconsistent normals** | GWN sums signed solid angles; flipped faces cancel out | **Critical** — but can be detected: run a mesh-repair pass to unify normals first |
| **Very large holes** | If >50% of the enclosing surface is missing, the winding number drops below 0.5 and containment becomes ambiguous | Moderate — threshold tuning needed |
| **Self-intersecting meshes** | GWN is still well-defined (it's a geometric sum), but the field may be >1 or <0 in regions of overlap | Low — usually still in the "inside" range |
| **Far from mesh** | w → 0 smoothly — correct behavior but may be confused with "near a large hole" | Low |

#### Computational Cost

**Naive:** O(m) per query point (sum over all m faces). For 10k faces × 60 bones = 600k solid-angle evaluations. Each is ~20 FLOPs → ~12M FLOPs → **~10ms in numpy vectorized**.

**Hierarchical acceleration** (Jacobson 2013, Algorithm 1+2):
- Build AABB hierarchy by bisection until clusters have ~100 faces or mostly boundary edges
- If query point is outside a node's bounding box, replace the cluster with its closure triangles (exact, O(1) per cluster)
- Measured complexity: O(m^0.43) — on a 100k-face mesh, ~80 face-clusters evaluated per query

**Fast Winding Number** (Barill et al. 2018, "Fast Winding Numbers for Soups and Clouds"):
- BVH where each node represents a cluster of triangles approximated by a single point + area + normal
- O(log m) per query point after O(m) preprocessing
- Handles **triangle soups** (no connectivity needed) and point clouds
- Available as `igl.fast_winding_number_for_meshes(v, f, q)` in libigl Python bindings

**Practical estimate for GhostRigger:** 60 bones × 10k-50k face mesh:
- Naive vectorized numpy: **10–50ms** (fast enough!)
- libigl fast winding number: **<5ms**

#### Implementation Complexity
- **Pure numpy GWN**: ~40 lines (vectorized solid-angle sum). No dependencies beyond numpy.
- **libigl**: `igl.winding_number(v, f, q)` — one function call, returns (n,) array of winding numbers.

#### Key References
- Jacobson, L., Kavan, L., Sorkine-Hornung, O. (2013). "Robust Inside-Outside Segmentation using Generalized Winding Numbers." ACM TOG 32(4). [Paper](https://users.cs.utah.edu/~ladislav/jacobson13robust/jacobson13robust.pdf)
- Van Oosterom, A., Strackee, J. (1983). "The solid angle of a plane triangle." IEEE Trans. Biomed. Eng.
- Barill, G., Dickson, N.G., Schmidt, A., Levin, D.I.W., Jacobson, A. (2018). "Fast Winding Numbers for Soups and Clouds." ACM TOG 37(4).

---

### A3. Oriented Bounds (Current Approach)

#### Mathematical Definition
Compute the oriented bounding box (OBB) of the mesh: the minimum-volume box aligned to the mesh's principal axes (via PCA of vertices). A point is "contained" if it lies inside this box.

#### Failure Modes
| Mode | Detail |
|---|---|
| **Not actual surface containment** | A bone inside the OBB may be outside the mesh surface (concavities, thin limbs) |
| **Over-permissive** | OBB of a character mesh includes all the empty space around concavities (armpits, between legs) |
| **Ignores mesh geometry entirely** | A crescent-shaped mesh has the same OBB as a full disc |

#### Computational Cost
O(n log n) for PCA + O(N) for point-in-box test. Trivial.

#### Verdict
**Inadequate.** This is what the codebase uses now (labeled `containment_guarantee: "oriented_bounds_only"`), and it does not test surface containment at all. It should be replaced.

---

### A4. Comparison Summary

| Criterion | Signed-Distance | GWN (Jacobson) | Oriented Bounds (current) |
|---|---|---|---|
| **Open-shell robustness** | ⚠️ Partial (fails on ray fallback) | ✅ **Excellent** | N/A (not surface-based) |
| **Watertight mesh accuracy** | ✅ Exact | ✅ Exact | ❌ Approximate |
| **Smooth/optimizable** | ⚠️ Discontinuous at feature transitions | ✅ **C^∞ smooth** | ❌ Non-differentiable box |
| **Computational cost (60 pts)** | ~50ms | ~10–50ms (naive), <5ms (libigl) | <1ms |
| **Implementation effort** | 1 line (trimesh) | ~40 lines (numpy) or 1 line (libigl) | Already implemented |
| **Gives distance metric** | ✅ Yes (meters) | ❌ No (dimensionless 0–1) | ❌ No |
| **Requires consistent normals** | ⚠️ Yes (for sign) | ⚠️ Yes (for orientation) | No |

---

## Part B: The Transform Optimization Problem

### B1. Formal Statement

Given:
- **Bone positions** B = {b₁, ..., b_N} ∈ ℝ³ (N ≈ 50–60, the KOTOR skeleton's deformation bones)
- **Target mesh** M = (V, F) with V ∈ ℝ^{n×3}, F ∈ ℤ^{m×3} (n ≈ 10k–50k vertices, m ≈ 20k–100k faces)

Find transform parameters θ = (s, R, t) where:
- s ∈ ℝ⁺ (uniform scale)
- R ∈ SO(3) (rotation, 3 DOF via axis-angle or quaternion)
- t ∈ ℝ³ (translation, 3 DOF)

such that the transformed bones **all satisfy the containment criterion**:

$$\text{contains}_M(s \cdot R \cdot \mathbf{b}_i + \mathbf{t}) = \text{True} \quad \forall i \in \{1, \ldots, N\}$$

where `contains_M(p)` is one of the containment tests from Part A.

### B2. Why This Is Non-Convex

The problem is non-convex for three reasons:

1. **Rotation R ∈ SO(3):** The rotation group is a non-convex manifold. Even with a linearization (axis-angle with small-angle approximation), the feasible set can have multiple disconnected components (e.g., rotating a bone array 180° to fit a symmetric mesh).

2. **Containment constraint discontinuity:** The `contains` predicate is a binary function — it's 1 inside, 0 outside. This is non-smooth and non-convex. The feasible set {θ : all bones inside} can be a complex non-convex region.

3. **Scale–rotation coupling:** Changing R moves bones in different directions (rigid rotation about centroid), so the scale s needed for containment depends on R.

### B3. Soft Penalty Formulation (Recommended)

Convert the hard containment constraint into a differentiable penalty:

$$\min_{\theta} \; E(\theta) = \sum_{i=1}^{N} \big[\max(0, \, -d_i(\theta))\big]^2$$

where **d_i(θ)** is the signed containment metric of the i-th transformed bone:

- **With signed distance:** d_i = signed_distance_M(s·R·b_i + t). Positive = inside. Penalty activates when d_i < 0 (outside).
- **With GWN:** d_i = w_M(s·R·b_i + t) − τ, where τ ∈ [0.3, 0.5] is a containment threshold. Penalty activates when w < τ.

**Advantages:**
- Differentiable almost everywhere (signed distance is C⁰; GWN is C^∞)
- Standard unconstrained optimization applies (gradient descent, L-BFGS, etc.)
- Naturally handles "almost inside" cases gracefully
- Can add regularization terms (minimize scale distortion, minimize rotation from seed, etc.)

**Quadratic exterior penalty** (Bertsekas 1999, §4.2):
The penalty max(0, −d)² is zero when the constraint is satisfied, positive when violated. Increasing a penalty weight λ → ∞ drives the solution toward feasibility.

### B4. Solver Approaches

#### Approach 1: Penalty-Based Gradient Descent (Recommended)

```
Algorithm: Penalty Gradient Descent for Bone Containment
─────────────────────────────────────────────────────────
Input: bones B (N×3), mesh M, seed transform (s₀, R₀, t₀)
Output: optimized transform (s, R, t)

1. θ ← (s₀, R₀, t₀)
2. for iter in range(max_iter):
3.     B_transformed ← s · (R @ B.T).T + t           # Apply current transform
4.     d ← containment_metric(M, B_transformed)        # Signed distance or GWN
5.     violations ← max(0, −d)                          # Positive where outside
6.     if max(violations) < ε: break                    # Converged — all inside
7.     ∇E ← compute_gradient(θ, B, M, d)                # Finite differences or analytic
8.     θ ← θ − learning_rate · ∇E                      # Gradient step
9.     project R onto SO(3)                             # Re-orthonormalize
10. return θ
```

**Gradient computation options:**
- **Finite differences** (simplest): perturb each of the 7 parameters (1 scale + 3 rotation + 3 translation) by δ, re-evaluate E. Cost: 8 evaluations per gradient step.
- **Analytic via nearest-point normal** (for signed distance): The gradient of signed_distance w.r.t. bone position is the face normal **n** at the nearest point. So ∂d_i/∂b_i = n_i. Then chain rule through s, R, t gives analytic gradients. Cost: 1 evaluation per step.

**Tradeoffs:**
- ✅ Simple, ~100 lines
- ✅ Uses existing trimesh/libigl containment functions
- ✅ Graceful handling of partial infeasibility
- ⚠️ Can get stuck in local minima (mitigate with multi-start, below)
- ⚠️ Finite-difference gradient is O(7) × containment cost per step

#### Approach 2: Alternating Optimization (Block Coordinate Descent)

Exploit the structure: translation and scale are convex subproblems when R is fixed.

```
Algorithm: Alternating Optimization
────────────────────────────────────
1. Fix R = R₀ (from seed or initial guess)
2. Solve for (s, t): 
   - This is a convex problem in (s, t) for fixed R
   - Use bisection on s (current code's approach) or LP for t given s
3. Fix (s, t)
4. Solve for R:
   - Use ICP-style SVD alignment: project bones to nearest surface points, 
     then compute optimal R via Kabsch/Procrustes (SVD of cross-covariance)
5. Repeat steps 2–4 until convergence
```

**Kabsch/Procrustes for rotation update** (point-to-point ICP):
Given current nearest surface points P = {p₁, ..., p_N} and bone positions X = {x₁, ..., x_N}:
1. Compute centroids: x̄ = mean(X), p̄ = mean(P)
2. Center: X̃ = X − x̄, P̃ = P − p̄
3. Cross-covariance: M = P̃ᵀ X̃  (3×3)
4. SVD: M = UΣVᵀ
5. R = U · diag(1, 1, det(UVᵀ)) · Vᵀ

**Tradeoffs:**
- ✅ Convex subproblems — guaranteed convergence of each block
- ✅ Kabsch rotation update is closed-form (no gradient)
- ⚠️ ICP is notoriously slow to converge (linear convergence rate)
- ⚠️ Gets stuck in bad local minima without good initialization

#### Approach 3: Multi-Start + Penalty (Best for Robustness)

Since rotation makes the problem non-convex, sample multiple rotation hypotheses:

```
Algorithm: Multi-Start Penalty Optimization
───────────────────────────────────────────
1. Generate K rotation hypotheses R₁, ..., R_K:
   - Use seed rotation (from _landmark_based_fit_solution / Kabsch)
   - Add uniform samples on SO(3) (e.g., 6 axis-aligned, 8 diagonal, 
     or random quaternions)
2. For each R_k:
   a. Run Approach 2 (alternating optimization) to convergence → (s_k, t_k)
   b. Compute residual E_k = Σ max(0, −d_i)²
3. Return the (R_k, s_k, t_k) with lowest residual E_k
```

**Tradeoffs:**
- ✅ Most robust to non-convexity
- ✅ K = 10–20 starts is feasible (each takes ~50ms → total <1s)
- ⚠️ More compute (but one-time at import — acceptable for GhostRigger)

### B5. Recommendation for GhostRigger

**Use Approach 3 (Multi-Start + Penalty) with Approach 2 (Alternating Optimization) as the inner solver.**

Reasons:
1. **~50–60 bones, one-time at import** → no real-time constraint; can afford 10–20 starts
2. **numpy/trimesh available** → all subroutines have library support
3. **Non-convexity from rotation** → multi-start mitigates local minima
4. **Current binary-search-on-scale** can be preserved as the (s, t) inner solver for fixed R — minimal code change
5. **Seed rotation from `_landmark_based_fit_solution`** (Kabsch on landmarks) provides a strong initial guess, reducing the number of random starts needed

---

## Part C: Implementation Path

### C1. Recommended Containment Definition

**Primary: Signed-distance with GWN sign fallback.**

```
For each query point p:
  1. Compute nearest surface point q and face normal n (trimesh ProximityQuery)
  2. Compute GWN w(p) (vectorized numpy or igl.winding_number)
  3. If w(p) > threshold (e.g., 0.3): INSIDE, return +‖p−q‖
  4. If w(p) < (1−threshold): OUTSIDE, return −‖p−q‖
  5. Else (ambiguous zone near open boundary): 
       use normal-based sign: (p−q)·n as tiebreaker
```

This hybrid gets the best of both worlds:
- **Distance magnitude** from nearest-point query (needed for gradient/penalty)
- **Robust inside/outside sign** from GWN (handles open shells)
- **Local fallback** for points very close to the surface

**If libigl is available:** Use `igl.signed_distance(V, F, P, sign_type='winding_number')` — this does exactly the hybrid above in optimized C++.

### C2. Concrete Functions to Use

```python
import numpy as np
import trimesh

# ─── Containment test ───
def containment_signed_distances(mesh, points):
    """
    Returns signed containment metric for each point.
    Positive = inside mesh (even for open shells).
    Uses GWN for robust sign, trimesh for distance magnitude.
    """
    # Option A: libigl (if installed)
    try:
        import igl
        s, sqrd, i, c = igl.signed_distance(
            points, mesh.vertices, mesh.faces,
            sign_type=igl.SIGNED_DISTANCE_TYPE_WINDING_NUMBER
        )
        return s  # positive inside, negative outside
    except ImportError:
        pass

    # Option B: Pure numpy/trimesh hybrid
    pq = trimesh.proximity.ProximityQuery(mesh)
    closest, distance, tri_id = pq.on_surface(points)
    
    # GWN for sign
    wn = generalized_winding_number(points, mesh.vertices, mesh.faces)
    
    # Sign: positive if w > 0.5 (inside), negative if w < 0.5
    sign = np.where(wn > 0.5, 1.0, -1.0)
    return sign * distance


def generalized_winding_number(query_pts, V, F):
    """
    Vectorized GWN computation (van Oosterom-Strackee solid angle sum).
    query_pts: (N, 3), V: (n, 3), F: (m, 3)
    Returns: (N,) array of winding numbers in [0, 1] (for open) or {0, 1} (watertight).
    """
    tri_verts = V[F]  # (m, 3, 3)
    N = query_pts.shape[0]
    m = F.shape[0]
    wn = np.zeros(N)
    
    # Process in chunks to limit memory: N × m solid angles
    CHUNK = 256
    for i in range(0, N, CHUNK):
        pts_chunk = query_pts[i:i+CHUNK]  # (c, 3)
        # Vectors from each query point to each triangle vertex
        a = tri_verts[:, 0, :][None, :, :] - pts_chunk[:, None, :]  # (c, m, 3)
        b = tri_verts[:, 1, :][None, :, :] - pts_chunk[:, None, :]
        c = tri_verts[:, 2, :][None, :, :] - pts_chunk[:, None, :]
        
        # van Oosterom-Strackee formula
        numerator = np.einsum('cmi,cmj->cm', a, np.cross(b, c))  # det[a b c]
        
        la = np.linalg.norm(a, axis=-1)
        lb = np.linalg.norm(b, axis=-1)
        lc = np.linalg.norm(c, axis=-1)
        
        denominator = (la * lb * lc 
                      + np.einsum('cmi,cmi->cm', a, b) * lc
                      + np.einsum('cmi,cmi->cm', b, c) * la
                      + np.einsum('cmi,cmi->cm', c, a) * lb)
        
        omega = np.arctan2(numerator, denominator)  # (c, m)
        wn[i:i+CHUNK] = omega.sum(axis=1) / (4.0 * np.pi)
    
    return wn
```

### C3. Transform Optimization (Multi-Start Alternating)

```python
from scipy.spatial.transform import Rotation

def fit_bones_inside_mesh(bones, mesh, seed_R=None, seed_s=1.0, seed_t=None,
                          n_starts=12, threshold=0.4, max_iter=50, tol=1e-4):
    """
    Find (s, R, t) so that all transformed bones are inside the mesh.
    Returns dict with s, R, t, residual, n_inside.
    """
    if seed_t is None:
        seed_t = mesh.centroid.copy()
    
    best = None
    
    for start_idx in range(n_starts):
        # Generate rotation hypothesis
        if start_idx == 0 and seed_R is not None:
            R = seed_R.copy()
        elif start_idx < 7:
            # 6 axis-aligned 90° rotations + identity
            axes = [np.eye(3)]
            for ax in range(3):
                for angle in [90, 180, 270]:
                    axes.append(Rotation.from_euler(ax, angle, degrees=True).as_matrix())
            R = axes[start_idx]
        else:
            R = Rotation.random().as_matrix()
        
        # Inner solver: alternating optimization
        s, t = seed_s, seed_t.copy()
        prev_residual = np.inf
        
        for it in range(max_iter):
            # Step 1: Transform bones with current (s, R, t)
            X = s * (R @ bones.T).T + t  # (N, 3)
            
            # Step 2: Evaluate containment
            sd = containment_signed_distances(mesh, X)
            violations = np.maximum(0, threshold_mesh - sd)  # positive where outside
            residual = np.sum(violations ** 2)
            
            if residual < tol:
                break
            
            # Step 3: Update scale (bisection — reuse existing approach)
            # Increase s until all inside, then binary search
            s = _update_scale(mesh, bones, R, t, s, threshold=threshold)
            
            # Step 4: Update translation (move toward centroid of violations)
            X = s * (R @ bones.T).T + t
            sd = containment_signed_distances(mesh, X)
            outside_mask = sd < threshold
            if outside_mask.any():
                pq = trimesh.proximity.ProximityQuery(mesh)
                closest, _, _ = pq.on_surface(X[outside_mask])
                # Push violated bones toward their nearest surface point
                t_correction = np.mean(closest - X[outside_mask], axis=0)
                t += 0.5 * t_correction  # damped step
            
            # Step 5: Update rotation (Kabsch on violated bones → nearest surface)
            X = s * (R @ bones.T).T + t
            sd = containment_signed_distances(mesh, X)
            outside_mask = sd < threshold
            if outside_mask.any() and outside_mask.sum() >= 3:
                pq = trimesh.proximity.ProximityQuery(mesh)
                closest, _, _ = pq.on_surface(X[outside_mask])
                R = _kabsch_update(X[outside_mask], closest, R)
            
            # Convergence check
            if abs(prev_residual - residual) < tol:
                break
            prev_residual = residual
        
        # Evaluate final
        X = s * (R @ bones.T).T + t
        sd = containment_signed_distances(mesh, X)
        n_inside = np.sum(sd >= threshold)
        total_residual = np.sum(np.maximum(0, threshold - sd) ** 2)
        
        if best is None or total_residual < best['residual']:
            best = {'s': s, 'R': R, 't': t, 
                    'residual': total_residual, 'n_inside': int(n_inside)}
    
    return best


def _kabsch_update(source_pts, target_pts, R_current):
    """Update rotation via SVD (Kabsch algorithm), small step from current."""
    src_centroid = source_pts.mean(axis=0)
    tgt_centroid = target_pts.mean(axis=0)
    src_centered = source_pts - src_centroid
    tgt_centered = target_pts - tgt_centroid
    
    M = tgt_centered.T @ src_centered  # (3, 3) cross-covariance
    U, S, Vt = np.linalg.svd(M)
    d = np.linalg.det(U @ Vt)
    R_delta = U @ np.diag([1, 1, d]) @ Vt
    
    # Interpolate toward new rotation (damped)
    R_new = R_delta @ R_current
    # Re-orthonormalize
    U, S, Vt = np.linalg.svd(R_new)
    R_new = U @ Vt
    return R_new
```

### C4. Estimated Lines of Code

| Component | Lines | Notes |
|---|---|---|
| GWN vectorized (pure numpy) | ~45 | `generalized_winding_number()` above |
| Containment signed distance hybrid | ~25 | `containment_signed_distances()` |
| Scale bisection (reuse existing) | ~30 | Already in `containment_fit.py` |
| Kabsch rotation update | ~15 | `_kabsch_update()` |
| Multi-start driver | ~80 | `fit_bones_inside_mesh()` |
| **Total new code** | **~195** | Plus ~20 lines of integration glue |

### C5. Validation Tests

```python
# Test 1: Watertight sphere — all points at origin must be "inside"
mesh = trimesh.creation.icosphere(subdivisions=3)
pts = np.zeros((1, 3))
assert containment_signed_distances(mesh, pts)[0] > 0  # inside → positive

# Test 2: Watertight sphere — point far outside
pts = np.array([[10.0, 0, 0]])
assert containment_signed_distances(mesh, pts)[0] < 0  # outside → negative

# Test 3: Open hemisphere (cut sphere) — center should still read "inside"
hemisphere = mesh.copy()
# Remove top half of faces
z_center = (mesh.vertices[mesh.faces].mean(axis=1))[:, 2]
hemisphere.faces = mesh.faces[z_center < 0]
wn = generalized_winding_number(np.zeros((1, 3)), hemisphere.vertices, hemisphere.faces)
assert 0.3 < wn[0] < 0.7  # partially enclosed — winding number is fractional

# Test 4: GWN == 1 for watertight mesh
wn = generalized_winding_number(np.zeros((1, 3)), mesh.vertices, mesh.faces)
assert abs(wn[0] - 1.0) < 1e-3

# Test 5: Transform optimization — random bones inside sphere
mesh = trimesh.creation.icosphere(radius=1.0, subdivisions=3)
bones = np.random.randn(20, 3) * 0.3  # random points near center
result = fit_bones_inside_mesh(bones, mesh, n_starts=5)
assert result['n_inside'] == 20  # all bones contained

# Test 6: Real KOTOR mesh — count contained bones before/after
# (manual verification with actual creature mesh)
```

---

## Part D: Integration with Existing Codebase

### D1. Where to Add the New Code

1. **New file:** `native/GhostRigger.Core.Math/Python/src/math/winding_number.py`
   - `generalized_winding_number()`
   - `containment_signed_distances()` (GWN-hybrid)
   - Pure numpy, no external deps beyond numpy/trimesh

2. **Modify:** `native/GhostRigger.Core.Math/Python/src/math/containment_fit.py`
   - Add `fit_bones_inside_mesh()` (multi-start alternating optimization)
   - Reuse existing `_ray_contains()` and binary-search-on-scale as fallbacks
   - Add `_kabsch_update()`

3. **Modify:** `headless_body_workflow.py` `_oriented_bounds_containment_solution()`
   - Replace the OBB-based `_bounds_contains_points()` call with `containment_signed_distances()`
   - Keep the OBB approach as a fast pre-filter (if bones are outside OBB, they're definitely outside the mesh — no need for expensive GWN)
   - Update `containment_guarantee` label from `"oriented_bounds_only"` to `"surface_signed_distance"` or `"surface_winding_number"`

### D2. Performance Budget

| Operation | Cost | Notes |
|---|---|---|
| GWN (naive, 60 pts × 30k faces) | ~30ms | Vectorized numpy |
| GWN (libigl fast winding) | ~2ms | If igl installed |
| trimesh ProximityQuery.on_surface (60 pts) | ~5ms | R-tree + KD-tree |
| One optimization iteration | ~40ms | containment + Kabsch + scale search |
| 50 iterations × 12 starts | ~24s worst case | But most starts converge in <20 iters |
| **Total realistic** | **~5–10s** | For one mesh at import time |

This is acceptable for a one-time import operation.

### D3. Dependency Considerations

| Dependency | Status in codebase | Notes |
|---|---|---|
| numpy | ✅ Required | Already a hard dependency |
| trimesh | ✅ Required | Already used for mesh I/O and proximity |
| scipy | ✅ Available | For `scipy.spatial.transform.Rotation` |
| libigl (igl) | ⚠️ Optional | `pip install libigl` — prebuilt wheels for Win/Mac/Linux x86_64. Provides `igl.signed_distance` with winding number sign and `igl.winding_number`. Recommended but not required. |
| embreex | ⚠️ Optional | Speeds up trimesh ray-casting fallback. Already a trimesh soft dependency. |

**Recommendation:** Try `igl` first (it has the best winding-number implementation in Python). Fall back to pure-numpy GWN if not installable.

---

## Part E: Key Literature

1. **Jacobson, L., Kavan, L., Sorkine-Hornung, O.** (2013). "Robust Inside-Outside Segmentation using Generalized Winding Numbers." ACM Transactions on Graphics 32(4), Article 36. — The foundational paper. Defines GWN on triangle soups, proves harmonicity, presents hierarchical acceleration. [PDF](https://users.cs.utah.edu/~ladislav/jacobson13robust/jacobson13robust.pdf)

2. **Van Oosterom, A., Strackee, J.** (1983). "The solid angle of a plane triangle." IEEE Transactions on Biomedical Engineering 30(2): 125–126. — The numerically stable solid-angle formula using atan2.

3. **Barill, G., Dickson, N.G., Schmidt, A., Levin, D.I.W., Jacobson, A.** (2018). "Fast Winding Numbers for Soups and Clouds." ACM Transactions on Graphics 37(4). — O(log n) acceleration via BVH clustering. Implemented as `igl.fast_winding_number_for_meshes()`.

4. **Bærentzen, J.A., Aanæs, H.** (2005). "Signed distance computation using the angle weighted pseudonormal." IEEE Transactions on Visualization and Computer Graphics 11(3): 243–255. — The pseudonormal signed-distance method that trimesh implements (with ray-casting fallback).

5. **Besl, P.J., McKay, N.D.** (1992). "A Method for Registration of 3-D Shapes." IEEE PAMI 14(2). — Original ICP. The Kabsch/Procrustes closed-form rotation update used in Approach 2.

6. **Bertsekas, D.P.** (1999). *Nonlinear Programming*, 2nd ed. Athena Scientific. Chapter 4: Penalty and Augmented Lagrangian Methods. — Theoretical basis for the soft penalty formulation.

7. **libigl Python bindings.** `igl.signed_distance()`, `igl.winding_number()`, `igl.fast_winding_number_for_meshes()`. [Docs](https://libigl.github.io/libigl-python-bindings/igl_docs/). — The most mature Python implementation of GWN-based signed distance.

8. **trimesh proximity module.** `ProximityQuery.signed_distance()`, `closest_point()`, `nearby_faces()`. [Docs](https://trimesh.org/trimesh.proximity.html). — R-tree + KD-tree accelerated nearest-point. Hybrid: normal-based sign when projection lands in triangle, ray-casting fallback otherwise.

9. **Jacobson, A.** Geometry Processing — Registration course. [GitHub](https://github.com/alecjacobson/geometry-processing-registration). — ICP pseudocode, point-to-point SVD closed-form, point-to-plane Gauss-Newton.
