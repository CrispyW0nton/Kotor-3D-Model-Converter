"""Binary RIM read/write: container format for module resources (ResRef + data)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykotor.resource.formats.rim.rim_data import RIM
from pykotor.resource.type import ResourceReader, ResourceType, ResourceWriter, autoclose

if TYPE_CHECKING:
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


class RIMBinaryReader(ResourceReader):
    """Reads RIM (Resource Information Manager) files.

    RIM files are container formats similar to ERF files, used for module resources.
    They store multiple game resources with ResRef, type, and data.

    References:
    ----------
        See rim_data module docstring. Unified K1/TSL: AddResourceImageContents (K1: 0x0040f990), CExoEncapsulatedFile::CExoEncapsulatedFile (K1: 0x0040ef90), AddEncapsulatedContents (K1: 0x0040f3c0), RIM leak string (K1: 0x0073d8a8); TSL: TODO.

        Note: RIM files use similar structure to ERF files but are read-only templates.
        The engine loads RIM files as module blueprints and exports to ERF for runtime mutation.
        Missing Features:
        ----------------
        - ResRef lowercasing (reone lowercases resrefs at rimreader.cpp:47)
        - Field order difference: PyKotor reads restype, resids, resoffsets, ressizes
        vs reone which reads resRef, type (uint16), skips 6 bytes, offset, size

    """

    def __init__(
        self,
        source: SOURCE_TYPES,
        offset: int = 0,
        size: int = 0,
    ):
        super().__init__(source, offset, size)
        self._rim: RIM | None = None

    @autoclose
    def load(self, *, auto_close: bool = True) -> RIM:  # noqa: FBT001, FBT002, ARG002
        self._rim = RIM()

        file_type = self._reader.read_string(4)
        file_version = self._reader.read_string(4)

        if file_type != "RIM ":
            msg = "The RIM file type that was loaded was unrecognized."
            raise ValueError(msg)

        if file_version != "V1.0":
            msg = "The RIM version that was loaded is not supported."
            raise ValueError(msg)

        self._reader.skip(4)  # Skip 0x08 (4 bytes)
        entry_count = self._reader.read_uint32()  # 0x0C
        offset_to_keys = self._reader.read_uint32()  # 0x10

        # Resilience: Vanilla files have 0 for offsets, meaning "Implicit" (Header + Keys)
        # If 0, we calculate them (Header size 120). If non-zero, we respect the file's values.
        if offset_to_keys == 0:
            offset_to_keys = 120

        self._read_entries(entry_count, offset_to_keys)

        return self._rim

    def _read_entries(self, entry_count: int, offset_to_keys: int):
        resrefs: list[str] = []
        resids: list[int] = []
        restypes: list[int] = []
        resoffsets: list[int] = []
        ressizes: list[int] = []

        if entry_count > 0 and offset_to_keys >= self._size:
            msg = "The RIM file is malformed: offset to keys is out of bounds."
            raise ValueError(msg)

        if offset_to_keys < self._size:
            self._reader.seek(offset_to_keys)
            for _ in range(entry_count):
                # reone lowercases resref at line 47, but we preserve case for round-trip fidelity
                # NOTE: Field order differs - PyKotor reads restype before resids, reone reads differently
                resref_str = self._reader.read_string(16).rstrip("\0")
                resrefs.append(resref_str)
                restypes.append(self._reader.read_uint32())
                resids.append(self._reader.read_uint32())
                resoffsets.append(self._reader.read_uint32())
                ressizes.append(self._reader.read_uint32())

            for i in range(len(resrefs)):
                self._reader.seek(resoffsets[i])
                resdata = self._reader.read_bytes(ressizes[i])
                self._rim.set_data(resrefs[i], ResourceType.from_id(restypes[i]), resdata)


class RIMBinaryWriter(ResourceWriter):
    FILE_HEADER_SIZE = 120
    KEY_ELEMENT_SIZE = 32

    def __init__(
        self,
        rim: RIM,
        target: TARGET_TYPES,
    ):
        super().__init__(target)
        self._rim: RIM = rim

    @autoclose
    def write(self, *, auto_close: bool = True):  # noqa: FBT001, FBT002, ARG002  # pyright: ignore[reportUnusedParameters]
        entry_count = len(self._rim)
        # Vanilla uses explicit offsets for keys (120), but 0 for resources (implicit)
        header_offset_to_keys = RIMBinaryWriter.FILE_HEADER_SIZE
        header_offset_to_resources = 0

        # Actual locations
        offset_to_keys = RIMBinaryWriter.FILE_HEADER_SIZE

        self._writer.write_string("RIM ")
        self._writer.write_string("V1.0")
        self._writer.write_uint32(0)  # 0x08
        self._writer.write_uint32(entry_count)  # 0x0C
        self._writer.write_uint32(header_offset_to_keys)  # 0x10
        self._writer.write_uint32(header_offset_to_resources)  # 0x14
        self._writer.write_bytes(b"\0" * 96)  # Padding to 120

        # Align data start to 16 bytes (Vanilla RIM behavior)
        keys_end = offset_to_keys + RIMBinaryWriter.KEY_ELEMENT_SIZE * entry_count
        key_padding = (16 - (keys_end % 16)) % 16

        current_data_offset = keys_end + key_padding
        resource_offsets = []

        # Pass 1: Calculate Offsets with strict vanilla alignment
        for resource in self._rim:
            resource_offsets.append(current_data_offset)

            # Vanilla Resource Padding Logic:
            # 1. Write Data
            # 2. Align to 4 bytes
            # 3. Write 16 bytes of null padding
            # This applies to ALL resources, including the last one (based on file size analysis)

            data_len = len(resource.data)
            current_data_offset += data_len

            padding = (4 - (current_data_offset % 4)) % 4
            current_data_offset += padding + 16

        for resid, resource in enumerate(self._rim):
            self._writer.write_string(str(resource.resref), string_length=16)
            self._writer.write_uint32(resource.restype.type_id)
            self._writer.write_uint32(resid)
            self._writer.write_uint32(resource_offsets[resid])
            self._writer.write_uint32(len(resource.data))

        self._writer.write_bytes(b"\0" * key_padding)

        for resource in self._rim:
            self._writer.write_bytes(resource.data)

            # Write Padding matches calculation
            current_pos = self._writer.position()
            padding = (4 - (current_pos % 4)) % 4
            self._writer.write_bytes(b"\0" * (padding + 16))
