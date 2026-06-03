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
2026-06-03.  Function addresses for the MDL loader and animation resolver are
therefore not yet verified and must not be cited as confirmed.  A later targeted
string-reference scan did verify selected hardcoded hook strings and
representative referring functions; those are recorded separately below because
they are narrower evidence than a fully decompiled attachment routine.

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

## Engine String Evidence: Attachment and Visual Hooks

Source: GhostRigger MCP `kotor_engine_script`, queried 2026-06-03.

This pass searched for exact defined string literals and collected references
to those strings.  It confirms that selected hook names are hardcoded and used
by representative K1/K2 weapon, visual-effect, camera, and control routines.
It does **not** yet prove complete MDL-loader behavior, full attachment
fallback behavior, or all socket semantics.

| Game | Exact string | String address | Representative referring functions |
| --- | --- | --- | --- |
| K1 | `rhand` | `0074f334` | `SwitchWeaponEvent@00610f40`, `ApplyLightsaberThrow@006a30e0`, `LoadVisualEffect@006a1880`, `HideWieldedItems@0069a6b0` |
| K1 | `lhand` | `0074f4b8` | `SwitchWeaponEvent@00610f40`, `LoadVisualEffect@006a1880`, `HideWieldedItems@0069a6b0` |
| K1 | `camerahook` | `0074f42c` | `SetAnimatedCamera@00641010`, `SetCamera@00671670`, `Setup3DScene@006100f0` |
| K1 | `handconjure` | `00751d74` | `LoadVisualEffect@006a1880`, `ApplySpellVisual@006a2e10`, `LoadConjureVisual@00695f30` |
| K1 | `impact_bolt` | `00751d40` | `HandleServerToPlayerSafeProjectileProjectile@006501b0` |
| K1 | `FreeLookHook` | `0075164c` | `Control@00639d00` |
| K2 | `rhand` | `00985e94` | `SwitchWeaponEvent@0040f4a0`, `ApplyLightsaberThrow@004fec40`, `LoadVisualEffect@004fae10`, `HideWieldedItems@004f5d80` |
| K2 | `lhand` | `00985e8c` | `SwitchWeaponEvent@0040f4a0`, `LoadVisualEffect@004fae10`, `HideWieldedItems@004f5d80` |
| K2 | `handconjure` | `00988b6c` | `LoadVisualEffect@004fae10`, `ApplySpellVisual@004fe950`, `LoadConjureVisual@004895b0` |
| K2 | `impact_bolt` | `009892c8` | `HandleServerToPlayerSafeProjectileProjectile@004bd180` |
| K2 | `FreeLookHook` | `0098b10c` | `Control@004e8350` |

Targeted decompile attempts for representative functions such as
`SwitchWeaponEvent` and `ApplyLightsaberThrow` returned function metadata and
disassembly, but the Ghidra decompiler process did not launch in the current
environment.  Therefore this section should be cited as string-reference
evidence, not as a full source-level semantic proof.

Limitations:

- The exact-string scan did not find defined literals for `headhook`,
  `LightsaberHook`, `DeflectHook`, or `headconjure` in this pass.  Those names
  remain fixture-verified through model data, not engine-string-verified.
- The absence of a defined exact string does not prove that a hook is unused;
  it may be constructed indirectly, referenced through data tables, hashed, or
  handled by model-specific runtime state.
- Full socket attachment fallback behavior and missing-node behavior remain
  pending until the owning routines are decompiled or otherwise traced.

## Targeted Function Metadata / Disassembly Evidence

Source: GhostRigger MCP `kotor_decompile_function` and
`kotor_inspect_memory`, queried 2026-06-03.

The Ghidra decompiler process still did not launch, so this is not source-level
decompilation.  However, targeted function metadata and disassembly are
available for known addresses.  This is enough to record function names,
signatures, instruction addresses, and static string addresses, while still
keeping MDL parser semantics marked as pending.

| Game | Function | Address | Evidence |
| --- | --- | --- | --- |
| K1 | `SwitchWeaponEvent` | `00610f40` | Function metadata reported signature `void __cdecl SwitchWeaponEvent(CAurObject *, char *, void *)`.  Disassembly at `00610f7a` loads static string address `0074f4d4`, and `00610fa6` loads `0074f4cc`; `kotor_inspect_memory` identifies those strings as `AppearanceForceUpdate` and `Loading`. |
| K1 | `LoadVisualEffect` | `006a1880` | Function metadata reported signature `int __thiscall LoadVisualEffect(CSWCVisualEffectOnObject *, ushort, int, ulong, ulong, ulong, byte, uchar, Vector)`.  Disassembly at `006a1a15` pushes static string address `0074b834`; `kotor_inspect_memory` identifies the string as `Imp_HeadCon_Node`.  `kotor_inspect_memory` also verifies `00751d74` as the exact string `handconjure`. |

Character Builder implications:

- This confirms targeted address-level inspection is usable even when broad
  symbol searches and the decompiler are unavailable.
- `LoadVisualEffect` references visual-effect hook/configuration strings, so
  helper nodes such as `handconjure`, `impact_bolt`, and related native
  template helpers should remain native-template-owned.
- `Imp_HeadCon_Node` is evidence for a visual-effect configuration/key string,
  not proof that the exact native socket `headconjure` was found as an engine
  string literal.
- These findings still do **not** prove MDL parser layout, skin weight behavior,
  full attachment fallback semantics, or missing-node behavior.

Tooling caveat:

- A broad `kotor_engine_script` memory scan returned no matches even for known
  addresses that `kotor_inspect_memory` can read.  Do not treat that broad scan
  as negative evidence.  Use targeted address reads or improved scripts for the
  next reverse-engineering pass.

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
6. Complete equipment/socket attachment routine analysis.  Selected string refs
   are now verified for `rhand`, `lhand`, `camerahook` in K1, `handconjure`,
   `impact_bolt`, and `FreeLookHook`; full semantics and missing-node behavior
   remain pending.
7. Narrow or disprove explicit engine string/function evidence for `headhook`,
   `LightsaberHook`, `DeflectHook`, and `headconjure`.

Until these function addresses are confirmed, Character Builder code should cite
this document only for the verified fixture facts and selected hook string refs
above, not for engine-loader internals.
