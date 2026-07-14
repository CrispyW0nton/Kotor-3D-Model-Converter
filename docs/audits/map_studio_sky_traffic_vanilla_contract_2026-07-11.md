# Map Studio Sky-Traffic Vanilla Contract Audit

Date: 2026-07-11

Owner: LordVaderCW

Roadmap: T3007 / T2908 / T3103

## Conclusion

KOTOR sky traffic is not a normal GIT placeable in the representative vanilla
maps. It is a room MDL/MDX animation graph. Map Studio may present an
Unreal-like actor with an arrow, spline, speed, banking, and loop controls, but
its compiler must write or preserve room-local `animloop1`, `animloop2`, or
`animloop3` controller data.

K2 executable disassembly around VAs `0x7A458E`, `0x7A45B4`, and `0x7A45DA`
passes those three animation names through the same model animation call. The
engine starts the named room loops; the examined module scripts do not.

## Vanilla Oracles

| Game/area | Room | Vanilla implementation |
|---|---|---|
| K1 Taris | `M02ab_02l` in `tar_m02ab` | 33.333-second `animloop1`, 109 animation-tree nodes, and 107 moving ship/dummy branches. `M02ac_02q` follows the same pattern. |
| K1 Dantooine | `m14aa_01f` | 63.833-second `animloop2`; moving `Brithdummy` owns `BrithRef`, a type-6 reference to `C_Brith` with `reattachable=0`. Equivalent rooms occur in `m14ab`, `m14ac`, and `m14ad`. |
| K2 Telos | `201TEL15` | 50-second `animloop1`; three shuttle parent dummies drive embedded textured shuttle meshes. Equivalent patterns occur in `202TEL06`, `203TELo`, `204TELo`, `208TELo`, `209TELo`, and `211TELd`. |

The matching GIT/script resources contain no flying visual actor or traffic
script. Taris uses spatial traffic/launch sounds, Dantooine has no Brith GIT
creature, and `201TEL` uses a muffled traffic sound.

### Exact K2 Telos Fixture

`201TEL15` is the primary K2 oracle:

- LYT position `(-92.836, -25.5385, 0)`;
- 81 geometry nodes, 62 meshes, embedded AABB node `walk15`;
- WOK with two walkable faces;
- `animloop1`: 50 seconds, 0.25 transition, animation root `201TEL15a`;
- sparse reachable animation tree of five nodes while the animation geometry
  header correctly declares all 81 geometry nodes;
- `ShuttleA_Dummy`: 171 position and 171 orientation keys;
- `ShuttleA_Dummy01`: 146 position and 146 orientation keys;
- `ShuttlB_Dummy`: 136 position and 132 orientation keys;
- shuttle texture `TEL_NShtl`;
- stars, Telos planet/backdrop, station, and lightmapped station geometry in
  the same room.

Sky/backdrop preservation and traffic preservation therefore cannot be
separate destructive import paths.

## Binary Contracts Observed

- Static root-node `+8` is `0`.
- Animation-node `+8` points to the owning animation-geometry offset.
- Animation geometry subtype is `5`.
- Position controller type is `8`.
- Orientation controller type is `20`.
- Animation geometry may declare the full room geometry node count while its
  reachable animation tree is intentionally sparse.
- Vanilla traffic position controllers use `binary_unknown0=16`.
- Vanilla traffic orientation controllers use `binary_unknown0=28`.
- Traffic orientation payloads use compressed two-column quaternions.
- Dantooine `Dummy01` uses a Bezier position controller with column flag
  `0x13`.

The static-controller `unknown0=0xFFFF` rule must not be applied blindly to
animation controllers.

## Current GhostStudio Losses

1. Stock room conversion flattens rendered surfaces and discards animations,
   dummy/reference nodes, emitters, and controller graphs.
2. Bezier controller data is not lossless. Position import forces three
   columns and writer masking turns `0x13` into `3`, removing interpolation
   metadata/tangents.
3. Authored animation export has no quaternion compressor matching vanilla's
   two-column orientation payload.
4. Default validation expects visited animation nodes to equal the declared
   count, rejecting vanilla's sparse-tree/full-count room animation contract.

Closed in the bounded 2026-07-11 preservation slice:

- reference-node model resref and `reattachable` now survive conversion,
  `ModelNode` cloning, primary/legacy writing, and readback;
- a legitimate zero animation transition is no longer replaced with `0.25`;
- the installed K1 `m14aa_01f` probe preserved `BrithRef -> C_Brith`,
  `reattachable=false`, and `animloop2 transition=0.0` through primary
  GhostStudio write/readback.

Until these are corrected, converting and re-exporting a traffic room must be
reported as destructive and blocked unless the original runtime graph is
retained unchanged.

## Authoring Contract

KMAP stores compact, human-readable intent:

- stable actor ID and host room;
- verified reference-model or embedded-mesh asset mode;
- source game/resref plus dependency hashes;
- automatic loop slot (`animloop1`, `animloop2`, or `animloop3`);
- room-local spline points;
- speed/duration, phase offset, direction, tangent facing, banking, smoothing,
  and loop policy;
- optional UTS/GIT sound binding;
- editor-only arrow/spline visibility.

For imported stock rooms, keep a retained-runtime binding containing source
game/resref, MDL/MDX hashes, required animation slots, retained non-render node
names, and preservation policy. Hydrate the graph from the source installation
or a project sidecar cache; do not embed opaque model bytes in KMAP. A missing
or hash-mismatched source blocks export instead of silently deleting traffic.

The compiler must attach the actor to a host-room dummy, use a reference node
only for proven compatible assets such as `C_Brith`, generate monotonic type-8
position and type-20 orientation tracks, and preserve sparse hierarchy,
animation root, transition, compression, Bezier metadata, opaque controller
bytes, and animation-node `+8`. It must never emit the actor as a normal GIT
placeable unless the user deliberately selects a separately proven scripted
interactive-object workflow.

## Required Proof Sequence

1. Add red tests for reference headers, zero transitions, Bezier tracks,
   compressed orientations, controller `unknown0`, and sparse declared counts.
2. No-edit structural round-trip against K1 `M02ab_02l`, K1 `m14aa_01f`, and
   K2 `201TEL15`.
3. Edit an unrelated mesh face and prove every retained track/reference is
   unchanged.
4. Build authored K1 Brith and K2 shuttle fixtures.
5. Compare raw animation-tree layout, controllers, MDL/MDX, LYT/VIS/WOK, and
   sampled world transforms with vanilla.
6. Manually warp in K1 and K2, watch at least two complete loops, and retain
   live-log plus video evidence.

Parser/readback success is not a game proof.
