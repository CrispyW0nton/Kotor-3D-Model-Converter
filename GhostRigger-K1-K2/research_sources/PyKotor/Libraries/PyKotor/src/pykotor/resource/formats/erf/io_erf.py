"""Binary ERF (encapsulated resource) read/write: header, key list, resource data."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykotor.resource.formats.erf.erf_data import ERF, ERFType
from pykotor.resource.type import ResourceReader, ResourceType, ResourceWriter, autoclose

if TYPE_CHECKING:
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


class ERFBinaryReader(ResourceReader):
    """Reads ERF (Encapsulated Resource File) files.

    ERF files are container formats that store multiple game resources. Used for MOD files,
    save games, and other resource collections.

    References:
    ----------
        Based on unified K1/TSL ERF structure. See erf_data module docstring; addresses (K1: swkotor.exe, TSL: TODO via REVA).
        - CExoResourceImageFile::AddResourceImageContents (reads RIM headers; Header=120, Count @ 0x0C, Keys @ 0x10, KeySize=32): K1: 0x0040f990, TSL: TODO
        - CExoEncapsulatedFile::CExoEncapsulatedFile: K1: 0x0040ef90, TSL: TODO
        - CExoKeyTable::AddEncapsulatedContents: K1: 0x0040f3c0, TSL: TODO. Validates "MOD V1.0"; header 160 bytes; Type [0x00], Version [0x04], EntryCount [0x10], KeyOffset [0x18].
        - "MOD V1.0" string: K1: 0x0074539c, TSL: TODO
        - "Table being rebuilt, this RIM is being leaked: %s": K1: 0x0073d8a8, TSL: TODO

    Note:
    ----
        ERF files are container formats that store multiple game resources. Used for MOD files,
        save games, and other resource collections.

    Missing Features: TODO: address
    ----------------
        - ResRef lowercasing (reone lowercases at erfreader.cpp:63)
        - ERF password/decryption support (xoreos-tools supports at unerf.cpp:108-145)

    """

    def __init__(
        self,
        source: SOURCE_TYPES,
        offset: int = 0,
        size: int = 0,
    ):
        super().__init__(source, offset, size)
        self._erf: ERF | None = None

    @autoclose
    def load(self, *, auto_close: bool = True) -> ERF:  # noqa: FBT001, FBT002, ARG002
        """Load ERF file.

        Args:
        ----
            self: The ERF object

        Returns:
        -------
            ERF: The loaded ERF object

        Processing Logic:
        ----------------
            - Read file header and validate file type and version
            - Read entry count and offsets to keys and resources sections
            - Read keys section into lists of ref, id, type
            - Read resources section into lists of offsets and sizes
            - Seek to each resource and read data into ERF object.
        """
        file_type: str = self._reader.read_string(4)
        file_version: str = self._reader.read_string(4)

        if file_version != "V1.0":
            msg = f"ERF version '{file_version}' is unsupported."
            raise ValueError(msg)

        erf_type: ERFType | None = next(
            (x for x in ERFType if x.value == file_type),
            None,
        )
        if erf_type is None:
            msg = f"Not a valid ERF file: '{file_type}'"
            raise ValueError(msg)

        self._erf = ERF(erf_type)

        language_count: int = self._reader.read_uint32()
        localized_string_size: int = self._reader.read_uint32()
        entry_count: int = self._reader.read_uint32()
        offset_to_localized_strings: int = self._reader.read_uint32()
        offset_to_keys: int = self._reader.read_uint32()
        offset_to_resources: int = self._reader.read_uint32()

        self._erf.build_year = self._reader.read_uint32()
        self._erf.build_day = self._reader.read_uint32()
        self._erf.description_strref = self._reader.read_uint32()

        # Resilience: Some ERF/MOD files might use implicit 160 offset if these are 0
        if offset_to_keys == 0:
            offset_to_keys = 160

        if offset_to_resources == 0:
            # If keys are at 160, resources are after (entry_count * 24)
            offset_to_resources = offset_to_keys + (entry_count * 24)

        # Guard against obviously corrupt headers before any seeking/allocation.
        _MAX_SANE_COUNT = 65536  # No legitimate ERF/MOD contains more than this many entries
        _MAX_SANE_LANG_COUNT = 32

        if entry_count > _MAX_SANE_COUNT:
            msg = f"ERF entry_count {entry_count} exceeds sanity limit; file may be malformed or truncated."
            raise ValueError(msg)

        if offset_to_keys >= self._size and entry_count > 0:
            msg = f"ERF offset_to_keys {offset_to_keys} is beyond file size {self._size}; file is malformed."
            raise ValueError(msg)

        if offset_to_resources >= self._size and entry_count > 0:
            msg = f"ERF offset_to_resources {offset_to_resources} is beyond file size {self._size}; file is malformed."
            raise ValueError(msg)

        # Read Localized Strings
        if language_count > 0 and offset_to_localized_strings > 0:
            if language_count > _MAX_SANE_LANG_COUNT:
                msg = f"ERF language_count {language_count} exceeds sanity limit; file may be malformed."
                raise ValueError(msg)
            self._reader.seek(offset_to_localized_strings)
            block_end = offset_to_localized_strings + localized_string_size
            # The count is number of entries, not bytes. But the entries are variable size.
            # Entry: [LangID (4)][Size (4)][String (Size)]
            for _ in range(language_count):
                if self._reader.position() >= block_end:
                    break
                lang_id = self._reader.read_uint32()
                str_size = self._reader.read_uint32()
                # Guard against absurdly large string sizes in corrupt files.
                remaining_block = block_end - self._reader.position()
                if str_size > remaining_block:
                    msg = f"ERF localized string size {str_size} exceeds remaining block size {remaining_block}."
                    raise ValueError(msg)
                # Use windows-1252 as safe default for legacy BioWare strings
                text = self._reader.read_string(str_size, encoding="windows-1252")
                self._erf.localized_strings[lang_id] = text

        resrefs: list[str] = []
        resids: list[int] = []
        restypes: list[int] = []
        self._reader.seek(offset_to_keys)
        for _ in range(entry_count):
            # reone lowercases resrefs at line 63, but we preserve case for round-trip fidelity
            resref_str = self._reader.read_string(16).rstrip("\0")
            resrefs.append(resref_str)
            resids.append(self._reader.read_uint32())
            restypes.append(self._reader.read_uint16())
            self._reader.skip(2)

        resoffsets: list[int] = []
        ressizes: list[int] = []
        self._reader.seek(offset_to_resources)
        for _ in range(entry_count):
            resoffsets.append(self._reader.read_uint32())
            ressizes.append(self._reader.read_uint32())

        for i in range(entry_count):
            self._reader.seek(resoffsets[i])
            resdata: bytes = self._reader.read_bytes(ressizes[i])
            self._erf.set_data(resrefs[i], ResourceType.from_id(restypes[i]), resdata)

        return self._erf


class ERFBinaryWriter(ResourceWriter):
    FILE_HEADER_SIZE = 160
    KEY_ELEMENT_SIZE = 24
    RESOURCE_ELEMENT_SIZE = 8

    def __init__(
        self,
        erf: ERF,
        target: TARGET_TYPES,
    ):
        super().__init__(target)
        self.erf: ERF = erf

    @autoclose
    def write(self, *, auto_close: bool = True):  # noqa: FBT001, FBT002, ARG002  # pyright: ignore[reportUnusedParameters]
        entry_count: int = len(self.erf)

        # Calculate Localized String Block Size
        language_count = len(self.erf.localized_strings)
        localized_string_block_size = 0
        sorted_langs = sorted(self.erf.localized_strings.items())  # Ensure deterministic order

        for _, text in sorted_langs:
            # Entry: 4 (ID) + 4 (Size) + len(text)
            localized_string_block_size += 8 + len(text.encode("windows-1252"))

        offset_to_localized_strings = 0
        if language_count > 0:
            offset_to_localized_strings = ERFBinaryWriter.FILE_HEADER_SIZE
        elif self.erf.erf_type == ERFType.ERF:
            # Heuristic: Generic ERF files (texture packs) tend to use 160 even if empty
            offset_to_localized_strings = ERFBinaryWriter.FILE_HEADER_SIZE

        offset_to_keys: int = ERFBinaryWriter.FILE_HEADER_SIZE + localized_string_block_size
        offset_to_resources: int = offset_to_keys + ERFBinaryWriter.KEY_ELEMENT_SIZE * entry_count

        # Use stored values if available, otherwise fallback to defaults/logic
        description_strref = self.erf.description_strref

        # Legacy auto-logic for new files if not set
        if description_strref == -1:  # Default from init
            if self.erf.is_save:
                description_strref = 0x00000000
            elif self.erf.erf_type is ERFType.ERF:
                description_strref = 0xFFFFFFFF  # Standard Empty
            elif self.erf.erf_type is ERFType.MOD:
                # 0xFFFFFFFF is standard for most modules (Verified via bulk scan of rimtesting/modules)
                # Note: TSL LIPS files consistently use 0xCDCDCDCD (Debug Fill), but we default to standard empty.
                description_strref = 0xFFFFFFFF

        self._writer.write_string(self.erf.erf_type.value)
        self._writer.write_string("V1.0")
        self._writer.write_uint32(language_count)
        self._writer.write_uint32(localized_string_block_size)
        self._writer.write_uint32(entry_count)
        self._writer.write_uint32(offset_to_localized_strings)
        self._writer.write_uint32(offset_to_keys)
        self._writer.write_uint32(offset_to_resources)
        self._writer.write_uint32(self.erf.build_year)
        self._writer.write_uint32(self.erf.build_day)
        self._writer.write_uint32(description_strref)
        self._writer.write_bytes(b"\0" * 116)

        # Write Localized Strings
        for lang_id, text in sorted_langs:
            encoded_text = text.encode("windows-1252")
            self._writer.write_uint32(lang_id)
            self._writer.write_uint32(len(encoded_text))
            self._writer.write_bytes(encoded_text)

        for resid, resource in enumerate(self.erf):
            self._writer.write_string(str(resource.resref), string_length=16)
            self._writer.write_uint32(resid)
            self._writer.write_uint16(resource.restype.type_id)
            self._writer.write_uint16(0)

        data_offset: int = offset_to_resources + ERFBinaryWriter.RESOURCE_ELEMENT_SIZE * entry_count
        for resource in self.erf:
            self._writer.write_uint32(data_offset)
            self._writer.write_uint32(len(resource.data))
            data_offset += len(resource.data)

        for resource in self.erf:
            self._writer.write_bytes(resource.data)
