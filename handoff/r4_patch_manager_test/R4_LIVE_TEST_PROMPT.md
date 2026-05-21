# R4 Live Test Prompt - KOTOR Custom Animation Integration

Test ID: `R4_GHOST_RIGGER_UE5_IDLE_LIVE_TEST_20260521`

Objective: validate end-to-end integration of a Ghost Rigger-retargeted UE5 animation through Custom Animation Core into a live KOTOR session.

Test type: proof-of-pipeline, not animation quality validation.

## Inputs

Modified model:

- Path: `files/override/pmbam.mdl`
- SHA-256: `bfcd3468838050d25159afa3c90d963fec1a06fcbfc64b6ea9982adc4a8be8df`
- Paired MDX: `files/override/pmbam.mdx`
- MDX SHA-256: `84dc9b42faa0b2004c0e10eef6ab0bc65e02ee7bffaca027b829574832a58154`
- Source animation: `M_Neutral_Stand_Idle_Loop` from Epic Game Animation Sample
- Slot: local PMBAM `victory` override
- Frames: 302 at 30 FPS
- Duration: 10.07 seconds

Baseline rollback files:

- `baseline/vanilla_pmbam.mdl`
- `baseline/vanilla_pmbam.mdx`

Reference reports:

- `ghostrigger_injection_manifest.json`
- `viewport_validation_report.json`
- `media/viewport_frame_0150.png`

## Phase 1 - Install Patch

1. Install this package through Patch Manager.
2. Verify `override/pmbam.mdl` and `override/pmbam.mdx` are installed.
3. Verify hashes match `manifest.json`.
4. Verify original files are backed up or can be restored.
5. Save install log to `logs/r4_install.log`.

## Phase 2 - Engine Boot

1. Launch KOTOR with Custom Animation Core enabled.
2. Confirm the game reaches the main menu.
3. Confirm Custom Animation Core registers animation ID `65000`.
4. Confirm no MDL parsing errors or assertion failures appear in logs.

Halt if the game crashes on boot, hangs on a black screen, logs an invalid-model parse error, or Custom Animation Core fails to load.

## Phase 3 - Trigger Animation

Use whichever path is available:

- Combat resolver path matching `CustomAnimationSmokeTest`
- Direct debug/console trigger for `victory`
- NSS script trigger for `ActionPlayAnimation`

Primary success signal: the PMBAM player character visibly changes pose when `victory` triggers.

Secondary signal: animation runs for about 10 seconds.

## Tier Classification

| Tier | Criteria | Meaning |
|---|---|---|
| 0 | Game crashes or animation trigger fails hard | HALT |
| 1 | Animation plays at all, even if rough | PIPELINE PROVEN |
| 2 | Animation plays without obvious corruption | Structural correctness |
| 3 | Animation resembles the UE5 idle | Retargeting correctness |
| 4 | Animation looks KOTOR-native and polished | Sprint 4+ goal |

R4 success threshold is Tier 1.

## Expected Non-Blocking Issues

- Static or stiff fingers.
- Static or limited head/neck motion.
- No translation or root motion.
- Stiff spine from first-pass collapse policy.
- Rough pose quality from core-body-only transfer.

Document these, but do not fail R4 for them.

## Rollback Test

1. Uninstall the patch.
2. Verify override files are removed or restored.
3. Verify vanilla PMBAM hashes match the baseline.
4. Launch the game again and confirm vanilla behavior returns.

## Reporting Contract

Reply with:

```text
[R4 LIVE TEST RESULT]
Tier: [0/1/2/3/4]
Status: PIPELINE PROVEN / HALT

Engine boot: pass/fail
Animation triggered: pass/fail
Duration matched: pass/fail
Rollback clean: pass/fail

Media: [paths]
Report: knowledge_base/live_tests/r4_ue5_idle_in_game_20260521.md

Critical findings:
- [anything unexpected]

Recommended next action:
- [Sprint 4 quality polish or specific debug task]
```
