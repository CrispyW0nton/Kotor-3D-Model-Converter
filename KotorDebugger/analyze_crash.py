"""Summarise a KOTOR crash from a debugger session's events.jsonl.

The live debugger (kotor_debugger.py) writes one JSON object per line to
<session>/events.jsonl. This tool pulls out the fatal exception and prints:
  - the crash address (both absolute and swkotor.exe/swkotor2.exe module offset)
  - the exception code (e.g. 0xc0000005 ACCESS_VIOLATION)
  - the walked stack frames: each return-address module offset + the first
    4 pointer args, with any readable strings the debugger dereferenced.

The module offset is what you feed to disasm_crash.py or a Ghidra project.

Usage:
    py analyze_crash.py <session_dir_or_events.jsonl> [--all]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _iter_events(path: Path):
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _print_exception(event: dict, index: int) -> None:
    addr = event.get("address_hex", "?")
    off = event.get("frames", [{}])[0].get("module", {}).get("offset_hex") if event.get("frames") else None
    code = event.get("exception_code_hex", "?")
    name = event.get("exception_name", "")
    fc = event.get("first_chance")
    print(f"\n=== exception #{index}  {code} {name}  first_chance={fc} ===")
    print(f"  crash address : {addr}   (module offset {off or 'n/a'})")
    params = event.get("exception_parameters")
    if params:
        print(f"  parameters    : {params}   (param0: 0=read 1=write 8=DEP; param1: faulting VA)")
    frames = event.get("frames") or []
    if frames:
        print(f"  stack ({len(frames)} frames):")
        for depth, frame in enumerate(frames):
            mod = frame.get("module", {})
            moff = mod.get("offset_hex", "?")
            ret = frame.get("return_hex", "?")
            args = frame.get("args_hex", [])
            strs = [s for s in (frame.get("arg_strings") or []) if s and s.strip() and s.strip() != "!"]
            line = f"    [{depth}] off={moff} ret={ret} args={args}"
            if strs:
                line += f"  strings={strs}"
            print(line)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session", help="Session directory or a path to events.jsonl")
    ap.add_argument("--all", action="store_true", help="Show every exception, not just the fatal one")
    args = ap.parse_args(argv)

    target = Path(args.session)
    events_path = target if target.is_file() else target / "events.jsonl"
    if not events_path.exists():
        print(f"No events.jsonl at {events_path}", file=sys.stderr)
        return 1

    exceptions = [e for e in _iter_events(events_path) if e.get("event") == "exception"]
    if not exceptions:
        print(f"No exceptions recorded in {events_path}. The game did not crash while attached.")
        return 0

    fatal = [e for e in exceptions if not e.get("first_chance")]
    print(f"session: {events_path.parent.name}")
    print(f"exceptions recorded: {len(exceptions)}  (fatal: {len(fatal)})")

    if args.all:
        for i, e in enumerate(exceptions):
            _print_exception(e, i)
    else:
        chosen = fatal[-1] if fatal else exceptions[-1]
        _print_exception(chosen, exceptions.index(chosen))
        print("\n(Use --all to see first-chance exceptions too.)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
