# Character Builder Continual Fixture: Bendak to Mandalorian

**Date added:** 2026-06-04
**Roadmap area:** M17-M22 native KOTOR Character Builder pipeline
**Primary task family:** T1205 / T1703 / T1803 / T1901 / T2203

## Fixture Contract

Use this external FBX as the continual Character Builder test model:

```text
C:\Users\NewAdmin\Documents\KotorMods\HighFidelityKotorCharacters\BendakStarkiller\Bendak.fbx
```

The intended KOTOR replacement target is:

```text
n_mandalorian03
```

Success means GhostRigger can transform the Bendak FBX into a usable KOTOR
replacement for `n_mandalorian03`, with the imported mesh aligned to the native
KOTOR template, bound to the preserved Odyssey node DAG, able to preview inherited
animations, and exported as an MDL/MDX candidate that reloads through the normal
validation gates.

Do not commit the FBX into the repository. It is a local modding fixture and
should be referenced by absolute path in manual QA notes or local-only test
configuration.

## Current Ground Truth

MCP checks on 2026-06-04 confirmed:

- The local Bendak FBX path exists.
- The configured K1/K2 game-library lookup currently lists `n_mandalorian`, but
  does not resolve `n_mandalorian03`.
- K1 `pmbam` remains available and reports 61 nodes, 44 mesh nodes, 17 bones,
  and supermodel `S_KPMF0200`.
- K1 Ghidra context is loaded for future engine-loader checks.

Treat `n_mandalorian03` lookup failure as a program/library-indexing issue to
resolve, not as permission to silently substitute a different target in this
fixture.

## Required Workflow

1. Open Character Builder.
2. Select or resolve the KOTOR base skeleton/model target for `n_mandalorian03`.
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
- Reload verification records native snapshot/report evidence.

## Capability Honesty

Passing GhostRigger preview and reload validation makes the output an export
candidate, not a guaranteed game-ready asset. Do not call this fixture
game-ready until it has also been installed into Override or a patch package and
tested in KOTOR with the expected appearance/UTC/2DA wiring.
