# Algorithm And Computational Geometry Skill

Use this skill for algorithm choice, geometric robustness, graph/search work,
runtime scheduling, selection/picking math, spatial queries, triangulation, and
validation algorithms.

## Book Grounding

- `Algorithm_Design_-_Kleinberg.pdf`: asymptotic analysis, graphs, BFS/DFS,
  greedy algorithms, shortest paths, union-find, divide-and-conquer, dynamic
  programming, network flow, NP-completeness, approximation, and randomized
  algorithms.
- `Computational_Geometry_-_Mark_de_Berg.pdf`: degeneracy handling, sweep-line
  segment intersection, polygon overlays, half-plane intersection, point
  location, Voronoi/Delaunay structures, arrangements/duality, convex hulls, and
  geometric data structures.
- `Math_for_Programming_Early_Access_-_Ronald_T_Kneusel.pdf`: floating-point
  representation, boolean algebra, sets, relations, functions, graphs, and
  programming-oriented mathematical reasoning.

## Workflow

1. State the problem shape before picking an algorithm: graph traversal,
   shortest path, scheduling, matching, flow, dynamic programming, geometric
   query, triangulation, or search.
2. Define input size and hot path. A linear scan can be correct for small tool
   panels; spatial indexes matter for per-frame viewport and picking work.
3. Make degeneracies explicit: equal coordinates, collinear points, coincident
   edges, zero-area faces, duplicate vertices, empty intersections, unbounded
   regions, and floating-point epsilon rules.
4. Prefer robust predicates and normalized representations over large piles of
   special-case branches.
5. Separate preprocessing from query time. Point-location, interval/segment
   trees, adjacency maps, and cached graph structures are useful only when the
   query workload justifies them.
6. For graph logic, record directionality, connectivity assumptions, cycles,
   topological constraints, and whether weights can be negative.
7. For optimization problems, name the proof style or risk: greedy exchange,
   dynamic-programming recurrence, flow reduction, heuristic, approximation, or
   brute-force fallback.

## GhostRigger Applications

- Selection and picking: ray/triangle tests, point-in-polygon, nearest feature,
  bounding volume rejection, and degenerate triangle handling.
- Mesh tools: edge adjacency, connected components, boundary loops, T-vertices,
  triangulation, overlays, and topology repair.
- Walkmesh/module tools: polygon intersection, point location, region labeling,
  Delaunay/triangulation-aware height interpolation, and path graph validation.
- Resource workflows: dependency graphs, topological ordering, cache invalidation
  propagation, and cycle detection.
- Sequence/timeline tools: interval scheduling, overlap detection, clip range
  queries, and dynamic programming only when simpler interval logic is not
  enough.

## Validation

- Test edge cases before performance cases.
- Include at least one degenerate input in targeted tests.
- Use small hand-checkable fixtures for geometry algorithms.
- Compare optimized implementations against a simple reference implementation
  when feasible.
