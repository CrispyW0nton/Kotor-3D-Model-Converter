# Mesh Processing Skill

Use this skill for mesh data structures, vertex/face/edge topology, mesh
processing algorithms (smoothing, subdivision, simplification, decimation,
remeshing), normal/tangent computation, UV parameterization, and the imported-
mesh cleanup pass that runs in GhostRigger's Character Studio before binding.

## Book Grounding

- `3D Mesh Processing and Character Animation` (Mukundan): mesh representation,
  OBJ/OFF/PLY formats, polygonal manifolds and Euler-Poincaré topology,
  face/winged-edge/half-edge (DCEL) data structures, adjacency queries, surface
  normal computation, bounding-box normalisation, mesh simplification (planarity
  metric, quadric error metric, vertex decimation, edge collapse), subdivision
  masks, and mesh parameterization/morphing.
- `Technical Animation in Video Games` (Lake): mesh topology **for deformation**,
  the polygon/NGon/triangle-count distinction, automated triangulation hazards,
  and the four reasons topology exists (silhouette, deformation, materials/
  textures, vertex colour).

Load `learned/meshskill.md` and `learned/vertexskill.md` for the standing
mesh/vertex contracts.

## Mesh Representation

A polygonal mesh is a **vertex list** (3D coordinates) plus a **face list**
(integer indices into the vertex list). Two facts that drive every GhostRigger
mesh-node read/write:

- **Winding encodes the front face.** An anticlockwise vertex ordering (viewed
  from the outward normal) is the conventional front. This is the AGENTS.md
  contract "validate face winding". A flipped winding is a flipped normal, which
  flips lighting and backface culling. MDL mesh-node face indices carry this
  orientation; never re-emit faces in arbitrary order.
- **Everything becomes triangles at runtime.** A quad is two triangles; an NGon
  is N-2 triangles. Automated triangulation of a concave/convex quad can split
  the diagonal either way, producing two different surfaces. On deforming
  meshes this is especially costly. Measure **triangle count**, not polygon
  count, for any performance budget.

A triangle mesh can be stored compactly as an **indexed list** or a **triangle
strip** (each new index + previous two = next triangle). When multiple strips
share one index array, a primitive-restart index (e.g. `65535`) separates them.
KOTOR MDL stores its own per-mesh-node vertex/index layout; the
`src/mesh_tools/` layer must preserve index order and winding across edits.

### Topology-for-deformation audit (pre-bind cleanup)

Before Character Studio binds an imported FBX/OBJ/glTF mesh (T2503), audit it
against the AGENTS.md "Treat mesh edits as topology contracts" rule. Topology
exists for only four reasons: **silhouette, deformation, materials/textures,
vertex colour**. If a vertex/edge/triangle contributes to none of these, it is
dead weight and a source of skinning artefacts. The audit must check:

- **Face winding** (consistent anticlockwise front), **normals**, **open/border
  edges** (unintended holes), **duplicate/overlapping faces**, **isolated
  vertices**, **T-vertices**, **missing UVs**, **flipped UV faces**, and
  **degenerate triangles** (zero-area). These are the literal AGENTS.md mesh
  contracts.
- NGons (>4 sides) and concave quads — triangulate deliberately, not
  automatically, so the split diagonal matches the artist's intent.
- Supporting edge loops / kite topology at joints — deformation topology that
  preserves volume when a joint bends. A mesh with no support loops will
  collapse at elbows/knees regardless of weights.

## Topology: Manifolds, Valence, Euler

Most mesh algorithms assume a **polygonal manifold**: (i) no edge is shared by
more than two faces, and (ii) the faces around a vertex form a single open or
closed chain. Non-manifold geometry (3+ faces on an edge, or split vertex
chains) breaks local edits, simplification, and skinning.

- **Border/boundary edge** = belongs to one face. **Interior edge** = belongs to
  exactly two faces. A closed manifold with no border edges is a polyhedron.
- **Interior vertex** = closed triangle fan around it; **boundary vertex** =
  open fan. This distinction is exactly the open-edge check in AGENTS.md.
- **One-ring / two-ring neighbourhood** of a vertex — the foundation of weight
  smoothing, normal averaging, and curvature estimation.
- **Valence** = number of incident edges. For a large closed triangle mesh the
  average valence is **6**, with `F ≈ 2V` and `E ≈ 3V` (Euler-Poincaré:
  `V + F − E = 2(1−g)` where `g` is genus/handles). Use these invariants as
  cheap integrity assertions after any edit: a simplification or remesh must
  preserve the Euler characteristic unless topology was intentionally changed.
- **Orientable / compatible**: adjacent faces are compatible if they share the
  same orientation. A mesh is orientable if every adjacent pair is compatible —
  the topological statement of "consistent winding".

## Mesh Data Structures

A flat vertex/face list has no neighbourhood info. GhostRigger's mesh tools that
do local edits (merge, split, weight smoothing, normal recompute) need a
connectivity structure. The canonical choices:

- **Face-based** (triangles only): each triangle stores its 3 vertex pointers +
  3 neighbour-triangle pointers. Cheap to build from a face list; gives O(1)
  one-ring traversal; **cannot** do edge collapse/flip cleanly (no edge data).
- **Winged-edge**: edge stores start/end verts, left/right faces, and the
  prev/next edge on each face. Powerful but **direction-ambiguous** — every edge
  op must resolve "which way does this edge point" with an if/else.
- **Half-edge (DCEL)**: split every edge into two directed half-edges, each
  belonging to one face (the face on its left). A half-edge stores: the vertex
  it points to, its face, its `next`/`prev` on the same face, and its `pair`
  (opposite half-edge on the adjacent face). No direction ambiguity, constant-
  time neighbourhood traversal. This is what production mesh libraries
  (OpenMesh) use.

The half-edge gives nine adjacency queries for free — `V:-V` (one-ring),
`V:-E`, `V:-F`, `E:-V`, `E:-E`, `E:-F`, `F:-V`, `F:-E`, `F:-F` — via iterators
(whole-mesh) and circulators (neighbourhood). Use them for: duplicate-vertex
detection (`V:-V`), open-edge finding (`E:-F` where one side has no face),
normal averaging (`V:-F`), and edge-length/dihedral computation (`E:-E`).

> KOTOR MDL is not stored as a half-edge mesh, but GhostRigger's `src/mesh_tools/`
> should build a transient half-edge/DCEL view over an imported mesh-node when
> running cleanup, validation, or weight smoothing, then write the corrected
> vertex/face arrays back. Never mutate the MDL arrays in place without the
> adjacency view — that is how T-vertices and split normals appear.

## Normals And Tangents

- **Face normal** = cross product of two edge vectors of the triangle
  (`n = p × q`), normalised. Flat shading = one normal per face; produces
  visible facet boundaries.
- **Vertex normal** = normalised sum of the face normals of all faces sharing
  the vertex (`V:-F` query). Use **area-weighted** face normals for a smoother,
  more accurate result: `n_avg = Σ(Aᵢ·nᵢ) / ΣAᵢ`. Per-vertex normals give smooth
  (Gouraud/Phong) shading.
- **Normals transform differently from points.** Under non-uniform scale a point
  uses the matrix `M`; a normal uses `M^{-T}` (inverse-transpose). AGENTS.md is
  explicit: "Normals usually need separate handling under non-uniform scale."
  MDL mesh nodes carry per-vertex normals; any transform applied at import or
  fit (including the `x, z, -y` axis conversion) must re-derive normals via
  `M^{-T}`, never by transforming them as points.
- **Crease / silhouette edges** come from the **dihedral angle** between
  adjacent faces: `angle = cos⁻¹(n₁·n₂)`. Edges above a threshold (e.g.
  `n₁·n₂ < 0.5` ⇒ >60°) are crease edges; an edge between a front-facing and a
  back-facing triangle (`n·v` sign change) is a silhouette edge. These are the
  basis for hard-edge / smoothing-group decisions and for the triangle-adjacency
  primitive used in shader-based edge detection.

## Bounding Box And Normalisation

Compute the axis-aligned bounding box with running min/max per axis; centroid =
midpoint; `modelScale = 1 / max(half-extent)`. Use this to centre/scale an
imported mesh to KOTOR object space before fit-to-node (T2503). Centring at the
mesh level is also the cheap sanity check that an imported model landed in the
right place relative to its target Odyssey node — a wildly off-centroid mesh
usually means a coordinate-space or axis-conversion bug.

## Mesh Processing Algorithms

### Simplification (LOD, decimation)

Simplification reduces triangle count while preserving shape and **topology**
(same Euler characteristic). It uses a **cost function** to pick what to remove:

- **Planarity metric**: distance `d` of a vertex from the area-weighted average
  plane of its one-ring fan, normalised by the largest incident edge length
  (`d / lₑ`) so it is scale-invariant in `[0,1]`. Low values ⇒ nearly flat ⇒
  safe to decimate.
- **Quadric error metric (QEM)**: `QEM(p;v) = Σ (Aᵢᵀ·p)²` summed over the
  vertex's triangles — sum of squared distances of candidate point `p` to each
  incident triangle plane. Precompute the `4×4` quadric per vertex; edge-collapse
  cost = `QEM(p;v) + QEM(p;w)`.
- **Edge cost**: dihedral angle + edge length — `k₁·cos⁻¹(n₁·n₂) + k₂·|e|`,
  optionally normalised to `[0,1]`.

**Vertex decimation** removes a vertex and its incident edges, leaving a hole
that is re-triangulated across the one-ring. **Edge collapse** moves an edge's
two endpoints to a common point (often the QEM-optimal position) and welds them.
After any collapse, update the half-edge connectivity and re-validate winding.

### Subdivision (smoothing / densifying)

Subdivision refines a mesh toward a smooth limit surface. **Approximation**
masks (e.g. Catmull-Clark / Loop-family) move existing points as a weighted
average of neighbours (existing point: `(1/8, 6/8, 1/8)` over the point and its
two edge-neighbours; new edge point: `1/2, 1/2`) and **insert** new points — the
surface stays near but inside the control cage. **Interpolation** masks pass
through control points but can overshoot, so negative weights are used to keep
the curve smooth. Use subdivision only when the target LOD genuinely needs more
density; on a skinned character it changes weight neighbourhoods, so re-bake
ROM after subdividing.

### UV parameterization

UV mapping is a 2D embedding of the 3D surface. The half-edge structure's
boundary loop defines the UV seam; AGENTS.md's "missing UVs / flipped UV faces"
checks are boundary/seam-integrity checks. UVs live in UV space (a distinct
transform space — AGENTS.md: "name the space before transforming:
object/bind/pose/parent/world/camera/screen/**UV**"). Imported UVs must survive
every transform untouched; only the sampling material/sampler policy changes.

## Per-Vertex Math: Name The Space

AGENTS.md requires naming the transform space before any per-vertex operation:
object, bind, pose, parent, world, camera, screen, or UV. Concretely for an
imported→bound→animated mesh in Character Studio:

- Imported mesh vertices arrive in **object space** (post `x, z, -y` correction).
- The **bind** step expresses each vertex in **bone/joint space** via the offset
  matrix `F` (see `learned/technicalanimationskill.md`).
- Each frame, the runtime multiplies the **pose** hierarchy product `L_k` by
  `F_k` to get the skinning matrix `J_k`, then applies LBS in **world** space.
- Normals/tangents use `J_k^{-T}`, never `J_k`.

Mixing these spaces is the single most common source of "the mesh exploded /
slid off the bone" bugs.

## GhostRigger Checks

- Run the full topology audit (winding, open edges, duplicates, isolated verts,
  T-vertices, missing/flipped UVs, degenerate tris) on every imported mesh
  before bind — this is the literal AGENTS.md mesh contract and the precondition
  for T2503.
- Preserve **stable object/subobject IDs** and index order across edits; the
  MDL mesh-node format and scene contracts depend on them.
- Build a transient half-edge/DCEL view for any adjacency-based operation
  (cleanup, smoothing, normal recompute) and write corrected arrays back; never
  hand-edit index arrays without the connectivity view.
- Re-derive normals/tangents via inverse-transpose after any non-uniform
  transform or axis conversion (`x, z, -y`).
- Assert Euler-characteristic invariants after simplification/remesh to catch
  accidental topology changes.
- Validate generated topology from extrude/bevel/inset/bridge defines material,
  UV, normal/tangent, selection, and skin-weight behaviour (AGENTS.md).
- Load `learned/meshskill.md`, `learned/vertexskill.md`, and
  `learned/technicalanimationskill.md` together for Character Studio mesh cases.

## Failure Patterns

- Lighting banding / faceted look on a smooth surface: per-face normals where
  per-vertex (area-weighted) normals are needed, or normals not re-derived as
  `M^{-T}` after a scale.
- Imported mesh "explodes" off the bones: space confusion (object vs bind vs
  pose) or normals/points transformed with the wrong matrix.
- Holes/tears after a merge or weight transfer: open/border edges introduced by
  an edit that did not consult the half-edge connectivity, or T-vertices left by
  a partial weld.
- Triangulation surprises (flipped diagonal, changed silhouette): let
  automated triangulation run on a concave quad/NGon — triangulate deliberately.
- Duplicate/overlapping faces causing z-fighting or doubled normals: failed the
  duplicate-face check in the pre-bind audit.
- Skin weights smear oddly after a topology change: subdivision/decimation
  altered one-ring neighbourhoods without re-baking ROM.
