# Character Builder Continual Fixture: Bendak to Mandalorian

**Date added:** 2026-06-04
**Roadmap area:** M17-M22 native KOTOR Character Builder pipeline
**Primary task family:** T1205 / T1703 / T1803 / T1901 / T2203

## Fixture Contract

Use this external FBX as the continual Character Builder custom mesh payload:

```text
C:\Users\NewAdmin\Documents\KotorMods\HighFidelityKotorCharacters\BendakStarkiller\Bendak.fbx
```

Use this KOTOR model as the native skeleton / node-DAG authority:

```text
n_mandalorian
```

The optional intended replacement/variant target for packaging tests is:

```text
n_mandalorian03
```

Success means GhostRigger can import the Bendak FBX as a custom mesh, fit it to
the `n_mandalorian` KOTOR skeleton, discard/quarantine any external FBX skeleton
as final authority, bind the Bendak mesh to the preserved Odyssey node DAG,
preview inherited/local Mandalorian animations, and export an MDL/MDX candidate
that reloads through the normal validation gates.

Do not commit the FBX into the repository. It is a local modding fixture and
should be referenced by absolute path in manual QA notes or local-only test
configuration.

## Current Ground Truth

MCP checks on 2026-06-04 confirmed:

- The local Bendak FBX path exists.
- The configured K1/K2 game-library lookup currently lists `n_mandalorian`, but
  does not resolve `n_mandalorian03`.
- K1 and K2 `n_mandalorian` both resolve as loadable MDLs with 70 nodes, 52 mesh
  nodes, 18 bones, local `pause1`/`pause2`, and supermodel `S_Female02`.
- MCP audit of K1/K2 `n_mandalorian` reports valid bounds and the same
  70-node / 52-mesh shape, while also surfacing current loader UV-count
  mismatch reports on native mesh nodes. Treat those native UV audit messages
  as loader/representation caveats, not as permission for imported Character
  Builder payloads to omit texture and UV evidence silently.
- K1 `pmbam` remains available and reports 61 nodes, 44 mesh nodes, 17 bones,
  and supermodel `S_KPMF0200`.
- K1 Ghidra context is loaded for future engine-loader checks.

Headless workflow proof on 2026-06-04 confirmed:

- `Bendak.fbx` loads as the imported custom mesh payload.
- K1 and K2 `n_mandalorian` load as selected native KOTOR base skeletons.
- Auto-fit reports `Fit to n_mandalorian (0.331x)`.
- `apply_template_rig` produces a `native_template_final` candidate with
  one skinned Bendak payload mesh, 55 KOTOR bone slots, and inherited
  `S_Female02` motion source.
- Staged KOTOR export writes `bendak.mdl` / `bendak.mdx` to temp output
  folders for both K1 and K2, and reload verification passes with hooks
  `rhand`, `Lhand_g`, and `headhook`, one mesh node, one skin node, and
  supermodel `S_Female02`.
- The headless workflow result code for a successful reload proof is
  `export_candidate_verified`, with `capability_stage=export_candidate` and
  `game_tested=False`. Do not treat this as an in-game launch claim.
- `tests/test_character_builder_bendak_local_fixture.py` preserves this as a
  guarded local fixture test. It skips when the local FBX or configured game
  install is unavailable, but in the current fixture environment it passed for
  both K1 and K2.
- The same guarded local fixture now packages the verified export under target
  resref `n_mandalorian03` for both K1 and K2 using the staged Character Builder
  Override-package readiness path. The package writes `n_mandalorian03.mdl`,
  `n_mandalorian03.mdx`, an Override manifest, and a readme/checklist into a
  temp package folder without touching a live game install.
- Current skin binding evidence is now explicit: the generated payload is
  recorded as `native_template_nearest_vertex_donor` /
  `donor_transfer_first_pass` when every imported vertex receives weights from
  the selected native KOTOR template donor surface. In the Bendak local fixture,
  all 4,722 imported vertices transfer from 2,166 native donor vertices with no
  nearest-bone fallback vertices.
- Donor/template weight transfer is no longer treated as trusted deformation
  evidence unless Auto-Fit records a complete source and target landmark set
  for `head`, `pelvis`, `side_pair`, `left_foot`, and `right_foot`. If donor
  weights exist but those landmarks are incomplete, export may remain allowed,
  but the validation report marks the weight gate as
  `donor_transfer_landmarks_incomplete` so the modder knows the mesh still
  needs fit/correspondence review before launch-quality claims.
- Character Builder compacts the generated skin bone map to the used influence
  slots before MDL/MDX export, keeping `bone_map`, `qbone_list`, `tbone_list`,
  and per-vertex influence indices aligned through writer/readback validation.
- Export preflight now requires recorded auto-fit evidence for native-template
  final rigs. The report must prove a finite positive scale, finite XYZ
  translation, sufficient confidence, non-fallback fit mode, and the KOTOR
  contract that the native skeleton remains the final DAG authority while the
  Bendak mesh remains the payload guest.
- Reload verification now emits a dedicated native-DAG proof after staged
  MDL/MDX readback. It checks that the selected KOTOR template's structural,
  helper, deform-helper, and socket paths still reload with exact casing and
  parent paths before ExportJob promotes final files. If a hook such as
  `headhook` is missing or moved after reload, promotion is blocked.
- Reload verification also checks imported payload mesh integrity. The Bendak
  mesh payload names from Character Builder bind evidence must reload with the
  same vertex count, face count, skin-row count, and compact KOTOR bone-map
  count before final MDL/MDX files are promoted.
- Validation reports now record SHA-256 hashes and byte sizes for the exact
  staged MDL/MDX pair. Override packaging verifies those hashes against the
  source files before copying, and game-test evidence must bind to the same
  artifact hashes before claiming `game_tested`.
- The native-template launch proof now resolves inherited animation libraries
  through the selected base model's real supermodel chain instead of trusting
  only the stored `supermodel` string. In the current configured install,
  K1 `n_mandalorian` resolves 267 available animations through
  `N_Mandalorian -> S_Female02 -> S_Female01 -> S_Male02 -> S_Male01`, and K2
  resolves 456 available animations through the same chain. The guarded
  Bendak fixture asserts that inherited/local names such as `pause1`, `pause2`,
  `walk`, and `tlknorm` are available before treating the export as a verified
  candidate.
- Staged validation reports now keep this as a separate animation evidence
  gate alongside fit, bind, and weight. The report records motion source,
  assigned/effective/resolved supermodel, available clip count, sample
  animation names, preview-slot coverage, and resolver diagnostics so a modder
  can see whether the candidate is only reload-verified or also has inherited
  animation-library proof.
- Staged validation reports now also record Auto-Fit landmark source evidence.
  The fit gate distinguishes imported skeleton/armature landmarks from mesh
  payload landmarks, mixed landmark evidence, and unrecorded landmark sources.
  This is the current proof that orientation and scale were driven by the
  imported rig's anatomy before the mesh payload was attached to the native
  KOTOR node hierarchy.
- Export preflight now warns when native-template candidates lack recorded
  Auto-Fit landmark source provenance or when any source fit landmark came
  from the mesh payload instead of the imported skeleton/armature. These
  candidates can remain exportable, but the fit evidence gate becomes
  `needs_review` in staged reports so mesh-only or weakly-proven alignment is
  not mistaken for launch-quality rig evidence.
- Export preflight now also treats imported payload material readiness as its
  own evidence gate. Missing texture/material names, missing UVs, UV-count
  mismatches, and invalid face-UV indices are warnings rather than structural
  export blockers, but staged reports mark the `material` gate as
  `needs_review` until a modder can prove the custom payload will appear with
  the intended texture mapping in-game.
- Staged validation reports now also include an `engine` evidence gate derived
  from `docs/ghidra_findings.md` and `CHARACTER_EXPORT_EVIDENCE`. This gate is
  currently `partial_reverse_engineering`, not `passed`, because MDL loader
  functions, skin-weight normalization behavior, complete socket semantics,
  and selected helper-string refs remain pending Ghidra work. Treat this as an
  explicit honesty marker: reload verification plus per-game manual testing can
  prove a candidate was tested, but the engine reverse-engineering ledger is
  still incomplete.

This proves a reload-verified export candidate, not an in-game-tested
replacement.

As of 2026-06-04, GhostRigger requires structured in-game evidence before an
export/package may claim `game_tested`. The evidence must use the
`ghostrigger.character_game_test.v1` schema, cover both `K1` and `K2`, and
mark every manual checklist item as passed separately for each game under
`per_game_checklist_results`. A legacy/global checklist claim is not enough.
Without per-engine evidence, Bendak remains an export candidate even when
MDL/MDX reload verification and Override packaging both succeed.

Treat `n_mandalorian` as the mandatory native base MDL that supplies the KOTOR
node DAG for this fixture. If a packaging/export test targets
`n_mandalorian03`, the Character Builder must keep both identities visible:
`n_mandalorian` is the base skeleton, while `n_mandalorian03` is only the
requested replacement/variant target.

## Required Workflow

1. Open Character Builder.
2. Select `n_mandalorian` as the KOTOR base skeleton/model.
   If the user types `n_mandalorian03` for an export/replacement target, the UI
   should explicitly show that it still loads base MDL `n_mandalorian` for the
   native skeleton.
3. Import `Bendak.fbx`.
4. Auto-fit the imported mesh to the KOTOR base:
   - correct front-facing direction,
   - correct upright axis,
   - scale close enough that only minor manual edits are needed,
   - root/pivot positioned at the KOTOR template origin.
5. Build the native KOTOR skeleton:
   - preserve exact native KOTOR node names and casing,
   - preserve the base DAG parent/child contract,
   - attach the imported Bendak skin mesh to the final native template state,
   - remove or quarantine temporary external armature nodes from export.
6. Assign inherited supermodel animations or selected local slots.
7. Preview at least idle, walk/run if available, and one combat-style animation.
8. Export MDL/MDX through the staged ExportJob path.
9. Reload the exported MDL/MDX and run Character Builder preflight/report gates.

## Acceptance Gates

The fixture is not considered passing until all of these are true:

- The Bendak mesh auto-orients and scales to the Mandalorian template with only
  small manual correction.
- Build/Confirm attaches the generated KOTOR node hierarchy to the Bendak mesh
  so translating preview state does not detach mesh from skeleton.
- Symmetry edits remain toggleable and apply to paired compatible guide nodes.
- The animation library populates from the selected supermodel chain.
- Previewed inherited animations deform the Bendak mesh plausibly.
- Export is blocked before writing if the final rig state is not
  `native_template_final`.
- Export writes MDL/MDX only through the staged Character Builder export
  transaction.
- Reload verification records native snapshot/report evidence and blocks if
  staged readback loses or moves selected native KOTOR structural paths or
  truncates the imported payload mesh/skin binding counts.
- Donor/native-template weight transfer is only considered trusted when the
  auto-fit report proves complete landmark correspondence for the selected
  native base and imported payload.
- Game-tested promotion requires a per-game manual checklist for K1 and K2;
  one shared checklist result must not promote the candidate.
- Game-tested promotion and packaging must identify the exact tested MDL/MDX
  bytes by SHA-256 hash.

## Capability Honesty

Passing GhostRigger preview and reload validation makes the output an export
candidate, not a guaranteed game-ready asset. Do not call this fixture
game-ready until it has also been installed into Override or a patch package and
tested in KOTOR with the expected appearance/UTC/2DA wiring.
