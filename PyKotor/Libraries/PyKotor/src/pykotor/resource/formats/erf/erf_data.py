"""This module handles classes relating to editing ERF files.

ERF (Encapsulated Resource File) files are self-contained archives used for modules, save games,
texture packs, and hak paks. Unlike BIF files which require a KEY file for filename lookups,
ERF files store both resource names (ResRefs) and data in the same file. They also support
localized strings for descriptions in multiple languages.

References:
----------
        Based on unified K1 (swkotor.exe) and TSL (swkotor2.exe) ERF structure.
        Addresses: (K1: swkotor.exe, TSL: swkotor2.exe — verify/fill TSL via REVA when available).

        - CExoEncapsulatedFile::CExoEncapsulatedFile — constructor for encapsulated file.
          K1: 0x0040ef90, TSL: TODO
        - CExoKeyTable::AddEncapsulatedContents — adds ERF/MOD/SAV contents to key table; tries NWM, MOD, SAV, ERF; opens "rb"; reads header/entries.
          K1: 0x0040f3c0, TSL: TODO
          Stack/header: Type [0x00], Version [0x04] ("V1.0"), EntryCount [0x10], KeyOffset [0x18]; Build Year/Day/DescStrRef allocated but unused.
        - "MOD V1.0" string (MOD file version identifier): K1: 0x0074539c, TSL: TODO
        ERF file format specification
        Binary Format:
        -------------
        Header (160 bytes):
        Offset | Size | Type   | Description
        -------|------|--------|-------------
        0x00   | 4    | char[] | File Type ("ERF ", "MOD ", "SAV ", "HAK ")
        0x04   | 4    | char[] | File Version ("V1.0")
        0x08   | 4    | uint32 | Language Count
        0x0C   | 4    | uint32 | Localized String Size (total bytes)
        0x10   | 4    | uint32 | Entry Count (number of resources)
        0x14   | 4    | uint32 | Offset to Localized String List
        0x18   | 4    | uint32 | Offset to Key List
        0x1C   | 4    | uint32 | Offset to Resource List
        0x20   | 4    | uint32 | Build Year (years since 1900)
        0x24   | 4    | uint32 | Build Day (days since Jan 1)
        0x28   | 4    | uint32 | Description StrRef (TLK reference)
        0x2C   | 116  | byte[] | Reserved (padding, usually zeros)
        Localized String Entry (variable length per language):
        - 4 bytes: Language ID (see Language enum)
        - 4 bytes: String Size (length in bytes)
        - N bytes: String Data (windows-1252 encoded text)
        Key Entry (24 bytes each):
        Offset | Size | Type   | Description
        -------|------|--------|-------------
        0x00   | 16   | char[] | ResRef (filename, null-padded, max 16 chars)
        0x10   | 4    | uint32 | Resource ID (index into resource list)
        0x14   | 2    | uint16 | Resource Type
        0x16   | 2    | uint16 | Unused (padding)
        Resource Entry (8 bytes each):
        Offset | Size | Type   | Description
        -------|------|--------|-------------
        0x00   | 4    | uint32 | Offset to Resource Data
        0x04   | 4    | uint32 | Resource Size
        Resource Data:
        Raw binary data for each resource at specified offsets


    Reference: Original BioWare engine binaries (ERF from swkotor.exe, swkotor2.exe). See module docstring for K1/TSL addresses.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from pykotor.common.misc import ResRef
from pykotor.resource.bioware_archive import ArchiveResource, BiowareArchive
from pykotor.resource.type import ResourceType
from pykotor.tools.misc import is_erf_file, is_mod_file, is_sav_file

if TYPE_CHECKING:
    import os

    from pykotor.common.misc import ResRef


class ERFResource(ArchiveResource):
    """A single resource stored in an ERF/MOD/SAV file.

    Unlike BIF resources, ERF resources include their ResRef (filename) directly in the
    archive. Each resource is identified by a unique ResRef and ResourceType combination.

    References:
    ----------
        See module docstring for engine addresses (K1 + TSL TODO). CExoEncapsulatedFile::CExoEncapsulatedFile, CExoKeyTable::AddEncapsulatedContents, "MOD V1.0".
        https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Formats/KotorERF/ERFBinaryStructure.cs - Key and Resource entries
        https://github.com/th3w1zard1/KotOR_IO/tree/master/KotOR_IO/File Formats/ERF.cs - Key and Resource classes
        https://github.com/th3w1zard1/KotOR.js/tree/master/src/interface/resource/IERFKeyEntry.ts - Key entry interface
        https://github.com/th3w1zard1/KotOR.js/tree/master/src/interface/resource/IERFResource.ts - Resource entry interface


    Attributes:
    ----------
        All attributes inherited from ArchiveResource (resref, restype, data, size)
        ERF resources have no additional attributes beyond the base ArchiveResource
    """

    def __init__(self, resref: ResRef, restype: ResourceType, data: bytes):
        # https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Formats/KotorERF/ERFBinaryStructure.cs:119-120
        # https://github.com/th3w1zard1/KotOR_IO/tree/master/KotOR_IO/File Formats/ERF.cs:197-198
        # https://github.com/th3w1zard1/KotOR.js/tree/master/src/resource/ERFObject.ts:103-107
        # ResRef stored in Key Entry (16 bytes, null-padded)
        # ResourceType stored in Key Entry (2 bytes, uint16)
        # Resource data referenced via Resource Entry (offset + size)
        super().__init__(resref=resref, restype=restype, data=data)


class ERFType(Enum):
    """The type of ERF file based on file header signature.

    ERF files can have different type signatures depending on their purpose:
    - ERF: Generic encapsulated resource file (texture packs, etc.)
    - MOD: Module file (game areas/levels)
    - SAV: Save game file
    - HAK: Hak pak file (custom content, unused in KotOR)

    References:
    ----------
        See module docstring for engine addresses (K1 + TSL TODO). CExoEncapsulatedFile::CExoEncapsulatedFile, CExoKeyTable::AddEncapsulatedContents, "MOD V1.0".
        https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Formats/KotorERF/ERFBinaryStructure.cs - FileType field
        https://github.com/th3w1zard1/KotOR_IO/tree/master/KotOR_IO/File Formats/ERF.cs - FileType reading
        https://github.com/th3w1zard1/KotOR.js/tree/master/src/resource/ERFObject.ts - File type default

    """

    ERF = "ERF "  # Generic ERF archive (texture packs, etc.)
    MOD = "MOD "  # Module file (game levels/areas)

    @classmethod
    def from_extension(cls, ext_or_filepath: os.PathLike | str) -> ERFType:
        if is_erf_file(ext_or_filepath):
            return cls.ERF
        if is_mod_file(ext_or_filepath):
            return cls.MOD
        if is_sav_file(ext_or_filepath):  # .SAV files still use the 'MOD ' signature in its first 4 bytes of the file header
            return cls.MOD
        msg = f"Invalid ERF extension in filepath '{ext_or_filepath}'."
        raise ValueError(msg)


class ERF(BiowareArchive):
    """Represents an ERF/MOD/SAV file.

    ERF (Encapsulated Resource File) is a self-contained archive format used for game modules,
    save games, and resource packs. Unlike BIF+KEY pairs, ERF files contain both resource names
    and data in a single file, making them ideal for distributable content like mods.

    References:
    ----------
        See module docstring for engine addresses (K1 + TSL TODO). CExoEncapsulatedFile::CExoEncapsulatedFile, CExoKeyTable::AddEncapsulatedContents, "MOD V1.0".
        https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Formats/KotorERF/ERFBinaryStructure.cs - FileRoot class
        https://github.com/th3w1zard1/KotOR_IO/tree/master/KotOR_IO/File Formats/ERF.cs - Complete ERF implementation
        https://github.com/th3w1zard1/KotOR.js/tree/master/src/resource/ERFObject.ts - ERFObject class


    Attributes:
    ----------
        erf_type: File type signature (ERF, MOD, SAV, HAK)
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/ERFBinaryStructure.cs:73 (FileType property)
            Reference: https://github.com/th3w1zard1/KotOR_IO/tree/master/ERF.cs:46 (FileType field)
            Reference: https://github.com/th3w1zard1/KotOR.js/tree/master/ERFObject.ts:45 (fileType default)
            Determines intended use of the archive
            ERF = texture packs, MOD = game modules, SAV = save games

        is_save: Flag indicating if this is a save game ERF
            Reference: https://github.com/th3w1zard1/KotOR_IO/tree/master/ERF.cs:15-16 (save game comment)
            Save games use MOD signature but have different structure
            Affects how certain fields are interpreted (e.g., build date)
            PyKotor-specific flag for save game handling

        build_year: Years since 1900 (e.g., 103 = 2003)
            Reference: https://github.com/th3w1zard1/Kotor.NET/blob/master/Kotor.NET/Formats/KotorERF/ERFBinaryStructure.cs:84 (BuildYear)

        build_day: Day of the year (1-366)
            Reference: https://github.com/th3w1zard1/Kotor.NET/blob/master/Kotor.NET/Formats/KotorERF/ERFBinaryStructure.cs:85 (BuildDay)

        description_strref: TLK String Reference for module description
            Reference: ERF File Format Specification (Offset 0x28)
            Note: Kotor.NET stops reading at 0x24 (BuildDay), skipping this field.
            Defaults: -1 for MOD/NWM, 0 for SAV

        localized_strings: Dictionary providing descriptions in multiple languages (LanguageID -> String)
            Reference: ERF File Format Specification (Offsets 0x08, 0x0C, 0x14)
            Note: reone (erfreader.cpp:28) and Kotor.NET (ERFBinaryStructure.cs:100) skip these fields.
            Used primarily in MOD files for module names/loading screens
    """

    BINARY_TYPE = ResourceType.ERF
    ARCHIVE_TYPE: type[ArchiveResource] = ERFResource
    COMPARABLE_FIELDS = ("erf_type", "is_save_erf", "build_year", "build_day", "description_strref", "localized_strings")
    COMPARABLE_SET_FIELDS = ("_resources",)

    def __init__(
        self,
        erf_type: ERFType = ERFType.ERF,
        *,
        is_save: bool = False,
        build_year: int = 0,
        build_day: int = 0,
        description_strref: int = -1,
        localized_strings: dict[int, str] | None = None,
    ):
        super().__init__()

        # https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Formats/KotorERF/ERFBinaryStructure.cs:73
        # https://github.com/th3w1zard1/KotOR_IO/tree/master/KotOR_IO/File Formats/ERF.cs:46
        # https://github.com/th3w1zard1/KotOR.js/tree/master/src/resource/ERFObject.ts:45
        # File type signature (ERF, MOD, SAV, HAK)
        self.erf_type: ERFType = erf_type

        # PyKotor-specific flag for save game handling
        # Save games use MOD signature but have different behavior
        self.is_save: bool = is_save

        self.build_year: int = build_year
        self.build_day: int = build_day
        self.description_strref: int = description_strref
        self.localized_strings: dict[int, str] = localized_strings if localized_strings is not None else {}

    @property
    def is_save_erf(self) -> bool:
        """Alias for ComparableMixin compatibility."""
        return self.is_save

    @is_save_erf.setter
    def is_save_erf(self, value: bool) -> None:
        self.is_save = value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.erf_type!r}, is_save={self.is_save}, desc_strref={self.description_strref})"

    def __eq__(self, other: object):
        from pykotor.resource.formats.rim import RIM  # Prevent circular imports  # noqa: PLC0415

        if not isinstance(other, (ERF, RIM)):
            return NotImplemented  # type: ignore[no-any-return]
        return set(self._resources) == set(other._resources)

    def __hash__(self) -> int:
        return hash((self.erf_type, tuple(self._resources), self.is_save, self.description_strref))

    def get_resource_offset(self, resource: ArchiveResource) -> int:
        """Return the byte offset of a resource's data in serialized archive order."""
        from pykotor.resource.formats.erf.io_erf import ERFBinaryWriter

        entry_count = len(self._resources)
        data_start = ERFBinaryWriter.FILE_HEADER_SIZE + ERFBinaryWriter.KEY_ELEMENT_SIZE * entry_count

        offset = data_start
        for res in self._resources:
            if res == resource:
                return offset
            offset += len(res.data)
        raise ValueError("Resource is not present in ERF resource list")

