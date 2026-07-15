# Maya-to-Map-Studio modeling construction audit

Date: 2026-07-14
Owner: LordVaderCW
Roadmap: T2907
Method: clean-room public behavior plus Ghidra 12.1.2 symbol/string/xref relationships

## Boundary

This pass did not copy Autodesk source, decompiled algorithms, icons, or other
assets. Maya was treated as a behavioral oracle. Ghidra was used to recover
tool-context structure, command/attribute relationships, history and
manipulator lifecycles, and press/drag/release boundaries. The Ghost Studio
implementation is original Python over the existing KMAP and Map Studio
architecture.

The detailed reproducible evidence is retained under:

- `Saved/Audits/maya_modeling_parity_20260714/MAYA_PRIMITIVE_CONSTRUCTION_HISTORY_20260714.md`
- `Saved/Audits/maya_modeling_parity_20260714/MAYA_PRIMITIVE_HISTORY_XREFS_20260714.md`
- `Saved/Audits/maya_modeling_parity_20260714/MAYA_SHELF_32_TOOL_PARITY_MATRIX_20260714.md`
- `C:/Users/NewAdmin/Documents/GDeveloper/Workspaces/Ghidra/projects/active/maya-2025-modeling/exports/`

The eight deep shelf relation exports total approximately 6 MiB. Their
individual SHA-256 hashes are recorded in the parity matrix so the evidence can
be reproduced without treating a mutable Ghidra project as product source.

## Principal finding: a primitive is a retained recipe

Maya creates three durable identities for a polygon primitive:

1. an object transform;
2. an evaluated polygon shape;
3. a construction-history node containing typed creation inputs.

Changing width, height, radius, subdivisions, axis, caps, baseline, twist, or
UV policy dirties that node and re-evaluates the same selected object. It does
not replace the object or rebuild the whole scene. Freeze Transformations adds
a downstream transform stage and preserves the primitive node. Delete History
is the separate explicit graph-to-static-shape boundary.

Map Studio therefore now treats standard primitives as small, versioned KMAP
construction recipes with stable construction-node identities. Previewing a
field edit evaluates one immutable recipe and patches only the selected
resident mesh. Apply performs one KMAP serialization and creates one undo
record. Cancel/Escape restores the exact resident baseline.

Freeze Transformations now moves the current translation, Z rotation, scale,
and pivot into an ordered immutable evaluation-stage list and resets only the
editable transform channels. Render geometry and derived WOK apply the same
stages in order. Repeated freeze and KMAP reload preserve both visible geometry
and the original typed primitive recipe; they no longer replace a rotated or
nonuniform primitive with a generic combined-mesh recipe.

## Measured primitive topology oracles

The public Maya probes established deterministic logical polygon counts. These
are acceptance oracles, not copied implementation details.

| Primitive/probe | Vertices | Edges | Polygon faces |
| --- | ---: | ---: | ---: |
| Plane 4 x 3 | 20 | 31 | 12 |
| Cube 2 x 3 x 4 | 54 | 104 | 52 |
| Sphere 12 x 8 | 86 | 180 | 96 |
| Torus 16 x 8 | 128 | 256 | 128 |
| Cylinder axis 8, height 1, caps 0/1/2 | 16/18/34 | 24/40/72 | 10/24/40 |
| Cone axis 8, height 1, caps 0/1/2 | 9/10/18 | 16/24/40 | 9/16/24 |

Ghost Studio now has a connected shared-index polygon-cage evaluator for
plane, cube, cylinder, sphere, cone, and torus that matches those counts. The
logical cage carries stable vertex/face/corner provenance, per-corner normals,
UV0 policy, axis, height baseline, cap subdivisions, round-cap intent, and
torus twist. Odyssey export remains separately triangulated because MDL needs
independent UV and hard-normal corners.

## Construction inspector behavior

The Map Studio Builder exposes a dynamic **Primitive Construction History**
inspector instead of a fixed five-row dimension form. It supports floats,
integers, booleans, choices, and vector values; grouped topology, cap, axis,
anchor, and UV controls; hard constraints separate from soft UI ranges; Reset
Defaults; Apply; Cancel; and Escape.

The clean-room Maya defaults and constraints captured by the typed schema are:

- dimensions/radii: hard minimum `0.01`, soft maximum `100`;
- plane/cube subdivisions: hard minimum `1`;
- cylinder/cone axis subdivisions: hard minimum `3`, height `1`, caps `0`;
- sphere/torus subdivisions: hard minimum `3`;
- subdivision soft maximum: `50`, not a hard cap;
- height baseline: `[-1, 1]`;
- torus twist: `[0, 360]`;
- signed primitive axis: normalized atomically and never clamped by the UI's
  legacy positive-dimension range.

Maya's exposed UV modes round-trip in KMAP. `None` disables UV0. The current
KOTOR render/export evaluator intentionally shares one deterministic layout
between several nonzero normalization modes; the inspector states that
limitation instead of presenting those modes as fully equivalent.

## Shelf-wide result

All 32 commands from the user's Maya custom shelf have a Map Studio route and
a useful subset. Routing is not equivalence. The strict gate is frontmost
hover, interactive preview, complete options, exact cancel, one undo/redo,
history behavior, channel preservation, KMAP reload, practical frame time,
visible Debug-app proof, and KOTOR proof when export changes.

As of this audit, the truthful strict score remains **0/32 fully
Maya-equivalent**. Strong subsets include prepared face extrusion, single-edge
bevel, authored mesh Combine/Separate, frontmost depth picking, and persistent
two-anchor Multi-Cut. The matrix records the missing interaction and topology
contracts for every command.

The existing single-edge extrusion gesture now uses the same prepared-session
architecture as face extrusion and bevel: topology is generated once, signed
distance samples update sparse channels, and the authoritative operator still
commits on release. The 65 x 65 core fixture evaluated in approximately
`0.07 ms/frame`; this excludes renderer upload and Qt paint and is therefore a
kernel result, not an end-to-end FPS claim.

The highest-priority remaining shared foundations are stable logical component
IDs/remaps after arbitrary topology edits, a general ordered operation stack,
first-class editable polygon objects inside compositions, dirty-range GPU
uploads, and explicit Delete History baking. Until those exist, commands such
as arbitrary Insert Edge Loop, turning-chain bevel, chained Multi-Cut, Quad
Draw extension/relax, and general per-object component editing must remain
labeled as partial.

## Verification standard

Focused tests cover the typed recipe schema and KMAP round trip, exact topology
counts, manifold/winding checks, axis/baseline behavior, cap and twist behavior,
non-mutating one-primitive preview, one-record commit, and signed inspector
ranges. The rebuilt Debug `GhostStudio.exe` was then exercised through its real
Qt accessibility surface: create a Composition Starter Room, add and select a
cube, change width and X/Y/Z subdivisions, wait for the mesh-local preview,
cancel back to the exact `1/1/1` baseline, repeat, apply once, undo back to the
baseline, and redo to `4/3/2`. The running status bar reported a `1.77 ms`
uncommitted preview and distinct Undo/Redo history messages. Visible captures
are retained at:

- `Saved/Audits/maya_modeling_parity_20260714/map_studio_primitive_live_preview.png`
- `Saved/Audits/maya_modeling_parity_20260714/map_studio_primitive_apply_undo_redo.png`

This proves the Ghost Studio interaction lifecycle in the actual native host;
it is not a claim that all 32 shelf commands are already Maya-equivalent.

This work is not, by itself, KOTOR engine proof. Any writer/export change still
requires vanilla structural comparison, a `plcaa` build, and a user-driven
KOTOR 2 warp before it may be called game-loadable.
