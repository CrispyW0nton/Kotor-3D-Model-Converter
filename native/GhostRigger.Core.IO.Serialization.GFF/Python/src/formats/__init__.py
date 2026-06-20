"""
GhostRigger — Ghostworks Format Library
GFF V3.2 reader/writer, archive reader (BIF/ERF/KEY/RIM), and related utilities.

Matches the format spec from GHOSTWORKS_BLUEPRINT.md Section 4.
"""
from .gff_types import (
    GffFieldType, GffField, GffStruct, GffFile,
    LocString, ResRef,
)
from .gff_reader import GffReader, read_gff
from .gff_writer import GffWriter, write_gff

__all__ = [
    "GffFieldType", "GffField", "GffStruct", "GffFile",
    "LocString", "ResRef",
    "GffReader", "read_gff",
    "GffWriter", "write_gff",
]
