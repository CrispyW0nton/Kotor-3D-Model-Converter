# KOTOR Ghidra Skill (Odyssey engine validation)

How agents query the OpenKotOR AgentDecompile Ghidra server to validate
Map Studio output against the real engine. Written 2026-07-08.

## Access

Client: `scripts/agdec_query.py` (raw MCP-over-HTTP JSON-RPC; headers are in
the script). Always run with `PYTHONIOENCODING=utf-8` (responses contain
Unicode that breaks cp1252).

```
py -3.14 scripts/agdec_query.py tools
py -3.14 scripts/agdec_query.py call open '{"path":"/TSL/k2_win_steam_aspyr_swkotor2.exe"}'
py -3.14 scripts/agdec_query.py call get-function '{"program":"/TSL/...","address":"0x0044b350"}'
py -3.14 scripts/agdec_query.py call get-references '{"program":"/TSL/...","address":"0x0046e9b0","direction":"to"}'
```

Programs live in the shared repository `Odyssey` (24 programs; K2 Steam/Aspyr
is `/TSL/k2_win_steam_aspyr_swkotor2.exe`; base 0x400000, so
`address = 0x400000 + WER/logger module offset`).

## What works / current limits

- `get-function`: signature + full **disassembly** always; the C
  **decompilation is currently unavailable** on the server ("DecompInterface
  failed to launch") — read the assembly.
- `get-references` direction "to": callers. Direction "from" returned
  nothing in our tests — climb call chains with repeated "to".
- `search-*` tools exist (`search-strings`, `search-symbols`,
  `search-constants`); tool names are exact — no aliases.
- The live-log analyzer's `annotate_with_ghidra=True` resolves crash
  offsets to function names automatically when the address has a defined
  function; undefined regions come back "None" — query `get-function` with
  the address anyway (it finds the containing `FUN_...`).

## Reading disassembly for crash triage (worked example)

Crash at 0x0044b3a8, read address 132 (=0x84):

```
0044b3a0  MOV ECX,[ECX + 0x8]     ; handle->id
0044b3a3  CALL 0x00452860         ; resolver: id -> object (returned NULL)
0044b3a8  MOV EDX,[EAX + 0x84]    ; NULL->field_0x84  <- the AV
```

Pattern: tiny absolute read address = NULL + field offset; the instruction
at the crash names the field; the CALL right before names the resolver.
Callers (get-references "to") give the subsystem: here
`FUN_0046e9b0(list, char* name)` — a find-by-name loop (per-item: resolve
handle, name at +0xb8, CRT stricmp at 0x0091d780).

## When to use engine data vs. vanilla files

Prefer VANILLA GAME FILES for format contracts (they are what the engine
provably accepts): e.g. GIT StoreList struct 11 uses `ResRef` +
XPosition/YPosition/ZPosition (dumped from 202TEL), LYT doorhook lines are
`room name 0 x y z qw qx qy qz` (101PER). Use Ghidra when the question is
*behavioral* (what does the engine DO with a field, which lookup crashed,
is a field optional) — and for K1-vs-K2 compatibility differences.

## PIE reconstruction contract

Treat the retail Odyssey runtime as the behavioral specification for every
Map Studio Play-in-Editor gameplay system. Before expanding focus selection,
the action queue, combat rounds, dialogue traversal, cameras, audio, inventory,
doors, creatures, or HUD behavior:

1. Recover the relevant control flow and data contracts from the analyzed K1
   and/or K2 executable when the local evidence is available.
2. Cross-check resource fields and presentation assets against unmodified game
   files that the retail engine accepts.
3. Keep recovered engine behavior, file-format evidence, and editor inference
   separately labeled in code, tests, proof receipts, and change notes.
4. Use a bounded approximation only when exact behavior is still unknown, and
   expose that limitation rather than presenting it as KOTOR parity.
5. Preserve manual retail-game proof as the final acceptance test; PIE evidence
   is never a substitute for a K1/K2 run.

The future GUI Editor is a separate main-workbench product surface. PIE may
consume the same resource/preview contracts, but Map Studio must not own the GUI
authoring implementation.

Also available: the local ZBrush Ghidra project at
`C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\Ghidra\projects\active\ZBrush`
for studying how ZModeler's modeling tools behave (educational reference for
GModeler bevel/extrude semantics).
