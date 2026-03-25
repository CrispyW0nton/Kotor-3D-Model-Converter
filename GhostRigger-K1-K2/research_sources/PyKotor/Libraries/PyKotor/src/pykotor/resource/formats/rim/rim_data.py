"""This module handles classes relating to editing RIM files.

RIM (Resource Information Module) files store template resources used as module blueprints.
RIM files are similar to ERF files but are read-only from the game's perspective. The game
loads RIM files as templates for modules and exports them to ERF format for runtime mutation.
RIM files store all resources inline with metadata, making them self-contained archives.

References:
----------
        Based on unified K1/TSL RIM structure (shared encapsulation with ERF). Addresses: K1: swkotor.exe, TSL: TODO (verify via REVA).
        - CExoResourceImageFile::AddResourceImageContents (reads RIM headers; Header=120, Count @ 0x0C, Keys @ 0x10, KeySize=32): K1: 0x0040f990, TSL: TODO
        - CExoEncapsulatedFile::CExoEncapsulatedFile: K1: 0x0040ef90, TSL: TODO
        - CExoKeyTable::AddEncapsulatedContents: K1: 0x0040f3c0, TSL: TODO
        - "Table being rebuilt, this RIM is being leaked: %s": K1: 0x0073d8a8, TSL: TODO
        Note: RIM files use similar structure to ERF files but are read-only templates.
        The engine loads RIM files as module blueprints and exports to ERF for runtime mutation.
        RIM files in original game often use "Implicit Offsets" where the offset to keys (0x10)
        is 0, implying it starts immediately after the 120-byte header.

        RIM file format specification
        Binary Format:
        -------------
        Header (120 bytes):
        Offset | Size | Type   | Description
        -------|------|--------|-------------
        0x00   | 4    | char[] | File Type ("RIM ")
        0x04   | 4    | char[] | File Version ("V1.0")
        0x08   | 4    | uint32 | Unknown (typically 0x00000000)
        0x0C   | 4    | uint32 | Resource Count
        0x10   | 4    | uint32 | Offset to Resource Table (0 = Implicit 120)
        0x14   | 1    | byte   | IsExtension (0x01 if extension RIM)
        0x15   | 99   | byte[] | Reserved / Padding

        Resource Entry (32 bytes each):
        Offset | Size | Type   | Description
        -------|------|--------|-------------
        0x00   | 16   | char[] | ResRef (filename, null-padded, max 16 chars)
        0x10   | 4    | uint32 | Resource Type ID
        0x14   | 4    | uint32 | Resource ID (index, usually sequential)
        0x18   | 4    | uint32 | Offset to Resource Data
        0x1C   | 4    | uint32 | Resource Size

        Resource Data:
        Raw binary data for each resource at specified offsets
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykotor.extract.file import ResourceIdentifier
from pykotor.resource.bioware_archive import ArchiveResource, BiowareArchive
from pykotor.resource.type import ResourceType

if TYPE_CHECKING:
    from pykotor.common.misc import ResRef


class RIMResource(ArchiveResource):
    """A resource stored inside a RIM archive.

    RIM resources are similar to ERF resources - they include the ResRef (filename) and
    resource type within the archive metadata. RIM resources are typically read-only from
    the game's perspective, as RIM files serve as module templates.

    References:
    ----------
        See module docstring (K1/TSL addresses). CExoEncapsulatedFile::CExoEncapsulatedFile (K1: 0x0040ef90), CExoKeyTable::AddEncapsulatedContents (K1: 0x0040f3c0); TSL: TODO.
        Derivations and Other Implementations:
        ----------
        https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Formats/KotorRIM/RIMBinaryStructure.cs:88-119
        https://github.com/th3w1zard1/KotOR_IO/tree/master/KotOR_IO/File



    Attributes:
    ----------
        All inherited from ArchiveResource (resref, restype, data, size)
        RIM resources have no additional attributes beyond ArchiveResource
    """

    def __init__(self, resref: ResRef, restype: ResourceType, data: bytes):
        # https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Formats/KotorRIM/RIMBinaryStructure.cs:104-108
        # https://github.com/th3w1zard1/KotOR_IO/tree/master/KotOR_IO/File Formats/RIM.cs:63-64
        # ResRef stored in Resource Entry (16 bytes, null-padded)
        # ResourceType stored in Resource Entry (4 bytes, uint32)
        # Resource data referenced via offset and size fields
        super().__init__(resref=resref, restype=restype, data=data)


class RIM(BiowareArchive):
    """Represents a RIM (Resource Information Module) file.

    RIM files are template archives used to initialize game modules. They are similar to ERF
    files but serve a different purpose - providing immutable resource templates that the game
    engine reads and exports to ERF format for runtime use. RIM files can also be extensions
    to other RIM files (marked with 'x' in filename).

    References:
    ----------
        See module docstring (K1/TSL addresses). CExoEncapsulatedFile::CExoEncapsulatedFile, CExoKeyTable::AddEncapsulatedContents; TSL: TODO.
        Derivations and Other Implementations:
        ----------
        https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Formats/KotorRIM/RIMBinaryStructure.cs:13-53
        https://github.com/th3w1zard1/KotOR_IO/tree/master/KotOR_IO/File



    Attributes:
    ----------
        Inherits from BiowareArchive: _resources, _resource_dict, etc.
        RIM-specific attributes managed by underlying BiowareArchive
    """

    BINARY_TYPE = ResourceType.RIM
    ARCHIVE_TYPE: type[ArchiveResource] = RIMResource
    COMPARABLE_SET_FIELDS = ("_resources",)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(resources={len(self._resources)})"

    def get(self, resname: str, restype: ResourceType) -> bytes | None:
        """Return the raw bytes for a resource, or None when not present."""
        resource = self._resource_dict.get(ResourceIdentifier(resname, restype))
        return None if resource is None else resource.data

    def remove(self, resname: str, restype: ResourceType) -> None:
        """Remove a resource from the archive if it exists."""
        key = ResourceIdentifier(resname, restype)
        resource = self._resource_dict.pop(key, None)
        if resource is not None:
            self._resources.remove(resource)

    def to_erf(self):
        """Return an ERF archive with the same resource payload."""
        from pykotor.resource.formats.erf.erf_data import ERF  # Prevent circular imports  # noqa: PLC0415

        erf = ERF()
        for resource in self._resources:
            erf.set_data(str(resource.resref), resource.restype, resource.data)
        return erf

    def get_resource_offset(self, resource: ArchiveResource) -> int:
        """Compute the binary offset for a given resource when serialised."""
        if not isinstance(resource, RIMResource):
            raise TypeError("Resource is not a RIMResource")
        from pykotor.resource.formats.rim.io_rim import RIMBinaryWriter  # noqa: PLC0415

        entry_count = len(self._resources)
        data_start = RIMBinaryWriter.FILE_HEADER_SIZE + RIMBinaryWriter.KEY_ELEMENT_SIZE * entry_count

        offset = data_start
        for res in self._resources:
            if res == resource:
                return offset
            offset += len(res.data)
        msg = "Resource is not present in RIM resource list"
        raise ValueError(msg)

    def __eq__(self, other: object):
        from pykotor.resource.formats.erf.erf_data import ERF  # Prevent circular imports  # noqa: PLC0415

        if not isinstance(other, (RIM, ERF)):
            return NotImplemented  # type: ignore[no-any-return]
        return set(self._resources) == set(other._resources)

    def __hash__(self) -> int:
        return hash(tuple(self._resources))
