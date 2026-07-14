# KotorMCP Live-Debug Skill

How to prove a Map Studio module in-game and triage engine crashes with the
GhostRigger KotorMCP stack. Written 2026-07-08 after the K2 plcaa hunt.

## The stack

| Piece | What it does |
| --- | --- |
| `kotor_dinput_hook_*` | DirectInput proxy DLL (`dinput8.dll` in the game dir). Queues key taps / console text via `kotor_dinput_proxy_commands.txt`; the DLL replays them into the game's DirectInput reads. |
| `kotor_log_*` | Debugger-attach logger. Waits for `swkotor2.exe`, records every debug event (exceptions with stack scans, DLL loads, thread exits) to `Saved/KotorLiveLogs/<session>/events.jsonl`. |
| `kotor_input_*` | OS-level SendInput window driver: menu clicks by screen ratio, window screenshots, and `run_save_warp_route` (Load Game -> save row -> Load -> console warp). |
| `kotor_prepare_save_warp_test` | Preflight: module installed, EnableCheats, windowed, save selection, hook state, `currentgame` staleness. Can also launch the game. |

All are async handlers importable directly (no MCP transport needed):
`from kotormcp.tools import kotor_live_log, kotor_dinput_hook, kotor_input, game_test`
Each returns `{"type":"text","text":"<json>"}` — parse `json.loads(raw["text"])`.
`scripts/kotor_live_warp_plcaa.py` is the reference driver (env:
`GR_WARP_TARGET`, `GR_SESSION_LABEL`, `GR_SKIP_PREFLIGHT`).

## The evidence-first loop

1. **Arm the logger BEFORE the game exists**: `kotor_log_start` with
   `wait_for_process=True` and a generous `duration_seconds` (it is a hard
   window — a 30-min window armed at 12:18 captures nothing at 13:56).
2. Launch (preflight `launch_game=True`) or let the human launch.
3. Drive or let the human drive: save load, then `warp <module>`.
4. `kotor_log_stop` + `kotor_log_analyze` (`annotate_with_ghidra=True`,
   `ghidra_program="/TSL/k2_win_steam_aspyr_swkotor2.exe"`).
5. Read `analysis.txt` / `analysis.json`: exception code, faulting module +
   offset, raw stack scan (return addresses into `swkotor2.exe`).

## Hygiene rules (each one bit us)

- **Clear `kotor_dinput_proxy_commands.txt` before every launch** — stale
  queued keys replay into the next session and contaminate it (we found the
  game sitting in the inventory screen from replayed keys).
- **Delete `<game>/currentgame/` after a crash and after reinstalling a
  module** — the engine caches visited modules there and will happily load
  the stale copy instead of your fixed `Modules/<name>.mod`.
- A save whose `last_module` equals the warp target invalidates the test —
  preflight enforces this.
- Manual (non-instrumented) crashes still leave evidence: WER
  `%ProgramData%\Microsoft\Windows\WER\ReportArchive\AppCrash_swkotor2*`
  (`Sig[3]`=module, `Sig[6]`=exception, `Sig[7]`=offset). Offsets there match
  the logger's `module_offset_hex` — you can correlate human runs with
  instrumented ones.
- Verify screen state from screenshots before trusting menu automation; the
  route assumes `start_screen`.

## Crash attribution checklist

1. Exception code + read/write address (`exception_parameters`): a tiny
   absolute address (e.g. 132 = 0x84) means NULL-object field access.
2. Faulting offset → Ghidra (see kotorghidraskill.md): decompile the
   function; walk the raw stack values that point into `swkotor2.exe` for
   callers (`value_hex` frames; instruction *after* a CALL = that CALL ran).
3. Correlate the crash T+ time against the action timeline (launch, save
   load, warp) from `events.jsonl` epochs.
4. Bisect module content empirically: rebuild variants
   (`k2_plcaa_gameplay_matrix.py --no-door --no-store --no-creatures
   --no-placeables --rename-room`), reinstall, clear `currentgame`, retest.
   Change ONE variable per game run.

## Case law (solved with this flow)

- **LYT doorhook sscanf crash** (`strlen` in `vscan_fn`, offset 0x519f40):
  we emitted 4-token doorhook lines; the engine sscanf's the vanilla shape
  `room door_name 0 x y z qw qx qy qz`. Writer fixed in
  `module_format.py::LYTLayout.to_text`.
- **Object-resolver NULL deref** (offset 0x4b3a8, read at 0x84): find-by-name
  loop resolving object handles; reproduced with and without doors, VIS
  self-reference removed, and once seemingly without the warp — as of
  2026-07-08 still open; next discriminator is warping a KNOWN-GOOD module
  (tst_light) while the custom module sits in Modules, to test whether the
  module-list scan itself is poisoned.
