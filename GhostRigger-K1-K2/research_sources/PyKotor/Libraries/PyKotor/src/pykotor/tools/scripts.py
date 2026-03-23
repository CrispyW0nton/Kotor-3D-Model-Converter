"""Script utility functions for NCS bytecode manipulation.

This module provides reusable, abstract functions for decompiling, disassembling,
and working with NCS (NWScript Compiled Script) bytecode. These functions are
tool-agnostic and can be used by any application that needs to work with scripts.

References:
----------
        Original BioWare engine binaries (from swkotor.exe, swkotor2.exe)
        Original BioWare engine binaries


"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykotor.resource.formats.ncs.ncs_auto import decompile_ncs, read_ncs

if TYPE_CHECKING:
    from pathlib import Path

    from pykotor.common.misc import Game
    from pykotor.common.script import ScriptConstant, ScriptFunction
    from pykotor.resource.formats.ncs.ncs_data import NCS


def _write_text_if_requested(output_path: Path | None, text: str) -> None:
    """Write text output to disk when an output path is provided."""
    if output_path:
        output_path.write_text(text, encoding="utf-8")


def _instruction_offset(index: int, instruction: object) -> int:
    """Return a stable instruction offset, falling back to 4-byte indexing."""
    offset = getattr(instruction, "offset", -1)
    if isinstance(offset, int) and offset >= 0:
        return offset
    return index * 4


def decompile_ncs_to_nss(
    ncs_path: Path,
    output_path: Path | None = None,
    *,
    game: Game,
    functions: list[ScriptFunction] | None = None,
    constants: list[ScriptConstant] | None = None,
) -> str:
    """Decompile NCS bytecode to NSS source code.

    Args:
    ----
        ncs_path: Path to the input NCS file
        output_path: Optional path to write output NSS file (if None, returns source string)
        game: Game version (K1 or TSL) for function/constant definitions
        functions: Optional custom function definitions
        constants: Optional custom constant definitions

    Returns:
    -------
        Decompiled NSS source code as string

    References:
    ----------
        Original BioWare engine binaries (from swkotor.exe, swkotor2.exe)
        Original BioWare engine binaries


    """
    ncs = read_ncs(ncs_path)
    source = decompile_ncs(ncs, game, functions, constants)

    _write_text_if_requested(output_path, source)

    return source


def disassemble_ncs(
    ncs_path: Path,
    output_path: Path | None = None,
    *,
    game: Game | None = None,
    pretty: bool = True,
) -> str:
    """Disassemble NCS bytecode to human-readable assembly text.

    Args:
    ----
        ncs_path: Path to the input NCS file
        output_path: Optional path to write output disassembly file
        game: Optional game version for better function name resolution
        pretty: Whether to format output with indentation and comments

    Returns:
    -------
        Disassembly text as string

    References:
    ----------
        Original BioWare engine binaries (from swkotor.exe, swkotor2.exe)
        Original BioWare engine binaries


    """
    ncs: NCS = read_ncs(ncs_path)

    lines: list[str] = []
    lines.append("; NCS Disassembly")
    lines.append(f"; Instructions: {len(ncs.instructions)}")
    lines.append("")

    for i, instruction in enumerate(ncs.instructions):
        instruction_str = str(instruction)

        if pretty:
            lines.append(f"{_instruction_offset(i, instruction):08X}: {instruction_str}")
        else:
            lines.append(instruction_str)

    result = "\n".join(lines)

    _write_text_if_requested(output_path, result)

    return result


def ncs_to_text(
    ncs_path: Path,
    output_path: Path | None = None,
    *,
    mode: str = "decompile",  # "decompile" or "disassemble"
    game: Game | None = None,
) -> str:
    """Convert NCS bytecode to text representation (decompile or disassemble).

    Args:
    ----
        ncs_path: Path to the input NCS file
        output_path: Optional path to write output text file
        mode: "decompile" for NSS source code, "disassemble" for assembly listing
        game: Game version (required for decompile mode)

    Returns:
    -------
        Text representation as string

    Raises:
    ------
        ValueError: If mode is invalid or game is None in decompile mode
    """
    if mode == "decompile":
        if game is None:
            msg = "Game version is required for decompilation mode"
            raise ValueError(msg)
        return decompile_ncs_to_nss(ncs_path, output_path, game=game)
    if mode == "disassemble":
        return disassemble_ncs(ncs_path, output_path, game=game)

    msg = f"Invalid mode: {mode!r}. Must be 'decompile' or 'disassemble'"
    raise ValueError(msg)
