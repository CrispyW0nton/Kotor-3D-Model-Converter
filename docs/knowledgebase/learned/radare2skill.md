# Radare2 Binary Analysis Skill

Use this skill when Radare2 is the most efficient way to triage, navigate,
annotate, script, debug, or propose a byte patch for a binary involved in Ghost
Studio development. Pair it with `binaryanalysisskill.md`; this file is the
tool-specific operating guide.

## Source and Version Policy

Study source:

- Soren Veyron, *Radare2 in Action: A Practical Guide to Open-Source Binary
  Analysis*, supplied locally for this study. The analyzed PDF is 272 pages and
  has SHA-256
  `6695ea17817ba4a478b1aeea578798ebb7c610bc7dff44eb873c6c8a8f215728`.

The book is useful for orientation, command families, automation, debugging,
and workflow ideas. Radare2 changes quickly and some book examples are
informal. Exact syntax must be checked against the installed binary's `?` help
and the current official Radare2 book before it is placed in a script.

Current authoritative references:

- official repository and first steps: https://github.com/radareorg/radare2
- official book: https://book.rada.re/
- analysis commands: https://book.rada.re/analysis/code_analysis.html
- debugger: https://book.rada.re/debugger/intro.html
- debugger memory maps: https://book.rada.re/debugger/memory_maps.html
- binary diffing: https://book.rada.re/tools/radiff2/binary_diffing.html
- write/cache behavior: https://book.rada.re/commandline/write.html
- ESIL: https://book.rada.re/emulation/intro.html
- projects and their limitations: https://book.rada.re/projects/usage.html

As of 2026-07-15, `r2`, `rabin2`, `rahash2`, and `rasm2` are not installed on
this workstation's normal `PATH`. Do not claim Radare2 verification until this
changes. Ghidra and local `pefile` + Capstone remain the available fallbacks.

## Book Examples That Require Correction

The study found several examples that must not be copied into Ghost Studio
automation without correction:

- current `axt` means references **to** an address; `axf` means references
  **from** an address;
- current `dmp` changes memory-page permissions; it is not a memory display or
  dump command. Use bounded print commands for inspection and check `dmd` for
  the installed version's map-dump behavior;
- current project management uses the `P` family; `Po` is legacy syntax;
- a file opened with write access can be changed immediately. There is no
  universal GUI-style final Save step;
- grepping a function list for a numeric constant does not find all code that
  accesses that value;
- `aaa` is heuristic analysis, not proof of complete or correct function
  discovery.

These corrections were cross-checked against the current official Radare2
book. Keep them in the skill even if a future version changes syntax, because
they illustrate why version/help capture is mandatory.

## Installation and Session Preflight

Before using commands from this skill:

1. Resolve the executable with `Get-Command r2`.
2. Record `r2 -v` and the tool path.
3. Hash the input file and work from a copy or read-only source.
4. Ask the installed version for command help (`?`, `i?`, `a?`, `ax?`, `d?`,
   `w?`, `wc?`) before automating a command family.
5. Prefer JSON-producing commands for scripts and evidence.

Do not install or upgrade Radare2 as a hidden side effect of an analysis task.
Record the chosen distribution/version because parser and project behavior can
change between releases.

## Read-Only by Default

Open ordinary analysis sessions without write mode:

```text
r2 <binary>
```

Do not start with `-w`, `oo+`, or a direct write command. Radare2 supports both
virtual-address and physical/file-offset views; record which one is active
before interpreting or proposing a patch.

For a new target, capture at least:

- file information and architecture;
- entry points;
- sections/maps and their file/virtual spans;
- imports, exports, symbols, and relocations where present;
- strings and string encodings;
- initial analysis depth and any warnings;
- SHA-256 of the exact input.

Use the current version's JSON variants (`...j`) when automation consumes the
result. Text meant for humans is not a stable parser API.

For a raw or corrupt container, a typical version-checked starting shape is:

```text
r2 -n suspect.mod
e io.va=false
s 0
px 160
izz
```

Useful bounded operations include `px 64 @ <file_offset>`,
`p8 32 @ <file_offset>`, byte search through `/x`, literal search through `/`,
and evidence labels through `f`. Verify each command with local help. The `@`
form executes at a temporary seek, which helps preserve a readable transcript.

## Core Navigation Model

Radare2 commands operate at the current seek. Keep a short session transcript
that records every important seek and address-space translation.

Common command families, subject to installed-version help:

- `s`: seek to an address, flag, or relative position;
- `px` / `p8`: display bytes as a hexdump or hexpairs;
- `pd`: disassemble a bounded number of instructions;
- `pdf`: print the current function disassembly;
- `agf`: render the current function graph;
- `i*`: inspect binary metadata, sections, symbols, imports, exports, strings,
  and entry points;
- `aa` / `aaa`: progressively analyze referenced code and data;
- `afl`: list inferred functions (`aflj` for structured output);
- `axt`: references **to** an address;
- `axf`: references **from** an address;
- `CC`: comments and annotations;
- `afn`: rename an inferred function after recording its original address.

Auto-analysis is an inference. Record the level used, keep raw bytes, and
manually correct function/basic-block boundaries only when independent evidence
supports the correction.

## Triage Workflow for PE Executables

For `swkotor.exe`, `swkotor2.exe`, or a native Ghost Studio binary:

1. Record file hash, PE timestamp, image base, machine type, and section table.
2. Map the reported runtime module offset to an RVA and section/file offset.
3. Seek to the exact fault address and capture surrounding bytes and bounded
   disassembly.
4. Inspect xrefs to relevant strings, constants, imports, and call targets.
5. Build the smallest control-flow graph that contains the fault.
6. Annotate inferred arguments and structures without replacing the raw
   evidence.
7. Compare the same path using a known successful vanilla resource.

If Radare2 and Ghidra disagree about a boundary or target, inspect the machine
bytes with a third focused decoder such as Capstone. Do not settle the question
by choosing the prettier pseudocode.

## Raw Data and KOTOR Containers

`MOD`, `ERF`, `RIM`, `GFF`, `MDL`, `MDX`, and `WOK` are data formats, not CPU
code. Do not run program-wide auto-analysis over them and interpret accidental
instructions as structure.

Use Radare2 for:

- bounded hex/ASCII views;
- signature and byte-pattern searches;
- physical offset navigation;
- entropy or region comparison where supported;
- explicit structure layouts after checking the installed formatter syntax;
- exporting exact candidate spans for an independent parser.

The authoritative reconstruction still belongs in Ghost Studio's format/IO
reader or a task-specific forensic reader. See `binaryanalysisskill.md` for
table validation and carving rules.

## Structured Evidence and Automation

Use `r2pipe` only after the equivalent commands have been verified manually
against the installed version.

A safe automation pattern is:

1. open input read-only;
2. collect version, file hash, metadata, sections, strings, functions, and
   xrefs as JSON;
3. keep command stderr/warnings;
4. bound every read and analysis range;
5. write one immutable JSON report per input hash;
6. close without write mode.

Do not parse colored console tables with regular expressions when a JSON form
exists. Do not use maximum analysis depth by reflex; start with the smallest
analysis that answers the question and escalate deliberately.

Radare2 project files can preserve annotations, but the official documentation
warns that project behavior has historically been unstable. Treat an exported
project as a convenience, not the sole evidence. Preserve hashes, JSON reports,
comments/flags scripts, and a plain command transcript separately.

## Binary Diffing

When `radiff2` is installed, capture its version and use it as a byte-difference
aid, not a semantic verdict. Version-check the current options before using
common forms such as:

```text
radiff2 original.mod recovered.mod
radiff2 -s original.mod recovered.mod
radiff2 -c original.mod recovered.mod
```

Whole-file similarity can be low after a valid container rebuild because
resource order and offsets changed. Compare header fields, directory geometry,
payload identities/hashes, and engine records separately. Function/graph diff
modes apply to executable code, not Odyssey data containers.

## Debugging Workflow

Dynamic debugging complements static analysis; it does not replace it.

Typical command families, verified through `d?` first:

- `r2 -d <program-or-pid>`: start or attach;
- `dm`: process memory maps;
- `dr`: registers;
- `db`: breakpoints;
- `dcu <address-or-flag>`: continue until a target;
- `ds`: single-step/step variants;
- `dc`: continue;
- debugger trace commands under `dt` where supported;
- the current version's detach/close command after inspecting `d?`.

Do not confuse current debugger memory commands: `dm` lists maps, `dmj`
provides structured map data, `dmm` lists loaded modules, and `dmp` changes
permissions. Inspect the installed `dm?` before relying on `dmd` or another
dump variant.

For KOTOR, prefer the existing KotorMCP live logger for reproducible crash
capture. Radare2 may then investigate an exact address or trace a bounded loader
path. Never attach two debuggers to the same process simultaneously.

Dynamic evidence covers only the executed path and input. Record module load
bases, ASLR state, game executable hash, target module hash, save/warp scenario,
and breakpoint conditions.

## Patch-Proposal Workflow

Radare2 can write bytes, assemble instructions, and manage an IO write cache.
Ghost Studio policy is stricter than tool capability:

1. Duplicate the target and record both hashes.
2. Open the duplicate read-only first and locate the exact physical span.
3. State the patch hypothesis and expected behavior.
4. If interactive patching is justified, enable IO cache before touching disk.
5. Use `wc?` for the installed version, list cached changes, export a diff, and
   prove undo/reset behavior.
6. Commit only a same-length, bounded patch unless a format-aware rebuild owns
   every relocated reference.
7. Rehash, independently parse, structurally compare, and repeat runtime proof.

Never use insertion/extension commands on an Odyssey container or room model
as a shortcut. A general binary editor cannot update unknown engine pointers or
format tables safely.

## ESIL, Decompilation, and Emulation

ESIL and decompiler output can help answer bounded questions about register
effects, branch conditions, or a small function. They are approximate models.
Validate important conclusions against raw instructions and, when possible, a
real debugger state.

Do not use symbolic/emulated success as proof that an engine loader will accept
a resource. Emulation omits external state, undocumented engine objects, driver
behavior, and unmodeled instructions.

## Ghost Studio Escalation Order

Use the least powerful tool that establishes independent evidence:

1. format-aware Ghost Studio/PyKotor readers;
2. raw header/table validator and vanilla structural diff;
3. hexdump/search with PowerShell or a focused Python reader;
4. local `pefile` + Capstone for an exact PE address;
5. Ghidra for functions, cross-references, and data flow;
6. Radare2 for fast interactive navigation, structured scripting, or a second
   disassembler opinion;
7. bounded live debugging/instrumentation;
8. manual KOTOR runtime proof.

Do not use executable disassembly to manufacture missing module geometry. It
can reveal loader contracts, not recreate art that is absent from every source.

## Book Chapter Anchors

- chapter 1, pages 7-27: Radare2 scope and command philosophy;
- chapter 2, pages 28-46: seek/navigation, visual modes, and help-driven use;
- chapter 3, pages 47-69: formats, metadata, sections, strings, and symbols;
- chapter 4, pages 70-92: disassembly, functions, graphs, xrefs, annotations;
- chapter 5, pages 93-116: decompilation and reconstruction caveats;
- chapter 6, pages 117-136: debugging, breakpoints, registers, memory;
- chapter 7, pages 137-157: r2pipe and repeatable automation;
- chapter 8, pages 158-179: packed/obfuscated-binary triage;
- chapter 12, pages 249-272: plugins, forensics, and documentation.

Security/exploit examples from later chapters are outside normal Ghost Studio
module recovery scope. Use only the analysis and evidence-management concepts
needed for authorized local binaries.
