# D20-M Reset Reality Check — 2026-04-18

## Verbatim command output from main branch (commit 2455263)

```
--- vertex_space.py exists? ---
MISSING

--- _WORLDSPACE_VERT_THRESHOLD ---
1446:    # _WORLDSPACE_VERT_THRESHOLD (0.5 units), the mesh is already in world space and
1453:    _WORLDSPACE_VERT_THRESHOLD = 1.5  # units; centroid beyond this → verts are world-space
1489:    # The centroid_mag threshold must match _WORLDSPACE_VERT_THRESHOLD so that
1497:        if _skin_centroid_mag > _WORLDSPACE_VERT_THRESHOLD:
1507:        if _centroid_mag > _WORLDSPACE_VERT_THRESHOLD:
3593:    _WORLDSPACE_THRESHOLD    = 1.5   # Must match _WORLDSPACE_VERT_THRESHOLD in _build_vbo_data

--- FIX-PROXY-THRESHOLD ---
1454:    # FIX-PROXY-THRESHOLD: Lowered from 2.0 to 1.5 to catch c_bantha 'head_Hair'

--- FIX-UVSENT ---
70:                FIX-UVSENT-V2: two-tier sentinel — character models use 20.0 (heals
1371:    # FIX-UVSENT-V2: Two-tier UV sentinel restored for correct seam healing.

--- FIX-DEFORM ---
46:  FIX-DEFORM:   Deformation-helper mesh nodes (bone proxies with _g suffix, no UVs,
2614:            # ── FIX-DEFORM: Deformation-helper detection ──────────────────
2615:            # FIX-DEFORM: Self-contained deformation-helper filter (no viewport import).

--- shader V-flip 1.0 - in_uv.y ---
32:  BUG-UV:   UV V-axis flipped  → v_uv.y = 1.0 - in_uv.y  in vertex shader
683:    vec2 flipped_uv = vec2(in_uv.x, 1.0 - in_uv.y);

--- Phase 17 in model_data ---
1015:        Phase 17: All KotOR MDL vertices (skin AND non-skin) are stored in
1118:            Phase 17: ALL nodes (skin + non-skin) use full world transform.

--- Strategy B in model_data ---
1172:            # Strategy B: if all non-skin nodes are tiny (face pieces ≤50 verts),

--- vertex_space / compute_vertex_space / VertexSpace in core files ---
(no matches)

--- D20-M in ROADMAP ---
(no matches)

--- Last line of ROADMAP ---
### Next Recommended Task
- **D13:** PMHA01/PFHA01 player model validation
- **D14:** Automated regression test suite
- **D15:** K2 area/module model validation
```

## Diagnosis

D20-M was **never landed on main**. The previous session created files on a
force-pushed PR branch (genspark_ai_developer) but that branch was squash-pushed
over the existing PR #46 content without merging. The main branch still contains:

1. `_WORLDSPACE_VERT_THRESHOLD = 1.5` — centroid-magnitude heuristic
2. FIX-PROXY-THRESHOLD — lowered threshold hack
3. FIX-UVSENT-V2 — UV sentinel (legitimate for UV, but conflated with transform)
4. FIX-DEFORM — deformation helper filter (partially legitimate)
5. Shader V-flip `1.0 - in_uv.y` — UV axis flip in vertex shader
6. Phase 17 unconditional `world_transform()` in compute_bounds()
7. Strategy B outlier exclusion in render_bounds()
8. **ZERO** references to vertex_space, VertexSpace, or compute_vertex_space
9. **ZERO** D20-M entries in ROADMAP_EXECUTION.md
10. src/core/vertex_space.py does **NOT EXIST**

The prior "D20-M complete" claim was false in practice. Starting from scratch.
