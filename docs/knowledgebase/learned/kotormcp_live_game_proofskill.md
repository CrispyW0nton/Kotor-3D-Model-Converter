# KotorMCP Live Game Proof Skill

Use this when validating a GhostRigger export inside the real KOTOR runtime,
especially when a Map Studio module, MDL/MDX export, or Override package works
in backend readers but may still fail in `swkotor.exe` or `swkotor2.exe`.

## Ownership

- Product surface: KotorMCP live game testing and Map/Character proof handoff.
- Owning package: `native/GhostRigger.Core.Automation/Python/src/kotormcp`.
- Native hook: `native/GhostRigger.Core.Automation/Native/KotorDInputProxy`.
- Evidence roots: `Saved/KotorLiveLogs`, `Saved/GameTestStaging`, and any
  task-specific proof manifest.

## Required Proof Stack

Use three layers together:

1. Game preflight through `kotor_prepare_save_warp_test`.
2. DirectInput proxy hook through `kotor_dinput_hook_status`,
   `kotor_dinput_hook_install`, and `kotor_dinput_hook_send`.
3. Windows debug-event logger plus Ghidra annotation through `kotor_log_start`,
   `kotor_log_status`, `kotor_log_stop`, and `kotor_log_analyze`.

The debug-event logger is not the DirectInput hook. The logger attaches like a
debugger and records process, DLL, exception, stack, module-offset, and Ghidra
address evidence. The DirectInput hook is the `dinput8.dll` proxy copied beside
the game executable; it lets KotorMCP queue keyboard/mouse input through
`kotor_dinput_proxy_commands.txt` and records hook load/input activity in
`kotor_dinput_proxy.log`.

## Game Aliases

- KOTOR 1: use `game="k1"`, executable `swkotor.exe`, Ghidra alias
  `/K1/k1_win_gog_swkotor.exe`.
- KOTOR 2 / TSL: use `game="k2"`, executable `swkotor2.exe`; for the Steam
  Aspyr binary prefer `ghidra_program="/TSL/k2_win_steam_aspyr_swkotor2.exe"`
  when analyzing a known Steam-session crash.

Runtime crash addresses should be converted as:

- Find the crashing module and module offset from the live log.
- For `swkotor.exe` and `swkotor2.exe`, add the offset to the static image base
  `0x00400000`.
- Use the resulting `ghidra_address` with `kotor_decompile_function`,
  `kotor_data_flow`, `kotor_call_graph`, or `kotor_engine_script`.

## Standard Flow

1. Install or verify the target module/Override package in the game folder.
2. Run `kotor_dinput_hook_install` for the target game. Refuse to replace an
   existing non-GhostRigger `dinput8.dll` unless it is intentionally backed up
   with `force=True`.
3. Run `kotor_prepare_save_warp_test` with `require_dinput_hook=True`,
   `target_module` set to the module resref, and the correct `game`.
4. Start the logger before launch or while waiting for process start:
   `kotor_log_start(game="k1"|"k2", session_label="task-label",
   wait_for_process=True, asset_resrefs=[...])`.
5. Launch the game in windowed mode, load a normal save, then warp. If normal
   synthetic input is blocked by elevation or focus, use
   `kotor_dinput_hook_send(text="warp tst_light", open_console=True,
   press_enter=True)`. The hook supports shifted characters such as `_` through
   `key_combo`.
6. Capture visible evidence with `kotor_capture_window` or a manual screenshot.
7. Stop and analyze the log. If there was a crash, run `kotor_log_analyze` with
   `annotate_with_ghidra=True` and, when needed, an exact `ghidra_program`.
8. Record proof results in the task manifest and add the verification details
   to `CHANGES.md`.

## Map Studio Notes

For authored map proof, prefer a small module such as `tst_light` or `grdev01`
and verify:

- the `.mod` is installed in the correct game's `Modules` folder,
- `EnableCheats=1` is set in `swkotor.ini` or `swkotor2.ini`,
- `AllowWindowedMode=1` and `FullScreen=0` are set for reliable capture,
- `currentgame/<module>.mod` is not stale before warping,
- the DirectInput hook log shows it loaded for the expected executable.

KOTOR1 and KOTOR2 are separate proof targets. Do not assume a module package
that loads in one game is valid in the other; inspect resources and stage a
game-specific package when format or dependency differences appear.

### `tst_light` Fullbright Lesson

- The KOTOR2 `tst_light` fullbright proof first failed during warp with
  `nvoglv32.dll` access violation / NVIDIA OpenGL out-of-memory events. The
  generated `currentgame/tst_light.mod` still contained 12 duplicate zero-radius
  `colorlight1` MDL light nodes with dynamic/shadow fields enabled.
- After neutralizing those MDL light fields while keeping the ARE fullbright
  values, the user confirmed the map loaded and the lighting was fixed. A later
  close while trying to take a screenshot produced different evidence
  (`0xE06D7363`, `KERNELBASE.dll`, stack including `DiscordHook.dll`) and should
  be treated as post-load overlay/runtime triage, not the original Map Studio
  warp crash.
- When using live logs to improve Map Studio, preserve both classes of evidence:
  the warp-load crash for export fixes, and any post-load overlay/driver closes
  as separate runtime-environment notes.
