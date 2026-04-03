"""Utility command functions for file operations, validation, and analysis.

This module provides reusable, abstract functions for common utility operations
like diff, grep, stats, validate, and merge. These functions are tool-agnostic
and can be used by any application that needs these utilities.

References:
----------
        Based on swkotor.exe resource formats:
        - CResGFF::CreateGFFFile @ 0x00411260 - Creates new GFF file
        - CResGFF::WriteGFFFile @ 0x00413030 - Writes GFF data to file
        - CTlkTable::AddFile @ 0x0041d920 - Adds TLK file to table
        - Load2DArray @ 0x004143b0 - Loads 2DA array data
        Tools/diff operations/ - File diffing implementation
        Libraries/PyKotor/src/pykotor/tslpatcher/diff/ - Structured diff engine

"""

from __future__ import annotations

import difflib

from typing import TYPE_CHECKING, Callable

from pykotor.resource.formats.gff.gff_auto import read_gff
from pykotor.resource.formats.gff.gff_data import GFFFieldType, GFFList, GFFStruct
from pykotor.resource.formats.tlk.tlk_auto import read_tlk
from pykotor.resource.formats.twoda.twoda_auto import read_2da

if TYPE_CHECKING:
    from pathlib import Path

    from pykotor.resource.formats.gff.gff_data import GFF


_GFF_SUFFIXES: tuple[str, ...] = (".gff", ".utc", ".uti", ".dlg", ".are", ".git", ".ifo")


def _write_output_if_requested(output_path: Path | None, content: str) -> None:
    if output_path:
        output_path.write_text(content, encoding="utf-8")


def _diff_structured_files(
    file1_path: Path,
    file2_path: Path,
    output_path: Path | None,
    context_lines: int,
    reader: Callable[[Path], object],
    to_text: Callable[[object], str],
) -> str:
    """Diff two structured resources by converting parsed objects to text."""
    try:
        object1 = reader(file1_path)
        object2 = reader(file2_path)

        text1 = to_text(object1)
        text2 = to_text(object2)

        diff_lines = list(
            difflib.unified_diff(
                text1.splitlines(keepends=True),
                text2.splitlines(keepends=True),
                fromfile=str(file1_path),
                tofile=str(file2_path),
                lineterm="",
                n=context_lines,
            ),
        )

        result = "".join(diff_lines)
        _write_output_if_requested(output_path, result)
        return result
    except Exception:
        return _diff_binary_files(file1_path, file2_path, output_path, context_lines)


def _grep_in_structured_file(
    file_path: Path,
    pattern: str,
    case_sensitive: bool,
    reader: Callable[[Path], object],
    to_text: Callable[[object], str],
) -> list[tuple[int, str]]:
    """Search text-converted structured resources (GFF/2DA/TLK)."""
    try:
        parsed = reader(file_path)
        text = to_text(parsed)
        return _grep_in_text_content(text, pattern, case_sensitive)
    except Exception:
        return []


def _update_gff_stats(file_path: Path, stats: dict[str, int | str]) -> None:
    gff = read_gff(file_path)
    stats["type"] = "GFF"
    stats["field_count"] = len(gff.root)


def _update_2da_stats(file_path: Path, stats: dict[str, int | str]) -> None:
    twoda = read_2da(file_path)
    stats["type"] = "2DA"
    stats["row_count"] = len(twoda)
    stats["column_count"] = len(twoda.get_headers()) if twoda else 0


def _update_tlk_stats(file_path: Path, stats: dict[str, int | str]) -> None:
    tlk = read_tlk(file_path)
    stats["type"] = "TLK"
    stats["string_count"] = len(tlk)


def diff_files(
    file1_path: Path,
    file2_path: Path,
    *,
    output_path: Path | None = None,
    context_lines: int = 3,
) -> str:
    """Compare two files and return a unified diff.

    Supports GFF, 2DA, TLK files with structured comparison.

    Args:
    ----
        file1_path: Path to first file
        file2_path: Path to second file
        output_path: Optional path to write diff output
        context_lines: Number of context lines in diff output

    Returns:
    -------
        Unified diff text as string

    References:
    ----------
        Based on swkotor.exe GFF structure:
        - CResGFF::CreateGFFFile @ 0x00411260 - Creates GFF file structure
        - CResGFF::WriteGFFFile @ 0x00413030 - Writes GFF data to file
        Tools/diff operations/src/kotordiff/differ.py
        Libraries/PyKotor/src/pykotor/tslpatcher/diff/structured.py

    """
    suffix = file1_path.suffix.lower()

    # Structured comparison for known formats
    if suffix in _GFF_SUFFIXES:
        return _diff_gff_files(file1_path, file2_path, output_path, context_lines)
    if suffix == ".2da":
        return _diff_2da_files(file1_path, file2_path, output_path, context_lines)
    if suffix == ".tlk":
        return _diff_tlk_files(file1_path, file2_path, output_path, context_lines)

    # Fallback to binary/text comparison
    return _diff_binary_files(file1_path, file2_path, output_path, context_lines)


def _diff_gff_files(
    file1_path: Path,
    file2_path: Path,
    output_path: Path | None,
    context_lines: int,
) -> str:
    """Compare two GFF files."""
    return _diff_structured_files(file1_path, file2_path, output_path, context_lines, read_gff, _gff_to_text)


def _diff_2da_files(
    file1_path: Path,
    file2_path: Path,
    output_path: Path | None,
    context_lines: int,
) -> str:
    """Compare two 2DA files."""
    return _diff_structured_files(file1_path, file2_path, output_path, context_lines, read_2da, _2da_to_text)


def _diff_tlk_files(
    file1_path: Path,
    file2_path: Path,
    output_path: Path | None,
    context_lines: int,
) -> str:
    """Compare two TLK files."""
    return _diff_structured_files(file1_path, file2_path, output_path, context_lines, read_tlk, _tlk_to_text)


def _diff_binary_files(
    file1_path: Path,
    file2_path: Path,
    output_path: Path | None,
    context_lines: int,
) -> str:
    """Fallback binary comparison."""
    data1 = file1_path.read_bytes()
    data2 = file2_path.read_bytes()

    if data1 == data2:
        result = f"Files are identical: {file1_path.name} and {file2_path.name}\n"
    else:
        result = f"Files differ:\n  {file1_path.name}: {len(data1)} bytes\n  {file2_path.name}: {len(data2)} bytes\n"

    _write_output_if_requested(output_path, result)

    return result


def grep_in_file(
    file_path: Path,
    pattern: str,
    *,
    case_sensitive: bool = False,
) -> list[tuple[int, str]]:
    """Search for a pattern in a file and return matching lines with line numbers.

    Supports text files and structured formats (GFF, 2DA, TLK).

    Args:
    ----
        file_path: Path to file to search
        pattern: Search pattern (regex or plain text)
        case_sensitive: Whether search is case-sensitive

    Returns:
    -------
        List of (line_number, line_text) tuples

    References:
    ----------
        Based on swkotor.exe GFF structure:
        - CResGFF::CreateGFFFile @ 0x00411260 - Creates GFF file structure
        - CResGFF::WriteGFFFile @ 0x00413030 - Writes GFF data to file


    """
    suffix = file_path.suffix.lower()

    # Handle structured formats
    if suffix in _GFF_SUFFIXES:
        return _grep_in_gff(file_path, pattern, case_sensitive)
    if suffix == ".2da":
        return _grep_in_2da(file_path, pattern, case_sensitive)
    if suffix == ".tlk":
        return _grep_in_tlk(file_path, pattern, case_sensitive)

    # Fallback to text file search
    return _grep_in_text_file(file_path, pattern, case_sensitive)


def _grep_in_text_file(
    file_path: Path,
    pattern: str,
    case_sensitive: bool,
) -> list[tuple[int, str]]:
    """Search in a plain text file."""
    matches: list[tuple[int, str]] = []
    text = pattern if case_sensitive else pattern.lower()

    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                search_line = line if case_sensitive else line.lower()
                if text in search_line:
                    matches.append((line_num, line.rstrip()))
    except UnicodeDecodeError:
        # Try binary search
        data = file_path.read_bytes()
        search_bytes = pattern.encode("utf-8") if case_sensitive else pattern.lower().encode("utf-8")
        if search_bytes in data:
            matches.append((0, f"Pattern found in binary file: {file_path.name}"))

    return matches


def _grep_in_gff(
    file_path: Path,
    pattern: str,
    case_sensitive: bool,
) -> list[tuple[int, str]]:
    """Search in GFF file by converting to text representation."""
    return _grep_in_structured_file(file_path, pattern, case_sensitive, read_gff, _gff_to_text)


def _grep_in_2da(
    file_path: Path,
    pattern: str,
    case_sensitive: bool,
) -> list[tuple[int, str]]:
    """Search in 2DA file."""
    return _grep_in_structured_file(file_path, pattern, case_sensitive, read_2da, _2da_to_text)


def _grep_in_tlk(
    file_path: Path,
    pattern: str,
    case_sensitive: bool,
) -> list[tuple[int, str]]:
    """Search in TLK file."""
    return _grep_in_structured_file(file_path, pattern, case_sensitive, read_tlk, _tlk_to_text)


def _grep_in_text_content(
    content: str,
    pattern: str,
    case_sensitive: bool,
) -> list[tuple[int, str]]:
    """Search pattern in text content."""
    matches: list[tuple[int, str]] = []
    search_text = pattern if case_sensitive else pattern.lower()

    for line_num, line in enumerate(content.splitlines(), 1):
        search_line = line if case_sensitive else line.lower()
        if search_text in search_line:
            matches.append((line_num, line))

    return matches


def get_file_stats(file_path: Path) -> dict[str, int | str]:
    """Get statistics about a file.

    Args:
    ----
        file_path: Path to file to analyze

    Returns:
    -------
        Dictionary with file statistics

    References:
    ----------
        Based on swkotor.exe GFF structure:
        - CResGFF::CreateGFFFile @ 0x00411260 - Creates GFF file structure
        - CResGFF::WriteGFFFile @ 0x00413030 - Writes GFF data to file


    """
    stats: dict[str, int | str] = {
        "path": str(file_path),
        "size": file_path.stat().st_size if file_path.exists() else 0,
        "exists": file_path.exists(),
    }

    if not file_path.exists():
        return stats

    suffix = file_path.suffix.lower()

    # Add format-specific statistics
    try:
        if suffix in _GFF_SUFFIXES:
            _update_gff_stats(file_path, stats)
        elif suffix == ".2da":
            _update_2da_stats(file_path, stats)
        elif suffix == ".tlk":
            _update_tlk_stats(file_path, stats)
    except Exception:
        pass

    return stats


def validate_file(file_path: Path) -> tuple[bool, str]:
    """Validate a file's format and structure.

    Args:
    ----
        file_path: Path to file to validate

    Returns:
    -------
        Tuple of (is_valid, error_message)

    References:
    ----------
        Based on swkotor.exe GFF structure:
        - CResGFF::CreateGFFFile @ 0x00411260 - Creates GFF file structure
        - CResGFF::WriteGFFFile @ 0x00413030 - Writes GFF data to file


    """
    if not file_path.exists():
        return False, f"File does not exist: {file_path}"

    suffix = file_path.suffix.lower()

    try:
        if suffix in (".gff", ".utc", ".uti", ".dlg", ".are", ".git", ".ifo"):
            read_gff(file_path)
            return True, "Valid GFF file"
        if suffix == ".2da":
            read_2da(file_path)
            return True, "Valid 2DA file"
        if suffix == ".tlk":
            read_tlk(file_path)
            return True, "Valid TLK file"
        if suffix in (".erf", ".mod", ".sav"):
            from pykotor.resource.formats.erf.erf_auto import read_erf

            read_erf(file_path)
            return True, "Valid ERF file"
        if suffix == ".rim":
            from pykotor.resource.formats.rim.rim_auto import read_rim

            read_rim(file_path)
            return True, "Valid RIM file"
        if suffix == ".tpc":
            from pykotor.resource.formats.tpc.tpc_auto import read_tpc

            read_tpc(file_path)
            return True, "Valid TPC file"

        return True, "File exists (format validation not implemented)"
    except Exception as e:
        return False, f"Validation failed: {str(e)}"


# Helper functions for text conversion
def _gff_to_text(gff: GFF) -> str:
    """Convert GFF to text representation for diff/grep."""
    lines: list[str] = []
    _gff_struct_to_text(gff.root, lines, "")
    return "\n".join(lines)


def _gff_struct_to_text(struct: GFFStruct, lines: list[str], indent: str) -> None:
    """Recursively convert GFF struct to text."""
    for label, field_type, value in struct:
        field_type_name = field_type.name
        value_str = str(value)
        lines.append(f"{indent}{label} ({field_type_name}): {value_str}")

        if field_type == GFFFieldType.Struct and isinstance(value, GFFStruct):
            _gff_struct_to_text(value, lines, indent + "  ")
        elif field_type == GFFFieldType.List and isinstance(value, GFFList):
            for i, item in enumerate(value):
                lines.append(f"{indent}  [{i}]")
                if isinstance(item, GFFStruct):
                    _gff_struct_to_text(item, lines, indent + "    ")


def _2da_to_text(twoda) -> str:
    """Convert 2DA to text representation."""
    lines: list[str] = []
    if twoda:
        headers = twoda.get_headers()
        lines.append("\t".join(headers))
        for row in twoda:
            values = [str(row.get(header, "")) for header in headers]
            lines.append("\t".join(values))
    return "\n".join(lines)


def _tlk_to_text(tlk) -> str:
    """Convert TLK to text representation."""
    lines: list[str] = []
    for i, entry in enumerate(tlk):
        text = entry.text if hasattr(entry, "text") else str(entry)
        lines.append(f"{i}: {text}")
    return "\n".join(lines)
