# GhostRigger Ghidra / Engine Findings

This document is the Character Builder engine-evidence ledger.  It separates
confirmed current evidence from pending reverse-engineering work so export
preflight does not rely on folklore or UI assumptions.

## Scope

The immediate Character Builder contract is:

- the selected native KOTOR base MDL owns the final node hierarchy;
- imported FBX/OBJ/glTF meshes are geometry payloads only;
- exported MDL/MDX candidates must preserve exact native node names, casing,
  parent paths, supermodel inheritance, sockets/hooks, and skin payload limits;
- K1 and K2 must be checked independently because their executable and model
  data are not interchangeable.

## Verified Binary Context

Source: GhostRigger MCP `kotor_binary_info`, queried 2026-06-03.

| Game | Program | Ghidra path | Language/compiler | Function count |
| --- | --- | --- | --- | --- |
| K1 | `swkotor.exe` | `/K1/k1_win_gog_swkotor.exe` | `x86:LE:32:default`, `windows` | 24591 |
| K2 | `swkotor2.exe` | `/TSL/k2_win_gog_aspyr_swkotor2.exe` | `x86:LE:32:default`, `windows` | 27318 |

The shared Ghidra repository is `Odyssey`.  Broad symbol searches for `Model`,
`MDL`, and `super`, plus a narrower function-iteration script, timed out on
2026-06-03.  Function addresses for the MDL loader, animation resolver, and
socket attachment routines are therefore not yet verified and must not be cited
as confirmed.

## Verified Native Body Fixture: `pmbam`

Source: GhostRigger MCP `ghostrigger_model_info`, queried 2026-06-03.

| Fact | K1 `pmbam` | K2 `pmbam` |
| --- | --- | --- |
| Source | `installation:pmbam.mdl` | `installation:pmbam.mdl` |
| Classification | `character` | `character` |
| Node count | 61 | 61 |
| Mesh node count | 44 | 44 |
| Bone/helper count | 17 | 17 |
| Total vertices | 3776 | 3780 |
| Total faces | 2839 | 2839 |
| Local animations | 0 | 0 |
| Supermodel | `S_KPMF0200` | `S_Female02` |
| Bounds min | `[-0.6063836283472632, -0.16740171867242043, -0.0020714636793865426]` | same |
| Bounds max | `[0.6103344030233976, 0.1676994140345448, 1.5574000477790833]` | same |

Confirmed structural helper/socket names for both games:

```text
PMBAM
cutscenedummy
rootdummy
rcollar_dum
rhand
lcollar_dum
lforearm
lhand
headhook
Impact
FreeLookHook
camerahook
headconjure
LightsaberHook
DeflectHook
handconjure
impact_bolt
```

Implications for Character Builder:

- `NativeSkeletonSnapshot` must preserve exact node casing and parent paths.
- `rhand`, `lhand`, `headhook`, `LightsaberHook`, `DeflectHook`, `Impact`,
  `FreeLookHook`, `camerahook`, `headconjure`, `handconjure`, and
  `impact_bolt` should be treated as native structural sockets/helpers rather
  than imported-mesh bones.
- A generated character that began from `pmbam` should not be considered
  export-ready without a native snapshot/provenance record.

## Verified Animation Inheritance Fixture: `pmbam`

Source: GhostRigger MCP `ghostrigger_list_retarget_animations`, queried
2026-06-03.

K1 chain:

```text
pmbam (0 local)
-> S_KPMF0200 (44 local, 44 new)
-> S_Female01 (48 local, 46 new)
-> S_Male02 (166 local, 166 new)
-> S_Male01 (12 local, 12 new)
```

K1 effective animation count: 268.

K2 chain:

```text
pmbam (0 local)
-> S_Female02 (88 local, 88 new)
-> S_Female01 (76 local, 73 new)
-> S_Male02 (230 local, 230 new)
-> S_Male01 (65 local, 65 new)
```

K2 effective animation count: 456.

The inherited chains include standard preview/runtime clips such as `pause1`,
`run`, and `tlknorm`.  This supports the Character Builder Step 3 requirement
that a valid KOTOR body/supermodel selection should populate an animation
library even when the body model itself has zero local animations.

## Verified Audit Caveat: UV Counts

Source: GhostRigger MCP `ghostrigger_audit`, queried 2026-06-03.

Both K1 and K2 `pmbam` report `bounding_box_ok: true` but also report many
`UV count mismatch (0 uvs vs N verts)` issues on skin nodes.  These audit
messages are current GhostRigger pipeline diagnostics, not yet confirmed
engine-fatal conditions.  Export preflight should not treat this exact audit
shape as an engine crash condition without deeper MDL/MDX loader evidence.

## Pending Ghidra Work

The following items are required before the Character Builder can claim
engine-complete export hardening:

1. Locate and document K1/K2 MDL parser functions.
2. Document MDL header layout, node array structure, name lookup behavior,
   controller arrays, and MDX offset handling.
3. Confirm skin mesh bone references, weight arrays, `qbone`/`tbone` matrices,
   maximum influences per vertex, and whether the engine normalizes weights.
4. Locate supermodel name resolution and confirm resref case behavior.
5. Locate animation-node matching and confirm exact/case/hash/index behavior.
6. Locate equipment/socket attachment routines for `headhook`, `rhand`,
   `lhand`, `LightsaberHook`, `camerahook`, and related helpers.

Until these function addresses are confirmed, Character Builder code should cite
this document only for the verified fixture facts above, not for engine-loader
internals.
