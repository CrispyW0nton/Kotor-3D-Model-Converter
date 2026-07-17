# KOTOR WOK/BWM Vanilla Contract

Use this note when reading, preserving, validating, repairing, or generating a
KOTOR room walkmesh (`.wok`). It records the empirical contract established by
an exhaustive census of the vanilla KOTOR 1 and KOTOR 2 game libraries. It is
not a substitute for a retail-game movement test, but it is the structural
baseline Map Studio must meet before an exported module is offered for one.

This note deliberately separates two policies:

- **Imported-vanilla fidelity:** preserve odd but known-loadable data exactly
  enough to round-trip it without inventing a new interpretation.
- **New authoring safety:** generate a smaller, stricter subset: no degenerate
  triangles or ambiguous non-manifold edges, complete adjacency and perimeter
  records, a complete AABB tree, and explicit authored surface intent.

Do not “clean” imported vanilla data merely because the stricter authoring
policy would reject it. Conversely, do not use a vanilla anomaly as permission
to emit malformed new WOKs.

## Ownership and Proof Boundary

- Pure BWM structures belong to Formats; reading and writing belong to IO.
- Authored walkmesh state and source-room fidelity belong to Scene.
- Generation and multi-step repair belong to Workflow/Systems.
- Structural, semantic, module-entry, and export gates belong to Validation.
- Map Studio presents overlays and repair choices; it must not own the topology
  algorithm in its window or viewport code.

The proof ladder is:

1. raw bytes, offsets, counts, and record extents are valid;
2. an independent reader parses the WOK;
3. indexed topology, adjacency, boundary loops, transitions, and AABB coverage
   agree with the raw bytes;
4. write/readback preserves those facts and all header vectors;
5. the room WOK, LYT offset, embedded room-MDL AABB node, IFO entry point, PTH,
   and module resources form one coherent module;
6. the candidate is compared structurally with appropriate vanilla WOKs;
7. the module is manually loaded and traversed in the correct retail game.

Only step 7 proves that a player can actually move through the result. PyKotor
or Ghost Studio parser acceptance is not retail-engine proof.

## Census Scope and Headline Results

The July 2026 census inspected every WOK exposed by the two vanilla Steam game
libraries, using both raw-table inspection and PyKotor parsing.

| Fact | KOTOR 1 | KOTOR 2 |
|---|---:|---:|
| WOK resources | 1,202 | 1,236 |
| Raw/table failures | 0 | 0 |
| PyKotor parse failures | 0 | 0 |
| Empty WOKs | 222 | 36 |
| Non-empty WOKs | 980 | 1,200 |
| Non-walk-only WOKs | 11 | 60 |
| Vertices | 114,851 | 103,593 |
| Faces | 189,588 | 152,792 |
| Recognized walkable faces | 95,612 | 58,544 |
| Recognized non-walkable faces | 93,976 | 94,248 |
| Adjacency rows | 95,612 | 58,682 |
| Serialized boundary-edge rows | 39,366 | 43,250 |
| Closed perimeter loops | 1,789 | 1,967 |
| Transition-edge records | 3,926 | 2,508 |

K2's 1,236 resources all reported BWM `V1.0`, type `1`. K1's 222 empty
resources were the intentional 136-byte visual-WOK form, not truncated files.
An empty or non-walk-only WOK is therefore not automatically corrupt.

The counts are a baseline for the scanned installations, not magic constants
that a validator should hardcode. A modded installation or another retail
distribution may expose a different inventory. The per-resource structural
rules below are the reusable contract.

## Header Vectors Are Serialized State

A WOK/BWM header carries five vectors:

- `relative_hook1`;
- `relative_hook2`;
- `absolute_hook1`;
- `absolute_hook2`;
- `position`.

Preserve all five. They are not disposable parser conveniences. In K1 alone,
973 WOKs have a non-zero `position`; a reader/writer that resets it changes
nearly the entire library. Earlier PyKotor-based round trips that constructed a
new BWM without copying the vectors silently zeroed them.

Room placement and the WOK header must also be interpreted in the correct
coordinate space. A generator must say whether its vertices are room-local or
module/world coordinates and must not apply a LYT translation twice. Header
preservation and LYT placement are separate responsibilities.

## Face Ordering and the Adjacency Domain

The adjacency table has one three-slot row for each face in the serialized
**adjacency domain**. Each non-negative slot identifies the matching edge of
the neighboring face as:

```text
neighbor_reference = neighbor_face_index * 3 + neighbor_edge_index
```

For K1, every non-empty WOK places the recognized walkable faces first and has:

```text
adjacency_count == recognized_walkable_face_count
```

Do not generalize this into “derive adjacency count from the surface material.”
K2 has a decisive vanilla exception:

- `104pera` has 138 adjacency rows;
- its first 138 faces use surface 16 (`BOTTOMLESS_PIT`);
- those are followed by 247 `NON_WALK` faces;
- none of the first 138 is counted by the normal recognized-walkable material
  set, yet they are the serialized adjacency domain.

This single room explains K2's total difference of 138 between 58,682 adjacency
rows and 58,544 recognized walkable faces. The reader must trust the explicit
adjacency count and face order. The writer must persist an explicit adjacency
domain; it must never reconstruct that domain solely from material names.

For newly authored ordinary floor WOKs, ordering walkable faces first and using
those faces as the adjacency domain is the safest vanilla-shaped policy. Keep
the domain explicit in the authored model so a future special surface does not
need to be guessed from an enum.

## Vertex Indices, Not Coordinates, Define Topology

All topology reconstruction must use the face's raw vertex indices. Two
vertices with equal coordinates but different indices may be an intentional
topological seam. Coordinate welding, rounded-coordinate edge keys, or
`Vector3` value equality can connect faces that vanilla deliberately keeps
separate.

Full-census evidence:

- K1 contains duplicate-coordinate, distinct-index seams that are real
  cross-face boundaries. Representative rooms include `m02ae_12a`,
  `m21aa_07a`, and `m41ac_09a`.
- K2 coordinate welding would erase 219 intentional seams across 20 WOKs.
  Representative rooms include `000trl`, `001ebo9`, `203tell`, `304nar_13`,
  `305nar_67`, `650dan_02`, and `902malf`.
- Raw-index topology reproduces all 43,250 K2 serialized boundary rows.
- Raw-index topology matches 176,042 of 176,046 K2 adjacency slots. The four
  remaining slots belong to the one ambiguous four-owner edge in `403dxne`.

For a triangle `(v0, v1, v2)`, retain three directed local edges in serialized
order. Build an undirected ownership key from the two integer vertex indices,
but retain each owner's face index, local edge index, and direction. Then:

- one owner means boundary;
- two owners mean a manifold adjacency candidate;
- more than two owners mean an ambiguous non-manifold edge.

Do not merge index identities before this analysis. Rendering may deduplicate
or split vertices in a separate cache, but the WOK topology layer must retain
the serialized identities.

## Vanilla Adjacency Anomalies

K1 raw-index adjacency has only two mismatching slots in the full library. Both
come from a degenerate self-edge in `m38aa_11`. K1 also has one edge with more
than two owners: edge `(6, 7)` in `m38aa_03` has four owning faces.

K2 has one corresponding non-manifold exception: `403dxne`, edge `(264, 270)`,
has four owners. It accounts for all four K2 adjacency mismatches and two
non-reciprocal references.

Policy:

- An imported vanilla WOK may preserve these known anomalies and report them as
  fidelity warnings with the resource identity.
- A newly generated WOK must reject a repeated-index/zero-area face and any
  edge with more than two owners. There is no unambiguous adjacency to invent.
- Do not “repair” a four-owner edge by picking an arbitrary neighbor. Split the
  authored topology or require the modder to resolve the overlap.
- Validate non-negative adjacency references for range, exact shared raw-index
  edge, and reciprocity. Aggregate failures rather than flooding the UI with
  one row per slot.

## Boundary Edges, Perimeter Loops, Holes, and Islands

The external `.wok` needs serialized boundary-edge and perimeter-loop records.
Reconstructing faces and adjacency is insufficient. A writer path that drops
the loop records can produce a file that its own parser accepts but that does
not define the walkable region correctly for the game.

Full-census evidence:

| Boundary fact | KOTOR 1 | KOTOR 2 |
|---|---:|---:|
| Geometric boundary edges | 39,364 | 43,250 |
| Serialized edge rows | 39,366 | 43,250 |
| Closed loops | 1,789 | 1,967 |
| Multi-loop WOKs | 253 | 256 |
| Multi-component WOKs | 87 | 77 |

K1's two extra serialized rows are associated with its degenerate-edge
anomalies; they are another reason not to “correct” imported retail data by
coordinate-derived regeneration.

Multiple loops are normal. They can represent:

- a hole or blocked cutout inside a floor;
- disconnected walkable islands in one room;
- separate boundary components created by room construction;
- a pinched or vertex-touching boundary where loop identity is not recoverable
  from a simple unique-next-vertex map.

K2 has 215 WOKs with hole-like extra loops and 610 hole loops in total. It also
has 40 pinched boundary vertices; `510ondf` and `650dan_02` are representative
exceptions. K1 has a vertex-touch exception in `m23ab_01a`.

Generation rules:

1. Start with directed boundary half-edges from the explicit adjacency domain.
2. Consume each serialized/topological boundary half-edge exactly once.
3. Trace all closed cycles; do not stop after the first outer boundary.
4. Keep separate connected components and nested loops.
5. At a vertex with multiple possible outgoing half-edges, use face-local
   topology and a deterministic angular/half-edge continuation rule. A map from
   vertex to one next vertex is insufficient for pinched boundaries.
6. Do not assume all outer loops or all hole loops have one fixed winding. The
   vanilla libraries contain mixed loop winding.
7. Preserve transition metadata on the exact boundary edge identity.
8. Re-read the emitted WOK and verify that every boundary edge is represented,
   every loop closes, and no half-edge is consumed twice or omitted.

## Transitions Are Edge Records, Not Surface 18

K1 has 3,926 transition-edge records and zero faces using surface 18. K2 has
2,508 transition-edge records. Therefore a validator or generator must not
require a face with material/surface 18 merely because a room has transitions.

Keep transition intent attached to boundary edges and room/link metadata.
Surface painting, WOK edge linkage, LYT room placement, VIS adjacency, doors or
triggers, and actual in-game traversal are separate claims that must all be
validated.

## AABB Tree Contract

For an ordinary non-empty WOK, the vanilla-shaped AABB is a rooted binary tree
with:

```text
leaf_count = face_count
node_count = 2 * face_count - 1
root_index = 0
```

Every node is reachable from root 0. Every face appears in exactly one leaf.
Internal child indices are valid, bounds are finite and ordered, and a leaf
references a valid face. The serialized `unknown` field observed across the
vanilla data is `4`. Observed split-plane values are `0`, `1`, `2`, `4`, `8`,
`16`, and `32`; do not emit an invented `3` for a Z split merely because a
library enum numbers axes consecutively.

Evidence:

- K2: all 1,200 non-empty WOKs have a complete `2F-1` tree, one reachable leaf
  per face.
- K1: 979 of 980 non-empty WOKs have the complete tree.
- The exact K1 exception is `m02af_01a`: 140 faces, 219 AABB nodes, 110 leaves,
  and 30 omitted faces. Every omitted face is `NON_WALK`.

Treat `m02af_01a` as a named imported-vanilla fidelity exception, not a template
for new output. A newly generated WOK must cover every face and use `2F-1`
nodes.

The builder must have a deterministic fallback when all candidate face centers
are equal on the chosen axis. Earlier value-based tree construction lost a
same-center face while round-tripping K1 `m36aa_01` and changed its AABB from
4,185 to 4,183 nodes. Median-split by stable face order, or another guaranteed
non-empty partition, must be used so recursion cannot silently discard a face.

Do not confuse this external-WOK acceleration structure with the embedded AABB
walkmesh node required in a playable room MDL. Export validation must check
both resources.

## Surfaces and Walkability

K1's observed face distribution is:

| Surface | Walkable faces | Non-walkable faces |
|---|---:|---:|
| 1 `DIRT` | 57,142 | 0 |
| 2 `OBSCURING` | 0 | 15,869 |
| 3 `GRASS` | 12,143 | 0 |
| 4 `STONE` | 6,501 | 0 |
| 5 `WOOD` | 882 | 0 |
| 6 `WATER` | 47 | 0 |
| 7 `NON_WALK` | 0 | 74,009 |
| 8 `TRANSPARENT` | 0 | 103 |
| 9 `CARPET` | 20 | 0 |
| 10 `METAL` | 18,534 | 0 |
| 11 `PUDDLES` | 16 | 0 |
| 13 `MUD` | 327 | 0 |
| 17 `DEEP_WATER` | 0 | 29 |
| 19 `NON_WALK_GRASS` | 0 | 3,966 |

These values also expose a naming hazard: surface 19 is
`NON_WALK_GRASS`, not `SNOW`. Do not let a UI label redefine the binary
semantics. Unknown or game-specific surface values must round-trip numerically
even when Ghost Studio lacks a friendly name.

The K2 `104pera` exception demonstrates that material and adjacency-domain
membership are distinct. Preserve both. For new authored geometry, surface
intent should be explicit per face; do not infer it only from render texture,
normal, height, or visibility.

## Empty and Non-Walk-Only WOKs

Visual-only room content is a first-class vanilla pattern:

- K1: 222 intentional 136-byte empty WOKs and 11 non-walk-only WOKs.
- K2: 36 empty WOKs and 60 non-walk-only WOKs.

The 11 K1 non-walk-only resources are:

```text
m08aa_10d
m17aa_18
m17aa_20w
m17aa_21w
m17aa_22
m17aa_23
m17aa_31w
m17ab_00b
m17ac_00b
m17ad_00b
m40aa_42a
```

Classify a room with module context, not WOK face count alone:

- `playable`: expected to contain traversable floor and participate in entry,
  PTH, transitions, or gameplay placement;
- `collision/non-walk`: intentionally supplies blocking/non-walk surfaces;
- `visual-only/backdrop`: art that does not define playable space;
- `missing/invalid`: a room expected to be playable but lacking coherent WOK
  data.

An empty sky/backdrop WOK may be valid. An empty WOK for the module's only
player-start room is a blocker. The classification must be evidence-backed and
persisted; filename suffixes alone are insufficient because some apparent
backdrop rooms also contain ordinary or walkable geometry.

## Slopes, Vertical Faces, and Degenerate Geometry

A 45-degree maximum walkable slope is a useful Map Studio authoring default,
not a universal vanilla validity rule. K2 contains:

- 776 recognized walkable faces steeper than 45 degrees;
- 334 recognized walkable faces that are effectively vertical;
- 50 recognized walkable faces with negative-facing normals.

Imported vanilla data may encode ramps, unusual winding, helper collision, or
engine-era artifacts that cannot be safely reclassified from the normal alone.
Preserve its surface type and topology. For newly generated terrain, apply the
authoring slope threshold consistently, expose it to the modder, and require an
explicit override for steep walkable faces.

Degenerate faces are also present in retail data:

- K1: 112 degenerate faces across 45 WOKs;
- K2: 106 zero-area faces.

Imported vanilla fidelity may retain and warn about them. New generation must
reject zero-area triangles, repeated vertex indices, non-finite vertices,
zero-length edges, and ambiguous non-manifold ownership. A retail anomaly is
not a safe authoring primitive.

K2's largest observed WOK, `701kore`, has 2,136 faces. This is useful as an
empirical performance fixture, not a proven engine maximum.

## Generator Contract for New WOKs

For a new or genuinely regenerated room walkmesh, use this sequence:

1. **Choose the source of truth.** Prefer authored walkability or a surviving
   source WOK. Render geometry alone cannot distinguish floor from tabletop,
   roof, ceiling, decoration, water, or visual backdrop.
2. **Name the coordinate space.** Compile room-local vertices and persist the
   intended header/LYT transform without applying it twice.
3. **Triangulate deterministically.** Preserve stable face and vertex IDs where
   possible; never use render-cache vertex welding as topology.
4. **Validate inputs.** Reject non-finite data, repeated indices, zero-area
   faces, zero-length edges, and edges with more than two owners.
5. **Assign explicit surface intent.** Use authored material/walkability data;
   slope is a default/diagnostic, not the sole classifier.
6. **Persist an explicit adjacency domain.** For ordinary authored floors,
   place walkable faces first and record their count. Do not later reconstruct
   this from material enums.
7. **Build raw-index adjacency.** Match exact undirected index pairs; encode the
   neighbor face and local edge; validate reciprocity.
8. **Trace every boundary loop.** Preserve islands, holes, pinches, and exact
   transition-edge identities. Do not assume one loop or one winding.
9. **Build the complete AABB.** Emit one leaf per face and `2F-1` reachable
   nodes with a deterministic equal-centroid fallback.
10. **Preserve header vectors.** New data may initialize them deliberately;
    conversion and regeneration paths must not erase surviving values.
11. **Serialize, re-read, and compare.** Confirm counts, vertex indices,
    adjacency, boundaries, loops, transitions, AABB coverage, header vectors,
    and surface values through an independent readback.
12. **Validate in module context.** Confirm LYT room coverage, embedded room-MDL
    AABB presence, IFO entry containment, PTH reachability, door/trigger links,
    and the absence of a walkable-ceiling enclosure.
13. **Queue retail proof.** Manually warp, spawn, click-to-move across every
    component/ramp/transition, test camera containment and doors, then save and
    reload while capturing the game log.

For imported rooms with a surviving WOK, source-seeded repair is safer than
wholesale generation from rendered triangles. Preserve the known floor and
fill only deliberately connected uncovered floor regions. Never automatically
classify every uncovered upward-facing surface as walkable.

For an imported room with **no** surviving WOK, generation must first persist a
versioned, reviewed surface/face allowlist plus a written reason. Normal and
slope checks are still required after that selection, but they are not
authoring intent: a roof, table, ledge, or platform can have the same upward
normal as the player floor. Stale surface or face indices block generation.

Do not assume every LYT visual partition owns an external WOK. The recovered
`505QGM` source is a concrete counterexample: `505QGM_01a`'s embedded AABB and
external WOK have identical 368-vertex/366-face indexed topology (maximum
per-index vertex delta about `0.0000041`), and that centralized collision mesh
overlaps the floor surfaces in all eight surviving visual partitions placed at
the same LYT origin. Creating seven additional partition WOKs would duplicate
collision. Calibrate partition ownership against the complete source layout,
embedded AABB, and render floors before treating a missing same-resref WOK as a
generation target.

The external WOK should contain the walkable floor and intentional blocking
surfaces, not a ceiling/wall shell that encloses the player as `NON_WALK`.
Earlier K2 testing showed that an enclosing non-walk ceiling can freeze player
movement even when the file parses.

Likewise, an editor's visual boundary-wall helper must not append vertical
`NON_WALK` triangles to the external game WOK. Odyssey containment comes from
the floor perimeter; the helper may remain as preview metadata, but the
serialized WOK remains floor-only.

New terrain carving validates every hole cell, rejects non-manifold third-edge
owners, and rejects disconnected walkable islands by default. A persisted
`allow_disconnected_walkmesh_islands=true` is an explicit review waiver, not
permission to invent a bridge. Composition ramps and stairs must share exact
raw seam indices with a real floor boundary; coordinate coincidence alone is
not connectivity.

## Imported-Vanilla Fidelity Rules

When loading and re-exporting an existing module:

- preserve vertex indices and duplicate-coordinate seams;
- preserve face order, explicit adjacency count, and unknown surface values;
- preserve all adjacency slots unless a user-authorized repair is being made;
- preserve every boundary edge, loop, and transition record;
- preserve all five header vectors;
- preserve degenerate and non-manifold anomalies with warnings when they match
  the source bytes;
- preserve empty and non-walk-only visual WOKs as such;
- preserve a known incomplete AABB such as K1 `m02af_01a` when doing a fidelity
  round trip, while preventing it from becoming the template for a new WOK;
- record before/after structural fingerprints and any intentional divergence.

If the modder actually edits topology, the result becomes newly authored data
and must pass the stricter generator contract. The UI should make this boundary
clear: “preserved retail anomaly” and “new invalid topology” are not the same
readiness state.

## Required Structural Fingerprint

Every WOK audit or conversion manifest should record at least:

```text
game and resource identity
source/output hashes
header magic, version, type, and all five vectors
vertex and face counts
surface histogram
adjacency-domain count
adjacency mismatch and non-reciprocal counts
non-manifold edge count
geometric and serialized boundary-edge counts
perimeter-loop count, closure, components, and nested/hole candidates
transition-edge count and targets
AABB node/leaf/reachable/covered/missing-face counts
degenerate and non-finite face counts
slope histogram for adjacency-domain faces
classification: playable, collision-only, visual-only, or missing/invalid
LYT offset and entry-point containment result
proof level reached
```

Keep raw-index and coordinate-derived diagnostics separate. A coordinate view
can help find visually coincident seams, but it must never replace indexed
topology in the pass/fail contract.

## Regression Fixtures

Use focused fixtures for each contract rather than one “normal room”:

- ordinary K1/K2 WOK for baseline round trip;
- K1 `m36aa_01` for same-center AABB leaf retention;
- K1 `m02af_01a` for the named incomplete-AABB fidelity exception;
- K1 `m02ae_12a`, `m21aa_07a`, or `m41ac_09a` for indexed seams;
- K1 `m38aa_11` for degenerate self-edge preservation diagnostics;
- K1 `m38aa_03` for four-owner non-manifold diagnostics;
- K2 `000trl`, `001ebo9`, or `203tell` for indexed seams and header-preserving
  round trip;
- K2 `104pera` for explicit adjacency-domain handling;
- K2 `403dxne` for four-owner/non-reciprocal retail anomaly handling;
- K2 `510ondf` or `650dan_02` for pinched boundary tracing;
- K2 `701kore` for the largest observed vanilla face-count performance case;
- one empty visual WOK and one non-walk-only WOK for classification;
- an authored ring with a hole, two disconnected islands, a ramp, a transition,
  and duplicate-coordinate distinct-index seams for strict generation tests.

Passing these fixtures establishes structural coverage. It still does not
replace a manual retail-game traversal of each converted module.

## Claims to Avoid

Do not say:

- “valid because PyKotor parses it”;
- “two equal coordinates are the same WOK vertex”;
- “adjacency count always equals the number of known walkable materials”;
- “a WOK has only one perimeter”;
- “loop winding always identifies a hole”;
- “surface 18 is required for a transition”;
- “45 degrees is the retail engine's universal hard limit”;
- “an empty WOK is corrupt”;
- “all vanilla anomalies are acceptable in generated content”;
- “a structurally complete WOK works in game.”

The honest claim before manual proof is: **vanilla-structural candidate, with
the listed fidelity exceptions and module-context gates passed**.
