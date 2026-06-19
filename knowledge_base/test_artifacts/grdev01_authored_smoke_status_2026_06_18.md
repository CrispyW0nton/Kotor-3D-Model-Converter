# grdev01 Authored Smoke Status - 2026-06-18

Owner: LordVaderCW
Task: T2648
Subsystem: Map Studio / authored module smoke proof

## Current State

The one-shot authored Map Studio smoke prep command has generated and installed the current `grdev01.mod` candidate for KOTOR 1.

This is **not game-tested yet**. It is only verified as installed and ready for an in-game launch test.

## Generated Package

- KMAP: `artifacts/map_studio/grdev01_authored_smoke_installed/grdev01.kmap`
- Staged module: `artifacts/map_studio/grdev01_authored_smoke_installed/install/Modules/grdev01.mod`
- Pack manifest: `artifacts/map_studio/grdev01_authored_smoke_installed/grdev01_pack_manifest.json`
- Proof manifest: `artifacts/map_studio/grdev01_authored_smoke_installed/grdev01_authored_module_game_manifest.json`
- Checklist: `artifacts/map_studio/grdev01_authored_smoke_installed/grdev01_authored_module_game_checklist.md`

## Installed Game Copy

- Installed module: `C:/Program Files (x86)/Steam/steamapps/common/swkotor/Modules/grdev01.mod`
- Previous installed copy backup: `C:/Program Files (x86)/Steam/steamapps/common/swkotor/Modules/grdev01.mod.bak1`
- Installed SHA-256: `9f8543313fefdbf23483daa2f85c45e40c2a9d27167a78bbb0aa4bc0c217872e`
- Staged SHA-256: `9f8543313fefdbf23483daa2f85c45e40c2a9d27167a78bbb0aa4bc0c217872e`
- Installed copy matches staged package: yes

## Package Readback Evidence

`scripts/check_grdev01_smoke_status.py` reported:

- Status: `installed_ready_for_game_test`
- `ready_for_game_launch`: `true`
- Package verification: `verified`
- Parsed GFF: `grdev01.are`, `grdev01.git`, `module.ifo`, `grdev01.pth`
- Parsed WOK: `grdev01_room01.wok`
- Model pair: `grdev01_room01.mdl/.mdx`
- Path points: `3`
- Path connections: `6`
- Missing required runtime resources: none

Required archive resources are present:

- `grdev01.are`
- `grdev01.git`
- `module.ifo`
- `grdev01.pth`
- `grdev01.lyt`
- `grdev01.vis`
- `grdev01_room01.mdl`
- `grdev01_room01.mdx`
- `grdev01_room01.wok`

## Commands Used

```powershell
python scripts\prepare_grdev01_authored_smoke.py --output-dir artifacts\map_studio\grdev01_authored_smoke_installed --overwrite-kmap --auto-detect-game-modules-dir --overwrite-module --json
```

```powershell
python scripts\check_grdev01_smoke_status.py --proof-manifest artifacts\map_studio\grdev01_authored_smoke_installed\grdev01_authored_module_game_manifest.json --game-modules-dir "C:\Program Files (x86)\Steam\steamapps\common\swkotor\Modules" --json
```

## Remaining Proof Gate

The next step must be a real KOTOR 1 run:

1. Launch KOTOR 1.
2. Run `warp grdev01`.
3. Confirm the module loads.
4. Confirm the player appears on the generated floor, not in void.
5. Confirm the test placeable appears where expected.
6. Confirm the player can walk on the generated floor.
7. Capture screenshot or video evidence.
8. Record the proof:

```powershell
python scripts\record_authored_module_game_proof.py --proof-manifest artifacts\map_studio\grdev01_authored_smoke_installed\grdev01_authored_module_game_manifest.json --evidence <screenshot-or-video> --module-loads-in-game --player-spawns-on-floor --test-placeable-visible --player-can-walk-on-floor
```

Do not mark the Map Studio smoke goal complete until the proof manifest and pack manifest are updated from actual in-game evidence.
