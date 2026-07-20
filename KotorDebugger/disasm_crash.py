"""Disassemble a crash address straight out of the KOTOR exe (no Ghidra needed).

This is the tool that cracked the plcaa crash: given a module offset from the
crash log (e.g. 0x0044b3a8), it maps the virtual address to a file offset via
the PE section table and disassembles the faulting instruction and the function
around it with Capstone. It reads the exe on disk read-only.

Requires:  py -m pip install capstone pefile

Usage:
    py disasm_crash.py --exe "<path to swkotor2.exe>" --addr 0x0044b3a8
    py disasm_crash.py --exe "<...swkotor.exe>"  --addr 0x0044b3a8 --func
    py disasm_crash.py --exe "<...>" --addr 0x0044b3a8 --addr 0x0046e9c2

--addr takes the ABSOLUTE virtual address (image base 0x400000 + module offset).
Crash logs print both; either "address_hex" or base+offset works.
"""
from __future__ import annotations

import argparse
import sys

try:
    import pefile
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
except ImportError:
    print("Missing dependency. Run:  py -m pip install capstone pefile", file=sys.stderr)
    raise SystemExit(2)


def _sections(pe):
    base = pe.OPTIONAL_HEADER.ImageBase
    out = []
    for s in pe.sections:
        va0 = base + s.VirtualAddress
        va1 = va0 + max(s.Misc_VirtualSize, s.SizeOfRawData)
        out.append((s.Name.rstrip(b"\x00").decode("latin-1"), va0, va1, s.PointerToRawData))
    return base, out


def _off(sections, va):
    for _name, va0, va1, fo in sections:
        if va0 <= va < va1:
            return fo + (va - va0)
    return None


def _func_start(data, sections, va, back=0x800):
    """Scan backwards for a 'push ebp; mov ebp,esp' (55 8B EC) prologue."""
    o = _off(sections, va)
    if o is None:
        return va
    for i in range(o - 1, max(0, o - back), -1):
        if data[i] == 0x55 and data[i + 1] == 0x8B and data[i + 2] == 0xEC and data[i - 1] in (0xC3, 0xCC, 0x90):
            return va - (o - i)
    return va - 48


def disasm(exe, addr, before, count, whole_func):
    pe = pefile.PE(exe, fast_load=True)
    base, sections = _sections(pe)
    data = pe.__data__
    md = Cs(CS_ARCH_X86, CS_MODE_32)

    start = _func_start(data, sections, addr) if whole_func else addr - before
    o = _off(sections, start)
    if o is None:
        print(f"  {hex(addr)}: not inside any PE section (image base {hex(base)})")
        return
    span = (addr - start) + (count * 8 if whole_func else count * 8)
    code = data[o:o + max(span, count * 8) + 32]
    label = "FUNCTION" if whole_func else "WINDOW"
    print(f"\n===== {label} around {hex(addr)}  (module offset {hex(addr - base)}, file offset {hex(o)}) =====")
    printed = 0
    for insn in md.disasm(code, start):
        mark = "   <<<< CRASH / target" if insn.address == addr else ""
        print(f"  {hex(insn.address)}: {insn.mnemonic:8} {insn.op_str}{mark}")
        printed += 1
        if not whole_func and printed >= count and insn.address >= addr:
            break
        if whole_func and (insn.mnemonic == "ret" or insn.mnemonic.startswith("ret")) and insn.address > addr:
            break
        if printed > 400:
            break


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", required=True, help="Path to swkotor.exe / swkotor2.exe")
    ap.add_argument("--addr", action="append", required=True,
                    help="Absolute VA to disassemble (repeatable), e.g. 0x0044b3a8")
    ap.add_argument("--before", type=int, default=48, help="Bytes of context before the address (window mode)")
    ap.add_argument("--count", type=int, default=30, help="Instructions to print (window mode)")
    ap.add_argument("--func", action="store_true", help="Disassemble the whole enclosing function instead of a window")
    args = ap.parse_args(argv)

    for addr_str in args.addr:
        addr = int(addr_str, 16) if addr_str.lower().startswith("0x") else int(addr_str)
        disasm(args.exe, addr, args.before, args.count, args.func)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
