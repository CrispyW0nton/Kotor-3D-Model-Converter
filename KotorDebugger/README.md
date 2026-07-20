# KotorDebugger

A standalone live crash debugger for **KOTOR 1 & 2** (`swkotor.exe` /
`swkotor2.exe`). It attaches to the running game as a Windows debugger, records
every exception (with a walked call stack and dereferenced string arguments) to
a log, and lets you disassemble the exact faulting instruction straight out of
the game exe — no Ghidra, no IDA, just Python.

This is the toolset that root-caused the KOTOR 2 custom-map crash to a single
wrong field in the model writer (`node+8`).

## What's in here

| File | What it does |
|------|--------------|
| `kotor_debugger.py` | The live debugger. Attaches to the game, prints a **live human-readable feed** to the console, and logs every event three ways per session: `live.log` (the readable feed), `events.jsonl` (full machine log), `summary.txt`. Pure stdlib `ctypes` — no install needed. |
| `analyze_crash.py`  | Reads a session's `events.jsonl` and prints the fatal crash: address, module offset, exception code, and the call stack with captured strings. |
| `disasm_crash.py`   | Disassembles a crash address directly from the game exe (maps virtual address → file offset via the PE section table, then Capstone). Needs `capstone` + `pefile`. |
| `debug_k1.bat` / `debug_k2.bat` | One-click: start a timestamped logging session that waits for the game, then run it and reproduce the crash. |

## Prerequisites

- **Windows** + **Python 3.9+** (the game is 32-bit; the debugger drives the
  Win32 debug API via `ctypes`, so any Python bitness works).
- The debugger must be able to attach: run your terminal **as the same user**
  that runs the game. (No admin needed for a normal Steam launch.)
- For `disasm_crash.py` only:
  ```
  py -m pip install capstone pefile
  ```

## How to capture a crash

For the K2 custom-animation/PLCaa workflow, double-click
`debug_k2_animation_patch.bat`. It starts the logger in the background, tags
`plcaa`, `c_drexlf`, and `kpm98_drx`, and writes a SHA-256 inventory of the
game-root runtime files and every loaded module. This is passive: it does not
install or replace `dinput8.dll`, `winmm.dll`, or any other mod-loader shim.

**1. Start a logging session that waits for the game:**

```
py kotor_debugger.py monitor --game k2 --wait-for-process
```

- `--game k1` or `--game k2`
- `--wait-for-process` makes it sit and attach the moment the game launches.
  (Or omit it and pass `--pid <PID>` to attach to an already-running game.)
- `--session-dir <folder>` chooses the output folder. **If you omit it, logs go
  to `KotorDebugger\sessions\<game>-<timestamp>\`** — the debugger prints the
  exact path at startup.
- `--duration-seconds N` caps the session length (default is generous).
- `--asset-resref plcaa` (repeatable) tags interesting resrefs so the log
  flags when the engine touches them.

**2. Launch KOTOR and reproduce the crash** (load a save, `warp <module>`, etc.).
The debugger attaches automatically and prints a **live feed** as things happen:

```
================================================================
 KotorDebugger  |  session: ...\sessions\k2-20260710-202855
 live view : ...\sessions\k2-20260710-202855\live.log   (open/tail to watch)
================================================================
[03:28:55] >> session started (game=k2) - waiting for swkotor2.exe to launch...
[03:29:10] .. found swkotor2.exe (pid 4812) - attaching debugger...
[03:29:10] ** attached and watching (37 modules). Reproduce the crash now.
[03:29:41]    [game] CModule::LoadArea plcaa
[03:29:41] XX  CRASH  0xc0000005 EXCEPTION_ACCESS_VIOLATION @ 0x0044b3a8  (module offset 0x4b3a8)  <- engine was near: ['plcaaa', 'plcaa']
```

- **You (the user)** just watch this window — the `XX CRASH` line tells you it
  crashed, where, and what the engine was doing.
- **An agent (headless)** can `tail -f <session>\live.log` for the same feed, or
  parse `events.jsonl` for full detail.

When the game crashes (or you close it / the duration elapses), the session
finalizes.

**3. Read the crash:**

```
py analyze_crash.py sessions\crash1
```

Example output (the real plcaa crash):

```
=== exception #5  0xc0000005 EXCEPTION_ACCESS_VIOLATION  first_chance=False ===
  crash address : 0x0044b3a8   (module offset 0x4b3a8)
  parameters    : [1, 16]   (param0: 0=read 1=write 8=DEP; param1: faulting VA)
  stack (6 frames):
    [0] off=0x0006e9c2 ret=0x0046e9c2 args=[...]  strings=['plcaaa']
    [1] off=0x0007044d ret=0x0047044d args=[...]  strings=['plcaaa']
    [2] off=0x00401ddd ret=0x00801ddd args=[...]  strings=['plcaa']
```

The **`strings=[...]`** are the payoff: the debugger dereferences each pointer
argument as text, so you see *what the engine was doing* — here it was building
`plcaa`+`"a"`="plcaaa" and looking it up.

## How to disassemble the crash

Take the crash address from step 3 and read the actual machine code:

```
py disasm_crash.py --exe "C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II\swkotor2.exe" --addr 0x0044b3a8 --func
```

- `--addr` is the **absolute** virtual address (image base `0x400000` + module
  offset). The analyzer prints both; either works.
- `--func` disassembles the whole enclosing function (finds the `push ebp` /
  `mov ebp,esp` prologue). Omit it for a small window around the address.
- Repeat `--addr` to disassemble several frames' return addresses at once.

Example (the faulting instruction):

```
  0x44b3a0: mov   ecx, dword ptr [ecx + 8]
  0x44b3a3: call  0x452860
  0x44b3a8: mov   edx, dword ptr [eax + 0x84]   <<<< CRASH / target
```

That told us `call 0x452860` returned NULL and `[eax+0x84]` faulted — the thread
that led to the `node+8` fix.

## The event log format

`<session>/events.jsonl` is one JSON object per line. The useful ones:

- `{"event":"exception", "address_hex":"0x0044b3a8", "exception_code_hex":"0xc0000005",
   "first_chance":false, "exception_parameters":[1,16], "frames":[...]}`
  - `first_chance:false` is the **fatal** one (the crash). First-chance
    exceptions are often handled and non-fatal.
  - each frame has `module.offset_hex` (offset into the exe/DLL), `return_hex`,
    `args_hex` (first 4 stack dwords), and `arg_strings` (those args read as text).
- `{"event":"load_dll", ...}` / `{"event":"output_debug_string", "text":"..."}` —
  module loads and the game's own `OutputDebugString` prints.

`<session>/summary.txt` and `summary.json` give the last exception at a glance.

## Notes / gotchas

- **Image base is `0x400000`.** Module offset `0x4b3a8` = absolute `0x4b3a8 + 0x400000` = `0x4044b3a8`… no: the exe loads at `0x400000`, so offset `0x4b3a8` = VA `0x44b3a8`. If a crash address is in a **loaded DLL** (e.g. a graphics driver), the module in that frame won't be `swkotor2.exe` — disassemble that DLL instead, or ignore it (driver-side crashes usually mean bad data reached the GPU, not an engine-logic bug).
- **Only the first-chance=false exception is the crash.** Games throw and handle
  first-chance exceptions all the time.
- The debugger runs **passively** — it logs and continues the game; it does not
  patch or freeze it. Closing your terminal detaches cleanly.
- Steam sometimes relaunches the game through a helper; `--wait-for-process`
  handles that by attaching to the real `swkotor*.exe` when it appears.
