# Base-Game Module Contract (K1 + K2 Evidence Scan)

Evidence source: `Saved/Codex/base_module_scan.json` (199 modules: 117 K1 + 82 K2,
scanned 2026-07-04 with PyKotor from the installed Steam games). Aggregates in
`Saved/Codex/base_module_contract_summary.md`. Companion design briefs:
`Saved/Codex/brief_kotor_net_analysis.md` (Kotor.NET deep dive) and
`Saved/Codex/brief_kpl_video_analysis.md` (KPL DSL + Area Designer video UX).

Use this file when validating Map Studio exports or defining readiness gates.
These are observed invariants of every shipping BioWare/Obsidian module — treat
violations as export blockers unless the user explicitly overrides.

## Hard invariants (100% of 199 base modules)

1. Every module has ARE, GIT, IFO, LYT, and PTH. PTH may have zero points
   (29 K1 / 9 K2 modules) but the resource itself is always present.
2. `Mod_Area_list` has exactly one area struct, and `Mod_Entry_Area` names it.
3. **ARE `Rooms` list == LYT room set, exactly** (case-insensitive). Zero
   mismatches in 199 modules. Both directions are gates.
4. **VIS is symmetric**: if A sees B then B sees A. Zero asymmetric pairs in
   196 modules with parseable VIS.
5. Every real LYT room has a WOK. The only exceptions are K1 `STUNT_*`
   cutscene modules whose LYT rooms are literally named `****` (no geometry).
   Map Studio should never emit `****` rooms.
6. `SunShadows` is 0 in 198/199 modules (one K2 exception). Default exports
   to shadows off.

## Soft norms (violate deliberately, not accidentally)

- VIS can be absent (3 K1 + 2 K2 modules) — engine loads, but treat a missing
  VIS as a warning, not silence. The K1 "missing" cases are actually
  nonstandard VIS files PyKotor fails to parse.
- Walkable-face share: K1 averages 50.3%, K2 37.4% of WOK faces walkable.
  A module with ~0% walkable faces will technically load but is unplayable —
  gate on "entry point stands on a walkable face" instead of the ratio.
- PTH: average 55 points (K1) / 115 (K2). Zero-point PTH is legal (small or
  cutscene areas) but any module with NPCs that should move needs points.
- GIT norms: waypoints (avg ~35/module) and placeables are near-universal;
  encounters and stores are rare (zero in 80%+ of modules). An empty
  creature/waypoint GIT is unusual but legal.
- Fog: roughly half of modules disable `SunFogOn`. Fullbright exports should
  keep fog off (matches existing Map Studio fullbright sanitizer).
- LYT scale: rooms/module avg 12.6 (K1, max 53) and 15.2 (K2, max 66);
  doorhooks avg 8-13.

## WOK surface material usage (face counts across all base modules)

| ID | Name (nwmax/toolset) | K1 count | K2 count | Walkable |
|----|----------------------|----------|----------|----------|
| 1  | Dirt                 | 55,771   | 8,354    | yes |
| 2  | Obscuring            | 12,452   | 781      | no  |
| 3  | Grass                | 11,314   | 8,809    | yes |
| 4  | Stone                | 6,098    | 16,575   | yes |
| 5  | Wood                 | 882      | —        | yes |
| 6  | Water (walkable)     | 47       | —        | yes |
| 7  | NonWalk              | 78,161   | 88,068   | no  |
| 8  | Transparent          | 173      | —        | no  |
| 9  | Carpet               | 20       | 864      | yes |
| 10 | Metal                | 21,609   | 22,817   | yes |
| 11 | Puddles              | 16       | 88       | yes |
| 13 | Swamp                | 327      | 88       | yes |
| 16 | Mud                  | —        | 138      | yes |
| 17 | Leaves               | 29       | 63       | yes |
| 19 | Door                 | 3,966    | 7,154    | yes |

Practical reading: floors are mostly 1/3/4/10 depending on biome; 7 is the
universal blocker; 19 marks door thresholds and correlates with transition
edges (3,970 K1 / 2,609 K2 transition edge refs). Map Studio's surface
painter should default to this vocabulary and treat IDs outside it as exotic.

## Kotor.NET-derived export contracts (see brief for file citations)

- WOK serialization: walkable faces sorted before non-walkable; adjacency
  records only for walkable faces (`faceIndex*3+edgeIndex`, -1 for absent or
  non-walkable neighbor); perimeter loops chained endpoint-to-endpoint;
  per-boundary-edge transition indices; AABB tree rebuilt on every write.
- `.mod` = ERF V1.0 with `MOD ` signature; resrefs max 16 chars, enforced at
  assignment time, ResID = ordinal index.
- GFF editing should be live-view (mutate the loaded GFF) so unknown fields
  round-trip — never rebuild ARE/GIT/IFO from a dataclass.
- Save-alternatives gate: refuse writes into RIM/BIF with a guided
  alternative (convert to .mod / save to override) instead of a bare error.

## Area Designer (video) UX notes applied to Map Studio direction

- Element-class mode strip (Room/Tile/Wall/Floor/Ceiling/Object x Select/Add)
  with one context-swapped palette dock — maps to our component modes.
- Kit-based room stamping with doorway sockets; ceilings hidden by default
  ("dollhouse" view) via a Visibility dropdown — candidates for viewport
  presentation flags.
- Textured-unlit default rendering of real game assets, dark background.
- Weaknesses to exceed: no gizmos, no undo affordance, no validation gates.
